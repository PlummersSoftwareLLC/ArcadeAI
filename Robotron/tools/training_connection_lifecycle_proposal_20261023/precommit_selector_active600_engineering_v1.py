"""Fix engineering order and gates before deriving or launching native cases."""
import hashlib
import importlib.util
import json
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
N = R / 'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025'
D = N / 'selector-active600-counterbalanced-engineering-original01'


def main():
    path = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    spec = importlib.util.spec_from_file_location('_design_h', path)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    goal = json.loads((G / 'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    family = json.loads((N / 'prepared-source-family-manifest-bounded-display-v2.json').read_bytes())
    prior = R / 'native32-quota64-API-epoch-reference-load600-original01-preparation-20261024'
    oldjob = json.loads((prior / 'job.json').read_bytes())
    oldfamily = json.loads(Path(oldjob['source_family_manifest']['path']).read_bytes())
    baseline = R / 'future-fixed-slot64-full-game-protocol-original01-preparation-20261024'
    baseview = h.pin(baseline / 'fixed_slot_cohort_view_v1.py')
    basedrain = h.pin(baseline / 'fixed_slot_cohort_drain_v1.py')
    assert goal['current_fixed_reference_policy']['sha256'] == 'b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
    protocol = json.loads(Path(oldjob['main_health_protocol']['path']).read_bytes())
    value = dict(
        schema='robotron-selector-active600-counterbalanced-engineering-precommit-v1',
        created_unix_s=time.time(),
        state='DESIGN_FIXED_BEFORE_ANY_ORIGINAL_RUN_SOURCE_BINDING_AND_GUARDS_REQUIRED',
        engineering_only=True, scientific_case=False, quality_qualified=False,
        original_attempts_per_case=1, no_retry=True, no_rescue_or_replacement_run=True,
        reference_policy=goal['current_fixed_reference_policy'],
        reference_saved_clocks=dict(learner_frame_count=3045860554, training_steps=11995683,
                                   optimized_samples=47558522880, frame_count=5926701223),
        reference_CPU_report=json.loads((N / 'campaign-inputs-and-gates-precommit.json').read_bytes())['reference']['CPU_report'],
        policy_used_in_all_four_cases='Identical protected3045 bytes; later3262 candidate is not used in engineering',
        ordered_cases=[dict(case='01-A1-baseline', implementation='A'),
                       dict(case='02-B1-proposal', implementation='B'),
                       dict(case='03-B2-proposal', implementation='B'),
                       dict(case='04-A2-baseline', implementation='A')],
        implementations=dict(A=dict(view=baseview, drain=basedrain),
                             B=dict(view=family['quota64_source_pins']['view'], drain=family['quota64_source_pins']['drain'])),
        common_bridge=family['quota64_source_pins']['bridge'],
        source_lineage=dict(prior_original_native_runtime=oldjob['runtime'],
            prior_original_native_job=h.pin(prior / 'job.json'),
            prior_closed_native_observer_and_raw_evidence=h.pin(prior / 'independent-original-quota64-reference600-all-scopes-and-raw-closeout.json'),
            new_actual_journal_alias_guards=family['actual_writer_alias_guards'],
            new_actual_source_and_initializer_guards=h.pin(N / 'actual-initializer-source-guards-CPU-original01/independent-original-family-guards-and-CPU-closeout.json'),
            bounded_display_guard_closeout=h.pin(N / 'display-bounded-projection-guards-CPU-original01/independent-original-display-guards-and-CPU-closeout.json')),
        common_runtime=dict(source_package=oldjob['source_package'], boot_seed=oldjob['boot_seed'],
            seed_runtime=oldjob['seed_runtime'], gpu_uuid=oldjob['gpu_uuid'], backend='inductor', device='cuda',
            cpu_threads=2, inference_batch_max_size=16, actor_slots=list(range(4096, 4128)),
            origin_port=19998, proxy_ports={str(s): 20000 + s - 4096 for s in range(4096, 4128)},
            lease=oldjob['lease'], main_binding=goal['current_main_binding'], main_observer=oldfamily['main_observer'],
            main_health_sources=protocol['health_job']['sources'],
            native_resources=['CPUQuota=1200%', 'MemoryMax=16G', 'MemorySwapMax=0', 'RuntimeMaxSec=22260',
                              'TasksMax=512', 'TimeoutStopSec=30', 'KillMode=mixed', 'SendSIGKILL=no'],
            observer_resources=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0', 'RuntimeMaxSec=22260',
                                'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'],
            same_instrumentation_for_A_and_B=True),
        active_window=dict(duration_s=600, maximum_time_to_active_anchor_s=300,
            internal_native_wall_limit_s=960, outer_owned_scope_cap_s=22260,
            start_predicate='All32 original startup1200 prefixes verified, original actor births live, fixed admission established and all32 original boundary acknowledgements ready; anchor per-slot accepted ledger counters with monotonic read brackets',
            end_predicate='First loop observation at or after600s from active anchor; capture the same all32 ledger counters and original slot births before intentional stop',
            intentional_stop=True, intentionally_unfinished_games_quarantined_from_quality=True,
            native_startup_and_compilation_outside_measured_window=True),
        raw_measurements=dict(
            selector_calls='Every actual cohort_status call: monotonic start/end ns, thread CPU ns, thread identity, known-start/completed/pending counts and exceptional status. Same wrapper, maximum131072 records per case; overflow is failure, no sampling/drop.',
            fixed_selector_stratum='Successful calls entirely inside active anchor/end with exactly32 known starts, zero completed and32 pending; at least100 such calls required in EACH case.',
            accepted_frame_throughput='Per-slot ledger accepted increments divided by active-window monotonic read-bracket midpoint elapsed. Preserve endpoint brackets and every native5s status. These are accepted emulator frames, not training samples.',
            slot_liveness='All32 original actor births and accepted counter increases across each successive retained active-window status; no rejected ledger frames.',
            main_health='Original dedicated main192/197 full sample stream, independent replay, and terminal resources/releases required.'),
        fixed_engineering_gates=dict(all_four_original_cases_required=True,
            all_original_startup_ROM_wire_ledger_main_health_and_owned_closeout_checks_required=True,
            all32_accepted_frames_advance=True, no_rejected_frames=True,
            all_original_input_pins_unchanged=True, private_GPU_ports_and_lease_released_between_cases=True,
            reference_A_CPU='Fixed median of ALL qualifying call CPU ns from A1+A2; neither A case discarded.',
            reference_A_FPS='Arithmetic mean of two valid A-case aggregate accepted-frame rates; neither A case discarded.',
            B1=dict(minimum_selector_median_CPU_reduction=.10, minimum_accepted_frame_FPS_ratio=.95),
            B2=dict(minimum_selector_median_CPU_reduction=.10, minimum_accepted_frame_FPS_ratio=.95),
            candidate_B_pooling_for_gate=False, all_tail_and_startup_predicates_unchanged=True),
        interpretation=dict(
            pass_meaning='Supports using the equivalent selector in the isolated evaluator for the next full-game study; gross FPS is an engineering regression check.',
            fail_meaning='Preserve original evidence and stop this comparison; no reruns or pooled B rescue.',
            limits=['No quality qualification from intentionally stopped games',
                    'No main useful training-throughput or learning-speed gain can be established',
                    'Four counterbalanced executions and correlated calls do not support IID significance or general FPS-gain claims',
                    'Same-shape calls are not identical journals; prior frozen-data CPU experiment supplies exact-input equivalence/timing evidence',
                    'Scientific full-game admission/timeout/quality gates remain unchanged']),
        launch_prerequisites=[
            'Bind exact common instrumentation, active-window/native source, per-case sources/jobs/configs and source families before any original launch',
            'Run bounded actual source-family/instrumentation guards and independently verify original CPU closures',
            'Validate actual engineering preparer/native initializer consumes the exact protocol before worker/Torch/MAME work',
            'Fresh actual main192/197, privateGPU0 idle, permanent lease and all33 private ports available before each case',
            'All previous original native/observer/reviewer scopes actually closed before proceeding'],
        current_precommit_does_not_authorize_skipping_prerequisites=True,
        main_runtime_changed=False, no_main_recipe_or_model_restore=True)
    for pin in [goal['current_fixed_reference_policy'], baseview, basedrain,
                family['quota64_source_pins']['view'], family['quota64_source_pins']['drain'], oldjob['runtime']]:
        h.checked(pin)
    D.mkdir(mode=0o700)
    pin = h.put(D / 'controlled-engineering-design-precommit.json', value)
    print(json.dumps(dict(precommit=pin, order=[item['case'] for item in value['ordered_cases']], active_s=600)))


if __name__ == '__main__':
    main()
