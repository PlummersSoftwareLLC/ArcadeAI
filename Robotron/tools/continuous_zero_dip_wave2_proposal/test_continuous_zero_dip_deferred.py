"""UNEXECUTED CPU-only regressions for one prospective classifier predicate.

The author has not parsed, compiled, imported or executed target/test code.
Future tests reconstruct the unapplied candidate in memory. One test generates
a private source package under root's explicit ignored-log work directory and
runs the actual v2 parser, complete handler and GameJournal with MemoryWire and
dummy inference. No real socket, checkpoint, model instance, replay or MAME.
"""
import ast
import copy
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]
RUN = GAME/'logs/managed-learning-20261015/run-26'
OLD = '        and (int(frame.game_score) > 0 or not recent_start)\n'
NEW = ('        and (int(frame.game_score) > 0 or not recent_start\n'
       '             or int(frame.level_number) >= 2)\n')
SOURCE_SHA = 'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed'
WIRE = GAME/'tools/game_boundary_diagnostics_proposal/wire_integration_validation/test_wire_integration.py'
CLASSIFIER = GAME/'tools/game_boundary_diagnostics_proposal/activation_bound_revision/test_game_boundary_diagnostics.py'


def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(pin):
    """Read only the exact sealed source/closed-metadata inputs in the lock."""
    path = Path(pin['path'])
    require(path.is_absolute() and path.suffix not in ('.pt', '.pth'), 'Source/metadata only')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read((4 << 20)+1)
        after = os.fstat(stream.fileno())
    def identity(info):
        return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
            mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
            mode=oct(info.st_mode & 0o777), uid=info.st_uid, nlink=info.st_nlink)
    require(identity(before) == identity(after) == identity(path.lstat()) == pin['identity']
        and len(raw) == pin['bytes'] <= 4 << 20 and digest(raw) == pin['sha256'],
        'Fixed source/metadata changed: '+str(path))
    return raw


def inputs():
    manifest = json.loads((HERE/'preparation-manifest.json').read_text())
    entries = manifest['files'] + manifest['upstreams']
    pins = {entry['path']: entry for entry in entries}
    require(len(pins) == len(entries), 'Duplicate manifest path')
    for entry in manifest['files']:
        checked(entry)
    return manifest, pins


def source_pair(pins):
    before = checked(pins[str(GAME/'Scripts/dqn/socket_server.py')]).decode()
    require(digest(before.encode()) == SOURCE_SHA and before.count(OLD) == 1,
            'Exact held f44 predicate required')
    after = before.replace(OLD, NEW)
    require(after.replace(NEW, OLD) == before, 'Candidate reverse differs')
    expected = ''.join(difflib.unified_diff(before.splitlines(keepends=True),
        after.splitlines(keepends=True), fromfile='a/Robotron/Scripts/dqn/socket_server.py',
        tofile='b/Robotron/Scripts/dqn/socket_server.py'))
    require(checked(pins[str(HERE/'unapplied.patch')]).decode() == expected,
            'Unapplied patch differs from exact one-predicate reconstruction')
    return before, after


def load_source_module(pin, name):
    """Only future root execution reaches these authenticated stdlib helpers."""
    checked(pin)
    specification = importlib.util.spec_from_file_location(name, pin['path'])
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def classify(module, source, *, previous=9900, score=0, wave=2, previous_wave=2,
             age=274, alive=True, previous_alive=True, done=False, start=False):
    owner = module.server(True, raw_score_prev=previous, raw_wave_prev=previous_wave,
        frames=204073, last_start_frame=204073-age, player_alive=previous_alive,
        game_uid=71, _boundary_previous_accepted=(previous, previous_wave,
            previous_alive, False, False, 3, 204072))
    owner._game_uid_seq = 71
    frame = module.frame(score, wave, alive=alive, done=done, start=start, lives=3)
    result = module.classifier(source)(owner, 7, frame)
    return result, owner, frame


def specs(case):
    """Synthetic trajectory matching saved scalar endpoints, never a RAM replay."""
    # First received frame creates known UID71 at accepted_frames_before203160.
    rows = [dict(score=0, wave=1, alive=False, done=False, start=False, lives=0)]
    rows += [dict(score=9000, wave=1, alive=True, done=False, start=False, lives=3)
             for _ in range(638)]
    # One inactive non-death pulse makes last_start_frame203799. Nothing here
    # asserts which physical event produced the real run's historical pulse.
    rows.append(dict(score=9800, wave=1, alive=False, done=False, start=True, lives=3))
    rows += [dict(score=9900, wave=2, alive=True, done=False, start=False, lives=3)
             for _ in range(273)]
    require(len(rows) == 913, 'Exact bounded accepted-clock prefix')
    if case == 'exact_uid71_72':
        rows += [dict(score=0, wave=2, alive=True, done=False, start=False, lives=3)]
        rows += [dict(score=10000, wave=2, alive=True, done=False, start=False, lives=3)
                 for _ in range(16)]
        rows += [dict(score=10100, wave=2, alive=True, done=False, start=False, lives=3),
                 dict(score=10100, wave=2, alive=False, done=True, start=False, lives=0)]
    elif case == 'valid_wave1_reset':
        rows += [dict(score=0, wave=1, alive=False, done=False, start=False, lives=0),
                 dict(score=100, wave=1, alive=True, done=False, start=False, lives=3),
                 dict(score=700, wave=1, alive=False, done=True, start=False, lives=0)]
    elif case == 'inactive_then_invalid_wave2':
        rows += [dict(score=0, wave=0, alive=False, done=False, start=False, lives=0),
                 dict(score=0, wave=2, alive=True, done=False, start=False, lives=3),
                 dict(score=10100, wave=2, alive=False, done=True, start=False, lives=0)]
    else:
        raise AssertionError('Unknown fixed scenario')
    return rows


def adapted_wire(module, pins):
    """Reuse actual old harness; only its one-admission fixture assumption changes.

    MemoryWire, v2 framing, constructor, complete handle_client, cleanup, action
    assertions and raw journal collection stay real/unchanged. Parser/classifier
    and journal are not stubbed. The returned cohort includes EVERY admission.
    """
    raw = checked(pins[str(WIRE)]).decode()
    tree = ast.parse(raw)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_case')
    text = ast.get_source_segment(raw, node)
    old = '''    require(len(admission) == 1 and admission[0]["client_slot"] == SLOT, "Unexpected actual admission set")
    begin = admission[0]["start_unix_s"]
    cohort = server.game_journal.cohort_status("wire-fixture", begin, begin)
    require(cohort["closed"] and cohort["started"] == 1, "Original toy cohort did not close")'''
    new = '''    require(admission and all(row["client_slot"] == SLOT for row in admission), "Unexpected actual admission set")
    begin, end = admission[0]["start_unix_s"], admission[-1]["start_unix_s"]
    cohort = server.game_journal.cohort_status("wire-fixture", begin, end)
    require(cohort["closed"] and cohort["started"] == len(admission), "Every original admission must remain counted")'''
    require(text.count(old) == 1, 'Original wire harness metadata boundary changed')
    adapted = text.replace(old, new)
    require(adapted.replace(new, old) == text, 'Wire harness adaptation not reversible')
    module.SLOT = 4107
    module.fixture_frames = specs
    exec(compile(adapted, '<private-adapted-original-run_case>', 'exec'), module.__dict__)
    return module.run_case


def private_child(work, variant):
    require(os.environ.get('ROBOTRON_ALLOW_ZERO_DIP_WIRE_TEST') == '1'
        and os.environ.get('CUDA_VISIBLE_DEVICES') == '' and variant in ('baseline', 'candidate'),
        'Explicit CUDA-hidden future CPU execution required')
    require(not any(n in sys.modules for n in ('torch', 'numpy', 'dqn')), 'Fresh child required')
    manifest, pins = inputs()
    before, after = source_pair(pins)
    package = work/'private/Scripts/dqn'
    require(package.is_dir() and work.is_relative_to(RUN), 'Root-owned ignored-log package required')
    expected = manifest['private_package_sources']
    for name, pin in expected.items():
        raw = checked(pin)
        if name == 'socket_server.py' and variant == 'candidate': raw = after.encode()
        require((package/name).read_bytes() == raw, 'Generated private source drift: '+name)
    sys.path.insert(0, str(package.parent))
    import numpy as np
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    require(torch.cuda.device_count() == 0 and not torch.cuda.is_initialized(), 'CUDA available')
    from dqn import config
    from dqn import socket_server as server_module
    require(Path(config.MODEL_DIR) == work/'models' and config.learning_control.path == work/'control/learning_control.json',
            'Import-time control/model paths escaped')
    config.RL_CONFIG.replay_tmpfs_dir = str(work/'tmpfs')
    config.RL_CONFIG.inference_batching_enabled = False
    for key, value in dict(start_advanced=False, start_level_min=1, epsilon_pct=0,
                           expert_pct=0, auto_curriculum=False, difficulty=5).items():
        setattr(config.game_settings, key, value)
    wire = load_source_module(pins[str(WIRE)], '_zero_dip_original_wire')
    run_case = adapted_wire(wire, pins)
    actual_server = server_module.SocketServer
    def seeded_server(*args, **kwargs):
        server = actual_server(*args, **kwargs)
        actual_init = server._init_client
        def seed(cid):
            actual_init(cid)
            server._game_uid_seq = 70
            server.client_states[cid].update(raw_score_prev=991500, raw_wave_prev=35,
                frames=203160, last_start_frame=203153, player_alive=False, game_uid=70,
                _boundary_previous_accepted=(991500, 35, False, False, False, 0, 203159))
        server._init_client = seed
        return server
    results = []
    with patch.object(server_module, 'SocketServer', side_effect=seeded_server), \
            patch.object(subprocess, 'Popen', side_effect=AssertionError('No child subprocess launch')):
        for case in ('exact_uid71_72', 'valid_wave1_reset', 'inactive_then_invalid_wave2'):
            result = run_case(server_module, config, np, work, case, True)
            starts = result['journal']['measurement_starts.jsonl']['rows']
            games = result['journal']['games.jsonl']['rows']
            if case == 'exact_uid71_72':
                require(starts[0]['game_uid'] == 71 and starts[0]['start_frame']['level'] == 1,
                        'Retained game needs a genuine known wave1 start')
                require(games[0]['game_uid'] == 71 and games[0]['first_play_level'] == 1,
                        'Original known game changed')
                if variant == 'baseline':
                    require(len(starts) == 2 and starts[1]['game_uid'] == 72
                        and games[0]['score'] == 9900 and games[0]['boundary_reason'] == 'score_reset'
                        and result['cohort']['abandoned'] == 1
                        and games[1]['excluded_reason'] == 'measurement_start_not_wave_1',
                        'Baseline must reproduce false split and invalid admission')
                    d = starts[1]['context']['game_boundary_diagnostics']
                    require(d['previous_accepted_wire']['accepted_frames_before'] == 204072
                        and d['current_wire']['accepted_frames_before'] == 204073
                        and d['last_start_frame_after'] == 203799 and d['recent_start'] is True,
                        'Exact saved accepted-clock relationships missing')
                else:
                    require(len(starts) == len(games) == 1 and games[0]['score'] == 10100
                        and games[0]['eligible'] is True and games[0]['complete'] is True
                        and games[0]['boundary_reason'] == 'wire_lives_exhausted'
                        and result['cohort']['valid'] is True and result['cohort']['abandoned'] == 0,
                        'Candidate must retain and fully complete the known game')
            elif case == 'valid_wave1_reset':
                require(len(starts) == 2 and starts[1]['start_frame']['level'] == 1
                    and games[1]['eligible'] is True and result['cohort']['abandoned'] == 0,
                    'Genuine inactive wave1 reset changed')
            else:
                require(len(starts) == 2 and result['cohort']['abandoned'] == 1
                    and games[1]['excluded_reason'] == 'measurement_start_not_wave_1',
                    'Inactive reset followed by badwave2 must still invalidate')
            # Preserve decisive real outputs without logging every synthetic frame.
            results.append(dict(case=case, frames=len(result['input_frames']),
                action_count=len(result['actions']), actor_calls=len(result['actor_calls']),
                starts=starts, games=games, cohort=result['cohort'],
                wire_sha256=result['wire_sha256'], no_replay_or_listener=result['no_replay_or_listener']))
    loaded = {}
    for name, module in list(sys.modules.items()):
        if name == 'dqn' or name.startswith(('dqn.', 'v3.')):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(package), 'Module escaped private package: '+name)
            loaded[name] = dict(path=str(path), sha256=digest(path.read_bytes()))
    require(not any('dqn.'+name in sys.modules for name in ('agent', 'training', 'replay_buffer', 'prefetch', 'metrics_dashboard')),
            'Forbidden learner/replay/dashboard imports')
    for name, pin in expected.items():
        original = checked(pin)
        chosen = after.encode() if name == 'socket_server.py' and variant == 'candidate' else original
        require((package/name).read_bytes() == chosen, 'Private source changed after execution')
    require(not torch.cuda.is_initialized(), 'CUDA initialized')
    output = dict(status='PASS', variant=variant, loaded_modules=loaded, cases=results,
        actual_full_handler=True, actual_parser=True, actual_journal=True,
        real_socket_or_model_or_replay_or_MAME=False,
        limits='Synthetic trajectory/MemoryWire/dummy inference and test-only initial scalar seed; not physical RAM or quality proof')
    (work/'result.json').write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')


class ContinuousZeroDipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.pins = inputs()
        cls.before, cls.after = source_pair(cls.pins)
        cls.original = load_source_module(cls.pins[str(CLASSIFIER)], '_zero_dip_original_extractors')

    def test_exact_patch_and_all_other_function_bodies_preserved(self):
        old, new = ast.parse(self.before), ast.parse(self.after)
        def functions(tree):
            return {node.name: ast.dump(node) for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        left, right = functions(old), functions(new)
        self.assertEqual(set(left), set(right))
        self.assertEqual([name for name in left if left[name] != right[name]], ['_continuous_play_score_dip'])

    def test_exact_closed_uid72_scalar_evidence_and_classifier(self):
        m = self.original
        row = next(json.loads(line) for line in checked(self.pins[self.manifest['closed_start_copy']]).splitlines()
                   if json.loads(line).get('game_uid') == 72)
        d = row['context']['game_boundary_diagnostics']
        self.assertEqual((row['client_id'], row['client_slot']), (11, 4107))
        self.assertEqual(d['current_wire']['accepted_frames_before']-d['last_start_frame_after'], 274)
        for source, expected in ((self.before, True), (self.after, False)):
            result, owner, frame = classify(m, source)
            self.assertEqual(result['new_game'], expected)
            self.assertEqual(owner.client_states[7]['game_uid'], 72 if expected else 71)
            self.assertEqual(frame.game_score, 0 if expected else 9900)
            self.assertEqual(result['boundary_inputs'][1],
                (0, 2, True, False, False, 3, 204073))

    def test_wave1_and_actual_reset_or_start_edges_keep_original_semantics(self):
        cases = [dict(wave=1, previous_wave=1), dict(alive=False),
            dict(previous_alive=False), dict(done=True), dict(start=True),
            dict(wave=0), dict(wave=1), dict(previous=100001),
            dict(previous=None, previous_wave=None)]
        for values in cases:
            with self.subTest(values=values):
                a, ao, af = classify(self.original, self.before, **values)
                b, bo, bf = classify(self.original, self.after, **values)
                self.assertEqual(a, b)
                self.assertEqual(ao.client_states, bo.client_states)
                self.assertEqual(vars(af), vars(bf))

    def test_recent_age_tolerance_wrap_and_jump_boundaries(self):
        for wave in (2, 255):
            for age in (0, 274, 299, 300):
                with self.subTest(wave=wave, age=age):
                    result, _, frame = classify(self.original, self.after, wave=wave,
                        previous_wave=wave, age=age, previous=100000)
                    self.assertFalse(result['new_game']); self.assertEqual(frame.game_score, 100000)
        for values in (dict(wave=1, previous_wave=1, age=300),
                       dict(previous=99000000, score=0, age=300),
                       dict(previous=99000000, score=0, age=274),
                       dict(score=260001), dict(previous=100001, score=0),
                       dict(previous=9900, score=9850)):
            with self.subTest(values=values):
                a, ao, af = classify(self.original, self.before, **values)
                b, bo, bf = classify(self.original, self.after, **values)
                self.assertEqual(a, b); self.assertEqual(ao.client_states, bo.client_states)
                self.assertEqual(vars(af), vars(bf))

    def test_private_actual_full_handler_and_journal_baseline_vs_candidate(self):
        require(os.environ.get('ROBOTRON_ALLOW_ZERO_DIP_WIRE_TEST') == '1'
            and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'Explicit future CPU test gate required')
        require(not any(name in sys.modules for name in ('torch', 'numpy', 'dqn')), 'Fresh stdlib parent required')
        root = Path(os.environ['ROBOTRON_ZERO_DIP_TEST_WORK_ROOT']).resolve(strict=True)
        require(root.is_relative_to(RUN), 'Generated packages belong under ignored run26 logs')
        wire = load_source_module(self.pins[str(WIRE)], '_zero_dip_wire_parent')
        for variant in ('baseline', 'candidate'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix='zero-dip-'+variant+'-', dir=root) as temporary:
                work = Path(temporary); package = work/'private/Scripts/dqn'; package.mkdir(parents=True)
                for name, pin in self.manifest['private_package_sources'].items():
                    raw = checked(pin)
                    if name == 'socket_server.py' and variant == 'candidate': raw = self.after.encode()
                    (package/name).write_bytes(raw)
                for name in ('models', 'journal', 'control', 'cache', 'tmpfs'): (work/name).mkdir()
                (work/'models/game_settings.json').write_text('{}\n')
                (work/'control/learning_control.json').write_text('{}\n')
                environment = wire.child_environment(work)
                environment.update(ROBOTRON_ALLOW_ZERO_DIP_WIRE_TEST='1', ROBOTRON_REJECTED_GAP_TELEMETRY='0')
                argv = [sys.executable, '-Xgil=0', '-I', '-B', str(Path(__file__).resolve()), '--private-child', str(work), variant]
                process = subprocess.Popen(argv, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, start_new_session=True)
                try:
                    stdout, stderr = process.communicate(timeout=120)
                except subprocess.TimeoutExpired:
                    process.kill(); stdout, stderr = process.communicate(timeout=15)
                    self.fail('Owned private child timeout/reaped exit%s\n%s\n%s' % (process.returncode, stdout, stderr))
                self.assertEqual(process.returncode, 0, stdout+'\n'+stderr)
                result = json.loads((work/'result.json').read_text())
                self.assertEqual(result['status'], 'PASS'); self.assertEqual(len(result['cases']), 3)
                print(json.dumps(dict(child_argv=argv, exit=process.returncode, stdout=stdout,
                    stderr=stderr, result=result), allow_nan=False))


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--private-child':
        private_child(Path(sys.argv[2]).resolve(strict=True), sys.argv[3])
    else:
        unittest.main()
