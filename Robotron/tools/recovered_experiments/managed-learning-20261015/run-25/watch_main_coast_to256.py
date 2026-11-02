#!/usr/bin/env python3
"""Inert until explicit ROOT execution: bounded5s main-only operational coast."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import time
import urllib.request

RUN = Path(__file__).resolve().parent
GAME = RUN.parents[2]
TOOLS = RUN.parent / 'run-23/collector4096-ABA-tools'
HELPER_SHA = '0af645348876472190932002d28b7c70a08cc16078e0b10a7c5beec13965b2e5'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def selected_environment(pid):
    env = dict(item.split('=', 1) for item in Path('/proc', str(pid), 'environ').read_bytes().decode().split('\0') if '=' in item)
    return {key:value for key,value in env.items() if key.startswith(('DQN_', 'ROBOTRON_')) or key == 'CUDA_VISIBLE_DEVICES'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trainer-pid', required=True, type=int)
    parser.add_argument('--supervisor-pid', required=True, type=int)
    parser.add_argument('--actor-manifest', required=True, type=Path)
    parser.add_argument('--slot0-log', required=True, type=Path)
    parser.add_argument('--gate', default=RUN.parent / 'run-23/fresh3-256M-gate.json', type=Path, help='Existence/stat only; never reads future checkpoint/quality data')
    parser.add_argument('--deadline-utc', default='2026-10-16T22:00:00+00:00')
    args = parser.parse_args()
    deadline = datetime.fromisoformat(args.deadline_utc).timestamp()
    helper_path = TOOLS / 'observe_collector.py'
    helper_raw = helper_path.read_bytes()
    if digest(helper_raw) != HELPER_SHA:
        raise ValueError('Pinned corrected collector helper changed')
    spec = importlib.util.spec_from_file_location('main_coast_collector_guard', helper_path)
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    snapshot_errors, checker_pin = guard.load_health_check()
    manifest_raw = args.actor_manifest.read_bytes(); manifest = json.loads(manifest_raw)
    actors, supervisors = guard.manifest_identities(manifest, args.trainer_pid)
    if args.supervisor_pid not in supervisors:
        raise ValueError('Expected supervisor absent from actual current-run manifest')
    trainer = guard.process(args.trainer_pid)
    supervisor = guard.process(args.supervisor_pid)
    expected_supervisor = next(item for item in manifest['supervisor_identities'] if item['pid'] == args.supervisor_pid)
    if (not trainer['alive'] or not supervisor['alive']
            or trainer['start_ticks'] != manifest['trainer_start_ticks']
            or supervisor['start_ticks'] != expected_supervisor['start_ticks']):
        raise ValueError('Actual pinned current-run main ownership differs')
    attestation_path = RUN / 'startup-independent-process-source-observation.json'
    attestation_raw = attestation_path.read_bytes(); attestation = json.loads(attestation_raw)
    if (not attestation['PASS'] or attestation['pid'] != args.trainer_pid
            or attestation['start_ticks'] != trainer['start_ticks']
            or selected_environment(args.trainer_pid) != attestation['environment']):
        raise ValueError('Actual current-run environment/startup identity differs')
    expected_sources = {str(GAME.parent/name):value for name,value in attestation['source_hashes'].items()}
    expected_sources.update({str(GAME/name):value for name,value in attestation['private12_hashes'].items()})
    for name, expected in expected_sources.items():
        if digest(Path(name).read_bytes()) != expected:
            raise ValueError('Initial attested source differs: ' + name)
    source_stats = {name:guard.stat_id(Path(name)) for name in expected_sources}
    control = GAME / 'models_dqn/learning_control.json'; control_sha = digest(control.read_bytes())
    bindings = guard.actor_log_bindings(manifest['actors'], RUN, args.slot0_log)
    actor_logs = {Path(path):guard.AppendReader(Path(path)) for item in bindings.values() for path in item['paths']}
    console = guard.AppendReader(RUN / 'console.log'); csv_path = RUN / 'training.csv'
    csv_reader = guard.AppendReader(csv_path)
    with csv_path.open() as stream:
        csv_fields = next(csv.reader(stream))
    if not set(guard.CSV_FIELDS) <= set(csv_fields):
        raise ValueError('Current CSV loss/pressure schema differs')
    with csv_path.open('rb') as stream:
        stream.seek(max(0, csv_reader.initial_offset - 262144)); tail = stream.read(csv_reader.initial_offset-stream.tell())
    latest_csv = None
    for values in csv.reader(io.StringIO(tail.decode(errors='replace'))):
        if len(values) == len(csv_fields):
            item = dict(zip(csv_fields, values)); latest_csv = {key:item[key] for key in guard.CSV_FIELDS}
    drops = int(latest_csv['replay_dropped']) if latest_csv else None
    output = RUN / 'main-coast-to256-health.jsonl'
    completion_path = RUN / 'main-coast-to256-complete.json'
    startup_path = RUN / 'main-coast-to256-startup.json'
    if any(path.exists() for path in (output, completion_path, startup_path)):
        raise FileExistsError('Refuse existing/partial coast evidence')
    started, mono = time.time(), time.monotonic()
    startup = dict(schema='robotron-main-coast-to256-startup-v1',started_utc=guard.utc(started),observer_pid=os.getpid(),
        trainer_pid=args.trainer_pid,trainer_start_ticks=trainer['start_ticks'],supervisor_pid=args.supervisor_pid,
        supervisor_start_ticks=supervisor['start_ticks'],period_s=5,deadline_utc=guard.utc(deadline),gate=str(args.gate),
        helper=dict(path=str(helper_path),sha256=HELPER_SHA),exposure_checker=checker_pin,
        actor_manifest=dict(path=str(args.actor_manifest),sha256=digest(manifest_raw)),
        source_attestation=dict(path=str(attestation_path),sha256=digest(attestation_raw)),
        expected_sources=expected_sources,initial_source_stats=source_stats,initial_control_sha256=control_sha,
        actor_stdout_bindings=bindings,actor_log_path_order=[str(path) for path in actor_logs],actor_log_initial_offsets={str(path):dict(offset=r.initial_offset,
            initial_file_end=r.initial_end_offset,partial_prefix_bytes=r.initial_partial_prefix_bytes,file_identity=r.file_identity)
            for path,r in actor_logs.items()},initial_console_offset=console.initial_offset,initial_CSV_offset=csv_reader.initial_offset,
        scope='Main-only operational fault detection. Concurrent privateGPU0 jobs explicitly allowed; no private status/quality/game/score/model reads, GPU context, controls/process/source writes. Root alone decides actions. Fresh per-run counter baseline; no cross-process subtraction.')
    with startup_path.open('x') as stream:
        json.dump(startup,stream,indent=2);stream.write('\n')
    log_counts = dict.fromkeys(guard.ERROR_PATTERNS,0); actor_counts = dict.fromkeys(guard.ACTOR_PATTERNS,0)
    previous, last_guard, gate_seen, rows, last_tick = None, None, None, 0, None
    issues_seen, notices_seen, max_gap, gaps, last_issues = {}, {}, 0., [], []
    last_bank, bank_changes, bank_pairs, active_pair, previous_bank_row = None, [], [], None, None
    with output.open('x') as stream:
        while True:
            wall, tick = time.time(), time.monotonic()
            if wall >= deadline:
                end_reason = 'fixed2200UTC_deadline'; break
            row = dict(utc=guard.utc(wall),ts=wall,elapsed_s=tick-mono,issues=[],notices=[])
            if last_tick is not None:
                gap = tick-last_tick; max_gap=max(max_gap,gap)
                if gap>7.5:gaps.append(dict(utc=row['utc'],gap_s=gap))
            last_tick = tick
            try:
                with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=2) as response:api=json.load(response)
                current = {key:api.get(key) for key in guard.API_FIELDS}
                errors,notices = guard.validate_api(current,previous,args.trainer_pid,192,snapshot_errors)
                row['issues'].extend(errors);row['notices'].extend(notices);previous=current
                hp=current['host_pipeline'];bank=current['bank_persistence'];optimizer=hp['learning_exposure']['optimizer']
                row['health']=dict(API_ts=current['ts'],clocks={key:current[key] for key in guard.CLOCKS},
                    client_count=current['client_count'],loss=current['loss'],grad_norm=current['grad_norm'],
                    fps=current['fps'],avg_inf_ms=current['avg_inf_ms'],train_step_ms=current['train_step_ms'],
                    train_compute_ms=current['train_compute_ms'],train_priority_ms=current['train_priority_ms'],
                    gpu1_util=current['gpu1_util'],gpu1_power_w=current['gpu1_power_w'],
                    pipeline_identity={key:hp[key] for key in ('schema','generation','sample_every')},
                    graphs={key:hp['inference_graphs'][key] for key in ('ready','capture_count','validation_replay_count','postload_validations','runtime_capture_count','fallback_count','fatal_error')},
                    native={key:hp['native_batch_update'][key] for key in ('enabled','available','completed_count','success_count','fallback_count','error_count')},
                    learning_exposure=hp['learning_exposure'])
                row['bank']={key:bank[key] for key in ('capture_attempts','capture_deferrals','writes','write_failures','writer_active','last_error')}
                row['bank'].update(output_backend=bank['output']['backend'],output_active=bank['output']['active'],
                    phase_counts={key:{field:value[field] for field in ('count','errors')} for key,value in bank['output']['totals'].items()})
                signature=[row['bank'][key] for key in ('capture_attempts','writes','writer_active','write_failures')]
                if signature!=last_bank:bank_changes.append(dict(utc=row['utc'],API_ts=current['ts'],signature=signature));last_bank=signature
                if bank['writer_active'] and (previous_bank_row is None or not previous_bank_row['bank']['writer_active']):
                    active_pair=dict(last_idle_utc=previous_bank_row['utc'] if previous_bank_row else None,first_active_utc=row['utc'],first_active_API_ts=current['ts'],writes_before=previous_bank_row['bank']['writes'] if previous_bank_row else None)
                if active_pair and not bank['writer_active']:
                    active_pair.update(last_active_utc=previous_bank_row['utc'],first_idle_after_utc=row['utc'],first_idle_after_API_ts=current['ts'],writes_after=bank['writes']);bank_pairs.append(active_pair);active_pair=None
                previous_bank_row=row
            except (OSError,ValueError,KeyError,TypeError) as error:
                row['issues'].append('main_API_snapshot:'+repr(error))
            row['owners']=dict(trainer=guard.process(args.trainer_pid),supervisor=guard.process(args.supervisor_pid))
            if row['owners']['trainer']!=trainer or row['owners']['supervisor']!=supervisor:row['issues'].append('main_owner_identity_changed')
            row['actor_mismatches']=[pid for pid,start in actors.items() if guard.process(pid)!=dict(alive=True,start_ticks=start)]
            if row['actor_mismatches']:row['issues'].append('main_actor_identity_changed')
            if last_guard is None or wall-last_guard['checked_unix_s']>=60:
                try:
                    last_guard=dict(checked_unix_s=wall,source_stat_unchanged=all(guard.stat_id(Path(name))==value for name,value in source_stats.items()),
                        control_sha256=digest(control.read_bytes()),environment_unchanged=selected_environment(args.trainer_pid)==attestation['environment'],
                        manifest_unchanged=args.actor_manifest.read_bytes()==manifest_raw,
                        helper_unchanged=digest(helper_path.read_bytes())==HELPER_SHA,
                        actor_descriptors_unchanged=all(os.readlink('/proc/'+pid+'/fd/'+fd)==target for pid,binding in bindings.items() for fd,target in binding['descriptors'].items()))
                except OSError as error:last_guard=dict(checked_unix_s=wall,error=repr(error))
            row['source_environment_control_guard']=last_guard
            if last_guard.get('error') or not all(last_guard.get(key) for key in ('source_stat_unchanged','environment_unchanged','manifest_unchanged','helper_unchanged','actor_descriptors_unchanged')) or last_guard.get('control_sha256')!=control_sha:
                row['issues'].append('main_source_env_control_or_log_binding_changed')
            try:
                for line in console.read():
                    for marker in log_counts:log_counts[marker]+=line.count(marker)
                events=[]
                for path,reader in actor_logs.items():
                    for line in reader.read():
                        for marker in actor_counts:actor_counts[marker]+=line.count(marker)
                        if any(marker in line for marker in actor_counts):events.append(dict(path=str(path),line=line))
                row['new_actor_transport_events']=events
                new_csv=[]
                for values in csv.reader(csv_reader.read()):
                    if len(values)!=len(csv_fields):raise ValueError('CSVappendshapechanged')
                    item=dict(zip(csv_fields,values));latest_csv={key:item[key] for key in guard.CSV_FIELDS};new_csv.append(latest_csv)
                    if drops is None:drops=int(latest_csv['replay_dropped'])
                    if int(latest_csv['replay_dropped'])!=drops:row['issues'].append('CSVnewreplaydrop')
                row['new_CSV_queue_signals']=new_csv;row['latest_CSV_queue_signals']=latest_csv
            except (OSError,ValueError,KeyError) as error:row['issues'].append('appendread:'+repr(error))
            row['main_log_counts']=dict(log_counts);row['actor_transport_counts']=dict(actor_counts)
            if any(log_counts.values()) or any(actor_counts.values()):row['issues'].append('main_training_compile_transport_or_actorlog_error')
            row['append_offsets']=dict(console=console.offset,csv=csv_reader.offset,actor_logs_in_startup_path_order=[reader.offset for reader in actor_logs.values()])
            if args.gate.exists():
                if gate_seen is None:gate_seen=wall
                q=args.gate.stat();row['queued256_gate_observed']=dict(first_seen_unix_s=gate_seen,size=q.st_size,mtime_ns=q.st_mtime_ns,inode=q.st_ino)
            row['issues']=sorted(set(row['issues']));row['notices']=sorted(set(row['notices']))
            for issue in row['issues']:issues_seen[issue]=issues_seen.get(issue,0)+1
            for notice in row['notices']:notices_seen[notice]=notices_seen.get(notice,0)+1
            if row['issues'] and row['issues']!=last_issues:print(json.dumps(dict(ALERT=row['utc'],issues=row['issues'])),flush=True)
            last_issues=row['issues'];stream.write(json.dumps(guard.safe(row),allow_nan=False,separators=(',',':'))+'\n');stream.flush();rows+=1
            if gate_seen is not None and wall>=gate_seen+120:
                end_reason='actual256_gate_plus120s';break
            time.sleep(max(0,mono+rows*5-time.monotonic()))
    report=dict(schema='robotron-main-coast-to256-complete-v1',started_utc=guard.utc(started),finished_utc=guard.utc(),observer_pid=os.getpid(),
        rows=rows,elapsed_s=time.monotonic()-mono,end_reason=end_reason,gate_first_seen_unix_s=gate_seen,largest_poll_gap_s=max_gap,gaps=gaps,
        issues=issues_seen,notices=notices_seen,bank_signature_changes=bank_changes,bank_pair_metadata_brackets=bank_pairs,
        unfinished_bank_pair=active_pair,main_pid=args.trainer_pid,supervisor_pid=args.supervisor_pid,
        final_console_offset=console.offset,final_CSV_offset=csv_reader.offset,
        final_actor_log_offsets={str(path):reader.offset for path,reader in actor_logs.items()},
        scope='Allrawrows/faults/notices retained; no quality/model/privatejob reads, GPUcontext or control/process/source actions. ConcurrentprivateGPU0 jobs allowed; no formalperformance/reliability inference. Rootalone decidesactions.')
    with completion_path.open('x') as stream:json.dump(guard.safe(report),stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(complete_utc=report['finished_utc'],rows=rows,issues=issues_seen,end_reason=end_reason)),flush=True)


if __name__=='__main__':main()
