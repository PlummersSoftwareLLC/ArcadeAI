"""CPU-only coordinator/gate contracts with fake runtimes and archived evidence."""
import copy
import json
from pathlib import Path
import sys
import time
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import startup_probe_core_v1 as core

SETTINGS=dict(slots=list(core.SLOTS),frames=4096,max_wall_s=300,poll_s=0.25)


def snapshot(count=4096, *, closed=True):
    return dict(closed=closed,failed=False,faults=0,rows=count*16,
        counts={slot:count for slot in core.SLOTS},pending=0,epochs={slot:1 for slot in core.SLOTS})


def matched():
    return dict(status='MATCHED_DIAGNOSTIC_PREFIX_ONLY',matched_frames=65536,
        accepted_frames=65535,rejected_frames=1,actor_slots=16,raw_ROM_start_acceptance_proven=False,
        start_eligibility_changed=False,protocol_selected=False,quality_qualified=False,
        learning_speed_gain_verified=False)


class Runtime:
    def __init__(self):
        self.events=[];self.failures={};self.now=0.;self.delays={};self.snapshots=[snapshot()]
        self.matcher=matched();self.audit_result=dict(valid=True,all_owned_actors_absent=True,
            sources_unchanged=True,checkpoint_unchanged=True,main_healthy=True,runtime_timeouts=0)
        self.cleanup_errors=[];self.release_errors=[];self.published=None
    def called(self,name):
        self.events.append(name);self.now+=self.delays.get(name,0.)
        if name in self.failures:raise self.failures[name]
    def prepare(self):self.called('prepare')
    def start(self):self.called('start')
    def check(self):self.called('check')
    def snapshot(self):
        self.called('snapshot')
        return self.snapshots.pop(0) if len(self.snapshots)>1 else self.snapshots[0]
    def cleanup(self):self.called('cleanup');return self.cleanup_errors
    def collect(self):self.called('collect');return self.matcher
    def audit(self):self.called('audit');return self.audit_result
    def release(self):self.called('release');return self.release_errors
    def publish(self,result):self.called('publish');self.published=copy.deepcopy(result)
    def clock(self):return self.now
    def sleep(self,seconds):self.events.append('sleep');self.now+=seconds


def predecessor():
    values={};calls=[]
    def entry(name,sha=None):
        return dict(path='/synthetic/'+name,sha256=sha or name)
    bundle={key:entry(key) for key in ('plan','status','native_owner','native_closure',
        'outer_owner','outer_closure','review_owner','review_closure','review_config','review_source','disposition')}
    for key,sha in (('plan',core.CURRENT_PLAN_SHA),('native_owner',core.NATIVE_OWNER_SHA),
                    ('outer_owner',core.OUTER_OWNER_SHA),('review_source',core.REVIEW_SOURCE_SHA)):
        bundle[key]['sha256']=sha
    values['plan']=dict(schema='synthetic-original-plan')
    values['status']=dict(state='finished',outcome='not_improved',plan_sha256=core.CURRENT_PLAN_SHA)
    values['disposition']=dict(schema='robotron-closed-quality-before-startup-diagnostic-v1',
        original_status_sha256=bundle['status']['sha256'],original_plan_sha256=core.CURRENT_PLAN_SHA,
        quality_campaign_closed=True,no_cohort_retry=True,native_outcome='not_improved',
        winner_protected_or_not_applicable=True)
    values['review_source']=b'CPU synthetic reviewer bytes; no source execution'
    for index,role in enumerate(('native','outer','review'),10):
        values[role+'_owner']=dict(pid=index,starttime_ticks=100+index,unit=role+'.service',
            timer=role+'.timer',cgroup='/user.slice/'+role+'.service')
        values[role+'_closure']=dict(original=values[role+'_owner'],original_exit=0,
            lifecycle_complete=True,unit_released=True,payload_retried=False)
    values['review_config']=dict(unit='review.service',argv=['python',bundle['review_source']['path'],'--execute'])
    def read(pin,as_json):
        name=Path(pin['path']).name;calls.append('read:'+name);return values[name]
    def archive(closure,owner,read,*,exit_zero):
        calls.append('archive:'+owner['unit']);assert exit_zero is False
        if not closure.get('lifecycle_complete') or not closure.get('unit_released'):
            raise ValueError('Synthetic original closure incomplete')
        assert closure['original']==owner
        return dict(ControlGroup=owner['cgroup'])
    def process(pid):calls.append('process:'+str(pid));return None
    def units(unit):calls.append('unit:'+unit);return dict(Id=unit,LoadState='not-found')
    def groups(group):calls.append('group:'+group);return False
    dependencies=dict(read=read,archive=archive,process_start=process,unit_fields=units,cgroup_exists=groups)
    return bundle,values,calls,dependencies


class Tests(unittest.TestCase):
    def run_runtime(self,runtime,**kwargs):
        return core.execute(runtime,SETTINGS,clock=runtime.clock,sleep=runtime.sleep,**kwargs)
    def finalizers(self,runtime):
        self.assertEqual([x for x in runtime.events if x in ('cleanup','collect','audit','release','publish')],
                         ['cleanup','collect','audit','release','publish'])

    def test_success_captures_exact_prefix_and_finalizes_before_publication(self):
        r=Runtime();result=self.run_runtime(r)
        self.assertTrue(result['valid']);self.assertEqual(result['status'],'MATCHED_DIAGNOSTIC_PREFIX_ONLY')
        self.assertEqual(r.events,['prepare','start','check','snapshot','cleanup','collect','audit','release','publish'])
        self.assertEqual(r.published,result);self.assertEqual(result['attempts'],1);self.assertFalse(result['retried'])
        self.assertTrue(all(result[key] is False for key in ('quality_qualified','protocol_selected',
            'raw_ROM_start_acceptance_proven','start_eligibility_changed','learning_speed_gain_verified')))

    def test_each_runtime_operation_failure_still_attempts_every_finalizer(self):
        for phase in ('prepare','start','check','snapshot'):
            with self.subTest(phase=phase):
                r=Runtime();r.failures[phase]=OSError('injected '+phase);result=self.run_runtime(r)
                self.assertFalse(result['valid']);self.finalizers(r)
                self.assertEqual(sum(x==phase for x in r.events),1)
                self.assertIn('injected '+phase,result['errors'][0]['message'])

    def test_prepare_time_counts_against_fixed_deadline(self):
        r=Runtime();r.delays['prepare']=300.;result=self.run_runtime(r)
        self.assertFalse(result['valid']);self.assertNotIn('start',r.events)
        self.assertIn('deadline expired',result['errors'][0]['message']);self.finalizers(r)

    def test_start_time_counts_against_fixed_deadline(self):
        r=Runtime();r.delays['start']=300.;result=self.run_runtime(r)
        self.assertFalse(result['valid']);self.assertNotIn('check',r.events);self.finalizers(r)

    def test_capture_deadline_does_not_extend_or_retry(self):
        r=Runtime();r.snapshots=[snapshot(0,closed=False)];r.delays['check']=150.
        result=self.run_runtime(r);self.assertFalse(result['valid'])
        self.assertEqual(r.events.count('start'),1);self.assertLessEqual(r.events.count('check'),2)
        self.assertIn('deadline expired',result['errors'][0]['message']);self.finalizers(r)

    def test_completion_after_deadline_is_still_invalid(self):
        r=Runtime();r.delays['snapshot']=300.;result=self.run_runtime(r)
        self.assertTrue(result['capture_complete']);self.assertFalse(result['valid']);self.finalizers(r)

    def test_interruption_before_prepare_and_during_capture_is_preserved(self):
        r=Runtime();result=self.run_runtime(r,stopped=lambda:True)
        self.assertFalse(result['valid']);self.assertNotIn('prepare',r.events);self.finalizers(r)
        r=Runtime();r.failures['check']=KeyboardInterrupt('injected interrupt');result=self.run_runtime(r)
        self.assertFalse(result['valid']);self.assertEqual(result['errors'][0]['type'],'KeyboardInterrupt');self.finalizers(r)

    def test_all_finalizer_exceptions_are_preserved_and_release_still_runs(self):
        r=Runtime()
        for name in ('cleanup','collect','audit','release'):r.failures[name]=RuntimeError('injected '+name)
        result=self.run_runtime(r);self.assertFalse(result['valid']);self.finalizers(r)
        self.assertEqual([x['stage'] for x in result['errors']],['cleanup','collect','audit','release'])

    def test_cleanup_error_lists_are_not_silently_accepted(self):
        r=Runtime();r.cleanup_errors=['owned actor wait failed'];r.release_errors=['owned lease close failed']
        result=self.run_runtime(r);self.assertFalse(result['valid']);self.finalizers(r)
        self.assertEqual([x['stage'] for x in result['errors']],['cleanup','release'])

    def test_same_original_runtime_object_cannot_be_reused_after_success_or_failure(self):
        for fail in (False,True):
            r=Runtime()
            if fail:r.failures['prepare']=RuntimeError('injected setup')
            self.run_runtime(r);before=list(r.events)
            with self.assertRaises(ValueError):self.run_runtime(r)
            self.assertEqual(r.events,before)

    def test_progress_counter_regression_and_connection_restart_fail(self):
        for restart in (False,True):
            r=Runtime();first=snapshot(2048,closed=False);second=snapshot(2048 if restart else 1024,closed=False)
            if restart:second['epochs'][4096]=2
            r.snapshots=[first,second];result=self.run_runtime(r)
            self.assertFalse(result['valid']);self.assertEqual(r.events.count('start'),1);self.finalizers(r)

    def test_early_close_faults_pending_work_and_bad_counts_are_invalid(self):
        variants=[]
        bad=snapshot(0);variants.append(bad)
        for key,value in (('faults',1),('failed',True),('pending',1),('rows',True)):
            bad=snapshot();bad[key]=value;variants.append(bad)
        bad=snapshot();bad['counts'][4096]=True;variants.append(bad)
        bad=snapshot();bad['epochs'][4096]=True;variants.append(bad)
        for value in variants:
            r=Runtime();r.snapshots=[value];result=self.run_runtime(r)
            self.assertFalse(result['valid']);self.finalizers(r)

    def test_partial_reconciliation_or_approval_flags_cannot_rescue_capture(self):
        for key,value in (('matched_frames',65535),('actor_slots',15),('accepted_frames',True),
                          ('raw_ROM_start_acceptance_proven',True),('quality_qualified',True),
                          ('learning_speed_gain_verified',True)):
            r=Runtime();r.matcher[key]=value;result=self.run_runtime(r)
            self.assertFalse(result['valid']);self.assertEqual(result['errors'][0]['stage'],'collect');self.finalizers(r)

    def test_every_runtime_audit_predicate_is_required(self):
        for key in ('valid','all_owned_actors_absent','sources_unchanged','checkpoint_unchanged','main_healthy','runtime_timeouts'):
            r=Runtime();r.audit_result[key]=1 if key=='runtime_timeouts' else False
            result=self.run_runtime(r);self.assertFalse(result['valid']);self.finalizers(r)

    def test_publish_failure_keeps_failure_and_does_not_rerun_capture(self):
        r=Runtime();r.failures['publish']=OSError('injected publication failure');result=self.run_runtime(r)
        self.assertFalse(result['valid']);self.assertEqual(result['errors'][-1]['stage'],'publish')
        self.assertEqual(r.events.count('start'),1);self.finalizers(r)
        self.assertIn('injected publication failure',result['errors'][-1]['traceback'])

    def test_nonfinite_and_backward_clocks_also_cleanup(self):
        r=Runtime();result=core.execute(r,SETTINGS,clock=lambda:float('nan'),sleep=r.sleep)
        self.assertFalse(result['valid']);self.finalizers(r)
        r=Runtime();values=iter((0.,-1.));result=core.execute(r,SETTINGS,clock=lambda:next(values),sleep=r.sleep)
        self.assertFalse(result['valid']);self.finalizers(r)

    def test_settings_cannot_weaken_fixed_target_slots_or_budget(self):
        for key,value in (('frames',4095),('frames',True),('slots',list(range(4096,4128))),
                          ('max_wall_s',301),('poll_s',1.0)):
            settings=copy.deepcopy(SETTINGS);settings[key]=value;r=Runtime()
            with self.assertRaises(ValueError):core.execute(r,settings,clock=r.clock,sleep=r.sleep)
            self.assertEqual(r.events,[])

    def test_successful_closed_gate_authenticates_archives_before_live_queries(self):
        bundle,values,calls,deps=predecessor();result=core.verify_closed_predecessor(bundle,**deps)
        self.assertEqual(result['original_owner_count'],3);self.assertFalse(result['GPU_lease_acquired'])
        last=max(i for i,x in enumerate(calls) if x.startswith('archive:'))
        self.assertTrue(all(i>last for i,x in enumerate(calls) if x.startswith(('process:','unit:','group:'))))
        self.assertEqual(sum(x.startswith('unit:') for x in calls),6)

    def test_missing_or_invalid_closure_prevents_every_live_query(self):
        for role in ('native','outer','review'):
            bundle,values,calls,deps=predecessor();values[role+'_closure']['lifecycle_complete']=False
            with self.assertRaises(ValueError):core.verify_closed_predecessor(bundle,**deps)
            self.assertFalse(any(x.startswith(('process:','unit:','group:')) for x in calls))

    def test_live_original_reused_PID_units_and_cgroups_are_distinguished(self):
        bundle,values,calls,deps=predecessor();deps['process_start']=lambda pid:999999
        self.assertEqual(core.verify_closed_predecessor(bundle,**deps)['status'],'ORIGINAL_PREDECESSOR_CLOSED')
        bundle,values,calls,deps=predecessor();deps['process_start']=lambda pid:100+pid
        with self.assertRaises(ValueError):core.verify_closed_predecessor(bundle,**deps)
        for field in ('unit','group'):
            bundle,values,calls,deps=predecessor()
            if field=='unit':deps['unit_fields']=lambda unit:dict(Id=unit,LoadState='loaded')
            else:deps['cgroup_exists']=lambda group:True
            with self.assertRaises(ValueError):core.verify_closed_predecessor(bundle,**deps)

    def test_foreign_campaign_owner_reviewer_or_disposition_is_refused(self):
        for key in ('plan','native_owner','outer_owner','review_source'):
            bundle,values,calls,deps=predecessor();bundle[key]['sha256']='0'*64
            with self.assertRaises(ValueError):core.verify_closed_predecessor(bundle,**deps)
            self.assertEqual(calls,[])
        bundle,values,calls,deps=predecessor();values['disposition']['winner_protected_or_not_applicable']=False
        with self.assertRaises(ValueError):core.verify_closed_predecessor(bundle,**deps)
        self.assertFalse(any(x.startswith(('process:','unit:','group:')) for x in calls))

    def test_stale_producer_status_requires_nonzero_original_exit_and_invalid_disposition(self):
        bundle,values,calls,deps=predecessor();values['status']['state']='running'
        values['disposition']['native_outcome']='invalid'
        with self.assertRaises(ValueError):core.verify_closed_predecessor(bundle,**deps)
        values['native_closure']['original_exit']=1
        self.assertEqual(core.verify_closed_predecessor(bundle,**deps)['native_outcome'],'invalid')

    def test_scientific_outcome_cannot_be_reinterpreted_and_review_config_must_match(self):
        bundle,values,calls,deps=predecessor();values['disposition']['native_outcome']='qualified_improvement'
        with self.assertRaises(ValueError):core.verify_closed_predecessor(bundle,**deps)
        bundle,values,calls,deps=predecessor();values['review_config']['argv']=[]
        with self.assertRaises(ValueError):core.verify_closed_predecessor(bundle,**deps)
        self.assertFalse(any(x.startswith(('process:','unit:','group:')) for x in calls))


if __name__=='__main__':
    time.sleep(2)  # Preserve a bracketable original CPU service birth.
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(name.startswith('dqn.') for name in sys.modules)
    print(json.dumps(dict(schema='robotron-startup-probe-coordinator-CPU-contracts-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Pure coordinator with fake clock/runtime and fake archived predecessor evidence; no process/unit/device queries, socket, numerical modules, emulator or real probe.',
        production_changed=False,runtime_adapter_present=False,launch_selected=False,
        protocol_selected=False,real_ROM_start_proven=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
