"""Default inert. One Root-authorized durable R1 controller and same-child reap.

Uses the unchanged owned-Popen helper. No canonical state writes, main controls,
policy install, independent review, continuation launch or scientific retry.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
I=G/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027'
A=Path(__file__).resolve().parent
# Study/source directories are resolved from the exact immutable selection.



def require(value,message):
    if not value:raise RuntimeError(message)


def load(name,path,digest):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Selected wrapper dependency changed')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def run(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Exact selected R1 wrapper required')
    h=load('_window03_D7_R1_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    helper=load('_window03_D7_R1_original_Popen',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py',
        'b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4')
    read=lambda p:json.loads(h.checked(p).read_bytes())
    selected_pin=h.pin(args.launch_selection.resolve())
    require(selected_pin['sha256']==args.launch_selection_sha256 and selected_pin['identity']['mode']=='0o444',
        'Exact immutable fresh R1 launch selection required')
    selected=read(selected_pin)
    S=Path(selected['prepared_manifest']['path']).parent
    D=Path(selected['sources']['study_preparer']['path']).parent
    require(selected['schema']=='robotron-generic-physical-original-R1-launch-selection-v1'
        and selected['source']==h.pin(A/'prepare_owned_physical_R1_launch_v1.py')
        and selected['sources']['wrapper']==h.pin(Path(__file__).resolve()), 'Actual Root-selected R1 source differs')
    for value in selected['sources'].values():h.checked(value)
    rp=selected['readiness'];ready=read(rp)
    require(ready['status']=='READY' and ready['CPU_qualifications_closed']is ready['original_attempts_unused']is True
        and ready['exact_review_precommit_and_source_CPU_binding_verified']is True
        and ready['source']==selected['sources']['finalizer'], 'Completed exact-source readiness required')
    def fresh_operation():
        require(0<=time.time()-ready['checked_unix_s']<=30
            and 0<=time.monotonic()-selected['created_monotonic_s']<=30
            and selected['operation_started_unix_s']<=ready['checked_unix_s']<=selected['created_unix_s']
            and 0<=selected['created_monotonic_s']-selected['operation_started_monotonic_s']<=30,
            'Same-operation original preflight must be fresh within30s')
    fresh_operation()
    mp=ready['prepared_manifest']
    require(mp==selected['prepared_manifest'] and mp['path']==str(S/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json'),
        'Exact selected fresh physical four-job manifest required')
    manifest=read(mp);study=read(manifest['study_precommit'])
    require(manifest['engineering_only']is False and manifest['study_precommit']==selected['study_precommit']
        and study['ordered_legs']==['R1','C1','R2','C2'] and study['no_retry']is True
        and study['policies']['candidate']['checkpoint']['sha256']==selected['candidate_sha256']
        and selected['candidate_capture']['result']in study['prospective_capture_evidence']
        and read(selected['candidate_capture']['result'])['endpoint']['sha256']==selected['candidate_sha256']
        and read(selected['candidate_capture']['plan'])['owner']==read(selected['candidate_capture']['result'])['owner']
        and study['policies']['reference']['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883',
        'Exact fresh physical RCRC/protected pair required')
    namespace='physical-cohort-proof2s-'+manifest['study_precommit']['sha256'][:16]+'-r1'
    unit='robotron-'+namespace+'-wrapper-original01-20261029.service'
    require(selected['wrapper_unit']==unit, 'Exact new wrapper namespace differs')
    review=read(ready['review_precommit']);cpu=read(ready['review_preparation_CPU'])
    require(review['native_prepared']==mp and review['engineering_only']is False
        and review['source']==h.pin(D/'prepare_deadline_independent_review_v4.py')
        and cpu['status']=='PASS_ENGINEERING_ONLY' and cpu['actual_exit']==0
        and read(cpu['original_job'])['review_precommit']==ready['review_precommit'], 'Actual selected independent-review precommit/CPU required')
    case=manifest['cases'][0];entry=ready['configurations'][0];job=read(case['native_job']);cfg=read(entry['config'])
    require(case['leg']==entry['leg']==job['leg']=='R1' and case['role']=='reference'
        and case['native_controller']==entry['controller']==h.pin(D/'control_deadline32_rounds_v11.py')
        and job['runtime']==h.pin(D/'run_deadline32_rounds_v11.py')
        and entry['config']['path']==str(S/'R1/controller-config-CPU-QUALIFIED.json')
        and case['native_job']==selected['R1']['native_job'] and entry['config']==selected['R1']['config']
        and cfg['unit']==selected['R1']['native_unit'], 'Exact new R1 runtime/controller/config required')
    require(not Path(job['output']).exists() and not Path(cfg['output']).exists()
        and not(S/'R1/controller-original-launch.json').exists() and not(A/'original-R1-wrapper-intent.json').exists(),
        'One original R1 scheduling attempt only')
    active=(json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes()).get('active_quality_job')or{})
    require(active.get('directory')==str(S) and active.get('candidate_sha256')==study['policies']['candidate']['checkpoint']['sha256'],
        'Root must register this exact new study before the original launch')
    fresh_operation()
    values=dict(x.split('=',1)for x in subprocess.check_output(['systemctl','--user','show',unit],text=True,timeout=5).splitlines()if'='in x)
    expected=dict(Id=unit,MainPID=str(os.getpid()),InvocationID=os.environ.get('INVOCATION_ID'),Type='exec',
        ActiveState='active',SubState='running',Restart='no',NRestarts='0',RemainAfterExit='yes',CPUQuotaPerSecUSec='2s',
        MemoryMax=str(512<<20),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='1h 20min',TimeoutStopUSec='10s',SendSIGKILL='no')
    require(all(values.get(k)==v for k,v in expected.items()) and expected['InvocationID'], 'Exact durable Root wrapper scope required')
    wp=helper.birth(os.getpid());require(wp is not None,'Original wrapper birth unavailable')
    fresh_operation()
    intent=h.put(A/'original-R1-wrapper-intent.json',dict(source=h.pin(Path(__file__).resolve()),readiness=rp,launch_selection=selected_pin,
        exact_original_job=case['native_job'],exact_original_config=entry['config'],original_attempt=1,no_retry=True,
        actual_wrapper_pid=os.getpid(),actual_wrapper_birth=wp,unit=unit,invocation_id=expected['InvocationID'],
        actual_wrapper_scope=values,created_unix_s=time.time(),canonical_state_written=False))
    def on_live(owner,child):
        h.put(A/'actual-original-R1-live-owner.json',dict(original_job=case['native_job'],config=entry['config'],
            owner=owner,controller=child,wrapper_pid=os.getpid(),wrapper_birth=wp,wrapper_unit=unit,
            wrapper_invocation_id=expected['InvocationID'],readiness=rp,observed_unix_s=time.time()))
        print(json.dumps(dict(event='ORIGINAL_R1_NATIVE_RUNNING',owner=owner,controller=child)),flush=True)
    outcome=dict(schema='robotron-owned-durable-R1-wrapper-terminal-v1',intent=intent,original_attempt=1,no_retry=True,
        wrapper_pid=os.getpid(),wrapper_birth=wp,scientific_payload_retried=False,quality_qualified=False,promotion=False)
    try:
        result=helper.invoke_controller_once(S/'R1','',entry['controller'],entry['config'],h,on_live)
        value=read(result);outcome.update(controller_result=result,actual_controller_exit=value['actual_exit'],
            live_registration_errors=value['live_registration_errors'],status='NATIVE_CLOSED_REVIEW_PENDING'if value['actual_exit']==0 and value['live_registration_errors']==[]else'ORIGINAL_NONZERO_OR_REGISTRATION_FAILURE_NO_RETRY')
        code=0 if outcome['status']=='NATIVE_CLOSED_REVIEW_PENDING'else 1
    except Exception as error:
        outcome.update(status='ORIGINAL_OUTCOME_UNRESOLVED_NO_RETRY',error=repr(error),traceback=traceback.format_exc());code=1
    outcome['ended_unix_s']=time.time();terminal=h.put(A/'original-R1-wrapper-terminal.json',outcome)
    print(json.dumps(dict(terminal=terminal,status=outcome['status'])),flush=True);return code


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--launch-selection',type=Path)
    p.add_argument('--launch-selection-sha256');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if a.run:sys.exit(run(a))
    else:print('PLAN_ONLY: no reads, outputs, queries, launches or controls')
