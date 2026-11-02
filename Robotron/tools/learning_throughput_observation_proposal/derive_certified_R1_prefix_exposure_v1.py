"""Describe one fixed archived R1 main-training interval; default is inert.

No API request, benchmark, scientific main, service change or numerical runtime.
All original records are retained; these rates do not establish a speed gain.
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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(value, message):
    if not value:
        raise ValueError(message)


def derive(selection_pin, h, reader):
    artifacts = []
    def read(entry, as_json=True):
        value = reader.read_pin(entry, as_json=as_json)
        artifacts.append(entry)
        return value
    selection = read(selection_pin)
    require(selection['schema'] == 'robotron-certified-R1-fixed-archived-exposure-selection-v1'
        and selection['source'] == h.pin(__file__) and selection['sample_count'] == 120,
        'Exact fixed time-selected original prefix required')
    output = Path(selection['output'])
    require(not output.exists(), 'Original descriptive derivation already consumed')
    job = read(selection['original_R1_job'])
    require(job['quality_leg'] == 'R1' and job['original_attempt'] == 1 and job['no_retry'] is True,
        'Original first reference leg required')
    main = read(job['main_binding'])
    policy = read(main['supervision_policy'])
    require(policy['trainer'] == main['owner'], 'Original trainer binding differs')
    for name, digest in [('supervision', '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0')]:
        entry = job['main_sources'][name]
        require(entry['sha256'] == digest, 'Original main supervision source differs')
        read(entry, False)
    supervision = load('_archived_R1_main_supervision', job['main_sources']['supervision']['path'])
    archives_path = G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
    archives_pin = h.pin(archives_path)
    require(archives_pin['sha256'] == '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445',
        'Original optimizer counter validator changed')
    read(archives_pin, False)
    archives = load('_archived_R1_optimizer_counter_validator', archives_path)
    indices = list(range(selection['first_index'], selection['last_index']+1))
    require(len(indices) == 120 and [row['index'] for row in selection['records']] == indices,
        'Every consecutive selected sample required')
    samples = []
    epochs = []
    ages = []
    pending = []
    for record in selection['records']:
        root = Path(job['output'])/'main-observations'
        require(record['API']['path'] == str(root/f"{record['index']:04d}-API.raw.json")
            and record['census']['path'] == str(root/f"{record['index']:04d}-census.json"),
            'Original prefix record path differs')
        api = read(record['API'])
        census = read(record['census'])
        state = supervision.validate_snapshot(policy, census, api['client_count'])
        require(state['full_capacity'] is True and state['completed_episodes'] == [],
            'Original main192 birth continuity required; no recovery allowance')
        require(api['training_enabled'] is True and api['measurement_active'] is False
            and api['lr'] == 1.25e-5 and api['epsilon'] == 0.1
            and math.isfinite(api['loss']) and api['pipeline_read_error'] == api['bank_persistence_read_error'] == ''
            and api['bank_persistence']['write_failures'] == 0, 'Original fixed phase/health differs')
        pipeline = api['host_pipeline']
        require(pipeline['available'] is True and pipeline['generation'] == 0
            and all(pipeline[k]['errors'] == 0 for k in ['inference', 'actor_refresh', 'target_refresh', 'learner_priority']),
            'Original host pipeline changed or failed')
        exposure = pipeline['learning_exposure']
        optimizer, replay = exposure['optimizer'], exposure['replay']
        pending.append(archives.inspect_optimizer_observation(optimizer))
        require(replay['enabled'] is replay['available'] is True
            and replay['process_id'] == optimizer['process_id'] == main['owner']['pid'],
            'Replay/optimizer counter owner differs')
        epochs.append([optimizer['instance_monotonic_ns'], optimizer['epoch'], replay['instance_monotonic_ns'], replay['epoch']])
        ages.append(api['pipeline_snapshot_age_s'])
        require(type(ages[-1]) in (float, int) and 0 <= ages[-1] <= 5, 'Stale pipeline snapshot')
        if samples:
            previous = samples[-1]
            require(0 < api['ts']-previous['API']['ts'] <= 30
                and 0 < census['monotonic_s']-previous['census']['monotonic_s'] <= 30,
                'Original observation clock regressed')
            for key in ['frame_count', 'learner_frame_count', 'training_steps', 'optimized_samples']:
                require(api[key] >= previous['API'][key], 'Original top-level counter regressed')
            prior = previous['API']['host_pipeline']['learning_exposure']
            require(all(optimizer['total'][key] >= value for key, value in prior['optimizer']['total'].items())
                and all(replay[key] >= prior['replay'][key] for key in ['accepted_total', 'accepted_learner_total']),
                'Original exposure counter regressed')
        samples.append(dict(API=api, census=census))
    require(all(epoch == epochs[0] for epoch in epochs), 'Original exposure epoch changed')
    a, z = samples[0]['API'], samples[-1]['API']
    elapsed = z['ts']-a['ts']
    monotonic_elapsed = samples[-1]['census']['monotonic_s']-samples[0]['census']['monotonic_s']
    require(elapsed > 500 and abs(elapsed-monotonic_elapsed) < 2, 'Original elapsed interval inconsistent')
    metric_delta = {key: z[key]-a[key] for key in ['frame_count', 'learner_frame_count', 'training_steps', 'optimized_samples']}
    ea, ez = a['host_pipeline']['learning_exposure'], z['host_pipeline']['learning_exposure']
    optimizer_delta = {key: ez['optimizer']['total'][key]-ea['optimizer']['total'][key]
        for key in ['attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable']}
    replay_delta = {key: ez['replay'][key]-ea['replay'][key] for key in ['accepted_total', 'accepted_learner_total']}
    source_delta = {key: ez['replay']['accepted_by_source_total'][key]-value
        for key, value in ea['replay']['accepted_by_source_total'].items()}
    require(all(value >= 0 for group in [optimizer_delta, replay_delta, source_delta] for value in group.values())
        and optimizer_delta['outcomes_recorded'] == sum(optimizer_delta[k] for k in ['applied', 'amp_skipped', 'unavailable'])
        and sum(source_delta.values()) == replay_delta['accepted_total']
        and source_delta['dqn']+source_delta['epsilon'] == replay_delta['accepted_learner_total'],
        'Original exposure delta accounting differs')
    for entry in artifacts:
        reader.read_pin(entry, as_json=False)
    require('torch' not in sys.modules, 'Descriptive derivation imported numerical runtime')
    report = dict(schema='robotron-certified-R1-fixed-prefix-main-exposure-v1',
        status='DESCRIPTIVE_CURRENT_MAIN_RATES_ONLY_NOT_CONTROLLED_GAIN', source=h.pin(__file__),
        selection=selection_pin, artifacts=artifacts, sample_count=120, API_interval_s=elapsed,
        census_monotonic_interval_s=monotonic_elapsed, pipeline_elapsed_interval_s=z['host_pipeline']['elapsed_s']-a['host_pipeline']['elapsed_s'],
        main_trainer=main['owner'], zero_in_interval_main_birth_changes=True, learning_exposure_epoch=epochs[0],
        metric_deltas=metric_delta, metric_rates_per_s={k:v/elapsed for k,v in metric_delta.items()},
        optimizer_outcome_deltas=optimizer_delta, optimizer_outcome_rates_per_s={k:v/elapsed for k,v in optimizer_delta.items()},
        accepted_replay_deltas=replay_delta, accepted_replay_rates_per_s={k:v/elapsed for k,v in replay_delta.items()},
        accepted_replay_source_deltas=source_delta,
        logical_draws_per_accepted_learner_insert=metric_delta['optimized_samples']/replay_delta['accepted_learner_total'],
        maximum_pipeline_snapshot_age_s=max(ages), endpoint_pipeline_snapshot_age_s=[ages[0], ages[-1]],
        optimizer_unfinished_range=[min(pending),max(pending)], learning_speed_gain_verified=False,
        quality_gain_verified=False, production_changed=False, new_benchmark_or_probe=False,
        limitations=['One time-selected interval during live R1; not a controlled comparison.',
            'Cached exposure and top-level counters are not atomic; rates use API elapsed time with cache ages retained.',
            'Applied counts optimizer calls admitted by instrumentation, not proof every parameter moved.',
            'Logical sample draws, accepted learner inserts, all replay inserts and raw frames have different denominators.',
            'No quality, convergence, replay coverage or GPU service-time improvement is established.'], created_unix_s=time.time())
    pin = h.put(output, report)
    print(json.dumps(dict(report=pin, metric_rates_per_s=report['metric_rates_per_s'],
        optimizer_outcome_rates_per_s=report['optimizer_outcome_rates_per_s'],
        replay_rates_per_s=report['accepted_replay_rates_per_s'], logical_draws_per_learner_insert=report['logical_draws_per_accepted_learner_insert'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--derive', action='store_true')
    parser.add_argument('--selection')
    parser.add_argument('--selection-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.derive:
        print('PLAN_ONLY')
        return
    h = load('_R1_exposure_helpers', B/'run_full_policy_startup_v3.py')
    require(h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'Helper changed')
    require(h.pin(__file__)['sha256'] == args.source_sha256, 'Exact derivation source differs')
    path = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    require(h.pin(path)['sha256'] == 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', 'Reader changed')
    reader = load('_R1_exposure_immutable_reader', path)
    pin = h.pin(args.selection)
    require(pin['sha256'] == args.selection_sha256, 'Fixed interval selection differs')
    derive(pin, h, reader)


if __name__ == '__main__':
    main()
