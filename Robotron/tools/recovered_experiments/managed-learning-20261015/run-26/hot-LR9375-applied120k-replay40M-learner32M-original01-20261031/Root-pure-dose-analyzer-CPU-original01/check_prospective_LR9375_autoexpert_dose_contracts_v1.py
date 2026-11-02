"""Root-only synthetic CPU qualification; no live observations or training actions."""
import copy,hashlib,importlib.util,json,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
L=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/hot-LR625-applied30k-replay10M-learner8M-original01-20261031')
SOURCE=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/hot-LR9375-applied120k-replay40M-learner32M-original01-20261031/selected-source/analyze_LR9375_autoexpert_dose_v1.py')
SHA='2c35dfe9e94719913c507da89f5b0b69a5f0031b30633752a13d0a5c83524c48'

def main():
 assert sys.argv[1:]==['--execute']
 assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SHA
 spec=importlib.util.spec_from_file_location('_root_prospective_LR9375_autoexpert_analyzer',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 raw=json.loads((L/'Root-actual-LR625-dose-anchor-sample-original01.json').read_text());sample=json.loads((L/'dose-observations-original01/000001-sample.json').read_text())
 for obj in (raw,sample):
  obj['api_now']['game_settings']['expert_pct']=-1;obj['api_now']['expert_ratio']=.1;obj['api_now']['lr']=5e-5*.1875;obj['api_now']['epsilon']=.1;obj['continuous_policy']['ratchet_frozen']=False
 e=raw['api_now']['host_pipeline']['learning_exposure']
 a=dict(schema='robotron-LR9375-autoexpert-dose-anchor-v1',main_owner=raw['observed_main_owner'],expected_lr=9.375e-6,expected_expert=.1,expected_epsilon=.1,control_sha256=raw['observed_control_sha256'],observed_unix_s=raw['observed_unix_s'],api_ts=raw['api_now']['ts'],optimizer_identity={k:e['optimizer'][k] for k in m.IDS},replay_identity={k:e['replay'][k] for k in m.IDS},base=m.counters(raw['api_now']),targets=dict(m.TARGETS))
 checks=[]
 before=copy.deepcopy((a,sample));r=m.analyze(a,sample);assert r['status']=='VALID' and r['deltas']==dict(applied_updates=3371,replay_additions=1265372,learner_frames=901993) and not r['all_reached'] and r['estimated_remaining_s']>0 and (a,sample)==before;checks.append('historical counters with synthetic LR9.375 and autoexpert10 observations: exact deltas, finite ETA, no mutation')
 def case(label,change,status):
  v=copy.deepcopy(sample);change(v);ans=m.analyze(a,v);assert ans['status']==status and (status=='VALID' or not ans['all_reached']),(label,ans);checks.append(label)
 case('owner drift rejects',lambda v:v['observed_main_owner'].update(birth=1),'REJECTED')
 case('control drift rejects',lambda v:v.update(observed_control_sha256='1'*64),'REJECTED')
 for kind in ('optimizer','replay'):case(kind+' epoch drift rejects',lambda v,k=kind:v['api_now']['host_pipeline']['learning_exposure'][k].update(epoch=99),'REJECTED')
 for value in (10,5):case('expert override '+str(value)+' rejects',lambda v,x=value:v['api_now']['game_settings'].update(expert_pct=x),'REJECTED')
 case('effective expert drift rejects',lambda v:v['api_now'].update(expert_ratio=.05),'REJECTED')
 case('epsilon drift rejects',lambda v:v['api_now'].update(epsilon=.2),'REJECTED')
 case('ratchet frozen rejects',lambda v:v['continuous_policy'].update(ratchet_frozen=True),'REJECTED')
 case('missing expert observation waits',lambda v:v['api_now']['game_settings'].pop('expert_pct'),'PENDING')
 case('boolean expert override waits',lambda v:v['api_now']['game_settings'].update(expert_pct=True),'PENDING')
 case('nonfinite expert observation waits',lambda v:v['api_now'].update(expert_ratio=float('nan')),'PENDING')
 case('cached API waits',lambda v:v['api_now'].update(ts=a['api_ts']),'PENDING')
 case('stale pipeline waits',lambda v:v['api_now'].update(pipeline_snapshot_age_s=11),'PENDING')
 case('unbalanced source sums wait',lambda v:v['api_now']['host_pipeline']['learning_exposure']['replay'].update(accepted_total=1),'PENDING')
 def unavailable(v):
  o=v['api_now']['host_pipeline']['learning_exposure']['optimizer']
  for k in ('attempts_started','outcomes_recorded','unavailable'):o['total'][k]+=1
  o['available']=False
 case('new unavailable rejects',unavailable,'REJECTED')
 def pending(v):
  o=v['api_now']['host_pipeline']['learning_exposure']['optimizer'];o['total']['attempts_started']+=1;o['unclassified_started_total']=1;o['available']=False
 case('one supported inflight outcome waits',pending,'PENDING')
 def endpoint(applied=120000,replay=40000000,learner=32000000,elapsed=4800):
  v=copy.deepcopy(raw);v['observed_unix_s']+=elapsed;api=v['api_now'];api['ts']+=elapsed;v['continuous_policy']['observed_unix_s']=v['observed_unix_s']-.01;api['pipeline_snapshot_age_s']=.1
  o=api['host_pipeline']['learning_exposure']['optimizer']
  for k in ('attempts_started','outcomes_recorded','applied'):o['total'][k]+=applied
  rr=api['host_pipeline']['learning_exposure']['replay'];rr['accepted_total']+=replay;rr['accepted_learner_total']+=16000000
  for k,n in dict(dqn=14400000,epsilon=1600000,expert=1000000,eval=replay-17000000).items():rr['accepted_by_source_total'][k]+=n
  api['learner_frame_count']+=learner;api['training_steps']+=applied;return v
 ans=m.analyze(a,endpoint());assert ans['status']=='VALID' and ans['all_reached'] and ans['estimated_remaining_s']==0;checks.append('all120k40M32M thresholds required and reached')
 for key,args in [('applied_updates',dict(applied=119999)),('replay_additions',dict(replay=39999999)),('learner_frames',dict(learner=31999999))]:
  ans=m.analyze(a,endpoint(**args));assert ans['status']=='VALID' and not ans['all_reached'] and ans['remaining'][key]==1;checks.append('one below '+key+' cannot finish')
 ans=m.analyze(a,endpoint(elapsed=119));assert ans['status']=='VALID' and ans['estimated_remaining_s'] is None;checks.append('no ETA before120seconds')
 v=copy.deepcopy(sample);prev=copy.deepcopy(r['counters'])
 for k in ('attempted','outcomes','applied'):prev[k]+=1
 v['previous']=dict(counters=prev,api_ts=sample['api_now']['ts']-.1);assert m.analyze(a,v)['status']=='REJECTED';checks.append('counter decrease versus previous rejects')
 out=dict(schema='robotron-Root-prospective-LR9375-autoexpert-analyzer-pure-CPU-v1',status='PASS_SYNTHETIC_CONTRACTS_ONLY',checks_count=len(checks),checks=checks,source_sha256=SHA,actual_expert_change=False,actual_trial_or_dose=False,live_observations=False,model_or_control_actions=False,scope='Immutable historical counters and deliberately synthetic LR9.375 and autoexpert10 observations; no live LR9375 observations, dose, policy, or quality evidence.')
 with (HERE/'report.json').open('x') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
 print(json.dumps(dict(status=out['status'],checks=len(checks))))

if __name__=='__main__':main()
