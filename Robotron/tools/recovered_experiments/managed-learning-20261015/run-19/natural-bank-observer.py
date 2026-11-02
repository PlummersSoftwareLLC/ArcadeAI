#!/usr/bin/env python3
"""Read-only bounded 1Hz natural bank event observation; standard library only."""
import datetime,json,pathlib,time,urllib.request,os
R=pathlib.Path(__file__).resolve().parents[3];D=pathlib.Path(__file__).resolve().parent
# R is Robotron: run-19 -> campaign -> logs -> Robotron.
pid=1131555;end=datetime.datetime(2026,10,16,9,24,tzinfo=datetime.timezone.utc).timestamp();outpath=D/'natural-bank-observations.jsonl'
manifest=json.loads((D/'actor192-all-connected.json').read_text());pids=manifest['mame_pids']; console=D/'console.log'; offset=0; counts={x:0 for x in ['Batched inference request timed out','Batched inference failed','Error receiving','Traceback','Training error:','ExactInferenceGraphError','[WARN]']};idx=0
statpaths={'latest':R/'models_dqn/robotron_dqn_latest.pt','best':R/'models_dqn/robotron_dqn_best.pt','hof_selector':R/'models_dqn/robotron_dqn_latest_replay_hof/CURRENT.json','ephof_selector':R/'models_dqn/robotron_dqn_latest_replay_ephof/CURRENT.json'}
def file_info(path):
 try:
  q=path.stat();return {'mtime_ns':q.st_mtime_ns,'ctime_ns':q.st_ctime_ns,'size':q.st_size,'inode':q.st_ino}
 except OSError as e:return {'error':repr(e)}
with outpath.open('x') as stream:
 while True:
  began=time.monotonic();wall=time.time();row={'utc':datetime.datetime.fromtimestamp(wall,datetime.timezone.utc).isoformat(),'observer_unix_s':wall,'observer_monotonic_ns':time.monotonic_ns(),'index':idx,'trainer_pid':pid}
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
  if idx%5==0:
   try:row['io_pressure']=pathlib.Path('/proc/pressure/io').read_text();row['memory_writeback']={k:v.strip() for k,v in (line.split(':',1) for line in pathlib.Path('/proc/meminfo').read_text().splitlines()) if k in ['Dirty','Writeback','WritebackTmp','MemAvailable']}
   except OSError as e:row['pressure_error']=repr(e)
  stream.write(json.dumps(row)+'\n');stream.flush()
  if idx==0:print(json.dumps({'started':row['utc'],'end_utc':'2026-10-16T09:24:00Z','path':str(outpath)}),flush=True)
  if wall>=end:break
  idx+=1;time.sleep(max(0,1-(time.monotonic()-began)))
(D/'natural-bank-observer-complete.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':idx+1,'complete':True},indent=2))
