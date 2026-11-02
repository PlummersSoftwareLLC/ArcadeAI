"""UNEXECUTED stdlib fake metadata/lifecycle guards, never a live capacity test.

Only the new stdlib parent/member modules load during future root execution.
No evaluator, Torch, DQN, emulator, subprocess, unit, GPU or network is opened.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import signal
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def selected(name):
    manifest = json.loads((HERE / 'preparation-manifest.json').read_bytes())
    entry = manifest['files'][name]
    path = HERE / name
    raw = path.read_bytes()
    if entry['path'] != str(path) or hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise AssertionError('Selected source changed')
    spec = importlib.util.spec_from_file_location('_test_parallel_' + name.replace('.', '_'), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VirtualPath(PurePosixPath):
    files = set()
    def resolve(self):
        return self
    def exists(self):
        return str(self) in self.files


class Process:
    def __init__(self, pid, *, hang=False):
        self.pid, self.returncode, self.hang = pid, None, hang
        self.signals, self.waits = [], []
    def poll(self):
        return self.returncode
    def send_signal(self, value):
        self.signals.append(value)
    def wait(self, timeout):
        self.waits.append(timeout)
        if self.hang:
            raise subprocess.TimeoutExpired(['owned'], timeout)
        self.returncode = 0
        return 0


class JointMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P, cls.M = selected('joint_parent.py'), selected('joint_member.py')

    def setUp(self):
        self.unexpected = []
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(lambda: self.assertEqual(self.unexpected, []))
        def forbidden(*args, **kwargs):
            self.unexpected.append((args, kwargs))
            raise AssertionError('Unexpected host operation')
        for target, name in ((self.P.subprocess, 'run'), (self.P.subprocess, 'Popen'),
                             (self.P.urllib.request, 'urlopen'), (self.P.os, 'kill')):
            self.stack.enter_context(patch.object(target, name, side_effect=forbidden))
        self.stack.enter_context(patch.object(self.P, 'process_start', side_effect=forbidden))
        self.stack.enter_context(patch.object(self.P, 'process_cgroup', side_effect=forbidden))

    def fixture(self):
        P = self.P
        def fp(name):
            return dict(path='/closed/' + name, sha256='a' * 64, bytes=10,
                identity=dict(device=1, inode=len(name), bytes=10, mtime_ns=1,
                    ctime_ns=1, mode='0o444', uid=1, nlink=1))
        case = dict(schema='robotron-parallel-frozen-quality-case-v1', authorized=True,
            mode='aa_validation', experiment='future-AA-only', output_directory=str(P.GAME / 'logs/future-parallel-AA'),
            reference=fp('reference'), candidate=fp('reference'), python=fp('python'),
            parent_unit='robotron-parallel-quality-AA-original01.service', cpu_mask=[72, 73],
            ports=[9999, 10000, 10001, 10002], main_baseline=fp('baseline'),
            prior_disposition=fp('disposition'), capacity_review=fp('capacity'), aa_review=None,
            boot_assets=fp('manifest.json'), effective_guard_manifest=fp('guard'))
        baseline = dict(schema='robotron-current-main192-runtime-baseline-v1', status='PASS', observed_unix_s=999,
            actors=[dict(slot=i, pid=1000+i, starttime_ticks=123, mask=list(range(72))) for i in range(192)],
            inference_worker=dict(mask=list(range(72))))
        values = dict(baseline=baseline, disposition=dict(source_freeze_released=True),
            capacity=dict(schema='robotron-parallel-quality-root-capacity-review-v1', status='PASS',
                profile=copy.deepcopy(P.PROFILE), main_baseline=case['main_baseline'],
                prior_disposition=case['prior_disposition'], minimum_GPU0_free_bytes=32 << 30),
            reference={}, guard={}, **{'manifest.json': {}})
        def reader(pin):
            name = PurePosixPath(pin['path']).name
            if name not in values:
                self.unexpected.append(('unbound_metadata', name))
                raise AssertionError('Unbound metadata')
            return json.dumps(values[name], allow_nan=False).encode()
        return case, values, reader

    def test_default_PLAN_has_no_source_or_runtime_actions(self):
        with patch.object(self.P, 'pin', side_effect=AssertionError('Default read')), \
                patch.object(self.P, 'execute', side_effect=AssertionError('Default execute')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(self.P.main([]), 0)
            self.assertIn('PLAN_ONLY', output.getvalue())
        with patch.object(self.M, 'execute', side_effect=AssertionError('Member execute')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.M.main([]), 0)

    def test_AA_case_exact_namespace_freshness_and_RC_requires_closed_AA(self):
        case, values, reader = self.fixture()
        VirtualPath.files = set()
        with patch.object(self.P, 'Path', VirtualPath), patch.object(self.P.time, 'time', return_value=1000), \
                patch.object(self.P.sys, 'executable', '/closed/python'):
            baseline, capacity = self.P.validate_case(case, reader=reader)
            self.assertEqual(len(baseline['actors']), 192)
            self.assertEqual(capacity['profile'], self.P.PROFILE)
            for mutate in (lambda x:x['ports'].__setitem__(1, x['ports'][0]),
                           lambda x:x['ports'].__setitem__(1, 9998),
                           lambda x:x.update(cpu_mask=[1, 72]),
                           lambda x:x.update(candidate=dict(x['candidate'], sha256='b'*64)),
                           lambda x:x.update(authorized=False)):
                changed=copy.deepcopy(case);mutate(changed)
                with self.assertRaises(ValueError):self.P.validate_case(changed, reader=reader)
            values['disposition']['source_freeze_released']=False
            with self.assertRaises(ValueError):self.P.validate_case(case, reader=reader)
            values['disposition']['source_freeze_released']=True
            values['baseline']['observed_unix_s']=0
            with self.assertRaises(ValueError):self.P.validate_case(case, reader=reader)
            values['baseline']['observed_unix_s']=999
            rc=copy.deepcopy(case);rc['mode']='rc_confirmation';rc['aa_review']=copy.deepcopy(rc['capacity_review']);rc['aa_review']['path']='/closed/aa'
            values['aa']=dict(schema='robotron-parallel-quality-closed-AA-review-v1', status='PASS',
                profile=copy.deepcopy(self.P.PROFILE), all_four_valid=True, latency_capacity_accepted=True,
                qualification=False, promotion=False)
            self.P.validate_case(rc, reader=reader)
            for field in ('all_four_valid','latency_capacity_accepted'):
                values['aa'][field]=False
                with self.assertRaises(ValueError):self.P.validate_case(rc, reader=reader)
                values['aa'][field]=True
            values['aa']['promotion']=True
            with self.assertRaises(ValueError):self.P.validate_case(rc, reader=reader)

    def test_dedicated_carrier_and_same_description_fd_forwarding_are_required(self):
        P=self.P;cgroup='/user.slice/owned.service'
        fields=dict(P.CARRIER, MainPID='55', NRestarts='0', SubState='running', InvocationID='owned', ControlGroup=cgroup)
        P.carrier_contract(fields,55,cgroup)
        for key,value in (('KillMode','process'),('SendSIGKILL','no'),('RemainAfterExit','no'),
                          ('ControlGroup','/user.slice/foreign.service'),('MainPID','99'),('TimeoutStopUSec','infinity')):
            changed=dict(fields,**{key:value})
            with self.assertRaises(ValueError):P.carrier_contract(changed,55,cgroup)
        args=P.with_lease(dict(stdin=-3,close_fds=True,env={}),7)
        self.assertEqual(args['pass_fds'],(7,));self.assertTrue(args['close_fds'])
        for fd in (None,True,2,-1):
            with self.assertRaises(ValueError):P.with_lease({},fd)
        with self.assertRaises(ValueError):P.with_lease({'pass_fds':(99,)},7)
        class FDPath(PurePosixPath):
            text='lock:\t1: FLOCK ADVISORY WRITE 55 00:01:2 0 EOF\n'
            def read_text(self):return self.text
        info=SimpleNamespace(st_dev=1,st_ino=2,st_mode=0o100600,st_uid=3,st_nlink=1,
            st_size=0,st_mtime_ns=4,st_ctime_ns=5)
        expected=dict(device=1,inode=2,mode='0o600',uid=3,nlink=1)
        def fd_stat(path):
            self.assertEqual(str(path),'/proc/55/fd/7')
            return info
        with patch.object(P,'Path',FDPath),patch.object(P.os,'stat',side_effect=fd_stat):
            self.assertEqual(P.descriptor_retained(55,7,expected),expected)
            FDPath.text='pos:\t0\n'
            with self.assertRaises(ValueError):P.descriptor_retained(55,7,expected)
            FDPath.text='lock:\t1: FLOCK ADVISORY WRITE 55 00:01:2 0 EOF\n'
            with self.assertRaises(ValueError):P.descriptor_retained(55,7,dict(expected,inode=99))

    def test_stop_signals_only_original_handles_and_records_timeout_without_kill(self):
        processes=[Process(100+i,hang=(i==3)) for i in range(4)]
        records=[dict(index=i+1,process=x,owner=dict(pid=x.pid,starttime_ticks=10,cgroup='/owned')) for i,x in enumerate(processes)]
        with patch.object(self.P,'alive',return_value=True):
            errors=self.P.stop_members(records,timeout=5,clock=lambda:10)
        self.assertEqual(len(errors),1)
        self.assertTrue(all(x.signals==[signal.SIGINT] for x in processes))
        self.assertTrue(all(x.waits==[5] for x in processes))
        self.assertIsNone(processes[-1].returncode)
        foreign=Process(999,hang=True);record=dict(process=foreign,owner=dict(pid=999,starttime_ticks=10))
        with patch.object(self.P,'alive',return_value=False):
            errors=self.P.stop_members([record],timeout=1,clock=lambda:0)
        self.assertEqual(foreign.signals,[]);self.assertEqual(len(errors),2)

    def test_fixed_wait_never_retries_failed_member_or_rearms_deadline(self):
        process=Process(100);record=dict(index=1,process=process,owner=dict(pid=100,starttime_ticks=10),directory='/virtual/member')
        VirtualPath.files=set();calls=[]
        with patch.object(self.P,'Path',VirtualPath),patch.object(self.P,'alive',return_value=True):
            ticks=iter((0,1,2))
            with self.assertRaisesRegex(ValueError,'deadline'):
                self.P.wait_stage(record,'prepared','a'*64,2,[record],lambda:False,lambda:calls.append('health'),
                    clock=lambda:next(ticks),sleep=lambda _:None)
            self.assertEqual(calls,['health','health'])
            process.returncode=1
            with self.assertRaisesRegex(ValueError,'member exited'):
                self.P.wait_stage(record,'prepared','a'*64,2,[record],lambda:False,lambda:None,
                    clock=lambda:0,sleep=lambda _:self.fail('Must not retry'))

    def test_padding_and_commands_refuse_clock_replay_parent_or_boundary_drift(self):
        M=self.M;parent=dict(pid=10,starttime_ticks=20,cgroup='/owned');command=dict(case_sha256='a'*64,parent=parent)
        self.assertEqual(M.command_contract(command,'a'*64,parent,True),command)
        for value,alive in ((dict(command,case_sha256='b'*64),True),(dict(command,parent=dict(parent,pid=11)),True),(command,False)):
            with self.assertRaises(ValueError):M.command_contract(value,'a'*64,parent,alive)
        status=dict(complete=True,valid=True,cohort=dict(complete=True));clocks=dict(training_steps=10,optimized_samples=40960);replay={}
        self.assertTrue(M.padding_contract(status,clocks,clocks,replay,replay,True))
        for args in ((dict(status,valid=False),clocks,clocks,replay,replay,True),
                     (status,dict(clocks,training_steps=11),clocks,replay,replay,True),
                     (status,clocks,clocks,dict(size=1),replay,True),
                     (status,clocks,clocks,replay,replay,False)):
            with self.assertRaises(ValueError):M.padding_contract(*args)

    def scientific_fixture(self, *, aa=False):
        P=self.P;plan=dict(mode='aa_validation' if aa else 'rc_confirmation',profile=P.PROFILE,
            case=dict(path='/closed/case'),source_manifest=dict(path='/closed/manifest'),parent=dict(pid=1),legs=[])
        records=[];values={};fields=('port','actors','actor_slots','inference_backend')
        class Evaluator:
            @staticmethod
            def stable_effective_implementation(value):return value
        for index,(role,score) in enumerate(zip(P.ORDER,(100,200,100,90)),1):
            spec=dict(index=index,role=role);plan['legs'].append(spec)
            process=Process(100+index);process.returncode=0
            owner=dict(pid=process.pid,starttime_ticks=10)
            records.append(dict(process=process,owner=owner))
            rows=[dict(journal_game_id=f'{index}:{n}',client_slot=4096+n%16,score=100 if aa else score) for n in range(64)]
            parallel=dict(profile=P.PROFILE,case=plan['case'],manifest=plan['source_manifest'],parent=plan['parent'],
                member_owner=owner,held_through_joint_stop=True,unscored_padding_faults_validated=True,actor_closure_complete=True)
            receipt=dict(job=dict(port=10000+index,actors=16,actor_slots=list(range(4096,4112)),inference_backend='inductor'),
                numeric_policy=dict(fp32=True),runtime=dict(device='cuda'),source_hashes=dict(source='same'),protocol=dict(greedy=True),
                effective_implementation=dict(code='same'),boot_assets=dict(identity='same'),socket_wait=dict(sha256='same'),parallel_profile=parallel)
            values[index]=(receipt,dict(rows=rows,protocol=dict(greedy=True)),'a'*64)
        def load_leg(spec, bound):
            self.assertIs(bound,plan)
            return values[spec['index']]
        def summarize(leg):
            scores=sorted(row['score'] for row in leg['rows'])
            return dict(count=len(scores),mean=sum(scores)/len(scores),median=(scores[len(scores)//2-1]+scores[len(scores)//2])/2)
        campaign=SimpleNamespace(load_leg=load_leg,summarize=summarize,evaluator=Evaluator,JOB_FIELDS=fields)
        return plan,records,campaign,values

    def test_actual_gate_keeps_each_candidate_separate_and_AA_never_qualifies(self):
        plan,records,campaign,values=self.scientific_fixture()
        result=self.P.assess(plan,records,campaign,all_padding_valid=True)
        self.assertEqual(result['outcome'],'not_improved');self.assertFalse(result['qualified_improvement'])
        self.assertEqual([x['mean_pass'] for x in result['candidate_checks']],[True,False])
        self.assertEqual(result['pooled_reference']['count'],128)
        aa,records,campaign,values=self.scientific_fixture(aa=True)
        result=self.P.assess(aa,records,campaign,all_padding_valid=True)
        self.assertFalse(result['qualified_improvement']);self.assertFalse(result['promotion'])
        self.assertEqual(result['outcome'],'AA_VALIDATION_COMPLETE_NOT_QUALIFICATION')

    def test_no_gate_on_missing_games_duplicate_ID_padding_or_foreign_provenance(self):
        for mode in ('count','duplicate','padding','provenance','exit'):
            with self.subTest(mode=mode):
                plan,records,campaign,values=self.scientific_fixture()
                if mode=='count':values[4][1]['rows'][:]=values[4][1]['rows'][:49]
                elif mode=='duplicate':values[4][1]['rows'][0]['journal_game_id']='1:0'
                elif mode=='provenance':values[4][0]['parallel_profile']['actor_closure_complete']=False
                elif mode=='exit':records[3]['process'].returncode=1
                with self.assertRaises(ValueError):self.P.assess(plan,records,campaign,all_padding_valid=(mode!='padding'))


if __name__ == '__main__':
    unittest.main()
