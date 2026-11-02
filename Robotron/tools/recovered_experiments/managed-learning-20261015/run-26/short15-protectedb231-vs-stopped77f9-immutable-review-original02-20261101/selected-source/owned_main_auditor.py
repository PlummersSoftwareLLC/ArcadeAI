"""Exact qualified physical Main replay kernel, no scientific-case acceptance.
"""
import math
import importlib.util
import sys

def require(value,message):
    if not value:raise ValueError(message)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def audit_main(job,result,read,h):
    source = load('_eng_review_actual_v6_health', h.checked(job['current_v6_health_source']))
    owned = load('_eng_review_owned_TRAIN_overlap', h.checked(job['owned_TRAIN_overlap_source']))
    expected_fleet = job['current_fleet']
    membership = read(expected_fleet['original_membership'])
    roles = read(expected_fleet['rolemap'])['slot_eval']
    original_supervisor = load('_eng_review_original_v6_cleanup', h.checked(expected_fleet['supervisor']['source']))
    support = load('_eng_review_original_bounded_Main', h.checked(job['screen_support']))
    main_report = read(result['main_health_report'])
    require(main_report['samples'] == result['main_samples'], 'Original Main streams differ')
    accepted = 0
    pending = 0
    previous = None
    previous_begin = None
    max_gap = 0
    bindings = {}
    binding_cache = {}
    pending_begin = None
    for sample in result['main_samples']:
        raw = read(sample['physical_v6'])
        before = raw['fleet_before']
        connections = raw['connections_before']
        now = max(before['updated_unix_s'], connections['observed_unix_s'])
        require(raw['schema'] == 'robotron-current-v6-owned-overlap-observation-v2', 'Exact owned-overlap raw schema required')
        before_metadata = owned.replay_pending(before, connections, expected_fleet, membership, roles, raw['owned_TRAIN_metadata_before'], now=now, strict_validator=source.validate_metadata, read_pin=read)
        after_metadata = owned.replay_pending(raw['fleet_after'], raw['connections_after'], expected_fleet, membership, roles, raw['owned_TRAIN_metadata_after'], now=max(raw['fleet_after']['updated_unix_s'], raw['connections_after']['observed_unix_s']), strict_validator=source.validate_metadata, read_pin=read)
        before_pending = before_metadata['pending_slots']
        after_pending = after_metadata['pending_slots']
        changed = source.stable_projection(before, connections) != source.stable_projection(raw['fleet_after'], raw['connections_after'])
        is_pending = bool(before_pending or after_pending or changed)
        require(sample['phase']['overlap_pending'] is is_pending and raw['accepted'] is (not is_pending) and (raw['projection_changed'] is changed) and (raw['supervisor_before'] == raw['supervisor_after']) and (raw['completed_monotonic_s'] - raw['started_monotonic_s'] <= 10), 'Original bounded physical/overlap observation differs')
        require(raw['physical_failure'] is None or is_pending, 'Unexplained physical failure was accepted')
        if is_pending:
            if pending_begin is None:
                pending_begin = raw['started_monotonic_s']
            require(raw['completed_monotonic_s'] - pending_begin <= 10, 'Original reconnect overlap exceeded10s')
        else:
            pending_begin = None
        if previous_begin is not None:
            gap = raw['started_monotonic_s'] - previous_begin
            require(0 < gap <= 15, 'Original physical observation gap exceeds contract')
            max_gap = max(max_gap, gap)
        previous_begin = raw['started_monotonic_s']
        if not is_pending:
            joined = source.validate_join(before, connections, expected_fleet, membership, roles, {int(k): v for k, v in raw['physical'].items()}, {int(k): v for k, v in raw['bindings'].items()}, {int(k): v for k, v in raw['closures'].items()}, now=now, closed_connection_predicate=original_supervisor.closed_connection)
            require(joined == raw['joined'] == sample['current_v6_join'], 'Original physical result differs')
            for key, event in raw['bindings'].items():
                owned.validate_binding_cleanup(before, int(key), event, read_pin=read, closed_connection=original_supervisor.closed_connection)
            accepted += 1
        else:
            pending += 1
        for key, event in raw['bindings'].items():
            pin = before['slots'][key]['current_physical_binding']
            bindings[pin['path']] = pin
            cached = binding_cache.get(pin['path'])
            if cached is None:
                value = read(pin)
                binding_cache[pin['path']] = (pin, value)
            else:
                require(cached[0] == pin, 'An immutable binding path changed identity')
                value = cached[1]
            require(value == event, 'Actual captured binding differs from immutable event')
        api = read(sample['API'])
        pipe = api['host_pipeline']
        exposure = pipe['learning_exposure']
        require(api['pipeline_read_error'] == api['bank_persistence_read_error'] == '' and api['training_enabled'] is True and (api['measurement_active'] is False) and math.isfinite(api['loss']) and (pipe['available'] is True) and (0 <= api['pipeline_snapshot_age_s'] <= 10) and (not pipe['inference']['errors']) and (pipe['inference_graphs']['ready'] is True) and (not pipe['inference_graphs'].get('fatal_error')) and (0 <= sample['observed_unix_s'] - api['ts'] <= 10), 'Original Main API unavailable, stale or nonfinite')
        support.validate_optimizer(exposure['optimizer'], job['current_main']['owner']['pid'])
        for kind in ('optimizer', 'replay'):
            require({k: exposure[kind][k] for k in ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')} == job['current_main']['exposure'][kind], 'Original Main optimizer/replay exposure lineage changed')
        clocks = {k: api[k] for k in ('frame_count', 'learner_frame_count', 'training_steps', 'optimized_samples')}
        require(clocks == sample['clocks'] and (previous is None or all((clocks[k] >= previous[k] for k in clocks))), 'Original logical Main clocks regressed')
        previous = clocks
    require(accepted >= 2 and result['main_samples'][-1]['phase']['overlap_pending'] is False and (result['main_observer_lifecycle'] == dict(original_observer_thread_closed=True, no_child_scope_created=True)), 'Original Main final accepted sample or closed observer missing')
    for pin in bindings.values():
        h.checked(pin)
    first=result['main_samples'][0]['clocks']
    require(all(previous[k]>first[k]for k in first),'All logical Main clocks must advance')
    return dict(accepted=accepted,pending=pending,maximum_gap_s=max_gap,unique_bindings=len(bindings),
        final_accepted=True,all_logical_clocks_advanced=True,quality_qualified=False)
