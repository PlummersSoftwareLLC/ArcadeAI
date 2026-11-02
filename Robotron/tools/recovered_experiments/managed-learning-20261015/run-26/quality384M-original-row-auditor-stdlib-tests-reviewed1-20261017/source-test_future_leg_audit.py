"""SOURCE-ONLY, UNEXECUTED stdlib fixtures. No campaign/model/game data read."""
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

spec=importlib.util.spec_from_file_location('future384_leg_audit',Path(__file__).with_name('audit_completed_leg.py'))
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def plan_fixture():
    candidate='a'*64
    evaluators={name:'b'*64 for name in audit.EVALUATOR_NAMES}
    execution={name:'c'*64 for name in audit.EXECUTION_NAMES}
    for name,sha in audit.BOUNDARY_SOURCES.items():
        if name=='tools/run_quality_campaign.py':execution[str(audit.GAME/name)]=sha
        else:evaluators[name]=sha
    execution[str(audit.GAME/'tools/run_frozen_sidecar.py')]=audit.BOUNDARY_SOURCES['tools/run_frozen_sidecar.py']
    checkpoints={role:dict(source=str(audit.GAME/source),snapshot=str(audit.CAMPAIGN/'checkpoints'/(role+'.pt')),sha256=sha)
        for role,source,sha in (
            ('reference','models_dqn/managed-incumbents/fresh3-256M-confirmed.pt',audit.REFERENCE_SHA256),
            ('candidate','models_dqn/managed-checkpoints/fresh3-384M.pt',candidate))}
    legs=[]
    for index,role in enumerate(('reference','candidate','reference','candidate'),1):
        job=dict(checkpoint=checkpoints[role]['snapshot'],directory=str(audit.CAMPAIGN/('%02d-'%index+role)),label=role+str(index),
            game_boundary_diagnostics=True,cohort_s=1200,actors=16,actor_slots=list(audit.SLOTS),epsilon=0,expert_ratio=0,
            difficulty=5,start_level=1,replay_enabled=False,fp16=False,wait_us=1000,
            device='cuda',gpu_uuid='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0',host='127.0.0.1',port=9999,
            inference_backend='inductor',inference_max_batch_size=16,cpu_threads=2,timeout_s=2400)
        legs.append(dict(index=index,role=role,job=job,command=['synthetic-sidecar','--game-boundary-diagnostics']))
    return dict(output_directory=str(audit.CAMPAIGN),evaluator_source_hashes=evaluators,execution_source_hashes=execution,
        checkpoints=checkpoints,legs=legs,precommit=dict(new_same_length_reference_cohorts=True,
        historical_or_interrupted_receipts_used=False,all_actor_slots=list(audit.SLOTS),
        min_full_games_per_leg=50,max_attempts_per_leg=1,include_every_admitted_game=True,
        include_full_completion_tail=True,admission_extensions=False,
        candidate_gate=dict(each_candidate_individually=True,reference='all games pooled from both fresh reference legs',
                            minimum_mean_ratio=1.05,minimum_median_ratio=1.0))),SimpleNamespace(candidate_sha256=candidate)


def proof_fixture():
    args=SimpleNamespace(candidate_sha256='a'*64)
    source=dict(sha256=args.candidate_sha256,path='synthetic-source-identity')
    copied=dict(sha256=args.candidate_sha256,path='synthetic-copy-identity')
    proof=dict(status='PASS',script_sha256=audit.VERIFIER_SHA256,sha256=args.candidate_sha256,
        source_before=source,source_after_verification=copy.deepcopy(source),verification_copy=copied,
        copy_after_verification=copy.deepcopy(copied),clocks=dict(learner_frame_count=audit.TARGET),
        execution_arguments=dict(expected_checkpoint=str(audit.GAME/'models_dqn/managed-checkpoints/fresh3-384M.pt'),
            expected_target=audit.TARGET,expected_tag='fresh3-384M',expected_sha256=args.candidate_sha256))
    return proof,args


class FutureBindingTests(unittest.TestCase):
    def test_default_literal_plan_reads_no_source_input_helper_or_output(self):
        with (mock.patch.object(audit,'digest',side_effect=AssertionError('read')),
              mock.patch.object(audit,'audit',side_effect=AssertionError('execute')),
              mock.patch.object(Path,'resolve',side_effect=AssertionError('path read')),
              contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertEqual(audit.main([]),0)
        self.assertEqual(output.getvalue(),audit.PLAN+'\n')

    def test_all_four_true_flags_full_source_sets_and_current_reference(self):
        plan,args=plan_fixture();audit.validate_future_plan(plan,args,audit.CAMPAIGN)
        self.assertEqual(len(plan['evaluator_source_hashes']),12)
        self.assertEqual(len(plan['execution_source_hashes']),4)

    def test_one_diagnostic_false_missing_cli_or_missing_source_fails(self):
        for mode in ('flag','cli','source'):
            plan,args=plan_fixture()
            if mode=='flag':plan['legs'][3]['job']['game_boundary_diagnostics']=False
            elif mode=='cli':plan['legs'][2]['command']=[]
            else:plan['evaluator_source_hashes'].pop('Scripts/main.lua')
            with self.subTest(mode=mode),self.assertRaises(ValueError):audit.validate_future_plan(plan,args,audit.CAMPAIGN)

    def test_wrong_checkpoint_old_campaign_pacing_or_threshold_fails(self):
        for mode in ('reference','candidate','campaign','pacing','threshold','cohort',
                     'jobcheckpoint','min50','maxattempts','includeevery','fulltail','extensions'):
            plan,args=plan_fixture();directory=audit.CAMPAIGN
            if mode=='reference':plan['checkpoints']['reference']['sha256']='d'*64
            elif mode=='candidate':plan['checkpoints']['candidate']['sha256']='d'*64
            elif mode=='campaign':directory=Path('/synthetic-old-campaign')
            elif mode=='pacing':plan['legs'][1]['job']['wait_us']=500
            elif mode=='threshold':plan['precommit']['candidate_gate']['minimum_mean_ratio']=1.01
            elif mode=='cohort':plan['legs'][0]['job']['cohort_s']=1199
            elif mode=='jobcheckpoint':plan['legs'][1]['job']['checkpoint']=plan['checkpoints']['reference']['snapshot']
            elif mode=='min50':plan['precommit']['min_full_games_per_leg']=49
            elif mode=='maxattempts':plan['precommit']['max_attempts_per_leg']=2
            elif mode=='includeevery':plan['precommit']['include_every_admitted_game']=False
            elif mode=='fulltail':plan['precommit']['include_full_completion_tail']=False
            else:plan['precommit']['admission_extensions']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):audit.validate_future_plan(plan,args,directory)

    def test_actual384_cpu_proof_unknown_until_supplied_then_strict(self):
        proof,args=proof_fixture();audit.validate_cpu_proof(proof,args)
        for mode in ('status','sha','clock','tag','sourcecopy'):
            bad=copy.deepcopy(proof)
            if mode=='status':bad['status']='FAIL'
            elif mode=='sha':bad['sha256']='e'*64
            elif mode=='clock':bad['clocks']['learner_frame_count']=audit.TARGET-1
            elif mode=='tag':bad['execution_arguments']['expected_tag']='fresh3-320M'
            else:bad['copy_after_verification']['sha256']='e'*64
            with self.subTest(mode=mode),self.assertRaises(ValueError):audit.validate_cpu_proof(bad,args)

    def test_full_nested_diagnostics_are_compared_without_stripping_unknowns(self):
        diagnostic=dict(schema='robotron-game-boundary-inputs-v1',journal_start_reason='new_game',previous_accepted_wire=None,
            current_wire={'raw_score':0,'raw_wave':1},classifier_previous={'raw_score':9900,'raw_wave':2},
            last_start_frame_before=0,last_start_frame_after=1,recent_start=True,classifier_new_game=True,classifier_verdict='accept',
            future_field={'nested':[1,2,3]})
        entry=dict(start_reason='new_game',context={'measurement_active':True,'game_boundary_diagnostics':diagnostic})
        row=dict(start_context=copy.deepcopy(entry['context']))
        audit.validate_original_context(entry,row)
        row['start_context']['game_boundary_diagnostics']['future_field']['nested'][-1]=4
        with self.assertRaisesRegex(ValueError,'diagnostic context'):audit.validate_original_context(entry,row)

    def test_original_dictionary_ids_duplicates_and_partial_journal_fail(self):
        with self.assertRaises(ValueError):audit.indexed([{'journal_game_id':'same'},{'journal_game_id':'same'}],'fixture')
        with self.assertRaisesRegex(ValueError,'Partial'):audit.lines(b'{"journal_game_id":"one"}')


class WarningTimingTests(unittest.TestCase):
    ADDRESS='socket.127.0.0.1:9999'
    ALSA='ALSA lib seq_hw.c:528:(snd_seq_hw_open) open /dev/snd/seq failed: Permission denied'
    def lines(self):
        return ['MAME synthetic start',self.ALSA,'MAME interface initialized.',
                'Socket connection opened to '+self.ADDRESS,'[SOCKET ACTION TIMEOUT] unix_s=102',
                'Socket open failed: '+self.ADDRESS+' (Connection refused)']
    def test_only_same_leg_exact_startup_and_post_cutoff_order_allowed(self):
        allowed,issues=audit.classify_actor_lines(self.lines(),self.ADDRESS,100.5,0,0)
        self.assertEqual(issues,[]);self.assertEqual([row['line_number'] for row in allowed],[2,6])
    def test_pre_first_handshake_refusal_runtime_timeout_or_successful_reconnect_not_hidden(self):
        refused='Socket open failed: '+self.ADDRESS+' (Connection refused)'
        variants=[(self.lines()[:4]+[refused],0,0),
                  (self.lines(),1,1),
                  (self.lines()[:5]+['Socket connection opened to '+self.ADDRESS,refused],0,0)]
        for lines,before,measured in variants:
            with self.subTest(before=before,measured=measured,lines=len(lines)):
                _,issues=audit.classify_actor_lines(lines,self.ADDRESS,100.5,before,measured)
                self.assertTrue(any(row['text']==refused for row in issues))
    def test_equal_integer_cutoff_and_unrecognized_warning_are_unclassified(self):
        lines=self.lines();lines[4]='[SOCKET ACTION TIMEOUT] unix_s=100'
        lines.append('RuntimeError: synthetic unknown')
        _,issues=audit.classify_actor_lines(lines,self.ADDRESS,100.5,0,0)
        self.assertEqual(len(issues),2)


if __name__=='__main__':
    unittest.main()
