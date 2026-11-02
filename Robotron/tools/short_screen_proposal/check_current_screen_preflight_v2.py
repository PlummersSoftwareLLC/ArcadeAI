"""CPU contracts and read-only live preflight for the fresh short screen.

Never imports Torch, launches an emulator/GPU body, or edits Main controls.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import fcntl
import subprocess
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--case', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if not a.execute:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    h = load('_fresh_preflight_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    read = lambda entry: json.loads(h.checked(entry).read_bytes())
    packet = read(h.pin(a.case / 'prepared-with-independent-review-NOT-LAUNCHED.json'))
    prepared_pin = packet['prepared']
    prepared = read(prepared_pin)
    selected = read(prepared['selection'])
    native = load('_fresh_preflight_native', h.checked(prepared['selected_sources']['native']))
    outer = load('_fresh_preflight_outer', h.checked(prepared['selected_sources']['outer']))
    controller = load('_fresh_preflight_controller', h.checked(prepared['selected_sources']['controller']))
    sources = read(h.pin(a.case / 'exact-parent-derivations.json'))
    reader = load('_fresh_preflight_reader', h.checked(prepared['independent_review']['reader']))
    auditor = load('_fresh_preflight_owned_Main_auditor', h.checked(prepared['independent_owned_Main_auditor']))
    # Use the exact independent review reader before any native launch.
    # Source hashes alone do not satisfy its immutable-file contract.
    strict_review_sources=[prepared['horizon_checkpoint_auditor'],
        prepared['independent_owned_Main_auditor'],prepared['independent_review']['source']]
    for role in ('R1','C1'):
        selected_job=read(prepared['jobs'][role]['job'])
        strict_review_sources += [selected_job['screen_support'],selected_job['components']['prefix_auditor'],
            selected_job['components']['score_auditor']]
    for selected_source in strict_review_sources:
        reader.read_pin(selected_source,as_json=False)
    checks = []

    def check(name, value):
        assert value, name
        checks.append(name)

    def rejects(name, job, operation):
        try:
            operation(job)
        except (AssertionError, ValueError, RuntimeError, KeyError):
            checks.append(name)
            return
        raise AssertionError('Invalid context accepted: ' + name)

    first = read(prepared['jobs']['R1']['job'])
    derivation = next(v for v in sources['changes'] if v['role'] == 'native')
    original = h.checked(derivation['parent']).read_text()
    current = h.checked(derivation['selected']).read_text()
    old_functions = {n.name: n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef)}
    new_functions = {n.name: n for n in ast.parse(current).body if isinstance(n, ast.FunctionDef)}
    check('native function inventory unchanged', set(old_functions) == set(new_functions))
    for name in old_functions:
        if name not in ('run', 'validate_completed_context'):
            check('unchanged native function ' + name, ast.dump(old_functions[name]) == ast.dump(new_functions[name]))
    run = ast.get_source_segment(current, new_functions['run'])
    old = "        main_guard=context['support'].CurrentMainHealth(job,output,h);main_guard.start()"
    new = "        main_module=load('_short_screen_actual_owned_Main',h.checked(job['current_v6_health_source']))\n        main_guard=main_module.CurrentV6MainHealth(job,output,h);main_guard.start()"
    check('native run changes only Main observer construction', ast.dump(ast.parse(run.replace(new, old)))
          == ast.dump(ast.parse(ast.get_source_segment(original, old_functions['run']))))
    profile = read(sources['parent_duration_profile'])
    check('all12 qualified scoring and retirement component pins unchanged', first['components'] == profile['components'])
    check('no early promotion or decision scope', selected['screen_only'] is True and selected['promotion'] is False
          and selected['short_screen_is_promotion_evidence'] is False)
    check('explicit matched15minute horizon', selected['screen_horizon_ns'] == 900_000_000_000
          and selected['checkpoint_offsets_ns'] == [300_000_000_000, 600_000_000_000])
    check('outer independent review retained', callable(outer.review_original_arm))
    seal_parent = load('_preflight_original_seal', h.checked(prepared['selected_sources']['post_writer_log_seal_parent']))
    import inspect
    check('same qualified post-writer log-seal AST', ast.dump(ast.parse(inspect.getsource(outer.seal_closed_log)))
          == ast.dump(ast.parse(inspect.getsource(seal_parent.seal_closed_log))))

    for key, damage in [('float_horizon', lambda j: j.update(horizon_ns=900_000_000_000.0)),
                        ('bool_horizon', lambda j: j.update(horizon_ns=True)),
                        ('unknown_horizon', lambda j: j.update(horizon_ns=1_200_000_000_000)),
                        ('retry', lambda j: j.update(attempt=2)),
                        ('missing_slot', lambda j: j['actor_slots'].pop()),
                        ('duplicate_transport', lambda j: j['sessions'].update({'4097': j['sessions']['4096']}))]:
        job = copy.deepcopy(first)
        damage(job)
        rejects('reject ' + key, job, native.validate_job)
    for key, damage in [('wrong_current_Main', lambda j: j['current_main']['owner'].update(pid=1)),
                        ('wrong_fleet', lambda j: j['current_fleet']['supervisor'].update(pid=1)),
                        ('changed_clocks', lambda j: j['expected_policy_clocks'].update(training_steps=1)),
                        ('changed_health_source', lambda j: j['current_v6_health_source'].update(sha256='0' * 64)),
                        ('mixed_selected_horizon', lambda j: j.update(horizon_ns=600_000_000_000))]:
        job = copy.deepcopy(first)
        damage(job)
        rejects('reject ' + key, job, lambda j: native.validate_completed_context(j, h))

    rows = []
    tokens = set()
    configs = read(prepared['controller_configs'])
    for leg in ('R1', 'C1'):
        job = read(prepared['jobs'][leg]['job'])
        for entry in job['inputs']:
            h.checked(entry)
        h.checked(job['checkpoint'])
        context = native.validate_completed_context(job, h)
        check(leg + ' real package/context ABI', len(context['modules']) == 12 and len(context['package_pins']) == 123)
        config = controller.checked_config(h.checked(configs['configs'][leg]))
        check(leg + ' exact selected runtime argv', config['argv'] == prepared['jobs'][leg]['argv'])
        for suffix in ('.service', '.timer'):
            check(leg + ' fresh unit ' + suffix, controller.show(config['unit'].removesuffix('.service') + suffix)['LoadState'] == 'not-found')
        tokens.update(job['sessions'].values()); tokens.update(job['connections'].values())
        cpu_entry = prepared['independent_review']['CPU_controller']
        cpu = load('_preflight_original_CPU_' + leg, h.checked(cpu_entry))
        cpu_config = prepared['independent_review']['configs'][leg]
        cpu.checked_config(h.checked(cpu_config))
        check(leg + ' independent review precommitted', not Path(prepared['independent_review']['reports'][leg]).exists())
        # Run the actual qualified physical observer, then independently replay
        # its retained samples through the exact selected review statements.
        health = load('_fresh_preflight_health_' + leg, h.checked(job['current_v6_health_source']))
        output = a.case / ('preflight-owned-Main-' + leg + '-original01')
        output.mkdir(mode=0o700)
        guard = health.CurrentV6MainHealth(job, output, h)
        guard.start()
        guard.observe()
        time.sleep(5.1)
        guard.observe()
        main_report = guard.finish(None)
        result = dict(main_samples=guard.samples, main_health_report=main_report, main_observer_lifecycle=guard.lifecycle)
        audit = auditor.audit_main(job, result, lambda pin: reader.read_pin(pin), h)
        check(leg + ' actual owned Main samples independently replay', audit['accepted'] >= 2 and audit['all_logical_clocks_advanced'])
        rows.append(dict(leg=leg, main_report=main_report, independent_Main_audit=audit))
    check('all128 transport identities fresh and distinct', len(tokens) == 128)
    port_check = outer.wait_for_job_ports(first)
    check('all33 original selected ports bindable', port_check['status'] == 'PORTS_FREE_BEFORE_LAUNCH')
    with open(first['lease']['path'], 'r+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        check('same permanent coordinator free', h.pin(first['lease']['path']) == first['lease'])
        fcntl.flock(stream, fcntl.LOCK_UN)
    gpu = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory', '--format=csv,noheader'],
        capture_output=True, text=True, timeout=15)
    check('private GPU0 idle', gpu.returncode == 0 and first['gpu_uuid'] not in gpu.stdout)
    check('no numerical runtime imported', 'torch' not in sys.modules)
    report = h.put(a.output, dict(status='PASS', observed_unix_s=time.time(), tests_run=len(checks), checks=checks,
        prepared=prepared_pin, rows=rows, port_check=port_check, GPU_query=gpu.stdout,
        main_or_controls_changed=False, private_runtime_launched=False, statistical_confidence_qualified=False,
        test_source=h.pin(Path(__file__)), promotion=False))
    print(json.dumps(dict(status='PASS', tests_run=len(checks), report={k: report[k] for k in ('path', 'sha256', 'bytes')})))


if __name__ == '__main__':
    main()
