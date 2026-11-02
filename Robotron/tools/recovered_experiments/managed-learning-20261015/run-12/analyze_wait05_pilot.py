#!/usr/bin/env python3
"""Read-only reduction of bounded graph/fleet pilot observations, stdlib only."""
from datetime import datetime,timezone
from pathlib import Path
import argparse,csv,hashlib,json,math,statistics

BASE=Path(__file__).resolve().parent
RAW=BASE/'wait05-pilot-observations.jsonl'
GPU_FIELDS=('gpu1_util','gpu1_power_w','gpu1_mem_used_mib','gpu1_clock_mhz','avg_inf_ms','cpu_util','cpu_load_1m','ram_available_gib')
CSV_FIELDS=('frames_per_s','samples_per_s','samples_per_frame','gpu_util_pct','gpu_power_w','samples_per_joule',
 'infer_batch_rows_mean','infer_sync_lock_wait_ms_mean','infer_input_transfer_host_ms_mean',
 'infer_dispatch_host_ms_mean','infer_cpu_readback_host_ms_mean','infer_service_host_ms_mean',
 'actor_refresh_sync_lock_wait_ms_mean','actor_refresh_copy_host_ms_mean','actor_refresh_service_host_ms_mean',
 'target_refresh_host_ms_mean','sample_wall_ms','compute_host_ms','priority_and_readback_ms','train_step_wall_ms','gpu_compute_ms')

def epoch(value): return datetime.fromisoformat(value).timestamp()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def good(row):return not row.get('observation_error')

def distribution(a,b,bounds):
 n=b['count']-a['count']; total=b['total']-a['total']
 hist=[y-x for x,y in zip(a['histogram'],b['histogram'])]
 assert n>=0 and all(x>=0 for x in hist) and sum(hist)==n
 def quantile(q):
  if not n:return None
  target=math.ceil(n*q); seen=0
  for bound,count in zip(bounds,hist):
   seen+=count
   if seen>=target:return bound
 return dict(count=n,mean=total/n if n else None,histogram=hist,p50_bin_upper=quantile(.5),p95_bin_upper=quantile(.95),cumulative_max_at_end=b['max'])

def window(rows,label):
 a,b=rows[0],rows[-1];dt=b['elapsed_s']-a['elapsed_s']
 frame_delta=b['frame_count']-a['frame_count'];sample_delta=b['optimized_samples']-a['optimized_samples']
 energy=sum((left['gpu1_power_w']+right['gpu1_power_w'])/2*(right['elapsed_s']-left['elapsed_s']) for left,right in zip(rows,rows[1:]))
 result=dict(label=label,utc_start=a['utc'],utc_end=b['utc'],duration_s=dt,observations=len(rows),clients=sorted({r['client_count'] for r in rows}),
  frame_delta=frame_delta,sample_delta=sample_delta,frames_per_s=frame_delta/dt,samples_per_s=sample_delta/dt,
  samples_per_frame=sample_delta/frame_delta if frame_delta else None,samples_per_joule=sample_delta/energy,
  gauges={key:dict(mean=statistics.mean(row[key] for row in rows),minimum=min(row[key] for row in rows),maximum=max(row[key] for row in rows)) for key in GPU_FIELDS},
  clocks={side:{key:row[key] for key in ('frame_count','learner_frame_count','optimized_samples','training_steps')} for side,row in [('start',a),('end',b)]})
 pa,pb=a['host_pipeline'],b['host_pipeline']
 result['pipeline']=dict(generation=pb['generation'],sample_every=pb['sample_every'],eligible_calls=pb['inference_eligible_calls']-pa['inference_eligible_calls'])
 for section in ('inference','actor_refresh','target_refresh'):
  start,end=pa[section],pb[section]
  entry=dict(count=end['count']-start['count'],errors=end['errors']-start['errors'])
  for key,value in end.items():
   if isinstance(value,dict) and 'histogram' in value:
    bounds=pb['batch_size_bucket_upper'] if key=='batch_size' else pb['latency_bucket_upper_ms']
    entry[key]=distribution(start[key],value,bounds)
  result['pipeline'][section]=entry
 ga,gb=pa['inference_graphs'],pb['inference_graphs']
 result['graphs']=dict(capture_count=gb['capture_count'],runtime_capture_count=gb['runtime_capture_count'],fallback_count=gb['fallback_count'],fatal_error=gb['fatal_error'],ready=gb['ready'],replay_delta=gb['replay_count']-ga['replay_count'],cpu_return_delta=gb['cpu_return_batches']-ga['cpu_return_batches'],rows_delta=gb['cpu_return_rows']-ga['cpu_return_rows'],all_call_batch_mean=(gb['cpu_return_rows']-ga['cpu_return_rows'])/(gb['cpu_return_batches']-ga['cpu_return_batches']) if gb['cpu_return_batches']>ga['cpu_return_batches'] else None,completed_calls_per_s=(gb['cpu_return_batches']-ga['cpu_return_batches'])/dt,validation_replays=gb['validation_replay_count'],graph_owned_reserved_bytes=gb['graph_owned_reserved_bytes'])
 csvrows=[r for r in csv.DictReader((BASE/'training.csv').open()) if epoch(a['utc'])+31<=epoch(r['utc'])<=epoch(b['utc']) and int(r['clients']) in result['clients']]
 result['CSV_rows']=len(csvrows)
 result['CSV_descriptive_means']={key:statistics.mean(float(r[key]) for r in csvrows if r[key]) if any(r[key] for r in csvrows) else None for key in CSV_FIELDS}
 return result


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',default='wait05-pilot-analysis.json');args=parser.parse_args()
 raw_files=[path for path in (RAW,BASE/'wait05-pilot-observations-extended.jsonl') if path.exists()]
 prefixes=[];rows=[];extended_complete=False
 for path in raw_files:
  data=path.read_bytes();end=data.rfind(b'\n')+1;prefix=data[:end]
  parsed=[json.loads(line) for line in prefix.splitlines() if line.strip()]
  prefixes.append(dict(path=str(path),complete_prefix_bytes=end,sha256=hashlib.sha256(prefix).hexdigest(),rows=len(parsed),last_index=parsed[-1]['index'] if parsed else None,utc_minus_monotonic_drift_s=(epoch(parsed[-1]['utc'])-epoch(parsed[0]['utc']))-(parsed[-1]['elapsed_s']-parsed[0]['elapsed_s']) if len(parsed)>1 else None))
  rows.extend(parsed)
  completion_path=BASE/('wait05-observer-extended-complete.json' if path.name.endswith('-extended.jsonl') else 'wait05-observer-complete.json')
  if completion_path.exists() and parsed:
   completion=json.loads(completion_path.read_text())
   extended_complete=parsed[-1]['index']==completion['duration_requested_s']
 completion_flags=[]
 for record in prefixes:
  completion_path=BASE/('wait05-observer-extended-complete.json' if record['path'].endswith('-extended.jsonl') else 'wait05-observer-complete.json')
  receipt=json.loads(completion_path.read_text()) if completion_path.exists() else {}
  completion_flags.append(receipt.get('status')=='complete' and record['last_index']==receipt.get('duration_requested_s'))
 extended_complete=len(prefixes)==2 and all(completion_flags)
 rows.sort(key=lambda row:epoch(row['utc']))
 end_marker=BASE/'pilot-run-end.json'
 closed=json.loads(end_marker.read_text()) if end_marker.exists() else None
 ignored_after_end=0
 if closed:
  ignored_after_end=sum(epoch(row['utc'])>=epoch(closed['utc']) for row in rows)
  rows=[row for row in rows if epoch(row['utc'])<epoch(closed['utc'])]
 for row in rows:row['elapsed_s']=epoch(row['utc'])-epoch(rows[0]['utc'])
 valid=[r for r in rows if good(r)]
 baseline=json.loads((BASE/'pilot-baseline.json').read_text())
 graph192=json.loads((BASE.parent/'run-10/graph192-phase-locked.json').read_text())['phase']
 cohorts=[];cuts=[];previous=None;identity=None
 # Never bridge an API observation error, long gap, process/epoch change or
 # a histogram/schema change, even when the client count happens to match.
 for row in rows:
  if not good(row):cuts.append(dict(utc=row['utc'],reason='observation_error'));previous=None;continue
  pipe=row['host_pipeline']
  header=(pipe['schema'],pipe['generation'],pipe['sample_every'],tuple(pipe['latency_bucket_upper_ms']),tuple(pipe['batch_size_bucket_upper']))
  process=row.get('process_identity',{}).get('start_ticks',identity)
  reason=None
  if previous is None:reason='start_or_after_observation_error'
  elif epoch(row['utc'])-epoch(previous['utc'])>2.5:reason='observation_gap'
  elif row['client_count']!=previous['client_count']:reason='client_count_changed'
  elif header!=previous['_pipeline_header']:reason='pipeline_metadata_changed'
  elif pipe['elapsed_s']<previous['host_pipeline']['elapsed_s']:reason='pipeline_clock_restarted'
  elif pipe['inference_eligible_calls']<previous['host_pipeline']['inference_eligible_calls']:reason='pipeline_counters_restarted'
  elif process!=identity:reason='process_identity_changed'
  row['_pipeline_header']=header
  if reason:
   cuts.append(dict(utc=row['utc'],reason=reason,clients=row['client_count']))
   cohorts.append([row])
  else:cohorts[-1].append(row)
  previous=row;identity=process
 results=[]
 for phase in cohorts:
  if phase[0]['client_count']<128:continue
  count=phase[0]['client_count']
  begin=epoch(phase[0]['utc'])+60
  begin_source='first observed stable count plus60s'
  ready=BASE/f'actor{count}-wait05-all-connected.json'
  if count>128 and ready.exists():
   begin=max(epoch(phase[0]['utc']),epoch(json.loads(ready.read_text())['utc'])+90)
   begin_source=str(ready)+' plus prespecified90s settle'
  stop=float('inf');stop_source=None
  for marker in BASE.glob('actor*-transition.json'):
   event=json.loads(marker.read_text())
   if event.get('phase','').startswith(str(count)+'_to_'):
    candidate=epoch(event['utc'])
    if candidate<stop:stop=candidate;stop_source=str(marker)
  settled=[r for r in phase if begin<=epoch(r['utc'])<stop]
  if len(settled)>=2 and settled[-1]['elapsed_s']-settled[0]['elapsed_s']>=120:
   result=window(settled,f"clients{phase[0]['client_count']}-settled")
   result['requested_minimum_settled_s']=180
   result['meets_requested_minimum']=result['duration_s']>=180
   result['window_status']='measured' if result['meets_requested_minimum'] else 'provisional_shorter_than_requested'
   result['window_definition']=dict(start_source=begin_source,end_source=stop_source,first_allowed_utc=datetime.fromtimestamp(begin,timezone.utc).isoformat())
   result['vs_run10_graph192_1ms_samples_ratio']=result['samples_per_s']/graph192['samples_per_s']
   result['vs_prespecified_run09_samples_ratio']=result['samples_per_s']/baseline['values']['samples_per_s']['mean']
   result['vs_prespecified_run09_samples_per_joule_ratio']=result['samples_per_joule']/baseline['values']['samples_per_joule']['mean']
   results.append(result)
 definitions=BASE/'pilot-phase-definitions.json'
 if definitions.exists():
  results=[]
  for spec in json.loads(definitions.read_text()):
   ready=BASE/spec['ready_receipt']
   if not ready.exists():continue
   begin=epoch(json.loads(ready.read_text())['utc'])+spec['settle_s']
   stop=float('inf');stop_path=BASE/spec['stop_receipt'] if spec.get('stop_receipt') else None
   if stop_path is not None and stop_path.exists():stop=epoch(json.loads(stop_path.read_text())['utc'])
   selected=[row for row in valid if begin<=epoch(row['utc'])<stop and row['client_count']==spec['actor_count']]
   if len(selected)<2 or epoch(selected[-1]['utc'])-epoch(selected[0]['utc'])<120:continue
   assert all(epoch(right['utc'])-epoch(left['utc'])<=2.5 for left,right in zip(selected,selected[1:])), 'Phase crosses an observation gap'
   assert all(row['_pipeline_header']==selected[0]['_pipeline_header'] for row in selected), 'Phase crosses a pipeline epoch'
   result=window(selected,spec['label']);result['phase_definition']=spec
   result['requested_minimum_settled_s']=spec['minimum_measure_s']
   result['meets_requested_minimum']=result['duration_s']>=spec['minimum_measure_s']
   result['window_status']='measured' if result['meets_requested_minimum'] else 'provisional_shorter_than_requested'
   result['vs_run10_graph192_1ms_samples_ratio']=result['samples_per_s']/graph192['samples_per_s']
   result['vs_prespecified_run09_samples_ratio']=result['samples_per_s']/baseline['values']['samples_per_s']['mean']
   results.append(result)
 # Align the same15 predeclared CSV intervals by cumulative-counter delta.
 old=list(csv.DictReader((BASE.parent/'run-09/training.csv').open()))
 inds=[i for i,r in enumerate(old) if baseline['first_utc']<=r['utc']<=baseline['last_utc']]
 oa,oz=old[inds[0]-1],old[inds[-1]]
 duration=epoch(oz['utc'])-epoch(oa['utc'])
 aligned=dict(first_interval_start=oa['utc'],last_interval_end=oz['utc'],intervals=len(inds),duration_s=duration,samples_per_s=(int(oz['optimized_samples'])-int(oa['optimized_samples']))/duration,frames_per_s=(int(oz['frames'])-int(oa['frames']))/duration)
 for result in results:result['vs_counter_aligned_run09_samples_ratio']=result['samples_per_s']/aligned['samples_per_s']
 guards=dict(observation_errors=[r.get('observation_error') for r in rows if not good(r)],
  all_graphs_ready=all(r['host_pipeline']['inference_graphs'].get('ready') for r in valid),
  capture_counts=sorted({r['host_pipeline']['inference_graphs']['capture_count'] for r in valid}),
  runtime_capture_counts=sorted({r['host_pipeline']['inference_graphs']['runtime_capture_count'] for r in valid}),
  fallback_counts=sorted({r['host_pipeline']['inference_graphs']['fallback_count'] for r in valid}),
  fatal_errors=sorted({r['host_pipeline']['inference_graphs']['fatal_error'] for r in valid if r['host_pipeline']['inference_graphs']['fatal_error'] is not None}),
  deadline_lines_start=valid[0]['deadline_lines'],deadline_lines_end=valid[-1]['deadline_lines'],
  latest_console_counts=valid[-1]['console_counts'],latest_error_lines=valid[-1]['parse_error_lines'])
 x=dict(schema='robotron-graph-combined-training-pilot-v1',utc=datetime.now(timezone.utc).isoformat(),
  raw_observations=prefixes,segmentation_cuts=cuts,elapsed_s=valid[-1]['elapsed_s'],samples=len(rows),
  status='run12_closed_by_root' if closed else ('bounded_observation_complete' if extended_complete else 'interim'),run_end=closed,ignored_after_run_end_rows=ignored_after_end,guards=guards,
  prespecified_baseline=baseline,run10_graph192_1ms_baseline=graph192,counter_aligned_baseline=aligned,phases=results,
  limitations=['Operational sequential comparison, not randomized same-model/same-game-state A/B; training and game density evolve.',
  'UTC rebases the two observers; within-file UTC-vs-monotonic drift must be checked. One-second observations are autocorrelated, not independent trials.',
  'API rates use exact cumulative sample/frame deltas across host wall time. GPU power is integrated sampled device power, not whole-system energy.',
  'Histogram statistics use sampled cumulative deltas; p95 values are bucket upper bounds, not exact percentiles. Max values are cumulative, not interval maxima.',
  'Training sample/compute/priority/step CSV durations are descriptive last-published values, not a complete per-update distribution.',
  'Graph replay relocates GPU wait from host dispatch to CPU readback; total service and total useful training throughput matter.',
  '128 uses observer start plus60s; later phases use root all-connected receipts plus prespecified90s settling, and root stop receipts trim prior phases. This cannot alone prove game-state stabilization.',
  'No GPU contexts, source edits, trainer/fleet controls or RNG/replay mutation from this observer.'])
 (BASE/args.output).write_text(json.dumps(x,indent=2)+'\n')
 print(json.dumps(dict(output=args.output,status=x['status'],elapsed_s=x['elapsed_s'],guards=guards,phases=[{k:p[k] for k in ('label','utc_start','utc_end','duration_s','frames_per_s','samples_per_s','samples_per_frame','samples_per_joule','vs_prespecified_run09_samples_ratio')} for p in results]),indent=2))
if __name__=='__main__':main()
