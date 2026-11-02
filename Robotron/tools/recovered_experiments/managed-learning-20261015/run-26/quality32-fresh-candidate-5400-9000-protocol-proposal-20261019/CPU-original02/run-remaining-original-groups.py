"""Run each remaining precommitted CPU group once after verifying its predecessor."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
T = Path(__file__).resolve().parent
H = G/'tools/quality_capacity_proposal'


def load(path, sha, name):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, tests, queries, outputs or launches')
        return
    reader = load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', '_tail9000_batch_reader')
    precommit = reader.pin(T/'precommit.json')
    assert precommit['sha256'] == '4c27997bdb25ce1dd36f80736df3446df3bdd2244c33e5ed929e6fb97786d4cb'
    selected = reader.read_pin(precommit)
    job = reader.read_pin(selected['job'])
    controller = selected['controller']
    runtime = load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445', '_tail9000_batch_archives')
    window = load(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
        'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3', '_tail9000_batch_main')
    main_path = G/'logs/managed-learning-20261015/run-26/quality32-CE1059-vs-post-supervised-main-next8M-original01-preparation-20261019/runtime-bindings/main-binding.json'
    main_pin = reader.pin(main_path); binding = reader.read_pin(main_pin)

    def verify(group):
        directory = T/('group-'+group)/'execution'
        owner_pin = reader.pin(directory/'root-original-identity.json')
        closure_pin = reader.pin(directory/'root-original-result-and-owned-release.json')
        owner = reader.read_pin(owner_pin); closure = reader.read_pin(closure_pin)
        runtime.archived_closure(closure, owner,
            lambda e, as_json=True: reader.read_pin(e, as_json=as_json), exit_zero=True)
        assert closure['original_exit'] == 0 and closure['lifecycle_complete'] and closure['unit_released']
        assert len(closure['full_original_archives']) == 6 and len(closure['owned_release']) == 2
        report_pin = reader.pin(T/('group-'+group+'-actual-test-result.json'))
        report = reader.read_pin(report_pin)
        assert report['passed'] is True and report['errors'] == report['failures'] == report['skipped'] == 0
        assert report['actual_tests_run'] == report['loaded_test_count'] > 0
        for pin in job['sources']:
            assert reader.pin(pin['path']) == pin
        result = dict(group=group, owner=owner_pin, closure=closure_pin, actual_tests=report_pin,
            actual_count=report['actual_tests_run'], all_six_original_archives_verified=True,
            exact_service_and_timer_releases_verified=True, original_exit=0,
            scientific_quality_run=False, candidate_captured=False)
        pin = window.publish(T/('root-independent-group-'+group+'-readback.json'), result)
        print(json.dumps(dict(group_verified=group, actual_tests=report['actual_tests_run'], readback=pin)), flush=True)
        return result

    results = [verify('A')]
    for group in 'BCDEFGH':
        config_pin = selected['configs'][group]
        reader.read_pin(config_pin)
        assert not Path(reader.read_pin(config_pin)['output']).exists()
        window.owner_and_files(binding)
        api = json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5))
        age = time.time()-(G/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime
        assert api['client_count'] == 192 and api['training_enabled'] is True
        assert 0 <= age <= 360 and 0 <= time.time()-api['ts'] <= 5
        assert api['quality_campaign']['available'] is False
        observation = window.publish(T/('main-before-group-'+group+'.json'),
            dict(unix_s=time.time(), main_binding=main_pin, all195_main_holds_verified=True,
                all192_original_actor_births_verified=True, client_count=192, training=True,
                learner_frames=api['learner_frame_count'], updates=api['training_steps'],
                fps=api.get('fps'), autosave_age_s=age))
        print(json.dumps(dict(starting_group=group, main_observation=observation)), flush=True)
        command = ['/usr/bin/python3.12', '-I', '-B', controller['path'], '--execute',
            '--config', config_pin['path'], '--expected-source-sha256', controller['sha256']]
        result = subprocess.run(command)
        assert result.returncode == 0, ('Original controller failed; no later group launched', group, result.returncode)
        results.append(verify(group))
    window.owner_and_files(binding)
    report = dict(status='ALL_ORIGINAL_CPU_GROUPS_PASS', precommit=precommit,
        groups=results, actual_tests=sum(row['actual_count'] for row in results),
        all_main195_and192_verified_after=True, quality_launched=False, candidate_captured=False,
        clock_budget_clarification=selected['clock_budget_clarification'])
    pin = window.publish(T/'root-all-original-groups-independent-readback.json', report)
    print(json.dumps(dict(status=report['status'], actual_tests=report['actual_tests'], report=pin)), flush=True)


if __name__ == '__main__':
    main()
