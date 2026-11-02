"""Additional read-only proof for permitted post-cutoff SIGTERM exits."""

def validate_post_cutoff_exit(slot, child, entry, score_row, cleanup, seal, seal_pin, failures):
    assert child['actual_exit'] == -15
    assert score_row['slot'] == int(slot) and score_row['status'] == 'censored'
    assert cleanup['schema'] == 'robotron-deadline32-intentional-cleanup-v1'
    assert cleanup['original_score_seal'] == seal_pin
    assert cleanup['errors_before'] == [] and cleanup['inference_error_before'] is None
    assert cleanup['server_shutdown_set_before_owned_signals'] is True
    assert cleanup['all_unfinished_original_children_live_before_cutoff'] is True
    assert cleanup['all32_original_origin_handlers_retained_until_common_shutdown'] is True
    assert seal['deadline_monotonic_ns'] <= seal['seal_observed_monotonic_ns']
    assert seal['seal_observed_monotonic_ns'] == cleanup['score_sealed_monotonic_ns']
    assert cleanup['score_sealed_monotonic_ns'] < cleanup['begin_monotonic_ns']
    assert cleanup['begin_monotonic_ns'] <= cleanup['declared_monotonic_ns'] <= cleanup['after_flags_monotonic_ns']
    keys = ['begin_monotonic_ns', 'declared_monotonic_ns', 'after_flags_monotonic_ns', 'score_sealed_monotonic_ns']
    assert entry['intentional_cleanup'] == {key: cleanup[key] for key in keys}
    assert entry['expected_deadline_retirement'] is True
    expected = f"DeadlineRetired('Selected deadline snapshot sealed; retire original slot {slot}')"
    assert entry['actual_proxy_error'] == expected
    matching = [event for event in failures if event['slot'] == int(slot)]
    assert len(matching) == 1
    event = matching[0]
    assert event['error'] == expected
    assert event['intentional_cleanup_flag'] is True and event['expected_deadline_retirement'] is True
    assert event['observed_monotonic_ns'] >= cleanup['after_flags_monotonic_ns']
    return dict(slot=int(slot), pid=child['pid'], birth=child['birth'], actual_exit=-15,
                score_status='censored', declared_cleanup_after_score_seal=True,
                original_proxy_retired_after_declared_cleanup=True,
                termination_allowed_by_unchanged_native_finally=True,
                exact_per_child_signal_timestamp_recorded=False)
