"""Root-only current-state held-startup DATA and planned unit text; default inert.

Only after actual backup closure, repaired-source installation and Root's separate
offline LR.125 control write. No source/control/unit installation, reload, start,
release, API/proc/runtime query, tensor loading or payload transformation occurs.
The selected existing --prepare-job operator stream-hashes the canonical checkpoint.
"""
import argparse,ast,hashlib,json,os,stat,subprocess,time
from pathlib import Path
ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
CPU_SHA='c608a2ce35263a07b064111a34606ed3c6d9a54f35334f1fa80620a766a2f21d'
STATE_SHA='06083be0404682c192d4feb61259827485a9b5c4ffd5a05a611dd08bf3878a5b'
CHECKPOINT_SHA='b15101eef254f09a7751ab5656557ae420f17c25e4ee39b59e43072046999d5b'
FIXED={'operator': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-A2-RPC-ACK-telemetry-fullstate-maintenance-original01-20261031/future-post-backup-held-startup-source-original01/prepare_and_release_repaired_current_fullstate_startup_v5.py', 'sha256': '11f7e4f1d1d8b11b373d4922c704ab072a57fc85f976d919c41995821df95d1a', 'bytes': 17169, 'identity': {'device': 2304, 'inode': 82734107, 'bytes': 17169, 'mtime_ns': 1793478910663965778, 'ctime_ns': 1793478910663965778, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'route': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-A2-RPC-ACK-telemetry-fullstate-maintenance-original01-20261031/future-post-backup-held-startup-source-original01/Root-post-backup-install-and-current-state-held-restart-SOURCE-ONLY-v1.json', 'sha256': 'd9450d646662afb472cfe7daaf175bdfba681744f8a51c83d389d3ccee9e5094', 'bytes': 21337, 'identity': {'device': 2304, 'inode': 82734110, 'bytes': 21337, 'mtime_ns': 1793478910673722590, 'ctime_ns': 1793478910673722590, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'launcher': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-cold-replay-cap-launcher-source-only-original01-20261029/launch_resume_expected_cold_cap_v1.py', 'sha256': 'a6ddcc7b5b84f22ffdd61127ecb5bd3898efb96b5c0b90858c8c3c0882121a90', 'bytes': 7049, 'identity': {'device': 2304, 'inode': 81407532, 'bytes': 7049, 'mtime_ns': 1793336225173344861, 'ctime_ns': 1793336225173344861, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'control_proposal': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-A2-RPC-ACK-telemetry-fullstate-maintenance-original01-20261031/PROPOSED-post-repair-LR625-control-NOT-INSTALLED-v1.json', 'sha256': 'ce14dde2497b52b947ac50ff7ad29362cfaee8fadf24e7813bae5d54bcfd405c', 'bytes': 1936, 'identity': {'device': 2304, 'inode': 82734239, 'bytes': 1936, 'mtime_ns': 1793479861819037279, 'ctime_ns': 1793479861819037279, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}


def require(ok,why):
    if not ok:raise ValueError(why)


def ident(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def metadata(path,allow_empty=False):
    path=Path(path);before=path.lstat();require(path.is_absolute()and path.resolve()==path and not path.is_symlink()
        and stat.S_ISREG(before.st_mode)and before.st_uid==os.getuid()and before.st_nlink==1
        and(0<=before.st_size if allow_empty else 0<before.st_size)and before.st_size<=8<<20,'Bounded canonical metadata/source required; never a model/array input')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        require(ident(os.fstat(fd))==ident(before),'Metadata open identity changed')
        with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read((8<<20)+1)
        require(ident(os.fstat(fd))==ident(before),'Metadata changed during read')
    finally:os.close(fd)
    require(ident(path.lstat())==ident(before)and len(raw)==before.st_size,'Metadata path/size changed')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=ident(before)),raw


def read(value,immutable=True):
    actual,raw=metadata(value['path']);require(actual==value and(not immutable or actual['identity']['mode']=='0o444'),'Exact selected full8 metadata required');return json.loads(raw)


def put(path,value):
    raw=value if type(value)is bytes else(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb')as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return metadata(path,allow_empty=not raw)[0]


def prepare(args):
    own,_=metadata(Path(__file__).resolve());require(own['sha256']==args.expected_source_sha256 and own['identity']['mode']=='0o444','Frozen selected startup DATA assembler required')
    sip,raw=metadata(args.selection);require(sip['sha256']==args.selection_sha256 and sip['identity']['mode']=='0o444','Immutable actual Root input selection required');s=json.loads(raw)
    require(s['schema']=='robotron-root-current-A2-repaired-held-startup-DATA-selection-v1'and type(s['expected_startup_cap'])is int and s['expected_startup_cap']==8,'Exact current-state cap8 startup DATA selection required')
    for p in FIXED.values():require(metadata(p['path'])[0]==p,'Selected operator/route/launcher/control proposal changed')
    rp=s['stopped_CPU_report'];mp=s['restoration_manifest'];pp=s['Root_positive_CPU_closeout'];bp=s['full_backup_manifest'];bcp=s['Root_closed_backup'];ip=s['installation_receipt'];desired=s['desired_control']
    report=read(rp);manifest=read(mp);positive=read(pp);backup=read(bp);closed=read(bcp);installed=read(ip)
    require(rp['sha256']==CPU_SHA and mp['sha256']==STATE_SHA and report['schema']=='robotron-stopped-full-training-state-CPU-result-v1'
        and report['status']=='PASS'and report['restoration_manifest']==mp and manifest['schema']=='robotron-stopped-full-training-state-restoration-manifest-v1'
        and manifest['status']=='VERIFIED_STOPPED_STATE'and manifest['original_job']==report['original_job'],'Exact current qualified CPU/manifest required; no older state substitution')
    require(positive['schema']=='robotron-root-current-A2-strict-CPU-positive-closure-v1'and positive['CPU_report']==rp and positive['restoration_manifest']==mp
        and type(positive['actual_exit'])is int and positive['actual_exit']==0 and positive['saved_checkpoint_sha256']==CHECKPOINT_SHA
        and all(positive[k]is True for k in('original_PID_birth_absent','original_service_and_timer_absent','original_cgroup_absent_or_empty')),'Actual Root CPU normal0 and positive owner/resource closure required')
    cpu_owner=read(positive['original_CPU_owner']);cpu_closed=read(positive['original_CPU_closure'])
    if 'CPU_closure'in s:require(s['CPU_closure']==positive['original_CPU_closure'],'Selected raw CPU closure differs from positive proof')
    require(cpu_closed['original']==cpu_owner and type(cpu_closed['original_exit'])is int and cpu_closed['original_exit']==0
        and cpu_closed['unit_released']is cpu_closed['lifecycle_complete']is True
        and report['actual_scope']['Id']==cpu_owner['unit']and report['actual_scope']['MainPID']==str(cpu_owner['pid'])
        and report['actual_scope']['InvocationID']==cpu_owner['invocation_id'],'Original CPU owner/report/closure mismatch')
    require(backup['schema']=='robotron-verified-stopped-full-training-backup-v1'and backup['status']=='COMPLETE_STREAM_HASHED_AND_FSYNCED'
        and backup['strict_CPU_report']==rp and backup['restoration_manifest']==mp
        and backup['source']['sha256']=='80e743771abf28ba839e6ee5d9bf8079fa13bf3ab29a0897bb2501c757a4bb8f'
        and all(backup[k]is True for k in('full_ring_states_and_next_states_streamed_and_hashed','all_selected_bank_generation_fields_copied','all_files_independent_single_link_readonly','no_sources_written_or_chmodded')),'Actual complete current fullstate independent backup required')
    require(closed['schema']=='robotron-Root-original-fullstate-backup-positive-closeout-v1'and closed['backup_manifest']==bp
        and type(closed['actual_exit'])is int and closed['actual_exit']==0
        and all(closed[k]is True for k in('original_tool_terminal0_confirmed','all_original_backup_processes_absent','all_original_backup_units_released','all_original_backup_cgroups_empty')),'Actual Root original-backup normal0 positive closure required')
    old=read(manifest['stopped_authority']);require(old['owner']==manifest['owner']and old['actual_exit']==0 and old['original_scope_released']is True,'Actual stopped Main authority required')
    for key in('owners_before','owners_after'):
        row=backup[key];require(row['trainer']==manifest['owner']and row['fleet']==old['fleet']
            and row['recorded_original_actor_births_absent']==192 and row['original_trainer_and_fleet_cgroups_empty']is True,'Actual complete backup must prove original Main/fleet/all192 closure')
    require(installed['schema']=='robotron-Root-exact-five-repair-source-installation-v1'and installed['status']=='EXACT_FIVE_SOURCES_INSTALLED_AND_FSYNCED'
        and installed['source']['sha256']=='8b12151ed2615aef1ecef5c3daafadde9411bdaa38b8330c595096c7e5795fea'
        and installed['backup_manifest']==bp and installed['Root_closed_backup']==bcp and installed['operator']==FIXED['operator'],'Actual exact five-source installation after this backup required')
    operator_raw=metadata(FIXED['operator']['path'])[1];catalogue=ast.literal_eval(next(n.value for n in ast.parse(operator_raw).body if isinstance(n,ast.Assign)and any(isinstance(x,ast.Name)and x.id=='INSTALLED_SHA'for x in n.targets)))
    sources=installed['source_pins'];require(len(sources)==len(catalogue)==14 and len({p['path']for p in sources})==14
        and{p['path']:p['sha256']for p in sources}==catalogue,'Exact fourteen fresh canonical installed source pins required')
    for p in sources:require(metadata(p['path'])[0]==p,'Fresh canonical installed source changed')
    control=read(desired,immutable=False);proposal=read(FIXED['control_proposal'])
    require(desired['path']==str(ROOT/'models_dqn/learning_control.json')and control==proposal['proposed_control']
        and type(control['lr_scale'])is float and control['lr_scale']==.125 and control.get('measurement')is None
        and type(control['experiment'])is str and control['experiment'],'Root must separately install the exact proposed offline.125/newexperiment control first')
    checkpoint=manifest['checkpoint'];require(checkpoint['path']==str(ROOT/'models_dqn/robotron_dqn_latest.pt')and checkpoint['sha256']==CHECKPOINT_SHA,'Use exact CURRENT stopped canonical checkpoint; no old weights or policy-only copy')
    cp=Path(checkpoint['path']);require(cp.resolve()==cp and not cp.is_symlink()and ident(cp.lstat())==checkpoint['identity'],'Current stopped checkpoint stat changed')
    phase=manifest['priority_metric_phase'];require(phase['metric']=='ce'and phase['valid']is True,'Current valid CE phase/founder required')
    console=Path(s['console_path']);ci=console.lstat();require(console.is_absolute()and console.resolve()==console and console.name=='trainer-console.log'
        and stat.S_ISREG(ci.st_mode)and ci.st_uid==os.getuid()and ci.st_nlink==1,'Append same existing owned trainer-console.log; never read/truncate its body')
    output=args.output.absolute();held=HERE/'post-backup-startup-held-original01'
    require(output.parent==HERE and output.resolve()==output and not output.exists()and held.resolve()==held and not held.exists(),'Fresh metadata and held-runtime paths required')
    output.mkdir(mode=0o700)
    authority=put(output/'Root-actual-closed-current-full-state-startup-authority.json',dict(schema='robotron-root-closed-stopped-full-state-startup-authority-v1',status='ACTUAL_CURRENT_STOPPED_CPU_AND_FULL_BACKUP_CLOSED',
        CPU_report=rp,restoration_manifest=mp,original_CPU_exit=0,all_original_CPU_resources_closed=True,old_trainer_and_population_closed=True,
        original_CPU_owner=positive['original_CPU_owner'],raw_CPU_owned_closure=positive['original_CPU_closure'],Root_CPU_positive_closeout=pp,
        actual_stopped_authority=manifest['stopped_authority'],full_independent_backup=bp,backup_original_exit=0,all_original_backup_resources_closed=True,
        Root_backup_positive_closeout=bcp,source_installation_receipt=ip,created_unix_s=time.time()))
    resume=put(output/('resume-'+CHECKPOINT_SHA+'.json'),dict(schema='robotron-priority-metric-start-v1',phase_id=phase['phase_id'],metric='ce',action='resume',previous_metric='ce',
        checkpoint={k:checkpoint[k]for k in('path','sha256','bytes')},model_dir=str(ROOT/'models_dqn'),root_precommit_sha256=phase['root_precommit_sha256']))
    startup=put(output/'Root-actual-current-state-held-startup-selection.json',dict(schema='robotron-root-continuous-startup-hold-selection-v1',unit='robotron-trainer.service',expected_startup_cap=8,
        output_directory=str(held),restoration_manifest=mp,stopped_CPU_report=rp,stopped_state_authority=authority,checkpoint=checkpoint,resume_record=resume,source_pins=sources))
    argv=['/usr/bin/python3.12','-I','-B',FIXED['operator']['path'],'--prepare-job','--expected-source-sha256',FIXED['operator']['sha256'],'--selection',startup['path'],'--selection-sha256',startup['sha256'],'--output',str(output/'startup-job.json')]
    result=subprocess.run(argv,capture_output=True,timeout=120);stdout=put(output/'operator-stdout.txt',result.stdout);stderr=put(output/'operator-stderr.txt',result.stderr)
    command=put(output/'Root-startup-operator-prepare-DATA-command.json',dict(argv=argv,actual_exit=result.returncode,stdout=stdout,stderr=stderr));require(result.returncode==0,'Startup DATA operator failed; no start/release performed')
    jp,raw=metadata(output/'startup-job.json');job=json.loads(raw);require(job['original_selection']==startup and job['checkpoint']==checkpoint and job['source_pins']==sources,'Produced startup job differs')
    environment=dict(DQN_MAX_SAMPLES_PER_FRAME='8',ROBOTRON_CONTINUOUS_TRAINING_MODE='1',ROBOTRON_CONTINUOUS_STARTUP_HOLD='1',ROBOTRON_CONTINUOUS_STARTUP_JOB=jp['path'],ROBOTRON_CONTINUOUS_STARTUP_JOB_SHA256=jp['sha256'],DQN_PRIORITY_PHASE_RECORD=resume['path'],DQN_PRIORITY_PHASE_RECORD_SHA256=resume['sha256'],PYTHONUNBUFFERED='1',ROBOTRON_RUN_DIR=str(HERE/'post-backup-Main-runtime-original01'))
    text='[Service]\nType=exec\nRestart=no\nExecStart=\nExecStart='+str(ROOT.parent/'.venv-gb300/bin/python')+' -Xgil=0 -I -B '+FIXED['launcher']['path']+' --expected-startup-cap 8 --records '+str(output)+'\n'
    text+=''.join('Environment="'+k+'='+v+'"\n'for k,v in environment.items())
    text+='UnsetEnvironment=ROBOTRON_TRAINING_ROUND_STATUS LD_PRELOAD PYTHONPATH\nStandardOutput=append:'+str(console)+'\nStandardError=inherit\nKillSignal=SIGINT\nSendSIGKILL=no\nTimeoutStopSec=240\n'
    planned=put(output/'97-repaired-current-state-startup.PLANNED.conf',text.encode())
    require(metadata(desired['path'])[0]==desired,'Root-selected new control changed during DATA preparation')
    return put(output/'prepared-current-state-held-startup-DATA-NOT-LAUNCHED.json',dict(schema='robotron-root-current-state-held-startup-DATA-preparation-v1',status='STARTUP_DATA_PREPARED_NOT_INSTALLED_NOT_STARTED_NOT_RELEASED',source=own,input_selection=sip,
        stopped_state_authority=authority,resume_record=resume,startup_selection=startup,startup_job=jp,operator_command=command,planned_permanent_unit_dropin=planned,console_stat_before_append=dict(path=str(console),identity=ident(ci)),
        desired_control=desired,saved_checkpoint=checkpoint,saved_scalar_clocks=manifest['saved_scalars'],new_held_owner=None,unit_installed_or_reloaded=False,Main_or_fleet_started=False,one_use_release_published=False,
        maintenance_HTTP_must_be_positively_closed_BEFORE_one_use_Root_release=True,restored_optimizer_payload_must_remain_exact_saved_LR9375_before_release=True,effective_LR625_firstupdate_requires_actual_postrelease_readback=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--expected-source-sha256');p.add_argument('--selection',type=Path);p.add_argument('--selection-sha256');p.add_argument('--output',type=Path,default=HERE/'post-backup-startup-metadata-original01');a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a)),flush=True)
    else:print('PLAN_ONLY_NO_READS_WRITES_OR_ACTIONS')
