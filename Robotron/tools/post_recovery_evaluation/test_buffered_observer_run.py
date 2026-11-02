"""Actual new observer/client loop with synthetic health and real RAM control.

Ownership and main census values are engineering fixtures. The strict worker,
byte queue, tmpfs publisher, native client consumer and durable close execute.
These fixtures cannot qualify scientific runtime or policy quality.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import buffered_raw_writer_v2 as buffered
from . import volatile_live_control_v1 as control_module
from . import round_observer_v7 as worker
from .round_observer_client_v8 import DedicatedMainHealth


class BufferedObserverRunTests(unittest.TestCase):
    def fixture(self, directory, *, fail_certificate=False):
        (directory/'status.json').write_text('{}')
        case = worker.write(directory/'case.json', dict(round_root=str(directory)))
        native = worker.write(directory/'native.json', dict(engineering_only=True))
        actual_owner = dict(pid=os.getpid(), birth=worker.birth(os.getpid()), uid=os.getuid(),
            unit='ENGINEERING-ONLY', invocation_id='b'*32, cgroup='/ENGINEERING-ONLY')
        counter = [0]

        def collect(case):
            counter[0] += 1
            api = dict(training_steps=counter[0])
            raw = json.dumps(api)
            return dict(api=api, raw_API_wire=raw,
                api_wire_sha256=hashlib.sha256(raw.encode()).hexdigest(), status={})

        health = SimpleNamespace(collect=collect, validate=lambda *a,**k: None,
            check_inputs=lambda *a,**k: None,
            base=lambda: SimpleNamespace(stable_round_status=lambda value:value))
        injected = []
        producer = threading.get_ident()

        def delayed_open(name, *args, **kwargs):
            if name == 'sample-000099.json' and not fail_certificate:
                injected.append(('create', threading.get_ident()))
                time.sleep(.8)
            return os.open(name, *args, **kwargs)

        def delayed_sync(fd):
            name = Path(os.readlink('/proc/self/fd/%d' % fd)).name
            if name == 'durable-readiness.json' and fail_certificate:
                raise OSError('injected buffered certificate durability failure')
            if name == 'sample-000104.json' and not fail_certificate:
                injected.append(('fsync', threading.get_ident()))
                time.sleep(.8)
            os.fsync(fd)

        class Writer(buffered.BufferedRawWriter):
            def __init__(self,*a,**k):
                super().__init__(*a,fsync=delayed_sync,open_file=delayed_open,**k)

        nonce = secrets.token_hex(16)
        output = directory/'raw'
        job = dict(schema=worker.SCHEMA, attempt=1, no_retry=True, interval_s=.2,
            initial_samples=100, maximum_gap_s=.5, work_s=4200, runtime_s=4260,
            nonce=nonce, parent={}, unit=actual_owner['unit'], native_job=native,
            native_runtime=worker.pin(Path(worker.__file__).resolve()), case=case,
            output=str(output), deadline_monotonic_s=time.monotonic()+60,
            raw_queue_protocol='pending-byte-digest-v2', live_control_path=str(control_module.path_for(nonce)),
            sources=dict(worker=worker.pin(Path(worker.__file__).resolve()), health=case,
                durability=worker.pin(Path(buffered.__file__).resolve()),
                control=worker.pin(Path(control_module.__file__).resolve())))
        job_pin = worker.write(directory/'job.json',job)
        guard = DedicatedMainHealth.__new__(DedicatedMainHealth)
        guard.common = worker
        guard.control_module = control_module
        guard.control_path = Path(job['live_control_path'])
        guard.live_path = guard.control_path/'live.json'
        guard.output = output
        guard.jobpin, guard.job, guard.worker_owner = job_pin, job, actual_owner
        guard.last_live = guard.initial = None
        stop = threading.Event()
        seen, consumer_errors = [], []

        def close_after_native_readiness():
            while not stop.wait(.02):
                try:
                    if not guard.live_path.exists():
                        continue
                    value = worker.read(guard.live_path)
                    record = guard._accept(value)
                    if not seen or record['observed_samples'] != seen[-1]['observed_samples']:
                        seen.append(record)
                    if record['initial'] is not None and record['observed_samples'] >= 112:
                        worker.write(output/'finish-request.json', dict(job=job_pin,nonce=nonce,
                            parent={},action='close',created_monotonic_s=time.monotonic()))
                        return
                except FileNotFoundError:
                    if fail_certificate:
                        return
                    raise
                except BaseException as failure:
                    consumer_errors.append(repr(failure))
                    return

        actual_replace = os.replace
        persistent_live_renames = []

        def slow_persistent_rename(source,destination,*a,**k):
            if Path(destination).name == 'live.json' and 'dst_dir_fd' not in k:
                persistent_live_renames.append(True)
                time.sleep(.8)
            return actual_replace(source,destination,*a,**k)

        thread = threading.Thread(target=close_after_native_readiness)
        thread.start()
        try:
            with patch.object(worker,'owner',return_value=actual_owner), \
                    patch.object(worker,'check_parent'), \
                    patch.object(worker,'load',side_effect=lambda name,pin:
                        SimpleNamespace(BufferedRawWriter=Writer) if name=='_original_bounded_raw_durability'
                        else control_module if name=='_original_tmpfs_live_control' else health), \
                    patch.object(os,'replace',side_effect=slow_persistent_rename):
                code = worker.run(job,job_pin)
        finally:
            stop.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertFalse(guard.control_path.exists())
        self.assertEqual(persistent_live_renames,[])
        return code, worker.read(output/'outcome.json'), seen, consumer_errors, injected, producer

    def test_actual_loop_survives800ms_create_and_fsync_and_avoids_persistent_live_rename(self):
        with tempfile.TemporaryDirectory() as directory:
            code,outcome,seen,errors,injected,producer = self.fixture(Path(directory))
            self.assertEqual(code,0)
            self.assertTrue(outcome['success'])
            self.assertIsNone(outcome['error'])
            self.assertEqual(errors,[])
            self.assertEqual([name for name,ident in injected],['create','fsync'])
            self.assertTrue(all(ident!=producer for name,ident in injected))
            self.assertTrue(all(row['index']==row['observed_samples']-1 for row in seen))
            first = next(row for row in seen if row['initial'] is not None)
            self.assertGreaterEqual(first['observed_samples'],103)
            self.assertEqual(first['initial']['index'],99)
            self.assertTrue(outcome['all_writer_threads_stopped'])
            self.assertEqual(outcome['uncommitted_raw'],[])
            samples = [worker.read(worker.checked(pin)) for pin in outcome['samples']]
            self.assertEqual(len(samples),outcome['queued_samples'])
            for index,pub in enumerate(outcome['publications']):
                pin = outcome['samples'][index]
                self.assertEqual(pub['queued_raw'],dict(sequence=samples[index]['durability_record']['sequence'],
                    sha256=pin['sha256'],bytes=pin['bytes']))
                self.assertLessEqual(pub['updated_monotonic_s']-samples[index]['snapshot']['monotonic_s'],.5)
            self.assertLessEqual(max(b['snapshot']['monotonic_s']-a['snapshot']['monotonic_s']
                for a,b in zip(samples,samples[1:])),.5)
            self.assertLessEqual(max(b['updated_monotonic_s']-a['updated_monotonic_s']
                for a,b in zip(outcome['publications'],outcome['publications'][1:])),.5)
            request = worker.read(worker.checked(outcome['finish_request']))
            self.assertGreaterEqual(samples[-1]['snapshot']['monotonic_s'],request['created_monotonic_s'])
            release = worker.read(worker.checked(outcome['control_release']))
            self.assertTrue(release['directory_absent'])
            self.assertEqual(release['last_publication']['sha256'],outcome['final_live']['sha256'])

    def test_failed_durable_prefix_never_authorizes_native_readiness_or_success(self):
        with tempfile.TemporaryDirectory() as directory:
            code,outcome,seen,errors,injected,producer = self.fixture(Path(directory),fail_certificate=True)
            self.assertEqual(code,1)
            self.assertFalse(outcome['success'])
            self.assertIn('buffered certificate durability failure',outcome['error'])
            self.assertIsNone(outcome['initial'])
            self.assertTrue(all(row['initial'] is None for row in seen))
            self.assertTrue(outcome['all_writer_threads_stopped'])
            self.assertIsNone(outcome['durability_seal'])
            self.assertTrue(worker.read(worker.checked(outcome['control_release']))['directory_absent'])


if __name__=='__main__':
    unittest.main()
