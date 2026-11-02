"""Root-authorized1Hz160M health-only watch: never inspect game/score/stat fields."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,re,time,urllib.request
BASE=Path(__file__).resolve().parent;CAMPAIGN=BASE.parent
JOB=CAMPAIGN/'sidecar-gpu0-160M-regression-guard-01';RUNNER=1756977;MAIN=1436155;SUP=1438661
OUTPUT=BASE/'quality160M-guard01-scoreblind-health.jsonl';COMPLETE=BASE/'quality160M-guard01-scoreblind-health-complete.json'
EXPECTED_SLOTS=set(range(4096,4112));START=time.time();TICK=time.monotonic()
GAME=CAMPAIGN.parents[1];CONTROL=GAME/'models_dqn/learning_control.json'
SOURCE_ATTESTATION=json.loads((BASE/'startup-independent-process-source-observation.json').read_bytes())
SOURCE_EXPECTED={str(GAME.parent/name):value for name,value in SOURCE_ATTESTATION['source_hashes'].items()}
SOURCE_EXPECTED.update({str(GAME/name):value for name,value in SOURCE_ATTESTATION['private12_hashes'].items()})
MAIN_ACTOR_PIN=json.loads((BASE/'actor192-all-connected.json').read_bytes())['actors']
owned_private_identity={};final_first_seen=None
CONTROL_EXPECTED=hashlib.sha256(CONTROL.read_bytes()).hexdigest();last_guard_check=-1;source_control_guard=None
def utc():return datetime.now(timezone.utc).isoformat()
def process(pid):
 try:
  p=Path('/proc',str(pid));s=p.joinpath('stat').read_text().rsplit(')',1)[1].split()
  return dict(alive=s[0] not in ['Z','X'],present=True,start_ticks=int(s[19]))
 except (OSError,IndexError):return dict(alive=False,present=False,start_ticks=None)
def select_status(document,final=False):
 out={key:document.get(key) for key in ['label','phase','active','complete','valid','reason','error']}
 if not final:
  boundary=document.get('boundary',{})
  out['boundary']={key:boundary.get(key) for key in ['ready','generation','clients','actor_slots']}
  out['actor_pids']={int(slot):int(pid) for slot,pid in document.get('actor_pids',{}).items()}
 else:
  out.update({key:document.get(key) for key in ['server_error','inference_error','cleanup_errors','invalidity_reasons','timeout_snapshot_unix_s']})
  out['runtime_action_timeouts']=sum(document.get('actor_timeout_logs',{}).values())
  out['cleanup_only_action_timeouts']=sum(document.get('actor_cleanup_timeout_logs',{}).values())
 return out
logs=[BASE/'console.log',BASE/'sidecar-gpu0-160M-regression-guard-01.log'];offsets={str(p):(p.stat().st_size if p==BASE/'console.log' else 0) for p in logs}
patterns=['Training error:','Traceback (most recent call last):','Batched inference request timed out','Batched inference failed','disabling torch.compile','torch.compile unavailable','Non-finite loss']
counts={str(path):dict.fromkeys(patterns,0) for path in logs};actor_identity={};issues_seen={};last_notified=set();rows=0;status_seen=False
main_start=process(MAIN)['start_ticks'];runner_start=process(RUNNER)['start_ticks'];final_health=None
with OUTPUT.open('x') as output:
 while time.monotonic()-TICK<1800:
  row=dict(utc=utc(),ts=time.time(),runner=process(RUNNER),main=process(MAIN),main_supervisor=process(SUP));issues=[]
  # Ownership metadata only: no args, model maps, GPU calls or game fields.
  pending_owners=[RUNNER];seen_owners=set()
  while pending_owners:
   pid=pending_owners.pop()
   if pid in seen_owners:continue
   seen_owners.add(pid);observed=process(pid)
   if observed['present'] and pid not in owned_private_identity:owned_private_identity[pid]=observed['start_ticks']
   try:pending_owners.extend(map(int,Path('/proc',str(pid),'task',str(pid),'children').read_text().split()))
   except OSError:pass
  row['owned_private_processes_remaining']=[pid for pid,start_ticks in owned_private_identity.items() if (lambda observed: observed['present'] and observed['start_ticks']==start_ticks)(process(pid))]
  if rows-last_guard_check>=30 or source_control_guard is None:
   current={name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in SOURCE_EXPECTED}
   main_actor_mismatch=[v['pid'] for v in MAIN_ACTOR_PIN if (lambda observed: not observed['alive'] or observed['start_ticks']!=v['start_ticks'])(process(v['pid']))]
   source_control_guard=dict(utc=row['utc'],source20_private12_unchanged=current==SOURCE_EXPECTED,main_actors_matched=192-len(main_actor_mismatch),main_actor_mismatched_pids=main_actor_mismatch,control_sha256=hashlib.sha256(CONTROL.read_bytes()).hexdigest())
   last_guard_check=rows
  row['source_control_guard']=dict(source_control_guard)
  if not source_control_guard['source20_private12_unchanged'] or source_control_guard['control_sha256']!=CONTROL_EXPECTED:issues.append('source20_private12_or_main_control_changed')
  if source_control_guard['main_actor_mismatched_pids']:issues.append('main_pinned_actor_identity_changed')
  status_path=JOB/'status.json';receipt_path=JOB/'receipt.json';final=receipt_path.exists()
  try:
   if final:
    document=json.loads(receipt_path.read_bytes());row['private']=select_status(document,True);final_health=row['private']
    if final_first_seen is None:final_first_seen=time.time()
   elif status_path.exists():
    document=json.loads(status_path.read_bytes());row['private']=select_status(document);status_seen=True
    phase=row['private']['phase'];pids=row['private']['actor_pids'];boundary=row['private']['boundary']
    if phase not in ['warming','complete','finished','restore_failed']:
     if not boundary.get('ready') or boundary.get('clients')!=16 or set(boundary.get('actor_slots') or [])!=EXPECTED_SLOTS:issues.append('private_boundary_not_ready_after_admission')
    if pids:
     live={slot:process(pid) for slot,pid in pids.items()};row['owned_private_processes']=live
     if not actor_identity and set(pids)==EXPECTED_SLOTS and all(v['alive'] for v in live.values()):actor_identity={slot:dict(pid=pids[slot],start_ticks=live[slot]['start_ticks']) for slot in pids}
     if phase not in ['complete','finished','restore_failed'] and actor_identity:
      if set(pids)!=EXPECTED_SLOTS or any(not live.get(slot,{}).get('alive') or pids.get(slot)!=identity['pid'] or live[slot]['start_ticks']!=identity['start_ticks'] for slot,identity in actor_identity.items()):issues.append('owned_private_actor_identity_or_liveness_changed')
   elif time.time()-START>90:issues.append('private_status_missing_after90s')
  except (OSError,ValueError,TypeError,KeyError) as error:row['status_read_error']=f'{type(error).__name__}: {error}';issues.append('private_status_read_error')
  private=row.get('private',{})
  if private.get('valid') is False or private.get('error') or private.get('server_error') or private.get('inference_error'):issues.append('private_invalid_or_runtime_error')
  if not row['runner']['alive'] and not final:issues.append('runner_ended_before_final_receipt')
  if row['runner']['alive'] and row['runner']['start_ticks']!=runner_start:issues.append('runner_PID_identity_changed')
  if not row['main']['alive'] or row['main']['start_ticks']!=main_start or not row['main_supervisor']['alive']:issues.append('main_owner_process_not_preserved')
  try:
   api=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=2));h=api['host_pipeline'];g=h['inference_graphs'];n=h['native_batch_update'];e=h['learning_exposure']
   row['main_health']=dict(API_ts=api['ts'],clocks={k:api[k] for k in ['training_steps','optimized_samples','learner_frame_count','frame_count','measurement_frames']},client_count=api['client_count'],pipeline_read_error=api['pipeline_read_error'],bank_persistence_read_error=api['bank_persistence_read_error'],graphs={k:g[k] for k in ['ready','capture_count','runtime_capture_count','fallback_count','fatal_error']},native={k:n[k] for k in ['enabled','available','success_count','fallback_count','error_count']},optimizer={k:e['optimizer'][k] for k in ['process_id','epoch','available','unclassified_started_total']},optimizer_unavailable=e['optimizer']['total']['unavailable'],replay_epoch=e['replay']['epoch'])
   bank=api['bank_persistence'];output_phase=bank['output']
   row['main_bank_health']={key:bank.get(key) for key in ['capture_attempts','capture_deferrals','writes','write_failures','writer_active','last_error']}
   row['main_bank_health'].update(output_backend=output_phase.get('backend'),output_active=output_phase.get('active'),phase_counts={name:{key:values.get(key) for key in ['count','errors']} for name,values in output_phase.get('totals',{}).items()})
   if bank.get('write_failures') or bank.get('last_error') or any(values.get('errors') for values in output_phase.get('totals',{}).values()):issues.append('main_bank_persistence_error')
   if api['client_count']!=192:issues.append('main_client_count_not192')
   if api['pipeline_read_error'] or api['bank_persistence_read_error']:issues.append('main_API_metadata_read_error')
   if not g['ready'] or g['capture_count']!=128 or g['runtime_capture_count'] or g['fallback_count'] or g['fatal_error']:issues.append('main_graph_route_error')
   if not n['enabled'] or not n['available'] or n['fallback_count'] or n['error_count']:issues.append('main_native_route_error')
   if e['optimizer']['total']['unavailable'] or e['optimizer']['unclassified_started_total'] not in (0,1):issues.append('main_optimizer_telemetry_unknown')
  except (OSError,ValueError,KeyError,TypeError) as error:row['main_API_error']=f'{type(error).__name__}: {error}';issues.append('main_API_read_failed')
  for path in logs:
   try:
    with path.open('rb') as log:
     log.seek(offsets[str(path)]);raw=log.read();offsets[str(path)]+=len(raw)
    # Diagnostics counts only; never retain score-bearing output lines.
    for pattern in patterns:counts[str(path)][pattern]+=raw.count(pattern.encode())
   except OSError as error:row.setdefault('log_read_errors',{})[str(path)]=type(error).__name__
  row['runtime_log_pattern_counts']=counts.copy()
  if any(any(values.values()) for values in counts.values()):issues.append('new_main_or_private_runtime_error_log')
  row['issues']=sorted(set(issues));rows+=1
  for issue in row['issues']:issues_seen[issue]=issues_seen.get(issue,0)+1
  persistent={issue for issue in row['issues'] if issues_seen[issue]>=3 or issue in ['private_invalid_or_runtime_error','main_graph_route_error','main_native_route_error','new_main_or_private_runtime_error_log']}
  if persistent-last_notified:print(json.dumps(dict(alert_utc=row['utc'],health_issues=sorted(persistent-last_notified))),flush=True);last_notified|=persistent
  output.write(json.dumps(row,allow_nan=False)+'\n');output.flush()
  if final and not row['owned_private_processes_remaining']:break
  time.sleep(max(0,START+rows-time.time()))
report=dict(schema='robotron-160M-guard01-scoreblind-health-v1',started_unix_s=START,finished_utc=utc(),elapsed_s=time.monotonic()-TICK,pid=os.getpid(),runner_pid=RUNNER,main_pid=MAIN,rows=rows,status_seen=status_seen,final_health=final_health,issues=issues_seen,actor_identity=actor_identity,owned_private_identity=owned_private_identity,final_first_seen_unix_s=final_first_seen,final_owned_processes_remaining=row.get('owned_private_processes_remaining'),log_byte_offsets=offsets,scope='Whitelisted operational health/ownership only; no game counts, rows, scores, means, medians, quantiles, quality decisions, GPU/model loads, or process/control/source writes.',known_auxiliary_overlap='Rootqueuedfuturegate controlwatchers are lightweight polling only. Main naturalbank metadata is captured explicitly; no forced save/restarts. Previous main-only5scoastwatch ended14:12:49.569432UTC before this private watch. Any other bounded auxiliary work separately disclosed.')
with COMPLETE.open('x') as out:json.dump(report,out,indent=2);out.write('\n')
print(json.dumps(dict(complete_utc=report['finished_utc'],rows=rows,final_health=final_health,issues=issues_seen)),flush=True)
