"""Archive stopped training data, hashing each source as tar reads it.

This preserves bytes; it does not qualify a policy or prove checkpoint/replay
scientific consistency. The operator must first stop every writer.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time


class HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        data = self.stream.read(size)
        self.digest.update(data)
        return data


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for unit in ("robotron-trainer.service", "robotron-mame.service"):
        pid = subprocess.check_output(
            ["systemctl", "--user", "show", unit, "-p", "MainPID", "--value"], text=True
        ).strip()
        if pid != "0":
            raise RuntimeError(f"Stop {unit} before backing up")
    args.output.mkdir(parents=True, exist_ok=False)
    game = args.game_root.resolve(strict=True)
    model = game / "models_dqn"
    files = []
    for path in sorted(args.replay.resolve(strict=True).iterdir()):
        if path.is_file():
            files.append((path, "models_dqn/robotron_dqn_latest_replay/" + path.name))
    for name in ("robotron_dqn_latest.pt", "game_settings.json", "learning_control.json"):
        path = model / name
        if path.exists():
            files.append((path, "models_dqn/" + name))
    for bank in ("hof", "ephof"):
        directory = model / ("robotron_dqn_latest_replay_" + bank)
        pointer = directory / "CURRENT.json"
        selected = json.loads(pointer.read_text())
        generation = selected["generation"]
        if not generation.startswith("gen-") or "/" in generation:
            raise ValueError("Invalid selected generation")
        files.append((pointer, str(pointer.relative_to(game))))
        for path in sorted((directory / "generations" / generation).iterdir()):
            files.append((path, str(path.relative_to(game))))
    for path in sorted((model / "managed-incumbents").glob("*.pt")):
        files.append((path, str(path.relative_to(game))))
    state = game / "logs/managed-learning-20261015/state.json"
    if state.exists():
        files.append((state, "migration-context/managed-learning-state.json"))
    started = time.time()
    records = []
    archive = args.output / "training-state.tar.zst"
    partial = archive.with_suffix(archive.suffix + ".partial")
    process = subprocess.Popen(["zstd", "-T8", "-3", "-o", str(partial)], stdin=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdin, mode="w|") as tar:
            for source, destination in files:
                if source.is_symlink() or not source.is_file():
                    raise ValueError(f"Expected ordinary file: {source}")
                before = source.stat()
                info = tar.gettarinfo(str(source), arcname=destination)
                with source.open("rb") as stream:
                    reader = HashingReader(stream)
                    tar.addfile(info, reader)
                after = source.stat()
                if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
                ):
                    raise RuntimeError(f"Source changed: {source}")
                records.append(dict(path=destination, bytes=before.st_size,
                                    sha256=reader.digest.hexdigest(), source=str(source)))
                print(json.dumps(records[-1]), flush=True)
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("Compression failed")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
    with partial.open("rb") as stream:
        os.fsync(stream.fileno())
    subprocess.run(["zstd", "-t", str(partial)], check=True)
    os.rename(partial, archive)
    manifest = dict(status="STOPPED_FILES_HASHED_ARCHIVED_AND_ZSTD_VERIFIED",
                    archive=archive.name, archive_sha256=sha256(archive),
                    archive_bytes=archive.stat().st_size, files=records,
                    started_unix_s=started, completed_unix_s=time.time(),
                    scientific_consistency_verified=False)
    with (args.output / "manifest.json").open("x") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    directory_fd = os.open(args.output, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}), flush=True)


if __name__ == "__main__":
    main()
