"""One selected old-mode population stop, FIFO fence and final save.

Default is inert. This does not install sources, start a replacement, or prove
saved payload integrity. A separate stopped CPU verifier must do the latter.
Unlike the earlier preserve-MAME-RAM adapter, the single owned RoundFleet is
closed first; its variable live/frozen population is never adopted by slot.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import subprocess
import time
import urllib.request


ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
CGROUP = Path('/sys/fs/cgroup')
CLOCKS = ('frame_count', 'learner_frame_count', 'training_steps', 'optimized_samples')
PERSISTENT = ('Thread-1 (serve', 'Thread-2 (_samp', 'Thread-3 (_cons',
              'Thread-4 (start', 'Thread-5 (stats')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def birth(pid, tid=None):
    path = Path('/proc', str(pid))
    if tid is not None:
        path = path/'task'/str(tid)
    try:
        return int((path/'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def show(unit):
    result = subprocess.run(['systemctl', '--user', 'show', unit],
                            capture_output=True, text=True, timeout=15)
    require(result.returncode == 0, 'Unit query failed')
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def load(entry, name):
    path = Path(entry['path'])
    require(hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], 'Dependency changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_pin(path):
    """Fingerprint selected system executables as well as user-owned sources."""
    path=Path(path);before=path.lstat()
    require(stat.S_ISREG(before.st_mode) and not path.is_symlink() and before.st_nlink==1,
            'Single regular canonical source required')
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    def identity(s):
        return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
                    ctime_ns=s.st_ctime_ns,mode=oct(s.st_mode&0o777),uid=s.st_uid,nlink=s.st_nlink)
    require(identity(before)==identity(path.lstat()),'Source changed during read')
    return dict(path=str(path),sha256=digest,bytes=before.st_size,identity=identity(before))


class Stop:
    def __init__(self, job):
        require(job['schema'] == 'robotron-owned-current-round-stop-job-v1'
                and job['authorized'] is True, 'Selected Root stop job required')
        require(re.fullmatch(r'continuous-stop-[A-Za-z0-9_-]{1,45}', job['case']), 'Unique stop case')
        self.job = job
        self.utils = load(job['dependencies']['linux_utilities'], '_old_stop_utilities')
        self.reader = load(job['dependencies']['bank_reader'], '_old_bank_reader')
        self.intent = load(job['dependencies']['bank_intent'], '_old_bank_intent')
        self.semantics = load(job['dependencies']['bank_semantics'], '_old_bank_semantics')
        self.u = self.utils
        for pin in job['inputs']:
            self.u.checked(pin)
        self.owner, self.fleet = job['trainer'], job['fleet']
        require(self.owner['unit'] == 'robotron-trainer.service'
                and self.fleet['unit'] == 'robotron-mame.service', 'Only selected permanent training units')
        self.out = Path(job['output'])
        require(self.out.resolve() == self.out and not self.out.exists(), 'New original output required')
        self.out.mkdir(mode=0o700)
        self.control = ROOT/'models_dqn/learning_control.json'
        self.control_pin = self.u.full_pin(self.control)
        self.base = self.u.checked(job['base_control'])
        require(self.control.read_bytes() == self.base, 'Current control changed')
        base = json.loads(self.base)
        require(base['lr_scale'] == .125 and base.get('measurement') is None,
                'Current .125 recipe without a foreign measurement required')
        self.case = job['case']
        self.probe = None
        self.probe_tid = None
        self.probe_id = None
        self.holds = {}
        self.current_pause = None
        self.signal_sent = {'fleet': False, 'trainer': False}
        self.final_API = None
        self.counter = 0

    def event(self, name, value):
        return self.u.publish(self.out/name, value)

    def live(self, owner):
        return self.u.live_owner(owner)

    def wait(self, predicate, seconds, reason):
        end = time.monotonic()+seconds
        while True:
            if predicate():
                return
            require(time.monotonic() < end, reason)
            time.sleep(.1)

    def candidates(self):
        self.live(self.owner)
        known = self.job['persistent_native']
        require(set(x['comm'] for x in known.values()) == set(PERSISTENT), 'Exact five source-bound persistent tasks')
        result = {}
        for path in Path('/proc', str(self.owner['pid']), 'task').iterdir():
            try:
                tid = int(path.name)
                born = birth(self.owner['pid'], tid)
                name = (path/'comm').read_text().strip()
                if str(tid) in known:
                    expected = known[str(tid)]
                    require(born == expected['starttime_ticks'] and name == expected['comm'],
                            'Persistent native birth/name changed')
                elif re.match(r'^(?:Thread-[0-9]+(?:[ ()].*)?|Timer.*)$', name):
                    if born == birth(self.owner['pid'], tid):
                        result[tid] = dict(tid=tid, starttime_ticks=born, comm=name,
                                           wchan=(path/'wchan').read_text().strip())
            except (FileNotFoundError, ProcessLookupError):
                continue
        require(all(birth(self.owner['pid'], int(tid)) == x['starttime_ticks']
                    for tid, x in known.items()), 'Persistent native task absent')
        return result

    def api(self):
        require('HTTP' not in self.holds, 'No API after HTTP admission hold')
        self.live(self.owner)
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
            raw = response.read((2 << 20)+1)
        require(len(raw) <= 2 << 20, 'API exceeds bound')
        value = json.loads(raw)
        require(0 <= time.time()-value['ts'] <= 5
                and 0 <= value['pipeline_snapshot_age_s'] <= 5
                and value['pipeline_read_error'] == value['bank_persistence_read_error'] == ''
                and value['managed_experiment'] == self.job['experiment']
                and value['lr'] == 6.25e-6, 'Original recipe/fresh API required')
        pipe = value['host_pipeline']
        require(pipe['available'] is True and pipe['generation'] == 0, 'Original pipeline generation')
        for key in ('inference', 'actor_refresh', 'target_refresh', 'learner_priority'):
            require(pipe[key]['errors'] == 0, 'Pipeline error: '+key)
        for key in ('optimizer', 'replay'):
            exposure = pipe['learning_exposure'][key]
            require(exposure['process_id'] == self.owner['pid'] and exposure['epoch'] == 1
                    and exposure['enabled'] is True, 'Original exposure identity changed')
            require(exposure['instance_monotonic_ns'] == self.job['exposure_instances'][key],
                    'Original exposure incarnation changed')
            if key == 'optimizer':
                total=exposure['total']
                require(all(type(total[k])is int and total[k]>=0 for k in
                            ('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')),
                        'Invalid optimizer outcome counts')
                gap=total['attempts_started']-total['outcomes_recorded']
                require(gap in (0,1) and exposure['unclassified_started_total']==gap
                        and total['outcomes_recorded']==total['applied']+total['amp_skipped']
                        and total['outcomes_recorded']>0 and total['unavailable']==0
                        and exposure['since_epoch']['unavailable']==0
                        and exposure['available'] is (gap==0),
                        'Only one ordinary in-flight attempt allowed; unknown outcomes remain invalid')
            else:
                require(exposure['available'] is True,'Replay exposure unavailable')
        self.counter += 1
        self.final_API = self.event('API-%04d.json' % self.counter, raw)
        return value

    def archive_unit(self, owner, label, *, console_tail=None, final_save=None):
        archive = {}
        for command in ('show', 'cat', 'journal'):
            argv = (['journalctl', '--user', '-u', owner['unit'], '--no-pager', '-o', 'short-monotonic']
                    if command == 'journal' else ['systemctl', '--user', command, owner['unit']])
            r = subprocess.run(argv, capture_output=True, timeout=30)
            require(r.returncode == 0, 'Original terminal archive failed: '+command)
            stdout=self.event(label+'-'+command+'-stdout.txt',r.stdout)
            stderr=self.event(label+'-'+command+'-stderr.txt',r.stderr)
            archive[command]=self.event(label+'-'+command+'-command.json',
                dict(owner=owner,argv=argv,exit=r.returncode,stdout=stdout,stderr=stderr,unix_s=time.time()))
        return self.event(label+'-terminal-archive.json',dict(owner=owner,archives=archive,
                         console_tail=console_tail,final_save=final_save))

    def preflight(self):
        self.live(self.owner)
        self.live(self.fleet)
        binding = json.loads(self.u.checked(self.job['main_binding']))
        for key,owner in [('trainer',self.owner),('fleet',self.fleet)]:
            original=binding['owners'][key]
            require(original['unit']==owner['unit'] and original['invocation']==owner['invocation_id']
                    and original['process']['pid']==owner['pid']
                    and original['process']['starttime_ticks']==owner['starttime_ticks']
                    and original['process']['cgroup']==owner['cgroup'],'Original D7 owner differs')
        env=dict(x.split('=',1)for x in Path('/proc',str(self.owner['pid']),'environ').read_bytes().decode().split('\0')if '='in x)
        require(env.get('ROBOTRON_CONTINUOUS_TRAINING_MODE','0')=='0'
                and env['DQN_PRIORITY_PHASE_RECORD_SHA256']==self.job['boot_resume_sha256']
                and env['DQN_BATCH_SIZE']=='4096' and env['DQN_N_STEP']=='3'
                and env['DQN_MAX_SAMPLES_PER_FRAME']=='8' and env['DQN_PER_PRIORITY_METRIC']=='ce',
                'Original mode0/recipe/resume differs')
        parent=CGROUP/self.owner['cgroup'].lstrip('/')
        require(parent.stat().st_uid==os.getuid() and os.access(parent,os.W_OK)
                and os.access(parent/'cgroup.threads',os.W_OK)
                and(parent/'cgroup.type').read_text().strip()=='domain'
                and not(parent/'cgroup.subtree_control').read_text().strip()
                and not any(p.is_dir()for p in parent.iterdir()),'Owned untouched delegated admission-fence scope required')
        require(len(binding['inputs']) == 247, 'Exact current D7 main input inventory')
        for path, expected in binding['inputs'].items():
            actual = source_pin(path)
            require(actual['sha256'] == expected['sha256']
                    and actual['identity'] == expected['identity'], 'Current held source changed: '+path)
        state = json.loads((ROOT/'logs/managed-learning-20261015/state.json').read_bytes())
        require(all(state.get(k) is None for k in ('active_quality_job', 'active_deadline_score_job',
                                                 'active_readonly_validation_job'))
                and state['optimization_goal']['scientific_job_running'] is False, 'Scientific job active')
        api = self.api()
        require(api['training_enabled'] is True and api['measurement_active'] is False
                and api['memory_buffer_size'] == 6000000
                and not (self.control.parent/'managed_save.request.json').exists(), 'Old main not ready')
        roles = json.loads(self.u.checked(self.job['rolemap']))
        require(set(roles)=={str(s)for s in range(192)} and all(type(v)is bool for v in roles.values())
                and sum(roles.values()) == 37, 'Actual155/37 role map required')
        root = CGROUP/self.fleet['cgroup'].lstrip('/')
        require(root.resolve(strict=True) == root, 'Fleet cgroup alias')
        members = set(map(int, (root/'cgroup.procs').read_text().split()))
        require(self.fleet['pid'] in members, 'Fleet absent from exact cgroup')
        actors = []
        for pid in sorted(members-{self.fleet['pid']}):
            p = Path('/proc', str(pid));raw = (p/'stat').read_text().rsplit(')', 1)[1].split()
            env = dict(x.split('=', 1) for x in (p/'environ').read_bytes().decode().split('\0') if '=' in x)
            slot = int(env['ROBOTRON_CLIENT_SLOT'])
            require(int(raw[1]) == self.fleet['pid'] and p.stat().st_uid == os.getuid()
                    and (p/'cgroup').read_text().strip() == '0::'+self.fleet['cgroup']
                    and (p/'exe').resolve() == Path(self.job['mame_executable'])
                    and (p/'cmdline').read_bytes().decode().rstrip('\0').split('\0')==self.job['actor_command']
                    and env['ROBOTRON_EVAL_MODE'] == ('1' if roles[str(slot)] else '2')
                    and env['ROBOTRON_RETIRE_AFTER_GAME'] == '1', 'Foreign fleet member/source/role')
            actors.append(dict(pid=pid, starttime_ticks=int(raw[19]), slot=slot,
                               eval_only=roles[str(slot)], state=raw[0]))
        require(len(actors) <= 192 and len({a['slot'] for a in actors}) == len(actors), 'Duplicate physical slots')
        require(all(r['client_slot'] in {a['slot'] for a in actors} for r in api['client_rows']),
                'Unowned live client before population stop')
        self.actor_births = actors
        self.old_handlers = self.candidates()
        self.event('original-current-population.json', dict(trainer=self.owner, fleet=self.fleet, actors=actors))
        self.event('restart-censored-active-scores.json', dict(schema='robotron-restart-censored-active-score-v1',
            observed_unix_s=time.time(), raw_API=self.final_API, rows=api['client_rows'],
            completed_round_results=api['training_round']['results'],
            active_scope='Current accepted full scores; interrupted games are restart-censored, never natural completions',
            quality_qualified=False))

    def request_stop(self,kind,owner):
        current=self.live(owner)
        expected_signal=str(int(signal.SIGTERM if kind=='fleet'else signal.SIGINT))
        expected_mode='mixed'if kind=='fleet'else'control-group'
        require(current.get('KillSignal')==expected_signal and current.get('KillMode')==expected_mode
                and current.get('SendSIGKILL')=='no','Selected supported service stop semantics changed')
        require(not self.signal_sent[kind],'One original manual service stop only')
        self.signal_sent[kind]=True
        argv=['systemctl','--user','stop','--no-block',owner['unit']]
        self.event(kind+'-manual-stop-intent.json',dict(owner=owner,argv=argv,
            original_restart_policy=current.get('Restart'),manual_stop_suppresses_automatic_restart=True))
        try:
            r=subprocess.run(argv,capture_output=True,timeout=15)
        except subprocess.TimeoutExpired as error:
            self.event(kind+'-manual-stop-command.json',dict(owner=owner,argv=argv,exit=None,
                error='StopUnit delivery/completion unknown; observe the same original, never retry',
                stdout=self.event(kind+'-stop-stdout.txt',error.stdout or b''),
                stderr=self.event(kind+'-stop-stderr.txt',error.stderr or b'')))
            raise
        self.event(kind+'-manual-stop-command.json',dict(owner=owner,argv=argv,exit=r.returncode,
            stdout=self.event(kind+'-stop-stdout.txt',r.stdout),stderr=self.event(kind+'-stop-stderr.txt',r.stderr)))
        require(r.returncode==0,'Original manual StopUnit request failed; never retry')

    def close_population(self):
        self.request_stop('fleet',self.fleet)
        self.wait(lambda: birth(self.fleet['pid']) != self.fleet['starttime_ticks'],
                  35, 'Same original fleet still live; observe, do not restart')
        value = show(self.fleet['unit'])
        require(value['ExecMainPID'] == str(self.fleet['pid']) and value['ExecMainCode'] == '1'
                and value['ExecMainStatus'] == '0' and value['NRestarts'] == '0'
                and value['MainPID'] == '0', 'Original fleet not normal0/no-restart')
        require(all(birth(a['pid']) != a['starttime_ticks'] for a in self.actor_births), 'Original actor remains')
        root = CGROUP/self.fleet['cgroup'].lstrip('/')
        require(not root.exists() or not (root/'cgroup.procs').read_text().strip(), 'Fleet cgroup populated')
        self.archive_unit(self.fleet, 'fleet')
        self.wait(lambda: self.api()['client_count'] == 0, 15, 'Old clients not disconnected')

    def open_probe(self):
        before = self.candidates()
        self.probe = socket.create_connection(('127.0.0.1', 9998), timeout=3)
        self.probe.settimeout(3)
        self.probe.sendall(struct.pack('>H', (1 << 14) | (8191 << 1)))
        def registered():
            api = self.api()
            if api['client_count'] != 1:
                return False
            row = api['client_rows'][0]
            require(row['client_slot'] == 8191 and row['eval'] is True and row['session_seconds'] == 0,
                    'Only owned explicit EVAL probe without frames')
            found = [x for tid, x in self.candidates().items()
                     if tid not in before and x['wchan'].startswith('poll_schedule_timeout')]
            if len(found) != 1:
                return False
            self.probe_tid, self.probe_id = found[0], row['client_id']
            return True
        self.wait(registered, 10, 'Explicit EVAL maintenance probe not source-bound')

    def hold(self, kind, comm):
        self.live(self.owner)
        found = [(int(tid), x) for tid, x in self.job['persistent_native'].items() if x['comm'] == comm]
        require(len(found) == 1 and kind not in self.holds, 'Exact source-bound admission task required')
        tid, info = found[0]
        task = Path('/proc', str(self.owner['pid']), 'task', str(tid))
        self.wait(lambda: (task/'wchan').read_text().strip().startswith('poll_schedule_timeout'),
                  5, 'Admission task not in source-bound poll wait')
        require(birth(self.owner['pid'], tid) == info['starttime_ticks'], 'Admission task replaced')
        parent = CGROUP/self.owner['cgroup'].lstrip('/')
        require(parent.stat().st_uid == os.getuid() and not (parent/'cgroup.subtree_control').read_text().strip(),
                'Owned delegated cgroup required')
        child = parent/(kind.lower()+'-'+self.case)
        require(not child.exists(), 'Hold already exists')
        child.mkdir()
        self.holds[kind] = dict(path=str(child), tid=tid, birth=info['starttime_ticks'])
        self.event(kind+'-hold-intent.json', self.holds[kind])
        (child/'cgroup.type').write_text('threaded\n')
        (child/'cgroup.freeze').write_text('1\n')
        (child/'cgroup.threads').write_text(str(tid)+'\n')
        self.wait(lambda: dict(line.split() for line in (child/'cgroup.events').read_text().splitlines()).get('frozen') == '1',
                  3, 'Admission hold not positively frozen')
        require(set(map(int, (child/'cgroup.threads').read_text().split())) == {tid}, 'Unexpected held native task')

    def release(self, kind):
        item = self.holds[kind];child = Path(item['path'])
        if not child.exists():
            require(birth(self.owner['pid']) != self.owner['starttime_ticks'],
                    'A live owned admission hold disappeared')
            parent=CGROUP/self.owner['cgroup'].lstrip('/')
            require(not parent.exists() or not(parent/'cgroup.procs').read_text().strip(),
                    'Absent hold with a populated original scope')
            del self.holds[kind]
            return
        require(child.resolve(strict=True) == child and child.stat().st_uid == os.getuid(), 'Owned hold changed')
        tids = set(map(int, (child/'cgroup.threads').read_text().split()))
        require(tids <= {item['tid']}, 'Foreign held task')
        if tids:
            require(birth(self.owner['pid'], item['tid']) == item['birth'], 'Held native birth changed')
            (child.parent/'cgroup.threads').write_text(str(item['tid'])+'\n')
        (child/'cgroup.freeze').write_text('0\n')
        require(not (child/'cgroup.threads').read_text().strip(), 'Hold still populated')
        child.rmdir();del self.holds[kind]

    def pause(self, purpose):
        label = self.case+'-'+purpose
        require(not (self.control.parent/'managed-measurements'/(label+'.json')).exists(), 'Pause label already used')
        data = dict(json.loads(self.base), measurement=dict(label=label, checkpoint=None, cohort_s=3600, timeout_s=7200))
        self.control_pin = self.u.atomic_owned_replace(self.control, self.control_pin,
            (json.dumps(data, indent=2)+'\n').encode(), suffix=self.case)
        def paused():
            api = self.api();m = api['managed_measurement']
            if not (api['measurement_active'] is True and api['training_enabled'] is False
                    and m.get('active') is True and m.get('label') == label and m.get('phase') == 'warming'):
                return False
            self.current_pause = dict(label=label, generation=m['generation'])
            return True
        self.wait(paused, 20, 'Real training-lock/prefetch pause did not enter')

    def check_pause(self, api):
        m = api['managed_measurement']
        require(api['measurement_active'] is True and api['training_enabled'] is False and m['active'] is True
                and all(m[k] == v for k, v in self.current_pause.items())
                and m['phase'] in ('warming', 'collecting', 'draining'), 'Owned supported pause changed')
        return m

    def marker(self):
        require('GAME' in self.holds and self.probe is not None, 'Exclusive owned maintenance input required')
        self.check_pause(self.api())
        payload = struct.pack('>HddBIBBBIBBB', 1890, 0., 0., 0, 0, 1, 0, 0, 20000, 2, 1, 3)+b'\0'*(1890*4)
        packet = struct.pack('>I', len(payload))+payload
        for _ in range(8):
            self.probe.sendall(packet);response = bytearray()
            while len(response) < 6:
                chunk = self.probe.recv(6-len(response));require(chunk, 'Probe closed before reply');response.extend(chunk)
        def acknowledged():
            api = self.api();m = self.check_pause(api);b = m.get('boundary', {})
            return (b.get('ready') is True and b.get('generation') == self.current_pause['generation']
                    and self.probe_id in b.get('acknowledged_client_ids', []))
        self.wait(acknowledged, 10, 'Actual consumer FIFO marker did not acknowledge')
        self.event(self.current_pause['label']+'-FIFO-ack.json', dict(pause=self.current_pause,
            actual_consumer_reset_marker_acknowledged=True, API=self.final_API))

    def cancel_pause_and_drain(self):
        old = self.current_pause
        self.control_pin = self.u.atomic_owned_replace(self.control, self.control_pin, self.base, suffix=self.case)
        def restored():
            api = self.api();m = api['managed_measurement']
            require(m.get('phase') != 'restore_failed', 'Restoration failed')
            return (api['measurement_active'] is False and api['training_enabled'] is True
                    and m.get('active') is False and m.get('label') == old['label'] and m.get('phase') == 'finished')
        self.wait(restored, 15, 'Owned pause not restored')
        self.current_pause = None
        boot = self.job['boot_saved_clocks']
        def exhausted():
            api = self.api();o = api['host_pipeline']['learning_exposure']['optimizer']
            require(api['client_count'] == 1 and api['client_rows'][0]['client_id'] == self.probe_id
                    and api['measurement_active'] is False, 'Unknown ordinary producer during finite budget drain')
            frames = api['frame_count']-boot['frame_count']-max(0, api['measurement_frames']-boot['measurement_frame_count'])
            samples = api['optimized_samples']-boot['optimized_samples']
            return (samples >= 8*max(1, frames) and o['total']['attempts_started'] == o['total']['outcomes_recorded']
                    and o['unclassified_started_total'] == o['total']['unavailable'] == 0)
        self.wait(exhausted, 25, 'Original cap8 budget not positively exhausted')

    def seal_banks(self):
        require(self.probe is None and 'GAME' in self.holds, 'Ordinary input/probe not closed')
        result = None
        def sealed():
            nonlocal result
            before = self.api();self.check_pause(before)
            require(before['client_count'] == 0 and before['client_rows'] == [], 'Remaining producer')
            if before['bank_persistence']['writer_active'] or before['bank_persistence']['output']['active'] is not None:
                return False
            banks = {k:self.reader.read_bank_generation(k, self.control.parent/('robotron_dqn_latest_replay_'+k))
                     for k in ('hof', 'ephof')}
            time.sleep(1.1)
            after = self.api();self.check_pause(after)
            proof = self.intent.validate(before, after, banks, expected_pid=self.owner['pid'], now=time.time())
            result = dict(bank_pair=proof, bank_metadata_semantics=self.semantics.bank_metadata_semantics(banks,self.reader),
                replay_exposure=after['host_pipeline']['learning_exposure']['replay'],
                clock_floor={k:after[k] for k in CLOCKS},final_API=self.final_API,
                input_sources_sealed=True,all_handlers_finished=True,prefetch_paused=True,budget_exhausted=True)
            return True
        self.wait(sealed, 180, 'Paused bank intent did not become quiescent')
        return self.event('bank-seal.json', result)

    def stop_trainer(self, bank_seal):
        self.hold('HTTP', 'Thread-1 (serve')
        self.wait(lambda: not self.candidates(), 15, 'HTTP/Timer/unknown auto-thread remains')
        time.sleep(1.1)
        require(not self.candidates(), 'Late cleanup/unknown auto-thread')
        console = Path(self.job['console']);info = console.stat()
        require(console.resolve(strict=True) == console and info.st_uid == os.getuid() and info.st_nlink == 1,
                'Bound original stdout file required')
        for fd in (1,2):
            p = Path('/proc', str(self.owner['pid']), 'fd', str(fd))
            require(p.readlink() == console and (p.stat().st_dev,p.stat().st_ino) == (info.st_dev,info.st_ino),
                    'Original stdout/stderr changed')
        require(b'PYTHONUNBUFFERED=1' in Path('/proc',str(self.owner['pid']),'environ').read_bytes().split(b'\0'),
                'Unbuffered final-save return marker required')
        requested=time.time()
        self.request_stop('trainer',self.owner)
        def retired():
            if birth(self.owner['pid']) == self.owner['starttime_ticks'] and 'HTTP' in self.holds:
                now = console.stat()
                require((now.st_dev,now.st_ino) == (info.st_dev,info.st_ino)
                        and 0 <= now.st_size-info.st_size <= 8 << 20, 'Original console append changed')
                with console.open('rb') as f:
                    f.seek(info.st_size);tail = f.read((8 << 20)+1)
                if b'Final model & settings saved' in tail:
                    self.release('HTTP')  # Save returned; payload success remains independently unproved.
            return birth(self.owner['pid']) != self.owner['starttime_ticks'] and show(self.owner['unit'])['MainPID'] == '0'
        self.wait(retired, 230, 'Same original trainer still stopping; do not restart')
        terminal = show(self.owner['unit'])
        require(terminal['ExecMainPID'] == str(self.owner['pid']) and terminal['ExecMainCode'] == '1'
                and terminal['ExecMainStatus'] == '0' and terminal['NRestarts'] == '0'
                and terminal['MainPID'] == '0', 'Original trainer exit/no-restart differs')
        binding=dict(path=str(console),device=info.st_dev,inode=info.st_ino,uid=info.st_uid,
                     nlink=info.st_nlink,offset=info.st_size)
        raw=self.semantics.read_console_tail(binding)
        final_save=self.semantics.final_save_console(raw)
        console_tail=self.event('trainer-final-console-tail.txt',raw)
        archive = self.archive_unit(self.owner,'trainer',console_tail=console_tail,final_save=final_save)
        for kind in list(self.holds):
            self.release(kind)
        root = CGROUP/self.owner['cgroup'].lstrip('/')
        require(not root.exists() or not (root/'cgroup.procs').read_text().strip(), 'Original trainer cgroup populated')
        return self.event('stopped-preservation-authority.json', dict(
            schema='robotron-owned-stopped-training-preservation-authority-v1',owner=self.owner,
            actual_exit=0,original_scope_released=True,terminal_archive=archive,
            final_API=json.loads(self.u.checked(bank_seal))['final_API'],bank_seal=bank_seal,
            stop_requested_unix_s=requested,stopped_unix_s=time.time(),
            saved_payload_integrity_qualified=False,replacement_started=False))

    def run(self):
        outcome = dict(status='ORIGINAL_STOP_INCOMPLETE',actual_stopped_authority=None,
                       model_replay_integrity_verified=False,replacement_started=False,source_installed=False)
        try:
            self.preflight();self.close_population();self.open_probe()
            self.hold('GAME','Thread-4 (start')
            self.pause('drain');self.marker()
            self.wait(lambda: not any(birth(self.owner['pid'],tid)==x['starttime_ticks']
                                     for tid,x in self.old_handlers.items()), 20, 'Original handlers remain')
            self.cancel_pause_and_drain();self.pause('final');self.marker()
            self.probe.close();self.probe=None
            self.wait(lambda: birth(self.owner['pid'],self.probe_tid['tid']) != self.probe_tid['starttime_ticks'],
                      5,'Owned probe handler remains')
            self.wait(lambda: self.api()['client_count'] == 0,5,'Cached probe still present')
            seal=self.seal_banks();authority=self.stop_trainer(seal)
            outcome.update(status='ORIGINAL_POPULATION_AND_TRAINER_STOPPED_CPU_VERIFICATION_REQUIRED',
                           actual_stopped_authority=authority)
        except BaseException as error:
            outcome['error']=repr(error)
        finally:
            errors=[]
            if self.probe is not None:
                try:self.probe.close()
                except BaseException as error:errors.append(dict(kind='owned_probe_close',error=repr(error)))
                else:self.probe=None
            for kind in list(self.holds):
                try:self.release(kind)
                except BaseException as error:errors.append(dict(kind=kind,error=repr(error)))
            try:
                if self.control.read_bytes() != self.base:
                    self.control_pin=self.u.atomic_owned_replace(self.control,self.control_pin,self.base,suffix=self.case)
            except BaseException as error:errors.append(dict(kind='owned_control_restore',error=repr(error)))
            outcome['cleanup_errors']=errors;outcome['one_shot_manual_stop_requests']=self.signal_sent
            self.event('original-outcome.json',outcome)
        return outcome


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path)
    parser.add_argument('--job-sha256');args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS');return 0
    require(args.job and hashlib.sha256(args.job.read_bytes()).hexdigest()==args.job_sha256,'Exact selected job')
    job=json.loads(args.job.read_bytes())
    require(job['source']['path']==str(Path(__file__).resolve())
            and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==job['source']['sha256'],'Selected controller source')
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Owned stop controller signal '+str(signum))
    for number in (signal.SIGINT,signal.SIGTERM):
        signal.signal(number,interrupted)
    result=Stop(job).run()
    return 0 if result['status']=='ORIGINAL_POPULATION_AND_TRAINER_STOPPED_CPU_VERIFICATION_REQUIRED' and not result['cleanup_errors'] else 1


if __name__=='__main__':
    raise SystemExit(main())
