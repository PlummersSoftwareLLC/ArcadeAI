"""One small archived-data derivation; inert unless --derive-once is supplied.

Join the two already consumed full-reference readbacks and independently
calculate C1 numerical conditions. This never invokes the scientific reviewer,
reads live APIs, changes runtime, or qualifies/promotes a candidate.
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

REFERENCE = 'c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'
CANDIDATE = 'e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
Q = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-reference1597-vs-production1741-original01-preparation-20261021')
OUTPUT = Q / 'fixed-fresh-R1-R2-and-conditional-C1-math-original01.json'


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path):
    path = Path(path)
    before = identity(path.stat())
    raw = path.read_bytes()
    assert before == identity(path.stat())
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), identity=before)


def bytes_from(entry):
    assert pin(entry['path']) == entry
    assert entry['identity']['mode'] == '0o444'
    assert entry['identity']['uid'] == os.getuid() and entry['identity']['nlink'] == 1
    raw = Path(entry['path']).read_bytes()
    assert pin(entry['path']) == entry
    return raw


def read(entry):
    return json.loads(bytes_from(entry))


def put(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as f:
        f.write(raw)
        f.flush()
        os.fchmod(f.fileno(), 0o444)
        os.fsync(f.fileno())
    return pin(path)


def fraction(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def median_fraction(scores):
    scores = sorted(scores)
    n = len(scores)
    return (Fraction(scores[n // 2]) if n % 2 else
            Fraction(scores[n // 2 - 1] + scores[n // 2], 2))


def cohort(entry, role, count, label, policy, clocks):
    result = read(entry['original_result'])
    proof = read(entry['readback'])
    assert result['original_exit'] == 0 and result['no_retry'] is True
    assert result['independent_readback'] == entry['readback']
    assert proof['status'] == f'ORIGINAL_{role}_COMPLETED_RECEIPT_ALL{count}_MEMBERSHIP_AND_STATISTICS_JOIN_PASS'
    assert proof['count'] == count and proof['pending'] == proof['abandoned'] == 0
    assert proof['all32_completed_slot_coverage'] is True
    assert proof['full_terminal_and_ROM_audit_still_required'] is True
    assert proof['scientific_reviewer_or_terminal_auditor_rerun'] is False
    assert proof['quality_qualified'] is False and proof['promotion'] is False
    receipt = read(proof['original_receipt']['readonly_copy'])
    membership = read(proof['original_fixed_membership'])
    assert receipt['valid'] is True and receipt['complete'] is True
    assert receipt['receipt_validator'] == 'passed' and receipt['cleanup_errors'] == []
    assert receipt['invalidity_reasons'] == [] and receipt['checkpoint_sha256'] == policy
    assert receipt['label'] == label and receipt['phase'] == 'finished'
    rows = receipt['rows']
    assert rows == receipt['cohort']['rows'] and len(rows) == count >= 50
    ids = {r['journal_game_id'] for r in rows}
    assert len(ids) == count and ids == set(membership['joined_snapshot_ids'])
    assert ids == set(receipt['cohort']['started_ids'])
    assert {r['client_slot'] for r in rows} == set(range(4096, 4128))
    raw_games = bytes_from(proof['original_games']['readonly_copy'])
    raw_starts = bytes_from(proof['original_starts']['readonly_copy'])
    assert receipt['terminal_journal_sha256'] == {
        'games.jsonl': hashlib.sha256(raw_games).hexdigest(),
        'measurement_starts.jsonl': hashlib.sha256(raw_starts).hexdigest()}
    games = [json.loads(line) for line in raw_games.splitlines()]
    starts = [json.loads(line) for line in raw_starts.splitlines()]
    by_id = {r['journal_game_id']: r for r in games}
    starts_by_id = {r['journal_game_id']: r for r in starts}
    assert len(by_id) == len(games) and len(starts_by_id) == len(starts)
    for row in rows:
        assert row == by_id[row['journal_game_id']]
        assert row['complete'] is True and row['eligible'] is True and row['known_start'] is True
        assert row['first_play_level'] == 1 and row['experiment'] == label
        assert row['measurement_active'] is True and row['measurement_generation'] == 1
        start = starts_by_id[row['journal_game_id']]
        assert start['start_unix_s'] == row['start_unix_s']
        assert receipt['cohort']['start_ts'] <= start['start_unix_s'] <= receipt['cohort']['close_ts']
        assert type(row['score']) is int and row['score'] >= 0
        for context in (row['start_context'], row['end_context']):
            assert [context[k] for k in ('learner_frames', 'training_steps', 'optimized_samples')] == clocks
            assert context['epsilon'] == context['expert_ratio'] == 0 and context['difficulty'] == 5
            assert context['measurement_active'] is True and context['measurement_generation'] == 1
    scores = [r['score'] for r in rows]
    mean, median = statistics.mean(scores), statistics.median(scores)
    assert mean == receipt['mean'] == proof['mean']
    assert median == receipt['median'] == proof['median']
    return rows, dict(role=role, count=count, score_sum=sum(scores), mean=mean,
                      median=median, original_result=entry['original_result'],
                      readback=entry['readback'], original_receipt=proof['original_receipt']['readonly_copy'],
                      original_games=proof['original_games']['readonly_copy'],
                      original_starts=proof['original_starts']['readonly_copy'],
                      original_fixed_membership=proof['original_fixed_membership'],
                      all32_completed_slots=True, pending=0, abandoned=0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--derive-once', action='store_true')
    p.add_argument('--job', type=Path)
    p.add_argument('--job-sha256')
    args = p.parse_args()
    if not args.derive_once:
        return
    assert not OUTPUT.exists(), 'Original derivation scope already consumed'
    job_pin = pin(args.job)
    assert job_pin['sha256'] == args.job_sha256
    job = read(job_pin)
    assert job['schema'] == 'robotron-fixed-fresh-R1-R2-conditional-C1-derivation-job-v1'
    assert job['reference_sha256'] == REFERENCE and job['candidate_sha256'] == CANDIDATE
    assert job['original_attempt'] == 1 and job['no_retry'] is True
    assert job['output'] == str(OUTPUT)
    native = read(job['original_native_config'])
    argv = native['argv']
    assert argv[argv.index('--reference-label') + 1] == 'CE1597M-protected-fixed-reference'
    assert argv[argv.index('--candidate-label') + 1] == 'CE1741M-production-profile06-next8M'
    r1, e1 = cohort(job['R1'], 'R1', 70, 'CE1597M-protected-fixed-reference-01', REFERENCE,
                    [1597432474, 6585181, 25397106688])
    r2, e2 = cohort(job['R2'], 'R2', 68, 'CE1597M-protected-fixed-reference-02', REFERENCE,
                    [1597432474, 6585181, 25397106688])
    c1, ec = cohort(job['C1'], 'C1', 65, 'CE1741M-production-profile06-next8M-01', CANDIDATE,
                    [1741229950, 7128160, 27621148672])
    assert not ({r['journal_game_id'] for r in r1} & {r['journal_game_id'] for r in r2})
    assert not ({r['journal_game_id'] for r in r1 + r2} & {r['journal_game_id'] for r in c1})
    reference_scores = [r['score'] for r in r1 + r2]
    candidate_scores = [r['score'] for r in c1]
    assert len(reference_scores) == 138 and len(candidate_scores) == 65
    ref_mean = Fraction(sum(reference_scores), 138)
    ref_median = median_fraction(reference_scores)
    threshold = ref_mean * Fraction(21, 20)
    c1_mean = Fraction(sum(candidate_scores), 65)
    c1_median = median_fraction(candidate_scores)
    fixed = dict(count=138, score_sum=sum(reference_scores), mean=float(ref_mean),
                 median=float(ref_median), mean_exact=fraction(ref_mean),
                 median_exact=fraction(ref_median), required_confirmation_mean=float(threshold),
                 required_confirmation_mean_exact=fraction(threshold),
                 required_confirmation_median=float(ref_median),
                 derivation='All original full R1 and R2 score rows concatenated; no averaged cohort means or medians.',
                 original_reference_membership=[dict(role=role, journal_game_id=r['journal_game_id'], score=r['score'])
                     for role, rows in [('R1', r1), ('R2', r2)] for r in rows])
    conditional = dict(count=65, mean=float(c1_mean), median=float(c1_median),
                       relative_mean_change_percent=float((c1_mean / ref_mean - 1) * 100),
                       mean_at_least_105_percent=c1_mean >= threshold,
                       median_preserved=c1_median >= ref_median,
                       numerical_conditions_met=c1_mean >= threshold and c1_median >= ref_median,
                       scope='Conditional numerical comparison only; original final scientific validity and separate C2 confirmation remain required.',
                       scientific_validity_confirmed=False, quality_qualified=False)
    result = dict(schema='robotron-fixed-fresh-reference-conditional-C1-original-derivation-v1',
                  status='FIXED_FRESH_R1_R2_ALL138_REFERENCE_AND_CONDITIONAL_C1_MATH_DERIVED',
                  source=pin(__file__), original_job=job_pin, observed_unix_s=time.time(),
                  reference_sha256=REFERENCE, candidate_sha256=CANDIDATE,
                  original_R1=e1, original_R2=e2, original_C1=ec,
                  fixed_fresh_reference=fixed, conditional_C1=conditional,
                  candidate_results_pooled=False, historical_reference_rows_used=False,
                  original_attempt=1, no_retry=True, scientific_reviewer_or_terminal_auditor_rerun=False,
                  live_runtime_or_scientific_input_changed=False, full_original_four_leg_audit_still_required=True,
                  C2_confirmation_still_required=True, quality_qualified=False, promotion=False,
                  learning_speed_gain_verified=False)
    out = put(OUTPUT, result)
    print(json.dumps(dict(status=result['status'], receipt=out,
                         fixed_reference={k: v for k, v in fixed.items() if k != 'original_reference_membership'},
                         conditional_C1=conditional)))


if __name__ == '__main__':
    main()
