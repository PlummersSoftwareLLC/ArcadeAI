import datetime,hashlib,json,os,pathlib,resource,subprocess,time
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron'); R=G/'logs/managed-learning-20261015/run-26'; C=G/'logs/managed-learning-20261015/quality-256M-vs-384M-20261017'
AF=R/'quality384M-actual-launch-plan-independent-review-20261017/future-leg-audit-argv.json'
AH='a38301935e5a19dbc2c3b19daf9288ac2721adffe71f495dc79bfe94c0abf444'; PH='81210cb86ad7cd78b3f9a7f4c764b83aad3364d0d8f0e382e29f340245a54704'; SH='47debecaf6a851d00b7d8717cdb342a9b551fe197e659a0c04594195412f7044'; CH='3765ad86e89952c409709e9dd5611f1a0242051c3dd67c800004b73a823b5611'
def sha(b): return hashlib.sha256(b).hexdigest()
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def emit(p,b):
 with p.open('xb') as f: f.write(b); f.flush(); os.fsync(f.fileno())
 p.chmod(0o444)
def js(p,d): emit(p,(json.dumps(d,sort_keys=True,indent=2)+'\n').encode())
ab=AF.read_bytes(); assert sha(ab)==AH
cmd=next(c for c in json.loads(ab)['commands'] if c['leg']==3); argv=cmd['argv']; out=pathlib.Path(cmd['output']); src=pathlib.Path(argv[argv.index('/usr/bin/python3')+3]); proof=pathlib.Path(argv[argv.index('--cpu-proof')+1])
assert sha(src.read_bytes())==SH and sha((C/'plan.json').read_bytes())==PH and sha(proof.read_bytes())==CH
sb=(C/'status.json').read_bytes(); s=json.loads(sb); leg=s['legs'][2]; assert s['plan_sha256']==PH and leg['index']==3 and leg['role']=='reference' and leg['pid']==3835744 and leg['state']=='finished' and leg['returncode']==0
rp=pathlib.Path(leg['receipt_path']); rb=rp.read_bytes(); d=json.loads(rb); co=d['cohort']
assert d['active'] is False and d['complete'] is True and d['valid'] is True and d['phase']=='complete'
assert co['closed'] is True and co['complete'] is True and co['valid'] is True and co['pending']==0 and co['abandoned']==0 and co['started']==co['count']==d['count']>=50
assert d['pending']==d['abandoned']==0 and not d['cleanup_errors'] and not d['invalidity_reasons'] and all(row['complete'] is True for row in d['rows'])
stat=pathlib.Path('/proc/3723673/stat').read_text(); ticks=int(stat.rsplit(') ',1)[1].split()[19]); assert ticks==30468106
ub=subprocess.check_output(['systemctl','--user','show','robotron-quality-256M-vs-384M-20261017.service','--property=MainPID,InvocationID,SubState'],text=True); unit=dict(x.split('=',1) for x in ub.splitlines() if '=' in x)
assert unit=={'MainPID':'3723673','InvocationID':'611d7a54ae7e4a649b0e1ed3505a7baa','SubState':'running'}
ex=R/'quality384M-reference02-auditor-execution-reviewed1-20261017'; assert not ex.exists() and not out.exists(); ex.mkdir()
for name,b in [('precondition-campaign-status.json',sb),('precondition-original-receipt.json',rb),('original-unit-show.txt',ub.encode())]: emit(ex/name,b)
limits={'address_space_bytes':512*1024*1024,'cpu_s':30,'file_bytes':32*1024*1024,'wall_s':90}
js(ex/'execution-precommit.json',{'schema':'robotron384-original-leg-auditor-execution-v1','utc':utc(),'leg':3,'argv':argv,'output':str(out),'prepared_argv_sha256':AH,'source_sha256':SH,'plan_sha256':PH,'cpu_proof_sha256':CH,'root_conditional_GO':'Explicit root authorization only after finished0/inactive/fulltails/cleanup; conditions satisfied','original_controller':unit,'controller_start_ticks':ticks,'precondition_status_sha256':sha(sb),'precondition_receipt_sha256':sha(rb),'no_retry':True,'limits':limits})
fd=os.open(ex,os.O_RDONLY|os.O_DIRECTORY); os.fsync(fd); os.close(fd)
def cap():
 resource.setrlimit(resource.RLIMIT_AS,(limits['address_space_bytes'],limits['address_space_bytes'])); resource.setrlimit(resource.RLIMIT_CPU,(30,30)); resource.setrlimit(resource.RLIMIT_FSIZE,(limits['file_bytes'],limits['file_bytes'])); resource.setrlimit(resource.RLIMIT_CORE,(0,0))
start=time.monotonic(); rc=None; failure=None; reaped=False
with (ex/'stdout.log').open('xb') as so,(ex/'stderr.log').open('xb') as se:
 try:
  child=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=so,stderr=se,check=False,timeout=90,preexec_fn=cap); rc=child.returncode; reaped=True
 except BaseException as error:
  failure=type(error).__name__+': '+str(error); reaped=isinstance(error,subprocess.TimeoutExpired)
 for f in (so,se): f.flush(); os.fsync(f.fileno())
for p in (ex/'stdout.log',ex/'stderr.log'): p.chmod(0o444)
rr=out/'review-receipt.json'; result={'schema':'robotron384-original-leg-auditor-completion-v1','utc':utc(),'leg':3,'original_exit':rc,'child_reaped':reaped,'elapsed_s':time.monotonic()-start,'failure':failure,'stdout_sha256':sha((ex/'stdout.log').read_bytes()),'stderr_sha256':sha((ex/'stderr.log').read_bytes()),'source_unchanged':sha(src.read_bytes())==SH,'plan_unchanged':sha((C/'plan.json').read_bytes())==PH,'review_receipt_path':str(rr),'review_receipt_sha256':sha(rr.read_bytes()) if rr.is_file() else None,'retries':0,'qualification_pass':False,'production_applied':False}
js(ex/'execution-completion.json',result); fd=os.open(ex,os.O_RDONLY|os.O_DIRECTORY); os.fsync(fd); os.close(fd)
print(json.dumps({'completion':result,'execution_receipt_sha256':sha((ex/'execution-completion.json').read_bytes())},indent=2))
