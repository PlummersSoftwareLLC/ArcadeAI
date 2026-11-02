"""Root-only CPU contracts for selected diagnostic AST, with fake collaborators.

Never imports training/dashboard/Torch or touches GPU, models, API, proc or controls.
Only the actual publication if-block and actual pure API helper are compiled. The
API return-field wiring, lock location, preincrement position and existing CUDA
calls are checked statically. This is not whole-training/dashboard qualification.
"""
import argparse
import ast
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
PACKET = HERE / 'prepared-existing-CUDA-diagnostic-timing-API-SOURCE-ONLY-v1.json'
PACKET_SHA = '293660d4dbb539184d57d3d1d4dc94bf69a2eae48a78061fb7d6f51a315c817a'
DASHBOARD_SHAS = {'159ecffa9250ef4e312faeb64da4c210398d14922a43fa6f4bfcd51d9870a0d5',
                  '9b133ae93eb199ab6b9dc834d7e3879c4f4de2d42dcf07eda1e51b88a8ba2403'}
FIELDS = ('elapsed_ms', 'sample_count', 'logical_training_step', 'observed_unix_s', 'device')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def checked(path, sha, expected=None, sealed=True):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'Canonical source path required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
            and 0 < before.st_size <= 1 << 20 and (not sealed or stat.S_IMODE(before.st_mode) == 0o444),
            'Owned bounded source/metadata required')
    raw = path.read_bytes()
    require(identity(path.lstat()) == identity(before) and len(raw) == before.st_size
            and hashlib.sha256(raw).hexdigest() == sha, 'Source bytes/identity/SHA changed')
    pin = dict(path=str(path), sha256=sha, bytes=len(raw), identity=identity(before))
    if expected is not None:
        require(pin == expected, 'Exact selected source full8 differs')
    return raw, pin


def function(tree, name):
    rows = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    require(len(rows) == 1, 'Unique actual function required: ' + name)
    return rows[0]


def dump(node):
    return ast.dump(node, include_attributes=False)


def cuda_calls(tree):
    return [dump(n) for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and (n.func.attr in ('record', 'elapsed_time', 'query', 'synchronize')
                 or ast.unparse(n.func).startswith('torch.cuda.'))]


def prepare(training, parent_training, dashboard, reference_dashboard):
    t, p, d, r = map(ast.parse, (training, parent_training, dashboard, reference_dashboard))
    train = function(t, '_train_step_impl')
    matches = [n for n in ast.walk(train) if isinstance(n, ast.If)
               and ast.unparse(n.test) == 'gpu_timing is not None'
               and any(isinstance(x, ast.Attribute) and x.attr == 'last_train_gpu_compute_diagnostic'
                       for x in ast.walk(n))]
    require(len(matches) == 1, 'Unique actual completed-diagnostic publication block required')
    block = matches[0]
    increments = [n for n in ast.walk(train) if isinstance(n, ast.AugAssign)
                  and ast.unparse(n.target) == 'agent.training_steps']
    require(len(increments) == 1 and block.end_lineno < increments[0].lineno,
            'Publication must remain before the actual logical-step increment')
    require(cuda_calls(t) == cuda_calls(p), 'Existing CUDA/event record/elapsed/query/sync calls differ')
    restored = copy.deepcopy(t)
    restored_block = [n for n in ast.walk(restored) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == 'gpu_timing is not None'
                      and any(isinstance(x, ast.Attribute) and x.attr == 'last_train_gpu_compute_diagnostic'
                              for x in ast.walk(n))][0]
    require(len(restored_block.body) == 3, 'Exact existing elapsed plus two publication assignments required')
    restored_block.body = restored_block.body[:1]
    require(dump(restored) == dump(p), 'Training differs beyond the selected diagnostic assignments')
    helper = function(d, '_training_gpu_compute_diagnostic')
    snapshot = function(d, '_build_snapshot')
    require(dump(helper) == dump(function(r, '_training_gpu_compute_diagnostic'))
            and dump(snapshot) == dump(function(r, '_build_snapshot')),
            'Selected dashboard changes telemetry helper/snapshot versus reviewed159e')
    assignments = [n for n in ast.walk(snapshot) if isinstance(n, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'gpu_compute_diagnostic' for target in n.targets)]
    expected = ast.parse("gpu_compute_diagnostic = _training_gpu_compute_diagnostic(getattr(self.metrics, 'last_train_gpu_compute_diagnostic', None))").body[0]
    require(len(assignments) == 1 and dump(assignments[0]) == dump(expected), 'API must validate one whole metrics record')
    require(any(isinstance(n, ast.With) and any(ast.unparse(x.context_expr) == 'self.metrics.lock' for x in n.items)
                and any(x is assignments[0] for x in ast.walk(n)) for n in ast.walk(snapshot)),
            'Existing metrics-lock snapshot location changed')
    returns = [n.value for n in ast.walk(snapshot) if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)
               and any(isinstance(k, ast.Constant) and k.value == 'train_gpu_compute_ms' for k in n.value.keys)]
    require(len(returns) == 1, 'Unique actual API return dictionary required')
    fields = {key.value: value for key, value in zip(returns[0].keys, returns[0].values) if isinstance(key, ast.Constant)}
    require(dump(fields['train_gpu_compute_ms']) == dump(ast.parse("gpu_compute_diagnostic['elapsed_ms']", mode='eval').body)
            and dump(fields['train_gpu_compute_diagnostic']) == dump(ast.Name(id='gpu_compute_diagnostic', ctx=ast.Load())),
            'API flat value and diagnostic must share the validated record')
    scopes = {key: ast.literal_eval(fields[key]) for key in ('train_gpu_compute_timing_scope', 'train_transfer_timing_scope')}
    require('not an interval average' in scopes['train_gpu_compute_timing_scope'] and 'unavailable' in scopes['train_transfer_timing_scope'], 'Honest timing scopes required')
    for node in (block, helper):
        require(not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(node)), 'No imports in selected AST')
        require(not any(isinstance(n, ast.Name) and n.id in {'torch', 'os', 'open', 'Path', 'subprocess', 'socket', 'urllib', 'importlib'} for n in ast.walk(node)), 'Forbidden runtime collaborator in selected AST')
    # These are the only selected target-code compilation/execution sites.
    publication = compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(block)], type_ignores=[])), '<actual-diagnostic-publication-AST>', 'exec')
    namespace = {'math': math}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(helper)], type_ignores=[])), '<actual-pure-diagnostic-helper-AST>', 'exec'), namespace)
    return publication, namespace['_training_gpu_compute_diagnostic'], scopes, dict(
        existing_CUDA_call_AST_exact=True, existing_CUDA_calls=len(cuda_calls(t)), training_inverse_whole_module_AST_exact=True,
        actual_preincrement_location=True, helper_and_snapshot_AST_exact_reviewed159e=True,
        API_single_record_lock_and_return_fields_join=True, target_modules_imported=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--dashboard-source', type=Path, required=True)
    parser.add_argument('--dashboard-sha256', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    _, own = checked(Path(__file__).resolve(), args.source_sha256)
    raw, packet_pin = checked(PACKET, PACKET_SHA)
    packet = json.loads(raw)
    training, training_pin = checked(packet['sources']['training']['path'], packet['sources']['training']['sha256'], packet['sources']['training'])
    prior = packet['exact_parent_deltas']['training']['parent']
    parent, parent_pin = checked(prior['path'], prior['sha256'], prior, sealed=False)
    ref = packet['sources']['metrics_dashboard']
    reference, reference_pin = checked(ref['path'], ref['sha256'], ref)
    require(args.dashboard_source.is_relative_to(HERE) and args.dashboard_sha256 in DASHBOARD_SHAS, 'Explicit reviewed private dashboard selection required')
    dashboard, dashboard_pin = checked(args.dashboard_source, args.dashboard_sha256)
    report_path = args.report
    require(report_path.is_absolute() and report_path.parent.parent == HERE and report_path.name == 'report.json'
            and report_path.parent.name.startswith('Root-actual-telemetry-pure-CPU-')
            and report_path.parent.resolve() == report_path.parent and not report_path.parent.exists(), 'Fresh dedicated Root CPU report directory required')
    publication, helper, scopes, static = prepare(training, parent, dashboard, reference)
    invalid_cases = []

    def publish(metrics, *, timing=True, elapsed=4.25, step=37, stamp=1700000000.25, device='cuda:0'):
        events = []
        end = object()
        class Start:
            def elapsed_time(self, selected_end):
                require(selected_end is end, 'Actual elapsed_time argument changed')
                events.append('elapsed_time')
                return elapsed
        class Device:
            def __str__(self):
                events.append('device')
                return device
        def clock():
            events.append('clock')
            return stamp
        agent = SimpleNamespace(training_steps=step)
        namespace = dict(metrics=metrics, gpu_timing=(Start(), end) if timing else None,
                         agent=agent, time=SimpleNamespace(time=clock), device=Device())
        exec(publication, namespace)
        return agent, events

    def api(metrics):
        diagnostic = helper(getattr(metrics, 'last_train_gpu_compute_diagnostic', None))
        value = dict(train_gpu_compute_ms=diagnostic['elapsed_ms'], train_gpu_compute_diagnostic=diagnostic, **scopes)
        json.dumps(value, allow_nan=False)
        return value

    class Contracts(unittest.TestCase):
        def unavailable(self, sample):
            actual = helper(sample)
            self.assertEqual(actual, dict(available=False, elapsed_ms=None, sample_count=None, logical_training_step=None, observed_unix_s=None, device=None))
            json.dumps(dict(train_gpu_compute_ms=actual['elapsed_ms'], train_gpu_compute_diagnostic=actual), allow_nan=False)

        def test01_no_first_sample_is_null_not_legacy_zero(self):
            metrics = SimpleNamespace(last_train_gpu_compute_ms=0.0)
            self.unavailable(None)
            self.assertIsNone(api(metrics)['train_gpu_compute_ms'])
            _, events = publish(metrics, timing=False)
            self.assertEqual(events, [])
            self.assertFalse(hasattr(metrics, 'last_train_gpu_compute_diagnostic'))

        def test02_first_value_count_preincrement_step_clock_device(self):
            metrics = SimpleNamespace()
            agent, events = publish(metrics)
            expected = dict(elapsed_ms=4.25, sample_count=1, logical_training_step=37, observed_unix_s=1700000000.25, device='cuda:0')
            self.assertEqual(metrics.last_train_gpu_compute_diagnostic, expected)
            self.assertEqual(events, ['elapsed_time', 'clock', 'device'])
            self.assertEqual(agent.training_steps, 37)
            agent.training_steps += 1
            self.assertEqual(api(metrics)['train_gpu_compute_diagnostic']['logical_training_step'], 37)
            self.assertEqual(api(metrics)['train_gpu_compute_ms'], 4.25)

        def test03_subsequent_whole_replacement_leaves_old_record_unchanged(self):
            metrics = SimpleNamespace()
            publish(metrics)
            previous = metrics.last_train_gpu_compute_diagnostic
            before = copy.deepcopy(previous)
            publish(metrics, elapsed=8.5, step=57, stamp=1700000002.5, device='cuda:1')
            self.assertIsNot(previous, metrics.last_train_gpu_compute_diagnostic)
            self.assertEqual(previous, before)
            self.assertEqual(metrics.last_train_gpu_compute_diagnostic, dict(elapsed_ms=8.5, sample_count=2, logical_training_step=57, observed_unix_s=1700000002.5, device='cuda:1'))

        def test04_nondiagnostic_keeps_count_stamp_value_and_record(self):
            metrics = SimpleNamespace()
            publish(metrics)
            previous = metrics.last_train_gpu_compute_diagnostic
            before = copy.deepcopy(previous)
            _, events = publish(metrics, timing=False, elapsed=99, step=99, stamp=1800000000, device='other')
            self.assertEqual(events, [])
            self.assertIs(previous, metrics.last_train_gpu_compute_diagnostic)
            self.assertEqual(previous, before)
            self.assertEqual(metrics.last_train_gpu_compute_ms, 4.25)

        def test05_API_polls_copy_without_count_time_or_record_mutation(self):
            metrics = SimpleNamespace()
            publish(metrics)
            sample = metrics.last_train_gpu_compute_diagnostic
            before = copy.deepcopy(sample)
            first, second = api(metrics), api(metrics)
            self.assertEqual(first, second)
            self.assertIsNot(first['train_gpu_compute_diagnostic'], sample)
            self.assertIsNot(first['train_gpu_compute_diagnostic'], second['train_gpu_compute_diagnostic'])
            first['train_gpu_compute_diagnostic']['elapsed_ms'] = 999
            self.assertEqual(sample, before)
            self.assertEqual(api(metrics), second)

        def test06_invalid_optional_fields_become_unavailable_null_JSON(self):
            good = dict(elapsed_ms=4.25, sample_count=1, logical_training_step=37, observed_unix_s=1700000000.25, device='cuda:0')
            faults = dict(elapsed_ms=[None, '4', True, -1, float('nan'), float('inf'), -float('inf')],
                          sample_count=[None, '1', True, 0, -1, 1.0],
                          logical_training_step=[None, '37', True, -1, 1.0],
                          observed_unix_s=[None, 'now', True, 0, -1, float('nan'), float('inf'), -float('inf')],
                          device=[None, True, 1, '', 'x'*81, 'cuda:\n0'])
            for key, values in faults.items():
                for value in values:
                    with self.subTest(field=key, value=repr(value)):
                        bad = dict(good, **{key:value}); before = copy.deepcopy(bad)
                        self.unavailable(bad)
                        self.assertEqual(repr(bad), repr(before))
                        invalid_cases.append(key+':'+repr(value))
            for key in FIELDS:
                with self.subTest(missing=key):
                    bad = dict(good); del bad[key]; self.unavailable(bad); invalid_cases.append('missing:'+key)
            for value in [None, [], '', False, 1, {}]:
                self.unavailable(value)
                invalid_cases.append('sample-type:'+repr(value))

        def test07_real_zero_and_step_zero_are_available(self):
            sample = dict(elapsed_ms=0.0, sample_count=1, logical_training_step=0, observed_unix_s=1, device='cuda')
            value = helper(sample)
            self.assertTrue(value['available'])
            self.assertEqual(value['elapsed_ms'], 0.0)
            self.assertEqual(set(value), {'available', *FIELDS})
            json.dumps(value, allow_nan=False)

        def test08_static_actual_API_and_CUDA_and_preincrement_joins(self):
            for key in ['existing_CUDA_call_AST_exact', 'training_inverse_whole_module_AST_exact', 'actual_preincrement_location', 'helper_and_snapshot_AST_exact_reviewed159e', 'API_single_record_lock_and_return_fields_join']:
                self.assertIs(static[key], True)
            self.assertNotIn('torch', sys.modules)
            self.assertFalse(any(name.startswith('dqn.') for name in sys.modules))

    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    for selected in [own, packet_pin, training_pin, parent_pin, reference_pin, dashboard_pin]:
        checked(selected['path'], selected['sha256'], selected, sealed=selected is not parent_pin)
    report = dict(schema='robotron-Root-pure-existing-CUDA-diagnostic-telemetry-CPU-v1',
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        success=result.wasSuccessful() and not result.skipped, invalid_optional_cases_checked=len(invalid_cases),
        fixture=own, source_packet=packet_pin, training=training_pin, training_parent=parent_pin,
        selected_dashboard=dashboard_pin, reviewed_dashboard_reference=reference_pin, static=static,
        scope='Only actual publication if-block and actual pure diagnostic helper AST with fake metrics/events/time/agent/device; API field wiring and CUDA calls checked statically. No whole training/dashboard, real CUDA/MAME/backend/latency/occupancy or production installation qualification.',
        actual_target_modules_imported=False, actual_CUDA_or_GPU_or_models_or_live_runtime_used=False,
        output=stream.getvalue())
    require('torch' not in sys.modules, 'Torch unexpectedly imported')
    report_path.parent.mkdir(mode=0o700, exist_ok=False)
    raw = (json.dumps(report, sort_keys=True, allow_nan=False)+'\n').encode()
    with report_path.open('xb') as out:
        out.write(raw); out.flush(); os.fsync(out.fileno()); os.fchmod(out.fileno(), 0o444)
    print(json.dumps({key:report[key] for key in ('tests_run', 'failures', 'errors', 'skipped', 'success', 'invalid_optional_cases_checked', 'scope')}))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
