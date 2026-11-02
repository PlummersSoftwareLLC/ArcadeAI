"""Derive startup-clock constraints from already archived R1 prefixes only.

Inert unless --derive is supplied. No live files, emulators, model imports,
scientific reviewers, clocks, or current evaluation controls are touched.
"""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path


ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = ROOT / 'logs/managed-learning-20261015/run-26'
QUALITY = RUN / 'quality32-reference1597-vs-production1741-original01-preparation-20261021'
EVIDENCE = QUALITY / 'R1-original-first-completed-game-independent-readback.json'
EVIDENCE_SHA = '0172f56fda8548b324575e83801c90dcb7ed2f5ceb6284fe88c906f24f1dc094'
OUTPUT = RUN / 'post-quality-startup-research-reconciliation-original01-20261021/current-R1-attachment-clock-constraints-original01.json'


def pin(path):
    path = Path(path)
    s = path.stat()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                bytes=s.st_size, identity=dict(device=s.st_dev, inode=s.st_ino,
                bytes=s.st_size, mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(s.st_mode & 0o777), uid=s.st_uid, nlink=s.st_nlink))


def checked(expected):
    path = Path(expected['path'])
    before = pin(path)
    assert before == expected and before['identity']['mode'] == '0o444'
    data = path.read_bytes()
    assert pin(path) == before
    return data


def derive():
    assert not OUTPUT.exists(), 'Distinct derivation already exists; do not rerun'
    parent = pin(EVIDENCE)
    assert parent['sha256'] == EVIDENCE_SHA
    e = json.loads(checked(parent))
    assert e['status'] == 'ORIGINAL_R1_FIRST_MEASURED_COMPLETE_GAME_PREFIX_JOINS_PASS'
    games_pin = e['original_games']['readonly_copy']
    status_pin = e['original_status']['readonly_copy']
    games = [json.loads(line) for line in checked(games_pin).splitlines()]
    status = json.loads(checked(status_pin))
    initial = sorted((r for r in games if r['start_reason'] == 'initial_attachment'),
                     key=lambda r: r['client_slot'])
    assert [r['client_slot'] for r in initial] == list(range(4096, 4128))
    assert len({r['journal_game_id'] for r in initial}) == 32
    start = status['start_ts']
    assert start == 1792625906.514471
    assert status['close_ts'] == start + 5400
    for r in initial:
        assert r['start_unix_s'] < start
        assert r['known_start'] is False and r['eligible'] is False
        assert r['excluded_reason'] == 'startup_attachment'
        assert r['measurement_active'] is True and r['measurement_generation'] == 1
        assert r['first_play_level'] == 1 and r['complete'] is True
        assert r['start_frame']['level'] == 0 and r['start_frame']['score'] == 0
        assert r['start_frame']['player_alive'] is True
        assert r['start_frame']['lives'] == 255 and r['start_frame']['raw_reserves'] == 0
    package = json.loads(checked(e['source_package']))
    # Source references are extracted from the same fixed runtime package.
    # Keep full-file pins and exact AST locations for independent inspection.
    source_facts = []
    base = ROOT / 'tools/quality_capacity_proposal/profile06/Robotron'
    assert package['root'] == str(base) and package['source_count'] == 123
    for relative, wanted in [
        ('tools/run_frozen_sidecar.py', ['run']),
        ('Scripts/dqn/managed_measurement.py', ['enter', 'tick']),
        ('Scripts/dqn/socket_server.py', ['_sync_measurement_boundary', 'measurement_boundary_status']),
        ('Scripts/dqn/game_journal.py', ['_begin']),
    ]:
        p = base / relative
        ppin = pin(p)
        raw = checked(ppin)
        assert package['files'][relative] == ppin['sha256']
        tree = ast.parse(raw)
        nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name in wanted]
        if relative.endswith('run_frozen_sidecar.py'):
            # The outer entry function may be called execute/run; locate the
            # actual function owning the fixed controller.enter/fleet.launch.
            nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and b'controller.enter(job.label' in b'\n'.join(raw.splitlines()[n.lineno-1:n.end_lineno])]
        assert nodes
        source_facts.append(dict(relative=relative, source=ppin,
            functions=[dict(name=n.name, line=n.lineno, end_line=n.end_lineno,
                ast_sha256=hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest())
                for n in nodes]))
    rows = [dict(client_slot=r['client_slot'], journal_game_id=r['journal_game_id'],
                 attachment_unix_s=r['start_unix_s'],
                 attachment_lead_before_admission_s=start-r['start_unix_s'],
                 excluded_initial_completion_unix_s=r['end_unix_s'],
                 excluded_initial_completion_after_admission_s=r['end_unix_s']-start)
            for r in initial]
    output = dict(schema='robotron-current-R1-attachment-clock-constraints-v1',
        status='ARCHIVED_ALL32_PRE_ADMISSION_ATTACHMENT_CONSTRAINTS_DERIVED',
        source=pin(__file__), parent_original_readback=parent,
        original_prefixes=[games_pin, status_pin], source_package=e['source_package'],
        source_functions=source_facts, original_fixed_admission_start_unix_s=start,
        rows=rows, slots=32,
        interpretation=[
            'All32 archived initial attachments were timestamped before the unchanged admission start; none can enter this cohort by changing known_start alone.',
            'All32 first wire frames report alive with wave0/lives255/raw reserves0. Generic player_alive before authenticated START1 is not proof of initialized play.',
            'All32 later reach first-play wave1 and complete, but their first game remains conservatively excluded; these fields do not certify an original first-game start.',
            'The fixed controller enters measurement before launching actors, then opens admission only after all32 boundary acknowledgments. A future startup certificate must explicitly address that ordering.',
            'A future protocol can stage an authenticated START1 until a prospective all-slot admission barrier, or reject any certificate before that barrier. Neither choice is implemented or selected.',
        ], limitations=[
            'Attachment and completion times are journal host observations, not authenticated START1/initialization host times.',
            'This is one current reference leg, not independent trials or a proven evaluation-speed gain.',
            'Loaded-ROM/player-field, before-play and host-clock certificate evidence remains missing.',
        ], runtime_changed=False, original_games_relabelled=False,
        scientific_review_rerun=False, new_probe_or_CPU_test_launched=False,
        protocol_selected=False, quality_qualified=False, learning_speed_gain_verified=False)
    assert not OUTPUT.exists()
    with OUTPUT.open('xb') as stream:
        stream.write(json.dumps(output, separators=(',', ':'), allow_nan=False).encode())
        stream.flush()
        os.fsync(stream.fileno())
    OUTPUT.chmod(0o444)
    print(json.dumps(pin(OUTPUT)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--derive', action='store_true')
    args = parser.parse_args()
    if args.derive:
        derive()
