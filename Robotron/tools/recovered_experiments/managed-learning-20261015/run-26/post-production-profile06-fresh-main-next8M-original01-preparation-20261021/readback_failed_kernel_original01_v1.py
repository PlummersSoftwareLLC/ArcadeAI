"""Close the original failed private kernel evidence without repeating any test."""
from pathlib import Path
import hashlib,importlib.util,json,sys,time,urllib.request

P=Path(__file__).resolve().parent
K=P/'capture-wrapper-kernel-original01'
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(path,sha,name):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    out=K/'root-original-failure-independent-disposition.json';assert not out.exists()
    n=G/'logs/managed-learning-20261015/run-26/profile06-production-continuity-live-controller-original01-preparation-20261021'
    l=load(n/'sources/handoff_linux_v1.py','3c0a54a589e6790865b1dcecc1a0bf6e1f662b204155c7bf767a1d8b579f7de2','_invalid_kernel_linux')
    pause=load(n/'sources/handoff_poststop_v1.py','0756488a19bf653a068aec8c9d3def26605b06498718621e9dc9a8a634f37b3c','_invalid_kernel_archives')
    c=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_invalid_kernel_control')
    runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_invalid_kernel_runtime')
    reader=runtime.protector();read=lambda e,as_json=True:reader.read_pin(e,as_json=as_json)
    failure_pin=l.full_pin(K/'root-original-failure-preserved.json');failure=read(failure_pin)
    assert failure['emergency_cleanup_used'] is True and failure['error']=="RuntimeError('Original lifecycle CLI exit differs')"
    assert not(K/'root-original-kernel-report.json').exists()
    root=P/'capture-wrapper-kernel-root-controller-original01'
    entries=[('root',root,root/'root-original-result-and-owned-release.json',1)]
    for variant in ['success','loss']:
        for role in ['fleet','capture','rescue']:
            d=K/variant/(role+'-execution');closure=d/'root-original-result-and-owned-release.json'
            if variant=='loss' and role=='fleet':
                closure=d/'root-terminal-closure-after-parent-failure-original01/root-original-result-and-owned-release.json'
            expected=23 if variant=='loss' and role=='capture' else 1 if variant=='loss' and role=='rescue' else 0
            entries.append((variant+'-'+role,d,closure,expected))
    archives=K/'original-failure-console-archives';archives.mkdir();lifecycles={};consoles=[]
    for role,directory,closure_path,expected in entries:
        owner_pin=l.full_pin(directory/'root-original-identity.json');owner=read(owner_pin)
        closure_pin=l.full_pin(closure_path);closure=read(closure_pin)
        fields=runtime.archived_closure(closure,owner,read,exit_zero=False)
        assert closure['original_exec_code']==1 and closure['original_exit']==expected
        assert runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
        assert fields['MemorySwapMax']=='0' and runtime.duration_seconds(fields['RuntimeMaxUSec'])==180
        assert fields['TasksMax']==('256' if role.endswith('-fleet') else '128')
        assert fields['Restart']==fields['SendSIGKILL']=='no' and runtime.duration_seconds(fields['TimeoutStopUSec'])==5
        assert l.process_start(owner['pid']) is None
        for unit in [owner['unit'],owner['timer']]:assert c.show(unit)['LoadState']=='not-found'
        first=read(l.full_pin(directory/'original-first-observed-show-command.json'))
        original_fields=dict(line.split('=',1) for line in read(first['stdout'],False).decode().splitlines() if '=' in line)
        assert original_fields['MainPID']==str(owner['pid']) and original_fields['InvocationID']==owner['invocation_id']
        assert not Path('/sys/fs/cgroup'+original_fields['ControlGroup']).exists()
        for name in ['stdout','stderr']:
            source=directory/(name+'.txt');before=l.full_pin(source)
            archive=pause.archive(l,source,archives/(role+'-'+name+'.txt'))
            assert l.full_pin(source)==before;consoles.append(dict(original=before,archive=archive))
        lifecycles[role]=dict(owner=owner_pin,closure=closure_pin,actual_exit=expected,
            original_descriptor_exits=[e['exit'] for e in closure['full_original_archives']])
    fixtures={}
    for variant in ['success','loss']:
        fixture_pin=l.full_pin(K/variant/'work/fixture-completed.json');fixture=read(fixture_pin)
        assert fixture['original192_preserved'] is True and len(fixture['actors'])==192
        assert all(l.process_start(a['pid']) is None for a in fixture['actors'])
        fixtures[variant]=fixture_pin
    watch_pin=l.full_pin(K/'loss/rescue-output/result.json');watch=read(watch_pin)
    assert watch['status']=='ORIGINAL_WATCH_FAILURE_PRESERVED' and watch['error']=="RuntimeError('Exact live owner changed')"
    assert watch['recovery']['status']=='EXACT_RECORDED_SAVE_OWNER_THAWED'
    design=read(l.full_pin(P/'prospective-window-and-fixed-reference1597-precommit.json'));binding=read(design['current_main_binding'])
    guard=load(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
        'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3','_invalid_kernel_main_guard')
    guard.owner_and_files(binding);wire=urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10).read()
    guard.healthy(json.loads(wire),read(binding['baseline_API']),binding['experiment'],time.time())
    result=dict(schema='profile06-original-private-kernel01-closed-invalid-disposition-v1',
        status='CLOSED_INVALID_ORIGINAL_PRIVATE_KERNEL_FAILURE_PRESERVED',observed_unix_s=time.time(),
        source=l.full_pin(Path(__file__)),original_failure=failure_pin,original_watch_failure=watch_pin,
        original_lifecycles=lifecycles,all42_original_descriptors_and_exact_owned_releases_verified=True,
        original_fixtures=fixtures,original_console_archives=consoles,emergency_cleanup_used=True,
        original_native_exits_preserved=True,partial_success_not_used_to_rescue_failure=True,
        original_test_retried=False,new_baseline_or_candidate_authorized=False,production_changed=False,
        main196_holds_and_original192_verified=True,main_API=l.publish(K/'main-API-after-invalid-original01.raw.json',wire),
        corrected_new_source_bundle=l.full_pin(P/'capture-wrapper-race-correction-source-bundle-v2.json'),
        new_original_CPU_and_kernel_validation_required=True,quality_qualified=False,promotion=False)
    print(json.dumps(dict(disposition=l.publish(out,result),status=result['status'])))


if __name__=='__main__':
    if sys.argv[1:]==['--observe']:main()
    else:print('PLAN_ONLY: no tests, launches, recovery or runtime changes')
