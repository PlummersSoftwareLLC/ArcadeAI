"""Seal a paused RAM bank save intent; final shutdown must fulfill it.

Dirty RAM banks are allowed explicitly. This never declares them persisted.
The caller must stop all input producers, preserve the owner/source and verify
the final synchronous save's revisions, metadata, geometry and success log.
"""
import math


def require(value,message):
    if not value:
        raise ValueError(message)


def integer(value):
    return type(value) is int and value >= 0


def validate(before,after,banks,*,expected_pid,now):
    require(set(banks) == {'hof','ephof'} and type(expected_pid) is int and expected_pid > 0,
            'Both original banks and process required')
    for api in (before,after):
        require(type(api.get('ts')) in (int,float) and math.isfinite(api['ts'])
                and 0 <= now-api['ts'] <= 5 and type(api.get('pipeline_snapshot_age_s')) in (int,float)
                and math.isfinite(api['pipeline_snapshot_age_s']) and 0 <= api['pipeline_snapshot_age_s'] <= 5
                and api.get('pipeline_read_error') == api.get('bank_persistence_read_error') == '',
                'Fresh original pipeline/bank view required')
        managed = api['managed_measurement']
        require(api['training_enabled'] is False and api['measurement_active'] is True
                and managed['active'] is True and managed['phase'] in ('warming','collecting','draining')
                and integer(managed['generation']) and managed['generation'] > 0,'Supported pause required')
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
        for name in banks:
            revision,saved = stats['revision'][name],stats['saved_revision'][name]
            require(integer(revision) and integer(saved) and saved <= revision
                    and type(stats['dirty'][name]) is bool and stats['dirty'][name] is (saved != revision)
                    and saved == banks[name]['selector']['mutation_generation'],
                    'RAM revision, saved revision and prior disk selector disagree: '+name)
    require(before['ts'] <= after['ts'],'API time regressed')
    require(all(before['managed_measurement'][key] == after['managed_measurement'][key]
                for key in ('generation','label')),'Owned supported pause changed')
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
    return dict(status='PAUSED_RAM_BANK_SAVE_INTENT_AND_PRIOR_DISK_GEOMETRY_VERIFIED',expected_pid=expected_pid,
        target_revisions=dict(after['bank_persistence']['revision']),banks=banks,
        dirty_at_seal=dict(after['bank_persistence']['dirty']),final_synchronous_save_required=True,
        all_target_revisions_already_persisted=not any(after['bank_persistence']['dirty'].values()),
        actual_state_payload_values_verified=False,production_handoff_ready=False)
