"""Offline startup observations only; never launch, import game code or admit games."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import time

GAME = Path(__file__).resolve().parents[2]
RUN = GAME / "logs/managed-learning-20261015/run-26"
LIMIT = 8 * 1024 * 1024


def identity(path):
    s = path.stat()
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(s.st_mode & 0o7777), uid=s.st_uid, nlink=s.st_nlink)


def stable_bytes(path):
    before = identity(path)
    if before['bytes'] > LIMIT:
        raise ValueError('Input exceeds bounded offline read')
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT or identity(path) != before:
        raise ValueError('Input changed during read')
    return raw, dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                     bytes=len(raw), identity=before)


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def decode(raw):
    def constant(value):
        raise ValueError('Nonfinite JSON: ' + value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=constant)


def publish(directory, name, raw):
    path = directory / name
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    retained, entry = stable_bytes(path)
    if retained != raw:
        raise ValueError('Published bytes differ')
    return entry


def retain(directory, name, path):
    raw, original = stable_bytes(path)
    copied = publish(directory, name, raw)
    if stable_bytes(path)[1] != original:
        raise ValueError('Original changed after exact copy')
    return raw, dict(original=original, copy=copied)


def startup_sequences(raw):
    if not raw or not raw.endswith(b'\n'):
        raise ValueError('Historical event log has incomplete final line')
    by_slot = defaultdict(list)
    for row_number, line in enumerate(raw.splitlines()):
        row = decode(line)
        slot = row['slot']
        if type(slot) is not int or not 4096 <= slot < 4112:
            raise ValueError('Unexpected historical actor slot')
        by_slot[slot].append((row_number, row))
    if set(by_slot) != set(range(4096, 4112)):
        raise ValueError('Historical slot coverage changed')
    result = []
    keys = ('wave', 'raw_reserves', 'alive', 'done', 'start_pressed',
            'classifier_new_game')
    for slot, events in sorted(by_slot.items()):
        if any(b[1]['unix_s'] < a[1]['unix_s'] for a, b in zip(events, events[1:])):
            raise ValueError('Historical per-slot clock moved backward')
        found = next(((i, n, row) for i, (n, row) in enumerate(events)
                      if row['score'] == 0 and row['wave'] == 1
                      and type(row['raw_reserves']) is int
                      and 0 < row['raw_reserves'] < 10 and row['alive'] is False), None)
        if found is None:
            raise ValueError('No initial wave-one inactive observation')
        index, line_number, row = found
        before = [event for _, event in events[:index]]
        result.append(dict(
            slot=slot, zero_based_original_line=line_number,
            observed_delay_s=row['unix_s'] - events[0][1]['unix_s'],
            classifier_new_game=row['classifier_new_game'],
            preceding_start_pulse=any(x['start_pressed'] is True for x in before),
            preceding_wave_above81=any(x['wave'] > 81 for x in before),
            preceding_reserves99=any(x['raw_reserves'] == 99 for x in before),
            preceding_alive_non_wave1=any(x['alive'] is True and x['wave'] != 1 for x in before),
            last_six_preceding_events_and_observation=[
                dict(zero_based_original_line=n, **{k: x[k] for k in keys})
                for n, x in events[max(0, index - 6):index + 1]]))
    counts = {key: sum(x[key] is True for x in result) for key in (
        'classifier_new_game', 'preceding_start_pulse', 'preceding_wave_above81',
        'preceding_reserves99', 'preceding_alive_non_wave1')}
    return dict(event_rows=sum(len(x) for x in by_slot.values()), actors=len(result),
                observation_counts=counts, per_actor=result)


def run(directory):
    directory = directory.resolve()
    if not directory.is_relative_to(RUN) or directory == RUN:
        raise ValueError('Output must be a new research directory under run-26')
    directory.mkdir(mode=0o755, parents=False, exist_ok=False)
    report = dict(schema='robotron-offline-historical-boot-observations-v1',
                  unix_s=time.time(), sources={}, historical={}, current_R1={})
    source_files = dict(
        analyzer=Path(__file__).resolve(),
        trace_writer=GAME / 'tools/confirmed_game_boundary_proposal/run_real_mame_validation_reviewed2.py',
        lua=GAME / 'tools/quality_capacity_proposal/profile04/Robotron/Scripts/main.lua',
        journal=GAME / 'tools/quality_capacity_proposal/profile04/Robotron/Scripts/dqn/game_journal.py',
        ingest=GAME / 'tools/quality_capacity_proposal/profile04/Robotron/Scripts/dqn/socket_server.py',
        rom_start_source=GAME / 'Code/Williams/RRG23.ASM',
        rom_symbols_source=GAME / 'Code/Williams/RRF.ASM')
    for key, path in source_files.items():
        _, report['sources'][key] = retain(directory, key + '-source.txt', path)
    for role in ('reference', 'integrated-no-fire-up'):
        original = RUN / ('confirmed-game-boundary-real-MAME-' + role + '-original01-20261018')
        raw, events = retain(directory, role + '-original-events.jsonl', original / 'wire-boundary-events.jsonl')
        result_raw, receipt = retain(directory, role + '-original-result.json', original / 'result.json')
        result = decode(result_raw)
        report['historical'][role] = dict(
            events=events, result=receipt,
            historical_reported_status=result.get('status'),
            historical_reported_scope=result.get('scope'), observations=startup_sequences(raw))
    diagnosis = RUN / 'readonly-quality-startup-attachments-original01-20261020'
    raw, retained = retain(directory, 'current-R1-original-games.jsonl', diagnosis / 'original-R1-games.jsonl')
    if hashlib.sha256(raw).hexdigest() != '492b0629b841d59e1cab31aa7146aff525bad699275a7552ed6046df42f62e93':
        raise ValueError('Current R1 original journal differs from closed receipt binding')
    attachments = [decode(line) for line in raw.splitlines()
                   if decode(line).get('excluded_reason') == 'startup_attachment']
    expected = dict(score=0, level=0, player_alive=True, lives=255,
                    start_pressed=False, raw_reserves=0)
    if (len(attachments) != 32
            or {x['client_slot'] for x in attachments} != set(range(4096, 4128))
            or any(x['start_frame'] != expected or x['known_start'] is not False
                   or x['eligible'] is not False for x in attachments)):
        raise ValueError('Current R1 initial-attachment observation changed')
    report['current_R1'] = dict(journal=retained, initial_attachments=32,
        identical_first_attachment_frame=expected, first_play_wave1=32,
        note='First playable wave one alone did not establish original known-start provenance.')
    if any(x['first_play_level'] != 1 for x in attachments):
        raise ValueError('Current R1 first playable wave changed')
    report.update(
        findings=[
            'Both historical traces contain16 initial start sequences each. All32 first wave-one inactive observations follow a start pulse, while classifier_new_game remains false.',
            'Every sequence first includes wave>81, raw reserves99 and alive at a non-wave-one value. These boot values cannot authorize admitting the initial attachment.',
            'The existing journal admits only known starts; a score-zero-to-score-zero startup does not trigger the score-decrease classifier.',
            'The trace writer records signature changes, not every accepted frame; its signature excludes score. There is no accepted-frame ordinal or raw STATUS byte in these event rows.',
            'Lua serializes start intent before applying that frame input. Intent alone is not proof that the ROM accepted start.',
            'Local assembly comments describe STATUS bit7 as game-over. START1 gates on STATUS and credits, initializes reserves/wave; PLSTRT also runs later. Source symbols alone are not a byte-verified observation of the current ROM.'],
        next_required_evidence=[
            'A prospective private diagnostic must capture bounded ordered raw ROM start evidence and accepted-frame/action ordering, including actual start acceptance before wave-one policy play.',
            'Distinguish boot/self-test/attract, insufficient-credit pulses, ordinary respawn, later wave transitions, reconnect and zero-score restart. Missing or contradictory evidence must exclude startup.',
            'Bind actor birth, ROM identity, connection epoch, source, fixed policy and cohort admission time. Startup before admission cannot be retroactively counted.',
            'If a startup barrier or first-game admission rule is proposed, validate it on new isolated CPU contracts and original real ROM runs after the current private study closes. Use identical new protocol for fresh R1/C1/R2/C2.'],
        limitations=[
            'Retrospective mechanism observations only. No historical raw-log checksum was asserted by this analysis before its read; exact retained bytes are bound at observation time.',
            'No original closed scientific review is rerun. Historical reported PASS is not a new independent runtime validation.',
            'No initial attachment is reclassified. No new start protocol, quality qualification, throughput gain or learning-speed improvement is established.'],
        live_runtime_changed=False, protocol_selected=False, scientific_review_rerun=False,
        quality_gain_verified=False, learning_speed_gain_verified=False)
    entry = publish(directory, 'historical-boot-sequence-independent-readback.json',
                    (json.dumps(report, indent=2, allow_nan=False) + '\n').encode())
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps(dict(readback=entry,
        historical_actor_sequences=sum(x['observations']['actors'] for x in report['historical'].values()),
        current_R1_initial_attachments=len(attachments), protocol_selected=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.execute:
        if args.output is None:
            parser.error('--output required')
        run(args.output)
    else:
        print('PLAN_ONLY: no file reads, writes, model imports, emulator or service actions')
