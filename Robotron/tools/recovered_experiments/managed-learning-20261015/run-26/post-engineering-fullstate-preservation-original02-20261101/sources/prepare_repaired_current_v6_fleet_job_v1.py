"""Default-inert finite DATA rebase of job0b63 for the repaired current Main.

Root runs --prepare ONLY after the NEW held restoration/release is real. Reads
bounded selected source/metadata; never probes processes/APIs, reads checkpoints,
imports target code, installs units, launches actors or changes learning controls.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

BASE = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fleet-only-v6-overlap-handoff-original01-20261031/continuous-supervisor-v6-job.json', 'sha256': '0b63a49c421707ed8a17155deeac5779e867fb009810e26a289e9e9483205813', 'bytes': 52398, 'identity': {'device': 2304, 'inode': 80879580, 'bytes': 52398, 'mtime_ns': 1793419045763771162, 'ctime_ns': 1793419045763771162, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
RECOVERY = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-A2-RPC-ACK-telemetry-fullstate-maintenance-original01-20261031/future-repaired-v6-fleet-DATA-source-original01/fleet-runtime-config-same15537-repaired-Lua120-v1.json', 'sha256': '18c0ba03e2ffcb7957eba831702f7ff410d0a8236cbc572040e06ccc61b2d518', 'bytes': 656, 'identity': {'device': 2304, 'inode': 82734199, 'bytes': 656, 'mtime_ns': 1793479422167542610, 'ctime_ns': 1793479422167542610, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
OPERATOR = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-A2-RPC-ACK-telemetry-fullstate-maintenance-original01-20261031/future-post-backup-held-startup-source-original01/prepare_and_release_repaired_current_fullstate_startup_v5.py', 'sha256': '11f7e4f1d1d8b11b373d4922c704ab072a57fc85f976d919c41995821df95d1a', 'bytes': 17169, 'identity': {'device': 2304, 'inode': 82734107, 'bytes': 17169, 'mtime_ns': 1793478910663965778, 'ctime_ns': 1793478910663965778, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
INSTALLED_SHA = {'/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/agent.py': 'd2a95ff0828df2a00ac86049965b6df304d26b50263b76d027d27a586ff77152', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/config.py': 'ef26db6aa19fe67ec9e1e15f8227b4e24bbc853b05d0ea00c450b290bf80b249', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/connection_cleanup_receipts.py': 'f27e38411238fcf62256e6b317836b757d31d5e0ac962ec8523dd380236d80ee', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/continuous_startup_bridge.py': '47efc654e1a46f281a094b43a8e55802b5f76cbdb62e830b5769a2f6d6e790f4', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/game_journal.py': '6aa78cb40434793853d17a1032cc6454ac86b0168828848d9d390336ba8678f0', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/main.py': '78178c39b281c0baf52222387f06db2d899c1bf2adfbe8c9fe2fd22729ff59c5', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/managed_driver.py': 'a7ec6dffba18e37b814842d498c8a34ba44f93dce4968ab769d480e329a643ec', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/managed_measurement.py': '39764cfa84572fe36c57e37a5c958d7caa001854c141ebcc161cc973f7b5f3c0', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/metrics_dashboard.py': '9b133ae93eb199ab6b9dc834d7e3879c4f4de2d42dcf07eda1e51b88a8ba2403', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/replay_buffer.py': '34b05e3c4403bc2dca53222222416db2afb733c480ee6238a0cc4e723885d0e8', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/socket_server.py': '1692ee2dbfb6f83d0f50234ee1eb30d0cf6bbe45d670a5a9fb52992fd92b56fc', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/bounded_fifo_cleanup_ack_v1.py': 'aab678c023598c90aa0374473eab7da8db9e71818a5d668aee2c222730d92fd8', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/main.lua': 'bc7df0d6ca18da11cd6498867a5b77e3638d8b721094264f056fe6a949d75f76', '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/training.py': '8cd1e1399c8313c4b9b0465142a72273ffcbb0e1a9053c4c3c9590493f110fe0'}
# Fixed0b63 indices: obsolete startup/owner/unit/cohort/backup/frontier/score DATA.
DROP = frozenset((32,33,34,35,36,37,38,41,42,43,44,45,46,47,48,49,52,53,54,55,56,57,58,59,60,69,70,77,78))
OWNER_KEYS = ('pid','birth','unit','invocation_id','cgroup','uid')
FIELDS = frozenset(('schema','new_Main_owner_record','new_startup_job','new_held_report',
    'new_Root_release','new_release_consumed','new_startup_authority',
    'current_backup_manifest','fleet_output','journal_directory'))


def require(value, reason):
    if not value: raise ValueError(reason)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def snapshot(path):
    path=Path(path)
    require(path.is_absolute() and path.resolve(strict=True)==path and not path.is_symlink(),
            'Canonical selected source/metadata required')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        s=os.fstat(stream.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_uid==1001==os.getuid() and s.st_nlink==1
            and 0<s.st_size<=2_000_000,'Bounded owned source/metadata only; no model/arrays')
        raw=stream.read(2_000_001)
        require(identity(s)==identity(os.fstat(stream.fileno()))==identity(path.lstat())
            and len(raw)==s.st_size,'Selected file changed during read')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(s)),raw


def checked(entry, immutable=True):
    require(type(entry) is dict and set(entry)=={'path','sha256','bytes','identity'},'Exact full8 pin required')
    actual,raw=snapshot(entry['path'])
    require(actual==entry and (not immutable or actual['identity']['mode']=='0o444'),
            'Exact selected immutable file required')
    return raw


def read(entry):
    return json.loads(checked(entry))


def prepare(args):
    own,_=snapshot(Path(__file__).resolve())
    require(own['sha256']==args.expected_source_sha256 and own['identity']['mode']=='0o444',
            'Exact immutable constructor source required')
    selected,raw=snapshot(args.selection)
    require(selected['sha256']==args.selection_sha256 and selected['identity']['mode']=='0o444',
            'Exact immutable Root selection required')
    s=json.loads(raw)
    require(set(s)==FIELDS and s['schema']=='robotron-root-repaired-v6-fleet-DATA-selection-v1',
            'Exact finite repaired-fleet selection fields required')
    base=read(BASE); require(len(base['inputs'])==79,'Fixed0b63 input inventory differs')
    selected_previous_owner={'pid': 599082, 'starttime_ticks': 1650370, 'unit': 'robotron-trainer.service', 'invocation_id': 'bd90079895534cbb9c0813cebe1f6e8c', 'cgroup': '/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-trainer.service'}
    cfg=read(RECOVERY); require(cfg['canonical_lua']==dict(path='/home/dave/source/repos/ArcadeAI/Robotron/Scripts/main.lua',
        sha256=INSTALLED_SHA['/home/dave/source/repos/ArcadeAI/Robotron/Scripts/main.lua']), 'Selected bc7 recovery config required')
    job=read(s['new_startup_job']); held=read(s['new_held_report'])
    release=read(s['new_Root_release']); consumed=read(s['new_release_consumed'])
    auth=read(s['new_startup_authority']); owner=held['owner']; observed=read(s['new_Main_owner_record'])['owner']
    require(set(owner)==set(OWNER_KEYS) and all(observed[k]==owner[k] and type(observed[k]) is type(owner[k]) for k in OWNER_KEYS)
        and owner['unit']=='robotron-trainer.service' and owner['uid']==1001
        and type(owner['pid']) is int and owner['pid']>1 and type(owner['birth']) is int and owner['birth']>0
        and re.fullmatch('[0-9a-f]{32}',owner['invocation_id']) is not None
        and owner['cgroup']==base['trainer']['cgroup']
        and (owner['pid'],owner['birth'],owner['invocation_id'])!=tuple(base['trainer'][k] for k in ('pid','birth','invocation_id')),
        'Actual NEW held/released Main owner record required')
    require(job['schema']=='robotron-continuous-main-before-update-startup-hold-job-v1'
        and job['mode']==base['mode'] and job['unit']==owner['unit']
        and job['original_attempt']==1 and job['no_retry'] is True
        and type(job['expected_startup_cap']) is int and job['expected_startup_cap']==8
        and job['operator_source']==OPERATOR,'Actual new14-source cap8 startup job required')
    require((owner['pid'],owner['birth'],owner['invocation_id']) !=
        (selected_previous_owner['pid'],selected_previous_owner['starttime_ticks'],selected_previous_owner['invocation_id']),
        'A fresh incarnation after the selected post-reboot owner is required')
    installed=job['source_pins']
    require(type(installed) is list and len(installed)==14
        and len({v['path'] for v in installed})==14
        and {v['path']:v['sha256'] for v in installed}==INSTALLED_SHA,'Exact repaired14 installed source catalogue required')
    for v in installed: checked(v,immutable=False)
    bypath={v['path']:v for v in installed}
    trainer=dict(owner,source=bypath['/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/main.py'],
        server_stamp=dict(pid=owner['pid'],birth=owner['birth'],
            source_sha256=INSTALLED_SHA['/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/socket_server.py']))
    require(held['schema']=='robotron-continuous-main-held-exact-restoration-report-v1'
        and held['status']=='VERIFIED_HELD_BEFORE_FIRST_UPDATE' and held['original_job']==s['new_startup_job']
        and held['checkpoint']==job['checkpoint'] and held['restoration_manifest']==job['restoration_manifest']
        and held['stopped_CPU_report']==job['stopped_CPU_report']
        and all(held[k] is True for k in ('all_online_target_Adam_scaler_payloads_equal',
            'optimizer_implementation_flags_exactly_equal','training_and_memory_locks_held_until_Root_release',
            'dashboard_and_GAME_listener_not_created'))
        and held['optimizer_attempts_before_release']==held['new_replay_inserts_before_release']==0,
        'Exact actual held restoration required')
    budget=held['startup_budget']
    require(budget['expected_startup_cap']==budget['runtime_cap']==8
        and budget['process_startup_environment_cap']=='8' and budget['fresh_per_boot_baseline_verified'] is True
        and budget['anchor_installed_or_rebased'] is False,'Exact restored cap8 budget required')
    require(release['schema']=='robotron-root-continuous-startup-one-use-release-v1'
        and release['owner']==owner and release['original_job']==s['new_startup_job']
        and release['held_report']==s['new_held_report'] and release['checkpoint']==job['checkpoint']
        and release['operator_source']==OPERATOR and release['allow_training'] is True
        and release['expected_startup_cap']==8 and release['startup_budget']==budget
        and consumed['schema']=='robotron-continuous-startup-release-consumed-v1'
        and consumed['owner']==owner and consumed['original_job']==s['new_startup_job']
        and consumed['held_report']==s['new_held_report'] and consumed['Root_release']==s['new_Root_release']
        and consumed['no_optimizer_or_replay_work_before_release'] is True
        and consumed['startup_budget']==budget,'Actual one-use release and consumption required')
    manifest=read(job['restoration_manifest']); cpu=read(job['stopped_CPU_report'])
    closed=read(job['stopped_state_authority']); backup=read(s['current_backup_manifest'])
    require(manifest['schema']=='robotron-stopped-full-training-state-restoration-manifest-v1'
        and manifest['status']=='VERIFIED_STOPPED_STATE'
        and manifest['owner']['pid']==selected_previous_owner['pid']
        and manifest['owner']==selected_previous_owner
        and manifest['checkpoint']==job['checkpoint'] and cpu['status']=='PASS'
        and cpu['restoration_manifest']==job['restoration_manifest']
        and cpu['original_job']==manifest['original_job'],'Actual current208501 strict state required; no oldS2 restore')
    require(closed['schema']=='robotron-root-closed-stopped-full-state-startup-authority-v1'
        and closed['CPU_report']==job['stopped_CPU_report'] and closed['restoration_manifest']==job['restoration_manifest']
        and closed['original_CPU_exit']==0 and closed['all_original_CPU_resources_closed'] is True
        and closed['old_trainer_and_population_closed'] is True,'Actual current strict CPU/population closure required')
    require(backup['schema']=='robotron-verified-stopped-full-training-backup-v1'
        and backup['status']=='COMPLETE_STREAM_HASHED_AND_FSYNCED'
        and backup['restoration_manifest']==job['restoration_manifest']
        and backup['strict_CPU_report']==job['stopped_CPU_report'],'Actual complete matching current-state backup required')
    require(auth['schema']=='robotron-root-continuous-main-startup-qualified-v1' and auth['trainer']==trainer
        and auth['all_model_optimizer_replay_banks_clocks_preserved'] is True
        and auth['new_mode_source_and_CPU_qualified'] is True and auth['actual_CPU_scope_closeouts'],
        'Actual new qualified source/restoration authority required')
    engineering=[]
    for v in auth['actual_CPU_scope_closeouts']:
        row=read(v);require(row['actual_exit']==0 and row['status']=='PASS_ENGINEERING_ONLY',
            'Actual original closed engineering qualification required');engineering.append(row)
    require(any(v.get('CPU_report')==job['stopped_CPU_report']
        and v.get('current_held_exact_restoration')==s['new_held_report']
        and v.get('new_one_use_release_consumed')==s['new_release_consumed']
        and v.get('full_backup_manifest')==s['current_backup_manifest'] for v in engineering),
        'Fresh engineering summary must join CURRENT CPU/backup/held/consumed, not old authority')
    output=Path(args.output); fleet=Path(s['fleet_output']); journal=Path(s['journal_directory'])
    require(output.is_absolute() and output.resolve(strict=False)==output and output.parent.is_dir() and not output.exists()
        and fleet.is_absolute() and fleet.resolve(strict=False)==fleet and not fleet.exists() and output.parent!=fleet
        and journal.is_absolute() and journal.resolve(strict=True)==journal and journal.is_dir(),
        'Fresh job/fleet output and actual new Main journal directory required')
    result=copy.deepcopy(base);result.update(trainer=trainer,source_authority=s['new_startup_authority'],
        output=str(fleet),journal_directory=str(journal))
    for name in ('parent_environment','actor_common_environment'):
        result[name].update(ROBOTRON_RECOVERY_CONFIG=RECOVERY['path'],ROBOTRON_RECOVERY_CONFIG_SHA256=RECOVERY['sha256'])
    held_inputs={}; replacements=[]; removed=[]
    for i,v in enumerate(base['inputs']):
        if i in DROP: removed.append(v);continue
        current=RECOVERY if v['path']==BASE['path'] else bypath.get(v['path'],v)
        if v['path']=='/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/power-outage-recovery-20261027-original01/fleet-runtime-config-rounds-jitter-v2.json': current=RECOVERY
        if current!=v:replacements.append(dict(prior=v,current=current))
        held_inputs[current['path']]=current
    added=[*installed,*[s[k] for k in ('new_Main_owner_record','new_startup_job','new_held_report',
        'new_Root_release','new_release_consumed','new_startup_authority','current_backup_manifest')],
        *[job[k] for k in ('restoration_manifest','stopped_CPU_report','stopped_state_authority','resume_record')],
        *auth['actual_CPU_scope_closeouts'],OPERATOR,own,selected]
    for v in added:held_inputs[v['path']]=v
    result['inputs']=list(held_inputs.values())
    changed={k for k in base if result[k]!=base[k]}
    require(changed<={'trainer','source_authority','output','journal_directory','parent_environment',
        'actor_common_environment','inputs'} and len(replacements)==5,'Only finite job/source/config rebase allowed')
    payload=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode()
    require(len(payload)<=2_000_000,'Bounded job required')
    with output.open('xb') as stream:
        stream.write(payload);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(output.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    produced,_=snapshot(output); v6=next(v for v in result['inputs'] if v['sha256']=='986777d1be4a474bab21f968a1a30bbf79b58623682bad75c23417d140e85a6a')
    argv=['/usr/bin/python3.12','-I','-B',v6['path'],'--execute','--config',produced['path'],
        '--config-sha256',produced['sha256'],'--source-sha256',v6['sha256']]
    print(json.dumps(dict(status='PREPARED_REPAIRED_V6_JOB_NOT_LAUNCHED',job=produced,base_job=BASE,
        changed_fields=sorted(changed),input_count=len(result['inputs']),source_and_config_replacements=replacements,
        obsolete_owner_startup_inputs_removed=removed,unit='robotron-mame.service',Type='exec',Restart='no',
        ExecStart=argv,Environment=dict(ROBOTRON_EVAL_MODE='0'),
        service_or_actor_launch_performed=False,API_or_proc_or_model_read=False)),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--selection');p.add_argument('--selection-sha256');p.add_argument('--output')
    p.add_argument('--expected-source-sha256');a=p.parse_args()
    if not a.prepare:print('PLAN_ONLY_NO_READS_OR_ACTIONS');return
    prepare(a)


if __name__=='__main__': main()
