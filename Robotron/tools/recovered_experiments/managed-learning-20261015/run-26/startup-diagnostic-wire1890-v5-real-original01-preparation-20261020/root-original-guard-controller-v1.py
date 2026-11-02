"""One root-owned guard lifecycle. Never reruns or adopts an original attempt."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import types

ROOT=Path('/home/dave/source/repos/ArcadeAI')
GAME=ROOT/'Robotron'
HERE=Path(__file__).resolve().parent
READER=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'

def require(value,message):
    if not value:raise ValueError(message)

def main():
    require(len(sys.argv)==2 and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==sys.argv[1],
            'Exact explicitly selected root controller required')
    require(hashlib.sha256(READER.read_bytes()).hexdigest()==
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','Reader changed')
    spec=importlib.util.spec_from_file_location('_root_startup_reader',READER)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    selected=reader.read_pin(reader.pin(HERE/'original-root-guard-selection.json'))
    require(selected['controller']==reader.pin(__file__) and selected['original_attempt']==1
        and selected['no_retry'] is True,'Original controller selection differs')
    launch=reader.checked_module('_root_selected_startup_launcher',selected['launcher'])
    r,plan,job,modules=launch.load_plan(selected['plan'])
    proof=r.read_pin(selected['real_preparation_readback'])
    require(proof['status']=='ACTUAL_REAL_INPUT_PREPARATION_PASS_ORIGINAL_EXIT0_ALL6_ARCHIVED_RELEASED_GUARD_NOT_SELECTED',
            'Original actual preparation proof missing')
    require(plan['sources']['launcher']==selected['launcher'],'Launcher plan/source differs')
    proc=modules['watchdog'].Processes()
    for unit in (plan['guard_unit'],plan['probe_unit']):
        for name in (unit,unit.removesuffix('.service')+'.timer'):
            f=proc.fields(name)
            require(f.get('Id')==name and f.get('LoadState')=='not-found','Original unit name consumed')
    require(not Path(plan['output']).exists() and not Path(job['output']).exists()
        and not Path(job['external_guard_permit_path']).exists(),'Original output or permit consumed')
    modules['core'].verify_closed_predecessor(job['predecessor'],
        read=lambda p,j:r.read_pin(p,as_json=j),archive=modules['closure'].archived_closure,
        process_start=modules['runtime'].process_start,unit_fields=proc.fields,
        cgroup_exists=lambda group:Path('/sys/fs/cgroup'+group).exists())
    main_binding=r.read_pin(job['main']);modules['main_guard'].owner_and_files(main_binding)
    monitor=modules['runtime'].System();monitor.reader=r;monitor.modules=modules;monitor.main=main_binding
    monitor.main_hash_stats={p:monitor.stat_key(Path(p).stat()) for p in main_binding['held_hashes']}
    monitor.baseline=modules['raw_api'].parse_wire(r.read_pin(main_binding['baseline_API'],as_json=False))
    monitor.previous=monitor.baseline;monitor.package=r.read_pin(job['package'])
    monitor.verify_inputs(types.SimpleNamespace(job=job))
    monitor.health(types.SimpleNamespace(owns_output=False),force=True)
    state=json.loads((GAME/'logs/managed-learning-20261015/state.json').read_bytes())
    require(state['active_diagnostic_job']['selection']==r.pin(HERE/'original-root-guard-selection.json')
        and state['active_quality_job'] is None,'Prospective canonical selection differs')
    out=HERE/'root-guard-execution';out.mkdir(mode=0o700);(out/'tmp').mkdir(mode=0o700)
    caps=launch.System();caps.reader=r;caps.output=out
    unit=plan['guard_unit'];timer=unit.removesuffix('.service')+'.timer'
    argv=['/usr/bin/python3.12','-I','-B','-u',selected['launcher']['path'],'--execute',
        '--plan',selected['plan']['path'],'--plan-sha256',selected['plan']['sha256'],
        '--source-sha256',selected['launcher']['sha256']]
    props=['Type=exec','RemainAfterExit=yes','Restart=no','WorkingDirectory='+str(ROOT),
        'StandardOutput=append:'+str(out/'stdout.txt'),'StandardError=append:'+str(out/'stderr.txt'),
        'CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','TasksMax=128','RuntimeMaxSec=600',
        'TimeoutStopSec=5','SendSIGKILL=no','CPUAffinity='+' '.join(map(str,plan['guard_affinity']))]
    command=['systemd-run','--user','--unit='+unit,'--on-active=3s','--timer-property=AccuracySec=100ms']
    command+=['--property='+p for p in props]
    command+=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(out/'tmp')]+argv
    result=dict(schema='robotron-root-original-startup-guard-lifecycle-v1',selection=r.pin(HERE/'original-root-guard-selection.json'),
        original=None,timer=None,archives=None,release=None,outcome=None,error=None,original_attempt=1,no_retry=True)
    try:
        caps.publish('original-scheduling-intent',dict(command=command,selected=selected))
        scheduled=caps.command('original-scheduling-carrier',command)
        require(scheduled['exit']==0 and not scheduled['timed_out'],'Scheduling failed; no retry')
        shown=caps.command('original-launch-timer-show',['systemctl','--user','show',timer])
        cat=caps.command('original-launch-timer-cat',['systemctl','--user','cat',timer])
        tf=caps.fields(shown)
        require(tf.get('Id')==timer and tf.get('LoadState')=='loaded' and tf.get('Unit')==unit
            and re.fullmatch('[0-9a-f]{32}',tf.get('InvocationID','')) and cat['exit']==0,'Original timer not captured')
        text=r.read_pin(cat['stdout'],as_json=False).decode();section=None;headers=0;targets=[]
        for line in text.splitlines():
            line=line.strip()
            if not line or line.startswith(('#',';')):continue
            if line.startswith('['):section=line;headers+=int(section=='[Timer]')
            if re.match(r'Unit\s*=',line):targets.append((section,line))
        require(headers==1 and (not targets or targets==[('[Timer]','Unit='+unit)]),'Original timer target differs')
        caps.timer=dict(unit=timer,invocation_id=tf['InvocationID']);result['timer']=caps.timer
        caps.publish('original-launch-timer',dict(original=caps.timer,show=shown,cat=cat))
        deadline=time.monotonic()+25;owner=None
        while owner is None:
            f=proc.fields(unit);pid=int(f.get('MainPID','0'))
            if pid:
                birth=proc.start(pid)
                actual=Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0')[:-1]
                if actual==[os.fsencode(a) for a in argv]:
                    require(Path('/proc',str(pid),'exe').resolve()==Path(argv[0]).resolve(),'Original guard executable differs')
                    owner=dict(unit=unit,invocation_id=f['InvocationID'],pid=pid,starttime_ticks=birth,
                        cgroup=proc.group(pid),cgroup_identity=proc.group_identity(proc.group(pid)),
                        start_monotonic_us=int(f['ExecMainStartTimestampMonotonic']),observed_live=True)
                    require(birth is not None and re.fullmatch('[0-9a-f]{32}',owner['invocation_id'])
                        and f.get('NRestarts')=='0' and f.get('ControlGroup')==owner['cgroup']
                        and sorted(os.sched_getaffinity(pid))==plan['guard_affinity'],'Original guard live identity differs')
                    again=proc.fields(unit)
                    require(again.get('MainPID')==str(pid) and again.get('InvocationID')==owner['invocation_id']
                        and proc.start(pid)==birth,'Original live guard not bracketed')
                    caps.owner=owner;result['original']=owner
                    caps.bytes('root-original-live-owner.json',(json.dumps(owner,indent=2)+'\n').encode())
                    caps.publish('original-live-owner-show',caps.command('original-first-live-show',['systemctl','--user','show',unit]))
                    print(json.dumps(dict(status='ORIGINAL_GUARD_LIVE',owner=owner)),flush=True)
                    break
            require(f.get('ExecMainCode','0')=='0','Original live guard birth missed; no adoption')
            require(time.monotonic()<deadline,'Original live birth observation timeout')
            time.sleep(.01)
        deadline=owner['start_monotonic_us']/1e6+620
        while True:
            f=proc.fields(unit)
            require(f.get('Id')==unit and f.get('InvocationID')==owner['invocation_id']
                and f.get('NRestarts')=='0' and f.get('MainPID') in ('0',str(owner['pid'])),'Original guard changed')
            if f.get('MainPID')=='0' and f.get('ExecMainCode') in ('1','2','3'):
                result['outcome']=launch.terminal(f,owner);break
            require(proc.start(owner['pid'])==owner['starttime_ticks'],'Original guard birth changed')
            require(time.monotonic()<deadline,'Observation timeout; original left untouched')
            time.sleep(.5)
        records=[]
        for target,inv in ((unit,owner['invocation_id']),(timer,caps.timer['invocation_id'])):
            for action in ('show','cat','journal'):
                args=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+inv] if action=='journal' else ['systemctl','--user',action,target]
                records.append(caps.command('original-terminal-'+('service' if target==unit else 'timer')+'-'+action,args))
        proof=launch.verify_archives(owner,caps.timer,records,lambda p,j:r.read_pin(p,as_json=j))
        caps.archives=records;result['archives']=dict(proof=proof,records=records)
        caps.publish('all-six-original-terminal-archives',result)
        result['release']=caps.release()
        require(proc.start(owner['pid']) is None and not Path('/sys/fs/cgroup'+owner['cgroup']).exists(),
                'Original guard process/cgroup remains')
        print(json.dumps(dict(status='ORIGINAL_GUARD_TERMINAL_ARCHIVED_RELEASED',outcome=result['outcome'])),flush=True)
    except BaseException as error:
        result['error']=repr(error)
        raise
    finally:
        caps.bytes('root-original-result-and-owned-release.json',(json.dumps(result,indent=2,allow_nan=False)+'\n').encode())

if __name__=='__main__':main()
