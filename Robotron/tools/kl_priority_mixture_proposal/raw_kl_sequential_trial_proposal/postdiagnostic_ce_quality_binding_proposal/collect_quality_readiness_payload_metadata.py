"""Root-only read-only postcapture quality runtime collection; default reads nothing.

Consumes closed original capture, b2e CPU and guard releases. Publishes fresh
baseline16, anchor8 and carrier readiness only; no capture, model, control, CPU,
unit launch or quality actions. Future inputs must be real immutable metadata.
"""
import argparse, errno, hashlib, importlib.util, json, os, re, sys, time
from pathlib import Path

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
Q=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
SELECTOR=Path(__file__).with_name('capture_candidate.py')
SELECTOR_SHA='e01a36c197c889d1994e72bee82a8622c8d7fad72477d6d0eaffef2c5e5aefbe'
BINDINGS=Path(__file__).with_name('quality_bindings_payload_metadata.py')
BINDINGS_SHA='e00c135d93ea83e0da23dd5b0a13e323f79023f0c3a111de4d2627bde1d13596'
QUERIES=RUN/'CE2048-trial02-first-LATCH-followup-readiness-collector-source-preparation-20261017/collect_readiness.py'
QUERY_SHA='9a8b4a20f090597f1ffad1a8c959c0cf886e3b119a17343857c7ce1d0f563f9b'
SCHEMA='robotron-postdiagnostic-live8M-quality-runtime-case-v1'
READY_SCHEMA='robotron-postdiagnostic-live8M-exclusive-readiness-v1'
ANCHOR=('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')
EVIDENCE=('capture_result','capture_release','phase_cpu_job','phase_cpu_report','phase_cpu_completion','CPU_execution','guard_release')


def require(value,message):
    if not value:raise RuntimeError(message)


def load(path,sha,name):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Pinned source changed: '+str(path))
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module)
    require(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Source changed during import');return module


def collect(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Collector source changed')
    C=load(SELECTOR,SELECTOR_SHA,'_postdiagnostic_quality_closed_capture')
    B=load(BINDINGS,BINDINGS_SHA,'_postdiagnostic_quality_metadata_bindings')
    require(C.fingerprint(SELECTOR)[1]['identity']['mode']==C.fingerprint(BINDINGS)[1]['identity']['mode']=='0o444',
        'Selected metadata sources must be sealed')
    require(args.case.suffix=='.json','Root case must be metadata JSON')
    _,case_pin=C.fingerprint(args.case)
    require(case_pin['sha256']==args.expected_case_sha256,'Root case SHA differs')
    case=B.read(case_pin)
    require(set(case)=={'schema',*EVIDENCE,'quality_unit','output_directory'} and case['schema']==SCHEMA and
        re.fullmatch('robotron-quality-[A-Za-z0-9_-]+',case['quality_unit'] or ''),'Exact closed-evidence root case required')
    out=args.output
    require(out==Path(case['output_directory']) and out.is_absolute() and out==out.resolve(strict=False) and
        out.parent==RUN and not out.exists(),'Fresh direct run26 observation output required')
    # Metadata validation precedes runtime queries or output creation. No model
    # descriptors are dereferenced; the numerical report remains the actual proof.
    require(all(isinstance(case[key],dict) and Path(case[key]['path']).suffix=='.json' for key in EVIDENCE),
        'Closed evidence must be metadata JSON, never model bodies')
    values={key:B.read(case[key]) for key in EVIDENCE}
    result=values['capture_result'];job=values['phase_cpu_job'];proof=values['phase_cpu_report'];completion=values['phase_cpu_completion']
    require(result['schema']=='robotron-postdiagnostic-live8M-candidate-result-v1' and
        result['status']=='CAPTURED_PENDING_ROOT_CPU' and result['CPU_executed'] is False and result['qualification_pass'] is False and
        result['control_changed'] is False and result['owner_actions'] is False and result['model_only'] is True and
        result['root_case']==result['root_precommit'] and result['cpu_job']==case['phase_cpu_job'],
        'Original successful model-only capture and exact CPU job required')
    original_case=B.read(result['root_case'])
    candidate=dict(tag=original_case['tag'],**B.triple(result['source']))
    B.check_root_capture(values['capture_release'],case['capture_result'],result['root_case'],original_case,B.archive_text)
    B.check_cpu(job,proof,completion,candidate)
    require(B.triple(proof['job_file'])==B.triple(case['phase_cpu_job']) and result['cpu_argv']==completion['argv'] and
        job['source']==result['source'] and job['verification_copy']==result['verification_copy'] and
        job['phase_snapshot']['acquisition']==result['acquisition'],'Original closed capture/CPU frozen tuple differs')
    B.check_CPU_release(values['CPU_execution'],case['phase_cpu_job'],case['phase_cpu_report'],case['phase_cpu_completion'],completion,
        B.read,B.archive_text,lambda pin:B.archived_bytes(pin,allow_empty=True))
    guard=values['guard_release']
    require(guard['original_exec_code']==1 and guard['original_exit']==0 and guard['original_result']=='success' and
        guard['original_archived_before_release'] is True and guard['unit_released'] is True and len(guard['owned_release'])==2,
        'Actual original metadata guard0 and owned release required')
    # Load only the original readonly IO/health/pure modules, not Snapshot,
    # numerical verifier, capture run() or the historically bound prepare().
    M=load(QUERIES,QUERY_SHA,'_postdiagnostic_quality_readonly_queries')
    modules={name:C.load(name) for name in ('entry','driver','ops','capture','observer')}
    entry,driver,ops,capture,observer=(modules[k] for k in ('entry','driver','ops','capture','observer'))
    files=capture.Files(ops);context=C.activation_context(original_case,files)
    activation=context['activation'];activation_pin=original_case['activation']['result'];adoption_pin=original_case['activation']['adoption']
    require(activation_pin['path']==str(B.ACTIVATION_RESULT) and activation_pin['sha256']==B.ACTIVATION_SHA and
        adoption_pin['path']==str(B.ACTIVATION_ADOPTION) and adoption_pin['sha256']==B.ADOPTION_SHA and
        result['current_phase']==context['phase']==dict(record=job['phase_snapshot']['phase_record'],
            boot_checkpoint=job['phase_snapshot']['boot_checkpoint'],boot_verification=job['phase_snapshot']['boot_verification'],
            expected=job['phase_snapshot']['expected_phase']) and result['owner']==context['owner']==job['phase_snapshot']['owner'],
        'Genuine completed current CE activation/phase/owner required')
    window=B.read(result['window_job']);outcome=B.read_raw(result['window_result'])
    event=B.read_raw(outcome['durability']['event']);receipt=B.read(outcome['durability']['durability'])
    _,window_current=B.check_window(original_case,dict(result,_experiment=job['experiment']),window,outcome,
        B.read_raw(window['baseline']['api']),event,receipt,observer)
    require(all(B.four(job['clock_floor'])[k]>=window_current['clocks'][k] for k in B.CLOCKS),
        'Original candidate CPU floor must cover the first durable LATCH')
    acquisition=B.read(result['acquisition']);slot_case=dict(completed_slot=acquisition['completed_slot_transition']['after']['actual_pin'])
    owner=context['owner'];binding=activation['healthy192']['binding'];saved=binding['bindings']
    activation_job=B.read(activation['root_job'])
    require(owner['pid']==2863379 and owner['starttime_ticks']==39797375 and
        owner['invocation_id']=='5a8bfc5e10674a8e9169978804378393' and
        context['phase']['record']['sha256']=='75ec8703405edfb250100006cab8ff44a364cbc84e33583697a985306fd21f10',
        'Exact completed current activation owner and phase required')
    out.mkdir(mode=0o700);ops.sync_directory(out.parent);obs=M.Observation(out)
    main_show=obs.show(owner['unit']);fleet_unit=activation_job['transition']['fleet_unit'];fleet_show=obs.show(fleet_unit)
    fleet=dict(unit=fleet_unit,pid=int(fleet_show['MainPID']),starttime_ticks=saved.get('supervisor_start_ticks',binding['supervisor_start_ticks']),
        invocation_id=fleet_show['InvocationID'],cgroup=fleet_show['ControlGroup'])
    require(fleet['pid']==int(binding['fleet']['MainPID']) and fleet['cgroup']==saved['fleet_cgroup'],
        'Fresh fleet must be the actual saved original supervisor')
    for o,s in ((owner,main_show),(fleet,fleet_show)):
        require(s['MainPID']==str(o['pid']) and s['InvocationID']==o['invocation_id'] and s['ControlGroup']==o['cgroup'] and
            s['ActiveState']=='active' and s['SubState']=='running' and s['NRestarts']=='0','Current owner/fleet unit changed')
    require(main_show['Restart']=='no','Main restart policy changed')
    def descriptor(identity,mask,group):
        return dict(pid=identity['pid'],starttime_ticks=identity['starttime_ticks'],uid=identity['uid'],
            argv=identity['cmdline'],cwd=identity['cwd'],exe=identity['exe'],mask=mask,cgroup=group)
    mask=activation_job['transition']['worker_mask'];main=descriptor(saved['worker']['trainer'],mask,owner['cgroup'])
    M.process(obs,owner,owner['cgroup'],main)
    fleet_process=dict(pid=fleet['pid'],starttime_ticks=fleet['starttime_ticks'],uid=[os.getuid()]*4,
        argv=['bash',str(GAME/'startmame.sh'),'192','novideo','nonaudio','--supervise','--socket-address','dell:9998'],
        cwd=str(GAME),exe='/usr/bin/bash',mask=mask,cgroup=fleet['cgroup'])
    M.process(obs,fleet,fleet['cgroup'],fleet_process)
    actors=[];actor_resources=[]
    for a in saved['actors']:
        amask=activation_job['transition']['actor_masks'][str(a['pid'])]
        actors.append(dict(pid=a['pid'],starttime_ticks=a['starttime_ticks'],slot=a['client_slot'],mask=amask))
        expected=descriptor(a,amask,fleet['cgroup']);M.process(obs,a,fleet['cgroup'],expected);actor_resources.append(expected)
    require(len(actors)==192 and len({a['pid'] for a in actors})==192 and {a['slot'] for a in actors}==set(range(192)),
        'Exact original192 actors/slots required')
    worker=dict(saved['worker']['thread'],mask=mask)
    env=dict(os.fsdecode(x).split('=',1) for x in M.proc_bytes(Path('/proc',str(owner['pid']),'environ'),1<<20).split(b'\0')
        if b'=' in x and os.fsdecode(x).startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_')))
    require(env==binding['environment'] and env['ROBOTRON_REJECTED_GAP_TELEMETRY']=='1',
        'Current selected diagnostic environment changed from genuine READY')
    B.check_diagnostic_sources(saved['source_hashes'],env)
    env_pin=obs.publish('actual-selected-environment.json',env)
    resources=dict(owner=owner,main=main,fleet=fleet_process,worker=worker,actors=actor_resources,main_unit=owner['unit'],fleet_unit=fleet_unit)
    resource_pin=obs.publish('actual-main192-resources.json',resources)
    fleet_pin=obs.publish('actual-fleet-descriptor.json',dict(owner=fleet,process=fleet_process))
    raw,api=driver.Driver.api(None);api_pin=obs.write('actual-main-API-before.raw.json',raw)
    require(all(api['host_pipeline']['learning_exposure'][kind]['process_id']==owner['pid'] for kind in ('optimizer','replay')),
        'Fresh API exposure must belong to actual current owner')
    origin=observer.normalise(B.read_raw(window['baseline']['api']));current=observer.normalise(api)
    require(all(current[k]==origin[k] for k in ('optimizer_identity','replay_identity')),'Original B optimizer/replay epochs changed')
    unit_files={path:sha for group in binding['unit_files'].values() for path,sha in group.items()}
    baseline=dict(main_owner=owner,fleet_owner=fleet,inference_worker=worker,actors=actors,
        source_hashes=saved['source_hashes'],control_hashes=saved['control_hashes'],unit_files=unit_files,
        environment_sha256=hashlib.sha256(json.dumps(env,sort_keys=True).encode()).hexdigest(),status='PASS',
        schema='robotron-current-main192-runtime-baseline-v1',observed_unix_s=time.time(),actual_main192_resources=resource_pin,
        actual_API=api_pin,actual_selected_environment=env_pin,actual_fleet_descriptor=fleet_pin,actual_activation=activation_pin)
    require(len(baseline)==16 and len(baseline['source_hashes'])==62 and len(baseline['control_hashes'])==2 and len(unit_files)==3 and
        baseline['source_hashes'][str(GAME/'Scripts/dqn/socket_server.py')]==B.EVALUATOR['Scripts/dqn/socket_server.py'],
        'Exact current baseline16/source62/control2/unit3/diagnostic socket required')
    floor={k:max(context['historical_floor'][k],B.four(proof['clocks'])[k]) for k in B.CLOCKS}
    health=entry.EntryHealth(driver,ops,files,observer,baseline,owner,env,resources,floor)
    control_path=GAME/'models_dqn/learning_control.json';control_raw,control_pin=C.fingerprint(control_path);control=json.loads(control_raw)
    require(control_pin['sha256']==original_case['control_before']['sha256'] and control['lr_scale']==.5 and
        control.get('measurement') is None and control['experiment']==job['experiment'],'Original unchanged .5 control required')
    health.check_health(control['experiment'],2.5e-5);entry.slot_guard(slot_case,files)
    blocked=set(M.BLOCKED)|{'capture_candidate.py','capture_entry.py','run_hot_window.py','run_forward_recovery.py',
        'run_healthy_ce_maintenance.py','verify_phase_snapshot_lr25.py','sequence_leg_audit.py','sequence_R1_audit.py',
        'root_quality_carrier.py','collect_quality_readiness.py','run_healthy_activation.py','benchmark_cost.py'}
    competing=[];private=[];global_actors=set()
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal() or int(p.name)==os.getpid():continue
        try:argv=[os.fsdecode(x) for x in M.proc_bytes(p/'cmdline').split(b'\0') if x];group=M.proc_bytes(p/'cgroup').decode()
        except OSError as e:
            if e.errno in (errno.ENOENT,errno.ESRCH):continue
            raise
        if any(os.path.basename(a) in blocked for a in argv):competing.append(dict(pid=int(p.name),argv=argv))
        if 'robotron-snapshot-smoke-' in group or any('/dev/shm/robotron-snapshot-smoke-' in a for a in argv):private.append(int(p.name))
        if argv and os.path.basename(argv[0])=='mame' and 'robotron' in argv:global_actors.add(int(p.name))
    obs.publish('actual-global-process-scan.json',dict(competing=competing,private=private,robotron_actors=sorted(global_actors)))
    require(not competing and not private and global_actors=={a['pid'] for a in actors},'Helper/private/global actor inventory differs')
    app=(Path('/sys/fs/cgroup')/owner['cgroup'].lstrip('/')).parent
    groups=[M.cgroup_empty('/'+str(p.relative_to('/sys/fs/cgroup'))) for p in app.glob('robotron-snapshot-smoke-*')]
    # Fresh absence is scoped to the three current owned originals. Earlier
    # failures/releases remain historical metadata in the sealed capture lineage.
    release_pins=[case['capture_release'],values['CPU_execution']['release_receipt'],case['guard_release']]
    absences=[];units=set()
    for release_evidence in release_pins:
        value=B.read(release_evidence)
        require(value['original_archived_before_release'] is True and value['unit_released'] is True and
            len(value['owned_release'])==2,'Actual archived owned release required')
        previous=value['original'];observed=M.process_start(previous['pid'])
        require(type(previous['starttime_ticks']) is int and previous['starttime_ticks']>0 and
            observed!=previous['starttime_ticks'],'Released original helper process remains or identity missing')
        absences.append(dict(pid=previous['pid'],expected_start=previous['starttime_ticks'],observed_start=observed))
        for item in value['owned_release']:
            unit=item['unit'];require(unit.endswith(('.service','.timer')) and unit not in (owner['unit'],fleet_unit),'Invalid absence target')
            units.add(unit)
    units.update((case['quality_unit']+'.service',case['quality_unit']+'.timer'))
    for unit in sorted(units):
        require(obs.show(unit)['LoadState']=='not-found','Owned helper/quality unit retained or live: '+unit)
        if unit.endswith('.service'):M.cgroup_empty(str(Path(owner['cgroup']).parent/unit))
    obs.publish('actual-owned-release-and-cgroup-checks.json',dict(releases=release_pins,original_absences=absences,
        private_cgroups=groups,units_not_found=sorted(units)))
    gpu=obs.call(['nvidia-smi','--query-gpu=index,uuid','--format=csv,noheader,nounits'])
    memory=obs.call(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'])
    require(gpu['returncode']==memory['returncode']==0,'GPU observation failed')
    require({int(a.strip()):b.strip() for a,b in (line.split(',') for line in gpu['stdout'].splitlines() if line.strip())}==M.GPU_UUIDS,'Actual GPU index/UUID map changed')
    free={a.strip():int(b.strip())*(1<<20) for a,b in (line.split(',') for line in memory['stdout'].splitlines() if line.strip())}
    fresh_raw,fresh_api=health.check_health(control['experiment'],2.5e-5);entry.slot_guard(slot_case,files)
    require(all(fresh_api['host_pipeline']['learning_exposure'][kind]['process_id']==owner['pid'] for kind in ('optimizer','replay')) and
        all(B.four(fresh_api)[k]>=B.four(proof['clocks'])[k] for k in B.CLOCKS) and
        B.finite(fresh_api['ts'])>=case['phase_cpu_report']['identity']['mtime_ns']/1e9,'Final API must be genuine postCPU same-owner/clocks')
    require(free[M.GPU_UUIDS[0]]>=14*(1<<30),'GPU0 memory below14GiB')
    for unit in sorted(units):require(obs.show(unit)['LoadState']=='not-found','Owned unit changed during final bracket: '+unit)
    fresh_pin=obs.write('actual-main-API.raw.json',fresh_raw)
    require(fresh_pin['identity']['mtime_ns']>=case['phase_cpu_report']['identity']['mtime_ns'],'Fresh API archive predates CPU report')
    baseline.update(actual_API=fresh_pin,observed_unix_s=time.time())
    baseline_pin=obs.publish('runtime-baseline.json',baseline)
    anchor={k:baseline[k] for k in ANCHOR};anchor_pin=obs.publish('runtime-anchor.json',anchor)
    readiness=dict(schema=READY_SCHEMA,status='PASS',observed_unix_s=time.time(),**anchor,
        candidate=dict(source=candidate['path'],sha256=candidate['sha256'],bytes=candidate['bytes'],
            root_job_sha256=case['phase_cpu_job']['sha256'],cpu_proof_sha256=case['phase_cpu_report']['sha256']),
        resources=dict(gpu0_uuid=M.GPU_UUIDS[0],gpu1_uuid=M.GPU_UUIDS[1],GPU0_free_bytes=free[M.GPU_UUIDS[0]],
            GPU0_no_compute_owner=True,GPU1_main_only=True,port9999_clear=True,lease_free=True,no_competing_helpers=True,
            no_private_cgroup_tmpfs_processes=True,no_pending_save=True,capture_and_CPU_units_released=True,
            commands_UID_cwd_exe_checked=True,held_environment_checked=True,unit_files_checked=True),release_evidence=release_pins)
    ready_pin=obs.publish('runtime-readiness.json',readiness)
    result_pin=obs.publish('collection-result.json',dict(status='PASS_FRESH_CURRENT_QUALITY_RUNTIME',root_case=case_pin,
        baseline=baseline_pin,anchor=anchor_pin,readiness=ready_pin,candidate=candidate,current_phase=context['phase'],
        capture_or_request_started=False,CPU_executed=False,control_changed=False,unit_actions=False,quality_started=False,
        model_or_replay_referents_accessed=False))
    print(json.dumps(dict(status='PASS',result=result_pin,baseline=baseline_pin,anchor=anchor_pin,readiness=ready_pin),allow_nan=False))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--expected-source-sha256');p.add_argument('--case',type=Path);p.add_argument('--expected-case-sha256');p.add_argument('--output',type=Path)
    args=p.parse_args(argv)
    if not args.execute:print('PLAN_ONLY: no reads/imports/runtime/outputs/capture/CPU/control/unit/quality actions');return 0
    require(args.expected_source_sha256 and args.case and args.expected_case_sha256 and args.output,'Explicit pinned case/source/new output required')
    collect(args);return 0


if __name__=='__main__':raise SystemExit(main())
