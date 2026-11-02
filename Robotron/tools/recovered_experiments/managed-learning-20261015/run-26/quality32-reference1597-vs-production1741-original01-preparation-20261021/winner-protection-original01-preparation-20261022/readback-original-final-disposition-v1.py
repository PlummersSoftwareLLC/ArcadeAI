"""Read original closed evidence and current holds before new protection; never rerun scientific review."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,os,stat,sys,time,urllib.request
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');P=Path(__file__).resolve().parent;Q=P.parent
JOB_SHA='4f1cc362f55b5a549da103e75a48b5589b084a54a92dc4b62c8ca1eee2cfcbd9'
def ident(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
def pin(p):
 p=Path(p);a=ident(p.stat());b=p.read_bytes();assert ident(p.stat())==a
 return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=a)
def put(p,raw):
 with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 return pin(p)
def load(p,sha,name):
 p=Path(p);before=pin(p);assert before['sha256']==sha and before['identity']['mode']=='0o444'
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);assert pin(p)==before;return m

def main(args):
 output=P/'root-final-disposition-readback.json';assert not output.exists()
 jp=pin(P/'job.json');assert jp['sha256']==JOB_SHA
 protector=load(G/'tools/quality_capacity_proposal/protect_quality32_winner_v7.py','4553ac74264021885db2f343992ccd9bf615c066b424e1be2ecc030d580b1c27','_final_disposition_protector')
 reader=protector.reader_module();job=reader.read_pin(jp);checked=protector.verify(job,jp,reader)
 runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_final_disposition_runtime')
 control=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_final_disposition_control')
 preserved=[jp,job['independent_C2_closed_readback'],job['independent_separate_candidate_gate_readback']]
 numerical=reader.read_pin(job['independent_separate_candidate_gate_readback']);assert numerical['both_independent_numerical_gates_passed'] and numerical['fixed_reference']['count']==138
 assert [v['count'] for v in numerical['candidate_confirmations']]==[65,64]
 for original,other in zip(checked['assessment']['individual_candidate_checks'],numerical['candidate_confirmations']):assert original['index']==other['leg_index'] and original['mean']==other['mean']['value'] and original['median']==other['median']['value'] and original['mean_pass'] is original['median_pass'] is True
 mp=pin(args.monitor_path);assert mp['sha256']==args.monitor_sha256 and Path(mp['path']).parent==Q/'root-live-monitor'
 monitor=reader.read_pin(mp);assert monitor['classification']=='ORIGINAL_NATIVE_TERMINAL_AWAITING_FINAL_DISPOSITION' and time.time()-monitor['unix_s']<600 and monitor['main']['client_count']==192 and monitor['published_main_recoveries']==0
 assert all(not v['live'] and v['actual_exit']==0 for v in monitor['original_owners']) and [v['counts']['count'] for v in monitor['legs']]==[70,65,68,64]
 preserved.append(mp);lifecycles=[]
 specs=[('native',job['original_native_owner'],job['original_native_closure'],12,12<<30,36600,512,120),('review',job['review_owner'],job['review_closure'],2,4<<30,180,256,5),('outer',job['original_outer_owner'],job['original_outer_closure'],2,1<<30,37800,256,180)]
 for label,op,cp,cpu,memory,maximum,tasks,stop in specs:
  owner=reader.read_pin(op);closure=reader.read_pin(cp);fields=runtime.archived_closure(closure,owner,lambda v,as_json=True:reader.read_pin(v,as_json=as_json),exit_zero=True)
  assert runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==cpu and fields['MemoryMax']==str(memory) and fields['MemorySwapMax']=='0' and runtime.duration_seconds(fields['RuntimeMaxUSec'])==maximum and fields['TasksMax']==str(tasks) and runtime.duration_seconds(fields['TimeoutStopUSec'])==stop and fields['Restart']=='no' and fields['SendSIGKILL']=='no'
  assert not Path('/proc',str(owner['pid'])).exists()
  for unit in [owner['unit'],owner['timer']]:assert control.show(unit)['LoadState']=='not-found'
  cgroup=owner.get('cgroup','/user.slice/user-1001.slice/user@1001.service/app.slice/'+owner['unit']);assert not Path('/sys/fs/cgroup'+cgroup).exists()
  descriptors=closure.get('full_original_archives',closure.get('native_archives'));assert len(descriptors)==6
  full8=[pin(row[channel]['path']) for row in descriptors for channel in ['stdout','stderr']]
  lifecycles.append(dict(kind=label,owner=op,closure=cp,actual_exit=0,all6_original_descriptors_verified=True,actual_descriptor_exits=[r['exit'] for r in descriptors],full8_descriptor_files=full8,exact_service_and_timer_absent=True,original_birth_and_cgroup_absent=True,original_resource_scope_verified=True))
  preserved.extend([op,cp,*full8])
 native=reader.read_pin(job['original_native_owner'])
 for leg in [1,2,3,4]:
  ap=pin(Q/f'runtime-bindings/leg-births/leg{leg}-actors.json');actors=reader.read_pin(ap);runtime.verify_cleanup(native,actors,'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0',Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock'));preserved.append(ap)
 wire=urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=12).read();api=json.loads(wire)
 assert api['client_count']==192 and api['training_enabled'] is True and api['lr']==1.25e-5 and all(math.isfinite(api[k]) for k in ['loss','grad_norm','q_mean']) and api['bank_persistence']['write_failures']==0 and not api['pipeline_read_error'] and not api['bank_persistence_read_error']
 latest=G/'models_dqn/robotron_dqn_latest.pt';autosave_age=time.time()-latest.stat().st_mtime;assert 0<=autosave_age<=360
 for v in preserved:assert pin(v['path'])==v
 assert 'torch' not in sys.modules
 ap=put(P/'root-final-disposition-main-API.raw.json',wire)
 report=dict(schema='profile06-original-full-final-disposition-readback-v1',status='PASS_ORIGINAL_REVIEW_ALL3_LIFECYCLES_CLEANUP_AND_MAIN_HOLDS',observed_unix_s=time.time(),source=pin(Path(__file__)),protection_job=jp,monitor=mp,original_protection_evidence_verification=dict(assessment=checked['assessment'],candidate_source=checked['candidate_source'],source_package=checked['source_package'],original_scientific_audit_rerun=checked['original_scientific_audit_rerun']),separate_candidate_gate_readback=job['independent_separate_candidate_gate_readback'],independent_C2_closed_readback=job['independent_C2_closed_readback'],original_lifecycles=lifecycles,all4_original_actor_sets_cleanup_verified=True,private_GPU0_and_port9999_idle_and_lease_released=True,main192_and_196_frozen_holds_verified_by_registered_monitor=True,main_API_raw=ap,main_learner_frames=api['learner_frame_count'],main_training_steps=api['training_steps'],bank_write_failures=0,latest_autosave_age_s=autosave_age,quality_qualified=True,promotion=False,publication_executed=False,original_review_rerun=False,learning_speed_gain_verified=False,main_runtime_changed=False)
 rp=put(output,(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(dict(readback=rp,status=report['status'],quality_qualified=True,promotion=False)))
if __name__=='__main__':
 if '--observe' in sys.argv[1:]:
  parser=argparse.ArgumentParser();parser.add_argument('--observe',action='store_true');parser.add_argument('--monitor-path',type=Path,required=True);parser.add_argument('--monitor-sha256',required=True);main(parser.parse_args())
 else:print('PLAN_ONLY: explicit source-bound monitor required; no review rerun or publication')
