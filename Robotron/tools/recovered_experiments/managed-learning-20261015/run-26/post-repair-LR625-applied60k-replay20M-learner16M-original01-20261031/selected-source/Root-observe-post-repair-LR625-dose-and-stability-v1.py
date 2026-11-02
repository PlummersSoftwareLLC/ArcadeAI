"""Root-only45s post-repair learning observer. Default-inert; no training actions.

API snapshots are cached/non-atomic. Existing CUDA diagnostics are latest sampled
stream spans, not interval GPU occupancy. Root owns CONTROL exclusively before
--execute; phase/anchor guards and byte-CAS prevent stale intentional handoffs.
"""
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import time
import urllib.request

R=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CASE=R/'logs/managed-learning-20261015/run-26/post-repair-LR625-applied60k-replay20M-learner16M-original01-20261031'
PHASE=CASE.name
ANALYZER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-repair-LR625-applied60k-replay20M-learner16M-original01-20261031/selected-source/analyze_post_repair_LR625_dose_v1.py', 'sha256': '97892ebc720f0ed0a459d02476eb13a84b6883e62d4de0563aa89a179b221259', 'bytes': 7929, 'identity': {'device': 2304, 'inode': 82735790, 'bytes': 7929, 'mtime_ns': 1793481294919624556, 'ctime_ns': 1793481294919624556, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
ANALYZER_SHA=ANALYZER['sha256']
CONTROL_SHA='3b1a46f7de088698487877ff30171f7dbe1c9d289f39778065a16e85b48a5521'
SERVER_SHA='1692ee2dbfb6f83d0f50234ee1eb30d0cf6bbe45d670a5a9fb52992fd92b56fc'
INTERVAL=45.0
SYSTEM_FIELDS=('cpu_util','cpu_count','cpu_load_1m','cpu_load_5m','cpu_load_15m',
    'ram_total_mib','ram_available_mib','ram_free_mib','ram_used_mib','ram_free_pct')


def require(value, reason):
    if not value:raise ValueError(reason)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def snapshot(path,immutable=True,limit=2<<20):
    path=Path(path);before=path.lstat()
    require(path.is_absolute() and path.resolve()==path and stat.S_ISREG(before.st_mode)
        and before.st_uid==os.getuid() and before.st_nlink==1 and 0<before.st_size<=limit
        and (not immutable or stat.S_IMODE(before.st_mode)==0o444),'Bounded canonical selected file required')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb')as stream:
        require(identity(os.fstat(stream.fileno()))==identity(before),'Opened different file')
        raw=stream.read(limit+1)
        require(identity(os.fstat(stream.fileno()))==identity(before)==identity(path.lstat())
            and len(raw)==before.st_size,'Selected file changed')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before)),raw


def selected(entry):
    pin,raw=snapshot(entry['path']);require(pin==entry,'Selected full8 differs');return raw


def write(path,value,replace=False,raw=None):
    payload=raw if raw is not None else (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    temp=path.with_name('.'+path.name+'.'+str(os.getpid())+'.tmp')if replace else path
    with temp.open('xb')as stream:
        stream.write(payload);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    if replace:os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(path=str(path),sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload))


def process_birth(pid):
    text=Path('/proc',str(pid),'stat').read_text()
    return int(text.rsplit(')',1)[1].split()[19])


def owner(expected):
    command=['systemctl','--user','show',expected['unit'],'--property=Id,MainPID,Type,ActiveState,SubState,Restart,NRestarts,InvocationID,ControlGroup']
    done=subprocess.run(command,capture_output=True,text=True,timeout=8)
    require(done.returncode==0,'Owner query failed')
    show=dict(x.split('=',1)for x in done.stdout.splitlines()if'='in x)
    wanted=dict(Id=expected['unit'],MainPID=str(expected['pid']),Type='exec',ActiveState='active',
        SubState='running',Restart='no',NRestarts='0',InvocationID=expected['invocation_id'],ControlGroup=expected['cgroup'])
    require(all(show.get(k)==v for k,v in wanted.items())and process_birth(expected['pid'])==expected['birth']
        and Path('/proc',str(expected['pid']),'cgroup').read_text().splitlines()==['0::'+expected['cgroup']],
        'Original Main/fleet owner changed; review')
    return dict(owner={k:expected[k]for k in ('pid','birth','unit','invocation_id','cgroup')},unit_fields=show)


def project_anchor(entry,module):
    summary=json.loads(selected(entry))
    require(summary['schema']=='robotron-root-post-repair-LR625-applied-replay-learner-dose-anchor-v1'
        and summary['experiment']==PHASE and {k:summary['trainer'][k]for k in ('pid','birth')}==module.OWNER
        and summary['control']['sha256']==CONTROL_SHA and summary['targets']==module.TARGETS,'Wrong actual anchor')
    # Root execution reads the selected sealed API, never a mutable/live baseline.
    api=json.loads(selected(summary['API']));e=api['host_pipeline']['learning_exposure'];base=module.counters(api)
    require({k:{name:e[k][name]for name in module.IDS}for k in ('optimizer','replay')}==summary['exposure_instances']
        and base['attempted']==base['outcomes'] and base['unavailable']==0
        and (base['applied'],base['attempted'],base['skipped'],base['replay'],base['learner_frames'])==tuple(summary['anchor'][k]for k in
            ('applied_updates','optimizer_attempts','AMP_skipped','replay_additions','learner_frames'))
        and api['ts']==summary['observation_API_unix_s'],'Anchor accounting/source join differs')
    policy=summary['policy']
    require(policy['actual_lr']==6.25e-6 and policy['lr_scale']==.125 and policy['manual_expert_pct']==-1
        and policy['effective_expert']==policy['epsilon']==.1 and policy['batch_size']==4096
        and policy['max_samples_per_frame']==8 and policy['n_step']==3 and policy['priority_metric']=='ce',
        'Wrong anchor recipe')
    anchor=dict(schema='robotron-post-repair-LR625-dose-anchor-v1',main_owner=module.OWNER,
        expected_lr=6.25e-6,expected_expert=.1,expected_epsilon=.1,control_sha256=CONTROL_SHA,
        observed_unix_s=summary['observed_unix_s'],api_ts=api['ts'],base=base,targets=dict(module.TARGETS),
        optimizer_identity=summary['exposure_instances']['optimizer'],replay_identity=summary['exposure_instances']['replay'])
    return summary,anchor


def phase_page(path,anchor_ref):
    _,raw=snapshot(path,immutable=False);page=json.loads(raw);trial=page['next_work']['learning_trial']
    require(trial.get('trial_id')==PHASE and type(trial.get('raw_anchor'))is dict
        and all(trial['raw_anchor'].get(k)==anchor_ref[k]for k in ('path','sha256')),
        'CONTROL phase/anchor ownership changed')
    return page,raw


def get(route,path):
    with urllib.request.urlopen('http://127.0.0.1:8771/api/'+route,timeout=8)as response:
        raw=response.read((2<<20)+1)
    write(path,None,raw=raw)  # Preserve original response before JSON/health validation.
    require(len(raw)<=2<<20,'API response exceeds bound');return json.loads(raw)


def mapping(value):
    return value if type(value) is dict else {}

def cell(value):
    require(value is None or type(value) in (str, bool, int, float), 'Scalar telemetry required')
    require(type(value) is not float or math.isfinite(value), 'Finite telemetry required')
    return '' if value is None else value

def bank_projection(index, analysis, sample):
    require(analysis.get('status') in ('VALID', 'PENDING', 'REJECTED')
            and analysis.get('source_sha256') == ANALYZER_SHA, 'Exact saved analyzer result required')
    require(sample.get('schema') == 'robotron-Root-post-repair-LR625-dose-observation-v1', 'Exact saved sample schema required')
    observed = analysis.get('observed_unix_s')
    require(type(observed) in (int, float) and observed > 0 and observed == sample.get('observed_unix_s'), 'Observation time join failed')
    api = mapping(sample.get('api_now')); bank = mapping(api.get('bank_persistence'))
    output = mapping(bank.get('output')); totals = mapping(output.get('totals'))
    dirty = mapping(bank.get('dirty')); delta = mapping(analysis.get('deltas'))
    row = dict(index=index, observed_unix_s=observed, API_ts=cell(api.get('ts')), status=analysis['status'],
               applied_updates_delta_from_anchor=cell(delta.get('applied_updates')), replay_additions_delta_from_anchor=cell(delta.get('replay_additions')),
               learner_frames_delta_from_anchor=cell(delta.get('learner_frames')), Main_FPS=cell(analysis.get('Main_FPS', api.get('fps'))),
               Main_loss=cell(analysis.get('Main_loss', api.get('loss'))), Main_grad_norm=cell(analysis.get('Main_grad_norm', api.get('grad_norm'))))
    for name in ('writer_active', 'capture_attempts', 'capture_deferrals', 'writes', 'write_failures',
                 'write_duration_s', 'last_write_duration_s', 'last_error'):
        suffix = '_total' if name in ('capture_attempts', 'capture_deferrals', 'writes', 'write_failures', 'write_duration_s') else ''
        row['bank_' + name + suffix] = cell(bank.get(name))
    row['bank_snapshot_lock_max_ms_lifetime'] = cell(bank.get('snapshot_lock_max_ms'))
    row.update(bank_dirty_hof=cell(dirty.get('hof')), bank_dirty_ephof=cell(dirty.get('ephof')),
               bank_output_backend=cell(output.get('backend')), bank_stream_output_enabled=cell(output.get('stream_output_enabled')),
               bank_output_schema=cell(output.get('schema')),
               bank_output_available=cell(output.get('available')),
               bank_output_active_json=(json.dumps(output['active'], separators=(',', ':'), allow_nan=False) if 'active' in output else ''),
               bank_API_read_error=cell(api.get('bank_persistence_read_error')),
               pipeline_read_error=cell(api.get('pipeline_read_error')), pipeline_snapshot_age_s=cell(api.get('pipeline_snapshot_age_s')))
    for phase, names in [('write', ('count', 'errors', 'host_total_ms', 'host_max_ms', 'payload_bytes', 'logical_bytes')),
                         ('file_fsync', ('count', 'errors', 'host_total_ms', 'host_max_ms'))]:
        for name in names:
            row['bank_field_' + phase + '_' + name + '_cumulative'] = cell(mapping(totals.get(phase)).get(name))
    policy = mapping(sample.get('continuous_policy')); stamp = policy.get('observed_monotonic_ns')
    recent = output.get('recent'); ended = []
    if type(recent) is list:
        ended = [event['ended_monotonic_ns'] for event in recent if type(event) is dict
                 and type(event.get('ended_monotonic_ns')) is int and event['ended_monotonic_ns'] > 0]
    row['bank_last_output_age_s_at_policy_observation'] = ''
    row['bank_last_output_age_reference_monotonic_ns'] = ''
    row['bank_last_output_age_reason'] = 'No saved policy monotonic timestamp'
    owner = mapping(sample.get('observed_main_owner')); policy_owner = mapping(policy.get('server_stamp'))
    row['observed_main_pid'] = cell(owner.get('pid'))
    row['observed_main_birth'] = cell(owner.get('birth'))
    row['bank_output_started_monotonic_ns'] = cell(output.get('started_monotonic_ns'))
    same_owner = all(type(owner.get(k)) is int and owner[k] > 0 and owner[k] == policy_owner.get(k) for k in ('pid', 'birth'))
    start = output.get('started_monotonic_ns')
    if type(stamp) is int and stamp > 0 and same_owner:
        row['bank_last_output_age_reference_monotonic_ns'] = stamp
        row['bank_last_output_age_reason'] = 'No retained completed field phase'
        if ended and type(start) is int and 0 < start <= max(ended) <= stamp:
            row['bank_last_output_age_s_at_policy_observation'] = (stamp - max(ended)) / 1e9
            row['bank_last_output_age_reason'] = 'Saved same-Main policy reference; includes cache/call skew'
        elif ended:
            row['bank_last_output_age_reason'] = 'Inconsistent or missing monotonic lineage; age unavailable'
    elif type(stamp) is int and stamp > 0:
        row['bank_last_output_age_reason'] = 'Policy/Main owner differs; age unavailable'
    for name in SYSTEM_FIELDS: row[name] = cell(api.get(name))
    return row


def row(index,analysis,sample):
    api=sample['api_now'];out=bank_projection(index,analysis,sample)
    out.update(reason=analysis['reason'],all_reached=analysis['all_reached'],elapsed_s=analysis.get('elapsed_s'),
        estimated_dose_remaining_s=analysis.get('estimated_remaining_s'),Main_clients=api.get('client_count'))
    for group in ('deltas','remaining','rates_per_s'):
        for name in ('applied_updates','replay_additions','learner_frames'):out[group+'_'+name]=analysis.get(group,{}).get(name)
    e=mapping(mapping(api.get('host_pipeline')).get('learning_exposure'))
    for family in ('optimizer','replay'):
        data=mapping(e.get(family))
        for name in ('process_id','instance_monotonic_ns','epoch','epoch_reason','available'):out[family+'_'+name]=data.get(name)
    opt=mapping(e.get('optimizer')); replay=mapping(e.get('replay'))
    for name in ('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable'):out['optimizer_'+name+'_total']=mapping(opt.get('total')).get(name)
    out['optimizer_unclassified_started_total']=opt.get('unclassified_started_total')
    for name in ('accepted_total','accepted_learner_total'):out['replay_'+name]=replay.get(name)
    for name in ('dqn','epsilon','expert','eval','unattributed'):out['replay_'+name+'_total']=mapping(replay.get('accepted_by_source_total')).get(name)
    for name in ('frame_count','learner_frame_count','training_steps','optimized_samples','fps','steps_per_sec','client_count','lr',
        'epsilon','expert_ratio','loss','grad_norm','bc_loss','q_mean','q_min','q_max','sample_dqn_frac','sample_epsilon_frac',
        'sample_expert_frac','avg_inf_ms','train_sample_ms','train_transfer_ms','train_compute_ms','train_priority_ms','train_step_ms'):
        out[name]=api.get(name)
    out['actual_expert_pct']=mapping(api.get('game_settings')).get('expert_pct')
    for name in ('below_support_mass','above_support_mass','edge_atom_mass','target_entropy','action_q_gap','categorical_kl'):
        out['c51_'+name]=mapping(api.get('c51_diagnostics')).get(name)
    for device in (0,1):
        for name in ('present','name','util','mem_util','power_w','temp_c'):out['gpu'+str(device)+'_'+name]=api.get('gpu'+str(device)+'_'+name)
    gpu=mapping(api.get('train_gpu_compute_diagnostic'));available=gpu.get('available')is True
    out['train_gpu_compute_available']=available
    for name in ('elapsed_ms','sample_count','logical_training_step','observed_unix_s','device'):
        out['train_gpu_compute_'+name]=gpu.get(name)if available else None
    stamp=out['train_gpu_compute_observed_unix_s']
    out['train_gpu_compute_age_s_at_Root_observation']=sample['observed_unix_s']-stamp if type(stamp)in(int,float)else None
    out['c51_diagnostics_json']=json.dumps(api.get('c51_diagnostics'),separators=(',',':'))
    out['bank_persistence_json']=json.dumps(api.get('bank_persistence'),separators=(',',':'))
    out['control_sha256']=sample['observed_control_sha256']
    return out


def update_control(path,page,old,anchor,anchor_ref,analysis,reference,api):
    work=page['next_work'];trial=work['learning_trial'];status=analysis['status']
    reached=status=='VALID'and analysis['all_reached'];estimate=analysis.get('estimated_remaining_s')
    trial.update(status='dose_reached'if reached else'collecting_dose'if status=='VALID'else'pending'if status=='PENDING'else'requires_review',
        raw_anchor=anchor_ref,targets=anchor['targets'],deltas=analysis.get('deltas'),remaining=analysis.get('remaining'),
        estimated_dose_remaining_s=estimate,expected_lr=6.25e-6,expected_expert=.1,expected_epsilon=.1,expected_expert_pct=-1)
    if status=='VALID':
        d=analysis['deltas'];left=analysis['remaining']
        stage=('Training dose reached; waiting for Root review'if reached else
            f"Training at LR 6.25e-6 · {d['applied_updates']:,}/60,000 applied updates · {d['replay_additions']/1e6:.2f}/20M replay · {d['learner_frames']/1e6:.2f}/16M learner frames")
        waiting=('Root reviews the dose and health, then selects a policy checkpoint and CPU verification.'if reached else
            f"All three thresholds: {left['applied_updates']:,} more applied updates, {left['replay_additions']/1e6:.2f}M replay additions and {left['learner_frames']/1e6:.2f}M learner frames.")
    else:stage='Training observation '+('pending'if status=='PENDING'else'requires review');waiting=analysis['reason']
    work.update(state='learning_dose_reached_waiting_policy'if reached else'learning_dose_collecting'if status=='VALID'else'learning_dose_observation_pending'if status=='PENDING'else'learning_dose_needs_review',
        current_stage=stage,waiting_for=waiting,
        detail='The repaired Main is training at LR 6.25e-6, automatic expert assistance at 10% and epsilon 10%. Accumulate all 60,000 applied updates, 20M replay additions and 16M learner frames before reviewing a new frozen policy.',
        next_stage='Root reviews health and dose, then saves and CPU-verifies a policy before selecting fresh score tests. No automatic save or test launch.',
        eta=('Training dose reached; later checkpoint and quality-test time is excluded.'if reached else'Waiting for enough fresh measured progress to estimate the dose.'if estimate is None else f'About {math.ceil(estimate/60)} minutes for the remaining training dose at the observed rate. Checkpoint, CPU and any score tests are excluded.'),
        main_training_continues=True,main_observed_fps=api.get('fps'),main_observation_unix_s=api.get('ts'),
        estimated_completion_unix_s=None,deadline_unix_s=None,updated_unix_s=analysis['observed_unix_s'],
        observation_unix_s=analysis['observed_unix_s'],actual_dose_observation=reference)
    page['observation_unix_s']=analysis['observed_unix_s']
    require(path.read_bytes()==old,'CONTROL changed during observation; do not overwrite')
    write(path,page,replace=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--expected-source-sha256');parser.add_argument('--anchor',type=Path);parser.add_argument('--anchor-sha256')
    parser.add_argument('--output-directory',type=Path);parser.add_argument('--control',type=Path,
        default=R/'logs/managed-learning-20261015/run-26/dashboard-current-work-status-original01-20261030/work-control.json')
    parser.add_argument('--max-seconds',type=float,default=21600);args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY_NO_READS_OR_ACTIONS');return 0
    own,_=snapshot(Path(__file__).resolve());require(own['sha256']==args.expected_source_sha256,'Exact observer source required')
    anchor_ref,_=snapshot(args.anchor);require(anchor_ref['sha256']==args.anchor_sha256,'Exact Root anchor required')
    code=selected(ANALYZER);spec=importlib.util.spec_from_file_location('_Root_post_repair_dose',ANALYZER['path'])
    module=importlib.util.module_from_spec(spec);exec(compile(code,ANALYZER['path'],'exec'),module.__dict__)
    summary,anchor=project_anchor(anchor_ref,module);phase_page(args.control,anchor_ref)
    out=args.output_directory
    require(out.is_absolute()and out.resolve()==out and out.parent==CASE and not out.exists()
        and 60<=args.max_seconds<=21600,'Fresh case-local output and finite budget required')
    out.mkdir(mode=0o700);records=out/'observations';records.mkdir(mode=0o700)
    started=time.monotonic();write(out/'owner.json',dict(pid=os.getpid(),birth=process_birth(os.getpid()),
        source=own,anchor=anchor_ref,analyzer=ANALYZER,started_unix_s=time.time(),interval_s=INTERVAL,max_seconds=args.max_seconds))
    write(out/'projected-anchor.json',anchor)
    previous=None;count=0;last=None;code=0;reason='budget_expired';error=None;next_poll=started
    try:
        while time.monotonic()-started<args.max_seconds:
            if (out/'STOP').exists():reason='Root_owned_stop_request';break
            page,control_before=phase_page(args.control,anchor_ref);count+=1;prefix=records/f'{count:06d}'
            began=time.time();write(prefix.with_name(prefix.name+'-intent.json'),dict(observed_start_unix_s=began,phase=PHASE))
            before={kind:owner(summary[kind])for kind in ('trainer','fleet')}
            _,lc_before=snapshot(Path(summary['control']['path']),immutable=False)
            api=get('now',prefix.with_name(prefix.name+'-API.json'));policy=get('continuous_training_policy',prefix.with_name(prefix.name+'-policy.json'))
            _,lc_after=snapshot(Path(summary['control']['path']),immutable=False)
            after={kind:owner(summary[kind])for kind in ('trainer','fleet')}
            sample=dict(schema='robotron-Root-post-repair-LR625-dose-observation-v1',observed_unix_s=time.time(),
                observation_started_unix_s=began,observed_main_owner=module.OWNER,
                observed_control_sha256=hashlib.sha256(lc_after).hexdigest(),api_now=api,continuous_policy=policy,
                original_owner_before=before,original_owner_after=after,nonatomic_cached_API_snapshots=True)
            sample_ref=write(prefix.with_name(prefix.name+'-sample.json'),sample)
            if previous is not None:sample['previous']=previous
            last=module.analyze(anchor,sample)
            if before!=after or lc_before!=lc_after:last=module.result('REJECTED','Owner/control changed inside observation')
            if policy.get('server_stamp')!=summary['trainer']['server_stamp']:last=module.result('REJECTED','Original server source/owner changed')
            last.update(observed_unix_s=sample['observed_unix_s'],sample=sample_ref,source_sha256=ANALYZER_SHA,
                actual_LR=api.get('lr'),actual_expert_ratio=api.get('expert_ratio'),actual_expert_pct=mapping(api.get('game_settings')).get('expert_pct'),
                actual_epsilon=api.get('epsilon'),Main_FPS=api.get('fps'),Main_loss=api.get('loss'),Main_grad_norm=api.get('grad_norm'))
            reference=write(prefix.with_name(prefix.name+'-analysis.json'),last)
            if last['status']=='VALID':previous=dict(counters=last['counters'],api_ts=last['api_ts'])
            values=row(count,last,sample);table=out/'dose-and-stability.csv';first=not table.exists()
            with table.open('a',newline='')as stream:
                writer=csv.DictWriter(stream,fieldnames=list(values))
                if first:writer.writeheader()
                writer.writerow(values);stream.flush();os.fsync(stream.fileno())
            write(out/'latest.json',last,replace=True)
            update_control(args.control,page,control_before,anchor,anchor_ref,last,reference,api)
            print(json.dumps({k:last.get(k)for k in ('observed_unix_s','status','all_reached','deltas','remaining','estimated_remaining_s','actual_LR','Main_FPS')},allow_nan=False),flush=True)
            if last['status']=='REJECTED':code=1;reason='original_observation_rejected';break
            if last['status']=='VALID'and last['all_reached']:reason='all_three_doses_reached';break
            next_poll=max(next_poll+INTERVAL,time.monotonic());remaining=args.max_seconds-(time.monotonic()-started)
            if remaining>0:time.sleep(min(max(0,next_poll-time.monotonic()),remaining))
        else:code=1
    except Exception as exc:code=1;reason='original_observer_failed';error=repr(exc)
    write(out/'result.json',dict(actual_exit=code,reason=reason,error=error,observations=count,
        ended_unix_s=time.time(),elapsed_s=time.monotonic()-started,last_analysis=last,
        Main_actions_or_policy_save_or_retry_or_restart=False,quality_or_mutation_authorized=False))
    return code


if __name__=='__main__':raise SystemExit(main())
