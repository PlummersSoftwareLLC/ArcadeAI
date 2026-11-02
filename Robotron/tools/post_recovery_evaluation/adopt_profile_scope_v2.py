"""Independently close one original CPU compatibility scope and preserve facts."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    spec = importlib.util.spec_from_file_location('_profile_adoption_helpers', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def adopt(directory, unit, pid, invocation, closed_terminal=None):
    h = load(ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    directory = Path(directory).resolve()
    job_pin = h.pin(directory/'job.json')
    job = json.loads(h.checked(job_pin).read_bytes())
    for key in ('driver', 'package', 'checkpoint', 'canonical_CPU_facts', 'benchmark'):
        h.checked(job[key])
    require(job['driver']['path'] == str(Path(__file__).with_name('check_frozen_profile_cpu_v2.py')),
            'Exact corrected CPU compatibility producer required')
    if closed_terminal is None:
        properties = subprocess.check_output(['systemctl', '--user', 'show', unit], text=True, timeout=5)
        values = dict(line.split('=', 1) for line in properties.splitlines() if '=' in line)
    else:
        require(Path(closed_terminal).resolve() == directory/'actual-original-terminal-properties.json', 'Only the original owned terminal archive is eligible')
        terminal_input = h.pin(Path(closed_terminal).resolve())
        require(terminal_input['identity']['mode'] == '0o444', 'Original terminal archive must be immutable')
        values = json.loads(h.checked(terminal_input).read_bytes())
    expected = dict(MainPID='0', ExecMainPID=str(pid), InvocationID=invocation, ExecMainCode='1',
        ExecMainStatus='0', Result='success', NRestarts='0', Restart='no', CPUQuotaPerSecUSec='2s',
        MemoryMax=str(4 << 30), MemorySwapMax='0', TasksMax='128', RuntimeMaxUSec='3min')
    require(unit.startswith('robotron-') and all(values[key] == value for key, value in expected.items()),
            'Actual original CPU scope/exit/resources differ')
    require(all(token in values['ExecStart'] for token in
                (job['driver']['path'], job_pin['path'], job_pin['sha256'], 'CUDA_VISIBLE_DEVICES=')),
            'Actual original producer/job/CPU isolation differs')
    before = int(values['ExecMainStartTimestampMonotonic'])/1e6
    after = int(values['ExecMainExitTimestampMonotonic'])/1e6
    require(0 < after-before <= 180, 'Actual original CPU elapsed bound differs')
    require(not Path('/proc', str(pid)).exists(), 'Original CPU process remains')
    output = Path(job['output'])
    proof_pin = h.pin(output/'profile-compatibility.json')
    proof = json.loads(h.checked(proof_pin).read_bytes())
    require(proof['checkpoint'] == job['checkpoint'] and proof['package'] == job['package']
            and proof['matched_canonical_CPU_facts'] == job['canonical_CPU_facts']
            and proof['inference_model_compatibility_passed'] is True
            and proof['source_files_verified'] == 123 and proof['CUDA_initialized'] is False,
            'Actual profile proof binding differs')
    canonical = json.loads(h.checked(job['canonical_CPU_facts']).read_bytes())
    raw_path = output/'result.json'
    raw_pin = h.pin(raw_path)
    raw = raw_path.read_bytes()
    require(h.pin(raw_path) == raw_pin, 'CPU facts changed after writer exit')
    frozen = json.loads(raw)
    fields = ('checkpoint_sha256', 'copied_state_sha256', 'checkpoint_metadata', 'numeric_policy',
              'q_min', 'q_max', 'q_mean', 'q_sha256', 'greedy_actions')
    require(all(frozen[key] == canonical[key] for key in fields), 'Full CPU Q/action/metadata facts differ')
    require(frozen['cuda_initialized'] is False and frozen['inference_error'] is None,
            'Actual CPU inference failed or initialized CUDA')
    _, package = h.package_inputs(job['package'])
    require(len(package) == 123, 'Actual frozen package closure differs')
    archive = directory/'frozen-CPU-facts.exact.json'
    if archive.exists():
        require(closed_terminal is not None and archive.read_bytes() == raw
                and archive.stat().st_mode & 0o222 == 0, 'Existing original archive differs')
    else:
        with archive.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == raw_pin['sha256'], 'Facts archive differs')
    if closed_terminal is None:
        terminal = h.put(directory/'actual-original-terminal-properties.json', values)
        stopped = subprocess.run(['systemctl', '--user', 'stop', unit], capture_output=True, text=True, timeout=10)
        require(stopped.returncode == 0, 'Original exited CPU scope release failed')
    else:
        terminal = terminal_input
    released = subprocess.check_output(['systemctl', '--user', 'show', unit, '-p',
        'LoadState,ActiveState,SubState,MainPID'], text=True, timeout=5)
    require(values['Slice'] == 'app.slice', 'Original CPU scope used an unexpected slice')
    expected_group = '/user.slice/user-%d.slice/user@%d.service/app.slice/%s' % (os.getuid(), os.getuid(), unit)
    recorded_group = values.get('ControlGroup')
    require(not recorded_group or recorded_group == expected_group, 'Recorded original cgroup differs')
    require('MainPID=0' in released and 'ActiveState=inactive' in released
            and not Path('/sys/fs/cgroup'+expected_group).exists(), 'Original CPU scope remains')
    return h.put(directory/'independent-profile-adoption.json', dict(
        schema='robotron-frozen-profile-CPU-independent-adoption-v1', status='PASS',
        original_job=job_pin, original_PID=pid, original_invocation=invocation,
        actual_exit=0, actual_resources_and_argv_verified=True, original_terminal=terminal,
        original_scope_released=True, released_properties=released,
        expected_cgroup_absent=expected_group, live_cgroup_property_not_retained=not bool(recorded_group),
        original_terminal_archive_used=closed_terminal is not None,
        original_frozen_facts=raw_pin, immutable_frozen_facts=h.pin(archive), profile_proof=proof_pin,
        all_Q_bytes_and_actions_match=True, synthetic_inputs_not_gameplay=True,
        GPU_numeric_or_gameplay_parity_proven=False, scientific_launch_qualified=False,
        quality_qualified=False, source=h.pin(Path(__file__).resolve())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adopt', action='store_true')
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--unit')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--invocation')
    parser.add_argument('--closed-terminal', type=Path)
    args = parser.parse_args()
    if args.adopt:
        print(json.dumps(adopt(args.directory, args.unit, args.pid, args.invocation, args.closed_terminal)), flush=True)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
