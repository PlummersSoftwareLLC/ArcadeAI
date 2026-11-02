"""Run the two prepared quota64 engineering suites inside one original CPU scope.

Inert unless explicitly selected with its pinned precommit. Synthetic fixtures
are not scientific games, and these checks cannot qualify or promote a policy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time


def pin(path):
    path=Path(path)
    s=path.stat();raw=path.read_bytes()
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                identity=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,
                              mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
                              mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink))


def put(path,value):
    with Path(path).open('x')as handle:
        os.fchmod(handle.fileno(),0o444)
        json.dump(value,handle,indent=2,allow_nan=False)
        handle.write('\n');handle.flush();os.fsync(handle.fileno())
    return pin(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--precommit',type=Path)
    parser.add_argument('--precommit-sha256')
    args=parser.parse_args()
    if not args.run or args.precommit is None or not args.precommit_sha256:
        parser.error('Explicit --run and exact precommit selection required')
    raw=args.precommit.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==args.precommit_sha256
    job=json.loads(raw)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    assert 'torch'not in sys.modules
    for entry in job['inputs']:assert pin(entry['path'])==entry,entry['path']
    assert job['runner']==pin(Path(__file__).resolve())
    root=Path(job['directory'])
    assert len(job['suites'])==2
    deadline=time.monotonic()+150
    observations=[]
    def main_health(label):
        result=subprocess.run(['/usr/bin/python3.12','-I','-B',job['main_monitor']['path']],
                              capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        value=json.loads(result.stdout)
        assert value['client_count']==192 and value['held_inputs']==197
        assert value['autosave_age_s']<=360 and value['training_enabled']is True
        observations.append(put(root/(label+'-main-health.json'),value))
    main_health('before')
    results=[]
    for suite in job['suites']:
        assert not Path(suite['report']).exists()
        argv=['/usr/bin/python3.12','-I','-B',suite['source']['path'],
              '--run-guards','--output',suite['report']]
        result=subprocess.run(argv,capture_output=True,text=True,
                              timeout=max(.1,deadline-time.monotonic()))
        logs={}
        for name,value in (('stdout',result.stdout),('stderr',result.stderr)):
            path=root/(suite['name']+'-'+name+'.txt')
            with path.open('x')as handle:
                os.fchmod(handle.fileno(),0o444);handle.write(value)
                handle.flush();os.fsync(handle.fileno())
            logs[name]=pin(path)
        report=json.loads(Path(suite['report']).read_text())if Path(suite['report']).exists()else None
        passed=(result.returncode==0 and report is not None
                and report['successful']is True and report['tests_run']==suite['expected_tests']
                and report['failures']==report['errors']==0
                and report['engineering_fixtures_only']is True
                and report['quality_qualified']is False)
        results.append(dict(name=suite['name'],argv=argv,actual_exit=result.returncode,
                            expected_tests=suite['expected_tests'],passed=passed,
                            report=pin(suite['report'])if report is not None else None,**logs))
    main_health('after')
    for entry in job['inputs']:assert pin(entry['path'])==entry,entry['path']
    success=all(value['passed']for value in results)
    summary=dict(schema='robotron-original-quota64-CPU-guard-summary-v1',
                 precommit=pin(args.precommit),success=success,suites=results,
                 expected_tests=30,main_observations=observations,
                 numerical_runtime_imported='torch'in sys.modules,
                 selected_inputs_unchanged=True,engineering_fixtures_only=True,
                 quality_qualified=False,production_changed=False,
                 actual_scoped_resources_and_owned_closure_still_require_independent_review=True)
    report=put(root/'original-CPU-guard-summary.json',summary)
    print(json.dumps(dict(success=success,summary=report,quality_qualified=False)),flush=True)
    return 0 if success else 1


if __name__=='__main__':
    raise SystemExit(main())
