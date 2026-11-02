"""Independently rejoin all seven original bounded CPU outcomes; never launch."""
import argparse
import hashlib
import importlib.util
import json
import re
import shlex
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
D = Path(__file__).resolve().parent


def load(path, sha, name):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-closed', action='store_true')
    args = parser.parse_args()
    if not args.validate_closed:
        print('PLAN_ONLY: no reads, queries, outputs, releases or runtime changes')
        return
    p = load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
             'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', 'reader')
    w = load(R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
             'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3', 'window')
    c = load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py',
             '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', 'control')
    r = load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
             '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445', 'runtime')
    read = lambda entry, as_json=True: p.read_pin(entry, as_json=as_json)
    precommit_pin = p.pin(D/'source-copy-and-test-group-precommit.json')
    precommit = read(precommit_pin)
    assert set(precommit['groups']) == set('ABCDEFG')
    for row in precommit['sources']:
        assert read(row['original'], False) == read(row['copy'], False)
    assert all((D/('group-'+group)/'execution/root-original-result-and-owned-release.json').exists()
               and (D/('group-'+group+'-actual-test-result.json')).exists() for group in 'ABCDEFG'), 'Original groups still pending; no outputs written'
    selected = [name for names in precommit['groups'].values() for name in names]
    assert len(selected) == len(set(selected))
    rows = []
    total = 0
    for group, expected_count in zip('ABCDEFG', [74, 2, 3, 2, 2, 2, 3]):
        execution = D/('group-'+group)/'execution'
        owner_pin = p.pin(execution/'root-original-identity.json')
        closure_pin = p.pin(execution/'root-original-result-and-owned-release.json')
        owner, closure = read(owner_pin), read(closure_pin)
        assert owner['unit'] == 'robotron-supervised-quality32-chain-'+group+'-CPU-original01-20261019.service'
        fields = r.archived_closure(closure, owner, read, exit_zero=True)
        assert fields['Restart'] == 'no' and fields['SendSIGKILL'] == 'no'
        assert r.duration_seconds(fields['RuntimeMaxUSec']) == 180
        assert r.duration_seconds(fields['CPUQuotaPerSecUSec']) == 2 and fields['MemoryMax'] == str(4 << 30)
        assert w.process_start(owner['pid']) is None
        assert all(c.show(owner[key])['LoadState'] == 'not-found' for key in ('unit', 'timer'))
        config_pin = p.pin(execution.parent/'original-controller-config.json')
        config = read(config_pin)
        assert config['argv'] == ['/usr/bin/python3.12', '-I', '-B', str(D/'run-original-test-group.py'), group]
        assert config['unit'] == owner['unit'] and str(D/'run-original-test-group.py') in fields['ExecStart']
        matched = re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}', fields['ExecStart'])
        assert matched is not None
        observed = shlex.split(matched[1])
        assert observed[:7] == ['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1']
        assert observed[7].startswith('TMPDIR=/') and observed[8:] == config['argv']
        result_pin = p.pin(D/('group-'+group+'-actual-test-result.json'))
        result = read(result_pin)
        assert result['group'] == group and result['passed'] is True
        assert result['actual_tests_run'] == result['loaded_test_count'] == expected_count
        assert result['selected_tests'] == precommit['groups'][group]
        assert result['errors'] == result['failures'] == 0 and not result['actual_quality_run']
        stderr = execution/'stderr.txt'
        text = stderr.read_text()
        assert ('Ran '+str(expected_count)+' tests in ') in text and text.rstrip().endswith('OK')
        archived_stdout = execution/'stdout.txt'
        rows.append(dict(group=group, owner=owner_pin, closure=closure_pin, config=config_pin,
            actual_test_result=result_pin, actual_tests=expected_count,
            original_console_path=str(archived_stdout),original_test_output_path=str(stderr)))
        total += expected_count
    assert total == 88
    # Every original outcome/command is validated before any output publication.
    for row in rows:
        row['original_console'] = w.publish(D/('group-'+row['group']+'-original-stdout-readonly.txt'), Path(row.pop('original_console_path')).read_bytes())
        row['original_test_output'] = w.publish(D/('group-'+row['group']+'-original-stderr-readonly.txt'), Path(row.pop('original_test_output_path')).read_bytes())
    state = json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    main = read(state['current_main_binding'])
    w.owner_and_files(main)
    source_scope = p.pin(D/'source-scope-independent-readback.json')
    read(source_scope)
    reference = p.pin(G/'models_dqn/managed-incumbents/freshCE-LR25-1059M-confirmed-reset-20261018.pt')
    invalid_candidate = p.pin(G/'models_dqn/managed-checkpoints/scorecarry849_LR25_next8M_01_20261019.pt')
    assert reference['sha256'] == '4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
    assert invalid_candidate['sha256'] == '667e0f275e4a3e67fddc36d23954929a9527d9e309ff60397f5add2e2471c04e'
    report = dict(status='ORIGINAL_SUPERVISED_QUALITY32_CHAIN88_PASS_ALL7_EXIT0_CLOSED',
        unix_s=time.time(), actual_test_count=total, original_groups=rows, source_scope=source_scope,
        precommit=precommit_pin, verifier=p.pin(Path(__file__).resolve()), current_main_binding=state['current_main_binding'],
        held_main_inputs_verified=195, source_package=precommit['source_package'], reference=reference,
        preserved_invalid_candidate=invalid_candidate, all_42_descriptors_verified=True,
        all_14_original_units_absent=True, real_supervised_restart_induced=False,
        synthetic_quality_proofs_only=True, original_invalid_quality_reinterpreted=False,
        ready_for_future_protocol_selection=True, actual_quality_run=False,
        actual_runtime_changed=False, quality_gain_verified=False, learning_speed_gain_verified=False)
    pin = w.publish(D/'root-all-original-groups-independent-readback.json', report)
    print(json.dumps(dict(status=report['status'], readback=pin), allow_nan=False))


if __name__ == '__main__':
    main()
