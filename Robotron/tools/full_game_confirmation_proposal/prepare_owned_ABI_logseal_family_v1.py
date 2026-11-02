"""Compose future-only full-game ABI/owned-health/log-seal corrections.

This does not select a scientific pair, start a process, or modify any active
screen or previous result. All full-game and early-C1 eligibility gates remain.
"""
import argparse
import ast
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
C = B / 'post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
F = B / 'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def replace_once(text, old, new, edits):
    assert text.count(old) == 1, old
    edits.append((old, new))
    return text.replace(old, new, 1)


def execute(output):
    hp = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(hp.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    h = load('_future_ABI_family_h', hp)
    read = lambda entry: json.loads(h.checked(entry).read_bytes())
    base_pin = h.pin(C / ('fullgame-evaluator-live-engineering-original01-20261101/'
        'slot-permit-archival-source-original02/native-scientific-archival-UNBOUND-original01/'
        'source-preparation-and-CPU-unbound-proof.json'))
    base = read(base_pin)
    health_pin = h.pin(F / 'future-owned-overlap-observer-reviewer-original02/current_v6_owned_overlap_health_v5.py')
    owned_pin = h.pin(F / 'future-owned-overlap-observer-reviewer-original02/owned_train_connection_overlap_v2.py')
    engineering_pin = h.pin(F / ('owned-overlap-fullgame-live-engineering-original04/'
        'qualified-original-fullgame-engineering-and-positive-owned-closeout.json'))
    assert engineering_pin['sha256'] == '199865114caef5ee023d1ae42fe464f805112e90082cd8328dfce1b187e8f6ce'
    assert owned_pin['sha256'] == 'c10b6a2e752b61aa345e648c26ee9bf7b82a711ab73f1351138ee31dcdb2a879'
    output.mkdir(mode=0o700)
    deltas = []

    def save(name, parent, text, edits):
        original = h.checked(parent).read_text()
        reverted = text
        for before, after in reversed(edits):
            assert reverted.count(after) == 1, before
            reverted = reverted.replace(after, before, 1)
        assert reverted == original
        ast.parse(text)
        target = output / name
        with target.open('x') as stream:
            stream.write(text); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        selected = h.pin(target)
        deltas.append(dict(parent=parent, selected=selected, exact_inverse_verified=True,
            edits=[dict(before=a, after=b) for a, b in edits],
            patch=''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True)))))
        return selected

    parent = base['native']
    raw = h.checked(parent).read_text()
    text, edits = raw, []
    text = replace_once(text, "        full_slot_permit_archival_CPU='a75c1ca5b554d8ba324550cb07fccfe1b46f86b0b7b0d7664cd9f5b13cca0a7c')",
        "        full_slot_permit_archival_CPU='a75c1ca5b554d8ba324550cb07fccfe1b46f86b0b7b0d7664cd9f5b13cca0a7c',\n"
        "        qualified_full64_owned_Main_engineering='" + engineering_pin['sha256'] + "')", edits)
    text = replace_once(text, "job.get('current_v6_health_source',{}).get('sha256')=='5e7efde5b458ab5dd6f7dba684b412d1cf0c998b62ec69b316f0b822c1d24d4a'",
        "job.get('current_v6_health_source',{}).get('sha256')=='" + health_pin['sha256'] + "'", edits)
    text = replace_once(text, "job.get('current_v6_health_qualification',{}).get('sha256')=='574b0d38bacab5724ad731e381274b6102d85fc6596b942518ac7e1cc65d4de3'",
        "job.get('current_v6_health_qualification',{}).get('sha256')=='" + engineering_pin['sha256'] + "'\n"
        "        and job.get('owned_TRAIN_overlap_source',{}).get('sha256')=='" + owned_pin['sha256'] + "'", edits)
    text = replace_once(text, 'server=actor=controller=server_worker=None;policy_before=policy_after=None',
                        'server=actor=controller=server_worker=None;policy_before=policy_after=None;compile_before=None', edits)
    text = replace_once(text, 'policy_before=policy_before,policy_after=policy_after,acquired_checkpoint=acquisition,',
                        'policy_before=policy_before,policy_after=policy_after,acquired_checkpoint=acquisition,compile_report=compile_before,', edits)
    native_pin = save('run_owned_ABI_fullgame_UNBOUND_v1.py', parent, text, edits)

    sequence_preparation = read(h.pin(F / 'future-early-C1-sequence-original01/source-preparation.json'))
    parent = sequence_preparation['source']
    raw = h.checked(parent).read_text()
    text, edits = raw, []
    runner_pin = h.pin(G / 'tools/full_game_confirmation_proposal/run_owned_overlap_fullgame_engineering_v3.py')
    runner_raw = h.checked(runner_pin).read_text()
    seal_function = next(n for n in ast.parse(runner_raw).body if isinstance(n, ast.FunctionDef) and n.name == 'seal_closed_log')
    seal_source = ast.get_source_segment(runner_raw, seal_function)
    text = replace_once(text, 'import os\n', 'import os\nimport stat\n', edits)
    text = replace_once(text, '\ndef main():', '\n' + seal_source + '\n\ndef main():', edits)
    marker = "                native_close=h.put(leg['native_closeout_path'],dict(status='PASS_ORIGINAL_FULLGAME_LEG_NATIVE_SCOPE_CLOSED',"
    seal = '''                execution=Path(self.read(leg['native_controller_config'])['output'])
                log_seal=h.put(directory/'original-native-output-log-seal.json',dict(
                    original_controller_result=closed['result'],original_scope_closure=closed['closure'],
                    original_Popen_reaped=True,all_original_controller_resources_closed=True,
                    logs={name:seal_closed_log(execution/name,h,writers_closed=True)
                          for name in ('stdout.txt','stderr.txt')}))
'''
    text = replace_once(text, marker, seal + marker, edits)
    text = replace_once(text, 'original_Popen_reaped=True,all_original_controller_resources_closed=True,scientific_review_pending=True))',
        'original_Popen_reaped=True,all_original_controller_resources_closed=True,scientific_review_pending=True,\n'
        '                    sealed_native_output_logs=log_seal))', edits)
    sequence_pin = save('run_early_C1_closed_logseal_UNBOUND_v1.py', parent, text, edits)
    checks = []

    def check(name, value):
        assert value, name
        checks.append(name)

    # Executing these modules is stdlib only. The zero pair hash must reject
    # every attempted scientific job before any model/runtime body is reached.
    native = load('_unbound_future_owned_ABI_native', h.checked(native_pin))
    check('scientific pair remains unbound', native.PAIR_SHA == '0' * 64)
    try:
        native.validate_job({})
    except ValueError as error:
        check('unbound native refuses before job reads', 'UNBOUND template' in str(error))
    else:
        raise AssertionError('Unbound native accepted a job')
    original_native = ast.parse(h.checked(base['native']).read_text())
    current_native = ast.parse(h.checked(native_pin).read_text())
    functions = lambda tree: {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
    old, new = functions(original_native), functions(current_native)
    check('native function inventory unchanged', set(old) == set(new))
    for name in old:
        if name not in ('validate_job', 'run'):
            check('native unchanged ' + name, old[name] == new[name])
    tree = ast.parse(h.checked(native_pin).read_text())
    exports = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == 'put' and len(n.args) >= 2 and isinstance(n.args[0], ast.BinOp)
        and isinstance(n.args[0].right, ast.Constant) and n.args[0].right.value == 'result.json')
    fields = {v.arg for v in exports.args[1].keywords}
    reviewer = h.pin(F / 'future-owned-overlap-observer-reviewer-original02/review_owned_overlap_fullgame_UNBOUND_v1.py')
    review_tree = ast.parse(h.checked(reviewer).read_text())
    needs = {n.slice.value for n in ast.walk(review_tree) if isinstance(n, ast.Subscript)
        and isinstance(n.value, ast.Name) and n.value.id == 'result' and isinstance(n.slice, ast.Constant)
        and isinstance(n.slice.value, str)}
    check('all reviewer primary result fields exported', needs <= fields)
    check('compile report explicitly exported', 'compile_report' in fields)
    old_sequence = ast.parse(h.checked(sequence_preparation['source']).read_text())
    new_sequence = ast.parse(h.checked(sequence_pin).read_text())
    old_functions, new_functions = functions(old_sequence), functions(new_sequence)
    check('only added qualified seal helper', set(new_functions) == set(old_functions) | {'seal_closed_log'})
    for name in old_functions:
        check('sequence top-level helper unchanged ' + name, old_functions[name] == new_functions[name])
    copied = next(n for n in new_sequence.body if isinstance(n, ast.FunctionDef) and n.name == 'seal_closed_log')
    check('seal kernel exact qualified AST', ast.dump(copied) == ast.dump(seal_function))
    old_class = next(n for n in old_sequence.body if isinstance(n, ast.ClassDef) and n.name == 'Sequence')
    new_class = next(n for n in new_sequence.body if isinstance(n, ast.ClassDef) and n.name == 'Sequence')
    old_methods, new_methods = functions(old_class), functions(new_class)
    check('sequence method inventory unchanged', set(old_methods) == set(new_methods))
    for name in old_methods:
        if name != 'run':
            check('sequence method unchanged ' + name, old_methods[name] == new_methods[name])
    check('no numerical runtime imported', 'torch' not in sys.modules and 'numpy' not in sys.modules)
    report = h.put(output / 'CPU-source-composition-contracts.json', dict(
        status='PASS_FUTURE_UNBOUND_SOURCE_COMPOSITION_ONLY', tests_run=len(checks), checks=checks,
        native=native_pin, sequence=sequence_pin, required_reviewer_primary_fields=sorted(needs),
        exported_primary_result_fields=sorted(fields), derivations=deltas,
        existing_early_C1_eligibility_authentication_and_all_game_predicates_retained=True,
        prior_full64_engineering_qualification=engineering_pin, native_capacity_or_promotion_gates_changed=False,
        current_owned_health=health_pin, current_owned_overlap=owned_pin,
        slot_closeout=base['slot_closeout'], wire_auditor=base['wire_auditor'],
        real_scientific_case_pair_sourcefamily_binding_and_preflight_still_required=True,
        actual_active_screen_modified=False, live_qualification_claimed=False,
        source_builder=h.pin(Path(__file__)), promotion=False))
    print(json.dumps(dict(status='PASS_FUTURE_UNBOUND_SOURCE_COMPOSITION_ONLY', tests_run=len(checks),
        reviewer_primary_fields=len(needs), report={k: report[k] for k in ('path', 'sha256', 'bytes')})))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.execute:
        assert a.output
        execute(a.output)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
