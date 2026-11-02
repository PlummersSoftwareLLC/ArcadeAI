"""UNSELECTED readonly LR25 endpoint quality readiness; default PLAN has no I/O.
Root alone executes pinned cases after successful driver/restoration/CPU closure.
Only new output files; no stop/signal/lease creation/control/state/model-body work.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

RUN=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
CASE_SCHEMA='robotron-lr25-endpoint-quality-readiness-root-case-v1'
SCHEMA='robotron-lr25-first-durable-endpoint-exclusive-readiness-v1'
DEPENDENCIES={'binding_manifest': {'bytes': 18312,
                      'identity': {'bytes': 18312,
                                   'ctime_ns': 1792282460212093699,
                                   'device': 2304,
                                   'inode': 86245490,
                                   'mode': '0o444',
                                   'mtime_ns': 1792282460212093699,
                                   'nlink': 1,
                                   'uid': 1001},
                      'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/lr25_endpoint_quality_binding_proposal/preparation-manifest.json',
                      'sha256': '6d296d287b016826e1850ced3160b0dcf868f899a2064715be5250ce2bdb5204'},
 'bindings': {'bytes': 37905,
              'identity': {'bytes': 37905,
                           'ctime_ns': 1792282460204556515,
                           'device': 2304,
                           'inode': 86245475,
                           'mode': '0o444',
                           'mtime_ns': 1792282259266568204,
                           'nlink': 1,
                           'uid': 1001},
              'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/lr25_endpoint_quality_binding_proposal/quality_bindings.py',
              'sha256': '3a4f6143c38c43d077ec1f1d4516b719cefae4b9521a77e4cd6c7aa41f2498dd'},
 'health': {'bytes': 34643,
            'identity': {'bytes': 34643,
                         'ctime_ns': 1792280881970481328,
                         'device': 2304,
                         'inode': 81788933,
                         'mode': '0o444',
                         'mtime_ns': 1792280813602209925,
                         'nlink': 1,
                         'uid': 1001},
            'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-before-parent-release-resource-source-preparation-20261017/observe_before_release.py',
            'sha256': '905f1d67911366a22139a9c7805b2ce59faa80512c51f7ecef8e427d478f5b5c'},
 'queries': {'bytes': 29433,
             'identity': {'bytes': 29433,
                          'ctime_ns': 1792274392315653342,
                          'device': 2304,
                          'inode': 81160570,
                          'mode': '0o444',
                          'mtime_ns': 1792274359969060889,
                          'nlink': 1,
                          'uid': 1001},
             'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-readiness-collector-source-preparation-20261017/collect_readiness.py',
             'sha256': '9a8b4a20f090597f1ffad1a8c959c0cf886e3b119a17343857c7ce1d0f563f9b'}}


def require(value,message):
    if not value:raise RuntimeError(message)


def source_bytes(pin):
    path=Path(pin['path']);require(path.is_absolute() and path==path.resolve(strict=True),'Canonical source required')
    def identity(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        before=os.fstat(stream.fileno());require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and
            before.st_nlink==1 and stat.S_IMODE(before.st_mode)==0o444 and 0<before.st_size<=4<<20,'Readonly bounded source required')
        raw=stream.read((4<<20)+1);require(len(raw)==before.st_size and
            identity(before)==identity(os.fstat(stream.fileno()))==identity(path.lstat())==pin['identity'],'Source changed')
    require(len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Source digest differs')
    return raw


def load(name):
    bound=DEPENDENCIES[name];raw=source_bytes(bound)
    spec=importlib.util.spec_from_file_location('_lr25_readiness_'+name,bound['path'])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    require(source_bytes(bound)==raw,'Source changed while importing stdlib helper')
    return module


def paired(values):
    require(type(values) is list and 0<len(values)<=128 and len(set(values))==len(values),'Explicit exact extra pairs required')
    for unit in values:
        require(type(unit) is str and unit.startswith('robotron-') and '/' not in unit and
            unit.endswith(('.service','.timer')) and all(c.isascii() and (c.isalnum() or c in '_.-') for c in unit),'Invalid extra unit')
        other=unit.removesuffix('.service')+'.timer' if unit.endswith('.service') else unit.removesuffix('.timer')+'.service'
        require(other in values,'Every extra service requires its exact timer pair')
    return set(values)


def original_absence(obs,M,owner,label):
    require(type(owner['pid']) is int and owner['pid']>0 and type(owner['starttime_ticks']) is int and
        owner['starttime_ticks']>0,'Actual original PID/start required: '+label)
    current=M.process_start(owner['pid'])
    result=dict(label=label,original_pid=owner['pid'],original_starttime_ticks=owner['starttime_ticks'],
        observed_starttime_ticks=current,original_absent=current!=owner['starttime_ticks'])
    obs.publish(label+'-original-process.json',result);require(result['original_absent'],'Original process still present: '+label)
    return result


def numeric_release(obs,bound,expected_report,expected_job,M,label):
    release=obs.pinned(bound)
    require(release['status']=='PASS' and release['original_exec_code']==1 and release['original_exit']==0 and
        release['original_result']=='success' and release['original_archived_before_release'] is True and
        release['unit_released'] is True and release['CPU_report']==expected_report and release['cpu_job']==expected_job,
        'Exact numeric result/job/report/archive/release differs: '+label)
    archive=obs.pinned(release['original_terminal_archive']);original=archive['original']
    require(archive['archived_before_release'] is True and archive['original_exec_code']==1 and archive['original_exit']==0 and
        archive['original_result']=='success' and original['pid']==release['original_pid'] and
        original['starttime_ticks']==release['original_starttime_ticks'] and original['invocation_id']==release['original_invocation'],
        'Actual original numerical identity differs: '+label)
    require(archive['independent_readonly_CPU_report']==expected_report and
        archive['original_CPU_report']['sha256']==expected_report['sha256'] and
        archive['original_CPU_report']['bytes']==expected_report['bytes'] and
        archive['original_CPU_report']['path']!=expected_report['path'],'Independent numeric report archive differs')
    groups=archive['full_original_archives'];require(set(groups)=={'service_show','service_cat','service_journal','timer_show','timer_cat','timer_journal'},'Full six original groups required')
    commands={}
    for name,pins in groups.items():
        cmd=obs.pinned(pins['command']);stdout=obs.pinned(pins['stdout'],raw_only=True);stderr=obs.pinned(pins['stderr'],raw_only=True)
        require(cmd['returncode']==0 and stdout.decode('utf-8','surrogateescape')==cmd['stdout'] and
            stderr.decode('utf-8','surrogateescape')==cmd['stderr'],'Original raw archive group differs: '+name)
        commands[name]=cmd
    fields=dict(line.split('=',1) for line in commands['service_show']['stdout'].splitlines() if '=' in line)
    require(all(fields.get(k)==v for k,v in dict(MainPID='0',ExecMainPID=str(original['pid']),
        InvocationID=original['invocation_id'],ExecMainCode='1',ExecMainStatus='0',Result='success',NRestarts='0').items()),
        'Same original retained numeric terminal0 required')
    timer=dict(line.split('=',1) for line in commands['timer_show']['stdout'].splitlines() if '=' in line)
    require(timer.get('InvocationID')==original['timer_invocation_id'] and
        original['invocation_id'] in ' '.join(commands['service_journal']['argv']) and
        original['timer_invocation_id'] in ' '.join(commands['timer_journal']['argv']),'Exact original service/timer invocation archive required')
    obs.pinned(archive['stdout'],raw_only=True);obs.pinned(archive['stderr'],raw_only=True)
    require(len(release['owned_release'])==2,'Exact owned numeric pair required');previous_end=None
    for index,item in enumerate(release['owned_release']):
        expected=original['timer'] if index==0 else original['unit'];stop=obs.pinned(item['stop']);show=obs.pinned(item['final_show'])
        state=dict(line.split('=',1) for line in show['stdout'].splitlines() if '=' in line)
        require(item['unit']==expected and stop['argv']==['systemctl','--user','stop',expected] and
            stop['returncode']==item['stop_returncode']==0 and show['returncode']==0 and
            show['argv']==['systemctl','--user','show',expected,'--all'] and state.get('LoadState')==item['final_load_state']=='not-found' and
            release['original_terminal_archive']['identity']['mtime_ns']/1e9<stop['started_unix_s'] and
            all(c['ended_unix_s']<stop['started_unix_s'] for c in commands.values()) and
            (previous_end is None or previous_end<=stop['started_unix_s']),'Exact archive-before timer-first numeric release required')
        previous_end=show['ended_unix_s']
    absence=original_absence(obs,M,original,label)
    return {original['unit'],original['timer']},absence


def collect(obs,case,M,H,B):
    require(set(case)=={'schema','binding','plan','extra_owned_units','extra_release_evidence'} and case['schema']==CASE_SCHEMA,'Exact future root case required')
    cfg=obs.pinned(case['binding']);bundle=B.validate(cfg);plan=obs.pinned(case['plan']);baseline=bundle['baseline'];e=cfg['evidence']
    require(plan['output_directory']==cfg['campaign']['output_directory'] and len(plan['evaluator_source_hashes'])==12 and
        len(plan['execution_source_hashes'])==4 and plan['evaluator_source_hashes']==B.EVALUATOR and
        plan['execution_source_hashes']==B.EXECUTION and all(plan['checkpoints'][role]['source']==cfg[role]['path'] and
        plan['checkpoints'][role]['sha256']==cfg[role]['sha256'] for role in ('reference','candidate')),'New actual LR25 plan/checkpoint/source closure differs')
    # Explicit HISTORICAL25b context only; never aliases the new candidate or plan.
    released=obs.pinned(e['prior_release']);historical=obs.pinned(released['binding_job'])
    require(released['source_freeze_released'] is True and released['owned_cleanup_complete'] is True and
        released['binding_job']['sha256']=='25bde9295865770d9a0317ad32a65efa464abb3f71ec3d68f8adc0c8978eeb5b' and
        historical['schema']==M.BINDING_SCHEMA,'Exact genuine historical ownership context required')
    closed=obs.pinned(released['actual_all4_and_owned_closure']);after=obs.pinned(closed['after_resources'])
    require(closed['owned_cleanup_complete'] is True and closed['all69_absent'] is True and after['status']=='PASS','Genuine prior owned closure required')
    historical_case=obs.pinned(after['root_case']);require(historical_case['binding']==released['binding_job'],'Prior actual root case belongs to another campaign')
    units,old_owners,maintenance=M.known_units(obs,historical,historical_case)
    keys=('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')
    require(all(baseline[k]==cfg['runtime_anchor'][k]==historical['runtime_anchor'][k] for k in keys) and
        cfg['experiment']==historical['experiment'] and baseline['actual_maintenance']==historical['evidence']['maintenance_result'],
        'Historical context must match restored current owner/maps/maintenance, without candidate substitution')
    extras=paired(case['extra_owned_units']);require(type(case['extra_release_evidence']) is list and 0<len(case['extra_release_evidence'])<=64,'Root extra actual release evidence required')
    for pin in case['extra_release_evidence']:obs.pinned(pin)
    units=set(units)|extras
    execution=obs.pinned(e['CPU_execution'])
    cpu_units,cpu_absence=numeric_release(obs,execution['release_receipt'],e['phase_cpu_report'],e['phase_cpu_job'],M,'endpoint-CPU')
    entry=obs.pinned(e['entry_CPU']);entry_job=entry['job_file']
    er=obs.pinned(e['entry_CPU_release']);entry_units,entry_absence=numeric_release(obs,e['entry_CPU_release'],e['entry_CPU'],er['cpu_job'],M,'entry-CPU')
    require(all(entry_job[k]==er['cpu_job'][k] for k in ('path','sha256','bytes')),'Original entry CPU job differs')
    units|=cpu_units|entry_units
    direct=obs.pinned(e['driver_identity']);done=obs.pinned(e['driver_completion']);raw_return=obs.pinned(done['original_return'])
    require(direct['pid']==1915969 and done['returncode']==raw_return['returncode']==0 and
        direct['pid']==raw_return['pid'] and direct['starttime_ticks']==raw_return['starttime_ticks'] and
        raw_return['argv']==direct['argv'] and raw_return['original_process_untouched'] is True and raw_return['observation_timeout'] is False,
        'Genuine original direct hot driver return0 required; no fictional systemd unit')
    direct_absence=original_absence(obs,M,direct,'hot-driver')
    quality=cfg['campaign']['unit'];units|={quality+'.service',quality+'.timer'}
    require(not units.intersection({baseline['main_owner']['unit'],baseline['fleet_owner']['unit']}),'Main/fleet cannot be absence targets')
    units=sorted(units);first=M.absent_units(obs,units);old_absence=[original_absence(obs,M,x,'historical-owner-'+str(i)) for i,x in enumerate(old_owners)]
    # Per-call proxy only: no mutation to any sealed module or installed globals.
    proxy=SimpleNamespace(**vars(M));proxy.BLOCKED=set(M.BLOCKED)|{'verify_phase_snapshot_lr25.py','run_hot_window.py'}
    observations=H.health(obs,historical,plan,baseline,maintenance,proxy)
    api=json.loads(obs.pinned(observations['raw_API'],raw_only=True));observer=B.load_observer();now=observer.normalise(api)
    initial=observer.normalise(B.read_raw(bundle['window']['baseline']['api']))
    require(now['optimizer_identity']==initial['optimizer_identity'] and now['replay_identity']==initial['replay_identity'] and
        all(B.four(api)[k]>=B.four(bundle['proof']['clocks'])[k] for k in B.CLOCKS) and
        B.finite(api['lr'])==2.5e-5 and B.finite(api['pipeline_snapshot_age_s'])>=0 and
        api['pipeline_snapshot_age_s']<=5 and not api['pipeline_read_error'],
        'Fresh actual postCPU API must retain B exposure epochs/endpoint clocks and fresh pipeline')
    last=M.absent_units(obs,units)
    direct_final=original_absence(obs,M,direct,'hot-driver-final')
    return dict(schema=SCHEMA,status='PASS',observed_unix_s=time.time(),candidate=dict(source=cfg['candidate']['path'],
        sha256=cfg['candidate']['sha256'],bytes=cfg['candidate']['bytes'],root_job_sha256=e['phase_cpu_job']['sha256'],cpu_proof_sha256=e['phase_cpu_report']['sha256']),
        **{k:baseline[k] for k in keys},resources=dict(gpu0_uuid=M.GPU_UUIDS[0],gpu1_uuid=M.GPU_UUIDS[1],GPU0_free_bytes=observations['GPU0_free_bytes'],
        GPU0_no_compute_owner=True,GPU1_main_only=True,port9999_clear=True,lease_free=True,no_competing_helpers=True,
        no_private_cgroup_tmpfs_processes=True,no_pending_save=True,owned_units_released=True,
        commands_UID_cwd_exe_checked=True,held_environment_checked=True,unit_files_checked=True),
        observations=dict(health=observations,first_unit_absence=first,last_unit_absence=last,old_process_absence=old_absence,
            direct_driver_absence=direct_absence,direct_driver_absence_final=direct_final,entry_CPU_absence=entry_absence,endpoint_CPU_absence=cpu_absence,
            historical_ownership_context=released['binding_job'],historical_owned_closure=released['actual_all4_and_owned_closure'],
            BLOCKED_additions=['verify_phase_snapshot_lr25.py','run_hot_window.py']),binding=case['binding'],plan=case['plan'],
        release_actions=False,quality_acceptance=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--case',type=Path)
    parser.add_argument('--case-sha256');parser.add_argument('--expected-source-sha256');parser.add_argument('--output',type=Path);args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY_UNSELECTED: no reads/imports/queries/locks/output; future binding/plan/extras unbound');return 0
    require(args.case and args.case_sha256 and args.expected_source_sha256 and args.output,'Exact root case/source/NEW output required')
    # Authenticate self using the same bounded readonly source primitive.
    path=Path(__file__).resolve();s=path.lstat();self_pin=dict(path=str(path),sha256=args.expected_source_sha256,bytes=s.st_size,
        identity=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink))
    source_bytes(self_pin);source_bytes(DEPENDENCIES['binding_manifest'])
    M,H,B=load('queries'),load('health'),load('bindings');out=args.output
    require(out.is_absolute() and out.parent==RUN and out==out.resolve(strict=False) and not os.path.lexists(out),'NEW direct run26 output required')
    out.mkdir(mode=0o700);fd=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    obs=M.Observation(out);result=dict(schema=SCHEMA,status='FAILED_EXCLUSIVE_READINESS_OBSERVATION',started_unix_s=time.time(),release_actions=False,quality_acceptance=False)
    try:
        raw,pin=M.read_file(args.case);require(pin['sha256']==args.case_sha256 and pin['identity']['mode']=='0o444' and pin['identity']['nlink']==1,'Exact readonly root case required')
        result.update(collect(obs,M.decode(raw),M,H,B),root_case=pin,checker_source=self_pin)
    except BaseException as error:result['first_error']=dict(type=type(error).__name__,message=str(error))
    result.update(ended_unix_s=time.time(),raw_command_metadata=obs.commands,saved_input_pins=obs.pins)
    obs.publish('runtime-readiness.json',result);print(json.dumps(dict(status=result['status'],output=str(out)),allow_nan=False))
    return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
