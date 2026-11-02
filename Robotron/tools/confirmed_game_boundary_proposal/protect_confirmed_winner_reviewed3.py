"""Review the bound campaign and protect a copy only after every original gate.

Default invocation is plan-only. --execute reviews closed artifacts; --publish
additionally creates new immutable files. No learner, control, service, existing
policy or managed-incumbent pointer is changed by this tool.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

CFG = JOB_PIN = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pin(path):
    path=Path(path)
    before=path.stat()
    hashed=digest(path)
    after=path.stat()
    identity=lambda s:dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,
        mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),
        uid=s.st_uid,nlink=s.st_nlink)
    require(identity(before)==identity(after), 'File changed while hashing')
    return dict(path=str(path),sha256=hashed,bytes=after.st_size,identity=identity(after))


def read_pin(entry, *, as_json=True):
    path=Path(entry['path'])
    require(path.is_absolute() and path==path.resolve(strict=True), 'Exact owned artifact path required')
    observed=pin(path)
    full={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}
    controller={'device','inode','mode','uid','nlink'}
    require(set(entry)=={'path','sha256','bytes','identity'}
            and set(entry['identity']) in (full,controller)
            and all(observed[key]==entry[key] for key in ('path','sha256','bytes'))
            and all(observed['identity'][key]==value for key,value in entry['identity'].items())
            and entry['identity']['mode']=='0o444'
            and entry['identity']['uid']==os.getuid() and entry['identity']['nlink']==1,
            'Immutable artifact identity differs (full snapshot or exact controller ABI required)')
    raw=path.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==entry['sha256'], 'Artifact changed during read')
    return json.loads(raw) if as_json else raw


def checked_module(name, entry):
    read_pin(entry, as_json=False)
    require(name not in sys.modules, 'Fresh checked protection dependency required')
    spec=importlib.util.spec_from_file_location(name, entry['path'])
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    require(pin(entry['path'])==entry, 'Dependency changed while importing')
    return module


def validate_closed_owner(closure, owner):
    require(type(closure.get('original_exit')) is int and closure['original_exit']==0
            and closure.get('lifecycle_complete') is True and closure.get('original')==owner,
            'Original service must exit0 and complete owned closure')
    released=closure.get('owned_release',[])
    require(len(released)==2 and {x.get('unit') for x in released}=={owner['unit'],owner['timer']}
            and all(x.get('confirmed_absent') is True for x in released), 'Original owned units not released')


def validate_review_join(review, leg, plan_sha256):
    count=leg['summary']['count']
    ids=set(leg['included_game_ids'])
    require(review.get('schema')=='robotron-confirmed-original-terminal-leg-v1'
            and review.get('valid') is True and review.get('leg')==leg['index']
            and review.get('role')==leg['role'] and review.get('plan_sha256')==plan_sha256
            and review.get('receipt_sha256')==leg['receipt_sha256'], 'Original audit/leg binding differs')
    require(type(count) is int and count>=50 and len(ids)==count
            and review.get('statistics',{}).get('count')==count
            and len(review.get('original_game_ids',[]))==count
            and len(review.get('admission_ids',[]))==count
            and set(review.get('original_game_ids',[]))==ids
            and set(review.get('admission_ids',[]))==ids, 'Audit does not cover every admitted full game')
    for name in ('original_terminal_readback','rom_game_over_evidence'):
        proof=review.get(name,{})
        require(proof.get('status')=='PASS' and type(proof.get('verified_games')) is int
                and proof['verified_games']==count
                and len(proof.get('links',[]))==count
                and {x['journal_game_id'] for x in proof.get('links',[])}==ids,
                'Independent terminal/ROM proof is incomplete')


def original_terminal_archive(closure, owner, evidence):
    validate_closed_owner(closure, owner)
    archives=closure.get('native_archives',closure.get('full_original_archives',[]))
    matching=[x for x in archives if x.get('argv')==['systemctl','--user','show',owner['unit']]]
    require(len(matching)==1 and matching[0].get('exit')==0, 'Original terminal service-show archive missing')
    record=matching[0]
    raw=read_pin(record['stdout'],as_json=False)
    evidence[record['stdout']['path']]=record['stdout']['sha256']
    fields=dict(line.split('=',1) for line in raw.decode().splitlines() if '=' in line)
    expected=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],MainPID='0',
        ExecMainPID=str(owner['pid']),ExecMainCode='1',ExecMainStatus='0',NRestarts='0',Result='success')
    require(all(fields.get(k)==v for k,v in expected.items()), 'Original native terminal identity/outcome differs')


def failed_terminal_archive(closure, owner, evidence, expected_exit, *, retained_tombstone=False):
    require(type(expected_exit) is int and expected_exit in (1,2), 'Only the two preserved original failures are allowed')
    require(type(closure.get('original_exit')) is int and closure['original_exit']==expected_exit
            and closure.get('original')==owner, 'Recorded failed original owner/exit differs')
    if retained_tombstone:
        require(expected_exit==1 and closure.get('failed_tombstone_retained') is True
                and closure.get('unit_released') is False,
                'Previous observer failure must remain honestly retained')
    else:
        require(closure.get('lifecycle_complete') is True and closure.get('unit_released') is True,
                'Original failed reference audit closure incomplete')
        released=closure.get('owned_release',[])
        require(len(released)==2 and {x.get('unit') for x in released}=={owner['unit'],owner['timer']}
                and all(x.get('confirmed_absent') is True for x in released), 'Failed audit owned release missing')
    archives=closure.get('native_archives',closure.get('full_original_archives',[]))
    records=[entry for entry in archives if entry.get('argv')==['systemctl','--user','show',owner['unit']]]
    require(len(records)==1 and records[0].get('exit')==0, 'Original failed service-show archive missing')
    entry=records[0]['stdout']; raw=read_pin(entry,as_json=False)
    evidence[entry['path']]=entry['sha256']
    fields=dict(line.split('=',1) for line in raw.decode().splitlines() if '=' in line)
    expected=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],MainPID='0',
        ExecMainPID=str(owner['pid']),ExecMainCode='1',ExecMainStatus=str(expected_exit),NRestarts='0',Result='exit-code')
    require(all(fields.get(key)==value for key,value in expected.items()), 'Archived failed original runtime identity differs')


def validate_reference_join(supplement, failed_review, leg, plan_sha256, failed_review_sha256):
    require(leg['index']==1 and leg['role']=='reference' and leg['summary']['count']==202,
            'Only this original202-game reference disposition is allowed')
    require(supplement.get('schema')=='robotron-original-audit-optional-warning-supplement-v1'
        and supplement.get('status')=='ORIGINAL_NEEDS_REVIEW_RESOLVED_EXACT_UNUSED_EXPERT_WARNING'
        and supplement.get('leg')==1 and supplement.get('role')=='reference'
        and supplement.get('plan_sha256')==plan_sha256
        and supplement.get('supplemental_valid_completed_leg') is True
        and supplement.get('original_audit_valid') is False
        and type(supplement.get('original_audit_exit')) is int and supplement['original_audit_exit']==2
        and type(supplement.get('original_evaluator_exit')) is int and supplement['original_evaluator_exit']==0
        and supplement.get('original_failed_review_sha256')==failed_review_sha256
        and supplement.get('original_auditor_source_sha256')==
            'a405fe2e7c4462a8ddac884d40b89f45d3d9ba47136286e497e85770593d35c0'
        and all(supplement.get(key) is False for key in
            ('cohort_rerun','original_auditor_rerun','original_receipts_changed','scientific_gates_changed')),
        'Exact original reference supplemental disposition differs')
    warning="[WARN] Robotron expert unavailable (No module named 'v3'); expert guidance disabled."
    expected_error='ValueError: Unclassified evaluator log issues require review: '+repr([dict(line_number=2,text=warning)])
    require(failed_review.get('valid') is False and failed_review.get('leg')==1
        and failed_review.get('schema')=='robotron-confirmed-original-terminal-leg-v1'
        and failed_review.get('error')==expected_error
        and supplement.get('classified_warning')==dict(line_number=2,text=warning,
            reason='Frozen greedy controls exclude the only expert action branch; actual handler differential passed.'),
        'Only the exact proven-unused optional expert warning is in scope')
    ids=set(leg['included_game_ids']); require(len(ids)==202,'Original reference game count differs')
    require(len(supplement.get('original_game_ids',[]))==202
        and set(supplement['original_game_ids'])==ids
        and supplement.get('statistics',{}).get('count')==202
        and all(supplement['statistics'][key]==leg['summary'][key] for key in ('mean','median')),
        'Reference supplement differs from original assessed rows')
    for name in ('original_terminal_readback','rom_game_over_evidence'):
        proof=supplement.get(name,{})
        require(proof==failed_review.get(name) and proof.get('status')=='PASS'
            and type(proof.get('verified_games')) is int and proof['verified_games']==202
            and len(proof.get('links',[]))==202
            and {row['journal_game_id'] for row in proof['links']}==ids,
            'Original successful reference proof prefix does not cover every game')


def verify_audit_artifacts(cached, audit_directory, directory, index, final_status, auditor, evidence):
    for original, entry in cached['artifacts'].items():
        name=Path(entry['copy']); require(name.name==str(name), 'Unsafe audit archive component')
        archive=audit_directory/name
        require(digest(archive)==entry['sha256'], 'Independent original audit archive changed')
        evidence[str(archive)]=entry['sha256']
        if Path(original)==Path(directory)/'status.json':
            observed=auditor.decode(archive.read_bytes())
            require([row for row in observed['legs'] if row['index']==index]
                ==[final_status['legs'][index-1]], 'Original finished leg record changed')
        else:
            require(digest(original)==entry['sha256'], 'Original audited artifact changed')
            evidence[original]=entry['sha256']


def exact_candidate_gates(receipts):
    require(len(receipts)==4,'All four original full cohorts required')
    scores=[]
    for receipt in receipts:
        rows=receipt.get('rows',receipt.get('cohort',{}).get('rows',[]))
        require(len(rows)>=50 and all(type(row.get('score')) is int and row['score']>=0 for row in rows),
                'Exact original integer scores and established floor required')
        scores.append([row['score'] for row in rows])
    reference=scores[0]+scores[2]
    def median_twice(values):
        values=sorted(values);middle=len(values)//2
        return values[middle]*2 if len(values)%2 else values[middle-1]+values[middle]
    checks=[]
    for index in (2,4):
        candidate=scores[index-1]
        left=20*sum(candidate)*len(reference);right=21*sum(reference)*len(candidate)
        median_pass=median_twice(candidate)>=median_twice(reference)
        require(left>=right and median_pass, 'Each candidate must independently pass exact5%-mean/preserved-median gates')
        checks.append(dict(index=index,count=len(candidate),mean_gate_integer_left=left,
            mean_gate_integer_right=right,mean_pass=True,median_pass=True))
    return checks


def review(directory):
    require(CFG is not None and Path(directory).resolve()==Path(CFG['campaign_directory']),
            'Explicit exact root protection job required')
    evidence={JOB_PIN['path']:JOB_PIN['sha256']}
    def read(entry):
        result=read_pin(entry);evidence[entry['path']]=entry['sha256'];return result
    package=read(CFG['source_package']);root=Path(package['root'])
    for relative,expected in package['files'].items():
        path=root/relative
        require(path.resolve(strict=True).is_relative_to(root) and digest(path)==expected,
                'Selected private evaluation package changed')
    auditor=checked_module('_confirmed_winner_auditor_'+str(time_nonce()),CFG['auditor_source'])
    evidence[CFG['auditor_source']['path']]=CFG['auditor_source']['sha256']
    watcher=checked_module('_confirmed_winner_watcher_'+str(time_nonce()),CFG['watcher_source'])
    evidence[CFG['watcher_source']['path']]=CFG['watcher_source']['sha256']
    read(CFG['binding_job'])
    args=argparse.Namespace(binding_job=Path(CFG['binding_job']['path']),
        binding_job_sha256=CFG['binding_job']['sha256'],campaign=Path(directory),plan_sha256=CFG['plan_sha256'])
    auditor.configure(args)
    for entry in (auditor.OPTIONAL_EXPERT_PROOF,auditor.OPTIONAL_EXPERT_CLOSURE):read(entry)
    plan=auditor.decode((Path(directory)/'plan.json').read_bytes())
    auditor.validate_future_plan(plan,args,Path(directory))
    require(digest(Path(directory)/'plan.json')==CFG['plan_sha256'],'Exact original native plan required')
    native_owner=read(CFG['native_owner']);observer_owner=read(CFG['observer_owner'])
    native_closure=read(pin(CFG['native_closure_path']));observer_closure=read(pin(CFG['observer_closure_path']))
    original_terminal_archive(native_closure,native_owner,evidence)
    original_terminal_archive(observer_closure,observer_owner,evidence)
    previous_owner=read(CFG['previous_observer_owner']);previous=read(CFG['previous_observer_archive'])
    failed_terminal_archive(previous,previous_owner,evidence,1,retained_tombstone=True)
    reference_control=read(CFG['original_reference_audit_control'])
    reference_owner=read(CFG['original_reference_audit_owner'])
    failed_terminal_archive(reference_control,reference_owner,evidence,2)
    original_failed=read(CFG['original_reference_failed_review'])
    supplement=read(CFG['reference_supplement'])
    supplement_closure=read(CFG['reference_supplement_closure']);supplement_owner=read(CFG['reference_supplement_owner'])
    original_terminal_archive(supplement_closure,supplement_owner,evidence)
    intent=read(CFG['pre_outcome_review_intent']);intent_status=read(CFG['pre_outcome_candidate_status'])
    require(intent['C1_completed_count_at_intent']==0 and intent_status['count']==0
        and supplement['pre_outcome_review_intent_sha256']==CFG['pre_outcome_review_intent']['sha256'],
        'Exact warning review must have been selected before first candidate outcome')
    require(supplement['actual_handler_proof_sha256']==auditor.OPTIONAL_EXPERT_PROOF['sha256']
        and supplement['actual_handler_original_closure_sha256']==auditor.OPTIONAL_EXPERT_CLOSURE['sha256'],
        'Reference supplement used another actual-handler proof')
    watcher.validate_reference_supplement(supplement,CFG['plan_sha256'])
    watcher_job=read(CFG['watcher_job'])
    require(watcher_job['owner']==native_owner and watcher_job['previous_observer']==previous_owner
        and watcher_job['reference_supplement']==CFG['reference_supplement']
        and watcher_job['reference_supplement_closure']==CFG['reference_supplement_closure']
        and set(watcher_job['configs'])=={'2','3','4'},'Current observer/reference handoff bindings differ')
    observer_result=read(pin(Path(watcher_job['output'])/'result.json'))
    require(observer_result.get('status')=='FOUR_ORIGINAL_COHORT_REVIEWS_COMPLETE_WITH_REFERENCE_SUPPLEMENT'
        and observer_result.get('original_owner')==native_owner
        and observer_result.get('original_reference_audit_exit')==2
        and observer_result.get('reference_supplement_included') is True
        and observer_result.get('original_reference_rerun') is False
        and len(observer_result.get('audits',[]))==4,'Current four-cohort review chain incomplete')
    sys.path.insert(0,str(root/'tools'))
    generic=checked_module('_confirmed_winner_generic_'+str(time_nonce()),pin(root/'tools/protect_quality_winner.py'))
    require(Path(generic.campaign.__file__).resolve()==root/'tools/run_quality_campaign.py',
            'Wrong loaded complete-game campaign implementation')
    base=generic.review(directory);evidence.update(base['evidence_sha256'])
    require(base['assessment']['outcome']=='qualified_improvement'
        and base['assessment']['qualified_improvement'] is True,
        'Both independently valid candidate cohorts must qualify')
    require([row['index'] for row in base['assessment']['candidate_checks']]==[2,4]
        and all(row['mean_pass'] is True and row['median_pass'] is True
                for row in base['assessment']['candidate_checks']),'Separate candidate gates required')
    terminals=sys.modules.get('confirmed_terminal_evidence')
    require(terminals is not None and Path(terminals.__file__).resolve()==root/'tools/confirmed_terminal_evidence.py',
            'Selected original-terminal implementation was not loaded')
    final_status=auditor.decode((Path(directory)/'status.json').read_bytes())
    require(len(final_status['legs'])==4 and all(type(row['returncode']) is int and row['returncode']==0
        for row in final_status['legs']),'All original evaluators must exit integer zero')
    joins=[];receipts=[]
    for index,completed_pin in enumerate(observer_result['audits'],1):
        completed=read(completed_pin);require(completed['index']==index,'Ordered review indices differ')
        assessed=base['assessment']['legs'][index-1]
        if index==1:
            require(completed.get('supplemental_review')==CFG['reference_supplement']
                and completed.get('original_audit_exit')==2 and completed.get('original_evaluator_exit')==0
                and completed.get('original_auditor_rerun') is False and completed.get('cohort_rerun') is False,
                'Original reference disposition was not adopted without a rerun')
            validate_reference_join(supplement,original_failed,assessed,CFG['plan_sha256'],
                                    CFG['original_reference_failed_review']['sha256'])
            require(supplement['original_finished_record']==final_status['legs'][0],
                    'Original reference record changed after supplemental review')
            require(original_failed['artifacts'][plan['legs'][0]['receipt_path']]['sha256']==assessed['receipt_sha256'],
                    'Original failed audit read another reference receipt')
            cached=supplement;archive_review=original_failed
            archive_directory=Path(CFG['original_reference_failed_review']['path']).parent
            control_entry=CFG['reference_supplement_closure'];review_entry=CFG['reference_supplement']
        else:
            require(completed.get('original_attempt')==1 and type(completed.get('controller_exit')) is int
                and completed['controller_exit']==0,'One successful original audit per remaining leg required')
            control=read(completed['controller_receipt'])
            require(type(control.get('original_exit')) is int and control['original_exit']==0
                and control['lifecycle_complete'] is True and control['unit_released'] is True,
                'Original remaining-leg audit did not cleanly succeed')
            cached=read(completed['audit_receipt']);validate_review_join(cached,assessed,CFG['plan_sha256'])
            archive_review=cached;archive_directory=Path(completed['audit_receipt']['path']).parent
            control_entry=completed['controller_receipt'];review_entry=completed['audit_receipt']
        spec=plan['legs'][index-1];receipt=auditor.decode(Path(spec['receipt_path']).read_bytes());receipts.append(receipt)
        rows=receipt.get('rows',receipt.get('cohort',{}).get('rows',[]))
        if index==1:
            require(sum(row['score'] for row in rows)==supplement['statistics']['score_sum'],
                    'Reference supplemental score sum differs from original rows')
        payloads={name:(Path(spec['job']['directory'])/'journal'/name).read_bytes()
                  for name in ('games.jsonl','measurement_starts.jsonl')}
        links=terminals.verify_original_journal_bytes(receipt,payloads)
        rom=[auditor.validate_rom_terminal(row,receipt['terminal_successors'][row['journal_game_id']]) for row in rows]
        require(links==cached['original_terminal_readback']['links'] and rom==cached['rom_game_over_evidence']['links'],
                'Cached terminal/ROM proof differs from original-byte recomputation')
        verify_audit_artifacts(archive_review,archive_directory,directory,index,final_status,auditor,evidence)
        joins.append(dict(index=index,review=review_entry,controller=control_entry,
            original_reference_audit_exit=2 if index==1 else None,verified_games=len(links),ROM_verified_games=len(rom)))
    exact=exact_candidate_gates(receipts)
    require(all(digest(path)==expected for path,expected in evidence.items()),'Closed evidence changed during review')
    require(not any(name=='torch' or name.startswith('torch.') for name in sys.modules),'Protection imported numerical runtime')
    base.update(schema='robotron-confirmed-terminal-protected-winner-reference-supplement-v1',
        evidence_sha256=evidence,root_protection_job=JOB_PIN,source_package=CFG['source_package'],
        original_native_closure=pin(CFG['native_closure_path']),original_observer_closure=pin(CFG['observer_closure_path']),
        previous_observer_failure=CFG['previous_observer_archive'],original_reference_audit_failure=CFG['original_reference_failed_review'],
        reference_warning_supplement=CFG['reference_supplement'],independent_terminal_and_ROM_reviews=joins,
        exact_individual_candidate_gates=exact,CPU_and_window_binding=CFG['binding_job'],original_authorities_verified=True)
    return base


def time_nonce():
    # Private import names differ during the mandatory second review in publish.
    import time
    return time.time_ns()


def configure(args):
    global CFG,JOB_PIN
    require(digest(__file__)==args.source_sha256, 'Protection source SHA differs')
    JOB_PIN=pin(args.job)
    require(JOB_PIN['sha256']==args.job_sha256, 'Exact root protection job required')
    CFG=read_pin(JOB_PIN)
    require(CFG['schema']=='robotron-confirmed-terminal-protection-reference-supplement-job-v1', 'Wrong protection job schema')


def _fsync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(directory, destination, label):
    """Create new immutable files without replacing any prior protected policy."""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", label) is None:
        raise ValueError("Label must be a simple filename component")
    audited = review(directory)
    if not audited["assessment"]["qualified_improvement"]:
        raise ValueError("Both candidate cohorts must qualify independently before publication")
    destination = Path(destination).resolve(strict=True)
    final = destination / f"{label}.pt"
    metadata = final.with_suffix(".pt.json")
    if final.exists() or metadata.exists():
        raise FileExistsError("Protected checkpoint or metadata already exists; never overwrite")
    entry = audited["checkpoints"]["candidate"]
    partials = []
    try:
        fd, name = tempfile.mkstemp(prefix=f".{label}.", suffix=".partial", dir=destination)
        partials.append(Path(name))
        with os.fdopen(fd, "wb") as output, Path(entry["snapshot"]).open("rb") as source:
            shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        if digest(name) != entry["sha256"]:
            raise ValueError("Protected copy does not match the precommitted candidate")
        # Revalidate all receipts and source identities after copying, before publishing.
        after = review(directory)
        if (after["evidence_sha256"] != audited["evidence_sha256"]
                or after["checkpoints"] != audited["checkpoints"]):
            raise ValueError("Campaign evidence changed while copying the winner")
        audited.update(published_utc=datetime.now(timezone.utc).isoformat(),
            protected_checkpoint=str(final), checkpoint_sha256=entry["sha256"],
            managed_incumbent_updated=False, live_learner_restored=False)
        fd, meta_name = tempfile.mkstemp(prefix=f".{label}.", suffix=".partial", dir=destination)
        partials.append(Path(meta_name))
        with os.fdopen(fd, "w") as stream:
            json.dump(audited, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        for path in partials:
            path.chmod(0o444)
        # Hard links publish exclusively and atomically on the destination filesystem.
        # If metadata publication fails, retain the checkpoint as an unpromoted orphan.
        os.link(name, final)
        _fsync_directory(destination)
        os.link(meta_name, metadata)
        _fsync_directory(destination)
    finally:
        for path in partials:
            path.unlink(missing_ok=True)
    return audited




def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--job',type=Path)
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, review, copies or publication')
        return 0
    require(args.job and args.job_sha256 and args.source_sha256, 'Exact source/job bindings required')
    configure(args)
    result=publish(CFG['campaign_directory'],CFG['destination'],CFG['label']) if args.publish else review(CFG['campaign_directory'])
    print(json.dumps(dict(outcome=result['assessment']['outcome'],
        candidate_checks=result['assessment']['candidate_checks'],
        protected_checkpoint=result.get('protected_checkpoint'),managed_incumbent_updated=False),indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
