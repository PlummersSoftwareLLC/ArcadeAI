"""One-use sequencing of the already running original R1 and fresh C1/R2/C2.

Never relaunch/adopt R1's controller; its existing wrapper owns observation and
release. Each later controller owns exactly one launch/observation in its own
process. No native/review retry, policy installation, main signal or promotion.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'tools/startup_policy_journal_proposal'
R=G/'logs/managed-learning-20261015/run-26'
ORDER=('R1','C1','R2','C2')
FOLDERS=('01-reference','02-candidate','03-reference','04-candidate')

def require(value,message):
    if not value:raise ValueError(message)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None

def invoke_controller_once(directory,prefix,source,config_pin,h,on_live=None):
    """One owned Popen; seal stdout/stderr only after that same child is reaped."""
    h.checked(source);config=json.loads(h.checked(config_pin).read_text())
    require(directory.is_absolute()and directory.is_dir(),'Existing exact output parent required')
    target=directory/(prefix+'controller-original-launch.json')
    require(not target.exists(),'Original controller scheduling attempt already consumed')
    argv=['/usr/bin/python3.12','-I','-B',source['path'],'--execute','--config',config_pin['path'],
        '--expected-source-sha256',source['sha256']]
    intent=h.put(target,dict(argv=argv,source=source,config=config_pin,original_attempt=1,no_retry=True,unix_s=time.time()))
    stdout_path=directory/(prefix+'controller-original-stdout.txt')
    stderr_path=directory/(prefix+'controller-original-stderr.txt')
    callback_errors=[];owner_seen=False
    with stdout_path.open('xb')as stdout,stderr_path.open('xb')as stderr:
        process=subprocess.Popen(argv,stdout=stdout,stderr=stderr,start_new_session=True)
        child=dict(pid=process.pid,starttime_ticks=birth(process.pid),observed_live=process.poll()is None)
        child_pin=h.put(directory/(prefix+'controller-original-child.json'),dict(**child,intent=intent))
        print(json.dumps(dict(event='ORIGINAL_CONTROLLER_STARTED',prefix=prefix,child=child_pin)),flush=True)
        while process.poll()is None:
            owner_path=Path(config['output'])/'root-original-identity.json'
            if not owner_seen and owner_path.exists()and owner_path.stat().st_mode&0o777==0o444:
                owner_seen=True
                try:
                    owner=json.loads(h.checked(h.pin(owner_path)).read_text())
                    if birth(owner['pid'])==owner['starttime_ticks']:
                        actual=[v.decode()for v in Path('/proc',str(owner['pid']),'cmdline').read_bytes().split(b'\0')[:-1]]
                        require(actual==config['argv'],'Actual original payload argv differs')
                        if on_live:on_live(owner,child)
                except Exception as error:callback_errors.append(repr(error))
            time.sleep(1)
        code=process.wait()
        stdout.flush();stderr.flush();os.fsync(stdout.fileno());os.fsync(stderr.fileno())
        os.fchmod(stdout.fileno(),0o444);os.fchmod(stderr.fileno(),0o444)
    closure=Path(config['output'])/'root-original-result-and-owned-release.json'
    result=h.put(directory/(prefix+'controller-original-result.json'),dict(actual_exit=code,
        original_attempt=1,no_retry=True,intent=intent,stdout=h.pin(stdout_path),stderr=h.pin(stderr_path),
        closure=h.pin(closure)if closure.exists()else None,live_registration_errors=callback_errors,ended_unix_s=time.time()))
    return result

def verify_closed_scope(directory,prefix,config_pin,h,read,rt,ctl,exit_zero=True):
    config=read(config_pin)
    result_pin=h.pin(directory/(prefix+'controller-original-result.json'));result=read(result_pin)
    owner_pin=h.pin(Path(config['output'])/'root-original-identity.json');owner=read(owner_pin)
    require(result['original_attempt']==1 and result['no_retry']is True and result.get('closure')is not None,
        'Original exact controller result/closure required')
    closure=read(result['closure']);fields=rt.archived_closure(closure,owner,read,exit_zero=exit_zero)
    require(result['actual_exit']==closure['original_exit']and (not exit_zero or result['actual_exit']==0),
        'Original controller/payload exits differ or failed')
    require(' '.join(config['argv'])+' ; ignore_errors=no ;'in fields['ExecStart'],
        'Actual original scoped command differs')
    require(birth(owner['pid'])!=owner['starttime_ticks'],'Original scoped process remains')
    for unit in (owner['unit'],owner['timer']):
        require(ctl.show(unit)['LoadState']=='not-found','Original owned unit remains')
        require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists(),
            'Original owned cgroup remains')
    for entry in config['pins']:require(ctl.pin(entry['path'])==entry,'Original scoped input changed')
    return dict(result=result_pin,owner=owner_pin,closure=result['closure'],fields=fields,identity=owner)

class StopNewActions(Exception):pass

class CampaignSequence:
    def __init__(self,precommit_pin,h,reader):
        self.h=h;self.read=lambda e,as_json=True:reader.read_pin(e,as_json=as_json)
        self.precommit_pin=precommit_pin;self.precommit=self.read(precommit_pin)
        self.ready_pin=self.precommit['launch_readiness'];self.ready=self.read(self.ready_pin)
        self.root=Path(self.ready['campaign_directory']);self.events=self.root/'sequence-events-prospective197-original01'
        self.rt=load('_sequence_archived_scope',h.checked(self.ready['native_closure']))
        self.ctl=load('_sequence_CPU_controller',h.checked(self.ready['CPU_controller']))
        self.q=load('_sequence_quality_review_predicates',h.checked(self.ready['leg_reviewer']))
        self.count=0;self.records=[]

    def event(self,label,value):
        self.count+=1
        pin=self.h.put(self.events/f'{self.count:04d}-{label}.json',value)
        print(json.dumps(dict(event=label,receipt=pin)),flush=True);return pin

    def check_new_actions(self):
        control=self.root/'sequencing-control-prospective197-original01.json'
        if control.exists()and json.loads(control.read_text()).get('stop_new_actions')is True:
            raise StopNewActions('Operator requested no further scheduling/preparation')
        current=json.loads((R.parent/'state.json').read_text()).get('active_quality_job')or{}
        if current.get('directory')!=str(self.root):
            raise StopNewActions('Canonical active campaign changed; no new actions')

    def register(self,stage,role,owner=None,controller=None,terminal=False):
        value=dict(stage=stage,current_leg=role,sequence_pid=os.getpid(),sequence_birth=birth(os.getpid()),
            native_or_reviewer=owner,controller=controller,launch_readiness=self.ready_pin,
            original_attempts_per_leg=1,no_retries=True,observed_unix_s=time.time())
        receipt=self.event(stage.lower(),value)
        target=self.root/'sequencing-status.json';temporary=target.with_name('sequencing-status.next.json')
        with temporary.open('w')as stream:json.dump(dict(value,event=receipt),stream,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
        state=R.parent/'state.json'
        # State is a dashboard/recovery projection, never the scientific result.
        for attempt in range(3):
            raw=state.read_bytes();data=json.loads(raw);goal=data['optimization_goal']
            active=goal.get('active_quality_job')or{}
            if active.get('directory')!=str(self.root):return
            previous_leg=active.get('current_leg')
            selected_leg=previous_leg if role=='campaign'and stage in ('SEQUENCING_STOPPED_REQUESTED','ORIGINAL_SEQUENCE_FAILED')else role
            active.update(state=stage,current_leg=selected_leg,sequence_latest_event=receipt)
            root_active=data.get('active_quality_job')or{}
            if root_active.get('directory')==str(self.root):
                root_active['current_leg']=ORDER.index(selected_leg)+1 if selected_leg in ORDER else 4
                root_active['state']=('finished'if stage in ('QUALIFIED_PENDING_PROTECTION','VALID_NOT_IMPROVED')
                    else 'stopped'if stage=='SEQUENCING_STOPPED_REQUESTED'
                    else 'failed'if stage=='ORIGINAL_SEQUENCE_FAILED'else 'running')
            if owner:
                active['actual_scope']=owner;active['actual_controller']=controller
                observer=active.get('sequence_observer',{})
                goal['actual_running_wait']=dict(kind=stage,quality_leg=role,sequence_pid=os.getpid(),
                    sequence_birth=birth(os.getpid()),tool_session_id=observer.get('tool_session_id'),
                    scope_pid=owner['pid'],scope_birth=owner['starttime_ticks'],unit=owner['unit'],
                    invocation_id=owner['invocation_id'],controller=controller,no_retry=True)
            elif terminal:
                existing=active.get('actual_scope')or active.get('actual_native')or{}
                if type(existing.get('pid'))is int and birth(existing['pid'])==existing.get('starttime_ticks'):
                    if goal.get('actual_running_wait'):goal['actual_running_wait']['sequencing_halted']=True
                else:goal['actual_running_wait']=None
            goal['last_progress']='Original quality sequence: '+stage+' '+role+'. No original retry, candidate pooling or main mutation.'
            data['updated_unix_s']=time.time();encoded=json.dumps(data,separators=(',',':'),allow_nan=False).encode()
            if len(encoded)>=1048576:return
            backup=self.root/'sequence-state-backups-prospective197-original01'/f'{self.count:04d}-{attempt}.json'
            with backup.open('xb')as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
            if state.read_bytes()!=raw:continue
            temporary=state.with_name(f'state.sequence-{os.getpid()}-{self.count}.tmp')
            with temporary.open('xb')as stream:stream.write(encoded);stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
            os.replace(temporary,state);fd=os.open(str(state.parent),os.O_DIRECTORY);os.fsync(fd);os.close(fd);return

    def native(self,directory,role):
        cfg_pin=self.h.pin(directory/'controller-config.json')
        evidence=verify_closed_scope(directory,'',cfg_pin,self.h,self.read,self.rt,self.ctl)
        owner=evidence['identity'];cfg=self.read(cfg_pin)
        self.q.validate_native_fields(evidence['fields'],cfg,owner,self.rt.duration_seconds)
        job_pin=self.h.pin(directory/'job.json');job=self.read(job_pin)
        self.q.validate_scope(job,job_pin,self.read(self.h.pin(directory/'precommitted-acceptance-scope.json')),cfg)
        self.q.validate_runtime_result(self.read(self.h.pin(directory/'diagnostic-output-original01/result.json')),job)
        require(job['quality_leg']==role and job['quality_pair_precommit']==self.ready['quality_pair'],
            'Original native role/pair changed')
        return evidence

    def review(self,directory,role):
        self.check_new_actions();cfg_name=('independent-review-controller-config-prospective197-original01.json' if role=='R1' else 'independent-review-controller-config.json')
        cfg_pin=self.h.pin(directory/cfg_name)
        cfg=self.read(cfg_pin);rjp=self.h.pin(directory/'independent-review-job.json')
        expected=['/usr/bin/python3.12','-I','-B',self.ready['leg_reviewer']['path'],'--observe','--job',
            rjp['path'],'--job-sha256',rjp['sha256'],'--expected-source-sha256',self.ready['leg_reviewer']['sha256']]
        require(cfg['argv']==expected,'Original independent review selection differs')
        invoke_controller_once(directory,'independent-review-',self.ready['CPU_controller'],cfg_pin,self.h,
            lambda owner,child:self.register('INDEPENDENT_REVIEW_RUNNING',role,owner,child))
        evidence=verify_closed_scope(directory,'independent-review-',cfg_pin,self.h,self.read,self.rt,self.ctl)
        fields=evidence['fields']
        require(self.rt.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
            and fields['MemorySwapMax']=='0'and self.rt.duration_seconds(fields['RuntimeMaxUSec'])==180
            and fields['TasksMax']=='256'and self.rt.duration_seconds(fields['TimeoutStopUSec'])==5
            and fields['SendSIGKILL']=='no'and fields['Restart']=='no','Original review resources differ')
        report_pin=self.h.pin(directory/'independent-quality-leg-review-original01/review.json');report=self.read(report_pin)
        require(report['valid']is report['full_game_score_verified']is True
            and report['quality_qualified']is report['promotion']is False and report['quality_leg']==role
            and report['quality_pair_precommit']==self.ready['quality_pair']and report['review_job']==rjp,
            'Original independent review failed or selected other evidence')
        return dict(**evidence,report=report_pin)

    def run(self):
        require(self.precommit['schema']=='robotron-existing-R1-quality32-sequence-precommit-v1'
            and self.precommit['source']==self.h.pin(__file__),'Exact one-use sequence/source required')
        prior=self.read(self.precommit['prior_observer_terminal'])
        prior_intent=self.read(self.precommit['prior_observer_intent'])
        require(prior['status']=='SEQUENCING_STOPPED_NO_NEW_ACTIONS' and prior['original_records']==[]
            and birth(prior_intent['pid'])!=prior_intent['birth'],'Prior observer must be terminal without scientific actions')
        first_owner=self.read(self.precommit['first_R1_native_owner'])
        first_controller=self.read(self.precommit['first_R1_controller'])
        require(birth(first_owner['pid'])==first_owner['starttime_ticks']
            and birth(first_controller['pid'])==first_controller['starttime_ticks'],
            'Existing original R1 native and controller must be live at sequence start')
        require(not (self.root/'original-sequence-observer-prospective197-original01-intent.json').exists(),'Original sequence already consumed')
        self.events.mkdir(mode=0o700);(self.root/'sequence-state-backups-prospective197-original01').mkdir(mode=0o700)
        self.h.put(self.root/'original-sequence-observer-prospective197-original01-intent.json',dict(source=self.h.pin(__file__),
            precommit=self.precommit_pin,pid=os.getpid(),birth=birth(os.getpid()),original_attempt=1,no_retry=True,
            R1_native_relaunched=False,R1_controller_observation_adopted=False,created_unix_s=time.time()))
        outcome=dict(schema='robotron-original-certified-quality32-sequence-outcome-v1',precommit=self.precommit_pin,
            original_records=self.records,quality_qualified=False,promotion=False,main_runtime_changed=False,
            original_attempts_per_leg=1,no_retries=True,R1_native_relaunched=False)
        try:
            self.register('OBSERVING_EXISTING_R1','R1',first_owner,
                {k:first_controller[k]for k in ('pid','starttime_ticks')})
            first=self.root/FOLDERS[0];gone_at=None
            while not ((first/'controller-original-result.json').exists()
                    and (first/'controller-original-result.json').stat().st_mode&0o777==0o444):
                self.check_new_actions()
                if birth(first_controller['pid'])!=first_controller['starttime_ticks']:
                    if gone_at is None:gone_at=time.monotonic()
                    require(time.monotonic()-gone_at<40,'Original R1 controller gone without sealed result; no restart')
                time.sleep(5)
            for index,role in enumerate(ORDER):
                directory=self.root/FOLDERS[index]
                if index:
                    self.check_new_actions()
                    preparer=load('_sequence_fresh_quality_leg_preparer',self.h.checked(self.ready['leg_preparer']))
                    preparer.prepare(self.ready_pin,role,self.h)
                    self.check_new_actions()
                    invoke_controller_once(directory,'',self.ready['native_controller'],
                        self.h.pin(directory/'controller-config.json'),self.h,
                        lambda owner,child,role=role:self.register('ORIGINAL_NATIVE_RUNNING',role,owner,child))
                native=self.native(directory,role)
                self.register('ORIGINAL_NATIVE_CLOSED',''+role,terminal=True)
                reviewed=self.review(directory,role)
                self.records.append(dict(role=role,native=native,independent_review=reviewed))
                self.register('ORIGINAL_LEG_VALIDATED',role,terminal=True)
            self.check_new_actions()
            cfg_pin=self.precommit['campaign_assessment_config']
            invoke_controller_once(self.root,'campaign-assessment-',self.ready['CPU_controller'],cfg_pin,self.h,
                lambda owner,child:self.register('CAMPAIGN_ASSESSMENT_RUNNING','campaign',owner,child))
            evidence=verify_closed_scope(self.root,'campaign-assessment-',cfg_pin,self.h,self.read,self.rt,self.ctl)
            report_pin=self.h.pin(self.root/'independent-campaign-assessment-original01/assessment.json');report=self.read(report_pin)
            require(report['valid']is True,'Original final campaign assessment invalid')
            outcome.update(status='ORIGINAL_FOUR_LEG_CAMPAIGN_COMPLETE',campaign_assessment=evidence,
                assessment_report=report_pin,quality_qualified=report['quality_qualified'])
            self.register('QUALIFIED_PENDING_PROTECTION'if report['quality_qualified']else'VALID_NOT_IMPROVED',
                'campaign',terminal=True)
        except StopNewActions as error:
            outcome.update(status='SEQUENCING_STOPPED_NO_NEW_ACTIONS',reason=str(error))
            self.register('SEQUENCING_STOPPED_REQUESTED','campaign',terminal=True)
        except Exception as error:
            outcome.update(status='ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY',error=repr(error),traceback=traceback.format_exc())
            self.register('ORIGINAL_SEQUENCE_FAILED','campaign',terminal=True)
        outcome['ended_unix_s']=time.time()
        pin=self.h.put(self.root/'original-sequence-observer-prospective197-original01-outcome.json',outcome)
        print(json.dumps(dict(outcome=pin,status=outcome['status'],quality_qualified=outcome['quality_qualified'])),flush=True)
        return 0 if outcome['status']in ('ORIGINAL_FOUR_LEG_CAMPAIGN_COMPLETE','SEQUENCING_STOPPED_NO_NEW_ACTIONS')else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true');parser.add_argument('--precommit')
    parser.add_argument('--precommit-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.run:print('PLAN_ONLY');return 0
    h=load('_original_quality_sequence_helpers',B/'run_full_policy_startup_v3.py')
    require(h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1','Helper changed')
    require(h.pin(__file__)['sha256']==args.source_sha256,'Sequence source changed')
    pin=h.pin(args.precommit);require(pin['sha256']==args.precommit_sha256,'Sequence precommit changed')
    reader_path=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    require(h.pin(reader_path)['sha256']=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','Reader changed')
    reader=load('_original_sequence_immutable_reader',reader_path)
    return CampaignSequence(pin,h,reader).run()

if __name__=='__main__':sys.exit(main())
