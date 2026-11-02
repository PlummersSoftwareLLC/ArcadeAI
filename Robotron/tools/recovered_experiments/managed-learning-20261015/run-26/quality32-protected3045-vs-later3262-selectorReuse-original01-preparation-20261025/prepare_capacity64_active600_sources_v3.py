"""Prepare separate UNSELECTED 32/64 evaluator engineering sources; never launch."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).parent
E = N / 'selector-active600-counterbalanced-engineering-original01'
S = N / 'isolated-source-family-original01'
F = N / 'future-evaluator-concurrency64-UNSELECTED-source-preparation-original02'


def expr(text):
    return ast.parse(text, mode='eval').body


def set_global(tree, name, value):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            node.value = expr(value)
            return
    tree.body.insert(1, ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=expr(value)))


class Shape(ast.NodeTransformer):
    def __init__(self, strings):
        self.strings = strings
        self.changes = []

    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value in self.strings:
            new = self.strings[node.value]
            self.changes.append(dict(line=node.lineno, old=node.value, new=new))
            return ast.copy_location(ast.Constant(new), node)
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'range' and len(node.args) == 2:
            args = node.args
            if all(isinstance(v, ast.Constant) for v in args):
                pair = tuple(v.value for v in args)
                if pair in ((4096, 4128), (20000, 20032)):
                    node.args[1] = expr(str(pair[0]) + ' + ACTOR_COUNT')
                    self.changes.append(dict(line=node.lineno, old=repr(pair), new='base + ACTOR_COUNT'))
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        left = ast.unparse(node.left)
        for index, value in enumerate(node.comparators):
            if not isinstance(value, ast.Constant):
                continue
            if value.value == 32 and left in (
                    "value['clients']", 'len(actors)', 'len(certified)', 'len(actual_slots)',
                    'len(registrations)', 'len(subjects)'):
                node.comparators[index] = expr('ACTOR_COUNT')
                self.changes.append(dict(line=node.lineno, old=left + ' == 32', new='ACTOR_COUNT'))
            elif value.value == 32 and (' for s in subjects' in left or left == "cohort['count']"):
                node.comparators[index] = expr('ACTOR_COUNT')
                self.changes.append(dict(line=node.lineno, old='subject/quota startup32', new='ACTOR_COUNT'))
            elif value.value == 2 and left in ("cohort['games_per_slot']", 'counts[slot]'):
                node.comparators[index] = expr('GAMES_PER_SLOT')
                self.changes.append(dict(line=node.lineno, old=left + ' quota2', new='GAMES_PER_SLOT'))
            elif value.value == 64 and left == 'len(set(values))':
                node.comparators[index] = expr('2 * ACTOR_COUNT')
                self.changes.append(dict(line=node.lineno, old=left + ' == 64', new='2 * ACTOR_COUNT'))
        if ast.unparse(node) == '1 <= count <= 2':
            node.comparators[-1] = expr('GAMES_PER_SLOT')
            self.changes.append(dict(line=node.lineno, old='quota upper2', new='GAMES_PER_SLOT'))
        return node

    def visit_DictComp(self, node):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Constant) and node.value.value == 2
                and any(isinstance(g.iter, ast.Name) and g.iter.id == 'SLOTS' for g in node.generators)):
            node.value = expr('GAMES_PER_SLOT')
            self.changes.append(dict(line=node.lineno, old='per-slot quota2', new='GAMES_PER_SLOT'))
        return node

    def visit_keyword(self, node):
        self.generic_visit(node)
        if node.arg == 'games_per_slot' and isinstance(node.value, ast.Constant) and node.value.value == 2:
            node.value = expr('GAMES_PER_SLOT')
            self.changes.append(dict(line=node.lineno, old='games_per_slot=2', new='GAMES_PER_SLOT'))
        if node.arg == 'certified_initial_games' and isinstance(node.value, ast.Constant) and node.value.value == 32:
            node.value = expr('ACTOR_COUNT')
            self.changes.append(dict(line=node.lineno, old='certified_initial_games32', new='ACTOR_COUNT'))
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if (isinstance(node.op, ast.LShift) and isinstance(node.left, ast.Constant) and node.left.value == 16
                and isinstance(node.right, ast.Constant) and node.right.value == 30):
            node.left = ast.Constant(24)
            self.changes.append(dict(line=node.lineno, old='16 << 30 memory bound', new='24 << 30'))
        return node


def prepare():
    assert not F.exists()
    F.mkdir(mode=0o700)
    spec = importlib.util.spec_from_file_location('_capacity_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    assert h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    proposal = h.pin(N / 'future-evaluator-concurrency64-UNSELECTED-proposal-original01/proposal.json')
    assert proposal['sha256'] == '8443ce85b70177433c9de2f1e1b9e74b0d3c55a0591df20b2465615f4ffc271e'
    design = h.put(F / 'engineering-scope-UNSELECTED.json', dict(
        schema='robotron-evaluator-count-active600-scope-definition-v1', proposal=proposal,
        baseline=dict(actor_count=32, games_per_slot=2), treatment=dict(actor_count=64, games_per_slot=1),
        common=dict(expected_games=64, minimum_complete_games=50, inference_max_batch_size=16,
                    warm_shapes=list(range(1, 17)), native_CPU_cores=12, native_memory_bytes=24 << 30,
                    active_seconds=600, wall_limit_seconds=960),
        protected_policy='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883',
        source_preparation_only=True, native_launch_selected=False, quality_qualified=False,
        actual64_startup_verified=False, throughput_gain_verified=False, created_unix_s=time.time()))
    parent = E / 'implementations/B'
    parents = dict(timing=G / 'tools/training_connection_lifecycle_proposal_20261023/selector_native_timing_v1.py', view=parent / 'fixed_slot_cohort_view_v1.py', drain=parent / 'fixed_slot_cohort_drain_v1.py',
                   games=S / 'components/audit_fixed_slot64_games_v1.py', wire=S / 'components/audit_quota64_wire_v2.py',
                   runtime=parent / 'run_native32_selector_active600_v1.py',
                   controller=parent / 'control_native32_selector_active600_v1.py',
                   reviewer=E / 'review_selector_active600_original_v1.py')
    names = dict(timing='selector_native_timing_v1.py', view='fixed_slot_cohort_view_v1.py', drain='fixed_slot_cohort_drain_v1.py',
                 games='audit_fixed_slot64_games_v1.py', wire='audit_quota64_wire_v2.py',
                 runtime='run_evaluator_count_active600_v1.py', controller='control_evaluator_count_active600_v1.py',
                 reviewer='review_evaluator_count_active600_v1.py')
    source_pins = {k: h.pin(p) for k, p in parents.items()}
    rows = []
    for role, count, cases in [('A32', 32, ('01-A1-control', '04-A2-control')),
                                ('B64', 64, ('02-B1-capacity64', '03-B2-capacity64'))]:
        directory = F / role
        directory.mkdir(mode=0o700)
        made = {}
        for key in ('view', 'drain', 'games', 'wire', 'timing', 'runtime', 'controller', 'reviewer'):
            path = parents[key]
            original = path.read_text()
            strings = {
                'first_two_known_starts_per_declared_slot': ('first_two_known_starts_per_declared_slot'
                    if count == 32 else 'first_known_start_per_declared_slot'),
                'robotron-native32-quota64-API-epoch-reference-load-diagnostic-v1': 'robotron-evaluator-count-active600-engineering-v1',
                'robotron-native32-quota64-API-epoch-reference-load-diagnostic-result-v1': 'robotron-evaluator-count-active600-engineering-result-v1',
                'MemoryMax=16G': 'MemoryMax=24G', '16G': '24G',
                'original-all32-prefix-diagnostic-stop.json': 'original-all-slots-prefix-diagnostic-stop.json',
                'original-active32-start.json': 'original-active-start.json',
                'original-active32-frame-rate.json': 'original-active-frame-rate.json',
                'robotron-selector-active32-endpoint-v1': 'robotron-selector-active-endpoint-v1',
                'robotron-selector-active32-accepted-frame-rate-v1': 'robotron-selector-active-accepted-frame-rate-v1',
            }
            for previous_key, pin in made.items():
                strings[source_pins[previous_key]['sha256']] = pin['sha256']
                strings[str(parents[previous_key])] = pin['path']
            tree = ast.parse(original)
            transformer = Shape(strings)
            tree = transformer.visit(tree)
            set_global(tree, 'ACTOR_COUNT', str(count))
            set_global(tree, 'GAMES_PER_SLOT', str(64 // count))
            if key in ('view', 'drain', 'games', 'wire', 'runtime'):
                set_global(tree, 'SLOTS', 'tuple(range(4096, 4096 + ACTOR_COUNT))')
            if key == 'runtime':
                set_global(tree, 'DIAGNOSTIC_SHA', repr(design['sha256']))
                set_global(tree, 'IMPLEMENTATION', repr(role))
                set_global(tree, 'CASE_NAMES', repr(cases))
                set_global(tree, 'COMPONENTS', 'Path(' + repr(str(directory)) + ')')
                functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
                validate, run, main = [functions[n] for n in ('validate_job', 'run', 'main')]
                for fn in (validate, run):
                    fn.args.kwonlyargs.append(ast.arg(arg='cpu_initializer'))
                    fn.args.kw_defaults.append(ast.Constant(False))
                validate.body[0:0] = ast.parse(
                    "require(type(cpu_initializer) is bool and job.get('initializer_fixture_only') is cpu_initializer, 'Explicit CPU-only fixture mode or native-job mode required')\n"
                    "require(job.get('capacity_shape') == dict(actor_count=ACTOR_COUNT, games_per_slot=GAMES_PER_SLOT, expected_games=64, identity_count=2*ACTOR_COUNT, inference_max_batch_size=16), 'Exact evaluator geometry required')\n").body
                for node in ast.walk(run):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'validate_job':
                        node.keywords.append(ast.keyword(arg='cpu_initializer', value=ast.Name(id='cpu_initializer', ctx=ast.Load())))
                first_try = next(n for n in run.body if isinstance(n, ast.Try))
                assert ast.unparse(first_try.body[0]).startswith('lease_entry = lease.acquire()')
                first_try.body[0:0] = ast.parse("if cpu_initializer:\n    raise RuntimeError('CPU_INITIALIZER_STOP_BEFORE_GPU_LEASE_WORKER_TORCH_MAME')\n").body
                parser_assign = next(i for i, n in enumerate(main.body) if isinstance(n, ast.Assign)
                                     and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute)
                                     and n.value.func.attr == 'parse_args')
                main.body[parser_assign:parser_assign] = ast.parse("parser.add_argument('--cpu-initializer', action='store_true')").body
                for node in ast.walk(main):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'run':
                        node.keywords.append(ast.keyword(arg='cpu_initializer', value=expr('args.cpu_initializer')))
            ast.fix_missing_locations(tree)
            raw = (ast.unparse(tree) + '\n').encode()
            target = directory / names[key]
            with target.open('xb') as stream:
                stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
            made[key] = h.pin(target)
            rows.append(dict(role=role, actor_count=count, component=key, parent=source_pins[key],
                             derived=made[key], explicit_AST_shape_changes=transformer.changes))
        h.put(directory / 'source-manifest-UNSELECTED.json', dict(
            schema='robotron-evaluator-count-active600-source-preparation-v1', actor_count=count,
            games_per_slot=64 // count, expected_games=64, source_pins=made,
            shared_bridge=h.pin(Path(json.loads((E / '02-B1-proposal/job.json').read_bytes())['quota64_source_pins']['bridge']['path'])),
            native_CPU_cores=12, native_memory_bytes=24 << 30, inference_max_batch_size=16,
            actual_initializer_checked=False, CPU_guards_complete=False, native_launch_ready=False,
            actual64_startup_verified=False, quality_qualified=False))
    manifest = h.put(F / 'source-derivation-INCOMPLETE.json', dict(
        schema='robotron-evaluator-capacity64-source-derivation-work-in-progress-v1', source=h.pin(__file__),
        design=design, derivations=rows, status='UNSELECTED_INCOMPLETE_CPU_AND_INTERFACE_GUARDS_REQUIRED',
        remaining=['Validate every cross-component binding and geometry-dependent admission/closure predicate.',
                   'Prepare explicit never-native CPU fixtures, refusal guards and actual pre-lease initializer checks for both shapes.',
                   'Prepare independent reviewer/controller/job interfaces and mathematical comparison guards.',
                   'Actual64 startup/ROM1200/resource/lifecycle proof and original engineering pilot remain required after current campaign disposition.'],
        native_job_prepared=False, native_launch_ready=False, main_or_current_scientific_source_changed=False,
        quality_qualified=False, throughput_gain_verified=False, learning_speed_gain_verified=False))
    print(json.dumps(dict(manifest=manifest, sources=len(rows), native_ready=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        print('PLAN_ONLY')
