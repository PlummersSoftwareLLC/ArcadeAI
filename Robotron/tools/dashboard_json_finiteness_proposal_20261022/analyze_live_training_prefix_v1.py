"""Describe all complete main captures in a live R1 prefix; no runtime changes.

Retrospective telemetry only. No experiment, causal speed claim, scientific
cohort qualification, optimizer step, model load or process operation.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G/'tools/startup_policy_journal_proposal'
N = G/'logs/managed-learning-20261015/run-26/quality32-protected1741-vs-normal2259-after-JSON-original01-preparation-20261022'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analyze', action='store_true')
    args = parser.parse_args()
    if not args.analyze:
        print('PLAN_ONLY')
        return 0
    h = load('_training_prefix_h', B/'run_full_policy_startup_v3.py')
    require(h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'Helper changed')
    job_pin = h.pin(N/'01-reference/job.json')
    require(job_pin['sha256'] == '5ac7ea00b60891b4c33b11dcb4bd9d533a171a0cfe06411fc94b9ebc6c5fdb33', 'Original live R1 job changed')
    job = json.loads(h.checked(job_pin).read_bytes())
    binding_pin = job['main_binding']
    binding = json.loads(h.checked(binding_pin).read_bytes())
    guard = load('_training_prefix_guard', h.checked(job['main_sources']['window']))
    sup = load('_training_prefix_supervision', h.checked(job['main_sources']['supervision']))
    audit = load('_training_prefix_strict_decoder', B/'audit_quality32_games_v1.py')
    require(h.pin(audit.__file__)['sha256'] == 'e106cb9d3a2131c34365daaf4638ccba97c94c02de00a4a33dfe4d7ce5876f9b', 'Strict decoder changed')
    baseline = audit.decode(h.checked(binding['baseline_API']).read_bytes())
    policy = json.loads(h.checked(binding['supervision_policy']).read_bytes())
    guard.owner_and_files(binding)
    observed = time.time()
    directory = Path(job['output'])/'main-observations'
    selected = []
    for index in range(10000):
        paths = [directory/f'{index:04d}-API.raw.json', directory/f'{index:04d}-census.json']
        if not all(path.exists() and path.stat().st_mode & 0o777 == 0o444 for path in paths):
            break
        selected.append((h.pin(paths[0]), h.pin(paths[1])))
    require(len(selected) >= 120, 'At least120 complete paired captures required')
    first = last = None
    gradient_flags = []
    previous = None
    lineage = None
    for index, (api_pin, census_pin) in enumerate(selected):
        api = audit.decode(h.checked(api_pin).read_bytes())
        census = json.loads(h.checked(census_pin).read_bytes())
        guard.healthy(api, baseline, binding['experiment'], census['unix_s'])
        state = sup.validate_snapshot(policy, census, api['client_count'])
        require(state['full_capacity'] and not state['pending'], 'Captured main192 was incomplete')
        require(type(api['loss']) in (int, float) and math.isfinite(api['loss']), 'Core loss is nonfinite')
        if api.get('grad_norm_nonfinite'):
            require(api['grad_norm'] is None and api['grad_norm_nonfinite'] in ('positive_infinity', 'negative_infinity', 'nan'),
                    'Optional diagnostic encoding differs')
            gradient_flags.append(dict(index=index, flag=api['grad_norm_nonfinite'], raw=api_pin))
        else:
            require(type(api['grad_norm']) in (int, float) and math.isfinite(api['grad_norm']), 'Unmarked diagnostic is invalid')
        exposure = api['host_pipeline']['learning_exposure']
        replay, optimizer = exposure['replay'], exposure['optimizer']
        require(replay['process_id'] == optimizer['process_id'] == binding['owner']['pid']
                and replay['epoch'] == optimizer['epoch'] == 1 and replay['available'] is optimizer['available'] is True,
                'Main exposure lineage or availability changed')
        identity = tuple((value['process_id'], value['instance_monotonic_ns'], value['epoch']) for value in (replay, optimizer))
        if lineage is None:
            lineage = identity
        require(identity == lineage, 'Process/counter instances changed')
        current = dict(ts=api['ts'], frame_count=api['frame_count'], learner_frame_count=api['learner_frame_count'],
            measurement_frames=api['measurement_frames'], training_steps=api['training_steps'], optimized_samples=api['optimized_samples'],
            accepted_total=replay['accepted_total'], accepted_learner_total=replay['accepted_learner_total'],
            accepted_by_source_total=replay['accepted_by_source_total'], optimizer_total=optimizer['total'])
        if previous is not None:
            require(current['ts'] > previous['ts'], 'Captured API timestamps did not advance')
            for name in ('frame_count', 'learner_frame_count', 'measurement_frames', 'training_steps',
                         'optimized_samples', 'accepted_total', 'accepted_learner_total'):
                require(type(current[name]) is int and current[name] >= previous[name], 'Captured clock moved backward')
            for name in ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable'):
                require(current['optimizer_total'][name] >= previous['optimizer_total'][name], 'Optimizer counter moved backward')
        first = first or current
        last = current
        previous = current
    elapsed = last['ts']-first['ts']
    delta = {key:last[key]-first[key] for key in ('frame_count', 'learner_frame_count', 'measurement_frames',
        'training_steps', 'optimized_samples', 'accepted_total', 'accepted_learner_total')}
    delta['accepted_by_source'] = {key:last['accepted_by_source_total'][key]-first['accepted_by_source_total'][key]
        for key in first['accepted_by_source_total']}
    delta['optimizer'] = {key:last['optimizer_total'][key]-first['optimizer_total'][key] for key in first['optimizer_total']}
    require(elapsed > 600 and sum(delta['accepted_by_source'].values()) == delta['accepted_total'], 'Telemetry interval differs')
    eligible = delta['frame_count']-delta['measurement_frames']
    rate = dict(raw_fleet_frames_s=delta['frame_count']/elapsed, learner_frames_s=delta['learner_frame_count']/elapsed,
        accepted_ring_inserts_s=delta['accepted_total']/elapsed, accepted_learner_inserts_s=delta['accepted_learner_total']/elapsed,
        optimizer_admitted_calls_s=delta['optimizer']['applied']/elapsed,
        logical_scheduled_samples_s=delta['optimized_samples']/elapsed,
        logical_samples_per_eligible_fleet_frame=delta['optimized_samples']/eligible,
        logical_samples_per_accepted_learner_insert=delta['optimized_samples']/delta['accepted_learner_total'])
    guard.owner_and_files(binding)
    output = N/'readonly-current-main-training-prefix-original01'
    require(not output.exists(), 'Original passive prefix analysis already consumed')
    output.mkdir(mode=0o700)
    receipt = h.put(output/'readback.json', dict(schema='robotron-readonly-live-main-training-prefix-description-v1',
        classification='RETROSPECTIVE_PASSIVE_TELEMETRY_NOT_CONTROLLED_GAIN_OR_QUALITY_REVIEW',
        source=h.pin(__file__), job=job_pin, current_main_binding=binding_pin,
        selection='Every complete immutable API/census pair from0000 through the latest complete pair present at selection time; no score-based selection.',
        selection_unix_s=observed, captured_pairs=selected, samples=len(selected), elapsed_s=elapsed,
        first=first, last=last, delta=delta, descriptive_rates=rate, optional_gradient_flags=gradient_flags,
        strict_JSON_errors=0, main_source_holds=197, main_actor_slots=192,
        no_optimizer_or_replay_instance_transition=True,
        denominator_explanation='Raw fleet frames include all actor modes. Greedy/low-epsilon autonomous eval experience intentionally trains; only dqn+epsilon actions advance learner_frame_count. Ring insert categories separately count eval/expert/dqn/epsilon. The cap uses eligible fleet frames, not accepted_learner_total.',
        source_evidence={name:h.pin(G/'Scripts/dqn'/name) for name in ('socket_server.py', 'config.py', 'learning_exposure.py', 'agent.py', 'replay_buffer.py')},
        limitations=['Cached fields are not an atomic optimizer/replay transaction.',
            'Admitted optimizer calls do not prove every parameter moved or every Adam counter advanced.',
            'No controlled speed/learning comparison or policy score qualification; complete original scientific reviews remain required.',
            'No nonfinite gradient capture in this prefix would not prove future captures cannot contain the explicitly encoded diagnostic.'],
        original_scientific_reader_rerun=False, main_runtime_changed=False, instrumentation_changed=False,
        quality_qualified=False, learning_speed_gain_verified=False, created_unix_s=time.time()))
    print(json.dumps(dict(receipt=receipt, samples=len(selected), elapsed_s=elapsed, delta=delta, descriptive_rates=rate,
        optional_gradient_flags=len(gradient_flags))), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
