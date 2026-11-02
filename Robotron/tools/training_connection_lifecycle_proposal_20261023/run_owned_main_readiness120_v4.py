"""One read-only120-second observation using the reusable mixed full-health engine."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time


def load(name,pin):
    path=Path(pin['path']);raw=path.read_bytes()
    assert len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-owned-main-health-v3-live120-job-v1'
    assert job['duration_s']==120 and job['poll_s']==.2 and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load('_owned120_h',job['sources']['helpers']);h.checked(job['sources']['full_health_engine'])
    engine=load('_owned120_engine',job['sources']['full_health_engine']);output=Path(job['output'])
    output.mkdir(mode=0o700);(output/'samples').mkdir(mode=0o700);guard=None;statuses=[]
    try:
        guard=engine.MainHealth(job,output,h);started=time.monotonic()
        while time.monotonic()-started<120 or guard.collector.stream.pending is not None:
            assert time.monotonic()-started<122,'Prospective fixed2s pending closure bound exceeded'
            tick=time.monotonic();guard.observe();time.sleep(max(0,.2-(time.monotonic()-tick)))
        result=guard.close();result.update(status='ORIGINAL_MIXED_MAIN_HEALTH120_CLOSED_NOT_NATIVE_VALIDATED',
            duration_s=time.monotonic()-started,job_sha256=args.job_sha256,source_sha256=args.source_sha256,
            scientific_guard_selected=False,quality_qualified=False,created_unix_s=time.time())
        h.put(output/'report.json',result)
        print(json.dumps(dict(status=result['status'],samples=len(result['samples']),deep_samples=result['deep_samples'],
            budget=result['transport']['budget'],writer=result['writer'])),flush=True);return 0
    except BaseException as error:
        failure=guard.preserve_failure(error)if guard is not None else dict(status='ORIGINAL_HEALTH120_SETUP_FAILED',error=repr(error))
        failure.update(quality_qualified=False,production_changed=False,created_unix_s=time.time())
        h.put(output/'failure.json',failure);print(json.dumps({k:v for k,v in failure.items()if k not in ('samples','actual_status','health_job')}),flush=True);return 1


if __name__=='__main__':raise SystemExit(main())
