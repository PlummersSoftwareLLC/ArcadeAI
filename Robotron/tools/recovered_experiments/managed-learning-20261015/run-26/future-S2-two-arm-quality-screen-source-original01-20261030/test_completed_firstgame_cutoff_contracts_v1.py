"""Root-only synthetic contracts using selected recorder/retirement/proxy ASTs.

Default inert. Only the selected pure wire codec is imported; other target
definitions are AST-extracted. No model/array, process, API or native socket action. Sources are authenticated before compiling isolated definitions.
"""
import argparse, ast, copy, hashlib, importlib.util, json, math, os, stat, statistics, struct, sys, tempfile, threading, time, types, unittest
from pathlib import Path


PARENT_LIFECYCLE={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025/evaluator-count-active600-counterbalanced-engineering-original06/future-startup-slot64-chain-correction-original01/run_cold_slot64_prefix_v1.py',
 'sha256': '9f6820ea3633d8e411f4408846d0aaef7a9b9bde1393b16975293315a32ca25d',
 'bytes': 61329,
 'identity': {'device': 2304,
              'inode': 84561442,
              'bytes': 61329,
              'mtime_ns': 1793049597343877802,
              'ctime_ns': 1793049597343877802,
              'mode': '0o444',
              'uid': 1001,
              'nlink': 1}}
MODULUS=None


def checked(entry):
    p=Path(entry['path']);a=p.lstat()
    assert p.is_absolute()and p.resolve()==p and not p.is_symlink()and stat.S_ISREG(a.st_mode)
    assert a.st_uid==os.getuid()and a.st_nlink==1 and stat.S_IMODE(a.st_mode)==0o444 and 0<a.st_size<=1<<20
    identity=lambda s:dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    raw=p.read_bytes();assert identity(a)==identity(p.lstat())and len(raw)==entry['bytes']and hashlib.sha256(raw).hexdigest()==entry['sha256']
    assert all(identity(a)[k]==v for k,v in entry['identity'].items())
    return raw


def definitions(entry,names,*,assignments=(),namespace=None):
    tree=ast.parse(checked(entry));body=[];found=set()
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef))and node.name in names:body.append(node);found.add(node.name)
        elif isinstance(node,ast.Assign)and any(isinstance(t,ast.Name)and t.id in assignments for t in node.targets):body.append(node)
    assert found==set(names)
    scope=dict(copy=copy,deepcopy=copy.deepcopy,math=math,statistics=statistics,threading=threading,time=time,json=json,os=os,stat=stat,Path=Path)
    scope.update(namespace or {});exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),entry['path']+'::synthetic-contract', 'exec'),scope)
    return scope


class Clock:
    def __init__(self):self.now=10_000_000_000
    def __call__(self):return self.now


class Event:
    def __init__(self,value=False,wait=None):self.value=value;self.on_wait=wait
    def is_set(self):return self.value
    def set(self):self.value=True
    def wait(self,seconds):return self.on_wait(seconds)if self.on_wait else self.value


def member(slot):
    return dict(slot=slot,session=f'{slot:032x}',connection=f'{slot+10000:032x}',game_uid=slot,journal_game_id=f'original:{slot}',start_certificate_id=f'{slot:064x}',startup_nonce=f'{slot+10000:064x}',policy_sha256='c'*64,measurement_generation=1,experiment='synthetic-screen',policy_clocks=dict(learner_frame_count=4_000_000_000,training_steps=15_000_000,optimized_samples=60_000_000_000))


def sample(slot,stamp,*,sequence=1201,before=9,score=100,origin_uid=None,selected=None):
    if selected is None:selected=dict(journal_game_id=f'original:{slot}',game_uid=slot,known_start=True,first_play_level=1,measurement_active=True,measurement_generation=1,mixed_experiment=False,mixed_measurement=False,experiment='synthetic-screen',score=score,playable_frames=sequence,finished=False,result=None)
    return dict(sequence=sequence,completed_exchange_ns=stamp,before_ordinal=before,accepted_ordinal=before+1,origin_game_uid=slot if origin_uid is None else origin_uid,full_score=score,effective_raw_score=score%MODULUS,score_offset=score-score%MODULUS,raw_wire_score=score%MODULUS,coerced_score_dips=0,policy_sha256='c'*64,measurement_generation=1,selected=selected,source_witness=dict(fixture_only=True,payload_sha256='d'*64))


def terminal(slot,stamp,score=200):
    confirmation=dict(schema='robotron-confirmed-game-reset-v1',reason='score_reset',previous_score=score,next_score=0,previous_game_uid=slot,next_game_uid=slot+50000,next_journal_game_id=f'next:{slot}',classifier_new_game=True)
    result=dict(journal_game_id=f'original:{slot}',game_uid=slot,client_slot=slot,complete=True,eligible=True,known_start=True,measurement_active=True,measurement_generation=1,experiment='synthetic-screen',first_play_level=1,score=score,terminal_confirmation=confirmation)
    selected=dict(journal_game_id=f'original:{slot}',game_uid=slot,known_start=True,first_play_level=1,measurement_active=True,measurement_generation=1,mixed_experiment=False,mixed_measurement=False,experiment='synthetic-screen',score=score,playable_frames=2000,finished=True,result=result)
    return sample(slot,stamp,sequence=1203,before=11,score=0,origin_uid=slot+50000,selected=selected)


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=Path(ARGS.sources).read_bytes();assert len(raw)<=1<<20 and hashlib.sha256(raw).hexdigest()==ARGS.sources_sha256
        sources=json.loads(raw);assert sources['existing_lifecycle_validator_parent']==PARENT_LIFECYCLE
        cls.pins=sources['selected'];base=json.loads(checked(sources['base_job']))
        cls.r=definitions(cls.pins['recorder'],{'require','integer','hex_value','identifier','DeadlineScoreRecorder'},assignments={'SLOTS','HORIZON_NS','MAX_AGE_NS','SCORE_MODULUS','MEMBER_KEYS','CLOCK_KEYS'})
        global MODULUS
        MODULUS=cls.r['SCORE_MODULUS']
        cls.s=definitions(cls.pins['support'],{'require','read_completed_lifecycle','CompletedRegistration'})
        codec_pin=cls.pins['completion_codec'];checked(codec_pin)
        assert 'wire_codec_v2'not in sys.modules
        spec=importlib.util.spec_from_file_location('wire_codec_v2',codec_pin['path']);codec=importlib.util.module_from_spec(spec);sys.modules[spec.name]=codec;spec.loader.exec_module(codec);checked(codec_pin);cls.codec=codec
        cls.child_lifecycle=staticmethod(definitions(PARENT_LIFECYCLE,{'require','validate_lifecycle'})['validate_lifecycle'])
        cls.lifecycle=base['components']['lifecycle'];cls.source_AST={}
        for role,pin in {**{k:cls.pins[k]for k in('recorder','support','clock_proxy','completion_codec')},'lifecycle':cls.lifecycle,'child_lifecycle':PARENT_LIFECYCLE}.items():
            tree=ast.parse(checked(pin));cls.source_AST[role]={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)}
    def ready(self,arm=True,initial_score=100):
        c=Clock();r=self.r['DeadlineScoreRecorder'](clock_ns=c);r.positively_retired_slots=set()
        for slot in self.r['SLOTS']:r.bind(slot,member(slot));r.observe(slot,sample(slot,c.now,score=initial_score))
        boundary=dict(ready=True,active=True,generation=1,requested_generation=1,clients=32,expected=32,acknowledged=32,actor_slots=list(self.r['SLOTS']),pending_client_ids=[],replay_pending_client_ids=[])
        if arm:r.arm(dict(all_first_play_certified=True,policy_sha256='c'*64,measurement_generation=1,boundary=boundary))
        return r,c,boundary
    def completed(self,arm=True,score=200):
        r,c,b=self.ready(arm=arm);slot=4096;c.now+=100;r.observe(slot,sample(slot,c.now,sequence=1202,before=10,score=score));c.now+=100;r.observe(slot,terminal(slot,c.now,score));return r,c,b
    def register(self,r):
        reg=self.s['CompletedRegistration'](r,self.child_lifecycle);m=r._members[4096]
        reg.register_start(slot=4096,session=m['session'],connection=m['connection'],nonce=m['startup_nonce'],client_id=7,journal_game_id=m['journal_game_id'],certificate_identifier=m['start_certificate_id'])
        view=reg.for_slot(4096);subject=dict(slot=4096,session=m['session'],connection=m['connection'],nonce=m['startup_nonce'],sequence=1204)
        return reg,view,subject
    def lifecycle_rows(self,proxy):
        base=dict(schema='robotron-full-tail-lifecycle-v2',**proxy.subject);seq=proxy.sequence;wire=proxy.last_response.hex()
        rows=[dict(base,kind='header',sequence=0,trace_frame_limit=1200,continuation_enabled=True),dict(base,kind='prefix_closed',sequence=1200,failed=False,machine_exit_requested=False,trace_events=2402,first_play_sequence=120,initialized_sequence=110,latched_sequence=111),dict(base,kind='stop_response',sequence=seq,response_hex=wire,nonce=proxy.issuer.nonce),dict(base,kind='stop_applied',sequence=seq,response_hex=wire,nonce=proxy.issuer.nonce,socket_ok=True,apply_ok=True,debug_bypass=False,held_start_before_response=False,start=0,coin=0),dict(base,kind='exit_requested',sequence=seq,response_hex=wire,apply_ok=True),dict(base,kind='closed',sequence=seq,reason='drained_shutdown',failed=False,stop_received=True)]
        for number,row in enumerate(rows,1):row['event']=number
        return rows
    def write_lifecycle(self,row,values,*,newline=True):
        path=row['private']/'lifecycle.jsonl';raw=b'\n'.join(json.dumps(v,separators=(',',':')).encode()for v in values)+(b'\n'if newline else b'')
        with path.open('wb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        st=path.stat();row['lifecycle_identity']=dict(device=st.st_dev,inode=st.st_ino,mode=oct(stat.S_IMODE(st.st_mode)),uid=st.st_uid,nlink=st.st_nlink)
    def row(self,r,receipt):
        summary=dict(sequence=receipt['sequence'],exchange_count=receipt['sequence'],accepted=receipt['sequence'],rejected=0,last_accepted_ordinal=12,original_payload_bytes=100,chain_sha256='e'*64,checkpoint_count=2,postprefix_raw_reconstructable=False)
        ledger=types.SimpleNamespace(subject={k:receipt[k]for k in('slot','session','connection')},sequence=receipt['sequence'],closed=True,stop_receipt=json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False).encode(),summary=lambda:copy.deepcopy(summary))
        proxy=types.SimpleNamespace(subject=copy.deepcopy(ledger.subject),sequence=receipt['sequence'],peer_eof=Event(True),stop_sent=Event(True),stop_receipt=copy.deepcopy(receipt),final_ledger=copy.deepcopy(summary),ledger=ledger,error=None,completed_retirement_authorized=Event(),completed_retirement_parked=Event(True))
        proxy.prefix_summary=dict(events=2402,footer=dict(first_play_sequence=120,initialized_sequence=110,latched_sequence=111));proxy.issuer=types.SimpleNamespace(nonce=receipt['nonce'])
        proxy.last_response=self.codec.encode_response(receipt['sequence'],struct.pack('>bbBBBB',0,0,0,0,1,0x85),nonce=receipt['nonce'],latched=True,stop=True)
        worker=types.SimpleNamespace(is_alive=lambda:True);temporary=tempfile.TemporaryDirectory(prefix='synthetic-child-lifecycle-',dir=ARGS.report.parent);self.addCleanup(temporary.cleanup)
        row=dict(child=types.SimpleNamespace(poll=lambda:0),proxy=proxy,worker=worker,private=Path(temporary.name));self.write_lifecycle(row,self.lifecycle_rows(proxy));return row
    def recent_pending(self,r,c,skip=4096):
        c.now=r._deadline-10
        for slot in self.r['SLOTS']:
            if slot!=skip:r.observe(slot,sample(slot,c.now,sequence=1202,before=10,score=300))
    def seal(self,r,c):
        c.now=r._deadline+10
        return r.seal(c.now,barrier=dict(deadline_monotonic_ns=r._deadline,no_new_origin_entries=True,inflight=0,closed_monotonic_ns=r._deadline+5))
    def test_01_completed_child_positive_retirement_exempts_only_activity(self):
        r,c,_=self.completed();self.recent_pending(r,c);r.positively_retired_slots.add(4096);r._fresh(r._deadline)
        self.assertEqual(r._scores[4096]['score'],200)
    def test_02_unfinished_and_unproved_completed_stay_freshness_guarded(self):
        for complete in(False,True):
            r,c,_=self.completed()if complete else self.ready();self.recent_pending(r,c)
            if not complete:r.positively_retired_slots.add(4096)
            with self.assertRaisesRegex(ValueError,'Stale'):r._fresh(r._deadline)
    def test_03_completed_score_and_terminal_are_never_amended(self):
        for mutation in('score','result'):
            r,c,_=self.completed();before=copy.deepcopy(r._scores[4096]);packet=terminal(4096,c.now+1);packet.update(sequence=1204,before_ordinal=12,accepted_ordinal=13)
            if mutation=='score':packet['selected']['score']=201
            else:packet['selected']['result']['score']=201
            c.now+=1
            with self.assertRaises(ValueError):r.observe(4096,packet)
            self.assertEqual(r._scores[4096],before)
        r,c,_=self.completed();before=copy.deepcopy(r._scores);c.now=r._deadline+1;self.assertFalse(r.observe(4096,terminal(4096,c.now)));self.assertEqual(r._scores,before)
    def test_04_wrong_first_game_and_identity_rejected(self):
        for key,value in(('game_uid',999),('journal_game_id','foreign'),('first_play_level',2),('measurement_generation',2)):
            r,c,_=self.ready();packet=sample(4096,c.now+1,sequence=1202,before=10,score=200);packet['selected'][key]=value;c.now+=1
            with self.assertRaises(ValueError):r.observe(4096,packet)
        r,c,_=self.ready();bad=member(4096);bad['session']='f'*32
        with self.assertRaises(ValueError):r.bind(4096,bad)
    def test_05_exact_slot_STOP_is_consumed_once(self):
        r,c,_=self.completed();reg,view,subject=self.register(r);receipt=view.authorize_slot(view.permit,**subject)
        self.assertTrue(receipt['consumed_before_send']);self.assertEqual(set(reg.consumed),{4096})
        with self.assertRaises(ValueError):view.authorize_slot(view.permit,**subject)
        self.assertEqual(reg.closed,set());self.assertEqual(r.positively_retired_slots,set())
    def test_06_wrong_STOP_identity_or_unfinished_game_has_no_authority(self):
        for key,value in(('slot',4097),('session','f'*32),('connection','f'*32),('nonce','f'*64),('sequence',1200)):
            r,c,_=self.completed();reg,view,subject=self.register(r);subject[key]=value
            with self.assertRaises(ValueError):view.authorize_slot(view.permit,**subject)
            self.assertEqual(reg.consumed,{})
        for key,value in(('certificate_identifier','f'*64),('nonce','f'*64)):
            r,c,_=self.completed();reg,view,subject=self.register(r);reg.registered[4096][key]=value
            if key=='nonce':subject['nonce']=value
            with self.assertRaises(ValueError):view.authorize_slot(view.permit,**subject)
            self.assertEqual(reg.consumed,{})
        for r,c,_ in(self.ready(),self.completed(arm=False)):
            reg,view,subject=self.register(r);self.assertIsNone(view.permit)
            with self.assertRaises(ValueError):view.authorize_slot({},**subject)
    def test_07_no_positive_child_retirement_without_normal0_EOF_matching_ledger(self):
        for fault in('running','nonzero','bool_exit','EOF','STOP_event','parked','receipt','ledger','ledger_closed','ledger_STOP','ledger_sequence','ledger_subject','score_amendment','Lua_STOP','Lua_subject','Lua_partial','proxy_error','worker_dead'):
            r,c,_=self.completed();reg,view,subject=self.register(r);receipt=view.authorize_slot(view.permit,**subject);row=self.row(r,receipt);p=row['proxy']
            if fault=='running':row['child'].poll=lambda:None
            elif fault=='nonzero':row['child'].poll=lambda:1
            elif fault=='bool_exit':row['child'].poll=lambda:False
            elif fault=='EOF':p.peer_eof=Event(False)
            elif fault=='STOP_event':p.stop_sent=Event(False)
            elif fault=='parked':p.completed_retirement_parked=Event(False)
            elif fault=='receipt':p.stop_receipt={}
            elif fault=='ledger':p.final_ledger={}
            elif fault=='ledger_closed':p.ledger.closed=False
            elif fault=='ledger_STOP':p.ledger.stop_receipt=b'{}'
            elif fault=='ledger_sequence':p.ledger.sequence+=1
            elif fault=='ledger_subject':p.ledger.subject={}
            elif fault=='score_amendment':r._scores[4096]['score']=201
            elif fault.startswith('Lua_'):
                values=self.lifecycle_rows(p)
                if fault=='Lua_STOP':values[3]['apply_ok']=False
                elif fault=='Lua_subject':values[3]['slot']=4097
                self.write_lifecycle(row,values,newline=fault!='Lua_partial')
            elif fault=='proxy_error':p.error='unexpected source error'
            else:row['worker'].is_alive=lambda:False
            with self.assertRaises(ValueError):reg.close_slot(4096,row)
            self.assertEqual(reg.closed,set());self.assertEqual(r.positively_retired_slots,set())
    def test_08_mixed_completed_retired_and_unfinished_cutoff_is_valid(self):
        r,c,_=self.completed();reg,view,subject=self.register(r);receipt=view.authorize_slot(view.permit,**subject);row=self.row(r,receipt)
        self.assertTrue(reg.close_slot(4096,row));self.assertTrue(row['worker'].is_alive());self.recent_pending(r,c)
        result=self.seal(r,c);self.assertEqual((result['n_scored'],result['n_completed'],result['n_censored']),(32,1,31))
        self.assertEqual(result['rows'][0]['score_at_deadline'],200);self.assertEqual(result['score_sum'],200+31*300)
        self.assertFalse(result['full_game_quality_qualified']);self.assertFalse(result['improvement_qualified'])
    def test_09_unknown_or_missing_members_and_inflight_barrier_rejected(self):
        r,c,_=self.ready();r._members.pop(4096)
        with self.assertRaises(ValueError):r._fresh(c.now)
        r,c,_=self.ready();r._scores.pop(4096)
        with self.assertRaises(ValueError):r._fresh(c.now)
        r,c,_=self.completed();self.recent_pending(r,c);r.positively_retired_slots.add(4096);c.now=r._deadline+10
        with self.assertRaises(ValueError):r.seal(c.now,barrier=dict(deadline_monotonic_ns=r._deadline,no_new_origin_entries=True,inflight=1,closed_monotonic_ns=r._deadline+5))
    def test_10_original32_admission_and_frozen_lifecycle_guards(self):
        entry=self.lifecycle;tree=ast.parse(checked(entry));cl=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='DeadlineMeasurementLifecycle');guard=next(n for n in cl.body if isinstance(n,ast.FunctionDef)and n.name=='guard')
        scope=dict(copy=copy,SLOTS=list(self.r['SLOTS']));scope['require']=self.r['require'];exec(compile(ast.fix_missing_locations(ast.Module(body=[guard],type_ignores=[])),entry['path']+'::guard','exec'),scope)
        _,_,boundary=self.ready();origin=types.SimpleNamespace(_owns_mode=True,_clocks={'step':1},_clock_values=lambda:{'step':1},_replay_guard={'adds':0},_replay_values=lambda:{'adds':0})
        obj=types.SimpleNamespace(phase='active',origin=origin,generation=1,boundary_status=lambda generation:copy.deepcopy(boundary));self.assertEqual(scope['guard'](obj)['clients'],32)
        pristine=copy.deepcopy(boundary)
        for fault in('missing','clock','replay'):
            boundary.clear();boundary.update(copy.deepcopy(pristine));origin._clock_values=lambda:{'step':1};origin._replay_values=lambda:{'adds':0}
            self.assertEqual(scope['guard'](obj)['clients'],32)
            if fault=='missing':boundary['actor_slots']=boundary['actor_slots'][1:];boundary.update(clients=31,expected=31,acknowledged=31)
            elif fault=='clock':origin._clock_values=lambda:{'step':2}
            else:origin._clock_values=lambda:{'step':1};origin._replay_values=lambda:{'adds':1}
            with self.assertRaises(ValueError):scope['guard'](obj)

    def test_11_actual_proxy_EOF_parks_until_owner_grant_AND_common_shutdown(self):
        entry=self.pins['clock_proxy'];tree=ast.parse(checked(entry));cl=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='StartupProxy');serve=next(n for n in cl.body if isinstance(n,ast.FunctionDef)and n.name=='serve')
        for fault in(None,'partial_EOF','owner_grant','global_shutdown'):
            with self.subTest(fault=fault):
                subject={k:member(4096)[k]for k in('slot','session','connection')};encoded=json.dumps(subject).encode();calls=[]
                class Sock:
                    def __init__(self):self.buffer=struct.pack('>H',(1<<14)|(4096<<1))+encoded
                    def settimeout(self,v):pass
                    def setsockopt(self,*v):pass
                    def sendall(self,v):pass
                    def recv(self,n):return b'x'if fault=='partial_EOF'else b''
                    def take(self,n):out,self.buffer=self.buffer[:n],self.buffer[n:];return out
                proxy=types.SimpleNamespace(subject=subject,stop_sent=Event(),stop_receipt=dict(screen_first_game_complete=True,sequence=1204),peer_eof=Event(),completed_retirement_parked=Event(),server=types.SimpleNamespace(shutdown_event=Event()),sequence=1204,error=None,request_budget=None,last_clock_error=None)
                def grant(seconds):
                    calls.append('owner');self.assertTrue(proxy.peer_eof.is_set());self.assertTrue(proxy.completed_retirement_parked.is_set());return fault!='owner_grant'
                def common(seconds):
                    calls.append('common');self.assertEqual(seconds,4200);self.assertTrue(proxy.peer_eof.is_set())
                    if fault!='global_shutdown':proxy.server.shutdown_event.set()
                    return True
                proxy.completed_retirement_authorized=Event(wait=grant);proxy.stop_event=Event(wait=common)
                proxy.trace=types.SimpleNamespace(loaded_rom=lambda:None,verify_closed_unchanged=lambda:None,closed_pin={'synthetic':True})
                proxy.ledger=types.SimpleNamespace(finalize=lambda receipt:dict(sequence=receipt['sequence'],synthetic=True))
                proxy.find_client=lambda:None;proxy._arm_request_budget=lambda:None;proxy._recv=lambda peer,n:struct.pack('>I',4)
                proxy.process=lambda peer,origin,raw:proxy.stop_sent.set();proxy.emit=lambda event:None
                codec=types.SimpleNamespace(HANDSHAKE=types.SimpleNamespace(size=len(encoded)),REQUEST=types.SimpleNamespace(size=4),MAX_PAYLOAD=0,MAX_META=0,decode_handshake=lambda raw:json.loads(raw))
                scope=dict(require=self.r['require'],copy=copy,struct=struct,socket=types.SimpleNamespace(IPPROTO_TCP=1,TCP_NODELAY=1),recv_exact=lambda sock,n:sock.take(n),codec=codec)
                exec(compile(ast.fix_missing_locations(ast.Module(body=[serve],type_ignores=[])),entry['path']+'::serve-only','exec'),scope)
                if fault is None:
                    self.assertIsNone(scope['serve'](proxy,Sock(),Sock()));self.assertEqual(calls,['owner','common']);self.assertTrue(proxy.server.shutdown_event.is_set())
                else:
                    with self.assertRaises(ValueError):scope['serve'](proxy,Sock(),Sock())
                    self.assertIsNotNone(proxy.error)
                    if fault=='owner_grant':self.assertEqual(calls,['owner'])

    def test_12_unwrapped_completed_AND_pending_scores_preserve_100M_carries(self):
        modulus=self.r['SCORE_MODULUS'];self.assertEqual(modulus,100_000_000);score=2*modulus+5_000_000
        r,c,_=self.completed(score=score);reg,view,subject=self.register(r);receipt=view.authorize_slot(view.permit,**subject);self.assertTrue(reg.close_slot(4096,self.row(r,receipt)))
        c.now=r._deadline-10
        for slot in self.r['SLOTS']:
            if slot!=4096:r.observe(slot,sample(slot,c.now,sequence=1202,before=10,score=score))
        result=self.seal(r,c);self.assertEqual((result['n_completed'],result['n_censored']),(1,31))
        self.assertEqual(result['score_sum'],32*205_000_000);self.assertEqual(result['mean_score'],205_000_000);self.assertEqual(result['median_score'],205_000_000)
        self.assertTrue(all(row['score_at_deadline']==205_000_000 and row['score_witness']['effective_raw_score']==5_000_000 and row['score_witness']['score_offset']==2*modulus for row in result['rows']))


def main():
    global ARGS
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--sources',type=Path);p.add_argument('--sources-sha256');p.add_argument('--report',type=Path);ARGS=p.parse_args()
    if not ARGS.execute:print('SOURCE_ONLY_INERT');return 0
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    value=dict(schema='robotron-completed-firstgame-cutoff-synthetic-CPU-contracts-v1',status='PASS'if result.wasSuccessful()else'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),source_manifest=dict(path=str(ARGS.sources),sha256=ARGS.sources_sha256),function_AST=getattr(Contracts,'source_AST',{}),scope='Actual recorder/retirement/lifecycle/proxy-EOF definitions with synthetic children/events/ledger/sockets; no proxy frame processing or inference. No gameplay/model/inference/full-tail or positive runtime closure credit.',runtime_module_import_or_proc_API_network_model_array_action=False,selected_pure_wire_codec_import=True)
    with ARGS.report.open('x')as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return 0 if result.wasSuccessful()and not result.skipped else 1


if __name__=='__main__':raise SystemExit(main())
