"""Pure future post-diagnostic CE4096 observations; root owns every I/O callback.

UNSELECTED SOURCE PREPARATION. No reads, control, owner, trainer or file actions.
Root authenticates the actual READY/closure/current phase and raw B before use.
NEW prospective horizons: 8M learner frames AND 8M accepted DQN+epsilon inserts.
Only timely original durable first-LATCH evidence permits one model-only request.
"""
import copy
import hashlib
import json
import math

SCHEMA='robotron-postdiagnostic-live8M-window-job-v1'
OBSERVATION_SCHEMA='robotron-postdiagnostic-live8M-window-observation-v1'
BATCH_SIZE=4096
RECIPE=dict(priority_metric='ce',batch_size=4096,learning_control_lr_scale=0.5,
            scheduled_lr=2.5e-5,max_samples_per_frame=8)
OWNER_KEYS={'pid','starttime_ticks','unit','invocation_id','cgroup'}
IDENTITY=('process_id','instance_monotonic_ns','epoch','epoch_reason')
COUNTERS=('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')
CATEGORIES=('dqn','epsilon','expert','eval','unattributed')
CLOCKS=('training_steps','optimized_samples','frame_count','learner_frame_count')
POLICY=dict(learner_frames=8000000,learner_accepted=8000000,poll_s=1,API_age_s=5,
            pipeline_age_s=5,unobservable_s=30,no_applied_s=60)
JOURNAL_BYTES=32<<20


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


def pin(value,label):
    require(isinstance(value,dict),'Missing root-authenticated PIN: '+label)
    require(type(value.get('path')) is str and value['path'].startswith('/') and
            '..' not in value['path'].split('/'),'Invalid PIN path: '+label)
    sha=value.get('sha256')
    require(type(sha) is str and len(sha)==64 and all(c in '0123456789abcdef' for c in sha),
            'Invalid PIN digest: '+label)
    require(integer(value.get('bytes'),label+'.bytes')>0,'Empty PIN: '+label)
    return value


def clock_value(value,label):
    require(isinstance(value,dict) and set(value)=={'boot_id','monotonic_s','wall_s'},'Exact clock required: '+label)
    require(type(value['boot_id']) is str and value['boot_id'],'Missing boot identity: '+label)
    require(number(value['monotonic_s'],label+'.monotonic')>0 and
            number(value['wall_s'],label+'.wall')>0,'Nonzero actual clock required: '+label)
    return value


def healthy_api(api,job,now):
    require(api['client_count']==192 and type(api['client_count']) is int and
            api['training_enabled'] is True and api['measurement_active'] is False and
            api['managed_experiment']==job['experiment'],'Active192 post-diagnostic window API scope differs')
    require(number(api['lr'],'scheduled API lr')==RECIPE['scheduled_lr'],'Scheduled API lr differs')
    age=now['wall_s']-number(api['ts'],'API timestamp')
    pipeline_age=number(api['pipeline_snapshot_age_s'],'pipeline age')
    require(age>=0 and pipeline_age>=0,'Future API timestamp or negative pipeline age')
    return age<=POLICY['API_age_s'] and pipeline_age<=POLICY['pipeline_age_s'] and not api['pipeline_read_error']


def validate_job(job,baseline_api):
    require(isinstance(job,dict) and set(job)=={'schema','experiment','owner','recipe','current_phase',
            'proofs','activation_ready_clock','baseline','policy'},'Exact post-diagnostic window job fields required')
    require(job['schema']==SCHEMA and json.dumps(job['recipe'],sort_keys=True,allow_nan=False)==
            json.dumps(RECIPE,sort_keys=True),'Exact CE4096/.5 recipe binding required')
    policy=job['policy']
    require(set(policy)==set(POLICY)|{'cutoff_s'} and all(type(policy[k]) is type(v) and policy[k]==v
            for k,v in POLICY.items()),'New prospective 8M+8M management policy differs')
    require(number(policy['cutoff_s'],'precommitted window cutoff')>0,'Future cutoff must be positive')
    require(type(job['experiment']) is str and 0<len(job['experiment'])<=120 and
            all(c.isascii() and (c.isalnum() or c in '_-') for c in job['experiment']),'Invalid post-diagnostic experiment')
    require(set(job['owner'])==OWNER_KEYS and integer(job['owner']['pid'],'owner.pid')>0 and
            integer(job['owner']['starttime_ticks'],'owner.start')>0,'Exact owned trainer fields required')
    for key in ('unit','invocation_id','cgroup'):
        require(type(job['owner'][key]) is str and job['owner'][key],'Missing owned field: '+key)
    phase=job['current_phase']
    require(isinstance(phase,dict) and set(phase)=={'record','boot_checkpoint','boot_verification','expected'},
            'Authentic dynamic CE founder descriptor required')
    for key in ('record','boot_checkpoint','boot_verification'):pin(phase[key],'current_phase.'+key)
    expected=phase['expected']
    require(isinstance(expected,dict) and set(expected)=={'metric','phase_id','root_precommit_sha256',
            'founder_phase_record_sha256','last_resume_record_sha256','started_from','valid'} and
            expected['metric']=='ce' and expected['valid'] is True and
            expected['founder_phase_record_sha256']==phase['record']['sha256'] and
            expected['last_resume_record_sha256'] is None,
            'Genuine dynamically bound new CE start founder required')
    require(type(expected['phase_id']) is str and 0<len(expected['phase_id'])<=100 and
            all(c.isascii() and (c.isalnum() or c in '_-') for c in expected['phase_id']), 'Invalid actual CE phase ID')
    digest=expected['root_precommit_sha256']
    require(type(digest) is str and len(digest)==64 and all(c in '0123456789abcdef' for c in digest),
            'Invalid actual phase root precommit digest')
    origin=expected['started_from']
    require(isinstance(origin,dict) and set(origin)=={'path','sha256','bytes','clocks'} and
            all(origin[k]==phase['boot_checkpoint'][k] for k in ('path','sha256','bytes')) and
            set(origin['clocks'])==set(CLOCKS) and all(integer(origin['clocks'][k],'boot.'+k)>0 for k in CLOCKS),
            'Actual CE boot checkpoint and four-clock floor required')
    require(set(job['proofs'])=={'root_precommit','activation_result','activation_adoption','control'},
            'Four authenticated post-activation root proof PINs required')
    for key,value in job['proofs'].items():pin(value,'proofs.'+key)
    require(set(job['baseline'])=={'api','observed_clock'},'Exact raw B PIN/clock required')
    pin(job['baseline']['api'],'baseline.api')
    start=clock_value(job['baseline']['observed_clock'],'baseline')
    ready=clock_value(job['activation_ready_clock'],'activation READY')
    require(start['boot_id']==ready['boot_id'] and start['monotonic_s']>=ready['monotonic_s'] and
            start['wall_s']>=ready['wall_s'],'Baseline must be observed after actual activation READY')
    require(healthy_api(baseline_api,job,start),'Baseline B is stale or pipeline read failed')
    require(number(baseline_api['ts'],'baseline API timestamp')-
            number(baseline_api['pipeline_snapshot_age_s'],'baseline pipeline age')>=ready['wall_s'],
            'Conservative pipeline snapshot time predates actual activation READY')
    baseline=normalise(baseline_api)
    require(all(baseline['clocks'][key]>=origin['clocks'][key] for key in CLOCKS) and baseline['accepted']>0 and
            baseline['learner_accepted']>0 and baseline['optimizer']['applied']>0 and
            baseline['optimizer']['outcomes_recorded']>0 and baseline['optimizer']['unavailable']==0 and
            baseline['unclassified']==0 and baseline_api['host_pipeline']['learning_exposure']['optimizer']['available'] is True,
            'Actual post-READY nonzero available pending0 B at/after boot required')
    require(baseline['optimizer_identity']['process_id']==baseline['replay_identity']['process_id']==job['owner']['pid'],
            'Baseline exposure belongs to another process')
    require(len(json.dumps(job,allow_nan=False).encode())<=256<<10,'Strict job exceeds bounded metadata')
    return copy.deepcopy(job),baseline,bounded(baseline_api,2<<20)

class HorizonObserver:
    def __init__(self,job,baseline_api):
        self.job,self.baseline,self.baseline_raw=validate_job(job,baseline_api)
        self.last=copy.deepcopy(self.baseline)
        self.terminal=None;self.first_observation=None;self.last_observation=None
        self.current_raw=None
        self.missing_since=None;self.last_now=None
        self.last_applied_s=self.job['baseline']['observed_clock']['monotonic_s']
        self.applied_anchor=copy.deepcopy(self.baseline)

    def _event(self,state,reason,now,**fields):
        mono=now.get('monotonic_s') if isinstance(now,dict) else None
        verified_time=type(mono) in (int,float) and math.isfinite(mono)
        result=dict(schema=OBSERVATION_SCHEMA,state=state,reason=reason,
            elapsed_s=mono-self.job['baseline']['observed_clock']['monotonic_s'] if verified_time else None,
            observed_monotonic_s=mono if verified_time else None,
            boot_id=now.get('boot_id') if isinstance(now,dict) else None,
            qualification_pass=False,candidate_requests_allowed=0,owner_actions_allowed=False,**fields)
        if state not in ('CONTINUE','LATCH'):
            result['terminal_observation']=copy.deepcopy(self.current_raw)
            if self.current_raw is None:result['last_valid_observation']=copy.deepcopy(self.last_observation)
        if state!='CONTINUE':self.terminal=copy.deepcopy(result)
        return result

    def _clock(self,now):
        clock_value(now,'observation')
        start=self.job['baseline']['observed_clock']
        require(now['boot_id']==start['boot_id'],'Boot identity changed')
        require(now['monotonic_s']>=start['monotonic_s'] and
                (self.last_now is None or now['monotonic_s']>=self.last_now),'Observer monotonic clock regressed')
        anchor=start['monotonic_s'] if self.last_now is None else self.last_now
        require(now['monotonic_s']-anchor<POLICY['unobservable_s'],
                'First observation or poll gap reached fixed unobservable grace')
        self.last_now=now['monotonic_s']

    def observe(self,api,owner,evidence,now):
        if self.terminal is not None:return copy.deepcopy(self.terminal)
        self.current_raw=None
        try:
            self._clock(now)
            require(owner==self.job['owner'],'Owned healthy trainer changed or absent during post-diagnostic window')
            require(isinstance(evidence,dict) and evidence.get('ok') is True,'Root ownership/source/control/phase/fleet evidence failed')
            bounded(evidence,65536)
            return self._observe_api(api,now)
        except (KeyError,TypeError,ValueError,OverflowError) as error:
            return self._event('INVALID',str(error)[:512],now,root_review_required=True)

    def _observe_api(self,api,now):
        elapsed=now['monotonic_s']-self.job['baseline']['observed_clock']['monotonic_s']
        fresh=api is not None
        if fresh:
            self.current_raw=bounded(api,2<<20)
            fresh=healthy_api(api,self.job,now)
        current=normalise(api) if fresh else None
        if current is not None:
            for key in ('optimizer_identity','replay_identity'):
                require(current[key]==self.baseline[key],'Exposure identity/epoch changed: '+key)
            for group in ('clocks','optimizer','optimizer_since_epoch','categories'):
                require(all(current[group][key]>=self.last[group][key] for key in self.last[group]),'Counter regressed: '+group)
            require(current['optimizer']['unavailable']==0,'Classified unavailable optimizer outcome increased')
        cutoff=self.job['policy']['cutoff_s']
        if elapsed>cutoff:return self._event('INCOMPLETE','Both horizons not durably observed by precommitted cutoff',now)
        if current is None:
            if self.missing_since is None:self.missing_since=now['monotonic_s']
            if now['monotonic_s']-self.missing_since>=POLICY['unobservable_s']:
                return self._event('INVALID','Observation missing/stale for fixed grace',now,root_review_required=True)
            if elapsed==cutoff:return self._event('INCOMPLETE','No fresh eligible observation at cutoff',now)
            return self._event('CONTINUE','Missing/stale observation inside bounded grace',now,progress=None)
        self.missing_since=None
        delta={key:current['optimizer'][key]-self.baseline['optimizer'][key] for key in COUNTERS}
        denominator=delta['applied']+delta['amp_skipped']
        progress=dict(learner_frames=current['clocks']['learner_frame_count']-self.baseline['clocks']['learner_frame_count'],
            fleet_frames=current['clocks']['frame_count']-self.baseline['clocks']['frame_count'],
            physical_accepted=current['accepted']-self.baseline['accepted'],
            physical_by_source={key:current['categories'][key]-self.baseline['categories'][key] for key in CATEGORIES},
            learner_accepted=current['learner_accepted']-self.baseline['learner_accepted'],
            logical_steps=current['clocks']['training_steps']-self.baseline['clocks']['training_steps'],
            logical_samples=current['clocks']['optimized_samples']-self.baseline['clocks']['optimized_samples'],
            optimizer_total=copy.deepcopy(current['optimizer']),optimizer_delta_from_B=delta,
            optimizer_pending=current['unclassified'],AMP_classified_denominator=denominator,
            AMP_skip_fraction=None if denominator==0 else delta['amp_skipped']/denominator,
            admitted_samples_from_B=delta['applied']*BATCH_SIZE,
            admitted_samples_process_total=current['optimizer']['applied']*BATCH_SIZE,
            admitted_samples_scope='Classified applied4096 batches; not logical samples or per-parameter movement',
            origin='All deltas use the same nonzero post-READY B; no cross-structure equality')
        if current['optimizer']['applied']>self.last['optimizer']['applied']:
            self.last_applied_s=now['monotonic_s'];self.applied_anchor=copy.deepcopy(current)
        stalled=(now['monotonic_s']-self.last_applied_s>=POLICY['no_applied_s'] and
            current['clocks']['learner_frame_count']>self.applied_anchor['clocks']['learner_frame_count'] and
            current['accepted']>self.applied_anchor['accepted'])
        self.last=copy.deepcopy(current);self.last_observation=bounded(api,2<<20)
        if self.first_observation is None:self.first_observation=copy.deepcopy(self.last_observation)
        if stalled:return self._event('INVALID','Frames/adds advance without applied admission for fixed interval',now,
                                     progress=progress,root_review_required=True)
        if progress['learner_frames']>=POLICY['learner_frames'] and progress['learner_accepted']>=POLICY['learner_accepted']:
            return self._event('LATCH','First fresh BOTH-horizon observation; durability still required',now,progress=progress,
                first_eligible_observation=copy.deepcopy(self.last_observation),durability_required=True,
                root_next='Only timely original durable event permits one candidate request; no helper owner actions')
        if elapsed==cutoff:return self._event('INCOMPLETE','Both horizons absent at cutoff',now,progress=progress)
        return self._event('CONTINUE','Both horizons not yet reached',now,progress=progress)


def encoded(value):
    # Root publisher must create ONLY these exact bytes, fsync file and directory,
    # and return their authentic FULLPIN. NaN remains confined to raw API payloads.
    return (json.dumps(value,indent=2,allow_nan=True)+'\n').encode()


def publication_pin(value,content,label):
    pin(value,label);data=encoded(content)
    require(value['sha256']==hashlib.sha256(data).hexdigest() and value['bytes']==len(data),
            'Published original bytes differ: '+label)
    return value


def durable_event(event,job,root,*,publish,get_clock):
    """Injected create-only publication; receipt follows actual event fsync."""
    sequence=integer(event['sequence'],'sequence')
    path=root/('observation-%04d.json'%sequence)
    event_pin=publication_pin(publish(path,copy.deepcopy(event)),event,'event')
    require(event_pin['path']==str(path),'Publisher returned another original event path')
    completed=clock_value(get_clock(),'event file+directory fsync completion')
    start=job['baseline']['observed_clock']
    require(completed['boot_id']==start['boot_id']==event['boot_id'] and
            completed['monotonic_s']>=event['observed_monotonic_s']>=start['monotonic_s'],
            'Actual event fsync completion predates observation or changed boot')
    receipt=dict(event=event_pin,sequence=sequence,completed_monotonic_s=completed['monotonic_s'],
        elapsed_s=completed['monotonic_s']-start['monotonic_s'],boot_id=completed['boot_id'],
        scope='Actual original event file+directory fsync completion; this paired metadata is published afterward')
    receipt_path=root/('durability-%04d.json'%sequence)
    receipt_pin=publication_pin(publish(receipt_path,receipt),receipt,'durability')
    require(receipt_pin['path']==str(receipt_path),'Publisher returned another paired receipt path')
    return dict(event=event_pin,durability=receipt_pin,completion=receipt)


class ReceiptJournal:
    """Same bounded journal budget; never retry any failed or terminal emission."""
    def __init__(self,*,publish,get_clock,root,job):
        self.publish,self.get_clock,self.root,self.job=publish,get_clock,root,copy.deepcopy(job)
        self.used=0;self.failure=None;self.terminal_attempted=False

    def emit(self,event):
        require(self.failure is None and not self.terminal_attempted,'Original failed/terminal emission cannot be replaced')
        if event['state']!='CONTINUE':self.terminal_attempted=True
        def write(path,value):
            size=len(encoded(value))
            if path.name.startswith('durability-'):require(size<=4096,'Durability metadata exceeds reserved space')
            require(self.used+size<=JOURNAL_BYTES,'Journal byte limit exceeded')
            result=self.publish(path,value);self.used+=size
            return result
        try:
            require(self.used+len(encoded(event))+4096<=JOURNAL_BYTES,'Fixed32MiB observation journal exhausted')
            return durable_event(event,self.job,self.root,publish=write,get_clock=self.get_clock)
        except BaseException as error:
            self.failure=repr(error)
            raise


def durable_result(event,pair,job):
    require(isinstance(pair,dict) and set(pair)=={'event','durability','completion'},'Original paired durability evidence required')
    publication_pin(pair['event'],event,'event')
    receipt=pair['completion'];publication_pin(pair['durability'],receipt,'durability')
    require(set(receipt)=={'event','sequence','completed_monotonic_s','elapsed_s','boot_id','scope'} and
            receipt['event']==pair['event'] and receipt['sequence']==event['sequence'],'Durability receipt names another event')
    start=job['baseline']['observed_clock']
    require(receipt['boot_id']==start['boot_id']==event['boot_id'] and
            number(receipt['completed_monotonic_s'],'completed monotonic')>=event['observed_monotonic_s']>=start['monotonic_s'] and
            number(receipt['elapsed_s'],'completed elapsed')==receipt['completed_monotonic_s']-start['monotonic_s'],
            'Durability clock does not join original event/B')
    allowed=(event['state']=='LATCH' and event['elapsed_s']<=job['policy']['cutoff_s'] and
             receipt['elapsed_s']<=job['policy']['cutoff_s'])
    return dict(status='LATCH_DURABLE' if allowed else ('LATCH_LATE_DURABILITY' if event['state']=='LATCH' else event['state']),
        observation=copy.deepcopy(event),durability=copy.deepcopy(pair),candidate_requests_allowed=int(allowed),
        qualification_pass=False,owner_actions_allowed=False)


def poll(job,*,baseline_api,get_api,get_owner,get_evidence,get_clock,sleep,emit):
    """One immutable first decision. Root callbacks have bounded I/O timeouts.

    emit must return durable_event's exact paired proof, not a bare success flag.
    A late/failed publication retains the original first decision and permits no
    replacement, replay, reanchoring or candidate. Root owns any later operation.
    """
    observer=HorizonObserver(job,baseline_api)
    budget=math.ceil(observer.job['policy']['cutoff_s']/POLICY['poll_s'])+2
    for sequence in range(budget):
        try:owner=get_owner();evidence=get_evidence()
        except Exception as error:owner=None;evidence=dict(ok=False,error=str(error)[:512])
        try:api=get_api()
        except Exception:api=None
        now=get_clock()  # Actual observation timestamp AFTER all callbacks.
        event=observer.observe(api,owner,evidence,now);event['sequence']=sequence
        try:result=durable_result(event,emit(copy.deepcopy(event)),observer.job)
        except Exception as error:
            return dict(status='EVIDENCE_FAILED',observation=copy.deepcopy(event),error=str(error)[:512],
                candidate_requests_allowed=0,qualification_pass=False,owner_actions_allowed=False)
        if event['state']!='CONTINUE':return result
        sleep(POLICY['poll_s'])
    return dict(status='POLL_BUDGET_EXHAUSTED',observation=copy.deepcopy(event),candidate_requests_allowed=0,
        qualification_pass=False,owner_actions_allowed=False)


def main():
    print(json.dumps(dict(status='PLAN_ONLY',schema=SCHEMA,policy=dict(POLICY,cutoff_s=None),recipe=RECIPE,
        actions=False,API_or_owner_reads=False,output_writes=False,qualification_pass=False,
        future_baseline=None,selected=False),sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
