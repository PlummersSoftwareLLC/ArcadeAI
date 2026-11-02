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


def phase(name,**values):
    print(json.dumps(dict(schema='robotron-CPU-guard-phase-v1',phase=name,monotonic_s=time.monotonic(),**values)),flush=True)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def execute(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Actual CPU driver differs')
    raw=Path(args.job).read_bytes();require(hashlib.sha256(raw).hexdigest()==args.job_sha256,'Actual CPU job differs')
    job=json.loads(raw);require(job['schema']=='robotron-deadline32-four-actual-jobs-CPU-guard-v2','New exact CPU job schema required')
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
        metadata={entry['path']:entry for entry in job['allowed_model_directory_metadata']}
        allowed_control=False
        if str(path)in metadata:
            require(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode), 'Pinned control metadata is not regular')
            actual=path.stat();expected=metadata[str(path)]['identity']
            require(actual.st_size<=1048576 and actual.st_size==metadata[str(path)]['bytes']
                    and actual.st_dev==expected['device'] and actual.st_ino==expected['inode'], 'Pinned control metadata identity differs')
            allowed_control=True
        require(path.suffix!='.pt' and ('models_dqn'not in path.parts or allowed_control),'Checkpoint/model body read prohibited in CPU guard')
        return original_open(path,*a,**kw)
    Path.open=guarded_open
    h=load('_deadline_actual_CPU_helpers',Path(job['helpers']['path']))
    phase('held_inputs_begin',count=len(job['inputs']))
    for pin in job['inputs']:h.checked(pin)
    phase('held_inputs_complete')
    def stat_only(pin):
        p=Path(pin['path']);s=p.lstat();i=pin['identity']
        if p.is_symlink():
            require(str(p)==sys.executable=='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python'
                and pin['sha256']=='4e1fe416a017995fb2f7e3e9b2fcd9ee80490fdcc17ad54e2625d245c179c048',
                'Only the exact selected known interpreter may use symlink binding')
            witness=json.loads(h.checked(job['interpreter_symlink_binding']).read_bytes())
            require(witness['source_pin']==pin and witness['path']==str(p)
                and witness['resolved_target']=='/home/dave/source/robotron-python/cpython-3.14.8+freethreaded-linux-aarch64-gnu/bin/python3.14t'
                and str(p.resolve(strict=True))==witness['resolved_target'],'Exact interpreter resolved target differs')
            def links_unchanged():
                require(len(witness['links'])==2 and witness['links'][0]['path']==str(p),'Exact known two-link interpreter chain required')
                for row in witness['links']:
                    link=Path(row['path']);v=link.lstat()
                    actual=dict(device=v.st_dev,inode=v.st_ino,bytes=v.st_size,mtime_ns=v.st_mtime_ns,ctime_ns=v.st_ctime_ns,
                        mode=oct(stat.S_IMODE(v.st_mode)),uid=v.st_uid,nlink=v.st_nlink)
                    require(stat.S_ISLNK(v.st_mode) and os.readlink(link)==row['readlink']
                        and actual==row['lstat_identity'],'Exact interpreter link identity/target changed')
            links_unchanged();s=p.stat();resolved=Path(witness['resolved_target']).lstat()
            require(stat.S_ISREG(s.st_mode)and stat.S_ISREG(resolved.st_mode)
                and (s.st_dev,s.st_ino)==(resolved.st_dev,resolved.st_ino),'Interpreter resolved regular inode differs')
            links_unchanged()
        else:
            require(stat.S_ISREG(s.st_mode) and s.st_size==pin['bytes'],'Attested regular model/MAME large input stat differs')
        values=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
            mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
        require(s.st_size==pin['bytes'] and all(values[k]==v for k,v in i.items()),'Attested large input identity changed')
    for pin in job['large_input_stat_attestations']:stat_only(pin)
    prepared=json.loads(h.checked(job['prepared_manifest']).read_bytes());cases=prepared['cases']
    require([v['leg']for v in cases]==['R1','C1','R2','C2'],'Actual fixed four serialized subjects required')
    native=load('_deadline_actual_CPU_native',h.checked(cases[0]['runtime']))
    # Explicit semantic reuse from the already closed exact four-job metadata
    # execution. Every original per-job domain join and every raw full SHA and
    # identity remain freshly checked; no scientific/native function changes.
    phase('closed_metadata_authority_begin')
    reuse_module=load('_closed_metadata_readiness_reuse',h.checked(job['readiness_reuse_shim']))
    reuse=reuse_module.ClosedMetadataReadiness(job,h,phase)
    original_contract_factory=native.round_contract
    def bounded_contract():
        return reuse.bind(original_contract_factory())
    native.round_contract=bounded_contract
    subjects=[]
    for case in cases:
        subject=json.loads(h.checked(case['native_job']).read_bytes())
        require(not Path(subject['output']).exists()and not Path(case['unqualified_controller_config']['path']).parent.joinpath('execution-original01').exists(),
                'Actual native output/execution must remain unused')
        require(Path(subject['prelaunch_family_guard_closeout'])==Path(subject['output']).parent/'source-family-guards-CPU-original01'/'independent-deadline32-family-guards-and-CPU-closeout.json',
            'Exact frozen native.run prelaunch guard path differs')
        require(not Path(subject['prelaunch_family_guard_closeout']).exists(),'Future exactjob CPU closeout must remain unused')
        subjects.append((case,subject))
    prebody=[];negative_checks=[]
    class ActualSerializedJobs(unittest.TestCase):
        def test_all_four_actual_native_completed_prebody_contexts(self):
            for case,subject in subjects:
                with self.subTest(leg=case['leg']):
                    ctx=native.validate_completed_context(subject,h)
                    self.assertEqual(len(ctx['modules']),12)
                    self.assertEqual(len(ctx['main_binding']['inputs']),native.round_contract().static_profile().validate_inventory(ctx['main_binding'],h)['input_count'])
                    baseline=json.loads(h.checked(ctx['main_binding']['baseline_snapshot']).read_bytes())
                    native.round_contract().static_profile().sample_domain(ctx['main_binding'],baseline)
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
                for damage in ('schema','binding','dependency','family','hot_bound','initial_samples','lease_inode','lease_path'):
                    p,f,j=copy.deepcopy(protocol),copy.deepcopy(family),copy.deepcopy(subject)
                    if damage=='schema':p['schema']='foreign'
                    elif damage=='binding':p['case']['sha256']='f'*64
                    elif damage=='dependency':
                        f['main_observer']['worker']['sha256']='f'*64
                        j['observer_sources']=copy.deepcopy(f['main_observer'])
                    elif damage=='hot_bound':p['hot_max_gap_s']=5
                    elif damage=='initial_samples':p['initial_samples']=5
                    elif damage=='lease_inode':
                        j['lease']=copy.deepcopy(j['lease']);j['lease']['identity']['inode']+=1
                    elif damage=='lease_path':
                        j['lease']=copy.deepcopy(j['lease']);j['lease']['path']+='.foreign'
                    else:f['deadline_components']['clock_proxy']['sha256']='f'*64
                    with self.subTest(leg=case['leg'],damage=damage),self.assertRaises(ValueError):native.validate_main_health_contract(j,p,f)
                    negative_checks.append(dict(leg=case['leg'],damage=damage,rejected=True))
        def test_actual_no_Torch_model_native_outputs_or_premature_guard_receipts(self):
            self.assertNotIn('torch',sys.modules)
            with self.assertRaisesRegex(ValueError,'body read prohibited'):Path(subjects[0][1]['checkpoint']['path']).open('rb')
            for case,subject in subjects:
                self.assertFalse(Path(subject['output']).exists());self.assertFalse(Path(subject['prelaunch_family_guard_closeout']).exists())
        def test_private_native_and_score_review_predicates_retained(self):
            for case,subject in subjects:
                family=json.loads(h.checked(subject['source_family_manifest']).read_bytes())
                proof=native.round_contract().validate_derivation(subject['runtime']['path'],family['reviewer']['path'])
                self.assertTrue(proof['background_health_contract_only'])
                self.assertTrue(proof['extra_preownership_launch_gate'])
        def test_actual_main_domain_proof_and_engineering_launch_refusal(self):
            for case,subject in subjects:
                ctx=native.validate_completed_context(subject,h)
                if prepared['engineering_only']:
                    with self.assertRaises(ValueError):native.round_contract().validate_launch(subject,ctx,h)
                    trial=dict(ctx);trial['family']=copy.deepcopy(ctx['family']);trial['family']['native_launch_qualified']=True
                    proof=native.round_contract().validate_launch(subject,trial,h)
                else:
                    proof=native.round_contract().validate_launch(subject,ctx,h)
                self.assertTrue(proof['raw_API_and_TCP_and_retirement_snapshots_replayed'])
                self.assertTrue(proof['accepted_evidence_and_projection_gaps_verified'])
                self.assertTrue(proof['prior_completed_EVAL_prefix_and_current_suffix_verified'])
                self.assertEqual(proof['main_health_profile'],'PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5')
                self.assertEqual(proof['verified_maximum_gap_s'],2.0)
                self.assertEqual(proof['proof_gap_contract'],'robotron-main-proof-gap-2s-v1')
                self.assertEqual(proof['full_main_input_count'],len(ctx['main_binding']['inputs']))
            self.assertEqual(reuse.counts,dict(semantics_reused_from_closed_metadata=4,raw_full_integrity_passes=4))
    tests=load('_deadline_actual_CPU_NEW_native_chain_tests',h.checked(job['new_native_chain_tests']))
    actual_new_count=unittest.defaultTestLoader.loadTestsFromTestCase(tests.Tests).countTestCases()
    require(actual_new_count==job['expected_new_native_chain_tests'],'Exact selected NEW integration count differs')
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(ActualSerializedJobs),
        unittest.defaultTestLoader.loadTestsFromTestCase(tests.Tests)])
    phase('subject_and_integration_tests_begin',tests=suite.countTestCases())
    started=time.time();capture=io.StringIO();result=unittest.TextTestRunner(stream=capture,verbosity=2).run(suite)
    phase('subject_and_integration_tests_complete',passed=result.wasSuccessful(),tests=result.testsRun)
    for case,subject in subjects:require(not Path(subject['output']).exists(),'CPU guard created native outcome')
    require('torch'not in sys.modules,'CPU guard imported Torch')
    for pin in job['inputs']:h.checked(pin)
    for pin in job['large_input_stat_attestations']:stat_only(pin)
    output=Path(job['output']);require(not output.exists(),'Original CPU output already exists');output.mkdir(mode=0o700)
    report=dict(schema='robotron-deadline32-four-actual-jobs-CPU-guard-result-v1',passed=result.wasSuccessful(),
        tests_run=result.testsRun,actual_serialized_job_tests=6,
        readiness_semantics_reused_from_closed_metadata=reuse.counts['semantics_reused_from_closed_metadata'],
        readiness_raw_full_integrity_passes=reuse.counts['raw_full_integrity_passes'],
        closed_metadata_readiness_authority=job['closed_metadata_readiness_authority'],
        reused_predicates='Original closed metadata actual four-job raw health and all192 slot predicates; no semantic raw replay in this guard.',
        every_job_raw_hash_slot_and_owner_epoch_checks_unchanged=True,new_native_chain_tests=actual_new_count,
        old_clock_controller19_rerun=False,actual_prebody_contexts=prebody,actual_contract_negative_cases=negative_checks,
        native_jobs=[c['native_job']for c in cases],prepared_manifest=job['prepared_manifest'],original_CPU_job=h.pin(args.job),
        actual_scope=scope,actual_ControlGroup=cgroup,actual_PID=os.getpid(),
        interpreter=dict(executable=sys.executable,version=sys.version,GIL_enabled=sys._is_gil_enabled()),
        started_unix_s=started,ended_unix_s=time.time(),output=capture.getvalue(),
        errors=[str(x)for x in result.errors],failures=[str(x)for x in result.failures],
        all_native_outputs_absent=True,all_future_guard_receipts_absent=True,Torch_imported=False,checkpoint_body_opened=False,
        large_input_scope='Checkpoint tensors remain unopened and model .pt inputs are stat-only. Held main executables, source and small control metadata are hashed for domain validation. Native launch reauthenticates all selected inputs.',
        native_or_GPU_MAME_source_state_unit_controls=False,owned_scope_closure_claimed=False)
    pin=h.put(output/'report.json',report);print(capture.getvalue(),flush=True);print(json.dumps(dict(report=pin,passed=result.wasSuccessful(),tests_run=result.testsRun)),flush=True)
    return 0 if result.wasSuccessful()else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--job',type=Path)
    p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY_NO_READS_OR_ACTIONS');return 0
    return execute(a)

if __name__=='__main__':raise SystemExit(main())
