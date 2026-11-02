"""Read the original completed26 CPU contracts; never starts or reruns tests."""
from pathlib import Path
import hashlib,importlib.util,json,os,re,shlex,sys,time,urllib.request

C=Path(__file__).resolve().parent
P=C.parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(path,sha,name):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    output=C/'root-independent-readback.json';assert not output.exists() and not(C/'original-console-archives').exists()
    runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_save_CPU26_runtime')
    reader=runtime.protector();pin=reader.pin
    construction_pin=pin(C/'source-and-controller-preparation.json')
    assert construction_pin['sha256']=='f86fcd77fc4235b1f75e18b0adb51a8757f77b4a9c8bb2170685ca45a983a922'
    construction=reader.read_pin(construction_pin);job=reader.read_pin(construction['job'])
    config=reader.read_pin(construction['config']);assert construction['sources']==job['sources']
    for entry in job['sources'].values():assert pin(entry['path'])==entry
    owner_pin=pin(C/'controller-execution/root-original-identity.json');owner=reader.read_pin(owner_pin)
    closure_pin=pin(C/'controller-execution/root-original-result-and-owned-release.json')
    assert closure_pin['sha256']=='b0f3798f0a398524178c7cb95decba1e72bf8afd0a00354eb4a2ce57476b0d3c'
    closure=reader.read_pin(closure_pin)
    fields=runtime.archived_closure(closure,owner,lambda e,as_json=True:reader.read_pin(e,as_json=as_json),exit_zero=True)
    assert runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
    assert fields['MemorySwapMax']=='0' and fields['TasksMax']=='128' and fields['Restart']==fields['SendSIGKILL']=='no'
    assert runtime.duration_seconds(fields['RuntimeMaxUSec'])==180 and runtime.duration_seconds(fields['TimeoutStopUSec'])==5
    expected=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+config['argv']
    match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart'])
    assert match and shlex.split(match[1])==expected and not Path('/proc',str(owner['pid'])).exists()
    control=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py',
        '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_save_CPU26_control')
    for unit in [owner['unit'],owner['timer']]:assert control.show(unit)['LoadState']=='not-found'
    report_pin=pin(C/'CPU-report.json');report=reader.read_pin(report_pin)
    assert report['status']=='PASS' and report['tests']==26 and report['failures']==report['errors']==report['skipped']==0
    assert report['tested_sources']==job['sources'] and report['mocked_unit_HTTP_and_process_events'] is True
    assert report['live_window_not_launched_by_this_CPU'] is True and report['production_changed'] is False
    stderr=(C/'controller-execution/stderr.txt').read_bytes()
    assert re.search(rb'Ran 26 tests in [0-9.]+s',stderr) and stderr.rstrip().endswith(b'OK')
    linux=load(Path(job['sources']['linux']['path']),job['sources']['linux']['sha256'],'_save_CPU26_linux')
    pause=load(Path(job['sources']['pause']['path']),job['sources']['pause']['sha256'],'_save_CPU26_archive')
    archive_dir=C/'original-console-archives';archive_dir.mkdir();consoles={}
    for name in ['stdout','stderr']:
        source=C/'controller-execution'/(name+'.txt');original=pin(source)
        archived=pause.archive(linux,source,archive_dir/(name+'.txt'))
        assert pin(source)==original;consoles[name]=dict(original=original,archive=archived)
    design_pin=pin(P/'prospective-window-and-fixed-reference1597-precommit.json');assert design_pin['sha256']=='bdb43d83e65b81722ed4b5c3369752cb4570290df6c39248d6aba251b6ca5c90';design=reader.read_pin(design_pin);binding=reader.read_pin(design['current_main_binding'])
    guard=load(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
        'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3','_save_CPU26_guard')
    guard.owner_and_files(binding)
    wire=urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10).read();api=json.loads(wire)
    guard.healthy(api,reader.read_pin(binding['baseline_API']),binding['experiment'],time.time())
    api_pin=linux.publish(C/'main-API-after-original-CPU21.raw.json',wire)
    result=dict(schema='profile06-window-flow-original26-independent-readback-v1',
        status='ACTUAL_ORIGINAL_OWNED_SAVE_WRAPPER_CPU26_ALL6_AND_RELEASE_PASS',observed_unix_s=time.time(),
        source=pin(Path(__file__)),original_preparation=construction_pin,original_job=construction['job'],
        original_config=construction['config'],original_owner=owner_pin,original_closure=closure_pin,CPU_report=report_pin,
        tested_sources=job['sources'],actual_tests=26,actual_exit=0,all6_original_descriptors_verified=True,
        original_descriptor_exits=[e['exit'] for e in closure['full_original_archives']],exact_owned_service_and_timer_released=True,
        original_consoles=consoles,current_main_binding=design['current_main_binding'],current_main_API=api_pin,
        main196_holds_and_original192_verified=True,actual_capture_kernel_proof_separately_required=True,original_CPU_retried=False,
        production_changed=False,baseline_selected=False,quality_qualified=False,promotion=False)
    assert 'torch' not in sys.modules
    print(json.dumps(dict(readback=linux.publish(output,result),status=result['status'],tests=26)))


if __name__=='__main__':
    if sys.argv[1:]==['--observe']:main()
    else:print('PLAN_ONLY: original completed CPU evidence only')
