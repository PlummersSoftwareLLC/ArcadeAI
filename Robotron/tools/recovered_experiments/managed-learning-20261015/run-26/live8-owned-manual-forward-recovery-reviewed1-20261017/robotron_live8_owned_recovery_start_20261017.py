#!/usr/bin/env python3
"""Start the ordinary before-source trainer from the newly verified latest."""
import importlib.util,json,os,subprocess,sys,time
from pathlib import Path
REPO=Path('/home/dave/source/repos/ArcadeAI');RUN=REPO/'Robotron/logs/managed-learning-20261015/run-26';D=RUN/'live8-owned-manual-forward-recovery-reviewed1-20261017'
def call(*args):return subprocess.run(list(args),capture_output=True,text=True,check=True,timeout=10)
def main():
    j=json.loads((RUN/'live8-owned-maintenance-root-preparation-reviewed3-20261017/root-job.json').read_text())
    sys.dont_write_bytecode=True;sys.path.insert(0,str(REPO/'Robotron/tools'))
    path=Path(j['helper_pins']['controller']['path']);spec=importlib.util.spec_from_file_location('root_owned_recovery_start',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    unit='robotron-live8-owned-recovery-CPU-reviewed1-20261017.service';show=call('systemctl','--user','show',unit).stdout;fields=dict(line.split('=',1) for line in show.splitlines() if '=' in line)
    assert fields['ExecMainCode']=='1' and fields['ExecMainStatus']=='0' and fields['Result']=='success'
    report_path=D/'cpu-output/cpu-verification.json';report=json.loads(report_path.read_text());job=json.loads((D/'cpu-job.json').read_text());assert report['status']=='PASS' and report['mode']=='stopped_latest' and report['root_job']==job
    assert m.fingerprint(job['source']['path'])==job['source'];assert all(report['clocks'][key]>=job['clock_floor'][key] for key in m.CLOCKS)
    (D/'CPU-original-unit-show.txt').write_text(show);(D/'CPU-original-unit-cat.txt').write_text(call('systemctl','--user','cat',unit).stdout)
    (D/'CPU-original-invocation-journal.txt').write_text(call('journalctl','--user','_SYSTEMD_INVOCATION_ID='+fields['InvocationID'],'--no-pager').stdout)
    m.publish(D/'CPU-original-exit-review.json',dict(status='PASS',original_invocation=fields['InvocationID'],original_pid=int(fields['ExecMainPID']),original_exec_code=1,original_exit=0,result='success',CPU_report=m.fingerprint(report_path),saved_clocks=report['clocks']))
    call('systemctl','--user','stop',unit)
    for path,sha in j['before']['bindings']['source_hashes'].items():assert m.fingerprint(path)['sha256']==sha,path
    assert not Path(j['sources'][-1]['destination']).exists() if j['sources'][-1]['before'] is None else True
    for path,sha in j['before']['bindings']['control_hashes'].items():assert m.fingerprint(path)['sha256']==sha,path
    assert not Path(j['original_dropin']['path']).exists()
    pid=j['before']['bindings']['worker']['trainer']['pid'];assert not Path('/proc',str(pid)).exists()
    current=call('systemctl','--user','show',j['trainer_unit'],'-p','MainPID','-p','ActiveState').stdout
    assert 'MainPID=0' in current and 'ActiveState=inactive' in current
    group=Path('/sys/fs/cgroup')/j['before']['trainer']['ControlGroup'].lstrip('/')
    assert not group.exists() or not any(p.read_text().split() for p in group.rglob('cgroup.procs'))
    bank_path=Path(j['helper_pins']['bank_state']['path']);s=importlib.util.spec_from_file_location('root_owned_recovery_banks',bank_path);banks=importlib.util.module_from_spec(s);s.loader.exec_module(banks)
    disk=json.loads((D/'stopped-disk-state.json').read_text());banks.assert_unchanged(disk,j['bank_spec'])
    for actor in j['before']['bindings']['actors']:
        text=Path('/proc',str(actor['pid']),'stat').read_text();assert int(text.rsplit(')',1)[1].split()[19])==actor['starttime_ticks']
    logs={path:dict(**binding,offset=Path(path).stat().st_size) for path,binding in j['before']['bindings']['logs'].items()}
    m.publish(D/'root-owned-normal-start-request.json',dict(owned_start_requested=True,unit=j['trainer_unit'],old_trainer=job['stopped_latest']['old_trainer'],latest=job['source'],verified_saved_clocks=report['clocks'],source_phase='before',capture_flag=False,root_job_sha256=m.fingerprint(RUN/'live8-owned-maintenance-root-preparation-reviewed3-20261017/root-job.json')['sha256'],log_boundary=logs,banks_counts={name:bank['counts'] for name,bank in disk['banks'].items()},limitations='Ordinary restart with post-save tail limits; no exact four-clock first-attempt observer proof on before-source boot.'))
    result=call('systemctl','--user','start','--no-block',j['trainer_unit']);m.publish(D/'root-owned-normal-start-return.json',dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        current=call('systemctl','--user','show',j['trainer_unit'],'-p','MainPID','-p','InvocationID','-p','ControlGroup','-p','ActiveState').stdout
        values=dict(line.split('=',1) for line in current.splitlines() if '=' in line)
        if int(values.get('MainPID','0')):
            pid=int(values['MainPID']);stat=Path('/proc',str(pid),'stat').read_text();owner=dict(pid=pid,starttime_ticks=int(stat.rsplit(')',1)[1].split()[19]),invocation_id=values['InvocationID'],cgroup=values['ControlGroup'],authorized_start_adopted=True,unknown_replacement_adopted=False)
            m.publish(D/'root-owned-normal-new-trainer.json',owner);print(json.dumps(dict(started=True,owner=owner,clocks=report['clocks'],bank_counts={name:bank['counts'] for name,bank in disk['banks'].items()})));return
        time.sleep(.1)
    raise RuntimeError('Requested normal start did not publish an owned PID within10s')
if __name__=='__main__':main()
