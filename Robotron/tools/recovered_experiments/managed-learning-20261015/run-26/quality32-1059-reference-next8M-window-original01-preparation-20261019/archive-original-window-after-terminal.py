import argparse,json,hashlib,importlib.util,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--source-sha256');args=p.parse_args()
if not args.execute:print('PLAN_ONLY: no reads, queries, outputs or owned release');raise SystemExit(0)
assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
P=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-1059-reference-next8M-window-original01-preparation-20261019');G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
def load(path,sha,name):
 assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','reader')
c=load(G/'tools/eval_capacity_proposal/control_original_pilot.py','db1119b3ea7db7e9878b7ebd89f06a3b1c126bde46a5398617a3739917a2d9b9','controller')
order=reader.read_pin(reader.pin(P/'original-window-closure-order.json'));owner=reader.read_pin(order['owner'])
s=c.show(owner['unit']);c.original_terminal(s,owner)
assert owner['pid']==2698606 and owner['starttime_ticks']==51584315 and owner['invocation_id']=='99569d105c3a450d8a966cce13a8c59e'
context={key:owner[key] for key in ('unit','timer','timer_invocation_id')};c.timer_state(c.show(owner['timer']),context)
out=Path(order['archive_directory']);assert not out.exists();out.mkdir(mode=0o700)
result=dict(schema='robotron-root-audit-original-result-and-GC-aware-owned-release-v1',original=owner,
 original_exec_code=int(s['ExecMainCode']),original_exit=int(s['ExecMainStatus']),original_result=s['Result'],
 timer_launch_archive=reader.pin(P/'execution/root-original-timer-launch-archive.json'),full_original_archives=[],original_archive_status=[],
 original_archived_before_release=False,owned_release=[],unit_released=False,lifecycle_complete=False,payload_retried=False,error=None)
for kind,unit in [('service',owner['unit']),('timer',owner['timer'])]:
 for action in ('show','cat','journal'):
  argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+owner['invocation_id' if kind=='service' else 'timer_invocation_id']] if action=='journal' else ['systemctl','--user',action,unit]
  rec=c.command(out,'original-'+kind+'-'+action,argv);result['full_original_archives'].append(rec)
  result['original_archive_status'].append(dict(kind=kind,action=action,exit=rec['exit'],timed_out=rec['timed_out']))
a=result['full_original_archives'];c.original_terminal(c.fields(a[0]),owner);state=c.timer_state(c.fields(a[3]),context)
result.update(original_archived_before_release=True,all_six_original_archive_commands_succeeded=all(row['exit']==0 for row in a),terminal_timer_state=state)
c.publish(out/'root-original-terminal-archive.json',result)
assert all(row['exit']==0 for row in a[:3]) and a[5]['exit']==0 and a[4]['exit'] in (0,1)
if a[4]['exit']!=0:
 z=c.command(out,'original-timer-GC-confirm-show',['systemctl','--user','show',owner['timer']]);result['timer_GC_confirmation']=z
 assert c.timer_state(c.fields(z),context)=='absent'
c.original_terminal(c.show(owner['unit']),owner)
for kind in ('timer','service'):
 row={};result['owned_release'].append(row);c.release_original(out,kind,owner,context,row)
assert all(row['confirmed_absent'] for row in result['owned_release'])
result.update(unit_released=True,lifecycle_complete=True,status='ORIGINAL_WINDOW_EXIT'+str(result['original_exit'])+'_ARCHIVED_AND_RELEASED',ended_unix_s=time.time())
entry=c.publish(out/'root-original-result-and-owned-release.json',result)
print(json.dumps(dict(status=result['status'],actual_original_exit=result['original_exit'],closure=entry)))
