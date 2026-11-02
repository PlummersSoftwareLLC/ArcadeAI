"""One original closed mixed main-health observation: immutable raw CPU review."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time


def load(name,pin):
    p=Path(pin['path']);raw=p.read_bytes();assert len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-closed-mixed-main-health-independent-review-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load('_closed_main_h',job['helpers']);reader=load('_closed_main_reader',job['reader'])
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    engine=load('_closed_main_engine',job['engine']);archive=load('_closed_main_archive',job['archive_reader'])
    closeout=load('_closed_main_scope',job['scope_reader'])
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    selected=read(job['original_job']);report=read(job['original_report'])
    scope=closeout.closeout(Path(job['original_job']['path']).parent,h,archive,read,0)
    assert report['status']=='ORIGINAL_MIXED_MAIN_HEALTH120_CLOSED_NOT_NATIVE_VALIDATED'
    assert report['health_job']==selected and report['job_sha256']==job['original_job']['sha256']
    assert report['writer']['all_original_samples_persisted']and report['writer']['thread_stopped']
    replay=engine.replay(selected,report['samples'],read(report['initial_cursors']),read,h,original_statuses=report['actual_status'])
    assert replay['transport']==report['transport']and replay['samples']==600 and replay['deep_samples']==24
    assert replay['original_capture_span_s']>=119 and 120<=report['duration_s']<=125
    assert report['guard_started_monotonic_s']<=replay['first_deep_monotonic_s']<replay['last_deep_monotonic_s']<=report['guard_ended_monotonic_s']
    assert replay['transport']['budget']['proc_repeat_groups']==1
    actual=replay['transport']['groups'][0];assert actual['kind']=='exact_owned_trainer_proc_repeat'
    assert len(actual['original_repeat_events'])==1 and len(actual['original_repeat_events'][0]['occurrences'])==2
    output=Path(job['output']);output.mkdir(mode=0o700)
    result=dict(status='ORIGINAL_LIVE600_SAMPLES24_CENSUSES_REAL_OWNED_PROC_REPEAT_RAW_REPLAY_VERIFIED_NOT_NATIVE_SELECTED',
        actual_original_scope=scope,original_report=job['original_report'],actual_replay=replay,
        actual_real_proc_certificate=actual,old_failed600_stays_invalid=True,whole_original597_stays_invalid=True,
        source_sha256=args.source_sha256,job_sha256=args.job_sha256,full_native_scope_and9000s_resource_validation_pending=True,
        scientific_guard_selected=False,quality_qualified=False,production_changed=False,created_unix_s=time.time())
    h.put(output/'review.json',result);print(json.dumps(dict(status=result['status'],samples=600,deep_censuses=24,
        real_proc_repeat_slot=actual['slot'],charged_s=actual['charged_s'])),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
