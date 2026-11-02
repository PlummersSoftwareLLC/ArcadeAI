"""Wait for the original R1 owner, review once, then start qualified continuation.

There is no native R1 launch/adoption path here. The original wrapper owns its
Popen through terminal receipt; transient unit absence is never completion.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STATE=ROOT/'logs/managed-learning-20261015/state.json'


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def original_R1_ready(observation):
    """Only a sealed controller receipt after its original wrapper is gone."""
    if observation['wrapper_alive']:return False
    require(observation['controller_alive']is False and observation['native_alive']is False,
            'Original R1 children remain after its wrapper disappeared')
    receipt=observation['controller_result']
    require(receipt is not None and type(receipt['actual_exit'])is int
            and receipt['actual_exit']==0 and receipt['live_registration_errors']==[],
            'Original R1 controller completion unavailable or failed; no retry')
    return True


def walk(wait,prepare_review,run_review,qualify,prepare_continuation,run_continuation,before):
    records={}
    for label,action in [('original_R1',wait),('prepare_review',prepare_review),('review',run_review),
                         ('qualify',qualify),('prepare_continuation',prepare_continuation),
                         ('continuation',run_continuation)]:
        before(label)
        records[label]=action(records)
    return records


def prepare(precommit,R1_owner,CPU_proof,output,projector_pid,projector_birth):
    p=load('_handoff_prepare_review',HERE/'prepare_deadline_independent_review_v4.py')
    h,read,pp,packet,case=p.selected(precommit,'R1')
    ownerpin=h.pin(R1_owner.resolve());owner=read(ownerpin)
    require(owner['original_job']==case['native_job']and owner['config']==case['native_config'],
            'Original R1 owner/job/config differs')
    cp=h.pin(CPU_proof.resolve());closed=read(cp);report=read(closed['actual_report']);cpu=read(closed['original_job'])
    require(closed['actual_exit']==0 and closed['status']=='PASS_ENGINEERING_ONLY'
            and closed['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified']is True
            and report['status']=='PASS'and report['tests_run']==8
            and report['original_job']==closed['original_job']
            and h.pin(Path(__file__).resolve())in cpu['inputs'], 'Exact handoff CPU proof required')
    helper=load('_handoff_prepare_original_owner',h.checked(packet['sources']['sequence']))
    require(helper.birth(owner['wrapper_pid'])==owner['wrapper_birth'], 'Original R1 wrapper must still own its attempt')
    require(type(projector_pid)is int and projector_pid>0 and type(projector_birth)is int and projector_birth>0,
            'Exact preceding passive-projector birth required')
    root=Path(case['native_job']['path']).parent.parent
    current=json.loads(STATE.read_bytes())
    require((current.get('active_quality_job')or{}).get('directory')==str(root), 'Original active study changed')
    for row in packet['cases']:
        require(not Path(row['review_job_path']).exists()and not Path(row['execution']).exists(),
                'An original review attempt is already consumed')
    output=output.resolve();require(output.is_relative_to(root)and not output.exists(), 'Fresh study-owned handoff directory required')
    output.mkdir(mode=0o700)
    sources=dict(source=h.pin(Path(__file__).resolve()),review_preparer=packet['source'],
        continuation=h.pin(HERE/'sequence_deadline_study_v6.py'),projector=h.pin(HERE/'project_deadline_study_v3.py'),
        owned_helper=packet['sources']['sequence'])
    return h.put(output/'precommit.json',dict(schema='robotron-original-R1-automatic-review-handoff-v1',
        **sources,review_precommit=pp,R1_original_owner=ownerpin,CPU_proof=cp,study_directory=str(root),
        output=str(output),previous_projector=dict(pid=projector_pid,birth=projector_birth),
        original_attempt=1,no_retry=True,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        original_R1_wait_bound_s=4380,quality_qualified=False,promotion=False))


class Handoff:
    def __init__(self,path,expected):
        self.p=load('_handoff_actual_review',HERE/'prepare_deadline_independent_review_v4.py')
        self.h,self.read=self.p.dependencies();self.pin=self.h.pin(path.resolve())
        require(self.pin['sha256']==expected,'Exact handoff precommit changed');self.job=self.read(self.pin)
        require(self.job['schema']=='robotron-original-R1-automatic-review-handoff-v1'
                and self.job['source']==self.h.pin(Path(__file__).resolve())and self.job['original_attempt']==1
                and self.job['no_retry']is True,'One original source-bound handoff required')
        self.helper=load('_handoff_actual_owned_helper',self.h.checked(self.job['owned_helper']))
        self.original=self.read(self.job['R1_original_owner']);self.root=Path(self.job['study_directory'])
        self.output=Path(self.job['output']);self.number=0
        self.h.put(self.output/'original-owner.json',dict(pid=os.getpid(),birth=self.helper.birth(os.getpid()),
            argv=[x.decode()for x in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]],precommit=self.pin))

    def event(self,label,value):
        self.number+=1
        pin=self.h.put(self.output/('%04d-'%self.number+label+'.json'),value)
        print(json.dumps(dict(event=label,receipt=pin)),flush=True);return pin

    def check(self,phase):
        require(self.job['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Original boot changed')
        stop=self.output/'stop-new-actions.json'
        require(not stop.exists()or json.loads(stop.read_bytes()).get('stop_new_actions')is not True,'Operator stopped new handoff actions')
        active=json.loads(STATE.read_bytes()).get('active_quality_job')or{}
        require(active.get('directory')==str(self.root),'Active original study changed; no new actions')
        for key in ('source','review_preparer','continuation','projector','owned_helper'):self.h.checked(self.job[key])

    def register(self,stage,owner=None,controller=None):
        event=self.event(stage.lower(),dict(stage=stage,scope=owner,controller=controller,unix_s=time.time()))
        for attempt in range(3):
            raw=STATE.read_bytes();value=json.loads(raw);active=value.get('active_quality_job')or{}
            require(active.get('directory')==str(self.root),'Active study changed during handoff projection')
            active.update(stage=stage,actual_original_scope=owner,actual_original_controller=controller,
                automatic_handoff=self.pin,automatic_handoff_pid=os.getpid(),automatic_handoff_birth=self.helper.birth(os.getpid()),
                automatic_handoff_event=event)
            goal=value['optimization_goal'];goal['scientific_job_running']=owner is not None
            goal['actual_running_wait']=dict(kind=stage,scope=owner,controller=controller,handoff=self.pin,
                pid=os.getpid(),birth=self.helper.birth(os.getpid()))
            goal['last_progress']='Original R1 handoff: '+stage+'. No quality gain or promotion established.'
            encoded=(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()
            require(len(encoded)<1<<20,'Canonical state bound exceeded')
            backup=self.output/('state-%04d-%02d.exact.json'%(self.number,attempt))
            with backup.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
            if STATE.read_bytes()!=raw:continue
            temporary=STATE.with_name('state.original-handoff-%d-%d.tmp'%(os.getpid(),attempt))
            with temporary.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
            if STATE.read_bytes()!=raw:
                temporary.unlink();continue  # Only this owned reversible projection retries.
            os.replace(temporary,STATE);fd=os.open(STATE.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd);return
        raise ValueError('Canonical projection changed repeatedly; original payload is never retried')

    def wait_R1(self,records):
        source=self.read(self.job['R1_original_owner']);root=self.root/'R1'
        started=time.monotonic();last=0
        while True:
            self.check('wait_original_R1')
            result_path=root/'controller-original-result.json'
            wrapper_alive=self.helper.birth(source['wrapper_pid'])==source['wrapper_birth']
            sealed=result_path.exists()and result_path.stat().st_mode&0o777==0o444
            observation=dict(wrapper_alive=wrapper_alive,
                controller_alive=self.helper.birth(source['controller']['pid'])==source['controller']['starttime_ticks'],
                native_alive=self.helper.birth(source['owner']['pid'])==source['owner']['starttime_ticks'],
                controller_result=self.read(self.h.pin(result_path))if sealed and not wrapper_alive else None)
            if original_R1_ready(observation):break
            require(time.monotonic()-started<self.job['original_R1_wait_bound_s'],'Original R1 wait bound reached; no restart')
            if time.monotonic()-last>=60:
                print(json.dumps(dict(event='SAME_ORIGINAL_R1_OWNER_OBSERVED',wrapper_pid=source['wrapper_pid'],
                    native_pid=source['owner']['pid'],elapsed_s=time.monotonic()-started)),flush=True);last=time.monotonic()
            time.sleep(5)
        _,_,_,packet,case=self.p.selected(Path(self.job['review_precommit']['path']),'R1')
        closed=self.p.closed_controller(root,'',case['native_config'],case['native_controller'],packet['sources'],self.h,self.read)
        return self.event('original-R1-closed-by-its-owner',closed)

    def prepare_review(self,records):
        pin=self.p.prepare_leg(Path(self.job['review_precommit']['path']),'R1')
        self.event('first-independent-R1-review-prepared',dict(prepared=pin));return pin

    def run_review(self,records):
        packet=self.read(records['prepare_review']);self.register('ORIGINAL_R1_INDEPENDENT_REVIEW_STARTING')
        def on_live(owner,child):self.register('ORIGINAL_R1_INDEPENDENT_REVIEW_RUNNING',owner,child)
        result=self.helper.invoke_controller_once(self.root/'R1','independent-review-',packet['controller'],packet['review_config'],self.h,on_live)
        value=self.read(result)
        require(value['actual_exit']==0 and value['live_registration_errors']==[], 'Original independent R1 review failed; no retry')
        return result

    def qualify(self,records):
        pin=self.p.qualify(Path(self.job['review_precommit']['path']),'R1')
        self.register('ORIGINAL_R1_INDEPENDENTLY_QUALIFIED');self.event('original-R1-qualified',dict(qualification=pin));return pin

    def prepare_continuation(self,records):
        sequence=load('_handoff_qualified_continuation',self.h.checked(self.job['continuation']))
        pin=sequence.prepare(Path(self.job['review_precommit']['path']),Path(self.job['R1_original_owner']['path']),self.output/'continuation-original01')
        self.event('original-continuation-prepared',dict(precommit=pin));return pin

    def owned_program(self,label,argv,on_live=None):
        self.h.put(self.output/(label+'-intent.json'),dict(argv=argv,original_attempt=1,no_retry=True))
        stdout=self.output/(label+'-stdout.txt');stderr=self.output/(label+'-stderr.txt')
        with stdout.open('xb')as out,stderr.open('xb')as err:
            child=subprocess.Popen(argv,stdout=out,stderr=err)
            owner=self.h.put(self.output/(label+'-owner.json'),dict(pid=child.pid,birth=self.helper.birth(child.pid),argv=argv))
            errors=[]
            try:
                if on_live:on_live(child)
            except Exception as error:errors.append(repr(error))
            code=child.wait();out.flush();err.flush();os.fchmod(out.fileno(),0o444);os.fchmod(err.fileno(),0o444);os.fsync(out.fileno());os.fsync(err.fileno())
        return self.h.put(self.output/(label+'-terminal.json'),dict(actual_exit=code,owner=owner,live_registration_errors=errors,
            stdout=self.h.pin(stdout),stderr=self.h.pin(stderr)))

    def run_continuation(self,records):
        pin=records['prepare_continuation'];source=self.job['continuation']
        projector=self.job['projector'];old=self.job['previous_projector']
        project_argv=['/usr/bin/python3','-I','-B',projector['path'],'--run','--precommit',pin['path'],
            '--previous-projector-pid',str(old['pid']),'--previous-projector-birth',str(old['birth'])]
        projection={}
        def on_live(child):
            # UI failure cannot interrupt or relaunch an original scientific
            # sequence. Its own separately reaped Popen remains authoritative.
            stream=None
            try:
                self.h.put(self.output/'projector-intent.json',dict(argv=project_argv,source=projector,no_process_controls=True))
                log=self.output/'projector-console.txt';stream=log.open('xb')
                process=subprocess.Popen(project_argv,stdout=stream,stderr=subprocess.STDOUT)
                projection.update(process=process,stream=stream,log=log)
                self.h.put(self.output/'projector-owner.json',dict(pid=process.pid,birth=self.helper.birth(process.pid),argv=project_argv))
            except Exception as error:
                if stream is not None and 'process'not in projection:stream.close()
                projection['start_error']=repr(error)
        result=self.owned_program('continuation',['/usr/bin/python3','-I','-B',source['path'],'--run','--precommit',pin['path'],
            '--precommit-sha256',pin['sha256'],'--source-sha256',source['sha256']],on_live)
        if projection.get('start_error'):
            self.event('passive-projector-start-error',dict(error=projection['start_error'],scientific_sequence_unchanged=True))
        if 'process'in projection:
            try:
                code=projection['process'].wait(timeout=30)
                stream=projection['stream'];stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno());stream.close()
                self.h.put(self.output/'projector-terminal.json',dict(actual_exit=code,console=self.h.pin(projection['log'])))
            except subprocess.TimeoutExpired:
                projection['stream'].close()
                self.event('passive-projector-terminal-unobserved',dict(pid=projection['process'].pid,no_signal_or_restart=True))
        terminal=self.read(result)
        require(terminal['actual_exit']==0 and terminal['live_registration_errors']==[],
                'Original continuation stopped; preserve failures without retry')
        return result

    def run(self):
        outcome=dict(schema='robotron-original-R1-handoff-outcome-v1',precommit=self.pin,original_attempt=1,no_retry=True,
            quality_qualified=False,promotion=False,started_unix_s=time.time())
        try:
            records=walk(self.wait_R1,self.prepare_review,self.run_review,self.qualify,self.prepare_continuation,self.run_continuation,self.check)
            outcome.update(status='ORIGINAL_SCREENING_SEQUENCE_FINISHED',records=records)
        except Exception as error:outcome.update(status='STOPPED_NO_RETRY',error=repr(error),traceback=traceback.format_exc())
        outcome['ended_unix_s']=time.time();pin=self.h.put(self.output/'outcome.json',outcome)
        print(json.dumps(dict(outcome=pin,status=outcome['status'])),flush=True)
        return 0 if outcome['status']=='ORIGINAL_SCREENING_SEQUENCE_FINISHED'else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--run',action='store_true')
    p.add_argument('--review-precommit',type=Path);p.add_argument('--R1-owner',type=Path);p.add_argument('--CPU-proof',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--projector-pid',type=int);p.add_argument('--projector-birth',type=int);p.add_argument('--precommit',type=Path);p.add_argument('--precommit-sha256')
    a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a.review_precommit,a.R1_owner,a.CPU_proof,a.output,a.projector_pid,a.projector_birth)),flush=True)
    elif a.run:raise SystemExit(Handoff(a.precommit,a.precommit_sha256).run())
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
