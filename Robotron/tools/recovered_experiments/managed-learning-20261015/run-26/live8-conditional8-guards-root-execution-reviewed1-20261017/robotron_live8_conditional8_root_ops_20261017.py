#!/usr/bin/env python3
"""Root retained-unit carrier for the reviewed conditional8 bundle."""
import argparse,datetime,hashlib,json,os,re,subprocess
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');G=R/'Robotron';RUN=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/live8_recompute_proposal'
UNITS={'tests':'robotron-live8-conditional8-guards-reviewed1-20261017.service','gpu':'robotron-snapshot-smoke-live8-conditional8-reviewed1-20261017.service'}
DIRS={'tests':RUN/'live8-conditional8-guards-root-execution-reviewed1-20261017','gpu':RUN/'live8-conditional8-root-execution-reviewed1-20261017'}
OUT=RUN/'live8-conditional8-reconstruction-reviewed1-20261017'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(a):return subprocess.run(a,capture_output=True,text=True,timeout=15)
def fields(t):return dict(x.split('=',1) for x in t.splitlines() if '=' in x)
def launch(args):
    kind=args.kind;d=DIRS[kind];u=UNITS[kind];manifest=P/'preparation-manifest.json'
    assert args.bundle_sha and sha(manifest)==args.bundle_sha
    bundle=json.loads(manifest.read_text())
    for name,item in bundle['files'].items():
        path=P/name;assert path.is_file() and not path.is_symlink() and path.resolve().parent==P.resolve() and sha(path)==item['sha256'],name
    assert 'LoadState=not-found' in call(['systemctl','--user','show',u,'-p','LoadState']).stdout
    d.mkdir()
    if kind=='tests':
        assert args.expected_tests and args.expected_tests>43
        argv=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','MKL_NUM_THREADS=2','/usr/bin/python3','-B','-m','unittest','-v']
        argv+=['Robotron.tools.kl_priority_mixture_proposal.recomputed_ce_capture_proposal.live8_recompute_proposal.'+name for name in ('test_process_scan','test_storage_watcher','test_reconstruction_contract')]
        properties=['MemoryMax=512M','TasksMax=64','RuntimeMaxSec=60','TimeoutStopSec=10']
    else:
        t=json.loads((DIRS['tests']/'root-result-review-and-release.json').read_text());assert t['status']=='PASS' and t['original_exit']==0 and t['bundle_sha256']==args.bundle_sha
        assert not OUT.exists()
        state=json.loads((RUN.parent/'state.json').read_text());gate=state['next_checkpoint'];assert gate['status']=='paused_for_conditional8_owned_window' and gate['target_learner_frames']==452629023 and gate['original_deadline_unix_s']==1792245505.2003896
        argv=[str(R/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',str(P/'cuda_trace_parent.py'),'--directory',str(OUT),'--launch']
        properties=['MemoryMax=16G','MemorySwapMax=0','TasksMax=128','RuntimeMaxSec=660','TimeoutStopSec=90','KillSignal=SIGINT','SendSIGKILL=no','Delegate=cpu memory pids','DelegateSubgroup=snapshot-supervisor']
    command=['systemd-run','--user','--unit='+u,'--property=Type=exec','--property=RemainAfterExit=yes','--property=CPUQuota=200%','--property=WorkingDirectory='+str(R),'--property=StandardOutput=append:'+str(d/'stdout.txt'),'--property=StandardError=append:'+str(d/'stderr.txt')]+['--property='+x for x in properties]
    if kind=='gpu':command+=['--on-active=3s','--timer-property=AccuracySec=100ms']
    command+=argv
    save(d/'root-launch-intent.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),kind=kind,unit=u,argv=command,bundle_sha256=args.bundle_sha,expected_tests=args.expected_tests,carrier_pid=os.getpid(),carrier_source_sha256=sha(Path(__file__)),original_terminal_must_be_archived_before_release=True))
    with (d/Path(__file__).name).open('xb') as f:f.write(Path(__file__).read_bytes());os.fchmod(f.fileno(),0o444)
    out=call(command);save(d/'root-launch-return.json',dict(returncode=out.returncode,stdout=out.stdout,stderr=out.stderr));assert out.returncode==0,out.stderr
    print(json.dumps(dict(launched=True,kind=kind,unit=u,output=str(OUT) if kind=='gpu' else str(d))))
def archive(args):
    kind=args.kind;d=DIRS[kind];u=UNITS[kind];out=call(['systemctl','--user','show',u]);assert out.returncode==0;f=fields(out.stdout)
    assert int(f['MainPID'])==0 and int(f['ExecMainPID'])>0 and f['InvocationID'] and f['SubState'] in ('exited','dead','failed')
    for name,value in [('original-unit-show.txt',out.stdout),('original-unit-cat.txt',call(['systemctl','--user','cat',u]).stdout),('original-invocation-journal.txt',call(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+f['InvocationID'],'--no-pager','-o','short-precise']).stdout)]:
        with (d/name).open('x') as stream:stream.write(value);os.fchmod(stream.fileno(),0o444)
    intent=json.loads((d/'root-launch-intent.json').read_text());observed_tests=None
    if kind=='tests':
        text=(d/'stderr.txt').read_text();match=re.search(r'Ran (\d+) tests? in ',text);observed_tests=int(match.group(1)) if match else None
    receipt=dict(kind=kind,original_pid=int(f['ExecMainPID']),original_invocation=f['InvocationID'],original_exec_code=int(f['ExecMainCode']),original_exit=int(f['ExecMainStatus']),original_result=f['Result'],bundle_sha256=intent['bundle_sha256'],observed_tests=observed_tests,memory_peak=f.get('MemoryPeak'),cpu_usage_nsec=f.get('CPUUsageNSec'),archived_files={q.name:sha(q) for q in d.iterdir() if q.is_file()})
    save(d/'root-original-terminal-archive.json',receipt)
    print(json.dumps(receipt|{'archived_files_count':len(receipt['archived_files'])},default=str))
def release(args):
    kind=args.kind;d=DIRS[kind];u=UNITS[kind];a=json.loads((d/'root-original-terminal-archive.json').read_text());f=fields(call(['systemctl','--user','show',u]).stdout)
    assert f['InvocationID']==a['original_invocation'] and int(f['ExecMainPID'])==a['original_pid'] and int(f['MainPID'])==0
    if kind=='gpu':
        proof=json.loads((d/'root-owned-terminal-cleanup-review.json').read_text());assert proof['owned_cleanup_complete'] and proof['original_invocation']==a['original_invocation'] and proof['original_pid']==a['original_pid']
        timer=u.removesuffix('.service')+'.timer';show=call(['systemctl','--user','show',timer,'-p','LoadState','-p','Triggers'])
        if 'LoadState=not-found' not in show.stdout:
            assert 'Triggers='+u in show.stdout;stopped=call(['systemctl','--user','stop',timer]);assert stopped.returncode==0,stopped.stderr
    stop=call(['systemctl','--user','stop',u]);assert stop.returncode==0,stop.stderr
    if a['original_result']!='success' and 'LoadState=not-found' not in call(['systemctl','--user','show',u,'-p','LoadState']).stdout:
        reset=call(['systemctl','--user','reset-failed',u]);assert reset.returncode==0,reset.stderr
    passed=a['original_exec_code']==1 and a['original_exit']==0 and a['original_result']=='success'
    if kind=='tests':
        intent=json.loads((d/'root-launch-intent.json').read_text());passed=passed and a['observed_tests']==intent['expected_tests'] and '\nOK\n' in (d/'stderr.txt').read_text()
    receipt=dict(status='PASS' if passed else 'FAILED',kind=kind,original_pid=a['original_pid'],original_invocation=a['original_invocation'],original_exit=a['original_exit'],original_exec_code=a['original_exec_code'],original_result=a['original_result'],bundle_sha256=a['bundle_sha256'],observed_tests=a['observed_tests'],original_terminal_archived_before_release=True,stop_returncode=stop.returncode)
    save(d/'root-result-review-and-release.json',receipt);print(json.dumps(receipt))
def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('launch','archive','release'));parser.add_argument('kind',choices=('tests','gpu'));parser.add_argument('--bundle-sha');parser.add_argument('--expected-tests',type=int);args=parser.parse_args();globals()[args.action](args)
if __name__=='__main__':main()
