"""Root-only DATA rebind to current once-only EVAL quiescence observer v5.

All existing original Main/fleet/actors remain selected. This prepares a NEW
case and full input ancestry; old static/proxy attempts are history only.
No API/proc/systemd/kernel query, model/MAME/ROM/array body read, raw replay,
scientific launch, source installation or production/state/public write.
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
MODE='CONTINUOUS_TRAIN155_EVAL37_ONCE'
LIMIT=2_000_000
CASE_SCHEMA='robotron-original192-live-pidfd-current-eval-quiescence-case-v5'
INVENTORY_SCHEMA='robotron-root-original192-live-pidfd-current-eval-quiescence-input-inventory-v5'
PROFILE='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
STATIC=('parent_pid','cgroup','command','environment','affinity','uids','executable')
FIXED={'prior_physical_case': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/fresh-v4-cohort-binding-original01-preparation/actual-new-v4-physical192-case-original01/new-v4-physical192-main-case.json', 'sha256': '6f7b6e4340030e301fd410947b527a14d957bc6392e9576a4f85a889fd8ce162', 'bytes': 1296548, 'identity': {'device': 2304, 'inode': 85333952, 'bytes': 1296548, 'mtime_ns': 1793297300889794305, 'ctime_ns': 1793297300889794305, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'prior_inventory': {'bytes': 259573, 'identity': {'bytes': 259573, 'ctime_ns': 1793297300871663044, 'device': 2304, 'inode': 85333951, 'mode': '0o444', 'mtime_ns': 1793297300871663044, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/fresh-v4-cohort-binding-original01-preparation/actual-new-v4-physical192-case-original01/exact-held-input-inventory.json', 'sha256': '19465e464242bae3c96ee385625995a72e731d69c76d62f227db80331e734a03'}, 'original247_case': {'bytes': 129153, 'identity': {'bytes': 129153, 'ctime_ns': 1793278913496049061, 'device': 2304, 'inode': 85226144, 'mode': '0o444', 'mtime_ns': 1793278913495780740, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/current-owner-evidence-original03-closed-control-cleanup/Root-normalized-control-operational-main-binding.json', 'sha256': '8956d405f84cab32bb4778b117726ebb30588e473680ca2b8c5c8df93102c814'}, 'health_family': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/prepared-live-pidfd-current-EVAL-quiescence-health-and-observer-SOURCE-ONLY-NOT-QUALIFIED-v5.json', 'sha256': '9e00ed11b9ad56b8a16911eb38c3d48f9edd0a7fa7d0bb670749cc9ed75d0eac', 'bytes': 9638, 'identity': {'device': 2304, 'inode': 85354105, 'bytes': 9638, 'mtime_ns': 1793309543262656319, 'ctime_ns': 1793309543262656319, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'health_map': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/prospective-live-pidfd-current-EVAL-quiescence-eight-role-observer-source-map-v5.json', 'sha256': '5d8ce346200f8737aae484b72a15b7f38dd8ea1da8ac463acc1c94531894f8b9', 'bytes': 6137, 'identity': {'device': 2304, 'inode': 85354082, 'bytes': 6137, 'mtime_ns': 1793309543260226097, 'ctime_ns': 1793309543260226097, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'health_source_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/independent-live-pidfd-current-EVAL-quiescence-health-six-source-peer-v5.json', 'sha256': '8c8311bb0fbc79eb9560ed8f521f326e666a14795b84cb5c61712797f5f703b9', 'bytes': 31956, 'identity': {'device': 2304, 'inode': 85354214, 'bytes': 31956, 'mtime_ns': 1793309637790162357, 'ctime_ns': 1793309637790162357, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'immediate_prior_case': {'bytes': 1312498, 'identity': {'bytes': 1312498, 'ctime_ns': 1793308180417659727, 'device': 2304, 'inode': 85352674, 'mode': '0o444', 'mtime_ns': 1793308180417659727, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-immutable-bootstrap-live-pidfd-original04/actual-main-case-original01/immutable-bootstrap-live-pidfd-main-case-v4.json', 'sha256': '9634ddbe13decdd74b44946d4951d8e5285309446005269e38690b7a83d03e9c'}, 'immediate_prior_inventory': {'bytes': 281724, 'identity': {'bytes': 281724, 'ctime_ns': 1793308180393739346, 'device': 2304, 'inode': 85352673, 'mode': '0o444', 'mtime_ns': 1793308180393739346, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-immutable-bootstrap-live-pidfd-original04/actual-main-case-original01/exact-held-input-inventory-v4.json', 'sha256': '1db700fd65eb4f6457095228697fbfbe3127dde7c1133bb1d3f1a366b9474041'}}


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

def validate_inventory(binding,h):
    require(binding['schema']==CASE_SCHEMA,'Exact NEW immutable-bootstrap/live-pidfd case required')
    authority=read_inventory(binding['input_inventory_authority'],h)
    require(authority['schema']==INVENTORY_SCHEMA and authority['status']=='ROOT_SELECTED_EXACT_HELD_INPUTS'
            and authority['mode']==MODE and authority['source_authority']==binding['continuous']['source_authority']
            and authority['inputs']==binding['inputs']
            and type(authority['input_count'])is int and authority['input_count']==len(binding['inputs']),
            'Exact NEW held-input inventory required')
    parent=read_inventory(authority['parent_case'],h)
    prior=read_inventory(authority['prior_physical_case'],h)
    immediate=read_inventory(authority['immediate_prior_case'],h)
    require(authority['parent_case']==FIXED['original247_case']
            and parent['schema']=='robotron-round-main-health-case-v1' and len(parent['inputs'])==247
            and authority['prior_physical_case']==FIXED['prior_physical_case']
            and prior['schema']=='robotron-continuous-physical-original192-health-case-v2'
            and len(prior['inputs'])==348 and authority['all_prior348_paths_retained']is True
            and authority['immediate_prior_case']==FIXED['immediate_prior_case']
            and immediate['schema']=='robotron-physical-original192-immutable-bootstrap-live-pidfd-health-case-v4'
            and len(immediate['inputs'])==365 and authority['all_v4_paths_retained']is True,
            'Exact247 ancestor and original348 physical history required')
    old=parent['inputs'];current_inputs=binding['inputs']
    require(set(old)<=set(prior['inputs'])<=set(immediate['inputs'])<=set(current_inputs)
            and authority['replacements']=={p:dict(before=v,after=current_inputs[p])for p,v in old.items()if v!=current_inputs[p]}
            and authority['added_inputs']=={p:v for p,v in current_inputs.items()if p not in old}
            and authority['prior348_replacements']=={p:dict(before=v,after=current_inputs[p])for p,v in prior['inputs'].items()if v!=current_inputs[p]}
            and authority['immediate_prior_replacements']=={p:dict(before=v,after=current_inputs[p])for p,v in immediate['inputs'].items()if v!=current_inputs[p]}
            and binding['input_inventory_authority']['path']not in current_inputs,
            'Every historical path/replacement/addition must remain explicit without self-hash')
    return authority


def assemble(selection_path,selection_sha,expected_source_sha,output):
    own=small_pin(Path(__file__).resolve())
    require(own['sha256']==expected_source_sha and own['identity']['mode']=='0o444',
            'Exact frozen current-EVAL-quiescence case DATA constructor required')
    selected=small_pin(selection_path);require(selected['sha256']==selection_sha,'Exact Root selection SHA required')
    choice=checked(selected)
    require(set(choice)=={'schema','prior_physical_case','immediate_prior_case','health_family','health_map','health_source_peer',
                         'owner_API_capture','input_overrides','extra_inputs'}
            and choice['schema']=='robotron-root-current-eval-quiescence-case-selection-v5',
            'Explicit NEW current-EVAL-quiescence Root metadata selection required')
    for key in ('prior_physical_case','immediate_prior_case','health_family','health_map','health_source_peer'):
        require(choice[key]==FIXED[key],'Only exact selected v4 source/history domain allowed')
    prior=checked(FIXED['immediate_prior_case']);inventory=checked(FIXED['immediate_prior_inventory'])
    historical348=checked(FIXED['prior_physical_case'])
    parent=checked(FIXED['original247_case'])
    require(prior['input_inventory_authority']==FIXED['immediate_prior_inventory']
            and inventory['inputs']==prior['inputs'] and len(prior['inputs'])==365
            and inventory['prior_physical_case']==FIXED['prior_physical_case']
            and len(historical348['inputs'])==348
            and inventory['parent_case']==FIXED['original247_case'] and len(parent['inputs'])==247
            and set(parent['inputs'])<=set(historical348['inputs'])<=set(prior['inputs']), 'Exact365/348/247 historical domain differs')
    family=checked(choice['health_family']);mapping_packet=checked(choice['health_map'])
    require(family['schema']=='robotron-live-pidfd-current-eval-quiescence-six-source-family-v5'
            and family['observer_map']==choice['health_map'] and family['case_schema']==CASE_SCHEMA
            and mapping_packet['case_schema']==CASE_SCHEMA and mapping_packet['profile']==PROFILE,
            'Exact selected6/source8/protocolv5 domain required')
    mapping=mapping_packet['observer_sources'];reviewer=mapping_packet['observer_reviewer']
    require(set(mapping)=={'registry','health_base','health','worker','client','durability','control','interpreter'}
            and all(Path(mapping[key]['path']).parent==HERE for key in('registry','health_base','health','worker','client')),
            'Exact new v5 typed observer source graph required')
    require(choice['health_source_peer']is not None,'Frozen selected HC5 source peer required')
    peer=checked(choice['health_source_peer'])
    capture=checked(choice['owner_API_capture'])
    require(capture['schema']=='robotron-root-static192-owner-and-API-metadata-capture-v1'
            and capture['no_child_census_or_192_runtime_or_engineering_qualification']is True
            and capture['no_signals_or_controls_or_model_GPU_or_quality_actions']is True,
            'Retained Root metadata capture only; not runtime qualification')
    owners=checked(capture['owners']);api=checked(capture['baseline_API']);wire=checked(capture['baseline_API'],raw=True)
    api_capture=checked(capture['baseline_API_capture'])
    require(api_capture['value']==api and api_capture['raw_wire'].encode()==wire
            and api_capture['sha256']==capture['baseline_API']['sha256'], 'Actual retained API wire bracket differs')
    for role in ('trainer','fleet'):
        actual,baseline=owners[role],prior['owners'][role]
        require(actual['unit']==baseline['unit'] and actual['invocation']==baseline['invocation']
                and actual['process']['pid']==baseline['process']['pid']
                and actual['process']['starttime_ticks']==baseline['process']['starttime_ticks']
                and all(actual['process'][key]==baseline['process'][key]for key in STATIC)
                and actual['process']['state']not in('T','t','Z','X','x'),
                'Current retained source/recipe/owner must remain the original physical cohort')
    require(api['training_enabled']is True and api['measurement_active']is False
            and {key:api[key]for key in prior['recipe']}==prior['recipe'],
            'Original continuous main recipe/training mode changed')
    exposure=api['host_pipeline']['learning_exposure']
    require(all(all(exposure[kind][key]==prior['exposure'][kind][key]
            for key in('process_id','instance_monotonic_ns','epoch','epoch_reason'))for kind in('optimizer','replay')),
            'Original optimizer/replay lineage changed')
    explicit=[own,selected,*FIXED.values(),choice['owner_API_capture'],capture['owners'],capture['baseline_API'],
              capture['baseline_API_capture'],*choice['input_overrides'],*choice['extra_inputs']]
    explicit += [value for key,value in mapping.items()if key!='interpreter']+[reviewer]
    overrides={}
    for value in explicit:
        require(type(value)is dict and set(value)=={'path','sha256','bytes','identity'}
                and current(value['path'])==value['identity'] and value['bytes']==value['identity']['bytes'],
                'Explicit full8 input identity changed')
        require(value['bytes']<=LIMIT,'No large-body input refresh is authorized by this DATA constructor')
        require(small_pin(Path(value['path']))==value,'Explicit small source/metadata SHA differs')
        require(value['path']not in overrides or overrides[value['path']]==value,'Conflicting explicit input pin')
        overrides[value['path']]=value
    inputs={};reused=0
    for path,old in prior['inputs'].items():
        actual=current(path)
        if path in overrides:inputs[path]=thin(overrides[path])
        else:
            require(actual==old['identity'], 'Changed held input requires explicit Root bounded fullSHA override: '+path)
            inputs[path]=old;reused+=1
    for path,value in overrides.items():inputs[path]=thin(value)
    require(set(prior['inputs'])<=set(inputs),'An immediate prior365 path was dropped')
    old_sources={entry['path']:entry for entry in prior['continuous']['source_pins']}
    for value in [v for k,v in mapping.items()if k!='interpreter']+[reviewer]:old_sources[value['path']]=value
    case=json.loads(json.dumps(prior));case.update(schema=CASE_SCHEMA,inputs=inputs,owners=owners,
        baseline_snapshot=capture['baseline_API'],exposure=exposure,source_guard=mapping['health_base']['path'])
    case.pop('input_inventory_authority',None)
    case['continuous'].update(accepted_profile=PROFILE,source_pins=list(old_sources.values()))
    registry=load(Path(mapping['registry']['path']),mapping['registry']['sha256'],'_current_eval_quiescence_case_v5_registry')
    registry.validate_case(case)
    for path,value in inputs.items():require(current(path)==value['identity'],'Held input changed during assembly')
    require(output.is_absolute()and output.parent.resolve(strict=True)==HERE and not output.exists(),
            'Fresh v5 DATA output directly under constructor required')
    output.mkdir(mode=0o700)
    authority=dict(schema=INVENTORY_SCHEMA,status='ROOT_SELECTED_EXACT_HELD_INPUTS',mode=MODE,
        source_authority=case['continuous']['source_authority'],inputs=inputs,input_count=len(inputs),
        parent_case=FIXED['original247_case'],prior_physical_case=FIXED['prior_physical_case'],all_prior348_paths_retained=True,
        immediate_prior_case=FIXED['immediate_prior_case'],all_v4_paths_retained=True,
        replacements={p:dict(before=v,after=inputs[p])for p,v in parent['inputs'].items()if v!=inputs[p]},
        added_inputs={p:v for p,v in inputs.items()if p not in parent['inputs']},
        prior348_replacements={p:dict(before=v,after=inputs[p])for p,v in historical348['inputs'].items()if v!=inputs[p]},
        immediate_prior_replacements={p:dict(before=v,after=inputs[p])for p,v in prior['inputs'].items()if v!=inputs[p]})
    authority_pin=put(output/'exact-held-input-inventory-v5.json',authority);case['input_inventory_authority']=authority_pin
    class Reader:
        @staticmethod
        def checked(value):checked(value,raw=True);return Path(value['path'])
    validate_inventory(case,Reader)
    cp=put(output/'current-EVAL-quiescence-main-case-v5.json',case)
    return put(output/'prepared-current-EVAL-quiescence-case-NOT-QUALIFIED-v5.json',dict(
        schema='robotron-root-current-eval-quiescence-case-preparation-v5',status='DATA_PREPARED_NOT_QUALIFIED',
        source=own,selection=selected,case=cp,input_inventory_authority=authority_pin,
        health_family=choice['health_family'],health_map=choice['health_map'],health_source_peer=choice['health_source_peer'],
        historical_ancestor_inputs=247,prior_physical_history_inputs=348,immediate_prior_inputs=365,held_input_count=len(inputs),
        all247_348_and365_paths_retained=True,unchanged_full8_digest_reuses=reused,
        explicit_prior348_replacements=authority['prior348_replacements'],
        explicit_immediate_prior_replacements=authority['immediate_prior_replacements'],
        baseline_is_retained_provenance_not_current_health=True,
        historical_membership_barrier_and_original_pidfd_anchors_reused_as_immutable_identity_only=True,
        stale_publisher_or_heartbeat_health_proof_reused=False,old_failed_scope_or_quality_evidence_reused=False,
        current_TCP_or_holderFD_or_heartbeat_or_future_exit_files_held_as_inputs=False,
        runtime_freshness_resources_engineering_or_scientific_launch_qualified=False,
        no_large_model_MAME_ROM_or_array_body_read=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--selection',type=Path)
    parser.add_argument('--selection-sha256');parser.add_argument('--expected-source-sha256');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.prepare:
        print('SOURCE_ONLY_NO_READS_IMPORTS_PROBES_OR_WRITES');return
    require(all((args.selection,args.selection_sha256,args.expected_source_sha256,args.output)),
            'Explicit selected Root DATA arguments required')
    print(json.dumps(assemble(args.selection,args.selection_sha256,args.expected_source_sha256,args.output),allow_nan=False))


if __name__=='__main__':main()
