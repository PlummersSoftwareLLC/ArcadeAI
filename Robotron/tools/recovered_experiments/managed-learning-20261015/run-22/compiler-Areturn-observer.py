#!/usr/bin/env python3
"""Read-only fixed compiler-Areturn window observer; no training/control/model imports."""
import datetime,json,pathlib,time,urllib.request,os,subprocess,hashlib,csv
R=pathlib.Path(__file__).resolve().parents[3];D=pathlib.Path(__file__).resolve().parent
manifest_path=D/'actor192-all-connected.json'; manifest_raw=manifest_path.read_bytes();manifest=json.loads(manifest_raw);pid=1420536
assert manifest['trainer_pid']==pid and manifest['client_count']==192 and len(set(manifest['mame_pids']))==192
connected_ts=datetime.datetime.fromisoformat(manifest['utc']).timestamp();cutoff=connected_ts+90;anchor=None;end=None
pids=manifest['mame_pids']; console=D/'console.log'; offset=0; counts={x:0 for x in ['Batched inference request timed out','Batched inference failed','Error receiving','Traceback','Training error:','ExactInferenceGraphError','[WARN]']};idx=0;next_probe=0;last_bank=None;last_fault=None
outpath=D/'compiler-Areturn-observations.jsonl';log_offsets={};actor_log_counts={'[SOCKET ACTION TIMEOUT]':0};actor_log_events=[]
statpaths={'latest':R/'models_dqn/robotron_dqn_latest.pt','best':R/'models_dqn/robotron_dqn_best.pt','hof_selector':R/'models_dqn/robotron_dqn_latest_replay_hof/CURRENT.json','ephof_selector':R/'models_dqn/robotron_dqn_latest_replay_ephof/CURRENT.json'}
def file_info(path):
 try:
  q=path.stat();return {'mtime_ns':q.st_mtime_ns,'ctime_ns':q.st_ctime_ns,'size':q.st_size,'inode':q.st_ino}
 except OSError as e:return {'error':repr(e)}
with outpath.open('x') as stream:
 while True:
  began=time.monotonic();wall=time.time();cadence=1;row={'utc':datetime.datetime.fromtimestamp(wall,datetime.timezone.utc).isoformat(),'observer_unix_s':wall,'observer_monotonic_ns':time.monotonic_ns(),'index':idx,'trainer_pid':pid,'sampling_interval_s':cadence}
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
   for logfile in sorted(D.glob('*fleet*.log')):
    try:
     with logfile.open(errors='replace') as handle:handle.seek(log_offsets.get(str(logfile),0));lognew=handle.read();log_offsets[str(logfile)]=handle.tell()
     for marker in actor_log_counts:actor_log_counts[marker]+=lognew.count(marker)
     actor_log_events.extend([line for line in lognew.splitlines() if '[SOCKET ACTION TIMEOUT]' in line])
    except OSError as error:row['actor_log_read_error']=repr(error)
   row['actor_log_error_counts']=actor_log_counts.copy();row['actor_log_events']=actor_log_events[:];actor_log_events.clear()
   try:
    with (D/'training.csv').open() as handle:
     recent_csv=list(csv.DictReader(handle))
    row['CSV_replay_dropped_max']=max(float(x['replay_dropped']) for x in recent_csv) if recent_csv else None
   except Exception as error:row['CSV_read_error']=repr(error)
   next_probe=wall+5
   try:
    probe=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,process_name,used_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=3);row['nvidia_compute_apps']=probe.stdout.strip();row['nvidia_compute_returncode']=probe.returncode
   except Exception as e:row['nvidia_probe_error']=repr(e)
   row['private96_file_stats']={}
   for job in D.parent.glob('sidecar-gpu0-96M*'):
    if job.is_dir():row['private96_file_stats'][job.name]={'status_file':file_info(job/'status.json'),'receipt_file':file_info(job/'receipt.json')}
   try:row['host_cpu_pressure']=pathlib.Path('/proc/pressure/cpu').read_text();row['host_loadavg']=pathlib.Path('/proc/loadavg').read_text().strip();row['host_cpu_stat']=pathlib.Path('/proc/stat').read_text().splitlines()[0]
   except OSError as e:row['host_cpu_probe_error']=repr(e)
   try:row['io_pressure']=pathlib.Path('/proc/pressure/io').read_text();row['memory_writeback']={k:v.strip() for k,v in (line.split(':',1) for line in pathlib.Path('/proc/meminfo').read_text().splitlines()) if k in ['Dirty','Writeback','WritebackTmp','MemAvailable']}
   except OSError as e:row['pressure_error']=repr(e)
  row['actor_log_error_counts_cumulative']=actor_log_counts.copy()
  b=row.get('bank_persistence') or {};hp=row.get('host_pipeline') or {};native=hp.get('native_batch_update') or {};graphs=hp.get('inference_graphs') or {};output=b.get('output') or {}
  bank_signature=(b.get('capture_attempts'),b.get('writes'),b.get('writer_active'))
  fault={'console':{k:v for k,v in counts.items() if v},'bank_write_failures':b.get('write_failures',0),'bank_last_error':b.get('last_error'),'field_errors':sum(v.get('errors',0) for v in output.get('totals',{}).values()),'native_errors':native.get('error_count',0),'native_fallbacks':native.get('fallback_count',0),'graph_fatal':graphs.get('fatal_error'),'graph_runtime_capture':graphs.get('runtime_capture_count',0),'graph_fallback':graphs.get('fallback_count',0),'clients_bad':row.get('client_count') if row.get('client_count')!=192 else None,'pinned_bad':row['pinned_actors_alive'] if row['pinned_actors_alive']!=192 else None,'observer_error':row.get('observer_error'),'process_error':row.get('process_error'),'pipeline_read_error':row.get('pipeline_read_error'),'bank_read_error':row.get('bank_persistence_read_error'),'actor_timeouts':actor_log_counts['[SOCKET ACTION TIMEOUT]'],'actor_log_read_error':row.get('actor_log_read_error'),'CSV_dropped':row.get('CSV_replay_dropped_max'),'CSV_read_error':row.get('CSV_read_error')}
  if any(fault.values()) and fault!=last_fault:print(json.dumps({'ALERT':row['utc'],'fault':fault}),flush=True)
  if last_bank is not None and bank_signature!=last_bank:print(json.dumps({'BANK_CHANGE':row['utc'],'bank':bank_signature,'field_active':output.get('active'),'deadline_count':counts['Batched inference request timed out']}),flush=True)
  last_bank=bank_signature;last_fault=fault
  if anchor is None and wall>=cutoff:
   anchor=wall;end=anchor+180
   print(json.dumps({'PRIMARY_ANCHOR':row['utc'],'minimum_endpoint_unix_s':end,'settle_cutoff_unix_s':cutoff,'all_faults_retained':True}),flush=True)
  row['primary_started']=anchor is not None
  stream.write(json.dumps(row)+'\n');stream.flush()
  if idx==0:print(json.dumps({'started':row['utc'],'connected_utc':manifest['utc'],'settle_cutoff_utc':datetime.datetime.fromtimestamp(cutoff,datetime.timezone.utc).isoformat(),'path':str(outpath)}),flush=True)
  if end is not None and wall>=end:break
  idx+=1;time.sleep(max(0,cadence-(time.monotonic()-began)))
(D/'compiler-Areturn-observer-complete.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':idx+1,'complete':True,'connected_utc':manifest['utc'],'manifest_sha256':hashlib.sha256(manifest_raw).hexdigest(),'settle_cutoff_unix_s':cutoff,'actual_primary_start_unix_s':anchor,'first180s_end_unix_s':wall},indent=2))
