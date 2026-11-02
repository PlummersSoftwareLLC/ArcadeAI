"""Create NEW-cohort immutable PIDFD anchor carrier/selection DATA only.

The unchanged fe306 witness consumes a static-v1 schema discriminator and only
slot_eval + continuous.original_slots. This explicitly purpose-limited carrier
is not a current/static/physical health case or qualification. All physical
anchors below come from the NEW v4 cohort's immutable actual producer events.
Default inert; Root alone prepares data, opens pidfds, launches and operates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

FIXED={'config': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/live-original01/startup-repair-original02/Root-prepared-fleet-v4-new-cohort-original01/continuous-supervisor-job.json', 'sha256': '15162bb5c3b239358e845d0e4fba8fb4e623ea09968b9021f4f74221106466b0', 'bytes': 33285, 'identity': {'device': 2304, 'inode': 85328246, 'bytes': 33285, 'mtime_ns': 1793294765576109707, 'ctime_ns': 1793294765576109707, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'membership': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/live-original01/startup-repair-original02/continuous-fleet-v4-new-cohort-original01/events/00000607-original192-membership.json', 'sha256': '250dd8887152af05fb22dee62c0ea22e633a3447746f22957dbcc4ca5fd0e6f4', 'bytes': 862890, 'identity': {'device': 2304, 'inode': 85333366, 'bytes': 862890, 'mtime_ns': 1793294946328947221, 'ctime_ns': 1793294946328947221, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'barrier': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/live-original01/startup-repair-original02/continuous-fleet-v4-new-cohort-original01/events/00000608-initial-all192-barrier.json', 'sha256': '2c4df52d43a39beca80be86bc4a4eb36bd458fb46fb7bb4b07b859d013f0d8f7', 'bytes': 157422, 'identity': {'device': 2304, 'inode': 85333367, 'bytes': 157422, 'mtime_ns': 1793294946333149151, 'ctime_ns': 1793294946333149151, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'owner_API_capture': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/fleet-snapshot-overflow-recovery-original01-20261029/new-cohort-owner-API-capture-original01/Root-owner-and-API-metadata-capture.json', 'sha256': 'fe3ad29af165ee70329b369c8b06fdd7f20d81d1b6f3cf928561848b8611bd71', 'bytes': 2325, 'identity': {'device': 2304, 'inode': 85333595, 'bytes': 2325, 'mtime_ns': 1793295418626161156, 'ctime_ns': 1793295418626161156, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'prior_history_case': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-physical-original192-original02/actual-physical-original192-case-original01/physical-original192-main-case.json', 'sha256': 'cc18250b10af2b444eebc87163a3cc710a75bf92ccbb954396c25e600edbe94d', 'bytes': 1267814, 'identity': {'device': 2304, 'inode': 85328257, 'bytes': 1267814, 'mtime_ns': 1793290332975214602, 'ctime_ns': 1793290332975214602, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'witness_source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/EVAL-pidfd-exit-witness-original01-preparation/hold_original_EVAL_pidfd_exits_v1.py', 'sha256': 'fe306753c9cbb20e715b76d60c116ef9ce47a768c1a1afe0b00c03eac02a095c', 'bytes': 16836, 'identity': {'device': 2304, 'inode': 85328172, 'bytes': 16836, 'mtime_ns': 1793287281184749129, 'ctime_ns': 1793287331238910888, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capability': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/live-original01/startup-repair-original02/pidfd-exit-capability-own-synthetic-original01/Root-actual-pidfd-exit-capability-results.json', 'sha256': '062f042870a5c6d546156734128d32455e30814f6e2d258b6de6bc698ab8dbca', 'bytes': 4259, 'identity': {'device': 2304, 'inode': 85328170, 'bytes': 4259, 'mtime_ns': 1793286873064044285, 'ctime_ns': 1793286873064044285, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
SLOTS=set(map(str,range(192)))
FIELDS={'eval_only','incarnation','original_child','spawn_intent','original_child_receipt','connection_binding'}


def require(ok,reason):
    if not ok:raise ValueError(reason)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def pin(path):
    path=Path(path);require(path.is_absolute()and path.resolve(strict=True)==path
        and not path.is_symlink(),'Canonical regular metadata path required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        a=identity(os.fstat(fd));require(stat.S_ISREG(os.fstat(fd).st_mode)
            and 0<=a['bytes']<=2_000_000,'Bounded metadata only')
        with os.fdopen(os.dup(fd),'rb')as f:b=f.read(2_000_001)
        require(len(b)==a['bytes']and identity(os.fstat(fd))==a
            and identity(path.lstat())==a,'Selected metadata changed')
    finally:os.close(fd)
    return dict(path=str(path),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=a)


def read(p):
    require(pin(p['path'])==p and p['identity']['mode']=='0o444'
        and p['identity']['uid']==os.getuid()and p['identity']['nlink']==1,
        'Exact immutable owned actual metadata required')
    b=Path(p['path']).read_bytes();require(hashlib.sha256(b).hexdigest()==p['sha256']and pin(p['path'])==p,
        'Selected metadata changed while reading')
    return json.loads(b)


def put(path,value):
    b=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode();require(len(b)<=2_000_000,'Bounded DATA only')
    with path.open('xb')as f:f.write(b);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return pin(path)


def prepare(output,witness_output,witness_unit,source_sha):
    own=pin(Path(__file__).resolve());require(own['sha256']==source_sha
        and own['identity']['mode']=='0o444','Exact frozen Root-selected metadata constructor required')
    cfg=read(FIXED['config']);member=read(FIXED['membership']);barrier=read(FIXED['barrier'])
    capture=read(FIXED['owner_API_capture']);owners=read(capture['owners'])
    api=read(capture['baseline_API']);bracket=read(capture['baseline_API_capture'])
    require(bracket['value']==api and bracket['raw_wire'].encode()==Path(capture['baseline_API']['path']).read_bytes()
        and bracket['sha256']==capture['baseline_API']['sha256'],'Actual archived raw/API metadata bracket differs')
    prior=read(FIXED['prior_history_case']);rolemap=read(cfg['rolemap']);roles=rolemap['slot_eval']
    require(set(roles)==SLOTS and all(type(v)is bool for v in roles.values())and sum(roles.values())==37,
        'Exact192 fixed155TRAIN/37EVAL rolemap required')
    sup=member['supervisor'];trainer=cfg['trainer'];authority=read(cfg['source_authority'])
    require(sup['pid']==909646 and sup['birth']==17859362
        and sup['invocation_id']=='5648e44c5c0d415ebfc7d109256f4676'
        and sup['source']['sha256']=='bc2f11eafa974b693d767ca5291a69655b37e79cb5d47f0db03ee10135dc77d1'
        and trainer==prior['continuous']['trainer']==authority['trainer']
        and trainer['pid']==654315 and trainer['birth']==16564768,
        'Only NEW actual v4 fleet and unchanged original trainer authority required')
    for role,anchor in [('fleet',sup),('trainer',trainer)]:
        row=owners[role];proc=row['process'];require(row['unit']==anchor['unit']
            and row['invocation']==anchor['invocation_id']and proc['pid']==anchor['pid']
            and proc['starttime_ticks']==anchor['birth']and proc['cgroup']==anchor['cgroup'],
            'Fresh Root owner record does not join this actual original owner')
    epoch=f"{sup['pid']}:{sup['birth']}:{sup['invocation_id']}"
    def event(p,kind,slot,inc=1):
        x=read(p);require(x['schema']=='robotron-continuous-training-event-v1'
            and x['mode']=='CONTINUOUS_TRAIN155_EVAL37_ONCE'and x['epoch']==epoch
            and x['supervisor']==sup and x['trainer']==trainer
            and x['source_authority']==cfg['source_authority']and x['kind']==kind
            and x['slot']==slot and x['incarnation']==inc,'Immutable NEW-cohort event binding differs')
        return x
    require(event(FIXED['membership'],'original192-membership',None,0)==member
        and event(FIXED['barrier'],'initial-all192-barrier',None,0)==barrier,
        'Actual new membership/barrier bindings differ')
    original=member['data']['original_slots'];b=barrier['data']
    require(set(original)==SLOTS and b['slots']==list(range(192))and b['slot_eval']==roles
        and b['original_membership']==FIXED['membership']and set(b['physical_connections'])==SLOTS
        and member['monotonic_ns']<=barrier['monotonic_ns'],
        'Exact new original192 immutable physical bootstrap required')
    expected_argv=['/usr/bin/python3.12','-I','-B',sup['source']['path'],'--execute','--config',
        FIXED['config']['path'],'--config-sha256',FIXED['config']['sha256'],'--source-sha256',sup['source']['sha256']]
    require(owners['fleet']['process']['command']==expected_argv,'Fresh actual v4 source/config argv differs')
    previous_pairs={(r['original_child']['pid'],r['original_child']['birth'])for r in prior['continuous']['original_slots'].values()}
    pairs=set();cids=set();tokens=set();selected={}
    for slot,row in original.items():
        require(set(row)==FIELDS and row['incarnation']==1 and row['eval_only']is roles[slot],
            'New immutable original row shape/role/incarnation differs')
        child=row['original_child'];spawn=event(row['spawn_intent'],'spawn-intent',int(slot))
        born=event(row['original_child_receipt'],'original-child',int(slot));bound=event(row['connection_binding'],'physical-connection',int(slot))
        actor=bound['data']['actor'];conn=bound['data']['connection'];pair=(child['pid'],child['birth'])
        require(pair not in pairs and pair not in previous_pairs and child['parent']==sup['pid']
            and child['cgroup']==sup['cgroup']and all(actor[k]==child[k]for k in('pid','birth','parent','cgroup'))
            and actor['uid']==os.getuid()==1001 and actor['command']==cfg['mame_argv']
            and actor['exe']=='/usr/games/mame'and child['launch_argv']==cfg['launch_argv'],
            'New original physical MAME identity/source/parent differs or adopts old cohort')
        expected=dict(cfg['actor_common_environment'],ROBOTRON_CLIENT_SLOT=slot,ROBOTRON_ACTOR_ROUND='1',
            ROBOTRON_EVAL_MODE='1'if roles[slot]else'2',ROBOTRON_RETIRE_AFTER_GAME='1'if roles[slot]else'0',
            ROBOTRON_PREVIEW_CLIENT='1'if slot=='0'else'0')
        require(child['controlled_env']==expected and actor['environment']==expected
            and conn['client_slot']==int(slot)and conn['eval_only']is roles[slot]
            and conn['client_id']not in cids and conn['token']not in tokens
            and b['physical_connections'][slot]==row['connection_binding'],
            'New actual controlled role/environment/connection identity differs')
        require(spawn['data']['argv']==cfg['launch_argv']and spawn['data']['previous_closure']is None
            and born['data']['spawn_intent']==row['spawn_intent']
            and born['data']['original_child']==dict(child,controlled_env=None)
            and spawn['monotonic_ns']<=born['monotonic_ns']<=bound['monotonic_ns']<=barrier['monotonic_ns']
            and bound['monotonic_ns']-born['monotonic_ns']<=5_000_000_000,
            'New original Popen/bind chronology differs')
        pairs.add(pair);cids.add(conn['client_id']);tokens.add(conn['token'])
        if roles[slot]:selected[slot]=dict(pid=child['pid'],birth=child['birth'],parent=child['parent'],
            uid=actor['uid'],initial_connection_binding=row['connection_binding'])
    require(len(selected)==37 and re.fullmatch(r'robotron-[A-Za-z0-9_.@-]+\.service',witness_unit)
        and witness_unit!='robotron-EVAL37-pidfd-exit-witness-original01-20261029.service',
        'Fresh witness unit and exact37 originals required')
    output=Path(output).absolute();witness_output=Path(witness_output).absolute()
    require(output.parent.resolve(strict=True)==Path(__file__).resolve().parent and not output.exists()
        and witness_output.parent.resolve(strict=True)==witness_output.parent and not witness_output.exists()
        and output!=witness_output,'Exclusive new carrier/witness paths required')
    output.mkdir(mode=0o700)
    carrier=put(output/'new-v4-original192-pidfd-anchor-carrier-NOT-HEALTH-CASE.json',dict(
        schema='robotron-continuous-static192-health-case-v1',
        purpose='PHYSICAL_ANCHOR_HISTORY_ONLY_FOR_UNCHANGED_FE306_CONSUMER_NOT_A_HEALTH_CASE',
        slot_eval=roles,continuous=dict(original_slots=original),
        provenance=dict(supervisor_config=FIXED['config'],membership=FIXED['membership'],barrier=FIXED['barrier'],
            actual_new_owner_API_capture=FIXED['owner_API_capture'],prior_case_used_only_to_reject_old_birth_adoption=FIXED['prior_history_case']),
        static_or_physical_runtime_health_or_engineering_or_quality_qualified=False))
    selection=put(output/'Root-new-v4-original37-EVAL-pidfd-witness-selection.json',dict(
        schema='robotron-root-original37-EVAL-pidfd-witness-selection-v1',nonce=uuid.uuid4().hex,
        unit=witness_unit,output=str(witness_output),original_case=carrier,capability=FIXED['capability'],originals=selected))
    payload=['/usr/bin/python3.12','-I','-B',FIXED['witness_source']['path'],'--execute',
        '--selection',selection['path'],'--selection-sha256',selection['sha256'],
        '--expected-source-sha256',FIXED['witness_source']['sha256']]
    return put(output/'prepared-new-v4-pre-pidfd-carrier-and-selection-NOT-QUALIFIED.json',dict(
        schema='robotron-new-v4-original192-pre-pidfd-carrier-preparation-v1',status='DATA_PREPARED_NOT_HEALTH_OR_LAUNCH_QUALIFIED',
        source=own,retained_inputs=FIXED,carrier=carrier,witness_selection=selection,witness_source=FIXED['witness_source'],
        Root_payload_argv=payload,Root_owned_service_launch_argv=['systemd-run','--user','--unit='+witness_unit,
            '--property=Type=exec','--property=Restart=no','--property=RemainAfterExit=yes',
            '--property=RuntimeMaxSec=86400','--property=CPUQuota=200%','--property=MemoryMax=128M',
            '--property=MemorySwapMax=0','--property=TasksMax=64','--property=TimeoutStopSec=5',
            '--property=SendSIGKILL=no','--',*payload],
        future_actual_new_holder_and_anchors_and_final_physical_case=None,
        no_old_cohort_identity_or_witness_adoption=True,no_input_history_dropped_by_final_case_claimed_yet=False,
        no_source_import_live_probe_kernel_operation_or_launch=True))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--output',type=Path);p.add_argument('--witness-output',type=Path);p.add_argument('--witness-unit')
    p.add_argument('--expected-source-sha256');a=p.parse_args()
    if not a.prepare:print('SOURCE_ONLY_INERT_NO_READS_OR_ACTIONS');return
    print(json.dumps(prepare(a.output,a.witness_output,a.witness_unit,a.expected_source_sha256)),flush=True)


if __name__=='__main__':main()
