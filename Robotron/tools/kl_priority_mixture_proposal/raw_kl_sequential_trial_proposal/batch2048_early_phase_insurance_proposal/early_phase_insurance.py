"""One asynchronous CE2048 early phase snapshot; literal PLAN by default.

The root controller owns the active runtime, observation clock and ending. Only
Snapshot.start/tick mutate its managed-request bookkeeping, on the main thread.
Model copying and the single retained CPU unit run in a background thread. No
Torch, NumPy, application import, model decoding or replay copy occurs here.
"""
import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import threading
import time
import traceback

MAX_MODEL = 512 << 20
OWNER_KEYS = {'pid', 'starttime_ticks', 'unit', 'invocation_id', 'cgroup'}


def require(value, message):
    if not value:
        raise RuntimeError(message)


EXECUTION_KIND = 'phase_early_insurance2048'
RESULT_SCHEMA = 'robotron-batch2048-early-phase-insurance-result-v1'
CPU_JOB_SCHEMA = 'robotron-batch2048-phase-snapshot-checkpoint-CPU-job-reviewed2-v1'
CPU_RESULT_SCHEMA = 'robotron-batch2048-phase-snapshot-checkpoint-CPU-result-reviewed2-v1'
ORIGINAL_STRICT_SHA = '7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
PROFILE = dict(path='/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_profile_horizon_proposal/profile.json',
    sha256='e755e22ade5cb56537b08f41f412e856da09435d88e4e71e09b22aba521eac50', bytes=764)
CPU_FAMILY = {'script': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_phase_cpu_verifier_reviewed2_proposal/verify_phase_snapshot_2048.py', 'sha256': 'a331b550191a48ab219cf92f2e1c42fc394e038c93609ecac4fb9a722b75e5cd', 'bytes': 37695}, 'strict_base': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_phase_cpu_verifier_reviewed2_proposal/strict_phase_base_2048.py', 'sha256': '47677509f170c4c3b6a1c03918e02ab13996af1ceafffac29b7536c2fad61f80', 'bytes': 33727}}
COLLECTOR_BINDING = {'script': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_producer_collector_proposal/collect_producer.py', 'sha256': 'b6a338297ca91f39b1270db8179fac06cd3ba3d6ef5fb175df46968ca6c3bcfb', 'bytes': 23824}, 'manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_producer_collector_proposal/preparation-manifest.json', 'sha256': '193b3956f6808cd4813527e369b8b30552d5d940dbc6d0bc352630a1d4dfa1fd', 'bytes': 3499}}  # Exact frozen193b/b6a family.
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')



class ReadonlyMetadataBase:
    """Only NEW local JSON is sealed; delegate existing bounded copier/identity IO."""
    def __init__(self, base):self.original=base
    def __getattr__(self, name):return getattr(self.original,name)
    def publish(self,path,value):
        path=Path(path)
        raw_api=path.name=='trigger-API.json' and path.parent.name=='snapshot'
        raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=raw_api)+'\n').encode()
        require(0<len(raw)<=self.MAX_JSON,'Bounded new local metadata required')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            offset=0
            while offset<len(raw):
                count=os.write(fd,raw[offset:]);require(count>0,'Short metadata write');offset+=count
            os.fchmod(fd,0o444);os.fsync(fd)
            require(self.identity(os.fstat(fd))==self.identity(path.lstat()),'New metadata path changed during publication')
        finally:os.close(fd)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        result=self.fingerprint(path,self.MAX_JSON)
        require(result['sha256']==hashlib.sha256(raw).hexdigest() and result['bytes']==len(raw) and
            result['identity']['mode']=='0o444' and result['identity']['uid']==os.getuid() and result['identity']['nlink']==1,
            'Published new readonly metadata differs')
        return result


def triple(value):
    return {key:value[key] for key in ('path','sha256','bytes')}


def readonly_json(base, pin):
    require(pin['identity']['mode']=='0o444' and pin['identity']['uid']==os.getuid()
        and pin['identity']['nlink']==1,'Independent owned readonly metadata required')
    return base.read_json(pin)


def checked_profile(base, pin):
    require(triple(pin)==PROFILE,'Wrong exact CE2048 profile')
    value=readonly_json(base,pin)
    require(value['priority_metric']=='ce' and value['batch_size']==2048 and
        value['before_batch_size']==value['return_batch_size']==4096 and value['LR_compensation'] is False
        and value['deliberate_recipe_changes']==['DQN_BATCH_SIZE'],'Wrong held one-knob profile')
    return value


def load_collector(base, binding):
    require(COLLECTOR_BINDING is not None,'UNCONSUMED: final collector source binding is unresolved')
    require(set(binding)=={'script','manifest'} and
        {name:triple(binding[name]) for name in ('script','manifest')}==COLLECTOR_BINDING,
        'Wrong exact reviewed producer collector')
    for value in binding.values():base.pin(value,base.MAX_SOURCE)
    module=base.load_module(binding['script']['path'],'CE2048_early_producer_collector')
    for value in binding.values():base.pin(value,base.MAX_SOURCE)
    require(str(Path(module.__file__).resolve())==binding['script']['path'],'Unexpected collector module path')
    return module


def check_python_identity(base, verifier, *, hash_executable):
    """Preserve the successful venv argv; attest its final symlink separately.

    Resolving argv itself before Popen would change Python's venv discovery.
    The23MiB executable is hashed at read_job and before CPU spawn only; frequent
    runtime guards compare its full stat identity, plus the small context pins.
    """
    spec = verifier["python_identity"]
    required = {"argv_path", "link_target", "link_identity", "executable", "pyvenv_cfg", "library_context"}
    require(isinstance(spec, dict) and set(spec) == required, "Invalid explicit Python binding")
    argv_path = Path(verifier["python"])
    require(str(argv_path) == spec["argv_path"] and argv_path.is_absolute() and argv_path.name == "python"
        and argv_path.parent == argv_path.parent.resolve(strict=True), "Python argv is not the explicit canonical-parent venv path")
    before = argv_path.lstat()
    require(stat.S_ISLNK(before.st_mode) and base.identity(before) == spec["link_identity"]
        and os.readlink(argv_path) == spec["link_target"], "Python venv symlink changed")
    target = base.canonical(spec["executable"]["path"])
    require(argv_path.resolve(strict=True) == target and target.stat().st_size <= 64 << 20
        and os.access(argv_path, os.X_OK), "Python resolved executable differs or is not executable")
    if hash_executable:
        base.pin(spec["executable"], 64 << 20)
    else:
        info = target.lstat()
        require(stat.S_ISREG(info.st_mode) and base.identity(info) == spec["executable"]["identity"]
            and info.st_size == spec["executable"]["bytes"], "Python executable metadata changed")
    venv = argv_path.parent.parent
    require(spec["pyvenv_cfg"]["path"] == str(venv / "pyvenv.cfg"), "Wrong venv configuration pin")
    base.pin(spec["pyvenv_cfg"], base.MAX_SOURCE)
    require(isinstance(spec["library_context"], list) and len(spec["library_context"]) == 4, "Exactly four held library context pins required")
    site = venv / "lib/python3.14t/site-packages"
    expected = {str(site / package / name) for package in ("torch", "numpy") for name in ("__init__.py", "version.py")}
    require({item["path"] for item in spec["library_context"]} == expected, "Python library context paths differ")
    for item in spec["library_context"]:
        base.pin(item, base.MAX_SOURCE)
    require(base.identity(argv_path.lstat()) == base.identity(before) and os.readlink(argv_path) == spec['link_target']
        and argv_path.resolve(strict=True) == target, 'Python symlink changed during identity check')
    return dict(argv_path=str(argv_path), resolved_executable=str(target),
        executable_sha256=spec['executable']['sha256'], executable_hashed=hash_executable,
        scope='Environment identity only; new numerical provenance requires actual retained phase CPU success')


def phase_job(adapter,base,experiment,owner,phase,pairs,context,frozen,floor,profile,producer,output):
    recipe=checked_profile(base,profile)
    acquisition=readonly_json(base,frozen['acquisition']);observed=readonly_json(base,producer)
    require(acquisition['schema']=='robotron-owned-phase-snapshot-acquisition-v1' and
        acquisition['purpose']=='candidate' and acquisition['client_count']==192 and
        acquisition['owner_before']==acquisition['owner_after']==owner and
        acquisition['source_checkpoint']==triple(frozen['source']) and acquisition['clock_floor']==floor and
        acquisition['phase_record_sha256']==phase['record']['sha256'] and
        acquisition['boot_checkpoint']==phase['boot_checkpoint'] and acquisition['stopped_absence'] is None,
        'Genuine active192 phase acquisition required; not startup/stopped/candidate selection')
    require(observed['schema']=='robotron-root-batch2048-producer-observation-v1' and
        observed['owner']==owner and observed['source_checkpoint']==triple(frozen['source']) and
        observed['acquisition_sha256']==frozen['acquisition']['sha256'] and observed['csv_scope']=='producer2048'
        and observed['profile_sha256']==PROFILE['sha256'],'Final actual2048 producer acquisition join differs')
    require(phase['expected']['metric']=='ce' and phase['expected']['valid'] is True and
        context['held_recipe_context']==recipe['held_recipe_context'],'Exact CE2048 model/recipe context required')
    require(all(type(floor[k]) is int and floor[k]>0 for k in CLOCKS),'Real four-clock floor required')
    return dict(schema=CPU_JOB_SCHEMA,verifier_sha256=CPU_FAMILY['script']['sha256'],
        strict_phase_base_sha256=CPU_FAMILY['strict_base']['sha256'],original_strict_base_sha256=ORIGINAL_STRICT_SHA,
        experiment=experiment,source=copy.deepcopy(frozen['source']),verification_copy=copy.deepcopy(frozen['verification_copy']),
        clock_floor=copy.deepcopy(floor),source_control_context=copy.deepcopy(context),output_directory=str(output),
        phase_snapshot=dict(purpose='candidate',owner=copy.deepcopy(owner),observed_clients=192,
            phase_record=copy.deepcopy(phase['record']),boot_checkpoint=copy.deepcopy(phase['boot_checkpoint']),
            boot_verification=copy.deepcopy(phase['boot_verification']),expected_phase=copy.deepcopy(phase['expected']),
            acquisition=copy.deepcopy(frozen['acquisition']),sources=copy.deepcopy(pairs)),
        batch2048_context=dict(profile=copy.deepcopy(profile),role='early_insurance',producer_observation=copy.deepcopy(producer)))


def check_phase_report(base, report_pin, job_pin):
    report=base.read_json(report_pin);job=readonly_json(base,job_pin)
    require(report.get('status')=='PASS' and report.get('schema')==CPU_RESULT_SCHEMA and report.get('role')=='phase_snapshot'
        and job['verifier_sha256']==CPU_FAMILY['script']['sha256'] and
        job['strict_phase_base_sha256']==CPU_FAMILY['strict_base']['sha256'] and job['original_strict_base_sha256']==ORIGINAL_STRICT_SHA and
        report['script']['sha256']==CPU_FAMILY['script']['sha256'] and report['strict_phase_base']['sha256']==CPU_FAMILY['strict_base']['sha256'] and
        report.get('root_job')==job and report['job_file']['sha256']==job_pin['sha256'] and
        report.get('phase_metadata_verified') is True and job['schema']==CPU_JOB_SCHEMA and
        job['phase_snapshot']['purpose']=='candidate' and job['phase_snapshot']['observed_clients']==192 and
        job['batch2048_context']['role']=='early_insurance' and report['configured_batch_size']==2048 and
        report['actual_producer_batch_size']==2048 and report['producer_CSV_verified'] is True,
        'Actual reviewed2 phase early-insurance report/job/profile required; no legacy7d relabelling')
    require(report['sha256']==job['source']['sha256']==job['verification_copy']['sha256'] and
        report['bytes']==job['source']['bytes']==job['verification_copy']['bytes'] and
        report['saved_priority_metric_phase']['metric']=='ce' and report['saved_priority_metric_phase']['valid'] is True and
        all(type(report['clocks'][k]) is int and report['clocks'][k]>=job['clock_floor'][k] for k in CLOCKS),
        'Actual phase model/finite clockfloor proof differs')
    return report


def check_phase_provenance(base,verifier,job_pin,proof):
    report_pin=proof['phase_cpu_report'];readonly_json(base,report_pin)
    report=check_phase_report(base,report_pin,job_pin)
    original=proof['original_numeric_report'];base.pin(original,base.MAX_JSON)
    require(original['sha256']==report_pin['sha256'] and original['bytes']==report_pin['bytes'] and
        (original['identity']['device'],original['identity']['inode'])!=(report_pin['identity']['device'],report_pin['identity']['inode']),
        'Numeric result must be independently archived; never chmod historical original')
    execution=readonly_json(base,proof['successful_execution']);completion=readonly_json(base,proof['successful_completion'])
    result=readonly_json(base,proof['successful_result'])
    owner=completion['original_owner']
    require(isinstance(owner,dict) and set(owner)==OWNER_KEYS and completion['original_pid']==owner['pid'] and
        completion['original_invocation']==owner['invocation_id'] and completion['original_nrestarts']==0 and
        completion['original_exec_code']==result['original_exec_code']==1 and
        completion['original_exit']==result['original_exit']==0 and completion['result']==result['original_result']=='success'
        and result['original_pid']==owner['pid'] and result['original_invocation']==owner['invocation_id'] and
        result['original_owner']==owner and result['actual_unit']==owner['unit'] and result['status']=='PASS' and
        execution['kind']==result['kind']==EXECUTION_KIND and execution['unit']==owner['unit'] and
        result['original_archived_before_release'] is True and result['numeric_report_sha256']==report_pin['sha256'] and
        result['original_completion']==proof['successful_completion'],'Actual original retained phase CPU provenance required')
    expected=[verifier['python'],'-Xgil=0','-I','-B','-u',CPU_FAMILY['script']['path'],'--execute','--job',job_pin['path'],
        '--expected-job-sha256',job_pin['sha256'],'--expected-verifier-sha256',CPU_FAMILY['script']['sha256']]
    require(execution['command']==expected and execution['argv'][-len(expected):]==expected and execution['job']==job_pin,
        'Original exact retained numerical argv/job differs')
    require([r['unit'] for r in result['releases']]==[execution['timer'],owner['unit']],
        'Exact timer-first/service release ordering required')
    for key in ('terminal_show','terminal_cat','invocation_journal'):
        artifact=completion[key];base.pin(artifact,base.MAX_SOURCE)
        require(artifact['identity']['mode']=='0o444' and artifact['identity']['uid']==os.getuid()
            and artifact['identity']['nlink']==1,'Original execution archives must be readonly')
    return report


def archive_phase_report(helper,original_report,destination):
    """Reuse the pinned metadata copier; never broaden the model-copy registry."""
    copied=helper.adapter.archive_metadata(helper.base,original_report,destination)
    helper.base.pin(original_report,helper.base.MAX_JSON)
    require(copied['sha256']==original_report['sha256'] and copied['bytes']==original_report['bytes'] and
        copied['identity']['mode']=='0o444' and
        (copied['identity']['device'],copied['identity']['inode'])!=
        (original_report['identity']['device'],original_report['identity']['inode']),
        'Independent actual numeric report archive differs')
    return copied


def phase_insurance_floor(base,result_pin,expected_owner,expected_phase_record,profile):
    result=readonly_json(base,result_pin);checked_profile(base,profile)
    require(result['schema']==RESULT_SCHEMA and result['status']=='PASS' and result['role']=='early_insurance' and
        result['owner']==expected_owner and result['phase']['record']==expected_phase_record and result['profile']==profile and
        result['eligible_quality_candidate'] is False and result['legacy_7d_insurance'] is False,
        'Explicit CE2048 early phase result required; never substitute legacy insurance/candidate')
    require(result['phase_cpu_report']==result['cpu_provenance']['phase_cpu_report'],
        'Published early phase report differs from its actual CPU provenance')
    job=readonly_json(base,result['phase_cpu_job']);verifier=dict(python=result['python'])
    report=check_phase_provenance(base,verifier,result['phase_cpu_job'],result['cpu_provenance'])
    require(job['phase_snapshot']['owner']==expected_owner and job['phase_snapshot']['phase_record']==expected_phase_record,
        'Insurance belongs to another owner/phase')
    saved=readonly_json(base,result['saved_receipt'])
    require(saved['role']=='early_insurance' and saved['tag']==result['tag'] and saved['trainer']==expected_owner
        and saved['source']==job['source'] and saved['acquisition']==job['phase_snapshot']['acquisition'],
        'Distinct actual saved early tag/acquisition differs')
    return dict(owner=copy.deepcopy(expected_owner),clock_floor={k:report['clocks'][k] for k in CLOCKS},
        tag=result['tag'],phase_record=copy.deepcopy(expected_phase_record),report=result['phase_cpu_report'],
        source=job['source'],role='early_insurance',legacy_7d_insurance=False,eligible_quality_candidate=False)



def command(argv, *, timeout=5):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    absent_show = argv[:3] == ['systemctl', '--user', 'show'] and 'LoadState=not-found' in result.stdout.splitlines()
    require(result.returncode == 0 or absent_show, 'Owned command failed: '+repr(argv)+': '+result.stderr[:1024])
    return result.stdout


def publish_text(base, path, text, *, allow_empty_journal=False):
    require((0 if allow_empty_journal else 1) <= len(text.encode()) <= base.MAX_SOURCE, 'Bounded nonempty unit/source archive required')
    with Path(path).open('x') as stream:
        stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o444)
    descriptor = os.open(Path(path).parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return base.fingerprint(path, base.MAX_SOURCE)


class Snapshot:
    """One unique managed request, then one explicit independent freeze.

    tick returns PENDING/COMPLETE/FAILED and never reads model bytes. freeze is
    called only in the early background task or after the candidate latch/pause.
    The caller enforces its ending wall budget independently of filesystem I/O.
    """
    def __init__(self, adapter, base, runtime, spec, output, *, clock=time.monotonic, wall=time.time):
        self.adapter, self.base, self.runtime = adapter, base, runtime
        self.spec, self.output = copy.deepcopy(spec), Path(output)
        require(self.output.is_absolute(), 'Snapshot output must be an explicit absolute owned path')
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', self.spec['tag'] or ''), 'Unique snapshot tag required')
        require(self.spec['save_timeout_s'] == 60, 'Snapshot save budget differs')
        self.clock, self.wall = clock, wall
        self.state, self.error, self.frozen = 'NEW', None, None
        self.freeze_started = False
        self.owner = self.raw_pin = self.transition = self.completed = self.floor = None

    def start(self, raw, clock_floor):
        require(self.state == 'NEW', 'Managed snapshot is one-shot')
        self.state = 'STARTING'
        try:
            runtime, base = self.runtime, self.base
            self.owner = copy.deepcopy(runtime.trainer_id())
            require(set(self.owner) == OWNER_KEYS, 'Actual owned trainer identity required')
            require(raw['client_count'] in (0, 192) and type(raw['client_count']) is int and
                    raw['host_pipeline']['learning_exposure']['optimizer']['process_id'] == self.owner['pid'] and
                    not raw.get('measurement_active', False), 'Snapshot API owner/client scope differs')
            self.floor = self.adapter.four(clock_floor)
            require(all(raw[key] >= value for key, value in self.floor.items()), 'Snapshot floor exceeds observed clocks')
            self.output.mkdir(mode=0o700)
            self.raw_pin = base.publish(self.output/'trigger-API.json', raw)
            model = Path(runtime.job['model_dir'])
            self.target = model/'managed-checkpoints'/(self.spec['tag']+'.pt')
            require(all(not Path(str(self.target)+suffix).exists() for suffix in ('', '.tmp', '.bak')),
                    'Snapshot source/tmp/bak must all be new')
            require(not (model/'managed_save.request.json').exists() and runtime.pending is None,
                    'Another managed request is pending')
            require(not (model/'managed_save.request.json.failed').exists(), 'Unresolved failed request')
            self.transition = dict(before=None, before_unix_s=self.wall())
            slot = model/'managed_save.request.json.completed'
            if slot.exists():
                before = base.fingerprint(slot, base.MAX_JSON)
                require(before == runtime.current_completed, 'Current completion changed before new request')
                actual, archive = base.exclusive_copy(slot, self.output/'completed-before.json')
                self.transition['before'] = dict(actual_pin=actual, archive=archive)
            require(self.spec['tag'] != runtime.job['startup_tag'], 'Insurance/candidate cannot reuse startup tag')
            self.started = self.clock()
            with runtime.metrics.block_restore_signals():
                pending = self.adapter.publish_request(base, model, self.output/'request.json', self.spec['tag'],
                                                      lambda value: setattr(runtime, 'pending', value))
            self.transition.update(request=dict(actual_pin=pending['pin'], archive=pending['archive']),
                                   request_unix_s=pending['publication']['before_expose_unix_s'])
            self.state = 'PENDING'
        except BaseException as error:
            self.state, self.error = 'FAILED', error
            raise
        return self.result()

    def tick(self):
        if self.state != 'PENDING':
            return self.result()
        try:
            require(self.clock() <= self.started + 60, 'First managed snapshot timed out; no retry')
            runtime, base = self.runtime, self.base
            require(runtime.trainer_id() == self.owner, 'Snapshot owner changed')
            runtime.request_guard()
            model = Path(runtime.job['model_dir']);slot = model/'managed_save.request.json.completed'
            failed = model/'managed_save.request.json.failed'
            if failed.exists() and base.read_json(base.fingerprint(failed, base.MAX_JSON)) == {'tag': self.spec['tag']}:
                raise RuntimeError('First managed snapshot failed; no retry')
            observed = base.fingerprint(slot, base.MAX_JSON)
            if base.read_json(observed) != {'tag': self.spec['tag']}:
                return self.result()
            pending = runtime.pending
            require(pending is not None and self.adapter.request_identity(observed['identity']) ==
                    self.adapter.request_identity(pending['pin']['identity']) and observed['identity']['nlink'] == 1,
                    'Completion is not the originally published owned request')
            actual, archive = base.exclusive_copy(slot, self.output/'completed-after.json')
            require(actual == observed, 'Completed request changed during archive')
            self.owner_after = copy.deepcopy(runtime.trainer_id())
            require(self.owner_after == self.owner, 'Snapshot owner changed across actual completion archive')
            self.transition.update(after=dict(actual_pin=actual, archive=archive), after_unix_s=self.wall())
            self.completed = copy.deepcopy(actual)
            with runtime.metrics.block_restore_signals():
                pending['publication']['completed_identity'] = actual['identity']
                runtime.current_completed = copy.deepcopy(actual); runtime.pending = None
            self.state = 'COMPLETE'
        except BaseException as error:
            self.state, self.error = 'FAILED', error
        return self.result()

    def result(self):
        return dict(status=self.state, error=None if self.error is None else repr(self.error),
                    completed=copy.deepcopy(self.completed), tag=self.spec['tag'])

    def freeze(self, *, purpose='candidate', phase):
        require(self.state == 'COMPLETE' and not self.freeze_started, 'Freeze one completed snapshot exactly once')
        self.freeze_started = True
        # Seal only the new completed model. No alias/replacement can be adopted.
        descriptor = os.open(self.target, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(descriptor)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
                    and 0 < before.st_size <= MAX_MODEL and self.base.identity(before) == self.base.identity(self.target.lstat()),
                    'New snapshot is not an owned bounded single-link model')
            os.fchmod(descriptor, 0o444); os.fsync(descriptor)
            require(self.base.identity(os.fstat(descriptor)) == self.base.identity(self.target.lstat()),
                    'Snapshot path replaced while sealing')
        finally:
            os.close(descriptor)
        source, copied = self.base.exclusive_copy(self.target, self.output/'model-readonly-copy.pt')
        require(source['sha256'] == copied['sha256'] and source['bytes'] == copied['bytes'] and
                copied['identity']['mode'] == '0o444' and
                (source['identity']['device'], source['identity']['inode']) !=
                (copied['identity']['device'], copied['identity']['inode']), 'Independent readonly model copy differs')
        acquisition = dict(schema='robotron-owned-phase-snapshot-acquisition-v1', purpose=purpose,
            experiment=self.runtime.job['experiment'], model_dir=self.runtime.job['model_dir'],
            owner_before=self.owner, owner_after=self.owner_after,
            client_count=self.base.read_json(self.raw_pin)['client_count'], source_checkpoint=self.adapter.triple(source),
            clock_floor=self.floor, phase_record_sha256=phase['record']['sha256'], boot_checkpoint=phase['boot_checkpoint'],
            tag=self.spec['tag'], completed_slot_transition=self.transition, stopped_absence=None)
        self.frozen = dict(source=source, verification_copy=copied,
                           acquisition=self.base.publish(self.output/'acquisition.json', acquisition))
        return copy.deepcopy(self.frozen)


class RetainedCPU:
    """Single reviewed2 phase CPU service; authentic early_insurance profile role.

    Failure retains the original failed service and evidence. Requested unit,
    exact argv/job and the actual child owner are exposed for the controller's
    narrowly scoped competing-helper guard; no basename exemption is granted.
    """
    def __init__(self, base, *, run=command, schedule=None, clock=time.monotonic, sleep=time.sleep):
        self.base, self.run, self.clock, self.sleep = base, run, clock, sleep
        self.schedule = schedule

    def show(self, unit):
        text = self.run(['systemctl', '--user', 'show', unit])
        return dict(line.split('=', 1) for line in text.splitlines() if '=' in line), text

    def run_once(self, helper, job_pin, verifier, directory):
        base, spec = self.base, helper.spec
        base.pin(verifier['script'], base.MAX_SOURCE)
        check_python_identity(base, verifier, hash_executable=True)
        unit = spec['cpu_unit'];timer = unit.removesuffix('.service')+'.timer'
        for name in (unit, timer):
            state, _ = self.show(name)
            require(state.get('LoadState') == 'not-found', 'Early CPU unit/timer name already exists')
        numerical = [verifier['python'], '-Xgil=0', '-I', '-B', '-u', verifier['script']['path'], '--execute',
            '--job', job_pin['path'], '--expected-job-sha256', job_pin['sha256'],
            '--expected-verifier-sha256', verifier['script']['sha256']]
        argv = ['systemd-run', '--user', '--unit='+unit, '--property=Type=exec', '--property=RemainAfterExit=yes',
            '--property=Restart=no', '--property=CPUQuota=200%', '--property=MemoryMax=3G',
            '--property=MemorySwapMax=0', '--property=TasksMax=64', '--property=RuntimeMaxSec=120',
            '--property=TimeoutStopSec=5', '--property=WorkingDirectory='+helper.runtime.job['game_root'],
            '--property=StandardOutput=append:'+str(directory/'stdout.txt'),
            '--property=StandardError=append:'+str(directory/'stderr.txt'),
            '--property=UnsetEnvironment=LD_PRELOAD PYTHONPATH',
            '--setenv=CUDA_VISIBLE_DEVICES=', '--setenv=PYTHONDONTWRITEBYTECODE=1',
            '--setenv=OMP_NUM_THREADS=2', '--setenv=MKL_NUM_THREADS=2',
            '--setenv=OPENBLAS_NUM_THREADS=2', '--setenv=NUMEXPR_NUM_THREADS=2',
            '--on-active=3s', '--timer-property=AccuracySec=100ms'] + numerical
        intent = base.publish(directory/'execution-intent.json', dict(kind=EXECUTION_KIND, unit=unit, timer=timer,
            argv=argv, job=job_pin, command=numerical, only_one_attempt=True))
        helper.register_request(dict(request=intent, unit=unit, timer=timer, job=job_pin,
                                     argv=argv, command=numerical, owner=None, carrier=None,
                                     terminal_archive=None, release=None))
        # The detached scheduling carrier must return and be reaped before firing.
        launch = helper.schedule(argv) if self.schedule is None else self.schedule(helper, argv)
        carrier_done = self.clock()
        base.publish(directory/'carrier-completion.json', dict(returncode=0, stdout=launch, reaped_monotonic_s=carrier_done))
        deadline = carrier_done + spec['cpu_timeout_s'] + 8
        adopted = None
        while True:
            state, text = self.show(unit)
            if state.get('LoadState') == 'loaded' and int(state.get('ExecMainPID', '0')) > 0:
                pid = int(state['ExecMainPID'])
                require(int(state.get('ExecMainStartTimestampMonotonic', '0')) / 1000000 > carrier_done,
                        'Early CPU started before scheduling carrier reaped')
                terminal = state.get('SubState') in ('exited', 'dead', 'failed') or state.get('ActiveState') == 'failed'
                if adopted is None and not terminal and state.get('ActiveState') in ('active', 'activating'):
                    proc = Path('/proc', str(pid))
                    try:
                        fields = (proc/'stat').read_text().rsplit(')', 1)[1].split()
                        actual_argv = [os.fsdecode(value) for value in (proc/'cmdline').read_bytes().split(b'\0') if value]
                        if not actual_argv:
                            raise ProcessLookupError(errno.ESRCH, 'CPU cmdline empty at possible terminal transition')
                        require(proc.stat().st_uid == os.getuid() and (proc/'exe').resolve(strict=True) ==
                                Path(verifier['python']).resolve(strict=True) and actual_argv == numerical and
                                (proc/'stat').read_text().rsplit(')', 1)[1].split()[19] == fields[19],
                                'Retained CPU UID/executable/argv/start bracket differs')
                        adopted = dict(pid=pid, starttime_ticks=int(fields[19]), unit=unit,
                            invocation_id=state['InvocationID'], cgroup=state['ControlGroup'])
                        helper.adopt_cpu(adopted)
                    except OSError as error:
                        if error.errno not in (errno.ENOENT, errno.ESRCH):
                            raise
                        ended, ended_text = self.show(unit)
                        require(ended.get('LoadState') == 'loaded' and int(ended['ExecMainPID']) == pid and
                                ended['InvocationID'] == state['InvocationID'] and ended['NRestarts'] == '0' and
                                ended.get('SubState') in ('exited', 'dead', 'failed'),
                                'CPU disappeared without its same retained original terminal')
                        state, text, terminal = ended, ended_text, True
                        adopted = helper.registration()['owner']
                if terminal:
                    break
            require(self.clock() <= deadline, 'Retained early CPU failed to terminate within fixed bound')
            self.sleep(.1)
        if adopted is None:
            adopted = helper.registration()['owner']  # Root's exact-argv guard may have observed it first.
        if adopted is not None:
            require(state['InvocationID'] == adopted['invocation_id'] and int(state['ExecMainPID']) == adopted['pid'],
                    'Original CPU unit identity changed')
        # Archive original loaded unit and invocation while retained, before stop/reset.
        show_pin = publish_text(base, directory/'original-terminal-show.txt', text)
        cat_pin = publish_text(base, directory/'original-terminal-cat.txt', self.run(['systemctl', '--user', 'cat', unit]))
        journal_pin = publish_text(base, directory/'original-invocation-journal.txt', self.run([
            'journalctl', '--user', '--no-pager', '-o', 'short-iso-precise', '_SYSTEMD_INVOCATION_ID='+state['InvocationID']]), allow_empty_journal=True)
        completion = dict(original_invocation=state['InvocationID'], original_pid=int(state['ExecMainPID']),
            original_exec_code=int(state['ExecMainCode']), original_exit=int(state['ExecMainStatus']),
            result=state['Result'], unit_released=False, original_owner=adopted,
            original_nrestarts=int(state['NRestarts']),
            terminal_show=show_pin, terminal_cat=cat_pin, invocation_journal=journal_pin)
        completion_pin = base.publish(directory/'original-execution-completion.json', completion)
        if adopted is not None:
            helper.record_terminal(completion_pin)
        require(adopted is not None, 'Original unit archived but no independently observed CPU PID/start; no invented identity')
        require(completion['original_exec_code'] == 1 and completion['original_exit'] == 0 and completion['original_nrestarts'] == 0 and
                completion['result'] == 'success', 'Original early insurance CPU failed; retained, no retry')
        original_report = base.fingerprint(Path(base.read_json(job_pin)['output_directory'])/'cpu-verification.json', base.MAX_JSON)
        check_phase_report(base, original_report, job_pin)
        report_pin = archive_phase_report(helper, original_report, directory/'numeric-report-readonly.json')
        check_phase_report(base, report_pin, job_pin)
        before, _ = self.show(unit)
        require(before['InvocationID'] == adopted['invocation_id'] and int(before['ExecMainPID']) == adopted['pid'] and
                before['ExecMainStatus'] == '0', 'Original CPU changed before exact release')
        # A successful terminal unit is now archived; release only its exact names.
        releases = []
        for name in (timer, unit):
            actual, _ = self.show(name)
            if actual.get('LoadState') == 'not-found':
                releases.append(dict(unit=name, already_absent=True)); continue
            if name == unit:
                require(actual['InvocationID'] == adopted['invocation_id'] and int(actual['ExecMainPID']) == adopted['pid'],
                        'CPU owner changed during release')
            else:
                require(unit in actual.get('Triggers', '').split(), 'Registered timer no longer targets owned CPU unit')
            self.run(['systemctl', '--user', 'stop', name])
            after, _ = self.show(name)
            require(after.get('LoadState') == 'not-found' or after.get('ActiveState') == 'inactive',
                    'Owned CPU unit/timer did not release')
            releases.append(dict(unit=name, already_absent=False, final_load_state=after.get('LoadState')))
        reviewed = base.publish(directory/'result-review-and-release.json', dict(status='PASS', kind=EXECUTION_KIND,
            original_invocation=adopted['invocation_id'], original_pid=adopted['pid'], original_exec_code=1,
            original_exit=0, original_result='success', original_archived_before_release=True,
            numeric_report_sha256=report_pin['sha256'], original_completion=completion_pin, actual_unit=unit,
            releases=releases, original_owner=adopted))
        helper.record_release(reviewed)
        return dict(phase_cpu_report=report_pin, original_numeric_report=original_report, successful_execution=intent,
                    successful_completion=completion_pin, successful_result=reviewed)


class EarlyPhaseInsurance:
    def __init__(self, adapter, base, runtime, spec, output, *, executor=None, spawn=None,
                 clock=time.monotonic, wall=time.time, run=command):
        required={'tag','cpu_unit','save_timeout_s','cpu_timeout_s','profile','collector','python_identity','producer_expectation'}
        require(isinstance(spec,dict) and set(spec)==required and spec['cpu_timeout_s']==120 and
                spec['save_timeout_s']==60 and re.fullmatch(r'robotron-[A-Za-z0-9_-]+\.service',spec['cpu_unit'] or ''),
                'Explicit one-shot CE2048 early phase spec required')
        self.adapter,self.base,self.runtime,self.spec=adapter,ReadonlyMetadataBase(base),runtime,copy.deepcopy(spec)
        self.output=Path(output);self.clock,self.wall,self.run=clock,wall,run
        self.snapshot=Snapshot(adapter,self.base,runtime,spec,self.output/'snapshot',clock=clock,wall=wall)
        self.executor=executor or RetainedCPU(self.base,run=run,clock=clock)
        self.spawn=spawn or self._spawn
        self._lock=threading.Lock();self._result=dict(status='NEW');self._registration=None
        self.worker_started=False;self.background_attempted=False

    @staticmethod
    def _spawn(function):
        thread = threading.Thread(target=function, name='one-early-insurance', daemon=True); thread.start()
        return thread

    def register_request(self, value):
        with self._lock:
            require(self._registration is None, 'Early CPU launch is one-shot')
            self._registration = copy.deepcopy(value)

    def adopt_cpu(self, owner):
        with self._lock:
            require(self._registration is not None and set(owner) == OWNER_KEYS and
                    owner['unit'] == self._registration['unit'] and owner['pid'] > 0 and owner['starttime_ticks'] > 0 and
                    re.fullmatch('[0-9a-f]{32}', owner['invocation_id'] or '') and owner['cgroup'], 'Actual registered CPU identity required')
            previous = self._registration['owner']
            require(previous is None or previous == owner, 'Never adopt replacement early CPU')
            self._registration['owner'] = copy.deepcopy(owner)

    def registration(self):
        with self._lock:
            return copy.deepcopy(self._registration)

    def record_terminal(self, pin):
        value = self.base.read_json(pin)
        require(pin['identity']['mode'] == '0o444' and pin['identity']['uid'] == os.getuid() and
                pin['identity']['nlink'] == 1, 'Readonly owned original CPU terminal archive required')
        with self._lock:
            owner = self._registration['owner']
            require(owner is not None and value['original_owner'] == owner and
                    value['original_pid'] == owner['pid'] and value['original_invocation'] == owner['invocation_id'] and
                    self._registration['terminal_archive'] is None, 'Original CPU terminal does not join registered actual owner')
            self._registration['terminal_archive'] = copy.deepcopy(pin)

    def record_release(self, pin):
        value = self.base.read_json(pin)
        with self._lock:
            owner = self._registration['owner']
            require(self._registration['terminal_archive'] is not None and self._registration['release'] is None and
                    value['original_completion'] == self._registration['terminal_archive'] and
                    value['original_owner'] == owner and value['actual_unit'] == owner['unit'] and
                    value['original_archived_before_release'] is True and value['original_exit'] == 0,
                    'Exact CPU release lacks its immutable original terminal proof')
            self._registration['release'] = copy.deepcopy(pin)

    def schedule(self, argv):
        # The scanner refreshes registration INSIDE each classified PID branch.
        # It waits for this short birth-registration critical section, rather
        # than seeing a child whose exact start identity has not been recorded.
        with self._lock:
            require(self._registration is not None and not self._registration.get('carrier_attempted', False),
                    'One registered detached scheduling carrier only')
            self._registration['carrier_attempted'] = True
            process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                fields = Path('/proc', str(process.pid), 'stat').read_text().rsplit(')', 1)[1].split()
                self._registration['carrier'] = dict(pid=process.pid, starttime_ticks=int(fields[19]),
                                                      argv=list(argv), reaped=False)
            except BaseException as error:
                self._registration['carrier_birth_error'] = repr(error)
                try:
                    if process.poll() is None:
                        process.terminate()
                    process.communicate(timeout=2)
                except BaseException as cleanup:
                    self._registration['carrier_birth_cleanup_error'] = repr(cleanup)
                raise
        try:
            stdout, stderr = process.communicate(timeout=2)
            require(process.returncode == 0, 'Original scheduling carrier failed: '+stderr[:1024])
            return stdout
        except BaseException:
            try:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=2)
            except BaseException as cleanup:
                with self._lock:
                    self._registration['carrier']['cleanup_error'] = repr(cleanup)
            raise
        finally:
            with self._lock:
                self._registration['carrier']['reaped'] = process.returncode is not None
                self._registration['carrier']['returncode'] = process.returncode

    def result(self):
        with self._lock:
            return copy.deepcopy(self._result)

    def start(self):
        require(self.result()['status'] == 'NEW', 'Early insurance cannot be restarted')
        with self._lock:
            self._result = dict(status='PENDING', phase='prepare')
        try:
            return self._start()
        except BaseException as error:
            with self._lock:
                self._result = dict(status='FAILED', phase='prepare', error=repr(error), traceback=traceback.format_exc())
            raise

    def _start(self):
        # Explicit root selection only; an unresolved external source cannot act.
        self.collector=load_collector(self.base,self.spec['collector'])
        self.profile=checked_profile(self.base,self.spec['profile'])
        family=self.runtime.job['phase_verifier2048']
        require({k:self.adapter.triple(family[k]) for k in ('script','strict_base')}==CPU_FAMILY,
                'Wrong exact reviewed2 CPU family')
        for value in family.values():self.base.pin(value,self.base.MAX_SOURCE)
        self.verifier=dict(script=copy.deepcopy(family['script']),strict_base=copy.deepcopy(family['strict_base']),
            python=self.runtime.job['verifier']['python'],python_identity=copy.deepcopy(self.spec['python_identity']))
        check_python_identity(self.base,self.verifier,hash_executable=True)
        self.output.mkdir(mode=0o700)
        raw=self.runtime.raw_api()
        require(raw['client_count']==192 and raw['training_enabled'] is True and not raw.get('measurement_active',False),
                'Early phase insurance requires genuinely active192, no pause')
        self.owner=copy.deepcopy(self.runtime.trainer_id());self.runtime.inspect('after')
        require(self.runtime.record['metric']==self.runtime.record['previous_metric']=='ce' and
                self.runtime.record['action']=='start','Only fresh treatment CE->CE phase accepted')
        pairs,self.context=self.runtime.phase_sources('early-phase-insurance2048')
        self.pairs=copy.deepcopy(pairs);self.source_pairs=self.base.publish(self.output/'source-archive-pairs.json',pairs)
        self.context['held_recipe_context']=copy.deepcopy(self.profile['held_recipe_context'])
        phase=dict(record=copy.deepcopy(self.runtime.record_pin),
            boot_checkpoint=self.adapter.triple(self.runtime.current_checkpoint['source']),
            boot_verification=copy.deepcopy(self.runtime.current_checkpoint['verification']),
            expected=self.adapter.expected_start(self.runtime.record,self.runtime.record_pin,
                self.base.read_json(self.runtime.current_checkpoint['verification'])))
        self.phase,self.context,archives=self.adapter.phase_metadata(self.base,phase,self.context,self.output/'metadata')
        self.base.publish(self.output/'metadata-archives.json',archives)
        expectation=readonly_json(self.base,self.spec['producer_expectation'])
        require(set(expectation)=={'schema','owner','boot_id','argv','cwd','exe','environment'} and
                expectation['schema']=='robotron-root-CE2048-producer-expectation-v1' and expectation['owner']==self.owner,
                'Actual selected new-owner producer expectation required')
        env=self.adapter.selected_environment(self.runtime.job['before']['environment'],
            self.runtime.job['batch_boundary'],self.runtime.record_pin)
        env={k:v for k,v in env.items() if k.startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_'))}
        require(expectation['environment']==env and env.get('DQN_BATCH_SIZE')=='2048' and
                env.get('DQN_PER_PRIORITY_METRIC')=='ce','Expected actual CE2048 environment differs')
        owner_pin=self.base.publish(self.output/'owner.json',self.owner)
        self.collector_spec=dict(schema='robotron-batch2048-producer-live-capture-spec-v1',profile=self.spec['profile'],
            owner=self.owner,owner_pin=owner_pin,phase_record=self.phase['record'],boot_verification=self.phase['boot_verification'],
            source_pins={name:pair['current'] for name,pair in pairs.items()},game_root=self.runtime.job['game_root'],
            environment=env,argv=expectation['argv'],cwd=expectation['cwd'],exe=expectation['exe'],
            experiment=self.runtime.job['experiment'],boot_id=expectation['boot_id'])
        self.snapshot.start(raw,self.adapter.four(raw))
        require(self.snapshot.owner==self.owner,'Early owner changed across request publication')
        with self._lock:self._result=dict(status='PENDING',phase='managed-save')
        return self.result()

    def tick(self):
        if self.result()['status']!='PENDING' or self.worker_started:return self.result()
        state=self.snapshot.tick()
        if state['status']=='FAILED':
            with self._lock:self._result=dict(status='FAILED',error=state['error'],phase='managed-save')
        elif state['status']=='COMPLETE':
            self.worker_started=True
            try:self.worker=self.spawn(self._background)
            except BaseException as error:
                with self._lock:self._result=dict(status='FAILED',phase='background-dispatch',error=repr(error))
        return self.result()

    def _background(self):
        with self._lock:
            require(not self.background_attempted,'One background acquisition/CPU attempt only')
            self.background_attempted=True
        try:
            # Independent read-only producer collection occurs while owner is live.
            # Neither collector nor worker calls runtime.inspect/static/API methods.
            capture=self.collector.capture_live(self.collector_spec,self.output/'producer-live-capture')
            frozen=self.snapshot.freeze(purpose='candidate',phase=self.phase)
            # FINAL real acquisition is already durably published by freeze.
            producer=self.collector.bind_capture(capture,frozen['source'],frozen['acquisition'],self.output/'producer-binding')
            saved=self.base.publish(self.output/'saved-early-phase-receipt.json',dict(
                schema='robotron-owned-CE2048-early-phase-snapshot-v1',role='early_insurance',tag=self.spec['tag'],
                trainer=self.owner,source=frozen['source'],copy=frozen['verification_copy'],trigger=self.snapshot.raw_pin,
                acquisition=frozen['acquisition'],completed_request=self.snapshot.transition['after']['archive'],
                producer_capture=capture,producer_observation=producer,phase_record=self.phase['record'],
                no_trainer_actor_stop_or_recipe_source_change=True,eligible_quality_candidate=False))
            context=copy.deepcopy(self.context)
            context['provenance']=list(context.get('provenance',[]))+[self.source_pairs,self.snapshot.raw_pin,saved,
                self.snapshot.transition['request']['archive'],self.snapshot.transition['after']['archive'],
                self.phase['record'],self.phase['boot_verification'],self.spec['producer_expectation'],capture,producer]
            job=phase_job(self.adapter,self.base,self.runtime.job['experiment'],self.owner,self.phase,self.pairs,
                          context,frozen,self.snapshot.floor,self.spec['profile'],producer,self.output/'cpu-output')
            jp=self.base.publish(self.output/'CPU-phase-job.json',job)
            execution_dir=self.output/'CPU-execution';execution_dir.mkdir(mode=0o700)
            proof=self.executor.run_once(self,jp,self.verifier,execution_dir)
            check_phase_provenance(self.base,self.verifier,jp,proof)
            check_python_identity(self.base,self.verifier,hash_executable=False)
            result=dict(schema=RESULT_SCHEMA,status='PASS',role='early_insurance',tag=self.spec['tag'],owner=self.owner,
                phase_cpu_report=proof['phase_cpu_report'],saved_receipt=saved,phase_cpu_job=jp,cpu_provenance=proof,
                python_identity=copy.deepcopy(self.verifier['python_identity']),python=self.verifier['python'],
                frozen=frozen,producer_capture=capture,producer_observation=producer,phase=copy.deepcopy(self.phase),
                profile=self.spec['profile'],eligible_quality_candidate=False,legacy_7d_insurance=False)
            result_pin=self.base.publish(self.output/'result.json',result)
            with self._lock:self._result=dict(result,result_pin=result_pin)
        except BaseException as error:
            failure=dict(status='FAILED',phase='freeze-or-first-phase-CPU',error=repr(error),traceback=traceback.format_exc())
            try:self.base.publish(self.output/'early-phase-insurance-failure.json',failure)
            except BaseException as reporting:failure['reporting_error']=repr(reporting)
            with self._lock:self._result=failure


def main():
    print('PLAN_ONLY_UNCONSUMED: explicit root-owned CE2048 phase adapter and frozen collector required; no reads/imports/actions')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
