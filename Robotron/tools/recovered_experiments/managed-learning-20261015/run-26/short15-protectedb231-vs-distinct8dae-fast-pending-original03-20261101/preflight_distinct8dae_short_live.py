from pathlib import Path
import fcntl,importlib.util,json,shutil,subprocess,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';F=B/'short15-protectedb231-vs-distinct8dae-fast-pending-original03-20261101'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_pre8liveH',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');reader=load('_pre8liveReader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py');read=lambda p,as_json=True:reader.read_pin(p,as_json=as_json)
p=read(h.pin(F/'prepared-with-review.json'));cpu=read(h.pin(F/'CPU-preflight-and-additional-cadence-contracts-original01.json'));assert cpu['status']=='PASS_FRESH_DISTINCT8DAE_SHORT_SCREEN_CPU_PREFLIGHT'and cpu['prepared']==h.pin(F/'prepared-with-review.json')
j=read(p['jobs']['R1']['job']);out=F/'preflight-current-Main-original01';out.mkdir(mode=0o700);health=load('_pre8liveHealth',h.checked(j['current_v6_health_source']));guard=health.CurrentV6MainHealth(j,out,h);guard.start();started=time.monotonic();accepted=0
while accepted<2:
 v=guard.observe();accepted+=int(not v['phase']['overlap_pending']);assert time.monotonic()-started<20
 if accepted<2:time.sleep(.2 if v['phase']['overlap_pending'] else 1)
report=guard.finish(None);auditor=load('_pre8liveAudit',h.checked(p['independent_owned_Main_auditor']));replay=auditor.audit_main(j,dict(main_health_report=report,main_samples=guard.samples,main_observer_lifecycle=guard.lifecycle),read,h)
outer=load('_pre8liveOuter',h.checked(p['selected_sources']['outer']));ports=outer.wait_for_job_ports(j)
assert ports['probe_sockets_released'] and ports['all_probe_socket_close_calls_attempted'] and ports['native_launch_started'] is False and ports['busy_port'] is None
lease=Path(j['lease']['path']);assert h.pin(lease)==j['lease']
with lease.open('rb')as file:fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(file,fcntl.LOCK_UN)
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=10);assert gpu.returncode==0 and j['gpu_uuid']not in gpu.stdout
ctl=load('_pre8liveCtl',h.checked(p['selected_sources']['controller']));unit_states=[];configs=read(p['controller_configs'])
for leg in ['R1','C1']:
 for config_pin in [configs['configs'][leg],p['independent_review']['configs'][leg]]:
  c=read(config_pin)
  for unit in [c['unit'],c['unit'].removesuffix('.service')+'.timer']:
   value=ctl.show(unit);assert value['LoadState']=='not-found';unit_states.append(dict(unit=unit,load_state=value['LoadState']))
assert shutil.disk_usage(G).free>=20<<30
for leg in ['R1','C1']:
 for pin in read(p['jobs'][leg]['job'])['inputs']:h.checked(pin)
assert 'torch'not in sys.modules and 'numpy'not in sys.modules
result=h.put(F/'positive-live-preflight-original01.json',dict(status='PASS_FRESH_ACTUAL_MAIN_PHYSICAL_PRIVATE_PORTS_GPU_AND_OWNERSHIP_PREFLIGHT',observed_unix_s=time.time(),prepared=h.pin(F/'prepared-with-review.json'),CPU_preflight=h.pin(F/'CPU-preflight-and-additional-cadence-contracts-original01.json'),physical_report=report,independent_Main_replay=replay,bind_only_ports=ports,lease_identity=j['lease'],private_GPU_idle=True,GPU_query=dict(stdout=gpu.stdout,stderr=gpu.stderr,exit=gpu.returncode),future_owned_units_absent=unit_states,root_free_bytes=shutil.disk_usage(G).free,native_or_MAME_or_GPU_context_started=False,Main_control_changed=False,scientific_launch_started=False,promotion=False))
print(json.dumps(dict(preflight={k:result[k]for k in ['path','sha256','bytes']},Main_replay=replay)),flush=True)
