"""One exact-owner save request, with an independent bounded recovery watcher.

Uses the already tested startup_save_pause/thaw helpers. Producer files retain
their normal modes; only separate archives are sealed. No action by default.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from types import SimpleNamespace
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
P = G/'logs/managed-learning-20261015/run-26/post-production-profile06-fresh-main-next8M-original01-preparation-20261021'
DESIGN_SHA = 'bdb43d83e65b81722ed4b5c3369752cb4570290df6c39248d6aba251b6ca5c90'
PAUSE_SHA = '0756488a19bf653a068aec8c9d3def26605b06498718621e9dc9a8a634f37b3c'
LINUX_SHA = '3c0a54a589e6790865b1dcecc1a0bf6e1f662b204155c7bf767a1d8b579f7de2'


def require(value, message):
    if not value:
        raise ValueError(message)


def full_pin(path):
    path = Path(path)
    def identity(s):
        return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,
            mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
            mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and not path.is_symlink()
        and before.st_uid == os.getuid() and before.st_nlink == 1,'Owned single regular file required')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream,'sha256').hexdigest()
    require(identity(path.lstat()) == identity(before),'File changed during pin')
    return dict(path=str(path),sha256=digest,bytes=before.st_size,identity=identity(before))


def checked(entry):
    require(full_pin(entry['path']) == entry,'Original full8 input changed')
    raw = Path(entry['path']).read_bytes()
    require(len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256'],
        'Original bytes changed after pin')
    return raw


def load(entry,name):
    checked(entry)
    spec = importlib.util.spec_from_file_location(name,entry['path'])
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    checked(entry)
    return module


def publish(path,value):
    raw = value if isinstance(value,bytes) else (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o444)
    return full_pin(path)


def mutable_state(path,value):
    path = Path(path);temporary = path.with_name(path.name+'.tmp')
    raw = (json.dumps(value,allow_nan=False)+'\n').encode()
    with temporary.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o664)
    os.replace(temporary,path)
    descriptor = os.open(path.parent,os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def validate_scope(job):
    require(job['schema'] == 'robotron-one-owned-candidate-save-v1','Unknown capture job')
    require(job['linux']['sha256'] == LINUX_SHA and job['pause_source']['sha256'] == PAUSE_SHA,
        'Use the original tested kernel primitives')
    require(job['design']['sha256'] == DESIGN_SHA,'Prospective design changed')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',job['tag']) is not None,'Invalid checkpoint tag')
    if job['mode'] == 'production':
        require(job['case'] == 'profile06-candidate-save-original01-20261021'
            and job['owner']['pid'] == 3295795 and job['owner']['starttime_ticks'] == 64995335
            and job['owner']['invocation_id'] == '160d2b4b1f6e4e2f8839790658a7d01c'
            and job['owner']['unit'] == 'robotron-managed-run-26-d3b365c9-trainer.service'
            and Path(job['model_dir']) == G/'models_dqn'
            and Path(job['capture_output']) == P/'capture-original01'
            and Path(job['rescue_output']) == P/'capture-rescue-original01'
            and job['tag'] == 'profile06_LR25_next8M_01_20261021','Foreign production capture scope')
        prefix = 'robotron-profile06-candidate-save-original01-20261021'
    else:
        require(job['mode'] == 'private_kernel_fixture','Unknown execution mode')
        require(job['fixture_variant'] in ('success','loss'),'Unknown private fixture variant')
        root = P/'capture-wrapper-kernel-original02'/job['fixture_variant']
        prefix = 'robotron-profile06-owned-save-kernel-original02-20261021-'+job['fixture_variant']
        require(job['case'] == prefix.removeprefix('robotron-')
            and Path(job['model_dir']) == root/'work/models'
            and Path(job['capture_output']) == root/'capture-output'
            and Path(job['rescue_output']) == root/'rescue-output'
            and job['owner']['unit'] == prefix+'-fleet.service','Foreign private fixture scope')
    require(job['controller_unit'] == prefix+'-capture.service'
        and job['rescue_unit'] == prefix+'-rescue.service','Capture/rescue unit scope differs')
    require(job['controller_argv_prefix'][:3] == ['/usr/bin/python3.12','-I','-B']
        and job['controller_argv_prefix'][-3:] == ['--job',job['job_path'],'--expected-job-sha256'],
        'Original controller argument scope differs')


def eligible_exposure(baseline,trigger,owner):
    require(baseline['optimizer_identity'] == trigger['optimizer_identity']
        and baseline['replay_identity'] == trigger['replay_identity']
        and trigger['optimizer_identity']['process_id'] == trigger['replay_identity']['process_id'] == owner['pid'],
        'Original window exposure owner/epoch changed')
    require(trigger['clocks']['learner_frame_count']-baseline['clocks']['learner_frame_count'] >= 8_000_000
        and trigger['learner_accepted']-baseline['learner_accepted'] >= 8_000_000,
        'Both original prospective8M horizons are required')


def dependencies(job):
    validate_scope(job)
    for entry in [job['design'],job['source'],job['controller_source'],job['linux'],job['pause_source']]:
        checked(entry)
    linux = load(job['linux'],'_capture_owned_linux')
    pause = load(job['pause_source'],'_capture_owned_pause')
    if job['mode'] == 'production':
        design = json.loads(checked(job['design']))
        require(job['main_binding'] == design['current_main_binding']
            and job['counter_module'] == design['counter_module'],'Original production window inputs differ')
        binding = json.loads(checked(job['main_binding']))
        require(binding['owner'] == job['owner'],'Original production save owner differs')
        require(job['main_guard']['sha256'] == 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3',
            'Original readonly main guard required')
        guard = load(job['main_guard'],'_capture_production_guard')
        guard.owner_and_files(binding)
        counter = load(job['counter_module'],'_capture_original_counters')
        baseline = counter.normalise(json.loads(checked(job['baseline_API'])))
        trigger = counter.normalise(json.loads(checked(job['trigger_API'])))
        eligible_exposure(baseline,trigger,job['owner'])
        latch = json.loads(checked(job['latch']))
        require(latch['status'] == 'LATCH' and latch['API'] == job['trigger_API']
            and latch['progress']['both_horizons'] is True,'Original first-eligible latch differs')
    return linux,pause


def identity(linux,unit,*,pid=None):
    fields = linux.show(unit);actual = int(fields.get('MainPID','0'))
    require(actual > 0 and (pid is None or actual == pid),'Original unit has no matching live owner')
    owner = dict(pid=actual,starttime_ticks=linux.process_start(actual),unit=unit,
        invocation_id=fields['InvocationID'],cgroup=fields['ControlGroup'])
    linux.live_owner(owner)
    require(fields['NRestarts'] == '0','Original process restarted')
    return owner


def command_matches(owner,prefix,job_sha):
    actual = [x.decode() for x in Path('/proc',str(owner['pid']),'cmdline').read_bytes().split(b'\0') if x]
    require(actual == prefix+[job_sha],'Original process command differs')


def rescue_state(job,state,original,linux,pause):
    require(state['schema'] == 'robotron-one-owned-save-state-v1'
        and state['case'] == job['case'] and state['controller'] == original
        and state['save_owner'] == job['owner'],'Foreign save recovery state')
    selected = state['paused_owner']
    require(selected is None or selected == job['owner'],'Foreign recorded pause owner')
    if selected is None:
        return dict(status='NO_RECORDED_SAVE_HOLD',runtime_changed=False)
    result = pause.thaw_startup_save(linux,selected)
    return dict(status='EXACT_RECORDED_SAVE_OWNER_THAWED',runtime_changed=True,thaw=result)


def controller_alive(linux,owner):
    """An original may exit between its proc birth read and unit observation."""
    if linux.process_start(owner['pid']) != owner['starttime_ticks']:
        return False
    try:
        linux.live_owner(owner)
        return True
    except RuntimeError:
        if linux.process_start(owner['pid']) != owner['starttime_ticks']:
            return False
        fields = linux.show(owner['unit'])
        if (fields.get('MainPID') == '0' and fields.get('InvocationID') == owner['invocation_id']
            and fields.get('ExecMainPID') == str(owner['pid']) and fields.get('NRestarts') == '0'
            and fields.get('ExecMainCode') in ('1','2','3')):
            return False
        raise


def watch(job,job_sha):
    linux,pause = dependencies(job);out = Path(job['rescue_output']);out.mkdir(mode=0o700)
    owner = identity(linux,job['rescue_unit'],pid=os.getpid())
    own_prefix = ['/usr/bin/python3.12','-I','-B',job['source']['path'],'--watch','--job',job['job_path'],'--expected-job-sha256']
    command_matches(owner,own_prefix,job_sha)
    publish(out/'owner.json',owner);publish(out/'ready.json',dict(owner=owner,job_sha256=job_sha))
    original = None;created = time.monotonic();result = None
    try:
        while time.monotonic()-created < 120:
            if original is None:
                fields = linux.show(job['controller_unit'])
                if int(fields.get('MainPID','0')):
                    original = identity(linux,job['controller_unit'])
                    command_matches(original,job['controller_argv_prefix'],job_sha)
                    publish(out/'original-controller-birth.json',original)
                elif time.monotonic()-created > 20:
                    raise RuntimeError('Original capture controller did not start')
            else:
                alive = controller_alive(linux,original)
                path = Path(job['capture_output'])/'save-publication-state.json'
                state = json.loads(path.read_bytes()) if path.exists() else None
                if state is not None:
                    require(state['case'] == job['case'] and state['controller'] == original
                        and state['save_owner'] == job['owner'],'Foreign observed save state')
                expired = state is not None and state['paused_owner'] is not None and time.monotonic() > state['deadline_monotonic_s']
                if not alive or expired:
                    recovery = rescue_state(job,state,original,linux,pause) if state is not None else dict(
                        status='NO_STATE_NO_HOLD_WAS_RECORDED',runtime_changed=False)
                    result = dict(status='ORIGINAL_CONTROLLER_EXIT_OBSERVED' if not alive else 'SAVE_HOLD_DEADLINE_RECOVERED',
                        original_controller=original,controller_alive=alive,recovery=recovery,
                        original_exit_not_normalized=True,restart_retry=False)
                    break
            time.sleep(.03)
        require(result is not None,'Bounded independent save watch expired')
        publish(out/'result.json',result)
        return 0 if result['controller_alive'] is False else 1
    except BaseException as error:
        # The selected hold cannot precede its durable state. A final bounded
        # exact-owner release also covers watcher errors after recording it.
        result = dict(status='ORIGINAL_WATCH_FAILURE_PRESERVED',error=repr(error),restart_retry=False)
        path = Path(job['capture_output'])/'save-publication-state.json'
        if original is not None and path.exists():
            try:result['recovery'] = rescue_state(job,json.loads(path.read_bytes()),original,linux,pause)
            except BaseException as recovery_error:result['recovery_error'] = repr(recovery_error)
        publish(out/'result.json',result)
        return 1


def wait_rescue(job,job_sha,linux,controller):
    out = Path(job['rescue_output']);deadline = time.monotonic()+15
    while time.monotonic()<deadline:
        ready = out/'ready.json';birth = out/'original-controller-birth.json'
        if ready.exists() and birth.exists():
            value = json.loads(ready.read_bytes());observed = json.loads(birth.read_bytes())
            require(value['job_sha256'] == job_sha and observed == controller,'Foreign original capture watch')
            linux.live_owner(value['owner'])
            require(value['owner']['unit'] == job['rescue_unit'],'Unexpected original rescue unit')
            return full_pin(ready),full_pin(birth)
        time.sleep(.03)
    raise RuntimeError('Original independent rescue did not capture this controller')


def capture(job,job_sha,*,after_frozen=None):
    linux,pause = dependencies(job);out = Path(job['capture_output']);out.mkdir(mode=0o700)
    controller = identity(linux,job['controller_unit'],pid=os.getpid())
    command_matches(controller,job['controller_argv_prefix'],job_sha)
    linux.live_owner(job['owner'])
    state = dict(schema='robotron-one-owned-save-state-v1',case=job['case'],controller=controller,
        save_owner=job['owner'],paused_owner=None,stage='waiting_for_independent_rescue',deadline_monotonic_s=time.monotonic()+15)
    mutable_state(out/'save-publication-state.json',state)
    def persist():
        state.update(paused_owner=adapter.startup_save_paused_owner,
            stage='exact_owner_hold_recorded' if adapter.startup_save_paused_owner else 'exact_owner_hold_released',
            deadline_monotonic_s=time.monotonic()+10)
        mutable_state(out/'save-publication-state.json',state)
        if adapter.startup_save_paused_owner is not None:
            publish(out/'original-state-before-kernel-hold.json',dict(state))
    adapter = SimpleNamespace(linux=linux,startup_save_paused_owner=None,b=SimpleNamespace(state=persist))
    try:
        ready,birth = wait_rescue(job,job_sha,linux,controller)
        if job['mode'] == 'production':
            guard = load(job['main_guard'],'_capture_last_main_guard')
            binding = json.loads(checked(job['main_binding']))
            guard.owner_and_files(binding)
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:
                api = json.loads(response.read(2<<20))
            guard.healthy(api,json.loads(checked(binding['baseline_API'])),binding['experiment'],time.time())
        model = Path(job['model_dir']);request = model/'managed_save.request.json'
        slot = request.with_name(request.name+'.completed');source = model/'managed-checkpoints'/(job['tag']+'.pt')
        require(not request.exists() and not source.exists(),'A save request or unique tag already exists')
        before = None if not slot.exists() else dict(actual_pin=full_pin(slot),archive=publish(out/'completed-slot-before.json',slot.read_bytes()))
        staging = request.with_name(request.name+'.'+job['case']+'.tmp')
        raw = (json.dumps(dict(tag=job['tag']))+'\n').encode();staged = publish(staging,raw)
        request_archive = publish(out/'request-original.json',raw)
        started = time.time()
        with pause.startup_save_pause(adapter,job['owner']) as group:
            linux.live_owner(json.loads(checked(ready))['owner'])
            require(dict(line.split() for line in (group/'cgroup.events').read_text().splitlines())['frozen']=='1',
                'Exact owner was not kernel frozen')
            require(time.monotonic()<state['deadline_monotonic_s'],'Original hold deadline passed')
            if after_frozen is not None:after_frozen(group)
            request_pin = pause.publish_request_exclusive(linux,staging,request)
            requested_at = time.time()
        publication = publish(out/'request-publication.json',dict(owner=job['owner'],controller=controller,
            rescue_ready=ready,original_watch_capture=birth,request=request_pin,request_archive=request_archive,
            original_staging=staged,hold_started_unix_s=started,request_unix_s=requested_at,
            hold_released_unix_s=time.time(),original_state_before_hold=full_pin(out/'original-state-before-kernel-hold.json')))
        deadline = time.monotonic()+60
        while time.monotonic()<deadline:
            linux.live_owner(job['owner'])
            if not request.exists() and source.exists() and slot.exists() and json.loads(slot.read_bytes())==dict(tag=job['tag']):break
            time.sleep(.03)
        else:raise RuntimeError('One original managed request has not completed; no retry')
        producer = full_pin(source)
        require(producer['identity']['mode'] == '0o664','Normal checkpoint producer mode differs')
        archive = pause.archive(linux,source,out/'candidate-readonly.pt')
        require(full_pin(source)==producer and archive['sha256']==producer['sha256'],'Independent candidate copy differs')
        after = dict(actual_pin=full_pin(slot),archive=publish(out/'completed-slot-after.json',slot.read_bytes()))
        result = dict(status='ORIGINAL_CAPTURE_ARCHIVED_NORMAL_PRODUCER_PRESERVED',owner=job['owner'],controller=controller,
            source=producer,checkpoint=archive,publication=publication,completed_slot_transition=dict(before=before,after=after),
            original_request_retried=False,normal_producer_mode_preserved=True,CPU_verified=False,
            quality_qualified=False,promotion=False,learning_speed_gain_verified=False)
        publish(out/'result.json',result)
        return 0
    except BaseException as error:
        publish(out/'result.json',dict(status='ORIGINAL_CAPTURE_FAILURE_PRESERVED',error=repr(error),
            owner=job['owner'],controller=controller,original_request_retried=False,promotion=False))
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',action='store_true');parser.add_argument('--watch',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--expected-job-sha256')
    args = parser.parse_args(argv)
    if not (args.capture or args.watch):
        print('PLAN_ONLY: no reads, outputs, save requests or runtime actions');return 0
    require(args.capture is not args.watch and args.job and args.expected_job_sha256,'One exact job and action required')
    entry = full_pin(args.job)
    require(entry['sha256']==args.expected_job_sha256 and entry['identity']['mode']=='0o444','Original sealed job differs')
    job = json.loads(checked(entry));require(Path(job['job_path'])==args.job.resolve(),'Original job pathname differs')
    require(Path(job['source']['path'])==Path(__file__).resolve(),'Use the exact selected capture source')
    return capture(job,entry['sha256']) if args.capture else watch(job,entry['sha256'])


if __name__ == '__main__':
    raise SystemExit(main())
