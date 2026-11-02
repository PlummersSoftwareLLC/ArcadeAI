"""Prepare four source-bound frozen-policy screening jobs; inert by default.

Production selection requires the completed prospective capture and independent
CPU/profile receipts. Engineering fixtures can never grant launch authority.
This tool launches no evaluation or emulator workloads and never accesses GPUs or alters learner state.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE = ROOT/'logs/managed-learning-20261015/run-26'
HERE = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation')
LOCAL = Path(__file__).resolve().parent
PREVIOUS = BASE/'deadline-score32-fixed-fleet-admission-original03-preparation-20261026/fixed-RCRC-deadline32-study-original03'
CAPTURE = BASE/'post-natural-turnover-durable-next-candidate-20261029-original03'
CAPTURE_PLAN_SHA = '43ace243055948eba395f97ba96faef339997c5d94cec6b50aea3104dbe9ae68'
PROTECTED_SHA = 'b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
LEGS = ('R1', 'C1', 'R2', 'C2')


def require(value, message):
    if not value:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read(value, h):
    path = h.checked(value)
    require(value['identity']['mode'] == '0o444' and value['identity']['uid'] == os.getuid(),
            'Selection/context evidence must be immutable and owned')
    return json.loads(path.read_bytes())


def subset_pin(value, h):
    actual = h.pin(value['path'])
    require(all(actual[key] == expected for key, expected in value.items()), 'Attested bytes/identity changed')
    require(actual['identity']['mode'] == '0o444', 'Selected artifact is not immutable')
    return actual


def profile_check(proof_pin, checkpoint, package, clocks, h):
    adopted = read(proof_pin, h)
    require(adopted['schema'] == 'robotron-frozen-profile-CPU-independent-adoption-v1'
            and adopted['status'] == 'PASS' and adopted['actual_exit'] == 0
            and adopted['all_Q_bytes_and_actions_match'] is True
            and adopted['original_scope_released'] is True, 'Independent actual profile scope closure required')
    proof = read(adopted['profile_proof'], h)
    require(proof['schema'] == 'robotron-frozen-profile-CPU-compatibility-v1'
            and proof['source_files_verified'] == 123 and proof['inference_model_compatibility_passed'] is True
            and proof['exact_synthetic_CPU_Q_summaries_match'] is True
            and proof['CUDA_initialized'] is False, 'Strict frozen-profile CPU compatibility required')
    require(subset_pin(proof['checkpoint'], h) == checkpoint and proof['package'] == package,
            'Profile proof does not match the selected policy/package')
    facts = read(proof['matched_canonical_CPU_facts'], h)
    parity = facts['cpu_action_and_q_internal_parity']
    require(facts['checkpoint_sha256'] == checkpoint['sha256'] and facts['cuda_initialized'] is False
            and facts['inference_error'] is None and parity['q_allclose'] is True
            and parity['greedy_agreement'] == parity['locked_fire_agreement'] == 1.0,
            'Canonical inference facts differ')
    require(all(facts['checkpoint_metadata'][key] == value for key, value in clocks.items()),
            'Selected saved clocks do not match strict actor metadata')
    return proof


def completed_capture(h):
    result_pin = h.pin(CAPTURE/'result.json')
    result = read(result_pin, h)
    plan_pin = h.pin(CAPTURE/'window-plan.json')
    require(plan_pin['sha256'] == CAPTURE_PLAN_SHA, 'Exact new independent original03 capture plan required')
    plan = read(plan_pin, h)
    require(result['state'] == 'captured_CPU_verified' and result['owner'] == plan['owner']
            and result['original_DQN_window_unchanged'] is True, 'Only the completed selected prospective capture is eligible')
    require(plan['thresholds'] == dict(applied_updates=5000, replay_inserts=1_000_000, elapsed_s=3600)
            and all(result['added'][key] >= value for key, value in plan['thresholds'].items()),
            'All three prospective thresholds must be met without borrowing old counts')
    require(sum(result['added']['by_source'].values()) == result['added']['replay_inserts'], 'Exposure attribution differs')
    for value in plan['inputs']:
        subset = h.pin(value['path'])
        require(all(subset[key] == expected for key, expected in value.items()), 'Capture source/recipe changed')
    require(result['endpoint']['path'] == str(CAPTURE/'endpoint.pt'), 'Actual new original03 endpoint path required')
    checkpoint = subset_pin(result['endpoint'], h)
    require(checkpoint['sha256'] not in ('862fb4cde4ecb146b5b23a83b77ccbf1675a980bc310f6c2a6a8806d87b7c81e',
            'e078b0da4ce4e25146fab7484f8489f590e1086370746cb392afcd7f5f8adef5',
            'a6e17a3c6cd8a9b6cb5479e6c6cbd1a284c1cd880372d0d02441680bc708e502',
            '444a14287789b26e3d84564cf4a9e49518d82d91d6a3ed82ca09526ef89c8523',
            '684b8506cf404dc23ef49a0081703e75e1b14d47aeab7921f7f54e196b5505fa'),
            'Failed original study cannot be retried with its selected policy')
    authority = subset_pin(result['CPU_verification'], h)
    cpu = read(authority, h)
    require(subset_pin(cpu['checkpoint'], h) == checkpoint
            and cpu['online_target_shapes_and_finiteness_verified'] is True
            and cpu['priority_phase_valid'] is True and cpu['priority_phase']['metric'] == 'ce'
            and cpu['optimizer_lrs'] == [3.125e-6] and cpu['Adam_parameters'] == 81
            and cpu['Adam_step_min'] == cpu['Adam_step_max'] > plan['entry_Adam_step']
            and cpu['CUDA_initialized'] is False, 'Actual CPU checkpoint verification differs')
    threshold = read(h.pin(CAPTURE/'first-threshold.raw.json'), h)
    require(all(cpu['clocks'][key] >= threshold[key] for key in cpu['clocks']), 'Captured state predates the threshold')
    owner = read(h.pin(CAPTURE/'CPU-original-owner.json'), h)
    terminal = read(h.pin(CAPTURE/'CPU-original-terminal.json'), h)
    release = read(h.pin(CAPTURE/'CPU-owned-release.json'), h)
    expected = dict(InvocationID=owner['invocation_id'], ExecMainPID=str(owner['pid']),
        MainPID='0', ExecMainCode='1', ExecMainStatus='0', NRestarts='0', CPUQuotaPerSecUSec='2s',
        MemoryMax=str(4 << 30), MemorySwapMax='0', TasksMax='128', RuntimeMaxUSec='3min')
    require(all(terminal[key] == value for key, value in expected.items())
            and release['terminal'] == terminal and release['original'] == owner['actual_properties']
            and release['after_release']['MainPID'] == '0'
            and release['after_release']['ActiveState'] == 'inactive'
            and not Path('/sys/fs/cgroup'+owner['actual_properties']['ControlGroup']).exists(),
            'Actual original CPU closure/release differs')
    stat_path = Path('/proc', str(owner['pid']), 'stat')
    require(not stat_path.exists() or int(stat_path.read_text().rsplit(')', 1)[1].split()[19]) != owner['birth'],
            'Original CPU verification birth remains')
    return dict(checkpoint=checkpoint, expected_policy_clocks=cpu['clocks'],
        training_experiment='CE4096-LR125-survival32M-original01-20261023',
        immutable_numerical_or_protection_authority=authority), [result_pin, plan_pin, authority,
        h.pin(CAPTURE/'CPU-original-owner.json'), h.pin(CAPTURE/'CPU-original-terminal.json'),
        h.pin(CAPTURE/'CPU-owned-release.json')]


def capture_binding(template_pin, h):
    template = read(template_pin, h)
    health = load('_prepare_round_health', Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/retired-api-row-projection-original01-preparation/capture-bracket-revision02/round_health_transport_retired_API_v4.py'))
    collector = load('_prepare_round_raw_API', Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/future-two-second-main-proof-contract-original01-preparation/source-family-original01/round_observer_proof2s_v1.py'))
    deadline = time.monotonic()+30
    while True:
        launcher = load('_prepare_exact_declared_launchers',Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/launcher_census_v1.py'))
        case = launcher.prepare_case(template)
        case['source_guard'] = '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/retired-api-row-projection-original01-preparation/capture-bracket-revision02/round_main_health_retired_API_v4.py'
        case['initial_round'] = json.loads((Path(case['round_root'])/'status.json').read_bytes())['round']
        try:
            baseline = collector.collect(health, case)
            health.validate(case, baseline)
            health.check_inputs(case, full=True)
            return case, baseline
        except (OSError, ValueError):
            require(time.monotonic() < deadline, 'No coherent original main context; no preparation retry')
            time.sleep(.2)


def prior_identities(h):
    root = BASE/'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025'
    cold = root/'evaluator-count-active600-counterbalanced-engineering-original06/future-startup-slot64-chain-correction-original01'
    clock = BASE/'deadline-score60min-protocol-original01-preparation-20261026'
    lazy = BASE/'deadline-score32-lazy-carry-correction-original02-preparation-20261026'
    paths = set(root.glob('*/job.json')) | set(cold.glob('*/job.json')) | set(PREVIOUS.glob('*/job.json'))
    for parent in (clock/'fixed-RCRC-deadline32-study-original01', clock/'guard-path-correction-original01',
                   lazy/'fixed-RCRC-deadline32-study-original02'):
        paths.update(parent.glob('*/job.json'))
    for parent in root.glob('*engineering-original*'):
        paths.update(parent.glob('*/job.json'))
    paths.update((BASE/'post-recovery-evaluation-isolation-original01-20261027').rglob('job.json'))
    identities, records = set(), []
    for path in sorted(paths):
        value = json.loads(path.read_bytes())
        if not all(isinstance(value.get(key), dict) for key in ('sessions', 'connections')):
            continue
        records.append(h.pin(path))
        for key in ('sessions', 'connections'):
            identities.update(token for token in value[key].values()
                              if isinstance(token, str) and re.fullmatch('[0-9a-f]{32}', token))
    return identities, records


def prepare(output, reference_profile, candidate_profile, *, main_domain_proof, lease_recovery, engineering=False):
    h = load('_round_study_helpers', ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    old_ref = read(h.pin(PREVIOUS/'R1/job.json'), h)
    old_candidate = read(h.pin(PREVIOUS/'C2/job.json'), h)
    state = json.loads((ROOT/'logs/managed-learning-20261015/state.json').read_bytes())
    goal = state['optimization_goal']
    require(not state.get('active_quality_job') and not goal['scientific_job_running']
            and not goal.get('performance_job_running'), 'A different scientific/performance job is active')
    reference = dict(checkpoint=old_ref['checkpoint'], expected_policy_clocks=old_ref['expected_policy_clocks'],
        training_experiment=old_ref['training_experiment'], immutable_numerical_or_protection_authority=old_ref['policy_authority'])
    require(reference['checkpoint']['sha256'] == PROTECTED_SHA, 'Protected fixed reference differs')
    evidence = []
    if engineering:
        authority = h.pin(BASE/'post-recovery-learning-20261027-original01/entry-CPU-verification.json')
        facts = read(authority, h)
        candidate = dict(checkpoint=subset_pin(facts['checkpoint'], h), expected_policy_clocks=facts['clocks'],
            training_experiment=reference['training_experiment'], immutable_numerical_or_protection_authority=authority)
    else:
        candidate, evidence = completed_capture(h)
    require(candidate['checkpoint']['sha256'] not in (PROTECTED_SHA, old_candidate['checkpoint']['sha256'])
            and all(candidate['expected_policy_clocks'][key] > value
                    for key, value in old_candidate['expected_policy_clocks'].items()),
            'Candidate must be distinct and later than the last screened policy in every saved clock')
    profile_check(reference_profile, reference['checkpoint'], old_ref['source_package'], reference['expected_policy_clocks'], h)
    profile_check(candidate_profile, candidate['checkpoint'], old_ref['source_package'], candidate['expected_policy_clocks'], h)
    restored = read(lease_recovery, h)
    require(restored['status'] == 'RESTORED_NEW_BOOT_COORDINATOR', 'Explicit restored coordinator required')
    main_proof = main_domain_proof
    read(main_proof, h)
    template_pin = h.pin(BASE/'post-recovery-learning-20261027-original03/clean-main-case.json')
    case, baseline = capture_binding(template_pin, h)
    require(baseline['api']['managed_experiment'] == reference['training_experiment'], 'Current recovered recipe differs')
    output = Path(output).absolute()
    require(output == output.resolve() and output.parent.is_dir() and not output.exists(), 'Exclusive fresh study directory required')
    output.mkdir(mode=0o700)
    baseline_pin = h.put(output/'main-baseline.raw.json', baseline)
    case.update(baseline_snapshot=baseline_pin, experiment=reference['training_experiment'])
    binding = h.put(output/'main-binding.json', case)
    runtime = h.pin(LOCAL/'run_deadline32_rounds_v11.py')
    reviewer = h.pin(LOCAL/'review_deadline32_rounds_v11.py')
    controller = h.pin(LOCAL/'control_deadline32_rounds_v11.py')
    contract_pin = h.pin(LOCAL/'deadline_round_contract_v11.py')
    native = load('_prepare_actual_round_native', Path(runtime['path']))
    control = load('_prepare_actual_round_controller', Path(controller['path']))
    contract = native.round_contract()
    protocol = h.put(output/'main-health-protocol.json', dict(schema='robotron-native-round-main-health-declared-launcher-proof2s-protocol-v1',
        case=binding, raw_API_required=True, close_requires_final_sample=True, hot_max_gap_s=2.0, initial_samples=100,
        raw_queue_protocol='pending-byte-digest-v2', volatile_live_tmpfs=True,source_bound_API_reconnect_projection=True,source_bound_natural_round_admission=True,source_bound_declared_launcher_census=True))
    observer = dict(client=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/future-two-second-main-proof-contract-original01-preparation/source-family-original01/round_observer_client_proof2s_v1.py')), worker=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/future-two-second-main-proof-contract-original01-preparation/source-family-original01/round_observer_proof2s_v1.py')),
        health=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/retired-api-row-projection-original01-preparation/capture-bracket-revision02/round_health_transport_retired_API_v4.py')),health_base=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/retired-api-row-projection-original01-preparation/capture-bracket-revision02/round_main_health_retired_API_v4.py')),API_projection=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/retired-api-row-projection-original01-preparation/capture-bracket-revision02/api_cached_projections_v3.py')),round_admission=h.pin(HERE/'round_admission_proof_v2.py'),launcher_census=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/launcher_census_v1.py')), durability=h.pin(HERE/'buffered_raw_writer_v2.py'), control=h.pin(HERE/'volatile_live_control_v1.py'), interpreter=h.pin(Path('/usr/bin/python3').resolve()))
    old_family = read(old_candidate['source_family_manifest'], h)
    study = h.put(output/'study-precommit.json', dict(schema='robotron-deadline32-fixed-fresh-RCRC-study-v1',
        created_unix_s=time.time(), ordered_legs=list(LEGS), horizon_ns=old_ref['horizon_ns'],
        actor_slots=old_ref['actor_slots'], policies=dict(reference=reference, candidate=candidate),
        n_scored_per_leg=32, n_reference_pooled=64, first_games_per_slot=1, no_retry=True,
        each_candidate_mean_ratio_min=[105,100], each_candidate_median_preserved=True,
        full_game_quality_qualified=False, improvement_qualified=False, promotion=False,
        engineering_only=engineering, prospective_capture_evidence=evidence,
        strict_reference_profile=reference_profile, strict_candidate_profile=candidate_profile,
        separate_fullgame_confirmation_required=dict(candidate_legs=2, minimum_games_each=64,
            all_slots=32, full_tail=True, mean_ratio_min=[105,100], median_preserved=True)))
    seen, prior = prior_identities(h)
    fresh, records = set(), []
    for leg in LEGS:
        directory = output/leg
        directory.mkdir(mode=0o700)
        role = 'reference' if leg.startswith('R') else 'candidate'
        selected = reference if role == 'reference' else candidate
        namespace = 'deadline32-proof2s-'+study['sha256'][:16]+'-'+leg.lower()+'-original01-20261029'
        native_unit = 'robotron-'+namespace+'.service'
        job = copy.deepcopy(old_ref if role == 'reference' else old_candidate)
        job.update(unit=native_unit, lease=restored['restored_lease'], runtime=runtime, output=str(directory/'deadline-output-original01'), leg=leg,
            created_unix_s=time.time(), checkpoint=selected['checkpoint'], expected_policy_clocks=selected['expected_policy_clocks'],
            policy_authority=selected['immutable_numerical_or_protection_authority'], study_precommit=study,
            observer_sources=observer, main_binding=binding, main_health_protocol=protocol,
            prelaunch_family_guard_closeout=str(directory/'source-family-guards-CPU-original01/independent-deadline32-family-guards-and-CPU-closeout.json'),
            label=namespace,
            measurement_label=namespace)
        for key in ('sessions', 'connections'):
            job[key] = {}
            for slot in job['actor_slots']:
                token = secrets.token_hex(16)
                while token == '0'*32 or token in fresh or token in seen:
                    token = secrets.token_hex(16)
                fresh.add(token)
                job[key][str(slot)] = token
        family = dict(schema='robotron-deadline32-declared-launcher-proof2s-source-family-v1', runtime=runtime,
            reviewer=reviewer, main_observer=observer, round_observer_reviewer=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/future-two-second-main-proof-contract-original01-preparation/source-family-original01/review_round_observer_proof2s_v1.py')),
            main_health_finalizer=old_family['main_health_finalizer'], deadline_components=job['components'],
            private_parent_job=h.pin(PREVIOUS/'C2/job.json'), current_main_binding=binding,
            lease_recovery_authority=lease_recovery, main_domain_hot_review=main_proof, native_launch_qualified=not engineering,
            engineering_only=engineering, source_preparation_only=True, native_launch_selected=False,
            required_additional_authority='Exact original per-job CPU guard closure is separately mandatory in native.run before ownership')
        family_pin = h.put(directory/'source-family.json', family)
        job['source_family_manifest'] = family_pin
        inputs = [*job['inputs'], runtime, reviewer, controller, contract_pin, study, protocol, binding,
            baseline_pin, family_pin, main_proof, lease_recovery, restored['restored_lease'], reference_profile, candidate_profile,
            h.pin(Path(__file__).resolve()), h.pin(HERE/'round_main_health_v7.py'), h.pin(HERE/'round_health_transport_v4.py'), *observer.values(), family['round_observer_reviewer'],
            family['main_health_finalizer'], family['private_parent_job'], selected['checkpoint'],
            selected['immutable_numerical_or_protection_authority'], *evidence, *prior]
        job['inputs'] = list({value['path']:value for value in inputs}.values())
        context = native.validate_completed_context(job, h)
        require(len(context['package_pins']) == 123 and len(context['main_binding']['inputs']) == 247,
                'Actual prepared private/main source inventories differ')
        if not engineering:
            contract.validate_launch(job, context, h)
        jp = h.put(directory/'job.json', job)
        config = dict(unit=native_unit,
            output=str(directory/'execution-original01'), argv=[str(ROOT.parent/'.venv-gb300/bin/python'),
                '-Xgil=0','-I','-B',runtime['path'],'--execute','--job',jp['path'],
                '--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']],
            properties=['CPUQuota=1200%','MemoryMax=24G','MemorySwapMax=0','RuntimeMaxSec=4260',
                'TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
            observation_s=4320, pins=[control.pin(value['path']) for value in [jp,*job['inputs']]])
        cp = h.put(directory/'controller-config-NOT-QUALIFIED.json', config)
        require(control.checked_config(cp['path']) == config, 'Actual controller interface differs')
        records.append(dict(leg=leg, role=role, native_job=jp, runtime=runtime, native_controller=controller,
            unqualified_controller_config=cp, source_family=family_pin, main_health_protocol=protocol,
            prelaunch_CPU_closeout=job['prelaunch_family_guard_closeout'], native_launch_ready=False))
    require(len(fresh) == 256 and not fresh & seen, 'Fresh transport identity coverage differs')
    return h.put(output/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json', dict(
        schema='robotron-deadline32-four-original-leg-preparation-v1', study_precommit=study,
        ordered_legs=list(LEGS), cases=records, source_preparer=h.pin(Path(__file__).resolve()), reviewer=reviewer,
        all256_transport_IDs_fresh_and_disjoint=True, prior_jobs=prior, engineering_only=engineering,
        main_domain_slots=192, main_current_active=baseline['observed_counts']['active'],
        main_current_completed=baseline['observed_counts']['completed'], exact_job_CPU_closed=False,
        native_launch_ready=False, any_scientific_payload_launched=False, quality_qualified=False,
        remaining='Exact serialized four-job CPU guards and independent scope closure; final hardware/port/lease/unit readiness; one original R1 launch.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--lease-recovery', type=Path, required=True)
    parser.add_argument('--main-domain-proof', type=Path, required=True)
    parser.add_argument('--engineering-entry', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--reference-profile', type=Path)
    parser.add_argument('--candidate-profile', type=Path)
    args = parser.parse_args()
    if args.prepare:
        h = load('_round_preparer_cli_helpers', ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
        result = prepare(args.output, h.pin(args.reference_profile.resolve()), h.pin(args.candidate_profile.resolve()),
                         main_domain_proof=h.pin(args.main_domain_proof.resolve()), lease_recovery=h.pin(args.lease_recovery.resolve()), engineering=args.engineering_entry)
        print(json.dumps(result), flush=True)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
