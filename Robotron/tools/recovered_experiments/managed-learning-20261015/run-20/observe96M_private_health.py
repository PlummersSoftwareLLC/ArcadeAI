#!/usr/bin/env python3
"""Bounded read-only private health observer; never retains partial scores."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

RUN = Path(__file__).resolve().parent
JOB = RUN.parent / 'sidecar-gpu0-96M-regression-guard-01'
START = json.loads((RUN / 'quality96M-first-startup-independent-audit.json').read_bytes())
MAIN = json.loads((RUN / 'actor192-all-connected.json').read_bytes())

def identity(pid):
    try:
        values = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return dict(start_ticks=int(values[19]), state=values[0])
    except (FileNotFoundError, ProcessLookupError):
        return None

main_identity = {str(pid): identity(pid) for pid in MAIN['mame_pids']}
status = json.loads((JOB / 'status.json').read_bytes())
deadline = time.monotonic() + max(30, min(1230, 1230 - status['elapsed_s']))
output = RUN / 'quality96M-first-private-health.jsonl'
started = datetime.now(timezone.utc).isoformat()
index = 0
with output.open('x') as stream:
    while True:
        now = datetime.now(timezone.utc).isoformat()
        row = dict(utc=now, index=index, partial_scores_inspected=False)
        try:
            status = json.loads((JOB / 'status.json').read_bytes())
            # Explicitly whitelist fields; no row, score, mean or interval is retained.
            row.update({key: status.get(key) for key in ('phase', 'active', 'complete', 'valid', 'reason', 'generation', 'elapsed_s', 'clocks', 'boundary')})
            cohort = status.get('cohort') or {}
            row['cohort_health'] = {key: cohort.get(key) for key in ('started', 'count', 'pending', 'abandoned', 'closed', 'complete', 'valid')}
            row['private_actor_identity_matches'] = {slot: (identity(p['pid']) or {}).get('start_ticks') == p['start_ticks'] for slot, p in START['actors'].items()}
            row['private_actor_timeout_counts'] = {slot: (JOB / 'actors' / slot / 'console.log').read_text(errors='replace').count('[SOCKET ACTION TIMEOUT]') for slot in START['actors']}
            row['runner_identity_matches'] = (identity(START['runner']['pid']) or {}).get('start_ticks') == START['runner']['start_ticks']
            row['main_trainer_identity_matches'] = (identity(START['main']['trainer']['pid']) or {}).get('start_ticks') == START['main']['trainer']['start_ticks']
            row['main_pinned_actor_identity_matches'] = sum((identity(pid) or {}).get('start_ticks') == (initial or {}).get('start_ticks') for pid, initial in main_identity.items())
            row['receipt_exists'] = (JOB / 'receipt.json').is_file()
            row['faults'] = []
            if row['clocks'] != START['clocks']:
                row['faults'].append('private_clock_drift')
            if not row['main_trainer_identity_matches'] or row['main_pinned_actor_identity_matches'] != 192:
                row['faults'].append('main_identity_changed')
            if any(row['private_actor_timeout_counts'].values()):
                row['faults'].append('private_actor_timeout')
            if not row['complete'] and (not all(row['private_actor_identity_matches'].values()) or not row['runner_identity_matches']):
                row['faults'].append('private_process_missing_before_completion')
            if row['phase'] in ('collecting', 'draining') and not row['boundary'].get('ready'):
                row['faults'].append('private_boundary_not_ready')
        except (OSError, ValueError, KeyError) as error:
            row['read_error'] = str(error)
        stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        stream.flush()
        if index % 4 == 0 or row.get('faults') or row.get('receipt_exists'):
            print(json.dumps({key: row.get(key) for key in ('utc', 'phase', 'complete', 'cohort_health', 'faults', 'receipt_exists')}), flush=True)
        index += 1
        if row.get('receipt_exists') or time.monotonic() >= deadline:
            break
        time.sleep(min(15, max(0, deadline - time.monotonic())))
summary = dict(started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(), rows=index,
               receipt_exists=(JOB / 'receipt.json').is_file(), bounded=True,
               partial_scores_inspected=False, source_or_control_changes=False)
with (RUN / 'quality96M-first-private-health-complete.json').open('x') as stream:
    json.dump(summary, stream, indent=2)
    stream.write('\n')
print(json.dumps(summary), flush=True)
