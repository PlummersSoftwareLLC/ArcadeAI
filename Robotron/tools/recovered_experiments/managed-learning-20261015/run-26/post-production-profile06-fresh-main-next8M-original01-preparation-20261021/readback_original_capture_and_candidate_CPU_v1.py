"""One independent readback of original capture and strict numerical CPU evidence.

No capture, verifier, original reader or scientific review is executed again.
Normal model/report modes remain unchanged; new archives and binding are sealed.
"""
from pathlib import Path
import ast,copy,hashlib,importlib.util,json,re,shlex,sys,time,urllib.request

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/post-production-profile06-fresh-main-next8M-original01-preparation-20261021'
C=P/'candidate-CPU-original01'
O=P/'captured-main-registration-original01'


def load(path,sha,name):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    assert not O.exists() and not(C/'candidate-CPU-report-readonly.json').exists()
    n=P.parent/'profile06-production-continuity-live-controller-original01-preparation-20261021'
    l=load(n/'sources/handoff_linux_v1.py','3c0a54a589e6790865b1dcecc1a0bf6e1f662b204155c7bf767a1d8b579f7de2','_captured_CPU_linux')
    runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_captured_CPU_runtime')
    control=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_captured_CPU_control')
    pause=load(n/'sources/handoff_poststop_v1.py','0756488a19bf653a068aec8c9d3def26605b06498718621e9dc9a8a634f37b3c','_captured_CPU_archives')
    reader=runtime.protector();read=lambda e,as_json=True:reader.read_pin(e,as_json=as_json)
    prep_pin=l.full_pin(C/'preparation.json');prep=read(prep_pin)
    assert prep['status']=='PREPARED_NOT_EXECUTED' and prep['normal_producer_mode_preserved'] is True
    jp=prep['CPU_job'];job=read(jp);config=read(prep['CPU_controller_config'])
    original_producer=prep['original_normal_producer'];candidate=prep['candidate'];copied=prep['verification_copy']
    for entry in [original_producer,candidate,copied]:assert l.full_pin(entry['path'])==entry
    assert original_producer['identity']['mode']=='0o664' and candidate['identity']['mode']==copied['identity']['mode']=='0o444'
    assert original_producer['sha256']==candidate['sha256']==copied['sha256']=='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
    assert len({(e['identity']['device'],e['identity']['inode']) for e in [original_producer,candidate,copied]})==3
    assert job['source']==original_producer and job['verification_copy']==copied
    producer=C/'verification/cpu-verification.json';report_before=l.full_pin(producer);raw=producer.read_bytes()
    assert l.full_pin(producer)==report_before;report=json.loads(raw)
    assert report['status']=='PASS' and report['schema']=='robotron-phase-snapshot-checkpoint-CPU-result-v1'
    assert report['root_job']==job and report['job_file']['path']==jp['path'] and report['job_file']['sha256']==jp['sha256']
    assert report['script']['sha256']=='14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'
    assert report['sha256']==candidate['sha256'] and report['bytes']==candidate['bytes']
    assert report['phase_metadata_verified'] is True and report['cuda_initialized'] is False and report['visible_cuda_devices']==0
    assert report['actual_restore_or_optimizer_step'] is report['actual_quality_qualification'] is False
    assert report['finite']['tensors']==443 and report['adam_state_count']==81 and report['adam_group_count']==1
    assert report['adam_step_min']==report['adam_step_max']==7124863.0
    assert set(report['models'])=={'online_state_dict','target_state_dict'}
    for value in report['models'].values():
        assert value['strict_cpu_load'] is True and value['tensor_count']==100 and value['parameter_count']==17837490
    for label,entry in [('source_checkpoint',original_producer),('root_readonly_verification_copy',copied)]:
        observed=report['bound_files'][label]
        assert all(observed[k]==entry[k] for k in ['path','sha256','bytes'])
        assert all(observed[k]==v for k,v in entry['identity'].items())
    assert report['actual_boot_checkpoint']['sha256']==prep['actual_boot_checkpoint_sha256']=='8cc9e90014cf8aa3a2bffd0d7fc4943cfe0301cd44d7b6f9a40e83d0ae28f764'
    assert report['saved_priority_metric_phase']['last_resume_record_sha256']==prep['phase_record_sha256']=='01be1b691a4ca524a7c8db8813cc517438d9f221a8bae261d93ed606af35b91b'
    assert all(type(job['clock_floor'][k]) is int and report['clocks'][k]>=job['clock_floor'][k] for k in ['training_steps','optimized_samples','learner_frame_count','frame_count'])
    assert report['clocks']['learner_frame_count']==1741229950 and report['clocks']['training_steps']==7128160
    report_pin=l.publish(C/'candidate-CPU-report-readonly.json',raw)
    assert report_pin['sha256']==report_before['sha256'] and l.full_pin(producer)==report_before
    root=read(prep['root_job']);provenance=read(prep['current_window_provenance'])
    assert provenance['status']=='PASS_CURRENT_ORIGINAL_WINDOW_PROVENANCE_ONLY' and provenance['views_are_original_producer_bytes'] is False
    assert provenance['normal_producer']==original_producer and provenance['evaluation_candidate']==candidate
    result=read(provenance['original_window_result']);latch=read(provenance['original_window_latch'])
    assert result['status']=='CAPTURED_FIRST_BOTH_HORIZONS' and result['checkpoint']==candidate
    assert result['progress']==latch['progress'] and result['progress']['both_horizons'] is True
    assert result['progress']['learner_frames']==8000717 and result['progress']['learner_accepted']==8002131
    lifecycle_inputs=[('window',root['window_owner'],root['window_closure'],None,5700)]
    for role,item in result['original_capture_lifecycles'].items():lifecycle_inputs.append((role,item['owner'],item['closure'],item['config'],180))
    CPUowner=l.full_pin(C/'controller-execution/root-original-identity.json');CPUclosure=l.full_pin(C/'controller-execution/root-original-result-and-owned-release.json')
    assert CPUclosure['sha256']=='7cf5bce7d9692a5cf8860df2821908a7d0af83a7e1e8a90166c70f50ac26f1ae'
    lifecycle_inputs.append(('numerical_CPU',CPUowner,CPUclosure,prep['CPU_controller_config'],180))
    lifecycles={}
    for role,op,cp,config_pin,seconds in lifecycle_inputs:
        owner=read(op);closure=read(cp);fields=runtime.archived_closure(closure,owner,read,exit_zero=True)
        assert runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
        assert fields['MemorySwapMax']=='0' and fields['TasksMax']=='128' and fields['Restart']==fields['SendSIGKILL']=='no'
        assert runtime.duration_seconds(fields['RuntimeMaxUSec'])==seconds and runtime.duration_seconds(fields['TimeoutStopUSec'])==5
        assert l.process_start(owner['pid']) is None
        for unit in [owner['unit'],owner['timer']]:assert control.show(unit)['LoadState']=='not-found'
        if config_pin is not None:
            selected=read(config_pin);expected=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
                'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(selected['output'])/'tmp')]+selected['argv']
            match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart'])
            assert match and shlex.split(match[1])==expected
        if role=='numerical_CPU':
            assert selected['argv']==[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',
                str(G/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'),'--execute','--job',jp['path'],
                '--expected-job-sha256',jp['sha256'],'--expected-verifier-sha256','14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5']
        lifecycles[role]=dict(owner=op,closure=cp,config=config_pin,actual_original_exit=0,
            actual_descriptor_exits=[row['exit'] for row in closure['full_original_archives']])
    publication=read(provenance['original_publication']);after=result['completed_slot_transition']['after']
    request=publication['request'];slot=after['actual_pin']
    assert l.full_pin(slot['path'])==slot and slot['identity']['mode']==request['identity']['mode']=='0o444'
    assert all(slot['identity'][k]==request['identity'][k] for k in set(slot['identity'])-{'ctime_ns'})
    assert slot['identity']['ctime_ns']>=request['identity']['ctime_ns']
    assert json.loads(read(publication['request_archive'],False))==json.loads(read(after['archive'],False))==dict(tag='profile06_LR25_next8M_01_20261021')
    binding=copy.deepcopy(provenance['main_after']);old_policy=binding.pop('supervision_policy',None)
    if old_policy is not None:binding['historical_supervision_policy_not_selected']=old_policy
    binding['schema']='robotron-current-main-after-prospective-capture-v1'
    guard=load(P.parent/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
        'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3','_captured_CPU_main_guard')
    guard.owner_and_files(binding);l.live_owner(binding['owner'])
    wire=urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10).read();api=json.loads(wire)
    guard.healthy(api,read(binding['baseline_API']),binding['experiment'],time.time())
    O.mkdir(mode=0o700);binding['baseline_API']=l.publish(O/'baseline-API.raw.json',wire)
    bp=l.publish(O/'current-main-binding.json',binding)
    old_monitor=n/'completed-registration/root-current-main-readonly-monitor.py';text=old_monitor.read_text()
    tree=ast.parse(text);assignment=next(node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PINS' for t in node.targets))
    pins=ast.literal_eval(assignment.value);pins['binding']=bp
    original_line=ast.get_source_segment(text,assignment);text=text.replace(original_line,'PINS = '+repr(pins),1)
    text=text.replace('NEWEST_STATE_SCORE_CARRY_MAIN_LIVE_ORIGINAL192','CURRENT_MAIN_AFTER_PROSPECTIVE_CAPTURE_ORIGINAL192')
    compile(text,'current-main-readonly-monitor.py','exec');monitor=l.publish(O/'current-main-readonly-monitor.py',text.encode())
    payloads={}
    for name in ['stdout','stderr']:
        source=C/'controller-execution'/(name+'.txt');before=l.full_pin(source)
        archived=pause.archive(l,source,O/('original-numerical-CPU-'+name+'.txt'))
        assert l.full_pin(source)==before;payloads[name]=dict(original=before,archive=archived)
    final=dict(schema='profile06-original-window-capture-and-numerical-CPU-independent-readback-v1',
        status='ACTUAL_ORIGINAL_CAPTURE_AND_STRICT_CPU_ALL24_AND_CURRENT_MAIN_PASS',observed_unix_s=time.time(),
        source=l.full_pin(Path(__file__)),candidate=candidate,normal_producer=original_producer,CPU_copy=copied,
        CPU_job=jp,CPU_config=prep['CPU_controller_config'],CPU_report=report_pin,
        original_CPU_producer_report=report_before,original_CPU_payload_archives=payloads,
        original_current_capture_provenance=prep['current_window_provenance'],original_lifecycles=lifecycles,
        all24_original_descriptors_and_exact_releases_verified=True,all_original_payload_exits_zero=True,
        current_main_binding=bp,current_main_monitor=monitor,current_main_monitor_command=['/usr/bin/python3.12','-I','-B',monitor['path']],
        historical_supervision_policy_archived_not_selected=old_policy,normal_producer_mode_preserved=True,
        actual_request_to_completed_slot_rename_identity_verified=True,clocks=report['clocks'],window_progress=result['progress'],
        main196_holds_and_original192_verified=True,actual_model_or_training_restore=False,
        original_capture_or_CPU_repeated=False,quality_qualified=False,promotion=False,learning_speed_gain_verified=False)
    assert 'torch' not in sys.modules
    print(json.dumps(dict(readback=l.publish(O/'root-independent-readback.json',final),status=final['status'],candidate_LF=report['clocks']['learner_frame_count'])))


if __name__=='__main__':
    if sys.argv[1:]==['--observe']:main()
    else:print('PLAN_ONLY: no original tests, captures or runtime actions')
