import pathlib,json,hashlib,subprocess,time,os,datetime,shutil,ast
ROOT=pathlib.Path('/home/dave/source/repos/ArcadeAI');R=ROOT/'Robotron/logs/managed-learning-20261015/run-26';D=ROOT/'Robotron/tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/revision2';J=R/'recomputed-capture-private-CPU20-reviewed2-20261017'
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 p.chmod(0o444)
def run(a):
 q=subprocess.run(a,text=True,capture_output=True);return dict(argv=a,code=q.returncode,stdout=q.stdout,stderr=q.stderr)
def props():
 q=run(['systemctl','--user','show',U]);return q,dict(l.split('=',1) for l in q['stdout'].splitlines() if '=' in l)
manifest=D/'manifest-source-review-v2.json';assert sha(manifest)=='356b8b0999b05d3d4cd6e2addfcbee832c7365c9c31f9c08506f8714c0dfeaa2';m=json.loads(manifest.read_text());PINS={str(D/n):v['sha256'] for n,v in m['files'].items()};PINS[str(manifest)]=sha(manifest)
lock=json.loads((D/'source-lock.json').read_text())
for v in lock['base'].values():PINS[v['path']]=v['sha256']
for v in lock['reused_byte_identical'].values():PINS[v['path']]=v['sha256']
v=lock['source_fixture_whole_step'];PINS[v['path']]=v['sha256']
K=ROOT/'Robotron/tools/kl_priority_mixture_proposal';old=K/'executed_trace_proposal';oldmanifest=old/'manifest.json';assert sha(oldmanifest)=='d7fcb2e36a7b08d472341d8f7f294d384f2591f17225832da83d350bff4e3316';oldm=json.loads(oldmanifest.read_text());PINS[str(oldmanifest)]=sha(oldmanifest)
for n,h in oldm['overlay_sha256'].items():PINS[str(old/n)]=h
fixture=K/'sampler_fixture.py';assert sha(fixture)=='10872d08f11556bff08031b0265fc488347be717e5e2a91ff84fcf461ce298e8';PINS[str(fixture)]=sha(fixture)
assigns={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(fixture.read_text()).body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('PINS','CANDIDATE_SHA256')}
for n,h in assigns['PINS'].items():PINS[str(ROOT/'Robotron/Scripts/dqn'/n)]=h
PINS[str(K/'replay_buffer_candidate.py')]=assigns['CANDIDATE_SHA256']
peer=R/'recomputed-ce-capture-revision2-scientific-source-peer-review-20261017/review-receipt.json';assert sha(peer)=='1ace803b071e964fea264b89950a700b1ba280393ac2bf9e8df106d931a5d4fc';PINS[str(peer)]=sha(peer)
def verify():
 for p,h in PINS.items():assert sha(p)==h,p
 for n in m['files']:assert not ((D/n).stat().st_mode&0o222),n
verify();J.mkdir();(J/'private-tmp').mkdir();(J/'bound-source').mkdir();shutil.copyfile(__file__,J/'root-controller-source.py')
for index,(name,h) in enumerate(PINS.items()):target=J/'bound-source'/('%02d-'%index+pathlib.Path(name).name);shutil.copyfile(name,target);target.chmod(0o444)
python=str(ROOT/'.venv-gb300/bin/python')
selection="import importlib.util,sys,unittest; p=sys.argv[1]; s=importlib.util.spec_from_file_location('private_recomputed_whole_selected',p); m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m); suite=unittest.defaultTestLoader.loadTestsFromTestCase(m.WholeRecomputedCaptureTests); assert suite.countTestCases()==6; result=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(0 if result.wasSuccessful() else 1)"
commands=[[python,'-Xgil=0','-I','-B',str(D/'test_recomputed_capture.py'),'-v'],[python,'-Xgil=0','-I','-B','-c',selection,str(D/'test_whole_training_capture.py')]]
runner=J/'runner.py';runner.write_text('import json,subprocess,pathlib,time,sys\nJ=pathlib.Path('+repr(str(J))+')\ncommands='+repr(commands)+'\nresults=[]\nfor index,argv in enumerate(commands):\n with (J/(str(index)+".stdout")).open("x") as out,(J/(str(index)+".stderr")).open("x") as err:\n  started=time.monotonic(); q=subprocess.run(argv,stdout=out,stderr=err,timeout=110)\n result=dict(index=index,argv=argv,returncode=q.returncode,elapsed_s=time.monotonic()-started); results.append(result)\n with (J/(str(index)+".completion.json")).open("x") as f: json.dump(result,f,indent=2)\n if q.returncode: sys.exit(q.returncode)\nwith (J/"children-completion.json").open("x") as f:json.dump(dict(status="PASS",results=results),f,indent=2)\n')
U='robotron-recomputed-capture-private-cpu20-reviewed2-20261017.service';_,p=props();assert p.get('LoadState')=='not-found'
argv=['systemd-run','--user','--unit='+U,'--property=WorkingDirectory='+str(ROOT),'--property=Restart=no','--property=RemainAfterExit=yes','--property=CollectMode=inactive','--property=MemoryMax=3G','--property=MemorySwapMax=0','--property=CPUQuota=200%','--property=TasksMax=128','--property=RuntimeMaxSec=120s','--property=StandardOutput=append:'+str(J/'console.log'),'--property=StandardError=inherit','/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','MKL_NUM_THREADS=2','NUMEXPR_NUM_THREADS=2','ROBOTRON_ALLOW_WHOLE_STEP_CPU=1','ROBOTRON_ALLOW_RECOMPUTED_WHOLE_CPU=1','TMPDIR='+str(J/'private-tmp'),python,'-Xgil=0','-I','-B','-u',str(runner)]
write(J/'execution-precommit.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),unit=U,argv=argv,commands=commands,source_pins=PINS,source_manifest_sha256=sha(manifest),root_and_scientific_source_review=True,synthetic_tests=dict(observer_AST=14,explicit_whole_training_class=6),selection_note='Select exact new6-method class; global importedBase TestCase is excluded intentionally, no sealed source change',checkpoint_wait_stays_active=True,hard_memory_bytes=3*2**30,private_disk_poll_budget=256*2**20,scope='Synthetic private CPU miniature model, real4096x8 replay/prefetch/original4loss/Adam/exposure; CPU scaler branch adapters explicitly not CUDA; no checkpoint/model/replay data loaded'))
q=run(argv);write(J/'launch-result.json',q);assert q['code']==0,q
start=time.monotonic();inv=None;peak=0
while True:
 sh,p=props()
 if inv is None and p.get('InvocationID'):
  inv=p['InvocationID'];write(J/'initial-owner.json',dict(invocation_id=inv,pid=p.get('MainPID'),ExecMainPID=p.get('ExecMainPID'),start_monotonic=p.get('ExecMainStartTimestampMonotonic')))
 if inv:assert p.get('InvocationID')==inv
 size=sum(f.stat().st_size for f in J.rglob('*') if f.is_file());peak=max(peak,size)
 if size>256*2**20:
  write(J/'disk-budget-failure.json',dict(bytes=size,limit=256*2**20,invocation=inv));run(['systemctl','--user','stop',U]);raise AssertionError('Owned disk budget exceeded')
 if p.get('SubState') in ('exited','failed','dead') and p.get('ExecMainPID') not in (None,'0'):break
 assert time.monotonic()-start<125
 time.sleep(.25)
write(J/'original-terminal-show.json',sh);write(J/'original-unit-cat.json',run(['systemctl','--user','cat',U]));write(J/'original-invocation-journal.json',run(['journalctl','--user','--no-pager','-o','json','_SYSTEMD_INVOCATION_ID='+inv]));verify()
passed=p['ExecMainCode']=='1' and p['ExecMainStatus']=='0'
for index,count in [(0,14),(1,6)]:
 log=(J/(str(index)+'.stderr')).read_text() if (J/(str(index)+'.stderr')).exists() else '';passed=passed and ('Ran '+str(count)+' tests') in log and log.rstrip().endswith('OK')
write(J/'execution-completion.json',dict(status='PASS' if passed else 'FAIL',actual_exit=int(p['ExecMainStatus']),invocation_id=inv,elapsed_s=time.monotonic()-start,memory_peak=p.get('MemoryPeak'),private_disk_observed_peak=peak,source_pins_unchanged=True,original_exit_archived_before_release=True,synthetic_tests=20 if passed else None))
if not passed:
 print(json.dumps(dict(status='FAIL',unit=U,invocation=inv,job=str(J),original_exit=p['ExecMainStatus'])));raise SystemExit(1)
release=run(['systemctl','--user','stop',U]);write(J/'owned-unit-release.json',release);_,after=props();assert after.get('LoadState')=='not-found';f=J/'root-result-review-and-release.json';write(f,dict(status='PASS_PRIVATE_CPU14_PLUS_WHOLE_IMPLEMENTATION6',synthetic_tests_passed=20,original_exit=0,invocation_id=inv,owned_unit_released=True,source_pins=PINS,source_manifest_sha256=sha(manifest),qualification_pass=False,production_applied=False,scope='Real private CPU replay/prefetch/full training/original4loss/Adam/exposure; tiny8-wide model, no actual torch.compile/CUDA/GB300/agent constructor/learning or quality proof',completion_sha256=sha(J/'execution-completion.json')));print(json.dumps(dict(status='PASS',root_review=str(f),root_review_sha256=sha(f),invocation=inv,memory_peak=p.get('MemoryPeak'),disk_peak=peak,seconds=time.monotonic()-start)))
