"""One owned 7067 handoff: close original R1, review once, continue once.

Default inert. Existing d095/ab5/d821 consumers remain unchanged. No R1
launch/adoption/retry, no PUBLIC or canonical/study-status writes, no projector.
The first-review wrapper owns its review-controller Popen; this operator owns
its scheduling carrier and the direct continuation Popen through wait/reap.
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

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE=ROOT/'logs/managed-learning-20261015/run-26'
STATE=ROOT/'logs/managed-learning-20261015/state.json'
SOURCES={'helpers': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'reader': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py', 'sha256': 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', 'bytes': 30116, 'identity': {'device': 2304, 'inode': 80249582, 'bytes': 30116, 'mtime_ns': 1792393596284579365, 'ctime_ns': 1792393631058725163, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'review_preparer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/prepare_deadline_independent_review_v4.py', 'sha256': 'd0955c345dd46d08d261cf6c20c8dff87e1335c4977d55d75a8ed895fac99be0', 'bytes': 17179, 'identity': {'device': 2304, 'inode': 85333911, 'bytes': 17179, 'mtime_ns': 1793297226271097135, 'ctime_ns': 1793297226271097135, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'first_review_wrapper': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/durable-first-R1-review-source-original01/run_owned_first_physical_R1_review_v1.py', 'sha256': 'ab5a0cf0cb69e0cf22ced1b608344e7b58ad1d243300df6d5c4fa4ee51b8225f', 'bytes': 11520, 'identity': {'device': 2304, 'inode': 85339090, 'bytes': 11520, 'mtime_ns': 1793301324310570634, 'ctime_ns': 1793301324310981770, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'continuation': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/postguard-owned-operations-generic-original02/sequence_physical_deadline_study_v3.py', 'sha256': 'd821a0121ad4b2cdec82877299d5666aecee56b42aa11c5ce70c738096cc80f9', 'bytes': 21820, 'identity': {'device': 2304, 'inode': 85333611, 'bytes': 21820, 'mtime_ns': 1793295575238127945, 'ctime_ns': 1793295575238127945, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'owned_helper': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py', 'sha256': 'b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4', 'bytes': 20193, 'identity': {'device': 2304, 'inode': 82217207, 'bytes': 20193, 'mtime_ns': 1792698816935644930, 'ctime_ns': 1792698816935644930, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'A5_release_adapter': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/completed-A5-wrapper-release-source-original01/close_completed_A5_wrapper_v1.py', 'sha256': 'bf88d6438217082375831f35c4111eae13f7c5ce99887e780a62ab1a338cb066', 'bytes': 20965, 'identity': {'device': 2304, 'inode': 85350055, 'bytes': 20965, 'mtime_ns': 1793305752641830570, 'ctime_ns': 1793305785000471385, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'wrapper_kernels': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/control_quality32_review_v1.py', 'sha256': '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', 'bytes': 17290, 'identity': {'device': 2304, 'inode': 81930188, 'bytes': 17290, 'mtime_ns': 1792424008109022468, 'ctime_ns': 1792424257834393599, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
EXPECTED_SELECTION_SHA='7067e638c7b47e5b34b14c2076af0717d142c23bcbaade4484298c570abe7e5b'
A5_STATUS='PASS_ORIGINAL_A5_WRAPPER_EXIT0_ARCHIVED_AND_RELEASED'


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


def dependencies():
    for value in SOURCES.values():
        require(hashlib.sha256(Path(value['path']).read_bytes()).hexdigest()==value['sha256'],
                'Exact source-bound handoff dependency changed')
    h=load('_physical_handoff_h',Path(SOURCES['helpers']['path']))
    for value in SOURCES.values():h.checked(value)
    immutable=load('_physical_handoff_immutable',h.checked(SOURCES['reader']))
    def read(value,as_json=True):return immutable.read_pin(value,as_json=as_json)
    return h,read


def prepare(selection,selection_sha,CPU_proof,public_config,output):
    h,read=dependencies();sp=h.pin(selection.resolve())
    require(sp['sha256']==selection_sha==EXPECTED_SELECTION_SHA,'Exact actual7067 R1 selection required')
    selected=read(sp);rp=selected['sources']['review_preparer']
    require(selected['schema']=='robotron-generic-physical-original-R1-launch-selection-v1'
            and rp==SOURCES['review_preparer'],'Exact already-launched private study source required')
    ready=read(selected['readiness']);pp=ready['review_precommit']
    p=load('_physical_handoff_prepare_review',h.checked(rp))
    _,_,actual_pp,packet,case=p.selected(Path(pp['path']),'R1')
    require(actual_pp==pp and packet['native_prepared']==selected['prepared_manifest'],
            'Actual launch and review precommit differ')
    root=Path(case['native_job']['path']).parent.parent
    ownerpin=h.pin(Path(selected['source']['path']).parent/'actual-original-R1-live-owner.json');owner=read(ownerpin)
    require(owner['original_job']==case['native_job']and owner['config']==case['native_config'],
            'Original R1 owner/job/config differs')
    helper=load('_physical_handoff_original_helper',h.checked(SOURCES['owned_helper']))
    require(helper.birth(owner['wrapper_pid'])==owner['wrapper_birth'],
            'Prepare while the same original R1 wrapper still owns its attempt')
    cp=h.pin(CPU_proof.resolve());closed=read(cp);report=read(closed['actual_report']);cpu=read(closed['original_job'])
    require(closed['actual_exit']==0 and closed['status']=='PASS_ENGINEERING_ONLY'
            and closed['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified']is True
            and report['status']=='PASS'and report['tests_run']==12
            and report['original_job']==closed['original_job']
            and h.pin(Path(__file__).resolve())in cpu['inputs']
            and SOURCES['A5_release_adapter']in cpu['inputs'], 'Exact source-specific12 lifecycle CPU proof required')
    pubpin=h.pin(public_config.resolve());pub=read(pubpin)
    require(pub['schema']=='robotron-generic-physical-public-status-selection-v1'
            and pub['launch_selection']==sp and pub['sequence_source']==SOURCES['continuation']
            and pub['source']['sha256']=='84e35d12c0a5e6864bf2eb3c4ebe800294dd78b843097efe80f11ca009ae6a3b',
            'Existing sole PUBLIC publisher must select this same study and continuation')
    # The consumed startup handoff public_preimage is intentionally not re-read.
    continuation=Path(pub['sequence_directory'])
    require(continuation.parent==root and continuation.is_absolute()and not continuation.exists(),
            'Exact fresh continuation output selected by existing PUBLIC bridge required')
    current=json.loads(STATE.read_bytes())
    require((current.get('active_quality_job')or{}).get('directory')==str(root),'Active original study changed')
    for row in packet['cases']:
        require(not Path(row['review_job_path']).exists()and not Path(row['execution']).exists(),
                'An original review attempt is already consumed')
    output=output.absolute();require(output.resolve()==output and output.parent==root and not output.exists(),
            'Fresh study-owned enclosing handoff directory required')
    adapter_dir=Path(SOURCES['A5_release_adapter']['path']).parent
    release_output=adapter_dir/'actual-handoff-A5-wrapper-release-original01'
    require(not release_output.exists(),'Original A5 wrapper-release output already consumed')
    output.mkdir(mode=0o700)
    unit='robotron-physical-cohort-proof2s-'+selected['study_precommit']['sha256'][:16]+'-automatic-handoff-original01-20261029.service'
    job=dict(schema='robotron-current7067-physical-R1-automatic-handoff-v2',source=h.pin(Path(__file__).resolve()),
        sources=SOURCES,launch_selection=sp,review_precommit=pp,R1_original_owner=ownerpin,CPU_proof=cp,
        public_config=pubpin,study_precommit=selected['study_precommit'],study_directory=str(root),
        output=str(output),continuation_directory=str(continuation),A5_release_output=str(release_output),
        original_attempt=1,no_retry=True,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        original_R1_wait_bound_s=4380,first_review_wrapper_wait_bound_s=2460,
        enclosing_unit=unit,enclosing_resources=dict(cpu_cores=2,memory_bytes=1<<30,runtime_s=30600,tasks=128),
        quality_qualified=False,promotion=False)
    jp=h.put(output/'precommit.json',job)
    argv=['systemd-run','--user','--unit='+unit,'--property=Type=exec','--property=RemainAfterExit=yes',
        '--property=CPUQuota=200%','--property=MemoryMax=1G','--property=MemorySwapMax=0','--property=RuntimeMaxSec=30600',
        '--property=TasksMax=128','--property=TimeoutStopSec=10','--property=SendSIGKILL=no','--property=Restart=no',
        '--property=StandardOutput=append:'+str(output/'handoff.stdout.log'),
        '--property=StandardError=append:'+str(output/'handoff.stderr.log'),
        '--setenv=PYTHONDONTWRITEBYTECODE=1','--setenv=PYTHONUNBUFFERED=1',
        '/usr/bin/python3.12','-I','-B',str(Path(__file__).resolve()),'--run','--precommit',jp['path'],
        '--precommit-sha256',jp['sha256'],'--source-sha256',job['source']['sha256']]
    return h.put(output/'prepared-automatic-handoff-NOT-LAUNCHED.json',dict(precommit=jp,source=job['source'],
        Root_owned_systemd_argv=argv,actual_owner_or_outcome=None,quality_qualified=False,promotion=False))


class Handoff:
    def __init__(self,path,expected):
        self.h,self.read=dependencies();self.pin=self.h.pin(path.resolve())
        require(self.pin['sha256']==expected,'Exact handoff precommit changed');self.job=self.read(self.pin)
        require(self.job['schema']=='robotron-current7067-physical-R1-automatic-handoff-v2'
                and self.job['source']==self.h.pin(Path(__file__).resolve())and self.job['sources']==SOURCES
                and self.job['original_attempt']==1 and self.job['no_retry']is True,'One original source-bound handoff required')
        self.p=load('_physical_handoff_actual_review',self.h.checked(SOURCES['review_preparer']))
        self.helper=load('_physical_handoff_actual_helper',self.h.checked(SOURCES['owned_helper']))
        self.ctl=load('_physical_handoff_completed_wrapper_kernels',self.h.checked(SOURCES['wrapper_kernels']))
        self.adapter=load('_physical_handoff_A5_only_release',self.h.checked(SOURCES['A5_release_adapter']))
        self.sequence=load('_physical_handoff_continuation',self.h.checked(SOURCES['continuation']))
        self.original=self.read(self.job['R1_original_owner']);self.root=Path(self.job['study_directory'])
        self.output=Path(self.job['output']);self.number=0;self.review_owner=None
        fields=self.ctl.show(self.job['enclosing_unit'])
        expected_fields=dict(Id=self.job['enclosing_unit'],MainPID=str(os.getpid()),InvocationID=os.environ.get('INVOCATION_ID'),
            Type='exec',ActiveState='active',SubState='running',NRestarts='0',Restart='no',RemainAfterExit='yes',
            CPUQuotaPerSecUSec='2s',MemoryMax=str(1<<30),MemorySwapMax='0',TasksMax='128',
            RuntimeMaxUSec='8h 30min',TimeoutStopUSec='10s',SendSIGKILL='no')
        require(expected_fields['InvocationID']and all(fields.get(k)==v for k,v in expected_fields.items()),
                'Exact declared2CPU1GiB8h30m original enclosing scope required')
        self.h.put(self.output/'original-owner.json',dict(pid=os.getpid(),birth=self.helper.birth(os.getpid()),
            argv=[x.decode()for x in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]],precommit=self.pin,actual_scope=fields))

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
        self.h.checked(self.job['source'])
        for value in self.job['sources'].values():self.h.checked(value)
        self.h.checked(self.job['public_config'])  # Immutable config only, never its consumed PUBLIC preimage.

    def register(self,stage,owner=None,controller=None):
        return self.event(stage.lower(),dict(stage=stage,scope=owner,controller=controller,unix_s=time.time(),
            canonical_state_written=False,PUBLIC_written=False))

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
        pin=self.adapter.release_completed(Path(self.job['launch_selection']['path']),self.job['launch_selection']['sha256'],
            Path(self.job['A5_release_output']),SOURCES['A5_release_adapter']['sha256'])
        self.require_A5_release(pin)
        return self.event('original-R1-and-A5-wrapper-owned-closed',dict(positive_A5_wrapper_release=pin))

    def require_A5_release(self,pin):
        receipt=self.read(pin);identity=receipt['identity']
        require(receipt['schema']=='robotron-current7067-A5-wrapper-only-owned-release-v1'
                and receipt['status']==A5_STATUS and receipt['lifecycle_complete']is True
                and type(receipt['original_wrapper_exit'])is int and receipt['original_wrapper_exit']==0
                and receipt['original_wrapper_birth_unit_and_captured_cgroup_absent']is True
                and receipt['all_three_archives_succeeded']is True
                and receipt['source']==SOURCES['A5_release_adapter']
                and receipt['launch_selection']==self.job['launch_selection']
                and identity['unit']==self.original['wrapper_unit']
                and identity['pid']==self.original['wrapper_pid']
                and identity['starttime_ticks']==self.original['wrapper_birth']
                and identity['invocation_id']==self.original['wrapper_invocation_id']
                and receipt['original_attempt']==1 and receipt['no_retry']is True
                and receipt['scientific_payload_retried']is False,
                'Positive exact original A5-only release required')
        return receipt

    def prepare_review(self,records):
        gate=self.read(records['original_R1']);self.require_A5_release(gate['positive_A5_wrapper_release'])
        pin=self.p.prepare_leg(Path(self.job['review_precommit']['path']),'R1')
        self.event('first-independent-R1-review-prepared',dict(prepared=pin));return pin

    def review_unit(self):
        return 'robotron-physical-cohort-proof2s-'+self.job['study_precommit']['sha256'][:16]+'-r1-independent-review-wrapper-original01-20261029.service'

    def review_command(self,prepared_pin):
        source=SOURCES['first_review_wrapper'];folder=Path(source['path']).parent
        return ['systemd-run','--user','--unit='+self.review_unit(),'--property=Type=exec','--property=RemainAfterExit=yes',
            '--property=CPUQuota=200%','--property=MemoryMax=512M','--property=MemorySwapMax=0','--property=RuntimeMaxSec=2400',
            '--property=TasksMax=128','--property=TimeoutStopSec=10','--property=SendSIGKILL=no','--property=Restart=no',
            '--property=StandardOutput=append:'+str(folder/'first-R1-review-wrapper-original01.stdout.log'),
            '--property=StandardError=append:'+str(folder/'first-R1-review-wrapper-original01.stderr.log'),
            '--setenv=PYTHONDONTWRITEBYTECODE=1','--setenv=PYTHONUNBUFFERED=1','/usr/bin/python3.12','-I','-B',source['path'],
            '--run','--launch-selection',self.job['launch_selection']['path'],'--launch-selection-sha256',self.job['launch_selection']['sha256'],
            '--prepared',prepared_pin['path'],'--prepared-sha256',prepared_pin['sha256'],'--expected-source-sha256',source['sha256']]

    def release_review_wrapper(self,identity,intent,terminal,qualified,review_closed):
        require(identity['unit']==self.review_unit()and intent['source']==SOURCES['first_review_wrapper']
                and intent['review_precommit']==self.job['review_precommit']
                and terminal['status']=='ORIGINAL_R1_INDEPENDENTLY_QUALIFIED'
                and terminal['actual_controller_exit']==0 and terminal['live_registration_errors']==[]
                and terminal['qualification']==qualified
                and terminal['controller_result']==review_closed['result'],
                'Only this completed first-review wrapper may be released')
        require(self.helper.birth(identity['pid'])!=identity['starttime_ticks'],'First-review wrapper birth remains')
        captured=intent['actual_scope'];unit=identity['unit'];out=self.output/'first-review-wrapper-owned-release-original01'
        require(not out.exists(),'First-review wrapper release attempt already consumed');out.mkdir(mode=0o700)
        captured_cgroup=captured['ControlGroup']
        require(type(captured_cgroup)is str and captured_cgroup.startswith('/user.slice/')
                and captured_cgroup.endswith('/'+unit), 'Exact captured running review-wrapper cgroup required')
        expected=dict(Id=unit,InvocationID=identity['invocation_id'],ExecMainPID=str(identity['pid']),MainPID='0',Type='exec',
            ExecMainCode='1',ExecMainStatus='0',Result='success',NRestarts='0',Restart='no',RemainAfterExit='yes',
            CPUQuotaPerSecUSec='2s',MemoryMax=str(512<<20),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='40min',
            TimeoutStopUSec='10s',SendSIGKILL='no')
        archives=[]
        for action in ('show','cat','journal'):
            argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+identity['invocation_id']]if action=='journal'else['systemctl','--user',action,unit]
            row=self.ctl.command(out,'original-'+action,argv);archives.append(row)
            require(row['exit']==0 and row['timed_out']is False,'First-review wrapper archive failed; leave untouched')
        fields=self.ctl.fields(archives[0]);self.ctl.original_terminal(fields,identity)
        require(all(fields.get(k)==v for k,v in expected.items())and fields.get('ControlGroup')in(None,'',captured_cgroup),
                'First-review wrapper terminal/resources changed')
        current=self.ctl.command(out,'before-release-show',['systemctl','--user','show',unit])
        require(current['exit']==0 and current['timed_out']is False,'First-review wrapper fresh SHOW failed')
        actual=self.ctl.fields(current);self.ctl.original_terminal(actual,identity)
        require(all(actual.get(k)==v for k,v in expected.items())and actual.get('ControlGroup')in(None,'',captured_cgroup),
                'First-review wrapper changed before release')
        released={};self.ctl.release_original(out,'service',identity,dict(timer=None),released)
        require(released['confirmed_absent']is True and self.ctl.show(unit).get('LoadState')=='not-found'
                and self.helper.birth(identity['pid'])!=identity['starttime_ticks']
                and not Path('/sys/fs/cgroup'+captured_cgroup).exists(), 'First-review wrapper release incomplete')
        return self.h.put(out/'owned-release.json',dict(schema='robotron-current7067-first-review-wrapper-only-owned-release-v1',
            status='PASS_ORIGINAL_FIRST_REVIEW_WRAPPER_EXIT0_ARCHIVED_AND_RELEASED',source=self.job['source'],identity=identity,
            original_intent=intent,original_terminal=terminal,qualification=qualified,original_review_closed=review_closed,
            archives=archives,owned_release=released,lifecycle_complete=True,original_wrapper_exit=0,
            original_wrapper_birth_unit_and_captured_cgroup_absent=True,PUBLIC_or_Main_or_fleet_controlled=False))

    def run_review(self,records):
        prepared=records['prepare_review'];folder=Path(SOURCES['first_review_wrapper']['path']).parent
        require(self.ctl.show(self.review_unit()).get('LoadState')=='not-found'
                and not(folder/'first-R1-review-wrapper-intent.json').exists(), 'First-review original already consumed')
        carrier=self.owned_program('first-review-wrapper-scheduling-carrier',self.review_command(prepared))
        carried=self.read(carrier);require(carried['actual_exit']==0 and carried['live_registration_errors']==[],
                'Original first-review scheduling carrier failed; no retry')
        started=time.monotonic();identity=None;intent=None;intentpin=None
        while True:
            intent_path=folder/'first-R1-review-wrapper-intent.json';terminal_path=folder/'first-R1-review-wrapper-terminal.json'
            if intent is None and intent_path.exists()and intent_path.stat().st_mode&0o777==0o444:
                intentpin=self.h.pin(intent_path);intent=self.read(intentpin)
                require(intent['source']==SOURCES['first_review_wrapper']and intent['actual_prepared_review']==prepared
                        and intent['review_precommit']==self.job['review_precommit']
                        and intent['original_R1_owner']==self.job['R1_original_owner']and intent['wrapper_unit']==self.review_unit(),
                        'First-review wrapper actual intent differs')
            if identity is None and intent is not None:
                pid=intent['wrapper_pid'];birth=intent['wrapper_birth'];fields=self.ctl.show(self.review_unit())
                if self.helper.birth(pid)==birth:
                    require(fields.get('MainPID')==str(pid)and fields.get('InvocationID')==intent['wrapper_invocation_id']
                            and fields.get('NRestarts')=='0'and fields.get('ControlGroup')==intent['actual_scope']['ControlGroup'],
                            'Actual original first-review wrapper live identity differs')
                    identity=dict(unit=self.review_unit(),pid=pid,starttime_ticks=birth,
                        invocation_id=intent['wrapper_invocation_id'],observed_live=True)
                    self.review_owner=self.h.put(self.output/'first-review-wrapper-original-owner.json',dict(**identity,intent=intentpin))
            if terminal_path.exists()and terminal_path.stat().st_mode&0o777==0o444:
                require(identity is not None,'Original first-review wrapper live identity missed; no adoption')
                termpin=self.h.pin(terminal_path);terminal=self.read(termpin)
                require(terminal['intent']==intentpin and terminal['wrapper_pid']==identity['pid']
                        and terminal['wrapper_birth']==identity['starttime_ticks']
                        and terminal['status']=='ORIGINAL_R1_INDEPENDENTLY_QUALIFIED'
                        and terminal['actual_controller_exit']==0 and terminal['live_registration_errors']==[],
                        'Original first-review wrapper did not qualify R1; no retry')
                if self.helper.birth(identity['pid'])!=identity['starttime_ticks']:
                    _,_,_,packet,case=self.p.selected(Path(self.job['review_precommit']['path']),'R1')
                    closed=self.p.closed_controller(self.root/'R1','independent-review-',self.read(prepared)['review_config'],packet['sources']['controller'],packet['sources'],self.h,self.read)
                    q=self.h.pin(self.root/'R1/root-R1-independent-qualified.json')
                    require(terminal['qualification']==q and self.read(q)['status']=='INDEPENDENT_DEADLINE32_QUALIFIED',
                            'Actual first-review qualification differs')
                    release=self.release_review_wrapper(identity,intent,terminal,q,closed)
                    return self.event('first-independent-R1-review-owned-closed',dict(scheduling_carrier=carrier,
                        original_wrapper_owner=self.review_owner,original_wrapper_terminal=termpin,owned_release=release,qualification=q))
            if identity is not None and self.helper.birth(identity['pid'])!=identity['starttime_ticks']and not terminal_path.exists():
                raise ValueError('First-review wrapper disappeared without its original terminal; no retry')
            require(time.monotonic()-started<self.job['first_review_wrapper_wait_bound_s'],
                    'First-review observation bound reached; original scope left untouched')
            # STOP prevents the next phase; it never interrupts an already-owned review.
            time.sleep(1)

    def qualify(self,records):
        result=self.read(records['review']);closed=self.read(result['owned_release'])
        require(closed['lifecycle_complete']is True and closed['original_wrapper_exit']==0,
                'First-review wrapper must be positively closed before continuation')
        pin=self.sequence.verify_existing_R1(Path(self.job['review_precommit']['path']),result['qualification'])
        self.event('original-R1-qualification-readonly-replayed',dict(qualification=pin));return pin

    def prepare_continuation(self,records):
        pin=self.sequence.prepare(Path(self.job['review_precommit']['path']),Path(self.job['R1_original_owner']['path']),
            Path(self.job['continuation_directory']))
        self.event('original-continuation-prepared',dict(precommit=pin));return pin

    def owned_program(self,label,argv,on_live=None):
        self.h.put(self.output/(label+'-intent.json'),dict(argv=argv,original_attempt=1,no_retry=True))
        stdout=self.output/(label+'-stdout.txt');stderr=self.output/(label+'-stderr.txt')
        with stdout.open('xb')as out,stderr.open('xb')as err:
            child=subprocess.Popen(argv,stdout=out,stderr=err)
            owner=None;errors=[]
            try:
                owner=self.h.put(self.output/(label+'-owner.json'),dict(pid=child.pid,birth=self.helper.birth(child.pid),argv=argv))
                if on_live:on_live(child)
            except Exception as error:errors.append(repr(error))
            code=child.wait();out.flush();err.flush();os.fchmod(out.fileno(),0o444);os.fchmod(err.fileno(),0o444);os.fsync(out.fileno());os.fsync(err.fileno())
        return self.h.put(self.output/(label+'-terminal.json'),dict(actual_exit=code,owner=owner,live_registration_errors=errors,
            stdout=self.h.pin(stdout),stderr=self.h.pin(stderr)))

    def run_continuation(self,records):
        pin=records['prepare_continuation'];source=SOURCES['continuation']
        result=self.owned_program('continuation',['/usr/bin/python3.12','-I','-B',source['path'],'--run','--precommit',pin['path'],
            '--precommit-sha256',pin['sha256'],'--source-sha256',source['sha256']])
        terminal=self.read(result)
        require(terminal['actual_exit']==0 and terminal['live_registration_errors']==[],
                'Original continuation stopped; preserve failures without retry')
        return result

    def run(self):
        outcome=dict(schema='robotron-current7067-physical-R1-handoff-outcome-v2',precommit=self.pin,original_attempt=1,no_retry=True,
            quality_qualified=False,promotion=False,started_unix_s=time.time())
        try:
            records=walk(self.wait_R1,self.prepare_review,self.run_review,self.qualify,self.prepare_continuation,self.run_continuation,self.check)
            outcome.update(status='ORIGINAL_SCREENING_SEQUENCE_FINISHED',records=records)
        except Exception as error:
            outcome.update(status='STOPPED_NO_RETRY',error=repr(error),traceback=traceback.format_exc(),
                original_observed_review_wrapper=self.review_owner,live_original_payloads_never_signalled_or_retried=True)
        outcome['ended_unix_s']=time.time();pin=self.h.put(self.output/'outcome.json',outcome)
        print(json.dumps(dict(outcome=pin,status=outcome['status'])),flush=True)
        return 0 if outcome['status']=='ORIGINAL_SCREENING_SEQUENCE_FINISHED'else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--run',action='store_true')
    p.add_argument('--launch-selection',type=Path);p.add_argument('--launch-selection-sha256');p.add_argument('--CPU-proof',type=Path)
    p.add_argument('--public-config',type=Path);p.add_argument('--output',type=Path);p.add_argument('--precommit',type=Path)
    p.add_argument('--precommit-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not(a.prepare or a.run):print('PLAN_ONLY_NO_READS_OR_ACTIONS');return 0
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256,'Exact handoff source required')
    if a.prepare:print(json.dumps(prepare(a.launch_selection,a.launch_selection_sha256,a.CPU_proof,a.public_config,a.output)),flush=True);return 0
    return Handoff(a.precommit,a.precommit_sha256).run()


if __name__=='__main__':raise SystemExit(main())
