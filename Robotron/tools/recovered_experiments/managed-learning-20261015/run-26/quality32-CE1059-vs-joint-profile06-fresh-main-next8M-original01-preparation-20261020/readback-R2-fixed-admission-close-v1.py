"""Passive original R2 fixed-admission closure; does not qualify a completed cohort."""
from pathlib import Path
import hashlib,json,os,stat,sys,time
GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
CAMPAIGN=GAME/'logs/managed-learning-20261015/quality-CE1059M-vs-joint-profile06-fresh-next8M-quality32-trial01-20261020'
LEG=CAMPAIGN/'03-reference'
OUTPUT=HERE/'R2-fixed-admission-close-prefixes'
def identity(s):
 return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
def pin(p):
 a=identity(p.stat());b=p.read_bytes();assert identity(p.stat())==a
 return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=a)
def write(p,raw):
 with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 return pin(p)
def capture(p,lines=False):
 with p.open('rb') as f:
  before=os.fstat(f.fileno());raw=f.read()
  if lines:raw=raw[:raw.rfind(b'\n')+1]
  f.seek(0);assert f.read(len(raw))==raw;after=os.fstat(f.fileno())
  assert all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_mode','st_uid','st_nlink'))
 return raw,dict(original_path=str(p),original_identity_before=identity(before),original_identity_after=identity(after),stable_prefix_reread=True,prefix_bytes=len(raw),prefix_sha256=hashlib.sha256(raw).hexdigest(),archive=write(OUTPUT/p.name,raw))
def main():
 out=HERE/'R2-fixed-admission-close-readback.json';assert not out.exists() and not OUTPUT.exists()
 pre=json.loads((LEG/'status.json').read_bytes());assert pre['cohort']['closed'] is True and time.time()>pre['close_ts']
 OUTPUT.mkdir()
 sr,sp=capture(LEG/'status.json');ar,ap=capture(LEG/'journal/measurement_starts.jsonl',True);gr,gp=capture(LEG/'journal/games.jsonl',True)
 s=json.loads(sr);starts=[json.loads(x) for x in ar.splitlines()];games=[json.loads(x) for x in gr.splitlines()];c=s['cohort']
 assert s['label']=='CE1059M-protected-fixed-reference-02' and s['generation']==1
 assert s['phase'] in ('draining','complete') and c['closed'] is True
 assert s['start_ts']==1792540079.5291417 and s['close_ts']==1792545479.5291417 and s['close_ts']-s['start_ts']==5400
 assert s['checkpoint_sha256']=='4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
 assert s['clocks']['learner_frame_count']==1059300354 and s['clocks']['training_steps']==4538417 and s['clocks']['optimized_samples']==17013561344
 job=s['job'];assert job['actors']==32 and job['actor_slots']==list(range(4096,4128))
 for k,v in dict(cohort_s=5400,timeout_s=9000,epsilon=0,expert_ratio=0,difficulty=5,start_level=1,replay_enabled=False).items():assert job[k]==v,(k,job[k])
 plan=pin(CAMPAIGN/'plan.json');assert plan['sha256']=='97b781ba8fc65d84ffb5d511a22c59391cd49e281afa059dbf1bebf2f81b73db'
 actors=pin(HERE/'runtime-bindings/leg-births/leg3-actors.json');handoff_path=HERE/'R2-original-startup-policy-and-C1-handoff-readback.json'
 assert pin(handoff_path)['sha256']=='20568332c1eeee510a851ad3db17d836dbe3d7ca50197db93defdf09ededd160'
 h=json.loads(handoff_path.read_bytes());assert actors==h['original32_actor_registry']
 assert len({r['journal_game_id'] for r in starts})==len(starts)
 admitted=[r for r in starts if r['experiment']==s['label'] and r['known_start'] is True and r['measurement_active'] is True and r['measurement_generation']==s['generation'] and s['start_ts']<=r['start_unix_s']<=s['close_ts']]
 ids=[r['journal_game_id'] for r in admitted];frozen=set(c['started_ids']);assert len(ids)==len(set(ids))==len(frozen)==s['started'] and set(ids)==frozen and len(ids)>=50
 assert c['started']==s['started'] and c['count']==s['count'] and c['pending']==s['pending'] and c['abandoned']==s['abandoned']
 assert s['count']+s['pending']+s['abandoned']==len(ids) and s['abandoned']==0
 pending=set(c['pending_ids']);abandoned=set(c['abandoned_ids']);assert pending<=frozen and abandoned<=frozen and not pending&abandoned and len(pending)==s['pending'] and len(abandoned)==s['abandoned']
 by_slot={}
 for r in admitted:
  assert r['client_slot'] in range(4096,4128);by_slot.setdefault(r['client_slot'],set()).add(r['client_id']);x=r['context']
  assert x['epsilon']==x['expert_ratio']==0 and x['difficulty']==5
  assert x['learner_frames']==1059300354 and x['training_steps']==4538417 and x['optimized_samples']==17013561344
 assert set(by_slot)==set(range(4096,4128)) and all(len(v)==1 for v in by_slot.values())
 assert {next(iter(v)) for v in by_slot.values()}==set(range(32))
 assert set(c['started_actor_slots'])==set(range(4096,4128))
 game_ids={r['journal_game_id'] for r in games};assert len(game_ids)==len(games)
 assert frozen-pending-abandoned<=game_ids
 eligible=[r for r in games if r.get('eligible') is True and r['experiment']==s['label'] and r['measurement_generation']==s['generation']]
 assert all(r['journal_game_id'] in frozen and r['known_start'] is True and r['complete'] is True for r in eligible)
 report=dict(schema='profile06-R2-fixed-admission-close-readback-v1',observed_unix_s=time.time(),source=pin(Path(__file__)),plan=plan,original_actor_registry=actors,original_handoff=pin(handoff_path),status=sp,original_starts_prefix=ap,original_games_prefix=gp,admission_start_unix_s=s['start_ts'],admission_close_unix_s=s['close_ts'],fixed_admission_s=5400,frozen_admitted_count=len(ids),frozen_admission_ids=ids,all_original_start_contexts_frozen=True,all32_slots_checked=True,one_original_client_per_slot=True,original_eligible_completed_rows_within_frozen_set=True,captured_status_counts={k:s[k] for k in ('count','started','pending','abandoned')},counts_are_snapshot_not_exact_cutoff_instant=True,all_admitted_tails_still_required=True,full_closed_original_journal_ROM_runtime_and_four_leg_review_still_required=True,quality_qualified=False,promotion=False,source_or_runtime_changed=False)
 p=write(out,(json.dumps(report,indent=2)+'\n').encode());print(json.dumps(dict(readback=p,frozen_admitted_count=len(ids),counts=report['captured_status_counts'],quality_qualified=False)))
if __name__=='__main__':
 if sys.argv[1:]==['--observe']:main()
 else:print('PLAN_ONLY: requires original R2 fixed admission to be closed before --observe')
