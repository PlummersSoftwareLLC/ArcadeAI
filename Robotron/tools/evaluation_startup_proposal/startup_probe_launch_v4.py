"""One authenticated guarded startup probe; inert unless explicitly executed.

This version is an isolated proposal. Real use requires the original preceding
quality campaign to be closed and any qualified winner protected first.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import types

GAME=Path(__file__).resolve().parents[2]
RUN=GAME/'logs/managed-learning-20261015/run-26'
READER=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
EXPECTED={
    'reader':'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071',
    'runtime':'924b0e5f5036bfeb4cc12d2a017372f197e0d74a3e75f50a6e908149a01fd202',
    'core':'6c0334d7a90216b080d3ed59cdf09f96b102aa56c7a3014fc255799e76cd5276',
    'watchdog':'f402f25bca7eb56bf4cd44ab39babb211982319ce95a53a308ddb9d0b12f0863',
    'closure':'2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445',
    'main_guard':'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3',
    'raw_api':'9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0',
    'tap_join':'7e0b45acc29c2f38e72bee50050244c6d6d955b20cdb1f2cc0edd37e19e2ddf7',
    'raw_matcher':'0d2a612b6cfa1726e7f0c9f163d0484a8ce3c29cc3ee8e06323c798032f7c7ba',
}
SETTINGS=dict(slots=list(range(4096,4112)),frames=4096,max_wall_s=300,poll_s=0.25)


def require(value,message):
    if not value:raise ValueError(message)


def checked_plan(plan):
    require(isinstance(plan,dict) and set(plan)=={'schema','job','output','probe_unit','guard_unit','guard_affinity','sources'}
        and plan['schema']=='robotron-authenticated-private-startup-launch-v2','Exact launcher plan required')
    require(set(plan['sources'])==set(EXPECTED)|{'launcher'}
        and all(plan['sources'][k]['sha256']==v for k,v in EXPECTED.items())
        and plan['sources']['launcher']['path']==str(Path(__file__).resolve()),'Exact tested launcher dependencies required')
    for key,prefix in [('probe_unit','private'),('guard_unit','guard')]:
        require(isinstance(plan[key],str) and re.fullmatch('robotron-startup-prefix-'+prefix+r'-[A-Za-z0-9_-]+\.service',plan[key]),
                'Dedicated original startup unit name required')
    output=Path(plan['output']);job_path=Path(plan['job']['path'])
    require(output.is_absolute() and output==output.resolve() and output.parent==job_path.parent
        and output.parent.is_relative_to(RUN) and output.name=='guard-execution',
        'Guard output must be the original job preparation guard-execution')
    mask=plan['guard_affinity']
    require(isinstance(mask,list) and mask and all(type(x) is int and x>=0 for x in mask)
        and mask==sorted(set(mask)),'Explicit inherited guard affinity required')
    return plan


def load_plan(entry):
    require(hashlib.sha256(READER.read_bytes()).hexdigest()==EXPECTED['reader'],'Evidence reader changed')
    spec=importlib.util.spec_from_file_location('_startup_launch_reader_'+str(time.time_ns()),READER)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    plan=checked_plan(reader.read_pin(entry))
    require(Path(entry['path']).parent==Path(plan['job']['path']).parent,'Original plan/job directories differ')
    for pin in plan['sources'].values():reader.read_pin(pin,as_json=False)
    modules={name:reader.checked_module('_startup_launch_'+name+'_'+str(time.time_ns()),plan['sources'][name])
             for name in EXPECTED if name!='reader'}
    job=reader.read_pin(plan['job']);modules['runtime'].checked_job(job)
    require(all(job['sources'][k]==plan['sources'][k] for k in job['sources']),
            'Runtime job and launcher sources differ')
    require(Path(job['external_guard_permit_path']).parent==Path(plan['job']['path']).parent
        and Path(job['output'])!=Path(plan['output']),'Original job output/permit scope differs')
    return reader,plan,job,modules


def complete_tap_result(reconciliation):
    """Content proof is mandatory, and never substitutes for the real unit exit."""
    require(type(reconciliation) is dict,'Original raw/tap reconciliation required')
    tap=reconciliation.get('tap_provenance')
    require(type(tap) is dict and tap.get('status')=='MATCHED_PASSIVE_TAP_CONTENT_ONLY',
            'Original complete passive tap content result required')
    raw={key:value for key,value in reconciliation.items() if key!='tap_provenance'}
    require(tap.get('raw_prefix_reconciliation')==raw,'Tap result does not join the same raw prefix')
    require(type(tap.get('actor_slots')) is int and tap['actor_slots']==16
        and type(tap.get('matched_inputs')) is int and tap['matched_inputs']==65536,
        'Complete16x4096 tap input coverage required')
    require(all(tap.get(key) is False for key in ('original_runtime_outcome_verified',
        'raw_ROM_start_acceptance_proven','start_eligibility_changed','protocol_selected',
        'quality_qualified','learning_speed_gain_verified')),'Content result cannot certify runtime/start/quality')
    slots=tap.get('slots');expected={str(slot) for slot in SETTINGS['slots']}
    require(type(slots) is dict and set(slots)==expected,'Exact16 declared tap slots required')
    for slot,row in slots.items():
        require(type(row) is dict and type(row.get('inputs')) is int and row['inputs']==4096,
                'Full original per-slot tap prefix required')
        require(row.get('captured_loaded_span_matches_pinned_ROM') is True
            and all(row.get(key) is False for key in ('full_loaded_ROM_image_verified',
                'first_start_certified','admission_clock_ordering_verified')),
                'Loaded span proof/certification scope differs')
        writes=row.get('status_writes');before=row.get('writes_before_first_input')
        common=row.get('common_restart_write_observations');starts=row.get('START1_write_observations')
        require(type(writes) is int and 0<=writes<=512 and type(before) is int and 0<=before<=writes
            and type(common) is int and 0<=common<=writes and type(starts) is list and len(starts)<=writes,
            'Bounded original write-site observations required')
        require(all(type(event) is dict and event.get('real_ROM_start_acceptance_proven') is False
            for event in starts),'Write-site observation cannot certify start acceptance')
    hashes=tap.get('input_sha256')
    require(type(hashes) is dict and set(hashes)=={'server','lua','tap','console'}
        and type(hashes['server']) is str and re.fullmatch('[0-9a-f]{64}',hashes['server']),
        'Original input-byte digest inventory required')
    for kind in ('lua','tap','console'):
        require(type(hashes[kind]) is dict and set(hashes[kind])==expected
            and all(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) for value in hashes[kind].values()),
            'Complete original per-slot digest inventory required')
    return dict(status='COMPLETE_PASSIVE_TAP_CONTENT_VERIFIED',actor_slots=16,matched_inputs=65536,
                actual_unit_outcome_verified=False,real_ROM_start_proven=False)


def checked_child_result(result,core):
    require(type(result) is dict and result.get('schema')=='robotron-one-attempt-startup-probe-coordinator-v1'
        and result.get('valid') is True and result.get('capture_complete') is True
        and result.get('status')=='MATCHED_DIAGNOSTIC_PREFIX_ONLY'
        and type(result.get('attempts')) is int and result['attempts']==1
        and result.get('retried') is False and result.get('scientific_review_rerun') is False
        and result.get('errors')==[] and type(result['errors']) is list,
        'Actual successful original coordinator result required')
    require(core.configuration(result.get('settings'))==SETTINGS,'Original coordinator settings differ')
    require(all(result.get(key) is False for key in ('raw_ROM_start_acceptance_proven',
        'start_eligibility_changed','protocol_selected','quality_qualified','learning_speed_gain_verified')),
        'Diagnostic coordinator cannot certify start/quality/speed')
    core.matched(result.get('reconciliation'))
    core.runtime_audit(result.get('runtime_audit'))
    return complete_tap_result(result['reconciliation'])


def terminal(fields,owner):
    require(fields.get('Id')==owner['unit'] and fields.get('InvocationID')==owner['invocation_id']
        and fields.get('NRestarts')=='0' and fields.get('MainPID')=='0'
        and fields.get('ExecMainPID')==str(owner['pid'])
        and fields.get('ExecMainStartTimestampMonotonic')==str(owner['start_monotonic_us'])
        and fields.get('ExecMainCode') in ('1','2','3')
        and re.fullmatch(r'\d+',fields.get('ExecMainStatus',''))
        and fields.get('SubState') in ('exited','dead','failed'),
        'Actual original terminal identity/outcome differs')
    require(int(fields.get('ExecMainExitTimestampMonotonic','0'))>=owner['start_monotonic_us'],
            'Actual original exit clock missing')
    if fields['ExecMainCode']=='1' and fields['ExecMainStatus']=='0':
        require(fields.get('Result')=='success','Zero exit lacks actual success result')
    return dict(exec_code=int(fields['ExecMainCode']),status=int(fields['ExecMainStatus']),result=fields.get('Result'),
                normal_exit=fields['ExecMainCode']=='1')


def verify_archives(owner,timer,records,read):
    """Signal-aware validation; raw code2/3 never becomes normal exit code1."""
    require(len(records)==6,'All six original descriptors required before release')
    expected=[]
    for unit,inv in [(owner['unit'],owner['invocation_id']),(timer['unit'],timer['invocation_id'])]:
        expected.extend([['systemctl','--user','show',unit],['systemctl','--user','cat',unit],
            ['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+inv]])
    for index,(record,argv) in enumerate(zip(records,expected)):
        require(record['argv']==argv and record['timed_out'] is False
            and type(record['exit']) is int and record['exit'] in ((0,1) if index==4 else (0,)),
            'Original archive command/outcome differs')
        read(record['stdout'],False);read(record['stderr'],False)
    fields=dict(x.split('=',1) for x in read(records[0]['stdout'],False).decode().splitlines() if '=' in x)
    outcome=terminal(fields,owner)
    tf=dict(x.split('=',1) for x in read(records[3]['stdout'],False).decode().splitlines() if '=' in x)
    require(tf.get('Id')==timer['unit'],'Original archived timer ID differs')
    if tf.get('LoadState')=='not-found':
        require(records[4]['exit']==1,'Absent timer cat must remain its actual failure')
    else:
        require(tf.get('LoadState')=='loaded' and tf.get('InvocationID')==timer['invocation_id']
            and tf.get('Unit')==owner['unit'] and records[4]['exit']==0,'Original archived timer differs')
    return dict(original_outcome=outcome,original_archived_before_release=True,all_six_verified=True)


class System:
    def __init__(self):
        self.reader=None;self.serial=0;self.write_lock=threading.Lock();self.owner=None
        self.timer=None;self.last_API=None;self.progress={};self.output=None

    def authenticate(self,entry):
        self.entry=entry;self.reader,self.plan,self.job,self.modules=load_plan(entry)
        runtime=self.modules['runtime'];core=self.modules['core'];self.proc=self.modules['watchdog'].Processes()
        # Actual archived closure is authenticated before own/live unit queries.
        self.predecessor=core.verify_closed_predecessor(self.job['predecessor'],
            read=lambda p,j:self.reader.read_pin(p,as_json=j),archive=self.modules['closure'].archived_closure,
            process_start=runtime.process_start,unit_fields=self.proc.fields,
            cgroup_exists=lambda group:Path('/sys/fs/cgroup'+group).exists())
        require(not any(n=='torch' or n.startswith('dqn.') for n in sys.modules),'CPU-only guard interpreter required')
        me=os.getpid();guard=self.proc.fields(self.plan['guard_unit'])
        require(guard.get('Id')==self.plan['guard_unit'] and guard.get('MainPID')==str(me)
            and guard.get('NRestarts')=='0' and guard.get('InvocationID')==os.environ.get('INVOCATION_ID')
            and re.fullmatch('[0-9a-f]{32}',guard.get('InvocationID',''))
            and self.proc.group(me)==guard.get('ControlGroup')
            and guard['ControlGroup'].endswith('/'+self.plan['guard_unit'])
            and sorted(os.sched_getaffinity(me))==self.plan['guard_affinity'],
            'Launcher must own its original external guard unit')
        self.guard_owner=dict(pid=me,starttime_ticks=self.proc.start(me),unit=self.plan['guard_unit'],
            invocation_id=guard['InvocationID'],cgroup=guard['ControlGroup'])
        require(self.guard_owner['starttime_ticks'] is not None,'Guard live birth missed')
        require(not Path(self.job['external_guard_permit_path']).exists(),'Original permit path already consumed')
        self.main=self.reader.read_pin(self.job['main'])
        require(len(self.main['actors'])==192 and {a['slot'] for a in self.main['actors']}==set(range(192)),
            'Fresh exact main192 binding required')
        self.modules['main_guard'].owner_and_files(self.main)
        self.forbidden={me,self.main['owner']['pid'],*(a['pid'] for a in self.main['actors'])}
        require(len(self.forbidden)==194,'Distinct guard/trainer/main192 identities required')
        self.monitor=runtime.System();self.monitor.reader=self.reader;self.monitor.modules=self.modules
        self.monitor.main=self.main
        self.monitor.main_hash_stats={p:self.monitor.stat_key(Path(p).stat()) for p in self.main['held_hashes']}
        self.monitor.baseline=self.modules['raw_api'].parse_wire(self.reader.read_pin(self.main['baseline_API'],as_json=False))
        self.monitor.previous=self.monitor.baseline
        self.monitor.package=self.reader.read_pin(self.job['package'])
        self.monitor.verify_inputs(types.SimpleNamespace(job=self.job))
        self.output=Path(self.plan['output']);require(not self.output.exists(),'Original guard output consumed')
        self.output.mkdir(mode=0o700);(self.output/'tmp').mkdir(mode=0o700)
        self.runtime_witness=types.SimpleNamespace(owns_output=True,publish_bytes=self.API_bytes)
        self.publish('guard-original-owner',self.guard_owner)

    def bytes(self,name,raw):
        require(self.output is not None and Path(name).name==name,'Owned flat guard artifact required')
        path=self.output/name
        with path.open('xb') as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        return self.reader.pin(path)

    def publish(self,kind,value):
        require(re.fullmatch('[A-Za-z0-9_-]+',kind) is not None,'Flat evidence kind required')
        with self.write_lock:
            self.serial+=1;name=f'{self.serial:06d}-{kind}.json'
            return self.bytes(name,(json.dumps(value,indent=2,allow_nan=False)+'\n').encode())

    def API_bytes(self,name,raw):
        with self.write_lock:
            self.last_API=self.bytes(name,raw);return self.last_API

    def sample(self):
        self.monitor.health(self.runtime_witness,force=True)
        api=self.monitor.previous;now=time.monotonic()
        for name in ('learner_frame_count','training_steps','optimized_samples'):
            value=api[name];old=self.progress.get(name)
            if old is None or value>old[0]:self.progress[name]=(value,now)
            else:require(now-old[1]<60,'Main '+name+' did not progress for60 seconds')
        require(self.last_API is not None,'Original raw main API witness missing')
        return dict(raw_API=self.last_API,main_owner=self.main['owner'],original192_actors_verified=True,
            clocks={k:api[k] for k in ('learner_frame_count','training_steps','optimized_samples')},
            scope='Exact main binding, raw API, optimizer/replay identities/recipe/progress and autosave checked.')

    def command(self,label,argv,timeout=10):
        started=time.monotonic();failure=None
        try:
            p=subprocess.run(argv,capture_output=True,timeout=timeout)
            stdout,stderr,code=p.stdout,p.stderr,p.returncode
        except subprocess.TimeoutExpired as error:
            stdout,stderr,code=error.stdout or b'',error.stderr or b'',None;failure=repr(error)
        with self.write_lock:
            self.serial+=1;stem=f'{self.serial:06d}-{label}'
            out=self.bytes(stem+'-stdout.txt',stdout);err=self.bytes(stem+'-stderr.txt',stderr)
        result=dict(argv=argv,exit=code,timed_out=failure is not None,error=failure,
                    start_monotonic_s=started,end_monotonic_s=time.monotonic(),stdout=out,stderr=err)
        self.publish(label+'-command',result);return result

    def fields(self,record):
        require(record['exit']==0 and not record['timed_out'],'Exact original query failed')
        return dict(x.split('=',1) for x in self.reader.read_pin(record['stdout'],as_json=False).decode().splitlines() if '=' in x)

    def schedule(self):
        require(not getattr(self,'schedule_attempted',False),'One scheduling attempt only')
        self.schedule_attempted=True;unit=self.plan['probe_unit'];timer=unit.removesuffix('.service')+'.timer'
        before_service=self.proc.fields(unit);before_timer=self.proc.fields(timer)
        require(before_service.get('Id')==unit and before_service.get('LoadState')=='not-found'
            and before_timer.get('Id')==timer and before_timer.get('LoadState')=='not-found',
            'Both exact future probe units must be absent')
        argv=[str(GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',str(Path(__file__).resolve()),
            '--child','--plan',self.entry['path'],'--plan-sha256',self.entry['sha256'],
            '--source-sha256',self.plan['sources']['launcher']['sha256']]
        self.child_argv=argv
        props=['Type=exec','RemainAfterExit=yes','Restart=no','WorkingDirectory='+str(GAME.parent),
            'StandardOutput=append:'+str(self.output/'child-stdout.txt'),
            'StandardError=append:'+str(self.output/'child-stderr.txt'),
            'CPUQuota=1600%','MemoryMax=32G','MemorySwapMax=0','TasksMax=256',
            'RuntimeMaxSec=345','TimeoutStopSec=5','SendSIGKILL=no',
            'CPUAffinity='+' '.join(map(str,self.job['affinity']))]
        command=['systemd-run','--user','--unit='+unit,'--on-active=3s','--timer-property=AccuracySec=100ms']
        command+=['--property='+p for p in props]
        command+=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','PYTHONDONTWRITEBYTECODE=1',
            'TMPDIR='+str(self.output/'tmp')]+argv
        self.publish('original-scheduling-intent',dict(command=command,unit=unit,timer=timer,attempt=1,no_retry=True))
        result=self.command('scheduling-carrier',command)
        require(result['exit']==0,'Scheduling carrier failed or timed out; no retry or unknown-owner adoption')
        shown=self.command('launch-timer-show',['systemctl','--user','show',timer])
        cat=self.command('launch-timer-cat',['systemctl','--user','cat',timer])
        fields=self.fields(shown)
        require(fields.get('Id')==timer and fields.get('LoadState')=='loaded' and fields.get('Unit')==unit
            and re.fullmatch('[0-9a-f]{32}',fields.get('InvocationID','')) and cat['exit']==0,
            'Original launch-time timer identity missing')
        text=self.reader.read_pin(cat['stdout'],as_json=False).decode()
        section=None;headers=0;units=[]
        for line in text.splitlines():
            line=line.strip()
            if not line or line.startswith(('#',';')):continue
            if line.startswith('['):section=line;headers+=int(line=='[Timer]')
            if re.match(r'Unit\s*=',line):units.append((section,line))
        require(headers==1 and (not units or units==[('[Timer]','Unit='+unit)]),
                'Original launch timer cat target is duplicate, malformed or foreign')
        self.timer=dict(unit=timer,invocation_id=fields['InvocationID'])
        self.publish('original-launch-timer',dict(original=self.timer,show=shown,cat=cat))

    def observe_birth(self):
        fields=self.proc.fields(self.plan['probe_unit']);pid=int(fields.get('MainPID','0'))
        if not pid:
            require(fields.get('ExecMainCode','0')=='0','Original live probe birth missed; no retrospective adoption')
            return None
        birth=self.proc.start(pid);group=self.proc.group(pid)
        command=Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0')[:-1]
        # The first live observation can precede env's exec of Python. Do not
        # bind or authorize that intermediate executable as the actual child.
        if command!=[os.fsencode(x) for x in self.child_argv]:return None
        require(Path('/proc',str(pid),'exe').resolve()==Path(self.child_argv[0]).resolve(),
                'Original child executable differs')
        owner=dict(unit=self.plan['probe_unit'],invocation_id=fields.get('InvocationID'),pid=pid,
            starttime_ticks=birth,cgroup=group,cgroup_identity=self.proc.group_identity(group),
            start_monotonic_us=int(fields.get('ExecMainStartTimestampMonotonic','0')),observed_live=True)
        self.modules['watchdog'].checked_owner(owner,self.forbidden)
        self.modules['watchdog'].owner_fields(self.proc.fields(owner['unit']),owner)
        require(self.proc.start(pid)==birth and sorted(os.sched_getaffinity(pid))==self.job['affinity'],
                'Original probe live birth/affinity differs')
        self.owner=owner;return owner

    def permit(self,owner):
        require(owner==self.owner and self.timer is not None,'Original owned birth and timer required')
        self.modules['watchdog'].owner_fields(self.proc.fields(owner['unit']),owner)
        require(self.proc.start(owner['pid'])==owner['starttime_ticks'],'Probe departed before permit')
        permit=dict(schema='robotron-original-startup-guard-live-binding-v1',job_sha256=self.plan['job']['sha256'],
            authorized_original_attempt=1,probe_owner=owner,guard_owner=self.guard_owner)
        path=Path(self.job['external_guard_permit_path'])
        with path.open('x') as f:json.dump(permit,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        self.publish('original-live-permit',self.reader.pin(path))

    def poll(self):
        fields=self.proc.fields(self.owner['unit'])
        # Empty ControlGroup is permitted only for an actual terminal record;
        # finish separately requires absence of the original recorded cgroup.
        self.modules['watchdog'].owner_fields(fields,self.owner,terminal_group_absent=fields.get('MainPID')=='0')
        if fields.get('MainPID')=='0' and fields.get('ExecMainCode') in ('1','2','3'):
            terminal(fields,self.owner);return fields
        require(self.proc.start(self.owner['pid'])==self.owner['starttime_ticks'],'Original probe birth changed')
        return None

    def cgroup_absent(self):return not Path('/sys/fs/cgroup'+self.owner['cgroup']).exists()

    def archive(self,fields):
        terminal(fields,self.owner);records=[]
        for unit,inv in [(self.owner['unit'],self.owner['invocation_id']),(self.timer['unit'],self.timer['invocation_id'])]:
            for action in ['show','cat','journal']:
                argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+inv] if action=='journal' else ['systemctl','--user',action,unit]
                records.append(self.command('original-'+('service' if unit==self.owner['unit'] else 'timer')+'-'+action,argv))
        proof=verify_archives(self.owner,self.timer,records,lambda p,j:self.reader.read_pin(p,as_json=j))
        self.archives=records;self.publish('original-terminal-archives',dict(**proof,records=records))
        self.retain_consoles();return proof

    def retain_consoles(self):
        if hasattr(self,'consoles'):return self.consoles
        console={};errors=[]
        for name in ('child-stdout.txt','child-stderr.txt'):
            try:
                path=self.output/name
                require(path.stat().st_size<=16*1024*1024,'Original console exceeds declared16MiB copy bound')
                before=self.reader.pin(path);raw=path.read_bytes()
                require(self.reader.pin(path)==before and hashlib.sha256(raw).hexdigest()==before['sha256'],
                        'Original child console changed during copy')
                console[name]=dict(original=before,readonly_copy=self.bytes(name+'.readonly',raw))
            except Exception as error:errors.append(name+': '+repr(error))
        self.consoles=dict(retained=console,errors=errors,original_producer_modes_unchanged=True)
        self.publish('original-child-consoles',self.consoles);return self.consoles

    def release(self):
        require(getattr(self,'archives',None) is not None,'Original archives must precede owned release')
        verify_archives(self.owner,self.timer,self.archives,lambda p,j:self.reader.read_pin(p,as_json=j))
        results=[]
        for kind,unit in [('timer',self.timer['unit']),('service',self.owner['unit'])]:
            row=dict(unit=unit);shown=self.command('release-'+kind+'-before-show',['systemctl','--user','show',unit]);row['before']=shown
            fields=self.fields(shown)
            require(fields.get('Id')==unit,'Original release ID differs')
            if fields.get('LoadState')!='not-found':
                if kind=='service':terminal(fields,self.owner)
                else:require(fields.get('InvocationID')==self.timer['invocation_id'] and fields.get('Unit')==self.owner['unit'],
                             'Unknown or replaced timer; no release authorized')
                row['stop']=self.command('release-'+kind+'-stop',['systemctl','--user','stop',unit])
                after=self.command('release-'+kind+'-after-show',['systemctl','--user','show',unit]);row['after']=after;fields=self.fields(after)
                if row['stop']['exit']!=0:
                    message=self.reader.read_pin(row['stop']['stderr'],as_json=False).decode().strip()
                    require(kind=='timer' and row['stop']['exit']==5 and fields.get('LoadState')=='not-found'
                        and message in ('Unit '+unit+' not loaded.','Failed to stop '+unit+': Unit '+unit+' not loaded.'),
                        'Owned stop failed without exact original timer-GC reason')
                if fields.get('LoadState')!='not-found':
                    require(kind=='service' and fields.get('ActiveState')=='failed','Owned unit still present')
                    terminal(fields,self.owner)
                    row['reset']=self.command('release-service-reset',['systemctl','--user','reset-failed',unit])
                    require(row['reset']['exit']==0,'Original failed state reset failed')
                    final=self.command('release-service-final-show',['systemctl','--user','show',unit]);row['final']=final;fields=self.fields(final)
            require(fields.get('Id')==unit and fields.get('LoadState')=='not-found','Exact owned unit absence not confirmed')
            row['confirmed_absent']=True;results.append(row)
        self.publish('original-owned-release',results);return results

    def audit(self):
        console=self.retain_consoles()
        require(not console['errors'],'Original child console retention incomplete')
        for p in self.plan['sources'].values():self.reader.read_pin(p,as_json=False)
        self.reader.read_pin(self.entry);self.reader.read_pin(self.plan['job'])
        self.monitor.verify_inputs(types.SimpleNamespace(job=self.job))
        self.modules['main_guard'].owner_and_files(self.main)
        require(self.cgroup_absent(),'Original probe cgroup remains after release')
        path=Path(self.job['output'])/'result.json'
        if not path.exists():return dict(valid=False,reason='Original child diagnostic result missing')
        require(path.stat().st_size<=16*1024*1024,'Original child result exceeds bound')
        result=self.reader.read_pin(self.reader.pin(path))
        tap=checked_child_result(result,self.modules['core'])
        capture=self.verify_capture_inputs(result['reconciliation']['tap_provenance'])
        return dict(valid=result.get('valid') is True,original_result=self.reader.pin(path),
            sources_unchanged=True,main192_held_inputs_unchanged=True,passive_tap_content=tap,
            original_capture_inputs=capture)

    def verify_capture_inputs(self,tap):
        root=Path(self.job['output']);path=root/'original-prefix-capture-inventory.json'
        require(path.stat().st_size<=256*1024,'Original capture inventory exceeds bound')
        inventory_pin=self.reader.pin(path);inventory=self.reader.read_pin(inventory_pin)
        require(type(inventory) is dict and set(inventory)=={'retained','errors','original_producer_modes_unchanged'}
            and inventory.get('errors')==[]
            and type(inventory['errors']) is list and inventory.get('original_producer_modes_unchanged') is True,
            'Original capture inventory has missing/invalid evidence')
        expected={'server':('server-prefix-readonly.jsonl',(16*(4096+16)+4)*2048,tap['input_sha256']['server'])}
        for slot in SETTINGS['slots']:
            for label,kind,maximum in [('Lua','lua',(4096+32)*2048),('tap','tap',4620*2048),
                                      ('console','console',16*1024*1024)]:
                expected[label+'-'+str(slot)]=(label+'-'+str(slot)+'-prefix-readonly.jsonl',maximum,
                                              tap['input_sha256'][kind][str(slot)])
        for name,(filename,sha) in self.modules['runtime'].ROM_INPUTS.items():
            expected[name]=('bound-'+name+'-input.bin',4096,sha)
        retained=inventory.get('retained')
        require(type(retained) is dict and set(retained)==set(expected),'Exact51 original capture inputs required')
        fields={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}
        for name,(filename,maximum,sha) in expected.items():
            entry=retained[name]
            require(type(entry) is dict and entry.get('path')==str(root/filename)
                and type(entry.get('bytes')) is int and 0<entry['bytes']<=maximum
                and entry.get('sha256')==sha and type(entry.get('identity')) is dict
                and set(entry['identity'])==fields,'Exact original capture path/hash/full identity required')
            raw=self.reader.read_pin(entry,as_json=False)
            require(len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==sha,
                    'Original captured bytes differ from matched inputs')
        require(self.reader.pin(path)==inventory_pin,'Original capture inventory changed during audit')
        return dict(inventory=inventory_pin,original_input_count=51,all_fullpins_and_input_digests_verified=True,
                    producer_modes_unchanged=True)


def execute(entry,*,system=None,clock=time.monotonic,sleep=time.sleep):
    """One external guard invocation; original failure is never retried."""
    caps=system if system is not None else System()
    require(not getattr(caps,'original_attempt_consumed',False),'One original launcher attempt per capability instance')
    caps.original_attempt_consumed=True
    watchdog=None;handlers={};result=dict(schema='robotron-authenticated-startup-original-result-v2',valid=False,
        original=None,original_outcome=None,archives=None,release=None,watchdog=None,audit=None,error=None,
        attempt=1,no_retry=True,real_ROM_start_proven=False,quality_qualified=False,learning_speed_gain_verified=False)
    archive_attempted=release_attempted=False
    def close_original(fields):
        nonlocal archive_attempted,release_attempted
        result['original_outcome']=terminal(fields,result['original'])
        if not watchdog.closed:result['watchdog']=watchdog.finish(fields,cgroup_absent=True)
        if not archive_attempted:
            archive_attempted=True
            result['archives']=caps.archive(fields)
            require(result['archives'].get('all_six_verified') is True
                and result['archives'].get('original_archived_before_release') is True,'Complete original archives required')
        if not release_attempted:
            require(result['archives'] is not None,'No owned release after failed archives')
            release_attempted=True
            result['release']=caps.release()
            require(len(result['release'])==2 and all(x.get('confirmed_absent') is True for x in result['release'])
                and {x['unit'] for x in result['release']}=={result['original']['unit'],caps.timer['unit']},
                'Both original owned units must be released')
    try:
        caps.authenticate(entry)
        watchdog=caps.modules['watchdog'].Watchdog(sample=caps.sample,publish=caps.publish,
            forbidden=caps.forbidden,processes=caps.proc)
        for signum in (signal.SIGINT,signal.SIGTERM):
            handlers[signum]=signal.signal(signum,lambda number,frame:watchdog.interrupt(number))
        watchdog.start()
        caps.schedule()
        deadline=clock()+15;owner=None
        while owner is None:
            require(clock()<deadline,'Original probe birth observation deadline; no retry/adoption')
            owner=caps.observe_birth()
            if owner is None:sleep(0.01)
        result['original']=owner;watchdog.bind(owner);caps.permit(owner)
        fields=None;deadline=owner['start_monotonic_us']/1e6+355
        while fields is None or not caps.cgroup_absent():
            require(clock()<deadline,'Original probe/cgroup did not terminate after external deadline; preserve unresolved')
            fields=caps.poll();sleep(0.1)
        close_original(fields)
        result['audit']=caps.audit()
        result['valid']=all(x.get('valid') is True for x in (result['watchdog'],result['audit']))
        result['valid']=result['valid'] and result['original_outcome']['exec_code']==1 and result['original_outcome']['status']==0
    except BaseException as error:
        result['error']=repr(error)
        if watchdog is not None:watchdog.interrupt(repr(error))
    finally:
        if watchdog is not None and not watchdog.closed:
            # Never terminate the independent deadline worker while an owned
            # original child can still be executing a blocked setup call.
            if watchdog.owner is not None:
                deadline=clock()+355
                while not watchdog.closed and clock()<deadline:
                    try:
                        fields=caps.poll()
                        if fields is not None and caps.cgroup_absent():
                            close_original(fields);break
                    except BaseException as error:result['cleanup_observation_error']=repr(error);break
                    sleep(0.1)
            if not watchdog.closed:
                watchdog.stop_event.set();watchdog.wake.set()
                for thread in (watchdog.witness_thread,watchdog.deadline_thread):
                    if thread is not None:thread.join(timeout=7)
                result['unresolved_original_resources']=True
        if result['original'] is not None and result['release'] is None:
            result['unresolved_original_resources']=True
        for number,handler in handlers.items():signal.signal(number,handler)
        if getattr(caps,'output',None) is not None:
            try:caps.publish('original-launch-result',result)
            except BaseException as error:result['valid']=False;result['publication_error']=repr(error)
    return result


def child(entry):
    reader,plan,job,modules=load_plan(entry)
    runtime=modules['runtime'].Runtime(job,plan['job'])
    result=modules['core'].execute(runtime,SETTINGS,stopped=runtime.stop_event.is_set)
    if result.get('valid') is True:
        try:checked_child_result(result,modules['core'])
        except Exception as error:
            print(json.dumps(dict(status='FAILED_LAUNCHER_CHILD_CONTENT_VALIDATION',valid=False,
                error=str(error)[:2000],quality_qualified=False,real_ROM_start_proven=False,
                learning_speed_gain_verified=False)),flush=True)
            return 1
    print(json.dumps(dict(status=result['status'],valid=result['valid'],quality_qualified=False,
        real_ROM_start_proven=False,learning_speed_gain_verified=False)),flush=True)
    return 0 if result['valid'] is True else 1


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group();modes.add_argument('--execute',action='store_true');modes.add_argument('--child',action='store_true')
    parser.add_argument('--plan');parser.add_argument('--plan-sha256');parser.add_argument('--source-sha256')
    args=parser.parse_args(argv)
    if not (args.execute or args.child):
        print('PLAN_ONLY: no source/job reads, runtime discovery, unit queries, scheduling, device or signal');return 0
    require(args.plan and args.plan_sha256 and args.source_sha256
        and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,
        'Explicit exact original plan/source hashes required')
    require(hashlib.sha256(Path(args.plan).read_bytes()).hexdigest()==args.plan_sha256,'Original launcher plan differs')
    # Bootstrap full immutable metadata through the fixed evidence reader.
    require(hashlib.sha256(READER.read_bytes()).hexdigest()==EXPECTED['reader'],'Evidence reader changed')
    spec=importlib.util.spec_from_file_location('_startup_entry_reader_'+str(time.time_ns()),READER)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader);entry=reader.pin(args.plan)
    reader.read_pin(entry)
    if args.child:return child(entry)
    return 0 if execute(entry)['valid'] else 1


if __name__=='__main__':sys.exit(main())
