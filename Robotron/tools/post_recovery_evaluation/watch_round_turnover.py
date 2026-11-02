"""Observe natural retirements and one complete round barrier without signals."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time


def checked(value):
    path = Path(value['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == value['sha256']
    return path


def write(path, value, exclusive=False):
    temporary = path if exclusive else path.with_name(path.name + '.tmp')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444 if exclusive else 0o664)
        os.fsync(stream.fileno())
    if not exclusive:
        os.replace(temporary, path)


def run(job):
    directory = Path(job['output'])
    directory.mkdir()
    spec = importlib.util.spec_from_file_location('_round_turnover_health', checked(job['source']))
    health = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(health)
    case = json.loads(checked(job['case']).read_bytes())
    health.check_inputs(case, full=True)
    assert job['maximum_s'] == 14400 and job['interval_s'] == 5
    started = time.monotonic()
    previous = None
    retired = set()
    turnovers = 0
    samples = events = retry_count = 0
    try:
        with (directory / 'observations.jsonl').open('x') as stream:
            while True:
                checked(job['driver'])
                checked(job['source'])
                health.check_inputs(case)
                deadline = time.monotonic() + 25
                while True:
                    try:
                        current = health.collect(case)
                        health.validate(case, current, previous=previous)
                        break
                    except (OSError, ValueError) as error:
                        stream.write(json.dumps(dict(retry_unix_s=time.time(), reason=str(error)))+'\n')
                        stream.flush()
                        retry_count += 1
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(.5)
                event = previous is None
                if previous is not None:
                    if current['status']['round'] == previous['status']['round']:
                        newly_retired = set(current['results']) - set(previous['results'])
                        retired.update(newly_retired)
                        event = bool(newly_retired)
                    else:
                        turnovers += 1
                        event = True
                if event:
                    write(directory / ('event-%04d.json' % events), current, exclusive=True)
                    events += 1
                samples += 1
                status = dict(state='observing_natural_round_transition', updated_unix_s=time.time(),
                    samples=samples, events=events, round=current['status']['round'],
                    active=current['status']['active'], completed=current['status']['completed'],
                    natural_retirements_observed=sorted(retired), round_turnovers_observed=turnovers,
                    elapsed_s=time.monotonic()-started, transient_retries=retry_count,
                    main_runtime_changed=False, scientific_launch_qualified=False)
                stream.write(json.dumps(status)+'\n')
                stream.flush()
                write(directory / 'status.json', status)
                if samples == 1 or samples % 12 == 0 or event:
                    print(json.dumps(status), flush=True)
                if (retired and turnovers) or time.monotonic()-started >= job['maximum_s']:
                    health.check_inputs(case, full=True)
                    status['state'] = ('natural_retirement_and_turnover_observed'
                                       if retired and turnovers else 'observation_bound_inconclusive')
                    write(directory / 'result.json', status, exclusive=True)
                    write(directory / 'status.json', status)
                    return
                previous = current
                time.sleep(job['interval_s'])
    except BaseException as error:
        write(directory / 'failure.json', dict(state='failed', reason=str(error),
            samples=samples, original_attempt_retained=True,
            main_runtime_or_private_evaluator_changed=False, scientific_launch_qualified=False),
            exclusive=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--job-sha256', required=True)
    args = parser.parse_args()
    run(json.loads(checked(dict(path=str(args.job),sha256=args.job_sha256)).read_bytes()))
