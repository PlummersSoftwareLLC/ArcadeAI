import json,hashlib,importlib.util,time,urllib.request
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');Q=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-CE1059-vs-post-score-carry849-next8M-original01-preparation-20261019')
def load(path,sha,name):
 assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
p=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','reader')
c=load(G/'tools/eval_capacity_proposal/control_original_pilot.py','db1119b3ea7db7e9878b7ebd89f06a3b1c126bde46a5398617a3739917a2d9b9','control')
o=load(G/'tools/quality_capacity_proposal/quality32_runtime_guard_v3.py','e733f6f442d86404de0a2089ce84cb85a91ecf522c60da18be838e4c05f3f95e','observer')
r=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','runtime')
raw=load(G/'tools/eval_capacity_proposal/raw_api_witness_v1.py','9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0','raw')
binding=p.read_pin(p.pin(Q/'runtime-bindings/campaign-binding.json'));main=p.read_pin(p.pin(Q/'runtime-bindings/main-binding.json'))
window=load(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py','f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3','main')
window.owner_and_files(main)
api=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5));window.healthy(api,p.read_pin(main['baseline_API']),main['experiment'],time.time())
assert 0<=time.time()-(G/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime<=360
owners=[]
for label,path,closurepath in [('native',Q/'runtime-bindings/native-owner.json',Q/'native-execution/native-terminal-archive/root-original-result-and-owned-release.json'),('outer',Q/'outer-controller-execution/root-original-live-owner.json',Q/'outer-controller-execution/native-terminal-archive/root-original-result-and-owned-release.json')]:
 owner=p.read_pin(p.pin(path));fields=c.show(owner['unit']);live=fields.get('MainPID')==str(owner['pid'])
 if live:
  assert fields['InvocationID']==owner['invocation_id'] and fields['NRestarts']=='0'
  assert int(Path('/proc',str(owner['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])==owner['starttime_ticks']
 elif fields.get('LoadState')=='loaded':c.original_terminal(fields,owner)
 else:
  closed=p.read_pin(p.pin(closurepath));r.archived_closure(closed,owner,lambda entry,as_json=True:p.read_pin(entry,as_json=as_json),exit_zero=False)
 owners.append(dict(role=label,original=owner,live=live,actual_exit=None if live else fields.get('ExecMainStatus')))
C=Path(binding['campaign']['output_directory']);status=json.loads((C/'status.json').read_bytes())
assert status['plan_sha256']==binding['campaign']['plan_sha256'];current=status.get('current_leg');leg=None;births=0;known=0
if current:
 record=status['legs'][current-1];path=Path(record['evaluator_status_path'])
 if path.exists():
  leg=json.loads(path.read_bytes())
  assert all(type(leg[key]) is int and leg[key]>=0 for key in ('count','started','pending','abandoned'))
  assert leg['count']+leg['pending']+leg['abandoned']==leg['started']
  if record['state']=='running':
   assert time.time()-path.stat().st_mtime<10
   epath=Q/'runtime-bindings/leg-births'/f'leg{current}-evaluator.json';apath=Q/'runtime-bindings/leg-births'/f'leg{current}-actors.json'
   evaluator=p.read_pin(p.pin(epath));actual=o.live_process(evaluator['pid'],owners[0]['original']['pid'],owners[0]['original']['cgroup'],evaluator['command']);assert actual['starttime_ticks']==evaluator['starttime_ticks']
   if apath.exists():
    actors=p.read_pin(p.pin(apath));assert set(actors)==set(map(str,range(4096,4128)))
    for slot,actor in actors.items():
     actual=o.live_process(actor['pid'],evaluator['pid'],evaluator['cgroup'],actor['command']);assert all(actual[key]==actor[key] for key in ('starttime_ticks','affinity')) and leg['actor_pids'][slot]==actor['pid']
    births=32
   elif leg['phase']!='warming':raise ValueError('Original live actor registry missing after warmup')
   if leg['phase']!='warming':assert leg['boundary']['ready'] and leg['boundary']['acknowledged']==32
 startpath=Path(record['evaluator_status_path']).parent/'journal/measurement_starts.jsonl'
 if startpath.exists():
  starts=[json.loads(line) for line in startpath.read_bytes().splitlines() if line.strip()];known=len({row['client_slot'] for row in starts if row.get('experiment')==leg.get('label')}) if leg else 0
samples=sorted((Q/'runtime-bindings/main-samples').glob('*.json'));latest=p.read_pin(p.pin(samples[-1]));joined=raw.rejoin_witness(latest,lambda entry:p.read_pin(entry,as_json=False));window.healthy(joined,p.read_pin(main['baseline_API']),main['experiment'],latest['unix_s'])
if owners[0]['live']:assert time.time()-latest['unix_s']<30
assert not list((Q/'runtime-bindings/main-rejections').glob('*.json'))
assert p.digest(binding['reference']['path'])==binding['reference']['sha256'] and p.digest(binding['candidate']['path'])==binding['candidate']['sha256']
resultpath=Q/'native-execution/root-controller-result.json';result=json.loads(resultpath.read_bytes()) if resultpath.exists() else None
out=dict(unix_s=time.time(),classification='VERIFIED_WAIT' if any(owner['live'] for owner in owners) else 'ORIGINAL_CAMPAIGN_AND_CONTROLLER_TERMINAL',original_owners=owners,native_state=status['state'],current_leg=current,role=None if not current else status['legs'][current-1]['role'],phase=None if leg is None else leg['phase'],counts=None if leg is None else {key:leg[key] for key in ('count','started','pending','abandoned')},known_start_slots=known,live_original_actor_births_verified=births,main_guard_samples=len(samples),rejected_main_observations=0,main=dict(client_count=api['client_count'],learner_frame_count=api['learner_frame_count'],training_steps=api['training_steps'],fps=api['fps']),original_result=result,quality_qualification_pending=True,learning_speed_gain_verified=False)
with (Q/'live-monitor-20261019.jsonl').open('a') as stream:stream.write(json.dumps(out,allow_nan=False)+'\n')
print(json.dumps(out,allow_nan=False))
