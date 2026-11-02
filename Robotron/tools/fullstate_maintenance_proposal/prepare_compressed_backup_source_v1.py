"""Derive a stopped-owner-only compressed backup with independent readback."""
import argparse,ast,hashlib,importlib.util,json,os,pathlib,sys
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/post-engineering-fullstate-preservation-original03-20261101/sources/copy_verified_current_continuous_state_v6.py'
def main():
    a=argparse.ArgumentParser();a.add_argument('--output',type=pathlib.Path,required=True);args=a.parse_args()
    assert hashlib.sha256(P.read_bytes()).hexdigest()=='a38d9dff1dd8f2b6e07198b1e685b00c55148bde785783a7c14d9ff750df2bcc'
    spec=importlib.util.spec_from_file_location('_compressed_source_parent',P);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    original=P.read_text();text=original;edits=[]
    def replace(before,after):
        nonlocal text
        assert text.count(before)==1,before[:70];text=text.replace(before,after,1);edits.append((before,after))
    functions=pathlib.Path(__file__).with_name('compressed_copy_functions_v1.txt')
    replace('import traceback\n','import traceback\nimport zlib\n')
    replace("VERIFIER=Path(__file__).with_name('verify_current_continuous_stopped_fullstate_v4.py')",'VERIFIER=Path('+repr(str(P.with_name('verify_current_continuous_stopped_fullstate_v4.py')))+')')
    old=next(n for n in ast.parse(original).body if isinstance(n,ast.FunctionDef)and n.name=='copy_file')
    replace(ast.get_source_segment(original,old),functions.read_text().rstrip())
    replace("job['schema']=='robotron-verified-stopped-full-training-backup-job-v1'","job['schema']=='robotron-verified-stopped-full-training-compressed-backup-job-v1'")
    replace("job['unit']=='robotron-current-continuous-backup3600-'","job['unit']=='robotron-current-continuous-compressed-backup3600-'")
    replace("    space=os.statvfs(parent);available=space.f_bavail*space.f_frsize;margin=max(32<<30,(total+9)//10)\n    require(available>=total+margin,'Insufficient free disk for complete copy plus margin')", "    space=os.statvfs(parent);available=space.f_bavail*space.f_frsize;margin=32<<30\n    require(type(job['maximum_compressed_bytes'])is int and 0<job['maximum_compressed_bytes']<=128<<30,\n        'Explicit bounded compressed-byte budget required')\n    require(available>=job['maximum_compressed_bytes']+margin,'Insufficient disk for compressed budget plus reserve')")
    replace("        completed_files=[],active_file=None,active_file_bytes=0,active_file_complete=False,complete=False)","        maximum_compressed_bytes=job['maximum_compressed_bytes'],compressed_bytes_written=0,\n        completed_files=[],active_file=None,active_file_bytes=0,active_file_complete=False,complete=False)")
    replace("schema='robotron-verified-stopped-full-training-backup-v1',status='COMPLETE_STREAM_HASHED_AND_FSYNCED'","schema='robotron-verified-stopped-full-training-compressed-backup-v1',status='COMPLETE_COMPRESSED_DECOMPRESSED_READBACK_HASHED_AND_FSYNCED'")
    replace("            destination_payload_reread_hash_performed=False,restore_performed=False,startup_restore_qualified=False,","            destination_payload_reread_hash_performed=True,codec='zlib-level1',\n            total_compressed_bytes=progress['compressed_bytes_written'],maximum_compressed_bytes=job['maximum_compressed_bytes'],\n            restore_performed=False,startup_restore_qualified=False,")
    back=text
    for before,after in reversed(edits):assert back.count(after)==1;back=back.replace(after,before,1)
    assert back==original;ast.parse(text);args.output.mkdir(mode=0o700)
    source=args.output/'copy_verified_compressed_current_state_v1.py'
    with source.open('x')as f:f.write(text);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    report=dict(status='PREPARED_COMPRESSED_BACKUP_SOURCE_NOT_CPU_QUALIFIED',parent=p.pin(P),source=p.pin(source),functions=p.pin(functions),builder=p.pin(pathlib.Path(__file__).resolve()),exact_reverse_edit_proof=True,edits=[dict(before=x,after=y)for x,y in edits],original_owner_identity_scope_and_file_selection_kernels_unchanged=True,whole_state_backup_performed=False)
    target=args.output/'source-derivation.json'
    with target.open('x')as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    print(json.dumps(dict(source={k:report['source'][k]for k in ('path','sha256','bytes')},derivation=str(target))))
if __name__=='__main__':main()
