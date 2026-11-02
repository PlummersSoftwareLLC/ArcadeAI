"""Private screen collaborators; no I/O until the Root-selected runner calls them."""
import copy
import hashlib
import json
import os
import stat
from pathlib import Path
import threading
import time
import urllib.request


def require(ok,message):
    if not ok:raise ValueError(message)


def read_completed_lifecycle(row):
    path=row['private']/'lifecycle.jsonl';fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd);identity=dict(device=before.st_dev,inode=before.st_ino,mode=oct(stat.S_IMODE(before.st_mode)),uid=before.st_uid,nlink=before.st_nlink)
        require(identity==row['lifecycle_identity']and stat.S_ISREG(before.st_mode)and 0<before.st_size<=32768,'Exact bounded child-closed lifecycle file required')
        raw=os.read(fd,32769);after=os.fstat(fd)
        require(len(raw)==before.st_size and raw.endswith(b'\n')and before.st_size==after.st_size
            and before.st_mtime_ns==after.st_mtime_ns and before.st_ctime_ns==after.st_ctime_ns,'Child-closed lifecycle changed or is incomplete')
    finally:os.close(fd)
    return raw


class CompletedRegistration:
    """Slot-specific STOP; closed means child0/EOF, not final origin-writer closure."""
    def __init__(self,recorder,lifecycle_validator):
        self.lock=threading.RLock();self.recorder=recorder;self.lifecycle_validator=lifecycle_validator
        self.registered={};self.consumed={};self.closed=set()
    def register_start(self,**value):
        require(set(value)=={'slot','session','connection','nonce','client_id','journal_game_id','certificate_identifier'},'Exact first-game registration required')
        with self.lock:
            require(value['slot']not in self.registered or self.registered[value['slot']]==value,'First-game identity cannot change')
            self.registered[value['slot']]=copy.deepcopy(value)
    def for_slot(self,slot):
        outer=self
        class View:
            lock=outer.lock
            def register_start(self,**value):return outer.register_start(**value)
            @property
            def permit(self):
                with outer.recorder._lock:
                    value=outer.recorder._scores.get(slot)
                    if outer.recorder._anchor is None or value is None or value['status']!='completed':return None
                    return dict(slot=slot,member=copy.deepcopy(outer.recorder._members[slot]),completed=copy.deepcopy(value))
            def authorize_slot(self,permit,**subject):
                with outer.lock,outer.recorder._lock:
                    require(subject['slot']==slot and slot not in outer.consumed,'One STOP for this original slot only')
                    registered=outer.registered[slot];member=outer.recorder._members[slot];value=outer.recorder._scores[slot]
                    require(outer.recorder._anchor is not None and value['status']=='completed'
                        and permit==dict(slot=slot,member=member,completed=value)
                        and all(subject[k]==registered[k]for k in('slot','session','connection','nonce'))
                        and registered['journal_game_id']==member['journal_game_id']
                        and registered['certificate_identifier']==member['start_certificate_id']and registered['nonce']==member['startup_nonce']
                        and type(subject['sequence'])is int and subject['sequence']>1200,'Exact naturally completed first-game authority required')
                    receipt=dict(subject,consumed_before_send=True,screen_first_game_complete=True,
                        completion=copy.deepcopy(value),member=copy.deepcopy(member),consumed_monotonic_ns=time.monotonic_ns())
                    outer.consumed[slot]=receipt
                    return copy.deepcopy(receipt)
        return View()
    def close_slot(self,slot,row):
        with self.lock,self.recorder._lock:
            receipt=self.consumed[slot];proxy=row['proxy'];ledger=proxy.ledger
            canonical=json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            require(type(row['child'].poll())is int and row['child'].poll()==0
                and proxy.peer_eof.is_set()and proxy.stop_sent.is_set()and proxy.stop_receipt==receipt
                and ledger.closed is True and ledger.stop_receipt==canonical
                and proxy.final_ledger==ledger.summary()and ledger.sequence==proxy.sequence==receipt['sequence']
                and ledger.subject==proxy.subject=={k:receipt[k]for k in('slot','session','connection')}
                and proxy.completed_retirement_parked.is_set()and row['worker'].is_alive()and proxy.error is None
                and self.recorder._scores[slot]==receipt['completion'],
                'Completed child needs original normal0, authentic STOP/EOF/closed ledger, immutable score and parked original proxy')
            require(callable(self.lifecycle_validator),'Exact existing Lua lifecycle validator required')
            row['lifecycle']=self.lifecycle_validator(read_completed_lifecycle(row),proxy.subject,proxy)
            self.closed.add(slot);self.recorder.positively_retired_slots.add(slot)
            proxy.completed_retirement_authorized.set()
            return True



class CurrentMainHealth:
    """Bounded current-owner/API observations; no historical physical-proof claim."""
    def __init__(self,job,output,h):
        self.expected=job['current_main'];self.output=output/'main-observations';self.h=h
        self.index=0;self.previous=None;self.samples=[];self.child=None;self.scope_complete=False;self.lifecycle=None
    def start(self):self.output.mkdir(mode=0o700)
    def observe(self):
        started=time.monotonic();owner=self.expected['owner'];p=Path('/proc',str(owner['pid']))
        birth=int((p/'stat').read_text().rsplit(')',1)[1].split()[19])
        cgroup=(p/'cgroup').read_text();env=dict(v.split('=',1)for v in(p/'environ').read_bytes().decode().split('\0')if'='in v)
        require(birth==owner['starttime_ticks']and p.stat().st_uid==os.getuid()
            and cgroup.splitlines()==['0::'+owner['cgroup']]and env.get('INVOCATION_ID')==owner['invocation_id']
            and all(env.get(k)==v for k,v in self.expected['environment'].items()),'Current Main birth/cgroup/recipe changed')
        with urllib.request.urlopen(self.expected['API'],timeout=5)as response:raw=response.read((1<<20)+1)
        require(len(raw)<=1<<20,'Bounded current Main API required');value=json.loads(raw)
        evidence=self.h.put(self.output/f'{self.index:05d}-API.json',value);self.index+=1
        now=time.time();pipe=value['host_pipeline'];optimizer=pipe['learning_exposure']['optimizer'];replay=pipe['learning_exposure']['replay'];tot=optimizer['total']
        require(time.monotonic()-started<=10 and type(value['ts'])in(int,float)and 0<=now-value['ts']<=10
            and value['pipeline_read_error']==value['bank_persistence_read_error']==''
            and pipe['available']is True and 0<=value['pipeline_snapshot_age_s']<=10
            and not pipe['inference']['errors']and pipe['inference_graphs']['ready']is True and not pipe['inference_graphs'].get('fatal_error')
            and value['training_enabled']is True and value['measurement_active']is False,
            'Current Main unavailable, stale or no longer learning')
        pending_optimizer_attempts=validate_optimizer(optimizer,owner['pid'])
        require(replay['process_id']==owner['pid'],'Current Main replay owner changed')
        for kind in('optimizer','replay'):
            actual=pipe['learning_exposure'][kind]
            require({k:actual[k]for k in('process_id','instance_monotonic_ns','epoch','epoch_reason')}==self.expected['exposure'][kind],
                'Current Main exposure lineage changed')
        clocks={k:value[k]for k in('frame_count','learner_frame_count','training_steps','optimized_samples')}
        require(all(type(v)is int and v>=0 for v in clocks.values())
            and(self.previous is None or all(v>=self.previous[k]for k,v in clocks.items())),'Current Main clocks regressed')
        self.previous=clocks
        rows=value['client_rows'];roles=dict(TRAIN=0,EVAL=0)
        require(type(rows)is list and all(type(row['eval'])is bool for row in rows),'Typed current TRAIN/EVAL role observations required')
        for row in rows:roles['EVAL'if row['eval']else'TRAIN']+=1
        sample=dict(observed_unix_s=now,API=evidence,owner=owner,clocks=clocks,clients=value['client_count'],
            observed_TRAIN_EVAL_counts=roles,pending_optimizer_attempts=pending_optimizer_attempts,expected_original_roles=dict(TRAIN=155,EVAL_once=37),
            EVAL_retirement_or_TRAIN_fault_not_inferred_from_count_alone=True,phase=dict(overlap_pending=False))
        self.samples.append(sample);return sample
    def finish(self,worker):
        require(worker is None or not worker.is_alive(),'Original Main observer thread remains')
        self.scope_complete=True;self.lifecycle=dict(original_observer_thread_closed=True,no_child_scope_created=True)
        return self.h.put(self.output/'bounded-Main-observations.json',dict(
            status='CURRENT_MAIN_OWNER_AND_API_OBSERVED',samples=self.samples,
            original192_physical_health_or_historical_schema_qualification_claimed=False))


def validate_optimizer(opt, expected_pid):
    if opt.get("schema") != "robotron-optimizer-exposure-v1" or opt.get("enabled") is not True or opt.get("process_id") != expected_pid:
        raise RuntimeError("Optimizer observation disabled or owner changed")
    if any(type(opt.get(k)) is not int or opt[k] < 0 for k in ("process_id", "instance_monotonic_ns", "epoch", "unclassified_started_total", "prior_epoch_outcomes_total")):
        raise RuntimeError("Invalid optimizer identity/pending-counter type")
    total, epoch = opt["total"], opt["since_epoch"]
    for counts in (total, epoch):
        if any(type(counts[k]) is not int or counts[k] < 0 for k in ("attempts_started", "outcomes_recorded", "applied", "amp_skipped", "unavailable")):
            raise RuntimeError("Invalid optimizer counter type/value")
        if counts["unavailable"] or counts["outcomes_recorded"] != counts["applied"] + counts["amp_skipped"]:
            raise RuntimeError("Unknown or inconsistent completed optimizer outcomes")
    pending = total["attempts_started"] - total["outcomes_recorded"]
    epoch_pending = epoch["attempts_started"] - epoch["outcomes_recorded"]
    if pending not in (0, 1) or epoch_pending != pending or opt["unclassified_started_total"] != pending:
        raise RuntimeError("Invalid optimizer pending-attempt accounting")
    expected_available = pending == 0 and epoch["outcomes_recorded"] > 0
    if opt.get("available") is not expected_available:
        raise RuntimeError("Optimizer availability flag contradicts counters")
    if opt.get("prior_epoch_outcomes_total") != 0:
        raise RuntimeError("Optimizer outcome straddled an epoch")
    return pending
