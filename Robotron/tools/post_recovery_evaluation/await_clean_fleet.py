"""Wait for a verified managed-only roster, then launch one fresh observation.

The wait does not signal clients or change learning. It never resumes or repeats
a failed window. All initial unaccepted observations remain outside the new
window, whose anchor is created by its separately pinned observer.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time


def checked(value):
    path=Path(value['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==value['sha256']
    return path


def pin(path):
    raw=path.read_bytes()
    return dict(path=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))


def write(path,value,exclusive=False):
    temporary=path if exclusive else path.with_name(path.name+'.tmp')
    with temporary.open('x')as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush()
        os.fchmod(stream.fileno(),0o444 if exclusive else 0o664);os.fsync(stream.fileno())
    if not exclusive:os.replace(temporary,path)


def run(job):
    directory=Path(job['output']);directory.mkdir()
    spec=importlib.util.spec_from_file_location('_clean_fleet_health',checked(job['health_source']))
    health=importlib.util.module_from_spec(spec);spec.loader.exec_module(health)
    template=json.loads(checked(job['health_case_template']).read_bytes())
    window_template=json.loads(checked(job['window_template']).read_bytes())
    health.check_inputs(template,full=True)
    assert job['required_clean_samples']==5 and job['interval_s']==5 and job['maximum_wait_s']==14400
    previous=None;clean=0;started=time.monotonic();attempts=0
    with (directory/'readiness-observations.jsonl').open('x')as log:
        while time.monotonic()-started<job['maximum_wait_s']:
            checked(job['driver']);checked(job['health_source']);checked(job['window_observer'])
            health.check_inputs(template)
            for value in window_template['inputs']:checked(value)
            case=copy.deepcopy(template)
            case['initial_round']=json.loads((Path(case['round_root'])/'status.json').read_bytes())['round']
            reason=None;sample=None;attempts+=1
            try:
                sample=health.collect(case)
                health.validate(case,sample,previous=previous)
                previous=sample;clean+=1
            except (OSError,ValueError)as error:
                reason=str(error);previous=None;clean=0
            status=dict(state='needs_isolation',updated_unix_s=time.time(),clean_samples=clean,
                required_clean_samples=5,readiness_attempts=attempts,last_reason=reason,
                owner=window_template['owner'],minimum_added_each=8_000_000,
                original_failed_windows_preserved=True,no_partial_counts_reused=True,
                next_stage='Start one fresh8M+8M observation after5 coherent managed-only samples')
            write(directory/'readiness-status.json',status)
            write(Path(window_template['dashboard_status']),status)
            log.write(json.dumps(status)+'\n');log.flush()
            if clean>=5:
                health.check_inputs(case,full=True)
                write(directory/'clean-main-case.json',case,exclusive=True)
                write(directory/'clean-main-snapshot.json',sample,exclusive=True)
                plan=copy.deepcopy(window_template)
                plan['purpose']='Fresh original03 continuation after managed-only roster validation; no failed window data reused'
                plan['expected_exposure_lineage']={key:{field:sample['api']['host_pipeline']['learning_exposure'][key][field]
                    for field in ['process_id','instance_monotonic_ns','epoch','epoch_reason']}
                    for key in ['optimizer','replay']}
                plan['clean_roster_case']=pin(directory/'clean-main-case.json')
                plan['clean_roster_snapshot']=pin(directory/'clean-main-snapshot.json')
                plan['inputs'] += [pin(checked(job['driver'])),pin(checked(job['health_source'])),
                                   pin(directory/'clean-main-case.json')]
                plan_path=directory/'window-plan.json';write(plan_path,plan,exclusive=True)
                # This exact original unit/output may be launched once only.
                command=['systemd-run','--user','--unit='+job['observer_unit'],
                    '-p','CPUQuota=10%','-p','MemoryMax=192M','-p','TasksMax=16','-p','Restart=no',
                    '/usr/bin/python3','-I','-B',str(checked(job['window_observer'])),'--plan',str(plan_path)]
                launched=subprocess.run(command,capture_output=True,text=True,timeout=10)
                write(directory/'original-launch.json',dict(argv=command,exit=launched.returncode,
                    stdout=launched.stdout,stderr=launched.stderr),exclusive=True)
                assert launched.returncode==0,'Original fresh-window launch failed'
                status.update(state='fresh_window_launched',window_plan=pin(plan_path),observer_unit=job['observer_unit'])
                write(directory/'activation.json',status,exclusive=True)
                return
            time.sleep(job['interval_s'])
    write(directory/'readiness-bound.json',dict(state='readiness_wait_bound_reached',
        attempts=attempts,no_window_started=True,no_main_runtime_or_learning_change=True),exclusive=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True);parser.add_argument('--job-sha256',required=True)
    args=parser.parse_args()
    job=json.loads(checked(dict(path=str(args.job),sha256=args.job_sha256)).read_bytes())
    try:run(job)
    except BaseException as error:
        directory=Path(job['output'])
        if directory.exists():write(directory/'readiness-failure.json',dict(state='failed',reason=repr(error),
            original_wait_preserved=True,no_main_runtime_changed=True),exclusive=True)
        raise
