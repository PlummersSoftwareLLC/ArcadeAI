"""Read one original current-owner CPU contract result and actual lifecycle; no test rerun."""
from pathlib import Path
import hashlib,importlib.util,json,os,re,shlex,stat,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');C=Path(__file__).resolve().parent;H=C.parent

def ident(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
def pin(p):
 p=Path(p);a=ident(p.stat());b=p.read_bytes();assert ident(p.stat())==a
 return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=a)
def put(p,raw):
 with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 return pin(p)
def load(p,sha,name):
 p=Path(p);v=pin(p);assert v['sha256']==sha and v['identity']['mode']=='0o444';s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);assert pin(p)==v;return m

def main():
 out=C/'root-independent-readback.json';assert not out.exists() and not (C/'original-payload-archives').exists()
 runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_current_contract_runtime');reader=runtime.protector();control=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_current_contract_control')
 jp=pin(C/'job.json');assert jp['sha256']=='799cd91f40f9bc00c2b90ed9ba7a50b9ce230f868f1344954b90a1c6f3ae300a';job=reader.read_pin(jp);configp=pin(C/'CPU-controller-config.json');assert configp['sha256']=='5658ea4bdfea0d59004b6bdd8631ae694f90b5c15f62d9656b9aa742c9bc5632';config=reader.read_pin(configp)
 ownerp=pin(C/'controller-execution/root-original-identity.json');owner=reader.read_pin(ownerp);closurep=pin(C/'controller-execution/root-original-result-and-owned-release.json');assert closurep['sha256']=='c3a71ea67cde342cd98428a834d00933a2fcadee05348c47c0a749cfdaf41162';closure=reader.read_pin(closurep);fields=runtime.archived_closure(closure,owner,lambda e,as_json=True:reader.read_pin(e,as_json=as_json),exit_zero=True)
 assert runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30) and fields['MemorySwapMax']=='0' and runtime.duration_seconds(fields['RuntimeMaxUSec'])==180 and fields['TasksMax']=='256' and runtime.duration_seconds(fields['TimeoutStopUSec'])==5 and fields['Restart']=='no' and fields['SendSIGKILL']=='no'
 expected=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+config['argv'];m=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart']);assert m and shlex.split(m[1])==expected
 assert not Path('/proc',str(owner['pid'])).exists()
 for unit in [owner['unit'],owner['timer']]:assert control.show(unit)['LoadState']=='not-found'
 reportp=pin(C/'CPU-report.json');report=reader.read_pin(reportp);assert report['status']=='CURRENT_OWNER_HANDOFF_CONTRACTS_PASS' and report['tests_run']==18 and report['failures']==report['errors']==0 and report['mocked_OS_and_kernel_events'] is True and report['actual_private_kernel_freeze_and_rescue_still_required'] is True and report['tested_sources']==job['sources']
 assert pin(job['source']['path'])==job['source'];assert job['source']['sha256']=='a93e24ab7fe93298b35b4a87e84c89e262b1d02096280ce36049356564685488'
 for e in job['sources'].values():assert pin(e['path'])==e
 stderr=C/'controller-execution/stderr.txt';raw=stderr.read_bytes();assert re.search(rb'Ran 18 tests in [0-9.]+s',raw) and raw.rstrip().endswith(b'OK') and b'FAILED' not in raw
 A=C/'original-payload-archives';A.mkdir();payloads=[]
 for name in ['stdout.txt','stderr.txt']:
  p=C/'controller-execution'/name;original=pin(p);archive=put(A/name,p.read_bytes());assert archive['sha256']==original['sha256'] and pin(p)==original;payloads.append(dict(original=original,archive=archive))
 guard=load(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py','f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3','_current_contract_main_guard');prepared=reader.read_pin(job['current_prepared']);main=reader.read_pin(prepared['original_main']);guard.owner_and_files(main)
 result=dict(schema='profile06-current-owner-original18-CPU-contract-independent-readback-v1',status='ACTUAL_CURRENT_OWNER_HANDOFF_18_CPU_CONTRACTS_PASS',observed_unix_s=time.time(),source=pin(Path(__file__)),original_test_source=job['source'],original_job=jp,original_controller_config=configp,original_owner=ownerp,original_closure=closurep,actual_original_exit=0,all6_original_descriptors_and_exact_release_verified=True,actual_descriptor_exits=[v['exit'] for v in closure['full_original_archives']],CPU_report=reportp,tested_sources=job['sources'],tests=18,failures=0,errors=0,payload_archives=payloads,mocked_external_OS_and_kernel_events=True,actual_private_kernel_freeze_and_rescue_still_required=True,current_main_binding=prepared['original_main'],current_main195_holds_and_original192_verified=True,production_source_control_or_model_changed=False,live_controller_selected=False,original_test_retried=False,quality_qualified=False,promotion=False,learning_speed_gain_verified=False)
 assert 'torch' not in sys.modules;rp=put(out,(json.dumps(result,indent=2)+'\n').encode());print(json.dumps(dict(readback=rp,status=result['status'],tests=18,actual_original_exit=0,private_kernel_test_still_required=True)))
if __name__=='__main__':
 if sys.argv[1:]==['--observe']:main()
 else:print('PLAN_ONLY: original completed CPU evidence only; no tests or live actions')
