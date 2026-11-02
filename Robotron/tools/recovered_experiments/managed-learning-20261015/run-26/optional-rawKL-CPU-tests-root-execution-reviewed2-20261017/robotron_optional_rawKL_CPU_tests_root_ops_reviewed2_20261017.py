#!/usr/bin/env python3
"""Root bounded448 capture-preparer guards; no candidate data access."""
import datetime,hashlib,json,os,re,subprocess,sys
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');RUN=R/'Robotron/logs/managed-learning-20261015/run-26'
PRE=R/'Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
SRC=PRE
UNITS={'tests':'robotron-optional-rawKL-CPU-guards-reviewed2-20261017.service'}
DIRS={kind:RUN/('optional-rawKL-CPU-'+kind+'-root-execution-reviewed2-20261017') for kind in UNITS}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(a):return subprocess.run(a,capture_output=True,text=True,timeout=15)
def fields(t):return dict(x.split('=',1) for x in t.splitlines() if '=' in x)
def launch(kind):
    d=DIRS[kind];u=UNITS[kind]
    assert sha(SRC/'preparation-manifest-reviewed2.json')=='2f083c4327540380498f10f7e3274b7cd1c9a1c2d4c54d9f5f8262cfbb2afd9a'
    assert sha(SRC/'preparation-manifest.json')=='1144139f168292b7c0648fcc76d24a945d7d7f295ec14d5f304f70d5ca5dfe11'
    manifest=json.loads((SRC/'preparation-manifest-reviewed2.json').read_text())
    for name,item in {**manifest['unchanged_original_bundle_pins'],**manifest['new_files']}.items():assert sha(SRC/name)==item['sha256'],name
    assert 'LoadState=not-found' in call(['systemctl','--user','show',u,'-p','LoadState']).stdout
    d.mkdir();envelope=dict(memory_bytes=3<<30,tasks=128,runtime_s=120)
    argv=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','ROBOTRON_ALLOW_PRIORITY_CPU=1','OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','MKL_NUM_THREADS=2',str(R/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B','-c',"import importlib.util,unittest,sys;from pathlib import Path;root=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal');suite=unittest.TestSuite();\nfor name in ['test_priority_phase','test_priority_routes_reviewed2']:\n spec=importlib.util.spec_from_file_location(name,root/(name+'.py'));module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))\nresult=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(0 if result.wasSuccessful() else 1)"]
    command=['systemd-run','--user','--unit='+u,'--property=Type=exec','--property=RemainAfterExit=yes','--property=CPUQuota=200%','--property=MemoryMax='+str(envelope['memory_bytes']),'--property=MemorySwapMax=0','--property=TasksMax='+str(envelope['tasks']),'--property=RuntimeMaxSec='+str(envelope['runtime_s']),'--property=TimeoutStopSec=5','--property=WorkingDirectory='+str(R),'--property=StandardOutput=append:'+str(d/'stdout.txt'),'--property=StandardError=append:'+str(d/'stderr.txt')]+argv
    save(d/'root-launch-intent.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),kind=kind,argv=command,source_sha256=sha(Path(__file__)),candidate_training_sha256=sha(SRC/'training.py'),bundle_sha256=sha(SRC/'preparation-manifest-reviewed2.json'),candidate_data_access=False))
    with (d/Path(__file__).name).open('xb') as f:f.write(Path(__file__).read_bytes());os.fchmod(f.fileno(),0o444)
    out=call(command);save(d/'root-launch-return.json',dict(returncode=out.returncode,stdout=out.stdout,stderr=out.stderr));assert out.returncode==0,out.stderr
    f=fields(call(['systemctl','--user','show',u]).stdout);pid=int(f['ExecMainPID']);assert pid>0 and f['InvocationID'] and f['NRestarts']=='0' and f['Restart']=='no'
    live=int(f['MainPID'])==pid;save(d/'root-observed-original-identity.json',dict(pid=pid,invocation_id=f['InvocationID'],observed_live=live,start_ticks=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19] if live else None))
    print(json.dumps(dict(launched=True,kind=kind,unit=u,pid=pid,invocation_id=f['InvocationID'])))
def archive(kind):
    d=DIRS[kind];u=UNITS[kind];out=call(['systemctl','--user','show',u]);assert out.returncode==0;f=fields(out.stdout);observed=json.loads((d/'root-observed-original-identity.json').read_text())
    assert f['MainPID']=='0' and f['SubState'] in ('exited','dead','failed') and int(f['ExecMainPID'])==observed['pid'] and f['InvocationID']==observed['invocation_id'] and f['NRestarts']=='0'
    for name,value in [('original-unit-show.txt',out.stdout),('original-unit-cat.txt',call(['systemctl','--user','cat',u]).stdout),('original-invocation-journal.txt',call(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+f['InvocationID'],'--no-pager','-o','short-precise']).stdout)]:
        with (d/name).open('x') as stream:stream.write(value);os.fchmod(stream.fileno(),0o444)
    count=None
    if kind=='tests':
        match=re.search(r'Ran (\d+) tests? in ',(d/'stderr.txt').read_text());count=int(match.group(1)) if match else None
    original=dict(kind=kind,original_pid=observed['pid'],original_invocation=observed['invocation_id'],original_exec_code=int(f['ExecMainCode']),original_exit=int(f['ExecMainStatus']),original_result=f['Result'],test_methods=count,memory_peak=f.get('MemoryPeak'),cpu_usage_nsec=f.get('CPUUsageNSec'),archive_files={q.name:sha(q) for q in d.iterdir() if q.is_file()})
    save(d/'root-original-terminal-archive.json',original)
    stopped=call(['systemctl','--user','stop',u]);assert stopped.returncode==0,stopped.stderr
    if f['Result']!='success' and 'LoadState=not-found' not in call(['systemctl','--user','show',u,'-p','LoadState']).stdout:
        reset=call(['systemctl','--user','reset-failed',u]);assert reset.returncode==0,reset.stderr
    passed=original['original_exec_code']==1 and original['original_exit']==0 and original['original_result']=='success'
    if kind=='tests':passed=passed and count==21 and '\nOK\n' in (d/'stderr.txt').read_text()
    result=dict(status='PASS' if passed else 'FAILED',kind=kind,original_pid=observed['pid'],original_invocation=observed['invocation_id'],original_exit=original['original_exit'],test_methods=count,original_archived_before_release=True)
    save(d/'root-result-review-and-release.json',result);print(json.dumps(result))
if __name__=='__main__':
    action,kind=sys.argv[1:];assert kind in UNITS;{'launch':launch,'archive':archive}[action](kind)
