"""Derive interval evidence from the saved read-only live observations."""
import json,statistics
from pathlib import Path

OUT=Path(__file__).resolve().parent
rows=[json.loads(line) for line in (OUT/'observations.jsonl').read_text().splitlines()]
a,b=rows[0],rows[-1];dt=b['observed_monotonic_s']-a['observed_monotonic_s']
initial=json.loads((OUT/'initial-bindings.json').read_text());final=json.loads((OUT/'final-bindings.json').read_text())
delta=lambda key:b[key]-a[key]
optimizer=lambda r:r['exposure']['optimizer']['total']
od={key:optimizer(b)[key]-optimizer(a)[key] for key in optimizer(a)}
rd={key:b['exposure']['replay'][key]-a['exposure']['replay'][key] for key in ('accepted_total','accepted_learner_total')}
def difference_mean(section):
    old,new=a['host_pipeline'][section],b['host_pipeline'][section]
    return {key:dict(unit='rows' if key=='batch_size' else 'ms',observations=value['count']-old[key]['count'],total=value['total']-old[key]['total'],
        mean=(value['total']-old[key]['total'])/(value['count']-old[key]['count']) if value['count']>old[key]['count'] else None)
        for key,value in new.items() if isinstance(value,dict) and 'count' in value and 'total' in value}

report=dict(schema='robotron-readonly-live-replay-pipeline-window-v1',start_api_ts=a['ts'],end_api_ts=b['ts'],
    observed_s=dt,api_timestamp_s=b['ts']-a['ts'],rows=len(rows),no_live_mutations=True,
    binding_checks=dict(same_bindings=final['same_bindings'],same_unit=final['same_unit'],
        trainer=initial['bindings']['worker']['trainer'],actor_count=len(initial['bindings']['actors']),
        all_clients_192=all(r['client_count']==192 for r in rows),
        all_exposure_processes_match_trainer=all(r['exposure'][kind]['process_id']==initial['bindings']['worker']['trainer']['pid'] for r in rows for kind in ('optimizer','replay')),
        all_counter_epochs_stable=all({kind:{key:r['exposure'][kind][key] for key in ('process_id','instance_monotonic_ns','epoch')} for kind in ('optimizer','replay')}=={kind:{key:a['exposure'][kind][key] for key in ('process_id','instance_monotonic_ns','epoch')} for kind in ('optimizer','replay')} for r in rows),
        guard_issues=[dict(row=i,issues=r['issues']) for i,r in enumerate(rows) if r['issues']]),
    cumulative_deltas=dict(optimizer=od,replay=rd,frames=delta('frame_count'),learner_frames=delta('learner_frame_count'),
        logical_optimized_samples=delta('optimized_samples'),logical_steps=delta('training_steps'),
        prefetched_batches=int(b['csv_observation']['prefetched_batches'])-int(a['csv_observation']['prefetched_batches']),
        direct_state_batches=int(b['csv_observation']['direct_state_batches'])-int(a['csv_observation']['direct_state_batches']),
        pressure_waits=int(b['csv_observation']['replay_pressure_waits'])-int(a['csv_observation']['replay_pressure_waits']),
        replay_drops=b['csv']['replay_dropped']-a['csv']['replay_dropped']),
    rates=dict(applied_admission_samples_per_s=od['applied']*4096/dt,logical_optimized_samples_per_s=delta('optimized_samples')/dt,
        accepted_learner_inserts_per_s=rd['accepted_learner_total']/dt,accepted_all_inserts_per_s=rd['accepted_total']/dt,
        frames_per_s=delta('frame_count')/dt,logical_samples_per_frame=delta('optimized_samples')/delta('frame_count'),
        optimizer_applied_calls_per_s=od['applied']/dt,pressure_waits_per_s=(int(b['csv_observation']['replay_pressure_waits'])-int(a['csv_observation']['replay_pressure_waits']))/dt),
    optimizer_pending=[r['optimizer_pending'] for r in rows],
    pipeline_interval_means={name:difference_mean(name) for name in ('inference','actor_refresh','target_refresh','learner_priority')},
    observed_csv_last_step_timings={key:dict(unweighted_observation_mean=statistics.mean(float(r['csv_observation'][key]) for r in rows),
        minimum=min(float(r['csv_observation'][key]) for r in rows),maximum=max(float(r['csv_observation'][key]) for r in rows))
        for key in ('sample_wall_ms','stage_host_ms','transfer_host_ms','compute_host_ms','priority_and_readback_ms','train_step_wall_ms','gpu_compute_ms')},
    thread_scheduler_deltas={name:dict(same_tid_epoch={key:value[key] for key in ('tid','starttime_ticks')}=={key:a['threads'][name][key] for key in ('tid','starttime_ticks')},
        cpu_runtime_s=(value['runtime_ns']-a['threads'][name]['runtime_ns'])/1e9,
        cpu_runtime_fraction=(value['runtime_ns']-a['threads'][name]['runtime_ns'])/1e9/dt,
        runnable_wait_s=(value['runqueue_wait_ns']-a['threads'][name]['runqueue_wait_ns'])/1e9)
        for name,value in b['threads'].items()},
    natural_bank_events=dict(writes=b['bank']['writes']-a['bank']['writes'],failures=b['bank']['write_failures']-a['bank']['write_failures'],
        active_rows=sum(bool(r['bank']['writer_active']) for r in rows),write_duration_s=b['bank']['write_duration_s']-a['bank']['write_duration_s']),
    interpretation=[
        'Applied exposure is optimizer-call admissions, not proof every parameter or Adam step advanced. Logical samples are schedule counters; rates must remain separately labelled.',
        'The API logical clocks and pipeline exposure counters are cached asynchronously. This window has1976 exposure attempts,1975 admissions,1AMP skip and1978 logical batches. The difference is consistent with endpoint cache skew; logical clocks do not establish2 additional Adam updates.',
        'sample_wall_ms is one last producer batch sample measurement (includes replay-lock acquisition, index selection and state filling); it is not cumulative and does not isolate state filling.',
        'Sampling and staging execute on a background producer and overlap the learner. train_step_wall_ms begins after prefetch get and excludes waiting for a ready batch; do not add sampling/staging/learner or GPU/host times.',
        'CSV timing means above are unweighted observations of last-step values, not an exact interval sum or a stall fraction. Sampled cumulative pipeline phase means use total/count differences.',
        'Replay pressure counter increments when the learner cap check blocks work; the counter is not a blocked-time duration. Near8 logical samples/frame supports an active replay-admission cap.',
        'Shorter replay lock holds may improve actor insert throughput even when direct learner work is capped; these observations do not establish that state fill dominates stalls or that parallel fill will improve throughput.',
        'No prefetch-get wait duration, queue occupancy, state-fill-only duration, actor replay-lock wait, or memory-bandwidth counter is available in this API. No load benchmark, affinity change or trace was run.',
        'This single window includes a concurrent frozen quality evaluator and any natural bank events shown; it is not a treatment trial or learning-quality claim.'
    ])
(OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({key:report[key] for key in ('observed_s','rows','binding_checks','rates','natural_bank_events','thread_scheduler_deltas')},indent=2))
