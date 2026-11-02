"""Root-only retained-metadata assembly; inert unless --prepare is explicit.

No API, procfs, systemctl, signal, launch, model, or array access. The resulting
case selects actual immutable original192 evidence for NEW engineering only.
Unchanged historical large input digests are retained only with identical full8
identity; changed large inputs require a separate explicit Root fullpin.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
MODE_ROOT = HERE.parent
HC = HERE
PRIOR_CASE_SHA='43a8436e475dd671d9219537e301e95353dee0a5d423ab4acda77182586ce944'
FAMILY_SHA='0effd7170f23dfac8ecd811c2df4b74435972b330bf74ba61913c530ce7a35b5'
ANCHORS_SHA='5b49571bbf451b69b305372350a5246a98860d8bfe076df795050bee6f71a38d'
WITNESS_READBACK_SHA='a12a6f3d22f570655b317f8dffa5d1a799dfdb46340f7cb3f998348ad3f35172'
WITNESS_SOURCE_SHA='fe306753c9cbb20e715b76d60c116ef9ce47a768c1a1afe0b00c03eac02a095c'
WITNESS_SELECTION_SHA='3326bf373b718adba2e09002d986a7a02ef6d1ef0acdc520976e818188a0eb50'
EVAL_JOURNAL_DIRECTORY=str(MODE_ROOT/'handoff-preservation-original01/live-original01/startup-repair-original02/runtime')
REGISTRY_SHA = '71fc044d7b3bbbfceba5ef23f69a6c741eeff5700176050c6cdbe9e4794bba69'
PROFILE_SHA = '5260662e651c6f26cde42bb04cde913dd51015658d071499b6966e661e6a451b'
MAP_SHA = 'ed8d6356a7ab12ef00824d4cfa25048ada2974d32e61cfc6e57f227c5dc68a80'
SUPERVISOR_SHA = '904b01f21fc1daf5268c56c64d13246c9cac0992bf6370c866f4f8b8fd382e03'
PARENT_SHA = '8956d405f84cab32bb4778b117726ebb30588e473680ca2b8c5c8df93102c814'
MODE = 'CONTINUOUS_TRAIN155_EVAL37_ONCE'
SLOTS = set(map(str, range(192)))
LITERAL_INPUT_KEYS = {'ROBOTRON_CLIENT_SLOT', 'ROBOTRON_ACTOR_ROUND',
    'ROBOTRON_RETIRE_AFTER_GAME', 'ROBOTRON_PREVIEW_FPS', 'ROBOTRON_EVAL_MODE'}
LIMIT = 2_000_000


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


def assemble(selection_path, selection_sha, expected_source_sha, output):
    own=small_pin(Path(__file__).resolve())
    require(own['sha256']==expected_source_sha and own['identity']['mode']=='0o444',
            'Exact frozen Root-selected physical case preparer required')
    selected=small_pin(selection_path);require(selected['sha256']==selection_sha,'Root selection SHA differs')
    choice=checked(selected)
    require(choice['schema']=='robotron-root-physical-original192-case-assembly-selection-v2'
            and set(choice)=={'schema','prior_case','startup_authority','witness_anchors',
                'witness_readback','extra_inputs'}, 'Exact explicit physical-cohort Root selection required')
    require(choice['prior_case']['sha256']==PRIOR_CASE_SHA,'Only the retained original192 physical history is selected')
    prior=checked(choice['prior_case']);require(prior['schema']=='robotron-continuous-static192-health-case-v1'
            and len(prior['inputs'])==292,'Actual prior292-input physical history required; no old qualification adoption')
    old_inventory=checked(prior['input_inventory_authority']);parent_pin=old_inventory['parent_case']
    require(parent_pin['sha256']==PARENT_SHA,'Exact original normalized247 ancestor required')
    parent=checked(parent_pin)
    require(parent['schema']=='robotron-round-main-health-case-v1' and len(parent['inputs'])==247
            and set(parent['inputs'])<=set(prior['inputs']),'Original247 domain was not retained')
    require(choice['startup_authority']==prior['continuous']['source_authority'],
            'Actual current startup/source authority changed')
    authority=checked(choice['startup_authority']);anchors=checked(choice['witness_anchors'])
    readback=checked(choice['witness_readback'])
    require(choice['witness_anchors']['sha256']==ANCHORS_SHA
            and choice['witness_readback']['sha256']==WITNESS_READBACK_SHA
            and anchors['schema']=='robotron-original37-EVAL-pidfd-held-anchors-v1'
            and anchors['all37_acquired_while_originals_live']is True,
            'Actual held-before-exit37 witness/readback required')
    witness=dict(selection=anchors['selection'],source=anchors['source'],anchors=choice['witness_anchors'],
        output=str(Path(choice['witness_anchors']['path']).parent),holder=anchors['holder'])
    require(witness['source']['sha256']==WITNESS_SOURCE_SHA and witness['selection']['sha256']==WITNESS_SELECTION_SHA,
            'Exact actual37 keeper source/selection required')
    checked(witness['source'],raw=True);checked(witness['selection'])
    family_pin=small_pin(HC/'prepared-physical-original192-typed-health-and-observer-SOURCE-ONLY-NOT-QUALIFIED-v2.json')
    map_pin=small_pin(HC/'prospective-physical192-eight-role-observer-source-map-v2.json')
    require(family_pin['sha256']==FAMILY_SHA and map_pin['sha256']==MAP_SHA,
            'Exact independently reviewed new physical source family/map required')
    family=checked(family_pin);mapping=checked(map_pin)['observer_sources']
    require(family['observer_sources']==mapping and len(mapping)==8,
            'Exact source-bound physical eight-role map required')
    source_pins=list(prior['continuous']['source_pins'])+authority['canonical_sources']+[prior['continuous']['supervisor']['source']]
    source_pins += [v for k,v in mapping.items()if k!='interpreter']
    source_pins += [family['observer_reviewer'],witness['source']]
    sources={}
    for value in source_pins:
        checked(value,raw=True,immutable=False)
        require(value['path']not in sources or sources[value['path']]==value,'Conflicting selected source authority')
        sources[value['path']]=value
    explicit=list(choice['extra_inputs'])+list(sources.values())
    explicit += [selected,own,choice['prior_case'],choice['startup_authority'],choice['witness_anchors'],
        choice['witness_readback'],witness['selection'],family_pin,map_pin]
    explicit += [small_pin(HC/'independent-physical-original192-health-and-kernel-exit-consumer-source-peer-v1.json')]
    overrides={}
    for value in explicit:
        require(set(value)=={'path','sha256','bytes','identity'} and current(value['path'])==value['identity']
                and value['bytes']==value['identity']['bytes'],'Explicit held-input full8 identity differs')
        if value['bytes']<=LIMIT:require(small_pin(Path(value['path']))==value,'Explicit held small-input fullSHA differs')
        require(value['path']not in overrides or overrides[value['path']]==value,'Conflicting explicit held input')
        overrides[value['path']]=value
    inputs={};reused=0;refreshed=[]
    for path,old in prior['inputs'].items():
        actual=current(path)
        if path in overrides:inputs[path]=thin(overrides[path])
        elif actual==old['identity']:inputs[path]=old;reused+=1
        else:
            require(actual['bytes']<=LIMIT,'Changed large historical input lacks explicit Root fullpin')
            inputs[path]=thin(small_pin(Path(path)));refreshed.append(path)
    for path,value in overrides.items():inputs[path]=thin(value)
    case=json.loads(json.dumps(prior))
    case.update(schema='robotron-continuous-physical-original192-health-case-v2',inputs=inputs,
        source_guard=str(HC/'continuous_physical192_health_v2.py'))
    case['continuous'].update(accepted_profile='PHYSICAL_ORIGINAL192_TRAIN_CURRENT_TCP_EVAL_ORIGINAL_ONCE',
        source_pins=list(sources.values()),eval_journal_directory=EVAL_JOURNAL_DIRECTORY,eval_exit_witness=witness)
    case.pop('input_inventory_authority')
    registry=load(HC/'continuous_physical192_registry_v2.py',REGISTRY_SHA,'_physical_case_registry_v2')
    registry.validate_case(case)  # Pure original bootstrap/source/keeper anchors; no current health claim.
    for path,value in inputs.items():require(current(path)==value['identity'],'Held input changed during case assembly')
    require(output.is_absolute()and output.parent.resolve(strict=True)==HERE and not output.exists(),
            'One exclusive physical-case DATA directory under this preparer required')
    output.mkdir(mode=0o700)
    inventory=dict(schema='robotron-root-continuous-static192-input-inventory-v1',
        status='ROOT_SELECTED_EXACT_HELD_INPUTS',mode=MODE,source_authority=choice['startup_authority'],
        inputs=inputs,input_count=len(inputs),parent_case=parent_pin,
        replacements={p:dict(before=v,after=inputs[p])for p,v in parent['inputs'].items()if v!=inputs[p]},
        added_inputs={p:v for p,v in inputs.items()if p not in parent['inputs']},
        prior_typed_case_history=choice['prior_case'],all_prior292_paths_retained=set(prior['inputs'])<=set(inputs))
    inventory_pin=put(output/'exact-held-input-inventory.json',inventory);case['input_inventory_authority']=inventory_pin
    class Reader:
        @staticmethod
        def checked(value):checked(value,raw=True);return Path(value['path'])
    validate_inventory(case,Reader)
    case_pin=put(output/'physical-original192-main-case.json',case)
    return put(output/'prepared-physical-original192-case-NOT-QUALIFIED.json',dict(
        schema='robotron-root-physical-original192-case-preparation-v2',status='DATA_PREPARED_NOT_QUALIFIED',
        source=own,selection=selected,case=case_pin,input_inventory_authority=inventory_pin,
        held_input_count=len(inputs),historical_round_ancestor_inputs=247,prior_typed_history_inputs=292,
        all_prior247_and292_paths_retained=True,unchanged_full8_historical_digest_reuses=reused,
        changed_small_input_full_SHA_refreshes=refreshed,original_EVAL_exit_witness=witness,
        no_large_executable_model_ROM_or_array_body_read=True,
        old_case_and_postbarrier_snapshot_used_only_for_immutable_physical_history=True,
        current_TRAIN_TCP_and_keeper_heartbeat_and_future_exit_files_not_frozen_case_inputs=True,
        actual_current_physical_health_or_resources_or_engineering_qualified=False,
        scientific_launch_qualified=False,quality_qualified=False,main_runtime_changed=False,
        next_Root_only_prepare_argv=['/usr/bin/python3.12','-I','-B',str(MODE_ROOT/'physical-original192-context-engineering-original01-preparation/prepare_physical192_engineering_v1.py'),
            '--prepare','--case',case_pin['path'],'--case-sha256',case_pin['sha256'],'--output',
            str(MODE_ROOT/'physical-original192-context-engineering-original01-preparation/actual-physical-contexts-original01')]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',action='store_true'); p.add_argument('--selection',type=Path)
    p.add_argument('--selection-sha256'); p.add_argument('--expected-source-sha256')
    p.add_argument('--output',type=Path)
    a = p.parse_args()
    if not a.prepare:
        print('PLAN_ONLY_NO_READS_IMPORTS_OUTPUTS_PROBES_OR_ACTIONS'); return
    print(json.dumps(assemble(a.selection,a.selection_sha256,a.expected_source_sha256,a.output)),flush=True)


if __name__ == '__main__':
    main()
