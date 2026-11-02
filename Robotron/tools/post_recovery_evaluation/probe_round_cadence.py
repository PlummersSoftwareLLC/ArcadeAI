"""Measure round/TCP capture cadence under the actual current actor load."""
import argparse
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args):
    directory = args.output.resolve()
    directory.mkdir(mode=0o700)
    h = load('_cadence_evidence', ROOT / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    worker_path = Path(__file__).with_name('round_observer_v2.py')
    health_path = Path(__file__).with_name('round_health_transport.py')
    worker_pin, health_pin = h.pin(worker_path), h.pin(health_path)
    worker = load('_cadence_raw_API_collector', worker_path)
    health = load('_cadence_round_TCP_health', health_path)
    case_pin = h.pin(args.case.resolve())
    assert case_pin['sha256'] == args.case_sha256
    case = json.loads(h.checked(case_pin).read_bytes())
    health.check_inputs(case, full=True)
    started = time.monotonic()
    cpu_started = time.process_time()
    previous = None
    attempts = []
    for index in range(100):
        before = time.monotonic()
        assert before-started < 80, 'Original cadence experiment bound exceeded'
        h.checked(worker_pin)
        h.checked(health_pin)
        health.check_inputs(case)
        sample, error = None, None
        try:
            sample = worker.collect(health, case)
            health.validate(case, sample, previous=previous)
        except (ValueError, OSError) as failure:
            error = repr(failure)
        captured = time.monotonic()
        row = dict(index=index, started_monotonic_s=before,
            capture_s=captured-before, accepted=error is None, error=error, snapshot=sample)
        attempts.append(dict(evidence=h.put(directory / ('attempt-%04d.json' % index), row),
            capture_s=row['capture_s'], accepted=row['accepted'], start=before))
        if error is None:
            previous = sample
        time.sleep(max(0, .2-(time.monotonic()-before)))
    health.check_inputs(case, full=True)
    times = sorted(row['capture_s'] for row in attempts)
    accepted = [row for row in attempts if row['accepted']]
    gaps = [right['start']-left['start'] for left, right in zip(accepted, accepted[1:])]
    result = dict(schema='robotron-round-cadence-engineering-measurement-v1',
        status='MEASURED_NOT_SCIENTIFICALLY_QUALIFIED', original_sources=dict(worker=worker_pin, health=health_pin),
        case=case_pin, attempts=attempts, accepted=len(accepted), total=len(attempts),
        elapsed_s=time.monotonic()-started, process_CPU_s=time.process_time()-cpu_started,
        capture_min_s=times[0], capture_median_s=times[len(times)//2],
        capture_p95_s=times[int(.95*(len(times)-1))], capture_max_s=times[-1],
        maximum_accepted_start_gap_s=max(gaps, default=None),
        accepted_start_gaps_over_500ms=sum(gap > .5 for gap in gaps),
        sampled_active_counts=sorted({json.loads(h.checked(row['evidence']).read_bytes())['snapshot']['status']['active']
            for row in accepted}), full192_actor_load_not_yet_measured=True,
        preserves_legacy_500ms_main_health_contract=False,
        main_processes_or_learning_controls_changed=False,
        quality_or_causal_throughput_gain_qualified=False)
    h.put(directory/'result.json', result)
    print(json.dumps({key: value for key, value in result.items() if key not in ('attempts','original_sources','case')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--case', type=Path)
    parser.add_argument('--case-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.execute:
        run(args)
    else:
        print('PLAN_ONLY: no reads or process actions')
