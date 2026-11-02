"""Read-only score-blind initial confirmation isolation audit."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, re, subprocess, urllib.request

D=Path(__file__).resolve().parent
G=D.parents[2]
J=D.parent/'sidecar-gpu0-192M-confirm-01'
PID=2034942
GPU0='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
GB='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'
SHIM='13d496b6f268d28c0b732e88635c0e05c7eaa5f7aa622d4e783767b0ace2ff4d'
SLOTS=list(range(4096,4112))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def proc(pid):
    base=Path('/proc')/str(pid);s=(base/'stat').read_text().split(') ',1)[1].split()
    return dict(pid=pid,ppid=int(s[1]),start_ticks=int(s[19]),state=s[0],argv=[x.decode(errors='replace') for x in (base/'cmdline').read_bytes().split(b'\0') if x])
def env(pid):return dict(x.decode().split('=',1) for x in (Path('/proc')/str(pid)/'environ').read_bytes().split(b'\0') if b'=' in x)
def write(name,data):
    p=D/name
    with p.open('x') as f:json.dump(data,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return sha(p)
def forbidden(value):
    low=value.lower()
    return str(G/'models_dqn') in value or ('replay' in low and ('robotron' in low or value.startswith('/dev/shm/')))

status=json.loads((J/'status.json').read_bytes())
meta={key:status.get(key) for key in ('phase','active','complete','valid','reason','error','start_ts','close_ts','boundary','actor_pids')}
assert meta['complete'] is False,'Refuse to label a final job initial'
early=json.loads((D/'quality192M-confirm01-owned-process-tree-early.json').read_bytes())
registry={row['pid']:row for row in early['processes']};todo=[PID];walked=set()
while todo:
    pid=todo.pop()
    if pid in walked:continue
    walked.add(pid)
    try:
        row=proc(pid);children=set()
        for task in (Path('/proc')/str(pid)/'task').iterdir():
            try:children.update(map(int,(task/'children').read_text().split()))
            except OSError:pass
        row['observed_task_children']=sorted(children);registry.setdefault(pid,row);todo.extend(children)
    except OSError:pass
owned=dict(utc=utc(),runner_pid=PID,processes=sorted(registry.values(),key=lambda x:x['pid']),scope='All-task recursive descendant union, including early compiler workers; PID/PPID/starttick metadata only.')
write('quality192M-confirm01-owned-process-tree.json',owned)
fd_bad={};map_bad={};fdlinks={};gone=[]
for row in owned['processes']:
    pid=row['pid'];base=Path('/proc')/str(pid)
    try:
        assert proc(pid)['start_ticks']==row['start_ticks']
        links={}
        for f in (base/'fd').iterdir():
            try:links[f.name]=os.readlink(f)
            except OSError:pass
        fdlinks[pid]=links
        bad={fd:target for fd,target in links.items() if forbidden(target)}
        if bad:fd_bad[str(pid)]=bad
        badmaps=[line for line in (base/'maps').read_text().splitlines() if forbidden(line)]
        if badmaps:map_bad[str(pid)]=badmaps
    except FileNotFoundError:gone.append(pid)
private=proc(PID);private_env=env(PID);actors=[];libraries={}
for slot in SLOTS:
    pid=int(meta['actor_pids'][str(slot)]);row=proc(pid);e=env(pid);args=row['argv'];base=J/'actors'/str(slot);log=base/'console.log'
    blob=log.read_bytes();blob=blob[:blob.rfind(b'\n')+1];text=blob.decode(errors='replace')
    activation=re.findall(r'\[robotron-socket-wait\] pid=(\d+) fd=(\d+) port=(\d+) interval_us=(\d+)',text)
    library=e['LD_PRELOAD'];libraries.setdefault(library,sha(library))
    paths=('-cfg_directory','-nvram_directory','-inipath','-state_directory','-snapshot_directory','-diff_directory','-input_directory','-share_directory','-comment_directory')
    checks=dict(forced_eval_highslot_env=e.get('ROBOTRON_CLIENT_SLOT')==str(slot) and e.get('ROBOTRON_EVAL_MODE')=='1' and e.get('ROBOTRON_PREVIEW_CLIENT')=='0',
        socket9999_wait1000=e.get('ROBOTRON_SOCKET_ADDRESS')=='127.0.0.1:9999' and e.get('ROBOTRON_SOCKET_WAIT_PORT')=='9999' and e.get('ROBOTRON_SOCKET_WAIT_US')=='1000',
        one_actual_shim_activation=len(activation)==1 and activation[0][0]==str(pid) and activation[0][2:]==('9999','1000'),shim_exact=libraries[library]==SHIM,
        headless_private_paths=args[args.index('-video')+1]=='none' and all(str(Path(args[args.index(flag)+1])).startswith(str(base)+'/') for flag in paths),
        isolated_runtime_paths_inherited_by_exec_child=e.get('ROBOTRON_DQN_MODEL_DIR')==str(J/'isolated-models') and e.get('ROBOTRON_DQN_CONTROL_PATH')==str(J/'isolated-control.json') and e.get('ROBOTRON_RUN_DIR')==str(J/'journal'),
        transport_errors0=all(marker not in text for marker in ('[SOCKET ACTION TIMEOUT]','Socket read error:','Socket write error:')))
    actors.append(dict(pid=pid,slot=slot,start_ticks=row['start_ticks'],checks=checks,activation_fields=activation,library=library,log_path=str(log),complete_prefix_bytes=len(blob),complete_prefix_sha256=hashlib.sha256(blob).hexdigest()))
manifest=json.loads((D/'actor192-all-connected.json').read_bytes());main_actors=[]
for row in manifest['actors']:
    try:actual=proc(row['pid']);same=actual['start_ticks']==row['start_ticks'] and actual['state'] not in ('Z','X')
    except OSError:same=False
    main_actors.append(dict(pid=row['pid'],slot=row['slot'],same_start_ticks=same))
with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as f:api=json.load(f)
main_api={key:api[key] for key in ('ts','client_count','training_steps','optimized_samples','learner_frame_count','frame_count','measurement_active')}
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,process_name,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
gpu_rows=[[x.strip() for x in line.split(',')] for line in gpu.stdout.splitlines() if line.strip()]
private_gpu=[row for row in gpu_rows if int(row[0]) in registry];main_gpu=[row for row in gpu_rows if row[0]=='1436155'];listeners=[]
for table in ('/proc/net/tcp','/proc/net/tcp6'):
    for line in Path(table).read_text().splitlines()[1:]:
        fields=line.split()
        if int(fields[1].split(':')[1],16)==9999 and fields[3]=='0A':listeners.append(dict(table=table,line=line,inode=fields[9]))
boundary=meta['boundary'];runner_fds=set(fdlinks[PID].values())
checks=dict(private_all_owned_GPU0_only_no_GB_context=gpu.returncode==0 and bool(private_gpu) and all(row[1]==GPU0 for row in private_gpu),
    runner_CUDA_env_GPU0_and_no_preload=private_env.get('CUDA_VISIBLE_DEVICES')==GPU0 and not private_env.get('LD_PRELOAD'),
    private_owned_FD_maps_no_real_replay_or_model_files=not fd_bad and not map_bad,
    all16_eval_headless_privateenv_shim9999wait1000=len(actors)==16 and all(all(row['checks'].values()) for row in actors),
    exact16_boundary_generation_highslots_acknowledged=boundary['ready'] is True and boundary['generation']==boundary['requested_generation']==1 and boundary['clients']==boundary['expected']==boundary['acknowledged']==16 and boundary['actor_slots']==SLOTS and not boundary['pending_client_ids'] and not boundary['replay_pending_client_ids'],
    main192_pinned_PIDs_API_and_not_measuring=len(main_actors)==192 and all(row['same_start_ticks'] for row in main_actors) and api['client_count']==192 and api['measurement_active'] is False,
    main_trainer_supervisor_startticks_unchanged=proc(1436155)['start_ticks']==24126660 and proc(1438661)['start_ticks']==24161893,
    main_GB300_only=bool(main_gpu) and all(row[1]==GB for row in main_gpu),
    port9999_listener_owned_by_private_runner=len(listeners)==1 and all('socket:['+row['inode']+']' in runner_fds for row in listeners))
scope='Observable FD/maps/device/ownership/boundary/transport only, no optimizer-object or heap proof. Runtime private paths are proven via actual16execchildren; /proc/runner/environ records exec-time values rather than later Python environment changes. Actualnumeric/compile metadata awaits finalreceipt. No partial gamecounts/scores inspected, realmodel payload/Torch/GPUcontext/control/source/process actions.'
probe=dict(utc=utc(),private_pid=PID,private_environment={key:value for key,value in private_env.items() if key.startswith(('ROBOTRON_','DQN_','CUDA_')) or key=='LD_PRELOAD'},private_cmdline=private['argv'],real_replay_model_fd_matches=fd_bad,real_replay_model_mmap_matches=map_bad,private_mame_children=actors,main_pid=1436155,main192_pinned_startticks_intact=main_actors,main_API=main_api,NVML=dict(returncode=gpu.returncode,compute_apps=gpu.stdout),owned_disappeared_after_tree_snapshot=gone,listeners9999=listeners,scope=scope)
write('quality192M-confirm01-initial-proc-isolation.json',probe)
report=dict(schema='robotron-192M-confirm01-initial-boundary-transport-isolation-audit-v1',utc=utc(),PASS=all(checks.values()),checks=checks,actors=actors,status_metadata_only=meta,known_owned_pids=sorted(registry),scope=scope)
pin=write('quality192M-confirm01-initial-boundary-transport.json',report)
print(json.dumps(dict(PASS=report['PASS'],failed=[key for key,value in checks.items() if not value],checks=len(checks),known_owned=len(registry),already_gone=gone,initial_audit_sha256=pin,start_ts=meta['start_ts'],close_ts=meta['close_ts']),indent=2))
