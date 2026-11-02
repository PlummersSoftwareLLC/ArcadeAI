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
S=I/'durable-e078b0da-launcher-mmap-study-original01'
D=I/'declared-launcher-evaluator-adapters-original04-mmap-preparation'
MANIFEST_SHA='53cadb2588874e143bf4385bd1d446fa83d31eb6784b371aacd634ec37c7bfe3'
UNIT='robotron-e078-original-R1-wrapper-original01-20261029.service'


def require(value,message):
    if not value:raise RuntimeError(message)


def load(name,path,digest):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Selected wrapper dependency changed')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def run(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Exact selected R1 wrapper required')
    h=load('_e078_R1_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    helper=load('_e078_R1_original_Popen',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py',
        'b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4')
    read=lambda p:json.loads(h.checked(p).read_bytes())
    rp=h.pin(args.readiness.resolve());require(rp['sha256']==args.readiness_sha256 and rp['identity']['mode']=='0o444','Exact immutable final readiness required')
    ready=read(rp);require(ready['status']=='READY' and ready['CPU_qualifications_closed']is ready['original_attempts_unused']is True
        and ready['exact_review_precommit_and_source_CPU_binding_verified']is True
        and 0<=time.time()-ready['checked_unix_s']<120,'Fresh completed exact-source readiness required')
    mp=ready['prepared_manifest'];require(mp['path']==str(S/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json')and mp['sha256']==MANIFEST_SHA,'Exact new E078 four-job manifest required')
    manifest=read(mp);study=read(manifest['study_precommit']);require(manifest['engineering_only']is False
        and study['ordered_legs']==['R1','C1','R2','C2'] and study['no_retry']is True
        and study['policies']['candidate']['checkpoint']['sha256']=='e078b0da4ce4e25146fab7484f8489f590e1086370746cb392afcd7f5f8adef5'
        and study['policies']['reference']['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883',
        'Exact fresh RCRC E078/protected3045 pair required')
    review=read(ready['review_precommit']);cpu=read(ready['review_preparation_CPU'])
    require(review['native_prepared']==mp and review['engineering_only']is False
        and review['source']==h.pin(D/'prepare_deadline_independent_review_v4.py')
        and cpu['status']=='PASS_ENGINEERING_ONLY' and cpu['actual_exit']==0
        and read(cpu['original_job'])['review_precommit']==ready['review_precommit'], 'Actual selected independent-review precommit/CPU required')
    case=manifest['cases'][0];entry=ready['configurations'][0];job=read(case['native_job']);cfg=read(entry['config'])
    require(case['leg']==entry['leg']==job['leg']=='R1' and case['role']=='reference'
        and case['native_controller']==entry['controller']==h.pin(D/'control_deadline32_rounds_v11.py')
        and job['runtime']==h.pin(D/'run_deadline32_rounds_v11.py')
        and entry['config']['path']==str(S/'R1/controller-config-CPU-QUALIFIED.json'), 'Exact new R1 runtime/controller/config required')
    require(not Path(job['output']).exists() and not Path(cfg['output']).exists()
        and not(S/'R1/controller-original-launch.json').exists() and not(A/'original-R1-wrapper-intent.json').exists(),
        'One original R1 scheduling attempt only')
    active=(json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes()).get('active_quality_job')or{})
    require(active.get('directory')==str(S) and active.get('candidate_sha256')==study['policies']['candidate']['checkpoint']['sha256'],
        'Root must register this exact new study before the original launch')
    values=dict(x.split('=',1)for x in subprocess.check_output(['systemctl','--user','show',UNIT],text=True,timeout=5).splitlines()if'='in x)
    expected=dict(Id=UNIT,MainPID=str(os.getpid()),InvocationID=os.environ.get('INVOCATION_ID'),Type='exec',
        ActiveState='active',SubState='running',Restart='no',NRestarts='0',RemainAfterExit='yes',CPUQuotaPerSecUSec='2s',
        MemoryMax=str(512<<20),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='1h 20min',TimeoutStopUSec='10s',SendSIGKILL='no')
    require(all(values.get(k)==v for k,v in expected.items()) and expected['InvocationID'], 'Exact durable Root wrapper scope required')
    wp=helper.birth(os.getpid());require(wp is not None,'Original wrapper birth unavailable')
    intent=h.put(A/'original-R1-wrapper-intent.json',dict(source=h.pin(Path(__file__).resolve()),readiness=rp,
        exact_original_job=case['native_job'],exact_original_config=entry['config'],original_attempt=1,no_retry=True,
        actual_wrapper_pid=os.getpid(),actual_wrapper_birth=wp,unit=UNIT,invocation_id=expected['InvocationID'],
        actual_wrapper_scope=values,created_unix_s=time.time(),canonical_state_written=False))
    def on_live(owner,child):
        h.put(A/'actual-original-R1-live-owner.json',dict(original_job=case['native_job'],config=entry['config'],
            owner=owner,controller=child,wrapper_pid=os.getpid(),wrapper_birth=wp,wrapper_unit=UNIT,
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--readiness',type=Path)
    p.add_argument('--readiness-sha256');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if a.run:sys.exit(run(a))
    else:print('PLAN_ONLY: no reads, outputs, queries, launches or controls')
