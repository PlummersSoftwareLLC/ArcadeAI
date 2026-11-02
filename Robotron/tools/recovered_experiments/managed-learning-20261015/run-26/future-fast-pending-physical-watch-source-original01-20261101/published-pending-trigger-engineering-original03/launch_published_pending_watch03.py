from pathlib import Path
import importlib.util,json,sys
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';L=B/'future-fast-pending-physical-watch-source-original01-20261101/published-pending-trigger-engineering-original03'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_pub03H',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');reader=load('_pub03Reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py');read=lambda p,as_json=True:reader.read_pin(p,as_json=as_json)
p=read(h.pin(L/'prepared-not-launched.json'));cpu=read(h.pin(L/'CPU-trigger-contracts-original01.json'));assert cpu['status']=='PASS_PUBLISHED_PENDING_TRIGGER_CPU_CONTRACTS' and cpu['checks_total']==9
job=read(p['job']);assert cpu['source']==job['runtime']and cpu['prospective_native']==job['prospective_native']
seq=load('_pub03Seq',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py');ctl=load('_pub03Ctl',h.checked(p['controller']));rt=load('_pub03RT',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
result=seq.invoke_controller_once(L,'',p['controller'],p['controller_config'],h);r=read(result);scope=seq.verify_closed_scope(L,'',p['controller_config'],h,read,rt,ctl,exit_zero=r['actual_exit']==0);child=read(h.pin(L/'controller-original-child.json'));assert seq.birth(child['pid'])!=child['starttime_ticks']
native=read(h.pin(L/'report.json'))if(L/'report.json').exists()else None
v=h.put(L/'original-engineering-result-and-positive-owned-closeout.json',dict(actual_exit=r['actual_exit'],original_scope=scope,all_original_resources_closed=True,original_Popen_reaped=True,controller_birth_absent=True,original_attempt=1,no_retry=True,native_report=h.pin(L/'report.json')if native else None,scientific_cohort=False,promotion=False))
print(json.dumps(dict(event='ORIGINAL_CLOSED',actual_exit=r['actual_exit'],native_status=native['status']if native else None,closeout={k:v[k]for k in ['path','sha256','bytes']})),flush=True)
raise SystemExit(r['actual_exit'])
