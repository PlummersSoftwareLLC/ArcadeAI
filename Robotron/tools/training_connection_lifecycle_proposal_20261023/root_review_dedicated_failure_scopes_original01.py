"""Independent readback of all eight actual scopes in the six-negative suite."""
import importlib.util,json,os,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal';D=R/'dedicated-main-health-six-failure-scopes-CPU-original01-preparation-20261023';O=D/'output-original01'
def load(path,name):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_negative_root_h');reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_negative_root_reader');arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_negative_root_arc');cl=load(P/'independent_component_closeout_v3.py','_negative_root_cl');ctl=load(P/'control_owned_health_CPU180_signalaware_v1.py','_negative_root_ctl')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
parent=cl.closeout(D,h,arc,read,0);rp=h.pin(O/'report.json');report=read(rp);assert [r['case']for r in report['cases']]==['abort','foreign_nonce','wrong_parent_birth','signal_TERM','signal_KILL','parent_exit']
cases=[]
for item in report['cases']:
 case=item['case'];directory=O/case;jp=h.pin(directory/'job.json');job=read(jp);outcome_path=directory/'observations/outcome.json'
 if case!='signal_KILL':
  scope=cl.closeout(directory,h,arc,read,1);outcome=read(item['outcome']);assert item['outcome']==h.pin(outcome_path)
  assert not outcome['success']and outcome['closed_report']is None and outcome['job']==jp and outcome['nonce']==job['nonce']and outcome['parent']==job['parent']
  if outcome['failure_report']is not None:
   failed=read(outcome['failure_report']);assert not failed['writer_thread_alive']and failed['writer_error']is None
   for index,pin in enumerate(failed['samples']):assert read(pin)['transport']['index']==index
  if case=='signal_TERM':assert outcome['signals_received']==[15]and 'Original observer signal 15'in outcome['error']
  else:assert outcome['signals_received']==[]
  if case=='abort':assert 'requested abort'in outcome['error']
  elif case=='foreign_nonce':assert 'Finish job/nonce/parent/action differs'in outcome['error']
  elif case=='wrong_parent_birth':assert 'parent birth is absent/changed'in outcome['error']and outcome['observed_samples']==0 and outcome['failure_report']is None
  classification=dict(actual_exec_code=1,actual_exit=1,actual_signal=None,received_signals=outcome['signals_received'],outcome=item['outcome'],error=outcome['error'])
 else:
  cfg=read(h.pin(directory/'controller-config.json'));ctl.checked_config(str(directory/'controller-config.json'));op=h.pin(directory/'execution-original01/root-original-identity.json');owner=read(op);cp=h.pin(directory/'execution-original01/root-original-result-and-owned-release.json');c=read(cp)
  assert c['original']==owner and c['original_exec_code']==2 and c['original_exit']is None and c['original_signal']==9 and c['original_result']=='signal'and c['audit_success']is False
  assert c['lifecycle_complete']and c['unit_released']and c['original_archived_before_release']and not c['payload_retried']
  for i,entry in enumerate(c['full_original_archives']):
   assert len(c['full_original_archives'])==6;kind='service'if i<3 else'timer';action=['show','cat','journal'][i%3];unit=owner['unit']if kind=='service'else owner['timer'];inv=owner['invocation_id']if kind=='service'else owner['timer_invocation_id']
   expected=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+inv]if action=='journal'else['systemctl','--user',action,unit]
   assert entry['argv']==expected and not entry['timed_out']and entry['exit']in ((0,1)if i==4 else(0,));read(entry['stdout'],False);read(entry['stderr'],False)
  fields=ctl.fields(c['full_original_archives'][0]);ctl.original_terminal(fields,owner)
  assert fields['ExecMainCode']=='2'and fields['ExecMainStatus']=='9'and fields['Result']=='signal'
  for k,v in dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no').items():assert fields[k]==v
  assert ' '.join(cfg['argv'])+' ; ignore_errors=no ;'in fields['ExecStart']
  timer=ctl.fields(c['full_original_archives'][3]);assert timer['Id']==owner['timer']
  if c['full_original_archives'][4]['exit']==1:assert timer['LoadState']=='not-found'
  else:assert timer['InvocationID']==owner['timer_invocation_id']and timer['Unit']==owner['unit']
  assert len(c['owned_release'])==2 and {r['unit']for r in c['owned_release']}=={owner['unit'],owner['timer']}and all(r['confirmed_absent']for r in c['owned_release'])
  for pin in cfg['pins']:assert ctl.pin(pin['path'])==pin
  for unit in [owner['unit'],owner['timer']]:assert ctl.show(unit)['LoadState']=='not-found'
  assert not Path('/proc',str(owner['pid'])).exists()and not(Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')/owner['unit']).exists()
  assert not outcome_path.exists();scope=dict(owner=op,closure=cp,all6_actual_archives_resources_argv_pins_release_verified=True)
  classification=dict(actual_exec_code=2,actual_exit=None,actual_signal=9,missing_outcome_preserved=True)
 cases.append(dict(case=case,worker_job=jp,scope=scope,classification=classification,trigger=item['trigger'],negative_raw_not_health_qualified=True))
holder=cl.closeout(O/'actual-parent-exit-fixture',h,arc,read,0)
exitcase=next(row for row in report['cases']if row['case']=='parent_exit');worker=read(exitcase['outcome']);hc=read(holder['closure']);ho=read(holder['owner']);hf=arc.archived_closure(hc,ho,read,exit_zero=True)
assert worker['parent']['pid']==ho['pid']and worker['parent']['birth']==ho['starttime_ticks']and worker['ended_monotonic_s']>=int(hf['ExecMainExitTimestampMonotonic'])/1e6
monitor=h.pin(R/'currentLR125-initialReady-firstSave-original01-preparation-20261023/postcapture-current-main-readonly-monitor-v2.py');main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
pp=h.put(D/'independent-original-six-failures-eight-scopes-and-signal-readback.json',dict(schema='robotron-dedicated-health-failure-scopes-independent-closeout-v1',parent_scope=parent,parent_exit_holder_scope=holder,cases=cases,actual_report=rp,
 all8_actual_scope_archives_resources_argv_pins_release_and_birth_absence_verified=True,all_persisted_negative_raw_pins_authenticated=True,
 actual_KILL_exec2_signal9_missing_outcome_not_normalized=True,actual_TERM_received15_normal_exit1_not_success=True,real_parent_exit0_preceded_worker_failure_verified=True,
 positive_component_still_distinct=h.pin(R/'dedicated-main-health-protocol-and-live-worker-CPU-original01-preparation-20261023/independent-original-protocol38-and-autonomous127-raw-both-scopes-closeout.json'),
 current_main=main,scientific_case=False,quality_qualified=False,production_changed=False))
S=R.parent/'state.json';before=S.read_bytes();s=json.loads(before);g=s['optimization_goal'];idx=read(g['current_recovery_index']);previous=g['current_recovery_index'];stage='DEDICATED_OBSERVER_SIX_FAILURES_EIGHT_SCOPES_INDEPENDENTLY_CLOSED_NATIVE_CLIENT_NEXT'
g.update(stage=stage,phase='DEDICATED_OBSERVER_NATIVE_CLIENT_FINALIZER_REVIEW_IMPLEMENTATION',actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,latest_goal_turn_classification='progress',last_progress='Six actual expected worker failures independently verified across8 scopes: abort, foreign nonce, wrong parent birth, TERM, KILL and real parent exit. Raw KILL2/9 and missing outcome preserved; TERM handler recorded15/exit1. All units released; main192/197 healthy. Native integration next, no quality gain.')
g['active_diagnostic_job'].update(state='CLOSED_ORIGINAL_PARENT0_ALL_NEGATIVES_VERIFIED',independent_closeout=pp)
g['future_main_observer_isolation'].update(state='POSITIVE_AND_SIX_ACTUAL_FAILURE_LIFECYCLES_VALIDATED_NATIVE_INTEGRATION_PENDING',failure_scope_closeout=pp)
g['latest_goal_turn_assessment']=dict(classification='progress',evidence=pp,work=g['last_progress'])
idx.update(previous_recovery_index=previous,stage=stage,phase=g['phase'],actual_running_wait=None,all_current_original_handles_terminal=True,source_freeze=False,full_source_freeze=False,negative_scopes_independent_closeout=pp,current_main_health=main,next_action='Implement and test native client/finalizer and9660s observer controller plus independent worker scope/raw joins; integrate unselected native/preparer/reviewer family and failed2715 exclusions. Require new actual32 startup-load diagnostic before a later frozen policy/new four-leg study.',created_unix_s=time.time())
ip=h.put(R/'current-optimization-recovery-index-20261023-dedicated-worker-six-failures-closed-native-client-next-original01.json',idx);g['current_recovery_index']=ip;g['next_action']=idx['next_action']
with(D/'canonical-before-independent-six-failure-closeout.raw.json').open('xb')as f:f.write(before);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
encoded=json.dumps(s,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1048576 and S.read_bytes()==before;tmp=S.with_name('state.dedicated-six-failures-closed.tmp')
with tmp.open('xb')as f:f.write(encoded);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
assert S.read_bytes()==before;os.replace(tmp,S);fd=os.open(S.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
doc=G/'DELL_SETUP.md';text=doc.read_text();a=text.index('Current optimization recovery:');b=text.index('The native initial baseline');doc.write_text(text[:a]+'''Current optimization recovery: [Observer failure scopes independently closed; native client next](logs/managed-learning-20261015/run-26/current-optimization-recovery-index-20261023-dedicated-worker-six-failures-closed-native-client-next-original01.json).
All actual handles are terminal. No scientific evaluation/diagnostic is running.
Source holds released. Do not restart prior studies, diagnostics or44337.

Original six-negative suite44337 closed0. Abort, foreign nonce, wrong parent
birth, TERM, KILL and real owned parent exit all rejected as precommitted. Actual
eight scopes' six archives/resources/argv/pins/releases and PID/cgroup absence
were independently checked. KILL retained ExecMainCode2/signal9, no exit value,
and no worker outcome. TERM handler recorded signal15 and actual normal exit1,
never success. Parent fixture actual exit0 preceded worker failure. Every persisted
negative raw pin was authenticated; no failed scope is health/quality-qualified.

Positive component4355 remains distinct:3 contracts/38 rejections, autonomous
127 samples/5 censuses,10 captures during2s parent pause, both scopes independently
closed0 and full raw replay verified. New9660s controller is prepared; native
client/finalizer/review/source-family integration and actual32 startup-load test
remain. All timing/copy/ownership/budget/game gates stay unchanged. No new score,
promotion or learning/useful-throughput gain. Main192/197, LR125/autosaves healthy.

'''+text[b:]);print(json.dumps(dict(proof=pp,recovery=ip,main=main)))
