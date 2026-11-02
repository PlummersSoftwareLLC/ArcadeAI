"""Root-only fresh read-only health after the retained recovery parent exits."""
import copy,importlib.util,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
def main():
    source=R/'accepted-newgame-failed-maintenance-forward-recovery-source-preparation-20261017/run_forward_recovery.py'
    spec=importlib.util.spec_from_file_location('recovery_health_primitives',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    H=m.load_helper();adapter=H.load(H.ADAPTER,H.ADAPTER_SHA,'post_recovery_adapter');base=adapter.load_v4()
    output=R/'accepted-newgame-failed-maintenance-forward-recovery-20261017'
    result_pin=base.fingerprint(output/'result.json',base.MAX_JSON);result=base.read_json(result_pin)
    assert result['status']=='READY_CE_FORWARD_RECOVERY' and result['manual_recovery_required'] is False
    assert result['CPU_ledger'] and all(x=='passed' for x in result['CPU_ledger'].values())
    job=base.read_json(result['root_job']);original=base.read_json(job['failed_job']);cfg=original['transition'];owner=result['owner']
    tools=Path(cfg['helper_pins']['live_host']['path']).parent;sys.path.insert(0,str(tools))
    live=base.load_module(cfg['helper_pins']['live_host']['path'],'post_recovery_live_host')
    class CurrentHost(live.LiveHost):
        def runtime_dropin(self):return Path(job['current_dropin']['path'])
    host=CurrentHost(cfg['trainer_unit'],cfg['fleet_unit']);current=host.describe()
    assert int(current['trainer']['MainPID'])==owner['pid'] and current['bindings']['worker']['trainer']['starttime_ticks']==owner['starttime_ticks']
    observed=subprocess.run(['systemctl','--user','show',cfg['trainer_unit']],capture_output=True,text=True,check=True,timeout=10)
    unit=dict(x.split('=',1) for x in observed.stdout.splitlines() if '=' in x)
    assert unit['InvocationID']==owner['invocation_id'] and unit['NRestarts']=='0' and unit['SubState']=='running'
    expected=copy.deepcopy(cfg['before']['bindings']['source_hashes']);expected[str(H.SOCKET)]=H.AFTER_SHA
    environment=adapter.selected_environment(cfg['before']['environment'],'ce',result['phase_record'])
    base.binding_matches(current,cfg['before'],expected,environment)
    for actor in current['bindings']['actors']:
        assert sorted(os.sched_getaffinity(actor['pid']))==cfg['actor_masks'][str(actor['pid'])] and not host.actor_stopped(actor)
    assert host.metric_host.mask(current['bindings']['worker'])==cfg['worker_mask']
    handover=base.read_json(result['reconnect']['handover'])
    host.metric_host.log_offsets=copy.deepcopy(handover['offsets'])
    row=host.capture();strict=base.read_json(result['reconnect']['strict_runtime']);previous=strict['observations'][-1]['row']
    plan=dict(batch_size=4096,replay_cap=8,initial_snapshot=dict(csv=cfg['baseline_csv']),exposure_identity={k:live.metrics.exposure_key(previous['exposure'][k]) for k in ('optimizer','replay')})
    issues=live.metrics.api_issues(row,plan);assert not issues,issues
    assert all(row[k]>=previous[k] for k in adapter.CLOCKS)
    assert row['learner_frame_count']>result['boot_checkpoint']['clocks']['learner_frame_count']
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as stream:raw=stream.read((2<<20)+1)
    assert len(raw)<=2<<20;api=json.loads(raw)
    assert api['client_count']==192 and api['host_pipeline']['learning_exposure']['optimizer']['process_id']==owner['pid']
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader'],capture_output=True,text=True,check=True,timeout=15)
    entries=[x.strip().split(', ') for x in gpu.stdout.splitlines() if x.strip()]
    assert len(entries)==1 and entries[0][0]=='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1' and int(entries[0][1])==owner['pid'],entries
    destination=R/'accepted-newgame-forward-recovery-postrelease-health-root-20261017';destination.mkdir(mode=0o700)
    for name,data in [('actual-main-API.raw.json',raw),('actual-main-unit-show.txt',observed.stdout.encode()),('actual-GPU-compute-apps.txt',gpu.stdout.encode())]:
        with (destination/name).open('xb') as f:f.write(data);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    description=base.publish(destination/'actual-runtime-description.json',current)
    report=base.publish(destination/'root-fresh-postrelease-health.json',dict(status='PASS',observed_unix_s=time.time(),owner=owner,recovery_result=result_pin,description=description,row=row,issues=issues,all_original192_resumed=True,source61_control2_unit3_recipe_held=True,log_handover_to_current_strict_clean=True,actual_GPU_compute_apps=base.fingerprint(destination/'actual-GPU-compute-apps.txt',base.MAX_SOURCE),actual_raw_API=base.fingerprint(destination/'actual-main-API.raw.json',base.MAX_JSON),actual_unit_show=base.fingerprint(destination/'actual-main-unit-show.txt',base.MAX_SOURCE),qualification_pass=False))
    print(json.dumps(report))
if __name__=='__main__':main()
