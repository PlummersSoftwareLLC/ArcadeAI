"""Unselected cap/local-anchor transaction prototype; no installer or transport.

The installed learner never imports this file. Future activation is BLOCKED until
all mutable recipe writers honor one reviewed guard lease. A synthetic lease can
exercise the transaction in a later CPU scope; it is not production authority.
No model, optimizer, scaler, replay rows, lifetime or schedule counters are reset.
"""
import hashlib
import json
import math
import os
import stat
from pathlib import Path
import threading
import time

FIELDS=('process_id','instance_monotonic_ns','epoch','epoch_reason')
WRITERS=('learning_control_refresh','keyboard_recipe_and_training_flags',
         'HTTP_game_settings','socket_effective_epsilon_and_expert')


def require(ok,reason):
    if not ok:
        raise ValueError(reason)


def clone(value):
    return json.loads(json.dumps(value,sort_keys=True,allow_nan=False))


def publish_exclusive(path,value):
    # No retry, replace, truncate or second chmod of an already published file.
    data=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(data);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def verify_owner_and_sources(binding):
    # Future runtime use only; authoring/AST review never invokes this function.
    pid=os.getpid()
    birth=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    require(binding['owner']==dict(pid=pid,birth_ticks=birth,
        invocation_id=os.environ.get('INVOCATION_ID')),'Actual original process owner differs')
    values=[*binding['source_context'],*binding['cooperating_writer_source_pins'].values()]
    for value in values:
        path=Path(value['path']);before=path.lstat()
        require(path.is_absolute() and stat.S_ISREG(before.st_mode) and not stat.S_ISLNK(before.st_mode)
            and path.suffix in ('.py','.json','.service','.conf'),
            'Held source/control metadata only; no model/replay/ROM body reads')
        actual=dict(device=before.st_dev,inode=before.st_ino,bytes=before.st_size,
            mtime_ns=before.st_mtime_ns,ctime_ns=before.st_ctime_ns,mode=oct(stat.S_IMODE(before.st_mode)),
            uid=before.st_uid,nlink=before.st_nlink)
        require(value['identity']==actual and value['bytes']==before.st_size and before.st_nlink==1
            and before.st_uid==os.getuid(),'Selected source/control identity differs')
        data=path.read_bytes();after=path.lstat()
        require((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns,
                stat.S_IMODE(after.st_mode),after.st_uid,after.st_nlink)
                ==tuple(actual[k] if k!='mode' else int(actual[k],8)
                    for k in ('device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'))
                and hashlib.sha256(data).hexdigest()==value['sha256'],
            'Selected source/control bytes changed')


def activation_adapter_unimplemented(*args,**kwargs):
    # Deliberately no environment flag, file poller, attach, live API or hotwrite.
    raise RuntimeError('UNQUALIFIED: cooperating recipe-writer lease and source-bound installation are not implemented')


class EffectiveCapLocalAnchorPrototype:
    """Bounded generation state; attach is not provided by this proposal.

    ``guard_lease`` must in a future reviewed integration serialize ALL WRITERS,
    publish the selected actual owner/source/recipe context, and be acquired
    BEFORE training_lock. Existing production writers do not honor such a lease.
    This is a real activation blocker, not an assumed quiescent interval.
    """
    def __init__(self,*,initial_cap,initial_anchor,binding,guard_lease,receipt_directory):
        require(type(initial_cap) in (int,float) and not isinstance(initial_cap,bool)
                and math.isfinite(initial_cap) and initial_cap==8,'Prototype baseline must be cap8')
        require(callable(guard_lease),'No transition without an explicit cooperating guard lease')
        require(set(initial_anchor)=={'frame_count','measurement_frame_count','optimized_samples'}
                and all(type(v)is int and v>=0 for v in initial_anchor.values()),'Exact existing local anchor required')
        require(set(binding)=={'owner','source_context','recipe','optimizer_lineage','replay_lineage',
                    'cooperating_writer_source_pins'} and binding['source_context']
                and set(binding['cooperating_writer_source_pins'])==set(WRITERS),
                'Owner/epoch/source/recipe and all cooperating writer sources must be bound')
        self._binding_wire=json.dumps(binding,sort_keys=True,allow_nan=False);self.guard_lease=guard_lease
        self.directory=Path(receipt_directory)
        require(self.directory.is_absolute() and self.directory.is_dir()
                and self.directory.resolve(strict=True)==self.directory
                and self.directory.stat().st_uid==os.getuid()
                and stat.S_IMODE(self.directory.stat().st_mode)==0o700
                and not self.directory.is_symlink() and not any(self.directory.iterdir()),
                'Root-created fresh empty owned receipt directory required')
        self._lock=threading.Lock();self._pending=None;self._request_event=threading.Event()
        self._state=dict(generation=0,effective_cap=float(initial_cap),local_anchor=clone(initial_anchor),
                        status='READY',request_sha256=None,apply_receipt=None,last_error=None)
        self._used=set()

    @property
    def binding(self):
        return json.loads(self._binding_wire)

    def snapshot(self):
        with self._lock:return clone(self._state)

    def submit(self,request):
        """In-process API only. An external authority/transport is not provided."""
        value=clone(request)
        require(set(value)=={'schema','generation','expected_generation','expected_cap','target_cap',
            'binding','request_id','no_retry'} and value['schema']=='robotron-prospective-effective-cap-local-anchor-request-v1'
            and value['binding']==self.binding and value['no_retry']is True,
            'Exact explicit generation, source/owner/epoch/recipe-bound no-retry request required')
        require(type(value['generation'])is int and type(value['expected_generation'])is int
            and type(value['request_id'])is str and len(value['request_id'])==64
            and all(c in '0123456789abcdef' for c in value['request_id'])
            and type(value['target_cap'])in (int,float) and not isinstance(value['target_cap'],bool)
            and value['generation'] in (1,2)
            and value['target_cap']==(12 if value['generation']==1 else 8),
            'This bounded prototype defines only cap8 to12 to8, one request per generation')
        with self._lock:
            require(self._state['status']=='READY' and self._pending is None
                and value['request_id']not in self._used
                and value['expected_generation']==self._state['generation']
                and value['generation']==self._state['generation']+1
                and value['expected_cap']==self._state['effective_cap']
                and value['target_cap']!=self._state['effective_cap'],'Duplicate/stale/overlapping generation refused')
            self._pending=value;self._request_event.set()

    def replay_pressure_reached(self,agent,metrics,cfg):
        # One lock captures cap, anchor and generation together. No prefetch or
        # replay-lock operation occurs while this lock or metrics.lock is held.
        with self._lock:
            state=self._state
            if state['status']!='READY':return True
            with metrics.lock:
                frames=int(metrics.frame_count)
                measured=int(getattr(metrics,'measurement_frame_count',0))
                samples=int(agent.optimized_samples)
            anchor=state['local_anchor'];cap=state['effective_cap']
            if getattr(agent,'_replay_warmup_pending',False):return True
            minimum=max(int(cfg.min_replay_to_train),int(cfg.batch_size))
            if len(agent.memory)<minimum:return True
            if (samples<anchor['optimized_samples'] or frames<anchor['frame_count']
                    or measured<anchor['measurement_frame_count']):return True
            delta_samples=max(0,samples-anchor['optimized_samples'])
            delta_frames=frames-anchor['frame_count']-max(0,measured-anchor['measurement_frame_count'])
            return delta_samples/max(1,delta_frames)>=cap

    def service_at_boundary(self,agent,metrics,cfg,*,pending_batch):
        """Called before the learner fetches its next batch, never from producer.

        Host lock order: cooperating recipe lease -> training -> prefetch pause
        (with NO budget/metrics/replay lock) -> replay -> budget -> metrics.
        All old producer work must finish its invalidate epoch; queued batches
        are discarded. A pending learner lease is forbidden, not inferred gone.
        RLocks and invalidation do not assert that all GPU streams are idle.
        """
        if not self._request_event.is_set():return False
        require(pending_batch is None,'Learner already owns a prepared batch')
        request=None;committed=False
        try:
            with self.guard_lease() as observed:
                require(observed==self.binding,'Actual cooperating source/owner/epoch/recipe guard differs')
                verify_owner_and_sources(self.binding)
                with agent._training_lock:
                    with self._lock:
                        require(self._state['status']=='READY' and self._pending is not None,'No eligible one-shot request')
                        request=self._pending;self._pending=None;self._request_event.clear()
                        self._used.add(request['request_id']);self._state['status']='APPLYING_HELD'
                        self._state['request_sha256']=hashlib.sha256(json.dumps(request,sort_keys=True,
                            separators=(',',':'),allow_nan=False).encode()).hexdigest()
                    intent=publish_exclusive(self.directory/('generation-'+str(request['generation'])+'-intent.json'),
                        dict(schema='robotron-prospective-effective-cap-local-anchor-intent-v1',request=request,
                            original_budget=self.snapshot(),commit_not_yet_observed=True,no_retry=True))
                    require(not agent._prefetch_paused,'A different prefetch hold already exists')
                    agent._pause_prefetch()
                    require(agent.training_enabled and getattr(metrics,'training_enabled',True)
                        and (not agent._exact_graph_requested or agent._exact_graph_loaded)
                        and not getattr(agent,'_continuous_startup_held',False)
                        and not getattr(metrics,'measurement_active',False)
                        and not getattr(metrics,'ratchet_frozen',False),'Learner/graph/measurement/ratchet boundary differs')
                    require(int(cfg.batch_size)==4096 and int(cfg.n_step)==3
                        and str(cfg.per_priority_metric)=='ce' and float(cfg.max_samples_per_frame)==8,
                        'Startup recipe changed; effective cap must not mutate RL_CONFIG')
                    require(self.binding['recipe']==dict(batch_size=4096,n_step=3,priority_metric='ce',
                        startup_cap=8,lr=3.125e-6,epsilon=.1,expert_ratio=.1,continuous_mode='1')
                        and agent.get_lr()==3.125e-6
                        and os.environ.get('ROBOTRON_CONTINUOUS_TRAINING_MODE')=='1',
                        'Exact held current recipe and continuous startup mode required')
                    phase=agent._priority_phase
                    require(phase is not None,'Actual restored CE phase is required')
                    phase.require_ready('ce')
                    outcome=agent._learning_optimizer_exposure.snapshot()
                    require(outcome['enabled']is True and outcome['available']is True
                        and {k:outcome[k]for k in FIELDS}==self.binding['optimizer_lineage']
                        and outcome['total']['attempts_started']==outcome['total']['outcomes_recorded']
                        and outcome['total']['unavailable']==0
                        and outcome['total']['outcomes_recorded']==outcome['total']['applied']+outcome['total']['amp_skipped'],
                        'A started/unclassified/unavailable optimizer outcome remains')
                    verify_owner_and_sources(self.binding)
                    # Hold the real replay lock across epoch verification AND
                    # commit. A training lock alone does not fence clear/flush.
                    with agent.memory.lock:
                        replay=agent.memory._insert_exposure.snapshot()
                        require(replay['enabled']is replay['available']is True
                            and {k:replay[k]for k in FIELDS}==self.binding['replay_lineage'],
                            'Current replay lineage differs')
                        require(len(agent.memory)>=max(int(cfg.batch_size),int(cfg.min_replay_to_train))
                            and not getattr(agent,'_replay_warmup_pending',False),'Replay is not ready')
                        with self._lock:
                            with metrics.lock:
                                require(abs(float(metrics.epsilon)-.1)<1e-12
                                    and abs(float(metrics.expert_ratio)-.1)<1e-12,
                                    'Effective actor recipe differs under the cooperating writer lease')
                                before=dict(training_steps=int(agent.training_steps),optimized_samples=int(agent.optimized_samples),
                                    metric_training_steps=int(metrics.total_training_steps),
                                    metric_optimized_samples=int(metrics.total_optimized_samples),
                                    last_target_update_samples=int(agent.last_target_update_samples),
                                    last_inference_sync_samples=int(agent.last_inference_sync_samples))
                                anchor=dict(frame_count=int(metrics.frame_count),
                                    measurement_frame_count=int(getattr(metrics,'measurement_frame_count',0)),
                                    optimized_samples=int(agent.optimized_samples))
                                previous=clone(self._state)
                                self._state.update(generation=request['generation'],effective_cap=float(request['target_cap']),
                                    local_anchor=anchor,status='COMMITTED_HELD')
                                committed=True
                    # No budget/metrics/replay lock is held during invalidate.
                    # Budget remains HELD so producer enabled_fn cannot sample
                    # even when _resume_prefetch clears its separate pause flag.
                    agent._resume_prefetch()
                    receipt=dict(schema='robotron-prospective-effective-cap-local-anchor-apply-receipt-v1',
                        status='CAP_AND_LOCAL_ANCHOR_COMMITTED_LEARNING_HELD_UNTIL_RECEIPT_PUBLICATION_RETURNS',
                        intent=intent,request=request,previous_budget=previous,committed_budget=self.snapshot(),
                        preserved_learner_counters=before,optimizer_outcomes=outcome,replay_lineage=replay,
                        owner_source_recipe_guard=self.binding,observed_monotonic_ns=time.monotonic_ns(),
                        lifetime_model_optimizer_scaler_replay_schedule_or_legacy_anchor_reset=False,
                        producer_invalidation_completed=True,learner_pending_batch_was_None=True,
                        physical_GPU_idle_claimed=False,actual_postpublication_work_observed=None)
                    receipt_pin=publish_exclusive(self.directory/('generation-'+str(request['generation'])+'-apply.json'),receipt)
                    with self._lock:
                        self._state['apply_receipt']=receipt_pin;self._state['status']='READY'
                    return True
        except Exception as error:
            # An after-commit I/O/guard/pause error never silently reverts cap,
            # retries, or reaches the learner's CE-phase invalidation handler.
            with self._lock:
                self._state['status']='BLOCKED_UNSEALED_NO_RETRY'
                self._state['last_error']=dict(type=type(error).__name__,message=str(error),committed=committed)
            try:publish_exclusive(self.directory/'blocked-no-retry.json',dict(
                schema='robotron-prospective-effective-cap-local-anchor-blocked-v1',request=request,
                state=self.snapshot(),automatic_retry_or_rollback_performed=False))
            except Exception:pass
            return False
