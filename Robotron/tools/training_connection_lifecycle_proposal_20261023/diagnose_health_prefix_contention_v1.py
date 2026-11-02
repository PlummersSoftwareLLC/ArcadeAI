"""Prospective CPU diagnostic: authentic closed-prefix work and live main sampling.

No models, MAME, learning mutations or game qualification. Two precommitted arms
compare the same original32 producer-prefix workload with a health thread and a
health interpreter child. Every observation and diagnostic failure is retained.
This is not an implementation of future scientific observer IPC/lifecycle.
"""
import argparse,hashlib,importlib.util,json,os,subprocess,sys,threading,time
from pathlib import Path

def load(pin,name):
    path=Path(pin['path']);raw=path.read_bytes()
    assert len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def birth(pid):
    return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])

def resource():
    cg=next(line.split(':',2)[2]for line in Path('/proc/self/cgroup').read_text().splitlines()if line.startswith('0::'))
    root=Path('/sys/fs/cgroup'+cg);out=dict(pid=os.getpid(),birth=birth(os.getpid()),cgroup=cg,monotonic_s=time.monotonic(),unix_s=time.time(),thread_cpu_s=time.thread_time(),process_cpu_s=time.process_time())
    for name in ['cpu.stat','cpu.pressure','memory.current','memory.peak','cpu.max','cpuset.cpus.effective']:
        path=root/name
        if path.exists():out[name]=path.read_text()
    return out

def observe_arm(job,h,arm,started=None):
    root=Path(job['output'])/arm;directory=root/'health';directory.mkdir(mode=0o700);(directory/'samples').mkdir(mode=0o700)
    engine=load(job['health_job']['sources']['full_health_engine'],'_diagnostic_engine_'+arm)
    guard=None;error=None;closed=None;failed=None;timing=[];begin=None
    try:
        guard=engine.MainHealth(job['health_job'],directory,h)
        first=guard.observe();begin=time.monotonic()
        h.put(root/'original-health-start.json',dict(pid=os.getpid(),birth=birth(os.getpid()),first=first,started_monotonic_s=begin,resource=resource()))
        if started is not None:started.set()
        while time.monotonic()-begin<job['arm_duration_s']:
            due=time.monotonic()+job['poll_s'];time.sleep(max(0,due-time.monotonic()))
            entry=dict(index=guard.collector.index,scheduled_monotonic_s=due,begin_monotonic_s=time.monotonic(),before=resource())
            try:status=guard.observe();entry.update(status=status)
            finally:entry.update(end_monotonic_s=time.monotonic(),after=resource());timing.append(entry)
        closed=guard.close();h.put(root/'original-closed-health.json',closed)
    except BaseException as failure:
        error=repr(failure)
        if guard is not None:
            if not guard.closed:failed=guard.preserve_failure(failure)
            else:
                # close() can mark closed before a pending stream fails. Preserve
                # the already drained original bytes without a second close.
                failed=dict(status='ORIGINAL_DIAGNOSTIC_HEALTH_CLOSE_FAILED',error=error,
                    samples=guard.collector.writer.records,actual_status=guard.statuses,
                    initial_cursors=guard.initial_cursors,health_job=job['health_job'],
                    writer_thread_alive=guard.collector.writer.thread.is_alive())
            if failed is not None:h.put(root/'original-failed-health.json',failed)
    finally:
        if started is not None:started.set()
    pins=closed['samples']if closed is not None else failed['samples']if failed is not None else[]
    previous=None;gaps=[];deep=0
    for pin in pins:
        record=json.loads(h.checked(pin).read_bytes());sample=record['transport'];deep+=int(record['deep']is not None)
        if previous is not None:gaps.append(dict(index=sample['index'],gap_s=sample['observed_unix_s']-previous))
        previous=sample['observed_unix_s']
    output=dict(schema='robotron-prefix-contention-live-health-arm-v1',arm=arm,pid=os.getpid(),birth=birth(os.getpid()),
        valid_closed_health=closed is not None,error=error,samples=len(pins),deep_censuses=deep,
        duration_since_first_sample_s=None if begin is None else time.monotonic()-begin,
        original_health_closed=h.pin(root/'original-closed-health.json')if closed is not None else None,
        original_health_failure=h.pin(root/'original-failed-health.json')if failed is not None else None,
        maximum_observation_gap_s=max((x['gap_s']for x in gaps),default=0),gap_violations=[x for x in gaps if x['gap_s']>.5],
        timing=timing,final_resource=resource(),production_changed=False,quality_qualified=False)
    return h.put(root/'original-health-arm-result.json',output)

def workload(job,h,bridge,root):
    barrier=threading.Barrier(33);results=[];errors=[];lock=threading.Lock()
    def one(subject):
        try:
            trace=h.checked(subject['trace']);identity={k:subject['trace']['identity'][k]for k in ['device','inode','mode','uid','nlink']}
            barrier.wait(timeout=10);begin=time.monotonic();cpu=time.thread_time()
            prefix=bridge.TracePrefix(trace,identity,subject['subject'],job['loaded_rom_sha256'])
            summary=prefix.closed_summary(subject['nonce'],subject['initialized_sequence'])
            assert summary['footer']==subject['footer']and summary['events']==subject['events']and summary['trace']['sha256']==subject['trace']['sha256']
            result=dict(slot=subject['subject']['slot'],start_monotonic_s=begin,end_monotonic_s=time.monotonic(),thread_CPU_s=time.thread_time()-cpu,
                actual_trace_sha256=summary['trace']['sha256'],events=summary['events'],original_prefix_verifier_unchanged=True)
            with lock:results.append(result)
        except BaseException as error:
            with lock:errors.append(repr(error))
            try:barrier.abort()
            except BaseException:pass
    threads=[threading.Thread(target=one,args=(subject,),name='authentic-prefix-'+str(subject['subject']['slot']))for subject in job['prefix_subjects']]
    before=resource()
    for thread in threads:thread.start()
    try:barrier.wait(timeout=10)
    except threading.BrokenBarrierError:pass
    for thread in threads:thread.join(timeout=20)
    assert not any(thread.is_alive()for thread in threads),'Diagnostic workload thread did not stop'
    assert not errors and len(results)==32,(errors,len(results))
    return dict(before=before,after=resource(),original32_prefixes=sorted(results,key=lambda row:row['slot']),all_threads_stopped=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');parser.add_argument('--health-arm',choices=['process'])
    args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256;job=json.loads(raw)
    assert job['schema']=='robotron-live-health-authentic-prefix-contention-diagnostic-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''and job['arm_duration_s']==25 and job['poll_s']==.2
    assert job['burst_offsets_s']==[2,5,8,11,14,17]and len(job['prefix_subjects'])==32
    h=load(job['helpers'],'_contention_h')
    for pin in job['sources'].values():h.checked(pin)
    for subject in job['prefix_subjects']:h.checked(subject['trace'])
    if args.health_arm:
        observe_arm(job,h,'process');return 0
    root=Path(job['output']);root.mkdir(mode=0o700)
    sys.path.insert(0,str(Path(job['bridge']['path']).parent));bridge=load(job['bridge'],'_contention_original_bridge')
    arms=[]
    for arm in ['thread','process']:
        directory=root/arm;directory.mkdir(mode=0o700);before=resource();child=None;thread=None
        if arm=='thread':
            ready=threading.Event();thread=threading.Thread(target=observe_arm,args=(job,h,arm,ready),name='diagnostic-live-health');thread.start()
            assert ready.wait(timeout=10),'Original diagnostic health thread did not start'
        else:
            argv=['/usr/bin/python3.12','-I','-B',str(Path(__file__).resolve()),'--execute','--job',args.job,'--job-sha256',args.job_sha256,'--source-sha256',args.source_sha256,'--health-arm','process']
            with (directory/'child-stdout.txt').open('xb')as out,(directory/'child-stderr.txt').open('xb')as err:
                child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
            h.put(directory/'original-child-identity.json',dict(pid=child.pid,birth=birth(child.pid),argv=argv,cgroup=Path('/proc',str(child.pid),'cgroup').read_text(),parent_pid=os.getpid(),parent_birth=birth(os.getpid())))
            deadline=time.monotonic()+10
            while not(directory/'original-health-start.json').exists():
                assert child.poll()is None and time.monotonic()<deadline,'Original diagnostic health child did not start'
                time.sleep(.01)
        baseline=time.monotonic();bursts=[]
        for offset in job['burst_offsets_s']:
            time.sleep(max(0,baseline+offset-time.monotonic()));bursts.append(workload(job,h,bridge,directory))
        if thread is not None:thread.join(timeout=35);assert not thread.is_alive()
        if child is not None:assert child.wait(timeout=35)==0
        pin=h.pin(directory/'original-health-arm-result.json');health=json.loads(h.checked(pin).read_bytes())
        for gap in health['gap_violations']:assert gap['gap_s']>.5
        arms.append(dict(arm=arm,before=before,after=resource(),health=pin,bursts=bursts,
            exact_same_original32_prefixes_each_burst=True,workload_threads_stopped=True,
            diagnostic_child_exit0_and_reaped=None if child is None else child.returncode==0))
    assert 'torch'not in sys.modules
    report=h.put(root/'report.json',dict(schema='robotron-authentic-prefix-contention-diagnostic-report-v1',
        status='BOTH_ORIGINAL_DIAGNOSTIC_ARMS_COMPLETED_HEALTH_OUTCOMES_PRESERVED',arms=arms,
        diagnostic_only=True,thread_or_process_health_failure_not_rescued=True,
        native_MAME_game_run=False,native_observer_IPC_lifecycle_fix_implemented=False,
        production_changed=False,quality_qualified=False,learning_speed_gain_verified=False,useful_training_throughput_gain_verified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=report,health=[{k:v for k,v in json.loads(h.checked(a['health']).read_bytes()).items()if k in ['arm','valid_closed_health','error','samples','maximum_observation_gap_s']}for a in arms])),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
