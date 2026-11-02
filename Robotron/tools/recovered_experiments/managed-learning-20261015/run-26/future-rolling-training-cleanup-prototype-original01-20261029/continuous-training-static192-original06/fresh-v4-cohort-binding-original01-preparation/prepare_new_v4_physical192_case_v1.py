"""Root-only NEW v4 cohort physical case/inventory DATA assembly.

Default inert. Reads only immutable retained metadata and source files, plus
filesystem identities for held inputs. No API/proc/service/kernel operations,
model/ROM/array body reads, raw replay, launch or production/state writes.
Prior311/247 paths remain explicit history; no old actor/health proof is adopted.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat

HERE=Path(__file__).resolve().parent
MODE_ROOT=HERE.parent
HC=MODE_ROOT/'health-consumer-physical-original192-v4-cohort-original03'
FAMILY_SHA='5a901e68e16270f7985f907964d46cc0ceb7b6e17dd1834009a5d616b88fcecd'
MAP_SHA='5e5c77c2554dacbe86b9ac0cd38eebe09d6eb1cbfe427310482dfdc8fd0b2bf1'
PRIOR_SHA='cc18250b10af2b444eebc87163a3cc710a75bf92ccbb954396c25e600edbe94d'
PARENT_SHA='8956d405f84cab32bb4778b117726ebb30588e473680ca2b8c5c8df93102c814'
BOOTSTRAP_SOURCE_SHAS={'1056bdf7d52266aa2d57c951e2cd16e3fbbb7077907bcdc4d0f26e2dd6b98410',
                      'a965014e6a5147dac51e091b14093bfe9d3ea7b3d50106195b625be7a0080960'}
WITNESS_SOURCE_SHA='fe306753c9cbb20e715b76d60c116ef9ce47a768c1a1afe0b00c03eac02a095c'
MODE='CONTINUOUS_TRAIN155_EVAL37_ONCE'
SLOTS=set(map(str,range(192)))
LIMIT=2_000_000


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def current(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(),
            'Canonical non-symlink input required: ' + str(path))
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), 'Regular input required: ' + str(path))
    return identity(info)


def checked(value, *, raw=False, immutable=True):
    require(type(value) is dict and set(value) == {'path','sha256','bytes','identity'},
            'Exact full8 pin required')
    path = Path(value['path']); selected = current(path)
    require(selected == value['identity'] and type(value['bytes']) is int
            and 0 <= selected['bytes'] == value['bytes'] <= LIMIT
            and selected['nlink'] == 1 and selected['uid'] == os.getuid()
            and (not immutable or selected['mode'] == '0o444'),
            'Selected bounded evidence identity differs: ' + str(path))
    with path.open('rb') as stream:
        require(identity(os.fstat(stream.fileno())) == selected, 'Opened input identity differs')
        data = stream.read(LIMIT+1)
        require(identity(os.fstat(stream.fileno())) == selected, 'Input changed while reading')
    require(current(path) == selected and len(data) == value['bytes']
            and hashlib.sha256(data).hexdigest() == value['sha256'],
            'Selected full SHA/identity differs: ' + str(path))
    return data if raw else json.loads(data)


def small_pin(path):
    path = Path(path); before = current(path)
    require(before['bytes'] <= LIMIT, 'Explicit large-input authority required: ' + str(path))
    with path.open('rb') as stream:
        require(identity(os.fstat(stream.fileno())) == before, 'Input open raced')
        raw = stream.read(LIMIT+1)
        require(identity(os.fstat(stream.fileno())) == before, 'Input read raced')
    require(current(path) == before and len(raw) == before['bytes'], 'Input changed during selection')
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=before)


def put(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= LIMIT, 'Bounded assembly metadata exceeded2MiB')
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw); stream.flush()
        os.fchmod(fd, 0o444); os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return small_pin(path)


def load(path, digest, name):
    value = small_pin(path)
    require(value['sha256'] == digest and value['identity']['mode'] == '0o444',
            'Exact frozen pure metadata consumer required')
    checked(value, raw=True)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def thin(value):
    return dict(sha256=value['sha256'], identity=value['identity'])


def read_inventory(value, h):
    require(value['identity']['mode']=='0o444','Immutable Root inventory metadata required')
    path=h.checked(value)
    require(path.stat().st_size<=LIMIT,'Bounded Root inventory/case required')
    return json.loads(path.read_bytes())


def validate_inventory(binding, h):
    require(binding['schema']=='robotron-continuous-physical-original192-health-case-v2',
            'New explicit original physical-cohort case required')
    authority=read_inventory(binding['input_inventory_authority'],h)
    require(authority['schema']=='robotron-root-continuous-static192-input-inventory-v1'
            and authority['status']=='ROOT_SELECTED_EXACT_HELD_INPUTS'
            and authority['mode']==MODE
            and authority['source_authority']==binding['continuous']['source_authority']
            and authority['inputs']==binding['inputs']
            and type(authority['input_count'])is int and authority['input_count']==len(binding['inputs']),
            'Exact actual physical-cohort held-input inventory required')
    parent=read_inventory(authority['parent_case'],h)
    require(parent['schema']=='robotron-round-main-health-case-v1' and len(parent['inputs'])==247,
            'Explicit original historical247 ancestor required')
    old,current=parent['inputs'],binding['inputs']
    require(set(old)<=set(current),'A historical held-input path was dropped')
    require(authority['replacements']=={p:dict(before=v,after=current[p])for p,v in old.items()if v!=current[p]}
            and authority['added_inputs']=={p:v for p,v in current.items()if p not in old}
            and binding['input_inventory_authority']['path']not in current,
            'Every actual replacement/addition must be exact; no self-hash recursion')
    return authority


def assemble(selection_path,selection_sha,expected_source_sha,output):
    own=small_pin(Path(__file__).resolve());require(own['sha256']==expected_source_sha
        and own['identity']['mode']=='0o444','Exact frozen NEW-cohort case constructor required')
    root_pin=small_pin(selection_path);require(root_pin['sha256']==selection_sha,'Exact Root selection SHA required')
    choice=checked(root_pin)
    require(set(choice)=={'schema','bootstrap_packet','health_family','health_map','health_source_peer',
                         'completed_clients_prefix','witness_anchors','witness_readback','extra_inputs'}
        and choice['schema']=='robotron-root-new-v4-physical192-case-selection-v1',
        'Exact NEW-cohort retained-metadata selection required')
    bootstrap=checked(choice['bootstrap_packet'])
    require(bootstrap['schema']=='robotron-new-v4-original192-pre-pidfd-carrier-preparation-v1'
        and bootstrap['source']['sha256']in BOOTSTRAP_SOURCE_SHAS
        and bootstrap['status']=='DATA_PREPARED_NOT_HEALTH_OR_LAUNCH_QUALIFIED',
        'Only the NEW v4 purpose-limited bootstrap carrier is admissible')
    checked(bootstrap['source'],raw=True)
    selected=bootstrap['retained_inputs'];cfg=checked(selected['config'])
    member=checked(selected['membership']);barrier=checked(selected['barrier'])
    prior_pin=selected['prior_history_case'];prior=checked(prior_pin)
    require(prior_pin['sha256']==PRIOR_SHA and len(prior['inputs'])==311,
        'Exact prior311 case is history only, never new ownership/health')
    old_inventory=checked(prior['input_inventory_authority']);parent_pin=old_inventory['parent_case']
    require(parent_pin['sha256']==PARENT_SHA,'Exact historical247 ancestor required')
    parent=checked(parent_pin);require(len(parent['inputs'])==247 and set(parent['inputs'])<=set(prior['inputs']),
        'Historical247 input path ancestry differs')
    capture=checked(selected['owner_API_capture']);owners=checked(capture['owners'])
    api=checked(capture['baseline_API']);api_capture=checked(capture['baseline_API_capture'])
    require(api_capture['value']==api and api_capture['raw_wire'].encode()==checked(capture['baseline_API'],raw=True)
        and api_capture['sha256']==capture['baseline_API']['sha256'],'Fresh retained raw/API bracket differs')
    authority=checked(cfg['source_authority']);roles=checked(cfg['rolemap'])['slot_eval']
    sup=member['supervisor'];trainer=cfg['trainer'];original=member['data']['original_slots']
    require(sup['pid']==909646 and sup['birth']==17859362
        and sup['invocation_id']=='5648e44c5c0d415ebfc7d109256f4676'
        and sup['source']['sha256']=='bc2f11eafa974b693d767ca5291a69655b37e79cb5d47f0db03ee10135dc77d1'
        and trainer==authority['trainer']==prior['continuous']['trainer']
        and cfg['source_authority']==prior['continuous']['source_authority'],
        'New actual fleet and unchanged original trainer/source authority required')
    epoch=f"{sup['pid']}:{sup['birth']}:{sup['invocation_id']}"
    require(set(original)==SLOTS and roles==prior['slot_eval']
        and barrier['epoch']==member['epoch']==epoch and barrier['supervisor']==sup
        and barrier['trainer']==member['trainer']==trainer
        and barrier['data']['original_membership']==selected['membership']
        and barrier['data']['slots']==list(range(192))and barrier['data']['slot_eval']==roles,
        'Exact NEW immutable192 role/membership/barrier joins required')
    for role,anchor in [('fleet',sup),('trainer',trainer)]:
        row=owners[role];proc=row['process'];require(row['unit']==anchor['unit']
            and row['invocation']==anchor['invocation_id']and proc['pid']==anchor['pid']
            and proc['starttime_ticks']==anchor['birth']and proc['cgroup']==anchor['cgroup'],
            'Fresh retained unit/process owner does not join actual NEW cohort')
    input_env={};generations=set();min_spawn=None
    for slot,row in original.items():
        spawn=checked(row['spawn_intent']);input_env[slot]=spawn['data']['input_environment']
        generations.add(spawn['data']['policy']['measurement_generation'])
        min_spawn=spawn['unix_s']if min_spawn is None else min(min_spawn,spawn['unix_s'])
    require(len(generations)==1,'New cohort spawn policies cross generations')
    prefix=checked(choice['completed_clients_prefix']);archive=checked(prefix['archive'],raw=True)
    require(prefix['schema']=='robotron-prior-cohort-EVAL-completed-prefix-v1'
        and prefix['canonical_path']==str(Path(cfg['journal_directory'])/'completed_clients.jsonl')
        and set(prefix['canonical_identity'])=={'device','inode','mode','uid','nlink'}
        and prefix['prefix_bytes']==prefix['archive']['bytes']==len(archive)
        and prefix['prefix_sha256']==prefix['archive']['sha256']==hashlib.sha256(archive).hexdigest()
        and prefix['cohort_min_spawn_unix_s']==min_spawn and(not archive or archive.endswith(b'\n')),
        'Exact immutable OLD EVAL prefix/canonical identity/new spawn boundary required')
    for line in archive.splitlines():
        row=json.loads(line);require(type(row['start_unix_s'])in(int,float)
            and type(row['end_unix_s'])in(int,float)and math.isfinite(row['start_unix_s'])
            and math.isfinite(row['end_unix_s'])
            and row['start_unix_s']<row['end_unix_s']<min_spawn,
            'Historical prefix may never discard a NEW-cohort game')
    anchors=checked(choice['witness_anchors']);wselection=checked(bootstrap['witness_selection'])
    checked(choice['witness_readback'])  # Root's independent actual FD/birth readback is retained provenance.
    require(anchors['schema']=='robotron-original37-EVAL-pidfd-held-anchors-v1'
        and anchors['all37_acquired_while_originals_live']is True
        and anchors['selection']==bootstrap['witness_selection']
        and anchors['source']==bootstrap['witness_source']
        and anchors['source']['sha256']==WITNESS_SOURCE_SHA
        and anchors['original_case']==bootstrap['carrier']
        and wselection['original_case']==bootstrap['carrier']
        and set(anchors['originals'])=={slot for slot,v in roles.items()if v},
        'Actual NEW37 held-before-exit witness/selection/carrier required')
    carrier=checked(bootstrap['carrier']);require(carrier['continuous']['original_slots']==original
        and carrier['slot_eval']==roles,'Witness carrier belongs to another physical cohort')
    witness=dict(selection=bootstrap['witness_selection'],source=anchors['source'],anchors=choice['witness_anchors'],
        output=wselection['output'],holder=anchors['holder'])
    require(Path(choice['witness_anchors']['path'])==Path(witness['output'])/'held-original37-anchors.json',
        'Actual new witness output differs')
    family=checked(choice['health_family']);mapbody=checked(choice['health_map']);mapping=mapbody['observer_sources']
    require(choice['health_family']['sha256']==FAMILY_SHA and choice['health_map']['sha256']==MAP_SHA
        and family['observer_sources']==mapping and len(mapping)==8
        and all(Path(mapping[k]['path']).parent==HC for k in('client','worker','health','health_base','registry')),
        'Exact frozen PREFIX-AWARE physical8 family required; old0eff is historical only')
    checked(choice['health_source_peer'])
    source_pins=authority['canonical_sources']+[sup['source'],cfg['physical_helper']]
    source_pins += [v for k,v in mapping.items()if k!='interpreter']+[family['observer_reviewer'],witness['source']]
    sources={}
    for value in source_pins:
        checked(value,raw=True,immutable=False)
        require(value['path']not in sources or sources[value['path']]==value,'Conflicting active source pins')
        sources[value['path']]=value
    explicit=list(choice['extra_inputs'])+cfg['inputs']+list(sources.values())
    explicit += [root_pin,own,choice['bootstrap_packet'],bootstrap['source'],bootstrap['carrier'],bootstrap['witness_selection']]
    explicit += list(selected.values())+[capture[k]for k in('owners','baseline_API','baseline_API_capture')]
    explicit += [choice[k]for k in('health_family','health_map','health_source_peer','completed_clients_prefix','witness_anchors','witness_readback')]
    explicit += [prefix['archive'],cfg['source_authority'],cfg['rolemap']]
    overrides={}
    for value in explicit:
        require(type(value)is dict and set(value)=={'path','sha256','bytes','identity'}
            and current(value['path'])==value['identity']and value['bytes']==value['identity']['bytes'],
            'Explicit NEW-cohort held-input full8 identity differs')
        if value['bytes']<=LIMIT:require(small_pin(Path(value['path']))==value,'Explicit small-input fullSHA differs')
        require(value['path']not in overrides or overrides[value['path']]==value,'Conflicting explicit held input')
        overrides[value['path']]=value
    inputs={};reused=0;refreshed=[]
    for path,old in prior['inputs'].items():
        actual=current(path)
        if path in overrides:inputs[path]=thin(overrides[path])
        elif actual==old['identity']:inputs[path]=old;reused+=1
        else:
            require(actual['bytes']<=LIMIT,'Changed large input requires separate Root fullSHA authority')
            inputs[path]=thin(small_pin(Path(path)));refreshed.append(path)
    for path,value in overrides.items():inputs[path]=thin(value)
    mame=prior['actor_executable'];require({k:v for k,v in current(mame['path']).items()if k!='nlink'}==mame['identity'],
        'Historical literal MAME executable identity changed')
    recipe={key:api[key]for key in('lr','epsilon','expert_ratio')}
    require(recipe==prior['recipe'],'Unchanged trainer recipe must remain exact')
    exposure=api['host_pipeline']['learning_exposure']
    require(all(all(exposure[kind][key]==prior['exposure'][kind][key]for key in
        ('process_id','instance_monotonic_ns','epoch','epoch_reason'))for kind in('optimizer','replay')),
        'Unchanged trainer optimizer/replay exposure lineage changed')
    case=dict(schema='robotron-continuous-physical-original192-health-case-v2',inputs=inputs,
        units=dict(trainer=trainer['unit'],fleet=cfg['unit']),owners=owners,slot_eval=roles,
        actor_environment=cfg['actor_common_environment'],actor_command=cfg['mame_argv'],actor_executable=mame,
        actor_affinity=owners['fleet']['process']['affinity'],recipe=recipe,exposure=exposure,
        round_root=cfg['output'],source_guard=mapping['health_base']['path'],experiment=api['managed_experiment'],
        continuous=dict(mode=MODE,accepted_profile='PHYSICAL_ORIGINAL192_TRAIN_CURRENT_TCP_EVAL_ORIGINAL_ONCE',
            maximum_proof_gap_s=2.0,narrow_API_exception_TTL_s=.5,epoch=epoch,snapshot_path=str(Path(cfg['output'])/'status.json'),
            supervisor=sup,trainer=trainer,server_stamp=trainer['server_stamp'],rolemap=cfg['rolemap'],
            source_authority=cfg['source_authority'],source_pins=list(sources.values()),policy_generation=next(iter(generations)),
            initial_barrier=selected['barrier'],original_membership=selected['membership'],original_slots=original,
            launch_argv=cfg['launch_argv'],input_environment_by_slot=input_env,eval_journal_directory=cfg['journal_directory'],
            eval_exit_witness=witness,completed_clients_prefix=choice['completed_clients_prefix']))
    registry=load(Path(mapping['registry']['path']),mapping['registry']['sha256'],'_NEW_v4_cohort_registry_case')
    registry.validate_case(case)
    for path,value in inputs.items():require(current(path)==value['identity'],'Held input changed during assembly')
    require(output.is_absolute()and output.parent.resolve(strict=True)==HERE and not output.exists(),
        'One exclusive NEW-case DATA directory under preparer required')
    output.mkdir(mode=0o700)
    inventory=dict(schema='robotron-root-continuous-static192-input-inventory-v1',status='ROOT_SELECTED_EXACT_HELD_INPUTS',
        mode=MODE,source_authority=cfg['source_authority'],inputs=inputs,input_count=len(inputs),parent_case=parent_pin,
        replacements={p:dict(before=v,after=inputs[p])for p,v in parent['inputs'].items()if v!=inputs[p]},
        added_inputs={p:v for p,v in inputs.items()if p not in parent['inputs']},
        prior_typed_case_history=prior_pin,all_prior311_paths_retained=set(prior['inputs'])<=set(inputs))
    inventory_pin=put(output/'exact-held-input-inventory.json',inventory);case['input_inventory_authority']=inventory_pin
    class Reader:
        @staticmethod
        def checked(value):checked(value,raw=True);return Path(value['path'])
    validate_inventory(case,Reader)
    cp=put(output/'new-v4-physical192-main-case.json',case)
    return put(output/'prepared-new-v4-physical192-case-NOT-QUALIFIED.json',dict(
        schema='robotron-root-new-v4-physical192-case-preparation-v1',status='DATA_PREPARED_NOT_QUALIFIED',source=own,
        selection=root_pin,case=cp,input_inventory_authority=inventory_pin,health_family=choice['health_family'],health_map=choice['health_map'],
        historical_ancestor_inputs=247,prior_failed_context_history_inputs=311,held_input_count=len(inputs),
        all247_and311_paths_retained=True,changed_small_input_fullSHA_refreshes=refreshed,unchanged_full8_digest_reuses=reused,
        old_physical_actor_identity_or_health_or_engineering_proof_adopted=False,new_actual37_witness=witness,
        immutable_old_EVAL_prefix=choice['completed_clients_prefix'],actual_runtime_freshness_or_resources_or_health_qualified=False,
        engineering_or_private_policy_or_quality_or_scientific_launch_qualified=False,no_large_model_MAME_ROM_or_array_body_read=True,
        current_TCP_keeper_heartbeat_and_future_exit_files_held_as_inputs=False,Root_only_new_engineering_case=cp))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--selection',type=Path);p.add_argument('--selection-sha256');p.add_argument('--output',type=Path)
    p.add_argument('--expected-source-sha256');a=p.parse_args()
    if not a.prepare:print('SOURCE_ONLY_INERT_NO_READS_OR_ACTIONS');return
    print(json.dumps(assemble(a.selection,a.selection_sha256,a.expected_source_sha256,a.output)),flush=True)


if __name__=='__main__':main()
