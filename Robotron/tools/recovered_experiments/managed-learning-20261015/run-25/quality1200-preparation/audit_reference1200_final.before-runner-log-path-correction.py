"""Bounded final reference audit. Default/help are inert; --execute needs full receipt.

No promotion/reference selection, model load, GPU context or process control.
Only the NEW private checkpoint copy is byte-hashed after complete owned cleanup.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

HERE=Path(__file__).resolve().parent; RUN=HERE.parent; CAMPAIGN=RUN.parent; GAME=CAMPAIGN.parents[1]
LABELS=('sidecar-gpu0-192M-reference1200-01','sidecar-gpu0-192M-reference1200-02')
SLOTS=list(range(4096,4112)); GPU0='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'; GB='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'
REF_HELPER_SHA='62370f2a77facc20b75777b47de3c06f3dfdfa8210133e39b8d9dcbdd5c6251b'
REF_PLAN_SHA='6560765fbf787f78bc033a9c0cee8ace59ea76ecb52e74e4dcc70049fabe488e'
EXPECTED='5076199285752a8748ce9566bc74c6b67210a03ae7f04f132f92b786dea102da'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):
 raw=Path(path).read_bytes();return json.loads(raw),raw

def identity(pid):
 try:
  fields=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
  return dict(present=True,start_ticks=int(fields[19]),state=fields[0])
 except (OSError,ValueError,IndexError):return dict(present=False,start_ticks=None,state=None)

def execute(label,runner_pid):
 job=CAMPAIGN/label;number=label[-2:];prefix='quality1200-reference'+number
 receipt,raw=read(job/'receipt.json')
 if receipt.get('complete') is not True:raise ValueError('Refuse partial reference receipt')
 complete_path=RUN/(label+'-scoreblind-health-complete.json');complete,complete_raw=read(complete_path)
 if not (complete['runner_pid']==runner_pid and complete['label']==label and complete['final_health']['complete'] is True
         and complete['final_owned_processes_remaining']==[]):raise ValueError('Wait for final owned score-blind registry before copy hash')
 plan,plan_raw=read(HERE/'quality1200-plan.json');assert sha(plan_raw)==REF_PLAN_SHA
 ref_source=(HERE/'quality1200_reference.py').read_bytes();assert sha(ref_source)==REF_HELPER_SHA
 spec=importlib.util.spec_from_file_location('final1200_frozen_reference',HERE/'quality1200_reference.py')
 ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref);shared=ref.shared_module()
 sys.path.insert(0,str(GAME/'tools'))
 from compare_sidecar_measurements import validate_backend,JOB_FIELDS
 from compare_frozen_measurements import FRAME_FIELDS
 from sidecar_boot import load_snapshot
 class CopyEvidence:
  def __init__(self):self.pins=[]
  def file(self,path,expected):
   value=sha(Path(path).read_bytes());assert value==expected,'Changed new private copy';self.pins.append(dict(path=str(path),sha256=value));return Path(path)
 saved=plan['reference']['saved_metadata'];protected=Path(plan['reference']['checkpoint']['path'])
 initial,initial_raw=read(RUN/(prefix+'-initial-proc-isolation.json'))
 boundary,boundary_raw=read(RUN/(prefix+'-initial-boundary-transport.json'))
 tree,tree_raw=read(RUN/(prefix+'-owned-process-tree.json'))
 registry={int(row['pid']):dict(row) for row in tree['processes']}
 for pid,start in complete['owned_private_identity'].items():
  pid=int(pid);detail=complete['owned_private_details'][str(pid)]
  if pid in registry:assert registry[pid]['start_ticks']==start,'Conflicting owned identity'
  else:registry[pid]=dict(pid=pid,start_ticks=start,ppid=detail['ppid'],first_observed_utc=detail['first_observed_utc'],scope='Additional all-task recursive watcher observation')
 remaining=[row for row in registry.values() if identity(row['pid'])['present'] and identity(row['pid'])['start_ticks']==row['start_ticks']]
 if remaining:raise ValueError('Wait for ALL initial and watcher-observed private identities before copy hash')
 evidence=CopyEvidence();leg=ref.validate_reference_leg(receipt,label,plan,evidence,
     type('Tools',(),dict(validate_backend=staticmethod(validate_backend),JOB_FIELDS=JOB_FIELDS)),shared)
 copyhash=evidence.pins[0]['sha256']
 assert copyhash==receipt['checkpoint_sha256']==plan['reference']['checkpoint']['sha256']==EXPECTED
 listeners=[]
 for table in ('/proc/net/tcp','/proc/net/tcp6'):
  for line in Path(table).read_text().splitlines()[1:]:
   parts=line.split()
   if int(parts[1].split(':')[1],16)==9999 and parts[3]=='0A':listeners.append(dict(table=table,line=line))
 probe=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,process_name','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
 gpu=[tuple(x.strip() for x in line.split(',')) for line in probe.stdout.splitlines() if line.strip()]
 private_gpu=[row for row in gpu if row[1]==GPU0]; main_gpu=[row for row in gpu if row[0]=='2148801']
 actual_sources={name:sha((GAME/name).read_bytes()) for name in receipt['source_hashes']}
 timeout_counts={};actor_logs=[]
 for slot in SLOTS:
  path=job/'actors'/str(slot)/'console.log';blob=path.read_bytes();text=blob.decode(errors='replace');events=[]
  for line in text.splitlines():
   if '[SOCKET ACTION TIMEOUT]' in line:
    match=re.search(r'\bunix_s=(\d+)\b',line);events.append(int(match[1]) if match else None)
  before=receipt['actor_timeout_logs_before_shutdown'][str(slot)]
  runtime=max(before,sum(i<before or ts is None or ts<=int(receipt['timeout_snapshot_unix_s']) for i,ts in enumerate(events)))
  timeout_counts[str(slot)]=dict(before=before,events_unix_s=events,runtime=runtime,after=len(events),cleanup_only=max(0,len(events)-runtime))
  actor_logs.append(dict(slot=slot,path=str(path),bytes=len(blob),sha256=sha(blob),transport_error_markers={marker:text.count(marker) for marker in ['Socket read error:','Socket write error:','Socket open failed:']}))
 health_path=RUN/(label+'-scoreblind-health.jsonl');health_raw=health_path.read_bytes();health_raw=health_raw[:health_raw.rfind(b'\n')+1]
 health=[json.loads(line) for line in health_raw.splitlines()];cutoff=receipt['timeout_snapshot_unix_s']
 runtime_issues=[];cleanup_issues=[]
 for row in health:
  for issue in row.get('issues',[]):
   (cleanup_issues if row['ts']>=cutoff else runtime_issues).append(dict(utc=row['utc'],ts=row['ts'],issue=issue))
 private_log_path=RUN/(label+'.log');private_log=private_log_path.read_bytes();private_text=private_log.decode(errors='replace')
 traceback_parts=private_text.split('Traceback (most recent call last):')[1:]
 exception_lines=[]
 for part in traceback_parts:
  exceptions=[line.strip() for line in part.splitlines() if re.match(r'^[A-Za-z][\w.]*?(?:Error|Exception):',line)]
  exception_lines.append(exceptions[0] if exceptions else None)
 known_stops={'RuntimeError: Inference batcher stopped before completion','RuntimeError: Inference batcher stopped before dispatch'}
 stop_source=(GAME/'Scripts/dqn/socket_server.py').read_text();runner_source=(GAME/'tools/run_frozen_sidecar.py').read_text()
 # Only the explicit batcher.stop messages can qualify; unknown/genuine faults stay bad.
 cleanup_block=runner_source.split('def cleanup_with_timeout_evidence(',1)[1]
 server_stop=stop_source.rsplit('    def stop(self):',1)[1]
 source_order=(cleanup_block.index('server.shutdown_event.set()')<cleanup_block.index('snapshot_unix_s = clock()')<cleanup_block.index('errors = cleanup_job(')
     and server_stop.index('self.shutdown_event.set()')<server_stop.index('self.inference_batcher.stop()')
     and all(stop_source.count(line.split(': ',1)[1])==1 for line in known_stops))
 stack_classified=(not traceback_parts or (all(line in known_stops for line in exception_lines)
     and source_order
     and all(row['ts']>=cutoff for row in cleanup_issues)
     and not runtime_issues and not receipt.get('server_error') and not receipt.get('inference_error')))
 if cleanup_issues:
  allowed={'new_main_or_private_runtime_error_log'}
  stack_classified=stack_classified and bool(traceback_parts) and all(row['issue'] in allowed for row in cleanup_issues)
  for row in health:
   counts=row['runtime_log_pattern_counts']
   for path,values in counts.items():
    if str(path)==str(RUN/'console.log'):stack_classified=stack_classified and not any(values.values())
    else:stack_classified=stack_classified and all(count==0 for pattern,count in values.items() if pattern!='Traceback (most recent call last):')
 with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as stream:api=json.load(stream)
 manifest,manifest_raw=read(RUN/'actor192-all-connected.json');source_observation,_=read(RUN/'startup-independent-process-source-observation.json')
 main_actors=[dict(pid=row['pid'],slot=row['slot'],same_start_ticks=identity(row['pid'])['start_ticks']==row['start_ticks']) for row in manifest['actors']]
 tee=source_observation['tee'];tee_visible=False
 for row in tee:
  for fd in row['fds']:
   try:tee_visible=tee_visible or os.readlink('/proc/'+str(row['pid'])+'/fd/'+str(fd))=='/dev/pts/2'
   except OSError:pass
 numeric=receipt['numeric_policy'];private_stat=Path(receipt['checkpoint_path']).stat();source_stat=protected.stat()
 live_boot=load_snapshot(Path(plan['backend']['job']['boot_assets']))
 live_shim_sha=sha(Path(receipt['socket_wait']['library']).read_bytes())
 source_guard_good=all(row['source_control_guard']['source20_private12_unchanged'] and row['source_control_guard']['main_actors_matched']==192 and not row['source_control_guard']['main_actor_mismatched_pids'] for row in health)
 main_health_good=all(row.get('main_health',{}).get('client_count')==192 and not row.get('main_API_error') for row in health)
 checks=dict(receipt_valid_complete_full_admitted_cohort=receipt['valid'] is True and receipt['active'] is False and receipt['phase']=='finished' and receipt['cohort']['started']==receipt['cohort']['count']==receipt['count']==len(leg['rows']) and receipt['cohort']['pending']==receipt['cohort']['abandoned']==0,
  official_fulltail_backend_and_matched1200_protocol_passed=True,protected192_identity_saved_clocks_no_defaulted_fields=copyhash==EXPECTED and not receipt['checkpoint_metadata']['defaulted_metadata_fields'] and all(receipt['checkpoint_metadata'][k]==saved[k] for k in shared.META_KEYS) and all(receipt['clocks'][k]==saved[k] for k in shared.CORE_CLOCKS),
  private_copy_independent_readonly=private_stat.st_nlink==1 and private_stat.st_mode&0o777==0o444 and (private_stat.st_dev,private_stat.st_ino)!=(source_stat.st_dev,source_stat.st_ino),
  private_owned_processes_listener_released=not remaining and not listeners,
  private_GPU0_context_released=probe.returncode==0 and not private_gpu,
  loaded_sources_unchanged=receipt['source_hashes']==receipt['ended_source_hashes']==actual_sources==plan['backend']['source_hashes'],
  protected_stat_boot_seed_and_shim_unchanged=ref.full_stat(protected)==plan['reference']['checkpoint']['stat'] and live_boot['identity']==plan['backend']['boot_identity'] and live_boot['files']==plan['backend']['boot_files'] and live_shim_sha==plan['backend']['socket_wait_sha256'],
  initial_replay_FD_GPU_and_boundary_isolation=boundary['PASS'] and all(boundary['checks'].values()) and not initial['real_replay_model_fd_matches'] and not initial['real_replay_model_mmap_matches'],
  all16_highslot_boundaries_and_starters=receipt['boundary']['ready'] and receipt['boundary']['clients']==receipt['boundary']['expected']==receipt['boundary']['acknowledged']==16 and receipt['boundary']['actor_slots']==SLOTS and not receipt['boundary']['pending_client_ids'] and not receipt['boundary']['replay_pending_client_ids'] and receipt['cohort']['started_actor_slots']==SLOTS,
  actual_FP32_TF32_compiled_warm1to16=numeric['weights']==numeric['inputs']=='float32' and numeric['cuda_matmul_allow_tf32'] is True and numeric['cudnn_allow_tf32'] is True and receipt['compile_report']['all_shapes_verified']==list(range(1,17)),
  runtime_timeouts0_teardown_diagnostics_match=all(row['runtime']==receipt['actor_timeout_logs'][slot]==0 and row['after']==receipt['actor_timeout_logs_after_shutdown'][slot] and row['cleanup_only']==receipt['actor_cleanup_timeout_logs'][slot] for slot,row in timeout_counts.items()),
  no_server_inference_cleanup_invalidity_errors=not any(receipt.get(key) for key in ['server_error','inference_error','cleanup_errors','invalidity_reasons']),
  no_unclassified_actor_transport_error_markers=all(not any(row['transport_error_markers'].values()) for row in actor_logs),
  scoreblind_prefix_complete_and_owned_union=bool(health) and health[-1]['private']['complete'] is True and health[-1]['ts']>=receipt['ended_unix_s'] and complete['final_health']['complete'] is True and complete['rows']==len(health),
  health_runtime_faults0_raw_cleanup_alerts_classified=not runtime_issues and stack_classified,
  all192_main_identity_source_control_and_GPU_preserved=all(row['same_start_ticks'] for row in main_actors) and api['client_count']==192 and api['measurement_active'] is False and identity(2148801)['start_ticks']==source_observation['start_ticks'] and identity(2149551)['start_ticks']==manifest['supervisor_identities'][0]['start_ticks'] and main_health_good and source_guard_good and bool(main_gpu) and all(row[1]==GB for row in main_gpu),
  main_clocks_advance_console_pts2=api['optimized_samples']>initial['main_API']['optimized_samples'] and api['learner_frame_count']>initial['main_API']['learner_frame_count'] and tee_visible)
 report=dict(schema='robotron-quality1200-reference-final-isolation-cleanup-audit-v1',utc=datetime.now(timezone.utc).isoformat(),label=label,
  **{'pass':all(checks.values())},checks=checks,receipt_path=str(job/'receipt.json'),receipt_sha256=sha(raw),checkpoint_sha256=EXPECTED,checkpoint_copy_sha256=copyhash,
  full_games=receipt['count'],saved_metadata=receipt['checkpoint_metadata'],numeric_policy=numeric,compile_report=receipt['compile_report'],official_frozen_protocol=leg['protocol'],source_hashes=actual_sources,
  initial_audit=dict(path=str(RUN/(prefix+'-initial-boundary-transport.json')),sha256=sha(boundary_raw)),
  owned_union=dict(processes=sorted(registry.values(),key=lambda row:row['pid']),initial_tree_sha256=sha(tree_raw),watcher_completion_sha256=sha(complete_raw),remaining=remaining,limitation='All observed identities checked. Watcher began after warmup; earlier unobserved compiler transients are not asserted. Whole-job port and GPU context absence checked independently.'),
  remaining_9999_listeners=listeners,NVML=dict(returncode=probe.returncode,compute_apps=probe.stdout.strip()),timeout_accounting=timeout_counts,actor_log_byte_pins=actor_logs,
  scoreblind_prefix=dict(path=str(health_path),bytes=len(health_raw),sha256=sha(health_raw),rows=len(health),start_utc=health[0]['utc'],end_utc=health[-1]['utc'],runtime_issues=runtime_issues,cleanup_issues_retained=cleanup_issues),
  private_stack_diagnostics=dict(log_path=str(private_log_path),bytes=len(private_log),sha256=sha(private_log),tracebacks=len(traceback_parts),exception_lines=exception_lines,known_batcher_stop_only=stack_classified,source_order_verified=source_order,cutoff_unix_s=cutoff,scope='Raw alerts preserved. Known message source path plus official final runtime0/error-free receipt classify intentional shutdown, not blanket all-log zero or exact timestamp for untimed stacklines.'),
  main192_final_identity=main_actors,main_API_clocks={key:api[key] for key in ['ts','client_count','training_steps','optimized_samples','learner_frame_count','frame_count','measurement_active']},
  main_bank_signature_changes=[],auxiliary_work_disclosures=[dict(scope='Bounded synthetic future-assessment fixture work overlapped this fixed private leg; no actual partial outcomes/model/Torch/GPU reads.',intervals_UTC=[['2026-10-16T17:58:19.496941+00:00','2026-10-16T17:58:19.761500+00:00'],['2026-10-16T17:58:38.545838+00:00','2026-10-16T17:58:38.860674+00:00']],known_test_PIDs=[2213465,2214506],preserved_receipts=['assessment-fixture-validation-v2.json','assessment-fixture-validation-v3.json']),dict(scope='Lightweight root polls, this watcher/initial proc-source audit, prospective source/fixture preparation and natural main autosaves/bank pairs may overlap; raw health/bank signatures retained. No isolated performance/reliability or policy-quality causality is inferred.')],scope='Final complete receipt only; one NEW private-copy hash, protected stat and prior root identity, no protected payload hash/Torch/model load/GPU context/control/source/state changes. This proves isolation/cleanup, not quality thresholds, numeric cross-process equivalence or universal reliability.')
 last=None
 for row in health:
  bank=row.get('main_bank_health',{});signature=(bank.get('capture_attempts'),bank.get('writes'),bank.get('writer_active'))
  if signature!=last:report['main_bank_signature_changes'].append(dict(observer_UTC=row['utc'],API_ts=row['main_health']['API_ts'],metadata=bank));last=signature
 out=RUN/(prefix+'-final-isolation-audit.json');data=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
 fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o444)
 try:os.write(fd,data);os.fchmod(fd,0o444);os.fsync(fd)
 finally:os.close(fd)
 print(json.dumps(dict(path=str(out),sha256=sha(data),**{'pass':report['pass']},failed=[k for k,v in checks.items() if not v],checks=len(checks),full_games=receipt['count'])))
 return 0 if report['pass'] else 1

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--label',choices=LABELS);parser.add_argument('--runner-pid',type=int)
 args=parser.parse_args(argv)
 if not args.execute:print(json.dumps(dict(mode='PLAN_ONLY_NO_EVIDENCE_READS',launch=False)));return 0
 if not args.label or not args.runner_pid:parser.error('Explicit completed reference label/runner PID required')
 return execute(args.label,args.runner_pid)
if __name__=='__main__':raise SystemExit(main())
