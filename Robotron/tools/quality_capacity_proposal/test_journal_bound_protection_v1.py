"""Protection tests publish synthetic candidates only into owned temporary dirs."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

import protect_quality32_winner_v5 as protect
import test_journal_bound_closed_review_v1 as full_fixture


class PrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.rows=[dict(journal_game_id=f'game:{i}') for i in range(50)]
        links=[dict(journal_game_id=row['journal_game_id'],previous_raw_reserves=0,
            inactive_player_observed=True,recent_restart_observed=True) for row in self.rows]
        original=dict(statistics=dict(count=50),original_game_ids=[row['journal_game_id'] for row in self.rows],
            original_terminal_readback=dict(status='PASS',verified_games=50,links=copy.deepcopy(links)),
            rom_game_over_evidence=dict(status='PASS',verified_games=50,links=copy.deepcopy(links)))
        self.reviewed=dict(index=2,role='candidate',cohort=dict(original_games=original,
            actor_logs=dict(slots={str(slot):{} for slot in protect.SLOTS})))
        self.receipt=dict(rows=self.rows);self.spec=dict(index=2,role='candidate')

    def validate(self):protect.validate_original_leg(self.reviewed,self.receipt,self.spec)

    def test_all_original_game_ROM_and_slot_proofs_pass(self):self.validate()

    def test_missing_game_ROM_proof_slot_or_changed_terminal_fails(self):
        for change in ('count','ROM_count','ROM_link','reserve','boolean_reserve','alive','restart','slot','role'):
            original=copy.deepcopy(self.reviewed);proof=self.reviewed['cohort']['original_games']
            if change=='count':proof['statistics']['count']=49
            elif change=='ROM_count':proof['rom_game_over_evidence']['verified_games']=49
            elif change=='ROM_link':proof['rom_game_over_evidence']['links'].pop()
            elif change=='reserve':proof['rom_game_over_evidence']['links'][0]['previous_raw_reserves']=1
            elif change=='boolean_reserve':proof['rom_game_over_evidence']['links'][0]['previous_raw_reserves']=False
            elif change=='alive':proof['rom_game_over_evidence']['links'][0]['inactive_player_observed']=False
            elif change=='restart':proof['rom_game_over_evidence']['links'][0]['recent_restart_observed']=False
            elif change=='slot':self.reviewed['cohort']['actor_logs']['slots'].pop('4127')
            else:self.reviewed['role']='reference'
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate()
            self.reviewed=original

    def test_default_CLI_is_inert_even_with_publish_without_execute(self):
        result=subprocess.run([sys.executable,'-I','-B',protect.__file__,'--publish','--job','/missing'],
            capture_output=True,text=True,check=True,timeout=10)
        self.assertTrue(result.stdout.startswith('PLAN_ONLY:'))

    def test_existing_label_and_unsafe_label_never_invoke_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'winner.pt';target.write_bytes(b'previous policy');target.chmod(0o444)
            before=target.read_bytes()
            with patch.object(protect,'verify') as verify:
                for label in ('winner','../escape','/absolute',''):
                    with self.subTest(label=label),self.assertRaises(ValueError):
                        protect.publish(dict(label=label,destination=directory),{},None)
                verify.assert_not_called()
            self.assertEqual(target.read_bytes(),before)
            self.assertFalse(list(Path(directory).glob('*.partial')))

    def test_reviewer_command_must_bind_the_original_script_job_source_and_owner(self):
        job=dict(review_job=dict(path='/synthetic/job.json',sha256='a'*64),
                 reviewer_source=dict(path='/synthetic/reviewer.py',sha256=protect.REVIEWER_SHA))
        owner=dict(unit='original-review.service')
        argv=['/usr/bin/python3.12','-I','-B',job['reviewer_source']['path'],'--execute','--job',
            job['review_job']['path'],'--job-sha256',job['review_job']['sha256'],'--source-sha256',protect.REVIEWER_SHA]
        config=dict(unit=owner['unit'],output='/tmp/synthetic-original-review',argv=argv)
        wrapper=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+config['output']+'/tmp']+argv
        fields=dict(ExecStart='{ path=/usr/bin/env ; argv[]='+' '.join(wrapper)+' ; ignore_errors=no ; pid=1 ; code=exited ; status=0 }')
        protect.validate_review_command(fields,owner,config,job)
        for change in ('script','job','source','owner','archive'):
            value=copy.deepcopy(config);observed=copy.deepcopy(fields);selected=copy.deepcopy(owner)
            if change=='script':value['argv'][3]='/synthetic/foreign.py'
            elif change=='job':value['argv'][-3]='b'*64
            elif change=='source':value['argv'][-1]='b'*64
            elif change=='owner':selected['unit']='foreign.service'
            else:observed['ExecStart']=observed['ExecStart'].replace('/synthetic/reviewer.py','/synthetic/foreign.py')
            with self.subTest(change=change),self.assertRaises(ValueError):
                protect.validate_review_command(observed,selected,value,job)


class FullProtectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=full_fixture.FullPathTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.reader=self.fixture.reader;self.root=self.fixture.root

    def prepare(self,candidate_gain=True):
        result,_,_=self.fixture.execute(candidate_gain=candidate_gain)
        self.assertTrue(result['valid'],result.get('error'))
        root_job=self.reader.pin(self.root/'root-job.json');source=self.reader.pin(Path(full_fixture.review.__file__))
        self.assertEqual(source['sha256'],protect.REVIEWER_SHA)
        owner=dict(self.fixture.owner,unit='robotron-quality32-synthetic-review.service',timer='robotron-quality32-synthetic-review.timer',
            pid=9_000_010,invocation_id='e'*32,timer_invocation_id='f'*32,cgroup='/synthetic-quality32-review')
        config=dict(unit=owner['unit'],output=str(self.root/'original-review-execution'),
            argv=['/usr/bin/python3.12','-I','-B',source['path'],'--execute','--job',root_job['path'],
                '--job-sha256',root_job['sha256'],'--source-sha256',source['sha256']])
        closure_entry=self.fixture.closure(owner,config,'original-review-closure',self.fixture.end_mono+1,self.fixture.end_mono+2)
        closure=self.reader.read_pin(closure_entry);record=closure['full_original_archives'][0]
        fields=dict(line.split('=',1) for line in self.reader.read_pin(record['stdout'],as_json=False).decode().splitlines() if '=' in line)
        fields.update(RuntimeMaxUSec='3min',MemoryMax=str(4<<30),CPUQuotaPerSecUSec='2s')
        record['stdout']=self.fixture.put(record['stdout']['path'],(''.join(key+'='+value+'\n' for key,value in fields.items())).encode())
        closure_entry=self.fixture.put(closure_entry['path'],closure)
        destination=self.root/'protected';destination.mkdir(mode=0o700)
        self.job=dict(schema='robotron-quality32-winner-protection-job-v1',label='synthetic-winner',destination=str(destination),
            reviewer_source=source,review_job=root_job,review_report=self.reader.pin(self.root/'review/review.json'),
            review_owner=self.fixture.put(self.root/'review-owner.json',owner),review_closure=closure_entry,
            review_controller_config=self.fixture.put(self.root/'review-controller-config.json',config))
        self.job_entry=self.fixture.put(self.root/'protection-job.json',self.job)
        self.no_scientific_rerun=Mock(side_effect=AssertionError('Original scientific audit must not rerun'))
        self.checked=self.reader.checked_module

    def reader_patch(self,name,entry):
        module=self.checked(name,entry)
        if entry['sha256']==protect.REVIEWER_SHA:module.review=self.no_scientific_rerun
        return module

    def publish(self):
        with patch.object(self.reader,'checked_module',side_effect=self.reader_patch):
            return protect.publish(self.job,self.job_entry,self.reader)

    def test_full_original_review_to_immutable_publication_preserves_reference_and_never_reruns_audit(self):
        self.prepare();before=self.reader.pin(self.fixture.reference['path'])
        result=self.publish();final=Path(result['protected_checkpoint']);metadata=final.with_suffix('.pt.json')
        self.assertEqual(final.read_bytes(),Path(self.fixture.candidate['path']).read_bytes())
        self.assertEqual(protect.digest(final),self.fixture.candidate['sha256'])
        for path in (final,metadata):
            self.assertEqual(path.stat().st_mode&0o777,0o444);self.assertEqual(path.stat().st_nlink,1)
        self.assertEqual(self.reader.pin(self.fixture.reference['path']),before)
        self.assertFalse(result['managed_incumbent_updated']);self.assertFalse(result['live_learner_restored'])
        self.assertFalse(result['original_scientific_audit_rerun']);self.no_scientific_rerun.assert_not_called()
        self.assertFalse(list(final.parent.glob('*.partial')))

    def test_one_failing_candidate_refuses_any_publication(self):
        self.prepare(candidate_gain=False)
        with self.assertRaisesRegex(ValueError,'qualified original independent review'):self.publish()
        self.assertEqual(list(Path(self.job['destination']).iterdir()),[])
        self.no_scientific_rerun.assert_not_called()

    def test_forged_qualified_flag_cannot_rescue_a_failed_original_candidate(self):
        self.prepare(candidate_gain=False)
        report=self.reader.read_pin(self.job['review_report'])
        report['quality_qualified']=True;report['decision']['qualified_improvement']=True
        report['decision']['outcome']='qualified_improvement'
        for check in report['decision']['individual_candidate_checks']:
            check['mean_pass']=check['median_pass']=True
        self.job['review_report']=self.fixture.put(self.job['review_report']['path'],report)
        self.job_entry=self.fixture.put(self.job_entry['path'],self.job)
        with self.assertRaisesRegex(ValueError,'Both original candidates'):self.publish()
        self.assertEqual(list(Path(self.job['destination']).iterdir()),[])
        self.no_scientific_rerun.assert_not_called()

    def test_evidence_mutation_after_copy_prevents_publication(self):
        self.prepare();actual_copy=protect.shutil.copyfileobj
        def copy_and_change(source,destination):
            actual_copy(source,destination)
            path=self.fixture.directory/'plan.json';value=json.loads(path.read_bytes());value['hypothesis']='changed after copy'
            self.fixture.put(path,value)
        with patch.object(protect.shutil,'copyfileobj',side_effect=copy_and_change),self.assertRaises(ValueError):self.publish()
        self.assertEqual(list(Path(self.job['destination']).iterdir()),[])
        self.no_scientific_rerun.assert_not_called()

    def test_metadata_publication_failure_retains_unpromoted_model_orphan(self):
        self.prepare();actual_link=protect.os.link
        def link(source,destination,*args,**kwargs):
            if str(destination).endswith('.pt.json'):raise OSError('synthetic metadata publication failure')
            return actual_link(source,destination,*args,**kwargs)
        with patch.object(protect.os,'link',side_effect=link),self.assertRaises(OSError):self.publish()
        destination=Path(self.job['destination']);model=destination/'synthetic-winner.pt'
        self.assertTrue(model.exists());self.assertEqual(protect.digest(model),self.fixture.candidate['sha256'])
        self.assertEqual(model.stat().st_nlink,1);self.assertFalse(model.with_suffix('.pt.json').exists())
        self.assertFalse(list(destination.glob('*.partial')))
        self.no_scientific_rerun.assert_not_called()
