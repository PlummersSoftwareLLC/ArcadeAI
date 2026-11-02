"""Derive new marker observations from closed v5 data; no old audit is invoked.

This is a bounded read-only historical calculation, not an admission certificate,
a diagnostic retry, a quality decision or a change to any current runtime.
"""
import argparse,hashlib,importlib.util,json,os,sys,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';D=R/'post-quality-startup-research-reconciliation-original01-20261021';HIST=R/'startup-diagnostic-wire1890-v5-real-original01-preparation-20261020/independent-original-diagnostic-review/review.json'
REPORT_SHA='4d8961997cdd67e0283bfab773a833f5912671672f57a61feb7eb1592c24be0b'
KEYS=('frame','epoch','exchange','raw_status','raw_reserves','raw_wave','raw_score_hex','wire_alive','wire_wave','wire_reserves','wire_score','wire_start','start_input','move','fire','apply_ok','socket_ok')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--derive',action='store_true');a=p.parse_args()
 if not a.derive:print('PLAN_ONLY: no reads, outputs or runtime actions');return
 rp=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py';assert hashlib.sha256(rp.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
 s=importlib.util.spec_from_file_location('_historical_marker_reader',rp);reader=importlib.util.module_from_spec(s);s.loader.exec_module(reader);pin=reader.pin;read=lambda e:reader.read_pin(e)
 reportpin=pin(HIST);assert reportpin['sha256']==REPORT_SHA;r=read(reportpin);assert r['valid'] is True and r['first_start_certified'] is r['admission_clock_ordering_verified'] is False
 inventory=read(r['inventory']);assert inventory['errors']==[] and inventory['original_producer_modes_unchanged'] is True
 slots={};byte_count=0
 for slot,old in sorted(r['independent_content_join']['slots'].items(),key=lambda x:int(x[0])):
  entry=inventory['retained']['Lua-'+slot];raw=reader.read_pin(entry,as_json=False);byte_count+=len(raw)
  assert len(raw)<3<<20 and len(old['START1_write_observations'])==1
  write=old['START1_write_observations'][0];write_frame=write['applied_input_frame'];session=None;expected_frame=0;first_init=first_alive=first_score=None;prewrite_score=False;scored_before_alive=False;first_zero_score_window=[];following=None
  for line in raw.splitlines():
   x=json.loads(line)
   if x['kind']=='header':session=x['session'];assert x['slot']==int(slot);continue
   if x['kind']!='frame':continue
   assert x['slot']==int(slot) and x['session']==session and x['frame']==expected_frame;expected_frame+=1
   if x['frame']<=write_frame and x['wire_score']!=0:prewrite_score=True
   if x['frame']==write_frame+1:following=x
   if x['frame']<=write_frame:continue
   if first_init is None and x['raw_wave']==x['wire_wave']==1 and x['raw_reserves']==x['wire_reserves']==2:first_init=x
   if first_alive is None and x['wire_alive']==1:
    first_alive=x
   if first_alive is not None and first_score is None and x['wire_score']==0:first_zero_score_window.append(x['frame'])
   if x['wire_score']>0:
    if first_alive is None:scored_before_alive=True
    first_score=x;break
  def view(x):return None if x is None else {key:x[key]for key in KEYS}
  slots[slot]=dict(original_Lua_prefix=entry,session=session,old_report_START1_write=write,checked_contiguous_frame_count=expected_frame,positive_score_at_or_before_START1=prewrite_score,immediate_following_frame=view(following),first_wave1_reserves2_after_write=view(first_init),first_wire_alive_after_write=view(first_alive),first_positive_wire_score_after_write=view(first_score),positive_score_before_first_wire_alive=scored_before_alive,observed_zero_score_alive_frame_count=len(first_zero_score_window),frame_index_order_observed=all(x is not None for x in [following,first_init,first_alive,first_score]) and write_frame<following['frame']<=first_init['frame']<first_alive['frame']<first_score['frame'],admission_certified=False,host_admission_clock_ordering_verified=False)
 assert len(slots)==16 and byte_count<48<<20
 ordered=[x for x in slots.values()if x['frame_index_order_observed']];zero=[x for x in ordered if not x['positive_score_at_or_before_START1'] and not x['positive_score_before_first_wire_alive'] and x['first_wire_alive_after_write']['wire_wave']==1 and x['first_wire_alive_after_write']['wire_score']==0]
 result=dict(schema='robotron-closed-first-play-marker-observations-v1',status='NEW_HISTORICAL_FRAME_MARKER_LEDGER_NOT_ADMISSION_CERTIFICATION',observed_unix_s=time.time(),source=pin(Path(__file__)),original_completed_review=reportpin,original_inventory=r['inventory'],input_bytes_hashed=byte_count,slots=slots,summary=dict(slots=len(slots),ordered_frame_sequences=len(ordered),zero_score_wave1_first_alive_after_START1_slots=len(zero),first_initialization_frames=sorted({x['first_wave1_reserves2_after_write']['frame']for x in ordered}),first_alive_frames=sorted({x['first_wire_alive_after_write']['frame']for x in ordered}),first_score_frames=sorted({x['first_positive_wire_score_after_write']['frame']for x in ordered})),scope='New observations derived from already verified closed immutable Lua prefixes and retained START1-site reports. No original reviewer, reconciler, diagnostic, CPU test, model, GPU or live input was executed.',limitations=['Wire-alive and counters are candidate observation fields, not independent proof of a full ROM startup or player count','Frame indices establish only intra-prefix order; these rows do not establish the host admission-clock deadline or current measurement generation','The first alive row already carries the next control response; future eligibility must be latched before any gameplay/scoring and linked across Lua/server/journal contexts','No current eligibility changes and no earlier unknown-start game may be relabelled or added to current quality'],first_start_certified=False,admission_clock_ordering_verified=False,real_ROM_start_proven=False,protocol_selected=False,quality_qualified=False,learning_speed_gain_verified=False,original_scientific_review_or_probe_repeated=False,live_runtime_changed=False)
 out=D/'historical-first-play-marker-ledger-original01.json'
 with out.open('x')as f:json.dump(result,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 assert 'torch' not in sys.modules
 print(json.dumps(dict(status=result['status'],receipt=pin(out),summary=result['summary'])))
if __name__=='__main__':main()
