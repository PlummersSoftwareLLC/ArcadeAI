"""Read-only 120s API/proc/CSV observations; no torch, signals or benchmarks."""
import copy,csv,hashlib,json,os,subprocess,time,urllib.request
from pathlib import Path
from Robotron.tools import inference_worker_affinity as metric

OUT=Path(__file__).resolve().parent
UNIT='robotron-managed-run-26-d3b365c9-trainer.service'
FLEET='robotron-managed-run-26-d3b365c9-fleet.service'

def unit():
    keys=('MainPID','ControlGroup','ActiveState','KillSignal','TimeoutStopUSec','SendSIGKILL','Restart')
    raw=subprocess.run(['systemctl','--user','show',UNIT,*['--property='+key for key in keys]],capture_output=True,text=True,check=True,timeout=5).stdout
    return dict(line.split('=',1) for line in raw.splitlines())

def dump(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def csv_row(path):
    with path.open('rb') as stream:
        header=stream.readline().decode();stream.seek(0,2);length=stream.tell()
        stream.seek(max(0,length-256*1024));lines=stream.read().decode().splitlines(keepends=True)
    complete=[line for line in lines if line.endswith('\n')]
    return list(csv.DictReader([header,complete[-1]]))[-1]

def threads(pid):
    out={}
    for entry in (Path('/proc')/str(pid)/'task').iterdir():
        try:
            name=(entry/'comm').read_text().strip()
            if name not in ('robotron-replay','TrainWorker','InferBatchWorke'):continue
            stat=metric.identity.stat_fields((entry/'stat').read_text())
            fields=(entry/'schedstat').read_text().split()
            out[name]=dict(tid=int(entry.name),starttime_ticks=stat['starttime_ticks'],runtime_ns=int(fields[0]),runqueue_wait_ns=int(fields[1]),slices=int(fields[2]))
        except FileNotFoundError:pass
    return out

start_unit=unit();pid=int(start_unit['MainPID']);host=metric.Host(pid,FLEET)
# The frozen sidecar is intentionally running. Only this instance's read-only
# exclusion check is bypassed; no production source or process is changed.
host.no_sidecars=lambda:None
binding=host.bindings();host.configure_logs(binding['logs'])
dump('initial-bindings.json',dict(unit=start_unit,bindings=binding,threads=threads(pid)))
dump('method.json',dict(read_only=True,target_s=120,poll_s=5,scope='GET /api/now, proc identities/schedstat, bounded CSV tail and incremental runtime logs',
    active_quality_campaign_allowed_for_observation=True,exclusion_check_bypass='local metric.Host instance only; no mutation methods called',
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),metrics_helper_sha256=metric.file_digest(metric.__file__)))
started=time.monotonic();previous=None;plan=None
with (OUT/'observations.jsonl').open('x') as stream:
    while True:
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as response:
            payload=response.read(2*1024*1024+1)
        metric.require(len(payload)<=2*1024*1024,'API snapshot unexpectedly large')
        raw=json.loads(payload);row=metric.compact_api(raw)
        row.update(observed_monotonic_s=time.monotonic(),observed_unix_s=time.time(),log_errors=host.log_errors())
        values=csv_row(host.csv_path)
        row['csv']={key:int(values[key]) for key in ('replay_dropped','batch_size')}
        row['csv']['replay_sample_cap']=float(values['replay_sample_cap'])
        row['csv']['utc']=values['utc']
        if plan is None:plan=dict(exposure_identity={kind:metric.exposure_key(row['exposure'][kind]) for kind in ('optimizer','replay')},initial_snapshot=copy.deepcopy(row),batch_size=4096,replay_cap=8)
        row['issues']=metric.api_issues(row,plan,previous)
        row['host_pipeline']=raw['host_pipeline']
        row['bank_persistence']=raw['bank_persistence']
        row['timing_ema']={key:raw[key] for key in raw if key.startswith('train_')}
        row['pipeline_snapshot_age_s']=raw['pipeline_snapshot_age_s']
        row['threads']=threads(pid)
        row['csv_observation']={key:values.get(key) for key in ('utc','elapsed_s','frames','steps','optimized_samples','prefetched_batches','direct_state_batches','replay_pressure_waits','replay_dropped','sample_wall_ms','stage_host_ms','transfer_host_ms','compute_host_ms','priority_and_readback_ms','train_step_wall_ms','gpu_compute_ms','gpu_util_pct','gpu_power_w','pipeline_counter_reset')}
        stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush()
        previous=row
        if row['observed_monotonic_s']-started>=120:break
        time.sleep(min(5,max(0,started+120-time.monotonic())))
finish=host.bindings();end_unit=unit()
dump('final-bindings.json',dict(unit=end_unit,bindings=finish,threads=threads(pid),same_bindings=finish==binding,same_unit=end_unit==start_unit))
print(json.dumps(dict(rows=sum(1 for _ in (OUT/'observations.jsonl').open()),elapsed_s=previous['observed_monotonic_s']-started,same_bindings=finish==binding,output=str(OUT)),indent=2))
