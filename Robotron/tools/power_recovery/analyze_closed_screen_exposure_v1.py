"""Recompute closed frozen-screen scores and exposure; no runtime imports.

This analysis follows immutable seals and existing metadata reviews. It does
not qualify raw gameplay, infer a causal learning-rate effect, or promote a
policy. It keeps every candidate/reference pair separate.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import statistics
import time

SLOTS=list(range(4096,4128))
REFERENCE='06558cbc185b76b2b44229ddfe469d2a92037e70f89de2481e8fb055f2c736ad'
HORIZON=3_600_000_000_000


def require(value,message):
    if not value:raise ValueError(message)


def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)),uid=info.st_uid,nlink=info.st_nlink)


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate JSON key')
            result[key]=value
        return result
    def bad_constant(value):raise ValueError('Nonfinite JSON constant: '+value)
    def floating(value):
        result=float(value);require(math.isfinite(result),'Nonfinite JSON number');return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad_constant,parse_float=floating)


class Reader:
    def __init__(self):self.inventory={}

    def read(self,pin):
        path=Path(pin['path']);require(path.is_absolute() and path.resolve(strict=True)==path,'Canonical input required')
        before=path.lstat()
        require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o444
            and before.st_uid==os.getuid() and before.st_nlink==1 and 0<before.st_size<=4<<20,
            'Bounded immutable owned metadata required')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as stream:
            raw=stream.read((4<<20)+1);after=os.fstat(stream.fileno())
        actual=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))
        require(identity(before)==identity(after)==identity(path.lstat()),'Input changed during read')
        require(all(actual[k]==pin[k] for k in ('path','sha256','bytes'))
            and all(actual['identity'][k]==v for k,v in pin.get('identity',{}).items()),'Input pin changed')
        self.inventory[str(path)]=actual
        return strict_json(raw)


def summarize(seal):
    rows=seal['rows']
    require(seal['horizon_ns']==HORIZON and len(rows)==seal['n_scored']==32
        and [r['slot'] for r in rows]==SLOTS,'All32 original slots and common one-hour horizon required')
    require(seal['fixed_denominator_valid'] is True
        and seal['full_game_quality_qualified'] is seal['improvement_qualified'] is False,
        'Exploratory scope required')
    for row in rows:
        for key in ('score_at_deadline','score_at_anchor','selected_first_game_accepted_frame_exposure','accepted_frame_exposure'):
            require(type(row[key]) is int and row[key]>=0,'Exact nonnegative integer score/exposure required')
        require(row['score_at_deadline']>=row['score_at_anchor'],'First-game score regressed')
        require(row['status'] in ('completed','censored'),'Original completion category required')
    scores=[r['score_at_deadline'] for r in rows]
    gain=sum(r['score_at_deadline']-r['score_at_anchor'] for r in rows)
    frames=sum(r['selected_first_game_accepted_frame_exposure'] for r in rows)
    completed=sum(r['status']=='completed' for r in rows)
    require(sum(scores)==seal['score_sum'] and statistics.mean(scores)==seal['mean_score']
        and statistics.median(scores)==seal['median_score'] and gain==seal['score_gain_since_anchor']
        and frames==seal['selected_first_game_accepted_frame_exposure']>0
        and sum(r['accepted_frame_exposure'] for r in rows)==seal['accepted_frame_exposure']
        and completed==seal['n_completed'] and 32-completed==seal['n_censored'],
        'Independent score/count/exposure arithmetic differs')
    return dict(policy_sha256=seal['policy']['policy_sha256'],n_scored=32,
        n_completed=completed,n_censored=32-completed,mean=statistics.mean(scores),
        median=statistics.median(scores),score_sum=sum(scores),score_gain_since_anchor=gain,
        first_game_frame_exposure=frames,first_game_frames_per_second=frames/3600,
        points_per_accepted_first_game_frame=gain/frames,
        anchor_monotonic_ns=seal['anchor_monotonic_ns'],deadline_monotonic_ns=seal['deadline_monotonic_ns'])


def analyze(selection,reader):
    require(selection['schema']=='robotron-closed-screen-exposure-analysis-selection-v1'
        and selection['promotion'] is False,'Explicit analysis-only selection required')
    results=[]
    for subject in selection['cases']:
        outer=reader.read(subject['outer_result'])
        require(type(outer['actual_exit']) is int and outer['actual_exit']==0
            and outer['error'] is None and outer['reporter_thread_closed'] is True
            and outer['legs']==['R1','C1'] and outer['native_or_original_controller_retried'] is False,
            'Original clean paired result required')
        arms={}
        for leg in ('R1','C1'):
            item=subject['arms'][leg];closed=reader.read(item['closed_scores']);native=reader.read(item['native_result'])
            seal=reader.read(native['deadline_score_seal'])
            require(closed['score_seal']==seal and native['complete'] is True and native['errors']==[]
                and native['all_original_threads_stopped'] is native['original_lease_released'] is True,
                'Exact closed native score seal required')
            require(closed['original_controller']['original_exit']==0
                and closed['original_controller']['unit_released'] is True,
                'Original controller closure required')
            arms[leg]=summarize(seal)
        reference,candidate=arms['R1'],arms['C1']
        require(reference['policy_sha256']==REFERENCE
            and candidate['policy_sha256']==subject['candidate_sha256']!=REFERENCE
            and reference['deadline_monotonic_ns']<candidate['anchor_monotonic_ns'],
            'Selected frozen policies and serial original arms required')
        require(outer['comparison']['reference_mean']==reference['mean']
            and outer['comparison']['candidate_mean']==candidate['mean'],'Outer summary join differs')
        metadata=None
        if subject.get('existing_metadata_review') is not None:
            metadata=reader.read(subject['existing_metadata_review'])
            require(metadata['status']=='PASS_CLOSED_METADATA_AND_ALL64_SCORE_ARITHMETIC'
                and metadata['reference']['mean']==reference['mean']
                and metadata['candidate']['mean']==candidate['mean']
                and metadata['reference']['first_game_frame_exposure']==reference['first_game_frame_exposure']
                and metadata['candidate']['first_game_frame_exposure']==candidate['first_game_frame_exposure'],
                'Existing independent metadata comparison differs')
        results.append(dict(case=subject['case'],reference=reference,candidate=candidate,
            mean_change=candidate['mean']/reference['mean']-1,
            median_change=candidate['median']/reference['median']-1,
            first_game_frame_change=candidate['first_game_frame_exposure']/reference['first_game_frame_exposure']-1,
            points_per_first_game_frame_change=candidate['points_per_accepted_first_game_frame']/reference['points_per_accepted_first_game_frame']-1,
            prior_metadata_review=subject.get('existing_metadata_review'),raw_gameplay_independently_requalified=False))
    return dict(schema='robotron-closed-screen-exposure-analysis-v1',status='PASS_RECOMPUTED_ALL_SEPARATE_PAIRS',
        observed_unix_s=time.time(),pairs=results,inventory=list(reader.inventory.values()),
        pooled_candidate_or_reference_scores=False,full_game_quality_qualified=False,promotion=False,
        interpretation='Descriptive cutoff scores and exposure. Serial screens and continuing training do not isolate a causal learning-rate or expert-fraction effect. Points/frame is diagnostic, not the promotion metric.',
        next_experiment_direction='Keep the current LR6.25e-6/expert10% recipe through the bound comparison. Higher LR9.375e-6 and expert5% screens provide no reason to repeat those changes now. After actual current R1/C1 closure and independent review, prioritize fresh complete-game confirmation against protected b231 when warranted; no promotion from cutoff scores.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--selection',type=Path)
    parser.add_argument('--selection-sha256');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    raw=args.selection.read_bytes();require(hashlib.sha256(raw).hexdigest()==args.selection_sha256,'Exact input selection SHA required')
    reader=Reader();report=analyze(strict_json(raw),reader)
    report['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['selection_sha256']=args.selection_sha256
    with args.output.open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'],pairs=len(report['pairs']),output=str(args.output))))
    return 0


if __name__=='__main__':raise SystemExit(main())
