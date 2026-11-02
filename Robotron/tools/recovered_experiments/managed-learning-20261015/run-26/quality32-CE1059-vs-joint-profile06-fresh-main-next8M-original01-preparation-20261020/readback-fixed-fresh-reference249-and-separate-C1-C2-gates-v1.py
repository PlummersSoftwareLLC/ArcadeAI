"""Passive fixed fresh R1+R2 and separate C1/C2 numerical gates; original final review still required."""
from pathlib import Path
from fractions import Fraction
import hashlib,json,os,stat,statistics,sys,time
HERE=Path(__file__).resolve().parent
PLAN_SHA='97b781ba8fc65d84ffb5d511a22c59391cd49e281afa059dbf1bebf2f81b73db'
SPECS=[('R1', 121, 'reference', 1, '6eb0925a3dc876b9fff0b3a4f8810d07f1890025176ca66432ed7b4404ccc448', 'a967f8c7b0a1f39d21f076c63720c7fe8a301f7ba7e62f9412ec1496359a1e95'), ('R2', 128, 'reference', 3, 'b4807162e16fa1206b89aaffa0eda8337422e920c7429b2a9688737974e7073b', '6e64c49a0ab2abac27488f22b6ca05af8b22d3894e960a15d0913eb12ac90b33'), ('C1', 67, 'candidate', 2, '290724b9883d001ad625db0dd870a69c8218e7601c13b2b067c79af7b16acee3', '2234ad7aa5919cda5a903b918b5e91e40cafae69e17ff8b8be2347b042e54f5a'), ('C2', 74, 'candidate', 4, None, '8a8322ef0798e6b7b0889a0a824b54df6a13d240c5656418bfda0c0b2a2c37ce')]
REF_SHA='4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
CAND_SHA='c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'
def identity(s):
 return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
def pin(p):
 a=identity(p.stat());raw=p.read_bytes();assert identity(p.stat())==a
 return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=a)
def immutable(p,expected=None):
 v=pin(p);assert v['identity']['mode']=='0o444' and v['identity']['uid']==1001 and v['identity']['nlink']==1
 assert expected is None or v['sha256']==expected
 return json.loads(p.read_bytes()),v
def fraction(v):return dict(numerator=v.numerator,denominator=v.denominator,value=float(v))
def main():
 output=HERE/'R1-R2-fixed-fresh-reference-and-separate-C1-C2-gates-readback.json';assert not output.exists()
 assert (HERE/'C2-original-closed-cohort-independent-readback/readback.json').exists(),'Original independent closed C2 readback is required first'
 fixed,fp=immutable(HERE/'R1-R2-fixed-fresh-reference-and-C1-independent-gate-readback.json','bea26329ffb10ebd7e6756d4abfe20c9acf13699e4427ae1390461a8830ca6af')
 assert fixed['source']['sha256']=='d77679a51d28bbd7991674036a9dca4befe2af75f636eeb5121279336999aa37' and pin(Path(fixed['source']['path']))==fixed['source']
 receipts={};inputs=[];preserved=[];scores={}
 for label,n,role,index,expected,source_sha in SPECS:
  report,rp=immutable(HERE/f'{label}-original-closed-cohort-independent-readback/readback.json',expected)
  assert report['status']==f'PASS_CLOSED_{label}_ORIGINALS_ROM_RUNTIME_ONLY'
  assert report['source']['sha256']==source_sha and pin(Path(report['source']['path']))==report['source']
  assert report['original_record']['index']==index and report['original_record']['role']==role and report['original_record']['returncode']==0 and report['original_record']['state']=='finished'
  assert report['original33_process_births_absent'] and report['fixed_admission_ids_match'] and not report['qualified_policy'] and not report['promotion']
  assert report['counts']==dict(count=n,started=n,pending=0,abandoned=0)
  assert report['plan']['sha256']==PLAN_SHA and pin(Path(report['plan']['path']))==report['plan']
  receipt_pin=report['captures'][0]['archive'];receipt,actual=immutable(Path(receipt_pin['path']));assert actual==receipt_pin
  assert actual['sha256']==report['receipt_sha256']==report['captures'][0]['original']['sha256']
  assert receipt['valid'] is True and receipt['complete'] is True and receipt['count']==receipt['started']==n and receipt['pending']==receipt['abandoned']==0
  assert receipt['checkpoint_sha256']==(REF_SHA if role=='reference' else CAND_SHA)
  rows=receipt['rows'];assert len(rows)==n and len({r['journal_game_id'] for r in rows})==n
  assert all(r['known_start'] is True and r['eligible'] is True and r['complete'] is True for r in rows)
  assert {r['client_slot'] for r in rows}==set(range(4096,4128))
  values=[r['score'] for r in rows];assert all(type(v) is int and v>=0 for v in values)
  stats=report['cohort']['original_games']['statistics'];assert stats['score_sum']==sum(values) and stats['count']==n
  assert stats['mean']==sum(values)/n==receipt['mean'] and stats['median']==statistics.median(values)==receipt['median']
  receipts[label]=receipt;scores[label]=values;inputs.append(dict(label=label,closed_readback=rp,receipt_archive=actual,source=report['source'],count=n,score_sum=sum(values)))
  preserved.extend([rp,actual,report['source'],report['plan']])
 preserved.extend([fp,fixed['source']])
 reference_values=scores['R1']+scores['R2'];assert len(reference_values)==249 and sum(reference_values)==630876325
 ref_mean=Fraction(sum(reference_values),249);ref_median=Fraction(statistics.median(reference_values));required=ref_mean*Fraction(21,20)
 reference=dict(leg_indices=[1,3],checkpoint_sha256=REF_SHA,count=249,score_sum=sum(reference_values),mean=fraction(ref_mean),median=fraction(ref_median),candidate_mean_minimum=fraction(required))
 assert reference==fixed['fixed_reference']
 confirmations=[]
 for label,index in [('C1',2),('C2',4)]:
  values=scores[label];mean=Fraction(sum(values),len(values));median=Fraction(statistics.median(values))
  gate=dict(label=label,leg_index=index,checkpoint_sha256=CAND_SHA,count=len(values),score_sum=sum(values),mean=fraction(mean),median=fraction(median),mean_ratio=fraction(mean/ref_mean),mean_at_least_105_percent=mean>=required,median_preserved=median>=ref_median,independent_numerical_gate_passed=mean>=required and median>=ref_median)
  if label=='C1':assert {k:v for k,v in gate.items() if k!='label'}==fixed['candidate1']
  confirmations.append(gate)
 for value in preserved:assert pin(Path(value['path']))==value
 report=dict(schema='profile06-fixed-fresh-reference249-and-separate-C1-C2-gates-v1',observed_unix_s=time.time(),source=pin(Path(__file__)),inputs=inputs,previous_fixed_reference_and_C1_gate=fp,selection='Exactly all121 R1 plus all128 R2 games form the unchanged fixed fresh reference. C1 is its own67-game cohort and C2 its own74-game cohort. No candidate pooling, history, score filtering, retry or extension.',fixed_reference=reference,candidate_confirmations=confirmations,both_independent_numerical_gates_passed=all(x['independent_numerical_gate_passed'] for x in confirmations),original_final_campaign_review_and_lifecycle_disposition_still_required=True,original_final_reviewer_executed_by_this_passive_reader=False,qualified_policy=False,promotion=False,learning_speed_gain_verified=False,source_or_runtime_changed=False)
 with output.open('xb') as f:f.write((json.dumps(report,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 print(json.dumps(dict(readback=pin(output),fixed_reference=reference,candidate_confirmations=confirmations,both_independent_numerical_gates_passed=report['both_independent_numerical_gates_passed'],promotion=False)))
if __name__=='__main__':
 if sys.argv[1:]==['--observe']:main()
 else:print('PLAN_ONLY: requires completed original independent C2 readback; original final review/lifecycle still required')
