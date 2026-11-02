from pathlib import Path
import importlib.util,json,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';L=B/'future-fast-pending-physical-watch-source-original01-20261101/live-pending-transition-engineering-original02'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_pendingH',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');p=json.loads((L/'prepared-not-launched.json').read_text());seq=load('_pendingSeq',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py');ctl=load('_pendingCtl',h.checked(p['controller']));rt=load('_pendingRT',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
result=seq.invoke_controller_once(L,'',p['controller'],p['controller_config'],h)
r=json.loads(h.checked(result).read_text());read=lambda pin,as_json=True:json.loads(h.checked(pin).read_text())if as_json else h.checked(pin).read_bytes()
closed=seq.verify_closed_scope(L,'',p['controller_config'],h,read,rt,ctl,exit_zero=r['actual_exit']==0)
cp=json.loads(h.checked(p['controller_config']).read_text());exit_report=h.put(L/'original-engineering-result-and-positive-owned-closeout.json',dict(actual_exit=r['actual_exit'],original_scope=closed,all_original_resources_closed=True,original_Popen_reaped=True,controller_birth_absent=seq.birth(json.loads((L/'controller-original-child.json').read_text())['pid'])!=json.loads((L/'controller-original-child.json').read_text())['starttime_ticks'],original_attempt=1,no_retry=True,scientific_cohort=False,promotion=False))
print(json.dumps(dict(event='ORIGINAL_CLOSED',actual_exit=r['actual_exit'],report={k:exit_report[k]for k in ['path','sha256','bytes']})),flush=True)
raise SystemExit(r['actual_exit'])
