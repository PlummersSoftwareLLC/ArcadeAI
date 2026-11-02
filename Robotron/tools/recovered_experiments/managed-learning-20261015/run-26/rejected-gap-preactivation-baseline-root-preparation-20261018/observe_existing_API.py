import argparse,datetime,hashlib,json,math,os,time,urllib.request
from pathlib import Path
P=argparse.ArgumentParser();P.add_argument('--output',type=Path,required=True);a=P.parse_args()
expected_start=38102590;pid=2257565
base=Path('/home/dave/source/repos/ArcadeAI/Robotron')
sources={'Scripts/dqn/socket_server.py':'4a1f6a3cc7c82d8c85e1af93ceac0ca7457663d5f5ba7c7d893e3c2b3003e26c','Scripts/dqn/metrics_dashboard.py':'3013d511f1d933fe6012df5cecd7f8a8861824bdd41580cbe241b7498916f1c6','Scripts/dqn/experiment_status.py':'e7048ec8365bca60f7bd320794c635e491407b33113e37a617f06f9f9d56c237'}
def guard():
 fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();assert int(fields[19])==expected_start
 for fn,h in sources.items():assert hashlib.sha256((base/fn).read_bytes()).hexdigest()==h
 assert not (base/'Scripts/dqn/rejected_gap_telemetry.py').exists()
def key(x):return tuple(x[k] for k in ['process_id','instance_monotonic_ns','epoch'])
start=time.monotonic();samples=[];firstkeys=None
for i in range(7):
 target=start+i*20
 if time.monotonic()<target:time.sleep(target-time.monotonic())
 guard();before=time.monotonic();x=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=8));after=time.monotonic()
 assert x['training_enabled'] and not x['measurement_active'] and x['client_count']==192 and not x['pipeline_read_error'] and not x['bank_persistence_read_error']
 assert x['pipeline_snapshot_age_s']<10 and abs(time.time()-x['ts'])<10
 p=x['host_pipeline'];e=p['learning_exposure'];assert p['available'] and all(e[k]['available'] and e[k]['process_id']==pid for k in ['optimizer','replay'])
 keys={k:key(e[k]) for k in ['optimizer','replay']}
 if firstkeys is None:firstkeys=keys
 assert firstkeys==keys and all(p[k]['errors']==0 for k in ['inference','actor_refresh','target_refresh','learner_priority'])
 row={k:x[k] for k in ['ts','frame_count','learner_frame_count','optimized_samples','training_steps','client_count','training_enabled','fps','steps_per_sec','avg_inf_ms','train_step_ms','pipeline_snapshot_age_s','loss','grad_norm']}
 row.update(observed_monotonic_before=before,observed_monotonic_after=after,exposure=e,bank_persistence={k:x['bank_persistence'][k] for k in ['writes','write_failures','writer_active','last_write_duration_s','revision','saved_revision']})
 if samples:assert all(row[k]>=samples[-1][k] for k in ['frame_count','learner_frame_count','optimized_samples','training_steps'])
 samples.append(row)
guard();dt=samples[-1]['observed_monotonic_after']-samples[0]['observed_monotonic_after'];rates={k:(samples[-1][k]-samples[0][k])/dt for k in ['frame_count','learner_frame_count','optimized_samples','training_steps']}
rates['physical_DQN_epsilon_per_s']=(sum(samples[-1]['exposure']['replay']['accepted_by_source_total'][k] for k in ['dqn','epsilon'])-sum(samples[0]['exposure']['replay']['accepted_by_source_total'][k] for k in ['dqn','epsilon']))/dt
rates['optimizer_applied_per_s']=(samples[-1]['exposure']['optimizer']['total']['applied']-samples[0]['exposure']['optimizer']['total']['applied'])/dt
result=dict(schema='robotron-rejected-gap-preactivation-existing-API-baseline-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS',main=dict(pid=pid,starttime_ticks=expected_start),sample_count=len(samples),observed_span_s=dt,interval_s=20,samples=samples,rates=rates,sources=sources,source_changed=False,controls_changed=False,scope='Passive existing-API preactivation baseline; evolving learner/host, no causal throughput or learning-speed claim; snapshots are not coherent across all counters.')
with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
print(json.dumps(dict(status='PASS',samples=len(samples),span_s=dt,rates=rates)),flush=True)
