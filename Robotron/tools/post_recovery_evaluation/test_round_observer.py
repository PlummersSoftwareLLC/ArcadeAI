import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from . import round_observer as protocol
from .round_observer_client import DedicatedMainHealth
from .round_observer_client_v2 import DedicatedMainHealth as DedicatedMainHealthV2
from .round_observer_client_v3 import DedicatedMainHealth as DedicatedMainHealthV3


def live_fixture(guard_class=DedicatedMainHealth):
    guard = guard_class.__new__(guard_class)
    guard.common = protocol
    guard.jobpin = {'path': '/synthetic/job', 'sha256': 'a'*64}
    guard.job = dict(nonce='1'*32)
    guard.worker_owner = dict(pid=os.getpid(), birth=protocol.birth(os.getpid()))
    guard.last_live = None
    value = dict(schema='robotron-round-observer-live-v1', job=guard.jobpin,
        nonce=guard.job['nonce'], owner=guard.worker_owner, state='running',
        updated_monotonic_s=time.monotonic(), observed_samples=5,
        initial=dict(index=4, unix_s=time.time(), unaccepted_samples=0),
        phase=dict(overlap_pending=False), latest_sample={})
    return guard, value


class RoundObserverTests(unittest.TestCase):
    guard_class = DedicatedMainHealth

    def test_live_identity_freshness_and_monotonic_publication(self):
        guard, value = live_fixture(self.guard_class)
        self.assertFalse(guard._accept(value)['phase']['overlap_pending'])
        for mutation in ('nonce', 'job', 'owner', 'stale', 'regression', 'state'):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(value)
                if mutation == 'nonce':
                    bad['nonce'] = '2'*32
                elif mutation == 'job':
                    bad['job']['sha256'] = 'b'*64
                elif mutation == 'owner':
                    bad['owner']['birth'] += 1
                elif mutation == 'stale':
                    bad['updated_monotonic_s'] -= 31
                elif mutation == 'regression':
                    bad['observed_samples'] = 4
                else:
                    bad['state'] = 'closed'
                with self.assertRaises(ValueError):
                    guard._accept(bad)

    def test_parent_command_scope_and_birth_are_bound(self):
        parent = dict(pid=os.getpid(), birth=protocol.birth(os.getpid()), uid=os.getuid(),
            cgroup=next(line[3:] for line in Path('/proc/self/cgroup').read_text().splitlines()
                        if line.startswith('0::')),
            argv=[part.decode() for part in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]])
        protocol.check_parent(parent)
        for key, value in [('birth', parent['birth']+1), ('cgroup', '/different'), ('argv', ['different'])]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                protocol.check_parent(dict(parent, **{key:value}))

    def test_pinned_bytes_identity_and_canonical_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'record.json'
            path.write_text('{"value":1}')
            pinned = protocol.pin(path)
            self.assertEqual(protocol.checked(pinned), path)
            path.chmod(0o400)
            with self.assertRaises(ValueError):
                protocol.checked(pinned)
            path.chmod(0o600)
            path.write_text('{"value":2}')
            with self.assertRaises(ValueError):
                protocol.checked(pinned)
            link = Path(directory) / 'alias.json'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                protocol.pin(link)
            with self.assertRaises(OSError):
                protocol.read(link)

    def test_publication_limits_and_immutable_record_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'record.json'
            value = protocol.write(path, dict(value='x'*100))
            self.assertEqual(value['identity']['mode'], '0o444')
            with self.assertRaises(FileExistsError):
                protocol.write(path, dict(value='replacement'))
            with self.assertRaises(ValueError):
                protocol.read(path, limit=20)
            live = Path(directory) / 'live.json'
            protocol.write(live, dict(index=1), live=True)
            protocol.write(live, dict(index=2), live=True)
            self.assertEqual(protocol.read(live), dict(index=2))

    def test_closed_or_already_launched_observer_cannot_be_reused(self):
        guard, _ = live_fixture(self.guard_class)
        guard.finished = True
        guard.child = object()
        with self.assertRaises(ValueError):
            guard.start()
        with self.assertRaises(ValueError):
            guard.observe()
        with self.assertRaises(ValueError):
            guard.finish(case_already_failed=False)


class RoundObserverV2Tests(RoundObserverTests):
    guard_class = DedicatedMainHealthV2


class RoundObserverV3Tests(RoundObserverTests):
    guard_class = DedicatedMainHealthV3

    def test_hot_projection_rejects600ms_age(self):
        guard, value = live_fixture(self.guard_class)
        value['updated_monotonic_s'] -= .6
        with self.assertRaises(ValueError):
            guard._accept(value)


if __name__ == '__main__':
    unittest.main()
