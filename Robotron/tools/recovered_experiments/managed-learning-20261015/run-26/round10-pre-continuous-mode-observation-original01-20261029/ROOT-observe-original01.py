"""One original60s read-only pre-continuous baseline; no training controls or score claims."""
import json, urllib.request, time, statistics, os
from pathlib import Path
D=Path(__file__).resolve().parent
rows=[];start=time.monotonic()
for i in range(7):
    if i:time.sleep(max(0,start+i*10-time.monotonic()))
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10) as f:u=json.load(f)
    h=u['host_pipeline'];e=h['learning_exposure'];o=e['optimizer'];r=e['replay'];g=next(x for x in u['gpus']if 'GB300'in x['name'])
    roles=u['client_rows'];a=dict(sample=i,observed_unix_s=time.time(),api_ts=u['ts'],pipeline_elapsed_s=h['elapsed_s'],pipeline_age_s=u['pipeline_snapshot_age_s'],generation=h['generation'],optimizer_identity=[o[k]for k in ['process_id','instance_monotonic_ns','epoch']],replay_identity=[r[k]for k in ['process_id','instance_monotonic_ns','epoch']],applied=o['total']['applied'],amp_skipped=o['total']['amp_skipped'],unavailable=o['total']['unavailable'],accepted_replay=r['accepted_total'],accepted_learner=r['accepted_learner_total'],raw_frame_count=u['frame_count'],optimized_samples=u['optimized_samples'],logical_steps=u['steps']if 'steps'in u else u.get('training_steps'),live_clients=u['client_count'],active_train=sum(x['eval']is False for x in roles),active_eval=sum(x['eval']is True for x in roles),round=u['training_round']['round'],gpu=g)
    assert len(roles)==u['client_count'] and a['optimizer_identity']==[294486,13696311381440,1] and a['replay_identity']==[294486,13698215653852,1] and a['generation']==0 and a['round']==10 and 0<=a['pipeline_age_s']<=5
    if rows:assert all(a[k]>=rows[-1][k]for k in ['pipeline_elapsed_s','applied','accepted_replay','accepted_learner','raw_frame_count','optimized_samples'])
    rows.append(a)
    with (D/'observations-original01.jsonl').open('a')as f:f.write(json.dumps(a,allow_nan=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
    print(json.dumps({'sample':i,'train':a['active_train'],'eval':a['active_eval'],'GB300_busy':g['gpu_util_pct']}),flush=True)
a,b=rows[0],rows[-1];dt=b['pipeline_elapsed_s']-a['pipeline_elapsed_s'];api_dt=b['api_ts']-a['api_ts'];out=dict(schema='robotron-pre-continuous-readonly-observational-baseline-v1',status='PASS_OBSERVATION_ONLY',samples=len(rows),pipeline_elapsed_s=dt,API_elapsed_s=api_dt,applied_updates_per_pipeline_s=(b['applied']-a['applied'])/dt,AMP_skipped=b['amp_skipped']-a['amp_skipped'],unavailable=b['unavailable']-a['unavailable'],replay_inserts_per_pipeline_s=(b['accepted_replay']-a['accepted_replay'])/dt,learner_inserts_per_pipeline_s=(b['accepted_learner']-a['accepted_learner'])/dt,raw_frames_per_API_s=(b['raw_frame_count']-a['raw_frame_count'])/api_dt,optimized_samples_per_API_s=(b['optimized_samples']-a['optimized_samples'])/api_dt,samples_per_raw_frame=(b['optimized_samples']-a['optimized_samples'])/(b['raw_frame_count']-a['raw_frame_count']),GB300_busy_sampled_mean=statistics.mean(x['gpu']['gpu_util_pct']for x in rows),GB300_memory_percent_mean=statistics.mean(100*x['gpu']['mem_used_mib']/x['gpu']['mem_total_mib']for x in rows),first_roles=[a['active_train'],a['active_eval']],last_roles=[b['active_train'],b['active_eval']],training_controls_changed=False,model_replay_changed=False,quality_or_causal_speed_gain_claimed=False,limits='Current round10 tail observed only; producer elapsed clocks used for applied/replay counters, API clocks for raw/sample schedule counters; sampled GPU gauges are not kernel efficiency or guaranteed peak throughput.')
p=D/'observational-baseline-original01.json'
with p.open('x')as f:json.dump(out,f,allow_nan=False,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
for p in [p,D/'observations-original01.jsonl']:os.chmod(p,0o444)
print(json.dumps(out),flush=True)
