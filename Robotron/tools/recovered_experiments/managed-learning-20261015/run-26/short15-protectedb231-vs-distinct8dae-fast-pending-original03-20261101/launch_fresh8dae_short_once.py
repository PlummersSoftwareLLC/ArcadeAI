from pathlib import Path
import importlib.util,json,os,subprocess,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';F=B/'short15-protectedb231-vs-distinct8dae-fast-pending-original03-20261101'
spec=importlib.util.spec_from_file_location('_launchFresh8H',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
pp=h.pin(F/'prepared-with-review.json');p=json.loads(h.checked(pp).read_text());cp=p['controller_configs'];controller=p['selected_sources']['controller'];outer=p['selected_sources']['outer'];cpu=h.pin(F/'CPU-preflight-and-additional-cadence-contracts-original01.json');live=h.pin(F/'positive-live-preflight-original01.json');c=json.loads(h.checked(cpu).read_text());a=json.loads(h.checked(live).read_text());assert c['checks_total']==33 and c['prepared']==pp and a['prepared']==pp and a['bind_only_ports']['status']=='PORTS_FREE_BEFORE_LAUNCH'
for pin in [cp,controller,outer]:h.checked(pin)
argv=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','/usr/bin/python3','-I','-B',outer['path'],'--execute','--source-sha256',outer['sha256'],'--prepared',pp['path'],'--prepared-sha256',pp['sha256'],'--controller',controller['path'],'--controller-sha256',controller['sha256'],'--configs',cp['path'],'--configs-sha256',cp['sha256'],'--control',str(G/'html/next-policy-evaluation.json'),'--output',str(F/'Root-controller-runtime-original01')]
intent=h.put(F/'original-sequence-launch-intent.json',dict(argv=argv,prepared=pp,controller=controller,outer=outer,configs=cp,CPU_preflight=cpu,actual_preflight=live,original_attempt=1,no_retry=True,scientific_scores_from_prior_studies_reused=False,unix_s=time.time()))
stdout=F/'original-sequence-stdout.txt';stderr=F/'original-sequence-stderr.txt'
with stdout.open('xb')as out,stderr.open('xb')as err:
 child=subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True);birth=int(Path('/proc',str(child.pid),'stat').read_text().rsplit(')',1)[1].split()[19]);owner=h.put(F/'original-sequence-child.json',dict(pid=child.pid,birth=birth,observed_live=child.poll()is None,launch_intent=intent))
 print(json.dumps(dict(status='ORIGINAL_NEW_SHORT_SCREEN_OUTER_STARTED',pid=child.pid,birth=birth,owner={k:owner[k]for k in ['path','sha256','bytes']})),flush=True)
 while child.poll()is None:time.sleep(1)
 code=child.wait();out.flush();err.flush();os.fsync(out.fileno());os.fsync(err.fileno());os.fchmod(out.fileno(),0o444);os.fchmod(err.fileno(),0o444)
result=h.put(F/'original-sequence-actual-exit.json',dict(actual_exit=code,original_pid=child.pid,original_birth=birth,original_Popen_reaped=True,original_attempt=1,no_retry=True,launch_intent=intent,stdout=h.pin(stdout),stderr=h.pin(stderr),ended_unix_s=time.time()))
print(json.dumps(dict(status='ORIGINAL_NEW_SHORT_SCREEN_OUTER_CLOSED',actual_exit=code,result={k:result[k]for k in ['path','sha256','bytes']})),flush=True)
raise SystemExit(code)
