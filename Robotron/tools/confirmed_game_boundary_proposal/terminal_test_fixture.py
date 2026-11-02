"""Synthetic unit-test proof construction; never original evaluation evidence."""
def add_confirmed_fixture(data):
    import copy
    mode = 'confirmed_reset_reserves_v1'
    data['job'].update(completion_policy=mode, game_boundary_diagnostics=True)
    successors = {}
    for index, row in enumerate(data['rows']):
        zero = row['score'] == 0
        reason = 'zero_score_restart' if zero else 'score_reset'
        uid = index + 1
        next_uid = uid if zero else uid + 10000
        row.update(client_id=index % 16, game_uid=uid, completion_policy=mode,
                   boundary_reason=reason, start_reason='score_reset')
        row['start_context']['complete_game_boundary_policy'] = mode
        diagnostic = dict(schema='robotron-game-boundary-inputs-v1',
            journal_start_reason=reason, classifier_verdict='accept', classifier_new_game=not zero,
            classifier_previous=dict(raw_score=row['score'] % 100_000_000, raw_wave=1, player_alive=False),
            previous_accepted_wire=dict(raw_score=row['score'] % 100_000_000, accepted_frames_before=5),
            current_wire=dict(raw_score=0, accepted_frames_before=6))
        next_id = row['journal_game_id'] + ':next'
        row['terminal_confirmation'] = dict(schema='robotron-confirmed-game-reset-v1',
            reason=reason, previous_score=row['score'], next_score=0,
            previous_game_uid=uid, next_game_uid=next_uid, previous_raw_reserves=0,
            next_raw_reserves=2, next_wave=1, next_alive=False, restart_pulse=True,
            classifier_new_game=not zero, next_journal_game_id=next_id,
            ingest_boundary_inputs=diagnostic)
        successors[row['journal_game_id']] = dict(journal_game_id=next_id,
            client_id=row['client_id'], client_slot=row['client_slot'], game_uid=next_uid,
            known_start=True, start_reason=reason, start_unix_s=row['end_unix_s']+.01,
            start_frame=dict(score=0, level=1, player_alive=False, raw_reserves=2),
            context=dict(complete_game_boundary_policy=mode,
                         game_boundary_diagnostics=copy.deepcopy(diagnostic)))
    data['terminal_successors'] = successors
