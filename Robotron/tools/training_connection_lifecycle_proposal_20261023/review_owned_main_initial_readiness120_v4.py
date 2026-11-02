"""Independently review one closed original120s dynamic-proc full-health diagnostic."""
import argparse
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

def load(name,pin):
    path=Path(pin['path']);raw=path.read_bytes()
    assert len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256']
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw)
    assert job['schema']=='robotron-closed-initial-readiness120-main-health-independent-review-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load('_dynamic120_h',job['helpers']);reader=load('_dynamic120_reader',job['reader'])
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    engine=load('_dynamic120_engine',job['engine'])
    archive=load('_dynamic120_archive',job['archive_reader'])
    closeout=load('_dynamic120_scope',job['scope_reader'])
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    selected=read(job['original_job']);report=read(job['original_report'])
    scope=closeout.closeout(Path(job['original_job']['path']).parent,h,archive,read,0)
    assert selected['schema']=='robotron-owned-main-health-v3-live120-job-v1'
    assert selected['duration_s']==120 and selected['poll_s']==.2
    assert report['status']=='ORIGINAL_MIXED_MAIN_HEALTH120_CLOSED_NOT_NATIVE_VALIDATED'
    assert report['health_job']==selected and report['job_sha256']==job['original_job']['sha256']
    assert report['writer']['all_original_samples_persisted']and report['writer']['thread_stopped']
    replay=engine.replay(selected,report['samples'],read(report['initial_cursors']),read,h,
        original_statuses=report['actual_status'])
    assert replay['transport']==report['transport']
    assert replay['samples']==len(report['samples'])and replay['deep_samples']==report['deep_samples']
    assert 240<=replay['samples']<=611
    assert replay['original_capture_span_s']>=119 and 120<=report['duration_s']<=125
    assert replay['maximum_observation_gap_s']<=.5
    assert report['guard_started_monotonic_s']<=replay['first_deep_monotonic_s']<replay['last_deep_monotonic_s']<=report['guard_ended_monotonic_s']
    assert replay['all197_held_inputs_final_independently_hashed']
    ready=replay['transport']['initial_readiness']
    assert ready['first_qualified_baseline_index']==ready['unaccepted_samples']
    assert 0<=ready['first_qualified_baseline_unix_s']-replay['first_observed_unix_s']<=2
    # Quiet runs remain full-health observations. Report actual proof kinds
    # separately; never invent a reconnect or dynamic-field event.
    proc=load('_dynamic120_proc',selected['sources']['proc_repeat'])
    groups=replay['transport']['groups']
    actual_dynamic=[g for g in groups if g['schema']==proc.SCHEMA
        and any(event['actual_changed_field_indices']for event in g['original_repeat_events'])]
    output=Path(job['output']);output.mkdir(mode=0o700)
    result=dict(schema='robotron-closed-initial-readiness120-main-health-independent-review-v1',
        status='ORIGINAL120S_FULL_RAW_HEALTH_REPLAY_VERIFIED_NOT_NATIVE_SELECTED',
        actual_original_scope=scope,original_report=job['original_report'],actual_replay=replay,
        actual_dynamic_proc_groups=actual_dynamic,actual_dynamic_proc_group_count=len(actual_dynamic),initial_readiness=ready,
        old2690_study_stays_invalid=True,old_failed_originals_requalified=False,
        source_sha256=args.source_sha256,job_sha256=args.job_sha256,
        scientific_guard_selected=False,quality_qualified=False,production_changed=False,
        scope='Original read-only health diagnostic. No full-game evaluation, policy-quality, learning-speed or useful-throughput conclusion.',
        created_unix_s=time.time())
    h.put(output/'review.json',result)
    print(json.dumps(dict(status=result['status'],samples=replay['samples'],deep_censuses=replay['deep_samples'],
        actual_dynamic_proc_groups=len(actual_dynamic),budget=replay['transport']['budget'])),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
