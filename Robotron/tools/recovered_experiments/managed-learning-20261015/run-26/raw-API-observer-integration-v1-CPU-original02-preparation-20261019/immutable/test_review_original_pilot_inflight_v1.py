"""CPU-only closed-evidence review tests; no real pilot or GPU work."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import review_original_pilot_inflight_v1 as review

GAME=review.GAME
PREP=GAME/'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018'


def prior_invalid_runtime(reader):
    old=PREP/'future-capacity32-runtime-pilot-preparation-20261019'
    prior = {key:reader.pin(old/relative) for key,relative in {
        'native_owner':'pilot-root-execution/root-original-live-owner.json',
        'outer_owner':'outer-controller-execution/root-original-live-owner.json',
        'native_closure':'pilot-root-execution/native-terminal-archive/root-original-result-and-owned-release.json',
        'outer_closure':'outer-controller-execution/native-terminal-archive/root-original-result-and-owned-release.json',
        'controller_result':'pilot-root-execution/root-controller-result.json',
        'original_review_attempt':'pilot-root-execution/root-original-independent-review-attempt.json',
        'source_diagnostic':'exposure-guard-source-diagnostic-original02-20261019/CPU-report.json'}.items()}

    prior.update(
        score_carry_CPU_readback=reader.pin(GAME/'logs/managed-learning-20261015/run-26/large-score-carry-CPU-root-readback-original02-20261019/root-readback.json'),
        corrected_source_package=reader.pin(GAME/'tools/eval_capacity_proposal/profile05/runtime-source-package.json'),
        corrected_parent_package=reader.pin(GAME/'tools/eval_capacity_proposal/profile03/runtime-source-package.json'),
        preceding_score_tear_invalid_study=reader.pin(PREP/'capacity32-confirmed1059-inflight-v1-preparation-20261019/large-score-tear-terminal-readback-20261019/root-readback.json'))
    prior.update(
        prior_nonfinite_runtime=reader.pin(PREP/'capacity32-confirmed1059-score-carry-v1-preparation-20261019/nonfinite-snapshot-terminal-readback-20261019/root-readback.json'),
        original_nonfinite_reproduction=reader.pin(GAME/'logs/managed-learning-20261015/run-26/nonfinite-observer-storage-CPU-original01-preparation-20261019/CPU-report.json'),
        raw_API_witness_source=reader.pin(GAME/'tools/eval_capacity_proposal/raw_api_witness_v1.py'),
        raw_API_witness_CPU=reader.pin(GAME/'logs/managed-learning-20261015/run-26/raw-API-witness-v1-CPU-original01-preparation-20261019/CPU-report.json'),
        raw_API_witness_CPU_closure=reader.pin(GAME/'logs/managed-learning-20261015/run-26/raw-API-witness-v1-CPU-original01-preparation-20261019/execution/root-original-result-and-owned-release.json'))
    return prior


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads((PREP/'capacity32-confirmed1059-raw-API-v1-preparation-20261019/planned-pilot.json').read_bytes())
        self.package=json.loads(Path(self.plan['source_package']['path']).read_bytes())
        self.receipt=dict(job=copy.deepcopy(self.plan['job']),label=self.plan['job']['label'],source_checkpoint_path=self.plan['job']['checkpoint'],
            checkpoint_sha256=self.plan['checkpoint']['sha256'],checkpoint_path=str(Path(self.plan['job']['directory'])/'checkpoint.pt'),
            start_ts=100,close_ts=3700,elapsed_s=3800,ended_unix_s=3900,timeout_snapshot_unix_s=3899,runtime=dict(device='cuda',
            cuda_visible_devices=self.plan['job']['gpu_uuid'],gpu_name='NVIDIA RTX PRO 2000 Blackwell',compute_capability=[12,0]),
            source_hashes={key:self.package['files'][key] for key in review.SOURCE_FILES})
        self.receipt['ended_source_hashes']=dict(self.receipt['source_hashes'])

    def test_exact_prepared_job_and_loaded_sources_pass_without_mutation(self):
        before=copy.deepcopy(self.receipt);review.validate_scope(self.plan,self.receipt,self.package)
        self.assertEqual(before,self.receipt)

    def test_changed_job_checkpoint_GPU_window_or_source_fails(self):
        original=copy.deepcopy(self.receipt)
        for change in ('actor','epsilon','checkpoint','GPU','window','deadline','source','copy'):
            data=copy.deepcopy(original)
            if change=='actor':data['job']['actors']=16
            elif change=='epsilon':data['job']['epsilon']=.1
            elif change=='checkpoint':data['checkpoint_sha256']='0'*64
            elif change=='GPU':data['runtime']['cuda_visible_devices']='GPU-main'
            elif change=='window':data['close_ts']+=1
            elif change=='deadline':data['elapsed_s']=float('nan')
            elif change=='copy':data['checkpoint_path']=data['source_checkpoint_path']
            else:data['source_hashes']['Scripts/main.lua']='0'*64
            with self.subTest(change=change),self.assertRaises(ValueError):review.validate_scope(self.plan,data,self.package)

    def test_duration_units_reject_missing_or_ambiguous_values(self):
        self.assertEqual(review.duration_seconds('1h 25min'),5100)
        self.assertEqual(review.duration_seconds('12s'),12)
        for text in ('infinity','',' ','-1s','1e3s','1m','NaNs'):
            with self.subTest(text=text),self.assertRaises(ValueError):review.duration_seconds(text)


class ClosureTests(unittest.TestCase):
    def setUp(self):self.reader=review.protector()
    def read(self,entry,as_json=True):return self.reader.read_pin(entry,as_json=as_json)

    def test_actual_original_C1_audit_closure_and_honest_timer_GC_are_read_back(self):
        control=json.loads((PREP/'audit-bindings-reviewed3/leg02-controller/root-original-result-and-owned-release.json').read_bytes())
        fields=review.archived_closure(control,control['original'],self.read,exit_zero=True)
        self.assertEqual(fields['ExecMainStatus'],'0')

    def test_actual_failed_reference_audit_can_only_be_a_preserved_predecessor(self):
        control=json.loads((PREP/'audit-bindings/leg01-controller/root-original-result-and-owned-release.json').read_bytes())
        self.assertEqual(review.archived_closure(control,control['original'],self.read,exit_zero=False)['ExecMainStatus'],'2')
        with self.assertRaises(ValueError):review.archived_closure(control,control['original'],self.read,exit_zero=True)

    def test_incomplete_release_retry_unknown_exit_or_missing_descriptor_fails(self):
        original=json.loads((PREP/'audit-bindings-reviewed3/leg02-controller/root-original-result-and-owned-release.json').read_bytes())
        for change in ('exit','bool','release','retry','descriptor','identity','timeout'):
            control=copy.deepcopy(original)
            if change=='exit':control['original_exit']=1
            elif change=='bool':control['original_exit']=False
            elif change=='release':control['owned_release'][0]['confirmed_absent']=False
            elif change=='retry':control['payload_retried']=True
            elif change=='descriptor':control['full_original_archives'].pop()
            elif change=='identity':control['original']['invocation_id']='0'*32
            else:control['full_original_archives'][0]['timed_out']=True
            with self.subTest(change=change),self.assertRaises(ValueError):
                review.archived_closure(control,control['original'],self.read,exit_zero=True)


class MainObservationTests(unittest.TestCase):
    def setUp(self):
        template_path=PREP.parent/'post-confirmed-scoring-next8M-original01-root-preparation-20261018/job.json'
        self.binding=json.loads(template_path.read_bytes())
        self.baseline=json.loads(Path(self.binding['baseline_API']['path']).read_bytes())
        self.binding['baseline_API_value']=self.baseline
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        source=Path(self.temp.name)/'main_guard.py';source.write_bytes((GAME/'tools/post_continuity_window.py').read_bytes());source.chmod(0o444)
        self.window=review.protector().checked_module('_test_main_guard_'+str(time.time_ns()),
            review.protector().pin(source))
        self.manifest=dict(schema='robotron-main192-pilot-observations-v1',status='PASS',configuration_changed=False,
            main_owner=self.binding['owner'],accounting_policy='single_inflight_optimizer_v1',rejected_observations=[])
        held=hashlib.sha256(json.dumps(self.binding['held_hashes'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.samples=[]
        for index in range(3):
            unix=1_792_400_000+index*10;api=copy.deepcopy(self.baseline)
            api['ts']=unix;api['pipeline_snapshot_age_s']=0
            for key in ('frame_count','learner_frame_count','optimized_samples','training_steps'):api[key]+=index*100
            self.samples.append(dict(monotonic_s=1000+index*10,unix_s=unix,main_owner=self.binding['owner'],
                original192_actors_verified=True,held_hashes_sha256=held,API=api,
                autosave=dict(mtime_ns=(unix-5)*10**9,bytes=275000000,age_s=5)))

    def validate(self):review.validate_main_samples(self.binding,self.manifest,self.samples,1005,1015,self.window.healthy)

    def test_real_guard_checks_cover_original_birth_to_exit(self):self.validate()

    def test_gap_missing_coverage_or_stale_checkpoint_fails(self):
        original=copy.deepcopy(self.samples)
        for change in ('gap','late_start','early_end','stale','future','zero_size'):
            self.samples=copy.deepcopy(original)
            if change=='gap':self.samples[-1]['monotonic_s']=1041
            elif change=='late_start':self.samples[0]['monotonic_s']=1006
            elif change=='early_end':self.samples[-1]['monotonic_s']=1014
            elif change=='stale':self.samples[1]['autosave']['age_s']=361
            elif change=='future':self.samples[1]['autosave']['age_s']=-1
            else:self.samples[1]['autosave']['bytes']=0
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate()

    def test_changed_owner_actors_sources_exposure_or_pipeline_fails(self):
        original=copy.deepcopy(self.samples)
        for change in ('owner','actors','source','epoch','pipeline','counter','outcome','API'):
            self.samples=copy.deepcopy(original);sample=self.samples[1]
            if change=='owner':sample['main_owner']=dict(sample['main_owner'],pid=1)
            elif change=='actors':sample['original192_actors_verified']=False
            elif change=='source':sample['held_hashes_sha256']='0'*64
            elif change=='epoch':sample['API']['host_pipeline']['learning_exposure']['optimizer']['epoch']+=1
            elif change=='pipeline':sample['API']['host_pipeline']['inference']['errors']=1
            elif change=='counter':sample['API']['training_steps']=0
            elif change=='outcome':sample['API']['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable']=1
            else:sample['API']['ts']-=10
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate()


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.status=dict(state='finished',plan_sha256=review.CURRENT_PLAN_SHA,outcome='invalid')
        self.decision=dict(schema='robotron-quality-disposition-before-capacity-pilot-v1',plan_sha256=review.CURRENT_PLAN_SHA,
            native_outcome='invalid',qualified_improvement=False,scientific_outcome_changed=False,
            protected_winner_metadata=None,winner_adopted_before_pilot=False)

    def test_failed_quality_is_preserved_for_an_independent_runtime_pilot(self):
        review.validate_preceding_decision(self.status,self.decision,None,None)

    def test_live_or_rewritten_outcome_is_never_accepted(self):
        for change in ('live','outcome','reinterpret','promotion'):
            status=copy.deepcopy(self.status);decision=copy.deepcopy(self.decision)
            if change=='live':status['state']='running'
            elif change=='outcome':decision['native_outcome']='qualified_improvement'
            elif change=='reinterpret':decision['scientific_outcome_changed']=True
            else:decision['winner_adopted_before_pilot']=True
            with self.subTest(change=change),self.assertRaises(ValueError):
                review.validate_preceding_decision(status,decision,None,None)

    def test_qualified_winner_requires_exact_protection_and_adoption(self):
        self.status['outcome']='qualified_improvement'
        self.decision.update(native_outcome='qualified_improvement',qualified_improvement=True,
            winner_adopted_before_pilot=True,protected_winner_job=dict(path='/synthetic/job',sha256=
                'f40c6c6d41f846fbab6238a545719453debd3e1cf2b7e9aaf0497dd6430a460c'))
        path=str(GAME/'models_dqn/managed-incumbents/synthetic.pt')
        metadata=dict(schema='robotron-confirmed-terminal-protected-winner-polling-recovery-v1',
            assessment=dict(qualified_improvement=True),checkpoints=dict(candidate=dict(sha256=review.CURRENT_CANDIDATE_SHA)),
            root_protection_job=self.decision['protected_winner_job'],protected_checkpoint=path)
        incumbent=dict(sha256=review.CURRENT_CANDIDATE_SHA,checkpoint=path)
        review.validate_preceding_decision(self.status,self.decision,metadata,incumbent)
        for bad_meta,bad_incumbent in ((None,incumbent),(metadata,None),
                (dict(metadata,checkpoints=dict(candidate=dict(sha256='0'*64))),incumbent)):
            with self.assertRaises(ValueError):review.validate_preceding_decision(self.status,self.decision,bad_meta,bad_incumbent)


class EarlyGuardTests(unittest.TestCase):
    def test_missing_original_closed_context_cannot_query_or_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp);job=dict(closed_context_path=str(directory/'missing.json'),output=str(directory/'output'))
            with patch.object(review.subprocess,'run',side_effect=AssertionError('No GPU query allowed')) as query,\
                 patch.object(review,'verify_cleanup',side_effect=AssertionError('No lease query allowed')) as cleanup,\
                 self.assertRaises(FileNotFoundError):review.review(job,{},review.protector())
            query.assert_not_called();cleanup.assert_not_called();self.assertFalse((directory/'output').exists())


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.lease=Path(self.temp.name)/'private.lock';self.lease.touch()
        self.owner=dict(pid=9_000_000,starttime_ticks=1,observed_live=True,cgroup='/synthetic-pilot-cgroup')
        self.actors={str(slot):dict(pid=9_000_001+slot,starttime_ticks=2,observed_live=True) for slot in review.SLOTS}

    def verify(self,stdout='',returncode=0,network=None):
        original=Path.read_text
        def text(path,*args,**kwargs):
            if str(path) in ('/proc/net/tcp','/proc/net/tcp6'):
                return 'header\n'+(network or '')
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',text),patch.object(review.fcntl,'flock') as lock,\
             patch.object(review.subprocess,'run',return_value=SimpleNamespace(returncode=returncode,stdout=stdout)) as query:
            review.verify_cleanup(self.owner,self.actors,'GPU-synthetic',self.lease)
            query.assert_called_once();self.assertEqual(lock.call_count,2)

    def test_no_processes_port_or_GPU_users_accepts_mocked_cleanup(self):self.verify()

    def test_missing_or_unobserved_actor_identity_fails_before_GPU_query(self):
        for change in ('missing','unobserved','duplicate'):
            original=copy.deepcopy(self.actors)
            if change=='missing':self.actors.pop('4127')
            elif change=='unobserved':self.actors['4127']['observed_live']=False
            else:self.actors['4127']['pid']=self.actors['4126']['pid']
            with self.subTest(change=change),self.assertRaises(ValueError):self.verify()
            self.actors=original

    def test_GPU_occupancy_failure_or_listening_port_is_rejected(self):
        for options in (dict(stdout='1234\n'),dict(returncode=1),
                        dict(network='0: 0100007F:270F 00000000:0000 0A\n')):
            with self.subTest(options=options),self.assertRaises(ValueError):self.verify(**options)

    def test_held_lease_is_not_adopted_signaled_or_replaced(self):
        original=Path.read_text
        def text(path,*args,**kwargs):
            return 'header\n' if str(path) in ('/proc/net/tcp','/proc/net/tcp6') else original(path,*args,**kwargs)
        with patch.object(Path,'read_text',text),patch.object(review.fcntl,'flock',side_effect=BlockingIOError),\
             patch.object(review.subprocess,'run') as query,self.assertRaises(BlockingIOError):
            review.verify_cleanup(self.owner,self.actors,'GPU-synthetic',self.lease)
        query.assert_not_called();self.assertTrue(self.lease.exists())


class SyntheticCompleteReviewTests(unittest.TestCase):
    """Run the full reviewer with synthetic closed artifacts and mocked OS state."""
    def test_whole_review_joins_sources_journals_logs_main_guard_and_closure(self):
        # Other retained server tests import Torch on CPU. The real reviewer
        # runs in a new stdlib process, so exercise that same import boundary.
        script='import sys\n'
        for path in (GAME/'tools/eval_capacity_proposal/profile03',GAME/'tools/eval_capacity_proposal',
                     GAME/'tools/confirmed_game_boundary_proposal'):
            script+='sys.path.insert(0,'+repr(str(path))+')\n'
        script+='sys.path.insert(0,'+repr(str(Path(__file__).parent))+')\n'
        script+='from test_review_original_pilot_inflight_v1 import SyntheticCompleteReviewTests\n'
        script+='assert "torch" not in sys.modules\n'
        script+='for archived_memory_limit, expected_valid in ((12<<30,True),(8<<30,False),(16<<30,False)):\n test=SyntheticCompleteReviewTests()\n try:\n  test.run_synthetic_review(archived_memory_limit,expected_valid)\n finally:\n  test.doCleanups()\n'
        script+='assert "torch" not in sys.modules\nprint("FRESH_METADATA_REVIEW_PASS_NO_TORCH")\n'
        result=subprocess.run([sys.executable,'-Xgil=0','-I','-B','-c',script],capture_output=True,text=True,timeout=40)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('FRESH_METADATA_REVIEW_PASS_NO_TORCH',result.stdout)

    def run_synthetic_review(self, archived_memory_limit=12<<30, expected_valid=True):
        from test_audit_pilot_evidence import EvidenceTests
        fixture=EvidenceTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        root=fixture.root;reader=review.protector();counter=[0]
        def put(path,value):
            path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
            raw=value if isinstance(value,bytes) else (json.dumps(value)+'\n').encode()
            path.write_bytes(raw);path.chmod(0o444);return reader.pin(path)
        def native_closure(owner,name):
            area=root/name;area.mkdir();records=[]
            fields=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],MainPID='0',
                ExecMainPID=str(owner['pid']),ExecMainCode='1',ExecMainStatus='0',NRestarts='0',Result='success',
                RuntimeMaxUSec='1h 45min',MemoryMax=str(archived_memory_limit),CPUQuotaPerSecUSec='12s',Restart='no',
                SendSIGKILL='no',ExecMainStartTimestampMonotonic='1000000000',ExecMainExitTimestampMonotonic='4901000000')
            for kind,unit in (('service',owner['unit']),('timer',owner['timer'])):
                for action in ('show','cat','journal'):
                    argv=['journalctl','--user','--unit',unit,'--no-pager'] if action=='journal' else ['systemctl','--user',action,unit]
                    content=('\n'.join(key+'='+value for key,value in fields.items())+'\n') if kind=='service' and action=='show' else ''
                    if kind=='timer' and action=='show':content='Id='+unit+'\nLoadState=not-found\n'
                    records.append(dict(argv=argv,exit=1 if kind=='timer' and action=='cat' else 0,timed_out=False,
                        stdout=put(area/(kind+'-'+action+'.out'),content.encode()),stderr=put(area/(kind+'-'+action+'.err'),b'')))
            return put(area/'closure.json',dict(original=owner,original_exit=0,lifecycle_complete=True,
                unit_released=True,original_archived_before_release=True,payload_retried=False,native_archives=records,
                owned_release=[dict(unit=unit,confirmed_absent=True) for unit in (owner['unit'],owner['timer'])]))
        plan=json.loads((PREP/'capacity32-confirmed1059-raw-API-v1-preparation-20261019/planned-pilot.json').read_bytes())
        package=json.loads(Path(plan['source_package']['path']).read_bytes());data=fixture.data
        protected=root/'protected.pt';protected_entry=put(protected,b'synthetic checkpoint bytes; no numerical model')
        checkpoint_entry=put(root/'checkpoint.pt',protected.read_bytes())
        plan['checkpoint']=protected_entry;plan['job'].update(checkpoint=str(protected),directory=str(root))
        data.update(job=copy.deepcopy(plan['job']),label=plan['job']['label'],checkpoint_path=str(root/'checkpoint.pt'),
            source_checkpoint_path=str(protected),checkpoint_sha256=checkpoint_entry['sha256'],
            start_ts=1_792_400_101,close_ts=1_792_403_701,ended_unix_s=1_792_403_900,
            elapsed_s=3800,timeout_snapshot_unix_s=1_792_403_898,
            runtime=dict(device='cuda',cuda_visible_devices=plan['job']['gpu_uuid'],
                gpu_name='NVIDIA RTX PRO 2000 Blackwell',compute_capability=[12,0]))
        data['source_hashes']={name:package['files'][name] for name in review.SOURCE_FILES}
        data['ended_source_hashes']=dict(data['source_hashes'])
        for row in data['rows']:
            row['experiment']=data['label']
            row['start_unix_s']+=1_792_400_001;row['end_unix_s']+=1_792_400_001
            for key in ('start_context','end_context'):row[key]['experiment']=data['label']
            successor=data['terminal_successors'][row['journal_game_id']]
            successor['start_unix_s']=row['end_unix_s']+.01
        row=data['rows'][-1];row['end_unix_s']=1_792_403_800;row['duration_s']=row['end_unix_s']-row['start_unix_s']
        data['terminal_successors'][row['journal_game_id']]['start_unix_s']=row['end_unix_s']+.01
        data['cohort'].update(experiment=data['label'],start_ts=data['start_ts'],close_ts=data['close_ts'])
        fixture.write_originals()
        boot_path=Path(plan['job']['boot_assets'])/'manifest.json'
        boot=json.loads(boot_path.read_bytes())
        boot.update(directory=str(boot_path.parent),manifest_path=str(boot_path),manifest_sha256=review.digest(boot_path))
        data['boot_assets']=boot
        boot_hash=review.digest(Path(plan['job']['boot_assets'])/'manifest.json')
        data['boot_restores']={str(slot):dict(identity=boot['identity'],files=boot['files'],manifest_sha256=boot_hash,
            restored_paths={name:str(root/'actors'/str(slot)/name) for name in boot['files']}) for slot in review.SLOTS}
        library=root/'socket-wait.so';put(library,b'synthetic socket-wait bytes; no shared library loaded')
        data['socket_wait'].update(library=str(library),sha256=review.digest(library))
        put(root/'receipt.json',data);put(root/'plan.json',dict(plan['job'],checkpoint_sha256=data['checkpoint_sha256']))
        plan_entry=put(root/'prepared-plan.json',plan)
        ready_entry=reader.pin(PREP/'future-capacity32-runtime-pilot-preparation-20261019/current-observer-reviewed4-readiness-amendment.json')
        ready=reader.read_pin(ready_entry)
        owner=dict(unit=plan['unit'],timer=plan['timer'],pid=9_000_000,starttime_ticks=1,observed_live=True,
            invocation_id='a'*32,timer_invocation_id='b'*32,cgroup='/synthetic-capacity-pilot')
        context=dict(schema='robotron-capacity-pilot-closed-context-v1',pilot_owner=put(root/'owner.json',owner),
            pilot_closure=native_closure(owner,'pilot-closure'),
            preceding_native_closure=native_closure(ready['current_native_owner'],'prior-native'),
            preceding_observer_closure=native_closure(ready['current_review_observer'],'prior-observer'))
        status_entry=put(root/'prior-status.json',dict(state='finished',plan_sha256=review.CURRENT_PLAN_SHA,outcome='not_improved'))
        context['preceding_quality_decision']=put(root/'decision.json',dict(schema='robotron-quality-disposition-before-capacity-pilot-v1',
            plan_sha256=review.CURRENT_PLAN_SHA,native_outcome='not_improved',qualified_improvement=False,
            scientific_outcome_changed=False,native_status_sha256=status_entry['sha256'],protected_winner_metadata=None,
            winner_adopted_before_pilot=False))
        context['incumbent_before_pilot']=put(root/'incumbent.json',dict(incumbent=dict(sha256=plan['checkpoint']['sha256'])))
        context['actor_identities']=put(root/'actors.json',{str(slot):dict(pid=data['socket_wait']['actors'][str(slot)]['pid'],
            starttime_ticks=2,observed_live=True) for slot in review.SLOTS})
        template_entry=reader.pin(PREP.parent/'post-confirmed-scoring-next8M-original01-root-preparation-20261018/job.json')
        binding=reader.read_pin(template_entry);slot=str(GAME/'models_dqn/managed_save.request.json.completed')
        binding['held_hashes'][slot]='acda2ce69c461834f4e67de18d32a215d36f98739180801608b8bb4095ed81b5'
        def api(unix,index):
            counts=dict(attempts_started=1000+index,outcomes_recorded=1000+index,applied=1000+index,amp_skipped=0,unavailable=0)
            exposure=dict(optimizer=dict(schema='robotron-optimizer-exposure-v1',enabled=True,available=True,
                process_id=binding['owner']['pid'],instance_monotonic_ns=10,epoch=1,
                total=dict(counts),since_epoch=dict(counts),unclassified_started_total=0),
                replay=dict(enabled=True,available=True,process_id=binding['owner']['pid'],
                instance_monotonic_ns=11,epoch=1,accepted_learner_total=1000+index))
            pipe=dict(schema='robotron-host-pipeline-v1',available=True,generation=0,learning_exposure=exposure)
            pipe.update({name:dict(errors=0) for name in ('inference','actor_refresh','target_refresh','learner_priority')})
            value=dict(client_count=192,training_enabled=True,measurement_active=False,managed_experiment=binding['experiment'],
                lr=1.25e-5,pipeline_read_error='',bank_persistence_read_error='',ts=unix,pipeline_snapshot_age_s=0,
                host_pipeline=pipe,bank_persistence=dict(write_failures=0))
            value.update({key:1000+index for key in ('frame_count','learner_frame_count','optimized_samples','training_steps')})
            return value
        baseline=api(1_792_400_000,0);binding['baseline_API']=put(root/'baseline.json',baseline)
        context['main_binding']=put(root/'main-binding.json',binding)
        held=hashlib.sha256(json.dumps(binding['held_hashes'],sort_keys=True,separators=(',',':')).encode()).hexdigest();samples=[]
        for index,monotonic in enumerate(range(999,4920,20)):
            unix=1_792_399_000+monotonic
            samples.append(put(root/'main-samples'/f'{index:03d}.json',dict(monotonic_s=monotonic,unix_s=unix,
                main_owner=binding['owner'],original192_actors_verified=True,held_hashes_sha256=held,**review.raw_witness_module().witness_fields(api(unix,index),put(root/'API-wires'/f'{index:03d}.raw',json.dumps(api(unix,index)).encode())),
                autosave=dict(mtime_ns=(unix-5)*10**9,bytes=275000000,age_s=5))))
        context['main_observations']=put(root/'main-manifest.json',dict(schema='robotron-main192-pilot-observations-v1',status='PASS',
            configuration_changed=False,main_owner=binding['owner'],samples=samples,API_witness_format=review.raw_witness_module().FORMAT,accounting_policy='single_inflight_optimizer_v1',rejected_observations=[]))
        console=root/'console.log';put(console,('Startup\n'+
            "[WARN] Robotron expert unavailable (No module named 'v3'); expert guidance disabled.\n").encode())
        context['console_path']=str(console);context_entry=put(root/'closed-context.json',context)
        guard=root/'main_guard.py';guard_entry=put(guard,(GAME/'tools/post_continuity_window.py').read_bytes())
        lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');identity=lease.lstat()
        job=dict(schema='robotron-original-capacity-pilot-review-job-v1',closed_context_path=context_entry['path'],
            output=str(root/'review'),runtime_paths={key:value['path'] for key,value in context.items() if isinstance(value,dict)},
            console_path=str(console),pilot_plan=plan_entry,readiness_amendment=ready_entry,
            preceding_campaign_status_path=status_entry['path'],evidence_helpers_selection=reader.pin(Path(__file__).parent/'synthetic-helper-selection.json'),
            main_hold_template=template_entry,main_guard_source=guard_entry,expected_completed_slot_sha256=binding['held_hashes'][slot],
            lease_path=str(lease),lease_identity=dict(device=identity.st_dev,inode=identity.st_ino))
        job['prior_invalid_runtime']=prior_invalid_runtime(reader)
        job_entry=put(root/'job.json',job)
        real_checked=reader.checked_module;main_checks=Mock()
        def checked(name,entry):
            module=real_checked(name,entry)
            if entry==guard_entry:module.owner_and_files=main_checks
            return module
        original_exists=Path.exists
        old_pids={ready[key]['pid'] for key in ('current_native_owner','current_review_observer')}
        def exists(path):
            if path.parent==Path('/proc') and path.name in {str(pid) for pid in old_pids}:return False
            return original_exists(path)
        with patch.object(review,'PILOT_PLAN_SHA',plan_entry['sha256']),patch.object(reader,'checked_module',side_effect=checked),\
             patch.object(Path,'exists',exists),patch.object(review,'verify_cleanup') as cleanup,\
             patch.object(review.urllib.request,'urlopen',side_effect=lambda *args,**kwargs:io.BytesIO(json.dumps(api(time.time(),999)).encode())):
            result=review.review(job,job_entry,reader)
        if expected_valid:
            self.assertTrue(result['valid'],result.get('error'));self.assertEqual(result['statistics']['count'],50)
            cleanup.assert_called_once();main_checks.assert_called_once()
        else:
            self.assertFalse(result['valid']);self.assertIn('Original resource/restart policy differs',result.get('error',''))
            cleanup.assert_not_called();main_checks.assert_not_called()
        self.assertFalse(result['quality_qualified']);self.assertFalse(result['capacity_speedup_verified'])


if __name__=='__main__':unittest.main()
