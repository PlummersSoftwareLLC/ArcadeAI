"""Passive bounded watch of original handles and immutable health samples."""
import argparse,hashlib,importlib.util,json,os,subprocess,time
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--observe',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
 if not a.observe:print('PLAN_ONLY');return 0
 assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
 raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
 assert job['duration_s']==300 and job['poll_s']==30 and job['may_control_or_schedule']is False
 def load(pin):
  path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
  sp=importlib.util.spec_from_file_location('_passive_root_h',path);h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h);return h
 h=load(job['helpers'])
 for pin in job['inputs']:h.checked(pin)
 root=Path(job['campaign']);out=Path(job['output']);out.mkdir(mode=0o700)
 def birth(pid):
  try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
  except FileNotFoundError:return None
 intent=h.put(out/'watch-intent.json',dict(pid=os.getpid(),birth=birth(os.getpid()),job=h.pin(a.job),source=h.pin(__file__),may_control_or_schedule=False,scientific_case=False,created_unix_s=time.time()))
 print(json.dumps(dict(passive_watch_intent=intent)),flush=True)
 records=[];reason='BOUNDED_PASSIVE_WATCH_COMPLETE';error=None;started=time.monotonic()
 try:
  while True:
   now=time.time();owners=[]
   for owner in job['original_parents']:
    current=birth(owner['pid']);owners.append(dict(**owner,observed_birth=current))
    if current!=owner['birth']:reason='ORIGINAL_HANDLE_TERMINAL_OR_CHANGED_REQUIRES_ACTUAL_OUTCOME_READBACK';break
   if reason!='BOUNDED_PASSIVE_WATCH_COMPLETE':break
   status=json.loads((root/'01-reference/diagnostic-output-original01/status.json').read_bytes());assert 0<=time.time()-status['observed_unix_s']<=6
   cohort=status['controller']['cohort'];assert cohort['abandoned']==0 and cohort['valid']and cohort['count']+cohort['pending']==cohort['started']<=64
   for slot,row in status['slots'].items():
    assert birth(row['pid'])==row['birth']and row['error']is None and row['ledger']['rejected']==0
   samples=root/'01-reference/diagnostic-output-original01/main-observations/samples';latest=max(samples.glob('*.json'));sample=json.loads(latest.read_bytes())['transport'];assert 0<=time.time()-sample['observed_unix_s']<=2
   main=json.loads(subprocess.check_output(['/usr/bin/python3.12','-I','-B',job['main_monitor']['path']],text=True,timeout=25))
   record=dict(observed_unix_s=time.time(),elapsed_s=time.monotonic()-started,original_parents=owners,controller_phase=status['controller']['phase'],cohort={key:cohort[key]for key in('started','count','pending','abandoned','mean','median','closed','closed_by')},min_sequence=min(row['sequence']for row in status['slots'].values()),max_sequence=max(row['sequence']for row in status['slots'].values()),raw_health_index=sample['index'],raw_health_age_s=time.time()-sample['observed_unix_s'],current_main=main,quality_qualified=False)
   rp=h.put(out/f'observation-{len(records):03d}.json',record);records.append(rp)
   print(json.dumps(dict(passive_elapsed_s=round(record['elapsed_s'],1),completed=cohort['count'],started=cohort['started'],pending=cohort['pending'],provisional_mean=cohort['mean'],raw_health_index=sample['index'],main_fps=main['fleet_fps'],autosave_age_s=main['autosave_age_s'])),flush=True)
   if record['elapsed_s']>=job['duration_s']:break
   time.sleep(min(job['poll_s'],job['duration_s']-record['elapsed_s']))
 except Exception as e:reason='PASSIVE_READBACK_EXCEPTION_REQUIRES_RECHECK_NOT_A_NATIVE_OUTCOME';error=repr(e)
 report=h.put(out/'watch-outcome.json',dict(status=reason,error=error,intent=intent,observations=records,original_handle_outcome_inferred=False,may_control_or_schedule=False,scientific_case=False,quality_qualified=False,created_unix_s=time.time()))
 print(json.dumps(dict(passive_watch_outcome=report,status=reason,error=error)),flush=True);return 0 if error is None else 1
if __name__=='__main__':raise SystemExit(main())
