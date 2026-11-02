"""Pure prospective full-game terminal validation; historical rows fail closed.

This module neither reads files nor decides quality gates. The owning evaluator
must obtain successors from its original measurement-start/game journals, and an
independent auditor must reconcile those files before any winner protection.
"""
MODE = 'confirmed_reset_reserves_v1'
SCHEMA = 'robotron-confirmed-game-reset-v1'


def require(condition, message):
    if not condition:
        raise ValueError('Unconfirmed full-game terminal: ' + message)


def integer(value, name):
    require(type(value) is int and value >= 0, name + ' must be a nonnegative integer')
    return value


def start_record(row):
    """Project an original game row or original measurement-start row equally."""
    return dict(journal_game_id=row['journal_game_id'], client_id=row['client_id'],
                client_slot=row['client_slot'], game_uid=row['game_uid'],
                start_unix_s=row['start_unix_s'], start_reason=row['start_reason'],
                known_start=row['known_start'], start_frame=row['start_frame'],
                context=row.get('start_context', row.get('context')))


def validate_terminal(row, successor):
    require(row.get('completion_policy') == MODE, 'explicit completion policy missing')
    require(row.get('complete') is True, 'partial game')
    require(row.get('start_context', {}).get('complete_game_boundary_policy') == MODE,
            'start completion policy differs')
    confirmation = row.get('terminal_confirmation')
    require(isinstance(confirmation, dict) and confirmation.get('schema') == SCHEMA,
            'terminal confirmation missing')
    score = integer(row.get('score'), 'score')
    require(confirmation.get('previous_score') == score,
            'terminal differs from accumulated full score')
    require(confirmation.get('previous_game_uid') == row.get('game_uid'), 'previous UID differs')
    reason = confirmation.get('reason')
    require(reason == row.get('boundary_reason') and reason in ('score_reset', 'zero_score_restart'),
            'terminal is not an accepted reset')
    diagnostic = confirmation.get('ingest_boundary_inputs')
    require(isinstance(diagnostic, dict) and diagnostic.get('schema') == 'robotron-game-boundary-inputs-v1'
            and diagnostic.get('classifier_verdict') == 'accept'
            and diagnostic.get('journal_start_reason') == reason, 'accepted ingest primitives missing')
    current = diagnostic.get('current_wire')
    previous = diagnostic.get('previous_accepted_wire')
    baseline = diagnostic.get('classifier_previous')
    require(isinstance(current, dict) and isinstance(previous, dict) and isinstance(baseline, dict),
            'previous/current accepted sample missing')
    require(integer(baseline.get('raw_score'), 'classifier baseline') == score % 100_000_000,
            'registered terminal truncates or differs from final classifier baseline')
    next_score = integer(confirmation.get('next_score'), 'next score')
    require(current.get('raw_score') == next_score % 100_000_000, 'next score differs from accepted wire')
    require(type(current.get('accepted_frames_before')) is int
            and type(previous.get('accepted_frames_before')) is int
            and current['accepted_frames_before'] > previous['accepted_frames_before'],
            'accepted samples are not ordered')
    if reason == 'score_reset':
        require(confirmation.get('classifier_new_game') is True
                and diagnostic.get('classifier_new_game') is True, 'classifier reset missing')
        require(next_score < score and next_score <= 100_000, 'score did not reset')
    else:
        require(score == next_score == 0, 'zero-score boundary has nonzero score')
        require(confirmation.get('previous_raw_reserves') == 0
                and type(confirmation.get('next_raw_reserves')) is int
                and 0 < confirmation['next_raw_reserves'] < 255,
                'zero-score reserve replenishment missing')
        require(confirmation.get('restart_pulse') is True
                and confirmation.get('next_wave') in (0, 1), 'zero-score restart evidence missing')
        require(confirmation.get('classifier_new_game') is False
                and diagnostic.get('classifier_new_game') is False, 'zero-score classifier evidence differs')
    require(isinstance(successor, dict), 'original successor start missing')
    require(successor.get('journal_game_id') == confirmation.get('next_journal_game_id')
            and successor.get('journal_game_id') != row.get('journal_game_id'), 'successor ID differs')
    require(successor.get('client_id') == row.get('client_id')
            and successor.get('client_slot') == row.get('client_slot')
            and successor.get('game_uid') == confirmation.get('next_game_uid'), 'successor actor/UID differs')
    require(successor.get('known_start') is True and successor.get('start_reason') == reason,
            'successor is not a known start')
    require(successor.get('start_unix_s', -1) >= row['end_unix_s'], 'successor precedes terminal')
    context = successor.get('context', {})
    require(context.get('complete_game_boundary_policy') == MODE
            and context.get('game_boundary_diagnostics') == diagnostic, 'successor accepted inputs differ')
    frame = successor.get('start_frame', {})
    require(frame.get('score') == next_score
            and frame.get('level') == confirmation.get('next_wave')
            and frame.get('player_alive') == confirmation.get('next_alive')
            and frame.get('raw_reserves') == confirmation.get('next_raw_reserves'), 'successor frame differs')
    return dict(journal_game_id=row['journal_game_id'],
                next_journal_game_id=successor['journal_game_id'], reason=reason, score=score)


def collect_successors(rows, original_game_rows, original_starts):
    """Require the independently persisted start registry and game rows to agree."""
    games, starts, full_games = {}, {}, {}
    for records, target in ((original_game_rows, games), (original_starts, starts)):
        for row in records:
            key = row['journal_game_id']
            require(key not in target, 'duplicate original journal/start ID')
            target[key] = start_record(row)
            if target is games:
                full_games[key] = row
    successors = {}
    for row in rows:
        own = row['journal_game_id']
        require(own in games and own in starts and games[own] == starts[own] == start_record(row)
                and full_games[own] == row,
                'admitted row differs from original game/start record')
        confirmation = row.get('terminal_confirmation')
        require(isinstance(confirmation, dict), 'terminal confirmation missing')
        identifier = confirmation.get('next_journal_game_id')
        require(identifier in starts and identifier in games and starts[identifier] == games[identifier],
                'next start was not retained in both original journals')
        successor = starts[identifier]
        validate_terminal(row, successor)
        successors[own] = successor
    return successors


def validate_receipt_terminals(receipt, rows):
    require(receipt.get('job', {}).get('completion_policy') == MODE,
            'job completion policy missing')
    require(receipt.get('job', {}).get('game_boundary_diagnostics') is True,
            'job accepted-boundary diagnostics missing')
    successors = receipt.get('terminal_successors')
    require(isinstance(successors, dict) and set(successors) == {r['journal_game_id'] for r in rows},
            'successor coverage differs from all admitted games')
    return [validate_terminal(row, successors[row['journal_game_id']]) for row in rows]
