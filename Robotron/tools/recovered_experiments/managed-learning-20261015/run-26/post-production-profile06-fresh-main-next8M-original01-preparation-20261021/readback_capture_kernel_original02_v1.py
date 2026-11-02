"""Read the completed revised-source kernel cases and all seven lifecycles."""
from pathlib import Path
import hashlib,importlib.util,json,re,shlex,sys,time,urllib.request

P=Path(__file__).resolve().parent
K=P/'capture-wrapper-kernel-original02'
E=P/'capture-wrapper-kernel-root-controller-original02'
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(path,sha,name):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    out=K/'root-independent-all42-readback.json';assert not out.exists()
    n=G/'logs/managed-learning-20261015/run-26/profile06-production-continuity-live-controller-original01-preparation-20261021'
    l=load(n/'sources/handoff_linux_v1.py','3c0a54a589e6790865b1dcecc1a0bf6e1f662b204155c7bf767a1d8b579f7de2','_capture42_linux')
    pause=load(n/'sources/handoff_poststop_v1.py','0756488a19bf653a068aec8c9d3def26605b06498718621e9dc9a8a634f37b3c','_capture42_archive')
    runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_capture42_runtime')
    c=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_capture42_control')
    reader=runtime.protector();read=lambda e,as_json=True:reader.read_pin(e,as_json=as_json)
    prep_pin=l.full_pin(P/'capture-wrapper-kernel-original02-preparation.json')
    assert prep_pin['sha256']=='b1976cd0f999e0e5979a8b789bb22c1054e527df5ff49c0574938ad4eb92168a'
    prep=read(prep_pin);job=read(prep['job']);cpu=read(prep['CPU_readback'])
    assert cpu['status']=='ACTUAL_ORIGINAL_OWNED_SAVE_WRAPPER_CPU23_ALL6_AND_RELEASE_PASS'
    assert cpu['actual_tests']==23 and cpu['actual_exit']==0 and cpu['tested_sources']['capture']==prep['sources']['capture']
    for entry in [*prep['sources'].values(),prep['job'],prep['config'],prep['CPU_readback']]:assert l.full_pin(entry['path'])==entry
    report_pin=l.full_pin(K/'root-original-kernel-report.json');report=read(report_pin)
    assert report['status']=='ACTUAL_ORIGINAL_CAPTURE_NORMAL_SAVE_AND_CONTROLLER_LOSS_KERNEL_PASS'
    assert report['all36_original_inner_descriptors_verified'] is True
    assert report['original_two_fixtures192_each_preserved'] is report['original_loss_exit23_preserved'] is True
    assert report['emergency_cleanup_used'] is report['production_changed'] is report['actual_ROM_model_or_replay_tested'] is False
    assert not(K/'root-original-failure-preserved.json').exists()
    for name,entry in report['source_pins'].items():
        assert l.full_pin(entry['path'])==entry and l.checked(entry)==l.checked(prep['sources'][name])
    entries=[('root',E,Path(prep['config']['path']),0)]
    for variant in ['success','loss']:
        for role in ['fleet','capture','rescue']:
            entries.append((variant+'-'+role,K/variant/(role+'-execution'),K/variant/(role+'-config.json'),
                23 if variant=='loss' and role=='capture' else 0))
    archive_dir=K/'independent-original-console-archives';archive_dir.mkdir();lifecycles={};consoles=[]
    for role,directory,config_path,expected_exit in entries:
        owner_pin=l.full_pin(directory/'root-original-identity.json');owner=read(owner_pin)
        closure_pin=l.full_pin(directory/'root-original-result-and-owned-release.json');closure=read(closure_pin)
        config_pin=l.full_pin(config_path);config=read(config_pin)
        fields=runtime.archived_closure(closure,owner,read,exit_zero=expected_exit==0)
        assert owner['unit']==config['unit'] and owner['unit'].startswith('robotron-profile06-owned-save-kernel-')
        assert closure['original_exec_code']==1 and closure['original_exit']==expected_exit
        assert runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
        assert fields['MemorySwapMax']=='0' and runtime.duration_seconds(fields['RuntimeMaxUSec'])==180
        assert fields['TasksMax']==('256' if role.endswith('-fleet') else '128')
        assert fields['Restart']==fields['SendSIGKILL']=='no' and runtime.duration_seconds(fields['TimeoutStopUSec'])==5
        expected=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+config['argv']
        match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart'])
        assert match and shlex.split(match[1])==expected and l.process_start(owner['pid']) is None
        for unit in [owner['unit'],owner['timer']]:assert c.show(unit)['LoadState']=='not-found'
        observed=read(l.full_pin(directory/'original-first-observed-show-command.json'))
        born=dict(line.split('=',1) for line in read(observed['stdout'],False).decode().splitlines() if '=' in line)
        assert born['MainPID']==str(owner['pid']) and born['InvocationID']==owner['invocation_id']
        assert born['ControlGroup'].endswith('/'+owner['unit']) and not Path('/sys/fs/cgroup'+born['ControlGroup']).exists()
        for name in ['stdout','stderr']:
            source=directory/(name+'.txt');original=l.full_pin(source)
            archive=pause.archive(l,source,archive_dir/(role+'-'+name+'.txt'))
            assert l.full_pin(source)==original;consoles.append(dict(original=original,archive=archive))
        lifecycles[role]=dict(owner=owner_pin,closure=closure_pin,config=config_pin,actual_original_exit=expected_exit,
            actual_descriptor_exits=[a['exit'] for a in closure['full_original_archives']])
    cases={}
    for variant in ['success','loss']:
        case_pin=report['original_cases'][variant];case=read(case_pin)
        assert case['status']=='ORIGINAL_PRIVATE_CAPTURE_KERNEL_CASE_PASS' and case['variant']==variant
        assert case['all18_original_descriptors_and_exact_releases_verified'] is True
        assert case['original192_children_and_affinities_preserved'] is case['private_heartbeat_resumed'] is True
        assert case['production_changed'] is False
        fixture=read(case['fixture']);complete=read(case['original_fixture_completion']);capture_job=read(case['original_capture_job'])
        assert complete['original192_preserved'] is True and fixture['owner']==complete['owner']==capture_job['owner']
        assert fixture['actors']==complete['actors'] and len(fixture['actors'])==192
        assert len({a['pid'] for a in fixture['actors']})==192 and all(l.process_start(a['pid']) is None for a in fixture['actors'])
        for role in ['fleet','capture','rescue']:
            original=case['original_closures'][role];actual=lifecycles[variant+'-'+role]
            assert original['owner']==actual['owner'] and original['closure']==actual['closure']
            assert original['actual_original_exit']==actual['actual_original_exit']==original['actual_lifecycle_CLI_exit']
        watch=read(case['original_watch_result'])
        assert watch['status']=='ORIGINAL_CONTROLLER_EXIT_OBSERVED' and watch['controller_alive'] is False and watch['restart_retry'] is False
        if variant=='success':
            saved=read(case['original_capture_result']);assert saved['normal_producer_mode_preserved'] is True
            assert saved['source']['identity']['mode']=='0o664' and saved['checkpoint']['identity']['mode']=='0o444'
            assert l.full_pin(saved['source']['path'])==saved['source'] and l.full_pin(saved['checkpoint']['path'])==saved['checkpoint']
            assert saved['source']['sha256']==saved['checkpoint']['sha256']
            publication=read(saved['publication']);request=publication['request'];original_request=read(publication['request_archive'],False)
            assert request['identity']['nlink']==1 and hashlib.sha256(original_request).hexdigest()==request['sha256']
            assert json.loads(original_request)==dict(tag=capture_job['tag'])
            state=read(publication['original_state_before_hold']);assert state['paused_owner']==fixture['owner']
            assert watch['recovery']['status']=='NO_RECORDED_SAVE_HOLD'
        else:
            injected=read(case['original_loss_injection']);captured_owner=read(lifecycles['loss-capture']['owner'])
            assert injected['actual_controller_pid']==captured_owner['pid'] and injected['actual_controller_starttime_ticks']==captured_owner['starttime_ticks']
            assert injected['kernel_frozen'] is injected['private_heartbeat_stopped'] is injected['inside_selected_capture_publication'] is True
            assert injected['expected_original_exit']==23 and watch['recovery']['status']=='EXACT_RECORDED_SAVE_OWNER_THAWED'
            assert watch['recovery']['thaw']['owner']==fixture['owner']
            assert not(K/variant/'capture-output/result.json').exists()
        cases[variant]=case_pin
    design=read(job['design']);binding=read(design['current_main_binding'])
    guard=load(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
        'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3','_capture42_main_guard')
    guard.owner_and_files(binding);wire=urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10).read();api=json.loads(wire)
    guard.healthy(api,read(binding['baseline_API']),binding['experiment'],time.time())
    assert api['host_pipeline']['learning_exposure']['replay']['process_id']==binding['owner']['pid']
    invalid=l.full_pin(P/'capture-wrapper-kernel-original01/root-original-failure-independent-disposition.json')
    assert invalid['sha256']=='2f77754789e4c0e6bcb28f6c5ecaa0516e664b36ff82edf3be453fef93abbe05'
    result=dict(schema='profile06-revised-owned-capture-kernel02-original-all42-readback-v1',
        status='ACTUAL_REVISED_CAPTURE_CPU23_KERNEL_TWO_CASES_ALL42_AND_RELEASE_PASS',observed_unix_s=time.time(),
        source=l.full_pin(Path(__file__)),original_preparation=prep_pin,original_CPU23=prep['CPU_readback'],
        original_kernel_report=report_pin,original_cases=cases,original_lifecycles=lifecycles,
        all42_original_descriptors_and_exact_releases_verified=True,original_console_archives=consoles,
        selected_capture_source=prep['sources']['capture'],tested_kernel_capture_source=report['source_pins']['capture'],
        normal_producer_mode_preserved=True,original_loss_exit23_preserved=True,emergency_cleanup_used=False,
        production_changed=False,actual_ROM_model_or_replay_tested=False,prior_invalid_original01=invalid,
        prior_result_retried_or_rescued=False,main196_holds_and_original192_verified=True,
        main_API=l.publish(K/'main-API-after-original-kernel02.raw.json',wire),
        prospective_baseline_selected=False,actual_candidate_captured=False,quality_qualified=False,promotion=False)
    assert 'torch' not in sys.modules
    print(json.dumps(dict(readback=l.publish(out,result),status=result['status'])))


if __name__=='__main__':
    if sys.argv[1:]==['--observe']:main()
    else:print('PLAN_ONLY: no original tests or runtime actions')
