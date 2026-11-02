#!/usr/bin/env python3
"""Summarize only the completed main-only coast bytes; no API/model/private reads."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import csv,hashlib,io,json,math,os,statistics,time

RUN=Path(__file__).resolve().parent
started=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
evidence=[]
def sha_bytes(raw):return hashlib.sha256(raw).hexdigest()
def read_json(path):
    path=Path(path);raw=path.read_bytes();evidence.append(dict(path=str(path),sha256=sha_bytes(raw),bytes=len(raw)))
    return json.loads(raw)
def numeric(value):
    try:return float(value)
    except (ValueError,TypeError):return float('nan')
def iso_seconds(text):return datetime.fromisoformat(text).timestamp()
def span_stats(values):return dict(minimum=min(values),maximum=max(values),mean=statistics.mean(values))
def exclusive_json(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as stream:stream.write(raw)
    return dict(path=str(path),sha256=sha_bytes(raw),bytes=len(raw))

complete=read_json(RUN/'main-coast-to160-complete.json')
startup=read_json(RUN/'main-coast-to160-startup.json')
raw_path=RUN/'main-coast-to160-health.jsonl';raw=raw_path.read_bytes()
evidence.append(dict(path=str(raw_path),sha256=sha_bytes(raw),bytes=len(raw),complete_line_prefix_bytes=len(raw) if raw.endswith(b'\n') else raw.rfind(b'\n')+1))
rows=[];parse_errors=[]
for index,line in enumerate(raw.splitlines(),1):
    try:rows.append(json.loads(line))
    except (ValueError,UnicodeError) as error:parse_errors.append(dict(line=index,error=str(error)))
if not rows:raise ValueError('No original observation rows')
first,last=rows[0],rows[-1]
watcher=RUN/'watch_main_coast_to160.py';watcher_raw=watcher.read_bytes()
evidence.append(dict(path=str(watcher),sha256=sha_bytes(watcher_raw),bytes=len(watcher_raw)))
actor_pin=read_json(complete['actor_pin_path'])
actor_rows=actor_pin['actors'];actor_identities=[(r['pid'],r['start_ticks']) for r in actor_rows]
checks={}
def check(name,value):checks[name]=bool(value)
check('completed_original821_rows_no_parse_or_partial_loss',len(rows)==complete['rows']==821 and not parse_errors and raw.endswith(b'\n'))
check('startup_source_matches_executed_watcher',startup['script_sha256']==sha_bytes(watcher_raw))
check('fixed_original_first_and_last_rows',first['utc']=='2026-10-16T13:04:29.562894+00:00' and last['utc']=='2026-10-16T14:12:49.562874+00:00' and startup['first_row_utc']==first['utc'])
monotonic_deltas=[b['monotonic_s']-a['monotonic_s'] for a,b in zip(rows,rows[1:])]
recorded_gaps=[dict(previous_utc=a['utc'],current_utc=b['utc'],elapsed_s=b['monotonic_s']-a['monotonic_s']) for a,b in zip(rows,rows[1:]) if b['monotonic_s']-a['monotonic_s']>7.5]
check('no_observed_poll_gap_or_time_reversal',not recorded_gaps and all(x>0 for x in monotonic_deltas) and not complete['gaps'] and math.isclose(max(monotonic_deltas),complete['largest_poll_gap_s'],rel_tol=1e-12))
issue_counts=Counter(issue for row in rows for issue in row.get('issues',[]));notice_counts=Counter(notice for row in rows for notice in row.get('notices',[]))
check('reported_issue_and_notice_tallies_match_complete',dict(issue_counts)==complete['issues'] and dict(notice_counts)==complete['notices'])
check('no_reported_coast_issues',not issue_counts)
check('all_rows_have_health_and_no_read_errors',all('health' in row and not row.get('API_error') and not row.get('append_read_error') for row in rows))
expected_owners=first['owners']
check('main_and_supervisor_identity_continuous',all(row['owners']==expected_owners for row in rows) and all(x['alive'] is True for x in expected_owners.values()) and expected_owners[str(complete['main_pid'])]['start_ticks']==complete['expected_main_start_ticks'] and expected_owners==startup['owners'])
check('all192_original_actor_PIN_pairs_unique',len(actor_identities)==len(set(actor_identities))==192 and len({p for p,t in actor_identities})==192)
check('all192_original_actors_matched_each5s_poll',all(row['actor_pin']==dict(expected=192,matched=192,mismatched_pids=[]) for row in rows))
check('all192_clients_and_training_enabled',all(row['health']['clients']==192 and row['health']['training_enabled'] is True for row in rows))
guards={row['source_control_guard']['utc']:row['source_control_guard'] for row in rows};guard_values=list(guards.values())
control_shas={x['control_sha256'] for x in guard_values}
check('all_recorded_source_stats_and_control_byte_guards_stable',all(x['source_stat_identity_unchanged'] is True and not x['changed_sources'] for x in guard_values) and len(control_shas)==1 and len(complete['expected_source_stats'])==len(complete['source_hash_attestation'])==20)
guard_ages=[iso_seconds(row['utc'])-iso_seconds(row['source_control_guard']['utc']) for row in rows]
guard_intervals=[iso_seconds(b['utc'])-iso_seconds(a['utc']) for a,b in zip(guard_values,guard_values[1:])]
health=[r['health'] for r in rows];clocks=[h['clocks'] for h in health]
clock_keys=list(clocks[0]);clock_changes={k:clocks[-1][k]-clocks[0][k] for k in clock_keys}
check('all_recorded_clocks_monotone',all(b[k]>=a[k] for a,b in zip(clocks,clocks[1:]) for k in clock_keys))
check('measurement_clock_constant',len({c['measurement_frames'] for c in clocks})==1)
epochs=health[0]['epoch_identity'];check('optimizer_and_replay_epoch_identities_constant',all(h['epoch_identity']==epochs for h in health))
optimizer=[h['optimizer_totals'] for h in health];optimizer_keys=list(optimizer[0])
check('all_optimizer_outcome_partitions_and_pending_valid',all(o['outcomes_recorded']==o['applied']+o['amp_skipped']+o['unavailable'] and o['attempts_started']==o['outcomes_recorded']+h['optimizer_pending'] and h['optimizer_pending'] in (0,1) and o['unavailable']==0 and h['optimizer_available']==(h['optimizer_pending']==0) for h,o in zip(health,optimizer)))
check('all_optimizer_totals_and_accepted_learner_monotone',all(b[k]>=a[k] for a,b in zip(optimizer,optimizer[1:]) for k in optimizer_keys) and all(b['accepted_learner']>=a['accepted_learner'] for a,b in zip(health,health[1:])))
optimizer_delta={k:optimizer[-1][k]-optimizer[0][k] for k in optimizer_keys}
skips=[]
for index,(left,right) in enumerate(zip(rows,rows[1:]),1):
    before_o=left['health']['optimizer_totals'];after_o=right['health']['optimizer_totals'];delta=after_o['amp_skipped']-before_o['amp_skipped']
    if delta:skips.append(dict(previous_row=index-1,row=index,previous_utc=left['utc'],current_utc=right['utc'],amp_skip_delta=delta,previous_totals=before_o,current_totals=after_o,previous_pending=left['health']['optimizer_pending'],current_pending=right['health']['optimizer_pending']))
check('recognized_skip_notices_match_exact_recorded_deltas',sum(x['amp_skip_delta'] for x in skips)==optimizer_delta['amp_skipped']==34 and len(skips)==notice_counts.get('recognized_AMP_skip_delta',0))
check('graph_route_ready_no_runtime_capture_fallback_or_fatal',all(h['graph']==dict(ready=True,capture_count=128,runtime_capture_count=0,fallback_count=0,fatal_error=None) for h in health))
check('native_route_successes_monotone_no_error_or_fallback',all(h['native']['enabled'] is True and h['native']['available'] is True and h['native']['fallback_count']==h['native']['error_count']==0 for h in health) and all(b['native']['success_count']>=a['native']['success_count'] for a,b in zip(health,health[1:])))
api_nonfinite_loss=[dict(row=i,utc=r['utc'],loss=r['health']['loss']) for i,r in enumerate(rows) if not math.isfinite(numeric(r['health']['loss']))]
api_nonfinite_grad=[dict(row=i,utc=r['utc'],grad_norm=r['health']['grad_norm'],loss=r['health']['loss'],clocks=r['health']['clocks']) for i,r in enumerate(rows) if not math.isfinite(numeric(r['health']['grad_norm']))]
check('no_sampled_API_nonfinite_loss',not api_nonfinite_loss)
api_ages=[r['ts']-r['health']['API_ts'] for r in rows]
api_intervals=[b['API_ts']-a['API_ts'] for a,b in zip(health,health[1:])]
check('API_timestamps_monotone',all(x>0 for x in api_intervals))
# Bound mutable main append logs at the exact frozen offsets, never read later data.
prefix_records=[];segments={};frozen_prefixes={}
for key,name in (('console','console.log'),('csv','training.csv')):
    path=RUN/name;start=complete['initial_offsets'][key];end=complete['final_offsets'][key]
    with path.open('rb') as stream:prefix=stream.read(end)
    if len(prefix)!=end:raise ValueError('Completed source prefix was truncated: '+key)
    frozen_prefixes[key]=prefix;segments[key]=prefix[start:end]
    prefix_records.append(dict(path=str(path),whole_prefix_bytes=end,whole_prefix_sha256=sha_bytes(prefix),interval_start_byte=start,interval_end_byte_exclusive=end,interval_bytes=end-start,interval_sha256=sha_bytes(prefix[start:end]),initial_offset_at_newline=(start==0 or prefix[start-1:start]==b'\n'),final_offset_at_newline=(end==0 or prefix[-1:]==b'\n'),scope='Bound completed main-only prefix; any later append is excluded.'))
patterns=first['log_pattern_counts_since_start'];console_counts={key:segments['console'].count(key.encode()) for key in patterns}
check('all_console_cumulative_counts_zero_and_source_prefix_agrees',all(r['log_pattern_counts_since_start']==dict.fromkeys(patterns,0) for r in rows) and console_counts==dict.fromkeys(patterns,0))
header=frozen_prefixes['csv'].split(b'\n',1)[0].decode().rstrip('\r');fields=next(csv.reader([header]))
raw_csv=[];csv_parse_errors=[]
for index,values in enumerate(csv.reader(io.StringIO(segments['csv'].decode())),1):
    if not values:continue
    if len(values)!=len(fields):csv_parse_errors.append(dict(interval_row=index,fields=len(values),expected=len(fields)));continue
    raw_csv.append(dict(zip(fields,values)))
selected_keys=('utc','steps','optimized_samples','learner_frames','replay_dropped','loss','grad_norm')
csv_selected=[{k:r[k] for k in selected_keys} for r in raw_csv]
recorded_csv=[r for row in rows for r in row.get('CSV_health_rows',[])]
check('all_original_complete_CSV_health_rows_retained',not csv_parse_errors and csv_selected==recorded_csv and all(complete['pending_append_bytes'][k]==0 for k in ('console','csv')))
drop_values={r['replay_dropped'] for r in raw_csv};check('all_CSV_drop_totals_constant_zero',drop_values=={'0'})
check('all_CSV_clock_rows_monotone',all(int(b[k])>=int(a[k]) for a,b in zip(recorded_csv,recorded_csv[1:]) for k in ('steps','optimized_samples','learner_frames')))
csv_nonfinite_grad=[r for r in recorded_csv if not math.isfinite(numeric(r['grad_norm']))]
csv_nonfinite_loss=[r for r in recorded_csv if not math.isfinite(numeric(r['loss']))]
check('no_CSV_nonfinite_loss',not csv_nonfinite_loss)
bank_fields=('capture_attempts','capture_deferrals','writes','write_failures')
check('bank_stream_metadata_no_recorded_errors',all(r['bank']['output_backend']=='stream' and r['bank']['write_failures']==0 and r['bank']['last_error'] is None and all(x['errors']==0 for x in r['bank']['phase_counts'].values()) for r in rows))
check('bank_counters_monotone',all(b['bank'][key]>=a['bank'][key] for a,b in zip(rows,rows[1:]) for key in bank_fields))
bank_changes=[]
for left,right in zip(rows,rows[1:]):
    changed={k:[left['bank'][k],right['bank'][k]] for k in (*bank_fields,'writer_active') if left['bank'][k]!=right['bank'][k]}
    if changed:bank_changes.append(dict(previous_utc=left['utc'],current_utc=right['utc'],changes=changed))
bank_delta={key:last['bank'][key]-first['bank'][key] for key in bank_fields}
phase_delta={key:{n:last['bank']['phase_counts'][key][n]-first['bank']['phase_counts'][key][n] for n in ('count','errors')} for key in first['bank']['phase_counts']}
check('four_bank_writes_in_two_observed_cycles',first['bank']['writes']==6 and last['bank']['writes']==10 and bank_delta['writes']==bank_delta['capture_attempts']==4 and bank_delta['capture_deferrals']==bank_delta['write_failures']==0)
bank_cycles=[];active=None
for left,right in zip(rows,rows[1:]):
    if not left['bank']['writer_active'] and right['bank']['writer_active']:
        active=dict(last_idle_before_start_utc=left['utc'],first_active_utc=right['utc'],writes_before=left['bank']['writes'])
    if active is not None and left['bank']['writer_active'] and not right['bank']['writer_active']:
        active.update(last_active_utc=left['utc'],first_idle_after_utc=right['utc'],writes_after=right['bank']['writes'],
            scope='5s sampled writer metadata brackets; exact capture/write/release durations not measured.')
        bank_cycles.append(active);active=None
check('two_complete_observed_bank_cycles_started13_31_and14_01',len(bank_cycles)==2 and active is None
    and [x['first_active_utc'][:16] for x in bank_cycles]==['2026-10-16T13:31','2026-10-16T14:01']
    and all(x['writes_after']-x['writes_before']==2 for x in bank_cycles))
# Full original endpoints; no warmup exclusion, quiet-window selection, or trimming.
monotonic_span=last['monotonic_s']-first['monotonic_s'];UTC_span=iso_seconds(last['utc'])-iso_seconds(first['utc']);API_span=health[-1]['API_ts']-health[0]['API_ts']
rates=dict(optimized_samples_per_host_s=clock_changes['optimized_samples']/monotonic_span,fleet_frames_per_host_s=clock_changes['frame_count']/monotonic_span,learner_frames_per_host_s=clock_changes['learner_frame_count']/monotonic_span,logical_updates_per_host_s=clock_changes['training_steps']/monotonic_span,samples_per_fleet_frame=clock_changes['optimized_samples']/clock_changes['frame_count'],samples_per_learner_frame=clock_changes['optimized_samples']/clock_changes['learner_frame_count'])
# Recheck frozen prefixes only, without reading post-window appends.
for key,name in (('console','console.log'),('csv','training.csv')):
    with (RUN/name).open('rb') as stream:check(key+'_frozen_prefix_still_exact',stream.read(len(frozen_prefixes[key]))==frozen_prefixes[key])
check('raw_observer_bytes_still_exact',raw_path.read_bytes()==raw)
check('small_input_evidence_unchanged',all(sha_bytes(Path(x['path']).read_bytes())==x['sha256'] for x in evidence))
proof=dict(schema='robotron-completed-main-coast-independent-proof-v1',started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),analysis_code=dict(path=str(Path(__file__)),sha256=sha_bytes(Path(__file__).read_bytes())),evidence=evidence,prefixes=prefix_records,checks=checks,parse_errors=parse_errors,csv_parse_errors=csv_parse_errors,reported_issue_counts=dict(issue_counts),reported_notice_counts=dict(notice_counts),recognized_AMP_skip_brackets=skips,API_nonfinite_gradient_rows=api_nonfinite_grad,CSV_nonfinite_gradient_rows=csv_nonfinite_grad,API_nonfinite_loss_rows=api_nonfinite_loss,CSV_nonfinite_loss_rows=csv_nonfinite_loss,observed_bank_metadata_transitions=bank_changes,observed_bank_cycles=bank_cycles,source_guard_records=guard_values)
proof_record=exclusive_json(RUN/'main-coast-to160-independent-proof.json',proof)
summary=dict(schema='robotron-completed-main-coast-independent-summary-v1',created_utc=datetime.now(timezone.utc).isoformat(),PASS=all(checks.values()),checks=checks,proof=proof_record,original_interval=dict(first_utc=first['utc'],last_utc=last['utc'],complete_started_utc=complete['started_utc'],complete_ended_utc=complete['ended_utc'],rows=len(rows),expected_rows=complete['rows'],host_monotonic_s=monotonic_span,observer_UTC_s=UTC_span,API_timestamp_s=API_span,whole_observer_elapsed_s=complete['elapsed_s'],poll_gap_s=span_stats(monotonic_deltas),gap_threshold_s=7.5,gaps=recorded_gaps,parse_errors=parse_errors,partial_or_pending_append_bytes=complete['pending_append_bytes'],end_reason=complete['end_reason'],endpoint_scope='Every original completed row including natural bank activity; counters anchored first-to-last rows, no trimming.'),clocks=dict(first=clocks[0],last=clocks[-1],delta=clock_changes),host_counter_rates=rates,secondary_API_counter_rates=dict(samples_per_s=clock_changes['optimized_samples']/API_span,fleet_FPS=clock_changes['frame_count']/API_span,learner_FPS=clock_changes['learner_frame_count']/API_span),API_snapshot_age_s=span_stats(api_ages),ownership=dict(main_pid=complete['main_pid'],supervisor_pid=complete['supervisor_pid'],observed_owners=expected_owners,actor_pin_count=192,all192_PID_starttick_pairs_matched_every_observed_poll=True,manifest=evidence[-1]),source_control_scope=dict(recorded_source_stats_count=20,inherited_source_SHA_attestation=complete['source_hash_attestation'],source_hash_payloads_recomputed=False,distinct_stat_control_checks=len(guard_values),observed_guard_interval_s=span_stats(guard_intervals),cached_guard_age_s=span_stats(guard_ages),control_sha256=next(iter(control_shas)),scope='Source20 stat identities and control bytes sampled every60–65s; hashes inherited from startup attestation. This is not a new code/payload hash sweep or continuous proof between polls.'),health=dict(reported_issues=dict(issue_counts),reported_notices=dict(notice_counts),API_read_error_rows=sum('API_error' in r for r in rows),append_read_error_rows=sum('append_read_error' in r for r in rows),console_cumulative_since_initial_offset=console_counts,CSV_health_rows=len(recorded_csv),CSV_drop_totals=sorted(drop_values),epoch_identity=epochs,optimizer_first=optimizer[0],optimizer_last=optimizer[-1],optimizer_delta=optimizer_delta,logical_update_delta_minus_outcome_delta=clock_changes['training_steps']-optimizer_delta['outcomes_recorded'],counter_clock_note='API/model clocks and optimizer outcome snapshots are read separately. Their delta difference cannot be classified as an optimizer outcome.',optimizer_pending_value_counts=dict(Counter(str(h['optimizer_pending']) for h in health)),optimizer_available_value_counts=dict(Counter(str(h['optimizer_available']) for h in health)),accepted_learner_first=health[0]['accepted_learner'],accepted_learner_last=health[-1]['accepted_learner'],accepted_learner_delta=health[-1]['accepted_learner']-health[0]['accepted_learner'],recognized_AMP_skip_delta=optimizer_delta['amp_skipped'],recognized_skip_brackets=len(skips),API_nonfinite_gradient_samples=len(api_nonfinite_grad),CSV_nonfinite_gradient_rows=len(csv_nonfinite_grad),nonfinite_loss_samples=len(api_nonfinite_loss)+len(csv_nonfinite_loss),graph_first=health[0]['graph'],graph_last=health[-1]['graph'],native_first=health[0]['native'],native_last=health[-1]['native']),bank_metadata=dict(first=first['bank'],last=last['bank'],delta=bank_delta,phase_delta=phase_delta,observed_cycles=bank_cycles,time_resolution_s=5,earlier13_01_event_observed=False,scope='Coarse API metadata records4additional bank writes6→10 and no recorded errors. No CURRENT/generation/file payload/durability validation or exact save-time attribution is performed here.'),limitations=['Descriptive main-only observation, not a controlled throughput comparison, causal speedup or universal reliability claim. No live/private160 quality, scores, model payload, GPU/profiler, controls or processes were accessed by this analysis.','821polls cannot establish continuous liveness or error absence between samples. Console cumulative counts apply only to the frozen appended byte interval, not the entire training campaign.','Compact raw rows retain optimizer partitions and accepted_learner only, not DQN/epsilon/expert/eval/unattributed replay-category totals, supported-Torch metadata or pipeline-generation values. Replay-category partitions and generation/getter-read health cannot be independently recomputed from these compact rows; absence of their faults is the observer report, not extra invented raw evidence.','API/model clocks and process-local optimizer snapshots are not atomic. Logical update delta need not equal recorded outcome delta; recognized AMP skips and nonfinite gradient rows remain separate and do not identify a particular parameter movement or causal event.','Bank baseline writes6 already includes earlier events;13:01 is outside this watch. Only13:31 and14:01 metadata transitions are covered, at5s resolution; no whole-save acceleration or GC/snapshot/unmap cause is established.','Startup receipt preserves an initial observer source-path-resolution failure before output creation; the observed interval belongs to the corrected relaunched watcher, with no training source/process change.'],initial_review_correction='The preserved first review used an overstrict minute-only assertion for bank transitions; the13:31/14:01 cycles correctly finish in13:32/14:02. This final check groups complete writer-active metadata brackets without dropping rows or relaxing any runtime/error guard.',execution=dict(started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_s=time.monotonic()-begin,pid=os.getpid(),installed_Torch_or_GPU_import=False))
# Correct ownership manifest pointer explicitly; evidence order is not semantic.
summary['ownership']['manifest']=next(x for x in evidence if x['path']==complete['actor_pin_path'])
record=exclusive_json(RUN/'main-coast-to160-independent-summary.json',summary)
print(json.dumps(dict(PASS=summary['PASS'],checks=len(checks),summary=record,rows=len(rows),host_counter_rates=rates,optimizer_delta=optimizer_delta,nonfinite_API_grad=len(api_nonfinite_grad),nonfinite_CSV_grad=len(csv_nonfinite_grad),CSV_health_rows=len(recorded_csv),bank_metadata_delta=bank_delta,analysis_elapsed_s=time.monotonic()-begin),indent=2))
