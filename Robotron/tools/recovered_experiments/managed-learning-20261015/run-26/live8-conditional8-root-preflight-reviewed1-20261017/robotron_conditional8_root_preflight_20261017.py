#!/usr/bin/env python3
"""Root-only read-only preflight for the immutable conditional8 execution."""
import datetime,fcntl,hashlib,importlib.util,json,math,os,subprocess,sys,time,urllib.request
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');G=R/'Robotron';B=G/'logs/managed-learning-20261015';RUN=B/'run-26'
P=G/'tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/live8_recompute_proposal';D=RUN/'live8-conditional8-root-preflight-reviewed1-20261017'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def start(pid):return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
def show(u):
    out=subprocess.run(['systemctl','--user','show',u],capture_output=True,text=True,timeout=10);assert out.returncode==0
    return dict(x.split('=',1) for x in out.stdout.splitlines() if '=' in x),out.stdout
def main():
    D.mkdir();s=json.loads((B/'state.json').read_text());g=s['next_checkpoint'];assert g['status']=='paused_for_conditional8_owned_window' and not Path('/proc',str(g['pid'])).exists()
    assert not (G/'models_dqn/managed_save.request.json').exists() and not Path(g['output']).exists() and not (G/'models_dqn/managed-checkpoints/fresh3-448M.pt').exists()
    manifest=P/'preparation-manifest-reviewed3.json';assert sha(manifest)=='ed50ea2201ab2af48e5864e65ea7c339a975a33ea68f113e7f3f99779ca608ac'
    for name,item in json.loads(manifest.read_text())['files'].items():assert sha(P/name)==item['sha256'] and (P/name).stat().st_mode&0o222==0,name
    assert sha(P/'cuda_trace_parent.py')=='02af5b4ab846c1fe2579ceeba4ceabff8f05a4686c6debe490df56c1978779ba'
    assert sha(P/'cuda_trace_worker.py')=='182f008a969f55c2aa5952612f1631b3435cab61cbc5ae42fcd708c4f91a03a7'
    test=RUN/'live8-conditional8-guards-root-execution-reviewed3-20261017/root-result-review-and-release.json';v=json.loads(test.read_text());assert v['status']=='PASS' and v['observed_tests']==59 and v['original_exit']==0
    spec=importlib.util.spec_from_file_location('_root_conditional8_parent',P/'cuda_trace_parent.py');parent=importlib.util.module_from_spec(spec);sys.modules[spec.name]=parent;spec.loader.exec_module(parent)
    lock=parent.read_lock();base,_=parent.helpers(lock);proof=base.guard_live_resources(allowed_pids={os.getpid()},initial=True)
    inputs=parent.bind_inputs(lock);assert len(inputs['attempts'])==8
    owner,raw=show('robotron-managed-run-26-d3b365c9-trainer.service');assert owner['MainPID']=='4140916' and owner['InvocationID']=='cf4f26d3c5b84d9ab1302ded3a073519' and start(4140916)==31570251
    (D/'main-unit-show.txt').write_text(raw);fleet,fraw=show('robotron-managed-run-26-d3b365c9-fleet.service');assert fleet['MainPID']=='2258189' and fleet['InvocationID']=='5ade9b2810524877921946df11ea597e';(D/'fleet-unit-show.txt').write_text(fraw)
    health=json.loads((RUN/'live8-success-current-health-root-reviewed2-20261017/root-current-health-PASS.json').read_text())
    masks=[]
    for actor in health['actors']:
        assert start(actor['pid'])==actor['starttime_ticks'];actual=sorted(os.sched_getaffinity(actor['pid']));assert actual==actor['mask'] and start(actor['pid'])==actor['starttime_ticks'];masks.append(dict(pid=actor['pid'],starttime_ticks=actor['starttime_ticks'],mask=actual))
    assert len(masks)==192
    for path,value in health['source_hashes'].items():assert sha(Path(path))==value,path
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as f:api=json.load(f)
    assert api['client_count']==192 and api['training_enabled'] and not api['measurement_active'] and api['learner_frame_count']<452629023 and api['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth'
    assert all(math.isfinite(api[key]) for key in ('loss','grad_norm','lr')) and api['lr']==2.5e-5
    graph=api['host_pipeline']['inference_graphs'];assert graph['ready'] and graph['capture_count']==128 and graph['validation_replay_count']==640 and graph['fallback_count']==0 and graph['runtime_capture_count']==0 and graph['fatal_error'] is None
    assert api['host_pipeline']['learning_exposure']['optimizer']['process_id']==4140916
    with Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock').open('r+') as lease:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lease,fcntl.LOCK_UN)
    model=G/'models_dqn/managed-incumbents/fresh3-384M-confirmed.pt';before=model.stat();digest=sha(model);assert digest=='ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963' and model.stat()==before and before.st_mode&0o222==0 and before.st_nlink==1
    save(D/'raw-current-api.json',api)
    save(D/'root-preflight-PASS.json',dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),bundle_sha256=sha(manifest),actual59guards=v,live_resource_guard=proof,retained_input_metadata=inputs,actor_masks=masks,current_learner_frames=api['learner_frame_count'],protected384_sha256=digest,main_owner=dict(pid=4140916,starttime_ticks=31570251,invocation_id=owner['InvocationID']),paused448=g,limitations='Read-only preflight; actual numerical imports/forward/child resources remain to be proven in the owned delegated service'))
    with (D/Path(__file__).name).open('xb') as f:f.write(Path(__file__).read_bytes());os.fchmod(f.fileno(),0o444)
    print(json.dumps(dict(status='PASS',main_pid=4140916,actors=len(masks),learner_frames=api['learner_frame_count'],payloads=len(inputs['attempts']),protected384_sha256=digest)))
if __name__=='__main__':main()
