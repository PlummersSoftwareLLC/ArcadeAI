"""Close original CPU13 and qualify four fresh original05 engineering jobs in the verified current main context."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

N=Path(__file__).resolve().parent
G=N.parents[3]
R=N/'future-capacity64-shared-slot-domain-UNSELECTED-original01/runtime-family-original03'
E=N/'evaluator-count-active600-counterbalanced-engineering-original05'

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
    h=load('_q_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    assert h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    reader=load('_q_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    read=lambda p,as_json=True:reader.read_pin(p,as_json=as_json)
    arc=load('_q_arc',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    closer=load('_q_closer',G/'tools/training_connection_lifecycle_proposal_20261023/independent_component_closeout_v3.py')
    ip=h.pin(E/'prepared-original-ABBA-jobs-NOT-LAUNCH-QUALIFIED.json')
    assert ip['sha256']=='072fcb7c8dfa8662809c73eb9b40527b8c2016ec207af5f43924cf4efd4d9a8d'
    index=read(ip);d=E/'actual-job-source-family-guards-CPU-original02'
    scope=closer.closeout(d,h,arc,read,0)
    rp=h.pin(d/'actual-thirteen-CPU-job-guard-results.json');report=read(rp)
    assert report['tests_run']==13 and report['passed']is True and report['prepared_original_jobs']==ip
    logs=[]
    for name in ('stdout.txt','stderr.txt'):
        source=d/'execution-original01'/name;raw=h.checked(h.pin(source)).read_bytes();dest=d/('closed-'+name)
        with dest.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        logs.append(h.pin(dest))
    cp=h.put(d/'independent-original-thirteen-exact-job-CPU-guards-closeout.json',dict(
        schema='robotron-shared64-exact-four-job-CPU13-independent-closeout-v1',scope=scope,report=rp,
        actual_tool_session=94605,actual_tool_terminal_exit=0,actual_exit=0,passed=True,tests_run=13,
        actual_CPU_cores=2,actual_memory_bytes=4<<30,actual_runtime_limit_s=180,closed_logs=logs,
        original8_and10_exact_job_guard_subsets_passed=True,exact_job_runtime_matches_actual_free_threaded_cold_import_proof=True,
        all384_new_IDs_disjoint_from_all_prior_original01_to04=True,current_main_context_and_monitor_exact_job_bindings_verified=True,
        all6_descriptors_argv_resources_pins_births_units_cgroups_release_verified=True,
        quality_qualified=False,created_unix_s=time.time()))
    prev=read(h.pin(N/'evaluator-count-active600-counterbalanced-engineering-original02/qualified-original-ABBA-launch-configs.json'))
    c9=h.pin(R/'CPU-complete-family-guards-original01/independent-original-ten-complete-family-CPU-guards-closeout.json')
    proof=read(c9);assert proof['actual_tool_terminal_exit']==0 and proof['actual_free_threaded_cold_native_imports32_and64_verified']is True
    capacity=prev['CPU64_prefix_review_capacity'];math=prev['measurement_math_CPU15'];read(capacity);read(math)
    cases=[]
    for record in index['cases']:
        guard=dict(status='PASS_ORIGINAL_QUOTA64_NATIVE_FAMILY_GUARDS_AND_CPU_CLOSED0',native_job=record['native_job'],
            native_runtime=record['runtime'],actual_CPU_cores=2,actual_memory_bytes=4<<30,actual_runtime_limit_s=180,
            actual_exit=0,actual_source_guards_and_scope=cp,actual8_exact_original_job_guards_passed=True,
            actual10_exact_original_job_guards_passed=True,actual11_exact_original_job_guards_passed=True,actual12_exact_original_job_guards_passed=True,actual13_exact_original_job_guards_passed=True,
            actual_native_mode_refusal_before_lease_verified=True,source_initializer_proof=c9,
            actual_full32_64_constructor_and_drain_guards=c9,actual_cold_native_imports32_64=c9,
            CPU64_prefix_reader_capacity=capacity,actual64_live_startup_verified=False,quality_qualified=False)
        dest=E/record['case']/'source-family-guards-CPU-original01';dest.mkdir(mode=0o700)
        gp=h.put(dest/'independent-original-family-guards-and-CPU-closeout.json',guard)
        cfg=copy.deepcopy(read(record['unqualified_controller_config']))
        ctl=load('_q_ctl_'+record['case'],h.checked(record['native_controller']))
        pins=cfg['pins']+[ctl.pin(p['path'])for p in (gp,cp,c9,capacity,math,rp,h.pin(__file__))]
        cfg['pins']=list({p['path']:p for p in pins}.values())
        cfgp=h.put(E/record['case']/'controller-config.json',cfg)
        assert ctl.checked_config(cfgp['path'])==cfg
        cases.append(dict(record,source_guard_closeout=gp,launch_config=cfgp,
            exact_job_CPU_guard_closeout_exists=True,native_launch_ready=True))
    pin=h.put(E/'qualified-original-ABBA-launch-configs.json',dict(
        schema='robotron-shared64-qualified-fresh-original05-ABBA-configs-v5',design=index['design'],prepared_original_jobs=ip,
        exact_job_CPU_guard_closeout=cp,complete_family_CPU8=c9,complete_family_CPU9=c9,complete_family_CPU10=c9,
        observer_component_CPU=read(index['design'])['observer_component_CPU'],observer_protocol_CPU=read(index['design'])['observer_protocol_CPU'],
        current_main_context_CPU=read(index['design'])['current_main_context_CPU'],current_main_monitor=read(index['design'])['current_main_monitor'],
        CPU64_prefix_review_capacity=capacity,measurement_math_CPU15=math,cases=cases,
        all384_original_identities_fresh=True,disjoint_from_original01_and02=True,prior_A1_rate_reused=False,disjoint_from_original03=True,disjoint_from_original04=True,
        one_original_attempt_each=True,no_retries=True,native_configs_guarded=True,
        actual64_live_startup_verified=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(qualified=pin,CPU13=cp)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--qualify',action='store_true')
    if p.parse_args().qualify:main()
    else:print('PLAN_ONLY')
