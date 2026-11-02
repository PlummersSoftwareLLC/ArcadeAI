"""Prepare the one bounded original CPU qualification; no scope is launched."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
Q=Path(__file__).resolve().parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

def prepare():
    h=load('_deadline_actual_CPU_prepare_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    prepared=h.pin(Q/'guard-path-correction-original01/prepared-four-legs-NOT-LAUNCH-QUALIFIED.json')
    assert prepared['sha256']=='ea42084f6091ce503d8a02030e2a91758850f7da73da6e050b319ed32df2c8e4'
    packet=json.loads(h.checked(prepared).read_bytes())
    controller=h.pin(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    assert controller['sha256']=='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
    driver=h.pin(Q/'run_deadline32_actual_jobs_CPU_v2.py');closer=h.pin(Q/'close_deadline32_actual_jobs_CPU_v2.py')
    tests=h.pin(Q/'test_deadline32_native_integration_v1.py')
    assert tests['sha256']=='33cc8a43ee895aeea6462258cb15ed3a5ca931a571238497ae3fcf477d7f2504'
    archive=h.pin(G/'tools/eval_capacity_proposal/review_original_pilot_score_carry_v1.py')
    root=Q/'actual-four-job-prebody-and-native-chain-CPU-original01';assert not root.exists();root.mkdir(mode=0o700)
    entries=[prepared,controller,driver,closer,tests,h.pin(__file__),h.pin(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'),
        h.pin(Q/'native-reviewer-source-preparation-v1.json'),h.pin(Q/'private-startup-clock32-original01/source-derivation.json'),
        h.pin(Q/'private-startup-clock32-original01/test_startup_deadline32_clock_v1.py')]
    for name in ('recorder-component-preparation-v3.json','proxy-hooks-component-preparation-v1.json','report-component-preparation-v1.json','lifecycle-component-preparation-v1.json'):
        entries.append(h.pin(Q/name))
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
    job=dict(schema='robotron-deadline32-four-actual-jobs-CPU-guard-v1',unit='robotron-deadline32-actual-four-job-prebody-nativechain-CPU-original01-20261026.service',
        output=str(root/'output-original01'),prepared_manifest=prepared,helpers=h.pin(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'),
        new_native_chain_tests=tests,inputs=list(small.values()),large_input_stat_attestations=list(large.values()),
        original_attempt=1,no_retry=True,expected_actual_serialized_job_tests=4,expected_new_native_chain_tests=5,
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
        CPU_job=jp,config=cp,controller=controller,driver=driver,helpers=job['helpers'],archive=archive,closeout_source=closer,
        source_preparer=h.pin(__file__),native_prepared_manifest=prepared,small_hashed_inputs=len(small),large_stat_only_inputs=len(large),
        actual_serialized_job_tests=4,new_native_chain_tests=5,old19_rerun=False,CPU_scope_launched=False,
        controller_command=['/usr/bin/python3.12','-I','-B',controller['path'],'--execute','--config',cp['path'],'--expected-source-sha256',controller['sha256']],
        closeout_command_template=['/usr/bin/python3.12','-I','-B',closer['path'],'--execute','--prepared',str(root/'prepared-original-CPU-NOT-LAUNCHED.json'),
            '--prepared-sha256','ROOT_INSERT_ACTUAL_PREPARED_PIN','--source-sha256',closer['sha256']],
        no_model_body_GPU_MAME_or_scope_launch=True))
    print(json.dumps(p),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    if p.parse_args().prepare:prepare()
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
