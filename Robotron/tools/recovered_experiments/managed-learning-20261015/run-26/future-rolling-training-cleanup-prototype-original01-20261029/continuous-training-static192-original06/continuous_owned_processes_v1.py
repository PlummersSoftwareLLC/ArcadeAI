"""Exact bounded physical-process/TCP helpers; inert definitions only."""
import os
from pathlib import Path
import socket


def require(value, message):
    if not value:
        raise ValueError(message)

def birth(pid):
    text = Path('/proc',str(pid),'stat').read_text()
    require(int(text.split(' ',1)[0]) == pid, 'Observed another process')
    fields = text.rsplit(')',1)[1].split()
    return dict(pid=pid,birth=int(fields[19]),parent=int(fields[1]),state=fields[0])

def cgroup(pid):
    lines=Path('/proc',str(pid),'cgroup').read_text().splitlines()
    require(len(lines)==1 and lines[0].startswith('0::/'),'Exact cgroup-v2 membership required')
    return lines[0][3:]

def actor(pid):
    before=birth(pid)
    root=Path('/proc',str(pid))
    command=[p.decode()for p in (root/'cmdline').read_bytes().split(b'\0')if p]
    env=dict(p.decode().split('=',1)for p in (root/'environ').read_bytes().split(b'\0')if b'='in p)
    result=dict(pid=before['pid'],birth=before['birth'],parent=before['parent'],
        exe=os.readlink(root/'exe'),command=command,
        environment=env,cgroup=cgroup(pid),uid=root.stat().st_uid)
    after=birth(pid)
    require(all(before[k]==after[k]for k in ('pid','birth','parent'))
        and before['state']not in ('Z','X','x')and after['state']not in ('Z','X','x'),
        'Actor identity changed or retired')
    return result

def tcp_binding(pid, endpoints):
    """Actual process-owned socket inode, not API-CID-to-PID inference."""
    root=Path('/proc',str(pid))
    require(os.readlink(root/'ns/net')==os.readlink('/proc/self/ns/net'), 'Actor network namespace differs')
    descriptors=list((root/'fd').iterdir())
    require(len(descriptors)<=4096,'Unexpected actor descriptor census')
    inodes=set()
    for fd in descriptors:
        try:
            value=os.readlink(fd)
        except FileNotFoundError:
            continue
        if value.startswith('socket:[')and value.endswith(']'):
            inodes.add(value[8:-1])
    def endpoint(text):
        address,port=text.split(':')
        return [socket.inet_ntoa(bytes.fromhex(address)[::-1]),int(port,16)]
    raw=(root/'net/tcp').read_bytes()
    require(len(raw)<=2_000_000,'Actor TCP evidence exceeds declared bound')
    found=[]
    for line in raw.decode().splitlines()[1:]:
        fields=line.split()
        if (len(fields)>9 and fields[3]=='01' and fields[9]in inodes
                and endpoint(fields[1])==endpoints['peer']
                and endpoint(fields[2])==endpoints['server']):
            found.append(dict(inode=int(fields[9]),local=endpoint(fields[1]),remote=endpoint(fields[2])))
    require(len(found)==1,'No unique actual process socket to this server connection')
    return found[0]
