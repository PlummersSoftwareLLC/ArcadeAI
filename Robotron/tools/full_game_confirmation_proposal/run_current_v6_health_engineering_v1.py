"""Finite read-only engineering observation; no scientific evaluation or GPU."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--job-sha256');args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    assert hashlib.sha256(args.job.read_bytes()).hexdigest()==args.job_sha256
    job=json.loads(args.job.read_text());assert job['samples']==5 and job['interval_s']==2 and job['wall_s']==45
    h=load('_v6_health_engineering_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h.checked(job['runtime']);h.checked(job['health_source'])
    module=load('_v6_health_engineering_guard',Path(job['health_source']['path']))
    output=Path(job['output']);output.mkdir(mode=0o700)
    begin=time.monotonic();records=[];error=None;closure=None
    try:
        guard=module.CurrentV6MainHealth(job,output,h);guard.start()
        for i in range(job['samples']):
            assert time.monotonic()-begin<job['wall_s'],'Finite engineering wall bound exceeded'
            record=guard.observe();records.append(record)
            print(json.dumps(dict(index=i,pending=record['phase']['overlap_pending'],join=record['current_v6_join'])),flush=True)
            if i+1<job['samples']:time.sleep(job['interval_s'])
        assert sum(not r['phase']['overlap_pending']for r in records)>=3,'Fewer than three accepted original192 observations'
        closure=guard.finish(None);assert time.monotonic()-begin<=job['wall_s']
    except Exception:error=traceback.format_exc()
    assert 'torch'not in sys.modules
    report=h.put(output/'engineering-result.json',dict(status='PASS_READ_ONLY_V6_PHYSICAL_ENGINEERING_ONLY'if error is None else'FAIL_READ_ONLY_V6_PHYSICAL_ENGINEERING_ONLY',
        original_job=h.pin(args.job),error=error,samples=records,observer_close=closure,
        elapsed_s=time.monotonic()-begin,actual_MAME_GPU_or_scientific_native_body_launched=False,
        fullgame_native_qualified=False,statistical_or_promotion_qualification=False,live_controls_changed=False,promotion=False))
    print(json.dumps(dict(status='PASS'if error is None else'FAIL',report=report,error=error)),flush=True)
    return 0 if error is None else 1


if __name__=='__main__':raise SystemExit(main())
