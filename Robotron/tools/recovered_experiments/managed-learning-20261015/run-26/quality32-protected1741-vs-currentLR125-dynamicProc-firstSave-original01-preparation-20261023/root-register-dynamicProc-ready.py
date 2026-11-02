import importlib.util,json,os,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';B=G/'tools/startup_policy_journal_proposal';P=G/'tools/training_connection_lifecycle_proposal_20261023';T=R/'quality32-protected1741-vs-currentLR125-dynamicProc-firstSave-original01-preparation-20261023';D=R/'currentLR125-dynamicProc-firstSave-original01-preparation-20261023'
def load(path,name):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_reg_h');reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_reg_r');arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_reg_arc');cl=load(P/'independent_component_closeout_v3.py','_reg_cl')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
V=T/'selected-family-source-guards-CPU-original01';proof=cl.closeout(V,h,arc,read,0);rp=h.pin(V/'output-original01/report.json');report=read(rp);assert report['tests']==6 and len(report['negative_checks'])==17
proof.update(report=rp,tests=6,negative_checks=17,selected_family_unchanged_from_tested_renderer=True,scientific_case_launched=False)
guardproof=h.put(V/'independent-original-selected-family-and-CPU-closeout.json',proof)
readypin=h.pin(T/'new-original-quality-launch-readiness.json');ready=read(readypin);pair=read(ready['quality_pair'])
assert all(not(T/f).exists()for f in ['01-reference','02-candidate','03-reference','04-candidate'])
monitor=h.pin(D/'postcapture-current-main-readonly-monitor-v2.py');proc=subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],capture_output=True,text=True,timeout=20);assert proc.returncode==0,proc.stderr;health=json.loads(proc.stdout);assert health['client_count']==192 and health['held_inputs']==197
preflight=h.put(T/'original-current-main-before-canonical-registration.json',dict(monitor=monitor,actual=health,source_guard_closeout=guardproof,created_unix_s=time.time()))
S=R.parent/'state.json';raw=S.read_bytes();state=json.loads(raw);goal=state['optimization_goal'];previous=h.put(T/'prior-canonical-quality-and-monitor-aliases.json',dict(top_active=state.get('active_quality_job'),goal_active=goal.get('active_quality_job'),current_main_monitor=goal.get('current_main_monitor'),source_freeze=goal.get('source_freeze'),full_source_freeze=goal.get('full_source_freeze'),current_recovery_index=goal.get('current_recovery_index')))
active=dict(state='prepared',directory=str(T),plan_path=str(T/'plan.json'),status_path=str(T/'status.json'),quality_pair=ready['quality_pair'],launch_readiness=readypin,current_leg=1,total_legs=4,reference_label='1741.2M protected reference',candidate_label='2700.4M dynamic-proc LR125 candidate',original_attempts_per_leg=1,no_retries=True,promotion=False,quality_qualified=False,prior_closed_study=previous,selected_family_guard=guardproof)
state['active_quality_job']=active;goal['active_quality_job']=dict(active,current_leg='R1');goal.update(status='active',stage='FRESH_DYNAMICPROC2700_ALL_FOUR_NEW_QUALITY_LEGS_PREPARED',phase='SOURCE_BOUND_ORIGINAL_SEQUENCE_READY',source_freeze=True,full_source_freeze=True,current_quality_source_freeze_state='HELD_FOR_FRESH_DYNAMICPROC2700_ORIGINAL_FOUR_LEG_CAMPAIGN',current_main_monitor=monitor,current_main_binding=ready['current_main_binding'],actual_running_wait=None,current_recovery_index_pointer_update_pending=True)
goal['current_dynamicProc_study']=dict(directory=str(T),readiness=readypin,precommit=h.pin(T/'original-fresh-sequence-precommit.json'),candidate_numerical_CPU=h.pin(D/'independent-original-numerical-CPU-closeout.json'),source_guard_closeout=guardproof,main_preflight=preflight,capture_limitation='Original60s prefix closed before owned managed-slot transition; historical independent current-hash replay was not qualified. All old failed cases remain excluded.',quality_qualified=False,learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False)
goal['last_progress']='Fresh2700.4M policy numerical CPU and actual selected source contracts passed; original four-leg sequence ready against protected1741. Main192/197 healthy, LR125 retained; no gain or promotion claimed.';goal['latest_goal_turn_progress']=dict(classification='progress',evidence=guardproof,scientific_qualification=False,created_unix_s=time.time());state['updated_unix_s']=time.time()
backup=T/'canonical-before-dynamicProc-ready.raw.json'
with backup.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
encoded=json.dumps(state,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1000000 and S.read_bytes()==raw
tmp=S.with_name('state.dynamicProc-ready.tmp')
with tmp.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps(dict(registered=True,state_bytes=len(encoded),guard_tests=6,negative_checks=17,source_guard=guardproof,precommit=h.pin(T/'original-fresh-sequence-precommit.json'))))
