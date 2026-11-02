"""Deferred source/metadata guards; authorship is not execution or CPU proof.

Future root execution reads only the four pinned source files below. It loads
the new stdlib wrapper/common recipe and extracts actual strict predicates into
closed namespaces; no numerical setup, torch, NumPy, checkpoint, phase file,
model, replay, process, API or unit is accessed. Real saved-model finite/Adam
verification remains a separate root-owned numerical CPU execution.
"""
import ast
import builtins
import copy
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


HERE = Path(__file__).resolve().parent
WRAPPER = HERE / 'verify_recipe_phase_snapshot.py'
WRAPPER_SHA = '14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'
RECIPE = HERE / 'recipe.py'
RECIPE_SHA = 'f11e4c8d6725c04c4495b416318713f675ba9305ffe6f7c4009a3bff9b860d0e'
OLD = HERE.parent / 'phase_snapshot_cpu_verifier_proposal/verify_phase_snapshot.py'
OLD_SHA = 'b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519'
STRICT = HERE.parent / 'phase_snapshot_cpu_verifier_proposal/strict_phase_base.py'
STRICT_SHA = '9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'
EFFECTIVE25_SHA = '5612ad9c5730030f818232146fc5073000b89ae8e93577fab8bd18a03d16c8e8'


class UnexpectedDependency(BaseException):
    pass


def authenticated(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise AssertionError('Source pin changed: ' + str(path))
    return data


def module_from_source(path, data, name):
    # Definitions/imports in these two exact new metadata-only sources are
    # intentional. Neither entrypoint main nor numerical loader is invoked.
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path)
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


def functions(data):
    source = data.decode()
    return {node.name: ast.get_source_segment(source, node)
            for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}


def strict_predicate(data, function, fragment, arguments):
    """Run the original statement, not an assertion reimplemented by a fake."""
    text = data.decode()
    tree = ast.parse(text)
    target = next(node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name == function)
    matches = [node for node in target.body if fragment in ast.get_source_segment(text, node)]
    if len(matches) != 1:
        raise AssertionError('Exact strict predicate boundary differs')
    context = [node for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'HELD_RECIPE_CONTEXT'
                       for t in node.targets)]
    if len(context) != 1:
        raise AssertionError('Exact strict context assignment differs')
    guard = ast.FunctionDef(name='guard', args=ast.arguments(posonlyargs=[],
        args=[ast.arg(arg=name) for name in arguments], vararg=None, kwonlyargs=[], kw_defaults=[],
        kwarg=None, defaults=[]), body=[copy.deepcopy(matches[0])], decorator_list=[], type_params=[])
    unit = ast.Module(body=[copy.deepcopy(context[0]), guard], type_ignores=[])
    def forbidden(*args, **kwargs):
        raise UnexpectedDependency('No host fallback in extracted predicate')
    safe = dict(vars(builtins))
    for name in ('__import__', 'open', 'input', 'breakpoint'):
        safe[name] = forbidden
    def require(value, message):
        if not value:
            raise RuntimeError(message)
    namespace = dict(__builtins__=safe, math=math, require=require)
    exec(compile(ast.fix_missing_locations(unit), '<actual-strict-metadata-predicate>', 'exec'), namespace)
    return namespace['guard']


class RecipeCPUMetadataContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if any(n == 'torch' or n.startswith('torch.') or n == 'numpy' for n in sys.modules):
            raise AssertionError('Fresh stdlib-only guard interpreter required')
        cls.wrapper_source = authenticated(WRAPPER, WRAPPER_SHA)
        cls.recipe_source = authenticated(RECIPE, RECIPE_SHA)
        cls.original_source = authenticated(OLD, OLD_SHA)
        cls.strict_source = authenticated(STRICT, STRICT_SHA)
        cls.w = module_from_source(WRAPPER, cls.wrapper_source, '_deferred_recipe_CPU_wrapper')
        cls.recipe = module_from_source(RECIPE, cls.recipe_source, '_deferred_common_recipe')

    def tearDown(self):
        self.assertFalse(any(n == 'torch' or n.startswith('torch.') or n == 'numpy'
                             for n in sys.modules))

    def context(self, scale):
        return self.recipe.held_context(self.recipe.for_scale(scale), self.recipe.HELD_50)

    def test_half_recipe_keeps_original_strict_source_and_shared_ABI(self):
        raw, proof = self.w.specialize_strict_source(self.strict_source, self.context(.5))
        self.assertEqual(raw, self.strict_source)
        self.assertEqual(proof['replacement_count'], 0)
        self.assertEqual(proof['effective_source_sha256'], STRICT_SHA)
        for scale in (.25, .5):
            with self.subTest(scale=scale):
                value = self.context(scale)
                self.assertEqual(self.w.infer_recipe(value), self.recipe.from_held(value))
                self.assertEqual(value['optimizer_lr'], 1.25e-5 if scale == .25 else 2.5e-5)
        old, new = functions(self.original_source), functions(self.wrapper_source)
        for name in ('require', 'sha', 'clocks', 'triple', 'load_base', 'immutable',
                     'read_job', 'historical_archive', 'check_acquisition', 'verify_phase'):
            self.assertEqual(new[name], old[name], name)

    def test_quarter_specializes_only_three_unique_literals_and_reverses_exactly(self):
        data, proof = self.w.specialize_strict_source(self.strict_source, self.context(.25))
        self.assertEqual(hashlib.sha256(data).hexdigest(), EFFECTIVE25_SHA)
        self.assertEqual(proof['replacement_count'], 3)
        self.assertTrue(proof['reverse_exact_raw_source'])
        self.assertFalse(proof['saved_metadata_normalized'])
        reverse = data
        for old, new in reversed(self.w.RECIPE_REPLACEMENTS):
            self.assertEqual(reverse.count(new), 1)
            reverse = reverse.replace(new, old)
        self.assertEqual(reverse, self.strict_source)
        before, after = functions(self.strict_source), functions(data)
        self.assertEqual(before['finite_tree'], after['finite_tree'])
        self.assertEqual(before['validate_checkpoint'], after['validate_checkpoint'])
        self.assertEqual(set(before), set(after))
        self.assertEqual([n for n in before if before[n] != after[n]], ['check_context'])

    def test_mixed_wrong_extra_and_nonliteral_full_contexts_refuse(self):
        for key, value in (('optimizer_lr', 2.5e-5), ('batch_size', 2048),
                           ('n_step', 1), ('max_samples_per_frame', 4),
                           ('learning_control_lr_scale', True), ('optimizer_lr', float('nan')),
                           ('epsilon', .2), ('fused', 1)):
            with self.subTest(key=key, value=value):
                context = self.context(.25); context[key] = value
                with self.assertRaises(RuntimeError):
                    self.w.specialize_strict_source(self.strict_source, context)
        for context in ({}, dict(self.context(.25), extra='unreviewed')):
            with self.assertRaises(RuntimeError):
                self.w.infer_recipe(context)
        corrupt = self.strict_source.replace(b'optimizer_lr=2.5e-5,', b'optimizer_lr=3.5e-5,')
        with self.assertRaises(RuntimeError):
            self.w.specialize_strict_source(corrupt, self.context(.25))

    def test_real_saved_Adam_group_predicate_checks_selected_LR_not_relabelled_half(self):
        for scale in (.25, .5):
            with self.subTest(scale=scale):
                data, unused = self.w.specialize_strict_source(self.strict_source, self.context(scale))
                guard = strict_predicate(data, 'validate_checkpoint', 'Saved Adam {name} differs', ('group',))
                good = dict(lr=1.25e-5 if scale == .25 else 2.5e-5, eps=1.5e-4, weight_decay=0.)
                guard(good)
                for key, value in (('lr', 2.5e-5 if scale == .25 else 1.25e-5),
                                   ('lr', float('nan')), ('lr', True), ('eps', 1e-8),
                                   ('weight_decay', .01)):
                    bad = dict(good); bad[key] = value
                    with self.assertRaises(RuntimeError):
                        guard(bad)

    def test_real_archived_control_guard_requires_same_recipe_and_label(self):
        for scale in (.25, .5):
            with self.subTest(scale=scale):
                data, unused = self.w.specialize_strict_source(self.strict_source, self.context(scale))
                guard = strict_predicate(data, 'check_context', 'Archived held-control experiment/recipe differs',
                                         ('control', 'job'))
                job = dict(experiment='synthetic_recipe_metadata')
                control = dict(experiment=job['experiment'], lr_scale=scale,
                               epsilon_ramp=dict(start=.1, end=.1))
                guard(control, job)
                for bad in (dict(control, lr_scale=.5 if scale == .25 else .25),
                            dict(control, experiment='old-label'),
                            dict(control, epsilon_ramp=dict(start=.1, end=.2))):
                    with self.assertRaises(RuntimeError):
                        guard(bad, job)

    def test_actual_dynamic_phase_and_four_clock_predicates_stay_strict(self):
        expected = dict(metric='ce', phase_id='ce4096_rejected_gap_observer_20261018',
            root_precommit_sha256='a' * 64, founder_phase_record_sha256='b' * 64,
            last_resume_record_sha256=None, started_from=dict(path='/synthetic/origin.pt',
            sha256='c' * 64, bytes=123, clocks=dict.fromkeys(self.w.CLOCKS, 10)), valid=True)
        phase = dict(schema=self.w.PHASE_SCHEMA, valid=True, invalid_reason=None,
            metric=expected['metric'], phase_id=expected['phase_id'],
            root_precommit_sha256=expected['root_precommit_sha256'],
            phase_record_sha256=expected['founder_phase_record_sha256'],
            last_resume_record_sha256=None, started_from=copy.deepcopy(expected['started_from']),
            priority_update_calls=18, ring_rows_submitted=1024, predecessor=None)
        checkpoint = dict.fromkeys(self.w.CLOCKS, 30); checkpoint['priority_metric_phase'] = phase
        floor = dict.fromkeys(self.w.CLOCKS, 25); boot = dict.fromkeys(self.w.CLOCKS, 20)
        evidence = {}
        self.w.verify_phase(checkpoint, evidence, expected, boot, floor, 'start')
        self.assertTrue(evidence['phase_metadata_verified'])
        for key in ('metric', 'phase_id', 'root_precommit_sha256', 'phase_record_sha256'):
            bad = copy.deepcopy(checkpoint); bad['priority_metric_phase'][key] = 'wrong'
            with self.assertRaises(RuntimeError):
                self.w.verify_phase(bad, {}, expected, boot, floor, 'start')
        for key in self.w.CLOCKS:
            bad = copy.deepcopy(checkpoint); bad[key] = 24
            with self.assertRaises(RuntimeError):
                self.w.verify_phase(bad, {}, expected, boot, floor, 'start')
        # Production recipe selection rejects KL before reading/compiling the
        # strict source; an explicit fake supplies only the common recipe API.
        original = self.w.load_recipe_api
        try:
            self.w.load_recipe_api = lambda base: (self.recipe, {})
            with self.assertRaises(RuntimeError):
                self.w.select_recipe_base(dict(source_control_context=dict(held_recipe_context=self.context(.25)),
                    phase_snapshot=dict(expected_phase=dict(metric='kl'))),
                    SimpleNamespace(HELD_RECIPE_CONTEXT=self.recipe.HELD_50))
        finally:
            self.w.load_recipe_api = original


if __name__ == '__main__':
    unittest.main(verbosity=2)
