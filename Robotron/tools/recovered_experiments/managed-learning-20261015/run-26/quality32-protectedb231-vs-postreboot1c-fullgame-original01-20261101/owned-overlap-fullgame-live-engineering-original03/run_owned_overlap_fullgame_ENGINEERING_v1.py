"""UNSELECTED template: later-policy quality32 cohort with source-bound mixed main health.

First two known starts per slot, all64 full games,21540s outer start horizon
and21600s timeout-from-enter, unchanged float32 compiled backend and all32
original startup certificates. The minimum50 floor remains in EACH leg. This native case never qualifies or
promotes a policy; separate independent per-leg and final four-leg review remain.
Main learning is supervised read-only. Default is inert.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

HERE=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal')
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
COHORT_COMPONENTS=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024')
BRIDGE_COMPONENTS=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031/full-game-retirement-source-only-original01-20261101/native-retirement-source-original01')
CAPACITY_PROOF_SHA='5fa6952ba9379aba48c15314b3b2ded6f8858bcdd19891bfcab4155630022d9a'
NEW_CANDIDATE_CLOCK_FLOOR={'learner_frame_count': 3041579470, 'training_steps': 11979944, 'optimized_samples': 47494055936, 'frame_count': 5918642727}
GPU='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
SLOTS=tuple(range(4096,4128))
PORTS={slot:20000+slot-4096 for slot in SLOTS}
LEASE=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
PAIR_SHA='fba1b894115c497cac537499f0d7f1fe0d8d9be28c1d25803d2b6597a6758768'
POLICIES={'engineering': {'sha256': '4ee11dff28d19f39ca452693fe3df643f31ec6a7db124b752b679ea756b1c0d8', 'clocks': {'training_steps': 19289561, 'learner_frame_count': 5036458379, 'optimized_samples': 77434247168, 'frame_count': 9659824354}}}
ROLES={'E1':'engineering'}
HEALTH_DEPENDENCIES={'helpers': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'health': '6124cd533852c4d531188a748eddf6c2b594c31eb9f2c781d80b6a0ed057a5df', 'supervision': '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0', 'window': 'ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a', 'primitives': 'd2feaaffd0ab3a0d6b0b5dd06b9d27b3a6f853b6b1776733eba6f89fbe01ce1a', 'collector': 'de1f6d4aafe185d123d418766e94ca7f6c3aa709427ea8711118a56f6fa27b84', 'transport': '72edfb7c42106011e9551d59e1e43bba0ee8759b9e39402fd6b11dd4f5e7a0ad', 'io': '76f70f1bc8be17a70b8a95be9e6f7d01bf147ff7d38053e499eda21bc8bc0ec1', 'proc_repeat': 'cac772547eecc7269de4a5b4201eb5fb63e1a6463b425cae6f70558695d4c263', 'mixed_transport': '0a2c8251641fafc295e93c72deabae379422054d535e5e8aa591a88b44825378', 'full_health_engine': 'd67e696915762c66f3cb660d40f25ac11f0422e4e83b1d7fe35a8af0b1f9b72d', 'indexed_join': '10c1fe25c3f8b232ec5b32a51f649f626a71c6a7e7e56801b5440782fddd54ce'}
FINALIZER_SHA='64c4001e3a46dd1f620bfa28b088f500bf8e9d3788a463d324cc408d7a42e6ee'
OBSERVER_DEPENDENCIES={'client': '38c7d536301454aa99ead0c158dd63ee79ef0e2fb02d156603e87a05aaaea220', 'worker': '6e935ebec347bcca69cb647cee972275f8fb2384c7620dc99e28bd0dd290cd63', 'protocol': 'f59df995a625ed534af1c2cb54a15c885a8e431ab84e3829e6a8b2c6ceb7bf10', 'controller': '12e479b0eb0545dab32da1d8f8130be3622670207c79ecaf0a164b812fa0ec5a', 'reviewer': '53ff0e62034c98ad7d2c3e9065f9f6acd7549116018cb29bd8822079d81c9b53'}
PREFIX_VALIDATOR_SHA='d86b1fc42e13238be7888545d58bfe7cbe94460ecbaf130417b78c997cf53447'


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def helpers():
    path=HERE/'run_full_policy_startup_v3.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1',
            'Actual CPU integration helper definitions differ')
    return load('_compiled32_original_helper_defs',path)


def validate_job(job):
    require(job.get('engineering_only')is True and job.get('quality_leg')=='E1'
        and job.get('stationary_CPU_report',{}).get('sha256')=='4b8ff21cafe80d65c5ff3614a025857f85a0bae2734f065c06e03cb9885a2bda'
        and job.get('stationary_CPU_closeout',{}).get('sha256')=='140dac315e3f559574010376bb71f5f586490bf95ec4f1dc6115d06959bb1b20'
        and job.get('engineering_slow_slot')==4127 and job.get('engineering_slow_speed')=='1.0',
        'Explicit CPU-qualified ENGINEERING_ONLY stationary policy and fixed slow original required')
    expected_validation=dict(
        quota64_CPU_guards='7eed341e987d32fb5d3d82ad5882a3b315532111d9218330750348940bd8b4b7',
        API_epoch_CPU_guards='bf419e767538ecf79cd1e19be20fcc15ee7c0e4c7e5ab7575250176e76cb3f39',
        native600_integration='037119f8d7b87d6f63660172b069fc28ec96920e89694ef095af382cd395d90d',
        extended_review_capacity=CAPACITY_PROOF_SHA)
    require(set(job['quota64_validation'])==set(expected_validation)
        and all(job['quota64_validation'][key]['sha256']==sha for key,sha in expected_validation.items()),
        'Exact prior quota64/API/native/capacity original engineering proofs required')
    expected_components=dict(view='494dcdbcb0ae30f95f4724435e6bf61c68bec3aa7fc3705e39636c0ba60ddbd0',
        drain='ecd278045df06736ed59c16c6293e6a220968cfb89d38820ae9b2117be075f7b',
        bridge='dd77a7f72553f4b7a487004b3c57ccf87d16dbbb56194e8b3f7b58a8d7b9478a',
        slot_retirement='78c1ed55490690d2fb18268fe2d8616251031a4692c1a8fb08a5cb22f54820e6',
        slot_closeout='d2527d9856c241a6576386543d8e61f3c01a33212f4bf7af525822059992d395')
    require(set(job['quota64_source_pins'])==set(expected_components)
        and all(job['quota64_source_pins'][key]['sha256']==sha for key,sha in expected_components.items()),
        'Exact guarded quota64 view/drain/bridge source family required')
    require(job.get('current_v6_health_source',{}).get('sha256')=='94d898e49672dd8a339a89318cf91a769e7bd898f56e7f3543ff0c98089e9d70'
        and job.get('current_v6_health_qualification',{}).get('sha256')=='6314839bfdcdda56967821a9d362361670c9a6745883dc23923338c07a0242a4'
        and job.get('owned_TRAIN_overlap_source',{}).get('sha256')=='c10b6a2e752b61aa345e648c26ee9bf7b82a711ab73f1351138ee31dcdb2a879'
        and all(type(job.get(k))is dict for k in ('current_main','current_fleet','source_family_manifest')),
        'Exact prospective current-v6 health source/engineering/fresh current owner binding required')
    require(job.get('quality_leg')in ROLES and job.get('quality_pair_precommit',{}).get('sha256')==PAIR_SHA
        and type(job.get('minimum_completed_games'))is int and job['minimum_completed_games']==50,
        'Exact precommitted four-leg pair and minimum50 required')
    selected=POLICIES[ROLES[job['quality_leg']]]
    require(job.get('expected_policy_clocks')==selected['clocks']
        and all(type(v)is int for v in job['expected_policy_clocks'].values()),
        'Exact selected role saved clocks required')
    require(job['schema']=='robotron-compiled-quota64-ENGINEERING-only-v1'
        and job['actor_slots']==list(SLOTS)and job['startup_trace_frames']==1200 and job['origin_port']==19998
        and job['proxy_ports']=={str(k):v for k,v in PORTS.items()}
        and job['device']=='cuda'and job['backend']=='inductor'and job['gpu_uuid']==GPU
        and job['cpu_threads']==2 and job['admission_s']==21540 and job['wall_limit_s']==540 and job['whole_cohort_timeout_s']==21600,
        'Exact compiled32 original scope required')
    require(all(type(job.get(k))is int and job[k]==540 for k in
        ('private_client_idle_timeout_s','private_parked_origin_timeout_s','private_lua_score_stall_timeout_s'))
        and type(job.get('private_score_stall_timeout_s'))is int and job['private_score_stall_timeout_s']==0
        and job['lua']['sha256']=='8f0c7f63ba188b741827302eb3e286b4246e80ea76da9138d35cc321ea93387a','Exact matched full-game parked/idle/score-only watchdog policy required')
    require('acceptance_scope'not in job
        and job.get('historical_startup_acceptance_scope',{}).get('sha256')==
            '692b5c0572d32ffae79b828eb64296c09eaa6b4e59de28ea9316b7f44a59fc77',
        'Historical startup acceptance must be explicitly named; full-tail scope is separately controller-pinned')
    require(all(type(job[k])is int for k in ('startup_trace_frames','origin_port','cpu_threads','admission_s','wall_limit_s','whole_cohort_timeout_s'))
        and all(type(v)is int for v in job['proxy_ports'].values()),'Typed fixed original limits required')
    require(job['source_package']['sha256']=='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
        and job['checkpoint']['sha256']==POLICIES[ROLES[job['quality_leg']]]['sha256']
        and job['validated_CPU_prefix']['sha256']=='7d0cc6f960626fef0b9c0a6c40f68f9dcb55fa98d351c6b25111792156cdb647',
        'Exact frozen source/policy and actual CPU handoff predecessor required')
    required_proofs=dict(compiled_startup='7d44dd648fa22836c96a39d126d468f572b282129c0e1ff0bcc77a96f4efb4da',
        continuation_wire='94412a9e8cb258734c9d6e160e3ff2c4636419559c838a85bd69096397e91b7b',
        host_drain='efc3fe13f58624479f0bed3d50d5616c89b4e46ddcb19d91e292d3d88090d900',
        bridge_ledger='477bb10126f7a15e856979f0c96b8e8e299b5aaefafac0a45cb98bf62b760082')
    require(set(job['full_tail_predecessors'])==set(required_proofs)
        and all(job['full_tail_predecessors'][key]['sha256']==sha for key,sha in required_proofs.items()),
        'Original full-tail component and compiled startup predecessors required')
    require(job['current_main']['owner']['pid']==job['current_fleet']['trainer']['pid']
        and job['current_main']['owner']['starttime_ticks']==job['current_fleet']['trainer']['birth'],
        'Current Main owner and actual v6 fleet must agree')
    require(job['lease']['path']==str(LEASE)and job['lease']['bytes']==0
        and job['lease']['sha256']==hashlib.sha256(b'').hexdigest()
        and job['lease']['identity']['mode']=='0o600'and job['lease']['identity']['uid']==os.geteuid()
        and job['lease']['identity']['nlink']==1,'Precommitted permanent GPU coordinator required')
    require(set(job['sessions'])==set(job['connections'])=={str(slot)for slot in SLOTS},
            'All32 original session/connection bindings required')
    values=[*job['sessions'].values(),*job['connections'].values()]
    require(len(set(values))==64 and all(type(v)is str and len(v)==32
        and v!='0'*32 and all(c in '0123456789abcdef'for c in v)for v in values),
        'Exactly64 distinct fresh nonzero identities required')
    output=Path(job['output'])
    require(output.is_absolute()and output.resolve()==output and not output.exists()
        and output.parent.is_dir(),'Fresh exact private output required')
    return output


def actor_environment(base,private,slot,session,connection,library):
    require(type(slot)is int and slot in SLOTS,'Unexpected original slot')
    env={k:v for k,v in base.items()if not k.startswith('ROBOTRON_')and k not in ('LD_PRELOAD','PYTHONPATH')}
    env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',CUDA_VISIBLE_DEVICES='',
        XDG_CONFIG_HOME=str(private/'mame-config'),XDG_DATA_HOME=str(private/'mame-data'),
        LD_PRELOAD=str(library),ROBOTRON_SOCKET_WAIT_US='1000',ROBOTRON_SOCKET_WAIT_PORT=str(PORTS[slot]),
        ROBOTRON_SOCKET_ADDRESS='127.0.0.1:'+str(PORTS[slot]),ROBOTRON_CLIENT_SLOT=str(slot),
        ROBOTRON_EVAL_MODE='1',ROBOTRON_PREVIEW_CLIENT='0',ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES='0',
        ROBOTRON_ENABLE_RRCHRIS_PATCH='0',ROBOTRON_FULL_STARTUP_TRACE=str(private/'producer.jsonl'),
        ROBOTRON_FULL_STARTUP_SLOT=str(slot),ROBOTRON_FULL_STARTUP_SESSION=session,
        ROBOTRON_FULL_STARTUP_CONNECTION=connection,ROBOTRON_FULL_TAIL_LIFECYCLE=str(private/'lifecycle.jsonl'))
    return env


def actor_command(job,private):
    argv=[job['mame']['path'],'robotron','-rompath',job['rompath'],'-noreadconfig','-cheat',
        '-noplugins','-nothrottle','-sound','none','-video','none','-skip_gameinfo',
        '-autoboot_script',str(private/'boot.lua'),'-inipath',str(private/'ini')]
    for option,name in [('cfg','cfg'),('nvram','nvram'),('input','inp'),('state','sta'),
        ('snapshot','snap'),('diff','diff'),('share','share'),('comment','comments')]:
        argv.extend(['-'+option+'_directory',str(private/name)])
    if int(private.name)==job['engineering_slow_slot']:
        argv.extend(['-throttle','-speed',job['engineering_slow_speed']])
    return argv


class PrivateLease:
    """Lock a precommitted permanent coordinator; never rewrite or unlink it."""
    def __init__(self,expected):
        self.expected=json.loads(json.dumps(expected));self.path=Path(expected['path'])
        self.fd=None;self.locked=False
    def current(self):
        value=self.path.lstat()
        require(stat.S_ISREG(value.st_mode),'Coordinator must be an original regular file')
        return helpers().pin(self.path)
    def acquire(self):
        require(self.current()==self.expected,'Precommitted coordinator identity changed')
        fd=os.open(self.path,os.O_RDWR|os.O_NOFOLLOW)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            value=os.fstat(fd)
            require((value.st_dev,value.st_ino)==(self.expected['identity']['device'],self.expected['identity']['inode'])
                and self.current()==self.expected,'Coordinator changed during lock acquisition')
        except Exception:
            os.close(fd)
            raise
        self.fd=fd;self.locked=True
        return dict(coordinator=self.expected,owner_pid=os.getpid(),owner_birth=process_birth(os.getpid()),
                    exclusive_lock_held=True,persistent_file_preserved=True)
    def release(self):
        require(self.fd is not None and self.locked,'No original coordinator lock held')
        value=os.fstat(self.fd)
        require(self.current()==self.expected and (value.st_dev,value.st_ino)==
            (self.expected['identity']['device'],self.expected['identity']['inode']),
            'Coordinator replaced; no foreign-file action')
        fcntl.flock(self.fd,fcntl.LOCK_UN);os.close(self.fd);self.fd=None;self.locked=False


def process_birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def await_original_actor_exits(actors,timeout_s=20):
    """Reap the same owned Popen objects after origin/bridge shutdown; no signals.

    Negative and nonzero statuses remain actual statuses. An observation
    deadline leaves explicit unknowns; it never manufactures successful exits.
    """
    require(type(timeout_s)in (int,float)and 0<timeout_s<=20,'Bounded original child wait required')
    deadline=time.monotonic()+timeout_s
    while True:
        exits={};unknown=[]
        for slot,row in actors.items():
            child=row['child']
            if child is None:continue
            require(isinstance(child,subprocess.Popen),'Only original owned Popen objects may be reaped')
            code=child.poll()
            if code is None:
                actual_birth=process_birth(child.pid)
                if actual_birth is None:
                    # Normal exit can race poll -> /proc. Reap the SAME child;
                    # disappearance itself is never treated as an exit code.
                    code=child.poll()
                    require(code is not None,'Original child disappeared without an available exit status')
                else:
                    require(actual_birth==row['birth'],'Original child birth changed; no status inferred')
                    unknown.append(slot)
            else:require(type(code)is int,'Actual original child exit required')
            exits[str(slot)]=dict(pid=child.pid,birth=row['birth'],actual_exit=code)
        if not unknown or time.monotonic()>=deadline:
            return dict(all_original_children_reaped=not unknown,original_children=exits,
                unknown_slots=unknown,signals_sent=False,exit_statuses_normalized=False)
        time.sleep(min(.05,max(0,deadline-time.monotonic())))


def finalize_actor_outputs(row,all_children_reaped,all_threads_stopped,pin):
    """Never chmod/hash a generated output while an original writer can remain."""
    require(type(all_children_reaped)is type(all_threads_stopped)is bool,'Explicit owned closure required')
    child=row['child']
    safe=bool(all_children_reaped and all_threads_stopped and (child is None or child.poll()is not None))
    files={};unsealed=[]
    for name in ('producer.jsonl','lifecycle.jsonl','proxy.jsonl','actor-stdout.txt','actor-stderr.txt','boot.lua'):
        path=row['private']/name
        if not path.exists():continue
        if safe:path.chmod(0o444);files[name]=pin(path)
        else:unsealed.append(str(path))
    return dict(files=files,outputs_sealed_after_original_writer_closure=safe,
                original_unsealed_output_paths=unsealed)


def persist_main_observation(directory,index,snapshot,wire,validate,h):
    """Keep the actual failing census/API before a health assertion can throw."""
    path=directory/f'{index:04d}-API.raw.json'
    with path.open('xb')as stream:
        stream.write(wire);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o444)
    record=dict(snapshot=h.put(directory/f'{index:04d}-census.json',snapshot),
        raw_API=h.pin(path),learner_frames=None,training_steps=None,unix_s=time.time())
    try:
        api=json.loads(wire)
        record.update(learner_frames=api['learner_frame_count'],training_steps=api['training_steps'])
        validate(api)
    except Exception as error:
        failure=h.put(directory/f'{index:04d}-failed-validation.json',dict(
            original_observation=record,accepted=False,actual_error=repr(error),
            raw_census_and_API_preserved_before_validation=True))
        return record,failure,error
    return record,None,None


def validate_lifecycle(raw,subject,proxy):
    """Join bounded actual Lua STOP application to consumed host authorization."""
    import wire_codec_v2 as codec
    require(type(raw)is bytes and len(raw)<=32768 and raw.endswith(b'\n'),
            'Bounded complete original lifecycle required')
    rows=[codec.decode_json(line)for line in raw.splitlines()]
    require(len(rows)==6 and [r['kind']for r in rows]==
        ['header','prefix_closed','stop_response','stop_applied','exit_requested','closed'],
        'Actual Lua lifecycle failed, incomplete or reordered')
    for event,row in enumerate(rows,1):
        require(row['schema']=='robotron-full-tail-lifecycle-v2' and type(row['event'])is int and row['event']==event
            and all(type(row.get(k))is type(v)and row[k]==v for k,v in subject.items()),
            'Actual Lua lifecycle subject/event differs')
    header,prefix,response,applied,exit_requested,closed=rows
    summary=proxy.prefix_summary
    require(header['sequence']==0 and header['trace_frame_limit']==1200 and header['continuation_enabled']is True
        and prefix['sequence']==1200 and prefix['failed']is prefix['machine_exit_requested']is False
        and prefix['trace_events']==summary['events']
        and all(prefix[k]==summary['footer'][k]for k in ('first_play_sequence','initialized_sequence','latched_sequence')),
        'Actual Lua prefix lifecycle differs from the closed original trace')
    wire=proxy.last_response;decoded=codec.decode_response(wire)
    require(decoded['stop']is decoded['latched']is True and decoded['sequence']==proxy.sequence>1200
        and proxy.stop_receipt['sequence']==proxy.sequence
        and all(row['sequence']==proxy.sequence for row in (response,applied,exit_requested,closed))
        and all(row['response_hex']==wire.hex()for row in (response,applied,exit_requested))
        and response['nonce']==applied['nonce']==decoded['nonce']==proxy.issuer.nonce
        and applied['socket_ok']is applied['apply_ok']is exit_requested['apply_ok']is True
        and applied['debug_bypass']is applied['held_start_before_response']is False
        and applied['start']==decoded['start'] and applied['coin']==decoded['coin']
        and closed['reason']=='drained_shutdown' and closed['failed']is False and closed['stop_received']is True,
        'Actual client did not apply the exact original host-authorized STOP')
    return rows


def validate_main_health_contract(job,protocol,family):
    """Exact native producer/consumer contract, callable before private actions."""
    require(protocol['schema']=='robotron-native-quota64-dedicated-main-health-protocol-v1'
        and protocol['health_job']['binding']==job['main_binding']
        and family['runtime']==job['runtime']
        and set(protocol['health_job']['sources'])==set(HEALTH_DEPENDENCIES)
        and all(protocol['health_job']['sources'][key]['sha256']==sha for key,sha in HEALTH_DEPENDENCIES.items())
        and family['main_prefix_validator']['sha256']==PREFIX_VALIDATOR_SHA
        and family['main_health_finalizer']['sha256']==FINALIZER_SHA
        and set(family['main_observer'])==set(OBSERVER_DEPENDENCIES)
        and all(family['main_observer'][key]['sha256']==sha for key,sha in OBSERVER_DEPENDENCIES.items()),
        'Exact prospective main-health engine/dependencies/family/binding required')


def run(job,jp,h):
    output=validate_job(job)
    require(not os.environ.get('LD_PRELOAD'),'Never preload Python')
    for entry in job['inputs']:h.checked(entry)
    for entry in list(job['quota64_validation'].values())+list(job['quota64_source_pins'].values()):h.checked(entry)
    root,package_pins=h.package_inputs(job['source_package'])
    output.mkdir(mode=0o700);(output/'actors').mkdir(mode=0o700)
    stopped=threading.Event();bridge_stop=threading.Event();errors=[];actors={};streams=[]
    health_stop=threading.Event();health_worker=None;main_lock=threading.Lock()
    main_guard=None;main_guard_report=None;main_guard_failure=None;main_finalizer=None;main_initial_readiness=None
    drain=None;drain_lock=threading.Lock();drain_payload=None;drain_identifier=None;retirement_partition=None
    server=actor=controller=server_worker=None;policy_before=policy_after=None;compile_before=None
    before_stop=after_stop=controller_exit=None;acquisition=None;library_entry=None
    lease=PrivateLease(job['lease']);lease_entry=None;main_samples=[];source_unchanged=False
    main_failures=[];main_observation_index=0;child_reap=None;all_threads_stopped=False
    started=time.monotonic();deadline=started+job['wall_limit_s']
    previous={sig:signal.signal(sig,lambda *_:stopped.set())for sig in (signal.SIGTERM,signal.SIGINT)}
    try:
        lease_entry=lease.acquire();h.put(output/'original-lease.json',lease_entry)
        gpu_before=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory',
            '--format=csv,noheader'],capture_output=True,text=True,timeout=10)
        require(gpu_before.returncode==0 and GPU not in gpu_before.stdout,'Private GPU0 is not idle')
        h.put(output/'original-GPU-before.json',dict(exit=gpu_before.returncode,stdout=gpu_before.stdout,stderr=gpu_before.stderr))
        h.checked(job['current_v6_health_qualification'])
        current_health=load('_fullgame_current_v6_main_health',h.checked(job['current_v6_health_source']))
        main_guard=current_health.CurrentV6MainHealth(job,output,h);main_guard.start()
        def collect_main():
            record=main_guard.observe()
            require(len(main_samples)<20000,'Original current-v6 observation ceiling exceeded; no truncation')
            main_samples.append(record);return record
        def check_main(require_closed=False):
            while True:
                with main_lock:record=collect_main()
                if not require_closed or not record['phase']['overlap_pending']:return record
                require(time.monotonic()<deadline and not stopped.is_set(),'No late current-v6 health rescue')
                time.sleep(.2)
        initial_ready=check_main(require_closed=True)
        main_initial_readiness=h.put(output/'original-initial-current-v6-main-readiness.json',initial_ready)
        def watch_main():
            while not health_stop.wait(5):
                try:
                    with main_lock:
                        if health_stop.is_set():return
                        collect_main()
                except Exception as error:
                    errors.append('Original current-v6 physical Main watch: '+repr(error));stopped.set();return
        health_worker=threading.Thread(target=watch_main,name='fullgame-current-v6-physical-Main',daemon=True)
        health_worker.start()
        sidecar=load('_compiled32_profile06_sidecar',root/'tools/run_frozen_sidecar.py')
        sidecar.configure_environment(SimpleNamespace(directory=output,gpu_uuid=GPU,device='cuda',
            completion_policy='confirmed_reset_reserves_v1',game_boundary_diagnostics=True,cpu_threads=2))
        os.environ['DQN_CLIENT_IDLE_TIMEOUT_S']=str(job['private_client_idle_timeout_s'])
        sys.path.insert(0,str(root/'Scripts'));sys.path.insert(0,str(HERE))
        sys.path.insert(0,str(COHORT_COMPONENTS));sys.path.insert(0,str(BRIDGE_COMPONENTS))
        import torch
        from dqn import config
        from dqn.inference_actor import InferenceActor
        from dqn.managed_measurement import ManagedMeasurement
        from dqn.socket_server import SocketServer,parse_frame_data,CLIENT_IDLE_TIMEOUT_S
        require(CLIENT_IDLE_TIMEOUT_S==540.0,'Actual private full-game idle lifetime differs')
        config.RL_CONFIG.client_stall_timeout_s=job['private_score_stall_timeout_s']
        require(config.RL_CONFIG.client_stall_timeout_s==0,'Private score-only watchdog remains enabled')
        import full_startup_proxy_slot_retirement_v1 as bridge
        import slot_quota_retirement_v1 as slot_retirement
        slot_closeout=load('_owned_engineering_full_slot_archival',h.checked(job['quota64_source_pins']['slot_closeout']))
        import startup_handoff_v2 as authority
        import fixed_slot_cohort_view_v1 as quota_view
        import fixed_slot_cohort_drain_v1 as quota_drain
        CohortDrain=quota_drain.CohortDrain
        QuotaMeasurement=quota_view.measurement_type(ManagedMeasurement)
        from tail_ledger_v1 import BoundedWitness
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        config.RL_CONFIG.inference_batch_max_size=16
        source=h.checked(job['checkpoint']);checkpoint=output/'checkpoint.pt'
        import shutil
        with source.open('rb')as incoming,checkpoint.open('xb')as outgoing:
            shutil.copyfileobj(incoming,outgoing);outgoing.flush();os.fsync(outgoing.fileno());os.fchmod(outgoing.fileno(),0o444)
        acquisition=h.pin(checkpoint)
        require(acquisition['sha256']==job['checkpoint']['sha256'],'Acquired policy bytes differ')
        actor=InferenceActor(checkpoint,device='cuda:0',inference_backend='inductor')
        metadata=actor.checkpoint_metadata
        import numpy as np
        loaded_actions=[]
        for batch in range(1,17):
            actions=actor.act_batch(np.zeros((batch,actor.state_size),dtype=np.float32),[0.0]*batch)
            require(actions==[(8,8,False)]*batch,'Actual compiled GPU engineering policy is not stationary')
            loaded_actions.append(dict(batch=batch,actions=actions))
        h.put(output/'original-compiled-engineering-idle-actions.json',dict(checkpoint=acquisition,checks=loaded_actions,engineering_only=True))
        require(all(metadata.get(key)==value and type(metadata.get(key))is int
                    for key,value in job['expected_policy_clocks'].items()),
                'Actual loaded role policy clocks differ from the precommitted CPU-verified policy')
        for key in ('learner_frame_count','frame_count','measurement_frame_count'):
            setattr(config.metrics,key,int(metadata[key]))
        config.metrics.total_training_steps=actor.training_steps
        config.metrics.total_optimized_samples=actor.optimized_samples
        config.metrics.training_enabled=False;config.metrics.preview_capture_enabled=False;config.metrics.hud_enabled=False
        for key,value in dict(start_advanced=False,start_level_min=1,epsilon_pct=0,expert_pct=0,
                              auto_curriculum=False,difficulty=5).items():setattr(config.game_settings,key,value)
        require(torch.cuda.device_count()==1 and os.environ['CUDA_VISIBLE_DEVICES']==GPU
            and actor.memory is actor.optimizer is None,'Actual private GPU inference isolation differs')
        server=SocketServer('127.0.0.1',19998,actor,replay_enabled=False)
        def boundary(generation):
            value=server.measurement_boundary_status(generation)
            value['ready']=bool(value['ready']and value['clients']==32 and value['actor_slots']==list(SLOTS))
            return value
        controller=QuotaMeasurement(actor,config.metrics,server.game_journal,boundary_status=boundary)
        controller.enter(job['label'],cohort_s=job['admission_s'],timeout_s=job['whole_cohort_timeout_s'])
        base_policy_reader=authority.live_policy_reader(actor,config.metrics,server,config.game_settings,
            checkpoint_path=checkpoint,checkpoint_sha256=acquisition['sha256'],actor_source_sha256=job['actor_source_sha256'])
        def policy_reader():
            return dict(base_policy_reader(),cohort_selection=json.loads(json.dumps(quota_drain.COHORT_SELECTION)))
        policy_before=policy_reader();compile_before=actor.compile_report
        quota_view.install_view(server,controller,policy_before)
        require(policy_before['numeric_policy']['compiled']is True and compile_before['all_shapes_verified']==list(range(1,17)),
                'Actual common compiled backend readiness differs')
        h.put(output/'original-loaded-policy.json',dict(policy=policy_before,compile_report=compile_before,
            gpu_uuid=GPU,CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],replay_enabled=server.replay_enabled,
            memory_is_none=actor.memory is None,optimizer_is_none=actor.optimizer is None))
        check_main();require(not stopped.is_set()and time.monotonic()<deadline,'Interrupted before original fleet')
        seed=load('_compiled32_seed_restore_defs',h.checked(job['seed_runtime']))
        builder=load('_compiled32_wait_builder',root/'tools/build_socket_wait.py')
        library=builder.build(output/'socket-wait-build');library.chmod(0o444);library_entry=h.pin(library)
        def admission():
            if controller.start_ts is None:return None
            return dict(open_unix_ns=int(controller.start_ts*1e9),close_unix_ns=int(controller.close_ts*1e9),
                        generation=controller.generation,experiment=controller.label)
        subjects=[dict(slot=slot,session=job['sessions'][str(slot)],connection=job['connections'][str(slot)])for slot in SLOTS]
        def drain_reader():
            nonlocal drain
            with drain_lock:
                if drain is None and controller.start_ts is not None:
                    drain=slot_retirement.SlotQuotaRetirement(CohortDrain(
                        server.game_journal,controller,subjects=subjects,
                        policy_reader=policy_reader,admission_reader=admission))
                return drain
        server_worker=threading.Thread(target=server.start,name='compiled32-origin',daemon=True);server_worker.start()
        ready_end=min(deadline,time.monotonic()+15)
        while not server.running:
            require(server_worker.is_alive()and time.monotonic()<ready_end,'Original compiled origin failed to bind');time.sleep(.01)
        for slot in SLOTS:
            private=output/'actors'/str(slot);private.mkdir(mode=0o700)
            for name in ('cfg','nvram','ini','inp','sta','snap','diff','share','comments','mame-data','mame-config'):
                (private/name).mkdir(mode=0o700)
            restored=seed.restore_seed(job,private)
            trace=private/'producer.jsonl';trace.touch(mode=0o600);s=trace.stat()
            trace_identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
            lifecycle=private/'lifecycle.jsonl';lifecycle.touch(mode=0o600);ls=lifecycle.stat()
            lifecycle_identity=dict(device=ls.st_dev,inode=ls.st_ino,mode=oct(stat.S_IMODE(ls.st_mode)),uid=ls.st_uid,nlink=ls.st_nlink)
            witness=(private/'proxy.jsonl').open('xb');streams.append(witness)
            witness_writer=BoundedWitness(witness)
            emit=witness_writer.emit
            proxy=bridge.StartupProxy(server,slot=slot,session=job['sessions'][str(slot)],connection=job['connections'][str(slot)],
                trace_path=trace,trace_identity=trace_identity,rom_sha256=job['loaded_rom_sha256'],policy_reader=policy_reader,
                admission_reader=admission,frame_parser=parse_frame_data,emit=emit,stop_event=bridge_stop,
                drain_reader=lambda slot=slot:None if drain_reader()is None else drain_reader().for_slot(slot),
                parked_origin_timeout_s=job['private_parked_origin_timeout_s'])
            listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,0)
            listener.bind(('127.0.0.1',PORTS[slot]));listener.listen(1);listener.settimeout(30)
            def serve(listener=listener,proxy=proxy,slot=slot):
                try:
                    with listener.accept()[0]as peer,socket.create_connection(('127.0.0.1',19998),timeout=5)as origin:
                        proxy.serve(peer,origin)
                except Exception as error:errors.append('Original slot'+str(slot)+': '+repr(error))
            worker=threading.Thread(target=serve,name='compiled32-proxy-'+str(slot),daemon=True)
            actors[slot]=dict(private=private,proxy=proxy,listener=listener,worker=worker,child=None,birth=None,
                boot_restore=restored,trace_identity=trace_identity,lifecycle_identity=lifecycle_identity,
                witness_writer=witness_writer,worker_started=False)
            with (private/'boot.lua').open('x')as stream:
                stream.write('local ok,err=pcall(function() assert(loadfile('+json.dumps(job['lua']['path'])+'))() end)\n'
                    'if not ok then print("COMPILED32_FULL_TAIL_FATAL "..tostring(err));manager.machine:exit() end\n')
        for slot,row in actors.items():
            require(not stopped.is_set()and time.monotonic()<deadline,'Interrupted during original fleet launch')
            row['worker'].start();row['worker_started']=True
            private=row['private'];env=actor_environment(os.environ,private,slot,job['sessions'][str(slot)],
                                                       job['connections'][str(slot)],library)
            out=(private/'actor-stdout.txt').open('xb');err=(private/'actor-stderr.txt').open('xb');streams.extend([out,err])
            argv=actor_command(job,private)
            child=subprocess.Popen(argv,stdout=out,stderr=err,stdin=subprocess.DEVNULL,env=env,cwd=private)
            row.update(child=child,birth=process_birth(child.pid))
            require(row['birth']is not None,'Original actor birth not captured')
            h.put(private/'original-actor.json',dict(pid=child.pid,starttime_ticks=row['birth'],slot=slot,
                session=job['sessions'][str(slot)],connection=job['connections'][str(slot)],argv=argv,
                original_job=jp,trace_identity=row['trace_identity'],lifecycle_identity=row['lifecycle_identity'],
                proxy_port=PORTS[slot],boot_restore=row['boot_restore']))
        fixed_window=None;last_status=0;status_index=0
        (output/'status-samples').mkdir(mode=0o700)
        while True:
            require(time.monotonic()<deadline and not stopped.is_set(),'Original compiled32 wall bound/interruption')
            require(not errors and server.inference_only_error is None and server_worker.is_alive()and server.running,
                    'Original bridge/inference/server failed')
            for slot,row in actors.items():
                child=row['child']
                require(child is not None and row['proxy'].error is None,'Original slot bridge failed')
                if child.poll()is None:require(process_birth(child.pid)==row['birth'],'Original actor birth changed')
                else:require(child.returncode==0 and row['proxy'].stop_sent.is_set(),
                    'Original actor exited nonzero or before host-authorized drain')
            status=controller.tick()
            require(status['valid']is not False,'Original complete-cohort controller invalidated: '+str(status['reason']))
            window_value=admission()
            if window_value is not None:
                if fixed_window is None:fixed_window=window_value;h.put(output/'original-fixed-admission.json',window_value)
                require(window_value==fixed_window,'Original admission moved')
                actual_drain=drain_reader()
                require(actual_drain is not None and actual_drain.state!='failed','Original host drain failed')
                if actual_drain.permit is None:
                    require(boundary(controller.generation)['ready'],'All32 original slots must remain acknowledged')
                    if all(row['proxy'].prefix_verified.is_set()for row in actors.values()):
                        permit=actual_drain.try_issue()
                        if permit is not None:
                            drain_payload=json.loads(permit.payload);drain_identifier=permit.identifier
                            h.put(output/'original-complete-cohort-drain-permit.json',
                                dict(identifier=permit.identifier,**drain_payload))
                if drain_payload is not None:
                    require(status['complete']is status['valid']is True,'Original cohort changed after drain publication')
            if time.monotonic()-last_status>=5:
                current=dict(schema='robotron-original-fullgame-ENGINEERING32-live-status-v1',observed_unix_s=time.time(),
                    original_pid=os.getpid(),original_birth=process_birth(os.getpid()),
                    original_job=jp,controller=status,fixed_admission=fixed_window,
                    drain_identifier=drain_identifier,quality_qualified=False,
                    slots={str(slot):dict(pid=row['child'].pid,birth=row['birth'],actual_exit=row['child'].poll(),
                        sequence=row['proxy'].sequence,handoff=row['proxy'].handoff,
                        prefix_verified=row['proxy'].prefix_verified.is_set(),stop_sent=row['proxy'].stop_sent.is_set(),
                        peer_EOF=row['proxy'].peer_eof.is_set(),error=row['proxy'].error,
                        ledger=row['proxy'].ledger.summary())for slot,row in actors.items()},
                    main_observations=len(main_samples),errors=list(errors))
                h.put(output/'status-samples'/f'{status_index:04d}.json',current);status_index+=1
                temp=output/'status.next.json'
                with temp.open('w')as stream:
                    json.dump(current,stream,separators=(',',':'),allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
                os.replace(temp,output/'status.json');last_status=time.monotonic()
            if all(row['child'].poll()is not None and row['proxy'].peer_eof.is_set()for row in actors.values()):break
            time.sleep(.05)
        for slot,row in actors.items():
            proxy=row['proxy']
            require(proxy.sent_complete.is_set()and proxy.sequence>1200 and proxy.handoff
                and proxy.prefix_verified.is_set()and proxy.stop_sent.is_set()and proxy.peer_eof.is_set()
                and proxy.final_ledger is not None,'Original slot full-tail/drain/EOF is incomplete')
            proxy.trace.verify_closed_unchanged()
            life_path=row['private']/'lifecycle.jsonl';lp=h.pin(life_path)
            require(all(lp['identity'][k]==v for k,v in row['lifecycle_identity'].items()),'Original lifecycle identity changed')
            raw=life_path.read_bytes();require(h.pin(life_path)==lp,'Original closed lifecycle changed')
            row['lifecycle']=validate_lifecycle(raw,dict(slot=slot,session=job['sessions'][str(slot)],
                connection=job['connections'][str(slot)]),proxy)
            for name in ('actor-stdout.txt','actor-stderr.txt'):
                text=(row['private']/name).read_text(errors='replace')
                require(not any(marker in text for marker in
                    ('FULL_STARTUP_ADAPTER_FAILURE','COMPILED32_FULL_TAIL_FATAL','Error in Lua')),
                    'Actual MAME/Lua reported a failure despite its exit code')
            row['footer']=proxy.prefix_summary['footer']
        policy_after=policy_reader();require(policy_after==policy_before and actor.compile_report==compile_before,
                                             'Actual common compiled policy/clocks/graphs changed')
        before_stop=server.game_journal.cohort_status(controller.label,controller.start_ts,controller.close_ts)
        certified={row['proxy'].handoff['journal_game_id']for row in actors.values()}
        retirement_partition=slot_closeout.validate(drain,before_stop,actors,
            drain_payload=drain_payload,drain_identifier=drain_identifier)
        require(len(certified)==32 and certified.issubset(set(before_stop['started_ids']))
            and before_stop['complete']is before_stop['valid']is True
            and before_stop['abandoned']==before_stop['pending']==0
            and before_stop['count']==before_stop['started']==64
            and before_stop['slot_admitted_counts']=={str(slot):2 for slot in SLOTS}
            and before_stop['started_actor_slots']==list(SLOTS)
            and drain_payload is not None
            and quota_drain.same_completed_membership(controller.status()['cohort'],before_stop)
            and retirement_partition['complete']is True,'All32 first certificates and every admitted completed game required')
        check_main(require_closed=True)
        h.put(output/'before-intentional-full-tail-origin-stop.json',dict(cohort=before_stop,policy=policy_after,
            compile_report=actor.compile_report,controller=controller.status(),
            drain_identifier=drain_identifier,drain_payload=drain_payload,
            slots={str(slot):dict(footer=row['footer'],handoff=row['proxy'].handoff,
                actual_MAME_exit=row['child'].returncode)for slot,row in actors.items()}))
    except Exception as error:errors.append(repr(error))
    finally:
        for slot,row in actors.items():
            child=row['child']
            if child is not None and child.poll()is None:
                try:
                    require(process_birth(child.pid)==row['birth'],'Changed original birth; no signal')
                    child.terminate()
                except Exception as error:errors.append('Original actor cleanup'+str(slot)+': '+repr(error))
        stop_end=time.monotonic()+10
        while any(row['child']is not None and row['child'].poll()is None for row in actors.values())and time.monotonic()<stop_end:
            time.sleep(.05)
        client_threads=[]
        if server is not None:
            with server.client_lock:client_threads=list(server.clients.values())
            try:server.stop()
            except Exception as error:errors.append('Original server stop: '+repr(error))
        bridge_stop.set()
        for row in actors.values():row['listener'].close()
        join_end=time.monotonic()+20
        owned_threads=[server_worker,*client_threads,*[r['worker']for r in actors.values()if r['worker_started']]]
        for worker in owned_threads:
            if worker is not None:
                worker.join(max(0,join_end-time.monotonic()))
                if worker.is_alive():errors.append('Original thread completion unknown: '+worker.name)
        if main_guard is not None:
            try:
                if not errors:check_main(require_closed=True)
            except Exception as error:errors.append('Original final current-v6 Main observation: '+repr(error))
        health_stop.set()
        if health_worker is not None:health_worker.join(timeout=20)
        if main_guard is not None:
            try:main_guard_report=main_guard.finish(health_worker)
            except Exception as error:
                errors.append('Original current-v6 Main close: '+repr(error))
                main_guard_failure=h.put(output/'original-current-v6-Main-close-failure.json',dict(error=repr(error)))
        owned_threads.append(health_worker)
        all_threads_stopped=all(worker is None or not worker.is_alive()for worker in owned_threads)
        # MAME can finish only after the origin/bridge stop releases an in-flight
        # RPC. Reap again here, before any output is sealed or lease is released.
        try:
            child_reap=await_original_actor_exits(actors)
            if not child_reap['all_original_children_reaped']:
                errors.append('Original child exits still unknown after origin shutdown: '+repr(child_reap['unknown_slots']))
        except Exception as error:errors.append('Original post-origin child wait: '+repr(error))
        if server is not None and controller is not None and controller.start_ts is not None:
            after_stop=server.game_journal.cohort_status(controller.label,controller.start_ts,controller.close_ts)
        if server is not None and server.inference_only_error is not None:errors.append('Actual inference error: '+server.inference_only_error)
        if controller is not None:
            try:controller_exit=controller.exit()
            except Exception as error:errors.append('Original measurement exit: '+repr(error))
        if before_stop is not None and (not quota_drain.same_completed_membership(before_stop,after_stop)or not controller_exit
                or controller_exit.get('valid')is not True):
            errors.append('Original admitted complete cohort changed during intentional teardown')
        if actor is not None:actor.close()
        for stream in streams:
            try:stream.flush();os.fsync(stream.fileno());stream.close()
            except Exception as error:errors.append('Original stream close: '+repr(error))
        for sig,handler in previous.items():signal.signal(sig,handler)
    try:
        for entry in job['inputs']+package_pins:h.checked(entry)
        require(acquisition is None or h.pin(acquisition['path'])==acquisition,'Acquired policy changed')
        source_unchanged=True
    except Exception as error:errors.append('Final input check: '+repr(error))
    actual_slots={}
    for slot,row in actors.items():
        finalized=finalize_actor_outputs(row,bool(child_reap and child_reap['all_original_children_reaped']),
                                         all_threads_stopped,h.pin)
        files=finalized['files']
        child=row['child'];actual_slots[str(slot)]=dict(pid=child.pid if child else None,birth=row['birth'],
            actual_exit=child.poll()if child else None,frames=row['proxy'].sequence,handoff=row['proxy'].handoff,
            footer=row.get('footer'),lifecycle=row.get('lifecycle'),files=files,boot_restore=row['boot_restore'],
            prefix_summary=row['proxy'].prefix_summary,host_stop_receipt=row['proxy'].stop_receipt,
            peer_EOF=row['proxy'].peer_eof.is_set(),final_ledger=row['proxy'].final_ledger,
            lifecycle_identity=row['lifecycle_identity'],trace_identity=row['trace_identity'],
            outputs_sealed_after_original_writer_closure=finalized['outputs_sealed_after_original_writer_closure'],
            original_unsealed_output_paths=finalized['original_unsealed_output_paths'])
        if child is not None and child.poll()is None:errors.append('Original actor completion unknown: '+str(slot))
    journal={};unsealed_journal=[]
    for name in ('games.jsonl','lives.jsonl','measurement_starts.jsonl'):
        path=output/'journal'/name
        if path.is_file():
            if all_threads_stopped and child_reap and child_reap['all_original_children_reaped']:
                path.chmod(0o444);journal[name]=h.pin(path)
            else:unsealed_journal.append(str(path))
    released=False
    if lease.fd is not None:
        try:
            require(all(row['child']is None or row['child'].poll()is not None for row in actors.values())
                and all(worker is None or not worker.is_alive()for worker in owned_threads)
                and(main_guard is None or main_guard.child is None or main_guard.scope_complete),
                'Unknown owned actor/thread completion; preserve original lease')
            lease.release();released=True
        except Exception as error:errors.append('Original private lease cleanup: '+repr(error))
    complete=bool(not errors and len(actual_slots)==32 and policy_before==policy_after
                  and policy_after is not None and source_unchanged and released and main_guard_report is not None and main_initial_readiness is not None and main_guard.scope_complete and main_guard.lifecycle is not None)
    result=h.put(output/'result.json',dict(schema='robotron-compiled-quota64-ENGINEERING-original-result-v1',
        status='PASS_ENGINEERING_ONLY_ALL64_NATURAL_GAMES_AND_SLOT_RETIREMENT'if complete else 'ORIGINAL_ENGINEERING_INVALID_NO_RETRY',
        complete=complete,errors=errors,original_job=jp,original_attempt=1,no_retry=True,original_slots=actual_slots,
        quality_leg=job['quality_leg'],quality_pair_precommit=job['quality_pair_precommit'],
        expected_policy_clocks=job['expected_policy_clocks'],minimum_completed_games=50,
        expected_selected_games=64,quota64_source_pins=job['quota64_source_pins'],
        cohort_selection=None if policy_before is None else policy_before['cohort_selection'],
        policy_before=policy_before,policy_after=policy_after,acquired_checkpoint=acquisition,compile_report=compile_before,
        before_intentional_stop=before_stop,after_intentional_stop=after_stop,controller_exit=controller_exit,
        drain_identifier=drain_identifier,drain_payload=drain_payload,
        slot_retirement_closeout=retirement_partition,
        private_parked_origin_timeout_s=job['private_parked_origin_timeout_s'],
        private_client_idle_timeout_s=job['private_client_idle_timeout_s'],
        private_score_stall_timeout_s=job['private_score_stall_timeout_s'],
        private_lua_score_stall_timeout_s=job['private_lua_score_stall_timeout_s'],
        journal=journal,main_samples=main_samples,main_observation_failures=main_failures,
        main_health_report=main_guard_report,main_health_failure=main_guard_failure,initial_main_readiness=main_initial_readiness,
        main_health_protocol=None,source_family_manifest=job['source_family_manifest'],
        current_main=job['current_main'],current_fleet=job['current_fleet'],
        current_v6_health_source=job['current_v6_health_source'],
        current_v6_health_qualification=job['current_v6_health_qualification'],
        main_observer_lifecycle=None if main_guard is None else main_guard.lifecycle,
        native_started_monotonic_s=started,native_deadline_monotonic_s=deadline,
        original_unsealed_journal_paths=unsealed_journal,
        original_post_origin_child_reap=child_reap,all_original_threads_stopped=all_threads_stopped,
        lease=lease_entry,original_lease_released=released,
        socket_wait_library=library_entry,immutable_inputs_unchanged=source_unchanged,
        engineering_only=True,quality_qualified=False,full_game_score_verified=False,learning_speed_gain_verified=False,
        main_runtime_changed=False,promotion_gates_changed=False,startup_protocol_changed_from_legacy=True,
        limitations='Single original quota64 quality leg: first two known starts per each32 slot,21540s outer horizon/21600s timeout-from-enter, minimum50 floor and all64 full games required. Raw startup prefix1200 is not a game cutoff. Independent original per-leg runtime/game/life review and fixed fresh R1+R2 versus separate C1/C2 campaign gates remain required. Native status alone does not qualify or promote a policy.'))
    print(json.dumps(dict(result=result,complete=complete)),flush=True)
    return 0 if complete else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job')
    parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY: no policy load, GPU, emulator, socket or outputs');return 0
    h=helpers();require(args.job and args.job_sha256 and args.source_sha256,'Explicit original bindings required')
    require(h.pin(__file__)['sha256']==args.source_sha256,'Actual compiled32 source differs')
    jp=h.pin(args.job);require(jp['sha256']==args.job_sha256 and jp['identity']['mode']=='0o444','Actual original job differs')
    return run(json.loads(Path(args.job).read_bytes()),jp,h)


if __name__=='__main__':sys.exit(main())
