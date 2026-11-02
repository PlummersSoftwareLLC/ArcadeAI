"""Prepare one fresh precommitted quality leg; no scheduling or main mutation."""
import argparse
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'tools/startup_policy_journal_proposal'
R=G/'logs/managed-learning-20261015/run-26'
ORDER=('R1','C1','R2','C2')
FOLDERS=('01-reference','02-candidate','03-reference','04-candidate')
ROLES={'R1':'reference','C1':'candidate','R2':'reference','C2':'candidate'}

def require(value,message):
    if not value:raise ValueError(message)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def prepare(readiness_pin,leg,h):
    readiness=json.loads(h.checked(readiness_pin).read_text())
    require(readiness['schema']=='robotron-certified-quality32-new-launch-readiness-v1'
        and readiness['leg_preparer']==h.pin(__file__)and leg in ORDER,
        'Exact new readiness/preparer/leg required')
    pair=json.loads(h.checked(readiness['quality_pair']).read_text())
    require(readiness['quality_pair']['sha256']=='7c74a3f8e27b3401404fe5d69bfbabd243f5cd57984b4f8f33087ba05a9a9f51',
        'Fixed original pair required')
    root=Path(readiness['campaign_directory']);index=ORDER.index(leg);directory=root/FOLDERS[index]
    require(root.is_relative_to(R)and root.resolve()==root and not directory.exists(),'Fresh exact original leg required')
    if index:
        previous=root/FOLDERS[index-1]
        report=json.loads((previous/'independent-quality-leg-review-original01/review.json').read_text())
        result=json.loads((previous/'independent-review-controller-original-result.json').read_text())
        require(report['valid']is report['full_game_score_verified']is True and report['quality_leg']==ORDER[index-1]
            and result['actual_exit']==0 and result['no_retry']is True,'Previous original leg must independently finish validly')
    for entry in readiness['inputs']:h.checked(entry)
    directory.mkdir(mode=0o700)
    template=json.loads(h.checked(readiness['native_job_template']).read_text())
    old_main=json.loads(h.checked(template['main_binding']).read_text())
    old_policy=json.loads(h.checked(old_main['supervision_policy']).read_text())
    sup=load('_fresh_quality_main_supervision',h.checked(template['main_sources']['supervision']))
    window=load('_fresh_quality_main_window',h.checked(template['main_sources']['window']))
    census=sup.collect(old_policy)
    require(set(census['actors'])==sup.SLOTS,'New leg must start with all192 current actors')
    for role in ('trainer','fleet'):
        sup.validate_owner(old_policy[role],census['owners'][role])
        require(all(census['owners'][role]['process'][k]==old_policy['baseline_owners'][role]['process'][k]
            for k in sup.STATIC),'Original main owner configuration changed')
    transitions=[]
    for slot,current in census['actors'].items():
        old=old_policy['baseline_actors'][slot];sup.validate_actor(slot,current,old,old_policy['fleet'])
        if sup.birth(current)!=sup.birth(old):
            require(census['previous_birth_probes'][slot]!=old['starttime_ticks']
                and current['starttime_ticks']>old['starttime_ticks'],'Unexplained actor identity transition')
            transitions.append(dict(slot=slot,old_pid=old['pid'],old_birth=old['starttime_ticks'],
                current_pid=current['pid'],current_birth=current['starttime_ticks']))
    main=copy.deepcopy(old_main)
    main['actors']=[dict(slot=int(slot),pid=row['pid'],starttime_ticks=row['starttime_ticks'],mask=row['affinity'])
        for slot,row in sorted(census['actors'].items(),key=lambda item:int(item[0]))]
    policy_preparer=load('_fresh_quality197_policy_preparer',h.checked(readiness['main_policy_preparer']))
    policy,snapshot=policy_preparer.make_policy(main,old_policy['fleet'])
    pp=h.put(directory/'prospective-main-supervision-policy.json',policy)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as response:raw=response.read(1048577)
    require(len(raw)<=1048576,'Bounded current main API required');api=json.loads(raw)
    state=sup.validate_snapshot(policy,snapshot,api['client_count'])
    require(state['full_capacity']and not state['pending']and not state['completed_episodes'],'Current main192 must be stable')
    window.owner_and_files(main)
    window.healthy(api,json.loads(h.checked(old_main['baseline_API']).read_text()),main['experiment'],time.time())
    require(0<=time.time()-(G/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime<=360,'Main autosave stale')
    with (directory/'baseline-API.raw.json').open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    main.update(supervision_policy=pp,baseline_API=h.pin(directory/'baseline-API.raw.json'),
        prospective_quality_leg=leg,prior_binding=template['main_binding'],
        new_leg_binding_only_prior_original_studies_unchanged=True)
    mp=h.put(directory/'prospective-main-binding.json',main)
    health=h.put(directory/'original-main192-private-resource-preflight.json',dict(
        current_census=snapshot,main_binding=mp,main192_valid=True,
        between_study_natural_actor_transitions=transitions,previous_studies_rebound=False,
        main_runtime_changed=False,observed_unix_s=time.time()))
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],
        capture_output=True,text=True,timeout=10)
    require(gpu.returncode==0 and template['gpu_uuid']not in gpu.stdout,'Private GPU0 must be idle')
    h.checked(template['lease']);fd=os.open(template['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    sockets=[]
    try:
        for port in [19998,*range(20000,20032)]:
            sock=socket.socket();sockets.append(sock);sock.bind(('127.0.0.1',port))
    finally:
        for sock in sockets:sock.close()
    resource=h.put(directory/'original-private-GPU-lease-and-port-preflight.json',dict(
        GPU_stdout=gpu.stdout,GPU_stderr=gpu.stderr,GPU_exit=gpu.returncode,
        lease=template['lease'],coordinator_unheld_and_unchanged=True,
        all33_private_ports_available=True,original_attempt=1,no_retry=True,observed_unix_s=time.time()))
    selected=pair[ROLES[leg]]
    runtime=load('_prepared_quality_native',h.checked(readiness['native_runtime']))
    controller=load('_prepared_quality_control',h.checked(readiness['native_controller']))
    reviewer=load('_prepared_quality_reader',h.checked(readiness['leg_reviewer']))
    job=copy.deepcopy(template)
    job.update(schema='robotron-compiled-full-tail32-quality-original-v1',created_unix_s=time.time(),
        runtime=readiness['native_runtime'],output=str(directory/'diagnostic-output-original01'),
        quality_leg=leg,quality_pair_precommit=readiness['quality_pair'],quality_launch_readiness=readiness_pin,
        minimum_completed_games=50,expected_policy_clocks=runtime.POLICIES[ROLES[leg]]['clocks'],
        checkpoint=selected['policy'],admission_s=5400,whole_cohort_timeout_s=9000,wall_limit_s=9600,
        label='quality1741-vs-restored192LR125-firstSave-'+leg.lower()+'-original01-20261023',
        main_binding=mp,sessions={str(slot):secrets.token_hex(16)for slot in runtime.SLOTS},
        connections={str(slot):secrets.token_hex(16)for slot in runtime.SLOTS},
        selected_change='Fresh same-backend frozen quality leg with certified first starts, fixed5400/min50 and every admitted full tail; strict source/runtime/main health. No learning change or promotion.',
        expected='Each original leg independently min50/all32/full tails/runtime valid. Only NEW R1+R2 form the fixed reference; C1 and C2 pass separately. No old engineering scores, retries or pooled candidate rescue.')
    additions=[*readiness['inputs'],readiness_pin,mp,pp,main['baseline_API'],health,resource,selected['policy'],
        selected['CPU_report'],selected['original_CPU_readback']]
    job['inputs']=list({entry['path']:entry for entry in [*template['inputs'],*additions]}.values())
    for entry in job['inputs']:h.checked(entry)
    runtime.validate_job(job);jp=h.put(directory/'job.json',job)
    scope=dict(schema='robotron-original-all32-compiled-quality32-acceptance-v1',job=jp,
        original_attempt=1,no_retry=True,fixed_admission_s=5400,whole_cohort_timeout_s=9000,
        wall_limit_s=9600,startup_trace_frames=1200,minimum_quality_completed_games=50,
        quality_minimum_games_remains=50,quality_qualified=False,promotion=False,
        quality_leg=leg,quality_pair=readiness['quality_pair'],launch_readiness=readiness_pin,
        requirements=pair,preflight=health,private_preflight=resource)
    ap=h.put(directory/'precommitted-acceptance-scope.json',scope)
    cfg=dict(unit='robotron-compiled-full-tail32-integration-quality1741-restored192lr125-firstsave-'+leg.lower()+'-original01-20261023.service',
        output=str(directory/'execution-original01'),
        argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',job['runtime']['path'],
            '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',job['runtime']['sha256']],
        properties=reviewer.PROPERTIES,pins=[controller.pin(e['path'])for e in [*job['inputs'],jp,ap]],observation_s=9720)
    cp=h.put(directory/'controller-config.json',cfg);controller.checked_config(cp['path']);reviewer.validate_scope(job,jp,scope,cfg)
    sources=dict(runtime=job['runtime'],control=readiness['native_controller'],wire=readiness['wire_auditor'],
        games=readiness['games_auditor'],native_closure=readiness['native_closure'],
        main_supervision=template['main_sources']['supervision'],main_window=template['main_sources']['window'],
        terminal_rom=readiness['terminal_rom'])
    review_job=dict(schema='robotron-original-quality32-independent-leg-review-job-v1',
        output=str(directory/'independent-quality-leg-review-original01'),native_job=jp,
        acceptance=ap,controller_config=cp,sources=sources)
    rjp=h.put(directory/'independent-review-job.json',review_job)
    cpu=load('_prepared_quality_cpu_control',h.checked(readiness['CPU_controller']))
    review_cfg=dict(unit='robotron-quality32-restored192lr125-firstsave-'+leg.lower()+'-independent-review-original01-20261023.service',
        output=str(directory/'independent-review-execution-original01'),
        argv=['/usr/bin/python3.12','-I','-B',readiness['leg_reviewer']['path'],'--observe','--job',rjp['path'],
            '--job-sha256',rjp['sha256'],'--expected-source-sha256',readiness['leg_reviewer']['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
            'TasksMax=256','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[cpu.pin(e['path'])for e in [*job['inputs'],jp,ap,cp,rjp]],observation_s=240)
    rcp=h.put(directory/'independent-review-controller-config.json',review_cfg);cpu.checked_config(rcp['path'])
    pre=h.put(directory/'original-leg-precommit.json',dict(schema='robotron-certified-quality32-original-leg-precommit-v1',
        quality_leg=leg,job=jp,acceptance=ap,controller_config=cp,review_job=rjp,
        independent_review_controller_config=rcp,launch_readiness=readiness_pin,
        original_attempt=1,no_retry=True,main_runtime_changed=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(prepared=True,leg=leg,precommit=pre,job=jp,controller_config=cp)),flush=True)
    return pre

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--readiness')
    parser.add_argument('--readiness-sha256');parser.add_argument('--leg');parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.prepare:print('PLAN_ONLY');return 0
    h=load('_quality_leg_preparation_helpers',B/'run_full_policy_startup_v3.py')
    require(h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1','Helper changed')
    require(h.pin(__file__)['sha256']==args.source_sha256,'Preparer source changed')
    pin=h.pin(args.readiness);require(pin['sha256']==args.readiness_sha256,'New readiness precommit changed')
    prepare(pin,args.leg,h);return 0

if __name__=='__main__':sys.exit(main())
