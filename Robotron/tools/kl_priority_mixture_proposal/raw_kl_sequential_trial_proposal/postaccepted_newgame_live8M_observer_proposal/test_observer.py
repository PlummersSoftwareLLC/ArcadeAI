"""Authored, UNEXECUTED stdlib metadata guards. No application imports or live I/O."""
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
SPEC=importlib.util.spec_from_file_location('_future_postfix_observer_guards',HERE/'observer.py')
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
        client_count=192,training_enabled=True,measurement_active=False,managed_experiment='synthetic_future_postfix',
        lr=2.5e-5,pipeline_snapshot_age_s=0.25,pipeline_read_error='',grad_norm=float('nan'),
        host_pipeline=dict(learning_exposure=dict(optimizer=optimizer,replay=replay)))

def observe(observer,api=None,elapsed=1,*,owner=None,evidence=None):
    return observer.observe(api_at(elapsed) if api is None else api,
        observer.job['owner'] if owner is None else owner,dict(ok=True) if evidence is None else evidence,clock(elapsed))

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

def math_is_nan(value):
    return value!=value

def job_at(cutoff=100):
    record=fake_pin('new-CE-record.json')
    boot=fake_pin('actual-new-recovery-boot.pt')
    bootclocks=dict(training_steps=900,optimized_samples=4000000,frame_count=499000000,learner_frame_count=299000000)
    expected=dict(metric='ce',phase_id='synthetic_new_CE_after_recovery',root_precommit_sha256='b'*64,
        founder_phase_record_sha256=record['sha256'],last_resume_record_sha256=None,
        started_from=dict(boot,clocks=bootclocks),valid=True)
    return dict(schema=helper.SCHEMA,experiment='synthetic_future_postfix',recipe=copy.deepcopy(helper.RECIPE),
        owner=dict(pid=123,starttime_ticks=789,unit='synthetic-trainer.service',invocation_id='b'*32,cgroup='/synthetic/trainer.service'),
        current_phase=dict(record=record,boot_checkpoint=boot,boot_verification=fake_pin('actual-boot-CPU.json'),expected=expected),
        proofs={key:fake_pin(key+'.json') for key in ('root_precommit','recovery_result','recovery_release','control')},
        recovery_ready_clock=clock(-1),baseline=dict(api=fake_pin('actual-raw-post-READY-B.json'),observed_clock=clock()),
        policy=dict(helper.POLICY,cutoff_s=cutoff))

def eligible(elapsed=1,**extra):
    return api_at(elapsed,learner=8000000,dqn=7500000,epsilon=500000,applied=10,**extra)

class PostFixWindowContracts(unittest.TestCase):
    def test_default_and_dynamic_READY_phase_context_are_read_free(self):
        with patch('builtins.open',side_effect=AssertionError('read')),patch.object(Path,'read_bytes',side_effect=AssertionError('read')),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(helper.main(),0)
        value=json.loads(out.getvalue());self.assertEqual(value['status'],'PLAN_ONLY');self.assertFalse(value['selected']);self.assertIsNone(value['future_baseline']);self.assertIsNone(value['policy']['cutoff_s'])
        first=helper.HorizonObserver(job_at(),api_at());self.assertTrue(math_is_nan(first.baseline_raw['grad_norm']))
        dynamic=job_at();dynamic['current_phase']['record']['sha256']='c'*64;dynamic['current_phase']['expected']['founder_phase_record_sha256']='c'*64
        self.assertEqual(helper.HorizonObserver(dynamic,api_at()).job['current_phase']['record']['sha256'],'c'*64)
        mutations=(lambda j:j['current_phase']['expected'].update(founder_phase_record_sha256='d'*64),
            lambda j:j['current_phase']['expected']['started_from'].update(sha256='d'*64),
            lambda j:j['current_phase']['expected'].update(last_resume_record_sha256='d'*64),
            lambda j:j['recovery_ready_clock'].update(boot_id='other'),
            lambda j:j['baseline'].update(observed_clock=clock(-2)),
            lambda j:j['proofs'].update(barrier=fake_pin('obsolete-barrier.json')),
            lambda j:j['policy'].update(learner_accepted=6000000),
            lambda j:j['recipe'].update(learning_control_lr_scale=.25),
            lambda j:j.update(start_request=clock()))
        for mutate in mutations:
            j=job_at();mutate(j)
            with self.assertRaises((ValueError,KeyError,TypeError)):helper.HorizonObserver(j,api_at())

    def test_B_is_nonzero_pending0_available_and_after_READY_cache_boundary(self):
        cases=[api_at(pending=1),api_at(applied=-100,skipped=-5),api_at(dqn=-1000000,epsilon=-200000,expert=-250000,evaluate=-100000,unattributed=-10000)]
        v=api_at();v['ts']-=.8;cases.append(v)
        v=api_at();v['lr']=1.25e-5;cases.append(v)
        v=api_at();v['learner_frame_count']=298999999;cases.append(v)
        v=api_at();v['host_pipeline']['learning_exposure']['optimizer']['available']=False;cases.append(v)
        for v in cases:
            with self.assertRaises((ValueError,KeyError)):helper.HorizonObserver(job_at(),v)
        self.assertEqual(helper.HorizonObserver(job_at(),api_at()).baseline['unclassified'],0)

    def test_new_8M_AND_8M_policy_same_B_accounting_and_first_pending1_LATCH(self):
        for value in (api_at(1,learner=8000000,dqn=6000000,applied=1),api_at(1,learner=7999999,dqn=8000000,applied=1),api_at(1,learner=8000000,expert=6000000,evaluate=2000000,applied=1)):
            self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),value)['state'],'CONTINUE')
        observer=helper.HorizonObserver(job_at(),api_at());first=observe(observer,eligible(pending=1,skipped=2,expert=9,evaluate=5,logical_steps=19,logical_samples=777))
        self.assertEqual(first['state'],'LATCH');self.assertEqual(first['candidate_requests_allowed'],0)
        p=first['progress'];self.assertEqual((p['learner_frames'],p['learner_accepted'],p['physical_accepted']),(8000000,8000000,8000014))
        self.assertEqual((p['optimizer_pending'],p['AMP_classified_denominator']),(1,12));self.assertEqual(p['AMP_skip_fraction'],2/12)
        self.assertEqual(p['admitted_samples_from_B'],10*4096);self.assertEqual(p['logical_samples'],777)
        self.assertEqual(p['physical_by_source'],dict(dqn=7500000,epsilon=500000,expert=9,eval=5,unattributed=0))
        first['progress']['learner_frames']=0
        later=observer.observe(None,None,{},clock(1000));self.assertEqual(later['state'],'LATCH');self.assertEqual(later['progress']['learner_frames'],8000000)
        self.assertFalse(later['owner_actions_allowed'])

    def test_epoch_counters_health_freshness_stall_and_cutoff_fail_closed(self):
        for kind in ('optimizer','replay'):
            v=api_at(1);v['host_pipeline']['learning_exposure'][kind]['epoch']+=1
            self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),v)['state'],'INVALID')
        for v in (api_at(1,dqn=-1),api_at(1,unavailable=1),api_at(1,pending=2)):
            self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),v)['state'],'INVALID')
        self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),owner={})['state'],'INVALID')
        self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),evidence={'ok':False})['state'],'INVALID')
        self.assertEqual(observe(helper.HorizonObserver(job_at(),api_at()),elapsed=30)['state'],'INVALID')
        observer=helper.HorizonObserver(job_at(),api_at())
        for elapsed in (20,40):self.assertEqual(observe(observer,api_at(elapsed,learner=elapsed,dqn=elapsed),elapsed)['state'],'CONTINUE')
        self.assertEqual(observe(observer,api_at(60,learner=60,dqn=60),60)['state'],'INVALID')
        self.assertEqual(observe(helper.HorizonObserver(job_at(10),api_at()),eligible(10),10)['state'],'LATCH')
        self.assertEqual(observe(helper.HorizonObserver(job_at(10),api_at()),eligible(11),11)['state'],'INCOMPLETE')
        self.assertNotIn('ceiling_s',job_at()['policy'])

    def test_original_durable_first_event_only_and_publication_failure_never_replaced(self):
        j=job_at(10);observer=helper.HorizonObserver(j,api_at());e=observe(observer,eligible(9),9);e['sequence']=0
        self.assertEqual(helper.durable_result(e,emit_pair(e,j,10),j)['candidate_requests_allowed'],1)
        late=helper.durable_result(e,emit_pair(e,j,10.01),j);self.assertEqual(late['status'],'LATCH_LATE_DURABILITY');self.assertEqual(late['candidate_requests_allowed'],0)
        pub=MemoryPublisher();journal=helper.ReceiptJournal(publish=pub,get_clock=lambda:clock(10),root=Path('/synthetic/journal'),job=j)
        journal.emit(e)
        with self.assertRaises(ValueError):journal.emit(e)
        failures=[]
        def fail(event):failures.append(event);raise OSError('original publication failed')
        result=helper.poll(j,baseline_api=api_at(),get_api=lambda:eligible(1),get_owner=lambda:j['owner'],get_evidence=lambda:{'ok':True},get_clock=lambda:clock(1),sleep=lambda _:self.fail('retry'),emit=fail)
        self.assertEqual(result['status'],'EVIDENCE_FAILED');self.assertEqual(result['candidate_requests_allowed'],0);self.assertEqual(len(failures),1)

    def test_finite_source_changes_and_original_accounting_durability_are_preserved(self):
        preservation=json.loads((HERE/'source-preservation.json').read_text());base=Path(preservation['base_observer']['path']).read_text()
        self.assertEqual(hashlib.sha256(base.encode()).hexdigest(),preservation['base_observer']['sha256'])
        source=base
        for change in preservation['replacements']:
            self.assertEqual(source.count(change['before']),1);source=source.replace(change['before'],change['after'],1)
        current=(HERE/'observer.py').read_text();self.assertEqual(source,current)
        def bodies(text):return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name in preservation['unchanged_pure_functions']:self.assertEqual(bodies(base)[name],bodies(current)[name])
        self.assertEqual([n.names[0].name for n in ast.parse(current).body if isinstance(n,ast.Import)],['copy','hashlib','json','math'])
        self.assertNotIn('start_request',current);self.assertNotIn('barrier_completed_clock',current)

if __name__=='__main__':unittest.main()
