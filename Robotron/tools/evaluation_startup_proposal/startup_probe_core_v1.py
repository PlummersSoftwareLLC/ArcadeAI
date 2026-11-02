"""Pure one-attempt startup diagnostic coordinator; no runtime adapter or launcher.

The caller must provide an authenticated private runtime. These contracts do
not prove real ROM start acceptance and cannot qualify or promote a policy.
"""
import math
import time
import traceback

SLOTS = tuple(range(4096, 4112))
FRAMES = 4096
MAX_WALL_S = 300
POLL_S = 0.25
CURRENT_PLAN_SHA = '9c1289bbd71b0e5ff6f317c5dcfead146bb319894680738b4d14c7acdb845e48'
NATIVE_OWNER_SHA = '52f880a7bb9de3c9b631df1d6230e975b41c70ac81f21c81b3e31b38c153d35b'
OUTER_OWNER_SHA = '26189c645c3ca776aa6d8074927a71563a6c4c8bedcbaaa10c9859cfd911afca'
REVIEW_SOURCE_SHA = 'e6c402b778aaca214a5a4533b6ffa8c5f010e2866a6afeda619970f35e2f92cb'


def require(value, message):
    if not value:
        raise ValueError(message)


def configuration(settings):
    require(isinstance(settings, dict) and set(settings) == {'slots','frames','max_wall_s','poll_s'},
            'Exact diagnostic coordinator settings required')
    require(type(settings['slots']) in (list,tuple) and tuple(settings['slots']) == SLOTS
            and all(type(x) is int for x in settings['slots']), 'Exactly16 declared private slots required')
    require(type(settings['frames']) is int and settings['frames'] == FRAMES,
            'Fixed4096-frame prefix required')
    require(type(settings['max_wall_s']) is int and settings['max_wall_s'] == MAX_WALL_S
            and type(settings['poll_s']) is float and settings['poll_s'] == POLL_S,
            'Fixed300-second/quarter-second coordinator bounds required')
    return dict(slots=list(SLOTS),frames=FRAMES,max_wall_s=MAX_WALL_S,poll_s=POLL_S)


def verify_closed_predecessor(bundle, *, read, archive, process_start, unit_fields, cgroup_exists):
    """Authenticate original closure evidence before any live unit/process query.

This gate grants no GPU lease and makes no device query. A runtime adapter must
still bind fresh main/ROM/source/output identities and acquire the private lease.
"""
    required = {'plan','status','native_owner','native_closure','outer_owner','outer_closure',
                'review_owner','review_closure','review_config','review_source','disposition'}
    require(isinstance(bundle,dict) and set(bundle) == required, 'Complete predecessor evidence required')
    require(bundle['plan']['sha256'] == CURRENT_PLAN_SHA
            and bundle['native_owner']['sha256'] == NATIVE_OWNER_SHA
            and bundle['outer_owner']['sha256'] == OUTER_OWNER_SHA
            and bundle['review_source']['sha256'] == REVIEW_SOURCE_SHA,
            'Exact original campaign/owners/reviewer required')
    plan, status, disposition = (read(bundle[key],True) for key in ('plan','status','disposition'))
    require(plan.get('schema') is not None and status.get('plan_sha256') == CURRENT_PLAN_SHA,
            'Original campaign plan binding differs')
    require(disposition.get('schema') == 'robotron-closed-quality-before-startup-diagnostic-v1'
            and disposition.get('original_status_sha256') == bundle['status']['sha256']
            and disposition.get('original_plan_sha256') == CURRENT_PLAN_SHA
            and disposition.get('quality_campaign_closed') is True
            and disposition.get('no_cohort_retry') is True,
            'Independent original terminal disposition missing')
    outcome = disposition.get('native_outcome')
    require(outcome in ('invalid','incomplete','not_improved','qualified_improvement'),
            'Unrecognized original scientific outcome')
    if status.get('state') == 'finished':
        require(status.get('outcome') == outcome, 'Scientific outcome was reinterpreted')
    else:
        require(outcome in ('invalid','incomplete'), 'Unfinished producer status cannot imply qualification')
    require(disposition.get('winner_protected_or_not_applicable') is True,
            'Preceding winner protection/disposition must finish first')
    read(bundle['review_source'],False)
    review_config = read(bundle['review_config'],True)
    owners = []
    for role in ('native','outer','review'):
        owner, closure = read(bundle[role+'_owner'],True), read(bundle[role+'_closure'],True)
        fields = archive(closure,owner,read,exit_zero=False)
        require(closure.get('payload_retried',False) is False, 'Original predecessor was retried')
        if role == 'review':
            require(review_config.get('unit') == owner['unit']
                    and bundle['review_source']['path'] in review_config.get('argv',[]),
                    'Original sole scientific review config differs')
        if role == 'native' and status.get('state') != 'finished':
            require(closure.get('original_exit') != 0, 'Successful native exit lacks original final status')
        owners.append((owner, fields))
    # Only after all archived identities/outcomes are authenticated do we query
    # actual live state. Never adopt a new process with a reused numeric PID.
    for owner, fields in owners:
        require(process_start(owner['pid']) != owner['starttime_ticks'], 'Original predecessor still lives')
        for unit in (owner['unit'],owner['timer']):
            live = unit_fields(unit)
            require(live.get('Id') == unit and live.get('LoadState') == 'not-found',
                    'Original predecessor unit remains')
        group = owner.get('cgroup') or fields.get('ControlGroup')
        if group:
            require(isinstance(group,str) and group.startswith('/user.slice/')
                    and not cgroup_exists(group), 'Original predecessor cgroup remains')
    return dict(status='ORIGINAL_PREDECESSOR_CLOSED',native_outcome=outcome,
                original_owner_count=3,GPU_lease_acquired=False,scientific_outcome_changed=False)


def progress(snapshot, previous=None):
    required = {'closed','failed','faults','rows','counts','pending','epochs'}
    require(isinstance(snapshot,dict) and set(snapshot) == required, 'Exact bounded capture snapshot required')
    require(type(snapshot['closed']) is type(snapshot['failed']) is bool,
            'Capture state flags must be booleans')
    require(type(snapshot['faults']) is int and snapshot['faults'] == 0 and snapshot['failed'] is False,
            'Private diagnostic recorder failed')
    counts, epochs = snapshot['counts'], snapshot['epochs']
    require(isinstance(counts,dict) and isinstance(epochs,dict)
            and set(counts) == set(epochs) == set(SLOTS), 'Declared capture slots differ')
    require(all(type(n) is int and 0 <= n <= FRAMES for n in counts.values())
            and all(type(n) is int and 0 <= n <= 1 for n in epochs.values()),
            'Capture bounds exceeded or a connection restarted')
    require(all(counts[slot] == 0 or epochs[slot] == 1 for slot in SLOTS),
            'Captured rows lack an original connection')
    require(type(snapshot['rows']) is int and snapshot['rows'] == sum(counts.values()), 'Captured row count differs')
    require(type(snapshot['pending']) is int and 0 <= snapshot['pending'] <= len(SLOTS), 'Pending capture count differs')
    require(snapshot['pending'] <= sum(n == 1 for n in epochs.values()),
            'Pending frames lack original connections')
    if previous is not None:
        require(all(counts[slot] >= previous['counts'][slot] and epochs[slot] >= previous['epochs'][slot]
                    for slot in SLOTS), 'Capture counters or connection epochs regressed')
    complete = all(n == FRAMES for n in counts.values()) and all(n == 1 for n in epochs.values())
    if snapshot['closed']:
        require(complete and snapshot['pending'] == 0, 'Capture closed before every original prefix finished')
    return bool(snapshot['closed'] and complete)


def matched(value):
    require(isinstance(value,dict) and value.get('status') == 'MATCHED_DIAGNOSTIC_PREFIX_ONLY',
            'Independent original-prefix reconciliation failed')
    require(type(value.get('matched_frames')) is int and value['matched_frames'] == len(SLOTS)*FRAMES
            and type(value.get('actor_slots')) is int and value['actor_slots'] == len(SLOTS),
            'Original matched-prefix coverage differs')
    accepted, rejected = value.get('accepted_frames'), value.get('rejected_frames')
    require(type(accepted) is type(rejected) is int and min(accepted,rejected) >= 0
            and accepted + rejected == value['matched_frames'], 'Accepted/rejected prefix counts differ')
    require(all(value.get(key) is False for key in ('raw_ROM_start_acceptance_proven',
        'start_eligibility_changed','protocol_selected','quality_qualified','learning_speed_gain_verified')),
        'Diagnostic join cannot grant start, quality or speed approval')


def runtime_audit(value):
    require(isinstance(value,dict), 'Independent runtime audit missing')
    for key in ('valid','all_owned_actors_absent','sources_unchanged','checkpoint_unchanged','main_healthy'):
        require(value.get(key) is True, 'Runtime audit failed: '+key)
    require(type(value.get('runtime_timeouts')) is int and value['runtime_timeouts'] == 0,
            'Runtime socket timeouts invalidate the diagnostic')


def execute(runtime, settings, *, clock=time.monotonic, sleep=time.sleep, stopped=lambda:False):
    """One authenticated runtime object, one attempt, all cleanup stages once.

The fixed wall deadline includes prepare/start. An external owned-unit guard
must cover a runtime operation that blocks without returning to this coordinator.
The runtime owns persistence, process handles and original immutable evidence.
"""
    settings = configuration(settings)
    require(not getattr(runtime,'startup_attempt_consumed',False), 'Original runtime attempt already consumed')
    runtime.startup_attempt_consumed = True
    required = ('prepare','start','check','snapshot','cleanup','collect','audit','release','publish')
    require(all(callable(getattr(runtime,name,None)) for name in required), 'Complete private runtime interface required')
    errors, previous = [], None
    complete = False
    start = last = None
    reconciled = audit = None
    phase = 'prepare'
    def budget():
        nonlocal start, last
        now = clock()
        require(type(now) in (int,float) and math.isfinite(now)
                and (last is None or now >= last), 'Probe clock regressed or became nonfinite')
        if start is None:start = now
        last = now
        require(now-start < settings['max_wall_s'], 'Original diagnostic deadline expired; no retry or extension')
        require(not stopped(), 'Original diagnostic interrupted')
    def failure(stage,error):
        errors.append(dict(stage=stage,type=type(error).__name__,message=str(error)[:2000],
            traceback=''.join(traceback.format_exception(type(error),error,error.__traceback__))[:32768]))
    def cleanup_stage(name):
        try:
            result = getattr(runtime,name)()
            require(isinstance(result,list) and all(isinstance(x,str) for x in result),
                    name+' must return explicit cleanup errors')
            for text in result:errors.append(dict(stage=name,type='CleanupError',message=text[:2000]))
        except BaseException as error:
            failure(name,error)
    try:
        budget();runtime.prepare();budget()
        phase = 'start';runtime.start();budget()
        phase = 'capture'
        while True:
            budget();runtime.check();budget()
            snapshot = runtime.snapshot()
            complete = progress(snapshot,previous)
            previous = dict(snapshot,counts=dict(snapshot['counts']),epochs=dict(snapshot['epochs']))
            budget()
            if complete:
                break
            sleep(settings['poll_s'])
    except BaseException as error:
        failure(phase,error)
    finally:
        # Keep collecting original evidence after failure. Neither an audit nor
        # evidence-copy exception is allowed to bypass the remaining finalizers.
        cleanup_stage('cleanup')
        try:
            reconciled = runtime.collect()
            if complete:matched(reconciled)
        except BaseException as error:
            failure('collect',error)
        try:
            audit = runtime.audit()
            runtime_audit(audit)
        except BaseException as error:
            failure('audit',error)
        cleanup_stage('release')
    valid = complete and not errors
    result = dict(schema='robotron-one-attempt-startup-probe-coordinator-v1',
        status='MATCHED_DIAGNOSTIC_PREFIX_ONLY' if valid else 'FAILED_DIAGNOSTIC_PRESERVED',
        capture_complete=complete,valid=valid,errors=errors,reconciliation=reconciled,runtime_audit=audit,
        settings=settings,attempts=1,retried=False,raw_ROM_start_acceptance_proven=False,
        start_eligibility_changed=False,protocol_selected=False,quality_qualified=False,
        learning_speed_gain_verified=False,scientific_review_rerun=False)
    try:
        runtime.publish(result)
    except BaseException as error:
        failure('publish',error)
        result.update(valid=False,status='FAILED_DIAGNOSTIC_PRESERVED')
    return result
