"""External private-probe watchdog library; no scheduling or executable launcher.

The launcher must authenticate the predecessor and immutable source/job/main
bindings, start this witness before scheduling, bind the observed original
probe birth, then retain all original unit archives before release. This module
never imports a numerical runtime or queries a GPU.
"""
import copy
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

MAX_RUNTIME_S=330
STOP_GRACE_S=5
MAX_SAMPLE_GAP_S=10
MAX_SAMPLE_DURATION_S=6
POLL_S=0.1
SAMPLE_S=2
MAX_GROUP_PROCESSES=64


def require(value,message):
    if not value:raise ValueError(message)


def number(value):
    return type(value) in (int,float) and math.isfinite(value)


def process_start(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def owner_fields(fields,owner,*,terminal_group_absent=False):
    group_matches=fields.get('ControlGroup')==owner['cgroup']
    if terminal_group_absent:
        group_matches=group_matches or (fields.get('ControlGroup') in (None,'') and fields.get('MainPID')=='0'
            and fields.get('ExecMainCode') in ('1','2','3'))
    require(fields.get('Id')==owner['unit'] and fields.get('InvocationID')==owner['invocation_id']
        and fields.get('NRestarts')=='0' and group_matches
        and fields.get('ExecMainPID')==str(owner['pid'])
        and int(fields.get('ExecMainStartTimestampMonotonic','0'))==owner['start_monotonic_us']
        and fields.get('MainPID') in ('0',str(owner['pid'])),
        'Original probe unit identity changed; no signal authorized')
    return fields


def checked_owner(owner,forbidden):
    require(isinstance(owner,dict) and set(owner)=={'unit','invocation_id','pid','starttime_ticks',
        'cgroup','cgroup_identity','start_monotonic_us','observed_live'},'Exact observed probe owner required')
    require(type(owner['pid']) is int and owner['pid']>0 and owner['pid'] not in forbidden
        and type(owner['starttime_ticks']) is int and owner['starttime_ticks']>0
        and type(owner['start_monotonic_us']) is int and owner['start_monotonic_us']>0
        and owner['observed_live'] is True,'Original probe live birth differs')
    require(isinstance(owner['unit'],str) and re.fullmatch(r'robotron-startup-prefix-private-[A-Za-z0-9_-]+\.service',owner['unit'])
        and re.fullmatch('[0-9a-f]{32}',owner['invocation_id'])
        and isinstance(owner['cgroup'],str) and owner['cgroup'].startswith('/user.slice/')
        and owner['cgroup'].endswith('/'+owner['unit']) and '..' not in Path(owner['cgroup']).parts,
        'Dedicated original probe unit/cgroup required')
    require(isinstance(owner['cgroup_identity'],dict) and set(owner['cgroup_identity'])=={'device','inode'}
        and all(type(x) is int and x>0 for x in owner['cgroup_identity'].values()),'Original cgroup inode required')
    return copy.deepcopy(owner)


class Processes:
    """Bounded real process capabilities, replaceable as one object in CPU tests."""
    def fields(self,unit):
        result=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=2)
        require(result.returncode==0,'Original unit observation failed')
        return dict(x.split('=',1) for x in result.stdout.splitlines() if '=' in x)

    def start(self,pid):return process_start(pid)

    def group(self,pid):
        lines=Path('/proc',str(pid),'cgroup').read_text().splitlines()
        require(len(lines)==1 and lines[0].startswith('0::/user.slice/'),'Expected unified owned user cgroup')
        return lines[0].split('::',1)[1]

    def group_identity(self,group):
        path=Path('/sys/fs/cgroup'+group)
        require(path==path.resolve(strict=True),'Exact original cgroup path required')
        info=path.stat();return dict(device=info.st_dev,inode=info.st_ino)

    def members(self,group):
        path=Path('/sys/fs/cgroup'+group)/'cgroup.procs'
        raw=path.read_bytes()
        require(len(raw)<=8192,'Original cgroup process list exceeds bound')
        ids=[int(row) for row in raw.splitlines()]
        require(len(ids)<=MAX_GROUP_PROCESSES and len(set(ids))==len(ids)
            and all(pid>0 for pid in ids),'Original cgroup process list differs')
        return ids

    def open(self,pid):return os.pidfd_open(pid)
    def close(self,fd):os.close(fd)
    def send(self,fd,signum):signal.pidfd_send_signal(fd,signum)


def signal_owned(owner,forbidden,processes,signum):
    """Signal pinned live processes only; never use a numeric-PID signal.

SIGTERM addresses the original MainPID. SIGKILL addresses a bounded snapshot
of surviving members of that same original cgroup, even if its main exited.
Every opened handle is closed, including a failed birth/membership inspection.
"""
    owner=checked_owner(owner,forbidden)
    require(signum in (signal.SIGTERM,signal.SIGKILL),'Only bounded TERM/KILL escalation allowed')
    fields=owner_fields(processes.fields(owner['unit']),owner)
    require(processes.group_identity(owner['cgroup'])==owner['cgroup_identity'],'Original cgroup was replaced')
    ids=([owner['pid']] if fields['MainPID']!='0' else []) if signum==signal.SIGTERM else processes.members(owner['cgroup'])
    require(len(ids)<=MAX_GROUP_PROCESSES and len(set(ids))==len(ids)
        and all(type(pid) is int and pid>0 and pid not in forbidden for pid in ids),
        'Forbidden or duplicate process in original probe group; no signal authorized')
    handles=[];sent=[];departed=[]
    try:
        for pid in ids:
            birth=processes.start(pid)
            if birth is None:departed.append(pid);continue
            if pid==owner['pid']:require(birth==owner['starttime_ticks'],'Original probe PID was reused')
            require(processes.group(pid)==owner['cgroup'],'A process escaped the original probe cgroup')
            try:fd=processes.open(pid)
            except ProcessLookupError:departed.append(pid);continue
            handles.append((pid,birth,fd))
            require(processes.start(pid)==birth and processes.group(pid)==owner['cgroup'],
                'A process birth/membership changed during pidfd open')
        owner_fields(processes.fields(owner['unit']),owner)
        require(processes.group_identity(owner['cgroup'])==owner['cgroup_identity'],'Original cgroup changed before signal')
        # Authenticate the complete snapshot before sending the first signal.
        for pid,birth,fd in handles:
            current=processes.start(pid)
            if current is None:departed.append(pid);continue
            require(current==birth and processes.group(pid)==owner['cgroup'],'Pinned process no longer belongs to original probe')
        for pid,birth,fd in handles:
            if pid in departed:continue
            try:processes.send(fd,signum);sent.append(dict(pid=pid,starttime_ticks=birth))
            except ProcessLookupError:departed.append(pid)
    finally:
        failures=[]
        for pid,birth,fd in handles:
            try:processes.close(fd)
            except OSError as error:failures.append(str(error))
        require(not failures,'Owned pidfd close failed: '+repr(failures))
    return dict(signal=int(signum),sent=sent,departed=departed,main_touched=False,
                scope='Original live process handles in the authenticated original probe cgroup only.')


def coverage(samples,start,end):
    require(number(start) and number(end) and 0<start<=end,'Actual original service monotonic interval required')
    require(isinstance(samples,list) and len(samples)>=2,'Whole-unit main observations missing')
    last_end=None
    for sample in samples:
        require(set(sample)=={'start_monotonic_s','end_monotonic_s','healthy','evidence'}
            and sample['healthy'] is True and sample['evidence'] is not None,
            'Rejected or unbound main observation cannot cover runtime')
        a,b=sample['start_monotonic_s'],sample['end_monotonic_s']
        require(number(a) and number(b) and 0<=a<=b and b-a<=MAX_SAMPLE_DURATION_S,
                'Main observation exceeded its bound')
        if last_end is not None:require(0<=a-last_end<=MAX_SAMPLE_GAP_S,'Main observation ordering/gap invalid')
        last_end=b
    require(samples[0]['end_monotonic_s']<=start and samples[-1]['start_monotonic_s']>=end,
            'Main observations do not bracket actual original service start/exit')
    return dict(whole_unit_main_coverage=True,actual_start_monotonic_s=start,actual_exit_monotonic_s=end,
                sample_count=len(samples),max_gap_s=MAX_SAMPLE_GAP_S)


class Watchdog:
    """Independent witness and deadline threads for one future owned probe.

``sample`` must be the launcher's authenticated CPU-only main192 observer;
``publish`` must append exact immutable original evidence in its owned output.
``bind`` is called by that launcher only after its one scheduling attempt.
No constructor or default-entry action schedules, discovers or signals a unit.
"""
    def __init__(self,*,sample,publish,forbidden,processes=None,clock=time.monotonic):
        require(callable(sample) and callable(publish) and callable(clock),'Bound capabilities required')
        require(isinstance(forbidden,set) and len(forbidden)>=193
            and all(type(x) is int and x>0 for x in forbidden),'Exact main trainer/192 forbidden births required')
        self.sample=sample;self.publish=publish;self.forbidden=set(forbidden)|{os.getpid()}
        self.processes=processes if processes is not None else Processes();self.clock=clock
        self.lock=threading.Lock();self.stop_event=threading.Event();self.wake=threading.Event()
        self.owner=None;self.samples=[];self.failures=[];self.actions=[];self.last_good=None
        self.term_at=None;self.kill_attempted=False;self.started=False;self.closed=False
        self.witness_thread=self.deadline_thread=None

    def fail(self,message):
        with self.lock:
            if str(message) not in self.failures:self.failures.append(str(message))
        self.wake.set()

    def observe(self):
        a=self.clock()
        try:
            evidence=self.sample();b=self.clock()
            require(evidence is not None and number(a) and number(b) and 0<=b-a<=MAX_SAMPLE_DURATION_S,
                    'Main sample missing or delayed')
            value=dict(start_monotonic_s=a,end_monotonic_s=b,healthy=True,evidence=evidence)
            self.publish('main-sample',value)
            with self.lock:
                require(self.last_good is None or a>=self.last_good,'Main observation clock regressed')
                self.samples.append(value);self.last_good=b
            return value
        except BaseException as error:
            self.fail('Main witness: '+repr(error));return None

    def start(self):
        require(not self.started and not self.closed,'Watchdog is one attempt only')
        self.started=True
        require(self.observe() is not None,'Initial main witness failed before scheduling')
        self.witness_thread=threading.Thread(target=self._witness,name='startup-main-witness',daemon=True)
        self.deadline_thread=threading.Thread(target=self._deadline,name='startup-independent-deadline',daemon=True)
        self.deadline_thread.start();self.witness_thread.start()

    def _witness(self):
        while not self.stop_event.wait(SAMPLE_S):self.observe()

    def _deadline(self):
        while not self.stop_event.is_set():
            try:self.tick()
            except BaseException as error:self.fail('Deadline worker: '+repr(error))
            self.wake.wait(POLL_S);self.wake.clear()

    def bind(self,owner):
        require(self.started and not self.closed and self.owner is None,'One observed probe birth allowed')
        candidate=checked_owner(owner,self.forbidden)
        require(self.processes.start(candidate['pid'])==candidate['starttime_ticks']
            and self.processes.group(candidate['pid'])==candidate['cgroup'],'Original live birth missing')
        fields=owner_fields(self.processes.fields(candidate['unit']),candidate)
        require(fields['MainPID']==str(candidate['pid'])
            and self.processes.group_identity(candidate['cgroup'])==candidate['cgroup_identity'],
            'Original live unit/cgroup missing')
        now=self.clock();start=candidate['start_monotonic_us']/1e6
        with self.lock:
            require(not self.failures and self.last_good is not None and start<=now
                and any(s['end_monotonic_s']<=start for s in self.samples)
                and now-start<15 and now-self.last_good<=MAX_SAMPLE_GAP_S,
                'Probe birth is stale, unwitnessed or outside permit window')
            self.owner=candidate
        self.publish('original-probe-owner',candidate);self.wake.set()

    def tick(self):
        now=self.clock()
        with self.lock:
            owner=copy.deepcopy(self.owner);last=self.last_good;failed=bool(self.failures)
        if not self.started or self.closed:return
        if last is None or now-last>MAX_SAMPLE_GAP_S:self.fail('Main observation coverage expired');failed=True
        if owner is None:return
        if now>=owner['start_monotonic_us']/1e6+MAX_RUNTIME_S:
            self.fail('Original probe external330s deadline');failed=True
        if not failed:return
        if self.term_at is None:
            self.term_at=now
            self._signal(owner,signal.SIGTERM)
        elif now-self.term_at>=STOP_GRACE_S and not self.kill_attempted:
            self.kill_attempted=True
            self._signal(owner,signal.SIGKILL)

    def _signal(self,owner,signum):
        event=dict(original=owner,signal=int(signum),monotonic_s=self.clock(),main_touched=False)
        try:event['result']=signal_owned(owner,self.forbidden,self.processes,signum)
        except BaseException as error:event['error']=repr(error);self.fail('Owned signal: '+repr(error))
        with self.lock:self.actions.append(event)
        try:self.publish('owned-signal',event)
        except BaseException as error:self.fail('Signal evidence: '+repr(error))

    def interrupt(self,reason):self.fail('External guard interrupted: '+str(reason))

    def finish(self,terminal_fields,*,cgroup_absent):
        require(self.started and not self.closed and self.owner is not None,'Original bound watchdog required')
        owner_fields(terminal_fields,self.owner,terminal_group_absent=cgroup_absent is True)
        require(terminal_fields.get('MainPID')=='0' and terminal_fields.get('ExecMainCode') in ('1','2','3')
            and terminal_fields.get('SubState') in ('exited','dead','failed') and cgroup_absent is True,
            'Original terminal outcome/cgroup absence required before stopping coverage')
        # Continue witnesses through exit and cgroup disappearance, independently
        # of a launcher's archive/release operations. A hung witness invalidates.
        self.stop_event.set();self.wake.set()
        for thread in (self.witness_thread,self.deadline_thread):
            if thread is not None:thread.join(timeout=7)
        live=any(t is not None and t.is_alive() for t in (self.witness_thread,self.deadline_thread))
        if live:
            self.fail('A watchdog worker remains live')
        else:self.observe()
        self.closed=True
        start=self.owner['start_monotonic_us']/1e6
        end=int(terminal_fields.get('ExecMainExitTimestampMonotonic','0'))/1e6
        try:covered=coverage(self.samples,start,end)
        except BaseException as error:self.fail('Coverage: '+repr(error));covered=dict(whole_unit_main_coverage=False)
        valid=not self.failures and terminal_fields['ExecMainCode']=='1' and terminal_fields.get('ExecMainStatus')=='0'
        result=dict(schema='robotron-external-startup-watchdog-result-v1',valid=valid,failures=list(self.failures),
            original=self.owner,terminal_fields=terminal_fields,actions=list(self.actions),samples=list(self.samples),
            coverage=covered,actual_signal_outcome_preserved=True,archives_verified=False,units_released=False,
            real_ROM_start_proven=False,quality_qualified=False,learning_speed_gain_verified=False)
        self.publish('watchdog-result',result);return result


if __name__=='__main__':
    print('LIBRARY_ONLY: no configuration reads, process discovery, scheduling, device query or signal; authenticated launcher integration remains required')
