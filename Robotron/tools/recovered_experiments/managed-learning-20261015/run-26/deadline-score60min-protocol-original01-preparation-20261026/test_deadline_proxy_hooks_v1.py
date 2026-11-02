"""CPU hook integration with the REAL deadline recorder; no runtime/model I/O."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


hooks = load('_deadline_actual_hooks', 'deadline_proxy_hooks_v1.py')
core = load('_deadline_real_recorder', 'deadline_score_recorder_v2.py')


class StartupProxy:
    """Only the external origin exchange is simulated; hooks/recorder are real."""
    def __init__(self, server, slot):
        self.server, self.cid = server, slot
        self.subject = dict(slot=slot, session=f'{slot:032x}', connection=f'{slot+5000:032x}')
        self.sequence = 1200
        self.handoff = dict(journal_game_id=str(slot), certificate_identifier=f'{slot+10000:064x}')
        self.issuer = SimpleNamespace(nonce=f'{slot+20000:064x}')
        self.prefix_verified = threading.Event(); self.prefix_verified.set()
        self.error = None
        self.ledger = SimpleNamespace(summary=lambda: dict(sequence=self.sequence, accepted=self.state()['frames']))
        self.calls = 0

    def state(self):
        with self.server.client_lock:
            return dict(self.server.client_states[self.cid])

    def process(self, peer, origin, raw):
        self.calls += 1
        magic, sequence, size, meta = hooks.REQUEST.unpack_from(raw)
        score = struct.unpack_from('>I', raw, hooks.REQUEST.size + 19)[0]
        with self.server.client_lock:
            cs = self.server.client_states[self.cid]
            cs['frames'] += 1; cs['raw_score_prev'] = score
            cs['game_score'] = cs['score_offset'] + score
        with self.server.game_journal.lock:
            game = self.server.game_journal.measurement_games[str(self.cid)]
            game['score'] = cs['game_score']; game['playable_frames'] += 1
        self.sequence = sequence


def raw(sequence, score):
    header = struct.pack('>HddBIBBBIBBB',1890,0.0,0.0,0,score,1,0,0,20000,2,1,2)
    payload = header + bytes(1890*4) + bytes(4)
    return hooks.REQUEST.pack(b'RSG2',sequence,len(payload),2) + payload + b'{}'


class Tests(unittest.TestCase):
    def fixture(self):
        clock = SimpleNamespace(now=10)
        recorder = core.DeadlineScoreRecorder(clock_ns=lambda: clock.now)
        gate = hooks.DeadlineExchangeGate(clock_ns=lambda: clock.now)
        policy = dict(policy_sha256='a'*64, measurement_generation=7, experiment='deadline-original',
                      policy_clocks=dict(learner_frame_count=3000000000,training_steps=10,optimized_samples=40960))
        server = SimpleNamespace(client_lock=threading.Lock(),client_states={},game_journal=SimpleNamespace(lock=threading.Lock(),measurement_games={}))
        parked=[]
        klass = hooks.build_deadline_proxy(StartupProxy, expected_base_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            recorder=recorder,gate=gate,policy=policy,on_cutoff=lambda p,*a: parked.append(p.subject['slot']),clock_ns=lambda: clock.now)
        proxies={}
        for slot in hooks.SLOTS:
            server.client_states[slot]=dict(frames=1200,game_uid=slot,game_score=100000000,raw_score_prev=0,score_offset=100000000,
                measurement_generation=7,measurement_active=True,client_slot=slot,eval_only=True)
            server.game_journal.measurement_games[str(slot)]=dict(journal_game_id=str(slot),game_uid=slot,known_start=True,first_play_level=1,
                measurement_active=True,measurement_generation=7,mixed_experiment=False,mixed_measurement=False,score=100000000,
                playable_frames=1,finished=False,result=None,start={'experiment':'deadline-original'})
            proxies[slot]=klass(server,slot)
            proxies[slot].process(None,None,raw(1201,25))
        boundary=dict(ready=True,active=True,generation=7,requested_generation=7,clients=32,expected=32,acknowledged=32,
            actor_slots=list(hooks.SLOTS),pending_client_ids=[],replay_pending_client_ids=[])
        return clock,recorder,gate,policy,server,proxies,boundary,parked

    def test_real_recorder_is_called_before_actual_gate_leave(self):
        clock,r,g,p,s,proxies,b,parked=self.fixture()
        original=g.leave
        def checked(ticket):
            self.assertIn(ticket[0],g.inflight)
            self.assertEqual(r._last_packets[ticket[0]]['sequence'],proxies[ticket[0]].sequence)
            original(ticket)
        g.leave=checked
        proxies[4096].process(None,None,raw(1202,50))
        self.assertEqual(r._scores[4096]['score'],100000050)
        self.assertEqual(g.inflight,{})

    def test_postdeadline_request_is_not_forwarded_or_scored(self):
        clock,r,g,p,s,proxies,b,parked=self.fixture()
        anchor=hooks.arm_ready32(proxies,b,r,g,p)
        clock.now=anchor['deadline_monotonic_ns']
        previous=proxies[4096].calls
        proxies[4096].process(None,None,raw(1202,99999999))
        self.assertEqual(proxies[4096].calls,previous)
        self.assertEqual(r._scores[4096]['score'],100000025)
        self.assertEqual(parked,[4096])

    def test_gate_drain_precedes_real_score_seal(self):
        clock,r,g,p,s,proxies,b,parked=self.fixture()
        anchor=hooks.arm_ready32(proxies,b,r,g,p); deadline=anchor['deadline_monotonic_ns']
        clock.now=deadline-1
        for proxy in proxies.values(): proxy.process(None,None,raw(1202,100))
        ticket=g.enter(4096); clock.now=deadline+1
        done=threading.Event(); result={}
        def drain(): result['barrier']=g.close_and_drain();done.set()
        thread=threading.Thread(target=drain);thread.start()
        self.assertFalse(done.wait(.01));g.leave(ticket);thread.join(1)
        self.assertTrue(done.is_set())
        seal=r.seal(clock.now,barrier=result['barrier'])
        self.assertEqual((seal['n_scored'],seal['n_completed'],seal['n_censored']),(32,0,32))
        g.mark_sealed();g.declare_teardown(server_shutdown_is_set=True)
        with self.assertRaises(hooks.DeadlineRetired):g.retire_received_request(proxies[4096],None,None,b'')

    def test_process_return_at_deadline_is_credited_after_late_snapshot(self):
        for late_return in (False, True):
            with self.subTest(late_return=late_return):
                clock,r,g,p,s,proxies,b,parked=self.fixture()
                deadline=hooks.arm_ready32(proxies,b,r,g,p)['deadline_monotonic_ns']
                clock.now=deadline-2
                for proxy in proxies.values(): proxy.process(None,None,raw(1202,100))
                original_process=StartupProxy.process
                original_snapshot=hooks.selected_journal_snapshot
                def process(*args):
                    value=original_process(*args);clock.now=deadline+int(late_return);return value
                def snapshot(*args):
                    clock.now=deadline+2;return original_snapshot(*args)
                with patch.object(StartupProxy,'process',process),patch.object(hooks,'selected_journal_snapshot',snapshot):
                    proxies[4096].process(None,None,raw(1203,200))
                seal=r.seal(clock.now,barrier=g.close_and_drain())
                row=seal['rows'][0]
                self.assertEqual(row['score_at_deadline'],100000100 if late_return else 100000200)
                if not late_return:
                    witness=row['score_witness']['source_witness']
                    self.assertEqual(witness['process_return_monotonic_ns'],deadline)
                    self.assertGreaterEqual(witness['snapshot_begin_monotonic_ns'],deadline)
                    self.assertGreater(witness['snapshot_end_monotonic_ns'],deadline)
                self.assertEqual(g.inflight,{})

    def test_unknown_pending_exchange_and_early_teardown_are_rejected(self):
        clock,r,g,p,s,proxies,b,parked=self.fixture()
        anchor=hooks.arm_ready32(proxies,b,r,g,p);ticket=g.enter(4096)
        clock.now=anchor['deadline_monotonic_ns']+hooks.MAX_DRAIN_NS+1
        with self.assertRaises(ValueError):g.close_and_drain()
        with self.assertRaises(ValueError):g.mark_sealed()
        with self.assertRaises(ValueError):g.declare_teardown(server_shutdown_is_set=True)
        g.leave(ticket)

    def test_snapshot_requires_actual_slot_eval_generation_and_coherence(self):
        clock,r,g,p,s,proxies,b,parked=self.fixture();proxy=proxies[4096]
        for key,bad in [('client_slot',4097),('eval_only',False),('measurement_active',False),('measurement_generation',8)]:
            saved=s.client_states[4096][key];s.client_states[4096][key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):
                hooks.completed_exchange_sample(proxy,raw(1201,25),1200,proxy.deadline_member,p,
                    completed_exchange_ns=clock.now,clock_ns=lambda: clock.now)
            s.client_states[4096][key]=saved
        original=hooks.selected_journal_snapshot
        def changed(*args):
            value=original(*args);s.client_states[4096]['frames']+=1;return value
        with patch.object(hooks,'selected_journal_snapshot',side_effect=changed),self.assertRaises(ValueError):
            hooks.completed_exchange_sample(proxy,raw(1201,25),1200,proxy.deadline_member,p,
                completed_exchange_ns=clock.now,clock_ns=lambda: clock.now)

    def test_first_game_registry_never_issues_a_false_fulltail_permit(self):
        reg=hooks.FirstGameRegistration()
        event=dict(slot=4096,session='a'*32,connection='b'*32,nonce='c'*64,client_id=0,journal_game_id='selected:1',certificate_identifier='d'*64)
        reg.register_start(**event);self.assertIsNone(reg.permit)
        event['journal_game_id']='later:2'
        with self.assertRaises(ValueError):reg.register_start(**event)


if __name__ == '__main__': unittest.main()
