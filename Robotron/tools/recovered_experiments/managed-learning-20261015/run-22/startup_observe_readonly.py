"""Read-only run22 default-compiler return startup evidence; no CUDA imports."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os,re,time,urllib.request
base=Path(__file__).resolve().parent;repo=base.parents[3];game=repo/'Robotron'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(name,data):
 with (base/name).open('x') as f:json.dump(data,f,indent=2);f.write('\n')
start=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
root=json.loads((base/'startup-root-record.json').read_text());pid=root['pid'];p=Path('/proc')/str(pid)
proc_start=int(p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19])
env=dict(item.split('=',1) for item in p.joinpath('environ').read_bytes().decode().split('\0') if '=' in item)
expected=json.loads((base/'resume-environment.json').read_text())
selected={k:v for k,v in env.items() if k.startswith(('ROBOTRON_','DQN_')) or k=='CUDA_VISIBLE_DEVICES'}
assert selected==expected and env.get('LD_PRELOAD') is None
prior=json.loads((base.parent/'run-21/startup-independent-process-source-observation.json').read_text())
source={k:sha(repo/k) for k in prior['source_hashes']};private={k:sha(game/k) for k in prior['private12_hashes']}
assert source==prior['source_hashes'] and private==prior['private12_hashes']
assert not (game/'Scripts/dqn/learning_exposure.py').exists()
def delta(a,b):return {k:[a.get(k),b.get(k)] for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}
actual_delta=delta(prior['environment'],selected)
assert set(actual_delta)=={'ROBOTRON_RUN_DIR','DQN_COMPILE_MODE'} and selected['DQN_COMPILE_MODE']=='default'
cmdline=p.joinpath('cmdline').read_bytes().replace(b'\0',b' ').decode();assert '-Xgil=0' in cmdline
tee=[]
for ent in Path('/proc').iterdir():
 if not ent.name.isdecimal():continue
 try:
  cmd=ent.joinpath('cmdline').read_bytes().replace(b'\0',b' ').decode()
  if cmd.startswith('tee ') and str(base.relative_to(game))+'/console.log' in cmd:
   fds={fd.name:os.readlink(fd) for fd in ent.joinpath('fd').iterdir()}
   tee.append(dict(pid=int(ent.name),cmdline=cmd,fds=fds))
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
assert len(tee)==1 and str(base/'console.log') in tee[0]['fds'].values() and '/dev/pts/2' in tee[0]['fds'].values()
observation=dict(schema='robotron-run22-independent-process-source-v1',utc=start,PASS=True,pid=pid,start_ticks=proc_start,cmdline=cmdline,environment=selected,environment_delta_vs_run21=actual_delta,other_runtime_environment={k:v for k,v in env.items() if k.startswith('CUDA_') and k not in selected},source_hashes=source,private12_hashes=private,exposure_proposal_undeployed=True,tee=tee,old_run21_PID_exists=Path('/proc/1398998').exists(),scope='Read-only small source files and kernel proc environment; no Torch import, CUDA context, heap injection, process controls or source mutation.')
assert not observation['old_run21_PID_exists'];put('startup-independent-process-source-observation.json',observation)
raw=urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3).read();api=json.loads(raw);capture=datetime.now(timezone.utc).isoformat();put('startup-api-independent-before-fleet.json',api)
fds={os.readlink(fd) for fd in p.joinpath('fd').iterdir()}
inodes={v[8:-1] for v in fds if v.startswith('socket:[')};owned=False
for net in ['tcp','tcp6']:
 for line in Path('/proc/net',net).read_text().splitlines()[1:]:
  col=line.split()
  if col[1].split(':')[-1]==f'{8771:04X}' and col[3]=='0A' and col[9] in inodes:owned=True
meta=json.loads((base/'metadata.json').read_text());old=json.loads((base.parent/'run-21/metadata.json').read_text());default=json.loads((base.parent/'run-20/metadata.json').read_text())
cfg_delta=delta(old['config'],meta['config']);assert cfg_delta=={'torch_compile_mode':['max-autotune-no-cudagraphs','default']}
assert meta['config']==default['config']
anchor=json.loads((base/'final-resume-checkpoint.json').read_text());saved=anchor['saved_metadata'];cpu=json.loads((base/'startup-independent-checkpoint-cpu.json').read_text())
g=api['host_pipeline']['inference_graphs'];n=api['host_pipeline']['native_batch_update'];bank=api['bank_persistence']
log=(base/'console.log').read_bytes();end=log.rfind(b'\n')+1;prefix=log[:end];text=prefix.decode(errors='replace')
errors={s:text.count(s) for s in ['torch.compile unavailable','disabling torch.compile','falling back to eager','Traceback','Training error:','ExactInferenceGraphError','Batched inference request timed out','Batched inference failed','Non-finite loss']}
training=re.search(r'torch\.compile: training graphs warm \((\d+)s\)',text);allwarm=re.search(r'torch\.compile: all graphs warm in (\d+)s',text)
checks=dict(actual_CPU_anchor_SHA_metadata_Adam81_exact=cpu['PASS'] and cpu['anchor_sha256']==anchor['sha256'],all_saved_tensors_finite_CPU=cpu['all_saved_tensors_finite_CPU'],source19_and_private12_unchanged=source==prior['source_hashes'] and private==prior['private12_hashes'],actual_environment_only_default_compile_and_runpath=set(actual_delta)=={'ROBOTRON_RUN_DIR','DQN_COMPILE_MODE'},config_default_restored_only_compile_delta=meta['config']==default['config'] and cfg_delta=={'torch_compile_mode':['max-autotune-no-cudagraphs','default']},compiled_full_loss_enabled=meta['config']['compile_full_loss'] and meta['config']['use_torch_compile'],both_loss_variants_warmed_by_audited_loop=bool(training and allwarm),zero_logged_compile_training_transport_errors=all(v==0 for v in errors.values()),API_owned_by_trainer=owned,prefleet_clients0=api['client_count']==0,prefleet_fleet_learner_measurement_clocks_exact=api['frame_count']==saved['frame_count'] and api['learner_frame_count']==saved['learner_frame_count'] and api['measurement_frames']==saved['measurement_frame_count'],one_postload_batch_only=api['training_steps']==saved['training_steps']+1 and api['optimized_samples']==saved['optimized_samples']+4096,ring6M_bank_generations_counts_exact=api['memory_buffer_size']==6000000 and all(v['match'] for v in cpu['banks'].values()),banks_clean_no_writes=bank['writes']==0 and bank['write_failures']==0 and not any(bank['dirty'].values()) and bank['last_error'] is None,graphs128_real640_postload1_ready=g['requested'] and g['ready'] and g['capture_count']==128 and g['validation_cpu_returns']==640 and g['postload_validations']==1 and g['covered_shapes']==list(range(1,129)),graphs_no_padding_or_shared_pool=not g['padding'] and g['private_pool_per_shape'],graphs_runtime_capture_fallback_fatal0=g['runtime_capture_count']==0 and g['fallback_count']==0 and g['fatal_error'] is None,graph_owned_memory_bounded=g['graph_owned_reserved_bytes']<=g['budget_bytes'],native_enabled_available_one_success=n['enabled'] and n['available'] and n['completed_count']==n['success_count']==1 and n['fallback_count']==n['error_count']==0,stream_bank_output_preserved=bank['output']['stream_output_enabled'] and bank['output']['backend']=='stream',no_counter_proposal_deployment='learning_exposure' not in api['host_pipeline'] and not (game/'Scripts/dqn/learning_exposure.py').exists(),API_read_errors0=not api['pipeline_read_error'] and not api['bank_persistence_read_error'],learning_controls_preserved=api['epsilon']==.1 and abs(api['expert_ratio']-.1)<1e-12 and api['lr']==2.5e-5 and meta['config']['n_step']==3 and meta['config']['max_samples_per_frame']==8 and meta['config']['c51_target_smoothing']==0 and meta['config']['batch_size']==4096)
assert all(checks.values()),checks
result=dict(schema='robotron-run22-prefleet-independent-audit-v1',utc=datetime.now(timezone.utc).isoformat(),PASS=True,checks=checks,trainer_pid=pid,trainer_start_ticks=proc_start,prefleet_capture_utc=capture,prefleet_API_ts=api['ts'],config_delta_vs_run21=cfg_delta,config_identical_default_run20=True,clock_evidence=dict(saved=saved,prefleet={k:api[k] for k in ['frame_count','learner_frame_count','measurement_frames','training_steps','optimized_samples']},compiler_B_saved_clock_delta=cpu['compiler_B_saved_clock_delta'],interpretation=cpu['clock_delta_interpretation']),compile_warm_log=dict(training_s=int(training[1]),all_s=int(allwarm[1]),policy='Same source selects max_autotune=False and triton.cudagraphs=False for both full training loss modules under default; dynamic actor compiled callable/options unchanged.',console_complete_prefix_bytes=end,console_complete_prefix_sha256=hashlib.sha256(prefix).hexdigest()),console_error_counts=errors,graphs=g,native=n,bank_output_backend=bank['output']['backend'],source_evidence=['startup-independent-checkpoint-cpu.json','startup-independent-process-source-observation.json','startup-api-independent-before-fleet.json'],evidence_sha256={name:sha(base/name) for name in ['startup-independent-checkpoint-cpu.json','startup-independent-process-source-observation.json','startup-api-independent-before-fleet.json','final-resume-checkpoint.json','resume-environment.json','startup-root-record.json']},limits=['Audited source loop and completed warm branch establish both loss variants warmed; no heap injection or kernel profiler. Absence of failure log paths is external evidence, not proof about every internal compiler graph break.','Saved finite CPU tensors and logical/Adam clock deltas do not prove per-event overflow behavior or attribute the B nonfinite gradient reading to compiler mode.','Compiler chronology and numerical differences must remain in future128M lineage; no learning-quality equivalence claim.','Prefleet readiness only;192 process/slot/shim/current-log health and settled throughput require separate post-launch observations.'],audit_execution=dict(started_utc=start,finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_s=time.monotonic()-begin,pid=os.getpid()))
put('startup-readonly-independent-audit.json',result)
print(json.dumps(dict(PASS=True,checks_passed=len(checks),path=str(base/'startup-readonly-independent-audit.json'),sha256=sha(base/'startup-readonly-independent-audit.json'),cpu_clock_delta=cpu['compiler_B_saved_clock_delta'],compile_warm=result['compile_warm_log'],execution=result['audit_execution'])))
