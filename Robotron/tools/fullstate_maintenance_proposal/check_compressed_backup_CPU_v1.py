"""Exercise real compressed backup I/O, corruption detection and failure fences."""
import argparse,ast,copy,hashlib,importlib.util,json,os,pathlib,sys,zlib
def main():
 p=argparse.ArgumentParser();p.add_argument('--prepared',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 prep=json.loads(a.prepared.read_text());source=pathlib.Path(prep['source']['path']);assert hashlib.sha256(source.read_bytes()).hexdigest()==prep['source']['sha256']
 sp=importlib.util.spec_from_file_location('_actual_compressed_backup_CPU',source);m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
 a.output.mkdir(mode=0o700);checks=[]
 def check(n,v):assert v,n;checks.append(n)
 def rejects(n,fn):
  try:fn()
  except (ValueError,RuntimeError,OSError,zlib.error):checks.append(n);return
  raise AssertionError('Unsafe case accepted: '+n)
 parent=pathlib.Path(prep['parent']['path']).read_text();new=source.read_text()
 oldfunc={n.name:ast.dump(n)for n in ast.parse(parent).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))};newfunc={n.name:ast.dump(n)for n in ast.parse(new).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
 for key in oldfunc:
  if key not in ['copy_file','execute']:check('unchanged original '+key,oldfunc[key]==newfunc[key])
 back=new
 for row in reversed(prep['edits']):assert back.count(row['after'])==1;back=back.replace(row['after'],row['before'],1)
 check('complete exact source reverse proof',back==parent)
 def sealed(name,raw):
  path=a.output/name
  with path.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
  return path
 def entry(path,relative):return dict(source=str(path),relative=relative,identity=m.source_identity(path),expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 def progress(budget=128<<20):return dict(compressed_bytes_written=0,maximum_compressed_bytes=budget,required_free_margin=0)
 output=a.output/'backup';output.mkdir(mode=0o700)
 results=[]
 for name,raw in [('zeros',b'\0'*(12<<20)),('pattern',bytes(range(256))*32769),('random',os.urandom(8<<20)),('empty',b'')]:
  path=sealed(name,raw);before=m.pin(path);pr=progress();result=m.copy_file(entry(path,name),output,pr,lambda:None);results.append(result)
  check(name+' complete independently decompressed/hash/fsync proof',result['complete']and result['fsync_completed']and result['destination_payload_reread_hash_performed']and result['independent_decompressed_sha256']==before['sha256']and result['bytes_copied']==len(raw))
  check(name+' independent physical readonly file',result['destination_identity']['mode']=='0o444'and result['destination_identity']['nlink']==1 and result['destination_identity']['inode']!=before['identity']['inode'])
  check(name+' exact compressed-byte budget accounting',pr['compressed_bytes_written']==pathlib.Path(result['destination']).stat().st_size==result['compressed_bytes'])
  check(name+' original source unchanged',m.pin(path)==before)
  check(name+' independently decodes to original bytes',zlib.decompress(pathlib.Path(result['destination']).read_bytes())==raw)
  rejects(name+' exclusive duplicate output rejected',lambda:path and m.copy_file(entry(path,name),output,progress(),lambda:None))
 good=results[0];packed=pathlib.Path(good['destination']).read_bytes()
 def read_bad(name,data,raw_size=None,raw_sha=None):
  path=sealed(name,data)
  return lambda:m.verify_compressed_file(path,good['bytes_copied']if raw_size is None else raw_size,good['stream_sha256']if raw_sha is None else raw_sha,hashlib.sha256(data).hexdigest())
 rejects('truncated trailer cannot qualify full output',read_bad('truncated',packed[:-1]))
 rejects('corrupted compression checksum rejected',read_bad('corrupt',packed[:-1]+bytes([packed[-1]^1])))
 rejects('trailing data refused',read_bad('trailing',packed+b'x'))
 rejects('concatenated stream refused',read_bad('concatenated',packed+zlib.compress(b'x')))
 rejects('decompression beyond selected original size refused',read_bad('overflow',packed,raw_size=1))
 rejects('wrong decompressed source hash refused',read_bad('wrongsource',packed,raw_sha='0'*64))
 rejects('wrong compressed hash refused',lambda:m.verify_compressed_file(pathlib.Path(good['destination']),good['bytes_copied'],good['stream_sha256'],'0'*64))
 random=a.output/'random';before=m.pin(random)
 rejects('byte-budget exhaustion fails before completion',lambda:m.copy_file(entry(random,'budget-exhausted'),output,progress(1),lambda:None))
 partial=output/'files/budget-exhausted.zlib';check('budget failure leaves only readonly partial',partial.exists()and(partial.stat().st_mode&511)==0o444)
 check('budget failure preserves original',m.pin(random)==before)
 bad=entry(random,'wrong-expected');bad['expected_sha256']='0'*64
 rejects('verified-source hash mismatch cannot qualify backup',lambda:m.copy_file(bad,output,progress(),lambda:None))
 check('source mismatch preserves original',m.pin(random)==before)
 bad=entry(random,'../escape');rejects('parent traversal refused',lambda:m.copy_file(bad,output,progress(),lambda:None))
 bad=entry(random,'/absolute');rejects('absolute destination refused',lambda:m.copy_file(bad,output,progress(),lambda:None))
 link=a.output/'source-link';link.symlink_to(random);bad=entry(random,'source-link');bad['source']=str(link)
 rejects('source symlink refused',lambda:m.copy_file(bad,output,progress(),lambda:None))
 check('all originals intact after negative cases',m.pin(random)==before)
 check('no numerical runtime imported','torch'not in sys.modules and'numpy'not in sys.modules)
 report=dict(status='PASS_COMPRESSED_BACKUP_ACTUAL_IO_CPU_CONTRACTS',checks_total=len(checks),checks=checks,source=prep['source'],source_derivation=m.pin(a.prepared),files=results,synthetic_test_data_only=True,whole_live_state_backup_performed=False,Main_or_sources_changed=False,source_owner_and_full_inventory_kernels_unchanged=True,promotion=False)
 target=a.output/'CPU-contracts.json'
 with target.open('x')as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
 print(json.dumps(dict(status=report['status'],checks=len(checks),report={k:m.pin(target)[k]for k in ('path','sha256','bytes')})),flush=True)
if __name__=='__main__':main()
