"""Bind original ABBA engineering sources/jobs without launching any case."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import textwrap
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
N = R / 'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025'
E = N / 'selector-active600-counterbalanced-engineering-original01'
OLD = R / 'native32-quota64-API-epoch-reference-load600-original01-preparation-20261024'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expression(source, name, value):
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.Assign)
             and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name]
    assert len(nodes) == 1, name
    node = nodes[0]
    lines = source.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = [name + '=' + value + '\n']
    return ''.join(lines)


def main():
    h = load(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', '_engprep_h')
    assert h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    cpu = load(G / 'tools/quality_capacity_proposal/control_quality32_review_v1.py', '_engprep_cpu')
    assert h.pin(cpu.__file__)['sha256'] == '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
    designpin = h.pin(E / 'controlled-engineering-design-precommit.json')
    assert designpin['sha256'] == '5b57de8e6ba55561acd5873143ca3ab209d4d23cc27bef04bc3b98291ff44d67'
    design = json.loads(h.checked(designpin).read_bytes())
    state = json.loads((G / 'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    assert design['common_runtime']['main_binding'] == state['current_main_binding']
    oldjob = json.loads((OLD / 'job.json').read_bytes())
    oldcfg = json.loads((OLD / 'controller-config.json').read_bytes())
    oldguard = json.loads((OLD / 'source-family-guards-CPU-original01/precommit.json').read_bytes())
    oldfamily = json.loads(h.checked(oldjob['source_family_manifest']).read_bytes())
    oldprotocol = json.loads(h.checked(oldjob['main_health_protocol']).read_bytes())
    originalpin = oldjob['runtime']
    assert originalpin['sha256'] == '84be266c203dc27192c16bfd8deb6bbb4c78590a138aeb6c039fff7e90a05e73'
    original = h.checked(originalpin).read_text()
    timingpin = state['current_controlled_engineering_experiment']['common_timing_source']
    assert timingpin['sha256'] == 'f66774301b045b2c668d12dda19fe14cd06a207ba2b59ab7b7326c88ac990cc2'
    h.checked(timingpin)
    implementations = E / 'implementations'
    implementations.mkdir(mode=0o700)
    records = []

    def write(path, source):
        compile(source, str(path), 'exec')
        with path.open('xb') as stream:
            stream.write(source.encode()); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        return h.pin(path)

    def exact(source, old, new):
        assert source.count(old) == 1, old[:120]
        return source.replace(old, new)

    # Extract the existing complete predicate into a callable used by run itself.
    original_run = next(n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    protocol_node = next(n for n in ast.walk(original_run) if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == 'require'
        and "protocol['schema']" in (ast.get_source_segment(original, n) or ''))
    old_protocol_block = ''.join(original.splitlines(keepends=True)[protocol_node.lineno - 1:protocol_node.end_lineno])
    predicate = 'def validate_main_health_contract(job,protocol,family):\n' + textwrap.indent(ast.unparse(protocol_node), '    ') + '\n\n'
    assert ast.dump(ast.parse(predicate).body[0].body[0]) == ast.dump(protocol_node)
    common = exact(original, old_protocol_block, '        validate_main_health_contract(job,protocol,family)\n')
    common = exact(common, 'def run(job,jp,h):', predicate + 'def run(job,jp,h):')
    common = expression(common, 'DIAGNOSTIC_SHA', repr(designpin['sha256']))
    common = expression(common, 'REFERENCE_SHA', repr(design['reference_policy']['sha256']))
    common = expression(common, 'REFERENCE_CLOCKS', repr(design['reference_saved_clocks']))
    common = exact(common, "and job['wall_limit_s']==720", "and job['wall_limit_s']==960")
    common = exact(common, "    output=Path(job['output'])\n", """    require(job['engineering_implementation']==IMPLEMENTATION and job['engineering_case']in CASE_NAMES
        and job['selector_timing_source']['sha256']==TIMING_SOURCE_SHA,
        'Exact original engineering case and common timing source required')
    output=Path(job['output'])
""")
    common = exact(common, '    started=time.monotonic();deadline=started+job[\'wall_limit_s\']\n',
        "    timing_api=selector_timing=selector_timing_report=active_start=active_end=active_rate_report=None\n"
        "    started=time.monotonic();deadline=started+job['wall_limit_s']\n")
    common = exact(common, '        sys.path.insert(0,str(COMPONENTS));sys.path.insert(0,str(Path(__file__).resolve().parent))\n',
        '        sys.path.insert(0,str(COMPONENTS));sys.path.insert(0,str(BRIDGE_COMPONENTS))\n')
    common = exact(common, '        CohortDrain=quota_drain.CohortDrain\n',
        "        timing_api=load('_engineering_selector_timing',h.checked(job['selector_timing_source']))\n"
        "        selector_timing=timing_api.SelectorTiming(quota_view.FixedSlotCohortView,job['quota64_source_pins']['view']['sha256'])\n"
        '        CohortDrain=quota_drain.CohortDrain\n')
    stop_node = next(n for n in ast.walk(original_run) if isinstance(n, ast.If)
                     and ast.unparse(n.test).startswith('time.monotonic() - started >= 600'))
    old_stop = ''.join(original.splitlines(keepends=True)[stop_node.lineno - 1:stop_node.end_lineno])
    new_stop = """            prefixes_ready=len(actors)==32 and all(row['proxy'].prefix_verified.is_set()for row in actors.values())
            if active_start is None:
                if prefixes_ready and fixed_window is not None and boundary(controller.generation)['ready']:
                    active_start=timing_api.active_endpoint(actors)
                    h.put(output/'original-active32-start.json',active_start)
                else:
                    require(time.monotonic()-started<300,'Original active32 anchor not established within300s')
            if active_start is not None and time.monotonic_ns()-active_start['midpoint_monotonic_ns']>=600_000_000_000:
                active_end=timing_api.active_endpoint(actors)
                rates=timing_api.window_rates(active_start,active_end)
                require(rates['midpoint_elapsed_s']>=600,'Original active window shortened')
                active_rate_report=h.put(output/'original-active32-frame-rate.json',rates)
                h.put(output/'original-all32-prefix-diagnostic-stop.json',dict(
                    reason='PRECOMMITTED_ACTIVE600_SELECTOR_LOAD_STOP',active_rate_report=active_rate_report,
                    observed_unix_s=time.time(),observed_monotonic_s=time.monotonic(),
                    prefixes={str(slot):row['proxy'].prefix_summary for slot,row in actors.items()},quality_qualified=False))
                raise ValueError('PRECOMMITTED_ACTIVE600_SELECTOR_LOAD_STOP_NOT_A_QUALITY_RESULT')
"""
    common = exact(common, old_stop, new_stop)
    common = exact(common, '                    main_observations=len(main_samples),errors=list(errors))\n',
        '                    active_start=active_start,main_observations=len(main_samples),errors=list(errors))\n')
    common = exact(common, "    try:\n        for entry in job['inputs']+package_pins:h.checked(entry)\n", """    if selector_timing is not None:
        try:
            require(all_threads_stopped and child_reap and child_reap['all_original_children_reaped'],
                'Cannot seal selector timings before original writers close')
            selector_timing_report=h.put(output/'original-selector-call-timing.json',selector_timing.finish())
        except Exception as error:errors.append('Original selector timing close: '+repr(error))
    try:
        for entry in job['inputs']+package_pins:h.checked(entry)
""")
    common = exact(common, '        before_intentional_stop=before_stop,after_intentional_stop=after_stop,controller_exit=controller_exit,\n',
        '        selector_call_timing=selector_timing_report,active_start=active_start,active_end=active_end,active_frame_rate=active_rate_report,\n'
        "        engineering_case=job['engineering_case'],engineering_implementation=job['engineering_implementation'],\n"
        '        before_intentional_stop=before_stop,after_intentional_stop=after_stop,controller_exit=controller_exit,\n')
    common += '\n'
    common = exact(common, "COMPONENTS=Path(", "BRIDGE_COMPONENTS=Path(" + repr(str(Path(design['common_bridge']['path']).parent)) + ")\n"
        'TIMING_SOURCE_SHA=' + repr(timingpin['sha256']) + "\nIMPLEMENTATION='UNBOUND'\nCASE_NAMES=()\nCOMPONENTS=Path(")
    templatepin = write(implementations / 'native-active600-common-UNBOUND-template.py', common)
    bindings = {}
    for name in ('A', 'B'):
        directory = implementations / name
        directory.mkdir(mode=0o700)
        components = {}
        for key in ('view', 'drain'):
            sourcepin = design['implementations'][name][key]
            components[key] = write(directory / Path(sourcepin['path']).name, h.checked(sourcepin).read_text())
            assert components[key]['sha256'] == sourcepin['sha256']
        components['bridge'] = design['common_bridge']
        text = expression(common, 'COMPONENTS', 'Path(' + repr(str(directory)) + ')')
        text = expression(text, 'IMPLEMENTATION', repr(name))
        cases = tuple(item['case'] for item in design['ordered_cases'] if item['implementation'] == name)
        text = expression(text, 'CASE_NAMES', repr(cases))
        for key in ('view', 'drain'):
            text = text.replace(design['implementations']['A'][key]['sha256'], components[key]['sha256'])
        runtimepin = write(directory / 'run_native32_selector_active600_v1.py', text)
        original_defs = {n.name: ast.dump(n) for n in ast.parse(original).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        changed_defs = {n.name: ast.dump(n) for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        assert all(changed_defs[k] == v for k, v in original_defs.items() if k not in ('run', 'validate_job'))
        controltext = h.checked(oldguard['native_controller']).read_text()
        controltext = exact(controltext, oldjob['runtime']['path'], runtimepin['path'])
        controlpin = write(directory / 'control_native32_selector_active600_v1.py', controltext)
        bindings[name] = dict(runtime=runtimepin, native_controller=controlpin, quota64_components=components)

    oldguardtext = h.checked(oldguard['runner']).read_text()
    guardtext = exact(oldguardtext, "('wall_limit_s',721)", "('wall_limit_s',961)")
    insertion = """        def test_actual_engineering_preparer_fixture_protocol_is_native_contract(self):
            fixture=read(job['initializer_fixture_job'])
            self.assertEqual(runtime.validate_job(fixture),Path(fixture['output']))
            actual_protocol=read(fixture['main_health_protocol'])
            actual_family=read(fixture['source_family_manifest'])
            runtime.validate_main_health_contract(fixture,actual_protocol,actual_family)
            self.assertEqual(actual_protocol,protocol)
            self.assertFalse(Path(fixture['output']).exists())
            wrong=dict(actual_protocol,schema='robotron-native-quota64-dedicated-main-health-protocol-v1')
            with self.assertRaisesRegex(ValueError,'Exact prospective main-health'):
                runtime.validate_main_health_contract(fixture,wrong,actual_family)
            negative_cases.append('scientific-schema-cannot-replace-engineering-protocol')

"""
    guardtext = exact(guardtext, '        def test_default_native_and_controller_entrypoints_are_inert(self):\n',
                      insertion + '        def test_default_native_and_controller_entrypoints_are_inert(self):\n')
    guardtext = exact(guardtext, "        native_runtime=native['runtime'],successful=result.wasSuccessful(),tests_run=result.testsRun,\n",
        "        native_runtime=native['runtime'],initializer_fixture_job=job['initializer_fixture_job'],successful=result.wasSuccessful(),tests_run=result.testsRun,\n")
    guardpin = write(implementations / 'validate_active600_native_family_v1.py', guardtext)

    for item in design['ordered_cases']:
        name, implementation = item['case'], item['implementation']
        directory = E / name
        directory.mkdir(mode=0o700)
        guards = directory / 'source-family-guards-CPU-original01'
        guards.mkdir(mode=0o700)
        fixture_root = directory / 'explicit-never-launched-initializer-fixture'
        fixture_root.mkdir(mode=0o700)
        (fixture_root / 'source-family-guards-CPU-original01').mkdir(mode=0o700)
        binding = bindings[implementation]
        family = copy.deepcopy(oldfamily)
        family.update(runtime=binding['runtime'], diagnostic_precommit=designpin,
            quota64_components=binding['quota64_components'], selector_timing_source=timingpin,
            engineering_case=name, source_family_engineering_only=True,
            exact_native_resources_or_active_load_verified=False)
        familypin = h.put(directory / 'diagnostic-source-family.json', family)
        main = json.loads(h.checked(state['current_main_binding']).read_bytes())
        origins = {}
        for actor in main['actors']:
            log = Path(os.readlink('/proc/' + str(actor['pid']) + '/fd/1'))
            stat = log.stat()
            assert log.resolve().is_relative_to(G / 'logs')
            origins[str(actor['slot'])] = dict(path=str(log), device=stat.st_dev, inode=stat.st_ino)
        protocol = copy.deepcopy(oldprotocol)
        protocol['health_job'].update(binding=state['current_main_binding'], log_origins=origins)
        assert protocol['prior_case'] is None
        protocolpin = h.put(directory / 'diagnostic-main-health-protocol.json', protocol)
        job = copy.deepcopy(oldjob)
        job.update(created_unix_s=time.time(), runtime=binding['runtime'], output=str(directory / 'diagnostic-output-original01'),
            checkpoint=design['reference_policy'], expected_policy_clocks=design['reference_saved_clocks'],
            wall_limit_s=960, label='selector-active600-' + name.lower() + '-original01-20261025',
            main_binding=state['current_main_binding'], source_family_manifest=familypin,
            main_health_protocol=protocolpin, diagnostic_precommit=designpin,
            engineering_case=name, engineering_implementation=implementation, selector_timing_source=timingpin,
            quota64_source_pins=binding['quota64_components'],
            sessions={str(slot): secrets.token_hex(16) for slot in range(4096, 4128)},
            connections={str(slot): secrets.token_hex(16) for slot in range(4096, 4128)},
            prelaunch_family_guard_closeout=str(guards / 'independent-original-family-guards-and-CPU-closeout.json'))
        additions = [designpin, familypin, protocolpin, state['current_main_binding'], timingpin,
            binding['runtime'], binding['native_controller'], *binding['quota64_components'].values(),
            design['reference_policy'], design['reference_CPU_report'], design['source_lineage']['new_actual_journal_alias_guards'],
            design['source_lineage']['new_actual_source_and_initializer_guards'], design['source_lineage']['bounded_display_guard_closeout'],
            state['current_controlled_engineering_experiment']['common_timing_guard_closeout']]
        job['inputs'] = list({pin['path']: pin for pin in [*oldjob['inputs'], *additions]}.values())
        for pin in job['inputs']:
            h.checked(pin)
        jobpin = h.put(directory / 'job.json', job)
        fixture = copy.deepcopy(job)
        fixture.update(output=str(fixture_root / 'diagnostic-output-original01'), initializer_fixture_only=True,
            prelaunch_family_guard_closeout=str(fixture_root / 'source-family-guards-CPU-original01/independent-original-family-guards-and-CPU-closeout.json'))
        fixturepin = h.put(fixture_root / 'job.json', fixture)
        config = copy.deepcopy(oldcfg)
        config.update(unit='robotron-compiled-full-tail32-integration-selector-active600-' + name.lower() + '-original01-20261025.service',
            output=str(directory / 'execution-original01'))
        config['argv'][4] = binding['runtime']['path']
        config['argv'][config['argv'].index('--job') + 1] = jobpin['path']
        config['argv'][config['argv'].index('--job-sha256') + 1] = jobpin['sha256']
        config['argv'][config['argv'].index('--source-sha256') + 1] = binding['runtime']['sha256']
        config['pins'] = [cpu.pin(pin['path']) for pin in [*job['inputs'], jobpin]]
        configpin = h.put(directory / 'controller-config.json', config)
        guardjob = dict(oldguard, directory=str(guards), report=str(guards / 'original-native-family-guards.json'),
            native_job=jobpin, native_config=configpin, native_controller=binding['native_controller'],
            runner=guardpin, main_monitor=state['current_main_monitor'], diagnostic_precommit=designpin,
            original_native_runtime=originalpin, initializer_fixture_job=fixturepin,
            expected_guard_methods=12, original_attempt=1, no_retry=True)
        guardjob['inputs'] = list({pin['path']: pin for pin in [*job['inputs'], jobpin, fixturepin,
            configpin, guardpin, oldguard['original_bridge'], oldguard['helper'], oldguard['reader'],
            state['current_main_monitor']]}.values())
        guardjobpin = h.put(guards / 'precommit.json', guardjob)
        cpuconfig = dict(unit='robotron-selector-active600-' + name.lower() + '-family-CPU-original01-20261025.service',
            output=str(guards / 'execution-original01'),
            argv=['/usr/bin/python3.12', '-I', '-B', guardpin['path'], '--run-guards', '--job', guardjobpin['path'], '--job-sha256', guardjobpin['sha256']],
            properties=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0', 'RuntimeMaxSec=180',
                        'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'],
            pins=[cpu.pin(pin['path']) for pin in [guardjobpin, *guardjob['inputs']]], observation_s=240)
        cpupin = h.put(guards / 'controller-config.json', cpuconfig)
        records.append(dict(case=name, implementation=implementation, native_job=jobpin,
            native_controller=binding['native_controller'], native_config=configpin,
            source_guard_job=guardjobpin, source_guard_CPU_config=cpupin, initializer_fixture=fixturepin,
            original_native_launched=False))
    proofpin = h.put(E / 'source-bindings-and-original-case-preparation.json', dict(
        schema='robotron-selector-active600-source-and-case-preparation-v1', design=designpin,
        original_runtime=originalpin, common_native_template=templatepin, implementations=bindings,
        common_timing=timingpin, guard_source=guardpin, original_guard_source=oldguard['runner'],
        unchanged_original_native_helpers_except_run_and_validate_job=True,
        original_protocol_predicate_AST_preserved_in_actual_run_consumer=True,
        all_original_native_controllers_unlaunched=True, actual_initializer_guard_still_required=True,
        original_resource_limits_unchanged=True, cases=records, no_Torch_MAME_or_worker_started=True))
    print(json.dumps(dict(preparation=proofpin, cases=[dict(case=r['case'], CPU_config=r['source_guard_CPU_config']) for r in records])))


if __name__ == '__main__':
    main()
