"""Prepare an exact four-job CPU qualification packet; never launch it."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE = ROOT/'logs/managed-learning-20261015/run-26'
HERE = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation')
LOCAL = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original06')


# The fifth control is an exact immutable resume record already held by the
# selected original192 case. This is not a directory-wide JSON/model exception.
SELECTED_RESUME_RECORD = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/models_dqn/resume-records/resume-f3dcfa4e6893fe8111afc53bc14204943d7535b6c152d05d6018db9f1d8be0e0.json', 'sha256': 'ad351d26a04afd2f99eb1deb628f86f6b470fad3093b1fd0b7516c722da481f0', 'bytes': 559, 'identity': {'bytes': 559, 'ctime_ns': 1793280707389499730, 'device': 2304, 'inode': 84699900, 'mode': '0o444', 'mtime_ns': 1793280707389499730, 'nlink': 1, 'uid': 1001}}
UNCHANGED_DRIVER = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original06/qualify_round_study_cpu_v6.py', 'sha256': 'c231234990ba10dc0bb04d4e01967ea83c6da20f52afac2642e5d0b896d52072', 'bytes': 18886, 'identity': {'device': 2304, 'inode': 85355318, 'bytes': 18886, 'mtime_ns': 1793311425839795069, 'ctime_ns': 1793311527248071013, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
MODELS = ROOT/'models_dqn'
SMALL_MODEL_METADATA_PATHS = frozenset({MODELS/'game_settings.json', MODELS/'learning_control.json',
    MODELS/'managed_save.request.json.completed',
    MODELS/'managed-measurements/scorecarry-previewflags-preserveRAM-original01-20261027-final.json',
    Path(SELECTED_RESUME_RECORD['path'])})


def preflight_held_inputs(inputs):
    """Pure classification only: no file reads, stat, model imports or outputs.

    Call before the expensive raw proof. All selected pins remain in the input
    domain. Unknown model controls fail; checkpoints/MAME stay stat-only.
    """
    assert type(inputs) is list, 'Selected held fullpin list required'
    small, large, other, paths = [], [], [], {}
    for value in inputs:
        assert type(value) is dict and set(value) == {'path','sha256','bytes','identity'}, 'Exact fullpin required'
        identity = value['identity']
        assert type(identity) is dict and set(identity) == {'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}, 'Exact full8 identity required'
        assert all(type(identity[k]) is int and identity[k] >= 0 for k in ('device','inode','bytes','mtime_ns','ctime_ns','uid','nlink')) and type(identity['mode']) is str, 'Typed full8 file identity required'
        assert type(value['path']) is str and type(value['sha256']) is str and len(value['sha256']) == 64 and all(c in '0123456789abcdef' for c in value['sha256']), 'Canonical held path and SHA required'
        path = Path(value['path'])
        assert path.is_absolute() and '..' not in path.parts and str(path) == value['path'], 'Lexically canonical held path required'
        assert type(value['bytes']) is int and type(identity['bytes']) is int and 0 <= value['bytes'] == identity['bytes'], 'Held byte count differs'
        if str(path) in paths:
            assert paths[str(path)] == value, 'Conflicting selected pins for one path'
            continue  # Equal aliases are retained in the caller's unchanged list.
        paths[str(path)] = value
        if path.suffix == '.pt' or path == Path('/usr/games/mame'):
            large.append(value)
        elif path.is_relative_to(MODELS):
            assert path in SMALL_MODEL_METADATA_PATHS, 'Unexpected model-directory control input: ' + str(path)
            assert 0 < value['bytes'] <= 1_048_576 and identity['uid'] == 1001 and identity['nlink'] == 1 and identity['mode'] in ('0o444','0o644','0o664'), 'Bounded owned single-link control metadata required'
            if path == Path(SELECTED_RESUME_RECORD['path']):
                assert value == SELECTED_RESUME_RECORD, 'Exact selected immutable559-byte resume record required'
            small.append(value)
        else:
            other.append(value)
    return dict(schema='robotron-exact-resume-held-input-classification-v1',
        input_entries=len(inputs),unique_paths=len(paths),small_model_metadata=small,
        large_stat_only=large,other_held_inputs=other,all_input_paths_preserved=True,
        filesystem_or_body_reads_performed=False,model_directory_scope_broadened=False)



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
    output = Path(output).resolve()
    output.mkdir(mode=0o700)
    controller = h.pin(ROOT/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    control = load('_round_CPU_prepare_controller', Path(controller['path']))
    old_directory = BASE/'deadline-score32-fixed-fleet-admission-original03-preparation-20261026/actual-four-job-prebody-and-native-chain-CPU-original01'
    old = json.loads((old_directory/'job.json').read_bytes())
    driver = h.pin(LOCAL/'qualify_round_study_cpu_v6.py')
    assert driver == UNCHANGED_DRIVER, 'Exact selected current-quiescence guard driver required'
    sources = [study_pin, controller, driver, h.pin(Path(__file__).resolve()), h.pin(Path(old['helpers']['path'])),
               old['new_native_chain_tests'], old['interpreter_symlink_binding'], old['previous_qualification_CPU_scope']]
    large = {}
    metadata = {}
    models = ROOT/'models_dqn'
    allowed = SMALL_MODEL_METADATA_PATHS
    for row in study['cases']:
        job = json.loads(h.checked(row['native_job']).read_bytes())
        sources += [row['native_job'], row['runtime'], row['native_controller'], row['unqualified_controller_config'],
                    *job['inputs']]
        case = json.loads(h.checked(job['main_binding']).read_bytes())
        for name in case['inputs']:
            path = Path(name)
            if path.is_relative_to(models):
                selected = dict(path=name,sha256=case['inputs'][name]['sha256'],
                    bytes=case['inputs'][name]['identity']['bytes'],identity=case['inputs'][name]['identity'])
                preflight_held_inputs([selected])
                assert path in allowed, 'Unexpected model-directory control input'
                assert path.resolve(strict=True) == path and not path.is_symlink() and path.is_file(), 'Canonical regular non-symlink control metadata required'
                actual = h.pin(path)
                assert actual == selected, 'Selected full8 control metadata changed; never refresh it implicitly'
                metadata[str(path)] = actual
    sources += list(metadata.values())
    small = {}
    for value in sources:
        path = Path(value['path'])
        if path.suffix == '.pt' or (path.is_relative_to(models) and path not in allowed) or path == Path('/usr/games/mame'):
            large[str(path)] = value
        else:
            small[str(path)] = value
    witness = json.loads(h.checked(old['interpreter_symlink_binding']).read_bytes())
    large[witness['source_pin']['path']] = witness['source_pin']
    unit = 'robotron-round-four-exact-contexts-CPU-' + ('engineering' if study['engineering_only'] else 'study') + '-current-eval-quiescence-proof2s-' + study_pin['sha256'][:16] + '-original01-20261029.service'
    job = dict(schema='robotron-deadline32-four-actual-jobs-CPU-guard-v2', unit=unit,
        output=str(output/'output-original01'), prepared_manifest=study_pin, helpers=old['helpers'],
        new_native_chain_tests=old['new_native_chain_tests'], interpreter_symlink_binding=old['interpreter_symlink_binding'],
        previous_qualification_CPU_scope=old['previous_qualification_CPU_scope'], inputs=list(small.values()),
        large_input_stat_attestations=list(large.values()), allowed_model_directory_metadata=list(metadata.values()),
        original_attempt=1, no_retry=True, expected_actual_serialized_job_tests=6,
        expected_new_native_chain_tests=4, expected_negative_cases_per_leg=8, old_clock_controller19_may_not_be_rerun=True,
        source=driver, engineering_only=study['engineering_only'],
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
