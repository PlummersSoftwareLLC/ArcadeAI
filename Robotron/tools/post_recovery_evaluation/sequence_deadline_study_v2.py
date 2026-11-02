"""Continue one already-owned original R1; review each leg before the next.

One controller Popen per future native/review, actual terminal observations,
no retry, no promotion. Default invocation is inert. The R1 wrapper remains
the sole owner of its running controller and is never adopted or relaunched.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import fcntl
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STATE=ROOT/'logs/managed-learning-20261015/state.json'
ORDER=['R1','C1','R2','C2']


def require(ok,message):
    if not ok:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def preparation():
    return load('_deadline_sequence_review_preparation',HERE/'prepare_deadline_independent_review_v1.py')


class StopNewActions(Exception):pass


def walk(cases,wait_R1,launch_native,review,assess,before):
    require([case['leg']for case in cases]==ORDER,'Exact original RCRC order required')
    records=[]
    for index,case in enumerate(cases):
        before('wait_original_R1'if index==0 else'native',case)
        native=wait_R1(case)if index==0 else launch_native(case)
        before('review',case)
        qualified=review(case,native)
        records.append(dict(leg=case['leg'],native=native,qualification=qualified))
    before('assessment',None)
    return records,assess(records)


def prepare(review_precommit,R1_owner,output):
    p=preparation();h,read,pp,packet,case=p.selected(review_precommit,'R1')
    ownerpin=h.pin(R1_owner.resolve());original=read(ownerpin)
    helper=load('_deadline_sequence_prepare_original_helper',h.checked(packet['sources']['sequence']))
    require(original['original_job']==case['native_job']and original['config']==case['native_config']
            and helper.birth(original['wrapper_pid'])==original['wrapper_birth']
            and helper.birth(original['owner']['pid'])==original['owner']['starttime_ticks']
            and helper.birth(original['controller']['pid'])==original['controller']['starttime_ticks'],
            'Exact already running original R1 owner/births required')
    root=Path(case['native_job']['path']).parent.parent
    current=json.loads(STATE.read_bytes());active=current.get('active_quality_job')or{}
    require(active.get('directory')==str(root)and active.get('stage')=='ORIGINAL_R1_NATIVE_RUNNING'
            and current['optimization_goal']['scientific_job_running']is True,'Exact active original R1 registration required')
    output=output.resolve();require(output.is_relative_to(p.BASE)and not output.exists(),'Fresh owned sequence directory required')
    for row in packet['cases'][1:]:
        subject=read(row['native_job']);cfg=read(row['native_config']);legroot=Path(row['native_job']['path']).parent
        require(not Path(subject['output']).exists()and not Path(cfg['output']).exists()
                and not (legroot/'controller-original-launch.json').exists(), 'Future original leg already consumed')
    output.mkdir(mode=0o700)
    return h.put(output/'sequence-precommit.json',dict(schema='robotron-deadline32-original-sequence-precommit-v1',
        source=h.pin(Path(__file__).resolve()),review_precommit=pp,review_preparer=packet['source'],
        R1_original_owner=ownerpin,study_directory=str(root),output=str(output),ordered_legs=ORDER,
        original_attempt=1,no_retry=True,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        source_helper=packet['sources']['sequence'],assessor=h.pin(HERE/'assess_screen_study.py'),
        review_preparation_CPU=h.pin(Path(pp['path']).parent.parent/'deadline-review-preparation-CPU-original01/independent-original-CPU-scope-closeout.json'),
        full_game_quality_qualified=False,promotion=False))


def atomic(path,value,suffix):
    temporary=path.with_name(path.name+'.'+suffix)
    with temporary.open('x')as stream:
        json.dump(value,stream,separators=(',',':'),allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
    os.replace(temporary,path)


class Sequence:
    def __init__(self,path,expected_sha):
        self.p=preparation();self.h,self.read=self.p.dependencies()
        self.pin=self.h.pin(path.resolve());require(self.pin['sha256']==expected_sha,'Selected original sequence changed')
        self.job=self.read(self.pin);h=self.h
        require(self.job['schema']=='robotron-deadline32-original-sequence-precommit-v1'
                and self.job['source']==h.pin(Path(__file__).resolve())
                and self.job['review_preparer']==h.pin(Path(self.p.__file__))
                and self.job['ordered_legs']==ORDER and self.job['original_attempt']==1 and self.job['no_retry']is True
                and self.job['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'Exact original sequence/source/boot required')
        self.review_precommit=Path(self.job['review_precommit']['path'])
        _,_,pp,self.packet,_=self.p.selected(self.review_precommit,'R1')
        require(pp==self.job['review_precommit'],'Original review precommit changed')
        cpu=self.read(self.job['review_preparation_CPU'])
        require(cpu['actual_exit']==0 and cpu['status']=='PASS_ENGINEERING_ONLY'
                and cpu['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified']is True,
                'Independent review preparation CPU closure required')
        self.helper=load('_deadline_sequence_owned_controller',h.checked(self.job['source_helper']))
        self.original=self.read(self.job['R1_original_owner']);self.root=Path(self.job['study_directory'])
        require(self.root==Path(self.packet['cases'][0]['native_job']['path']).parent.parent,'Original study root differs')
        self.output=Path(self.job['output']);self.number=0
        self.events=self.output/'events-original01';self.events.mkdir(mode=0o700)
        self.h.put(self.output/'sequence-original-child.json',dict(pid=os.getpid(),birth=self.helper.birth(os.getpid()),
                   original_precommit=self.pin,observed_live=True,created_unix_s=time.time()))

    def event(self,label,value):
        self.number+=1
        pin=self.h.put(self.events/('%04d-'%self.number+label+'.json'),value)
        print(json.dumps(dict(event=label,receipt=pin)),flush=True);return pin

    def check(self,kind,case):
        stop=self.output/'sequencing-control.json'
        if stop.exists()and json.loads(stop.read_bytes()).get('stop_new_actions')is True:
            raise StopNewActions('Operator requested no new scientific scheduling')
        current=json.loads(STATE.read_bytes());active=current.get('active_quality_job')or{}
        if active.get('directory')!=str(self.root):raise StopNewActions('Canonical active study changed')
        epoch=self.read(current['optimization_goal']['next_fixed_reference_epoch'])
        prepared=self.read(self.packet['native_prepared']);study=self.read(prepared['study_precommit'])
        require(epoch['reference_policy']==study['policies']['reference']['checkpoint'],'Protected reference epoch changed')
        for pin in (self.job['source'],self.job['review_preparer'],self.job['assessor'],self.job['source_helper']):self.h.checked(pin)

    def project(self,stage,case,*,owner=None,controller=None,terminal=False):
        event=self.event(stage.lower(),dict(stage=stage,leg=case['leg']if case else None,owner=owner,controller=controller,
            sequence_pid=os.getpid(),sequence_birth=self.helper.birth(os.getpid()),unix_s=time.time()))
        raw=STATE.read_bytes();current=json.loads(raw);active=current.get('active_quality_job')or{}
        require(active.get('directory')==str(self.root),'Canonical active study changed during projection')
        active.update(stage=stage,state='failed'if stage=='ORIGINAL_SEQUENCE_FAILED_NO_RETRY'else('closed'if terminal else'running'),
            current_leg=ORDER.index(case['leg'])+1 if case else active.get('current_leg'),sequence_pid=os.getpid(),
            sequence_birth=self.helper.birth(os.getpid()),sequence_precommit=self.pin,sequence_latest_event=event)
        active.update(actual_original_scope=owner,actual_original_controller=controller)
        goal=current['optimization_goal'];goal['scientific_job_running']=owner is not None and not terminal
        goal['actual_running_wait']=dict(kind=stage,quality_leg=case['leg'],scope=owner,controller=controller,
            sequence_pid=os.getpid(),sequence_birth=self.helper.birth(os.getpid()),no_retry=True)if owner is not None else None
        goal['last_progress']='Original684b fixed-cutoff comparison: '+stage+'. No complete-game gain or promotion established.'
        encoded=(json.dumps(current,separators=(',',':'),allow_nan=False)+'\n').encode();require(len(encoded)<1<<20,'Canonical state bound exceeded')
        backup=self.output/('state-preimage-%04d.exact.json'%self.number)
        with backup.open('xb')as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        require(STATE.read_bytes()==raw,'Canonical state changed before sequence projection')
        temporary=STATE.with_name('state.deadline-sequence-original01.tmp')
        with temporary.open('xb')as stream:stream.write(encoded);stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
        require(STATE.read_bytes()==raw,'Canonical state changed during sequence projection');os.replace(temporary,STATE)
        fd=os.open(STATE.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
        status=json.loads((self.root/'status.json').read_bytes())
        status.update(state='failed'if'FAILED'in stage else('closed'if terminal else'running'),
                      current_leg=ORDER.index(case['leg'])+1 if case else status['current_leg'],updated_unix_s=time.time())
        if case:status['legs'][ORDER.index(case['leg'])]['state']='complete'if stage.endswith('INDEPENDENTLY_QUALIFIED')else('failed'if'FAILED'in stage else'running')
        if terminal and 'FAILED'in stage:
            for row in status['legs']:
                if row['state']=='pending':row['state']='cancelled'
                elif row['state']=='running':row['state']='failed'
        atomic(self.root/'status.json',status,'sequence-next')

    def wait_R1(self,case):
        result=Path(case['native_job']['path']).parent/'controller-original-result.json'
        native=self.read(case['native_job']);cfg=self.read(case['native_config'])
        unit=self.original['owner']['unit'];control=load('_deadline_wait_original_native_control',self.h.checked(case['native_controller']))
        while not result.exists()or self.helper.birth(self.original['wrapper_pid'])==self.original['wrapper_birth']:
            self.check('wait_original_R1',case)
            require(time.monotonic()<=int(self.original['owner']['starttime_ticks'])/os.sysconf('SC_CLK_TCK')+cfg['observation_s']+120,
                    'Original R1 observation bound expired; preserve without retry')
            if not result.exists():
                fields=control.show(unit)
                require(fields['InvocationID']==self.original['owner']['invocation_id']and fields['NRestarts']=='0',
                        'Original R1 invocation changed')
            time.sleep(2)
        # Its original wrapper/Popen alone supplies actual terminal observation.
        closed=self.p.closed_controller(Path(case['native_job']['path']).parent,'',case['native_config'],
            case['native_controller'],self.packet['sources'],self.h,self.read)
        self.event('original-R1-wrapper-closed',closed)
        return closed['result']

    def fresh_ready(self,case):
        h=self.h;job=self.read(case['native_job']);cfg=self.read(case['native_config']);root=Path(case['native_job']['path']).parent
        require(not Path(job['output']).exists()and not Path(cfg['output']).exists()
                and not (root/'controller-original-launch.json').exists(),'Original native attempt already consumed')
        control=load('_deadline_future_native_control',h.checked(case['native_controller']))
        require(control.checked_config(case['native_config']['path'])==cfg,'Exact qualified native config changed')
        for pin in cfg['pins']:require(control.pin(pin['path'])==pin,'Frozen native input changed')
        for unit in (cfg['unit'],cfg['unit'].removesuffix('.service')+'.timer'):
            require(control.show(unit)['LoadState']=='not-found','Future original unit/timer already exists')
        h.checked(job['lease']);fd=os.open(job['lease']['path'],os.O_RDONLY|os.O_NOFOLLOW)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)
        for port in [job['origin_port'],*job['proxy_ports'].values()]:
            with socket.socket()as listener:listener.bind(('0.0.0.0',port))
        hardware=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=10)
        require(hardware.returncode==0 and not any(job['gpu_uuid']in row for row in hardware.stdout.splitlines()),'Dedicated evaluator GPU remains occupied')
        family=self.read(job['source_family_manifest']);binding=self.read(job['main_binding'])
        worker=load('_deadline_future_fresh_observer',h.checked(family['main_observer']['worker']))
        health=load('_deadline_future_fresh_health',h.checked(family['main_observer']['health']))
        deadline=time.monotonic()+15
        while True:
            try:
                sample=worker.collect(health,binding);health.validate(binding,sample);health.check_inputs(binding,full=True);break
            except (ValueError,OSError):
                require(time.monotonic()<deadline,'Fresh coherent main census unavailable before original launch')
                time.sleep(.02)
        raw=h.put(self.output/(case['leg']+'-fresh-main-before-launch.raw.json'),sample)
        return self.event(case['leg']+'-fresh-resource-readiness',dict(native_job=case['native_job'],config=case['native_config'],fresh_main=raw,
            main_round=sample['status']['round'],GPU_UUID=job['gpu_uuid'],GPU_compute_apps=hardware.stdout,
            original_attempt_unused=True,exact_units_ports_and_lease_free=True,checked_unix_s=time.time()))

    def launch_native(self,case):
        readiness=self.fresh_ready(case);self.check('native',case)
        self.project('ORIGINAL_'+case['leg']+'_NATIVE_STARTING',case)
        root=Path(case['native_job']['path']).parent
        def on_live(owner,child):self.project('ORIGINAL_'+case['leg']+'_NATIVE_RUNNING',case,owner=owner,controller=child)
        pin=self.helper.invoke_controller_once(root,'',case['native_controller'],case['native_config'],self.h,on_live)
        result=self.read(pin)
        require(type(result['actual_exit'])is int and result['actual_exit']==0 and result['live_registration_errors']==[],
                'Original native/controller failed; no retry')
        return pin

    def review(self,case,native):
        preparedpin=self.p.prepare_leg(self.review_precommit,case['leg']);prepared=self.read(preparedpin)
        self.check('review',case);self.project('ORIGINAL_'+case['leg']+'_INDEPENDENT_REVIEW_STARTING',case)
        root=Path(case['native_job']['path']).parent
        def on_live(owner,child):self.project('ORIGINAL_'+case['leg']+'_INDEPENDENT_REVIEW_RUNNING',case,owner=owner,controller=child)
        pin=self.helper.invoke_controller_once(root,'independent-review-',prepared['controller'],prepared['review_config'],self.h,on_live)
        result=self.read(pin)
        require(type(result['actual_exit'])is int and result['actual_exit']==0 and result['live_registration_errors']==[],
                'Original independent review/controller failed; no retry')
        qualified=self.p.qualify(self.review_precommit,case['leg'])
        self.project('ORIGINAL_'+case['leg']+'_INDEPENDENTLY_QUALIFIED',case)
        return qualified

    def assess(self,records):
        # The assessor reopens every independent qualification/six-descriptor
        # archive and uses the unchanged numerical reducer. It cannot promote.
        source=self.job['assessor'];assessor=load('_deadline_sequence_original_assessor',self.h.checked(source))
        manifest=self.packet['native_prepared']
        return assessor.assess(Path(manifest['path']),manifest['sha256'],self.output/'four-original-screen-assessment.json')

    def run(self):
        outcome=dict(schema='robotron-deadline32-original-sequence-outcome-v1',precommit=self.pin,original_attempt=1,no_retry=True,
                     full_game_quality_qualified=False,promotion=False,started_unix_s=time.time())
        try:
            self.check('wait_original_R1',self.packet['cases'][0])
            self.event('waiting-for-owned-original-R1',dict(original=self.job['R1_original_owner'],no_process_adoption=True))
            records,assessment=walk(self.packet['cases'],self.wait_R1,self.launch_native,self.review,self.assess,self.check)
            outcome.update(status='FOUR_ORIGINAL_SCREENING_LEGS_REVIEWED',records=records,assessment=assessment)
            self.project('FOUR_ORIGINAL_SCREENING_LEGS_REVIEWED',None,terminal=True)
        except Exception as error:
            outcome.update(status='STOPPED_NO_NEW_ACTIONS'if isinstance(error,StopNewActions)else'ORIGINAL_FAILURE_PRESERVED_NO_RETRY',
                           error=repr(error),traceback=traceback.format_exc())
            # Record failure without touching any running original payload.
            try:
                active=json.loads(STATE.read_bytes()).get('active_quality_job')or{}
                owner=active.get('actual_original_scope')or{}
                if owner and self.helper.birth(owner['pid'])==owner['starttime_ticks']:
                    outcome['original_scope_still_running_preserved']=owner
                    self.event('sequence-stopped-original-scope-preserved',dict(owner=owner,error=repr(error)))
                else:self.project('ORIGINAL_SEQUENCE_FAILED_NO_RETRY',None,terminal=True)
            except Exception as projection_error:outcome['canonical_projection_error']=repr(projection_error)
        outcome['ended_unix_s']=time.time()
        pin=self.h.put(self.output/'sequence-original-outcome.json',outcome)
        print(json.dumps(dict(outcome=pin,status=outcome['status'])),flush=True)
        return 0 if outcome['status']=='FOUR_ORIGINAL_SCREENING_LEGS_REVIEWED'else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true');parser.add_argument('--run',action='store_true')
    parser.add_argument('--review-precommit',type=Path);parser.add_argument('--R1-owner',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--precommit',type=Path);parser.add_argument('--precommit-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if args.prepare:print(json.dumps(prepare(args.review_precommit,args.R1_owner,args.output)),flush=True)
    elif args.run:
        require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Original sequence source changed')
        return Sequence(args.precommit,args.precommit_sha256).run()
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')


if __name__=='__main__':sys.exit(main())
