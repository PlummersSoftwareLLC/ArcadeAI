"""Future owned CONTINUOUS TRAIN155 / one-game EVAL37 fleet; inert by default.

No current source/job is selected by this file. --execute requires Root's fresh
fully pinned job, restored trainer qualification and its exact owned unit.
TRAIN-only rolling reconnects require the SAME owned process and fresh kernel TCP
proof after complete old-token cleanup. Original membership remains immutable.
Natural TRAIN completions never stop, freeze or respawn a child. Fault recovery
is serial, ownership/connection-cleanup bound and explicitly censored.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import time
import urllib.parse
import urllib.request

MODE='CONTINUOUS_TRAIN155_EVAL37_ONCE'
CLEANUP_FLAGS=('original_handler_stopped','original_owned_timer_stopped',
    'owned_timer_callback_succeeded','journal_disconnect_succeeded',
    'FIFO_reset_executed','replay_consumer_healthy')
CONNECTION_FIELDS=('token','client_id','client_slot','eval_only','connection_ns','socket_endpoints')
ORIGINAL_FIELDS=('eval_only','incarnation','original_child','spawn_intent',
                 'original_child_receipt','connection_binding')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def pin(path):
    path=Path(path)
    require(path.resolve(strict=True)==path and not path.is_symlink(),'Canonical regular evidence required')
    identity=lambda s:dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,
        mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    a=path.stat();require(stat.S_ISREG(a.st_mode)and a.st_size<=2_000_000,'Bounded small source/metadata required')
    raw=path.read_bytes();require(identity(a)==identity(path.stat()),'Evidence changed during read')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(a))


def read(entry):
    return json.loads(selected_bytes(entry))


def selected_bytes(entry):
    require(pin(entry['path'])==entry,'Selected evidence pin changed')
    raw=Path(entry['path']).read_bytes()
    require(len(raw)==entry['bytes']and hashlib.sha256(raw).hexdigest()==entry['sha256']
        and pin(entry['path'])==entry,'Selected bytes changed during read')
    return raw


def exclusive(path, value=None, raw=None):
    require((value is None)!=(raw is None),'One exact payload required')
    payload=raw if raw is not None else (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    require(len(payload)<=2_000_000,'Durable event exceeds declared bound')
    with path.open('xb')as stream:
        stream.write(payload);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return pin(path)


def atomic_snapshot(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    require(len(raw)<=524288,'Static192 snapshot exceeds declared512KiB bound')
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('xb')as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def module(name,entry):
    raw=selected_bytes(entry)
    spec=importlib.util.spec_from_file_location(name,entry['path'])
    value=importlib.util.module_from_spec(spec)
    exec(compile(raw,entry['path'],'exec'),value.__dict__)
    return value


class RawCompletionTail:
    def __init__(self,path):
        self.path=Path(path);self.position=self.path.stat().st_size if self.path.exists()else 0
        self.identity=None if not self.path.exists()else(self.path.stat().st_dev,self.path.stat().st_ino)
        self.pending=b''
    def poll(self):
        if not self.path.exists():return []
        with self.path.open('rb')as stream:
            s=os.fstat(stream.fileno());identity=(s.st_dev,s.st_ino)
            if self.identity is None:self.identity=identity
            require(identity==self.identity and s.st_size>=self.position,'Journal replaced/truncated')
            stream.seek(self.position);raw=stream.read(2_000_000);self.position+=len(raw)
        pieces=(self.pending+raw).split(b'\n');self.pending=pieces.pop()
        require(len(self.pending)<=65536,'Journal line exceeds cleanup evidence bound')
        return [(json.loads(line),line+b'\n')for line in pieces if line]


def closed_connection(connection,cleanup,stamp):
    require(type(connection)is dict and type(cleanup)is dict
        and set(CONNECTION_FIELDS)<=set(connection)
        and set(CONNECTION_FIELDS+CLEANUP_FLAGS+('schema','server_stamp','observed_unix_s',
            'cleanup_error','ready_for_external_join','replay_admission_open'))<=set(cleanup),
        'Complete typed cleanup record required')
    require(cleanup['schema']=='robotron-prospective-connection-cleanup-receipt-v2'
        and cleanup['server_stamp']==stamp
        and type(cleanup['observed_unix_s'])in(int,float)
        and math.isfinite(cleanup['observed_unix_s'])and cleanup['observed_unix_s']>0
        and all(cleanup[k]==connection[k] and type(cleanup[k])is type(connection[k])
                for k in CONNECTION_FIELDS),'Exact old-token cleanup identity required')
    require(cleanup['cleanup_error']is None,'Old-token cleanup failed; preserve raw error')
    require(type(cleanup['ready_for_external_join'])is bool
        and type(cleanup['replay_admission_open'])is bool
        and all(type(cleanup[k])is bool for k in CLEANUP_FLAGS),'Typed cleanup primitives required')
    return cleanup['ready_for_external_join']is True and cleanup['replay_admission_open']is True and all(
        cleanup[k]is True for k in CLEANUP_FLAGS)


def train_refill_eligible(row,maximum):
    return (row['eval_only']is False and row['state']=='fault_cleanup'
        and row['closure']is not None and row['natural_result']is None
        and row['quarantine_reason']is None and type(row['faults'])is int and 0<row['faults']<maximum)


def train_journal_binding(result,history,closures,generation):
    require(type(result.get('client_id'))is int
        and type(result.get('start_unix_s'))in(int,float)
        and type(result.get('end_unix_s'))in(int,float)
        and math.isfinite(result['start_unix_s'])and math.isfinite(result['end_unix_s'])
        and 0<result['start_unix_s']<=result['end_unix_s']
        and all(type(result[context]['measurement_generation'])is int
            and result[context]['measurement_generation']==generation
            and result[context]['measurement_active']is False
            and result[context]['ratchet_frozen']is False for context in ('start_context','end_context')),'Natural TRAIN clock/policy differs')
    same_cid=[e for e in history if e['connection']['client_id']==result['client_id']]
    if not same_cid:return None
    # CID is reusable and journals carry no token. Once reused in this slot,
    # never assign a newly observed row to an earlier same-CID binding.
    entry=same_cid[-1];connection=entry['connection']
    require(connection['client_slot']==result['client_slot']and connection['eval_only']is False,
            'TRAIN binding role/slot differs')
    if result['start_unix_s']<entry['authenticated_unix_s']:return None
    closed=closures.get(connection['token'])
    if closed is not None and result['end_unix_s']>closed['closed_unix_s']:return None
    return entry


class ContinuousTrainingFleet:
    def __init__(self,cfg,source):
        require(cfg['schema']=='robotron-continuous-training-supervisor-job-v2'
            and cfg['rolling_TRAIN_rebind_same_process_only']is True
            and cfg['slot_local_TRAIN_refill_after_owned_closure_only']is True
            and cfg['EVAL_refill_allowed']is False
            and cfg['mode']==MODE and cfg['original_attempt']==1 and cfg['no_retry']is True,
            'Exact fresh continuous-mode supervisor job required')
        for value in cfg['inputs']:require(pin(value['path'])==value,'Source/authority changed')
        authority=read(cfg['source_authority'])
        require(authority['schema']=='robotron-root-continuous-main-startup-qualified-v1'
            and authority['trainer']==cfg['trainer']
            and authority['all_model_optimizer_replay_banks_clocks_preserved']is True
            and authority['new_mode_source_and_CPU_qualified']is True
            and authority['actual_CPU_scope_closeouts'],
            'Actual Root-qualified same-state startup/source family required')
        for value in authority['actual_CPU_scope_closeouts']:
            close=read(value)
            require(close['actual_exit']==0 and close['status']=='PASS_ENGINEERING_ONLY',
                    'Actual original closed CPU qualification required')
        self.cfg=cfg;self.source=source
        self.physical=module('_continuous_owned_processes',cfg['physical_helper'])
        self.rolemap=read(cfg['rolemap'])
        self.roles=self.rolemap['slot_eval']
        require(set(self.roles)==set(map(str,range(192)))
            and all(type(v)is bool for v in self.roles.values())and sum(self.roles.values())==37,
            'Exactly155TRAIN/37EVAL fixed slot roles required')
        require(cfg['api_root']=='http://127.0.0.1:8771'and cfg['startup_s']==5
            and cfg['fault_cleanup_s']==10 and cfg['max_faults']==3,
            'Exact declared startup/fault bounds required')
        require(cfg['launch_argv'][1:]==cfg['mame_argv'][1:]
            and cfg['mame_argv'][0]=='/usr/games/mame'
            and cfg['launch_argv'][1]=='robotron','Literal existing role-wrapper/MAME tail required')
        require(not os.environ.get('LD_PRELOAD')and
            {'ROBOTRON_CLIENT_SLOT','ROBOTRON_ACTOR_ROUND','ROBOTRON_EVAL_MODE',
             'ROBOTRON_PREVIEW_FPS','ROBOTRON_RETIRE_AFTER_GAME'}<=set(cfg['input_environment_keys']),
            'Do not preload supervisor; retain literal INPUT slot/role controls')
        self.owner=self.owner_record()
        self.root=Path(cfg['output']);require(not self.root.exists(),'Fresh owned output only')
        self.root.mkdir(mode=0o700);(self.root/'events').mkdir(mode=0o700);(self.root/'actors').mkdir(mode=0o700)
        self.epoch=f"{self.owner['pid']}:{self.owner['birth']}:{self.owner['invocation_id']}"
        self.sequence=0;self.stopping=False;self.errors=[];self.children={};self.records={}
        self.error_occurrences=0;self.error_distinct_details=0;self.last_error_detail=None
        self.error_counts_by_scope={};self.error_counts_by_slot={};self.error_latest_digest={}
        self.completed_train=0;self.completed_eval=0;self.partial_games=0;self.train_score_sum=0
        self.seen_jids=set();self.initial_bound=set();self.barrier=None;self.policy_generation=None
        self.original_membership=None;self.original_slots={};self.reaped_history=[]
        self.binding_history={};self.binding_closures={};self.unverified_train_games=0
        self.tail=RawCompletionTail(Path(cfg['journal_directory'])/'games.jsonl')
        self.event('begin',None,0,dict(source=source,job=cfg,owner=self.owner))

    def owner_record(self):
        result=subprocess.run(['systemctl','--user','show',self.cfg['unit']],
            capture_output=True,text=True,timeout=10)
        require(result.returncode==0,'Exact supervisor unit observation failed')
        s=dict(x.split('=',1)for x in result.stdout.splitlines()if'='in x)
        require(s.get('Id')==self.cfg['unit']and s.get('MainPID')==str(os.getpid())
            and s.get('NRestarts')=='0'and s.get('Restart')=='no'
            and s.get('ActiveState')=='active'and s.get('SubState')=='running'
            and s.get('Type')=='exec'and re.fullmatch('[0-9a-f]{32}',s.get('InvocationID','')),
            'Exact current owned no-restart supervisor MainPID required')
        b=self.physical.birth(os.getpid())
        require(s['ControlGroup']==self.physical.cgroup(os.getpid()),'Supervisor cgroup differs')
        return dict(pid=os.getpid(),birth=b['birth'],unit=self.cfg['unit'],
            invocation_id=s['InvocationID'],cgroup=s['ControlGroup'],source=self.source)

    def stop(self,*ignored):
        # Existing original Popen objects remain retained until finally cleanup.
        self.stopping=True

    def event(self,kind,slot,incarnation,data):
        self.sequence+=1
        return exclusive(self.root/'events'/f'{self.sequence:08d}-{kind}.json',dict(
            schema='robotron-continuous-training-event-v1',mode=MODE,epoch=self.epoch,
            kind=kind,slot=slot,incarnation=incarnation,supervisor=self.owner,
            trainer=self.cfg['trainer'],source_authority=self.cfg['source_authority'],
            unix_s=time.time(),monotonic_ns=time.monotonic_ns(),data=data))

    def record_error(self,scope,slot,error,context=None):
        """Bound display state; retain every distinct full error immutably.

        Repeated occurrences update exact counters without repeated fsync/files.
        One latest digest/pin per fixed scope/slot bounds memory. Changed details use
        a content-addressed immutable file; older details remain on disk.
        """
        require(scope in ('observation','original-birth','slot','initial-spawn','journal')
            and (slot is None or type(slot)is int and 0<=slot<192),'Declared error scope/slot required')
        message=str(error)
        detail=dict(scope=scope,slot=slot,error_type=type(error).__name__,message=message,context=context)
        digest=hashlib.sha256(json.dumps(detail,sort_keys=True,separators=(',',':'),
            ensure_ascii=True,allow_nan=False).encode()).hexdigest()
        key=(scope,slot)
        recent=self.error_latest_digest.get(key)
        if recent is None or recent['digest']!=digest:
            path=self.root/'events'/('error-detail-'+digest+'.json')
            if path.exists():
                entry=pin(path);prior=read(entry)
                require(prior['schema']=='robotron-continuous-supervisor-error-detail-v1'
                    and prior['epoch']==self.epoch and prior['detail']==detail,
                    'Existing immutable error detail differs')
            else:
                entry=exclusive(path,dict(schema='robotron-continuous-supervisor-error-detail-v1',
                    epoch=self.epoch,supervisor=self.owner,trainer=self.cfg['trainer'],
                    unix_s=time.time(),monotonic_ns=time.monotonic_ns(),detail=detail))
                self.error_distinct_details+=1
            recent=dict(digest=digest,pin=entry)
            self.error_latest_digest[key]=recent
        self.last_error_detail=recent['pin']
        self.error_occurrences+=1
        self.error_counts_by_scope[scope]=self.error_counts_by_scope.get(scope,0)+1
        if slot is not None:
            label=str(slot);self.error_counts_by_slot[label]=self.error_counts_by_slot.get(label,0)+1
        display=(scope+(''if slot is None else ' slot'+str(slot))+': '+message).encode(
            'ascii','backslashreplace').decode('ascii')[:256]
        if display not in self.errors and len(self.errors)<32:self.errors.append(display)
        # Historical errors remain immutable evidence. They still seal initial
        # admission; an independently closed TRAIN slot may recover locally.

    def error_summary(self):
        return dict(occurrences=self.error_occurrences,distinct_immutable_details=self.error_distinct_details,
            counts_by_scope=dict(self.error_counts_by_scope),counts_by_slot=dict(self.error_counts_by_slot),
            last_detail=self.last_error_detail,detail_directory=str(self.root/'events'),
            detail_filename_rule='error-detail-<SHA256(canonical-detail-JSON)>.json',
            inline_errors_maximum=32,inline_message_maximum_chars=256)

    def get(self,path,query=None):
        began=time.monotonic_ns()
        suffix=''if query is None else'?'+urllib.parse.urlencode(query)
        with urllib.request.urlopen(self.cfg['api_root']+path+suffix,timeout=2)as response:
            raw=response.read(524289)
        require(len(raw)<=524288,'Bounded continuous evidence response required')
        value=json.loads(raw);ended=time.monotonic_ns()
        require(value.get('server_stamp')==self.cfg['trainer']['server_stamp']
            and type(value.get('observed_monotonic_ns'))is int
            and began<=value['observed_monotonic_ns']<=ended and ended-began<=2_000_000_000,
            'Fresh exact original trainer policy/connection evidence required')
        return value

    def policy(self):
        value=self.get('/api/continuous_training_policy')
        require(value['schema']=='robotron-continuous-main-policy-v1'
            and value['continuous_training_mode']is True
            and value['main_measurement_entry_disabled']is True
            and value['measurement_active']is False and value['ratchet_frozen']is False
            and value['replay_admission_open']is True and value['consumer_error']is None
            and value['training_enabled']is True,'Actual permanent-main-measurement fence/replay readiness required')
        if self.policy_generation is None:self.policy_generation=value['measurement_generation']
        require(type(value['measurement_generation'])is int
            and value['measurement_generation']==self.policy_generation,'Main policy generation changed')
        return value

    def spawn(self,slot):
        previous=self.records.get(slot)
        require(not self.stopping and (not self.errors if previous is None else
            train_refill_eligible(previous,self.cfg['max_faults'])),'Admission sealed')
        require(previous is None or previous['state']=='fault_cleanup'and previous['closure']is not None,
                'No replacement before original closure is durable')
        require(previous is None or previous['eval_only']is False,'Never refill any EVAL attempt')
        if previous is not None:
            close=read(previous['closure'])['data']
            require(close['original_pid']==previous['original_child']['pid']
                and close['original_birth']==previous['original_child']['birth']
                and close['original_wait_reaped']is True and close['original_birth_absent']is True
                and type(close['actual_exit'])is int and close['connection_cleanup'],
                'Actual original TRAIN exit/reap/cleanup required before local refill')
            try:still=self.physical.birth(previous['original_child']['pid'])
            except FileNotFoundError:still=None
            require(still is None or still['birth']!=previous['original_child']['birth'],
                'Previously closed TRAIN birth reappeared')
        policy=self.policy()  # Real source mode forbids all main entry changes.
        if previous is not None:
            current=self.get('/api/continuous_training_connections')
            require(not any(c['client_slot']==slot for c in current['connections']),
                    'TRAIN slot has a live unowned connection before refill')
        require(self.owner_record()==self.owner,'Supervisor owner changed before Popen')
        inc=1 if previous is None else previous['incarnation']+1
        env=dict(os.environ,**self.cfg['parent_environment'],ROBOTRON_CLIENT_SLOT=str(slot),
            ROBOTRON_ACTOR_ROUND=str(inc),ROBOTRON_RETIRE_AFTER_GAME='1'if self.roles[str(slot)]else'0',
            ROBOTRON_PREVIEW_FPS='30',ROBOTRON_EVAL_MODE='0')
        intent=self.event('spawn-intent',slot,inc,dict(argv=self.cfg['launch_argv'],
            input_environment={k:env.get(k)for k in self.cfg['input_environment_keys']},
            policy=policy,previous_closure=None if previous is None else previous['closure']))
        directory=self.root/'actors'/f'{slot:03d}-{inc:03d}';directory.mkdir(mode=0o700)
        with (directory/'stdout.log').open('ab')as log:
            child=subprocess.Popen(self.cfg['launch_argv'],env=env,stdout=log,stderr=subprocess.STDOUT)
        # Track the ACTUAL original handle before any fallible observation.
        item=dict(child=child,incarnation=inc,started=time.monotonic(),token=None,tokens=set(),
            faults=0 if previous is None else previous['faults'],directory=directory)
        self.children[slot]=item
        try:
            b=self.physical.birth(child.pid)
            require(b['parent']==self.owner['pid'],'New child is not original direct Popen child')
            original=dict(pid=child.pid,birth=b['birth'],parent=b['parent'],cgroup=self.physical.cgroup(child.pid),
                launch_argv=self.cfg['launch_argv'],controlled_env=None)
            spawned=self.event('original-child',slot,inc,dict(original_child=original,spawn_intent=intent))
            self.records[slot]=dict(eval_only=self.roles[str(slot)],incarnation=inc,state='starting',
                original_child=original,spawn_intent=intent,connection_binding=None,
                natural_result=None,closure=None,prior_fault_closure=None if previous is None else previous['closure'],
                quarantine_reason=None,faults=item['faults'],original_child_receipt=spawned)
        except Exception as error:
            self.records[slot]=dict(eval_only=self.roles[str(slot)],incarnation=inc,state='quarantined',
                original_child=dict(pid=child.pid,birth=None),spawn_intent=intent,connection_binding=None,
                natural_result=None,closure=None,prior_fault_closure=None,quarantine_reason=repr(error).encode('ascii','backslashreplace').decode('ascii')[:256],faults=item['faults'])
            self.record_error('original-birth',slot,error)

    def capture_connection(self,slot,connection):
        # Exact same physical helper as v4; no PID/CID/comm inference or adoption.
        row=self.records[slot];item=self.children[slot];child=item['child']
        require(connection['client_slot']==slot and connection['eval_only']is row['eval_only'],
                'Connection slot/role differs')
        before=self.physical.actor(child.pid)
        expected=dict(self.cfg['actor_common_environment'],ROBOTRON_CLIENT_SLOT=str(slot),
            ROBOTRON_ACTOR_ROUND=str(row['incarnation']),ROBOTRON_EVAL_MODE='1'if row['eval_only']else'2',
            ROBOTRON_RETIRE_AFTER_GAME='1'if row['eval_only']else'0',ROBOTRON_PREVIEW_CLIENT='1'if slot==0 else'0')
        require(before['pid']==child.pid and before['birth']==row['original_child']['birth']
            and before['parent']==self.owner['pid'] and before['uid']==os.getuid()
            and before['cgroup']==self.owner['cgroup'] and before['command']==self.cfg['mame_argv']
            and before['exe']==self.cfg['mame_argv'][0]
            and all(before['environment'].get(k)==v for k,v in expected.items()),'Actual MAME slot/role/source differs')
        tcp=self.physical.tcp_binding(child.pid,connection['socket_endpoints'])
        require(before==self.physical.actor(child.pid)and child.poll()is None,'Original actor changed during TCP binding')
        before['environment']={k:before['environment'][k]for k in expected}
        return dict(actor=before,process_owned_TCP=tcp,controlled_environment=expected)

    def append_binding(self,slot,connection,proof,previous,old_cleanup=None):
        row=self.records[slot];item=self.children[slot]
        authenticated=time.time()
        require(type(authenticated)in(int,float)and math.isfinite(authenticated)and authenticated>0,
                'Positive finite binding clock required')
        binding=self.event('physical-connection',slot,row['incarnation'],dict(actor=proof['actor'],
            connection=connection,process_owned_TCP=proof['process_owned_TCP'],previous_binding=previous,
            authenticated_unix_s=authenticated,old_token_cleanup=old_cleanup))
        entry=dict(binding=binding,connection=json.loads(json.dumps(connection)),
            authenticated_unix_s=authenticated,incarnation=row['incarnation'],spawn_intent=row['spawn_intent'])
        self.binding_history.setdefault(slot,[]).append(entry)
        row['connection_binding']=binding;row['original_child']['controlled_env']=proof['controlled_environment']
        item['token']=connection['token'];item['tokens'].add(connection['token'])
        item.pop('reconnect_started',None);item.pop('unbound_candidate_token',None)
        row['state']=('retiring_eval'if row['natural_result']is not None else'active_eval')if row['eval_only']else'active_train'
        self.initial_bound.add(slot)
        return binding

    def bind(self,slot,connections):
        row=self.records[slot]
        matches=[c for c in connections if c['client_slot']==slot and c['eval_only']is row['eval_only']]
        if len(matches)!=1:return False
        connection=matches[0];proof=self.capture_connection(slot,connection)
        self.append_binding(slot,connection,proof,row['connection_binding'])
        return True

    def observe_train(self,slot,connections):
        row=self.records[slot];item=self.children[slot]
        require(row['eval_only']is False and item['child'].poll()is None,'Live owned TRAIN only')
        old=read(row['connection_binding'])['data']['connection']
        current=[c for c in connections if c['client_slot']==slot]
        require(len(current)<=1 and (not current or current[0]['eval_only']is False),
                'Ambiguous or changed TRAIN role')
        if current and current[0]==old:
            require(item.get('unbound_candidate_token')is None,'Unbound TRAIN token remains unresolved')
            row['state']='active_train';item.pop('reconnect_started',None);return
        if 'reconnect_started'not in item:
            item['reconnect_started']=time.monotonic()
            self.event('train-reconnect-wait',slot,row['incarnation'],dict(previous_binding=row['connection_binding']))
        row['state']='reconnecting_train'
        require(time.monotonic()-item['reconnect_started']<=self.cfg['fault_cleanup_s']+self.cfg['startup_s'],
                'TRAIN reconnect did not authenticate within declared cleanup+startup bounds')
        if not current:return
        candidate=current[0]
        require(type(candidate['token'])is str and candidate['token']not in item['tokens']
            and type(candidate['connection_ns'])is int and candidate['connection_ns']>old['connection_ns']
            and type(candidate['client_id'])is int,'Fresh never-used TRAIN token required')
        require(item.get('unbound_candidate_token')in(None,candidate['token']),
                'Another unbound TRAIN token appeared before ownership proof')
        item['unbound_candidate_token']=candidate['token']
        cleanup=self.get('/api/connection_cleanup_token',dict(token=old['token']))
        if not closed_connection(old,cleanup,self.cfg['trainer']['server_stamp']):return
        policy=self.policy()
        proof=self.capture_connection(slot,candidate)
        again=self.get('/api/continuous_training_connections')
        require(again['continuous_training_mode']is True and again['main_measurement_entry_disabled']is True
            and [c for c in again['connections']if c['client_slot']==slot]==[candidate],
                'New TRAIN token changed during kernel proof')
        # Repeat the same physical identity/TCP proof AFTER the repeated API row.
        repeated=self.capture_connection(slot,candidate)
        require(proof==repeated,'Original TRAIN physical identity/TCP changed during rebind')
        require(time.monotonic()-item['reconnect_started']<=self.cfg['fault_cleanup_s']+self.cfg['startup_s'],
                'TRAIN proof exceeded declared cleanup+startup bounds')
        close=self.event('train-binding-retired',slot,row['incarnation'],dict(
            previous_binding=row['connection_binding'],cleanup=cleanup,policy=policy,
            actor_not_replaced=True,actor_exit_or_game_completion_claimed=False))
        require(old['token']not in self.binding_closures,'Old token already retired')
        self.binding_closures[old['token']]=dict(receipt=close,closed_unix_s=cleanup['observed_unix_s'])
        self.append_binding(slot,candidate,proof,row['connection_binding'],close)

    def journals(self):
        for result,line in self.tail.poll():
            try:
                self.journal_row(result,line)
            except Exception as error:
                # The tail consumed this batch already. Preserve this row and
                # continue so one rejected TRAIN connection cannot drop EVAL.
                path=self.root/'events'/('journal-'+hashlib.sha256(line).hexdigest()+'.jsonl')
                raw=pin(path)if path.exists()else exclusive(path,raw=line)
                require(selected_bytes(raw)==line,'Failed journal row evidence changed')
                slot=result.get('client_slot')if isinstance(result,dict)else None
                if type(slot)is not int or not 0<=slot<192:slot=None
                self.record_error('journal',slot,error,dict(raw_line=raw))

    def journal_row(self,result,line):
        jid=result.get('journal_game_id');slot=result.get('client_slot')
        if type(jid)is not str or jid in self.seen_jids:return
        require(type(slot)is int and slot in self.records,'Journal row for undeclared slot')
        row=self.records[slot]
        require(result.get('eval_only')is row['eval_only'],'Durable journal role changed')
        self.seen_jids.add(jid)
        raw=exclusive(self.root/'events'/f'journal-{hashlib.sha256(line).hexdigest()}.jsonl',raw=line)
        natural=(all(result.get(k)is True for k in ('complete','eligible','known_start'))
            and result.get('boundary_reason')in('score_reset','zero_score_restart'))
        event=self.event('natural-result'if natural else'partial-result',slot,row['incarnation'],
            dict(raw_line=raw,result=result,natural_complete=natural))
        if not natural:self.partial_games+=1;return
        require(type(result.get('score'))is int and result['score']>=0,'Exact full unwrapped score required')
        if not row['eval_only']:
            matched=(None if row['quarantine_reason']is not None else train_journal_binding(
                result,self.binding_history.get(slot,[]),self.binding_closures,self.policy_generation))
            if matched is None:
                self.unverified_train_games+=1
                self.event('unverified-train-result',slot,row['incarnation'],dict(raw_line=raw,
                    journal_event=event,reason='No unique latest authenticated token interval; no retrospective CID adoption',
                    counted_in_verified_train_scores=False))
                return
            self.event('verified-train-result-binding',slot,matched['incarnation'],dict(
                journal_event=event,physical_binding=matched['binding'],spawn_intent=matched['spawn_intent']))
            self.completed_train+=1;self.train_score_sum+=result['score']
            return
        # Original one-game EVAL scoring/identity semantics are unchanged.
        require(row['connection_binding']is not None,'Natural row lacks an observed original physical connection')
        conn=read(row['connection_binding'])['data']['connection']
        intent=read(row['spawn_intent'])
        require(type(result.get('client_id'))is int and result['client_id']==conn['client_id']
            and result['start_unix_s']>=intent['unix_s']
            and result['start_context']['measurement_generation']==self.policy_generation
            and result['start_context']['measurement_active']is False
            and result['start_context']['ratchet_frozen']is False,
            'Natural row is not this original physical connection and fixed policy incarnation')
        require(row['natural_result']is None,'An EVAL slot completed more than one eligible game')
        row['natural_result']=event;row['state']='retiring_eval';self.completed_eval+=1
        self.children[slot]['result_seen']=time.monotonic()

    def close_original(self,slot):
        row=self.records[slot];item=self.children[slot];child=item['child'];code=child.poll()
        if code is None:return False
        require(child.wait(timeout=0)==code,'Original Popen status/reap changed')
        require(item.get('unbound_candidate_token')is None,
                'Exited TRAIN has an unbound token; no retrospective ownership or refill')
        current=self.get('/api/continuous_training_connections')
        if any(c['client_slot']==slot for c in current['connections']):return False
        # The natural receipt is fsync'd BEFORE Lua can receive its exit bit.
        # Drain again after actual exit so a poll/write race cannot misclassify
        # an EVAL completion as a failed attempt eligible for replacement.
        self.journals()
        if (self.tail.pending or self.tail.path.exists()
                and self.tail.position<self.tail.path.stat().st_size):return False
        try:old=self.physical.birth(child.pid)
        except FileNotFoundError:old=None
        require(old is None or old['birth']!=row['original_child']['birth'],'Original PID/birth remains')
        require(item['tokens'],'Original connection was never physically bound; do not guess PID from slot')
        cleanup=[]
        for token in sorted(item['tokens']):
            value=self.get('/api/connection_cleanup_token',dict(token=token))
            require(value['client_slot']==slot and value['eval_only']is row['eval_only']
                and value['token']==token,'Original connection cleanup identity differs')
            bound=[e for e in self.binding_history.get(slot,[])if e['connection']['token']==token]
            require(len(bound)==1,'Original token lacks unique physical binding history')
            if not closed_connection(bound[0]['connection'],value,self.cfg['trainer']['server_stamp']):return False
            cleanup.append(value)
            if token not in self.binding_closures:
                terminal=self.event('physical-binding-closed',slot,row['incarnation'],dict(
                    physical_binding=bound[0]['binding'],cleanup=value,original_exit=code))
                self.binding_closures[token]=dict(receipt=terminal,closed_unix_s=value['observed_unix_s'])
        if (row['eval_only']and row['natural_result']is None
                and any(c['terminal_receipt']is not None for c in cleanup)):
            # Positive server completion cannot become a replacement permit
            # merely because a tail/config/publication observation is delayed.
            return False
        if row['natural_result']is not None:
            require(code==0,'Completed EVAL original actor did not exit normally')
            result=read(row['natural_result'])['data']['result']
            require(any(c['terminal_receipt']==result and c['terminal_line_sha256']==
                read(row['natural_result'])['data']['raw_line']['sha256']for c in cleanup),
                'EVAL natural terminal was not committed by this original connection')
        close=self.event('original-reaped-closure',slot,row['incarnation'],dict(actual_exit=code,
            original_pid=child.pid,original_birth=row['original_child']['birth'],
            original_wait_reaped=True,original_birth_absent=True,connection_cleanup=cleanup,
            natural_result=row['natural_result'],restart_censored=row['natural_result']is None))
        row['closure']=close
        self.reaped_history.append(close)
        if row['eval_only']and row['natural_result']is not None:row['state']='closed_eval'
        else:
            row['state']='fault_cleanup'if row['quarantine_reason']is None else'quarantined'
            row['faults']+=1
            require(row['faults']<self.cfg['max_faults'],'Original slot repeatedly failed; quarantine')
        return True

    def barrier_partition(self,connections):
        """Root-selected EVER-BOUND originals; never a simultaneous192 claim."""
        if (self.initial_bound!=set(range(192))or self.errors
                or set(self.records)!=set(range(192))):return None
        live=set();closed=set()
        for slot,row in self.records.items():
            child=self.children[slot]['child']
            if (row['incarnation']!=1 or row['faults']!=0
                    or row['prior_fault_closure']is not None
                    or row['quarantine_reason']is not None
                    or row['connection_binding']is None):return None
            if row['state']==('active_eval'if row['eval_only']else'active_train'):
                if (child.poll()is not None or row['natural_result']is not None
                        or row['closure']is not None):return None
                live.add(slot)
            elif row['eval_only']and row['state']=='closed_eval':
                if child.poll()!=0 or row['natural_result']is None or row['closure']is None:return None
                closure=read(row['closure'])['data']
                if (closure['actual_exit']!=0 or closure['original_wait_reaped']is not True
                        or closure['original_birth_absent']is not True
                        or closure['natural_result']!=row['natural_result']
                        or closure['restart_censored']is not False):return None
                closed.add(slot)
            else:return None  # Retiring EVAL must finish its positive closure.
        if (len(live)<155 or len(closed)>37 or len(live)+len(closed)!=192
                or len(connections)!=len(live)
                or {c['client_slot']for c in connections}!=live
                or len({c['token']for c in connections})!=len(live)
                or any(c['token']!=self.children[c['client_slot']]['token']
                       or c['eval_only']is not self.roles[str(c['client_slot'])]
                       for c in connections)):return None
        return dict(live_slots=sorted(live),closed_eval_slots=sorted(closed))

    def snapshot(self):
        counts={state:sum(r['state']==state for r in self.records.values())for state in
            ('starting','active_train','reconnecting_train','active_eval','retiring_eval','closed_eval','fault_cleanup','quarantined')}
        compact={}
        for slot,row in self.records.items():
            original=self.original_slots.get(str(slot))
            digest=None if original is None else hashlib.sha256(json.dumps(original,
                sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()
            compact[str(slot)]=dict(eval_only=row['eval_only'],incarnation=row['incarnation'],
                state=row['state'],original_pid=row['original_child']['pid'],
                original_birth=row['original_child'].get('birth'),original_slot_sha256=digest,
                natural_result=row['natural_result'],closure=row['closure'],
                prior_fault_closure=row['prior_fault_closure'],quarantine_reason=row['quarantine_reason'],
                faults=row['faults'],current_physical_binding=row['connection_binding'],
                physical_binding_history_count=len(self.binding_history.get(slot,[])))
        atomic_snapshot(self.root/'status.json',dict(schema='robotron-continuous-training-rolling-TRAIN-snapshot-v3',
            mode=MODE,epoch=self.epoch,updated_unix_s=time.time(),updated_monotonic_ns=time.monotonic_ns(),
            supervisor=self.owner,trainer=self.cfg['trainer'],rolemap=self.cfg['rolemap'],
            source_authority=self.cfg['source_authority'],initial_admission=dict(complete=self.barrier is not None,
                slots_ever_bound=sorted(self.initial_bound),immutable_all192_barrier=self.barrier),
            original_membership=self.original_membership,
            slots=compact,counts=counts,errors=list(self.errors),error_summary=self.error_summary(),
            completed_train_games=self.completed_train,completed_eval_games=self.completed_eval,
            partial_or_censored_games=self.partial_games,unverified_train_full_games=self.unverified_train_games,
            TRAIN_rebind_same_process_only=True,EVAL_refill_allowed=False,
            train_full_game_score_sum=self.train_score_sum,
            train_full_game_mean=None if not self.completed_train else self.train_score_sum/self.completed_train,
            score_scope='Natural full changing-policy games; unwrapped full scores, no private frozen-policy quality claim',
            quality_qualified=False))

    def run(self):
        try:
            initial=self.get('/api/continuous_training_connections')
            require(initial['connections']==[],'Initial supervisor requires zero old/unowned connections')
            # Observe each actual child promptly. A batch of192 HTTP/unit/fsync
            # launches before the first bind could consume its exact5s bound.
            # Scientific selection waits for all192 original live anchors and
            # the current155TRAIN/remaining-active-EVAL plus closed-EVAL proof.
            next_initial=0
            while not self.stopping:
                try:
                    batch=self.get('/api/continuous_training_connections')
                    require(batch['continuous_training_mode']is True and batch['main_measurement_entry_disabled']is True,
                            'Actual permanent main-policy mode disappeared')
                    # Bind changed TRAIN tokens before attributing new journal rows.
                    # Drain EVAL natural terminals BEFORE its original TCP/exit checks.
                    for slot,item in list(self.children.items()):
                        row=self.records[slot]
                        if row['state']in('active_train','reconnecting_train')and item['child'].poll()is None:
                            try:self.observe_train(slot,batch['connections'])
                            except Exception as error:
                                row['state']='quarantined';row['quarantine_reason']=repr(error).encode('ascii','backslashreplace').decode('ascii')[:256]
                                self.record_error('slot',slot,error)
                    self.journals()
                except Exception as error:
                    self.record_error('observation',None,error)
                    self.snapshot();time.sleep(1);continue
                for slot,item in list(self.children.items()):
                    row=self.records[slot]
                    try:
                        if (row['state']=='starting'or row['state']=='retiring_eval'and row['connection_binding']is None)and item['child'].poll()is None:
                            try:bound=self.bind(slot,batch['connections'])
                            except (FileNotFoundError,ProcessLookupError,ValueError):bound=False
                            require(bound or time.monotonic()-item['started']<=self.cfg['startup_s'],
                                    'Exact original child did not bind within declared5s bootstrap')
                        if row['state']=='active_eval'and item['child'].poll()is None:
                            current=[c for c in batch['connections']if c['client_slot']==slot]
                            require(len(current)==1 and current[0]['token']==item['token'],
                                    'Original EVAL connection changed; no rebind or refill')
                        if (row['state']=='retiring_eval'and item['child'].poll()is None
                                and time.monotonic()-item['result_seen']>5):
                            # A normal natural exit is required for the static
                            # profile. Preserve a stuck original as evidence;
                            # no signal can manufacture a normal closure.
                            raise ValueError('Completed EVAL did not exit naturally within5s; retain original')
                        if item['child'].poll()is not None and row['closure']is None:
                            if 'exit_seen'not in item:item['exit_seen']=time.monotonic()
                            require(self.close_original(slot)or time.monotonic()-item['exit_seen']<=self.cfg['fault_cleanup_s'],
                                    'Original connection cleanup did not close within bound')
                        if train_refill_eligible(row,self.cfg['max_faults']):
                            self.spawn(slot)
                    except Exception as error:
                        row['state']='quarantined';row['quarantine_reason']=repr(error).encode('ascii','backslashreplace').decode('ascii')[:256]
                        self.record_error('slot',slot,error)
                partition=None if self.barrier is not None else self.barrier_partition(batch['connections'])
                if partition is not None:
                    self.original_slots={str(slot):{k:(self.binding_history[slot][0]['binding']
                        if k=='connection_binding'else row[k])for k in ORIGINAL_FIELDS}
                                         for slot,row in self.records.items()}
                    # Freeze a JSON copy; later operational fault bookkeeping
                    # cannot mutate the original static membership authority.
                    self.original_slots=json.loads(json.dumps(self.original_slots,allow_nan=False))
                    self.original_membership=self.event('original192-membership',None,0,
                        dict(original_slots=self.original_slots))
                    self.barrier=self.event('initial-all192-barrier',None,0,dict(
                        slots=sorted(self.initial_bound),slot_eval=self.roles,physical_connections={
                            str(k):self.binding_history[k][0]['binding']for k in self.records},
                        original_membership=self.original_membership,
                        admission_basis='EVER_BOUND_ORIGINAL192_NOT_SIMULTANEOUS',
                        live_slots=partition['live_slots'],closed_eval_slots=partition['closed_eval_slots']))
                if (next_initial<192 and not self.errors and not self.stopping
                        and all(r['connection_binding']is not None for r in self.records.values())):
                    batch_started=time.monotonic()
                    for _ in range(8):
                        if (next_initial>=192 or self.errors or self.stopping
                                or time.monotonic()-batch_started>.5):break
                        try:
                            self.spawn(next_initial);next_initial+=1
                        except Exception as error:
                            self.record_error('initial-spawn',next_initial,error)
                            break
                self.snapshot();time.sleep(.2)
        finally:
            # Never act on names, CIDs or unknown PIDs. Preserve every original
            # handle and actual status, including failed bootstrap children.
            for item in self.children.values():
                child=item['child']
                if child.poll()is None:child.terminate()
            end=time.monotonic()+3
            while time.monotonic()<end and any(i['child'].poll()is None for i in self.children.values()):time.sleep(.05)
            terminal=[]
            for slot,item in self.children.items():
                child=item['child']
                if child.poll()is None:child.kill()
                code=child.wait(timeout=5)
                terminal.append(dict(slot=slot,incarnation=item['incarnation'],pid=child.pid,actual_exit=code))
            self.event('owned-supervisor-terminal',None,0,dict(children=terminal,errors=self.errors,
                error_summary=self.error_summary(),prior_original_reaped_closures=self.reaped_history,
                all_original_children_reaped=True,quality_qualified=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--config');p.add_argument('--config-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY_NO_READS_ACTIONS_OR_OUTPUTS');return
    source=pin(Path(__file__).resolve());require(source['sha256']==a.source_sha256,'Exact selected supervisor required')
    cp=pin(Path(a.config).resolve());require(cp['sha256']==a.config_sha256,'Exact future original job required')
    fleet=ContinuousTrainingFleet(read(cp),source)
    signal.signal(signal.SIGTERM,fleet.stop);signal.signal(signal.SIGINT,fleet.stop)
    fleet.run()


if __name__=='__main__':main()
