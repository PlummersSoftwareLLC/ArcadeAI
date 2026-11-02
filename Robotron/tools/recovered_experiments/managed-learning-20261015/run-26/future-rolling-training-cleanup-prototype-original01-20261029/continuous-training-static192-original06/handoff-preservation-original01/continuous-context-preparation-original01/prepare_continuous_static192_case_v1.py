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
MODE_ROOT = HERE.parent.parent
HC = MODE_ROOT/'health-consumer-original01'
PROFILE = MODE_ROOT/'private-static-profile-consumers-original01/static_profile_contract_v2.py'
REGISTRY_SHA = '2f3eddaf75ee3b9a875d0a621a63eeea7274eae3afa75bcceb309002233316d1'
PROFILE_SHA = '5260662e651c6f26cde42bb04cde913dd51015658d071499b6966e661e6a451b'
MAP_SHA = '4629c151898362a71c3aa1f011c2088154c1cd69b9abc8959efdad79103c7410'
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


def assemble(selection_path, selection_sha, expected_source_sha, output):
    own = small_pin(Path(__file__).resolve())
    require(own['sha256'] == expected_source_sha and own['identity']['mode'] == '0o444',
            'Explicit frozen preparer source required')
    selected = small_pin(selection_path)
    require(selected['sha256'] == selection_sha, 'Root selection SHA differs')
    choice = checked(selected)
    require(choice['schema'] == 'robotron-root-continuous-static192-case-assembly-selection-v1'
            and set(choice) == {'schema','supervisor_config','publisher_snapshot',
                'owner_API_capture','parent_case','extra_inputs'},
            'Exact explicit Root retained-metadata selection required')
    cfg = checked(choice['supervisor_config'])
    snapshot = checked(choice['publisher_snapshot'])
    capture = checked(choice['owner_API_capture'])
    parent = checked(choice['parent_case'])
    require(choice['parent_case']['sha256'] == PARENT_SHA
            and parent['schema'] == 'robotron-round-main-health-case-v1'
            and len(parent['inputs']) == 247, 'Exact normalized historical247 parent required')
    require(capture['schema'] == 'robotron-root-static192-owner-and-API-metadata-capture-v1',
            'Actual Root-owned metadata capture required')
    owners = checked(capture['owners']); api = checked(capture['baseline_API'])
    api_capture = checked(capture['baseline_API_capture'])
    api_raw = checked(capture['baseline_API'], raw=True)
    require(api_capture['value'] == api and api_capture['raw_wire'].encode() == api_raw
            and api_capture['sha256'] == capture['baseline_API']['sha256'],
            'Actual baseline raw/API capture joins differ')
    require(cfg['schema'] == 'robotron-continuous-training-supervisor-job-v1'
            and cfg['mode'] == MODE and cfg['original_attempt'] == 1 and type(cfg['original_attempt']) is int
            and cfg['no_retry'] is True and cfg['startup_s'] == 5
            and cfg['fault_cleanup_s'] == 10 and cfg['max_faults'] == 3
            and cfg['api_root'] == 'http://127.0.0.1:8771'
            and not (set(cfg['parent_environment']) & LITERAL_INPUT_KEYS),
            'Selected literal supervisor profile/INPUT keyword-disjoint contract differs')
    require(snapshot['schema'] == 'robotron-continuous-training-static192-snapshot-v2'
            and snapshot['mode'] == MODE and snapshot['errors'] == []
            and snapshot['trainer'] == cfg['trainer'] and snapshot['rolemap'] == cfg['rolemap']
            and snapshot['source_authority'] == cfg['source_authority']
            and snapshot['supervisor']['source']['sha256'] == SUPERVISOR_SHA
            and snapshot['supervisor']['unit'] == cfg['unit']
            and snapshot['initial_admission']['complete'] is True
            and snapshot['initial_admission']['slots_ever_bound'] == list(range(192))
            and set(snapshot['slots']) == SLOTS,
            'Actual retained admitted-original192 snapshot/owner/source differs')
    authority = checked(cfg['source_authority']); rolemap = checked(cfg['rolemap'])
    require(authority['schema'] == 'robotron-root-continuous-main-startup-qualified-v1'
            and authority['trainer'] == cfg['trainer'], 'Actual qualified startup authority differs')
    registry = load(HC/'continuous_static192_registry_v1.py', REGISTRY_SHA, '_static_case_registry')
    profile = load(PROFILE, PROFILE_SHA, '_static_case_inventory')
    membership_pin = snapshot['original_membership']
    membership = checked(membership_pin); original = membership['data']['original_slots']
    require(set(original) == SLOTS, 'Immutable exact original192 membership required')
    map_pin = small_pin(HC/'prospective-static192-eight-role-observer-source-map-v1.json')
    require(map_pin['sha256'] == MAP_SHA, 'Exact frozen static eight-role map required')
    source_map = checked(map_pin)['observer_sources']
    require(set(source_map) == {'client','worker','health','health_base','registry',
            'durability','control','interpreter'}, 'Exact eight logical observer roles required')

    # Full-value source authority is separate from the inherited247 inventory.
    source_pins = authority['canonical_sources'] + [snapshot['supervisor']['source'], cfg['physical_helper']]
    source_pins += [v for key,v in source_map.items() if key != 'interpreter']
    source_pins += [small_pin(HC/'review_continuous_static192_observer_v1.py'), small_pin(PROFILE)]
    sources = {}
    for value in source_pins:
        checked(value, raw=True, immutable=False)
        require(value['path'] not in sources or sources[value['path']] == value,
                'Conflicting selected source pins')
        sources[value['path']] = value

    # Never read a large historical executable/model/ROM body in this preparer.
    # All unchanged full8 identities retain the already held historical digest.
    inputs = {}; unchanged = 0; refreshed = []
    explicit = list(choice['extra_inputs']) + cfg['inputs'] + list(sources.values())
    explicit += [choice[k] for k in ('supervisor_config','publisher_snapshot','owner_API_capture','parent_case')]
    explicit += [capture[k] for k in ('owners','baseline_API','baseline_API_capture')]
    explicit += [cfg['source_authority'],cfg['rolemap'],map_pin,membership_pin,
                 snapshot['initial_admission']['immutable_all192_barrier']]
    overrides = {}
    for value in explicit:
        require(type(value) is dict and set(value) == {'path','sha256','bytes','identity'}
                and current(value['path']) == value['identity'] and value['bytes'] == value['identity']['bytes'],
                'Explicit held-input full8 identity differs')
        if value['bytes'] <= LIMIT:
            # General historical inputs may be root-owned executables; small_pin
            # checks full bytes without imposing event producer ownership/mode.
            require(small_pin(Path(value['path'])) == value, 'Explicit held-input SHA differs')
        require(value['path'] not in overrides or overrides[value['path']] == value,
                'Conflicting explicit held-input authority')
        overrides[value['path']] = value
    for path, old in parent['inputs'].items():
        now = current(path)
        if path in overrides:
            inputs[path] = thin(overrides[path])
        elif now == old['identity']:
            inputs[path] = old; unchanged += 1
        else:
            require(now['bytes'] <= LIMIT, 'Changed large input lacks explicit Root fullpin: ' + path)
            inputs[path] = thin(small_pin(Path(path))); refreshed.append(path)
    for path,value in overrides.items():
        inputs[path] = thin(value)
    mame = parent['actor_executable']
    require(mame['path'] == '/usr/games/mame'
            and {k:v for k,v in current(mame['path']).items() if k != 'nlink'} == mame['identity'],
            'Historical literal MAME executable identity changed')
    input_env = {}
    generations = set()
    for slot,row in original.items():
        spawn = checked(row['spawn_intent'])
        input_env[slot] = spawn['data']['input_environment']
        generations.add(spawn['data']['policy']['measurement_generation'])
    require(len(generations) == 1, 'Original spawn policies cross measurement generations')
    recipe = {key:api[key] for key in ('lr','epsilon','expert_ratio')}
    require(all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in recipe.values())
            and type(api['managed_experiment']) is str and api['managed_experiment'],
            'Nonempty actual baseline experiment/fixed finite recipe required')
    case = dict(schema=registry.CASE_SCHEMA, inputs=inputs,
        units=dict(trainer=cfg['trainer']['unit'], fleet=cfg['unit']), owners=owners,
        slot_eval=rolemap['slot_eval'], actor_environment=cfg['actor_common_environment'],
        actor_command=cfg['mame_argv'], actor_executable=mame,
        actor_affinity=owners['fleet']['process']['affinity'], recipe=recipe,
        exposure=api['host_pipeline']['learning_exposure'], round_root=cfg['output'],
        source_guard=str(HC/'continuous_static192_health_v1.py'), experiment=api['managed_experiment'],
        continuous=dict(mode=MODE,accepted_profile='STATIC_ORIGINAL192_NO_FAULT_ADOPTION',
            maximum_proof_gap_s=2.0,narrow_API_exception_TTL_s=.5,epoch=snapshot['epoch'],
            snapshot_path=str(Path(cfg['output'])/'status.json'),supervisor=snapshot['supervisor'],
            trainer=cfg['trainer'],server_stamp=cfg['trainer']['server_stamp'],rolemap=cfg['rolemap'],
            source_authority=cfg['source_authority'],source_pins=list(sources.values()),
            policy_generation=next(iter(generations)),
            initial_barrier=snapshot['initial_admission']['immutable_all192_barrier'],
            original_membership=membership_pin,original_slots=original,
            launch_argv=cfg['launch_argv'],input_environment_by_slot=input_env))
    registry.validate_case(case)  # Pure immutable metadata joins, no live census.
    for slot,compact in snapshot['slots'].items():
        row = registry.slot_view(case,slot,compact)
        registry.original(case,slot,row)
        if row['eval_only']:
            require(row['state'] in ('active_eval','retiring_eval','closed_eval'), 'EVAL fault/replacement refused')
            if row['state'] != 'active_eval':
                natural,result = registry.natural(case,slot,row)
                if row['state'] == 'closed_eval':
                    registry.closed(case,slot,row,natural,result)
        else:
            require(row['state'] == 'active_train' and row['natural_result'] is row['closure'] is None,
                    'TRAIN must remain its exact original active process')
    for path,value in inputs.items():
        require(current(path) == value['identity'], 'Held input changed during assembly: ' + path)
    require(output.is_absolute() and output.parent.resolve(strict=True) == HERE
            and not output.exists(), 'One exclusive case DATA output directory under preparer required')
    output.mkdir(mode=0o700)
    inventory = dict(schema='robotron-root-continuous-static192-input-inventory-v1',
        status='ROOT_SELECTED_EXACT_HELD_INPUTS',mode=MODE,source_authority=cfg['source_authority'],
        inputs=inputs,input_count=len(inputs),parent_case=choice['parent_case'],
        replacements={p:dict(before=v,after=inputs[p]) for p,v in parent['inputs'].items() if v != inputs[p]},
        added_inputs={p:v for p,v in inputs.items() if p not in parent['inputs']})
    inventory_pin = put(output/'exact-held-input-inventory.json',inventory)
    case['input_inventory_authority'] = inventory_pin
    class Reader:
        @staticmethod
        def checked(value):
            checked(value,raw=True)
            return Path(value['path'])
    profile.validate_inventory(case, Reader)
    case_pin = put(output/'continuous-main-case.json',case)
    return put(output/'prepared-actual-continuous-static192-case-NOT-QUALIFIED.json',dict(
        schema='robotron-root-continuous-static192-case-preparation-v1',status='DATA_PREPARED_NOT_QUALIFIED',
        source=own,selection=selected,case=case_pin,input_inventory_authority=inventory_pin,
        selected_retained_evidence=choice,actual_held_input_count=len(inputs),historical_parent_input_count=247,
        unchanged_full8_historical_digest_reuses=unchanged,changed_small_input_full_SHA_refreshes=refreshed,
        no_historical_input_dropped=True,no_large_executable_model_ROM_or_array_body_read=True,
        admission_basis='EVER_BOUND_ORIGINAL192_NOT_SIMULTANEOUS',simultaneous192_claimed=False,
        actual_runtime_freshness_or_resources_qualified=False,static_context_engineering_qualified=False,
        scientific_launch_qualified=False,quality_qualified=False,main_runtime_changed=False,
        next_Root_only_prepare_argv=['/usr/bin/python3.12','-I','-B',
            str(MODE_ROOT/'new-static-context-engineering-original01-preparation/prepare_static192_engineering_v1.py'),
            '--prepare','--case',case_pin['path'],'--case-sha256',case_pin['sha256'],'--output',
            str(MODE_ROOT/'new-static-context-engineering-original01-preparation/actual-new-main-contexts-original01')]))


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
