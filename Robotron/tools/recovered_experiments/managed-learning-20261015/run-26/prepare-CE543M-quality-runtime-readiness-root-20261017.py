"""Fresh read-only launch readiness using the already checked concrete bindings."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

REPO = Path('/home/dave/source/repos/ArcadeAI')
GAME = REPO / 'Robotron'
RUN = GAME / 'logs/managed-learning-20261015/run-26'
SRC = GAME / 'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/next_CE_quality_binding_companion_reviewed2_proposal'
OUT = RUN / 'CE543M-quality-fresh-runtime-readiness-root-20261017'
CARRIER_SHA = '6f6d0386e85a98f22fda3dacc55747d13f0f4978f0b8ce4c4906bba33bc1cfc5'
HELPER = RUN / 'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py'
HELPER_SHA = 'd525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'


def load(path, digest, name):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--binding-job', type=Path)
    parser.add_argument('--binding-job-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN ONLY: fresh explicit root binding required; no runtime queries or actions.')
        return
    sys.dont_write_bytecode = True
    carrier = load(SRC / 'root_quality_carrier.py', CARRIER_SHA, '_root_quality_ready_carrier')
    carrier.configure(SimpleNamespace(binding_job=args.binding_job, binding_job_sha256=args.binding_job_sha256,
                                     expected_source_sha256=CARRIER_SHA))
    bound, _ = carrier.inputs(args)
    cfg, bundle = carrier.CFG, carrier.BUNDLE
    helper = load(HELPER, HELPER_SHA, '_root_quality_ready_resources')
    OUT.mkdir(mode=0o700)
    def record(name, value):
        return helper.publish(OUT / (name + '.json'), value)
    capture_job = helper.pinned(bundle['capture']['root_job'])
    history = capture_job['history']
    original = helper.pinned(history['activation_job'])
    outer = helper.pinned(history['outer_job'])
    activation = helper.pinned(history['activation'])
    ce = helper.pinned(history['CE_return'])
    resources, raw_api = helper.current_ce_and_resources(outer, original, activation, ce, record)
    helper.publish(OUT / 'checked-resources.json', resources)
    helper.write_bytes(OUT / 'fresh-raw-API.json', raw_api)
    anchor = cfg['runtime_anchor']
    assert resources['owner'] == anchor['main_owner']
    for actor in anchor['actors']:
        assert resources['actor_masks'][str(actor['pid'])] == actor['mask']
    assert resources['inference_mask'] == anchor['inference_worker']['mask']
    assert not (GAME / 'models_dqn/managed_save.request.json').exists()
    unit_names = ['robotron-live-ce-candidate01-capture-20261017',
        'robotron-live-ce-candidate01-phase-cpu-20261017',
        'robotron-quality-448M-vs-rawkl-trial02-first8M-20261017',
        'robotron-rawkl-trial02-quality-terminal-closure-reviewed1-20261017'] + [
        f'robotron-rawkl-trial02-quality-leg{n:02d}-audit-reviewed1-20261017' for n in range(1,5)]
    releases = {}
    for name in unit_names:
        for suffix in ('.timer', '.service'):
            fields, raw = helper.show(name + suffix)
            assert fields['LoadState'] == 'not-found'
            releases[name + suffix] = raw
    helper.publish(OUT / 'all-previous-owned-units-released.json', releases)
    for path, digest in anchor['unit_files'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    memory = helper.command(['nvidia-smi', '--query-gpu=uuid,memory.free', '--format=csv,noheader,nounits'])
    assert memory['returncode'] == 0
    free = {row.split(',')[0].strip():int(row.split(',')[1]) * (1 << 20)
            for row in memory['stdout'].splitlines() if row.strip()}
    assert free[carrier.GPU0] >= 14 * (1 << 30)
    helper.publish(OUT / 'GPU-free-memory.json', memory)
    fleet = anchor['fleet_owner']
    status = Path('/proc', str(fleet['pid']), 'status').read_text()
    assert next(line.split()[1:] for line in status.splitlines() if line.startswith('Uid:')) == [str(os.getuid())] * 4
    assert helper.process_start(fleet['pid']) == fleet['starttime_ticks']
    helper.publish(OUT / 'fleet-process-descriptor.json', dict(owner=fleet,
        argv=[os.fsdecode(part) for part in Path('/proc', str(fleet['pid']), 'cmdline').read_bytes().split(b'\0') if part],
        cwd=os.readlink('/proc/' + str(fleet['pid']) + '/cwd'), exe=os.readlink('/proc/' + str(fleet['pid']) + '/exe')))
    fresh_fleet = json.loads((OUT/'fleet-process-descriptor.json').read_text())
    prior_fleet = json.loads((RUN/'live-CE-candidate01-fresh-runtime-baseline-root-20261017/actual-fleet-process-descriptor.json').read_text())
    assert fresh_fleet == {key:prior_fleet[key] for key in fresh_fleet}
    ready = dict(copy.deepcopy(anchor), schema='robotron-live-CE-exclusive-readiness-v1', status='PASS',
        observed_unix_s=time.time(), candidate=dict(source=cfg['candidate']['path'], sha256=cfg['candidate']['sha256'],
            bytes=cfg['candidate']['bytes'], root_job_sha256=bound['phase_cpu_job']['sha256'],
            cpu_proof_sha256=bound['phase_cpu_proof']['sha256']),
        resources=dict(gpu0_uuid=carrier.GPU0, gpu1_uuid=carrier.GPU1, GPU0_free_bytes=free[carrier.GPU0],
            GPU0_no_compute_owner=resources['GPU0_free'], GPU1_main_only=resources['sole_main_on_GPU1'],
            port9999_clear=resources['port9999_unused'], lease_free=resources['lease_unheld'],
            no_competing_helpers=resources['no_private_tmpfs_or_helpers'],
            no_private_cgroup_tmpfs_processes=resources['no_private_tmpfs_or_helpers'], no_pending_save=True,
            capture_and_CPU_units_released=True, commands_UID_cwd_exe_checked=True,
            held_environment_checked=True, unit_files_checked=True))
    # This reruns live main/fleet/192, source/control, selected environment SHA,
    # phase record, GPU/lease/port and current API checks before publishing PASS.
    current = carrier.fast_runtime(ready)
    carrier.readiness_contract(ready, bound)
    actual = helper.publish(OUT / 'runtime-readiness.json', ready)
    helper.publish(OUT / 'root-readiness-result.json', dict(status='PASS', readiness=actual,
        current=current, binding_job=carrier.BINDING_PIN, candidate_quality_claim=False, launched=False))
    print(json.dumps(dict(status='PASS', readiness=actual, current=current)))


if __name__ == '__main__':
    main()
