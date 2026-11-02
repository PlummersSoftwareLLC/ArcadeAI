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
    require(pin(path)==entry and entry['identity']['mode']=='0o444'
            and entry['identity']['uid']==os.getuid() and entry['identity']['nlink']==1,
            'Immutable artifact identity differs')
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


def review(directory):
    require(CFG is not None and Path(directory).resolve()==Path(CFG['campaign_directory']),
            'Explicit exact root protection job required')
    evidence={JOB_PIN['path']:JOB_PIN['sha256']}
    def read(entry):
        result=read_pin(entry)
        evidence[entry['path']]=entry['sha256']
        return result
    package=read(CFG['source_package'])
    root=Path(package['root'])
    for relative, expected in package['files'].items():
        path=root/relative
        require(path.resolve(strict=True).is_relative_to(root) and digest(path)==expected,
                'Selected private evaluation package changed')
    source=CFG['auditor_source']
    auditor=checked_module('_confirmed_winner_auditor_'+str(time_nonce()),source)
    evidence[source['path']]=source['sha256']
    binding=read(CFG['binding_job'])
    args=argparse.Namespace(binding_job=Path(CFG['binding_job']['path']),
        binding_job_sha256=CFG['binding_job']['sha256'],campaign=Path(directory),
        plan_sha256=CFG['plan_sha256'])
    auditor.configure(args)
    plan=auditor.decode((Path(directory)/'plan.json').read_bytes())
    auditor.validate_future_plan(plan,args,Path(directory))
    require(digest(Path(directory)/'plan.json')==CFG['plan_sha256'], 'Exact original native plan required')
    native_owner=read(CFG['native_owner'])
    observer_owner=read(CFG['observer_owner'])
    native_closure=read(pin(CFG['native_closure_path']))
    observer_closure=read(pin(CFG['observer_closure_path']))
    original_terminal_archive(native_closure,native_owner,evidence)
    original_terminal_archive(observer_closure,observer_owner,evidence)
    watcher_job=read(CFG['watcher_job'])
    require(watcher_job['owner']==native_owner, 'Audit observer belongs to another original campaign')
    observer_result=read(pin(Path(watcher_job['output'])/'result.json'))
    require(observer_result.get('status')=='ALL_FOUR_ORIGINAL_TERMINAL_AUDITS_PASS'
            and observer_result.get('original_owner')==native_owner
            and len(observer_result.get('audits',[]))==4, 'All four original terminal audits required')
    # This immutable package includes the existing reviewed publication algorithm
    # and strict complete-game assessment. No implementation is monkey-patched.
    sys.path.insert(0,str(root/'tools'))
    generic_path=root/'tools/protect_quality_winner.py'
    generic=checked_module('_confirmed_winner_generic_'+str(time_nonce()),pin(generic_path))
    require(Path(generic.campaign.__file__).resolve()==root/'tools/run_quality_campaign.py',
            'Wrong loaded campaign implementation')
    base=generic.review(directory)
    evidence.update(base['evidence_sha256'])
    require(base['assessment']['outcome']=='qualified_improvement'
            and base['assessment']['qualified_improvement'] is True,
            'Both independently valid candidate cohorts must qualify')
    require([x['index'] for x in base['assessment']['candidate_checks']]==[2,4]
            and all(x['mean_pass'] is True and x['median_pass'] is True
                    for x in base['assessment']['candidate_checks']), 'Separate candidate gates required')
    terminal_module=sys.modules.get('confirmed_terminal_evidence')
    require(terminal_module is not None and Path(terminal_module.__file__).resolve()==root/'tools/confirmed_terminal_evidence.py',
            'Selected terminal implementation was not loaded')
    final_status=auditor.decode((Path(directory)/'status.json').read_bytes())
    require(all(type(x['returncode']) is int and x['returncode']==0 for x in final_status['legs']),
            'Original evaluator exit codes must be integer zero')
    audit_joins=[]
    for expected_index, completed_pin in enumerate(observer_result['audits'],1):
        completed=read(completed_pin)
        require(completed['index']==expected_index and completed['original_attempt']==1
                and type(completed['controller_exit']) is int and completed['controller_exit']==0,
                'One original audit per ordered leg required')
        control=read(completed['controller_receipt'])
        require(type(control['original_exit']) is int and control['original_exit']==0
                and control['lifecycle_complete'] is True and control['unit_released'] is True,
                'Original bounded audit did not cleanly succeed')
        cached=read(completed['audit_receipt'])
        assessed=base['assessment']['legs'][expected_index-1]
        validate_review_join(cached,assessed,CFG['plan_sha256'])
        spec=plan['legs'][expected_index-1]
        receipt=auditor.decode(Path(spec['receipt_path']).read_bytes())
        rowlist=receipt.get('rows',receipt.get('cohort',{}).get('rows',[]))
        payloads={name:(Path(spec['job']['directory'])/'journal'/name).read_bytes()
                  for name in ('games.jsonl','measurement_starts.jsonl')}
        links=terminal_module.verify_original_journal_bytes(receipt,payloads)
        rom=[auditor.validate_rom_terminal(row,receipt['terminal_successors'][row['journal_game_id']])
             for row in rowlist]
        require(links==cached['original_terminal_readback']['links']
                and rom==cached['rom_game_over_evidence']['links'], 'Cached audit differs from original terminal recomputation')
        # Audits archive a live native status snapshot. Its finished leg record
        # must match final status; its whole-file hash need not remain current.
        audit_directory=Path(completed['audit_receipt']['path']).parent
        for original, entry in cached['artifacts'].items():
            name=Path(entry['copy'])
            require(name.name==str(name), 'Unsafe audit archive component')
            archive=audit_directory/name
            require(digest(archive)==entry['sha256'], 'Independent audit archive changed')
            evidence[str(archive)]=entry['sha256']
            if Path(original)==Path(directory)/'status.json':
                observed=auditor.decode(archive.read_bytes())
                require([x for x in observed['legs'] if x['index']==expected_index]
                        ==[final_status['legs'][expected_index-1]], 'Original finished leg record changed')
            else:
                require(digest(original)==entry['sha256'], 'Original audited artifact changed')
        audit_joins.append(dict(index=expected_index,review=completed['audit_receipt'],
            controller=completed['controller_receipt'],verified_games=len(links),ROM_verified_games=len(rom)))
    require(all(digest(path)==expected for path,expected in evidence.items()), 'Closed evidence changed during review')
    require(not any(x=='torch' or x.startswith('torch.') for x in sys.modules), 'Protection review imported numerical runtime')
    base.update(schema='robotron-confirmed-terminal-protected-winner-v1',
        evidence_sha256=evidence,root_protection_job=JOB_PIN,source_package=CFG['source_package'],
        original_native_closure=pin(CFG['native_closure_path']),
        original_observer_closure=pin(CFG['observer_closure_path']),
        independent_terminal_and_ROM_audits=audit_joins,
        CPU_and_window_binding=CFG['binding_job'],original_authorities_verified=True)
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
    require(CFG['schema']=='robotron-confirmed-terminal-protection-job-v1', 'Wrong protection job schema')


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
