"""Authenticate the complete prospective9000 CPU proof before future acquisition.

Pure standard-library predicates; no execution, policy publication or retry.
The caller supplies the immutable reader and original-archive validator.
"""
import re
import shlex

EXPECTED_COUNTS = dict(A=109, B=2, C=3, D=2, E=2, F=2, G=3, H=29)


def require(value, message):
    if not value:
        raise ValueError(message)


def validate(proof, precommit, job, selected_sources, read, archives, absent, duration):
    require(proof['status'] == 'ALL_ORIGINAL_CPU_GROUPS_PASS'
            and proof['actual_tests'] == sum(EXPECTED_COUNTS.values())
            and proof['all_main195_and192_verified_after'] is True
            and proof['quality_launched'] is False and proof['candidate_captured'] is False,
            'All original CPU groups must close successfully before new acquisition')
    require([row['group'] for row in proof['groups']] == list(EXPECTED_COUNTS)
            and precommit['groups_order'] == list(EXPECTED_COUNTS)
            and set(precommit['configs']) == set(job['groups']) == set(EXPECTED_COUNTS)
            and precommit['stop_after_any_failed_original'] is True
            and precommit['no_scientific_launch'] is True,
            'Exact independent CPU groups and original no-launch scope required')
    require(job['schema'] == 'robotron-tail9000-original-CPU-groups-v1'
            and job['candidate_captured'] is False and job['quality_launched'] is False,
            'Exact tested future9000 CPU job required')
    require(read(precommit['job']) == job and read(proof['precommit']) == precommit
            and proof['clock_budget_clarification'] == precommit['clock_budget_clarification'],
            'Independent proof must rejoin its original test precommit and clock description')
    require(len({pin['path'] for pin in job['sources']}) == len(job['sources']),
            'Duplicate tested source paths are ambiguous')
    for pin in selected_sources.values():
        require(pin in job['sources'], 'Selected source was not bound by actual CPU groups')
        read(pin, False)
    for pin in job['sources']:
        read(pin, False)
    units = set()
    for row in proof['groups']:
        group = row['group']; count = EXPECTED_COUNTS[group]
        report = read(row['actual_tests'])
        require(report['group'] == group and report['actual_tests_run'] == report['loaded_test_count'] == row['actual_count'] == count
                and report['passed'] is True and report['failures'] == report['errors'] == report['skipped'] == 0
                and report['actual_quality_run'] is False and report['actual_policy_publication'] is False
                and report['CUDA_hidden'] is True and report['numerical_runtime_imported'] is False
                and report['selected_tests'] == job['groups'][group],
                'Actual original test count, selection or CPU-only result differs')
        owner = read(row['owner']); closure = read(row['closure'])
        config = read(precommit['configs'][group])
        require(owner['unit'] not in units and owner['timer'] not in units
                and owner['timer'] == owner['unit'].removesuffix('.service')+'.timer',
                'Distinct original CPU service and timer owners required')
        units.update((owner['unit'], owner['timer']))
        fields = archives(closure, owner, read, exit_zero=True)
        require(closure['original_exit'] == row['original_exit'] == 0
                and closure['lifecycle_complete'] is True and closure['unit_released'] is True
                and len(closure['full_original_archives']) == 6
                and len(closure['owned_release']) == 2
                and row['all_six_original_archives_verified'] is True
                and row['exact_service_and_timer_releases_verified'] is True,
                'Every original CPU result and all six archives/releases must be verified')
        argv = config['argv']
        require(config['unit'] == owner['unit']
                and argv[:3] == ['/usr/bin/python3.12', '-I', '-B']
                and len(argv) == 11 and argv[3].endswith('/run_tail9000_CPU_group_v1.py')
                and any(pin['path'] == argv[3] for pin in job['sources'])
                and argv[4:] == ['--execute', '--job', precommit['job']['path'],
                    '--job-sha256', precommit['job']['sha256'], '--group', group],
                'Exact original CPU worker, job and group command required')
        wrapper = ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH',
            'CUDA_VISIBLE_DEVICES=', 'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR='+config['output']+'/tmp']+argv
        match = re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}', fields['ExecStart'])
        require(match is not None and shlex.split(match[1]) == wrapper,
                'Actual original CPU archive command differs from selected config')
        require(duration(fields['RuntimeMaxUSec']) == 180 and fields['MemoryMax'] == str(4<<30)
                and duration(fields['CPUQuotaPerSecUSec']) == 2
                and fields['Restart'] == 'no' and fields['SendSIGKILL'] == 'no',
                'Actual original CPU resource bounds or restart policy differs')
        require(absent(owner['unit']) and absent(owner['timer']),
                'A selected original CPU unit remains loaded')
    return dict(status='COMPLETE_ORIGINAL9000_CPU_AUTHORITY_VERIFIED', actual_tests=sum(EXPECTED_COUNTS.values()),
        groups=list(EXPECTED_COUNTS), original_descriptors=6*len(EXPECTED_COUNTS),
        released_original_units=len(units), scientific_quality_qualified=False, candidate_captured=False)
