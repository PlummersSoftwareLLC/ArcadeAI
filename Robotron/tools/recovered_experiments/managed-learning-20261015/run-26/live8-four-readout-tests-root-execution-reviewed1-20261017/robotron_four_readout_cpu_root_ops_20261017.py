#!/usr/bin/env python3
"""Root retained CPU tests and decode of the eight conditional weight readouts."""
import datetime,hashlib,json,os,re,subprocess,sys
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI');RUN=R/'Robotron/logs/managed-learning-20261015/run-26'
PRE=RUN/'live8-four-readout-analysis-source-preflight-20261017'
SRC=R/'Robotron/tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/four_readout_analysis_proposal'
UNITS={'tests':'robotron-live8-four-readout-guards-reviewed1-20261017.service','analysis':'robotron-live8-four-readout-analysis-reviewed1-20261017.service'}
DIRS={kind:RUN/('live8-four-readout-'+kind+'-root-execution-reviewed1-20261017') for kind in UNITS}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(a):return subprocess.run(a,capture_output=True,text=True,timeout=15)
def fields(t):return dict(x.split('=',1) for x in t.splitlines() if '=' in x)
def launch(kind):
    d=DIRS[kind];u=UNITS[kind];assert sha(PRE/'future-argv.json')=='9b3f9eb150292b9a4df23e8a5fae3b479f498b995f5cef399934703680014248'
    assert sha(SRC/'preparation-manifest.json')=='2323334270193c323a0b923153ef1688d0dc102ec5880af39e8f8c03fb6ce098'
    for name,item in json.loads((SRC/'preparation-manifest.json').read_text())['files'].items():assert sha(SRC/name)==item['sha256'],name
    assert sha(PRE/'input-binding.json')=='99672e1d9c50fb26cbf1b4ecd866f595669e9e9ede771abcc619fc3943003bea'
    assert 'LoadState=not-found' in call(['systemctl','--user','show',u,'-p','LoadState']).stdout
    plan=json.loads((PRE/'future-argv.json').read_text());d.mkdir()
    if kind=='analysis':
        test=json.loads((DIRS['tests']/'root-result-review-and-release.json').read_text());assert test['status']=='PASS' and test['original_exit']==0 and test['test_methods']==12
        assert not Path(plan[kind]['argv'][-1]).exists()
    envelope=plan[kind]['envelope'];argv=['/usr/bin/env']
    for name in plan['unset_env']:argv+=['-u',name]
    argv+=[name+'='+value for name,value in plan['env'].items()]+plan[kind]['argv']
    command=['systemd-run','--user','--unit='+u,'--property=Type=exec','--property=RemainAfterExit=yes','--property=CPUQuota=200%','--property=MemoryMax='+str(envelope['memory_bytes']),'--property=TasksMax='+str(envelope['tasks']),'--property=RuntimeMaxSec='+str(envelope['runtime_s']),'--property=TimeoutStopSec=5','--property=WorkingDirectory='+str(R),'--property=StandardOutput=append:'+str(d/'stdout.txt'),'--property=StandardError=append:'+str(d/'stderr.txt')]+argv
    save(d/'root-launch-intent.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),kind=kind,argv=command,source_sha256=sha(Path(__file__)),tool_sha256=sha(SRC/'analyse_four_readouts.py'),binding_sha256=sha(PRE/'input-binding.json'),actual_original_CE_comparison_stays_failed_all8=True))
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
    if kind=='tests':passed=passed and count==12 and '\nOK\n' in (d/'stderr.txt').read_text()
    result=dict(status='PASS' if passed else 'FAILED',kind=kind,original_pid=observed['pid'],original_invocation=observed['invocation_id'],original_exit=original['original_exit'],test_methods=count,original_archived_before_release=True)
    save(d/'root-result-review-and-release.json',result);print(json.dumps(result))
if __name__=='__main__':
    action,kind=sys.argv[1:];assert kind in UNITS;{'launch':launch,'archive':archive}[action](kind)
