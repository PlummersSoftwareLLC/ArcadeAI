"""Six original owned negative scopes: abort, nonce, parent birth, TERM, KILL, exit.

Expected rejection is test success, never a successful health observation. Raw
signals retain original ExecMainCode/status; a missing outcome stays missing.
"""
import argparse,copy,hashlib,importlib.util,json,os,signal,subprocess,sys,time
from pathlib import Path
def load(pin,name):
 path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def birth(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
 if not a.execute:print('PLAN_ONLY');return 0
 assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
 raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
 assert job['schema']=='robotron-dedicated-health-six-negative-scope-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
 h=load(job['helpers'],'_negative_h');reader=load(job['reader'],'_negative_reader');arc=load(job['archive'],'_negative_arc');closer=load(job['closer'],'_negative_closer');cpu=load(job['CPU_controller'],'_negative_cpu');protocol=load(job['protocol_source'],'_negative_protocol')
 def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
 for key in ['helpers','reader','archive','closer','CPU_controller','protocol_source','worker','parent_fixture','worker_interpreter','RAM_helper']:h.checked(job[key])
 storage=load(job['RAM_helper'],'_negative_RAM_storage')
 root=Path(job['output']);root.mkdir(mode=0o700);records=[]
 me=cpu.show(job['parent_unit']);assert me['MainPID']==str(os.getpid())and me['InvocationID']==os.environ['INVOCATION_ID']
 parent=dict(pid=os.getpid(),birth=birth(os.getpid()),uid=os.geteuid(),unit=job['parent_unit'],invocation_id=me['InvocationID'],cgroup=me['ControlGroup'],argv=[v.decode()for v in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]],job=h.pin(a.job),source=h.pin(__file__))
 def launch(directory,unit,source,jp,pins):
  cfg=dict(unit=unit,output=str(directory/'execution-original01'),argv=([job['worker_interpreter']['path'],'-Xgil=0']if source==job['worker']else['/usr/bin/python3.12'])+['-I','-B',source['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',source['sha256']],properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],pins=[cpu.pin(v['path'])for v in {x['path']:x for x in [*pins,jp,source]}.values()],observation_s=240)
  cp=h.put(directory/'controller-config.json',cfg);cpu.checked_config(cp['path'])
  with(directory/'controller-stdout.txt').open('xb')as out,(directory/'controller-stderr.txt').open('xb')as err:
   argv=['/usr/bin/python3.12','-I','-B',job['CPU_controller']['path'],'--execute','--config',cp['path'],'--expected-source-sha256',job['CPU_controller']['sha256']];child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
  child_birth=birth(child.pid);h.put(directory/'original-controller-child.json',dict(pid=child.pid,birth=child_birth,argv=argv))
  return child,child_birth,cp
 def ready(directory,child,*,running):
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   path=directory/'execution-original01/root-original-identity.json'
   if path.exists()and path.stat().st_mode&0o777==0o444:
    owner=read(h.pin(path))
    if not running:return owner
    worker_job=read(h.pin(directory/'job.json'));live=Path(worker_job['live_control']['live_path'])
    storage.check_live(worker_job['live_control'])
    if live.exists():
     state=protocol.checked_read(live,os.geteuid(),mode=0o644)
     if state['state']=='failed':raise AssertionError(state['error'])
     if state['state']=='running'and state['initial']['index']is not None:return owner
   assert child.poll()is None,'Original controller exited before its expected live marker';time.sleep(.02)
  raise ValueError('Original live identity not observed; no retry')
 holder=None;holder_birth=None;holder_job=None;holder_root=None;holder_scope=None
 for case in ['abort','foreign_nonce','wrong_parent_birth','signal_TERM','signal_KILL','parent_exit']:
  directory=root/case;directory.mkdir(mode=0o700);selected=copy.deepcopy(parent)
  if case=='parent_exit':
   holder_root=root/'actual-parent-exit-fixture';holder_root.mkdir(mode=0o700);holder_job=h.put(holder_root/'job.json',dict(output=str(holder_root/'output-original01'),helpers=job['helpers'],original_attempt=1,no_retry=True))
   holder,holder_birth,hcp=launch(holder_root,job['unit_prefix']+'-holder.service',job['parent_fixture'],holder_job,[job['helpers']]);ho=ready(holder_root,holder,running=False)
   fields=cpu.show(ho['unit']);hc=read(hcp)
   selected=dict(pid=ho['pid'],birth=ho['starttime_ticks'],uid=os.geteuid(),unit=ho['unit'],invocation_id=ho['invocation_id'],cgroup=fields['ControlGroup'],argv=hc['argv'],job=holder_job,source=job['parent_fixture'])
  elif case=='wrong_parent_birth':selected['birth']+=1
  started=time.monotonic();prior=h.put(directory/'prior-groups.json',[])
  wjob=dict(schema='robotron-dedicated-main-health-job-v1',output=str(directory/'observations'),helpers=job['helpers'],protocol_source=job['protocol_source'],health_job=job['health_job'],prior_groups=prior,worker_interpreter=job['worker_interpreter'],
   observer_unit=job['unit_prefix']+'-'+case.lower().replace('_','-')+'.service',unit_runtime_s=180,parent=selected,parent_started_monotonic_s=started,deadline_monotonic_s=started+60,poll_s=.2,nonce=os.urandom(16).hex(),original_attempt=1,no_retry=True)
  wjob.update(native_job=selected['job'],live_control_helper=job['RAM_helper'])
  wjob['live_control']=storage.create(wjob['nonce'],selected,wjob['native_job'],wjob['observer_unit'],h)
  jp=h.put(directory/'job.json',wjob);pins=[job['RAM_helper'],job['worker_interpreter'],*job['health_job']['sources'].values(),job['health_job']['binding'],job['protocol_source'],selected['job'],selected['source'],prior]
  child,child_birth,cp=launch(directory,wjob['observer_unit'],job['worker'],jp,pins);owner=ready(directory,child,running=case!='wrong_parent_birth')
  evidence=None
  if case in ('abort','foreign_nonce'):
   nonce=wjob['nonce']if case=='abort'else('0'*32 if wjob['nonce']!='0'*32 else'1'*32)
   evidence=h.put(directory/'observations/finish-request.json',dict(schema=protocol.FINISH_SCHEMA,job=jp,nonce=nonce,parent=selected,action='abort'if case=='abort'else'close',created_monotonic_s=time.monotonic()))
  elif case in ('signal_TERM','signal_KILL'):
   fields=cpu.show(owner['unit']);assert fields['MainPID']==str(owner['pid'])and fields['InvocationID']==owner['invocation_id']and birth(owner['pid'])==owner['starttime_ticks']
   sig=signal.SIGTERM if case=='signal_TERM'else signal.SIGKILL
   evidence=h.put(directory/'original-exact-owner-signal-intent.json',dict(owner=h.pin(directory/'execution-original01/root-original-identity.json'),signal=int(sig),birth_checked=True,unix_s=time.time()))
   os.kill(owner['pid'],sig)
  elif case=='parent_exit':
   deadline=time.monotonic()+5
   while not(holder_root/'output-original01/ready.json').exists():assert holder.poll()is None and time.monotonic()<deadline;time.sleep(.02)
   evidence=h.put(holder_root/'output-original01/finish-request.json',dict(action='normal_fixture_exit',job_sha256=holder_job['sha256']))
   assert holder.wait(timeout=25)==0 and birth(holder.pid)!=holder_birth
   holder_scope=closer.closeout(holder_root,h,arc,read,0)
  assert child.wait(timeout=25)==1 and birth(child.pid)!=child_birth
  closurepin=h.pin(directory/'execution-original01/root-original-result-and-owned-release.json');closure=read(closurepin)
  if case=='signal_KILL':
   assert closure['original_exec_code']==2 and closure['original_exit']is None and closure['original_signal']==9 and closure['original_result']=='signal'and closure['audit_success']is False
   assert closure['original']==owner and closure['lifecycle_complete']and closure['unit_released']and closure['original_archived_before_release']and not closure['payload_retried']
   archives=closure['full_original_archives'];assert len(archives)==6
   for i,entry in enumerate(archives):
    kind='service'if i<3 else'timer';action=['show','cat','journal'][i%3];unit=owner['unit']if kind=='service'else owner['timer'];inv=owner['invocation_id']if kind=='service'else owner['timer_invocation_id']
    expected=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+inv]if action=='journal'else['systemctl','--user',action,unit]
    assert entry['argv']==expected and not entry['timed_out']and entry['exit']in ((0,1)if i==4 else(0,));read(entry['stdout'],False);read(entry['stderr'],False)
   fields=cpu.fields(archives[0]);assert fields['ExecMainCode']=='2'and fields['ExecMainStatus']=='9'and fields['Result']=='signal'and fields['InvocationID']==owner['invocation_id'];cpu.original_terminal(fields,owner)
   timer=cpu.fields(archives[3]);assert timer['Id']==owner['timer']
   if archives[4]['exit']==1:assert timer['LoadState']=='not-found'
   else:assert timer['InvocationID']==owner['timer_invocation_id']and timer['Unit']==owner['unit']
   assert len(closure['owned_release'])==2 and {r['unit']for r in closure['owned_release']}=={owner['unit'],owner['timer']}and all(r['confirmed_absent']for r in closure['owned_release'])
   config=read(cp);assert ' '.join(config['argv'])+' ; ignore_errors=no ;'in fields['ExecStart']
   for key,value in dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no').items():assert fields[key]==value
   for pin in config['pins']:assert cpu.pin(pin['path'])==pin
   for unit in [owner['unit'],owner['timer']]:assert cpu.show(unit)['LoadState']=='not-found'
   assert birth(owner['pid'])!=owner['starttime_ticks']and not(Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')/owner['unit']).exists()
   assert not(directory/'observations/outcome.json').exists();scope=dict(owner=h.pin(directory/'execution-original01/root-original-identity.json'),closure=closurepin,actual_exec_code=2,actual_signal=9,actual_exit=None,
    all6_actual_archives_resources_argv_pins_release_and_birth_absence_verified=True,missing_worker_outcome_preserved=True)
   outcome=None
  else:
   scope=closer.closeout(directory,h,arc,read,1);outcomepin=h.pin(directory/'observations/outcome.json');outcome=read(outcomepin)
   assert not outcome['success']and outcome['closed_report']is None and outcome['job']==jp and outcome['parent']==selected and outcome['nonce']==wjob['nonce']
   if case=='abort':assert 'requested abort'in outcome['error']
   if case=='foreign_nonce':assert 'Finish job/nonce/parent/action differs'in outcome['error']
   if case=='wrong_parent_birth':assert 'parent birth is absent/changed'in outcome['error']and outcome['observed_samples']==0 and outcome['failure_report']is None
   else:
    assert outcome['all_writer_threads_stopped']and outcome['failure_report']is not None
    failure=read(outcome['failure_report']);assert failure['writer_thread_alive']is False and failure['writer_error']is None
    if case=='signal_TERM':assert 0<=len(failure['samples'])-failure['observed_samples']<=1
    else:assert len(failure['samples'])==failure['observed_samples']
    for index,pin in enumerate(failure['samples']):assert read(pin)['transport']['index']==index
   if case=='signal_TERM':assert outcome['signals_received']==[15]and 'Original observer signal 15'in outcome['error']
   else:assert outcome['signals_received']==[]
  if outcome is not None:assert outcome['live_control']==wjob['live_control']and outcome['live_control_helper']==job['RAM_helper']
  RAM_release=storage.archive_and_release(wjob['live_control'],directory/'live-control-archive',h,worker_job=jp,owner=h.pin(directory/'execution-original01/root-original-identity.json'),closure=closurepin)
  RAM_review=storage.verify_release(wjob['live_control'],RAM_release,directory/'live-control-archive',jp,h.pin(directory/'execution-original01/root-original-identity.json'),closurepin,read,h)
  records.append(dict(case=case,worker_job=jp,original_scope=scope,trigger=evidence,RAM_control_release=RAM_release,RAM_control_independent_review=RAM_review,outcome=None if outcome is None else h.pin(directory/'observations/outcome.json'),expected_rejection_preserved=True,health_qualified=False))
 assert 'torch'not in sys.modules
 report=h.put(root/'report.json',dict(schema='robotron-dedicated-health-six-negative-original-scope-report-v1',status='SIX_ORIGINAL_EXPECTED_FAILURES_AND_ACTUAL_SIGNAL_CLASSIFICATIONS_VERIFIED',
  cases=records,parent_exit_holder_scope=holder_scope,wrong_birth_value_explicit_negative_fixture=True,signals_to_exact_owned_test_workers_only=True,
  actual_KILL_code2_signal9_not_normalized=True,actual_TERM_handler_recorded_signal15_normal_exit1_not_success=True,
  RAM_control_helper=job['RAM_helper'],all_case_RAM_control_bytes_archived_before_owned_release=True,native_integration_still_required=True,scientific_case=False,quality_qualified=False,production_changed=False,created_unix_s=time.time()))
 print(json.dumps(dict(report=report,cases=len(records))),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
