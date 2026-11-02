"""Default inert. ROOT-only metadata construction or a read-only fresh192 check."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import types
import urllib.request

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME / 'logs/managed-learning-20261015/run-26'
D = RUN / 'current-continuation-raw4hz-source-only-original01-20261027'
OBS = D / 'live-original01/read-only-fresh192-three-owner-observation-original01'
HELPER = D / 'fresh-fleet-rolemap/slot0-preview-flag-correction-original02/exec_fresh_fleet_roles_v2.py'
HELPER_SHA = 'd922ecfac60acaafa7e1624007a7bb1b8bb9e267277a7629d14e27098b47a94d'
CORE = RUN / 'deadline-score32-later-policy-firstSave-original01-preparation-20261026/postcapture-current-main-reconciliation-original01/current-main-binding.json'
CORE_SHA = '07b2e23220d9d4d5950a6a6259f268bcc71102f4b228f694cc0f3cbe1505f468'
PRIOR = RUN / 'preview-selected-client-wallclock-original01-preparation-20261027/actual-RAW-timing-diagnostic-original04-20261027/readonly-current-output-to-diagnostic227-reconciliation-original01/actual-diagnostic227-main-binding-original01.json'
SLOTS = {str(i) for i in range(192)}
UNIT_FIELDS = ('Id','MainPID','ActiveState','SubState','Type','Restart','NRestarts','InvocationID','ControlGroup')
COLLECTOR_ENV_KEYS = {'LD_PRELOAD','LUA_PATH','LUA_CPATH','SDL_VIDEODRIVER','SDL_AUDIODRIVER'}


def require(value, text):
    if not value: raise ValueError(text)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def pin(path):
    path = Path(path); before = path.lstat()
    require(path.is_absolute() and path.resolve(strict=True) == path and stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1 and 0 < before.st_size <= 2_000_000, 'Bounded regular source/metadata required')
    with path.open('rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Source changed before read')
        raw = stream.read(2_000_001)
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Source changed while reading')
    require(identity(path.lstat()) == identity(before), 'Source changed after read')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))


def read(p):
    require(pin(p['path']) == p and p['identity']['mode'] == '0o444'
            and p['identity']['uid'] == os.getuid(), 'Immutable exact metadata required')
    value = json.loads(Path(p['path']).read_text())
    require(pin(p['path']) == p, 'Metadata changed during parsing'); return value


def read_closed_startup_report(p, closure):
    """The original08c producer report retains normal0664; never chmod its outputs."""
    expected = D/'live-original01/startup-CPU-original01/output/cpu-verification.json'
    require(p['path'] == str(expected) and p['sha256'] == 'c6421325c526d243b19b26bbd1fade85ba416cc31658652d78fe961f53aba7a1'
            and p['identity']['mode'] == '0o664' and p['identity']['uid'] == os.getuid()
            and pin(expected) == p, 'Exact closed producer report full pin/mode required')
    require(closure['original'] == dict(pid=1066391,starttime_ticks=117539835,
            invocation_id='3be8cc9037e04976b4edaf1ae2852a7f',
            unit='robotron-managed-run-26-continuation-raw4hz-original01-20261027-startup-CPU-original01.service',
            timer='robotron-managed-run-26-continuation-raw4hz-original01-20261027-startup-CPU-original01.timer',
            timer_invocation_id='0038827186454bd4b15ee29bb36ba466',observed_live=True)
            and type(closure['original_exit']) is int and closure['original_exit'] == 0
            and closure['lifecycle_complete'] is True and closure['unit_released'] is True
            and closure['audit_success'] is True and closure['all_six_original_archive_commands_succeeded'] is True,
            'Exact original successful producer/closure required')
    result = json.loads(expected.read_text()); require(pin(expected) == p, 'Closed report changed during read')
    job_pin = pin(D/'live-original01/startup-CPU-original01/job.json'); job = read(job_pin)
    flattened = dict(path=job_pin['path'],sha256=job_pin['sha256'],**job_pin['identity'])
    require(result['job_file'] == flattened and result['root_job'] == job,
            'Closed producer report must name its actual exact original job')
    return result


def module(p, name):
    raw = Path(p['path']).read_bytes(); require(pin(p['path']) == p, 'Module pin differs')
    result = types.ModuleType(name); result.__file__ = p['path']
    exec(compile(raw,p['path'],'exec'),result.__dict__); return result


def publish(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False); stream.write('\n'); stream.flush()
        os.fchmod(stream.fileno(),0o444); os.fsync(stream.fileno())
    return pin(path)


def api_roles(api, rolemap):
    rows = api['client_rows']
    require(api['client_count'] == 192 and len(rows) == 192
            and api['training_enabled'] is True and api['measurement_active'] is False
            and api['memory_buffer_size'] == 6000000
            and api['managed_experiment'] == 'CE4096-LR125-survival32M-original01-20261023'
            and api['lr'] == 6.25e-6 and api['pipeline_read_error'] == ''
            and api['bank_persistence_read_error'] == '' and api['host_pipeline']['available'] is True,
            'Actual192 live training/hot6M/current .125 recipe scope required')
    exposure = api['host_pipeline']['learning_exposure']
    for key,reason in (('optimizer','optimizer_restore_begin'),('replay','directory_adopt_begin')):
        row = exposure[key]
        require(row['enabled'] is True and row['available'] is True and row['process_id'] == 1062324
                and row['epoch'] == 1 and row['epoch_reason'] == reason,
                'Current actual replay/optimizer producer incarnation required')
    result = {}
    for row in rows:
        slot = str(row['client_slot'])
        require(type(row['client_slot']) is int and slot in SLOTS and slot not in result
                and row['eval'] is rolemap['slot_eval'][slot]
                and type(row['client_id']) is int, 'Actual unique slot/role/CID required')
        result[slot] = dict(client_id=row['client_id'],eval=row['eval'])
    require(len({row['client_id'] for row in result.values()}) == 192, 'Duplicate actual CID')
    return result


def validate_capture(capture, h, manifest, rolemap):
    require(capture['schema'] == 'robotron-actual-fresh192-three-owner-readonly-capture-v1'
            and set(capture['owners']) == set(capture['owners_after']) == {'trainer','fleet','supplemental0'}
            and capture['owners'] == capture['owners_after'] and set(capture['actors']) == SLOTS,
            'Exact stable three-owner full192 capture required')
    owners = capture['owners']
    expected = {'trainer':(1062324,117468652,'429ceaf754ca49b495056180a0350411'),
                'fleet':(1073404,117607824,'f791a854723b4f90ab5fa8a637a13868'),
                'supplemental0':(1122536,117687032,'ccdd44624bd142db8effc98139940e7d')}
    for key,(pid,born,inv) in expected.items():
        unit,process = owners[key]['unit'],owners[key]['process']
        require(process['pid'] == pid and process['starttime_ticks'] == born
                and unit['MainPID'] == str(pid) and unit['InvocationID'] == inv
                and unit['ControlGroup'] == process['cgroup'] and unit['ActiveState'] == 'active'
                and unit['SubState'] == 'running' and unit['NRestarts'] == '0'
                and process['uids'] == [os.getuid()]*4, 'Actual original owner identity differs')
    for slot,actor in capture['actors'].items():
        env = dict(manifest['actor_environment'],ROBOTRON_CLIENT_SLOT=slot,
                   ROBOTRON_PREVIEW_CLIENT='1' if slot == '0' else '0')
        command,output,probe = h.prepare_launch(manifest,rolemap,manifest['actor_args'],env)
        observed_output = {k:v for k,v in output.items() if k.startswith('ROBOTRON_') or k in COLLECTOR_ENV_KEYS}
        require(probe is None and actor['command'] == command and actor['environment'] == observed_output
                and actor['uids'] == [os.getuid()]*4 and actor['affinity'] == owners['fleet']['process']['affinity'],
                'Actor literal command/environment/role/affinity differs')
        if slot == '0':
            require(actor == owners['supplemental0']['process'], 'Slot0 must be its actual separate MainPID')
        else:
            require(actor['parent_pid'] == owners['fleet']['process']['pid']
                    and actor['cgroup'] == owners['fleet']['process']['cgroup'], 'Original191 parent/cgroup differs')
    require(len({(a['pid'],a['starttime_ticks']) for a in capture['actors'].values()}) == 192,
            'Duplicate actor birth')
    before = api_roles(capture['api_before'],rolemap); after = api_roles(capture['api'],rolemap)
    require(before == after, 'API role/CID mapping raced capture')
    return after


def prepare(output, *, preflight=False):
    output = Path(output)
    require(output.parent.resolve(strict=True) == D and not output.exists(), 'NEW output directly under owned continuation only')
    proof_pin = pin(OBS/'independent-actual-fresh192-roles-sources-and-three-owners.json'); proof = read(proof_pin)
    require(proof_pin['sha256'] == '3ea4faa22cd18d7096edc0081e20ef2c16a493ad32090ae4878fa6e1ba7847c5'
            and proof['status'] == 'READONLY_PASS' and proof['actor_count'] == 192
            and proof['eval_count'] == 37 and proof['training_count'] == 155
            and proof['original191_exact'] is True and proof['slot0_separate_unit_ownership'] is True,
            'Actual independent192 proof required')
    capture = read(proof['capture']); manifest = read(capture['manifest'])
    hp = pin(HELPER); require(hp['sha256'] == HELPER_SHA, 'Corrected V2 required')
    h = module(hp,'_fresh192_roles'); rolemap = h.validate_manifest(manifest)
    h.verify_rendered_wrapper(capture['manifest'],manifest)
    roles = validate_capture(capture,h,manifest,rolemap)
    core_pin = pin(CORE); require(core_pin['sha256'] == CORE_SHA, 'Historical core197 source set required')
    core = read(core_pin); require(len(core['held_hashes']) == 197, 'Historical core source set differs')
    startup_result_pin = pin(D/'live-original01/startup-save-original01/ROOT-actual-startup-save-and-copy-result.json')
    startup_result = read(startup_result_pin); acquisition = read(startup_result['acquisition'])
    transition = acquisition['completed_slot_transition']; completed = str(GAME/'models_dqn/managed_save.request.json.completed')
    trainer = capture['owners']['trainer']
    trainer_id = dict(pid=trainer['process']['pid'],starttime_ticks=trainer['process']['starttime_ticks'],
        unit=trainer['unit']['Id'],invocation_id=trainer['unit']['InvocationID'],cgroup=trainer['unit']['ControlGroup'])
    require(acquisition['schema'] == 'robotron-owned-phase-snapshot-acquisition-v1'
            and acquisition['purpose'] == 'startup' and acquisition['client_count'] == 0
            and acquisition['owner_before'] == acquisition['owner_after'] == trainer_id
            and transition['before']['actual_pin']['path'] == transition['after']['actual_pin']['path'] == completed
            and transition['before']['actual_pin']['sha256'] == core['held_hashes'][completed]
            and transition['before']['archive']['sha256'] == core['held_hashes'][completed]
            and read(transition['request']['archive']) == read(transition['after']['archive']) == {'tag':acquisition['tag']}
            and transition['request']['actual_pin']['sha256'] == transition['after']['actual_pin']['sha256'],
            'Only the actual owned startup completed-slot transition may replace its historical source hash')
    read(transition['before']['archive'])
    phase = pin(capture['trainer_curated_environment']['DQN_PRIORITY_PHASE_RECORD'])
    require(phase == startup_result['phase']
            and phase['sha256'] == capture['trainer_curated_environment']['DQN_PRIORITY_PHASE_RECORD_SHA256']
            == acquisition['phase_record_sha256'], 'Actual active new resume record required')
    cpu_pin = pin(D/'live-original01/startup-CPU-original01/output/cpu-verification.json')
    closure_pin = pin(D/'live-original01/startup-CPU-original01/execution/root-original-result-and-owned-release.json')
    closure = read(closure_pin)
    cpu = read_closed_startup_report(cpu_pin,closure)
    require(cpu['status'] == 'PASS' and cpu['sha256'] == startup_result['source']['sha256']
            and cpu['phase_acquisition'] == acquisition
            and cpu['script']['sha256'] == '08c165ed917b8633ab658a8efbc915f81e37adff21c1330cd5806cd3148f4051'
            and cpu['saved_priority_metric_phase']['last_resume_record_sha256'] == phase['sha256']
            and type(closure['original_exit']) is int and closure['original_exit'] == 0
            and closure['lifecycle_complete'] is True and closure['unit_released'] is True,
            'Actual new-owner startup08c phase PASS and original CPU closure required')
    installed = capture['actual_installed_source_pins']; sources = {}
    old_unit_paths = {p for p in core['held_hashes'] if p.startswith('/run/user/')}
    require(len(old_unit_paths) == 4, 'Explicit retired unit/dropin set differs')
    overrides = dict(installed); overrides[capture['actual_wrapper']['path']] = capture['actual_wrapper']
    overrides[completed] = transition['after']['actual_pin']
    control_transition = None
    control_path = str(GAME/'models_dqn/learning_control.json')
    control_pin = pin(control_path)
    if control_pin['sha256'] != core['held_hashes'][control_path]:
        event_pin = pin(D/'stop-original01/final_supported_pause_prefetch_quiesced.json')
        event = read(event_pin)
        base_control_pin = pin(D/'stop-preparation-original01/original-learning-control.json')
        base_control = read(base_control_pin)
        require(base_control_pin['sha256'] == core['held_hashes'][control_path]
                and event['purpose'] == 'final'
                and event['label'] == 'scorecarry-current227-preserve-original01-20261027-final'
                and event['control'] == control_pin, 'Only exact original final-owned control transition allowed')
        current_control = json.loads(Path(control_path).read_text())
        require(pin(control_path) == control_pin and current_control == dict(base_control,
                measurement=dict(label=event['label'],checkpoint=None,cohort_s=3600,timeout_s=7200)),
                'Final-owned control must preserve every original recipe field')
        overrides[control_path] = control_pin
        control_transition = dict(base_control_archive=base_control_pin,actual_final_pause_event=event_pin,
            current_control=control_pin,scope='Owned final label retained as data; new-process observed managed_measurement empty and measurement_active false.')
    for path,sha in core['held_hashes'].items():
        if path in old_unit_paths: continue
        actual = pin(path)
        require(actual == overrides[path] if path in overrides else actual['sha256'] == sha,
                'Core source escaped installed-source transition: '+path)
        sources[path] = actual
    extra = [*installed.values(),capture['actual_wrapper'],capture['manifest'],manifest['helper'],
             manifest['rolemap'],manifest['collector'],pin(__file__),phase,startup_result_pin,
             startup_result['acquisition'],cpu_pin,closure_pin,
             pin(D/'fresh-fleet-rolemap/slot0-owned-recovery-original01/actual-slot0-owned-exec-job-original01.json')]
    slot0_job = read(extra[-1]); extra.extend([slot0_job['source'],slot0_job['quarantine_admission']])
    if control_transition is not None:
        extra.extend([control_transition['base_control_archive'],control_transition['actual_final_pause_event']])
    for owner in capture['owners'].values():
        extra.append(pin('/run/user/'+str(os.getuid())+'/systemd/transient/'+owner['unit']['Id']))
    for p in extra:
        require(pin(p['path']) == p, 'New actual source identity changed'); sources[p['path']] = p
    held = {path:p['sha256'] for path,p in sources.items()}
    held_sha = hashlib.sha256(json.dumps(held,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    owner_ids = {key:dict(pid=v['process']['pid'],starttime_ticks=v['process']['starttime_ticks'],
        unit=v['unit']['Id'],invocation_id=v['unit']['InvocationID'],cgroup=v['unit']['ControlGroup'])
        for key,v in capture['owners'].items()}
    if preflight:
        return dict(status='METADATA_PREFLIGHT_PASS',source_count=len(held),actor_count=192,
            eval_count=37,training_count=155,all_actual_metadata_and_source_checks_before_mkdir=True,
            producer_report_mode_preserved=cpu_pin['identity']['mode'],outputs_written=0,
            API_proc_unit_or_control_queries=0,model_binary_or_replay_body_reads=0)
    output.mkdir(mode=0o700)
    policy = dict(schema='robotron-fresh192-split-owner-supervision-policy-v1',trainer=owner_ids['trainer'],
        fleet=owner_ids['fleet'],supplemental0=owner_ids['supplemental0'],baseline_owners=capture['owners'],
        baseline_actors=capture['actors'],actual_API_roles=roles,trainer_curated_environment=capture['trainer_curated_environment'],
        source_files=sources,held_hashes_sha256=held_sha,source_count=len(held),
        actor_ownership={s:'supplemental0' if s == '0' else 'fleet' for s in SLOTS},
        limits=dict(missing_slots=0,automatic_birth_replacements=0),
        process_environment_capture_scope='All ROBOTRON_ plus exact1f41 LD_PRELOAD/LUA/SDL fields; MAME_BIN is not exported by that collector record.',
        scope='Strict current three-owner registry; later actual actor replacement requires ROOT rebind, never fake parentage.')
    policy_pin = publish(output/'current-fresh192-supervision-policy.json',policy)
    binding = dict(schema='robotron-current-fresh192-continuation-registry-v1',owner=owner_ids['trainer'],
        actors=[dict(slot=int(s),pid=capture['actors'][s]['pid'],starttime_ticks=capture['actors'][s]['starttime_ticks'],
                     mask=capture['actors'][s]['affinity']) for s in sorted(SLOTS,key=int)],
        held_hashes=held,experiment=core['experiment'],baseline_API=capture['api'],supervision_policy=policy_pin,
        prior_binding=pin(PRIOR),historical_core197_binding=core_pin,actual_192_capture=proof['capture'],
        independent_actual_192_proof=proof_pin,actor_ownership=policy['actor_ownership'],actual_roles=roles,
        actual_owners=owner_ids,canonical_RAW_Lua_SHA=h.RAW_SHA,eval_count=37,training_count=155,
        retired_unit_source_paths={p:core['held_hashes'][p] for p in sorted(old_unit_paths)},
        owned_managed_save_slot_transition=transition,active_resume_phase_record=phase,
        owned_final_control_transition=control_transition,
        startup_checkpoint=startup_result['source'],startup_CPU_report=cpu_pin,startup_CPU_closure=closure_pin,
        new_live_game_cohort=True,old_training_and_fixed32_quality_history_unchanged=True,
        scope='New same-state trainer+fresh192 actors, including separately owned supplemental slot0; old227 is historical.')
    bp = publish(output/'current-fresh192-main-binding.json',binding)
    return publish(output/'prepared-fresh192-binding-NOT-CANONICALLY-ADOPTED.json',dict(
        schema='robotron-fresh192-binding-construction-v1',binding=bp,policy=policy_pin,
        source=pin(__file__),source_count=len(held),actual_capture=proof['capture'],independent_proof=proof_pin,
        canonical_state_written=False,live_process_or_source_actions=0))


def check_live(binding_pin):
    """Fresh read-only strict-current check; never calls a legacy binding guard."""
    binding = read(binding_pin)
    require(binding['schema'] == 'robotron-current-fresh192-continuation-registry-v1', 'Explicit fresh binding ABI required')
    policy = read(binding['supervision_policy'])
    require(policy['schema'] == 'robotron-fresh192-split-owner-supervision-policy-v1', 'Explicit split-owner policy ABI required')
    for path,expected in policy['source_files'].items():
        require(pin(path) == expected and binding['held_hashes'][path] == expected['sha256'], 'Current selected source changed')
    capture = read(binding['actual_192_capture']); manifest = read(capture['manifest'])
    h = module(manifest['helper'],'_fresh192_monitor_roles'); rolemap = h.validate_manifest(manifest)
    h.verify_rendered_wrapper(capture['manifest'],manifest)
    collector = module(manifest['collector'],'_fresh192_monitor_processes')
    def api():
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as stream:
            raw = stream.read(2_000_001)
        require(len(raw) <= 2_000_000, 'Bounded API metadata only'); value = json.loads(raw)
        age = time.time()-value['ts']; pipeline_age = value['pipeline_snapshot_age_s']
        require(type(age) in (int,float) and math.isfinite(age) and 0 <= age <= 5
                and type(pipeline_age) in (int,float) and math.isfinite(pipeline_age) and 0 <= pipeline_age <= 5,
                'Current API and pipeline producer snapshots must both be fresh')
        for key in ('optimizer','replay'):
            actual = value['host_pipeline']['learning_exposure'][key]
            previous = capture['api']['host_pipeline']['learning_exposure'][key]
            require(all(actual[k] == previous[k] for k in ('process_id','instance_monotonic_ns','epoch','epoch_reason')),
                    'Current pipeline producer differs from actual current baseline')
        return value
    def owners():
        result = {}
        for key in ('trainer','fleet','supplemental0'):
            expected = policy[key]; fields = h.unit_show(expected['unit'])
            result[key] = dict(unit={k:fields[k] for k in UNIT_FIELDS},process=collector.process_record(expected['pid']))
        return result
    started = time.monotonic(); first_api = api(); before = owners()
    require(before == policy['baseline_owners'], 'Original current owner incarnation changed')
    actors = {slot:collector.process_record(actor['pid']) for slot,actor in policy['baseline_actors'].items()}
    require(actors == policy['baseline_actors'], 'A current actor birth/source/env/parent changed; ROOT rebind required')
    for key in ('trainer','fleet','supplemental0'):
        group = Path('/sys/fs/cgroup'+policy[key]['cgroup']); actual = set()
        for raw_pid in (group/'cgroup.procs').read_text().split():
            pid = int(raw_pid)
            try: command = Path('/proc',raw_pid,'cmdline').read_bytes().split(b'\0')
            except FileNotFoundError: continue
            if command[:1] == [b'/usr/games/mame']: actual.add(pid)
        expected = {a['pid'] for slot,a in actors.items() if policy['actor_ownership'][slot] == key}
        require(actual == expected, 'Owned scope has extra or missing MAME processes')
    environment = {}
    for item in Path('/proc',str(policy['trainer']['pid']),'environ').read_bytes().split(b'\0'):
        if b'=' not in item: continue
        k,v = item.split(b'=',1); k,v = k.decode(),v.decode()
        if k.startswith(('DQN_','ROBOTRON_','CUDA_')) or k == 'PYTHONUNBUFFERED': environment[k] = v
    require(environment == policy['trainer_curated_environment'], 'Current full controlled trainer environment changed')
    after = owners(); last_api = api()
    observed = dict(schema=capture['schema'],owners=before,owners_after=after,actors=actors,
                    api_before=first_api,api=last_api)
    roles = validate_capture(observed,h,manifest,rolemap)
    require(roles == policy['actual_API_roles'] and time.monotonic()-started <= 5,
            'Actual CID map changed or current observation exceeded bound')
    return dict(status='READONLY_PASS',binding=binding_pin,source_count=len(binding['held_hashes']),
        actor_count=192,eval_count=37,training_count=155,three_original_owners_unchanged=True,
        supplemental0_parent_not_fabricated=True,learner_frame_count=last_api['learner_frame_count'],
        training_steps=last_api['training_steps'],fps=last_api['fps'],api_timestamp=last_api['ts'],
        controls_process_or_canonical_writes=0)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--prepare',action='store_true')
    p.add_argument('--check',action='store_true'); p.add_argument('--binding'); p.add_argument('--binding-sha256')
    p.add_argument('--preflight',action='store_true')
    p.add_argument('--output'); p.add_argument('--expected-source-sha256'); args = p.parse_args()
    require(sum((args.prepare,args.check,args.preflight)) <= 1, 'Select one explicit mode')
    if not(args.prepare or args.check or args.preflight):
        print('PLAN_ONLY: no reads, construction, live probes or controls'); return
    own = pin(__file__); require(own['sha256'] == args.expected_source_sha256
            and own['identity']['mode'] == '0o444', 'Frozen selected constructor required')
    if args.prepare or args.preflight: result = prepare(args.output,preflight=args.preflight)
    else:
        bp = pin(args.binding); require(bp['sha256'] == args.binding_sha256, 'Exact actual binding SHA required')
        result = check_live(bp)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
