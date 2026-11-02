"""Collect-only first transport anomaly plus a fixed original raw tail.

Uses the unchanged source-pinned Collector/Writer/capture/nontransport engine.
The strict original transport reviewer remains rejected after its first error;
we never retry it or return an accepted health observation. No production writes,
signals, model loads, save requests or scientific qualification are performed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time


def require(value,message):
    if not value:raise ValueError(message)


def load(name,pin):
    path=Path(pin['path']);raw=path.read_bytes()
    require(len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Exact selected source required')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


class DiagnosticTransport:
    """Preserve strict rejection; keep raw capture active solely for diagnosis."""
    def __init__(self,original,clock=time.monotonic):
        self.original=original;self.clock=clock;self.first=None;self.samples=0;self.tail_samples=0
        self.closed=False;self.last_original_observed_unix_s=None

    def observe(self,sample):
        require(not self.closed,'Diagnostic transport already closed')
        self.samples+=1
        self.last_original_observed_unix_s=sample['observed_unix_s']
        if self.first is None:
            try:
                original_phase=self.original.observe(sample)
                return dict(phase='collect_only_strict_prefix',accepted=False,diagnostic_only=True,
                            original_phase=original_phase)
            except ValueError as error:
                self.first=dict(index=sample['index'],original_observed_unix_s=sample['observed_unix_s'],
                    observed_monotonic_s=self.clock(),error=repr(error))
                return dict(phase='collect_only_first_strict_rejection',accepted=False,diagnostic_only=True,
                            first_rejection=dict(self.first))
        self.tail_samples+=1
        return dict(phase='collect_only_tail_original_stream_still_rejected',accepted=False,diagnostic_only=True)

    def tail_complete(self):
        return self.first is not None and self.clock()-self.first['observed_monotonic_s']>=1. and \
            self.last_original_observed_unix_s-self.first['original_observed_unix_s']>=1.

    def close(self):
        require(not self.closed,'Diagnostic transport already closed');self.closed=True
        return dict(first_strict_rejection=self.first,samples=self.samples,tail_samples=self.tail_samples,
            strict_stream_retried=False,transport_accepted=False,health_qualified=False,quality_qualified=False,
            diagnostic_only=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Exact diagnostic source required')
    raw=Path(args.job).read_bytes();require(hashlib.sha256(raw).hexdigest()==args.job_sha256,'Exact diagnostic job required')
    job=json.loads(raw)
    require(job['schema']=='robotron-first-transport-anomaly-raw-tail-job-v1'and job['duration_s']==600
        and job['tail_s']==1 and job['poll_s']==.2 and os.environ.get('CUDA_VISIBLE_DEVICES')=='',
        'Fixed collect-only CPU diagnostic required')
    base=load('_anomaly_tail_base',job['sources']['collector'])
    output=Path(job['output']);output.mkdir(mode=0o700);(output/'samples').mkdir(mode=0o700)
    collector=None;statuses=[];started=time.monotonic();diagnostic=None
    try:
        collector=base.Collector(job,output);diagnostic=DiagnosticTransport(collector.stream);collector.stream=diagnostic
        collector.h.put(output/'initial-log-cursors.json',collector.initial_cursors)
        start=time.monotonic()
        while True:
            tick=time.monotonic()
            if tick-start>=600 and diagnostic.first is None:break
            require(tick-start<=602,'Fixed diagnostic tail deadline exceeded')
            statuses.append(collector.observe())
            if diagnostic.tail_complete():break
            time.sleep(max(0,.2-(time.monotonic()-tick)))
        collector.closed=True;writer=collector.writer.close();summary=diagnostic.close()
        require(collector.failed is None and len(collector.writer.records)==collector.index==summary['samples'],
                'Original nontransport/capture/persistence failure; diagnostic incomplete')
        collector.window.owner_and_files(collector.main)
        if summary['first_strict_rejection']is not None:
            require(summary['tail_samples']>=1,'No original raw tail captured after the strict rejection')
        report=dict(status='ORIGINAL_FIRST_ANOMALY_AND_RAW_TAIL_CAPTURED_COLLECT_ONLY'if summary['first_strict_rejection']else
            'ORIGINAL_FIXED600_RAW_CAPTURE_NO_TRANSPORT_TRIGGER_COLLECT_ONLY',
            diagnostic=summary,samples=collector.writer.records,actual_status=statuses,writer=writer,
            deep_samples=collector.deep_count,source_specialization=collector.source_proof,
            duration_s=time.monotonic()-start,job_sha256=args.job_sha256,source_sha256=args.source_sha256,
            all197_held_inputs_final_checked=True,transport_accepted=False,health_qualified=False,
            quality_qualified=False,scientific_guard_selected=False,production_changed=False,created_unix_s=time.time())
        collector.h.put(output/'report.json',report)
        print(json.dumps({key:report[key]for key in ['status','diagnostic','writer','deep_samples','duration_s']}),flush=True)
        return 0
    except BaseException as error:
        failure=dict(status='ORIGINAL_COLLECT_ONLY_DIAGNOSTIC_FAILED_PRESERVED',error=repr(error),
            elapsed_s=time.monotonic()-started,health_qualified=False,quality_qualified=False,production_changed=False)
        if collector is not None:
            if not collector.writer.closed:
                try:failure['writer']=collector.writer.close()
                except BaseException as close_error:failure['writer_error']=repr(close_error)
            failure.update(samples=collector.writer.records,observed_samples=collector.index,
                diagnostic=diagnostic.close()if diagnostic is not None and not diagnostic.closed else None)
            collector.h.put(output/'failure.json',failure)
        else:
            with(output/'setup-failure.json').open('x')as f:
                json.dump(failure,f,allow_nan=False);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        print(json.dumps({key:value for key,value in failure.items()if key!='samples'}),flush=True)
        return 1


if __name__=='__main__':raise SystemExit(main())
