"""One passive completed-R2 receipt/membership join; default invocation is inert.

Never invokes the scientific reviewer or terminal/ROM auditor. Run once only
after the original R2 evaluator exited0 and its same campaign advanced to C2.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import statistics
import subprocess
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
Q = R / 'quality32-reference1597-vs-production1741-original01-preparation-20261021'
C = R.parent / 'quality-reference1597M-vs-production1741M-profile06-quality32-original01-20261021'
D = Q / 'R2-original-completed-receipt-readback-original01'
OUTPUT = Q / 'R2-original-completed-receipt-independent-readback.json'
REFERENCE = 'c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path):
    path = Path(path)
    before = identity(path.stat())
    raw = path.read_bytes()
    assert identity(path.stat()) == before
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), identity=before)


def read(entry):
    assert entry['identity']['mode'] == '0o444' and pin(entry['path']) == entry
    raw = Path(entry['path']).read_bytes()
    assert pin(entry['path']) == entry
    return json.loads(raw)


def put(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    return pin(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-once', action='store_true')
    if not parser.parse_args().read_once:
        return
    assert not OUTPUT.exists() and not D.exists(), 'Original readback scope already consumed'
    parent_pin = pin(Q / 'R2-closed-admissions-reader-original-result.json')
    assert parent_pin['sha256'] == 'ba9fd29d53d49c903d454f0ecbc3ad53d1408ba7943cc382ac005096a5f2015b'
    parent = read(parent_pin)
    assert parent['original_exit'] == 0 and parent['no_retry'] is True
    membership_pin = parent['independent_readback']
    membership = read(membership_pin)
    assert membership_pin['sha256'] == 'c739a157363ea6d439b1ad632a65e9fa1dd6fa2529bdd8fe4cac3c62b9a3bd87'
    assert membership['status'] == 'ORIGINAL_R2_FIXED_CLOSED_ADMISSION_MEMBERSHIP_PREFIX_JOIN_PASS'
    ids = set(membership['joined_snapshot_ids'])
    assert len(ids) == 68 and membership['admission_membership_frozen'] is True
    registration_pin = pin(Q / 'root-live-monitor-registration.json')
    assert registration_pin['sha256'] == 'eb746aafd3d9197dc8ca5e7a0b0891583224645d4d737962178e2239e3a705a8'
    registration = read(registration_pin)
    observed = subprocess.run(registration['command'], capture_output=True)
    assert observed.returncode == 0, observed.stderr.decode()
    monitor = json.loads(observed.stdout)
    assert monitor['classification'] == 'LIVE_SUPERVISED_QUALITY32_PREFIX_VERIFIED'
    assert all(o['live'] for o in monitor['original_owners']) and monitor['current_leg'] >= 4
    assert monitor['legs'][-1]['live_actor_births_verified'] == 32
    leg = monitor['legs'][2]
    assert leg['index'] == 3 and leg['role'] == 'reference'
    assert leg['original_record_state'] == 'finished' and leg['verified_actor_births'] == 32
    assert leg['live_actor_births_verified'] == 0
    assert leg['counts'] == dict(count=68, started=68, pending=0, abandoned=0)
    D.mkdir(mode=0o700)

    def capture(path, name, *, stable=True):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            before = identity(os.fstat(stream.fileno()))
            assert before['uid'] == os.getuid() and before['nlink'] == 1
            assert before['bytes'] <= 32 << 20
            raw = stream.read(before['bytes'])
            after = identity(os.fstat(stream.fileno()))
            assert len(raw) == before['bytes']
            stream.seek(0)
            assert stream.read(len(raw)) == raw
            if stable:
                assert before == after
            else:
                assert (before['device'], before['inode']) == (after['device'], after['inode'])
        return raw, dict(original_path=str(path), observed_before=before,
            observed_after=after, byte_range=[0, len(raw)],
            readonly_copy=put(D / name, raw), original_prefix_reread_identical=True,
            original_producer_modified_by_reader=False)

    raw, campaign_evidence = capture(C / 'status.json', 'original-campaign-status.snapshot.json', stable=False)
    campaign = json.loads(raw)
    record = campaign['legs'][2]
    assert record['index'] == 3 and record['role'] == 'reference'
    assert record['state'] == 'finished' and record['returncode'] == 0 and record['pid'] == 1721309
    assert record['receipt_path'] == str(C / '03-reference/receipt.json')
    raw, receipt_evidence = capture(C / '03-reference/receipt.json', 'original-R2-receipt.readonly.json')
    receipt = json.loads(raw)
    assert receipt['valid'] is True and receipt['complete'] is True
    assert receipt['phase'] == 'finished' and receipt['active'] is False
    assert receipt['checkpoint_sha256'] == REFERENCE and receipt['receipt_validator'] == 'passed'
    assert receipt['invalidity_reasons'] == [] and receipt['cleanup_errors'] == []
    assert receipt['label'] == 'CE1597M-protected-fixed-reference-02'
    cohort = receipt['cohort']
    assert cohort['closed'] is True and cohort['complete'] is True
    assert cohort['start_ts'] == 1792640903.198065 and cohort['close_ts'] == 1792646303.198065
    assert cohort['count'] == cohort['started'] == receipt['count'] == 68
    assert cohort['pending'] == cohort['abandoned'] == receipt['pending'] == receipt['abandoned'] == 0
    rows = receipt['rows']
    assert rows == cohort['rows'] and len(rows) == 68
    assert {row['journal_game_id'] for row in rows} == set(cohort['started_ids']) == ids
    assert {row['client_slot'] for row in rows} == set(range(4096, 4128))
    assert set(cohort['started_actor_slots']) == set(range(4096, 4128))
    raw_games, games_evidence = capture(C / '03-reference/journal/games.jsonl', 'original-R2-games.readonly.jsonl')
    raw_starts, starts_evidence = capture(C / '03-reference/journal/measurement_starts.jsonl', 'original-R2-starts.readonly.jsonl')
    assert raw_games.endswith(b'\n') and raw_starts.endswith(b'\n')
    assert receipt['terminal_journal_sha256'] == {
        'games.jsonl': hashlib.sha256(raw_games).hexdigest(),
        'measurement_starts.jsonl': hashlib.sha256(raw_starts).hexdigest()}
    games = [json.loads(line) for line in raw_games.splitlines()]
    starts = [json.loads(line) for line in raw_starts.splitlines()]
    original_games = {row['journal_game_id']: row for row in games}
    original_starts = {row['journal_game_id']: row for row in starts}
    assert len(original_games) == len(games) and len(original_starts) == len(starts)
    assert {row['journal_game_id'] for row in starts
            if cohort['start_ts'] <= row['start_unix_s'] <= cohort['close_ts']} == ids
    for row in rows:
        uid = row['journal_game_id']
        assert original_games[uid] == row
        assert row['complete'] is True and row['eligible'] is True and row['known_start'] is True
        assert row['first_play_level'] == 1 and row['measurement_generation'] == 1 and row['measurement_active'] is True
        assert row['experiment'] == receipt['label']
        start = original_starts[uid]
        assert start['start_unix_s'] == row['start_unix_s'] and start['client_slot'] == row['client_slot']
        assert start['client_id'] == row['client_id'] and start['game_uid'] == row['game_uid']
        assert start['known_start'] is True and start['measurement_active'] is True and start['measurement_generation'] == 1
        assert start['context'] == row['start_context']
        for context in [row['start_context'], row['end_context']]:
            assert context['learner_frames'] == 1597432474
            assert context['training_steps'] == 6585181 and context['optimized_samples'] == 25397106688
            assert context['epsilon'] == context['expert_ratio'] == 0 and context['difficulty'] == 5
            assert context['measurement_active'] is True and context['measurement_generation'] == 1
        assert type(row['score']) is int and row['score'] >= 0
    scores = [row['score'] for row in rows]
    mean, median = statistics.mean(scores), statistics.median(scores)
    assert receipt['mean'] == cohort['mean'] == mean
    assert receipt['median'] == cohort['median'] == median
    result = dict(status='ORIGINAL_R2_COMPLETED_RECEIPT_ALL68_MEMBERSHIP_AND_STATISTICS_JOIN_PASS',
        source=pin(__file__), observed_unix_s=time.time(), original_monitor_report=monitor['receipt'],
        original_closed_admission_result=parent_pin, original_fixed_membership=membership_pin,
        original_campaign_status=campaign_evidence, original_receipt=receipt_evidence,
        original_games=games_evidence, original_starts=starts_evidence,
        all68_admitted_IDs_joined=True, all32_completed_slot_coverage=True,
        count=68, mean=mean, median=median, pending=0, abandoned=0,
        original_R2_exit=0, original_R2_evaluator_and_actor_births_released=True,
        full_terminal_and_ROM_audit_still_required=True,
        scope='One completed reference leg only. Statistics describe all68 original R2 games. The fixed fresh R1+R2 statistics must be computed once from both original full reference row sets. Final original four-leg scientific/ROM/runtime review and both independent C1/C2 confirmation gates remain required.',
        scientific_reviewer_or_terminal_auditor_rerun=False, runtime_changed=False,
        quality_qualified=False, promotion=False, learning_speed_gain_verified=False)
    entry = put(OUTPUT, (json.dumps(result, indent=2) + '\n').encode())
    print(json.dumps(dict(status=result['status'], receipt=entry,
                         count=68, mean=mean, median=median)))


if __name__ == '__main__':
    main()
