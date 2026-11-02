"""Archive/release only the captured already-terminal private loss fixture."""
from pathlib import Path
import hashlib,importlib.util,json,sys

P=Path(__file__).resolve().parent
D=P/'capture-wrapper-kernel-original01/loss/fleet-execution'


def load(path,sha,name):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
    l=load(G/'logs/managed-learning-20261015/run-26/profile06-production-continuity-live-controller-original01-preparation-20261021/sources/handoff_linux_v1.py',
        '3c0a54a589e6790865b1dcecc1a0bf6e1f662b204155c7bf767a1d8b579f7de2','_failed_fixture_linux')
    c=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py',
        '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_failed_fixture_control')
    runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_failed_fixture_runtime')
    reader=runtime.protector();owner=json.loads(l.checked(l.full_pin(D/'root-original-identity.json')))
    assert owner['unit']=='robotron-profile06-owned-save-kernel-original01-20261021-loss-fleet.service'
    assert owner['pid']==3345293 and owner['starttime_ticks']==65133155
    launch_pin=l.full_pin(D/'root-original-timer-launch-archive.json');launch=json.loads(l.checked(launch_pin))
    assert all(launch[k]==owner[k] for k in ['unit','timer','timer_invocation_id'])
    for key in ['timer_show','timer_cat']:
        assert launch[key]['exit']==0 and launch[key]['timed_out'] is False
        reader.read_pin(launch[key]['stdout'],as_json=False);reader.read_pin(launch[key]['stderr'],as_json=False)
    assert l.process_start(owner['pid']) is None
    fields=c.show(owner['unit']);c.original_terminal(fields,owner)
    assert fields['ExecMainStatus']=='0' and fields['ExecMainCode']=='1' and fields['Result']=='success'
    completion_pin=l.full_pin(D.parent/'work/fixture-completed.json');completion=json.loads(l.checked(completion_pin))
    assert completion['owner']['pid']==owner['pid'] and completion['original192_preserved'] is True
    assert all(l.process_start(actor['pid']) is None for actor in completion['actors'])
    out=D/'root-terminal-closure-after-parent-failure-original01';out.mkdir(mode=0o700)
    archives=[]
    for kind in ['service','timer']:
        unit=owner['unit' if kind=='service' else 'timer']
        invocation=owner['invocation_id' if kind=='service' else 'timer_invocation_id']
        for action in ['show','cat','journal']:
            argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+invocation] if action=='journal' else ['systemctl','--user',action,unit]
            archives.append(c.command(out,'original-'+kind+'-'+action,argv))
    result=dict(original=owner,original_exec_code=1,original_exit=0,original_result='success',
        timer_launch_archive=launch_pin,full_original_archives=archives,original_archived_before_release=True,
        payload_retried=False,owned_release=[],unit_released=False,lifecycle_complete=False,
        original_fixture_completion=completion_pin,original_parent_failure=l.full_pin(P/'capture-wrapper-kernel-original01/root-original-failure-preserved.json'))
    l.publish(out/'original-terminal-before-owned-release.json',result)
    c.original_terminal(c.show(owner['unit']),owner)
    context={k:owner[k] for k in ['unit','timer','timer_invocation_id']}
    for kind in ['timer','service']:
        release={};result['owned_release'].append(release);c.release_original(out,kind,owner,context,release)
    assert all(row['confirmed_absent'] for row in result['owned_release'])
    result.update(unit_released=True,lifecycle_complete=True,status='ORIGINAL_TERMINAL_FIXTURE_ARCHIVED_AND_OWNED_RELEASED')
    runtime.archived_closure(result,owner,lambda e,as_json=True:reader.read_pin(e,as_json=as_json),exit_zero=True)
    print(json.dumps(l.publish(out/'root-original-result-and-owned-release.json',result)))


if __name__=='__main__':
    if sys.argv[1:]==['--close-terminal']:main()
    else:print('PLAN_ONLY: no running process may be stopped or adopted')
