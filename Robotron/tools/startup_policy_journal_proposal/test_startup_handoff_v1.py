"""New CPU contract against the actual immutable profile06 GameJournal.

Policy readers, clocks and transport/ROM event chains are synthetic. These tests
do not load a neural model, run MAME, rerun old guards or admit quality results.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]
handoff=load('_new_startup_handoff',HERE/'startup_handoff_v1.py')
base=load('_unchanged_profile06_journal',
    GAME/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/game_journal.py')
ACTION=struct.pack('>bbBBBB',-1,-1,0,0,1,0x85)
ROM=bytes(0x19000)


class Clock:
    def __init__(self):
        self.wall=1_000_000_000_000
        self.mono=50_000_000_000
    def advance(self,nanoseconds):
        self.wall+=nanoseconds
        self.mono+=nanoseconds


def frame(**changes):
    values=dict(game_score=0,level_number=1,player_alive=False,num_lasers=2,lives=3,
                start_pressed=False,done=False)
    values.update(changes)
    return SimpleNamespace(**values)


class Fixture:
    def __init__(self,load_rom=True):
        self.temp=tempfile.TemporaryDirectory(prefix='robotron-new-startup-handoff-')
        self.clock=Clock()
        self.policy=dict(checkpoint_sha256='a'*64,policy_load_id='b'*64,
            measurement_active=True,measurement_generation=7,experiment='new-handoff-contract',
            training_enabled=False,replay_enabled=False,epsilon=0.0,expert_ratio=0.0,
            learner_frame_count=1741229950,training_steps=7128160,optimized_samples=27621148672)
        self.window=dict(open_unix_ns=999_000_000_000,close_unix_ns=1010_000_000_000,
                         generation=7,experiment='new-handoff-contract')
        self.context=dict(experiment='new-handoff-contract',measurement_active=True,
            measurement_generation=7,epsilon=0.0,expert_ratio=0.0,difficulty=5,
            learner_frames=1741229950,training_steps=7128160,optimized_samples=27621148672)
        self.cs=dict(client_slot=4096,game_uid=91,frames=109,eval_only=True)
        self.journal=base.GameJournal(self.temp.name,clock=lambda:self.clock.wall/1e9,
                                      completion_policy='confirmed_reset_reserves_v1')
        # Unknown boot attachments can contain unreliable wire-alive/counter
        # junk. It must remain excluded rather than being silently corrected.
        self.journal.observe(17,frame(game_score=100,level_number=88,player_alive=True,
            num_lasers=255,lives=255),self.cs,context=lambda:self.context)
        self.previous=copy.deepcopy(self.journal.active[17])
        self.authority=handoff.StartupHandoff(self.journal,client_id=17,slot=4096,
            session='1'*32,connection='2'*32,expected_rom_sha256=hashlib.sha256(ROM).hexdigest(),
            policy_reader=lambda:self.policy,admission_reader=lambda:self.window,
            wall_ns=lambda:self.clock.wall,monotonic_ns=lambda:self.clock.mono)
        if load_rom:
            self.authority.loaded_rom(ROM)
        self.sent=[]

    def evidence(self):
        authority=self.authority
        common=dict(session='1'*32,connection='2'*32,slot=4096,nonce=authority.nonce)
        application=dict(common,sequence=100,event=1000,response_hex=authority.response.hex(),
            start=1,coin=0,socket_ok=True,apply_ok=True,debug_bypass=False,
            held_start_before_response=False)
        gate=dict(common,sequence=102,event=1005,address=0x9840,instruction_pc=0x2715,
            instruction_hex='9740',dp=0x98,a=1,data=1,mask=255,bank_entry=1,
            last_start=1,last_apply_ok=True,last_socket_ok=True)
        setup=dict(common,sequence=103,event=1006,address=0x9859,instruction_pc=0x2751,
            instruction_hex='9759',dp=0x98,a=127,data=127,mask=255,bank_entry=1,
            last_start=0,last_apply_ok=True,last_socket_ok=True)
        initialized=dict(common,sequence=109,event=1010,score=0,wave=1,raw_reserves=2,
            player_count=1,current_player=1,player_alive=False,first_play_sequence=-1)
        origin=dict(client_id=17,client_slot=4096,frame_sequence=109,accepted=True,
                    accepted_frames=109,game_uid=91,raw_payload_sha256='c'*64)
        return dict(application=application,gate=gate,setup=setup,
                    initialization=initialized,origin_acceptance=origin)

    def authorize(self,send=None):
        return self.authority.authorize(100,ACTION,self.sent.append if send is None else send)

    def issue(self,evidence=None):
        self.authorize()
        self.chain=self.evidence() if evidence is None else evidence
        def receive():
            self.clock.advance(6_000_000)
            return self.chain
        return self.authority.issue(receive)

    def apply(self,permit,observed=None):
        return self.authority.handoff(permit,frame() if observed is None else observed,
                                      self.cs,lambda:self.context)

    def no_transition(self):
        assert self.journal.active[17]['journal_game_id']==self.previous['journal_game_id']
        assert self.journal.active[17]['known_start'] is False
        assert not self.journal.games_path.exists()
        assert not self.journal.measurement_starts_path.exists()

    def close(self):
        self.temp.cleanup()


class StartupJournalContract(unittest.TestCase):
    def fixture(self,**kwargs):
        value=Fixture(**kwargs)
        self.addCleanup(value.close)
        return value

    def test_unknown_boot_row_preserved_distinct_start_pending_no_terminal(self):
        f=self.fixture()
        permit=f.issue()
        # A caller mutating its original dictionary cannot change issued bytes.
        f.chain['initialization']['score']=999999
        result=f.apply(permit)
        new=f.journal.active[17]
        self.assertNotEqual(result['previous_journal_game_id'],result['journal_game_id'])
        self.assertEqual(new['game_uid'],91)
        self.assertTrue(new['known_start'])
        self.assertEqual(new['score'],0)
        self.assertEqual(new['max_level'],0)
        self.assertIsNone(new['first_play_level'])
        self.assertIsNone(new['terminal_confirmation'])
        self.assertEqual(new['observed_frames'],1)
        old=json.loads(f.journal.games_path.read_text())
        self.assertEqual(old['score'],100)
        self.assertEqual(old['max_level'],88)
        self.assertFalse(old['known_start'])
        self.assertFalse(old['complete'])
        self.assertFalse(old['eligible'])
        self.assertEqual(old['excluded_reason'],'startup_attachment')
        self.assertIsNone(old['terminal_confirmation'])
        self.assertNotIn('startup_certificate',old['start_context'])
        self.assertNotIn('startup_certificate',old['end_context'])
        starts=[json.loads(line)for line in f.journal.measurement_starts_path.read_text().splitlines()]
        self.assertEqual(len(starts),1)
        self.assertEqual(starts[0]['journal_game_id'],new['journal_game_id'])
        self.assertEqual(starts[0]['context']['startup_certificate']['policy']['checkpoint_sha256'],'a'*64)
        status=f.journal.cohort_status('new-handoff-contract',999,1010)
        self.assertEqual((status['started'],status['pending'],status['count'],status['abandoned']),(1,1,0,0))

    def test_future_play_and_disconnect_remain_incomplete_not_a_full_game(self):
        f=self.fixture();f.apply(f.issue())
        f.cs['frames']+=1
        f.journal.observe(17,frame(player_alive=True,game_score=400),f.cs,context=lambda:f.context)
        f.journal.disconnect(17,lambda:f.context)
        rows=[json.loads(line)for line in f.journal.games_path.read_text().splitlines()]
        self.assertEqual(len(rows),2)
        self.assertTrue(rows[1]['known_start'])
        self.assertEqual(rows[1]['first_play_level'],1)
        self.assertFalse(rows[1]['complete'])
        self.assertFalse(rows[1]['eligible'])
        self.assertIsNone(rows[1]['terminal_confirmation'])
        status=f.journal.cohort_status('new-handoff-contract',999,1010)
        self.assertEqual((status['count'],status['abandoned']),(0,1))

    def test_policy_or_generation_change_before_issue_rejected(self):
        for key,value in [('checkpoint_sha256','d'*64),('policy_load_id','d'*64),
                          ('measurement_generation',8),('learner_frame_count',1741229951)]:
            f=self.fixture();f.authorize();chain=f.evidence();f.policy[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                f.authority.issue(lambda:chain)
            f.no_transition()

    def test_stale_client_policy_context_or_window_before_handoff_rejected(self):
        variants=[('policy','policy_load_id','d'*64),('cs','frames',110),('cs','game_uid',92),
                  ('context','measurement_generation',8),('context','difficulty',6),
                  ('context','training_steps',0),('context','epsilon',0.1),
                  ('window','close_unix_ns',1011_000_000_000)]
        for target,key,value in variants:
            f=self.fixture();permit=f.issue();getattr(f,target)[key]=value
            with self.subTest(target=target,key=key),self.assertRaises(ValueError):
                f.apply(permit)
            f.no_transition()

    def test_duplicate_foreign_or_payload_changed_permit_cannot_reauthorize(self):
        f=self.fixture();permit=f.issue();f.apply(permit)
        before=f.journal.games_path.read_bytes(),f.journal.measurement_starts_path.read_bytes()
        with self.assertRaises(ValueError):f.apply(permit)
        self.assertEqual(before,(f.journal.games_path.read_bytes(),f.journal.measurement_starts_path.read_bytes()))
        f=self.fixture();permit=f.issue();clone=copy.copy(permit)
        with self.assertRaises(ValueError):f.apply(clone)
        f.no_transition()
        f=self.fixture();permit=f.issue();permit.payload=permit.payload.replace(b'"game_uid":91',b'"game_uid":92')
        with self.assertRaises(ValueError):f.apply(permit)
        f.no_transition()

    def test_fixed_cutoff_rollback_and_wall_monotonic_disagreement(self):
        f=self.fixture();f.clock.advance(10_000_000_000)
        with self.assertRaises(ValueError):f.authorize()
        self.assertFalse(f.sent);f.no_transition()
        for change in ['late','rollback','wall_jump']:
            f=self.fixture();f.authorize();chain=f.evidence()
            def receive():
                if change=='late':f.clock.advance(11_000_000_000)
                elif change=='rollback':f.clock.advance(-1_000_000_000)
                else:f.clock.wall+=1_000_000_000
                return chain
            with self.subTest(change=change),self.assertRaises(ValueError):
                f.authority.issue(receive)
            f.no_transition()
        f=self.fixture();permit=f.issue();f.clock.advance(11_000_000_000)
        with self.assertRaises(ValueError):f.apply(permit)
        f.no_transition()

    def test_distinct_gate_delayed_setup_and_initialization_before_play_required(self):
        cases=[('gate','instruction_pc',0x27a5),('gate','last_start',0),('gate','mask',0),
               ('setup','event',1004),('initialization','player_count',2),
               ('initialization','first_play_sequence',108),('initialization','score',1),
               ('application','response_hex','00'*48),('application','debug_bypass',True)]
        for name,key,value in cases:
            f=self.fixture();f.authorize();chain=f.evidence();chain[name][key]=value
            with self.subTest(name=name,key=key),self.assertRaises(ValueError):
                f.authority.issue(lambda:chain)
            f.no_transition()

    def test_failure_send_or_apply_is_final_no_local_authorization_retry(self):
        f=self.fixture()
        def disconnect(raw):raise BrokenPipeError('original transport lost')
        with self.assertRaises(BrokenPipeError):f.authorize(disconnect)
        with self.assertRaises(ValueError):f.authorize()
        f.no_transition()
        for key,value in [('apply_ok',False),('socket_ok',False),('held_start_before_response',True)]:
            f=self.fixture();f.authorize();chain=f.evidence();chain['application'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                f.authority.issue(lambda:chain)
            with self.assertRaises(ValueError):f.authorize()
            f.no_transition()

    def test_origin_must_accept_exact_current_frame_and_UID(self):
        f=self.fixture();f.authorize();chain=f.evidence();chain['origin_acceptance']['accepted']=False
        with self.assertRaises(ValueError):f.authority.issue(lambda:chain)
        f.no_transition()
        for key,value in [('accepted_frames',108),('game_uid',92)]:
            f=self.fixture();f.authorize();chain=f.evidence();chain['origin_acceptance'][key]=value
            permit=f.authority.issue(lambda:chain)
            with self.subTest(key=key),self.assertRaises(ValueError):f.apply(permit)
            f.no_transition()

    def test_wrong_ROM_zero_policy_or_nonfrozen_behavior_never_sends_START(self):
        f=self.fixture(load_rom=False)
        with self.assertRaises(ValueError):f.authority.loaded_rom(b'incomplete')
        with self.assertRaises(ValueError):f.authorize()
        self.assertFalse(f.sent)
        for key,value in [('checkpoint_sha256','0'*64),('training_enabled',True),
                          ('replay_enabled',True),('epsilon',0.1),('measurement_generation',True)]:
            f=self.fixture();f.policy[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):f.authorize()
            self.assertFalse(f.sent);f.no_transition()

    def test_journal_write_failure_preserved_and_permit_cannot_retry(self):
        f=self.fixture();permit=f.issue();original=f.journal._write
        def write(path,row):
            if path==f.journal.measurement_starts_path:raise OSError('original start append failed')
            return original(path,row)
        f.journal._write=write
        with self.assertRaises(OSError):f.apply(permit)
        old=json.loads(f.journal.games_path.read_text())
        self.assertFalse(old['complete']);self.assertFalse(old['eligible'])
        f.journal._write=original
        before=f.journal.games_path.read_bytes()
        with self.assertRaises(ValueError):f.apply(permit)
        self.assertEqual(f.journal.games_path.read_bytes(),before)
        self.assertFalse(f.journal.measurement_starts_path.exists())

    def test_legacy_journal_mode_and_fake_loaded_actor_rejected(self):
        with tempfile.TemporaryDirectory(prefix='robotron-legacy-no-handoff-')as directory:
            legacy=base.GameJournal(directory)
            with self.assertRaises(ValueError):
                handoff.StartupHandoff(legacy,client_id=17,slot=4096,session='1'*32,
                    connection='2'*32,expected_rom_sha256=hashlib.sha256(ROM).hexdigest(),
                    policy_reader=lambda:{},admission_reader=lambda:{})
            policy=Path(directory)/'fixture.pt';policy.write_bytes(b'not-a-model');policy.chmod(0o444)
            with self.assertRaises(ValueError):
                handoff.live_policy_reader(FakeActor(),None,None,None,checkpoint_path=policy,
                    checkpoint_sha256='a'*64,actor_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


class FakeActor:
    pass


if __name__=='__main__':
    unittest.main(verbosity=2)
