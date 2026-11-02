"""Review remaining original legs once after the reference warning disposition.

This observer launches only the selected bounded read-only audit jobs. It never
restarts/evaluates a cohort, changes training, stops the quality owner, or
publishes a policy. A failed or ambiguous attempt is preserved without retry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

STOP = False


def require(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    path=Path(path); before=path.stat()
    raw=path.read_bytes(); after=path.stat()
    require(before == after, 'File changed while reading')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=after.st_size,
        identity=dict(device=after.st_dev,inode=after.st_ino,bytes=after.st_size,
            mtime_ns=after.st_mtime_ns,ctime_ns=after.st_ctime_ns,mode=oct(after.st_mode&0o777),
            uid=after.st_uid,nlink=after.st_nlink))


def publish(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return pin(path)


def select_ready(plan, state, attempted):
    """Only a unique original finished/exit0 record can authorize its one audit."""
    require(state['plan_sha256'] == plan['sha256'], 'Original native plan changed')
    records=state['legs']
    require([r['index'] for r in records] == list(range(1,len(records)+1))
            and 0 <= len(records) <= 4, 'Duplicate, missing or reordered original legs')
    for record in records:
        index=record['index']; require(type(index) is int, 'Integer original index required')
        require(record['role'] == ('reference' if index%2 else 'candidate'), 'Original R/C order differs')
        require(record['state'] in ('running','finished'), 'Unknown original leg state')
        if record['state'] == 'running':
            require(record is records[-1], 'Only the last original leg can be running')
            return None
        require(type(record.get('returncode')) is int and record['returncode'] == 0,
                'Original leg did not finish exit0; no audit or retry authorized')
        if index not in attempted:
            return index
    return None



def validate_review(review,index,plan_sha256):
    require(review.get('valid') is True and review.get('leg')==index
            and review.get('plan_sha256')==plan_sha256
            and review.get('schema')=='robotron-confirmed-original-terminal-leg-v1',
            'Independent original-terminal audit rejected or wrong scope')
    proof=review.get('original_terminal_readback',{})
    count=review.get('statistics',{}).get('count')
    require(type(count) is int and count>=50 and proof.get('status')=='PASS'
            and type(proof.get('verified_games')) is int and proof['verified_games']==count,
            'Independent original-terminal proof does not cover every admitted game')
    rom=review.get('rom_game_over_evidence',{})
    require(rom.get('status')=='PASS' and type(rom.get('verified_games')) is int
            and rom['verified_games']==count,
            'Independent ROM game-over evidence does not cover every admitted game')



def validate_reference_supplement(review,plan_sha256):
    require(review.get('schema')=='robotron-original-audit-optional-warning-supplement-v1'
        and review.get('status')=='ORIGINAL_NEEDS_REVIEW_RESOLVED_EXACT_UNUSED_EXPERT_WARNING'
        and review.get('leg')==1 and review.get('role')=='reference'
        and review.get('plan_sha256')==plan_sha256
        and review.get('original_audit_valid') is False
        and type(review.get('original_audit_exit')) is int and review['original_audit_exit']==2
        and type(review.get('original_evaluator_exit')) is int and review['original_evaluator_exit']==0
        and review.get('supplemental_valid_completed_leg') is True
        and review.get('cohort_rerun') is False and review.get('original_auditor_rerun') is False
        and review.get('original_receipts_changed') is False and review.get('scientific_gates_changed') is False,
        'Only the exact original reference needs-review disposition can be seeded')
    count=review.get('statistics',{}).get('count'); ids=review.get('original_game_ids',[])
    require(type(count) is int and count==202 and len(ids)==len(set(ids))==count,
        'Full original reference game identity/count required')
    for name in ('original_terminal_readback','rom_game_over_evidence'):
        proof=review.get(name,{})
        require(proof.get('status')=='PASS' and proof.get('verified_games')==count
            and len(proof.get('links',[]))==count
            and {row['journal_game_id'] for row in proof['links']}==set(ids),
            'Every original reference terminal/ROM link required')
    require(review['classified_warning']==dict(line_number=2,
        text="[WARN] Robotron expert unavailable (No module named 'v3'); expert guidance disabled.",
        reason='Frozen greedy controls exclude the only expert action branch; actual handler differential passed.'),
        'Only the exact unused-expert warning is covered')


def original_owner(owner):
    raw=subprocess.check_output(['systemctl','--user','show',owner['unit'],
        '-p','Id','-p','InvocationID','-p','MainPID','-p','ExecMainPID',
        '-p','ExecMainCode','-p','ExecMainStatus','-p','NRestarts','-p','SubState'],text=True,timeout=10)
    fields=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
    require(fields['Id'] == owner['unit'] and fields['InvocationID'] == owner['invocation_id']
            and fields['NRestarts'] == '0', 'Original native owner changed; leave it untouched')
    if fields['MainPID'] != '0':
        require(fields['MainPID'] == str(owner['pid']), 'Native owner PID changed')
        raw=(Path('/proc')/str(owner['pid'])/'stat').read_text()
        require(int(raw.rsplit(')',1)[1].split()[19]) == owner['starttime_ticks'], 'Native owner start changed')
        return False
    require(fields['ExecMainPID'] == str(owner['pid']) and fields['ExecMainCode'] == '1'
            and fields['SubState'] in ('exited','dead','failed'), 'Original terminal outcome unavailable')
    return True


def run(job):
    output=Path(job['output']);output.mkdir(mode=0o700)
    attempted=[1];audits=[];started=time.monotonic()
    try:
        require(original_owner(job['owner']) is False, 'Observer must start while original parent is live')
        publish(output/'original-live-owner.json',job['owner'])
        for entry in job['pins']:require(pin(entry['path'])==entry,'Selected handoff evidence changed')
        require(original_owner(job['previous_observer']) is True,'Original failed observer must be terminal')
        reference_review=json.loads(Path(job['reference_supplement']['path']).read_text())
        validate_reference_supplement(reference_review,job['plan']['sha256'])
        closure=json.loads(Path(job['reference_supplement_closure']['path']).read_text())
        require(type(closure.get('original_exit')) is int and closure['original_exit']==0
            and closure.get('lifecycle_complete') is True and closure.get('unit_released') is True,
            'Original supplemental review did not close exit0')
        audits.append(publish(output/'leg01-original-needs-review-disposition.json',dict(index=1,
            supplemental_review=job['reference_supplement'],original_audit_exit=2,
            original_evaluator_exit=0,original_auditor_rerun=False,cohort_rerun=False,promotion=False)))
        while True:
            require(time.monotonic()-started < 30600, 'Original observer deadline; no retry')
            for entry in job['pins']:
                require(pin(entry['path']) == entry, 'Bound source/config/evidence changed')
            terminal=original_owner(job['owner'])
            state=json.loads(Path(job['state_path']).read_text())
            require(state['legs'][0]==reference_review['original_finished_record'],'Original reference record changed after handoff')
            index=select_ready(job['plan'],state,attempted)
            if STOP:
                raise InterruptedError('Observer stopped; quality owner and training left untouched')
            if index is not None:
                config=job['configs'][str(index)]
                # Persist intent before launching; an ambiguous launch is never repeated.
                publish(output/f'leg{index:02d}-original-attempt.json',dict(index=index,
                    original_record=state['legs'][index-1],config=config,attempt=1,retry=False))
                attempted.append(index)
                argv=['/usr/bin/python3.12','-I','-B',job['controller']['path'],
                    '--execute','--config',config['path'],
                    '--expected-source-sha256',job['controller']['sha256']]
                with (output/f'leg{index:02d}-controller.stdout.txt').open('x') as stdout, \
                     (output/f'leg{index:02d}-controller.stderr.txt').open('x') as stderr:
                    child=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=130)
                cfg=json.loads(Path(config['path']).read_text())
                receipt=Path(cfg['output'])/'root-original-result-and-owned-release.json'
                record=json.loads(receipt.read_text())
                require(child.returncode == 0 and record['original_exit'] == 0
                        and record['lifecycle_complete'] is True and record['unit_released'] is True,
                        'Original audit/controller nonzero or incomplete; preserve without retry')
                audit_path=Path(cfg['argv'][cfg['argv'].index('--output')+1])/'review-receipt.json'
                review=json.loads(audit_path.read_text())
                validate_review(review,index,job['plan']['sha256'])
                audit=publish(output/f'leg{index:02d}-completed.json',dict(index=index,
                    controller_exit=child.returncode,controller_receipt=pin(receipt),
                    audit_receipt=pin(audit_path),original_attempt=1,promotion=False))
                audits.append(audit)
            elif terminal:
                require(state['state'] == 'finished' and len(audits) == 4,
                        'Original campaign ended before all four valid row audits')
                publish(output/'result.json',dict(status='FOUR_ORIGINAL_COHORT_REVIEWS_COMPLETE_WITH_REFERENCE_SUPPLEMENT',
                    audits=audits,original_owner=job['owner'],
                    original_reference_audit_exit=2,reference_supplement_included=True,
                    original_reference_rerun=False,qualification_decided=False,promotion=False))
                return 0
            time.sleep(5)
    except BaseException as error:
        publish(output/'result.json',dict(status='PRESERVED_WITHOUT_RETRY',error=repr(error),
            attempted=attempted,audits=audits,quality_owner_touched=False,training_touched=False,promotion=False))
        return 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path)
    parser.add_argument('--job-sha256');parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, launches, mutations or runtime queries');return 0
    require(pin(Path(__file__).resolve())['sha256'] == args.source_sha256
            and pin(args.job)['sha256'] == args.job_sha256, 'Exact root source/job required')
    job=json.loads(args.job.read_text())
    require(job['schema'] == 'robotron-original-confirmed-terminal-audit-observer-reference-supplement-v1'
            and set(job['configs']) == {'2','3','4'}, 'Only remaining original audit jobs2..4 are allowed')
    def stop(*_):
        global STOP
        STOP=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    return run(job)


if __name__=='__main__':
    raise SystemExit(main())
