"""Root-only B -> S2 stop DATA preparation. Default inert; never stop/launch.

Requires the new counter-aware PASS report. No model/array/game/log bodies are
read; bounded API/metadata snapshots and exact file/proc identities are retained.
"""
import argparse, copy, hashlib, json, os, stat, subprocess, time, urllib.request
from pathlib import Path
ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
T=HERE.parent
B=T/'B-cold-cap12-original01'
MEASUREMENT=B/'counter-aware-measurement-original01'
COHORT=B/'fresh155-train37-eval-cohort-original01'
TRAINER=dict(pid=167514,starttime_ticks=27299341,unit='robotron-trainer.service',invocation_id='99edc3b8c8d24bb2a7570ef18b0e7bdc',cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-trainer.service')
FLEET=dict(pid=168479,starttime_ticks=27329911,unit='robotron-mame.service',invocation_id='4589d7b54c5d4aa187283573d3795f27',cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-mame.service')
PERSISTENT={'Thread-1 (serve','Thread-2 (_samp','Thread-3 (_cons','Thread-4 (start','Thread-5 (stats'}
FIXED={'assembler': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-current-main-cold-cap-state-preservation-original01-20261030/prepare_current_continuous_preservation_header_v3.py', 'sha256': 'e2877afb6695fcf3c08015331a0b0b6a0f1f12578cacba6a82d1d4dfff1af8b7', 'bytes': 25721, 'identity': {'device': 2304, 'inode': 81427026, 'bytes': 25721, 'mtime_ns': 1793385023716774058, 'ctime_ns': 1793385023716774058, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'template': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-current-main-cold-cap-state-preservation-original01-20261030/UNFILLED-Root-current-continuous-preservation-FIFO-frontier-selection-v2.json', 'sha256': '27688014135717ff29f30430c613939db8e7d24a1fb349b9c41d92aea9a5917d', 'bytes': 4820, 'identity': {'device': 2304, 'inode': 81426628, 'bytes': 4820, 'mtime_ns': 1793383965309480983, 'ctime_ns': 1793383965309480983, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'prior_observation': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/Root-actual-current-preservation-DATA-original01/Root-actual-fresh-current-owner-population-observation.json', 'sha256': 'fbabb40b4086bf40b035ba91d9a9624042168428d10ae05cb769a7d713e06d8a', 'bytes': 29426, 'identity': {'device': 2304, 'inode': 81426633, 'bytes': 29426, 'mtime_ns': 1793384053948458755, 'ctime_ns': 1793384053948458755, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'startup_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-cold-cap12-original01/startup-metadata/startup-job.json', 'sha256': '0f370c2d47047a9aac6676495e140eb1654a12c630a7a4d02d9add92e7dc9b27', 'bytes': 9799, 'identity': {'device': 2304, 'inode': 81429522, 'bytes': 9799, 'mtime_ns': 1793389338247855650, 'ctime_ns': 1793389338247855650, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'held': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-cold-cap12-original01/startup-held/verified-held-before-first-update.json', 'sha256': '47f15ce7778d053561f3160b5b81298fb26a6a115a692ea4838bc8cef79fe652', 'bytes': 6700, 'identity': {'device': 2304, 'inode': 81429521, 'bytes': 6700, 'mtime_ns': 1793389409373076495, 'ctime_ns': 1793389409373076495, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'consumed': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-cold-cap12-original01/startup-held/release-consumed.json', 'sha256': '3e2938eeb6b0879d462d1ac7512a35ba405158d97a9c91adb1750b28fe1ade01', 'bytes': 2763, 'identity': {'device': 2304, 'inode': 81429535, 'bytes': 2763, 'mtime_ns': 1793389571829037404, 'ctime_ns': 1793389571829037404, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'cohort_config': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-cold-cap12-original01/fresh-cohort-metadata-original01/continuous-supervisor-job.json', 'sha256': '639718ea24bfd7c614b272caa99950ecaddf32fd3d6b0707b9bd2ed896bda815', 'bytes': 41632, 'identity': {'device': 2304, 'inode': 81429543, 'bytes': 41632, 'mtime_ns': 1793389571943543056, 'ctime_ns': 1793389571943543056, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'plan': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/Root-prospective-counter-aware8-12-8-engineering-precommit-v3.json', 'sha256': 'dc080a28e61aed43b4825cdbcd54a755929250c6e28766f3fd2f053421c16a90', 'bytes': 7774, 'identity': {'device': 2304, 'inode': 81428721, 'bytes': 7774, 'mtime_ns': 1793387380100067059, 'ctime_ns': 1793387380100067059, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'reader_selection': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-cold-cap12-original01/startup-metadata/Root-prospective-B-counter-aware-measurement-selection.json', 'sha256': 'fe7093259ddd1f8e8a14cc34805bc5ceb98a0b6cea8a582eeab7cdc3cfb7f73a', 'bytes': 6083, 'identity': {'device': 2304, 'inode': 81430568, 'bytes': 6083, 'mtime_ns': 1793389856338723719, 'ctime_ns': 1793389856338723719, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'reader': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/observe_cold_budget_arm_v2.py', 'sha256': '2a28609b40a01ef585ec214162ccb63de6a5a0e6cf4e5745e10a49a47ea8d2ed', 'bytes': 13356, 'identity': {'device': 2304, 'inode': 79964332, 'bytes': 13356, 'mtime_ns': 1793387398973916257, 'ctime_ns': 1793387398973916257, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}

def require(ok,why):
    if not ok:raise ValueError(why)

def ident(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)

def bounded(path,limit=4<<20,*,allow_empty=False):
    p=Path(path);s=p.lstat();require(p.is_absolute()and p.resolve(strict=True)==p and stat.S_ISREG(s.st_mode)and not p.is_symlink()and s.st_uid==os.getuid()and s.st_nlink==1 and (0<=s.st_size if allow_empty else 0<s.st_size)and s.st_size<=limit,'Canonical bounded metadata required')
    raw=p.read_bytes();require(ident(s)==ident(p.stat()),'Metadata changed during read');return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=ident(s)),raw

def read(pin):
    actual,raw=bounded(pin['path']);require(actual==pin,'Selected metadata/source changed');return json.loads(raw)

def sealed(path):
    p,raw=bounded(path);require(p['identity']['mode']=='0o444','Immutable Root evidence required');return p,json.loads(raw)

def put(path,value,*,allow_empty=False):
    raw=value if isinstance(value,bytes)else(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return bounded(path,allow_empty=allow_empty)[0]

def proc(pid):
    p=Path('/proc',str(pid));v=(p/'stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid,starttime_ticks=int(v[19]),parent=int(v[1]),state=v[0],uid=p.stat().st_uid,cgroup=(p/'cgroup').read_text().strip())

def owner(expected):
    r=subprocess.run(['systemctl','--user','show',expected['unit']],capture_output=True,text=True,timeout=15);require(r.returncode==0,'Owner SHOW failed')
    v=dict(x.split('=',1)for x in r.stdout.splitlines()if'='in x);p=proc(expected['pid'])
    require(v.get('Id')==expected['unit']and v.get('MainPID')==str(expected['pid'])and v.get('InvocationID')==expected['invocation_id']and v.get('ControlGroup')==expected['cgroup']and v.get('NRestarts')=='0'and v.get('SubState')=='running'and v.get('ActiveState')=='active','Exact original live unit required')
    require(p['starttime_ticks']==expected['starttime_ticks']and p['uid']==os.getuid()and p['cgroup']=='0::'+expected['cgroup'],'Exact owner birth/UID/cgroup required');return dict(properties=v,process=p)

def prepare(output,expected_source):
    own,_=bounded(Path(__file__).resolve());require(own['sha256']==expected_source and own['identity']['mode']=='0o444','Frozen selected helper required')
    # This gate precedes directory creation, proc/API/unit observation or DATA invocation.
    report_pin,report=sealed(MEASUREMENT/'report.json')
    require(report['schema']=='robotron-cold-budget-arm-observation-v1'and report['status']=='PASS_ENGINEERING_OBSERVATION'and report['arm']=='B'and report['cap']==12,'Only the new counter-aware B PASS report authorizes DATA preparation')
    result_pin,result=sealed(MEASUREMENT/'result.json');require(result['actual_exit']==0 and result['status']==report['status'],'Successful original observation terminal required')
    selection=read(FIXED['reader_selection']);plan=read(FIXED['plan']);require(selection['parent_plan']=={k:FIXED['plan'][k]for k in('path','sha256','bytes')}and selection['future_output']==str(MEASUREMENT)and selection['arm']=='B'and selection['cap']==12 and selection['selected_reader']=={k:FIXED['reader'][k]for k in('path','sha256','bytes')}and selection['original_incomplete_observation_retained']is True,'Exact new reader/plan selection required')
    require(plan['no_original_failure_rescue']is True and plan['original_incomplete_observation']['sha256'],'Old failure must remain history')
    for v in FIXED.values():require(bounded(v['path'])[0]==v,'A selected source/metadata input changed')
    observer_pin,observer=sealed(MEASUREMENT/'owner.json');args=observer['argv']
    require(all(args[k]==v for k,v in dict(arm='B',cap=12,trainer_pid=TRAINER['pid'],trainer_birth=TRAINER['starttime_ticks'],fleet_pid=FLEET['pid'],fleet_birth=FLEET['starttime_ticks']).items()),'Observed B owners differ')
    require(args['output']==str(MEASUREMENT)and args['fleet_status']==str(COHORT/'status.json')and args['held_report']==FIXED['held']['path'],'Observation names another cohort/restore')
    barrier_pin,barrier=sealed(args['barrier']);require(Path(barrier_pin['path']).parent==COHORT/'events'and barrier['kind']=='initial-all192-barrier'and barrier['epoch']==f"{FLEET['pid']}:{FLEET['starttime_ticks']}:{FLEET['invocation_id']}",'Exact initial cohort barrier required')
    first_pin,first=sealed(MEASUREMENT/'sample-00.json');last_pin,last=sealed(MEASUREMENT/'sample-10.json')
    require(all(s['fleet']['initial_admission']['immutable_all192_barrier']==barrier_pin and s['fleet']['original_membership']==barrier['data']['original_membership']for s in(first,last)),'Measurement initial cohort changed')
    cfg=read(FIXED['cohort_config']);job=read(FIXED['startup_job']);held=read(FIXED['held']);consumed=read(FIXED['consumed'])
    require(job['expected_startup_cap']==held['startup_budget']['runtime_cap']==12 and consumed['original_job']==FIXED['startup_job']and consumed['held_report']==FIXED['held'],'Exact B restoration chain required')
    manifest=read(job['restoration_manifest']);prior=read(FIXED['prior_observation']);template=read(FIXED['template'])
    target=Path(output).absolute();require(target.parent==HERE and not target.exists(),'Fresh direct child DATA directory required');target.mkdir(mode=0o700)
    capture_started=time.time()
    owner_before={k:owner(v)for k,v in [('trainer',TRAINER),('fleet',FLEET)]}
    status_pin,status_raw=bounded(COHORT/'status.json',2<<20);status=json.loads(status_raw)
    require(status['schema']=='robotron-continuous-training-static192-snapshot-v2'and 0<=time.time()-status['updated_unix_s']<=5 and status['epoch']==barrier['epoch']and status['initial_admission']['immutable_all192_barrier']==barrier_pin and status['original_membership']==barrier['data']['original_membership'],'Fresh same initial cohort required')
    require(status['trainer']==cfg['trainer']and all(status['supervisor'][k]==v for k,v in dict(pid=FLEET['pid'],birth=FLEET['starttime_ticks'],unit=FLEET['unit'],invocation_id=FLEET['invocation_id'],cgroup=FLEET['cgroup']).items()),'Current cohort owner changed')
    require(set(status['slots'])==set(map(str,range(192)))and status['counts']['active_train']==155 and not status['errors']and status['error_summary']['occurrences']==0,'All original TRAIN actors and error-free cohort required')
    members=set(map(int,(Path('/sys/fs/cgroup'+FLEET['cgroup'])/'cgroup.procs').read_text().split()));require(FLEET['pid']in members,'Fleet absent from owned scope')
    actors=[];live=set();roles=read(cfg['rolemap'])['slot_eval']
    for slot,row in sorted(status['slots'].items(),key=lambda x:int(x[0])):
        original=first['fleet']['slots'][slot];require(all(row[k]==original[k]for k in('original_pid','original_birth','original_slot_sha256','incarnation','eval_only')),'Original cohort membership changed')
        pid=row['original_pid'];birth=row['original_birth'];require(type(pid)is int and type(birth)is int and row['eval_only']is roles[slot],'Typed original actor/role required')
        try:p=proc(pid)
        except FileNotFoundError:p=None
        if p is None or p['starttime_ticks']!=birth:
            require(row['eval_only']is True and pid not in members,'A TRAIN actor disappeared or a foreign birth entered scope');state='absent'
        else:
            path=Path('/proc',str(pid));env=dict(x.split('=',1)for x in(path/'environ').read_bytes().decode().split('\0')if'='in x)
            require(pid in members and p['parent']==FLEET['pid']and p['uid']==os.getuid()and p['cgroup']=='0::'+FLEET['cgroup']and str((path/'exe').resolve())==cfg['mame_argv'][0]and(path/'cmdline').read_bytes().decode().rstrip('\0').split('\0')==cfg['mame_argv'],'Exact actor parent/birth/command/cgroup required')
            after=proc(pid)
            require(env.get('ROBOTRON_CLIENT_SLOT')==slot and env.get('ROBOTRON_EVAL_MODE')==('1'if row['eval_only']else'2')and env.get('ROBOTRON_RETIRE_AFTER_GAME')==('1'if row['eval_only']else'0')and all(after[k]==p[k]for k in('pid','starttime_ticks','parent','uid','cgroup')),'Actor role/source changed during capture');live.add(pid);state=p['state']
        actors.append(dict(pid=pid,starttime_ticks=birth,slot=int(slot),eval_only=row['eval_only'],state=state))
    require(members=={FLEET['pid'],*live}and len({(v['pid'],v['starttime_ticks'])for v in actors})==192,'Foreign or duplicate fleet member')
    persistent={}
    for path in Path('/proc',str(TRAINER['pid']),'task').iterdir():
        try:name=(path/'comm').read_text().strip();born=int((path/'stat').read_text().rsplit(')',1)[1].split()[19])
        except FileNotFoundError:continue
        if name in PERSISTENT:persistent[path.name]=dict(comm=name,starttime_ticks=born)
    require(len(persistent)==5 and {v['comm']for v in persistent.values()}==PERSISTENT,'Exact five persistent native threads required')
    source_expected={Path(v['path']).name:v for v in prior['current_source_pins']};source_expected.update({Path(v['path']).name:v for v in job['source_pins']})
    require(len(source_expected)==15,'Exact fifteen source domain required');sources=[]
    for name,v in sorted(source_expected.items()):
        require(v['path']==str(ROOT/'Scripts/dqn'/name)and bounded(v['path'])[0]==v,'Current source identity changed');sources.append(v)
    ring=dict(schema='robotron-Root-original-ring-storage-metadata-adapter-v1',spec=copy.deepcopy(manifest['ring_and_banks']['spec']),ring=copy.deepcopy(manifest['ring_and_banks']['ring']),source_restoration_manifest=job['restoration_manifest'],actual_ten_storage_object_identities_revalidated_before_stop=True,observed_unix_s=time.time(),array_bodies_read=False)
    require(len(ring['ring']['arrays'])==10,'Exact ten stored replay arrays required')
    for v in ring['ring']['arrays'].values():
        path=Path(v['path']);s=path.lstat();left=v['identity'];require(path.resolve()==path and not path.is_symlink()and stat.S_ISREG(s.st_mode)and(s.st_dev,s.st_ino,s.st_size,s.st_uid,s.st_nlink)==tuple(left[k]for k in('device','inode','size','uid','nlink')),'Original replay storage replaced; no array body read')
    ring_pin=put(target/'actual-B-ring-storage-before.json',ring)
    control_pin,control_raw=bounded(ROOT/'models_dqn/learning_control.json');control=json.loads(control_raw);require(control['lr_scale']==.0625 and control.get('measurement')is None,'Ordinary current recipe required')
    console=prior['console'];c=Path(console);cs=c.stat();require(stat.S_ISREG(cs.st_mode)and cs.st_uid==os.getuid()and cs.st_nlink==1,'Owned console required')
    for fd in('1','2'):
        p=Path('/proc',str(TRAINER['pid']),'fd',fd);require(p.resolve()==c and(p.stat().st_dev,p.stat().st_ino)==(cs.st_dev,cs.st_ino),'Current original console FD differs')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as response:api_raw=response.read((2<<20)+1)
    require(len(api_raw)<=2<<20,'Bounded API required');api_pin=put(target/'actual-B-API-before-DATA.json',api_raw);api=json.loads(api_raw)
    require(0<=time.time()-api['ts']<=5 and api['training_enabled']is True and api['measurement_active']is False,'Fresh ordinary API required')
    for kind in('optimizer','replay'):
        require(all(api['host_pipeline']['learning_exposure'][kind][k]==held['exposure'][kind][k]for k in('process_id','instance_monotonic_ns','epoch','epoch_reason')),'B learning exposure lineage changed')
    logs={};runtime=Path(cfg['journal_directory'])
    for name in('training.csv','games.jsonl','lives.jsonl','completed_clients.jsonl','metadata.json'):
        p=runtime/name;logs[str(p)]=dict(available=p.exists(),identity=ident(p.stat())if p.exists()else None,body_read=False)
    meta_pin,meta_raw=bounded(runtime/'metadata.json');metadata_preimage=put(target/'runtime-metadata.pre-S2.exact.json',meta_raw)
    logs[str(runtime/'metadata.json')].update(body_read=True,source_metadata=meta_pin,immutable_preimage=metadata_preimage)
    owner_after={k:owner(v)for k,v in [('trainer',TRAINER),('fleet',FLEET)]};require(all(owner_before[k]['process']['starttime_ticks']==owner_after[k]['process']['starttime_ticks']for k in owner_before),'Owner changed during DATA capture')
    evidence=put(target/'Root-S2-readonly-capture-evidence.json',dict(measurement_report=report_pin,measurement_result=result_pin,observer=observer_pin,first=first_pin,last=last_pin,barrier=barrier_pin,reader_selection=FIXED['reader_selection'],plan=FIXED['plan'],old_failure=plan['original_incomplete_observation'],owner_before=owner_before,owner_after=owner_after,fleet_status=put(target/'B-fleet-status.exact.json',status_raw),API=api_pin,learning_log_metadata=logs,array_or_model_or_game_log_bodies_read=False))
    selected=copy.deepcopy(template);selected.update(first_current_main_stop=False,owner=TRAINER,fleet=FLEET,expected_current_cap=12,startup_job=FIXED['startup_job'],startup_held=FIXED['held'],startup_release_consumed=FIXED['consumed'],ring_storage_before=ring_pin,measurement_gate=report_pin,Root_capture_evidence=evidence)
    selection_pin=put(target/'Root-actual-B-forward-preservation-selection.json',selected)
    require(time.time()-capture_started<60,'Readonly observation exceeded fresh preparation bound')
    observation=put(target/'Root-fresh-B-owner-population-observation.json',dict(schema='robotron-Root-current-continuous-preservation-observation-v1',observed_unix_s=capture_started,trainer=TRAINER,fleet=FLEET,persistent_native=persistent,actors=actors,current_source_pins=sources,base_control=control_pin,historical_cleanup_receipts=[],console=console,actor_command=cfg['mame_argv'],mame_executable=cfg['mame_argv'][0],Root_readonly_capture=evidence))
    argv=['/usr/bin/python3.12','-I','-B',FIXED['assembler']['path'],'--prepare-stop','--selection',selection_pin['path'],'--selection-sha256',selection_pin['sha256'],'--observation',observation['path'],'--observation-sha256',observation['sha256'],'--output',str(target/'stop-DATA'),'--source-sha256',FIXED['assembler']['sha256']]
    result=subprocess.run(argv,capture_output=True,timeout=60);stdout=put(target/'assembler-stdout.txt',result.stdout,allow_empty=True);stderr=put(target/'assembler-stderr.txt',result.stderr,allow_empty=True)
    command=put(target/'Root-DATA-assembler-command.json',dict(argv=argv,actual_exit=result.returncode,stdout=stdout,stderr=stderr));require(result.returncode==0,'DATA assembler failed; no stop executed')
    prepared_pin,prepared=sealed(target/'stop-DATA/prepared-current-continuous-stop-NOT-LAUNCHED.json')
    return put(target/'prepared-B-forward-S2-DATA-NOT-STOPPED.json',dict(schema='robotron-root-B-forward-S2-DATA-preparation-v1',status='DATA_PREPARED_NOT_STOPPED',source=own,measurement_report=report_pin,selection=selection_pin,observation=observation,evidence=evidence,assembler_command=command,prepared_stop=prepared_pin,Root_controller_argv_NOT_EXECUTED=prepared['Root_controller_argv'],stop_CPU_backup_release_or_launch_executed=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--expected-source-sha256');p.add_argument('--output',type=Path,default=HERE/'actual-DATA-preparation-original01');a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a.output,a.expected_source_sha256)),flush=True)
    else:print('PLAN_ONLY_NO_OBSERVATIONS_OR_WRITES')
