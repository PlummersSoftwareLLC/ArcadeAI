"""Independent complete raw, durable-write, runtime and lifecycle probe review."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job')
    p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    review=json.loads(raw);assert review['schema']=='robotron-independent-runtime-cadence-writer-probe-review-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(review['helpers'],'_probe_review_h');reader=load(review['reader'],'_probe_review_reader')
    arc=load(review['archive'],'_probe_review_arc');closer=load(review['scope_helper'],'_probe_review_close')
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    for pin in review['inputs']:h.checked(pin)
    directory=Path(review['directory']);scope=closer.closeout(directory,h,arc,read,0)
    job_pin=h.pin(directory/'job.json');job=read(job_pin);original_pin=h.pin(Path(job['output'])/'report.json');original=read(original_pin)
    assert original['job']==job_pin and original['every_original_arm_once'] is True
    assert original['health_failures_not_requalified'] is True and original['quality_qualified'] is False
    assert [r['arm']for r in original['original_reports']]==[r['id']for r in job['arms']]
    parent_pin=h.pin(Path(job['output'])/'original-parent.json');parent=read(parent_pin);owner=read(scope['owner'])
    assert parent['pid']==owner['pid']and parent['birth']==owner['starttime_ticks']and parent['unit']==owner['unit']
    assert parent['invocation_id']==owner['invocation_id']and parent['job']==job_pin
    config=read(h.pin(directory/'controller-config.json'));assert parent['argv']==config['argv']
    source=parent['source'];h.checked(source)
    engine=load(job['health_job']['sources']['full_health_engine'],'_probe_review_engine')
    evidence=[]
    for selected,entry in zip(job['arms'],original['original_reports']):
        arm=read(entry['report']);child=read(entry['child']);exit=read(entry['original_exit'])
        assert arm['arm']==selected and arm['parent']==parent_pin and arm['all_writer_threads_stopped'] is True
        assert exit['actual_exit']==0 and exit['child_reaped'] is exit['birth_absent'] is True
        assert exit['original_child']==entry['child']and exit['original_attempt']==1 and exit['no_retry'] is True
        assert birth(child['pid'])!=child['birth']and child['parent']==parent_pin
        expected=[selected['executable'],*selected['interpreter_options'],'-I','-B',source['path'],'--execute','--job',job_pin['path'],
            '--job-sha256',job_pin['sha256'],'--source-sha256',source['sha256'],'--arm',selected['id']]
        assert child['argv']==expected and child['cgroup']=='0::'+parent['cgroup']+'\n'
        assert arm['before']['pid']==arm['after']['pid']==child['pid']and arm['before']['birth']==arm['after']['birth']==child['birth']
        for position in ('before','after'):
            resource=arm[position]
            assert resource['cgroup']==parent['cgroup']and resource['cpu_max']=='200000 100000\n'
            assert resource['GIL_enabled']==selected['GIL_enabled']and resource['executable']==selected['executable']
        assert arm['after']['monotonic_s']-arm['before']['monotonic_s']>=25
        assert len(arm['durable_write_bursts'])==6 and arm['stress_errors']==[]
        for index,burst in enumerate(arm['durable_write_bursts']):
            assert burst['index']==index and burst['offset_s']==job['burst_offsets_s'][index]
            assert burst['before']['pid']==burst['after']['pid']==child['pid']and len(burst['files'])==32
            assert burst['before']['monotonic_s']<burst['after']['monotonic_s']
            for item,pin in enumerate(burst['files']):
                h.checked(pin)
                assert pin['path']==str(Path(job['output'])/selected['id']/('durable-stress-%02d-%02d.json'%(index,item)))
                assert pin['sha256']==job['stress_record']['sha256']and pin['bytes']==job['stress_record']['bytes']
                assert pin['identity']['mode']=='0o444'and pin['identity']['uid']==job['stress_record']['identity']['uid']and pin['identity']['nlink']==1
        if arm['valid_closed_health']:
            assert arm['error']is arm['failed_health']is None
            closed=read(arm['closed_health']);assert closed['health_job']==job['health_job']
            assert closed['writer']['all_original_samples_persisted'] is closed['writer']['thread_stopped'] is True
            raw=engine.replay(job['health_job'],closed['samples'],read(closed['initial_cursors']),read,h,original_statuses=closed['actual_status'])
            assert raw['transport']==closed['transport']and raw['deep_samples']==closed['deep_samples']
            assert raw['maximum_observation_gap_s']==arm['maximum_gap_s']<.5
            assert raw['samples']==arm['original_raw_samples']and raw['deep_samples']>=4
            assert len(arm['timings'])==raw['samples']
        else:
            assert arm['closed_health']is None and arm['error']is not None
            failed=read(arm['failed_health']);count=len(failed['samples'])-len(failed['actual_status'])
            assert count in (0,1)and failed['writer_thread_alive'] is False
            try:engine.replay(job['health_job'],failed['samples'],read(failed['initial_cursors']),read,h,original_statuses=failed['actual_status']+[None]*count)
            except ValueError as error:assert repr(error)==failed['original_collector_error'];raw=dict(expected_failure=repr(error),samples=len(failed['samples']))
            else:raise AssertionError('Failed diagnostic arm was requalified')
        def cpu_stat(value):return {k:int(v)for k,v in (line.split()for line in value.splitlines())}
        before,after=cpu_stat(arm['before']['cpu_stat']),cpu_stat(arm['after']['cpu_stat'])
        evidence.append(dict(arm=selected['id'],original_report=entry['report'],raw_independent_replay=raw,
            actual_child_and_runtime_argv_birth_GIL_and_reaping_verified=True,all192_exact_original_durable_writes_verified=True,
            poll_s=selected['poll_s'],GIL_enabled=selected['GIL_enabled'],valid_closed_health=arm['valid_closed_health'],
            max_gap_s=arm['maximum_gap_s'],quota_throttled_periods=after['nr_throttled']-before['nr_throttled'],
            maximum_observe_s=max((t.get('observe_s',0)for t in arm['timings']),default=0),
            maximum_projection_s=max((t.get('projection_s',0)for t in arm['timings']),default=0),
            GC_summary=arm['GC_summary'],original_child_exit=entry['original_exit']))
    by_name={e['arm']:e for e in evidence}
    comparisons={runtime:dict(p200_max_gap_s=by_name[runtime+'-p200']['max_gap_s'],p100_max_gap_s=by_name[runtime+'-p100']['max_gap_s'],
        both_valid=by_name[runtime+'-p200']['valid_closed_health']and by_name[runtime+'-p100']['valid_closed_health'])for runtime in ('py312','py314')}
    assert 'torch'not in sys.modules
    output=Path(review['output']);output.mkdir(mode=0o700)
    rp=h.put(output/'report.json',dict(schema='robotron-independent-runtime-cadence-writer-probe-review-v1',
        original_scope=scope,original_report=original_pin,original_probe_job=job_pin,arms=evidence,comparisons=comparisons,
        all_original_raw_and_durable_write_and_child_evidence_verified=True,
        stress_not_claimed_as_original_failure_cause=True,short_diagnostic_not_long_native_reliability_proof=True,
        prospective_main_or_quality_source_change_not_selected=True,quality_qualified=False,playing_gain_verified=False,
        learning_speed_gain_verified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=rp,comparisons=comparisons)),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
