"""New CPU/native-Lua full-tail runtime scope, ownership and final receipt guards.

No Torch, GPU, real MAME, systemd launch or consumed test methods run. Native
Lua fixture definitions run a new transcript to test the final host join.
"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


runtime=load('_full_tail32_new_scope_runtime',HERE/'run_compiled_full_tail32_v1.py')
control=load('_full_tail32_new_scope_control',HERE/'control_compiled_full_tail32_v1.py')
native=load('_consumed_wire_v2_fixture_defs_only',HERE/'test_full_tail_wire_v2.py')


class OriginalCompiledFullTailScope(unittest.TestCase):
    def directory(self):
        t=tempfile.TemporaryDirectory(prefix='robotron-original-full-tail32-scope-');self.addCleanup(t.cleanup)
        return Path(t.name)

    def job(self,directory):
        prior=runtime.G/'logs/managed-learning-20261015/run-26/compiled32-policy-startup-real-original01-preparation-20261022/job.json'
        j=json.loads(prior.read_bytes())
        j.update(schema='robotron-compiled-full-tail32-original-v1',startup_trace_frames=1200,
            wall_limit_s=9600,whole_cohort_timeout_s=9000,output=str(directory/'uncreated-output'),
            full_tail_predecessors={key:dict(sha256=sha)for key,sha in dict(
                compiled_startup='7d44dd648fa22836c96a39d126d468f572b282129c0e1ff0bcc77a96f4efb4da',
                continuation_wire='94412a9e8cb258734c9d6e160e3ff2c4636419559c838a85bd69096397e91b7b',
                host_drain='efc3fe13f58624479f0bed3d50d5616c89b4e46ddcb19d91e292d3d88090d900',
                bridge_ledger='477bb10126f7a15e856979f0c96b8e8e299b5aaefafac0a45cb98bf62b760082').items()})
        j.pop('frames')
        return j

    def test_fixed32_GPU_backend_policy_predecessors_and_whole_cohort_bounds(self):
        directory=self.directory();job=self.job(directory)
        self.assertEqual(runtime.validate_job(job),directory/'uncreated-output')
        for key,value in [('actor_slots',list(runtime.SLOTS[:-1])),('device','cpu'),('backend','eager'),
            ('gpu_uuid','GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'),('admission_s',91),
            ('startup_trace_frames',1200.),('whole_cohort_timeout_s',180),('wall_limit_s',840)]:
            with self.subTest(key=key),self.assertRaises(ValueError):runtime.validate_job(dict(job,**{key:value}))
        for key in job['full_tail_predecessors']:
            damaged=copy.deepcopy(job);damaged['full_tail_predecessors'][key]['sha256']='0'*64
            with self.subTest(predecessor=key),self.assertRaises(ValueError):runtime.validate_job(damaged)
        damaged=copy.deepcopy(job);damaged['connections']['4097']=damaged['connections']['4096']
        with self.assertRaises(ValueError):runtime.validate_job(damaged)
        self.assertNotIn('torch',sys.modules)

    def test_actor_environment_keeps_private_paths_inputs_and_has_no_emulated_game_cutoff(self):
        directory=self.directory();job=self.job(directory)
        base=dict(HOME='/home/dave',CUDA_VISIBLE_DEVICES='foreign',ROBOTRON_EVAL_MODE='0',
            ROBOTRON_FULL_TAIL_LIFECYCLE='foreign',ROBOTRON_DEBUG_BYPASS_FRAMES='100',
            LD_PRELOAD='foreign',PYTHONPATH='foreign')
        for slot in runtime.SLOTS:
            private=directory/str(slot)
            env=runtime.actor_environment(base,private,slot,job['sessions'][str(slot)],
                job['connections'][str(slot)],directory/'owned-wait.so')
            self.assertEqual(env['HOME'],'/home/dave');self.assertEqual(env['CUDA_VISIBLE_DEVICES'],'')
            self.assertEqual(env['ROBOTRON_EVAL_MODE'],'1');self.assertEqual(env['ROBOTRON_ENABLE_RRCHRIS_PATCH'],'0')
            self.assertEqual(env['ROBOTRON_FULL_TAIL_LIFECYCLE'],str(private/'lifecycle.jsonl'))
            self.assertEqual(env['ROBOTRON_FULL_STARTUP_TRACE'],str(private/'producer.jsonl'))
            self.assertEqual(env['ROBOTRON_SOCKET_ADDRESS'],'127.0.0.1:'+str(runtime.PORTS[slot]))
            self.assertNotIn('ROBOTRON_DEBUG_BYPASS_FRAMES',env);self.assertNotIn('PYTHONPATH',env)
            argv=runtime.actor_command(job,private)
            self.assertNotIn('-seconds_to_run',argv)
            self.assertIn('-noreadconfig',argv);self.assertIn('-cheat',argv)
            self.assertEqual(argv[argv.index('-autoboot_script')+1],str(private/'boot.lua'))

    def test_controller_exact_full_tail_resources_and_original_ownership_lifecycle_preserved(self):
        directory=self.directory()
        jobpath=runtime.G/'logs/managed-learning-20261015/run-26/full-tail32-scope-contract-fixture/job.json'
        source=HERE/'run_compiled_full_tail32_v1.py'
        cfg=dict(unit='robotron-compiled-full-tail32-integration-original01-20261022.service',
            output=str(directory/'not-launched'),argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python',
                '-Xgil=0','-I','-B',str(source),'--execute','--job',str(jobpath),
                '--job-sha256','a'*64,'--source-sha256','b'*64],
            properties=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=9660',
                'TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
            pins=[dict(path=str(jobpath),sha256='a'*64),dict(path=str(source),sha256='b'*64)],observation_s=9720)
        path=directory/'controller-fixture.json'
        def check(value):path.write_text(json.dumps(value));return control.checked_config(path)
        self.assertEqual(check(cfg),cfg)
        for damage in ('resource','unit','runtime','observation'):
            changed=copy.deepcopy(cfg)
            if damage=='resource':changed['properties'][3]='RuntimeMaxSec=900'
            elif damage=='unit':changed['unit']='robotron-managed-run-26-d3b365c9-trainer.service'
            elif damage=='runtime':changed['argv'][4]=str(HERE/'run_compiled_startup32_v2.py')
            else:changed['observation_s']=960
            with self.subTest(damage=damage),self.assertRaises(ValueError):check(changed)
        parent=ast.parse((HERE/'control_compiled_startup32_v2.py').read_text())
        current=ast.parse((HERE/'control_compiled_full_tail32_v1.py').read_text())
        def lifecycle(tree):return [ast.dump(n,include_attributes=False)for n in tree.body
            if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name!='checked_config']
        self.assertEqual(lifecycle(parent),lifecycle(current))
        parent_runtime=load('_consumed_prefix_runtime_defs_only',HERE/'run_compiled_startup32_v2.py')
        import inspect
        self.assertEqual(inspect.getsource(runtime.PrivateLease),inspect.getsource(parent_runtime.PrivateLease))

    def test_native_Lua_full_tail_lifecycle_joins_exact_applied_STOP_and_rejects_corruption(self):
        raw=native.run_lua('for sequence=1,1202 do step(sequence,false)end;step(1203,true);return table.concat(lifecycle_lines)',steps=True).encode()
        rows=[json.loads(line)for line in raw.splitlines()]
        prefix=rows[1];response=rows[2]
        proxy=SimpleNamespace(sequence=1203,last_response=bytes.fromhex(response['response_hex']),
            stop_receipt=dict(sequence=1203),issuer=SimpleNamespace(nonce=response['nonce']),
            prefix_summary=dict(events=prefix['trace_events'],footer={k:prefix[k]for k in
                ('first_play_sequence','initialized_sequence','latched_sequence')}))
        subject={k:response[k]for k in ('slot','session','connection')}
        self.assertEqual(runtime.validate_lifecycle(raw,subject,proxy),rows)
        for index,key,value in [(3,'apply_ok',False),(3,'socket_ok',False),(3,'start',1),
            (2,'nonce','f'*64),(4,'response_hex','00'*48),(5,'failed',True),
            (1,'first_play_sequence',9),(0,'continuation_enabled',False),(3,'slot',4097)]:
            changed=copy.deepcopy(rows);changed[index][key]=value
            damaged=(''.join(json.dumps(r)+'\n'for r in changed)).encode()
            with self.subTest(index=index,key=key),self.assertRaises(ValueError):runtime.validate_lifecycle(damaged,subject,proxy)
        with self.assertRaises(ValueError):runtime.validate_lifecycle(raw+b'{}\n',subject,proxy)
        self.assertNotIn('torch',sys.modules)


if __name__=='__main__':unittest.main(verbosity=2)
