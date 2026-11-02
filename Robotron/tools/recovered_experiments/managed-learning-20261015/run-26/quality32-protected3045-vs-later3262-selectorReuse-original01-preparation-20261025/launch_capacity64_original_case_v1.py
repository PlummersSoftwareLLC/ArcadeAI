"""Fresh preflight then one original protected-policy capacity ABBA native case."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).resolve().parent
E = N / 'evaluator-count-active600-counterbalanced-engineering-original01'


def load(name, path, digest):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def launch(case):
    h=load('_capacity_launch_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
           '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader=load('_capacity_launch_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
                'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    read=lambda p:reader.read_pin(p)
    qualified_pin=h.pin(E/'qualified-original-ABBA-launch-configs.json')
    assert qualified_pin['sha256']=='9ac672e897ca7560a01134197d582df2cbd0c4d3b3c0be12f289dd405527d7d1'
    qualified=read(qualified_pin);design=read(qualified['design'])
    names=[c['case']for c in qualified['cases']]
    assert names==['01-A1-control','02-B1-capacity64','03-B2-capacity64','04-A2-control']
    index=names.index(case);record=qualified['cases'][index]
    directory=E/case;job=read(record['native_job']);config=read(record['launch_config'])
    ctl=load('_capacity_launch_controller',h.checked(record['native_controller']),record['native_controller']['sha256'])
    assert ctl.checked_config(record['launch_config']['path'])==config
    assert job['checkpoint']==design['reference_policy'] and job['experiment_precommit']==qualified['design']
    assert job['diagnostic_only']is True and job['scientific_case']is False and job['initializer_fixture_only']is False
    assert record['native_launch_ready']is True
    assert not Path(job['output']).exists()and not Path(config['output']).exists()
    assert not(directory/'original-native-launch-preflight.json').exists()
    for unit in (config['unit'],config['unit'].removesuffix('.service')+'.timer'):
        assert ctl.show(unit)['LoadState']=='not-found'
    for pin in config['pins']:assert ctl.pin(pin['path'])==pin
    guard=read(record['source_guard_closeout'])
    assert guard['native_job']==record['native_job'] and guard['native_runtime']==record['runtime']
    assert guard['actual_exit']==0 and guard['actual8_exact_original_job_guards_passed']is True
    prior=[]
    for name in names[:index]:
        pin=h.pin(E/name/'independent-original-capacity64-case-closeout.json');proof=read(pin)
        assert proof['case']==name and proof['status']=='VALID_ORIGINAL_CAPACITY64_ENGINEERING_CASE_NO_QUALITY'
        assert proof['all_native_observer_reviewer_archives_resources_pins_and_release_verified']is True
        assert proof['private_resources_free']is True and proof['quality_qualified']is False
        for owner_pin in proof['original_owners']:
            owner=read(owner_pin)
            assert birth(owner['pid'])!=owner['starttime_ticks']
            for unit in (owner['unit'],owner['timer']):assert ctl.show(unit)['LoadState']=='not-found'
        prior.append(pin)
    goal=json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    assert goal['scientific_job_running']is False
    assert job['main_binding']==design['main_binding']==goal['current_main_binding']
    monitor=h.checked(goal['current_main_monitor'])
    current=subprocess.run(['/usr/bin/python3.12','-I','-B',str(monitor)],capture_output=True,text=True,timeout=30)
    assert current.returncode==0,current.stderr
    main=json.loads(current.stdout)
    assert main['client_count']==192 and main['held_inputs']==197 and main['autosave_age_s']<=360
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],
                       capture_output=True,text=True,timeout=20)
    assert gpu.returncode==0 and job['gpu_uuid']not in gpu.stdout
    lease=h.pin(job['lease']['path']);assert lease==job['lease']
    assert(lease['identity']['device'],lease['identity']['inode'])==(32,757)
    fd=os.open(job['lease']['path'],os.O_RDWR|os.O_NOFOLLOW);sockets=[]
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for port in (job['origin_port'],*job['proxy_ports'].values()):
            sock=socket.socket();sockets.append(sock);sock.bind(('127.0.0.1',port))
    finally:
        for sock in sockets:sock.close()
        fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
    assert h.pin(job['lease']['path'])==lease
    preflight=h.put(directory/'original-native-launch-preflight.json',dict(
        schema='robotron-capacity64-original-case-launch-preflight-v1',source=h.pin(__file__),case=case,
        qualified_launches=qualified_pin,design=qualified['design'],prior_valid_original_closeouts=prior,
        native_job=record['native_job'],launch_config=record['launch_config'],main=main,
        GPU_readback=dict(exit=gpu.returncode,stdout=gpu.stdout,stderr=gpu.stderr),
        lease=lease,private_ports_free=1+len(job['proxy_ports']),permanent_coordinator_unheld_and_unchanged=True,
        original_attempt=1,no_retry=True,quality_qualified=False,observed_unix_s=time.time()))
    print(json.dumps(dict(preflight=preflight,launching=case,controller=record['native_controller'],config=record['launch_config'])),flush=True)
    os.execv('/usr/bin/python3.12',['/usr/bin/python3.12','-I','-B',record['native_controller']['path'],
        '--execute','--config',record['launch_config']['path'],'--expected-source-sha256',record['native_controller']['sha256']])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--case',choices=['01-A1-control','02-B1-capacity64','03-B2-capacity64','04-A2-control'])
    a=p.parse_args()
    if a.execute:
        assert a.case is not None;launch(a.case)
    else:print('PLAN_ONLY')
