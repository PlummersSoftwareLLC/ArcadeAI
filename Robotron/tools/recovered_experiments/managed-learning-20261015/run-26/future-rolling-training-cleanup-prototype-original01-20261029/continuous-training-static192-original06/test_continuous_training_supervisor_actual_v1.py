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
SOURCE_NAME='continuous_training_fleet_v3.py'
SOURCE_SHA='904b01f21fc1daf5268c56c64d13246c9cac0992bf6370c866f4f8b8fd382e03'


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
    p=HERE/SOURCE_NAME;raw=p.read_bytes()
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
    def test_actual_tail_preserves_partial_line_and_rejects_replacement_or_truncation(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);p=h.path
            p.write_bytes(b'{"old":true}\n');tail=h.ns['RawCompletionTail'](p)
            self.assertEqual(tail.poll(),[])
            with p.open('ab')as out:out.write(b'{"fresh":')
            self.assertEqual(tail.poll(),[]);self.assertTrue(tail.pending)
            with p.open('ab')as out:out.write(b'true}\n')
            self.assertEqual(tail.poll(),[({'fresh':True},b'{"fresh":true}\n')])
            p.write_bytes(b'')
            with self.assertRaises(ValueError):tail.poll()
            other=h.fleet.root/'replacement';other.write_bytes(b'{"fake":true}\n');os.replace(other,p)
            with self.assertRaises(ValueError):tail.poll()

    def test_actual_TRAIN_natural_games_keep_same_original_handle_binding_and_incarnation(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet;child=h.bind(40)
            binding=f.records[40]['connection_binding'];token=f.children[40]['token']
            first,one=h.natural(40,'SYNTHETIC-TRAIN-1',score=100)
            second,two=h.natural(40,'SYNTHETIC-TRAIN-2',score=0)
            f.journals()
            self.assertIs(f.children[40]['child'],child)
            self.assertEqual((f.records[40]['state'],f.records[40]['incarnation']),('active_train',1))
            self.assertEqual((f.records[40]['connection_binding'],f.children[40]['token']),(binding,token))
            self.assertIsNone(f.records[40]['natural_result']);self.assertIsNone(f.records[40]['closure'])
            self.assertEqual((f.completed_train,f.train_score_sum,f.completed_eval),(2,100,0))
            self.assertEqual((len(h.backend.created),child.terminations,child.kills,len(child.waits)),(1,0,0,0))
            for result,raw in ((first,one),(second,two)):
                saved=f.root/'events'/('journal-'+hashlib.sha256(raw).hexdigest()+'.jsonl')
                self.assertEqual(saved.read_bytes(),raw)
                self.assertEqual(json.loads(saved.read_bytes()),result)

    def test_actual_EVAL_exit_tail_race_and_positive_server_terminal_never_authorize_refill(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet;child=h.bind(0)
            result,raw=h.natural(0,'SYNTHETIC-EVAL-1',append=False)
            child.code=0
            # Original exit and server terminal are positive, but the local
            # ordinary journal tail has not yet supplied its durable row.
            self.assertFalse(f.close_original(0))
            self.assertIsNone(f.records[0]['closure'])
            self.assertIsNone(f.records[0]['natural_result'])
            h.append(raw[:len(raw)//2]);self.assertFalse(f.close_original(0))
            h.append(raw[len(raw)//2:]);self.assertTrue(f.close_original(0))
            self.assertEqual(f.records[0]['state'],'closed_eval')
            close=h.ns['read'](f.records[0]['closure'])['data']
            self.assertEqual(close['actual_exit'],0);self.assertFalse(close['restart_censored'])
            self.assertEqual(close['original_pid'],child.pid)
            self.assertTrue(close['original_wait_reaped']and close['original_birth_absent'])
            self.assertGreater(len(child.waits),0)
            with self.assertRaises(ValueError):f.spawn(0)
            self.assertEqual((len(h.backend.created),child.terminations,child.kills),(1,0,0))

    def test_actual_run_closes_exited_disconnected_original_before_operational_replacement(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet;old=[];replaced=[]
            def snapshot(value):
                if 40 in f.records and f.records[40]['state']=='active_train'and not old:
                    old.append(f.children[40]['child']);old[0].code=7
                if old and f.records[40]['incarnation']==2:
                    replaced.append(f.children[40]['child']);f.stopping=True
                if f.errors:f.stopping=True
            h.backend.on_snapshot=snapshot
            def on_popen(child):
                if child.slot==40 and child.inc==2:
                    assert old and old[0].waits and old[0].code==7
                    assert h.backend.cleanup_queries and f.reaped_history
                    assert f.records[40]['state']=='fault_cleanup'and f.records[40]['closure']is not None
            h.backend.on_popen=on_popen
            f.run()
            self.assertFalse(f.errors)
            self.assertEqual(len(replaced),1)
            self.assertIsNot(replaced[0],old[0])
            self.assertEqual((old[0].terminations,old[0].kills),(0,0))
            close=h.ns['read'](f.records[40]['prior_fault_closure'])['data']
            self.assertEqual(close['actual_exit'],7);self.assertTrue(close['restart_censored'])
            self.assertTrue(all(c.waits for c in h.backend.created))

    def test_actual_bounded_bootstrap_and_everbound192_barrier_require_exact_live_or_closed_partition(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet
            def snapshot(value):
                if f.barrier is not None:f.stopping=True
            h.backend.on_snapshot=snapshot
            f.run()
            self.assertFalse(f.errors);self.assertIsNotNone(f.barrier)
            self.assertEqual(f.initial_bound,set(range(192)))
            self.assertEqual(len(h.backend.created),192)
            barrier=h.ns['read'](f.barrier)
            self.assertEqual(barrier['data']['admission_basis'],'EVER_BOUND_ORIGINAL192_NOT_SIMULTANEOUS')
            self.assertEqual(barrier['data']['slots'],list(range(192)))
            self.assertEqual(len(barrier['data']['physical_connections']),192)
            before=next(data for kind,slot,inc,data,pin in h.events if kind=='original192-membership')
            self.assertEqual(len(before['original_slots']),192)
            # Actual loop publishes no more than8 before observing bindings.
            outstanding=0;peak=0
            for kind,slot,inc,data,pin in h.events:
                if kind=='original-child':outstanding+=1;peak=max(peak,outstanding)
                elif kind=='physical-connection':outstanding-=1
            self.assertLessEqual(peak,8)
            self.assertTrue(all(v['initial_admission']['complete']is False for v in h.snapshots[:-1]))
            self.assertLess(len((f.root/'status.json').read_bytes()),524289)
            self.assertTrue(all(c.waits for c in h.backend.created))
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet
            for slot in range(192):h.bind(slot)
            h.natural(0,'SYNTHETIC-EARLY-EVAL');h.backend.created[0].code=0
            self.assertTrue(f.close_original(0))
            connections=h.backend.get('/api/continuous_training_connections')['connections']
            partition=f.barrier_partition(connections)
            self.assertEqual(partition['closed_eval_slots'],[0])
            self.assertEqual(len(partition['live_slots']),191)
            # All192 were physically bound, while one original EVAL has
            # already normally closed. This never asserts simultaneous192.
            f.initial_bound.remove(191);self.assertIsNone(f.barrier_partition(connections));f.initial_bound.add(191)
            child=f.children[40]['child'];child.code=1
            self.assertIsNone(f.barrier_partition(connections));child.code=None
            for key,value in [('faults',1),('incarnation',2),('quarantine_reason','fault'),('connection_binding',None)]:
                before=f.records[40][key];f.records[40][key]=value
                with self.subTest(field=key):self.assertIsNone(f.barrier_partition(connections))
                f.records[40][key]=before
            wrong=copy.deepcopy(connections);wrong[0]['token']='UNKNOWN'
            self.assertIsNone(f.barrier_partition(wrong))
            wrong=copy.deepcopy(connections);wrong.append(dict(client_slot=999,token='UNKNOWN',eval_only=False))
            self.assertIsNone(f.barrier_partition(wrong))
            before=f.records[0]['closure'];body=h.ns['read'](before)
            body['data']['original_wait_reaped']=False
            f.records[0]['closure']=h.ns['exclusive'](f.root/'negative-closure.json',value=body)
            self.assertIsNone(f.barrier_partition(connections));f.records[0]['closure']=before
            f.records[0]['state']='retiring_eval'
            self.assertIsNone(f.barrier_partition(connections))
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet;h.backend.connections_enabled=False
            h.clock.on_sleep=lambda:setattr(f,'stopping',True)if f.errors else h._loop_budget()
            f.run()
            self.assertIsNone(f.barrier)
            self.assertTrue(any('5s bootstrap'in e for e in f.errors))
            self.assertLessEqual(len(h.backend.created),8)
            self.assertTrue(all(c.waits for c in h.backend.created))

    def test_actual_stuck_EVAL_is_retained_without_signal_until_owned_finally_and_birth_faults_reap(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet;noted=[];quarantined=[]
            def snapshot(value):
                if 0 in f.records and f.records[0]['state']=='active_eval'and not noted:
                    child=f.children[0]['child'];child.ignore_terminate=True;noted.append(child)
                    h.natural(0,'SYNTHETIC-STUCK-EVAL')
                if noted and f.records[0]['state']=='quarantined':
                    quarantined.append((f.children[0]['child']is noted[0],noted[0].terminations,noted[0].kills))
                    f.stopping=True
            h.backend.on_snapshot=snapshot;f.run()
            self.assertEqual(quarantined,[(True,0,0)])
            self.assertIsNone(f.records[0]['closure'])
            self.assertEqual(noted[0].terminations,1);self.assertEqual(noted[0].kills,1)
            terminal=next(data for kind,slot,inc,data,pin in h.events if kind=='owned-supervisor-terminal')
            self.assertTrue(terminal['all_original_children_reaped'])
            self.assertEqual(next(r['actual_exit']for r in terminal['children']if r['slot']==0),-9)
            self.assertTrue(all(c.waits for c in h.backend.created))
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);f=h.fleet;h.backend.fail_birth_slots.add(0)
            h.clock.on_sleep=lambda:setattr(f,'stopping',True)if f.errors else h._loop_budget()
            f.run()
            self.assertEqual(f.records[0]['state'],'quarantined')
            self.assertIn(0,f.children)  # Actual original handle survived failed observation.
            self.assertIsNone(f.records[0]['original_child']['birth'])
            self.assertTrue(all(c.waits for c in h.backend.created))


if __name__=='__main__':
    unittest.main()
