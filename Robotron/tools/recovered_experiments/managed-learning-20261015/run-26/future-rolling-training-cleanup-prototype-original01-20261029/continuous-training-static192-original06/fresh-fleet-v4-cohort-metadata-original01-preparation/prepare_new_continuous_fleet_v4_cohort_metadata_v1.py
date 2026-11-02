"""Prepare one NEW fleet-v4 config and drop-in DATA; never install or launch.

The original failed cohort remains history. This program only reads bounded
source/metadata and writes exclusive files inside its own selected output.
The live trainer, models, replay, Lua, actor recipe and unit files are untouched.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

FIXED={'base_config': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/live-original01/startup-repair-original02/continuous-supervisor-job-original02.json', 'sha256': '5e7b6626798459421855105e846cfa9402f984453bb93dd65913da80e8374323', 'bytes': 27856, 'identity': {'device': 2304, 'inode': 85226755, 'bytes': 27856, 'mtime_ns': 1793282588201751971, 'ctime_ns': 1793282588201751971, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'base_applied_dropin': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/live-original01/startup-repair-original02/Root-actual-fleet95-original02-applied.conf', 'sha256': '4dc3fc59f611d9106070b3bff550125561ccb8509422a49ec5712a53fb1b3c2d', 'bytes': 808, 'identity': {'device': 2304, 'inode': 85226758, 'bytes': 808, 'mtime_ns': 1793282588203822277, 'ctime_ns': 1793282588203822277, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'supervisor_source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/continuous_training_fleet_v4.py', 'sha256': 'bc2f11eafa974b693d767ca5291a69655b37e79cb5d47f0db03ee10135dc77d1', 'bytes': 36204, 'identity': {'device': 2304, 'inode': 85235752, 'bytes': 36204, 'mtime_ns': 1793294287369521367, 'ctime_ns': 1793294406988263416, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'supervisor_source_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/independent-continuous-fleet-v4-bounded-errors-and-journal-source-peer-v1.json', 'sha256': '89e69d6e770545725f3ae308ee32b2beca75a8577713e7919b799ae5cfba4557', 'bytes': 5073, 'identity': {'device': 2304, 'inode': 85235756, 'bytes': 5073, 'mtime_ns': 1793294453636623859, 'ctime_ns': 1793294453636623859, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'unit_base': {'path': '/home/dave/.config/systemd/user/robotron-mame.service', 'sha256': '44e666804c47c6b3ca24370cf10f6a5611155d554add2d472b9ae2b6392bf0af', 'bytes': 572, 'identity': {'device': 2304, 'inode': 79724892, 'bytes': 572, 'mtime_ns': 1791933574937576166, 'ctime_ns': 1791933574937576166, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'unit90': {'path': '/home/dave/.config/systemd/user/robotron-mame.service.d/90-power-recovery.conf', 'sha256': '72cdfddc652ad30f956b980603ea3fb91526fda5bad11c06ef1089f01bbbbfd7', 'bytes': 1638, 'identity': {'device': 2304, 'inode': 79725289, 'bytes': 1638, 'mtime_ns': 1793130275525069460, 'ctime_ns': 1793130275525069460, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'unit95': {'path': '/home/dave/.config/systemd/user/robotron-mame.service.d/95-continuous-training.conf', 'sha256': '4dc3fc59f611d9106070b3bff550125561ccb8509422a49ec5712a53fb1b3c2d', 'bytes': 808, 'identity': {'device': 2304, 'inode': 79725797, 'bytes': 808, 'mtime_ns': 1793282588203329508, 'ctime_ns': 1793282588203329508, 'mode': '0o644', 'uid': 1001, 'nlink': 1}}}
LIMIT=2_000_000
OVERRIDDEN={'ROBOTRON_CLIENT_SLOT','ROBOTRON_ACTOR_ROUND','ROBOTRON_EVAL_MODE',
            'ROBOTRON_PREVIEW_FPS','ROBOTRON_RETIRE_AFTER_GAME'}


def require(ok,reason):
    if not ok:raise ValueError(reason)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def pin(path):
    path=Path(path);require(path.is_absolute()and path.resolve(strict=True)==path
        and not path.is_symlink(),'Canonical regular metadata/source path required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=identity(os.fstat(fd));require(stat.S_ISREG(os.fstat(fd).st_mode)
            and before['bytes']<=LIMIT,'Bounded source/metadata required; no model or array bodies')
        with os.fdopen(os.dup(fd),'rb')as f:raw=f.read(LIMIT+1)
        require(len(raw)==before['bytes']and identity(os.fstat(fd))==before
            and identity(path.lstat())==before,'Source/metadata changed during read')
    finally:os.close(fd)
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)


def raw(entry,immutable=True):
    require(pin(entry['path'])==entry and entry['identity']['uid']==os.getuid()
        and entry['identity']['nlink']==1
        and(not immutable or entry['identity']['mode']=='0o444'),'Exact selected owned source/metadata required')
    data=Path(entry['path']).read_bytes()
    require(hashlib.sha256(data).hexdigest()==entry['sha256']and pin(entry['path'])==entry,
            'Selected metadata changed')
    return data


def read(entry):return json.loads(raw(entry))


def put(path,value=None,data=None):
    require((value is None)!=(data is None),'One exact data payload required')
    b=data if data is not None else(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    require(len(b)<=LIMIT,'Bounded prepared DATA required')
    with path.open('xb')as f:f.write(b);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return pin(path)


def prepare(output,cohort_output,expected_source_sha):
    own=pin(Path(__file__).resolve());require(own['sha256']==expected_source_sha
        and own['identity']['mode']=='0o444','Exact frozen metadata constructor required')
    base=read(FIXED['base_config']);before95=raw(FIXED['base_applied_dropin']).decode()
    source=FIXED['supervisor_source'];peer=read(FIXED['supervisor_source_peer']);raw(source)
    require(peer['source']==source and peer['status'].startswith('SOURCE_ABI_GO'),
            'Exact independent v4 source peer required')
    unitfiles={key:raw(FIXED[key],immutable=False)for key in('unit_base','unit90','unit95')}
    require(unitfiles['unit95'].decode()==before95,'Current95 differs from retained actual failed-cohort definition')
    require(base['schema']=='robotron-continuous-training-supervisor-job-v1'
        and base['mode']=='CONTINUOUS_TRAIN155_EVAL37_ONCE'and base['unit']=='robotron-mame.service'
        and base['original_attempt']==1 and base['no_retry']is True,'Actual base config ABI differs')
    trainer=base['trainer'];require(trainer['pid']==654315 and trainer['birth']==16564768
        and trainer['invocation_id']=='c9a7ad073c8043af8b9499acb4ae4372'
        and trainer['uid']==os.getuid()==1001
        and trainer['server_stamp']==dict(pid=654315,birth=16564768,
            source_sha256='a076501b0601a637b91269a41572be60496754ad1da4b04385d77c51b9f34423'),
        'Preserved original trainer/server source differs')
    roles=read(base['rolemap'])['slot_eval'];require(set(roles)==set(map(str,range(192)))
        and all(type(v)is bool for v in roles.values())and sum(roles.values())==37,
        'Exactly155TRAIN/37EVAL original roles required')
    require(not OVERRIDDEN.intersection(base['parent_environment'])
        and OVERRIDDEN<=set(base['input_environment_keys']),
        'Parent environment collides with literal per-slot spawn kwargs')
    require(base['launch_argv'][1:]==base['mame_argv'][1:]
        and base['mame_argv'][0]=='/usr/games/mame'
        and base['launch_argv'][0].endswith('/mame_with_roles.sh'),
        'Exact direct role-wrapper and literal MAME tail required')
    authority=read(base['source_authority']);require(authority['trainer']==trainer,
        'Existing unchanged trainer startup authority differs')
    held={v['path']:v for v in base['inputs']}
    lua=held[base['mame_argv'][-1]];require(lua['sha256'].startswith('2d478'),
        'Selected existing actual Lua source differs')
    for value in base['inputs']:raw(value,immutable=False)
    directory=Path(output).absolute();cohort=Path(cohort_output).absolute()
    require(directory.parent.resolve(strict=True)==directory.parent and not directory.exists()
        and cohort.parent.resolve(strict=True)==cohort.parent and not cohort.exists()
        and cohort!=Path(base['output'])and directory!=cohort and directory not in cohort.parents
        and cohort not in directory.parents,'Exclusive separate new metadata/cohort paths required')
    for path in(directory,cohort,Path(source['path'])):
        require(re.fullmatch(r'[A-Za-z0-9_./-]+',str(path))is not None,'Unit argv paths must need no escaping')
    directory.mkdir(mode=0o700)
    archives={key:put(directory/('previous-'+key+'.exact'),data=data)for key,data in unitfiles.items()}
    oldsource=[v for v in base['inputs']if Path(v['path']).name=='continuous_training_fleet_v3.py']
    require(len(oldsource)==1,'Exact previous selected supervisor source required')
    inputs=list(base['inputs'])  # Preserve the old frozen source as explicit history.
    inputs += [source,FIXED['supervisor_source_peer'],FIXED['base_config'],FIXED['base_applied_dropin'],own,*archives.values()]
    cfg=copy.deepcopy(base);cfg['output']=str(cohort);cfg['inputs']=list({v['path']:v for v in inputs}.values())
    require(all(cfg[key]==base[key]for key in base if key not in('output','inputs')),
        'Actor/Main/unit/role/recipe/environment fields must remain exact')
    config=put(directory/'continuous-supervisor-job.json',value=cfg)
    argv=['/usr/bin/python3.12','-I','-B',source['path'],'--execute','--config',config['path'],
        '--config-sha256',config['sha256'],'--source-sha256',source['sha256']]
    lines=before95.splitlines();positions=[i for i,line in enumerate(lines)if line.startswith('ExecStart=')and line!='ExecStart=']
    require(len(positions)==1 and 'ExecStart='in lines and 'Type=exec'in lines and 'Restart=no'in lines,
        'Actual retained95 override shape differs')
    lines[positions[0]]='ExecStart='+' '.join(argv)
    dropin=put(directory/'95-continuous-training.conf',data=('\n'.join(lines)+'\n').encode())
    return put(directory/'prepared-new-fleet-v4-cohort-DATA-NOT-LAUNCHED.json',value=dict(
        schema='robotron-root-new-fleet-v4-cohort-metadata-preparation-v1',status='DATA_PREPARED_NOT_LAUNCH_AUTHORITY',
        source=own,base_config=FIXED['base_config'],previous_applied95=FIXED['base_applied_dropin'],
        supervisor_source=source,supervisor_source_peer=FIXED['supervisor_source_peer'],
        prepared_config=config,prepared_dropin95=dropin,original_unit_source_archives=archives,
        new_cohort_output=str(cohort),preserved_trainer=trainer,role_count=dict(TRAIN=155,EVAL=37),
        exact_unchanged_fields=[key for key in base if key not in('output','inputs')],
        old_supervisor_source_kept_only_as_history=oldsource[0],new_selected_supervisor_source=source,
        old_failed_attempt_not_retried=True,new_supervisor_owner_and_invocation=None,
        actual_new_actor_births_barrier_health_or_quality=None,
        Root_install_target='/home/dave/.config/systemd/user/robotron-mame.service.d/95-continuous-training.conf',
        Root_payload_argv=argv,Root_only_actions_required=['Verify actual3-regression CPU PASS+ownedcloseout',
            'Verify old failed supervisor and all its original children absent and no old connections/cleanup pending',
            'Verify original trainer654315/birth16564768/invc9a7 still owns unchanged source/recipe',
            'Install only prepared95 bytes, daemon-reload and start same unit as one NEW cohort/invocation',
            'Capture new original owner before claiming admission; never adopt oldcase43/cc182 or oldEVALanchors'],
        unit_base_working_directory_environment_and_UID_inheritance_changed=False,
        live_queries_controls_units_model_replay_Lua_or_main_writes_performed=False,
        service_or_actor_launch_performed=False,engineering_or_scientific_or_quality_qualification=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--output',type=Path);p.add_argument('--cohort-output',type=Path);p.add_argument('--expected-source-sha256')
    a=p.parse_args()
    if not a.prepare:print('SOURCE_ONLY_INERT_NO_READS_OUTPUTS_IMPORTS_OR_ACTIONS');return
    require(a.output and a.cohort_output and a.expected_source_sha256,'Exact new metadata/cohort/source selection required')
    print(json.dumps(prepare(a.output,a.cohort_output,a.expected_source_sha256)),flush=True)


if __name__=='__main__':main()
