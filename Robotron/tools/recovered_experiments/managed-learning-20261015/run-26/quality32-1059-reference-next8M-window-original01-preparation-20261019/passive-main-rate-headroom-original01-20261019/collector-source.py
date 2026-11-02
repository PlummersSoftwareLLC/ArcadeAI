import json,time,hashlib,importlib.util,math,os,statistics,urllib.request
from pathlib import Path
P=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-1059-reference-next8M-window-original01-preparation-20261019');D=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-1059-reference-next8M-window-original01-preparation-20261019/passive-main-rate-headroom-original01-20261019')
def load(path,sha,name):
 assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
p=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','reader')
c=load(G/'tools/eval_capacity_proposal/control_original_pilot.py','db1119b3ea7db7e9878b7ebd89f06a3b1c126bde46a5398617a3739917a2d9b9','owner')
selection=p.read_pin(p.pin(P/'root-selection.json'));job=p.read_pin(selection['job']);owner=p.read_pin(p.pin(P/'execution/root-original-live-owner.json'))
w=load(Path(selection['source']['path']),selection['source']['sha256'],'window')
rawmod=load(G/'tools/eval_capacity_proposal/raw_api_witness_v1.py','9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0','raw')
counters=load(Path(job['counter_module']['path']),job['counter_module']['sha256'],'counters')
def save(name,value):return w.publish(D/name,value)
samples=[];normal=[];raw_metrics=[];start=time.monotonic();baseline=p.read_pin(job['baseline_API'])
try:
 for i in range(13):
  delay=start+i*10-time.monotonic()
  if delay>0:time.sleep(delay)
  fields=c.show(owner['unit']);assert fields['MainPID']==str(owner['pid']) and fields['InvocationID']==owner['invocation_id'] and fields['NRestarts']=='0'
  assert w.process_start(owner['pid'])==owner['starttime_ticks'];w.owner_and_files(job)
  with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:raw=response.read(rawmod.MAX_WIRE_BYTES+1)
  raw_pin=save(f'{i:02d}-API.raw',raw);api=rawmod.parse_wire(raw);w.healthy(api,baseline,job['experiment'],time.time());value=counters.normalise(api)
  metrics={key:(api.get(key) if type(api.get(key)) in (int,float) and math.isfinite(api[key]) else None) for key in ('fps','steps_per_sec','train_sample_ms','train_transfer_ms','train_compute_ms','train_priority_ms','train_step_ms','cpu_util','gpu0_util','gpu1_util','gpu1_power_w','ram_free_gib')}
  record=dict(index=i,unix_s=time.time(),monotonic_s=time.monotonic(),**rawmod.witness_fields(api,raw_pin),metrics=metrics)
  samples.append(save(f'{i:02d}-witness.json',record));normal.append(value);raw_metrics.append(record)
 elapsed=raw_metrics[-1]['monotonic_s']-raw_metrics[0]['monotonic_s'];first,last=normal[0],normal[-1]
 for group in ('optimizer_identity','replay_identity'):assert first[group]==last[group]
 delta={key:last['clocks'][key]-first['clocks'][key] for key in first['clocks']}
 applied=last['optimizer']['applied']-first['optimizer']['applied'];skips=last['optimizer']['amp_skipped']-first['optimizer']['amp_skipped']
 means={key:statistics.mean(row['metrics'][key] for row in raw_metrics if row['metrics'][key] is not None) for key in raw_metrics[0]['metrics'] if any(row['metrics'][key] is not None for row in raw_metrics)}
 result=dict(status='PASS_PASSIVE_MAIN_ONLY_RATE_WITNESSES',samples=samples,sample_count=13,elapsed_s=elapsed,work_delta=delta,applied_updates=applied,AMP_skips=skips,fleet_frames_per_s=delta['frame_count']/elapsed,learner_frames_per_s=delta['learner_frame_count']/elapsed,logical_samples_per_s=delta['optimized_samples']/elapsed,logical_updates_per_s=delta['training_steps']/elapsed,applied_updates_per_s=applied/elapsed,logical_samples_per_fleet_frame=delta['optimized_samples']/delta['frame_count'],mean_reported_diagnostics=means,current_configured_sample_cap=8,measurements_are_observational=True,causal_capacity_or_learning_speed_gain_verified=False,recipe_or_main_changed=False,model_or_replay_loaded=False)
 save('root-readback.json',result);print(json.dumps({key:value for key,value in result.items() if key!='samples'}))
except BaseException as error:
 save('failure-preserved.json',dict(error=repr(error),samples=samples,main_changed=False));raise
