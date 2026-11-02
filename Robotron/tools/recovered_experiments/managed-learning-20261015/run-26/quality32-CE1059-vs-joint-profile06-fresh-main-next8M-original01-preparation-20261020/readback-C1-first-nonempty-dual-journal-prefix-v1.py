"""Passive C1 first nonempty original dual-journal prefix; no cohort qualification."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = Path(__file__).resolve().parent
CAMPAIGN = GAME/'logs/managed-learning-20261015/quality-CE1059M-vs-joint-profile06-fresh-next8M-quality32-trial01-20261020'
OUTPUT = HERE/'C1-first-nonempty-dual-journal-prefixes'


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def pin(path):
    raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                identity=identity(path.stat()))


def write(path, raw):
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o664)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o444)
    return pin(path)


def capture(path, *, complete_lines=False):
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read()
        if complete_lines:
            raw = raw[:raw.rfind(b'\n')+1]
        stream.seek(0)
        assert stream.read(len(raw)) == raw
        after = os.fstat(stream.fileno())
        assert all(getattr(before,key) == getattr(after,key)
                   for key in ('st_dev','st_ino','st_mode','st_uid','st_nlink'))
    return raw, dict(original_path=str(path), identity_before=identity(before),
        identity_after=identity(after), prefix_bytes=len(raw),
        prefix_sha256=hashlib.sha256(raw).hexdigest(), stable_prefix_reread=True,
        archive=write(OUTPUT/path.name, raw))


def main():
    assert not OUTPUT.exists()
    OUTPUT.mkdir()
    source = GAME/'tools/quality_capacity_proposal/audit_quality32_evidence_v4.py'
    assert pin(source)['sha256'] == 'f07ccdd098cbf879c7ff98ef26e92e525b7a0ea951c38641fa2b5c0571fa50e3'
    spec = importlib.util.spec_from_file_location('_C1_first_dual_journal_evidence', source)
    cohorts = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cohorts
    spec.loader.exec_module(cohorts)
    game, backend, helpers, auditor = cohorts.dependencies()
    terminal = __import__(backend.__package__+'.confirmed_terminal_evidence', fromlist=['start_record'])
    status_raw, status_capture = capture(CAMPAIGN/'02-candidate/status.json')
    starts_raw, starts_capture = capture(CAMPAIGN/'02-candidate/journal/measurement_starts.jsonl', complete_lines=True)
    games_raw, games_capture = capture(CAMPAIGN/'02-candidate/journal/games.jsonl', complete_lines=True)
    status = json.loads(status_raw)
    starts = [json.loads(line) for line in starts_raw.splitlines()]
    games = [json.loads(line) for line in games_raw.splitlines()]
    registry = auditor.indexed(starts, 'original C1 starts')
    original_games = auditor.indexed(games, 'original C1 games')
    rows = [row for row in games if row['known_start'] is True
        and row['measurement_active'] is True and row['experiment'] == status['label']
        and status['start_ts'] <= row['start_unix_s'] <= status['close_ts']]
    assert rows and status['checkpoint_sha256'] == 'c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'
    available_before_validation = {row['journal_game_id']:row.get('terminal_confirmation',{}).get('next_journal_game_id')
        for row in rows if row.get('terminal_confirmation',{}).get('next_journal_game_id') in original_games}
    assert available_before_validation, 'No original successor game rows available in this prefix'
    checked, available_pairs, pending_pairs = [], [], []
    for row in rows:
        assert row['complete'] is True and row['eligible'] is True
        assert row['measurement_generation'] == status['generation']
        own = registry[row['journal_game_id']]
        assert terminal.start_record(own) == terminal.start_record(row)
        auditor.validate_original_context(own, row)
        for name in ('start_context','end_context'):
            context = row[name]
            assert context['epsilon'] == context['expert_ratio'] == 0 and context['difficulty'] == 5
            assert context['learner_frames'] == 1597432474 and context['training_steps'] == 6585181
            assert context['optimized_samples'] == 25397106688
        identifier = row['terminal_confirmation']['next_journal_game_id']
        successor = terminal.start_record(registry[identifier])
        reset = terminal.validate_terminal(row, successor)
        rom = auditor.validate_rom_terminal(row, successor)
        checked.append(dict(journal_game_id=row['journal_game_id'], own_original_start_context_match=True,
                            selected_reset=reset, independent_ROM_terminal=rom))
        if identifier in original_games:
            terminal.collect_successors([row], games, starts)
            available_pairs.append(dict(game=row['journal_game_id'], successor=identifier))
        else:
            pending_pairs.append(dict(game=row['journal_game_id'], successor=identifier))
    assert {pair['game']:pair['successor'] for pair in available_pairs} == available_before_validation
    assert 'torch' not in sys.modules
    report = dict(schema='robotron-profile06-C1-first-nonempty-dual-journal-prefix-v1',
        observed_unix_s=time.time(), source=pin(Path(__file__)), evidence_source=pin(source),
        status=status_capture, starts_prefix=starts_capture, games_prefix=games_capture,
        captured_status_counts={key:status[key] for key in ('started','count','pending','abandoned')},
        checked_every_eligible_completed_original_row=True, original_completed_rows_checked=len(rows),
        first_completed_eligible_game=rows[0], original_start_reset_ROM_checks=checked,
        available_pairs_chosen_before_validation=available_before_validation,
        all_available_original_successor_pairs_checked=available_pairs,
        successor_game_rows_still_pending=pending_pairs,
        selection='Every original known-start game in the captured fixed-admission prefix; no score filter or fallback.',
        quality_qualified=False, promotion=False, closed_whole_journal_runtime_and_four_leg_gates_still_required=True,
        source_or_runtime_changed=False)
    result = write(HERE/'C1-first-nonempty-original-dual-journal-prefix-readback.json',
        (json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(dict(readback=result, original_completed_rows_checked=len(rows),
                         available_original_successor_pairs=len(available_pairs),
                         pending_successor_game_rows=len(pending_pairs), quality_qualified=False)))


if __name__ == '__main__':
    if sys.argv[1:] == ['--observe']:
        main()
    else:
        print('PLAN_ONLY: passive readback requires --observe after an eligible game completes')
