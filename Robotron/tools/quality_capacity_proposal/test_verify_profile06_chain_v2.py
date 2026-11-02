"""One real source-chain join plus in-memory refusal tests; no science launch."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
H=G/'tools/quality_capacity_proposal'
JOB=None
READER=None
POOL=None
READ_CACHE={}
READ_PATHS=set()
CPU_CALLS=[]


def real_read(pin,as_json=True):
    require_path(pin['path'])
    key=(pin['path'],pin['sha256'],as_json)
    if key not in READ_CACHE:READ_CACHE[key]=READER.read_pin(pin,as_json=as_json)
    READ_PATHS.add(pin['path'])
    return copy.deepcopy(READ_CACHE[key]) if as_json else READ_CACHE[key]


def require_path(path):
    if path not in POOL:raise ValueError('Unbound authority dependency: '+path)


def real_check(pin):
    require_path(pin['path'])
    return READER.pin(pin['path'])==pin


class TrackedReader:
    def read_pin(self,pin,*,as_json=True):return real_read(pin,as_json)
    def pin(self,path):return READER.pin(path)
    def checked_module(self,name,pin):
        real_read(pin,False)
        return READER.checked_module(name,pin)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authority=READER.checked_module('profile06_authority_under_test',JOB['authority_source'])
        cls.control=READER.checked_module('profile06_selftest_controller',JOB['controller_source'])
        cls.runtime=READER.checked_module('profile06_selftest_archives',JOB['archive_source'])
        cls.old_cpu=READER.checked_module('profile06_selftest_CPU_resources',JOB['resource_checker_source'])
        cls.bundle=real_read(JOB['bundle']);cls.selected=real_read(JOB['selected_sources'])
        cls.actual_baseline=None

    def setUp(self):
        self.bundle=copy.deepcopy(type(self).bundle)
        self.selected=copy.deepcopy(type(self).selected)
        self.overrides={};self.bad_input=None;self.cpu_calls=[]
        self.use_real_CPU=False;self.fail_CPU=False;self.bad_baseline=False

    def read(self,pin,as_json=True):
        if pin['path'] in self.overrides:
            value=self.overrides[pin['path']]
            return copy.deepcopy(value) if as_json else value
        return real_read(pin,as_json)

    def check(self,pin):
        return False if pin['path']==self.bad_input else real_check(pin)

    def cpu(self,config,owner,closure,inputs,argv,units):
        self.cpu_calls.append(closure['path'])
        if self.fail_CPU:raise ValueError('Injected original CPU closure refusal')
        if self.use_real_CPU:
            result=self.old_cpu.cpu(config,owner,closure,inputs,argv,self.read,self.runtime.archived_closure,
                lambda unit:self.control.show(unit)['LoadState']=='not-found',self.runtime.duration_seconds,units)
            CPU_CALLS.append(closure['path']);return result
        # Negative predicate cases replace only external CPU capabilities;
        # the real positive validates every original command and resource.
        identity=self.read(owner);units.update((identity['unit'],identity['timer']))

    def baseline(self,old,pin):
        if type(self).actual_baseline is None:
            module=READER.checked_module('profile06_actual_unchanged_baseline_'+str(time.time_ns()),pin)
            type(self).actual_baseline=module.authorize(old,TrackedReader(),self.control,self.runtime)
        value=copy.deepcopy(type(self).actual_baseline)
        if self.bad_baseline:value['source_authority']['total_source_tests']=219
        return value

    def run_gate(self):
        return self.authority.validate(self.bundle,self.selected,self.read,self.check,self.cpu,self.baseline)

    def mutate_report(self,row,change):
        pin=row['actual_tests'];report=self.read(pin);change(report);self.overrides[pin['path']]=report
        archive=row['consoles']['stdout'].get('archive',row['consoles']['stdout'].get('readonly_archive'))
        raw=self.read(archive,False);lines=raw.splitlines(keepends=True)
        self.overrides[archive['path']]=b''.join(lines[:-1])+(json.dumps(report)+'\n').encode()

    def test_00_actual_original_chain_joins_without_source_or_scientific_changes(self):
        self.use_real_CPU=True
        value=self.run_gate()
        self.assertEqual(value['status'],'COMBINED_PROFILE06_ORIGINAL_SOURCE_AND_CPU_CHAIN_VERIFIED')
        self.assertEqual(value['additional_original_CPU_units'],41)
        self.assertEqual(len(self.cpu_calls),41)
        self.assertFalse(value['source_selected_for_science'])
        self.assertFalse(value['candidate_captured']);self.assertFalse(value['quality_qualified'])
        self.assertEqual(value['bound_integration_tests'],113)

    def test_01_missing_required_proof_refuses_before_baseline_or_CPU(self):
        del self.bundle['wire56']
        with self.assertRaises(ValueError):self.run_gate()
        self.assertEqual(self.cpu_calls,[])

    def test_02_foreign_combined_package_hash_is_refused(self):
        self.bundle['package']['sha256']='0'*64
        with self.assertRaises(ValueError):self.run_gate()

    def test_03_foreign_selected_reviewer_source_is_refused(self):
        self.selected['review_closed_quality32_v8.py']['sha256']='f'*64
        with self.assertRaises(ValueError):self.run_gate()

    def test_04_extra_selected_source_cannot_change_the_authorized_set(self):
        self.selected['arbitrary.py']=copy.deepcopy(self.selected['review_closed_quality32_v8.py'])
        with self.assertRaises(ValueError):self.run_gate()

    def test_05_original_baseline219_cannot_substitute_for220(self):
        self.bad_baseline=True
        with self.assertRaisesRegex(ValueError,'baseline220'):self.run_gate()

    def test_06_original_CPU_capability_failure_is_not_ignored(self):
        self.fail_CPU=True
        with self.assertRaisesRegex(ValueError,'original CPU closure refusal'):self.run_gate()
        self.assertEqual(len(self.cpu_calls),1)

    def test_07_changed_prospective_input_refuses_the_chain(self):
        row=self.read(self.bundle['journal34']);job=self.read(row['job'])
        self.bad_input=job['inputs'][0]['path']
        with self.assertRaisesRegex(ValueError,'prospectively bound input changed'):self.run_gate()

    def test_08_primitive_result_cannot_claim_full_handler_validation(self):
        row=self.read(self.bundle['primitive18'])
        self.mutate_report(row,lambda report:report.update(full_handler_validated=True))
        with self.assertRaisesRegex(ValueError,'Primitive18 scope'):self.run_gate()

    def test_09_closed_gate_must_retain_the_actual_native_nonzero_exit(self):
        row=self.read(self.bundle['closed26'])
        self.mutate_report(row,lambda report:report.update(actual_native_review_outer_exits=[0,2,1]))
        with self.assertRaisesRegex(ValueError,'closed-original gate26'):self.run_gate()

    def test_10_dependency_edit_beyond_binding_substitutions_is_refused(self):
        source=self.selected['protect_quality32_winner_v6.py']
        self.overrides[source['path']]=self.read(source,False)+b'\n# an unreviewed dependency change\n'
        with self.assertRaisesRegex(ValueError,'beyond exact tested source bindings'):self.run_gate()

    def test_11_missing_expensive_original_cannot_be_rescued_by_other_groups(self):
        pin=self.bundle['bound36'];value=self.read(pin);value['groups'].pop();self.overrides[pin['path']]=value
        with self.assertRaisesRegex(ValueError,'separate expensive original CPU'):self.run_gate()

    def test_12_duplicate_expensive_case_cannot_replace_a_missing_case(self):
        value=self.read(self.bundle['bound36']);first=self.read(value['groups'][0]['actual_tests'])['selected_tests'][0]
        self.mutate_report(value['groups'][1],lambda report:report.update(selected_tests=[first]))
        with self.assertRaisesRegex(ValueError,'distinct bound integration cases'):self.run_gate()

    def test_13_missing_full_handler_variant_is_refused(self):
        wire=self.read(self.bundle['wire56']);value=self.read(wire['original_child_result']);value['cases'].pop()
        self.overrides[wire['original_child_result']['path']]=value
        with self.assertRaisesRegex(ValueError,'actual full-handler56 source/result joins'):self.run_gate()

    def test_14_duplicate_full_handler_variant_is_refused_even_with_matching_results(self):
        wire=self.read(self.bundle['wire56']);child=self.read(wire['original_child_result']);parent=self.read(wire['original_parent_result'])
        child['cases'][1]=copy.deepcopy(child['cases'][0]);parent['cases']=copy.deepcopy(child['cases'])
        self.overrides[wire['original_child_result']['path']]=child;self.overrides[wire['original_parent_result']['path']]=parent
        with self.assertRaisesRegex(ValueError,'Every actual full-handler variant'):self.run_gate()

    def test_15_full_handler_result_from_another_work_directory_is_refused(self):
        pin=self.bundle['wire56'];wire=self.read(pin);wire['original_parent_result']['path']='/foreign/result.json'
        self.overrides[pin['path']]=wire
        # Its foreign immutable read is also forbidden by the declared pool.
        with self.assertRaises(ValueError):self.run_gate()

    def test_16_changed_original_full_handler_journal_is_refused(self):
        wire=self.read(self.bundle['wire56']);entry=next(iter(wire['original_journals'].values()))
        self.bad_input=entry['files']['games.jsonl']['original']['path']
        with self.assertRaisesRegex(ValueError,'original full-handler journal changed'):self.run_gate()

    def test_17_combined_package_file_must_be_in_the_actual_original_CPU_inventory(self):
        row=self.read(self.bundle['bound77']);job=self.read(row['job'])
        target=str(H/'profile06/Robotron/Scripts/display.lua')
        job['inputs']=[p for p in job['inputs'] if p['path']!=target]
        self.overrides[row['job']['path']]=job
        with self.assertRaisesRegex(ValueError,'package file absent'):self.run_gate()


def main():
    global JOB,READER,POOL
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--job-sha256',required=True);a=p.parse_args()
    time.sleep(2)
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;JOB=json.loads(raw)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    readerpath=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    assert hashlib.sha256(readerpath.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
    spec=importlib.util.spec_from_file_location('profile06_authority_test_reader',readerpath);READER=importlib.util.module_from_spec(spec);spec.loader.exec_module(READER)
    POOL={pin['path']:pin for pin in JOB['immutable_inputs']+JOB['quiescent_normal_inputs']}
    assert len(POOL)==len(JOB['immutable_inputs'])+len(JOB['quiescent_normal_inputs'])
    for pin in POOL.values():assert READER.pin(pin['path'])==pin
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);assert suite.countTestCases()==18
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    for pin in POOL.values():assert READER.pin(pin['path'])==pin
    assert 'torch' not in sys.modules and 'numpy' not in sys.modules
    print(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),
        errors=len(result.errors),skipped=len(result.skipped),positive_actual_original_IO=True,
        positive_actual_new_CPU_units=len(CPU_CALLS),actual_read_paths=sorted(READ_PATHS),
        all_declared_inputs_unchanged=True,negative_cases_use_in_memory_overrides_and_CPU_substitutes=True,
        CUDA_hidden=True,numerical_runtime_imported=False,actual_quality_run=False,actual_candidate_captured=False,
        source_selected_for_science=False,quality_qualified=False,learning_speed_gain_verified=False)),flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
