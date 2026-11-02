"""Root's single, fixed native CPU validation. No quality/capture operation."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI')
GAME = ROOT / 'Robotron'
RUN = GAME / 'logs/managed-learning-20261015/run-26'
HERE = Path(__file__).resolve().parent
OUT = RUN / 'continuous-zero-dip-wave2-reviewed2-CPU-original01-root-execution-20261018'
PACKET = GAME / 'tools/continuous_zero_dip_wave2_proposal/preparation-reviewed2-manifest.json'
PACKET_SHA = '947981d64af6c3cfce1d7191f1a02ce40f8ca79b5273aaee0dcc7a43b1760fd4'
PEER = RUN / 'continuous-zero-dip-wave2-reviewed2-independent-source-review-20261018/source-review-receipt.json'
UNIT = 'robotron-continuous-zero-dip-wave2-reviewed2-CPU-original01-20261018.service'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def pin(path):
    path = Path(path)
    require(path.suffix not in ('.pt', '.pth'), 'Source/metadata only')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        a = os.fstat(stream.fileno())
        raw = stream.read((4 << 20) + 1)
        z = os.fstat(stream.fileno())
    require(stat.S_ISREG(a.st_mode) and a.st_size <= 4 << 20
            and (a.st_ino, a.st_mtime_ns, a.st_ctime_ns, a.st_size)
            == (z.st_ino, z.st_mtime_ns, z.st_ctime_ns, z.st_size), 'File changed')
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                identity=dict(device=a.st_dev, inode=a.st_ino, bytes=a.st_size,
                              mtime_ns=a.st_mtime_ns, ctime_ns=a.st_ctime_ns,
                              mode=oct(stat.S_IMODE(a.st_mode)), uid=a.st_uid, nlink=a.st_nlink))


def publish(name, value):
    target = OUT / name
    raw = (json.dumps(value, indent=2) + '\n').encode()
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(target)


def command(label, argv):
    start = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=25)
        value = dict(argv=argv, exit=r.returncode, stdout=r.stdout, stderr=r.stderr,
                     timed_out=False)
    except subprocess.TimeoutExpired as e:
        as_text = lambda x: x.decode() if isinstance(x, bytes) else (x or '')
        value = dict(argv=argv, exit=None, stdout=as_text(e.stdout),
                     stderr=as_text(e.stderr), timed_out=True)
    value.update(started_unix_s=start, ended_unix_s=time.time())
    record = publish(label + '.json', value)
    return value, record


def fields(value):
    require(value['exit'] == 0 and not value['timed_out'], 'Command did not complete')
    return dict(line.split('=', 1) for line in value['stdout'].splitlines() if '=' in line)


def show():
    r = subprocess.run(['systemctl', '--user', 'show', UNIT, '--all'],
                       capture_output=True, text=True, timeout=10)
    require(r.returncode == 0, r.stderr)
    return dict(line.split('=', 1) for line in r.stdout.splitlines() if '=' in line)


def run(args):
    require(pin(__file__)['sha256'] == args.expected_source_sha256, 'Controller SHA differs')
    packet_pin = pin(PACKET)
    require(packet_pin['sha256'] == PACKET_SHA, 'Selected packet differs')
    manifest = json.loads(PACKET.read_text())
    entries = manifest['files'] + manifest['upstreams']
    for entry in entries:
        require(pin(entry['path']) == entry, 'Input changed: ' + entry['path'])
    peer_pin = pin(PEER)
    require(peer_pin['sha256'] == args.peer_sha256, 'Independent review differs')
    peer = json.loads(PEER.read_text())
    require('PASS' in peer['status'] and 'SOURCE' in peer['status'], 'Source review not passed')
    require(not OUT.exists(), 'Original output already exists; no rerun')
    require(show().get('LoadState') == 'not-found', 'Original unit name already exists')
    require(Path('/proc/2863379/stat').read_text().rsplit(')', 1)[1].split()[19] == '39797375',
            'Original trainer identity changed')
    OUT.mkdir()
    (OUT / 'work').mkdir()
    (OUT / 'tmp').mkdir()
    properties = ['Type=exec', 'WorkingDirectory=' + str(ROOT), 'Restart=no',
                  'RemainAfterExit=yes', 'CollectMode=inactive', 'MemoryMax=4G',
                  'MemorySwapMax=0', 'CPUQuota=200%', 'TasksMax=128',
                  'RuntimeMaxSec=180s', 'TimeoutStopSec=5s',
                  'StandardOutput=append:' + str(OUT / 'stdout.txt'),
                  'StandardError=append:' + str(OUT / 'stderr.txt')]
    argv = ['systemd-run', '--user', '--unit=' + UNIT]
    argv += ['--property=' + p for p in properties]
    argv += ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH',
             'CUDA_VISIBLE_DEVICES=', 'PYTHONDONTWRITEBYTECODE=1',
             'OMP_NUM_THREADS=2', 'MKL_NUM_THREADS=2', 'OPENBLAS_NUM_THREADS=2',
             'NUMEXPR_NUM_THREADS=2', 'ROBOTRON_ALLOW_ZERO_DIP_WIRE_TEST=1',
             'ROBOTRON_ZERO_DIP_TEST_WORK_ROOT=' + str(OUT / 'work'),
             'TMPDIR=' + str(OUT / 'tmp'), '/usr/bin/python3.12', '-I', '-B',
             str(HERE / 'payload_entry.py')]
    precommit = publish('root-execution-precommit.json', dict(
        schema='robotron-root-zero-dip-reviewed2-native-CPU-precommit-v1',
        selected_unix_s=time.time(), unit=UNIT, actual_argv=argv,
        controller=pin(__file__), payload_entry=pin(HERE / 'payload_entry.py'),
        selected_packet=packet_pin, independent_source_review=peer_pin,
        input_pins=entries, original_attempt=1, retry=False, model_or_quality_operation=False))
    launched, launch_pin = command('root-native-launch', argv)
    require(launched['exit'] == 0 and not launched['timed_out'], 'Original launch failed')
    owner = None
    observe_deadline = time.monotonic() + 12
    while time.monotonic() < observe_deadline:
        s = show()
        if int(s.get('MainPID', '0')) > 0:
            pid = int(s['MainPID'])
            ticks = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
            require(s['NRestarts'] == '0' and s['ActiveState'] == 'active'
                    and s['SubState'] == 'running' and s['InvocationID'], 'Unexpected owner')
            owner = dict(unit=UNIT, pid=pid, starttime_ticks=ticks,
                         invocation_id=s['InvocationID'], observed_live=True,
                         control_group=s['ControlGroup'], NRestarts=0)
            publish('root-original-live-owner.json', owner)
            print(json.dumps(dict(status='ORIGINAL_NATIVE_CPU_OBSERVED_LIVE', original=owner)), flush=True)
            break
        time.sleep(.05)
    require(owner is not None, 'Original was not observed live; no retry')
    deadline = time.monotonic() + 210
    while time.monotonic() < deadline:
        s = show()
        require(s['InvocationID'] == owner['invocation_id'] and s['NRestarts'] == '0',
                'Original unit identity changed')
        if s['MainPID'] == '0' and s['SubState'] in ('exited', 'failed', 'dead'):
            break
        require(int(s['MainPID']) == owner['pid'], 'Unexpected running owner')
        require(int(Path(f"/proc/{owner['pid']}/stat").read_text().rsplit(')', 1)[1].split()[19])
                == owner['starttime_ticks'], 'PID reused')
        time.sleep(.25)
    else:
        publish('root-observation-expired-original-not-restarted.json', owner)
        raise RuntimeError('Observation expired; inspect same native unit, never rerun')
    require(s['ExecMainPID'] == str(owner['pid']),
            'Wrong terminal original')
    archives = []
    for label, cmd in (
        ('original-service-show', ['systemctl', '--user', 'show', UNIT, '--all']),
        ('original-service-cat', ['systemctl', '--user', 'cat', UNIT]),
        ('original-invocation-journal', ['journalctl', '--user', '--no-pager', '-o',
                                       'short-iso', '_SYSTEMD_INVOCATION_ID=' + owner['invocation_id']])):
        value, evidence = command(label, cmd)
        archives.append(dict(record=evidence, exit=value['exit'], timed_out=value['timed_out'],
                             ended_unix_s=value['ended_unix_s']))
    require(all(a['exit'] == 0 and not a['timed_out'] for a in archives),
            'Archive incomplete; no release')
    for entry in entries:
        require(pin(entry['path']) == entry, 'Input drift after test')
    current = show()
    require(current['InvocationID'] == owner['invocation_id']
            and current['ExecMainPID'] == str(owner['pid']) and current['MainPID'] == '0'
            and current['NRestarts'] == '0', 'Terminal owner changed before release')
    group = Path('/sys/fs/cgroup') / owner['control_group'].lstrip('/') / 'cgroup.procs'
    require(not group.exists() or not group.read_text().strip(), 'Original descendants remain')
    stopped, stop_pin = command('original-owned-service-stop-once', ['systemctl', '--user', 'stop', UNIT])
    after, after_pin = command('original-service-after-release', ['systemctl', '--user', 'show', UNIT, '--all'])
    final = fields(after)
    result = dict(schema='robotron-root-zero-dip-reviewed2-original-native-CPU-result-v1',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), original=owner,
        precommit=precommit, launch=launch_pin, native_code=int(s['ExecMainCode']),
        native_exit=int(s['ExecMainStatus']), native_result=s['Result'],
        archives=archives, archives_before_stop=max(a['ended_unix_s'] for a in archives)
        < stopped['started_unix_s'], owned_stop=stop_pin, after_release=after_pin,
        stop_exit=stopped['exit'], unit_after_load_state=final.get('LoadState'),
        unit_released=stopped['exit'] == 0 and final.get('LoadState') == 'not-found',
        failed_descriptor_retained=final.get('ActiveState') == 'failed',
        memory_peak_bytes=s.get('MemoryPeak'), source_pins_unchanged=True,
        stdout=pin(OUT / 'stdout.txt'), stderr=pin(OUT / 'stderr.txt'),
        original_attempt=1, retry=False, reset_failed=False,
        model_or_quality_operation=False, production_source_changed=False)
    result['status'] = 'PASS_NATIVE0_OWNED_RELEASED' if (
        result['native_exit'] == 0 and result['native_result'] == 'success'
        and result['unit_released']) else 'ORIGINAL_NATIVE_RESULT_REQUIRES_REVIEW'
    receipt = publish('root-original-native-CPU-result-and-owned-release.json', result)
    fd = os.open(OUT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps(dict(status=result['status'], result=receipt, native_exit=result['native_exit'],
                          unit_released=result['unit_released'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', required=True)
    parser.add_argument('--expected-source-sha256', required=True)
    parser.add_argument('--peer-sha256', required=True)
    run(parser.parse_args())
