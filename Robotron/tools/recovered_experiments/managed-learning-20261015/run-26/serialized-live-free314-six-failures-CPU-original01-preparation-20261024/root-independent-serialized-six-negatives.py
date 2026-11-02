"""Independent readback of all eight actual scopes in the six-negative suite."""
import importlib.util,json,os,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal';D=R/'serialized-live-free314-six-failures-CPU-original01-preparation-20261024';O=D/'output-original01'
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
  assert outcome['interpreter']['GIL_enabled']is False and outcome['interpreter']['major_minor']==[3,14]and outcome['interpreter']['binary']==job['worker_interpreter']
  cfg=read(h.pin(directory/'controller-config.json'));assert cfg['argv'][:4]==[job['worker_interpreter']['path'],'-Xgil=0','-I','-B']
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
monitor=h.pin(R/'currentLR125-dedicatedObserver-firstSave-original01-preparation-20261024/postcapture-current-main-readonly-monitor-v2.py');main=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],check=True,capture_output=True,text=True,timeout=25).stdout)
pp=h.put(D/'independent-original-six-failures-eight-scopes-and-signal-readback.json',dict(schema='robotron-dedicated-health-failure-scopes-independent-closeout-v1',parent_scope=parent,parent_exit_holder_scope=holder,cases=cases,actual_report=rp,
 all8_actual_scope_archives_resources_argv_pins_release_and_birth_absence_verified=True,all_persisted_negative_raw_pins_authenticated=True,
 actual_KILL_exec2_signal9_missing_outcome_not_normalized=True,actual_TERM_received15_normal_exit1_not_success=True,real_parent_exit0_preceded_worker_failure_verified=True,
 positive_component_still_distinct=h.pin(R/'serialized-live-free314-client-CPU-original01-preparation-20261024/independent-original-serialized-client-runtime-and-raw-closeout.json'),
 current_main=main,scientific_case=False,quality_qualified=False,production_changed=False))

print(json.dumps(dict(proof=pp,main=main)))
