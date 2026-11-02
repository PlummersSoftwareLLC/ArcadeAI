"""Protocol rejection contracts plus one real autonomous separately scoped worker.

Fixtures in pure protocol tests are explicitly synthetic. The actual worker
uses current main192/197 and is observed/closed once; no MAME or game evidence.
"""
import argparse,copy,hashlib,importlib.util,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path

def load(pin,name):
    path=Path(pin['path']);raw=path.read_bytes()
    if len(raw)!=pin['bytes']or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Selected source bytes changed')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256;job=json.loads(raw)
    assert job['schema']=='robotron-dedicated-main-health-component-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_component_h');protocol=load(job['protocol_source'],'_component_protocol')
    reader=load(job['reader'],'_component_r');arc=load(job['archive'],'_component_arc');closer=load(job['closer'],'_component_closer');cpu=load(job['CPU_controller'],'_component_cpu')
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    for key in ['worker','protocol_source','CPU_controller','helpers','reader','archive','closer']:h.checked(job[key])
    root=Path(job['output']);root.mkdir(mode=0o700);negative=[]
    class Contracts(unittest.TestCase):
        def sample(self):
            # Exact values below deliberately belong only to this pure fixture.
            jp=dict(path='/synthetic/job.json',sha256='a'*64,bytes=123,identity={})
            parent=dict(pid=1,birth=2);selected=dict(nonce='b'*32,parent=parent,deadline_monotonic_s=102.)
            owner=dict(pid=3,starttime_ticks=4)
            live=dict(schema=protocol.LIVE_SCHEMA,job=jp,nonce=selected['nonce'],parent=parent,owner=owner,state='running',error=None,
                latest=dict(index=0,phase=dict(accepted=True,overlap_pending=False)),initial=dict(index=0,unix_s=1000.,unaccepted_samples=0),
                observed_samples=1,emitted_monotonic_s=100.,emitted_unix_s=1000.,outcome=None)
            return jp,selected,owner,live
        def test_01_typed_fresh_original_live_projection(self):
            jp,j,o,v=self.sample();self.assertEqual(protocol.validate_live(v,jp,j,o,100.1),v)
            changes=[('schema','other'),('job',{}),('nonce','c'*32),('parent',{}),('owner',{}),('state','closed'),('state','failed'),('error','bad'),('outcome',{}),('observed_samples',True),('observed_samples',2),('emitted_monotonic_s',99.),('emitted_monotonic_s',101.),('emitted_monotonic_s',float('nan'))]
            for key,value in changes:
                bad=copy.deepcopy(v);bad[key]=value
                with self.assertRaises(ValueError):protocol.validate_live(bad,jp,j,o,100.1)
                negative.append('live:'+key+':'+str(value))
            for index in [True,-1,1]:
                bad=copy.deepcopy(v);bad['latest']['index']=index
                with self.assertRaises(ValueError):protocol.validate_live(bad,jp,j,o,100.1)
                negative.append('live:index:'+str(index))
            for initial in [dict(index=True,unix_s=1000.,unaccepted_samples=0),dict(index=0,unix_s=1000.,unaccepted_samples=True),dict(index=11,unix_s=1000.,unaccepted_samples=11),dict(index=None,unix_s=None,unaccepted_samples=0)]:
                bad=copy.deepcopy(v);bad['initial']=initial
                with self.assertRaises(ValueError):protocol.validate_live(bad,jp,j,o,100.1)
                negative.append('live:initial:'+repr(initial))
        def test_02_exact_finish_nonce_parent_action_deadline(self):
            jp,j,o,v=self.sample();finish=dict(schema=protocol.FINISH_SCHEMA,job=jp,nonce=j['nonce'],parent=j['parent'],action='close',created_monotonic_s=100.)
            self.assertEqual(protocol.validate_finish(finish,jp,j,100.1),'close')
            abort=dict(finish,action='abort');self.assertEqual(protocol.validate_finish(abort,jp,j,100.1),'abort')
            for key,value in [('schema','wrong'),('job',{}),('nonce','c'*32),('parent',{}),('action','restart'),('created_monotonic_s',101.),('created_monotonic_s',float('inf'))]:
                bad=copy.deepcopy(finish);bad[key]=value
                with self.assertRaises(ValueError):protocol.validate_finish(bad,jp,j,100.1)
                negative.append('finish:'+key)
            with self.assertRaises(ValueError):protocol.validate_finish(finish,jp,j,102.)
            negative.append('finish:original_deadline')
        def test_03_bounded_JSON_and_actual_regular_file_identity(self):
            for raw in [b'',b'[]',b'{"x":1,"x":2}',b'{"x":NaN}',b'x'*65537]:
                with self.assertRaises(ValueError):protocol.decode(raw)
                negative.append('json:'+raw[:25].decode(errors='replace'))
            with tempfile.TemporaryDirectory(dir=root)as name:
                path=Path(name)/'live.json';jp,j,o,v=self.sample();protocol.publish_live(path,v)
                self.assertEqual(protocol.checked_read(path,os.geteuid(),mode=0o644),v)
                with self.assertRaises(ValueError):protocol.checked_read(path,os.geteuid()+1,mode=0o644)
                negative.append('file:UID')
                with self.assertRaises(ValueError):protocol.checked_read(path,os.geteuid(),mode=0o444)
                negative.append('file:mode')
                link=Path(name)/'symlink.json';link.symlink_to(path)
                with self.assertRaises(OSError):protocol.checked_read(link,os.geteuid(),mode=0o644)
                negative.append('file:symlink')
                hard=Path(name)/'hard.json';os.link(path,hard)
                with self.assertRaises(ValueError):protocol.checked_read(path,os.geteuid(),mode=0o644)
                negative.append('file:hardlink')
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    assert tests.wasSuccessful()
    contract=h.put(root/'pure-protocol-contracts.json',dict(tests=tests.testsRun,negative_checks=negative,synthetic_fixture_fields=True,quality_qualified=False))
    fields=cpu.show(job['parent_unit'])
    assert fields['MainPID']==str(os.getpid())and fields['InvocationID']==os.environ['INVOCATION_ID']
    parent=dict(pid=os.getpid(),birth=birth(os.getpid()),uid=os.geteuid(),unit=job['parent_unit'],invocation_id=fields['InvocationID'],cgroup=fields['ControlGroup'],
        argv=[x.decode()for x in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]],job=h.pin(args.job),source=h.pin(__file__))
    worker_root=root/'worker-original01';worker_root.mkdir(mode=0o700);started=time.monotonic();prior=h.put(worker_root/'verified-prior-groups.json',[])
    worker_job=dict(schema='robotron-dedicated-main-health-job-v1',output=str(worker_root/'observations'),helpers=job['helpers'],protocol_source=job['protocol_source'],
        health_job=job['health_job'],prior_groups=prior,observer_unit=job['worker_unit'],unit_runtime_s=180,parent=parent,
        parent_started_monotonic_s=started,deadline_monotonic_s=started+75,poll_s=.2,nonce=os.urandom(16).hex(),original_attempt=1,no_retry=True)
    wjp=h.put(worker_root/'job.json',worker_job)
    argv=['/usr/bin/python3.12','-I','-B',job['worker']['path'],'--execute','--job',wjp['path'],'--job-sha256',wjp['sha256'],'--source-sha256',job['worker']['sha256']]
    pins=[*job['health_job']['sources'].values(),job['health_job']['binding'],job['worker'],job['protocol_source'],parent['source'],parent['job'],prior,wjp]
    cfg=dict(unit=job['worker_unit'],output=str(worker_root/'execution-original01'),argv=argv,
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[cpu.pin(pin['path'])for pin in {p['path']:p for p in pins}.values()],observation_s=240)
    cfgpin=h.put(worker_root/'controller-config.json',cfg);cpu.checked_config(cfgpin['path'])
    with(root/'worker-controller-stdout.txt').open('xb')as stdout,(root/'worker-controller-stderr.txt').open('xb')as stderr:
        command=['/usr/bin/python3.12','-I','-B',job['CPU_controller']['path'],'--execute','--config',cfgpin['path'],'--expected-source-sha256',job['CPU_controller']['sha256']]
        child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr)
    child_birth=birth(child.pid)
    h.put(root/'original-worker-controller-child.json',dict(pid=child.pid,birth=child_birth,argv=command))
    actual_owner=None;first=None;progress=None;finish=None
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            assert child.poll()is None,'Original worker controller ended before readiness'
            path=worker_root/'execution-original01/root-original-identity.json';live=worker_root/'observations/live.json'
            if path.exists()and path.stat().st_mode&0o777==0o444 and live.exists():
                basic=read(h.pin(path));owner=dict(pid=basic['pid'],starttime_ticks=basic['starttime_ticks'],unit=basic['unit'],invocation_id=basic['invocation_id'],
                    cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+basic['unit'],uid=os.geteuid())
                value=protocol.checked_read(live,os.geteuid(),mode=0o644)
                if value['state']=='running':
                    value=protocol.validate_live(value,wjp,worker_job,owner,time.monotonic())
                    if value['initial']['index']is not None and not value['latest']['phase']['overlap_pending']:actual_owner=owner;first=value;break
                elif value['state']=='failed':raise AssertionError(value['error'])
            time.sleep(.02)
        assert first is not None,'Original worker readiness not observed'
        # No native requests drive sampling during this deliberate parent pause.
        time.sleep(2)
        progress=protocol.validate_live(protocol.checked_read(worker_root/'observations/live.json',os.geteuid(),mode=0o644),wjp,worker_job,actual_owner,time.monotonic())
        assert progress['observed_samples']-first['observed_samples']>=8
        deadline=time.monotonic()+23
        while time.monotonic()<deadline:
            assert child.poll()is None
            protocol.validate_live(protocol.checked_read(worker_root/'observations/live.json',os.geteuid(),mode=0o644),wjp,worker_job,actual_owner,time.monotonic())
            time.sleep(.2)
        finish=h.put(worker_root/'observations/finish-request.json',dict(schema=protocol.FINISH_SCHEMA,job=wjp,nonce=worker_job['nonce'],parent=parent,action='close',created_monotonic_s=time.monotonic()))
        assert child.wait(timeout=25)==0
    except BaseException:
        path=worker_root/'observations/finish-request.json'
        if child.poll()is None and path.parent.exists()and not path.exists():
            h.put(path,dict(schema=protocol.FINISH_SCHEMA,job=wjp,nonce=worker_job['nonce'],parent=parent,action='abort',created_monotonic_s=time.monotonic()))
        if child.poll()is None:child.wait(timeout=25)
        raise
    scope=closer.closeout(worker_root,h,arc,read,0);outcomepin=h.pin(worker_root/'observations/outcome.json');outcome=read(outcomepin)
    assert outcome['success']and outcome['all_writer_threads_stopped']and not outcome['signals_received']and outcome['owner']==actual_owner
    assert outcome['job']==wjp and outcome['parent']==parent and outcome['nonce']==worker_job['nonce']and outcome['failure_report']is None
    closed=read(outcome['closed_report']);engine=load(job['health_job']['sources']['full_health_engine'],'_component_replay')
    replay=engine.replay(job['health_job'],closed['samples'],read(closed['initial_cursors']),read,h,original_statuses=closed['actual_status'])
    assert replay['transport']==closed['transport']and replay['deep_samples']>=5 and replay['samples']>=100
    assert birth(actual_owner['pid'])!=actual_owner['starttime_ticks']and birth(child.pid)!=child_birth
    assert 'torch'not in sys.modules
    report=h.put(root/'report.json',dict(schema='robotron-dedicated-health-component-report-v1',status='PURE_PROTOCOL_AND_ORIGINAL_SEPARATE_CPU_AUTONOMOUS_WORKER_PASS',
        pure_protocol_contract=contract,original_worker_job=wjp,original_worker_scope=scope,original_worker_outcome=outcomepin,initial_live=first,
        parent_pause_without_capture_requests_s=2,autonomous_sample_progress=progress['observed_samples']-first['observed_samples'],finish_request=finish,
        complete_original_raw_replay=replay,separate_actual_CPU_cgroup_verified=True,worker_and_controller_normal_exit0_and_reaped=True,
        native_integration_still_required=True,scientific_case=False,quality_qualified=False,production_changed=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=report,tests=tests.testsRun,negative_checks=len(negative),raw_samples=replay['samples'],deep=replay['deep_samples'])),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
