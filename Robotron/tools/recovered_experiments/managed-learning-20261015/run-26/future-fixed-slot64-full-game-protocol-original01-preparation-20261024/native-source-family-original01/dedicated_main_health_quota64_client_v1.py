"""Unselected native client for exactly one independently scoped original observer.

Live state never substitutes for immutable original closure/raw review. No
restart, adoption, main mutation, GPU operation or import-time process action.
"""
import json,os,secrets,subprocess,time
from pathlib import Path

RAM_CONTROL_SHA='52372d96fdbfbd2955c260ef864d456e034c8cfe015aa776b4391b5b2e679f8c'

CONTROLLER_SHA='12e479b0eb0545dab32da1d8f8130be3622670207c79ecaf0a164b812fa0ec5a'

def require(value,message):
    if not value:raise ValueError(message)

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

class DedicatedMainHealth:
    def __init__(self,job,jp,protocol,family,h,*,started,deadline,prior_groups):
        self.h=h;self.native=job;self.native_pin=jp;self.protocol=protocol;self.family=family
        self.started=started;self.deadline=deadline;self.child=None;self.child_birth=None;self.owner=None
        self.last_live=None;self.initial=None;self.scope_complete=False;self.lifecycle=None;self.finished=False
        self.root=Path(job['output'])/'main-health-scope';self.output=Path(job['output'])/'main-observations'
        self.sources=family['main_observer'];require(set(self.sources)=={'client','worker','protocol','controller','reviewer'},'Exact observer source family required')
        for pin in self.sources.values():h.checked(pin)
        self.interpreter=family['main_observer_interpreter'];h.checked(self.interpreter)
        require(self.interpreter['path']=='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','Exact free314 observer interpreter required')
        require(self.sources['client']==h.pin(__file__)and self.sources['controller']['sha256']==CONTROLLER_SHA,
            'Exact selected native client/controller source required')
        self.codec=h.load('_dedicated_native_protocol',h.checked(self.sources['protocol']))
        self.control=h.load('_dedicated_native_controller',h.checked(self.sources['controller']))
        self.root.mkdir(mode=0o700)
        cg=next(line.split(':',2)[2]for line in Path('/proc/self/cgroup').read_text().splitlines()if line.startswith('0::'))
        unit=Path(cg).name;fields=self.control.show(unit)
        require(fields['MainPID']==str(os.getpid())and fields['InvocationID']==os.environ['INVOCATION_ID']and fields['ControlGroup']==cg,
            'Original native parent scope identity differs')
        self.parent=dict(pid=os.getpid(),birth=birth(os.getpid()),uid=os.geteuid(),unit=unit,invocation_id=fields['InvocationID'],cgroup=cg,
            argv=[v.decode()for v in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]],job=jp,source=job['runtime'])
        prior=h.put(self.root/'verified-original-prior-case-groups.json',prior_groups)
        self.job=dict(schema='robotron-dedicated-main-health-job-v1',output=str(self.output),helpers=protocol['health_job']['sources']['helpers'],
            protocol_source=self.sources['protocol'],health_job=protocol['health_job'],prior_groups=prior,observer_unit=unit[:-8]+'-mainhealth.service',worker_interpreter=self.interpreter,
            unit_runtime_s=22260,parent=self.parent,parent_started_monotonic_s=started,deadline_monotonic_s=deadline,poll_s=.2,nonce=secrets.token_hex(16),original_attempt=1,no_retry=True,
            native_job=jp,native_protocol=job['main_health_protocol'],source_family=job['source_family_manifest'])
        self.storage_pin=family['main_live_control'];require(self.storage_pin['sha256']==RAM_CONTROL_SHA,'Exact RAM live-control helper required')
        self.storage=h.load('_dedicated_RAM_control',h.checked(self.storage_pin))
        self.live_control=self.storage.create(self.job['nonce'],self.parent,jp,self.job['observer_unit'],h)
        self.job.update(live_control=self.live_control,live_control_helper=self.storage_pin)
        try:
            self.jobpin=h.put(self.root/'job.json',self.job)
            argv=[self.interpreter['path'],'-Xgil=0','-I','-B',self.sources['worker']['path'],'--execute','--job',self.jobpin['path'],
                '--job-sha256',self.jobpin['sha256'],'--source-sha256',self.sources['worker']['sha256']]
            pins=[self.interpreter,*protocol['health_job']['sources'].values(),protocol['health_job']['binding'],*self.sources.values(),jp,job['runtime'],
                job['main_health_protocol'],job['source_family_manifest'],prior,self.storage_pin,self.jobpin]
            config=dict(unit=self.job['observer_unit'],output=str(self.root/'execution-original01'),argv=argv,
                properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=22260','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
                pins=[self.control.pin(pin['path'])for pin in {p['path']:p for p in pins}.values()],observation_s=22320)
            self.configpin=h.put(self.root/'controller-config.json',config);self.control.checked_config(self.configpin['path'])

        except BaseException:
            self.storage.release_unstarted(self.live_control,self.parent,jp,self.root/'constructor-failed-live-control-archive',h)
            raise

    def start(self):
        require(self.child is None,'Original observer may be launched only once')
        argv=['/usr/bin/python3.12','-I','-B',self.sources['controller']['path'],'--execute','--config',self.configpin['path'],
            '--expected-source-sha256',self.sources['controller']['sha256']]
        env=dict(os.environ);env.pop('LD_PRELOAD',None);env.pop('PYTHONPATH',None);env['CUDA_VISIBLE_DEVICES']='';env['PYTHONDONTWRITEBYTECODE']='1'
        with(self.root/'controller-stdout.txt').open('xb')as out,(self.root/'controller-stderr.txt').open('xb')as err:
            self.child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=env)
        self.child_birth=birth(self.child.pid)
        require(type(self.child_birth)is int and self.child_birth>0,'Original observer controller birth was not captured')
        self.controller_child_pin=self.h.put(self.root/'original-controller-child.json',dict(pid=self.child.pid,birth=self.child_birth,argv=argv,parent=self.parent))
        limit=min(self.deadline,time.monotonic()+25)
        while time.monotonic()<limit:
            require(self.child.poll()is None,'Original observer controller ended before readiness; no adoption or retry')
            identity=self.root/'execution-original01/root-original-identity.json'
            if identity.exists()and identity.stat().st_mode&0o777==0o444:
                basic=json.loads(self.h.checked(self.h.pin(identity)).read_bytes())
                self.owner=dict(pid=basic['pid'],starttime_ticks=basic['starttime_ticks'],unit=basic['unit'],invocation_id=basic['invocation_id'],
                    cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+basic['unit'],uid=os.geteuid())
                self.storage.check_live(self.live_control)
                live=Path(self.live_control['live_path'])
                if live.exists():
                    value=self.codec.checked_read(live,os.geteuid(),mode=0o644)
                    require(value['state']not in ('failed','closed'),'Original observer failed before native setup: '+str(value.get('error')))
                    if value['state']=='running':
                        self._accept(value)
                        if self.initial['index']is not None and not value['latest']['phase']['overlap_pending']:return value['latest']
            time.sleep(.02)
        raise ValueError('Original native observer readiness deadline; no restart')

    def _accept(self,value):
        self.codec.validate_live(value,self.jobpin,self.job,self.owner,time.monotonic())
        require(birth(self.owner['pid'])==self.owner['starttime_ticks'],'Original autonomous observer birth changed')
        if self.last_live is not None:require(value['observed_samples']>=self.last_live['observed_samples'],'Original observer sample count regressed')
        self.last_live=value;self.initial=value['initial'];return value['latest']

    def observe(self):
        require(not self.finished and self.child is not None and self.child.poll()is None,'Original observer is terminal/unstarted')
        self.storage.check_live(self.live_control)
        return self._accept(self.codec.checked_read(Path(self.live_control['live_path']),os.geteuid(),mode=0o644))

    def finish(self,*,case_already_failed):
        require(not self.finished,'Original observer finalization may run only once');self.finished=True
        result=dict(report=None,failure=None,errors=[],watch_stopped=True,writer_stopped=False,scope_complete=False,statuses=[])
        if self.child is None:
            result['live_control_release']=self.storage.release_unstarted(self.live_control,self.parent,self.native_pin,self.root/'live-control-archive',self.h)
            result['errors'].append('Original observer never launched; no complete monitoring proof');return result
        command=self.output/'finish-request.json'
        # This immutable command targets the fresh source/job/nonce-bound output,
        # including startup failures before a first live projection was received.
        if self.child.poll()is None and self.output.exists()and not command.exists():
            self.h.put(command,dict(schema=self.codec.FINISH_SCHEMA,job=self.jobpin,nonce=self.job['nonce'],parent=self.parent,
                action='abort'if case_already_failed else'close',created_monotonic_s=time.monotonic()))
        try:self.child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            result['errors'].append('Original observer controller still running; no release or success inferred');return result
        cp=self.root/'execution-original01/root-original-result-and-owned-release.json';op=self.root/'execution-original01/root-original-identity.json'
        if not cp.exists()or not op.exists():
            result['errors'].append('Original observer closed scope receipt missing');return result
        closure_pin=self.h.pin(cp);closure=json.loads(self.h.checked(closure_pin).read_bytes());owner_pin=self.h.pin(op);owner=json.loads(self.h.checked(owner_pin).read_bytes())
        require(owner['unit']==self.job['observer_unit']and closure['original']==owner and closure['lifecycle_complete']is True and closure['unit_released']is True and closure['original_archived_before_release']is True,
            'Original observer actual lifecycle incomplete')
        require(birth(owner['pid'])!=owner['starttime_ticks']and birth(self.child.pid)!=self.child_birth,'Original observer/controller birth remains')
        require(len(closure['owned_release'])==2 and {row['unit']for row in closure['owned_release']}=={owner['unit'],owner['timer']}
            and all(row['confirmed_absent']for row in closure['owned_release']),
            'Both original observer units must be released')
        for unit in [owner['unit'],owner['timer']]:require(self.control.show(unit)['LoadState']=='not-found','Original observer unit remains')
        require(not(Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')/owner['unit']).exists(),'Original observer cgroup remains')
        self.scope_complete=True;result['scope_complete']=True
        self.live_control_release=self.storage.archive_and_release(self.live_control,self.root/'live-control-archive',self.h,worker_job=self.jobpin,owner=owner_pin,closure=closure_pin)
        result['live_control_release']=self.live_control_release
        outcome_pin=self.h.pin(self.output/'outcome.json')if(self.output/'outcome.json').exists()else None
        outcome=None if outcome_pin is None else json.loads(self.h.checked(outcome_pin).read_bytes())
        if outcome is not None:
            require(outcome['job']==self.jobpin and outcome['parent']==self.parent and outcome['nonce']==self.job['nonce']
                and outcome['worker_source']==self.sources['worker']and outcome['protocol_source']==self.sources['protocol'],
                'Original worker outcome source/job/parent/nonce differs')
            result['writer_stopped']=outcome['all_writer_threads_stopped']
            result['report']=outcome['closed_report'];result['failure']=outcome['failure_report']
            pin=result['report']or result['failure']
            if pin is not None:result['statuses']=json.loads(self.h.checked(pin).read_bytes())['actual_status']
        success=bool(not case_already_failed and outcome is not None and outcome['success']is True and outcome['signals_received']==[]
            and closure['original_exec_code']==1 and closure['original_exit']==0 and closure['original_result']=='success'
            and self.child.returncode==0 and result['writer_stopped']is True and result['report']is not None and result['failure']is None)
        if not success:result['errors'].append('Original dedicated observer did not close validly: '+str(None if outcome is None else outcome['error']))
        self.lifecycle=self.h.put(self.root/'native-observer-lifecycle.json',dict(schema='robotron-native-dedicated-observer-lifecycle-v1',
            native_job=self.native_pin,worker_job=self.jobpin,worker_config=self.configpin,worker_owner=owner_pin,worker_closure=closure_pin,
            worker_outcome=outcome_pin,controller_child=self.controller_child_pin,actual_controller_exit=self.child.returncode,
            all_owned_worker_and_controller_processes_reaped=True,original_scope_released=True,parent=self.parent,success=success,
            native_started_monotonic_s=self.started,native_deadline_monotonic_s=self.deadline,live_control_release=self.live_control_release,quality_qualified=False))
        return result
