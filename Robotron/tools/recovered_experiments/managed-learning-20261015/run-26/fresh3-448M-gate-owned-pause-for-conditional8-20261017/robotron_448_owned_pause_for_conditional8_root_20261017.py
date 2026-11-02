#!/usr/bin/env python3
"""Pause only the verified waiting448 helper, retaining its original deadline."""
import datetime,hashlib,json,os,signal,subprocess,time,urllib.request
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');G=R/'Robotron';B=G/'logs/managed-learning-20261015';RUN=B/'run-26'
D=RUN/'fresh3-448M-gate-owned-pause-for-conditional8-20261017'
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(a):return subprocess.run(a,capture_output=True,text=True,timeout=10)
def props(t):return dict(x.split('=',1) for x in t.splitlines() if '=' in x)
def main():
    p=B/'state.json';old=p.read_bytes();s=json.loads(old);g=s['next_checkpoint']
    assert g['status']=='waiting' and g['unit']=='robotron-checkpoint-448M-run26-post-live8v4-20261017.service' and g['pid']==4161497 and g['start_ticks']=='31625645' and g['invocation_id']=='a25845c5b0a449b1ad9c8a5347ba02df'
    assert g['target_learner_frames']==452629023 and g['original_deadline_unix_s']==1792245505.2003896
    proc=Path('/proc',str(g['pid']));assert proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==g['start_ticks']
    before=call(['systemctl','--user','show',g['unit']]);f=props(before.stdout)
    assert before.returncode==0 and f['MainPID']==str(g['pid']) and f['InvocationID']==g['invocation_id'] and f['Restart']=='no' and f['ActiveState']=='active'
    argv=proc.joinpath('cmdline').read_bytes().split(b'\0');assert str(G/'tools/checkpoint_at_frame.py').encode() in argv and b'fresh3-448M' in argv and b'452629023' in argv
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as stream:v=json.load(stream)
    assert v['learner_frame_count']<g['target_learner_frames'] and v['client_count']==192 and v['training_enabled'] and not v['measurement_active'] and v['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth'
    assert v['host_pipeline']['learning_exposure']['optimizer']['process_id']==4140916
    assert not (G/'models_dqn/managed_save.request.json').exists() and not Path(g['output']).exists() and not (G/'models_dqn/managed-checkpoints/fresh3-448M.pt').exists()
    D.mkdir();(D/'state-before.json').write_bytes(old)
    for name,text in [('original-running-show.txt',before.stdout),('original-unit-cat.txt',call(['systemctl','--user','cat',g['unit']]).stdout)]:
        with (D/name).open('x') as stream:stream.write(text);os.fchmod(stream.fileno(),0o444)
    save(D/'root-owned-pause-intent.json',dict(gate=g,current_learner_frames=v['learner_frame_count'],source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),signal='SIGTERM bound owned waiter only; trainer/actors untouched'))
    assert props(call(['systemctl','--user','show',g['unit']]).stdout)['InvocationID']==g['invocation_id'] and proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==g['start_ticks']
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as stream:last=json.load(stream)
    assert last['learner_frame_count']<g['target_learner_frames'] and last['managed_experiment']==v['managed_experiment']
    assert not (G/'models_dqn/managed_save.request.json').exists() and not Path(g['output']).exists() and not (G/'models_dqn/managed-checkpoints/fresh3-448M.pt').exists()
    os.kill(g['pid'],signal.SIGTERM);deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        raw=call(['systemctl','--user','show',g['unit']]).stdout;f=props(raw)
        if f['MainPID']=='0' and f['ExecMainCode'] in ('1','2','3'):break
        time.sleep(.1)
    assert f['MainPID']=='0' and f['ExecMainPID']==str(g['pid']) and f['InvocationID']==g['invocation_id'] and not proc.exists()
    for name,text in [('original-terminal-show.txt',raw),('original-invocation-journal.txt',call(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+g['invocation_id'],'--no-pager','-o','short-precise']).stdout)]:
        with (D/name).open('x') as stream:stream.write(text);os.fchmod(stream.fileno(),0o444)
    save(D/'original-owned-terminal.json',dict(pid=g['pid'],invocation_id=f['InvocationID'],exec_main_code=int(f['ExecMainCode']),exec_main_status=int(f['ExecMainStatus']),result=f['Result'],signal_sent='SIGTERM',checkpoint_triggered=False))
    stopped=call(['systemctl','--user','stop',g['unit']]);assert stopped.returncode==0,stopped.stderr
    probe=call(['systemctl','--user','show',g['unit'],'-p','LoadState'])
    if 'LoadState=not-found' not in probe.stdout:
        reset=call(['systemctl','--user','reset-failed',g['unit']]);assert reset.returncode==0,reset.stderr
    assert 'LoadState=not-found' in call(['systemctl','--user','show',g['unit'],'-p','LoadState']).stdout
    assert not (G/'models_dqn/managed_save.request.json').exists() and not Path(g['output']).exists() and not (G/'models_dqn/managed-checkpoints/fresh3-448M.pt').exists()
    receipt=dict(status='OWNED448_WAITER_PAUSED_ORIGINAL_DEADLINE_RETAINED',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_gate=g,original_deadline_unix_s=g['original_deadline_unix_s'],original_terminal_archived_before_release=True,checkpoint_triggered=False,trainer_actors_untouched=True)
    q=D/'pause-completion.json';save(q,receipt)
    paused=dict(g,status='paused_for_conditional8_owned_window',pause_receipt=str(q),pause_sha256=hashlib.sha256(q.read_bytes()).hexdigest())
    s['next_checkpoint']=paused;s['next_screen']['next_checkpoint']=paused;s['optimization_goal']['next_checkpoint']=paused;s['owned_checkpoint_waiter_pause']=receipt;s['updated_utc']=receipt['utc'];s['updated_unix_s']=time.time();assert p.read_bytes()==old
    temp=p.with_name('.state.448-conditional8-pause-root.tmp')
    with temp.open('x') as stream:json.dump(s,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,p)
    with (D/Path(__file__).name).open('xb') as stream:stream.write(Path(__file__).read_bytes());os.fchmod(stream.fileno(),0o444)
    print(json.dumps(receipt))
if __name__=='__main__':main()
