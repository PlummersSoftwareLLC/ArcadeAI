#!/usr/bin/env python3
"""Read-only fixed exposure-health window observer; no training/control/model imports."""
import datetime,json,pathlib,time,urllib.request,os,subprocess,hashlib,csv,math
from exposure_health_checks import snapshot_errors
R=pathlib.Path(__file__).resolve().parents[3];D=pathlib.Path(__file__).resolve().parent
manifest_path=D/'actor192-all-connected.json'; manifest_raw=manifest_path.read_bytes();manifest=json.loads(manifest_raw);pid=1436155
assert manifest['trainer_pid']==pid and manifest['client_count']==192 and len(set(manifest['mame_pids']))==192
hard_end=datetime.datetime(2026,10,16,12,8,tzinfo=datetime.timezone.utc).timestamp();coast_end=datetime.datetime(2026,10,16,12,tzinfo=datetime.timezone.utc).timestamp();pair_complete_ts=None;base_writes=None;base_captures=None
pids=manifest['mame_pids']; console=D/'console.log'; offset=0; counts={x:0 for x in ['Batched inference request timed out','Batched inference failed','Error receiving','Traceback','Training error:','ExactInferenceGraphError','[WARN]']};idx=0;next_probe=0;last_bank=None;last_fault=None
outpath=D/'natural-bank-exposure-observations.jsonl';log_offsets={};actor_log_counts={'[SOCKET ACTION TIMEOUT]':0};actor_log_events=[];previous_exposure=None;previous_exposure_utc=None
statpaths={'latest':R/'models_dqn/robotron_dqn_latest.pt','best':R/'models_dqn/robotron_dqn_best.pt','hof_selector':R/'models_dqn/robotron_dqn_latest_replay_hof/CURRENT.json','ephof_selector':R/'models_dqn/robotron_dqn_latest_replay_ephof/CURRENT.json'}
def file_info(path):
 try:
  q=path.stat();return {'mtime_ns':q.st_mtime_ns,'ctime_ns':q.st_ctime_ns,'size':q.st_size,'inode':q.st_ino}
 except OSError as e:return {'error':repr(e)}
ramp=json.loads((D/'startup-independent-ramp-audit.json').read_text());transport={};transport_initial=[];markers=['[SOCKET ACTION TIMEOUT]','[SOCKET RECV ERROR]','[SOCKET SEND ERROR]']
for actor in ramp['all192_actor_logs']:
 path=pathlib.Path(actor['path']);raw=path.read_bytes();complete=raw[:raw.rfind(b'\n')+1];segment=complete[actor['current_PID_segment_byte_offset']:];state=dict(pid=actor['pid'],slot=actor['slot'],path=str(path),offset=len(complete),initial_offset=len(complete),inode=path.stat().st_ino,hasher=hashlib.sha256(segment),counts={m:segment.count(m.encode()) for m in markers},segment_start=actor['current_PID_segment_byte_offset'],prior_reviewed_complete_prefix_sha256=actor['complete_prefix_sha256'])
 transport[actor['pid']]=state;transport_initial.append({k:v for k,v in state.items() if k!='hasher'}|{'current_PID_segment_sha256':state['hasher'].hexdigest()})
(D/'natural-bank-exposure-transport-start.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'actors':transport_initial,'scope':'CurrentPIDsegments and complete log-prefix lengths/inodes; inherited historical reviewed prefix hash is provenance, not rehashed during this observer.'},indent=2)+'\n')
def transport_probe():
 totals={m:0 for m in markers};changes=[];errors=[]
 for state in transport.values():
  path=pathlib.Path(state['path'])
  try:
   q=path.stat()
   if q.st_ino!=state['inode'] or q.st_size<state['offset']:raise RuntimeError('log rotated or truncated')
   with path.open('rb') as handle:handle.seek(state['offset']);raw=handle.read()
   raw=raw[:raw.rfind(b'\n')+1]
   if raw:
    state['offset']+=len(raw);state['hasher'].update(raw)
    for m in markers:state['counts'][m]+=raw.count(m.encode())
    changes.append({'pid':state['pid'],'slot':state['slot'],'complete_prefix_bytes':state['offset'],'new_current_segment_bytes':len(raw),'new_error_lines':[line.decode(errors='replace') for line in raw.splitlines() if any(m.encode() in line for m in markers)]})
   stat=pathlib.Path(f"/proc/{state['pid']}/stat").read_text().split(') ',1)[1].split();expected=next(a['start_ticks'] for a in manifest['actors'] if a['pid']==state['pid'])
   if int(stat[19])!=expected:raise RuntimeError('actor PID/startticks changed')
  except Exception as error:errors.append({'pid':state['pid'],'error':repr(error)})
  for m in markers:totals[m]+=state['counts'][m]
 return totals,changes,errors
with outpath.open('x') as stream:
 while True:
  began=time.monotonic();wall=time.time();cadence=5 if wall<coast_end else 1;row={'utc':datetime.datetime.fromtimestamp(wall,datetime.timezone.utc).isoformat(),'observer_unix_s':wall,'observer_monotonic_ns':time.monotonic_ns(),'index':idx,'trainer_pid':pid,'sampling_interval_s':cadence}
  try:
   with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as f:a=json.load(f)
   for k in ['ts','host_pipeline','bank_persistence','pipeline_snapshot_age_s','pipeline_read_error','bank_persistence_read_error','frame_count','learner_frame_count','measurement_frames','optimized_samples','training_steps','client_count','epsilon','expert_ratio','lr','fps','steps_per_sec','rpl_per_frame','train_sample_ms','train_transfer_ms','train_compute_ms','train_priority_ms','train_step_ms','avg_inf_ms','loss','grad_norm','training_enabled','measurement_active','gpus','gpu1_util','gpu1_power_w','memory_buffer_size']:row[k]=a.get(k)
  except Exception as e:row['observer_error']=repr(e)
  try:
   t=pathlib.Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split();row['process_stat']={'utime_ticks':int(t[11]),'stime_ticks':int(t[12]),'threads':int(t[17]),'start_ticks':int(t[19]),'rss_pages':int(t[21]),'clock_ticks_per_s':os.sysconf('SC_CLK_TCK'),'page_bytes':os.sysconf('SC_PAGE_SIZE')};row['process_io']={k:int(v) for k,v in (line.split(':',1) for line in pathlib.Path(f'/proc/{pid}/io').read_text().splitlines())}
  except Exception as e:row['process_error']=repr(e)
  with console.open(errors='replace') as f:f.seek(offset);new=f.read();offset=f.tell()
  for x in counts:counts[x]+=new.count(x)
  row['console_error_counts']=counts.copy();row['console_new_events']=[x for x in new.splitlines() if any(y in x for y in ['[BANK','Saved','Saving','checkpoint','Error','timed out','failed','[WARN]'])]
  row['file_stats']={k:file_info(v) for k,v in statpaths.items()};row['pinned_actors_alive']=sum(pathlib.Path(f'/proc/{p}').exists() for p in pids)
  if wall>=next_probe:
   actor_log_counts,transport_changes,transport_errors=transport_probe();row['actor_log_error_counts']=actor_log_counts.copy();row['transport_prefix_changes']=transport_changes;row['transport_probe_errors']=transport_errors
   try:
    with (D/'training.csv').open() as handle:
     recent_csv=list(csv.DictReader(handle))
    row['CSV_replay_dropped_max']=max(float(x['replay_dropped']) for x in recent_csv) if recent_csv else None
   except Exception as error:row['CSV_read_error']=repr(error)
   next_probe=wall+5
   try:
    probe=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,process_name,used_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=3);row['nvidia_compute_apps']=probe.stdout.strip();row['nvidia_compute_returncode']=probe.returncode
   except Exception as e:row['nvidia_probe_error']=repr(e)
   try:row['host_cpu_pressure']=pathlib.Path('/proc/pressure/cpu').read_text();row['host_loadavg']=pathlib.Path('/proc/loadavg').read_text().strip();row['host_cpu_stat']=pathlib.Path('/proc/stat').read_text().splitlines()[0]
   except OSError as e:row['host_cpu_probe_error']=repr(e)
   try:row['io_pressure']=pathlib.Path('/proc/pressure/io').read_text();row['memory_writeback']={k:v.strip() for k,v in (line.split(':',1) for line in pathlib.Path('/proc/meminfo').read_text().splitlines()) if k in ['Dirty','Writeback','WritebackTmp','MemAvailable']}
   except OSError as e:row['pressure_error']=repr(e)
  row['actor_log_error_counts_cumulative']=actor_log_counts.copy()
  b=row.get('bank_persistence') or {};hp=row.get('host_pipeline') or {};native=hp.get('native_batch_update') or {};graphs=hp.get('inference_graphs') or {};output=b.get('output') or {}
  exposure=hp.get('learning_exposure') or {};exposure_errors=snapshot_errors(exposure,previous_exposure,pid);row['exposure_validation_errors']=exposure_errors
  if previous_exposure and not exposure_errors:
   skipped=exposure['optimizer']['total']['amp_skipped']-previous_exposure['optimizer']['total']['amp_skipped']
   if skipped:print(json.dumps({'AMP_SKIP_OBSERVED':row['utc'],'previous_observation_utc':previous_exposure_utc,'increment':skipped,'causality':'Counter bracket only, not aligned atomically to model clocks/gradient diagnostics.'}),flush=True)
  if row.get('grad_norm') is not None and not math.isfinite(row['grad_norm']):print(json.dumps({'NONFINITE_GRAD_DIAGNOSTIC':row['utc'],'grad_norm':str(row['grad_norm']),'scope':'Retained diagnostic, not automatically a telemetry failure or per-row AMP classification.'}),flush=True)
  previous_exposure=exposure;previous_exposure_utc=row['utc']
  bank_signature=(b.get('capture_attempts'),b.get('writes'),b.get('writer_active'))
  fault={'console':{k:v for k,v in counts.items() if v},'bank_write_failures':b.get('write_failures',0),'bank_last_error':b.get('last_error'),'field_errors':sum(v.get('errors',0) for v in output.get('totals',{}).values()),'native_errors':native.get('error_count',0),'native_fallbacks':native.get('fallback_count',0),'graph_fatal':graphs.get('fatal_error'),'graph_runtime_capture':graphs.get('runtime_capture_count',0),'graph_fallback':graphs.get('fallback_count',0),'clients_bad':row.get('client_count') if row.get('client_count')!=192 else None,'pinned_bad':row['pinned_actors_alive'] if row['pinned_actors_alive']!=192 else None,'observer_error':row.get('observer_error'),'process_error':row.get('process_error'),'pipeline_read_error':row.get('pipeline_read_error'),'bank_read_error':row.get('bank_persistence_read_error'),'actor_errors':sum(actor_log_counts.values()),'transport_probe_errors':row.get('transport_probe_errors'),'actor_log_read_error':row.get('actor_log_read_error'),'CSV_dropped':row.get('CSV_replay_dropped_max'),'CSV_read_error':row.get('CSV_read_error'),'exposure_errors':exposure_errors,'nonfinite_loss':row.get('loss') is not None and not math.isfinite(row['loss'])}
  if any(fault.values()) and fault!=last_fault:print(json.dumps({'ALERT':row['utc'],'fault':fault}),flush=True)
  if last_bank is not None and bank_signature!=last_bank:print(json.dumps({'BANK_CHANGE':row['utc'],'bank':bank_signature,'field_active':output.get('active'),'deadline_count':counts['Batched inference request timed out']}),flush=True)
  last_bank=bank_signature;last_fault=fault
  if base_writes is None:base_writes=b.get('writes');base_captures=b.get('capture_attempts')
  if pair_complete_ts is None and b.get('writes',0)>=base_writes+2 and not b.get('writer_active',True):
   pair_complete_ts=wall;print(json.dumps({'PAIR_COMPLETE':row['utc'],'minimum_recovery_s':135,'fixed_deadline_utc':'2026-10-16T12:08:00Z'}),flush=True)
  row['new_writes_since_observer_start']=b.get('writes',0)-base_writes;row['pair_complete_first_observed_unix_s']=pair_complete_ts;row['pair_recovery_elapsed_s']=wall-pair_complete_ts if pair_complete_ts is not None else None
  stream.write(json.dumps(row)+'\n');stream.flush()
  if idx==0:print(json.dumps({'started':row['utc'],'cadence':'5s until12:00 then1Hz','end_rule':'pair+135srecovery or fixed12:08deadline','path':str(outpath)}),flush=True)
  if wall>=hard_end or (pair_complete_ts is not None and wall-pair_complete_ts>=135):break
  idx+=1;time.sleep(max(0,cadence-(time.monotonic()-began)))
transport_final=[{k:v for k,v in state.items() if k!='hasher'}|{'current_PID_segment_sha256':state['hasher'].hexdigest()} for state in transport.values()]
(D/'natural-bank-exposure-transport-end.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'actors':transport_final},indent=2)+'\n')
(D/'natural-bank-exposure-observer-complete.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':idx+1,'complete':True,'manifest_sha256':hashlib.sha256(manifest_raw).hexdigest(),'baseline_captures':base_captures,'baseline_writes':base_writes,'pair_complete_observed_unix_s':pair_complete_ts,'endpoint_unix_s':wall,'recovery_s':wall-pair_complete_ts if pair_complete_ts is not None else None,'fixed_deadline_unix_s':hard_end,'stop_reason':'pair_and_135s_recovery' if pair_complete_ts is not None and wall-pair_complete_ts>=135 else 'fixed_deadline'},indent=2)+'\n')
