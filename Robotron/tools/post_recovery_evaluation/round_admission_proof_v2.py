"""Prove natural round admission from unchanged fleet source and raw receipts.

Raw status/API/census fields are retained. A declared view can account for the
short sequential spawn phase only after the preceding durable192-score barrier.
It never invents an actor, connection, completion, or observer sample.
"""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import statistics

ROOT=Path(__file__).resolve().parents[2]
FLEET=ROOT/'tools/power_recovery/round_fleet.py'
FLEET_SHA='f6bba59d7d69b2d437728ff6fcabdd4e575a5b14aa22e25dbab4a72a3463b4d2'
SLOTS=set(map(str,range(192)))
BOOTSTRAP_MAX_S=5
MAX_CHAIN=16


def require(value,message):
    if not value:raise ValueError(message)


def effective_round(sample):
    proof=sample.get('round_admission')
    return proof['effective_round'] if proof is not None else sample['status']['round']


def chain_start(case,sample,previous):
    anchor=case['initial_round']if previous is None else effective_round(previous)
    return min(anchor,sample['status']['round'])


def view(sample):
    proof=sample.get('round_admission')
    if proof is not None and proof['bootstrap']:
        current=proof['current']
        return dict(round=proof['effective_round'],started=json.loads(current['started']['raw']),
            results={slot:json.loads(value['raw'])for slot,value in current['receipts'].items()},
            receipt_hashes={slot:value['sha256']for slot,value in current['receipts'].items()},
            pending=set(proof['pending']),registering=set(proof['registering']),bootstrap=True)
    return dict(round=sample['status']['round'],started=sample['started'],results=sample['results'],
        receipt_hashes=sample['receipt_hashes'],pending=set(),registering=set(),bootstrap=False)


def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,mode=oct(stat.S_IMODE(info.st_mode)),
        uid=info.st_uid,nlink=info.st_nlink)


def capture(path):
    path=Path(path)
    require(path.is_absolute()and path.resolve(strict=True)==path and not path.is_symlink(),
            'Round evidence path is not canonical')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb')as stream:
        info=os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode)and info.st_uid==os.getuid()and info.st_nlink==1,
                'Round evidence is not an original owned regular file')
        raw=stream.read((2<<20)+1)
        require(len(raw)<=2<<20 and identity(os.fstat(stream.fileno()))==identity(info),
                'Round evidence changed or exceeded bound')
    require(identity(path.stat())==identity(info),'Round evidence path changed during capture')
    return dict(path=str(path),raw=raw.decode('utf-8'),sha256=hashlib.sha256(raw).hexdigest(),identity=identity(info))


def raw_record(value,path):
    raw=value['raw'].encode('utf-8')
    require(value['path']==str(path)and value['sha256']==hashlib.sha256(raw).hexdigest()
            and value['identity']['bytes']==len(raw)and len(raw)<=2<<20
            and value['identity']['uid']==os.getuid()and value['identity']['nlink']==1,
            'Archived round bytes/path/identity differ')
    return raw


def collect_round(root,number,closed):
    directory=root/('round-%06d'%number)
    result=dict(round=number,started=capture(directory/'started.json'),
        receipts={str(int(path.name.split('-')[1])):capture(path)
            for path in sorted(directory.glob('slot-*-result.json'))})
    if closed:result.update(summary=capture(directory/'summary.json'),scores_csv=capture(directory/'scores.csv'))
    return result


def collect(case,sample,previous=None,*,journal_lines=None):
    """Attach evidence only for initial jumps, turnover, or bounded bootstrap."""
    root=Path(case['round_root']);published=sample['status']['round'];number=published
    next_path=root/('round-%06d'%(published+1))/'started.json'
    if next_path.exists():number+=1
    actors=set(sample['actors']);results=set(sample['results'])if number==published else set()
    api_slots={str(row['client_slot'])for row in sample['api']['client_rows']}
    bootstrap=number!=published or actors|results!=SLOTS or api_slots-results!=actors-results
    start=chain_start(case,sample,previous)
    if number==start and not bootstrap:return sample
    require(type(start)is int and type(number)is int and 0<=number-start<=MAX_CHAIN,
            'Round admission chain is backward or exceeds predeclared bound')
    # The journal terminating newline is the existing commit rule. Preserve
    # relevant original lines, including their exact bytes, for raw replay.
    if journal_lines is None:
        wire=Path(case['completion_journal']).read_bytes()
        journal={row['journal_game_id']:line.decode('utf-8')+'\n'for line in wire.split(b'\n')[:-1]
            if line for row in [json.loads(line)]}
    else:
        # The pinned census has already read this same committed journal and
        # parsed each row. Reuse its exact raw lines; verify_round independently
        # rejoins every selected line to its original per-slot receipt.
        journal=journal_lines
    chain=[collect_round(root,n,True)for n in range(start,number)]
    current=collect_round(root,number,False)if bootstrap else None
    records=[*chain,*([current]if current else [])]
    identifiers={json.loads(value['raw'])['result']['journal_game_id']for record in records
        for value in record['receipts'].values()}
    require(identifiers<=journal.keys(),'Round admission receipt precedes its journal commit')
    actual_results=set(current['receipts'])if current else results
    sample['round_admission']=dict(schema='robotron-natural-round-admission-raw-v1',
        fleet_source_sha256=FLEET_SHA,effective_round=number,published_round=published,
        bootstrap=bootstrap,bootstrap_max_s=BOOTSTRAP_MAX_S,chain_start=start,closed_chain=chain,
        current=current,pending=sorted(SLOTS-actors-actual_results,key=int),
        registering=sorted(actors-actual_results-api_slots,key=int),
        committed_journal_lines={key:journal[key]for key in sorted(identifiers)})
    return sample


def verify_round(case,record,lines,closed):
    number=record['round'];root=Path(case['round_root'])/('round-%06d'%number)
    started=json.loads(raw_record(record['started'],root/'started.json'))
    require(started['round']==number and started['slots']==list(range(192))
            and started['one_full_game_each']is True and started['next_round_waits_for_all']is True,
            'Round start does not declare original192 single-game slots')
    require(set(record['receipts'])<=SLOTS,'Round receipt has an unknown slot')
    results={}
    for slot,value in record['receipts'].items():
        outer=json.loads(raw_record(value,root/('slot-%03d-result.json'%int(slot))))
        row=outer['result'];line=lines.get(row['journal_game_id'])
        require(line is not None and line.endswith('\n')and json.loads(line)==row,
                'Round receipt lacks its exact committed raw journal line')
        require(outer['round']==number and str(row['client_slot'])==slot
                and type(outer['pid'])is int and outer['pid']>0
                and row['start_unix_s']>=started['started_unix_s']
                and row['end_unix_s']>=row['start_unix_s']
                and type(row['eval_only'])is bool and row['eval_only']==case['slot_eval'][slot]
                and row['experiment']==case['experiment']
                and row['complete']is row['eligible']is row['known_start']is True
                and row['boundary_reason']in ('score_reset','zero_score_restart')
                and type(row['score'])is int and row['score']>=0,
                'Round completion slot/start/boundary/score differs')
        results[slot]=outer
    require(len({outer['result']['journal_game_id']for outer in results.values()})==len(results),
            'Round receipt reuses another committed game')
    if not closed:return started,results,None
    summary=json.loads(raw_record(record['summary'],root/'summary.json'))
    require(set(results)==SLOTS and summary['round']==number and summary['total']==192
            and summary['completed']==summary['retired']==192 and summary['active']==0
            and summary['complete']is summary['all_final_scores_durable']is True
            and summary['changing_policy_training_round']is True and summary['quality_qualified']is False,
            'Round admission lacks the complete durable192-score/reap barrier')
    scores=[outer['result']['score']for outer in results.values()]
    require(summary['mean']==statistics.mean(scores)and summary['median']==statistics.median(scores),
            'Round admission summary numerical values differ')
    rows=list(csv.DictReader(io.StringIO(raw_record(record['scores_csv'],root/'scores.csv').decode())))
    require(len(rows)==192 and {row['slot']for row in rows}==SLOTS
            and all(int(row['score'])==results[row['slot']]['result']['score']
                and row['journal_game_id']==results[row['slot']]['result']['journal_game_id']for row in rows),
            'Round admission CSV does not match all192 original results')
    expected=[dict(slot=int(slot),score=outer['result']['score'],level=outer['result']['max_level'],
        duration_s=outer['result']['duration_s'],journal_game_id=outer['result']['journal_game_id'])
        for slot,outer in sorted(results.items(),key=lambda item:int(item[0]))]
    require(summary['results']==expected and summary['updated_unix_s']>=started['started_unix_s']
            and all(outer['result']['end_unix_s']<=summary['updated_unix_s']for outer in results.values()),
            'Round admission summary roster or completion times differ')
    return started,results,summary


def verify(case,sample,previous=None):
    proof=sample.get('round_admission')
    if proof is None:
        require(previous is not None or sample['status']['round']==case['initial_round'],
                'Unexplained initial round without a durable predecessor chain')
        return view(sample)
    require(proof['schema']=='robotron-natural-round-admission-raw-v1'
            and proof['fleet_source_sha256']==FLEET_SHA==case['inputs'][str(FLEET)]['sha256']
            and hashlib.sha256(FLEET.read_bytes()).hexdigest()==FLEET_SHA,
            'Original sequential one-game fleet source changed')
    published=sample['status']['round'];number=proof['effective_round']
    start=chain_start(case,sample,previous)
    require(type(number)is int and proof['published_round']==published and proof['chain_start']==start
            and 0<=number-start<=MAX_CHAIN and number in (published,published+1)
            and (previous is None or number-effective_round(previous)in (0,1)),
            'Skipped, backward, or unexplained round admission')
    require(proof['bootstrap_max_s']==BOOTSTRAP_MAX_S and type(proof['bootstrap'])is bool,
            'Prospective bootstrap declaration changed')
    chain=proof['closed_chain'];require([record['round']for record in chain]==list(range(start,number)),
            'Round predecessor chain is incomplete or reordered')
    records=[*chain,*([proof['current']]if proof['current']else [])]
    identifiers={json.loads(value['raw'])['result']['journal_game_id']for record in records
        for value in record['receipts'].values()}
    require(set(proof['committed_journal_lines'])==identifiers,
            'Raw admission journal witness coverage differs from original receipts')
    verified=[verify_round(case,record,proof['committed_journal_lines'],True)for record in chain]
    current=view(sample)
    if proof['bootstrap']:
        require(proof['current']['round']==number,'Bootstrap raw directory belongs to another round')
        current_start,current_results,_=verify_round(case,proof['current'],proof['committed_journal_lines'],False)
        require(current['started']==current_start and current['results']==current_results,
                'Bootstrap view does not match original raw start/receipts')
    else:
        require(proof['current']is None and proof['pending']==proof['registering']==[]and number==published,
                'Ordinary admission carries an unexplained bootstrap projection')
    for index,(began,results,summary)in enumerate(verified):
        next_start=verified[index+1][0]if index+1<len(verified)else current['started']
        require(next_start['started_unix_s']>=summary['updated_unix_s'],
                'Next round started before all192 scores and retirements')
        if index==0:
            baseline=previous
            if baseline is None and case.get('baseline_snapshot'):
                pin=case['baseline_snapshot'];raw=Path(pin['path']).read_bytes()
                require(hashlib.sha256(raw).hexdigest()==pin['sha256'],'Original baseline snapshot changed')
                baseline=json.loads(raw)
            if baseline is not None and effective_round(baseline)==start:
                prior=view(baseline)
                require(all(record_hash==chain[0]['receipts'][slot]['sha256']
                    for slot,record_hash in prior['receipt_hashes'].items()),'Original committed score changed across admission')
                require(all(results[slot]['pid']==actor['pid']for slot,actor in baseline['actors'].items()),
                        'Admission retired a different original actor PID')
            elif baseline is not None:
                require(effective_round(baseline)==number and baseline.get('round_admission')is not None
                        and baseline['round_admission']['bootstrap']is True
                        and baseline['round_admission']['closed_chain']==chain,
                        'Bootstrap continuation lost its accepted original barrier')
    if verified:
        old_pids={outer['pid']for _,results,_ in verified for outer in results.values()}
        require(not old_pids&{actor['pid']for actor in sample['actors'].values()},
                'An original retired actor survived round admission')
    actors=set(sample['actors']);results=set(current['results']);api=sample['api']
    slots=[str(row['client_slot'])for row in api['client_rows']]
    if proof['bootstrap']:
        age=sample['unix_s']-current['started']['started_unix_s']
        require(0<=age<=BOOTSTRAP_MAX_S and 0<=sample['unix_s']-api['ts']<=.5,
                'Sequential bootstrap or its raw API is stale')
        require(number>case['initial_round']or previous is not None,
                'Initial readiness cannot begin from an unproved bootstrap')
        if number!=published:
            require(sample['status']['complete']is True and sample['status']['retired']==192
                    and verified and verified[-1][2]==sample['status']|{
                        k:verified[-1][2][k]for k in verified[-1][2]if k not in sample['status']},
                    'Unpublished new round lacks its original completed status')
        else:require(not current['pending'],'Published round cannot hide a missing actor')
        require(current['pending']==SLOTS-actors-results
                and (not current['pending']or current['pending']==set(map(str,range(min(map(int,current['pending'])),192))))
                and not current['pending']&(actors|results),'Sequential bootstrap pending slots are not the unspawned suffix')
        require(len(slots)==len(set(slots))==api['client_count']and set(slots)<=actors
                and current['registering']==actors-results-set(slots),
                'Bootstrap API has an unknown, duplicate, or falsely registered slot')
        require(all(type(row['connected_seconds'])in (int,float)
                and math.isfinite(row['connected_seconds'])and 0<=row['connected_seconds']
                and row['connected_seconds']+sample['unix_s']-api['ts']<=age+.05
                for row in api['client_rows']), 'Bootstrap API row predates the new original round')
        if previous is not None and effective_round(previous)==number:
            prior=view(previous)
            require(current['pending']<=prior['pending'], 'A spawned actor became pending again')
    if verified:
        current['previous_complete']=dict(summary=verified[-1][2],results=verified[-1][1],
            receipts={slot:value['sha256']for slot,value in chain[-1]['receipts'].items()})
    return current
