"""Root-only data preparation for one original old-mode stop; default inert.

Reads held filesystem metadata/source files and exact current control bytes.
Never imports a candidate, queries a process/unit/API, controls a service,
opens replay/model payloads, or starts the resulting controller. Fresh owners
and native task births must come from Root's immutable observation. The stop
adapter independently rechecks them and all247 held inputs before controls.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G/'logs/managed-learning-20261015/run-26'
D = B/'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06'
H = D/'handoff-preservation-original01'
HERE = H/'stop-sources'
OLD = B/'current-continuation-raw4hz-source-only-original01-20261027/preview-flags-preserveRAM-trainer-restart-original01/stop-sources'
EVIDENCE = H/'current-owner-evidence-original01'
CONTROL = G/'models_dqn/learning_control.json'
CONSOLE = B/'power-outage-recovery-20261027-original01/runtime/trainer-console.log'
PERSISTENT = {'Thread-1 (serve','Thread-2 (_samp','Thread-3 (_cons','Thread-4 (start','Thread-5 (stats'}
SELECTED = {
    'stop': (HERE/'stop_owned_current_round_training_v3.py','fe4a804db13347a74af512bca37adaf9aeb4660025cc9efe373b22a086ded7db'),
    'controller': (HERE/'control_owned_current_stop900_v1.py','3016bffdec578cacbb354e5d8d453b05e84d42ed8a42e0a3874d91f439c063e8'),
    'source_peer': (HERE/'independent-owned-current-stop-v3-and-900-resource-source-peer-v1.json','6d382596a3cb60a0306536444754079558bd45bacbd2db34a686266bba6b2c7a'),
    'guard_closeout': (H/'stop-focused-six-original01-preparation/independent-original-CPU-scope-closeout.json','22ed0d258a5305fb1b81cd1eb68bf052a1eb38b837cee9676fba53a1d86bb514'),
    'main_binding': (B/'post-recovery-evaluation-isolation-original01-20261027/durable-window03-D7-fixed-RCRC-study-original01/main-binding.json','c75868e40f0b63fb088818b3b9a285831ef22c1b4dabe97f1a5e06601059cf44'),
    'boot_CPU_report': (B/'power-outage-recovery-20261027-original01/post-training-CPU-verification-original02.json','e04dc403489d2545fd4e67909537d2684f20f4a52c15eee0df1edb36de2cb114'),
    'phase_record': (G/'models_dqn/resume-records/resume-b99e50b9b1e7339f27c44de399e556ea0213c011ce2480c71eccd1e70ebd179e.json','f919a465369d4f28266693ae7a438946ef688a9f6087322c4bf917e6c5d327d2'),
    'phase_anchor': (B/'post-natural-turnover-durable-next-candidate-20261029-original03/endpoint-CPU.json','d9dfb33918a98a3164f503fafe7bc6ac4dfca1df15c252b531f4d0dd1eca8990'),
    'ring_storage_before': (EVIDENCE/'current-live-header-inventory-NOT-QUIESCENT.json','255cd2cc1e07223399202193cec21b08138d5012ae8884889a6bdf99a08fe2d7'),
    'ring_insert_anchor': (EVIDENCE/'original-adoption-pointer-anchor.json','1b7ca229e20e8fe43ca8dd94490d4f4acdd21aef3dceb8712bee1e20d0e0fe74'),
    'measurement_clock_inference': (EVIDENCE/'original-boot-measurement-clock-source-inference.json','eea4ed1d14c8fcd52687caec248b0ac85a8d6409f958be7bc27f5d86c1bd4db1'),
    'linux_utilities': (OLD/'current192_linux_stop_v1.py','3268d0bf2e18d3a7aa9c09addd331b1e42353be45c666203f0818caf294d7437'),
    'bank_reader': (G/'tools/score_carry_proposal/bank_generation_witness.py','dcbebda66feac28a312819a83c8915a8f6cb812ace78b10f2368c7ab4ab4804e'),
    'bank_intent': (G/'tools/score_carry_proposal/bank_shutdown_intent_v1.py','741fb4cbb3c049de4808331ebc8029e5f123adcc310c150efafbac3451171f87'),
    'bank_semantics': (OLD/'current192_poststop_only_v1.py','7c8e995d67bfbd826e87d327a5dc4dfa796bb12e4c368a3eafd37e23c8466278'),
}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,mode=oct(stat.S_IMODE(info.st_mode)),
        uid=info.st_uid,nlink=info.st_nlink)


def read_file(path, *, limit=4 << 20):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(),
            'Canonical selected metadata/source file required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
            and before.st_nlink == 1 and 0 <= before.st_size <= limit,
            'Owned bounded single-link metadata/source file required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Selected source open race')
        raw = stream.read(limit+1)
        require(len(raw) == before.st_size and identity(os.fstat(stream.fileno())) == identity(before)
                == identity(path.lstat()), 'Selected metadata/source changed while reading')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before)), raw


def selected(name):
    path, digest = SELECTED[name]
    value, raw = read_file(path)
    require(value['sha256'] == digest, 'Frozen source/evidence changed: '+name)
    return value, raw


def read_pin(value):
    actual, raw = read_file(value['path'])
    require(actual == value, 'Actual full8 metadata changed')
    return json.loads(raw)


def publish(path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(),0o444); os.fsync(stream.fileno())
    fd = os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return read_file(path)[0]


def owner_from_binding(binding, key):
    row = binding['owners'][key]
    process = row['process']
    return dict(unit=row['unit'],pid=process['pid'],starttime_ticks=process['starttime_ticks'],
                invocation_id=row['invocation'],cgroup=process['cgroup'])


def prepare(args):
    own, _ = read_file(Path(__file__).resolve())
    require(own['sha256'] == args.expected_source_sha256 and own['identity']['mode'] == '0o444',
            'Explicit frozen metadata preparer required')
    observed_pin, raw = read_file(Path(args.runtime_snapshot))
    require(observed_pin['sha256'] == args.runtime_snapshot_sha256
            and observed_pin['identity']['mode'] == '0o444', 'Immutable actual Root runtime observation required')
    observation = json.loads(raw)
    require(observation['schema'] == 'robotron-root-current-training-stop-preparation-observation-v1',
            'Root observation schema differs')
    now = time.time(); stamp = observation['observed_unix_s']
    require(type(stamp) in (int,float) and math.isfinite(stamp) and 0 <= now-stamp <= 60,
            'Root must supply fresh owners/native births within60 seconds before preparation')
    pins, values = {}, {}
    for name in SELECTED:
        value, raw = selected(name); pins[name] = value
        if Path(value['path']).suffix == '.json':
            values[name] = json.loads(raw)
    binding, boot = values['main_binding'], values['boot_CPU_report']
    require(len(binding['inputs']) == 247, 'Exact historical current D7 source domain required')
    # Stat only here. The selected Stop performs fresh fullSHA on all247
    # before its first control. Never open model/ring/MAME/interpreter bodies.
    for path, value in binding['inputs'].items():
        actual = Path(path)
        require(actual.resolve(strict=True) == actual and not actual.is_symlink()
                and identity(actual.lstat()) == value['identity'], 'Held input identity changed: '+path)
    for key in ('trainer','fleet'):
        owner = observation[key]
        require(set(owner) == {'unit','pid','starttime_ticks','invocation_id','cgroup'}
                and owner == owner_from_binding(binding,key), 'Fresh Root owner differs from selected original: '+key)
    native = observation['persistent_native']
    require(type(native) is dict and len(native) == 5
            and {row['comm'] for row in native.values()} == PERSISTENT
            and all(type(tid) is str and re.fullmatch('[1-9][0-9]*',tid)
                    and set(row) == {'starttime_ticks','comm'}
                    and type(row['starttime_ticks']) is int and row['starttime_ticks'] > 0
                    for tid,row in native.items()), 'Five exact actual source-bound native TID/birth/name rows required')
    inference = values['measurement_clock_inference']
    anchor = values['ring_insert_anchor']
    instances = observation['exposure_instances']
    require(set(instances) == {'optimizer','replay'}
            and all(type(instances[key]) is int and instances[key] > 0
                    and instances[key] == binding['exposure'][key]['instance_monotonic_ns']
                    == inference[key+'_identity']['instance_monotonic_ns'] for key in instances)
            and anchor['instance_monotonic_ns'] == instances['replay']
            and inference['process_id'] == observation['trainer']['pid']
            and inference['process_starttime_ticks'] == observation['trainer']['starttime_ticks']
            and anchor['owner'] == observation['trainer'], 'Actual unchanged optimizer/replay lineage differs')
    require(inference['boot_CPU_report']['sha256'] == pins['boot_CPU_report']['sha256']
            and all(inference['boot_saved_clocks'][key] == value for key,value in boot['saved_clocks'].items())
            and boot['selected_lr_scale'] == .0625 and boot['saved_optimizer_lrs'] == [3.125e-6]
            and boot['resume_record']['sha256'] == pins['phase_record']['sha256'], 'Original loaded clocks/.0625 recipe differs')
    phase, founder = values['phase_record'], values['phase_anchor']['priority_phase']
    require(phase['schema'] == 'robotron-priority-metric-start-v1' and phase['action'] == 'resume'
            and phase['metric'] == phase['previous_metric'] == founder['metric'] == 'ce'
            and phase['phase_id'] == founder['phase_id'] == boot['phase_id']
            and phase['root_precommit_sha256'] == founder['root_precommit_sha256']
            and phase['checkpoint'] == boot['checkpoint'], 'Original CE founder/boot resume join differs')
    close = values['guard_closeout']; report = read_pin(close['actual_report'])
    guard_job = read_pin(close['original_job'])
    require(close['schema'] == 'robotron-engineering-original-CPU-independent-closeout-v1'
            and close['status'] == 'PASS_ENGINEERING_ONLY' and close['actual_exit'] == 0
            and close['actual_CPU_cores'] == 2 and close['actual_memory_bytes'] == 4 << 30
            and close['actual_runtime_limit_s'] == 180
            and close['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified'] is True
            and report['status'] == 'PASS' and report['tests_run'] == 6 and report['failures'] == report['errors'] == []
            and report['original_job'] == close['original_job']
            and report['fixture']['sha256'] == '0cf9ce90dc571c2429397fd87a848802e65c38d5c36e176c21a5f22ada017da2'
            and pins['stop'] in guard_job['inputs'], 'Exact actual closed Stop6 qualification required')
    role_doc_path = B/'power-outage-recovery-20261027-original01/preserved-192-rolemap.json'
    role_doc_pin, role_raw = read_file(role_doc_path)
    roles = json.loads(role_raw)['slot_eval']
    require(roles == binding['slot_eval'] and set(roles) == {str(i) for i in range(192)}
            and all(type(value) is bool for value in roles.values()) and sum(roles.values()) == 37,
            'Exact immutable155TRAIN/37EVAL rolemap required')
    control_pin, control_raw = read_file(CONTROL)
    base = json.loads(control_raw)
    require(base['lr_scale'] == .0625 and base.get('measurement') is None,
            'Current control must be original .0625 with no owned or foreign measurement')
    require(observation['console'] == str(CONSOLE), 'Actual original append-console path differs')
    case = args.case
    require(re.fullmatch(r'continuous-stop-[A-Za-z0-9_-]{1,45}',case), 'One explicit unique original stop case required')
    output = Path(args.output)
    require(output.is_absolute() and output.parent.resolve(strict=True) == HERE
            and output.resolve(strict=False) == output and not output.exists(), 'Fresh exclusive stop metadata directory required')
    require(time.time()-stamp <= 60, 'Root observation expired during metadata preparation')
    output.mkdir(mode=0o700)
    archived_control = publish(output/'base-control.json',control_raw)
    raw_roles = publish(output/'original-slot-eval-rolemap.json',roles)
    dependencies = {key:pins[key] for key in ('linux_utilities','bank_reader','bank_intent','bank_semantics')}
    qualifiers = {key:pins[key] for key in ('source_peer','guard_closeout','boot_CPU_report','phase_record',
        'phase_anchor','ring_storage_before','ring_insert_anchor','measurement_clock_inference')}
    inputs = [own,observed_pin,pins['stop'],pins['controller'],pins['main_binding'],archived_control,raw_roles,
              role_doc_pin,close['actual_report'],close['original_job']]
    inputs += list(dependencies.values()) + list(qualifiers.values())
    require(len({value['path'] for value in inputs}) == len(inputs), 'Distinct explicit source/metadata inputs required')
    job = dict(schema='robotron-owned-current-round-stop-job-v1',authorized=True,case=case,
        source=pins['stop'],output=str(output/'stop-output'),trainer=observation['trainer'],fleet=observation['fleet'],
        persistent_native=native,exposure_instances=instances,console=observation['console'],
        main_binding=pins['main_binding'],base_control=archived_control,rolemap=raw_roles,
        experiment=binding['experiment'],boot_resume_sha256=pins['phase_record']['sha256'],
        boot_saved_clocks=inference['boot_saved_clocks'],actor_command=binding['actor_command'],
        mame_executable=binding['actor_executable']['path'],dependencies=dependencies,inputs=inputs,
        original_attempt=1,no_retry=True,Root_runtime_observation=observed_pin,qualifications=qualifiers,
        explicit_recipe=dict(lr_scale=.0625,lr=3.125e-6,priority_metric='ce',batch_size=4096,n_step=3,
                             max_samples_per_frame=8,replay_capacity=6000000,continuous_mode='0'),
        population_scope='Actual same-owner variable0..192; never adopt cached D7 actor births/CIDs as current',
        root_header_is_live_NOT_quiescent=True,actual_stop_or_saved_integrity_qualified=False,
        source_install_or_new_trainer_authorized=False)
    jp = publish(output/'job.json',job)
    # Keep actual full8 job/metadata pins in the job. Existing C218 accepts
    # its documented reduced5 config identities without invented timestamps.
    def reduced(value):
        return dict(value,identity={k:value['identity'][k] for k in ('device','inode','mode','uid','nlink')})
    argv = ['/usr/bin/python3.12','-I','-B',pins['stop']['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256']]
    config = dict(unit='robotron-owned-current-round-stop-original01-20261029.service',
        output=str(output/'controller-execution-original01'),argv=argv,
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=900',
                    'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[reduced(value) for value in [jp]+inputs],observation_s=960)
    cp = publish(output/'controller-config.json',config)
    require(read_file(CONTROL)[0] == control_pin, 'Current control changed during preparation; no stop is authorized')
    return publish(output/'prepared-current-original-stop900-NOT-LAUNCHED.json',dict(
        schema='robotron-current-owned-stop900-actual-data-preparation-v1',status='DATA_PREPARED_NOT_LAUNCHED',
        source=own,job=jp,config=cp,Root_runtime_observation=observed_pin,selected_stop=pins['stop'],
        selected_controller=pins['controller'],qualifications=qualifiers,
        canonical_control_before=control_pin,archived_base_control=archived_control,original_roles=raw_roles,
        Root_controller_argv=['/usr/bin/python3.12','-I','-B',pins['controller']['path'],'--execute','--config',cp['path'],
                              '--expected-source-sha256',pins['controller']['sha256']],
        expected_original_controller_owner=str(output/'controller-execution-original01/root-original-identity.json'),
        expected_original_controller_closeout=str(output/'controller-execution-original01/root-original-result-and-owned-release.json'),
        expected_stop_outcome=str(output/'stop-output/original-outcome.json'),
        expected_stopped_preservation_authority=str(output/'stop-output/stopped-preservation-authority.json'),
        runtime_freshly_rechecked_only_by_selected_Stop=True,metadata_preparer_did_not_query_live_runtime=True,
        actual_stop_controller_owner=None,actual_stop_result=None,actual_saved_payload_integrity=None,
        any_install_or_replacement_started=False,scientific_launch_qualified=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--expected-source-sha256')
    parser.add_argument('--runtime-snapshot');parser.add_argument('--runtime-snapshot-sha256')
    parser.add_argument('--output');parser.add_argument('--case',default='continuous-stop-original01-20261029')
    args = parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY_NO_READS_IMPORTS_OUTPUTS_PROBES_OR_CONTROLS');return
    print(json.dumps(prepare(args)),flush=True)


if __name__ == '__main__':
    main()
