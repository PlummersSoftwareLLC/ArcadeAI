"""Verify actual original winner publication and its closure; no scientific review or publication rerun."""
from pathlib import Path
import hashlib,importlib.util,json,math,os,re,shlex,stat,statistics,sys,time,urllib.request
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');P=Path(__file__).resolve().parent;Q=P.parent;E=P/'publication-original01-execution'
def ident(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
def pin(p):
 p=Path(p);a=ident(p.stat());b=p.read_bytes();assert ident(p.stat())==a
 return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=a)
def load(p,sha,name):
 p=Path(p);v=pin(p);assert v['sha256']==sha and v['identity']['mode']=='0o444';s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);assert pin(p)==v;return m

def main():
 out=P/'actual-original-publication-independent-readback.json';assert not out.exists()
 protector=load(G/'tools/quality_capacity_proposal/protect_quality32_winner_v6.py','815f326b3129721910450c74a96eea3bfcda0b4f70430cb1ba9545388ab9a212','_publication_protector');reader=protector.reader_module()
 runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_publication_runtime');control=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_publication_control')
 jp=pin(P/'job.json');assert jp['sha256']=='a54168bc10e58eaa973fdc19de45acb402b669972f6591a91cc739748ff13ba4';job=reader.read_pin(jp)
 rp=pin(P/'root-final-disposition-readback.json');assert rp['sha256']=='6aa6d10b74f9e4f5734d6409a0a2a460058dc34b941ec8a29f1b8b089cddf918';root=reader.read_pin(rp);assert root['quality_qualified'] is True and root['protection_job']==jp and not root['original_review_rerun']
 cp=pin(E/'root-original-result-and-owned-release.json');assert cp['sha256']=='422f18439600de8c6346b21efa94fe1ec79c51501dd7c1ff56b2e9d1db5e6907';op=pin(E/'root-original-identity.json');owner=reader.read_pin(op);closure=reader.read_pin(cp)
 fields=runtime.archived_closure(closure,owner,lambda v,as_json=True:reader.read_pin(v,as_json=as_json),exit_zero=True)
 assert fields['MemoryMax']==str(4<<30) and fields['MemorySwapMax']=='0' and runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and runtime.duration_seconds(fields['RuntimeMaxUSec'])==180 and runtime.duration_seconds(fields['TimeoutStopUSec'])==5 and fields['TasksMax']=='256' and fields['Restart']=='no' and fields['SendSIGKILL']=='no'
 configp=pin(P/'publication-controller-config.json');assert configp['sha256']=='5512c64d37ce859bb2be510369bca62dca66b099bc62273add1308c4e01f8487';config=reader.read_pin(configp);assert config['unit']==owner['unit']
 expected=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(E/'tmp')]+config['argv'];match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart']);assert match and shlex.split(match[1])==expected
 assert not Path('/proc',str(owner['pid'])).exists()
 for unit in [owner['unit'],owner['timer']]:assert control.show(unit)['LoadState']=='not-found'
 path=Path(job['destination'])/(job['label']+'.pt');metadata=Path(str(path)+'.json');model=pin(path);mp=pin(metadata)
 assert model['sha256']=='c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c' and model['bytes']==275208960
 for v in [model,mp]:assert v['identity']['mode']=='0o444' and v['identity']['uid']==1001 and v['identity']['nlink']==1
 meta=reader.read_pin(mp);assert meta['schema']=='robotron-quality32-protected-winner-v1' and meta['root_protection_job']==jp and meta['checkpoint_sha256']==model['sha256'] and meta['checkpoint_bytes']==model['bytes'] and meta['protected_checkpoint']==str(path)
 assert meta['assessment']==root['original_protection_evidence_verification']['assessment'] and meta['assessment']['qualified_improvement'] and not meta['assessment']['candidates_pooled_for_qualification']
 assert meta['original_review_report']==job['review_report'] and meta['original_review_owner']==job['review_owner'] and meta['original_review_closure']==job['review_closure']
 assert meta['managed_incumbent_updated'] is False and meta['live_learner_restored'] is False and meta['original_scientific_audit_rerun'] is False and meta['learning_speed_gain_verified'] is False
 assert pin(meta['candidate_source']['path'])==meta['candidate_source'] and pin(meta['reference']['path'])==meta['reference'];old=meta['reference']
 assert old['sha256']=='4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
 clocks=meta['acquisition']['clocks'];assert clocks['learner_frame_count']==1597432474 and clocks['training_steps']==6585181 and clocks['optimized_samples']==25397106688
 values=[];receipt_pins=[]
 for leg,n in [('02-candidate',67),('04-candidate',74)]:
  f=Path(meta['campaign_directory'])/leg/'receipt.json';fp=pin(f);receipt=json.loads(f.read_bytes());assert receipt['valid'] is True and receipt['complete'] is True and receipt['count']==receipt['started']==n and receipt['pending']==receipt['abandoned']==0 and receipt['checkpoint_sha256']==model['sha256'];values.extend(row['score'] for row in receipt['rows']);receipt_pins.append(fp)
 assert len(values)==141 and sum(values)==539629275
 api=json.loads(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=12).read());assert api['client_count']==192 and api['learner_frame_count']>clocks['learner_frame_count'] and api['lr']==1.25e-5 and all(math.isfinite(api[k]) for k in ['loss','grad_norm','q_mean']) and api['bank_persistence']['write_failures']==0
 preserved=[jp,rp,cp,op,configp,model,mp,old,meta['candidate_source'],*receipt_pins]
 for v in preserved:assert pin(v['path'])==v
 report=dict(schema='profile06-actual-original-publication-independent-readback-v1',status='PASS_ORIGINAL_PUBLICATION_BYTES_METADATA_LIFECYCLE_AND_MAIN',observed_unix_s=time.time(),source=pin(Path(__file__)),protection_job=jp,root_final_disposition=rp,original_publication_owner=op,original_publication_closure=cp,controller_config=configp,all6_original_publication_descriptors_verified=True,actual_descriptor_exits=[v['exit'] for v in closure['full_original_archives']],actual_publication_exit=0,exact_publication_service_timer_released=True,actual_selected_publication_command_verified=True,protected_model=model,protected_metadata=mp,prior_protected_model_preserved=old,candidate_receipts=receipt_pins,candidate_summary_descriptive_only=dict(count=len(values),score_sum=sum(values),mean=sum(values)/len(values),median=statistics.median(values)),saved_clocks=clocks,assessment=meta['assessment'],published_utc=meta['published_utc'],main192_healthy=True,main_learner_frames=api['learner_frame_count'],main_training_steps=api['training_steps'],bank_write_failures=0,canonical_incumbent_updated_by_this_reader=False,live_learner_restored=False,original_scientific_review_rerun=False,publication_rerun=False,learning_speed_gain_verified=False)
 with out.open('xb') as f:f.write((json.dumps(report,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 print(json.dumps(dict(readback=pin(out),protected_model=model,protected_metadata=mp,descriptive_candidate_summary=report['candidate_summary_descriptive_only'],canonical_incumbent_updated=False)))
if __name__=='__main__':
 if sys.argv[1:]==['--observe']:main()
 else:print('PLAN_ONLY: verify one actual original publication; no publication, review or policy mutation')
