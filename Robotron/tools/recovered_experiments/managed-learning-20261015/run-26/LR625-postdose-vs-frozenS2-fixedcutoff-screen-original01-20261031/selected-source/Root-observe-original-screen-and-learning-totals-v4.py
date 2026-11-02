import pathlib,json,time,urllib.request,csv,datetime,zoneinfo,hashlib
b=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26');j=b/'LR625-postdose-vs-frozenS2-fixedcutoff-screen-original01-20261031';m=b/'fleet-only-v6-overlap-handoff-original01-20261031';out=j/'Root-controller-runtime-original01'
def birth(pid):
 try:return int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
owner=json.loads((out/'owner.json').read_text());outerlive=birth(owner['pid'])==owner['birth'];hb=json.loads((out/'heartbeat.json').read_text());leg=hb.get('leg');now=time.time();n=time.monotonic_ns();observation={'unix_s':now,'UTC':datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat(),'outer_live':outerlive,'current_leg':leg}
for key in ['R1','C1']:
 closed=out/(key+'-closed-and-scores.json');status=j/key/'runtime-original01/status.json';result=j/key/'runtime-original01/result.json'
 if closed.exists():
  d=json.loads(closed.read_text());s=d['score_seal'];observation[key]={'state':'ORIGINAL0_CLOSED_SCORES_SEALED','mean':s['mean_score'],'median':s['median_score'],'completed':s['n_completed'],'censored':s['n_censored']}
 elif status.exists():
  s=json.loads(status.read_text());anchor=s.get('anchor');v={'phase':s['phase'],'age_s':now-s['observed_unix_s'],'tracked':s['n_scored'],'completed':s['n_completed'],'playing':s['n_emulators_active'],'errors':s['errors']}
  if anchor:
   remaining=(anchor['deadline_monotonic_ns']-n)/1e9;v['remaining_min']=max(0,remaining/60);v['cutoff_Central']=datetime.datetime.fromtimestamp(now+remaining,zoneinfo.ZoneInfo('America/Chicago')).strftime('%I:%M:%S %p %Z')
  observation[key]=v
 if result.exists() and not closed.exists():
  d=json.loads(result.read_text());observation[key+'_native_result']={'complete':d.get('complete'),'errors':d.get('errors',[])[:2],'main_health_failure':str(d.get('main_health_failure'))[:500]}
with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=8) as f:api=json.load(f)
st=json.loads((m/'v6-fleet-original01/status.json').read_text());control=(b.parents[2]/'models_dqn/learning_control.json') if False else pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron/models_dqn/learning_control.json');controlsha=hashlib.sha256(control.read_bytes()).hexdigest()
observation['Main']={k:api.get(k) for k in ['ts','fps','client_count','training_enabled','learner_frame_count','optimized_samples','lr','epsilon','expert_ratio']};observation['Main']['same_original_birth']=birth(208501)==27823352;observation['Main']['control_sha256']=controlsha;observation['v6']={'same_original_birth':birth(965562)==30270092,'counts':st['counts'],'errors':st['errors'][:2],'rebind_hints':sum(x['physical_binding_history_count']>x['incarnation'] for x in st['slots'].values())}
row={'observed_unix_s':now,'API_ts':api['ts'],'leg':leg,'game_FPS':api['fps'],'client_count':api['client_count'],'learner_frames':api['learner_frame_count'],'optimized_samples':api['optimized_samples'],'lr':api['lr'],'epsilon':api['epsilon'],'expert':api['expert_ratio'],'control_sha256':controlsha,'supervisor_active_train':st['counts']['active_train'],'supervisor_quarantined':st['counts']['quarantined'],'outer_live':outerlive};p=j/'Root-control-and-throughput-observations-original01.csv';new=not p.exists()
with p.open('a') as f:
 w=csv.DictWriter(f,fieldnames=list(row))
 if new:w.writeheader()
 w.writerow(row)

try:
 exposure=api['host_pipeline']['learning_exposure']; opt=exposure['optimizer']; replay=exposure['replay']; totals=opt['total']; sources=replay['accepted_by_source_total']
 erow={'observed_unix_s':now,'API_ts':api['ts'],'leg':leg,'pipeline_snapshot_age_s':api.get('pipeline_snapshot_age_s'),'pipeline_read_error':api.get('pipeline_read_error'),'optimizer_available':opt['available'],'replay_available':replay['available']}
 for family,value in [('optimizer',opt),('replay',replay)]:
  for key in ['process_id','instance_monotonic_ns','epoch','epoch_reason']:erow[family+'_'+key]=value[key]
 for key in ['attempts_started','outcomes_recorded','applied','amp_skipped','unavailable']:erow['optimizer_'+key+'_total']=totals[key]
 erow['optimizer_unclassified_started_total']=opt['unclassified_started_total'];erow['optimizer_prior_epoch_outcomes_total']=opt['prior_epoch_outcomes_total']
 erow.update(replay_accepted_total=replay['accepted_total'],replay_accepted_learner_total=replay['accepted_learner_total'],learner_frame_count=api['learner_frame_count'],logical_training_steps=api['training_steps'],optimized_samples=api['optimized_samples'],Main_FPS=api['fps'],control_sha256=controlsha)
 for key in ['dqn','epsilon','expert','eval','unattributed']:erow['replay_accepted_'+key+'_total']=sources[key]
 ep=j/'Root-applied-update-and-replay-intake-observations-original01.csv';enew=not ep.exists()
 with ep.open('a') as f:
  ew=csv.DictWriter(f,fieldnames=list(erow))
  if enew:ew.writeheader()
  ew.writerow(erow)
 observation['actual_exposure']={'applied':totals['applied'],'AMP_skipped':totals['amp_skipped'],'unavailable':totals['unavailable'],'new_replay':replay['accepted_total'],'learner_replay':replay['accepted_learner_total'],'optimizer_pending_unclassified':opt['unclassified_started_total'],'pipeline_age_s':api.get('pipeline_snapshot_age_s')}
except (KeyError,TypeError,ValueError) as error:
 observation['exposure_trace_error']=repr(error)


diag=api.get('c51_diagnostics') or {}
stability={'observed_unix_s':now,'API_ts':api['ts'],'leg':leg,'pipeline_snapshot_age_s':api.get('pipeline_snapshot_age_s'),'pipeline_read_error':api.get('pipeline_read_error'),'bank_persistence_read_error':api.get('bank_persistence_read_error'),'control_sha256':controlsha}
for key in ['frame_count','learner_frame_count','training_steps','optimized_samples','steps_per_sec','fps','client_count','lr','epsilon','expert_ratio','loss','grad_norm','bc_loss','q_mean','q_min','q_max','sample_dqn_frac','sample_epsilon_frac','sample_expert_frac','memory_buffer_size','memory_buffer_pct','avg_inf_ms','train_sample_ms','train_transfer_ms','train_compute_ms','train_priority_ms','train_step_ms','cpu_util','cpu_count','cpu_load_1m','cpu_load_5m','cpu_load_15m']:
 stability[key]=api.get(key)
for key in ['below_support_mass','above_support_mass','edge_atom_mass','target_entropy','action_q_gap','categorical_kl']:stability['c51_'+key]=diag.get(key)
for device in [0,1]:
 for suffix in ['present','name','util','mem_util','mem_used_mib','mem_total_mib','temp_c','power_w','power_limit_w','clock_mhz']:stability['gpu'+str(device)+'_'+suffix]=api.get('gpu'+str(device)+'_'+suffix)
stability['c51_diagnostics_json']=json.dumps(diag,separators=(',',':'))
stability['game_settings_json']=json.dumps(api.get('game_settings'),separators=(',',':'))
stability['bank_persistence_json']=json.dumps(api.get('bank_persistence'),separators=(',',':'))
sp=j/'Root-main-learner-stability-and-system-timing-observations-original01.csv';snew=not sp.exists()
with sp.open('a') as f:
 sw=csv.DictWriter(f,fieldnames=list(stability))
 if snew:sw.writeheader()
 sw.writerow(stability)
observation['Main_learner_metrics']={key:api.get(key) for key in ['loss','grad_norm','bc_loss','q_mean']}
observation['Main_learner_metrics']['categorical_kl']=diag.get('categorical_kl')

print(json.dumps({'UTC':observation['UTC'],'Main_learner_metrics':observation['Main_learner_metrics'],'exposure':observation.get('actual_exposure',observation.get('exposure_trace_error')),'outer_live':outerlive,'leg':leg,'legs':{k:v for k,v in observation.items() if k.startswith(('R1','C1'))},'Main_FPS':api['fps'],'Main_clients':api['client_count'],'Main_healthy_same_original':observation['Main']['same_original_birth'] and api['training_enabled'],'controls_unchanged':controlsha=='b38b801fbdbfd872b8f859e7ec99e7341d3b59e0d0b333074a75145625db55c4','v6_same_original_live':observation['v6']['same_original_birth'],'v6_status_age_s':now-st['updated_unix_s'],'v6_counts':st['counts'],'v6_errors':st['errors'][:2],'v6_rebind_hints':observation['v6']['rebind_hints']}))

