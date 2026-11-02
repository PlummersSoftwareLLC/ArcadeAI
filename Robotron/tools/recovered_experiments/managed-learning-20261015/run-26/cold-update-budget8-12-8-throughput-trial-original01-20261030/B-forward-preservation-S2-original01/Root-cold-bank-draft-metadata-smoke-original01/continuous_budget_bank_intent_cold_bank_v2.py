"""Seal a paused RAM bank save intent; final shutdown must fulfill it.

Dirty RAM banks are allowed explicitly. This never declares them persisted.
The caller must stop all input producers, preserve the owner/source and verify
the final synchronous save's revisions, metadata, geometry and success log.
"""
import math
import json


def require(value,message):
    if not value:
        raise ValueError(message)


def integer(value):
    return type(value) is int and value >= 0


def validate(before,after,banks,*,expected_pid,now,expected_cap,loaded_baseline,origin=None):
    require(set(banks) == {'hof','ephof'} and type(expected_pid) is int and expected_pid > 0,
            'Both original banks and process required')
    if origin is not None:
        require(origin['schema']=='robotron-source-bound-cold-bank-counter-origin-v1'
            and origin['owner']['pid']==expected_pid and integer(origin['loaded_local_revision'])and origin['loaded_local_revision']==1
            and integer(origin['loaded_adds_total'])and origin['loaded_adds_total']==0 and origin['counter_values_normalized_or_reset']is False
            and origin['loaded_bank_payload_and_episode_metadata_equal']is True
            and integer(origin['held_replay']['accepted_total'])and origin['held_replay']['accepted_total']==0
            and json.dumps(origin['banks'],sort_keys=True,allow_nan=False)==json.dumps(banks,sort_keys=True,allow_nan=False),
            'Explicit exact loaded disk/local-clock origin required')
    for api in (before,after):
        require(type(api.get('ts')) in (int,float) and math.isfinite(api['ts'])
                and 0 <= now-api['ts'] <= 5 and type(api.get('pipeline_snapshot_age_s')) in (int,float)
                and math.isfinite(api['pipeline_snapshot_age_s']) and 0 <= api['pipeline_snapshot_age_s'] <= 5
                and api.get('pipeline_read_error') == api.get('bank_persistence_read_error') == '',
                'Fresh original pipeline/bank view required')
        require(type(expected_cap) is int and expected_cap in (8,12), 'Selected current startup cap required')
        require(type(loaded_baseline) is dict and set(loaded_baseline) ==
                {'frame_count','measurement_frame_count','optimized_samples'}
                and all(type(v) is int and v >= 0 for v in loaded_baseline.values()),
                'Exact actual restored per-boot F/M/O baseline required')
        require(api['training_enabled'] is True and api['measurement_active'] is False
                and api['client_count'] == 0 and api['client_rows'] == []
                and api.get('managed_measurement',{}).get('active',False) is False,
                'Continuous zero-input current trainer required; no managed pause is claimed')
        frames = api['frame_count'] - loaded_baseline['frame_count'] - max(0,
            api['measurement_frames'] - loaded_baseline['measurement_frame_count'])
        samples = api['optimized_samples'] - loaded_baseline['optimized_samples']
        require(type(api['frame_count']) is type(api['measurement_frames']) is type(api['optimized_samples']) is int
                and frames >= 0 and samples >= expected_cap * max(1,frames),
                'Existing per-boot replay budget must be positively exhausted')
        pipe = api['host_pipeline']
        optimizer,replay = (pipe['learning_exposure'][name] for name in ('optimizer','replay'))
        require(pipe['available'] is True and optimizer['enabled'] is replay['enabled'] is True
                and optimizer['process_id'] == replay['process_id'] == expected_pid,'Original exposure owner differs')
        total = optimizer['total']
        require(all(integer(total.get(k)) for k in ('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable'))
                and total['attempts_started'] == total['outcomes_recorded'] == total['applied']+total['amp_skipped']
                and total['unavailable'] == optimizer['unclassified_started_total'] == 0
                and optimizer['available'] is True,'Optimizer/prefetch work remains')
        stats = api['bank_persistence']
        require(stats['writer_active'] is False and integer(stats['write_failures']) and stats['write_failures'] == 0
                and stats['last_error'] is None and stats['output']['active'] is None
                and all(integer(v['errors']) and v['errors'] == 0 for v in stats['output']['totals'].values()),
                'A bank writer/output is active or failed')
        if origin is not None:
            require(all(integer(stats[k])and stats[k]==0 for k in('capture_attempts','capture_deferrals','writes','write_failures')),
                'Inherited disk origin requires no intervening bank capture/write')
            require(all(replay[k]==origin['held_replay'][k]for k in('process_id','instance_monotonic_ns','epoch','epoch_reason'))
                and all(optimizer[k]==origin['held_optimizer'][k]for k in('process_id','instance_monotonic_ns','epoch','epoch_reason'))
                and integer(replay['accepted_total']),'Exact same B exposure origin required')
        for name in banks:
            revision,saved = stats['revision'][name],stats['saved_revision'][name]
            require(integer(revision) and integer(saved) and saved <= revision
                    and type(stats['dirty'][name]) is bool and stats['dirty'][name] is (saved != revision)
                    and (saved == banks[name]['selector']['mutation_generation']if origin is None else saved==1),
                    'RAM revision, saved revision and prior disk selector disagree: '+name)
    require(before['ts'] <= after['ts'],'API time regressed')
    for name in ('frame_count','learner_frame_count','measurement_frames','training_steps','optimized_samples'):
        require(integer(before[name]) and before[name] == after[name],'Paused clock moved: '+name)
    require(before['host_pipeline']['generation'] == after['host_pipeline']['generation'],'Pipeline generation changed')
    elapsed = [v['host_pipeline']['elapsed_s'] for v in (before,after)]
    require(all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in elapsed)
            and elapsed[1] > elapsed[0],'Distinct pipeline cache views required')
    for name in ('optimizer','replay'):
        left,right = (v['host_pipeline']['learning_exposure'][name] for v in (before,after))
        require(integer(left['epoch']) and left['epoch'] > 0 and left['epoch'] == right['epoch'],
                'Exposure restore/load epoch changed')
        keys = ('total',) if name == 'optimizer' else ('accepted_total','accepted_learner_total','accepted_by_source_total')
        require(all(left[key] == right[key] for key in keys),'Paused exposure moved: '+name)
    require(all(before['bank_persistence'][key] == after['bank_persistence'][key]
                for key in ('revision','saved_revision','dirty','writes','write_failures')),'Bank intent changed between views')
    return dict(status='CONTINUOUS_BUDGET_EXHAUSTED_RAM_BANK_INTENT_AND_PRIOR_DISK_GEOMETRY_VERIFIED',expected_pid=expected_pid,
        target_revisions=dict(after['bank_persistence']['revision']),banks=banks,
        dirty_at_seal=dict(after['bank_persistence']['dirty']),final_synchronous_save_required=True,
        all_target_revisions_already_persisted=origin is None and not any(after['bank_persistence']['dirty'].values()),
        actual_state_payload_values_verified=False,production_handoff_ready=False,
        cold_bank_origin=origin,process_adds_at_seal=after['host_pipeline']['learning_exposure']['replay']['accepted_total']if origin is not None else None,
        expected_current_cap=expected_cap,loaded_baseline=dict(loaded_baseline),
        no_managed_pause_or_prefetch_pause_claimed=True,
        read_only_prefetch_staging_may_remain=True)
