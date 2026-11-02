"""Read-only120s observation of the original corrected-source runtime and main."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME / 'logs/managed-learning-20261015/run-26'
STUDY = RUN / ('confirmed-scoring-quality-original01-preparation-20261018/'
               'capacity32-confirmed1059-score-carry-v1-preparation-20261019')


def require(value, message):
    if not value:
        raise ValueError(message)


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())


def load(name, path, sha):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == sha, 'Original reader changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return
    reader = load('_headroom_reader', GAME / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    guard = load('_headroom_main', RUN / 'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
        'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3')
    def read(path):
        return reader.read_pin(reader.pin(path))
    binding = read(STUDY / 'runtime-bindings-controller02/main-binding.json')
    baseline = reader.read_pin(binding['baseline_API'])
    census = read(STUDY / 'root-original32-live-runtime-census.json')
    owner = reader.read_pin(census['native_owner'])
    outer = reader.read_pin(census['outer_owner'])
    plan = read(STUDY / 'planned-pilot.json')
    group = Path('/sys/fs/cgroup' + owner['cgroup'])
    boot = read(RUN / 'boundary-continuity-forward-recovery-original01-20261018/newest_stopped/CPU-report-readonly.json')
    anchor = boot['clocks']
    require(boot['status'] == 'PASS' and boot['sha256'] ==
        '6000d04108d0dcfd653ec8e80dd94b4dc92d992079927e391cc8ab5b1be7e823', 'Recorded boot evidence changed')
    args.output.mkdir(mode=0o700)
    write(args.output / 'observation-plan.json', dict(samples=13, interval_s=10,
        native_owner=census['native_owner'], outer_owner=census['outer_owner'],
        main_binding=reader.pin(STUDY / 'runtime-bindings-controller02/main-binding.json'),
        original_boot_CPU_report=reader.pin(RUN / 'boundary-continuity-forward-recovery-original01-20261018/newest_stopped/CPU-report-readonly.json'),
        captured_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        production_changed=False, study_changed=False, scope='Passive resource and clock context only; no causal speed, dose, policy gain or deployment validity.'))
    samples = []
    failure = None
    started = time.monotonic()
    try:
        for index in range(13):
            time.sleep(max(0., started + index * 10 - time.monotonic()))
            require(time.monotonic() - started < 180, 'Passive observation budget exceeded')
            guard.owner_and_files(binding)
            for original in (owner, outer):
                require(guard.process_start(original['pid']) == original['starttime_ticks'], 'Original private process ended or changed')
                raw = subprocess.check_output(['systemctl', '--user', 'show', original['unit']], text=True, timeout=5)
                fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
                require(fields['MainPID'] == str(original['pid']) and fields['InvocationID'] == original['invocation_id']
                        and fields['NRestarts'] == '0', 'Original private invocation changed')
            for original in census['original32_actors'].values():
                require(guard.process_start(original['pid']) == original['starttime_ticks']
                        and sorted(os.sched_getaffinity(original['pid'])) == original['affinity'], 'Original actor changed')
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
                api = json.load(response)
            guard.healthy(api, baseline, binding['experiment'], time.time())
            age = time.time() - (GAME / 'models_dqn/robotron_dqn_latest.pt').stat().st_mtime
            require(0 <= age <= 360, 'Main checkpoint stale')
            resource = subprocess.check_output(['nvidia-smi', '--query-gpu=uuid,utilization.gpu,memory.used,temperature.gpu',
                '--format=csv,noheader,nounits'], text=True, timeout=5)
            gpu = {}
            for line in resource.splitlines():
                uuid, utilization, memory, temperature = [x.strip() for x in line.split(',')]
                gpu[uuid] = dict(utilization_percent=float(utilization), memory_MiB=float(memory), temperature_C=float(temperature))
            status = json.loads((Path(plan['job']['directory']) / 'status.json').read_bytes())
            eligible = api['frame_count'] - anchor['frame_count'] - max(0, api['measurement_frames'] - anchor['measurement_frame_count'])
            sample = dict(unix_s=time.time(), monotonic_s=time.monotonic(), API=api,
                private_status=status, gpu=gpu, cpu_stat={key:int(value) for key,value in
                    (line.split() for line in (group / 'cpu.stat').read_text().splitlines())},
                memory_current=int((group / 'memory.current').read_text()), memory_peak=int((group / 'memory.peak').read_text()),
                memory_events=(group / 'memory.events').read_text(), autosave_age_s=age,
                reconstructed_loaded_anchor=dict(eligible_fleet_frames=eligible,
                    logical_samples=api['optimized_samples'] - anchor['optimized_samples'],
                    credit_at_cap8=8 * max(1, eligible) - (api['optimized_samples'] - anchor['optimized_samples'])),
                main193_and_original192_and_private32_verified=True)
            write(args.output / f'sample-{index:02d}.json', sample)
            samples.append(sample)
    except Exception as error:
        failure = repr(error)
    result = dict(status='PASS' if failure is None and len(samples)==13 else 'INCOMPLETE_OR_FAILED',
        error=failure, sample_count=len(samples), source_changed=False, study_changed=False,
        capacity_speedup_verified=False, learning_speed_gain_verified=False,
        anchor_scope='Reconstructed recorded loaded anchor only; not direct observation of any private warmup anchor.',
        clock_scope='Cached optimizer outcomes and top-level logical counters have different timestamps; never subtract one from the other to infer AMP skips.')
    if len(samples) >= 2:
        a,b=samples[0],samples[-1]
        elapsed=b['monotonic_s']-a['monotonic_s']
        result.update(elapsed_s=elapsed, private_mean_CPU_cores=(b['cpu_stat']['usage_usec']-a['cpu_stat']['usage_usec'])/1e6/elapsed,
            private_throttled_periods=b['cpu_stat']['nr_throttled']-a['cpu_stat']['nr_throttled'],
            private_peak_memory_bytes=max(x['memory_peak'] for x in samples),
            main_rates_per_s={key:(b['API'][key]-a['API'][key])/elapsed
                for key in ('frame_count','learner_frame_count','optimized_samples','training_steps')},
            gpu_means={uuid:{key:sum(x['gpu'][uuid][key] for x in samples)/len(samples)
                for key in ('utilization_percent','temperature_C')} for uuid in a['gpu']},
            reconstructed_cap8_credit_range=[min(x['reconstructed_loaded_anchor']['credit_at_cap8'] for x in samples),
                                           max(x['reconstructed_loaded_anchor']['credit_at_cap8'] for x in samples)])
    write(args.output / 'result.json', result)
    print(json.dumps(result))
    require(result['status']=='PASS', 'Preserve incomplete passive observation; do not alter or restart original study')


if __name__ == '__main__':
    main()
