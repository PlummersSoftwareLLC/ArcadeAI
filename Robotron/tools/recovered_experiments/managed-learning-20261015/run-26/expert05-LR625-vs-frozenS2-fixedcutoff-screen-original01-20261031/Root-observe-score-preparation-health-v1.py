"""Root-only genuine Main/preparation observation while Root owns CONTROL."""
import hashlib,json,os,tempfile,time,urllib.request
from pathlib import Path
D=Path(__file__).resolve().parent
B=D.parent
R=B.parents[2]
assert R.name=='Robotron'
assert not (D/'Root-one-original-launch-intent-and-CONTROL-handoff.json').exists(),'CONTROL handoff has begun; stop this observer'
def get(route):
 with urllib.request.urlopen('http://127.0.0.1:8771/api/'+route,timeout=8) as f:return json.load(f)
a=get('now');p=get('continuous_training_policy');now=time.time()
birth=int(Path('/proc/208501/stat').read_text().rsplit(')',1)[1].split()[19])
assert birth==27823352 and a['training_enabled'] is p['training_enabled'] is p['replay_admission_open'] is True
assert a['measurement_active'] is p['measurement_active'] is False and p['consumer_error'] is None
assert a['lr']==6.25e-6 and a['epsilon']==.1 and a['expert_ratio']==.05 and a['game_settings']['expert_pct']==5
assert 0<=now-a['ts']<10 and a['pipeline_read_error']==a['bank_persistence_read_error']==''
assert hashlib.sha256((R/'models_dqn/learning_control.json').read_bytes()).hexdigest()=='b38b801fbdbfd872b8f859e7ec99e7341d3b59e0d0b333074a75145625db55c4'
status={'observed_unix_s':now,'Main_same_original':True,'Main_FPS':a['fps'],'Main_clients':a['client_count'],'manual_expert_pct':5,'effective_expert':a['expert_ratio'],'actual_LR':a['lr'],'actual_epsilon':a['epsilon'],'prepared_metadata_present':(D/'prepared-matched-fixed-cutoff-two-arm-DATA-NOT-LAUNCHED-v1.json').exists(),'R1_job_present':(D/'R1/job.json').exists(),'C1_job_present':(D/'C1/job.json').exists(),'scoring_original_not_launched':True}
control=B/'dashboard-current-work-status-original01-20261030/work-control.json';old=control.read_bytes();d=json.loads(old);w=d['next_work']
assert w['state'] in {'expert05_frozen_score_test_preparation','expert05_metadata_preflight_passed','expert05_private_resource_preflight'},'Preparation phase has advanced; stop this observer'
w.update(updated_unix_s=now,observation_unix_s=now,main_observed_fps=a['fps'],main_observation_unix_s=now,preparation_live_observation=status);d['observation_unix_s']=now
raw=(json.dumps(d,indent=2,allow_nan=False)+'\n').encode();assert control.read_bytes()==old
fd,tmp=tempfile.mkstemp(prefix='.work-control-preparation-observation-',dir=control.parent)
with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
os.chmod(tmp,control.stat().st_mode&0o777);assert control.read_bytes()==old;os.replace(tmp,control)
print(json.dumps(status))
