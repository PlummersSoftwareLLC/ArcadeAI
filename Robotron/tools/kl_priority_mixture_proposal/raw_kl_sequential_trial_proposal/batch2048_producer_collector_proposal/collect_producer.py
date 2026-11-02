#!/usr/bin/env python3
"""Unconsumed two-stage read-only producer collector; literal PLAN by default."""
import argparse
import copy
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import time
import traceback

PROFILE = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_profile_horizon_proposal/profile.json')
PROFILE_SHA = 'e755e22ade5cb56537b08f41f412e856da09435d88e4e71e09b22aba521eac50'
MAX_FILE, MAX_TOTAL = 4 << 20, 32 << 20
HEADER, SUFFIX, MAX_SECONDS = 32768, 256 << 10, 10
SOURCES = {'__init__.py', 'model.py', 'config.py', 'learning_control.py',
           'agent.py', 'training.py', 'loss_kernel.py', 'priority_phase.py'}
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
OWNER = {'pid', 'starttime_ticks', 'unit', 'invocation_id', 'cgroup'}
FLAGS = ('DQN_RECOMPUTED_CE_CAPTURE_DIR', 'DQN_EXECUTED_CE_TRACE_DIR')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
        mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def owner(value):
    require(isinstance(value, dict) and set(value) == OWNER, 'Exact known owner required')
    require(all(type(value[k]) is int and value[k] > 0 for k in ('pid', 'starttime_ticks'))
        and re.fullmatch(r'robotron-managed-[A-Za-z0-9_.-]+-trainer\.service', value['unit'] or '')
        and re.fullmatch(r'[0-9a-f]{32}', value['invocation_id'] or '')
        and value['cgroup'].startswith('/user.slice/')
        and value['cgroup'].endswith('/' + value['unit']) and '..' not in value['cgroup'].split('/'), 'Bad owner identity')
    return copy.deepcopy(value)


def absolute(value):
    require(type(value) is str and Path(value).is_absolute() and str(Path(value)) == value
        and '..' not in Path(value).parts and '\0' not in value, 'Canonical absolute path required')
    return Path(value)


def pin_shape(pin):
    require(isinstance(pin, dict) and set(pin) == {'path', 'sha256', 'bytes', 'identity'}, 'Full PIN required')
    absolute(pin['path'])
    require(re.fullmatch('[0-9a-f]{64}', pin['sha256'] or '') and type(pin['bytes']) is int and pin['bytes'] > 0,
        'PIN SHA/bytes missing')
    require(set(pin['identity']) == {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'nlink'}
        and pin['identity']['bytes'] == pin['bytes'], 'PIN identity incomplete')
    return copy.deepcopy(pin)


def triple(pin):
    pin_shape(pin)
    return {k: pin[k] for k in ('path', 'sha256', 'bytes')}


def bounded_read(path, limit, *, proc=False):
    path = Path(path)
    if proc:
        require(str(path) == '/proc/sys/kernel/random/boot_id' or
            re.fullmatch(r'/proc/[1-9][0-9]*/(?:stat|status|cmdline|environ|cgroup)', str(path)), 'Unknown proc read')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and (0 <= before.st_size <= limit if proc else 0 < before.st_size <= limit), 'Bounded regular file required: ' + str(path))
        chunks, length = [], 0
        while True:
            part = os.read(fd, min(65536, limit + 1 - length))
            if not part:
                break
            chunks.append(part); length += len(part)
            require(length <= limit, 'Read exceeded bound')
        after, named = os.fstat(fd), path.lstat()
        same = (all(getattr(before,k) == getattr(after,k) == getattr(named,k)
                    for k in ('st_dev','st_ino','st_mode','st_uid')) if proc else
                identity(before) == identity(after) == identity(named))
        require(length > 0 and same, 'File changed/empty during read')
        return b''.join(chunks), identity(before)
    finally:
        os.close(fd)


def read_pin(pin, *, readonly=True):
    pin_shape(pin)
    require(not re.search(r'\.(?:pt|pth)(?:$|\.(?:tmp|bak)$)', Path(pin['path']).name), 'Collector never opens checkpoint bodies')
    raw, observed = bounded_read(absolute(pin['path']), MAX_FILE)
    require(observed == pin['identity'] and len(raw) == pin['bytes'] and sha(raw) == pin['sha256'], 'Bound metadata/source changed')
    require(observed['uid'] == os.getuid() and observed['nlink'] == 1, 'Owned single-link file required')
    if readonly:
        require(observed['mode'] == '0o444', 'Immutable metadata required')
    return raw


def read_json(pin):
    return json.loads(read_pin(pin))


class Writer:
    def __init__(self, output):
        self.path = absolute(str(output))
        require(not self.path.exists() and self.path.parent.resolve() == self.path.parent
            and self.path.parent.stat().st_uid == os.getuid(), 'NEW output under owned canonical parent required')
        self.path.mkdir(mode=0o700); self.total = 0; self.pins = []

    def put(self, name, value):
        raw = value if type(value) is bytes else (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
        require(0 < len(raw) <= MAX_FILE and self.total + len(raw) <= MAX_TOTAL, 'Metadata artifact budget exceeded')
        path = self.path / name
        require(path.parent == self.path and not path.exists(), 'Create-only artifact name required')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            offset = 0
            while offset < len(raw):
                n = os.write(fd, raw[offset:]); require(n > 0, 'Short metadata write'); offset += n
            os.fchmod(fd, 0o444); os.fsync(fd)
        finally:
            os.close(fd)
        d = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(d)
        finally: os.close(d)
        result = dict(path=str(path), sha256=sha(raw), bytes=len(raw), identity=identity(path.lstat()))
        require(read_pin(result) == raw, 'Published metadata differs')
        self.total += len(raw); self.pins.append(result)
        return result


def unit_start(command, expected):
    require(command['argv'] == ['systemctl', '--user', '--timestamp=us+utc', 'show', expected['unit'], '--all']
        and command.get('environment_overrides') == {'TZ': 'UTC'} and command['returncode'] == 0, 'Precise original unit command required')
    fields = dict(x.split('=', 1) for x in command['stdout'].splitlines() if '=' in x)
    require(fields.get('MainPID') == fields.get('ExecMainPID') == str(expected['pid'])
        and fields.get('InvocationID') == expected['invocation_id'] and fields.get('ControlGroup') == expected['cgroup']
        and fields.get('NRestarts') == '0' and fields.get('Restart') == 'no', 'Original producer unit differs')
    text = fields.get('ExecMainStartTimestamp', '')
    require(re.fullmatch(r'[A-Z][a-z]{2} [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6} UTC', text), 'UTC microsecond start required')
    dt = datetime.strptime(text, '%a %Y-%m-%d %H:%M:%S.%f UTC').replace(tzinfo=timezone.utc)
    require(dt.strftime('%a %Y-%m-%d %H:%M:%S.%f UTC') == text
        and fields.get('ExecMainStartTimestampMonotonic', '').isdecimal()
        and int(fields['ExecMainStartTimestampMonotonic']) > 0, 'Unit start calendar/monotonic differs')
    delta = dt - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return fields, (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


class ReadOnlyHost:
    def clock(self):
        raw, _ = bounded_read('/proc/sys/kernel/random/boot_id', 128, proc=True)
        return dict(boot_id=raw.decode().strip(), monotonic_s=time.monotonic(), unix_s=time.time())

    def observe(self, expected):
        pid = expected['pid']; proc = Path('/proc') / str(pid)
        def small(name, limit): return bounded_read(proc / name, limit, proc=True)[0]
        def start():
            raw = small('stat', 4096).decode(); fields = raw[raw.rfind(')') + 2:].split()
            require(int(raw.split(' ', 1)[0]) == pid and len(fields) > 19, 'Bad exact PID stat')
            return int(fields[19])
        require(start() == expected['starttime_ticks'], 'Owner PID absent/reused')
        argv = [os.fsdecode(v) for v in small('cmdline', 128 << 10).split(b'\0') if v]
        status = small('status', 32768).decode()
        uids = next([int(v) for v in line.split()[1:]] for line in status.splitlines() if line.startswith('Uid:'))
        cg = small('cgroup', 16384).decode().strip()
        environment = dict(os.fsdecode(v).split('=', 1) for v in small('environ', 256 << 10).split(b'\0') if b'=' in v)
        environment = {k:v for k,v in environment.items() if k.startswith(('DQN_', 'ROBOTRON_', 'CUDA_', 'TORCHINDUCTOR_'))}
        process = dict(pid=pid, starttime_ticks=start(), argv=argv, uid=uids, cgroup=cg,
            cwd=os.readlink(proc / 'cwd'), exe=os.readlink(proc / 'exe'))
        command = ['systemctl', '--user', '--timestamp=us+utc', 'show', expected['unit'], '--all']
        result = subprocess.run(command, env=dict(os.environ, TZ='UTC'), capture_output=True, text=True, timeout=3, check=False)
        require(len(result.stdout.encode()) <= MAX_FILE and len(result.stderr.encode()) <= 32768, 'Unit metadata too large')
        unit = dict(argv=command, environment_overrides={'TZ':'UTC'}, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        require(start() == expected['starttime_ticks'], 'Owner changed during observation')
        return dict(owner=copy.deepcopy(expected), process=process, environment=environment, unit=unit)

    def csv(self, path):
        return csv_capture(path)


def csv_capture(path):
    path = absolute(str(path))
    require(path.parent.resolve() == path.parent and path.parent.is_dir()
        and path.parent.stat().st_uid == os.getuid(), 'Owned canonical producer run-directory required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        first = os.fstat(fd); before = path.lstat()
        require(stat.S_ISREG(first.st_mode) and first.st_uid == os.getuid() and first.st_nlink == 1
            and identity(first)['mode'] in ('0o600','0o640','0o644','0o660','0o664')
            and identity(first) == identity(before), 'CSV open identity differs')
        header = os.read(fd, HEADER + 1); end = header.find(b'\n')
        require(0 <= end < HEADER, 'Bounded complete CSV header required'); header = header[:end+1]
        begin = max(len(header), first.st_size - SUFFIX)
        boundary = True
        if begin > len(header):
            os.lseek(fd, begin-1, os.SEEK_SET); boundary = os.read(fd, 1) == b'\n'
        os.lseek(fd, begin, os.SEEK_SET); tail = os.read(fd, min(SUFFIX, max(0, first.st_size-begin)))
        cursor = begin; complete = []
        for line in tail.splitlines(keepends=True):
            if cursor == begin and not boundary: cursor += len(line); continue
            if line.endswith(b'\n'): complete.append((cursor, line))
            cursor += len(line)
        require(complete, 'No bounded complete data row'); offset, row = complete[-1]
        last = os.fstat(fd); after = path.lstat()
        require(identity(last) == identity(after) and all(getattr(first,k) == getattr(last,k)
            for k in ('st_dev','st_ino','st_uid','st_nlink','st_mode')) and last.st_size >= first.st_size
            and last.st_mtime_ns >= first.st_mtime_ns and offset + len(row) <= first.st_size, 'CSV replaced/truncated during read')
        return dict(raw=header+row, source_csv=dict(path=str(path), regular_file=True, opened_nofollow=True,
            fd_before=identity(first), path_before=identity(before), fd_after=identity(last), path_after=identity(after)),
            header_bytes=len(header), row_start_offset=offset, row_end_offset=offset+len(row),
            header_sha256=sha(header), row_sha256=sha(row))
    finally: os.close(fd)


def check_observation(value, spec):
    expected = spec['owner']; process = value['process']; env = value['environment']
    require(value['owner'] == expected and process['pid'] == expected['pid']
        and process['starttime_ticks'] == expected['starttime_ticks'] and process['uid'] == [os.getuid()] * 4
        and process['argv'] == spec['argv'] and process['cwd'] == spec['cwd'] and process['exe'] == spec['exe']
        and process['cgroup'] == '0::' + expected['cgroup'], 'Actual process identity/command/UID/cgroup differs')
    require(env == spec['environment'] and env.get('DQN_BATCH_SIZE') == '2048'
        and env.get('DQN_PER_PRIORITY_METRIC') == 'ce' and not any(k in env for k in FLAGS)
        and env.get('DQN_PRIORITY_PHASE_RECORD') == spec['phase_record']['path']
        and env.get('DQN_PRIORITY_PHASE_RECORD_SHA256') == spec['phase_record']['sha256'], 'Actual configured phase/profile differs')
    fields, micros = unit_start(value['unit'], expected)
    unit_env = dict(v.split('=',1) for v in shlex.split(fields.get('Environment','')) if '=' in v)
    require(all(unit_env.get(k) == env[k] for k in ('DQN_BATCH_SIZE','DQN_PER_PRIORITY_METRIC',
        'DQN_PRIORITY_PHASE_RECORD','DQN_PRIORITY_PHASE_RECORD_SHA256','ROBOTRON_RUN_DIR')), 'Unit/proc configured environment differs')
    return micros


def capture_live(spec, output, host=None):
    fields = {'schema','profile','owner','owner_pin','phase_record','boot_verification','source_pins',
              'game_root','environment','argv','cwd','exe','experiment','boot_id'}
    require(set(spec) == fields and spec['schema'] == 'robotron-batch2048-producer-live-capture-spec-v1', 'Exact capture spec required')
    owner(spec['owner']); require(read_json(spec['owner_pin']) == spec['owner'], 'Actual adopted owner PIN differs')
    require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',spec['boot_id'] or ''), 'Actual boot identity required')
    require(spec['profile']['path'] == str(PROFILE) and spec['profile']['sha256'] == PROFILE_SHA
        and spec['profile']['bytes'] == 764, 'Exact profile required'); profile = read_json(spec['profile'])
    record = read_json(spec['phase_record']); boot = read_json(spec['boot_verification'])
    require(profile['batch_size'] == 2048 and record['metric'] == 'ce' and record['action'] == 'start'
        and record['previous_metric'] == 'ce' and boot['status'] == 'PASS' and boot.get('phase_metadata_verified') is True
        and boot.get('saved_priority_metric_phase',{}).get('metric') == 'ce'
        and boot['saved_priority_metric_phase'].get('valid') is True
        and record['checkpoint']['sha256'] == boot['sha256'] and record['checkpoint']['bytes'] == boot['bytes'], 'Actual CE treatment founder/boot differs')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,120}', spec['experiment'] or '') and set(spec['source_pins']) == SOURCES, 'Source/experiment scope differs')
    source_raw = {}
    for name, pin in spec['source_pins'].items():
        require(pin['path'] == str(absolute(spec['game_root']) / 'Scripts/dqn' / name), 'Source path escaped')
        source_raw[name] = read_pin(pin, readonly=False)
    host = ReadOnlyHost() if host is None else host
    started = host.clock(); before = host.observe(spec['owner']); start_us = check_observation(before, spec)
    csv_data = host.csv(absolute(before['environment']['ROBOTRON_RUN_DIR']) / 'training.csv')
    after = host.observe(spec['owner']); end_us = check_observation(after, spec); finished = host.clock()
    require(started['boot_id'] == finished['boot_id'] == spec['boot_id'] and start_us == end_us
        and 0 <= finished['monotonic_s'] - started['monotonic_s'] <= MAX_SECONDS
        and started['unix_s'] <= finished['unix_s'], 'Capture clock/owner bound differs')
    require(before['environment'] == after['environment'] and before['process'] == after['process'], 'Producer changed across capture')
    u0,_=unit_start(before['unit'],spec['owner']);u1,_=unit_start(after['unit'],spec['owner'])
    require(all(u0.get(k)==u1.get(k) for k in ('MainPID','ExecMainPID','InvocationID','ControlGroup','NRestarts','Restart',
        'ExecMainStartTimestamp','ExecMainStartTimestampMonotonic','Environment')), 'Unit changed across capture')
    raw = csv_data['raw']; table = list(csv.reader(io.StringIO(raw.decode())))
    require(len(table) == 2 and len(table[0]) == len(table[1]) and len(set(table[0])) == len(table[0]), 'Exact unique CSV header/one row required')
    parsed = list(csv.DictReader(io.StringIO(raw.decode())))
    require(len(parsed) == 1 and parsed[0]['batch_size'] == '2048', 'No genuine current2048 row')
    row = parsed[0]; stamp = row['utc']; require(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?\+00:00',stamp), 'UTC row precision missing')
    dt = datetime.fromisoformat(stamp); delta = dt - datetime(1970,1,1,tzinfo=timezone.utc)
    row_us = (delta.days*86400+delta.seconds)*1000000+delta.microseconds
    require(start_us <= row_us and Decimal(row_us)/1000000 <= Decimal(str(finished['unix_s']))
        and Decimal(start_us)/1000000 <= Decimal(str(started['unix_s']))
        and row['experiment'] == spec['experiment'] and row['measurement_active'] == 'False', 'CSV historical/future/wrong experiment/mode')
    for field, key in (('steps','training_steps'),('optimized_samples','optimized_samples'),('learner_frames','learner_frame_count'),('frames','frame_count')):
        require(type(boot['clocks'][key]) is int and boot['clocks'][key] > 0
            and row[field].isdecimal() and int(row[field]) >= boot['clocks'][key], 'CSV predates genuine boot: '+key)
    writer = Writer(output)
    env0=writer.put('environment-before.json',before['environment']); env1=writer.put('environment-after.json',after['environment'])
    unit0=writer.put('unit-before.json',before['unit']); unit1=writer.put('unit-after.json',after['unit']); csv_pin=writer.put('producer-row.csv',raw)
    origin=dict(schema='robotron-root-batch2048-producer-CSV-origin-v2',owner_before=spec['owner'],owner_after=spec['owner'],
        environment_before=env0,environment_after=env1,unit_before=unit0,unit_after=unit1,csv_archive=csv_pin,
        **{k:v for k,v in csv_data.items() if k!='raw'},observed_before_unix_s=started['unix_s'],observed_after_unix_s=finished['unix_s'])
    origin_pin=writer.put('producer-origin.json',origin)
    archives={name:writer.put('source-'+name+'.txt',raw) for name,raw in sorted(source_raw.items())}
    for pin in writer.pins:read_pin(pin)
    for key in ('profile','owner_pin','phase_record','boot_verification'):read_pin(spec[key])
    for name,pin in spec['source_pins'].items():require(read_pin(pin,readonly=False)==source_raw[name],'Source changed across live capture')
    result=dict(schema='robotron-batch2048-live-producer-capture-v1',status='CAPTURED_ONLY',spec=spec,
        environment=env0,trainer_unit=unit0,csv=csv_pin,csv_origin=origin_pin,source_archives=archives,
        producer_started_unix_s=float(Decimal(start_us)/1000000),observed_unix_s=finished['unix_s'],
        clock_before=started,clock_after=finished,process_before=before['process'],process_after=after['process'],
        artifacts=list(writer.pins),checkpoint=None,acquisition=None,phase_CPU_verified=False,qualification_pass=False)
    return writer.put('capture.json',result)


def bind_capture(capture_pin, source, acquisition_pin, output):
    """Only immutable metadata: no live owner, CSV, source-code or .pt reads."""
    capture=read_json(capture_pin); require(capture['status']=='CAPTURED_ONLY'
        and capture['schema']=='robotron-batch2048-live-producer-capture-v1', 'Actual live capture required')
    for pin in capture['artifacts']:read_pin(pin)
    spec=capture['spec']; acquisition=read_json(acquisition_pin); source=pin_shape(source)
    require(acquisition['schema']=='robotron-owned-phase-snapshot-acquisition-v1'
        and acquisition['purpose'] in ('startup','candidate','newest_stopped')
        and acquisition['owner_before']==acquisition['owner_after']==spec['owner']
        and acquisition['source_checkpoint']==triple(source) and acquisition['experiment']==spec['experiment']
        and acquisition['phase_record_sha256']==spec['phase_record']['sha256']
        and acquisition['boot_checkpoint']==read_json(spec['phase_record'])['checkpoint'], 'Final historical acquisition does not join capture/phase/source')
    require(type(acquisition['client_count']) is int and acquisition['client_count'] in (0,192), 'Honest client scope required')
    origin=read_json(capture['csv_origin']);require(origin['owner_before']==origin['owner_after']==spec['owner'], 'Historical capture owner changed')
    observation=dict(schema='robotron-root-batch2048-producer-observation-v1',experiment=spec['experiment'],profile_sha256=PROFILE_SHA,
        owner=spec['owner'],source_checkpoint=triple(source),acquisition_sha256=acquisition_pin['sha256'],environment=capture['environment'],
        trainer_unit=capture['trainer_unit'],csv=capture['csv'],csv_scope='producer2048',csv_origin=capture['csv_origin'],
        producer_started_unix_s=capture['producer_started_unix_s'],observed_unix_s=capture['observed_unix_s'])
    writer=Writer(output); pin=writer.put('producer-observation.json',observation)
    writer.put('binding-receipt.json',dict(status='BOUND_PENDING_PHASE_CPU',capture=capture_pin,source=source,acquisition=acquisition_pin,
        producer_observation=pin,historical_capture_reused=True,owner_reobserved=False,capture_time_relabelled=False,
        checkpoint_opened=False,phase_CPU_verified=False,qualification_pass=False))
    for artifact in capture['artifacts']:read_pin(artifact)
    require(read_json(capture_pin)==capture and read_json(acquisition_pin)==acquisition,'Binding metadata changed')
    return pin


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--expected-job-sha256');parser.add_argument('--expected-source-sha256')
    args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: two-stage metadata capture/bind; no reads/imports/runtime/output/actions');return 0
    try:
        require(args.job is not None and 'LD_PRELOAD' not in os.environ and 'PYTHONPATH' not in os.environ
            and os.environ.get('CUDA_VISIBLE_DEVICES')=='','Explicit root job/CUDAhidden clean parent required')
        raw,_=bounded_read(Path(__file__).resolve(),MAX_FILE);require(sha(raw)==args.expected_source_sha256,'Collector source changed')
        raw,ident=bounded_read(args.job,MAX_FILE);require(sha(raw)==args.expected_job_sha256 and ident['mode']=='0o444'
            and ident['uid']==os.getuid() and ident['nlink']==1,'Exact owned immutable root job required');job=json.loads(raw)
        require(job['schema']=='robotron-batch2048-producer-collector-job-v1','Root schema differs')
        if job['operation']=='capture':
            require(set(job)=={'schema','operation','spec','output_directory'},'Capture job fields differ');pin=capture_live(job['spec'],job['output_directory'])
        else:
            require(job['operation']=='bind' and set(job)=={'schema','operation','capture','source','acquisition','output_directory'},'Binding job fields differ')
            pin=bind_capture(job['capture'],job['source'],job['acquisition'],job['output_directory'])
        print(json.dumps(dict(status='METADATA_ONLY',result=pin,phase_CPU_verified=False),sort_keys=True));return 0
    except Exception:
        traceback.print_exc();return 1


if __name__=='__main__':
    raise SystemExit(main())
