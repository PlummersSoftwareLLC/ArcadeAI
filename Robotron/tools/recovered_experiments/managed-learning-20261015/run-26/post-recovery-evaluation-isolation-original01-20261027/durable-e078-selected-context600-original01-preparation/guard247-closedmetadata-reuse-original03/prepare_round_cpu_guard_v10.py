"""Prepare an exact four-job CPU qualification packet; never launch it."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE = ROOT/'logs/managed-learning-20261015/run-26'
HERE = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation')
LOCAL = Path(__file__).resolve().parent
REUSE = LOCAL.parent/'closed-metadata-readiness-reuse-original03-preparation'
AUTHORITY_SHA = '5e83e9db759c1844c0236f2b60c14dd56995e63e0f3436387ddfc12190fe4ee3'
DRIVER_SHA = '85e8bfed0594561036f7dae24b3ccf9aab180591d80ae9a92a5be968c9add8dc'
SHIM_SHA = 'cf693756eb5059dc268f91df0b6d91ec10e4dcc0f13f21daa66512ec806a2b37'
FAILED_SHA = '445680bc53a832152f68788befd59b5c4010b3f246617e97475c15b47cc926c9'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(manifest, output):
    h = load('_round_CPU_prepare_helpers', ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    study_pin = h.pin(Path(manifest).resolve())
    study = json.loads(h.checked(study_pin).read_bytes())
    assert [row['leg'] for row in study['cases']] == ['R1', 'C1', 'R2', 'C2']
    authority_pin = h.pin(REUSE/'actual-closed-metadata-readiness-authority-original01.json')
    assert authority_pin['sha256'] == AUTHORITY_SHA
    authority = json.loads(h.checked(authority_pin).read_bytes())
    assert authority['schema'] == 'robotron-closed-metadata-and-raw-readiness-predicate-reuse-authority-v1'
    assert authority['native_prepared'] == study_pin and authority['native_jobs'] == [row['native_job'] for row in study['cases']]
    assert authority['ordered_legs'] == ['R1', 'C1', 'R2', 'C2']
    failure_pin = h.pin(Path(study_pin['path']).parent/'four-exact-contexts-CPU-original02/ROOT-timeout-owned-closure-original01/ROOT-original-timeout-guard-owned-release.json')
    assert failure_pin['sha256'] == FAILED_SHA
    failure = json.loads(h.checked(failure_pin).read_bytes())
    assert failure['schema'] == 'robotron-original-CPU-guard-timeout-positive-owned-closure-v1'
    assert failure['actual_original_ExecMainCode'] == 2 and failure['actual_original_signal'] == 15
    assert failure['actual_original_Result'] == 'timeout' and failure['normal_exit_not_claimed'] is True
    assert failure['all_original_service_timer_birth_and_cgroup_absent'] is True
    assert failure['CPU_report_absent'] is True and failure['qualification'] is False
    output = Path(output).resolve()
    output.mkdir(mode=0o700)
    controller = h.pin(ROOT/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    control = load('_round_CPU_prepare_controller', Path(controller['path']))
    old_directory = BASE/'deadline-score32-fixed-fleet-admission-original03-preparation-20261026/actual-four-job-prebody-and-native-chain-CPU-original01'
    old = json.loads((old_directory/'job.json').read_bytes())
    driver = h.pin(REUSE/'qualify_round_study_cpu_closed_metadata_v7.py')
    shim = h.pin(REUSE/'closed_metadata_readiness_reuse_v1.py')
    assert driver['sha256'] == DRIVER_SHA and shim['sha256'] == SHIM_SHA
    def authority_pins(value):
        if isinstance(value, dict):
            if {'path', 'sha256', 'bytes', 'identity'} <= set(value):
                return [value]
            return [pin for child in value.values() for pin in authority_pins(child)]
        if isinstance(value, list):
            return [pin for child in value for pin in authority_pins(child)]
        return []
    closed_metadata_job = json.loads(h.checked(authority['metadata_job']).read_bytes())
    readiness_inputs = [authority_pin, shim, failure_pin, *authority_pins(authority), *closed_metadata_job['inputs']]
    for value in readiness_inputs:
        h.checked(value)
    sources = [study_pin, controller, driver, h.pin(Path(__file__).resolve()), h.pin(Path(old['helpers']['path'])),
               old['new_native_chain_tests'], old['interpreter_symlink_binding'], old['previous_qualification_CPU_scope']]
    large = {}
    metadata = {}
    models = ROOT/'models_dqn'
    allowed = {models/'game_settings.json', models/'learning_control.json', models/'managed_save.request.json.completed',
               models/'managed-measurements/scorecarry-previewflags-preserveRAM-original01-20261027-final.json'}
    for row in study['cases']:
        job = json.loads(h.checked(row['native_job']).read_bytes())
        sources += [row['native_job'], row['runtime'], row['native_controller'], row['unqualified_controller_config'],
                    *job['inputs']]
        case = json.loads(h.checked(job['main_binding']).read_bytes())
        for name in case['inputs']:
            path = Path(name)
            if path.is_relative_to(models):
                assert path in allowed, 'Unexpected model-directory control input'
                metadata[str(path)] = h.pin(path)
    sources += list(metadata.values()) + readiness_inputs
    small = {}
    for value in sources:
        path = Path(value['path'])
        if path.suffix == '.pt' or (path.is_relative_to(models) and path not in allowed) or path == Path('/usr/games/mame'):
            large[str(path)] = value
        else:
            small[str(path)] = value
    witness = json.loads(h.checked(old['interpreter_symlink_binding']).read_bytes())
    large[witness['source_pin']['path']] = witness['source_pin']
    unit = 'robotron-round-four-exact-contexts-CPU-' + ('engineering' if study['engineering_only'] else 'study') + '-launcher-original03-20261029.service'
    job = dict(schema='robotron-deadline32-four-actual-jobs-CPU-guard-v2', unit=unit,
        output=str(output/'output-original01'), prepared_manifest=study_pin, helpers=old['helpers'],
        new_native_chain_tests=old['new_native_chain_tests'], interpreter_symlink_binding=old['interpreter_symlink_binding'],
        previous_qualification_CPU_scope=old['previous_qualification_CPU_scope'], inputs=list(small.values()),
        large_input_stat_attestations=list(large.values()), allowed_model_directory_metadata=list(metadata.values()),
        original_attempt=1, no_retry=True, expected_actual_serialized_job_tests=6,
        expected_new_native_chain_tests=4, expected_negative_cases_per_leg=8, old_clock_controller19_may_not_be_rerun=True,
        source=driver, readiness_reuse_shim=shim, closed_metadata_readiness_authority=authority_pin,
        failed_original02_owned_timeout_closure=failure_pin, engineering_only=study['engineering_only'],
        resources=dict(cpu_cores=2, memory_bytes=4 << 30, runtime_s=180, tasks_max=128))
    jp = h.put(output/'job.json', job)
    interpreter = witness['source_pin']['path']
    cfg = dict(unit=unit, output=str(output/'execution-original01'),
        argv=[interpreter,'-Xgil=0','-I','-B',driver['path'],'--execute','--job',jp['path'],
              '--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
                    'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[control.pin(value['path']) for value in [jp,*small.values()]], observation_s=240)
    cp = h.put(output/'controller-config.json', cfg)
    assert control.checked_config(cp['path']) == cfg
    return h.put(output/'prepared-CPU-NOT-LAUNCHED.json', dict(
        schema='robotron-round-four-exact-contexts-CPU-preparation-v1', CPU_job=jp,
        config=cp, controller=controller, driver=driver, helpers=old['helpers'],
        archive=h.pin(ROOT/'tools/eval_capacity_proposal/review_original_pilot_score_carry_v1.py'),
        reader=h.pin(ROOT/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'),
        native_prepared_manifest=study_pin, source_preparer=h.pin(Path(__file__).resolve()),
        readiness_reuse_shim=shim, closed_metadata_readiness_authority=authority_pin,
        failed_original02_owned_timeout_closure=failure_pin,
        small_hashed_inputs=len(small), large_stat_only_attestations=len(large),
        expected_actual_subject_tests=6, expected_unchanged_private_boundary_tests=4,
        old19_rerun=False, engineering_only=study['engineering_only'], CPU_scope_launched=False,
        scientific_launch_qualified=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare(args.manifest, args.output)), flush=True)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
