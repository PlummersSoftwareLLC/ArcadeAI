#!/usr/bin/env python3
"""Root-owned fixed448 quality carrier; default literal PLAN has no reads.

Narrow adaptation of the actual384 root launcher. Only explicit --execute may
prepare a real default plan, perform fresh preflight, or schedule the campaign.
There is no service release, retry, checkpoint request, or publication action.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import urllib.request

R=Path('/home/dave/source/repos/ArcadeAI');G=R/'Robotron';B=G/'logs/managed-learning-20261015';RUN=B/'run-26'
D=RUN/'quality448M-actual-default-plan-prelaunch-20261017'
J=RUN/'quality448M-actual-durable-launch-reviewed1-20261017'
OUT=B/'quality-384M-vs-448M-20261017'
U='robotron-quality-384M-vs-448M-20261017'
REFERENCE=G/'models_dqn/managed-incumbents/fresh3-384M-confirmed.pt'
REFERENCE_SHA='ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963'
CANDIDATE=G/'models_dqn/managed-checkpoints/fresh3-448M.pt'
CPU_WRAPPER_SHA='ea6ccfcd62e2683641475634ba1647856a988691a6cede3dbeda629dd03ba56b'
CAMPAIGN=G/'tools/run_quality_campaign.py'
CAMPAIGN_SHA='574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128'
SIDECAR_SHA='cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90'
BASELINE=RUN/'live8-success-current-health-root-reviewed2-20261017/root-current-health-PASS.json'
BASELINE_SHA='27cbecb43b76ff4e01b0b268bc2c1404b83ee708aaaa55a51ebfba91bda83a2c'
OLD_PLAN=B/'quality-256M-vs-384M-20261017/plan.json'
OLD_PLAN_SHA='81210cb86ad7cd78b3f9a7f4c764b83aad3364d0d8f0e382e29f340245a54704'
GPU0='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
GPU1='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'
TARGET=452629023


def require(ok,message):
    if not ok:raise RuntimeError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def call(argv,timeout=20):
    value=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
    return dict(argv=argv,returncode=value.returncode,stdout=value.stdout,stderr=value.stderr)


def show(unit):
    value=call(['systemctl','--user','show',unit]);require(value['returncode']==0,'Unit show failed')
    return value,dict(line.split('=',1) for line in value['stdout'].splitlines() if '=' in line)


def pinned_json(path,expected):
    require(path is not None and expected is not None and Path(path).stat().st_size<=4<<20,'Explicit bounded JSON+SHA required')
    before=sha(path);require(before==expected,'Bound JSON SHA differs: '+str(path))
    value=json.loads(Path(path).read_text());require(sha(path)==before,'Bound JSON changed during parse')
    return value,dict(path=str(Path(path).resolve()),sha256=before)


def inputs(args):
    require(args.candidate_sha256 and type(args.candidate_bytes) is int and 200<<20<=args.candidate_bytes<=400<<20,
            'Actual future candidate SHA/bytes required')
    job,jp=pinned_json(args.root_job,args.root_job_sha256)
    proof,pp=pinned_json(args.cpu_proof,args.cpu_proof_sha256)
    completion,cp=pinned_json(args.cpu_completion,args.cpu_completion_sha256)
    require(job['schema']=='robotron-managed-candidate-checkpoint-CPU-job-v1' and job['verifier_sha256']==CPU_WRAPPER_SHA
            and job['candidate']['tag']=='fresh3-448M' and job['candidate']['target_learner_frames']==TARGET,
            'Actual generic448 root job differs')
    require(job['source']['path']==str(CANDIDATE) and job['source']['sha256']==args.candidate_sha256
            and job['source']['bytes']==args.candidate_bytes,'Actual candidate source identity differs')
    require(proof['schema']=='robotron-managed-candidate-checkpoint-CPU-result-v1' and proof['status']=='PASS'
            and proof['root_job']==job and proof['job_file']['sha256']==jp['sha256']
            and proof['script']['sha256']==CPU_WRAPPER_SHA and proof['sha256']==args.candidate_sha256
            and proof['bytes']==args.candidate_bytes and proof['path']==job['verification_copy']['path']
            and proof['clocks']['learner_frame_count']>=TARGET,'Actual generic CPU proof/source/job differs')
    require(completion['status']=='PASS' and completion['original_exec_code']==1 and completion['original_exit']==0
            and completion['original_result']=='success' and completion['original_terminal_archived_before_release'] is True
            and completion['owned_unit_released'] is True and type(completion['original_pid']) is int
            and completion['original_pid']>0 and len(completion['original_invocation'])==32
            and completion['job_sha256']==jp['sha256'] and completion['cpu_verification']==pp['path']
            and completion['cpu_verification_sha256']==pp['sha256'], 'Matching CPU original0/released report/job required')
    require(CANDIDATE.stat().st_size==args.candidate_bytes and sha(CANDIDATE)==args.candidate_sha256,
            'Candidate changed after CPU verification')
    require(sha(REFERENCE)==REFERENCE_SHA and not REFERENCE.stat().st_mode&0o222,'Protected384 reference differs')
    return dict(job=jp,cpu_proof=pp,cpu_completion=cp,candidate_sha256=args.candidate_sha256,candidate_bytes=args.candidate_bytes),job


def default_argv():
    return ['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1',
        str(R/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',str(CAMPAIGN),
        '--reference-checkpoint',str(REFERENCE),'--candidate-checkpoint',str(CANDIDATE),'--output-dir',str(OUT),
        '--reference-label','fresh3-384M-reference','--candidate-label','fresh3-448M-candidate','--gpu-uuid',GPU0,
        '--boot-assets',str(B/'sidecar-boot-assets-v1'),'--port','9999','--cohort-s','1200','--timeout-s','2400',
        '--mame','/usr/games/mame','--rompath',str(G/'roms'),'--game-boundary-diagnostics',
        '--hypothesis','Saved448M improves greedy full-game score over protected384M in fresh matched frozen cohorts with common boundary diagnostics.']


def launch_argv(saved):
    require(saved==default_argv(),'Saved default argv differs from exact reviewed canonical profile')
    return [*saved,'--launch']


def validate_plan(plan,candidate_sha):
    require(plan['output_directory']==str(OUT) and plan['checkpoints']['reference']['source']==str(REFERENCE)
            and plan['checkpoints']['reference']['sha256']==REFERENCE_SHA
            and plan['checkpoints']['candidate']['source']==str(CANDIDATE)
            and plan['checkpoints']['candidate']['sha256']==candidate_sha,'Fresh plan checkpoints/output differ')
    policy=plan['precommit']
    require(policy['order']==['reference','candidate','reference','candidate'] and policy['min_full_games_per_leg']==50
            and policy['all_actor_slots']==list(range(4096,4112)) and policy['include_every_admitted_game'] is True
            and policy['include_full_completion_tail'] is True and policy['max_attempts_per_leg']==1
            and policy['admission_extensions'] is False and policy['automatic_promotion'] is False
            and policy['automatic_rollback'] is False and policy['learning_changes'] is False
            and policy['candidate_gate']==dict(each_candidate_individually=True,reference='all games pooled from both fresh reference legs',minimum_mean_ratio=1.05,minimum_median_ratio=1.0),
            'Fresh fixed cohort/tail/individual quality gates differ')
    require([leg['role'] for leg in plan['legs']]==['reference','candidate','reference','candidate'],'Four fresh legs required')
    for leg in plan['legs']:
        job=leg['job'];require(job['cohort_s']==1200 and job['timeout_s']==2400 and job['actors']==16
            and job['actor_slots']==list(range(4096,4112)) and job['gpu_uuid']==GPU0 and job['port']==9999
            and job['game_boundary_diagnostics'] is True and job['inference_backend']=='inductor'
            and job['fp16'] is False and job['replay_enabled'] is False and job['epsilon']==0 and job['expert_ratio']==0
            and job['cpu_threads']==2 and job['checkpoint']==plan['checkpoints'][leg['role']]['snapshot'],
            'All four identical compiledFP32 fixed evaluation profiles required')


def source_checks(plan):
    require(sha(CAMPAIGN)==CAMPAIGN_SHA and sha(G/'tools/run_frozen_sidecar.py')==SIDECAR_SHA,'Frozen campaign/evaluator source changed')
    for path,value in plan['evaluator_source_hashes'].items():require(sha(G/path)==value,'Evaluator closure changed: '+path)
    for path,value in plan['execution_source_hashes'].items():require(sha(path)==value,'Execution closure changed: '+path)
    old,_=pinned_json(OLD_PLAN,OLD_PLAN_SHA)
    require(plan['evaluator_source_hashes']==old['evaluator_source_hashes'] and plan['execution_source_hashes']==old['execution_source_hashes']
            and plan['boot_assets']==old['boot_assets'],'Approved common12+4/boot protocol differs')
    for name,value in plan['boot_assets']['files'].items():
        path=B/'sidecar-boot-assets-v1'/name
        require(path.stat().st_size==value['bytes'] and sha(path)==value['sha256'],'Frozen boot source changed')


def prepare(args):
    bound,_=inputs(args)
    require(not D.exists() and not OUT.exists() and not J.exists(),'Fresh preview/output/execution directories required')
    require(sha(CAMPAIGN)==CAMPAIGN_SHA and sha(G/'tools/run_frozen_sidecar.py')==SIDECAR_SHA,'Approved source differs')
    D.mkdir()
    argv=default_argv();result=call(argv,timeout=60)
    write(D/'default-execution.json',result);require(result['returncode']==0,'Actual campaign default failed; preserve once result')
    plan=json.loads(result['stdout']);validate_plan(plan,args.candidate_sha256);source_checks(plan)
    write(D/'default-plan.json',plan);write(D/'default-argv.json',argv)
    sources={**{str(G/path):value for path,value in plan['evaluator_source_hashes'].items()},**plan['execution_source_hashes']}
    archive=D/'source-archive';archive.mkdir()
    entries={}
    for index,(path,value) in enumerate(sorted(sources.items())):
        copy_path=archive/(str(index).zfill(2)+'-'+Path(path).name)
        with copy_path.open('xb') as stream:
            stream.write(Path(path).read_bytes());stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        require(sha(copy_path)==value and sha(path)==value,'Source changed during archival')
        entries[path]=dict(sha256=value,copy=str(copy_path))
    write(D/'root-default-plan-source-review.json',dict(status='PASS_FIXED_PROTOCOL_SOURCE_BINDING',plan_sha256=sha(D/'default-plan.json'),source_entries=entries,actual_inputs=bound,source_freeze=True))
    return dict(status='ACTUAL_PLAN_PREPARED_NOT_LAUNCHED',preview_sha256=sha(D/'default-plan.json'),directory=str(D))


def readiness_contract(value,bound):
    health,_=pinned_json(BASELINE,BASELINE_SHA)
    require(value['schema']=='robotron-quality448-exclusive-readiness-v1' and value['status']=='PASS'
            and type(value['observed_unix_s']) in (float,int) and 0<=time.time()-value['observed_unix_s']<180,
            'Actual runtime observation must be fresh within180s')
    require(value['candidate']==dict(source=str(CANDIDATE),sha256=bound['candidate_sha256'],bytes=bound['candidate_bytes'],
            root_job_sha256=bound['job']['sha256'],cpu_proof_sha256=bound['cpu_proof']['sha256']),
            'Runtime candidate/CPU/job identity differs')
    require(value['main_owner']==dict(pid=4140916,starttime_ticks=31570251,invocation_id='cf4f26d3c5b84d9ab1302ded3a073519')
            and value['fleet_owner']==dict(pid=2258189,starttime_ticks=26614335,invocation_id='5ade9b2810524877921946df11ea597e')
            and value['inference_worker']==dict(tid=4142023,starttime_ticks=31574570,mask=list(range(72))),
            'Runtime main/fleet/inference incarnation differs')
    key=lambda actor:(actor['pid'],actor['starttime_ticks'],actor['slot'],actor['mask'])
    require(len(value['actors'])==192 and sorted(map(key,value['actors']))==sorted(map(key,health['actors']))
            and value['source_hashes']==health['source_hashes'] and value['control_hashes']==health['control_hashes'],
            'Runtime exact192/held60/control2 bindings differ')
    resources=value['resources']
    require(resources['gpu0_uuid']==GPU0 and resources['gpu1_uuid']==GPU1 and resources['GPU0_free_bytes']>=14*(1<<30)
            and all(resources[name] is True for name in ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free',
                'no_competing_helpers','no_private_cgroup_tmpfs_processes','no_pending_save','capture_and_CPU_units_released',
                'commands_UID_cwd_exe_checked','held_environment_checked','unit_files_checked')),
            'Fresh exclusive resource/owner/held-profile proof incomplete')
    require(value['unit_files'] and all(Path(path).is_absolute() and sha(path)==digest for path,digest in value['unit_files'].items()),
            'Current unit-file closure differs')


def fast_runtime(readiness):
    health,_=pinned_json(BASELINE,BASELINE_SHA)
    require(len(health['source_hashes'])==60 and len(health['control_hashes'])==2,'Exact held60/control2 baseline required')
    for path,value in {**health['source_hashes'],**health['control_hashes']}.items():require(sha(path)==value,'Held60/control2 changed')
    for unit,pid,ticks,inv in [('robotron-managed-run-26-d3b365c9-trainer.service',4140916,31570251,'cf4f26d3c5b84d9ab1302ded3a073519'),
            ('robotron-managed-run-26-d3b365c9-fleet.service',2258189,26614335,'5ade9b2810524877921946df11ea597e')]:
        _,value=show(unit);require(value['MainPID']==str(pid) and value['InvocationID']==inv and value['SubState']=='running','Main/fleet owner changed')
        require(int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])==ticks,'Main/fleet PID reused')
    for actor in health['actors']:
        path=Path('/proc',str(actor['pid']),'stat')
        require(int(path.read_text().rsplit(')',1)[1].split()[19])==actor['starttime_ticks']
                and sorted(os.sched_getaffinity(actor['pid']))==actor['mask']==list(range(72)),'Original192 identity/mask drift')
    require(len(health['actors'])==192,'Exact192 actor baseline required')
    require(int(Path('/proc/4140916/task/4142023/stat').read_text().rsplit(')',1)[1].split()[19])==31574570
            and sorted(os.sched_getaffinity(4140916))==list(range(72)) and sorted(os.sched_getaffinity(4142023))==list(range(72)),
            'Main/inference mask changed')
    for path in ('/proc/net/tcp','/proc/net/tcp6'):
        require(not any(row.split()[3]=='0A' and int(row.split()[1].rsplit(':',1)[1],16)==9999 for row in Path(path).read_text().splitlines()[1:]),'Port9999 not clear')
    with Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock').open('r+') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lease,fcntl.LOCK_UN)
    require(not (G/'models_dqn/managed_save.request.json').exists(),'Managed save pending')
    raw=Path('/proc/4140916/environ').read_bytes().split(b'\0')
    environment={part.split(b'=',1)[0].decode():part.split(b'=',1)[1].decode() for part in raw
        if b'=' in part and part.split(b'=',1)[0].decode().startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_'))}
    require(hashlib.sha256(json.dumps(environment,sort_keys=True).encode()).hexdigest()==readiness['environment_sha256'],
            'Main held execution environment differs from fresh readiness')
    applications=call(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'])
    require(applications['returncode']==0,'GPU ownership query failed')
    rows=[(int(line.split(',')[0]),line.split(',')[1].strip()) for line in applications['stdout'].splitlines() if line.strip()]
    require(all(uuid!=GPU0 for pid,uuid in rows) and [(pid,uuid) for pid,uuid in rows if uuid==GPU1]==[(4140916,GPU1)],
            'GPU0 owner remains or main GPU ownership differs')
    memory=call(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'])
    require(memory['returncode']==0,'GPU free-memory query failed')
    free={line.split(',')[0].strip():int(line.split(',')[1].strip())*(1<<20) for line in memory['stdout'].splitlines() if line.strip()}
    require(free[GPU0]>=14*(1<<30),'GPU0 free margin below14GiB')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as stream:api=json.load(stream)
    require(api['client_count']==192 and api['training_enabled'] and not api['measurement_active']
            and api['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth'
            and api['host_pipeline']['learning_exposure']['optimizer']['process_id']==4140916,'Current API owner/held branch changed')
    return dict(main_pid=4140916,actors=192,current_learner_frames=api['learner_frame_count'])


def launch(args):
    bound,job=inputs(args)
    require(args.plan_sha256 and sha(D/'default-plan.json')==args.plan_sha256,'Explicit reviewed actual plan SHA required')
    plan=json.loads((D/'default-plan.json').read_text());validate_plan(plan,args.candidate_sha256);source_checks(plan)
    prepared=json.loads((D/'root-default-plan-source-review.json').read_text())
    require(prepared['actual_inputs']==bound and prepared['plan_sha256']==sha(D/'default-plan.json'),'Prepared input bindings changed')
    review,rp=pinned_json(args.plan_review,args.plan_review_sha256)
    ready,rr=pinned_json(args.runtime_readiness,args.runtime_readiness_sha256)
    require(str(review['status']).startswith('PASS') and review['plan_sha256']==args.plan_sha256
            and review['actual_inputs']==bound, 'Plan review does not identify exact actual plan/inputs')
    readiness_contract(ready,bound)
    require(not OUT.exists() and not J.exists(),'Fresh campaign/execution directory required')
    for unit in (U+'.service',U+'.timer',json.loads(Path(job['candidate']['capture_execution']['path']).read_text())['gate_unit']['unit']):
        require(show(unit)[1]['LoadState']=='not-found','Owned quality/capture unit still retained or live: '+unit)
    current=fast_runtime(ready)
    # GPU ownership/free margin, no competing helpers/private resources, full
    # command/UID/environment/unit closure and recent logs are independently
    # reviewed in the fresh immutable runtime receipt, per READINESS.txt.
    J.mkdir()
    argv=launch_argv(json.loads((D/'default-argv.json').read_text()))
    command=['systemd-run','--user','--on-active=3s','--timer-property=AccuracySec=100ms','--unit='+U,
        '--property=Type=exec','--property=WorkingDirectory='+str(R),'--property=Restart=no','--property=RemainAfterExit=yes',
        '--property=KillMode=mixed','--property=KillSignal=SIGINT','--property=SendSIGKILL=no','--property=TimeoutStopSec=240s',
        '--property=StandardOutput=append:'+str(J/'console.log'),'--property=StandardError=inherit',*argv]
    write(J/'precommit.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),unit=U,argv=command,
        actual_inputs=bound,plan_sha256=sha(D/'default-plan.json'),plan_review=rp,runtime_readiness=rr,current=current,
        scheduling_delay_s=3,source_freeze=True,learning_changes=False,automatic_retry=False))
    with (J/'root-launch-controller.py').open('xb') as stream:
        stream.write(Path(__file__).read_bytes());stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    carrier=call(command);reaped_monotonic_ns=time.monotonic_ns()
    write(J/'scheduling-carrier-result.json',dict(carrier,carrier_reaped_by_subprocess_run=True,returned_unix_s=time.time(),returned_monotonic_ns=reaped_monotonic_ns))
    require(carrier['returncode']==0,'Scheduling carrier failed; preserve result without retry')
    raw,timer=show(U+'.timer');write(J/'original-timer-show-after-carrier-reaped.json',raw)
    raw,service=show(U+'.service');write(J/'service-after-carrier-reaped.json',raw)
    still_waiting=timer.get('ActiveState')=='active' and timer.get('SubState')=='waiting' and service.get('MainPID')=='0'
    started_after_reap=(int(service.get('ExecMainStartTimestampMonotonic','0'))*1000>reaped_monotonic_ns
        and service.get('InvocationID') and int(service.get('ExecMainPID','0'))>0 and service.get('NRestarts')=='0')
    require(still_waiting or started_after_reap, 'Carrier-before-trigger proof unavailable; preserve actual owned launch, never relaunch')
    if started_after_reap:
        if service.get('SubState')=='running':observe()
        else:
            write(J/'original-controller-identity.json',dict(pid=int(service['ExecMainPID']),
                invocation_id=service['InvocationID'],unit=U+'.service',observed_live=False,
                terminal_before_live_observation=True,start_monotonic_us=int(service['ExecMainStartTimestampMonotonic'])))
    return dict(status='DURABLE_LAUNCH_SUBMITTED',unit=U,carrier_reaped_before_trigger=True)


def observe():
    raw,value=show(U+'.service');pid=int(value['MainPID'])
    require(value['SubState']=='running' and pid>0 and value['InvocationID'] and value['NRestarts']=='0'
            and value['FragmentPath'].endswith('/'+U+'.service') and str(CAMPAIGN) in value['ExecStart']
            and str(OUT) in value['ExecStart'],'Actual owned running controller not ready')
    ticks=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    result=dict(pid=pid,starttime_ticks=ticks,invocation_id=value['InvocationID'],unit=U+'.service',observed_live=True)
    path=J/'original-controller-identity.json'
    if path.exists():
        require(json.loads(path.read_text())==result,'Existing owned observation differs')
        return result
    write(J/'original-controller-running-show.json',raw);write(path,result)
    return result


def archive():
    identity=json.loads((J/'original-controller-identity.json').read_text())
    raw,value=show(U+'.service')
    require(value['MainPID']=='0' and value['SubState'] in ('exited','dead','failed')
            and value['ExecMainPID']==str(identity['pid']) and value['InvocationID']==identity['invocation_id']
            and value['NRestarts']=='0','Original retained terminal identity differs; no collected defaults')
    write(J/'original-terminal-show.json',raw)
    write(J/'original-terminal-cat.json',call(['systemctl','--user','cat',U+'.service']))
    write(J/'original-invocation-journal.json',call(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+identity['invocation_id'],'--no-pager','-o','short-precise']))
    result=dict(status='ORIGINAL_TERMINAL_ARCHIVED_NOT_RELEASED',original=identity,exec_main_code=int(value['ExecMainCode']),
        exec_main_status=int(value['ExecMainStatus']),result=value['Result'],service_retained=True)
    write(J/'original-terminal-archive.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--action',choices=('prepare','launch','observe','archive'),default='prepare')
    for name in ('candidate-sha256','root-job-sha256','cpu-proof-sha256','cpu-completion-sha256','plan-sha256','plan-review-sha256','runtime-readiness-sha256'):parser.add_argument('--'+name)
    parser.add_argument('--candidate-bytes',type=int)
    for name in ('root-job','cpu-proof','cpu-completion','plan-review','runtime-readiness'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: future actual448 CPU proof/candidate required before default-plan; reviewed fresh runtime before detached launch; no reads/imports/queries/actions')
        return 0
    result=prepare(args) if args.action=='prepare' else launch(args) if args.action=='launch' else observe() if args.action=='observe' else archive()
    print(json.dumps(result,indent=2,allow_nan=False));return 0


if __name__=='__main__':
    raise SystemExit(main())
