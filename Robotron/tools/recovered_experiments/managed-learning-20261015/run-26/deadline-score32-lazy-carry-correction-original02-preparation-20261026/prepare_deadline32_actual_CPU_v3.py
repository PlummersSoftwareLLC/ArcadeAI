"""Prepare the one bounded original CPU qualification; no scope is launched."""
import argparse
import hashlib
import importlib.util
import json
import os
import stat
from pathlib import Path
import sys
Q=Path(__file__).resolve().parent
OLD=Q.parent/'deadline-score60min-protocol-original01-preparation-20261026'
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

def prepare(args):
    h=load('_deadline_actual_CPU_prepare_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    prepared=h.pin(Q/'fixed-RCRC-deadline32-study-original02/prepared-four-legs-NOT-LAUNCH-QUALIFIED.json')
    assert prepared['sha256']==args.prepared_sha256
    packet=json.loads(h.checked(prepared).read_bytes())
    controller=h.pin(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    assert controller['sha256']=='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
    driver=h.pin(Q/'run_deadline32_actual_jobs_CPU_v4.py');closer=h.pin(Q/'close_deadline32_actual_jobs_CPU_v4.py')
    assert args.new_integration_tests.is_absolute()and args.new_integration_tests.parent==Q
    assert stat.S_IMODE(args.new_integration_tests.stat().st_mode)==0o444
    tests=h.pin(args.new_integration_tests)
    assert tests['sha256']==args.new_integration_sha256 and args.new_integration_count>0
    archive=h.pin(G/'tools/eval_capacity_proposal/review_original_pilot_score_carry_v1.py')
    root=Q/'actual-four-job-prebody-and-native-chain-CPU-original01';assert not root.exists();root.mkdir(mode=0o700)
    prior_prepared=h.pin(OLD/'actual-four-job-prebody-and-native-chain-CPU-original02/prepared-original-CPU-NOT-LAUNCHED.json')
    prior_closure=h.pin(OLD/'actual-four-job-prebody-and-native-chain-CPU-original02/execution-original01/root-original-result-and-owned-release.json')
    assert json.loads(h.checked(prior_closure).read_bytes())['original_exit']==0
    old_CPU=json.loads((OLD/'actual-four-job-prebody-and-native-chain-CPU-original02/job.json').read_bytes())
    sourcepin=next(p for p in old_CPU['large_input_stat_attestations'] if p['path']=='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python')
    linkpaths=[Path(sourcepin['path']),Path('/home/dave/source/robotron-python/cpython-3.14+freethreaded-linux-aarch64-gnu')]
    links=[]
    for link in linkpaths:
        v=link.lstat();assert stat.S_ISLNK(v.st_mode)
        links.append(dict(path=str(link),readlink=os.readlink(link),lstat_identity=dict(device=v.st_dev,inode=v.st_ino,bytes=v.st_size,
            mtime_ns=v.st_mtime_ns,ctime_ns=v.st_ctime_ns,mode=oct(stat.S_IMODE(v.st_mode)),uid=v.st_uid,nlink=v.st_nlink)))
    interpreter_witness=h.put(root/'exact-selected-interpreter-symlink-binding.json',dict(
        schema='robotron-exact-known-free314-interpreter-symlink-binding-v1',path=sourcepin['path'],source_pin=sourcepin,
        resolved_target=str(Path(sourcepin['path']).resolve(strict=True)),links=links,model_MAME_symlink_permission_added=False))
    native0=json.loads(h.checked(packet['cases'][0]['native_job']).read_bytes());reader=native0['main_sources']['reader']
    entries=[prepared,controller,driver,closer,tests,interpreter_witness,prior_prepared,prior_closure,reader,h.pin(__file__),h.pin(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'),
        h.pin(OLD/'native-reviewer-source-preparation-v1.json'),
        h.pin(OLD/'test_deadline32_native_integration_v1.py'),h.pin(OLD/'deadline_proxy_hooks_v1.py'),h.pin(OLD/'private-startup-clock32-original01/source-derivation.json'),
        h.pin(OLD/'private-startup-clock32-original01/test_startup_deadline32_clock_v1.py')]
    for name in ('recorder-component-preparation-v3.json','proxy-hooks-component-preparation-v1.json','report-component-preparation-v1.json','lifecycle-component-preparation-v1.json'):
        entries.append(h.pin(OLD/name))
    for name in ('test_startup_handoff_v1.py','startup_handoff_v1.py','test_full_tail_proxy_v4.py','full_startup_proxy_v4.py',
        'tail_ledger_v1.py','wire_codec_v2.py','boot_readiness_v3.py','startup_handoff_v2.py','test_cohort_drain_v1.py','cohort_drain_v1.py'):
        entries.append(h.pin(G/'tools/startup_policy_journal_proposal'/name))
    for case in packet['cases']:
        entries.extend([case['native_job'],case['unqualified_controller_config'],case['native_controller']])
        native=json.loads(h.checked(case['native_job']).read_bytes());entries.extend(native['inputs'])
    small={};large={}
    for entry in entries:
        if Path(entry['path']).suffix=='.pt'or entry['bytes']>8*1024*1024:large[entry['path']]=entry
        else:small[entry['path']]=entry
    job=dict(schema='robotron-deadline32-four-actual-jobs-CPU-guard-v1',unit='robotron-deadline32-lazycarry-study02-four-prebody-nativechain-CPU-original01-20261026.service',
        output=str(root/'output-original01'),prepared_manifest=prepared,helpers=h.pin(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'),
        new_native_chain_tests=tests,interpreter_symlink_binding=interpreter_witness,previous_qualification_CPU_scope=prior_closure,inputs=list(small.values()),large_input_stat_attestations=list(large.values()),
        original_attempt=1,no_retry=True,expected_actual_serialized_job_tests=4,expected_new_native_chain_tests=args.new_integration_count,
        old_clock_controller19_may_not_be_rerun=True,source=driver,resources=dict(cpu_cores=2,memory_bytes=4<<30,runtime_max_s=180,tasks_max=128))
    jp=h.put(root/'job.json',job)
    control=load('_deadline_actual_CPU_prepare_control',h.checked(controller))
    argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',driver['path'],
        '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']]
    config=dict(unit=job['unit'],output=str(root/'execution-original01'),argv=argv,
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=240,pins=[control.pin(p['path'])for p in {p['path']:p for p in [jp,*small.values()]}.values()])
    cp=h.put(root/'controller-config.json',config);assert control.checked_config(cp['path'])==config
    p=h.put(root/'prepared-original-CPU-NOT-LAUNCHED.json',dict(schema='robotron-deadline32-four-actual-jobs-CPU-preparation-v1',
        CPU_job=jp,config=cp,controller=controller,driver=driver,helpers=job['helpers'],archive=archive,closeout_source=closer,reader=reader,
        exact_interpreter_symlink_binding=interpreter_witness,previous_successful_original_CPU_scope=prior_closure,
        source_preparer=h.pin(__file__),native_prepared_manifest=prepared,small_hashed_inputs=len(small),large_stat_only_inputs=len(large),
        actual_serialized_job_tests=4,new_native_chain_tests=args.new_integration_count,old19_rerun=False,CPU_scope_launched=False,
        controller_command=['/usr/bin/python3.12','-I','-B',controller['path'],'--execute','--config',cp['path'],'--expected-source-sha256',controller['sha256']],
        closeout_command_template=['/usr/bin/python3.12','-I','-B',closer['path'],'--execute','--prepared',str(root/'prepared-original-CPU-NOT-LAUNCHED.json'),
            '--prepared-sha256','ROOT_INSERT_ACTUAL_PREPARED_PIN','--source-sha256',closer['sha256']],
        no_model_body_GPU_MAME_or_scope_launch=True))
    print(json.dumps(p),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--prepared-sha256');p.add_argument('--new-integration-tests',type=Path)
    p.add_argument('--new-integration-sha256');p.add_argument('--new-integration-count',type=int)
    args=p.parse_args()
    if args.prepare:prepare(args)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
