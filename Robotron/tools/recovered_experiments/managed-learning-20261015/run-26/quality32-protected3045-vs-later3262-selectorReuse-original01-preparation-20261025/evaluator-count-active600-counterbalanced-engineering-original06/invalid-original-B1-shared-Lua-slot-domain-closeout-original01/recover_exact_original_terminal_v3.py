"""ROOT-only durable-identity recovery of an already failed original service.

Never launches or observes/retries the payload. The interrupted parent observer
did not publish terminal archives. Original live identity/launch archive remain.
Reuse the selected controller's exact terminal checks and release functions;
write only new recovery evidence here. Default/import are inert.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import time

HERE = Path(__file__).resolve().parent
E = HERE.parent
CASE = E / '02-B1-capacity64'
SOURCE = E.parent / 'future-capacity64-shared-slot-domain-UNSELECTED-original01/runtime-family-original03/B64/control_evaluator_count_active600_v2.py'
SOURCE_SHA = '240c98a87ea5e07575228bcd469f8028fce087feecf970cdedbb1b61f8c85a39'

def execute():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA
    spec = importlib.util.spec_from_file_location('_original06_B1_terminal_recovery', SOURCE)
    c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
    original = CASE / 'execution-original01'
    identity_path = original / 'root-original-identity.json'
    assert hashlib.sha256(identity_path.read_bytes()).hexdigest() == 'b7ef9607a70e11874183012b40a79c870a9f5dc87fae6c1c1c6a3dcc084a7958'
    identity = json.loads(identity_path.read_text())
    assert identity == dict(pid=3684797,starttime_ticks=113715045,invocation_id='fd206baf383d4dcb853049651060bf40',unit='robotron-compiled-full-tail32-integration-capacity64-02-b1-capacity64-original06-20261026.service',timer='robotron-compiled-full-tail32-integration-capacity64-02-b1-capacity64-original06-20261026.timer',timer_invocation_id='7899870ceb414deba03a1c8c9d25ef5b',observed_live=True)
    assert not Path('/proc',str(identity['pid'])).exists()
    cfg = c.checked_config(CASE / 'controller-config.json')
    assert hashlib.sha256((CASE/'controller-config.json').read_bytes()).hexdigest() == '31a383494de688877c84bc749f8c76e2b28565c99df2a526da87783a9ac01530'
    assert cfg['unit']==identity['unit'] and cfg['output']==str(original)
    launch = json.loads((original / 'root-original-timer-launch-archive.json').read_text())
    intent = json.loads((original / 'root-launch-intent.json').read_text())
    assert c.pin(original/'root-launch-intent.json') == launch['launch_intent']
    assert all(intent[k] == cfg[k] for k in cfg)
    assert launch['unit'] == identity['unit'] and launch['timer'] == identity['timer'] and launch['timer_invocation_id'] == identity['timer_invocation_id']
    for name in ('timer_cat','timer_show','scheduling_carrier'):
        r=launch[name]; assert r['exit']==0 and not r['timed_out']
        for key in ('stdout','stderr'):
            p=Path(r[key]['path']); assert c.pin(p)==r[key]
    live = c.show(identity['unit']); c.original_terminal(live,identity)
    assert live['ExecMainStatus']=='1' and live['Result']=='exit-code'
    group=subprocess.run(['systemctl','--user','show',identity['unit'],'--property=ControlGroup','--value'],capture_output=True,text=True,timeout=10)
    assert group.returncode==0 and group.stdout.strip()==''
    assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',identity['unit']).exists()
    context={k:identity[k] for k in ('unit','timer','timer_invocation_id')}
    c.timer_state(c.show(identity['timer']),context)
    # Six original descriptors are archived before any release action. Timer
    # cat may honestly be1 if original expired timer was already collected.
    archives=[]
    for kind,unit in [('service',identity['unit']),('timer',identity['timer'])]:
        for action in ('show','cat','journal'):
            argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+identity['invocation_id' if kind=='service' else 'timer_invocation_id']] if action=='journal' else ['systemctl','--user',action,unit]
            archives.append(c.command(HERE,'original-'+kind+'-'+action,argv))
    assert all(r['exit']==0 and not r['timed_out'] for r in archives[:3]+archives[5:])
    assert archives[4]['exit'] in (0,1) and not archives[4]['timed_out']
    c.original_terminal(c.fields(archives[0]),identity)
    timer_state=c.timer_state(c.fields(archives[3]),context)
    assert archives[4]['exit']==0 or timer_state=='absent'
    result=dict(schema='robotron-root-audit-durable-terminal-recovery-v1',original=identity,original_exec_code=1,original_exit=1,original_result='exit-code',timer_launch_archive=c.pin(original/'root-original-timer-launch-archive.json'),full_original_archives=archives,original_archive_status=[dict(kind='service' if i<3 else 'timer',action=('show','cat','journal')[i%3],exit=r['exit'],timed_out=r['timed_out']) for i,r in enumerate(archives)],all_six_original_archive_commands_succeeded=all(r['exit']==0 for r in archives),original_archived_before_release=True,owned_release=[],unit_released=False,lifecycle_complete=False,audit_success=False,payload_retried=False,error=None,terminal_timer_state=timer_state,original_observer_handle_unavailable=True,new_observer_or_payload_started=False,scope='New explicit ROOT terminal-only recovery authenticated by durable original live PID/birth/invocation and launch archive; not a resumed original observe() or retrospective live-identity claim.')
    c.publish(HERE/'root-original-terminal-archive.json',result)
    c.original_terminal(c.show(identity['unit']),identity)
    for kind in ('timer','service'):
        record={};result['owned_release'].append(record)
        c.release_original(HERE,kind,identity,context,record)
    assert all(r['confirmed_absent'] for r in result['owned_release'])
    assert not Path('/proc',str(identity['pid'])).exists()
    for unit in (identity['unit'],identity['timer']):
        assert c.show(unit)['LoadState']=='not-found'
        assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists()
    result.update(unit_released=True,lifecycle_complete=True,status='ORIGINAL_NONZERO_PRESERVED_DURABLE_TERMINAL_RECOVERY_ARCHIVED_AND_RELEASED',ended_unix_s=time.time(),source=c.pin(__file__))
    pin=c.publish(HERE/'root-original-result-and-owned-release.json',result)
    print(json.dumps(pin))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.execute:execute()
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
