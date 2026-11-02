"""Future stdlib guards. All runtime operations use FakeOps; no real service/API/GPU reads."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('quality_closure_under_test',Path(__file__).with_name('close_quality_trial02.py'))
M=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)

class FakeOps:
    def __init__(self):
        self.events=[]; self.values={}; self.processes={}; self.health_error=None; self.show_fault=None; self.stop_error=None
        self.group='/saved/original-quality.service'
        self.units={M.UNIT:dict(LoadState='loaded',MainPID='0',ExecMainPID=str(M.PID),InvocationID=M.INV,
            ControlGroup='',NRestarts='0',ExecMainCode='1',ExecMainStatus='0',Result='success',ActiveState='active',SubState='exited'),
            M.TIMER:dict(LoadState='loaded',InvocationID='a'*32,Triggers=M.UNIT,ActiveState='active',SubState='elapsed')}
        identity=dict(pid=M.PID,starttime_ticks=M.START,invocation_id=M.INV,unit=M.UNIT)
        running=dict(MainPID=str(M.PID),InvocationID=M.INV,ControlGroup=self.group)
        self.launch={
            'original-controller-identity.json':identity,
            'original-controller-running-show.json':dict(stdout=self.encode(running)),
            'original-timer-show-after-carrier-reaped.json':dict(stdout=self.encode(self.units[M.TIMER]))}
    @staticmethod
    def encode(value): return '\n'.join(k+'='+str(v) for k,v in value.items())+'\n'
    @staticmethod
    def fields(text): return dict(line.split('=',1) for line in text.splitlines() if '=' in line)
    def read_file(self,path):
        name=Path(path).name
        return json.dumps(self.launch[name]).encode(),dict(sha256=M.LAUNCH_PINS[name])
    def pinned(self,pin): return copy.deepcopy(self.values[pin['path']])
    def show(self,unit):
        value=copy.deepcopy(self.units.get(unit,dict(LoadState='not-found')))
        if self.show_fault: self.show_fault(unit,value)
        return value,dict(argv=['systemctl','--user','show',unit,'--all'],returncode=0,stdout=self.encode(value),stderr='')
    def original_terminal(self,owner,value):
        M.require(value.get('MainPID')=='0' and value.get('ExecMainPID')==str(owner['pid'])
            and value.get('InvocationID')==owner['invocation_id'] and value.get('NRestarts')=='0'
            and value.get('ControlGroup') in ('',owner['cgroup']) and int(value.get('ExecMainCode',0))!=0,'Nonterminal/replaced original')
    def command(self,argv):
        self.events.append(('command',tuple(argv)))
        if argv[:3]==['systemctl','--user','stop']:
            self.units[argv[3]]=dict(LoadState='not-found')
            rc,err=self.stop_error or (0,'')
            return dict(argv=argv,returncode=rc,stdout='',stderr=err)
        return dict(argv=argv,returncode=0,stdout='' if argv[0]=='journalctl' else 'original unit text\n',stderr='')
    def publish(self,path,value):
        self.events.append(('durable',Path(path).name)); self.values[str(path)]=copy.deepcopy(value)
        return dict(path=str(path),sha256='f'*64,bytes=1,identity=dict(mode='0o444',nlink=1))
    def write_bytes(self,path,data,allow_empty=False):
        M.require(data or allow_empty,'Empty archive not authorized')
        return self.publish(path,dict(bytes=len(data)))
    def process_start(self,pid): return self.processes.get(pid)
    def cgroup_empty(self,path):
        self.events.append(('empty-cgroup',path))
        M.require(not self.processes.get('cgroup'),'Nonempty original cgroup')
    def current_ce_and_resources(self,*args):
        self.events.append(('health',))
        if self.health_error: raise RuntimeError(self.health_error)
        return dict(main192=True,GPU0_free=True,port9999_unused=True),b'{"client_count":192}'

def fixture(outcome='not_improved'):
    ops=FakeOps(); campaign='/future-actual-campaign'
    def pin(name,value):
        p=dict(path=name,sha256=(str(len(ops.values)%10)*64),bytes=1,identity=dict(mode='0o444',nlink=1))
        ops.values[name]=value; return p
    state=dict(state='finished',plan_sha256=M.PLAN_SHA,legs=[])
    summary=dict(outcome=outcome,plan_sha256=M.PLAN_SHA,legs=[])
    acceptance=dict(status='PASS_ROOT_ALL_FOUR',plan_sha256=M.PLAN_SHA,binding_job_sha256=M.BINDING_SHA,
        accepted_leg_indices=[1,2,3,4],campaign_outcome=outcome,leg_receipt_sha256=[],audit_receipt_sha256=[],
        audit_original_exit=[0]*4,independent_review_sha256=[],audit_disposition=['original_audit_valid']*4)
    cfg=dict(campaign=dict(output_directory=campaign),evidence={})
    for key,value in [('outer_job',{}),('activation_job',{}),('activation',{}),('ce_return',dict(owner=dict(
        pid=620749,starttime_ticks=33475842,invocation_id='3e0b59be7ec5484d9cc8d33265e74d77')))]:
        cfg['evidence'][key]=pin(key,value)
    binding=pin('binding',cfg); binding['sha256']=M.BINDING_SHA
    job=dict(schema='robotron-trial02-quality-owned-closure-job-v1',binding_job=binding,timer_invocation_id='a'*32,
        terminal_status=pin(campaign+'/status.json',state),terminal_summary=pin(campaign+'/summary.json',summary),
        root_acceptance=pin('root-acceptance',acceptance),legs=[],output_directory='unused')
    for n,label in enumerate(('R1','C1','R2','C2'),1):
        evaluator=dict(pid=10000+n,starttime_ticks=20000+n)
        actors=[dict(slot=4096+s,pid=n*100000+s,starttime_ticks=n*200000+s) for s in range(16)]
        receipt=pin('receipt'+str(n),dict(complete=True,active=False,valid=True,pending=0,abandoned=0,
            socket_wait=dict(actors={str(a['slot']):dict(pid=a['pid']) for a in actors})))
        original=dict(index=n,state='finished',returncode=0,pid=evaluator['pid'],role='reference' if n in (1,3) else 'candidate',receipt_path=receipt['path'])
        state['legs'].append(original); summary['legs'].append(dict(index=n,returncode=0,valid=True,receipt_sha256=receipt['sha256']))
        audit=pin('audit'+str(n),dict(leg=n,valid=True,plan_sha256=M.PLAN_SHA,receipt_sha256=receipt['sha256']))
        units=[f'robotron-rawkl-trial02-quality-leg{n:02d}-audit-reviewed1-20261017.'+suffix for suffix in ('timer','service')]
        execution=pin('execution'+str(n),dict(audit_receipt=audit,source_pins_held=True,original_archived_before_release=True,
            original_pid=30000+n,original_starttime_ticks=40000+n,original_invocation='c'*32,original_result='success',
            original_exec_code=1,original_exit=0,owned_release=[dict(unit=u,final_load_state='not-found') for u in units]))
        review=pin('review'+str(n),dict(status='PASS_SAVED',leg=n,actual_plan_sha256=M.PLAN_SHA,
            original_audit=dict(pid=30000+n,starttime_ticks=40000+n,invocation_id='c'*32,exec_code=1,exit_status=0,result='success'),
            original_evaluator=dict(pid=evaluator['pid']),key_artifacts=[copy.deepcopy(audit),copy.deepcopy(execution)]))
        observed={label+'_actors':actors}
        if n==1: observed.update(quality_owner=dict(pid=M.PID,starttime_ticks=M.START),quality_unit=dict(InvocationID=M.INV),evaluator=evaluator)
        else: observed.update(owners={M.UNIT:dict(pid=M.PID,starttime_ticks=M.START)},unit_show_all={M.UNIT:dict(InvocationID=M.INV)},**{label+'_evaluator':evaluator})
        job['legs'].append(dict(index=n,receipt=receipt,finished_record=pin('finished'+str(n),original),audit_receipt=audit,
            audit_execution=execution,independent_review=review,startup_observation=pin('startup'+str(n),copy.deepcopy(observed)),evaluator=evaluator,actors=actors))
        acceptance['leg_receipt_sha256'].append(receipt['sha256']); acceptance['audit_receipt_sha256'].append(audit['sha256'])
        acceptance['independent_review_sha256'].append(review['sha256'])
    return ops,job,cfg,acceptance

class QualityClosureGuards(unittest.TestCase):
    def close(self,ops,job):
        with tempfile.TemporaryDirectory() as directory:
            return M.close(job,dict(sha256='j'*64),Path(directory)/'new',ops)
    def stops(self,ops): return [x[1][-1] for x in ops.events if x[0]=='command' and x[1][:3]==('systemctl','--user','stop')]
    def test_default_plan_never_loads_operations(self):
        with patch.object(M,'load_ops',side_effect=AssertionError('input/runtime import')),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(M.main([]),0)
    def test_nonterminal_wrong_owner_and_restart_refuse_before_output(self):
        for key,value in [('MainPID','638119'),('ExecMainPID','7'),('InvocationID','b'*32),('NRestarts','1')]:
            with self.subTest(key=key):
                ops,job,_,_=fixture(); ops.units[M.UNIT][key]=value
                with self.assertRaises(RuntimeError): self.close(ops,job)
                self.assertFalse(ops.events)
    def test_not_improved_closes_without_qualification_or_source_release(self):
        ops,job,_,_=fixture(); result=self.close(ops,job)
        self.assertTrue(result['owned_cleanup_complete']); self.assertEqual(result['accepted_quality_outcome'],'not_improved')
        self.assertFalse(result['qualification_pass'] or result['source_freeze_released'] or result['publication'])
        self.assertEqual(self.stops(ops),[M.TIMER,M.UNIT])
        self.assertEqual(len(ops.values[result['pre_release_absence']['path']]['processes']),69)
        self.assertTrue(ops.values[result['post_release_absence']['path']]['cgroup_empty_or_absent'])
        self.assertIn('raw_API',result['post_release_health'])
    def test_full_both_archives_durable_before_first_stop_and_timer_has_no_mainpid(self):
        ops,job,_,_=fixture(); self.assertNotIn('MainPID',ops.units[M.TIMER]); self.close(ops,job)
        stop=next(i for i,x in enumerate(ops.events) if x[0]=='command' and x[1][:3]==('systemctl','--user','stop'))
        names={x[1] for x in ops.events[:stop] if x[0]=='durable'}
        self.assertTrue({'service-show.txt','service-cat.txt','service-journal.txt','timer-show.txt','timer-cat.txt','timer-journal.txt',
            'original-execution-before-any-release.json'}<=names)
    def test_failed_original_exit_preserved_and_no_release(self):
        ops,job,_,_=fixture(); ops.units[M.UNIT].update(ExecMainStatus='9',Result='exit-code')
        result=self.close(ops,job); self.assertFalse(result['owned_cleanup_complete']); self.assertEqual(result['original_execution']['exit_status'],9)
        self.assertFalse(self.stops(ops)); self.assertIn('original-execution-before-any-release.json',[x[1] for x in ops.events if x[0]=='durable'])
    def test_mismatched_latebound_receipt_refuses_after_archiving_before_release(self):
        ops,job,_,_=fixture(); ops.values['receipt4']['pending']=1
        result=self.close(ops,job); self.assertFalse(result['owned_cleanup_complete']); self.assertFalse(self.stops(ops))
    def test_supplied_wrong_private_start_rejected_against_saved_observation(self):
        ops,job,cfg,_=fixture(); job['legs'][3]['evaluator']['starttime_ticks']+=1
        with self.assertRaises(RuntimeError): M.final_proofs(ops,job,cfg,None)
    def test_explicit_root_accepted_narrow_manual_audit_preserves_exit2(self):
        ops,job,cfg,acceptance=fixture(); ops.values['audit1']=dict(leg=1,valid=False,result='needs_review')
        ops.values['execution1']['original_exit']=2; acceptance['audit_original_exit'][0]=2
        ops.values['review1']['original_audit']['exit_status']=2
        ops.values['execution1']['original_result']=ops.values['review1']['original_audit']['result']='exit-code'
        acceptance['audit_disposition'][0]='root_accepted_narrow_manual_review'
        result=M.final_proofs(ops,job,cfg,None); self.assertEqual(result['audit_original_exit'],[2,0,0,0])
        acceptance['audit_disposition'][0]='original_audit_valid'
        with self.assertRaises(RuntimeError): M.final_proofs(ops,job,cfg,None)
    def test_unknown_audit_exit_and_foreign_release_refused(self):
        for change in ('exit','unit'):
            with self.subTest(change=change):
                ops,job,cfg,_=fixture()
                if change=='exit': ops.values['execution2']['original_exit']=1
                else: ops.values['execution2']['owned_release'][0]['unit']='foreign.timer'
                with self.assertRaises(RuntimeError): M.final_proofs(ops,job,cfg,None)
    def test_unrelated_same_leg_pass_does_not_authenticate_execution(self):
        for change in ('pid','artifact'):
            with self.subTest(change=change):
                ops,job,cfg,_=fixture()
                if change=='pid': ops.values['review1']['original_audit']['pid']+=1
                else: ops.values['review1']['key_artifacts'][0]['sha256']='wrong'
                with self.assertRaises(RuntimeError): M.final_proofs(ops,job,cfg,None)
    def test_original_actor_and_original_cgroup_absence_required(self):
        for target in ('actor','cgroup'):
            with self.subTest(target=target):
                ops,job,_,_=fixture()
                if target=='actor': ops.processes[job['legs'][0]['actors'][0]['pid']]=job['legs'][0]['actors'][0]['starttime_ticks']
                else: ops.processes['cgroup']=1
                self.assertFalse(self.close(ops,job)['owned_cleanup_complete']); self.assertFalse(self.stops(ops))
    def test_port_gpu_and_extra_actor_resource_faults_do_not_release(self):
        for fault in ('Port9999 listener remains','GPU0 not free','Global Robotron MAME inventory differs'):
            with self.subTest(fault=fault):
                ops,job,_,_=fixture(); ops.health_error=fault
                self.assertFalse(self.close(ops,job)['owned_cleanup_complete']); self.assertFalse(self.stops(ops))
    def test_parent_replacement_after_preproof_stops_before_any_release(self):
        ops,job,_,_=fixture()
        def health(*args):
            ops.units[M.UNIT]['InvocationID']='b'*32; return {},b'{}'
        ops.current_ce_and_resources=health
        self.assertFalse(self.close(ops,job)['owned_cleanup_complete']); self.assertFalse(self.stops(ops))
    def test_timer_replacement_refuses_before_stop(self):
        ops,job,_,_=fixture()
        def health(*args):
            ops.units[M.TIMER]['InvocationID']='b'*32; return {},b'{}'
        ops.current_ce_and_resources=health
        self.assertFalse(self.close(ops,job)['owned_cleanup_complete']); self.assertFalse(self.stops(ops))
    def test_noncanonical_stop_error_preserves_failure_even_when_unit_disappears(self):
        ops,job,_,_=fixture(); ops.stop_error=(5,f'Unit {M.TIMER} not loaded.\nUnrelated error')
        self.assertFalse(self.close(ops,job)['owned_cleanup_complete']); self.assertEqual(self.stops(ops),[M.TIMER])
    def test_exact_bound_not_loaded_rc5_preserves_original_return(self):
        ops,job,_,_=fixture(); ops.stop_error=(5,f'Unit {M.TIMER} not loaded.')
        owner=M.original_owner(ops,job); releases=[]
        M.release_one(ops,job,owner,M.TIMER,lambda *args:None,releases)
        self.assertEqual(releases[0]['actual_stop_returncode'],5); self.assertTrue(releases[0]['released'])

if __name__=='__main__': unittest.main()
