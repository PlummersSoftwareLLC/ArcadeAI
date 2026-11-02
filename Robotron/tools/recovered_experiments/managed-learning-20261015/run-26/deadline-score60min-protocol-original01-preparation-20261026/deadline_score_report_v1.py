"""Dedicated deadline32 console formatting and exact four-leg numeric gates.

No file/runtime/model actions. Numeric gates alone never qualify or promote a
policy; original independent source/score/cutoff/ownership audits remain required.
"""
import statistics

SCHEMA = 'robotron-first-game-deadline-score32-v2'
ORDER = ('R1', 'C1', 'R2', 'C2')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate(seal):
    require(seal['schema'] == SCHEMA and seal['horizon_ns'] == 3_600_000_000_000,
            'Explicit selected deadline32/60-minute metric required')
    require(seal['n_scored'] == 32 and len(seal['rows']) == 32 and
            [r['slot'] for r in seal['rows']] == list(range(4096, 4128)), 'Exactly32 original scored slots required')
    completed = 0
    scores = []
    for row in seal['rows']:
        require(row['status'] in ('completed', 'censored'), 'Unknown cutoff classification')
        done = row['status'] == 'completed'
        require(row['whole_game_complete'] is done and row['right_censored'] is (not done),
                'Completion and censoring labels disagree')
        score = row['score_at_deadline']
        require(type(score) is int and score >= 0, 'Exact unwrapped integer score required')
        scores.append(score); completed += done
    require(seal['n_completed'] == completed and seal['n_censored'] == 32-completed,
            'Scored/completed/censored denominators disagree')
    require(seal['score_sum'] == sum(scores) and seal['mean_score'] == statistics.mean(scores)
            and seal['median_score'] == statistics.median(scores), 'Deadline summary differs from original32 rows')
    require(seal['full_game_quality_qualified'] is seal['improvement_qualified'] is False,
            'Original deadline seal must retain its explicit scope')
    return scores


def format_console(seal):
    validate(seal)
    lines = ['FIRST-GAME SCORE AT THE 60-MINUTE DEADLINE',
        f"Scored: {seal['n_scored']}  Completed: {seal['n_completed']}  Unfinished / right-censored: {seal['n_censored']}",
        f"Mean: {seal['mean_score']:,.1f}  Median: {seal['median_score']:,.1f}  SE: {seal['se_score']:,.1f}",
        'Slot State       Full score  Gain from anchor  First-game frames since anchor  All frames since anchor  Score age(s)  Activity age(ms)']
    for row in seal['rows']:
        gain = row['score_at_deadline']-row['score_at_anchor']
        lines.append(f"{row['slot']:4d} {row['status']:9s} {row['score_at_deadline']:12,d} {gain:17,d} "
            f"{row['selected_first_game_accepted_frame_exposure']:18,d} {row['accepted_frame_exposure']:11,d} "
            f"{row['score_snapshot_age_ns']/1e9:12.3f} {row['activity_age_ns']/1e6:17.3f}")
    lines.append('All32 first games remain in the mean and median; later games are retained outside this metric.')
    lines.append('Frame exposure is reported because a fixed wall deadline includes evaluator throughput.')
    return '\n'.join(lines)+'\n'


def compare_four(seals):
    require(type(seals) is dict and set(seals) == set(ORDER), 'All four fixed original deadline legs required')
    scores = {name: validate(seals[name]) for name in ORDER}
    reference_sha = seals['R1']['policy']['policy_sha256']
    candidate_sha = seals['C1']['policy']['policy_sha256']
    require(seals['R2']['policy']['policy_sha256'] == reference_sha and
            seals['C2']['policy']['policy_sha256'] == candidate_sha and candidate_sha != reference_sha,
            'Both roles must retain their preselected frozen policy')
    ids, sessions, connections = set(), set(), set()
    for name in ORDER:
        for row in seals[name]['rows']:
            member = row['member']
            key = (member['session'], member['connection'], member['journal_game_id'])
            require(key not in ids, 'Original first-game identity reused across legs')
            require(member['session'] not in sessions and member['connection'] not in connections,
                    'Original transport identity reused across slots or legs')
            ids.add(key)
            sessions.add(member['session']); connections.add(member['connection'])
    ref = scores['R1'] + scores['R2']
    total, n = sum(ref), len(ref)
    median2 = sorted(ref)[31] + sorted(ref)[32]
    gates = {}
    for name in ('C1', 'C2'):
        values = scores[name]
        left, right = sum(values)*n*100, total*len(values)*105
        candidate_median2 = sorted(values)[15] + sorted(values)[16]
        gates[name] = dict(n_scored=32, n_completed=seals[name]['n_completed'],
            n_censored=seals[name]['n_censored'], mean_integer_left=left, mean_integer_right=right,
            mean_gain_defined=total > 0, mean_gain_passed=total > 0 and left >= right,
            mean_gain_reason=None if total > 0 else 'relative_gain_undefined_zero_reference_score_sum',
            median_twice=candidate_median2,
            reference_median_twice=median2, median_preserved=candidate_median2 >= median2,
            numerical_gate_passed=total > 0 and left >= right and candidate_median2 >= median2)
    return dict(schema='robotron-deadline32-fixed-fresh-RCRC-numerical-gates-v1',
        metric_schema=SCHEMA, horizon_ns=3_600_000_000_000, ordered_legs=list(ORDER),
        reference_n_scored=64, reference_n_completed=seals['R1']['n_completed']+seals['R2']['n_completed'],
        reference_n_censored=seals['R1']['n_censored']+seals['R2']['n_censored'],
        reference_score_sum=total, reference_mean=statistics.mean(ref),
        reference_mean_exact=dict(numerator=total,denominator=n), reference_median_twice=median2,
        independent_candidates=gates, both_numeric_gates_passed=all(g['numerical_gate_passed'] for g in gates.values()),
        all_original_scored_rows_retained=True, candidate_pool_rescue=False,
        original_transport_identities_fresh=True,
        journal_game_identity_scope='original session plus original connection plus journal-local game id',
        independent_source_cutoff_score_and_owned_cleanup_audits_still_required=True,
        automatic_promotion=False, full_game_quality_qualified=False, causal_learning_speed_gain_established=False)
