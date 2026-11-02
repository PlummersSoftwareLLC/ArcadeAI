"""Unselected fast-scope refinement; same v1 data ABI, sampling and scope.

Reuse only the v1 bounded recorder and coverage decoder. Its generator-based
frame/enqueue/consume helpers are never called. No live source integration.
Closed-capture tickets keep recording admitted frame/command completion tails.
"""
from contextlib import contextmanager
import threading
import matched_frame_trace_v1 as _base

_lock=threading.Lock()
_active=None
_generation=0
_routes={}
_local=threading.local()


class Recorder(_base.Recorder):
    def snapshot(self):
        result=super().snapshot()
        with _lock:result['pending_routes']=sum(t[0] is self for t in _routes.values())
        result['implementation']='fast-scopes-v2'
        return result


_fault=_base._fault
validate_snapshot=_base.validate_snapshot


class _Noop:
    __slots__=()
    def __enter__(self):return None
    def __exit__(self,*args):return False


_NOOP=_Noop()


def connection(cid,slot):
    global _generation
    try:
        with _lock:_generation+=1;generation=_generation
        return [int(cid),int(slot),generation,0]
    except Exception:
        if _active is not None:_fault(_active)
        return None


@contextmanager
def capture(recorder):
    global _active
    if type(recorder) is not Recorder:raise TypeError('Exact explicit recorder required')
    with _lock:
        if _active is not None or _routes:raise RuntimeError('Prior capture or replay commands remain active')
        _active=recorder
    try:yield recorder
    finally:
        with _lock:_active=None


def mark(ticket,phase,metadata=None):
    # Avoid **kwargs allocation on every uncaptured source marker.
    if ticket is None:return
    recorder=ticket[0]
    try:
        if not isinstance(phase,str) or not 1<=len(phase)<=64:raise ValueError('Bounded diagnostic phase required')
        if metadata is None:metadata={}
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


class _FrameScope:
    __slots__=('connection','recorder','ticket','previous','previous_scope')
    def __init__(self,connection,recorder):
        self.connection,self.recorder=connection,recorder;self.ticket=None
        self.previous=getattr(_local,'frame',None);self.previous_scope=getattr(_local,'in_frame',False)
    def __enter__(self):
        try:
            if self.connection is not None:
                self.connection[3]+=1
                if self.recorder is not None:self.ticket=self.recorder.frame(self.connection)
            elif self.recorder is not None:_fault(self.recorder)
            _local.frame=self.ticket;_local.in_frame=True
            mark(self.ticket,'handler_begin')
        except Exception:
            if self.recorder is not None:_fault(self.recorder)
        return self.ticket
    def __exit__(self,kind,error,tb):
        if kind is not None:mark(self.ticket,'handler_exception',{'error':kind.__name__})
        mark(self.ticket,'handler_exit')
        try:_local.frame=self.previous;_local.in_frame=self.previous_scope
        except Exception:
            if self.recorder is not None:_fault(self.recorder)
        return False


def frame(connection):
    recorder=_active
    try:
        if recorder is None and getattr(_local,'frame',None) is None:
            # Source uses this factory only in a with statement. Keep its connection
            # frame sequence advancing while the capture admission window is shut.
            if connection is not None:connection[3]+=1
            return _NOOP
        return _FrameScope(connection,recorder)
    except Exception:
        if recorder is not None:_fault(recorder)
        return _NOOP


def frame_mark(phase):
    try:
        ticket=getattr(_local,'frame',None)
        if ticket is not None:mark(ticket,phase)
    except Exception:
        if _active is not None:_fault(_active)


def new_request():
    parent=None
    try:
        parent=getattr(_local,'frame',None)
        if parent is None:
            recorder=_active
            if recorder is not None and not getattr(_local,'in_frame',False):
                with recorder.lock:recorder.unmatched_inference+=1
            return None
        ticket=parent[0].child(parent,'inference');mark(ticket,'begin');return ticket
    except Exception:
        recorder=parent[0] if parent is not None else _active
        if recorder is not None:_fault(recorder)
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
    # Keep the same lock and publication-before-queue-put ordering as v1.
    # A closed capture may still have an admitted command in flight.
    with _lock:return _routes.get(id(item))


def _remove_route_id(item_id,ticket):
    try:
        with _lock:
            if _routes.get(item_id) is ticket:_routes.pop(item_id,None)
    except Exception:_fault(ticket[0])


class _EnqueueScope:
    __slots__=('parent','item_id','command','client_id','ticket','previous','admitted')
    def __init__(self,parent,item):
        self.parent=parent;self.item_id=id(item);self.command=item[0];self.client_id=item[1]
        self.ticket=None;self.previous=getattr(_local,'enqueue',None);self.admitted=False
    def __enter__(self):
        try:
            if type(self.command) is not str or len(self.command)>32 or type(self.client_id) not in (int,type(None)):
                raise ValueError('Primitive bounded command identity required')
            self.ticket=self.parent[0].child(self.parent,'commands',dict(command=self.command,client_id=self.client_id))
            if self.ticket is not None:
                with _lock:
                    if self.item_id in _routes:raise ValueError('Duplicate command identity')
                    _routes[self.item_id]=self.ticket
            mark(self.ticket,'enqueue_attempt');_local.enqueue=self
        except Exception:_fault(self.parent[0])
        return None
    def __exit__(self,*args):
        if self.ticket is not None:
            mark(self.ticket,'enqueue_return',{'admitted':self.admitted})
            if not self.admitted:_remove_route_id(self.item_id,self.ticket)
        try:_local.enqueue=self.previous
        except Exception:_fault(self.parent[0])
        return False


def enqueue(item):
    parent=None
    try:
        parent=getattr(_local,'frame',None)
        if parent is not None:return _EnqueueScope(parent,item)
        recorder=_active
        if recorder is not None and not getattr(_local,'in_frame',False):
            command=item[0]
            if command in ('step','boost','elite','reset_client','barrier'):
                with recorder.lock:recorder.unmatched_commands[command]=recorder.unmatched_commands.get(command,0)+1
        return _NOOP
    except Exception:
        recorder=parent[0] if parent is not None else _active
        if recorder is not None:_fault(recorder)
        return _NOOP


def enqueue_succeeded(item):
    scope=None
    try:
        scope=getattr(_local,'enqueue',None)
        if scope is None or scope.item_id!=id(item):return
        scope.admitted=True;mark(scope.ticket,'enqueue_succeeded')
    except Exception:
        if scope is not None:_fault(scope.parent[0])


def dequeued(item):
    try:
        ticket=_route(item)
        if ticket is not None:mark(ticket,'dequeued')
    except Exception:
        if _active is not None:_fault(_active)


class _ConsumeScope:
    __slots__=('ticket','item_id','previous')
    def __init__(self,item_id,ticket,previous):
        self.ticket,self.item_id,self.previous=ticket,item_id,previous
    def __enter__(self):
        try:_local.consumer=self.ticket;mark(self.ticket,'consumer_begin')
        except Exception:
            if self.ticket is not None:_fault(self.ticket[0])
        return None
    def __exit__(self,kind,error,tb):
        if kind is not None:mark(self.ticket,'consumer_exception',{'error':kind.__name__})
        mark(self.ticket,'consumer_end')
        if self.ticket is not None:_remove_route_id(self.item_id,self.ticket)
        try:_local.consumer=self.previous
        except Exception:
            if self.ticket is not None:_fault(self.ticket[0])
        return False


def consume(item):
    try:
        ticket=_route(item);previous=getattr(_local,'consumer',None)
        if ticket is None and previous is None:return _NOOP
        return _ConsumeScope(id(item),ticket,previous)
    except Exception:
        if _active is not None:_fault(_active)
        return _NOOP


def consumer_mark(phase):
    try:
        ticket=getattr(_local,'consumer',None)
        if ticket is not None:mark(ticket,phase)
    except Exception:
        if _active is not None:_fault(_active)


def insert_accepted(exposure,category):
    ticket=None
    try:
        ticket=getattr(_local,'consumer',None)
        if ticket is None:return
        mark(ticket,'insert_accepted',dict(process_id=exposure.process_id,
            instance_monotonic_ns=exposure.instance_monotonic_ns,epoch=exposure.epoch,category=category))
    except Exception:
        recorder=ticket[0] if ticket is not None else _active
        if recorder is not None:_fault(recorder)
