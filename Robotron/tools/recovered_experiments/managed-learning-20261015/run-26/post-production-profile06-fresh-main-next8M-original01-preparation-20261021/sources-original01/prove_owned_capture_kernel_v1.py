"""Two fresh private kernel cases for the selected one-save capture wrapper.

Success checks actual request publication and normal producer/archive modes.
Loss injects actual controller exit23 inside the selected kernel hold. The
independent selected watcher must thaw the same private192-child fixture.
No production process, model, request, control or cgroup is changed.
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

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/post-production-profile06-fresh-main-next8M-original01-preparation-20261021'
K=P/'capture-wrapper-kernel-original01'
CONTROL=G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'
CONTROL_SHA='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'


def require(value,message):
    if not value:raise RuntimeError(message)


def load(entry,name):
    require(hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256'],'Selected source differs')
    spec=importlib.util.spec_from_file_location(name,entry['path']);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def wait(predicate,seconds,message):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        result=predicate()
        if result:return result
        time.sleep(.03)
    raise RuntimeError(message+'; no retry')


def normal_write(path,raw):
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o664)


def fixture_main(work):
    require(work.parent.parent==K and work.parent.name in ('success','loss'),'Exact private fixture work root required')
    inputs=json.loads((work/'fixture-inputs.json').read_bytes())
    linux=load(inputs['linux'],'_owned_save_fixture_linux')
    wrapper=load(inputs['capture'],'_owned_save_fixture_files')
    unit='robotron-profile06-owned-save-kernel-original01-20261021-'+work.parent.name+'-fleet.service'
    owner=wrapper.identity(linux,unit,pid=os.getpid())
    children=[];count=0;last_save=None
    try:
        for _ in range(192):children.append(subprocess.Popen(['/usr/bin/sleep','300']))
        actors=[dict(slot=i,pid=child.pid,starttime_ticks=linux.process_start(child.pid),mask=sorted(os.sched_getaffinity(child.pid)))
            for i,child in enumerate(children)]
        require(len({a['pid'] for a in actors})==192,'Distinct original192 fixture children required')
        slot=work/'models/managed_save.request.json.completed'
        normal_write(slot,b'{"tag":"before_private_fixture"}\n')
        linux.publish(work/'fixture-ready.json',dict(owner=owner,actors=actors))
        request=work/'models/managed_save.request.json'
        while not(work/'fixture-release.json').exists():
            require(all(child.poll() is None for child in children),'An original private child exited')
            count+=1;wrapper.mutable_state(work/'heartbeat.json',dict(count=count,monotonic_s=time.monotonic()))
            if request.exists():
                value=json.loads(request.read_bytes());require(last_save is None,'Only one fixture request is allowed')
                time.sleep(.08)
                source=work/'models/managed-checkpoints'/(value['tag']+'.pt')
                normal_write(source,b'PRIVATE_FIXTURE_MODEL_STAND_IN\n'*2048)
                temporary=slot.with_name(slot.name+'.producer.tmp')
                normal_write(temporary,(json.dumps(value)+'\n').encode());os.replace(temporary,slot)
                request.unlink();last_save=dict(source=linux.full_pin(source),slot=linux.full_pin(slot))
                linux.publish(work/'fixture-save-completed.json',last_save)
            time.sleep(.02)
        for actor in actors:
            require(linux.process_start(actor['pid'])==actor['starttime_ticks']
                and sorted(os.sched_getaffinity(actor['pid']))==actor['mask'],'Original private child identity/affinity changed')
        linux.publish(work/'fixture-completed.json',dict(owner=owner,actors=actors,original192_preserved=True,
            heartbeat_count=count,last_save=last_save))
    finally:
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:child.wait(timeout=3)
    return 0


def injected_loss(job,job_sha):
    require(job['mode']=='private_kernel_fixture' and job['fixture_variant']=='loss','Private loss injection only')
    wrapper=load(job['source'],'_owned_save_actual_loss_target')
    linux=load(job['linux'],'_owned_save_actual_loss_linux')
    work=Path(job['model_dir']).parent
    def lose(group):
        before=(work/'heartbeat.json').read_bytes();time.sleep(.12)
        require((work/'heartbeat.json').read_bytes()==before,'Private heartbeat did not stop during the real hold')
        events=dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())
        require(events['frozen']=='1','Private replacement was not kernel frozen')
        linux.publish(work/'original-loss-injection.json',dict(actual_controller_pid=os.getpid(),
            actual_controller_starttime_ticks=linux.process_start(os.getpid()),save_owner=job['owner'],
            kernel_frozen=True,private_heartbeat_stopped=True,expected_original_exit=23,
            inside_selected_capture_publication=True,original192_children=192,production_changed=False))
        os._exit(23)
    return wrapper.capture(job,job_sha,after_frozen=lose)


class Integration:
    def __init__(self,job):
        self.job=job;self.l=load(job['sources']['linux'],'_owned_save_root_linux')
        self.c=load(dict(path=str(CONTROL),sha256=CONTROL_SHA),'_owned_save_root_control')
        self.runtime=load(job['archive_checker'],'_owned_save_root_archives')
        self.reader=self.runtime.protector();self.children={};self.sources={}

    def start(self,case,role,argv,pins):
        unit='robotron-profile06-owned-save-kernel-original01-20261021-'+case.name+'-'+role+'.service'
        output=case/(role+'-execution')
        config=dict(unit=unit,output=str(output),argv=argv,properties=['CPUQuota=200%','MemoryMax=4G',
            'RuntimeMaxSec=180','MemorySwapMax=0','TasksMax='+('256' if role=='fleet' else '128'),
            'TimeoutStopSec=5','SendSIGKILL=no'],pins=[self.c.pin(e['path']) for e in pins],observation_s=240)
        cp=self.l.publish(case/(role+'-config.json'),config);self.c.checked_config(cp['path'])
        command=['/usr/bin/python3.12','-I','-B',str(CONTROL),'--execute','--config',cp['path'],
            '--expected-source-sha256',CONTROL_SHA]
        with (case/(role+'-launcher-stdout.txt')).open('xb') as stdout,(case/(role+'-launcher-stderr.txt')).open('xb') as stderr:
            process=subprocess.Popen(command,stdout=stdout,stderr=stderr)
        self.children[(case.name,role)]=process
        return cp

    def closed(self,case,role,expected):
        output=case/(role+'-execution');closure_path=output/'root-original-result-and-owned-release.json'
        wait(closure_path.exists,40,'Original private '+role+' closure is incomplete')
        cp=self.l.full_pin(closure_path);closure=json.loads(self.l.checked(cp))
        op=self.l.full_pin(output/'root-original-identity.json');owner=json.loads(self.l.checked(op))
        self.runtime.archived_closure(closure,owner,lambda e,as_json=True:self.reader.read_pin(e,as_json=as_json),exit_zero=expected==0)
        require(closure['original_exit']==expected and closure['original_exec_code']==1,'Original injected/private exit differs')
        process=self.children[(case.name,role)];actual=process.wait(timeout=5)
        require(actual==(0 if expected==0 else 1),'Original lifecycle CLI exit differs')
        require(self.l.show(owner['unit'])['LoadState']==self.l.show(owner['timer'])['LoadState']=='not-found',
            'Original exact private release incomplete')
        return dict(owner=op,closure=cp,actual_original_exit=expected,actual_lifecycle_CLI_exit=actual,
            actual_descriptor_exits=[r['exit'] for r in closure['full_original_archives']])

    def case(self,variant):
        case=K/variant;case.mkdir(mode=0o700);work=case/'work';work.mkdir(mode=0o700)
        (work/'models/managed-checkpoints').mkdir(parents=True)
        fixture_inputs=self.l.publish(work/'fixture-inputs.json',self.sources)
        fleet_config=self.start(case,'fleet',['/usr/bin/python3.12','-I','-B',self.sources['harness']['path'],
            '--fixture-main','--work',str(work)],[*self.sources.values(),fixture_inputs])
        ready=wait(lambda:(work/'fixture-ready.json').exists(),20,'Original private fleet is not ready')
        fixture_pin=self.l.full_pin(work/'fixture-ready.json');fixture=json.loads(self.l.checked(fixture_pin))
        prefix='robotron-profile06-owned-save-kernel-original01-20261021-'+variant
        job_path=case/'capture-job.json';controller_source=self.sources['capture' if variant=='success' else 'harness']
        controller_prefix=['/usr/bin/python3.12','-I','-B',controller_source['path'],
            '--capture' if variant=='success' else '--loss','--job',str(job_path),'--expected-job-sha256']
        capture_job=dict(schema='robotron-one-owned-candidate-save-v1',mode='private_kernel_fixture',fixture_variant=variant,
            case=prefix.removeprefix('robotron-'),owner=fixture['owner'],model_dir=str(work/'models'),
            capture_output=str(case/'capture-output'),rescue_output=str(case/'rescue-output'),tag='private_fixture_'+variant,
            controller_unit=prefix+'-capture.service',rescue_unit=prefix+'-rescue.service',job_path=str(job_path),
            controller_argv_prefix=controller_prefix,controller_source=controller_source,source=self.sources['capture'],
            linux=self.sources['linux'],pause_source=self.sources['pause'],design=self.job['design'])
        wrapper=load(self.sources['capture'],'_owned_save_root_scope_'+variant);wrapper.validate_scope(capture_job)
        jp=self.l.publish(job_path,capture_job);inputs=[*self.sources.values(),jp,self.job['design']]
        self.start(case,'rescue',['/usr/bin/python3.12','-I','-B',self.sources['capture']['path'],'--watch',
            '--job',jp['path'],'--expected-job-sha256',jp['sha256']],inputs)
        wait(lambda:(case/'rescue-output/ready.json').exists(),15,'Original private rescue is not ready')
        self.start(case,'capture',controller_prefix+[jp['sha256']],inputs)
        capture_closed=self.closed(case,'capture',0 if variant=='success' else 23)
        rescue_closed=self.closed(case,'rescue',0)
        rescue_pin=self.l.full_pin(case/'rescue-output/result.json');rescue=json.loads(self.l.checked(rescue_pin))
        require(rescue['status']=='ORIGINAL_CONTROLLER_EXIT_OBSERVED' and rescue['controller_alive'] is False
            and rescue['restart_retry'] is False,'Original independent watch did not observe actual controller loss/exit')
        if variant=='success':
            result_pin=self.l.full_pin(case/'capture-output/result.json');result=json.loads(self.l.checked(result_pin))
            require(result['status']=='ORIGINAL_CAPTURE_ARCHIVED_NORMAL_PRODUCER_PRESERVED'
                and result['normal_producer_mode_preserved'] is True,'Original normal capture did not pass')
            require(result['source']['identity']['mode']=='0o664' and result['checkpoint']['identity']['mode']=='0o444'
                and self.l.full_pin(result['source']['path'])==result['source']
                and self.l.full_pin(result['checkpoint']['path'])==result['checkpoint'],'Actual normal producer/archive identity changed')
            publication=json.loads(self.l.checked(result['publication']))
            require(publication['request']['identity']['nlink']==1
                and publication['request']['sha256']==publication['request_archive']['sha256'],'Actual exclusive request publication differs')
            require(rescue['recovery']['status']=='NO_RECORDED_SAVE_HOLD','Normal finally did not release its own hold')
            evidence=dict(original_capture_result=result_pin)
        else:
            injection_pin=self.l.full_pin(work/'original-loss-injection.json');injection=json.loads(self.l.checked(injection_pin))
            require(injection['kernel_frozen'] is True and injection['private_heartbeat_stopped'] is True
                and injection['inside_selected_capture_publication'] is True and injection['expected_original_exit']==23,
                'Original private kernel loss was not injected inside the selected capture function')
            require(rescue['recovery']['status']=='EXACT_RECORDED_SAVE_OWNER_THAWED'
                and rescue['recovery']['thaw']['owner']==fixture['owner'],'Original watcher did not thaw this exact private owner')
            require(not(case/'capture-output/result.json').exists()
                and not(work/'models/managed_save.request.json').exists(),'Injected original loss was normalized or saved again')
            evidence=dict(original_loss_injection=injection_pin)
        before=json.loads((work/'heartbeat.json').read_bytes())['count']
        wait(lambda:json.loads((work/'heartbeat.json').read_bytes())['count']>before,3,'Same private fixture heartbeat did not resume')
        for actor in fixture['actors']:
            require(self.l.process_start(actor['pid'])==actor['starttime_ticks']
                and sorted(os.sched_getaffinity(actor['pid']))==actor['mask'],'An original private child changed')
        self.l.publish(work/'fixture-release.json',dict(case=variant,original192_checked=True))
        fleet_closed=self.closed(case,'fleet',0)
        completion_pin=self.l.full_pin(work/'fixture-completed.json');completion=json.loads(self.l.checked(completion_pin))
        require(completion['original192_preserved'] is True and completion['actors']==fixture['actors'],'Original private completion census differs')
        require(all(self.l.process_start(a['pid']) is None for a in fixture['actors']),'Original private children not all reaped')
        report=dict(status='ORIGINAL_PRIVATE_CAPTURE_KERNEL_CASE_PASS',variant=variant,fixture=fixture_pin,
            original_capture_job=jp,original_fixture_completion=completion_pin,original_watch_result=rescue_pin,
            original_closures=dict(fleet=fleet_closed,capture=capture_closed,rescue=rescue_closed),
            all18_original_descriptors_and_exact_releases_verified=True,original192_children_and_affinities_preserved=True,
            private_heartbeat_resumed=True,production_changed=False,**evidence)
        return self.l.publish(case/'root-case-readback.json',report)

    def run(self):
        require(self.job['schema']=='profile06-owned-save-two-private-kernel-cases-v1' and not K.exists(),
            'One fresh original kernel integration only')
        proof=json.loads(self.l.checked(self.job['CPU_readback']))
        require(proof['status']=='ACTUAL_ORIGINAL_OWNED_SAVE_WRAPPER_CPU21_ALL6_AND_RELEASE_PASS'
            and proof['tested_sources']['capture']==self.job['sources']['capture'],'Original selected21 CPU contracts required')
        for entry in [*self.job['sources'].values(),self.job['design'],self.job['CPU_readback']]:self.l.checked(entry)
        K.mkdir(mode=0o700);(K/'sources').mkdir()
        for name,entry in self.job['sources'].items():
            self.sources[name]=self.l.publish(K/'sources'/Path(entry['path']).name,self.l.checked(entry))
        try:
            cases={variant:self.case(variant) for variant in ('success','loss')}
            report=dict(status='ACTUAL_ORIGINAL_CAPTURE_NORMAL_SAVE_AND_CONTROLLER_LOSS_KERNEL_PASS',
                original_cases=cases,source_pins=self.sources,CPU_readback=self.job['CPU_readback'],
                all36_original_inner_descriptors_verified=True,original_two_fixtures192_each_preserved=True,
                original_loss_exit23_preserved=True,emergency_cleanup_used=False,production_changed=False,
                actual_ROM_model_or_replay_tested=False,original_integration_retried=False)
            return self.l.publish(K/'root-original-kernel-report.json',report)
        except BaseException as error:
            failure=dict(status='ORIGINAL_PRIVATE_CAPTURE_KERNEL_FAILURE_PRESERVED',error=repr(error),emergency_cleanup_used=False)
            for variant in ('success','loss'):
                work=K/variant/'work';ready=work/'fixture-ready.json'
                if ready.exists() and not(work/'fixture-release.json').exists():
                    try:
                        fixture=json.loads(ready.read_bytes());pause=load(self.sources['pause'],'_owned_save_emergency_pause_'+variant)
                        pause.thaw_startup_save(self.l,fixture['owner'])
                        self.l.publish(work/'fixture-release.json',dict(emergency=True));failure['emergency_cleanup_used']=True
                    except BaseException as cleanup_error:failure[variant+'_cleanup_error']=repr(cleanup_error)
            self.l.publish(K/'root-original-failure-preserved.json',failure)
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root',action='store_true');parser.add_argument('--fixture-main',action='store_true')
    parser.add_argument('--loss',action='store_true');parser.add_argument('--work',type=Path)
    parser.add_argument('--job',type=Path);parser.add_argument('--expected-job-sha256');args=parser.parse_args()
    if args.fixture_main:return fixture_main(args.work)
    if not(args.run_root or args.loss):print('PLAN_ONLY: no private fixture or production actions');return 0
    require(args.job and hashlib.sha256(args.job.read_bytes()).hexdigest()==args.expected_job_sha256,'Exact original job required')
    job=json.loads(args.job.read_bytes())
    if args.loss:return injected_loss(job,args.expected_job_sha256)
    print(json.dumps(Integration(job).run()));return 0


if __name__=='__main__':raise SystemExit(main())
