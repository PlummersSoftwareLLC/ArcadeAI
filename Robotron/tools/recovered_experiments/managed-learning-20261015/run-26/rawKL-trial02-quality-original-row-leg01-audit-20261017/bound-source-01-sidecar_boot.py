#!/usr/bin/env python3
"""Immutable, validated Robotron boot assets for private evaluation actors.

Uses only the standard library. Capturing reads the selected live source files;
restoring writes only new files under an already-created private actor directory.
No emulator, socket, trainer, replay, or GPU is opened here.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import xml.etree.ElementTree as ET


SCHEMA = "robotron-sidecar-boot-v1"
REQUIRED_PATHS = ("nvram/robotron/nvram", "cfg/robotron.cfg", "ini/mame.ini")
MANIFEST_NAME = "manifest.json"
_PROC_ROOT = Path("/proc")
_MAX_ASSET_BYTES = 1024 * 1024


def _path(value):
    return Path(os.path.abspath(Path(value).expanduser()))


def _no_symlinks(path, *, missing_ok=False):
    for component in reversed((path, *path.parents)):
        try:
            mode = component.lstat().st_mode
        except FileNotFoundError:
            if missing_ok:
                continue
            raise
        if stat.S_ISLNK(mode):
            raise ValueError(f"Symlinks are forbidden in boot-asset paths: {component}")


def _signature(value):
    return {name: getattr(value, name) for name in
            ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_state(path):
    _no_symlinks(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= _MAX_ASSET_BYTES:
        raise ValueError(f"Boot asset must be a nonempty bounded regular file: {path}")
    digest = _sha256(path)
    after = path.stat()
    if _signature(before) != _signature(after):
        raise RuntimeError(f"Boot source changed while reading: {path}")
    return dict(path=str(path), stat=_signature(after), sha256=digest)


def _vanished(error):
    return isinstance(error, FileNotFoundError) or error.errno in (errno.ENOENT, errno.ESRCH)


def _scan_writable_sources(sources):
    """Reject writable source FDs; unreadable plausible writers fail.

    Inaccessible unrelated desktop/system FD tables are a recorded visibility
    limit. MAME, Python and Robotron/trainer processes must be inspectable.
    Stable inode/stat/hash checks independently bracket the complete copy.
    """
    identities = {(value["stat"]["st_dev"], value["stat"]["st_ino"]): relative
                  for relative, value in sources.items()}
    checked, skipped = 0, []
    for process in _PROC_ROOT.iterdir():
        if not process.name.isdigit():
            continue
        relevant, same_user, command = False, False, "unknown"
        try:
            same_user = process.stat().st_uid == os.geteuid()
            relevant = same_user  # Unknown same-user executables fail closed.
            try:
                command = (process / "comm").read_text().strip()
                name = command.lower()
                relevant = (any(token in name for token in ("mame", "robotron", "trainer"))
                            or same_user and "python" in name)
                try:
                    arguments = (process / "cmdline").read_bytes().lower()
                    relevant |= any(token in arguments for token in (b"mame", b"robotron", b"starttrainer"))
                except OSError as error:
                    if _vanished(error):
                        continue
            except OSError as error:
                if _vanished(error):
                    continue
            descriptors = list((process / "fd").iterdir())
        except OSError as error:
            if _vanished(error):
                continue
            if relevant:
                raise RuntimeError(f"Cannot inspect relevant process {process.name} ({command}) for boot-source writers") from error
            skipped.append(dict(pid=int(process.name), command=command, same_user=same_user))
            continue
        checked += 1
        for descriptor in descriptors:
            try:
                value = descriptor.stat()
            except OSError as error:
                if _vanished(error):
                    continue
                if relevant:
                    raise RuntimeError(f"Cannot inspect relevant FD {descriptor}") from error
                continue
            relative = identities.get((value.st_dev, value.st_ino))
            if relative is None:
                continue
            try:
                info = (process / "fdinfo" / descriptor.name).read_text()
                flags = int(next(line.split(":", 1)[1].strip() for line in info.splitlines()
                                 if line.startswith("flags:")), 8)
            except (OSError, StopIteration, ValueError) as error:
                if isinstance(error, OSError) and _vanished(error):
                    continue
                raise RuntimeError(f"Cannot determine access flags for a source FD: {descriptor}") from error
            if flags & os.O_ACCMODE in (os.O_WRONLY, os.O_RDWR):
                raise RuntimeError(f"Boot source has an active writable FD: pid={process.name} fd={descriptor.name} asset={relative}")
    return dict(checked_processes=checked, active_writers=0,
                uninspectable_unrelated_processes=skipped,
                policy="Reject writable source FDs and unreadable MAME/Robotron/trainer or same-user Python processes; record inaccessible unrelated processes as a visibility limit.")


def _validate_cfg(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise ValueError("Robotron cfg is not valid XML") from error
    systems = root.findall("system")
    if (root.tag != "mameconfig" or root.attrib.get("version") != "10"
            or len(systems) != 1 or systems[0].attrib.get("name") != "robotron"):
        raise ValueError("Boot cfg must be a version-10 mameconfig for exactly Robotron")


def _identity(manifest):
    fields = {key: value for key, value in manifest.items() if key != "identity"}
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _remove_owned_snapshot(directory):
    for current, directories, _ in os.walk(directory):
        Path(current).chmod(0o700)
        for name in directories:
            (Path(current) / name).chmod(0o700)
    shutil.rmtree(directory)


def capture_snapshot(destination, *, nvram_source=Path("/home/dave/.mame/nvram/robotron/nvram"),
                     cfg_source=Path("/home/dave/.mame/cfg/robotron.cfg"),
                     ini_source=Path("/etc/mame/mame.ini")):
    """Capture stable source files into a NEW immutable snapshot directory."""
    destination = _path(destination)
    _no_symlinks(destination, missing_ok=True)
    paths = dict(zip(REQUIRED_PATHS, map(_path, (nvram_source, cfg_source, ini_source))))
    sources = {relative: _source_state(path) for relative, path in paths.items()}
    if sources[REQUIRED_PATHS[0]]["stat"]["st_size"] != 1024:
        raise ValueError("Robotron NVRAM must contain exactly 1024 bytes")
    _validate_cfg(paths["cfg/robotron.cfg"])
    before_writers = _scan_writable_sources(sources)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        files = {}
        for relative, source in paths.items():
            target = destination / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Exclusive creation guarantees independent storage and no overwrite.
            with source.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
                writer.flush()
                os.fsync(writer.fileno())
            files[relative] = dict(bytes=target.stat().st_size, sha256=_sha256(target))
            assert target.stat().st_ino != source.stat().st_ino or target.stat().st_dev != source.stat().st_dev
        after_sources = {relative: _source_state(path) for relative, path in paths.items()}
        if after_sources != sources:
            raise RuntimeError("Boot source files changed during the full snapshot copy")
        after_writers = _scan_writable_sources(after_sources)
        for relative, value in files.items():
            if (value["bytes"] != sources[relative]["stat"]["st_size"]
                    or value["sha256"] != sources[relative]["sha256"]):
                raise RuntimeError(f"Boot copy does not match source: {relative}")
        _validate_cfg(destination / "cfg/robotron.cfg")
        manifest = dict(schema=SCHEMA, created_utc=datetime.now(timezone.utc).isoformat(),
                        files=files, source_files=sources,
                        writer_checks=dict(before=before_writers, after=after_writers))
        manifest["identity"] = _identity(manifest)
        with (destination / MANIFEST_NAME).open("x") as stream:
            stream.write(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        for current, _, names in os.walk(destination, topdown=False):
            for name in names:
                (Path(current) / name).chmod(0o444)
            Path(current).chmod(0o555)
        return load_snapshot(destination)
    except BaseException:
        _remove_owned_snapshot(destination)
        raise


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate boot manifest key: {key}")
        result[key] = value
    return result


def load_snapshot(directory):
    """Validate exact paths, immutable files, XML, manifest identity and hashes."""
    directory = _path(directory)
    _no_symlinks(directory)
    if not directory.is_dir():
        raise ValueError("Boot snapshot must be a directory")
    if directory.stat().st_mode & 0o222:
        raise ValueError("Boot snapshot directories must be immutable")
    files, directories = set(), set()
    for current, children, names in os.walk(directory, followlinks=False):
        for name in (*children, *names):
            target = Path(current) / name
            if target.is_symlink():
                raise ValueError(f"Snapshot contains a symlink: {target}")
            if target.is_dir() and target.stat().st_mode & 0o222:
                raise ValueError("Boot snapshot directories must be immutable")
        directories.update(str((Path(current) / name).relative_to(directory)) for name in children)
        files.update(str((Path(current) / name).relative_to(directory)) for name in names)
    if files != {*REQUIRED_PATHS, MANIFEST_NAME} or directories != {"cfg", "ini", "nvram", "nvram/robotron"}:
        raise ValueError("Boot snapshot must contain exactly the required asset paths and manifest")
    for relative in files:
        value = (directory / relative).lstat()
        if not stat.S_ISREG(value.st_mode) or value.st_mode & 0o222 or value.st_nlink != 1:
            raise ValueError(f"Boot snapshot files must be independent immutable regular files: {relative}")
    manifest_path = directory / MANIFEST_NAME
    if manifest_path.stat().st_size > _MAX_ASSET_BYTES:
        raise ValueError("Boot manifest is unexpectedly large")
    manifest = json.loads(manifest_path.read_text(), object_pairs_hook=_unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if (not isinstance(manifest, dict)
            or set(manifest) != {"schema", "created_utc", "files", "source_files", "writer_checks", "identity"}
            or manifest["schema"] != SCHEMA or manifest["identity"] != _identity(manifest)
            or set(manifest["files"]) != set(REQUIRED_PATHS)
            or set(manifest["source_files"]) != set(REQUIRED_PATHS)):
        raise ValueError("Boot snapshot manifest schema, identity or paths differ")
    for relative, expected in manifest["files"].items():
        if (not isinstance(expected, dict) or set(expected) != {"bytes", "sha256"}
                or isinstance(expected["bytes"], bool) or not isinstance(expected["bytes"], int)
                or not 0 < expected["bytes"] <= _MAX_ASSET_BYTES
                or not isinstance(expected["sha256"], str) or len(expected["sha256"]) != 64):
            raise ValueError(f"Invalid boot asset manifest entry: {relative}")
        target = directory / relative
        if target.stat().st_size != expected["bytes"] or _sha256(target) != expected["sha256"]:
            raise ValueError(f"Boot snapshot asset changed: {relative}")
    if manifest["files"][REQUIRED_PATHS[0]]["bytes"] != 1024:
        raise ValueError("Robotron NVRAM must contain exactly 1024 bytes")
    _validate_cfg(directory / "cfg/robotron.cfg")
    return dict(manifest, directory=str(directory), manifest_path=str(manifest_path),
                manifest_sha256=_sha256(manifest_path))


def restore_snapshot(directory, actor_directory):
    """Restore new independent writable files into existing private cfg/ini/nvram dirs."""
    manifest = load_snapshot(directory)
    seed, actor = _path(directory), _path(actor_directory)
    _no_symlinks(actor)
    for name in ("cfg", "ini", "nvram"):
        _no_symlinks(actor / name)
        if not (actor / name).is_dir():
            raise ValueError(f"Create the private actor {name} directory before restoring")
    targets = {relative: actor / relative for relative in REQUIRED_PATHS}
    for target in targets.values():
        _no_symlinks(target, missing_ok=True)
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite an existing actor boot asset: {target}")
    created_files, created_directory = [], False
    try:
        robotron = actor / "nvram/robotron"
        if not robotron.exists():
            robotron.mkdir(mode=0o700)
            created_directory = True
        for relative, target in targets.items():
            with (seed / relative).open("rb") as reader, target.open("xb") as writer:
                created_files.append(target)
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
                writer.flush()
                os.fsync(writer.fileno())
            target.chmod(0o600)
            if _sha256(target) != manifest["files"][relative]["sha256"]:
                raise RuntimeError(f"Restored boot asset mismatch: {relative}")
        # Revalidate the immutable seed after the complete restore operation.
        if load_snapshot(seed)["manifest_sha256"] != manifest["manifest_sha256"]:
            raise RuntimeError("Boot snapshot changed during restore")
    except BaseException:
        for target in created_files:
            target.unlink(missing_ok=True)
        if created_directory:
            robotron.rmdir()
        raise
    return dict(manifest, restored_paths={relative: str(path) for relative, path in targets.items()})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "validate"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--nvram-source", type=Path, default=Path("/home/dave/.mame/nvram/robotron/nvram"))
    parser.add_argument("--cfg-source", type=Path, default=Path("/home/dave/.mame/cfg/robotron.cfg"))
    parser.add_argument("--ini-source", type=Path, default=Path("/etc/mame/mame.ini"))
    args = parser.parse_args(argv)
    result = (capture_snapshot(args.directory, nvram_source=args.nvram_source,
                              cfg_source=args.cfg_source, ini_source=args.ini_source)
              if args.command == "capture" else load_snapshot(args.directory))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
