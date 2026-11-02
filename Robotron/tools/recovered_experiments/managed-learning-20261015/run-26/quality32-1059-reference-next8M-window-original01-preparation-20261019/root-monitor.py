import json,hashlib,importlib.util,time,urllib.request
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-1059-reference-next8M-window-original01-preparation-20261019')
def load(path,sha,name):
 assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','reader')
controller=load(G/'tools/eval_capacity_proposal/control_original_pilot.py','db1119b3ea7db7e9878b7ebd89f06a3b1c126bde46a5398617a3739917a2d9b9','controller')
selection=reader.read_pin(reader.pin(P/'root-selection.json'));job=reader.read_pin(selection['job']);window=load(Path(selection['source']['path']),selection['source']['sha256'],'window')
owner=reader.read_pin(reader.pin(P/'execution/root-original-live-owner.json'));fields=controller.show(owner['unit'])
assert fields['InvocationID']==owner['invocation_id'] and fields['NRestarts']=='0'
live=fields.get('MainPID')==str(owner['pid'])
if live:assert window.process_start(owner['pid'])==owner['starttime_ticks']
else:controller.original_terminal(fields,owner)
status_path=Path(job['output'])/'status.json';status=json.loads(status_path.read_bytes()) if status_path.exists() else None
result_path=Path(job['output'])/'result.json';result=reader.read_pin(reader.pin(result_path)) if result_path.exists() else None
api=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5));baseline=reader.read_pin(job['baseline_API']);window.healthy(api,baseline,job['experiment'],time.time())
transition=bool(status and status.get('both_horizons') and live and result is None)
if result and result.get('status')=='CAPTURED_FIRST_BOTH_HORIZONS':
 job['held_hashes'][str(G/'models_dqn/managed_save.request.json.completed')]=result['completed_slot_transition']['after']['actual_pin']['sha256']
 reader.read_pin(result['checkpoint'],as_json=False)
if not transition:window.owner_and_files(job)
else:
 assert status['learner_frames']>=8000000 and status['learner_accepted']>=8000000
 assert window.process_start(job['owner']['pid'])==job['owner']['starttime_ticks']
 assert time.time()-status_path.stat().st_mtime<65
 assert (Path(job['output'])/'first-durable-both-horizons.json').exists()
assert reader.digest(selection['reference']['path'])==selection['reference']['sha256']
summary=dict(unix_s=time.time(),classification='VERIFIED_WAIT' if live else 'ORIGINAL_WINDOW_TERMINAL',original_owner=owner,original_live=live,original_exit=None if live else int(fields['ExecMainStatus']),window_status=status,window_status_age_s=None if status is None else time.time()-status_path.stat().st_mtime,original_result=result,main=dict(client_count=api['client_count'],learner_frame_count=api['learner_frame_count'],training_steps=api['training_steps'],fps=api['fps']),held_files_checked=not transition,source_and_recipe_changed=False,quality_qualified=False,learning_speed_gain_verified=False)
with (P/'live-monitor-20261019.jsonl').open('a') as stream:stream.write(json.dumps(summary,allow_nan=False)+'\n')
print(json.dumps(summary,allow_nan=False))
