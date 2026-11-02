"""Protect a new copy only from the one successful original closed32 review.

Default invocation is inert. --execute verifies retained evidence; --publish
also creates new immutable files. No scientific audit is rerun, no existing
policy is replaced, and no learner, incumbent pointer or service is changed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile
import time


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
READER = GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA = 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
REVIEWER_SHA = '60f4c9ab189a1fe0a8ae3a2c7e854991e07e2f7aede88301458ce5913b29800a'
RUNTIME = GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
RUNTIME_SHA = '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'
SLOTS = list(range(4096,4128))


def require(value,message):
    if not value:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def reader_module():
    require(digest(READER) == READER_SHA,'Exact immutable reader differs')
    spec=importlib.util.spec_from_file_location('_protect32_reader_'+str(time.time_ns()),READER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def validate_review_command(fields,owner,config,job):
    root_job=job['review_job'];source=job['reviewer_source']
    expected=['/usr/bin/python3.12','-I','-B',source['path'],'--execute','--job',root_job['path'],
        '--job-sha256',root_job['sha256'],'--source-sha256',REVIEWER_SHA]
    require(config['unit'] == owner['unit'] and config['argv'] == expected,
            'Original independent reviewer config differs')
    wrapper=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+expected
    match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart'])
    require(match is not None and shlex.split(match[1]) == wrapper,
            'Successful original service did not execute the selected independent review')


def validate_original_leg(reviewed,receipt,spec):
    require(reviewed['index'] == spec['index'] and reviewed['role'] == spec['role'],
            'Original independent leg identity differs')
    rows=receipt['rows'];ids={row['journal_game_id'] for row in rows}
    original=reviewed['cohort']['original_games']
    require(len(rows) >= 50 and len(ids) == len(rows)
            and type(original['statistics']['count']) is int and original['statistics']['count'] == len(rows)
            and set(original['original_game_ids']) == ids,
            'Original independent review omitted or changed a full game')
    for name in ('original_terminal_readback','rom_game_over_evidence'):
        proof=original[name]
        require(proof['status'] == 'PASS' and type(proof['verified_games']) is int and proof['verified_games'] == len(rows)
                and len(proof['links']) == len(rows)
                and {link['journal_game_id'] for link in proof['links']} == ids,
                'Every original terminal and ROM proof is required')
    require(all(type(link['previous_raw_reserves']) is int and link['previous_raw_reserves'] == 0 and link['inactive_player_observed'] is True
                and link['recent_restart_observed'] is True
                for link in original['rom_game_over_evidence']['links']),
            'Independent ROM exhausted-reserve/inactive-player/restart proof differs')
    require(set(reviewed['cohort']['actor_logs']['slots']) == set(map(str,SLOTS)),
            'All32 independently reviewed actor logs required')


def verify(job,job_pin,reader):
    """Read the original result and recompute score gates; never invoke its audit."""
    require(job['schema'] == 'robotron-quality32-winner-protection-job-v1','Exact protection job required')
    evidence={job_pin['path']:job_pin['sha256']}
    def read(entry,as_json=True):
        value=reader.read_pin(entry,as_json=as_json);evidence[entry['path']]=entry['sha256'];return value
    require(job['reviewer_source']['sha256'] == REVIEWER_SHA,'Exact tested closed reviewer required')
    reviewer=reader.checked_module('_protect32_review_'+str(time.time_ns()),job['reviewer_source'])
    evidence[job['reviewer_source']['path']]=REVIEWER_SHA
    require(digest(RUNTIME) == RUNTIME_SHA,'Exact original archive validator changed')
    runtime=reader.checked_module('_protect32_archives_'+str(time.time_ns()),reader.pin(RUNTIME))
    evidence[str(RUNTIME)]=RUNTIME_SHA
    report=read(job['review_report']);root_job=read(job['review_job']);owner=read(job['review_owner'])
    closure=read(job['review_closure']);config=read(job['review_controller_config'])
    require(report['schema'] == 'robotron-closed-quality32-independent-review-v1'
            and report['valid'] is True and report['status'] == 'VALID_CLOSED_FOUR_LEG_QUALITY32_REVIEW'
            and report['quality_qualified'] is True and report['promotion'] is False
            and report['learning_speed_gain_verified'] is False and report['actual_runtime_changed'] is False
            and report['root_job'] == job['review_job']
            and job['review_report']['path'] == str(Path(root_job['output'])/'review.json'),
            'One valid qualified original independent review required')
    fields=runtime.archived_closure(closure,owner,read,exit_zero=True)
    require(runtime.duration_seconds(fields['RuntimeMaxUSec']) == 180
            and fields['MemoryMax'] == str(4<<30)
            and runtime.duration_seconds(fields['CPUQuotaPerSecUSec']) == 2
            and fields['Restart'] == 'no' and fields['SendSIGKILL'] == 'no',
            'Original independent reviewer CPU resource/restart scope differs')
    validate_review_command(fields,owner,config,job)
    require(report['evidence_sha256'].get(job['reviewer_source']['path']) == REVIEWER_SHA,
            'Original report did not bind its actual reviewer source')
    context=read(report['closed_context'])
    require(report['closed_context']['path'] == root_job['closed_context_path']
            and context['binding'] == root_job['binding'], 'Original closed context/binding differs')
    binding=read(root_job['binding']);native_owner=read(context['native_owner'])
    native_closure=read(context['native_closure'])
    runtime.archived_closure(native_closure,native_owner,read,exit_zero=True)
    require(report['original_native_exit0_and_cleanup_verified'] is True
            and report['main_supervised_runtime_verified'] is True
            and report['main_supervision_summary']['full_capacity'] is True
            and type(report['main_supervision_summary']['recoveries']) is int
            and 0 <= report['main_supervision_summary']['recoveries'] <= 4
            and type(report['main_supervision_summary']['charged_recovery_s']) in (int,float)
            and type(report['main_supervision_summary']['charged_recovery_wall_s']) in (int,float)
            and 0 <= report['main_supervision_summary']['charged_recovery_s'] <= 120
            and 0 <= report['main_supervision_summary']['charged_recovery_wall_s'] <= 120
            and report['main192_continuous_holds_verified'] is (report['main_supervision_summary']['recoveries']==0)
            and report['full_original_tails_and_ROM_verified'] is True
            and report['acquisition']['candidate'] == binding['candidate']
            and report['acquisition']['reference'] == binding['reference'],
            'Original runtime, main holds, full tails or CPU acquisition differs')
    for path,expected in report['evidence_sha256'].items():
        require(Path(path).is_absolute() and digest(path) == expected,'Original reviewed evidence changed')
        evidence[path]=expected
    archive=Path(job['review_report']['path']).parent
    for original,entry in report['artifacts'].items():
        name=entry['copy']
        require(name not in ('','.','..') and Path(name).name == name,'Unsafe original review archive component')
        path=archive/name
        require(path.resolve(strict=True) == path and digest(path) == entry['sha256']
                and digest(original) == entry['sha256'],'Original independent archive changed')
        evidence[str(path)]=entry['sha256']
    directory=Path(binding['campaign']['output_directory'])
    plan=json.loads((directory/'plan.json').read_bytes())
    require(digest(directory/'plan.json') == binding['campaign']['plan_sha256'],
            'Original campaign plan differs')
    require(len(report['legs']) == 4,'All four original independent leg results required')
    legs=[]
    for spec,reviewed in zip(plan['legs'],report['legs']):
        raw=Path(spec['receipt_path']).read_bytes();receipt=json.loads(raw)
        require(hashlib.sha256(raw).hexdigest() == reviewed['receipt_sha256'],
                'Original reviewed receipt changed')
        validate_original_leg(reviewed,receipt,spec)
        legs.append(dict(index=spec['index'],role=spec['role'],rows=receipt['rows']))
    decision=reviewer.decision(legs)
    require(decision == report['decision'] and decision['qualified_improvement'] is True
            and decision['outcome'] == 'qualified_improvement'
            and [value['index'] for value in decision['individual_candidate_checks']] == [2,4]
            and all(value['mean_pass'] is True and value['median_pass'] is True
                for value in decision['individual_candidate_checks']),
            'Both original candidates must independently pass exact mean/median gates')
    source=reader.pin(plan['checkpoints']['candidate']['snapshot'])
    require(source['sha256'] == binding['candidate']['sha256'],'Original acquired candidate differs')
    read(source,False)
    require(all(digest(path) == expected for path,expected in evidence.items()),
            'Original protection evidence changed during verification')
    return dict(schema='robotron-quality32-protected-winner-v1',reviewed_utc=datetime.now(timezone.utc).isoformat(),
        root_protection_job=job_pin,campaign_directory=str(directory),plan_sha256=binding['campaign']['plan_sha256'],
        original_review_report=job['review_report'],original_review_owner=job['review_owner'],
        original_review_closure=job['review_closure'],original_root_review_job=job['review_job'],
        source_package=binding['evidence']['source_package'],acquisition=report['acquisition'],
        main_supervision_policy=binding['main_holds']['supervision_policy'],
        main_supervision_summary=report['main_supervision_summary'],
        assessment=decision,candidate_source=source,reference=binding['reference'],evidence_sha256=evidence,
        original_scientific_audit_rerun=False,managed_incumbent_updated=False,live_learner_restored=False,
        learning_speed_gain_verified=False,scope='Frozen-policy quality only; preserves both individual gates and all original evidence.')


def fsync_directory(path):
    fd=os.open(path,os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def publish(job,job_pin,reader):
    label=job['label'];destination=Path(job['destination'])
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',label) is not None,'Simple new label required')
    require(destination.is_absolute() and destination.resolve(strict=True) == destination
            and destination.is_dir() and destination.stat().st_uid == os.getuid(),
            'Exact owned destination directory required')
    final=destination/(label+'.pt');metadata=destination/(label+'.pt.json')
    require(not final.exists() and not metadata.exists(),'Never overwrite or retry an existing protected label')
    checked=verify(job,job_pin,reader);source=checked['candidate_source'];partials=[]
    try:
        fd,name=tempfile.mkstemp(prefix='.'+label+'.',suffix='.partial',dir=destination);partials.append(Path(name))
        with os.fdopen(fd,'wb') as output,Path(source['path']).open('rb') as stream:
            shutil.copyfileobj(stream,output);output.flush();os.fchmod(output.fileno(),0o444);os.fsync(output.fileno())
        require(digest(name) == source['sha256'],'Protected copy differs from original candidate')
        after=verify(job,job_pin,reader)
        require(after['evidence_sha256'] == checked['evidence_sha256']
                and after['candidate_source'] == source,'Original evidence changed while copying; no publication')
        checked.update(published_utc=datetime.now(timezone.utc).isoformat(),protected_checkpoint=str(final),
            checkpoint_sha256=source['sha256'],checkpoint_bytes=source['bytes'])
        fd,meta_name=tempfile.mkstemp(prefix='.'+label+'.',suffix='.partial',dir=destination);partials.append(Path(meta_name))
        with os.fdopen(fd,'w') as stream:
            json.dump(checked,stream,indent=2,allow_nan=False);stream.write('\n')
            stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        os.link(name,final);fsync_directory(destination)
        # A failure here deliberately retains the unpromoted model orphan.
        os.link(meta_name,metadata);fsync_directory(destination)
    finally:
        for path in partials:path.unlink(missing_ok=True)
        fsync_directory(destination)
    return checked


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if '--execute' not in argv:
        print('PLAN_ONLY: no reads, writes, launches, services or policy publication')
        return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--publish',action='store_true')
    parser.add_argument('--job',type=Path,required=True);parser.add_argument('--job-sha256',required=True)
    parser.add_argument('--source-sha256',required=True);args=parser.parse_args(argv)
    require(digest(__file__) == args.source_sha256,'Exact selected protection source required')
    reader=reader_module();entry=reader.pin(args.job);require(entry['sha256'] == args.job_sha256,'Protection job SHA differs')
    job=reader.read_pin(entry)
    result=publish(job,entry,reader) if args.publish else verify(job,entry,reader)
    print(json.dumps(dict(outcome=result['assessment']['outcome'],protected_checkpoint=result.get('protected_checkpoint'),
        managed_incumbent_updated=False,live_learner_restored=False)))
    return 0


if __name__ == '__main__':raise SystemExit(main())
