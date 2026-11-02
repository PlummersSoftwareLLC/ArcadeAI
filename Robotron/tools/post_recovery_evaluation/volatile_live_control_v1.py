"""Tiny exclusive tmpfs projection; scientific raw evidence remains on disk.

This directory is an ephemeral control channel. Its bytes never substitute for
durable raw snapshots. Preserve a final cold copy before removing owned files.
"""
import hashlib
import json
import os
from pathlib import Path
import stat


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, uid=info.st_uid,
                mode=oct(stat.S_IMODE(info.st_mode)))


def path_for(nonce):
    require(type(nonce) is str and len(nonce) == 32
            and all(c in '0123456789abcdef' for c in nonce), 'Exact fresh nonce required')
    return Path('/dev/shm')/('robotron-observer-live-'+nonce)


class VolatileLiveControl:
    LIMIT = 128 << 10

    def __init__(self, nonce, binding):
        root = Path('/dev/shm')
        require(root.resolve(strict=True) == root and not root.is_symlink(), 'Canonical tmpfs root required')
        mounts = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
        require(any(row[4] == str(root) and row[row.index('-')+1] == 'tmpfs' for row in mounts),
                'Live control must use actual tmpfs')
        self.path = path_for(nonce)
        self.binding = json.loads(json.dumps(binding, allow_nan=False))
        self.path.mkdir(mode=0o700)
        self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.owner = identity(os.fstat(self.fd))
        require(self.owner['uid'] == os.getuid() and self.owner['mode'] == '0o700'
                and self.owner['device'] == root.stat().st_dev, 'Original tmpfs owner differs')
        self.closed = False
        self.last = None

    def publish(self, value):
        require(not self.closed, 'Original live projection is closed')
        raw = (json.dumps(value, allow_nan=False, separators=(',', ':'))+'\n').encode()
        require(len(raw) <= self.LIMIT, 'Live projection exceeds128KiB')
        fd = os.open('live.next', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
        os.replace('live.next', 'live.json', src_dir_fd=self.fd, dst_dir_fd=self.fd)
        self.last = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), value=json.loads(raw))

    def descriptor(self):
        return dict(schema='robotron-owned-volatile-live-directory-v1', path=str(self.path),
                    identity=dict(self.owner), binding=json.loads(json.dumps(self.binding)),
                    volatile_not_scientific_raw_evidence=True)

    def close(self):
        require(not self.closed, 'Original live release is single-use')
        require(identity(os.fstat(self.fd)) == self.owner and not self.path.is_symlink()
                and identity(self.path.stat()) == self.owner, 'Original live directory changed')
        names = set(os.listdir(self.fd))
        require(names <= {'live.json', 'live.next'}, 'Unknown live-control file; no deletion authorized')
        files = []
        for name in sorted(names):
            info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                    and info.st_nlink == 1 and info.st_size <= self.LIMIT,
                    'Original live file owner/type/links/size differs')
            files.append(dict(name=name, identity=identity(info), bytes=info.st_size))
        if 'live.json' in names:
            fd = os.open('live.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.fd)
            with os.fdopen(fd, 'rb') as stream:
                raw = stream.read(self.LIMIT+1)
            require(self.last is not None and len(raw) == self.last['bytes']
                    and hashlib.sha256(raw).hexdigest() == self.last['sha256'],
                    'Final volatile publication changed')
        for row in files:
            os.unlink(row['name'], dir_fd=self.fd)
        os.rmdir(self.path)
        os.close(self.fd)
        self.closed = True
        require(not self.path.exists(), 'Original live directory remains')
        return dict(schema='robotron-owned-volatile-live-release-v1', original=self.descriptor(),
                    removed_files=files, directory_absent=True, last_publication=self.last)
