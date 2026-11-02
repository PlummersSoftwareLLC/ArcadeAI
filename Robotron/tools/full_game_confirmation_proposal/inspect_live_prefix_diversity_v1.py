"""Bounded read-only comparison of aligned actual-play prefixes.

Different identities and wall clocks do not count as game diversity. Distinct
trajectories would still not prove statistical independence. The selected
scientific reviewers and acceptance rules are not changed by this observation.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
FIELDS=('game_score','level_number','lives','player_alive','num_lasers')


def require(value,message):
    if not value:raise ValueError(message)


def inspect(path,slot,job,samples=200):
    source_hash=hashlib.sha256();payload_hash=hashlib.sha256();action_hash=hashlib.sha256()
    states=[];first=None;sequences=[];read_bytes=0
    with path.open('rb')as stream:
        identity=os.fstat(stream.fileno())
        for line_index in range(4000):
            line=stream.readline(1<<20);read_bytes+=len(line)
            require(read_bytes<=64<<20,'Bounded prefix byte limit exceeded')
            require(line.endswith(b'\n'),'Prefix not yet fully available or row exceeds limit')
            source_hash.update(line);row=json.loads(line)
            if line_index==0:
                require(row['subject']==dict(slot=slot,session=job['sessions'][str(slot)],
                    connection=job['connections'][str(slot)]),'Foreign original transport subject')
            if row.get('kind')!='origin_exchange':continue
            metadata=row['metadata'];start=metadata['first_play_sequence']
            require(type(start)is int and type(metadata['sequence'])is int,'Untyped frame clock')
            # -1 is the explicit pre-play sentinel. Never hash boot rows as play.
            if start<=0 or metadata['sequence']<start:continue
            if first is None:first=start
            require(start==first and metadata['sequence']==first+len(states)
                and row['sequence']==metadata['sequence'],'Noncontiguous aligned play prefix')
            states.append({stage:{key:row[stage][key]for key in FIELDS}for stage in ('before','after')})
            sequences.append(row['sequence'])
            # Exact original observation bytes, without transport subject/time.
            for digest,key in ((payload_hash,'original_payload_hex'),(action_hash,'actual_action_hex')):
                value=bytes.fromhex(row[key]);digest.update(len(value).to_bytes(8,'big'));digest.update(value)
            if len(states)==samples:break
        require(len(states)==samples,'All declared actual-play samples required')
        current=path.stat();end=os.fstat(stream.fileno())
        require((identity.st_dev,identity.st_ino)==(end.st_dev,end.st_ino)==(current.st_dev,current.st_ino)
            and end.st_size>=read_bytes,'Live original file was replaced or shortened')
    return dict(slot=slot,source_path=str(path),source_device=identity.st_dev,source_inode=identity.st_ino,
        inspected_prefix_bytes=read_bytes,inspected_prefix_sha256=source_hash.hexdigest(),
        first_play_sequence=first,first_sequence=sequences[0],last_sequence=sequences[-1],samples=samples,
        state_fields=list(FIELDS),state_sha256=hashlib.sha256(json.dumps(states,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        observation_sha256=payload_hash.hexdigest(),action_sha256=action_hash.hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('_live_diversity_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    jp=h.pin(args.job);job=json.loads(h.checked(jp).read_text())
    require(job['actor_slots']==list(range(4096,4128)),'Exact original32 required')
    actors=Path(job['output'])/'actors'
    rows=[inspect(actors/str(slot)/'proxy.jsonl',slot,job)for slot in job['actor_slots']]
    groups={}
    for key in ('state_sha256','observation_sha256','action_sha256'):
        grouped={}
        for row in rows:grouped.setdefault(row[key],[]).append(row['slot'])
        groups[key]=list(grouped.values())
    report=h.put(args.output,dict(status='OBSERVED_ALIGNED_LIVE_PREFIX_DIVERSITY',observed_unix_s=time.time(),
        job=jp,source=h.pin(__file__),policy_sha256=job['checkpoint']['sha256'],samples_per_slot=200,
        original_slots=32,rows=rows,groups=groups,distinct_sequences={key:len(value)for key,value in groups.items()},
        source_files_live_not_sealed=True,raw_prefix_replay_possible_from_future_sealed_original=True,
        equal_prefix_does_not_prove_equal_full_games=True,distinct_prefix_does_not_prove_independence=True,
        no_effective_sample_size_or_population_confidence_established=True,
        acceptance_rules_or_running_jobs_changed=False,promotion=False))
    print(json.dumps(dict(report=report,distinct_sequences={key:len(value)for key,value in groups.items()})),flush=True)


if __name__=='__main__':main()
