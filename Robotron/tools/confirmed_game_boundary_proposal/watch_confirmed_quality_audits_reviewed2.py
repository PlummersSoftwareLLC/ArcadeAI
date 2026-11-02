"""Audit each original completed quality leg once, using pinned controllers.

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
    attempted=[];audits=[];started=time.monotonic()
    try:
        require(original_owner(job['owner']) is False, 'Observer must start while original parent is live')
        publish(output/'original-live-owner.json',job['owner'])
        while True:
            require(time.monotonic()-started < 30600, 'Original observer deadline; no retry')
            for entry in job['pins']:
                require(pin(entry['path']) == entry, 'Bound source/config/evidence changed')
            terminal=original_owner(job['owner'])
            state=json.loads(Path(job['state_path']).read_text())
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
                publish(output/'result.json',dict(status='ALL_FOUR_ORIGINAL_TERMINAL_AUDITS_PASS',
                    audits=audits,original_owner=job['owner'],qualification_decided=False,promotion=False))
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
    require(job['schema'] == 'robotron-original-confirmed-terminal-audit-observer-v1'
            and set(job['configs']) == {'1','2','3','4'}, 'Exact four original audit jobs required')
    def stop(*_):
        global STOP
        STOP=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    return run(job)


if __name__=='__main__':
    raise SystemExit(main())
