"""Bound historical early scores using life-boundary journals, not invented snapshots.

The resulting ranges are observation bounds, not statistical confidence
intervals. Comparing them with the final hour tests whether shortening the
metric can change the observed ranking. No live workload or control is read.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import statistics
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
MINUTES=(5,10,15,20,30)


def require(value,message):
    if not value:raise ValueError(message)


def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)),uid=info.st_uid,nlink=info.st_nlink)


class Reader:
    def __init__(self):self.inventory={}

    def raw(self,pin):
        path=Path(pin['path']);before=path.lstat()
        require(path.is_absolute() and path.resolve(strict=True)==path
            and stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o444
            and before.st_uid==os.getuid() and before.st_nlink==1 and 0<before.st_size<=16<<20,
            'Bounded canonical immutable journal/metadata required')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb')as stream:
            raw=stream.read((16<<20)+1);after=os.fstat(stream.fileno())
        actual=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))
        require(identity(before)==identity(after)==identity(path.lstat()),'Input changed during read')
        require(all(actual[k]==pin[k]for k in ('path','sha256','bytes'))
            and all(actual['identity'][k]==v for k,v in pin.get('identity',{}).items()),'Held input changed')
        self.inventory[str(path)]=actual
        return raw

    def read(self,pin):return json.loads(self.raw(pin))

    def pin(self,path):
        before=path.lstat();raw=path.read_bytes()
        require(identity(before)==identity(path.lstat()),'Input changed while selected')
        return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))


def arm(subject,reader):
    native=reader.read(subject['native_result'])
    require(native['complete'] is True and native['errors']==[],'Original closed native result required')
    seal=reader.read(native['deadline_score_seal'])
    require(seal['n_scored']==32 and seal['n_completed']==0 and seal['n_censored']==32,
        'This historical backtest handles selected first games still active at the final cutoff only')
    require(seal['horizon_ns']==3_600_000_000_000,'Original one-hour endpoint required')
    root=Path(subject['native_result']['path']).parent
    lower=upper=None
    for path in sorted((root/'status-samples').glob('*.json')):
        status=reader.read(reader.pin(path))
        require(status['original_job']==native['original_job'] and status['errors']==[],
            'Original status source/job differs')
        if status['anchor'] is None:lower=status['observed_unix_s']
        else:
            require(all(status['anchor'][k]==seal[k]for k in ('anchor_monotonic_ns','deadline_monotonic_ns','horizon_ns')),
                'Status/final monotonic anchor differs')
            upper=status['observed_unix_s'];break
    require(lower is not None and upper is not None and 0<upper-lower<30,
        'Retained status observations must bracket the actual common anchor within30s')
    members={row['member']['journal_game_id']:row for row in seal['rows']}
    require(len(members)==32 and {r['slot']for r in members.values()}==set(range(4096,4128)),
        'All32 distinct final selected game identities required')
    events={key:[]for key in members}
    for raw in reader.raw(native['journal']['lives.jsonl']).splitlines():
        row=json.loads(raw);jid=row['journal_game_id']
        if jid not in members or row.get('known_game_start') is not True:continue
        expected=members[jid]['member'];context=row['context']
        require(row['client_slot']==expected['slot'] and row['game_uid']==expected['game_uid']
            and context['experiment']==expected['experiment']
            and context['measurement_generation']==expected['measurement_generation']
            and context['measurement_active'] is True,'Life event belongs to a different measured game')
        score=row['cumulative_score'];require(type(score)is int and score>=0,'Full integer journal score required')
        stamp=datetime.fromisoformat(row['utc']);require(stamp.tzinfo is not None,'Explicit UTC journal time required')
        events[jid].append((stamp.timestamp(),score))
    for values in events.values():
        values.sort();require(all(a[1]<=b[1]for a,b in zip(values,values[1:])),
            'Selected first-game life score regressed; no interpolation or repair allowed')
    estimates={}
    for minute in MINUTES:
        bounds=[]
        for jid,row in members.items():
            # Use a later score only as an upper bound; never report it as the
            # score at the requested earlier horizon or interpolate linearly.
            low=max([row['score_at_anchor']]+[score for stamp,score in events[jid]if stamp<=lower+minute*60])
            high=min([row['score_at_deadline']]+[score for stamp,score in events[jid]if stamp>=upper+minute*60])
            require(low<=high,'Historical observations give inconsistent bounds')
            bounds.append(dict(slot=row['slot'],lower=low,upper=high))
        estimates[str(minute)]=dict(mean_lower=statistics.mean(r['lower']for r in bounds),
            mean_upper=statistics.mean(r['upper']for r in bounds),slots=bounds)
    return dict(final_mean=seal['mean_score'],anchor_wall_time_bounds=[lower,upper],
        anchor_bracket_width_s=upper-lower,early=estimates)


def analyze(selection,reader):
    results=[]
    for case in selection['cases']:
        reference=arm(case['arms']['R1'],reader);candidate=arm(case['arms']['C1'],reader)
        final_change=candidate['final_mean']/reference['final_mean']-1
        early={}
        for minute in MINUTES:
            a,b=reference['early'][str(minute)],candidate['early'][str(minute)]
            low=b['mean_lower']/a['mean_upper']-1;high=b['mean_upper']/a['mean_lower']-1
            direction='higher'if low>0 else'lower'if high<0 else'unresolved'
            early[str(minute)]=dict(mean_change_observation_bounds=[low,high],observed_direction=direction,
                opposite_final_observed_direction=direction==('lower'if final_change>0 else'higher'))
        results.append(dict(case=case['case'],reference=reference,candidate=candidate,
            final60min_mean_change=final_change,early_comparisons=early))
    count=len(results)
    return dict(schema='robotron-short-horizon-life-journal-backtest-v1',status='PASS_CONSERVATIVE_HISTORICAL_OBSERVATION_BOUNDS',
        observed_unix_s=time.time(),pairs=results,input_inventory=list(reader.inventory.values()),
        summary={str(m):dict(opposite_final_direction=sum(r['early_comparisons'][str(m)]['opposite_final_observed_direction']for r in results),
            unresolved=sum(r['early_comparisons'][str(m)]['observed_direction']=='unresolved'for r in results),pairs=count)for m in MINUTES},
        limits=['Observation brackets, not statistical confidence intervals or exact early score snapshots.',
            'Wall-clock life records are bracketed using source-owned status observations; clock stability is assumed. No new historical clock guarantee is invented.',
            'Five related serial comparisons cannot establish99% predictive reliability.',
            'An early-horizon difference tests that early metric; even perfect precision does not prove the same ranking at one hour or full-game completion.',
            'Any early futility threshold chosen after this backtest needs prospective validation and error control before automatic deployment.'],
        current_test_changed=False,promotion=False,full_game_confirmation_gates_changed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--selection',type=Path)
    parser.add_argument('--selection-sha256');parser.add_argument('--output',type=Path);args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    raw=args.selection.read_bytes();require(hashlib.sha256(raw).hexdigest()==args.selection_sha256,'Exact selected cases SHA required')
    report=analyze(json.loads(raw),Reader());report['selection_sha256']=args.selection_sha256
    report['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open('x')as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'],summary=report['summary'],output=str(args.output))))
    return 0


if __name__=='__main__':raise SystemExit(main())
