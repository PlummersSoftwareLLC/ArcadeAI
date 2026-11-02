"""Inert prospective joins for original supervisor-owned actors; no launcher.

Every method is explicit. No import-time proc/API access, processes, signals or
outputs. This is not wired into RoundFleet and does not implement rolling proof
membership or persistence. The current whole-round supervisor remains unchanged.
"""
import hashlib
import json
import os
import secrets
from pathlib import Path
import socket
import subprocess
import time


def require(value, message):
    if not value:
        raise ValueError(message)


def birth(pid):
    text = Path('/proc',str(pid),'stat').read_text()
    require(int(text.split(' ',1)[0]) == pid, 'Observed another process')
    fields = text.rsplit(')',1)[1].split()
    return dict(pid=pid,birth=int(fields[19]),parent=int(fields[1]),state=fields[0])


def cgroup(pid):
    lines=Path('/proc',str(pid),'cgroup').read_text().splitlines()
    require(len(lines)==1 and lines[0].startswith('0::/'),'Exact cgroup-v2 membership required')
    return lines[0][3:]


def actor(pid):
    before=birth(pid)
    root=Path('/proc',str(pid))
    command=[p.decode()for p in (root/'cmdline').read_bytes().split(b'\0')if p]
    env=dict(p.decode().split('=',1)for p in (root/'environ').read_bytes().split(b'\0')if b'='in p)
    result=dict(pid=before['pid'],birth=before['birth'],parent=before['parent'],
        exe=os.readlink(root/'exe'),command=command,
        environment=env,cgroup=cgroup(pid),uid=root.stat().st_uid)
    after=birth(pid)
    require(all(before[k]==after[k]for k in ('pid','birth','parent'))
        and before['state']not in ('Z','X','x')and after['state']not in ('Z','X','x'),
        'Actor identity changed or retired')
    return result


def tcp_binding(pid, endpoints):
    """Actual process-owned socket inode, not API-CID-to-PID inference."""
    root=Path('/proc',str(pid))
    require(os.readlink(root/'ns/net')==os.readlink('/proc/self/ns/net'), 'Actor network namespace differs')
    descriptors=list((root/'fd').iterdir())
    require(len(descriptors)<=4096,'Unexpected actor descriptor census')
    inodes=set()
    for fd in descriptors:
        try:
            value=os.readlink(fd)
        except FileNotFoundError:
            continue
        if value.startswith('socket:[')and value.endswith(']'):
            inodes.add(value[8:-1])
    def endpoint(text):
        address,port=text.split(':')
        return [socket.inet_ntoa(bytes.fromhex(address)[::-1]),int(port,16)]
    raw=(root/'net/tcp').read_bytes()
    require(len(raw)<=2_000_000,'Actor TCP evidence exceeds declared bound')
    found=[]
    for line in raw.decode().splitlines()[1:]:
        fields=line.split()
        if (len(fields)>9 and fields[3]=='01' and fields[9]in inodes
                and endpoint(fields[1])==endpoints['peer']
                and endpoint(fields[2])==endpoints['server']):
            found.append(dict(inode=int(fields[9]),local=endpoint(fields[1]),remote=endpoint(fields[2])))
    require(len(found)==1,'No unique actual process socket to this server connection')
    return found[0]


class OwnedTrainingRefillJoins:
    def __init__(self, slot_eval, *, launch_argv, mame_argv, controlled_environment,
                 expected_server_stamp, maximum_generations=4096):
        require(type(slot_eval)is dict and set(slot_eval)==set(map(str,range(192)))
            and all(type(v)is bool for v in slot_eval.values())
            and sum(slot_eval.values())==37,'Preserve exact37EVAL/155TRAIN slot map')
        require(type(maximum_generations)is int and 192<=maximum_generations<=4096,
                'Explicit bounded future generation budget required')
        require(all(type(a)is list and a and all(type(v)is str for v in a)
                    for a in (launch_argv,mame_argv))
            and type(controlled_environment)is dict
            and all(type(k)is type(v)is str for k,v in controlled_environment.items())
            and {'ROBOTRON_RECOVERY_CONFIG','ROBOTRON_RECOVERY_CONFIG_SHA256',
                 'LD_PRELOAD','ROBOTRON_SOCKET_WAIT_PORT','ROBOTRON_SOCKET_WAIT_US'}
                <=set(controlled_environment)
            and type(expected_server_stamp)is dict
            and set(expected_server_stamp)=={'pid','birth','source_sha256'}
            and all(type(expected_server_stamp[k])is int and expected_server_stamp[k]>0
                    for k in ('pid','birth'))
            and type(expected_server_stamp['source_sha256'])is str
            and len(expected_server_stamp['source_sha256'])==64,
            'Exact future command/environment/server authority required')
        self.roles=dict(slot_eval)
        self.launch_argv=list(launch_argv)
        self.mame_argv=list(mame_argv)
        self.common=dict(controlled_environment)
        self.server=dict(expected_server_stamp)
        self.maximum_generations=maximum_generations
        self.records={}
        self.completed=[]
        self.sealed=False
        self.spawn_claims={}
        self.pending_children=[]

    def seal(self):
        # Stop admission only. No actor signals, terminations or queue actions.
        self.sealed=True

    def _require_fresh_policy(self, snapshot, began, ended, expected_generation):
        require(type(snapshot)is dict and snapshot.get('server_stamp')==self.server
            and snapshot.get('measurement_active')is False
            and type(snapshot.get('measurement_generation'))is int
            and snapshot['measurement_generation']==expected_generation
            and snapshot.get('replay_admission_open')is True
            and snapshot.get('replay_consumer_healthy')is True
            and snapshot.get('cleanup_error')is None
            and type(snapshot.get('observed_monotonic_ns'))is int
            and began<=snapshot['observed_monotonic_ns']<=ended
            and ended-began<=2_000_000_000,
            'Fresh inactive unchanged-generation replay-ready healthy policy required')

    def prepare_training_spawn(self, slot, generation, prior_ticket, read_terminal):
        """Consume eligibility BEFORE caller Popen or an actual blocked-child release.

        This method does not prove that ordering or atomic admission. A real
        caller must hold its reviewed measurement/control admission fence across
        this check and Popen/release. An existing running actor is never called
        unadmitted by this method. No process is launched or released here.
        """
        require(not self.sealed and type(slot)is int and str(slot)in self.roles
            and not self.roles[str(slot)] and slot in self.records,
            'Only an unsealed original TRAIN slot can request spawn eligibility')
        previous=self.records[slot]
        require(previous['retired'] and type(generation)is int
            and generation==previous['generation']+1 and previous['ticket']is not None
            and prior_ticket==previous['ticket'],'Exact unused previous-generation eligibility ticket required')
        require(len(self.completed)+sum(not r['retired']for r in self.records.values())
            +sum(not r['observed']for r in self.spawn_claims.values())<self.maximum_generations,
            'Bounded future generation budget exhausted before ticket consumption')
        proof=previous['retirement_proof'];old=proof['actual_cleanup'];row=proof['durable_terminal']
        began=time.monotonic_ns()
        fresh=json.loads(json.dumps(read_terminal(row['client_id'],slot,row['journal_game_id']),allow_nan=False))
        ended=time.monotonic_ns()
        self._require_fresh_policy(fresh,began,ended,old['measurement_generation'])
        require(not self.sealed and fresh.get('ready_for_external_join')is True
            and all(fresh.get(k)==old.get(k)for k in ('schema','token','server_cleanup_incarnation',
                'client_id','client_slot','eval_only','connection_ns','socket_endpoints',
                'terminal_receipt','terminal_line_sha256')),
            'Exact previous original terminal/connection cleanup and open admission required')
        value=dict(schema='robotron-prospective-training-pre-spawn-eligibility-v1',
            slot=slot,generation=generation,claim_nonce=secrets.token_hex(16),
            consumed_ticket_sha256=prior_ticket,measurement_generation=fresh['measurement_generation'],
            fresh_previous_cleanup=fresh,created_monotonic_ns=ended,
            expires_monotonic_ns=ended+2_000_000_000,
            scope='ELIGIBILITY_ONLY_NOT_ACTOR_ADMISSION_PROOF',admission_proved=False,
            pre_spawn_or_actual_gate_release_order_proved=False,
            caller_pre_spawn_or_actual_gate_release_and_policy_fence_required=True)
        previous['ticket']=None  # Burn once; no rearm after a later failure.
        self.spawn_claims[slot]=dict(value=value,observed=False,child=None)
        return json.loads(json.dumps(value,allow_nan=False))

    def observe_original(self, slot, generation, child, cid, read_active, *, spawn_claim=None):
        require(type(slot)is int and str(slot)in self.roles
            and type(generation)is int and generation>=1 and isinstance(child,subprocess.Popen)
            and child.args==self.launch_argv,'Exact original owned Popen required')
        # This Popen already exists and may already be acting. Retain it for
        # physical tracking/quarantine before any policy or evidence failure.
        pending=next((r for r in self.pending_children if r['child']is child),None)
        if pending is None:
            require(len(self.pending_children)<self.maximum_generations,
                    'Auxiliary tracking capacity exhausted; caller must retain original Popen')
            pending=dict(slot=slot,generation=generation,child=child,
                physical_tracking_complete=False,requires_caller_admission_or_quarantine=True)
            self.pending_children.append(pending)
        require(pending['slot']==slot and pending['generation']==generation,
                'Original Popen cannot be rebound to another generation')
        require(child.poll()is None,'Original actor already retired; caller retains its reap obligation')
        previous=self.records.get(slot)
        if previous is None:
            require(generation==1 and spawn_claim is None,'Original first generation only')
        else:
            claim=self.spawn_claims.get(slot)
            require(not self.sealed and not self.roles[str(slot)] and previous['retired']
                and generation==previous['generation']+1 and claim is not None
                and spawn_claim==claim['value'] and not claim['observed'],
                'Exact fresh pre-spawn TRAIN eligibility claim required; this is physical tracking only')
            if claim['child']is None:
                claim['child']=child
            require(claim['child']is child,'Spawn claim already belongs to another original Popen')
        require(len(self.completed)+len([r for r in self.records.values()if not r['retired']])
            <self.maximum_generations,'Future generation budget exhausted; no history overwritten')
        began=time.monotonic_ns()
        observed=actor(child.pid)
        require(observed['parent']==os.getpid() and observed['uid']==os.getuid()
            and observed['cgroup']==cgroup(os.getpid()) and observed['exe']==self.mame_argv[0]
            and observed['command']==self.mame_argv,'Original direct child image/argv/owner differs')
        expected=dict(self.common,ROBOTRON_CLIENT_SLOT=str(slot),ROBOTRON_ACTOR_ROUND=str(generation),
            ROBOTRON_RETIRE_AFTER_GAME='1',ROBOTRON_EVAL_MODE='1'if self.roles[str(slot)]else'2')
        require(all(observed['environment'].get(k)==v for k,v in expected.items()),'Original slot/role/source environment differs')
        connection=json.loads(json.dumps(read_active(cid,slot),allow_nan=False))
        require(connection['schema']=='robotron-prospective-connection-cleanup-receipt-v2'
            and connection['server_stamp']==self.server and connection['client_id']==cid
            and connection['client_slot']==slot and connection['eval_only']is self.roles[str(slot)]
            and connection['original_handler_stopped']is False and connection['terminal_receipt']is None
            and connection['training_refill_candidate']is False,'Exact active server connection differs')
        if previous is not None:
            self._require_fresh_policy(connection,began,time.monotonic_ns(),
                spawn_claim['measurement_generation'])
            require(time.monotonic_ns()<=spawn_claim['expires_monotonic_ns'],
                    'Pre-spawn eligibility claim expired; existing actor remains tracked for quarantine')
        tcp=tcp_binding(child.pid,connection['socket_endpoints'])
        ended=time.monotonic_ns()
        after=actor(child.pid)
        require((previous is None or not self.sealed
                 and ended<=spawn_claim['expires_monotonic_ns'])and observed==after and child.poll()is None
            and began<=connection['observed_monotonic_ns']<=ended and ended-began<=2_000_000_000,
            'Fresh same original actor/socket/connection bracket required')
        # Retain only controlled environment, not unrelated process secrets.
        observed['environment']={k:observed['environment'][k]for k in expected}
        evidence=dict(slot=slot,generation=generation,actor=observed,connection=connection,
            process_owned_TCP=tcp,observation_start_monotonic_ns=began,observation_end_monotonic_ns=ended,
            observed_unix_s=time.time(),physical_actor_connected_proved=True,
            observation_scope='PHYSICAL_TRACKING_ONLY_ACTOR_MAY_ALREADY_BE_ACTING',
            admission_proved=False,pre_spawn_or_actual_gate_release_order_proved=False,
            requires_external_caller_admission_or_quarantine=True,
            spawn_eligibility_claim=spawn_claim)
        if previous is not None:
            self.spawn_claims[slot]['observed']=True
        pending['physical_tracking_complete']=True
        self.records[slot]=dict(child=child,generation=generation,evidence=evidence,
            retired=False,ticket=None)
        return json.loads(json.dumps(evidence,allow_nan=False))

    def join_retired(self, slot, raw_terminal_line, read_terminal):
        require(type(slot)is int and slot in self.records,'Exact previously bound original slot required')
        current=self.records[slot]
        require(not current['retired'] and type(raw_terminal_line)is bytes
            and raw_terminal_line.endswith(b'\n') and len(raw_terminal_line)<=65537,
            'Exact unconsumed bounded durable terminal line required')
        row=json.loads(raw_terminal_line)
        initial=current['evidence'];connection=initial['connection'];child=current['child']
        require(row['client_slot']==slot and type(row['client_slot'])is int
            and row['client_id']==connection['client_id'] and type(row['client_id'])is int
            and row['eval_only']is self.roles[str(slot)]
            and all(row.get(k)is True for k in ('complete','eligible','known_start'))
            and row['boundary_reason']in('score_reset','zero_score_restart')
            and type(row['score'])is int and row['score']>=0,'Original natural complete slot/role receipt required')
        began=time.monotonic_ns()
        cleanup=json.loads(json.dumps(read_terminal(row['client_id'],slot,row['journal_game_id']),allow_nan=False))
        ended=time.monotonic_ns()
        require(cleanup['schema']=='robotron-prospective-connection-cleanup-receipt-v2'
            and cleanup['server_stamp']==self.server and cleanup['token']==connection['token']
            and cleanup['server_cleanup_incarnation']==connection['server_cleanup_incarnation']
            and cleanup['socket_endpoints']==connection['socket_endpoints']
            and cleanup['connection_ns']==connection['connection_ns']
            and cleanup['client_id']==row['client_id'] and cleanup['client_slot']==slot
            and cleanup['eval_only']is self.roles[str(slot)]
            and cleanup['terminal_receipt']==row
            and cleanup['terminal_line_sha256']==hashlib.sha256(raw_terminal_line).hexdigest()
            and cleanup['ready_for_external_join']is True
            and all(cleanup[k]is True for k in ('original_handler_stopped','original_owned_timer_stopped',
                'owned_timer_callback_succeeded','journal_disconnect_succeeded','FIFO_reset_executed','replay_consumer_healthy'))
            and cleanup['cleanup_error']is None
            and began<=cleanup['observed_monotonic_ns']<=ended and ended-began<=2_000_000_000,
            'Exact fresh original connection/terminal/handler/Timer/FIFO closure required')
        require(child.poll()==0 and child.wait(timeout=0)==0,'Original owned actor normal0 and reap required')
        try:
            still=birth(child.pid)
        except FileNotFoundError:
            still=None
        require(still is None or still['birth']!=initial['actor']['birth'],
                'Original actor PID/birth is still present')
        refill=(not self.sealed and not self.roles[str(slot)]
            and cleanup['measurement_active']is False and cleanup['replay_admission_open']is True
            and cleanup['training_refill_candidate']is True)
        proof=dict(schema='robotron-prospective-original-actor-training-refill-join-v1',
            slot=slot,generation=current['generation'],initial_physical_connection=initial,
            durable_terminal=row,durable_terminal_line_sha256=hashlib.sha256(raw_terminal_line).hexdigest(),
            actual_cleanup=cleanup,original_owned_actor_actual_exit=0,original_owned_actor_wait_reaped=True,
            original_PID_birth_absent=True,training_refill_ticket_eligible=refill,
            EVAL_role_preserved=self.roles[str(slot)],runtime_integration_qualified=False,
            rolling_membership_protocol_qualified=False,safe_refill_qualified=False)
        ticket=hashlib.sha256(json.dumps(proof,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()if refill else None
        current.update(retired=True,ticket=ticket,retirement_proof=proof)
        self.completed.append(proof)
        return dict(proof=json.loads(json.dumps(proof,allow_nan=False)),next_generation_ticket=ticket)


class RawCompletionTail:
    def __init__(self, path):
        self.path = path
        self.position = path.stat().st_size if path.exists() else 0
        self.identity = None if not path.exists() else (path.stat().st_dev, path.stat().st_ino)
        self.pending = b""

    def poll(self):
        if not self.path.exists():
            return []
        with self.path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            identity = (info.st_dev, info.st_ino)
            if self.identity is None:
                self.identity = identity
            if identity != self.identity or info.st_size < self.position:
                raise RuntimeError("Completion journal was replaced or truncated")
            stream.seek(self.position)
            raw = stream.read(2_000_000)
            self.position += len(raw)
        pieces = (self.pending + raw).split(b"\n")
        self.pending = pieces.pop()
        if len(self.pending) > 1_000_000:
            raise RuntimeError("Completion journal line exceeded bound")
        return [(json.loads(line), line+b"\n") for line in pieces if line]

