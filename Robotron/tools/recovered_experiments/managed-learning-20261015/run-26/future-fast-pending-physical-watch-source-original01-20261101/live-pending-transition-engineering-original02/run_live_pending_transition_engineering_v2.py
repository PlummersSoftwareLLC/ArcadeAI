"""Finite read-only observer engineering; creates no actors, model or GPU context."""
import argparse,ast,copy,hashlib,importlib.util,json,os
from pathlib import Path
import threading,time,traceback

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job',type=Path);p.add_argument('--job-sha256');a=p.parse_args()
 if not a.execute:print('PLAN_ONLY');return 0
 G=Path('/home/dave/source/repos/ArcadeAI/Robotron');h=load('_liveFastWatchStartup',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
 jp=h.pin(a.job);assert jp['sha256']==a.job_sha256;job=json.loads(h.checked(jp).read_text());assert job['runtime']==h.pin(Path(__file__).resolve())
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''and not os.environ.get('LD_PRELOAD')
 assert job['schema']=='robotron-readonly-fast-pending-transition-engineering-v2'and job['accepted_samples_required']==40 and job['pending_samples_required']==1 and job['stable_observation_window_s']==520
 out=Path(job['output']);assert not out.exists();out.mkdir(mode=0o700)
 bindings=json.loads(h.checked(job['bindings']).read_text());source=h.checked(job['prospective_native']);module=ast.parse(source.read_text());run=next(n for n in module.body if isinstance(n,ast.FunctionDef)and n.name=='run');watch=next(n for n in ast.walk(run)if isinstance(n,ast.FunctionDef)and n.name=='watch_main')
 health=load('_liveFastWatchHealth',h.checked(bindings['current_v6_health_source']));main_guard=health.CurrentV6MainHealth(bindings,out,h);main_guard.start()
 health_stop=threading.Event();stopped=threading.Event();main_lock=threading.Lock();errors=[];samples=[];accepted=[];started=time.monotonic()
 def collect_main():
  value=main_guard.observe();samples.append(value)
  if not value['phase']['overlap_pending']:accepted.append(value)
  assert len(samples)<1000 and time.monotonic()-started<540
  covered = len(samples)>len(accepted) and not value['phase']['overlap_pending']
  if len(accepted)>=job['accepted_samples_required'] and (covered or time.monotonic()-started>=job['stable_observation_window_s']):health_stop.set()
  return value
 context=dict(main_guard=main_guard,health_stop=health_stop,stopped=stopped,main_lock=main_lock,errors=errors,collect_main=collect_main)
 exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(watch)],type_ignores=[])),str(source),'exec'),context)
 worker=threading.Thread(target=context['watch_main'],name='actual-fast-pending-physical-watch',daemon=True)
 report={};code=1
 try:
  worker.start()
  while worker.is_alive():
   worker.join(.2)
   if time.monotonic()-started>=550:raise TimeoutError('Declared finite live observer bound')
  assert errors==[] and stopped.is_set()is False and len(accepted)>=40
  final=main_guard.finish(worker)
  for pin in job['inputs']:h.checked(pin)
  assert 'torch'not in __import__('sys').modules and 'numpy'not in __import__('sys').modules
  covered = len(samples)-len(accepted)>=job['pending_samples_required']
  report=dict(status='PASS_LIVE_PENDING_TRANSITION_WATCH_ENGINEERING' if covered else 'STABLE_LIVE_WATCH_COVERAGE_INSUFFICIENT_NO_PENDING',pending_branch_live_coverage=covered,physical_health_report=final,
   accepted_samples=len(accepted),pending_samples=len(samples)-len(accepted),all_existing_10s_overlap_15s_gap_and_process_TCP_cleanup_guards_retained=True,
   original_observer_thread_closed=True,models_or_actors_or_GPU_context_created=False,any_Main_control_changed=False)
  code=0
 except Exception:report=dict(status='FAILED_ORIGINAL_READONLY_FAST_PENDING_WATCH_ENGINEERING',error=traceback.format_exc(),errors=errors,accepted_samples=len(accepted),pending_samples=len(samples)-len(accepted))
 finally:
  health_stop.set();worker.join(12)
  if worker.is_alive():report.update(status='FAILED_OBSERVER_THREAD_NOT_CLOSED',original_observer_thread_closed=False);code=1
 report.update(original_job=jp,source=job['runtime'],elapsed_s=time.monotonic()-started,quality_qualified=False,promotion=False)
 result=h.put(Path(job['report']),report);print(json.dumps(dict(status=report['status'],report={k:result[k]for k in ['path','sha256','bytes']},accepted=report.get('accepted_samples'),pending=report.get('pending_samples'))),flush=True)
 return code

if __name__=='__main__':raise SystemExit(main())
