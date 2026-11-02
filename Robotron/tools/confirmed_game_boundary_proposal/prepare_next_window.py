"""Prepare a fresh 8M/8M candidate window only after both real validations close.

No service launch, control write, checkpoint request, learner stop or GPU import.
The unchanged observer must be launched within30s of the resulting baseline.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import time
import urllib.request

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE = GAME/'logs/managed-learning-20261015/run-26'
PACKAGE = GAME/'tools/confirmed_game_boundary_proposal/quality_integration_reviewed4'


def prepare():
    spec = importlib.util.spec_from_file_location('_next_window', GAME/'tools/post_continuity_window.py')
    window = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(window)
    require, pin, publish = window.require, window.pin, window.publish
    require(pin(GAME/'tools/post_continuity_window.py')['sha256'] ==
            'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3',
            'Original window observer changed')
    proofs = []
    for name in ('reference', 'integrated-no-fire-up'):
        stem = 'confirmed-game-boundary-real-MAME-'+name+'-original01'
        result = BASE/(stem+'-20261018/result.json')
        closure = BASE/(stem+'-preparation-20261018/native-terminal-archive/root-original-result-and-owned-release.json')
        value, closed = json.loads(result.read_bytes()), json.loads(closure.read_bytes())
        require(value['status'] == 'PASS' and value['source_unchanged']
                and value['owned_actors_absent'] and not value['cleanup_errors'], 'Real validation did not pass')
        require(closed['original_exit'] == 0 and closed['lifecycle_complete'] is True,
                'Original real validation not archived/released')
        if name.startswith('integrated'):
            require(value['original_terminal_readback']['status'] == 'PASS', 'Real original-file proof missing')
        proofs.extend((pin(result), pin(closure)))
    template = BASE/'post-production-continuity-first8M-original01-root-preparation-20261018/job.json'
    old_result = json.loads((BASE/'post-production-continuity-first8M-original01-20261018/result.json').read_bytes())
    job = copy.deepcopy(json.loads(template.read_bytes()))
    transitioned = old_result['completed_slot_transition']['after']['actual_pin']
    require(pin(transitioned['path']) == transitioned, 'Known previous capture slot changed')
    job['held_hashes'][transitioned['path']] = transitioned['sha256']
    manifest = json.loads((PACKAGE/'runtime-source-package.json').read_bytes())
    require(Path(manifest['root']) == PACKAGE/'Robotron', 'Wrong exact private source package')
    for relative, digest in manifest['files'].items():
        path = str(PACKAGE/'Robotron'/relative)
        require(pin(path)['sha256'] == digest, 'Private evaluator package changed')
        job['held_hashes'][path] = digest
    job.update(output=str(BASE/'post-confirmed-scoring-next8M-original01-20261018'),
               tag='confirmed_scoring_LR25_next8M_01_20261018')
    job['quality_precommit'].update(same_fixed_admission_s=5400, same_whole_cohort_timeout_s=7200,
        source_package=pin(PACKAGE/'runtime-source-package.json'), completion_policy='confirmed_reset_reserves_v1',
        mandatory_original_terminal_journal_readback=True)
    job['scope'] = ('New 8M learner-frame AND accepted DQN+epsilon transition window after real scoring validation. '
        'Main phase label, numerical sources, LR, exploration, replay and optimizer remain unchanged. '
        'Fresh corrected-source R/C/R/C only; never rescue interrupted campaigns; no learning-speed claim.')
    # All original actor identities, affinities and the current phase are retained.
    window.owner_and_files(job)
    preparation = BASE/'post-confirmed-scoring-next8M-original01-root-preparation-20261018'
    require(not preparation.exists() and not Path(job['output']).exists(), 'Unique window paths already exist')
    preparation.mkdir(mode=0o700)
    publish(preparation/'control-after.json', (GAME/'models_dqn/learning_control.json').read_bytes())
    raw = urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5).read()
    baseline = json.loads(raw)
    window.healthy(baseline, baseline, job['experiment'], time.time())
    job['baseline_monotonic_s'] = time.monotonic()
    job['baseline_API'] = publish(preparation/'baseline-API.raw.json', raw)
    job_pin = publish(preparation/'job.json', job)
    publish(preparation/'root-selection.json', dict(job=job_pin, validation_proofs=proofs,
        package=pin(PACKAGE/'runtime-source-package.json'), original_template=pin(template),
        descriptive_main_phase_label_unchanged=True, new_candidate_window=True, learning_changes=False,
        quality_qualified=False, promotion=False))
    print(json.dumps(dict(job=job_pin, baseline_frames=baseline['learner_frame_count'],
        baseline_monotonic_s=job['baseline_monotonic_s'], launch_within_s=30), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        prepare()
    else:
        print('PLAN_ONLY: no reads or actions')
