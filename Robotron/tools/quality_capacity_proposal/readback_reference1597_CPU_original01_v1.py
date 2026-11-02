"""Once-only independent readback of original reference1597 metadata CPU21."""
from pathlib import Path
import ast,hashlib,importlib.util,json,os,shlex,re,stat,subprocess
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');H=G/'tools/quality_capacity_proposal';P=G/'logs/managed-learning-20261015/run-26/post-production-profile06-fresh-main-next8M-original01-preparation-20261021';C=P/'reference1597-metadata-CPU-original01'
def module(path,sha,name):
 assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 reader=module(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','_CPU21_reader')
 runtime=module(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_CPU21_archives')
 control=module(H/'control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_CPU21_control')
 pin=reader.pin;read=lambda e,as_json=True:reader.read_pin(e,as_json=as_json)
 prep_pin=pin(C/'source-and-controller-preparation.json');prep=read(prep_pin);job=read(prep['job']);config=read(prep['config']);owner_pin=pin(C/'controller-execution/root-original-identity.json');owner=read(owner_pin);closure_pin=pin(C/'controller-execution/root-original-result-and-owned-release.json');closure=read(closure_pin)
 fields=runtime.archived_closure(closure,owner,read,exit_zero=True)
 assert runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30) and fields['MemorySwapMax']=='0' and runtime.duration_seconds(fields['RuntimeMaxUSec'])==180 and fields['TasksMax']=='128' and runtime.duration_seconds(fields['TimeoutStopUSec'])==5 and fields['SendSIGKILL']==fields['Restart']=='no'
 expected=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+config['argv']
 match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart']);assert match and shlex.split(match[1])==expected and config['unit']==owner['unit']
 for unit in [owner['unit'],owner['timer']]:assert control.show(unit)['LoadState']=='not-found'
 assert not Path('/proc',str(owner['pid'])).exists()
 report_pin=pin(job['report']);report=read(report_pin);assert report['status']=='PASS' and report['tests']==21 and all(report[k]==0 for k in ['failures','errors','skipped']) and report['tested_sources']==job['sources']==prep['sources']
 for entry in job['sources'].values():assert pin(entry['path'])==entry;read(entry,False)
 stderr=Path(config['output'])/'stderr.txt';stdout=Path(config['output'])/'stdout.txt';payload_error=stderr.read_bytes();payload_out=stdout.read_bytes();assert b'Ran 21 tests' in payload_error and payload_error.rstrip().endswith(b'OK') and b'FAILED' not in payload_error
 summary=json.loads(payload_out);assert summary['status']=='PASS' and summary['tests']==21 and summary['report']==report_pin
 archives={}
 for name,p in [('original_payload_stderr',stderr),('original_payload_stdout',stdout)]:
  before=pin(p);raw=p.read_bytes();assert pin(p)==before
  dest=C/(name+'.readonly.txt')
  with dest.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
  archives[name]=dict(original=before,archive=pin(dest));assert pin(p)==before
 result=dict(status='ACTUAL_REFERENCE1597_METADATA_CPU21_ALL6_AND_RELEASE_PASS',source=pin(Path(__file__)),preparation=prep_pin,job=prep['job'],config=prep['config'],original_owner=owner_pin,original_closure=closure_pin,actual_tests=report_pin,tested_sources=job['sources'],original_payload_archives=archives,all6_original_descriptors_verified=True,exact_owned_service_and_timer_released=True,original_exit=0,original_tests_repeated=False,scientific_evaluation_started=False,quality_qualified=False,promotion=False)
 p=C/'root-independent-readback.json'
 with p.open('x')as f:json.dump(result,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 print(json.dumps(dict(status=result['status'],readback=pin(p))))
if __name__=='__main__':main()
