"""Passive first original C2 known-start readback; startup partial stays excluded."""
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
OUTPUT = HERE/'C2-first-original-admission-prefixes'


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
        assert all(getattr(before, key) == getattr(after, key)
                   for key in ('st_dev','st_ino','st_mode','st_uid','st_nlink'))
    return raw, dict(original_path=str(path), original_identity_before=identity(before),
        original_identity_after=identity(after), prefix_bytes=len(raw),
        prefix_sha256=hashlib.sha256(raw).hexdigest(), stable_prefix_reread=True,
        archive=write(OUTPUT/path.name, raw))


def main():
    assert not OUTPUT.exists()
    OUTPUT.mkdir()
    source = GAME/'tools/quality_capacity_proposal/audit_quality32_evidence_v4.py'
    assert pin(source)['sha256'] == 'f07ccdd098cbf879c7ff98ef26e92e525b7a0ea951c38641fa2b5c0571fa50e3'
    spec = importlib.util.spec_from_file_location('_C2_first_start_evidence', source)
    cohorts = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cohorts
    spec.loader.exec_module(cohorts)
    game, backend, helpers, auditor = cohorts.dependencies()
    terminal = __import__(backend.__package__+'.confirmed_terminal_evidence', fromlist=['start_record'])
    status_raw, status_capture = capture(CAMPAIGN/'04-candidate/status.json')
    starts_raw, starts_capture = capture(CAMPAIGN/'04-candidate/journal/measurement_starts.jsonl', complete_lines=True)
    games_raw, games_capture = capture(CAMPAIGN/'04-candidate/journal/games.jsonl', complete_lines=True)
    status = json.loads(status_raw)
    starts = [json.loads(line) for line in starts_raw.splitlines()]
    games = [json.loads(line) for line in games_raw.splitlines()]
    admitted = [row for row in starts if row['experiment'] == status['label']
        and row['known_start'] is True and row['measurement_active'] is True
        and row['measurement_generation'] == status['generation']
        and status['start_ts'] <= row['start_unix_s'] <= status['close_ts']]
    assert admitted and status['phase'] == 'collecting'
    assert status['checkpoint_sha256'] == 'c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'
    assert set(status['cohort']['started_ids']) <= {row['journal_game_id'] for row in admitted}
    first = admitted[0]
    assert first['journal_game_id'] == '1792546860225994898:33'
    assert first['client_id'] == 18 and first['client_slot'] == 4114 and first['game_uid'] == 33
    preceding = [row for row in games if row.get('terminal_confirmation',{}).get('next_journal_game_id') == first['journal_game_id']]
    assert len(preceding) == 1
    previous = preceding[0]
    assert previous['known_start'] is False and previous['eligible'] is False
    assert previous['excluded_reason'] == 'startup_attachment'
    assert first['context']['game_boundary_diagnostics'] == previous['terminal_confirmation']['ingest_boundary_inputs']
    projected = terminal.start_record(first)
    reset = terminal.validate_terminal(previous, projected)
    rom = auditor.validate_rom_terminal(previous, projected)
    context = first['context']
    assert context['epsilon'] == context['expert_ratio'] == 0 and context['difficulty'] == 5
    assert context['learner_frames'] == 1597432474 and context['training_steps'] == 6585181
    assert context['optimized_samples'] == 25397106688
    assert 'torch' not in sys.modules
    report = dict(schema='robotron-profile06-C2-first-original-eligible-start-v1',
        observed_unix_s=time.time(), source=pin(Path(__file__)), evidence_source=pin(source),
        status=status_capture, starts_prefix=starts_capture, games_prefix=games_capture,
        captured_status_counts={key:status[key] for key in ('started','count','pending','abandoned')},
        first_original_eligible_start=first, preceding_unknown_start_game=previous['journal_game_id'],
        startup_game_eligible=False, startup_game_counted=False,
        selected_reset_mechanics=reset, independent_ROM_reset_predicate=rom,
        same_original_terminal_and_next_start_ingest_context=True,
        completed_known_start_game_validated=False, full_closed_journal_cohort_validation_still_required=True,
        quality_qualified=False, promotion=False, source_or_runtime_changed=False)
    result = write(HERE/'C2-first-original-eligible-start-and-startup-exclusion-readback.json',
        (json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(dict(readback=result, first_admitted_game=first['journal_game_id'],
        client_slot=first['client_slot'], startup_game_counted=False, quality_qualified=False)))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe', action='store_true')
    args = parser.parse_args()
    if args.observe:
        main()
