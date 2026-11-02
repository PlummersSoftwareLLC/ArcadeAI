#!/usr/bin/env python3
"""Read-only current health and unchanged policy/source evidence after live8."""
import datetime, hashlib, json, math, os, stat, subprocess, time, urllib.request
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');G=R/'Robotron';RUN=G/'logs/managed-learning-20261015/run-26'
C=RUN/'live8-owned-maintenance-reviewed4-20261017';D=RUN/'live8-success-current-health-root-20261017'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(4<<20),b''):h.update(chunk)
    return h.hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def ps(pid):return Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
def show(u):
    c=subprocess.run(['systemctl','--user','show',u],capture_output=True,text=True,timeout=8);assert c.returncode==0
    return c.stdout,dict(x.split('=',1) for x in c.stdout.splitlines() if '=' in x)
def api():
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as f:return json.load(f)
def main():
    D.mkdir();j=json.loads((C/'root-job.json').read_text());ev=json.loads((C/'event-05.json').read_text())['proof'];binding=ev['binding'];owner=binding['bindings']['worker']['trainer'];pid=owner['pid'];assert int(ps(pid)[19])==owner['starttime_ticks']
    raw,unit=show(j['trainer_unit']);assert int(unit['MainPID'])==pid and unit['InvocationID']=='cf4f26d3c5b84d9ab1302ded3a073519' and unit['ActiveState']=='active'
    (D/'current-main-unit-show.txt').write_text(raw)
    fraw,fleet=show(j['fleet_unit']);assert fleet['MainPID']==j['before']['fleet']['MainPID'] and fleet['InvocationID']=='5ade9b2810524877921946df11ea597e'
    (D/'current-fleet-unit-show.txt').write_text(fraw)
    actors=[]
    for a in binding['bindings']['actors']:
        fields=ps(a['pid']);assert int(fields[19])==a['starttime_ticks'] and fields[0] in ('S','R')
        mask=sorted(os.sched_getaffinity(a['pid']));assert mask==j['actor_masks'][str(a['pid'])] and int(ps(a['pid'])[19])==a['starttime_ticks']
        actors.append(dict(pid=a['pid'],starttime_ticks=a['starttime_ticks'],slot=a['client_slot'],state=fields[0],mask=mask))
    assert sorted(a['slot'] for a in actors)==list(range(192))
    worker=binding['bindings']['worker']['thread'];tid=worker['tid'];t=Path('/proc',str(pid),'task',str(tid),'stat');assert int(t.read_text().rsplit(')',1)[1].split()[19])==worker['starttime_ticks'];assert sorted(os.sched_getaffinity(tid))==j['worker_mask']
    expected=dict(j['before']['bindings']['source_hashes'])
    for s in j['sources']:expected[s['destination']]=s['after']['sha256']
    for p,h in expected.items():assert sha(Path(p))==h,p
    for p,h in j['before']['bindings']['control_hashes'].items():assert sha(Path(p))==h,p
    assert expected[str(G/'Scripts/dqn/loss_kernel.py')]=='de9621e3d926a8f49f230f9e271c645a7498d38445622d6ae2761ab2bbd7253a'
    drop=Path('/run/user/1001/systemd/user')/(j['trainer_unit']+'.d')/'90-recomputed-ce-live8.conf';assert not drop.exists()
    maps=Path('/proc',str(pid),'maps').read_text();mp=D/'current-main-proc-maps.txt'
    with mp.open('x') as f:f.write(maps);os.fchmod(f.fileno(),0o444)
    arrays=json.loads((C/'event-03.json').read_text())['state']['ring']['arrays'];proof={}
    for name,desc in arrays.items():
        if name=='priorities':continue
        rows=[x.split(None,5) for x in maps.splitlines() if x.endswith(' '+desc['path'])];assert len(rows)==1
        row=rows[0];ident=desc['identity'];dev=int(row[3].split(':')[0],16),int(row[3].split(':')[1],16)
        assert row[1]=='rw-s' and int(row[4])==ident['inode'] and dev==(os.major(ident['device']),os.minor(ident['device']))
        proof[name]=dict(path=desc['path'],inode=int(row[4]),device=row[3],permissions=row[1])
    trace=C/'ce-recomputed-capture-original8'
    def inventory():return {p.name:dict(bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,inode=p.stat().st_ino) for p in trace.iterdir() if p.is_file()}
    before=inventory();assert len(list(trace.glob('attempt-*.payload.pt')))==8 and len(list(trace.glob('attempt-??.json')))==8
    first=api();save(D/'api-before.json',first);time.sleep(3);second=api();save(D/'api-after.json',second)
    for v in (first,second):
        assert v['client_count']==192 and v['training_enabled'] and not v['measurement_active'] and v['managed_experiment']==j['experiment']
        assert all(math.isfinite(v[k]) for k in ('loss','grad_norm','lr')) and v['lr']==2.5e-5
        graph=v['host_pipeline']['inference_graphs'];assert graph['ready'] and graph['capture_count']==128 and graph['validation_replay_count']==640 and graph['runtime_capture_count']==0 and graph['fallback_count']==0 and graph['fatal_error'] is None
        assert v['host_pipeline']['learning_exposure']['optimizer']['process_id']==pid and v['pipeline_read_error'] is None and v['bank_persistence_read_error'] is None
    for k in ('learner_frame_count','frame_count','optimized_samples','training_steps'):assert second[k]>first[k],k
    assert before==inventory() and int(ps(pid)[19])==owner['starttime_ticks']
    model=G/'models_dqn/managed-incumbents/fresh3-384M-confirmed.pt';st=model.stat();digest=sha(model);after=model.stat();assert st==after and digest=='ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963' and stat.S_IMODE(st.st_mode)==0o444 and st.st_nlink==1
    report=dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),owner=dict(owner,invocation_id=unit['InvocationID']),fleet=dict(pid=int(fleet['MainPID']),invocation_id=fleet['InvocationID']),actors=actors,inference_worker=worker,source_hashes=expected,control_hashes=j['before']['bindings']['control_hashes'],ring_maps=proof,raw_maps_sha256=sha(mp),capture_inventory_unchanged=before,capture_dormant_after8_source_and_no_new_artifacts=True,future_capture_dropin_absent=True,protected_incumbent=dict(path=str(model),sha256=digest,bytes=st.st_size,mode='0o444',nlink=1),current_frames={k:second[k] for k in ('learner_frame_count','frame_count','training_steps','optimized_samples')},scope='Fresh read-only identities/masks/maps/source hashes/API advancement plus protected-byte rehash; no coherent replay/RNG/actor anchor, RAM bank equality, sustained throughput or learning improvement claim')
    save(D/'root-current-health-PASS.json',report)
    with (D/Path(__file__).name).open('xb') as f:f.write(Path(__file__).read_bytes());os.fchmod(f.fileno(),0o444)
    print(json.dumps(dict(status='PASS',actors=len(actors),main_pid=pid,learner_frames=second['learner_frame_count'],source_files=len(expected),mapped_ring_fields=len(proof),protected_sha=digest)))
if __name__=='__main__':main()
