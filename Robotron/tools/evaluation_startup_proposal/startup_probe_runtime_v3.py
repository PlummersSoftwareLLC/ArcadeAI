"""Private startup diagnostic adapter library; no executable launch entry point.

A future authenticated owned-unit launcher must supply the original closed
predecessor and live external-guard permit. This module never qualifies policy.
"""
import fcntl
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys
import threading
import time

GAME=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
GPU='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
PACKAGE_SHA='f23e8b4e172da247b7755ec84a82c2ab3ee5a4ef82f3fac8f188462ffb394fdf'
EXPECTED={
    'reader':'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071',
    'core':'6c0334d7a90216b080d3ed59cdf09f96b102aa56c7a3014fc255799e76cd5276',
    'closure':'2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445',
    'main_guard':'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3',
    'raw_api':'9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0',
    'tap_join':'4afdc6e0eb9f431bb6f2223524f446fbdbf127972461987ce71662c36641aaaf',
    'raw_matcher':'77992b95bac8da672e3b24e1f1cf2d7ea2a65943ee0785597d3c96867c072a37',
}
SLOTS=tuple(range(4096,4112))
FRAMES=4096
ROM_INPUTS={
    'ROM3':('2084_rom_3b_3005-15.a4','f9a8f0054d1855adaee37e33c9f14491be24e6f1898bd558444aa8d53c8ce37b'),
    'ROM10':('2084_rom_10b_3005-22.a7','2346893d291a2f070e27048209f87b514c44e445eee7d02e6cf71dd9c5680069'),
}


def require(value,message):
    if not value:raise ValueError(message)


def process_start(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def fd_identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,mode=oct(stat.S_IMODE(info.st_mode)),
        uid=info.st_uid,nlink=info.st_nlink)


def checked_job(job):
    keys={'schema','output','package','checkpoint','predecessor','main','binary_inputs',
          'boot_assets','boot_identity','sessions','affinity','lease','external_guard_permit_path','sources'}
    require(isinstance(job,dict) and set(job)==keys
        and job['schema']=='robotron-private-startup-runtime-job-v2','Exact private runtime job required')
    output=Path(job['output'])
    require(output.is_absolute() and output==output.resolve() and not output.exists()
        and output.parent.is_dir() and output.parent==GAME/'logs/managed-learning-20261015/run-26',
        'Fresh owned run-26 diagnostic output required')
    require(job['package']['sha256']==PACKAGE_SHA,'Exact126-source diagnostic package required')
    require(set(job['sources'])==set(EXPECTED)|{'runtime'}
        and all(job['sources'][k]['sha256']==v for k,v in EXPECTED.items()),'Exact diagnostic source helpers required')
    require(Path(job['sources']['runtime']['path'])==Path(__file__).resolve(),'Actual runtime source must be bound')
    tap_source=Path(job['sources']['tap_join']['path'])
    require(tap_source.name=='reconcile_acceptance_tap_v1.py'
        and Path(job['sources']['raw_matcher']['path'])==tap_source.parent/'startup_server_prefix_v1.py',
        'Exact adjacent independent tap/raw matcher source paths required')
    require(isinstance(job['sessions'],dict) and set(job['sessions'])=={str(x) for x in SLOTS}
        and len(set(job['sessions'].values()))==16
        and all(isinstance(v,str) and re.fullmatch('[0-9a-f]{32}',v) for v in job['sessions'].values()),
        'Exactly16 distinct bound actor sessions required')
    mask=job['affinity']
    require(isinstance(mask,list) and mask and all(type(x) is int and x>=0 for x in mask)
        and mask==sorted(set(mask)),'Explicit private inherited affinity required')
    require(job['boot_assets']==str(GAME/'logs/managed-learning-20261015/sidecar-boot-assets-v1'),
        'Exact initialized boot snapshot required')
    require(isinstance(job['boot_identity'],str) and re.fullmatch('[0-9a-f]{64}',job['boot_identity']),
        'Boot snapshot identity required')
    require(isinstance(job['binary_inputs'],list) and job['binary_inputs']
        and any(e.get('path')=='/usr/games/mame' for e in job['binary_inputs'])
        and any(Path(e['path']).is_relative_to(GAME/'roms') for e in job['binary_inputs']),
        'Bound MAME/ROM/boot binary inventory required')
    require(len(job['binary_inputs'])<=1024
        and len({e['path'] for e in job['binary_inputs']})==len(job['binary_inputs']),
        'Unique bounded binary inventory required')
    for filename,sha in ROM_INPUTS.values():
        entries=[e for e in job['binary_inputs'] if e['path']==str(GAME/'roms/robotron'/filename)]
        require(len(entries)==1 and entries[0].get('sha256')==sha and entries[0].get('bytes')==4096,
                'Exact ROM startup chip input required')
    require(job['lease']['path']=='/dev/shm/robotron-snapshot-smoke-gpu0.lock'
        and set(job['lease'])=={'path','device','inode'}
        and all(type(job['lease'][k]) is int and job['lease'][k]>0 for k in ('device','inode')),
        'Canonical private GPU lease binding required')
    permit=Path(job['external_guard_permit_path'])
    require(permit.is_absolute() and permit==permit.resolve() and permit.parent.is_dir()
        and permit.is_relative_to(GAME/'logs/managed-learning-20261015/run-26')
        and not permit.is_relative_to(output),'Exact future external permit path required')
    return output


class System:
    """Real capabilities are invoked only by explicit adapter lifecycle methods."""
    def __init__(self):
        self.lease_fd=None
        self.modules={}
        self.last_health=None
        self.main_hash_stats={}

    def authenticate(self,runtime):
        job=runtime.job;checked_job(job)
        reader_path=Path(job['sources']['reader']['path'])
        require(hashlib.sha256(reader_path.read_bytes()).hexdigest()==EXPECTED['reader'],'Evidence reader changed')
        spec=importlib.util.spec_from_file_location('_startup_runtime_reader_'+str(time.time_ns()),reader_path)
        self.reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.reader)
        r=self.reader
        require(runtime.job_entry is not None and r.read_pin(runtime.job_entry)==job,'Immutable original runtime job differs')
        for name,entry in job['sources'].items():r.read_pin(entry,as_json=False)
        for name in ('core','closure','main_guard','raw_api','tap_join'):
            self.modules[name]=r.checked_module('_startup_runtime_'+name+'_'+str(time.time_ns()),job['sources'][name])
        runtime.tap_join=self.modules['tap_join']
        self.predecessor=self.modules['core'].verify_closed_predecessor(job['predecessor'],
            read=lambda p,j:r.read_pin(p,as_json=j),archive=self.modules['closure'].archived_closure,
            process_start=process_start,unit_fields=self.unit_fields,
            cgroup_exists=lambda group:Path('/sys/fs/cgroup'+group).exists())
        permit_path=Path(job['external_guard_permit_path'])
        require(permit_path.parent==Path(runtime.job_entry['path']).parent,'Permit must belong to original job directory')
        deadline=time.monotonic()+15
        while not permit_path.exists():
            require(time.monotonic()<deadline,'Original guard permit observation deadline expired')
            time.sleep(0.05)
        self.guard_permit_entry=r.pin(permit_path)
        permit=r.read_pin(self.guard_permit_entry)
        require(permit.get('schema')=='robotron-original-startup-guard-live-binding-v1'
            and permit.get('job_sha256')==runtime.job_entry['sha256']
            and permit.get('authorized_original_attempt')==1,'Original external guard permit missing')
        owner=permit.get('probe_owner',{})
        require(owner.get('pid')==os.getpid() and owner.get('starttime_ticks')==process_start(os.getpid())
            and owner.get('cgroup')==self.cgroup(os.getpid())
            and owner.get('invocation_id')==os.environ.get('INVOCATION_ID')
            and isinstance(owner.get('invocation_id'),str)
            and re.fullmatch('[0-9a-f]{32}',owner['invocation_id']), 'External guard does not own this original probe')
        guard=permit.get('guard_owner',{})
        require(type(guard.get('pid')) is int and guard['pid']!=os.getpid()
            and process_start(guard['pid'])==guard.get('starttime_ticks'),'Original external guard is not live')
        require(self.cgroup(guard['pid'])==guard.get('cgroup'),'External guard cgroup differs')
        live_guard=self.unit_fields(guard['unit'])
        require(live_guard.get('MainPID')==str(guard['pid'])
            and live_guard.get('InvocationID')==guard.get('invocation_id')
            and live_guard.get('NRestarts')=='0','Original external guard unit differs')
        self.guard_owner=guard;self.probe_owner=owner
        require(sorted(os.sched_getaffinity(os.getpid()))==job['affinity'],'Original private inherited affinity differs')
        self.package=r.read_pin(job['package']);self.root=Path(self.package['root'])
        require(self.package['source_count']==len(self.package['files'])==len(self.package['file_pins'])==126,
            'Private package inventory differs')
        self.verify_inputs(runtime)
        self.main=r.read_pin(job['main'])
        require(len(self.main['actors'])==192 and {x['slot'] for x in self.main['actors']}==set(range(192)),
            'Fresh exact main192 actor binding required')
        self.modules['main_guard'].owner_and_files(self.main)
        self.main_hash_stats={p:self.stat_key(Path(p).stat()) for p in self.main['held_hashes']}
        baseline_raw=r.read_pin(self.main['baseline_API'],as_json=False)
        self.baseline=self.modules['raw_api'].parse_wire(baseline_raw)
        self.previous=self.baseline
        self.health(runtime,force=True)

    def unit_fields(self,unit):
        result=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=10)
        require(result.returncode==0,'Original unit query failed')
        return dict(row.split('=',1) for row in result.stdout.splitlines() if '=' in row)

    def cgroup(self,pid):
        lines=Path('/proc',str(pid),'cgroup').read_text().splitlines()
        require(len(lines)==1 and lines[0].startswith('0::/user.slice/'),'Expected owned unified user cgroup')
        return lines[0].split('::',1)[1]

    def stat_key(self,info):return tuple(fd_identity(info).values())

    def verify_inputs(self,runtime):
        r=self.reader;job=runtime.job
        for entry in self.package['file_pins'].values():r.read_pin(entry,as_json=False)
        for entry in job['sources'].values():r.read_pin(entry,as_json=False)
        require(r.pin(job['checkpoint']['path'])==job['checkpoint']
            and job['checkpoint']['identity']['mode']=='0o444'
            and job['checkpoint']['identity']['uid']==os.getuid()
            and job['checkpoint']['identity']['nlink']==1
            and Path(job['checkpoint']['path']).is_relative_to(GAME/'models_dqn/managed-incumbents'),
            'Original protected checkpoint changed')
        for entry in job['binary_inputs']:require(r.pin(entry['path'])==entry,'Bound binary/ROM/boot input changed')
        roms=GAME/'roms';found=set();directories=0
        for directory,subdirs,names in os.walk(roms,followlinks=False):
            directories+=1;require(directories<=128 and len(found)<=512,'ROM inventory exceeds explicit bound')
            require(not Path(directory).is_symlink() and all(not (Path(directory)/n).is_symlink()
                for n in subdirs),'ROM directory symlink is not bound')
            for name in names:
                path=Path(directory)/name
                require(path.is_file() and not path.is_symlink(),'Unexpected ROM inventory entry')
                found.add(str(path))
        expected={e['path'] for e in job['binary_inputs'] if Path(e['path']).is_relative_to(roms)}
        require(found and found==expected,'Complete original ROM file inventory differs')

    def acquire(self,runtime):
        job=runtime.job;path=Path(job['lease']['path']);before=path.lstat()
        require(path.resolve(strict=True)==path and stat.S_ISREG(before.st_mode)
            and before.st_uid==os.getuid() and before.st_nlink==1
            and dict(device=before.st_dev,inode=before.st_ino)=={k:job['lease'][k] for k in ('device','inode')},
            'Private GPU lease identity differs')
        self.lease_fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        after=os.fstat(self.lease_fd)
        require((after.st_dev,after.st_ino)==(before.st_dev,before.st_ino),'Lease changed during open')
        fcntl.flock(self.lease_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            probe.bind(('127.0.0.1',9999))
        value=subprocess.run(['nvidia-smi','--id='+GPU,'--query-compute-apps=pid',
            '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
        require(value.returncode==0 and not value.stdout.strip(),'Private GPU0 is not idle')

    def binary_bytes(self,runtime,filename,expected_sha):
        path=GAME/'roms/robotron'/filename
        entries=[e for e in runtime.job['binary_inputs'] if e['path']==str(path)]
        require(len(entries)==1 and entries[0]['sha256']==expected_sha and entries[0]['bytes']==4096,
                'Bound ROM chip declaration differs')
        entry=entries[0]
        require(self.reader.pin(path)==entry,'Bound ROM chip changed')
        with path.open('rb') as stream:raw=stream.read(4097)
        require(len(raw)==4096 and hashlib.sha256(raw).hexdigest()==expected_sha
            and self.reader.pin(path)==entry,'Bound ROM chip changed while reading')
        return raw,entry

    def bootstrap(self,runtime):
        r=self.reader;job=runtime.job;root=self.root
        require(not any(n=='torch' or n=='config' or n.startswith('dqn.')
            or n=='startup_server_prefix_v1' for n in sys.modules),'Fresh private interpreter required')
        sys.path.insert(0,str(root/'tools'))
        frozen=r.checked_module('_startup_private_frozen_'+str(time.time_ns()),
                                self.package['file_pins']['tools/run_frozen_sidecar.py'])
        require(frozen.GAME==root,'Private runner module root differs')
        runtime.frozen=frozen
        selected=frozen.Job(Path(job['checkpoint']['path']),runtime.output,'startup-tap-prefix-original01',
            'cuda',GPU,9999,240,300,1000,Path('/usr/games/mame'),GAME/'roms',2,
            Path(job['boot_assets']),'inductor',True,'confirmed_reset_reserves_v1',16)
        selected.validate(require_boot_assets=True)
        runtime.output.mkdir(mode=0o700);runtime.owns_output=True
        runtime.publish_value('original-job.json',job)
        runtime.selected=selected
        runtime.boot=frozen.boot_module().load_snapshot(selected.boot_assets)
        require(runtime.boot['identity']==job['boot_identity'],'Original initialized boot identity differs')
        frozen.configure_environment(selected)
        runtime.checkpoint,runtime.checkpoint_sha=frozen.copy_checkpoint(selected)
        require(runtime.checkpoint_sha==job['checkpoint']['sha256'],'Copied checkpoint differs')
        runtime.checkpoint_signature=frozen.checkpoint_identity(runtime.checkpoint)
        sys.path.insert(0,str(root/'Scripts'))
        torch=importlib.import_module('torch')
        config=importlib.import_module('dqn.config')
        actor_module=importlib.import_module('dqn.inference_actor')
        server_module=importlib.import_module('dqn.socket_server')
        measurement=importlib.import_module('dqn.managed_measurement')
        trace=importlib.import_module('startup_server_prefix_v1')
        for module,name in ((config,'Scripts/dqn/config.py'),(actor_module,'Scripts/dqn/inference_actor.py'),
            (server_module,'Scripts/dqn/socket_server.py'),(measurement,'Scripts/dqn/managed_measurement.py'),
            (trace,'Scripts/startup_server_prefix_v1.py')):
            require(Path(module.__file__).resolve()==root/name,'Imported private module origin differs')
            r.read_pin(self.package['file_pins'][name],as_json=False)
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        config.RL_CONFIG.inference_batch_max_size=16
        runtime.actor=frozen.build_inference_actor(actor_module.InferenceActor,runtime.checkpoint,selected)
        metadata=runtime.actor.checkpoint_metadata
        for name in ('learner_frame_count','frame_count','measurement_frame_count'):
            setattr(config.metrics,name,int(metadata[name]))
        config.metrics.total_training_steps=runtime.actor.training_steps
        config.metrics.total_optimized_samples=runtime.actor.optimized_samples
        config.metrics.training_enabled=False;config.metrics.preview_capture_enabled=False;config.metrics.hud_enabled=False
        for name,value in dict(start_advanced=False,start_level_min=1,epsilon_pct=0,
                expert_pct=0,auto_curriculum=False,difficulty=5).items():setattr(config.game_settings,name,value)
        library=importlib.import_module('build_socket_wait').build(runtime.output/'socket-wait-build')
        runtime.config=config;runtime.trace=trace
        runtime.server=server_module.SocketServer('127.0.0.1',9999,runtime.actor,replay_enabled=False)
        require(runtime.server.async_buffer is None and runtime.server.inference_batcher is not None
            and runtime.server.inference_batcher.max_batch_size==16,'Private replay/batch isolation differs')
        runtime.controller=measurement.ManagedMeasurement(runtime.actor,config.metrics,runtime.server.game_journal,
            boundary_status=lambda generation:frozen.fixed_boundary(runtime.server,generation,SLOTS))
        runtime.original_spec=frozen.mame_spec
        frozen.mame_spec=runtime.mame_spec
        runtime.fleet=frozen.PrivateFleet(selected,library,popen=runtime.popen,
            expected_boot_identity=runtime.boot['identity'])
        runtime.worker=threading.Thread(target=runtime.server.start,name='private-startup-prefix-server',daemon=True)

    def health(self,runtime,force=False):
        now=time.monotonic()
        if not force and self.last_health is not None and now-self.last_health<5:return
        self.last_health=now
        require(process_start(self.main['owner']['pid'])==self.main['owner']['starttime_ticks'],'Main trainer changed')
        for actor in self.main['actors']:
            require(process_start(actor['pid'])==actor['starttime_ticks']
                and sorted(os.sched_getaffinity(actor['pid']))==actor['mask'],'Main actor birth/affinity changed')
        for path,key in self.main_hash_stats.items():require(self.stat_key(Path(path).stat())==key,'Held main input changed')
        import urllib.request
        wire=self.modules['raw_api']
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:
            raw=response.read(wire.MAX_WIRE_BYTES+1)
        api=wire.parse_wire(raw)
        self.modules['main_guard'].healthy(api,self.baseline,self.main['experiment'],time.time())
        require(all(type(api[k]) is int and api[k]>=self.previous[k] for k in
            ('frame_count','learner_frame_count','optimized_samples','training_steps')),'Main work clocks regressed')
        self.modules['closure'].inspect_optimizer_observation(api['host_pipeline']['learning_exposure']['optimizer'])
        for kind in ('optimizer','replay'):
            current=api['host_pipeline']['learning_exposure'][kind]
            baseline=self.baseline['host_pipeline']['learning_exposure'][kind]
            require(all(type(current[k]) is int and current[k]==baseline[k]
                for k in ('process_id','instance_monotonic_ns','epoch'))
                and current['process_id']==self.main['owner']['pid'],'Main optimizer/replay identity changed')
        for key in ('epsilon','expert_ratio','lr'):
            require(type(api[key]) in (int,float) and math.isfinite(api[key])
                and math.isclose(api[key],self.baseline[key],rel_tol=0,abs_tol=1e-12),'Main behavior recipe changed')
        age=time.time()-(GAME/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime
        require(0<=age<=360,'Main checkpoint freshness failed')
        self.previous=api
        if runtime.owns_output:
            runtime.publish_bytes('main-API-'+str(time.time_ns())+'.bin',raw)

    def spawn(self,runtime,argv,kwargs):
        process=subprocess.Popen(argv,**kwargs)
        # Register the owned Popen handle before any birth inspection can fail.
        runtime.owned_handles.append(process)
        slot=int(kwargs['env']['ROBOTRON_CLIENT_SLOT'])
        require(slot in runtime.actor_outputs,'Original actor output binding missing')
        outputs=runtime.actor_outputs[slot]
        require(Path(kwargs['cwd'])==Path(outputs['directory'])
            and kwargs['env'].get('ROBOTRON_STARTUP_ACCEPTANCE_PATH')==outputs['tap']
            and kwargs['env'].get('ROBOTRON_STARTUP_DIAGNOSTIC_PATH')==outputs['lua']
            and kwargs['env'].get('ROBOTRON_STARTUP_DIAGNOSTIC_SESSION')==outputs['session'],
            'Original actor output/session environment differs')
        birth=process_start(process.pid)
        require(birth is not None and process.poll() is None,'Original actor live birth missed')
        raw=Path('/proc',str(process.pid),'stat').read_text().rsplit(')',1)[1].split()
        require(int(raw[1])==os.getpid() and process_start(process.pid)==birth,'Actor parent/birth differs')
        require(self.cgroup(process.pid)==self.probe_owner['cgroup'],'Actor escaped owned probe cgroup')
        require(sorted(os.sched_getaffinity(process.pid))==runtime.job['affinity'],'Private actor affinity differs')
        require(Path('/proc',str(process.pid),'exe').resolve()==Path('/usr/games/mame').resolve(),
            'Original actor executable differs')
        require(Path('/proc',str(process.pid),'cmdline').read_bytes().split(b'\0')[:-1]
            ==[os.fsencode(x) for x in argv],'Original actor argv differs')
        runtime.births[slot]=dict(pid=process.pid,starttime_ticks=birth,parent_pid=os.getpid(),
            cgroup=self.probe_owner['cgroup'],mask=runtime.job['affinity'],argv=argv,
            session=runtime.job['sessions'][str(slot)],private_directory=kwargs['cwd'].as_posix(),
            outputs=outputs)
        runtime.publish_value('actor-'+str(slot)+'-original-birth.json',runtime.births[slot])
        return process

    def check(self,runtime):
        require(process_start(self.guard_owner['pid'])==self.guard_owner['starttime_ticks'],'Original external guard departed')
        runtime.frozen.check_protocol(runtime.config,runtime.actor,runtime.checkpoint_signature,runtime.checkpoint)
        require(runtime.worker.is_alive() and runtime.server.running and not runtime.server.inference_only_error,
            'Private server/inference failed')
        require(len(runtime.births)==16 and not runtime.fleet.exited(),'Owned private actor exited')
        for birth in runtime.births.values():
            require(process_start(birth['pid'])==birth['starttime_ticks']
                and sorted(os.sched_getaffinity(birth['pid']))==birth['mask'],'Private actor identity changed')
        before=runtime.snapshot()
        stamp_before=time.time();state=runtime.controller.tick();stamp_after=time.time()
        after=runtime.snapshot()
        require(state.get('valid') is not False,'Private frozen controller failed')
        if state['phase']!='warming':
            require(runtime.frozen.fixed_boundary(runtime.server,runtime.controller.generation,SLOTS)['ready'],
                    'Original private boundary changed')
        runtime.publish_value('boundary-'+str(time.time_ns())+'.json',dict(before_unix_s=stamp_before,
            after_unix_s=stamp_after,phase=state['phase'],admission_start=state.get('start_ts'),
            admission_close=state.get('close_ts'),before=before,after=after,
            scope='Separate snapshots bracket controller.tick; no atomic simultaneity claimed.'))
        self.health(runtime)

    def audit(self,runtime):
        require(runtime.owns_output and runtime.boot is not None,'Runtime setup did not complete')
        self.verify_inputs(runtime)
        self.modules['main_guard'].owner_and_files(self.main)
        self.health(runtime,force=True)
        require(runtime.frozen.boot_module().load_snapshot(runtime.selected.boot_assets)['identity']
            ==runtime.boot['identity'],'Boot inputs changed')
        require(all(process_start(x['pid'])!=x['starttime_ticks'] for x in runtime.births.values())
            and all(p.poll() is not None for p in runtime.owned_handles),'An owned private actor remains')
        require(len(runtime.births)==16,'Original actor birth coverage incomplete')
        backend=runtime.fleet.backend_evidence()
        require(len(backend)==16 and all(x['matching_activation'] for x in backend.values()),'Original socket-wait backend missing')
        timeouts=runtime.timeouts or {}
        counters=timeouts.get('actor_timeout_logs',{})
        require(set(map(int,counters))==set(SLOTS),'Runtime timeout coverage missing')
        count=sum(counters.values())
        return dict(valid=count==0,all_owned_actors_absent=True,sources_unchanged=True,
            checkpoint_unchanged=runtime.frozen.checkpoint_identity(runtime.checkpoint)==runtime.checkpoint_signature,
            main_healthy=True,runtime_timeouts=count,backend=backend,timeout_evidence=timeouts,
            main_coverage_scope='Child observations only; whole owned-unit coverage still requires the external guard.')

    def release(self):
        errors=[]
        if self.lease_fd is not None:
            descriptor=self.lease_fd;self.lease_fd=None
            try:os.close(descriptor)
            except OSError as error:errors.append(str(error))
        return errors


class Runtime:
    def __init__(self,job,job_entry=None,*,system=None):
        # This constructor performs no reads, allocation of runtime resources or process discovery.
        self.job=job;self.job_entry=job_entry;self.system=system if system is not None else System()
        self.output=Path(job['output']);self.owns_output=False
        self.frozen=self.selected=self.boot=self.actor=self.config=self.trace=None
        self.server=self.controller=self.fleet=self.worker=self.recorder=self.capture_context=None
        self.original_spec=None;self.stream=None;self.timeouts=None
        self.births={};self.owned_handles=[];self.cleanup_done=False
        self.tap_join=None;self.actor_outputs={};self.tap_observations={}
        self.prior_handlers={};self.stop_event=threading.Event()

    def publish_bytes(self,name,raw):
        require(self.owns_output and Path(name).name==name,'Owned flat artifact name required')
        path=self.output/name
        with path.open('xb') as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        return self.system.reader.pin(path)

    def publish_value(self,name,value):
        return self.publish_bytes(name,(json.dumps(value,indent=2,allow_nan=False)+'\n').encode())

    def prepare(self):
        self.system.authenticate(self)
        for number in (signal.SIGTERM,signal.SIGINT):
            self.prior_handlers[number]=signal.signal(number,lambda *_:self.stop_event.set())
        self.system.acquire(self)
        self.system.bootstrap(self)
        require(not self.stop_event.is_set(),'Original private setup interrupted')

    def mame_spec(self,job,slot,library=None):
        require(job is self.selected and slot in SLOTS,'Only this original private job is allowed')
        require(self.owns_output and self.output.is_dir() and slot not in self.actor_outputs,
                'Original owned output and one actor specification required')
        argv,environment,private=self.original_spec(job,slot,library)
        require(private==self.output/'actors'/str(slot),'Private actor output differs')
        actors=self.output/'actors'
        actors.mkdir(mode=0o700,exist_ok=True)
        require(actors==actors.resolve(strict=True) and actors.stat().st_uid==os.getuid()
            and stat.S_IMODE(actors.stat().st_mode)==0o700,'Exact owned private actor parent required')
        require(not private.exists() and not private.is_symlink(),'Fresh actor directory required')
        private.mkdir(mode=0o700)
        trace=private/'startup-prefix.jsonl'
        tap=private/'startup-acceptance.jsonl'
        console=private/'console.log'
        require(all(not path.exists() and not path.is_symlink() for path in (trace,tap,console)),
                'Original actor output already exists')
        self.actor_outputs[slot]=dict(directory=str(private),lua=str(trace),tap=str(tap),console=str(console),
            session=self.job['sessions'][str(slot)],directory_identity=fd_identity(private.stat()))
        self.publish_value('actor-'+str(slot)+'-original-output-context.json',self.actor_outputs[slot])
        environment=dict(environment)
        environment.update(ROBOTRON_STARTUP_DIAGNOSTIC_PATH=str(trace),
            ROBOTRON_STARTUP_ACCEPTANCE_PATH=str(tap),
            ROBOTRON_STARTUP_DIAGNOSTIC_SESSION=self.job['sessions'][str(slot)],
            ROBOTRON_STARTUP_DIAGNOSTIC_LIMIT=str(FRAMES))
        return argv,environment,private

    def popen(self,argv,**kwargs):
        return self.system.spawn(self,argv,kwargs)

    def start(self):
        require(not self.stop_event.is_set(),'Original private startup interrupted')
        self.controller.enter(self.selected.label,cohort_s=240,timeout_s=300)
        self.stream=(self.output/'server-prefix.jsonl').open('xb')
        def write(line):
            self.stream.write(line.encode());self.stream.flush();return True
        self.recorder=self.trace.Recorder({int(k):v for k,v in self.job['sessions'].items()},write,limit=FRAMES)
        self.capture_context=self.trace.capture(self.recorder,self.server)
        self.capture_context.__enter__()
        self.worker.start()
        deadline=time.monotonic()+15
        while not self.server.running:
            require(self.worker.is_alive() and time.monotonic()<deadline and not self.stop_event.is_set(),
                    'Private listener failed/interrupted before launch')
            time.sleep(0.02)
        self.fleet.launch()

    def check(self):
        require(not self.stop_event.is_set(),'Original private probe interrupted')
        self.system.check(self)

    def snapshot(self):
        require(self.recorder is not None,'Capture has not started')
        with self.recorder.lock:
            result=dict(closed=self.recorder.closed,failed=self.recorder.failed,faults=self.recorder.faults,
                rows=self.recorder.rows,counts=dict(self.recorder.counts),epochs=dict(self.recorder.epochs),
                pending=sum(c['pending'] is not None for c in self.recorder.clients.values()))
        # Only the short recorder copy above owns its lock. Disk reads and
        # controller callbacks never run under the server's recorder lock.
        if result['closed'] and not result['failed'] and result['faults']==0:
            require(set(result['counts'])==set(SLOTS)
                and all(n==FRAMES for n in result['counts'].values()),'Raw capture closed before full coverage')
            require(set(self.actor_outputs)==set(SLOTS),'All original actor outputs must be bound')
            # Do not short-circuit: inspect every declared actor on each pass.
            tails=[self.tap_tail(slot) for slot in SLOTS]
            result['closed']=all(tails)
        return result

    def tap_tail(self,slot):
        """Bounded live footer witness; the full post-cleanup join is separate."""
        require(self.owns_output and slot in self.actor_outputs,'Owned original tap context required')
        outputs=self.actor_outputs[slot];private=Path(outputs['directory']);path=Path(outputs['tap'])
        info=private.stat();declared=outputs['directory_identity']
        require(private==private.resolve(strict=True) and stat.S_ISDIR(info.st_mode)
            and stat.S_IMODE(info.st_mode)==0o700 and info.st_uid==os.getuid()
            and info.st_dev==declared['device'] and info.st_ino==declared['inode'],
            'Original private actor directory changed')
        if not path.exists():
            require(not path.is_symlink() and slot not in self.tap_observations,
                    'Original tap disappeared or is a broken link')
            return False
        require(path==path.resolve(strict=True) and path.parent==private,'Exact original tap path required')
        with path.open('rb') as stream:
            before=os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
                and before.st_size<=4620*2048,'Original bounded tap file identity differs')
            stream.seek(max(0,before.st_size-4096));tail=stream.read(4096)
            after=os.fstat(stream.fileno())
        current=path.stat()
        stable=lambda s:tuple(fd_identity(s)[k] for k in ('device','inode','mode','uid','nlink'))
        require(stable(before)==stable(after)==stable(current)
            and current.st_size>=after.st_size>=before.st_size,'Tap identity or append order changed')
        previous=self.tap_observations.get(slot)
        if previous is not None:
            require(previous['stable']==stable(after) and after.st_size>=previous['size'],
                    'Original tap was replaced or truncated')
            if previous['complete']:
                require(previous['identity']==fd_identity(after),'Original completed tap changed')
                return True
        observation=dict(stable=stable(after),size=after.st_size,complete=False)
        self.tap_observations[slot]=observation
        if fd_identity(before)!=fd_identity(after) or not tail or not tail.endswith(b'\n'):
            return False
        line=tail.splitlines()[-1]
        require(len(line)+1<=2048,'Tap tail line exceeds bound')
        def unique(pairs):
            result={}
            for key,value in pairs:
                require(key not in result,'Duplicate tap tail JSON key');result[key]=value
            return result
        def nonfinite(value):raise ValueError('Nonfinite tap tail: '+value)
        row=json.loads(line,object_pairs_hook=unique,parse_constant=nonfinite)
        require(type(row) is dict and row.get('kind') in ('header','installed','input','status_write','footer'),
                'Fault or unknown tap tail')
        require(row.get('schema')=='robotron-ROM-start-tap-v1' and type(row.get('slot')) is int
            and row['slot']==slot and row.get('session')==outputs['session'],'Tap tail session differs')
        if row['kind']!='footer':return False
        require(self.tap_join is not None and set(row)==self.tap_join.COMMON|self.tap_join.KEYS['footer'],
                'Exact tap footer fields required')
        fixed=dict(inputs_observed=FRAMES,faults=0,failed=False,logging_failed=False,last_input_frame=FRAMES-1,
            capacity_reached=True,raw_provenance_only=True,real_ROM_start_acceptance_proven=False,
            start_eligibility_changed=False,reason='capacity')
        require(all(type(row.get(key)) is type(value) and row[key]==value for key,value in fixed.items()),
                'Tap footer incomplete or failed')
        writes=row.get('writes_observed')
        require(type(writes) is int and 0<=writes<=512 and type(row.get('sequence')) is int
            and row['sequence']==FRAMES+writes+3,'Tap footer event/write coverage differs')
        observation.update(complete=True,identity=fd_identity(after))
        return True

    def cleanup(self):
        require(not self.cleanup_done,'Cleanup already attempted')
        self.cleanup_done=True;errors=[]
        # All handles are registered before an inspection can fail, including
        # one whose Popen returned but whose birth validation failed.
        if self.server is not None:self.server.shutdown_event.set()
        if all(x is not None for x in (self.frozen,self.fleet,self.server,self.worker,self.controller)):
            try:
                self.timeouts,extra=self.frozen.cleanup_with_timeout_evidence(
                    self.fleet,self.server,self.worker,self.controller,self.prior_handlers)
                errors.extend(extra)
            except BaseException as error:
                errors.append('Frozen cleanup: '+str(error))
                try:
                    errors.extend(self.frozen.cleanup_job(self.fleet,self.server,self.worker,
                                                         self.controller,self.prior_handlers))
                except BaseException as secondary:errors.append('Fallback frozen cleanup: '+str(secondary))
        else:
            for resource in (self.fleet,self.server):
                if resource is not None:
                    try:errors.extend(resource.stop() or [])
                    except BaseException as error:errors.append('Partial setup cleanup: '+str(error))
        # An exceptional Popen birth inspection may precede fleet.processes
        # assignment. Only these registered original Popen handles are used.
        for process in self.owned_handles:
            try:
                if process.poll() is None:process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=5)
            except BaseException as error:errors.append('Owned child cleanup: '+str(error))
        if self.capture_context is not None:
            try:self.capture_context.__exit__(None,None,None)
            except BaseException as error:errors.append('Capture cleanup: '+str(error))
            self.capture_context=None
        if self.stream is not None:
            try:self.stream.close()
            except BaseException as error:errors.append('Prefix close: '+str(error))
        if self.original_spec is not None:
            try:self.frozen.mame_spec=self.original_spec
            except BaseException as error:errors.append('Private spec restoration: '+str(error))
        for number,handler in self.prior_handlers.items():
            try:signal.signal(number,handler)
            except BaseException as error:errors.append('Signal restoration: '+str(error))
        return errors

    def copy_original(self,path,name,maximum):
        require(self.cleanup_done and self.owns_output,'Original evidence must be copied after cleanup')
        require(path.is_relative_to(self.output) and path==path.resolve(strict=True)
            and stat.S_ISREG(path.lstat().st_mode),
                'Exact owned producer file path required')
        with path.open('rb') as stream:
            before=os.fstat(stream.fileno());raw=stream.read(maximum+1);after=os.fstat(stream.fileno())
        require(fd_identity(before)==fd_identity(after)
            and fd_identity(path.stat())==fd_identity(after)
            and before.st_uid==os.getuid() and before.st_nlink==1 and stat.S_ISREG(before.st_mode),
            'Original producer prefix identity changed')
        if len(raw)>maximum or before.st_size>maximum:
            retained=self.publish_bytes(name+'.oversize-prefix.bin',raw[:maximum])
            self.publish_value(name+'.oversize-original-identity.json',dict(path=str(path),
                identity=fd_identity(after),retained_prefix=retained,maximum_bytes=maximum,
                complete=False,truncated=True,source_full_sha256=None,
                scope='Bounded exact original prefix only; oversized producer remains invalid and unchanged.'))
            raise ValueError('Original producer exceeds bound; exact capped prefix retained: '+retained['path'])
        entry=self.publish_bytes(name,raw)
        self.publish_value(name+'.original-identity.json',dict(path=str(path),identity=fd_identity(after),
            sha256=hashlib.sha256(raw).hexdigest(),scope='Exact original bytes retained; producer mode unchanged.'))
        return raw,entry

    def collect(self):
        require(self.owns_output,'No original output was created')
        retained={};errors=[];server=None;lua={};taps={};consoles={};rom={}
        try:
            server,retained['server']=self.copy_original(self.output/'server-prefix.jsonl',
                'server-prefix-readonly.jsonl',(16*(FRAMES+16)+4)*2048)
        except Exception as error:errors.append('Server prefix: '+str(error))
        for slot in SLOTS:
            private=self.output/'actors'/str(slot)
            if slot in self.actor_outputs:
                try:
                    info=private.stat();declared=self.actor_outputs[slot]['directory_identity']
                    require(private==private.resolve(strict=True) and stat.S_IMODE(info.st_mode)==0o700
                        and info.st_uid==os.getuid() and info.st_dev==declared['device']
                        and info.st_ino==declared['inode'],'Original actor directory changed before collection')
                except Exception as error:errors.append('Actor '+str(slot)+' context: '+str(error))
            for label,filename,maximum,target in (
                    ('Lua','startup-prefix.jsonl',(FRAMES+32)*2048,lua),
                    ('tap','startup-acceptance.jsonl',4620*2048,taps),
                    ('console','console.log',16*1024*1024,consoles)):
                try:
                    raw,entry=self.copy_original(private/filename,
                        label+'-'+str(slot)+'-prefix-readonly.jsonl',maximum)
                    target[slot]=raw;retained[label+'-'+str(slot)]=entry
                    observed=self.tap_observations.get(slot)
                    if label=='tap' and observed and observed['complete']:
                        require(fd_identity((private/filename).stat())==observed['identity'],
                                'Original completed tap changed before collection')
                except Exception as error:errors.append(label+' '+str(slot)+' prefix: '+str(error))
        for name,(filename,sha) in ROM_INPUTS.items():
            try:
                raw,original=self.system.binary_bytes(self,filename,sha)
                retained[name]=self.publish_bytes('bound-'+name+'-input.bin',raw)
                self.publish_value('bound-'+name+'-input-original.json',original)
                rom[name]=raw
            except Exception as error:errors.append(name+' input: '+str(error))
        if self.trace is None or self.tap_join is None:errors.append('Authenticated capture/checker component missing')
        self.publish_value('original-prefix-capture-inventory.json',dict(retained=retained,errors=errors,
            original_producer_modes_unchanged=True))
        require(not errors and server is not None,'Original prefix inventory incomplete; preserved without retry')
        sessions={int(k):v for k,v in self.job['sessions'].items()}
        result=self.trace.reconcile(lua,server,sessions,limit=FRAMES)
        self.publish_value('original-prefix-reconciliation.json',result)
        checked=self.tap_join.reconcile(lua,server,taps,consoles,sessions,rom['ROM3'],rom['ROM10'],limit=FRAMES)
        require(checked.get('status')=='MATCHED_PASSIVE_TAP_CONTENT_ONLY'
            and checked.get('raw_prefix_reconciliation')==result
            and type(checked.get('actor_slots')) is int and checked['actor_slots']==16
            and type(checked.get('matched_inputs')) is int and checked['matched_inputs']==16*FRAMES,
            'Complete independent tap/raw input join differs')
        require(all(checked.get(key) is False for key in ('original_runtime_outcome_verified',
            'raw_ROM_start_acceptance_proven','start_eligibility_changed','protocol_selected',
            'quality_qualified','learning_speed_gain_verified')),'Content join cannot certify runtime/start/quality')
        self.publish_value('original-passive-tap-content-reconciliation.json',checked)
        return dict(result,tap_provenance=checked)

    def audit(self):return self.system.audit(self)
    def release(self):return self.system.release()
    def publish(self,result):
        if self.owns_output:self.publish_value('result.json',result)
        else:require(result['valid'] is False,'Unowned output cannot carry a valid result')


if __name__=='__main__':
    print('LIBRARY_ONLY: no job reads, process/device queries, runtime setup or launch; an authenticated external launcher is still required')
