"""Describe an observed window; never infer a performance or quality gain."""
import argparse
import importlib.util
from pathlib import Path
import json

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
OUT=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def analyze():
    h=load('_window_description_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    immutable=load('_window_description_reader',ROOT/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    observation=h.pin(OUT/'original-five-minute-observation.json');report=immutable.read_pin(observation)
    assert report['status']=='VERIFIED_WAIT'and len(report['observations'])==31 and report['warnings']==[]
    before=immutable.read_pin(report['first_main_snapshot'])['snapshot']
    after=immutable.read_pin(report['last_main_snapshot'])['snapshot']
    seconds=after['monotonic_s']-before['monotonic_s'];assert 299<=seconds<=301
    a,b=before['api'],after['api'];pa,pb=a['host_pipeline'],b['host_pipeline']
    assert pa['generation']==pb['generation'] and pa['sample_every']==pb['sample_every']
    ea,eb=pa['learning_exposure'],pb['learning_exposure']
    for kind in ('optimizer','replay'):
        for key in ('process_id','instance_monotonic_ns','epoch','epoch_reason'):
            assert ea[kind][key]==eb[kind][key]
    def difference(first,last):
        value=last-first;assert value>=0;return value
    optimizer={key:difference(ea['optimizer']['total'][key],eb['optimizer']['total'][key])for key in ea['optimizer']['total']}
    replay={key:difference(ea['replay']['accepted_by_source_total'][key],eb['replay']['accepted_by_source_total'][key])for key in ea['replay']['accepted_by_source_total']}
    rows=difference(ea['replay']['accepted_total'],eb['replay']['accepted_total']);assert sum(replay.values())==rows
    clocks={key:difference(a[key],b[key])for key in ('learner_frame_count','training_steps','optimized_samples')}
    means={}
    for phase in ('inference','actor_refresh','target_refresh','learner_priority'):
        first,last=pa[phase],pb[phase];assert first['errors']==last['errors']==0
        means[phase]={}
        for key,value in first.items():
            if isinstance(value,dict)and set(('count','total'))<=set(value):
                count=difference(value['count'],last[key]['count'])
                total=difference(value['total'],last[key]['total'])
                means[phase][key]=dict(sampled_count=count,mean_host_elapsed_ms=total/count if count else None)
    native={key:difference(pa['native_batch_update'][key],pb['native_batch_update'][key])for key in ('success_count','fallback_count','error_count')}
    value=dict(schema='robotron-passive-training-window-description-v1',original_observation=observation,
        source=h.pin(Path(__file__).resolve()),first_raw_snapshot=report['first_main_snapshot'],last_raw_snapshot=report['last_main_snapshot'],
        observed_seconds=seconds,clocks_added=clocks,optimizer_outcomes_added=optimizer,replay_inserts_added=rows,
        replay_inserts_by_source=replay,descriptive_rates_per_s=dict(learner_frames=clocks['learner_frame_count']/seconds,
            admitted_optimizer_calls=optimizer['applied']/seconds,new_replay_inserts=rows/seconds),
        scheduled_optimizer_rows_per_new_replay_insert=clocks['optimized_samples']/rows,
        sampled_host_elapsed_means=means,native_priority_update_outcomes_added=native,
        main_round_before=before['status']['round'],main_round_after=after['status']['round'],
        main_counts_before=before['observed_counts'],main_counts_after=after['observed_counts'],
        scope='Observed live counters under the existing shared workload. Optimizer applied means admitted call; timings are sampled host elapsed and include waits. Nested times are not additive. No paired controlled throughput or learning-speed comparison.',
        next_performance_investigation='If repeated windows agree, investigate packed device readback and scheduling before further CPU sum-tree tuning; current data cannot identify GPU kernel time or prove a speedup.',
        causal_throughput_gain_established=False,useful_training_throughput_gain_established=False,
        learning_speed_gain_established=False,quality_gain_established=False,promotion=False)
    result=h.put(OUT/'observed-training-window-description.json',value)
    print(json.dumps(dict(result=result,seconds=seconds,rates=value['descriptive_rates_per_s'],priority_means=means['learner_priority'])),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--analyze',action='store_true');args=parser.parse_args()
    if args.analyze:analyze()
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
