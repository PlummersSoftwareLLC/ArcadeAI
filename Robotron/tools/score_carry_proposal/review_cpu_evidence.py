"""Read back original CPU evidence; never launch MAME, alter main or qualify policy."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import urllib.request

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME / 'logs/managed-learning-20261015/run-26'


def require(value, message):
    if not value:
        raise ValueError(message)


def publish(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())


def load(name, path, expected):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Reader source changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Do not overwrite original readback')
    reader = load('_carry_reader', GAME / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
                  'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    reviewer = load('_carry_original_lifecycle', GAME / 'tools/eval_capacity_proposal/review_original_pilot_inflight_v1.py',
                    '92d58c5b16c548c09509e3537e02d0f1223c6c92552d305f5ff34d6dd1b879ac')
    evidence = {}

    def read(entry, as_json=True):
        value = reader.read_pin(entry, as_json=as_json)
        evidence[entry['path']] = entry
        return value

    def file(path):
        return read(reader.pin(path))

    def closure(directory, exit_code):
        pin = reader.pin(RUN / directory / 'execution/root-original-result-and-owned-release.json')
        value = read(pin)
        require(value['original_exit'] == exit_code, 'Actual original CPU outcome changed')
        reviewer.archived_closure(value, value['original'], read, exit_zero=exit_code == 0)
        return pin

    failures = [closure(name, 1) for name in (
        'large-score-carry-full-handler-CPU-original01-preparation-20261019',
        'large-score-carry-confirmed-handler-CPU-original01-preparation-20261019',
        'eval-capacity-profile04-CPU-original01-preparation-20261019')]
    primitive = file(RUN / 'large-score-carry-primitive-CPU-original01-20261019.json')
    require(primitive['status'] == 'PASS' and primitive['tests_run'] == 14
            and primitive['failures'] == primitive['errors'] == 0, 'Primitive tests failed')
    reports = []
    for name, kind in (
        ('large-score-carry-full-handler-CPU-original02-preparation-20261019', 'production'),
        ('large-score-carry-confirmed-handler-CPU-original02-preparation-20261019', 'confirmed')):
        work = RUN / name / 'work'
        completed = closure(name, 0)
        result = file(work / 'result.json')
        require(result['status'] == 'PASS' and result['child_exit'] == 0
                and len(result['cases']) == 44 and result['production_changed'] is False,
                'Original complete handler evidence failed')
        manifest = file(work / 'input.json')
        require(manifest.get('source_kind', 'production') == kind, 'Wrong journal source')
        for path, expected in manifest['installed_sources'].items():
            require(reader.digest(path) == expected, 'Main or historical private source changed')
        for name_in_package, expected in manifest['package_hashes'].items():
            require(reader.digest(work / 'private/Scripts/dqn' / name_in_package) == expected,
                    'Actual private CPU package changed')
        total_frames = total_replay = 0
        for row in result['cases']:
            label = f"{row['case']}-{int(row['replay'])}-{int(row['patched'])}-{int(row['torn'])}"
            case = file(work / (label + '.json'))
            require(len(case['actions']) == row['frames'], 'Wire frame/action conservation failed')
            queued = [dict(x['transition'], metadata=dict(x['transition']['metadata']))
                      for x in case['replay_enqueues']]
            for item in queued:
                item['metadata'].pop('client_id', None)
            require(queued == case['replay_steps'], 'Replay enqueue/consumer conservation failed')
            require(case['replay_steps'] if row['replay'] else not case['replay_steps'],
                    'Missing training replay or frozen replay leak')
            total_frames += row['frames']
            total_replay += len(case['replay_steps'])
        for replay in (0, 1):
            for case_name, prior_score in [('million', 999975), ('two_million', 1999975),
                                            ('ten_million', 9999975)]:
                values = {suffix: file(work / f'{case_name}-{replay}-{suffix}.json')
                          for suffix in ('0-0', '1-0', '0-1', '1-1')}
                require(values['0-0'] == values['1-0'] == values['1-1']
                        and values['0-1'] != values['0-0'], 'Full-path differential failed')
                eligible = [x for x in values['1-1']['journal'] if x['eligible']]
                require(len(eligible) == 1 and eligible[0]['uid'] == 2
                        and eligible[0]['score'] == prior_score + 1000,
                        'Corrected full score or game identity was lost')
                if kind == 'confirmed' and not replay:
                    namespace = {'require': require}
                    path = GAME / 'tools/confirmed_game_boundary_proposal/audit_confirmed_completed_leg_reviewed3.py'
                    require(reader.digest(path) == 'de901669780868cb842e9c9068ce11261a1d1f359c1940bb5bba6b2646c37ade',
                            'Independent ROM predicate changed')
                    node = next(n for n in ast.parse(path.read_bytes()).body
                                if isinstance(n, ast.FunctionDef) and n.name == 'validate_rom_terminal')
                    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
                    rows = [json.loads(line) for line in (work / 'journal' /
                            f'{case_name}-0-1-1/games.jsonl').read_text().splitlines()]
                    for row in rows:
                        if row['eligible']:
                            namespace['validate_rom_terminal'](row, {})
            for control in ('score_wrap', 'wave_wrap', 'truncated_nonzero', 'zero_real_restart', 'zero_no_restart'):
                require(file(work / f'{control}-{replay}-0-0.json') ==
                        file(work / f'{control}-{replay}-1-0.json'), 'Existing reset/wrap control changed')
        reports.append(dict(source_kind=kind, closure=completed, scenarios=44,
                            wire_frames=total_frames, replay_rows=total_replay))
    profile = file(GAME / 'tools/eval_capacity_proposal/profile05/runtime-source-package.json')
    require(profile['source_count'] == 123 and profile['changed_parent_files'] ==
            ['Scripts/dqn/socket_server.py', 'tools/test_eval_capacity.py'], 'Profile scope changed')
    parent = file(Path(profile['parent_manifest']['path']))
    for relative, expected in profile['files'].items():
        require(reader.digest(Path(profile['root']) / relative) == expected, 'New profile changed')
        if relative not in profile['changed_parent_files']:
            require(expected == parent['files'][relative], 'An unrelated profile source changed')
    regression = RUN / 'eval-capacity-profile05-CPU-original01-preparation-20261019'
    tests = file(regression / 'CPU-report.json')
    require(tests['status'] == 'PASS' and tests['tests_run'] == 88
            and tests['failures'] == tests['errors'] == tests['skipped'] == 0
            and tests['cuda_initialized'] is False, 'Existing evaluator regressions failed')
    regression_closure = closure(regression.name, 0)
    baseline = file(regression / 'original-fixture-diagnostic.json')
    require(baseline['status'] == 'REPRODUCED_PREEXISTING_FIXTURE_FAILURES'
            and len(baseline['failures']) == 1 and len(baseline['errors']) == 2,
            'Previously stale measurement fixtures were not reproduced on original source')
    args.output.mkdir(mode=0o700)
    binding_path = RUN / ('confirmed-scoring-quality-original01-preparation-20261018/'
        'capacity32-confirmed1059-inflight-v1-preparation-20261019/runtime-bindings/main-binding.json')
    binding = file(binding_path)
    guard = load('_carry_main_hold', RUN / 'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
                 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3')
    guard.owner_and_files(binding)
    api = json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=10))
    guard.healthy(api, file(Path(binding['baseline_API']['path'])), binding['experiment'], time.time())
    age = time.time() - (GAME / 'models_dqn/robotron_dqn_latest.pt').stat().st_mtime
    require(0 <= age <= 360, 'Main autosave stale')
    publish(args.output / 'main-API.json', api)
    report = dict(schema='robotron-large-score-carry-original-CPU-readback-v1', status='PASS',
        observed_unix_s=time.time(), primitive_tests=14, handler_runs=reports,
        regression_tests=88, regression_closure=regression_closure, preserved_failed_CPU_runs=failures,
        profile_manifest=reader.pin(GAME / 'tools/eval_capacity_proposal/profile05/runtime-source-package.json'),
        main_held_files=len(binding['held_hashes']), main_actors=len(binding['actors']),
        learner_frames=api['learner_frame_count'], autosave_age_s=age,
        evidence=evidence, original_scientific_studies_still_invalid=True,
        production_changed=False, GPU_MAME_validation_complete=False,
        quality_qualification=False, learning_speed_gain_verified=False,
        next_action='Precommit and validate a distinct corrected-source runtime study; preserve main and all prior outcomes.')
    publish(args.output / 'root-readback.json', report)
    pin = reader.pin(args.output / 'root-readback.json')
    print(json.dumps(dict(status='PASS', primitive_tests=14, full_handler_scenarios=88,
                         evaluator_regressions=88, report=pin)))


if __name__ == '__main__':
    main()
