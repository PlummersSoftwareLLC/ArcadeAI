"""Recovered-round health integration for the original all64 complete-game protocol.

The internal historical selection descriptor retains its minimum50 transport
floor. Original native and reviewer predicates already require exactly64 actual
complete games/two per slot; the additional pair/job requirement is explicitly64.
Nothing here launches a process, loads Torch, acquires a lease or promotes.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE = ROOT/'logs/managed-learning-20261015/run-26'
ORIGINAL = BASE/'future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-protocol-interface-correction-original01'
NATIVE = ORIGINAL/'run_quality32_quota64_selected_original01_v2.py'
NATIVE_SHA = '9ecf99ba66b76b8bd31de06e894124e495d3fedba86ba5a1c36db628ccb95f83'
REVIEW = ORIGINAL/'read_quality32_quota64_selected_original01_v2.py'
REVIEW_SHA = 'e2231b41f69671ebb0d80bf52a3aeb20e273486fc58934c33ecef61eec185d2c'
TEMPLATE = BASE/'quality32-protected1741-vs-currentLR125-quota64Protocol-firstSave-original01-preparation-20261024/04-candidate/job.json'
HERE = Path(__file__).resolve().parent
HELPER = ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
HELPER_SHA = '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
PRIVATE_FIELDS = ('schema','actor_slots','origin_port','device','backend','cpu_threads','admission_s','wall_limit_s',
    'source_package','actor_source_sha256','loaded_rom_sha256','prior_ROM_identity_proof','lua','mame','rompath',
    'boot_seed','seed_runtime','proxy_ports','gpu_uuid','measurement_entry_timeout_s','startup_trace_frames',
    'whole_cohort_timeout_s','full_tail_predecessors','full_tail_scope_guard','historical_startup_acceptance_scope',
    'validated_CPU_prefix','main_sources','quota64_validation','quota64_source_pins')
ORDER = ('R1','C1','R2','C2')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def helpers():
    require(hashlib.sha256(HELPER.read_bytes()).hexdigest() == HELPER_SHA, 'Helper source changed')
    return load('_fullgame_round_helpers', HELPER)


def read(pin, h):
    path = h.checked(pin)
    require(path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o222 == 0
            and path.stat().st_size <= 64 << 20, 'Sealed bounded owned evidence required')
    return json.loads(path.read_bytes())


def install_pair(job, namespace):
    h = helpers()
    pair = read(job['quality_pair_precommit'], h)
    require(pair['schema'] == 'robotron-recovered-round-fullgame-pair-v1'
            and pair['ordered_legs'] == list(ORDER) and pair['minimum_complete_games_each'] == 64
            and job['confirmation_min_complete_games'] == 64
            and pair['all32_slots'] is pair['full_tails'] is pair['no_candidate_pooling'] is pair['no_scientific_retry'] is True
            and pair['each_mean_ratio_min'] == [105,100] and pair['each_median_preserved'] is True,
            'Exact64/all32/full-tail independent confirmation requirements required')
    policies = {}
    for role in ('reference','candidate'):
        selected = pair[role]
        require(selected['policy']['identity']['mode'] == '0o444', 'Immutable policy required')
        cpu = read(selected['CPU_report'], h)
        adoption = read(selected['original_CPU_readback'], h)
        proof = read(adoption['profile_proof'], h)
        require(cpu['status'] == adoption['status'] == 'PASS'
                and adoption['schema'] == 'robotron-frozen-profile-CPU-independent-adoption-v1'
                and adoption['actual_exit'] == 0
                and proof['schema'] == 'robotron-frozen-profile-CPU-compatibility-v1'
                and proof['package'] == job['source_package'] and proof['source_files_verified'] == 123
                and cpu['sha256'] == selected['policy']['sha256'] and cpu['clocks'] == selected['saved_clocks']
                and cpu['independent_profile_adoption'] == selected['original_CPU_readback']
                and adoption['all_Q_bytes_and_actions_match'] is adoption['original_scope_released'] is True
                and proof['checkpoint'] == selected['policy']
                and proof['inference_model_compatibility_passed'] is True and proof['CUDA_initialized'] is False,
                'Exact independently closed CPU/profile authority required')
        facts = read(proof['matched_canonical_CPU_facts'], h)
        require(facts['checkpoint_sha256'] == selected['policy']['sha256']
                and all(facts['checkpoint_metadata'][key] == value for key,value in selected['saved_clocks'].items()),
                'Pair saved clocks differ from actual strict actor facts')
        policies[role] = dict(sha256=selected['policy']['sha256'],clocks=selected['saved_clocks'])
    require(policies['reference']['sha256'] != policies['candidate']['sha256']
            and all(policies['candidate']['clocks'][key] > value for key,value in policies['reference']['clocks'].items()),
            'Distinct strictly later frozen candidate required')
    require(job['engineering_only'] is pair['engineering_only'], 'Pair/job engineering domain differs')
    namespace.update(PAIR_SHA=job['quality_pair_precommit']['sha256'], POLICIES=policies,
                     RUNTIME_SHA=job['runtime']['sha256'], SELECTED_RUNTIME=Path(job['runtime']['path']))
    return pair


def context(job, h):
    pair = install_pair(job, {})
    family = read(job['source_family_manifest'], h)
    protocol = read(job['main_health_protocol'], h)
    require(job['runtime'] == h.pin(HERE/'run_fullgame_rounds_v7.py')
            and family['leg_reviewer'] == h.pin(HERE/'review_fullgame_rounds_v7.py')
            and family['contract'] == h.pin(Path(__file__).resolve()), 'Actual fullgame adapter source identity differs')
    require(family['schema'] == 'robotron-recovered-round-fullgame-declared-launcher-family-v1'
            and family['runtime'] == job['runtime'] and family['current_main_binding'] == job['main_binding']
            and family['engineering_only'] is pair['engineering_only']
            and protocol == dict(schema='robotron-native-fullgame-round-main-health-declared-launcher-protocol-v1',
                case=job['main_binding'],raw_API_required=True,close_requires_final_sample=True,hot_max_gap_s=.5,initial_samples=100,raw_queue_protocol='pending-byte-digest-v2',volatile_live_tmpfs=True,source_bound_API_reconnect_projection=True,source_bound_natural_round_admission=True,source_bound_declared_launcher_census=True),
            'Exact source-bound fullgame round observer context required')
    expected = {'client': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-evaluator-adapters-original01-preparation/fullgame_round_observer_client_v8.py', 'worker': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-evaluator-adapters-original01-preparation/fullgame_round_observer_v6.py', 'health': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/round_health_transport_launcher_v1.py', 'health_base': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/round_main_health_launcher_v1.py', 'API_projection': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/api_reconnect_projection_v1.py', 'round_admission': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/round_admission_proof_v2.py', 'launcher_census': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/launcher_census_v1.py', 'durability': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/buffered_raw_writer_v2.py', 'control': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/volatile_live_control_v1.py', 'interpreter': '/usr/bin/python3.12'}
    expected = {name:Path(path) for name,path in expected.items()}
    require(set(family['main_observer']) == set(expected), 'Exact fullgame observer dependency set required')
    for name,path in expected.items():
        require(family['main_observer'][name] == h.pin(path), 'Selected fullgame observer source differs: '+name)
    require(family['main_observer_reviewer'] == h.pin(HERE/'review_fullgame_round_observer_v7.py')
            and family['main_health_finalizer']['sha256'] == '64c4001e3a46dd1f620bfa28b088f500bf8e9d3788a463d324cc408d7a42e6ee',
            'Actual independent observer reviewer/finalizer required')
    h.checked(family['main_health_finalizer'])
    template = read(family['private_parent_job'], h)
    require(family['private_parent_job']['path'] == str(TEMPLATE)
            and all(job[field] == template[field] for field in PRIVATE_FIELDS), 'Private ROM/selector/backend/clock/resource context changed')
    recovery = read(family['lease_recovery_authority'], h)
    require(recovery['restored_lease'] == job['lease'] and recovery['absent_pre_outage_lease'] == template['lease']
            and recovery['current_boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            and recovery['created_exclusively_without_replacing_existing_file'] is True
            and recovery['exclusive_lock_acquisition_and_release_verified'] is True, 'Exact recovered permanent coordinator required')
    h.checked(job['lease'])
    binding = read(job['main_binding'], h)
    require(binding['schema'] == 'robotron-round-main-health-case-v1' and len(binding['inputs']) == 247,
            'All243 recovered main inputs required')
    health = load('_fullgame_round_context_health', h.checked(family['main_observer']['health']))
    health.check_inputs(binding,full=True)
    baseline = read(binding['baseline_snapshot'],h)
    health.validate(binding,baseline)
    require(binding['experiment'] == job['training_experiment'] == baseline['api']['managed_experiment'],
            'Recovered main recipe differs from selected training context')
    wire = baseline['raw_API_wire'].encode()
    require(hashlib.sha256(wire).hexdigest() == baseline['api_wire_sha256'] and json.loads(wire) == baseline['api'],
            'Baseline raw API does not join the census')
    return dict(pair=pair,family=family,protocol=protocol,binding=binding,baseline=baseline)


def validate_launch(job, jp, ctx, h):
    pair,family = ctx['pair'],ctx['family']
    require(pair['engineering_only'] is False and family['native_launch_qualified'] is True,
            'Engineering context can never launch a scientific fullgame cohort')
    assessment = read(pair['screen_assessment'],h)
    require(assessment['schema'] == 'robotron-round-screen-study-independent-assessment-v1'
            and assessment['status'] == 'FOUR_ORIGINAL_SCREENING_LEGS_QUALIFIED'
            and assessment['historical_replay_only'] is False and assessment['screening_passed'] is True
            and assessment['policy_decision'] == 'REQUIRE_FRESH_COMPLETE_GAME_CONFIRMATION'
            and assessment['promotion'] is assessment['full_game_quality_qualified'] is False
            and assessment['source'] == h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/assess_screen_study.py')), 'Actual passing original screen required')
    screening = read(assessment['study_precommit'],h)
    require(all(screening['policies'][role]['checkpoint'] == pair[role]['policy']
                and screening['policies'][role]['expected_policy_clocks'] == pair[role]['saved_clocks']
                for role in ('reference','candidate')), 'Fullgame pair differs from the fixed screened policies')
    numeric = load('_fullgame_screen_numbers', h.checked(assessment['unchanged_numeric_source']))
    seals = {leg:read(assessment['original_closed_scopes'][leg]['score_seal'],h) for leg in ORDER}
    recomputed = numeric.compare_four(seals)
    require(recomputed == assessment['numerical_gates'] and recomputed['both_numeric_gates_passed'] is True,
            'Independent screening mean/median gates do not both pass')
    epoch = read(pair['protected_reference_epoch'],h)
    require(epoch['reference_policy'] == pair['reference']['policy'], 'Protected fixed-reference epoch differs')
    current = json.loads((ROOT/'logs/managed-learning-20261015/state.json').read_bytes())
    require(current['optimization_goal']['next_fixed_reference_epoch'] == pair['protected_reference_epoch'],
            'Protected reference was superseded before original fullgame launch')
    reviewer = load('_fullgame_main_domain_reviewer',h.checked(family['main_observer_reviewer']))
    proof = read(family['main_domain_hot_review'],h)
    checked = reviewer.verify(proof['lifecycle'],h)
    lifecycle = read(proof['lifecycle'],h);worker = read(lifecycle['worker_job'],h);proved = read(worker['case'],h)
    require(checked['original_sources'] == family['main_observer']
            and proved['inputs'] == ctx['binding']['inputs'] and proved['slot_eval'] == ctx['binding']['slot_eval'],
            'Fullgame readiness uses another source/role domain')
    static = ('pid','starttime_ticks','parent_pid','cgroup','command','environment','affinity','uids','executable')
    for role in ('trainer','fleet'):
        before,now = proved['owners'][role],ctx['binding']['owners'][role]
        require(before['unit'] == now['unit'] and before['invocation'] == now['invocation']
                and all(before['process'][key] == now['process'][key] for key in static), 'Main owner changed')
    for kind in ('optimizer','replay'):
        require(all(proved['exposure'][kind][key] == ctx['binding']['exposure'][kind][key]
                    for key in ('process_id','instance_monotonic_ns','epoch','epoch_reason')), 'Exposure lineage changed')
    guard_path = Path(job['prelaunch_CPU_closeout'])
    require(guard_path == Path(job['output']).parent/'fullgame-CPU-guards-original01/independent-closeout.json',
            'Exact fullgame per-job CPU guard path required')
    guard = read(h.pin(guard_path),h)
    require(guard['schema'] == 'robotron-fullgame-exact-job-CPU-closeout-v1' and guard['status'] == 'PASS'
            and guard['native_job'] == jp and guard['runtime'] == job['runtime']
            and guard['actual_exit'] == 0 and guard['original_scope_released'] is True
            and guard['actual_CPU_cores'] == 2 and guard['actual_memory_bytes'] == 4 << 30
            and guard['actual_runtime_limit_s'] == 180,
            'Actual exact-job CPU qualification/closure required before private ownership')
    return checked


def review_health(job, jp, result, owner, cfg, admission, started, ended, read_pin, h):
    ctx = context(job,h)
    family = ctx['family']
    verifier = load('_fullgame_closed_round_verifier',h.checked(family['main_observer_reviewer']))
    checked = verifier.verify(result['main_observer_lifecycle'],h)
    life = read_pin(result['main_observer_lifecycle']);worker = read_pin(life['worker_job'])
    parent = worker['parent']
    require(worker['native_job'] == jp and worker['native_runtime'] == job['runtime'] and worker['case'] == job['main_binding']
            and parent['pid'] == owner['pid'] and parent['birth'] == owner['starttime_ticks']
            and parent['unit'] == owner['unit'] and parent['invocation_id'] == owner['invocation_id']
            and parent['argv'] == cfg['argv'], 'Original native/observer scope join differs')
    closed = read_pin(result['main_health_report']);outcome = read_pin(life['outcome'])
    require(closed['success'] is True and closed['outcome'] == life['outcome'] and closed['job'] == life['worker_job']
            and closed['actual_status'] == result['main_samples'] == outcome['samples'], 'Native closed report/sample coverage differs')
    require(life['native_started_monotonic_s'] == result['native_started_monotonic_s']
            and life['native_deadline_monotonic_s'] == result['native_deadline_monotonic_s']
            == result['native_started_monotonic_s']+22200, 'Original native time bounds differ')
    receipt = read_pin(result['initial_main_readiness'])
    initial = outcome['initial'];loaded = h.pin(Path(job['output'])/'original-loaded-policy.json')
    loaded_unix = loaded['identity']['mtime_ns']/1e9
    require(receipt['schema'] == 'robotron-native-initial-main-readiness-v1'
            and receipt['original_job'] == jp and receipt['runtime'] == job['runtime']
            and receipt['main_health_protocol'] == job['main_health_protocol']
            and receipt['before_sidecar_Torch_policy_or_MAME'] is True
            and receipt['first_qualified_baseline_index'] == initial['index'] == 99
            and receipt['first_qualified_baseline_unix_s'] == initial['unix_s']
            and receipt['unaccepted_initial_samples'] == initial['unaccepted_samples'], 'Actual100-sample readiness receipt differs')
    require(result['initial_main_readiness']['path'] == str(Path(job['output'])/'original-initial-main-readiness.json')
            and result['initial_main_readiness']['identity']['mtime_ns'] <= loaded['identity']['mtime_ns'],
            'Original readiness receipt path or publication order differs')
    first = read_pin(outcome['samples'][0])['snapshot']
    last = read_pin(outcome['samples'][-1])['snapshot']
    require(0 <= initial['unix_s']-first['unix_s'] <= 30
            and initial['unix_s'] <= receipt['observed_unix_s'] <= loaded_unix <= admission['open_unix_ns']/1e9
            and started <= result['native_started_monotonic_s'] <= checked['first_accepted_monotonic_s'] <= checked['initial_qualified_monotonic_s']
            <= receipt['observed_monotonic_s'] < checked['last_accepted_monotonic_s'] <= ended
            and outcome['ended_monotonic_s'] <= result['native_deadline_monotonic_s']
            and 0 <= ended-checked['last_accepted_monotonic_s'] <= 30,
            'Fresh original main coverage/readiness/private-policy ordering differs')
    initial_exposure = first['api']['host_pipeline']['learning_exposure']
    final_exposure = last['api']['host_pipeline']['learning_exposure']
    require(final_exposure['optimizer']['total']['applied'] > initial_exposure['optimizer']['total']['applied']
            and final_exposure['replay']['accepted_total'] > initial_exposure['replay']['accepted_total'],
            'No admitted updates or fresh replay during the original cohort')
    return dict(checked=checked,receipt=result['initial_main_readiness'],
                health=dict(raw_report=result['main_health_report'],raw_samples=checked['accepted_samples'],
                    physical_censuses=checked['accepted_samples'],maximum_gap_s=.5,raw_API_and_TCP_replayed=True))


def validate_derivation(native_path, review_path):
    spec_path = HERE/'fullgame_round_adaptation_delta_v7.json'
    require(hashlib.sha256(spec_path.read_bytes()).hexdigest() == '9dd39130903a68614741b2295d225a87cf441825ddc0d404828ee2bb92e5fc63', 'Explicit adaptation delta changed')
    delta = json.loads(spec_path.read_bytes())
    originals = ((NATIVE,NATIVE_SHA,native_path,delta['native']), (REVIEW,REVIEW_SHA,review_path,delta['reviewer']))
    changed = []
    for original,digest,current,edits in originals:
        raw = original.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, 'Actual validated predecessor changed')
        expected = raw.decode()
        for edit in edits:
            require(expected.count(edit['old']) == 1, 'Delta no longer targets exactly one source block')
            expected = expected.replace(edit['old'],edit['new'])
        expected = expected.replace('__FULLGAME_CONTRACT_SHA__',hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        observed = Path(current).read_text()
        require(ast.dump(ast.parse(expected)) == ast.dump(ast.parse(observed)), 'Source differs beyond explicit pair/health adaptation')
        before = {n.name:ast.dump(n) for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        after = {n.name:ast.dump(n) for n in ast.parse(observed).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        changed.append(dict(unchanged=sorted(k for k,v in before.items() if after.get(k)==v),
                            changed_or_added=sorted(k for k,v in after.items() if before.get(k)!=v)))
    return dict(schema='robotron-fullgame-private-predicate-derivation-v1',status='PASS',
        exact_explicit_delta=True,private_count_life_game_tail_score_cleanup_and_timeout_predicates_preserved=True,
        native=changed[0],reviewer=changed[1],engineering_only=True,scientific_launch_qualified=False)
