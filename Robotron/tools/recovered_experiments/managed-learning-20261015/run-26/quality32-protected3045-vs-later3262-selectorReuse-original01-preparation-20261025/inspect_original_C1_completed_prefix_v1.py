"""Read-only provisional C1 journal consistency; never qualifies a cohort."""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import time
G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).parent
D = N / '02-candidate/diagnostic-output-original01'
MANIFEST_SHA = '27cc0064844e756ba63afd515bdac52de94d046ff57396aa98ad18a7d623845e'
HELPER_SHA = '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
POLICY_SHA = 'df4314b05aceddeec263e598690fe803e32985497a0e26b38f36162452291bb4'

def load(path, name, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    return module

def capture(source, target, h):
    with source.open('rb') as stream:
        info = os.fstat(stream.fileno())
        assert 0 < info.st_size <= 64 << 20
        raw = stream.read(info.st_size)
    if source.suffix == '.jsonl':
        raw = raw[:raw.rfind(b'\n') + 1]
    assert raw
    with target.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 292)
        os.fsync(stream.fileno())
    return dict(snapshot=h.pin(target), original_path=str(source), original_device=info.st_dev, original_inode=info.st_ino, original_bytes_at_open=info.st_size, original_mtime_ns_at_open=info.st_mtime_ns)

def inspect(output):
    h = load(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', '_partial_h', HELPER_SHA)
    manifest_path = N / 'selected-source-family-manifest.json'
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == MANIFEST_SHA
    manifest = json.loads(manifest_path.read_bytes())
    auditor_pin = manifest['games_auditor']
    h.checked(auditor_pin)
    auditor = load(Path(auditor_pin['path']), '_partial_existing_auditor', auditor_pin['sha256'])
    terminals, rom = auditor.dependencies()
    assert output.is_absolute() and output.resolve() == output
    assert output.parent == N and (not output.exists())
    output.mkdir(mode=448)
    producers = []
    for source, name in [(D / 'status.json', 'native-status.raw.json'), (D / 'journal/games.jsonl', 'games-prefix.raw.jsonl'), (D / 'journal/lives.jsonl', 'lives-prefix.raw.jsonl'), (D / 'journal/measurement_starts.jsonl', 'measurement-starts-prefix.raw.jsonl'), (D / 'original-loaded-policy.json', 'loaded-policy.raw.json')]:
        producers.append(capture(source, output / name, h))
    status = json.loads((output / 'native-status.raw.json').read_bytes())
    cohort = status['controller']['cohort']
    assert not status['errors'] and cohort['failure_reason'] is None and (not cohort['abandoned'])
    assert cohort['count'] == len(cohort['rows']) > 0
    assert cohort['pending'] == cohort['started'] - cohort['count']
    policy = json.loads((output / 'loaded-policy.raw.json').read_bytes())['policy']
    assert policy['checkpoint_sha256'] == POLICY_SHA
    assert policy['training_enabled'] is policy['replay_enabled'] is False
    assert policy['epsilon'] == policy['expert_ratio'] == 0

    def lines(name):
        return auditor.lines((output / name).read_bytes())
    game_rows = lines('games-prefix.raw.jsonl')
    life_rows = lines('lives-prefix.raw.jsonl')
    start_rows = lines('measurement-starts-prefix.raw.jsonl')
    games = auditor.indexed(game_rows, 'games')
    starts = auditor.indexed(start_rows, 'starts')
    selected, quotas, outside = auditor.select_original_starts(start_rows, cohort['experiment'], cohort['start_ts'], cohort['close_ts'], source_is_start_order=True)
    ordinals = {}
    by_slot = {}
    for key, row in selected.items():
        slot = row['client_slot']
        by_slot[slot] = by_slot.get(slot, 0) + 1
        ordinals[key] = by_slot[slot]
    checks = []
    for row in cohort['rows']:
        key = row['journal_game_id']
        assert games[key] == row and key in selected and (selected[key] == starts[key])
        assert all((row[field] is True for field in ['known_start', 'complete', 'eligible', 'eval_only', 'measurement_active']))
        assert row['first_play_level'] == 1 and row['excluded_reason'] == ''
        assert terminals.start_record(starts[key]) == terminals.start_record(row)
        successor = terminals.start_record(starts[row['terminal_confirmation']['next_journal_game_id']])
        terminal = terminals.validate_terminal(row, successor)
        rom_terminal = rom.validate_rom_terminal(row, successor)
        for context in [row['start_context'], row['end_context'], successor['context']]:
            auditor.context_policy(context, policy)
        lives = [life for life in life_rows if life['journal_game_id'] == key]
        assert [life['life'] for life in lives] == list(range(1, row['deaths'] + 1))
        previous = 0
        for life in lives:
            assert life['known_game_start'] is life['eval_only'] is True
            assert all((life[field] == row[field] for field in ['client_id', 'client_slot', 'game_uid']))
            assert life['playable_frames'] > 0
            assert previous <= life['cumulative_score'] <= row['score']
            assert life['life_score'] == life['cumulative_score'] - previous
            assert row['start_unix_s'] <= datetime.fromisoformat(life['utc']).timestamp() <= row['end_unix_s']
            auditor.context_policy(life['context'], policy)
            previous = life['cumulative_score']
        life_sum = sum((life['life_score'] for life in lives))
        assert life_sum == previous
        checks.append(dict(journal_game_id=key, slot=row['client_slot'], selected_start_ordinal=ordinals[key], score=row['score'], verified_lives=len(lives), life_score_sum=life_sum, life_score_sum_equals_final_score=life_sum == row['score'], terminal=terminal, ROM_terminal=rom_terminal))
    scores = [row['score'] for row in checks]
    assert statistics.mean(scores) == cohort['mean']
    assert statistics.median(scores) == cohort['median']
    assert 'torch' not in sys.modules
    report = dict(schema='robotron-provisional-original-C1-completed-prefix-review-v1', created_unix_s=time.time(), source=h.pin(__file__), source_manifest=h.pin(manifest_path), established_auditor=auditor_pin, established_terminal_predicates=[h.pin(Path(terminals.__file__)), h.pin(Path(rom.__file__))], inputs=producers, cohort={key: cohort[key] for key in ['count', 'started', 'pending', 'abandoned', 'mean', 'median']}, games=checks, all_completed_rows_match_original_game_and_start_registries=True, all_completed_life_sequences_and_score_increments_verified=True, all_completed_life_score_sums_equal_final_scores=all((row['life_score_sum_equals_final_score'] for row in checks)), limits=['Only captured producer-completed selected games are checked; incomplete games are excluded from this provisional mean.', 'Successor starts are joined to original registry; complete successor game rows may not yet exist.', 'Full cohort/ROM/wire/startup1200/runtime/tail review remains the original scientific reviewer responsibility.', 'Existing life predicate permits final score above last recorded death score; exact-sum equality is reported, not a new scientific gate.'], original_scientific_case_closed=False, reference_mean_final=False, quality_qualified=False, scientific_attempts_started=0, scientific_source_or_runtime_changed=False)
    pin = h.put(output / 'provisional-consistency-report.json', report)
    print(json.dumps(dict(report=pin, cohort=report['cohort'], all_life_score_sums_equal=report['all_completed_life_score_sums_equal_final_scores'])))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.inspect:
        print('PLAN_ONLY: no input reads, imports, launches or qualification')
        return 0
    assert args.output is not None
    inspect(args.output)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
