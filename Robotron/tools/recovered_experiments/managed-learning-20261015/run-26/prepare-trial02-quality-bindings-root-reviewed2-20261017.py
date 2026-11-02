"""Root preparation after actual trial02 completion; never starts a process or trial."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

REPO = Path('/home/dave/source/repos/ArcadeAI')
GAME = REPO / 'Robotron'
BASE = GAME / 'logs/managed-learning-20261015'
RUN = BASE / 'run-26'
SOURCES = GAME / 'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/fresh_quality_trial02_binding_companions_proposal'
TRIAL = RUN / 'rawKL-trial02-controller-20261017'
RETURN = RUN / 'rawKL-trial02-return-CE-20261017'
OUT = RUN / 'rawKL-trial02-quality-binding-root-preparation-20261017'
ADAPTER = GAME / 'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/live_one_trial_installed_ce_revision2_proposal/run_raw_kl_transition.py'
ADAPTER_SHA = 'fd4e9d7b9b562c2bd6c663b9651d02b4167a3f552fcacb71cb8571440f3e9bf5'


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def pin(path):
    path = Path(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = identity(os.fstat(stream.fileno()))
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        assert before == identity(os.fstat(stream.fileno())) == identity(path.lstat()), path
    return dict(path=str(path), sha256=digest, bytes=before['bytes'], identity=before)


def read(path):
    return json.loads(Path(path).read_text())


def pinned(path, digest):
    value = pin(path)
    assert value['sha256'] == digest and value['identity']['mode'] == '0o444', path
    return value


def save(name, value, raw=False):
    path = OUT / name
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=raw)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    fd = os.open(OUT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return pin(path)


def archive_metadata(source, name):
    before = pin(source['path'])
    assert before == source
    data = Path(source['path']).read_bytes()
    assert len(data) == source['bytes'] and hashlib.sha256(data).hexdigest() == source['sha256']
    path = OUT / name
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    fd = os.open(OUT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    assert pin(source['path']) == before
    archived = pin(path)
    assert archived['sha256'] == source['sha256'] and archived['bytes'] == source['bytes']
    return archived


def module(path, digest, name):
    assert pin(path)['sha256'] == digest
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def unit(name):
    result = subprocess.run(['systemctl', '--user', 'show', name, '--all'],
                            capture_output=True, text=True, timeout=20, check=True)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def proc_start(pid):
    return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--owned-cleanup', type=Path)
    parser.add_argument('--owned-cleanup-sha256')
    parser.add_argument('--guards', type=Path)
    parser.add_argument('--guards-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN ONLY: actual completed trial, CE return, terminal cleanup, source peer and guard proof are required; no reads or actions.')
        return
    sys.dont_write_bytecode = True
    manifest_pin = pinned(SOURCES / 'preparation-manifest.json', args.manifest_sha256)
    manifest = read(manifest_pin['path'])
    for name, expected in manifest['files'].items():
        observed = pinned(SOURCES / name, expected['sha256'])
        assert observed['bytes'] == expected['bytes']
    cleanup_pin = pinned(args.owned_cleanup, args.owned_cleanup_sha256)
    guards_pin = pinned(args.guards, args.guards_sha256)
    cleanup = read(cleanup_pin['path'])
    assert str(cleanup['status']).startswith('PASS') and cleanup['owned_cleanup_complete'] is True
    assert read(guards_pin['path'])['status'] == 'PASS'
    result = read(TRIAL / 'result.json')
    assert result['status'] == 'COMPLETE' and not result['manual_recovery_required']
    ce = read(result['CE_return']['path'])
    assert result['CE_return'] == pin(RETURN / 'result.json')
    assert ce['status'] == 'READY' and ce['mode'] == 'return_ce' and not ce['manual_recovery_required']
    assert ce['owner']['pid'] != result['retired_owner']['pid']
    outer = read(result['root_job']['path'])
    original_job = read(RUN / 'rawKL-trial02-final-root-preparation-20261017/activation-job-FINAL.json')
    return_job = read(RETURN / 'root-job.json')
    assert pin(ADAPTER)['sha256'] == ADAPTER_SHA
    live_pin = return_job['helper_pins']['live_host']
    sys.path.insert(0, str(GAME / 'tools'))
    live = module(Path(live_pin['path']), live_pin['sha256'], '_root_quality_trial02_live_host')

    class Host(live.LiveHost):
        def runtime_dropin(self):
            return Path(return_job['original_dropin']['path'])

    host = Host(return_job['trainer_unit'], return_job['fleet_unit'])
    binding = host.describe()
    assert binding['bindings']['source_hashes'] == return_job['before']['bindings']['source_hashes']
    assert binding['bindings']['control_hashes'] == return_job['before']['bindings']['control_hashes']
    assert binding['bindings']['actors'] == original_job['before']['bindings']['actors']
    assert binding['fleet']['MainPID'] == original_job['before']['fleet']['MainPID'] == '2258189'
    assert binding['supervisor_start_ticks'] == original_job['before']['supervisor_start_ticks']
    current_unit = unit(return_job['trainer_unit'])
    assert current_unit['MainPID'] == str(ce['owner']['pid'])
    assert current_unit['InvocationID'] == ce['owner']['invocation_id']
    assert current_unit['ControlGroup'] == ce['owner']['cgroup']
    assert proc_start(ce['owner']['pid']) == ce['owner']['starttime_ticks']
    assert current_unit['ActiveState'] == 'active' and current_unit['SubState'] == 'running'
    assert current_unit['Restart'] == 'no' and current_unit['NRestarts'] == '0'
    fleet_unit = unit(return_job['fleet_unit'])
    fleet_owner = dict(pid=int(fleet_unit['MainPID']), starttime_ticks=proc_start(int(fleet_unit['MainPID'])),
                       unit=return_job['fleet_unit'], invocation_id=fleet_unit['InvocationID'],
                       cgroup=fleet_unit['ControlGroup'])
    assert fleet_owner['invocation_id'] == '5ade9b2810524877921946df11ea597e'
    worker = binding['bindings']['worker']
    assert worker['trainer']['pid'] == ce['owner']['pid']
    assert worker['trainer']['starttime_ticks'] == ce['owner']['starttime_ticks']
    actors = [dict(pid=actor['pid'], starttime_ticks=actor['starttime_ticks'], slot=actor['client_slot'],
                   mask=sorted(os.sched_getaffinity(actor['pid']))) for actor in binding['bindings']['actors']]
    assert len(actors) == 192 and sorted(actor['slot'] for actor in actors) == list(range(192))
    assert all(actor['mask'] == list(range(72)) for actor in actors)
    inference = dict(tid=worker['thread']['tid'], starttime_ticks=worker['thread']['starttime_ticks'],
                     mask=sorted(os.sched_getaffinity(worker['thread']['tid'])))
    assert inference['mask'] == sorted(os.sched_getaffinity(ce['owner']['pid'])) == list(range(72))
    raw_environment = Path('/proc', str(ce['owner']['pid']), 'environ').read_bytes().split(b'\0')
    environment = {key.decode(): value.decode() for pair in raw_environment if b'=' in pair
                   for key, value in [pair.split(b'=', 1)]
                   if key.decode().startswith(('DQN_', 'ROBOTRON_', 'CUDA_', 'TORCHINDUCTOR_'))}
    phase = ce['startup_phase_proof']['phase']
    assert environment['DQN_PER_PRIORITY_METRIC'] == 'ce'
    assert environment['DQN_PRIORITY_PHASE_RECORD_SHA256'] == phase['record']['sha256']
    assert environment['DQN_PRIORITY_PHASE_RECORD'] == phase['record']['path']
    assert 'DQN_RECOMPUTED_CE_CAPTURE_DIR' not in environment and 'DQN_EXECUTED_CE_TRACE_DIR' not in environment
    assert pin(phase['record']['path']) == phase['record']
    files = {}
    for fields in (current_unit, fleet_unit):
        for path in [fields['FragmentPath'], *fields['DropInPaths'].split()]:
            files[path] = pin(path)['sha256']
    assert not (GAME / 'models_dqn/managed_save.request.json').exists()
    host.adopt_initial(binding)
    host.metric_host.configure_logs(binding['bindings']['logs'])
    row = host.capture()
    profile = dict(batch_size=4096, replay_cap=8,
                   initial_snapshot=dict(csv=return_job['baseline_csv']),
                   exposure_identity={key:live.metrics.exposure_key(row['exposure'][key]) for key in ('optimizer', 'replay')})
    assert not live.metrics.api_issues(row, profile)
    assert row['client_count'] == 192 and row['exposure']['optimizer']['process_id'] == ce['owner']['pid']
    binding_module = module(SOURCES / 'quality_bindings.py', manifest['files']['quality_bindings.py']['sha256'], '_root_trial02_quality_binding')
    OUT.mkdir(mode=0o700)
    health_pin = save('post-return-CE-all192-root-health.json', dict(binding=binding, API=row,
                      actors_with_actual_masks=actors, inference_worker=inference, unit_files=files), raw=True)
    baseline = dict(schema='robotron-rawKL-trial02-post-return-quality-baseline-v1', status='PASS',
                    main_owner=ce['owner'], fleet_owner=fleet_owner, inference_worker=inference,
                    actors=actors, source_hashes=binding['bindings']['source_hashes'],
                    control_hashes=binding['bindings']['control_hashes'], unit_files=files,
                    environment_sha256=hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest())
    baseline_pin = save('post-return-CE-runtime-baseline.json', baseline)
    early_readonly = archive_metadata(result['early_insurance'], 'early-insurance-numeric-report-readonly.json')
    selected_cpu = ce['ending']['candidate_CPU']
    cpu_report = read(selected_cpu['path'])
    cpu_root = Path(selected_cpu['path']).parent
    candidate = result['candidate']['source']
    assert pin(candidate['path']) == candidate
    predecessor = BASE / 'quality-384M-vs-448M-20261017/plan.json'
    concrete = dict(schema=binding_module.SCHEMA, experiment=return_job['experiment'],
        candidate=dict(tag=binding_module.TAG, path=candidate['path'], sha256=candidate['sha256'], bytes=candidate['bytes']),
        evidence=dict(phase_cpu_job=pin(cpu_root/'cpu-job.json'), phase_cpu_report=selected_cpu,
            phase_cpu_completion=pin(cpu_root/'cpu-completion.json'), trial_result=pin(TRIAL/'result.json'),
            outer_job=result['root_job'], activation_job=outer['activation_job'], trial_core=outer['trial_core'],
            activation=result['activation'], observer=result['observer'], decision=result['decision']['event'],
            durability=result['decision']['durability'], ce_return=result['CE_return'],
            early_insurance=early_readonly, deadline_result=pin(TRIAL/'deadline-result.json'), owned_cleanup=cleanup_pin),
        runtime_baseline=baseline_pin, runtime_anchor={key:value for key,value in baseline.items() if key not in ('schema', 'status')},
        actual_launch_identities=pin(binding_module.ACTUAL_LAUNCH_IDENTITIES),
        original_executions=cleanup['original_executions'], predecessor_quality_plan=pin(predecessor),
        campaign=dict(output_directory=str(BASE/'quality-448M-vs-rawKL-trial02-first8M-20261017'),
            preview_directory=str(RUN/'rawKL-trial02-quality-default-plan-prelaunch-20261017'),
            execution_directory=str(RUN/'rawKL-trial02-quality-durable-launch-20261017'),
            unit='robotron-quality-448M-vs-rawkl-trial02-first8M-20261017',
            reference_label='fresh3-448M-reference', candidate_label='rawkl-trial02-first8M-candidate',
            hypothesis='The first frozen candidate after bounded sequential raw-KL trial02 improves greedy full-game score over protected448 under fresh common-backend cohorts.'))
    assert all(not Path(concrete['campaign'][key]).exists() for key in ('output_directory', 'preview_directory', 'execution_directory'))
    checked = binding_module.validate(concrete)
    assert checked['proof'] == cpu_report
    job_pin = save('root-quality-binding-job.json', concrete)
    receipt = save('root-quality-binding-preparation.json', dict(status='PASS_ACTUAL_BINDINGS_NO_PLAN_OR_LAUNCH',
        binding_job=job_pin, manifest=manifest_pin, guards=guards_pin, owned_cleanup=cleanup_pin,
        post_return_health=health_pin, post_return_baseline=baseline_pin,
        candidate_phase_CPU=selected_cpu, prepared_monotonic_s=time.monotonic(),
        actual_default_plan=None, launched=False, candidate_quality_claim=False))
    print(json.dumps(dict(status='PASS_ACTUAL_BINDINGS_NO_PLAN_OR_LAUNCH', receipt=receipt, job=job_pin)))


if __name__ == '__main__':
    main()
