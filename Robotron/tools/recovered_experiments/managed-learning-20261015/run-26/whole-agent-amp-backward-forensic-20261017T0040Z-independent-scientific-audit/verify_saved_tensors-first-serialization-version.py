"""Verify retained artifacts on CPU only; never import the diagnostic/model."""
import collections
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sys

assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
import numpy as np
import torch
torch.set_num_threads(2)
torch.set_num_interop_threads(2)
assert not torch.cuda.is_initialized()
ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parent.parent
DATA = RUN / 'whole-agent-amp-backward-forensic-20261017T0040Z'
OUT = Path(__file__).resolve().parent
sha = lambda value: hashlib.sha256(value).hexdigest()
load_json = lambda path: json.loads(path.read_text())


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def native(value):
    assert value.device.type == 'cpu'
    return value.detach().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()


def structure(value):
    result = hashlib.sha256()
    def visit(item):
        if isinstance(item, torch.Tensor):
            result.update(json.dumps([str(item.dtype), list(item.shape)]).encode())
            result.update(native(item))
        elif isinstance(item, np.ndarray):
            result.update(json.dumps([str(item.dtype), list(item.shape)]).encode())
            result.update(item.tobytes())
        elif isinstance(item, dict):
            for key in sorted(item, key=lambda key: (type(key).__name__, str(key))):
                result.update(repr(key).encode())
                visit(item[key])
        elif isinstance(item, (tuple, list)):
            result.update(type(item).__name__.encode())
            for value in item:
                visit(value)
        else:
            result.update(repr(item).encode())
    visit(value)
    return result.hexdigest()


def equal(actual, saved, path=''):
    if isinstance(actual, dict):
        assert actual.keys() == saved.keys(), path
        for key in actual:
            equal(actual[key], saved[key], path + '/' + str(key))
    elif isinstance(actual, (tuple, list)):
        assert len(actual) == len(saved), path
        for index, value in enumerate(actual):
            equal(value, saved[index], path + '/' + str(index))
    elif isinstance(actual, float):
        if not math.isfinite(actual):
            assert str(actual) == saved, (path, actual, saved)
        else:
            assert actual == saved, (path, actual, saved)
    else:
        assert actual == saved, (path, actual, saved)


def stats(value):
    finite = torch.isfinite(value)
    good = value[finite].double()
    return dict(dtype=str(value.dtype), shape=list(value.shape), numel=value.numel(),
        sha256=sha(native(value)), all_finite=bool(finite.all()),
        nan=int(torch.isnan(value).sum()), positive_inf=int(torch.isposinf(value).sum()),
        negative_inf=int(torch.isneginf(value).sum()),
        finite_max_abs=float(good.abs().max()) if good.numel() else None,
        finite_l2=float(torch.linalg.vector_norm(good)) if good.numel() else 0.,
        full_l2=float(torch.linalg.vector_norm(value.double().reshape(-1))))


def verify_artifact(path, saved):
    assert path.name == saved['path'] and path.stat().st_size == saved['bytes']
    assert file_sha(path) == saved['sha256']
    payload = torch.load(path, map_location='cpu', weights_only=True)
    assert structure(payload) == saved['content_sha256']
    tensors = {}
    def visit(value, name=''):
        if isinstance(value, torch.Tensor):
            assert value.device.type == 'cpu'
            tensors[name] = dict(dtype=str(value.dtype), shape=list(value.shape),
                numel=value.numel(), sha256=sha(native(value)))
        elif isinstance(value, dict):
            for key, item in value.items():
                visit(item, name + '/' + str(key))
        elif isinstance(value, (tuple, list)):
            for index, item in enumerate(value):
                visit(item, name + '/' + str(index))
    visit(payload)
    assert tensors == saved['tensors']
    return payload


manifest = load_json(DATA/'launch-manifest.json')
results = load_json(DATA/'result.json')
assert results == load_json(DATA/'capture/phase-result.json')
assert results['status'] == 'OBSERVATIONS_COMPLETE'
names = ['fp16_amp_default', 'fp16_amp_scale1', 'fp32_unscaled']
assert [row['case'] for row in results['cases']] == names
assert manifest['seed'] == 20261016 and manifest['cases'] == [[names[0], 65536.], [names[1], 1.], [names[2], None]]
assert manifest['worker_sha256'] == '1f922bd4e49dc50b7c3cefc3bb2478d09b0628ee5430a0f18b3bcdd03c903dad'
files = [p for p in DATA.rglob('*') if p.is_file() and '/cache/' not in str(p) and '/private/' not in str(p)]
file_hashes = {str(p.relative_to(DATA)): dict(sha256=file_sha(p), bytes=p.stat().st_size) for p in files}
inputs = DATA/'capture/inputs'
batch_meta = load_json(inputs/'batch.json')
arrays = {}
for name, meta in batch_meta['arrays'].items():
    path = inputs/(name+'.npy')
    value = np.load(path, allow_pickle=False)
    assert not value.dtype.hasobject and str(value.dtype) == meta['dtype'] and list(value.shape) == meta['shape']
    assert file_sha(path) == meta['sha256'] and sha(value.tobytes()) == meta['raw_sha256']
    assert np.isfinite(value).all()
    arrays[name] = value
assert set(arrays) == set(('states','actions','rewards','next_states','dones','horizons','is_expert','actor_kind','indices','weights'))
assert arrays['states'].shape == arrays['next_states'].shape == (8,11128)
assert ((arrays['actions'] >= 0) & (arrays['actions'] < 81)).all()
assert ((arrays['horizons'] >= 1) & (arrays['horizons'] <= 3)).all()
configuration = load_json(inputs/'configuration.json')
presence = load_json(inputs/'presence.json')
cfg = configuration['config']
for field in ('states','next_states'):
    start = cfg['global_features']; end = start + cfg['object_token_count']*cfg['object_token_features']
    tokens = arrays[field][:,:cfg['single_frame_state_size']][:,start:end].reshape(8,cfg['object_token_count'],cfg['object_token_features'])
    mask = tokens[...,0] > .5
    assert np.array_equal(mask, np.load(inputs/(field+'-present.npy'),allow_pickle=False))
    assert presence[field] == dict(present_per_row=mask.sum(axis=1).tolist(),padding_per_row=(~mask).sum(axis=1).tolist(),fully_empty_rows=int((~mask.any(axis=1)).sum()))
fresh = verify_artifact(inputs/'fresh-state.pt', load_json(inputs/'fresh-state-manifest.json'))
baseline = load_json(inputs/'baseline-certificate.json')
assert {name:structure(value) for name,value in fresh['networks'].items()} == baseline['certificate']['networks']
assert structure(fresh['optimizer']) == baseline['certificate']['optimizer']
assert fresh['optimizer']['state'] == {} and fresh['scaler']['scale'] == 65536.
assert all(bool(torch.isfinite(value).all()) for network in fresh['networks'].values() for value in network.values())
rng = load_json(inputs/'rng.json')
def tuples(value):
    return tuple(tuples(item) for item in value) if isinstance(value,list) else value
rng_tensors = torch.load(inputs/'torch-rng.pt',map_location='cpu',weights_only=True)
keys = np.load(inputs/'numpy-rng.npy',allow_pickle=False)
rng_fingerprint = structure(dict(python=tuples(rng['python']),numpy=(rng['numpy_name'],keys,rng['numpy_position'],rng['numpy_has_gauss'],rng['numpy_cached_gauss']),cpu=rng_tensors['cpu'],cuda=rng_tensors['cuda']))
assert rng_fingerprint == baseline['rng_sha256']
case_summaries = []; stored = {}; actual_outputs = {}
for case in results['cases']:
    directory = DATA/'capture'/case['case']; name = case['case']
    assert case == load_json(directory/'result.json')
    assert case['status'] == 'OBSERVED' and case['no_step_certificate'] and case['backward_completed_before_boundary']
    assert case['before'] == case['after'] == baseline['certificate']
    assert case['pre_forward_rng_sha256'] == case['post_backward_rng_sha256'] == rng_fingerprint
    assert case['calls'] == dict(optimizer_step=0,scaler_step=0,scaler_update=0,unscale=int(case['amp']),boundary=1)
    if case['amp']:
        assert case['scaler_before'] == case['scaler_after']
        assert case['scaler_before']['scale'] == case['initial_scale']
    gradients_by_stage = {}
    for stage in (('scaled','unscaled') if case['amp'] else ('unscaled',)):
        report = load_json(directory/(stage+'-gradients.json'))
        values = verify_artifact(directory/(stage+'-gradients.pt'),report['artifact'])
        assert len(values) == 99
        bad = {}; totals = dict(nan=0,positive_inf=0,negative_inf=0); present = 0; maximum = 0.
        for parameter,value in values.items():
            expected = report['parameters'][parameter]
            if value is None:
                assert expected is None
                continue
            present += 1
            computed = stats(value);equal(computed,expected, name+'/'+stage+'/'+parameter)
            maximum = max(maximum,computed['finite_max_abs'] or 0.)
            for key in totals:totals[key] += computed[key]
            if not computed['all_finite']:bad[parameter] = computed
        gradients_by_stage[stage] = dict(present=present,missing=len(values)-present,nonfinite_parameters=bad,nonfinite_counts=totals,finite_max_abs=maximum,all_parameter_stats_exact=True)
        stored[(name,stage)] = values
    if case['amp']:
        for parameter,s in stored[(name,'scaled')].items():
            u = stored[(name,'unscaled')][parameter]
            if s is None:assert u is None;continue
            assert torch.equal(torch.isnan(s),torch.isnan(u)) and torch.equal(torch.isposinf(s),torch.isposinf(u)) and torch.equal(torch.isneginf(s),torch.isneginf(u))
            valid = torch.isfinite(s);assert torch.equal(s[valid]/case['initial_scale'],u[valid])
    boundary = load_json(directory/'boundary.json');assert boundary == case['boundary']
    actual = verify_artifact(directory/'actual-loss-and-inputs.pt',boundary['actual']);actual_outputs[name]=actual
    for field,value in actual.items():equal(stats(value),boundary['tensors'][field], name+'/boundary/'+field)
    assert float(actual['weighted_loss']) == boundary['loss'] and torch.isfinite(actual['weighted_loss'])
    for field in ('states','next_states','rewards','dones','horizons','is_expert','weights'):
        saved = torch.from_numpy(arrays[field]).to(actual[field+'_t'].dtype)
        assert torch.equal(saved,actual[field+'_t'])
    forward=load_json(directory/'forward.json')
    mask_artifacts=0
    for row in forward:
        if 'masks' in row:verify_artifact(directory/row['masks']['path'],row['masks']);mask_artifacts+=1
    if case['amp']:
        assert boundary['outcome_mode']=='single_cuda_found_inf'
        assert float(actual['outcome_tensor']) == (1. if name=='fp16_amp_default' else 0.)
    else:assert boundary['outcome_mode']=='unscaled'
    case_summaries.append(dict(case=name,loss=boundary['loss'],stages=gradients_by_stage,mask_artifacts_verified=mask_artifacts,before_after_certificate_equal=True,forbidden_calls=0,pre_post_rng_sha256=rng_fingerprint))
default,scale1,fp32=(actual_outputs[name] for name in names)
assert default.keys()==scale1.keys()
for key in default:
    if key!='outcome_tensor':assert torch.equal(default[key],scale1[key]),key
assert case_summaries[0]['stages']['unscaled']['nonfinite_counts']==dict(nan=3937,positive_inf=99,negative_inf=117)
assert len(case_summaries[0]['stages']['unscaled']['nonfinite_parameters'])==4
assert all(not case_summaries[i]['stages']['unscaled']['nonfinite_parameters'] for i in (1,2))
dot=norm1=norm2=error2=0.
for parameter,a in stored[(names[1],'unscaled')].items():
    b=stored[(names[2],'unscaled')][parameter]
    if a is None:assert b is None;continue
    a=a.double().reshape(-1);b=b.double().reshape(-1)
    dot+=float(torch.dot(a,b));norm1+=float(torch.dot(a,a));norm2+=float(torch.dot(b,b));error2+=float(torch.dot(a-b,a-b))
comparison=dict(gradient_cosine=dot/math.sqrt(norm1*norm2),relative_gradient_L2_error_vs_FP32=math.sqrt(error2/norm2),AMP_scale1_full_L2=math.sqrt(norm1),FP32_full_L2=math.sqrt(norm2),scope='Stored finite gradient tensors only; no extra forward/backward or strict IEEE FP32 claim')
assert not torch.cuda.is_initialized()
assert all(file_sha(DATA/name)==value['sha256'] for name,value in file_hashes.items())
report=dict(schema='robotron-forensic-independent-cpu-artifact-verification-v1',verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),data_directory=str(DATA),result='PASS_SAVED_ARTIFACTS_CONSISTENT',torch_version=str(torch.__version__),torch_threads=torch.get_num_threads(),interop_threads=torch.get_num_interop_threads(),CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],cuda_initialized=False,source_worker_sha256=manifest['worker_sha256'],seed=manifest['seed'],files=file_hashes,batch_arrays_verified=10,model_manifest_per_tensor_hashes_verified=True,baseline_model_network_sha256=baseline['certificate']['networks'],baseline_optimizer_sha256=baseline['certificate']['optimizer'],baseline_optimizer_empty=True,saved_RNG_fingerprint=rng_fingerprint,presence=presence,cases=case_summaries,AMP_forward_inputs_outputs_except_found_inf_bitwise_identical=True,finite_control_comparison=comparison,scope_limits=['No independent after-state model/optimizer/replay tensor archives exist. No-step proof combines equal recorded before/after certificates, persisted initial fingerprints and frozen boundary/step-guard source. The deleted private replay cannot be independently rehashed here.','No CUDA context, model construction, forward/backward, optimizer step, sampling or diagnostic rerun. All tensors loaded weights_only on CPU.','Fresh seed20261016 and its saved8-row batch only; cannot reconstruct old reviewed2 weights/batches or prove its exact cause.','FP32 control retains recorded TF32/backend settings. Numerical CUDA operations need not be deterministic despite identical saved RNG.','This backward-only observation is neither snapshot capture/restore nor a learning-quality or production AMP recommendation.'])
path=OUT/'cpu-verification.json'
with path.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
path.chmod(0o444)
print(json.dumps(dict(path=str(path),sha256=file_sha(path),cases=[dict(case=row['case'],loss=row['loss'],present=row['stages']['unscaled']['present'],missing=row['stages']['unscaled']['missing'],nonfinite_parameters=list(row['stages']['unscaled']['nonfinite_parameters']),counts=row['stages']['unscaled']['nonfinite_counts'],finite_max_abs=row['stages']['unscaled']['finite_max_abs']) for row in case_summaries],comparison=comparison,CUDA_initialized=False),indent=2))
