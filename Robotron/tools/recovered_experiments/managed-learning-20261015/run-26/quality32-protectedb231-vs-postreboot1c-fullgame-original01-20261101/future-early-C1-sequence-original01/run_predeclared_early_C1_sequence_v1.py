"""Own exactly one original R1/C1/R2/C2 sequence and its independent reviews.

Every native/review is launched once through the pinned owned controller and
waited/released before the next. Any invalid original leg stops the sequence.
Display projections are separate from scientific acceptance. Default inert.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import urllib.request

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CASE=G/'logs/managed-learning-20261015/run-26/quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'


ACTIVE_CASE=CASE
EARLY_ASSESSOR_SHA='9a296e50b1ec1e9e0d7111fbab0db9d326ad226f832f386119f14a92d76282ad'
EARLY_NUMERIC_SHA='7c5ceadf9b155d2d80067729079d9eb75c6be38a9a6755f034ac3f68fcf1e2a4'


class EarlyC1Rejected(Exception):pass


def validate_future_prepared(job,prepared,h):
    case=Path(prepared['campaign_directory'])
    require(case.is_absolute()and case.resolve()==case and case.is_relative_to(G/'logs/managed-learning-20261015/run-26')
        and case!=ACTIVE_CASE and prepared['pair']['sha256']!='9ea5d482628964107a0543665239c5147599e543c0e3ecd0d51b759e8c7e6b62',
        'Fresh future campaign required; active original campaign excluded')
    read=lambda pin:json.loads(h.checked(pin).read_text())
    family=read(prepared['source_family']);rule=read(prepared['early_C1_rule'])
    require(prepared['sequence_source']==job['runtime']==h.pin(__file__)
        and family['sequence_source']==job['runtime']and family['pair']==prepared['pair']
        and family['early_C1_assessor']==prepared['early_C1_assessor']
        and family['early_C1_numeric']==prepared['early_C1_numeric']
        and family['early_C1_rule']==prepared['early_C1_rule']
        and prepared['early_C1_assessor']['sha256']==EARLY_ASSESSOR_SHA
        and prepared['early_C1_numeric']['sha256']==EARLY_NUMERIC_SHA,
        'Future sequence/rule/assessor/numeric source family differs')
    require(rule['schema']=='robotron-predeclared-fullgame-C1-failure-rule-v1'
        and rule['campaign_directory']==str(case)and rule['pair']==prepared['pair']
        and rule['required_closed_roles']==['R1','C1','R2']
        and rule['stage']=='after_R2_review_before_C2_launch'
        and rule['skip_C2_only_if_C1_gate_failed']is True and rule['promotion_shortcut_allowed']is False
        and rule['assessor']==prepared['early_C1_assessor']and rule['numeric_gate']==prepared['early_C1_numeric']
        and rule['scheduler']==job['runtime'],'Exact predeclared future decision rule required')
    for leg in prepared['legs']:
        native=read(leg['native_job'])
        require(native['source_family_manifest']==prepared['source_family']
            and native['quality_pair_precommit']==prepared['pair']and prepared['early_C1_rule']in native['inputs']
            and not Path(native['output']).exists()
            and not(Path(leg['directory'])/'controller-original-launch.json').exists(),
            'All four fresh native jobs must precommit this same rule; no adoption/retry')
    return case


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def atomic(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();tmp=path.with_name(path.name+'.sequence-next')
    with tmp.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def optional(path,limit=16<<20):
    try:
        with Path(path).open('rb')as stream:raw=stream.read(limit+1)
        require(len(raw)<=limit,'Bounded display input exceeded')
        return json.loads(raw)
    except (FileNotFoundError,json.JSONDecodeError):return None


def project_display(leg,stage,job,native_status,loaded,review=None):
    label='Protected champion'if leg['model_role']=='reference'else'Candidate'
    cohort={};phase=stage;reason=None
    if native_status is not None:
        require(native_status['original_job']==leg['native_job'],'Display received a foreign native job')
        controller=native_status['controller'];cohort=controller.get('cohort')or{}
        phase=controller.get('phase')or stage
        if controller.get('valid')is False:reason=controller.get('reason')
    if review is not None:cohort=review['cohort'];phase='complete'
    if stage=='reviewing':phase='independent_review';reason='Checking complete game and runtime records'
    display=dict(label=label,phase=phase,valid=True if review is not None else None,
        complete=review is not None,reason=reason,cohort={k:cohort.get(k)for k in ('count','started','pending','mean','median','se','start_ts','close_ts')})
    if loaded is not None:
        policy=loaded['policy'];require(policy['checkpoint_sha256']==job['checkpoint']['sha256'],'Display loaded role policy differs')
        display.update(checkpoint_sha256=policy['checkpoint_sha256'],clocks={k:policy[k]for k in ('learner_frame_count','training_steps','optimized_samples')})
    return display


class Sequence:
    def __init__(self,job,h):
        self.job=job;self.h=h;self.prepared=json.loads(h.checked(job['prepared']).read_text())
        validate_future_prepared(job,self.prepared,h)
        require(self.prepared['campaign_directory']==str(CASE)and [r['role']for r in self.prepared['legs']]==['R1','C1','R2','C2'],
            'Exact four-role original sequence required')
        self.reader=load('_fixed_sequence_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
        self.archive=load('_fixed_sequence_archive',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
        self.seq=load('_fixed_sequence_original_scope_owner',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py')
        self.native_controller=load('_fixed_sequence_native_control',h.checked(self.prepared['native_controller']))
        self.cpu_controller=load('_fixed_sequence_CPU_control',h.checked(self.prepared['CPU_controller']))
        self.lock=threading.Lock();self.publish_lock=threading.Lock();self.stop=threading.Event();self.worker=None
        self.state=dict(stage='prepared',current=None,finished={},terminal=False,error=None,assessment=None)
        self.display_errors=[];self.results=[]

    def read(self,pin,as_json=True):return self.reader.read_pin(pin,as_json=as_json)

    def update(self,**values):
        with self.lock:self.state.update(values)

    def publish(self):
        with self.publish_lock:self.publish_locked()

    def publish_locked(self):
        with self.lock:state=copy.deepcopy(self.state)
        current=state['current'];now=time.time();progress=[];current_display=None
        for leg in self.prepared['legs']:
            role=leg['role'];finished=state['finished'].get(role)
            entry=dict(index=leg['index'],role=leg['model_role'],state='pending')
            if finished is not None:
                entry.update(state='finished',receipt_path=leg['display_receipt_path'])
            elif state['stage']=='rejected_after_C1'and role=='C2':
                display=dict(label='Candidate',phase='skipped',valid=None,complete=False,
                    reason='C1 failed its mean or median gate; C2 was not started',cohort={})
                atomic(Path(leg['display_live_path']),display)
                entry.update(state='skipped',evaluator_status_path=leg['display_live_path'])
            elif current==role:
                job=self.read(leg['native_job']);out=Path(job['output'])
                raw=optional(out/'status.json');loaded=optional(out/'original-loaded-policy.json',1<<20)
                display=project_display(leg,state['stage'],job,raw,loaded)
                atomic(Path(leg['display_live_path']),display);current_display=display
                entry.update(state='reviewing'if state['stage']=='reviewing'else'running',
                    evaluator_status_path=leg['display_live_path'],started_unix_s=state.get('started_unix_s'))
            progress.append(entry)
        status=dict(state='failed'if state['error']else'finished'if state['terminal']else'running',
            current_leg=next((r['index']for r in self.prepared['legs']if r['role']==current),None),
            updated_unix_s=now,legs=progress,outcome=('not_improved_C1'if state['stage']=='rejected_after_C1'else
                None if state['assessment']is None else
                'qualified_pending_protection'if state['assessment'].get('all_candidate_gates_passed')else'not_improved'),
            reason=state['error']or('C1 failed; C2 was not started'if state['stage']=='rejected_after_C1'else
                'All original legs reviewed; final assessment complete'if state['terminal']else'All selected full games and independent review required'))
        atomic(CASE/'status.json',status)
        current_label=current or'Preparation';cohort=(current_display or{}).get('cohort')or{}
        if state['error']:
            title='Confirmation stopped: original records need review';detail='The original invalid result is preserved. No policy promotion.'
        elif state['stage']=='rejected_after_C1':
            title='Candidate failed C1; C2 was not started';detail='Three original full-game cohorts were independently reviewed. Main training continues.'
        elif state['stage']=='early_C1_assessment':
            title='Checking C1 against the fresh reference';detail='All three full-game cohorts are reviewed; checking whether C2 is still required.'
        elif state['terminal']:
            title='Full-game confirmation finished; assessment available';detail='Original games, independent reviews and the fixed C1/C2 gates are recorded. Main training continues.'
        elif state['stage']=='reviewing':
            title=f'{current_label}: independently reviewing complete games';detail='Checking all selected game, authorization, shutdown and trainer-health records.'
        else:
            count=cohort.get('count');started=cohort.get('started')
            title=f'{current_label}: full-game confirmation running'
            detail=f'{count or 0} of64 selected games complete; {started or 0} starts recorded. Finished clients retire while remaining selected games continue.'
            if current_display is None or not cohort.get('started'):detail='Loading the fixed policy and starting the original32-client cohort. Main training continues.'
        public=dict(schema='robotron-prepared-policy-screening-status-v1',study_directory=str(CASE),state=status['state'],
            stage=state['stage'],current_leg=current,updated_unix_s=now,observation_unix_s=now,quality_qualified=False,promotion=False,
            main_training_continues=True,legs=progress,
            next_work=dict(state=state['stage'],current_stage=title,detail=detail,
                waiting_for='All selected full games and independent review'if not state['terminal']else'Final result processing',
                next_stage='Select the next candidate'if state['stage']=='rejected_after_C1'else
                    'Next original cohort'if not state['terminal']else'Apply the independently assessed promotion gates',
                eta='Game completion has no fixed estimate; each cohort has a six-hour safety limit. No unfinished game is treated as completed.',
                main_training_continues=True,mode_installed=True,main_mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',updated_unix_s=now,observation_unix_s=now))
        atomic(G/'html/next-policy-evaluation.json',public)
        atomic(CASE/'sequence-heartbeat.json',dict(owner_pid=os.getpid(),owner_birth=birth(os.getpid()),updated_unix_s=now,
            stage=state['stage'],current_leg=current,terminal=state['terminal'],display_errors=len(self.display_errors)))

    def reporter(self):
        while not self.stop.is_set():
            try:self.publish()
            except Exception as error:
                if len(self.display_errors)<32:self.display_errors.append(dict(unix_s=time.time(),error=repr(error)))
            self.stop.wait(5)

    def invoke(self,directory,config_pin,controller_pin,controller):
        result=self.seq.invoke_controller_once(directory,'',controller_pin,config_pin,self.h)
        close=self.seq.verify_closed_scope(directory,'',config_pin,self.h,self.read,self.archive,controller,exit_zero=False)
        code=self.read(close['result'])['actual_exit']
        return result,close,code

    def CPU_config(self,directory,unit,runtime,jobpin):
        controller=self.cpu_controller
        config=dict(unit=unit,output=str(directory/'execution-original01'),
            argv=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',runtime['path'],'--execute','--job',jobpin['path'],'--job-sha256',jobpin['sha256']],
            properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
            pins=[controller.pin(pin['path'])for pin in (runtime,jobpin)],observation_s=660)
        return self.h.put(directory/'controller-config.json',config)

    def assess_C1_before_C2(self):
        require([r['role']for r in self.results]==['R1','C1','R2'],
            'Exactly three original completed and reviewed legs required before early assessment')
        h=self.h;self.update(stage='early_C1_assessment',current=None)
        directory=CASE/'early-C1-assessment-CPU-original01';directory.mkdir(mode=0o700)
        job=h.put(directory/'job.json',dict(schema='robotron-predeclared-early-C1-three-leg-assessment-v1',
            runtime=self.prepared['early_C1_assessor'],campaign_directory=str(CASE),pair=self.prepared['pair'],
            source_family=self.prepared['source_family'],original_decision_kernel=self.prepared['original_decision_kernel'],
            numeric_gate=self.prepared['early_C1_numeric'],numeric_CPU_proof=self.prepared['early_C1_numeric_CPU_proof'],
            predeclared_rule=self.prepared['early_C1_rule'],legs=self.results,report=str(directory/'report.json')))
        cfg=self.CPU_config(directory,'robotron-fullgame-early-C1-CPU-original01.service',self.prepared['early_C1_assessor'],job)
        _,closed,code=self.invoke(directory,cfg,self.prepared['CPU_controller'],self.cpu_controller)
        report_pin=h.pin(directory/'report.json')if(directory/'report.json').exists()else None
        report=self.read(report_pin)if report_pin else None
        require(code==0 and report is not None and report['status']=='PASS_AUTHENTICATED_PREDECLARED_C1_FAILURE_ASSESSMENT'
            and report['valid']is True and report['original_job']==job
            and report['runtime']==self.prepared['early_C1_assessor']
            and report['pair']==self.prepared['pair']and report['source_family']==self.prepared['source_family']
            and report['predeclared_rule']==self.prepared['early_C1_rule']
            and type(report['stop_remaining_legs'])is bool and type(report['C2_required'])is bool
            and report['stop_remaining_legs']is not report['C2_required']
            and report['promotion_eligible']is False and report['cancellation_or_scheduling_performed']is False,
            'Original early assessment failed or used a foreign decision; no rescue/retry')
        h.put(directory/'positive-original-early-assessment-closeout.json',dict(actual_exit=code,
            original_Popen_reaped=True,all_original_controller_resources_closed=True,
            original_result=closed['result'],closure=closed['closure'],owner=closed['owner'],report=report_pin))
        if report['stop_remaining_legs']:
            self.update(assessment=report,stage='rejected_after_C1',current=None)
            raise EarlyC1Rejected('C1 gate failed; C2 must remain unstarted')
        return report_pin

    def run(self):
        h=self.h;error=None;actual_exit=1
        owner=h.put(CASE/'original-sequence-owner.json',dict(pid=os.getpid(),birth=birth(os.getpid()),parent_pid=os.getppid(),
            boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),runtime=h.pin(__file__),job=h.pin(self.job['job_path']),
            original_attempt=1,no_retry=True,started_unix_s=time.time()))
        self.worker=threading.Thread(target=self.reporter,name='fixed-fullgame-status-reporter',daemon=True);self.worker.start()
        try:
            for leg in self.prepared['legs']:
                role=leg['role'];directory=Path(leg['directory']);job=self.read(leg['native_job'])
                self.update(stage='native_running',current=role,started_unix_s=time.time())
                _,closed,code=self.invoke(directory,leg['native_controller_config'],self.prepared['native_controller'],self.native_controller)
                resultpin=h.pin(Path(job['output'])/'result.json')if(Path(job['output'])/'result.json').exists()else None
                result=self.read(resultpin)if resultpin else None
                require(code==0 and result is not None and result['complete']is True and result['errors']==[],
                    f'Original {role} native invalid (actual exit{code}); no retry or replacement')
                require(len(result['original_slots'])==32 and result['all_original_threads_stopped']is result['original_lease_released']is True
                    and all(type(r['actual_exit'])is int and r['actual_exit']==0 and birth(r['pid'])!=r['birth']
                        and r['outputs_sealed_after_original_writer_closure']is True for r in result['original_slots'].values()),
                    'Original native children, threads or writer seals remain incomplete')
                native_close=h.put(leg['native_closeout_path'],dict(status='PASS_ORIGINAL_FULLGAME_LEG_NATIVE_SCOPE_CLOSED',
                    actual_exit=code,original_job=leg['native_job'],original_controller_config=leg['native_controller_config'],
                    original_result=closed['result'],closure=closed['closure'],owner=closed['owner'],native_result=resultpin,
                    original_Popen_reaped=True,all_original_controller_resources_closed=True,scientific_review_pending=True))
                self.update(stage='reviewing')
                review_template=self.read(leg['review_job_template']);review_template.pop('original_native_closeout_path')
                review_template['original_native_closeout']=native_close
                rd=directory/'independent-review-original01';review_job=h.put(rd/'job.json',review_template)
                review_cfg=self.CPU_config(rd,f'robotron-b231-1c-{role.lower()}-review-CPU-original01-20261101.service',self.prepared['leg_reviewer'],review_job)
                _,review_closed,review_code=self.invoke(rd,review_cfg,self.prepared['CPU_controller'],self.cpu_controller)
                review_pin=h.pin(rd/'report.json')if(rd/'report.json').exists()else None
                review=self.read(review_pin)if review_pin else None
                require(review_code==0 and review is not None and review.get('valid')is True and review.get('full_game_score_verified')is True,
                    f'Original {role} independent review invalid (actual exit{review_code}); no corrected-review rescue')
                review_close=h.put(leg['review_closeout_path'],dict(status='PASS_ORIGINAL_FULLGAME_LEG_REVIEW_SCOPE_CLOSED',actual_exit=review_code,
                    original_Popen_reaped=True,all_original_controller_resources_closed=True,original_result=review_closed['result'],
                    closure=review_closed['closure'],owner=review_closed['owner'],report=review_pin,controller_config=review_cfg))
                loaded=optional(Path(job['output'])/'original-loaded-policy.json',1<<20)
                display=project_display(leg,'complete',job,None,loaded,review);atomic(Path(leg['display_receipt_path']),display)
                self.results.append(dict(role=role,prepared=leg['native_prepared'],native_closeout=native_close,review_closeout=review_close))
                with self.lock:self.state['finished'][role]=dict(review=review_pin)
                self.publish()
                if role=='R2':self.assess_C1_before_C2()
            self.update(stage='campaign_assessment',current=None)
            directory=CASE/'campaign-assessment-CPU-original01';directory.mkdir(mode=0o700)
            assessment_job=h.put(directory/'job.json',dict(schema='robotron-fixed-b231-1c-four-leg-assessment-v1',runtime=self.prepared['campaign_assessor'],
                campaign_directory=str(CASE),pair=self.prepared['pair'],source_family=self.prepared['source_family'],
                original_decision_kernel=self.prepared['original_decision_kernel'],legs=self.results,report=str(directory/'report.json')))
            cfg=self.CPU_config(directory,'robotron-b231-1c-assessment-CPU-original01-20261101.service',self.prepared['campaign_assessor'],assessment_job)
            _,closed,code=self.invoke(directory,cfg,self.prepared['CPU_controller'],self.cpu_controller)
            report_pin=h.pin(directory/'report.json')if(directory/'report.json').exists()else None
            report=self.read(report_pin)if report_pin else None
            require(code==0 and report is not None and report['valid']is True,'Original four-leg assessment invalid')
            h.put(directory/'positive-original-assessment-closeout.json',dict(actual_exit=code,original_Popen_reaped=True,
                all_original_controller_resources_closed=True,closure=closed['closure'],owner=closed['owner'],report=report_pin))
            self.update(assessment=report,stage='complete',current=None);actual_exit=0
        except EarlyC1Rejected:
            actual_exit=0
        except Exception:
            error=traceback.format_exc();self.update(error=error,stage='invalid_original',current=self.state['current'])
        finally:
            self.update(terminal=True);self.stop.set()
            if self.worker is not None:self.worker.join(10)
            if self.worker is not None and self.worker.is_alive():error=(error or'')+'\nOriginal reporter thread remains';actual_exit=1
            try:self.publish()
            except Exception as exc:self.display_errors.append(dict(error=repr(exc)))
            h.put(CASE/'original-sequence-result.json',dict(actual_exit=actual_exit,error=error,owner=owner,original_attempt=1,no_retry=True,
                original_legs=self.results,reporter_thread_closed=self.worker is None or not self.worker.is_alive(),
                display_errors=self.display_errors,assessment=self.state['assessment'],promotion_performed=False,completed_unix_s=time.time()))
        print(json.dumps(dict(original_sequence_actual_exit=actual_exit,completed_original_legs=len(self.results),error=error)),flush=True)
        return actual_exit


def main():
    global CASE
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--job-sha256');args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    h=load('_fixed_fullgame_sequence_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    jp=h.pin(args.job);require(jp['sha256']==args.job_sha256,'Exact original sequence job required')
    job=json.loads(h.checked(jp).read_text());require(job['runtime']==h.pin(__file__),'Original sequence source changed')
    preflight=json.loads(h.checked(job['preflight']).read_text())
    require(preflight['status']=='PASS_FIXED_CONFIRMATION_PREFLIGHT'
        and preflight['prepared']==job['prepared'] and preflight['sequence_source']==job['runtime'],
        'Successful checks of these exact original sources and jobs required')
    prepared=json.loads(h.checked(job['prepared']).read_text())
    CASE=validate_future_prepared(job,prepared,h)
    active=json.loads((G/'logs/managed-learning-20261015/state.json').read_text()).get('active_quality_job')or{}
    require(active.get('directory')==str(CASE),'Future campaign must be explicitly registered before execution')
    job['job_path']=str(args.job);return Sequence(job,h).run()


if __name__=='__main__':raise SystemExit(main())
