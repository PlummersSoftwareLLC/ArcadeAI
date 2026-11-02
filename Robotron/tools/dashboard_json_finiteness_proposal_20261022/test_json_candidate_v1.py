"""Real sampler methods and JavaScript engine; no live service or scientific main."""
import ast
import copy
import ctypes
from collections import deque
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import threading
import time
import unittest

P = Path(__file__).resolve().parent
G = P.parents[1]
Q = G/'logs/managed-learning-20261015/run-26/quality32-protected1741-vs-normal2202-start-certified-original01-preparation-20261022'
BAD = Q/'01-reference/diagnostic-output-original01/main-observations/1532-API.raw.json'
ORIGINAL = G/'Scripts/dqn/metrics_dashboard.py'
CANDIDATE = P/'metrics_dashboard_candidate_v1.py'
SOURCE_SHA = '3d1aa1950e6b1c5224ace3aecb9c837e433e5c36941b89465b414749f903da27'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


history = module('_JSON_guard_original_history', G/'Scripts/dqn/dashboard_history.py')
games = module('_JSON_guard_original_strict_decoder', G/'tools/startup_policy_journal_proposal/audit_quality32_games_v1.py')
window = module('_JSON_guard_original_pure_main_health',
    G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')


def sampler(path):
    tree = ast.parse(path.read_text())
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == '_DashboardState')
    helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name == '_json_safe_diagnostic_snapshot']
    owner.body = [node for node in owner.body if isinstance(node, ast.FunctionDef)
        and node.name in ['sample', 'payload', 'now_body']]
    namespace = dict(json=json, math=math, time=time, Any=object,
        compact_history_row=history.compact_history_row, bounded_history=history.bounded_history)
    exec(compile(ast.fix_missing_locations(ast.Module(body=helpers+[owner], type_ignores=[])), str(path), 'exec'), namespace)
    return namespace['_DashboardState']


def state(path, snapshot, warmup=False):
    value = sampler(path)()
    value.lock = threading.Lock()
    value.history = deque()
    value.latest = None
    value._cached_now_body = b'{}'
    value._sample_count = 0 if warmup else 11
    value._first_sample_time = None
    value._update_web_client_count_locked = lambda: None
    value._build_snapshot = lambda: snapshot
    return value


def js_function(text, name):
    start = text.index('    function '+name+'(')
    opening = text.index('{', start)
    depth = 1
    end = opening+1
    while depth:
        depth += (text[end] == '{')-(text[end] == '}')
        end += 1
    return text[start:end]


def evaluate_js_boolean(source):
    lib = ctypes.CDLL('/lib/aarch64-linux-gnu/libjavascriptcoregtk-4.1.so.0')
    ptr = ctypes.c_void_p
    lib.JSGlobalContextCreate.argtypes = [ptr]
    lib.JSGlobalContextCreate.restype = ptr
    lib.JSStringCreateWithUTF8CString.argtypes = [ctypes.c_char_p]
    lib.JSStringCreateWithUTF8CString.restype = ptr
    lib.JSEvaluateScript.argtypes = [ptr, ptr, ptr, ptr, ctypes.c_int, ctypes.POINTER(ptr)]
    lib.JSEvaluateScript.restype = ptr
    lib.JSValueToBoolean.argtypes = [ptr, ptr]
    lib.JSValueToBoolean.restype = ctypes.c_bool
    lib.JSStringRelease.argtypes = [ptr]
    lib.JSGlobalContextRelease.argtypes = [ptr]
    context = lib.JSGlobalContextCreate(None)
    script = lib.JSStringCreateWithUTF8CString(source.encode())
    exception = ptr()
    try:
        value = lib.JSEvaluateScript(context, script, None, None, 1, ctypes.byref(exception))
        if exception.value:
            raise AssertionError('Real JavaScriptCore evaluation raised an exception')
        return bool(lib.JSValueToBoolean(context, value))
    finally:
        lib.JSStringRelease(script)
        lib.JSGlobalContextRelease(context)


class DashboardJSONCandidateV1(unittest.TestCase):
    def original(self):
        return json.loads(BAD.read_bytes())

    def test_actual_captured_failure_reproduces_in_old_sampler_and_new_body_is_strict_JSON_in_both_paths(self):
        original = self.original()
        self.assertTrue(math.isinf(original['grad_norm']))
        old = state(ORIGINAL, original)
        old.sample()
        with self.assertRaises(ValueError):
            games.decode(old.now_body())
        for warmup in [True, False]:
            with self.subTest(warmup=warmup):
                current = state(CANDIDATE, original, warmup)
                current.sample()
                decoded = games.decode(current.now_body())
                self.assertIsNone(decoded['grad_norm'])
                self.assertEqual(decoded['grad_norm_nonfinite'], 'positive_infinity')
                self.assertEqual({k:v for k,v in decoded.items() if k not in ['grad_norm', 'grad_norm_nonfinite']},
                    {k:v for k,v in original.items() if k != 'grad_norm'})
                json.dumps(current.payload(), allow_nan=False)
                self.assertTrue(math.isinf(original['grad_norm']))
        with self.assertRaises(ValueError):
            games.decode(BAD.read_bytes())
        review = json.loads((Q/'01-reference/independent-quality-leg-review-original01/review.json').read_text())
        self.assertFalse(review['valid'])

    def test_nonfinite_gradient_variants_are_explicit_and_finite_values_keep_exact_original_encoding(self):
        for number, label in [(float('inf'), 'positive_infinity'), (-float('inf'), 'negative_infinity'), (float('nan'), 'nan')]:
            data = self.original()
            data['grad_norm'] = number
            current = state(CANDIDATE, data)
            current.sample()
            decoded = games.decode(current.now_body())
            self.assertIsNone(decoded['grad_norm'])
            self.assertEqual(decoded['grad_norm_nonfinite'], label)
        for number in [0.0, -0.0, 0.25, -0.25, 1e30]:
            data = self.original()
            data['grad_norm'] = number
            old, current = state(ORIGINAL, data), state(CANDIDATE, data)
            old.sample()
            current.sample()
            self.assertEqual(old.now_body(), current.now_body())
            self.assertNotIn('grad_norm_nonfinite', games.decode(current.now_body()))

    def test_nonfinite_core_fields_fail_visibly_without_poisoning_history_or_serving_previous_healthy_body(self):
        for path in [('loss',), ('epsilon',), ('quality_campaign', 'legs', 0, 'mean'),
                ('c51_diagnostics', 'categorical_kl'), ('host_pipeline', 'learning_exposure', 'optimizer', 'total', 'applied')]:
            with self.subTest(path=path):
                good = self.original()
                good['grad_norm'] = 0.2
                current = state(CANDIDATE, good)
                current.sample()
                before = copy.deepcopy(current.history)
                bad = copy.deepcopy(good)
                target = bad
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = float('inf')
                current._build_snapshot = lambda: bad
                with self.assertRaises(ValueError):
                    current.sample()
                failure = games.decode(current.now_body())
                self.assertIn('snapshot_error', failure)
                self.assertEqual(current.history, before)
                with self.assertRaises((KeyError, ValueError)):
                    window.healthy(failure, {}, 'unchanged', time.time())
                json.dumps(current.payload(), allow_nan=False)

    def test_recovery_does_not_mutate_input_or_retain_an_old_error_flag(self):
        data = self.original()
        current = state(CANDIDATE, data)
        current.sample()
        self.assertIsNone(current.history[-1]['grad_norm'])
        self.assertEqual(current.history[-1]['grad_norm_nonfinite'], 'positive_infinity')
        bad = dict(data, loss=float('inf'))
        current._build_snapshot = lambda: bad
        with self.assertRaises(ValueError):
            current.sample()
        good = dict(data, grad_norm=0.3)
        current._build_snapshot = lambda: good
        current.sample()
        decoded = games.decode(current.now_body())
        self.assertEqual(decoded['grad_norm'], 0.3)
        self.assertNotIn('snapshot_error', decoded)
        self.assertNotIn('grad_norm_nonfinite', decoded)
        self.assertTrue(math.isinf(data['grad_norm']))

    def test_real_JS_parser_formatter_and_window_smoothing_preserve_missing_gradient_as_gap(self):
        text = CANDIDATE.read_text()
        javascript = '\n'.join(js_function(text, name) for name in ['chartNumber', 'fmtPaddedFloat', 'buildWindowSmoothedHistory'])
        current = state(CANDIDATE, self.original())
        current.sample()
        javascript += '\n(function(){\n'
        javascript += 'const fixed=JSON.parse('+json.dumps(current.now_body().decode())+');\n'
        javascript += 'let oldRejected=false;try{JSON.parse('+json.dumps(BAD.read_text())+');}catch(e){oldRejected=true;}\n'
        javascript += '''const rows=buildWindowSmoothedHistory([{ts:0,grad_norm:0.2},{ts:1,grad_norm:null},{ts:2,grad_norm:0.4}], [{key:"grad_norm",alpha:0.5}], 2);
return oldRejected && fixed.grad_norm===null && fixed.grad_norm_nonfinite==="positive_infinity"
 && Number.isNaN(chartNumber(null)) && Number.isNaN(chartNumber(undefined)) && chartNumber(0)===0
 && fmtPaddedFloat(null)==="--" && fmtPaddedFloat(Infinity)==="--" && fmtPaddedFloat(0.25,2,3)==="00.250"
 && rows[1].grad_norm===null && Number.isFinite(rows[0].grad_norm) && Number.isFinite(rows[2].grad_norm);
})()'''
        self.assertTrue(evaluate_js_boolean(javascript))
        self.assertIn('if (!Number.isFinite(value)) return NaN;', text)
        self.assertEqual(text.count('if (now && now.snapshot_error) throw new Error(now.snapshot_error);'), 2)

    def test_production_source_and_every_existing_python_method_except_sampler_remain_unchanged(self):
        self.assertEqual(hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(), SOURCE_SHA)
        def methods(path):
            return {node.name:ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(path.read_text()))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        old, new = methods(ORIGINAL), methods(CANDIDATE)
        self.assertEqual(set(new)-set(old), {'_json_safe_diagnostic_snapshot'})
        self.assertEqual(set(old)-set(new), set())
        for name in old:
            if name != 'sample':
                self.assertEqual(old[name], new[name], name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
