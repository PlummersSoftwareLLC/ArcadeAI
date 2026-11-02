"""Repeat launch checks and bind the exact new review-preparation CPU proof."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def finalize(base,precommit,cpu,output):
    h=load('_selected_final_readiness_h',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    def read(pin):return json.loads(h.checked(pin).read_bytes())
    bp,pp,cp=[h.pin(p.resolve())for p in (base,precommit,cpu)]
    previous,packet,closed=read(bp),read(pp),read(cp);manifest=read(previous['prepared_manifest'])
    assert previous['schema']=='robotron-round-study-resource-readiness-v1'
    assert previous['CPU_qualifications_closed']is previous['original_attempts_unused']is True
    assert packet['native_prepared']==previous['prepared_manifest']and packet['engineering_only']is False
    assert packet['source']==h.pin(HERE/'prepare_deadline_independent_review_v4.py')
    assert closed['status']=='PASS_ENGINEERING_ONLY'and closed['actual_exit']==0
    assert closed['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified']is True
    assert closed['source']==h.pin(HERE/'close_engineering_cpu_scope_v2.py')
    actual_cpu=read(closed['original_job']);report=read(closed['actual_report'])
    assert actual_cpu['review_precommit']==pp and actual_cpu['source']==h.pin(HERE/'check_deadline_review_preparation_cpu_v3.py')
    assert actual_cpu['original_attempt']==1 and actual_cpu['no_retry']is True
    assert report['original_job']==closed['original_job']and report['status']=='PASS'and report['tests_run']==6
    assert report['Torch_imported']is report['GPU_or_MAME_launched']is False
    assert h.pin(HERE/'prepare_deadline_independent_review_v4.py')in actual_cpu['inputs']
    assert h.pin(HERE/'review_deadline32_rounds_v11.py')in actual_cpu['inputs']
    assert [row['native_job']for row in packet['cases']]==[row['native_job']for row in manifest['cases']]
    for case,entry in zip(manifest['cases'],previous['configurations']):
        job=read(case['native_job']);cfg=read(entry['config'])
        assert case['leg']==entry['leg']and not Path(job['output']).exists()and not Path(cfg['output']).exists()
        assert not(Path(case['native_job']['path']).parent/'controller-original-launch.json').exists()
        control=load('_selected_final_controller',h.checked(entry['controller']))
        assert control.checked_config(entry['config']['path'])==cfg
        for pin in cfg['pins']:assert control.pin(pin['path'])==pin
        for unit in (cfg['unit'],cfg['unit'].removesuffix('.service')+'.timer'):
            assert control.show(unit)['LoadState']=='not-found'
    first=read(manifest['cases'][0]['native_job']);h.checked(first['lease'])
    fd=os.open(first['lease']['path'],os.O_RDONLY|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    for port in [first['origin_port'],*first['proxy_ports'].values()]:
        with socket.socket()as listener:listener.bind(('0.0.0.0',port))
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=10)
    assert gpu.returncode==0 and not any(first['gpu_uuid']in line for line in gpu.stdout.splitlines())
    family=read(first['source_family_manifest']);case=read(first['main_binding'])
    health=load('_selected_final_health',h.checked(family['main_observer']['health']))
    worker=load('_selected_final_worker',h.checked(family['main_observer']['worker']));deadline=time.monotonic()+15
    while True:
        try:
            sample=worker.collect(health,case);health.validate(case,sample);health.check_inputs(case,full=True);break
        except (ValueError,OSError):
            assert time.monotonic()<deadline,'No coherent original main census before launch'
            time.sleep(.02)
    raw=h.put(output.with_name('fresh-main-final-before-R1.raw.json'),sample)
    result=dict(previous,source=h.pin(Path(__file__).resolve()),original_resource_review=bp,
        checked_unix_s=time.time(),status='READY',fresh_main=raw,raw_GPU_readback=gpu.stdout,GPU0_occupants=[],
        review_precommit=pp,review_preparation_CPU=cp,exact_review_precommit_and_source_CPU_binding_verified=True,
        active=sample['observed_counts']['active'],completed=sample['observed_counts']['completed'],main_round=sample['status']['round'])
    return h.put(output.resolve(),result)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--finalize',action='store_true')
    p.add_argument('--base',type=Path);p.add_argument('--precommit',type=Path);p.add_argument('--CPU-closeout',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.finalize:print(json.dumps(finalize(a.base,a.precommit,a.CPU_closeout,a.output)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
