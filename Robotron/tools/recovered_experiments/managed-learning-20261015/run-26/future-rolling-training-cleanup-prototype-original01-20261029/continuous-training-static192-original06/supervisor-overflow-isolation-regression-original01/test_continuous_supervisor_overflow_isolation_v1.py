"""Prospective actual-method fixtures; source-only, Root alone executes later.

The selected supervisor methods/tail/immutable writers are compiled from a
fixed source. Every Popen, PID/birth, physical socket, policy/cleanup GET and
clock is synthetic. The actual loop runs on a bounded fake clock; no service,
actor, network, proc, model or current journal is imported/probed/controlled.
Actual constructor/root authority and real Linux/HTTP collectors are outside
this component scope. All files below live in temporary fixture directories.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest


HERE=Path(__file__).resolve().parent
SOURCE_ROOT=HERE.parent
SOURCE_NAME='continuous_training_fleet_v4.py'
SOURCE_SHA='bc2f11eafa974b693d767ca5291a69655b37e79cb5d47f0db03ee10135dc77d1'


class Clock:
    def __init__(self):
        self.now=1000.
        self.on_sleep=None
        self.sleeps=0
    def time(self):return 1793000000.+self.now
    def monotonic(self):return self.now
    def monotonic_ns(self):return int(self.now*1e9)
    def sleep(self,seconds):
        self.now+=seconds;self.sleeps+=1
        if self.on_sleep is not None:self.on_sleep()
        if self.sleeps>500:raise AssertionError('Synthetic loop budget exceeded')


class ControlledOS:
    environ={}
    def __getattr__(self,name):return getattr(os,name)


def actual_source(clock, backend):
    if not isinstance(SOURCE_SHA,str)or len(SOURCE_SHA)!=64:
        raise RuntimeError('Supervisor fixture source is not frozen')
    p=SOURCE_ROOT/SOURCE_NAME;raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA
    tree=ast.parse(raw)
    helpers={'require','pin','read','selected_bytes','exclusive','atomic_snapshot'}
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in helpers
        or isinstance(n,ast.ClassDef)and n.name in {'RawCompletionTail','ContinuousTrainingFleet'}
        or isinstance(n,ast.Assign)and all(isinstance(t,ast.Name)and t.id in {'MODE','ORIGINAL_FIELDS'}for t in n.targets)]
    ns=dict(hashlib=hashlib,json=json,os=ControlledOS(),Path=Path,stat=stat,
        time=clock,subprocess=SimpleNamespace(Popen=backend.popen,STDOUT=object()))
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),str(p),'exec'),ns)
    return ns


class Child:
    def __init__(self,pid,slot,inc,backend):
        self.pid,self.slot,self.inc=pid,slot,inc
        self.backend=backend;self.code=None
        self.waits=[];self.terminations=0;self.kills=0
        self.ignore_terminate=False
    def poll(self):return self.code
    def wait(self,timeout):
        self.waits.append(timeout)
        if self.code is None:raise AssertionError('Synthetic original still running')
        return self.code
    def terminate(self):
        self.terminations+=1
        if not self.ignore_terminate:self.code=-15
    def kill(self):self.kills+=1;self.code=-9


class Backend:
    def __init__(self,clock):
        self.clock=clock;self.h=None;self.created=[];self.spawn_times=[]
        self.on_popen=None;self.on_snapshot=None
        self.connections_enabled=True;self.cleanup_ready=True;self.cleanup_wrong_token=False
        self.birth_still_live=set();self.fail_birth_slots=set();self.cleanup_queries=[]
        self.policy_changes={};self.terminals={}
    def popen(self,argv,*,env,stdout,stderr):
        slot,inc=int(env['ROBOTRON_CLIENT_SLOT']),int(env['ROBOTRON_ACTOR_ROUND'])
        child=Child(4000+len(self.created),slot,inc,self)
        if self.on_popen is not None:self.on_popen(child)
        self.created.append(child);self.spawn_times.append((slot,inc,self.clock.now))
        self.clock.now+=.1  # Synthetic bounded work; no real waiting.
        return child
    def current(self,pid):return next(c for c in self.created if c.pid==pid)
    def birth(self,pid):
        child=self.current(pid)
        if child.slot in self.fail_birth_slots:raise FileNotFoundError('Synthetic unavailable birth')
        if child.code is not None and pid not in self.birth_still_live:raise FileNotFoundError('Synthetic reaped birth')
        return dict(birth=9000+pid,parent=self.h.fleet.owner['pid'])
    def cgroup(self,pid):return self.h.fleet.owner['cgroup']
    def actor(self,pid):
        child=self.current(pid);f=self.h.fleet
        return dict(pid=pid,birth=9000+pid,parent=f.owner['pid'],uid=os.getuid(),cgroup=f.owner['cgroup'],
            command=f.cfg['mame_argv'],exe=f.cfg['mame_argv'][0],
            environment=dict(f.cfg['actor_common_environment'],ROBOTRON_CLIENT_SLOT=str(child.slot),
                ROBOTRON_ACTOR_ROUND=str(child.inc),ROBOTRON_EVAL_MODE='1'if f.roles[str(child.slot)]else'2',
                ROBOTRON_RETIRE_AFTER_GAME='1'if f.roles[str(child.slot)]else'0',
                ROBOTRON_PREVIEW_CLIENT='1'if child.slot==0 else'0'))
    def tcp_binding(self,pid,endpoints):
        return dict(inode=pid+10000,local=endpoints['peer'],remote=endpoints['server'])
    def connection(self,child):
        return dict(client_slot=child.slot,client_id=child.pid,eval_only=self.h.fleet.roles[str(child.slot)],
            token='SYNTHETIC-%d-%d'%(child.slot,child.inc),connection_ns=child.pid*100,
            socket_endpoints=dict(peer=['127.0.0.1',20000+child.slot],server=['127.0.0.1',9998]))
    def policy(self):
        value=dict(schema='robotron-continuous-main-policy-v1',
            server_stamp=self.h.fleet.cfg['trainer']['server_stamp'],
            observed_monotonic_ns=self.clock.monotonic_ns(),observed_unix_s=self.clock.time(),
            continuous_training_mode=True,main_measurement_entry_disabled=True,
            measurement_active=False,ratchet_frozen=False,replay_admission_open=True,
            consumer_error=None,training_enabled=True,measurement_generation=0)
        value.update(self.policy_changes);return value
    def get(self,path,query=None):
        if path=='/api/continuous_training_policy':return self.policy()
        if path=='/api/continuous_training_connections':
            connections=[]if not self.connections_enabled else [self.connection(c)
                for c in self.created if c.code is None and self.h.fleet.children.get(c.slot,{}).get('child')is c]
            return dict(self.policy(),schema='robotron-continuous-active-connections-v1',connections=connections)
        if path=='/api/connection_cleanup_token':
            token=query['token'];self.cleanup_queries.append(token)
            child=next(c for c in self.created if self.connection(c)['token']==token)
            terminal=self.terminals.get(child.slot)
            return dict(client_slot=child.slot,eval_only=self.h.fleet.roles[str(child.slot)],
                token='WRONG'if self.cleanup_wrong_token else token,
                ready_for_external_join=self.cleanup_ready,
                terminal_receipt=None if terminal is None else terminal[0],
                terminal_line_sha256=None if terminal is None else hashlib.sha256(terminal[1]).hexdigest())
        raise AssertionError('Unexpected synthetic GET '+path)


class Harness:
    def __init__(self,directory):
        self.clock=Clock();self.backend=Backend(self.clock)
        self.ns=actual_source(self.clock,self.backend)
        f=self.ns['ContinuousTrainingFleet'].__new__(self.ns['ContinuousTrainingFleet'])
        self.fleet=f;self.backend.h=self
        f.root=Path(directory).resolve()
        (f.root/'events').mkdir();(f.root/'actors').mkdir()
        self.path=f.root/'games.jsonl'
        f.cfg=dict(trainer=dict(pid=1000,birth=8000,server_stamp=dict(pid=1000,birth=8000,source_sha256='a'*64)),
            source_authority=dict(SYNTHETIC_NOT_ACTUAL=True),rolemap=dict(SYNTHETIC_NOT_ACTUAL=True),
            launch_argv=['SYNTHETIC-ROLE-WRAPPER','robotron','-video','none'],
            mame_argv=['/usr/games/mame','robotron','-video','none'],
            parent_environment=dict(ROBOTRON_CONTINUOUS_TRAINING_MODE='1',ROBOTRON_SOCKET_ADDRESS='dell:9998'),
            actor_common_environment=dict(ROBOTRON_CONTINUOUS_TRAINING_MODE='1',
                ROBOTRON_SOCKET_ADDRESS='dell:9998',ROBOTRON_PREVIEW_FPS='30'),
            input_environment_keys=['ROBOTRON_CLIENT_SLOT','ROBOTRON_ACTOR_ROUND','ROBOTRON_EVAL_MODE',
                'ROBOTRON_PREVIEW_FPS','ROBOTRON_RETIRE_AFTER_GAME'],startup_s=5,fault_cleanup_s=10,max_faults=3)
        f.source=dict(SYNTHETIC_NOT_ACTUAL=True)
        f.owner=dict(pid=1001,birth=8001,unit='SYNTHETIC.service',invocation_id='2'*32,
            cgroup='/SYNTHETIC/fleet',source=f.source)
        f.epoch='1001:8001:'+('2'*32)
        f.roles={str(slot):slot<37 for slot in range(192)}
        f.physical=SimpleNamespace(birth=self.backend.birth,cgroup=self.backend.cgroup,
            actor=self.backend.actor,tcp_binding=self.backend.tcp_binding)
        f.owner_record=lambda:copy.deepcopy(f.owner)
        f.get=self.backend.get
        f.sequence=0;f.stopping=False;f.errors=[];f.children={};f.records={}
        f.error_occurrences=0;f.error_distinct_details=0;f.last_error_detail=None
        f.error_counts_by_scope={};f.error_counts_by_slot={};f.error_latest_digest={}
        f.completed_train=f.completed_eval=f.partial_games=f.train_score_sum=0
        f.seen_jids=set();f.initial_bound=set();f.barrier=None;f.policy_generation=None
        f.original_membership=None;f.original_slots={};f.reaped_history=[]
        f.tail=self.ns['RawCompletionTail'](self.path)
        self.events=[];self.snapshots=[];self.game_uids={};self.game_ends={}
        actual_event=f.event
        def event(kind,slot,inc,data):
            value=actual_event(kind,slot,inc,data)
            self.events.append((kind,slot,inc,copy.deepcopy(data),value))
            return value
        f.event=event
        actual_snapshot=f.snapshot
        def snapshot():
            actual_snapshot()
            value=json.loads((f.root/'status.json').read_bytes());self.snapshots.append(value)
            if self.backend.on_snapshot is not None:self.backend.on_snapshot(value)
        f.snapshot=snapshot
        self.clock.on_sleep=lambda:self._loop_budget()
    def _loop_budget(self):
        if self.clock.sleeps>=250:self.fleet.stopping=True
    def bind(self,slot):
        f=self.fleet
        if slot not in f.children:f.spawn(slot)
        connection=self.backend.connection(f.children[slot]['child'])
        assert f.bind(slot,[connection])
        return f.children[slot]['child']
    def natural(self,slot,jid,*,score=0,append=True):
        row=self.fleet.records[slot];binding=self.ns['read'](row['connection_binding'])['data']['connection']
        intent=self.ns['read'](row['spawn_intent']);self.clock.now+=2
        self.game_uids[slot]=self.game_uids.get(slot,0)+1
        start=max(intent['unix_s']+.01,self.game_ends.get(slot,0)+.01)
        result=dict(journal_game_id=jid,client_slot=slot,client_id=binding['client_id'],
            eval_only=row['eval_only'],score=score,game_uid=self.game_uids[slot],
            complete=True,eligible=True,known_start=True,boundary_reason='zero_score_restart'if score==0 else'score_reset',
            start_unix_s=start,end_unix_s=self.clock.time(),
            start_context=dict(measurement_generation=self.fleet.policy_generation,
                               measurement_active=False,ratchet_frozen=False))
        raw=(json.dumps(result,separators=(',',':'))+'\n').encode()
        self.game_ends[slot]=result['end_unix_s'];self.backend.terminals[slot]=(result,raw)
        if append:self.append(raw)
        return result,raw
    def append(self,raw):
        with self.path.open('ab')as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())


class Tests(unittest.TestCase):
    def test_actual_error_details_and_counts_stay_bounded_beyond_old_wire_limit(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet
            for slot in range(192):h.bind(slot)
            original={slot:item['child']for slot,item in f.children.items()}
            message='FULL-SYNTHETIC-'+('nonASCII-雪-'*300)
            failure=ValueError(message)
            # The unchanged actual writer rejects the old repeated-list shape.
            with self.assertRaisesRegex(ValueError,'512KiB'):
                h.ns['atomic_snapshot'](f.root/'old-unbounded-negative.json',dict(errors=[message]*12000))
            for _ in range(12000):f.record_error('slot',40,failure)
            first=f.last_error_detail
            self.assertEqual(f.error_summary()['occurrences'],12000)
            self.assertEqual(f.error_summary()['distinct_immutable_details'],1)
            self.assertEqual(len(list((f.root/'events').glob('error-detail-*.json'))),1)
            f.record_error('slot',41,ValueError('different-slot'))
            f.record_error('slot',40,failure)
            self.assertEqual(f.last_error_detail,first)  # repeat updates the true latest occurrence
            for number in range(64):f.record_error('journal',number,ValueError('distinct-'+str(number)),dict(SYNTHETIC=number))
            f.snapshot();raw=(f.root/'status.json').read_bytes();value=json.loads(raw)
            self.assertLessEqual(len(raw),524288)
            self.assertEqual(value['error_summary']['occurrences'],12066)
            self.assertEqual(value['error_summary']['distinct_immutable_details'],66)
            self.assertEqual(value['error_summary']['counts_by_scope'],dict(slot=12002,journal=64))
            self.assertEqual(value['error_summary']['counts_by_slot']['40'],12002)  # journal40 adds one
            self.assertLessEqual(len(value['errors']),32)
            self.assertTrue(all(len(m)<=256 and m.isascii()for m in value['errors']))
            self.assertLessEqual(len(f.error_latest_digest),5*193)
            detail=h.ns['read'](first)
            self.assertEqual(detail['detail']['message'],message)
            self.assertEqual(detail['detail']['error_type'],'ValueError')
            self.assertEqual(len(list((f.root/'events').glob('error-detail-*.json'))),66)
            for slot,child in original.items():
                self.assertIs(f.children[slot]['child'],child)
                self.assertEqual((child.terminations,child.kills,len(child.waits)),(0,0,0))

    def test_actual_same_batch_bad_TRAIN_CID_cannot_discard_later_normal_EVAL(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet;train=h.bind(40);evaluation=h.bind(0)
            binding=f.records[40]['connection_binding'];token=f.children[40]['token']
            bad,_=h.natural(40,'SYNTHETIC-TRAIN-RECONNECTED',score=100,append=False)
            bad['client_id']+=100000
            badraw=(json.dumps(bad,separators=(',',':'))+'\n').encode()
            result,goodraw=h.natural(0,'SYNTHETIC-EVAL-AFTER-TRAIN',score=0,append=False)
            h.append(badraw+goodraw)
            f.journals()
            self.assertEqual(f.completed_train,0)
            self.assertEqual(f.completed_eval,1)
            self.assertIsNotNone(f.records[0]['natural_result'])
            self.assertIs(f.children[40]['child'],train)
            self.assertEqual((f.records[40]['connection_binding'],f.children[40]['token']),(binding,token))
            self.assertEqual((train.terminations,train.kills,len(train.waits)),(0,0,0))
            self.assertEqual(f.error_summary()['counts_by_scope'],dict(journal=1))
            for raw in (badraw,goodraw):
                saved=f.root/'events'/('journal-'+hashlib.sha256(raw).hexdigest()+'.jsonl')
                self.assertEqual(saved.read_bytes(),raw)
            evaluation.code=0
            self.assertTrue(f.close_original(0))
            closed=h.ns['read'](f.records[0]['closure'])['data']
            self.assertEqual(closed['actual_exit'],0)
            self.assertTrue(closed['original_wait_reaped']and closed['original_birth_absent'])
            self.assertFalse(closed['restart_censored'])
            self.assertEqual(f.records[0]['state'],'closed_eval')
            self.assertEqual((len(h.backend.created),train.terminations,train.kills),(2,0,0))
            with self.assertRaises(ValueError):f.spawn(0)

    def test_actual_run_repeated_exit_deferral_preserves_live_TRAIN_until_explicit_stop(self):
        for long_error in (False,True):
            with self.subTest(long_error=long_error),tempfile.TemporaryDirectory()as directory:
                h=Harness(directory);f=h.fleet;train=h.bind(40);evaluation=h.bind(0)
                result,raw=h.natural(0,'SYNTHETIC-MISSING-TAIL',append=False)
                evaluation.code=0  # actual selected close_original must wait/reap this synthetic original
                f.record_error('observation',None,ValueError('SYNTHETIC admission already sealed'))
                actual_get=f.get;initial=[True]
                huge='NETWORK-SYNTHETIC-'+('雪'*2000)
                def get(path,query=None):
                    if path=='/api/continuous_training_connections'and initial[0]:
                        initial[0]=False;return dict(h.backend.policy(),connections=[])
                    if long_error and path=='/api/connection_cleanup_token':raise ValueError(huge)
                    return actual_get(path,query)
                f.get=get
                stopped=[]
                def snapshot(value):
                    self.assertLessEqual(len((f.root/'status.json').read_bytes()),524288)
                    if f.error_counts_by_scope.get('slot',0)>=20:
                        self.assertIs(f.children[40]['child'],train)
                        self.assertEqual((train.terminations,train.kills,len(train.waits)),(0,0,0))
                        self.assertIsNone(f.records[0]['natural_result'])
                        self.assertIsNone(f.records[0]['closure'])
                        self.assertTrue(evaluation.waits)
                        if long_error:
                            reason=f.records[0]['quarantine_reason']
                            self.assertTrue(reason.isascii());self.assertLessEqual(len(reason),256)
                            self.assertEqual(h.ns['read'](f.last_error_detail)['detail']['message'],huge)
                        stopped.append(True);f.stopping=True  # ONLY this explicit synthetic stop permits finally
                h.backend.on_snapshot=snapshot
                f.run()
                self.assertEqual(stopped,[True])
                self.assertEqual(len(h.backend.created),2)  # no refill or replacement
                self.assertEqual((train.terminations,train.kills),(1,0))
                self.assertEqual((evaluation.terminations,evaluation.kills),(0,0))
                terminal=next(data for kind,slot,inc,data,pin in h.events if kind=='owned-supervisor-terminal')
                self.assertTrue(terminal['all_original_children_reaped'])
                self.assertTrue(all(c.waits for c in h.backend.created))
                self.assertGreaterEqual(f.error_counts_by_scope['slot'],20)


if __name__=='__main__':unittest.main()
