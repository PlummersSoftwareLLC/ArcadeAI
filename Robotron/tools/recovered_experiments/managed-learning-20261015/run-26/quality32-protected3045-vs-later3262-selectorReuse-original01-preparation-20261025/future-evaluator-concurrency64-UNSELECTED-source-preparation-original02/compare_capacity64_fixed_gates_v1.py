"""Exact original ABBA rate gates. Original scope/raw reviews remain mandatory."""
from fractions import Fraction
import json

ORDER = ('01-A1-control', '02-B1-capacity64', '03-B2-capacity64', '04-A2-control')
SPEC = dict(order=list(ORDER), private_accepted_frame_min_ratio=[6, 5],
            main_fleet_frame_min_ratio=[19, 20], main_admitted_row_min_ratio=[19, 20],
            fixed_A_reference='arithmetic_mean_of_original_A1_and_A2_rates',
            candidate_B_pooling=False, selector_CPU_cost_gate=False,
            require_all_original_scopes_and_raw_reviews=True)


def require(value, message):
    if not value:
        raise ValueError(message)


def fraction(record):
    require(type(record) is dict and set(record) == {'numerator', 'denominator'}
            and type(record['numerator']) is type(record['denominator']) is int
            and record['numerator'] > 0 and record['denominator'] > 0,
            'Positive exact original rate required')
    return Fraction(record['numerator'], record['denominator'])


def output(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def compare(measurements, spec):
    require(type(spec) is dict and spec == SPEC
            and json.dumps(spec, sort_keys=True) == json.dumps(SPEC, sort_keys=True),
            'Original fixed actor-count ABBA gates differ')
    require(type(measurements) is dict and set(measurements) == set(ORDER),
            'All four separate original ABBA measurements required')
    rates = {}
    identity = None
    for index, name in enumerate(ORDER):
        record = measurements[name]
        require(record['schema'] == 'robotron-evaluator-count-active600-independent-measurements-v1'
                and record['actor_count'] == (32 if index in (0, 3) else 64)
                and type(record['actor_count']) is int,
                'Original measurement schema/geometry differs')
        require(type(record['active_duration_ns']) is type(record['accepted_frames']) is int
                and record['active_duration_ns'] >= 600000000000 and record['accepted_frames'] > 0,
                'Original accepted-frame counter/duration differs')
        require(record['all_declared_original_slot_identities_and_counter_advances_verified'] is True
                and record['all_active_statuses_advance_every_slot'] is True
                and record['exact_rates_and_descriptive_costs_recomputed_without_runtime_measurement_helper'] is True
                and record['no_comparison_decision_until_all4_originals_closed'] is True
                and record['selector_CPU_cross_shape_comparison_used'] is False
                and record['quality_qualified'] is False,
                'Original active-window measurement validity differs')
        main = record['main_rates']
        require(main['schema'] == 'robotron-capacity64-main-own-clock-rates-v1'
                and main['held_batch_size'] == 4096 and type(main['held_batch_size']) is int
                and main['own_clocks_kept_separate'] is True
                and main['stable_epochs_and_monotonic_counters_verified'] is True
                and main['unavailable_outcomes_within_window'] == 0
                and type(main['unavailable_outcomes_within_window']) is int
                and main['quality_qualified'] is False,
                'Original main-admission own-clock validity differs')
        token = main['stable_optimizer_instance_epoch_pipeline_generation']
        require(type(token) is list and len(token) == 4
                and all(type(v) is int and v >= 0 for v in token)
                and token[0] == main['bound_main_process_id'] and token[0] > 0 and token[1] > 0,
                'Original main optimizer identity missing')
        identity = identity or token
        require(token == identity, 'Main optimizer/process/epoch/pipeline changed across ABBA')
        frames, rows, applied = main['fleet_frames'], main['admitted_rows'], main['optimizer_applied_admissions']
        require(all(type(v) is int and v > 0 for v in (frames, rows, applied))
                and rows == applied * 4096, 'Original main admission/fleet counters differ')
        fleet_time, row_time = fraction(main['fleet_elapsed_s']), fraction(main['optimizer_pipeline_elapsed_s'])
        require(fleet_time >= 590 and row_time >= 590 and abs(fleet_time - row_time) <= 3,
                'Original independent main rate durations differ')
        fleet_rate, row_rate = fraction(main['fleet_frame_rate']), fraction(main['admitted_optimizer_row_rate'])
        require(fleet_rate == frames / fleet_time and row_rate == rows / row_time,
                'Reported main rate differs from its own original counters/clock')
        rates[name] = dict(private=Fraction(record['accepted_frames'] * 10**9, record['active_duration_ns']),
                           main_fleet=fleet_rate, main_admitted_rows=row_rate)
    reference = {key:(rates[ORDER[0]][key] + rates[ORDER[3]][key]) / 2 for key in rates[ORDER[0]]}
    thresholds = dict(private=Fraction(6, 5), main_fleet=Fraction(19, 20), main_admitted_rows=Fraction(19, 20))
    gates = {}
    for name in ORDER[1:3]:
        checks = {}
        for key, threshold in thresholds.items():
            rate = rates[name][key]
            checks[key] = dict(actual_rate=output(rate), fixed_A_reference_rate=output(reference[key]),
                               threshold_ratio=output(threshold), actual_ratio=output(rate / reference[key]),
                               passed=rate >= threshold * reference[key])
        gates[name] = dict(checks=checks, passed=all(v['passed'] for v in checks.values()))
    return dict(schema='robotron-capacity64-exact-fixed-ABBA-rate-gates-v1',
                fixed_A_reference={key:output(rate) for key, rate in reference.items()}, independent_B_gates=gates,
                both_independent_B_gates_passed=all(v['passed'] for v in gates.values()),
                exact_fraction_arithmetic=True, candidate_B_pool_used=False, selector_CPU_cross_shape_gate_used=False,
                all_original_native_observer_reviewer_closure_and_raw_startup_main_health_reviews_required=True,
                native_readiness_or_adoption_established_by_math_alone=False, quality_qualified=False,
                full_game_wall_time_gain_verified=False, useful_training_throughput_gain_verified=False,
                learning_speed_gain_verified=False)
