"""Unselected reusable main-health engine and memory-bounded raw reviewer.

Uses the unchanged source-pinned capture/Writer/physical/recipe/pipeline/bank/
autosave engine, with the mixed complete-window transport reviewer. No module-
import actions, policy load, main mutations, signals or scientific qualification.
"""
import copy
import json
from pathlib import Path
import threading
import time


def require(value,message):
    if not value:raise ValueError(message)


def dependencies(job,h):
    for pin in job['sources'].values():h.checked(pin)
    modules={}
    for key in ('collector','primitives','transport','proc_repeat','mixed_transport','health','supervision','indexed_join'):
        modules[key]=h.load('_owned_main_health_'+key+'_'+str(time.monotonic_ns()),Path(job['sources'][key]['path']))
    return modules


class MainHealth:
    """Reusable engine for a future native observer; original bytes queued first."""
    def __init__(self,job,output,h,prior_groups=()):
        self.job=copy.deepcopy(job);self.h=h;self.output=Path(output);self.lock=threading.RLock();self.closed=False
        self.started_monotonic_s=time.monotonic();self.started_unix_s=time.time();self.statuses=[]
        modules=dependencies(job,h);self.modules=modules
        self.collector=None
        try:
            self.collector=modules['collector'].Collector(self.job,self.output)
            collector=self.collector
            collector.p=modules['indexed_join'].bind(collector.p)
            collector.stream=modules['mixed_transport'].Stream(collector.p,collector.transport,modules['proc_repeat'],
                collector.main,collector.initial_cursors,collector.p.LUA_SHA,prior_groups)
            self.initial_cursors=h.put(self.output/'initial-log-cursors.json',collector.initial_cursors)
        except BaseException:
            if self.collector is not None and not self.collector.writer.closed:self.collector.writer.close()
            raise

    def observe(self):
        with self.lock:
            require(not self.closed,'Original health observer already closed')
            status=self.collector.observe();self.statuses.append(status);return status

    def close(self):
        with self.lock:
            require(not self.closed,'Original health observer already closed');self.closed=True
            result=self.collector.close()
            result.update(schema='robotron-owned-main-full-health-closed-report-v2',
                initial_cursors=self.initial_cursors,actual_status=self.statuses,
                guard_started_monotonic_s=self.started_monotonic_s,guard_started_unix_s=self.started_unix_s,
                guard_ended_monotonic_s=time.monotonic(),guard_ended_unix_s=time.time(),
                health_job=self.job,quality_qualified=False)
            return result

    def preserve_failure(self,error):
        """Drain original bytes without manufacturing a closed/valid health report."""
        with self.lock:
            self.closed=True;collector=self.collector;writer=None;writer_error=None
            if not collector.writer.closed:
                try:writer=collector.writer.close()
                except BaseException as failure:writer_error=repr(failure)
            return dict(status='ORIGINAL_MAIN_FULL_HEALTH_FAILURE_PRESERVED',error=repr(error),
                original_collector_error=collector.failed,initial_cursors=self.initial_cursors,
                samples=copy.deepcopy(collector.writer.records),observed_samples=collector.index,
                deep_samples=collector.deep_count,actual_status=self.statuses,writer=writer,
                writer_error=writer_error,writer_thread_alive=collector.writer.thread.is_alive(),
                health_job=self.job,quality_qualified=False)


def replay(job,sample_pins,initial_cursors,read,h,*,prior_groups=(),original_statuses=None):
    """Read each immutable original sample once; retain only current evidence windows.

    Caller must authenticate this source and the selected job and independently
    verify the original native scope, intervals, writers, lease and game/life
    receipts. Prior groups must come from already source-bound original closed
    raw replay, and final campaign review must preserve that whole four-leg chain.
    """
    modules=dependencies(job,h)
    p=modules['indexed_join'].bind(modules['primitives']);cap=modules['transport'];proc=modules['proc_repeat']
    mixed=modules['mixed_transport'];health=modules['health'];sup=modules['supervision'];base=modules['collector']
    main=read(job['binding']);policy=read(main['supervision_policy']);baseline=read(main['baseline_API'])
    proof=health.verify_sources(Path(job['sources']['window']['path']).read_bytes(),
        Path(job['sources']['supervision']['path']).read_bytes(),Path(job['sources']['health']['path']).read_bytes())
    require(type(sample_pins)is list and sample_pins,'Every original main sample required')
    if original_statuses is not None:require(len(original_statuses)==len(sample_pins),'Original status/sample count differs')
    stream=mixed.Stream(p,cap,proc,main,initial_cursors,p.LUA_SHA,prior_groups)
    previous_API=None;previous_deep=None;last_deep=None;deep_count=0;begin=end=None
    first_deep=None;first_work=None;counts={};pending=0;max_gap=0.;previous_now=None
    for index,pin in enumerate(sample_pins):
        record=read(pin);sample=base.unpacked(record);API=p.decode(sample['raw_API'])
        require(sample['index']==index,'Original sample skipped/reordered/duplicated')
        now=sample['observed_unix_s'];begin=now if begin is None else begin;end=now
        if previous_now is not None:max_gap=max(max_gap,now-previous_now)
        previous_now=now
        if record['deep']is not None:
            deep=record['deep'];health.physical(sup,policy,deep['snapshot'],previous_deep)
            health.autosave(deep['autosave'],deep['checked_unix_s'])
            require(deep['held197_checked_live']is True and deep['held_error']is None
                and deep['snapshot']['unix_s']<=deep['checked_unix_s']<=sample['API_begin_unix_s']
                and deep['autosave']['uid']==job['binding']['identity']['uid'],
                'Original deep census/source/autosave is not bracketed')
            previous_deep=deep['snapshot'];last_deep=deep;deep_count+=1
            if first_deep is None:first_deep=deep['snapshot']
        require(last_deep is not None and 0<=now-last_deep['checked_unix_s']<=10,
                'Original sample lacks fresh full physical/source/autosave coverage')
        health.sample(p,API,baseline,main['experiment'],now,previous_API)
        if first_work is None:first_work=(API['learner_frame_count'],API['training_steps'])
        phase=stream.observe(sample)
        if original_statuses is not None:
            status=original_statuses[index]
            require(status['index']==index and status['phase']==phase
                and status['learner_frames']==API['learner_frame_count']
                and status['training_steps']==API['training_steps']and status['fleet_fps']==API['fps'],
                'Original cached phase/work clocks differ from raw replay')
        pending+=int(phase['overlap_pending']);name=str(API['client_count']);counts[name]=counts.get(name,0)+1
        previous_API=API
    summary=stream.close();require(deep_count>=3,'Original full health census coverage incomplete')
    require(len(main['held_hashes'])==197 and all(h.pin(path)['sha256']==sha
        for path,sha in main['held_hashes'].items()),'Original197 held inputs changed at independent readback')
    return dict(schema='robotron-owned-main-full-health-raw-replay-v2',samples=len(sample_pins),
        deep_samples=deep_count,API_count_histogram=counts,pending_samples=pending,
        first_observed_unix_s=begin,last_observed_unix_s=end,original_capture_span_s=end-begin,
        maximum_observation_gap_s=max_gap,first_deep_monotonic_s=first_deep['collection_started_monotonic_s'],
        last_deep_monotonic_s=last_deep['snapshot']['monotonic_s'],first_learner_frames=first_work[0],
        first_training_steps=first_work[1],
        final_learner_frames=previous_API['learner_frame_count'],final_training_steps=previous_API['training_steps'],
        transport=summary,source_specialization=proof,all197_held_inputs_final_independently_hashed=True,
        caller_original_native_scope_interval_writer_and_game_review_still_required=True,
        scientific_guard_selected=False,quality_qualified=False)
