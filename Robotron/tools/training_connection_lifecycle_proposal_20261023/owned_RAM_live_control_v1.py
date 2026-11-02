"""Owned ephemeral live-control location; codec and durable evidence stay separate.

Callers must authenticate the actual worker scope before requesting release.
Independent review must also authenticate that scope; this helper is not a
scientific or systemd authority. Import performs no I/O or resource allocation.
"""
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time

SCHEMA = 'robotron-owned-RAM-live-control-v1'
BASE = Path('/dev/shm')
PREFIX = 'robotron-main-health-live-'
LIMIT = 65536
TOKEN_KEYS = ('pid', 'birth', 'uid', 'unit', 'invocation_id', 'cgroup')
BINDING_KEYS = {'schema', 'nonce', 'parent', 'native_job', 'observer_unit', 'root',
                'root_identity', 'live_path', 'lock_path', 'helper', 'mount', 'created_monotonic_s'}


def require(value, message):
    if not value:
        raise ValueError(message)


def parent_token(parent):
    return {key: parent[key] for key in TOKEN_KEYS}


def directory_identity(path):
    value = Path(path).lstat()
    require(stat.S_ISDIR(value.st_mode), 'Original RAM control root must be a directory')
    return dict(device=value.st_dev, inode=value.st_ino, uid=value.st_uid,
                mode=oct(stat.S_IMODE(value.st_mode)), nlink=value.st_nlink)


def validate(binding, nonce, parent, native_job, h, *, present=True):
    require(type(binding) is dict and set(binding) == BINDING_KEYS and binding['schema'] == SCHEMA,
            'Exact RAM control binding fields required')
    require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce) is not None
            and binding['nonce'] == nonce and binding['parent'] == parent_token(parent)
            and binding['native_job'] == native_job, 'RAM control nonce/parent/native job differs')
    require(binding['helper'] == h.pin(__file__), 'RAM control helper source differs')
    root = BASE / (PREFIX + nonce)
    require(binding['root'] == str(root) and binding['live_path'] == str(root / 'live.json')
            and binding['lock_path'] == str(root / 'live.json.lock'), 'RAM control path escaped its nonce directory')
    token = binding['parent']
    require(type(token['pid']) is type(token['birth']) is int and token['pid'] > 0 and token['birth'] > 0
            and token['uid'] == os.geteuid() and re.fullmatch('robotron-[A-Za-z0-9_-]+[.]service', binding['observer_unit']) is not None,
            'Typed original RAM control owner and observer unit required')
    identity = binding['root_identity']
    require(type(identity) is dict and set(identity) == {'device', 'inode', 'uid', 'mode', 'nlink'}
            and type(identity['device']) is type(identity['inode']) is int and identity['inode'] > 0
            and identity['device'] == BASE.stat().st_dev and identity['uid'] == os.geteuid()
            and identity['mode'] == '0o700' and identity['nlink'] == 2,
            'Original owned700 single-directory RAM identity required')
    mount = binding['mount']
    require(type(mount) is dict and set(mount) == {'argv', 'exit', 'stdout', 'stderr'}
            and mount['argv'] == ['findmnt', '-T', '/dev/shm', '-n', '-o', 'FSTYPE']
            and type(mount['exit']) is int and mount['exit'] == 0 and mount['stdout'] == 'tmpfs\n'
            and mount['stderr'] == '', 'Actual tmpfs mount evidence required')
    clock = binding['created_monotonic_s']
    require(type(clock) in (int, float) and math.isfinite(clock) and 0 < clock <= time.monotonic(),
            'Original finite RAM creation clock required')
    if present:
        require(directory_identity(root) == identity and root.resolve() == root,
                'Original RAM directory identity changed')
    return root


def create(nonce, parent, native_job, observer_unit, h):
    require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce) is not None,
            'Fresh exact nonce required before RAM allocation')
    token = parent_token(parent)
    require(type(token['pid']) is type(token['birth']) is int and token['pid'] > 0 and token['birth'] > 0
            and token['uid'] == os.geteuid() and type(observer_unit) is str
            and re.fullmatch('robotron-[A-Za-z0-9_-]+[.]service', observer_unit) is not None,
            'Exact owner/unit required before RAM allocation')
    argv = ['findmnt', '-T', '/dev/shm', '-n', '-o', 'FSTYPE']
    result = subprocess.run(argv, capture_output=True, text=True, timeout=5)
    require(result.returncode == 0 and result.stdout == 'tmpfs\n' and result.stderr == '',
            'Live controls require the actual tmpfs mount')
    root = BASE / (PREFIX + nonce)
    root.mkdir(mode=0o700)  # Exclusive; an existing original is never adopted.
    binding = dict(schema=SCHEMA, nonce=nonce, parent=parent_token(parent), native_job=native_job,
                   observer_unit=observer_unit, root=str(root), root_identity=directory_identity(root),
                   live_path=str(root / 'live.json'), lock_path=str(root / 'live.json.lock'),
                   helper=h.pin(__file__), mount=dict(argv=argv, exit=result.returncode,
                   stdout=result.stdout, stderr=result.stderr), created_monotonic_s=time.monotonic())
    validate(binding, nonce, parent, native_job, h)
    return binding


def check_live(binding):
    """Only RAM metadata is read on the live path; full binding checks precede it."""
    root = Path(binding['root'])
    require(directory_identity(root) == binding['root_identity'] and root.resolve() == root,
            'Original live RAM control directory identity changed')


def file_shape(pin, binding, worker_pid):
    path = Path(pin['path'])
    root = Path(binding['root'])
    require(path.parent == root and path.name in ('live.json', 'live.json.lock',
            'live.json.' + str(worker_pid) + '.tmp'), 'Unknown RAM control member; preserve it')
    identity = pin['identity']
    require(identity['uid'] == binding['parent']['uid'] and identity['nlink'] == 1,
            'Original RAM member owner/link count differs')
    if path.name == 'live.json.lock':
        require(identity['mode'] == '0o600' and pin['bytes'] == 0, 'Original empty600 RAM live lock required')
    elif path.name == 'live.json':
        require(identity['mode'] == '0o644' and 0 < pin['bytes'] <= LIMIT, 'Original bounded644 RAM live bytes required')
    else:
        require(0 <= pin['bytes'] <= LIMIT and int(identity['mode'], 8) & 0o111 == 0,
                'Bounded non-executable interrupted RAM temporary file required')


def process_birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


def archive_and_release(binding, archive_root, h, *, worker_job, owner, closure):
    """Preserve exact original bytes, then release only this closed worker's root."""
    job = json.loads(h.checked(worker_job).read_bytes())
    original = json.loads(h.checked(owner).read_bytes())
    closed = json.loads(h.checked(closure).read_bytes())
    root = validate(binding, job['nonce'], job['parent'], job['native_job'], h)
    require(job['live_control'] == binding and job['live_control_helper'] == binding['helper']
            and original['unit'] == job['observer_unit'] == binding['observer_unit']
            and closed['original'] == original and closed['lifecycle_complete'] is True
            and closed['unit_released'] is True and closed['original_archived_before_release'] is True,
            'RAM release requires the original closed worker job/owner/closure')
    require(type(original['pid']) is type(original['starttime_ticks']) is int
            and original['pid'] > 0 and original['starttime_ticks'] > 0,
            'Typed original RAM writer birth required')
    require(process_birth(original['pid']) != original['starttime_ticks']
            and len(closed['owned_release']) == 2
            and {r['unit'] for r in closed['owned_release']} == {original['unit'], original['timer']}
            and all(r['confirmed_absent'] for r in closed['owned_release'])
            and not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', original['unit']).exists(),
            'RAM writer original process or scope remains')
    members = sorted(root.iterdir())
    require(len(members) <= 3, 'Unknown additional RAM members; preserve all originals')
    originals = []
    for path in members:
        value = path.lstat()
        require(stat.S_ISREG(value.st_mode) and not path.is_symlink(), 'RAM control member must be an original regular file')
        pin = h.pin(path)
        file_shape(pin, binding, original['pid'])
        originals.append(pin)
    archive_root = Path(archive_root)
    archive_root.mkdir(mode=0o700)
    files = []
    for pin in originals:
        data = h.checked(pin).read_bytes()
        require(h.pin(pin['path']) == pin, 'Original RAM bytes changed before durable archival')
        target = archive_root / (Path(pin['path']).name + '.original-bytes')
        with target.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        archived = h.pin(target)
        require(archived['sha256'] == pin['sha256'] and archived['bytes'] == pin['bytes'],
                'RAM original byte archive differs')
        files.append(dict(original=pin, archived=archived))
    intent = h.put(archive_root / 'original-control-archive-and-release-intent.json',
        dict(schema='robotron-RAM-control-release-intent-v1', binding=binding, worker_job=worker_job,
             owner=owner, closure=closure, files=files, root_before_release=directory_identity(root),
             all_original_bytes_durably_archived=True, created_monotonic_s=time.monotonic()))
    validate(binding, job['nonce'], job['parent'], job['native_job'], h)
    require({str(p) for p in root.iterdir()} == {p['path'] for p in originals}, 'RAM member set changed before release')
    for pin in originals:
        require(h.pin(pin['path']) == pin, 'RAM member identity changed before release')
    for pin in originals:
        Path(pin['path']).unlink()
    require(directory_identity(root) == binding['root_identity'], 'RAM directory identity changed before rmdir')
    root.rmdir()
    require(not root.exists() and not root.is_symlink(), 'Original RAM directory remains after release')
    return h.put(archive_root / 'original-owned-RAM-release-result.json',
        dict(schema='robotron-owned-RAM-control-release-result-v1', intent=intent, binding=binding,
             original_root_absent=True, original_members_absent=True, released_monotonic_s=time.monotonic()))


def verify_release(binding, release, expected_root, worker_job, owner, closure, read, h):
    job = read(worker_job)
    validate(binding, job['nonce'], job['parent'], job['native_job'], h, present=False)
    expected_root = Path(expected_root)
    result = read(release)
    require(release['path'] == str(expected_root / 'original-owned-RAM-release-result.json')
            and result['schema'] == 'robotron-owned-RAM-control-release-result-v1'
            and result['binding'] == binding and result['original_root_absent'] is True
            and result['original_members_absent'] is True, 'Original RAM release result differs')
    intent = read(result['intent'])
    require(result['intent']['path'] == str(expected_root / 'original-control-archive-and-release-intent.json')
            and intent['schema'] == 'robotron-RAM-control-release-intent-v1' and intent['binding'] == binding
            and intent['worker_job'] == worker_job and intent['owner'] == owner and intent['closure'] == closure
            and intent['root_before_release'] == binding['root_identity']
            and intent['all_original_bytes_durably_archived'] is True, 'RAM archive intent/source joins differ')
    original = read(owner)
    require(type(intent['files']) is list and len(intent['files']) <= 3, 'Bounded original RAM member manifest required')
    names = set()
    for item in intent['files']:
        pin = item['original']
        file_shape(pin, binding, original['pid'])
        name = Path(pin['path']).name
        require(name not in names, 'Duplicate original RAM member')
        names.add(name)
        require(item['archived']['path'] == str(expected_root / (name + '.original-bytes'))
                and item['archived']['sha256'] == pin['sha256'] and item['archived']['bytes'] == pin['bytes'],
                'Original RAM archive escaped or changed bytes')
        read(item['archived'], False)
        require(not Path(pin['path']).exists() and not Path(pin['path']).is_symlink(), 'Original RAM member remains')
    require(not Path(binding['root']).exists() and not Path(binding['root']).is_symlink(), 'Original RAM root remains')
    require(intent['created_monotonic_s'] <= result['released_monotonic_s'] <= time.monotonic(),
            'Original RAM release chronology differs')
    return dict(release=release, archived_members=len(names), original_root_absent=True,
                exact_original_bytes_and_modes_retained=True, quality_qualified=False)


def release_unstarted(binding, parent, native_job, archive_root, h):
    root = validate(binding, binding['nonce'], parent, native_job, h)
    require(list(root.iterdir()) == [], 'Unstarted RAM control directory is not empty; preserve it')
    root.rmdir()
    archive_root = Path(archive_root)
    archive_root.mkdir(mode=0o700)
    return h.put(archive_root / 'original-unstarted-RAM-release.json',
        dict(schema='robotron-unstarted-RAM-control-release-v1', binding=binding,
             original_root_absent=not root.exists(), created_monotonic_s=time.monotonic()))
