"""Read-only live-prefix diagnostics. Never qualifies, schedules or controls a case."""
import argparse
import collections
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HELPER_SHA = '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


def descriptor(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(s.st_mode & 511), uid=s.st_uid, nlink=s.st_nlink)


def run(a, h, out):
    job_pin = h.pin(Path(a.job).resolve(strict=True))
    assert job_pin['sha256'] == a.job_sha256
    job = json.loads(h.checked(job_pin).read_bytes())
    assert job['may_control_or_schedule'] is False and job['duration_s'] == 300
    root = Path(job['campaign'])
    folders = {'R1': '01-reference', 'C1': '02-candidate', 'R2': '03-reference', 'C2': '04-candidate'}
    assert folders[job['quality_leg']] == job['leg_folder']
    native = root / job['leg_folder'] / 'diagnostic-output-original01'
    baseline_pin = job.get('preceding_partial_readback', job['previous_readback'])
    baseline = json.loads(h.checked(baseline_pin).read_bytes())
    before_completed = {r['journal_game_id'] for r in baseline.get('all_completed_links', [])}
    outcome_pin = h.pin(Path(job['output']) / 'watch-outcome.json')
    assert outcome_pin['sha256'] == a.watch_outcome_sha256
    outcome = json.loads(h.checked(outcome_pin).read_bytes())
    assert outcome['status'] == 'BOUNDED_PASSIVE_WATCH_COMPLETE' and outcome['error'] is None
    intent = json.loads(h.checked(outcome['intent']).read_bytes())
    assert birth(intent['pid']) is None
    records = [json.loads(h.checked(p).read_bytes()) for p in outcome['observations']]
    assert len(records) == 11 and 300 <= records[-1]['elapsed_s'] <= 310
    samples = []
    for i, record in enumerate(records):
        api = json.loads(h.checked(record['API_raw']).read_bytes())
        assert api['host_pipeline']['learning_exposure'] == record['actual_main_learning_exposure']
        status = json.loads((Path(job['output']) / f'native-status-{i:03d}.json').read_bytes())
        samples.append(status)
        assert all(p['birth'] == p['observed_birth'] for p in record['original_parents'])
        assert 32 <= record['cohort']['started'] <= 64 and record['cohort']['abandoned'] == 0
        if i:
            assert record['raw_health_index'] > records[i - 1]['raw_health_index']
            assert record['cohort']['count'] >= records[i - 1]['cohort']['count']
            assert all(status['slots'][s]['sequence'] > samples[i - 1]['slots'][s]['sequence']
                       for s in status['slots'])
    parents = []
    for p in job['original_parents']:
        assert birth(p['pid']) == p['birth']
        parents.append(dict(**p, observed_birth=birth(p['pid'])))
    ready = json.loads((root / 'new-original-quality-launch-readiness.json').read_bytes())
    aud = load('_partial_selected_auditor', h.checked(ready['games_auditor']))
    terminals, rom = aud.dependencies()
    policy = json.loads((native / 'original-loaded-policy.json').read_bytes())['policy']

    def archive(path, raw):
        with path.open('xb') as f:
            f.write(raw)
            f.flush()
            os.fchmod(f.fileno(), 0o444)
            os.fsync(f.fileno())
        return h.pin(path)

    raw = (native / 'status.json').read_bytes()
    status = json.loads(raw)
    age = time.time() - status['observed_unix_s']
    assert 0 <= age <= 6
    status_pin = archive(out / 'native-status.raw.json', raw)
    cohort = status['controller']['cohort']
    assert cohort['valid'] is True and 32 <= cohort['started'] <= 64 and cohort['abandoned'] == 0
    assert cohort['count'] + cohort['pending'] == cohort['started']
    payloads, prefixes = {}, {}
    for name in ('measurement_starts', 'games', 'lives'):
        path = native / 'journal' / f'{name}.jsonl'
        with path.open('rb') as f:
            before = os.fstat(f.fileno())
            assert 0 < before.st_size <= 256 * 1024 * 1024
            raw = f.read(before.st_size)
            after = os.fstat(f.fileno())
        assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
        assert after.st_size >= before.st_size and path.stat().st_ino == before.st_ino
        stop = raw.rfind(b'\n') + 1
        assert stop > 0
        pin = archive(out / f'{name}-prefix.raw.jsonl', raw[:stop])
        prefixes[name] = dict(archive=pin, producer=str(path), descriptor_before=descriptor(before),
                              descriptor_after=descriptor(after), retained_prefix_bytes=stop,
                              unparsed_trailing_bytes=len(raw) - stop, producer_still_open=True)
        payloads[name] = aud.lines(raw[:stop])
    starts = aud.indexed(payloads['measurement_starts'], 'starts')
    games = aud.indexed(payloads['games'], 'games')
    rows = aud.indexed(cohort['rows'], 'completed cohort')
    selected = set()
    outside = []
    admitted_counts = {}
    for slot in range(4096, 4128):
        own = [r for r in payloads['measurement_starts'] if r['client_slot'] == slot
               and r['known_start'] is True and r['experiment'] == policy['experiment']]
        assert len(own) >= 1
        admitted_counts[str(slot)] = min(2, len(own))
        selected.update(r['journal_game_id'] for r in own[:2])
        outside.extend(r['journal_game_id'] for r in own[2:])
    assert selected == set(cohort['started_ids'])
    assert cohort['slot_admitted_counts'] == admitted_counts
    by_life = collections.defaultdict(list)
    for life in payloads['lives']:
        by_life[life['journal_game_id']].append(life)

    def check_lives(key, identity, final=None):
        lives = by_life[key]
        assert [r['life'] for r in lives] == list(range(1, len(lives) + 1))
        previous = 0
        for life in lives:
            assert life['known_game_start'] is life['eval_only'] is True
            assert all(life[k] == identity[k] for k in ('client_id', 'client_slot', 'game_uid'))
            assert type(life['playable_frames']) is int and life['playable_frames'] > 0
            score = aud.integer(life['cumulative_score'], 'life cumulative score')
            assert score >= previous and aud.integer(life['life_score'], 'life score') == score - previous
            stamp = datetime.datetime.fromisoformat(life['utc']).timestamp()
            assert identity['start_unix_s'] <= stamp
            if final is not None:
                assert stamp <= final['end_unix_s'] and score <= final['score']
            aud.context_policy(life['context'], policy)
            previous = score
        return lives, previous

    links = []
    for key, row in rows.items():
        assert key in selected and games[key] == row
        assert terminals.start_record(row) == terminals.start_record(starts[key])
        assert row['known_start'] is row['complete'] is row['eligible'] is row['eval_only'] is True
        assert row['excluded_reason'] == '' and row['first_play_level'] == 1 and row['completion_policy'] == aud.MODE
        for context in (row['start_context'], row['end_context']):
            aud.context_policy(context, policy)
        successor = terminals.start_record(starts[row['terminal_confirmation']['next_journal_game_id']])
        terminal = terminals.validate_terminal(row, successor)
        rom_terminal = rom.validate_rom_terminal(row, successor)
        lives, score = check_lives(key, row, final=row)
        assert len(lives) == row['deaths'] and score == row['score'] == sum(r['life_score'] for r in lives)
        links.append(dict(journal_game_id=key, slot=row['client_slot'], score=row['score'],
                          duration_s=row['duration_s'], life_count=len(lives), life_score_sum=score,
                          terminal=terminal, ROM_terminal=rom_terminal, successor_start_retained=True,
                          successor_game_row_retained=successor['journal_game_id'] in games))
    assert before_completed.issubset(rows)
    scores = [r['score'] for r in rows.values()]
    assert len(scores) == cohort['count'] and statistics.mean(scores) == cohort['mean']
    assert statistics.median(scores) == cohort['median']
    progress = []
    for key in cohort['pending_ids']:
        lives, score = check_lives(key, starts[key])
        progress.append(dict(journal_game_id=key, slot=starts[key]['client_slot'],
                             completed_life_rows=len(lives), completed_life_cumulative_score=score))
    actors = []
    for slot, row in status['slots'].items():
        assert birth(row['pid']) == row['birth'] and row['error'] is None and row['ledger']['rejected'] == 0
        actor = json.loads((native / f'actors/{slot}/original-actor.json').read_bytes())
        argv = Path('/proc', str(row['pid']), 'cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
        assert argv == actor['argv']
        actors.append(dict(slot=int(slot), pid=row['pid'], birth=row['birth'], argv_verified=True))
    native_job = json.loads((root / job['leg_folder'] / 'job.json').read_bytes())
    assert len(native_job['inputs']) == 244
    for pin in native_job['inputs']:
        h.checked(pin)
    main = json.loads(subprocess.check_output(['/usr/bin/python3.12', '-I', '-B',
                      h.checked(job['main_monitor'])], text=True, timeout=25))
    main_pin = h.put(out / 'current-main.json', main)
    report = dict(schema='robotron-private-live-leg-partial-journal-diagnostics-v2', quality_leg=job['quality_leg'], created_unix_s=time.time(),
                  diagnostic_source=h.pin(__file__), diagnostic_argv=sys.argv, job=job_pin, baseline=baseline_pin,
                  watch_outcome=outcome_pin, passive_tool_exit_supplied=a.original_watch_tool_exit,
                  passive_process_absent=True, observations_verified=11, original_parents_live=parents,
                  original_actors_live=actors, scientific_held_inputs_verified=244, current_main=main_pin,
                  raw_health_index_span=[records[0]['raw_health_index'], records[-1]['raw_health_index']],
                  following_native_status=status_pin, following_native_status_age_at_read_s=age,
                  following_raw_prefixes=prefixes, selected_auditor=ready['games_auditor'],
                  terminal_dependency_pins=[h.pin(p) for p, _ in aud.DEPENDENCIES],
                  following_cohort={k: cohort[k] for k in ('count', 'started', 'pending', 'abandoned', 'mean', 'median', 'valid')},
                  all_completed_links=links, new_completed_links=[r for r in links if r['journal_game_id'] not in before_completed],
                  current_pending_life_prefixes=progress, retained_outside_selected_start_ids=outside,
                  prospective_first_two_membership_reconstructed=True, first_two_starts_per_slot_reconstructed=True,
                  limitations=['Live append-only prefixes are not closed final journals.',
                               'Per-row terminal checks use original measurement-start successors. Final reconciliation in both original journals, full tails, wire and runtime audits remain mandatory.',
                               'Completed-life score changes exclude the current life and are not final game scores or remaining-life counts.'],
                  scientific_sources_or_recipe_changed=False, journal_full_tail_verified=False,
                  full_game_score_verified=False, quality_qualified=False, policy_promoted=False,
                  throughput_gain_verified=False, learning_speed_gain_verified=False)
    assert 'torch' not in sys.modules
    pin = h.put(out / 'readback.json', report)
    print(json.dumps(dict(report=pin, cohort=report['following_cohort'],
                          new_completed=len(report['new_completed_links']),
                          pending_life_prefixes_checked=len(progress))), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inspect', action='store_true')
    p.add_argument('--job')
    p.add_argument('--job-sha256')
    p.add_argument('--source-sha256')
    p.add_argument('--watch-outcome-sha256')
    p.add_argument('--original-watch-tool-exit', type=int)
    a = p.parse_args()
    if not a.inspect:
        print('PLAN_ONLY: no reads, imports, scheduling or control')
        return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == a.source_sha256
    assert a.original_watch_tool_exit == 0
    helper_path = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(helper_path.read_bytes()).hexdigest() == HELPER_SHA
    h = load('_partial_diagnostic_helpers', helper_path)
    out = Path(a.job).resolve(strict=True).parent / 'independent-partial-journal-readback-original01'
    out.mkdir(mode=0o700)
    try:
        run(a, h, out)
    except Exception as error:
        pin = h.put(out / 'passive-diagnostic-failure.json', dict(
            classification='PASSIVE_DIAGNOSTIC_FAILURE_NOT_A_NATIVE_OUTCOME', error=repr(error),
            traceback=traceback.format_exc(), original_handle_outcome_inferred=False,
            source=h.pin(__file__), argv=sys.argv, created_unix_s=time.time()))
        print(json.dumps(dict(failure=pin)), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
