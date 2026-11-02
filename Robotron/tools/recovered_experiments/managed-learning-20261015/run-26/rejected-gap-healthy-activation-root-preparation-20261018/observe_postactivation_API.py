import argparse,datetime,hashlib,json,math,os,time,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
base=Path('/home/dave/source/repos/ArcadeAI/Robotron');run=base/'logs/managed-learning-20261015/run-26'
rp=run/'rejected-gap-healthy-activation-original01-20261018/result.json';rb=rp.read_bytes();assert hashlib.sha256(rb).hexdigest()=='f47b861115c62a87097f6eef0750f9c07db8a6876d59c87ab0a5ff0801a19621'
activation=json.loads(rb);assert activation['status']=='READY_HEALTHY_DIAGNOSTIC_ACTIVATION' and not activation['manual_recovery_required'];owner=activation['owner'];pid=owner['pid']
job=json.loads(Path(activation['root_job']['path']).read_text());sources={x['destination']:x['after']['sha256'] for x in job['transition']['sources']}
def guard():
 stat=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();assert int(stat[19])==owner['starttime_ticks']
 for path,digest in sources.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
def get(endpoint):
 with urllib.request.urlopen('http://127.0.0.1:8771/api/'+endpoint,timeout=8) as r:raw=r.read(2097153)
 assert len(raw)<=2097152
 return json.loads(raw)
def key(x):return tuple(x[k] for k in ('process_id','instance_monotonic_ns','epoch'))
start=time.monotonic();samples=[];firstkeys=None;gap_epoch=None
for i in range(7):
 target=start+i*20
 if time.monotonic()<target:time.sleep(target-time.monotonic())
 guard();before=time.monotonic();x=get('now');g=get('rejected_gaps');after=time.monotonic()
 assert x['training_enabled'] and not x['measurement_active'] and x['client_count']==192 and x['lr']==2.5e-5 and not x['pipeline_read_error'] and not x['bank_persistence_read_error']
 assert x['pipeline_snapshot_age_s']<10 and abs(time.time()-x['ts'])<10
 pipeline=x['host_pipeline'];e=pipeline['learning_exposure'];assert pipeline['available'] and all(e[k]['available'] and e[k]['process_id']==pid for k in ('optimizer','replay'))
 keys={k:key(e[k]) for k in ('optimizer','replay')}
 if firstkeys is None:firstkeys=keys
 assert firstkeys==keys and all(pipeline[k]['errors']==0 for k in ('inference','actor_refresh','target_refresh','learner_priority'))
 assert g['available'] and g['reason']=='available';snap=g['snapshot'];assert snap['enabled'] and snap['available'] and snap['process_id']==pid and not snap['observer_error'] and not snap['counter_saturated'] and snap['counters']['tracking_overflow']==0 and snap['active_tracked_clients']==192
 this_epoch=(snap['process_id'],snap['instance_monotonic_ns'])
 if gap_epoch is None:gap_epoch=this_epoch
 assert gap_epoch==this_epoch
 row={k:x[k] for k in ('ts','frame_count','learner_frame_count','optimized_samples','training_steps','client_count','training_enabled','fps','steps_per_sec','avg_inf_ms','train_step_ms','pipeline_snapshot_age_s','loss','grad_norm')}
 row.update(observed_monotonic_before=before,observed_monotonic_after=after,exposure=e,rejected_gaps=g,quality_campaign=x.get('quality_campaign'),bank_persistence={k:x['bank_persistence'][k] for k in ('writes','write_failures','writer_active','last_write_duration_s','revision','saved_revision')})
 if samples:
  assert all(row[k]>=samples[-1][k] for k in ('frame_count','learner_frame_count','optimized_samples','training_steps'))
  assert all(value>=samples[-1]['rejected_gaps']['snapshot']['counters'][k] for k,value in snap['counters'].items())
 samples.append(row)
guard();dt=samples[-1]['observed_monotonic_after']-samples[0]['observed_monotonic_after'];rates={k:(samples[-1][k]-samples[0][k])/dt for k in ('frame_count','learner_frame_count','optimized_samples','training_steps')}
rates['physical_DQN_epsilon_per_s']=(sum(samples[-1]['exposure']['replay']['accepted_by_source_total'][k] for k in ('dqn','epsilon'))-sum(samples[0]['exposure']['replay']['accepted_by_source_total'][k] for k in ('dqn','epsilon')))/dt
rates['optimizer_applied_per_s']=(samples[-1]['exposure']['optimizer']['total']['applied']-samples[0]['exposure']['optimizer']['total']['applied'])/dt
delta={k:value-samples[0]['rejected_gaps']['snapshot']['counters'][k] for k,value in samples[-1]['rejected_gaps']['snapshot']['counters'].items()}
result=dict(schema='robotron-rejected-gap-postactivation-existing-API-window-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS',owner=owner,activation_result=dict(path=str(rp),sha256=hashlib.sha256(rb).hexdigest(),bytes=len(rb)),sample_count=7,observed_span_s=dt,interval_s=20,samples=samples,rates=rates,rejected_gap_counter_deltas=delta,sources=sources,source_or_control_changed_during_window=False,scope='Passive two-minute live check after activation; evolving learner/host and changed process epochs, no randomized timing control or causal throughput/learning-speed claim. Independent API snapshots/counters are asynchronous, with payloads possibly in flight. UID continuity is classifier-only; no enqueue/physical replay equivalence.')
with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
print(json.dumps(dict(status='PASS',sample_count=7,span_s=dt,rates=rates,rejected_gap_counter_deltas=delta)),flush=True)
