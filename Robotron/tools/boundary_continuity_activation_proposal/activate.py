"""One controlled newest-state activation of the tested score-continuity predicate.

Default invocation is read-free. The explicit job pins the running owner, actor
set, released comparison, regression proof, source transaction and CPU helpers.
No protected policy is loaded, no replay is cleared, and starts are never retried.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback
import urllib.request

ROOT = Path('/home/dave/source/repos/ArcadeAI')
GAME = ROOT/'Robotron'
MODEL = GAME/'models_dqn'
LATEST = MODEL/'robotron_dqn_latest.pt'
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def pin(path):
    path = Path(path)
    before = path.lstat()
    require(path.is_file() and not path.is_symlink() and before.st_nlink == 1, 'Single regular file required')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.lstat()
    def identity(s):
        return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                    ctime_ns=s.st_ctime_ns, mode=oct(s.st_mode & 0o777), uid=s.st_uid, nlink=s.st_nlink)
    require(identity(before) == identity(after), 'File changed during fingerprint')
    return dict(path=str(path), sha256=digest, bytes=after.st_size, identity=identity(after))


def checked(value):
    require(pin(value['path']) == value, 'Pinned file changed: '+value['path'])
    return Path(value['path']).read_bytes()


def publish(path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    return pin(path)


def archive(path, destination):
    before = pin(path)
    with Path(path).open('rb') as source, Path(destination).open('xb') as target:
        shutil.copyfileobj(source, target, 1 << 20)
        target.flush(); os.fchmod(target.fileno(), 0o444); os.fsync(target.fileno())
    result = pin(destination)
    require(pin(path) == before and result['sha256'] == before['sha256'], 'Archive source moved')
    return result


def starttime(pid):
    try:
        raw = Path('/proc', str(pid), 'stat').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return int(raw.rsplit(')', 1)[1].split()[19])


def signal_actor(actor, number):
    require(starttime(actor['pid']) == actor['starttime_ticks'], 'Actor identity changed before signal')
    require(sorted(os.sched_getaffinity(actor['pid'])) == actor['mask'], 'Actor affinity changed')
    os.kill(actor['pid'], number)


def stopped(actor):
    require(starttime(actor['pid']) == actor['starttime_ticks'], 'Original actor disappeared')
    return Path('/proc', str(actor['pid']), 'stat').read_text().rsplit(')', 1)[1].split()[0] in ('T', 't')


def show(unit):
    r = subprocess.run(['systemctl', '--user', 'show', unit, '--all'], capture_output=True, text=True,
                       timeout=20, check=True)
    return dict(line.split('=', 1) for line in r.stdout.splitlines() if '=' in line)


def api():
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        return json.load(response)


def load(value, name):
    checked(value)
    spec = importlib.util.spec_from_file_location(name, value['path'])
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    require(pin(value['path']) == value, 'Helper changed while importing')
    return module


def resume_record(saved_phase, checkpoint):
    require(saved_phase['metric'] == 'ce' and saved_phase['valid'] is True, 'Valid saved CE phase required')
    return dict(schema='robotron-priority-metric-start-v1', phase_id=saved_phase['phase_id'], metric='ce',
                action='resume', previous_metric='ce', checkpoint=checkpoint, model_dir=str(MODEL),
                root_precommit_sha256=saved_phase['root_precommit_sha256'])


class Activation:
    def __init__(self, job):
        self.job = job; self.out = Path(job['output']); self.out.mkdir(mode=0o700)
        self.paused = []; self.commands = 0; self.cpu_attempts = 0
        self.result = dict(status='PREPARING', production_applied=False, start_attempts=0,
                           rollback=False, protected_policy_loaded=False, replay_cleared=False)

    def event(self, name, value):
        return publish(self.out/name, value)

    def command(self, argv, *, timeout=40):
        self.commands += 1
        r = subprocess.run(argv, capture_output=True, timeout=timeout)
        prefix = f'command-{self.commands:03}'
        self.event(prefix+'-stdout.txt', r.stdout); self.event(prefix+'-stderr.txt', r.stderr)
        self.event(prefix+'.json', dict(argv=argv, exit=r.returncode, unix_s=time.time()))
        require(r.returncode == 0, 'Owned command failed: '+repr(argv))

    def wait(self, predicate, seconds, message):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(1)
        raise RuntimeError(message)

    def identity(self, owner):
        value = show(owner['unit'])
        require(value['MainPID'] == str(owner['pid']) and value['InvocationID'] == owner['invocation_id']
                and value['NRestarts'] == '0' and value['SubState'] == 'running'
                and starttime(owner['pid']) == owner['starttime_ticks'], 'Original live owner changed')

    def context(self):
        j = self.job
        for item in j['pins']: checked(item)
        release = json.loads(checked(j['quality_release']))
        require(release['source_freeze_released'] is True and release['quality_qualification'] is False,
                'Actual prior invalid comparison must be disposed and released')
        proof = json.loads(checked(j['integration_proof']))
        require(proof['tests'] == 2 and proof['original_child_exits'] == [0, 0]
                and proof['production_patch_applied'] is False, 'Original private integration proof required')
        self.identity(j['anchor']['main_owner']); self.identity(j['anchor']['fleet_owner'])
        require(len(j['anchor']['actors']) == 192, 'Original192 required')
        for actor in j['anchor']['actors']:
            require(not stopped(actor), 'An actor is already stopped')
        require(not (MODEL/'managed_save.request.json').exists(), 'Existing save request must finish')
        raw = api()
        self.health = load(j['health_helper'], '_activation_main_health')
        self.health.main_health_contract(raw, json.loads(checked(j['baseline_API'])),
                                         j['anchor']['main_owner']['pid'], time.time())
        self.event('before-main-API.json', raw)
        self.floor = {k:raw[k] for k in CLOCKS}
        self.banks = load(j['bank_helper'], '_activation_banks')
        self.template = json.loads(checked(j['cpu_template']))

    def cpu(self, purpose, source, owner, phase, boot, boot_proof, expected, acquisition):
        directory = self.out/purpose; directory.mkdir()
        source_pin = pin(source); copied = archive(source, directory/'model-readonly.pt')
        job = copy.deepcopy(self.template)
        job.update(source=source_pin, verification_copy=copied, clock_floor=dict(self.floor),
                   output_directory=str(directory/'cpu-output'))
        acquisition.update(schema='robotron-owned-phase-snapshot-acquisition-v1', purpose=purpose,
            experiment=job['experiment'], model_dir=str(MODEL), owner_before=owner, owner_after=owner,
            client_count=192 if purpose == 'newest_stopped' else 0,
            source_checkpoint={k:source_pin[k] for k in ('path','sha256','bytes')},
            clock_floor=dict(self.floor), phase_record_sha256=phase['sha256'], boot_checkpoint=boot)
        acquisition_pin = self.event(purpose+'/acquisition.json', acquisition)
        job['phase_snapshot'].update(purpose=purpose, owner=owner,
            observed_clients=192 if purpose == 'newest_stopped' else 0, phase_record=phase,
            boot_checkpoint=boot, boot_verification=boot_proof, expected_phase=expected, acquisition=acquisition_pin)
        job_pin = self.event(purpose+'/CPU-job.json', job)
        self.cpu_attempts += 1
        config = dict(unit=f'robotron-boundary-activation-{purpose.replace("_","-")}-cpu-original01-20261018.service',
            output=str(directory/'cpu-execution'),
            argv=[self.job['python'], '-Xgil=0', '-I', '-B', self.job['verifier']['path'], '--execute',
                  '--job', job_pin['path'], '--expected-job-sha256', job_pin['sha256'],
                  '--expected-verifier-sha256', self.job['verifier']['sha256']],
            properties=['CPUQuota=200%','MemoryMax=4G','RuntimeMaxSec=180','MemorySwapMax=0',
                        'TasksMax=128','TimeoutStopSec=5'],
            pins=[], observation_s=240)
        # The existing bounded controller pins its own source; the verifier checks
        # every job/source/archive and newest-stopped owner absence itself.
        for value in [self.job['cpu_controller'], self.job['verifier'], job_pin]:
            item = copy.deepcopy(value)
            item['identity'] = {k:v for k,v in item['identity'].items()
                                if k in ('device','inode','mode','uid','nlink')}
            config['pins'].append(item)
        config_pin = self.event(purpose+'/CPU-controller-config.json', config)
        controller = self.job['cpu_controller']
        self.command(['/usr/bin/python3.12','-I','-B',controller['path'],'--execute','--config',config_pin['path'],
                      '--expected-source-sha256',controller['sha256']], timeout=300)
        lifecycle = json.loads((directory/'cpu-execution/root-original-result-and-owned-release.json').read_text())
        require(lifecycle['original_exit'] == 0 and lifecycle['lifecycle_complete'], 'CPU proof failed or lifecycle incomplete')
        report = json.loads((directory/'cpu-output/cpu-verification.json').read_text())
        require(report['status'] == 'PASS' and report['phase_metadata_verified'] is True, 'Strict phase CPU failed')
        report_pin = archive(directory/'cpu-output/cpu-verification.json', directory/'CPU-report-readonly.json')
        self.event(purpose+'/CPU-PASS.json', dict(report=report_pin, lifecycle=lifecycle))
        return report, report_pin, source_pin

    def stop(self):
        j = self.job; old = j['anchor']['main_owner']
        for actor in j['anchor']['actors']:
            self.paused.append(actor); signal_actor(actor, signal.SIGSTOP)
        self.wait(lambda: all(stopped(a) for a in self.paused), 15, 'Actors did not stop')
        self.identity(old)
        self.event('original-before-stop-show.json', show(old['unit']))
        self.command(['systemctl','--user','stop','--no-block',old['unit']])
        def retired():
            value = show(old['unit'])
            return value['MainPID'] == '0' and starttime(old['pid']) != old['starttime_ticks']
        self.wait(retired, 240, 'Original trainer has not retired; no source write authorized')
        value = show(old['unit'])
        require(value['ActiveState'] == 'inactive' and value['ExecMainPID'] == str(old['pid'])
                and value['ExecMainCode'] == '1' and value['ExecMainStatus'] == '0'
                and value['NRestarts'] == '0', 'Original shutdown did not exit0')
        group = Path('/sys/fs/cgroup'+old['cgroup'])/'cgroup.procs'
        require(not group.exists() or not group.read_text().strip(), 'Old trainer cgroup is not empty')
        self.event('original-terminal-show.json', value)
        absence = self.event('original-absence.json', dict(schema='robotron-live8-owned-trainer-absence-v1',
            trainer=old, unit_main_pid=0, unit_active_state='inactive', old_process_absent=True,
            owned_cgroup_empty=True, latest_path=str(LATEST)))
        spec = self.template['phase_snapshot']
        report, report_pin, latest = self.cpu('newest_stopped', LATEST, old, spec['phase_record'],
            spec['boot_checkpoint'], spec['boot_verification'], spec['expected_phase'],
            dict(tag=None, completed_slot_transition=None, stopped_absence=absence))
        self.floor = dict(report['clocks'])
        self.stopped_report, self.stopped_report_pin, self.boot = report, report_pin, latest
        self.bank_snapshot = self.banks.stopped_state(j['bank_spec'])
        self.event('stopped-ring-and-banks.json', self.bank_snapshot)

    def apply(self):
        j = self.job
        require(all(stopped(a) for a in self.paused), 'Actor escaped pause')
        require(starttime(j['anchor']['main_owner']['pid']) is None, 'Original owner still present')
        destination = Path(j['before_source']['path'])
        checked(j['before_source']); raw = checked(j['after_source'])
        require(not (destination.with_suffix('.boundary-tmp')).exists(), 'Source staging file exists')
        temporary = destination.with_suffix('.boundary-tmp')
        with temporary.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o664); os.fsync(stream.fileno())
        os.replace(temporary, destination)
        require(pin(destination)['sha256'] == j['after_source']['sha256'], 'Installed source differs')
        self.result['production_applied'] = True
        self.event('source-applied.json', pin(destination))
        # Shutdown rewrites game settings; restore the identical pre-stop bytes.
        settings = MODEL/'game_settings.json'
        temporary = settings.with_suffix('.boundary-tmp')
        with temporary.open('xb') as stream:
            stream.write(checked(j['settings_archive'])); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, settings)
        phase = resume_record(self.stopped_report['saved_priority_metric_phase'],
                              {k:self.boot[k] for k in ('path','sha256','bytes')})
        self.phase_pin = self.event('resume-phase-record.json', phase)
        dropin = Path(j['dropin']['path']); checked(j['dropin'])
        content = checked(j['dropin']).decode()
        old = self.template['phase_snapshot']['phase_record']
        require(content.count(old['path']) == content.count(old['sha256']) == 1, 'Old phase dropin binding differs')
        content = content.replace(old['path'], self.phase_pin['path']).replace(old['sha256'], self.phase_pin['sha256'])
        with dropin.with_suffix('.boundary-tmp').open('x') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.replace(dropin.with_suffix('.boundary-tmp'), dropin)
        self.event('new-dropin.json', pin(dropin))
        self.command(['systemctl','--user','daemon-reload'])

    def startup(self):
        j = self.job; unit = j['anchor']['main_owner']['unit']
        self.result['start_attempts'] += 1
        require(self.result['start_attempts'] == 1, 'No startup retry')
        self.command(['systemctl','--user','start','--no-block',unit])
        self.wait(lambda: int(show(unit)['MainPID']) > 0, 30, 'New trainer PID missing')
        value = show(unit); pid = int(value['MainPID'])
        self.owner = dict(pid=pid, starttime_ticks=starttime(pid), unit=unit,
                          invocation_id=value['InvocationID'], cgroup=value['ControlGroup'])
        self.event('replacement-owner.json', self.owner)
        latest_api = None
        def ready():
            nonlocal latest_api
            self.identity(self.owner)
            try: latest_api = api()
            except (OSError, ValueError): return False
            return latest_api.get('host_pipeline',{}).get('learning_exposure',{}).get('replay',{}).get('process_id') == pid
        self.wait(ready, 600, 'Replacement dashboard did not become ready')
        require(latest_api['client_count'] == 0 and latest_api['memory_buffer_size'] == 6000000
                and latest_api['lr'] == 1.25e-5, 'Startup profile differs or actors arrived early')
        require(latest_api['host_pipeline']['inference_graphs']['ready'] is True
                and latest_api['host_pipeline']['inference_graphs']['capture_count'] == 128,
                'Exact inference graphs are not ready')
        require(all(latest_api[k] == self.floor[k] for k in CLOCKS), 'Clocks changed before actor admission')
        self.banks.assert_unchanged(self.bank_snapshot, j['bank_spec'])
        self.event('startup-ring-maps.json', self.banks.verify_maps(pid, self.bank_snapshot))
        self.event('startup-API.json', latest_api)
        self.startup_api = latest_api
        # Obtain an actual zero-client save-slot transition for the existing
        # strict startup verifier. No previously saved candidate is substituted.
        slot = MODEL/'managed_save.request.json.completed'
        before_time = time.time(); before = None
        if slot.exists(): before = dict(actual_pin=pin(slot), archive=archive(slot, self.out/'completed-slot-before.json'))
        tag = 'boundary-continuity-startup-original01-20261018'
        request = MODEL/'managed_save.request.json'
        require(not request.exists() and not (MODEL/'managed-checkpoints'/(tag+'.pt')).exists(), 'Save slot/tag already used')
        # Briefly stop this exact replacement while publishing and archiving the
        # request, so the consumer cannot move the slot before its PIN is saved.
        self.identity(self.owner)
        os.kill(pid, signal.SIGSTOP)
        try:
            temporary = request.with_suffix('.boundary-tmp')
            with temporary.open('x') as stream:
                json.dump(dict(tag=tag), stream); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, request)
            request_pin = pin(request); request_archive = archive(request, self.out/'startup-request.json')
            requested_at = time.time()
        finally:
            require(starttime(pid) == self.owner['starttime_ticks'], 'Replacement changed during save-slot publication')
            os.kill(pid, signal.SIGCONT)
        def saved():
            try: return json.loads(slot.read_text()) == dict(tag=tag) and not request.exists()
            except (OSError, ValueError): return False
        self.wait(saved, 60, 'Startup save request did not finish')
        after_time = time.time(); after_pin = pin(slot); after_archive = archive(slot, self.out/'completed-slot-after.json')
        source = MODEL/'managed-checkpoints'/(tag+'.pt'); os.chmod(source, 0o444)
        expected = copy.deepcopy(self.template['phase_snapshot']['expected_phase'])
        expected['last_resume_record_sha256'] = self.phase_pin['sha256']
        transition = dict(before=before, request=dict(actual_pin=request_pin, archive=request_archive),
            after=dict(actual_pin=after_pin, archive=after_archive), before_unix_s=before_time,
            request_unix_s=requested_at, after_unix_s=after_time)
        report, _, _ = self.cpu('startup', source, self.owner, self.phase_pin,
            {k:self.boot[k] for k in ('path','sha256','bytes')}, self.stopped_report_pin, expected,
            dict(tag=tag, completed_slot_transition=transition, stopped_absence=None))
        require(report['clocks'] == self.floor, 'Startup CPU clocks changed')
        self.banks.assert_unchanged(self.bank_snapshot, j['bank_spec'])
        self.result['zero_client_CPU_passed'] = True

    def resume(self):
        errors = []
        for actor in self.paused:
            try: signal_actor(actor, signal.SIGCONT)
            except BaseException as error: errors.append(dict(actor=actor, error=repr(error)))
        count = len(self.paused)
        self.paused = []
        self.event('actor-resume-attempt.json', dict(count=count, errors=errors))
        require(not errors, 'Original actor resume failed')

    def run(self):
        try:
            self.context(); self.stop(); self.apply(); self.startup(); self.resume()
            def connected():
                self.identity(self.owner)
                self.final_api = api()
                return self.final_api['client_count'] == 192
            self.wait(connected, 180, 'Original192 did not reconnect')
            require(self.final_api['training_enabled'] and self.final_api['lr'] == 1.25e-5,
                    'Healthy learning settings not restored')
            self.health.main_health_contract(self.final_api, self.startup_api, self.owner['pid'], time.time())
            for actor in self.job['anchor']['actors']: require(not stopped(actor), 'Actor remained stopped')
            self.result.update(status='ACTIVATED_NEWEST_STATE_ORIGINAL192_RECONNECTED', owner=self.owner,
                               main_API=self.event('healthy192-API.json', self.final_api))
        except BaseException as error:
            self.result.update(status='FAILED_OUTCOME_PRESERVED', error=repr(error), traceback=traceback.format_exc())
            # Retire only a replacement incarnation this controller actually
            # started. Never admit actors to a failed/unverified startup.
            if hasattr(self, 'owner'):
                try:
                    self.identity(self.owner)
                    paused_ids = {a['pid'] for a in self.paused}
                    for actor in self.job['anchor']['actors']:
                        if actor['pid'] not in paused_ids:
                            self.paused.append(actor); signal_actor(actor, signal.SIGSTOP)
                    self.command(['systemctl','--user','stop','--no-block',self.owner['unit']])
                    self.wait(lambda: starttime(self.owner['pid']) != self.owner['starttime_ticks'],
                              240, 'Failed replacement has not retired')
                    self.event('failed-replacement-terminal.json', show(self.owner['unit']))
                except BaseException as cleanup:
                    self.result['replacement_cleanup_error'] = repr(cleanup)
        finally:
            if self.paused:
                try: self.resume()
                except BaseException as error: self.result['resume_error'] = repr(error)
            self.result['ended_unix_s'] = time.time(); self.event('result.json', self.result)
        return 0 if self.result['status'] == 'ACTIVATED_NEWEST_STATE_ORIGINAL192_RECONNECTED' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256'); args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no reads or runtime actions'); return 0
    require(args.job and pin(args.job)['sha256'] == args.expected_job_sha256, 'Exact root job required')
    job = json.loads(args.job.read_text()); require(job['authorized'] is True, 'Explicit activation required')
    for number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(number, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    return Activation(job).run()


if __name__ == '__main__':
    raise SystemExit(main())
