"""Partition already archived R1 game-journal counters; default is inert.

This distinct descriptive derivation never reads live games, invokes an old
reviewer/test/probe, imports a model, or changes admission or actor lifecycles.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path


G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
Q = R / 'quality32-reference1597-vs-production1741-original01-preparation-20261021'
PARENT = Q / 'R1-original-completed-receipt-independent-readback.json'
OUTPUT = Q / 'R1-closed-journal-observation-budget-original01.json'


def pin(path):
    path = Path(path)
    s = path.stat()
    identity = dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                    mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                    mode=oct(s.st_mode & 0o777), uid=s.st_uid, nlink=s.st_nlink)
    raw = path.read_bytes()
    t = path.stat()
    assert identity == dict(device=t.st_dev, inode=t.st_ino, bytes=t.st_size,
                           mtime_ns=t.st_mtime_ns, ctime_ns=t.st_ctime_ns,
                           mode=oct(t.st_mode & 0o777), uid=t.st_uid, nlink=t.st_nlink)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), identity=identity)


def checked(entry):
    assert pin(entry['path']) == entry and entry['identity']['mode'] == '0o444'
    raw = Path(entry['path']).read_bytes()
    assert pin(entry['path']) == entry
    return raw


def derive():
    assert not OUTPUT.exists(), 'Original descriptive derivation already consumed'
    parent_pin = pin(PARENT)
    assert parent_pin['sha256'] == 'c8792a93e2a371f07b6e7ef32aebae894b31de92ffbf21130a3383699d8f855b'
    parent = json.loads(checked(parent_pin))
    assert parent['status'] == 'ORIGINAL_R1_COMPLETED_RECEIPT_ALL70_MEMBERSHIP_AND_STATISTICS_JOIN_PASS'
    assert parent['count'] == 70 and parent['pending'] == parent['abandoned'] == 0
    membership_pin = parent['original_fixed_membership']
    membership = json.loads(checked(membership_pin))
    assert membership_pin['sha256'] == '27463d0af3430725954a435b629cd730f67db34c42dee4c848e5b52bcb85087d'
    ids = set(membership['joined_snapshot_ids'])
    assert len(ids) == 70
    games_pin = parent['original_games']['readonly_copy']
    raw = checked(games_pin)
    assert len(raw) < 2 << 20 and raw.endswith(b'\n')
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len({row['journal_game_id'] for row in rows}) == len(rows)
    groups = dict(admitted_fixed70=[], initial_attachment=[], known_start_after_close=[])
    start, close = 1792625906.514471, 1792631306.514471
    for row in rows:
        assert row['measurement_active'] is True and row['measurement_generation'] == 1
        assert row['experiment'] == 'CE1597M-protected-fixed-reference-01'
        assert type(row['observed_frames']) is int and row['observed_frames'] >= 0
        if row['journal_game_id'] in ids:
            assert start <= row['start_unix_s'] <= close
            assert row['known_start'] is True and row['complete'] is True and row['eligible'] is True
            groups['admitted_fixed70'].append(row)
        elif row['start_reason'] == 'initial_attachment':
            assert row['known_start'] is False and row['complete'] is True and row['eligible'] is False
            assert row['excluded_reason'] == 'startup_attachment' and row['start_unix_s'] < start
            groups['initial_attachment'].append(row)
        else:
            assert row['known_start'] is True and row['start_unix_s'] > close
            groups['known_start_after_close'].append(row)
    assert {row['journal_game_id'] for row in groups['admitted_fixed70']} == ids
    assert len(groups['initial_attachment']) == 32
    assert {row['client_slot'] for row in groups['initial_attachment']} == set(range(4096, 4128))
    total = sum(row['observed_frames'] for row in rows)
    summaries = {}
    for name, values in groups.items():
        observed = sum(row['observed_frames'] for row in values)
        summaries[name] = dict(journal_game_rows=len(values),
            completed_game_rows=sum(row['complete'] is True for row in values),
            incomplete_game_rows=sum(row['complete'] is False for row in values),
            journal_observed_frames=observed,
            fraction_of_journal_observed_frames=dict(numerator=observed, denominator=total),
            percent_of_journal_observed_frames=100 * observed / total)
    assert sum(value['journal_game_rows'] for value in summaries.values()) == len(rows)
    assert sum(value['journal_observed_frames'] for value in summaries.values()) == total
    result = dict(schema='robotron-closed-R1-journal-observation-budget-v1',
        status='ARCHIVED_R1_OBSERVATION_COUNTER_PARTITION_ONLY_NO_SPEED_GAIN',
        source=pin(__file__), original_completed_R1_readback=parent_pin,
        original_fixed_admission_membership=membership_pin,
        closed_original_games_archive=games_pin, journal_game_rows=len(rows),
        journal_observed_frames=total, groups=summaries,
        research_implications=[
            'Prioritize whether a distinct prospective authenticated first-game certificate can safely improve sample yield; current initial attachments remain excluded.',
            'Separately assess retiring an original actor only after all its admitted tails and required successor evidence are complete. This needs new explicit lifecycle rules and a bounded controlled capacity experiment.',
            'Preserve the fixed fresh reference, independent confirmations, minimum count, all-slot coverage, complete original tails and terminal/ROM/runtime checks in any future protocol.',
        ], limitations=[
            'These are counters in the closed game journal, not an independent count of every emulator frame, GPU action, CPU cycle, joule or wall-clock second.',
            'Initial attachments include uncertified startup observation; they are not certified full games and cannot be relabelled or added to this comparison.',
            'Known starts after close are outside the original fixed membership even when their game rows are complete or eligible by journal-local rules.',
            'No runtime saving, throughput gain, learning-speed gain, causal policy improvement or prospective admissibility follows from these shares.',
            'This is one closed reference leg. Both research directions remain unselected until the active original study has its full disposition and source holds are released.',
        ], old_games_relabelled=False, current_runtime_changed=False,
        original_reviewer_test_or_probe_rerun=False, new_CPU_test_or_probe_launched=False,
        protocol_selected=False, quality_qualified=False, learning_speed_gain_verified=False)
    with OUTPUT.open('xb') as stream:
        stream.write(json.dumps(result, separators=(',', ':'), allow_nan=False).encode())
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(dict(receipt=pin(OUTPUT), groups=summaries,
                         journal_observed_frames=total)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--derive', action='store_true')
    if parser.parse_args().derive:
        derive()
