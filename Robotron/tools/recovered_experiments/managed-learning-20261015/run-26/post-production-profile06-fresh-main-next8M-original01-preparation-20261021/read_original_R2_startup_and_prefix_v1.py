"""Once-only passive original R2 startup prefixes; no scientific qualification."""
from pathlib import Path
import hashlib,importlib.util,json,os,re,stat,subprocess,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=R/'post-production-profile06-fresh-main-next8M-original01-preparation-20261021';Q=R/'quality32-reference1597-vs-production1741-original01-preparation-20261021';C=R.parent/'quality-reference1597M-vs-production1741M-profile06-quality32-original01-20261021';D=Q/'R2-original-startup-prefix-readback-original01'
FOUND={'952bea55':'80f51d8e7ec62518afad7e56a47e0756f83f813c','4c05fd3c':'0d727458454826fd8222e4022b755d686ccb065f','e8238019':'0ce29f4bf6bdee677c8e80c2d5e66fc556ba349f','827cb5c9':'1732d16cd88e0662f1cffce1aeda5c8aa8c31338','3ecf4620':'3c670a1f8df35d18451c82f220a02448bf5ef5ac','752d7a46':'85dd58d14d527ca75d6c546d6271bf8ee5a82c8c'}
def load(path,sha,name):
 assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','_R2_startup_reader');pin=reader.pin;read=lambda e:reader.read_pin(e)
 regpin=pin(Q/'root-live-monitor-registration.json');reg=read(regpin);observed=subprocess.run(reg['command'],capture_output=True);assert observed.returncode==0,observed.stderr.decode();report=json.loads(observed.stdout);assert report['classification']=='LIVE_SUPERVISED_QUALITY32_PREFIX_VERIFIED' and report['current_leg']==3 and all(x['live']for x in report['original_owners']) and report['legs'][2]['verified_actor_births']==report['legs'][2]['live_actor_births_verified']==32 and report['main']['client_count']==192
 bp=pin(Q/'runtime-bindings/leg-births/leg3-actors.json');actors=read(bp);assert set(actors)==set(map(str,range(4096,4128)))
 D.mkdir(mode=0o700)
 def put(path,raw):
  with path.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
  return pin(path)
 def enc(o):return(json.dumps(o,indent=2)+'\n').encode()
 def ident(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
 def prefix(path,name,limit):
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb')as f:
   before=ident(os.fstat(f.fileno()));assert before['uid']==os.getuid() and before['nlink']==1
   raw=f.read(min(limit,before['bytes']));after=ident(os.fstat(f.fileno()));f.seek(0);repeat=f.read(len(raw))
  assert repeat==raw and before['device']==after['device'] and before['inode']==after['inode'] and after['bytes']>=len(raw)
  return raw,dict(original_path=str(path),observed_before=before,observed_after=after,byte_range=[0,len(raw)],copy=put(D/name,raw),original_prefix_reread_identical=True,original_producer_mutated=False)
 logs=[]
 for slot in sorted(actors,key=int):
  raw,evidence=prefix(C/'03-reference/actors'/slot/'console.log','actor-'+slot+'-startup-prefix.log',65536);text=raw.decode();found=dict(re.findall(r'FOUND: CRC\(([0-9a-f]+)\) SHA1\(([0-9a-f]+)\)',text));assert found==FOUND
  for textpart in ['[PATCH] RRCHRIS runtime ROM patch disabled.','Robotron socket target: socket.127.0.0.1:9999','Robotron socket wait: socket readiness wait 1000us, host wall timers','Robotron eval override: EVAL (greedy, wave-1)','[DIFFICULTY] GA1 poked to 5']:assert textpart in text,(slot,textpart)
  assert re.search(r'\[robotron-socket-wait\] pid='+str(actors[slot]['pid'])+r' fd=\d+ port=9999 interval_us=1000',text)
  assert not any(t in text for t in ['[SOCKET ACTION TIMEOUT]','ERROR: Failed to','Segmentation fault'])
  logs.append(dict(slot=int(slot),original_actor_birth=actors[slot],startup=evidence,ROM_found_checksums=found,expected_runtime_banner=True))
 raw,statuspin=prefix(C/'03-reference/status.json','original-evaluator-status.snapshot.json',262144);status=json.loads(raw);assert status['phase']=='collecting' and status['complete'] is False and status['boundary']['ready'] is True and status['boundary']['acknowledged']==32 and status['boundary']['required_actor_slots']==list(range(4096,4128))
 assert status['checkpoint_sha256']=='c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c' and status['clocks']['learner_frame_count']==1597432474
 lp=C/'03-reference/journal/lives.jsonl';raw,lifepin=prefix(lp,'original-life-journal.prefix.jsonl',1048576);rows=[json.loads(x)for x in raw.splitlines()[:-1] if x];assert rows and all(x['eval_only'] is True and x['context']['epsilon']==x['context']['expert_ratio']==0 and x['context']['learner_frames']==1597432474 and x['context']['difficulty']==5 for x in rows)
 output=dict(status='ORIGINAL_R2_ALL32_STARTUP_ROM_BANNERS_AND_BOUNDARY_PREFIX_PASS',observed_unix_s=time.time(),source=pin(Path(__file__)),monitor_registration=regpin,monitor_report=report['receipt'],original_actor_registry=bp,all32_current_original_births_verified=True,startup_logs=logs,eval_status=statuspin,boundary_acknowledged=32,original_life_prefix=lifepin,complete_life_rows_checked=len(rows),prefix_slots=sorted({x['client_slot']for x in rows}),admitted_game_snapshot=dict(started=status['started'],completed=status['count'],pending=status['pending'],abandoned=status['abandoned']),main=report['main'],ROM_scope='Six distinguishing startup FOUND CRC/SHA1 pairs and disabled runtime patch banners; final original complete-game ROM audit remains mandatory',quality_qualified=False,promotion=False,scientific_audit_rerun=False,learning_speed_gain_verified=False,runtime_changed=False)
 receipt=put(Q/'R2-original-startup-prefix-independent-readback.json',enc(output));print(json.dumps(dict(status=output['status'],receipt=receipt,life_rows=output['complete_life_rows_checked'],snapshot=output['admitted_game_snapshot'],main=output['main'])))
if __name__=='__main__':main()
