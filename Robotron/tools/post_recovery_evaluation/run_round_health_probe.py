"""One bounded read-only engineering probe of the round-aware main validator."""
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


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())


def run(job):
    directory = Path(job['output'])
    directory.mkdir()
    spec = importlib.util.spec_from_file_location('_round_health_original_probe', checked(job['source']))
    health = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(health)
    case = json.loads(checked(job['case']).read_bytes())
    health.check_inputs(case, full=True)
    assert job['duration_s'] == 180 and job['interval_s'] == 5
    started = time.monotonic()
    previous = None
    accepted = 0
    retired_during_probe = set()
    observed_turnovers = 0
    retries = []
    try:
        while True:
            checked(job['source'])
            checked(job['driver'])
            health.check_inputs(case)
            deadline = time.monotonic() + 25
            while True:
                try:
                    sample = health.collect(case)
                    health.validate(case, sample, previous=previous)
                    break
                except (OSError, ValueError) as error:
                    retries.append(dict(unix_s=time.time(), reason=str(error)))
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.5)
            if previous is not None:
                if sample['status']['round'] == previous['status']['round']:
                    retired_during_probe.update(set(sample['results']) - set(previous['results']))
                else:
                    observed_turnovers += 1
            write(directory / ('sample-%04d.json' % accepted), sample)
            previous = sample
            accepted += 1
            print(json.dumps(dict(sample=accepted, round=sample['status']['round'],
                active=sample['status']['active'], completed=sample['status']['completed'])), flush=True)
            if time.monotonic() - started >= job['duration_s']:
                break
            time.sleep(job['interval_s'])
        health.check_inputs(case, full=True)
        write(directory / 'result.json', dict(state='passed_read_only_engineering_prefix',
            samples=accepted, elapsed_s=time.monotonic()-started,
            natural_retirements_observed=sorted(retired_during_probe),
            actual_round_turnovers_observed=observed_turnovers, transient_retries=retries,
            current_full_input_count=len(case['inputs']), original_job=job,
            private_evaluator_changed=False, main_runtime_changed=False,
            scientific_cohort_launch_qualified=False, quality_qualified=False))
    except BaseException as error:
        write(directory / 'failure.json', dict(state='failed', samples=accepted,
            reason=str(error), original_attempt_retained=True, transient_retries=retries,
            main_runtime_or_private_evaluator_changed=False, quality_qualified=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--job-sha256', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        path = checked(dict(path=str(args.job), sha256=args.job_sha256))
        run(json.loads(path.read_bytes()))
    else:
        print('PLAN_ONLY: no reads, writes or process actions')
