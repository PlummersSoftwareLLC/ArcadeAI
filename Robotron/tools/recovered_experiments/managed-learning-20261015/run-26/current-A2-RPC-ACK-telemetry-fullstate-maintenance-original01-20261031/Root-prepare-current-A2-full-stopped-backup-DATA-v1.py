"""Root-only backup DATA assembly after actual strict CPU normal0 closure.

Default inert. Reads bounded metadata/source and stopped settings only; no model,
array or bank bodies, runtime queries, service actions, copying or controller
execution. Existing backup3600 remains the future copying/closure authority.
"""
import argparse,hashlib,importlib.util,json,os,stat
from pathlib import Path
ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
FIXED={'backup': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-current-main-cold-cap-state-preservation-original01-20261030/current-A2-LR9375-route-source-only-original01-20261031/copy_verified_current_continuous_state_A2_LR9375_v9.py', 'sha256': '80e743771abf28ba839e6ee5d9bf8079fa13bf3ab29a0897bb2501c757a4bb8f', 'bytes': 22403, 'identity': {'device': 2304, 'inode': 82727660, 'bytes': 22403, 'mtime_ns': 1793470800562871702, 'ctime_ns': 1793470992908160059, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'backup_controller': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/backup-sources/control_stopped_training_backup3600_v1.py', 'sha256': '7e59804f7b3eb86ad5f0fca0b62f9f940bbca429b837588f926f53d2c27068e6', 'bytes': 17269, 'identity': {'device': 2304, 'inode': 85225863, 'bytes': 17269, 'mtime_ns': 1793276698175882231, 'ctime_ns': 1793276698175882231, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'backup_template': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/backup-sources/Root-stopped-backup-v4-job-template-UNFILLED-NOT-LAUNCHABLE.json', 'sha256': 'dbf8f2d48bbb00856a1df3fad8f7c492e1e526f3495561d692c4bc05517b905c', 'bytes': 1273, 'identity': {'device': 2304, 'inode': 85226048, 'bytes': 1273, 'mtime_ns': 1793278182335692807, 'ctime_ns': 1793278182335692807, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'verifier': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-current-main-cold-cap-state-preservation-original01-20261030/current-A2-LR9375-route-source-only-original01-20261031/verify_current_continuous_stopped_fullstate_A2_LR9375_v7.py', 'sha256': '45be28f595c4c2f9dc4ae10eee53aa686114cfe37ec70704ac5cbf2b3044e1ce', 'bytes': 37599, 'identity': {'device': 2304, 'inode': 82727614, 'bytes': 37599, 'mtime_ns': 1793470688083822071, 'ctime_ns': 1793470992883159971, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'archive_reviewer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py', 'sha256': '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445', 'bytes': 41700, 'identity': {'device': 2304, 'inode': 81678691, 'bytes': 41700, 'mtime_ns': 1792418424753572422, 'ctime_ns': 1792418754597299596, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'source_archive_origin': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-forward-preservation-S2-original01/actual-full-stopped-backup-S2-preparation-original01/job.json', 'sha256': '670d3eace4c34f51facff3666f820ca0dfe93a44f210b1f5bd2846145bd78345', 'bytes': 53066, 'identity': {'device': 2304, 'inode': 82580759, 'bytes': 53066, 'mtime_ns': 1793394015848726054, 'ctime_ns': 1793394015848726054, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
SOURCE_ADDITIONS={'priority_phase.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/priority_phase.py', 'sha256': 'ee3c0d02bc1eab55e92ffd605c3736fe5a0ef905a8a8ee242c687301ea2b7c5b', 'bytes': 8049, 'identity': {'device': 2304, 'inode': 79696083, 'bytes': 8049, 'mtime_ns': 1792239930889420904, 'ctime_ns': 1792239930889863082, 'mode': '0o644', 'uid': 1001, 'nlink': 1}}, 'loss_kernel.py': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/loss_kernel.py', 'sha256': '23eb8fc0d8409c9f31ef26ec4596da9c2257e3985abbbfa7d5fbdcb337e21f67', 'bytes': 9373, 'identity': {'device': 2304, 'inode': 79724946, 'bytes': 9373, 'mtime_ns': 1792239930874436076, 'ctime_ns': 1792239930874877901, 'mode': '0o644', 'uid': 1001, 'nlink': 1}}}


def require(ok,why):
    if not ok:raise ValueError(why)


def ident(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def metadata(path,*,allow_empty=False):
    path=Path(path);before=path.lstat();require(path.is_absolute()and path.resolve()==path and not path.is_symlink()
        and stat.S_ISREG(before.st_mode)and before.st_uid==os.getuid()and before.st_nlink==1
        and(0<=before.st_size if allow_empty else 0<before.st_size)and before.st_size<=8<<20,'Bounded canonical metadata/source required; no payload sweep')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        require(ident(os.fstat(fd))==ident(before),'Metadata changed on open')
        with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read((8<<20)+1)
        require(ident(os.fstat(fd))==ident(before),'Metadata changed during read')
    finally:os.close(fd)
    require(ident(path.lstat())==ident(before)and len(raw)==before.st_size,'Metadata path/size changed')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=ident(before)),raw


def read(value,as_json=True):
    require(type(value['bytes'])is int and(0<value['bytes']if as_json else 0<=value['bytes'])and value['bytes']<=8<<20,'Bounded selected metadata pin required')
    actual,raw=metadata(value['path'],allow_empty=not as_json)
    require(actual['sha256']==value['sha256']and actual['bytes']==value['bytes']
        and all(actual['identity'][k]==v for k,v in value['identity'].items()),'Selected reduced5/full8 metadata changed')
    return json.loads(raw)if as_json else raw


def argument(path,sha):
    selected,raw=metadata(path);require(selected['sha256']==sha and selected['identity']['mode']=='0o444','Exact immutable Root metadata required');return selected,json.loads(raw)


def put(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb')as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return metadata(path)[0]


def load(role):
    value=FIXED[role];require(metadata(value['path'])[0]==value and value['identity']['mode']=='0o444','Frozen selected metadata controller/reviewer changed')
    spec=importlib.util.spec_from_file_location('_A2_backup_DATA_'+role,value['path']);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def prepare(args):
    own,_=metadata(Path(__file__).resolve());require(own['sha256']==args.expected_source_sha256 and own['identity']['mode']=='0o444','Frozen backup DATA assembler required')
    for value in FIXED.values():require(metadata(value['path'])[0]==value,'Selected backup source family changed')
    rp,report=argument(args.strict_report,args.strict_report_sha256);mp,manifest=argument(args.restoration_manifest,args.restoration_manifest_sha256)
    cp,closed=argument(args.CPU_closure,args.CPU_closure_sha256)
    require(report['schema']=='robotron-stopped-full-training-state-CPU-result-v1'and report['status']=='PASS'
        and report['source']==FIXED['verifier']and report['restoration_manifest']==mp
        and manifest['schema']=='robotron-stopped-full-training-state-restoration-manifest-v1'and manifest['status']=='VERIFIED_STOPPED_STATE'
        and manifest['source']==report['source']and manifest['original_job']==report['original_job'],'Actual current strict PASS/manifest/source join required')
    op,raw=metadata(Path(cp['path']).with_name('root-original-identity.json'));require(op['identity']['mode']=='0o444','Original C218 owner must be immutable');cpu_owner=json.loads(raw)
    reviewer=load('archive_reviewer');terminal=reviewer.archived_closure(closed,cpu_owner,read,exit_zero=True)
    require(report['actual_scope']['Id']==cpu_owner['unit']and report['actual_scope']['MainPID']==str(cpu_owner['pid'])
        and report['actual_scope']['InvocationID']==cpu_owner['invocation_id']
        and all(terminal.get(k)==v for k,v in dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='10min').items()),
        'Exact independently closed strict600 owner/resources required')
    strict=read(report['original_job']);sp=strict['current_selection'];selection=read(sp);ap=manifest['stopped_authority'];authority=read(ap)
    require(authority['schema']=='robotron-continuous-budget-stopped-preservation-authority-v1'and authority['original_selection']==sp
        and authority['owner']==manifest['owner']==selection['owner']and authority['fleet']==selection['fleet']
        and authority['owner']['pid']==208501 and authority['owner']['starttime_ticks']==27823352
        and type(authority['actual_exit'])is int and authority['actual_exit']==0 and authority['original_scope_released']is True,
        'Actual same-A2 original Main normal0 stopped authority required')
    require(selection['expected_current_cap']==8 and selection['expected_control_sha256']=='c13002750cdbb8c0d3a2017fba8a6d52283d15e8a07339dd8c104e3f94f46f1e'
        and type(selection['expected_lr_scale'])is float and selection['expected_lr_scale']==.1875,'Exact preserved before-stop .1875 recipe required')
    # Existing live-stop producer writes actual selection under runtime/, sibling to original job.json.
    selected_path=Path(sp['path']);require(selected_path.name=='actual-current-stop-selection.json'and selected_path.parent.name=='runtime','Exact original live-stop selection layout required')
    sjp,raw=metadata(selected_path.parent.parent/'job.json');stop_job=json.loads(raw)
    require(sjp['identity']['mode']=='0o444'and stop_job['current_selection']==selection['parent_Root_selection']
        and stop_job['trainer']==authority['owner']and stop_job['fleet']==authority['fleet']and stop_job['source']==selection['input_closure_producer'],
        'Original current live-stop job/selection/population binding differs')
    population=stop_job['original_population'];physical=read(population);fleet_archive=selection['fleet_terminal_archive']
    require(physical['trainer']==authority['owner']and physical['fleet']==authority['fleet']and len(physical['actors'])==192
        and fleet_archive==authority['fleet_terminal_archive'],'Exact original192 population/fleet archive required')
    closure=read(selection['input_closure']);sources={Path(v['path']).name:v for v in closure['source_pins']}
    # Exact two unchanged source archives omitted from the15 current writer/API pins.
    for name,value in SOURCE_ADDITIONS.items():
        require(name not in sources or sources[name]==value,'Conflicting source archive addition')
        read(value,False);sources[name]=value
    required={'__init__.py','model.py','config.py','learning_control.py','agent.py','replay_buffer.py','training.py','priority_phase.py','main.py','socket_server.py','managed_driver.py','managed_measurement.py','loss_kernel.py'}
    require(required<=set(sources)and all(v['path']==str(ROOT/'Scripts/dqn'/name)for name,v in sources.items()),'Complete canonical current source archive set required')
    for value in sources.values():read(value,False)
    context=strict['source_control_context'];settings,raw=metadata(ROOT/'models_dqn/game_settings.json');json.loads(raw)
    configuration=dict(learning_control=context['archived_control'],trainer_unit=context['archived_trainer_unit'],game_settings=settings)
    for value in configuration.values():read(value,False)
    output=args.output.absolute();destination=args.destination_root.absolute()
    require(output.parent==HERE and output.resolve()==output and not output.exists(),'Fresh direct-child backup DATA directory required')
    require(destination.resolve()==destination and not destination.exists()and destination.parent.is_dir()
        and destination.parent.resolve()==destination.parent and destination.parent.stat().st_uid==os.getuid()
        and not destination.is_relative_to(Path('/dev/shm'))and not destination.is_relative_to(ROOT/'models_dqn')and not destination.is_relative_to(ROOT/'Scripts')
        and destination.parent.stat().st_dev!=Path('/dev/shm').stat().st_dev,'Fresh Root-selected same-host disk backup destination required')
    template=read(FIXED['backup_template']);template.pop('required_actual_schema')
    unit='robotron-current-continuous-backup3600-'+rp['sha256'][:16]+'.service'
    job=dict(template,schema='robotron-verified-stopped-full-training-backup-job-v1',source=FIXED['backup'],unit=unit,
        original_attempt=1,no_retry=True,strict_CPU_report=rp,restoration_manifest=mp,strict_CPU_owner=op,strict_CPU_closure=cp,
        stopped_authority=ap,original_population=population,fleet_terminal_archive=fleet_archive,current_source_archives=sources,configuration_archives=configuration,
        destination_root=str(destination),destination_volume=dict(scope='ROOT_SELECTED_SAME_HOST_DISK',device=destination.parent.stat().st_dev))
    selected=[own,*FIXED.values(),rp,mp,op,cp,report['original_job'],sp,ap,sjp,population,fleet_archive,*strict['inputs'],*sources.values(),*configuration.values()]
    unique={}
    for value in selected:
        read(value,False)
        if value['path']in unique:require(unique[value['path']]['sha256']==value['sha256']and unique[value['path']]['bytes']==value['bytes'],'Conflicting duplicate metadata input')
        if value['path']not in unique or len(value['identity'])>len(unique[value['path']]['identity']):unique[value['path']]=value
    job['inputs']=list(unique.values());output.mkdir(mode=0o700);jp=put(output/'job.json',job);controller=load('backup_controller')
    config=dict(unit=unit,output=str(output/'execution-original01'),argv=['/usr/bin/python3.12','-I','-B',FIXED['backup']['path'],
        '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',FIXED['backup']['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=3600','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=3660,pins=[controller.pin(v['path'])for v in[jp,*job['inputs']]])
    cf=put(output/'controller-config.json',config);controller.checked_config(cf['path'])
    return put(output/'prepared-current-A2-full-backup-DATA-NOT-LAUNCHED.json',dict(schema='robotron-root-current-A2-full-backup-DATA-preparation-v1',status='BACKUP_DATA_PREPARED_NOT_LAUNCHED',source=own,
        strict_CPU_report=rp,restoration_manifest=mp,strict_CPU_owner=op,strict_CPU_closure=cp,job=jp,config=cf,
        Root_controller_argv_NOT_EXECUTED=['/usr/bin/python3.12','-I','-B',FIXED['backup_controller']['path'],'--execute','--config',cf['path'],'--expected-source-sha256',FIXED['backup_controller']['sha256']],
        copying_or_controller_or_runtime_or_source_control_install_actions_performed=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--expected-source-sha256')
    p.add_argument('--strict-report',type=Path);p.add_argument('--strict-report-sha256');p.add_argument('--restoration-manifest',type=Path);p.add_argument('--restoration-manifest-sha256')
    p.add_argument('--CPU-closure',type=Path);p.add_argument('--CPU-closure-sha256');p.add_argument('--output',type=Path,default=HERE/'actual-full-stopped-backup-DATA-original01')
    p.add_argument('--destination-root',type=Path,default=HERE/'full-stopped-backup-current-A2-original01');a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OUTPUTS_OR_ACTIONS')
