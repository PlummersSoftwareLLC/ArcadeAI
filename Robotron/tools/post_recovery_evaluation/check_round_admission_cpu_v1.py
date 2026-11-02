"""Qualify original raw admission replay and synthetic bootstrap boundaries."""
import argparse
import ast
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def execute(a):
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=a.job.read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert os.environ['CUDA_VISIBLE_DEVICES']==''and 'torch'not in sys.modules
    fields=dict(line.split('=',1)for line in subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=5).splitlines()if'='in line)
    expected=dict(MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],CPUQuotaPerSecUSec='2s',
        MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='3min',NRestarts='0',Restart='no')
    assert all(fields.get(k)==v for k,v in expected.items())
    h=load('_admission_CPU_h',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    for pin in job['inputs']:h.checked(pin)
    output=Path(job['output']);output.mkdir(mode=0o700);started=time.monotonic()
    health=load('_admission_CPU_actual_health',HERE/'round_health_transport_v6.py')
    case=json.loads(h.checked(job['original_case']).read_bytes());health.check_inputs(case,full=True)
    failures=[];deadline=time.monotonic()+10
    while True:
        sample=None
        try:
            sample=health.collect(case);health.validate(case,sample);first=sample
            second=health.collect(case,previous=first);health.validate(case,second,previous=first)
            assert 0<=second['monotonic_s']-first['monotonic_s']<=.5
            break
        except (ValueError,OSError)as error:
            failures.append(h.put(output/('unaccepted-fixture-%03d.raw.json'%len(failures)),
                dict(error=repr(error),snapshot=sample)))
            assert time.monotonic()<deadline,'No coherent actual engineering fixture'
    firstpin=h.put(output/'actual-initial.raw.json',first);secondpin=h.put(output/'actual-next.raw.json',second)
    # Physical transport and ordinary recipe/exposure predicates are unchanged.
    def functions(path):return {n.name:ast.dump(n)for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef)}
    old=functions(HERE/'round_health_transport_v5.py');new=functions(HERE/'round_health_transport_v6.py')
    assert set(old)==set(new)
    assert all(old[k]==new[k]for k in old if k not in ('base','collect'))
    oldbase=functions(HERE/'round_main_health_v5.py');newbase=functions(HERE/'round_main_health_v6.py')
    assert set(newbase)==set(oldbase)|{'admission'}
    assert all(oldbase[k]==newbase[k]for k in oldbase if k not in ('collect','validate'))
    os.environ['ROBOTRON_ADMISSION_ENGINEERING_FIXTURES']=str(output);sys.path.insert(0,str(ROOT.parent))
    suite=unittest.defaultTestLoader.loadTestsFromName('Robotron.tools.post_recovery_evaluation.test_round_admission_proof_v1')
    capture=io.StringIO();result=unittest.TextTestRunner(stream=capture,verbosity=2).run(suite)
    for pin in job['inputs']:h.checked(pin)
    assert 'torch'not in sys.modules
    report=h.put(output/'report.json',dict(schema='robotron-natural-round-admission-CPU-engineering-result-v1',
        status='PASS'if result.wasSuccessful()else'FAIL',original_job=h.pin(a.job),actual_PID=os.getpid(),actual_scope=fields,
        tests_run=result.testsRun,test_output=capture.getvalue(),elapsed_s=time.monotonic()-started,
        actual_initial_snapshot=firstpin,actual_next_snapshot=secondpin,unaccepted_engineering_fixtures=failures,
        actual_closed_round_chain=[row['round']for row in first['round_admission']['closed_chain']],
        physical_TCP_and_ordinary_controls_AST_unchanged=True,all_other_base_functions_AST_unchanged=True,
        bootstrap_tests_are_synthetic=True,actual_live_turnover_not_yet_observed=True,
        bootstrap_max_s=5,observer_500ms_bound_unchanged=True,raw_API_or_status_rewritten=False,
        Torch_imported=False,GPU_or_MAME_launched=False,scientific_launch_qualified=False,quality_qualified=False,promotion=False))
    print(capture.getvalue(),flush=True);print(json.dumps(dict(report=report,passed=result.wasSuccessful())),flush=True)
    return 0 if result.wasSuccessful()else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--job',type=Path);p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if a.execute:raise SystemExit(execute(a))
    print('PLAN_ONLY_NO_READS_OR_ACTIONS')
