"""Standard-library-only boot snapshot integrity and copy-ownership tests."""

import contextlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from . import sidecar_boot as boot


class BootSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="robotron-boot-test-")
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.nvram = self.sources / "nvram"
        self.cfg = self.sources / "robotron.cfg"
        self.ini = self.sources / "mame.ini"
        self.nvram.write_bytes(bytes(range(256)) * 4)
        self.cfg.write_text("\ufeff<?xml version='1.0'?><mameconfig version='10'><system name='robotron'/></mameconfig>")
        self.ini.write_text("rompath /fixture/roms\nvideo none\n")
        self.snapshot = self.root / "snapshot"

    def tearDown(self):
        # Snapshot directories deliberately forbid normal file mutations.
        for current, directories, _ in os.walk(self.root):
            Path(current).chmod(0o700)
            for directory in directories:
                path = Path(current) / directory
                if not path.is_symlink():
                    path.chmod(0o700)
        self.temporary.cleanup()

    def capture(self, path=None, *, real_scan=False):
        def capture():
            return boot.capture_snapshot(path or self.snapshot, nvram_source=self.nvram,
                                         cfg_source=self.cfg, ini_source=self.ini)
        if real_scan:
            return capture()
        with patch.object(boot, "_scan_writable_sources", return_value=dict(
                checked_processes=0, active_writers=0, policy="Integrity fixture: FD scan tested separately")):
            return capture()

    def actor(self, name="actor"):
        actor = self.root / name
        for directory in ("cfg", "nvram", "ini"):
            (actor / directory).mkdir(parents=True)
        return actor

    def change_manifest(self, update):
        path = self.snapshot / boot.MANIFEST_NAME
        manifest = json.loads(path.read_text())
        update(manifest)
        manifest["identity"] = boot._identity(manifest)
        path.chmod(0o600)
        path.write_text(json.dumps(manifest))
        path.chmod(0o444)

    def test_capture_exact_immutable_independent_files_and_manifest(self):
        result = self.capture()
        self.assertEqual(result["schema"], boot.SCHEMA)
        self.assertEqual(set(result["files"]), set(boot.REQUIRED_PATHS))
        self.assertEqual(result["files"][boot.REQUIRED_PATHS[0]]["bytes"], 1024)
        self.assertEqual(result, boot.load_snapshot(self.snapshot))
        self.assertEqual(len(result["identity"]), 64)
        sources = [self.nvram, self.cfg, self.ini]
        for relative, source in zip(boot.REQUIRED_PATHS, sources):
            target = self.snapshot / relative
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertNotEqual(target.stat().st_ino, source.stat().st_ino)
            self.assertEqual(target.stat().st_nlink, 1)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE((self.snapshot / "manifest.json").stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE(self.snapshot.stat().st_mode), 0o555)
        self.assertEqual(result["writer_checks"]["before"]["active_writers"], 0)
        self.assertEqual(result["writer_checks"]["after"]["active_writers"], 0)

    def test_restore_writable_independent_copies_do_not_mutate_seed_or_other_actor(self):
        manifest = self.capture()
        first, second = self.actor(), self.actor("actor2")
        restored = boot.restore_snapshot(self.snapshot, first)
        boot.restore_snapshot(self.snapshot, second)
        self.assertEqual(restored["identity"], manifest["identity"])
        for relative in boot.REQUIRED_PATHS:
            target, peer, seed = first / relative, second / relative, self.snapshot / relative
            self.assertEqual(target.read_bytes(), seed.read_bytes())
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertEqual(len({target.stat().st_ino, peer.stat().st_ino, seed.stat().st_ino}), 3)
        (first / boot.REQUIRED_PATHS[0]).write_bytes(b"x" * 1024)
        self.assertEqual((second / boot.REQUIRED_PATHS[0]).read_bytes(), self.nvram.read_bytes())
        self.assertEqual(boot.load_snapshot(self.snapshot)["identity"], manifest["identity"])

    def test_sources_can_change_after_capture_without_changing_seed(self):
        manifest = self.capture()
        self.ini.write_text("changed later\n")
        self.assertEqual(boot.load_snapshot(self.snapshot)["identity"], manifest["identity"])

    def test_capture_refuses_existing_destination_and_source_symlinks(self):
        self.snapshot.mkdir()
        marker = self.snapshot / "keep"
        marker.write_text("keep")
        with self.assertRaises(FileExistsError):
            self.capture()
        self.assertEqual(marker.read_text(), "keep")
        linked = self.sources / "linked"
        linked.symlink_to(self.nvram)
        with self.assertRaises(ValueError):
            boot.capture_snapshot(self.root / "bad", nvram_source=linked, cfg_source=self.cfg, ini_source=self.ini)

    def test_bad_nvram_and_non_robotron_or_malformed_cfg_are_rejected(self):
        self.nvram.write_bytes(b"short")
        with self.assertRaises(ValueError):
            self.capture()
        self.nvram.write_bytes(b"a" * 1024)
        for xml in ("<bad", "<mameconfig version='10'><system name='pacman'/></mameconfig>",
                    "<mameconfig version='9'><system name='robotron'/></mameconfig>",
                    "<mameconfig version='10'><system name='robotron'/><system name='robotron'/></mameconfig>"):
            self.cfg.write_text(xml)
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                self.capture()
            self.assertFalse(self.snapshot.exists())

    def test_live_writable_source_fd_rejected_but_readonly_fd_allowed(self):
        with self.nvram.open("rb"):
            self.capture(real_scan=True)
        with self.nvram.open("r+b"):
            with self.assertRaisesRegex(RuntimeError, "active writable FD"):
                self.capture(self.root / "writable-rejected", real_scan=True)
        self.assertFalse((self.root / "writable-rejected").exists())

    def test_full_copy_bracket_detects_source_change_and_cleans_partial_snapshot(self):
        copy = boot.shutil.copyfileobj
        modified = False

        def copy_and_mutate(reader, writer, **kwargs):
            nonlocal modified
            copy(reader, writer, **kwargs)
            if not modified:
                modified = True
                self.ini.write_text("different during full copy\n")

        with patch.object(boot.shutil, "copyfileobj", side_effect=copy_and_mutate):
            with self.assertRaisesRegex(RuntimeError, "changed during"):
                self.capture()
        self.assertFalse(self.snapshot.exists())

    def test_writer_check_runs_before_and_after_complete_copy(self):
        clean = dict(checked_processes=1, active_writers=0, uninspectable_other_user_pids=[])
        with patch.object(boot, "_scan_writable_sources", side_effect=[clean, RuntimeError("writer appeared")]) as check:
            with self.assertRaisesRegex(RuntimeError, "writer appeared"):
                self.capture(real_scan=True)
        self.assertEqual(check.call_count, 2)
        self.assertFalse(self.snapshot.exists())

    def test_unreadable_mame_fails_but_unrelated_desktop_is_recorded(self):
        proc = self.root / "proc"
        process = proc / "12345"
        (process / "fd").mkdir(parents=True)
        (process / "comm").write_text("mame\n")
        (process / "cmdline").write_bytes(b"/usr/games/mame\0robotron\0")
        original = Path.iterdir

        def guarded(path):
            if path == process / "fd":
                raise PermissionError("fixture inaccessible FD table")
            return original(path)

        sources = {"nvram/robotron/nvram": boot._source_state(self.nvram)}
        with patch.object(boot, "_PROC_ROOT", proc), patch.object(Path, "iterdir", guarded):
            with self.assertRaisesRegex(RuntimeError, "relevant process"):
                boot._scan_writable_sources(sources)
            (process / "comm").write_text("python3\n")
            (process / "cmdline").write_bytes(b"python3\0fixture_worker.py\0")
            with self.assertRaisesRegex(RuntimeError, "relevant process"):
                boot._scan_writable_sources(sources)
            (process / "comm").write_text("(sd-pam)\n")
            (process / "cmdline").write_bytes(b"/usr/lib/systemd/systemd\0")
            result = boot._scan_writable_sources(sources)
        self.assertEqual(result["uninspectable_unrelated_processes"],
                         [dict(pid=12345, command="(sd-pam)", same_user=True)])

    def test_hardlinked_seed_is_rejected(self):
        self.capture()
        linked = self.root / "external-hardlink"
        os.link(self.snapshot / "nvram/robotron/nvram", linked)
        with self.assertRaisesRegex(ValueError, "independent immutable"):
            boot.load_snapshot(self.snapshot)
        linked.unlink()
        boot.load_snapshot(self.snapshot)

    def test_manifest_identity_tampering_hash_size_and_exact_paths_rejected(self):
        self.capture()
        path = self.snapshot / "manifest.json"
        content = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(content.replace(b'"created_utc": "', b'"created_utc": "changed'))
        path.chmod(0o444)
        with self.assertRaises(ValueError):
            boot.load_snapshot(self.snapshot)
        path.chmod(0o600)
        path.write_bytes(content)
        path.chmod(0o444)
        self.change_manifest(lambda d: d["files"]["cfg/robotron.cfg"].update(bytes=1))
        with self.assertRaises(ValueError):
            boot.load_snapshot(self.snapshot)
        self.change_manifest(lambda d: d["files"].update({"../escape": dict(bytes=1, sha256="0" * 64)}))
        with self.assertRaises(ValueError):
            boot.load_snapshot(self.snapshot)

    def test_changed_asset_writable_asset_extra_file_and_symlink_are_rejected(self):
        self.capture()
        target = self.snapshot / "ini/mame.ini"
        target.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "immutable"):
            boot.load_snapshot(self.snapshot)
        target.write_text("changed")
        target.chmod(0o444)
        with self.assertRaisesRegex(ValueError, "changed"):
            boot.load_snapshot(self.snapshot)
        self.snapshot.chmod(0o700)
        (self.snapshot / "extra").write_text("extra")
        self.snapshot.chmod(0o555)
        with self.assertRaisesRegex(ValueError, "exactly"):
            boot.load_snapshot(self.snapshot)
        self.snapshot.chmod(0o700)
        (self.snapshot / "extra").unlink()
        self.snapshot.chmod(0o555)
        target.parent.chmod(0o700)
        target.unlink()
        target.symlink_to(self.ini)
        target.parent.chmod(0o555)
        with self.assertRaisesRegex(ValueError, "symlink"):
            boot.load_snapshot(self.snapshot)

    def test_restore_preflights_every_destination_and_does_not_overwrite(self):
        self.capture()
        actor = self.actor()
        existing = actor / "ini/mame.ini"
        existing.write_text("existing")
        with self.assertRaises(FileExistsError):
            boot.restore_snapshot(self.snapshot, actor)
        self.assertEqual(existing.read_text(), "existing")
        self.assertFalse((actor / "nvram/robotron").exists())
        self.assertFalse((actor / "cfg/robotron.cfg").exists())

    def test_restore_rejects_symlinked_directories_and_cleans_failed_copy(self):
        self.capture()
        actor = self.actor()
        (actor / "cfg").rmdir()
        (actor / "cfg").symlink_to(self.sources, target_is_directory=True)
        with self.assertRaises(ValueError):
            boot.restore_snapshot(self.snapshot, actor)
        (actor / "cfg").unlink()
        (actor / "cfg").mkdir()
        with patch.object(boot.shutil, "copyfileobj", side_effect=OSError("copy failure")):
            with self.assertRaisesRegex(OSError, "copy failure"):
                boot.restore_snapshot(self.snapshot, actor)
        self.assertFalse((actor / "nvram/robotron").exists())
        self.assertFalse((actor / "cfg/robotron.cfg").exists())

    def test_capture_cli_uses_only_standard_library_and_prints_valid_manifest(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(boot, "_scan_writable_sources", return_value=dict(
                checked_processes=0, active_writers=0, policy="CLI fixture")):
            boot.main(["capture", str(self.snapshot), "--nvram-source", str(self.nvram),
                       "--cfg-source", str(self.cfg), "--ini-source", str(self.ini)])
        self.assertEqual(json.loads(output.getvalue())["identity"], boot.load_snapshot(self.snapshot)["identity"])

    def test_writable_snapshot_directories_are_rejected(self):
        self.capture()
        for directory in (self.snapshot, self.snapshot/'cfg'):
            directory.chmod(0o755)
            with self.assertRaisesRegex(ValueError, 'directories must be immutable'):
                boot.load_snapshot(self.snapshot)
            directory.chmod(0o555)


if __name__ == "__main__":
    unittest.main()
