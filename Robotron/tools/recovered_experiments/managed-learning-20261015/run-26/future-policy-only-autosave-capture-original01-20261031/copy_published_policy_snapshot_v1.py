"""Root-only read-only copy of one atomically published policy generation.

No Main/API/control calls, Torch import, replay access or policy qualification.
The source pathname may advance while the opened published inode is copied.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time


ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
AGENT = ROOT / 'Scripts/dqn/agent.py'
AGENT_SHA = 'd2a95ff0828df2a00ac86049965b6df304d26b50263b76d027d27a586ff77152'
LATEST = ROOT / 'models_dqn/robotron_dqn_latest.pt'


def require(value, reason):
    if not value:
        raise ValueError(reason)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, uid=s.st_uid,
        mode=oct(stat.S_IMODE(s.st_mode)), nlink=s.st_nlink,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    require(output.is_absolute() and output.parent.resolve(strict=True) == output.parent
        and not output.exists(), 'Fresh canonical private output directory required')
    require(AGENT.resolve(strict=True) == AGENT and not AGENT.is_symlink()
        and hashlib.sha256(AGENT.read_bytes()).hexdigest() == AGENT_SHA,
        'Reviewed atomic-save publisher source changed')
    require(LATEST.parent.resolve(strict=True) == LATEST.parent,
        'Canonical published checkpoint parent required')
    started = time.time()
    output.mkdir(mode=0o700)
    destination = output / 'frozen-policy.pt'
    with os.fdopen(os.open(LATEST, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as incoming:
        before = os.fstat(incoming.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
            and before.st_nlink in (0, 1) and 0 < before.st_size <= 512 << 20,
            'Bounded owned regular published generation without hardlinks required')
        digest = hashlib.sha256()
        copied = 0
        with destination.open('xb') as outgoing:
            while True:
                block = incoming.read(1024 * 1024)
                if not block:
                    break
                copied += len(block)
                require(copied <= before.st_size, 'Opened published generation grew')
                digest.update(block)
                outgoing.write(block)
            outgoing.flush()
            after = os.fstat(incoming.fileno())
            stable = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_uid, s.st_mode)
            require(copied == before.st_size and stable(before) == stable(after)
                and after.st_nlink in (0, 1), 'Opened published generation changed')
            # Atomic replacement may unlink this already-open source generation;
            # its nlink/ctime change does not change its bytes or invalidate the FD.
            require(hashlib.sha256(AGENT.read_bytes()).hexdigest() == AGENT_SHA,
                'Reviewed atomic-save publisher source changed during copy')
            os.fchmod(outgoing.fileno(), 0o444)
            os.fsync(outgoing.fileno())
        source_sha = digest.hexdigest()
    with destination.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == source_sha,
            'Independent copy rehash differs')
    saved = destination.stat()
    require(saved.st_nlink == 1 and saved.st_size == copied
        and stat.S_IMODE(saved.st_mode) == 0o444, 'Readonly independent copy differs')
    receipt = dict(schema='robotron-policy-only-published-FD-copy-v1',
        status='COPIED_READONLY_POLICY_GENERATION_NOT_CPU_OR_QUALITY_QUALIFIED',
        source_path=str(LATEST), opened_published_generation_before=identity(before),
        opened_published_generation_after=identity(after), source_path_may_now_name_a_newer_generation=True,
        source_bytes_copied=copied, streaming_sha256=source_sha,
        independent_copy=dict(path=str(destination), sha256=source_sha, bytes=copied, identity=identity(saved)),
        atomic_publisher_source=dict(path=str(AGENT), sha256=AGENT_SHA),
        copy_source=dict(path=str(Path(__file__).resolve()),
            sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        started_unix_s=started, ended_unix_s=time.time(),
        Main_or_model_or_optimizer_or_replay_control_mutated=False,
        CPU_verification=None, fullstate_or_replay_backup_claimed=False, quality_qualified=False)
    with (output / 'published-policy-copy.json').open('x') as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    fsync_directory(output)
    fsync_directory(output.parent)
    print(json.dumps(dict(status=receipt['status'], checkpoint=receipt['independent_copy'])))


if __name__ == '__main__':
    main()
