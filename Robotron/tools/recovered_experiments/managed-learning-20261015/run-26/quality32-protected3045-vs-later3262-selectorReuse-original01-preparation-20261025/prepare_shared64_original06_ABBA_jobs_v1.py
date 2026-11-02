"""Prepare single-use prospective ABBA jobs; never launch native work.

New native jobs fail before acquiring the GPU lease until their exact original
CPU family-guard closeouts exist. Native qualification is a separate step.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).resolve().parent
P = N / 'future-capacity64-shared-slot-domain-UNSELECTED-original01/runtime-family-original03'
E = N / 'evaluator-count-active600-counterbalanced-engineering-original06'
ORDER = ('01-A1-control', '02-B1-capacity64', '03-B2-capacity64', '04-A2-control')


def load(name, path, digest):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def write_source(path, text, h):
    compile(text, str(path), 'exec')
    with path.open('xb') as f:
        f.write(text.encode());f.flush();os.fchmod(f.fileno(), 0o444);os.fsync(f.fileno())
    return h.pin(path)


def prepare():
    h = load('_capacity_native_prep_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
             '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    cpu = load('_capacity_native_prep_cpu', G / 'tools/quality_capacity_proposal/control_quality32_review_v1.py',
               '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14')
    state = json.loads((G / 'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    assert state['scientific_job_running'] is False and state['source_freeze'] is False
    assert state['all_current_original_scientific_handles_terminal'] is True
    failed_pin = state['last_closed_original_scientific_campaign']
    assert failed_pin['sha256'] == '7361fb02997c08e1d6f9bac9f84be5945151e549b8c35a9e23c896c9b0498074'
    failure = json.loads(h.checked(failed_pin).read_bytes())
    assert failure['original_scientific_case_closed'] is True and failure['quality_qualified'] is False
    manifest_pin = h.pin(N / 'future-coalescing-raw-reviewer-provenance-original01/current-main-reviewer-templates-original01/readiness.json')
    assert manifest_pin['sha256'] == 'e6ae0882a4c56872ae8b3a40d8f4e3afcf00a196dbb3705e9975060b1efd6e17'
    manifest = json.loads(h.checked(manifest_pin).read_bytes())
    proof = json.loads(h.checked(manifest['CPU15_original_closeout']).read_bytes())
    assert proof['passed'] is True and proof['tests_run'] == 15 and proof['actual_tool_terminal_exit'] == 0
    index_pin = h.pin(N / 'future-coalescing-raw-reviewer-provenance-original01/current-main-reviewer-templates-original01/index.json')
    assert index_pin['sha256'] == '623d54b769a2551a80d4c6b95054037404920f3948c439122eeeb60b916460bd'
    templates = {c['role']:c for c in json.loads(h.checked(index_pin).read_bytes())['cases']}
    assert not E.exists(), 'One original preparation; never overwrite/retry cases'
    E.mkdir(mode=0o700)
    source_root = E / 'reviewer-sources';source_root.mkdir(mode=0o700)
    reviewers = {}
    complete = json.loads(h.checked(manifest['complete_family_CPU8']).read_bytes())
    assert complete['actual_tool_terminal_exit'] == 0 and complete['tests_run'] == 10
    assert complete['actual32_and64_pre_MAME_seed_and_proxy_constructor_loops_passed'] is True
    assert complete['actual_free_threaded_cold_native_imports32_and64_verified'] is True
    assert complete['main_observer_coalescing_dependencies_and_old_sources_refusal_passed'] is True
    observer=json.loads(h.checked(manifest['observer_component_CPU']).read_bytes())
    assert observer['actual_tool_terminal_exit']==0 and observer['live_control_coalesced_without_losing_raw']is True
    assert observer['actual_protocol']['sha256']=='0ec8510b82783b6d47cad99ba63c59045f32e5b9acf6dbfa128b308f9641d2b9'
    assert manifest['current_main_binding'] == state['current_main_binding'] == observer['current_main_binding']
    assert manifest['current_main_monitor'] == state['current_main_monitor'] == observer['current_main_monitor']
    assert manifest['current_main_context_CPU'] == manifest['observer_component_CPU']
    assert manifest['current_main_context_CPU']['sha256'] == '1ea379b440a56a28de41cf334b2a64ccfee40a959b50fce373bbff9e3e8b7bfc'
    assert observer['original500ms_freshness_and_max_gap_limits_unchanged'] is True
    chain=json.loads(h.checked(manifest['raw_reviewer_protocol_chain_CPU']).read_bytes())
    assert chain['passed'] is True and chain['tests_run']==8 and chain['actual_tool_terminal_exit']==0
    assert chain['actual_A32_B64_raw_reviewer_protocol_boundary_executed'] is True
    assert chain['full_raw_native_review_verified'] is False
    assert chain['original05_still_invalid'] is True
    assert state['last_failed_original_capacity_experiment']['sha256'] == 'ae1ae37dce0e8dde9056a82411a43cc142fce50961a8435d22036efb2627b7a5'
    for role, template in templates.items():
        parent = template['sources']['reviewer']
        text = h.checked(parent).read_text()
        reviewers[role] = write_source(source_root / (role + '-review_evaluator_count_active600_v3.py'), text, h)
        h.put(source_root / (role + '-reviewer-derivation.json'), dict(parent=parent, derived=reviewers[role], exact_changes=[],
            all_original_raw_scope_main_ROM_and_clean_main_rate_checks_unchanged=True, native_launch_ready=False, quality_qualified=False))
    monitor = state['current_main_monitor']
    proc = subprocess.run(['/usr/bin/python3.12', '-I', '-B', str(h.checked(monitor))],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    main = json.loads(proc.stdout)
    assert main['client_count'] == 192 and main['held_inputs'] == 197
    fresh_main = h.put(E / 'main192-readonly-preparation-readback.json', main)
    reference = json.loads(h.checked(templates['A32']['job']).read_bytes())['checkpoint']
    assert reference['sha256'] == 'b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
    h.checked(reference)
    design = dict(schema='robotron-evaluator-count-original-ABBA-active600-precommit-v1', source=h.pin(__file__),
                  created_unix_s=time.time(), status='PREPARED_NOT_NATIVE_LAUNCH_QUALIFIED',
                  fixed_scope_definition=h.pin(P / 'engineering-scope-UNSELECTED.json'),
                  original_proposal=h.pin(N / 'future-evaluator-concurrency64-UNSELECTED-proposal-original01/proposal.json'),
                  fixed_comparison_spec=manifest['comparison_spec'], comparator=manifest['comparator'],
                  ordered_cases=[dict(case=name, role='A32' if i in (0,3) else 'B64',
                                      actor_count=32 if i in (0,3) else 64, games_per_slot=2 if i in (0,3) else 1)
                                 for i,name in enumerate(ORDER)],
                  reference_policy=reference, source_templates=index_pin, source_and_math_readiness=manifest_pin,
                  complete_domain_family=manifest['complete_family'], complete_family_CPU8=manifest['complete_family_CPU8'],
                  prior_original_experiment_failure=state['last_failed_original_capacity_experiment'],
                  observer_component_CPU=manifest['observer_component_CPU'],observer_protocol_CPU=manifest['observer_protocol_CPU'],
                  current_main_context_CPU=manifest['current_main_context_CPU'],current_main_monitor=manifest['current_main_monitor'],
                  raw_reviewer_protocol_chain_CPU=manifest['raw_reviewer_protocol_chain_CPU'],reviewer_source_derivation=manifest['reviewer_source_derivation'],
                  common_running_projection_coalescence_stats_required=True,all_original01_02_03_04_05_IDs_must_be_excluded=True,
                  all_four_original_cases_fresh=True, prior_A1_rate_adopted=False,
                  main_rate_reader=manifest['main_rate_reader'], measurement_reader=manifest['measurement_reader'],
                  reviewers=reviewers, main_binding=state['current_main_binding'], current_main_readback=fresh_main,
                  previous_original_scientific_failure=failed_pin, native_CPU_cores=12, native_memory_bytes=24 << 30,
                  native_TasksMax=512, inference_max_batch_size=16, active_window_s=600, native_wall_limit_s=960,
                  original_attempts_each=1, no_retries=True, no_B_pooling=True, selector_CPU_cross_shape_gate=False,
                  native_launch_ready=False, actual64_startup_verified=False, quality_qualified=False,
                  full_game_wall_time_gain_verified=False, learning_speed_gain_verified=False,
                  limits='This precommit defines the prospective original experiment. Exact per-native-job CPU guard/initializer/interface proofs and64-prefix/raw-review capacity remain required before any original native launch.')
    design_pin = h.put(E / 'controlled-engineering-design-precommit.json', design)
    records = []
    ids = set()
    for i, name in enumerate(ORDER):
        role = 'A32' if i in (0,3) else 'B64'
        template = templates[role]
        directory = E / name;directory.mkdir(mode=0o700)
        job = copy.deepcopy(json.loads(h.checked(template['job']).read_bytes()))
        family = copy.deepcopy(json.loads(h.checked(job['source_family_manifest']).read_bytes()))
        protocol = copy.deepcopy(json.loads(h.checked(job['main_health_protocol']).read_bytes()))
        old_family, old_protocol = job['source_family_manifest'], job['main_health_protocol']
        family.update(engineering_case=name, experiment_precommit=design_pin, source_preparation_only=False,
                      native_launch_selected=False, exact_native_resources_or_active_load_verified=False,
                      actual64_startup_verified=False, legacy_32slot_component_proofs_only=True,
                      independent_measurement_reader=manifest['measurement_reader'], main_rate_reader=manifest['main_rate_reader'],
                      reviewer=reviewers[role], prospective_bounds=dict(native_wall_s=960, positive_load_s=600,
                          native_unit_runtime_s=22260, observer_unit_runtime_s=22260, controller_observation_s=22320))
        family_pin = h.put(directory / 'source-family-native-preparation.json', family)
        # Keep the established observer-protocol predicates and inputs. The
        # dedicated observer binds actual parent/job/output at runtime.
        assert protocol['health_job']['binding'] == job['main_binding'] == design['main_binding']
        protocol_pin = h.put(directory / 'diagnostic-main-health-protocol.json', protocol)
        job.update(created_unix_s=time.time(), output=str(directory / 'diagnostic-output-original01'),
                   initializer_fixture_only=False, engineering_case=name, label='capacity64-' + name + '-original06-20261026',
                   experiment_precommit=design_pin, main_rate_reader=manifest['main_rate_reader'],
                   source_family_manifest=family_pin, main_health_protocol=protocol_pin,
                   prelaunch_family_guard_closeout=str(directory / 'source-family-guards-CPU-original01/independent-original-family-guards-and-CPU-closeout.json'),
                   selected_change='Private evaluator count only: A32x2 versusB64x1, common optimized selector/batch16/12CPU/24GiB',
                   prior_CPU_fixture_template=template['job'], actual64_startup_verified=False,
                   native_launch_ready=False, scientific_case=False, quality_qualified=False)
        for field in ('sessions','connections'):
            job[field] = {str(slot):secrets.token_hex(16) for slot in job['actor_slots']}
            for value in job[field].values():
                assert value not in ids and value != '0' * 32
                ids.add(value)
        replaced = {old_family['path']:family_pin, old_protocol['path']:protocol_pin}
        inputs = [replaced.get(p['path'], p) for p in job['inputs']]
        inputs += [design_pin, family_pin, protocol_pin, manifest_pin, manifest['CPU15_original_closeout'],
                   manifest['measurement_reader'], manifest['main_rate_reader'], manifest['comparator'],
                   manifest['comparison_spec'], reviewers[role], h.pin(__file__)]
        job['inputs'] = list({p['path']:p for p in inputs}.values())
        runtime_pin = template['sources']['runtime']
        runtime = load('_capacity_native_prepare_' + role + '_' + str(i), h.checked(runtime_pin), runtime_pin['sha256'])
        assert runtime.validate_job(job) == Path(job['output'])
        runtime.validate_main_health_contract(job, protocol, family)
        assert not Path(job['prelaunch_family_guard_closeout']).exists()
        job_pin = h.put(directory / 'job.json', job)
        controller_pin = template['sources']['controller']
        controller = load('_capacity_native_controller_' + str(i), h.checked(controller_pin), controller_pin['sha256'])
        cfg = dict(unit='robotron-compiled-full-tail32-integration-capacity64-' + name.lower() + '-original06-20261026.service',
                   output=str(directory / 'execution-original01'),
                   argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',runtime_pin['path'],
                         '--execute','--job',job_pin['path'],'--job-sha256',job_pin['sha256'],'--source-sha256',runtime_pin['sha256']],
                   properties=['CPUQuota=1200%','MemoryMax=24G','MemorySwapMax=0','RuntimeMaxSec=22260','TasksMax=512',
                               'TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'], observation_s=22320,
                   pins=[controller.pin(p['path']) for p in {p['path']:p for p in [job_pin,runtime_pin,*job['inputs']]}.values()])
        cfg_pin = h.put(directory / 'controller-config-NOT-QUALIFIED.json', cfg)
        assert controller.checked_config(cfg_pin['path']) == cfg
        records.append(dict(case=name, role=role, actor_count=len(job['actor_slots']), native_job=job_pin,
                            native_controller=controller_pin, unqualified_controller_config=cfg_pin, source_family=family_pin,
                            main_health_protocol=protocol_pin, reviewer=reviewers[role], runtime=runtime_pin,
                            exact_job_CPU_guard_closeout_exists=False, native_launch_ready=False))
    assert len(ids) == 384
    prepared = h.put(E / 'prepared-original-ABBA-jobs-NOT-LAUNCH-QUALIFIED.json', dict(
        schema='robotron-capacity64-original-ABBA-job-preparation-v1', design=design_pin, cases=records,
        distinct_original_session_connection_IDs=384, actual_validate_job_main_contract_controller_interfaces_checked=True,
        all_native_outputs_and_executions_absent=True, exact_job_CPU_guards_complete=False,
        native_launch_ready=False, actual64_startup_verified=False, quality_qualified=False,
        remaining=['Bounded CPU guard and initializer proof for these exact four prepared native jobs; no inherited fixture guard promotion.',
                   'Guard derived reviewers and actual64-prefix/raw-review capacity under4GiB.',
                   'Prepare original native/observer/reviewer ABBA sequencer and independent final scope/math reviewer.',
                   'Actual launch-time main/GPU/ports/lease/resource preflight and original ABBA execution.']))
    print(json.dumps(dict(prepared=prepared, native_launch_ready=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    if parser.parse_args().prepare:
        prepare()
    else:
        print('PLAN_ONLY')
