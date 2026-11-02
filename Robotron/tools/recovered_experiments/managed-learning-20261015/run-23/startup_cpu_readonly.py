"""Independent CPU-only read of root's exact run23 resume anchor; no mutations."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os,resource,time
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
started=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
r=Path(__file__).resolve().parent;game=r.parents[2]
root=json.loads((r/'final-resume-checkpoint.json').read_text())
anchor=game/root['checkpoint'];latest=game/root['source']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
assert sha(anchor)==root['sha256']
latest_sha=sha(latest)
assert latest_sha==root['sha256']
before=anchor.stat()
import numpy as np
import torch
torch.set_num_threads(2);torch.set_num_interop_threads(1)
assert not torch.cuda.is_initialized()
c=torch.load(anchor,map_location='cpu',weights_only=True)
finite_tensor_count=0
def finite_tree(value):
 global finite_tensor_count
 if torch.is_tensor(value):
  assert value.device.type=='cpu' and bool(torch.isfinite(value).all())
  finite_tensor_count+=1
 elif isinstance(value,dict):
  for item in value.values():finite_tree(item)
 elif isinstance(value,(list,tuple)):
  for item in value:finite_tree(item)
finite_tree(c)
meta={k:c[k] for k in root['saved_metadata']}
assert meta==root['saved_metadata']
prior_path=game/'logs/managed-learning-20261015/run-19/fresh3-96M-checkpoint-lineage.json'
assert sha(prior_path)=='aa701312ed0b4165b83e84e49b3add3e441d919d0e7b50b346bb33d38f06b4fa'
prior=json.loads(prior_path.read_text())['candidate']
checks={}
for name,expected in prior['state_dict_signatures'].items():
 actual={k:dict(shape=list(v.shape),dtype=str(v.dtype)) for k,v in c[name].items()}
 checks[name+'_geometry']=actual==expected
 assert checks[name+'_geometry']
 assert all(v.device.type=='cpu' and bool(torch.isfinite(v).all()) for v in c[name].values())
o=c['optimizer_state_dict'];assert len(o['state'])==root['optimizer_state_count']==81
steps=sorted({float(v['step'].item()) for v in o['state'].values()});assert steps==root['optimizer_parameter_steps']
assert all(v.device.type=='cpu' and bool(torch.isfinite(v).all()) for row in o['state'].values() for v in row.values() if torch.is_tensor(v))
groups=[]
for group in o['param_groups']:
 g={k:v for k,v in group.items() if k!='params'};g['parameter_count']=len(group['params']);groups.append(g)
assert groups[0]['lr']==2.5e-5 and groups[0]['eps']==.00015 and groups[0]['fused'] is True and groups[0]['foreach'] is False and groups[0]['parameter_count']==99
assert c['epsilon']==.1 and abs(c['expert_ratio']-.1)<1e-12 and c['lr_gear']=='climb' and c['lr_anchor_step']==0
banks={}
for bank,expected in root['banks'].items():
 directory=game/f'models_dqn/robotron_dqn_latest_replay_{bank}'
 selector_path=directory/'CURRENT.json';raw=selector_path.read_bytes();selector=json.loads(raw)
 assert hashlib.sha256(raw).hexdigest()==expected['selector_sha256'] and selector==expected['selector']
 p=Path(expected['metadata_path']);assert sha(p)==expected['metadata_sha256']
 with np.load(p,allow_pickle=False) as a:
  stride=int(a['stride'].item());lengths=a['ep_len']
  assert stride=={'hof':1536,'ephof':2048}[bank] and lengths.shape==(192,)
  assert np.all(lengths>=0) and np.all(lengths<=stride)
  episodes=int(np.count_nonzero(lengths));transitions=int(lengths.sum())
  assert episodes==expected['episodes'] and transitions==expected['transitions']
  assert int(a['state_size'].item())==11128 and int(a['mutation_generation'].item())==selector['mutation_generation']
 assert selector_path.read_bytes()==raw
 banks[bank]=dict(selector=selector,selector_sha256=expected['selector_sha256'],metadata_sha256=expected['metadata_sha256'],episodes=episodes,transitions=transitions,match=True)
p=Path(root['replay_metadata']['path']);assert sha(p)==root['replay_metadata']['sha256']
ring=np.load(p,allow_pickle=False);assert ring.tolist()==root['replay_metadata']['values']
assert ring[1]==6000000 and ring[0]==root['replay_metadata']['values'][0]
assert sha(anchor)==root['sha256'] and anchor.stat().st_size==before.st_size and anchor.stat().st_mtime_ns==before.st_mtime_ns
initial=json.loads((r.parent/'run-22/final-resume-checkpoint.json').read_text())
initial_steps=initial['optimizer_parameter_steps'];assert len(initial_steps)==len(steps)==1
clock_delta=dict(logical_updates=meta['training_steps']-initial['saved_metadata']['training_steps'],optimized_samples=meta['optimized_samples']-initial['saved_metadata']['optimized_samples'],learner_frames=meta['learner_frame_count']-initial['saved_metadata']['learner_frame_count'],fleet_frames=meta['frame_count']-initial['saved_metadata']['frame_count'],Adam_parameter_steps=steps[0]-initial_steps[0])
clock_delta['logical_minus_Adam_delta']=clock_delta['logical_updates']-clock_delta['Adam_parameter_steps']
assert clock_delta['optimized_samples']==clock_delta['logical_updates']*4096
assert all(value>=0 for value in clock_delta.values())
assert not torch.cuda.is_initialized()
report=dict(schema='robotron-run23-independent-resume-cpu-v1',PASS=True,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_s=time.monotonic()-tick,pid=os.getpid(),CUDA_VISIBLE_DEVICES='',CUDA_initialized=False,torch_threads=torch.get_num_threads(),torch_interop_threads=torch.get_num_interop_threads(),max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,anchor=str(anchor),anchor_sha256=root['sha256'],latest_sha256=latest_sha,metadata=meta,optimizer_state_count=81,optimizer_parameter_steps=steps,optimizer_groups=groups,all_saved_tensors_finite_CPU=True,finite_tensor_count=finite_tensor_count,default_return_saved_clock_delta=clock_delta,clock_delta_interpretation='Actual saved logical and per-parameter Adam clocks, not per-event overflow proof or evidence of a compiler cause.',geometry=checks,banks=banks,ring_metadata=ring.tolist(),scope='Actual checkpoint CPU load and bounded bank/ring metadata only; no model/replay/control/process/source writes.')
with (r/'startup-independent-checkpoint-cpu.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({k:report[k] for k in ['PASS','started_utc','finished_utc','elapsed_s','pid','anchor_sha256','metadata','optimizer_parameter_steps','CUDA_initialized']}))
