from pathlib import Path
import ast,copy,importlib.util,json,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';N=B/'future-fast-pending-physical-watch-source-original01-20261101';O=N/'live-pending-transition-engineering-original02';L=N/'published-pending-trigger-engineering-original03'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_event03h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');head=load('_event03head',B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101/sources/prepare_current_continuous_preservation_header_v3.py')
assert not L.exists();L.mkdir(mode=0o700)
helper='''\ndef wait_for_published_pending(guard, limit_s):
 """Read-only wake-up hint; the subsequent real observer decides validity.

 No physical health coverage is claimed during this finite waiting stage.
 Stat at50Hz, parse only a newly published fleet snapshot, and never touch
 an actor, socket, trainer control, or the original supervisor's files.
 """
 started=time.monotonic();last=None;reads=0;checks=0
 while True:
  now=time.monotonic()
  if now-started>=limit_s:
   return dict(reason='NO_PUBLISHED_PENDING_WITHIN_PREDECLARED_WAIT',wait_s=now-started,stat_checks=checks,snapshot_reads=reads,pending_slots=[]),None
  path=Path(guard.expected['status_path']);st=path.stat();checks+=1
  signature=(st.st_ino,st.st_mtime_ns,st.st_size)
  if signature!=last:
   last=signature;value=guard.status();reads+=1
   assert value['epoch']==guard.expected['epoch'],'Original fleet epoch changed during trigger wait'
   assert value['errors']==[] and value['error_summary']['occurrences']==0,'Original fleet fault during trigger wait'
   slots=sorted(int(k)for k,v in value['slots'].items()if v['state']in ('reconnecting_train','retiring_eval'))
   if slots:
    return dict(reason='ACTUAL_PUBLISHED_PENDING_WAKEUP_HINT',observed_monotonic_s=time.monotonic(),wait_s=time.monotonic()-started,stat_checks=checks,snapshot_reads=reads,pending_slots=slots,exact_status_signature=list(signature)),value
  time.sleep(min(.02,max(0,limit_s-(time.monotonic()-started))))
\n'''
src=(O/'run_live_pending_transition_engineering_v2.py').read_text();src=src.replace('\ndef main():',helper+'def main():',1)
edits=[
("job['schema']=='robotron-readonly-fast-pending-transition-engineering-v2'and job['accepted_samples_required']==40 and job['pending_samples_required']==1 and job['stable_observation_window_s']==520", "job['schema']=='robotron-published-pending-trigger-engineering-v3'and job['accepted_samples_required']==40 and job['pending_samples_required']==1 and job['stable_observation_window_s']==275 and job['trigger_wait_s']==240"),
("report={};code=1", "report={};code=1;trigger=None;trigger_snapshot=None;trigger_pin=None;observing_started=None"),
("time.monotonic()-started>=job['stable_observation_window_s']", "time.monotonic()-observing_started>=job['stable_observation_window_s']"),
("  worker.start()", "  trigger,trigger_snapshot=wait_for_published_pending(main_guard,job['trigger_wait_s'])\n  observing_started=time.monotonic()\n  try:collect_main()\n  finally:\n   if trigger_snapshot is not None:trigger_pin=h.put(out/'actual-published-pending-wakeup-snapshot.json',trigger_snapshot)\n  worker.start()"),
("  health_stop.set();worker.join(12)", "  health_stop.set()\n  if worker.ident is not None:worker.join(12)"),
(" report.update(original_job=jp", " report.update(published_pending_trigger=trigger,trigger_snapshot=trigger_pin,no_health_coverage_claimed_during_trigger_wait=True,original_job=jp")]
for a,b in edits:
 assert src.count(a)==1,(a,src.count(a));src=src.replace(a,b)
ast.parse(src);rp=head.put(L/'run_published_pending_watch_engineering_v3.py',src.encode());old=json.loads((O/'job.json').read_text());j=copy.deepcopy(old);j.update(schema='robotron-published-pending-trigger-engineering-v3',runtime=rp,stable_observation_window_s=275,trigger_wait_s=240,output=str(L/'runtime-original01'),report=str(L/'report.json'))
j['inputs']=[rp if v==old['runtime']else v for v in old['inputs']]
for pin in j['inputs']:h.checked(pin)
jp=h.put(L/'job.json',j);prep=json.loads((O/'prepared-not-launched.json').read_text());ctl=load('_event03ctl',h.checked(prep['controller']));c=copy.deepcopy(json.loads((O/'controller-config.json').read_text()));c.update(unit='robotron-published-pending-CPU-'+jp['sha256'][:12]+'.service',output=str(L/'execution-original01'))
for i,v in enumerate(c['argv']):
 if v==old['runtime']['path']:c['argv'][i]=rp['path']
 if v==str(O/'job.json'):c['argv'][i]=jp['path']
 if v==prep['job']['sha256']:c['argv'][i]=jp['sha256']
c['pins']=[ctl.pin(pin['path'])for pin in [jp]+j['inputs']];cp=h.put(L/'controller-config.json',c);ctl.checked_config(cp['path'])
p=h.put(L/'prepared-not-launched.json',dict(status='PRECOMMITTED_PUBLISHED_PENDING_TRIGGER_READONLY_ENGINEERING_NOT_LAUNCHED',controller=prep['controller'],controller_config=cp,job=jp,success_rule='At least40 accepted physical samples plus at least1 actual pending observation and subsequent accepted recovery; replay actual fast-pending cadence and strict process/TCP/cleanup joins independently. Wake-up hint alone is not branch coverage.',wait_rule='Up to240s for a newly published real fleet snapshot containing reconnecting_train or retiring_eval. Stat at50Hz, parse changed snapshots only. No health coverage claimed during this pre-observation wait. If none, still observe finite stable window and classify missing coverage truthfully.',finite_stop='Stop once40 accepted and actual pending covered; otherwise accepted sample after275s observation. Total collection bound540s/wall550s/resource600s. No attempt retry.',unchanged_bounds=dict(cleanup_ACK_s=7,overlap_s=10,collection_s=10,observer_gap_s=15),prospective_native=old['prospective_native'],no_Main_control_changes=True,no_actors_or_GPU_context=True,quality_qualified=False,promotion=False))
print(json.dumps({k:p[k]for k in ['path','sha256','bytes']}))
