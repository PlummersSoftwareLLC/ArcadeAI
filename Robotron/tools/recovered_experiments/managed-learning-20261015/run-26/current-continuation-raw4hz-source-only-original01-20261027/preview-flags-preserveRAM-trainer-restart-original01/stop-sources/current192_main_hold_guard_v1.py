"""Observe one prospective post-correction window and request one checkpoint.

Uses the existing pure exposure-accounting validator. No trainer restart,
learning-parameter changes, evaluation, retry, rollback or promotion occurs.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/home/dave/source/repos/ArcadeAI')
GAME = ROOT/'Robotron'
MODEL = GAME/'models_dqn'
HORIZON = 8_000_000


def require(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    path = Path(path); before = path.stat()
    with path.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'File changed while hashing')
    return dict(path=str(path),sha256=digest,bytes=after.st_size,identity=dict(
        device=after.st_dev,inode=after.st_ino,bytes=after.st_size,mtime_ns=after.st_mtime_ns,
        ctime_ns=after.st_ctime_ns,mode=oct(after.st_mode&0o777),uid=after.st_uid,nlink=after.st_nlink))


def publish(path, value, *, replace=False):
    path = Path(path)
    raw = value if isinstance(value,bytes) else (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    target = path.with_suffix(path.suffix+'.tmp') if replace else path
    with target.open('xb') as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    if replace: os.replace(target,path)
    descriptor=os.open(path.parent,os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
    return pin(path)


def process_start(pid):
    try: raw=Path('/proc',str(pid),'stat').read_text()
    except (FileNotFoundError,ProcessLookupError): return None
    return int(raw.rsplit(')',1)[1].split()[19])


def progress(current, baseline, previous):
    for kind in ('optimizer_identity','replay_identity'):
        require(current[kind]==baseline[kind], 'Exposure process/instance/epoch changed')
    for group in ('clocks','optimizer','optimizer_since_epoch','categories'):
        require(all(current[group][key]>=previous[group][key] for key in previous[group]),
                'Counter regressed: '+group)
    require(current['optimizer']['unavailable']==0, 'Unclassified optimizer outcome')
    frames=current['clocks']['learner_frame_count']-baseline['clocks']['learner_frame_count']
    accepted=current['learner_accepted']-baseline['learner_accepted']
    require(accepted>=0, 'Learner accepted count regressed')
    return dict(learner_frames=frames,learner_accepted=accepted,
        applied_updates=current['optimizer']['applied']-baseline['optimizer']['applied'],
        amp_skips=current['optimizer']['amp_skipped']-baseline['optimizer']['amp_skipped'],
        logical_samples=current['clocks']['optimized_samples']-baseline['clocks']['optimized_samples'],
        both_horizons=frames>=HORIZON and accepted>=HORIZON)


def healthy(api, baseline, experiment, now):
    require(api['client_count']==192 and api['training_enabled'] is True and api['measurement_active'] is False
            and api['managed_experiment']==experiment and api['lr']==6.25e-6, 'Held main192 recipe changed')
    require(api['pipeline_read_error']==api['bank_persistence_read_error']=='', 'Pipeline/bank read error')
    age=now-api['ts'];pipeline_age=api['pipeline_snapshot_age_s']
    require(type(age) in (int,float) and math.isfinite(age) and 0<=age<=5
            and type(pipeline_age) in (int,float) and math.isfinite(pipeline_age) and 0<=pipeline_age<=5,
            'Stale, future or nonfinite API/pipeline sample')
    pipe=api['host_pipeline']
    require(pipe['schema']=='robotron-host-pipeline-v1' and pipe['available'] is True
            and type(pipe['generation']) is int and pipe['generation']==baseline['host_pipeline']['generation'],
            'Pipeline unavailable or generation changed')
    for kind in ('inference','actor_refresh','target_refresh','learner_priority'):
        require(type(pipe[kind]['errors']) is int and pipe[kind]['errors']==0, 'Pipeline error: '+kind)
    require(type(api['bank_persistence']['write_failures']) is int
            and api['bank_persistence']['write_failures']==0, 'Bank persistence failed')


def owner_and_files(job):
    owner=job['owner']
    require(job['schema']=='robotron-current-fresh192-continuation-registry-v1'
            and (owner['pid'],owner['starttime_ticks'],owner['invocation_id']) ==
                (1062324,117468652,'429ceaf754ca49b495056180a0350411')
            and len(job['actors'])==192 and {a['slot']for a in job['actors']}==set(range(192)),
            'Exact new original trainer and real192 registry required')
    require(process_start(owner['pid'])==owner['starttime_ticks'], 'Original trainer changed')
    for actor in job['actors']:
        require(process_start(actor['pid'])==actor['starttime_ticks']
                and sorted(os.sched_getaffinity(actor['pid']))==actor['mask'], 'Original actor changed')
    for path,digest in job['held_hashes'].items():
        require(pin(path)['sha256']==digest, 'Held source/control/phase/unit changed: '+path)
    require(not (MODEL/'managed_save.request.json').exists(), 'A foreign save request is pending')


def capture(job, out, latch, api):
    tag=job['tag'];request=MODEL/'managed_save.request.json';slot=request.with_name(request.name+'.completed')
    source=MODEL/'managed-checkpoints'/(tag+'.pt');owner=job['owner']
    require(not request.exists() and not source.exists(), 'Save request or unique checkpoint tag already exists')
    before_time=time.time();before=None
    if slot.exists():
        before=dict(actual_pin=pin(slot),archive=publish(out/'completed-slot-before.json',slot.read_bytes()))
    temp=request.with_suffix('.continuity-tmp')
    with temp.open('x') as stream:
        json.dump(dict(tag=tag),stream);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    request_archive=publish(out/'request-original.json',temp.read_bytes())
    require(process_start(owner['pid'])==owner['starttime_ticks'], 'Owner changed before publication')
    state=Path('/proc',str(owner['pid']),'stat').read_text().rsplit(')',1)[1].split()[0]
    require(state not in ('T','t'), 'Trainer was already stopped before publication')
    pause_start=time.monotonic()
    os.kill(owner['pid'],signal.SIGSTOP)
    try:
        # Exclusive link refuses a concurrently published foreign request.
        os.link(temp,request);temp.unlink()
        request_pin=pin(request)
        request_time=time.time()
    finally:
        require(process_start(owner['pid'])==owner['starttime_ticks'], 'Owner changed during publication')
        os.kill(owner['pid'],signal.SIGCONT)
    publish(out/'request-publication.json',dict(tag=tag,latch=latch,owner=owner,request=request_pin,
        request_archive=request_archive,request_time=request_time,brief_exact_owner_pause=True,
        owner_pause_s=time.monotonic()-pause_start))
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        require(process_start(owner['pid'])==owner['starttime_ticks'], 'Owner changed during save')
        if not request.exists() and source.exists() and json.loads(slot.read_text())==dict(tag=tag):break
        time.sleep(.1)
    else:raise ValueError('One save request did not complete; no retry')
    os.chmod(source,0o444)
    with source.open('rb') as stream:os.fsync(stream.fileno())
    after_time=time.time();after_pin=pin(slot)
    after_archive=publish(out/'completed-slot-after.json',slot.read_bytes())
    return dict(checkpoint=pin(source),owner=owner,trigger_API=api,tag=tag,
        completed_slot_transition=dict(before=before,
            request=dict(actual_pin=request_pin,archive=request_archive),
            after=dict(actual_pin=after_pin,archive=after_archive),before_unix_s=before_time,
            request_unix_s=request_time,after_unix_s=after_time),
        CPU_verified=False,quality_qualified=False,promotion=False)


def run(job):
    out=Path(job['output']);out.mkdir(mode=0o700)
    entry=job['counter_module'];require(pin(entry['path'])==entry, 'Pure counter validator changed')
    spec=importlib.util.spec_from_file_location('_continuity_window_counters',entry['path'])
    counters=importlib.util.module_from_spec(spec);spec.loader.exec_module(counters)
    baseline_raw=Path(job['baseline_API']['path']).read_bytes()
    require(pin(job['baseline_API']['path'])==job['baseline_API'], 'Baseline API changed')
    baseline_api=json.loads(baseline_raw);baseline=counters.normalise(baseline_api);previous=copy.deepcopy(baseline)
    start=job['baseline_monotonic_s'];last_poll=start;last_applied=start;missing=None;last_guard=0
    result=None
    try:
        owner_and_files(job)
        require(time.monotonic()-start<30, 'Fresh prospective baseline missed its initial observation')
        while True:
            now=time.monotonic();require(now-last_poll<30, 'Observation gap reached30s');last_poll=now
            require(now-start<=job['cutoff_s'], 'Precommitted window cutoff expired')
            if now-last_guard>=5: owner_and_files(job);last_guard=now
            try:
                with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:raw=response.read(2<<20)
                value=json.loads(raw)
            except (OSError,ValueError):
                if missing is None:missing=now
                require(now-missing<30, 'API missing for30s');time.sleep(1);continue
            healthy(value,baseline_api,job['experiment'],time.time());missing=None
            current=counters.normalise(value);delta=progress(current,baseline,previous)
            if current['optimizer']['applied']>previous['optimizer']['applied']:last_applied=now
            require(now-last_applied<60, 'No applied optimizer outcome for60s')
            previous=current
            status=dict(state='observing',elapsed_s=now-start,observed_unix_s=time.time(),**delta)
            publish(out/'status.json',status,replace=True)
            if delta['both_horizons']:
                owner_and_files(job)
                api_pin=publish(out/'first-eligible-API.raw.json',raw)
                latch=publish(out/'first-durable-both-horizons.json',dict(status='LATCH',progress=delta,
                    observed_monotonic_s=now,observed_unix_s=time.time(),API=api_pin,job_experiment=job['experiment']))
                result=capture(job,out,latch,api_pin)
                publish(out/'result.json',dict(status='CAPTURED_FIRST_BOTH_HORIZONS',progress=delta,**result))
                publish(out/'status.json',dict(status,state='captured',checkpoint=result['checkpoint']),replace=True)
                return 0
            time.sleep(1)
    except BaseException as error:
        publish(out/'result.json',dict(status='FAILED_OR_INCOMPLETE_PRESERVED',error=repr(error),
            trainer_restarted=False,checkpoint_retried=False,promotion=False))
        return 1


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path)
    parser.add_argument('--job-sha256');args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no reads or actions');return 0
    require(args.job and pin(args.job)['sha256']==args.job_sha256, 'Exact root job required')
    job=json.loads(args.job.read_text());require(job['authorized'] is True, 'Explicit one-window selection required')
    for number in (signal.SIGINT,signal.SIGTERM):
        signal.signal(number,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    return run(job)


if __name__=='__main__':raise SystemExit(main())
