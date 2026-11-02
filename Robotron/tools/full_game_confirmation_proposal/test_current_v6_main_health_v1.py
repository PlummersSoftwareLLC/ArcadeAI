"""CPU failure contracts using a sealed live probe as immutable fixture data.

Modified process/socket/retirement values are synthetic; these tests do not
observe physical actors or qualify a live native or scientific evaluator.
"""
import argparse
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CHECK=SUPERVISOR=H=FIXTURE=None


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


class HealthTests(unittest.TestCase):
    def case(self):return copy.deepcopy(FIXTURE)

    def verify(self,case):
        f,c,e,m,r,p,b,z,now=case
        return CHECK.validate_join(f,c,e,m,r,p,b,z,now=now,closed_connection_predicate=SUPERVISOR.closed_connection)

    def make_closed_eval(self,case):
        f,c,e,m,roles,p,b,closures,now=case
        slot=next(s for s in CHECK.SLOTS if roles[str(s)]);row=f['slots'][str(slot)];connection=b[slot]['data']['connection']
        row['state']='closed_eval';f['counts']['active_eval']-=1;f['counts']['closed_eval']+=1
        f['completed_eval_games']+=1
        c['connections']=[v for v in c['connections']if v['client_slot']!=slot];del p[slot]
        natural_pin=dict(path='/synthetic-natural.json',sha256='a'*64,bytes=1,identity={})
        closure_pin=dict(path='/synthetic-closure.json',sha256='b'*64,bytes=1,identity={})
        row['natural_result']=natural_pin;row['closure']=closure_pin
        result=dict(complete=True,eligible=True,known_start=True,client_slot=slot,client_id=connection['client_id'],eval_only=True)
        cleanup=dict(connection,schema='robotron-prospective-connection-cleanup-receipt-v2',
            server_stamp=e['trainer']['server_stamp'],observed_unix_s=now,cleanup_error=None,
            ready_for_external_join=True,replay_admission_open=True,terminal_receipt=result,terminal_line_sha256='c'*64)
        cleanup.update({key:True for key in SUPERVISOR.CLEANUP_FLAGS})
        common=dict(epoch=f['epoch'],slot=slot,supervisor=f['supervisor'],trainer=f['trainer'],source_authority=f['source_authority'])
        natural=dict(common,kind='natural-result',data=dict(result=result,natural_complete=True,raw_line={'sha256':'c'*64}))
        close=dict(common,kind='original-reaped-closure',data=dict(actual_exit=0,original_pid=row['original_pid'],
            original_birth=row['original_birth'],original_wait_reaped=True,original_birth_absent=True,
            natural_result=natural_pin,restart_censored=False,connection_cleanup=[cleanup]))
        closures[slot]=dict(closure=close,natural=natural,original_birth_absent=True)
        return slot

    def test_original192_live_fixture_joins(self):
        r=self.verify(self.case());self.assertEqual((r['live_originals'],r['natural_EVAL_closed']),(192,0))

    def test_missing_train_or_duplicate_connection_rejected(self):
        case=self.case();slot=next(s for s in CHECK.SLOTS if not case[4][str(s)])
        case[1]['connections']=[r for r in case[1]['connections']if r['client_slot']!=slot]
        with self.assertRaises(ValueError):self.verify(case)
        case=self.case();case[1]['connections'].append(copy.deepcopy(case[1]['connections'][0]))
        with self.assertRaises(ValueError):self.verify(case)

    def test_wrong_birth_parent_role_incarnation_and_fault_rejected(self):
        for damage in ('birth','parent','role','incarnation','fault'):
            with self.subTest(damage=damage):
                case=self.case()
                if damage=='birth':case[5][0]['actor']['birth']+=1
                elif damage=='parent':case[5][0]['actor']['parent']+=1
                elif damage=='role':case[0]['slots']['0']['eval_only']=not case[0]['slots']['0']['eval_only']
                elif damage=='incarnation':case[0]['slots']['0']['incarnation']=2
                else:case[0]['slots']['0']['faults']=1
                with self.assertRaises(ValueError):self.verify(case)

    def test_wrong_socket_environment_or_binding_source_rejected(self):
        for damage in ('TCP','environment','binding'):
            with self.subTest(damage=damage):
                case=self.case()
                if damage=='TCP':case[5][0]['TCP']['inode']+=1
                elif damage=='environment':case[5][0]['actor']['environment']['ROBOTRON_CLIENT_SLOT']='99'
                else:case[6][0]['epoch']='foreign'
                with self.assertRaises(ValueError):self.verify(case)

    def test_stale_or_wrong_Main_connection_stamp_rejected(self):
        case=self.case();case[1]['observed_unix_s']=case[8]-6
        with self.assertRaises(ValueError):self.verify(case)
        case=self.case();case[1]['server_stamp']['pid']+=1
        with self.assertRaises(ValueError):self.verify(case)

    def test_pending_reconnect_is_retained_but_never_a_qualified_census(self):
        case=self.case();f=case[0];f['slots']['0']['state']='reconnecting_train'
        f['counts']['active_train']-=1;f['counts']['reconnecting_train']+=1
        self.assertEqual(CHECK.validate_metadata(*case[:5],now=case[8]),[0])
        with self.assertRaises(ValueError):self.verify(case)

    def test_positive_natural_EVAL_closure_retains_original192_denominator(self):
        case=self.case();self.make_closed_eval(case);r=self.verify(case)
        self.assertEqual((r['live_originals'],r['natural_EVAL_closed']),(191,1))

    def test_retired_EVAL_nonzero_boolean_missing_receipt_or_live_birth_rejected(self):
        for damage in ('nonzero','boolean','missing_terminal','still_alive','unclosed_token','foreign_binding'):
            with self.subTest(damage=damage):
                case=self.case();slot=self.make_closed_eval(case);z=case[7][slot]
                if damage=='nonzero':z['closure']['data']['actual_exit']=1
                elif damage=='boolean':z['closure']['data']['actual_exit']=False
                elif damage=='missing_terminal':z['closure']['data']['connection_cleanup'][0]['terminal_receipt']=None
                elif damage=='still_alive':z['original_birth_absent']=False
                elif damage=='unclosed_token':z['closure']['data']['connection_cleanup'][0]['original_handler_stopped']=False
                else:case[6][slot]['epoch']='foreign'
                with self.assertRaises(ValueError):self.verify(case)

    def pending_guard(self,*,pending_age=0,gap_age=None):
        case=self.case();f,c,e,m,r,p,b,z,now=case
        f['slots']['0']['state']='reconnecting_train';f['counts']['active_train']-=1;f['counts']['reconnecting_train']+=1
        guard=CHECK.CurrentV6MainHealth.__new__(CHECK.CurrentV6MainHealth)
        guard.expected=e;guard.membership=m;guard.roles=r;guard.samples=[]
        guard.pending_since=100-pending_age;guard.previous_observed=None if gap_age is None else 100-gap_age
        guard.supervisor_process=lambda:{};guard.base=SimpleNamespace(observe=lambda:{})
        guard.status=lambda:copy.deepcopy(f);guard.get_connections=lambda:copy.deepcopy(c)
        guard.h=SimpleNamespace(put=lambda *a,**k:None);guard.output=Path('/no-write')
        return guard,now

    def test_overlap_cannot_extend_beyond_declared_ten_seconds(self):
        guard,now=self.pending_guard(pending_age=11);saved=CHECK.time
        CHECK.time=SimpleNamespace(monotonic=lambda:100,time=lambda:now)
        try:
            with self.assertRaisesRegex(ValueError,'within10s'):guard.observe()
        finally:CHECK.time=saved

    def test_observer_gap_cannot_extend_beyond_declared_fifteen_seconds(self):
        guard,now=self.pending_guard(gap_age=16);saved=CHECK.time
        CHECK.time=SimpleNamespace(monotonic=lambda:100,time=lambda:now)
        try:
            with self.assertRaisesRegex(ValueError,'15s'):guard.observe()
        finally:CHECK.time=saved


def main():
    global CHECK,SUPERVISOR,H,FIXTURE
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--source',type=Path);parser.add_argument('--fixture-job',type=Path);parser.add_argument('--physical-fixture',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    H=load('_v6_guard_CPU_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    CHECK=load('_v6_guard_CPU_source',args.source)
    job=json.loads(args.fixture_job.read_text());raw=json.loads(args.physical_fixture.read_text())
    expected=job['current_fleet'];SUPERVISOR=load('_v6_guard_CPU_original_cleanup',H.checked(expected['supervisor']['source']))
    membership=json.loads(H.checked(expected['original_membership']).read_text());roles=json.loads(H.checked(expected['rolemap']).read_text())['slot_eval']
    FIXTURE=(raw['fleet_before'],raw['connections_before'],expected,membership,roles,
        {int(k):v for k,v in raw['physical'].items()},{int(k):v for k,v in raw['bindings'].items()},
        {int(k):v for k,v in raw['closures'].items()},max(raw['fleet_before']['updated_unix_s'],raw['connections_before']['observed_unix_s']))
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HealthTests))
    assert 'torch'not in sys.modules
    report=H.put(args.output,dict(status='PASS'if r.wasSuccessful()else'FAIL',tests_run=r.testsRun,log=stream.getvalue(),
        errors=[dict(test=str(t),traceback=v)for t,v in r.errors],failures=[dict(test=str(t),traceback=v)for t,v in r.failures],
        source=H.pin(args.source),test_source=H.pin(Path(__file__)),fixture_job=H.pin(args.fixture_job),physical_fixture=H.pin(args.physical_fixture),
        immutable_original_cleanup_predicate=expected['supervisor']['source'],modified_fixture_values_are_synthetic=True,
        actual_MAME_GPU_native_or_scientific_qualification=False,promotion=False))
    print(json.dumps(dict(status='PASS'if r.wasSuccessful()else'FAIL',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),report=report)))
    return 0 if r.wasSuccessful()else 1


if __name__=='__main__':raise SystemExit(main())
