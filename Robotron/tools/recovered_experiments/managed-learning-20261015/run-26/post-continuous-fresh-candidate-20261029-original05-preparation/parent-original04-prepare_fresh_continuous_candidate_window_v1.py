"""Default inert. Root-only preparation of one fresh continuous-training window.

No mode starts the observer, pauses training, requests a save, restarts games,
or qualifies a scientific observer. --verify-entry is an explicit CPU action.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import types

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
HERE=Path(__file__).resolve().parent
OUT=B/'post-continuous-fresh-candidate-20261029-original04'
EXPECTED_OWNER=dict(pid=654315,birth_ticks=16564768,invocation_id='c9a7ad073c8043af8b9499acb4ae4372')
EXPECTED_SERVER=dict(pid=654315,birth=16564768,source_sha256='a076501b0601a637b91269a41572be60496754ad1da4b04385d77c51b9f34423')
ENVIRONMENT={'DQN_BATCH_SIZE':'4096','DQN_N_STEP':'3','DQN_MAX_SAMPLES_PER_FRAME':'8',
 'DQN_PER_PRIORITY_METRIC':'ce','ROBOTRON_CONTINUOUS_TRAINING_MODE':'1'}
THRESHOLDS=dict(applied_updates=5000,replay_inserts=1000000,elapsed_s=3600)
ENTRY_UNIT='robotron-continuous-fresh-entry-CPU-original04-20261029.service'
ENDPOINT_UNIT='robotron-continuous-fresh-endpoint-CPU-original04-20261029.service'
OBSERVER_UNIT='robotron-continuous-fresh-candidate-window-original04-20261029.service'
PYTHON='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python'
VERIFIER=G/'tools/power_recovery/verify_snapshot.py'
CHECKPOINT=G/'models_dqn/robotron_dqn_latest.pt'
SOURCES={'library': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04-preparation/watch_learning_window_continuous_v4.py', 'sha256': '4dc714d1677f58ebebd39002e1c9f42df4828fe0ef87795b714a2f2c210938fd', 'bytes': 18615, 'identity': {'device': 2304, 'inode': 85351385, 'bytes': 18615, 'mtime_ns': 1793306998562707000, 'ctime_ns': 1793306998562863608, 'mode': 292, 'uid': 1001, 'nlink': 1}}, 'watcher': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04-preparation/watch_replay_progress_continuous_candidate_v2.py', 'sha256': '73b574312cb294aeed166606568d33e41144e26c6c12516204aec88fb30f10bf', 'bytes': 10015, 'identity': {'device': 2304, 'inode': 85351376, 'bytes': 10015, 'mtime_ns': 1793306981390969150, 'ctime_ns': 1793306981390969150, 'mode': 292, 'uid': 1001, 'nlink': 1}}, 'verifier': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/power_recovery/verify_snapshot.py', 'sha256': '225baef72e62f5ea473a645800d3eed72b4001283ad8239682070ac1e63de533', 'bytes': 3340, 'identity': {'device': 2304, 'inode': 84702690, 'bytes': 3340, 'mtime_ns': 1793158901143599646, 'ctime_ns': 1793158901143599646, 'mode': 436, 'uid': 1001, 'nlink': 1}}}


def require(value,message):
    if not value:raise RuntimeError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,nlink=s.st_nlink)


def fullpin(path):
    path=Path(path);s=path.lstat()
    require(stat.S_ISREG(s.st_mode) and not path.is_symlink(),'Regular selected metadata/source required')
    raw=path.read_bytes();require(identity(path.lstat())==identity(s),'Selected input changed during read')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(s))


def checked(value,immutable=False):
    require(type(value) is dict and set(value)=={'path','sha256','bytes','identity'},'Full8 selected input required')
    path=Path(value['path']);require(path.is_absolute(),'Absolute selected input path required')
    require(0<value['bytes']<=2*1024*1024,'Only bounded source/control metadata may be read here')
    require(value['identity']['uid']==os.getuid() and value['identity']['nlink']==1,'Owned independent input required')
    if immutable:require(value['identity']['mode']==0o444,'Immutable Root authority required')
    require(fullpin(path)==value,'Selected full8/SHA input changed: '+str(path))
    return path.read_bytes()


def load(role):
    value=SOURCES[role];raw=checked(value)
    m=types.ModuleType('_fresh_continuous_window_'+role);m.__file__=value['path']
    exec(compile(raw,value['path'],'exec'),m.__dict__);return m


def selected(path,digest):
    selected_pin=fullpin(path);require(selected_pin['sha256']==digest,'Root selection SHA differs')
    value=json.loads(checked(selected_pin,True))
    require(value['schema']=='robotron-root-fresh-continuous-exposure-window-selection-v1'
        and value['status']=='ROOT_SELECTED_NEW_WINDOW_NOT_STARTED','Explicit new Root selection required')
    require(value['owner']==EXPECTED_OWNER and value['server_stamp']==EXPECTED_SERVER,'Current trainer incarnation differs')
    require(value['environment']==ENVIRONMENT,'Current CE4096/n3/cap8/continuous recipe differs')
    require(value['no_reset_or_hot_control_change'] is True and value['prior_window_counts_reused'] is False,
        'Fresh observational treatment only')
    require(value['entry_counters_are_not_the_window_anchor'] is True,'Window anchor is taken only after own entryCPU')
    require(type(value['policy_generation']) is int and value['policy_generation']>=0,'Actual policy generation required')
    require(set(value['root_capture_inputs'])=={'owner_and_environment','now','continuous_policy'},'Fresh Root capture evidence required')
    for p in value['root_capture_inputs'].values():checked(p,True)
    holds=value['source_and_control_inputs'];require(holds and len({p['path'] for p in holds})==len(holds),'Unique exact current source holds required')
    for p in holds:checked(p)
    required={str(G/'Scripts/dqn'/name) for name in ('__init__.py','agent.py','main.py','socket_server.py',
        'metrics_dashboard.py','learning_exposure.py','model.py','config.py','replay_buffer.py')}
    required.add(str(G/'models_dqn/learning_control.json'))
    require(required<={p['path'] for p in holds},'Current source/control input inventory incomplete')
    bypath={p['path']:p for p in holds}
    require(bypath[str(G/'Scripts/dqn/main.py')]['sha256']=='78178c39b281c0baf52222387f06db2d899c1bf2adfbe8c9fe2fd22729ff59c5'
        and bypath[str(G/'Scripts/dqn/socket_server.py')]['sha256']==EXPECTED_SERVER['source_sha256'],
        'Selected actual main/server source changed')
    for role,p in SOURCES.items():checked(p)
    context=dict(owner=value['owner'],server_stamp=value['server_stamp'],policy_generation=value['policy_generation'],
        slot_eval=value['slot_eval'],environment=value['environment'],source_and_control_inputs=holds)
    plan=dict(schema='robotron-replay-progress-candidate-window-plan-v1',owner=value['owner'],python=PYTHON,
        verifier=str(VERIFIER),checkpoint=str(CHECKPOINT),dashboard_status=str(OUT/'capture-status-projection.json'),
        observer_library={k:SOURCES['library'][k] for k in ('path','sha256','bytes')},
        expected_exposure_lineage=value['expected_exposure_lineage'],continuous_context=context,
        thresholds=THRESHOLDS,maximum_wait_s=14400,original_DQN_window_unchanged=True,CPU_unit=ENDPOINT_UNIT,
        no_training_controls_changed=True,no_live_game_restart=True,automatic_promotion=False,
        original_partial_counts_reused=False,original_failed_case_restarted=False,
        purpose='Own fresh continuous exposure only; no previous window time/counts or failed scientific proof reused.',
        scientific_monitor_qualified=False,quality_qualified=False,
        capture_rule='All own 3600s/5000 applied/1M normally admitted fresh replay; first observed normal autosave mtime>own threshold+10s; isolated CPU before acceptance.',
        root_selection=selected_pin,source=fullpin(Path(__file__)))
    observer=load('library');observer.configure(plan)
    require(observer.owner()==EXPECTED_OWNER,'Current original trainer owner changed')
    watch=load('watcher')
    return value,selected_pin,observer,watch,plan


def prepare_entry(value,selected_pin,observer,watch,plan):
    require(0<=time.time()-value['created_unix_s']<=60,'Fresh Root entry selection within60s required')
    require(not OUT.exists(),'New exposure output only; no adoption of partial output')
    OUT.mkdir(mode=0o700);entry=OUT/'entry-CPU-original01';entry.mkdir(mode=0o700)
    endpoint=observer.copy_snapshot(CHECKPOINT,entry/'entry.pt')
    observer.publish(OUT/'entry-snapshot-prepared-NOT-CPU-VERIFIED.json',dict(
        schema='robotron-independent-durable-window-entry-preparation-v1',endpoint=endpoint,
        owner=EXPECTED_OWNER,source=observer.pin(Path(__file__)),Root_selection=selected_pin,
        CPU_unit=ENTRY_UNIT,own_window_not_started=True,prior_partial_counts_reused=False),exclusive=True)
    print(json.dumps(dict(status='ENTRY_COPIED_NOT_CPU_VERIFIED',entry=endpoint,next_mode='--verify-entry')))


def verify_entry(value,selected_pin,observer,watch,plan):
    entry=OUT/'entry-CPU-original01';prepared=observer.read(OUT/'entry-snapshot-prepared-NOT-CPU-VERIFIED.json')
    require(prepared['owner']==EXPECTED_OWNER and prepared['Root_selection']==selected_pin
        and not (OUT/'entry-CPU-authority.json').exists(),'Original own entry CPU only')
    endpoint=prepared['endpoint'];observer.check_pin(endpoint)
    verification=watch.verify_CPU(dict(plan,CPU_unit=ENTRY_UNIT),entry,endpoint,observer)
    observer.publish(OUT/'entry-CPU-authority.json',dict(endpoint=endpoint,
        actual_CPU_verification=observer.pin(entry/'endpoint-CPU.json'),
        original_CPU_owner=observer.pin(entry/'CPU-original-owner.json'),
        original_CPU_terminal=observer.pin(entry/'CPU-original-terminal.json'),
        original_CPU_release=observer.pin(entry/'CPU-owned-release.json'),
        Root_selection=selected_pin,new_entry_Adam_step=verification['Adam_step_min'],own_window_not_started=True),exclusive=True)
    print(json.dumps(dict(status='OWN_ENTRY_CPU_VERIFIED_AND_RELEASED',next_mode='--prepare-window')))


def prepare_window(value,selected_pin,observer,watch,plan):
    require(not (OUT/'window-plan.json').exists() and not (OUT/'anchor.raw.json').exists(),'Wholly new window only')
    authority=observer.read(OUT/'entry-CPU-authority.json')
    require(authority['Root_selection']==selected_pin,'Entry selection differs')
    for key in ('actual_CPU_verification','original_CPU_owner','original_CPU_terminal','original_CPU_release'):
        observer.check_pin(authority[key])
    verification=observer.read(authority['actual_CPU_verification']['path'])
    require(verification['checkpoint']==authority['endpoint'] and verification['CUDA_initialized'] is False,'Own entry CPU differs')
    fresh=observer.observe(EXPECTED_OWNER,OUT,plan['expected_exposure_lineage']);observer.validate(fresh,EXPECTED_OWNER)
    require(all(fresh[key]>=verification['clocks'][key] for key in observer.CLOCKS),'Fresh API precedes own entry CPU')
    observer.publish(OUT/'prelaunch-API-NOT-WINDOW-ANCHOR.json',fresh,exclusive=True)
    plan['entry_Adam_step']=verification['Adam_step_min'];plan['entry_verification']=authority['actual_CPU_verification']
    paths=[Path(p['path']) for p in value['source_and_control_inputs']]
    paths += [Path(p['path']) for p in value['root_capture_inputs'].values()]
    paths += [Path(p['path']) for p in SOURCES.values()]+[Path(__file__),Path(selected_pin['path'])]
    paths += [OUT/'prelaunch-API-NOT-WINDOW-ANCHOR.json']
    paths += [Path(authority[key]['path']) for key in ('actual_CPU_verification','original_CPU_owner','original_CPU_terminal','original_CPU_release')]
    plan['inputs']=[observer.pin(path) for path in dict.fromkeys(paths)]
    for p in plan['inputs']:observer.check_pin(p)
    observer.publish(OUT/'window-plan.json',plan,exclusive=True)
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',plan=observer.pin(OUT/'window-plan.json'),argv=observer_command())))


def observer_command():
    return ['systemd-run','--user','--unit='+OBSERVER_UNIT,'-p','Type=exec','-p','Restart=no',
        '-p','RemainAfterExit=yes','-p','CPUQuota=100%','-p','MemoryMax=256M','-p','MemorySwapMax=0',
        '-p','TasksMax=32','-p','RuntimeMaxSec=14820','-p','TimeoutStopSec=10','-p','SendSIGKILL=no',
        '-p','StandardOutput=append:'+str(OUT/'observer.stdout.log'),
        '-p','StandardError=append:'+str(OUT/'observer.stderr.log'),
        '/usr/bin/python3.12','-I','-B',SOURCES['watcher']['path'],'--plan',str(OUT/'window-plan.json')]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);modes=parser.add_mutually_exclusive_group()
    for name in ('prepare-entry','verify-entry','prepare-window','print-observer-command'):
        modes.add_argument('--'+name,action='store_true')
    parser.add_argument('--selection',type=Path);parser.add_argument('--selection-sha256');args=parser.parse_args(argv)
    if args.print_observer_command:print(json.dumps(dict(argv=observer_command(),launch_performed=False)));return
    if not any((args.prepare_entry,args.verify_entry,args.prepare_window)):
        print('PLAN_ONLY: no input reads, copies, probes, outputs, CPU or observer launch');return
    require(args.selection is not None and args.selection_sha256 is not None,'Explicit immutable Root selection required')
    values=selected(args.selection,args.selection_sha256)
    if args.prepare_entry:prepare_entry(*values)
    elif args.verify_entry:verify_entry(*values)
    else:prepare_window(*values)

if __name__=='__main__':main()
