"""CPU-only checkpoint provenance and corruption tests; no evaluator body."""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
C=G/'logs/managed-learning-20261015/run-26/post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
LEGACY=G/'logs/managed-learning-20261015/run-26/deadline-score60min-protocol-original01-preparation-20261026'
REC=PACKET=FIX=WITNESS=CHECK=METADATA=None


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def fixture(completion=None):
    clock=FIX.Clock();rec=REC.DeadlineScoreRecorder(clock_ns=clock,horizon_ns=600_000_000_000,
        checkpoint_offsets_ns=[300_000_000_000]);rec.positively_retired_slots=set()
    base=100_000_025
    for slot in REC.SLOTS:
        rec.bind(slot,FIX.member(slot));rec.observe(slot,WITNESS(FIX.sample(slot,clock.now,score=base,offset=100_000_000),slot))
    anchor=rec.arm(FIX.readiness());target=anchor['anchor_monotonic_ns']+300_000_000_000;deadline=anchor['deadline_monotonic_ns']
    clock.now=target-2
    for slot in REC.SLOTS:rec.observe(slot,WITNESS(FIX.sample(slot,clock.now,sequence=1202,before=10,score=base+100,offset=100_000_000),slot))
    if completion:
        clock.now=target-1 if completion=='before'else target+1
        rec.observe(4096,WITNESS(FIX.terminal_sample(4096,clock.now,base+100,sequence=1203,before=11),4096))
        rec.positively_retired_slots.add(4096)
    clock.now=target+1
    for slot in REC.SLOTS:
        if completion and slot==4096:continue
        rec.observe(slot,WITNESS(FIX.sample(slot,clock.now,sequence=1203,before=11,score=base+900,offset=100_000_000),slot))
    clock.now=target+2;checkpoint=rec.take_checkpoints(clock.now)[0]
    clock.now=deadline-1
    for slot in REC.SLOTS:
        if completion and slot==4096:continue
        rec.observe(slot,WITNESS(FIX.sample(slot,clock.now,sequence=1204,before=12,score=base+1000,offset=100_000_000),slot))
    clock.now=deadline+2
    barrier=dict(deadline_monotonic_ns=deadline,no_new_origin_entries=True,inflight=0,
        closed_monotonic_ns=deadline+1,entered=100,finished=100,fixed_drain_bound_ns=PACKET.BOUND)
    final=rec.seal(clock.now,barrier=barrier)
    job=dict(actor_slots=list(REC.SLOTS),checkpoint={'sha256':final['policy']['policy_sha256']},
        measurement_label=final['policy']['experiment'],horizon_ns=600_000_000_000,checkpoint_offsets_ns=[300_000_000_000],
        expected_policy_clocks=final['policy']['policy_clocks'],sessions={str(s):FIX.member(s)['session']for s in REC.SLOTS},
        connections={str(s):FIX.member(s)['connection']for s in REC.SLOTS})
    prefixes=[];starts={};games={}
    for row in final['rows']:
        m=row['member'];prefixes.append(dict(slot=m['slot'],session=m['session'],connection=m['connection'],
            game_uid=m['game_uid'],journal_game_id=m['journal_game_id'],certificate_identifier=m['start_certificate_id'],nonce=m['startup_nonce']))
        starts[m['journal_game_id']]=dict(client_slot=m['slot'],game_uid=m['game_uid'],known_start=True,
            measurement_active=True,measurement_generation=1,experiment=final['policy']['experiment'])
        if row['whole_game_complete']:games[m['journal_game_id']]=row['completed_row']
    cleanup=dict(score_sealed_monotonic_ns=clock.now,begin_monotonic_ns=deadline+3,
        declared_monotonic_ns=deadline+4,after_flags_monotonic_ns=deadline+5,errors_before=[],
        inference_error_before=None,server_shutdown_set_before_owned_signals=True)
    native=METADATA.attach(dict(original_barrier=barrier),final)
    final_audit=PACKET.audit(job,native,final,dict(anchor=anchor),cleanup,prefixes,starts,games)
    native['_test_final_context']=dict(anchor=dict(anchor=anchor),cleanup=cleanup,starts=starts)
    return [job,checkpoint,final,final_audit,prefixes,native,games,PACKET]


class CheckpointAuditTests(unittest.TestCase):
    def test_real_recorder_checkpoint_and_final_cutoff_audit_join(self):
        values=fixture();result=CHECK.audit_checkpoint(*values)
        self.assertEqual((result['n_scored'],result['n_completed']),(32,0))
        self.assertTrue(result['no_post_horizon_score_credit'])
        self.assertFalse(result['statistical_decision_qualified'])

    def test_completed_before_target_joins_terminal_and_original_STOP(self):
        result=CHECK.audit_checkpoint(*fixture('before'))
        self.assertEqual(result['n_completed'],1)

    def test_completed_after_target_remains_unfinished_at_checkpoint(self):
        values=fixture('after');result=CHECK.audit_checkpoint(*values)
        self.assertEqual(result['n_completed'],0);self.assertEqual(values[2]['n_completed'],1)

    def test_incomplete_duplicate_or_foreign_original_members_rejected(self):
        for damage in ('missing','duplicate','transport','prefix','policy'):
            values=fixture();cp=values[1]
            if damage=='missing':cp['rows'].pop()
            elif damage=='duplicate':cp['rows'][0]=deepcopy(cp['rows'][1])
            elif damage=='transport':cp['rows'][0]['member']['session']='e'*32
            elif damage=='prefix':values[4][0]['nonce']='e'*64
            else:cp['policy']['policy_sha256']='e'*64
            with self.subTest(damage=damage),self.assertRaises(ValueError):CHECK.audit_checkpoint(*values)

    def test_late_score_bad_crossing_or_wrong_origin_witness_rejected(self):
        for damage in ('late_score','crossing_before_target','crossing_sequence','wrong_origin','carry','exposure'):
            values=fixture();cp=values[1];row=cp['rows'][0];target=cp['horizon_monotonic_ns']
            if damage=='late_score':row['score_witness']['completed_exchange_ns']=target+1
            elif damage=='crossing_before_target':row['first_post_horizon_activity']=deepcopy(row['activity'])
            elif damage=='crossing_sequence':row['first_post_horizon_activity']['sequence']+=1
            elif damage=='wrong_origin':row['activity']['source_witness']['origin_state']['client_slot']+=1
            elif damage=='carry':row['score_witness']['score_offset']=0
            else:row['accepted_frame_exposure']+=1
            with self.subTest(damage=damage),self.assertRaises(ValueError):CHECK.audit_checkpoint(*values)

    def test_stale_score_with_otherwise_consistent_packet_clocks_rejected(self):
        values=fixture();row=values[1]['rows'][0];stamp=values[1]['horizon_monotonic_ns']-PACKET.BOUND-1
        row['score_witness']['completed_exchange_ns']=stamp;source=row['score_witness']['source_witness']
        for key in ('process_return_monotonic_ns','snapshot_begin_monotonic_ns','snapshot_end_monotonic_ns'):source[key]=stamp
        with self.assertRaises(ValueError):CHECK.audit_checkpoint(*values)

    def test_earlier_completion_cannot_be_hidden_as_unfinished(self):
        values=fixture('before');row=values[1]['rows'][0]
        row.update(whole_game_complete=False,status='censored',completed_row=None,completion_observed_ns=None,
            positively_retired_without_future_traffic=False)
        with self.assertRaises(ValueError):CHECK.audit_checkpoint(*values)

    def test_later_completion_cannot_be_credited_to_the_earlier_checkpoint(self):
        values=fixture('after');row=values[1]['rows'][0];last=values[2]['rows'][0]
        row.update(whole_game_complete=True,status='completed',completed_row=deepcopy(last['completed_row']),
            completion_observed_ns=last['completion_observed_ns'])
        with self.assertRaises(ValueError):CHECK.audit_checkpoint(*values)

    def test_missing_STOP_nonzero_or_boolean_child_exit_rejected(self):
        for damage in ('STOP','nonce','exit1','boolean_exit','future_authority'):
            values=fixture('before');native=values[5]
            if damage=='STOP':native['completed_first_game_STOP_authorities']['4096']['consumed_before_send']=False
            elif damage=='nonce':native['completed_first_game_STOP_authorities']['4096']['nonce']='e'*64
            elif damage=='exit1':native['original_slots']['4096']['actual_exit']=1
            elif damage=='boolean_exit':native['original_slots']['4096']['actual_exit']=False
            else:native['completed_first_game_STOP_authorities']['4096']['consumed_monotonic_ns']=values[1]['observed_monotonic_ns']+1
            with self.subTest(damage=damage),self.assertRaises(ValueError):CHECK.audit_checkpoint(*values)

    def test_mixed_schedule_claims_missing_closure_or_wrong_final_audit_rejected(self):
        for damage in ('schedule','horizon','mean','completed_count','automatic','independence','closure','final_audit'):
            values=fixture();cp=values[1]
            if damage=='schedule':values[0]['checkpoint_offsets_ns']=[]
            elif damage=='horizon':cp['final_horizon_ns']=900_000_000_000
            elif damage=='mean':cp['mean_score']+=1
            elif damage=='completed_count':cp['n_completed']=1
            elif damage=='automatic':cp['automatic_decision']=True
            elif damage=='independence':cp['repeated_looks_are_not_independent_games']=False
            elif damage=='closure':values[5]['all_original_threads_stopped']=False
            else:values[3]['score_sum']+=1
            with self.subTest(damage=damage),self.assertRaises(ValueError):CHECK.audit_checkpoint(*values)


    def test_final_retirement_guard_rejects_missing_original_proof(self):
        for damage in ('normal_slots','writer','unsealed','STOP_sequence','STOP_payload','STOP_flag','native_error'):
            values=fixture('before');job,cp,final,previous,prefixes,native,games,packet=values
            self.assertTrue(packet.validate_completed_retirement(final['rows'][0],job,native,final))
            if damage=='normal_slots':native['completed_original_normal0_slots']=[]
            elif damage=='writer':native['original_slots']['4096']['outputs_sealed_after_original_writer_closure']=False
            elif damage=='unsealed':native['original_slots']['4096']['original_unsealed_output_paths']=['unknown']
            elif damage=='STOP_sequence':native['completed_first_game_STOP_authorities']['4096']['sequence']+=1
            elif damage=='STOP_payload':native['completed_first_game_STOP_authorities']['4096']['completion']['score']+=1
            elif damage=='STOP_flag':native['completed_first_game_STOP_authorities']['4096']['consumed_before_send']=False
            else:native['errors']=['unknown original failure']
            with self.subTest(damage=damage),self.assertRaises(ValueError):packet.validate_completed_retirement(final['rows'][0],job,native,final)

    def test_unfinished_final_activity_must_still_be_fresh(self):
        job,cp,final,previous,prefixes,native,games,packet=fixture()
        activity=final['rows'][0]['last_activity'];stamp=final['deadline_monotonic_ns']-PACKET.BOUND-1
        activity['completed_exchange_ns']=stamp
        for key in ('process_return_monotonic_ns','snapshot_begin_monotonic_ns','snapshot_end_monotonic_ns'):
            activity['source_witness'][key]=stamp
        final['rows'][0]['activity_age_ns']=PACKET.BOUND+1
        context=native['_test_final_context']
        with self.assertRaises(ValueError):packet.audit(job,native,final,context['anchor'],context['cleanup'],prefixes,context['starts'],games)


def main():
    global REC,PACKET,FIX,WITNESS,CHECK,METADATA
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--source-manifest',type=Path);parser.add_argument('--source-manifest-sha256');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    raw=args.source_manifest.read_bytes();assert hashlib.sha256(raw).hexdigest()==args.source_manifest_sha256
    h=load('_checkpoint_test_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');manifest=json.loads(raw)
    REC=load('_checkpoint_test_recorder',h.checked(manifest['sources']['recorder']))
    PACKET=load('_checkpoint_test_packet_auditor',h.checked(manifest['sources']['score_auditor']))
    sys.modules['deadline_score_recorder_v3']=REC
    FIX=load('_checkpoint_test_fixture_defs',LEGACY/'test_deadline_score_recorder_v3.py')
    legacy_audit=load('_checkpoint_test_packet_fixture_defs',LEGACY/'test_audit_deadline32_score_v1.py');WITNESS=legacy_audit.witness
    METADATA=load('_checkpoint_retirement_fixture_metadata',Path(__file__).with_name('retirement_test_metadata_v1.py'))
    CHECK=load('_checkpoint_new_auditor',Path(__file__).with_name('audit_horizon_checkpoint_v1.py'))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CheckpointAuditTests))
    assert 'torch'not in sys.modules
    report=dict(status='PASS'if result.wasSuccessful()else'FAIL',tests_run=result.testsRun,
        failures=[dict(test=str(test),traceback=trace)for test,trace in result.failures],
        errors=[dict(test=str(test),traceback=trace)for test,trace in result.errors],log=stream.getvalue(),
        manifest=h.pin(args.source_manifest),auditor=h.pin(Path(__file__).with_name('audit_horizon_checkpoint_v1.py')),
        test_source=h.pin(Path(__file__)),Torch_imported=False,GPU_MAME_or_native_body_launched=False,
        current_sources_or_controls_changed=False,statistical_error_control_qualified=False,promotion=False)
    pin=h.put(args.output,report)
    print(json.dumps(dict(status=report['status'],tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),report=pin)))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
