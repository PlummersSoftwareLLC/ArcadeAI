"""CPU integration: real immutable journal, synthetic policy/ROM/socket observations.
No model, MAME, GPU, host clock adjustment or source/process controls.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import struct
import sys
import unittest
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

authority=load('_deadline32_new_authority_test',HERE/'startup_handoff_deadline32_v1.py')
proxy=load('_deadline32_new_proxy_test',HERE/'full_startup_proxy_deadline32_v1.py')
audit=load('_deadline32_new_audit_test',HERE/'audit_startup_deadline32_clock_v2.py')
defs=load('_deadline32_old_fixture_definitions_only',G/'tools/startup_policy_journal_proposal/test_startup_handoff_v1.py')
bridge_defs=load('_deadline32_old_bridge_fixture_definitions_only',G/'tools/startup_policy_journal_proposal/test_full_tail_proxy_v4.py')

class Fixture(defs.Fixture):
    def __init__(self):
        super().__init__()
        self.logs=[];self.deadline=self.clock.mono+3_000_000_000
        self.authority=authority.StartupHandoff(self.journal,client_id=17,slot=4096,
            session='1'*32,connection='2'*32,expected_rom_sha256=hashlib.sha256(defs.ROM).hexdigest(),
            policy_reader=lambda:self.policy,admission_reader=lambda:self.window,
            wall_ns=lambda:self.clock.wall,monotonic_ns=lambda:self.clock.mono,
            clock_emit=self.logs.append,action_deadline_reader=lambda:self.deadline)
        self.authority.loaded_rom(defs.ROM)

class BridgeFixture(bridge_defs.Fixture):
    def __init__(self):
        saved=bridge_defs.bridge
        try:
            bridge_defs.bridge=proxy
            super().__init__()
        finally:bridge_defs.bridge=saved
    def step(self,**changes):
        self.proxy._arm_request_budget()
        return super().step(**changes)

class ClockIntegration(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f
    def bridge(self):
        f=BridgeFixture();self.addCleanup(f.close);return f
    def test_actual_journal_three_witnesses_preserved_without_completing_game(self):
        f=self.fixture();permit=f.issue();body=json.loads(permit.payload);handoff=f.apply(permit)
        self.assertEqual([r['phase']for r in f.logs if r['kind']=='deadline_host_clock_sample'],list(authority.clock_component().PHASES))
        self.assertEqual(body['host_clock_samples'],{p:f.authority.clock_samples[p]for p in ('before_authorization','after_accepted_frame')})
        start=json.loads(f.journal.measurement_starts_path.read_text())
        self.assertEqual(start['context']['startup_clock_handoff']['witness'],handoff['clock_handoff_sample'])
        self.assertIsNone(f.journal.active[17]['terminal_confirmation']);self.assertFalse(f.journal.active[17]['finished'])
        self.assertEqual(len(f.journal.games_path.read_text().splitlines()),1)
    def test_real_wall_step_at_issue_persists_both_clock_endpoints_before_fail(self):
        f=self.fixture();f.authorize();chain=f.evidence();f.clock.wall+=80_000_000
        with self.assertRaises(authority.clock_component().ClockCoherenceError):f.authority.issue(lambda:chain)
        row=f.logs[-1];self.assertEqual(row['kind'],'deadline_host_clock_failure')
        self.assertEqual(row['evidence']['maximum_possible_error_ns'],80_000_000)
        self.assertIn('lower',row['evidence']);self.assertIn('upper',row['evidence']);f.no_transition()
    def test_real_wall_step_at_third_sample_never_hands_off(self):
        f=self.fixture();permit=f.issue();f.clock.wall+=80_000_000
        with self.assertRaises(authority.clock_component().ClockCoherenceError):f.apply(permit)
        self.assertEqual(f.logs[-1]['phase'],'before_journal_handoff');f.no_transition()
        self.assertEqual(permit.state,'failed')
    def test_all_three_preempted_attempts_retained_before_failure(self):
        f=self.fixture()
        values=iter([50_000_000_000,50_002_000_000,50_002_000_000,50_004_000_000,50_004_000_000,50_006_000_000])
        f.authority.monotonic_ns=lambda:next(values)
        with self.assertRaises(authority.clock_component().ClockSamplingError):f.authorize()
        row=f.logs[-1];self.assertEqual(len(row['evidence']['attempts']),3)
        self.assertEqual(row['evidence']['failure_reason'],'attempt_limit_exhausted')
        self.assertFalse(f.sent);f.no_transition()
    def test_preempted_pair_resamples_and_stays_inside_same_action_deadline(self):
        f=self.fixture();base=f.clock.mono
        values=iter([base,base+500_000_000,base+500_000_000,base+500_000_000,base+500_000_000])
        f.authority.monotonic_ns=lambda:next(values)
        walls=iter([f.clock.wall,f.clock.wall+500_000_000]);f.authority.wall_ns=lambda:next(walls)
        f.authorize();w=f.logs[0]['witness']
        self.assertEqual(w['selected_index'],2);self.assertEqual(w['parent_deadline_mono_ns'],f.deadline)
        self.assertEqual(w['attempts'][0]['span_ns'],500_000_000)
    def test_proxy_fixed_budget_covers_send_receive_and_no_rearm(self):
        f=self.bridge();f.proxy._arm_request_budget();original=copy.deepcopy(f.proxy.request_budget)
        with self.assertRaisesRegex(ValueError,'Prior'):f.proxy._arm_request_budget()
        self.assertEqual(f.proxy.request_budget,original)
        f.fleet.advance(3_000_000_000)
        with self.assertRaisesRegex(ValueError,'expired'):f.proxy._send(f.peer,b'abc')
        self.assertFalse(f.peer.sent)
    def test_proxy_receive_enforces_deadline_after_blocked_operation(self):
        f=self.bridge();f.proxy._arm_request_budget()
        class Late:
            def settimeout(self,value):self.timeout=value
            def recv(self,count):f.fleet.advance(3_000_000_000);return b'X'
        late=Late()
        with self.assertRaisesRegex(ValueError,'expired'):f.proxy._recv(late,1)
        self.assertEqual(late.timeout,3.0)
    def test_actual_proxy_1200_prefix_and_independent_clock_replay(self):
        f=self.bridge();f.prefix()
        for i,row in enumerate(f.logs,1):row['proxy_event']=i
        handoff=next(r for r in f.logs if r['kind']=='actual_policy_journal_handoff')
        proof=audit.audit_clock_chain(f.logs,handoff['certificate'],handoff['result'])
        self.assertTrue(proof['all_three_witnesses_replayed'])
        self.assertEqual(proof['unchanged_tolerance_ns'],50_000_000)
        self.assertEqual(len([r for r in f.logs if r['kind']=='deadline_request_budget_begin']),1200)
        self.assertLess(len(f.logs),8192)
    def test_clock_auditor_rejects_deadline_witness_source_and_order_tampering(self):
        f=self.bridge();f.prefix()
        for i,row in enumerate(f.logs,1):row['proxy_event']=i
        handoff=next(r for r in f.logs if r['kind']=='actual_policy_journal_handoff')
        cases=('renew','uncertainty','order','source','missingthird')
        for damage in cases:
            rows=copy.deepcopy(f.logs);samples=[r for r in rows if r['kind']=='deadline_host_clock_sample']
            if damage=='renew':samples[2]['request_budget']['deadline_monotonic_ns']+=1
            elif damage=='uncertainty':samples[0]['witness']['selected']['uncertainty_ns']+=1
            elif damage=='order':samples[0]['proxy_event']=9999
            elif damage=='source':samples[0]['clock_component_sha256']='f'*64
            else:rows.remove(samples[2])
            with self.subTest(damage=damage),self.assertRaises((ValueError,StopIteration)):
                audit.audit_clock_chain(rows,handoff['certificate'],handoff['result'])
    def test_full_first_start_raw_prefix_all_original_joins_and_incomplete_game(self):
        f=self.bridge();f.prefix();f.step()
        f.fleet.journal.disconnect(96,lambda:f.fleet.context)
        out=Path(f.fleet.temp.name)/'audit-output';actorpath=out/'actors/4096/original-actor.json';actorpath.parent.mkdir(parents=True)
        job=dict(output=str(out),sessions={'4096':f.subject['session']},connections={'4096':f.subject['connection']},
            proxy_ports={'4096':23001},loaded_rom_sha256=hashlib.sha256(bridge_defs.defs.ROM).hexdigest(),
            startup_admission_duration_ns=f.fleet.window['close_unix_ns']-f.fleet.window['open_unix_ns'])
        actorpath.write_text(json.dumps(dict(f.subject,pid=99999999,starttime_ticks=123,
            proxy_port=23001,original_job={'sha256':'d'*64})))
        for i,row in enumerate(f.logs,1):row['proxy_event']=i
        wirepath=Path(f.fleet.temp.name)/'proxy.jsonl';wirepath.write_text(''.join(json.dumps(r)+'\n'for r in f.logs))
        f.path.chmod(0o444)
        def pin(path):
            path=Path(path);st=path.stat();raw=path.read_bytes()
            return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=dict(
                device=st.st_dev,inode=st.st_ino,bytes=st.st_size,mtime_ns=st.st_mtime_ns,ctime_ns=st.st_ctime_ns,
                mode=oct(st.st_mode&0o777),uid=st.st_uid,nlink=st.st_nlink))
        def read(item,as_json=True):
            raw=Path(item['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==item['sha256']
            return json.loads(raw)if as_json else raw
        entry=dict(actual_exit=0,frames=f.proxy.sequence,handoff=f.proxy.handoff,pid=99999999,birth=123,
            footer=json.loads(f.path.read_text().splitlines()[-1]),prefix_summary=f.proxy.prefix_summary,
            files={'producer.jsonl':pin(f.path),'proxy.jsonl':pin(wirepath)})
        starts={r['journal_game_id']:r for r in map(json.loads,f.fleet.journal.measurement_starts_path.read_text().splitlines())}
        games={r['journal_game_id']:r for r in map(json.loads,f.fleet.journal.games_path.read_text().splitlines())}
        result={'policy_before':f.fleet.policy,'_admission':f.fleet.window}
        audit.dependencies()
        proof=audit.audit_first_start_prefix(4096,entry,job,result,starts,games,read,pin,expected_job_sha256='d'*64)
        self.assertTrue(proof['clock_proof']['all_three_witnesses_replayed'])
        self.assertFalse(games[f.proxy.handoff['journal_game_id']]['complete'])
        self.assertTrue(proof['prefix_ledger']['raw_prefix_ledger_recomputed'])
        boundary=dict(score_sealed_monotonic_ns=100,begin_monotonic_ns=101,declared_monotonic_ns=103,after_flags_monotonic_ns=104)
        for actual_exit in (1,-15):
            changed=dict(entry,actual_exit=actual_exit,intentional_cleanup=boundary)
            actual=audit.audit_first_start_prefix(4096,changed,job,result,starts,games,read,pin,expected_job_sha256='d'*64)
            self.assertEqual(actual['actual_exit'],actual_exit)
        with self.assertRaisesRegex(ValueError,'cleanup bracket'):
            audit.audit_first_start_prefix(4096,dict(entry,actual_exit=-15),job,result,starts,games,read,pin,expected_job_sha256='d'*64)
    def test_retirement_requires_exact_positive_seal_bracket_and_never_hides_clock_fault(self):
        boundary=dict(score_sealed_monotonic_ns=100,begin_monotonic_ns=101,declared_monotonic_ns=103,after_flags_monotonic_ns=104)
        row=dict(kind='original_proxy_failure',sequence=1300,error="DeadlineRetired('Selected deadline snapshot sealed; retire original slot 4096')",
            intentional_cleanup_flag=True,observed_monotonic_ns=102,cleanup_begin_monotonic_ns=101,
            cleanup_declared_monotonic_ns=103,clock_error_evidence=None)
        audit.audit_proxy_disposition([row],dict(intentional_cleanup=boundary),slot=4096)
        for changes in ({'intentional_cleanup_flag':False},{'observed_monotonic_ns':100},
            {'clock_error_evidence':{'fault':1}},{'error':"ValueError('clock fault')"}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                audit.audit_proxy_disposition([dict(row,**changes)],dict(intentional_cleanup=boundary),slot=4096)
    def test_postprefix_budget_stays_enforced_without_dense_log_growth(self):
        f=self.bridge();f.prefix();before=len(f.logs)
        for seq in range(1201,1251):f.step()
        self.assertLess(len(f.logs)-before,5)
        self.assertEqual(f.proxy.sequence,1250);self.assertIsNone(f.proxy.request_budget)
        self.assertEqual(len(f.origin.sent),1250)

if __name__=='__main__':unittest.main(verbosity=2)
