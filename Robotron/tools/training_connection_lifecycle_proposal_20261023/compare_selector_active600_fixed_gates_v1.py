"""Pure engineering gates; caller must independently validate all four originals.

Uses exact integer median and frame/time arithmetic. No B pooling, causal FPS
claim, scientific quality decision, policy promotion or runtime actions.
"""


def median_twice(values):
    ordered = sorted(values)
    if not ordered or any(type(v) is not int or v < 0 for v in ordered):
        raise ValueError('Original nonnegative integer CPU costs required')
    middle = len(ordered) // 2
    return 2 * ordered[middle] if len(ordered) % 2 else ordered[middle - 1] + ordered[middle]


def compare(measurements, design):
    expected = ['01-A1-baseline', '02-B1-proposal', '03-B2-proposal', '04-A2-baseline']
    if set(measurements) != set(expected):
        raise ValueError('All four original measurements required')
    if [r['case'] for r in design['ordered_cases']] != expected:
        raise ValueError('Original fixed ABBA order differs')
    fixed = design['fixed_engineering_gates']
    if (fixed['B1'] != dict(minimum_selector_median_CPU_reduction=.10, minimum_accepted_frame_FPS_ratio=.95)
            or fixed['B2'] != fixed['B1'] or fixed['candidate_B_pooling_for_gate'] is not False):
        raise ValueError('Original separate B gates differ')
    for name in expected:
        record = measurements[name]
        if record['schema'] != 'robotron-active600-independent-selector-measurements-v1':
            raise ValueError('Original independently reviewed measurements required')
        if (type(record['active_duration_ns']) is not int or record['active_duration_ns'] < 600000000000
                or type(record['accepted_frames']) is not int or record['accepted_frames'] <= 0
                or record['quality_qualified'] is not False
                or record['exact_rates_and_stratum_recomputed_without_runtime_measurement_helper'] is not True
                or record['all32_original_slot_identities_and_counter_advances_verified'] is not True
                or record['all_active_statuses_advance_every_slot'] is not True):
            raise ValueError('Original active-window validity differs')
        stratum = record['fixed_stratum']
        if ((stratum['known_starts'], stratum['completed'], stratum['pending']) != (32, 0, 32)
                or stratum['count'] != len(stratum['thread_CPU_ns']) or stratum['count'] < 100
                or stratum['median_thread_CPU_ns_twice'] != median_twice(stratum['thread_CPU_ns'])):
            raise ValueError('Fixed original timing stratum differs')
    a1, a2 = (measurements[name] for name in (expected[0], expected[3]))
    reference_costs = [*a1['fixed_stratum']['thread_CPU_ns'], *a2['fixed_stratum']['thread_CPU_ns']]
    reference_cpu = median_twice(reference_costs)
    if reference_cpu <= 0:
        raise ValueError('Positive original baseline CPU median required')
    f1, f2 = a1['accepted_frames'], a2['accepted_frames']
    t1, t2 = a1['active_duration_ns'], a2['active_duration_ns']
    reference_fps = (f1 / t1 + f2 / t2) * 1e9 / 2
    gates = {}
    for key, name in [('B1', expected[1]), ('B2', expected[2])]:
        data = measurements[name]
        cpu = data['fixed_stratum']['median_thread_CPU_ns_twice']
        fb, tb = data['accepted_frames'], data['active_duration_ns']
        cpu_left, cpu_right = cpu * 10, reference_cpu * 9
        # FB/TB >= (19/40) * (FA1/TA1 + FA2/TA2); nanoseconds cancel.
        fps_left, fps_right = fb * 40 * t1 * t2, 19 * tb * (f1 * t2 + f2 * t1)
        gates[key] = dict(case=name, median_CPU_ns_twice=cpu,
            CPU_reduction_fraction=1 - cpu / reference_cpu,
            CPU_gate_left_integer=cpu_left, CPU_gate_right_integer=cpu_right,
            CPU_gate_passed=cpu_left <= cpu_right,
            accepted_frame_FPS=fb * 1e9 / tb,
            accepted_frame_FPS_ratio=(fb * 1e9 / tb) / reference_fps,
            FPS_gate_left_integer=fps_left, FPS_gate_right_integer=fps_right,
            FPS_gate_passed=fps_left >= fps_right,
            passed=cpu_left <= cpu_right and fps_left >= fps_right)
    return dict(schema='robotron-selector-active600-fixed-engineering-gates-v1',
        reference_A_cases=[expected[0], expected[3]], fixed_reference_call_count=len(reference_costs),
        fixed_reference_median_CPU_ns_twice=reference_cpu,
        fixed_reference_mean_accepted_frame_FPS=reference_fps,
        independent_B_gates=gates, both_independent_B_gates_passed=all(r['passed'] for r in gates.values()),
        candidate_B_pool_used=False, exact_integer_gate_arithmetic=True,
        requires_all_original_scope_and_raw_validity_closeouts_from_caller=True,
        evaluator_engineering_only=True, quality_qualified=False, policy_promoted=False,
        general_FPS_improvement_claim=False, useful_training_throughput_gain_verified=False,
        learning_speed_gain_verified=False)
