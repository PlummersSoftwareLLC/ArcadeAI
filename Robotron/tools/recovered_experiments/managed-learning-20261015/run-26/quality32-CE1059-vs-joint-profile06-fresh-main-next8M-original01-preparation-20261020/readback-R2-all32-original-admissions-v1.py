"""Passive all32 original R2 admissions; every startup partial stays excluded."""
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
OUTPUT = HERE/'R2-all32-original-admission-prefixes'


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
    spec = importlib.util.spec_from_file_location('_R2_all32_start_evidence', source)
    cohorts = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cohorts
    spec.loader.exec_module(cohorts)
    game, backend, helpers, auditor = cohorts.dependencies()
    terminal = __import__(backend.__package__+'.confirmed_terminal_evidence', fromlist=['start_record'])
    status_raw, status_capture = capture(CAMPAIGN/'03-reference/status.json')
    starts_raw, starts_capture = capture(CAMPAIGN/'03-reference/journal/measurement_starts.jsonl', complete_lines=True)
    games_raw, games_capture = capture(CAMPAIGN/'03-reference/journal/games.jsonl', complete_lines=True)
    status = json.loads(status_raw)
    starts = [json.loads(line) for line in starts_raw.splitlines()]
    games = [json.loads(line) for line in games_raw.splitlines()]
    admitted = [row for row in starts if row['experiment'] == status['label']
        and row['known_start'] is True and row['measurement_active'] is True
        and row['measurement_generation'] == status['generation']
        and status['start_ts'] <= row['start_unix_s'] <= status['close_ts']]
    assert admitted and status['phase'] == 'collecting'
    assert set(status['cohort']['started_ids']) <= {row['journal_game_id'] for row in admitted}
    assert status['checkpoint_sha256'] == '4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
    slots = set(range(4096,4128))
    actors_path = HERE/'runtime-bindings/leg-births/leg3-actors.json'
    actors = json.loads(actors_path.read_bytes())
    assert set(actors) == {str(slot) for slot in slots}
    assert status['boundary']['acknowledged'] == 32
    assert set(status['boundary']['acknowledged_client_ids']) == set(range(32))
    assert set(status['boundary']['actor_slots']) == slots
    assert len({row['journal_game_id'] for row in starts}) == len(starts)
    first_by_slot, clients_by_slot = {}, {}
    for row in admitted:
        slot = row['client_slot']
        assert slot in slots
        first_by_slot.setdefault(slot,row)
        clients_by_slot.setdefault(slot,set()).add(row['client_id'])
        context = row['context']
        assert context['epsilon'] == context['expert_ratio'] == 0 and context['difficulty'] == 5
        assert context['learner_frames'] == 1059300354 and context['training_steps'] == 4538417
        assert context['optimized_samples'] == 17013561344
    assert set(first_by_slot) == slots
    assert all(len(clients)==1 for clients in clients_by_slot.values())
    assert {next(iter(clients)) for clients in clients_by_slot.values()} == set(range(32))
    checks = []
    for slot in sorted(slots):
        first = first_by_slot[slot]
        preceding = [row for row in games if row.get('terminal_confirmation',{}).get('next_journal_game_id') == first['journal_game_id']]
        assert len(preceding) == 1
        previous = preceding[0]
        assert previous['client_slot'] == slot and previous['client_id'] == first['client_id']
        assert previous['known_start'] is False and previous['eligible'] is False
        assert previous['excluded_reason'] == 'startup_attachment'
        assert first['context']['game_boundary_diagnostics'] == previous['terminal_confirmation']['ingest_boundary_inputs']
        projected = terminal.start_record(first)
        reset = terminal.validate_terminal(previous,projected)
        rom = auditor.validate_rom_terminal(previous,projected)
        checks.append(dict(slot=slot,client_id=first['client_id'],first_original_admission=first['journal_game_id'],preceding_excluded_startup=previous['journal_game_id'],original_ingest_context_match=True,selected_reset=reset,independent_ROM_reset_predicate=rom))
    startup_rows = [row for row in games if not row['known_start']]
    assert len(startup_rows) == 32
    assert all(row['eligible'] is False and row['excluded_reason']=='startup_attachment' for row in startup_rows)
    assert 'torch' not in sys.modules
    report = dict(schema='robotron-profile06-R2-all32-original-admissions-v1',
        observed_unix_s=time.time(), source=pin(Path(__file__)), evidence_source=pin(source),
        status=status_capture, starts_prefix=starts_capture, games_prefix=games_capture,
        captured_status_counts={key:status[key] for key in ('started','count','pending','abandoned')},
        all_original_admission_ids=[row['journal_game_id'] for row in admitted], all32_first_admission_checks=checks, original_actor_registry=pin(actors_path), admitted_rows_checked=len(admitted), excluded_original_startup_rows=len(startup_rows),
        startup_game_eligible=False, startup_game_counted=False,
        all32_selected_reset_and_independent_ROM_checks_passed=True,
        same_original_terminal_and_next_start_ingest_context=True,
        completed_known_start_game=False, full_closed_journal_cohort_validation_still_required=True,
        quality_qualified=False, promotion=False, source_or_runtime_changed=False)
    result = write(HERE/'R2-all32-original-admissions-prefix-readback.json',
        (json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(dict(readback=result, admitted_rows_checked=len(admitted), all32_slots_checked=True, startup_game_counted=False, quality_qualified=False)))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe', action='store_true')
    args = parser.parse_args()
    if args.observe:
        main()
