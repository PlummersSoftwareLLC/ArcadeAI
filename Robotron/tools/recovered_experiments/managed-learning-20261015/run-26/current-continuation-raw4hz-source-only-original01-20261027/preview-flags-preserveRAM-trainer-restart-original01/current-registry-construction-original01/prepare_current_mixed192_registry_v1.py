"""Inert by default. ROOT-selected mixed-survivor registry construction/check only."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import types
import urllib.request

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
PARENT = GAME/'logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027'
CASE = PARENT/'preview-flags-preserveRAM-trainer-restart-original01'
LIVE = CASE/'live-original01'
PRIOR_PATH = PARENT/'actual-fresh192-binding-original01/current-fresh192-main-binding.json'
PRIOR_SHA = '0b1b8fb71122597412f83f39eaaa4739b4b5c71d148dad05981574b822233cff'
PRIMITIVES = PARENT/'fresh192-binding-construction-original01/prepare_fresh192_binding_v3.py'
PRIMITIVES_SHA = '15f2a66039626a4e22a7d0cdc6231f7305ca1f79c9c67012946a2b814e502893'
SOCKET_SHA = '12214060f4d0caac8e7479dbfa3a29b3c7413516dfd73266c92a809c99eb29ec'
SLOTS = {str(i) for i in range(192)}
UNIT_FIELDS = ('Id','MainPID','ActiveState','SubState','Type','Restart','NRestarts','InvocationID','ControlGroup')


def require(value, message):
    if not value: raise ValueError(message)


def primitives():
    require(not PRIMITIVES.is_symlink() and stat.S_IMODE(PRIMITIVES.stat().st_mode) == 0o444,
            'Frozen original registry primitives required')
    raw = PRIMITIVES.read_bytes(); require(hashlib.sha256(raw).hexdigest() == PRIMITIVES_SHA, 'Original primitives changed')
    p = types.ModuleType('_closed_registry_primitives'); p.__file__ = str(PRIMITIVES)
    exec(compile(raw,str(PRIMITIVES),'exec'),p.__dict__); return p


def producer_json(p, pin, expected_path):
    require(pin['path'] == str(expected_path) and pin['identity']['mode'] in ('0o644','0o664')
            and pin['identity']['uid'] == os.getuid() and p.pin(expected_path) == pin,
            'Exact bounded normal-producer full pin required')
    value = json.loads(expected_path.read_text()); require(p.pin(expected_path) == pin, 'Producer changed during parse'); return value


def api_roles(api, baseline_roles, owner_pid, producer_baseline=None, fresh=False):
    require(api['client_count'] == 192 and len(api['client_rows']) == 192 and api['training_enabled'] is True
            and api['measurement_active'] is False and api['managed_measurement'] == {}
            and api['memory_buffer_size'] == 6000000
            and api['managed_experiment'] == 'CE4096-LR125-survival32M-original01-20261023'
            and api['lr'] == 6.25e-6 and api['pipeline_read_error'] == ''
            and api['bank_persistence_read_error'] == '' and api['host_pipeline']['available'] is True,
            'Actual192 current recipe/hot replay/healthy unpaused scope required')
    if fresh:
        age = time.time()-api['ts']; pipeline_age = api['pipeline_snapshot_age_s']
        require(all(type(v) in (int,float) and math.isfinite(v) and 0 <= v <= 5 for v in (age,pipeline_age)),
                'Current API and pipeline must both be fresh')
    exposure = api['host_pipeline']['learning_exposure']
    for key,reason in (('optimizer','optimizer_restore_begin'),('replay','directory_adopt_begin')):
        row = exposure[key]
        require(row['enabled'] is True and row['available'] is True and row['process_id'] == owner_pid
                and row['epoch'] == 1 and row['epoch_reason'] == reason, 'Actual restored producer lineage differs')
        if producer_baseline is not None:
            require(all(row[k] == producer_baseline[key][k] for k in
                    ('process_id','instance_monotonic_ns','epoch','epoch_reason')), 'Current producer incarnation changed')
    result = {}
    for row in api['client_rows']:
        slot = str(row['client_slot'])
        require(type(row['client_slot']) is int and slot in SLOTS and slot not in result
                and row['eval'] is baseline_roles[slot]['eval'] and type(row['client_id']) is int,
                'Actual unique role/slot/CID required')
        result[slot] = dict(client_id=row['client_id'],eval=row['eval'])
    require(len({r['client_id'] for r in result.values()}) == 192, 'Duplicate actual CID'); return result


def owner_id(observation):
    unit,process = observation['unit'],observation['process']
    return dict(pid=process['pid'],starttime_ticks=process['starttime_ticks'],unit=unit['Id'],
                invocation_id=unit['InvocationID'],cgroup=unit['ControlGroup'])


def validate_capture(capture, prior, old_policy, new_owner, new_slot0, h, manifest, rolemap):
    require(capture['schema'] == 'robotron-actual-fresh192-three-owner-readonly-capture-v1'
            and set(capture['actors']) == set(capture['prior_actor_births']) == SLOTS and capture['owners'] == capture['owners_after']
            and set(capture['owners']) == {'trainer','fleet','supplemental0'}, 'Actual stable mixed192 capture required')
    owners = capture['owners']
    require(owner_id(owners['trainer']) == new_owner and owner_id(owners['supplemental0']) == new_slot0
            and owner_id(owners['fleet']) == prior['actual_owners']['fleet'], 'Actual current three owners differ')
    require(new_owner['pid'] == 1369090 and new_owner['starttime_ticks'] == 118144098
            and new_owner['invocation_id'] == '853cc815c77b4d75bcef0c8fdd144758'
            and new_slot0['pid'] == 1382787 and new_slot0['starttime_ticks'] == 118204588
            and new_slot0['invocation_id'] == 'dcb390fca76844999cfe3b3262680411', 'Exact actual trainer/new0 scope required')
    require(owners['fleet'] == old_policy['baseline_owners']['fleet'], 'Original supervisor changed')
    for key,observation in owners.items():
        unit,proc = observation['unit'],observation['process']
        require(unit['MainPID'] == str(proc['pid']) and unit['ControlGroup'] == proc['cgroup']
                and unit['ActiveState'] == 'active' and unit['SubState'] == 'running' and unit['NRestarts'] == '0'
                and proc['uids'] == [os.getuid()]*4, 'Live owner identity/status differs')
    transitions = {}
    for slot,actor in capture['actors'].items():
        old = old_policy['baseline_actors'][slot]
        env = dict(manifest['actor_environment'],ROBOTRON_CLIENT_SLOT=slot,ROBOTRON_PREVIEW_CLIENT='1' if slot == '0' else '0')
        command,output,probe = h.prepare_launch(manifest,rolemap,manifest['actor_args'],env)
        expected_env = {k:v for k,v in output.items() if k.startswith('ROBOTRON_') or k in
                        ('LD_PRELOAD','LUA_PATH','LUA_CPATH','SDL_VIDEODRIVER','SDL_AUDIODRIVER')}
        require(probe is None and actor['command'] == command and actor['environment'] == expected_env
                and actor['uids'] == [os.getuid()]*4 and actor['affinity'] == old['affinity']
                and actor['executable'] == old['executable'], 'Actual actor source/role/argv/affinity/MAME identity differs')
        if slot == '0': require(actor == owners['supplemental0']['process'], 'Current0 must be real separate MainPID')
        else: require(actor['parent_pid'] == owners['fleet']['process']['pid']
                      and actor['cgroup'] == owners['fleet']['process']['cgroup'], 'Fleet actor parent/cgroup differs')
        survived = (actor['pid'],actor['starttime_ticks']) == (old['pid'],old['starttime_ticks'])
        if survived: require(actor == old, 'Surviving process record changed')
        observation = capture['prior_actor_births'][slot]
        require(observation['original_pid'] == old['pid'] and observation['original_starttime_ticks'] == old['starttime_ticks']
                and observation['current_pid'] == actor['pid'] and observation['current_starttime_ticks'] == actor['starttime_ticks']
                and observation['same_original_birth'] is survived
                and observation['original_birth_present'] is survived
                and (observation['observed_original_pid_birth'] == old['starttime_ticks']) is survived,
                'Positive original birth presence/absence must join every actual survivor/replacement')
        transitions[slot] = dict(prior_pid=old['pid'],prior_starttime_ticks=old['starttime_ticks'],
            actual_pid=actor['pid'],actual_starttime_ticks=actor['starttime_ticks'],survived=survived,
            prior_birth_observation=observation,fresh_emulator_game_cohort=not survived,
            post_reconnect_initial_game_known_start=None,
            registry_does_not_certify_complete_game_eligibility=True)
    require(len({(a['pid'],a['starttime_ticks']) for a in capture['actors'].values()}) == 192, 'Duplicate actual actor birth')
    roles = api_roles(capture['api_before'],prior['actual_roles'],new_owner['pid'])
    require(roles == api_roles(capture['api'],prior['actual_roles'],new_owner['pid']), 'Actual API reconnected map raced')
    return roles,transitions


def prepare(p, selection_pin, output, preflight=False):
    selection = p.read(selection_pin)
    require(set(selection) == {'schema','prior_binding','capture','independent_proof','new_trainer_owner',
            'new_slot0_owner','startup_report','startup_closure'}
            and selection['schema'] == 'robotron-root-current-mixed192-registry-selection-v1', 'Explicit ROOT actual selection required')
    require(selection['prior_binding']['path'] == str(PRIOR_PATH) and selection['prior_binding']['sha256'] == PRIOR_SHA,
            'Exact prior213 registry required')
    prior = p.read(selection['prior_binding']); old_policy = p.read(prior['supervision_policy'])
    capture = p.read(selection['capture']); proof = p.read(selection['independent_proof'])
    new_owner = p.read(selection['new_trainer_owner']); new0 = p.read(selection['new_slot0_owner'])
    require(proof['status'] == 'READONLY_PASS' and proof['capture'] == selection['capture']
            and proof['actor_count'] == 192 and proof['eval_count'] == 37 and proof['training_count'] == 155,
            'Independent actual post-thaw192 proof required')
    manifest = p.read(capture['manifest']); h = p.module(manifest['helper'],'_mixed192_role_primitives')
    rolemap = h.validate_manifest(manifest); h.verify_rendered_wrapper(capture['manifest'],manifest)
    roles,transitions = validate_capture(capture,prior,old_policy,new_owner,new0,h,manifest,rolemap)
    stop_pin = p.pin(CASE/'stop-original01/result.json'); stop = p.read(stop_pin)
    install_pin = p.pin(CASE/'source-install-original01/ROOT-actual-source-install-receipt-original01.json'); install = p.read(install_pin)
    save_pin = p.pin(LIVE/'startup-save-original01/ROOT-actual-startup-save-and-copy-result.json'); save = p.read(save_pin)
    acquisition = p.read(save['acquisition']); phase = p.read(save['phase'])
    require(stop['status'] == 'CURRENT_TRAINER_STOPPED_AND_FULL_STATE_HOT_REPLAY_PRESERVED'
            and stop['saved']['strict_phase_verified'] is True and stop['saved']['replay_bank_consistency_verified'] is True
            and install['actual_stop_result'] == stop_pin and install['same192_actor_births_preserved'] is True
            and save['owner'] == new_owner and acquisition['owner_before'] == acquisition['owner_after'] == new_owner
            and acquisition['purpose'] == 'startup' and acquisition['client_count'] == 0
            and phase['checkpoint'] == {k:stop['saved']['checkpoint'][k] for k in ('path','sha256','bytes')},
            'Actual stopped/installed/zero-input startup same-state lineage differs')
    closure = p.read(selection['startup_closure'])
    require(type(closure['original_exit']) is int and closure['original_exit'] == 0
            and all(closure[k] is True for k in ('lifecycle_complete','unit_released','audit_success','all_six_original_archive_commands_succeeded')),
            'Original startupCPU successful owned closure required')
    cpu = producer_json(p,selection['startup_report'],LIVE/'startup-CPU-original01/output/cpu-verification.json')
    job_pin = p.pin(LIVE/'startup-CPU-original01/job.json'); job = p.read(job_pin)
    config_pin = p.pin(LIVE/'startup-CPU-original01/controller-config.json'); config = p.read(config_pin)
    require(cpu['job_file'] == dict(path=job_pin['path'],sha256=job_pin['sha256'],**job_pin['identity'])
            and cpu['root_job'] == job and closure['original']['unit'] == config['unit']
            and cpu['status'] == 'PASS' and cpu['script']['sha256'] == '08c165ed917b8633ab658a8efbc915f81e37adff21c1330cd5806cd3148f4051'
            and cpu['sha256'] == save['source']['sha256'] and cpu['phase_acquisition'] == acquisition
            and cpu['saved_priority_metric_phase']['last_resume_record_sha256'] == save['phase']['sha256'],
            'Exact normal-producer08c report/job/closure/phase source join required')
    socket = str(GAME/'Scripts/dqn/socket_server.py'); control_path = str(GAME/'models_dqn/learning_control.json')
    completed = str(GAME/'models_dqn/managed_save.request.json.completed')
    event_pin = p.pin(CASE/'stop-original01/final_supported_pause_prefetch_quiesced.json'); event = p.read(event_pin)
    base_pin = p.pin(CASE/'stop-preparation-original01/original-learning-control.json'); base = p.read(base_pin)
    control = producer_json(p,event['control'],Path(control_path))
    require(base_pin['sha256'] == prior['held_hashes'][control_path] and event['purpose'] == 'final'
            and control == dict(base,measurement=dict(label=event['label'],checkpoint=None,cohort_s=3600,timeout_s=7200)),
            'Only the exact next owned-final control transition allowed')
    terminal_path = GAME/'models_dqn/managed-measurements'/(event['label']+'.json'); terminal_pin = p.pin(terminal_path)
    terminal = producer_json(p,terminal_pin,terminal_path)
    require(terminal['active'] is False and terminal['phase'] == 'finished' and terminal['complete'] is True
            and terminal['valid'] is False and terminal['reason'] == 'trainer_shutdown'
            and terminal['label'] == event['label'] and terminal['request'] == control['measurement'],
            'Normal producer old pause label must be terminal, never a quality pass')
    transition = acquisition['completed_slot_transition']
    require(transition['before']['actual_pin']['sha256'] == prior['held_hashes'][completed]
            and transition['before']['archive']['sha256'] == prior['held_hashes'][completed]
            and p.read(transition['request']['archive']) == p.read(transition['after']['archive']) == {'tag':acquisition['tag']},
            'Exact owned startup completed-slot transition required')
    overrides = dict(install['actual_installed_pins']); overrides[control_path] = event['control']; overrides[completed] = transition['after']['actual_pin']
    require(set(install['actual_installed_pins']) == {socket} and overrides[socket]['sha256'] == SOCKET_SHA
            and install['old_archives'][socket]['sha256'] == prior['held_hashes'][socket], 'Only selected122 socket source installed')
    settings_path = str(GAME/'models_dqn/game_settings.json')
    settings_pin = p.pin(settings_path); settings_archive = p.pin(CASE/'stop-preparation-original01/original-game-settings.json')
    old_settings = old_policy['source_files'][settings_path]
    require(settings_pin['sha256'] == settings_archive['sha256'] == old_settings['sha256']
            and all(settings_pin['identity'][k] == old_settings['identity'][k] for k in ('device','bytes','mode','uid','nlink'))
            and producer_json(p,settings_pin,Path(settings_path)) == p.read(settings_archive),
            'Final settings rewrite must preserve exact pre-stop bytes/permissions/ownership')
    overrides[settings_path] = settings_pin
    retired = {str(Path('/run/user',str(os.getuid()),'systemd/transient')/old_policy[k]['unit']) for k in ('trainer','supplemental0')}
    sources = {}
    for path,old_pin in old_policy['source_files'].items():
        if path in retired: continue
        expected = overrides.get(path,old_pin); require(p.pin(path) == expected, 'Unqualified retained source change: '+path); sources[path] = expected
    extra = [selection_pin,selection['capture'],selection['independent_proof'],selection['new_trainer_owner'],selection['new_slot0_owner'],
             selection['startup_report'],selection['startup_closure'],save['phase'],save['acquisition'],stop_pin,install_pin,save_pin,
             event_pin,base_pin,terminal_pin,job_pin,config_pin,settings_archive,p.pin(__file__)]
    for observation in capture['owners'].values(): extra.append(p.pin(Path('/run/user',str(os.getuid()),'systemd/transient')/observation['unit']['Id']))
    for value in extra: require(p.pin(value['path']) == value, 'Current metadata source changed'); sources[value['path']] = value
    for path,value in overrides.items(): require(p.pin(path) == value, 'Actual source override changed'); sources[path] = value
    held = {path:value['sha256'] for path,value in sources.items()}
    survived = sum(t['survived'] for t in transitions.values()); replaced = 192-survived
    require(replaced > 0, 'This original scope records the observed watchdog replacement disposition')
    output = Path(output); require(output.parent.resolve(strict=True) == CASE and not output.exists(), 'NEW case-local registry output required')
    if preflight: return dict(status='METADATA_PREFLIGHT_PASS',survivors=survived,replacements=replaced,source_count=len(held),outputs_written=0)
    output.mkdir(mode=0o700)
    policy = dict(schema='robotron-fresh192-split-owner-supervision-policy-v1',**{k:owner_id(v) for k,v in capture['owners'].items()},
        baseline_owners=capture['owners'],baseline_actors=capture['actors'],actual_API_roles=roles,
        trainer_curated_environment=capture['trainer_curated_environment'],source_files=sources,source_count=len(held),
        held_hashes_sha256=hashlib.sha256(json.dumps(held,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        actor_ownership={slot:'supplemental0' if slot == '0' else 'fleet' for slot in SLOTS},limits=dict(missing_slots=0,automatic_birth_replacements=0))
    policy_pin = p.publish(output/'current-mixed192-supervision-policy.json',policy)
    binding = dict(schema=prior['schema'],owner=new_owner,actors=[dict(slot=int(slot),pid=a['pid'],starttime_ticks=a['starttime_ticks'],mask=a['affinity'])
        for slot,a in sorted(capture['actors'].items(),key=lambda pair:int(pair[0]))],held_hashes=held,experiment=prior['experiment'],
        baseline_API=capture['api'],supervision_policy=policy_pin,prior_binding=selection['prior_binding'],actual_192_capture=selection['capture'],
        independent_actual_192_proof=selection['independent_proof'],actual_roles=roles,actual_owners={k:owner_id(v) for k,v in capture['owners'].items()},
        actor_ownership=policy['actor_ownership'],canonical_RAW_Lua_SHA=h.RAW_SHA,eval_count=37,training_count=155,
        active_resume_phase_record=save['phase'],owned_managed_save_slot_transition=transition,
        unchanged_settings_producer_rewrite=dict(prior_source=old_settings,pre_stop_archive=settings_archive,current_source=settings_pin,bytes_unchanged=True),
        owned_final_control_transition=dict(base_control_archive=base_pin,actual_final_pause_event=event_pin,current_control=event['control'],terminal_record=terminal_pin),
        startup_checkpoint=save['source'],startup_CPU_report=selection['startup_report'],startup_CPU_closure=selection['startup_closure'],
        new_live_game_cohort=False,mixed_physical_game_cohorts=True,actor_transitions=transitions,
        emulator_survivor_count=survived,emulator_replacement_count=replaced,full192_RAM_continuity_attempt_succeeded=False,
        pre_thaw_same192_receipts_retained_as_stage_specific=True,old_slot0_exit_code_known=False,
        old_training_and_fixed32_quality_history_unchanged=True,
        scope='Trainer/model/replay continued; post-thaw watchdog replaced actualsubset of emulator processes. Survivors reconnected from existing RAM; replacements are fresh emulator starts. Registry does not certify game-start/whole-game eligibility or all192 RAM continuity.')
    bp = p.publish(output/'current-mixed192-main-binding.json',binding)
    return p.publish(output/'prepared-current-mixed192-registry-NOT-CANONICALLY-ADOPTED.json',dict(schema='robotron-current-mixed192-registry-construction-v1',
        binding=bp,policy=policy_pin,source=p.pin(__file__),source_count=len(held),survivors=survived,replacements=replaced,canonical_state_written=False))


def check_live(p, binding_pin):
    binding = p.read(binding_pin); policy = p.read(binding['supervision_policy'])
    require(binding['mixed_physical_game_cohorts'] is True and binding['new_live_game_cohort'] is False,
            'Explicit actual mixed-cohort registry required')
    for path,expected in policy['source_files'].items():
        require(p.pin(path) == expected and binding['held_hashes'][path] == expected['sha256'], 'Current source changed')
    capture = p.read(binding['actual_192_capture']); manifest = p.read(capture['manifest'])
    h = p.module(manifest['helper'],'_mixed_current_roles'); rolemap = h.validate_manifest(manifest)
    h.verify_rendered_wrapper(capture['manifest'],manifest)
    collector = p.module(manifest['collector'],'_mixed_current_processes')
    def api():
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as stream: raw = stream.read(2_000_001)
        require(len(raw) <= 2_000_000, 'Bounded API metadata required'); value = json.loads(raw)
        roles = api_roles(value,policy['actual_API_roles'],policy['trainer']['pid'],
                          capture['api']['host_pipeline']['learning_exposure'],fresh=True)
        require(roles == policy['actual_API_roles'], 'Current CID map changed; ROOT rebind required'); return value
    def owners():
        result = {}
        for key in ('trainer','fleet','supplemental0'):
            owner = policy[key]; fields = h.unit_show(owner['unit'])
            result[key] = dict(unit={k:fields[k] for k in UNIT_FIELDS},process=collector.process_record(owner['pid']))
        return result
    started = time.monotonic(); first = api(); before = owners()
    require(before == policy['baseline_owners'], 'Current owner incarnation changed')
    actors = {slot:collector.process_record(actor['pid']) for slot,actor in policy['baseline_actors'].items()}
    require(actors == policy['baseline_actors'], 'Current actor birth/source/environment changed; ROOT rebind required')
    for key in ('trainer','fleet','supplemental0'):
        group = Path('/sys/fs/cgroup'+policy[key]['cgroup']); actual = set()
        for raw_pid in (group/'cgroup.procs').read_text().split():
            try: command = Path('/proc',raw_pid,'cmdline').read_bytes().split(b'\0')
            except FileNotFoundError: continue
            if command[:1] == [b'/usr/games/mame']: actual.add(int(raw_pid))
        expected = {a['pid'] for slot,a in actors.items() if policy['actor_ownership'][slot] == key}
        require(actual == expected, 'Owned scope MAME membership differs')
    environment = {}
    for item in Path('/proc',str(policy['trainer']['pid']),'environ').read_bytes().split(b'\0'):
        if b'=' not in item: continue
        k,v = item.split(b'=',1); k,v = k.decode(),v.decode()
        if k.startswith(('DQN_','ROBOTRON_','CUDA_')) or k == 'PYTHONUNBUFFERED': environment[k] = v
    require(environment == policy['trainer_curated_environment']
            and {k:v for k,v in environment.items() if k.startswith('CUDA_')} ==
                dict(CUDA_DEVICE_ORDER='PCI_BUS_ID',CUDA_VISIBLE_DEVICES='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'),
            'Exact full current trainer environment/GPU binding changed')
    after = owners(); last = api()
    require(before == after and time.monotonic()-started <= 5, 'Current observation raced or exceeded bound')
    return dict(status='READONLY_PASS',binding=binding_pin,source_count=len(binding['held_hashes']),
        actor_count=192,eval_count=37,training_count=155,
        emulator_survivor_count=binding['emulator_survivor_count'],emulator_replacement_count=binding['emulator_replacement_count'],
        full192_RAM_continuity_attempt_succeeded=False,mixed_physical_game_cohorts=True,
        learner_frame_count=last['learner_frame_count'],training_steps=last['training_steps'],fps=last['fps'],
        controls_process_or_canonical_writes=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--preflight',action='store_true'); parser.add_argument('--selection'); parser.add_argument('--selection-sha256')
    parser.add_argument('--check',action='store_true'); parser.add_argument('--binding'); parser.add_argument('--binding-sha256')
    parser.add_argument('--output'); parser.add_argument('--expected-source-sha256'); args = parser.parse_args()
    require(sum((args.prepare,args.preflight,args.check)) <= 1, 'Select one mode')
    if not(args.prepare or args.preflight or args.check): print('PLAN_ONLY: no imports, reads, probes or controls'); return
    p = primitives(); own = p.pin(__file__)
    require(own['sha256'] == args.expected_source_sha256 and own['identity']['mode'] == '0o444', 'Frozen selected source required')
    if args.check:
        bp = p.pin(args.binding); require(bp['sha256'] == args.binding_sha256, 'Exact current binding required')
        result = check_live(p,bp)
    else:
        selection = p.pin(args.selection); require(selection['sha256'] == args.selection_sha256, 'Exact ROOT selection required')
        result = prepare(p,selection,args.output,preflight=args.preflight)
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
