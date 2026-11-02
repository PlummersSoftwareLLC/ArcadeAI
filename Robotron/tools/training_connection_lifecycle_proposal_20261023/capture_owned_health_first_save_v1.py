"""One fresh60-second full-health prefix and one existing managed-save capture.

No learning-window/lr/model/replay change or evaluator launch. The existing
source-bound capture briefly pauses only the exact known trainer while
exclusively publishing its save request, then resumes it in its finally block.
SIGINT/SIGTERM are deferred across that bounded capture call to preserve this
resume path. All previous failed windows/studies remain unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import time


def load(name,pin):
    path=Path(pin['path']);raw=path.read_bytes();assert len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-owned-health-first-managed-save-job-v1'and job['prefix_s']==60 and job['poll_s']==.2
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load('_fresh_save_h',job['helpers'])
    for pin in [job['engine'],job['health_job'],job['selection'],job['binding']]:h.checked(pin)
    selected=json.loads(h.checked(job['health_job']).read_bytes());binding=json.loads(h.checked(job['binding']).read_bytes())
    assert selected['binding']==job['binding']and len(binding['held_hashes'])==197
    engine=load('_fresh_save_engine',job['engine']);window=load('_fresh_save_window',selected['sources']['window'])
    out=Path(job['output']);out.mkdir(mode=0o700);prefix_dir=out/'prefix';prefix_dir.mkdir();(prefix_dir/'samples').mkdir()
    old_handlers={sig:signal.signal(sig,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))for sig in (signal.SIGINT,signal.SIGTERM)}
    guard=None;captured=False
    try:
        target=window.MODEL/'managed-checkpoints'/(job['tag']+'.pt');assert not target.exists()
        guard=engine.MainHealth(selected,prefix_dir,h);start=time.monotonic()
        while time.monotonic()-start<60:
            tick=time.monotonic();guard.observe();time.sleep(max(0,.2-(time.monotonic()-tick)))
        prefix=guard.close();assert prefix['actual_status'][-1]['learner_frames']>prefix['actual_status'][0]['learner_frames']
        assert prefix['actual_status'][-1]['training_steps']>prefix['actual_status'][0]['training_steps']
        prefix_pin=h.put(out/'closed-original60s-prefix.json',prefix)
        last=json.loads(h.checked(prefix['samples'][-1]).read_bytes());packed=load('_fresh_save_raw_pack',selected['sources']['collector'])
        raw_API=packed.decode(last['transport']['raw_API']);API=json.loads(raw_API)
        assert API['client_count']==192 and API['learner_frame_count']>job['after_learner_frame_count']
        API_pin=window.publish(out/'prefix-endpoint-API.raw.json',raw_API)
        latch=h.put(out/'first-eligible-prefix-latch.json',dict(status='CLOSED_FRESH_HEALTH_PREFIX_ONLY_NOT32M_WINDOW',prefix=prefix_pin,API=API_pin,tag=job['tag'],created_unix_s=time.time(),quality_qualified=False))
        context=dict(binding,tag=job['tag']);window.owner_and_files(context)
        before=time.monotonic();mask=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM})
        try:result=window.capture(context,out,latch,API_pin);captured=True
        finally:signal.pthread_sigmask(signal.SIG_SETMASK,mask)
        h.put(out/'result.json',dict(status='CAPTURED_ONE_GENUINELY_LATER_POLICY_AFTER_CLOSED_HEALTH_PREFIX',
            prefix=prefix_pin,prefix_latch=latch,capture_elapsed_s=time.monotonic()-before,
            selection=job['selection'],original_attempt=1,no_retry=True,old_windows_and_studies_requalified=False,
            production_recipe_changed=False,**result))
        print(json.dumps(dict(status='CAPTURED_ONE_GENUINELY_LATER_POLICY',checkpoint=result['checkpoint'],CPU_verified=False,quality_qualified=False)),flush=True);return 0
    except BaseException as error:
        failure=dict(status='ORIGINAL_NEW_SAVE_SELECTION_FAILED_PRESERVED_NO_RETRY',error=repr(error),
            checkpoint_capture_returned=captured,quality_qualified=False,recipe_changed=False,created_unix_s=time.time())
        if guard is not None and not guard.closed:
            try:failure['prefix_failure']=guard.preserve_failure(error)
            except BaseException as close_error:failure['prefix_close_error']=repr(close_error)
        h.put(out/'failure.json',failure);print(json.dumps({k:v for k,v in failure.items()if k!='prefix_failure'}),flush=True);return 1
    finally:
        for sig,handler in old_handlers.items():signal.signal(sig,handler)


if __name__=='__main__':raise SystemExit(main())
