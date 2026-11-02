"""Archive and release only the captured original outer controller after exit.

Default is inert. The original live birth and launch evidence already exist.
No payload launch, review, retry, signal normalization or running-unit stop.
"""
from pathlib import Path
import hashlib,importlib.util,json,os,shlex,stat,sys,time
GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
OUT=HERE/'outer-controller-execution/native-terminal-archive'
OWNER_SHA='256426c11f5dd4ab6bacfb9d17e2c7d9fde21c092914108e57449ca79ab161eb'
PLAN_SHA='cae68e777f97a07d0f35ac97f6d59d40383409b87077ee18e54a10b3c035cbf7'
LAUNCH_SHA='1064d43d80eb91f6f08472cff5ec812fcadd4faa0794ef51fbce5d104f1a3579'
def identity(s):
 return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
def pin(p):
 p=Path(p);a=identity(p.stat());b=p.read_bytes();assert identity(p.stat())==a
 return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=a)
def load(path,expected,name):
 p=pin(path);assert p['sha256']==expected and p['identity']['mode']=='0o444'
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);assert pin(path)==p;return m

def main():
 assert not OUT.exists()
 op=pin(HERE/'outer-controller-execution/root-original-live-owner.json');pp=pin(HERE/'original-outer-launch-plan.json');lp=pin(HERE/'outer-controller-execution/root-original-timer-launch-archive.json')
 assert op['sha256']==OWNER_SHA and pp['sha256']==PLAN_SHA and lp['sha256']==LAUNCH_SHA
 owner=json.loads(Path(op['path']).read_bytes());plan=json.loads(Path(pp['path']).read_bytes());launch=json.loads(Path(lp['path']).read_bytes())
 assert owner['pid']==2106059 and owner['starttime_ticks']==61690056 and owner['invocation_id']=='a812711de5334c3fa00da9088587811e' and owner['observed_live'] is True
 assert owner['unit']==plan['unit']=='robotron-quality32-CE1059-vs-joint-profile06-fresh-next8M-controller-original01-20261020.service'
 assert not Path('/proc',str(owner['pid'])).exists(),'Original outer must have actually exited; leave live original untouched'
 assert launch['unit']==owner['unit'] and launch['timer']==owner['timer'] and launch['timer_invocation_id']==owner['timer_invocation_id']
 control=load(GAME/'tools/quality_capacity_proposal/control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_outer_close_control')
 runtime=load(GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_outer_close_runtime')
 shown=control.show(owner['unit']);control.original_terminal(shown,owner)
 assert shown.get('ControlGroup','') in ('',owner['cgroup'])
 if not shown.get('ControlGroup'):assert not Path('/sys/fs/cgroup'+owner['cgroup']).exists()
 assert shown['MemoryMax']==str(1<<30) and runtime.duration_seconds(shown['CPUQuotaPerSecUSec'])==2 and runtime.duration_seconds(shown['RuntimeMaxUSec'])==37800 and shown['TasksMax']=='256' and shown['SendSIGKILL']=='no' and shown['KillMode']=='mixed' and runtime.duration_seconds(shown['TimeoutStopUSec'])==180
 group=Path('/sys/fs/cgroup'+owner['cgroup']);assert not group.exists() or not (group/'cgroup.procs').read_text().strip()
 context=dict(unit=owner['unit'],timer=owner['timer'],timer_invocation_id=owner['timer_invocation_id'])
 # Validate the original launch-time timer against the captured invocation.
 launch_full8=[]
 for rec in [launch['timer_show'],launch['timer_cat']]:
  for channel in ['stdout','stderr']:
   expected=rec[channel];actual=pin(expected['path']);assert all(actual[k]==expected[k] for k in ['path','sha256','bytes']);assert all(actual['identity'][k]==v for k,v in expected['identity'].items());launch_full8.append(actual)
 launchshown=control.fields(launch['timer_show']);assert control.timer_state(launchshown,context)=='original_loaded' and launch['timer_cat']['exit']==0
 OUT.mkdir()
 result=dict(schema='robotron-root-audit-original-result-and-GC-aware-owned-release-v1',source=pin(Path(__file__)),original=owner,original_owner_pin=op,original_outer_plan=pp,original_launch_descriptor_full8=launch_full8,original_exec_code=1,original_exit=int(shown['ExecMainStatus']),original_result=shown['Result'],timer_launch_archive=lp,full_original_archives=[],original_archive_status=[],all_six_original_archive_commands_succeeded=False,original_archived_before_release=False,owned_release=[],unit_released=False,lifecycle_complete=False,payload_retried=False,original_scientific_review_rerun=False,signal_or_exit_normalized=False,error=None)
 try:
  for kind,unit in [('service',owner['unit']),('timer',owner['timer'])]:
   for action in ['show','cat','journal']:
    invocation=owner['invocation_id' if kind=='service' else 'timer_invocation_id']
    argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+invocation] if action=='journal' else ['systemctl','--user',action,unit]
    rec=control.command(OUT,'original-'+kind+'-'+action,argv);result['full_original_archives'].append(rec);result['original_archive_status'].append(dict(kind=kind,action=action,exit=rec['exit'],timed_out=rec['timed_out']))
  records=result['full_original_archives'];terminal=control.fields(records[0]);control.original_terminal(terminal,owner);assert int(terminal['ExecMainStatus'])==result['original_exit']
  assert terminal['Result']==result['original_result']
  result.update(original_archived_before_release=True,all_six_original_archive_commands_succeeded=all(x['exit']==0 and x['timed_out'] is False for x in records),terminal_timer_state=control.timer_state(control.fields(records[3]),context))
  control.publish(OUT/'root-original-terminal-archive.json',result)
  assert all(x['exit']==0 and x['timed_out'] is False for x in records[:3]+records[5:]) and records[4]['exit'] in (0,1) and records[4]['timed_out'] is False
  if records[4]['exit']!=0:
   gc=control.command(OUT,'original-timer-GC-confirm-show',['systemctl','--user','show',owner['timer']]);result['timer_GC_confirmation']=gc;assert control.timer_state(control.fields(gc),context)=='absent'
  control.original_terminal(control.show(owner['unit']),owner)
  for kind in ['timer','service']:
   rec={};result['owned_release'].append(rec);control.release_original(OUT,kind,owner,context,rec)
  assert all(x['confirmed_absent'] for x in result['owned_release']) and not Path('/proc',str(owner['pid'])).exists() and not group.exists()
  result.update(unit_released=True,lifecycle_complete=True,status='ORIGINAL_AUDIT_EXIT0_ARCHIVED_AND_RELEASED' if result['original_exit']==0 else 'ORIGINAL_AUDIT_NONZERO_PRESERVED_ARCHIVED_AND_RELEASED')
 except Exception as error:
  result.update(status='ORIGINAL_OUTCOME_PRESERVED_OWNED_RELEASE_INCOMPLETE',error=repr(error))
 # Supplement inherited descriptor PINs with all8 fields without rewriting any
 # original receipt. Original actual exits, stderr and timer-GC outcomes remain.
 result['full8_archive_files']=[pin(p) for p in sorted(OUT.iterdir()) if p.is_file()]
 control.publish(OUT/'root-original-result-and-owned-release.json',result)
 output=pin(OUT/'root-original-result-and-owned-release.json');print(json.dumps(dict(closure=output,status=result['status'],original_exit=result['original_exit'],lifecycle_complete=result['lifecycle_complete'],payload_retried=False)))
 assert result['lifecycle_complete'] is True,result.get('error')
if __name__=='__main__':
 if sys.argv[1:]==['--close-owned-terminal']:main()
 else:print('PLAN_ONLY: only original outer terminal archive and exact owned release; explicit --close-owned-terminal required')
