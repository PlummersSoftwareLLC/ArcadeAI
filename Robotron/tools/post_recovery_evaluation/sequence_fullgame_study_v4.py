"""One original recovered-round fullgame RCRC sequence; default inert.

Reuses the validated owned Popen/controller helper. No adoption, retry, model
installation, main-process signal, or unrelated-service/GPU workload change.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
HELPER_SHA='b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4'


def pipeline():
    spec=importlib.util.spec_from_file_location('_fullgame_sequence_pipeline',HERE/'fullgame_review_pipeline_v3.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def original_helper(p,h):
    path=p.ROOT/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py'
    p.require(h.pin(path)['sha256']==HELPER_SHA,'Actual owned-controller sequence helper changed')
    return p.load('_fullgame_original_owned_controller_helper',path)


def walk_original_phases(cases,native,review,assessment,before):
    """A failure or stop propagates before the next original can be scheduled."""
    if [case['leg']for case in cases]!=['R1','C1','R2','C2']:raise ValueError('Exact RCRC phase order required')
    records=[]
    for case in cases:
        before('native',case);n=native(case)
        before('review',case);r=review(case,n)
        records.append(dict(leg=case['leg'],native=n,review=r))
    before('assessment',None)
    return records,assessment(records)


def prepare(review_precommit,assessment_packet,output):
    p=pipeline();h=p.helpers();rp=h.pin(review_precommit.resolve());reviews=p.read(rp)
    p.require(reviews['schema']=='robotron-four-fullgame-independent-review-precommit-v1'and reviews['engineering_only']is False,
        'Engineering review precommit cannot prepare a scientific sequence')
    ap=h.pin(assessment_packet.resolve());assessment=p.read(ap)
    p.require(assessment['schema']=='robotron-fullgame-final-assessment-CPU-preparation-v1'
        and assessment['review_precommit']==rp and assessment['assessment_launched']is False,
        'Exact unlaunched final assessment preparation required')
    prepared=p.read(reviews['native_prepared'])
    producer=p.load('_fullgame_sequence_production_eligibility',HERE/'prepare_fullgame_study_v2.py')
    producer.eligible_screen(prepared['screen_assessment'],prepared['reference_epoch'],h)
    p.require(prepared['engineering_only']is False and reviews['ordered_legs']==prepared['ordered_legs']==p.ORDER,
        'Exact production RCRC preparation required')
    publication=p.read(reviews['CPU_guard_publication']);p.require(publication['status']=='PASS'
        and publication['prepared']==reviews['native_prepared'],'Actual exact-job CPU guard publication required')
    guards={case['leg']:case for case in publication['cases']};cases=[]
    sources=[rp,ap,reviews['native_prepared'],reviews['CPU_guard_publication'],h.pin(HERE/'fullgame_review_pipeline_v3.py'),
        h.pin(HERE/'assess_fullgame_study_v4.py'),h.pin(Path(__file__).resolve()),h.pin(p.CPU_CONTROLLER)]
    helper=original_helper(p,h);sources.append(h.pin(Path(helper.__file__)))
    for case,review in zip(prepared['cases'],reviews['cases']):
        guard=guards[case['leg']];p.require(review['native_job']==guard['native_job']==case['native_job'],'Exact original job join differs')
        packet=p.read(review['review_job']);cfg=p.read(review['review_config']);p.validate_packet(case,packet,cfg,h)
        p.require(packet['controller_config']==guard['qualified_controller_config'],'Exact qualified native configuration required')
        cases.append(dict(**case,qualified_native_config=guard['qualified_controller_config'],review=review))
        sources += [case['native_job'],case['runtime'],guard['qualified_controller_config'],review['review_job'],review['review_config']]
    output=output.resolve();p.require(output.is_relative_to(p.BASE)and output.parent.is_dir()and not output.exists(),'Exclusive original sequence output required')
    output.mkdir(mode=0o700)
    return h.put(output/'sequence-precommit.json',dict(schema='robotron-recovered-fullgame-sequence-precommit-v1',review_precommit=rp,
        native_prepared=reviews['native_prepared'],assessment_preparation=ap,cases=cases,ordered_legs=p.ORDER,
        protected_reference_epoch=prepared['reference_epoch'],source=h.pin(Path(__file__).resolve()),
        pipeline=h.pin(HERE/'fullgame_review_pipeline_v3.py'),owned_controller_helper=h.pin(Path(helper.__file__)),
        inputs=list({pin['path']:pin for pin in sources}.values()),output=str(output),original_attempts_per_phase=1,
        no_retry=True,engineering_only=False,scientific_payload_launched=False,promotion=False))


class StopNewActions(Exception):pass


class Sequence:
    def __init__(self,precommit,expected_sha):
        self.p=pipeline();self.h=self.p.helpers();self.pin=self.h.pin(precommit.resolve())
        self.p.require(self.pin['sha256']==expected_sha,'Exact sequence precommit required')
        self.job=self.p.read(self.pin)
        self.p.require(self.job['schema']=='robotron-recovered-fullgame-sequence-precommit-v1'
            and self.job['engineering_only']is False and self.job['original_attempts_per_phase']==1 and self.job['no_retry']is True
            and self.job['source']==self.h.pin(Path(__file__).resolve())and self.job['pipeline']==self.h.pin(HERE/'fullgame_review_pipeline_v3.py'),
            'Production original sequence/source binding required')
        self.helper=original_helper(self.p,self.h);self.root=Path(self.job['output']);self.events=self.root/'events'
        self.state=self.p.ROOT/'logs/managed-learning-20261015/state.json';self.number=0;self.closed=False
        self.prepared=self.p.read(self.job['native_prepared']);self.reviews=self.p.read(self.job['review_precommit'])
        self.assessment=self.p.read(self.job['assessment_preparation'])

    def check_new_actions(self):
        control=self.root/'stop-new-actions.json'
        if control.exists()and json.loads(control.read_bytes()).get('stop_new_actions')is True:raise StopNewActions('Operator requested no new original actions')
        state=json.loads(self.state.read_bytes());active=state.get('active_quality_job')or{}
        if active.get('directory')!=str(self.root):raise StopNewActions('Canonical active sequence changed; no new actions')
        self.p.require(state['optimization_goal']['next_fixed_reference_epoch']==self.job['protected_reference_epoch'],
            'Protected reference changed before the next original action')
        for pin in self.job['inputs']:self.h.checked(pin)

    def project(self,stage,role,owner=None,child=None,*,initial=False,terminal=False):
        self.number+=1
        event=self.h.put(self.events/f'{self.number:04d}-{stage.lower()}.json',dict(stage=stage,role=role,
            sequence_precommit=self.pin,sequence_pid=os.getpid(),sequence_birth=self.helper.birth(os.getpid()),
            original_owner=owner,original_controller=child,observed_unix_s=time.time(),promotion=False))
        for attempt in range(3):
            raw=self.state.read_bytes();s=json.loads(raw);g=s['optimization_goal'];active=s.get('active_quality_job')
            if initial:
                self.p.require(not active and not g.get('scientific_job_running')and not g.get('performance_job_running'),
                    'Another scientific/performance job is active')
                s['active_quality_job']=dict(directory=str(self.root),state='running',current_leg=1,sequence_precommit=self.pin)
            else:self.p.require(active and active.get('directory')==str(self.root),'Canonical active sequence changed')
            stopped=stage=='STOPPED_NO_NEW_ACTIONS_REQUIRES_OWNED_SCOPE_AUDIT'
            current=s['active_quality_job'];current.update(stage=stage,current_leg=self.p.ORDER.index(role)+1 if role in self.p.ORDER else 4,
                sequence_latest_event=event,state='finished'if terminal else'stopped'if stopped else'running')
            previous_wait=g.get('actual_running_wait')or{}
            previous_owner=previous_wait.get('scope')or{}
            g['scientific_job_running']=bool(owner)or(stopped and bool(previous_owner)
                and self.helper.birth(previous_owner['pid'])==previous_owner['starttime_ticks'])
            if stopped:current['pending_owned_scope_audit']=True
            g['last_progress']='Original recovered fullgame sequence: '+stage+' '+role+'. No retry or policy install.'
            if terminal:g['actual_running_wait']=None
            elif stopped:g['actual_running_wait']=dict(previous_wait,sequencing_stopped=True,pending_owned_scope_audit=True)
            else:g['actual_running_wait']=dict(kind=stage,quality_leg=role,sequence_pid=os.getpid(),
                sequence_birth=self.helper.birth(os.getpid()),scope=owner,controller=child,sequence_precommit=self.pin)
            encoded=(json.dumps(s,separators=(',',':'),allow_nan=False)+'\n').encode();self.p.require(len(encoded)<1<<20,'Canonical reader size bound exceeded')
            backup=self.root/f'state-before-event-{self.number:04d}-{attempt}.exact.json'
            with backup.open('xb')as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
            if self.state.read_bytes()!=raw:continue
            tmp=self.state.with_name(f'state.fullgame-sequence-{os.getpid()}-{self.number}.tmp')
            with tmp.open('xb')as stream:stream.write(encoded);stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
            self.p.require(self.state.read_bytes()==raw,'Concurrent canonical update; no overwrite');os.replace(tmp,self.state)
            fd=os.open(self.state.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd);return event
        raise ValueError('Canonical compare-and-swap collisions; no further scheduling')

    def preflight(self,case):
        p,h=self.p,self.h;subject=p.read(case['native_job'])
        native=p.load('_fullgame_sequence_actual_native',HERE/'run_fullgame_rounds_v3.py');ctx=native.validate_completed_context(subject,h)
        native.round_contract().validate_launch(subject,case['native_job'],ctx,h)
        h.checked(subject['lease']);fd=os.open(subject['lease']['path'],os.O_RDONLY|os.O_NOFOLLOW)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)
        for port in [subject['origin_port'],*subject['proxy_ports'].values()]:
            with socket.socket()as probe:probe.bind(('0.0.0.0',port))
        gpu=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=10)
        p.require(gpu.returncode==0 and subject['gpu_uuid']not in gpu.stdout,'Dedicated evaluation GPU is not idle; no scientific scheduling')
        health=p.load('_fullgame_sequence_live_health',h.checked(ctx['family']['main_observer']['health']))
        worker=p.load('_fullgame_sequence_live_collector',h.checked(ctx['family']['main_observer']['worker']))
        end=time.monotonic()+15
        while True:
            try:sample=worker.collect(health,ctx['binding']);health.validate(ctx['binding'],sample);health.check_inputs(ctx['binding'],full=True);break
            except(ValueError,OSError):
                p.require(time.monotonic()<end,'Fresh coherent original main domain unavailable');time.sleep(.02)
        return dict(raw=sample,GPU_readback=gpu.stdout,case=case['native_job'])

    def invoke(self,directory,prefix,source,config,role):
        self.check_new_actions()
        self.helper.invoke_controller_once(directory,prefix,source,config,self.h,
            lambda owner,child:self.project('ORIGINAL_SCOPE_RUNNING',role,owner,child))
        result_pin=self.h.pin(directory/(prefix+'controller-original-result.json'));result=self.p.read(result_pin)
        self.p.require(type(result['actual_exit'])is int and result['actual_exit']==0 and result['original_attempt']==1
            and result['no_retry']is True and result['live_registration_errors']==[],
            'Original controller failed, registration failed or retried; no further phase')
        return result_pin

    def before(self,kind,case):
        self.check_new_actions()
        if kind=='native':
            proof=self.preflight(case);self.h.put(self.root/('preflight-'+case['leg']+'.json'),proof)
        if kind=='assessment':self.project('ORIGINAL_ASSESSMENT_PENDING','assessment')

    def native(self,case):
        root=Path(case['native_job']['path']).parent
        self.invoke(root,'',case['controller'],case['qualified_native_config'],case['leg'])
        closed=self.p.owned_scope(case['qualified_native_config'],self.h,native=True)
        subject=self.p.read(case['native_job']);reviewer=self.p.load('_fullgame_sequence_native_predicates',HERE/'review_fullgame_rounds_v3.py')
        reviewer.validate_runtime_result(self.p.read(self.h.pin(Path(subject['output'])/'result.json')),subject)
        self.project('ORIGINAL_NATIVE_CLOSED',case['leg'])
        return dict(owner=closed['owner_pin'],closure=closed['closure_pin'])

    def review(self,case,native):
        record=case['review'];root=Path(case['native_job']['path']).parent
        self.invoke(root,'independent-review-',record['controller'],record['review_config'],case['leg'])
        closed=self.p.owned_scope(record['review_config'],self.h)
        report_pin=self.h.pin(root/'independent-quality-leg-review-original01/review.json');report=self.p.read(report_pin)
        self.p.require(report['valid']is report['full_game_score_verified']is True and report['quality_qualified']is report['promotion']is False
            and report['review_job']==record['review_job']and report['original_native_job']==case['native_job']
            and report['quality_leg']==case['leg'],'Original independent scientific review invalid; no next leg')
        self.project('ORIGINAL_LEG_VALIDATED',case['leg'])
        return dict(owner=closed['owner_pin'],closure=closed['closure_pin'],report=report_pin)

    def assess(self,records):
        cfg_pin=self.assessment['config'];cfg=self.p.read(cfg_pin);root=Path(cfg['output']).parent
        carrier=self.invoke(root,'campaign-assessment-',self.assessment['controller'],cfg_pin,'assessment')
        closed=self.p.owned_scope(cfg_pin,self.h);report_pin=self.h.pin(self.assessment['prospective_assessment_output']);report=self.p.read(report_pin)
        self.p.require(report['schema']=='robotron-recovered-round-fullgame-study-assessment-v1'
            and report['status']=='FOUR_ORIGINAL_COMPLETE_GAME_LEGS_QUALIFIED'
            and report['review_precommit']==self.job['review_precommit']and report['native_prepared']==self.job['native_prepared']
            and report['source']==self.reviews['assessor']and report['promotion']is False,
            'Actual original final assessment missing or belongs to another study')
        closeout=self.h.put(root/'independent-final-assessment-original-closeout.json',dict(
            schema='robotron-recovered-fullgame-final-assessment-original-closeout-v1',status='PASS',
            assessment=report_pin,assessment_preparation=self.job['assessment_preparation'],original_config=cfg_pin,
            original_controller_result=carrier,original_owner=closed['owner_pin'],original_closure=closed['closure_pin'],
            actual_exit=0,actual_CPU_cores=2,actual_memory_bytes=4<<30,actual_runtime_max_s=1980,
            all_six_descriptors_resources_argv_birth_unit_timer_cgroup_and_release_verified=True,
            source=self.h.pin(Path(__file__).resolve()),promotion=False))
        self.closed=True
        self.project('QUALIFIED_PENDING_PROTECTION'if report['full_game_quality_qualified']else'VALID_NOT_IMPROVED','assessment',terminal=True)
        return dict(report=report_pin,closeout=closeout,full_game_quality_qualified=report['full_game_quality_qualified'],promotion=False)

    def run(self):
        for pin in self.job['inputs']:self.h.checked(pin)
        self.p.require(not self.events.exists()and not(self.root/'original-sequence-intent.json').exists(),'Original sequence attempt consumed; no adoption/restart')
        for case in self.job['cases']:
            for pin in (case['qualified_native_config'],case['review']['review_config']):
                cfg=self.p.read(pin)
                self.p.require(not Path(cfg['output']).exists(),'Original scope namespace consumed; no retry')
                control=self.p.cpu_controller(self.h)
                self.p.require(all(control.show(unit)['LoadState']=='not-found'for unit in (cfg['unit'],cfg['unit'].removesuffix('.service')+'.timer')),'Future original unit names must be unused')
        preflight=self.preflight(self.job['cases'][0])
        self.events.mkdir(mode=0o700)
        self.h.put(self.root/'original-sequence-intent.json',dict(precommit=self.pin,source=self.h.pin(Path(__file__).resolve()),
            pid=os.getpid(),birth=self.helper.birth(os.getpid()),original_attempt=1,no_retry=True,preflight=preflight))
        outcome=dict(schema='robotron-recovered-fullgame-sequence-outcome-v1',precommit=self.pin,promotion=False)
        try:
            self.project('ORIGINAL_SEQUENCE_REGISTERED','R1',initial=True)
            records,final=walk_original_phases(self.job['cases'],self.native,self.review,self.assess,self.before)
            outcome.update(status='FOUR_ORIGINAL_FULLGAME_LEGS_AND_ASSESSMENT_CLOSED',records=records,assessment=final)
        except StopNewActions as error:outcome.update(status='STOPPED_NO_NEW_ACTIONS',error=str(error))
        except Exception as error:outcome.update(status='ORIGINAL_FAILURE_PRESERVED_NO_RETRY',error=repr(error),traceback=traceback.format_exc())
        if not self.closed:
            # A failed controller may still have an owned payload. Preserve the
            # active registration for independent cleanup; never infer terminal.
            try:self.project('STOPPED_NO_NEW_ACTIONS_REQUIRES_OWNED_SCOPE_AUDIT','sequence')
            except Exception as error:outcome['canonical_projection_error']=repr(error)
        outcome['ended_unix_s']=time.time();result=self.h.put(self.root/'original-sequence-outcome.json',outcome)
        print(json.dumps(dict(outcome=result,status=outcome['status'],promotion=False)),flush=True)
        return 0 if self.closed else 1


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--prepare',action='store_true');a.add_argument('--run',action='store_true')
    a.add_argument('--reviews',type=Path);a.add_argument('--assessment',type=Path);a.add_argument('--output',type=Path)
    a.add_argument('--precommit',type=Path);a.add_argument('--precommit-sha256');args=a.parse_args()
    if args.prepare:print(json.dumps(prepare(args.reviews,args.assessment,args.output)),flush=True)
    elif args.run:sys.exit(Sequence(args.precommit,args.precommit_sha256).run())
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
