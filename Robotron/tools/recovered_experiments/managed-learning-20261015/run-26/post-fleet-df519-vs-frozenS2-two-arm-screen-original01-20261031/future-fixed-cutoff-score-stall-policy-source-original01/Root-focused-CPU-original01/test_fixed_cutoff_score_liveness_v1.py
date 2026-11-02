"""Root-only focused pure CPU checks; no gameplay, models, APIs, or live controls."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
K = SOURCE.parent
B = K.parent
RESULTS = []


def pin(path):
    raw = path.read_bytes()
    s = path.stat()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
        identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns, mode=oct(s.st_mode & 0o7777),
        uid=s.st_uid, nlink=s.st_nlink))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reject(label, fn, errors=(ValueError, KeyError)):
    try:
        fn()
    except errors:
        RESULTS.append(label)
        return
    raise AssertionError('Invalid case accepted: ' + label)


def main():
    assert sys.argv[1:] == ['--execute']
    packet = json.loads((SOURCE / 'prepared-matched-fixed-cutoff-private-score-stall-policy-SOURCE-ONLY-v1.json').read_text())
    for entry in [*packet['selected_sources'].values(), *packet['unchanged_source_evidence'].values()]:
        assert pin(Path(entry['path'])) == entry
    native_path = Path(packet['selected_sources']['runtime']['path'])
    native = load(native_path, '_Root_fixed_cutoff_liveness_under_test')
    job = json.loads((K / 'R1/job.json').read_text())
    job.update(packet['future_Root_job_additions'])
    job['output'] = str(HERE / 'native-runtime-must-remain-absent')
    selection = json.loads((K / 'Root-prospective-newer-policy-vs-frozenS2-selection.json').read_text())
    selection.update(packet['future_Root_selection_additions'])
    selected_path = HERE / 'synthetic-selected-context.json'
    selected_path.write_text(json.dumps(selection) + '\n')
    selected_path.chmod(0o444)
    job['screen_selection'] = pin(selected_path)
    helpers = native.parent().helpers()
    native.validate_job(job)
    context = native.validate_completed_context(job, helpers)
    assert len(context['modules']) == 12 and 'torch' not in sys.modules
    RESULTS.append('actual valid job and selection, 12 components and frozen source package')
    for label, key, value in [('boolean server timeout', 'private_score_stall_timeout_s', False),
            ('nonzero server timeout', 'private_score_stall_timeout_s', 120),
            ('boolean Lua timeout', 'private_lua_score_stall_timeout_s', True),
            ('old Lua timeout', 'private_lua_score_stall_timeout_s', 180)]:
        bad = copy.deepcopy(job)
        bad[key] = value
        reject(label, lambda bad=bad: native.validate_job(bad))
    bad = copy.deepcopy(job)
    del bad['private_score_stall_timeout_s']
    reject('missing declared server timeout', lambda: native.validate_job(bad))
    bad = copy.deepcopy(job)
    bad['lua']['sha256'] = '1' * 64
    reject('wrong Lua identity', lambda: native.validate_job(bad))
    for number, (label, change) in enumerate([
            ('selection boolean timeout', lambda x: x.update(private_score_stall_timeout_s=False)),
            ('selection old Lua timeout', lambda x: x.update(private_lua_score_stall_timeout_s=180)),
            ('selection runtime mismatch', lambda x: x['private_protocol_sources']['runtime'].update(sha256='2' * 64)),
            ('selection Lua mismatch', lambda x: x['private_protocol_sources']['lua'].update(sha256='3' * 64))]):
        changed = copy.deepcopy(selection)
        change(changed)
        path = HERE / ('synthetic-invalid-selection-' + str(number) + '.json')
        path.write_text(json.dumps(changed) + '\n')
        path.chmod(0o444)
        bad = copy.deepcopy(job)
        bad['screen_selection'] = pin(path)
        reject(label, lambda bad=bad: native.validate_completed_context(bad, helpers))

    server_path = Path(packet['unchanged_source_evidence']['private_socket_server']['path'])
    tree = ast.parse(server_path.read_bytes())
    matches = []
    for node in ast.walk(tree):
        for field, body in ast.iter_fields(node):
            if not isinstance(body, list):
                continue
            for index, child in enumerate(body[:-1]):
                if isinstance(child, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_stall_s' for t in child.targets):
                    assert isinstance(body[index + 1], ast.If)
                    matches.append([child, body[index + 1]])
    assert len(matches) == 1
    branch = compile(ast.fix_missing_locations(ast.Module(body=matches[0], type_ignores=[])), str(server_path) + '::actual-score-watchdog', 'exec')
    def watchdog(timeout, now, score=1083050):
        cs = dict(stall_score=1083050, stall_t0=0.0)
        scope = dict(RL_CONFIG=SimpleNamespace(client_stall_timeout_s=timeout),
            frame=SimpleNamespace(game_score=score), cs=cs, time=SimpleNamespace(time=lambda: now))
        exec(branch, scope)
        return cs
    reject('parent120 rejects unchanged accepted score at121s', lambda: watchdog(120, 121), (ConnectionError,))
    for when in (121, 3600, 4200):
        assert watchdog(0, when)['stall_score'] == 1083050
    assert watchdog(120, 500, 1083100) == dict(stall_score=1083100, stall_t0=500)
    native_tree = ast.parse(native_path.read_bytes())
    overrides = [n for n in ast.walk(native_tree) if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == 'client_stall_timeout_s' for t in n.targets)]
    assert len(overrides) == 1
    fake_config = SimpleNamespace(RL_CONFIG=SimpleNamespace(client_stall_timeout_s=120))
    exec(compile(ast.fix_missing_locations(ast.Module(body=overrides, type_ignores=[])), str(native_path) + '::actual-private-override', 'exec'), dict(config=fake_config, job=job))
    assert fake_config.RL_CONFIG.client_stall_timeout_s == 0
    RESULTS.append('actual private override and server branch allow unchanged scores through4200s; parent branch and score-change path checked')

    recorder = context['modules']['recorder']
    fixture = load(B / 'future-S2-two-arm-quality-screen-source-original01-20261030/test_completed_firstgame_cutoff_contracts_v1.py', '_Root_existing_pure_member_sample_fixtures')
    fixture.MODULUS = 100000000
    clock = [10_000_000_000]
    rec = recorder.DeadlineScoreRecorder(clock_ns=lambda: clock[0])
    for slot in recorder.SLOTS:
        rec.bind(slot, fixture.member(slot))
        rec.observe(slot, fixture.sample(slot, clock[0], score=0))
    clock[0] += recorder.HORIZON_NS
    for slot in recorder.SLOTS:
        rec.observe(slot, fixture.sample(slot, clock[0], sequence=1202, before=10, score=0))
    rec._fresh(clock[0])
    assert all(value['score'] == 0 for value in rec._scores.values())
    RESULTS.append('actual recorder accepts all32 unchanged zero scores after3600s with fresh accepted first-game witnesses')
    slot = recorder.SLOTS[0]
    score_stamp = rec._scores[slot]['score_observed_ns']
    rec._scores[slot]['score_observed_ns'] -= recorder.MAX_AGE_NS + 1
    reject('stale pending score witness', lambda: rec._fresh(clock[0]))
    rec._scores[slot]['score_observed_ns'] = score_stamp
    activity_stamp = rec._last_packets[slot]['completed_exchange_ns']
    rec._last_packets[slot]['completed_exchange_ns'] -= recorder.MAX_AGE_NS + 1
    reject('stale unfinished activity', lambda: rec._fresh(clock[0]))
    rec._last_packets[slot]['completed_exchange_ns'] = activity_stamp
    member = rec._members.pop(slot)
    reject('missing member', lambda: rec._fresh(clock[0]))
    rec._members[slot] = member
    valid = fixture.sample(slot, clock[0], sequence=1203, before=11, score=0)
    for label, key, value in [('wrong first-game UID', 'origin_game_uid', slot + 100000),
            ('wrong frozen policy', 'policy_sha256', '2' * 64),
            ('invalid unwrapped carry', 'score_offset', 1)]:
        bad = copy.deepcopy(valid)
        bad[key] = value
        reject(label, lambda bad=bad: rec.observe(slot, bad))

    lua = Path(packet['selected_sources']['lua']['path']).read_bytes()
    old_lua = Path(json.loads((K / 'R1/job.json').read_text())['lua']['path']).read_bytes()
    assert old_lua.count(b'STALL_EXIT_SECS = 180') == 1
    assert lua == old_lua.replace(b'STALL_EXIT_SECS = 180', b'STALL_EXIT_SECS = 4260', 1)
    assert 4260 > job['wall_limit_s'] and 4260 > job['horizon_ns'] / 1e9 + job['startup_limit_s']
    assert not Path(job['output']).exists() and 'torch' not in sys.modules
    RESULTS.append('Lua exact single timeout substitution beyond bounded run; completed STOP code untouched')
    result = dict(status='PASS_FOCUSED_PRIVATE_FIXED_CUTOFF_CPU_CONTRACTS', actual_exit=0,
        checks=RESULTS, checks_count=len(RESULTS), groups=4, torch_imported=False,
        Main_or_fleet_API_or_proc_access=False, model_tensor_loaded=False,
        CUDA_initialized=False, native_gameplay_launched=False,
        sources=packet['selected_sources'], scope='Actual typed native context gates, actual AST-extracted server watchdog/private override, actual recorder, exact Lua text; synthetic accepted-frame data only.')
    with (HERE / 'report.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(dict(status=result['status'], groups=4, checks=len(RESULTS))), flush=True)


if __name__ == '__main__':
    main()
