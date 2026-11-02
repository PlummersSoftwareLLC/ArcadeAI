"""Authored metadata guards; UNEXECUTED by author, no application imports."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('_future_hot_window_metadata_guards',HERE/'hot_window_observer.py')
helper=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def fake_pin(name):
    return dict(path='/synthetic/unactivated/'+name,sha256='a'*64,bytes=100)


def clock(elapsed=0):
    return dict(boot_id='synthetic-boot',monotonic_s=1000+elapsed,wall_s=100000+elapsed)


def api_at(elapsed=0,*,learner=0,fleet=0,dqn=0,epsilon=0,expert=0,evaluate=0,
           unattributed=0,applied=0,skipped=0,pending=0,unavailable=0,logical_steps=0,logical_samples=0):
    categories=dict(dqn=1000000+dqn,epsilon=200000+epsilon,expert=250000+expert,
                    eval=100000+evaluate,unattributed=10000+unattributed)
    total=dict(applied=100+applied,amp_skipped=5+skipped,unavailable=unavailable)
    total['outcomes_recorded']=sum(total.values())
    total['attempts_started']=total['outcomes_recorded']+pending
    identity=dict(process_id=123,instance_monotonic_ns=99999,epoch=2,epoch_reason='synthetic_existing_epoch')
    optimizer=dict(identity,schema='robotron-optimizer-exposure-v1',enabled=True,
        available=total['outcomes_recorded']>0 and unavailable==0 and pending==0,total=total,
        since_epoch=copy.deepcopy(total),unclassified_started_total=pending)
    replay=dict(identity,schema='robotron-replay-insert-exposure-v1',enabled=True,available=True,
        accepted_total=sum(categories.values()),accepted_learner_total=categories['dqn']+categories['epsilon'],
        accepted_by_source_total=categories)
    # Genuine API key names; deliberately no training/measurement_mode aliases.
    return dict(training_steps=1000+logical_steps,optimized_samples=4096000+logical_samples,
        frame_count=500000000+fleet,learner_frame_count=300000000+learner,ts=100000+elapsed,
        client_count=192,training_enabled=True,measurement_active=False,managed_experiment='synthetic_future_lr25',
        lr=1.25e-5,pipeline_snapshot_age_s=0.25,pipeline_read_error='',grad_norm=float('nan'),
        host_pipeline=dict(learning_exposure=dict(optimizer=optimizer,replay=replay)))


def job_at(cutoff=100):
    record=fake_pin('current-CE-record.json');record['sha256']=helper.FOUNDER
    return dict(schema=helper.SCHEMA,experiment='synthetic_future_lr25',recipe=copy.deepcopy(helper.RECIPE),
        owner=dict(pid=123,starttime_ticks=789,unit='synthetic-trainer.service',invocation_id='b'*32,
                   cgroup='/synthetic/trainer.service'),
        current_phase=dict(record=record,boot_checkpoint=fake_pin('historical-boot.pt'),
            boot_verification=fake_pin('historical-boot-CPU.json'),
            expected=dict(metric='ce',valid=True,founder_phase_record_sha256=helper.FOUNDER)),
        proofs={key:fake_pin(key+'.json') for key in ('root_precommit','control_after','entry_CPU','barrier')},
        barrier_completed_clock=clock(-1),baseline=dict(api=fake_pin('actual-raw-post-barrier-B.json'),observed_clock=clock()),
        policy=dict(helper.POLICY,cutoff_s=cutoff))


def observe(observer,api=None,elapsed=1,*,owner=None,evidence=None):
    return observer.observe(api_at(elapsed) if api is None else api,
        observer.job['owner'] if owner is None else owner,dict(ok=True) if evidence is None else evidence,clock(elapsed))


def eligible(elapsed=1,**extra):
    return api_at(elapsed,learner=8000000,dqn=5500000,epsilon=500000,applied=10,**extra)


class MemoryPublisher:
    """Synthetic callback, not a filesystem publisher or fsync proof."""
    def __init__(self):self.values={};self.calls=[]
    def __call__(self,path,value):
        path=str(path)
        if path in self.values:raise ValueError('create-only synthetic duplicate')
        self.calls.append(path);self.values[path]=copy.deepcopy(value)
        raw=helper.encoded(value)
        return dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))


def emit_pair(event,job,completed=2):
    return helper.durable_event(event,job,Path('/synthetic/new-journal'),publish=MemoryPublisher(),get_clock=lambda:clock(completed))


class HotWindowContracts(unittest.TestCase):
    def test_default_plan_has_no_reads_callbacks_or_actual_baseline(self):
        with patch('builtins.open',side_effect=AssertionError('no reads')), \
                patch.object(Path,'read_bytes',side_effect=AssertionError('no reads')), \
                patch.object(helper,'HorizonObserver',side_effect=AssertionError('no observer')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(helper.main(),0)
        value=json.loads(output.getvalue())
        self.assertEqual(value['status'],'PLAN_ONLY')
        self.assertIsNone(value['policy']['cutoff_s']);self.assertIsNone(value['future_baseline'])
        self.assertFalse(value['selected']);self.assertFalse(value['actions'])

    def test_genuine_API_keys_nonzero_B_and_post_barrier_bound_are_required(self):
        baseline=api_at()
        self.assertNotIn('training',baseline);self.assertNotIn('measurement_mode',baseline)
        observer=helper.HorizonObserver(job_at(),baseline)
        self.assertGreater(observer.baseline['accepted'],0)
        self.assertGreater(observer.baseline['optimizer']['applied'],0)
        self.assertTrue(math_is_nan(observer.baseline_raw['grad_norm']))
        wrong=[]
        value=api_at();value['ts']-=0.8;wrong.append(value) # ts-age falls before barrier.
        value=api_at();value['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable']=1;wrong.append(value)
        wrong.append(api_at(pending=1))
        wrong.append(api_at(applied=-100,skipped=-5)) # No process/epoch outcomes cannot be B.
        wrong.append(api_at(dqn=-1000000,epsilon=-200000,expert=-250000,
                            evaluate=-100000,unattributed=-10000)) # Genuine partitions, zero replay B.
        value=api_at();value['lr']=2.5e-5;wrong.append(value)
        value=api_at();value['measurement_active']=True;wrong.append(value)
        value=api_at();value['training_enabled']=False;wrong.append(value)
        value=api_at();value['managed_experiment']='old_experiment';wrong.append(value)
        for index,value in enumerate(wrong):
            with self.subTest(index=index),self.assertRaises((ValueError,KeyError)):
                helper.HorizonObserver(job_at(),value)
        for key in helper.CLOCKS:
            value=api_at();value[key]=0
            with self.subTest(clock=key),self.assertRaises(ValueError):helper.HorizonObserver(job_at(),value)
        value=job_at();value['baseline']['observed_clock']=clock(-2)
        with self.assertRaises(ValueError):helper.HorizonObserver(value,api_at())

    def test_exact_recipe_phase_proof_and_future_policy_bindings(self):
        changes=[('recipe','batch_size',2048),('recipe','learning_control_lr_scale',0.5),
            ('recipe','scheduled_lr',2.5e-5),('recipe','priority_metric','kl'),('recipe','max_samples_per_frame',9),
            ('policy','learner_frames',7999999),('policy','learner_accepted',5999999),('policy','cutoff_s',None)]
        for group,key,value in changes:
            job=job_at();job[group][key]=value
            with self.subTest(group=group,key=key),self.assertRaises((ValueError,TypeError)):
                helper.HorizonObserver(job,api_at())
        for mutate in (lambda j:j['current_phase']['record'].update(sha256='c'*64),
                       lambda j:j['proofs']['control_after'].update(sha256=None),
                       lambda j:j.update(start_request=clock()),
                       lambda j:j['baseline']['api'].update(path='../wrong'),
                       lambda j:j['barrier_completed_clock'].update(boot_id='other-boot')):
            job=job_at();mutate(job)
            with self.assertRaises((ValueError,KeyError,TypeError)):helper.HorizonObserver(job,api_at())

    def test_all_deltas_share_B_and_AMP_denominator_excludes_pending(self):
        observer=helper.HorizonObserver(job_at(),api_at())
        event=observe(observer,api_at(1,learner=100,fleet=200,dqn=30,epsilon=10,expert=20,
            evaluate=9,unattributed=2,applied=3,skipped=2,pending=1,logical_steps=7,logical_samples=12345))
        self.assertEqual(event['state'],'CONTINUE');p=event['progress']
        self.assertEqual((p['learner_frames'],p['fleet_frames'],p['learner_accepted'],p['physical_accepted']),(100,200,40,71))
        self.assertEqual(p['physical_by_source'],dict(dqn=30,epsilon=10,expert=20,eval=9,unattributed=2))
        self.assertEqual((p['logical_steps'],p['logical_samples']),(7,12345))
        self.assertEqual(p['optimizer_delta_from_B'],dict(attempts_started=6,outcomes_recorded=5,applied=3,amp_skipped=2,unavailable=0))
        self.assertEqual((p['optimizer_pending'],p['AMP_classified_denominator'],p['AMP_skip_fraction']),(1,5,0.4))
        self.assertEqual(p['admitted_samples_from_B'],3*4096)
        self.assertEqual(p['admitted_samples_process_total'],103*4096)
        self.assertNotEqual(p['logical_samples'],p['admitted_samples_from_B'])

    def test_horizon_uses_learner_inserts_only_and_keeps_first_pending1_LATCH(self):
        for current in (api_at(1,learner=7999999,dqn=6000000,applied=1),
                        api_at(1,learner=8000000,dqn=5999999,applied=1),
                        api_at(1,learner=8000000,expert=3000000,evaluate=2000000,unattributed=1000000,applied=1)):
            self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),current)['state'],'CONTINUE')
        observer=helper.HorizonObserver(job_at(),api_at())
        first=observe(observer,eligible(pending=1))
        self.assertEqual(first['state'],'LATCH');self.assertEqual(first['candidate_requests_allowed'],0)
        self.assertEqual(first['progress']['optimizer_pending'],1)
        self.assertEqual(first['progress']['learner_accepted'],6000000)
        first['first_eligible_observation']['learner_frame_count']=0
        later=observer.observe(None,None,{},clock(1000))
        self.assertEqual(later['state'],'LATCH')
        self.assertEqual(later['first_eligible_observation']['learner_frame_count'],308000000)
        self.assertEqual(later['progress']['optimizer_pending'],1)
        self.assertFalse(later['owner_actions_allowed'])

    def test_owner_identity_epoch_unavailable_partition_and_counter_regressions(self):
        for group in ('optimizer','replay'):
            for key in helper.IDENTITY:
                value=api_at(1)
                item=value['host_pipeline']['learning_exposure'][group][key]
                value['host_pipeline']['learning_exposure'][group][key]=item+1 if type(item) is int else 'different'
                with self.subTest(group=group,key=key):
                    self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),value)['state'],'INVALID')
        for value in (api_at(1,unavailable=1),api_at(1,pending=2)):
            self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),value)['state'],'INVALID')
        for key in helper.CLOCKS:
            value=api_at(1);value[key]-=1
            self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),value)['state'],'INVALID')
        value=api_at(1,dqn=-1) # Partition remains valid; monotonic per-source guard must reject.
        self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),value)['state'],'INVALID')
        self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),owner={})['state'],'INVALID')
        self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),evidence={'ok':False})['state'],'INVALID')

    def test_freshness_gap_monotonic_stall_and_cutoff_have_no_owner_ceiling(self):
        observer=helper.HorizonObserver(job_at(),api_at())
        value=api_at(1);value['ts']-=6
        self.assertEqual(observe(observer,value)['state'],'CONTINUE')
        self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),elapsed=30)['state'],'INVALID')
        observer=helper.HorizonObserver(job_at(),api_at())
        self.assertEqual(observe(observer,elapsed=2)['state'],'CONTINUE')
        self.assertEqual(observe(observer,elapsed=1)['state'],'INVALID')
        observer=helper.HorizonObserver(job_at(),api_at())
        for elapsed in (20,40):self.assertEqual(observe(observer,api_at(elapsed,learner=elapsed,dqn=elapsed),elapsed)['state'],'CONTINUE')
        self.assertEqual(observe(observer,api_at(60,learner=60,dqn=60),60)['state'],'INVALID')
        self.assertEqual(observe(helper.HorizonObserver(job_at(10),api_at()),eligible(10),10)['state'],'LATCH')
        self.assertEqual(observe(helper.HorizonObserver(job_at(10),api_at()),eligible(11),11)['state'],'INCOMPLETE')
        self.assertEqual(observe(helper.HorizonObserver(job_at(10),api_at()),api_at(10),10)['state'],'INCOMPLETE')
        self.assertNotIn('ceiling_s',job_at()['policy']);self.assertFalse(hasattr(helper,'ending_deadline'))

    def test_only_timely_original_paired_durability_authorizes_candidate(self):
        job=job_at(10);observer=helper.HorizonObserver(job,api_at())
        event=observe(observer,eligible(9),9);event['sequence']=0
        result=helper.durable_result(event,emit_pair(event,job,10),job)
        self.assertEqual(result['status'],'LATCH_DURABLE');self.assertEqual(result['candidate_requests_allowed'],1)
        self.assertEqual(observer.terminal['candidate_requests_allowed'],0)
        late=helper.durable_result(event,emit_pair(event,job,10.01),job)
        self.assertEqual(late['status'],'LATCH_LATE_DURABILITY');self.assertEqual(late['candidate_requests_allowed'],0)
        self.assertEqual(late['observation']['first_eligible_observation'],event['first_eligible_observation'])
        for change in (lambda p:p['event'].update(sha256='f'*64),
                       lambda p:p['completion'].update(sequence=1),
                       lambda p:p['completion'].update(boot_id='other'),
                       lambda p:p['completion'].update(completed_monotonic_s=1008)):
            pair=emit_pair(event,job,10);change(pair)
            # Recompute the receipt's synthetic publication PIN: the semantic
            # sequence/clock join must reject even a self-consistent JSON hash.
            raw=helper.encoded(pair['completion'])
            pair['durability'].update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
            with self.assertRaises(ValueError):helper.durable_result(event,pair,job)

    def test_terminal_and_failed_emit_are_once_only_and_budgets_are_bounded(self):
        job=job_at();event=observe(helper.HorizonObserver(job,api_at()),eligible());event['sequence']=0
        publisher=MemoryPublisher()
        journal=helper.ReceiptJournal(publish=publisher,get_clock=lambda:clock(2),root=Path('/synthetic/journal'),job=job)
        pair=journal.emit(event)
        self.assertEqual(len(publisher.calls),2)
        self.assertEqual(pair['completion']['event'],pair['event'])
        with self.assertRaises(ValueError):journal.emit(event)
        broken=MemoryPublisher()
        def bad_publish(path,value):
            original=broken(path,value)
            if path.name.startswith('durability-'):raise OSError('synthetic metadata failure')
            return original
        journal=helper.ReceiptJournal(publish=bad_publish,get_clock=lambda:clock(2),root=Path('/synthetic/broken'),job=job)
        with self.assertRaises(OSError):journal.emit(event)
        self.assertEqual(len(broken.calls),2)
        with self.assertRaises(ValueError):journal.emit(event)
        limited=helper.ReceiptJournal(publish=MemoryPublisher(),get_clock=lambda:clock(2),root=Path('/synthetic/limit'),job=job)
        limited.used=helper.JOURNAL_BYTES-4096
        with self.assertRaises(ValueError):limited.emit(event)

    def test_poll_timestamps_after_callbacks_and_preserves_first_publication_failure(self):
        job=job_at(10);order=[];publisher=MemoryPublisher();count={'clock':0}
        def get_clock():
            order.append('clock');count['clock']+=1
            return clock(9 if count['clock']==1 else 11)
        def record(name,value):
            def call():order.append(name);return value
            return call
        journal=helper.ReceiptJournal(publish=publisher,get_clock=get_clock,root=Path('/synthetic/late'),job=job)
        result=helper.poll(job,baseline_api=api_at(),get_api=record('api',eligible(9)),
            get_owner=record('owner',job['owner']),get_evidence=record('evidence',{'ok':True}),
            get_clock=get_clock,sleep=lambda _:self.fail('first terminal must not sleep'),emit=journal.emit)
        self.assertEqual(order[:4],['owner','evidence','api','clock'])
        self.assertEqual(result['status'],'LATCH_LATE_DURABILITY');self.assertEqual(result['candidate_requests_allowed'],0)
        self.assertEqual(len(publisher.calls),2)
        failures=[]
        def failed_emit(event):failures.append(event);raise OSError('original failed publication')
        result=helper.poll(job,baseline_api=api_at(),get_api=lambda:eligible(1),get_owner=lambda:job['owner'],
            get_evidence=lambda:{'ok':True},get_clock=lambda:clock(1),
            sleep=lambda _:self.fail('failed emission must not retry'),emit=failed_emit)
        self.assertEqual(len(failures),1);self.assertEqual(result['status'],'EVIDENCE_FAILED')
        self.assertEqual(result['observation']['state'],'LATCH');self.assertEqual(result['candidate_requests_allowed'],0)

    def test_six_original_pure_functions_are_exact_and_no_action_or_import_expansion(self):
        source=(HERE/'hot_window_observer.py').read_text()
        preservation=json.loads((HERE/'source-preservation.json').read_text())
        original=Path(preservation['horizon_original']['path']).read_text()
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),preservation['horizon_original']['sha256'])
        def bodies(text):
            lines=text.splitlines(keepends=True)
            return {node.name:''.join(lines[node.lineno-1:node.end_lineno]) for node in ast.parse(text).body
                    if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
        for name in ('require','integer','number','bounded','identity','normalise'):
            self.assertEqual(bodies(source)[name],bodies(original)[name])
        imports=[node.names[0].name for node in ast.parse(source).body if isinstance(node,ast.Import)]
        self.assertEqual(imports,['copy','hashlib','json','math'])
        self.assertNotIn('start_request',source);self.assertNotIn('def ending_deadline',source)
        self.assertEqual(helper.CATEGORIES,('dqn','epsilon','expert','eval','unattributed'))


def math_is_nan(value):
    return value!=value


if __name__=='__main__':unittest.main()
