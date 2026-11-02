#!/usr/bin/env python3
"""Read-only normal recovery checks and create-only evidence."""
import importlib.util,json,os,re,subprocess,sys,urllib.request,hashlib,time
from pathlib import Path
REPO=Path('/home/dave/source/repos/ArcadeAI');GAME=REPO/'Robotron';RUN=GAME/'logs/managed-learning-20261015/run-26';D=RUN/'live8-owned-manual-forward-recovery-reviewed1-20261017'
def main():
    sys.dont_write_bytecode=True;sys.path.insert(0,str(GAME/'tools'))
    import parallel_state_fill_trial as primitives
    metrics=primitives.metrics
    j=json.loads((RUN/'live8-owned-maintenance-root-preparation-reviewed3-20261017/root-job.json').read_text());owner=json.loads((D/'root-owned-normal-new-trainer.json').read_text());request=json.loads((D/'root-owned-normal-start-request.json').read_text())
    class Host(primitives.LiveHost):
        def runtime_dropin(self):return Path(j['original_dropin']['path'])
    host=Host(j['trainer_unit'],j['fleet_unit']);current=host.describe();assert int(current['trainer']['MainPID'])==owner['pid'];assert current['bindings']['worker']['trainer']['starttime_ticks']==owner['starttime_ticks'];host.adopt_initial(current)
    invocation=subprocess.run(['systemctl','--user','show',j['trainer_unit'],'--value','-p','InvocationID'],capture_output=True,text=True,check=True,timeout=5).stdout.strip();assert invocation==owner['invocation_id']
    for key in ['actors','fleet_cgroup','source_hashes','control_hashes','logs']:assert current['bindings'][key]==j['before']['bindings'][key],key
    assert current['environment']==j['before']['environment'];assert current['unit_files']==j['before']['unit_files'];assert current['fleet']==j['before']['fleet'];assert current['supervisor_start_ticks']==j['before']['supervisor_start_ticks']
    assert all(sorted(os.sched_getaffinity(actor['pid']))==j['actor_masks'][str(actor['pid'])] for actor in current['bindings']['actors'])
    assert host.metric_host.mask(current['bindings']['worker'])==j['worker_mask'];assert all(not host.actor_stopped(actor) for actor in current['bindings']['actors'])
    host.metric_host.configure_logs(current['bindings']['logs']);first=host.capture();plan=dict(batch_size=4096,replay_cap=8,initial_snapshot=first,exposure_identity={kind:metrics.exposure_key(first['exposure'][kind]) for kind in ['optimizer','replay']})
    assert not metrics.api_issues(first,plan),metrics.api_issues(first,plan)
    assert all(first[key]>=request['verified_saved_clocks'][key] for key in ('training_steps','optimized_samples','learner_frame_count','frame_count'))
    path=current['trainer_stdout']['path'];saved=request['log_boundary'][path]
    with Path(path).open('rb') as f:
        info=os.fstat(f.fileno());assert(info.st_dev,info.st_ino)==(saved['device'],saved['inode']);f.seek(saved['offset']);boot=f.read(4<<20);assert f.tell()==info.st_size
    text=boot.decode(errors='replace');latest=request['latest']['path'];assert re.findall(r'^Loaded v28 model from (.+)$',text,re.M)==[latest];assert re.findall(r'^Loaded model from: (.+)$',text,re.M)==[latest]
    matches=re.findall(r'^\s*(HOF|EPHOF) loaded: ([0-9][0-9,]*) episodes / ([0-9][0-9,]*) transitions\s*$',text,re.M)
    counts={name.lower():dict(episodes=int(ep.replace(',','')),transitions=int(tr.replace(',',''))) for name,ep,tr in matches};assert len(matches)==2 and counts==request['banks_counts'],counts
    assert not any(marker in text for marker in ['Optimizer state skipped:','GradScaler state skipped:','Optimizer state absent/stale','Incompatible checkpoint engine version','Replay buffer skipped','No replay buffer found','Replay buffer load failed:','[WARN] HOF load failed:','[WARN] EpHOF load failed:','ExactInferenceGraphError','Model load failed/incompatible','No model found, starting fresh'])
    assert hashlib.sha256(Path(latest).read_bytes()).hexdigest()==request['latest']['sha256']
    snapshot=json.loads((D/'stopped-disk-state.json').read_text());expected={value['path']:(name,value) for name,value in snapshot['ring']['arrays'].items() if name!='priorities'};maps=Path('/proc',str(owner['pid']),'maps').read_text();seen={name:0 for name,_ in expected.values()}
    for line in maps.splitlines():
        fields=line.split(None,5)
        if len(fields)!=6 or fields[5] not in expected:continue
        name,descriptor=expected[fields[5]];major,minor=(int(v,16) for v in fields[3].split(':'));identity=descriptor['identity'];assert (major,minor,int(fields[4]))==(os.major(identity['device']),os.minor(identity['device']),identity['inode'])
        if fields[1]=='rw-s':seen[name]+=1
    assert len(seen)==9 and all(seen.values())
    # Payload timestamps may advance after192 reconnect; compare mapped inode,
    # not a stale full-file identity or bank RAM content.
    time.sleep(3);second=host.capture();assert not metrics.api_issues(second,plan,first),metrics.api_issues(second,plan,first)
    assert second['optimized_samples']>first['optimized_samples'] and second['learner_frame_count']>first['learner_frame_count']
    report=dict(status='PASS',owner=owner,current_binding=current,first=first,second=second,banks_counts=counts,mapped_ring_count_by_field=seen,boot_log_start=saved['offset'],boot_log_end=saved['offset']+len(boot),boot_log_sha256=hashlib.sha256(boot).hexdigest(),latest_SHA_preserved=True,source_phase='before',observer_installed=False,actual_live8_rows=0,graph_capture_count=second['graphs']['capture_count'],graph_validation_replay_count=second['graphs']['validation_replay_count'],protected_incumbent_unchanged=True,load_proof_scope='CPU-verified newest latest+owned successful loader/graph/optimizer/scaler source guards and current>=saved; no direct loaded-four-clock observer proof or coherent restart claim')
    p=D/'root-normal-recovery-health-PASS.json'
    with p.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444)
    print(json.dumps(dict(status='PASS',pid=owner['pid'],client_count=second['client_count'],learner_frame_count=second['learner_frame_count'],optimized_samples=second['optimized_samples'],graph_count=second['graphs']['capture_count'],bank_counts=counts)))
if __name__=='__main__':main()
