"""Passive first measured R1 game/start/life/terminal joins, no scientific audit."""
from pathlib import Path
import hashlib,importlib.util,json,os,stat,subprocess,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=R/'post-production-profile06-fresh-main-next8M-original01-preparation-20261021';Q=R/'quality32-reference1597-vs-production1741-original01-preparation-20261021';C=R.parent/'quality-reference1597M-vs-production1741M-profile06-quality32-original01-20261021';D=Q/'R1-original-first-completed-game-readback-original01'
def main():
 path=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py';assert hashlib.sha256(path.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071';s=importlib.util.spec_from_file_location('_first_R1_complete_reader',path);reader=importlib.util.module_from_spec(s);s.loader.exec_module(reader);pin=reader.pin
 reg=reader.read_pin(pin(Q/'root-live-monitor-registration.json'));run=subprocess.run(reg['command'],capture_output=True,timeout=30);assert run.returncode==0,run.stderr.decode();monitor=json.loads(run.stdout);assert monitor['classification']=='LIVE_SUPERVISED_QUALITY32_PREFIX_VERIFIED' and all(x['live']for x in monitor['original_owners']) and monitor['current_leg']==1 and monitor['legs'][0]['counts']['count']>=1
 pre=reader.read_pin(pin(P/'reference1597-tested-quality-precommit.json'));assert pre['source_package']['sha256']=='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e';package=reader.read_pin(pre['source_package']);helper=pin(Path(package['root'])/'tools/confirmed_terminal_evidence.py');assert helper['sha256']==package['files']['tools/confirmed_terminal_evidence.py'];terminal=reader.checked_module('_first_R1_complete_terminal_pure',helper)
 D.mkdir(mode=0o700)
 def ident(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
 def put(path,raw):
  with path.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
  return pin(path)
 def prefix(path,name,limit):
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb')as f:
   before=ident(os.fstat(f.fileno()));assert before['uid']==os.getuid() and before['nlink']==1 and 0<before['bytes']<=limit
   raw=f.read(before['bytes']);after=ident(os.fstat(f.fileno()));f.seek(0);assert f.read(len(raw))==raw and before['device']==after['device'] and before['inode']==after['inode']
  return raw,dict(original_path=str(path),observed_before=before,observed_after=after,byte_range=[0,len(raw)],readonly_copy=put(D/name,raw),original_prefix_reread_identical=True,producer_changed=False)
 def lines(raw):return [json.loads(x)for x in raw[:raw.rfind(b'\n')+1].splitlines()]
 raw,status_evidence=prefix(C/'01-reference/status.json','original-status.snapshot.json',1<<20);status=json.loads(raw);cohort=status['cohort'];assert status['phase']=='collecting' and status['checkpoint_sha256']==pre['reference']['sha256'] and cohort['count']>=1 and cohort['abandoned']==0
 completed=set(cohort['started_ids'])-set(cohort['pending_ids'])-set(cohort['abandoned_ids']);assert len(completed)==cohort['count']
 raw,games_evidence=prefix(C/'01-reference/journal/games.jsonl','original-games.prefix.jsonl',4<<20);games=lines(raw);selected=[x for x in games if x['journal_game_id']in completed];assert selected
 game=min(selected,key=lambda x:(x['end_unix_s'],x['journal_game_id']));uid=game['journal_game_id'];assert game['complete'] is game['eligible'] is game['known_start'] is game['eval_only'] is True and game['first_play_level']==1 and game['playable_frames']>0
 assert cohort['start_ts']<=game['start_unix_s']<cohort['close_ts'] and game['end_unix_s']>game['start_unix_s'] and game['completion_policy']=='confirmed_reset_reserves_v1' and game['client_slot']in range(4096,4128)
 for ctx in [game['start_context'],game['end_context']]:
  assert ctx['learner_frames']==1597432474 and ctx['training_steps']==6585181 and ctx['optimized_samples']==25397106688 and ctx['epsilon']==ctx['expert_ratio']==0 and ctx['difficulty']==5 and ctx['experiment']==status['label'] and ctx['measurement_active'] is True and ctx['measurement_generation']==1
 raw,starts_evidence=prefix(C/'01-reference/journal/measurement_starts.jsonl','original-measurement-starts.prefix.jsonl',4<<20);starts=lines(raw);own=[x for x in starts if x['journal_game_id']==uid];assert len(own)==1 and terminal.start_record(game)==terminal.start_record(own[0])
 next_id=game['terminal_confirmation']['next_journal_game_id'];next_start=[x for x in starts if x['journal_game_id']==next_id];assert len(next_start)==1;terminal_join=terminal.validate_terminal(game,terminal.start_record(next_start[0]))
 confirmation=game['terminal_confirmation'];diagnostic=confirmation['ingest_boundary_inputs'];assert confirmation['previous_raw_reserves']==0 and diagnostic['previous_accepted_wire']['player_alive'] is False and diagnostic['recent_start'] is True
 raw,lives_evidence=prefix(C/'01-reference/journal/lives.jsonl','original-lives.prefix.jsonl',16<<20);life=[x for x in lines(raw)if x['journal_game_id']==uid];assert len(life)==game['deaths']>0 and [x['life']for x in life]==list(range(1,game['deaths']+1))
 for row in life:
  assert row['game_uid']==game['game_uid'] and row['client_slot']==game['client_slot'] and row['client_id']==game['client_id'] and row['known_game_start'] is row['eval_only'] is True and row['context']['learner_frames']==1597432474 and row['context']['experiment']==status['label']
 result=dict(status='ORIGINAL_R1_FIRST_MEASURED_COMPLETE_GAME_PREFIX_JOINS_PASS',observed_unix_s=time.time(),source=pin(Path(__file__)),original_monitor_report=monitor['receipt'],source_package=pre['source_package'],pure_terminal_helper=helper,original_status=status_evidence,original_games=games_evidence,original_starts=starts_evidence,original_lives=lives_evidence,game=game,original_measured_start=own[0],original_successor_start=next_start[0],terminal_join=terminal_join,life_records_checked=len(life),cohort_snapshot={k:cohort[k]for k in ['started','count','pending','abandoned','started_actor_slots']},main=monitor['main'],first_play_wave1_verified=True,recorded_exhausted_reserves_and_inactive_recent_START_verified=True,scope='One completed measured game prefix only; original successor start is joined. The successor completed-game row may not yet exist in the live game journal. Full final dual-journal, all admitted tails, ROM/runtime/lifecycles and independent candidate qualification remain required.',scientific_audit_rerun=False,quality_qualified=False,promotion=False,learning_speed_gain_verified=False,runtime_changed=False)
 receipt=put(Q/'R1-original-first-completed-game-independent-readback.json',(json.dumps(result,indent=2)+'\n').encode());print(json.dumps(dict(status=result['status'],receipt=receipt,game_id=uid,score=game['score'],life_records=len(life),snapshot=result['cohort_snapshot'],main=result['main'])))
if __name__=='__main__':main()
