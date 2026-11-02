"""Bounded sampled socket-response timing; no device sync or application decisions.

Selected-at-ingress frames are all sampled. Other connections sample ordinal
1,21,41,... independently, without policy RNG. Sequential phases are exclusive;
lock/enqueue spans are nested and must not be added to response_total again.
"""
import os
import threading
import time
from bisect import bisect_left

SCHEMA = 'robotron-socket-response-pipeline-v1'
OUTCOMES = ('accepted', 'done', 'inactive', 'parse_reject', 'classifier_reject',
            'no_response', 'disconnected', 'aborted', 'other')
PHASES = ('header_wait', 'payload_wait', 'parse_cache', 'classify', 'state', 'journal',
          'metrics_aggregate', 'previous_step', 'choose_action', 'inference', 'action_write',
          'response_total', 'client_lock_wait', 'client_lock_hold', 'enqueue_wait',
          'preview_metrics_wait', 'preview_metrics_hold')
BOUNDS_MS = (.01, .05, .1, .25, .5, 1., 2., 5., 10., 20., 50., 100., 250., 500., 1000., None)


def _distribution():
    return dict(count=0, sum_ms=0., max_ms=0., histogram=[0] * len(BOUNDS_MS))


def _add(d, value):
    d['count'] += 1; d['sum_ms'] += value; d['max_ms'] = max(d['max_ms'], value)
    d['histogram'][bisect_left(BOUNDS_MS[:-1], value)] += 1


def _group():
    return dict(completed_sampled_frames=0, outcomes={}, phase_calls={},
                phases={p: dict(wall=_distribution(), thread_cpu=_distribution()) for p in PHASES},
                queue_depth_observations=0, queue_depth_sum=0, queue_depth_max=0, queue_depth_last=None,
                ingress_queue_depth_count=0, ingress_queue_depth_sum=0, ingress_queue_depth_max=0, ingress_queue_depth_last=None, last_sample_identity=None, selected_identity_changes=0)


class ResponseTelemetry:
    def __init__(self, sample_every=20, *, wall_ns=time.perf_counter_ns,
                 thread_cpu_ns=getattr(time, 'thread_time_ns', None)):
        if type(sample_every) is not int or sample_every < 1:
            raise ValueError('Positive integer sampling interval required')
        self.sample_every = sample_every; self.wall = wall_ns; self.cpu = thread_cpu_ns
        self._lock = threading.Lock(); self._pid = os.getpid(); self._instance = wall_ns()
        self._errors = 0; self._groups = dict(selected=_group(), background=_group())

    def begin(self, cid, slot, ordinal, selected, *, connection_ns=0):
        # No lock or clock call on the ordinary unsampled path.
        if not selected and (ordinal - 1) % self.sample_every:
            return None
        try:
            return _Trace(self, cid, slot, ordinal, bool(selected), connection_ns)
        except Exception:
            self.error(); return None

    def error(self):
        with self._lock: self._errors += 1

    def record(self, trace, outcome):
        with self._lock:
            g = self._groups['selected' if trace.selected else 'background']
            g['completed_sampled_frames'] += 1
            identity=dict(client_id=trace.cid, slot=trace.slot, connection_ns=trace.connection_ns)
            if trace.selected and g['last_sample_identity'] is not None and identity != g['last_sample_identity']:
                g['selected_identity_changes'] += 1
            g['last_sample_identity']=identity
            if outcome not in OUTCOMES: outcome='other'
            g['outcomes'][outcome] = g['outcomes'].get(outcome, 0) + 1
            for phase, (wall, cpu, calls) in trace.values.items():
                _add(g['phases'][phase]['wall'], wall / 1e6)
                if cpu is not None: _add(g['phases'][phase]['thread_cpu'], cpu / 1e6)
                g['phase_calls'][phase] = g['phase_calls'].get(phase, 0) + calls
            if trace.ingress_depth is not None:
                depth=trace.ingress_depth; g['ingress_queue_depth_count'] += 1
                g['ingress_queue_depth_sum'] += depth; g['ingress_queue_depth_max'] = max(g['ingress_queue_depth_max'], depth)
                g['ingress_queue_depth_last'] = depth
            for depth in trace.depths:
                g['queue_depth_observations'] += 1; g['queue_depth_sum'] += depth
                g['queue_depth_max'] = max(g['queue_depth_max'], depth); g['queue_depth_last'] = depth

    def snapshot(self):
        from copy import deepcopy
        with self._lock:
            return dict(schema=SCHEMA, available=self._errors == 0, observer_errors=self._errors,
                process_id=self._pid, instance_monotonic_ns=self._instance,
                sample_every_background=self.sample_every, selected_sampling='every frame, selection at ingress',
                thread_cpu_available=self.cpu is not None, latency_bucket_upper_ms=list(BOUNDS_MS),
                nested_spans_not_additive_to_response_total=True,
                response_total_scope='payload complete through successful response send; excludes header/payload waits',
                queue_depth_scope='queue admission only; not proof of physical replay insertion',
                groups=deepcopy(self._groups))


class _Trace:
    def __init__(self, owner, cid, slot, ordinal, selected, connection_ns):
        self.owner=owner; self.cid=cid; self.slot=slot; self.ordinal=ordinal; self.selected=selected
        self.connection_ns=connection_ns
        self.closed=False; self.values={}; self.open={}; self.depths=[]; self.ingress_depth=None
        self.last=self.now(); self.phase='header_wait'; self.response_start=None

    def now(self):
        return self.owner.wall(), self.owner.cpu() if self.owner.cpu is not None else None

    def add(self, phase, start, end):
        wall=end[0]-start[0]
        cpu=None if start[1] is None or end[1] is None else end[1]-start[1]
        if wall < 0 or (cpu is not None and cpu < 0): raise ValueError('Timing clock regressed')
        old=self.values.get(phase, (0, None if cpu is None else 0, 0))
        self.values[phase]=(old[0]+wall, None if cpu is None or old[1] is None else old[1]+cpu, old[2]+1)

    def mark(self, phase):
        if self.closed: return
        try:
            if phase not in PHASES: raise ValueError('Unknown response phase')
            now=self.now(); self.add(self.phase,self.last,now); self.last=now; self.phase=phase
            if phase == 'parse_cache' and self.response_start is None: self.response_start=now
        except Exception: self.closed=True; self.owner.error()

    def start(self, phase):
        if self.closed: return
        try:
            if phase not in PHASES or phase in self.open: raise ValueError('Invalid nested phase')
            self.open[phase]=self.now()
        except Exception: self.closed=True; self.owner.error()

    def stop(self, phase):
        if self.closed: return
        try: self.add(phase,self.open.pop(phase),self.now())
        except Exception: self.closed=True; self.owner.error()

    def discard(self):
        self.closed=True

    def observe_queue(self, buffer, *, ingress=False):
        if self.closed or buffer is None: return
        try: self.queue_depth(buffer.queue.qsize(), ingress=ingress)
        except Exception: self.owner.error()

    def queue_depth(self, depth, *, ingress=False):
        if self.closed: return
        if type(depth) is int and depth >= 0:
            if ingress: self.ingress_depth=depth
            if len(self.depths) < 64: self.depths.append(depth)

    def finish(self, outcome='aborted', *, response_sent=False):
        if self.closed: return
        self.closed=True
        try:
            now=self.now(); self.add(self.phase,self.last,now)
            for phase,start in self.open.items(): self.add(phase,start,now)
            if response_sent and self.response_start is not None:
                self.add('response_total',self.response_start,now)
            self.owner.record(self, outcome)
        except Exception: self.owner.error()


def interval_summary(current, previous=None):
    """Non-draining selected-frame means from fresh cumulative counter deltas."""
    if not isinstance(current, dict) or not current.get('available', False):
        return dict(available=False, reason='response observer unavailable')
    same = (isinstance(previous, dict) and previous.get('process_id') == current['process_id']
            and previous.get('instance_monotonic_ns') == current['instance_monotonic_ns'])
    now=current['groups']['selected']; old=previous['groups']['selected'] if same else None
    if old is not None and now['selected_identity_changes'] != old['selected_identity_changes']:
        return dict(available=False, reason='selected client/connection changed')
    means={}
    for phase, distributions in now['phases'].items():
        means[phase]={}
        for clock,d in distributions.items():
            before=old['phases'][phase][clock] if old is not None else dict(count=0,sum_ms=0.)
            count=d['count']-before['count']; total=d['sum_ms']-before['sum_ms']
            if count < 0 or total < -1e-7: return dict(available=False, reason='response counters regressed')
            means[phase][clock]=total/count if count else None
    return dict(available=True, response_samples=now['phases']['response_total']['wall']['count']-
        (old['phases']['response_total']['wall']['count'] if old is not None else 0),
        means_ms=means, ingress_queue_depth_last=now['ingress_queue_depth_last'],
        ingress_queue_depth_max_cumulative=now['ingress_queue_depth_max'],
        selected_identity=now['last_sample_identity'])


def format_interval_row(summary):
    """One extra tabular console row; all latency columns are selected means."""
    if not summary.get('available', False):
        return '[RESPONSE] unavailable: ' + summary.get('reason','unknown')
    means=summary['means_ms']
    def value(phase, clock='wall'):
        v=means[phase][clock]
        return '     -' if v is None else f'{v:6.2f}'
    depth=summary['ingress_queue_depth_last']
    return ('[RESPONSE] ' + f"{summary['response_samples']:6d} " +
        ' '.join(value(p,c) for p,c in (('response_total','wall'),('response_total','thread_cpu'),
            ('parse_cache','wall'),('client_lock_wait','wall'),('client_lock_hold','wall'),
            ('journal','wall'),('metrics_aggregate','wall'),('previous_step','wall'),
            ('enqueue_wait','wall'),('inference','wall'),('action_write','wall'))) +
        f" {str(depth) if depth is not None else '-':>6} {summary['ingress_queue_depth_max_cumulative']:6d}")


def report_fields(snapshot, summary):
    """Stable numeric CSV columns plus the bounded cumulative source snapshot."""
    import json
    result=dict(response_schema=SCHEMA, response_available=bool(summary.get('available',False)),
        response_error=summary.get('reason',''), response_process_id=snapshot.get('process_id'),
        response_instance_ns=snapshot.get('instance_monotonic_ns'),
        response_selected_samples=summary.get('response_samples'),
        response_ingress_queue_depth_last=summary.get('ingress_queue_depth_last'),
        response_ingress_queue_depth_max_cumulative=summary.get('ingress_queue_depth_max_cumulative'),
        response_snapshot_json=json.dumps(snapshot,allow_nan=False,separators=(',',':')))
    for phase in PHASES:
        for clock in ('wall','thread_cpu'):
            result['response_selected_'+phase+'_'+clock+'_mean_ms'] = (
                summary.get('means_ms',{}).get(phase,{}).get(clock))
    return result
