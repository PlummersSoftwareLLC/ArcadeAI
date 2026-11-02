"""Exercise the complete observer loop with explicitly synthetic health inputs.

Only ownership and main-health collection are fixtures. The actual sampler,
durability queue, readiness gate, projection timing, close request and outcome
writer execute unchanged. These fixtures cannot authorize scientific work.
"""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

from . import durable_raw_writer as durable
from . import round_observer_v6 as worker


class SyntheticObserverRunTests(unittest.TestCase):
    def run_fixture(self, directory, *, fail_certificate):
        status = directory/'status.json'
        status.write_text('{}')
        case_pin = worker.write(directory/'case.json', dict(round_root=str(directory)))
        native_pin = worker.write(directory/'native.json', dict(engineering_only=True))
        owner = dict(pid=os.getpid(), birth=worker.birth(os.getpid()), unit='engineering-fixture-only',
            uid=os.getuid(), invocation_id='b'*32, cgroup='/synthetic-fixture-not-a-real-owner')
        sequence = [0]

        def collect(case):
            sequence[0] += 1
            api = dict(training_steps=sequence[0])
            raw = json.dumps(api)
            return dict(api=api, raw_API_wire=raw,
                api_wire_sha256=worker.hashlib.sha256(raw.encode()).hexdigest(), status={})

        health = types.SimpleNamespace(collect=collect, validate=lambda *a, **k: None,
            check_inputs=lambda *a, **k: None,
            base=lambda: types.SimpleNamespace(stable_round_status=lambda value: value))
        counts = [0]

        def fsync(fd):
            path = os.readlink('/proc/self/fd/%d' % fd)
            if path.endswith('durable-readiness.json') and fail_certificate:
                raise OSError('injected initial-certificate fsync failure')
            if '/sample-' in path and not os.path.isdir(path):
                counts[0] += 1
                if counts[0] == 100 and not fail_certificate:
                    time.sleep(.8)
            os.fsync(fd)

        class Writer(durable.DurableRawWriter):
            def __init__(self, *a, **k):
                super().__init__(*a, fsync=fsync, **k)

        wrapper = types.SimpleNamespace(DurableRawWriter=Writer)
        output = directory/'raw'
        job = dict(schema=worker.SCHEMA, attempt=1, no_retry=True, interval_s=.2,
            initial_samples=100, maximum_gap_s=.5, work_s=4200, runtime_s=4260,
            nonce='a'*32, parent={}, unit=owner['unit'], native_job=native_pin,
            native_runtime=worker.pin(Path(worker.__file__).resolve()), case=case_pin,
            output=str(output), deadline_monotonic_s=time.monotonic()+60,
            sources=dict(worker=worker.pin(Path(worker.__file__).resolve()),
                health=case_pin, durability=worker.pin(Path(durable.__file__).resolve())))
        job_pin = worker.write(directory/'job.json', job)
        stopped = threading.Event()
        seen = []
        errors = []

        def close_when_ready():
            try:
                while not stopped.wait(.02):
                    path = output/'live.json'
                    if not path.exists():
                        continue
                    live = worker.read(path)
                    if not seen or live['observed_samples'] != seen[-1]['observed_samples']:
                        seen.append(live)
                    if live['initial'] is not None and live['observed_samples'] >= 110:
                        worker.write(output/'finish-request.json', dict(job=job_pin, nonce=job['nonce'],
                            parent={}, action='close', created_monotonic_s=time.monotonic()))
                        return
            except BaseException as failure:
                errors.append(repr(failure))

        closer = threading.Thread(target=close_when_ready)
        closer.start()
        try:
            with patch.object(worker, 'owner', return_value=owner), \
                    patch.object(worker, 'check_parent'), \
                    patch.object(worker, 'load', side_effect=lambda name, value:
                        wrapper if name == '_original_bounded_raw_durability' else health):
                code = worker.run(job, job_pin)
        finally:
            stopped.set()
            closer.join(2)
        self.assertFalse(closer.is_alive())
        self.assertEqual(errors, [])
        return code, worker.read(output/'outcome.json'), seen

    def test_full_loop_keeps500ms_and_durable_readiness_after800ms_stall(self):
        with tempfile.TemporaryDirectory() as directory:
            code, outcome, seen = self.run_fixture(Path(directory), fail_certificate=False)
            self.assertEqual(code, 0)
            self.assertTrue(outcome['success'])
            self.assertIsNone(outcome['error'])
            ready = next(value for value in seen if value['initial'] is not None)
            self.assertGreaterEqual(ready['observed_samples'], 103)
            self.assertEqual(outcome['initial']['index'], 99)
            rows = [worker.read(worker.checked(pin))['snapshot'] for pin in outcome['samples']]
            self.assertLessEqual(max(b['monotonic_s']-a['monotonic_s'] for a,b in zip(rows, rows[1:])), .5)
            pubs = outcome['publications']
            self.assertLessEqual(max(b['updated_monotonic_s']-a['updated_monotonic_s'] for a,b in zip(pubs,pubs[1:])), .5)
            self.assertTrue(outcome['all_writer_threads_stopped'])
            seal = worker.read(worker.checked(outcome['durability_seal']))
            self.assertEqual(seal['sample_count'], len(rows))
            self.assertGreaterEqual(seal['maximum_file_fsync_s'], .8)
            request = worker.read(worker.checked(outcome['finish_request']))
            self.assertGreaterEqual(rows[-1]['monotonic_s'], request['created_monotonic_s'])

    def test_failed_certificate_never_grants_readiness_or_success(self):
        with tempfile.TemporaryDirectory() as directory:
            code, outcome, seen = self.run_fixture(Path(directory), fail_certificate=True)
            self.assertEqual(code, 1)
            self.assertFalse(outcome['success'])
            self.assertIn('initial-certificate fsync failure', outcome['error'])
            self.assertIsNone(outcome['initial'])
            self.assertTrue(all(value['initial'] is None for value in seen))
            self.assertTrue(outcome['all_writer_threads_stopped'])
            self.assertIsNone(outcome['durability_seal'])


if __name__ == '__main__':
    unittest.main()
