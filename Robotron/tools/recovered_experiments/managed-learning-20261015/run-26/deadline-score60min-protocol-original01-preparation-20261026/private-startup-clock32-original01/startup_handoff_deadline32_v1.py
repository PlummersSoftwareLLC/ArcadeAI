"""Prospective startup authority and journal handoff for an isolated adapter.

No work occurs on import. This module is not installed in the running server.
The selected adapter must join actual wire responses, input applications, raw
ROM observations and the origin server's accepted-frame ordinal. A dictionary
from a client is not, by itself, trusted evidence. Nonces provide a transport
join; this module does not provide cryptographic peer authentication.
"""
import copy
import importlib.util
import threading
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import secrets
import struct
import time

JOURNAL_SHA = '96864c78df67f46bc58b1c4af4ce1bceb3791a8842fdcf02871385a1013d1e0f'
RESPONSE = struct.Struct('>4sIBB32s6s')

CLOCK_COMPONENT=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_clock_cosampling_proposal_20261026/clock_cosampling_v1.py')
CLOCK_COMPONENT_SHA='4846a6c74e9d07fb4ebe9c31be9920b539179915940b679928b323703874cab1'
_CLOCK=None
_CLOCK_LOCK=threading.Lock()

def clock_component():
    global _CLOCK
    with _CLOCK_LOCK:
        if _CLOCK is None:
            raw=CLOCK_COMPONENT.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=CLOCK_COMPONENT_SHA:raise ValueError('Selected clock component changed')
            spec=importlib.util.spec_from_file_location('_deadline32_clock_cosampling',CLOCK_COMPONENT)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            if CLOCK_COMPONENT.read_bytes()!=raw:raise ValueError('Clock component changed during import')
            _CLOCK=module
        return _CLOCK


def require(value, message):
    if not value:
        raise ValueError(message)


def integer(value, name, minimum=0):
    require(type(value) is int and minimum <= value < 1 << 64, 'Invalid '+name)
    return value


def hex_string(value, length, name, *, nonzero=False):
    require(type(value) is str and re.fullmatch('[0-9a-f]{%d}' % length, value)
            and (not nonzero or value != '0'*length), 'Invalid '+name)
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def file_identity(path):
    s = Path(path).stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
            s.st_mode & 0o777, s.st_uid, s.st_nlink)


def live_policy_reader(actor, metrics, server, settings, *, checkpoint_path,
                       checkpoint_sha256, actor_source_sha256):
    """Build a source-bound reader of the actually loaded InferenceActor.

    Call only after acquisition and ManagedMeasurement.enter/install. File
    identity and model tensor versions are re-read at each endpoint. No model
    state is installed or changed. Source integrity and the original checkpoint
    digest must also be checked by the owning runtime at final disposition.
    """
    path = Path(checkpoint_path).resolve(strict=True)
    hex_string(checkpoint_sha256, 64, 'checkpoint', nonzero=True)
    source = Path(inspect.getsourcefile(type(actor)))
    require(type(actor).__name__ == 'InferenceActor'
            and hashlib.sha256(source.read_bytes()).hexdigest() == actor_source_sha256,
            'Actual selected inference actor source differs')
    before = file_identity(path)
    require(before[5] == 0o444 and before[7] == 1, 'Read-only acquired policy required')
    with path.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == checkpoint_sha256,
                'Acquired checkpoint bytes differ')
    require(file_identity(path) == before, 'Acquired policy changed during binding')

    def read():
        require(file_identity(path) == before and Path(actor.checkpoint_path) == path
                and actor.checkpoint_sha256 == checkpoint_sha256,
                'Loaded acquisition identity changed')
        require(actor.memory is None and actor.optimizer is None
                and server.replay_enabled is False and server.async_buffer is None
                and actor.training_enabled is False and actor.behavior_locked is True
                and actor._prefetch_paused is True and actor.inference_error is None
                and actor.infer_net.training is False,
                'Actual inference-only measurement isolation changed')
        require(settings.difficulty == 5 and settings.start_advanced is False
                and settings.start_level_min == 1
                and settings.epsilon_pct == settings.expert_pct == 0,
                'Greedy wave1/difficulty5 controls changed')
        versions = [(name, tuple(tensor.shape), str(tensor.dtype), tensor._version)
                    for name, tensor in actor.infer_net.state_dict().items()]
        load_id = hashlib.sha256(canonical(dict(pid=os.getpid(), checkpoint=checkpoint_sha256,
                         actor_source=actor_source_sha256, tensor_versions=versions))).hexdigest()
        require(int(metrics.total_training_steps) == actor.training_steps
                and int(metrics.total_optimized_samples) == actor.optimized_samples
                and int(metrics.learner_frame_count) == actor.learner_frame_count,
                'Actual loaded and measurement clocks differ')
        return dict(checkpoint_sha256=checkpoint_sha256, policy_load_id=load_id,
                    checkpoint_path=str(path), actor_source_sha256=actor_source_sha256,
                    numeric_policy=copy.deepcopy(actor.numeric_policy),
                    measurement_active=metrics.measurement_active,
                    measurement_generation=metrics.measurement_generation,
                    experiment=metrics.measurement_label, training_enabled=actor.training_enabled,
                    replay_enabled=server.replay_enabled, epsilon=0.0, expert_ratio=0.0,
                    learner_frame_count=actor.learner_frame_count, training_steps=actor.training_steps,
                    optimized_samples=actor.optimized_samples)
    return read


class _Permit:
    __slots__ = ('identifier', 'payload', 'state')

    def __init__(self, payload):
        self.payload = canonical(payload)
        self.identifier = hashlib.sha256(self.payload).hexdigest()
        self.state = 'issued'


class StartupHandoff:
    """One fresh session, one authorization, one prospective journal transition.

    All evidence inputs come from the selected live adapter. After an error this
    authority cannot authorize, issue or apply again. Existing unknown records
    are preserved as incomplete; no terminal, score reset or new ingest UID is
    invented. Other clients and ordinary completion logic are untouched.
    """
    def __init__(self, journal, *, client_id, slot, session, connection,
                 expected_rom_sha256, policy_reader, admission_reader,
                 wall_ns=time.time_ns, monotonic_ns=time.monotonic_ns,
                 clock_emit=None, action_deadline_reader=None):
        source = Path(inspect.getsourcefile(type(journal)))
        require(type(journal).__name__ == 'GameJournal'
                and hashlib.sha256(source.read_bytes()).hexdigest() == JOURNAL_SHA
                and journal.completion_policy == 'confirmed_reset_reserves_v1',
                'Exact confirmed-mode journal required')
        self.journal = journal
        self.cid = integer(client_id, 'client id')
        self.slot = integer(slot, 'slot', 4096)
        require(self.slot < 4128, 'Private slot outside32')
        self.session = hex_string(session, 32, 'session')
        self.connection = hex_string(connection, 32, 'connection')
        self.rom_sha = hex_string(expected_rom_sha256, 64, 'loaded ROM', nonzero=True)
        self.policy_reader, self.admission_reader = policy_reader, admission_reader
        self.wall_ns, self.monotonic_ns = wall_ns, monotonic_ns
        self.state = 'new'
        self.rom_loaded = False
        self.permits = {}
        require(callable(clock_emit) and callable(action_deadline_reader), 'Clock witness publisher and existing action-deadline reader required')
        self.clock_emit,self.action_deadline_reader=clock_emit,action_deadline_reader
        self.clock_samples={};self.clock_coherence={};self.last_clock_error=None

    def _clock_failure(self,error,phase,sequence):
        evidence=copy.deepcopy(getattr(error,'evidence',dict(error=repr(error),clock_samples=self.clock_samples)))
        self.last_clock_error=dict(phase=phase,error=repr(error),evidence=evidence)
        # Publish original uncertainty/clock endpoints BEFORE propagating failure.
        self.clock_emit(dict(kind='deadline_host_clock_failure',phase=phase,sequence=sequence,
            nonce=getattr(self,'nonce',None),error=repr(error),evidence=evidence,
            clock_component_sha256=CLOCK_COMPONENT_SHA))

    def _sample_clock(self,phase,sequence):
        clock=clock_component()
        try:
            deadline=self.action_deadline_reader()
            witness=clock.sample_pair(phase,deadline_mono_ns=deadline,
                wall_ns=self.wall_ns,monotonic_ns=self.monotonic_ns)
        except Exception as error:
            self._clock_failure(error,phase,sequence)
            raise
        self.clock_samples[phase]=copy.deepcopy(witness)
        self.clock_emit(dict(kind='deadline_host_clock_sample',phase=phase,sequence=sequence,
            nonce=self.nonce,witness=witness,clock_component_sha256=CLOCK_COMPONENT_SHA))
        return witness['selected']

    def _check_clock(self,phase,sequence):
        try:
            proof=clock_component().check_coherence(self.clock_samples['before_authorization'],self.clock_samples[phase])
        except Exception as error:
            self._clock_failure(error,phase,sequence)
            raise
        self.clock_coherence[phase]=copy.deepcopy(proof)
        self.clock_emit(dict(kind='deadline_host_clock_coherence',phase=phase,sequence=sequence,
            nonce=self.nonce,proof=proof,clock_component_sha256=CLOCK_COMPONENT_SHA))
        return proof

    def _subject(self):
        policy = copy.deepcopy(self.policy_reader())
        for key in ['checkpoint_sha256', 'policy_load_id']:
            hex_string(policy[key], 64, key, nonzero=True)
        require(policy['measurement_active'] is True
                and policy['training_enabled'] is policy['replay_enabled'] is False,
                'Live frozen-policy isolation differs')
        integer(policy['measurement_generation'], 'generation', 1)
        for key in ['learner_frame_count', 'training_steps', 'optimized_samples']:
            integer(policy[key], key)
        for key in ['epsilon', 'expert_ratio']:
            require(type(policy[key]) in (int, float) and policy[key] == 0,
                    'Live behavior is not greedy')
        require(type(policy['experiment']) is str and bool(policy['experiment'].strip()),
                'Live experiment label required')
        window = copy.deepcopy(self.admission_reader())
        require(set(window) == {'open_unix_ns', 'close_unix_ns', 'generation', 'experiment'},
                'Exact fixed admission binding required')
        integer(window['open_unix_ns'], 'admission open')
        integer(window['close_unix_ns'], 'admission close', window['open_unix_ns']+1)
        require(type(window['generation']) is int
                and window['generation'] == policy['measurement_generation']
                and window['experiment'] == policy['experiment'],
                'Window and live measurement differ')
        return policy, window

    def _inside(self, timestamp):
        integer(timestamp, 'host timestamp')
        require(self.window['open_unix_ns'] <= timestamp < self.window['close_unix_ns'],
                'Outside fixed admission')

    def loaded_rom(self, raw):
        try:
            require(self.state == 'new' and not self.rom_loaded,
                    'ROM witness already consumed or authority failed')
            require(type(raw) is bytes and len(raw) == 0x19000
                    and hashlib.sha256(raw).hexdigest() == self.rom_sha,
                    'Actual full loaded ROM witness differs')
            self.rom_loaded = True
        except Exception:
            self.state = 'failed'
            raise

    def authorize(self, sequence, action, send):
        try:
            require(self.state == 'new' and self.rom_loaded, 'Fresh full-ROM authority required')
            self.state = 'sending'
            self.sequence = integer(sequence, 'response sequence', 1)
            require(self.sequence <= 1200, 'First authorization must remain in the bounded startup prefix')
            require(type(action) is bytes and len(action) == 6, 'Actual v2 action required')
            move, fire, source, advanced, level, difficulty = struct.unpack('>bbBBBB',action)
            require(-1 <= move <= 7 and -1 <= fire <= 7 and source in (0,4)
                    and advanced == 0 and level == 1 and difficulty == 0x85,
                    'Actual response is not neutral/greedy forced-eval wave1/difficulty5')
            self.policy, self.window = self._subject()
            self.nonce = secrets.token_hex(32)
            self.response = RESPONSE.pack(b'RSP2', sequence, 1, 0, bytes.fromhex(self.nonce), action)
            lower = self._sample_clock('before_authorization',self.sequence)
            self.lower_mono = lower['midpoint_mono_ns']
            self.lower_wall = lower['wall_ns']
            self._inside(self.lower_wall)
            require(send(self.response) is None, 'Actual complete sendall required')
            require(integer(self.monotonic_ns(),'host monotonic clock') >= self.lower_mono,
                    'Host clock reversed')
            self.state = 'awaiting_evidence'
            return self.response
        except Exception:
            self.state = 'failed'
            raise

    def _identity(self, record):
        require(record['session'] == self.session and record['connection'] == self.connection
                and type(record['slot']) is int and record['slot'] == self.slot
                and record['nonce'] == self.nonce, 'Raw evidence session/nonce differs')
        integer(record['sequence'], 'raw sequence', 1)

    def issue(self, receive_evidence):
        try:
            require(self.state == 'awaiting_evidence', 'No unconsumed original authorization')
            self.state = 'receiving_evidence'
            evidence = copy.deepcopy(receive_evidence())
            upper = self._sample_clock('after_accepted_frame',evidence['origin_acceptance']['frame_sequence'])
            upper_wall = upper['wall_ns']
            upper_mono = upper['midpoint_mono_ns']
            self._inside(upper_wall)
            require(self.lower_wall <= upper_wall and self.lower_mono <= upper_mono,
                    'Host clock reversed')
            issue_clock_proof = self._check_clock('after_accepted_frame',evidence['origin_acceptance']['frame_sequence'])
            require(self._subject() == (self.policy, self.window),
                    'Live loaded policy, clocks or generation changed')
            require(set(evidence) == {'application', 'gate', 'setup', 'initialization', 'origin_acceptance'},
                    'Complete live chain required')
            application, gate, setup, initialized, origin = [evidence[k] for k in
                ['application', 'gate', 'setup', 'initialization', 'origin_acceptance']]
            for record in [application, gate, setup, initialized]:
                self._identity(record)
            require(application['sequence'] == self.sequence
                    and application['response_hex'] == self.response.hex()
                    and type(application['start']) is int and application['start'] == 1
                    and application['socket_ok'] is application['apply_ok'] is True
                    and application['debug_bypass'] is application['held_start_before_response'] is False,
                    'Original actual response/application join differs')
            for record, values in [(gate, dict(address=0x9840, instruction_pc=0x2715,
                    instruction_hex='9740', dp=0x98, a=1, data=1, mask=255, bank_entry=1)),
                    (setup, dict(address=0x9859, instruction_pc=0x2751,
                    instruction_hex='9759', dp=0x98, a=127, data=127, mask=255, bank_entry=1))]:
                require(all(type(record[k]) is type(v) and record[k] == v for k,v in values.items()),
                        'Distinct accepted gate or delayed setup witness differs')
                require(record['last_apply_ok'] is record['last_socket_ok'] is True,
                        'ROM witness has failed input transport')
            require(type(gate['last_start']) is int and gate['last_start'] == 1
                    and self.sequence <= gate['sequence'] < self.sequence+3,
                    'Accepted player-count gate lacks authorized held START')
            require(type(setup['last_start']) is int and setup['last_start'] in (0,1),
                    'Invalid later setup input state')
            for record in [application, gate, setup, initialized]:
                integer(record['event'], 'producer event', 1)
            require(application['event'] < gate['event'] < setup['event'] < initialized['event']
                    and gate['sequence'] <= setup['sequence'] < initialized['sequence'],
                    'Actual application/gate/setup/initialization order differs')
            require(all(type(initialized[k]) is type(v) and initialized[k] == v for k,v in
                    dict(score=0,wave=1,raw_reserves=2,player_count=1,current_player=1,
                         player_alive=False,first_play_sequence=-1).items()),
                    'One-player initialization before play required')
            require(type(origin['client_id']) is int and origin['client_id'] == self.cid
                    and type(origin['client_slot']) is int and origin['client_slot'] == self.slot
                    and type(origin['frame_sequence']) is int
                    and origin['frame_sequence'] == initialized['sequence']
                    and origin['accepted'] is True, 'Actual origin acceptance differs')
            integer(origin['accepted_frames'], 'origin accepted ordinal', 1)
            integer(origin['game_uid'], 'origin game UID', 1)
            hex_string(origin['raw_payload_sha256'], 64, 'accepted raw frame', nonzero=True)
            payload = dict(schema='robotron-prospective-startup-journal-certificate-v2',
                session=self.session,connection=self.connection,slot=self.slot,nonce=self.nonce,
                policy=self.policy,admission=self.window,loaded_rom_sha256=self.rom_sha,
                lower_before_send_unix_ns=self.lower_wall,upper_after_receive_unix_ns=upper_wall,
                lower_monotonic_ns=self.lower_mono,upper_monotonic_ns=upper_mono,evidence=evidence,
                host_clock_scheme='bounded-host-clock-cosample-v1',host_clock_component_sha256=CLOCK_COMPONENT_SHA,
                host_clock_samples=copy.deepcopy(self.clock_samples),host_clock_coherence=issue_clock_proof)
            permit = _Permit(payload)
            self.permits[permit.identifier] = permit
            self.state = 'issued'
            return permit
        except Exception:
            self.state = 'failed'
            raise

    def handoff(self, permit, frame, cs, context):
        try:
            require(self.state == 'issued' and isinstance(permit,_Permit)
                    and self.permits.get(permit.identifier) is permit and permit.state == 'issued',
                    'Only this live unconsumed permit can hand off')
            require(hashlib.sha256(permit.payload).hexdigest() == permit.identifier,
                    'Issued immutable payload changed')
            # Consume before any I/O: an append failure never authorizes a retry.
            permit.state = 'consuming'
            self.state = 'consuming'
            payload = json.loads(permit.payload)
            require(self._subject() == (self.policy,self.window), 'Live policy or generation changed')
            handoff_clock = self._sample_clock('before_journal_handoff',payload['evidence']['origin_acceptance']['frame_sequence'])
            now_wall = handoff_clock['wall_ns']
            now_mono = handoff_clock['midpoint_mono_ns']
            self._inside(now_wall)
            require(now_wall >= payload['upper_after_receive_unix_ns']
                    and now_mono >= payload['upper_monotonic_ns']
                    and handoff_clock['mono_before_ns'] >= self.clock_samples['after_accepted_frame']['selected']['mono_after_ns'],
                    'Host clock changed after issuance')
            handoff_clock_proof = self._check_clock('before_journal_handoff',payload['evidence']['origin_acceptance']['frame_sequence'])
            ctx = copy.deepcopy(context())
            require(ctx.get('measurement_active') is True
                    and type(ctx.get('measurement_generation')) is int
                    and ctx['measurement_generation'] == self.policy['measurement_generation']
                    and ctx.get('experiment') == self.policy['experiment']
                    and type(ctx.get('epsilon')) in (int,float) and ctx['epsilon'] == 0
                    and type(ctx.get('expert_ratio')) in (int,float) and ctx['expert_ratio'] == 0
                    and type(ctx.get('difficulty')) is int and ctx['difficulty'] == 5
                    and all(type(ctx.get(name)) is int and ctx[name] == self.policy[policy_name]
                            for name,policy_name in [('learner_frames','learner_frame_count'),
                                ('training_steps','training_steps'),('optimized_samples','optimized_samples')]),
                    'Actual journal measurement context differs')
            origin = payload['evidence']['origin_acceptance']
            require(type(cs.get('frames')) is int and cs['frames'] == origin['accepted_frames']
                    and type(cs.get('game_uid')) is int and cs['game_uid'] == origin['game_uid']
                    and type(cs.get('client_slot')) is int and cs['client_slot'] == self.slot
                    and cs.get('eval_only') is True, 'Live accepted client state advanced or changed')
            require(type(frame.game_score) is int and frame.game_score == 0
                    and type(frame.level_number) is int and frame.level_number == 1
                    and type(frame.player_alive) in (bool,int) and frame.player_alive == 0
                    and type(frame.num_lasers) is int
                    and frame.num_lasers == 2 and type(frame.lives) is int and 0 < frame.lives < 255,
                    'Actual accepted initialization frame differs')
            # Capture the old context before adding the new start certificate.
            original_context = copy.deepcopy(ctx)
            old_context = lambda: copy.deepcopy(original_context)
            ctx['startup_certificate'] = dict(identifier=permit.identifier,**payload)
            ctx['startup_clock_handoff'] = dict(certificate_identifier=permit.identifier,
                witness=copy.deepcopy(self.clock_samples['before_journal_handoff']),coherence=handoff_clock_proof)
            stable_context = lambda: copy.deepcopy(ctx)
            with self.journal.lock:
                previous = self.journal.active.get(self.cid)
                require(previous is not None and previous['known_start'] is False
                        and previous['start_reason'] == 'initial_attachment'
                        and previous['finished'] is False and previous['game_uid'] == cs['game_uid'],
                        'Only the original unknown attachment may hand off')
                require(previous['measurement_active'] is True
                        and previous['measurement_generation'] == self.policy['measurement_generation']
                        and previous['start'].get('experiment') == self.policy['experiment']
                        and not previous['mixed_measurement'] and not previous['mixed_experiment'],
                        'Original attachment measurement differs')
                journal_now = self.journal.clock()
                require(type(journal_now) in (int,float) and math.isfinite(journal_now),
                        'Invalid journal clock')
                self._inside(int(journal_now*1_000_000_000))
                old_identifier = previous['journal_game_id']
                # Boot-time wire-alive/score junk remains in the excluded row.
                self.journal._finish(previous, old_context, 'startup_certificate_handoff', False)
                game = self.journal._begin(self.cid, frame, cs, stable_context, True,
                                           'prospective_certified_first_start_v2')
                self._inside(int(game['start_unix_s']*1_000_000_000))
            # The selected proxy holds the next action until this returns, so
            # the origin cannot accept the next frame during this transition.
            self.journal.observe(self.cid,frame,cs,context=stable_context)
            require(self.journal.active[self.cid]['journal_game_id'] == game['journal_game_id'],
                    'Journal changed during first-frame observation')
            permit.state, self.state = 'consumed','consumed'
            return dict(previous_journal_game_id=old_identifier,
                        journal_game_id=game['journal_game_id'],certificate_identifier=permit.identifier,
                        previous_complete=False,previous_eligible=False,new_known_start=True,
                        game_uid_unchanged=True,clock_handoff_sample=copy.deepcopy(self.clock_samples['before_journal_handoff']),
                        clock_handoff_coherence=handoff_clock_proof)
        except Exception:
            self.state = 'failed'
            if isinstance(permit,_Permit):
                permit.state = 'failed'
            raise
