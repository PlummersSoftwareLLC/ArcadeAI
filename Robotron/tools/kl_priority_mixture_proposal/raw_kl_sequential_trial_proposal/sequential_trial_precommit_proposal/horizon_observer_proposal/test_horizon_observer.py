"""Authored/unexecuted pure stdlib guards; synthetic metadata, no application imports."""
import contextlib
import copy
import io
import unittest
from unittest.mock import patch

from . import horizon_observer as helper


def api_at(elapsed=100, *, learner=0, physical=0, applied=1, skipped=0,
           inflight=0, expert=0, evaluate=0, unattributed=0):
    # Physical is all categories; the default remainder is actual learner-eligible.
    categories=dict(dqn=physical-expert-evaluate-unattributed,epsilon=0,
                    expert=expert,eval=evaluate,unattributed=unattributed)
    recorded=applied+skipped
    total=dict(attempts_started=recorded+inflight,outcomes_recorded=recorded,
               applied=applied,amp_skipped=skipped,unavailable=0)
    identity=dict(process_id=123,instance_monotonic_ns=1000,epoch=1,epoch_reason='restore')
    optimizer=dict(identity,schema='robotron-optimizer-exposure-v1',enabled=True,
                   available=recorded>0 and inflight==0,total=total,since_epoch=copy.deepcopy(total),
                   unclassified_started_total=inflight)
    replay=dict(identity,schema='robotron-replay-insert-exposure-v1',enabled=True,available=True,
                accepted_total=physical,accepted_learner_total=categories['dqn'],
                accepted_by_source_total=categories)
    return dict(training_steps=100+recorded,optimized_samples=409600+recorded*4096,
                frame_count=20000+physical,learner_frame_count=10000+learner,
                ts=100000+elapsed,pipeline_snapshot_age_s=0,pipeline_read_error='',
                host_pipeline=dict(learning_exposure=dict(optimizer=optimizer,replay=replay)))


def job_at(healthy_elapsed=90):
    return dict(schema=helper.SCHEMA,policy=copy.deepcopy(helper.POLICY),
        owner=dict(pid=123,starttime_ticks=200,unit='robotron-managed-test-trainer.service',
                   invocation_id='a'*32,cgroup='/user.slice/test.service'),
        start_request=dict(boot_id='test-boot',monotonic_s=1000,unix_s=100000),
        healthy192_monotonic_s=1000+healthy_elapsed,
        boot_four_clocks=dict(training_steps=100,optimized_samples=409600,
                              frame_count=20000,learner_frame_count=10000),
        trial_core_sha256='b'*64,activation_receipt_sha256='c'*64,
        before_resume_api=api_at(10,applied=0))


def clock(elapsed):
    return dict(boot_id='test-boot',monotonic_s=1000+elapsed,wall_s=100000+elapsed)


def observe(observer,api,elapsed=100,owner=None,evidence=None):
    return observer.observe(api,observer.job['owner'] if owner is None else owner,
                            dict(ok=True) if evidence is None else evidence,clock(elapsed))


class HorizonContracts(unittest.TestCase):
    def test_default_is_literal_no_observation(self):
        with patch.object(helper,'HorizonObserver',side_effect=AssertionError('not default')), \
                contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(helper.main(),0)
        self.assertIn('PLAN_ONLY',stream.getvalue())

    def test_both_independent_horizons_required_not_logical_samples(self):
        observer=helper.HorizonObserver(job_at())
        huge=api_at(100,learner=8000000,physical=5999999)
        huge['training_steps']=999999999;huge['optimized_samples']=999999999999
        self.assertEqual(observe(observer,huge)['state'],'CONTINUE')
        fresh=helper.HorizonObserver(job_at())
        self.assertEqual(observe(fresh,api_at(100,learner=7999999,physical=6000000))['state'],'CONTINUE')
        event=observe(helper.HorizonObserver(job_at()),api_at(100,learner=8000000,physical=6000000))
        self.assertEqual(event['state'],'LATCH')
        self.assertEqual(event['candidate_requests_allowed'],1)
        self.assertFalse(event['qualification_pass'])

    def test_physical_all_five_categories_not_learner_only(self):
        data=api_at(100,learner=8000000,physical=6000000,expert=2000000,evaluate=1000000,unattributed=1000000)
        data['host_pipeline']['learning_exposure']['replay']['accepted_by_source_total']['epsilon']=500000
        data['host_pipeline']['learning_exposure']['replay']['accepted_by_source_total']['dqn']-=500000
        event=observe(helper.HorizonObserver(job_at()),data)
        self.assertEqual(event['state'],'LATCH')
        self.assertEqual(event['progress']['physical_accepted'],6000000)
        self.assertEqual(event['progress']['learner_accepted'],2000000)

    def test_partition_errors_and_boolean_counters_refused(self):
        for change in ('physical','learner','outcomes','inflight','available','bool'):
            data=api_at(100,physical=10);ex=data['host_pipeline']['learning_exposure']
            if change=='physical':ex['replay']['accepted_total']+=1
            if change=='learner':ex['replay']['accepted_learner_total']+=1
            if change=='outcomes':ex['optimizer']['total']['outcomes_recorded']+=1
            if change=='inflight':ex['optimizer']['unclassified_started_total']=2
            if change=='available':ex['optimizer']['available']=False
            if change=='bool':data['learner_frame_count']=True
            with self.subTest(change=change):
                self.assertEqual(observe(helper.HorizonObserver(job_at()),data)['state'],'INVALID')

    def test_internal_one_inflight_is_normal_and_real_skip_partition_retained(self):
        data=api_at(100,learner=8000000,physical=6000000,applied=2,skipped=3,inflight=1)
        event=observe(helper.HorizonObserver(job_at()),data)
        self.assertEqual(event['state'],'LATCH')
        self.assertEqual(event['progress']['optimizer_total']['amp_skipped'],3)
        self.assertEqual(event['progress']['admitted_samples_total'],8192)

    def test_available_uses_since_epoch_not_total_outcomes(self):
        job=job_at();optimizer=job['before_resume_api']['host_pipeline']['learning_exposure']['optimizer']
        optimizer['total'].update(attempts_started=3,outcomes_recorded=3,applied=3)
        # Same actual source rule: this new epoch has no recorded outcomes yet.
        self.assertFalse(optimizer['available'])
        observer=helper.HorizonObserver(job)
        data=api_at(100,applied=3)
        optimizer=data['host_pipeline']['learning_exposure']['optimizer']
        optimizer['since_epoch']=dict.fromkeys(helper.COUNTERS,0);optimizer['available']=False
        self.assertEqual(observe(observer,data)['state'],'CONTINUE')
        data=api_at(101,applied=4);optimizer=data['host_pipeline']['learning_exposure']['optimizer']
        optimizer['since_epoch']=dict(attempts_started=1,outcomes_recorded=1,applied=1,amp_skipped=0,unavailable=0)
        self.assertEqual(observe(observer,data,101)['state'],'CONTINUE')
        invalid=copy.deepcopy(data);invalid['host_pipeline']['learning_exposure']['optimizer']['available']=False
        self.assertEqual(observe(helper.HorizonObserver(job),invalid,101)['state'],'INVALID')

    def test_full_instance_epoch_owner_and_evidence_discontinuity(self):
        for group in ('optimizer','replay'):
            for field in helper.IDENTITY:
                data=api_at();entry=data['host_pipeline']['learning_exposure'][group]
                entry[field]=entry[field]+1 if type(entry[field]) is int else 'different'
                with self.subTest(group=group,field=field):
                    self.assertEqual(observe(helper.HorizonObserver(job_at()),data)['state'],'INVALID')
        observer=helper.HorizonObserver(job_at())
        self.assertEqual(observe(observer,api_at(),owner=dict(observer.job['owner'],starttime_ticks=201))['state'],'INVALID')
        self.assertEqual(observe(helper.HorizonObserver(job_at()),api_at(),evidence=dict(ok=False))['state'],'INVALID')

    def test_counter_regression_and_classified_unavailable_refuse(self):
        observer=helper.HorizonObserver(job_at())
        self.assertEqual(observe(observer,api_at(100,learner=100,physical=100,applied=4))['state'],'CONTINUE')
        for field in ('learner','physical','applied'):
            other=copy.deepcopy(observer)
            args=dict(learner=100,physical=100,applied=4);args[field]-=1
            self.assertEqual(observe(other,api_at(101,**args),101)['state'],'INVALID')
        data=api_at();entry=data['host_pipeline']['learning_exposure']['optimizer']
        entry['total']['unavailable']=1;entry['total']['outcomes_recorded']+=1
        entry['total']['attempts_started']+=1;entry['since_epoch']=copy.deepcopy(entry['total']);entry['available']=False
        self.assertEqual(observe(helper.HorizonObserver(job_at()),data)['state'],'INVALID')

    def test_freshness_grace_and_recovery_before_expiry(self):
        observer=helper.HorizonObserver(job_at())
        stale=api_at(100);stale['ts']-=6
        self.assertEqual(observe(observer,stale,100)['state'],'CONTINUE')
        self.assertEqual(observe(observer,None,129)['state'],'CONTINUE')
        self.assertEqual(observe(observer,api_at(130),130)['state'],'CONTINUE')
        self.assertEqual(observe(observer,None,131)['state'],'CONTINUE')
        self.assertEqual(observe(observer,None,160)['state'],'CONTINUE')
        self.assertEqual(observe(observer,None,161)['state'],'INVALID')
        for changed in ('pipeline','error'):
            data=api_at()
            if changed=='pipeline':data['pipeline_snapshot_age_s']=6
            else:data['pipeline_read_error']='unavailable'
            self.assertEqual(observe(helper.HorizonObserver(job_at()),data)['state'],'CONTINUE')

    def test_no_applied_with_real_progress_is_stop_not_skip_rate_heuristic(self):
        observer=helper.HorizonObserver(job_at(10))
        for elapsed in (10,39,68):observe(observer,api_at(elapsed,applied=0),elapsed)
        event=observe(observer,api_at(70,learner=1,physical=1,applied=0,skipped=3),70)
        self.assertEqual(event['state'],'INVALID')
        fresh=helper.HorizonObserver(job_at(10))
        for elapsed in (10,39,68):observe(fresh,api_at(elapsed,applied=0),elapsed)
        idle=observe(fresh,api_at(70,applied=0,skipped=3),70)
        self.assertEqual(idle['state'],'CONTINUE')
        live=observe(helper.HorizonObserver(job_at(60)),api_at(70,learner=1,physical=1,applied=1,skipped=100),70)
        self.assertEqual(live['state'],'CONTINUE')

    def test_exact_cutoff_eligible_allowed_late_tail_never_rescues(self):
        target=dict(learner=8000000,physical=6000000)
        exact=observe(helper.HorizonObserver(job_at(3230)),api_at(3240,**target),3240)
        self.assertEqual(exact['state'],'LATCH')
        for elapsed in (3240,3241):
            event=observe(helper.HorizonObserver(job_at(3230)),api_at(elapsed),elapsed)
            self.assertEqual(event['state'],'INCOMPLETE')
        late=observe(helper.HorizonObserver(job_at(3230)),api_at(3241,**target),3241)
        self.assertEqual(late['state'],'INCOMPLETE')
        no_data=observe(helper.HorizonObserver(job_at(3230)),None,3240)
        self.assertEqual(no_data['state'],'INCOMPLETE')

    def test_ceiling_precedes_horizon_and_ending_never_grants_candidate(self):
        event=observe(helper.HorizonObserver(job_at(3590)),api_at(3600,learner=8000000,physical=6000000),3600)
        self.assertEqual(event['state'],'INVALID');self.assertTrue(event['manual_recovery_required'])
        result=helper.ending_deadline(job_at(),clock(3600),KL_owner_present=True)
        self.assertEqual(result['state'],'INVALID')
        result=helper.ending_deadline(job_at(),clock(3601),KL_owner_present=False)
        self.assertEqual(result['state'],'ROOT_ENDING_PROOF_REQUIRED')
        self.assertNotIn('candidate_requests_allowed',result)

    def test_latch_and_terminal_are_immutable_under_later_calls_and_input_mutation(self):
        observer=helper.HorizonObserver(job_at());data=api_at(100,learner=8000000,physical=6000000)
        first=observe(observer,data);first['candidate_requests_allowed']=999;data['learner_frame_count']=0
        later=observer.observe(None,None,dict(ok=False),clock(3600))
        self.assertEqual(later['state'],'LATCH');self.assertEqual(later['candidate_requests_allowed'],1)
        self.assertEqual(later['first_eligible_observation']['learner_frame_count'],8010000)
        invalid=helper.HorizonObserver(job_at());first=observe(invalid,api_at(),owner={})
        self.assertEqual(observe(invalid,api_at(101,learner=8000000,physical=6000000),101),first)

    def test_clock_failures_keep_invalid_receipt_without_fabricating_time(self):
        for now in ({},None,dict(monotonic_s=float('nan'),wall_s=1,boot_id='test-boot')):
            result=helper.HorizonObserver(job_at()).observe(None,None,{},now)
            self.assertEqual(result['state'],'INVALID');self.assertIsNone(result['observed_monotonic_s'])
        for now in (dict(clock(100),boot_id='different'),clock(9)):
            self.assertEqual(helper.HorizonObserver(job_at()).observe(None,None,{},now)['state'],'INVALID')
        observer=helper.HorizonObserver(job_at());observe(observer,api_at(100),100)
        self.assertEqual(observe(observer,api_at(99),99)['state'],'INVALID')

    def test_fresh_api_cannot_hide_first_or_later_unobserved_gap(self):
        target=dict(learner=8000000,physical=6000000)
        first=observe(helper.HorizonObserver(job_at(70)),api_at(100,**target),100)
        self.assertEqual(first['state'],'INVALID')
        self.assertIn('poll gap',first['reason'])
        observer=helper.HorizonObserver(job_at())
        self.assertEqual(observe(observer,api_at(100),100)['state'],'CONTINUE')
        result=observe(observer,api_at(130,**target),130)
        self.assertEqual(result['state'],'INVALID');self.assertNotIn('candidate_requests_allowed',result)

    def test_job_requires_actual_bindings_and_fresh_before_resume_object(self):
        for field in ('activation_receipt_sha256','trial_core_sha256'):
            value=job_at();value[field]=None
            with self.subTest(field=field),self.assertRaises(ValueError):helper.HorizonObserver(value)
        value=job_at();value['before_resume_api']=api_at(10,physical=1,applied=0)
        with self.assertRaises(ValueError):helper.HorizonObserver(value)
        value=job_at();value['policy']['cutoff_s']+=1
        with self.assertRaises(ValueError):helper.HorizonObserver(value)

    def test_poll_injected_only_and_api_error_grace_has_bounded_receipts(self):
        times=iter((clock(100),clock(100),clock(101),clock(101)))
        values=iter((OSError('API unavailable'),api_at(101,learner=8000000,physical=6000000)))
        receipts=[];sleeps=[]
        def get_api():
            item=next(values)
            if isinstance(item,Exception):raise item
            return item
        result=helper.poll(job_at(),get_api=get_api,get_owner=lambda:job_at()['owner'],
            get_evidence=lambda:dict(ok=True),get_clock=lambda:next(times),sleep=sleeps.append,emit=receipts.append)
        self.assertEqual([r['state'] for r in receipts],['CONTINUE','LATCH'])
        self.assertEqual([r['sequence'] for r in receipts],[0,1]);self.assertEqual(sleeps,[1])
        self.assertEqual(result['candidate_requests_allowed'],1)

    def test_receipt_failure_propagates_no_silent_retry_or_action(self):
        error=OSError('durable receipt failed');calls=[]
        def fail_receipt(event):calls.append(event);raise error
        with self.assertRaises(OSError) as caught:
            helper.poll(job_at(),get_api=lambda:api_at(100,learner=8000000,physical=6000000),
                get_owner=lambda:job_at()['owner'],get_evidence=lambda:dict(ok=True),
                get_clock=lambda:clock(100),sleep=lambda _:self.fail('no retry'),emit=fail_receipt)
        self.assertIs(caught.exception,error);self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
