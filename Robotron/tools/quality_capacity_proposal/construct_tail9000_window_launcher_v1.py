"""Construct a new prospective-window launcher; inert without explicit write flag."""
import argparse
import hashlib
import json
import os
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
P = R/'post-tail9000-main-next8M-original01-preparation-20261019'
PARENT = R/'post-supervised-main-next8M-original01-preparation-20261019/run-original-window.py'

HELPERS = r'''

def verify_CPU_proof(proof, source, group, reader, control, runtime):
    read = lambda entry, as_json=True: reader.read_pin(entry, as_json=as_json)
    require(proof['source'] == source and proof['all_six_original_archives_verified'] is True
            and proof['original_units_absent'] is True, 'Selected CPU proof source or closure differs')
    read(source, False)
    report = read(proof['actual_tests']); job = read(proof['job']); config = read(proof['config'])
    require(report['group'] == group and report['actual_tests_run'] == report['loaded_test_count'] == proof['actual_count']
            and type(proof['actual_count']) is int and proof['actual_count'] > 0
            and report['passed'] is True and report['failures'] == report['errors'] == report['skipped'] == 0
            and report['selected_tests'] == job['groups'][group]
            and report['actual_quality_run'] is False and report['actual_policy_publication'] is False
            and report['CUDA_hidden'] is True and report['numerical_runtime_imported'] is False
            and source in job['sources'] and proof['tests'] in job['sources'],
            'Original selected CPU tests, scope or source membership differs')
    for pin in job['sources']:
        read(pin, False)
    owner = read(proof['original_owner']); closure = read(proof['original_closure'])
    fields = runtime.archived_closure(closure, owner, read, exit_zero=True)
    require(closure['original_exit'] == 0 and closure['lifecycle_complete'] is True
            and closure['unit_released'] is True and len(closure['full_original_archives']) == 6
            and len(closure['owned_release']) == 2 and config['unit'] == owner['unit'],
            'Actual original CPU owner, exit, archives or releases differ')
    argv = config['argv']
    expected = ['/usr/bin/python3.12', '-I', '-B', str(G/'tools/quality_capacity_proposal/run_tail9000_CPU_group_v1.py'),
        '--execute', '--job', proof['job']['path'], '--job-sha256', proof['job']['sha256'], '--group', group]
    wrapper = ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR='+config['output']+'/tmp']+expected
    match = re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}', fields['ExecStart'])
    require(argv == expected and match is not None and shlex.split(match[1]) == wrapper,
            'Archived original CPU command differs from its selected job')
    require(runtime.duration_seconds(fields['RuntimeMaxUSec']) == 180
            and fields['MemoryMax'] == str(4<<30) and runtime.duration_seconds(fields['CPUQuotaPerSecUSec']) == 2
            and fields['Restart'] == 'no' and fields['SendSIGKILL'] == 'no', 'Actual CPU resource scope differs')
    require(all(control.show(owner[key])['LoadState'] == 'not-found' for key in ('unit', 'timer')),
            'An original CPU service or timer remains loaded')
    return proof['actual_count']


def selected_chain(reader, control):
    proposal = R/'quality32-fresh-candidate-5400-9000-protocol-proposal-20261019'
    scope_pin = reader.pin(proposal/'root-source-scope-and-selected-chain-readback.json')
    require(scope_pin['sha256'] == 'da7b79f7880c193b9e50946b0ad12003a406376cbe6a14316203b0d18ff4da94',
            'Exact completed prospective9000 source/CPU scope required')
    scope = reader.read_pin(scope_pin)
    require(scope['status'] == 'TAIL9000_CHAIN152_AUTHORITY11_FOLLOWUP3_CPU_PASS_NOT_YET_ACQUIRED'
            and scope['total_actual_passed_CPU_tests'] == 166
            and scope['candidate_captured'] is False and scope['quality_qualified'] is False,
            'Complete original166 CPU checks, no quality reinterpretation required')
    authority = load(G/'tools/quality_capacity_proposal/verify_tail9000_chain_v1.py',
        '4954b0fd03bc3bbb09dcaddb490e11868fe662b6d313211a55bc589c8b49e7d4', '_tail_window_authority')
    runtime = load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445', '_tail_window_archives')
    proof = reader.read_pin(scope['chain']); tested = reader.read_pin(proof['precommit'])
    test_job = reader.read_pin(tested['job'])
    read = lambda entry, as_json=True: reader.read_pin(entry, as_json=as_json)
    authority.validate(proof, tested, test_job, scope['selected_sources'], read,
        runtime.archived_closure, lambda unit: control.show(unit)['LoadState'] == 'not-found', runtime.duration_seconds)
    require(verify_CPU_proof(read(scope['authority_CPU']), scope['authority_source'], 'authority', reader, control, runtime) == 11,
            'All original authority tests must pass')
    require(verify_CPU_proof(read(scope['followup_CPU']), scope['followup_source'], 'followup', reader, control, runtime) == 3,
            'All original followup tests must pass')
    package = scope['source_package']
    require(package['path'] == str(G/'tools/quality_capacity_proposal/profile04/runtime-source-package.json')
            and package['sha256'] == '3ee43f9bd95fdda8f02abc048999a84513da71125dfd6b2e6558f45d2de6caf9',
            'Only the newly tested9000 runtime package may be selected')
    contents = read(package)
    for relative, sha in contents['files'].items():
        require(hashlib.sha256((Path(contents['root'])/relative).read_bytes()).hexdigest() == sha,
                'A tested private runtime source changed')
    clarification = read(scope['clock_budget_clarification'])
    require(clarification['fixed_entry_based_timeout_s'] == 9000
            and clarification['fixed_admission_s'] == 5400 and clarification['nominal_difference_s'] == 3600
            and clarification['runtime_sources_changed'] is False,
            'Preserve entry-based deadline; warming consumes nominal drain')
    return scope_pin, scope, runtime


def require_launcher_CPU(reader, control, runtime):
    proof = reader.read_pin(reader.pin(P/'launcher-CPU-original01/root-original-launcher-CPU-readback.json'))
    require(proof['status'] == 'ORIGINAL_LAUNCHER_CPU_PASS_ALL6_EXIT0_OWNED_RELEASE_VERIFIED'
            and proof['tests'] == reader.pin(P/'test_window_launcher_v1.py'),
            'Actual original launcher refusal/scope tests required before a baseline')
    require(verify_CPU_proof(proof, reader.pin(__file__), 'launcher', reader, control, runtime) >= 10,
            'Selected launcher test scope is incomplete')
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-new-launcher', action='store_true')
    args = parser.parse_args()
    if not args.write_new_launcher:
        print('PLAN_ONLY: no reads, writes or launches')
        return
    original = PARENT.read_bytes()
    assert hashlib.sha256(original).hexdigest() == '9c4e38f08a524f9eb2fc1eefeb8ee361ac39f561881a95c7200e3deb91521900'
    assert not P.exists()
    value = original.decode(); changes = []
    def replace(before, after):
        nonlocal value
        assert before in value, before
        changes.append(dict(before=before, after=after, occurrences=value.count(before)))
        value = value.replace(before, after)
    replace('import os\n', 'import os\nimport re\nimport shlex\n')
    replace("P = R/'post-supervised-main-next8M-original01-preparation-20261019'", "P = R/'post-tail9000-main-next8M-original01-preparation-20261019'")
    replace("CHAIN = R/'supervised-quality32-chain-CPU-original01-preparation-20261019'", "CHAIN = R/'quality32-fresh-candidate-5400-9000-protocol-proposal-20261019/CPU-original02'")
    replace("OUT = R/'post-supervised-main-next8M-original01-20261019'", "OUT = R/'post-tail9000-main-next8M-original01-20261019'")
    replace("UNIT = 'robotron-post-supervised-main-next8M-original01-20261019.service'", "UNIT = 'robotron-post-tail9000-main-next8M-original01-20261019.service'")
    marker = '\n\ndef launch():\n'
    replace(marker, HELPERS+marker)
    replace("    execution = P/'execution'\n", "    require_launcher_CPU(reader, control, runtime)\n    execution = P/'execution'\n")
    start = value.index("    chain_pin = guard.pin(CHAIN/'root-all-original-groups-independent-readback.json')")
    end = value.index('    require_launcher_CPU(reader, control, runtime)', start)
    before = value[start:end]
    after = "    scope_pin, scope, runtime = selected_chain(reader, control)\n    chain_pin = scope['chain']\n"
    replace(before, after)
    replace("tag='scorecarry849_LR25_supervised_next8M_01_20261019'", "tag='scorecarry849_LR25_tail9000_next8M_01_20261019'")
    replace('Fixed5400/7200,min50', 'Fixed5400/9000,min50')
    replace('No reuse or retry of invalid1223/1275 quality or candidate667e0f27;',
            'No reuse or retry of invalid1223/1275/1306 quality or their checkpoints;')
    replace("    job['supervised_quality_chain'] = chain_pin\n", "    job['supervised_quality_chain'] = chain_pin\n    job['quality_precommit'].update(same_whole_cohort_timeout_s=9000, source_package=scope['source_package'])\n    job['clock_budget_clarification'] = scope['clock_budget_clarification']\n")
    replace("                     source_package=old_selection['source_package'], observer_integration_CPU=old_selection['observer_integration_CPU'],\n                     observer_integration_closure=old_selection['observer_integration_closure'], binding=state['current_main_binding'],",
            "                     source_package=scope['source_package'], completed_CPU_chain=chain_pin,\n                     completed_source_scope=scope_pin, clock_budget_clarification=scope['clock_budget_clarification'], binding=state['current_main_binding'],")
    P.mkdir(mode=0o700)
    target = P/'run-original-window.py'
    fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o664)
    with os.fdopen(fd, 'w') as stream:
        stream.write(value); stream.flush(); os.fsync(stream.fileno())
    report = dict(parent=str(PARENT), parent_sha256=hashlib.sha256(original).hexdigest(),
        target=str(target), target_sha256=hashlib.sha256(value.encode()).hexdigest(), transitions=changes,
        constructed_only=True, launched=False, numerical_or_capture_observer_changed=False)
    fd = os.open(P/'launcher-source-construction.json', os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o444)
    with os.fdopen(fd, 'w') as stream:
        json.dump(report, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(dict(source=str(target), launch_ready=False)))


if __name__ == '__main__':
    main()
