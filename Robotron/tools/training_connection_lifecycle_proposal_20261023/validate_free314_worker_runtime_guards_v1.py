"""Three actual wrong-runtime/binary scopes must reject before monitoring starts."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job')
    p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-free314-worker-runtime-guards-CPU-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_runtime_guards_h');reader=load(job['reader'],'_runtime_guards_reader')
    arc=load(job['archive'],'_runtime_guards_archive');closer=load(job['closer'],'_runtime_guards_closer')
    cpu=load(job['CPU_controller'],'_runtime_guards_cpu')
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    for pin in job['inputs']:h.checked(pin)
    root=Path(job['output']);root.mkdir(mode=0o700)
    fields=cpu.show(job['parent_unit']);assert fields['MainPID']==str(os.getpid())and fields['InvocationID']==os.environ['INVOCATION_ID']
    parent=dict(pid=os.getpid(),birth=birth(os.getpid()),uid=os.geteuid(),unit=job['parent_unit'],invocation_id=fields['InvocationID'],
        cgroup=fields['ControlGroup'],argv=[s.decode()for s in Path('/proc/self/cmdline').read_bytes().split(b'\0')[:-1]],job=h.pin(a.job),source=h.pin(__file__))
    records=[]
    for case in ('wrong_python','GIL_enabled','wrong_binary_hash'):
        directory=root/case;directory.mkdir(mode=0o700)
        worker=read(job['worker_job_template']);prior=h.put(directory/'prior-groups.json',[])
        started=time.monotonic();worker.update(output=str(directory/'observations'),parent=parent,parent_started_monotonic_s=started,
            deadline_monotonic_s=started+45,unit_runtime_s=180,observer_unit=job['unit_prefix']+'-'+case.lower().replace('_','-')+'.service',
            prior_groups=prior,nonce=os.urandom(16).hex(),original_attempt=1,no_retry=True)
        if case=='wrong_binary_hash':worker['worker_interpreter']=copy.deepcopy(worker['worker_interpreter']);worker['worker_interpreter']['sha256']='0'*64
        jp=h.put(directory/'job.json',worker)
        interpreter=['/usr/bin/python3.12']if case=='wrong_python'else[job['worker_interpreter']['path'],'-Xgil='+('1'if case=='GIL_enabled'else'0')]
        argv=[*interpreter,'-I','-B',job['worker']['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',job['worker']['sha256']]
        pins=[*job['inputs'],jp,prior,parent['job'],parent['source']]
        cfg=dict(unit=worker['observer_unit'],output=str(directory/'execution-original01'),argv=argv,
            properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
            pins=[cpu.pin(pin['path'])for pin in {p['path']:p for p in pins}.values()],observation_s=240)
        cp=h.put(directory/'controller-config.json',cfg);cpu.checked_config(cp['path'])
        with(directory/'controller-stdout.txt').open('xb')as out,(directory/'controller-stderr.txt').open('xb')as err:
            child=subprocess.Popen(['/usr/bin/python3.12','-I','-B',job['CPU_controller']['path'],'--execute','--config',cp['path'],
                '--expected-source-sha256',job['CPU_controller']['sha256']],stdin=subprocess.DEVNULL,stdout=out,stderr=err)
        child_birth=birth(child.pid);assert child.wait(timeout=35)==1 and birth(child.pid)!=child_birth
        scope=closer.closeout(directory,h,arc,read,1)
        error=read(scope['actual_stderr'],False).decode()
        expected='Exact free-threaded3.14 observer runtime required'if case!='wrong_binary_hash'else'Selected input differs: '+job['worker_interpreter']['path']
        assert expected in error and not(directory/'observations').exists()
        records.append(dict(case=case,original_job=jp,original_argv=argv,scope=scope,expected_rejection=expected,
            controller_pid=child.pid,controller_birth=child_birth,controller_exit1_and_reaped=True,
            no_health_output_or_outcome_created=True,quality_qualified=False))
    assert 'torch'not in sys.modules
    rp=h.put(root/'report.json',dict(schema='robotron-free314-worker-runtime-guards-report-v1',cases=records,
        all_three_original_context_rejections_preserved=True,main_runtime_changed=False,scientific_case=False,
        quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=rp,cases=len(records))),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
