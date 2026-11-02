"""Independent serialized live protocol reference600 load review; no game quality."""
import argparse
import ast
import collections
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def analyse(timing,samples,read):
    assert timing['schema']=='robotron-diagnostic-observer-critical-path-timings-v1'
    assert timing['truncated'] is False and timing['health_predicates_changed'] is False
    assert timing['events_persisted_only_after_capture_stopped'] is True
    rows=timing['events'];assert len(rows)<=65536 and [r['event']for r in rows]==list(range(len(rows)))
    stages=[];gc=[];by_stage=collections.defaultdict(list)
    for row in rows:
        if row['kind']=='gc':gc.append(row);continue
        assert row['kind']=='stage'and row['stage']in ('initial_parent','emit.starting','verify_parent','guard.observe','emit.running','sleep')
        before,after=row['before'],row['after']
        for clock in (before,after):
            assert all(type(clock[k])in (int,float)and math.isfinite(clock[k])for k in ('monotonic_s','unix_s','thread_cpu_s','process_cpu_s'))
            assert all(type(v)is int and v>=0 for v in clock['cpu_stat'].values())
        wall=after['monotonic_s']-before['monotonic_s'];assert wall>=0
        assert abs((after['unix_s']-before['unix_s'])-wall)<.05
        assert after['thread_cpu_s']>=before['thread_cpu_s'] and after['process_cpu_s']>=before['process_cpu_s']
        measured=dict(stage=row['stage'],index=row['index'],event=row['event'],wall_s=wall,
            thread_cpu_s=after['thread_cpu_s']-before['thread_cpu_s'],process_cpu_s=after['process_cpu_s']-before['process_cpu_s'],
            before_unix_s=before['unix_s'],after_unix_s=after['unix_s'],unit_check=row['unit_check'],
            requested_sleep_s=row['requested_sleep_s'],error=row['error'],
            quota_throttled_usec=after['cpu_stat']['throttled_usec']-before['cpu_stat']['throttled_usec'],
            quota_throttled_periods=after['cpu_stat']['nr_throttled']-before['cpu_stat']['nr_throttled'])
        assert measured['quota_throttled_usec']>=0 and measured['quota_throttled_periods']>=0
        stages.append(measured);by_stage[row['stage']].append(measured)
    guards={row['index']:row for row in by_stage['guard.observe']}
    assert len(guards)==len(by_stage['guard.observe'])==len(samples)
    observations=[]
    for index,pin in enumerate(samples):
        record=read(pin);sample=record['transport'];guard=guards[index]
        assert sample['index']==index and guard['error']is None
        assert guard['before_unix_s']<=sample['API_begin_unix_s']<=sample['observed_unix_s']<=guard['after_unix_s']
        observations.append(dict(index=index,observed_unix_s=sample['observed_unix_s'],
            API_begin_unix_s=sample['API_begin_unix_s'],API_end_unix_s=sample['API_end_unix_s'],
            tcp_begin_unix_s=sample['tcp_begin_unix_s'],tcp_end_unix_s=sample['tcp_end_unix_s'],deep=record['deep']is not None))
    gaps=[dict(index=b['index'],gap_s=b['observed_unix_s']-a['observed_unix_s'],begin=a['observed_unix_s'],end=b['observed_unix_s'])for a,b in zip(observations,observations[1:])]
    assert all(gap['gap_s']<=.5 for gap in gaps)
    top=[]
    for gap in sorted(gaps,key=lambda row:row['gap_s'],reverse=True)[:20]:
        overlapping=[]
        for stage in stages:
            overlap=max(0.,min(gap['end'],stage['after_unix_s'])-max(gap['begin'],stage['before_unix_s']))
            if overlap:overlapping.append(dict(stage=stage,overlap_s=overlap))
        top.append(dict(gap,stages=overlapping,unaccounted_s=gap['gap_s']-sum(r['overlap_s']for r in overlapping),
            GC_events=[r for r in gc if gap['begin']<=r['monotonic_s']+timing['started']['unix_s']-timing['started']['monotonic_s']<=gap['end']]))
    summary={name:dict(count=len(items),maximum_wall_s=max(r['wall_s']for r in items),total_wall_s=sum(r['wall_s']for r in items),
        total_thread_cpu_s=sum(r['thread_cpu_s']for r in items),quota_throttled_periods=sum(r['quota_throttled_periods']for r in items),
        slowest=sorted(items,key=lambda r:r['wall_s'],reverse=True)[:10])for name,items in by_stage.items()}
    return dict(events=len(rows),stages=len(stages),GC_events=len(gc),raw_samples=len(samples),
        maximum_gap_s=max(r['gap_s']for r in gaps),stage_summary=summary,largest20_gap_intervals=top,
        instrumentation_has_some_cost=True,previous_failed_case_cause_reproduced=False,
        no_scientific_fix_or_reliability_claim=True,quality_qualified=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job')
    p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    review=json.loads(raw);assert review['schema']=='robotron-serialized-free314-load600-independent-review-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(review['helpers'],'_critical_review_h');reader=load(review['reader'],'_critical_review_reader')
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    for pin in review['inputs']:h.checked(pin)
    job_pin=review['native_job'];job=read(job_pin);out=Path(job['output']);result=read(review['native_result'])
    assert job['schema']=='robotron-native32-serialized-free314-observer-load-diagnostic-v1'and job['diagnostic_only']is True and 'quality_leg'not in job
    assert result['complete'] is result['quality_qualified'] is False and result['main_health_failure']is None
    assert result['errors'][0]=="ValueError('PRECOMMITTED_CRITICAL_PATH600_LOAD_STOP_AFTER_ALL32_PREFIXES_NOT_A_QUALITY_RESULT')"
    assert result['original_lease_released']is result['all_original_threads_stopped']is result['immutable_inputs_unchanged']is True
    assert result['original_unsealed_journal_paths']==[]
    marker=read(h.pin(out/'original-all32-prefix-diagnostic-stop.json'))
    assert marker['reason']=='PRECOMMITTED_SERIALIZED_FREE314_REFERENCE600_LOAD_STOP'
    assert set(marker['prefixes'])=={str(s)for s in range(4096,4128)}
    assert marker['observed_monotonic_s']-result['native_started_monotonic_s']>=600
    assert marker['observed_monotonic_s']<result['native_deadline_monotonic_s']==result['native_started_monotonic_s']+720
    arc=load(review['archive'],'_critical_review_arc');owner=read(review['native_owner']);cfg=read(review['native_config'])
    fields=arc.archived_closure(read(review['native_closure']),owner,read,exit_zero=False)
    for k,v in dict(Id=owner['unit'],InvocationID=owner['invocation_id'],ExecMainPID=str(owner['pid']),ExecMainCode='1',ExecMainStatus='1',
        CPUQuotaPerSecUSec='12s',MemoryMax=str(16<<30),MemorySwapMax='0',RuntimeMaxUSec='13min',TasksMax='512',
        TimeoutStopUSec='30s',KillMode='mixed',SendSIGKILL='no',Restart='no',NRestarts='0').items():assert fields[k]==v
    command='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(Path(cfg['output'])/'tmp')+' '+' '.join(cfg['argv'])
    assert command+' ; ignore_errors=no ;'in fields['ExecStart']
    for pin in cfg['pins']:
        actual=h.pin(pin['path']);assert all(actual[k]==pin[k]for k in ('path','sha256','bytes'))
        assert all(actual['identity'][k]==v for k,v in pin['identity'].items())
    control=load(review['native_controller'],'_critical_review_control');control.checked_config(review['native_config']['path'])
    for unit in (owner['unit'],owner['timer']):assert control.show(unit)['LoadState']=='not-found'
    assert birth(owner['pid'])!=owner['starttime_ticks']
    assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',owner['unit']).exists()
    started=int(fields['ExecMainStartTimestampMonotonic'])/1e6;ended=int(fields['ExecMainExitTimestampMonotonic'])/1e6
    assert 0<started<ended<=time.monotonic()and ended-started<=780
    family=read(job['source_family_manifest']);protocol=read(job['main_health_protocol'])
    verifier=load(family['main_observer']['reviewer'],'_critical_review_observer')
    checked=verifier.verify(job,job_pin,owner,cfg['argv'],result['main_observer_lifecycle'],protocol,family,[],read,h)
    assert checked['closed_report']==result['main_health_report']
    closed=read(result['main_health_report']);assert closed['actual_status']==result['main_samples']
    assert len(closed['samples'])>=2800 and closed['deep_samples']>=100
    engine=load(protocol['health_job']['sources']['full_health_engine'],'_critical_review_engine')
    replay=engine.replay(protocol['health_job'],closed['samples'],read(closed['initial_cursors']),read,h,prior_groups=[],original_statuses=closed['actual_status'])
    assert replay['transport']==closed['transport']and replay['deep_samples']==closed['deep_samples']
    assert started<=closed['guard_started_monotonic_s']<=replay['first_deep_monotonic_s']<=replay['last_deep_monotonic_s']<=closed['guard_ended_monotonic_s']<=ended
    assert closed['guard_ended_monotonic_s']>=marker['observed_monotonic_s']
    outcome=read(checked['worker_outcome'])
    assert outcome['interpreter']['GIL_enabled']is False and outcome['interpreter']['major_minor']==[3,14]
    assert family['main_observer']['protocol']['sha256']=='7f39fb03c43bb9856873913d59329bbe05717bfc8fd5a47abbfd7b1a31bc1a7f'
    lock_pin=h.pin(out/'main-observations/live.json.lock');h.checked(lock_pin)
    assert lock_pin['bytes']==0 and lock_pin['identity']['mode']=='0o600'and lock_pin['identity']['nlink']==1
    lock_fd=os.open(lock_pin['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock_fd,fcntl.LOCK_UN)
    finally:os.close(lock_fd)
    proofs=family['serialized_protocol_components'];component=read(proofs['protocol'])
    assert component['original_guards']==38 and component['concurrent_publications']==5000
    assert component['strict_original_read_and_publish_bodies_AST_unchanged']and component['finish_protocol_unchanged']
    provenance=read(proofs['source_provenance'])
    original=ast.parse(read(provenance['original_protocol'],False).decode())
    prospective=ast.parse(read(family['main_observer']['protocol'],False).decode())
    nodes={n.name:n for n in prospective.body if isinstance(n,ast.FunctionDef)}
    for node in original.body:
        if isinstance(node,ast.FunctionDef):
            selected=nodes[dict(checked_read='_checked_read_strict',publish_live='_publish_live_unlocked').get(node.name,node.name)]
            selected.name=node.name;assert ast.dump(selected)==ast.dump(node)
    timing_pin=None;measured=None
    policy=result['policy_before'];loaded_pin=h.pin(out/'original-loaded-policy.json');loaded=read(loaded_pin)
    assert loaded['policy']==policy and policy['checkpoint_sha256']==job['checkpoint']['sha256']=='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
    assert policy['training_enabled']is policy['replay_enabled']is False and policy['epsilon']==policy['expert_ratio']==0
    assert loaded['gpu_uuid']==job['gpu_uuid']and loaded['compile_report']['all_shapes_verified']==list(range(1,17))
    assert loaded['memory_is_none']is loaded['optimizer_is_none']is True
    initial_helpers=load(review['initial_helpers'],'_critical_review_initial')
    initial=initial_helpers.validate_initial_readiness(read(result['initial_main_readiness']),result['initial_main_readiness'],job,job_pin,replay,loaded_pin,read(h.pin(out/'original-fixed-admission.json')),started,ended)
    wire=load(review['original_wire_auditor'],'_critical_review_wire');wire.dependencies();games=wire.games_audit
    reaped=result['original_post_origin_child_reap'];assert reaped['all_original_children_reaped']is True
    assert reaped['unknown_slots']==[] and reaped['signals_sent']is reaped['exit_statuses_normalized']is False
    prefixes=[]
    for slot in range(4096,4128):
        entry=result['original_slots'][str(slot)];child=reaped['original_children'][str(slot)]
        assert entry['pid']==child['pid']and entry['birth']==child['birth']and entry['actual_exit']==child['actual_exit']==0
        assert birth(entry['pid'])!=entry['birth']and entry['outputs_sealed_after_original_writer_closure']is True
        assert entry['original_unsealed_output_paths']==[]and marker['prefixes'][str(slot)]==entry['prefix_summary']
        for pin in entry['files'].values():h.checked(pin)
        rows=games.lines(read(entry['files']['producer.jsonl'],False));subject=dict(slot=slot,session=job['sessions'][str(slot)],connection=job['connections'][str(slot)])
        assert all(all(row[k]==v for k,v in subject.items())for row in rows)
        assert rows[-1]==entry['prefix_summary']['footer']and rows[-1]['reason']=='prefix_complete'and rows[-1]['failed']is False
        chunks=[r for r in rows if r['kind']=='raw_ROM_chunk'];assert [r['offset']for r in chunks]==list(range(0,0x19000,128))
        image=b''.join(bytes.fromhex(r['data_hex'])for r in chunks);assert len(image)==102400 and hashlib.sha256(image).hexdigest()==job['loaded_rom_sha256']
        raw_wire=games.lines(read(entry['files']['proxy.jsonl'],False));assert [r['proxy_event']for r in raw_wire]==list(range(1,len(raw_wire)+1))
        ledger=wire.audit_prefix_ledger(raw_wire,rows,subject,job['loaded_rom_sha256'],entry)
        prefixes.append(dict(slot=slot,ledger=ledger,all1200_original_pairs_and_loaded_ROM_verified=True,full_tail_quality_not_validated=True))
    h.checked(job['lease']);fd=os.open(job['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    for port in (19998,*range(20000,20032)):
        with socket.socket()as sock:sock.bind(('127.0.0.1',port))
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,check=True,timeout=10)
    assert job['gpu_uuid']not in gpu.stdout and 'torch'not in sys.modules
    output=Path(review['output']);output.mkdir(mode=0o700)
    rp=h.put(output/'report.json',dict(schema='robotron-serialized-free314-reference600-independent-review-v1',native_job=job_pin,native_result=review['native_result'],
        native_actual_interval=[started,ended],native_expected_exit1_verified=True,all_native_archives_resources_commands_pins_release_verified=True,
        worker_independent_review=checked,raw_replay=replay,initial_readiness=initial,all32_original_startup_prefixes=prefixes,
        timing_source_report=timing_pin,timing_analysis=measured,precommitted600s_stop=marker,
        strict_live_protocol=family['main_observer']['protocol'],actual_live_lock=lock_pin,strict_original_reader_and_publisher_AST_verified=True,native600_load_requirement_achieved=True,
        all_original_errors_retained=result['errors'],private_resources_free=True,scientific_case=False,
        previous_scientific_failure_reproduced=False,health_fix_verified=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=rp,samples=len(closed['samples']),max_gap_s=replay['maximum_observation_gap_s'])));return 0

if __name__=='__main__':raise SystemExit(main())
