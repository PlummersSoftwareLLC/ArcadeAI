"""Bounded independent stdlib audit of the frozen Areturn leg; one6.4MB raw read."""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path

D = Path(__file__).resolve().parent
sha = lambda raw: hashlib.sha256(raw).hexdigest()
summary_raw = (D / 'collector-Areturn-summary.json').read_bytes()
assert sha(summary_raw) == '970a76633a1b5af2d39c47fd6fa8930ccff5370ac257d62f91f10a4e65253046'
summary = json.loads(summary_raw)
complete_raw = (D / 'collector-Areturn-complete.json').read_bytes(); complete = json.loads(complete_raw)
adoption_raw = (D / 'collector4096-Areturn-root-window-adoption.json').read_bytes(); adoption = json.loads(adoption_raw)
raw = Path(summary['raw_complete_prefix']['path']).read_bytes()  # Single body read.
assert raw.endswith(b'\n')
rows = [json.loads(line) for line in raw.splitlines()]
anchor = adoption['anchor_unix_s']
first = next(i for i, row in enumerate(rows) if row['observer_unix_s'] >= anchor)
last = next(i for i in range(first, len(rows)) if rows[i]['observer_unix_s'] - rows[first]['observer_unix_s'] >= 180)
a, z = rows[first], rows[last]
window, guarded = rows[first:last+1], rows[:last+1]
duration = z['observer_unix_s'] - a['observer_unix_s']
clocks = ('optimized_samples','frame_count','learner_frame_count','training_steps','measurement_frames')
deltas = {key: z[key] - a[key] for key in clocks}
rates = dict(samples_per_s=deltas['optimized_samples']/duration,
             fleet_frames_per_s=deltas['frame_count']/duration,
             samples_per_nonmeasurement_fleet_frame=deltas['optimized_samples']/(deltas['frame_count']-deltas['measurement_frames']))
manifest_raw = Path(summary['actor_manifest']['path']).read_bytes(); manifest = json.loads(manifest_raw)
actor_rows = {str(actor['pid']): actor for actor in manifest['actors']}
bindings, initial = summary['actor_stdout_bindings'], summary['actor_log_initial_offsets']
paths = {path for value in bindings.values() for path in value['paths']}
actor_segments = []
markers = ('[SOCKET ACTION TIMEOUT]','Socket read error:','Socket write error:',
           'socket_read_error','socket_write_error','Socket open failed:')
for path in sorted(paths):
    info = initial[path]; file = Path(path); s = file.stat()
    start, end = info['complete_prefix_offset'], z['append_offsets']['actor_logs'][path]
    assert [s.st_dev,s.st_ino] == info['file_identity'] and start <= end <= s.st_size
    assert end-start < 1_000_000
    with file.open('rb') as stream:
        stream.seek(start); segment = stream.read(end-start)
    text = segment.decode(errors='replace')
    actor_segments.append(dict(path=path, start=start, end=end, bytes=len(segment), sha256=sha(segment),
                               marker_counts={marker:text.count(marker) for marker in markers},
                               ending_partial_line=bool(segment and not segment.endswith(b'\n'))))

counter_errors = []
counter_identity = None
previous = None
for index, row in enumerate(guarded):
    exposure = row['host_pipeline']['learning_exposure']; opt, replay = exposure['optimizer'], exposure['replay']
    identity = tuple(value for item in (opt,replay) for value in (item['process_id'],item['instance_monotonic_ns'],item['epoch'],item['epoch_reason']))
    counter_identity = counter_identity or identity
    total = opt['total']; source = replay['accepted_by_source_total']
    valid = (identity == counter_identity and opt['process_id'] == replay['process_id'] == 2148801
        and opt['epoch'] == replay['epoch'] == 1 and opt['enabled'] and replay['enabled']
        and total['outcomes_recorded'] == total['applied']+total['amp_skipped']+total['unavailable']
        and total['attempts_started']-total['outcomes_recorded'] == opt['unclassified_started_total']
        and opt['unclassified_started_total'] in (0,1) and total['unavailable'] == opt['prior_epoch_outcomes_total'] == 0
        and (opt['available'] or opt['unclassified_started_total']==1)
        and replay['accepted_total'] == sum(source.values())
        and replay['accepted_learner_total'] == source['dqn']+source['epsilon'])
    for name, value in (('optimizer',opt),('replay',replay)):
        if name == 'optimizer':
            valid &= all(type(v) is int and v>=0 for v in value['total'].values())
            valid &= value['total'] == value['since_epoch']
        else:
            valid &= value['accepted_total'] == value['accepted_since_epoch'] and value['accepted_learner_total'] == value['accepted_learner_since_epoch']
            valid &= value['accepted_by_source_total'] == value['accepted_by_source_since_epoch']
    if previous:
        valid &= all(opt['total'][key]>=previous['optimizer']['total'][key] for key in total)
        valid &= all(source[key]>=previous['replay']['accepted_by_source_total'][key] for key in source)
    if not valid:
        counter_errors.append(dict(index=index,utc=row['utc']))
    previous = exposure

def endpoints(x,y):
    elapsed=y['observer_unix_s']-x['observer_unix_s']
    samples=y['optimized_samples']-x['optimized_samples']; fleet=y['frame_count']-x['frame_count']-(y['measurement_frames']-x['measurement_frames'])
    return dict(start_utc=x['utc'],end_utc=y['utc'],duration_s=elapsed,samples_per_s=samples/elapsed,SPF=samples/fleet)

blocks=[]
for offset in range(0,180,30):
    x=next(row for row in window if row['observer_unix_s']>=a['observer_unix_s']+offset)
    y=next(row for row in window if row['observer_unix_s']>=a['observer_unix_s']+offset+30)
    blocks.append(endpoints(x,y))
tail=next(row for row in window if row['observer_unix_s']>=z['observer_unix_s']-30)
last_block=endpoints(tail,z)
energy=sum((x['gpu1_power_w']+y['gpu1_power_w'])*.5*(y['observer_unix_s']-x['observer_unix_s']) for x,y in zip(window,window[1:]))
util_integral=sum((x['gpu1_util']+y['gpu1_util'])*.5*(y['observer_unix_s']-x['observer_unix_s']) for x,y in zip(window,window[1:]))
notices=[dict(utc=row['utc'],notices=row['notices']) for row in guarded if row['notices']]
ea,ez=a['host_pipeline']['learning_exposure'],z['host_pipeline']['learning_exposure']
opt_delta={key:ez['optimizer']['total'][key]-ea['optimizer']['total'][key] for key in ea['optimizer']['total']}
replay_delta={key:ez['replay']['accepted_by_source_total'][key]-ea['replay']['accepted_by_source_total'][key] for key in ea['replay']['accepted_by_source_total']}
checks={
 'summary_supplied_SHA_and_complete_raw_prefix_pins_match':len(raw)==summary['raw_complete_prefix']['bytes']==complete['raw']['bytes'] and sha(raw)==summary['raw_complete_prefix']['sha256']==complete['raw']['sha256'],
 'prospective_adoption_precedes_fixed_anchor_without_reanchor':adoption['root_authorizes_Areturn_observer'] and adoption['duration_s']==180 and anchor==summary['prospective_anchor_unix_s']==complete['requested_anchor_unix_s'] and datetime.datetime.fromisoformat(adoption['utc']).timestamp()<anchor,
 'first_eligible_then_first180_endpoint_exact':complete['complete'] is True and [first,last]==summary['source_row_indexes']==[complete['first_primary_index'],complete['last_primary_index']] and first==73 and last==254 and complete['primary_start_unix_s']==a['observer_unix_s'] and complete['primary_end_unix_s']==z['observer_unix_s'] and summary['start_utc']==a['utc'] and summary['end_utc']==z['utc'],
 'all255_rows_retained_and182_primary_rows_no_issues':len(rows)==summary['guard_rows_including_settle']==255 and len(window)==summary['rows']==182 and [r['index'] for r in rows]==list(range(len(rows))) and not any(row['issues'] for row in guarded) and summary['valid'] is True,
 'primary_raw_counter_rates_and_SPF_exact':deltas==summary['clock_deltas'] and duration==summary['duration_s'] and all(math.isclose(v,summary[k],rel_tol=1e-13) for k,v in rates.items()) and deltas['measurement_frames']==0,
 'six_nominal_boundary_bins_and_actual_last_duration_preserved':len(blocks)==len(summary['blocks30s'])==6 and all(b['start_utc']==s['start_utc'] and b['end_utc']==s['end_utc'] and b['duration_s']==s['duration_s'] and math.isclose(b['samples_per_s'],s['samples_per_s'],rel_tol=1e-13) and math.isclose(b['SPF'],s['samples_per_nonmeasurement_fleet_frame'],rel_tol=1e-13) for b,s in zip(blocks,summary['blocks30s'])) and last_block['duration_s']==summary['last30s']['duration_s'],
 'all192_actual_stdout_paths_and_new_prefix_offsets_covered':sha(manifest_raw)==summary['actor_manifest']['sha256']==adoption['actor_manifest_sha256'] and set(bindings)==set(actor_rows) and len(bindings)==len(paths)==len(initial)==192 and sorted(v['slot'] for v in bindings.values())==list(range(192)) and all(set(row['append_offsets']['actor_logs'])==paths for row in guarded) and all(bindings[pid]['slot']==actor['slot'] for pid,actor in actor_rows.items()),
 'all192_bounded_NEW_segments_exact_printed_read_write_timeout_markers0':all(not any(segment['marker_counts'].values()) for segment in actor_segments),
 'all_held_PID_stdout_source_control_and_new_log_guards_clean':all(row['trainer_pid']==2148801 and row['trainer_identity']==dict(alive=True,start_ticks=26264365) and not row['actor_mismatches'] and not row['supervisor_mismatches'] and not any(row['console_error_counts'].values()) and not any(row['actor_transport_counts'].values()) and not row['new_actor_transport_events'] and row['source_control_guard']['source_stat_unchanged'] and row['source_control_guard']['manifest_unchanged'] and row['source_control_guard']['actor_stdout_descriptors_unchanged'] and row['source_control_guard']['exposure_checker_unchanged'] and row['source_control_guard']['control_sha256']==summary['initial_control_sha256'] for row in guarded),
 'all_counter_epochs_partitions_learner_categories_and_monotonicity_valid':not counter_errors,
 'all192_graph_native_loss_bank_read_drop_health_clean':all(row['client_count']==192 and row['training_enabled'] and not row['measurement_active'] and math.isfinite(float(row['loss'])) and not row['pipeline_read_error'] and not row['bank_persistence_read_error'] and row['host_pipeline']['inference_graphs']['ready'] and row['host_pipeline']['inference_graphs']['capture_count']==128 and row['host_pipeline']['inference_graphs']['validation_replay_count']==640 and row['host_pipeline']['inference_graphs']['postload_validations']==1 and row['host_pipeline']['inference_graphs']['runtime_capture_count']==row['host_pipeline']['inference_graphs']['fallback_count']==0 and row['host_pipeline']['inference_graphs']['fatal_error'] is None and row['host_pipeline']['native_batch_update']['success_count']==row['host_pipeline']['native_batch_update']['completed_count'] and row['host_pipeline']['native_batch_update']['error_count']==row['host_pipeline']['native_batch_update']['fallback_count']==0 and row['bank_persistence']['write_failures']==0 and row['bank_persistence']['last_error'] is None and all(v['errors']==0 for v in row['bank_persistence']['output']['totals'].values()) and all(int(item['replay_dropped'])==0 for item in row['new_CSV_queue_signals']) for row in guarded),
 'AMP_Infgrad_notices_and_nonatomic_counter_deltas_preserved':notices==summary['notices'] and opt_delta==summary['optimizer_counter_delta'] and replay_delta==summary['accepted_replay_by_source_delta'],
 'GPU_only_energy_fullcoverage_recomputed':summary['energy']['available'] and summary['energy']['covered_s']==duration and all(math.isfinite(row['gpu1_power_w']) and math.isfinite(row['gpu1_util']) for row in window) and math.isclose(energy,summary['energy']['integral'],rel_tol=1e-13) and math.isclose(deltas['optimized_samples']/energy,summary['energy']['samples_per_joule'],rel_tol=1e-13) and math.isclose(util_integral/duration,summary['gpu_util']['mean'],rel_tol=1e-13),
}
report=dict(schema='robotron-collector4096-Areturn-fixed-endpoint-independent-audit-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),PASS=all(checks.values()),checks=checks,
 summary_sha256=sha(summary_raw),completion_sha256=sha(complete_raw),adoption_sha256=sha(adoption_raw),raw_sha256=sha(raw),raw_bytes=len(raw),raw_body_reads=1,
 selected_indexes=[first,last],start_utc=a['utc'],end_utc=z['utc'],duration_s=duration,clock_deltas=deltas,**rates,
 nominal30s_boundary_bins_actual_intervals=blocks,last_nominal30s_actual=last_block,
 GPU_only_joules=energy,samples_per_GPU_joule=deltas['optimized_samples']/energy,GPU_util_mean=util_integral/duration,
 optimizer_delta=opt_delta,replay_by_source_delta=replay_delta,counter_errors=counter_errors,notices_preserved=notices,
 actual192_log_new_segments=actor_segments,
 marker_scope_correction='Prospectively root-adopted B/Areturn observer adds exact printed read/write/open error markers to optional trace tags and actiontimeouts. This independent audit also checks all of those markers in bounded NEW segments for each of all192 stdout paths. Summary/raw/endpoint algorithm unchanged.',
 timing_caveat='Primary180.999996s is the FIRST observed endpoint>=180s after the first eligible row; it is preserved, not reanchored. Nominal30s bins use original fixed-boundary first>= selection; actual durations including final nominal30s29.999999s are retained rather than called mathematically exact30s.',
 clock_caveat='API/optimizer/replay metrics are asynchronously cached, not an atomic joined snapshot. Logical3149/samples3150batches and3139outcomes/3137applied/2AMPskips are retained without invented per-update reconciliation or causality. Two primary knownskip brackets and no Inf-gradient notice are retained, not automatic faults.',
 scope='Existing frozen raw/evidence and bounded newly appended actor-log segments only; no live API/model/Torch/GPU/process/control/source action. Any subsequent root-coordinated fleet stop lies outside frozen endpoint and is not a primary-window fault. No B/Areturn selection or learning-quality inference.')
output=D/'collector-Areturn-independent-fixed-audit.json'
with output.open('x') as file:
 json.dump(report,file,indent=2,allow_nan=False);file.write('\n');file.flush();os.fchmod(file.fileno(),0o444);os.fsync(file.fileno())
print(json.dumps(dict(PASS=report['PASS'],checks=len(checks),failed=[k for k,v in checks.items() if not v],sha256=sha(output.read_bytes()),start_utc=a['utc'],end_utc=z['utc'],rates=rates,log_new_bytes=sum(v['bytes'] for v in actor_segments)),indent=2))
