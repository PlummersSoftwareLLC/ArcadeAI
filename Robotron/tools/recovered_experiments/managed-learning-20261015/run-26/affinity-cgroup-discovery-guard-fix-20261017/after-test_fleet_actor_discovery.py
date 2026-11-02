"""Temporary proc/cgroup fixtures only; no live processes or numerical imports."""
import copy
import errno
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from . import inference_worker_affinity as metrics


class FleetActorDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proc, self.groups = self.root / 'proc', self.root / 'cgroup'
        self.cgroup = '/user.slice/fixture-fleet.service'
        self.members = self.groups / self.cgroup.lstrip('/') / 'cgroup.procs'
        self.members.parent.mkdir(parents=True)
        self.records = {}
        self.log = self.root / 'actor.log';self.log.touch()
        for pid in range(1, 193):
            self.add_actor(pid, pid - 1)
        self.members.write_text(' '.join(str(pid) for pid in self.records))
        self.expected = copy.deepcopy(list(self.records.values()))

    def add_actor(self, pid, slot):
        process = self.proc / str(pid);process.mkdir(parents=True, exist_ok=True)
        process.joinpath('cmdline').write_bytes(b'/usr/games/mame\0robotron\0')
        process.joinpath('cgroup').write_text('0::' + self.cgroup + '\n')
        process.joinpath('fd').mkdir(exist_ok=True)
        for name in ('1', '2'):
            process.joinpath('fd', name).symlink_to(self.log)
        self.records[pid] = dict(pid=pid, starttime_ticks=10000 + pid, client_slot=slot)

    def discover(self, fault=None, identity_fault=None):
        original_read = Path.read_bytes
        def mapped_path(value):
            if value == '/proc':return self.proc
            if value == '/sys/fs/cgroup':return self.groups
            return Path(value)
        def read(path):
            if fault and path == fault[0]:raise fault[1]
            return original_read(path)
        def identify(pid, kind):
            if identity_fault and pid == identity_fault[0]:raise identity_fault[1]
            return copy.deepcopy(self.records[pid])
        with patch.object(metrics, 'Path', side_effect=mapped_path), \
                patch.object(Path, 'read_bytes', read), \
                patch.object(metrics.identity, 'identify_process', side_effect=identify):
            return metrics.discover_fleet_actors(self.cgroup)

    def test_exact_fleet_and_existing_nonactor_succeed(self):
        extra = self.proc / '900';extra.mkdir();extra.joinpath('cmdline').write_bytes(b'sleep\0' + b'30\0')
        self.members.write_text(self.members.read_text() + ' 900')
        actors, logs = self.discover()
        self.assertEqual(actors, self.expected)
        self.assertEqual(logs, {str(self.log)})

    def test_unknown_vanished_candidate_skipped_only_for_enoent_or_esrch(self):
        self.members.write_text(self.members.read_text() + ' 900')
        path = self.proc / '900/cmdline'
        for error in (FileNotFoundError(errno.ENOENT, 'gone', str(path)),
                      ProcessLookupError(errno.ESRCH, 'gone', str(path))):
            with self.subTest(errno=error.errno):
                self.assertEqual(self.discover(fault=(path, error))[0], self.expected)

    def test_missing_expected_actor_before_classification_still_fails_exact_slots(self):
        path = self.proc / '1/cmdline'
        for number in (errno.ENOENT, errno.ESRCH):
            with self.subTest(errno=number), self.assertRaisesRegex(metrics.GuardFailure, 'exact main actor slots'):
                self.discover(fault=(path, OSError(number, 'expected actor vanished')))

    def test_classified_actor_disappearance_is_fatal_with_pid_and_operation(self):
        for number in (errno.ENOENT, errno.ESRCH):
            with self.subTest(errno=number), self.assertRaisesRegex(metrics.GuardFailure, 'Classified MAME PID 1 identity'):
                self.discover(identity_fault=(1, OSError(number, 'classified actor vanished')))
        self.proc.joinpath('1/fd/1').unlink()
        with self.assertRaisesRegex(metrics.GuardFailure, 'Classified MAME PID 1 stdout/stderr fd 1'):
            self.discover()

    def test_permission_other_io_and_errno_less_discovery_errors_fail_closed(self):
        self.members.write_text(self.members.read_text() + ' 900')
        path = self.proc / '900/cmdline'
        for error in (PermissionError(errno.EACCES, 'permission denied'), OSError(errno.EIO, 'I/O failed'),
                      FileNotFoundError('no reliable errno')):
            with self.subTest(error=repr(error)), self.assertRaisesRegex(metrics.GuardFailure, 'candidate PID 900 cmdline discovery'):
                self.discover(fault=(path, error))

    def test_classified_actor_cgroup_and_other_io_fail_closed(self):
        self.proc.joinpath('1/cgroup').write_text('0::/another/group\n')
        with self.assertRaisesRegex(metrics.GuardFailure, 'Classified MAME PID 1 cgroup'):
            self.discover()
        self.proc.joinpath('1/cgroup').write_text('0::' + self.cgroup + '\n')
        with self.assertRaisesRegex(metrics.GuardFailure, 'Classified MAME PID 1 identity'):
            self.discover(identity_fault=(1, PermissionError(errno.EACCES, 'identity unreadable')))

    def test_extra_or_duplicate_mame_slot_is_fatal(self):
        for slot in (192, 0):
            with self.subTest(slot=slot):
                self.add_actor(901 + slot, slot)
                self.members.write_text(' '.join(str(pid) for pid in range(1, 193)) + ' ' + str(901 + slot))
                with self.assertRaisesRegex(metrics.GuardFailure, 'exact main actor slots'):
                    self.discover()
        self.members.write_text(' '.join(str(pid) for pid in range(1, 193)))
        self.records[2]['client_slot'] = 0
        with self.assertRaisesRegex(metrics.GuardFailure, 'exact main actor slots'):
            self.discover()

    def test_replacement_pid_or_start_ticks_still_fail_complete_binding_comparison(self):
        original = dict(actors=self.expected)
        for replacement in ('pid', 'start_ticks'):
            with self.subTest(replacement=replacement):
                self.records = {actor['pid']: copy.deepcopy(actor) for actor in self.expected}
                if replacement == 'pid':
                    self.add_actor(900, 0)
                    self.members.write_text('900 ' + ' '.join(str(pid) for pid in range(2, 193)))
                else:
                    self.records[1]['starttime_ticks'] += 1
                    self.members.write_text(' '.join(str(pid) for pid in range(1, 193)))
                actors, _ = self.discover()
                self.assertEqual([a['client_slot'] for a in actors], list(range(192)))
                host = types.SimpleNamespace(bindings=lambda: dict(actors=actors),
                                             mask=lambda _: list(range(72)))
                with self.assertRaisesRegex(metrics.GuardFailure, 'Ownership/source/environment/control binding changed'):
                    metrics.Host.verify(host, dict(bindings=original), list(range(72)))


if __name__ == '__main__':
    unittest.main()
