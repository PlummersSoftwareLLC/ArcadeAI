"""Bind the completed26 window-flow evidence under its correct scope label.

The original passive readback's inherited wrapper label remains unchanged.
No tests, original readback or native process is executed again.
"""
from pathlib import Path
import hashlib,importlib.util,json,sys,time

C=Path(__file__).resolve().parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(path,sha,name):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    n=G/'logs/managed-learning-20261015/run-26/profile06-production-continuity-live-controller-original01-preparation-20261021'
    l=load(n/'sources/handoff_linux_v1.py','3c0a54a589e6790865b1dcecc1a0bf6e1f662b204155c7bf767a1d8b579f7de2','_window_scope_linux')
    runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_window_scope_runtime')
    reader=runtime.protector();entry=l.full_pin(C/'root-independent-readback.json')
    assert entry['sha256']=='6da7c9a2c99813fc876d5722733899692394b691a4d739b74af3a597e0f30298'
    original=json.loads(l.checked(entry));assert original['status']=='ACTUAL_ORIGINAL_OWNED_SAVE_WRAPPER_CPU26_ALL6_AND_RELEASE_PASS'
    report=reader.read_pin(original['CPU_report']);assert report['schema']=='profile06-window-flow-original26-CPU-report-v1'
    assert report['status']=='PASS' and report['tests']==26 and report['failures']==report['errors']==report['skipped']==0
    assert report['tested_sources']==original['tested_sources'] and original['actual_tests']==26 and original['actual_exit']==0
    for key,name in [('observer','prospective_window_v1.py'),('launcher','launch_window_v1.py')]:
        source=original['tested_sources'][key]
        assert Path(source['path'])==C.parent/'window-sources-original01'/name and l.full_pin(source['path'])==source
    closure=reader.read_pin(original['original_closure']);owner=reader.read_pin(original['original_owner'])
    assert owner['unit']=='robotron-profile06-next8M-window-flow-contracts-original01-20261021.service'
    runtime.archived_closure(closure,owner,lambda e,as_json=True:reader.read_pin(e,as_json=as_json),exit_zero=True)
    result=dict(original,status='ACTUAL_ORIGINAL_WINDOW_FLOW_CPU_ALL6_AND_RELEASE_PASS',
        source=l.full_pin(Path(__file__)),original_scope_label_readback=entry,scope_label_corrected=True,
        scope_label_correction_unix_s=time.time(),original_tests_or_reader_retried=False)
    print(json.dumps(dict(readback=l.publish(C/'root-window-flow-authority-readback.json',result),status=result['status'])))


if __name__=='__main__':
    if sys.argv[1:]==['--bind-metadata']:main()
    else:print('PLAN_ONLY: no tests or native processes')
