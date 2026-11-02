"""Fresh ROOT deadline32 main/resource readiness; no launch or process controls.

Reuse the existing exact lease/GPU0/all65port checker; actual new CPU guards
and controller pins stay separate from the scientific deadline metric.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
Q=Path(__file__).resolve().parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
N=Q.parent/'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def check(leg,output):
    original=load('_deadline_ready_original_resource_checks',N/'close_shared64_original06_case_v1.py')
    c=original.CloseOriginal('02-B1-capacity64');h=c.h
    mp=h.pin(Q/'qualified-native-envelopes-after-CPU02-original01/qualified-four-native-envelopes.json')
    assert mp['sha256']=='75c2381a5a92b2267be96351ef9337a133e4d8023f1b4443a68dc54dfa9b9f87'
    packet=c.read(mp);case=next(x for x in packet['cases']if x['leg']==leg)
    job=c.read(case['native_job']);cfg=c.read(case['native_launch_config']);guard=c.read(case['exact_job_CPU_guard'])
    assert guard['status']=='PASS'and guard['native_job']==case['native_job']and guard['runtime']==case['runtime']
    assert guard['actual_exit']==0 and guard['actual_CPU_cores']==2 and guard['actual_memory_bytes']==4<<30 and guard['actual_runtime_limit_s']==180
    assert case['exact_job_CPU_guard']['path']==job['prelaunch_family_guard_closeout']
    assert not Path(job['output']).exists()and not Path(cfg['output']).exists()
    assert job['lease']==c.job['lease']and job['origin_port']==c.job['origin_port']and job['gpu_uuid']==c.job['gpu_uuid']
    assert job['proxy_ports']=={str(s):c.job['proxy_ports'][str(s)]for s in range(4096,4128)}
    resources=c.free_resources()
    state=json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    assert state['current_main_binding']==job['main_binding']and not state['scientific_job_running']and not state['performance_job_running']
    monitor=state['current_main_monitor'];h.checked(monitor)
    r=subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],capture_output=True,text=True,timeout=30)
    assert r.returncode==0,r.stderr
    main=json.loads(r.stdout)
    assert main['client_count']==192 and main['held_inputs']==197 and main['bound192_actor_identities_and_affinities_verified']is True
    assert main['training_enabled']is True and main['measurement_active']is False
    control=load('_deadline_ready_actual_controller',h.checked(case['native_controller']))
    assert control.checked_config(case['native_launch_config']['path'])==cfg
    for unit in (cfg['unit'],cfg['unit'][:-8]+'.timer',cfg['unit'][:-8]+'-mainhealth.service',cfg['unit'][:-8]+'-mainhealth.timer'):
        assert control.show(unit)['LoadState']=='not-found'
        assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists()
    model_stats=[]
    for pin in cfg['pins']:
        p=Path(pin['path'])
        if p.suffix=='.pt':
            s=p.lstat();assert stat.S_ISREG(s.st_mode)and not p.is_symlink()
            actual=dict(path=str(p),sha256=pin['sha256'],bytes=s.st_size,identity=dict(device=s.st_dev,inode=s.st_ino,
                mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink))
            assert actual==pin
            retained=next(v for v in [job['checkpoint'],*job['inputs']]if v['path']==str(p))
            full=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
            assert all(full[k]==v for k,v in retained['identity'].items());model_stats.append(actual)
        else:assert control.pin(p)==pin
    private=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():continue
        try:argv=[v.decode(errors='replace')for v in(proc/'cmdline').read_bytes().split(b'\0')if v]
        except OSError:continue
        if any(Path(v).name in ('run_frozen_sidecar.py','run_cold_slot64_prefix_v1.py','run_evaluator_count_active600_v2.py','run_deadline32_leg_v1.py')for v in argv):private.append(int(proc.name))
        if argv and Path(argv[0]).name=='mame'and'robotron'in argv:
            try:env=dict(v.decode().split('=',1)for v in(proc/'environ').read_bytes().split(b'\0')if b'='in v)
            except OSError:continue
            if env.get('ROBOTRON_CLIENT_SLOT')in{str(s)for s in range(4096,4160)}:private.append(int(proc.name))
    assert private==[]
    return h.put(output,dict(schema='robotron-deadline32-root-time-local-readiness-v1',passed=True,created_unix_s=time.time(),leg=leg,
        qualified_manifest=mp,native_job=case['native_job'],native_launch_config=case['native_launch_config'],source=h.pin(__file__),
        main=main,main_monitor=monitor,resources=resources,exact_job_CPU_guard=case['exact_job_CPU_guard'],
        all_selected_small_inputs_and_model_fullstats_unchanged=True,model_body_read=False,model_stats=model_stats,
        private_runner_or_highslot_PIDs=private,exact_future_native_observer_units_and_cgroups_absent=True,
        native_output_and_execution_unused=True,native_launch_argv=case['native_launch_argv'],
        ROOT_must_launch_promptly_or_repeat_explicit_readiness=True,native_launched=False,improvement_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');p.add_argument('--leg',choices=('R1','C1','R2','C2'));p.add_argument('--output',type=Path);a=p.parse_args()
    if a.check:print(json.dumps(check(a.leg,a.output)))
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
