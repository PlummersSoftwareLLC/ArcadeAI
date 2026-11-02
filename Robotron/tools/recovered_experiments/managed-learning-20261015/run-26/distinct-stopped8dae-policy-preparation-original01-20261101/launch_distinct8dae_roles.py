from pathlib import Path
import importlib.util,json,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';D=B/'distinct-stopped8dae-policy-preparation-original01-20261101/CPU-roles-original01'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_roles8H',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');reader=load('_roles8Reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py');read=lambda pin,as_json=True:reader.read_pin(pin,as_json=as_json)
p=read(h.pin(D/'prepared-CPU-roles.json'));seq=load('_roles8Seq',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py');ctl=load('_roles8Ctl',h.checked(p['controller']));rt=load('_roles8RT',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
result=seq.invoke_controller_once(D,'',p['controller'],p['controller_config'],h);r=read(result);closed=seq.verify_closed_scope(D,'',p['controller_config'],h,read,rt,ctl,exit_zero=r['actual_exit']==0);child=read(h.pin(D/'controller-original-child.json'));assert seq.birth(child['pid'])!=child['starttime_ticks']
report=read(h.pin(D/'report.json')) if (D/'report.json').exists()else None
if r['actual_exit']==0:
 assert report['status']=='PASS_FRESH_REFERENCE_AND_CANDIDATE_CPU_ACQUISITION' and report['CUDA_initialized']is False and report['Main_or_replay_or_protected_or_selected_policy_modified']is False
 assert report['same_frozen_schema'] and report['all_original_policy_bytes_preserved']
 for role,value in report['roles'].items():
  assert len(value['CPU_batch_checks'])==16 and value['online_target_and_initialized_Adam_payloads_finite']
  assert value['optimizer_initialized_states']==81 and value['CUDA_initialized']is False
  h.checked(value['source_checkpoint']);h.checked(value['checkpoint'])
v=h.put(D/'original-role-CPU-result-and-owned-closeout.json',dict(status='PASS_DISTINCT8DAE_CPU_AND_INFERENCE_COMPATIBILITY'if r['actual_exit']==0 else 'FAILED_ORIGINAL_DISTINCT8DAE_COMPATIBILITY',actual_exit=r['actual_exit'],original_scope=closed,original_Popen_reaped=True,all_original_resources_closed=True,original_controller_birth_absent=True,report=h.pin(D/'report.json')if report else None,policies={k:v['checkpoint']['sha256']for k,v in report['roles'].items()}if report else None,CPU_batch_sizes=list(range(1,17)),source_policy_or_Main_or_replay_modified=False,quality_qualified=False,promotion=False))
print(json.dumps(dict(closeout={k:v[k]for k in ['path','sha256','bytes']},status='PASS'if r['actual_exit']==0 else 'FAILED')),flush=True)
raise SystemExit(r['actual_exit'])
