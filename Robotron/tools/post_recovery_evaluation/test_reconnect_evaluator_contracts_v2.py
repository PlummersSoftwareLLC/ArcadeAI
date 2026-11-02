"""Reject source/protocol substitutions in actual inert evaluator contexts."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
I=ROOT/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class ReconnectContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h=load('_reconnect_contract_test_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
        cls.report=json.loads((I/'admission-evaluators-preparation-CPU-original01/runtime/report.json').read_bytes())

    def subjects(self,kind):
        prepared=json.loads(self.h.checked(self.report[kind+'_prepared']).read_bytes())
        case=prepared['cases'][0]
        return json.loads(self.h.checked(case['native_job']).read_bytes()),load('_reconnect_test_'+kind,Path(case['runtime']['path']))

    def test_deadline_exact_nine_dependencies_and_projection_opt_in(self):
        job,native=self.subjects('deadline')
        protocol=json.loads(self.h.checked(job['main_health_protocol']).read_bytes())
        family=json.loads(self.h.checked(job['source_family_manifest']).read_bytes())
        expected={'client','worker','health','health_base','API_projection','round_admission','interpreter','durability','control'}
        self.assertEqual(set(family['main_observer']),expected)
        for fault in ('base_hash','projection_hash','missing_base','missing_projection','extra','flag_false','flag_missing','admission_hash','missing_admission','admission_false','admission_missing'):
            p,f,j=copy.deepcopy(protocol),copy.deepcopy(family),copy.deepcopy(job)
            if fault=='admission_hash':f['main_observer']['round_admission']['sha256']='f'*64
            elif fault=='missing_admission':f['main_observer'].pop('round_admission')
            elif fault=='admission_false':p['source_bound_natural_round_admission']=False
            elif fault=='admission_missing':p.pop('source_bound_natural_round_admission')
            elif fault=='base_hash':f['main_observer']['health_base']['sha256']='f'*64
            elif fault=='projection_hash':f['main_observer']['API_projection']['sha256']='f'*64
            elif fault=='missing_base':f['main_observer'].pop('health_base')
            elif fault=='missing_projection':f['main_observer'].pop('API_projection')
            elif fault=='extra':f['main_observer']['foreign']=f['main_observer']['health']
            elif fault=='flag_false':p['source_bound_API_reconnect_projection']=False
            else:p.pop('source_bound_API_reconnect_projection')
            j['observer_sources']=copy.deepcopy(f['main_observer'])
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):
                native.validate_main_health_contract(j,p,f)

    def test_fullgame_exact_nine_dependencies_and_projection_opt_in(self):
        job,native=self.subjects('fullgame')
        protocol=json.loads(self.h.checked(job['main_health_protocol']).read_bytes())
        family=json.loads(self.h.checked(job['source_family_manifest']).read_bytes())
        self.assertEqual(len(family['main_observer']),9)
        for fault in ('base_hash','projection_hash','missing_base','missing_projection','extra','flag_false','flag_missing','admission_hash','missing_admission','admission_false','admission_missing'):
            p,f,j=copy.deepcopy(protocol),copy.deepcopy(family),copy.deepcopy(job)
            if fault=='admission_hash':f['main_observer']['round_admission']['sha256']='f'*64
            elif fault=='missing_admission':f['main_observer'].pop('round_admission')
            elif fault=='admission_false':p['source_bound_natural_round_admission']=False
            elif fault=='admission_missing':p.pop('source_bound_natural_round_admission')
            elif fault=='base_hash':f['main_observer']['health_base']['sha256']='f'*64
            elif fault=='projection_hash':f['main_observer']['API_projection']['sha256']='f'*64
            elif fault=='missing_base':f['main_observer'].pop('health_base')
            elif fault=='missing_projection':f['main_observer'].pop('API_projection')
            elif fault=='extra':f['main_observer']['foreign']=f['main_observer']['health']
            elif fault=='flag_false':p['source_bound_API_reconnect_projection']=False
            else:p.pop('source_bound_API_reconnect_projection')
            with tempfile.TemporaryDirectory(prefix='robotron-reconnect-contract-')as directory:
                d=Path(directory)
                j['main_health_protocol']=self.h.put(d/'protocol.json',p)
                j['source_family_manifest']=self.h.put(d/'family.json',f)
                with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):
                    native.validate_completed_context(j,self.h)
