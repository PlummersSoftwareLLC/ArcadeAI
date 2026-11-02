#!/usr/bin/env python3
"""Root-only one-shot offline CPU analysis, with retained original exit evidence."""
import datetime, hashlib, json, os, subprocess, sys
from pathlib import Path
R=Path('/home/dave/source/repos/ArcadeAI')
RUN=R/'Robotron/logs/managed-learning-20261015/run-26'
P=RUN/'live8-actual-CE-analysis-source-preflight-20261017'
D=RUN/'live8-actual-CE-analysis-root-execution-reviewed1-20261017'
U='robotron-live8-actualCE-analysis-reviewed1-20261017.service'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def run(a):return subprocess.run(a,capture_output=True,text=True,timeout=15)
def main():
    action=sys.argv[1]
    if action=='launch':
        D.mkdir()
        assert 'LoadState=not-found' in run(['systemctl','--user','show',U,'-p','LoadState']).stdout
        assert sha(P/'future-argv.json')=='83c173993f3a5fafe37b2738f748ba8c2cd50423c1b4e483aeb485118ad14332'
        assert sha(P/'input-binding.json')=='0c2a528a3b1611b6e746e9ca09653297b62c750e35887bfaa1982dd8258351cf'
        args=json.loads((P/'future-argv.json').read_text())['analysis']['argv']
        tool=R/'Robotron/tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/offline_actual_ce_analysis_proposal/analyse_actual_ce.py'
        assert sha(tool)=='e4ffb0cb95aa4f426005cce351b11cb96b4af30339908183e1f61fbf728875bb'
        assert not Path(args[-1]).exists()
        tests=RUN/'live8-actualCE-analysis-guards-root-execution-20261017/root-result-review-and-release.json'
        t=json.loads(tests.read_text());assert t['status']=='PASS' and t['original_exit']==0 and t['measured']['test_methods']==10
        cmd=['systemd-run','--user','--unit='+U,'--property=Type=exec','--property=RemainAfterExit=yes','--property=CPUQuota=200%','--property=MemoryMax=3G','--property=TasksMax=128','--property=RuntimeMaxSec=120','--property=TimeoutStopSec=5','--property=WorkingDirectory='+str(R),'--property=StandardOutput=append:'+str(D/'stdout.txt'),'--property=StandardError=append:'+str(D/'stderr.txt')]+args
        save(D/'root-launch-intent.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),argv=cmd,source_sha256=sha(Path(__file__)),input_binding_sha256=sha(P/'input-binding.json'),tests_sha256=sha(tests),no_live_actions=True))
        with (D/Path(__file__).name).open('xb') as f:f.write(Path(__file__).read_bytes());os.fchmod(f.fileno(),0o444)
        c=run(cmd);save(D/'root-launch-return.json',dict(returncode=c.returncode,stdout=c.stdout,stderr=c.stderr));assert c.returncode==0,c.stderr
        print(json.dumps(dict(launched=True,unit=U)))
    elif action=='archive':
        c=run(['systemctl','--user','show',U]);assert c.returncode==0
        fields=dict(x.split('=',1) for x in c.stdout.splitlines() if '=' in x)
        assert fields['SubState'] in ('exited','failed','dead') and int(fields['ExecMainPID'])>0
        artifacts={}
        for name,out in [('original-unit-show.txt',c.stdout),('original-unit-cat.txt',run(['systemctl','--user','cat',U]).stdout),('original-invocation-journal.txt',run(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+fields['InvocationID'],'--no-pager','-o','short-precise']).stdout)]:
            p=D/name
            with p.open('x') as f:f.write(out);os.fchmod(f.fileno(),0o444)
            artifacts[name]=sha(p)
        save(D/'root-original-terminal-archive.json',dict(original_pid=int(fields['ExecMainPID']),original_invocation=fields['InvocationID'],original_exec_code=fields['ExecMainCode'],original_exit=int(fields['ExecMainStatus']),original_result=fields['Result'],memory_peak=fields.get('MemoryPeak'),cpu_usage_nsec=fields.get('CPUUsageNSec'),artifacts=artifacts))
        stop=run(['systemctl','--user','stop',U]);assert stop.returncode==0,stop.stderr
        if fields['Result']!='success':
            probe=run(['systemctl','--user','show',U,'-p','LoadState'])
            if 'LoadState=not-found' not in probe.stdout:
                reset=run(['systemctl','--user','reset-failed',U]);assert reset.returncode==0,reset.stderr
        outcome=dict(status='PASS' if fields['ExecMainCode']=='1' and fields['ExecMainStatus']=='0' and fields['Result']=='success' else 'FAILED',original_pid=int(fields['ExecMainPID']),original_invocation=fields['InvocationID'],original_exit=int(fields['ExecMainStatus']),original_exec_code=fields['ExecMainCode'],original_result=fields['Result'],original_archived_before_release=True,stop_returncode=stop.returncode)
        save(D/'root-result-review-and-release.json',outcome);print(json.dumps(outcome))
    else:raise ValueError(action)
if __name__=='__main__':main()
