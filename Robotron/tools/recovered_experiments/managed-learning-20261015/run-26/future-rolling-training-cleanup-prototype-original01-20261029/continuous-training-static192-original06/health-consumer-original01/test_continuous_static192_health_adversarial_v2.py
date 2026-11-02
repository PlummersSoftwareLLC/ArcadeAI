"""Source-only adversarial draft; Root alone may run after source freeze.

Only SHA-bound actual pure verifier functions are compiled. All process, unit,
API, TCP, bootstrap/startup authority, CPU closeout and event evidence below is
SYNTHETIC test data. Temporary0444 events exercise the real immutable reader.
No collector/proc/API/unit/model/actor code is imported or called, and passing
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
import tempfile
import time
from types import SimpleNamespace
import unittest


HERE = Path(__file__).resolve().parent
SOURCES = {
    'registry': ('continuous_static192_registry_v1.py', '2f3eddaf75ee3b9a875d0a621a63eeea7274eae3afa75bcceb309002233316d1'),
    'health': ('continuous_static192_health_v1.py', '6fcff86103d409a3646f523a6adf6a95cc9eabd3b0090826493aaa99a7b9fbcc'),
    'transport': ('continuous_static192_transport_v1.py', '73462699277d0382cdb981167284add7b95b6cf31f2073a708cb77e52f479372'),
}


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def pin(path):
    raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), identity=identity(path.stat()))


def source(role):
    name, expected = SOURCES[role]
    if not isinstance(expected, str) or len(expected) != 64:
        raise RuntimeError('Unfrozen health fixture source: '+role)
    path = HERE/name
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    return ast.parse(raw), str(path)


def actual_pure_functions():
    common = dict(hashlib=hashlib, json=json, math=math, mmap=mmap,
        os=os, Path=Path, socket=socket, stat=stat, copy=copy)
    tree, filename = source('registry')
    ns = dict(common)
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
        or isinstance(n, ast.Assign) and all(isinstance(t, ast.Name)
            and t.id in {'MODE','SCHEMA','CASE_SCHEMA','SLOTS','STATES','FIXED_SLOT',
                         'ORIGINAL_FIELDS','COMPACT_FIELDS'} for t in n.targets)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), filename, 'exec'), ns)
    registry = SimpleNamespace(**ns)
    tree, filename = source('health')
    ns = dict(common, registry=lambda: registry)
    wanted = {'birth','stat_identity','file_identity','check_inputs','validate_optimizer_accounting',
              'stable_round_status','observed_counts','validate_policy','validate','require'}
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    # STATIC is the actual producer identity projection, not a relaxed fixture projection.
    selected += [n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'STATIC' for t in n.targets)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), filename, 'exec'), ns)
    health = SimpleNamespace(**ns)
    tree, filename = source('transport')
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
            actor_command=['/usr/games/mame', 'SYNTHETIC-NOT-EXECUTED-ROM'],
            actor_executable=dict(path='/usr/games/mame',SYNTHETIC_NOT_ACTUAL=True), actor_affinity=[0, 1],
            recipe=dict(lr=3.125e-6,epsilon=.02,expert_ratio=0.0),
            units=dict(trainer='synthetic-trainer.service', fleet='synthetic-fleet.service'),
            inputs={}, round_root=str(self.root))
        stamp = dict(pid=1000, birth=8000,source_sha256=owner_source['sha256'])
        trainer = dict(pid=1000, birth=8000, unit='synthetic-trainer.service',
            invocation_id='1'*32, cgroup='/synthetic/trainer', source=owner_source,
            server_stamp=stamp)
        supervisor = dict(pid=1001, birth=8001, unit='synthetic-fleet.service',
            invocation_id='2'*32, cgroup='/synthetic/fleet', source=owner_source)
        c = dict(mode=self.reg.MODE, epoch='1001:8001:'+('2'*32),
            supervisor=supervisor, trainer=trainer, original_slots={}, server_stamp=stamp,
            snapshot_path=str(self.root/'status.json'),
            accepted_profile='STATIC_ORIGINAL192_NO_FAULT_ADOPTION',
            maximum_proof_gap_s=2.0, narrow_API_exception_TTL_s=.5,
            launch_argv=['SYNTHETIC-ROLE-WRAPPER'], input_environment_by_slot={},
            policy_generation=0)
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
                SYNTHETIC_NOT_ACTUAL=True))
        c['source_pins'] = [pin(HERE/SOURCES[key][0]) for key in SOURCES]+[owner_source]
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
            row(conn['peer'],conn['server'],'01',30000+int(slot))
            row(conn['server'],conn['peer'],'01',40000+int(slot))
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
        status = dict(schema=self.reg.SCHEMA,mode=self.reg.MODE,epoch=c['epoch'],
            supervisor=c['supervisor'],trainer=c['trainer'],rolemap=c['rolemap'],source_authority=c['source_authority'],
            original_membership=c['original_membership'],errors=[],slots={},updated_unix_s=unix-.1,
            updated_monotonic_ns=int((mono-.1)*1e9),initial_admission=dict(complete=True,
                slots_ever_bound=list(range(192)),immutable_all192_barrier=c['initial_barrier']))
        for slot,original in c['original_slots'].items():
            # Independent implementation of the declared compact-wire hash;
            # the actual verifier's original_digest/slot_view must agree.
            raw=json.dumps(original,sort_keys=True,separators=(',',':'),
                ensure_ascii=True,allow_nan=False).encode('utf-8')
            status['slots'][slot]=dict(eval_only=self.roles[slot],incarnation=1,
                state='active_eval' if self.roles[slot] else 'active_train',
                original_pid=original['original_child']['pid'],original_birth=original['original_child']['birth'],
                original_slot_sha256=hashlib.sha256(raw).hexdigest(),natural_result=None,closure=None,
                prior_fault_closure=None,quarantine_reason=None,faults=0)
        def capture(schema):
            return dict(before_monotonic_ns=int((mono-.15)*1e9),after_monotonic_ns=int((mono-.05)*1e9),
                value=dict(schema=schema,server_stamp=c['server_stamp'],continuous_training_mode=True,
                    main_measurement_entry_disabled=True,measurement_active=False,measurement_generation=0,
                    ratchet_frozen=False,training_enabled=True,replay_admission_open=True,consumer_error=None,
                    observed_monotonic_ns=int((mono-.1)*1e9),observed_unix_s=unix-.1))
        connections = capture('robotron-continuous-active-connections-v1')
        connections['value']['connections'] = copy.deepcopy(list(self.connections.values()))
        result = dict(schema='robotron-continuous-static192-main-health-snapshot-v1',unix_s=unix,monotonic_s=mono,
            owners=copy.deepcopy(self.case['owners']),status=status,actors=actors,api=api,
            policy_capture=capture('robotron-continuous-main-policy-v1'),connections_capture=connections,
            PID_absence={},capture_started_monotonic_s=mono-.2,capture_ended_monotonic_s=mono-.01,
            transport=dict(raw_tables=dict(tcp=self.tcp_table(actors),tcp6='synthetic IPv6 header\n'),
                socket_inodes=dict(trainer=['1999']+[str(40000+int(s))for s in actors],
                                   **{s:[str(30000+int(s))]for s in actors}),
                namespaces={s:'net:[SYNTHETIC]'for s in ['trainer',*actors]},collector_namespace='net:[SYNTHETIC]'))
        self.counts(result); self.sync_children(result)
        return self.refresh(result)

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
        row['state'],row['natural_result'] = 'retiring_eval',natural
        if closed:
            conn = self.connections[slot]
            receipt = dict(schema='robotron-prospective-connection-cleanup-receipt-v2',
                server_stamp=self.case['continuous']['server_stamp'], token=conn['token'],client_id=0,
                client_slot=0,eval_only=True,connection_ns=conn['connection_ns'],socket_endpoints=conn['socket_endpoints'],
                original_handler_stopped=True,original_owned_timer_stopped=True,owned_timer_callback_succeeded=True,
                journal_disconnect_succeeded=True,FIFO_reset_executed=True,replay_consumer_healthy=True,
                ready_for_external_join=True,cleanup_error=None,terminal_receipt=result,
                terminal_line_sha256=raw_line['sha256'])
            row['closure'] = self.event('original-reaped-closure',0,dict(actual_exit=0,
                original_pid=2000,original_birth=9000,original_wait_reaped=True,original_birth_absent=True,
                natural_result=natural,restart_censored=False,connection_cleanup=[receipt]),mono=999.9)
            row['state'] = 'closed_eval'
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
        self.sync_children(sample);self.counts(sample)
        return previous,self.refresh(sample)

    def replacement_event(self, sample, field, change):
        row = sample['status']['slots']['0']
        body = self.reg.read_pin(row[field]);change(body)
        row[field] = self.write('synthetic-negative-event.json',body)
        self.refresh(sample)


class Tests(unittest.TestCase):
    def test_actual_pure_all192_case_and_strict_physical_sample_accept_only_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            h = Synthetic192(directory)
            h.reg.validate_case(h.case)
            source_only = copy.deepcopy(h.case)
            del source_only['inputs']['/usr/games/mame']
            # Actual regular-source hash checks, separately from the literal
            # MAME membership predicate. No MAME/body hash is exercised here.
            h.health.check_inputs(source_only,full=True)
            sample = h.sample()
            accepted = h.transport.validate(h.case,sample)
            self.assertEqual(accepted['partition']['active_train'],155)
            self.assertEqual(accepted['partition']['active_eval'],37)
            self.assertLess(len(h.wire(sample['status'])[0].encode()),524288)
            raw_before=copy.deepcopy(sample['status'])
            view=h.reg.validate_snapshot(h.case,sample)
            self.assertIn('original_child',view['slots']['40'])
            self.assertNotIn('original_child',sample['status']['slots']['40'])
            self.assertEqual(sample['status'],raw_before)  # raw compact wire is retained
            reports=copy.deepcopy(sample['status']);reports.update(train_games_completed=123,last_train_game=dict(score=0))
            self.assertEqual(h.health.stable_round_status(reports),h.health.stable_round_status(sample['status']))
            for field,value in [('incarnation',2),('faults',1),('prior_fault_closure',{'fake':True}),
                                ('quarantine_reason','fault'),('state','quarantined'),
                                ('original_pid',99999),('original_birth',99999),
                                ('original_slot_sha256','0'*64),('original_child',{'extra':'forbidden'})]:
                bad = copy.deepcopy(sample);bad['status']['slots']['40'][field] = value
                h.counts(bad);h.refresh(bad)
                with self.subTest(field=field),self.assertRaises(ValueError):
                    h.transport.validate(h.case,bad)

    def test_complete_immutable_barrier_role_and_source_authority_are_mandatory(self):
        with tempfile.TemporaryDirectory() as directory:
            h = Synthetic192(directory)
            for key,value in [('complete',False),('slots_ever_bound',list(range(191))),
                              ('immutable_all192_barrier',None)]:
                bad=h.sample();bad['status']['initial_admission'][key]=value;h.refresh(bad)
                with self.subTest(key=key),self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            case=copy.deepcopy(h.case);del case['continuous']['original_slots']['191']
            with self.assertRaises(ValueError):h.reg.validate_case(case)
            case=copy.deepcopy(h.case);case['continuous']['original_membership']=None
            with self.assertRaises((ValueError,TypeError)):h.reg.validate_case(case)
            case=copy.deepcopy(h.case);case['slot_eval']['40']=True
            with self.assertRaises(ValueError):h.reg.validate_case(case)
            case=copy.deepcopy(h.case);entry=case['continuous']['source_pins'][0]
            case['inputs'][entry['path']]['sha256']='0'*64
            with self.assertRaises(ValueError):h.reg.validate_case(case)
            case=copy.deepcopy(h.case);body=h.reg.read_pin(case['continuous']['initial_barrier'])
            del body['data']['physical_connections']['191']
            case['continuous']['initial_barrier']=h.write('synthetic-incomplete-barrier.json',body)
            with self.assertRaises(ValueError):h.reg.validate_case(case)
            writable=h.write('synthetic-writable-event.json',dict(x=1));Path(writable['path']).chmod(0o644)
            writable=pin(Path(writable['path']))
            with self.assertRaises(ValueError):h.reg.read_pin(writable)

    def test_actual_physical_role_owner_connection_policy_and_epoch_guards_reject_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            h = Synthetic192(directory)
            mutations=[lambda s:s['actors']['40'].__setitem__('pid',99999),
                lambda s:s['actors']['40'].__setitem__('starttime_ticks',99999),
                lambda s:s['actors']['40']['environment'].__setitem__('ROBOTRON_EVAL_MODE','1'),
                lambda s:s['owners']['trainer']['process'].__setitem__('starttime_ticks',99999),
                lambda s:s['connections_capture']['value']['connections'][40].__setitem__('token','different'),
                lambda s:s['policy_capture']['value'].__setitem__('measurement_active',True),
                lambda s:s['policy_capture']['value'].__setitem__('replay_admission_open',False),
                lambda s:s['policy_capture']['value'].__setitem__('measurement_generation',1),
                lambda s:s['api']['host_pipeline']['learning_exposure']['optimizer'].__setitem__('epoch',2)]
            for i,change in enumerate(mutations):
                bad=h.sample();change(bad);h.sync_children(bad);h.refresh(bad)
                with self.subTest(case=i),self.assertRaises(ValueError):h.transport.validate(h.case,bad)

    def test_TRAIN_cannot_retire_and_EVAL_closure_requires_exact_raw_token_reap_Timer_FIFO(self):
        with tempfile.TemporaryDirectory() as directory:
            h = Synthetic192(directory)
            previous,good=h.retired(score=0)
            self.assertEqual(h.transport.validate(h.case,good,previous)['projected_retired_API_slots'],['0'])
            bad=h.sample();bad['status']['slots']['40'].update(state='closed_eval',natural_result=good['status']['slots']['0']['natural_result'])
            h.counts(bad);h.refresh(bad)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            checks=[lambda b:b['data'].__setitem__('actual_exit',1),
                lambda b:b['data'].__setitem__('original_wait_reaped',False),
                lambda b:b['data'].__setitem__('original_birth_absent',False),
                lambda b:b['data'].__setitem__('original_birth',99999),
                lambda b:b['data']['connection_cleanup'][0].__setitem__('token','wrong'),
                lambda b:b['data']['connection_cleanup'][0].__setitem__('FIFO_reset_executed',False),
                lambda b:b['data']['connection_cleanup'][0].__setitem__('original_handler_stopped',False),
                lambda b:b['data']['connection_cleanup'][0].__setitem__('original_owned_timer_stopped',False),
                lambda b:b['data']['connection_cleanup'][0].__setitem__('owned_timer_callback_succeeded',False),
                lambda b:b['data']['connection_cleanup'][0].__setitem__('terminal_line_sha256','0'*64),
                lambda b:b['data']['connection_cleanup'][0]['terminal_receipt'].__setitem__('score',1)]
            for i,change in enumerate(checks):
                bad=copy.deepcopy(good);h.replacement_event(bad,'closure',change)
                with self.subTest(case=i),self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)
            bad=copy.deepcopy(good)
            def wrong_source(body):body['source_authority']=dict(body['source_authority'],sha256='0'*64)
            h.replacement_event(bad,'natural_result',wrong_source)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)

    def test_retired_API_requires_original_half_second_expiry_absence_and_TCP_bracket(self):
        with tempfile.TemporaryDirectory() as directory:
            h=Synthetic192(directory);previous,good=h.retired()
            self.assertEqual(h.transport.validate(h.case,good,previous)['partition']['closed_eval'],1)
            checks=[lambda s:s['api'].__setitem__('ts',h.now-.501),
                lambda s:s.__setitem__('capture_started_monotonic_s',999.499),
                lambda s:s['PID_absence']['0'].__setitem__('before_monotonic_s',999.7),
                lambda s:s['PID_absence']['0'].update(absent=False,current_birth=9001,state='S'),
                lambda s:s['api']['client_rows'][0].__setitem__('client_id',9999),
                lambda s:s['api']['client_rows'][0].__setitem__('connected_seconds',9.),
                lambda s:s['retired_API_projection']['entries'].clear()]
            for i,change in enumerate(checks):
                bad=copy.deepcopy(good);change(bad);h.refresh(bad)
                with self.subTest(case=i),self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)
            too_old=copy.deepcopy(previous);too_old['monotonic_s']=999.499
            with self.assertRaises(ValueError):h.transport.validate(h.case,good,too_old)
            prior,old_result=h.retired(age=.501)
            with self.assertRaises(ValueError):h.transport.validate(h.case,old_result,prior)
            bad=copy.deepcopy(good)
            old_lines=previous['transport']['raw_tables']['tcp'].splitlines()
            bad['transport']['raw_tables']['tcp']+='\n'.join(old_lines[1:3])+'\n'
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)

    def test_unchanged_strict_TCP_no_unknown_pair_and_two_second_proof_counter_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            h=Synthetic192(directory);previous=h.sample()
            at_limit=h.sample(mono=1002.,unix=h.now+2.)
            h.transport.validate(h.case,at_limit,previous)
            too_late=h.sample(mono=1002.00001,unix=h.now+2.00001)
            with self.assertRaises(ValueError):h.transport.validate(h.case,too_late,previous)
            bad=h.sample();bad['transport']['namespaces']['40']='net:[FOREIGN]'
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=h.sample();raw=bad['transport']['raw_tables']['tcp'].splitlines()
            extra=raw[1].split();extra[0]='999:';extra[1]='0100007F:270E';extra[2]='0100007F:7530';extra[3]='01';extra[9]='99999'
            bad['transport']['raw_tables']['tcp']+=' '.join(extra)+'\n'
            bad['transport']['socket_inodes']['trainer'].append('99999')
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=h.sample();bad['api']['client_rows']=[r for r in bad['api']['client_rows']if r['client_slot']!=40]
            bad['api']['client_count']-=1;h.refresh(bad)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)
            bad=h.sample();bad['api']['frame_count']=1;h.refresh(bad)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad,previous)
            bad=h.sample();bad['api']['host_pipeline']['learning_exposure']['replay']['accepted_total']=101;h.refresh(bad)
            with self.assertRaises(ValueError):h.transport.validate(h.case,bad)


if __name__=='__main__':
    unittest.main()
