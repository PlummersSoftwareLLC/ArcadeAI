"""Passive fixed closed-admission membership joins for one live original C2; no audit rerun."""
from pathlib import Path
import hashlib,importlib.util,json,os,stat,subprocess,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';Q=R/'quality32-reference1597-vs-production1741-original01-preparation-20261021';C=R.parent/'quality-reference1597M-vs-production1741M-profile06-quality32-original01-20261021';D=Q/'C2-original-closed-admissions-readback-original01'
def main():
 path=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py';assert hashlib.sha256(path.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071';s=importlib.util.spec_from_file_location('_first_C2_admit_reader',path);reader=importlib.util.module_from_spec(s);s.loader.exec_module(reader);pin=reader.pin
 registration=reader.read_pin(pin(Q/'root-live-monitor-registration.json'));r=subprocess.run(registration['command'],capture_output=True);assert r.returncode==0,r.stderr.decode();observed=json.loads(r.stdout);assert observed['classification']=='LIVE_SUPERVISED_QUALITY32_PREFIX_VERIFIED' and all(x['live']for x in observed['original_owners']) and observed['current_leg']==4 and observed['legs'][3]['verified_actor_births']==32
 D.mkdir(mode=0o700)
 def ident(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
 def put(p,raw):
  with p.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
  return pin(p)
 def prefix(path,name):
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb')as f:
   a=ident(os.fstat(f.fileno()));assert a['uid']==os.getuid() and a['nlink']==1 and a['bytes']<=1<<20
   raw=f.read(a['bytes']);b=ident(os.fstat(f.fileno()));f.seek(0);assert f.read(len(raw))==raw and a['device']==b['device'] and a['inode']==b['inode']
  return raw,dict(original_path=str(path),observed_before=a,observed_after=b,byte_range=[0,len(raw)],readonly_copy=put(D/name,raw),original_prefix_reread_identical=True,original_producer_changed=False)
 wire,status_evidence=prefix(C/'04-candidate/status.json','original-status.snapshot.json');status=json.loads(wire);cohort=status['cohort'];assert status['phase']=='draining' and status['checkpoint_sha256']=='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83' and status['boundary']['acknowledged']==32
 assert cohort['started']>=32 and set(cohort['started_actor_slots'])==set(range(4096,4128)) and cohort['closed'] and cohort['start_ts']==1792648130.7147546 and cohort['close_ts']==1792653530.7147546
 raw,start_evidence=prefix(C/'04-candidate/journal/measurement_starts.jsonl','original-measurement-starts.prefix.jsonl');end=raw.rfind(b'\n')+1;all_rows=[json.loads(line)for line in raw[:end].splitlines()];rows=[row for row in all_rows if cohort['start_ts']<=row['start_unix_s']<=cohort['close_ts']];assert len(rows)>=32
 ids=set();joins=[]
 for row in rows:
  uid=row['journal_game_id'];assert uid not in ids;ids.add(uid);x=row['context'];c=x['game_boundary_diagnostics']
  assert row['known_start'] is True and row['measurement_active'] is True and row['measurement_generation']==status['generation']==1 and row['experiment']==x['experiment']==status['label']
  assert cohort['start_ts']<=row['start_unix_s']<=cohort['close_ts'] and row['client_slot'] in range(4096,4128)
  assert x['learner_frames']==1741229950 and x['training_steps']==7128160 and x['optimized_samples']==27621148672 and x['epsilon']==x['expert_ratio']==0 and x['difficulty']==5 and x['ratchet_frozen'] is False and x['complete_game_boundary_policy']=='confirmed_reset_reserves_v1'
  assert c['classifier_verdict']=='accept' and row['start_reason'] in ('score_reset','zero_score_restart')
  joins.append(dict(journal_game_id=uid,slot=row['client_slot'],client_id=row['client_id'],start_unix_s=row['start_unix_s'],known_start=True,current_generation=True,frozen_candidate_context=True,in_fixed_window=True,in_captured_status_membership=uid in cohort['started_ids']))
 common=set(cohort['started_ids'])&ids;assert len(common)>=32 and ids==set(cohort['started_ids'])
 assert {row['client_slot']for row in rows if row['journal_game_id']in common}==set(range(4096,4128))
 result=dict(status='ORIGINAL_C2_FIXED_CLOSED_ADMISSION_MEMBERSHIP_PREFIX_JOIN_PASS',observed_unix_s=time.time(),source=pin(Path(__file__)),original_monitor_report=observed['receipt'],original_status=status_evidence,original_measurement_start_prefix=start_evidence,complete_start_rows_in_prefix=len(all_rows),in_window_start_rows=len(rows),out_of_window_start_ids=[row['journal_game_id']for row in all_rows if not cohort['start_ts']<=row['start_unix_s']<=cohort['close_ts']],admission_membership_frozen=True,completed_and_pending_counts_are_snapshot_not_exact_cutoff=True,minimum50_possible=cohort['started']>=50,joined_snapshot_ids=sorted(common),start_rows=joins,cohort_snapshot={k:cohort[k]for k in ['started','count','pending','abandoned','started_actor_slots']},main=observed['main'],scope='Fixed admission is closed and the complete in-window original start journal membership equals the frozen status membership, covering all32 slots. Completed/pending counts are the later captured snapshot, not exact-cutoff counts. Every admitted game/full tail, minimum50 complete games, original first-play/terminal/ROM/runtime evidence and both independent candidate gates remain required.',all32_original_private_births_live=True,all196_main_holds_and192_actors_verified=True,full_tails_still_required=True,quality_qualified=False,promotion=False,scientific_audit_rerun=False,runtime_changed=False)
 receipt=put(Q/'C2-original-closed-admissions-independent-readback.json',(json.dumps(result,indent=2)+'\n').encode());print(json.dumps(dict(status=result['status'],receipt=receipt,joined_snapshot_ids=result['joined_snapshot_ids'],snapshot=result['cohort_snapshot'],main=result['main'])))
if __name__=='__main__':main()
