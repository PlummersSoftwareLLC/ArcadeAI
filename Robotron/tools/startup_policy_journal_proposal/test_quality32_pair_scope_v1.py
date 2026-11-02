"""New CPU-only guards for the fixed1741/2202 quality scope; no games or models."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

B=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal')
R=B.parents[1]/'logs/managed-learning-20261015/run-26'
N=R/'quality32-protected1741-vs-normal2202-start-certified-original01-preparation-20261022'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

q=load('_quality_pair_runtime',B/'run_compiled_full_tail32_quality_v1.py')
old=load('_quality_pair_original_base',B/'run_compiled_full_tail32_v2.py')
control=load('_quality_pair_control',B/'control_compiled_full_tail32_quality_v1.py')
old_control=load('_quality_pair_old_control',B/'control_compiled_full_tail32_v2.py')

class QualityPairScopeV1(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.original=json.loads((R/'compiled32-policy-full-tail-cleanup-v2-real-original01-preparation-20261022/job.json').read_text())

    def fixture(self,leg):
        job=copy.deepcopy(self.original)
        job.update(schema='robotron-compiled-full-tail32-quality-original-v1',quality_leg=leg,
            quality_pair_precommit={'sha256':q.PAIR_SHA},minimum_completed_games=50,
            admission_s=5400,output=str(Path(self.temp.name)/'never-created-output'))
        role=q.POLICIES[q.ROLES[leg]]
        job['checkpoint']['sha256']=role['sha256']
        job['expected_policy_clocks']=dict(role['clocks'])
        return job

    def reject(self,job):
        with self.assertRaises(ValueError):q.validate_job(job)

    def test_four_fixed_roles_accept_their_exact_saved_policy_and_never_the_other_policy(self):
        for leg in ('R1','C1','R2','C2'):
            with self.subTest(leg=leg):
                job=self.fixture(leg)
                self.assertEqual(q.validate_job(job),Path(job['output']))
                bad=copy.deepcopy(job)
                other='candidate'if q.ROLES[leg]=='reference'else'reference'
                bad['checkpoint']['sha256']=q.POLICIES[other]['sha256']
                self.reject(bad)
                bad['expected_policy_clocks']=q.POLICIES[other]['clocks']
                self.reject(bad)

    def test_pair_identity_and_typed_saved_clocks_reject_relabelled_or_changed_candidates(self):
        job=self.fixture('C1')
        for key,value in [('quality_leg','C3'),('quality_leg','reference'),
                ('quality_pair_precommit',{'sha256':'0'*64}),
                ('expected_policy_clocks',{**job['expected_policy_clocks'],'learner_frame_count':2202676282}),
                ('expected_policy_clocks',{**job['expected_policy_clocks'],'training_steps':8863417.0})]:
            bad=copy.deepcopy(job);bad[key]=value;self.reject(bad)

    def test_quality_minimum_fixed_admission_and_timeout_cannot_reuse_engineering_scope_or_extend(self):
        job=self.fixture('R1')
        for key,values in [('minimum_completed_games',(32,49,51,50.0,True)),
                ('admission_s',(90,5399,5401,5400.0)),
                ('whole_cohort_timeout_s',(8999,9001)),('wall_limit_s',(9599,9601))]:
            for value in values:
                with self.subTest(key=key,value=value):
                    bad=copy.deepcopy(job);bad[key]=value;self.reject(bad)
        self.reject(self.original)
        with self.assertRaises(ValueError):old.validate_job(job)

    def test_actual_controller_family_binds_only_the_new_runtime_and_same_owned_resources(self):
        path=Path(self.temp.name)/'config.json';future=N/'never-launched-quality-fixture/job.json'
        runtime=str(B/'run_compiled_full_tail32_quality_v1.py')
        cfg=dict(unit='robotron-compiled-full-tail32-integration-quality-guard-original01.service',
            output=str(Path(self.temp.name)/'never-created-controller-output'),
            argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',runtime,
                '--execute','--job',str(future),'--job-sha256','1'*64,'--source-sha256','2'*64],
            properties=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=9660',
                'TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
            pins=[{'path':str(future),'sha256':'1'*64},{'path':runtime,'sha256':'2'*64}],observation_s=9720)
        path.write_text(json.dumps(cfg));self.assertEqual(control.checked_config(path),cfg)
        with self.assertRaises(ValueError):old_control.checked_config(path)
        for key,value in [('observation_s',9721),('properties',cfg['properties'][:-1]+['SendSIGKILL=yes'])]:
            bad=copy.deepcopy(cfg);bad[key]=value;path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):control.checked_config(path)

    def test_transport_cleanup_health_and_controller_lifecycle_bodies_are_preserved(self):
        def definitions(path):
            return {n.name:ast.dump(n,include_attributes=False)for n in ast.parse(path.read_text()).body
                if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        a,b=definitions(Path(old.__file__)),definitions(Path(q.__file__))
        self.assertEqual(set(a),set(b))
        self.assertEqual([k for k in a if a[k]!=b[k]],['validate_job','run'])
        a,b=definitions(Path(old_control.__file__)),definitions(Path(control.__file__))
        self.assertEqual([k for k in a if a[k]!=b[k]],['checked_config'])
        run=next(n for n in ast.parse(Path(q.__file__).read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='run')
        enter=[n for n in ast.walk(run)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='enter']
        self.assertEqual(len(enter),1)
        cohort_arg=next(k.value for k in enter[0].keywords if k.arg=='cohort_s')
        self.assertEqual(ast.dump(cohort_arg),ast.dump(ast.parse("job['admission_s']",mode='eval').body))
        self.assertIn("before_stop['count'] == before_stop['started'] >= 50",ast.unparse(run))

if __name__=='__main__':unittest.main(verbosity=2)
