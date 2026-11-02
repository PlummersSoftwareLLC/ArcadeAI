"""Passive fixed fresh R1+R2 pool and independent C1 numerical gate; C2/final review still required."""
from pathlib import Path
from fractions import Fraction
import hashlib,json,os,stat,statistics,sys,time
HERE=Path(__file__).resolve().parent
PLAN_SHA='97b781ba8fc65d84ffb5d511a22c59391cd49e281afa059dbf1bebf2f81b73db'
SPECS=[('R1',121,'reference',1,'6eb0925a3dc876b9fff0b3a4f8810d07f1890025176ca66432ed7b4404ccc448','a967f8c7b0a1f39d21f076c63720c7fe8a301f7ba7e62f9412ec1496359a1e95'),('R2',128,'reference',3,None,'6e64c49a0ab2abac27488f22b6ca05af8b22d3894e960a15d0913eb12ac90b33'),('C1',67,'candidate',2,'290724b9883d001ad625db0dd870a69c8218e7601c13b2b067c79af7b16acee3','2234ad7aa5919cda5a903b918b5e91e40cafae69e17ff8b8be2347b042e54f5a')]
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
 output=HERE/'R1-R2-fixed-fresh-reference-and-C1-independent-gate-readback.json';assert not output.exists()
 assert (HERE/'R2-original-closed-cohort-independent-readback/readback.json').exists(),'Original independent closed R2 readback is required first'
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
 reference_values=scores['R1']+scores['R2'];assert len(reference_values)==249
 ref_mean=Fraction(sum(reference_values),len(reference_values));ref_median=Fraction(statistics.median(reference_values))
 candidate_values=scores['C1'];cand_mean=Fraction(sum(candidate_values),len(candidate_values));cand_median=Fraction(statistics.median(candidate_values))
 required=ref_mean*Fraction(21,20);mean_pass=cand_mean>=required;median_pass=cand_median>=ref_median
 for value in preserved:assert pin(Path(value['path']))==value
 report=dict(schema='profile06-fixed-fresh-reference249-and-independent-C1-gate-v1',observed_unix_s=time.time(),source=pin(Path(__file__)),inputs=inputs,selection='Exactly all121 independently validated original fresh R1 games plus all128 original fresh R2 games form one fixed reference. C1 is its own67-game cohort; no candidate pooling,history,retry or score filtering.',fixed_reference=dict(leg_indices=[1,3],checkpoint_sha256=REF_SHA,count=249,score_sum=sum(reference_values),mean=fraction(ref_mean),median=fraction(ref_median),candidate_mean_minimum=fraction(required)),candidate1=dict(leg_index=2,checkpoint_sha256=CAND_SHA,count=67,score_sum=sum(candidate_values),mean=fraction(cand_mean),median=fraction(cand_median),mean_ratio=fraction(cand_mean/ref_mean),mean_at_least_105_percent=mean_pass,median_preserved=median_pass,independent_numerical_gate_passed=mean_pass and median_pass),C2_independently_valid_complete_game_confirmation_still_required=True,original_final_campaign_review_and_lifecycle_disposition_still_required=True,qualified_policy=False,promotion=False,learning_speed_gain_verified=False,source_or_runtime_changed=False)
 with output.open('xb') as f:f.write((json.dumps(report,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 print(json.dumps(dict(readback=pin(output),fixed_reference=report['fixed_reference'],candidate1=report['candidate1'],promotion=False)))
if __name__=='__main__':
 if sys.argv[1:]==['--observe']:main()
 else:print('PLAN_ONLY: requires completed original independent R2 readback first; no promotion or final campaign decision')
