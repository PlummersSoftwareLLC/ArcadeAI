"""Read-only replay of the originally selected post-reboot screen validators.

The native result and original service must already have closed normally.
This qualifies only this protocol's startup prefixes, cutoff score witnesses
and bounded Main owner/API observations. It cannot reconstruct raw tail frames,
prove historical physical fleet health, promote a policy or close tool50607.
All failures are preserved. No corrected future scientific validator is used.
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
C=G/'logs/managed-learning-20261015/run-26/post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
SELECTED={
    'helpers':(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'),
    'reader':(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'),
    'archive':(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'),
}
COMPONENT_SHA={
    'prefix_auditor':'e0217fffc18039b65a5168f266600bcff999df3c0e10a65e4a73ffa53bdda5a3',
    'score_auditor':'947f82b448abd66cf2118ae31c5ac980a8e61d174e9f201be2c4200b0bf19e33',
}
SUPPORT_SHA='2ccd2fbcdec7f1ca31000c5d696bf3b30ecf48c21a96b25ba01db7a6fc90787f'


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path,sha):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Selected review dependency changed')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    require(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Review dependency changed during import')
    return module


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def audit_main(job,result,read,support):
    report=read(result['main_health_report']);samples=result['main_samples']
    require(report['status']=='CURRENT_MAIN_OWNER_AND_API_OBSERVED'
        and report['samples']==samples and len(samples)>=2
        and report['original192_physical_health_or_historical_schema_qualification_claimed']is False,
        'Original bounded Main stream differs')
    require(result['main_observer_lifecycle']==dict(original_observer_thread_closed=True,no_child_scope_created=True)
        and result['main_health_failure']is None,'Original Main observer did not close normally')
    initial=read(result['initial_main_readiness'])
    require(initial==samples[0],'Original initial Main readiness sample differs')
    expected=job['current_main'];previous=None;previous_time=None;max_gap=0;pending=0
    first=None;last=None;role_sets=set()
    for index,sample in enumerate(samples):
        require(sample['owner']==expected['owner'] and sample['phase']==dict(overlap_pending=False),
            'Original recorded Main owner or phase changed')
        api=read(sample['API']);stamp=sample['observed_unix_s']
        require(type(stamp)in(int,float)and math.isfinite(stamp)
            and type(api['ts'])in(int,float)and math.isfinite(api['ts'])and 0<=stamp-api['ts']<=10,
            'Recorded original Main API stale')
        require(api['pipeline_read_error']==api['bank_persistence_read_error']==''
            and api['host_pipeline']['available']is True and 0<=api['pipeline_snapshot_age_s']<=10
            and not api['host_pipeline']['inference']['errors']
            and api['host_pipeline']['inference_graphs']['ready']is True
            and not api['host_pipeline']['inference_graphs'].get('fatal_error')
            and api['training_enabled']is True and api['measurement_active']is False,
            'Recorded Main pipeline unavailable or learning stopped')
        require(type(api['loss'])in(int,float)and math.isfinite(api['loss']),
            'Recorded Main loss is not finite')
        exposure=api['host_pipeline']['learning_exposure']
        actual_pending=support.validate_optimizer(exposure['optimizer'],expected['owner']['pid'])
        require(actual_pending==sample['pending_optimizer_attempts'],'Original pending optimizer accounting differs')
        pending+=actual_pending
        for kind in ('optimizer','replay'):
            require({k:exposure[kind][k]for k in ('process_id','instance_monotonic_ns','epoch','epoch_reason')}==expected['exposure'][kind],
                'Original Main optimizer/replay exposure lineage changed')
        clocks={k:api[k]for k in ('frame_count','learner_frame_count','training_steps','optimized_samples')}
        require(clocks==sample['clocks']and all(type(v)is int and v>=0 for v in clocks.values())
            and(previous is None or all(clocks[k]>=previous[k]for k in clocks)),
            'Original Main clocks regressed or differ from source API')
        roles=dict(TRAIN=0,EVAL=0)
        require(type(api['client_rows'])is list and all(type(row['eval'])is bool for row in api['client_rows']),
            'Original Main role row types differ')
        for row in api['client_rows']:roles['EVAL'if row['eval']else'TRAIN']+=1
        require(roles==sample['observed_TRAIN_EVAL_counts']and api['client_count']==sample['clients']
            and sample['expected_original_roles']==dict(TRAIN=155,EVAL_once=37)
            and sample['EVAL_retirement_or_TRAIN_fault_not_inferred_from_count_alone']is True,
            'Original observed Main counts differ')
        role_sets.add((roles['TRAIN'],roles['EVAL']))
        if previous_time is not None:
            require(stamp>previous_time,'Original Main observations reordered')
            max_gap=max(max_gap,stamp-previous_time)
        if first is None:first=dict(clocks)
        last=dict(clocks);previous=clocks;previous_time=stamp
    require(all(last[k]>first[k]for k in first),'Main did not advance every logical learning clock')
    return dict(status='PASS_ORIGINAL_BOUNDED_MAIN_STREAM_REPLAY',samples=len(samples),
        first_clocks=first,last_clocks=last,clock_deltas={k:last[k]-first[k]for k in first},
        observed_maximum_sample_gap_s=max_gap,observations_with_pending_optimizer_attempt=pending,
        observed_role_count_pairs=sorted(role_sets),
        scope='Recorded API plus source-bound observer owner checks; historical192 physical census is not claimed.',
        original_process_exposure_lineage_preserved=True,all_API_files_individually_rehashed=True)


def review(leg,h,reader,archive):
    inventory={}
    def read(pin,as_json=True):
        value=reader.read_pin(pin,as_json=as_json);inventory[pin['path']]=pin;return value
    prepared_pin=h.pin(C/'prepared.json');prepared=read(prepared_pin)
    require(prepared['selection']['sha256']=='fa61b63cc2f8b9c12e5298507d66c42ec8d64129bd1d66732ba355dc725d495d',
        'Exact original post-reboot selection required')
    selected=read(prepared['selection']);configs=read(prepared['controller_configs'])
    require(prepared['ordered_legs']==configs['ordered_legs']==['R1','C1']and leg in prepared['ordered_legs'],
        'Only original selected two-arm study accepted')
    job_pin=prepared['jobs'][leg]['job'];job=read(job_pin)
    require(job['leg']==leg and job['attempt']==1 and job['no_retry']is True
        and job['screen_selection']==prepared['selection']and job['current_main']==selected['current_main'],
        'Original single-attempt job selection differs')
    config=read(configs['configs'][leg]);out=Path(config['output'])
    owner=read(h.pin(out/'root-original-identity.json'));closure_pin=h.pin(out/'root-original-result-and-owned-release.json')
    closure=read(closure_pin);fields=archive.archived_closure(closure,owner,read,exit_zero=True)
    require(birth(owner['pid'])!=owner['starttime_ticks'],'Original native is still running')
    require(config['argv']==prepared['jobs'][leg]['argv'] and fields['Restart']=='no','Original invocation changed')
    result_pin=h.pin(Path(job['output'])/'result.json');result=read(result_pin)
    require(result['original_job']==job_pin and result['leg']==leg and result['attempt']==1 and result['no_retry']is True
        and result['complete']is True and result['errors']==[]
        and result['all_original_threads_stopped']is result['original_lease_released']is True
        and result['original_post_origin_child_reap']['all_original_children_reaped']is True
        and result['immutable_inputs_unchanged']is True
        and result['current_main']==job['current_main'],'Original native did not close normally')
    modules={}
    for key,sha in COMPONENT_SHA.items():
        pin=job['components'][key];require(pin['sha256']==sha,'Corrected or different scientific auditor cannot be substituted')
        read(pin,False);modules[key]=load('_original_post_reboot_'+key,Path(pin['path']),sha)
    require(job['screen_support']['sha256']==SUPPORT_SHA,'Original Main observer source changed')
    read(job['screen_support'],False);support=load('_original_post_reboot_support',Path(job['screen_support']['path']),SUPPORT_SHA)
    prefix=modules['prefix_auditor'];prefix.dependencies()
    starts=prefix.games_audit.indexed(prefix.games_audit.lines(read(result['journal']['measurement_starts.jsonl'],False)),'start')
    games=prefix.games_audit.indexed(prefix.games_audit.lines(read(result['journal']['games.jsonl'],False)),'game')
    seal=read(result['deadline_score_seal']);anchor_pin=h.pin(Path(job['output'])/'original-deadline-anchor.json')
    anchor=read(anchor_pin);cleanup=read(result['intentional_cleanup'])
    augmented=dict(result,_admission=anchor['fixed_admission']);prefixes=[]
    require(set(result['original_slots'])=={str(k)for k in range(4096,4128)},'Exactly32 original slots required')
    for slot in range(4096,4128):
        entry=result['original_slots'][str(slot)]
        require(entry['outputs_sealed_after_original_writer_closure']is True and entry['original_unsealed_output_paths']==[],
            'Original slot outputs are not sealed')
        for pin in entry['files'].values():read(pin,False)
        prefix.validate_original_file_identity(entry['trace_identity'],entry['files']['producer.jsonl'])
        prefix.validate_original_file_identity(entry['lifecycle_identity'],entry['files']['lifecycle.jsonl'])
        proof=prefix.audit_first_start_prefix(slot,entry,job,augmented,starts,games,read,h.pin,expected_job_sha256=job_pin['sha256'])
        prefixes.append(proof)
        print(json.dumps(dict(phase='original_prefix_pass',leg=leg,slot=slot,count=len(prefixes))),flush=True)
    score=modules['score_auditor'].audit(job,result,seal,anchor,cleanup,prefixes,starts,games)
    main=audit_main(job,result,read,support)
    for pin in job['inputs']:h.checked(pin)
    h.checked(result['acquired_checkpoint'])
    require('torch'not in sys.modules,'Read-only review imported a numerical runtime')
    return dict(status='PASS_ORIGINAL_SELECTED_PREFIX_SCORE_AND_BOUNDED_MAIN_REPLAY',leg=leg,
        observed_unix_s=time.time(),prepared=prepared_pin,original_job=job_pin,original_native_result=result_pin,
        original_archived_closure=closure_pin,original_actual_exit=closure['original_exit'],
        original_selected_auditors={k:job['components'][k]for k in COMPONENT_SHA},
        original_Main_observer_source=job['screen_support'],prefixes=prefixes,score=score,main=main,
        score_seal=result['deadline_score_seal'],anchor=anchor_pin,inputs=list(inventory.values()),
        raw_postprefix_frames_reconstructed=False,original_tool50607_closure_qualified=False,
        historical_physical192_health_qualified=False,full_game_quality_qualified=False,
        paired_comparison_qualified=False,scientific_run_retried_or_rescued=False,promotion=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--leg',choices=['R1','C1'])
    parser.add_argument('--source-sha256');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    require(args.leg is not None and args.output is not None,'Leg and new output path required')
    source=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    require(source==args.source_sha256,'Exact frozen review orchestration source required')
    modules={k:load('_selected_review_'+k,*v)for k,v in SELECTED.items()}
    try:report=review(args.leg,modules['helpers'],modules['reader'],modules['archive'])
    except Exception:
        report=dict(status='FAIL_ORIGINAL_SELECTED_LEG_REVIEW',leg=args.leg,traceback=traceback.format_exc(),
            observed_unix_s=time.time(),scientific_retry_or_corrected_auditor_substitution=False,promotion=False)
    report['review_orchestration_source']=modules['helpers'].pin(Path(__file__))
    pin=modules['helpers'].put(args.output,report)
    print(json.dumps(dict(status=report['status'],report=pin)),flush=True)
    return 0 if report['status'].startswith('PASS_')else 1


if __name__=='__main__':raise SystemExit(main())
