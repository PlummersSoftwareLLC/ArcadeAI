"""Unselected physical/recipe health companion; transport completion remains separate.

The original healthy body changes ONLY its raw-count predicate to192/193. Never
rewrite an API count. Original physical identities are stricter than supervised
recovery: all192 exact births remain mandatory. Import performs no I/O.
"""
import ast
import hashlib
import math

WINDOW_SHA='ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a'
SUPERVISION_SHA='1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'


def require(value,message):
    if not value:raise ValueError(message)


def verify_sources(original_window,original_supervision,companion_source):
    require(hashlib.sha256(original_window).hexdigest()==WINDOW_SHA and
            hashlib.sha256(original_supervision).hexdigest()==SUPERVISION_SHA,
            'Exact original nontransport sources required')
    def function(raw):
        tree=ast.parse(raw)
        return next(node for node in tree.body if isinstance(node,ast.FunctionDef)and node.name=='healthy')
    original=function(original_window);expected=ast.parse(ast.unparse(original).replace(
        "api['client_count'] == 192", "api['client_count'] in (192, 193)")).body[0]
    require(ast.dump(expected,include_attributes=False)==ast.dump(function(companion_source),include_attributes=False),
            'Original healthy body changed beyond its explicit raw-count predicate')
    return dict(original_recipe_pipeline_bank_API_freshness_body_preserved=True,
                only_raw_count_predicate_changed=True,counts_never_normalized=True,
                transport_completion_still_required=True)


def healthy(api, baseline, experiment, now):
    require(api['client_count'] in (192,193) and api['training_enabled'] is True and api['measurement_active'] is False
            and api['managed_experiment']==experiment and api['lr']==6.25e-6, 'Held main192 recipe changed')
    require(api['pipeline_read_error']==api['bank_persistence_read_error']=='', 'Pipeline/bank read error')
    age=now-api['ts'];pipeline_age=api['pipeline_snapshot_age_s']
    require(type(age) in (int,float) and math.isfinite(age) and 0<=age<=5
            and type(pipeline_age) in (int,float) and math.isfinite(pipeline_age) and 0<=pipeline_age<=5,
            'Stale, future or nonfinite API/pipeline sample')
    pipe=api['host_pipeline']
    require(pipe['schema']=='robotron-host-pipeline-v1' and pipe['available'] is True
            and type(pipe['generation']) is int and pipe['generation']==baseline['host_pipeline']['generation'],
            'Pipeline unavailable or generation changed')
    for kind in ('inference','actor_refresh','target_refresh','learner_priority'):
        require(type(pipe[kind]['errors']) is int and pipe[kind]['errors']==0, 'Pipeline error: '+kind)
    require(type(api['bank_persistence']['write_failures']) is int
            and api['bank_persistence']['write_failures']==0, 'Bank persistence failed')


def physical(sup,policy,snapshot,previous=None):
    sup.validate_policy(policy)
    require(snapshot['schema']=='robotron-main-supervision-snapshot-v1','Original full census required')
    now,unix=snapshot['monotonic_s'],snapshot['unix_s']
    start_mono,start_unix=snapshot['collection_started_monotonic_s'],snapshot['collection_started_unix_s']
    require(all(sup.finite(value)and value>0 for value in (now,unix,start_mono,start_unix))
        and 0<=now-start_mono<=sup.LIMITS['max_collection_s']
        and 0<=unix-start_unix<=sup.LIMITS['max_collection_s'],'Slow/nonfinite original physical census')
    require(set(snapshot['owners'])=={'trainer','fleet'},'Both original main owners required')
    for role in ('trainer','fleet'):
        sup.validate_owner(policy[role],snapshot['owners'][role])
        require(all(snapshot['owners'][role]['process'][key]==policy['baseline_owners'][role]['process'][key]
            for key in sup.STATIC),'Original owner process configuration changed')
    actors=snapshot['actors'];probes=snapshot['previous_birth_probes']
    require(set(actors)==set(probes)==sup.SLOTS and len({actor['pid']for actor in actors.values()})==192,
            'All192 exact physical actors and probes required; no missing/extra actors')
    for slot,actor in actors.items():
        original=policy['baseline_actors'][slot]
        sup.validate_actor(slot,actor,original,policy['fleet'])
        require(sup.birth(actor)==sup.birth(original)and probes[slot]==original['starttime_ticks'],
                'Original192 actor birth changed or contradicted its probe')
    if previous is not None:
        require(0<now-previous['monotonic_s']<=sup.LIMITS['max_sample_gap_s']
            and 0<unix-previous['unix_s']<=sup.LIMITS['max_sample_gap_s'],
            'Original physical census gap/regression')
    return dict(all192_exact_original_births_and_full_static_identities=True,
                both_original_owners_verified=True,supervised_replacements_permitted=False)


def autosave(metadata,now):
    require(type(metadata['mtime_ns'])is int and metadata['bytes']>0 and
        type(now)in(int,float)and math.isfinite(now)and
        0<=now-metadata['mtime_ns']/1e9<=360,'Main normal autosave stale/future/empty')


def sample(p,API,baseline,experiment,now,previous_API=None):
    p.rows(API)  # Full192 slots; raw count192/193 only. No standalone transport acceptance.
    healthy(API,baseline,experiment,now)
    if previous_API is not None:
        for key in ('learner_frame_count','training_steps','optimized_samples'):
            require(type(API[key])is int and API[key]>=previous_API[key], 'Main learner clock regressed')
    return dict(nontransport_recipe_pipeline_bank_checks_pass=True,transport_acceptance=False)
