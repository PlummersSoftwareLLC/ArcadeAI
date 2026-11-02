"""Synthetic authority joins; no original services or scientific artifacts changed."""
import copy
from pathlib import Path
import sys
import unittest

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import verify_tail9000_chain_v1 as authority


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.values = {}
        def put(name, value):
            path = '/synthetic/'+name
            self.values[path] = value
            return dict(path=path, sha256=name)
        self.put = put
        self.worker = put('run_tail9000_CPU_group_v1.py', b'synthetic worker')
        self.source = put('selected-observer.py', b'synthetic observer')
        self.selected = dict(observer=self.source)
        self.job = dict(schema='robotron-tail9000-original-CPU-groups-v1', sources=[self.worker, self.source],
            candidate_captured=False, quality_launched=False,
            groups={group: ['synthetic_case_'+group] for group in authority.EXPECTED_COUNTS})
        job_pin = put('job.json', self.job)
        self.pre = dict(job=job_pin, groups_order=list(authority.EXPECTED_COUNTS), configs={},
            stop_after_any_failed_original=True, no_scientific_launch=True,
            clock_budget_clarification=put('clock.json', dict(nominal_difference_s=3600)))
        self.proof = dict(status='ALL_ORIGINAL_CPU_GROUPS_PASS', actual_tests=152,
            all_main195_and192_verified_after=True, quality_launched=False, candidate_captured=False,
            precommit=put('precommit.json', self.pre), groups=[],
            clock_budget_clarification=self.pre['clock_budget_clarification'])
        for group, count in authority.EXPECTED_COUNTS.items():
            owner = dict(unit='synthetic-'+group+'.service', timer='synthetic-'+group+'.timer')
            argv = ['/usr/bin/python3.12', '-I', '-B', self.worker['path'], '--execute', '--job',
                job_pin['path'], '--job-sha256', job_pin['sha256'], '--group', group]
            config = dict(unit=owner['unit'], output='/synthetic/output-'+group, argv=argv)
            wrapper = ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
                'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR='+config['output']+'/tmp']+argv
            fields = dict(ExecStart='{ path=/usr/bin/env ; argv[]='+' '.join(wrapper)+' ; ignore_errors=no ; pid=123 ; code=exited ; status=0 }',
                RuntimeMaxUSec='180', MemoryMax=str(4<<30), CPUQuotaPerSecUSec='2', Restart='no', SendSIGKILL='no')
            report = dict(group=group, actual_tests_run=count, loaded_test_count=count, passed=True,
                failures=0, errors=0, skipped=0, actual_quality_run=False, actual_policy_publication=False,
                CUDA_hidden=True, numerical_runtime_imported=False, selected_tests=self.job['groups'][group])
            closure = dict(original_exit=0, lifecycle_complete=True, unit_released=True,
                full_original_archives=[{} for _ in range(6)], owned_release=[{}, {}], fields=fields)
            self.pre['configs'][group] = put('config-'+group+'.json', config)
            self.proof['groups'].append(dict(group=group, actual_count=count, actual_tests=put('report-'+group+'.json', report),
                owner=put('owner-'+group+'.json', owner), closure=put('closure-'+group+'.json', closure),
                original_exit=0, all_six_original_archives_verified=True, exact_service_and_timer_releases_verified=True))

    def read(self, entry, as_json=True):
        return self.values[entry['path']]

    def archives(self, closure, owner, read, exit_zero):
        self.assertTrue(exit_zero)
        if closure['original_exit'] != 0:
            raise ValueError('Original CPU owner failed')
        return closure['fields']

    def validate(self, absent=lambda unit: True):
        return authority.validate(self.proof, self.pre, self.job, self.selected, self.read,
                                  self.archives, absent, float)

    def test_all_eight_original_groups_and_selected_sources_join(self):
        result = self.validate()
        self.assertEqual(result['actual_tests'], 152)
        self.assertEqual(result['original_descriptors'], 48)
        self.assertEqual(result['released_original_units'], 16)
        self.assertFalse(result['scientific_quality_qualified'])

    def test_missing_reordered_or_duplicate_group_cannot_pass(self):
        original = copy.deepcopy(self.proof)
        for kind in ('missing', 'order', 'duplicate'):
            self.proof = copy.deepcopy(original)
            if kind == 'missing': self.proof['groups'].pop()
            elif kind == 'order': self.proof['groups'].reverse()
            else: self.proof['groups'][-1] = self.proof['groups'][0]
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.validate()

    def test_wrong_total_main_scope_or_quality_claim_refused(self):
        for key, value in [('actual_tests', 151), ('all_main195_and192_verified_after', False),
                           ('candidate_captured', True), ('quality_launched', True), ('status', 'PARTIAL_PASS')]:
            before = self.proof[key]; self.proof[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate()
            self.proof[key] = before

    def test_changed_skipped_failed_or_unrelated_test_report_refused(self):
        report = self.values['/synthetic/report-D.json']
        for key, value in [('actual_tests_run', 1), ('skipped', 1), ('errors', 1), ('failures', 1),
                           ('passed', False), ('CUDA_hidden', False), ('actual_quality_run', True),
                           ('actual_policy_publication', True), ('numerical_runtime_imported', True),
                           ('selected_tests', ['unrelated'])]:
            before = report[key]; report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate()
            report[key] = before

    def test_missing_selected_source_or_changed_full_pin_refused(self):
        self.selected['observer'] = dict(self.source, sha256='foreign')
        with self.assertRaises(ValueError): self.validate()
        self.selected['observer'] = self.source
        self.job['sources'].append(dict(self.source))
        with self.assertRaises(ValueError): self.validate()

    def test_wrong_worker_job_or_group_in_original_command_refused(self):
        config = self.values['/synthetic/config-C.json']
        for index, value in [(3, '/foreign/run_tail9000_CPU_group_v1.py'), (6, '/other/job.json'),
                             (8, 'wrong-hash'), (10, 'A')]:
            before = config['argv'][index]; config['argv'][index] = value
            with self.subTest(index=index), self.assertRaises(ValueError): self.validate()
            config['argv'][index] = before

    def test_forged_archive_command_refused(self):
        fields = self.values['/synthetic/closure-E.json']['fields']
        fields['ExecStart'] = fields['ExecStart'].replace('--group E', '--group F')
        with self.assertRaises(ValueError): self.validate()

    def test_wrong_CPU_limits_restart_or_SIGKILL_refused(self):
        fields = self.values['/synthetic/closure-F.json']['fields']
        for key, value in [('RuntimeMaxUSec', '181'), ('MemoryMax', str(8<<30)),
                           ('CPUQuotaPerSecUSec', '4'), ('Restart', 'always'), ('SendSIGKILL', 'yes')]:
            before = fields[key]; fields[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate()
            fields[key] = before

    def test_nonzero_original_missing_archive_or_incomplete_release_refused(self):
        closure = self.values['/synthetic/closure-G.json']
        for key, value in [('original_exit', 1), ('unit_released', False), ('lifecycle_complete', False),
                           ('full_original_archives', [{}]*5), ('owned_release', [{}])]:
            before = closure[key]; closure[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate()
            closure[key] = before

    def test_still_loaded_original_unit_or_duplicate_owner_refused(self):
        with self.assertRaises(ValueError): self.validate(absent=lambda unit: unit != 'synthetic-H.timer')
        self.values['/synthetic/owner-H.json'] = self.values['/synthetic/owner-A.json']
        with self.assertRaises(ValueError): self.validate()

    def test_extra_test_group_or_retry_scope_refused(self):
        self.pre['configs']['I'] = self.pre['configs']['A']
        with self.assertRaises(ValueError): self.validate()
        del self.pre['configs']['I']
        self.pre['stop_after_any_failed_original'] = False
        with self.assertRaises(ValueError): self.validate()


if __name__ == '__main__':
    unittest.main()
