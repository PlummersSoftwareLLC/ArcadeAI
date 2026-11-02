"""Close only the already observed original indexed benchmark SIGTERM timeout.

Read/archive actual termination without normalizing it into an exit code, then
release only its exact absent-process service/timer identities. No payload retry,
new observation adoption, process signals or changes to any production unit.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
D=G/'logs/managed-learning-20261015/run-26/indexed-main-health-v3-fullscope-CPU-original01-preparation-20261023'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    h=load('_signal_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    controller=G/'tools/training_connection_lifecycle_proposal_20261023/control_owned_cap_live600_v1.py'
    assert hashlib.sha256(controller.read_bytes()).hexdigest()=='94a398ac68abdbf26cf13b14bbec27d9692a3f250b3a892c70d8bfccbe662dca'
    c=load('_signal_c',controller);config=json.loads((D/'controller-config.json').read_text());original=D/'execution-original01'
    owner=json.loads((original/'root-original-identity.json').read_text());observer=json.loads((original/'root-original-result-and-owned-release.json').read_text())
    assert observer['status']=='ORIGINAL_OUTCOME_PRESERVED_OWNED_RELEASE_INCOMPLETE'and observer['original_exit']is None
    assert owner['pid']==2940394 and owner['starttime_ticks']==89332523 and owner['invocation_id']=='4089f42f322b4be8a70fa78fc0fff99a'
    assert config['unit']==owner['unit']=='robotron-indexed-main-health-v3-fullscope-CPU-original01-20261023.service'
    for pin in config['pins']:assert c.pin(pin['path'])==pin
    out=D/'signal-timeout-original-terminal-closeout';out.mkdir(mode=0o700)
    def command(label,argv):return c.command(out,label,argv)
    def absent_birth():
        path=Path('/proc',str(owner['pid']),'stat')
        assert not path.exists()or int(path.read_text().rsplit(')',1)[1].split()[19])!=owner['starttime_ticks']
        cg=Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',owner['unit'])
        assert not cg.exists()or not(cg/'cgroup.procs').read_text().strip()
    def terminal(fields):
        wanted=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],MainPID='0',ExecMainPID=str(owner['pid']),
            ExecMainCode='2',ExecMainStatus='15',Result='timeout',NRestarts='0',CPUQuotaPerSecUSec='2s',
            MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='11min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no')
        assert all(fields.get(k)==v for k,v in wanted.items()),{k:fields.get(k)for k in wanted}
        expected='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(original/'tmp')+' '+' '.join(config['argv'])
        assert expected+' ; ignore_errors=no ;'in fields['ExecStart'];absent_birth()
    terminal(c.show(owner['unit']));archives=[]
    for kind,unit,invocation in [('service',owner['unit'],owner['invocation_id']),('timer',owner['timer'],owner['timer_invocation_id'])]:
        for action in ['show','cat','journal']:
            argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+invocation]if action=='journal'else['systemctl','--user',action,unit]
            archives.append(command(kind+'-'+action,argv))
    for index,row in enumerate(archives):assert not row['timed_out']and row['exit']in((0,1)if index==4 else(0,))
    fields=c.fields(archives[0]);terminal(fields)
    context=dict(unit=owner['unit'],timer=owner['timer'],timer_invocation_id=owner['timer_invocation_id'])
    timer_state=c.timer_state(c.fields(archives[3]),context)
    if archives[4]['exit']==1:assert timer_state=='absent'
    before=h.put(out/'actual-signal-timeout-termination-before-release.json',dict(owner=owner,
        actual_exec_main_code=2,actual_signal=15,actual_result='timeout',normal_exit_code=None,
        payload_success=False,full_original_archives=archives,all6_actual_descriptors_archived_before_release=True,
        CPUUsageNSec=int(fields['CPUUsageNSec']),MemoryPeak=int(fields['MemoryPeak']),original_observer_result=h.pin(original/'root-original-result-and-owned-release.json'),
        source_termination_classification_not_normalized=True,created_unix_s=time.time()))
    releases=[]
    for kind,unit in [('timer',owner['timer']),('service',owner['unit'])]:
        shown=command(kind+'-release-before',['systemctl','--user','show',unit]);s=c.fields(shown)
        state=c.timer_state(s,context)if kind=='timer'else('absent'if s['LoadState']=='not-found'else'original_loaded')
        if kind=='service'and state!='absent':terminal(s)
        record=dict(unit=unit,before=shown,stop=None,reset=None,confirmed_absent=state=='absent')
        if state!='absent':
            record['stop']=command(kind+'-owned-stop',['systemctl','--user','stop',unit]);assert record['stop']['exit']==0
            after=command(kind+'-after-stop',['systemctl','--user','show',unit]);s=c.fields(after);record['after_stop']=after
            if s['LoadState']!='not-found':
                if kind=='service':terminal(s)
                else:c.timer_state(s,context)
                assert s['ActiveState']=='failed'
                record['reset']=command(kind+'-owned-failed-reset',['systemctl','--user','reset-failed',unit]);assert record['reset']['exit']==0
                after=command(kind+'-after-reset',['systemctl','--user','show',unit]);s=c.fields(after);record['after_reset']=after
            assert s['Id']==unit and s['LoadState']=='not-found';record['confirmed_absent']=True
        releases.append(record)
    absent_birth()
    result=h.put(out/'actual-original-signal-timeout-and-owned-release.json',dict(status='ORIGINAL_SIGTERM_TIMEOUT_PRESERVED_ACTUAL6_ARCHIVES_AND_OWNED_RELEASE_COMPLETE',
        original_termination=before,original_normal_exit_code=None,actual_signal=15,actual_result='timeout',
        original_success=False,owned_release=releases,all_original_units_confirmed_absent=True,
        benchmark_passed=False,synthetic_full_scope_not_validated=True,payload_retried=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
