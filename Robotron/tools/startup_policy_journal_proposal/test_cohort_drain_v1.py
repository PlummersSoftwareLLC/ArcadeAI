"""New all32 host-drain contract using the actual journal and controller.

Policy, ROM, accepted inputs and host clocks are synthetic. No old test methods,
MAME processes, neural models, live actors or quality campaigns are run.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]
PROFILE=GAME/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


drain=load('_original_host_drain_contract_v1',HERE/'cohort_drain_v1.py')
startup=load('_original_host_drain_startup_v2',HERE/'startup_handoff_v2.py')
journal_module=load('_original_host_drain_actual_journal',PROFILE/'game_journal.py')
controller_module=load('_original_host_drain_actual_controller',PROFILE/'managed_measurement.py')
SLOTS=list(range(4096,4128))
ACTION=struct.pack('>bbBBBB',-1,-1,0,0,1,0x85)
ROM=bytes(0x19000)


def frame(**changes):
    data=dict(game_score=0,level_number=1,player_alive=False,num_lasers=2,lives=3,start_pressed=False,done=False)
    data.update(changes)
    return SimpleNamespace(**data)


class SyntheticAgent:
    def __init__(self):
        self.training_enabled=False;self.behavior_locked=True;self._prefetch_paused=True
        self._training_lock=threading.RLock();self.memory=None
        self.training_steps=7128160;self.optimized_samples=27621148672
    def capture_inference_policy(self):return {'synthetic_frozen_weight':1}
    def install_inference_policy(self,value):assert value=={'synthetic_frozen_weight':1}
    def _pause_prefetch(self):self._prefetch_paused=True


class Fixture:
    def __init__(self):
        self.temp=tempfile.TemporaryDirectory(prefix='robotron-original-host-drain-v1-')
        self.wall=1_000_000_000_000;self.mono=50_000_000_000
        self.agent=SyntheticAgent()
        self.metrics=SimpleNamespace(lock=threading.Lock(),training_enabled=False,
            learner_frame_count=1741229950,total_training_steps=self.agent.training_steps,
            total_optimized_samples=self.agent.optimized_samples,measurement_active=False,
            measurement_generation=0,measurement_label='',ratchet_frozen=False)
        self.journal=journal_module.GameJournal(self.temp.name,clock=lambda:self.wall/1e9,
            completion_policy='confirmed_reset_reserves_v1')
        self.controller=controller_module.ManagedMeasurement(self.agent,self.metrics,self.journal,
            clock=lambda:self.wall/1e9,boundary_status=lambda generation:
                dict(ready=True,generation=generation,actor_slots=SLOTS))
        self.controller.enter('original-host-drain-contract-v1',cohort_s=90,timeout_s=300)
        self.controller.tick()
        self.policy=dict(checkpoint_sha256='a'*64,policy_load_id='b'*64,
            measurement_active=True,measurement_generation=1,experiment=self.controller.label,
            training_enabled=False,replay_enabled=False,epsilon=0.0,expert_ratio=0.0,
            learner_frame_count=1741229950,training_steps=self.agent.training_steps,
            optimized_samples=self.agent.optimized_samples)
        self.window=dict(open_unix_ns=int(self.controller.start_ts*1e9),
            close_unix_ns=int(self.controller.close_ts*1e9),generation=1,experiment=self.controller.label)
        self.context=dict(experiment=self.controller.label,measurement_active=True,measurement_generation=1,
            epsilon=0.0,expert_ratio=0.0,difficulty=5,learner_frames=1741229950,
            training_steps=self.agent.training_steps,optimized_samples=self.agent.optimized_samples)
        self.subjects=[dict(slot=s,session=f'{s:032x}',connection=f'{s+10000:032x}')for s in SLOTS]
        self.gate=drain.CohortDrain(self.journal,self.controller,subjects=self.subjects,
            policy_reader=lambda:self.policy,admission_reader=lambda:self.window,
            wall_ns=lambda:self.wall,monotonic_ns=lambda:self.mono)
        self.states={};self.bindings={}
        self.advance(1_000_000)
        for subject in self.subjects:self.certify(subject)

    def advance(self,ns):self.wall+=ns;self.mono+=ns

    def certify(self,subject):
        slot=subject['slot'];cid=slot-4000
        cs=dict(client_slot=slot,game_uid=slot+1,frames=109,eval_only=True)
        self.states[slot]=cs
        self.journal.observe(cid,frame(game_score=100,level_number=88,player_alive=True,
            num_lasers=255,lives=255),cs,context=lambda:self.context)
        issuer=startup.StartupHandoff(self.journal,client_id=cid,**subject,
            expected_rom_sha256=hashlib.sha256(ROM).hexdigest(),policy_reader=lambda:self.policy,
            admission_reader=lambda:self.window,wall_ns=lambda:self.wall,monotonic_ns=lambda:self.mono)
        issuer.loaded_rom(ROM);sent=[];issuer.authorize(100,ACTION,sent.append)
        common=dict(subject,nonce=issuer.nonce)
        application=dict(common,sequence=100,event=1000,response_hex=sent[0].hex(),
            start=1,coin=0,socket_ok=True,apply_ok=True,debug_bypass=False,held_start_before_response=False)
        gate=dict(common,sequence=102,event=1005,address=0x9840,instruction_pc=0x2715,
            instruction_hex='9740',dp=0x98,a=1,data=1,mask=255,bank_entry=1,
            last_start=1,last_apply_ok=True,last_socket_ok=True)
        setup=dict(common,sequence=103,event=1006,address=0x9859,instruction_pc=0x2751,
            instruction_hex='9759',dp=0x98,a=127,data=127,mask=255,bank_entry=1,
            last_start=0,last_apply_ok=True,last_socket_ok=True)
        initialized=dict(common,sequence=109,event=1010,score=0,wave=1,raw_reserves=2,
            player_count=1,current_player=1,player_alive=False,first_play_sequence=-1)
        origin=dict(client_id=cid,client_slot=slot,frame_sequence=109,accepted=True,
            accepted_frames=109,game_uid=cs['game_uid'],raw_payload_sha256='c'*64)
        self.advance(6_000_000)
        permit=issuer.issue(lambda:dict(application=application,gate=gate,setup=setup,
            initialization=initialized,origin_acceptance=origin))
        result=issuer.handoff(permit,frame(),cs,lambda:self.context)
        binding=dict(subject,client_id=cid,nonce=issuer.nonce,journal_game_id=result['journal_game_id'],
            certificate_identifier=result['certificate_identifier'])
        self.bindings[slot]=binding;self.gate.register_start(**binding)
        self.journal.observe(cid,frame(player_alive=True),cs,context=lambda:self.context)

    def complete_game(self,slot,score=None,next_wave=1):
        cid=slot-4000;cs=self.states[slot]
        score=(slot-4096)*100 if score is None else score
        self.journal.observe(cid,frame(game_score=score,player_alive=True,num_lasers=0),cs,
            context=lambda:self.context)
        self.journal.observe(cid,frame(game_score=score,done=True,num_lasers=0),cs,
            context=lambda:self.context)
        self.advance(100_000)
        if score>0:cs['game_uid']+=1
        self.journal.observe(cid,frame(start_pressed=True,num_lasers=2,level_number=next_wave),cs,
            new_game=score>0,context=lambda:self.context)

    def closed(self):
        self.advance(self.window['close_unix_ns']-self.wall+1_000_000)
        self.controller.tick()

    def complete_all(self):
        self.closed()
        for slot in SLOTS:self.complete_game(slot,next_wave=1 if slot==4096 else 7)
        self.controller.tick()

    def authorize(self,permit,slot=4096,**changes):
        data={k:v for k,v in self.bindings[slot].items()if k in ('slot','session','connection','nonce')}
        data['sequence']=1201;data.update(changes)
        return self.gate.authorize_slot(permit,**data)

    def close(self):self.temp.cleanup()


class OriginalHostDrainContract(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_open_and_all32_pending_after_close_never_authorize_stop(self):
        f=self.fixture()
        self.assertIsNone(f.gate.try_issue());self.assertIsNone(f.gate.frozen_ids)
        f.closed();self.assertIsNone(f.gate.try_issue())
        self.assertEqual(len(f.gate.frozen_ids),32)
        self.assertEqual(f.controller.status()['phase'],'draining')

    def test_real_all32_terminal_reset_joins_keep_zero_and_old_wave_then_single_stop_each(self):
        f=self.fixture();f.complete_all();permit=f.gate.try_issue()
        body=json.loads(permit.payload)
        self.assertEqual(body['count'],32);self.assertFalse(body['quality_qualified'])
        cohort=f.controller.status()['cohort']
        self.assertEqual(min(r['score']for r in cohort['rows']),0)
        self.assertEqual(cohort['rows'][1]['terminal_confirmation']['next_wave'],7)
        receipts=[f.authorize(permit,s)for s in SLOTS]
        self.assertEqual(len(permit.used_slots),32)
        self.assertTrue(all(r['consumed_before_send']for r in receipts))
        self.assertEqual(len({r['slot']for r in receipts}),32)
        with self.assertRaisesRegex(ValueError,'already consumed'):f.authorize(permit)

    def test_extra_admitted_high_score_tail_keeps_original33_denominator(self):
        f=self.fixture();f.complete_game(4096)
        cs=f.states[4096]
        f.journal.observe(96,frame(player_alive=True,game_score=9_000_000),cs,context=lambda:f.context)
        f.closed()
        for slot in SLOTS[1:]:f.complete_game(slot)
        f.controller.tick()
        self.assertIsNone(f.gate.try_issue());self.assertEqual(len(f.gate.frozen_ids),33)
        self.assertEqual(f.controller.status()['pending'],1)
        f.complete_game(4096,score=9_000_000);f.controller.tick()
        permit=f.gate.try_issue();self.assertEqual(json.loads(permit.payload)['count'],33)
        self.assertEqual(max(r['score']for r in f.controller.status()['rows']),9_000_000)

    def test_exact_close_boundary_start_is_retained_and_later_start_is_outside(self):
        f=self.fixture();f.advance(f.window['close_unix_ns']-f.wall)
        f.complete_game(4096)  # complete_game advances100us: arrange exact boundary below.
        # Its new game is already outside, so it is never substituted for an admitted game.
        f.controller.tick();self.assertIsNone(f.gate.try_issue())
        self.assertEqual(len(f.gate.frozen_ids),32)
        g=self.fixture();g.advance(g.window['close_unix_ns']-g.wall-100_000)
        g.complete_game(4096);g.controller.tick();self.assertIsNone(g.gate.try_issue())
        self.assertEqual(len(g.gate.frozen_ids),33)
        self.assertEqual(g.journal.active[96]['start_unix_s'],g.controller.close_ts)

    def test_late_tail_completion_waits_for_actual_controller_tick(self):
        f=self.fixture();f.closed()
        for slot in SLOTS:f.complete_game(slot)
        self.assertIsNone(f.gate.try_issue())
        self.assertFalse(f.controller.status()['complete'])
        f.controller.tick();self.assertIsNotNone(f.gate.try_issue())

    def test_abandonment_policy_window_and_clock_damage_fail_without_rescue(self):
        for failure in ('abandoned','policy','window','clock'):
            with self.subTest(failure=failure):
                f=self.fixture();f.closed()
                if failure=='abandoned':f.journal.disconnect(96,lambda:f.context)
                elif failure=='policy':f.policy['training_steps']+=1
                elif failure=='window':f.window['close_unix_ns']+=1
                else:f.wall+=51_000_000
                with self.assertRaises(ValueError):f.gate.try_issue()
                self.assertEqual(f.gate.state,'failed')
                with self.assertRaisesRegex(ValueError,'no rescue'):f.gate.try_issue()

    def test_foreign_copied_mutated_early_and_consumed_permits_cannot_send_stop(self):
        for failure in ('copy','payload','subject','sequence'):
            with self.subTest(failure=failure):
                f=self.fixture();f.complete_all();permit=f.gate.try_issue()
                if failure=='copy':permit=copy.copy(permit)
                elif failure=='payload':permit.payload+=b' '
                changes={'nonce':'f'*64}if failure=='subject'else {'sequence':1200}if failure=='sequence'else {}
                with self.assertRaises(ValueError):f.authorize(permit,**changes)
                self.assertEqual(f.gate.state,'failed')
                self.assertEqual(len(permit.used_slots),0)

    def test_terminal_join_and_closed_membership_changes_remain_failures(self):
        f=self.fixture();f.complete_all()
        row=f.controller.status()['rows'][0]
        f.journal.measurement_games[row['journal_game_id']]['result']['terminal_confirmation']['next_journal_game_id']='invented'
        with self.assertRaises(ValueError):f.gate.try_issue()
        g=self.fixture();g.closed();self.assertIsNone(g.gate.try_issue())
        # Explicit fixture corruption: backdate a new start after the denominator froze.
        cs=dict(client_slot=4096,game_uid=99999,eval_only=True)
        old_clock=g.journal.clock;g.journal.clock=lambda:g.controller.close_ts
        with g.journal.lock:g.journal._begin(123456,frame(),cs,lambda:g.context,True,'score_reset')
        g.journal.clock=old_clock
        with self.assertRaisesRegex(ValueError,'membership changed'):g.gate.try_issue()


if __name__=='__main__':unittest.main(verbosity=2)
