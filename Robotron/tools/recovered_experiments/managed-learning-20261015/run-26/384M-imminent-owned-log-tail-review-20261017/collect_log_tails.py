"""Read only bounded inode-bound log tails and one contemporary increment."""
import ast
import datetime as dt
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

OUT=Path(__file__).parent
GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
PRE=RUN/'inference-affinity-v2-live-20261017T0012Z/precommit.json'
ARTIFACTS={}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(name,value):
    data=value if isinstance(value,bytes) else (json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    path=OUT/name
    with path.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    path.chmod(0o444)
    ARTIFACTS[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def ticks(pid):return int((Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()[19])

def owners(pre):
    results=[]
    rows=[pre['bindings']['worker']['trainer'],*pre['bindings']['actors']]
    for row in rows:
        pid=row['pid'];before=ticks(pid)
        if before!=row['starttime_ticks']:raise ValueError('Owned PID changed '+str(pid))
        fds={}
        for fd in ('1','2'):
            path=Path('/proc')/str(pid)/'fd'/fd
            target=path.resolve(strict=True);info=path.stat()
            binding=pre['bindings']['logs'].get(str(target))
            if binding!=dict(device=info.st_dev,inode=info.st_ino):raise ValueError('Owned stdout binding changed '+str(pid))
            fds[fd]=str(target)
        if ticks(pid)!=before:raise ValueError('Owner changed during log inspection '+str(pid))
        results.append(dict(pid=pid,starttime_ticks=before,slot=row['client_slot'],fds=fds))
    return results

def read(path,binding,cap,*,offset=None):
    path=Path(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or dict(device=info.st_dev,inode=info.st_ino)!=binding:
            raise ValueError('Bound regular log changed '+str(path))
        end=info.st_size
        start=max(0,end-cap) if offset is None else offset
        if start>end:raise ValueError('Log truncated '+str(path))
        if end-start>cap:raise ValueError('Contemporary log increment exceeded bound '+str(path))
        stream.seek(start);data=stream.read(end-start)
        after=os.fstat(stream.fileno());current=path.lstat()
        if len(data)!=end-start or after.st_size<end or any((v.st_dev,v.st_ino)!=(info.st_dev,info.st_ino) for v in (after,current)):
            raise ValueError('Log inode/truncation changed during read '+str(path))
    return data,dict(path=str(path),device=info.st_dev,inode=info.st_ino,size_at_read=end,
        mtime_ns=info.st_mtime_ns,mtime_UTC=dt.datetime.fromtimestamp(info.st_mtime,dt.timezone.utc).isoformat(),
        offset_start=start,offset_end=end,captured_bytes=len(data),prefix_omitted=start>0,
        read_observed_unix=time.time(),cap=cap)

def scan(data,record,markers,audit_start):
    hits=[];offset=record['offset_start']
    lines=data.splitlines(keepends=True)
    first_partial=record['prefix_omitted']
    timestamps=[]
    for index,line in enumerate(lines):
        text=line.decode(errors='replace').rstrip('\r\n')
        found=[marker for marker in markers if marker.lower() in text.lower()]
        explicit=[int(value) for value in re.findall(r'\bunix_s=(\d+)\b',text)]
        timestamps.extend(explicit)
        if found:
            if explicit:
                classification='historical_timestamped' if max(explicit)<audit_start else 'contemporary_timestamped'
            elif record['mtime_ns']/1e9<audit_start:
                classification='historical_file_mtime_no_line_timestamp'
            else:
                classification='untimed_tail_requires_context'
            hits.append(dict(offset_start=offset,offset_end=offset+len(line),text=text,
                markers=found,unix_seconds=explicit,classification=classification,
                first_line_partial=bool(index==0 and first_partial)))
        offset+=len(line)
    train=[int(value.replace(',','')) for value in re.findall(rb'\bTRAIN\s+([\d,]+)',data)]
    return dict(hits=hits,line_timestamps_min=min(timestamps) if timestamps else None,
        line_timestamps_max=max(timestamps) if timestamps else None,
        TRAIN_learner_min=min(train) if train else None,TRAIN_learner_max=max(train) if train else None,
        TRAIN_row_count=len(train))

def main():
    started=time.time();mono=time.monotonic();pre=json.loads(PRE.read_text())
    if sha(PRE)!='c45a70c7528ef2c1a40893c37cc9b925a140685e3a43563f7bd187b978119b97':raise ValueError('Precommit differs')
    helper=GAME/'tools/inference_worker_affinity.py'
    tree=ast.parse(helper.read_text())
    markers=list(ast.literal_eval(next(node.value for node in tree.body if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id=='LOG_MARKERS' for target in node.targets))))
    markers+=['out of memory','CUDA error:','CUDA_ERROR','Killed process','Segmentation fault',
        'Connection refused','Socket open failed:','socket: Broken pipe','Input/output error','No space left on device']
    before_owners=owners(pre)
    save('owned-log-owners-first.json',before_owners)
    records=[]
    for index,(path,binding) in enumerate(sorted(pre['bindings']['logs'].items())):
        cap=256*1024 if path.endswith('/console.log') else 64*1024 if path.endswith('/fleet.log') else 32*1024
        data,record=read(path,binding,cap)
        filename='tail-%03d-%s'%(index,Path(path).name)
        save(filename,data)
        record.update(artifact=filename,scan=scan(data,record,markers,started))
        records.append(record)
    # This contemporaneous interval has actual byte offsets; earlier tails
    # have bounded wall-clock coverage only when their own evidence gives it.
    delay=12-(time.monotonic()-mono)
    if delay>0:time.sleep(delay)
    deltas=[]
    for index,record in enumerate(records):
        path=record['path'];binding=pre['bindings']['logs'][path]
        data,increment=read(path,binding,128*1024,offset=record['offset_end'])
        filename='increment-%03d-%s'%(index,Path(path).name)
        if data:save(filename,data)
        increment.update(artifact=filename if data else None,scan=scan(data,increment,markers,started))
        deltas.append(increment)
    after_owners=owners(pre);save('owned-log-owners-final.json',after_owners)
    all_hits=[dict(path=row['path'],**hit) for row in records for hit in row['scan']['hits']]
    delta_hits=[dict(path=row['path'],**hit) for row in deltas for hit in row['scan']['hits']]
    timestamped=[value for row in records for value in (row['scan']['line_timestamps_max'],) if value is not None]
    checks=dict(precommit_log_bindings_193=len(records)==193,
        owned_main_and192_actor_log_FDs_match=before_owners==after_owners and len(before_owners)==193,
        all_owner_ticks_stable=ticks(3032848)==28609635 and ticks(3593422)==30108625,
        no_new_increment_fault_markers=not delta_hits,
        no_tail_fault_with_contemporary_timestamp=not any(hit['classification']=='contemporary_timestamped' for hit in all_hits),
        no_unclassified_untimed_tail_fault=not any(hit['classification']=='untimed_tail_requires_context' for hit in all_hits))
    console=next(row for row in records if row['path'].endswith('/console.log'))
    console_delta=next(row for row in deltas if row['path']==console['path'])
    checks['trainer_log_recently_written']=time.time()-console['mtime_ns']/1e9<90
    checks['trainer_tail_has_training_rows']=console['scan']['TRAIN_row_count']>0
    result=dict(schema='robotron-bounded-owned-log-tail-health-review-v1',
        status='PASS_BOUNDED_OBSERVATION' if all(checks.values()) else 'AUDIT_NEEDS_REVIEW',checks=checks,
        observed_start_UTC=dt.datetime.fromtimestamp(started,dt.timezone.utc).isoformat(),
        observed_end_UTC=dt.datetime.now(dt.timezone.utc).isoformat(),elapsed_s=time.monotonic()-mono,
        precommit=dict(path=str(PRE),sha256=sha(PRE)),marker_source=dict(path=str(helper),sha256=sha(helper),
            method='AST literal only; helper not imported',markers=markers),
        bounded_tails=records,contemporary_increments=deltas,tail_marker_hits=all_hits,increment_marker_hits=delta_hits,
        latest_actor_timeout_unix=max(timestamped) if timestamped else None,
        latest_actor_timeout_UTC=dt.datetime.fromtimestamp(max(timestamped),dt.timezone.utc).isoformat() if timestamped else None,
        trainer_console=console,trainer_console_increment=console_delta,
        total_tail_bytes=sum(row['captured_bytes'] for row in records),total_increment_bytes=sum(row['captured_bytes'] for row in deltas),
        artifacts=ARTIFACTS,collector_sha256=sha(__file__),
        interpretation=['Timestamped old timeouts remain historical evidence, not current runtime failures',
            'No generic ALSA/ROM/startup warning suppression was used to certify current increments; raw bounded tails are retained',
            'Silent actor logs do not independently prove gameplay progress or absence of suppressed events; exact live owners were verified',
            'Current trainer TRAIN rows and append/mtime establish logging progress only; no API/socket request or controlled performance test'],
        limits=['No full log-history read; main256KiB/fleet64KiB/other32KiB tails only; prior bytes outside prefixes unreviewed',
            'No previous wall-clock start offset exists for the old tails; untimestamped tail fault matches require review unless filemtime is historical',
            'Only contemporaneous12s increments have known first/end offsets; source markers are not an exhaustive detector of silent failures',
            'No model/replay/numerical import/test, socket connection, signal, checkpoint, service or production/source mutation'])
    save('bounded-log-review-receipt.json',result)
    fd=os.open(OUT,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps(dict(status=result['status'],checks=checks,tail_bytes=result['total_tail_bytes'],
        increment_bytes=result['total_increment_bytes'],tail_marker_hits=len(all_hits),increment_marker_hits=len(delta_hits),
        latest_actor_timeout_UTC=result['latest_actor_timeout_UTC'],trainer_tail=console['scan'],
        trainer_increment=console_delta['scan'],receipt=str(OUT/'bounded-log-review-receipt.json'),
        sha256=sha(OUT/'bounded-log-review-receipt.json')),indent=2))

if __name__=='__main__':main()
