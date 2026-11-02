from pathlib import Path
import datetime,hashlib,importlib.util,json
R=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
p=R/'postaccepted-newgame-quality-R1-audit-wait-source-preparation-20261017/control_audit.py'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='db6e9399792aecb3fb3e84e255a2e208f6a2981316f6e76c306cca5af049f986'
spec=importlib.util.spec_from_file_location('_root_capture_exact_closure',p);c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
old=R/'rejected-gap-postactivation-availability-capture-original01-root-execution-20261018';payload=R/'rejected-gap-postactivation-availability-capture-original01-20261018/result.json'
t=json.loads((old/'root-original-terminal-archive.json').read_text());owner=t['original'];unit=owner['unit'];timer=owner['timer']
assert owner['pid']==2896979 and owner['starttime_ticks']==39898709 and owner['invocation_id']=='3dfdc62a25a941a3b25e304446800da7' and owner['observed_live'] is True
assert t['original_exec_code']==1 and t['original_exit'] in (0,1) and not Path('/proc/2896979').exists()
value=json.loads(payload.read_text());assert value['sample_count']==7 and value['excluded_samples']==value['retries']==0 and value['producer_changes'] is False
assert t['original_exit']==(0 if value['issue_count']==0 else 1)
out=R/'rejected-gap-postactivation-availability-capture-original-owned-closure-root-20261018';out.mkdir(mode=0o700)
prior=old/'root-original-result-and-owned-release.json'
proof=dict(schema='robotron-root-original-availability-capture-and-owned-release-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),original=owner,original_exec_code=1,original_exit=t['original_exit'],original_result=t['original_result'],original_terminal_archive=c.pin(old/'root-original-terminal-archive.json'),actual_archive_exit_codes=[x['exit']for x in t['full_original_archives']],payload=c.pin(payload),payload_status=value['status'],issue_count=value['issue_count'],samples=7,excluded_samples=0,payload_or_observer_retried=False,stdout=c.pin(old/'stdout.txt'),stderr=c.pin(old/'stderr.txt'),all_original_archived_before_release=True)
if prior.exists():
 completed=json.loads(prior.read_text());assert completed['unit_released'] and completed['original']==owner and c.show(unit)['LoadState']==c.show(timer)['LoadState']=='not-found'
 proof.update(original_wrapper_exit=0,original_owned_release=c.pin(prior),unit_released=True,manual_release_needed=False)
else:
 state=c.show(unit);assert state['MainPID']=='0' and state['ExecMainPID']==str(owner['pid']) and state['InvocationID']==owner['invocation_id'] and state['NRestarts']=='0' and state['ExecMainCode']=='1' and int(state['ExecMainStatus'])==t['original_exit']
 stop=json.loads((old/'release-timer-stop-command.json').read_text());assert stop['exit']==5 and c.show(timer)['LoadState']=='not-found'
 _,absence=c.command(out,'original-timer-fresh-not-found-show',['systemctl','--user','show',timer]);assert absence['exit']==0
 archives=[]
 for action in ('show','cat','journal'):
  argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+owner['invocation_id']]if action=='journal'else['systemctl','--user',action,unit]
  _,rec=c.command(out,'original-service-'+action,argv);assert rec['exit']==0;archives.append(rec)
 proof.update(original_wrapper_exit=1,original_timer_stop=c.pin(old/'release-timer-stop-command.json'),actual_timer_stop_exit=5,timer_fresh_absence=absence,second_timer_stop_attempted=False,manual_release_needed=True,original_service_archives_before_release=archives)
 terminal=c.publish(out/'root-original-native-terminal-before-owned-release.json',proof)
 _,stopped=c.command(out,'release-exact-original-service-stop',['systemctl','--user','stop',unit]);assert stopped['exit']==0
 after=c.show(unit);reset=None
 if after['LoadState']!='not-found':
  assert after['InvocationID']==owner['invocation_id'] and after['MainPID']=='0' and after['ExecMainPID']==str(owner['pid']) and after['ActiveState']=='failed' and int(after['ExecMainStatus'])==t['original_exit']
  _,reset=c.command(out,'release-exact-original-failed-service-reset-failed',['systemctl','--user','reset-failed',unit]);assert reset['exit']==0
 _,final=c.command(out,'release-exact-original-service-final-show',['systemctl','--user','show',unit]);assert final['exit']==0 and c.show(unit)['LoadState']=='not-found'
 proof.update(terminal_before_owned_release=terminal,owned_release=dict(timer_already_absent=True,service_stop=stopped,reset_failed=reset,service_final=final),unit_released=True)
main=c.show('robotron-managed-run-26-d3b365c9-trainer.service');assert main['MainPID']=='2863379' and main['InvocationID']=='5a8bfc5e10674a8e9169978804378393' and main['NRestarts']=='0'
proof.update(main_owner_unchanged=True,runtime_or_controls_changed=False)
print(json.dumps(c.publish(out/'root-original-full-window-result-and-owned-release.json',proof)),flush=True)
