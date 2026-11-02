from pathlib import Path
import datetime,hashlib,importlib.util,json,os,sys
R=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
p=R/'postaccepted-newgame-quality-R1-audit-wait-source-preparation-20261017/control_audit.py'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='db6e9399792aecb3fb3e84e255a2e208f6a2981316f6e76c306cca5af049f986'
s=importlib.util.spec_from_file_location('_root_original_guard_closure',p);c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
old=R/'rejected-gap-healthy-activation-reviewed2-seven-guards-original01-root-execution-20261018'
out=R/'rejected-gap-healthy-activation-reviewed2-seven-native-PASS-owned-closure-root-20261018';out.mkdir(mode=0o700)
intent=json.loads((old/'root-launch-intent.json').read_text());unit=intent['unit'];timer=intent['timer']
assert unit=='robotron-rejected-gap-healthy-activation-reviewed2-seven-guards-original01-20261018.service'
assert json.loads((old/'root-scheduling-carrier-command.json').read_text())['exit']==0
launch=dict(x.split('=',1) for x in (old/'original-launch-timer-show-stdout.txt').read_text().splitlines() if '=' in x)
assert launch['Id']==timer and launch['Unit']==unit and launch['InvocationID']=='87790d845c154821a79053eb1eb5d0e5'
state=c.show(unit);inv='4cfccec4e2ef41589e8ff07bb7f31618'
assert state['InvocationID']==inv and state['ExecMainPID']=='2838931' and state['MainPID']=='0' and state['ExecMainCode']=='1' and state['ExecMainStatus']=='0' and state['Result']=='success' and state['NRestarts']=='0'
assert not Path('/proc/2838931').exists()
text=(old/'stderr.txt').read_text();assert 'Ran 7 tests in' in text and '\nOK\n' in text and text.count(' ... ok\n')==7 and 'skipped' not in text
assert 'test_healthy_activation_reviewed2.py' in state['ExecStart'] and '/usr/bin/python3.12' in state['ExecStart']
archives=[]
for kind,u,i in [('service',unit,inv),('timer',timer,launch['InvocationID'])]:
 for action in ('show','cat','journal'):
  argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+i] if action=='journal' else ['systemctl','--user',action,u]
  _,record=c.command(out,'original-'+kind+'-'+action,argv);archives.append(record)
assert [r['exit'] for r in archives[:3]]==[0,0,0]
before=dict(schema='robotron-root-original-native-guard-outcome-and-launcher-failure-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='NATIVE7_PASS_LAUNCHER_FAILED_BEFORE_OBSERVATION',unit=unit,timer=timer,invocation_id=inv,native_ExecMainPID=2838931,observed_live_kernel_identity=False,observed_kernel_starttime_ticks=None,original_exec_code=1,original_exit=0,original_result='success',launcher_exit=1,launcher_error=c.pin(old/'root-launch-error-preserved.json'),launch_intent=c.pin(old/'root-launch-intent.json'),launch_timer_show=c.pin(old/'original-launch-timer-show-command.json'),launch_timer_cat=c.pin(old/'original-launch-timer-cat-command.json'),native_state_before_release=state,full_original_archives=archives,actual_archive_exit_codes=[x['exit'] for x in archives],stdout=c.pin(old/'stdout.txt'),stderr=c.pin(old/'stderr.txt'),tests_run=7,tests_passed=7,tests_skipped=0,payload_or_observer_retried=False,source_applied=False,runtime_activation_started=False)
before_pin=c.publish(out/'root-original-native-terminal-before-release.json',before)
release=[]
for kind,u in [('timer',timer),('service',unit)]:
 fresh=c.show(u)
 if fresh['LoadState']=='not-found':
  _,record=c.command(out,'release-'+kind+'-already-not-found-show',['systemctl','--user','show',u]);release.append(dict(unit=u,already_not_found=True,show=record));continue
 assert fresh['InvocationID']==(inv if kind=='service' else launch['InvocationID'])
 _,record=c.command(out,'release-'+kind+'-stop',['systemctl','--user','stop',u]);assert record['exit']==0
 _,final=c.command(out,'release-'+kind+'-final-show',['systemctl','--user','show',u]);assert final['exit']==0 and c.show(u)['LoadState']=='not-found'
 release.append(dict(unit=u,stop=record,final=final))
main=c.show('robotron-managed-run-26-d3b365c9-trainer.service');assert main['MainPID']=='2257565' and main['InvocationID']=='2cd616ad4ca9405c9584701229cfbf0a' and main['NRestarts']=='0'
before.update(terminal_evidence_before_release=before_pin,owned_release=release,unit_released=True,root_guard_acceptance='Actual selected reviewed2 fixture seven native tests passed. Launcher failed before live kernel observation solely on implicit timer Unit representation; preserve missing live identity and launcher failure, never fabricate generic wrapper success.',main_owner_unchanged=True)
pin=c.publish(out/'root-explicit-native7-PASS-launcher-failure-and-owned-release.json',before);print(json.dumps(pin),flush=True)
