"""Read-only arithmetic on one original pair of immutable passive API snapshots."""
from pathlib import Path
import json,hashlib,os,stat,time,sys
HERE=Path(__file__).resolve().parent
GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
def pin(p):
 s=p.stat();raw=p.read_bytes();assert p.stat()==s
 return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink))
def main():
 out=HERE/'readback.json';assert not out.exists()
 a=json.loads((HERE/'start-API.json').read_bytes());b=json.loads((HERE/'end-API.json').read_bytes())
 owners=[json.loads((HERE/name).read_bytes()) for name in ['start-owner.json','end-owner.json']]
 assert all(x['pid']==3170722 and x['starttime_ticks']==52892579 for x in owners)
 assert owners[0]['cgroup']==owners[1]['cgroup'] and 'robotron-managed-run-26-d3b365c9-trainer.service' in owners[0]['cgroup']
 dt=b['ts']-a['ts'];assert 60<=dt<=180
 for v in [a,b]:
  assert v['client_count']==192 and v['training_enabled'] and v['lr']==0.0000125
  assert v['epsilon']==0.1 and abs(v['expert_ratio']-0.1)<1e-10
  assert not v['pipeline_read_error'] and not v['bank_persistence_read_error']
  assert v['pipeline_snapshot_age_s']<3
  assert v['quality_campaign']['current_leg']==3 and v['quality_campaign']['state']=='running' and not v['quality_campaign']['stale']
  assert v['bank_persistence']['write_failures']==0
 x=a['host_pipeline']['learning_exposure'];y=b['host_pipeline']['learning_exposure']
 for key in ['optimizer','replay']:
  for f in ['schema','enabled','available','process_id','instance_monotonic_ns','epoch','epoch_reason']:
   assert x[key][f]==y[key][f],(key,f)
  assert x[key]['enabled'] and x[key]['available'] and x[key]['process_id']==3170722
 def delta(old,new):
  d=new-old;assert d>=0;return d
 d={k:delta(a[k],b[k]) for k in ['frame_count','learner_frame_count','training_steps','optimized_samples']}
 d['optimizer_applied']=delta(x['optimizer']['total']['applied'],y['optimizer']['total']['applied'])
 d['optimizer_amp_skipped']=delta(x['optimizer']['total']['amp_skipped'],y['optimizer']['total']['amp_skipped'])
 d['optimizer_unavailable']=delta(x['optimizer']['total']['unavailable'],y['optimizer']['total']['unavailable'])
 d['accepted_learner_replay']=delta(x['replay']['accepted_learner_total'],y['replay']['accepted_learner_total'])
 d['accepted_by_source']={k:delta(x['replay']['accepted_by_source_total'][k],y['replay']['accepted_by_source_total'][k]) for k in x['replay']['accepted_by_source_total']}
 assert d['accepted_learner_replay']==d['accepted_by_source']['dqn']+d['accepted_by_source']['epsilon']
 rates={k:value/dt for k,value in d.items() if isinstance(value,(int,float))}
 report=dict(schema='profile06-R2-passive-main-training-exposure-rates-v1',observed_unix_s=time.time(),source=pin(Path(__file__)),snapshots=[pin(HERE/name) for name in ['start-API.json','end-API.json','start-owner.json','end-owner.json']],production_counter_sources=[pin(GAME/'Scripts/dqn'/name) for name in ['config.py','socket_server.py','learning_exposure.py']],duration_s=dt,deltas=d,rates_per_s=rates,main_pid=3170722,main_starttime_ticks=52892579,main192_at_both_ends=True,epochs_and_process_instances_unchanged=True,optimizer_scope=y['optimizer']['scope'],replay_scope=y['replay']['scope'],scope='One passive interval with concurrent original R2 evaluation; host/API counters, no benchmark, causal comparison, parameter movement or learning-quality gain proof.',learning_speed_gain_verified=False,quality_qualified=False,promotion=False,source_or_runtime_changed=False)
 with out.open('xb') as f:f.write((json.dumps(report,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 print(json.dumps(dict(readback=pin(out),duration_s=dt,rates_per_s=rates,deltas=d)))
if __name__=='__main__':
 if sys.argv[1:]==['--observe']:main()
 else:print('PLAN_ONLY: passive immutable-snapshot arithmetic requires --observe')
