"""Read-only actual API validation; never constructs or runs a stop job."""
import argparse
import importlib.util
import json
from pathlib import Path
import urllib.request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--header', type=Path)
    p.add_argument('--header-sha256')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if not a.execute:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    import hashlib
    assert hashlib.sha256(a.header.read_bytes()).hexdigest() == a.header_sha256
    spec = importlib.util.spec_from_file_location('_read_only_stop_header', a.header)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    packet = json.loads((a.header.parent.parent / 'prepared-current-source-family.json').read_bytes())
    recovery = a.header.parent.parent.parent / 'reboot-recovery-20261031-original01'
    f = json.loads((recovery / 'fleet-v6-original01/status.json').read_bytes())
    selection = dict(schema='robotron-root-current-continuous-preservation-selection-v1',
        owner=packet['previous_owner'], expected_current_cap=8, first_current_main_stop=False,
        fleet={('starttime_ticks' if k == 'birth' else k): v for k, v in f['supervisor'].items() if k != 'source'},
        startup_job=h.metadata(recovery / 'startup-metadata-original01/startup-job.json')[0],
        startup_held=h.metadata(recovery / 'startup-held-original01/verified-held-before-first-update.json')[0],
        startup_release_consumed=h.metadata(recovery / 'startup-held-original01/release-consumed.json')[0])
    anchor = h.load('inputs').startup_anchor(selection)
    # Construction creates output/state for the real operation. Deliberately
    # bypass it; supply only the fields used by this read-only API method.
    kernel = h.load('stop_kernel')
    value = object.__new__(kernel.Stop)
    value.owner = selection['owner']
    value.holds = {}
    value.u = h.load('linux')
    value.counter = 0
    assert a.output.is_absolute() and not a.output.exists()
    a.output.mkdir(mode=0o700)
    value.out = a.output
    x = json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=10))
    value.job = dict(experiment=x['managed_experiment'], exposure_instances={
        k: anchor['exposure_at_load'][k]['instance_monotonic_ns'] for k in ('optimizer', 'replay')})
    observed = value.api()
    report = h.put(a.output / 'report.json', dict(
        status='PASS_ACTUAL_LIVE_INHERITED_STOP_API_READONLY', owner=selection['owner'],
        kernel=h.SOURCES['stop_kernel'], raw_API=value.final_API,
        observed_API={k: observed[k] for k in ('ts', 'training_steps', 'learner_frame_count',
                                             'optimized_samples', 'client_count', 'lr')},
        service_action_performed=False, constructor_executed=False, live_source_changed=False,
        test_source=h.metadata(Path(__file__).resolve())[0]))
    print(json.dumps({k: report[k] for k in ('path', 'sha256', 'bytes')}))


if __name__ == '__main__':
    main()
