"""One bounded read-only pass of the root-pinned192 actors and current-log prefixes."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,re,time,urllib.request
base=Path(__file__).resolve().parent;repo=base.parents[3];game=repo/'Robotron'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def prefix(path):
 raw=path.read_bytes();return raw[:raw.rfind(b'\n')+1]
started=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
manifest_path=base/'actor192-all-connected.json';manifest_raw=manifest_path.read_bytes();m=json.loads(manifest_raw)
assert m['trainer_pid']==1436155 and m['client_count']==192 and len(m['actors'])==192
assert {a['slot'] for a in m['actors']}==set(range(192))
assert {a['pid'] for a in m['actors']}==set(m['mame_pids'])
old=json.loads((base.parent/'run-22/actor192-all-connected.json').read_text())
startup=json.loads((base/'startup-root-record.json').read_text());cutover=datetime.fromisoformat(startup['utc']).timestamp()
expected_shim='13d496b6f268d28c0b732e88635c0e05c7eaa5f7aa622d4e783767b0ace2ff4d'
actors=[];logs=[];shims={};paths={}
patterns=['[SOCKET ACTION TIMEOUT]','[SOCKET RECV ERROR]','[SOCKET SEND ERROR]']
for expected in m['actors']:
 pid=expected['pid'];slot=expected['slot'];p=Path('/proc')/str(pid)
 start_ticks=int(p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]);exe=os.readlink(p/'exe')
 env=dict(item.split('=',1) for item in p.joinpath('environ').read_bytes().decode().split('\0') if '=' in item)
 fields={k:env.get(k) for k in ['ROBOTRON_CLIENT_SLOT','ROBOTRON_SOCKET_WAIT_US','ROBOTRON_SOCKET_WAIT_PORT','ROBOTRON_SOCKET_ADDRESS','ROBOTRON_SOCKET_WAIT_LIBRARY','LD_PRELOAD','MAME_BIN','ROBOTRON_EVAL_MODE','ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES']}
 library=fields['ROBOTRON_SOCKET_WAIT_LIBRARY'];assert library
 if library not in shims:shims[library]=digest(Path(library).read_bytes())
 cmdline=p.joinpath('cmdline').read_bytes().replace(b'\0',b' ').decode()
 mapped=library in p.joinpath('maps').read_text()
 fds={fd:os.readlink(p/'fd'/fd) for fd in ['1','2']};assert fds['1']==fds['2']
 okay=(start_ticks==expected['start_ticks'] and exe=='/usr/games/mame' and mapped and fields['ROBOTRON_CLIENT_SLOT']==str(slot) and fields['ROBOTRON_SOCKET_WAIT_US']=='1000' and fields['ROBOTRON_SOCKET_WAIT_PORT']=='9998' and fields['ROBOTRON_SOCKET_ADDRESS']=='dell:9998' and fields['LD_PRELOAD']==library and fields['MAME_BIN']==str(game/'tools/mame_with_socket_wait.sh') and fields['ROBOTRON_EVAL_MODE']=='0' and fields['ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES']=='0' and '-nothrottle' in cmdline and str(game/'Scripts/main.lua') in cmdline)
 actors.append(dict(pid=pid,slot=slot,start_ticks=start_ticks,shim_mapped=mapped,exe=exe,environment=fields,stdout_stderr=fds,PASS=okay))
 path=Path(fds['1']);raw=prefix(path);paths[str(path)]=dict(complete_prefix_bytes=len(raw),complete_prefix_sha256=digest(raw))
 activation=list(re.finditer(rb'\[robotron-socket-wait\] pid='+str(pid).encode()+rb' fd=(\d+) port=(\d+) interval_us=(\d+)',raw))
 offset=activation[0].start() if len(activation)==1 else -1
 record=[v.decode() for v in activation[0].groups()] if len(activation)==1 else []
 segment=raw[offset:] if offset>=0 else b''
 errors={s:segment.count(s.encode()) for s in patterns}
 current=[]
 for line in raw.splitlines():
  if b'[SOCKET ACTION TIMEOUT]' not in line:continue
  found=re.search(rb'unix_s=([0-9]+(?:\.[0-9]+)?)',line)
  if found and float(found[1])>=cutover:current.append(line.decode(errors='replace'))
 logs.append(dict(pid=pid,slot=slot,path=str(path),complete_prefix_bytes=len(raw),complete_prefix_sha256=digest(raw),current_PID_activation_count=len(activation),current_PID_activation=record,current_PID_segment_byte_offset=offset,current_PID_segment_errors=errors,post_cutover_embedded_action_timeouts=current,PASS=len(activation)==1 and record[1:]==['9998','1000'] and not any(errors.values()) and not current))
api=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3));g=api['host_pipeline']['inference_graphs'];n=api['host_pipeline']['native_batch_update']
main_prefix=prefix(base/'console.log');main_patterns=['Training error:','Traceback','Batched inference request timed out','Batched inference failed','disabling torch.compile','torch.compile unavailable','Non-finite loss']
main_errors={s:main_prefix.count(s.encode()) for s in main_patterns}
checks=dict(all192_pinned_PIDs_startticks_exe_env_shim_map=all(a['PASS'] for a in actors),slots_exact0to191={a['slot'] for a in actors}==set(range(192)),API192_slots_exact=api['client_count']==192 and {a['client_slot'] for a in api['client_rows']}==set(range(192)),supervisor_pinned_present=all(Path('/proc',str(p)).exists() for p in m['supervisor_pids']),old_owned_mame_PIDs_all_gone=all(not Path('/proc',str(p)).exists() for p in old['mame_pids']),one_expected_shim_content=len(shims)==1 and set(shims.values())=={expected_shim},main_error_counts0=not any(main_errors.values()),graph_ready128_no_runtimecapture_fallback_fatal=g['ready'] and g['capture_count']==128 and g['runtime_capture_count']==0 and g['fallback_count']==0 and g['fatal_error'] is None,native_success_no_fallback_error=n['enabled'] and n['available'] and n['completed_count']==n['success_count'] and n['success_count']>1 and n['fallback_count']==n['error_count']==0,metadata_read_errors0=not api['pipeline_read_error'] and not api['bank_persistence_read_error'],exposure_route_enabled='learning_exposure' in api['host_pipeline'],all192_own_actor_logs_activation1_current_timeout_errors0=all(a['PASS'] for a in logs))
exposure=api['host_pipeline']['learning_exposure'];opt=exposure['optimizer'];replay=exposure['replay']
baseline=json.loads((base/'startup-readonly-independent-audit.json').read_text())['learning_exposure']
pending=opt['unclassified_started_total'];total=opt['total'];sources=replay['accepted_by_source_total']
checks.update(exposure_same_process_load_epochs=all(exposure[name]['process_id']==1436155 and exposure[name]['epoch']==baseline[name]['epoch'] and exposure[name]['instance_monotonic_ns']==baseline[name]['instance_monotonic_ns'] for name in ['optimizer','replay']),replay_new_learner_admissions_known_sources=replay['accepted_total']>0 and replay['accepted_learner_total']>0 and replay['accepted_total']==sum(sources.values()) and replay['accepted_learner_total']==sources['dqn']+sources['epsilon'] and sources['unattributed']==0,optimizer_known_completed_outcomes_no_unavailable=total['outcomes_recorded']>1 and total['unavailable']==0 and total['outcomes_recorded']==total['applied']+total['amp_skipped'] and opt['prior_epoch_outcomes_total']==0,optimizer_pending_at_most_one=pending in (0,1) and total['attempts_started']-total['outcomes_recorded']==pending and opt['available']==(pending==0))
assert manifest_path.read_bytes()==manifest_raw
assert all(checks.values()),checks
report=dict(schema='robotron-run23-independent-ramp-audit-v1',PASS=True,checks=checks,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_s=time.monotonic()-tick,pid=os.getpid(),manifest=dict(path=str(manifest_path.relative_to(repo)),sha256=digest(manifest_raw),actual_pin_utc=m['utc'],settle_boundary_unix_s=m['ts']+90),trainer_pid=m['trainer_pid'],supervisor_pids=m['supervisor_pids'],actors=actors,shim_hashes=shims,main_log=dict(path=str(base/'console.log'),complete_prefix_bytes=len(main_prefix),complete_prefix_sha256=digest(main_prefix)),main_error_counts=main_errors,API_snapshot_ts=api['ts'],graph_route={k:g[k] for k in ['capture_count','ready','replay_count','cpu_return_rows','runtime_capture_count','fallback_count','fatal_error']},native=n,learning_exposure=exposure,exposure_interpretation='Counters are process-local. Imported6M excluded; accepted learner means successful post-nstep dqn+epsilon ring.add, not wire frames/resident partition counts. Applied=optimizer call admitted; skipped and saved per-parameter Adam clocks remain separate. Transient pending<=1 can make availableFalse; no unavailable outcomes observed.',all192_actor_logs=logs,cutover_unix_s=cutover,scope='Read-only single pass of kernel proc and complete log byte prefixes. No Torch/model/GPU work or process/control/source mutation.',limits=['Per-instance actor logs are appended across runs; exact current-PID activation offsets and embedded timeout timestamps separate current evidence from retained historical errors.','This is startup/ramp health, not a throughput or learning-quality selection result. All observation overlaps must remain disclosed without moving prospective performance boundaries.'])
path=base/'startup-independent-ramp-audit.json'
with path.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(PASS=True,checks_passed=len(checks),path=str(path),sha256=digest(path.read_bytes()),started_utc=report['started_utc'],finished_utc=report['finished_utc'],elapsed_s=report['elapsed_s'],pid=report['pid'],all192_current_logs_errors0=True)))
