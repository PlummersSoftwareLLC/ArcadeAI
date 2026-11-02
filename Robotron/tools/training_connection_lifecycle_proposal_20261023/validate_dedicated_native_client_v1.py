"""Real native-shaped client/finalizer/reviewer component; no Torch or games."""
import argparse,hashlib,importlib.util,json,os,sys,threading,time
from pathlib import Path
def load(pin,name):
 path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
 if not a.execute:print('PLAN_ONLY');return 0
 assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
 raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
 assert job['schema']=='robotron-dedicated-native-client-component-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
 h=load(job['helpers'],'_client_component_h');reader=load(job['reader'],'_client_component_reader')
 def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
 jp=h.pin(a.job);family=read(job['source_family_manifest']);protocol=read(job['main_health_protocol'])
 client=load(family['main_observer']['client'],'_client_component');finalizer=load(family['main_health_finalizer'],'_client_component_finalizer');reviewer=load(family['main_observer']['reviewer'],'_client_component_review')
 root=Path(job['output']);root.mkdir(mode=0o700);started=time.monotonic();deadline=started+job['wall_limit_s'];guard=None;watch=None;stop=threading.Event();lock=threading.Lock();errors=[];snapshots=[]
 def collect():
  status=guard.observe();snapshots.append(status);return status
 def watch_status():
  while not stop.wait(.2):
   try:
    with lock:
     if stop.is_set():return
     collect()
   except Exception as e:errors.append(repr(e));return
 try:
  guard=client.DedicatedMainHealth(job,jp,protocol,family,h,started=started,deadline=deadline,prior_groups=[])
  initial=guard.start();assert guard.initial['index']is not None and not initial['phase']['overlap_pending']
  watch=threading.Thread(target=watch_status,name='native-shaped-health-status-watch');watch.start()
  time.sleep(25)
  assert not errors
 except BaseException as e:errors.append(repr(e))
 finally:
  finalized=finalizer.finalize(guard,watch,stop,lock,collect,deadline,h,root/'main-observations',case_already_failed=bool(errors))if guard is not None else None
 assert not errors and finalized is not None,errors
 assert finalized['errors']==[]and finalized['watch_stopped']and finalized['writer_stopped']and finalized['scope_complete']
 assert guard.scope_complete and not watch.is_alive()and guard.child.returncode==0
 native_owner=read(h.pin(Path(job['controller_directory'])/'execution-original01/root-original-identity.json'))
 native_argv=[x.decode()for x in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]]
 checked=reviewer.verify(job,jp,native_owner,native_argv,guard.lifecycle,protocol,family,[],read,h)
 assert checked['closed_report']==finalized['report']
 closed=read(finalized['report']);assert closed['actual_status']==finalized['statuses']
 engine=load(protocol['health_job']['sources']['full_health_engine'],'_client_component_engine')
 replay=engine.replay(protocol['health_job'],closed['samples'],read(closed['initial_cursors']),read,h,original_statuses=closed['actual_status'])
 assert replay['transport']==closed['transport']and replay['samples']>=100 and replay['deep_samples']>=5
 assert [status['index']for status in finalized['statuses']]==list(range(replay['samples']))
 assert 'torch'not in sys.modules
 report=h.put(root/'report.json',dict(schema='robotron-dedicated-native-client-component-report-v1',status='REAL_LONG_SCOPE_CLIENT_WATCH_FINALIZER_REVIEW_AND_RAW_REPLAY_PASS',
  initial_ready=initial,initial_baseline=guard.initial,watch_snapshots=len(snapshots),all_actual_original_statuses=len(finalized['statuses']),finalized=finalized,
  observer_lifecycle=guard.lifecycle,independent_worker_review=checked,complete_original_raw_replay=replay,native_started_monotonic_s=started,native_deadline_monotonic_s=deadline,
  actual_observer_runtime_scope_s=9660,actual_capture_s=closed['guard_ended_monotonic_s']-closed['guard_started_monotonic_s'],
  native_MAME_integration_still_required=True,scientific_case=False,quality_qualified=False,production_changed=False,created_unix_s=time.time()))
 print(json.dumps(dict(report=report,samples=replay['samples'],deep=replay['deep_samples'])));return 0
if __name__=='__main__':raise SystemExit(main())
