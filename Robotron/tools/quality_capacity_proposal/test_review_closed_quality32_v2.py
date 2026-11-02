"""Closed-review integration checks; synthetic histories, no live mutations."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import review_closed_quality32_v2 as review
import audit_quality32_evidence_v1 as cohorts
import test_audit_pilot_evidence as fixtures
import audit_pilot_evidence as helpers
import audit_confirmed_completed_leg_reviewed3 as auditor
from Robotron.tools import compare_sidecar_measurements as backend


def legs(counts=(50,50,50,50), scores=(100,105,100,105)):
    return [dict(index=index,role=role,rows=[dict(journal_game_id=f'{index}:{i}',
        client_slot=4096+i%32,score=score) for i in range(count)])
        for index,(role,count,score) in enumerate(zip(
            ['reference','candidate','reference','candidate'],counts,scores),1)]


class DecisionTests(unittest.TestCase):
    def test_both_candidates_exactly_at_gate_pass_individually(self):
        data=legs();before=copy.deepcopy(data);result=review.decision(data)
        self.assertTrue(result['qualified_improvement'])
        self.assertEqual(result['pooled_reference']['count'],100)
        self.assertEqual([x['index'] for x in result['individual_candidate_checks']],[2,4])
        self.assertFalse(result['candidates_pooled_for_qualification'])
        self.assertEqual(data,before)

    def test_strong_other_candidate_cannot_rescue_a_failure(self):
        for scores in ((100,104,100,1000),(100,1000,100,104)):
            with self.subTest(scores=scores):
                result=review.decision(legs(scores=scores))
                self.assertFalse(result['qualified_improvement'])
                self.assertEqual(sum(x['mean_pass'] for x in result['individual_candidate_checks']),1)

    def test_high_mean_cannot_rescue_failed_median(self):
        data=legs()
        for index,row in enumerate(data[1]['rows']):row['score']=99 if index<26 else 1000
        result=review.decision(data);check=result['individual_candidate_checks'][0]
        self.assertTrue(check['mean_pass']);self.assertFalse(check['median_pass'])
        self.assertFalse(result['qualified_improvement'])

    def test_all_fresh_reference_games_are_used_with_unequal_counts(self):
        result=review.decision(legs(counts=(50,73,150,61),scores=(100,180,200,200)))
        self.assertEqual(result['pooled_reference'],dict(count=200,score_sum=35000,mean=175,median=200))
        self.assertFalse(result['qualified_improvement'])
        self.assertFalse(result['individual_candidate_checks'][0]['mean_pass'])

    def test_under50_missing_high_slot_overlap_and_noninteger_scores_fail(self):
        for change in ('count','slot','overlap','float_score','boolean_score','negative_score','missing_leg'):
            data=legs()
            if change=='count':data[1]['rows'].pop()
            elif change=='slot':
                for row in data[3]['rows']:
                    if row['client_slot']==4127:row['client_slot']=4126
            elif change=='overlap':data[1]['rows'][0]['journal_game_id']=data[0]['rows'][0]['journal_game_id']
            elif change=='missing_leg':data.pop()
            else:data[1]['rows'][0]['score']={'float_score':105.,'boolean_score':True,'negative_score':-1}[change]
            with self.subTest(change=change),self.assertRaises(ValueError):review.decision(data)

    def test_zero_reference_and_changed_roles_cannot_qualify(self):
        with self.assertRaises(ValueError):review.decision(legs(scores=(0,105,0,105)))
        data=legs();data[2]['role']='candidate'
        with self.assertRaises(ValueError):review.decision(data)

    def test_four_original_ROM_reviewed_cohorts_feed_the_same_individual_decision(self):
        reviewed=[]
        for index,role in enumerate(['reference','candidate','reference','candidate'],1):
            case=fixtures.EvidenceTests('test_all50_originals_and_ROM_proofs_cover32_slots_without_mutation')
            case.setUp()
            try:
                data=case.data;label=f'original-synthetic-leg-{index}'
                data['label']=data['job']['label']=label
                successors={}
                for row in data['rows']:
                    old=row['journal_game_id'];new=f'{index}:{old}'
                    successor=data['terminal_successors'][old]
                    successor['journal_game_id']=new+':next'
                    row['journal_game_id']=new;row['experiment']=label
                    row['start_context']['experiment']=row['end_context']['experiment']=label
                    row['terminal_confirmation']['next_journal_game_id']=successor['journal_game_id']
                    successors[new]=successor
                data['terminal_successors']=successors
                data['cohort']['started_ids']=[row['journal_game_id'] for row in data['rows']]
                case.write_originals()
                result=cohorts.completed_cohort(data,case.root,backend,helpers,auditor)
                self.assertEqual(result['original_games']['rom_game_over_evidence']['verified_games'],50)
                reviewed.append(dict(index=index,role=role,rows=copy.deepcopy(data['rows'])))
            finally:case.doCleanups()
        result=review.decision(reviewed)
        self.assertEqual(result['pooled_reference']['count'],100)
        self.assertFalse(result['qualified_improvement'])


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.plan=dict(legs=[dict(index=i,role=role,receipt_path=f'/tmp/{i}/receipt.json',
            console_log=f'/tmp/{i}.log',evaluator_status_path=f'/tmp/{i}/status.json')
            for i,role in enumerate(['reference','candidate','reference','candidate'],1)])
        self.status=dict(state='finished',plan_sha256='a'*64,outcome='qualified_improvement',legs=[
            dict(spec,state='finished',returncode=0,pid=1000+spec['index'],
                 started_unix_s=100*spec['index'],ended_unix_s=100*spec['index']+99)
            for spec in self.plan['legs']])
        self.summary=dict(plan_sha256='a'*64,outcome='qualified_improvement',stop_signal=None)

    def validate(self):return review.validate_records(self.plan,self.status,self.summary,'a'*64)

    def test_exact_original_four_successful_records_pass(self):
        self.assertEqual(len(self.validate()),4)

    def test_nonzero_interrupted_duplicate_missing_running_or_overlapping_record_fails(self):
        for change in ('nonzero','signal','duplicate_pid','missing','running','overlap','receipt','plan'):
            before=copy.deepcopy((self.status,self.summary))
            if change=='nonzero':self.status['legs'][1]['returncode']=1
            elif change=='signal':self.summary['stop_signal']=2
            elif change=='duplicate_pid':self.status['legs'][1]['pid']=self.status['legs'][0]['pid']
            elif change=='missing':self.status['legs'].pop()
            elif change=='running':self.status['legs'][1]['state']='running'
            elif change=='overlap':self.status['legs'][1]['started_unix_s']=101
            elif change=='receipt':self.status['legs'][1]['receipt_path']='/tmp/foreign.json'
            else:self.summary['plan_sha256']='b'*64
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate()
            self.status,self.summary=before


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.owner=dict(pid=900,cgroup='/synthetic-campaign')
        self.record=dict(pid=1000)
        self.evaluator=dict(pid=1000,parent_pid=900,cgroup='/synthetic-campaign',
                            starttime_ticks=100,observed_live=True)
        self.actors={str(slot):dict(pid=slot+10000,starttime_ticks=1000+slot,observed_live=True,
            parent_pid=1000,cgroup='/synthetic-campaign') for slot in review.SLOTS}
        self.receipt=dict(socket_wait=dict(actors={slot:dict(pid=value['pid']) for slot,value in self.actors.items()}))

    def validate(self):return review.validate_births(self.record,self.evaluator,self.actors,self.receipt,self.owner)

    def test_original_evaluator_and_all32_births_pass(self):self.validate()

    def test_unknown_parent_group_missing_high_slot_or_changed_pacing_PID_fails(self):
        for change in ('parent','group','not_live','start','missing','pacing','evaluator'):
            before=copy.deepcopy((self.evaluator,self.actors,self.receipt))
            if change=='parent':self.actors['4127']['parent_pid']=999
            elif change=='group':self.actors['4127']['cgroup']='/foreign'
            elif change=='not_live':self.actors['4127']['observed_live']=False
            elif change=='start':self.actors['4127']['starttime_ticks']=0
            elif change=='missing':self.actors.pop('4127')
            elif change=='pacing':self.receipt['socket_wait']['actors']['4127']['pid']=999
            else:self.evaluator['parent_pid']=999
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate()
            self.evaluator,self.actors,self.receipt=before


class RootBindingTests(unittest.TestCase):
    def test_exact_precommitted_main_holds_are_required(self):
        main=dict(owner=dict(pid=900),actors=list(range(192)),held_hashes={str(i):'a'*64 for i in range(193)},experiment='same')
        binding=dict(main_holds=copy.deepcopy(main),expected_window=dict(owner=dict(pid=900)))
        review.validate_main_binding(main,binding)
        for change in ('hash','actor','owner','experiment'):
            value=copy.deepcopy(main)
            if change=='hash':value['held_hashes']['192']='b'*64
            elif change=='actor':value['actors'][-1]=999
            elif change=='owner':value['owner']['pid']=901
            else:value['experiment']='another'
            with self.subTest(change=change),self.assertRaises(ValueError):review.validate_main_binding(value,binding)

    def test_original_native_command_must_match_bound_controller_and_archive(self):
        config=dict(unit='original.service',output='/tmp/original',argv=[
            str(review.GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',
            str(review.HERE/'profile03/Robotron/tools/run_quality_campaign.py'),
            '--actors','32','--game-boundary-diagnostics','--launch'])
        binding=dict(campaign=dict(native_unit=config['unit'],controller_output=config['output'],command=config['argv']))
        wrapper=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','TMPDIR=/tmp/original/tmp']+config['argv']
        fields=dict(ExecStart='{ path=/usr/bin/env ; argv[]='+' '.join(wrapper)+' ; ignore_errors=no ; pid=900 ; code=exited ; status=0 }')
        review.validate_native_command(fields,binding,config)
        fields['ExecStart']=fields['ExecStart'].replace('run_quality_campaign.py','foreign.py')
        with self.assertRaises(ValueError):review.validate_native_command(fields,binding,config)

    def test_foreign_executable_cannot_pass_even_when_binding_and_archive_agree(self):
        config=dict(unit='original.service',output='/tmp/original',argv=['/usr/bin/python3.12','/tmp/foreign.py'])
        binding=dict(campaign=dict(native_unit=config['unit'],controller_output=config['output'],command=config['argv']))
        wrapper=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','TMPDIR=/tmp/original/tmp']+config['argv']
        fields=dict(ExecStart='{ path=/usr/bin/env ; argv[]='+' '.join(wrapper)+' ; ignore_errors=no ; pid=900 ; code=exited ; status=0 }')
        with self.assertRaisesRegex(ValueError,'Selected private32-slot'):
            review.validate_native_command(fields,binding,config)

    def test_missing_closed_context_has_no_output_or_runtime_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'output'
            def missing(path):raise FileNotFoundError(path)
            reader=SimpleNamespace(pin=missing)
            with self.assertRaises(FileNotFoundError):
                review.review(dict(closed_context_path=str(Path(directory)/'missing.json'),output=str(output)),{},reader)
            self.assertFalse(output.exists())

    def test_default_CLI_does_not_read_requested_job_or_import_numerical_runtime(self):
        result=subprocess.run([sys.executable,'-I','-B',review.__file__,'--job','/missing.json'],
            capture_output=True,text=True,check=True,timeout=10)
        self.assertTrue(result.stdout.startswith('PLAN_ONLY:'))

    def test_actual_dependency_sources_match_the_tested_components(self):
        for path,expected in review.DEPENDENCIES.values():
            self.assertEqual(review.digest(path),expected)
