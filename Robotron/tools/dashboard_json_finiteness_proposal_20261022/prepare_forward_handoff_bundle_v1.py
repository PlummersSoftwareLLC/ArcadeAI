"""Derive a dashboard-only, current-owner handoff proposal from deployed code.

This writes immutable proposal sources. It does not construct a live backend,
select a live plan, change production files, or operate services/cgroups.
"""
import argparse
import ast
import difflib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
H = R/'dashboard-JSON-production-continuity-main-inputs-original01-preparation-20261022'
PRIOR = R/'profile06-production-continuity-live-controller-original01-preparation-20261021'
PREPARED_SHA = 'c27c57a591702df5c12a0dc563633d99b58a176130748a06b1e8e418e49d98ca'


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY')
        return 0
    spec = importlib.util.spec_from_file_location('_JSON_forward_bundle_h', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = h
    spec.loader.exec_module(h)
    require(h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'Helper changed')
    prepared_pin = h.pin(H/'prepared-inputs.json')
    require(prepared_pin['sha256'] == PREPARED_SHA, 'New inputs changed')
    prepared = json.loads(h.checked(prepared_pin).read_bytes())
    prior_plan_pin = h.pin(PRIOR/'plan.json')
    require(prior_plan_pin['sha256'] == 'ebaaf494d421532cfdc2ae94ae4fb5d99bef29bd529b642d18e6b29d8f4a4122', 'Deployed prior plan changed')
    prior_plan = json.loads(h.checked(prior_plan_pin).read_bytes())
    out = H/'sources-original01'
    require(not out.exists(), 'Original source construction already consumed')
    out.mkdir(mode=0o700)

    def replace(raw, old, new, count):
        require(raw.count(old) == count, 'Unexpected source replacement count: '+old)
        return raw.replace(old, new)

    def publish(path, raw):
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        return h.pin(path)

    pins = {}
    changes = {}
    for name in ('handoff_controller_v1.py', 'handoff_linux_v1.py', 'handoff_poststop_v1.py',
                 'handoff_recovery_v1.py', 'handoff_socket_seal_v1.py', 'bank_shutdown_intent_v1.py'):
        entry = prior_plan['sources'][name]
        original = h.checked(entry).read_bytes()
        raw = original.decode()
        if name == 'handoff_linux_v1.py':
            for old, new, count in (
                ('84901c887437e99873d65c2348f18ca9e2f022a393f3c5282d68064c9f1fbf40', prepared['installed_before']['sha256'], 1),
                ('b552b2e83a9cc10cf7e4125cef22f571abe9189bd2ad3e63c6f48aa7df0e4516', prepared['proposed_source']['sha256'], 1),
                ("self.prepared['proposed_socket']", "self.prepared['proposed_source']", 1),
                ("and self.prepared['proposed_source']['sha256'] == NEW_SOCKET_SHA,", "and self.prepared['proposed_source']['sha256'] == NEW_SOCKET_SHA\n                and self.prepared['selected_source_relative'] == 'Scripts/dqn/metrics_dashboard.py',", 1),
                ("self.owner['pid'] == 3170722", "self.owner['pid'] == 3295795", 1),
                ("self.owner['starttime_ticks'] == 52892579", "self.owner['starttime_ticks'] == 64995335", 1),
                ('f2896a1cbb3c4a94a7568ab83120d21e', '160d2b4b1f6e4e2f8839790658a7d01c', 1),
                ("['optimized_samples'] == 20238235648", "['optimized_samples'] == 27292198912", 1)):
                raw = replace(raw, old, new, count)
        if name in ('handoff_poststop_v1.py', 'handoff_recovery_v1.py'):
            raw = replace(raw, "'Scripts/dqn/socket_server.py'", "'Scripts/dqn/metrics_dashboard.py'", 1)
        if name == 'handoff_poststop_v1.py':
            raw = replace(raw, "b.prepared['proposed_socket']", "b.prepared['proposed_source']", 1)
        compile(raw, str(out/name), 'exec')
        pins[name] = publish(out/name, raw.encode())
        patch = ''.join(difflib.unified_diff(original.decode().splitlines(True), raw.splitlines(True), fromfile='deployed/'+name, tofile='proposed/'+name))
        changes[name] = dict(original=entry, proposed=pins[name], byte_identical=raw.encode() == original,
                             patch=publish(out/(name+'.patch'), patch.encode()))
    # The existing preparation entry point is inert by default. Bind it to the
    # exact new prepared inputs and source transaction, preserving its logic.
    prior_preparer = R/'profile06-production-continuity-main-inputs-original01-preparation-20261021/sources-v2/prepare_handoff_poststop_v1.py'
    entry = h.pin(prior_preparer)
    require(entry['sha256'] == 'ae74eeba644aff21a1c97cad95e1f69d1e4da7893c95ad17266e4a0c9d34614d', 'Pinned prior preparer required')
    original = h.checked(entry).read_bytes()
    raw = original.decode()
    for old, new, count in (
        ('profile06-production-continuity-main-inputs-original01-preparation-20261021', H.name, 1),
        ('ac0f2ff0bd79e0fc6c780585fd8899f8ba1cfeb0c16fd001b7ad024af55e2a5a', PREPARED_SHA, 1),
        ('scorecarry-profile06-main-original01-20261021', 'scorecarry-dashboardJSON-main-original01-20261022', 2),
        (r'scorecarry-profile06-main-original[0-9]{2}-20261021', r'scorecarry-dashboardJSON-main-original[0-9]{2}-20261022', 1),
        ("'proposed_socket'", "'proposed_source'", 1),
        ('full195_holds_and_original192_verified', 'full196_holds_and_original192_verified', 1)):
        raw = replace(raw, old, new, count)
    compile(raw, str(out/prior_preparer.name), 'exec')
    pins[prior_preparer.name] = publish(out/prior_preparer.name, raw.encode())
    changes[prior_preparer.name] = dict(original=entry, proposed=pins[prior_preparer.name],
        patch=publish(out/(prior_preparer.name+'.patch'), ''.join(difflib.unified_diff(
            original.decode().splitlines(True), raw.splitlines(True), fromfile='deployed/'+prior_preparer.name,
            tofile='proposed/'+prior_preparer.name)).encode()))
    # Show the exact scope, including unchanged OS/recovery primitives. The
    # parser-named result fields are retained as internal ABI compatibility.
    def bodies(raw):
        tree = ast.parse(raw)
        return {'.'.join(parents+[node.name]): ast.dump(node, include_attributes=False)
                for parents, node in walk(tree)}

    def walk(tree, parents=None):
        parents = parents or []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield parents, node
            elif isinstance(node, ast.ClassDef):
                yield from walk(node, parents+[node.name])

    allowed = {'handoff_linux_v1.py': {'LinuxBackend.__init__', 'LinuxBackend.preflight'},
               'handoff_poststop_v1.py': {'Poststop.install'}, 'handoff_recovery_v1.py': {'recover'},
               'prepare_handoff_poststop_v1.py': {'prepare', 'main'}}
    changed_bodies = {}
    for name, change in changes.items():
        before = bodies(h.checked(change['original']).read_bytes())
        after = bodies(h.checked(change['proposed']).read_bytes())
        require(set(before) == set(after), 'Handoff callable set changed')
        changed = {key for key in before if before[key] != after[key]}
        require(changed <= allowed.get(name, set()), 'Unselected handoff function changed: '+name)
        changed_bodies[name] = sorted(changed)
    main_binding = json.loads(h.checked(prepared['original_main']).read_bytes())
    guard = h.load('_JSON_forward_bundle_guard', R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')
    guard.owner_and_files(main_binding)
    result = h.put(H/'source-bundle-construction-original01.json', dict(
        schema='robotron-dashboard-only-current-owner-handoff-source-derivation-v1', status='SOURCES_PREPARED_UNEXECUTED',
        builder=h.pin(__file__), prepared=prepared_pin, prior_deployed_plan=prior_plan_pin, changes=changes,
        source_pins=pins, changed_function_bodies=changed_bodies,
        compatibility_note='OLD_SOCKET_SHA/NEW_SOCKET_SHA and parser result fields retain their deployed internal ABI names; values and sole target path bind only the exact dashboard source.',
        kernel_freeze_and_thaw_function_bodies_unchanged=True, controller_order_and_gates_byte_identical=True,
        socket_seal_and_bank_intent_byte_identical=True, original_scientific_review_remains_invalid=True,
        main_runtime_changed=False, production_changed=False, live_plan_selected=False,
        source_contract_tests_still_required=True, created_unix_s=time.time()))
    print(json.dumps(dict(result=result, sources=pins, changed_function_bodies=changed_bodies)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
