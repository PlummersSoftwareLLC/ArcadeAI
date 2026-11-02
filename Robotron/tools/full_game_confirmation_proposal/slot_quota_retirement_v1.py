"""Prospective per-slot retirement around the unchanged quota64 authority.

Each slot may stop after its own TWO originally selected full games finish.
The original authority must still validate all64 games before global completion.
No I/O or runtime actions occur until explicitly constructed and called.
"""
import copy
import hashlib
import inspect
import json
from pathlib import Path
import threading

PARENT_SHA='ecd278045df06736ed59c16c6293e6a220968cfb89d38820ae9b2117be075f7b'
SLOTS=tuple(range(4096,4128))


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


class SlotPermit:
    __slots__=('payload','identifier','used')
    def __init__(self,body):
        self.payload=canonical(body);self.identifier=hashlib.sha256(self.payload).hexdigest();self.used=False


class SlotQuotaRetirement:
    def __init__(self,original):
        require(type(original).__name__=='CohortDrain'
            and hashlib.sha256(Path(inspect.getsourcefile(type(original))).read_bytes()).hexdigest()==PARENT_SHA,
            'Exact original quota64 authority required')
        require(original.state=='waiting' and original.permit is None,'Original authority already consumed')
        self.original=original;self.lock=threading.RLock();self._failed=False
        self._permits={};self._commitments={};self._receipts={};self._views={slot:self._view(slot)for slot in SLOTS}

    @property
    def state(self):return 'failed'if self._failed else self.original.state

    @property
    def permit(self):
        """Original GLOBAL certificate; never forge its used-slot history."""
        return self.original.permit

    @property
    def slot_stop_receipts(self):
        with self.lock:return copy.deepcopy(self._receipts)

    def _live(self):
        require(not self._failed,'Per-slot authority failed; no rescue or retry')
        return self.original._live()

    def _invalidate(self):
        self._failed=True;self.original.state='failed'

    def register_start(self,**subject):
        with self.lock:
            try:
                self._live();return self.original.register_start(**subject)
            except Exception:
                self._invalidate();raise

    def _slot_rows(self,cohort,slot):
        base=self.original
        require(set(base.registrations)==set(SLOTS),'All32 original certified starts required before slot retirement')
        require(cohort['valid'] is True and cohort['abandoned']==0
            and cohort['expected_games']==64 and cohort['games_per_slot']==2,
            'Original selected quota64 cohort changed')
        rows=[copy.deepcopy(row)for row in cohort['rows']if row['client_slot']==slot]
        if len(rows)<2:return None
        require(len(rows)==2 and cohort['slot_admitted_counts'][str(slot)]==2,
            'Only the original two selected games may retire a slot')
        rows.sort(key=lambda row:(row['start_unix_s'],row['journal_game_id']))
        ids=[row['journal_game_id']for row in rows]
        require(len(set(ids))==2 and set(ids)<=set(cohort['started_ids'])
            and ids[0]==base.registrations[slot]['journal_game_id']
            and rows[0]['terminal_confirmation']['next_journal_game_id']==ids[1],
            'First certified game and its actual next game must be the selected pair')
        with base.journal.lock:
            games={key:copy.deepcopy(base.journal.measurement_games.get(key))for key in
                set(ids)|{row['terminal_confirmation']['next_journal_game_id']for row in rows}}
        # Same actual-row, natural-terminal and next-journal joins as the
        # original global64 guard, applied to this unchanged selected pair.
        for row in rows:
            registration=base.registrations.get(slot)
            require(registration is not None and row['client_id']==registration['client_id']
                and row['known_start'] is row['complete'] is row['eligible'] is row['eval_only'] is row['measurement_active'] is True
                and row['excluded_reason']=='' and row['first_play_level']==1 and row['playable_frames']>0
                and row['measurement_generation']==base.policy['measurement_generation']
                and row['experiment']==base.policy['experiment']
                and row['completion_policy']=='confirmed_reset_reserves_v1',
                'Selected slot result is not an eligible confirmed full game')
            game=games.get(row['journal_game_id'])
            require(game is not None and game['finished'] is True and game['result']==row,
                'Slot result differs from the retained actual journal member')
            terminal=row['terminal_confirmation']
            require(type(terminal)is dict and terminal['schema']=='robotron-confirmed-game-reset-v1'
                and terminal['reason']==row['boundary_reason']
                and terminal['previous_score']==row['score'] and terminal['previous_game_uid']==row['game_uid']
                and terminal['reason']in('score_reset','zero_score_restart'),
                'Actual terminal reset is missing')
            next_game=games.get(terminal['next_journal_game_id'])
            require(next_game is not None and next_game['journal_game_id']!=row['journal_game_id']
                and next_game['known_start'] is next_game['measurement_active'] is True
                and next_game['client_id']==row['client_id'] and next_game['client_slot']==slot
                and next_game['game_uid']==terminal['next_game_uid']
                and next_game['start_frame']['score']==terminal['next_score']
                and next_game['start_frame']['level']==terminal['next_wave']
                and next_game['start_frame']['raw_reserves']==terminal['next_raw_reserves']
                and next_game['measurement_generation']==row['measurement_generation']
                and next_game['start']['experiment']==row['experiment']
                and next_game['start_unix_s']>=row['end_unix_s'],
                'Actual next-reset journal join differs')
        return rows

    def try_issue(self):
        """Issue completed SLOT permits; return GLOBAL permit only at all64."""
        with self.lock:
            try:
                now,mono,status=self._live();cohort=self.original._cohort(now)
                if set(self.original.registrations)!=set(SLOTS):return None
                for slot in SLOTS:
                    if slot in self._permits:continue
                    rows=self._slot_rows(cohort,slot)
                    if rows is None:continue
                    registration=self.original.registrations[slot]
                    self._permits[slot]=SlotPermit(dict(schema='robotron-fixed-slot-two-full-games-retirement-v1',
                        policy=copy.deepcopy(self.original.policy),admission=copy.deepcopy(self.original.window),
                        registration=copy.deepcopy(registration),slot=slot,selected_game_ids=[r['journal_game_id']for r in rows],
                        selected_rows_sha256=digest(rows),required_complete_games_this_slot=2,
                        global_expected_games=64,global_completed_at_issue=cohort['count'],
                        issued_unix_ns=now,issued_monotonic_ns=mono,global_completion_claim=False,quality_qualified=False))
                    self._commitments[slot]=self._permits[slot].identifier
                if self.original.permit is None:return self.original.try_issue()
                return self.original.permit
            except Exception:
                self._invalidate();raise

    def authorize_slot(self,permit,*,slot,session,connection,nonce,sequence):
        with self.lock:
            try:
                now,mono,status=self._live()
                require(type(slot)is int and slot in SLOTS and type(sequence)is int and 1200<sequence<(1<<32),
                    'Original post-prefix slot/sequence required')
                require(permit is self._permits.get(slot) and type(permit)is SlotPermit and not permit.used
                    and slot not in self._receipts and permit.identifier==self._commitments[slot]
                    and hashlib.sha256(permit.payload).hexdigest()==permit.identifier,
                    'Exact unused original slot permit required')
                registration=self.original.registrations[slot]
                require(all(registration[k]==v for k,v in dict(slot=slot,session=session,connection=connection,nonce=nonce).items()),
                    'Foreign original slot STOP subject')
                cohort=self.original._cohort(now);rows=self._slot_rows(cohort,slot);body=json.loads(permit.payload)
                require(rows is not None and digest(rows)==body['selected_rows_sha256']
                    and [r['journal_game_id']for r in rows]==body['selected_game_ids']
                    and body['policy']==self.original.policy and body['admission']==self.original.window
                    and body['registration']==registration and body['global_completion_claim'] is False
                    and body['schema']=='robotron-fixed-slot-two-full-games-retirement-v1'
                    and body['slot']==slot and body['required_complete_games_this_slot']==2
                    and body['global_expected_games']==64
                    and now>=body['issued_unix_ns'] and mono>=body['issued_monotonic_ns'],
                    'Original selected slot games or policy changed before STOP')
                permit.used=True
                receipt=dict(schema='robotron-consumed-two-game-slot-retirement-v1',
                    permit_identifier=permit.identifier,selected_rows_sha256=body['selected_rows_sha256'],
                    selected_game_ids=body['selected_game_ids'],slot=slot,session=session,connection=connection,
                    nonce=nonce,sequence=sequence,authorized_unix_ns=now,authorized_monotonic_ns=mono,
                    consumed_before_send=True,global_completion_claim=False)
                self._receipts[slot]=copy.deepcopy(receipt);return receipt
            except Exception:
                self._invalidate();raise

    def _view(self,slot):
        owner=self
        class View:
            lock=owner.lock
            @property
            def permit(self):return owner._permits.get(slot)
            def register_start(self,**subject):
                if subject.get('slot')!=slot:
                    with owner.lock:owner._invalidate()
                    raise ValueError('Slot-view registration mismatch')
                return owner.register_start(**subject)
            def authorize_slot(self,permit,**subject):
                if subject.get('slot')!=slot:
                    with owner.lock:owner._invalidate()
                    raise ValueError('Slot-view STOP mismatch')
                return owner.authorize_slot(permit,**subject)
        return View()

    def for_slot(self,slot):
        require(type(slot)is int and slot in self._views,'Declared original slot required')
        return self._views[slot]
