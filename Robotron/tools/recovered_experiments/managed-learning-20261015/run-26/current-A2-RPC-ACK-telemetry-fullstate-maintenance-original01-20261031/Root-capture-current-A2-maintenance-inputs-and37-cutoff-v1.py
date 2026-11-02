"""Root-only current A2 capture and37-score preservation; DATA preparation only.

Default inert. No service stop, controller execution, control/public write, model
or array-body read, CUDA/target import, or policy/quality claim is implemented.
"""
import argparse,copy,hashlib,json,math,os,stat,subprocess,time,urllib.request
from pathlib import Path
ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
V6=ROOT/'logs/managed-learning-20261015/run-26/fleet-only-v6-overlap-handoff-original01-20261031/v6-fleet-original01'
PERSISTENT={'Thread-1 (serve','Thread-2 (_samp','Thread-3 (_cons','Thread-4 (start','Thread-5 (stats'}
FIXED={'proposal': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-A2-RPC-ACK-telemetry-fullstate-maintenance-original01-20261031/PROPOSED-current-A2-maintenance-selection-fields-NOT-LAUNCHABLE-v1.json', 'sha256': 'df5517dca6b4850eb79a67a087ad79be09e68dc1d4aa0f12a01f6976fda45242', 'bytes': 14052, 'identity': {'device': 2304, 'inode': 82733749, 'bytes': 14052, 'mtime_ns': 1793477757495038658, 'ctime_ns': 1793477757495038658, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'assembler': {'bytes': 24007, 'identity': {'bytes': 24007, 'ctime_ns': 1793471846081147948, 'device': 2304, 'inode': 82727975, 'mode': '0o444', 'mtime_ns': 1793471846081092748, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-current-main-cold-cap-state-preservation-original01-20261030/current-A2-LR9375-route-source-only-original01-20261031/prepare_current_A2_LR9375_preservation_v7.py', 'sha256': 'af3ce5206aa5b14789a41f031b31e73ec6d1c9f52832d85eb32408da6c5694be'}, 'prior_observation': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/Root-actual-current-preservation-DATA-original01/Root-actual-fresh-current-owner-population-observation.json', 'sha256': 'fbabb40b4086bf40b035ba91d9a9624042168428d10ae05cb769a7d713e06d8a', 'bytes': 29426, 'identity': {'device': 2304, 'inode': 81426633, 'bytes': 29426, 'mtime_ns': 1793384053948458755, 'ctime_ns': 1793384053948458755, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'cohort_config': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fleet-only-v6-overlap-handoff-original01-20261031/continuous-supervisor-v6-job.json', 'sha256': '0b63a49c421707ed8a17155deeac5779e867fb009810e26a289e9e9483205813', 'bytes': 52398, 'identity': {'device': 2304, 'inode': 80879580, 'bytes': 52398, 'mtime_ns': 1793419045763771162, 'ctime_ns': 1793419045763771162, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'F_closure': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/Root-original2024-and55872-positive-closure-original01.json', 'sha256': 'e1bc2b6c1d942486abdae20b387881d76b11057bfb28f9963e5e2054259bf2ff', 'bytes': 27145, 'identity': {'device': 2304, 'inode': 82733740, 'bytes': 27145, 'mtime_ns': 1793477310024913945, 'ctime_ns': 1793477310024913945, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'F_comparison': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031/Root-complete-S2-versus-LR9375-comparison-original01.json', 'sha256': '2e6743c9d8adb2261e8c237a6db22706ffcebd55c6e24c619853b2081fbe8f94', 'bytes': 3423, 'identity': {'device': 2304, 'inode': 82733746, 'bytes': 3423, 'mtime_ns': 1793477481507102081, 'ctime_ns': 1793477481507102081, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-forward-preservation-S2-original01/actual-stopped600-S2-mixed-bank-preparation-original01/runtime/restoration-manifest.json', 'sha256': 'd10149a2431819c11d1e7c82add0443b04e76ab0b3407ef9d97792c8ea2df990', 'bytes': 422258, 'identity': {'device': 2304, 'inode': 82580707, 'bytes': 422258, 'mtime_ns': 1793393872273623585, 'ctime_ns': 1793393872273623585, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}

def require(ok,why):
    if not ok:raise ValueError(why)

def ident(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)

def bounded(path,limit=4<<20,*,allow_empty=False):
    p=Path(path);s=p.lstat();require(p.is_absolute()and p.resolve(strict=True)==p and stat.S_ISREG(s.st_mode)and not p.is_symlink()and s.st_uid==os.getuid()and s.st_nlink==1 and (0<=s.st_size if allow_empty else 0<s.st_size)and s.st_size<=limit,'Canonical bounded metadata required')
    raw=p.read_bytes();require(ident(s)==ident(p.stat()),'Metadata changed during read');return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=ident(s)),raw

def read(pin):
    actual,raw=bounded(pin['path']);require(actual==pin,'Selected metadata/source changed');return json.loads(raw)

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


def snapshot(target,name,path,limit=2<<20):
    original,raw=bounded(path,limit);saved=put(target/name,raw)
    return json.loads(raw),dict(original=original,immutable_preimage=saved)


def get(target,name,path):
    with urllib.request.urlopen('http://127.0.0.1:8771'+path,timeout=5)as response:raw=response.read((2<<20)+1)
    require(0<len(raw)<=2<<20,'Bounded API response required');saved=put(target/name,raw)
    return json.loads(raw),saved


def exact_status(value,trainer,fleet,cfg):
    expected=dict(pid=fleet['pid'],birth=fleet['starttime_ticks'],unit=fleet['unit'],invocation_id=fleet['invocation_id'],cgroup=fleet['cgroup'])
    require(value['schema']=='robotron-continuous-training-rolling-TRAIN-snapshot-v3'
        and 0<=time.time()-value['updated_unix_s']<=5 and value['trainer']==cfg['trainer']
        and all(value['supervisor'][k]==v for k,v in expected.items())
        and value['epoch']==f"{fleet['pid']}:{fleet['starttime_ticks']}:{fleet['invocation_id']}"
        and set(value['slots'])==set(map(str,range(192))),'Fresh exact current v6 owner/status required')
    # Errors/quarantine are retained raw, never required empty or reclassified.
    return value


def current_connection_map(value,stamp):
    require(value['schema']=='robotron-continuous-active-connections-v1'and value['server_stamp']==stamp
        and value['continuous_training_mode']is True and value['main_measurement_entry_disabled']is True
        and value['measurement_active']is False and 0<=time.time()-value['observed_unix_s']<=5,'Fresh same-Main connection getter required')
    rows=value['connections'];result={}
    for row in rows:
        slot=row['client_slot'];require(type(slot)is int and 0<=slot<192 and slot not in result
            and type(row['client_id'])is int and type(row['eval_only'])is bool
            and type(row['token'])is str and row['token']and type(row['connection_ns'])is int
            and type(row['socket_endpoints'])is dict,'Unique typed actual current slot/connection required')
        result[slot]=row
    require(len(result)==len(rows),'Duplicate current Main connection refused');return result


def event(pin,status,slot,kind):
    require(Path(pin['path']).parent==V6/'events'and pin['identity']['mode']=='0o444','Exact owned immutable v6 event path required')
    value=read(pin)
    require(value['kind']==kind and value['slot']==slot and value['epoch']==status['epoch']
        and value['supervisor']==status['supervisor']and value['incarnation']==status['slots'][str(slot)]['incarnation'],
        'Original v6 event identity differs');return value


def preserve37(target,cfg,roles,trainer,fleet,actors):
    before,before_pin=snapshot(target,'v6-status.cutoff-before.exact.json',V6/'status.json')
    exact_status(before,trainer,fleet,cfg)
    c0,c0pin=get(target,'connections.cutoff-before.exact.json','/api/continuous_training_connections')
    api,apipin=get(target,'Main-API.maintenance-cutoff.exact.json','/api/now')
    c1,c1pin=get(target,'connections.cutoff-after.exact.json','/api/continuous_training_connections')
    after,after_pin=snapshot(target,'v6-status.cutoff-after.exact.json',V6/'status.json')
    exact_status(after,trainer,fleet,cfg)
    keys=('original_pid','original_birth','eval_only','incarnation','state','natural_result','closure')
    require(all(all(before['slots'][s][k]==after['slots'][s][k]for k in keys)for s in roles),
        'An EVAL identity/terminal transition changed across cutoff; preserve capture without inventing a score')
    stamp=cfg['trainer']['server_stamp'];left=current_connection_map(c0,stamp);right=current_connection_map(c1,stamp)
    require(0<=time.time()-api['ts']<=5 and api['training_enabled']is True and api['measurement_active']is False
        and math.isclose(api['lr'],5e-5*.1875,rel_tol=1e-12,abs_tol=0)
        and math.isclose(api['epsilon'],.1,rel_tol=1e-12,abs_tol=1e-12)
        and math.isclose(api['expert_ratio'],.1,rel_tol=1e-12,abs_tol=1e-12),'Fresh exact current A2/LR9375 ordinary API required')
    byslot={}
    for row in api['client_rows']:
        s=row['client_slot'];require(type(s)is int and s not in byslot and type(row['eval'])is bool,'Unique typed Main API slot required');byslot[s]=row
    require(api['client_count']==len(byslot)and sum(not v['eval']for v in byslot.values())==155,'Actual155 TRAIN rows required')
    rows=[];natural=[];pending=[];actor_map={v['slot']:v for v in actors}
    identity=('client_id','client_slot','eval_only','token','connection_ns','socket_endpoints')
    for s in sorted(roles,key=int):
        slot=int(s);row=before['slots'][s];actor=actor_map[slot]
        if row['state']=='closed_eval':
            require(slot not in byslot and slot not in left and slot not in right and row['natural_result']and row['closure'],
                'Completed EVAL must have no current Main row and have both terminal pins')
            n=event(row['natural_result'],before,slot,'natural-result');result=n['data']['result'];closed=event(row['closure'],before,slot,'original-reaped-closure')['data']
            require(n['data']['natural_complete']is True and all(result.get(k)is True for k in('complete','eligible','known_start','eval_only'))
                and result['client_slot']==slot and type(result['client_id'])is int and type(result['score'])is int and result['score']>=0
                and type(result['journal_game_id'])is str and result['journal_game_id']
                and result['boundary_reason']in('score_reset','zero_score_restart'),'Eligible complete unwrapped natural EVAL required')
            require(type(closed['actual_exit'])is int and closed['actual_exit']==0 and closed['original_wait_reaped']is True
                and closed['original_birth_absent']is True and closed['original_pid']==actor['pid']and closed['original_birth']==actor['starttime_ticks']
                and closed['natural_result']==row['natural_result']and closed['restart_censored']is False,'Positive original natural EVAL closure required')
            try:live=proc(actor['pid'])
            except FileNotFoundError:live=None
            require(live is None or live['starttime_ticks']!=actor['starttime_ticks'],'Completed original EVAL birth still present')
            score=dict(slot=slot,eval_only=True,pid=actor['pid'],birth=actor['starttime_ticks'],incarnation=row['incarnation'],
                status='natural_complete',score=result['score'],client_id=result['client_id'],journal_game_id=result['journal_game_id'],
                natural_result=row['natural_result'],closure=row['closure'],original_birth_absent=True)
            natural.append(slot)
        else:
            require(slot in byslot and slot in left and slot in right and byslot[slot]['eval']is True
                and all(left[slot][k]==right[slot][k]for k in identity)and right[slot]['eval_only']is True
                and byslot[slot]['client_id']==right[slot]['client_id']and type(byslot[slot]['score'])is int and byslot[slot]['score']>=0,
                'Missing/changed/unknown pending EVAL identity; no fabricated zero or retrospective TCP adoption')
            score=dict(slot=slot,eval_only=True,pid=actor['pid'],birth=actor['starttime_ticks'],incarnation=row['incarnation'],
                status='maintenance_cutoff_censored',score=byslot[slot]['score'],client_id=byslot[slot]['client_id'],current_connection=right[slot],
                Main_API_row=byslot[slot],journal_game_id=None,game_UID_available=False,
                historical_TCP_or_original_game_identity_adopted=False)
            pending.append(slot)
        rows.append(score)
    require(len(rows)==len(roles)==37 and len(natural)+len(pending)==37
        and {s for s,v in byslot.items()if v['eval']}==set(pending)
        and {s for s,v in left.items()if v['eval_only']}=={s for s,v in right.items()if v['eval_only']}==set(pending)
        and len(left)==len(right)==api['client_count']==155+len(pending),'Exact37 EVAL partition and actual connection counts required')
    values=[v['score']for v in rows];ordered=sorted(values)
    saved=put(target/'cohort37-scores.json',dict(schema='robotron-Root-original37-maintenance-cutoff-v1',observed_unix_s=time.time(),
        cutoff_API_unix_s=api['ts'],owner=trainer,fleet=fleet,rows=rows,n_scored=37,n_completed=len(natural),n_censored=len(pending),
        score_sum=sum(values),mean_score=sum(values)/37,median_score=ordered[18],completed_slots=natural,pending_slots=pending,
        immutable_evidence=dict(status_before=before_pin,status_after=after_pin,connections_before=c0pin,API=apipin,connections_after=c1pin),
        score_scope='Descriptive all37 maintenance snapshot during changing Main training; natural completed scores plus current censored unwrapped scores.',
        original_game_UID_or_historical_connection_continuity_for_pending_claimed=False,frozen_policy_quality_or_promotion_claimed=False,
        zero_score_defaults_or_score_modulus_applied=False))
    return saved,after,after_pin,api,apipin


def capture(output,expected_source):
    own,_=bounded(Path(__file__).resolve());require(own['sha256']==expected_source and own['identity']['mode']=='0o444','Frozen selected capture source required')
    proposal=read(FIXED['proposal']);selected=copy.deepcopy(proposal['selection_fields']);trainer=selected['owner'];fleet=selected['fleet']
    for v in FIXED.values():require(bounded(v['path'])[0]==v,'Selected static source/metadata changed')
    fclosed=read(FIXED['F_closure']);require(fclosed['schema']=='robotron-Root-original-F-pair-and-tabular-positive-closure-v1'
        and fclosed['Root_tool_handle_acknowledgements']['original2024_actual_terminal0']is True
        and fclosed['Root_tool_handle_acknowledgements']['original55872_actual_terminal0']is True
        and fclosed['outer_actual_exit']==fclosed['recorder_actual_exit']==fclosed['final_observer_actual_exit']==0,'Actual F+recorder positive closure required before capture')
    cfg=read(FIXED['cohort_config']);startup=read(selected['startup_job']);held=read(selected['startup_held']);consumed=read(selected['startup_release_consumed'])
    manifest=read(FIXED['manifest']);prior=read(FIXED['prior_observation']);rolemap=read(cfg['rolemap'])['slot_eval']
    require(set(rolemap)==set(map(str,range(192)))and all(type(v)is bool for v in rolemap.values())and sum(rolemap.values())==37,'Original155/37 role map required')
    require(startup['restoration_manifest']==FIXED['manifest']and consumed['original_job']==selected['startup_job']and consumed['held_report']==selected['startup_held'],'Exact A2 restoration chain required')
    target=Path(output).absolute();require(target.parent==HERE and not target.exists(),'Fresh direct-child capture directory required');target.mkdir(mode=0o700)
    capture_started=time.time();owner_before={k:owner(v)for k,v in [('trainer',trainer),('fleet',fleet)]}
    status,status_pin=snapshot(target,'v6-status.population.exact.json',V6/'status.json');exact_status(status,trainer,fleet,cfg)
    members=set(map(int,(Path('/sys/fs/cgroup'+fleet['cgroup'])/'cgroup.procs').read_text().split()));require(fleet['pid']in members,'Original v6 absent from cgroup')
    actors=[];live_pids=set()
    for slot,row in sorted(status['slots'].items(),key=lambda v:int(v[0])):
        pid,born=row['original_pid'],row['original_birth'];require(type(pid)is int and type(born)is int and row['eval_only']is rolemap[slot]
            and type(row['incarnation'])is int and row['incarnation']>0,'Typed actual latest slot/Popen identity required')
        try:current=proc(pid)
        except FileNotFoundError:current=None
        if current is None or current['starttime_ticks']!=born:
            require(row['eval_only']is True and row['state']=='closed_eval'and pid not in members,'Only honestly closed natural EVAL may be absent');state='absent'
        else:
            path=Path('/proc',str(pid));env=dict(v.split('=',1)for v in(path/'environ').read_bytes().decode().split('\0')if'='in v)
            require(pid in members and current['state']not in('Z','X','x')and current['parent']==fleet['pid']and current['uid']==os.getuid()
                and current['cgroup']=='0::'+fleet['cgroup']and str((path/'exe').resolve())==cfg['mame_argv'][0]
                and(path/'cmdline').read_bytes().decode().rstrip('\0').split('\0')==cfg['mame_argv'],'Actual owned latest actor birth/command differs')
            again=proc(pid);require(all(again[k]==current[k]for k in('pid','starttime_ticks','parent','uid','cgroup'))
                and env.get('ROBOTRON_CLIENT_SLOT')==slot and env.get('ROBOTRON_EVAL_MODE')==('1'if row['eval_only']else'2')
                and env.get('ROBOTRON_RETIRE_AFTER_GAME')==('1'if row['eval_only']else'0'),'Actual actor role/source changed during capture')
            state=current['state'];live_pids.add(pid)
        actors.append(dict(pid=pid,starttime_ticks=born,slot=int(slot),eval_only=row['eval_only'],state=state,incarnation=row['incarnation'],
            supervisor_state=row['state'],physical_binding_history_count=row['physical_binding_history_count']))
    require(members=={fleet['pid'],*live_pids}and len({(v['pid'],v['starttime_ticks'])for v in actors})==192,'Unknown or duplicate actual fleet cgroup member')
    persistent={}
    for path in Path('/proc',str(trainer['pid']),'task').iterdir():
        try:name=(path/'comm').read_text().strip();born=int((path/'stat').read_text().rsplit(')',1)[1].split()[19])
        except FileNotFoundError:continue
        if name in PERSISTENT:persistent[path.name]=dict(comm=name,starttime_ticks=born)
    require(len(persistent)==5 and {v['comm']for v in persistent.values()}==PERSISTENT,'Exact5 original persistent native tasks required')
    expected={Path(v['path']).name:v for v in prior['current_source_pins']};expected.update({Path(v['path']).name:v for v in startup['source_pins']})
    require(len(expected)==15,'Exact15 current source domain required');sources=[]
    for name,v in sorted(expected.items()):require(v['path']==str(ROOT/'Scripts/dqn'/name)and bounded(v['path'])[0]==v,'Current15 source identity changed');sources.append(v)
    ring=dict(schema='robotron-Root-original-ring-storage-metadata-adapter-v1',spec=copy.deepcopy(manifest['ring_and_banks']['spec']),ring=copy.deepcopy(manifest['ring_and_banks']['ring']),
        source_restoration_manifest=FIXED['manifest'],actual_ten_storage_object_identities_revalidated_before_stop=True,observed_unix_s=time.time(),array_bodies_read=False)
    require(len(ring['ring']['arrays'])==10,'Exact10 original replay arrays required')
    for v in ring['ring']['arrays'].values():
        path=Path(v['path']);s=path.lstat();require(path.resolve()==path and not path.is_symlink()and stat.S_ISREG(s.st_mode)
            and(s.st_dev,s.st_ino,s.st_size,s.st_uid,s.st_nlink)==tuple(v['identity'][k]for k in('device','inode','size','uid','nlink')),'Replay storage object changed; no array body was read')
    ring_pin=put(target/'actual-A2-ring-storage-before.json',ring)
    control_pin,raw=bounded(ROOT/'models_dqn/learning_control.json');control=json.loads(raw)
    require(control_pin['sha256']==selected['expected_control_sha256']and type(control['lr_scale'])is float and control['lr_scale']==.1875 and control.get('measurement')is None,'Exact currentc130/.1875 control required')
    console=Path('/proc',str(trainer['pid']),'fd','1').readlink();require(console.is_absolute()and console.resolve()==console and console.name=='trainer-console.log','Actual canonical trainer-console.log required')
    cs=console.stat();require(stat.S_ISREG(cs.st_mode)and cs.st_uid==os.getuid()and cs.st_nlink==1,'Owned trainer console required')
    for fd in('1','2'):
        path=Path('/proc',str(trainer['pid']),'fd',fd);require(path.resolve()==console and(path.stat().st_dev,path.stat().st_ino)==(cs.st_dev,cs.st_ino),'Main originalstdout/stderr binding differs')
    logs={};runtime=Path(cfg['journal_directory'])
    for name in('training.csv','games.jsonl','lives.jsonl','completed_clients.jsonl','metadata.json'):
        path=runtime/name;logs[str(path)]=dict(available=path.exists(),identity=ident(path.stat())if path.exists()else None,body_read=False)
    meta_pin,meta_raw=bounded(runtime/'metadata.json');metadata_preimage=put(target/'runtime-metadata.pre-maintenance.exact.json',meta_raw)
    logs[str(runtime/'metadata.json')].update(body_read=True,source_metadata=meta_pin,immutable_preimage=metadata_preimage)
    cutoff,after,after_pin,api,api_pin=preserve37(target,cfg,[s for s in rolemap if rolemap[s]],trainer,fleet,actors)
    for actor in actors:
        row=after['slots'][str(actor['slot'])];require((row['original_pid'],row['original_birth'],row['eval_only'],row['incarnation'])==(actor['pid'],actor['starttime_ticks'],actor['eval_only'],actor['incarnation']),'Latest slot/Popen changed before DATA')
    for kind in('optimizer','replay'):
        require(all(api['host_pipeline']['learning_exposure'][kind][k]==held['exposure'][kind][k]for k in('process_id','instance_monotonic_ns','epoch','epoch_reason')),'Actual A2 exposure instance/epoch changed')
    owner_after={k:owner(v)for k,v in [('trainer',trainer),('fleet',fleet)]};require(all(owner_before[k]['process']['starttime_ticks']==owner_after[k]['process']['starttime_ticks']for k in owner_before),'Original owner changed during capture')
    require(bounded(ROOT/'models_dqn/learning_control.json')[0]==control_pin,'Currentcontrol changed during capture')
    evidence=put(target/'Root-current-A2-readonly-capture-evidence.json',dict(source=own,static_proposal=FIXED['proposal'],F_closure=FIXED['F_closure'],F_comparison=FIXED['F_comparison'],
        owner_before=owner_before,owner_after=owner_after,initial_v6_status=status_pin,final_v6_status=after_pin,API=api_pin,cohort37_cutoff=cutoff,
        log_metadata=logs,known_quarantine_and_errors_preserved=True,historical_cleanup_success_or_TCP_adoption_claimed=False,array_model_game_log_bodies_read=False))
    selected.update(ring_storage_before=ring_pin,preserved_original_EVAL37_scores=cutoff,F_positive_owned_closeout=FIXED['F_closure'],F_tabular_runner_positive_closeout=FIXED['F_closure'],F_decision_history=FIXED['F_comparison'],Root_capture_evidence=evidence)
    selection_pin=put(target/'Root-actual-current-A2-maintenance-selection.json',selected)
    require(time.time()-capture_started<60,'Currentcapture exceeded fresh60s preparation bound')
    observation=put(target/'Root-fresh-current-A2-owner-population-observation.json',dict(schema='robotron-Root-current-continuous-preservation-observation-v1',observed_unix_s=capture_started,
        trainer=trainer,fleet=fleet,persistent_native=persistent,actors=actors,current_source_pins=sources,base_control=control_pin,historical_cleanup_receipts=[],
        console=str(console),actor_command=cfg['mame_argv'],mame_executable=cfg['mame_argv'][0],Root_readonly_capture=evidence))
    argv=['/usr/bin/python3.12','-I','-B',FIXED['assembler']['path'],'--prepare-stop','--selection',selection_pin['path'],'--selection-sha256',selection_pin['sha256'],
        '--observation',observation['path'],'--observation-sha256',observation['sha256'],'--output',str(target/'stop-DATA'),'--source-sha256',FIXED['assembler']['sha256']]
    result=subprocess.run(argv,capture_output=True,timeout=60);stdout=put(target/'assembler-stdout.txt',result.stdout,allow_empty=True);stderr=put(target/'assembler-stderr.txt',result.stderr,allow_empty=True)
    command=put(target/'Root-DATA-assembler-command.json',dict(argv=argv,actual_exit=result.returncode,stdout=stdout,stderr=stderr));require(result.returncode==0,'DATA-only assembler failed; no stop was executed')
    prepared_pin,prepared_raw=bounded(target/'stop-DATA/prepared-current-continuous-stop-NOT-LAUNCHED.json');prepared=json.loads(prepared_raw)
    return put(target/'prepared-current-A2-maintenance-DATA-NOT-STOPPED.json',dict(schema='robotron-root-current-A2-maintenance-DATA-preparation-v1',status='DATA_PREPARED_NOT_STOPPED',source=own,
        selection=selection_pin,observation=observation,evidence=evidence,cohort37_cutoff=cutoff,assembler_command=command,prepared_stop=prepared_pin,
        Root_controller_argv_NOT_EXECUTED=prepared['Root_controller_argv'],stop_CPU_backup_release_install_or_launch_executed=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',action='store_true');p.add_argument('--expected-source-sha256');p.add_argument('--output',type=Path,default=HERE/'actual-current-A2-maintenance-DATA-original01');a=p.parse_args()
    if a.capture:print(json.dumps(capture(a.output,a.expected_source_sha256)),flush=True)
    else:print('PLAN_ONLY_NO_OBSERVATIONS_OR_WRITES')
