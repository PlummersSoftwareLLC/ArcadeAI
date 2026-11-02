"""Two NEW pure acceptance-contract cases; no old suite or actual verdict.

Prior fixture definitions seed synthetic future accepted OUTPUT. Every benchmark
value/ROOT verdict below is explicitly a CPU fixture, never installed authority.
"""
import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
P = HERE.parent


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=load('_new_RAW_acceptance',HERE/'accepted_raw_preview_authority_v1.py')
        cls.old_source=P/'posttrial-slot163-authorities-and-readonly-reconciliation-original02-guard-corrections/posttrial_slot163_output_authority_v2.py'
        cls.definitions=load('_prior_fixture_defs_NO_OLD_TESTS',P/'accepted-preview-declared-subset-source-original01/test_declared_preview_subset_v1.py')
        cls.definitions.Tests.setUpClass();cls.previous=cls.definitions.Tests()
        cls.base=cls.previous.fixtures.Tests.execbase
        target=P/'fast-preview-rgb565-capture-original01-preparation-20261027/raw-format1-existing-wire-policy-original01/main-lua-preview-fast-raw-format1-v1.lua'
        blob=target.read_bytes();cls.target=dict(path=str(target),sha256=hashlib.sha256(blob).hexdigest(),
            bytes=len(blob),identity=cls.base.identity(target.lstat()))

    def fixture(self):
        fixture,plan,old_read,table,pins=self.previous.complete_plan()
        authority=table[pins['authority']['path']]
        verdict_pin=dict(path='/CPUfixture/RAW-verdict');report_pin=dict(path='/CPUfixture/RAW-report')
        evidence_pin=dict(path='/CPUfixture/RAW-evidence')
        authority.update(output_lua=self.target,wire_policy=copy.deepcopy(self.raw.RAW_WIRE_POLICY),benchmark_verdict=verdict_pin)
        selection=table[pins['selection']['path']]
        selection.update(output_lua=self.target,wire_policy=copy.deepcopy(self.raw.RAW_WIRE_POLICY),benchmark_verdict=verdict_pin)
        binding=table[pins['binding']['path']];binding['preview_expected_target_sha256']=self.target['sha256']
        policy=table[pins['policy']['path']];actor=policy['baseline_actors']['163']
        actor['command'][actor['command'].index('-autoboot_script')+1]=self.target['path']
        authority['prior_actor']=copy.deepcopy(actor);selection['prior_actor']=authority['prior_actor']
        table[pins['transition']['path']]['schema']='robotron-owned-slot163-next-output-readonly-reconciliation-evidence-v1'
        verdict=dict(schema='robotron-root-selected-RAW-preview-operational-benchmark-verdict-v1',
            accepted=True,selected_target=self.target,wire_policy=copy.deepcopy(self.raw.RAW_WIRE_POLICY),
            actual_output_binding=pins['binding'],actual_benchmark_report=report_pin,
            benchmark_target_fps=30,minimum_fresh_cache_fps=27,both_ON_windows_target_met=True,
            useful_throughput_within_one_percent_point_budget=True,
            observed_ON_fresh_cache_fps=[28.5,29.1],relative_useful_throughput_point_change=-.004)
        report=dict(schema='robotron-root-selected-RAW-preview-operational-benchmark-report-v1',
            selected_target=self.target,wire_policy=copy.deepcopy(self.raw.RAW_WIRE_POLICY),actual_output_binding=pins['binding'],
            observed_ON_fresh_cache_fps=verdict['observed_ON_fresh_cache_fps'],
            relative_useful_throughput_point_change=verdict['relative_useful_throughput_point_change'],
            actual_raw_benchmark_evidence=evidence_pin)
        table[verdict_pin['path']]=verdict;table[report_pin['path']]=report
        table[evidence_pin['path']]=dict(CPU_fixture_ONLY=True)
        def read(pin,as_json=True):
            if pin['path'] in table:return copy.deepcopy(table[pin['path']])
            return old_read(pin,as_json)
        return authority,read,verdict,report,fixture

    def test_RAW_acceptance_requires_actual_verdict_original_criteria_and_keeps_INPUT(self):
        authority,read,verdict,report,fixture=self.fixture()
        manifest=self.raw.validate_authority(authority,read,self.base)
        self.assertEqual(manifest,fixture.manifest)
        self.assertEqual(manifest['target_lua']['sha256'],'507f3f5a799d49791d2c6cbca3f4600167a166c4a410723d4d29225d18b6e0ab')
        self.assertEqual(self.raw.accepted_target(authority,read,self.base),self.target)
        row=manifest['slots']['163']
        command,env=self.raw.prepare_output(authority,manifest,row['expected_args'],dict(row['expected_environment']),self.base)
        self.assertEqual(command[command.index('-autoboot_script')+1],self.target['path'])
        self.assertEqual(env['ROBOTRON_EVAL_MODE'],'1')
        for kind in ('threshold','budget','missing','wire','report','flag'):
            with self.subTest(kind=kind):
                authority,read,verdict,report,_=self.fixture()
                if kind=='threshold':verdict['observed_ON_fresh_cache_fps'][1]=26.99
                if kind=='budget':verdict['relative_useful_throughput_point_change']=-.011
                if kind=='missing':authority['benchmark_verdict']=None
                if kind=='wire':authority['wire_policy']['RLE_enabled']=True
                if kind=='report':report['selected_target']={'path':'/CPUfixture/wrong-target'}
                if kind=='flag':verdict['both_ON_windows_target_met']=False
                with self.assertRaises(ValueError):self.raw.validate_authority(authority,read,self.base)

    def test_old_rollback_branch_and_private_guard_preserved_with_explicit_None_extension(self):
        old=ast.parse(self.old_source.read_text());new=ast.parse((HERE/'accepted_raw_preview_authority_v1.py').read_text())
        def method(tree,name):return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        self.assertEqual(ast.dump(method(old,'validate_private_claim_directory'),include_attributes=False),
                         ast.dump(method(new,'validate_private_claim_directory'),include_attributes=False))
        def rollback(tree):
            fn=method(tree,'validate_authority')
            return next(n.orelse for n in fn.body if isinstance(n,ast.If) and n.orelse)
        old_branch=rollback(old);new_branch=rollback(new)
        self.assertEqual(ast.dump(ast.Module(body=old_branch,type_ignores=[]),include_attributes=False),
                         ast.dump(ast.Module(body=new_branch[1:],type_ignores=[]),include_attributes=False))
        fixture=self.previous.fixture()[0];manifest=fixture.manifest;row=manifest['slots']['163']
        rollback_authority=dict(mode=self.raw.ROLLBACK,output_lua=manifest['original_lua'])
        command,env=self.raw.prepare_output(rollback_authority,manifest,row['expected_args'],dict(row['expected_environment']),self.base)
        self.assertEqual(command[command.index('-autoboot_script')+1],manifest['original_lua']['path'])
        self.assertEqual(env['ROBOTRON_EVAL_MODE'],'1')


if __name__=='__main__':unittest.main()
