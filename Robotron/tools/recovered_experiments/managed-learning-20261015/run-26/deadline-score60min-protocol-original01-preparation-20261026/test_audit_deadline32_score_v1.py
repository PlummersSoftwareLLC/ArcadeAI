"""Independent cutoff/carry audit against real recorder output and mutations."""
import copy
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value


audit=load('_deadline_audit',HERE/'audit_deadline32_score_v1.py')
core=load('_deadline_audit_real_recorder',HERE/'deadline_score_recorder_v2.py')
defs=load('_deadline_recorder_fixture_defs_only',HERE/'test_deadline_score_recorder_v2.py')


def witness(sample,slot,*,snapshot_delay=0):
    raw=struct.pack('>HddBIBBBIBBB',1890,0.,0.,0,sample['raw_wire_score'],1,0,0,20000,2,1,2)
    sample['source_witness']=dict(schema='robotron-deadline32-completed-origin-snapshot-v1',
        process_return_monotonic_ns=sample['completed_exchange_ns'],
        snapshot_begin_monotonic_ns=sample['completed_exchange_ns'],
        snapshot_end_monotonic_ns=sample['completed_exchange_ns']+snapshot_delay,
        raw_header_hex=raw.hex(),original_payload_sha256='f'*64,
        origin_state=dict(client_slot=slot,eval_only=True,measurement_active=True,measurement_generation=1,
            game_uid=sample['origin_game_uid'],frames=sample['accepted_ordinal'],game_score=sample['full_score'],
            raw_score_prev=sample['effective_raw_score'],score_offset=sample['score_offset'],coerced_score_dips=sample['coerced_score_dips']),
        ledger_snapshot=dict(sequence=sample['sequence'],last_accepted_ordinal=sample['accepted_ordinal']),
        selected_journal_game_id=f'original:{slot}')
    return sample


class Tests(unittest.TestCase):
    def fixture(self,completed=False,zero=False):
        clock=defs.Clock();r=core.DeadlineScoreRecorder(clock_ns=clock);score=0 if zero else 100000025
        for slot in core.SLOTS:
            r.bind(slot,defs.member(slot));r.observe(slot,witness(defs.sample(slot,clock.now,score=score,offset=0 if zero else 100000000),slot))
        anchor=r.arm(defs.readiness());d=anchor['deadline_monotonic_ns'];clock.now=d-10
        for slot in core.SLOTS:r.observe(slot,witness(defs.sample(slot,clock.now,sequence=1202,before=10,score=score,offset=0 if zero else 100000000),slot))
        games={}
        if completed:
            clock.now=d
            packet=witness(defs.terminal_sample(4096,d,score,zero_same_uid=zero),4096,snapshot_delay=1)
            r.observe(4096,packet);games[packet['selected']['journal_game_id']]=packet['selected']['result']
        clock.now=d+2
        barrier=dict(deadline_monotonic_ns=d,no_new_origin_entries=True,inflight=0,closed_monotonic_ns=d+1,
            entered=64+int(completed),finished=64+int(completed),fixed_drain_bound_ns=audit.BOUND)
        seal=r.seal(clock.now,barrier=barrier)
        first=defs.member(4096);policy=seal['policy']
        job=dict(actor_slots=list(core.SLOTS),checkpoint={'sha256':policy['policy_sha256']},measurement_label=policy['experiment'],
            sessions={str(s):defs.member(s)['session']for s in core.SLOTS},
            connections={str(s):defs.member(s)['connection']for s in core.SLOTS},expected_policy_clocks=policy['policy_clocks'])
        cleanup=dict(score_sealed_monotonic_ns=clock.now,begin_monotonic_ns=d+3,declared_monotonic_ns=d+4,
            after_flags_monotonic_ns=d+5,errors_before=[],inference_error_before=None,server_shutdown_set_before_owned_signals=True)
        starts={};prefixes=[]
        for row in seal['rows']:
            m=row['member'];starts[m['journal_game_id']]=dict(client_slot=m['slot'],game_uid=m['game_uid'],known_start=True,
                measurement_active=True,measurement_generation=1,experiment=policy['experiment'])
            prefixes.append(dict(slot=m['slot'],session=m['session'],connection=m['connection'],game_uid=m['game_uid'],
                journal_game_id=m['journal_game_id'],certificate_identifier=m['start_certificate_id'],nonce=m['startup_nonce']))
        return [job,dict(original_barrier=barrier),seal,dict(anchor=anchor),cleanup,prefixes,starts,games]

    def test_real_recorder_all32_censored_full_integer_carry(self):
        result=audit.audit(*self.fixture())
        self.assertEqual((result['n_scored'],result['n_completed'],result['n_censored']),(32,0,32))
        self.assertEqual(result['score_sum'],100000025*32)
        self.assertFalse(result['all_raw_tail_frames_reconstructed'])

    def test_completed_old_score_and_zero_same_uid_join_before_teardown(self):
        for zero in (False,True):
            with self.subTest(zero=zero):
                values=self.fixture(completed=True,zero=zero);result=audit.audit(*values)
                self.assertEqual((result['n_completed'],result['n_censored']),(1,31))
                row=values[2]['rows'][0]
                self.assertEqual(row['completion_source_witness']['snapshot_end_monotonic_ns'],values[2]['deadline_monotonic_ns']+1)

    def test_cutoff_policy_carry_and_exposure_mutations_reject(self):
        for damage in ('postdeadline','carry','mode','exposure','denominator','teardown','member'):
            values=self.fixture();seal=values[2];row=seal['rows'][0]
            if damage=='postdeadline':row['score_witness']['completed_exchange_ns']=seal['deadline_monotonic_ns']+1
            elif damage=='carry':row['score_witness']['score_offset']=0
            elif damage=='mode':row['last_activity']['source_witness']['origin_state']['eval_only']=False
            elif damage=='exposure':row['accepted_frame_exposure']+=1
            elif damage=='denominator':seal['n_censored']=31
            elif damage=='teardown':values[4]['begin_monotonic_ns']=seal['seal_observed_monotonic_ns']-1
            else:values[5][0]['nonce']='0'*64
            with self.subTest(damage=damage),self.assertRaises(ValueError):audit.audit(*values)

    def test_disconnect_cannot_be_relabelled_completed(self):
        values=self.fixture(completed=True);row=values[2]['rows'][0]
        row['completed_row']['complete']=False
        values[-1][row['member']['journal_game_id']]=copy.deepcopy(row['completed_row'])
        with self.assertRaises(ValueError):audit.audit(*values)

    def test_terminal_closing_mode_ledger_and_accepted_ordinal_are_actual(self):
        for damage in ('mode','sequence','ordinal'):
            values=self.fixture(completed=True);row=values[2]['rows'][0]
            if damage=='mode':row['completion_source_witness']['origin_state']['eval_only']=False
            elif damage=='sequence':row['completion_source_witness']['ledger_snapshot']['sequence']+=1
            else:row['completion_accepted_ordinal']+=1
            with self.subTest(damage=damage),self.assertRaises(ValueError):audit.audit(*values)


if __name__=='__main__':unittest.main()
