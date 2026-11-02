"""Independent raw review of the one closed finite engineering integration.

Reuse original full-game ROM/START, raw start-order/quota, terminal/ROM/life
and sparse-wire kernels. Reconcile per-slot STOP only against the original two
selected full games and actual Lua bytes. The source01 runtime did not archive
whole slot permit bodies: retain that gap, never synthesize them or claim a
body-hash replay. This is not a scientific candidate evaluation or promotion.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
PAIR_SHA='4ae55c88bb1263fc5d974a6ca499eb446cf26dc13f2ab40ebc64b81651c5d4a6'
CASE=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101')


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def validate_bound_context(config,prepared,job,pair,family,h):
    require(job['engineering_only']is True and job['quality_leg']==config['role']=='E1'
        and pair['engineering_only']is True and job['quality_pair_precommit']['sha256']==PAIR_SHA
        and pair['checkpoint']==job['checkpoint']and pair['clocks']==job['expected_policy_clocks']
        and pair['selected_games']==64 and pair['slots']==list(range(4096,4128))
        and prepared['native']==job['runtime']and prepared['pair']==job['quality_pair_precommit']
        and family['schema']=='robotron-owned-overlap-ENGINEERING-source-family-v1'
        and family['pair']==job['quality_pair_precommit']and family['native']==job['runtime']
        and family['leg_reviewer']==h.pin(__file__)
        and family['current_Main_health']==job['current_v6_health_source']
        and family['current_Main_owned_overlap']==job['owned_TRAIN_overlap_source']
        and family['wire_auditor']==config['wire_auditor']and family['games_auditor']==config['original_games'],
        'Exact engineering policy/native/owned-observer/reviewer family required')
    cpu=json.loads(h.checked(job['stationary_CPU_report']).read_text())
    close=json.loads(h.checked(job['stationary_CPU_closeout']).read_text())
    require(cpu['status']=='PASS_CPU_IDLE_ENGINEERING_ONLY_POLICY'and cpu['joint_action']==80
        and cpu['checkpoint']==job['checkpoint']and cpu['clocks']==job['expected_policy_clocks']
        and close['status']=='PASS_CPU_IDLE_ENGINEERING_ONLY_POLICY_AND_OWNED_CLOSEOUT',
        'Original CPU-verified stationary engineering policy required')
    return pair



def review(config,h,reader):
    inputs={}
    def read(pin,as_json=True):
        value=reader.read_pin(pin,as_json=as_json);inputs[pin['path']]=pin;return value
    prepared=read(config['native_prepared']);jp=prepared['job'];job=read(jp)
    root=Path(jp['path']).parent;out=Path(job['output']);result_pin=h.pin(out/'result.json');result=read(result_pin)
    pair=read(job['quality_pair_precommit']);family=read(job['source_family_manifest'])
    selected=validate_bound_context(config,prepared,job,pair,family,h)
    terminal=read(config['original_native_closeout'])
    require(terminal['status']=='PASS_ORIGINAL_FULLGAME_LEG_NATIVE_SCOPE_CLOSED'
        and terminal['actual_exit']==0 and terminal['original_job']==jp
        and terminal['original_Popen_reaped']is True and terminal['all_original_controller_resources_closed']is True
        and result['complete']is True and result['errors']==[]and result.get('engineering_only')is True
        and result['original_attempt']==1 and result['no_retry']is True
        and result['original_job']==jp and result['all_original_threads_stopped']is result['original_lease_released']is True,
        'Original scientific scope did not close normally')
    archive=load('_eng_review_original_archive',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    owner=read(h.pin(root/'execution-original01/root-original-identity.json'))
    close=read(h.pin(root/'execution-original01/root-original-result-and-owned-release.json'))
    fields=archive.archived_closure(close,owner,read,exit_zero=True)
    controller_config=read(prepared['controller_config'])
    require(' '.join(controller_config['argv'])+' ; ignore_errors=no ;'in fields['ExecStart']
        and terminal['original_controller_config']==prepared['controller_config'],
        'Actual original command differs from the fixed native/job/source pins')
    expected=dict(CPUQuotaPerSecUSec='12s',MemoryMax=str(24<<30),MemorySwapMax='0',RuntimeMaxUSec='10min',
        TasksMax='512',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual finite engineering resource bounds differ')
    runtime=load('_eng_review_native_definitions',h.checked(prepared['native']))
    wire_pin=config['wire_auditor'];read(wire_pin,False)
    wire=load('_eng_review_slot_wire',h.checked(wire_pin));wire.dependencies()
    games=load('_eng_review_original_quota_games',h.checked(config['original_games']))
    original_reviewer=load('_eng_review_original_log_functions',h.checked(config['original_reviewer']))
    payloads={name:read(pin,False)for name,pin in result['journal'].items()}
    require(set(payloads)=={'games.jsonl','lives.jsonl','measurement_starts.jsonl'},'Complete original journals required')
    starts=games.indexed(games.lines(payloads['measurement_starts.jsonl']),'start')
    game_rows=games.indexed(games.lines(payloads['games.jsonl']),'game')
    window=read(h.pin(out/'original-fixed-admission.json'));policy=result['policy_before']
    require(policy==result['policy_after']and policy['checkpoint_sha256']==job['checkpoint']['sha256'],
        'Actual frozen engineering policy changed')
    cohort=result['before_intentional_stop']
    require(games.canonical(cohort['rows'])==games.canonical(result['after_intentional_stop']['rows'])
        and cohort['count']==cohort['started']==64 and cohort['complete']is cohort['valid']is True,
        'All64 selected natural games must remain complete across cleanup')
    internal=dict(result,_admission=window);prefixes={};actor_logs=[]
    for slot in range(4096,4128):
        entry=result['original_slots'][str(slot)];private=out/'actors'/str(slot)
        actor=read(h.pin(private/'original-actor.json'))
        require(type(entry['actual_exit'])is int and entry['actual_exit']==0 and birth(entry['pid'])!=entry['birth']
            and actor['pid']==entry['pid']and actor['starttime_ticks']==entry['birth']and actor['original_job']==jp
            and actor['argv']==runtime.actor_command(job,private)
            and entry['outputs_sealed_after_original_writer_closure']is True and entry['original_unsealed_output_paths']==[],
            'Original MAME command, normal0, absence or sealed-output binding differs')
        for name,pin in entry['files'].items():
            require(pin['path']==str(private/name),'Original private output escaped');h.checked(pin)
        wire.validate_original_file_identity(entry['trace_identity'],entry['files']['producer.jsonl'])
        wire.validate_original_file_identity(entry['lifecycle_identity'],entry['files']['lifecycle.jsonl'])
        prefixes[slot]=wire.audit_slot_prefix(slot,entry,job,internal,starts,game_rows,read,h.pin,expected_job_sha256=jp['sha256'])
        restore=read(entry['boot_restore']);require(restore['seed']==job['boot_seed']and restore['identity']==job['boot_seed']['identity'],
            'Original initialized seed provenance changed')
        actor_logs.append(original_reviewer.audit_actor_logs(read(entry['files']['actor-stdout.txt'],False).decode(),
            read(entry['files']['actor-stderr.txt'],False).decode(),slot,entry['pid'],job['proxy_ports'][str(slot)]))
        print(json.dumps(dict(phase='original_engineering_prefix_pass',slot=slot,count=len(prefixes))),flush=True)
    for key in ('pid','nonce','client_id','journal_game_id','certificate_identifier'):
        require(len({r[key]for r in prefixes.values()})==32,'Original prefix identities repeated')
    original_games=games.review(payloads,cohort,policy,window,prefixes)
    permit=read(h.pin(out/'original-complete-cohort-drain-permit.json'))
    require(permit['identifier']==result['drain_identifier']and {k:v for k,v in permit.items()if k!='identifier'}==result['drain_payload']
        and permit['cohort_sha256']==original_games['cohort_fingerprint']
        and set(permit['started_ids'])==set(original_games['admitted_ids'])
        and permit['issued_unix_ns']>=max(int(r['end_unix_s']*1e9)for r in cohort['rows']),
        'Original global64 certificate differs from independently audited natural completions')
    tails=[];receipts=[]
    archived_permits={r['slot']:r['full_slot_permit']for r in result['slot_retirement_closeout']['slots']}
    require(set(archived_permits)==set(range(4096,4128)),'All32 actual archived permit bodies required')
    for slot in range(4096,4128):
        entry=result['original_slots'][str(slot)];subject=dict(slot=slot,session=job['sessions'][str(slot)],connection=job['connections'][str(slot)])
        lifecycle=games.lines(read(entry['files']['lifecycle.jsonl'],False))
        require(lifecycle==entry['lifecycle'],'Saved lifecycle differs from raw bytes')
        selected=[r for r in cohort['rows']if r['client_slot']==slot]
        tails.append(wire.audit_applied_tail(wire.wire_rows(read(entry['files']['proxy.jsonl'],False)),lifecycle,
            entry,subject,permit,original_games['cohort_fingerprint'],policy,window,selected_rows=selected,slot_permit_record=archived_permits[slot]))
        receipts.append(entry['host_stop_receipt'])
    require(len({r['permit_identifier']for r in receipts})==32,'Distinct actual slot STOP permits required')
    partition=result['slot_retirement_closeout']
    require(partition['complete']is True and partition['selected_games']==64 and partition['slot_retirements']==32
        and partition['global_used_slots_intentionally_empty']is True
        and partition['global_certificate_identifier']==permit['identifier']
        and {r['slot']:r['STOP_receipt']for r in partition['slots']}=={r['slot']:r for r in receipts},
        'Native separate slot/global completion partition differs')
    source=load('_eng_review_actual_v6_health',h.checked(job['current_v6_health_source']))
    owned=load('_eng_review_owned_TRAIN_overlap',h.checked(job['owned_TRAIN_overlap_source']))
    expected_fleet=job['current_fleet'];membership=read(expected_fleet['original_membership']);roles=read(expected_fleet['rolemap'])['slot_eval']
    original_supervisor=load('_eng_review_original_v6_cleanup',h.checked(expected_fleet['supervisor']['source']))
    support=load('_eng_review_original_bounded_Main',h.checked(job['screen_support']))
    main_report=read(result['main_health_report']);require(main_report['samples']==result['main_samples'],'Original Main streams differ')
    accepted=0;pending=0;previous=None;previous_begin=None;max_gap=0;bindings={};binding_cache={};pending_begin=None
    for sample in result['main_samples']:
        raw=read(sample['physical_v6']);before=raw['fleet_before'];connections=raw['connections_before']
        now=max(before['updated_unix_s'],connections['observed_unix_s'])
        require(raw['schema']=='robotron-current-v6-owned-overlap-observation-v2','Exact owned-overlap raw schema required')
        before_metadata=owned.replay_pending(before,connections,expected_fleet,membership,roles,
            raw['owned_TRAIN_metadata_before'],now=now,strict_validator=source.validate_metadata,read_pin=read)
        after_metadata=owned.replay_pending(raw['fleet_after'],raw['connections_after'],expected_fleet,membership,roles,
            raw['owned_TRAIN_metadata_after'],now=max(raw['fleet_after']['updated_unix_s'],raw['connections_after']['observed_unix_s']),
            strict_validator=source.validate_metadata,read_pin=read)
        before_pending=before_metadata['pending_slots'];after_pending=after_metadata['pending_slots']
        changed=source.stable_projection(before,connections)!=source.stable_projection(raw['fleet_after'],raw['connections_after'])
        is_pending=bool(before_pending or after_pending or changed)
        require(sample['phase']['overlap_pending']is is_pending and raw['accepted']is(not is_pending)
            and raw['projection_changed']is changed and raw['supervisor_before']==raw['supervisor_after']
            and raw['completed_monotonic_s']-raw['started_monotonic_s']<=10,
            'Original bounded physical/overlap observation differs')
        require(raw['physical_failure']is None or is_pending,'Unexplained physical failure was accepted')
        if is_pending:
            if pending_begin is None:pending_begin=raw['started_monotonic_s']
            require(raw['completed_monotonic_s']-pending_begin<=10,'Original reconnect overlap exceeded10s')
        else:pending_begin=None
        if previous_begin is not None:
            gap=raw['started_monotonic_s']-previous_begin;require(0<gap<=15,'Original physical observation gap exceeds contract');max_gap=max(max_gap,gap)
        previous_begin=raw['started_monotonic_s']
        if not is_pending:
            joined=source.validate_join(before,connections,expected_fleet,membership,roles,
                {int(k):v for k,v in raw['physical'].items()},{int(k):v for k,v in raw['bindings'].items()},
                {int(k):v for k,v in raw['closures'].items()},now=now,closed_connection_predicate=original_supervisor.closed_connection)
            require(joined==raw['joined']==sample['current_v6_join'],'Original physical result differs')
            for key,event in raw['bindings'].items():
                owned.validate_binding_cleanup(before,int(key),event,read_pin=read,
                    closed_connection=original_supervisor.closed_connection)
            accepted+=1
        else:pending+=1
        for key,event in raw['bindings'].items():
            pin=before['slots'][key]['current_physical_binding'];bindings[pin['path']]=pin
            cached=binding_cache.get(pin['path'])
            if cached is None:
                value=read(pin);binding_cache[pin['path']]=(pin,value)
            else:
                require(cached[0]==pin,'An immutable binding path changed identity')
                value=cached[1]
            require(value==event,'Actual captured binding differs from immutable event')
        api=read(sample['API']);pipe=api['host_pipeline'];exposure=pipe['learning_exposure']
        require(api['pipeline_read_error']==api['bank_persistence_read_error']==''and api['training_enabled']is True
            and api['measurement_active']is False and math.isfinite(api['loss'])
            and pipe['available']is True and 0<=api['pipeline_snapshot_age_s']<=10
            and not pipe['inference']['errors']and pipe['inference_graphs']['ready']is True
            and not pipe['inference_graphs'].get('fatal_error')and 0<=sample['observed_unix_s']-api['ts']<=10,
            'Original Main API unavailable, stale or nonfinite')
        support.validate_optimizer(exposure['optimizer'],job['current_main']['owner']['pid'])
        for kind in ('optimizer','replay'):
            require({k:exposure[kind][k]for k in ('process_id','instance_monotonic_ns','epoch','epoch_reason')}==job['current_main']['exposure'][kind],
                'Original Main optimizer/replay exposure lineage changed')
        clocks={k:api[k]for k in ('frame_count','learner_frame_count','training_steps','optimized_samples')}
        require(clocks==sample['clocks']and(previous is None or all(clocks[k]>=previous[k]for k in clocks)),
            'Original logical Main clocks regressed');previous=clocks
    require(accepted>=2 and result['main_samples'][-1]['phase']['overlap_pending']is False
        and result['main_observer_lifecycle']==dict(original_observer_thread_closed=True,no_child_scope_created=True),
        'Original Main final accepted sample or closed observer missing')
    for pin in bindings.values():h.checked(pin)
    require(result['compile_report']['all_shapes_verified']==list(range(1,17))
        and policy['numeric_policy']['compiled']is True,'Actual common float32 compiled backend not ready')
    loaded=read(h.pin(out/'original-loaded-policy.json'))
    unused_expert_proof=bool(policy['epsilon']==policy['expert_ratio']==0
        and policy['training_enabled']is False and loaded['replay_enabled']is False
        and loaded['memory_is_none']is loaded['optimizer_is_none']is True)
    require(unused_expert_proof,'Frozen greedy no-replay/no-optimizer allowance not proven')
    evaluator_logs=original_reviewer.audit_evaluator_logs(
        read(h.pin(root/'execution-original01/stdout.txt'),False).decode(),
        read(h.pin(root/'execution-original01/stderr.txt'),False).decode(),policy,unused_expert_proof,
        expected_closed_client_ids={p['client_id']for p in prefixes.values()})
    for pin in job['inputs']:h.checked(pin)
    h.checked(result['acquired_checkpoint'])
    require('torch'not in sys.modules,'Independent raw reviewer imported numerical runtime')
    early=[r for r in receipts if r['authorized_monotonic_ns']<permit['issued_monotonic_ns']]
    return dict(status='PASS_ENGINEERING_RAW64_PREFIX32_FULLPERMIT_STOP32_OWNED_MAIN',observed_unix_s=time.time(),
        native_job=jp,native_result=result_pin,original_native_closeout=config['original_native_closeout'],
        original_prefixes=list(prefixes.values()),original_games=original_games,actual_slot_STOP_tails=tails,
        actor_logs=actor_logs,evaluator_logs=evaluator_logs,early_slot_retirements_before_global_completion=len(early),
        longest_park_before_global_completion_lower_bound_s=max((permit['issued_monotonic_ns']-r['authorized_monotonic_ns'])/1e9 for r in early)if early else 0,
        bounded_Main=dict(samples=len(result['main_samples']),accepted_physical=accepted,unaccepted_overlap=pending,
            maximum_gap_s=max_gap,distinct_actual_bindings=len(bindings)),
        all_original_selected64_natural_games_and_lives_verified=True,all32_original_ROM_START_clock_input_and_actual_STOP_Lua_EOF_verified=True,
        engineering_only=True,scores_are_not_learning_quality=True,valid=True,full_game_score_verified=True,role=job['quality_leg'],pair=job['quality_pair_precommit'],
        policy_sha256=job['checkpoint']['sha256'],cohort=cohort,cohort_selection=policy['cohort_selection'],
        numeric_policy=policy['numeric_policy'],compile_report=result['compile_report'],
        original_native_owner=owner,slot_permit_body_hash_replay_performed=True,
        raw_postprefix_frames_reconstructed=False,candidate_promotion_qualified=False,promotion=False,inputs=list(inputs.values()))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--job-sha256');args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    require(hashlib.sha256(args.job.read_bytes()).hexdigest()==args.job_sha256,'Exact review job required')
    config=json.loads(args.job.read_text())
    h=load('_eng_raw_review_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    reader=load('_eng_raw_review_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    h.checked(config['runtime'])
    try:report=review(config,h,reader)
    except Exception:report=dict(status='FAIL_INDEPENDENT_OWNED_OVERLAP_ENGINEERING_REVIEW',error=traceback.format_exc(),promotion=False)
    report['original_review_job']=h.pin(args.job);report['review_runtime']=config['runtime']
    pin=h.put(Path(config['report']),report);print(json.dumps(dict(status=report['status'],report=pin,error=report.get('error'))),flush=True)
    return 0 if report['status'].startswith('PASS_')else 1


if __name__=='__main__':raise SystemExit(main())
