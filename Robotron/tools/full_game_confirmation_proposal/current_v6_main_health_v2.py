"""Prospective bounded current-v6 Main/fleet health; no actions on import.

Reuse the original bounded owner/API/exposure observer and qualified physical
actor/TCP helpers. Every accepted sample joins current original192 membership
to live physical actors or positive natural-EVAL closures. A natural reconnect
can produce a retained, explicitly unaccepted overlap sample for at most10s.
There is no historical continuous192 or subsecond-census claim.
"""
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

SUPPORT_SHA='2ccd2fbcdec7f1ca31000c5d696bf3b30ecf48c21a96b25ba01db7a6fc90787f'
PHYSICAL_SHA='82d78c8b7c4583821b614d39753a6304698196919496fd8255888cb318b12b0a'
SUPERVISOR_SHA='986777d1be4a474bab21f968a1a30bbf79b58623682bad75c23417d140e85a6a'
SLOTS=tuple(range(192))
STATES=('starting','active_train','reconnecting_train','active_eval','retiring_eval','closed_eval','fault_cleanup','quarantined')


def require(value,message):
    if not value:raise ValueError(message)


def load(name,pin,h):
    path=h.checked(pin);spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    h.checked(pin);return module


def stable_projection(fleet,connections):
    return dict(epoch=fleet['epoch'],slots={k:{q:r[q]for q in
        ('eval_only','incarnation','state','original_pid','original_birth','current_physical_binding','natural_result','closure','faults','quarantine_reason','prior_fault_closure')}
        for k,r in fleet['slots'].items()},connections=sorted(connections['connections'],key=lambda r:r['client_slot']))


def validate_metadata(fleet,connections,expected,membership,roles,*,now):
    require(fleet['schema']=='robotron-continuous-training-rolling-TRAIN-snapshot-v3'
        and fleet['mode']=='CONTINUOUS_TRAIN155_EVAL37_ONCE'
        and fleet['epoch']==expected['epoch'] and fleet['supervisor']==expected['supervisor']
        and fleet['trainer']==expected['trainer'] and fleet['source_authority']==expected['source_authority']
        and fleet['original_membership']==expected['original_membership']and fleet['rolemap']==expected['rolemap'],
        'Current v6 original supervisor/trainer/source lineage changed')
    require(0<=now-fleet['updated_unix_s']<=5 and not fleet['errors']
        and fleet['error_summary']['occurrences']==0 and fleet['counts']['quarantined']==fleet['counts']['fault_cleanup']==0
        and fleet['unverified_train_full_games']==0 and fleet['TRAIN_rebind_same_process_only']is True
        and fleet['EVAL_refill_allowed']is False,'Current v6 fleet stale or faulted')
    require(connections['schema']=='robotron-continuous-active-connections-v1'
        and connections['server_stamp']==expected['trainer']['server_stamp']
        and connections['continuous_training_mode']is connections['main_measurement_entry_disabled']is True
        and connections['training_enabled']is connections['replay_admission_open']is True
        and connections['measurement_active']is connections['ratchet_frozen']is False
        and connections['consumer_error']is None and 0<=now-connections['observed_unix_s']<=5,
        'Current Main connection provenance/mode/freshness changed')
    require(set(fleet['slots'])==set(roles)==set(map(str,SLOTS))
        and all(type(v)is bool for v in roles.values())and sum(roles.values())==37,
        'Exactly155TRAIN/37EVAL original slot roles required')
    require(membership['kind']=='original192-membership'and membership['epoch']==fleet['epoch']
        and membership['supervisor']==fleet['supervisor']and membership['trainer']==fleet['trainer']
        and membership['source_authority']==fleet['source_authority']
        and fleet['initial_admission']['complete']is True
        and fleet['initial_admission']['slots_ever_bound']==list(SLOTS),
        'Original192 membership source changed')
    members=membership['data']['original_slots'];require(set(members)==set(map(str,SLOTS)),'All192 original members required')
    counts={state:0 for state in STATES};pending=[]
    for slot in SLOTS:
        key=str(slot);row=fleet['slots'][key];original=members[key]
        require(row['state']in counts and row['eval_only']is roles[key]is original['eval_only']
            and type(row['incarnation'])is int and row['incarnation']==original['incarnation']==1
            and row['original_pid']==original['original_child']['pid']
            and row['original_birth']==original['original_child']['birth']
            and row['faults']==0 and row['prior_fault_closure']is None and row['quarantine_reason']is None,
            'An original slot was replaced, faulted or changed role')
        counts[row['state']]+=1
        if row['state']in('reconnecting_train','retiring_eval'):
            require(row['eval_only']is (row['state']=='retiring_eval'),'Foreign role in natural transition')
            pending.append(slot)
        else:require(row['state']==('active_eval'if row['eval_only']else'active_train')
            or row['eval_only']and row['state']=='closed_eval','Unexpected current slot state')
        if row['state']in('active_train','active_eval'):
            require(row['natural_result']is None and row['closure']is None,'Active original slot already has a terminal closure')
    require(counts==fleet['counts'],'Fleet state/count arithmetic differs')
    require(fleet['completed_eval_games']==counts['retiring_eval']+counts['closed_eval'],
        'Natural EVAL completion counter differs from retained slot outcomes')
    rows=connections['connections']
    require(type(rows)is list and len({r['client_slot']for r in rows})==len({r['token']for r in rows})==len(rows)
        and all(type(r['client_slot'])is int and str(r['client_slot'])in roles
            and r['eval_only']is roles[str(r['client_slot'])]for r in rows),'Duplicate/foreign live Main connection')
    return pending


def validate_join(fleet,connections,expected,membership,roles,physical,bindings,closures,*,now,closed_connection_predicate):
    require(callable(closed_connection_predicate)
        and hashlib.sha256(Path(inspect.getsourcefile(closed_connection_predicate)).read_bytes()).hexdigest()==SUPERVISOR_SHA,
        'Original v6 token-cleanup predicate required')
    pending=validate_metadata(fleet,connections,expected,membership,roles,now=now)
    require(not pending,'An overlap sample cannot qualify a physical census')
    current={r['client_slot']:r for r in connections['connections']};live=[];closed=[]
    for slot in SLOTS:
        row=fleet['slots'][str(slot)]
        require(slot in bindings,'Original slot lacks its source-bound physical connection record')
        event=bindings[slot];data=event['data']
        require(event['kind']=='physical-connection'and event['epoch']==fleet['epoch']and event['slot']==slot
            and event['incarnation']==1 and event['supervisor']==fleet['supervisor']and event['trainer']==fleet['trainer'],
            'Original slot physical-binding lineage changed')
        if row['state']=='closed_eval':
            require(slot not in current and slot not in physical and row['natural_result']is not None and row['closure']is not None,
                'Retired EVAL still live or lacks positive closure')
            close=closures[slot]['closure'];natural=closures[slot]['natural'];body=close['data']
            require(close['kind']=='original-reaped-closure'and natural['kind']=='natural-result'
                and close['epoch']==natural['epoch']==fleet['epoch']and close['slot']==natural['slot']==slot
                and close['supervisor']==natural['supervisor']==fleet['supervisor']
                and close['trainer']==natural['trainer']==fleet['trainer']
                and close['source_authority']==natural['source_authority']==fleet['source_authority']
                and type(body['actual_exit'])is int and body['actual_exit']==0
                and body['original_pid']==row['original_pid']and body['original_birth']==row['original_birth']
                and body['original_wait_reaped']is body['original_birth_absent']is True
                and body['natural_result']==row['natural_result']and body['restart_censored']is False
                and closures[slot]['original_birth_absent']is True,
                'Retired EVAL original normal0/natural-result/reap closure differs')
            result=natural['data']['result']
            connection=bindings[slot]['data']['connection']
            cleanups=body['connection_cleanup']
            require(natural['data']['natural_complete']is True
                and result['complete']is result['eligible']is result['known_start']is True
                and result['client_id']==connection['client_id']and result['eval_only']is True
                and cleanups and all(c['client_slot']==slot and c['eval_only']is True
                    and closed_connection_predicate({k:c[k]for k in ('token','client_id','client_slot','eval_only','connection_ns','socket_endpoints')},c,expected['trainer']['server_stamp'])for c in cleanups)
                and any(all(c[k]==connection[k]for k in connection)for c in cleanups)
                and result['client_slot']==slot and any(c['terminal_receipt']==result
                    and c['terminal_line_sha256']==natural['data']['raw_line']['sha256']for c in cleanups),
                'Retired EVAL terminal was not durably committed by its original connection')
            closed.append(slot);continue
        require(slot in current and slot in physical and slot in bindings,'Original active slot lacks a connection or physical witness')
        proof=physical[slot];actor=proof['actor']
        require(data['connection']==current[slot], 'Current connection does not join its immutable physical binding')
        recorded=data['actor']
        require(all(actor[k]==recorded[k]for k in ('pid','birth','parent','exe','command','cgroup','uid'))
            and actor['pid']==row['original_pid']and actor['birth']==row['original_birth']
            and actor['parent']==fleet['supervisor']['pid']and actor['cgroup']==fleet['supervisor']['cgroup']
            and actor['uid']==os.getuid()and actor['exe']=='/usr/games/mame'
            and all(actor['environment'].get(k)==v for k,v in recorded['environment'].items())
            and proof['TCP']==data['process_owned_TCP']and proof['before_after_actor_equal']is True,
            'Original MAME birth/parent/role/environment/process-owned TCP changed')
        live.append(slot)
    require(set(current)==set(physical)==set(live)and len(live)+len(closed)==192
        and len([s for s in live if not roles[str(s)]])==155,
        'Current accepted census did not retain all155 TRAIN and all37 original EVAL outcomes')
    return dict(live_slots=live,closed_eval_slots=closed,live_originals=len(live),natural_EVAL_closed=len(closed),
        physical_process_and_TCP_sample_verified=True,historical_continuous192_claimed=False)


class CurrentV6MainHealth:
    def __init__(self,job,output,h):
        self.h=h;self.job=job;self.expected=job['current_fleet'];self.output=output/'main-observations'
        require(job['screen_support']['sha256']==SUPPORT_SHA
            and self.expected['physical_helper']['sha256']==PHYSICAL_SHA
            and self.expected['supervisor']['source']['sha256']==SUPERVISOR_SHA,'Exact original observer and physical helpers required')
        self.support=load('_future_v6_bounded_Main_support',job['screen_support'],h)
        self.physical=load('_future_v6_physical_helpers',self.expected['physical_helper'],h)
        self.supervisor=load('_future_v6_original_supervisor_definitions',self.expected['supervisor']['source'],h)
        self.base=self.support.CurrentMainHealth(job,output,h)
        self.fleet_job=self.read(self.expected['job'])
        require(self.fleet_job['trainer']==self.expected['trainer']and self.fleet_job['rolemap']==self.expected['rolemap']
            and self.fleet_job['source_authority']==self.expected['source_authority'],
            'Current original fleet job/source authority differs')
        self.membership=self.read(self.expected['original_membership']);self.roles=self.read(self.expected['rolemap'])['slot_eval']
        self.samples=[];self.pending_since=None;self.previous_observed=None
        self.child=None;self.scope_complete=False;self.lifecycle=None

    def read(self,pin):
        p=self.h.checked(pin);raw=p.read_bytes()
        require(hashlib.sha256(raw).hexdigest()==pin['sha256'],'Immutable fleet evidence changed during read')
        return json.loads(raw)

    def get_connections(self):
        with urllib.request.urlopen('http://127.0.0.1:8771/api/continuous_training_connections',timeout=5)as response:
            raw=response.read((2<<20)+1)
        require(len(raw)<=2<<20,'Bounded current connection API required');return json.loads(raw)

    def status(self):
        p=Path(self.expected['status_path']);require(p.is_absolute()and p.name=='status.json','Exact current fleet snapshot path required')
        raw=p.read_bytes();require(len(raw)<=2<<20,'Bounded fleet snapshot required');return json.loads(raw)

    def start(self):self.base.start()

    def supervisor_process(self):
        expected=self.expected['supervisor'];actual=self.physical.actor(expected['pid'])
        require(actual['birth']==expected['birth']and actual['cgroup']==expected['cgroup']
            and actual['uid']==os.getuid()and actual['environment'].get('INVOCATION_ID')==expected['invocation_id']
            and actual['command'][3:]==[expected['source']['path'],'--execute','--config',self.expected['job']['path'],
                '--config-sha256',self.expected['job']['sha256'],'--source-sha256',expected['source']['sha256']],
            'Actual original v6 supervisor process/invocation/job changed')
        actual['environment']={'INVOCATION_ID':actual['environment']['INVOCATION_ID']}
        return actual

    def observe(self):
        begin=time.monotonic();supervisor_before=self.supervisor_process();base=self.base.observe();index=len(self.samples)
        before=self.status();connections=self.get_connections();now=time.time()
        pending=validate_metadata(before,connections,self.expected,self.membership,self.roles,now=now)
        proofs={};bindings={};closures={};failure=None
        if not pending:
            try:
                for slot in SLOTS:
                    row=before['slots'][str(slot)]
                    if row['state']=='closed_eval':
                        bindings[slot]=self.read(row['current_physical_binding'])
                        try:observed=self.physical.birth(row['original_pid'])['birth']
                        except (FileNotFoundError,ProcessLookupError):observed=None
                        closures[slot]=dict(closure=self.read(row['closure']),natural=self.read(row['natural_result']),
                            original_birth_absent=observed!=row['original_birth'])
                        continue
                    binding=self.read(row['current_physical_binding']);bindings[slot]=binding
                    actor=self.physical.actor(row['original_pid'])
                    tcp=self.physical.tcp_binding(row['original_pid'],binding['data']['connection']['socket_endpoints'])
                    after_actor=self.physical.actor(row['original_pid'])
                    proofs[slot]=dict(actor=actor,TCP=tcp,before_after_actor_equal=actor==after_actor)
            except Exception as error:failure=repr(error)
        after_connections=self.get_connections();after=self.status();after_pending=validate_metadata(after,after_connections,
            self.expected,self.membership,self.roles,now=time.time())
        changed=stable_projection(before,connections)!=stable_projection(after,after_connections)
        supervisor_after=self.supervisor_process()
        require(supervisor_before==supervisor_after,'Original supervisor changed during observation')
        is_pending=bool(pending or after_pending or changed)
        require(failure is None or is_pending,'Unexplained original process/TCP failure: '+str(failure))
        elapsed=time.monotonic()-begin
        require(elapsed<=10,'Current-v6 complete observation exceeded declared10s bound')
        if self.previous_observed is not None:
            require(begin-self.previous_observed<=15,'Current-v6 observer gap exceeded declared15s bound')
        self.previous_observed=begin
        if is_pending:
            if self.pending_since is None:self.pending_since=begin
            require(time.monotonic()-self.pending_since<=10,'Original reconnect/retirement did not close within10s; no health rescue')
            joined=None
        else:
            joined=validate_join(before,connections,self.expected,self.membership,self.roles,proofs,bindings,closures,
                now=now,closed_connection_predicate=self.supervisor.closed_connection)
            self.pending_since=None
        # Keep complete physical environments only in private bounded artifacts.
        # Restrict them to the same declared environment keys as original bindings.
        for slot,proof in proofs.items():
            keys=bindings[slot]['data']['actor']['environment']
            proof['actor']['environment']={k:proof['actor']['environment'].get(k)for k in keys}
        raw=self.h.put(self.output/f'{index:05d}-v6-physical.json',dict(schema='robotron-current-v6-bounded-physical-observation-v1',
            started_monotonic_s=begin,completed_monotonic_s=time.monotonic(),base=base,fleet_before=before,
            connections_before=connections,physical={str(k):v for k,v in proofs.items()},bindings={str(k):v for k,v in bindings.items()},
            closures={str(k):v for k,v in closures.items()},fleet_after=after,connections_after=after_connections,
            supervisor_before=supervisor_before,supervisor_after=supervisor_after,
            pending_slots=sorted(set(pending+after_pending)),projection_changed=changed,physical_failure=failure,joined=joined,
            accepted=is_pending is False,collection_limit_s=10,maximum_observer_gap_s=15,maximum_overlap_s=10))
        sample=dict(base,physical_v6=raw,phase=dict(overlap_pending=is_pending),current_v6_join=joined)
        self.samples.append(sample);return sample

    def finish(self,worker):
        require(worker is None or not worker.is_alive(),'Original v6 observer thread remains')
        require(self.samples and self.samples[-1]['phase']['overlap_pending']is False,
            'Final original physical observation must be accepted; no late replacement')
        base_report=self.base.finish(worker)
        self.scope_complete=True;self.lifecycle=dict(original_observer_thread_closed=True,no_child_scope_created=True)
        return self.h.put(self.output/'bounded-current-v6-Main-observations.json',dict(
            status='CURRENT_V6_ORIGINAL_MEMBERS_PHYSICAL_AND_BOUNDED_MAIN_OBSERVED',samples=self.samples,
            base_report=base_report,current_fleet=self.expected,scope='Bounded per-sample original physical/TCP joins with explicit <=10s reconnect overlap; no historical uninterrupted192 or subsecond census claim.',
            original192_physical_health_or_historical_schema_qualification_claimed=False))
