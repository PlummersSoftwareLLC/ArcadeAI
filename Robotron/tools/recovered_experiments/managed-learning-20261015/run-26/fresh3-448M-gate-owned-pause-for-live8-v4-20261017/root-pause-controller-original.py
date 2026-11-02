#!/usr/bin/env python3
"""Stop only the bound waiting model-only gate; preserve its original deadline."""
import json,hashlib,os,signal,subprocess,time,datetime,urllib.request
from pathlib import Path
ROOT=Path('/home/dave/source/repos/ArcadeAI');BASE=ROOT/'Robotron/logs/managed-learning-20261015';RUN=BASE/'run-26'
def call(*argv):return subprocess.run(list(argv),capture_output=True,text=True,timeout=10,check=True)
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def props(text):return dict(line.split('=',1) for line in text.splitlines() if '=' in line)
def main():
    state_path=BASE/'state.json';raw=state_path.read_bytes();state=json.loads(raw);g=state['next_checkpoint'];assert g['unit']=='robotron-checkpoint-448M-run26-20261017.service' and g['pid']==4108221 and g['status']=='waiting'
    unit=g['unit'];before=call('systemctl','--user','show',unit).stdout;p=props(before);assert p['MainPID']==str(g['pid']) and p['InvocationID']==g['invocation_id'] and p['ActiveState']=='active' and p['Restart']=='no'
    proc=Path('/proc',str(g['pid']));assert proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==g['start_ticks']
    argv=proc.joinpath('cmdline').read_bytes().split(b'\0');assert str(ROOT/'Robotron/tools/checkpoint_at_frame.py').encode() in argv and b'fresh3-448M' in argv and b'452629023' in argv
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as f:api=json.load(f)
    assert api['learner_frame_count']<g['target_learner_frames'] and api['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth' and api['client_count']==192
    assert not (ROOT/'Robotron/models_dqn/managed_save.request.json').exists();assert not Path(g['output']).exists();assert not (ROOT/'Robotron/models_dqn/managed-checkpoints/fresh3-448M.pt').exists()
    d=RUN/'fresh3-448M-gate-owned-pause-for-live8-v4-20261017';d.mkdir();(d/'state-before.json').write_bytes(raw);(d/'original-running-show.txt').write_text(before);(d/'original-unit-cat.txt').write_text(call('systemctl','--user','cat',unit).stdout)
    save(d/'owned-pause-precommit.json',dict(gate=g,actual_learner_frames=api['learner_frame_count'],signal='SIGTERM only bound original PID; no pending save and target not reached',root_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    # Directly terminating this non-restarting owned waiter retains its failed
    # terminal unit until the original invocation/exit has been archived.
    assert props(call('systemctl','--user','show',unit).stdout)['InvocationID']==g['invocation_id'];assert proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==g['start_ticks'];os.kill(g['pid'],signal.SIGTERM)
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        terminal=call('systemctl','--user','show',unit).stdout;t=props(terminal)
        if t['MainPID']=='0' and t['ExecMainCode'] in ('1','2','3'):break
        time.sleep(.1)
    assert t['MainPID']=='0' and t['InvocationID']==g['invocation_id'] and t['ExecMainPID']==str(g['pid']) and not proc.exists()
    (d/'original-terminal-show.txt').write_text(terminal);(d/'original-invocation-journal.txt').write_text(call('journalctl','--user','_SYSTEMD_INVOCATION_ID='+g['invocation_id'],'--no-pager').stdout)
    save(d/'original-owned-pause-terminal.json',dict(invocation_id=t['InvocationID'],pid=g['pid'],exec_main_code=int(t['ExecMainCode']),exec_main_status=int(t['ExecMainStatus']),result=t['Result'],owned_signal='SIGTERM',checkpoint_triggered=False))
    call('systemctl','--user','stop',unit);call('systemctl','--user','reset-failed',unit)
    post=subprocess.run(['systemctl','--user','show',unit,'-p','LoadState','-p','MainPID'],capture_output=True,text=True,timeout=5).stdout;assert 'LoadState=not-found' in post
    saved=dict(status='OWNED_WAITER_PAUSED_ORIGINAL_DEADLINE_RETAINED',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_gate=g,original_deadline_unix_s=g['original_deadline_unix_s'],original_terminal_archived=True,owned_unit_released=True,target_and_tag_unchanged=True,checkpoint_triggered=False,report=str(d/'pause-completion.json'))
    save(d/'pause-completion.json',saved)
    paused=dict(g,status='paused_for_live8_owned_window_v4',pause_receipt=str(d/'pause-completion.json'),pause_sha256=hashlib.sha256((d/'pause-completion.json').read_bytes()).hexdigest())
    state['next_checkpoint']=paused;state['optimization_goal']['next_checkpoint']=paused;state['next_screen']['next_checkpoint']=paused;state['owned_checkpoint_waiter_pause']=saved
    temporary=state_path.with_name('.state.448-owned-pause-v4-root.tmp');temporary.write_text(json.dumps(state,indent=2)+'\n');os.replace(temporary,state_path);print(json.dumps(saved))
if __name__=='__main__':main()
