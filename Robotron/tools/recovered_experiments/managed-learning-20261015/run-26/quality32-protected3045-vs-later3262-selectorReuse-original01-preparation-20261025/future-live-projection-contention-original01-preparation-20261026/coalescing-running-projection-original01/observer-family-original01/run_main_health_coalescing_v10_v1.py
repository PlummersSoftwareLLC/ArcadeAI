"""Unselected autonomous observer for its own2CPU/4G systemd allocation.

No Torch, MAME, GPU, training mutation, native signals or quality qualification.
Native code/review must separately own and verify this original scope lifecycle.
"""
import argparse,hashlib,importlib.util,json,os,signal,subprocess,sys,time
from pathlib import Path

RAM_CONTROL_SHA='52372d96fdbfbd2955c260ef864d456e034c8cfe015aa776b4391b5b2e679f8c'

def require(value,message):
    if not value:raise ValueError(message)

def load(pin,name):
    path=Path(pin['path']);raw=path.read_bytes();require(len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Selected source bytes changed')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def show(unit):
    result=subprocess.run(['systemctl','--user','show',unit],check=True,capture_output=True,text=True,timeout=5)
    return dict(line.split('=',1)for line in result.stdout.splitlines()if '='in line)

def own_cgroup(pid):
    return next(line.split(':',2)[2]for line in Path('/proc',str(pid),'cgroup').read_text().splitlines()if line.startswith('0::'))

def verify_parent(parent,h,*,unit_check):
    require(set(parent)=={'pid','birth','uid','unit','invocation_id','cgroup','argv','job','source'},'Exact original native parent fields required')
    require(type(parent['pid'])is int and type(parent['birth'])is int and birth(parent['pid'])==parent['birth'],
        'Original native parent birth is absent/changed')
    require(parent['uid']==os.geteuid()and Path('/proc',str(parent['pid'])).stat().st_uid==parent['uid'],
        'Original native parent UID differs')
    require(own_cgroup(parent['pid'])==parent['cgroup'],'Original native parent cgroup differs')
    argv=[value.decode()for value in Path('/proc',str(parent['pid']),'cmdline').read_bytes().split(b'\0')[:-1]]
    require(argv==parent['argv']and '--job'in argv and '--job-sha256'in argv and '--source-sha256'in argv,
        'Original native parent argv differs')
    require(argv[argv.index('--job')+1]==parent['job']['path']and argv[argv.index('--job-sha256')+1]==parent['job']['sha256']
        and parent['source']['path']in argv and argv[argv.index('--source-sha256')+1]==parent['source']['sha256'],
        'Original native parent job/source CLI join differs')
    if unit_check:
        for pin in (parent['job'],parent['source']):h.checked(pin)
        fields=show(parent['unit'])
        require(fields['Id']==parent['unit']and fields['MainPID']==str(parent['pid'])and fields['InvocationID']==parent['invocation_id']
            and fields['ControlGroup']==parent['cgroup']and fields['ActiveState']=='active'and fields['SubState']=='running'
            and fields['NRestarts']=='0','Original native parent systemd identity changed')

def verify_self(job):
    require(type(job['unit_runtime_s'])is int and job['unit_runtime_s']in (180,22260),'Explicit bounded observer scope required')
    fields=show(job['observer_unit']);expected=dict(Id=job['observer_unit'],MainPID=str(os.getpid()),
        InvocationID=os.environ['INVOCATION_ID'],ActiveState='active',SubState='running',NRestarts='0',
        CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no')
    for key,value in expected.items():require(fields[key]==value,'Actual observer scope differs: '+key)
    require(fields['RuntimeMaxUSec']=={180:'3min',22260:'6h 11min'}[job['unit_runtime_s']],
        'Actual observer runtime bound differs')
    require(fields['ControlGroup']==own_cgroup(os.getpid())and fields['ControlGroup']!=job['parent']['cgroup'],
        'Observer must have its own CPU allocation, outside the native cgroup')
    return dict(pid=os.getpid(),starttime_ticks=birth(os.getpid()),unit=job['observer_unit'],invocation_id=fields['InvocationID'],
        cgroup=fields['ControlGroup'],uid=os.geteuid())

def run(job,jp,h,protocol,worker_source):
    require(sys.version_info[:2]==(3,14)and sys._is_gil_enabled()is False,'Exact free-threaded3.14 observer runtime required')
    require(job['worker_interpreter']['path']==sys.executable=='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','Exact selected observer interpreter path required');h.checked(job['worker_interpreter'])
    require(job['schema']=='robotron-dedicated-main-health-job-v1'and type(job['original_attempt'])is int and job['original_attempt']==1 and job['no_retry']is True,
        'Exact prospective original observer job required')
    require(type(job['nonce'])is str and len(job['nonce'])==32 and all(c in '0123456789abcdef'for c in job['nonce']),
        'Exact fresh observer nonce required')
    require(job['poll_s']==.2 and protocol.finite(job['deadline_monotonic_s'])and protocol.finite(job['parent_started_monotonic_s'])
        and 0<job['deadline_monotonic_s']-job['parent_started_monotonic_s']<=22200
        and job['parent_started_monotonic_s']<=time.monotonic()<job['deadline_monotonic_s'],
        'Bounded original parent interval required; never extend its deadline')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and not os.environ.get('LD_PRELOAD'),'Observer must remain CPU-only without a preload')
    require(job['health_job']['sources']['transport']['sha256']=='72edfb7c42106011e9551d59e1e43bba0ee8759b9e39402fd6b11dd4f5e7a0ad',
        'Exact CPU-guarded await-old-API-epoch transport required')
    for pin in job['health_job']['sources'].values():h.checked(pin)
    h.checked(job['health_job']['binding']);h.checked(job['prior_groups']);prior=json.loads(h.checked(job['prior_groups']).read_bytes())
    require(type(prior)is list,'Verified predecessor group list required')
    root=Path(job['output']);require(root.is_absolute()and root.resolve()==root and root.parent.is_dir()and not root.exists(),
        'Fresh exact observer output required');root.mkdir(mode=0o700);(root/'samples').mkdir(mode=0o700)
    storage=None;live_ready=False
    owner=None;guard=None;latest=None;closed=None;failure=None;error=None;outcome=None;next_unit_check=0.;received=[]
    def initial():
        stream=None if guard is None else guard.collector.stream
        return dict(index=None if stream is None else stream.ready_index,unix_s=None if stream is None else stream.ready_unix_s,
            unaccepted_samples=0 if stream is None else stream.initial_unaccepted_samples)
    def emit(state):
        require(live_ready and storage is not None,'Original RAM live control was not validated')
        storage.check_live(job['live_control'])
        protocol.publish_live(Path(job['live_control']['live_path']),dict(schema=protocol.LIVE_SCHEMA,job=jp,nonce=job['nonce'],parent=job['parent'],owner=owner,
            state=state,error=error,latest=latest,initial=initial(),observed_samples=0 if guard is None else guard.collector.index,
            emitted_monotonic_s=time.monotonic(),emitted_unix_s=time.time(),outcome=outcome))
    def interrupted(signum,frame):received.append(signum);raise InterruptedError('Original observer signal '+str(signum))
    handlers={sig:signal.signal(sig,interrupted)for sig in (signal.SIGINT,signal.SIGTERM)}
    try:
        require(job['live_control_helper']['sha256']==RAM_CONTROL_SHA,'Exact RAM live-control helper required');h.checked(job['live_control_helper'])
        storage=load(job['live_control_helper'],'_worker_RAM_control');storage.validate(job['live_control'],job['nonce'],job['parent'],job['native_job'],h);live_ready=True
        owner=verify_self(job);verify_parent(job['parent'],h,unit_check=True);emit('starting')
        engine=load(job['health_job']['sources']['full_health_engine'],'_dedicated_original_engine')
        guard=engine.MainHealth(job['health_job'],root,h,prior)
        while True:
            require(sys._is_gil_enabled()is False,'Original observer GIL context changed')
            tick=time.monotonic();require(tick<job['deadline_monotonic_s'],'Original native deadline reached; no late observer rescue')
            verify_parent(job['parent'],h,unit_check=tick>=next_unit_check)
            if tick>=next_unit_check:next_unit_check=tick+5
            latest=guard.observe();require(time.monotonic()<job['deadline_monotonic_s'],'Original native deadline reached during sample')
            emit('running')
            command=root/'finish-request.json'
            if command.exists():
                finish=protocol.checked_read(command,os.geteuid(),mode=0o444)
                action=protocol.validate_finish(finish,jp,job,time.monotonic())
                require(action!='abort','Original native requested abort; preserve all raw observations as failure')
                if not latest['phase']['overlap_pending']:
                    closed=h.put(root/'closed-full-health-report.json',guard.close());break
            time.sleep(max(0.,tick+.2-time.monotonic()))
    except BaseException as exc:
        error=repr(exc)
        if guard is not None:
            try:failure=h.put(root/'failed-full-health-report.json',guard.preserve_failure(exc))
            except BaseException as preservation:error+='; original preservation failure '+repr(preservation)
    finally:
        for sig,handler in handlers.items():signal.signal(sig,handler)
    writer_stopped=guard is not None and not guard.collector.writer.thread.is_alive()
    success=closed is not None and error is None and writer_stopped and not received
    require('torch'not in sys.modules,'Observer unexpectedly imported Torch')
    require(sys.version_info[:2]==(3,14)and sys._is_gil_enabled()is False,'Original observer free-threaded context changed')
    publication_stats=protocol.publication_stats()
    if success:
        require(set(publication_stats)=={'attempts','published','coalesced_busy_reader','errors'}
            and all(type(v)is int and v>=0 for v in publication_stats.values())
            and publication_stats['attempts']==publication_stats['published']+publication_stats['coalesced_busy_reader']==guard.collector.index
            and publication_stats['published']>0 and publication_stats['errors']==0,
            'Original raw observations and running projection attempt counts differ')
    outcome=h.put(root/'outcome.json',dict(running_projection_publication_stats=publication_stats,schema=protocol.OUTCOME_SCHEMA,job=jp,worker_source=worker_source,
        protocol_source=job['protocol_source'],owner=owner,parent=job['parent'],nonce=job['nonce'],success=success,live_control=job.get('live_control'),live_control_helper=job.get('live_control_helper'),
        interpreter=dict(binary=job['worker_interpreter'],executable=sys.executable,version=sys.version,major_minor=list(sys.version_info[:2]),GIL_enabled=sys._is_gil_enabled()),
        closed_report=closed,failure_report=failure,error=error,signals_received=received,
        all_writer_threads_stopped=writer_stopped,initial=initial(),observed_samples=0 if guard is None else guard.collector.index,
        deep_samples=0 if guard is None else guard.collector.deep_count,ended_monotonic_s=time.monotonic(),ended_unix_s=time.time(),
        scientific_case_qualification=False,quality_qualified=False,production_changed=False))
    if live_ready:emit('closed'if success else'failed')
    print(json.dumps(dict(outcome=outcome,success=success,error=error)),flush=True)
    return 0 if success else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Original worker source changed')
    raw=Path(args.job).read_bytes();require(hashlib.sha256(raw).hexdigest()==args.job_sha256,'Original worker job changed');job=json.loads(raw)
    h=load(job['helpers'],'_dedicated_h');jp=h.pin(args.job);h.checked(jp)
    protocol=load(job['protocol_source'],'_dedicated_protocol');h.checked(job['protocol_source'])
    return run(job,jp,h,protocol,h.pin(__file__))

if __name__=='__main__':raise SystemExit(main())
