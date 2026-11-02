"""One saved-evidence C2 membership/statistics and separate C1/C2 math join.

Default is inert. Never invokes a scientific reviewer, changes original
producers, selects rows, publishes a policy, or touches a live learner.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import stat
import statistics
import time

P = Path(__file__).resolve().parent
Q = P.parent


def ident(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path):
    path = Path(path)
    before = ident(path.stat())
    raw = path.read_bytes()
    assert ident(path.stat()) == before
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), identity=before)


def read(entry):
    assert pin(entry['path']) == entry and entry['identity']['mode'] == '0o444'
    raw = Path(entry['path']).read_bytes()
    assert pin(entry['path']) == entry
    return json.loads(raw)


def put(path, raw):
    with path.open('xb') as f:
        f.write(raw)
        f.flush()
        os.fchmod(f.fileno(), 0o444)
        os.fsync(f.fileno())
    return pin(path)


def emit(path, value):
    return put(path, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def capture(path, target):
    path = Path(path)
    before = pin(path)
    assert before['identity']['uid'] == os.getuid() and before['identity']['nlink'] == 1
    assert before['bytes'] <= 32 << 20
    raw = path.read_bytes()
    assert pin(path) == before
    copy = put(target, raw)
    assert copy['sha256'] == before['sha256'] and pin(path) == before
    return raw, dict(original=before, readonly_copy=copy, original_producer_changed=False)


def number(value):
    return dict(value=float(value), numerator=value.numerator, denominator=value.denominator)


def med(scores):
    values = sorted(scores)
    n = len(values)
    return Fraction(values[n // 2]) if n % 2 else Fraction(values[n // 2 - 1] + values[n // 2], 2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--derive-once', action='store_true')
    p.add_argument('--job', type=Path)
    p.add_argument('--job-sha256')
    args = p.parse_args()
    if not args.derive_once:
        return
    jp = pin(args.job)
    assert jp['sha256'] == args.job_sha256
    job = read(jp)
    assert job['schema'] == 'robotron-current-closed-C2-and-separate-gates-job-v1'
    assert job['original_attempt'] == 1 and job['no_retry'] is True
    out_c2, out_math = P / 'C2-original-full64-closed-readback.json', P / 'separate-C1-C2-numerical-gates-readback.json'
    D = P / 'closed-math-original01'
    assert not out_c2.exists() and not out_math.exists() and not D.exists()
    review, controller = read(job['review_report']), read(job['native_controller_result'])
    assert controller['original_native_exit'] == controller['original_review_exit'] == 0
    assert controller['review_report'] == job['review_report']
    assert controller['valid'] is controller['quality_qualified'] is True
    assert review['status'] == 'VALID_CLOSED_FOUR_LEG_QUALITY32_REVIEW'
    assert review['valid'] is review['quality_qualified'] is True
    assert review['decision']['candidates_pooled_for_qualification'] is False
    fixed_parent = read(job['fixed_reference_readback'])
    membership = read(job['C2_closed_membership'])
    assert membership['admission_membership_frozen'] is True
    frozen_ids = set(membership['joined_snapshot_ids'])
    assert len(frozen_ids) == 64
    plan = read(job['plan'])
    assert len(plan['legs']) == len(review['legs']) == 4
    D.mkdir(mode=0o700)
    legs, receipts, inputs = [], [], []
    expected_counts = [70, 65, 68, 64]
    for index, (spec, reviewed, count) in enumerate(zip(plan['legs'], review['legs'], expected_counts), 1):
        assert spec['index'] == reviewed['index'] == index
        assert spec['role'] == reviewed['role'] == ('reference' if index in (1, 3) else 'candidate')
        raw, evidence = capture(spec['receipt_path'], D / f'leg{index}-original-receipt.readonly.json')
        assert evidence['original']['sha256'] == reviewed['receipt_sha256']
        receipt = json.loads(raw)
        assert receipt['valid'] is receipt['complete'] is True
        assert receipt['active'] is False and receipt['phase'] == 'finished'
        assert receipt['invalidity_reasons'] == receipt['cleanup_errors'] == []
        assert receipt['receipt_validator'] == 'passed'
        assert receipt['count'] == receipt['started'] == count >= 50
        assert receipt['pending'] == receipt['abandoned'] == 0
        assert receipt['cohort']['closed'] is receipt['cohort']['complete'] is True
        rows = receipt['rows']
        assert rows == receipt['cohort']['rows'] and len(rows) == count
        assert len({r['journal_game_id'] for r in rows}) == count
        assert {r['client_slot'] for r in rows} == set(range(4096, 4128))
        policy = job['reference_sha256'] if index in (1, 3) else job['candidate_sha256']
        clocks = [1597432474, 6585181, 25397106688] if index in (1, 3) else [1741229950, 7128160, 27621148672]
        assert receipt['checkpoint_sha256'] == policy
        for row in rows:
            assert row['complete'] is row['eligible'] is row['known_start'] is row['eval_only'] is True
            assert row['first_play_level'] == 1 and type(row['score']) is int and row['score'] >= 0
            assert receipt['cohort']['start_ts'] <= row['start_unix_s'] <= receipt['cohort']['close_ts']
            for ctx in (row['start_context'], row['end_context']):
                assert [ctx[k] for k in ('learner_frames', 'training_steps', 'optimized_samples')] == clocks
                assert ctx['epsilon'] == ctx['expert_ratio'] == 0 and ctx['difficulty'] == 5
                assert ctx['measurement_active'] is True and ctx['measurement_generation'] == 1
        scores = [r['score'] for r in rows]
        assert statistics.mean(scores) == receipt['mean']
        assert statistics.median(scores) == receipt['median']
        legs.append(dict(index=index, role=spec['role'], rows=rows, scores=scores))
        receipts.append(receipt)
        inputs.append(evidence)
    c2 = receipts[3]
    ids = {r['journal_game_id'] for r in c2['rows']}
    assert ids == frozen_ids == set(c2['cohort']['started_ids'])
    assert c2['cohort']['start_ts'] == 1792648130.7147546 and c2['cohort']['close_ts'] == 1792653530.7147546
    games_raw, games_evidence = capture(Path(plan['legs'][3]['receipt_path']).parent / 'journal/games.jsonl', D / 'C2-games.readonly.jsonl')
    starts_raw, starts_evidence = capture(Path(plan['legs'][3]['receipt_path']).parent / 'journal/measurement_starts.jsonl', D / 'C2-starts.readonly.jsonl')
    assert c2['terminal_journal_sha256'] == {'games.jsonl': hashlib.sha256(games_raw).hexdigest(), 'measurement_starts.jsonl': hashlib.sha256(starts_raw).hexdigest()}
    games = [json.loads(x) for x in games_raw.splitlines()]
    starts = [json.loads(x) for x in starts_raw.splitlines()]
    by_id = {r['journal_game_id']: r for r in games}
    assert len(by_id) == len(games)
    assert all(by_id[r['journal_game_id']] == r for r in c2['rows'])
    assert {r['journal_game_id'] for r in starts if c2['cohort']['start_ts'] <= r['start_unix_s'] <= c2['cohort']['close_ts']} == ids
    reference_rows = legs[0]['rows'] + legs[2]['rows']
    assert len({r['journal_game_id'] for r in reference_rows}) == 138
    prior_rows = fixed_parent['fixed_fresh_reference']['original_reference_membership']
    assert {r['journal_game_id']: r['score'] for r in reference_rows} == {r['journal_game_id']: r['score'] for r in prior_rows}
    scores = [r['score'] for r in reference_rows]
    ref_mean, ref_med = Fraction(sum(scores), 138), med(scores)
    prior = fixed_parent['fixed_fresh_reference']
    assert sum(scores) == prior['score_sum'] == 530891825
    assert float(ref_mean) == prior['mean'] and float(ref_med) == prior['median']
    assert review['decision']['pooled_reference'] == dict(count=138, score_sum=sum(scores), mean=float(ref_mean), median=float(ref_med))
    confirmations = []
    for leg, checked in zip((legs[1], legs[3]), review['decision']['individual_candidate_checks']):
        values = leg['scores']
        mean, median = Fraction(sum(values), len(values)), med(values)
        mean_pass, median_pass = mean >= ref_mean * Fraction(21, 20), median >= ref_med
        assert checked['index'] == leg['index'] and checked['count'] == len(values)
        assert checked['mean'] == float(mean) and checked['median'] == float(median)
        assert checked['mean_pass'] is mean_pass is True and checked['median_pass'] is median_pass is True
        confirmations.append(dict(leg_index=leg['index'], count=len(values), score_sum=sum(values), mean=number(mean), median=number(median), mean_pass=mean_pass, median_pass=median_pass, relative_mean_gain_percent=float((mean / ref_mean - 1) * 100)))
    c2proof = dict(status='ORIGINAL_C2_FULL64_CLOSED_RECEIPT_JOURNAL_MEMBERSHIP_STATISTICS_JOIN_PASS', source=pin(__file__), job=jp,
        original_receipt=inputs[3], original_games=games_evidence, original_starts=starts_evidence, original_membership=job['C2_closed_membership'],
        count=64, pending=0, abandoned=0, mean=c2['mean'], median=c2['median'], all32_completed_slots=True, full64_ids=sorted(ids),
        original_final_scientific_review=job['review_report'], scientific_audit_rerun=False, promotion=False)
    c2pin = emit(out_c2, c2proof)
    result = dict(status='CURRENT_FIXED138_AND_BOTH_SEPARATE_CANDIDATE_NUMERICAL_GATES_MATCH_ORIGINAL_FINAL_REVIEW', source=pin(__file__), job=jp,
        original_final_scientific_review=job['review_report'], original_receipts=inputs, prior_fixed_reference=job['fixed_reference_readback'],
        fixed_reference=dict(count=138, score_sum=sum(scores), mean=number(ref_mean), median=number(ref_med)), candidate_confirmations=confirmations,
        both_independent_numerical_gates_passed=True, candidates_pooled_for_qualification=False, independent_C2_closed_readback=c2pin,
        original_attempt=1, no_retry=True, scientific_audit_rerun=False, promotion=False, observed_unix_s=time.time())
    resultpin = emit(out_math, result)
    print(json.dumps(dict(C2_readback=c2pin, numerical_readback=resultpin, fixed_reference=result['fixed_reference'], confirmations=confirmations)))


if __name__ == '__main__':
    main()
