"""Independently preserve the original2739 invalid study; no game qualification."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

def load(pin,name):
    path=Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job')
    parser.add_argument('--job-sha256');parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    review=json.loads(raw);assert review['schema']=='robotron-failed-dedicated2739-independent-review-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(review['helpers'],'_failed2739_h');reader=load(review['reader'],'_failed2739_reader')
    arc=load(review['archive'],'_failed2739_arc')
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    for pin in review['inputs']:h.checked(pin)
    campaign=Path(review['campaign']);directory=campaign/'01-reference'
    job_pin=review['native_job'];job=read(job_pin);result=read(review['native_result'])
    assert job['quality_leg']=='R1' and job['quality_pair_precommit']['sha256']=='a8d442fb60bd5d4859e2c3683f9e91e410c71d33d6b0de3e3b25d87f17d05cb2'
    assert job['output']==str(directory/'diagnostic-output-original01')
    assert result['complete'] is result['quality_qualified'] is result['full_game_score_verified'] is False
    assert result['no_retry'] is True and result['original_attempt']==1
    assert result['main_health_report'] is None and result['main_health_failure'] is not None
    assert result['immutable_inputs_unchanged'] is result['original_lease_released'] is result['all_original_threads_stopped'] is True
    assert result['original_unsealed_journal_paths']==[]
    failure=read(result['main_health_failure'])
    assert failure['error']==failure['original_collector_error']=="ValueError('Skipped, reordered or delayed original stream sample')"
    assert len(failure['samples'])==failure['observed_samples']==1838
    assert len(failure['actual_status'])==1837 and failure['deep_samples']==71
    assert failure['writer']['all_original_samples_persisted'] is failure['writer']['thread_stopped'] is True
    assert failure['writer_error'] is None and failure['writer_thread_alive'] is False
    life=read(result['main_observer_lifecycle'])
    assert life['native_job']==job_pin and life['success'] is False and life['actual_controller_exit']==1
    assert life['all_owned_worker_and_controller_processes_reaped'] is life['original_scope_released'] is True
    family=read(job['source_family_manifest']);protocol=read(job['main_health_protocol'])
    for pin in family['main_observer'].values():h.checked(pin)
    worker_job=read(life['worker_job']);worker_outcome=read(life['worker_outcome'])
    assert worker_job['native_job']==job_pin and worker_job['native_protocol']==job['main_health_protocol']
    assert worker_job['health_job']==failure['health_job']==protocol['health_job']
    assert worker_job['unit_runtime_s']==9660 and worker_job['poll_s']==.2
    assert worker_outcome['job']==life['worker_job'] and worker_outcome['success'] is False
    assert worker_outcome['signals_received']==[] and worker_outcome['all_writer_threads_stopped'] is True
    assert worker_outcome['failure_report']==result['main_health_failure'] and worker_outcome['error']==failure['error']
    assert worker_outcome['worker_source']==family['main_observer']['worker']
    assert worker_outcome['protocol_source']==family['main_observer']['protocol']
    assert worker_job['parent']==worker_outcome['parent']==life['parent']
    scope_reports=[]
    def scope(owner_pin,closure_pin,config_pin,quota,memory,tasks,stop,kind):
        owner=read(owner_pin);closure=read(closure_pin);cfg=read(config_pin)
        fields=arc.archived_closure(closure,owner,read,exit_zero=False)
        expected=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],ExecMainPID=str(owner['pid']),
            ExecMainCode='1',ExecMainStatus='1',CPUQuotaPerSecUSec=quota,MemoryMax=str(memory),MemorySwapMax='0',
            RuntimeMaxUSec='2h 41min',TasksMax=tasks,TimeoutStopUSec=stop,SendSIGKILL='no',Restart='no',NRestarts='0')
        assert all(fields[k]==v for k,v in expected.items())
        assert closure['original_exit']==1 and closure['payload_retried'] is False
        command='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(Path(cfg['output'])/'tmp')+' '+' '.join(cfg['argv'])
        assert command+' ; ignore_errors=no ;'in fields['ExecStart']
        for pin in cfg['pins']:
            actual=h.pin(pin['path']);assert all(actual[k]==pin[k]for k in ('path','sha256','bytes'))
            assert all(actual['identity'][k]==v for k,v in pin['identity'].items())
        current=[]
        for unit in (owner['unit'],owner['timer']):
            r=subprocess.run(['systemctl','--user','show',unit],check=True,capture_output=True,text=True,timeout=10)
            f=dict(line.split('=',1)for line in r.stdout.splitlines()if '='in line)
            assert f['Id']==unit and f['LoadState']=='not-found'
            current.append(dict(argv=r.args,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
        assert birth(owner['pid'])!=owner['starttime_ticks']
        assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',owner['unit']).exists()
        start=int(fields['ExecMainStartTimestampMonotonic'])/1e6;end=int(fields['ExecMainExitTimestampMonotonic'])/1e6
        assert 0<start<end<=time.monotonic()and end-start<=9660
        scope_reports.append(dict(kind=kind,owner=owner_pin,closure=closure_pin,config=config_pin,actual_exit=1,
            actual_interval=[start,end],actual_six_archives_resources_argv_pins_release_and_reaping_verified=True,post_release_units=current))
        return owner,cfg,fields,start,end
    native_owner,native_cfg,native_fields,started,ended=scope(review['native_owner'],review['native_closure'],review['native_config'],'12s',16<<30,'512','30s','native')
    observer_owner,observer_cfg,observer_fields,ws,we=scope(life['worker_owner'],life['worker_closure'],life['worker_config'],'2s',4<<30,'128','5s','observer')
    assert native_fields['KillMode']=='mixed' and started<=ws<we<=ended
    assert worker_job['parent']['pid']==native_owner['pid']and worker_job['parent']['birth']==native_owner['starttime_ticks']
    assert worker_job['parent']['argv']==native_cfg['argv']and worker_job['parent']['job']==job_pin
    assert worker_job['parent']['source']==job['runtime']
    assert worker_job['deadline_monotonic_s']==result['native_deadline_monotonic_s']==result['native_started_monotonic_s']+9600
    assert worker_outcome['ended_monotonic_s']<worker_job['deadline_monotonic_s']
    child=read(life['controller_child']);assert birth(child['pid'])!=child['birth']
    reaped=result['original_post_origin_child_reap'];assert reaped['all_original_children_reaped'] is True
    assert reaped['unknown_slots']==[] and reaped['signals_sent'] is reaped['exit_statuses_normalized'] is False
    assert set(reaped['original_children'])==set(result['original_slots'])=={str(s)for s in range(4096,4128)}
    for slot,entry in result['original_slots'].items():
        child=reaped['original_children'][slot]
        assert entry['pid']==child['pid']and entry['birth']==child['birth']and entry['actual_exit']==child['actual_exit']==0
        assert birth(entry['pid'])!=entry['birth']and entry['outputs_sealed_after_original_writer_closure'] is True
        assert entry['original_unsealed_output_paths']==[]
        for pin in entry['files'].values():h.checked(pin)
    cohort=result['after_intentional_stop']
    assert cohort['count']==cohort['pending']==0 and cohort['started']==cohort['abandoned']==32
    assert cohort['complete'] is cohort['valid'] is False
    for folder in ('02-candidate','03-reference','04-candidate'):assert not(campaign/folder).exists()
    assert not(campaign/'independent-campaign-assessment-original01').exists()
    outcome=read(review['sequence_outcome']);assert outcome['quality_qualified'] is False and outcome['status']=='ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY'
    for pin in (review['sequence_intent'],review['display_intent']):
        o=read(pin);assert birth(o['pid'])!=o['birth']
    # Preserve the absent rejected status; replay every raw record and require
    # the original stream to fail before a status could exist for that record.
    read_indices=[];gaps=[];previous=None;last_transport=None
    sample_paths={p['path']for p in failure['samples']}
    def raw_read(pin,as_json=True):
        nonlocal previous,last_transport
        value=read(pin,as_json)
        if pin['path']in sample_paths:
            t=value['transport'];read_indices.append(t['index'])
            if previous is not None:gaps.append(dict(index=t['index'],gap_s=t['observed_unix_s']-previous))
            previous=t['observed_unix_s'];last_transport={key:t[key]for key in ('index','API_begin_unix_s','API_end_unix_s','tcp_begin_unix_s','tcp_end_unix_s','observed_unix_s')}
        return value
    engine=load(failure['health_job']['sources']['full_health_engine'],'_failed2739_engine')
    try:
        engine.replay(failure['health_job'],failure['samples'],read(failure['initial_cursors']),raw_read,h,
            prior_groups=[],original_statuses=failure['actual_status']+[None])
    except ValueError as error:
        assert repr(error)==failure['error'];raw_error=repr(error)
    else:raise AssertionError('Original failed stream unexpectedly validated')
    assert read_indices==list(range(1838))
    violations=[gap for gap in gaps if gap['gap_s']>.5]
    assert len(violations)==1 and violations[0]['index']==1837
    assert len(read(failure['samples'][-1])['transport']['raw_API']['base64'])>0
    h.checked(job['lease']);fd=os.open(job['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    for port in (19998,*range(20000,20032)):
        with socket.socket()as probe:probe.bind(('127.0.0.1',port))
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],check=True,capture_output=True,text=True,timeout=10)
    assert job['gpu_uuid']not in gpu.stdout and 'torch'not in sys.modules
    output=Path(review['output']);output.mkdir(mode=0o700)
    report=h.put(output/'report.json',dict(schema='robotron-failed-dedicated2739-independent-closeout-review-v1',
        native_job=job_pin,native_result=review['native_result'],original_scope_reviews=scope_reports,
        original_failure_report=result['main_health_failure'],all1838_raw_samples_replayed_to_exact_first_failure=True,
        original_successful_statuses=1837,rejected_sample_status_absent=True,first_failure_index=1837,
        raw_replay_error=raw_error,maximum_gap_s=max(g['gap_s']for g in gaps),gap_violations=violations,
        rejected_transport_timestamps=last_transport,physical_censuses_retained=71,
        all32_actual_MAME_reaped_exit0=True,all_private_resources_released=True,
        main_health_writer_closed=True,sequence_and_display_terminal=True,
        counts=dict(completed=0,started=32,pending=0,abandoned=32),C1_R2_C2='NOT_RUN',
        all_original_errors_retained=result['errors'],candidate_and_study_retry_forbidden=True,
        original_source_pins_unchanged=True,quality_qualified=False,full_game_score_verified=False,
        publication=False,root_cause_not_proven=True,created_unix_s=time.time()))
    print(json.dumps(dict(report=report,first_failure_index=1837,max_gap_s=violations[0]['gap_s'],quality_qualified=False)))
    return 0

if __name__=='__main__':raise SystemExit(main())
