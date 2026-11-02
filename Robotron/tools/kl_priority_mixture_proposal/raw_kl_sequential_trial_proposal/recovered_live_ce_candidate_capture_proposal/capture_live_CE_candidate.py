"""One live CE model-only capture; no transition, pause, restart or CPU launch.

Default literal PLAN. Root must pin a real post-quality-release job before execute.
The capture result is pending strict CPU verification, never policy qualification.
"""
import argparse
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import tempfile
import time
import traceback

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME/'logs/managed-learning-20261015/run-26'
Q = GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
CLOCKS = ('training_steps','optimized_samples','learner_frame_count','frame_count')
MAX_JSON = 4 << 20
MAX_MODEL = 512 << 20
SOURCE_NAMES = ('__init__.py','model.py','config.py','learning_control.py','agent.py','training.py','loss_kernel.py','priority_phase.py')
DEPENDENCIES = {
    'resources': (RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py', 'd525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'),
    'snapshot': (Q/'live_one_trial_installed_ce_revision2_proposal/early_insurance.py', '0112da455fd0c3c7b711cda2ff59f8575a637f2544ec37f9ad68ad2698b0dab4'),
    'phase': (GAME/'tools/phase_snapshot_cpu_verifier_proposal/verify_phase_snapshot.py', 'b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519'),
}
SCHEMA = 'robotron-one-live-ce-candidate-capture-job-v1'
RESULT_SCHEMA = 'robotron-one-live-ce-candidate-capture-result-v1'


def require(value, message):
    if not value: raise RuntimeError(message)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def four(value):
    result = {key:value[key] for key in CLOCKS}
    require(all(type(x) is int and x > 0 for x in result.values()), 'Invalid four saved clocks')
    return result


def triple(pin):
    return {key:pin[key] for key in ('path','sha256','bytes')}


def request_identity(value):
    """Immutable request bytes/inode; link/rename alone may change ctime/nlink."""
    return {key:value[key] for key in ('device','inode','bytes','mtime_ns','mode','uid')}


def publish_request(base, model, archive, tag, register):
    """Seal+archive bytes BEFORE a no-overwrite publication; retain opened inode.

    The consumer may rename request->completed before the publisher is scheduled
    again. The historical request PIN therefore describes the owned opened file
    at publication, with its intended path; it is not a claimed later path stat.
    """
    path=model/'managed_save.request.json'
    require(not path.exists(),'Pending request already exists')
    raw=(json.dumps({'tag':tag},sort_keys=True)+'\n').encode()
    fd,name=tempfile.mkstemp(prefix='.managed-phase-request-',dir=model)
    temporary=Path(name);before=None;pending=None;primary=None
    try:
        pending=dict(tag=tag,pin=None,archive=None,publication=dict(
            identity_scope='Owned FD before no-overwrite publication; path may immediately move to completed',
            temporary_path=str(temporary),created=base.identity(os.fstat(fd)),published=False))
        register(pending)  # Partial preparation is owned evidence too.
        with os.fdopen(fd,'w+b',closefd=False) as stream:
            stream.write(raw);stream.flush();os.fsync(fd);os.fchmod(fd,0o444)
        before=base.identity(os.fstat(fd))
        _,archived=base.exclusive_copy(temporary,archive)
        historical=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)
        pending.update(pin=historical,archive=archived)
        pending['publication']['prepared']=before
        pending['publication']['before_expose_unix_s']=time.time()
        os.link(temporary,path,follow_symlinks=False)
        pending['publication']['published']=True
        pending['publication']['after_expose_unix_s']=time.time()
        linked=base.identity(os.fstat(fd));pending['publication']['after_link']=linked
        require(request_identity(linked)==request_identity(before) and linked['nlink'] in (1,2),'Publication inode changed')
        require(request_identity(base.identity(temporary.lstat()))==request_identity(before),'Owned invisible temp replaced')
        temporary.unlink();base.fsync_directory(model)
        pending['publication']['after_temp_unlink']=base.identity(os.fstat(fd))
        require(pending['publication']['after_temp_unlink']['nlink']==1,'Request publication has an unexpected link')
        return pending
    except BaseException as error:
        primary=error
        raise
    finally:
        # Remove only our still-open, unchanged invisible inode. Never remove a
        # request/completed/failed path, including on an interrupted publication.
        try:
            if temporary.exists() and before is not None:
                if request_identity(base.identity(temporary.lstat()))==request_identity(before):temporary.unlink()
            os.close(fd)
        except BaseException as error:
            if primary is None:raise
            if pending is not None:pending['publication'].setdefault('secondary_cleanup_errors',[]).append(repr(error))


class Files:
    MAX_JSON = MAX_JSON

    def __init__(self, ops):
        self.ops = ops
        self.raw_api = self.api = None

    @staticmethod
    def identity(info):
        return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
            mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,
            mode=oct(stat.S_IMODE(info.st_mode)),uid=info.st_uid,nlink=info.st_nlink)

    @staticmethod
    def fsync_directory(path):
        fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)

    def fingerprint(self,path,limit=MAX_MODEL):
        path=Path(path)
        require(path.is_absolute() and path==path.resolve(strict=True),'Canonical absolute file required')
        with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
            before=os.fstat(f.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
                and 0<before.st_size<=limit,'Owned bounded single-link file required: '+str(path))
            h=hashlib.sha256()
            total=0
            while True:
                chunk=f.read(4<<20)
                if not chunk: break
                total+=len(chunk)
                require(total<=before.st_size,'File grew beyond the bounded snapshot')
                h.update(chunk)
            require(total==before.st_size and self.identity(before)==self.identity(os.fstat(f.fileno()))==self.identity(path.lstat()),'File changed: '+str(path))
        return dict(path=str(path),sha256=h.hexdigest(),bytes=before.st_size,identity=self.identity(before))

    def read_json(self,pin):
        require(self.fingerprint(pin['path'],MAX_JSON)==pin,'Metadata PIN changed')
        value=json.loads(Path(pin['path']).read_bytes())
        require(self.fingerprint(pin['path'],MAX_JSON)==pin,'Metadata changed while parsed')
        return value

    def publish(self,path,value):
        if value is self.api:
            # Preserve the authentic API bytes, including a legitimate skipped-step NaN norm.
            return self.ops.write_bytes(path,self.raw_api)
        return self.ops.publish(path,value)

    def exclusive_copy(self,source,destination):
        source=Path(source);destination=Path(destination)
        before=self.fingerprint(source)
        require(destination.is_absolute() and destination==destination.resolve(strict=False), 'Canonical NEW copy path required')
        with os.fdopen(os.open(source,os.O_RDONLY|os.O_NOFOLLOW),'rb') as src:
            require(self.identity(os.fstat(src.fileno()))==before['identity'],'Source replaced before copy')
            with destination.open('xb') as dst:
                written=0
                while True:
                    chunk=src.read(4<<20)
                    if not chunk: break
                    written+=len(chunk)
                    require(written<=before['bytes'],'Copy source grew beyond bounded snapshot')
                    dst.write(chunk)
                require(written==before['bytes'],'Copy source truncated')
                dst.flush();os.fchmod(dst.fileno(),0o444);os.fsync(dst.fileno())
            require(self.identity(os.fstat(src.fileno()))==before['identity'],'Source changed during copy')
        self.fsync_directory(destination.parent)
        copied=self.fingerprint(destination)
        require(self.fingerprint(source)==before and copied['sha256']==before['sha256'] and copied['bytes']==before['bytes']
            and (copied['identity']['device'],copied['identity']['inode'])!=(before['identity']['device'],before['identity']['inode']),
            'Independent copy/hash/identity changed')
        return before,copied


class Signals:
    @staticmethod
    @contextmanager
    def block_restore_signals():
        old=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM,signal.SIGHUP})
        try: yield
        finally: signal.pthread_sigmask(signal.SIG_SETMASK,old)


class CaptureRuntime:
    def __init__(self,ops,files,job,owner,source_hashes):
        self.ops,self.files,self.job,self.owner=ops,files,job,copy.deepcopy(owner)
        self.source_hashes=source_hashes
        self.publications=[];self._pending=None
        slot=Path(job['model_dir'])/'managed_save.request.json.completed'
        self.current_completed=files.fingerprint(slot,MAX_JSON) if slot.exists() else None
        self.metrics=Signals()

    @property
    def pending(self): return self._pending

    @pending.setter
    def pending(self,value):
        if value is not None and not any(value is x for x in self.publications):
            self.publications.append(value)
        self._pending=value

    def trainer_id(self):
        state,_=self.ops.show(self.owner['unit'])
        require(self.ops.process_start(self.owner['pid'])==self.owner['starttime_ticks'] and
            state['MainPID']==str(self.owner['pid']) and state['InvocationID']==self.owner['invocation_id'] and
            state['ControlGroup']==self.owner['cgroup'] and state['ActiveState']=='active' and
            state['SubState']=='running' and state['Restart']=='no','Actual live CE owner changed')
        return copy.deepcopy(self.owner)

    def request_guard(self):
        self.trainer_id()
        for path,sha in self.source_hashes.items():
            require(self.files.fingerprint(path,MAX_JSON)['sha256']==sha,'Capture source/control changed')
        if self.pending is not None:
            require(self.pending['tag']==self.job['tag'],'Foreign pending request registered')
            active=Path(self.job['model_dir'])/'managed_save.request.json'
            if active.exists():
                actual=self.files.fingerprint(active,MAX_JSON)
                require(self.pending['pin'] is not None and request_identity(actual['identity'])==
                    request_identity(self.pending['pin']['identity']) and actual['sha256']==self.pending['pin']['sha256'],
                    'Foreign/replaced pending request')
        else:
            model=Path(self.job['model_dir'])
            require(not (model/'managed_save.request.json').exists() and not (model/'managed_save.request.json.failed').exists(),
                'Foreign pending/failed save request appeared')
            slot=model/'managed_save.request.json.completed'
            require((self.files.fingerprint(slot,MAX_JSON) if slot.exists() else None)==self.current_completed,
                'Current completion changed outside owned request')


def sealed(files,pin):
    require(files.fingerprint(pin['path'],MAX_JSON)==pin and pin['identity']['mode']=='0o444',
        'Exact owned readonly metadata PIN required')
    return files.read_json(pin)


def recovery_context(job, files):
    """Consume the genuine forward-repair shape; never relabel it as CE_return."""
    require(set(job['recovery']) == {'result','job','release'}, 'Exact recovery evidence required')
    rec, repair, release = (sealed(files,job['recovery'][key]) for key in ('result','job','release'))
    require(rec['status']=='READY_CE_FORWARD_REPAIR' and rec['original_trial_failed'] is True and
        rec['trial_retried'] is False and rec['manual_recovery_required'] is False and
        rec['recovery_target_batch_size']==4096 and rec['qualification_pass'] is False,
        'Actual successful forward CE4096 repair required')
    require(rec['root_job']==job['recovery']['job'] and release['status']=='PASS' and
        triple(release['result'])==triple(job['recovery']['result']) and release['owner']==rec['owner']==job['expected_owner'] and
        release['original_exit']==0 and release['original_exec_code']==1 and release['original_result']=='success' and
        release['original_archived_before_release'] is True and release['unit_released'] is True and
        len(release['owned_release'])==2 and all(x['returncode']==0 and x['final_LoadState']=='not-found' for x in release['owned_release']),
        'Original successful repair/release/owner join differs')
    activation=sealed(files,repair['activation_job'])
    require(job['experiment']==activation['experiment'] and job['startup_tag']==repair['startup_tag'],
        'Actual experiment/startup tag differs')
    startup=rec['startup'];phase=copy.deepcopy(startup['phase']);record=sealed(files,phase['record'])
    proof=sealed(files,startup['phase_CPU_readonly_archive'])
    require(triple(release['actual_startup_CPU'])==triple(startup['phase_CPU_readonly_archive']) and
        proof['status']=='PASS' and proof['phase_metadata_verified'] is True and
        proof['held_recipe_context']['batch_size']==4096 and proof['root_job']['phase_snapshot']['owner']==rec['owner'] and
        proof['root_job']['phase_snapshot']['observed_clients']==0 and
        proof['root_job']['phase_snapshot']['phase_record']==phase['record'] and
        proof['root_job']['phase_snapshot']['expected_phase']==phase['expected'],
        'Actual CE4096 startup CPU/phase proof differs')
    expected=phase['expected'];saved=proof['saved_priority_metric_phase']
    require(record['action']=='start' and record['metric']==record['previous_metric']=='ce' and
        record['phase_id']==repair['phase_id']==expected['phase_id'] and
        record['checkpoint']==phase['boot_checkpoint']==triple(rec['boot_checkpoint']['source']) and
        record['root_precommit_sha256']==repair['repair_intent']['sha256']==expected['root_precommit_sha256'] and
        phase['record']['sha256']==expected['founder_phase_record_sha256'] and
        expected['last_resume_record_sha256'] is None and expected['valid'] is True and
        all(saved[k]==expected[k] for k in ('metric','phase_id','root_precommit_sha256','started_from','valid')) and
        saved['phase_record_sha256']==phase['record']['sha256'] and saved['last_resume_record_sha256'] is None,
        'Recovered CE founder/boot/intent lineage differs')
    boot=sealed(files,phase['boot_verification'])
    require(boot['status']=='PASS' and boot['sha256']==phase['boot_checkpoint']['sha256'] and
        boot['bytes']==phase['boot_checkpoint']['bytes'] and expected['started_from']==dict(phase['boot_checkpoint'],clocks=four(boot['clocks'])),
        'Original actual recovery boot proof differs')
    binding=rec['healthy192']['binding'];original=activation['before']
    require(len(binding['bindings']['actors'])==192 and binding['bindings']['actors']==original['bindings']['actors'] and
        binding['bindings']['source_hashes']==original['bindings']['source_hashes'] and
        binding['bindings']['control_hashes']==original['bindings']['control_hashes'] and
        binding['fleet']['MainPID']==original['fleet']['MainPID'] and
        binding['supervisor_start_ticks']==original['supervisor_start_ticks'] and
        binding['environment']['DQN_BATCH_SIZE']=='4096' and binding['environment']['DQN_PER_PRIORITY_METRIC']=='ce' and
        binding['environment']['DQN_PRIORITY_PHASE_RECORD']==phase['record']['path'] and
        binding['environment']['DQN_PRIORITY_PHASE_RECORD_SHA256']==phase['record']['sha256'],
        'Recovered actor/source/control/environment anchor differs')
    require(rec['final_resume']['all_matching_actors_resumed'] is True and not rec['final_resume']['failures'],
        'Repair did not undo every actor pause')
    return dict(recovery=rec,repair=repair,release=release,phase=phase,phase_proof=proof,binding=binding,
        actor_masks=activation['actor_masks'],worker_mask=activation['worker_mask'],fleet_unit=activation['fleet_unit'])


def current_ce_and_resources(ops, context, record):
    """Original resource checks, bound to the genuine recovered CE anchor."""
    show,process_start,actual_process=ops.show,ops.process_start,ops.actual_process
    read_file,cgroup_empty,identity=ops.read_file,ops.cgroup_empty,ops.identity
    command,GPU_UUIDS,CLOCKS=ops.command,ops.GPU_UUIDS,ops.CLOCKS
    EARLY_UNIT,BLOCKED=ops.EARLY_UNIT,ops.BLOCKED
    rec=context['recovery'];owner=rec['owner'];binding=context['binding'];original=binding
    phase_proof=context['phase_proof']
    current,_=show(owner['unit'])
    require(current['MainPID']==str(owner['pid']) and current['InvocationID']==owner['invocation_id'] and
        current['ControlGroup']==owner['cgroup'] and current['ActiveState']=='active' and
        current['SubState']=='running' and current['Restart']=='no','Recovered CE owner not retained/running')
    for released in context['release']['owned_release']:
        state,_=show(released['unit']);require(state['LoadState']=='not-found','Repair helper unit remains loaded')
    masks = {str(actor['pid']): actual_process(actor, original['bindings']['fleet_cgroup'])
        for actor in original['bindings']['actors']}
    require(len(masks) == 192 and masks == context['actor_masks'], 'Original192 masks changed')
    worker = binding['bindings']['worker']; main_mask = actual_process(worker['trainer'], owner['cgroup'])
    require(main_mask == context['worker_mask'], 'Main affinity changed')
    fleet, _ = show(context['fleet_unit'])
    require(fleet['MainPID'] == original['fleet']['MainPID']
        and fleet['ControlGroup'] == original['fleet']['ControlGroup']
        and process_start(int(fleet['MainPID'])) == original['supervisor_start_ticks'], 'Fleet supervisor changed')
    environment = dict(os.fsdecode(part).split('=',1) for part in
        Path('/proc',str(owner['pid']),'environ').read_bytes().split(b'\0') if b'=' in part)
    require(all(environment.get(key) == value for key,value in binding['environment'].items())
        and environment.get('DQN_PER_PRIORITY_METRIC') == 'ce'
        and not any(environment.get(key) for key in ('DQN_RECOMPUTED_CE_CAPTURE_DIR','DQN_EXECUTED_CE_TRACE_DIR')),
        'Actual CE environment changed')
    tid = worker['thread']; require(process_start(tid['tid']) == tid['starttime_ticks'], 'Inference TID changed')
    inference = sorted(os.sched_getaffinity(tid['tid']))
    require(inference == context['worker_mask']
        and Path('/proc', str(owner['pid']), 'task', str(tid['tid'])).exists(), 'Inference membership/mask changed')
    hashes = {}
    for path, digest in dict(binding['bindings']['source_hashes'], **original['bindings']['control_hashes']).items():
        _, pin = read_file(path); require(pin['sha256'] == digest, 'Held source/control changed: '+path); hashes[path] = digest
    for label, files in original['unit_files'].items():
        for path, digest in files.items():
            _, pin = read_file(path); require(pin['sha256'] == digest, 'Held unit source changed')
    for unit in (EARLY_UNIT, EARLY_UNIT.removesuffix('.service')+'.timer'):
        value, _ = show(unit); require(value['LoadState'] == 'not-found', 'Early CPU unit still loaded')
    observed_actors = set()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal() or int(entry.name) == os.getpid():
            continue
        try:
            argv = (entry/'cmdline').read_bytes().split(b'\0')
        except OSError as error:
            if error.errno in (2, 3): continue
            raise
        require(not any(os.path.basename(os.fsdecode(arg)) in BLOCKED for arg in argv if arg),
            'Parent/private numerical helper remains: '+entry.name)
        if argv and os.path.basename(os.fsdecode(argv[0])) == 'mame' and b'robotron' in argv:
            observed_actors.add(int(entry.name))
    require(observed_actors == {actor['pid'] for actor in original['bindings']['actors']},
        'Global Robotron MAME inventory is not exactly the original192')
    private = list(Path('/dev/shm').glob('robotron-snapshot-smoke-*'))
    require(not any(p.is_dir() for p in private), 'Private tmpfs remains')
    app = Path('/sys/fs/cgroup')/owner['cgroup'].lstrip('/')
    for group in app.parent.glob('robotron-snapshot-smoke-*'):
        cgroup_empty('/'+str(group.relative_to('/sys/fs/cgroup')))
    cgroup_empty('/user.slice/user-%s.slice/user@%s.service/app.slice/%s' % (os.getuid(), os.getuid(), EARLY_UNIT))
    for table in ('tcp', 'tcp6'):
        for line in Path('/proc/net', table).read_text().splitlines()[1:]:
            row = line.split(); require(not (row[3] == '0A' and int(row[1].rsplit(':',1)[1],16) == 9999), 'Port9999 listener remains')
    lease = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
    before = lease.lstat(); require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid(), 'Lease identity differs')
    fd = os.open(lease, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(fd)) == identity(before) == identity(lease.lstat()), 'Lease open race')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)
    gpu = command(['nvidia-smi', '--query-gpu=index,uuid', '--format=csv,noheader,nounits'])
    apps = command(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader,nounits'])
    require(gpu['returncode'] == apps['returncode'] == 0, 'GPU observation failed')
    gpu_map = {int(row.split(',')[0].strip()):row.split(',')[1].strip() for row in gpu['stdout'].splitlines() if row.strip()}
    app_rows = [(int(row.split(',')[0].strip()),row.split(',')[1].strip()) for row in apps['stdout'].splitlines() if row.strip()]
    require(gpu_map == GPU_UUIDS and app_rows == [(owner['pid'], GPU_UUIDS[1])],
        'Known GPU mapping differs/GPU0 not free/main not sole GPU1 process')
    record('GPU-index-map', gpu); record('GPU-processes', apps)
    # API values can legitimately contain a NaN grad_norm for a recorded AMP skip.
    # Preserve raw response bytes; no parser or gradient-value rewrite.
    import urllib.request
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=3) as response:
        raw = response.read(2 << 20)
    api = json.loads(raw); pipeline = api['host_pipeline']; graphs = pipeline['inference_graphs']
    require(api['client_count'] == 192 and api['training_enabled'] is True
        and 0 <= time.time()-float(api['ts']) <= 5
        and pipeline['learning_exposure']['optimizer']['process_id'] == owner['pid']
        and pipeline['learning_exposure']['replay']['process_id'] == owner['pid']
        and graphs['ready'] and graphs['capture_count'] == 128 and graphs['validation_replay_count'] == 640
        and graphs['postload_validations'] >= 1 and graphs['runtime_capture_count'] == graphs['fallback_count'] == 0
        and graphs['fatal_error'] is None and all(pipeline[key]['errors'] == 0 for key in
            ('inference','actor_refresh','target_refresh','learner_priority'))
        and all(api[key] >= phase_proof['clocks'][key] for key in CLOCKS),
        'Current CE192/graphs/API owner differs')
    after, _ = show(owner['unit'])
    require(process_start(owner['pid']) == owner['starttime_ticks'] and after['MainPID'] == str(owner['pid'])
        and after['InvocationID'] == owner['invocation_id'], 'CE owner changed during cleanup proof')
    return dict(owner=owner, actor_masks=masks, main_mask=main_mask, inference_mask=inference,
        source_control_hashes=hashes, GPU0_free=True, sole_main_on_GPU1=True,
        lease_unheld=True, port9999_unused=True, no_private_tmpfs_or_helpers=True), raw


def run(job,job_pin,ops,snapmod,phase,files):
    fields={'schema','experiment','model_dir','output_directory','tag','startup_tag','save_timeout_s',
        'expected_owner','root_release','recovery','cpu_python'}
    require(set(job)==fields and job['schema']==SCHEMA and job['save_timeout_s']==60,'Exact capture job/budget schema required')
    model=Path(job['model_dir']);out=Path(job['output_directory'])
    require(model==GAME/'models_dqn' and out.is_absolute() and out==out.resolve(strict=False)
        and out.parent==RUN and not out.exists(),'Actual default model directory and NEW direct run26 output required')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',job['tag'] or '') and job['tag']!=job['startup_tag'],'Unique nonstartup tag required')
    require(isinstance(job['cpu_python'],str) and Path(job['cpu_python']).is_absolute(),'Root verified venv argv required')
    release=job['root_release']
    require(set(release)=={'source_freeze_released','quality_cleanup','freeze_release'} and release['source_freeze_released'] is True,
        'Root must explicitly release the completed quality source freeze before capture')
    released=sealed(files,release['freeze_release'])
    require(released['source_freeze_released'] is True and released['owned_cleanup_complete'] is True and
        released['status']=='PASS_ROOT_EXPLICIT_CURRENT_CE543M_SOURCE_FREEZE_RELEASE' and
        released['actual_owned_closure']==release['quality_cleanup'] and
        released['actual_plan_sha256']=='25aaded11bf956b715cc5fb58be1901d236a30444e74253594461f8d11c00d75' and
        released['current_campaign']=='quality-448M-vs-CE543M-20261017' and
        released['all69_original_owned_processes_absent'] is True and released['original_parent_exit']==0 and
        released['original_audit_exits_preserved']==[0,2,0,0], 'Actual root freeze release/cleanup join differs')
    cleanup=sealed(files,release['quality_cleanup'])
    require(cleanup['status']=='PASS_ORIGINAL_QUALITY_ARCHIVED_OWNED_CLEANUP_COMPLETE' and cleanup['owned_cleanup_complete'] is True,
        'Actual completed original quality cleanup required')
    context=recovery_context(job,files);rec=context['recovery'];current_phase=context['phase']
    out.mkdir(mode=0o700);files.fsync_directory(out.parent)
    commands=[];result=dict(schema=RESULT_SCHEMA,status='STARTING',qualification_pass=False,
        cpu_verification=None,root_job=job_pin,source_freeze_released=True,raw_commands=commands)
    def record(name,raw):
        p=files.publish(out/('%03d-'%len(commands)+name+'-command.json'),raw);commands.append(p);return p
    def health():
        return current_ce_and_resources(ops,context,record)
    snapshot=None
    try:
        before,raw=health();require(before['owner']==job['expected_owner'],'Fresh actual owner differs')
        files.raw_api=raw;files.api=json.loads(raw);floor=four(files.api)
        require(files.api['client_count']==192 and files.api['training_enabled'] is True and
            not files.api.get('measurement_active',False),'Live unpaused192 nonmeasurement capture only')
        before_pin=files.publish(out/'before-capture-resources.json',before)
        runtime=CaptureRuntime(ops,files,job,before['owner'],before['source_control_hashes'])
        adapter=type('SnapshotPrimitives',(),dict(four=staticmethod(four),triple=staticmethod(triple),
            request_identity=staticmethod(request_identity),publish_request=staticmethod(publish_request)))
        snapshot=snapmod.Snapshot(adapter,files,runtime,{'tag':job['tag'],'save_timeout_s':60},out/'capture')
        snapshot.start(files.api,floor)
        while snapshot.state=='PENDING':
            time.sleep(.2);snapshot.tick()
        require(snapshot.state=='COMPLETE','First owned managed save failed: '+str(snapshot.error))
        frozen=snapshot.freeze(purpose='candidate',phase=current_phase)
        after,after_api=health();require(after['owner']==before['owner'],'CE owner changed across freeze')
        after_pin=files.publish(out/'after-capture-resources.json',after)
        files.ops.write_bytes(out/'after-capture-API.json',after_api)
        metadata=out/'metadata';metadata.mkdir(mode=0o700)
        sources={}
        for name in SOURCE_NAMES:
            src,archive=files.exclusive_copy(GAME/'Scripts/dqn'/name,metadata/name)
            sources[name]=dict(current=src,archive=archive)
        _,control=files.exclusive_copy(model/'learning_control.json',metadata/'learning_control.json')
        unit=ops.command(['systemctl','--user','cat',rec['owner']['unit']]);require(unit['returncode']==0,'Current trainer unit cat failed')
        unit_pin=ops.write_bytes(metadata/'trainer-unit.txt',unit['stdout'].encode('utf-8','surrogateescape'))
        _,boot_archive=files.exclusive_copy(current_phase['boot_verification']['path'],metadata/'boot-CPU-proof.json')
        require(boot_archive['sha256']==current_phase['boot_verification']['sha256'] and
            boot_archive['bytes']==current_phase['boot_verification']['bytes'],'Actual ORIGINAL boot proof changed')
        current_phase['boot_verification']=boot_archive
        strict=phase.load_base()  # Stdlib-only metadata setup; never numerical_setup/validate_checkpoint.
        context=dict(game_root=str(GAME),model_dir=str(model),
            model_package={n:sources[n]['current'] for n in strict.MODEL_NAMES},
            archived_control=control,archived_trainer_unit=unit_pin,
            provenance=[job_pin,release['quality_cleanup'],before_pin,after_pin,snapshot.raw_pin],
            held_recipe_context=strict.HELD_RECIPE_CONTEXT)
        spec=dict(purpose='candidate',owner=before['owner'],observed_clients=192,phase_record=current_phase['record'],
            boot_checkpoint=current_phase['boot_checkpoint'],boot_verification=boot_archive,
            expected_phase=current_phase['expected'],acquisition=frozen['acquisition'],sources=sources)
        cpu_job=dict(schema=phase.SCHEMA,verifier_sha256=DEPENDENCIES['phase'][1],
            strict_phase_base_sha256=phase.STRICT_SHA256,original_strict_base_sha256=phase.ORIGINAL_SHA256,
            experiment=job['experiment'],source=frozen['source'],verification_copy=frozen['verification_copy'],clock_floor=floor,
            source_control_context=context,output_directory=str(out/'phase-CPU-output'),phase_snapshot=spec)
        evidence=dict(bound_files={})
        model_dir=strict.check_context(cpu_job,evidence)
        phase.check_acquisition(cpu_job,strict,evidence,model_dir)  # Metadata/source-only; no model/tensor load.
        runtime.request_guard();require(runtime.current_completed==snapshot.completed,'Current completed slot lost')
        cpu_pin=files.publish(out/'phase-CPU-job.json',cpu_job)
        require(cpu_pin['bytes']<=1<<20,'Phase CPU job exceeds frozen1MiB limit')
        cpu_argv=[job['cpu_python'],'-Xgil=0','-I','-B',str(DEPENDENCIES['phase'][0]),'--execute','--job',cpu_pin['path'],
            '--expected-job-sha256',cpu_pin['sha256'],'--expected-verifier-sha256',DEPENDENCIES['phase'][1]]
        result.update(status='CAPTURED_PENDING_CPU',owner=before['owner'],source=frozen['source'],
            verification_copy=frozen['verification_copy'],acquisition=frozen['acquisition'],cpu_job=cpu_pin,
            cpu_argv=cpu_argv,trigger_API=snapshot.raw_pin,current_phase=current_phase,
            capture_completion=files.publish(out/'capture-completion.json',dict(status='COMPLETE',tag=job['tag'],
                owner_before=snapshot.owner,owner_after=snapshot.owner_after,transition=snapshot.transition,
                request_publication=runtime.publications)),candidate_clocks=None,
            cpu_completion=None,model_only=True,replay_RNG_actor_anchor=False)
        files.publish(out/'result.json',result);return result
    except BaseException as error:
        result.update(status='FAILED',error=repr(error),traceback=traceback.format_exc(),
            snapshot_state=None if snapshot is None else snapshot.result(),
            scope='Preserve first failure and any owned pending request; no retry/stop/resume/rollback or CPU launch')
        try:files.publish(out/'result.json',result)
        except BaseException as secondary:print('Secondary capture reporting error: '+repr(secondary),file=sys.stderr)
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path)
    parser.add_argument('--expected-job-sha256');parser.add_argument('--expected-source-sha256')
    args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: root-owned post-quality liveCE capture; no reads/imports/requests/outputs/actions')
        return 0
    require(args.job is not None and re.fullmatch('[0-9a-f]{64}',args.expected_job_sha256 or '')
        and re.fullmatch('[0-9a-f]{64}',args.expected_source_sha256 or ''),'Explicit actual pinned job/source required')
    # Bootstrap copies only stdlib-safe file primitives before loading any reviewed helper.
    bootstrap=Files(None);self_pin=bootstrap.fingerprint(Path(__file__).resolve(),MAX_JSON)
    require(self_pin['sha256']==args.expected_source_sha256 and self_pin['identity']['mode']=='0o444','Capture source not exact sealed source')
    jp=bootstrap.fingerprint(args.job,1<<20);require(jp['sha256']==args.expected_job_sha256 and jp['identity']['mode']=='0o444','Job not exact sealed job')
    job=bootstrap.read_json(jp)
    for path,sha in DEPENDENCIES.values():
        p=bootstrap.fingerprint(path,MAX_JSON);require(p['sha256']==sha and p['identity']['mode']=='0o444','Reviewed dependency changed')
    ops=load_module(DEPENDENCIES['resources'][0],'_live_ce_capture_resource_checks')
    snapmod=load_module(DEPENDENCIES['snapshot'][0],'_live_ce_capture_snapshot')
    phase=load_module(DEPENDENCIES['phase'][0],'_live_ce_capture_phase_metadata')
    return 0 if run(job,jp,ops,snapmod,phase,Files(ops))['status']=='CAPTURED_PENDING_CPU' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        traceback.print_exc();raise SystemExit(1)
