"""Source-bound physical-cohort fixtures; Root alone operates the bounded CPU job.

Only SHA-bound actual pure verifier functions and the keeper descriptor collector are compiled.
The collector uses explicit synthetic remote-FD readers, clock, and unit records. All process, unit,
API, TCP, bootstrap/startup authority, CPU closeout and event evidence below is
SYNTHETIC test data. Temporary0444 events exercise the real immutable reader.
No live collector/proc/API/unit/model/actor operation is imported or called, and passing
these fixtures would not establish any actual startup or scientific readiness.
"""
import ast
import copy
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import socket
import stat
import struct
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest


HERE = Path(__file__).resolve().parent
SOURCES = {
    'registry': ('continuous_physical192_registry_v5.py', '8cc5340708a73ffb97b16be4b96e72b3d5560ee0b371b7ffd8d67c4074cf76b4'),
    'health': ('continuous_physical192_health_v5.py', '3818916a5921cb6b66d50249dd4266aa710b396c6169a6cad5d17257519fdda1'),
    'transport': ('continuous_physical192_transport_v5.py', '46e2e8c8435bcd644738f819a6cff8605ab68e2fb3b989a3acb9926d11623c83'),
}
LEGACY_ROOT = HERE.parent/'health-consumer-original01'
LEGACY_SOURCES = {
    'registry': ('continuous_static192_registry_v1.py', '2f3eddaf75ee3b9a875d0a621a63eeea7274eae3afa75bcceb309002233316d1'),
    'health': ('continuous_static192_health_v1.py', '6fcff86103d409a3646f523a6adf6a95cc9eabd3b0090826493aaa99a7b9fbcc'),
    'transport': ('continuous_static192_transport_v1.py', '73462699277d0382cdb981167284add7b95b6cf31f2073a708cb77e52f479372'),
}
PRODUCER = Path('/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/connection_cleanup_receipts.py')
PRODUCER_SHA = 'f27e38411238fcf62256e6b317836b757d31d5e0ac962ec8523dd380236d80ee'
SERVER = Path('/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/socket_server.py')
SERVER_SHA = 'a076501b0601a637b91269a41572be60496754ad1da4b04385d77c51b9f34423'
NEW_PROFILE = 'PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
KERNEL_SOURCE = HERE.parent/'EVAL-pidfd-exit-witness-original01-preparation/hold_original_EVAL_pidfd_exits_v1.py'
KERNEL_SOURCE_SHA = 'fe306753c9cbb20e715b76d60c116ef9ce47a768c1a1afe0b00c03eac02a095c'



def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def pin(path):
    raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), identity=identity(path.stat()))


def source(role, sources=SOURCES, root=HERE):
    name, expected = sources[role]
    if not isinstance(expected, str) or len(expected) != 64:
        raise RuntimeError('Unfrozen health fixture source: '+role)
    path = root/name
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    return ast.parse(raw), str(path)


def actual_pure_functions(sources=SOURCES, root=HERE):
    common = dict(hashlib=hashlib, json=json, math=math, mmap=mmap,
        os=os, Path=Path, socket=socket, stat=stat, copy=copy, struct=struct)
    tree, filename = source('registry',sources,root)
    ns = dict(common)
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
        or isinstance(n, ast.Assign) and all(isinstance(t, ast.Name)
            and t.id in {'MODE','SCHEMA','CASE_SCHEMA','SLOTS','STATES','FIXED_SLOT',
                         'ORIGINAL_FIELDS','COMPACT_FIELDS'} for t in n.targets)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), filename, 'exec'), ns)
    registry = SimpleNamespace(**ns)
    tree, filename = source('health',sources,root)
    ns = dict(common, registry=lambda: registry)
    wanted = {'birth','stat_identity','file_identity','check_inputs','validate_optimizer_accounting',
              'stable_round_status','observed_counts','validate_policy','validate_keeper_descriptors','validate_eval_holder','validate','require'}
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    # STATIC is the actual producer identity projection, not a relaxed fixture projection.
    selected += [n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'STATIC' for t in n.targets)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), filename, 'exec'), ns)
    health = SimpleNamespace(**ns)
    tree, filename = source('transport',sources,root)
    ns = dict(common, base=lambda: health)
    wanted = {'require','endpoint','tcp_rows','validate_transport','anchor','project_API','validate'}
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    selected += [n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'PORT' for t in n.targets)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), filename, 'exec'), ns)
    return registry, health, SimpleNamespace(**ns)


def proc(pid, birth, parent, cgroup, command, environment, executable):
    return dict(pid=pid, starttime_ticks=birth, parent_pid=parent,
        cgroup=cgroup, command=command, environment=environment,
        affinity=[0, 1], uids=[os.getuid()]*4, executable=executable, state='S')


class Synthetic192:
    """No runtime fact is asserted by these fabricated records."""
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.reg, self.health, self.transport = actual_pure_functions()
        self.sequence = 0
        # Deterministic synthetic wall clock, including temporary event mtimes;
        # no real observation time is claimed by this fixture evidence.
        self.now = 1793000000.25
        executable = self.write('synthetic-executable.txt', b'SYNTHETIC: never executed\n')
        owner_source = self.write('synthetic-owner-source.txt', b'SYNTHETIC owner source\n')
        self.roles = {str(slot): slot < 37 for slot in range(192)}
        self.case = dict(schema=self.reg.CASE_SCHEMA, slot_eval=self.roles,
            actor_environment={'ROBOTRON_CONTINUOUS_TRAINING_MODE':'1',
                'ROBOTRON_SOCKET_ADDRESS':'dell:9998','ROBOTRON_PREVIEW_FPS':'30'},
            actor_command=['/usr/games/mame', 'robotron', '-nowindow'],
            actor_executable=dict(path='/usr/games/mame',SYNTHETIC_NOT_ACTUAL=True), actor_affinity=[0, 1],
            recipe=dict(lr=3.125e-6,epsilon=.02,expert_ratio=0.0),
            units=dict(trainer='synthetic-trainer.service', fleet='synthetic-fleet.service'),
            inputs={}, round_root=str(self.root))
        server_source=pin(SERVER)
        assert server_source['sha256']==SERVER_SHA
        stamp = dict(pid=1000, birth=8000,source_sha256=server_source['sha256'])
        trainer = dict(pid=1000, birth=8000, unit='synthetic-trainer.service',
            invocation_id='1'*32, cgroup='/synthetic/trainer', source=owner_source,
            server_stamp=stamp)
        supervisor = dict(pid=1001, birth=8001, unit='synthetic-fleet.service',
            invocation_id='2'*32, cgroup='/synthetic/fleet', source=owner_source)
        c = dict(mode=self.reg.MODE, epoch='1001:8001:'+('2'*32),
            supervisor=supervisor, trainer=trainer, original_slots={}, server_stamp=stamp,
            snapshot_path=str(self.root/'status.json'),
            accepted_profile=NEW_PROFILE,
            maximum_proof_gap_s=2.0, narrow_API_exception_TTL_s=.5,
            launch_argv=['SYNTHETIC-ROLE-WRAPPER'], input_environment_by_slot={},
            policy_generation=0,eval_journal_directory=str(self.root/'journal'),eval_exit_witness=None)
        self.case['continuous'] = c
        self.case['owners'] = {key: dict(unit=owner['unit'], invocation=owner['invocation_id'],
            process=proc(owner['pid'], owner['birth'], 1, owner['cgroup'],
                ['SYNTHETIC-'+key], {'ROBOTRON_CONTINUOUS_TRAINING_MODE':'1'}, executable))
            for key, owner in [('trainer', trainer), ('fleet', supervisor)]}
        c['rolemap'] = self.write('synthetic-rolemap.json', dict(slot_eval=self.roles))
        fake_close = self.write('synthetic-CPU-closeout.json',
            dict(actual_exit=0, status='PASS_ENGINEERING_ONLY', SYNTHETIC_NOT_ACTUAL=True))
        c['source_authority'] = self.write('synthetic-startup-authority.json',
            dict(schema='robotron-root-continuous-main-startup-qualified-v1', trainer=trainer,
                all_model_optimizer_replay_banks_clocks_preserved=True,
                new_mode_source_and_CPU_qualified=True, actual_CPU_scope_closeouts=[fake_close],
                canonical_sources=[pin(HERE/SOURCES[key][0]) for key in SOURCES]+[owner_source,server_source],
                SYNTHETIC_NOT_ACTUAL=True))
        c['source_pins'] = [pin(HERE/SOURCES[key][0]) for key in SOURCES]+[owner_source,server_source]
        self.case['inputs'] = {p['path']:dict(sha256=p['sha256'], identity=p['identity'])
                               for p in c['source_pins']}
        # Literal-path membership only. This is deliberately not a fake full
        # binary identity and must never be passed to check_inputs/read_pin.
        self.case['inputs']['/usr/games/mame'] = dict(SYNTHETIC_MEMBERSHIP_ONLY=True)
        self.connections = {}
        for slot in map(str, range(192)):
            env = self.reg.expected_environment(self.case, slot)
            input_env = dict(env,ROBOTRON_EVAL_MODE='0')
            c['input_environment_by_slot'][slot] = input_env
            child = dict(pid=2000+int(slot), birth=9000+int(slot), parent=supervisor['pid'],
                cgroup=supervisor['cgroup'], launch_argv=c['launch_argv'], controlled_env=env)
            policy = dict(schema='robotron-continuous-main-policy-v1',server_stamp=stamp,
                continuous_training_mode=True,main_measurement_entry_disabled=True,
                measurement_active=False,ratchet_frozen=False,replay_admission_open=True,
                consumer_error=None,training_enabled=True,measurement_generation=0,
                observed_monotonic_ns=995900000000,observed_unix_s=self.now-10.1)
            intent = self.event('spawn-intent', int(slot),
                dict(argv=c['launch_argv'], input_environment=input_env, previous_closure=None,policy=policy), mono=996.0)
            spawned = self.event('original-child', int(slot),
                dict(original_child=dict(child, controlled_env=None), spawn_intent=intent), mono=996.1)
            conn = dict(client_slot=int(slot), client_id=int(slot), eval_only=self.roles[slot],
                connection_ns=100000+int(slot), token='synthetic-connection-'+slot,
                socket_endpoints=dict(peer=['127.0.0.1',20000+int(slot)], server=['127.0.0.1',9998]))
            self.connections[slot] = conn
            physical = self.event('physical-connection', int(slot), dict(previous_binding=None,
                actor=dict(pid=child['pid'], birth=child['birth'], parent=child['parent'],
                    cgroup=child['cgroup'], uid=os.getuid(), command=self.case['actor_command'],
                    exe=self.case['actor_executable']['path'], environment=env), connection=conn,
                process_owned_TCP=dict(inode=30000+int(slot),
                    local=conn['socket_endpoints']['peer'], remote=conn['socket_endpoints']['server'])), mono=996.2)
            c['original_slots'][slot] = dict(eval_only=self.roles[slot], incarnation=1,original_child=child,
                spawn_intent=intent, original_child_receipt=spawned, connection_binding=physical,
                )
        c['original_membership'] = self.event('original192-membership',None,
            dict(original_slots=copy.deepcopy(c['original_slots'])),incarnation=0,mono=997.)
        c['initial_barrier'] = self.event('initial-all192-barrier', None, dict(slots=list(range(192)),
            slot_eval=self.roles,original_membership=c['original_membership'],physical_connections={s:r['connection_binding']
                for s,r in c['original_slots'].items()}), incarnation=0, mono=998.0)
        lineage = dict(process_id=1000, instance_monotonic_ns=500, epoch=1, epoch_reason='synthetic')
        self.case['exposure'] = dict(optimizer=dict(lineage), replay=dict(lineage))
        self.prepare_prefix()
        self.prepare_keeper()

    def write(self, label, value):
        self.sequence += 1
        p = self.root/('%04d-' % self.sequence+label)
        raw = value if isinstance(value, bytes) else (json.dumps(value, separators=(',',':'))+'\n').encode()
        with p.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        # Immutable from the returned pin onward. This sets only a temporary
        # fixture file's mtime, avoiding real filesystem scheduling in TTL tests.
        os.utime(p,ns=(int((self.now-.05)*1e9),int((self.now-.05)*1e9)))
        return pin(p)

    def event(self, kind, slot, data, *, incarnation=1, mono=999.0, unix=None):
        c = self.case['continuous']
        return self.write('synthetic-event.json', dict(schema='robotron-continuous-training-event-v1',
            mode=self.reg.MODE, epoch=c['epoch'], kind=kind, slot=slot, incarnation=incarnation,
            supervisor=c['supervisor'], trainer=c['trainer'], source_authority=c['source_authority'],
            unix_s=(self.now-10 if kind in ('spawn-intent','original-child','physical-connection','initial-all192-barrier')
                    else self.now-.01) if unix is None else unix,
            monotonic_ns=int(mono*1e9), data=data))

    @staticmethod
    def wire(value):
        raw = json.dumps(value, separators=(',',':'))
        return raw, hashlib.sha256(raw.encode()).hexdigest()

    def refresh(self, sample):
        sample['raw_status_wire'] = self.wire(sample['status'])[0]
        sample['raw_API_wire'], sample['api_wire_sha256'] = self.wire(sample['api'])
        for key in ('policy_capture','connections_capture'):
            sample[key]['raw_wire'], sample[key]['sha256'] = self.wire(sample[key]['value'])
        return sample

    def counts(self, sample):
        sample['status']['counts'] = {state:sum(r['state']==state for r in sample['status']['slots'].values())
                                     for state in self.reg.STATES}

    def sync_children(self, sample):
        sample['original_children'] = [str(r['pid']) for r in sample['actors'].values()]
        sample['child_census'] = [dict(pid=r['pid'],record=copy.deepcopy(r),confirm_record=copy.deepcopy(r))
                                  for r in sample['actors'].values()]

    def tcp_table(self, actors):
        def endpoint(value):
            return socket.inet_aton(value[0])[::-1].hex().upper()+':%04X' % value[1]
        rows = ['synthetic Linux TCP header']
        def row(local, remote, state, inode, uid=None):
            rows.append('%d: %s %s %s 00000000:00000000 00:00000000 00000000 %d 0 %s 1 0' %
                (len(rows),endpoint(local),endpoint(remote),state,os.getuid() if uid is None else uid,inode))
        row(['0.0.0.0',9998], ['0.0.0.0',0], '0A', 1999)
        for slot in actors:
            conn = self.connections[slot]['socket_endpoints']
            row(conn['peer'],conn['server'],'01',self.client_inode(slot))
            row(conn['server'],conn['peer'],'01',self.server_inode(slot))
        return '\n'.join(rows)+'\n'

    def sample(self, *, mono=1000.0, unix=None):
        unix = self.now if unix is None else unix
        c = self.case['continuous']
        optimizer = dict(self.case['exposure']['optimizer'], schema='robotron-optimizer-exposure-v1',
            enabled=True, available=True, unclassified_started_total=0,
            total=dict(attempts_started=10,outcomes_recorded=10,applied=10,amp_skipped=0,unavailable=0),
            since_epoch=dict(attempts_started=10,outcomes_recorded=10,applied=10,amp_skipped=0,unavailable=0))
        replay = dict(self.case['exposure']['replay'], enabled=True, available=True, accepted_total=100,
            accepted_learner_total=80, accepted_by_source_total=dict(dqn=60,epsilon=20,eval=20,expert=0))
        api = dict(training_enabled=True,measurement_active=False,ts=unix-.05,pipeline_snapshot_age_s=.05,
            **self.case['recipe'],training_steps=10,learner_frame_count=100,optimized_samples=40960,frame_count=200,
            host_pipeline=dict(learning_exposure=dict(optimizer=optimizer,replay=replay)),
            client_count=192,client_rows=[dict(client_slot=int(s),client_id=int(s),eval=self.roles[s],connected_seconds=10.)
                                        for s in map(str,range(192))])
        actors = {s:proc(r['original_child']['pid'],r['original_child']['birth'],c['supervisor']['pid'],
            c['supervisor']['cgroup'],self.case['actor_command'],self.reg.expected_environment(self.case,s),
            self.case['actor_executable']) for s,r in c['original_slots'].items()}
        status = self.reg.bootstrap_projection(self.case)
        def capture(schema):
            return dict(before_monotonic_ns=int((mono-.15)*1e9),after_monotonic_ns=int((mono-.05)*1e9),
                value=dict(schema=schema,server_stamp=c['server_stamp'],continuous_training_mode=True,
                    main_measurement_entry_disabled=True,measurement_active=False,measurement_generation=0,
                    ratchet_frozen=False,training_enabled=True,replay_admission_open=True,consumer_error=None,
                    observed_monotonic_ns=int((mono-.1)*1e9),observed_unix_s=unix-.1))
        connections = capture('robotron-continuous-active-connections-v1')
        connections['value']['connections'] = copy.deepcopy(list(self.connections.values()))
        result = dict(schema='robotron-original192-live-pidfd-current-eval-quiescence-snapshot-v5',unix_s=unix,monotonic_s=mono,
            owners=copy.deepcopy(self.case['owners']),status=status,actors=actors,api=api,
            policy_capture=capture('robotron-continuous-main-policy-v1'),connections_capture=connections,
            PID_absence={},EVAL_journal_evidence={},EVAL_cleanup_captures={},
            EVAL_kernel_exit_receipts={},EVAL_exit_witness_capture=None,capture_started_monotonic_s=mono-.2,capture_ended_monotonic_s=mono-.01,
            transport=dict(raw_tables=dict(tcp=self.tcp_table(actors),tcp6='synthetic IPv6 header\n'),
                socket_inodes=dict(trainer=['1999']+[str(self.server_inode(s))for s in actors],
                                   **{s:[str(self.client_inode(s))]for s in actors}),
                namespaces={s:'net:[SYNTHETIC]'for s in ['trainer',*actors]},collector_namespace='net:[SYNTHETIC]'))
        self.sync_children(result)
        self.prefix_capture(result)
        self.holder_capture(result,{})
        return self.refresh(result)


    def client_inode(self,slot):
        return getattr(self,'changed_inode',{}).get(str(slot),(30000+int(slot),40000+int(slot)))[0]

    def server_inode(self,slot):
        return getattr(self,'changed_inode',{}).get(str(slot),(30000+int(slot),40000+int(slot)))[1]

    def rebind_train(self,slot='40', *, cid=1040,token='SYNTHETIC-FRESH-TRAIN-TCP',mono=1000.0):
        """Synthetic SAME original physical actor, fresh owned endpoint/inodes.

        The source-bound current producer supplies new CID/token; the fixture
        does not invent a replacement Popen, wait/reap or actual observation.
        """
        assert self.roles[slot]is False
        if not hasattr(self,'changed_inode'):self.changed_inode={}
        self.changed_inode[slot]=(50000+int(slot),60000+int(slot))
        conn=self.connections[slot]
        conn.update(client_id=cid,token=token,connection_ns=int((mono-.3)*1e9))
        conn['socket_endpoints']['peer'][1]=31000+int(slot)
        sample=self.sample(mono=mono)
        for row in sample['api']['client_rows']:
            if row['client_slot']==int(slot):row.update(client_id=cid,connected_seconds=.2)
        # Mutable publisher diagnostics do not enter the v4 bootstrap certificate.
        sample['connections_capture']['value']['connections']=actual_current_rows(self.connections)
        return self.refresh(sample)

    def legacy(self,sample):
        case=copy.deepcopy(self.case);case['schema']='robotron-continuous-static192-health-case-v1'
        case['continuous']['accepted_profile']='STATIC_ORIGINAL192_NO_FAULT_ADOPTION'
        raw=copy.deepcopy(sample);raw['schema']='robotron-continuous-static192-main-health-snapshot-v1'
        raw['status']['schema']='robotron-continuous-training-static192-snapshot-v2'
        raw['status'].pop('historical_bootstrap_only');raw['status'].pop('current_health_claimed')
        raw['status'].update(errors=[],updated_unix_s=raw['unix_s']-.1,
            updated_monotonic_ns=int((raw['monotonic_s']-.1)*1e9))
        self.counts(raw);self.refresh(raw)
        return case,raw

    def retired(self, *, age=.1, closed=True, score=0):
        previous = self.sample(mono=999.8,unix=self.now-.2)
        sample = self.sample()
        slot = '0';row = sample['status']['slots'][slot]
        result = dict(complete=True,eligible=True,known_start=True,eval_only=True,
            client_id=0,client_slot=0,game_uid=1,score=score,journal_game_id='SYNTHETIC:1',
            boundary_reason='zero_score_restart' if score==0 else 'score_reset',
            start_unix_s=self.now-5,end_unix_s=self.now-age,
            start_context=dict(measurement_generation=0,measurement_active=False,ratchet_frozen=False))
        raw_line = self.write('synthetic-journal-line.jsonl',
            (json.dumps(result,separators=(',',':'))+'\n').encode())
        natural = self.event('natural-result',0,dict(result=result,raw_line=raw_line,natural_complete=True),
                             mono=999.85,unix=self.now-.05)
        conn = self.connections[slot]
        receipt = dict(schema='robotron-prospective-connection-cleanup-receipt-v2',
            server_stamp=self.case['continuous']['server_stamp'],token=conn['token'],client_id=0,
            client_slot=0,eval_only=True,connection_ns=conn['connection_ns'],socket_endpoints=conn['socket_endpoints'],
            original_handler_stopped=True,original_owned_timer_stopped=True,owned_timer_callback_succeeded=True,
            journal_disconnect_succeeded=True,FIFO_reset_executed=True,replay_consumer_healthy=True,replay_admission_open=True,
            ready_for_external_join=True,cleanup_error=None,terminal_receipt=result,
            terminal_line_sha256=raw_line['sha256'],observed_monotonic_ns=999900000000)
        raw=Path(raw_line['path']).read_text()
        journal=Path(self.case['continuous']['eval_journal_directory']);journal.mkdir(exist_ok=True)
        for name in ('games.jsonl','completed_clients.jsonl'):
            with (journal/name).open('a')as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
        sample['EVAL_journal_evidence'][slot]=dict(schema='robotron-independent-original-EVAL-journal-evidence-v1',
            raw_line=raw,raw_line_sha256=raw_line['sha256'],main_raw_line=raw,retirement_raw_line=raw,
            main_path=str(journal/'games.jsonl'),retirement_path=str(journal/'completed_clients.jsonl'),
            first_observed_unix_s=self.now-.05,first_observed_monotonic_s=999.9,
            retirement_line_offset=0,retirement_prefix_identity=identity((journal/'completed_clients.jsonl').stat()))
        wire,sha=self.wire(receipt)
        sample['EVAL_cleanup_captures'][slot]=dict(before_monotonic_ns=999850000000,
            after_monotonic_ns=999950000000,value=receipt,raw_wire=wire,sha256=sha)
        del sample['actors'][slot]
        sample['PID_absence'][slot] = dict(pid=2000,path='/proc/2000/stat',absent=True,current_birth=None,state=None,
            before_monotonic_s=999.9,after_monotonic_s=999.91)
        sample['connections_capture']['value']['connections'] = [c for c in sample['connections_capture']['value']['connections']
                                                                if c['client_slot']!=0]
        sample['transport']['raw_tables']['tcp'] = self.tcp_table(sample['actors'])
        del sample['transport']['socket_inodes'][slot]
        del sample['transport']['namespaces'][slot]
        sample['transport']['socket_inodes']['trainer'].remove('40000')
        sample['retired_API_projection'] = dict(schema='robotron-continuous-retired-API-evidence-v1',entries={slot:
            dict(anchor=self.transport.anchor(self.case,previous,slot),PID_absence=sample['PID_absence'][slot])})
        self.sync_children(sample);self.prefix_capture(sample)
        self.holder_capture(sample,{})
        if closed:self.kernel(sample)
        return previous,self.refresh(sample)

    def write_named(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        raw=(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()
        with path.open('xb')as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        os.utime(path,ns=(int((self.now-.05)*1e9),)*2)
        return pin(path)

    @staticmethod
    def info80(pid,parent,*,mask=39,status=0):
        # Synthetic exact kernel ABI buffers, never a pidfd/ioctl operation.
        raw=bytearray(80)
        for offset,value,fmt in ((0,mask,'Q'),(16,pid,'I'),(20,pid,'I'),(24,parent,'I'),
                                  (28,os.getuid(),'I'),(36,os.getuid(),'I'),(60,status,'i'),(72,127,'Q')):
            struct.pack_into('='+fmt,raw,offset,value)
        return bytes(raw)

    def kernel(self,sample,*,mask=44,status=0,all37=False):
        selected=self.case['continuous']['eval_exit_witness'];anchors=self.anchors_value;receipts={}
        originals=anchors['originals']
        for slot in (originals if all37 else ['0']):
            anchor=originals[slot];original=anchor['original'];raw=self.info80(original['pid'],original['parent'],mask=mask,status=status)
            info=dict(raw80_hex=raw.hex(),returned_mask=mask,supported_mask=127,exit_code_raw=status)
            value=dict(schema='robotron-original-EVAL-retained-pidfd-exit-v1',anchors=selected['anchors'],
                selection=selected['selection'],source=selected['source'],holder=selected['holder'],nonce='3'*32,
                slot=int(slot),anchor=anchor,original=original,descriptor=anchor['descriptor'],
                request_ioctl=0xc050ff0b,request_mask=0x28,original_Popen_wait_called_claimed=False,
                actor_signals_or_wait_or_reap_performed=False,returned_raw80_hex=raw.hex(),returned_info=info,
                raw_wait_status=status,normal_exit_zero=True,normal_exit=True,normal_exit_status=0,
                signal_termination=False,original_birth_absent=True,status='KERNEL_REAPED_NORMAL0',
                capture_begin_monotonic_ns=999800000000,capture_end_monotonic_ns=999850000000,
                observed_monotonic_ns=999900000000)
            path=self.kernel_output/('exit-slot-%03d.json'%int(slot))
            if path.exists():path.unlink()  # replace only this temporary synthetic scenario's test evidence
            receipts[slot]=self.write_named(path,value)
        return self.holder_capture(sample,receipts,all37=all37)

    def prepare_prefix(self):
        journal=Path(self.case['continuous']['eval_journal_directory']);journal.mkdir()
        for name in ('completed_clients.jsonl','games.jsonl'):
            with (journal/name).open('xb')as f:
                f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
        info=identity((journal/'completed_clients.jsonl').stat())
        archive=self.write('synthetic-prior-EVAL-prefix.jsonl',b'')
        thin={k:info[k]for k in ('device','inode','mode','uid','nlink')}
        record=self.write('synthetic-prior-EVAL-prefix.json',dict(
            schema='robotron-prior-cohort-EVAL-completed-prefix-v1',
            canonical_path=str(journal/'completed_clients.jsonl'),canonical_identity=thin,
            archive=archive,prefix_bytes=0,prefix_sha256=archive['sha256'],cohort_min_spawn_unix_s=self.now-10))
        self.case['continuous']['completed_clients_prefix']=record
        for entry in (record,archive):self.case['inputs'][entry['path']]=dict(sha256=entry['sha256'],identity=entry['identity'])

    def prefix_capture(self,sample):
        record=self.reg.read_pin(self.case['continuous']['completed_clients_prefix'])
        path=Path(record['canonical_path']);info=identity(path.stat())
        sample['EVAL_completed_prefix_capture']=dict(record=self.case['continuous']['completed_clients_prefix'],
            canonical_path=str(path),canonical_identity=info,raw_prefix_wire='',prefix_bytes=0,
            prefix_sha256=hashlib.sha256(b'').hexdigest(),
            before_monotonic_s=sample['monotonic_s']-.18,after_monotonic_s=sample['monotonic_s']-.17)
        return sample

    def prepare_keeper(self):
        source=pin(KERNEL_SOURCE);assert source['sha256']==KERNEL_SOURCE_SHA
        c=self.case['continuous'];c['source_pins'].append(source)
        self.case['inputs'][source['path']]=dict(sha256=source['sha256'],identity=source['identity'])
        self.kernel_output=self.root/'synthetic-retained-kernel'
        holder=dict(pid=5000,birth=10000,parent=1,uid=os.getuid(),unit='synthetic-holder.service',
            invocation_id='5'*32,cgroup='/synthetic/holder')
        originals={slot:dict(pid=row['original_child']['pid'],birth=row['original_child']['birth'],
            parent=row['original_child']['parent'],uid=os.getuid(),initial_connection_binding=row['connection_binding'])
            for slot,row in c['original_slots'].items()if self.roles[slot]}
        selection=self.write('synthetic-kernel-selection.json',dict(output=str(self.kernel_output),nonce='3'*32,originals=originals))
        anchors_value=dict(schema='robotron-original37-EVAL-pidfd-held-anchors-v1',source=source,
            selection=selection,holder=holder,nonce='3'*32,all37_acquired_while_originals_live=True,
            originals={slot:dict(slot=int(slot),original=row,fd_number=100+int(slot),
                descriptor=dict(device=5,inode=70000+int(slot),mode='0o700',uid=0),
                initial_info=dict(raw80_hex=self.info80(row['pid'],row['parent']).hex()),
                capture_end_monotonic_ns=997500000000)for slot,row in originals.items()})
        anchors=self.write_named(self.kernel_output/'held-original37-anchors.json',anchors_value)
        c['eval_exit_witness']=dict(source=source,selection=selection,anchors=anchors,output=str(self.kernel_output),holder=holder)
        self.anchors_value=anchors_value

    def synthetic_original_keeper(self):
        selected=self.case['continuous']['eval_exit_witness'];holder=selected['holder']
        return dict(unit=holder['unit'],invocation=holder['invocation_id'],process=proc(holder['pid'],holder['birth'],1,
            holder['cgroup'],['SYNTHETIC-PYTHON',selected['source']['path'],selected['source']['sha256'],
                selected['selection']['path'],selected['selection']['sha256']],{},dict(path='SYNTHETIC-PYTHON')))

    def actual_keeper_census(self,sample,publication,owner):
        """Actual source collector with synthetic remote FD readers only.

        No /proc read, pidfd acquisition, ioctl, unit query or clock observation
        occurs. Every delegated reader checks its exact synthetic selected path.
        """
        tree,filename=source('health')
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='collect_keeper_descriptors')
        selected=self.case['continuous']['eval_exit_witness'];holder=selected['holder']
        byfd={str(row['fd_number']):(slot,row)for slot,row in self.anchors_value['originals'].items()}
        calls=[]
        def row(path,kind):
            p=Path(path);assert p.parts[-3:]==(str(holder['pid']),kind,p.name)
            slot,value=byfd[p.name];return slot,value
        def descriptor(path):
            slot,value=row(path,'fd');calls.append(('stat',slot));return copy.deepcopy(value['descriptor'])
        def link(path):
            slot,value=row(path,'fd');calls.append(('link',slot));return 'anon_inode:[pidfd]'
        def fdinfo(path):
            slot,value=row(path,'fdinfo');calls.append(('fdinfo',slot))
            target=value['original']['pid']if slot in sample['actors']else -1
            return 'pos:\t0\nflags:\t02000002\nmnt_id:\t15\nino:\t%d\nPid:\t%d\nNSpid:\t%d\n'%(value['descriptor']['inode'],target,target)
        begin=int((sample['monotonic_s']-.16)*1e9);ticks=iter(begin+100000*i for i in range(500))
        def unit(name,reader):assert name==holder['unit'];return copy.deepcopy(owner)
        ns=dict(registry=lambda:self.reg,Path=Path,require=self.health.require,
            time=SimpleNamespace(monotonic_ns=lambda:next(ticks)),os=SimpleNamespace(readlink=link),
            pidfd_descriptor=descriptor,read_pidfd_info=fdinfo,unit_record=unit)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),filename,'exec'),ns)
        value=ns['collect_keeper_descriptors'](self.case,publication,object(),copy.deepcopy(owner))
        unresolved=set(self.anchors_value['originals'])-set(publication['exit_receipts'])
        assert len(calls)==len(unresolved)*6
        for slot in unresolved:
            assert calls.count(('stat',slot))==calls.count(('link',slot))==calls.count(('fdinfo',slot))==2
        return value

    def holder_capture(self,sample,receipts,*,all37=False,old_publication=True):
        c=self.case['continuous'];selected=c['eval_exit_witness'];holder=selected['holder']
        common=dict(holder=holder,source=selected['source'],selection=selected['selection'],
            anchors=selected['anchors'],nonce='3'*32,exit_receipts=receipts)
        mono=sample['monotonic_s'];sample['EVAL_kernel_exit_receipts']=receipts
        if all37:
            value=dict(common,schema='robotron-original37-EVAL-pidfd-holder-terminal-v1',
                all37_exit_receipts_present=True,unresolved_slots=[],status='ALL37_REAPED_NORMAL0')
            path=self.kernel_output/'holder-terminal.json'
            if path.exists():path.unlink()  # synthetic temporary publication only
            publication=self.write_named(path,value)
            cap=dict(state='ALL37_IMMUTABLE_EXIT_RECEIPTS_PUBLISHED',holder=None,descriptor_census=None,
                publication=dict(kind='COMPLETE_TERMINAL_PUBLICATION',immutable_pin=publication))
        else:
            value=dict(common,schema='robotron-original37-EVAL-pidfd-holder-live-v1',state='HOLDING_UNRESOLVED_ORIGINALS',
                unresolved_slots=sorted(set(self.anchors_value['originals'])-set(receipts)),
                updated_monotonic_ns=int((mono-200 if old_publication else mono-.05)*1e9),
                updated_unix_s=sample['unix_s']-(200 if old_publication else .05))
            owner=self.synthetic_original_keeper()
            cap=dict(state='HOLDING_UNRESOLVED_ORIGINALS',holder=owner,
                descriptor_census=self.actual_keeper_census(sample,value,owner),
                publication=dict(kind='LIVE_HEARTBEAT',path=str(self.kernel_output/'holder-live.json')))
        wire,sha=self.wire(value)
        cap['publication'].update(before_monotonic_ns=int((mono-.16)*1e9),after_monotonic_ns=int((mono-.02)*1e9),
            raw_wire=wire,sha256=sha,value=value)
        sample['EVAL_exit_witness_capture']=cap
        return sample

    def replacement_event(self, sample, field, change):
        row = sample['status']['slots']['0']
        body = self.reg.read_pin(row[field]);change(body)
        row[field] = self.write('synthetic-negative-event.json',body)
        self.refresh(sample)

def actual_current_rows(connections):
    """Compile the actual producer method, with explicit synthetic handler/lock.

    No real Thread is started and no server, process or socket is created.
    Only this selected method runs against a synthetic receipt-record mapping.
    """
    raw=PRODUCER.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PRODUCER_SHA:raise ValueError('Exact active-identity producer source required')
    tree=ast.parse(raw);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='ConnectionCleanupReceipts')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name=='active_identity_rows')
    ns=dict(copy=copy)
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(PRODUCER),'exec'),ns)
    rows={c['token']:dict(cid=c['client_id'],slot=c['client_slot'],eval_only=c['eval_only'],
        connection_ns=c['connection_ns'],endpoints=copy.deepcopy(c['socket_endpoints']),recorded=False,
        handler=SimpleNamespace(is_alive=lambda:True))for c in connections.values()}
    book=SimpleNamespace(lock=threading.Lock(),records=rows)
    return ns['active_identity_rows'](book,set(rows))



class Tests(unittest.TestCase):
    def test_actual_current_producer_and_same_physical_TRAIN_new_owned_TCP(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Synthetic192(directory);h.reg.validate_case(h.case)
            sample=h.rebind_train();original=h.case['continuous']['original_slots']['40']['original_child']
            self.assertEqual(sample['actors']['40']['pid'],original['pid'])
            self.assertEqual(sample['actors']['40']['starttime_ticks'],original['birth'])
            h.transport.validate(h.case,sample)
            view=h.reg.validate_snapshot(h.case,sample)
            self.assertEqual(view['current_connections']['40']['client_id'],1040)
            self.assertEqual(view['current_connections']['40']['token'],'SYNTHETIC-FRESH-TRAIN-TCP')
            self.assertEqual(len(view['current_connections']),192)
            certificate=copy.deepcopy(sample['status'])
            self.assertTrue(certificate['historical_bootstrap_only']);self.assertFalse(certificate['current_health_claimed'])
            # Deliberately malformed and oversized SYNTHETIC mutable publisher data.
            # No actual production/status file is read or written by the fixture.
            Path(h.case['continuous']['snapshot_path']).write_bytes(b'SYNTHETIC UNREAD BAD STATUS '*24000)
            self.assertEqual(h.reg.bootstrap_projection(h.case),certificate)
            h.transport.validate(h.case,sample)
            bad=copy.deepcopy(sample);bad['status']['current_health_claimed']=True;h.refresh(bad)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            oldreg,oldhealth,oldtransport=actual_pure_functions(LEGACY_SOURCES,LEGACY_ROOT)
            case,old_sample=h.legacy(sample)
            with self.assertRaises(ValueError):oldtransport.validate(case,old_sample)
            rows=actual_current_rows(h.connections)
            self.assertNotIn('game_uid',rows[0]);self.assertNotIn('pid',rows[0])

    def test_original192_authority_no_replacement_source_or_role_drift(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Synthetic192(directory)
            for mutation in ('membership','barrier','slot','role','source'):
                case=copy.deepcopy(h.case)
                if mutation=='membership':case['continuous']['original_membership']=None
                elif mutation=='barrier':case['continuous']['initial_barrier']=None
                elif mutation=='slot':del case['continuous']['original_slots']['191']
                elif mutation=='role':case['slot_eval']['40']=True
                else:
                    entry=case['continuous']['source_pins'][0];case['inputs'][entry['path']]['sha256']='0'*64
                with self.subTest(mutation=mutation),self.assertRaises((ValueError,TypeError)):
                    h.reg.validate_case(case)
            entry=h.write('tiny-held-input.txt',b'SYNTHETIC tiny held source\n')
            tiny=dict(inputs={entry['path']:dict(sha256=entry['sha256'],identity=entry['identity'])})
            h.health.check_inputs(tiny,full=True)
            for key,value in [('sha256','0'*64),('identity',dict(entry['identity'],inode=0))]:
                bad=copy.deepcopy(tiny);bad['inputs'][entry['path']][key]=value
                with self.subTest(input_guard=key),self.assertRaises(ValueError):h.health.check_inputs(bad,full=True)
            link=h.root/'synthetic-input-symlink';link.symlink_to(entry['path'])
            bad=dict(inputs={str(link):dict(sha256=entry['sha256'],identity=entry['identity'])})
            with self.assertRaises(ValueError):h.health.check_inputs(bad,full=True)
            sample=h.rebind_train()
            for field,value in [('pid',999999),('starttime_ticks',999999),('parent_pid',999999),('cgroup','/foreign')]:
                bad=copy.deepcopy(sample);bad['actors']['40'][field]=value;h.sync_children(bad)
                with self.subTest(field=field),self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=copy.deepcopy(sample);bad['actors']['40']['executable']={'path':'/foreign/mame'};h.sync_children(bad)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=copy.deepcopy(sample);bad['actors']['40']['environment']['ROBOTRON_EVAL_MODE']='1';h.sync_children(bad)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)

    def test_current_TRAIN_connections_unique_owned_and_raw_evidence_not_forged(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Synthetic192(directory);good=h.rebind_train()
            rows=good['connections_capture']['value']['connections']
            byslot={str(r['client_slot']):i for i,r in enumerate(rows)}
            for key,value in [('client_id',rows[byslot['41']]['client_id']),('token',rows[byslot['41']]['token']),('eval_only',True)]:
                bad=copy.deepcopy(good);bad['connections_capture']['value']['connections'][byslot['40']][key]=value;h.refresh(bad)
                with self.subTest(key=key),self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=copy.deepcopy(good);bad['connections_capture']['value']['connections'][byslot['40']]['socket_endpoints']['peer'][1]+=1;h.refresh(bad)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=copy.deepcopy(good);bad['transport']['namespaces']['40']='net:[FOREIGN]'
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=copy.deepcopy(good);bad['transport']['socket_inodes']['41'].append(str(h.client_inode('40')))
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=copy.deepcopy(good);actors=dict(bad['actors']);actors.pop('40');bad['transport']['raw_tables']['tcp']=h.tcp_table(actors)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=copy.deepcopy(good);bad['connections_capture']['raw_wire']='{}'  # deliberately NOT refreshed
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=copy.deepcopy(good);bad['connections_capture']['value']['server_stamp']['source_sha256']='0'*64;h.refresh(bad)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)

    def test_EVAL_keeps_original_connection_natural_row_and_positive_normal_closure(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Synthetic192(Path(directory)/'normal');previous,good=h.retired(score=0)
            h.reg.validate_case(h.case);h.transport.validate(h.case,good,previous)
            self.assertEqual(h.reg.validate_snapshot(h.case,good,previous)['counts']['closed_eval'],1)
            # Bootstrap is historical even when independent journal/kernel/cleanup closes EVAL.
            self.assertIsNone(good['status']['slots']['0']['natural_result'])
            self.assertIsNone(good['status']['slots']['0']['closure'])
            active=h.sample();next(r for r in active['connections_capture']['value']['connections']if r['client_slot']==0)['token']='NEW-EVAL-TOKEN';h.refresh(active)
            with self.assertRaises(ValueError):h.transport.validate(h.case,active)
            for flag in ('original_handler_stopped','original_owned_timer_stopped','owned_timer_callback_succeeded',
                         'journal_disconnect_succeeded','FIFO_reset_executed','replay_consumer_healthy'):
                bad=copy.deepcopy(good);value=bad['EVAL_cleanup_captures']['0']['value'];value[flag]=False
                raw,sha=h.wire(value);bad['EVAL_cleanup_captures']['0'].update(raw_wire=raw,sha256=sha)
                with self.subTest(cleanup=flag),self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)
            for field,value in [('original_birth_absent',False),('normal_exit_zero',False),('source',dict(path='foreign'))]:
                bad=copy.deepcopy(good);body=h.reg.read_pin(bad['EVAL_kernel_exit_receipts']['0']);body[field]=value
                path=h.kernel_output/'exit-slot-000.json';path.unlink();entry=h.write_named(path,body)
                bad['EVAL_kernel_exit_receipts']['0']=entry
                pub=bad['EVAL_exit_witness_capture']['publication'];pub['value']['exit_receipts']['0']=entry
                wire,sha=h.wire(pub['value']);pub.update(raw_wire=wire,sha256=sha)
                with self.subTest(exit_guard=field),self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)
                h.kernel(good)  # restore a new synthetic positive receipt for the next independent negative
            h=Synthetic192(Path(directory)/'pending');prior,missing=h.retired(closed=False)
            h.transport.validate(h.case,missing,prior)
            view=h.reg.validate_snapshot(h.case,missing,prior)
            self.assertEqual(view['counts']['closed_eval'],0);self.assertEqual(view['counts']['retiring_eval'],1)
            # Pid=-1 on a held descriptor proves neither exit code nor reaping.
            raw=missing['EVAL_exit_witness_capture']['descriptor_census']['descriptors']['0']['raw_fdinfo_before']
            self.assertIn('Pid:\t-1',raw)
            with self.assertRaises(ValueError):h.reg.kernel_eval_exit(h.case,missing,'0')
            bad=copy.deepcopy(missing);bad['EVAL_cleanup_captures'].clear()
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad,prior)
            h.kernel(missing);h.transport.validate(h.case,missing,prior)
            self.assertEqual(h.reg.validate_snapshot(h.case,missing,prior)['counts']['closed_eval'],1)
            unlisted=h.holder_capture(copy.deepcopy(missing),{})
            self.assertTrue((h.kernel_output/'exit-slot-000.json').is_file())
            self.assertEqual(h.reg.validate_snapshot(h.case,unlisted,prior)['counts']['closed_eval'],0)
            with self.assertRaises(ValueError):h.health.validate_eval_holder(h.case,unlisted,missing)
            for mask,status in [(0,0),(39,0),(44,15),(44,1792)]:
                h.kernel(missing,mask=mask,status=status)
                with self.subTest(mask=mask,raw_wait_status=status),self.assertRaises(ValueError):h.transport.validate(h.case,missing,prior)
            h.kernel(missing)
            bad=copy.deepcopy(missing);bad['EVAL_exit_witness_capture']['publication']['value']['exit_receipts']={}
            pub=bad['EVAL_exit_witness_capture']['publication'];wire,sha=h.wire(pub['value']);pub.update(raw_wire=wire,sha256=sha)
            with self.assertRaises(ValueError):h.health.validate_eval_holder(h.case,bad)
            with self.assertRaises(ValueError):h.reg.kernel_eval_exit(h.case,bad,'0')
            # An authentic old publication clock is acceptable only with a fresh actual-FD census.
            h.health.validate_eval_holder(h.case,missing)
            for field,value in [('updated_monotonic_ns',1001000000000),('updated_monotonic_ns',-1),
                                ('updated_monotonic_ns',999900000000.5),('updated_monotonic_ns',True),
                                ('updated_unix_s',missing['unix_s']+1),('updated_unix_s',-1),
                                ('updated_unix_s',float('nan'))]:
                bad=copy.deepcopy(missing);pub=bad['EVAL_exit_witness_capture']['publication']
                pub['value'][field]=value;wire,sha=h.wire(pub['value']);pub.update(raw_wire=wire,sha256=sha)
                with self.subTest(publication_clock=field,value=value),self.assertRaises(ValueError):
                    h.health.validate_eval_holder(h.case,bad)
            for mutation in ('dead','birth','missing_fd','inode','target','namespace','live_target_absent','duplicate','bracket','source','foreign_fd','reused_fd'):
                bad=copy.deepcopy(missing);cap=bad['EVAL_exit_witness_capture'];census=cap['descriptor_census']
                if mutation=='dead':census['owner_after']['process']['state']='Z'
                elif mutation=='birth':census['owner_after']['process']['starttime_ticks']+=1
                elif mutation=='missing_fd':census['descriptors'].pop('1')
                elif mutation=='inode':census['descriptors']['1']['descriptor_after']['inode']+=1
                elif mutation=='target':census['descriptors']['1']['raw_fdinfo_after']=census['descriptors']['1']['raw_fdinfo_after'].replace('Pid:\t2001','Pid:\t9999')
                elif mutation=='namespace':census['descriptors']['1']['raw_fdinfo_after']=census['descriptors']['1']['raw_fdinfo_after'].replace('NSpid:\t2001','NSpid:\t2001 100')
                elif mutation=='live_target_absent':
                    census['descriptors']['1']['raw_fdinfo_after']=census['descriptors']['1']['raw_fdinfo_after'].replace('Pid:\t2001','Pid:\t-1').replace('NSpid:\t2001','NSpid:\t-1')
                elif mutation=='duplicate':census['descriptors']['1']['descriptor_before']=copy.deepcopy(census['descriptors']['2']['descriptor_before'])
                elif mutation=='bracket':census['after_monotonic_ns']=1001000000000
                elif mutation=='source':census['owner_after']['process']['command']=['FOREIGN']
                elif mutation=='foreign_fd':census['descriptors']['1']['link_after']='socket:[123]'
                else:census['descriptors']['1']['fd_number']+=1
                with self.subTest(FD_guard=mutation),self.assertRaises(ValueError):h.health.validate_eval_holder(h.case,bad)
            # Only actual publication/kernel predicates are exercised here;
            # this synthetic terminal does not prove still-present actors exited.
            terminal=h.sample();h.kernel(terminal,all37=True)
            h.health.validate_eval_holder(h.case,terminal)
            for slot in terminal['EVAL_kernel_exit_receipts']:h.reg.kernel_eval_exit(h.case,terminal,slot)
            bad=copy.deepcopy(terminal);bad['EVAL_kernel_exit_receipts'].pop('36')
            with self.assertRaises(ValueError):h.health.validate_eval_holder(h.case,bad)

    def test_retired_EVAL_half_second_TTL_and_original_absence_TCP_brackets_remain(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Synthetic192(directory);previous,good=h.retired()
            h.transport.validate(h.case,good,previous)
            checks=[lambda s:s['api'].__setitem__('ts',h.now-.501),lambda s:s.__setitem__('capture_started_monotonic_s',999.499),
                lambda s:s['PID_absence']['0'].__setitem__('before_monotonic_s',999.7),
                lambda s:s['PID_absence']['0'].update(absent=False,current_birth=9001,state='S'),
                lambda s:s['retired_API_projection']['entries'].clear()]
            for i,change in enumerate(checks):
                bad=copy.deepcopy(good);change(bad);h.refresh(bad)
                with self.subTest(case=i),self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)
            bad=copy.deepcopy(good);bad['transport']['raw_tables']['tcp']+='\n'.join(previous['transport']['raw_tables']['tcp'].splitlines()[1:3])+'\n'
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)

    def test_two_second_proof_policy_epochs_and_counters_remain_strict(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Synthetic192(directory);previous=h.sample()
            h.transport.validate(h.case,h.sample(mono=1002.,unix=h.now+2.),previous)
            with self.assertRaises(ValueError):h.transport.validate(h.case,h.sample(mono=1002.00001,unix=h.now+2.00001),previous)
            changes=[lambda s:s['policy_capture']['value'].__setitem__('measurement_active',True),
                lambda s:s['policy_capture']['value'].__setitem__('replay_admission_open',False),
                lambda s:s['policy_capture']['value'].__setitem__('measurement_generation',1),
                lambda s:s['api']['host_pipeline']['learning_exposure']['optimizer'].__setitem__('epoch',2),
                lambda s:s['api'].__setitem__('frame_count',1)]
            for i,change in enumerate(changes):
                bad=h.sample();change(bad);h.refresh(bad)
                with self.subTest(case=i),self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)


    def test_current_once_EVAL_generic_latch_class_preserves_raw_history_and_all_other_proofs(self):
        with tempfile.TemporaryDirectory()as directory:
            for score in (0,12345):
                with self.subTest(score=score):
                    h=Synthetic192(Path(directory)/('score-%d'%score));previous,sample=h.retired(score=score)
                    ordinary=copy.deepcopy(sample['EVAL_cleanup_captures']['0']['value'])
                    normal=h.reg.classify_cleanup_postconditions(ordinary)
                    self.assertEqual(normal['classification'],'ORDINARY_CLEANUP_COMPLETED')
                    self.assertTrue(normal['current_postconditions_proved'])
                    self.assertTrue(normal['original_ready_for_external_join'])
                    self.assertFalse(normal['original_cleanup_success_or_CID_reuse_claimed'])
                    incomplete=h.reg.classify_cleanup_postconditions(dict(ordinary,ready_for_external_join=False))
                    self.assertEqual(incomplete['classification'],'CLEANUP_INCOMPLETE')
                    self.assertIs(incomplete['current_postconditions_proved'],False)
                    value=sample['EVAL_cleanup_captures']['0']['value']
                    value.update(cleanup_error='Original connection cleanup failed',ready_for_external_join=False)
                    wire,sha=h.wire(value);sample['EVAL_cleanup_captures']['0'].update(raw_wire=wire,sha256=sha)
                    frozen=copy.deepcopy((h.case,sample))
                    classification=h.reg.classify_cleanup_postconditions(value)
                    self.assertEqual(classification['classification'],
                        'CURRENT_ONCE_ONLY_EVAL_QUIESCENCE_AFTER_RECORDED_DISCONNECT_EXCEPTION')
                    self.assertTrue(classification['current_postconditions_proved'])
                    self.assertEqual(classification['historical_cleanup_error'],'Original connection cleanup failed')
                    self.assertIs(classification['original_ready_for_external_join'],False)
                    self.assertIs(classification['original_cleanup_success_or_CID_reuse_claimed'],False)
                    self.assertIs(classification['original_deadline_or_wait_exception_subtype_proved'],False)
                    self.assertIs(classification['refill_external_handoff_or_reservation_release_authorized'],False)
                    h.transport.validate(h.case,sample,previous)
                    self.assertEqual(h.reg.validate_snapshot(h.case,sample,previous)['counts']['closed_eval'],1)
                    self.assertEqual((h.case,sample),frozen)
                    self.assertEqual(sample['EVAL_cleanup_captures']['0']['value']['cleanup_error'],
                        'Original connection cleanup failed')
                    self.assertIs(sample['EVAL_cleanup_captures']['0']['value']['ready_for_external_join'],False)
                    self.assertEqual(sample['EVAL_cleanup_captures']['0']['raw_wire'],wire)
                    self.assertEqual(sample['EVAL_cleanup_captures']['0']['sha256'],sha)
                    # A cleanup classification alone cannot prove the selected
                    # original actor exited/reaped or its socket disappeared.
                    pending=copy.deepcopy(sample);h.holder_capture(pending,{})
                    with self.assertRaises(ValueError):h.reg.validate_snapshot(h.case,pending,previous)
                    with self.assertRaises(ValueError):h.reg.kernel_eval_exit(h.case,pending,'0')

    def test_current_once_EVAL_recovery_refuses_false_missing_forged_and_future_evidence(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Synthetic192(directory);previous,good=h.retired()
            base=good['EVAL_cleanup_captures']['0']['value']
            base.update(cleanup_error='Original connection cleanup failed',ready_for_external_join=False)
            wire,sha=h.wire(base);good['EVAL_cleanup_captures']['0'].update(raw_wire=wire,sha256=sha)
            h.transport.validate(h.case,good,previous)
            primitives=('original_handler_stopped','original_owned_timer_stopped','owned_timer_callback_succeeded',
                        'journal_disconnect_succeeded','FIFO_reset_executed','replay_consumer_healthy')
            mutations=[]
            for flag in primitives:
                for kind in ('false','missing','nonbool'):
                    mutations.append((flag,kind))
            mutations += [('cleanup_error',v)for v in ('different failure','Original connection cleanup failed ',True)]
            mutations += [('ready_for_external_join',True),('replay_admission_open',False),('replay_admission_open','missing'),
                ('token','wrong'),('client_id',9999),('client_slot',191),('eval_only',False),('connection_ns',0),
                ('terminal_line_sha256','0'*64),('terminal_receipt',None)]
            for field,value in mutations:
                bad=copy.deepcopy(good);capture=bad['EVAL_cleanup_captures']['0'];record=capture['value']
                if value=='missing':record.pop(field)
                elif value=='false':record[field]=False
                elif value=='nonbool':record[field]=1
                else:record[field]=value
                wire,sha=h.wire(record);capture.update(raw_wire=wire,sha256=sha)
                before=copy.deepcopy((h.case,bad))
                with self.subTest(field=field,value=value),self.assertRaises((ValueError,KeyError)):
                    h.transport.validate(h.case,bad,previous)
                self.assertEqual((h.case,bad),before)
            # Invalid source, terminal bytes, replay policy and current clocks
            # cannot be masked by the newly recognized historical error class.
            changes=[lambda s:s['EVAL_cleanup_captures']['0']['value']['server_stamp'].__setitem__('source_sha256','0'*64),
                lambda s:s['EVAL_cleanup_captures']['0']['value'].__setitem__('observed_monotonic_ns',1001000000000),
                lambda s:s['EVAL_cleanup_captures']['0'].__setitem__('before_monotonic_ns',997900000000),
                lambda s:s['EVAL_journal_evidence']['0'].__setitem__('raw_line_sha256','0'*64),
                lambda s:s['policy_capture']['value'].__setitem__('replay_admission_open',False),
                lambda s:s['PID_absence']['0'].update(absent=False,current_birth=9000,state='S'),
                lambda s:s['api'].__setitem__('ts',h.now-.501)]
            for i,change in enumerate(changes):
                bad=copy.deepcopy(good);change(bad);h.refresh(bad)
                capture=bad['EVAL_cleanup_captures']['0'];wire,sha=h.wire(capture['value']);capture.update(raw_wire=wire,sha256=sha)
                with self.subTest(strict_gate=i),self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)
            bad=copy.deepcopy(good);bad['transport']['raw_tables']['tcp']+='\n'.join(previous['transport']['raw_tables']['tcp'].splitlines()[1:3])+'\n'
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)
            # Exercise actual raw80 decoding under the recovery-positive cleanup.
            for mask,status in ((0,0),(39,0),(44,15),(44,1792)):
                h.kernel(good,mask=mask,status=status)
                with self.subTest(EXIT_mask=mask,raw_status=status),self.assertRaises(ValueError):
                    h.transport.validate(h.case,good,previous)
            h.kernel(good)
            self.assertIs(good['EVAL_cleanup_captures']['0']['value']['ready_for_external_join'],False)
            self.assertEqual(good['EVAL_cleanup_captures']['0']['value']['cleanup_error'],'Original connection cleanup failed')


if __name__=='__main__':unittest.main()
