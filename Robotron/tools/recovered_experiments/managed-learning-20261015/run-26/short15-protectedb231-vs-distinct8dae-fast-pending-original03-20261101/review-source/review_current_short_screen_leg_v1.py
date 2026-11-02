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
C=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/short15-protectedb231-vs-distinct8dae-fast-pending-original03-20261101')
SELECTED={
    'helpers':(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'),
    'reader':(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'),
    'archive':(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'),
}
COMPONENT_SHA={
    'prefix_auditor':'e0217fffc18039b65a5168f266600bcff999df3c0e10a65e4a73ffa53bdda5a3',
    'score_auditor':'77a75536f688bf2bb563bf9c686d0379f0e4152ef14ef1edf057c58a949a0d5e',
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


OWNED_MAIN_AUDITOR={'bytes': 1607,
 'identity': {'bytes': 1607,
              'ctime_ns': 1793578903950206554,
              'device': 2304,
              'inode': 85601235,
              'mode': '0o444',
              'mtime_ns': 1793578903950206554,
              'nlink': 1,
              'uid': 1001},
 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/short15-protectedb231-vs-distinct8dae-fast-pending-original03-20261101/selected-source/owned_main_with_pending_cadence_v1.py',
 'sha256': '306b2e66409a1618b9c17d30e4e16adecbcd77153765bbe463dbd149346143e8'}

def audit_main(job,result,read,h):
    auditor=load('_current_selected_owned_Main_auditor',Path(OWNED_MAIN_AUDITOR['path']),OWNED_MAIN_AUDITOR['sha256'])
    h.checked(OWNED_MAIN_AUDITOR)
    return auditor.audit_main(job,result,read,h)


def review(leg,h,reader,archive):
    inventory={}
    def read(pin,as_json=True):
        value=reader.read_pin(pin,as_json=as_json);inventory[pin['path']]=pin;return value
    prepared_pin=h.pin(C/'prepared-with-review.json');prepared=read(prepared_pin)
    require(prepared['selection']['sha256']=='daa9e8cd912296c760873c6a8b45aa1696491f21a1312f2ceb95dc809482aee9',
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
    main=audit_main(job,result,read,h)
    require(result['compile_report']['all_shapes_verified']==list(range(1,17))
        and result['policy_before']['numeric_policy']['compiled'] is True,'Actual common compiled inference required')
    checkpoint_pin=prepared['horizon_checkpoint_auditor'];read(checkpoint_pin,False)
    checkpoints=load('_current_selected_checkpoint_auditor',Path(checkpoint_pin['path']),checkpoint_pin['sha256'])
    require(set(result['predeclared_horizon_checkpoints'])=={str(v)for v in job['checkpoint_offsets_ns']},
        'All predeclared intermediate horizons required')
    checkpoint_reviews={key:checkpoints.audit_checkpoint(job,read(pin),seal,score,prefixes,result,games,modules['score_auditor'])
        for key,pin in result['predeclared_horizon_checkpoints'].items()}
    for pin in job['inputs']:h.checked(pin)
    h.checked(result['acquired_checkpoint'])
    require('torch'not in sys.modules,'Read-only review imported a numerical runtime')
    return dict(status='PASS_ORIGINAL_SELECTED_PREFIX_SCORE_AND_BOUNDED_MAIN_REPLAY',leg=leg,
        observed_unix_s=time.time(),prepared=prepared_pin,original_job=job_pin,original_native_result=result_pin,
        original_archived_closure=closure_pin,original_actual_exit=closure['original_exit'],
        original_selected_auditors={k:job['components'][k]for k in COMPONENT_SHA},
        original_Main_observer_source=job['screen_support'],prefixes=prefixes,score=score,main=main,intermediate_checkpoint_reviews=checkpoint_reviews,
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
