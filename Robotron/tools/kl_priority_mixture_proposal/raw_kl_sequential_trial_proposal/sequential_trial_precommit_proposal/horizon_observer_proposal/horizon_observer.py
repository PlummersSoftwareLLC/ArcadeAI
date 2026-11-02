"""Injected observational horizon decisions; no trainer/service/filesystem actions.

SOURCE PREPARATION. Root supplies bounded API/owner/evidence/clock/receipt calls.
The literal default never reads jobs or imports application/numerical modules.
"""
import copy
import json
import math

SCHEMA='robotron-raw-kl-horizon-job-v1'
OWNER_KEYS={'pid','starttime_ticks','unit','invocation_id','cgroup'}
IDENTITY=('process_id','instance_monotonic_ns','epoch','epoch_reason')
COUNTERS=('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')
CATEGORIES=('dqn','epsilon','expert','eval','unattributed')
CLOCKS=('training_steps','optimized_samples','frame_count','learner_frame_count')
POLICY=dict(learner_frames=8000000,physical_adds=6000000,cutoff_s=3240,ceiling_s=3600,
            poll_s=1,API_age_s=5,pipeline_age_s=5,unobservable_s=30,no_applied_s=60)


def require(value,message):
    if not value:raise ValueError(message)


def integer(value,name):
    require(type(value) is int and value>=0,'Invalid nonnegative integer: '+name)
    return value


def number(value,name):
    require(type(value) in (int,float) and math.isfinite(value),'Invalid finite number: '+name)
    return float(value)


def bounded(value,limit):
    # API's unrelated grad_norm can contain NaN on a known AMP skip. Required
    # counters/timestamps are validated independently; do not turn NaN into0.
    require(len(json.dumps(value,allow_nan=True,separators=(',',':')).encode())<=limit,
            'Observation exceeds bounded JSON size')
    return copy.deepcopy(value)


def identity(value):
    require(isinstance(value,dict),'Missing exposure identity')
    result={key:value[key] for key in IDENTITY}
    require(integer(result['process_id'],'process_id')>0 and
            integer(result['instance_monotonic_ns'],'instance_monotonic_ns')>0 and
            type(result['epoch_reason']) is str and 0<len(result['epoch_reason'])<=80,'Bad exposure identity')
    integer(result['epoch'],'epoch')
    return result


def normalise(api):
    require(isinstance(api,dict),'API is not an object')
    clocks={key:integer(api[key],key) for key in CLOCKS}
    exposure=api['host_pipeline']['learning_exposure']
    optimizer=exposure['optimizer'];replay=exposure['replay']
    require(optimizer['schema']=='robotron-optimizer-exposure-v1' and optimizer['enabled'] is True and
            replay['schema']=='robotron-replay-insert-exposure-v1' and replay['enabled'] is True and
            replay['available'] is True and type(optimizer['available']) is bool,'Exposure schema/availability differs')
    counts={key:integer(optimizer['total'][key],'optimizer.'+key) for key in COUNTERS}
    epoch_counts={key:integer(optimizer['since_epoch'][key],'optimizer.since_epoch.'+key) for key in COUNTERS}
    unfinished=integer(optimizer['unclassified_started_total'],'unclassified')
    require(counts['outcomes_recorded']==sum(counts[key] for key in ('applied','amp_skipped','unavailable')) and
            counts['attempts_started']-counts['outcomes_recorded']==unfinished and unfinished in (0,1),
            'Internal optimizer outcome partition/inflight differs')
    require(epoch_counts['outcomes_recorded']==sum(epoch_counts[key] for key in ('applied','amp_skipped','unavailable')) and
            all(epoch_counts[key]<=counts[key] for key in COUNTERS), 'Epoch optimizer partition differs')
    require(optimizer['available'] is (epoch_counts['outcomes_recorded']>0 and epoch_counts['unavailable']==0 and unfinished==0),
            'Optimizer available flag disagrees with its atomic counters')
    categories={key:integer(replay['accepted_by_source_total'][key],'accepted.'+key) for key in CATEGORIES}
    total=integer(replay['accepted_total'],'accepted_total')
    learner=integer(replay['accepted_learner_total'],'accepted_learner_total')
    require(total==sum(categories.values()) and learner==categories['dqn']+categories['epsilon'],
            'Physical and learner insertion partitions differ')
    return dict(clocks=clocks,optimizer_identity=identity(optimizer),replay_identity=identity(replay),
        optimizer=counts,optimizer_since_epoch=epoch_counts,unclassified=unfinished,
        accepted=total,learner_accepted=learner,categories=categories)


def validate_job(job):
    require(job['schema']==SCHEMA and job['policy']==POLICY,'Frozen observer policy differs')
    require(set(job['owner'])==OWNER_KEYS and integer(job['owner']['pid'],'owner.pid')>0 and
            integer(job['owner']['starttime_ticks'],'owner.start')>0,'Exact owned trainer fields required')
    for key in ('unit','invocation_id','cgroup'):
        require(type(job['owner'][key]) is str and job['owner'][key],'Missing owned field: '+key)
    start=job['start_request']
    require(type(start['boot_id']) is str and start['boot_id'],'Missing boot identity')
    number(start['monotonic_s'],'start monotonic')
    require(number(job['healthy192_monotonic_s'],'healthy time')>=start['monotonic_s'],'Healthy time precedes start')
    require(all(integer(job['boot_four_clocks'][key],key)>0 for key in CLOCKS),'Missing actual saved boot clocks')
    for key in ('trial_core_sha256','activation_receipt_sha256'):
        value=job[key]
        require(type(value) is str and len(value)==64 and all(ch in '0123456789abcdef' for ch in value),
                'Missing actual immutable binding: '+key)
    baseline=normalise(job['before_resume_api'])
    require(baseline['accepted']==0 and baseline['learner_accepted']==0 and
            all(baseline['clocks'][key]>=job['boot_four_clocks'][key] for key in CLOCKS) and
            baseline['optimizer']['unavailable']==0,'Startup exposure/floor does not join actual fresh load')
    require(baseline['optimizer_identity']['process_id']==baseline['replay_identity']['process_id']==job['owner']['pid'],
            'Exposure belongs to another process')
    return bounded(job,2<<20),baseline


class HorizonObserver:
    def __init__(self,job):
        self.job,self.baseline=validate_job(job)
        self.last=copy.deepcopy(self.baseline)
        self.terminal=None;self.first_observation=None;self.last_observation=None
        self.current_raw=None
        self.missing_since=None;self.last_now=None
        self.last_applied_s=self.job['healthy192_monotonic_s']
        self.applied_anchor=copy.deepcopy(self.baseline)

    def _event(self,state,reason,now,**fields):
        # Clock validation can itself be the failure. Preserve that failure
        # without inventing an observation time or raising again while reporting.
        mono=now.get('monotonic_s') if isinstance(now,dict) else None
        verified_time=type(mono) in (int,float) and math.isfinite(mono)
        result=dict(schema='robotron-raw-kl-horizon-observation-v1',state=state,reason=reason,
            elapsed_s=mono-self.job['start_request']['monotonic_s'] if verified_time else None,
            observed_monotonic_s=mono if verified_time else None,
            boot_id=now.get('boot_id') if isinstance(now,dict) else None,
            qualification_pass=False,**fields)
        if state not in ('CONTINUE','LATCH'):
            result['terminal_observation']=copy.deepcopy(self.current_raw)
            if self.current_raw is None:result['last_valid_observation']=copy.deepcopy(self.last_observation)
        if state!='CONTINUE':self.terminal=copy.deepcopy(result)
        return result

    def _clock(self,now):
        require(isinstance(now,dict),'Missing observation clock')
        number(now['monotonic_s'],'observation monotonic');number(now['wall_s'],'observation wall')
        require(now['boot_id']==self.job['start_request']['boot_id'],'Boot identity changed')
        require(now['monotonic_s']>=self.job['healthy192_monotonic_s'] and
                (self.last_now is None or now['monotonic_s']>=self.last_now),'Observer monotonic clock regressed')
        anchor=self.job['healthy192_monotonic_s'] if self.last_now is None else self.last_now
        require(now['monotonic_s']-anchor<POLICY['unobservable_s'],
                'First observation or poll gap reached fixed unobservable grace')
        self.last_now=now['monotonic_s']

    def observe(self,api,owner,evidence,now):
        if self.terminal is not None:return copy.deepcopy(self.terminal)
        self.current_raw=None
        try:
            self._clock(now)
            require(owner==self.job['owner'],'Owned trainer changed or absent during active trial')
            require(isinstance(evidence,dict) and evidence.get('ok') is True,'Root ownership/source/journal/fleet evidence failed')
            bounded(evidence,65536)
            return self._observe_api(api,now)
        except (KeyError,TypeError,ValueError,OverflowError) as error:
            return self._event('INVALID',str(error)[:512],now,manual_recovery_required=True)

    def _observe_api(self,api,now):
        elapsed=now['monotonic_s']-self.job['start_request']['monotonic_s']
        fresh=api is not None
        if fresh:
            self.current_raw=bounded(api,2<<20)
            age=now['wall_s']-number(api['ts'],'API timestamp')
            pipeline_age=number(api['pipeline_snapshot_age_s'],'pipeline age')
            require(age>=0 and pipeline_age>=0,'Future API timestamp or negative pipeline age')
            fresh=age<=POLICY['API_age_s'] and pipeline_age<=POLICY['pipeline_age_s'] and not api['pipeline_read_error']
        current=normalise(api) if fresh else None
        if current is not None:
            for key in ('optimizer_identity','replay_identity'):
                require(current[key]==self.baseline[key],'Exposure identity/epoch changed: '+key)
            for group in ('clocks','optimizer','optimizer_since_epoch','categories'):
                require(all(current[group][key]>=self.last[group][key] for key in self.last[group]),
                        'Counter regressed: '+group)
            require(current['optimizer']['unavailable']==0,'Classified unavailable optimizer outcome increased')
        if elapsed>=POLICY['ceiling_s']:
            return self._event('INVALID','KL owner at or beyond fixed ceiling',now,manual_recovery_required=True)
        if elapsed>POLICY['cutoff_s']:
            return self._event('INCOMPLETE','Horizon not observed by fixed cutoff',now)
        if current is None:
            if self.missing_since is None:self.missing_since=now['monotonic_s']
            if now['monotonic_s']-self.missing_since>=POLICY['unobservable_s']:
                return self._event('INVALID','Observation missing/stale for fixed grace',now,manual_recovery_required=True)
            if elapsed==POLICY['cutoff_s']:return self._event('INCOMPLETE','No fresh eligible observation at cutoff',now)
            return self._event('CONTINUE','Missing/stale observation inside bounded grace',now,progress=None)
        self.missing_since=None
        progress=dict(learner_frames=current['clocks']['learner_frame_count']-self.job['boot_four_clocks']['learner_frame_count'],
            physical_accepted=current['accepted']-self.baseline['accepted'],
            learner_accepted=current['learner_accepted']-self.baseline['learner_accepted'],
            logical_steps=current['clocks']['training_steps']-self.job['boot_four_clocks']['training_steps'],
            logical_samples=current['clocks']['optimized_samples']-self.job['boot_four_clocks']['optimized_samples'],
            optimizer_total=current['optimizer'],
            optimizer_delta_since_pre_resume={key:current['optimizer'][key]-self.baseline['optimizer'][key] for key in COUNTERS},
            admitted_samples_total=current['optimizer']['applied']*4096,
            admitted_samples_scope='Process-local admitted4096 batches; not per-parameter movement')
        if current['optimizer']['applied']>self.last['optimizer']['applied']:
            self.last_applied_s=now['monotonic_s'];self.applied_anchor=copy.deepcopy(current)
        stalled=(now['monotonic_s']-self.last_applied_s>=POLICY['no_applied_s'] and
            current['clocks']['learner_frame_count']>self.applied_anchor['clocks']['learner_frame_count'] and
            current['accepted']>self.applied_anchor['accepted'])
        self.last=copy.deepcopy(current)
        self.last_observation=bounded(api,2<<20)
        if self.first_observation is None:self.first_observation=copy.deepcopy(self.last_observation)
        if stalled:return self._event('INVALID','Frames/adds advance without applied admission for fixed interval',now,
                                      progress=progress,manual_recovery_required=True)
        if progress['learner_frames']>=POLICY['learner_frames'] and progress['physical_accepted']>=POLICY['physical_adds']:
            return self._event('LATCH','First fresh BOTH-horizon observation',now,progress=progress,
                first_eligible_observation=copy.deepcopy(self.last_observation),candidate_requests_allowed=1,
                root_next='Owned pause/unique save/stop/newest-state CE return; helper performs no actions')
        if elapsed==POLICY['cutoff_s']:return self._event('INCOMPLETE','Both horizons absent at cutoff',now,progress=progress)
        return self._event('CONTINUE','Both horizons not yet reached',now,progress=progress)


def poll(job,*,get_api,get_owner,get_evidence,get_clock,sleep,emit):
    """Bounded observer; callback I/O/action ownership remains with root.

    Callbacks must have their own short timeouts. emit is append-only/create-only
    and must durably record LATCH before returning; an emit error propagates, so
    root must stop/recover rather than reinstantiate to seek another candidate.
    API read exceptions become missing observations. Other callback failures are
    INVALID evidence. KeyboardInterrupt/SystemExit propagate to root cleanup.
    """
    observer=HorizonObserver(job)
    for sequence in range(3602):
        now=get_clock()
        try:owner=get_owner();evidence=get_evidence()
        except Exception as error:owner=None;evidence=dict(ok=False,error=str(error)[:512])
        try:api=get_api()
        except Exception:api=None
        now=get_clock()  # Timestamp AFTER callback work; never claim future API data.
        event=observer.observe(api,owner,evidence,now)
        event['sequence']=sequence
        emit(copy.deepcopy(event))
        if event['state']!='CONTINUE':return event
        sleep(POLICY['poll_s'])
    event=observer._event('INVALID','Fixed poll receipt budget exhausted',get_clock(),manual_recovery_required=True)
    emit(event);return event


def ending_deadline(job,now,*,KL_owner_present):
    """Pure follow-up; root separately proves exact absence/handles recovery.

    This never overwrites the immutable candidate latch or grants a new one.
    """
    require(type(KL_owner_present) is bool,'Root must supply observed owner-presence classification')
    require(now['boot_id']==job['start_request']['boot_id'],'Boot changed during ending')
    elapsed=number(now['monotonic_s'],'ending time')-number(job['start_request']['monotonic_s'],'start time')
    return dict(state='INVALID' if KL_owner_present and elapsed>=POLICY['ceiling_s'] else 'ROOT_ENDING_PROOF_REQUIRED',
        KL_owner_present=KL_owner_present,elapsed_s=elapsed,qualification_pass=False,
        reason='Ceiling breach/manual' if KL_owner_present and elapsed>=POLICY['ceiling_s'] else
               'Root must prove retirement/newest CPU/explicit CE return; no helper action')


def main():
    print(json.dumps(dict(status='PLAN_ONLY',schema=SCHEMA,policy=POLICY,actions=False,
        API_or_owner_reads=False,output_writes=False,qualification_pass=False),sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
