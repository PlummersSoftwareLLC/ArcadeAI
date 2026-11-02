"""Prospective bounded host-clock co-sampling; no import actions or I/O.

Caller placement supplies causality: sample before sending authorization, after
receiving the accepted frame, and before journal handoff. Never allocate/extend
an action deadline here. Witnesses preserve every attempted pair and gap.
"""
import copy
import time

SCHEMA='robotron-bounded-host-clock-cosample-v1'
COHERENCE_TOLERANCE_NS=50_000_000
MAX_ATTEMPTS=3
MAX_PAIR_SPAN_NS=1_000_000
MAX_TOTAL_NS=1_000_000_000
MAX_TIMESTAMP_NS=(1<<63)-1
PHASES=('before_authorization','after_accepted_frame','before_journal_handoff')

class ClockSamplingError(ValueError):
    def __init__(self,reason,evidence):
        super().__init__('Host clock co-sampling failed: '+reason)
        self.reason=reason;self.evidence=copy.deepcopy(evidence)

class ClockCoherenceError(ValueError):
    def __init__(self,reason,evidence):
        super().__init__('Host clock coherence failed: '+reason)
        self.reason=reason;self.evidence=copy.deepcopy(evidence)

def integer(value,name,minimum=0,maximum=MAX_TIMESTAMP_NS):
    if type(value) is not int or not minimum<=value<=maximum:
        raise ValueError('Invalid integer '+name)
    return value

def policy(max_attempts,max_span_ns,max_total_ns):
    return dict(max_attempts=integer(max_attempts,'max_attempts',1,MAX_ATTEMPTS),
        max_span_ns=integer(max_span_ns,'max_span_ns',1,MAX_PAIR_SPAN_NS),
        max_total_ns=integer(max_total_ns,'max_total_ns',1,MAX_TOTAL_NS),
        coherence_tolerance_ns=COHERENCE_TOLERANCE_NS)

def sample_pair(phase,*,deadline_mono_ns,monotonic_ns=time.monotonic_ns,wall_ns=time.time_ns,
                max_attempts=MAX_ATTEMPTS,max_span_ns=MAX_PAIR_SPAN_NS,max_total_ns=MAX_TOTAL_NS):
    """At most three immediate pairs, clipped to the existing action deadline.

    A representative midpoint lies inside the observed bracket. Its maximum
    uncertainty is ceil(span/2). There is no sleep or outcome-dependent retry.
    Errors carry all attempted clocks; they never yield a usable witness.
    """
    if phase not in PHASES:raise ValueError('Unknown clock-sample phase')
    deadline_mono_ns=integer(deadline_mono_ns,'parent action deadline',1)
    selected_policy=policy(max_attempts,max_span_ns,max_total_ns)
    result=dict(schema=SCHEMA,status='sampling',phase=phase,policy=selected_policy,
        parent_deadline_mono_ns=deadline_mono_ns,effective_deadline_mono_ns=None,
        started_mono_ns=None,completed_mono_ns=None,total_elapsed_ns=None,
        attempts=[],selected_index=None,selected=None,failure_reason=None)
    def fail(reason,completed=None):
        result.update(status='failed',failure_reason=reason,completed_mono_ns=completed)
        if completed is not None and result['started_mono_ns'] is not None:
            result['total_elapsed_ns']=completed-result['started_mono_ns']
        raise ClockSamplingError(reason,result)
    previous_after=previous_wall=None
    for index in range(1,max_attempts+1):
        attempt=dict(index=index,mono_before_ns=None,wall_ns=None,mono_after_ns=None,
            span_ns=None,gap_before_ns=None,elapsed_from_begin_ns=None,status='reading')
        result['attempts'].append(attempt)
        try:before=integer(monotonic_ns(),'monotonic before')
        except Exception:fail('invalid_or_failed_monotonic_before')
        attempt['mono_before_ns']=before
        if result['started_mono_ns'] is None:
            result['started_mono_ns']=before
            result['effective_deadline_mono_ns']=min(deadline_mono_ns,before+max_total_ns)
        if previous_after is not None and before<previous_after:
            attempt['status']='monotonic_reversed';fail('monotonic_reversed_between_attempts',before)
        attempt['gap_before_ns']=0 if previous_after is None else before-previous_after
        if before>=result['effective_deadline_mono_ns']:
            attempt['status']='deadline_before_pair';fail('deadline_exhausted',before)
        try:wall=integer(wall_ns(),'wall clock')
        except Exception:fail('invalid_or_failed_wall_clock',before)
        attempt['wall_ns']=wall
        try:after=integer(monotonic_ns(),'monotonic after')
        except Exception:fail('invalid_or_failed_monotonic_after')
        attempt.update(mono_after_ns=after,span_ns=after-before,
            elapsed_from_begin_ns=after-result['started_mono_ns'])
        if after<before:
            attempt['status']='monotonic_reversed';fail('monotonic_reversed_inside_pair',after)
        if previous_wall is not None and wall<previous_wall:
            attempt['status']='wall_reversed';fail('wall_reversed_between_attempts',after)
        if after>=result['effective_deadline_mono_ns']:
            attempt['status']='deadline_after_pair';fail('deadline_exhausted',after)
        if after-before<=max_span_ns:
            midpoint=before+(after-before)//2
            selected=dict(wall_ns=wall,mono_before_ns=before,mono_after_ns=after,
                midpoint_mono_ns=midpoint,uncertainty_ns=max(midpoint-before,after-midpoint))
            attempt['status']='selected'
            result.update(status='sampled',completed_mono_ns=after,total_elapsed_ns=after-result['started_mono_ns'],
                selected_index=index,selected=selected)
            validate_pair(result)
            return result
        attempt['status']='span_exceeded';previous_after,previous_wall=after,wall
    fail('attempt_limit_exhausted',result['attempts'][-1]['mono_after_ns'])

def validate_pair(witness):
    """Replay a successful witness without clocks, I/O or native state."""
    if not isinstance(witness,dict) or witness.get('schema')!=SCHEMA or witness.get('status')!='sampled':
        raise ValueError('Need a successful bounded co-sample witness')
    if witness.get('phase') not in PHASES or witness.get('failure_reason') is not None:
        raise ValueError('Clock phase/failure differs')
    p=witness['policy']
    if type(p) is not dict or integer(p['coherence_tolerance_ns'],'coherence tolerance',1)!=COHERENCE_TOLERANCE_NS:
        raise ValueError('Clock coherence tolerance differs')
    if p!=policy(p['max_attempts'],p['max_span_ns'],p['max_total_ns']):raise ValueError('Clock policy differs')
    rows=witness['attempts'];chosen=integer(witness['selected_index'],'selected index',1,p['max_attempts'])
    if type(rows) is not list or len(rows)!=chosen:raise ValueError('Missing or extra clock attempts')
    begin=integer(witness['started_mono_ns'],'sample begin')
    deadline=integer(witness['parent_deadline_mono_ns'],'parent deadline',1)
    effective=min(deadline,begin+p['max_total_ns'])
    if integer(witness['effective_deadline_mono_ns'],'effective deadline',1)!=effective:raise ValueError('Deadline was extended')
    previous_after=previous_wall=None
    for index,row in enumerate(rows,1):
        if type(row) is not dict:raise ValueError('Clock attempt must be an object')
        before=integer(row['mono_before_ns'],'attempt before');after=integer(row['mono_after_ns'],'attempt after')
        wall=integer(row['wall_ns'],'attempt wall')
        if integer(row['index'],'attempt index',1)!=index or after<before or after>=effective:raise ValueError('Invalid clock attempt order/deadline')
        if index==1 and before!=begin:raise ValueError('Sample begin differs')
        if previous_after is not None and (before<previous_after or wall<previous_wall):raise ValueError('Clock reversed')
        if integer(row['span_ns'],'attempt span')!=after-before or integer(row['gap_before_ns'],'attempt gap')!=(0 if previous_after is None else before-previous_after):
            raise ValueError('Clock span/gap differs')
        if integer(row['elapsed_from_begin_ns'],'attempt elapsed')!=after-begin:raise ValueError('Clock elapsed differs')
        if index<chosen:
            if row['status']!='span_exceeded' or after-before<=p['max_span_ns']:
                raise ValueError('Skipped an already usable clock pair')
        elif row['status']!='selected' or after-before>p['max_span_ns']:
            raise ValueError('Selected pair exceeds uncertainty bound')
        previous_after,previous_wall=after,wall
    midpoint=before+(after-before)//2
    expected=dict(wall_ns=wall,mono_before_ns=before,mono_after_ns=after,
        midpoint_mono_ns=midpoint,uncertainty_ns=max(midpoint-before,after-midpoint))
    if type(witness['selected']) is not dict or set(witness['selected'])!=set(expected):raise ValueError('Selected clock fields differ')
    if any(integer(witness['selected'][key],key)!=value for key,value in expected.items()):raise ValueError('Selected clock values differ')
    if witness['selected']!=expected or integer(witness['completed_mono_ns'],'sample completion')!=after or integer(witness['total_elapsed_ns'],'sample elapsed')!=after-begin:
        raise ValueError('Selected midpoint/uncertainty/elapsed differs')
    return copy.deepcopy(expected)

def check_coherence(lower,upper):
    """Conservative unchanged50ms bound, for issuance AND later handoff.

    Compare before_authorization→after_accepted_frame and separately
    before_authorization→before_journal_handoff. Do not check adjacent pairs only.
    """
    a,b=validate_pair(lower),validate_pair(upper)
    if lower['phase']!='before_authorization' or upper['phase'] not in PHASES[1:]:
        raise ValueError('Clock comparison has wrong causal phases')
    wall_elapsed=b['wall_ns']-a['wall_ns'];mono_elapsed=b['midpoint_mono_ns']-a['midpoint_mono_ns']
    uncertainty=a['uncertainty_ns']+b['uncertainty_ns']
    evidence=dict(schema='robotron-conservative-host-clock-coherence-v1',lower=copy.deepcopy(lower),upper=copy.deepcopy(upper),
        tolerance_ns=COHERENCE_TOLERANCE_NS,wall_elapsed_ns=wall_elapsed,midpoint_mono_elapsed_ns=mono_elapsed,
        signed_midpoint_error_ns=wall_elapsed-mono_elapsed,total_uncertainty_ns=uncertainty,
        maximum_possible_error_ns=abs(wall_elapsed-mono_elapsed)+uncertainty)
    if b['mono_before_ns']<a['mono_after_ns'] or mono_elapsed<0 or wall_elapsed<0:
        raise ClockCoherenceError('clock_reversal_or_noncausal_order',evidence)
    if evidence['maximum_possible_error_ns']>COHERENCE_TOLERANCE_NS:
        raise ClockCoherenceError('wall_monotonic_incoherence',evidence)
    evidence.update(passed=True,certificate_clock_fields=dict(
        lower_before_send_unix_ns=a['wall_ns'],upper_after_receive_unix_ns=b['wall_ns'],
        lower_monotonic_ns=a['midpoint_mono_ns'],upper_monotonic_ns=b['midpoint_mono_ns']))
    return evidence
