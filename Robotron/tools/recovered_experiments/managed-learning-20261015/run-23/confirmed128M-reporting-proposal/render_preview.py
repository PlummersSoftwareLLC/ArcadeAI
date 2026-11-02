#!/usr/bin/env python3
"""Render proposal only, explicitly reusing root model attestations (no payload I/O)."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,importlib.util,json,os,sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
GAME=REPO/'Robotron';BASE=GAME/'logs/managed-learning-20261015'
PROPOSED=HERE/'proposed';started=datetime.now(timezone.utc).isoformat()
sys.path.insert(0,str(GAME/'tools'))
prepared=json.loads((HERE/'prepared.json').read_bytes())
data_path=PROPOSED/'learning-and-throughput-progress.json';data=json.loads(data_path.read_bytes())
renderer_path=PROPOSED/'render_learning_progress.py'
spec=importlib.util.spec_from_file_location('proposed_confirmed128_renderer',renderer_path)
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
original_digest=renderer.digest
canonical=GAME/'tools/render_learning_progress.py'
models=prepared['model_payload_refresh']['files']
model_checks=[];source_checks=[];checkpoint_validation_requests=[]
def stat_record(path):
    x=Path(path).stat()
    return dict(size_bytes=x.st_size,mtime_ns=x.st_mtime_ns,inode=x.st_ino,device=x.st_dev,mode=oct(x.st_mode&0o777),nlink=x.st_nlink)
def scoped_digest(path):
    path=Path(path).resolve();key=str(path)
    if key in models:
        assert stat_record(path)==models[key]['stat'],key+' changed model stat'
        model_checks.append(key)
        return models[key]['sha256_attestation']
    if path==canonical:
        assert original_digest(path)==prepared['before']['render_learning_progress.py']['sha256']
        actual=original_digest(renderer_path)
        assert actual==data['plotting']['renderer_sha256']
        source_checks.append(key+' -> '+str(renderer_path))
        return actual
    result=original_digest(path);source_checks.append(key);return result
original_backend=renderer.validate_backend
def scoped_backend(receipt,*,verify_checkpoint=False):
    checkpoint_validation_requests.append(dict(label=receipt['label'],requested=verify_checkpoint,
        performed=False,scope='Existing pinned root full-leg/model-copy/isolation attestations reused; unchanged statistical/backend validator runs.'))
    return original_backend(receipt,verify_checkpoint=False)
renderer.digest=scoped_digest;renderer.validate_backend=scoped_backend
output=PROPOSED/'learning-and-throughput-progress.png'
assert not output.exists()
result=renderer.render(data,output)
assert result['validated_cohorts']==22 and result['disjoint_games']==2385
assert result['observational_guard_count']==1 and result['validated_batch_trials']==3
assert all(Path(v['path']).read_bytes()==(HERE/'before'/n).read_bytes() for n,v in prepared['before'].items())
assert data['fixed_transport_learning'][:-1]==json.loads((HERE/'before/learning-and-throughput-progress.json').read_bytes())['fixed_transport_learning']
for path,record in models.items():assert stat_record(path)==record['stat']
assert not any(x=='torch' or x.startswith('torch.') for x in sys.modules)
result.update(schema='robotron-confirmed128M-proposal-render-validation-v1',started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),proposal_only=True,canonical_untouched=True,model_payloads_rehashed=False,model_source_attestations=models,model_stat_checks=len(model_checks),model_source_stat_checks_repeated_after_render=True,source_hash_scope='All small sources freshly hashed before and after; canonical renderer path explicitly substituted with exact proposed renderer bytes for preview only. Model source hashes use retained root attestations with before/after stat guards; no model payload read/hash.',canonical_renderer_substitution=dict(path=str(canonical),actual_before_sha256=prepared['before']['render_learning_progress.py']['sha256'],proposed_path=str(renderer_path),proposed_sha256=original_digest(renderer_path)),source_hash_calls=len(source_checks),private_checkpoint_payload_requests=checkpoint_validation_requests,input_json_sha256=original_digest(data_path),png_sha256=original_digest(output),no_Torch_import=True,plotting_CPU_only=True)
path=HERE/'render-validation.json'
path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('model_source_attestations','private_checkpoint_payload_requests')},indent=2))
