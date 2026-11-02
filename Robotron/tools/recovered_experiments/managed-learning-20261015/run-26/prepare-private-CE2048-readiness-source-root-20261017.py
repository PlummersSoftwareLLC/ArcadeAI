"""Create additive source only; never import the proposal or numerical code."""
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
OLD=BASE/'phaseB_readiness_proposal/private_validation_phase_record_permissions_reviewed2_proposal'
NEW=BASE/'phaseB_readiness_proposal/batch2048_CE_private_validation_proposal'
assert not NEW.exists()

def pin(path):
    raw=path.read_bytes()
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))

def once(text,old,new):
    assert text.count(old)==1,(old,text.count(old))
    return text.replace(old,new,1)

def role_rename(text):
    return text.replace('kl18','ce18').replace('return_ce','restart_ce').replace('raw-kl-stage-b','ce-batch2048-stage-b')

old_lock=OLD/'source-lock.json'
assert pin(old_lock)['sha256']=='8edbe0082cb93939ebc9bfe6be922058f9c821addf72567f57d2c7a83b53b5fc'
lock=json.loads(old_lock.read_bytes())
profile_path=BASE/'batch2048_profile_horizon_proposal/profile.json'
profile=pin(profile_path)
assert profile['sha256']=='e755e22ade5cb56537b08f41f412e856da09435d88e4e71e09b22aba521eac50'
lock.update(schema='robotron-ce-batch2048-stage-b-private-v1',variants=['ce18','resume','restart_ce'],batch_rows=2048,
    source_batch_rows=4096,batch_profile=profile,input_subset=dict(begin=0,end=2048,source_attempt=1,
        selection='First2048 ordered rows of fully validated original4096 attempt01; reused18 times. Not a new replay draw.'))
lock['stage_b'].update(roles=lock['variants'],samples_per_attempt=2048,synthetic_frame_credit_per_attempt=256,
    synthetic_frame_credits_total=4608,priority_metric='ce')
lock['reconstruction_policy'].update(selection='Fixed first2048 ordered rows of original4096 attempt01 reused18 times under verified448weights; not18new draws.')
lock['restrictions'].update(CE2048_only=True,current_main_latest_or_future_owner_proof=False)
lock_bytes=(json.dumps(lock,indent=2,sort_keys=True)+'\n').encode()
lock_sha=hashlib.sha256(lock_bytes).hexdigest()

parent_old=(OLD/'cuda_trace_parent.py').read_text()
parent=role_rename(parent_old)
parent=once(parent,'SOURCE-ONLY private raw-KL Stage B constructor/learner/phase readiness.','SOURCE-ONLY private CE2048 constructor/learner/phase readiness.')
parent=once(parent,"SOURCE_LOCK_SHA256 = '8edbe0082cb93939ebc9bfe6be922058f9c821addf72567f57d2c7a83b53b5fc'",f"SOURCE_LOCK_SHA256 = '{lock_sha}'")
parent=parent.replace("lock['batch_rows']==4096","lock['batch_rows']==2048 and lock['source_batch_rows']==4096")
parent=parent.replace("lock['stage_b']['samples_per_attempt']==4096","lock['stage_b']['samples_per_attempt']==2048")
parent=parent.replace("lock['stage_b']['synthetic_frame_credit_per_attempt']==512","lock['stage_b']['synthetic_frame_credit_per_attempt']==256")
parent=parent.replace("lock['stage_b']['synthetic_frame_credits_total']==9216","lock['stage_b']['synthetic_frame_credits_total']==4608")
parent=once(parent,"    for group in ('immutable_helpers','source_files'):",
    "    profile=lock['batch_profile']; profile_path=Path(profile['path'])\n"
    "    require(profile=="+repr(profile)+" and digest(profile_path)==profile['sha256']\n"
    "        and profile_path.stat().st_size==profile['bytes']\n"
    "        and lock['stage_b']['priority_metric']=='ce'\n"
    "        and lock['input_subset']['begin']==0 and lock['input_subset']['end']==2048, 'Exact CE2048 profile/subset differs')\n"
    "    for group in ('immutable_helpers','source_files'):")
parent=parent.replace("DQN_BATCH_SIZE='4096'","DQN_BATCH_SIZE='2048'")
parent=parent.replace("'ce' if variant=='restart_ce' else 'kl'","'ce'")
parent=parent.replace("'ce-stageB-' if variant=='restart_ce' else 'kl-stageB-'","'ce2048-restart-' if variant=='restart_ce' else 'ce2048-start-'")
parent=parent.replace("'unknown' if variant=='ce18' else 'kl'","'unknown' if variant=='ce18' else 'ce'")
parent=parent.replace('isolated-raw-kl-stage-b','isolated-ce-batch2048-stage-b')
parent=parent.replace('batch_rows=4096','batch_rows=2048')
parent=once(parent,"            scope='Actual private candidate constructor/load and isolated fixed-input learner/phase-lifecycle readiness; no live adoption or learning-quality qualification',",
    "            input_subset=lock['input_subset'], batch_rows=2048, priority_metric='ce',\n"
    "            scope='Actual private CE2048 constructor/load and isolated fixed-subset learner/phase readiness; no live adoption or learning-quality qualification',")
parent=parent.replace('Readonly verified448 weights with reused genuine older attempt01 inputs are a declared regression fixture, never a new current draw',
    'Readonly verified448 weights with first2048 ordered rows of original4096 attempt01 reused18 times; a declared geometry fixture, never a new current draw')
parent=parent.replace('Previous all8 captured-vs-recomputed failures remain unchanged; no historical actualH/KL or learning-benefit claim',
    'Historical failures remain unchanged; no current replay-population, efficacy, learning-speed or throughput claim')

worker_old=(OLD/'cuda_trace_worker.py').read_text()
worker=role_rename(worker_old)
worker=once(worker,'BATCH = 4096','BATCH = 2048')
worker=once(worker,'FRAME_CREDIT = 512','FRAME_CREDIT = 256')
worker=once(worker,"cfg.per_priority_metric==('ce' if ctx.variant=='restart_ce' else 'kl')","cfg.per_priority_metric=='ce'")
worker=once(worker,'    ctx.payload,ctx.original_row,ctx.original_item=payload,row,item',
    '    # Preserve the original4096 validation above; choose one fixed ordered subset only afterwards.\n'
    '    ctx.payload,ctx.original_row,ctx.original_item=fixed_subset(payload),row,item')
subset='''def fixed_subset(payload):
    """Pure ordered slicing after the unchanged original4096 payload contract."""
    require(set(payload['inputs'])==set(INPUT_NAMES), 'Original input names differ')
    require(all(tuple(value.shape)==((4096,11128) if name in ('states','next_states') else (4096,))
        for name,value in payload['inputs'].items()), 'Original4096 geometry differs')
    draw=payload['draw']
    require(tuple(draw['indices'].shape)==(4096,) and len(draw['small_batch_fields']['actor_kind'])==4096,
        'Original4096 draw geometry differs')
    selected=dict(payload)
    selected['inputs']={name:value[:BATCH] for name,value in payload['inputs'].items()}
    selected['draw']=dict(draw, indices=draw['indices'][:BATCH],
        small_batch_fields=dict(draw['small_batch_fields'], actor_kind=draw['small_batch_fields']['actor_kind'][:BATCH]))
    return selected


'''
worker=once(worker,'class FixedReplayAdapter:',subset+'class FixedReplayAdapter:')
worker=once(worker,"require(isinstance(outputs,tuple) and len(outputs)==5,'Actual KL compiled5 ABI changed')",
    "require(isinstance(outputs,tuple) and len(outputs)==4,'Actual CE compiled4 ABI changed')")
worker=once(worker,"self.forward=dict(diagnostic=_diagnostic,ce=values[1].numpy(),priority=values[4].numpy(),",
    "self.forward=dict(diagnostic=_diagnostic,ce=values[1].numpy(),priority=values[1].numpy(),")
worker=once(worker,"require(values[4].shape==(BATCH,) and values[4].dtype==torch.float32 and\n                        outputs[4].requires_grad is False and outputs[4].grad_fn is None,\n                        'Actual fifth priority vector is not detached FP32')",
    "require(values[1].shape==(BATCH,) and values[1].dtype==torch.float32\n                        and values[3].shape==(12,), 'Actual CE vector/diagnostic geometry differs')")
worker=once(worker,"list(phase['last_diagnostics'].values())==observers.forward['diagnostics'][12:]",
    "phase['metric']=='ce' and phase['last_diagnostics'] is None")
worker=worker.replace('Expected exact cap8 boundary after fixed4096 update','Expected exact cap8 boundary after fixed2048 update')
worker=once(worker,"spec['action']=='resume' and phase['metric']=='kl'","spec['action']=='resume' and phase['metric']=='ce'")
worker=once(worker,"phase['predecessor']['metric']=='kl'","phase['predecessor']['metric']=='ce'")
worker=worker.replace('Actual KL resume phase differs','Actual CE resume phase differs').replace('Actual explicit return-to-CE phase differs','Actual explicit CE-to-CE restart phase differs')
worker=once(worker,"private_serving_graph_release=ctx.graph_release,source_lock_sha256=ctx.parent.SOURCE_LOCK_SHA256,",
    "private_serving_graph_release=ctx.graph_release,source_lock_sha256=ctx.parent.SOURCE_LOCK_SHA256,\n        input_subset=ctx.lock['input_subset'],batch_rows=BATCH,priority_metric='ce',")

def functions(text):
    return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
preservation={}
for label,old,new in [('parent',parent_old,parent),('worker',worker_old,worker)]:
    original=functions(role_rename(old));final=functions(new)
    preservation[label]=dict(renamed_symbols='kl18→ce18, return_ce→restart_ce, raw-kl-stage-b→ce-batch2048-stage-b',
        unchanged_bodies=[k for k,v in original.items() if final.get(k)==v],
        changed_bodies=[k for k,v in original.items() if k in final and final[k]!=v],
        added_bodies=[k for k in final if k not in original])
assert preservation['worker']['changed_bodies']==['setup','StepObservers','one_attempt','run']
assert 'verify_progress' in preservation['worker']['unchanged_bodies']
assert 'construct_and_load' in preservation['worker']['unchanged_bodies']

NEW.mkdir()
def write(name,raw):
    if isinstance(raw,str):raw=raw.encode()
    p=NEW/name
    with p.open('xb') as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return pin(p)
files=[write('source-lock.json',lock_bytes),write('cuda_trace_parent.py',parent),write('cuda_trace_worker.py',worker)]
for name,old,new in [('parent',parent_old,parent),('worker',worker_old,worker)]:
    files.append(write(name+'.patch',''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original/'+name,tofile='CE2048/'+name))))
files.append(write('source-preservation.json',json.dumps(preservation,indent=2)+'\n'))
note='''SOURCE ONLY; UNEXECUTED. Root owns any real imports, tests, GPU or service actions.
This additive CE2048 private validation reuses the reviewed2 StageB owned parent,
process/cgroup/resource/storage lifecycle and actual RainbowAgent load/prefetch/
fusedAMP/Adam/native-update observers. Production source bodies are unchanged.
All roles use CE:18 fixed calls, CE resume with0 calls, new CE restart with0 calls.
The four-output CE loss and CE priority readback are observed honestly; the old
five-output KL contract and signed/mass diagnostics are not applied to CE.

The checkpoint is the existing strict CPU-verified448 fixture, not current main
latest or future2048 owner. The FULL historical4096 original attempt01 payload is
validated unchanged before selecting exactly its first2048 ordered rows and the
matching indices/actor-kind. The original source and payload are never modified.
This fixed subset is reused18 times, never described as new replay draws. Native
tree indices, duplicate-last leaf updates and the actual six-million SumTree are
checked. Synthetic frame credits256/call enforce exact2048 samples at cap8 and
never advance learner frames. Natural diagnostics at ordinal18 remain unreclocked.
No19th call/rescue; all18AMPskips means readinessFalse. Adam/scaler/progress bodies,
source copies, owned128 serving graph construction/postload then explicit PRIVATE
release before learner work, and all resource limits remain preserved.

Default PLAN only. Actual launch is forbidden until current four-cohort quality,
original audits/independent reviews, owned cleanup and explicit root freeze release.
Then root must review this source+guards, precommit its exact lock/output/retained
unit, and execute once on free physicalGPU0 with a CUDAhidden stdlib parent under
the existing delegated robotron-snapshot-smoke unit pattern. Numerical child must
use the actual free-threaded Python/Torch environment and keep GPU1/main192 intact.
This is geometry and lifecycle readiness only, never efficacy, speed, current
ring restoration, latest finiteness or serving/learning concurrency evidence.
'''
files.append(write('PREPARATION.txt',note))
manifest=dict(schema='robotron-private-CE2048-readiness-source-preparation-v1',status='SOURCE_ONLY_UNEXECUTED_PENDING_PEER_AND_GUARDS',files=files,
    original_parent=pin(OLD/'cuda_trace_parent.py'),original_worker=pin(OLD/'cuda_trace_worker.py'),original_lock=pin(old_lock),
    profile=profile,source_lock_sha256=lock_sha,actual_gpu_execution=None,actual_imports_or_tests=False,source_freeze_released=False,
    qualification=False,activation=False,scope='Future private CE2048 default-four-output whole learner and phase geometry fixture only.')
mp=write('preparation-manifest.json',json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(manifest=mp,preservation=preservation)))
