#!/usr/bin/env python3
"""Root retained-unit launch/archive. No trainer or actor calls in this carrier."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO=Path('/home/dave/source/repos/ArcadeAI')
RUN=REPO/'Robotron/logs/managed-learning-20261015/run-26'
PROPOSAL=REPO/'Robotron/tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/live8_maintenance_proposal'
PREP=RUN/'live8-owned-maintenance-root-preparation-reviewed1-20261017'
UNITS=dict(tests='robotron-live8-maintenance-guards-reviewed1-20261017.service',maintenance='robotron-live8-maintenance-reviewed1-20261017.service')
DIRS=dict(tests=RUN/'live8-maintenance-guards-root-execution-reviewed1-20261017',maintenance=RUN/'live8-owned-maintenance-root-execution-reviewed1-20261017')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def publish(p,v):
    with p.open('x') as f:
        json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(argv):return subprocess.run(argv,capture_output=True,text=True,timeout=15)
def launch(kind):
    d=DIRS[kind];d.mkdir();unit=UNITS[kind]
    probe=call(['systemctl','--user','show',unit,'-p','LoadState','-p','MainPID'])
    assert 'LoadState=not-found' in probe.stdout,probe.stdout
    # Reviewed source hashes are independently checked against the frozen bundle.
    manifest=json.loads((PROPOSAL/'preparation-manifest.json').read_text())
    for name,record in manifest['files'].items():
        assert sha(PROPOSAL/name)==record['sha256'],name
    if kind=='tests':
        argv=['/usr/bin/python3','-B','-m','unittest','-v',
          'Robotron.tools.kl_priority_mixture_proposal.recomputed_ce_capture_proposal.live8_maintenance_proposal.test_live8_maintenance',
          'Robotron.tools.kl_priority_mixture_proposal.recomputed_ce_capture_proposal.live8_maintenance_proposal.test_bank_state_revision2']
        properties=['MemoryMax=512M','RuntimeMaxSec=60','TimeoutStopSec=10','TasksMax=64']
    else:
        job=PREP/'root-job.json';controller=PROPOSAL/'run_live8_maintenance.py'
        argv=['/usr/bin/python3','-B',str(controller),'--launch','--job',str(job),
              '--expected-job-sha256',sha(job),'--expected-controller-sha256',sha(controller)]
        properties=['MemoryMax=4G','RuntimeMaxSec=4800','TimeoutStopSec=900','TasksMax=128','KillSignal=SIGINT','SendSIGKILL=no']
    base=['systemd-run','--user','--unit='+unit,'--property=Type=oneshot','--property=RemainAfterExit=yes',
          '--property=CPUQuota=200%','--property=WorkingDirectory='+str(REPO),
          '--property=StandardOutput=append:'+str(d/'stdout.txt'),'--property=StandardError=append:'+str(d/'stderr.txt'),
          '--setenv=CUDA_VISIBLE_DEVICES=','--setenv=PYTHONDONTWRITEBYTECODE=1','--setenv=OMP_NUM_THREADS=2',
          '--setenv=MKL_NUM_THREADS=2','--setenv=OPENBLAS_NUM_THREADS=2']
    if kind=='maintenance':base+=['--on-active=3s','--timer-property=AccuracySec=100ms']
    base+=['--property='+x for x in properties]
    command=base+argv
    publish(d/'root-launch-intent.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),kind=kind,unit=unit,argv=command,
            preparation_manifest_sha256=sha(PROPOSAL/'preparation-manifest.json'),carrier_source_sha256=sha(Path(__file__))))
    result=call(command)
    publish(d/'root-launch-return.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
    assert result.returncode==0,result.stderr
    print(json.dumps(dict(kind=kind,unit=unit,directory=str(d),launched=True)))
def archive(kind):
    d=DIRS[kind];unit=UNITS[kind]
    show=call(['systemctl','--user','show',unit]);assert show.returncode==0
    fields=dict(line.split('=',1) for line in show.stdout.splitlines() if '=' in line)
    assert fields['ExecMainCode']=='1' and fields['SubState'] in ('exited','failed','dead'),fields.get('SubState')
    assert fields['InvocationID'] and int(fields['ExecMainPID'])>0
    (d/'original-unit-show.txt').write_text(show.stdout)
    cat=call(['systemctl','--user','cat',unit]);(d/'original-unit-cat.txt').write_text(cat.stdout)
    journal=call(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+fields['InvocationID'],'--no-pager','-o','short-precise'])
    (d/'original-invocation-journal.txt').write_text(journal.stdout)
    if kind=='tests':
        assert fields['ExecMainStatus']=='0' and fields['Result']=='success'
        text=(d/'stderr.txt').read_text();assert '\nOK\n' in text,text[-3000:]
        import re
        match=re.search(r'Ran (\d+) tests? in ',text);assert match
        measured=dict(test_methods=int(match.group(1)),result='PASS')
    else:
        result_path=RUN/'live8-owned-maintenance-reviewed1-20261017/result.json'
        actual=json.loads(result_path.read_text())
        measured=dict(status=actual['status'],capture_complete=actual['capture_complete'],manual_recovery_required=actual['manual_recovery_required'],
                      result=str(result_path),result_sha256=sha(result_path))
    publish(d/'root-original-terminal-archive.json',dict(kind=kind,original_invocation=fields['InvocationID'],original_pid=int(fields['ExecMainPID']),
            original_exec_code=fields['ExecMainCode'],original_exit=int(fields['ExecMainStatus']),original_result=fields['Result'],
            archived_files={p.name:sha(p) for p in d.iterdir() if p.is_file()},measured=measured))
    if kind=='maintenance':
        stopped_timer=call(['systemctl','--user','stop',unit.removesuffix('.service')+'.timer'])
        assert stopped_timer.returncode==0,stopped_timer.stderr
    stopped=call(['systemctl','--user','stop',unit]);assert stopped.returncode==0,stopped.stderr
    publish(d/'root-result-review-and-release.json',dict(status='PASS' if fields['ExecMainStatus']=='0' else 'FAILED',kind=kind,
       original_invocation=fields['InvocationID'],original_pid=int(fields['ExecMainPID']),original_exit=int(fields['ExecMainStatus']),
       original_archived_before_release=True,unit_stop_returncode=stopped.returncode,measured=measured))
    print(json.dumps(dict(released=True,kind=kind,**measured)))
if __name__=='__main__':
    action,kind=sys.argv[1:]
    assert kind in UNITS
    {'launch':launch,'archive':archive}[action](kind)
