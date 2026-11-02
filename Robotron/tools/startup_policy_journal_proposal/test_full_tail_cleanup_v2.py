"""New original cleanup/evidence contract with actual owned Python children.

No real MAME, Torch/GPU, main actors or prior scientific/guard methods run.
The child waits for input to model a writer released by origin shutdown.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

HERE=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


runtime=load('_new_original_full_tail_cleanup_v2',HERE/'run_compiled_full_tail32_v2.py')
h=load('_original_cleanup_pin_helpers',HERE/'run_full_policy_startup_v3.py')
CHILD='''import os,sys
with open(sys.argv[1],"ab") as stream:
 stream.write(b"before\\n");stream.flush()
 print("READY",flush=True)
 sys.stdin.buffer.read(1)
 stream.write(b"after\\n");stream.flush();os.fsync(stream.fileno())
sys.exit(int(sys.argv[2]))
'''


class OriginalFullTailCleanupV2(unittest.TestCase):
    def directory(self):
        t=tempfile.TemporaryDirectory(prefix='robotron-original-tail-cleanup-v2-');self.addCleanup(t.cleanup)
        return Path(t.name)

    def child(self,code=0):
        directory=self.directory();path=directory/'actor-stdout.txt'
        child=subprocess.Popen([sys.executable,'-I','-B','-c',CHILD,str(path),str(code)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.assertEqual(child.stdout.readline(),b'READY\n')
        birth=runtime.process_birth(child.pid);self.assertIsNotNone(birth)
        def release():
            if not child.stdin.closed:
                try:child.stdin.close()
                except BrokenPipeError:pass
            if child.poll()is None:
                child.wait(timeout=5)
            for pipe in (child.stdout,child.stderr):pipe.close()
        self.addCleanup(release)
        return dict(child=child,birth=birth,private=directory)

    def release(self,row):row['child'].stdin.write(b'x');row['child'].stdin.flush();row['child'].stdin.close()

    def test_live_original_writer_stays_unsealed_then_actual_nonzero_reap_seals_final_bytes(self):
        row=self.child(17);path=row['private']/'actor-stdout.txt';original_mode=path.stat().st_mode&0o777
        first=runtime.await_original_actor_exits({4096:row},timeout_s=.06)
        self.assertFalse(first['all_original_children_reaped']);self.assertEqual(first['unknown_slots'],[4096])
        self.assertIsNone(first['original_children']['4096']['actual_exit'])
        def no_pin(path):raise AssertionError('A live writer must never be hashed as final')
        withheld=runtime.finalize_actor_outputs(row,False,True,no_pin)
        self.assertEqual(withheld['files'],{});self.assertEqual(path.stat().st_mode&0o777,original_mode)
        self.assertEqual(withheld['original_unsealed_output_paths'],[str(path)])
        self.release(row)
        final=runtime.await_original_actor_exits({4096:row},timeout_s=5)
        self.assertTrue(final['all_original_children_reaped'])
        self.assertEqual(final['original_children']['4096']['actual_exit'],17)
        self.assertFalse(final['signals_sent']);self.assertFalse(final['exit_statuses_normalized'])
        sealed=runtime.finalize_actor_outputs(row,True,True,h.pin)
        self.assertTrue(sealed['outputs_sealed_after_original_writer_closure'])
        self.assertEqual(path.read_bytes(),b'before\nafter\n')
        self.assertEqual(h.pin(path),sealed['files']['actor-stdout.txt'])
        self.assertEqual(path.stat().st_mode&0o777,0o444)

    def test_actual_negative_child_exit_is_preserved_without_success_normalization(self):
        row=self.child();child=row['child']
        self.assertEqual(runtime.process_birth(child.pid),row['birth'])
        child.terminate();result=runtime.await_original_actor_exits({4096:row},timeout_s=5)
        self.assertTrue(result['all_original_children_reaped'])
        self.assertEqual(result['original_children']['4096']['actual_exit'],-15)
        self.assertFalse(result['exit_statuses_normalized'])

    def test_foreign_birth_and_unfinished_owned_thread_cannot_seal_outputs(self):
        row=self.child();child=row['child']
        with self.assertRaisesRegex(ValueError,'birth changed'):
            runtime.await_original_actor_exits({4096:dict(row,birth=row['birth']+1)},timeout_s=.06)
        self.assertIsNone(child.poll())
        withheld=runtime.finalize_actor_outputs(row,True,True,h.pin)
        self.assertFalse(withheld['outputs_sealed_after_original_writer_closure'])
        self.assertEqual(withheld['files'],{})
        self.release(row);runtime.await_original_actor_exits({4096:row},timeout_s=5)
        event=threading.Event();worker=threading.Thread(target=event.wait);worker.start()
        self.addCleanup(lambda:(event.set(),worker.join(5)))
        self.assertFalse(runtime.finalize_actor_outputs(row,True,not worker.is_alive(),h.pin)
                         ['outputs_sealed_after_original_writer_closure'])
        event.set();worker.join(5)
        self.assertTrue(runtime.finalize_actor_outputs(row,True,not worker.is_alive(),h.pin)
                        ['outputs_sealed_after_original_writer_closure'])

    def test_failed_census_API_and_bad_JSON_are_persisted_before_validation_rejection(self):
        for bad_json in (False,True):
            with self.subTest(bad_json=bad_json):
                directory=self.directory();snapshot=dict(schema='synthetic-census-only',slot=51)
                wire=b'{broken JSON\n'if bad_json else b'{"learner_frame_count":123,"training_steps":456}\n'
                def validate(api):
                    self.assertEqual((directory/'0000-API.raw.json').read_bytes(),wire)
                    self.assertEqual(json.loads((directory/'0000-census.json').read_bytes()),snapshot)
                    raise ValueError('synthetic identity changed')
                record,failure,error=runtime.persist_main_observation(directory,0,snapshot,wire,validate,h)
                self.assertIsInstance(error,ValueError)
                self.assertEqual(h.pin(directory/'0000-API.raw.json'),record['raw_API'])
                self.assertEqual((directory/'0000-API.raw.json').read_bytes(),wire)
                result=json.loads(Path(failure['path']).read_bytes())
                self.assertFalse(result['accepted']);self.assertTrue(result['raw_census_and_API_preserved_before_validation'])
                self.assertEqual(result['original_observation'],record)
                self.assertIn('JSONDecodeError'if bad_json else 'synthetic identity changed',result['actual_error'])
                self.assertEqual((directory/'0000-census.json').stat().st_mode&0o777,0o444)
        self.assertNotIn('torch',sys.modules)


if __name__=='__main__':unittest.main(verbosity=2)
