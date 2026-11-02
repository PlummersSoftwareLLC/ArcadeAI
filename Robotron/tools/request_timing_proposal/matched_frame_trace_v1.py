"""Unselected bounded host trace linking handler, inference and replay commands.

No environment activation, file, process, GPU, network or replay-array access.
Tickets retain primitive metadata only. All timing uses perf_counter_ns.
This proposal has not entered either live source package.
"""
from contextlib import contextmanager
from copy import deepcopy
import threading
import time

_lock = threading.Lock()
_active = None
_generation = 0
_routes = {}  # id(command tuple) -> diagnostic ticket; never retain the tuple.
_local = threading.local()


class Recorder:
    def __init__(self, *, max_frames=2048, sample_every=128, max_children=16,
                 max_events=64, clock=time.perf_counter_ns):
        for value, ceiling in [(max_frames,4096),(sample_every,1048576),
                               (max_children,32),(max_events,128)]:
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError('Positive bounded integer trace limits required')
        self.max_frames,self.sample_every=max_frames,sample_every
        self.max_children,self.max_events=max_children,max_events
        self.clock=clock
        self.lock=threading.Lock()
        self.frames={}
        self.seen=self.capacity_drops=self.event_drops=self.child_drops=0
        self.unmatched_inference=self.faults=0
        self.unmatched_commands={}

    def frame(self, connection):
        with self.lock:
            sequence=self.seen;self.seen+=1
            if sequence % self.sample_every:
                return None
            if len(self.frames)>=self.max_frames:
                self.capacity_drops+=1;return None
            self.frames[sequence]=dict(frame_id=sequence,connection=list(connection),
                events=[],inference=[],commands=[])
        return (self,'frame',sequence,-1)

    def child(self, parent, kind, metadata=None):
        with self.lock:
            frame=self.frames[parent[2]];children=frame[kind]
            if len(children)>=self.max_children:
                self.child_drops+=1;return None
            index=len(children);children.append(dict(index=index,metadata=metadata or {},events=[]))
        return (self,kind,parent[2],index)

    def snapshot(self):
        with self.lock:
            result=dict(schema='robotron-matched-host-frame-trace-v1',clock='perf_counter_ns',
                limits=dict(max_frames=self.max_frames,sample_every=self.sample_every,
                    max_children=self.max_children,max_events=self.max_events),
                seen=self.seen,capacity_drops=self.capacity_drops,event_drops=self.event_drops,
                child_drops=self.child_drops,faults=self.faults,
                unmatched_inference=self.unmatched_inference,
                unmatched_commands=dict(self.unmatched_commands),
                frames=deepcopy(list(self.frames.values())))
        with _lock:
            result['pending_routes']=sum(t[0] is self for t in _routes.values())
        return result


def _fault(recorder):
    try:
        with recorder.lock:recorder.faults+=1
    except Exception:
        pass


def connection(cid, slot):
    global _generation
    try:
        with _lock:
            _generation+=1;generation=_generation
        return [int(cid),int(slot),generation,0]
    except Exception:
        if _active is not None:_fault(_active)
        return None


@contextmanager
def capture(recorder):
    global _active
    if type(recorder) is not Recorder:
        raise TypeError('Exact explicit recorder required')
    with _lock:
        if _active is not None or _routes:
            raise RuntimeError('Prior capture or replay commands remain active')
        _active=recorder
    try:yield recorder
    finally:
        with _lock:_active=None


def mark(ticket, phase, **metadata):
    if ticket is None:return
    recorder=ticket[0]
    try:
        if not isinstance(phase,str) or not 1 <= len(phase) <= 64:
            raise ValueError('Bounded diagnostic phase required')
        if any(not isinstance(k,str) or len(k)>64 or type(v) not in (str,int,bool,type(None))
               or isinstance(v,str) and len(v)>80 for k,v in metadata.items()):
            raise ValueError('Primitive bounded metadata required')
        with recorder.lock:
            stamp=recorder.clock()
            if type(stamp) is not int or stamp<0:raise ValueError('Finite integer clock required')
            row=recorder.frames[ticket[2]]
            if ticket[1]!='frame':row=row[ticket[1]][ticket[3]]
            if len(row['events'])>=recorder.max_events:recorder.event_drops+=1
            else:row['events'].append([phase,stamp,metadata])
    except Exception:_fault(recorder)


@contextmanager
def frame(connection):
    previous=getattr(_local,'frame',None);previous_scope=getattr(_local,'in_frame',False)
    ticket=None;recorder=_active
    try:
        if connection is not None:
            connection[3]+=1
            if recorder is not None:ticket=recorder.frame(connection)
        elif recorder is not None:_fault(recorder)
        _local.frame=ticket;_local.in_frame=True;mark(ticket,'handler_begin')
    except Exception:
        if recorder is not None:_fault(recorder)
    try:yield ticket
    except BaseException as error:
        mark(ticket,'handler_exception',error=type(error).__name__)
        raise
    finally:
        mark(ticket,'handler_exit')
        try:_local.frame=previous;_local.in_frame=previous_scope
        except Exception:
            if recorder is not None:_fault(recorder)


def frame_mark(phase):
    try:mark(getattr(_local,'frame',None),phase)
    except Exception:
        if _active is not None:_fault(_active)


def new_request():
    try:
        parent=getattr(_local,'frame',None)
        if parent is None:
            recorder=_active
            if recorder is not None and not getattr(_local,'in_frame',False):
                with recorder.lock:recorder.unmatched_inference+=1
            return None
        ticket=parent[0].child(parent,'inference');mark(ticket,'begin');return ticket
    except Exception:
        if _active is not None:_fault(_active)
        return None


def batch_begin(tickets):
    try:_local.batch=tuple(t for t in tickets if t is not None)
    except Exception:
        if _active is not None:_fault(_active)


def batch_mark(phase):
    try:
        for ticket in getattr(_local,'batch',()):mark(ticket,phase)
    except Exception:
        if _active is not None:_fault(_active)


def batch_end():
    try:_local.batch=()
    except Exception:
        if _active is not None:_fault(_active)


def _route(item):
    with _lock:return _routes.get(id(item))


def _remove_route(item,ticket):
    try:
        with _lock:
            if _routes.get(id(item)) is ticket:_routes.pop(id(item),None)
    except Exception:_fault(ticket[0])


@contextmanager
def enqueue(item):
    ticket=None
    try:
        parent=getattr(_local,'frame',None)
        recorder=_active
        if parent is None and recorder is not None and not getattr(_local,'in_frame',False):
            command=item[0]
            if command in ('step','boost','elite','reset_client','barrier'):
                with recorder.lock:
                    recorder.unmatched_commands[command]=recorder.unmatched_commands.get(command,0)+1
        if parent is not None:
            if type(item[0]) is not str or len(item[0])>32 or type(item[1]) not in (int,type(None)):
                raise ValueError('Primitive bounded command identity required')
            metadata=dict(command=item[0],client_id=item[1])
            # No args/kwargs, state, reward or actor object is retained.
            ticket=parent[0].child(parent,'commands',metadata)
            if ticket is not None:
                with _lock:
                    if id(item) in _routes:raise ValueError('Duplicate command identity')
                    _routes[id(item)]=ticket
            mark(ticket,'enqueue_attempt')
    except Exception:
        if _active is not None:_fault(_active)
    previous=getattr(_local,'enqueue',None)
    try:_local.enqueue=(id(item),ticket,False)
    except Exception:
        if ticket is not None:_fault(ticket[0])
    try:yield
    finally:
        scope=getattr(_local,'enqueue',None)
        admitted=scope is not None and scope[0]==id(item) and scope[2]
        mark(ticket,'enqueue_return',admitted=bool(admitted))
        if not admitted and ticket is not None:_remove_route(item,ticket)
        try:_local.enqueue=previous
        except Exception:
            if ticket is not None:_fault(ticket[0])


def enqueue_succeeded(item):
    try:
        scope=getattr(_local,'enqueue',None)
        if scope is not None and scope[0]==id(item):
            _local.enqueue=(id(item),scope[1],True)
            mark(scope[1],'enqueue_succeeded')
    except Exception:
        if _active is not None:_fault(_active)


def dequeued(item):
    try:mark(_route(item),'dequeued')
    except Exception:
        if _active is not None:_fault(_active)


@contextmanager
def consume(item):
    ticket=None;previous=getattr(_local,'consumer',None)
    try:ticket=_route(item);_local.consumer=ticket;mark(ticket,'consumer_begin')
    except Exception:
        if _active is not None:_fault(_active)
    try:yield
    except BaseException as error:
        mark(ticket,'consumer_exception',error=type(error).__name__)
        raise
    finally:
        mark(ticket,'consumer_end')
        if ticket is not None:_remove_route(item,ticket)
        try:_local.consumer=previous
        except Exception:
            if ticket is not None:_fault(ticket[0])


def consumer_mark(phase):
    try:mark(getattr(_local,'consumer',None),phase)
    except Exception:
        if _active is not None:_fault(_active)


def insert_accepted(exposure,category):
    """Called only after the original normal-ring-add exposure increment."""
    try:
        mark(getattr(_local,'consumer',None),'insert_accepted',
            process_id=exposure.process_id,instance_monotonic_ns=exposure.instance_monotonic_ns,
            epoch=exposure.epoch,category=category)
    except Exception:
        if _active is not None:_fault(_active)


def validate_snapshot(snapshot):
    """Coverage report, not performance/quality qualification or a deployment gate."""
    if snapshot.get('schema')!='robotron-matched-host-frame-trace-v1' or snapshot.get('clock')!='perf_counter_ns':
        raise ValueError('Exact matched trace schema required')
    limits=snapshot['limits'];seen=set();commands=inferences=accepted=complete=0
    frame_censored=command_censored=0
    for row in snapshot['frames']:
        key=row['frame_id']
        if type(key) is not int or key in seen or key%limits['sample_every'] or not 0<=key<snapshot['seen']:
            raise ValueError('Invalid or duplicate sampled frame ID')
        seen.add(key)
        if len(row['connection'])!=4 or any(type(x) is not int for x in row['connection']):
            raise ValueError('Exact primitive connection/frame identity required')
        channels=[row]+row['commands']+row['inference']
        for channel in channels:
            if len(channel['events'])>limits['max_events']:raise ValueError('Event bound exceeded')
            previous=-1
            for phase,stamp,metadata in channel['events']:
                if type(stamp) is not int or stamp<previous:raise ValueError('Nonmonotonic channel')
                previous=stamp
        frame_phases={p for p,t,m in row['events']}
        complete+=int('handler_exit' in frame_phases);frame_censored+=int('handler_exit' not in frame_phases)
        for channel in row['commands']:
            commands+=1;phases={p for p,t,m in channel['events']}
            accepted+=sum(p=='insert_accepted' for p,t,m in channel['events'])
            returns=[m for p,t,m in channel['events'] if p=='enqueue_return']
            admitted=bool(returns and returns[-1].get('admitted'))
            command_censored+=int(admitted and 'consumer_end' not in phases)
            if 'insert_accepted' in phases and channel['metadata']['command']!='step':
                raise ValueError('Non-step command claims an insert')
        inferences+=len(row['inference'])
    return dict(sampled_frames=len(seen),completed_handler_scopes=complete,
        incomplete_handler_scopes=frame_censored,inference_requests=inferences,
        replay_commands=commands,accepted_ring_add_events=accepted,
        incomplete_admitted_commands=command_censored,pending_routes=snapshot['pending_routes'],
        capture_loss={k:snapshot[k] for k in ['capacity_drops','event_drops','child_drops','faults']},
        unmatched_inference=snapshot['unmatched_inference'],production_deployed=False,
        unmatched_commands=snapshot['unmatched_commands'],
        quality_gain_verified=False,learning_speed_gain_verified=False)
