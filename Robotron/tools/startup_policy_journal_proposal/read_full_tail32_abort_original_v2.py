"""Preserve the failed original full-tail32 and independently inspect closure.

This does not rescue a partial cohort, fill unknown exits, relaunch, repair,
signal or change the trainer. Default invocation has no runtime side effects.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
D=R/'compiled32-policy-full-tail-real-original01-preparation-20261022'


def require(value,message):
    if not value:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--observe',action='store_true')
    if not parser.parse_args().observe:print('PLAN_ONLY: no original observation or outputs');return 0
    helper=R/'quality32-reference1597-vs-production1741-original01-preparation-20261021/winner-protection-original01-preparation-20261022/readback-original-final-disposition-v1.py'
    require(hashlib.sha256(helper.read_bytes()).hexdigest()=='bae9e9c3e5eb552322285dc2422d5edd95549273aef58125e187f2305085fcdf','Helper changed')
    spec=importlib.util.spec_from_file_location('_abort_original_helpers',helper)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    put=lambda p,v:m.put(p,(json.dumps(v,indent=2,allow_nan=False)+'\n').encode())
    output=D/'original-full-tail32-invalid-output-drift-and-postexit-closure-readback-v2.json'
    require(not output.exists(),'Original abort readback already consumed')
    intent=put(D/'original-abort-readback-v2-intent.json',dict(source=m.pin(__file__),original_attempt=1,no_retry=True,observed_unix_s=time.time()))
    rd=m.load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','_abort_original_reader')
    rt=m.load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_abort_original_native_closure')
    ctl=m.load(G/'tools/startup_policy_journal_proposal/control_compiled_full_tail32_v1.py',
        '163d0860b4ec7ed6ec21e484502aa6a4602de6530c216031b3088a08b23d7dfd','_abort_original_control')
    read=lambda entry,as_json=True:rd.read_pin(entry,as_json=as_json)
    jp=m.pin(D/'job.json');require(jp['sha256']=='8089988cb3d98946de3751ed73e8829a7f25b8fbae145bd6ad957faca15fe786','Original job changed')
    job=read(jp);cp=m.pin(D/'controller-original-result.json');controller=read(cp)
    op=m.pin(D/'execution-original01/root-original-identity.json');owner=read(op)
    require(controller['actual_exit']==1 and controller['original_attempt']==1 and controller['no_retry']is True,
            'Failed original controller outcome changed')
    closure=read(controller['closure']);fields=rt.archived_closure(closure,owner,read,exit_zero=False)
    require(fields['ExecMainStatus']=='1'and fields['ExecMainCode']=='1'
        and fields['MemoryMax']==str(16<<30)and fields['MemorySwapMax']=='0'
        and rt.duration_seconds(fields['CPUQuotaPerSecUSec'])==12
        and rt.duration_seconds(fields['RuntimeMaxUSec'])==9660
        and fields['TasksMax']=='512'and rt.duration_seconds(fields['TimeoutStopUSec'])==30
        and fields['KillMode']=='mixed'and fields['SendSIGKILL']=='no'and fields['Restart']=='no',
        'Actual original nonzero exit or resource scope differs')
    require(not Path('/proc',str(owner['pid'])).exists(),'Original native still exists')
    for unit in (owner['unit'],owner['timer']):
        require(ctl.show(unit)['LoadState']=='not-found','Owned original unit remains')
        require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists(),
                'Original cgroup remains')
    rp=m.pin(Path(job['output'])/'result.json');result=read(rp)
    require(result['complete']is False and result['status']=='ORIGINAL_COMPILED_FULL_TAIL32_INVALID_NO_RETRY'
        and result['original_lease_released']is False and result['immutable_inputs_unchanged']is True
        and result['errors'][0]=="Original independent main-health watch: ValueError('Initial observation must preserve all precommitted births')",
        'Original invalid cause or cleanup uncertainty changed')
    cohort=result['after_intentional_stop']
    require([cohort[k]for k in ('started','count','pending','abandoned')]==[32,1,0,31]
        and result['controller_exit']['valid']is False
        and result['controller_exit']['reason']=='controller_exit_before_cohort_complete',
        'Original incomplete cohort was rescued or filtered')
    require(set(result['original_slots'])=={str(s)for s in range(4096,4128)},'All32 original actor records required')
    actors=[];output_drift=[]
    for slot,entry in result['original_slots'].items():
        require(entry['actual_exit']is None and not Path('/proc',str(entry['pid'])).exists(),
                'Original unknown actor exit must remain unknown; current birth must be absent')
        for name,file in entry['files'].items():
            current=m.pin(file['path'])
            require(all(current['identity'][k]==file['identity'][k]for k in ('device','inode','mode','uid','nlink')),
                    'Original output object was replaced or changed ownership')
            if current!=file:
                captured=m.put(D/('postexit-current-'+slot+'-'+name),read(current,False))
                output_drift.append(dict(slot=int(slot),file=name,original_result_receipt=file,
                    current_stable_observation=current,current_bytes_capture=captured,
                    original_receipt_invalid=True,original_receipt_not_rewritten=True))
            else:read(file,False)
        actors.append(dict(slot=int(slot),pid=entry['pid'],birth=entry['birth'],
                           original_individual_exit=None,current_original_birth_absent=True))
    for entry in job['inputs']+[result['acquired_checkpoint']]:require(m.pin(entry['path'])==entry,'Original input changed')
    package=read(job['source_package'])
    require(len(package['files'])==123,'Exact selected package required')
    for relative,sha in package['files'].items():
        require(m.pin(Path(package['root'])/relative)['sha256']==sha,'Private package changed')
    for pin in result['journal'].values():read(pin,False)
    lease=job['lease'];require(m.pin(lease['path'])==lease,'Persistent coordinator changed')
    import fcntl
    fd=os.open(lease['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    require(m.pin(lease['path'])==lease,'Coordinator probe changed original identity')
    for port in [19998,*range(20000,20032)]:
        with socket.socket()as probe:probe.bind(('127.0.0.1',port))
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],
                       capture_output=True,text=True,timeout=10)
    require(gpu.returncode==0 and job['gpu_uuid']not in gpu.stdout,'Private GPU0 remains occupied')
    observation=read(m.pin(D/'post-abort-main-readonly-observation/current-main192-identity-change-readback.json'))
    require(observation['changed_count']==1 and observation['changed_slots'][0]['slot']==51
        and observation['all192_current_slots_present']is True
        and observation['trainer_and_fleet_owners_unchanged']is True
        and observation['all196_held_source_hashes_unchanged']is True,'Current main event evidence differs')
    captures={}
    for name,path in [('main-slot51-log',G/'logs/mame_instance_51.log'),('main-fleet-log',R/'fleet.log')]:
        raw=path.read_bytes();require(raw.endswith(b'\n'),'Main log prefix incomplete')
        captures[name]=m.put(D/(name+'-post-abort-prefix-capture.txt'),raw)
    actor_log=read(captures['main-slot51-log'],False).decode()
    fleet_log=read(captures['main-fleet-log'],False).decode()
    require('[STALL WATCHDOG] score frozen at 131175 for 180s - exiting for supervisor respawn'in actor_log
        and '[SUPERVISOR] 08:36:15 respawned client 51 (PID 2893221, crash 1/5 in window)'in fleet_log,
        'Existing watchdog and exact fleet respawn provenance missing')
    require('torch'not in sys.modules,'Passive closure audit imported numerical runtime')
    proof=put(output,dict(schema='robotron-original-full-tail32-invalid-preserved-and-current-closure-v1',
        status='INVALID_ORIGINAL_AND_OUTPUT_RECEIPT_DRIFT_PRESERVED_POSTEXIT_RESOURCES_NOW_ABSENT',source=m.pin(__file__),intent=intent,
        job=jp,original_controller_result=cp,original_owner=op,original_closure=controller['closure'],original_result=rp,
        actual_native_exit=1,actual_controller_exit=1,all6_original_descriptors_verified=True,
        original_output_receipts_valid=False,original_post_snapshot_output_drift=output_drift,
        original_output_drift_count=len(output_drift),
        earlier_abort_reader_rejection_preserved=m.pin(D/'original-abort-reader-v1-failure-preserved.json'),
        actual_descriptor_exits=[r['exit']for r in closure['full_original_archives']],
        original_invalid_reason=result['errors'][0],original_counts={k:cohort[k]for k in ('started','count','pending','abandoned')},
        original_individual_actor_exits_remain_unknown=actors,original_explicit_lease_release_remains_false=True,
        supplemental_current_all32_births_native_unit_timer_cgroup_ports_GPU_absent=True,
        persistent_empty_coordinator_original_identity_unchanged_and_currently_unheld=True,
        current_flock_release_is_implicit_process_exit_not_original_explicit_release=True,
        all71_original_inputs_and123_package_sources_unchanged=True,
        main_event_observation=m.pin(D/'post-abort-main-readonly-observation/current-main192-identity-change-readback.json'),
        main_logs_appendable_prefix_captures=captures,existing_main_watchdog_and_fleet_respawn_verified=True,
        agent_did_not_restart_or_signal_main=True,prior_main_interruption_duration_unknown=True,
        completed_partial_game_excluded_from_quality_and_reference=True,quality_qualified=False,
        full_game_score_verified=False,promotion=False,learning_speed_gain_verified=False,
        retry_or_old_scientific_reader_rerun=False,observed_unix_s=time.time(),
        next='Keep this original invalid. Verify current main stability, then new explicit runtime version/cleanup/failure capture and fresh main bindings for a distinctly precommitted engineering case. Never rescue this cohort or rewrite unknown exits.'))
    print(json.dumps(dict(readback=proof,original_invalid=True,private_resources_now_closed=True)),flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
