#!/usr/bin/env python3
"""Read-only stdlib-only bounded API/console observation; no torch or controls."""
from datetime import datetime, timezone
import hashlib,json,os,time,urllib.request
from pathlib import Path

BASE=Path(__file__).resolve().parent
PID=854252
URL='http://127.0.0.1:8771/api/now'
OUT=BASE/'graph-pilot-observations-extended.jsonl'
GAUGES=('ts','frame_count','learner_frame_count','optimized_samples','training_steps',
 'fps','steps_per_sec','rpl_per_frame','avg_inf_ms','client_count','web_client_count',
 'train_sample_ms','train_transfer_ms','train_compute_ms','train_priority_ms','train_step_ms',
 'loss','grad_norm','lr','epsilon','expert_ratio','training_enabled','measurement_active',
 'gpu1_util','gpu1_mem_util','gpu1_mem_used_mib','gpu1_power_w','gpu1_temp_c','gpu1_clock_mhz',
 'gpu0_util','gpu0_mem_used_mib','cpu_util','cpu_load_1m','ram_available_gib',
 'pipeline_snapshot_age_s','pipeline_read_error','bank_persistence_read_error')
TERMS=('Batched inference request timed out','Batched inference failed','Client ',
 'Error receiving','partial','Traceback','Training error:','fallback','ExactInferenceGraphError')

def proc_identity():
 s=Path(f'/proc/{PID}/stat').read_text();tail=s[s.rfind(')')+2:].split()
 return dict(pid=PID,start_ticks=int(tail[19]),state=tail[0])

# Continue after the initial600s observer, avoiding duplicate API sampling.
not_before=datetime(2026,10,16,6,31,30,tzinfo=timezone.utc).timestamp()
while time.time()<not_before: time.sleep(min(1,not_before-time.time()))
start=time.monotonic(); identity=proc_identity(); last_errors=None
with OUT.open('x') as out:
 for index in range(901):
  tick=time.monotonic()
  row=dict(utc=datetime.now(timezone.utc).isoformat(),elapsed_s=tick-start,index=index)
  try:
   with urllib.request.urlopen(URL,timeout=2) as stream:x=json.load(stream)
   row.update({key:x.get(key) for key in GAUGES})
   row['host_pipeline']=x.get('host_pipeline',{})
   row['bank_persistence']=x.get('bank_persistence',{})
   text=(BASE/'console.log').read_text(errors='replace')
   row['console_counts']={key:text.count(key) for key in TERMS}
   row['deadline_lines']=sum('Batched inference request timed out' in line for line in text.splitlines())
   row['parse_error_lines']=[line[-240:] for line in text.splitlines() if ('error' in line.lower() or 'parse' in line.lower()) and not line.startswith('Starting')][-12:]
   if index%60==0:
    row['process_identity']=proc_identity()
    if row['process_identity']['start_ticks']!=identity['start_ticks']:raise RuntimeError('Trainer process identity changed')
   graph=row['host_pipeline'].get('inference_graphs',{})
   errors=(row['deadline_lines'],graph.get('fatal_error'),graph.get('fallback_count'),graph.get('runtime_capture_count'))
   if index%60==0 or errors!=last_errors:
    print(json.dumps(dict(utc=row['utc'],elapsed_s=row['elapsed_s'],frames=row.get('frame_count'),samples=row.get('optimized_samples'),fps=row.get('fps'),clients=row.get('client_count'),gpu=row.get('gpu1_util'),power=row.get('gpu1_power_w'),avg_inf=row.get('avg_inf_ms'),errors=errors,graph_replays=graph.get('replay_count'))),flush=True)
   last_errors=errors
  except Exception as exc:
   row['observation_error']=repr(exc)
   print(json.dumps(dict(elapsed_s=row['elapsed_s'],observation_error=repr(exc))),flush=True)
  out.write(json.dumps(row,separators=(',',':'))+'\n');out.flush()
  if index<900:time.sleep(max(0,1-(time.monotonic()-tick)))
print(json.dumps(dict(status='complete',path=str(OUT),elapsed_s=time.monotonic()-start)),flush=True)
