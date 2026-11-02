"""Inactive independent quota64 journal audit; NOT selected by a runtime.

Reconstruct first-two membership from original raw starts, without consulting
outcomes. Existing confirmed-terminal, ROM, startup, life and statistics checks
remain unchanged. Actual scoped guards and integration remain outstanding.
"""
GAMES_PER_SLOT = 1
ACTOR_COUNT = 64
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SLOTS = tuple(range(4096, 4096 + ACTOR_COUNT))
COHORT_SELECTION = dict(schema='robotron-fixed-slot64-selection-v1', strategy='first_known_start_per_declared_slot', actor_slots=list(SLOTS), games_per_slot=GAMES_PER_SLOT, expected_games=64, minimum_complete_games=50, outer_start_horizon_s=21540, whole_cohort_timeout_from_enter_s=21600, timestamp_close_role='outer_start_horizon', selector_source_sha256='2e8d0aa660686875a87c8d44f5978b9dcfb60d07ac179080724f760e4ccc01fd')
MODE = 'confirmed_reset_reserves_v1'
DEPENDENCIES = ((G / 'tools/quality_capacity_proposal/profile06/Robotron/tools/confirmed_terminal_evidence.py', '56ef66f08c2fc476a552584f2f2ba1eef909c1ea291df585ee35e629ccae8b8a'), (G / 'tools/confirmed_game_boundary_proposal/audit_confirmed_completed_leg_reviewed3.py', 'de901669780868cb842e9c9068ce11261a1d1f359c1940bb5bba6b2646c37ade'))

def require(value, message):
    if not value:
        raise ValueError(message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, 'Invalid original ' + name)
    return value

def number(value, name):
    require(type(value) in (int, float) and math.isfinite(value), 'Invalid original ' + name)
    return value

def decode(raw):

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate original JSON key')
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError('Nonfinite original JSON value')
    result = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    require(type(result) is dict, 'Original JSON object required')
    return result

def lines(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 256 * 1024 * 1024 and raw.endswith(b'\n'), 'Complete bounded original JSONL required')
    rows = []
    for line in raw.splitlines():
        require(0 < len(line) <= 1024 * 1024, 'Original JSONL row bound differs')
        rows.append(decode(line))
    return rows

def indexed(rows, name):
    result = {}
    for row in rows:
        identifier = row.get('journal_game_id')
        require(type(identifier) is str and bool(identifier) and (identifier not in result), 'Missing/duplicate original ' + name + ' journal ID')
        result[identifier] = row
    return result

def dependencies():
    modules = []
    for path, sha in DEPENDENCIES:
        require(hashlib.sha256(path.read_bytes()).hexdigest() == sha, 'Original terminal predicate source changed')
        name = '_full_tail_games_predicate_' + str(len(sys.modules))
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == sha, 'Terminal predicate changed during import')
        modules.append(module)
    require('torch' not in sys.modules, 'Journal review imported numerical runtime')
    return modules

def context_policy(context, policy):
    require(type(context) is dict and context.get('measurement_active') is True and (type(context.get('measurement_generation')) is int) and (context['measurement_generation'] == policy['measurement_generation']) and (context.get('experiment') == policy['experiment']) and (type(context.get('difficulty')) is int) and (context['difficulty'] == 5), 'Original journal frozen context changed')
    for key in ('epsilon', 'expert_ratio'):
        require(number(context.get(key), key) == 0, 'Original journal is not greedy')
    for key, loaded in [('learner_frames', 'learner_frame_count'), ('training_steps', 'training_steps'), ('optimized_samples', 'optimized_samples')]:
        require(integer(context.get(key), key) == policy[loaded], 'Original journal loaded clocks changed')

def original_ordinal(row):
    key = row.get('journal_game_id')
    require(type(key) is str, 'Missing original occurrence ID')
    prefix, separator, ordinal = key.rpartition(':')
    require(separator and prefix.isascii() and prefix.isdecimal() and (int(prefix) > 0) and ordinal.isascii() and ordinal.isdecimal() and (int(ordinal) > 0) and (str(int(ordinal)) == ordinal), 'Malformed original occurrence ID')
    return (prefix, int(ordinal))

def select_original_starts(rows, experiment, start_ts, close_ts, *, source_is_start_order):
    """Independent raw-byte selection; never read score/eligibility/completion."""
    candidates = [row for row in rows if row['experiment'] == experiment]
    occurrences = [original_ordinal(row) for row in candidates]
    require(len({prefix for prefix, _ in occurrences}) <= 1, 'Mixed original journal runs')
    if not source_is_start_order:
        candidates = sorted(candidates, key=lambda row: original_ordinal(row)[1])
    previous = 0
    counts = {slot: 0 for slot in SLOTS}
    selected = {}
    outside = []
    for row in candidates:
        _, ordinal = original_ordinal(row)
        require(ordinal > previous, 'Original known-start occurrence order changed')
        previous = ordinal
        require(row['known_start'] is row['measurement_active'] is True, 'Raw start is not a known measurement start')
        slot = integer(row['client_slot'], 'original slot', 4096)
        require(slot in SLOTS, 'Foreign original slot')
        timestamp = number(row['start_unix_s'], 'original start time')
        key = row['journal_game_id']
        if start_ts <= timestamp <= close_ts and counts[slot] < GAMES_PER_SLOT:
            selected[key] = row
            counts[slot] += 1
        else:
            outside.append(key)
    return (selected, counts, outside)

def review(payloads, cohort, policy, window, certified):
    """Review original closed bytes; certified joins must come from raw startup audit.

    All64 selected full games and all32 slot quotas are mandatory. The minimum
    floor remains50 and separate candidate confirmations remain outside this module.
    """
    require(set(payloads) == {'games.jsonl', 'measurement_starts.jsonl', 'lives.jsonl'}, 'All original game/start/life bytes required')
    terminals, rom = dependencies()
    game_rows = lines(payloads['games.jsonl'])
    start_rows = lines(payloads['measurement_starts.jsonl'])
    life_rows = lines(payloads['lives.jsonl'])
    games = indexed(game_rows, 'game')
    starts = indexed(start_rows, 'start')
    require(cohort['closed'] is cohort['complete'] is cohort['valid'] is True and cohort['pending'] == cohort['abandoned'] == 0 and (not cohort['pending_ids']) and (not cohort['abandoned_ids']) and (not cohort['abandonment_reasons']), 'Original cohort is not completely drained and valid')
    require(cohort['experiment'] == policy['experiment'] == window['experiment'] and policy['measurement_generation'] == window['generation'] and (int(cohort['start_ts'] * 1000000000.0) == window['open_unix_ns']) and (int(cohort['close_ts'] * 1000000000.0) == window['close_unix_ns']) and (window['close_unix_ns'] - window['open_unix_ns'] == 21540000000000), 'Original outer start horizon differs')
    require(canonical(policy.get('cohort_selection')) == canonical(COHORT_SELECTION), 'Original certificate policy does not bind quota64 selection and bounds')
    require(cohort['schema'] == 'robotron-fixed-slot64-cohort-status-v1' and cohort['admission_mode'] == COHORT_SELECTION['strategy'] and (cohort['timestamp_close_role'] == 'outer_start_horizon') and (cohort['closed_by'] == 'slot_quota') and (cohort['all_slot_quotas_admitted'] is True) and (cohort['expected_games'] == 64) and (cohort['games_per_slot'] == GAMES_PER_SLOT) and (cohort['minimum_complete_games'] == 50), 'Original quota64 cohort descriptor differs')
    admitted, quotas, outside_starts = select_original_starts(start_rows, policy['experiment'], cohort['start_ts'], cohort['close_ts'], source_is_start_order=True)
    require(quotas == {slot: GAMES_PER_SLOT for slot in SLOTS} and cohort['slot_admitted_counts'] == {str(slot): GAMES_PER_SLOT for slot in SLOTS} and (cohort['started_ids'] == list(admitted)) and (type(cohort['retained_outside_cohort_ids']) is list) and (outside_starts[:len(cohort['retained_outside_cohort_ids'])] == cohort['retained_outside_cohort_ids']), 'Original first-two quotas or retained extra starts differ')
    rows = indexed(cohort['rows'], 'cohort')
    identifiers = set(admitted)
    require(len(identifiers) == len(cohort['started_ids']) == len(rows) == cohort['count'] == cohort['started'] == 64 and identifiers == set(cohort['started_ids']) == set(rows) and identifiers.issubset(games), 'An admitted original full tail is missing, duplicated or omitted')
    raw_admitted, raw_quotas, raw_outside = select_original_starts([r for r in game_rows if r['known_start'] is True], policy['experiment'], cohort['start_ts'], cohort['close_ts'], source_is_start_order=False)
    require(set(raw_admitted) == identifiers and raw_quotas == quotas and (set(raw_outside) == set(outside_starts)), 'Original starts/games first-two registries disagree')
    require(set(certified) == set(SLOTS) and cohort['started_actor_slots'] == list(SLOTS) and ({r['client_slot'] for r in rows.values()} == set(SLOTS)), 'Original all32 coverage differs')
    original_cids = {}
    for slot, entry in certified.items():
        require(entry['slot'] == slot and entry['journal_game_id'] in identifiers, 'Original certified start is missing')
        integer(entry['client_id'], 'certified client')
        require(entry['client_id'] not in original_cids.values(), 'Original certified client reused across slots')
        original_cids[slot] = entry['client_id']
        row = games[entry['journal_game_id']]
        certificate = row['start_context'].get('startup_certificate')
        require(type(certificate) is dict and certificate['identifier'] == entry['certificate_identifier'], 'Original certified journal certificate differs')
        body = {k: v for k, v in certificate.items() if k != 'identifier'}
        require(digest(body) == certificate['identifier'] and body['schema'] == 'robotron-prospective-startup-journal-certificate-v2' and (body['policy'] == policy) and (body['admission'] == window) and all((body[k] == entry[k] for k in ('slot', 'session', 'connection', 'nonce'))), 'Original certificate policy/window/subject changed')
        prior = games.get(entry['previous_journal_game_id'])
        require(prior is not None and prior['journal_game_id'] != row['journal_game_id'] and (prior['known_start'] is prior['complete'] is prior['eligible'] is False) and (prior['start_reason'] == 'initial_attachment') and (prior['excluded_reason'] == 'startup_attachment') and (prior['terminal_confirmation'] is None) and ('startup_certificate' not in prior['start_context']) and ('startup_certificate' not in prior['end_context']) and (prior['client_id'] == row['client_id'] == entry['client_id']) and (prior['client_slot'] == row['client_slot'] == slot) and (prior['game_uid'] == row['game_uid'] == entry['game_uid']), 'Unknown original attachment or unchanged ingest UID was rewritten')
        require(row['start_reason'] == 'prospective_certified_first_start_v2', 'Original first start is not prospective certification')
    certified_ids = {r['journal_game_id'] for r in certified.values()}
    require({r['journal_game_id'] for r in start_rows if 'startup_certificate' in r['context']} == certified_ids, 'Unexpected missing or extra startup certificate')
    for key, entry in admitted.items():
        row = games[key]
        require(row == rows[key] and all((entry[k] == row[k] for k in ('client_id', 'client_slot', 'game_uid', 'start_utc', 'start_unix_s', 'start_reason', 'known_start', 'measurement_active', 'measurement_generation', 'start_frame'))) and (entry['context'] == row['start_context']), 'Original admission/outcome/cohort identity differs')
        require(row['known_start'] is row['complete'] is row['eligible'] is row['eval_only'] is row['measurement_active'] is True and row['excluded_reason'] == '' and (row['first_play_level'] == 1) and (row['completion_policy'] == MODE) and (row['client_id'] == original_cids[row['client_slot']]), 'Original completed game is invalid or changed clients')
        require(integer(row['playable_frames'], 'playable frames', 1) <= integer(row['observed_frames'], 'observed frames') and number(row['end_unix_s'], 'end') >= number(row['start_unix_s'], 'start'), 'Original game frames or times differ')
        integer(row['score'], 'score')
        integer(row['deaths'], 'deaths')
        for context in (row['start_context'], row['end_context']):
            context_policy(context, policy)
        require(row['start_context']['complete_game_boundary_policy'] == MODE, 'Original completion policy changed')
        if key not in certified_ids:
            rom.validate_original_context(entry, row)
    successors = terminals.collect_successors(list(rows.values()), game_rows, start_rows)
    terminal_links = [terminals.validate_terminal(row, successors[key]) for key, row in rows.items()]
    rom_links = [rom.validate_rom_terminal(row, successors[key]) for key, row in rows.items()]
    by_life = {key: [] for key in identifiers}
    for life in life_rows:
        if life['journal_game_id'] in by_life:
            by_life[life['journal_game_id']].append(life)
    life_links = []
    for key, row in rows.items():
        lives = by_life[key]
        require([r['life'] for r in lives] == list(range(1, row['deaths'] + 1)), 'Original life/death sequence is missing or duplicated')
        previous_score = 0
        for life in lives:
            require(life['known_game_start'] is life['eval_only'] is True and all((life[k] == row[k] for k in ('client_id', 'client_slot', 'game_uid'))) and (integer(life['playable_frames'], 'life playable frames', 1) > 0), 'Original life belongs to a foreign or unknown game')
            score = integer(life['cumulative_score'], 'life cumulative score')
            require(previous_score <= score <= row['score'] and integer(life['life_score'], 'life score') == score - previous_score, 'Original life scores do not join the same game')
            stamp = datetime.fromisoformat(life['utc'])
            require(stamp.tzinfo is not None and row['start_unix_s'] <= stamp.timestamp() <= row['end_unix_s'], 'Original life timestamp falls outside the game')
            context_policy(life['context'], policy)
            previous_score = score
        life_links.append(dict(journal_game_id=key, verified_lives=len(lives), score=row['score']))
    scores = [row['score'] for row in rows.values()]
    stats = dict(count=len(scores), started=len(scores), mean=statistics.mean(scores), median=statistics.median(scores), sd=statistics.stdev(scores), se=statistics.stdev(scores) / math.sqrt(len(scores)))
    for key, value in stats.items():
        require(math.isclose(number(cohort[key], key), value, rel_tol=1e-12, abs_tol=1e-09), 'Saved cohort statistics differ from all original games')
    return dict(schema='robotron-fixed-slot64-original-quality-journal-review-v1', cohort_selection=COHORT_SELECTION, slot_admitted_counts=quotas, retained_outside_start_ids=outside_starts, status='PASS_ALL_ADMITTED_ORIGINAL_JOURNAL_TERMINALS_ROM_AND_LIVES', admitted_ids=sorted(identifiers), statistics=dict(stats, score_sum=sum(scores)), certified_initial_games=ACTOR_COUNT, original_game_rows=len(game_rows), original_start_rows=len(start_rows), original_life_rows=len(life_rows), terminal_links=terminal_links, rom_links=rom_links, life_links=life_links, original_payload_sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()}, retained_outside_cohort_ids=sorted(set(games) - identifiers), cohort_fingerprint=digest(dict(started_ids=sorted(identifiers), rows=cohort['rows'])), journal_full_tail_verified=True, full_game_score_verified=False, quality_qualified=False, promotion=False, quality_minimum_games_unchanged=50, runtime_policy_source_main_startup_and_release_still_required=True)
