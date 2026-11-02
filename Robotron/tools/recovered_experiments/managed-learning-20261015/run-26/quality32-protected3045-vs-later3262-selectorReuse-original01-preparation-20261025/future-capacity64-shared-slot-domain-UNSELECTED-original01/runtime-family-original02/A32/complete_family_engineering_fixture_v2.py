"""Inactive quota64 engineering fixture factory, with synthetic policy/ROM/time.

Constructs actual pinned journal/startup/controller/drain objects only when the
future original CPU guards call fixture_type and instantiate its returned class.
No fixture, numerical model, actor, test or filesystem work runs on import.
"""
import copy
import hashlib
from pathlib import Path
import struct
import tempfile
import threading
from types import SimpleNamespace

SLOTS=list(range(4096,4128))
ACTION=struct.pack('>bbBBBB',-1,-1,0,0,1,0x85)
ROM=bytes(0x19000)


def fixture_type(modules):
    drain,startup,journal_module,view=(modules[k]for k in ('drain','startup','journal','view'))
    controller_module=SimpleNamespace(ManagedMeasurement=view.measurement_type(modules['measurement'].ManagedMeasurement))
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
            self.controller.enter('quota64-synthetic-engineering-only',cohort_s=21540,timeout_s=21600)
            self.policy=dict(checkpoint_sha256='a'*64,policy_load_id='b'*64,
                measurement_active=True,measurement_generation=1,experiment=self.controller.label,
                training_enabled=False,replay_enabled=False,epsilon=0.0,expert_ratio=0.0,
                learner_frame_count=1741229950,training_steps=self.agent.training_steps,
                optimized_samples=self.agent.optimized_samples)
            self.policy['cohort_selection']=copy.deepcopy(drain.COHORT_SELECTION)
            self.original_journal=self.journal
            server=SimpleNamespace(game_journal=self.journal)
            self.journal=view.install_view(server,self.controller,self.policy)
            self.controller.tick()
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
            unknown={r['client_slot']:r for r in self.journal.completed}
            self.certified={}
            for slot,binding in self.bindings.items():
                game=self.journal.measurement_games[binding['journal_game_id']]
                self.certified[slot]=dict(binding,previous_journal_game_id=unknown[slot]['journal_game_id'],
                                          game_uid=game['game_uid'])

        def advance(self,ns):self.wall+=ns;self.mono+=ns

        def certify(self,subject):
            slot=subject['slot'];cid=slot-4000
            cs=dict(client_slot=slot,game_uid=slot+1,frames=109,eval_only=True)
            self.states[slot]=cs
            self.journal.observe(cid,frame(game_score=100,level_number=88,player_alive=True,
                num_lasers=255,lives=255),cs,context=lambda:self.context)
            issuer=startup.StartupHandoff(self.original_journal,client_id=cid,**subject,
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
            f=self;cid=slot-4000;cs=f.states[slot]
            score=(slot-4096)*100 if score is None else score
            cs['frames']+=1
            f.journal.observe(cid,frame(game_score=score,player_alive=True,num_lasers=0),cs,
                              context=lambda:f.context)
            f.advance(100_000);cs['frames']+=1
            f.journal.observe(cid,frame(game_score=score,done=True,num_lasers=0,lives=1),cs,
                              context=lambda:f.context)
            previous=(score%100_000_000,1,False,True,False,1,cs['frames'])
            f.advance(100_000);cs['frames']+=1
            if score>0:cs['game_uid']+=1
            current=(0,next_wave,False,False,True,3,cs['frames'])
            boundary=(previous,current,score%100_000_000,1,False,cs['frames']-1,cs['frames'],True,score>0,'accept')
            f.journal.observe(cid,frame(start_pressed=True,num_lasers=2,level_number=next_wave),cs,
                new_game=score>0,context=lambda:f.context,boundary_inputs=boundary)

        def closed(self):
            self.advance(self.window['close_unix_ns']-self.wall+1_000_000)
            self.controller.tick()

        def complete_all(self):
            for _ in range(2):
                for slot in SLOTS:self.complete_game(slot,next_wave=1)
            self.controller.tick()

        def closed_payloads(self):
            self.controller.tick()
            cohort=copy.deepcopy(self.controller.status()['cohort'])
            for slot in SLOTS:self.journal.disconnect(slot-4000,lambda:self.context)
            payloads={name:(Path(self.temp.name)/name).read_bytes()for name in
                      ('games.jsonl','measurement_starts.jsonl','lives.jsonl')}
            return dict(payloads=payloads,cohort=cohort,policy=copy.deepcopy(self.policy),
                        window=copy.deepcopy(self.window),certified=copy.deepcopy(self.certified))

        def authorize(self,permit,slot=4096,**changes):
            data={k:v for k,v in self.bindings[slot].items()if k in ('slot','session','connection','nonce')}
            data['sequence']=1201;data.update(changes)
            return self.gate.authorize_slot(permit,**data)

        def close(self):self.temp.cleanup()
    return Fixture
