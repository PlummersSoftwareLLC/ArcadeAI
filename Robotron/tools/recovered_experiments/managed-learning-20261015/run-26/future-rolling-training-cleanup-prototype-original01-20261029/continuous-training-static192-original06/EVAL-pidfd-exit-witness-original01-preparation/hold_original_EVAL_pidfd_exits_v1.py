"""Default inert. Root-only retained kernel exit witnesses for37 original EVALs.

Opens pidfds while selected original processes are alive. Never sends signals,
waits for/reaps actors, reads models, changes files outside its fresh output,
or claims that an original supervisor Popen.wait call was instrumented.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import struct
import sys
import time

BASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06')
CAPABILITY_SHA = '062f042870a5c6d546156734128d32455e30814f6e2d258b6de6bc698ab8dbca'
REQUEST_IOCTL = 0xc050ff0b
REQUEST_MASK = 0x28
EXIT = 8
SUPPORTED = 32
LIMIT = 2_000_000


def require(value, reason):
    if not value:
        raise ValueError(reason)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
        mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(),
            'Canonical selected metadata/source required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        first = os.fstat(fd); before = identity(first)
        require(stat.S_ISREG(first.st_mode) and 0 < first.st_size <= LIMIT,
                'Bounded regular metadata/source required')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            raw = stream.read(LIMIT + 1)
        require(len(raw) == first.st_size and identity(os.fstat(fd)) == before
                and identity(path.lstat()) == before, 'Selected input changed during read')
    finally:
        os.close(fd)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), identity=before)


def read(value):
    require(type(value) is dict and set(value) == {'path','sha256','bytes','identity'}
            and value['identity']['mode'] == '0o444'
            and value['identity']['uid'] == os.getuid() and value['identity']['nlink'] == 1
            and pin(value['path']) == value, 'Exact immutable owned metadata required')
    raw = Path(value['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == value['sha256']
            and pin(value['path']) == value, 'Metadata changed after check')
    return json.loads(raw)


def put(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    require(len(raw) <= LIMIT, 'Bounded witness metadata required')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    return pin(path)


def heartbeat(path, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    require(len(raw) <= 128 << 10, 'Bounded live holder heartbeat required')
    temporary = path.with_name('.holder-live.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def process(pid):
    root = Path('/proc', str(pid))
    raw = (root / 'stat').read_text().rsplit(')', 1)[1].split()
    return dict(pid=pid, birth=int(raw[19]), parent=int(raw[1]),
                state=raw[0], uid=root.stat().st_uid)


def cgroup():
    lines = Path('/proc/self/cgroup').read_text().splitlines()
    require(len(lines) == 1 and lines[0].startswith('0::/'), 'Exact cgroup-v2 holder required')
    return lines[0][3:]


def holder(unit):
    value = process(os.getpid()); value.pop('state')
    inv = os.environ.get('INVOCATION_ID', '')
    group = cgroup()
    require(re.fullmatch('[0-9a-f]{32}', inv) is not None
            and inv != '0' * 32 and Path(group).name == unit,
            'Actual original owned systemd service invocation required')
    value.update(unit=unit, invocation_id=inv, cgroup=group)
    return value


def fd_identity(fd):
    s = os.fstat(fd)
    require(s.st_ino > 0, 'Actual retained pidfd inode required')
    return dict(device=s.st_dev, inode=s.st_ino, mode=oct(s.st_mode), uid=s.st_uid)


def info(fd):
    raw = bytearray(80)
    struct.pack_into('=Q', raw, 0, REQUEST_MASK)
    fcntl.ioctl(fd, REQUEST_IOCTL, raw, True)
    fields = ('returned_mask','cgroupid','pid','tgid','ppid','ruid','rgid','euid','egid',
              'suid','sgid','fsuid','fsgid','exit_code_raw','coredump_mask',
              'coredump_signal','supported_mask')
    value = dict(zip(fields, struct.unpack('=QQ11IiIIQ', raw)))
    require(value['returned_mask'] & SUPPORTED and value['supported_mask'] & EXIT,
            'Actual kernel must report support for retained exit info')
    value['raw80_hex'] = raw.hex()
    return value


def validate_selection(value, source):
    require(set(value) == {'schema','nonce','unit','output','original_case','capability','originals'}
            and value['schema'] == 'robotron-root-original37-EVAL-pidfd-witness-selection-v1'
            and re.fullmatch('[0-9a-f]{32}', value['nonce'] or '') is not None
            and value['nonce'] != '0' * 32
            and re.fullmatch(r'robotron-[A-Za-z0-9_.@-]+\.service', value['unit'] or '') is not None,
            'Exact prospective original37 EVAL selection required')
    case = read(value['original_case']); cap = read(value['capability'])
    require(value['capability']['sha256'] == CAPABILITY_SHA
            and cap['schema'] == 'robotron-root-pidfd-get-info-own-synthetic-capability-v1'
            and cap['status'] == 'PASS_ACTUAL_KERNEL_AFTER_REAP_EXIT_INFO_NORMAL_SIGNAL_NONCHILD'
            and cap['pidfd_info_size'] == 80 and cap['ioctl_hex'] == hex(REQUEST_IOCTL)
            and cap['alive_zero_not_treated_as_exit_proof'] is True,
            'Exact actual deployed-kernel capability qualification required')
    require(os.uname().release == cap['kernel_release']
            and os.uname().machine == cap['machine'] == 'aarch64' and sys.byteorder == 'little',
            'The actual qualified kernel and little-endian ABI are required')
    require(case['schema'] == 'robotron-continuous-static192-health-case-v1'
            and set(case['slot_eval']) == set(map(str,range(192)))
            and all(type(v) is bool for v in case['slot_eval'].values())
            and sum(case['slot_eval'].values()) == 37,
            'Immutable original192 physical anchor authority required')
    slots = {k for k,v in case['slot_eval'].items() if v is True}
    require(set(value['originals']) == slots and len(slots) == 37, 'Exactly the37 selected EVAL slots required')
    births = set()
    for slot, row in value['originals'].items():
        original = case['continuous']['original_slots'][slot]
        child = original['original_child']; bound = read(original['connection_binding'])
        actor = bound['data']['actor']; conn = bound['data']['connection']
        require(set(row) == {'pid','birth','parent','uid','initial_connection_binding'}
                and all(type(row[k]) is int for k in ('pid','birth','parent','uid'))
                and original['eval_only'] is True and original['incarnation'] == 1
                and row['pid'] == child['pid'] == actor['pid']
                and row['birth'] == child['birth'] == actor['birth']
                and row['parent'] == child['parent'] == actor['parent']
                and row['uid'] == actor['uid'] == os.getuid() == source['identity']['uid']
                and row['initial_connection_binding'] == original['connection_binding']
                and conn['client_slot'] == int(slot) and conn['eval_only'] is True,
                'Selected EVAL is not its exact original physical/connection anchor')
        pair = (row['pid'],row['birth']); require(pair not in births, 'Duplicate original birth')
        births.add(pair)
    out = Path(value['output'])
    require(out.is_absolute() and out.resolve() == out and out.is_relative_to(BASE)
            and out.parent.is_dir() and not out.exists(), 'One fresh owned witness output required')
    return case, out


def run(selection_path, selection_sha, source_sha):
    source = pin(Path(__file__).resolve())
    require(source['sha256'] == source_sha and source['identity']['mode'] == '0o444',
            'Exact frozen Root-selected witness source required')
    selected = pin(selection_path)
    require(selected['sha256'] == selection_sha, 'Exact actual Root selection SHA required')
    selection = read(selected); case, out = validate_selection(selection, source)
    own = holder(selection['unit'])
    out.mkdir(mode=0o700)
    held = {}; anchors_pin = None; receipts = {}; stopping = False
    def stop(*unused):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    common = dict(selection=selected, source=source, holder=own, nonce=selection['nonce'],
                  original_case=selection['original_case'], request_ioctl=REQUEST_IOCTL,
                  request_ioctl_hex=hex(REQUEST_IOCTL), request_mask=REQUEST_MASK)
    try:
        for slot, original in sorted(selection['originals'].items(), key=lambda v:int(v[0])):
            begin_ns = time.monotonic_ns(); begin_unix = time.time()
            before = process(original['pid'])
            require(all(before[k] == original[k] for k in ('pid','birth','parent','uid'))
                    and before['state'] not in ('Z','X','x'), 'Original EVAL must be alive before pidfd acquisition')
            fd = os.pidfd_open(original['pid'], 0)
            held[slot] = dict(fd=fd, original=original)
            descriptor = fd_identity(fd)
            rawfd = Path('/proc/self/fdinfo', str(fd)).read_text()
            require(len(rawfd) <= 16384, 'Bounded pidfd fdinfo required')
            fdinfo = dict(line.split(':',1) for line in rawfd.splitlines() if ':' in line)
            initial = info(fd); after = process(original['pid'])
            require(int(fdinfo['Pid'].strip()) == original['pid']
                    and initial['returned_mask'] & 3 == 3 and not initial['returned_mask'] & EXIT
                    and initial['pid'] == initial['tgid'] == original['pid']
                    and initial['ppid'] == original['parent']
                    and initial['ruid'] == initial['euid'] == original['uid']
                    and all(after[k] == original[k] for k in ('pid','birth','parent','uid'))
                    and after['state'] not in ('Z','X','x') and fd_identity(fd) == descriptor,
                    'Live original identity changed across pidfd acquisition')
            held[slot]['anchor'] = dict(slot=int(slot), original=original, descriptor=descriptor,
                fd_number=fd, initial_info=initial, initial_fdinfo=rawfd,
                capture_begin_monotonic_ns=begin_ns,capture_end_monotonic_ns=time.monotonic_ns(),
                capture_begin_unix_s=begin_unix,capture_end_unix_s=time.time())
        require(holder(selection['unit']) == own and len(held) == 37,
                'Original holder changed before all37 anchors were durable')
        anchors_pin = put(out/'held-original37-anchors.json', dict(common,
            schema='robotron-original37-EVAL-pidfd-held-anchors-v1',
            originals={s:v['anchor'] for s,v in held.items()},all37_acquired_while_originals_live=True,
            actor_signals_or_wait_or_reap_performed=False,observed_unix_s=time.time(),
            observed_monotonic_ns=time.monotonic_ns()))
        while len(receipts) < 37 and not stopping:
            require(holder(selection['unit']) == own, 'Retained holder identity changed')
            heartbeat(out/'holder-live.json',dict(common,
                schema='robotron-original37-EVAL-pidfd-holder-live-v1',state='HOLDING_UNRESOLVED_ORIGINALS',
                anchors=anchors_pin,exit_receipts=dict(receipts),
                unresolved_slots=sorted(set(held)-set(receipts),key=int),
                updated_unix_s=time.time(),updated_monotonic_ns=time.monotonic_ns()))
            for slot, item in held.items():
                if slot in receipts:
                    continue
                fd = item['fd']; anchor = item['anchor']; original = item['original']
                require(fd_identity(fd) == anchor['descriptor'], 'Retained pidfd descriptor changed')
                begin_ns = time.monotonic_ns(); returned = info(fd)
                if not returned['returned_mask'] & EXIT:
                    continue
                try:
                    current = process(original['pid'])
                except (FileNotFoundError, ProcessLookupError):
                    current = None
                absent = current is None or current['birth'] != original['birth']
                if not absent:
                    continue
                raw = returned['exit_code_raw']
                normal = os.WIFEXITED(raw); status = os.WEXITSTATUS(raw) if normal else None
                signalled = os.WIFSIGNALED(raw); term = os.WTERMSIG(raw) if signalled else None
                zero = normal and status == 0
                receipts[slot] = put(out/('exit-slot-%03d.json'%int(slot)),dict(common,
                    schema='robotron-original-EVAL-retained-pidfd-exit-v1', anchors=anchors_pin,
                    slot=int(slot), original=original, anchor=anchor,descriptor=anchor['descriptor'],
                    returned_info=returned,returned_raw80_hex=returned['raw80_hex'],
                    kernel_exit_flag_returned=True,raw_wait_status=raw,normal_exit=normal,
                    normal_exit_status=status,signal_termination=signalled,termination_signal=term,
                    normal_exit_zero=zero,original_birth_absent=True,observed_process_at_original_pid=current,
                    status='KERNEL_REAPED_NORMAL0'if zero else'KERNEL_REAPED_NONZERO_OR_SIGNAL'if normal or signalled else'KERNEL_REAPED_OTHER_WAIT_STATUS',
                    capture_begin_monotonic_ns=begin_ns,capture_end_monotonic_ns=time.monotonic_ns(),
                    observed_unix_s=time.time(),observed_monotonic_ns=time.monotonic_ns(),
                    original_Popen_wait_called_claimed=False,actor_signals_or_wait_or_reap_performed=False))
            if len(receipts) < 37:
                time.sleep(.5)
        complete = len(receipts) == 37
        all_zero = complete and all(read(r)['normal_exit_zero'] for r in receipts.values())
        return put(out/'holder-terminal.json',dict(common,
            schema='robotron-original37-EVAL-pidfd-holder-terminal-v1',anchors=anchors_pin,
            status='ALL37_REAPED_NORMAL0'if all_zero else'ALL37_REAPED_WITH_NONZERO_OR_SIGNAL'if complete else'INTERRUPTED_WITH_UNRESOLVED_ORIGINALS',
            exit_receipts=receipts,unresolved_slots=sorted(set(held)-set(receipts),key=int),
            all37_exit_receipts_present=complete,all37_normal_zero=all_zero,
            original_Popen_wait_called_claimed=False,actor_signals_or_wait_or_reap_performed=False,
            observed_unix_s=time.time(),observed_monotonic_ns=time.monotonic_ns()))
    except BaseException as error:
        put(out/'holder-failure.json',dict(common,schema='robotron-original37-EVAL-pidfd-holder-failure-v1',
            error=repr(error),anchors=anchors_pin,acquired_slots=sorted(held,key=int),
            exit_receipts=receipts,all37_exit_receipts_present=False,
            actor_signals_or_wait_or_reap_performed=False,observed_unix_s=time.time(),
            observed_monotonic_ns=time.monotonic_ns()))
        raise
    finally:
        for item in held.values():
            os.close(item['fd'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true');p.add_argument('--selection',type=Path)
    p.add_argument('--selection-sha256');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if not a.execute:
        print('SOURCE_ONLY_INERT_NO_READS_OR_PIDFD_CALLS');return
    require(a.selection and a.selection_sha256 and a.expected_source_sha256,'Explicit exact Root selection/source required')
    print(json.dumps(run(a.selection,a.selection_sha256,a.expected_source_sha256)),flush=True)


if __name__ == '__main__':
    main()
