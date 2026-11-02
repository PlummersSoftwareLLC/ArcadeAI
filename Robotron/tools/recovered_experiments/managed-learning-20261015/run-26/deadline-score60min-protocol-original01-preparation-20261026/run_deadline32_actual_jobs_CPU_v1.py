"""One original CPU qualification of four actual serialized deadline32 jobs.

No launch/observe/signal, model opening, Torch import, GPU/MAME or main mutation.
The separate ROOT closeout follows terminal archive/release; this report alone
never pretends its own process has closed.
"""
import argparse
import copy
import hashlib
import importlib.abc
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import unittest


def require(ok,message):
    if not ok:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def execute(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Actual CPU driver differs')
    raw=Path(args.job).read_bytes();require(hashlib.sha256(raw).hexdigest()==args.job_sha256,'Actual CPU job differs')
    job=json.loads(raw);require(job['schema']=='robotron-deadline32-four-actual-jobs-CPU-guard-v1','New exact CPU job schema required')
    require(sys.version_info[:2]==(3,14)and sys._is_gil_enabled()is False,'Actual free-threaded3.14 required')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and not os.environ.get('LD_PRELOAD'),'Explicit CPU-only environment required')
    require('torch'not in sys.modules,'Torch must not precede prebody guard')
    fields_result=subprocess.run(['systemctl','--user','show',job['unit']],capture_output=True,text=True,timeout=10)
    require(fields_result.returncode==0,'Actual original CPU scope show failed')
    fields=dict(line.split('=',1)for line in fields_result.stdout.splitlines()if'='in line)
    scope=dict(Id=job['unit'],MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],ActiveState='active',
        SubState='running',NRestarts='0',CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',
        RuntimeMaxUSec='3min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no')
    require(all(fields.get(k)==v for k,v in scope.items()),'Actual exact2CPU/4GiB/180s scope differs')
    cgroup=next(x.split(':',2)[2]for x in Path('/proc/self/cgroup').read_text().splitlines()if x.startswith('0::'))
    require(cgroup==fields['ControlGroup'],'Actual original CPU cgroup differs')
    class DenyTorch(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname=='torch'or fullname.startswith('torch.'):raise RuntimeError('Torch import prohibited in actual prebody CPU guard')
    sys.meta_path.insert(0,DenyTorch())
    original_open=Path.open
    def guarded_open(path,*a,**kw):
        require(path.suffix!='.pt'and 'models_dqn'not in path.parts,'Checkpoint/model body read prohibited in CPU guard')
        return original_open(path,*a,**kw)
    Path.open=guarded_open
    h=load('_deadline_actual_CPU_helpers',Path(job['helpers']['path']))
    for pin in job['inputs']:h.checked(pin)
    def stat_only(pin):
        p=Path(pin['path']);s=p.lstat();i=pin['identity']
        require(stat.S_ISREG(s.st_mode)and not p.is_symlink()and s.st_size==pin['bytes'],'Attested large input stat differs')
        values=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
            mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
        require(all(values[k]==v for k,v in i.items()),'Attested large input identity changed')
    for pin in job['large_input_stat_attestations']:stat_only(pin)
    prepared=json.loads(h.checked(job['prepared_manifest']).read_bytes());cases=prepared['cases']
    require([v['leg']for v in cases]==['R1','C1','R2','C2'],'Actual fixed four serialized subjects required')
    native=load('_deadline_actual_CPU_native',h.checked(cases[0]['runtime']))
    subjects=[]
    for case in cases:
        subject=json.loads(h.checked(case['native_job']).read_bytes())
        require(not Path(subject['output']).exists()and not Path(case['unqualified_controller_config']['path']).parent.joinpath('execution-original01').exists(),
                'Actual native output/execution must remain unused')
        require(not Path(subject['prelaunch_family_guard_closeout']).exists(),'Future exactjob CPU closeout must remain unused')
        subjects.append((case,subject))
    prebody=[];negative_checks=[]
    class ActualSerializedJobs(unittest.TestCase):
        def test_all_four_actual_native_completed_prebody_contexts(self):
            for case,subject in subjects:
                with self.subTest(leg=case['leg']):
                    ctx=native.validate_completed_context(subject,h)
                    self.assertEqual(len(ctx['modules']),12)
                    self.assertEqual(len(ctx['main_binding']['held_hashes']),197)
                    self.assertEqual(len(ctx['main_binding']['actors']),192)
                    prebody.append(dict(leg=case['leg'],native_job=case['native_job'],runtime=case['runtime'],
                        component_count=len(ctx['modules']),package_source_count=len(ctx['package_pins']),main_binding=subject['main_binding'],
                        actual_full_health_contract_checked=True,protocol_provenance=ctx['protocol_provenance'],
                        Torch_and_checkpoint_body_opened=False))
        def test_actual_serialized_controller_pin_shapes_and_exact_scopes(self):
            control=load('_deadline_actual_CPU_native_controller',h.checked(cases[0]['native_controller']))
            for case,subject in subjects:
                config=json.loads(h.checked(case['unqualified_controller_config']).read_bytes())
                self.assertEqual(control.checked_config(case['unqualified_controller_config']['path']),config)
                self.assertEqual(config['argv'][7:10],[case['native_job']['path'],'--job-sha256',case['native_job']['sha256']])
                bypath={p['path']:p for p in config['pins']}
                for selected in [case['native_job'],case['runtime'],subject['components']['clock_proxy']]:
                    actual=control.pin(selected['path']);self.assertEqual(bypath[selected['path']],actual)
                    self.assertEqual(set(actual['identity']),{'device','inode','mode','uid','nlink'})
                self.assertEqual(subject['runtime'],json.loads(h.checked(subject['source_family_manifest']).read_bytes())['runtime'])
        def test_actual_health_contract_rejects_foreign_schema_binding_dependency_and_family(self):
            for case,subject in subjects:
                protocol=json.loads(h.checked(subject['main_health_protocol']).read_bytes())
                family=json.loads(h.checked(subject['source_family_manifest']).read_bytes())
                for damage in ('schema','binding','dependency','family','duration'):
                    p,f=copy.deepcopy(protocol),copy.deepcopy(family)
                    if damage=='schema':p['schema']='foreign'
                    elif damage=='binding':p['health_job']['binding']['sha256']='f'*64
                    elif damage=='dependency':p['health_job']['sources']['transport']['sha256']='f'*64
                    elif damage=='duration':p['health_job']['duration_s']=4201
                    else:f['deadline_components']['clock_proxy']['sha256']='f'*64
                    with self.subTest(leg=case['leg'],damage=damage),self.assertRaises(ValueError):native.validate_main_health_contract(subject,p,f)
                    negative_checks.append(dict(leg=case['leg'],damage=damage,rejected=True))
        def test_actual_no_Torch_model_native_outputs_or_premature_guard_receipts(self):
            self.assertNotIn('torch',sys.modules)
            with self.assertRaisesRegex(ValueError,'body read prohibited'):Path(subjects[0][1]['checkpoint']['path']).open('rb')
            for case,subject in subjects:
                self.assertFalse(Path(subject['output']).exists());self.assertFalse(Path(subject['prelaunch_family_guard_closeout']).exists())
    tests=load('_deadline_actual_CPU_NEW_native_chain_tests',h.checked(job['new_native_chain_tests']))
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(ActualSerializedJobs),
        unittest.defaultTestLoader.loadTestsFromTestCase(tests.Tests)])
    started=time.time();capture=io.StringIO();result=unittest.TextTestRunner(stream=capture,verbosity=2).run(suite)
    for case,subject in subjects:require(not Path(subject['output']).exists(),'CPU guard created native outcome')
    require('torch'not in sys.modules,'CPU guard imported Torch')
    for pin in job['inputs']:h.checked(pin)
    for pin in job['large_input_stat_attestations']:stat_only(pin)
    output=Path(job['output']);require(not output.exists(),'Original CPU output already exists');output.mkdir(mode=0o700)
    report=dict(schema='robotron-deadline32-four-actual-jobs-CPU-guard-result-v1',passed=result.wasSuccessful(),
        tests_run=result.testsRun,actual_serialized_job_tests=4,new_native_chain_tests=unittest.defaultTestLoader.loadTestsFromTestCase(tests.Tests).countTestCases(),
        old_clock_controller19_rerun=False,actual_prebody_contexts=prebody,actual_contract_negative_cases=negative_checks,
        native_jobs=[c['native_job']for c in cases],prepared_manifest=job['prepared_manifest'],original_CPU_job=h.pin(args.job),
        actual_scope=scope,actual_ControlGroup=cgroup,actual_PID=os.getpid(),
        interpreter=dict(executable=sys.executable,version=sys.version,GIL_enabled=sys._is_gil_enabled()),
        started_unix_s=started,ended_unix_s=time.time(),output=capture.getvalue(),
        errors=[str(x)for x in result.errors],failures=[str(x)for x in result.failures],
        all_native_outputs_absent=True,all_future_guard_receipts_absent=True,Torch_imported=False,checkpoint_body_opened=False,
        large_input_scope='Selected previously attested model/MAME large inputs stat-only; no body hash or load. Native original launch reauthenticates allselectedinput digests.',
        native_or_GPU_MAME_source_state_unit_controls=False,owned_scope_closure_claimed=False)
    pin=h.put(output/'report.json',report);print(capture.getvalue(),flush=True);print(json.dumps(dict(report=pin,passed=result.wasSuccessful(),tests_run=result.testsRun)),flush=True)
    return 0 if result.wasSuccessful()else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--job',type=Path)
    p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY_NO_READS_OR_ACTIONS');return 0
    return execute(a)

if __name__=='__main__':raise SystemExit(main())
