from pathlib import Path
import json,time,hashlib,importlib.util,urllib.request,os,subprocess
R=Path('/home/dave/source/repos/ArcadeAI/Robotron');RUN=R/'logs/managed-learning-20261015/run-26';P=RUN/'confirmed-scoring-quality-original01-preparation-20261018';D=P/'capacity32-confirmed1059-raw-API-v1-preparation-20261019'
f=R/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py';assert hashlib.sha256(f.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071';spec=importlib.util.spec_from_file_location('_current_study_monitor_reader',f);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
wentry=p.pin(RUN/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py');assert wentry['sha256']=='f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3';w=p.checked_module('_current_study_monitor_main',wentry);binding=p.read_pin(p.pin(D/'runtime-bindings/main-binding.json'));w.owner_and_files(binding)
api=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5));w.healthy(api,p.read_pin(binding['baseline_API']),binding['experiment'],time.time());age=time.time()-(R/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime;assert 0<=age<=360
s=json.loads((R/'logs/managed-learning-20261015/state.json').read_bytes());assert s['incumbent']['sha256']=='4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e' and s['incumbent']['full_game_quality_qualified'] is True
selection=p.read_pin(p.pin(D/'study-selection.json'));plan=p.read_pin(selection['plan']);status_path=Path(plan['job']['directory'])/'status.json';status=json.loads(status_path.read_bytes()) if status_path.exists() else {}
owners=[]
for child in ('outer-controller-execution','pilot-root-execution'):
 owner=p.read_pin(p.pin(D/child/'root-original-live-owner.json'))
 raw=subprocess.check_output(['systemctl','--user','show',owner['unit']],text=True,timeout=10);fields=dict(x.split('=',1) for x in raw.splitlines() if '=' in x)
 if fields.get('LoadState')=='not-found':
  closure=p.read_pin(p.pin(D/child/'native-terminal-archive/root-original-result-and-owned-release.json'));assert closure['original']==owner and closure['unit_released'] and closure['lifecycle_complete']
  fields=dict(LoadState='not-found',MainPID='0',InvocationID=owner['invocation_id'],ExecMainPID=str(owner['pid']),ExecMainCode=str(closure['original_exec_code']),ExecMainStatus=str(closure['original_exit']),archived_and_owned_released=True)
 else:
  assert fields['InvocationID']==owner['invocation_id'] and fields['NRestarts']=='0' and fields['MainPID'] in ('0',str(owner['pid']))
  if fields['MainPID']!='0':assert w.process_start(owner['pid'])==owner['starttime_ticks']
 owners.append(dict(original=owner,fields={k:fields.get(k) for k in ('LoadState','MainPID','ExecMainPID','ExecMainCode','ExecMainStatus','ActiveState','SubState','InvocationID','MemoryCurrent','MemoryPeak','archived_and_owned_released')}))
active=owners[1]['fields']['MainPID']!='0'
census=p.read_pin(p.pin(D/'root-original32-live-runtime-census.json'))
actor_checks=0
if active and status.get('phase') in ('collecting','draining'):
 assert set(status['actor_pids'])==set(map(str,range(4096,4128)))
 for slot,owner in census['original32_actors'].items():
  assert status['actor_pids'][slot]==owner['pid'] and w.process_start(owner['pid'])==owner['starttime_ticks'] and sorted(os.sched_getaffinity(owner['pid']))==owner['affinity'];actor_checks+=1
 assert status['checkpoint_sha256']==plan['checkpoint']['sha256'] and status['count']+status['pending']==status['started'] and status['abandoned']==0
samples=sorted((D/'runtime-bindings/main-samples').glob('*.json'));sample=p.read_pin(p.pin(samples[-1]));raw=p.checked_module('_current_raw_witness',p.pin(R/'tools/eval_capacity_proposal/raw_api_witness_v1.py'));assert p.digest(R/'tools/eval_capacity_proposal/raw_api_witness_v1.py')=='9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0';decoded=raw.rejoin_witness(sample,lambda e:p.read_pin(e,as_json=False));w.healthy(decoded,p.read_pin(binding['baseline_API']),binding['experiment'],sample['unix_s']);sample_age=time.time()-sample['unix_s']
if active:assert sample_age<30
rejections=sorted((D/'runtime-bindings/main-rejections').glob('*.json'))
result_path=D/'pilot-root-execution/root-controller-result.json'
life=status_path.parent/'journal/lives.jsonl'
q=api['quality_campaign'];assert q['state']=='finished' and q['outcome']=='qualified_improvement' and not q['stale'] and not q.get('read_error')
value=dict(unix_s=time.time(),classification='VERIFIED_WAIT' if active else 'ORIGINAL_NATIVE_TERMINAL_REVIEW_PENDING_OR_COMPLETE',main={k:api[k] for k in ('client_count','learner_frame_count','training_steps')},main193_files_and192_original_actor_PIDs_affinities_verified=True,autosave_age_s=age,pipeline_errors={k:api['host_pipeline'][k]['errors'] for k in ('inference','actor_refresh','target_refresh','learner_priority')},bank_write_failures=api['bank_persistence']['write_failures'],original_owners=owners,original32_actor_births_affinities_verified=actor_checks,private_status={k:status.get(k) for k in ('phase','count','started','pending','abandoned','elapsed_s')},private_status_age_s=time.time()-status_path.stat().st_mtime if status_path.exists() else None,private_life_journal_age_s=time.time()-life.stat().st_mtime if life.exists() else None,known_start_slots=len(status.get('cohort',{}).get('started_actor_slots',[])),guard_samples=len(samples),latest_guard_sample_age_s=sample_age,rejected_observations=[str(x) for x in rejections],original_controller_result=json.loads(result_path.read_bytes()) if result_path.exists() else None,quality_winner_still_protected=True,capacity_speedup_verified=False,learning_speed_gain_verified=False)
with (D/'live-monitor-20261019.jsonl').open('a') as stream:stream.write(json.dumps(value,separators=(',',':'))+'\n');stream.flush();os.fsync(stream.fileno())
print(json.dumps(value))
