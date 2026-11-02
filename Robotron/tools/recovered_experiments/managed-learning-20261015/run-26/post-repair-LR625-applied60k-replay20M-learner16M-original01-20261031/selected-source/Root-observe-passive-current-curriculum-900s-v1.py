"""Root-only passive curriculum projections:21 starts45s apart; default inert.
Only ordinary cached API and fresh connection metadata; no controls/actions.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
import urllib.request
CASE=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-repair-LR625-applied60k-replay20M-learner16M-original01-20261031')
OUTPUT=CASE/'current-curriculum-passive-observations-original01'
STAMP=dict(pid=1644742,birth=36415496,source_sha256='1692ee2dbfb6f83d0f50234ee1eb30d0cf6bbe45d670a5a9fb52992fd92b56fc')
CONTROL='3b1a46f7de088698487877ff30171f7dbe1c9d289f39778065a16e85b48a5521'
IDS=('process_id','instance_monotonic_ns','epoch','epoch_reason')
EXPECTED={'optimizer':(1644742,364158651613186,1,'optimizer_restore_begin'),'replay':(1644742,364159801033522,1,'directory_adopt_begin')}
ROW=('client_id','client_slot','eval','level','score','lives','fps','session_seconds','connected_seconds')
CONNECTION=('client_id','client_slot','token','eval_only','connection_ns')
API=('ts','frame_count','learner_frame_count','training_steps','optimized_samples','fps','client_count','cpu_util','cpu_load_1m','cpu_load_5m','cpu_load_15m','gpu0_util','gpu1_util','gpu0_power_w','gpu1_power_w','train_gpu_compute_ms','train_gpu_compute_diagnostic','episodes_this_run','eplen_1m','eplen_100k','average_level','sample_dqn_frac','sample_epsilon_frac','sample_expert_frac','eval_life_score','eval_life_count','lr','epsilon','expert_ratio')


def require(value,reason):
    if not value:raise ValueError(reason)


def write(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))


def get(route):
    began=time.monotonic_ns()
    with urllib.request.urlopen('http://127.0.0.1:8771/api/'+route,timeout=3)as f:raw=f.read((2<<20)+1)
    ended=time.monotonic_ns();require(len(raw)<=2<<20,'API exceeds2MiB bound')
    data=json.loads(raw);require(type(data)is dict,'API object required');return data,began,ended


def projection(index,api,connections,began,ended):
    now=time.time()
    require(connections.get('schema')=='robotron-continuous-active-connections-v1'
        and connections.get('server_stamp')==STAMP,'Original Main owner/source/schema changed')
    require(type(connections.get('observed_monotonic_ns'))is int
        and began<=connections['observed_monotonic_ns']<=ended,'Connection metadata is not fresh')
    require(type(api.get('ts'))in(int,float)and math.isfinite(api['ts'])and 0<=now-api['ts']<=10,'Ordinary API is stale/invalid')
    exposure=api['host_pipeline']['learning_exposure'];opt=exposure['optimizer'];replay=exposure['replay']
    require(all(tuple(exposure[k][n]for n in IDS)==EXPECTED[k]for k in EXPECTED),'Exposure owner/epoch changed')
    total=opt['total'];names=('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')
    require(opt['schema']=='robotron-optimizer-exposure-v1'and replay['schema']=='robotron-replay-insert-exposure-v1'
        and opt['enabled']is replay['enabled']is replay['available']is True,'Exposure schema/availability changed')
    require(all(type(total[k])is int and total[k]>=0 for k in names),'Invalid optimizer counters')
    pending=total['attempts_started']-total['outcomes_recorded']
    require(total['outcomes_recorded']==total['applied']+total['amp_skipped']+total['unavailable']
        and pending in(0,1)and opt['unclassified_started_total']==pending
        and opt['available']is(pending==0),'Invalid settled/inflight optimizer accounting')
    sources=replay['accepted_by_source_total'];require(set(sources)=={'dqn','epsilon','expert','eval','unattributed'}
        and all(type(v)is int and v>=0 for v in sources.values())
        and sum(sources.values())==replay['accepted_total']
        and sources['dqn']+sources['epsilon']==replay['accepted_learner_total'],'Replay source accounting invalid')
    require(type(api['client_rows'])is list and type(connections['connections'])is list,'Client/connection schema changed')
    rows=[{k:r[k]for k in ROW}for r in api['client_rows']]
    conns=[{k:r[k]for k in CONNECTION}for r in connections['connections']]
    require(all(type(r['eval'])is bool and type(r['client_id'])is int and type(r['client_slot'])is int for r in rows)
        and all(type(r['eval_only'])is bool and type(r['token'])is str for r in conns),'Invalid row role/identity types')
    left=[(r['client_id'],r['client_slot'],r['eval'])for r in rows]
    right=[(r['client_id'],r['client_slot'],r['eval_only'])for r in conns]
    mismatch=dict(API_only=sorted(set(left)-set(right)),connections_only=sorted(set(right)-set(left)),
        duplicate_API_keys=len(left)-len(set(left)),duplicate_connection_keys=len(right)-len(set(right)))
    value=dict(schema='robotron-Root-passive-current-curriculum-projection-v1',index=index,observed_unix_s=now,
        server_stamp=connections['server_stamp'],selected_control_sha256_CONTEXT_ONLY_NOT_REHASHED=CONTROL,
        API_fields={k:api.get(k)for k in API},client_rows=rows,connections=conns,
        exposure={k:{n:exposure[k][n]for n in IDS}for k in EXPECTED},optimizer_totals=total,
        optimizer_pending=pending,replay_accepted_total=replay['accepted_total'],
        replay_accepted_learner_total=replay['accepted_learner_total'],replay_accepted_by_source_total=sources,
        connection_policy={k:connections.get(k)for k in ('observed_unix_s','observed_monotonic_ns','measurement_generation','continuous_training_mode','measurement_active','training_enabled','replay_admission_open','consumer_error')},
        nonatomic_identity_diagnostic=mismatch,scope='Cached rows and fresh connections are not atomic. No game-age, replay-wave-distribution, original-actor-census, dose or quality qualification.')
    table=dict(index=index,observed_unix_s=now,API_ts=api['ts'],row_count=len(rows),connection_count=len(conns),
        row_connection_mismatch_count=len(mismatch['API_only'])+len(mismatch['connections_only']),
        optimizer_pending=pending,applied=total['applied'],attempts=total['attempts_started'],
        AMP_skipped=total['amp_skipped'],unavailable=total['unavailable'],replay_accepted=replay['accepted_total'],
        replay_learner=replay['accepted_learner_total'],learner_frames=api.get('learner_frame_count'),fps=api.get('fps'),
        episodes_this_run=api.get('episodes_this_run'),eplen_1m=api.get('eplen_1m'),eplen_100k=api.get('eplen_100k'))
    for name,count in sources.items():table['accepted_'+name]=count
    for flag,label in((False,'TRAIN'),(True,'EVAL')):
        role=[r for r in rows if r['eval']is flag];table[label+'_count']=len(role)
        for name,predicate in(('le25',lambda v:v<=25),('le75',lambda v:v<=75),('gt75',lambda v:v>75),('gt81',lambda v:v>81)):
            table[label+'_level_'+name]=sum(predicate(r['level'])for r in role)
        for name in('level','score','lives','fps'):table[label+'_'+name+'_median']=statistics.median(r[name]for r in role)if role else None
    return value,table


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY_NO_READS_OR_ACTIONS');return 0
    own=Path(__file__).resolve();raw=own.read_bytes();require(hashlib.sha256(raw).hexdigest()==a.expected_source_sha256
        and own.stat().st_mode&0o777==0o444,'Exact frozen observer required')
    require(OUTPUT.resolve()==OUTPUT and not OUTPUT.exists(),'Fresh original output required');OUTPUT.mkdir(mode=0o700)
    birth=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]);started=time.monotonic()
    write(OUTPUT/'owner.json',dict(pid=os.getpid(),birth=birth,source=dict(path=str(own),sha256=a.expected_source_sha256),
        started_unix_s=time.time(),polls=21,interval_s=45,scheduled_span_s=900,final_settle_limit_s=10,expected_Main=STAMP,
        selected_control_sha256_CONTEXT_ONLY_NOT_REHASHED=CONTROL,CONTROL_PUBLIC_actions_or_direct_model_replay_GPU_access=False))
    records=0;code=0;error=None;last=None
    try:
        for index in range(21):
            delay=started+45*index-time.monotonic()
            if delay>0:time.sleep(delay)
            require(time.monotonic()-started<=910,'Observation budget expired')
            api,_,_=get('now');connections,began,ended=get('continuous_training_connections')
            value,table=projection(index,api,connections,began,ended)
            require(time.monotonic()-started<=910,'Final bounded observation exceeded budget')
            last=write(OUTPUT/f'{index:03d}-projection.json',value)
            with(OUTPUT/'curriculum.csv').open('a',newline='')as f:
                writer=csv.DictWriter(f,fieldnames=list(table))
                if not records:writer.writeheader()
                writer.writerow(table);f.flush();os.fsync(f.fileno())
            records+=1;print(json.dumps(table,allow_nan=False),flush=True)
    except Exception as exc:code=1;error=repr(exc)
    write(OUTPUT/'result.json',dict(actual_exit=code,pid=os.getpid(),birth=birth,records=records,
        duration_s=time.monotonic()-started,ended_unix_s=time.time(),error=error,last_projection=last,
        completed_all21=records==21,no_retry_or_restart=True,quality_or_dose_qualified=False,Main_or_control_actions=False))
    return code


if __name__=='__main__':raise SystemExit(main())
