"""ROOT-only fresh readiness; reuse original main/resource checks. No launch.

Default/import inert. Protected body uses retained SHA+exactstat; actual selected
controller hashes all its inputs again at launch. Writes one new readiness only.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
D=HERE/'cold-prefix-preparation05-original01'
N=HERE.parents[1]
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def check():
    original=load('_cold_ready_original_resources',N/'close_shared64_original06_case_v1.py')
    c=original.CloseOriginal('02-B1-capacity64');h=c.h
    manifest_pin=h.pin(D/'cold-prefix-native-launch-qualified-after-CPU19.json')
    assert manifest_pin['sha256']=='a83a4c35e4ecc9d2ec46d7c5ca3976da821b405ffee154bb2f48c4688e8941e1'
    m=c.read(manifest_pin);job=c.read(m['native_job']);cfg=c.read(m['native_launch_config'])
    guard=c.read(m['original_CPU19_closeout'])
    assert guard['actual_exit']==0 and guard['tests_run']==19 and guard['native_job']==m['native_job']
    assert guard['native_runtime']==m['native_runtime'] and guard['no_CPU_retry'] is True
    assert not Path(job['output']).exists() and not Path(cfg['output']).exists()
    assert job['lease']==c.job['lease'] and job['origin_port']==c.job['origin_port']
    assert job['proxy_ports']==c.job['proxy_ports'] and job['gpu_uuid']==c.job['gpu_uuid']
    # Unchanged original lease/flock/all65binds/GPU0 context checks. No new guard
    # implementation and no forced cleanup or private-process interaction.
    resources=c.free_resources()
    state=json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    assert state['current_main_binding']==job['main_binding']
    monitor=state['current_main_monitor'];h.checked(monitor)
    r=subprocess.run(['/usr/bin/python3.12','-I','-B',monitor['path']],capture_output=True,text=True,timeout=30)
    assert r.returncode==0,r.stderr
    main=json.loads(r.stdout)
    assert main['client_count']==192 and main['held_inputs']==197 and main['bound192_actor_identities_and_affinities_verified'] is True
    assert main['training_enabled'] is True and main['measurement_active'] is False
    control=load('_cold_ready_actual_control',Path(m['native_controller']['path']))
    assert h.pin(m['native_controller']['path'])==m['native_controller']
    assert control.checked_config(m['native_launch_config']['path'])==cfg
    for unit in (cfg['unit'],cfg['unit'][:-8]+'.timer'):
        assert control.show(unit)['LoadState']=='not-found'
        assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists()
    model_stats=[]
    for pin in cfg['pins']:
        p=Path(pin['path'])
        if p.suffix=='.pt':
            s=p.stat();actual=dict(path=str(p),sha256=pin['sha256'],bytes=s.st_size,
                identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink))
            assert actual==pin and not p.is_symlink();model_stats.append(actual)
            retained=next(v for v in [job['checkpoint'],*job['inputs']] if v['path']==str(p))
            full=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
            assert all(full[k]==v for k,v in retained['identity'].items())
        else:assert control.pin(p)==pin
    private=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():continue
        try:argv=[v.decode(errors='replace') for v in (proc/'cmdline').read_bytes().split(b'\0') if v]
        except OSError:continue
        if any(Path(v).name in ('run_frozen_sidecar.py','run_cold_slot64_prefix_v1.py','run_evaluator_count_active600_v2.py') for v in argv):private.append(int(proc.name))
        if argv and Path(argv[0]).name=='mame' and 'robotron' in argv:
            env=dict(v.decode().split('=',1) for v in (proc/'environ').read_bytes().split(b'\0') if b'=' in v)
            if env.get('ROBOTRON_CLIENT_SLOT') in {str(x) for x in range(4096,4160)}:private.append(int(proc.name))
    assert private==[]
    return h.put(D/'actual-root-cold-prefix-launch-readiness.json',dict(
        schema='robotron-cold64-prefix-root-time-local-readiness-v1',passed=True,created_unix_s=time.time(),
        qualified_manifest=manifest_pin,source=h.pin(__file__),main=main,main_monitor=monitor,
        resources=resources,all_selected_small_inputs_hashes_and_protected_stat_unchanged=True,
        protected_model_body_read=False,model_stats=model_stats,private_runner_or_highslot_PIDs=private,
        exact_future_native_units_and_cgroups_absent=True,native_output_and_execution_unused=True,
        native_launch_argv=m['native_launch_argv'],root_must_launch_promptly_or_repeat_explicit_readiness=True,
        native_launched=False,quality_qualified=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    if p.parse_args().check:print(json.dumps(check()))
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
