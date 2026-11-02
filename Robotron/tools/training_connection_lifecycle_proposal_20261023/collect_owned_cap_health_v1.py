"""Unselected read-only live transport/physical health integration diagnostic.

Capture clocks bracket original raw evidence. A bounded separate writer persists
all samples; slow fsync never moves capture timestamps. Any gap, writer failure,
unfinished handover or changed actor rejects the entire original observation.
No signal, configuration, save request, model load, MAME launch or GPU operation.
"""
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import threading
import time
import urllib.request


def require(value,message):
    if not value:raise ValueError(message)


def load(name,pin):
    path=Path(pin['path']);raw=path.read_bytes()
    require(len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Source bytes changed')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def encode(raw):
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode())


def decode(value):
    raw=base64.b64decode(value['base64'],validate=True)
    require(len(raw)==value['bytes']and hashlib.sha256(raw).hexdigest()==value['sha256'],'Raw evidence bytes changed')
    return raw


def packed(sample,deep):
    entry={key:value for key,value in sample.items()if key not in ('raw_API','raw_tcp','raw_fds','log_chunks')}
    entry.update({key:encode(sample[key])for key in ('raw_API','raw_tcp','raw_fds')})
    entry['log_chunks']=[dict(chunk,raw=encode(chunk['raw']))for chunk in sample['log_chunks']]
    return dict(schema='robotron-owned-cap-health-raw-sample-v1',transport=entry,deep=deep)


def unpacked(record):
    require(record['schema']=='robotron-owned-cap-health-raw-sample-v1','Unknown original sample format')
    sample=copy.deepcopy(record['transport'])
    for key in ('raw_API','raw_tcp','raw_fds'):sample[key]=decode(sample[key])
    for chunk in sample['log_chunks']:chunk['raw']=decode(chunk['raw'])
    return sample


class Writer:
    def __init__(self,h,directory):
        self.h=h;self.directory=directory;self.pending=queue.Queue(maxsize=32)
        self.records=[];self.failure=None;self.max_pending=0;self.closed=False
        self.thread=threading.Thread(target=self.run,name='owned-cap-evidence-writer',daemon=True);self.thread.start()

    def run(self):
        try:
            while True:
                entry=self.pending.get()
                try:
                    if entry is None:return
                    index=entry['transport']['index']
                    self.records.append(self.h.put(self.directory/f'{index:06d}-original.json',entry))
                finally:self.pending.task_done()
        except BaseException as error:self.failure=repr(error)

    def submit(self,entry):
        require(not self.closed and self.failure is None and self.thread.is_alive(),'Original evidence writer failed/closed')
        self.pending.put_nowait(entry);self.max_pending=max(self.max_pending,self.pending.qsize())

    def close(self):
        require(not self.closed,'Original writer already closed');self.closed=True
        require(self.failure is None and self.thread.is_alive(),'Original writer failed before closure')
        self.pending.put(None,timeout=5);self.thread.join(timeout=15)
        require(not self.thread.is_alive()and self.failure is None and self.pending.unfinished_tasks==0,
                'Original evidence writer did not drain and stop')
        return dict(all_original_samples_persisted=True,thread_stopped=True,max_pending=self.max_pending)


class Collector:
    def __init__(self,job,output):
        self.job=job;self.output=output
        self.h=load('_live_h',job['sources']['helpers'])
        for entry in job['sources'].values():self.h.checked(entry)
        self.p=load('_live_primitives',job['sources']['primitives'])
        self.transport=load('_live_stream',job['sources']['transport'])
        self.health=load('_live_health',job['sources']['health'])
        self.sup=load('_live_sup',job['sources']['supervision'])
        self.window=load('_live_window',job['sources']['window'])
        self.io=load('_live_io',job['sources']['io'])
        self.main=json.loads(self.h.checked(job['binding']).read_bytes())
        self.policy=json.loads(self.h.checked(self.main['supervision_policy']).read_bytes())
        self.baseline=json.loads(self.h.checked(self.main['baseline_API']).read_bytes())
        self.source_proof=self.health.verify_sources(Path(job['sources']['window']['path']).read_bytes(),
            Path(job['sources']['supervision']['path']).read_bytes(),Path(job['sources']['health']['path']).read_bytes())
        require(len(self.main['held_hashes'])==197,'Original197 held inputs required')
        self.window.owner_and_files(self.main)
        self.cursors={}
        for actor in self.main['actors']:
            path=Path(os.readlink(f"/proc/{actor['pid']}/fd/1"));info=path.stat();origin=job['log_origins'][str(actor['slot'])]
            require(path==Path(origin['path'])and(info.st_dev,info.st_ino)==(origin['device'],origin['inode'])
                and path.resolve().is_relative_to(Path(job['log_root']).resolve()),'Original actor log origin changed')
            self.cursors[str(actor['slot'])]=dict(path=str(path),device=info.st_dev,inode=info.st_ino,
                offset=info.st_size,last_observed_unix_s=time.time())
        self.initial_cursors=copy.deepcopy(self.cursors)
        self.stream=self.transport.Stream(self.p,self.main,self.cursors,self.p.LUA_SHA)
        self.fd_raw=None;self.next_fd=0.;self.next_deep=0.;self.deep=None;self.previous_deep=None;self.previous_API=None
        self.index=0;self.deep_count=0;self.closed=False;self.failed=None;self.writer=Writer(self.h,output/'samples')

    def all_fds(self):
        begin=time.time();trainer=self.io.fd_inodes(self.main['owner']['pid']);actors={}
        for actor in self.main['actors']:actors[str(actor['slot'])]=self.io.fd_inodes(actor['pid'])
        return json.dumps(dict(begin_unix_s=begin,end_unix_s=time.time(),trainer=trainer,actors=actors),
                          separators=(',',':'),allow_nan=False).encode()

    def capture_deep(self):
        snapshot=self.sup.collect(self.policy)
        held_error=None
        try:self.window.owner_and_files(self.main)
        except Exception as error:held_error=repr(error)
        st=(self.window.MODEL/'robotron_dqn_latest.pt').stat()
        return dict(snapshot=snapshot,autosave=dict(device=st.st_dev,inode=st.st_ino,bytes=st.st_size,
            mtime_ns=st.st_mtime_ns,uid=st.st_uid),checked_unix_s=time.time(),
            held197_checked_live=held_error is None,held_error=held_error)

    def logs(self):
        pieces=[]
        for slot,cursor in self.cursors.items():
            path=Path(cursor['path']);info=path.stat();now=time.time()
            require((info.st_dev,info.st_ino)==(cursor['device'],cursor['inode'])and info.st_size>=cursor['offset'],
                    'Original actor log inode/size changed')
            size=info.st_size-cursor['offset'];require(size<=256<<10,'Original log burst exceeded fixed byte bound')
            if size:
                with path.open('rb')as file:file.seek(cursor['offset']);raw=file.read(size)
                require(len(raw)==size,'Original actor log short read')
                pieces.append(dict(slot=int(slot),actor_pid=self.main['actors'][int(slot)]['pid'],path=str(path),
                    device=info.st_dev,inode=info.st_ino,offset=cursor['offset'],bytes=size,raw=raw,
                    lower_observed_unix_s=cursor['last_observed_unix_s'],upper_observed_unix_s=now))
                cursor['offset']+=size
            cursor['last_observed_unix_s']=now
        return pieces

    def observe(self):
        require(self.failed is None and not self.closed,'Original collector failed/closed; no recovery')
        try:
            return self._observe()
        except BaseException as error:self.failed=repr(error);raise

    def _observe(self):
        begin=time.monotonic();deep=None
        if begin>=self.next_deep:
            deep=self.capture_deep();self.next_deep=time.monotonic()+5
        API_begin=time.time()
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=.4)as response:raw=response.read((1<<20)+1)
        API_end=time.time();require(0<len(raw)<=1<<20,'Bounded original API required')
        API=self.p.decode(raw)
        table,tcp_raw=self.io.tcp()
        # A full FD view is forced for any changed API or kernel topology, even
        # when the server reuses a CID. Otherwise cache age remains below1.25s.
        refresh=self.fd_raw is None or time.monotonic()>=self.next_fd or API['client_count']!=192
        if not refresh:
            view=self.p.decode(self.fd_raw)
            try:self.transport.full_owned_join(self.p,self.p.tcp(tcp_raw),view)
            except ValueError:refresh=True
        if refresh:
            self.fd_raw=self.all_fds();self.next_fd=time.monotonic()+1
        chunks=self.logs()
        sample=dict(index=self.index,API_begin_unix_s=API_begin,API_end_unix_s=API_end,
            tcp_begin_unix_s=table['begin_unix_s'],tcp_end_unix_s=table['end_unix_s'],observed_unix_s=time.time(),
            raw_API=raw,raw_tcp=tcp_raw,raw_fds=self.fd_raw,log_chunks=chunks)
        # Queue the actual bytes/census before any original assertion can fail.
        self.writer.submit(packed(sample,deep));self.index+=1
        if deep is not None:
            require(deep['held_error'] is None,'Original held source/control check failed: '+str(deep['held_error']))
            self.health.physical(self.sup,self.policy,deep['snapshot'],self.previous_deep)
            self.health.autosave(deep['autosave'],deep['checked_unix_s'])
            self.previous_deep=deep['snapshot'];self.deep=deep;self.deep_count+=1
        require(self.deep is not None and 0<=sample['observed_unix_s']-self.deep['checked_unix_s']<=10,
                'Fresh original physical/source/autosave census missing')
        self.health.sample(self.p,API,self.baseline,self.main['experiment'],sample['observed_unix_s'],self.previous_API)
        self.previous_API=API
        phase=self.stream.observe(sample)
        return dict(index=sample['index'],phase=phase,loop_s=time.monotonic()-begin,
                    learner_frames=API['learner_frame_count'],training_steps=API['training_steps'],fleet_fps=API['fps'])

    def close(self):
        require(not self.closed,'Original collector already closed');self.closed=True
        writer=self.writer.close()
        require(self.failed is None,'Original collector failed; no late rescue')
        summary=self.stream.close()
        require(len(self.writer.records)==self.index and self.deep_count>=3,'Original evidence coverage incomplete')
        self.window.owner_and_files(self.main)
        return dict(status='ORIGINAL_LIVE_TRANSPORT_AND_FULL_HEALTH_CLOSED_NOT_SCIENTIFIC',
            transport=summary,samples=self.writer.records,writer=writer,deep_samples=self.deep_count,
            source_specialization=self.source_proof,held197_final_verified=True,
            no_production_runtime_change=True,quality_qualified=False,scientific_guard_selected=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Exact collector source required')
    raw=Path(args.job).read_bytes();require(hashlib.sha256(raw).hexdigest()==args.job_sha256,'Exact collector job required')
    job=json.loads(raw);require(job['schema']=='robotron-owned-cap-live-health-job-v1'and job['duration_s']==120
        and job['poll_s']==.2 and os.environ.get('CUDA_VISIBLE_DEVICES')=='','Fixed CPU read-only diagnostic required')
    output=Path(job['output']);output.mkdir(mode=0o700);(output/'samples').mkdir(mode=0o700)
    collector=None;status=[];started=time.monotonic()
    try:
        collector=Collector(job,output);collector.h.put(output/'initial-log-cursors.json',collector.initial_cursors)
        start=time.monotonic()
        while time.monotonic()-start<job['duration_s']:
            tick=time.monotonic();status.append(collector.observe())
            time.sleep(max(0,job['poll_s']-(time.monotonic()-tick)))
        result=collector.close();result.update(created_unix_s=time.time(),duration_s=time.monotonic()-start,
            actual_status=status,job_sha256=args.job_sha256,source_sha256=args.source_sha256)
        collector.h.put(output/'report.json',result)
        print(json.dumps(dict(status=result['status'],samples=len(result['samples']),deep_samples=result['deep_samples'],
            budget=result['transport']['budget'],writer=result['writer'])),flush=True)
        return 0
    except BaseException as error:
        failure=dict(status='ORIGINAL_LIVE_HEALTH_REJECTED_PRESERVED',error=repr(error),quality_qualified=False,
            no_production_runtime_change=True,elapsed_s=time.monotonic()-started)
        if collector is not None:
            if not collector.writer.closed:
                try:failure['writer']=collector.writer.close()
                except BaseException as closure_error:failure['writer_error']=repr(closure_error)
            failure.update(samples=collector.writer.records,observed_samples=collector.index,deep_samples=collector.deep_count)
            collector.h.put(output/'failure.json',failure)
        else:
            with(output/'setup-failure.json').open('x')as file:
                json.dump(failure,file,allow_nan=False);file.flush();os.fchmod(file.fileno(),0o444);os.fsync(file.fileno())
        print(json.dumps(failure if collector is None else {key:value for key,value in failure.items()if key!='samples'}),flush=True)
        return 1


if __name__=='__main__':raise SystemExit(main())
