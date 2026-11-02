"""One-minute, read-only observational baseline; no scores or GPU calls."""
import csv
import json
import os
from pathlib import Path
import statistics
import time
import urllib.request

D = Path(__file__).resolve().parent
rows = []
start = time.monotonic()
with (D / 'observations-original01.jsonl').open('x') as out:
    for index in range(7):
        if index:
            time.sleep(max(0, start+10*index-time.monotonic()))
        began = time.monotonic()
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=4) as response:
            api = json.load(response)
        exposure = api['host_pipeline']['learning_exposure']
        optimizer, replay = exposure['optimizer'], exposure['replay']
        assert optimizer['enabled'] and optimizer['available'] and replay['enabled'] and replay['available']
        row = {key: api.get(key) for key in (
            'ts', 'frame_count', 'learner_frame_count', 'optimized_samples', 'measurement_frames',
            'training_steps', 'fps', 'steps_per_sec', 'train_sample_ms', 'train_step_ms',
            'pipeline_snapshot_age_s', 'gpu1_name', 'gpu1_util', 'gpu1_power_w',
            'gpu1_mem_used_mib', 'gpu1_mem_total_mib')}
        row.update(index=index, observed_unix_s=time.time(), observed_monotonic_s=time.monotonic(),
                   API_read_elapsed_s=time.monotonic()-began,
                   optimizer_identity={k:optimizer[k] for k in ('process_id','instance_monotonic_ns','epoch','epoch_reason')},
                   replay_identity={k:replay[k] for k in ('process_id','instance_monotonic_ns','epoch','epoch_reason')},
                   optimizer_since_epoch=optimizer['since_epoch'],
                   admitted_by_source=replay['accepted_by_source_since_epoch'],
                   admitted_rows=replay['accepted_since_epoch'],
                   training_round={k:api['training_round'].get(k) for k in ('round','active','completed','total')})
        assert row['gpu1_name'] == 'NVIDIA GB300'
        if rows:
            assert row['optimizer_identity'] == rows[0]['optimizer_identity']
            assert row['replay_identity'] == rows[0]['replay_identity']
        rows.append(row)
        out.write(json.dumps(row, separators=(',', ':'))+'\n')
        out.flush()
        print(json.dumps({k:row[k] for k in ('index','observed_unix_s','gpu1_util','gpu1_power_w','fps','steps_per_sec')}), flush=True)
    os.fsync(out.fileno())

first, last = rows[0], rows[-1]
duration = last['ts']-first['ts']
raw = last['frame_count']-first['frame_count']-(last['measurement_frames']-first['measurement_frames'])
samples = last['optimized_samples']-first['optimized_samples']
admitted = last['admitted_rows']-first['admitted_rows']
assert duration > 50 and raw > 0 and admitted > 0
outcomes = {k:last['optimizer_since_epoch'][k]-first['optimizer_since_epoch'][k]
            for k in ('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')}
report = dict(schema='robotron-root-unchanged-cap8-tail-observation-v1',
    status='OBSERVATIONAL_BASELINE_ONLY_NO_TREATMENT',
    sample_count=len(rows), elapsed_API_s=duration, actual_elapsed_s=last['observed_monotonic_s']-first['observed_monotonic_s'],
    optimizer_and_replay_identity_unchanged=True,
    rounds=[first['training_round'],last['training_round']], delta_optimizer_outcomes=outcomes,
    rates=dict(accepted_nonmeasurement_frames_s=raw/duration, admitted_rows_s=admitted/duration,
               logical_updates_s=samples/4096/duration, applied_updates_s=outcomes['applied']/duration,
               samples_per_raw_frame=samples/raw, samples_per_admitted_row=samples/admitted),
    sampled_GB300=dict(mean_util_pct=statistics.mean(r['gpu1_util'] for r in rows),
                       min_util_pct=min(r['gpu1_util'] for r in rows),max_util_pct=max(r['gpu1_util'] for r in rows),
                       mean_power_W=statistics.mean(r['gpu1_power_w'] for r in rows),
                       min_memory_used_pct=min(100*r['gpu1_mem_used_mib']/r['gpu1_mem_total_mib'] for r in rows),
                       max_memory_used_pct=max(100*r['gpu1_mem_used_mib']/r['gpu1_mem_total_mib'] for r in rows)),
    limitations=['Seven regular cached API GPU samples, not a controlled GPU duty-cycle average',
                 'Main round9 tail population only; no full-population, treatment, quality or causal claim',
                 'Producer/API counters have separate publication boundaries'],
    any_training_or_scientific_control_changed=False, any_scores_read=False,
    quality_qualified=False, promotion=False)
with (D / 'observational-baseline-original01.json').open('x') as out:
    json.dump(report, out, indent=2)
    out.write('\n');out.flush();os.fsync(out.fileno());os.fchmod(out.fileno(),0o444)
with (D / 'observations-original01.csv').open('x',newline='') as out:
    fields=['index','ts','fps','steps_per_sec','gpu1_util','gpu1_power_w','gpu1_mem_used_mib','train_sample_ms','train_step_ms']
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    out.flush();os.fsync(out.fileno());os.fchmod(out.fileno(),0o444)
os.chmod(D/'observations-original01.jsonl',0o444)
print(json.dumps(report),flush=True)
