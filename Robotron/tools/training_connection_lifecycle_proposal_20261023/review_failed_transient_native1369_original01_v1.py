"""Independently preserve failed filtered native1369; never qualifies or retries the case."""
import argparse,collections,fcntl,hashlib,importlib.util,json,os,socket,subprocess,sys,time
from pathlib import Path

def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;review=json.loads(raw)
    assert review['schema']=='robotron-failed-transient-native1369-independent-review-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(review['helpers'],'_failed1369_h');reader=load(review['reader'],'_failed1369_r');arc=load(review['archive'],'_failed1369_arc')
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    for pin in review['inputs']:h.checked(pin)
    jp=review['native_job'];job=read(jp);result=read(review['native_result']);out=Path(job['output'])
    assert job['schema']=='robotron-native32-transient-live-filtered-free314-load-diagnostic-v1'and job['diagnostic_only']is True and 'quality_leg'not in job
    assert result['complete']is result['quality_qualified']is result['full_game_score_verified']is False
    assert result['original_attempt']==1 and result['no_retry']is True
    assert result['errors'][0]=="Original independent mixed full main-health watch: ValueError('Bounded original live lock wait exceeded')"
    assert result['main_health_report']is None and result['main_health_failure']is not None
    assert result['immutable_inputs_unchanged']is result['original_lease_released']is result['all_original_threads_stopped']is True
    assert result['original_unsealed_journal_paths']==[] and not(out/'original-all32-prefix-diagnostic-stop.json').exists()
    failure=read(result['main_health_failure']);expected="ValueError('Skipped, reordered or delayed original stream sample')"
    assert failure['error']==failure['original_collector_error']==expected
    assert len(failure['samples'])==failure['observed_samples']==1369 and len(failure['actual_status'])==1368 and failure['deep_samples']==53
    assert failure['writer']['all_original_samples_persisted']is failure['writer']['thread_stopped']is True
    assert failure['writer_error']is None and failure['writer_thread_alive']is False
    family=read(job['source_family_manifest']);protocol=read(job['main_health_protocol']);life=read(result['main_observer_lifecycle'])
    assert life['native_job']==jp and life['success']is False and life['actual_controller_exit']==1
    assert life['all_owned_worker_and_controller_processes_reaped']is life['original_scope_released']is True
    wj=read(life['worker_job']);wo=read(life['worker_outcome'])
    assert wj['native_job']==jp and wj['native_protocol']==job['main_health_protocol']and wj['source_family']==job['source_family_manifest']
    assert wj['health_job']==failure['health_job']==protocol['health_job']and wj['unit_runtime_s']==9660 and wj['poll_s']==.2
    assert wo['job']==life['worker_job']and wo['success']is False and wo['closed_report']is None
    assert wo['failure_report']==result['main_health_failure']and wo['error']==expected and wo['signals_received']==[]
    assert wo['all_writer_threads_stopped']is True and wj['parent']==wo['parent']==life['parent']and wj['nonce']==wo['nonce']
    assert wo['worker_source']==family['main_observer']['worker']and wo['protocol_source']==family['main_observer']['protocol']==wj['protocol_source']
    assert wo['interpreter']['GIL_enabled']is False and wo['interpreter']['major_minor']==[3,14]
    assert wo['interpreter']['binary']==wj['worker_interpreter']==family['main_observer_interpreter']
    for pin in [*family['main_observer'].values(),family['main_observer_interpreter']]:h.checked(pin)
    assert family['main_observer']['protocol']['sha256']=='f59df995a625ed534af1c2cb54a15c885a8e431ab84e3829e6a8b2c6ceb7bf10'
    scopes=[]
    def scope(op,cp,config,kind):
        owner=read(op);closure=read(cp);cfg=read(config);f=arc.archived_closure(closure,owner,read,exit_zero=False)
        native=kind=='native';values=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],ExecMainPID=str(owner['pid']),ExecMainCode='1',ExecMainStatus='1',
            CPUQuotaPerSecUSec='12s'if native else'2s',MemoryMax=str((16 if native else 4)<<30),MemorySwapMax='0',RuntimeMaxUSec='13min'if native else'2h 41min',
            TasksMax='512'if native else'128',TimeoutStopUSec='30s'if native else'5s',SendSIGKILL='no',Restart='no',NRestarts='0')
        assert all(f[k]==v for k,v in values.items())and closure['original_exit']==1 and closure['payload_retried']is False
        command='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(Path(cfg['output'])/'tmp')+' '+' '.join(cfg['argv'])
        assert command+' ; ignore_errors=no ;'in f['ExecStart']
        for pin in cfg['pins']:
            actual=h.pin(pin['path']);assert all(actual[k]==pin[k]for k in ('path','sha256','bytes'))and all(actual['identity'][k]==v for k,v in pin['identity'].items())
        current=[]
        for unit in (owner['unit'],owner['timer']):
            run=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,check=True,timeout=5)
            fields=dict(line.split('=',1)for line in run.stdout.splitlines()if '='in line)
            assert fields['Id']==unit and fields['LoadState']=='not-found';current.append(dict(argv=run.args,exit=run.returncode,stdout=run.stdout))
        assert birth(owner['pid'])!=owner['starttime_ticks']and not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',owner['unit']).exists()
        start=int(f['ExecMainStartTimestampMonotonic'])/1e6;end=int(f['ExecMainExitTimestampMonotonic'])/1e6
        assert 0<start<end<=time.monotonic()and end-start<=(780 if native else 9660)
        scopes.append(dict(kind=kind,owner=op,closure=cp,config=config,actual_exit=1,actual_interval=[start,end],actual_six_archives_resources_argv_pins_release_reaping_verified=True,post_release_units=current))
        return owner,cfg,f,start,end
    no,nc,nf,ns,ne=scope(review['native_owner'],review['native_closure'],review['native_config'],'native')
    oo,oc,of,ws,we=scope(life['worker_owner'],life['worker_closure'],life['worker_config'],'observer')
    assert nf['KillMode']=='mixed'and ns<=ws<we<=ne
    assert wj['parent']['pid']==no['pid']and wj['parent']['birth']==no['starttime_ticks']and wj['parent']['argv']==nc['argv']
    assert wj['parent']['job']==jp and wj['parent']['source']==job['runtime']
    assert oc['argv']==[family['main_observer_interpreter']['path'],'-Xgil=0','-I','-B',family['main_observer']['worker']['path'],'--execute','--job',life['worker_job']['path'],'--job-sha256',life['worker_job']['sha256'],'--source-sha256',family['main_observer']['worker']['sha256']]
    assert wj['deadline_monotonic_s']==result['native_deadline_monotonic_s']==result['native_started_monotonic_s']+720
    assert wo['ended_monotonic_s']<wj['deadline_monotonic_s'];child=read(life['controller_child']);assert birth(child['pid'])!=child['birth']
    read_indices=[];gaps=[];previous=None;kernel_epochs=[];sample_paths={p['path']for p in failure['samples']}
    collector=load(failure['health_job']['sources']['collector'],'_failed1369_collector')
    primitives=load(failure['health_job']['sources']['primitives'],'_failed1369_primitives')
    def raw_read(pin,as_json=True):
        nonlocal previous
        value=read(pin,as_json)
        if pin['path']in sample_paths:
            t=value['transport'];read_indices.append(t['index'])
            if previous is not None:gaps.append(t['observed_unix_s']-previous)
            previous=t['observed_unix_s']
            unpacked=collector.unpacked(value);snapshot=json.loads(unpacked['raw_tcp'])
            assert snapshot['schema']=='robotron-original-inet-diag-port9998-snapshot-v3'and snapshot['error']is None
            assert snapshot['begin_unix_s']==unpacked['tcp_begin_unix_s']and snapshot['end_unix_s']==unpacked['tcp_end_unix_s']
            table=primitives.tcp(unpacked['raw_tcp']);api=primitives.decode(unpacked['raw_API'])
            assert api['client_count']==192 and len([row for row in table if row['state']=='01'])==384
            assert t['index']==len(kernel_epochs)
            kernel_epochs.append(dict(index=t['index'],tcp_begin_unix_s=snapshot['begin_unix_s'],tcp_end_unix_s=snapshot['end_unix_s'],
                API_begin_unix_s=t['API_begin_unix_s'],API_end_unix_s=t['API_end_unix_s'],observed_unix_s=t['observed_unix_s'],rows=len(table),datagrams=len(snapshot['datagrams'])))
        return value
    engine=load(failure['health_job']['sources']['full_health_engine'],'_failed1369_engine')
    try:engine.replay(failure['health_job'],failure['samples'],read(failure['initial_cursors']),raw_read,h,prior_groups=[],original_statuses=failure['actual_status']+[None])
    except ValueError as error:assert repr(error)==expected
    else:raise AssertionError('Original failed stream unexpectedly validated')
    assert read_indices==list(range(1369))and max(gaps[:-1])<=.5 and gaps[-1]>.5 and max(gaps)==gaps[-1]
    binding=read(failure['health_job']['binding'])
    assert len(binding['held_hashes'])==197 and all(h.pin(path)['sha256']==sha for path,sha in binding['held_hashes'].items())
    capture=family['inet_diag_capture_components'];contracts=read(capture['contracts']);capacity=read(capture['resource']);query=read(capture['query'])
    assert contracts['typed_negative_rejections']==187 and capacity['resource_passed']is True
    assert capacity['synthetic_samples']==48332 and capacity['actual_elapsed_s']<600
    assert query['exact_original_source_OR_destination_port9998_predicate']is True
    provenance=read(capture['capture_provenance']);selected={Path(row['prospective']['path']).name:row['prospective']for row in provenance['source_changes']}
    for key in ('io','primitives'):
        pin=failure['health_job']['sources'][key];assert selected[Path(pin['path']).name]==pin
    loaded=read(h.pin(out/'original-loaded-policy.json'));policy=result['policy_before']
    assert loaded['policy']==policy and policy['checkpoint_sha256']==job['checkpoint']['sha256']=='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
    assert policy['training_enabled']is policy['replay_enabled']is False and policy['epsilon']==policy['expert_ratio']==0
    assert loaded['gpu_uuid']==job['gpu_uuid']and loaded['compile_report']['all_shapes_verified']==list(range(1,17))and loaded['memory_is_none']is loaded['optimizer_is_none']is True
    reaped=result['original_post_origin_child_reap'];assert reaped['all_original_children_reaped']is True and reaped['unknown_slots']==[]and reaped['signals_sent']is reaped['exit_statuses_normalized']is False
    assert set(reaped['original_children'])==set(result['original_slots'])=={str(s)for s in range(4096,4128)}
    wire=load(review['original_wire_auditor'],'_failed1369_wire');wire.dependencies();games=wire.games_audit;prefixes=[]
    for slot,entry in result['original_slots'].items():
        child=reaped['original_children'][slot];assert entry['pid']==child['pid']and entry['birth']==child['birth']and entry['actual_exit']==child['actual_exit']==0
        assert birth(entry['pid'])!=entry['birth']and entry['outputs_sealed_after_original_writer_closure']is True and entry['original_unsealed_output_paths']==[]
        for pin in entry['files'].values():h.checked(pin)
        rows=games.lines(read(entry['files']['producer.jsonl'],False));subject=dict(slot=int(slot),session=job['sessions'][slot],connection=job['connections'][slot])
        assert all(all(row[k]==v for k,v in subject.items())for row in rows)
        raw_wire=games.lines(read(entry['files']['proxy.jsonl'],False));ledger=wire.audit_prefix_ledger(raw_wire,rows,subject,job['loaded_rom_sha256'],entry)
        image=b''.join(bytes.fromhex(row['data_hex'])for row in rows if row['kind']=='raw_ROM_chunk');assert len(image)==102400 and hashlib.sha256(image).hexdigest()==job['loaded_rom_sha256']
        prefixes.append(dict(slot=int(slot),original_prefix_ledger=ledger,full_ROM_verified=True))
    cohort=result['after_intentional_stop'];assert cohort['count']==cohort['pending']==0 and cohort['started']==cohort['abandoned']==32
    lock=h.pin(out/'main-observations/live.json.lock');h.checked(lock);assert lock['bytes']==0 and lock['identity']['mode']=='0o600'and lock['identity']['nlink']==1
    for pin in (lock,job['lease']):
        h.checked(pin);fd=os.open(pin['path'],os.O_RDWR|os.O_NOFOLLOW)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)
    for port in (19998,*range(20000,20032)):
        with socket.socket()as sock:sock.bind(('127.0.0.1',port))
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,check=True,timeout=10)
    assert job['gpu_uuid']not in gpu.stdout and 'torch'not in sys.modules
    output=Path(review['output']);output.mkdir(mode=0o700)
    report=h.put(output/'report.json',dict(schema='robotron-failed-transient-native1369-independent-review-v1',native_job=jp,native_result=review['native_result'],original_scope_reviews=scopes,
        original_failure_report=result['main_health_failure'],all1369_raw_samples_replayed_to_exact_first_failure=True,original_successful_statuses=1368,rejected_sample_status_absent=True,
        first_failure_index=1368,raw_replay_error=expected,maximum_gap_s=max(gaps),physical_censuses_retained=53,kernel_epochs=kernel_epochs,all_kernel_envelopes_and_original_epochs_verified=True,filtered_capture_components=capture,
        physical192_API_count=192,distinct_established_socket_identities=384,all32_actual_MAME_reaped_exit0=True,all32_original_prefixes_and_ROM=prefixes,
        all_private_resources_released=True,main_health_writer_closed=True,actual_live_lock=lock,live_protocol_lock_error_reported=True,
        counts=dict(completed=0,started=32,pending=0,abandoned=32),native600_requirement_achieved=False,all_original_errors_retained=result['errors'],failed_original_not_requalified=True,
        original_source_pins_unchanged=True,original_maximum_raw_copy_limit_unchanged=2,quality_qualified=False,full_game_score_verified=False,root_cause_not_proven=True,created_unix_s=time.time()))
    print(json.dumps(dict(report=report,max_gap_s=max(gaps),raw_samples=1369)),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
