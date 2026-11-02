"""Focused new functions/paths. Retained real barrier bytes + synthetic launch phases."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
sys.path.insert(0,str(ROOT))
from tools.post_recovery_evaluation import test_round_admission_proof_v3 as retained


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


launch=load('_new_launcher_tests',HERE/'launcher_census_v1.py')
health=load('_new_transport_tests',HERE/'round_health_transport_launcher_v1.py')
base=health.base()


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory=ROOT/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/natural-round-admission-single-journal-CPU-original03/runtime'
        with patch.dict(os.environ,ROBOTRON_ADMISSION_ENGINEERING_FIXTURES=str(directory)):
            retained.RoundAdmissionTests.setUpClass()
        cls.template=retained.RoundAdmissionTests()
        cls.contract_case=launch.prepare_case(retained.RoundAdmissionTests.original_case)

    def fixture(self,stage='python'):
        case,prior,sample=self.template.fixture(3,1)
        case['launcher_contract']=copy.deepcopy(self.contract_case['launcher_contract'])
        case['inputs']=copy.deepcopy(self.contract_case['inputs'])
        self.number=sample['round_admission']['effective_round']
        anchor=case['launcher_contract']['clock_anchor']
        offset=(anchor['boottime_s']-anchor['monotonic_before_s']+anchor['boottime_s']-anchor['monotonic_after_s'])/2
        clock=dict(ticks_per_second=os.sysconf('SC_CLK_TCK'),monotonic_before_s=sample['monotonic_s']-.02,
            monotonic_after_s=sample['monotonic_s']-.0199,boottime_s=sample['monotonic_s']-.01995+offset)
        actor=sample['actors']['2']
        actor['starttime_ticks']=int((clock['boottime_s']-.1)*clock['ticks_per_second'])
        actor['environment']=launch.expected_input(case,'2',self.number)
        actor['command']=launch.expected_commands(case)[stage]
        actor['executable']=copy.deepcopy(case['launcher_contract']['stage_executables'][stage])
        self.attach(case,sample,clock)
        return case,prior,sample

    def attach(self,case,sample,clock=None):
        if clock is None:clock=sample['launcher_census']['clock']
        rows=[]
        for slot,record in sample['actors'].items():
            rows.append(dict(pid=record['pid'],record=copy.deepcopy(record),confirm_record=copy.deepcopy(record),stage=launch.phase(case,record)))
        sample['launcher_census']=dict(schema=launch.SCHEMA,round=self.number,clock=copy.deepcopy(clock),
            original_children=[str(row['pid'])for row in rows],children=rows)
        sample['observed_counts']=base.observed_counts(sample)
        retained.transport(sample)

    def test_exact_input_stages_then_same_birth_MAME_output(self):
        for stage in ('env','bash','python'):
            with self.subTest(stage=stage):
                case,prior,sample=self.fixture(stage)
                health.validate(case,sample,previous=prior)
                current=copy.deepcopy(sample);actor=current['actors']['2']
                actor['command']=case['actor_command'];actor['executable']=case['actor_executable']
                actor['environment']=dict(case['actor_environment'],ROBOTRON_CLIENT_SLOT='2',ROBOTRON_ACTOR_ROUND=str(self.number),
                    ROBOTRON_EVAL_MODE='1'if case['slot_eval']['2']else'2',ROBOTRON_PREVIEW_CLIENT='0')
                current['unix_s']+=.01;current['monotonic_s']+=.01;current['api']['ts']+=.01
                self.attach(case,current)
                health.validate(case,current,previous=sample)
                self.assertEqual((actor['pid'],actor['starttime_ticks']),
                    (sample['actors']['2']['pid'],sample['actors']['2']['starttime_ticks']))

    def test_wrong_input_role_environment_argv_executable_and_owner_refused(self):
        for fault in ('role','extra_env','argv','exe','parent','cgroup','uid','affinity'):
            case,prior,sample=self.fixture();actor=sample['actors']['2']
            if fault=='role':actor['environment']['ROBOTRON_EVAL_MODE']='1'
            if fault=='extra_env':actor['environment']['ROBOTRON_UNDECLARED']='1'
            if fault=='argv':actor['command'].append('--foreign')
            if fault=='exe':actor['executable']['identity']['inode']+=1
            if fault=='parent':actor['parent_pid']+=1
            if fault=='cgroup':actor['cgroup']+='/foreign'
            if fault=='uid':actor['uids'][0]+=1
            if fault=='affinity':actor['affinity']=actor['affinity'][1:]
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):
                self.attach(case,sample);health.validate(case,sample,previous=prior)

    def test_birth_replacement_backward_stage_and_unobserved_MAME_refused(self):
        for fault in ('birth','pid','backward','vanished'):
            case,prior,previous=self.fixture();sample=copy.deepcopy(previous)
            sample['unix_s']+=.01;sample['monotonic_s']+=.01;sample['api']['ts']+=.01
            if fault=='birth':sample['actors']['2']['starttime_ticks']+=1
            if fault=='pid':sample['actors']['2']['pid']+=1
            if fault=='backward':
                sample['actors']['2']['command']=launch.expected_commands(case)['bash']
                sample['actors']['2']['executable']=case['launcher_contract']['stage_executables']['bash']
            if fault=='vanished':
                sample['actors'].pop('2');sample['round_admission']['pending'].insert(0,'2');sample['round_admission']['registering'].remove('2')
            self.attach(case,sample)
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):
                health.validate(case,sample,previous=previous)

    def test_exact5s_age_boundary_and_expired_or_forged_clocks(self):
        case,_,sample=self.fixture();actor=sample['actors']['2'];clock=sample['launcher_census']['clock']
        for age,accepted in ((5.,True),(5.0001,False)):
            witness=copy.deepcopy(clock);old=witness['boottime_s']
            witness['boottime_s']=actor['starttime_ticks']/witness['ticks_per_second']+age
            shift=witness['boottime_s']-old
            witness['monotonic_before_s']+=shift;witness['monotonic_after_s']+=shift
            if accepted:self.assertEqual(launch.check_child(case,actor,self.number,witness),'python')
            else:
                with self.assertRaises(ValueError):launch.check_child(case,actor,self.number,witness)
        for field,delta in (('ticks_per_second',1),('boottime_s',1),('monotonic_after_s',.002)):
            witness=copy.deepcopy(clock);witness[field]+=delta
            with self.subTest(field=field),self.assertRaises(ValueError):launch.check_child(case,actor,self.number,witness)

    def test_launcher_birth_before_original_round_refused(self):
        case,prior,sample=self.fixture();sample['actors']['2']['starttime_ticks']-=100
        self.attach(case,sample)
        with self.assertRaisesRegex(ValueError,'predates'):health.validate(case,sample,previous=prior)

    def test_incomplete192_barrier_registered_launcher_and_changed_source_refused(self):
        for fault in ('score191','retired191','registered','source','ordinary'):
            case,prior,sample=self.fixture();proof=sample['round_admission']
            if fault=='score191':proof['closed_chain'][0]['receipts'].pop('0')
            if fault=='retired191':
                row=json.loads(proof['closed_chain'][0]['summary']['raw']);row['retired']=191
                retained.rewrite(proof['closed_chain'][0]['summary'],row)
            if fault=='registered':
                sample['api']['client_rows'].append(dict(client_slot=2,client_id=9999,eval=case['slot_eval']['2'],connected_seconds=.01))
                sample['api']['client_count']+=1;proof['registering'].remove('2');retained.transport(sample)
            if fault=='source':case['launcher_contract']['source_sha256']=dict(launch.SOURCES,foreign='0'*64)
            if fault=='ordinary':sample.pop('round_admission')
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):health.validate(case,sample,previous=prior)

    def test_capture_failure_retains_exact_attempted_PID_and_partial_record(self):
        case,_,sample=self.fixture();actor=sample['actors']['2'];calls=[]
        def record(pid):
            calls.append(pid)
            if len(calls)==1:return copy.deepcopy(actor)
            raise FileNotFoundError('INJECTED confirmed child vanished')
        with patch.object(launch,'sample_clock',return_value=sample['launcher_census']['clock']),\
             patch.object(launch,'raw_identity',return_value=dict(pid=actor['pid'],stat=dict(error='INJECTED absent'))):
            with self.assertRaises(launch.CensusFailure)as found:
                launch.capture_children(case,case['owners']['fleet']['process'],record,[str(actor['pid'])],self.number)
        entry=found.exception.raw_snapshot['evidence']['children'][0]
        self.assertEqual(entry['pid'],actor['pid']);self.assertEqual(entry['record'],actor)
        self.assertIn('INJECTED',entry['error']);self.assertEqual(entry['raw_rejection_identity']['pid'],actor['pid'])

    def test_paired_capture_exec_race_refused_with_both_original_records(self):
        case,_,sample=self.fixture();actor=sample['actors']['2'];next_actor=copy.deepcopy(actor)
        next_actor['command']=launch.expected_commands(case)['bash'];next_actor['executable']=case['launcher_contract']['stage_executables']['bash']
        records=iter((copy.deepcopy(actor),next_actor))
        with patch.object(launch,'sample_clock',return_value=sample['launcher_census']['clock']),\
             patch.object(launch,'raw_identity',return_value=dict(pid=actor['pid'])),self.assertRaises(launch.CensusFailure)as found:
            launch.capture_children(case,case['owners']['fleet']['process'],lambda _:next(records),[str(actor['pid'])],self.number)
        self.assertIn('record',found.exception.raw_snapshot['evidence']['children'][0])

    def test_transport_failure_retains_already_collected_raw_sample(self):
        marker=dict(raw_API_wire='RAW',actors={})
        with patch.object(base,'collect',return_value=marker),patch.object(Path,'read_text',side_effect=FileNotFoundError('INJECTED TCP race')):
            with self.assertRaises(base.launchers().CensusFailure)as found:health.collect({})
        self.assertEqual(found.exception.raw_snapshot['evidence']['partial_main_snapshot'],marker)

    def test_worker_retains_collection_exception_and500ms_predicates_unchanged(self):
        tree=ast.parse((HERE/'round_observer_launcher_v1.py').read_bytes())
        raw=next(n.value for n in ast.walk(tree)if isinstance(n,ast.keyword)and n.arg=='raw_snapshot')
        error=launch.CensusFailure('INJECTED',dict(pid=123))
        self.assertEqual(eval(compile(ast.Expression(raw),'<actual worker raw_snapshot>','eval'),dict(sample=None,failure=error)),error.raw_snapshot)
        old=ast.parse((ROOT/'tools/post_recovery_evaluation/round_observer_v10.py').read_bytes())
        def gates(t):
            return [ast.dump(n,include_attributes=False)for n in ast.walk(t)if isinstance(n,ast.Call)
                and isinstance(n.func,ast.Name)and n.func.id=='require'and any(isinstance(a,ast.Constant)and isinstance(a.value,str)
                    and ('500ms'in a.value or 'deadline observer bounds'in a.value)for a in n.args)]
        self.assertEqual(gates(tree),gates(old))

    def test_TCP_and_score_receipt_and_admission_verifiers_unchanged(self):
        old=ast.parse((ROOT/'tools/post_recovery_evaluation/round_health_transport_v7.py').read_bytes())
        new=ast.parse((HERE/'round_health_transport_launcher_v1.py').read_bytes())
        names=('endpoint','tcp_rows','socket_inodes','validate_transport','validate')
        fn=lambda t,name:ast.dump(next(n for n in t.body if isinstance(n,ast.FunctionDef)and n.name==name),include_attributes=False)
        for name in names:self.assertEqual(fn(old,name),fn(new,name),name)
        self.assertEqual(fn(ast.parse((ROOT/'tools/post_recovery_evaluation/round_main_health_v7.py').read_bytes()),'completed_round'),
            fn(ast.parse((HERE/'round_main_health_launcher_v1.py').read_bytes()),'completed_round'))


if __name__=='__main__':unittest.main(verbosity=2)
