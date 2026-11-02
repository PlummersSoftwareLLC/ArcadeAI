"""Inert until Root runs one original independent R1 review and qualification.

The original R1 must already be closed by its own wrapper. This wrapper owns
one new review-controller Popen through wait/reap, then calls the unchanged
exact qualification function. No native launch, canonical update or retry.
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
O=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def load(name,path,digest):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Exact selected review dependency changed')
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


def run(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,
        'Exact Root-selected first review wrapper required')
    h=load('_first_R1_review_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    helper=load('_first_R1_actual_owned_Popen',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py',
        'b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4')
    launch_pin=h.pin(args.launch_selection.resolve())
    require(launch_pin['sha256']==args.launch_selection_sha256 and launch_pin['identity']['mode']=='0o444',
        'Exact actual immutable W03 launch selection required')
    launch=json.loads(h.checked(launch_pin).read_bytes())
    require(launch['schema']=='robotron-generic-physical-original-R1-launch-selection-v1'
        and launch['source']['sha256']=='5701b99c08bb7a7e16e4052daa45d2fae3bd6ba257a8592dd460804347d6320d'
        and launch['source']['identity']['mode']=='0o444'
        and launch['sources']['review_preparer']['sha256']=='d0955c345dd46d08d261cf6c20c8dff87e1335c4977d55d75a8ed895fac99be0'
        and launch['sources']['review_preparer']['identity']['mode']=='0o444',
        'Exact immutable generic physical launch and review sources required')
    A=Path(h.checked(launch['source'])).parent
    D=Path(h.checked(launch['sources']['review_preparer'])).parent
    S=Path(launch['prepared_manifest']['path']).parent
    require(S.is_relative_to(G/'logs/managed-learning-20261015/run-26')
        and launch['source']==h.pin(A/'prepare_owned_physical_R1_launch_v1.py')
        and launch['sources']['review_preparer']==h.pin(D/'prepare_deadline_independent_review_v4.py'),
        'Actual bound study, generator and review-preparer paths required')
    p=load('_first_R1_actual_review_preparation',D/'prepare_deadline_independent_review_v4.py',
        'd0955c345dd46d08d261cf6c20c8dff87e1335c4977d55d75a8ed895fac99be0')
    ready=json.loads(h.checked(launch['readiness']).read_bytes())
    precommit=S/'review-precommit-original01/precommitted-four-reviews.json'
    pp=h.pin(precommit);require(pp==ready['review_precommit'],'Exact actually qualified W03 review precommit required')
    _,read,selected,packet,case=p.selected(precommit,'R1')
    require(selected==pp and packet['CPU_guard_publication']==ready['exact_four_guards']
        and Path(packet['CPU_guard_publication']['path']).name=='all-four-exact-native-guard-receipts.json'
        and Path(packet['CPU_guard_publication']['path']).is_relative_to(G/'logs/managed-learning-20261015/run-26')
        and packet['native_prepared']==launch['prepared_manifest']
        and packet['native_prepared']['path']==str(S/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json'),
        'Actual new W03 D7 guard and four-job manifest required')
    operation=read(launch['ROOT_operation_inputs'])
    guards=read(packet['CPU_guard_publication']);guard_closed=read(guards['original_all4_CPU_closeout'])
    guard_report=read(guard_closed['actual_CPU_report'])
    authority=read(guard_report['closed_metadata_readiness_authority'])
    require(operation['schema']=='robotron-generic-physical-R1-ROOT-operation-inputs-v1'
        and operation['source_preparation']==launch['source_preparation']
        and authority['source_contract']==operation['guard_source_contract']
        and authority['native_prepared']==packet['native_prepared']
        and guard_closed['actual_exit']==0 and guard_closed['tests_run']==10
        and guard_report['readiness_semantics_reused_from_closed_metadata']==4
        and guard_report['readiness_raw_full_integrity_passes']==4,
        'Exact actual Root-selected guard contract and four-subject closure required')
    manifest=read(packet['native_prepared'])
    require(manifest['study_precommit']==launch['study_precommit']
        and manifest['study_precommit']['path']==str(S/'study-precommit.json'),
        'Exact actual W03 fixed RCRC study required')
    study=read(manifest['study_precommit'])
    require(study['policies']['candidate']['checkpoint']['sha256']==launch['candidate_sha256']
        and launch['candidate_capture']['result']in study['prospective_capture_evidence']
        and read(launch['candidate_capture']['result'])['endpoint']['sha256']==launch['candidate_sha256']
        and study['policies']['reference']['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883',
        'Exact actual W03 candidate/protected pair required')
    unit='robotron-physical-cohort-proof2s-'+manifest['study_precommit']['sha256'][:16]+'-r1-independent-review-wrapper-original01-20261029.service'
    fields=dict(v.split('=',1)for v in subprocess.check_output(['systemctl','--user','show',unit],text=True,timeout=5).splitlines()if'='in v)
    expected=dict(Id=unit,MainPID=str(os.getpid()),InvocationID=os.environ.get('INVOCATION_ID'),
        Type='exec',ActiveState='active',SubState='running',Restart='no',NRestarts='0',RemainAfterExit='yes',
        CPUQuotaPerSecUSec='2s',MemoryMax=str(512<<20),MemorySwapMax='0',TasksMax='128',
        RuntimeMaxUSec='40min',TimeoutStopUSec='10s',SendSIGKILL='no')
    require(expected['InvocationID']and all(fields.get(k)==v for k,v in expected.items()),
        'Exact durable first independent-review wrapper scope required')
    prepared_pin=h.pin(args.prepared.resolve())
    require(prepared_pin['sha256']==args.prepared_sha256 and prepared_pin['identity']['mode']=='0o444'
        and prepared_pin['path']==str(S/'R1/independent-review-prepared-original01.json'),
        'Exact actually prepared original R1 review required')
    prepared=read(prepared_pin)
    require(prepared['precommit']==pp and prepared['leg']=='R1' and prepared['no_retry']is True
        and prepared['controller']==packet['sources']['controller']and prepared['reviewer']==case['reviewer']
        and prepared['review_job']['path']==case['review_job_path']
        and prepared['review_config']['path']==case['review_config_path'],
        'Original first review preparation differs')
    owner_pin=h.pin(A/'actual-original-R1-live-owner.json');original=read(owner_pin)
    require(original['original_job']==case['native_job']and original['config']==case['native_config'],
        'Original R1 owner is from another job/config')
    require(helper.birth(original['wrapper_pid'])!=original['wrapper_birth']
        and helper.birth(original['controller']['pid'])!=original['controller']['starttime_ticks']
        and helper.birth(original['owner']['pid'])!=original['owner']['starttime_ticks'],
        'Original R1 wrapper/controller/native must all be closed')
    closed=p.closed_controller(S/'R1','',case['native_config'],case['native_controller'],packet['sources'],h,read)
    require(closed['result']['path']==str(S/'R1/controller-original-result.json'),
        'Actual original R1 controller closure differs')
    active=(json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes()).get('active_quality_job')or{})
    require(active.get('directory')==str(S)and active.get('current_leg',1)in(1,'R1'),
        'Root must retain this exact original R1 study registration')
    cfg=read(prepared['review_config'])
    require(not Path(cfg['output']).exists()and not Path(case['report']).exists()
        and not(S/'R1/independent-review-controller-original-launch.json').exists()
        and not(S/'R1/root-R1-independent-qualified.json').exists()
        and not(O/'first-R1-review-wrapper-intent.json').exists(),
        'One original independent review scheduling attempt only')
    me=helper.birth(os.getpid());require(me is not None,'Wrapper birth unavailable')
    intent=h.put(O/'first-R1-review-wrapper-intent.json',dict(source=h.pin(Path(__file__).resolve()),
        review_precommit=pp,actual_prepared_review=prepared_pin,original_R1_owner=owner_pin,
        original_native_closed=closed,original_attempt=1,no_retry=True,wrapper_pid=os.getpid(),wrapper_birth=me,
        wrapper_unit=unit,wrapper_invocation_id=expected['InvocationID'],actual_scope=fields,created_unix_s=time.time()))
    def on_live(owner,child):
        pin=h.put(O/'actual-first-independent-R1-review-live-owner.json',dict(prepared_review=prepared_pin,
            owner=owner,controller=child,wrapper_pid=os.getpid(),wrapper_birth=me,wrapper_unit=unit,
            wrapper_invocation_id=expected['InvocationID'],observed_unix_s=time.time()))
        print(json.dumps(dict(event='FIRST_ORIGINAL_R1_INDEPENDENT_REVIEW_RUNNING',receipt=pin)),flush=True)
    outcome=dict(schema='robotron-first-original-R1-independent-review-wrapper-terminal-v1',intent=intent,
        original_attempt=1,no_retry=True,wrapper_pid=os.getpid(),wrapper_birth=me,
        native_relaunched=False,review_retried=False,full_game_quality_qualified=False,promotion=False)
    try:
        result=helper.invoke_controller_once(S/'R1','independent-review-',prepared['controller'],prepared['review_config'],h,on_live)
        actual=read(result);outcome.update(controller_result=result,actual_controller_exit=actual['actual_exit'],
            live_registration_errors=actual['live_registration_errors'])
        require(type(actual['actual_exit'])is int and actual['actual_exit']==0 and actual['live_registration_errors']==[],
            'Original independent review failed or has unresolved registration; no retry')
        qualified=p.qualify(precommit,'R1')
        outcome.update(status='ORIGINAL_R1_INDEPENDENTLY_QUALIFIED',qualification=qualified);code=0
    except Exception as error:
        outcome.update(status='ORIGINAL_REVIEW_UNQUALIFIED_PRESERVED_NO_RETRY',error=repr(error),traceback=traceback.format_exc());code=1
    outcome['ended_unix_s']=time.time();pin=h.put(O/'first-R1-review-wrapper-terminal.json',outcome)
    print(json.dumps(dict(terminal=pin,status=outcome['status'])),flush=True);return code


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--prepared',type=Path)
    p.add_argument('--prepared-sha256');p.add_argument('--expected-source-sha256');p.add_argument('--launch-selection',type=Path);p.add_argument('--launch-selection-sha256');args=p.parse_args()
    if args.run:raise SystemExit(run(args))
    print('PLAN_ONLY: no reads, outputs, imports, queries, controls or launches')
