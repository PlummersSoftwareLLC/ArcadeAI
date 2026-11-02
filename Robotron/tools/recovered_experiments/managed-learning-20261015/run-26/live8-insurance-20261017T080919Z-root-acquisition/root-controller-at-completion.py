from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,stat,subprocess,tempfile,urllib.request

ROOT=Path('/home/dave/source/repos/ArcadeAI');GAME=ROOT/'Robotron';MODELS=GAME/'models_dqn';RUN=GAME/'logs/managed-learning-20261015/run-26'
TRAINER='robotron-managed-run-26-d3b365c9-trainer.service';FLEET=TRAINER.replace('trainer.service','fleet.service')
def require(x,m):
    if not x:raise RuntimeError(m)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ident(p):
    s=Path(p).lstat();require(stat.S_ISREG(s.st_mode),'Not regular')
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
def syncdir(p):
    f=os.open(p,os.O_DIRECTORY)
    try:os.fsync(f)
    finally:os.close(f)
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    syncdir(p.parent)
def unit(u):
    r=subprocess.run(['systemctl','--user','show',u],capture_output=True,text=True,check=True)
    return dict(x.split('=',1) for x in r.stdout.splitlines() if '=' in x)
def process(pid):
    fields=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid,starttime_ticks=int(fields[19]),state=fields[0],ppid=int(fields[1]),pgid=int(fields[2]))
def api():
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=10) as f:return json.load(f)
def held():
    t,f=unit(TRAINER),unit(FLEET)
    require(t['MainPID']=='4098959' and t['InvocationID']=='85363b88e20f414790b0f683d693621e' and t['ActiveState']=='active','Trainer changed')
    require(f['MainPID']=='2258189' and f['InvocationID']=='5ade9b2810524877921946df11ea597e' and f['ActiveState']=='active','Fleet changed')
    require(process(4098959)['starttime_ticks']==31468656 and process(2258189)['starttime_ticks']==26614335,'PID reused')
    value=api();require(value['client_count']==192 and value['training_enabled'] and value['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth' and not value['measurement_active'],'Unexpected main profile')
    require(value['host_pipeline']['inference']['errors']==0 and not value['pipeline_read_error'] and not value['bank_persistence_read_error'],'Main health failure')
    return t,f,value
def create():
    request=MODELS/'managed_save.request.json'
    require(not request.exists(),'Pending request already owned')
    require(not (MODELS/'managed_save.request.json.failed').exists(),'Unresolved failed request')
    t,f,value=held()
    state=json.loads((RUN.parent/'state.json').read_text())
    require(state['optimization_goal']['status']=='active' and state['optimization_goal']['next_checkpoint']['status']=='paused_for_live8_owned_window_v4','Goal/gate changed')
    require(state['active_maintenance_job'] is None and state.get('active_diagnostic_job') is None,'Another active job')
    blockers={'checkpoint_at_frame.py','cuda_trace_parent.py','cuda_trace_worker.py','forensic_parent.py','forensic_worker.py','cpu_reservation_trial.py','run_quality_campaign.py','run_frozen_sidecar.py'}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():continue
        try:args=(entry/'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
        require(not any(Path(os.fsdecode(a)).name in blockers for a in args if a),'Competing helper still live')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');tag='live8-insurance-'+stamp
    directory=RUN/(tag+'-root-acquisition');source=MODELS/'managed-checkpoints'/(tag+'.pt')
    require(not directory.exists() and not source.exists(),'Unique insurance path already exists')
    directory.mkdir(mode=0o700)
    prior=MODELS/'managed_save.request.json.completed';prior_record=None
    if prior.exists():
        raw=prior.read_bytes();dest=directory/'previous-completed-request.json'
        with dest.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        dest.chmod(0o444);prior_record=dict(path=str(prior),identity=ident(prior),sha256=sha(prior),archived_as=str(dest),archived_sha256=sha(dest))
    actor_ids=[]
    for rawpid in (Path('/sys/fs/cgroup')/f['ControlGroup'].lstrip('/')/'cgroup.procs').read_text().split():
        pid=int(rawpid)
        try:
            if (Path('/proc')/rawpid/'comm').read_text().strip()!='mame':continue
            observed=process(pid);observed['affinity']=sorted(os.sched_getaffinity(pid));actor_ids.append(observed)
        except (FileNotFoundError,ProcessLookupError):raise RuntimeError('Actor disappeared during binding')
    require(len(actor_ids)==192 and all(a['affinity']==list(range(72)) for a in actor_ids),'Actor count or masks changed')
    trainer=dict(pid=4098959,starttime_ticks=31468656,unit=TRAINER,invocation_id=t['InvocationID'],cgroup=t['ControlGroup'])
    context=dict(schema='robotron-live8-insurance-root-acquisition-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        tag=tag,checkpoint=str(source),request_path=str(request),request_payload=dict(tag=tag),trainer=trainer,
        fleet=dict(unit=FLEET,pid=2258189,starttime_ticks=26614335,invocation_id=f['InvocationID'],cgroup=f['ControlGroup']),
        actors=sorted(actor_ids,key=lambda a:a['pid']),trigger_snapshot={k:value[k] for k in ('learner_frame_count','frame_count','training_steps','optimized_samples','client_count')},
        branch=value['managed_experiment'],model_dir=str(MODELS),prior_completion=prior_record,
        root_controller_sha256=sha(__file__),only_model_save=True,save_replay=False,no_stop_or_source_recipe_affinity_change=True)
    save(directory/'precommit.json',context);save(directory/'main-before.json',value)
    with (directory/'root-controller-at-request.py').open('xb') as archive:archive.write(Path(__file__).read_bytes());archive.flush();os.fsync(archive.fileno())
    (directory/'root-controller-at-request.py').chmod(0o444)
    fd,name=tempfile.mkstemp(prefix='.live8-insurance-request-',dir=MODELS)
    try:
        with os.fdopen(fd,'w') as out:json.dump(dict(tag=tag),out);out.write('\n');out.flush();os.fsync(out.fileno())
        os.link(name,request)
    finally:Path(name).unlink(missing_ok=True)
    syncdir(MODELS)
    save(directory/'request-publication.json',dict(status='ONE_MODEL_ONLY_REQUEST_PUBLISHED',tag=tag,request_path=str(request),checkpoint=str(source),published_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    print(json.dumps(dict(status='REQUESTED_ONCE',directory=str(directory),tag=tag,checkpoint=str(source))))
def complete(directory):
    directory=directory.resolve();require(directory.parent==RUN and directory.name.startswith('live8-insurance-'),'Unexpected acquisition path')
    context=json.loads((directory/'precommit.json').read_text());source=Path(context['checkpoint']);tag=context['tag']
    t,f,value=held();require(t['InvocationID']==context['trainer']['invocation_id'],'Trainer changed since request')
    request=MODELS/'managed_save.request.json';completed=MODELS/'managed_save.request.json.completed'
    require(not request.exists(),'Own request still pending; observe again, do not replace')
    require(completed.is_file() and json.loads(completed.read_text())==dict(tag=tag),'Matching completed request missing')
    require(source.is_file() and 0<source.stat().st_size<=512*(1<<20),'Saved model missing/wrong size')
    require(not (directory/'saved-insurance-receipt.json').exists(),'Insurance already frozen')
    raw=completed.read_bytes()
    with (directory/'matching-completed-request.json').open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    (directory/'matching-completed-request.json').chmod(0o444)
    source.chmod(0o444);before=ident(source);source_sha=sha(source);copy=directory/'insurance-readonly-copy.pt'
    with source.open('rb') as inp,copy.open('xb') as out:shutil.copyfileobj(inp,out,4*(1<<20));out.flush();os.fsync(out.fileno())
    copy.chmod(0o444);syncdir(directory)
    require(ident(source)==before and sha(source)==source_sha==sha(copy),'Source/copy bytes changed')
    require((before['device'],before['inode'])!=(ident(copy)['device'],ident(copy)['inode']),'Copy shares source inode')
    require(json.loads(completed.read_text())==dict(tag=tag),'Completion changed while freezing')
    save(directory/'main-after.json',value)
    with (directory/'root-controller-at-completion.py').open('xb') as archive:archive.write(Path(__file__).read_bytes());archive.flush();os.fsync(archive.fileno())
    (directory/'root-controller-at-completion.py').chmod(0o444)
    receipt=dict(status='MODEL_SAVED_MATCHED_FROZEN_CPU_VERIFICATION_PENDING',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),tag=tag,
        source=dict(path=str(source),sha256=source_sha,**before),copy=dict(path=str(copy),sha256=sha(copy),**ident(copy)),
        completed_request=str(directory/'matching-completed-request.json'),completed_request_sha256=sha(directory/'matching-completed-request.json'),
        precommit=str(directory/'precommit.json'),precommit_sha256=sha(directory/'precommit.json'),trainer=context['trainer'],
        actual_tensor_clocks_unknown_until_CPU_proof=True,insurance_is_not_boot_input=True,no_replay_copy=True,no_trainer_actor_stop_or_recipe_source_change=True)
    save(directory/'saved-insurance-receipt.json',receipt)
    print(json.dumps(dict(status=receipt['status'],receipt=str(directory/'saved-insurance-receipt.json'),sha256=sha(directory/'saved-insurance-receipt.json'),model_sha256=source_sha)))
parser=argparse.ArgumentParser();parser.add_argument('action',choices=('create','complete'));parser.add_argument('--directory',type=Path);args=parser.parse_args()
if args.action=='create':create()
else:require(args.directory is not None,'Directory required');complete(args.directory)
