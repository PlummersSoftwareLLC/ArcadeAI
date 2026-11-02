"""Independent prospective32-slot plan and completed-cohort evidence checks.

This is an unselected evidence component. The final root auditor must separately
authenticate the acquisition CPU/window proofs, original campaign owner/exit,
continuous main holds, closed evidence capture and original audit lifecycle.
Nothing here qualifies, publishes, launches or changes a policy. Import is inert.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SLOTS = list(range(4096, 4128))
ORDER = ['reference', 'candidate', 'reference', 'candidate']
REFERENCE_SHA = '4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
PACKAGE_SHA = '3ee43f9bd95fdda8f02abc048999a84513da71125dfd6b2e6558f45d2de6caf9'
PACKAGE = GAME/'tools/quality_capacity_proposal/profile04/runtime-source-package.json'
HELPERS = GAME/'tools/eval_capacity_proposal/audit_pilot_evidence_score_carry_v1.py'
HELPERS_SHA = 'bb93048c6cee1e844e72b0baa5bb8a7c1c9d18f838d16e28e4cc40913e97ad1a'
AUDITOR = GAME/'tools/confirmed_game_boundary_proposal/audit_confirmed_completed_leg_reviewed3.py'
AUDITOR_SHA = 'de901669780868cb842e9c9068ce11261a1d1f359c1940bb5bba6b2646c37ade'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked_module(path, expected, name):
    require(sha(path) == expected, 'Evidence dependency source changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    require(sha(path) == expected, 'Evidence dependency changed during import')
    return module


def dependencies():
    """Load only source-bound stdlib validators; never a learner or GPU runtime."""
    require(sha(PACKAGE) == PACKAGE_SHA, 'Selected private quality package changed')
    package = json.loads(PACKAGE.read_bytes())
    root = Path(package['root'])
    require(package['source_count'] == len(package['files']) == 123,
            'Exact123-source private package required')
    for relative, expected in package['files'].items():
        path = root/relative
        require(path.resolve(strict=True).is_relative_to(root) and sha(path) == expected,
                'Private package source differs')
    original = GAME/'tools/confirmed_game_boundary_proposal/quality_integration_reviewed4/Robotron/Scripts/dqn/socket_server.py'
    corrected = root/'Scripts/dqn/socket_server.py'
    require(sha(original) == '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408'
            and sha(corrected) == '84901c887437e99873d65c2348f18ca9e2f022a393f3c5282d68064c9f1fbf40',
            'Original and corrected handler bindings differ')
    def remaining(path):
        tree = ast.parse(path.read_text())
        tree.body = [node for node in tree.body if not (
            isinstance(node, ast.FunctionDef) and node.name == '_continuous_play_score_dip')]
        return ast.dump(tree)
    require(remaining(original) == remaining(corrected),
            'Handler changed outside the proved score-dip helper')
    prefix = '_quality32_evidence_' + str(len(sys.modules))
    namespace = types.ModuleType(prefix)
    namespace.__path__ = [str(root/'tools')]
    sys.modules[prefix] = namespace
    backend = __import__(prefix+'.compare_sidecar_measurements', fromlist=['validate_original_backend'])
    helpers = checked_module(HELPERS, HELPERS_SHA, prefix+'_helpers')
    auditor = checked_module(AUDITOR, AUDITOR_SHA, prefix+'_auditor')
    auditor.validate_optional_expert_proof()
    require('torch' not in sys.modules, 'Evidence review imported numerical runtime')
    return root, backend, helpers, auditor


def validate_plan(plan, binding, game):
    """Check every leg against the caller's separately authenticated root binding."""
    directory = Path(binding['output_directory'])
    require(directory.is_absolute() and directory.parent == GAME/'logs/managed-learning-20261015'
            and plan['output_directory'] == str(directory), 'Wrong exact future campaign directory')
    require(plan['checkpoints'] == binding['checkpoints']
            and plan['checkpoints']['reference']['sha256'] == REFERENCE_SHA
            and plan['checkpoints']['candidate']['sha256'] != REFERENCE_SHA,
            'Protected1059 reference and distinct future candidate required')
    for role, entry in plan['checkpoints'].items():
        require(role in ('reference', 'candidate')
                and entry['snapshot'] == str(directory/'checkpoints'/(role+'.pt')),
                'Canonical frozen role snapshot required')
    require(plan['evaluator_source_hashes'] == binding['evaluator_source_hashes']
            and plan['execution_source_hashes'] == binding['execution_source_hashes'],
            'Exact root source precommit required')
    require([leg['index'] for leg in plan['legs']] == [1, 2, 3, 4]
            and [leg['role'] for leg in plan['legs']] == ORDER, 'Four fresh R/C/R/C legs required')
    expected_gate = dict(order=ORDER, new_same_length_reference_cohorts=True,
        historical_or_interrupted_receipts_used=False, min_full_games_per_leg=50,
        all_actor_slots=SLOTS, include_every_admitted_game=True, include_full_completion_tail=True,
        max_attempts_per_leg=1, admission_extensions=False, automatic_promotion=False,
        automatic_rollback=False, learning_changes=False, candidate_gate=dict(
            each_candidate_individually=True, reference='all games pooled from both fresh reference legs',
            minimum_mean_ratio=1.05, minimum_median_ratio=1.0))
    require(plan['precommit'] == expected_gate, 'Full admission and individual candidate gates differ')
    common = None
    for leg in plan['legs']:
        job = leg['job']
        legdir = directory/f"{leg['index']:02d}-{leg['role']}"
        require(job['directory'] == str(legdir) and leg['receipt_path'] == str(legdir/'receipt.json')
                and job['checkpoint'] == plan['checkpoints'][leg['role']]['snapshot'],
                'Canonical leg directory and role checkpoint required')
        require(type(job['actors']) is int and job['actors'] == 32 and job['actor_slots'] == SLOTS
                and job['cohort_s'] == 5400 and job['timeout_s'] == 9000
                and job['completion_policy'] == 'confirmed_reset_reserves_v1'
                and job['game_boundary_diagnostics'] is True and job['epsilon'] == job['expert_ratio'] == 0
                and job['difficulty'] == 5 and job['start_level'] == 1
                and job['replay_enabled'] is False and job['fp16'] is False,
                'Frozen32-slot full-game protocol differs')
        require(job['device'] == 'cuda' and job['gpu_uuid'] == 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
                and job['host'] == '127.0.0.1' and job['port'] == 9999 and job['wait_us'] == 1000
                and job['inference_backend'] == 'inductor' and job['inference_max_batch_size'] == 16
                and job['cpu_threads'] == 2 and job['mame'] == '/usr/games/mame'
                and job['rompath'] == str(GAME/'roms'), 'Frozen physical backend differs')
        command = leg['command']
        expected_command = [str(GAME.parent/'.venv-gb300/bin/python'), '-Xgil=0', '-B', '-u',
                            str(Path(game)/'tools/run_frozen_sidecar.py')]
        for flag, value in (('--checkpoint', job['checkpoint']), ('--job-dir', job['directory']),
                ('--label', job['label']), ('--device', 'cuda'), ('--gpu-uuid', job['gpu_uuid']),
                ('--inference-backend', 'inductor'), ('--port', job['port']),
                ('--cohort-s', job['cohort_s']), ('--timeout-s', job['timeout_s']),
                ('--wait-us', job['wait_us']), ('--cpu-threads', job['cpu_threads']),
                ('--mame', job['mame']), ('--rompath', job['rompath']), ('--boot-assets', job['boot_assets'])):
            expected_command.extend([flag, str(value)])
        expected_command.extend(['--launch', '--actors', '32', '--game-boundary-diagnostics'])
        require(command == expected_command, 'Exact private32-slot evaluator command required')
        signature = {key: value for key, value in job.items()
                     if key not in ('checkpoint', 'directory', 'label')}
        require(common is None or signature == common, 'All four leg protocols must match')
        common = signature


def completed_cohort(receipt, directory, backend, helpers, auditor):
    """Recheck originals, ROM evidence and logs, plus strict client bijection.

    Caller authenticates the job and checkpoint against validate_plan and the
    actual acquisition proof; this component never substitutes for those checks.
    """
    result = helpers.original_games(receipt, directory, backend, auditor)
    ids = receipt['boundary']['acknowledged_client_ids']
    require(isinstance(ids, list) and len(ids) == 32 and len(set(ids)) == 32
            and all(type(value) is int and value >= 0 for value in ids),
            'Exactly32 distinct nonnegative startup client identities required')
    require(all(type(row['client_id']) is int and row['client_id'] >= 0 for row in receipt['rows']),
            'Exact nonnegative original client identity required')
    logs = helpers.actor_logs(receipt, directory, auditor)
    return dict(status='PASS_COHORT_ORIGINALS_ROM_LOGS_ONLY', original_games=result,
        actor_logs=logs, quality_qualified=False, promotion=False,
        root_acquisition_campaign_lifecycle_and_main_hold_checks_still_required=True)


if __name__ == '__main__':
    print('PLAN_ONLY: unselected evidence component; no reads, queries, outputs, launches or promotion')
