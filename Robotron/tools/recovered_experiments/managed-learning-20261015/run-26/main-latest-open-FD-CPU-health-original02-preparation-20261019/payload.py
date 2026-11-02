import json,os,time,hashlib,importlib.util,stat,math,urllib.request,sys
from pathlib import Path
ROOT=Path('/home/dave/source/repos/ArcadeAI');GAME=ROOT/'Robotron';RUN=GAME/'logs/managed-learning-20261015/run-26'
FOLDER=RUN/'main-latest-open-FD-CPU-health-original02-preparation-20261019'
PREP=RUN/'confirmed-scoring-quality-original01-preparation-20261018'
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
reader_path=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
assert hashlib.sha256(reader_path.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
spec=importlib.util.spec_from_file_location('_autosave_health_reader',reader_path);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
w=p.checked_module('_autosave_health_main',p.pin(RUN/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py'))
main=p.read_pin(p.pin(RUN/'post-confirmed-scoring-next8M-original01-root-preparation-20261018/job.json'))
main['held_hashes'][str(GAME/'models_dqn/managed_save.request.json.completed')]='acda2ce69c461834f4e67de18d32a215d36f98739180801608b8bb4095ed81b5'
baseline=p.read_pin(main['baseline_API']);census=p.read_pin(p.pin(PREP/'root-original-C2-runtime-census.json'))
def health():
 w.owner_and_files(main)
 for owner in [census['native_original'],census['observer_original'],census['C2_evaluator'],*census['C2_actors'].values()]:assert w.process_start(owner['pid'])==owner['starttime_ticks']
 with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:api=json.load(response)
 w.healthy(api,baseline,main['experiment'],time.time());assert not api['quality_campaign']['stale'] and not api['quality_campaign'].get('read_error')
 return api
before_API=health()
prior=p.read_pin(p.pin(RUN/'confirmed-scoring-candidate-CPU-original01-preparation-20261018/candidate-CPU-report-readonly.json'))
body_path=Path(prior['strict_phase_base']['path']);body_pin=p.pin(body_path);assert body_pin['sha256']=='9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'
body=p.checked_module('_autosave_finite_tree_only',body_pin)
# Import only Torch and call the proven finite_tree helper. Never call its
# numerical_setup/model loader, optimizer step, replay loader or verifier main.
import torch
torch.set_num_threads(2);torch.set_num_interop_threads(2);assert not torch.cuda.is_initialized()
path=GAME/'models_dqn/robotron_dqn_latest.pt'
opened_unix=time.time()
with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
 first=os.fstat(stream.fileno());assert stat.S_ISREG(first.st_mode) and first.st_uid==os.getuid() and 0<first.st_size<512*2**20
 assert 0<=opened_unix-first.st_mtime_ns/1e9<=360
 before_hash=hashlib.file_digest(stream,'sha256').hexdigest();stream.seek(0)
 checkpoint=torch.load(stream,map_location='cpu',weights_only=True)
 counts=dict(tensors=0,scalars=0,integer_scalars=0,tensor_elements=0);body.finite_tree(checkpoint,torch,counts)
 assert counts['tensors']==prior['finite']['tensors'] and counts['tensor_elements']==prior['finite']['tensor_elements']
 for key,expected in (('engine_version',28),('state_size',11128),('single_frame_state_size',2782),('frame_stack',4),('baseline_batch_size',512)):
  assert checkpoint[key]==expected,(key,checkpoint[key])
 online=checkpoint['online_state_dict'];target=checkpoint['target_state_dict'];assert set(online)==set(target) and len(online)==len(target)==100
 assert all(online[key].shape==target[key].shape and online[key].dtype==target[key].dtype for key in online)
 clocks={key:checkpoint[key] for key in ('training_steps','optimized_samples','learner_frame_count','frame_count')}
 assert all(type(value) is int and value>=prior['clocks'][key] for key,value in clocks.items())
 assert math.isclose(checkpoint['epsilon'],.1,rel_tol=0,abs_tol=1e-12) and math.isclose(checkpoint['expert_ratio'],.1,rel_tol=0,abs_tol=1e-12)
 phase=checkpoint['priority_metric_phase'];old=prior['saved_priority_metric_phase']
 for key in ('schema','phase_id','metric','root_precommit_sha256','phase_record_sha256','last_resume_record_sha256','started_from','predecessor','initial_tree','valid','invalid_reason'):
  assert phase[key]==old[key],('priority_phase',key)
 assert phase['valid'] is True and phase['metric']=='ce' and phase['priority_update_calls']>=old['priority_update_calls'] and phase['ring_rows_submitted']>=old['ring_rows_submitted']
 optimizer=checkpoint['optimizer_state_dict'];assert set(optimizer)=={'state','param_groups'} and len(optimizer['param_groups'])==1 and len(optimizer['state'])==81
 group=optimizer['param_groups'][0];ids=group['params'];assert len(ids)==len(set(ids)) and set(optimizer['state']).issubset(ids)
 for key,value in prior['adam_group'].items():
  if key=='betas':assert tuple(group[key])==tuple(value),('Adam_group',key)
  else:assert group[key]==value,('Adam_group',key)
 steps=[]
 for value in optimizer['state'].values():
  assert set(value)=={'step','exp_avg','exp_avg_sq'} and value['step'].numel()==1
  step=float(value['step'].item());assert step>0 and step.is_integer();steps.append(step)
  assert value['exp_avg'].shape==value['exp_avg_sq'].shape and value['exp_avg'].dtype==value['exp_avg_sq'].dtype
  assert bool((value['exp_avg_sq']>=0).all())
 assert min(steps)==max(steps) and min(steps)>=prior['adam_step_min']
 scaler=checkpoint['grad_scaler_state_dict'];assert set(scaler)=={'scale','growth_factor','backoff_factor','growth_interval','_growth_tracker'}
 assert scaler['scale']>0 and scaler['growth_factor']>1 and 0<scaler['backoff_factor']<1 and 0<=scaler['_growth_tracker']<scaler['growth_interval']
 stream.seek(0);after_hash=hashlib.file_digest(stream,'sha256').hexdigest();last=os.fstat(stream.fileno())
 assert before_hash==after_hash and (first.st_dev,first.st_ino,first.st_size,first.st_mtime_ns)==(last.st_dev,last.st_ino,last.st_size,last.st_mtime_ns)
after_API=health();assert all(after_API[key]>=before_API[key] and clocks[key]<=after_API[key] for key in clocks)
assert not torch.cuda.is_initialized()
# Rename/unlink metadata may legitimately change while an opened old autosave
# remains readable. Two full FD hashes and its content identity must agree.
identity=lambda info:dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,nlink=info.st_nlink)
report=dict(schema='robotron-current-autosave-open-FD-CPU-health-v1',status='PASS_CURRENT_AUTOSAVE_FD_CPU_HEALTH',observed_unix_s=time.time(),scope='Read-only CPU finite/structure/phase check of one already-existing autosave opened by descriptor. No retained model copy, new policy capture, model restore, optimizer step, replay access, game audit, quality qualification or learning-speed claim.',source_alias=str(path),opened_unix_s=opened_unix,source_opened_sha256=before_hash,source_FD_identity_before=identity(first),source_FD_identity_after=identity(last),source_alias_inode_after=path.stat().st_ino,opened_FD_content_unchanged=True,finite=counts,clocks=clocks,priority_phase=phase,Adam_state_count=81,Adam_step_min=min(steps),Adam_step_max=max(steps),logical_training_steps_minus_Adam_step=checkpoint['training_steps']-int(min(steps)),Adam_clock_scope='Report actual serialized clocks; do not attribute their difference solely to AMP skips.',Adam_group={key:value for key,value in group.items() if key!='params'},grad_scaler=scaler,Torch_version=torch.__version__,CPU_threads=torch.get_num_threads(),CPU_interop_threads=torch.get_num_interop_threads(),CUDA_initialized=torch.cuda.is_initialized(),source_model_bytes_copied=0,finite_helper=body_pin,preserved_first_reader_failure=p.pin(RUN/'main-latest-open-FD-CPU-health-original01-preparation-20261019/execution/root-original-result-and-owned-release.json'),metadata_container_correction='Only normalize Adam betas tuple versus JSON list; all numerical checks unchanged.',main_owner=main['owner'],main193_held_files_and192_original_actor_PIDs_masks_verified_before_after=True,C2_original_evaluator_and16_actors_verified_before_after=True,API_before={key:before_API[key] for key in clocks},API_after={key:after_API[key] for key in clocks},configuration_changed=False,policy_capture=False,restore_or_optimizer_step=False,replay_access=False,quality_qualified=False,promotion=False)
with (FOLDER/'CPU-health-report.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
print(json.dumps({key:report[key] for key in ('status','source_opened_sha256','finite','clocks','Adam_state_count','Adam_step_min','CUDA_initialized','policy_capture','configuration_changed')}),flush=True)
