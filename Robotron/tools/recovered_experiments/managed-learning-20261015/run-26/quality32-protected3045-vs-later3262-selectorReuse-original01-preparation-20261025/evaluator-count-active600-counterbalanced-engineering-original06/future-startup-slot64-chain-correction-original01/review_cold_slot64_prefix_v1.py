"""Independent original cold-all64 ROM1200 startup-prefix review; no game quality."""
GAMES_PER_SLOT = 1
ACTOR_COUNT = 64
import argparse
import ast
import collections
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time

def load(pin, name):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None

def analyse(timing, samples, read):
    assert timing['schema'] == 'robotron-diagnostic-observer-critical-path-timings-v1'
    assert timing['truncated'] is False and timing['health_predicates_changed'] is False
    assert timing['events_persisted_only_after_capture_stopped'] is True
    rows = timing['events']
    assert len(rows) <= 65536 and [r['event'] for r in rows] == list(range(len(rows)))
    stages = []
    gc = []
    by_stage = collections.defaultdict(list)
    for row in rows:
        if row['kind'] == 'gc':
            gc.append(row)
            continue
        assert row['kind'] == 'stage' and row['stage'] in ('initial_parent', 'emit.starting', 'verify_parent', 'guard.observe', 'emit.running', 'sleep')
        before, after = (row['before'], row['after'])
        for clock in (before, after):
            assert all((type(clock[k]) in (int, float) and math.isfinite(clock[k]) for k in ('monotonic_s', 'unix_s', 'thread_cpu_s', 'process_cpu_s')))
            assert all((type(v) is int and v >= 0 for v in clock['cpu_stat'].values()))
        wall = after['monotonic_s'] - before['monotonic_s']
        assert wall >= 0
        assert abs(after['unix_s'] - before['unix_s'] - wall) < 0.05
        assert after['thread_cpu_s'] >= before['thread_cpu_s'] and after['process_cpu_s'] >= before['process_cpu_s']
        measured = dict(stage=row['stage'], index=row['index'], event=row['event'], wall_s=wall, thread_cpu_s=after['thread_cpu_s'] - before['thread_cpu_s'], process_cpu_s=after['process_cpu_s'] - before['process_cpu_s'], before_unix_s=before['unix_s'], after_unix_s=after['unix_s'], unit_check=row['unit_check'], requested_sleep_s=row['requested_sleep_s'], error=row['error'], quota_throttled_usec=after['cpu_stat']['throttled_usec'] - before['cpu_stat']['throttled_usec'], quota_throttled_periods=after['cpu_stat']['nr_throttled'] - before['cpu_stat']['nr_throttled'])
        assert measured['quota_throttled_usec'] >= 0 and measured['quota_throttled_periods'] >= 0
        stages.append(measured)
        by_stage[row['stage']].append(measured)
    guards = {row['index']: row for row in by_stage['guard.observe']}
    assert len(guards) == len(by_stage['guard.observe']) == len(samples)
    observations = []
    for index, pin in enumerate(samples):
        record = read(pin)
        sample = record['transport']
        guard = guards[index]
        assert sample['index'] == index and guard['error'] is None
        assert guard['before_unix_s'] <= sample['API_begin_unix_s'] <= sample['observed_unix_s'] <= guard['after_unix_s']
        observations.append(dict(index=index, observed_unix_s=sample['observed_unix_s'], API_begin_unix_s=sample['API_begin_unix_s'], API_end_unix_s=sample['API_end_unix_s'], tcp_begin_unix_s=sample['tcp_begin_unix_s'], tcp_end_unix_s=sample['tcp_end_unix_s'], deep=record['deep'] is not None))
    gaps = [dict(index=b['index'], gap_s=b['observed_unix_s'] - a['observed_unix_s'], begin=a['observed_unix_s'], end=b['observed_unix_s']) for a, b in zip(observations, observations[1:])]
    assert all((gap['gap_s'] <= 0.5 for gap in gaps))
    top = []
    for gap in sorted(gaps, key=lambda row: row['gap_s'], reverse=True)[:20]:
        overlapping = []
        for stage in stages:
            overlap = max(0.0, min(gap['end'], stage['after_unix_s']) - max(gap['begin'], stage['before_unix_s']))
            if overlap:
                overlapping.append(dict(stage=stage, overlap_s=overlap))
        top.append(dict(gap, stages=overlapping, unaccounted_s=gap['gap_s'] - sum((r['overlap_s'] for r in overlapping)), GC_events=[r for r in gc if gap['begin'] <= r['monotonic_s'] + timing['started']['unix_s'] - timing['started']['monotonic_s'] <= gap['end']]))
    summary = {name: dict(count=len(items), maximum_wall_s=max((r['wall_s'] for r in items)), total_wall_s=sum((r['wall_s'] for r in items)), total_thread_cpu_s=sum((r['thread_cpu_s'] for r in items)), quota_throttled_periods=sum((r['quota_throttled_periods'] for r in items)), slowest=sorted(items, key=lambda r: r['wall_s'], reverse=True)[:10]) for name, items in by_stage.items()}
    return dict(events=len(rows), stages=len(stages), GC_events=len(gc), raw_samples=len(samples), maximum_gap_s=max((r['gap_s'] for r in gaps)), stage_summary=summary, largest20_gap_intervals=top, instrumentation_has_some_cost=True, previous_failed_case_cause_reproduced=False, no_scientific_fix_or_reliability_claim=True, quality_qualified=False)

def validate_observer420_derivation(historical_family, family, read):
    pin = family['observer_bound420_derivation']
    assert pin['sha256'] == 'bb362cf27cdfc065b275fb393706940cd29af7bd5a4b00c9d73d5ee8f556fe9a'
    derivation = read(pin)
    assert derivation['schema'] == 'robotron-cold64-observer-bounded420-source-derivation-v1'
    assert derivation['old_sources_changed'] is derivation['launched'] is False
    parents, selected = derivation['source_parents'], derivation['selected_sources']
    assert set(parents) == set(selected) == {'client', 'worker', 'controller', 'reviewer', 'protocol'}
    assert historical_family['main_observer'] == parents
    assert family['main_observer'] == selected
    assert parents['protocol'] == selected['protocol']
    assert selected['protocol']['sha256'] == '0ec8510b82783b6d47cad99ba63c59045f32e5b9acf6dbfa128b308f9641d2b9'
    for role in ('client', 'worker', 'controller', 'reviewer'):
        before = read(parents[role], False).decode()
        after = read(selected[role], False).decode()
        if role == 'client':
            expected = before.replace('12e479b0eb0545dab32da1d8f8130be3622670207c79ecaf0a164b812fa0ec5a', '2b6cd5a25c66f99011621385616efad6adaaa792ef0eab28300ba18a0f6466c7').replace('22260', '420').replace('22320', '480')
        elif role == 'worker':
            expected = before.replace('in (180,22260)', 'in (420,)').replace("{180:'3min',22260:'6h 11min'}", "{420:'7min'}")
        elif role == 'controller':
            expected = before.replace("'22260'", "'420'").replace("22320<=c['observation_s']<=22380", "480<=c['observation_s']<=480")
        else:
            expected = before.replace('22260', '420').replace('22320', '480').replace("'6h 11min'", "'7min'")
        assert expected != before and after == expected, 'Unexpected observer420 source/predicate delta: ' + role
    return dict(derivation=pin, historical_sources=parents, selected_bounded420_sources=selected,
                exact_only_watchdog_observation_and_client_controller_pin_delta_verified=True,
                historical_coalescing_CPU_proof_preserved_at_original_node=True,
                selected_protocol_and_health_algorithms_unchanged=True)

def validate_protocol_provenance(family, read):
    """Verify historical derivations at their own nodes, then the selected codec.

    Historical receipts describe their original sources. They remain immutable;
    continuity to the active running publisher requires its own guarded source.
    """
    def nodes(pin):
        return {n.name: n for n in ast.parse(read(pin, False)).body if isinstance(n, ast.FunctionDef)}

    def unchanged(parent, child, renamed):
        previous, current = nodes(parent), nodes(child)
        for name, original in previous.items():
            selected = current[renamed.get(name, name)]
            selected.name = name
            assert ast.dump(selected) == ast.dump(original), name

    RAM_contracts = read(family['RAM_control_components']['contracts'])
    assert RAM_contracts['original_codec_guards'] == 38 and RAM_contracts['RAM_negative_guards'] == 31
    RAM_provenance = read(family['RAM_control_components']['source_provenance'])
    assert RAM_provenance['helper'] == family['main_live_control']
    for record in RAM_provenance['source_changes']:
        source = read(record['prospective'], False).decode()
        for before, after in reversed(record['changes']):
            assert source.count(after) == 1
            source = source.replace(after, before)
        assert source == read(record['original'], False).decode()

    transient = family['transient_live_protocol_components']
    tproof = read(transient['protocol'])
    tprov = read(transient['source_provenance'])
    assert RAM_provenance['codec'] == tprov['prospective_protocol']
    assert tproof['original_guards'] == 38 and tproof['concurrent_publications'] == 5000
    assert tproof['strict_original_reader_and_validation_and_lock_AST_unchanged'] is True
    assert tproof['immutable_finish_and_authoritative_raw_and_outcome_unchanged'] is True
    unchanged(tprov['original_protocol'], tprov['prospective_protocol'], {'publish_live': '_publish_live_serialized_durable_v4'})
    # Preserve the original transient-publisher checks at the historical v5 node.
    publisher = nodes(tprov['prospective_protocol'])['publish_live']
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'fsync' for n in ast.walk(publisher))
    protected = next(n for n in publisher.body if isinstance(n, ast.With) and isinstance(n.items[0].context_expr, ast.Call) and isinstance(n.items[0].context_expr.func, ast.Name) and n.items[0].context_expr.func.id == '_live_lock')
    assert all(isinstance(n, (ast.If, ast.Expr)) for n in protected.body)
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'replace' for n in ast.walk(protected))

    proofs = family['serialized_protocol_components']
    component = read(proofs['protocol'])
    assert component['original_guards'] == 38 and component['concurrent_publications'] == 5000
    assert component['strict_original_read_and_publish_bodies_AST_unchanged'] and component['finish_protocol_unchanged']
    provenance = read(proofs['source_provenance'])
    assert provenance['prospective_protocol'] == tprov['original_protocol']
    unchanged(provenance['original_protocol'], provenance['prospective_protocol'], {'checked_read': '_checked_read_strict', 'publish_live': '_publish_live_unlocked'})

    selected = family['main_observer']['protocol']
    assert selected['sha256'] == '0ec8510b82783b6d47cad99ba63c59045f32e5b9acf6dbfa128b308f9641d2b9'
    unchanged(tprov['prospective_protocol'], selected, {'publish_live': '_publish_live_required_v5'})
    cpupin = family['coalescing_protocol_CPU']
    assert cpupin['sha256'] == '4ed599c14b1270619c2479aec3c33af48c0b38cc636ae8d079229dbbc0b75ec6'
    cpu = read(cpupin)
    assert cpu['actual_tool_terminal_exit'] == 0
    assert cpu['original38_contracts_4_interleaves_6_lock_negatives_2_timeouts_and5000_generic_concurrency_passed'] is True
    assert cpu['all6_descriptors_argv_resources_pins_birth_unit_cgroup_release_verified'] is True
    assert cpu['original_reader500ms_freshness_required_publications_and100ms_bounds_unchanged'] is True
    guarded = read(cpu['report'])
    assert guarded['protocol'] == selected
    assert guarded['coalescing']['groups'] == cpu['coalescing_feature_groups'] == 7
    assert guarded['coalescing']['original_reader_and_raw_validity_rules_unchanged'] is True
    assert guarded['coalescing']['coalescing_only_running_control_projections'] is True
    assert guarded['coalescing']['required_terminal_and_start_publications_unchanged'] is True
    assert guarded['coalescing']['all_children_and_threads_joined'] is True
    derivation = read(guarded['source_provenance'])
    assert derivation['derived'] == selected
    before, after = derivation['exact_change']
    parent = read(derivation['parent'], False).decode()
    assert parent.count(before) == 1 and parent.replace(before, after) == read(selected, False).decode()

    actualpin = family['coalescing_observer_component_CPU']
    actual = read(actualpin)
    assert actual['actual_tool_terminal_exit'] == actual['parent_actual_exit'] == actual['observer_actual_exit'] == 0
    assert actual['actual_protocol'] == selected
    assert actual['current_main_binding'] == family['current_component_main_binding']
    assert actualpin == family['current_main_context_CPU']
    assert actual['original500ms_freshness_and_max_gap_limits_unchanged'] is True
    assert actual['all_original_raw_indices_complete'] is True
    assert actual['all6_descriptors_resources_argv_pins_birth_units_cgroups_release_verified'] is True
    assert actual['maximum_observation_gap_s'] <= .5
    stats = actual['running_projection_publication_stats']
    assert stats['attempts'] == stats['published'] + stats['coalesced_busy_reader'] == actual['original_raw_main_samples']
    assert stats['published'] > 0 and stats['coalesced_busy_reader'] > 0 and stats['errors'] == 0
    observer420 = validate_observer420_derivation(read(actual['component_family']), family, read)
    return dict(historical_RAM_codec=RAM_provenance['codec'], historical_serialized_codec=provenance['prospective_protocol'],
                selected_protocol=selected, coalescing_protocol_CPU=cpupin, current_context_observer_CPU=actualpin,
                observer420_historical_to_selected_bridge=observer420,
                all_historical_derivations_and_retained_function_AST_verified=True,
                selected_running_publisher_exact_source_and_guarded_behavior_verified=True,
                raw_runtime_ROM_quality_and_rate_checks_unchanged=True)

def validate_cold_marker(job, result, marker):
    assert result['schema'] == 'robotron-cold-all64-startup-prefix-result-v1'
    assert job['diagnostic_role'] == 'cold_all64_startup_prefix_only' and job['wall_limit_s'] == 360
    assert marker['schema'] == 'robotron-cold-all64-prefix-only-stop-v1'
    assert marker['reason'] == 'PRECOMMITTED_ALL64_COLD_STARTUP_PREFIX_ONLY_STOP'
    assert marker['all64_prefixes_certified'] is marker['no_active600_window'] is True
    assert marker['runtime_errors_before_intentional_stop'] == []
    assert marker['server_inference_error_before_intentional_stop'] is None
    assert marker['quality_qualified'] is marker['throughput_gain_verified'] is marker['learning_speed_gain_verified'] is False
    assert result['active_start'] is result['active_end'] is result['active_frame_rate'] is None
    assert result['policy_before'] == result['policy_after'] == marker['policy']
    boundary, admission = marker['boundary'], marker['fixed_admission']
    assert boundary['ready'] is boundary['active'] is True
    assert boundary['clients'] == boundary['expected'] == boundary['acknowledged'] == 64
    assert boundary['actor_slots'] == list(range(4096, 4160))
    assert boundary['pending_client_ids'] == boundary['replay_pending_client_ids'] == []
    assert boundary['generation'] == boundary['requested_generation'] == admission['generation'] == marker['policy']['measurement_generation'] == result['controller_exit']['generation']
    assert admission['experiment'] == marker['policy']['experiment'] == job['label']
    assert set(marker['prefixes']) == set(marker['subjects']) == {str(s) for s in range(4096, 4160)}
    nonces = []
    for slot, value in marker['subjects'].items():
        entry = result['original_slots'][slot]
        assert value['pid'] == entry['pid'] and value['birth'] == entry['birth']
        assert value['handoff'] == entry['handoff'] and 1200 < value['sequence'] <= entry['frames']
        assert re.fullmatch('[a-f0-9]{64}', value['nonce']) and value['nonce'] != '0' * 64
        nonces.append(value['nonce'])
        assert marker['prefixes'][slot] == entry['prefix_summary']
    assert len(set(nonces)) == 64
    errors = result['errors']
    assert errors and errors[0] == "ValueError('PRECOMMITTED_ALL64_COLD_STARTUP_PREFIX_ONLY_STOP_NOT_A_QUALITY_RESULT')"
    # The marker is reachable only after detected runtime/transport errors were
    # zero. Every accepted later error comes from the original owned teardown;
    # retain exact strings, and fail closed on unknown/non-teardown diagnostics.
    for error in errors[1:]:
        match = re.fullmatch(r"Original slot(\d+): ValueError\('(Original full-tail exchange interrupted|Original origin client disappeared|Original startup connection ended during a frame|Actual origin inference failed)'\)", error)
        assert match and 4096 <= int(match.group(1)) <= 4159, 'Unclassified post-marker diagnostic: ' + error
    return dict(all64_armed_original_boundary=True, original_errors_retained=errors,
                full_tail_quality_validated=False)

def validate_cleanup_events(result, marker, boundary):
    assert boundary['schema'] == 'robotron-cold-prefix-intentional-cleanup-boundary-v1'
    assert boundary['original_prefix_marker'] == result['cold_prefix_marker']
    begin, declared, after = [boundary[k] for k in ('begin_monotonic_ns', 'declaration_complete_monotonic_ns', 'after_flags_monotonic_ns')]
    assert all(type(value) is int for value in (begin, declared, after))
    assert marker['observed_monotonic_s'] * 1e9 <= begin <= declared <= after
    assert boundary['errors_before_intentional_cleanup'] == [result['errors'][0]]
    assert boundary['inference_error_before_intentional_cleanup'] is None
    assert boundary['shutdown_already_set'] is False
    assert boundary['shutdown_set_before_owned_signals'] is boundary['intentional_cleanup_flag_set'] is boundary['before_first_owned_actor_signal'] is True
    observed = result['private_failure_events']
    assert type(observed) is list
    for event in observed:
        assert type(event['slot']) is int and 4096 <= event['slot'] <= 4159
        assert event['intentional_cleanup_observed'] is True
        assert type(event['observed_monotonic_ns']) is int and event['observed_monotonic_ns'] >= begin
        assert event['message'] == 'Original slot' + str(event['slot']) + ': ' + event['error']
    assert collections.Counter(event['message'] for event in observed) == collections.Counter(result['errors'][1:]), 'Unattributed private/runtime/cleanup error'
    return dict(exact_original_error_event_join=True, intentional_cleanup_source_order_and_clock_boundary_verified=True,
                original_private_failure_events=observed, original_cleanup_boundary=boundary)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--execute', action='store_true')
    p.add_argument('--job')
    p.add_argument('--job-sha256')
    p.add_argument('--source-sha256')
    a = p.parse_args()
    if not a.execute:
        print('PLAN_ONLY')
        return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == a.source_sha256
    raw = Path(a.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == a.job_sha256
    review = json.loads(raw)
    assert review['schema'] == 'robotron-cold-all64-startup-prefix-independent-review-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    h = load(review['helpers'], '_critical_review_h')
    reader = load(review['reader'], '_critical_review_reader')

    def read(pin, as_json=True):
        return reader.read_pin(pin, as_json=as_json)
    for pin in review['inputs']:
        h.checked(pin)
    job_pin = review['native_job']
    job = read(job_pin)
    out = Path(job['output'])
    result = read(review['native_result'])
    assert job['schema'] == 'robotron-cold-all64-startup-prefix-original-v1' and job['diagnostic_only'] is True and ('quality_leg' not in job)
    assert result['complete'] is result['quality_qualified'] is False and result['main_health_failure'] is None
    assert result['errors'][0] == "ValueError('PRECOMMITTED_ALL64_COLD_STARTUP_PREFIX_ONLY_STOP_NOT_A_QUALITY_RESULT')"
    assert result['original_lease_released'] is result['all_original_threads_stopped'] is result['immutable_inputs_unchanged'] is True
    assert result['original_unsealed_journal_paths'] == []
    marker = read(h.pin(out / 'original-all64-startup-prefix-only-stop.json'))
    assert result['cold_prefix_marker'] == h.pin(out / 'original-all64-startup-prefix-only-stop.json')
    validate_cold_marker(job, result, marker)
    cleanup_attribution = validate_cleanup_events(result, marker, read(result['prefix_cleanup_boundary']))
    load(job['startup_lua_chain']['guard'], '_cold_actual_Lua_chain').validate_job(job)
    assert marker['reason'] == 'PRECOMMITTED_ALL64_COLD_STARTUP_PREFIX_ONLY_STOP'
    assert set(marker['prefixes']) == {str(s) for s in range(4096, 4096 + ACTOR_COUNT)}
    assert 0 < marker['observed_monotonic_s'] - result['native_started_monotonic_s'] < 300
    assert marker['observed_monotonic_s'] < result['native_deadline_monotonic_s'] == result['native_started_monotonic_s'] + 360
    arc = load(review['archive'], '_critical_review_arc')
    owner = read(review['native_owner'])
    cfg = read(review['native_config'])
    fields = arc.archived_closure(read(review['native_closure']), owner, read, exit_zero=False)
    for k, v in dict(Id=owner['unit'], InvocationID=owner['invocation_id'], ExecMainPID=str(owner['pid']), ExecMainCode='1', ExecMainStatus='1', CPUQuotaPerSecUSec='12s', MemoryMax=str(24 << 30), MemorySwapMax='0', RuntimeMaxUSec='7min', TasksMax='512', TimeoutStopUSec='30s', KillMode='mixed', SendSIGKILL='no', Restart='no', NRestarts='0').items():
        assert fields[k] == v
    command = '/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR=' + str(Path(cfg['output']) / 'tmp') + ' ' + ' '.join(cfg['argv'])
    assert command + ' ; ignore_errors=no ;' in fields['ExecStart']
    for pin in cfg['pins']:
        actual = h.pin(pin['path'])
        assert all((actual[k] == pin[k] for k in ('path', 'sha256', 'bytes')))
        assert all((actual['identity'][k] == v for k, v in pin['identity'].items()))
    control = load(review['native_controller'], '_critical_review_control')
    control.checked_config(review['native_config']['path'])
    for unit in (owner['unit'], owner['timer']):
        assert control.show(unit)['LoadState'] == 'not-found'
    assert birth(owner['pid']) != owner['starttime_ticks']
    assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', owner['unit']).exists()
    started = int(fields['ExecMainStartTimestampMonotonic']) / 1000000.0
    ended = int(fields['ExecMainExitTimestampMonotonic']) / 1000000.0
    assert 0 < started < ended <= time.monotonic() and ended - started <= 480
    family = read(job['source_family_manifest'])
    protocol = read(job['main_health_protocol'])
    verifier = load(family['main_observer']['reviewer'], '_critical_review_observer')
    checked = verifier.verify(job, job_pin, owner, cfg['argv'], result['main_observer_lifecycle'], protocol, family, [], read, h)
    assert checked['closed_report'] == result['main_health_report']
    closed = read(result['main_health_report'])
    assert closed['actual_status'] == result['main_samples']
    assert len(closed['samples']) >= 2 and closed['deep_samples'] >= 1
    engine = load(protocol['health_job']['sources']['full_health_engine'], '_critical_review_engine')
    capture = family['inet_diag_capture_components']
    contracts = read(capture['contracts'])
    capacity = read(capture['resource'])
    query = read(capture['query'])
    assert contracts['typed_negative_rejections'] == 187 and capacity['resource_passed'] is True
    assert capacity['synthetic_samples'] == 48332 and capacity['actual_elapsed_s'] < 600
    assert query['exact_original_source_OR_destination_port9998_predicate'] is True
    capture_provenance = read(capture['capture_provenance'])
    selected = {Path(row['prospective']['path']).name: row['prospective'] for row in capture_provenance['source_changes']}
    for key in ('io', 'primitives'):
        pin = protocol['health_job']['sources'][key]
        assert selected[Path(pin['path']).name] == pin
    collector = load(protocol['health_job']['sources']['collector'], '_kernel600_unpack')
    original_read = read
    sample_paths = {pin['path'] for pin in closed['samples']}
    kernel_epochs = []

    def kernel_read(pin, as_json=True):
        value = original_read(pin, as_json)
        if as_json and pin['path'] in sample_paths:
            sample = collector.unpacked(value)
            snapshot = json.loads(sample['raw_tcp'])
            assert snapshot['schema'] == 'robotron-original-inet-diag-port9998-snapshot-v3' and snapshot['error'] is None
            assert snapshot['begin_unix_s'] == sample['tcp_begin_unix_s'] and snapshot['end_unix_s'] == sample['tcp_end_unix_s']
            assert sample['index'] == len(kernel_epochs)
            kernel_epochs.append(dict(index=sample['index'], begin_unix_s=snapshot['begin_unix_s'], end_unix_s=snapshot['end_unix_s'], datagrams=len(snapshot['datagrams']), raw_envelope_bytes=len(sample['raw_tcp'])))
        return value
    replay = engine.replay(protocol['health_job'], closed['samples'], read(closed['initial_cursors']), kernel_read, h, prior_groups=[], original_statuses=closed['actual_status'])
    assert len(kernel_epochs) == replay['samples']
    assert replay['transport'] == closed['transport'] and replay['deep_samples'] == closed['deep_samples']
    assert started <= closed['guard_started_monotonic_s'] <= replay['first_deep_monotonic_s'] <= replay['last_deep_monotonic_s'] <= closed['guard_ended_monotonic_s'] <= ended
    assert closed['guard_ended_monotonic_s'] >= marker['observed_monotonic_s']
    outcome = read(checked['worker_outcome'])
    assert outcome['interpreter']['GIL_enabled'] is False and outcome['interpreter']['major_minor'] == [3, 14]
    assert family['main_observer']['protocol']['sha256'] == '0ec8510b82783b6d47cad99ba63c59045f32e5b9acf6dbfa128b308f9641d2b9'
    RAM = checked['RAM_control_review']
    life = read(result['main_observer_lifecycle'])
    RAM_release = read(life['live_control_release'])
    RAM_intent = read(RAM_release['intent'])
    lock_item = next((row for row in RAM_intent['files'] if Path(row['original']['path']).name == 'live.json.lock'))
    lock_pin = lock_item['archived']
    assert read(lock_pin, False) == b'' and lock_item['original']['identity']['mode'] == '0o600'
    assert not Path(lock_item['original']['path']).exists() and (not Path(RAM_release['binding']['root']).exists())
    assert not (out / 'main-observations/live.json').exists() and (not (out / 'main-observations/live.json.lock').exists())
    protocol_provenance = validate_protocol_provenance(family, read)
    transient = family['transient_live_protocol_components']
    quota_audit = load(review['quota_game_auditor'], '_quota64_engineering_selection')
    quota_runtime = load(review['quota_runtime'], '_quota64_engineering_policy_descriptor')
    assert result['quota64_source_pins'] == job['quota64_source_pins']
    assert result['cohort_selection'] == quota_runtime.COHORT_SELECTION
    source_guard = read(review['source_family_guard_closeout'])
    assert source_guard['native_job'] == job_pin and source_guard['native_runtime'] == job['runtime']
    assert source_guard['status'] == 'PASS_ORIGINAL_QUOTA64_NATIVE_FAMILY_GUARDS_AND_CPU_CLOSED0'
    assert source_guard['actual_exit'] == 0
    starts = quota_audit.lines(read(result['journal']['measurement_starts.jsonl'], False))
    starts_index = quota_audit.indexed(starts, 'startup starts')
    final_games_index = quota_audit.indexed(quota_audit.lines(read(result['journal']['games.jsonl'], False)), 'closed startup games')
    admission = read(h.pin(out / 'original-fixed-admission.json'))
    assert admission['close_unix_ns'] - admission['open_unix_ns'] == 21540000000000
    assert admission == marker['fixed_admission']
    prefix_result = dict(result, _admission=admission)
    cohort = result['after_intentional_stop']
    selected, counts, outside = quota_audit.select_original_starts(starts, job['label'], cohort['start_ts'], cohort['close_ts'], source_is_start_order=True)
    assert cohort['started_ids'] == list(selected) and cohort['started'] == len(selected)
    assert cohort['slot_admitted_counts'] == {str(slot): count for slot, count in counts.items()}
    assert set(counts) == set(range(4096, 4096 + ACTOR_COUNT)) and all((1 <= count <= GAMES_PER_SLOT for count in counts.values()))
    assert cohort['pending'] == 0 and cohort['count'] + cohort['abandoned'] == cohort['started']
    assert cohort['retained_outside_cohort_ids'] == outside
    assert result['controller_exit']['valid'] is False
    quota_selection = dict(strategy=quota_runtime.COHORT_SELECTION, started_ids=list(selected), slot_counts=counts, retained_outside_start_ids=outside, completed_at_engineering_stop=cohort['count'], abandoned_after_engineering_stop=cohort['abandoned'], scientific_quality_not_evaluated=True)
    assert result['active_start'] is result['active_end'] is result['active_frame_rate'] is None
    assert result['policy_after'] == result['policy_before'] == marker['policy']
    assert job['experiment_precommit'] == review['engineering_design']
    assert job['main_rate_reader'] == review['main_rate_reader']
    policy = result['policy_before']
    loaded_pin = h.pin(out / 'original-loaded-policy.json')
    loaded = read(loaded_pin)
    assert loaded['policy'] == policy and policy['checkpoint_sha256'] == job['checkpoint']['sha256'] == 'b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
    assert policy['training_enabled'] is policy['replay_enabled'] is False and policy['epsilon'] == policy['expert_ratio'] == 0
    assert loaded['gpu_uuid'] == job['gpu_uuid'] and loaded['compile_report']['all_shapes_verified'] == list(range(1, 17))
    assert loaded['memory_is_none'] is loaded['optimizer_is_none'] is True
    initial_helpers = load(review['initial_helpers'], '_critical_review_initial')
    initial = initial_helpers.validate_initial_readiness(read(result['initial_main_readiness']), result['initial_main_readiness'], job, job_pin, replay, loaded_pin, read(h.pin(out / 'original-fixed-admission.json')), started, ended)
    wire = load(review['original_wire_auditor'], '_critical_review_wire')
    wire.dependencies()
    games = wire.games_audit
    reaped = result['original_post_origin_child_reap']
    assert reaped['all_original_children_reaped'] is True
    assert reaped['unknown_slots'] == [] and reaped['signals_sent'] is reaped['exit_statuses_normalized'] is False
    prefixes = []
    for slot in range(4096, 4096 + ACTOR_COUNT):
        entry = result['original_slots'][str(slot)]
        child = reaped['original_children'][str(slot)]
        assert entry['pid'] == child['pid'] and entry['birth'] == child['birth'] and (entry['actual_exit'] == child['actual_exit'] == 0)
        assert birth(entry['pid']) != entry['birth'] and entry['outputs_sealed_after_original_writer_closure'] is True
        assert entry['original_unsealed_output_paths'] == [] and marker['prefixes'][str(slot)] == entry['prefix_summary']
        for pin in entry['files'].values():
            h.checked(pin)
        rows = games.lines(read(entry['files']['producer.jsonl'], False))
        subject = dict(slot=slot, session=job['sessions'][str(slot)], connection=job['connections'][str(slot)])
        assert all((all((row[k] == v for k, v in subject.items())) for row in rows))
        assert rows[-1] == entry['prefix_summary']['footer'] and rows[-1]['reason'] == 'prefix_complete' and (rows[-1]['failed'] is False)
        chunks = [r for r in rows if r['kind'] == 'raw_ROM_chunk']
        assert [r['offset'] for r in chunks] == list(range(0, 102400, 128))
        image = b''.join((bytes.fromhex(r['data_hex']) for r in chunks))
        assert len(image) == 102400 and hashlib.sha256(image).hexdigest() == job['loaded_rom_sha256']
        raw_wire = games.lines(read(entry['files']['proxy.jsonl'], False))
        assert [r['proxy_event'] for r in raw_wire] == list(range(1, len(raw_wire) + 1))
        certificate = wire.audit_slot_prefix(slot, entry, job, prefix_result, starts_index, final_games_index, read, h.pin, expected_job_sha256=job_pin['sha256'])
        assert certificate['nonce'] == marker['subjects'][str(slot)]['nonce']
        assert certificate['certificate_identifier'] == marker['subjects'][str(slot)]['handoff']['certificate_identifier']
        prefixes.append(dict(slot=slot, certificate=certificate, all1200_original_pairs_ROM_START_nonce_initialized_firstplay_independently_replayed=True, full_tail_quality_not_validated=True))
    h.checked(job['lease'])
    fd = os.open(job['lease']['path'], os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    for port in (19998, *range(20000, 20000 + ACTOR_COUNT)):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    gpu = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory', '--format=csv,noheader'], capture_output=True, text=True, check=True, timeout=10)
    assert job['gpu_uuid'] not in gpu.stdout and 'torch' not in sys.modules
    output = Path(review['output'])
    output.mkdir(mode=448)
    rp = h.put(output / 'report.json', dict(schema='robotron-cold-all64-startup-prefix-independent-review-v1', native_job=job_pin, native_result=review['native_result'], native_actual_interval=[started, ended], native_expected_exit1_verified=True, all_native_archives_resources_commands_pins_release_verified=True, worker_independent_review=checked, raw_replay=replay, initial_readiness=initial, all_declared_original_startup_prefixes=prefixes, declared_actor_count=ACTOR_COUNT, quota64_raw_selection=quota_selection, original_source_family_guard_closeout=review['source_family_guard_closeout'], cold_prefix_stop=marker, all64_actual_armed_generation_acknowledgements_verified=True, startup_only_expected_exit_and_cleanup_classified=True, cleanup_event_attribution=cleanup_attribution, no_active600_window=True, strict_live_protocol=family['main_observer']['protocol'], archived_RAM_live_lock=lock_pin, original_RAM_live_lock=lock_item['original'], RAM_control_independent_review=RAM, strict_original_reader_and_historical_publisher_AST_verified=True, historical_transient_and_selected_coalescing_provenance_verified=True, protocol_provenance=protocol_provenance, transient_live_components=transient, all64_cold_startup_prefix_requirement_achieved=True, all_original_fixed_query_kernel_epochs_and_raw_headers_independently_replayed=True, kernel_epochs=kernel_epochs, filtered_capture_components=capture, all_original_errors_retained=result['errors'], private_resources_free=True, scientific_case=False, previous_scientific_failure_reproduced=False, health_fix_verified=False, quality_qualified=False, created_unix_s=time.time()))
    print(json.dumps(dict(report=rp, samples=len(closed['samples']), max_gap_s=replay['maximum_observation_gap_s'])))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
