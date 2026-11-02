"""One root-only seven-sample passive window; default PLAN reads nothing.

Every bounded response and receive record is sealed before classification. No
producer/control/unit/model operation, retry, favorable sample selection or
continuous-validity/causal-speed claim. The prior failed observer is preserved.
"""
import argparse
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import stat
import time
import urllib.error
import urllib.request

RUN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
ACTIVATION = RUN/'rejected-gap-healthy-activation-original01-20261018/result.json'
ACTIVATION_SHA = 'f47b861115c62a87097f6eef0750f9c07db8a6876d59c87ab0a5ff0801a19621'
PRIOR = RUN/'rejected-gap-postactivation-original-window-failure-owned-closure-root-20261018/root-explicit-original-window-failure-and-owned-release.json'
PRIOR_SHA = '33db3f35e72625c3669eb051a523a7023e9f9332adda2d834bbf47ea8adde1f1'
CLOCKS = ('frame_count','learner_frame_count','optimized_samples','training_steps')
COUNTS = ('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')
CATEGORIES = ('dqn','epsilon','expert','eval','unattributed')
MAX_BODY = 2 << 20


def require(value, message):
    if not value:raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
        mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def closed(path, expected):
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        before=os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size<=4<<20 and stat.S_IMODE(before.st_mode)==0o444
            and before.st_uid==os.getuid() and before.st_nlink==1,'Closed owned metadata required')
        raw=stream.read((4<<20)+1)
        require(identity(before)==identity(os.fstat(stream.fileno()))==identity(path.lstat()),'Metadata read race')
    require(hashlib.sha256(raw).hexdigest()==expected,'Closed metadata hash differs')
    return json.loads(raw),dict(path=str(path),sha256=expected,bytes=len(raw),identity=identity(before))


def publish(path, payload):
    raw=payload if isinstance(payload,bytes) else (json.dumps(payload,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno());info=os.fstat(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(info))


def guard_read(owner, sources):
    # Facts only: no assertion may discard an already received sample.
    facts=dict(process_starttime_ticks=None,sources={},errors=[])
    try:
        fields=(Path('/proc')/str(owner['pid'])/'stat').read_text().rsplit(')',1)[1].split()
        facts['process_starttime_ticks']=int(fields[19])
    except Exception as error:facts['errors'].append('process_read:'+type(error).__name__+':'+str(error)[:200])
    for path in sources:
        try:facts['sources'][path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except Exception as error:facts['errors'].append('source_read:'+path+':'+type(error).__name__+':'+str(error)[:200])
    return facts


def receive(endpoint, path):
    raw=b'';meta=dict(endpoint=endpoint,started_monotonic_s=time.monotonic(),started_unix_s=time.time(),
        status=None,error=None,partial=False,oversize=False,received_response=False)
    try:
        with urllib.request.urlopen('http://127.0.0.1:8771/api/'+endpoint,timeout=8) as response:
            meta.update(status=response.status,received_response=True)
            raw=response.read(MAX_BODY+1)
    except urllib.error.HTTPError as error:
        meta.update(status=error.code,received_response=True,error=type(error).__name__+':'+str(error)[:300])
        try:raw=error.read(MAX_BODY+1)
        except Exception as second:meta['body_error']=type(second).__name__+':'+str(second)[:300]
        finally:error.close()
    except Exception as error:
        meta['error']=type(error).__name__+':'+str(error)[:300]
        partial=getattr(error,'partial',b'')
        if isinstance(partial,bytes):raw=partial[:MAX_BODY+1];meta['partial']=bool(partial)
    meta.update(ended_monotonic_s=time.monotonic(),ended_unix_s=time.time(),oversize=len(raw)>MAX_BODY)
    meta['raw']=publish(path,raw)  # Before parse, identity checks or semantic classification.
    return raw,meta


def integer(value):return type(value) is int and value>=0

def finite(value):return type(value) in (int,float) and math.isfinite(value)


def classify(raw_now,raw_gaps,received,owner,sources):
    issues=[];events=[];out=dict(issues=issues,availability_events=events,clocks=None,pipeline_generation=None,
        optimizer=None,replay=None,gaps=None,now_timestamp=None,pipeline_age_s=None,owner_valid=True,owner_guard_valid=True,pipeline_available=False)
    def issue(name):issues.append(name)
    for bracket in ('guard_before','guard_after'):
        guard=received[bracket]
        if guard['errors'] or guard['process_starttime_ticks']!=owner['starttime_ticks'] or guard['sources']!=sources:
            issue(bracket+':owner_or_source_mismatch');out['owner_valid']=False;out['owner_guard_valid']=False
    parsed={}
    for name,raw in (('now',raw_now),('rejected_gaps',raw_gaps)):
        response=received[name]
        if response['error'] or response['status']!=200 or response['partial'] or response['oversize']:
            issue(name+':HTTP_or_bounded_read_failure')
        try:
            value=json.loads(raw)
            if not isinstance(value,dict):raise ValueError('object required')
            parsed[name]=value
        except Exception as error:issue(name+':decode:'+type(error).__name__)
    now=parsed.get('now',{});pipeline=now.get('host_pipeline',{})
    if not isinstance(pipeline,dict):pipeline={};issue('pipeline:missing_object')
    if now.get('client_count')!=192 or now.get('training_enabled') is not True or now.get('measurement_active') is not False or now.get('lr')!=2.5e-5:
        issue('now:192_training_recipe')
    for field in ('pipeline_read_error','bank_persistence_read_error'):
        if now.get(field):issue(field+':'+str(now[field])[:200])
    stamp=now.get('ts');age=now.get('pipeline_snapshot_age_s')
    if not finite(stamp) or not -2<=received['now']['ended_unix_s']-stamp<10:issue('now:timestamp_stale_or_invalid')
    else:out['now_timestamp']=stamp
    if not finite(age) or not 0<=age<10:issue('pipeline:age_stale_or_invalid')
    else:out['pipeline_age_s']=age
    if all(integer(now.get(k)) for k in CLOCKS):out['clocks']={k:now[k]for k in CLOCKS}
    else:issue('now:missing_or_invalid_four_clocks')
    out['pipeline_available']=pipeline.get('available') is True
    if not out['pipeline_available']:issue('pipeline:unavailable');events.append('pipeline_unavailable')
    if integer(pipeline.get('generation')):out['pipeline_generation']=pipeline['generation']
    else:issue('pipeline:generation_missing')
    for section in ('inference','actor_refresh','target_refresh','learner_priority'):
        value=pipeline.get(section,{})
        if not isinstance(value,dict) or not integer(value.get('errors')):issue('pipeline:'+section+':errors_missing')
        elif value['errors']!=0:issue('pipeline:'+section+':errors_nonzero')
    exposure=pipeline.get('learning_exposure',{})
    if not isinstance(exposure,dict):exposure={}
    for name,schema in (('optimizer','robotron-optimizer-exposure-v1'),('replay','robotron-replay-insert-exposure-v1')):
        value=exposure.get(name,{})
        if not isinstance(value,dict):value={}
        key={k:value.get(k)for k in ('process_id','instance_monotonic_ns','epoch')}
        owned=value.get('process_id')==owner['pid'] and all(integer(v)for v in key.values())
        if not owned:issue(name+':owner_or_identity_invalid');out['owner_valid']=False
        if value.get('schema')!=schema or value.get('enabled') is not True:issue(name+':schema_or_disabled')
        if name=='optimizer':
            total=value.get('total',{});current=value.get('since_epoch',{})
            good=all(isinstance(t,dict) and all(integer(t.get(k))for k in COUNTS)
                and t['outcomes_recorded']==t['applied']+t['amp_skipped']+t['unavailable'] for t in (total,current))
            pending=total['attempts_started']-total['outcomes_recorded'] if good else None
            if not good or pending<0 or value.get('unclassified_started_total')!=pending:
                issue('optimizer:counter_partition_or_pending_invalid');good=False
            if good:
                expected=current['unavailable']==0 and current['outcomes_recorded']>0 and pending==0
                if type(value.get('available')) is not bool or value['available']!=expected:issue('optimizer:available_formula_inconsistent')
                if total['unavailable'] or current['unavailable']:issue('optimizer:classified_unavailable_outcome_nonzero');events.append('optimizer_unavailable_outcomes')
                if current['outcomes_recorded']==0:issue('optimizer:no_current_epoch_outcomes');events.append('optimizer_no_outcomes')
                if pending==1 and current['unavailable']==0 and current['outcomes_recorded']>0:
                    events.append('optimizer_one_attempt_in_flight')
                elif pending!=0:issue('optimizer:pending_not_normal_one');events.append('optimizer_unknown_pending')
                out[name]=dict(identity=key,total={k:total[k]for k in COUNTS},since_epoch={k:current[k]for k in COUNTS},
                    pending=pending,available=value.get('available'),last_reason=str(value.get('last_reason'))[:160],
                    counter_valid=owned and value.get('schema')==schema and value.get('enabled') is True
                        and current['outcomes_recorded']>0 and current['unavailable']==total['unavailable']==0
                        and pending in (0,1) and value.get('available')==expected)
        else:
            counts=value.get('accepted_by_source_total',{})
            good=isinstance(counts,dict) and set(counts)==set(CATEGORIES) and all(integer(v)for v in counts.values())
            good=good and integer(value.get('accepted_total')) and integer(value.get('accepted_learner_total')) and value.get('accepted_total')==sum(counts.values()) and value.get('accepted_learner_total')==counts['dqn']+counts['epsilon']
            if not good:issue('replay:counter_partition_invalid')
            if value.get('available') is not True:issue('replay:unavailable');events.append('replay_unavailable')
            if good:out[name]=dict(identity=key,accepted_by_source_total=dict(counts),accepted_total=value['accepted_total'],
                accepted_learner_total=value['accepted_learner_total'],available=value.get('available'),counter_valid=owned and value.get('available') is True and value.get('schema')==schema and value.get('enabled') is True)
    gaps=parsed.get('rejected_gaps',{});snapshot=gaps.get('snapshot')
    if gaps.get('schema')!='robotron-rejected-gap-api-v1':issue('rejected_gaps:API_schema_invalid')
    if gaps.get('available') is not True or gaps.get('reason')!='available':issue('rejected_gaps:unavailable:'+str(gaps.get('reason'))[:80]);events.append('rejected_gaps_unavailable')
    if isinstance(snapshot,dict):
        counters=snapshot.get('counters',{})
        good=isinstance(counters,dict) and all(integer(v)for v in counters.values())
        key={k:snapshot.get(k)for k in ('process_id','instance_monotonic_ns')}
        if snapshot.get('process_id')!=owner['pid'] or not all(type(v) is int and v>0 for v in key.values()):issue('rejected_gaps:owner_identity_invalid');out['owner_valid']=False
        if snapshot.get('schema')!='robotron-rejected-gap-observation-v1':issue('rejected_gaps:snapshot_schema_invalid')
        if snapshot.get('enabled') is not True or snapshot.get('available') is not True or snapshot.get('observer_error') is not False or snapshot.get('counter_saturated') is not False:issue('rejected_gaps:disabled_or_fault')
        if snapshot.get('active_tracked_clients')!=192 or counters.get('tracking_overflow')!=0:issue('rejected_gaps:tracking_coverage_invalid')
        if good:out['gaps']=dict(identity=key,counters=dict(counters),active_tracked_clients=snapshot.get('active_tracked_clients'),
            counter_valid=gaps.get('schema')=='robotron-rejected-gap-api-v1' and gaps.get('available') is True and gaps.get('reason')=='available'
                and snapshot.get('schema')=='robotron-rejected-gap-observation-v1' and snapshot.get('process_id')==owner['pid']
                and all(type(v) is int and v>0 for v in key.values())
                and snapshot.get('enabled') is True and snapshot.get('available') is True and snapshot.get('observer_error') is False
                and snapshot.get('counter_saturated') is False and snapshot.get('active_tracked_clients')==192 and counters.get('tracking_overflow')==0)
        else:issue('rejected_gaps:counters_invalid')
    else:issue('rejected_gaps:snapshot_missing')
    return out


def rates(samples):
    result=dict(logical=None,physical_DQN_epsilon_per_s=None,optimizer_applied_per_s=None,rejected_gap_counter_deltas=None,
        unavailable_reasons=[],pending_endpoint_caveat=False)
    if len(samples)!=7:result['unavailable_reasons'].append('not_all_seven_scheduled_samples');return result
    first,last=samples[0],samples[-1];a,b=first['classification'],last['classification']
    dt=last['received']['now']['ended_monotonic_s']-first['received']['now']['ended_monotonic_s']
    common=dt>0 and all(s['classification'].get('owner_valid') and s['classification'].get('pipeline_available') for s in samples)
    common=common and all(s['received'][key]['status']==200 and not s['received'][key]['error']
        and not s['received'][key]['partial'] and not s['received'][key]['oversize']for s in samples for key in ('now',))
    common=common and a.get('pipeline_generation') is not None and all(s['classification'].get('pipeline_generation')==a['pipeline_generation']for s in samples)
    valid_clocks=common and all(s['classification'].get('clocks') is not None and s['classification'].get('now_timestamp') is not None
        and s['classification'].get('pipeline_age_s') is not None for s in samples)
    valid_clocks=valid_clocks and all(all(y['classification']['clocks'][k]>=x['classification']['clocks'][k]for k in CLOCKS)for x,y in zip(samples,samples[1:]))
    if valid_clocks:result['logical']={k:(b['clocks'][k]-a['clocks'][k])/dt for k in CLOCKS}
    else:result['unavailable_reasons'].append('full_window_owner_generation_clock_coverage_invalid')
    for name,target,field in (('optimizer','optimizer_applied_per_s','applied'),('replay','physical_DQN_epsilon_per_s','accepted_learner_total')):
        rows=[s['classification'].get(name)for s in samples]
        good=common and all(r is not None and r['counter_valid'] for r in rows)
        good=good and all(r['identity']==rows[0]['identity']for r in rows)
        good=good and not any(any(issue.startswith(name+':')for issue in s['classification']['issues'])for s in samples)
        if good:
            values=[r['total'][field]if name=='optimizer'else r[field]for r in rows]
            group='total'if name=='optimizer'else'accepted_by_source_total'
            good=all(set(y[group])==set(x[group]) and all(y[group][k]>=x[group][k]for k in x[group])for x,y in zip(rows,rows[1:]))
        if good:
            result[target]=(values[-1]-values[0])/dt
            if name=='optimizer':result['pending_endpoint_caveat']=bool(rows[0]['pending'] or rows[-1]['pending'])
        else:result['unavailable_reasons'].append(name+':full_window_same_epoch_counter_coverage_invalid')
    rows=[s['classification'].get('gaps')for s in samples]
    gap_ok=all(s['classification'].get('owner_guard_valid') and s['received']['rejected_gaps']['status']==200
        and not s['received']['rejected_gaps']['error'] and not s['received']['rejected_gaps']['partial']
        and not s['received']['rejected_gaps']['oversize'] for s in samples)
    if gap_ok and all(r is not None and r['counter_valid'] and r['identity']==rows[0]['identity'] and set(r['counters'])==set(rows[0]['counters'])for r in rows) and all(
            all(y['counters'][k]>=x['counters'][k]for k in x['counters'])for x,y in zip(rows,rows[1:])):
        result['rejected_gap_counter_deltas']={k:rows[-1]['counters'][k]-rows[0]['counters'][k]for k in rows[0]['counters']}
    else:result['unavailable_reasons'].append('rejected_gap_full_window_identity_or_counters_invalid')
    result['observed_endpoint_span_s']=dt
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--output',type=Path)
    p.add_argument('--expected-source-sha256');args=p.parse_args()
    if not args.execute:print('PLAN_ONLY: one seven-sample diagnostic window; no reads/actions');return 0
    require(args.expected_source_sha256 and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Explicit selected source SHA required')
    activation,activation_pin=closed(ACTIVATION,ACTIVATION_SHA);_,prior_pin=closed(PRIOR,PRIOR_SHA)
    require(activation['status']=='READY_HEALTHY_DIAGNOSTIC_ACTIVATION' and activation['manual_recovery_required'] is False,'Actual READY activation required')
    owner=activation['owner'];jp=activation['root_job'];job,_=closed(Path(jp['path']),jp['sha256'])
    sources={x['destination']:x['after']['sha256']for x in job['transition']['sources']}
    out=args.output;require(out is not None and out.is_absolute() and out==out.resolve(strict=False) and out.parent==RUN and not out.exists(),'NEW direct run26 output directory required')
    out.mkdir(mode=0o700);start=time.monotonic();samples=[]
    for i in range(7):
        target=start+i*20
        if time.monotonic()<target:time.sleep(target-time.monotonic())
        before=guard_read(owner,sources)
        raw_now,now=receive('now',out/('sample-%02d-now.raw.json'%i))
        raw_gaps,gaps=receive('rejected_gaps',out/('sample-%02d-rejected-gaps.raw.json'%i))
        received=dict(index=i,scheduled_monotonic_s=target,scheduled_offset_s=i*20,
            guard_before=before,guard_after=guard_read(owner,sources),now=now,rejected_gaps=gaps,classification_performed=False)
        received_pin=publish(out/('sample-%02d-received.json'%i),received)
        try:classification=classify(raw_now,raw_gaps,received,owner,sources)
        except Exception as error:classification=dict(issues=['classification_exception:'+type(error).__name__+':'+str(error)[:300]],availability_events=[],owner_valid=False)
        # Add cross-sample findings before sealing this classification.
        if samples:
            previous=samples[-1]['classification']
            for name in ('optimizer','replay','gaps'):
                a,b=previous.get(name),classification.get(name)
                if a is not None and b is not None:
                    if a['identity']!=b['identity']:classification['issues'].append(name+':identity_or_epoch_changed')
                    group='total'if name=='optimizer'else'accepted_by_source_total'if name=='replay'else'counters'
                    if set(a[group])!=set(b[group]) or any(b[group][k]<a[group][k]for k in a[group] if k in b[group]):
                        classification['issues'].append(name+':counter_schema_or_monotonicity_invalid')
            if previous.get('pipeline_generation') is not None and classification.get('pipeline_generation')!=previous['pipeline_generation']:
                classification['issues'].append('pipeline:generation_changed')
            if previous.get('clocks') is not None and classification.get('clocks') is not None and any(
                    classification['clocks'][k]<previous['clocks'][k]for k in CLOCKS):classification['issues'].append('now:four_clock_regression')
        classification_pin=publish(out/('sample-%02d-classification.json'%i),classification)
        samples.append(dict(received=received,classification=classification,received_record=received_pin,classification_record=classification_pin))
    summary=rates(samples);issues=sum(len(s['classification']['issues'])for s in samples)
    result=dict(schema='robotron-postactivation-availability-capture-v1',status='PASS_OBSERVATIONS_COMPLETE'if not issues else'OBSERVATIONS_COMPLETE_WITH_ISSUES',
        activation=activation_pin,prior_failed_observer_preserved=prior_pin,owner=owner,sources=sources,sample_count=len(samples),
        scheduled_span_s=120,interval_s=20,observed_end_monotonic_s=time.monotonic(),issue_count=issues,samples=samples,rates=summary,
        producer_changes=False,retries=0,excluded_samples=0,
        scope='Seven fixed scheduled samples; raw responses sealed before classification. Independent cached APIs are asynchronous. Pending optimizer endpoints are retained and explicitly labelled; applied means admitted calls, not parameter movement. No favorable subwindow replacement, continuous-validity or causal speed/learning claim. The original composite-assert failure has no raw response and its exact cause remains unknown.')
    publish(out/'result.json',result)
    print(json.dumps(dict(status=result['status'],sample_count=len(samples),issue_count=issues,rates=summary),allow_nan=False),flush=True)
    return 0 if not issues else 1


if __name__=='__main__':raise SystemExit(main())
