"""CPU contracts for exact handler bodies, bounded capture and Lua/server joins."""
import ast
from contextlib import redirect_stdout, redirect_stderr
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import socket
import struct
import sys
import threading
import time
import traceback
import types
import unittest

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]
sys.path.insert(0, str(HERE))
import startup_server_prefix_v2 as trace
import prepare_startup_server_v2 as builder

previous_path = HERE / 'test_startup_lua_v1.py'
if hashlib.sha256(previous_path.read_bytes()).hexdigest() != 'e07e3688afcbbd1c7e7c9ba0435341519066f7d6b8dd851f0742cc40f64557f2':
    raise ValueError('Exact prior CPU Lua fixture required')
spec = importlib.util.spec_from_file_location('_startup_server_CPU_Lua_fixture', previous_path)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
# Correct only this new fixture; the sealed historical fixture is preserved.
previous.PRELUDE = previous.PRELUDE.replace("11128", "1890")

SESSIONS = {4096: 'a' * 32}
PAYLOAD = trace.HEADER.pack(1890, 0., 0., 0, 0, 0, 0, 1, 20000, 2, 1, 3) + b'\0' * (1890 * 4 + 4)
ACTION = struct.pack('bbBBBB', 4, 6, 4, 0, 1, 0x85)
NEUTRAL = struct.pack('bbBBBB', -1, -1, 0, 0, 1, 0x85)


def private():
    return types.SimpleNamespace(replay_enabled=False, async_buffer=None,
                                 agent=types.SimpleNamespace(training_enabled=False))


def recorder(sessions=None, limit=16):
    lines=[]
    r=trace.Recorder(SESSIONS if sessions is None else sessions,
                     lambda line: lines.append(line) is None, limit=limit)
    return r, lines


def encoded(rows):
    return ''.join(json.dumps(x,separators=(',',':'))+'\n' for x in rows).encode()


def method_nodes(source):
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='SocketServer')
    return [n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('handle_client','_pack_action')]


def handler_run(source, mode, *, failed_send=False, failed_writer=False):
    metrics=types.SimpleNamespace(measurement_active=True,ratchet_frozen=False,override_expert=False,
        lock=threading.RLock(),increment_total_controls=lambda:None,add_inference_time=lambda x:None)
    frame=types.SimpleNamespace(state=[0.]*4,game_score=1_000_000 if mode=='crash' else 0,
        level_number=1,num_lasers=2,lives=3,player_alive=mode=='play',done=mode=='done',start_pressed=False,
        preview_pixels=None)
    scope=dict(struct=struct,socket=socket,time=time,traceback=traceback,sys=sys,random=random,
        threading=types.SimpleNamespace(Timer=lambda *a,**k:types.SimpleNamespace(start=lambda:None)),
        metrics=metrics,game_settings=types.SimpleNamespace(difficulty=5),RL_CONFIG=types.SimpleNamespace(client_stall_timeout_s=0),
        WIRE_PARAMS_COUNT=1890,CLIENT_IDLE_TIMEOUT_S=10,_MAX_FRAME_PAYLOAD_BYTES=2*1024*1024,
        _MAX_SCORE_JUMP=500_000,_last_implausible_warn_t=0.,_WAVE_PROBE=False,_DBG_ACTIONS=False,
        _SRC_NONE=0,_SRC_DQN=1,_SRC_EPSILON=2,_SRC_EXPERT=3,_SRC_EVAL=4,
        slice_model_state=lambda state:list(state),parse_frame_data=lambda *a,**k:None if mode=='parse' else frame,
        action_index_to_wire_dir=lambda n:n,_apply_fire_hold=lambda cs,fire:fire,_startup_prefix=trace)
    exec(compile(ast.Module(body=method_nodes(source),type_ignores=[]),'<CPU-exact-startup-handler>','exec'),scope)
    class Server:
        handle_client=scope['handle_client'];_pack_action=scope['_pack_action']
        def __init__(self):
            self.replay_enabled=False;self.async_buffer=None
            self.agent=types.SimpleNamespace(training_enabled=False,act=lambda *a,**k:(3,5,False))
            self.inference_batcher=None;self.game_boundary_diagnostics=False;self.running=True
            self.client_lock=threading.RLock();self._exception_log_lock=threading.Lock()
            self.shutdown_event=threading.Event();self._eval_override={};self._unwrap_stash={}
            self.client_states={0:dict(frames=0,last_time=time.time(),raw_score_prev=0,raw_wave_prev=1,
                                      last_state=None,last_action=None,eval_only=True)}
            self.clients={0:object()};self.game_journal=None;self._game_uid_seq=0
            self._rejected_gaps=types.SimpleNamespace(event=lambda *a,**k:None)
            self.errors=[];self.journal=[];self.batches=[]
            self.reads=iter([struct.pack('>H',0x4000+4096*2),struct.pack('>I',len(PAYLOAD)),PAYLOAD])
        def _recv_exact(self,*a,**k):return next(self.reads)
        def _parse_client_handshake(self,v):return False,4096,1
        def _ensure_preview_client_selected_locked(self):return None,False
        def _preview_enabled_for_client(self,cid):return False
        def _hud_enabled_for_client(self,cid):return False
        def _is_preview_client(self,cid):return False
        def _is_eval_client(self,cid):return True
        def _sync_measurement_boundary(self,*a):return True
        def _replay_writable(self,*a):return False
        def _stack_model_state(self,cs,state):return state
        def _journal_observe(self,cid,frame,cs,new_game,**k):self.journal.append(cs['frames'])
        def _account_frame_batch(self,*a):self.batches.append(a)
        def _sync_client_count_locked(self):pass
        def _fail_inference_only(self,message):self.errors.append(message)
        def _clear_preview_cache(self):pass
        def _cleanup(self):pass
        def _actor_controls(self,cs):return 0.,0.,'measurement'
    server=Server()
    class Sock:
        def __init__(self):self.sent=[]
        def setblocking(self,value):pass
        def setsockopt(self,*a):pass
        def shutdown(self,*a):pass
        def close(self):pass
        def sendall(self,payload):
            self.sent.append(payload);server.running=False;server.shutdown_event.set()
            if failed_send:raise OSError('injected send failure')
    sock=Sock();r,lines=recorder()
    if failed_writer:r.write=lambda x:(_ for _ in ()).throw(OSError('injected observer failure'))
    with trace.capture(r,server),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
        server.handle_client(sock,0)
    return dict(sent=sock.sent,errors=server.errors,journal=server.journal,batches=server.batches),r,lines


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=(GAME/'tools/quality_capacity_proposal/profile04/Robotron/Scripts/dqn/socket_server.py').read_text()
        cls.proposed=builder.build(cls.original)
        cls.lua=previous.Lua()

    def matched_fixture(self):
        lua=self.lua.run(previous.PRELUDE+'''
        values[0x9859]=129;r:connected()
        for i=0,3 do
            local action=i==0 and string.pack("bbBBBB",-1,-1,0,0,1,0x85) or response
            local move,fire=i==0 and -1 or 4,i==0 and -1 or 6
            r:begin(i,memory);r:exchange(payload);r:response(action);r:finish(move,fire,1,1,true,true)
        end
        r:close("test");return table.concat(lines)''').encode()
        server=private();r,lines=recorder();sock=types.SimpleNamespace(sendall=lambda x:None)
        with trace.capture(r,server):
            trace.notify(server,'connect',7,4096)
            for i in range(4):
                trace.notify(server,'received',7,PAYLOAD)
                if i:trace.notify(server,'accepted',7,i)
                trace.send(server,sock,7,NEUTRAL if i==0 else ACTION)
            trace.notify(server,'disconnect',7)
        return {4096:lua},''.join(lines).encode()

    def test_full_source_AST_preserved_and_all_five_send_paths_covered(self):
        self.assertEqual(builder.stripped_tree(self.proposed),ast.dump(ast.parse(self.original),include_attributes=False))
        self.assertEqual(self.proposed.count('_startup_prefix.send(self, sock, cid,'),5)
        compile(self.proposed,'<isolated-full-source>','exec')

    def test_exact_handlers_preserve_all_five_path_actions(self):
        for mode in ('parse','crash','done','inactive','play'):
            with self.subTest(mode=mode):
                before,_,_=handler_run(self.original,mode)
                after,r,lines=handler_run(self.proposed,mode)
                broken,_,_=handler_run(self.proposed,mode,failed_writer=True)
                self.assertEqual(before,after);self.assertEqual(before,broken)
                self.assertEqual(after['errors'],[]);self.assertEqual(len(after['sent']),1)
                rows=[json.loads(x) for x in lines];frames=[x for x in rows if x['kind']=='frame']
                self.assertEqual(len(frames),1)
                self.assertEqual(frames[0]['accepted'],mode not in ('parse','crash'))
                self.assertEqual(frames[0]['action_hex'],after['sent'][0].hex())
                self.assertTrue(frames[0]['send_ok']);self.assertEqual(r.faults,0)

    def test_exact_handlers_preserve_failed_send_behavior(self):
        for mode in ('parse','crash','done','inactive','play'):
            with self.subTest(mode=mode):
                before,_,_=handler_run(self.original,mode,failed_send=True)
                after,r,lines=handler_run(self.proposed,mode,failed_send=True)
                self.assertEqual(before,after)
                row=next(json.loads(x) for x in lines if json.loads(x)['kind']=='frame')
                self.assertFalse(row['send_ok']);self.assertGreater(r.faults,0)

    def test_actual_Lua_binary_header_and_server_reconcile_rejected_ordinals(self):
        lua,server=self.matched_fixture();result=trace.reconcile(lua,server,SESSIONS,limit=16)
        self.assertEqual((result['matched_frames'],result['accepted_frames'],result['rejected_frames']),(4,3,1))
        self.assertFalse(result['raw_ROM_start_acceptance_proven'] or result['protocol_selected'])

    def test_paired_action_wire_or_epoch_tampering_is_rejected(self):
        lua,server=self.matched_fixture();raw=[json.loads(x) for x in server.splitlines()]
        for key,value in (('action_hex','ff0604000185'),('wire_start',0),('exchange',9),('accepted_ordinal',8),('epoch',2)):
            with self.subTest(key=key):
                bad=copy.deepcopy(raw);row=next(x for x in bad if x['kind']=='frame');row[key]=value
                with self.assertRaises(ValueError):trace.reconcile(lua,encoded(bad),SESSIONS,limit=16)

    def test_missing_duplicate_and_reordered_frames_cannot_be_joined(self):
        lua,server=self.matched_fixture();rows=[json.loads(x) for x in server.splitlines()]
        indices=[i for i,x in enumerate(rows) if x['kind']=='frame'];i,j=indices[:2]
        variants=[rows[:i]+rows[i+1:],rows[:i]+[rows[i]]+rows[i:]]
        swapped=copy.deepcopy(rows);swapped[i],swapped[j]=swapped[j],swapped[i];variants.append(swapped)
        for bad in variants:
            with self.assertRaises(ValueError):trace.reconcile(lua,encoded(bad),SESSIONS,limit=16)

    def test_boolean_counter_impostors_and_session_substitution_fail(self):
        lua,server=self.matched_fixture();rows=[json.loads(x) for x in server.splitlines()]
        variants=[]
        for key,value in (('faults',False),('rows',True),('counts',{'4096':True})):
            bad=copy.deepcopy(rows);bad[-1][key]=value;variants.append(bad)
        bad=copy.deepcopy(rows);next(x for x in bad if x['kind']=='frame')['wire_start']=True;variants.append(bad)
        bad=copy.deepcopy(rows);next(x for x in bad if x['kind']=='connection')['session']='b'*32;variants.append(bad)
        for bad in variants:
            with self.assertRaises(ValueError):trace.reconcile(lua,encoded(bad),SESSIONS,limit=16)

    def test_partial_oversized_duplicate_key_and_nonfinite_json_fail(self):
        lua,server=self.matched_fixture()
        for bad in (server[:-1],server+b' '*(2048*100),server.replace(b'"faults":0',b'"faults":0,"faults":0'),
                    server.replace(b'"faults":0',b'"faults":NaN')):
            with self.assertRaises(ValueError):trace.reconcile(lua,bad,SESSIONS,limit=16)

    def test_raw_STATUS_or_input_mismatch_rejects_matched_prefix(self):
        lua,server=self.matched_fixture();rows=[json.loads(x) for x in lua[4096].splitlines()]
        for key,value in (('raw_status',128),('raw_reserves',9),('raw_wave',2),('start_input',0),('move',False)):
            bad=copy.deepcopy(rows);next(x for x in bad if x['kind']=='frame')[key]=value
            with self.assertRaises(ValueError):trace.reconcile({4096:encoded(bad)},server,SESSIONS,limit=16)

    def test_capture_is_bound_to_exact_private_server_instance(self):
        a,b=private(),private();r,lines=recorder()
        with trace.capture(r,a):
            trace.notify(b,'connect',0,4096);self.assertEqual(r.clients,{})
            trace.notify(a,'connect',0,4096);self.assertEqual(len(r.clients),1)
        for change in ('replay','buffer','training'):
            target=private()
            if change=='replay':target.replay_enabled=True
            elif change=='buffer':target.async_buffer=object()
            else:target.agent.training_enabled=True
            candidate,_=recorder()
            with self.assertRaises(ValueError):
                with trace.capture(candidate,target):pass

    def test_nested_capture_and_closed_recorder_are_refused(self):
        a=private();r,_=recorder();other,_=recorder()
        with trace.capture(r,a):
            with self.assertRaises(ValueError):
                with trace.capture(other,a):pass
        with self.assertRaises(ValueError):
            with trace.capture(r,a):pass

    def test_context_close_with_pending_work_records_incomplete_prefix(self):
        a=private();r,lines=recorder()
        with trace.capture(r,a):
            trace.notify(a,'connect',0,4096);trace.notify(a,'received',0,PAYLOAD)
        footer=json.loads(lines[-1]);self.assertEqual(footer['pending_frames'],1)
        self.assertGreater(footer['faults'],0)

    def test_bounded_capacity_stops_future_decode_and_write(self):
        a=private();r,lines=recorder();sock=types.SimpleNamespace(sendall=lambda x:None)
        with trace.capture(r,a):
            trace.notify(a,'connect',0,4096)
            for i in range(16):
                trace.notify(a,'received',0,PAYLOAD);trace.notify(a,'accepted',0,i+1);trace.send(a,sock,0,ACTION)
            n=len(lines)
            for i in range(1000):trace.notify(a,'received',0,b'bad');trace.send(a,sock,0,ACTION)
            self.assertEqual(len(lines),n)
        self.assertEqual(r.rows,16);self.assertEqual(r.faults,0)
        self.assertEqual(json.loads(lines[-1])['reason'],'capacity')

    def test_all32_concurrent_slots_retain_bounded_independent_ordinals(self):
        sessions={slot:format(slot,'032x') for slot in range(4096,4128)}
        a=private();r,lines=recorder(sessions);sock=types.SimpleNamespace(sendall=lambda data:None)
        def actor(slot):
            trace.notify(a,'connect',slot,slot)
            for i in range(16):
                trace.notify(a,'received',slot,PAYLOAD)
                trace.notify(a,'accepted',slot,i+1)
                trace.send(a,sock,slot,ACTION)
        with trace.capture(r,a):
            with ThreadPoolExecutor(max_workers=32) as pool:list(pool.map(actor,sessions))
        self.assertEqual((r.rows,r.faults),(512,0));self.assertLessEqual(len(r.clients),32)
        rows=[json.loads(x) for x in lines]
        self.assertEqual(json.loads(lines[-1])['counts'],{str(slot):16 for slot in sessions})
        for slot in sessions:
            frames=[x for x in rows if x['kind']=='frame' and x['slot']==slot]
            self.assertEqual([x['exchange'] for x in frames],list(range(1,17)))
            self.assertEqual([x['accepted_ordinal'] for x in frames],list(range(1,17)))
        self.assertLessEqual(max(len(x.encode()) for x in lines),2048)

    def test_connection_error_spam_has_bounded_events_and_memory(self):
        r,lines=recorder();a=private()
        with trace.capture(r,a):
            for cid in range(10000):trace.notify(a,'connect',cid,8191)
        self.assertLessEqual(len(lines),r.max_events);self.assertEqual(r.clients,{})
        self.assertTrue(r.closed and r.failed)

    def test_writer_fault_preserves_send_return_and_exception_identity(self):
        a=private();r,lines=recorder();sent=[];marker=object()
        sock=types.SimpleNamespace(sendall=lambda data:sent.append(data) or marker)
        with trace.capture(r,a):
            trace.notify(a,'connect',0,4096);trace.notify(a,'received',0,PAYLOAD)
            r.write=lambda line:(_ for _ in ()).throw(OSError('observer write failed'))
            self.assertIs(trace.send(a,sock,0,ACTION),marker)
            failure=ConnectionResetError('original socket error')
            broken=types.SimpleNamespace(sendall=lambda x:(_ for _ in ()).throw(failure))
            with self.assertRaises(ConnectionResetError) as caught:trace.send(a,broken,0,ACTION)
            self.assertIs(caught.exception,failure)
        self.assertEqual(sent,[ACTION]);self.assertTrue(r.failed)

    def test_disabled_capture_forwards_exact_payload_object(self):
        payload=bytes(ACTION);marker=object();seen=[]
        sock=types.SimpleNamespace(sendall=lambda data:seen.append(data) or marker)
        self.assertIs(trace.send(object(),sock,0,payload),marker);self.assertIs(seen[0],payload)

    def test_invalid_wire_shapes_and_accepted_gaps_are_observable_faults(self):
        for payload in (b'short',PAYLOAD[:-1],PAYLOAD+b'x'):
            a=private();r,_=recorder()
            with trace.capture(r,a):trace.notify(a,'connect',0,4096);trace.notify(a,'received',0,payload)
            self.assertGreater(r.faults,0)
        a=private();r,_=recorder()
        with trace.capture(r,a):
            trace.notify(a,'connect',0,4096);trace.notify(a,'received',0,PAYLOAD);trace.notify(a,'accepted',0,2)
        self.assertGreater(r.faults,0)

    def test_configuration_changes_and_reconnects_invalidate_join(self):
        a=private();r,lines=recorder()
        with trace.capture(r,a):
            trace.notify(a,'connect',0,4096);a.agent.training_enabled=True
            trace.notify(a,'received',0,PAYLOAD)
        self.assertGreater(r.faults,0)
        lua,server=self.matched_fixture();rows=[json.loads(x) for x in server.splitlines()]
        connection=copy.deepcopy(next(x for x in rows if x['kind']=='connection'));connection['epoch']=2
        rows.insert(-1,connection)
        with self.assertRaises(ValueError):trace.reconcile(lua,encoded(rows),SESSIONS,limit=16)

    def test_unknown_slots_missing_Lua_coverage_and_invalid_options_fail(self):
        lua,server=self.matched_fixture()
        with self.assertRaises(ValueError):trace.reconcile({},server,SESSIONS,limit=16)
        for sessions,limit in (({},16),({8192:'a'*32},16),(SESSIONS,15),(SESSIONS,16385),({4096:'bad'},16)):
            with self.assertRaises(ValueError):recorder(sessions,limit)
        rows=[json.loads(x) for x in server.splitlines()];rows.insert(-1,dict(rows[1],slot=4097))
        with self.assertRaises(ValueError):trace.reconcile(lua,encoded(rows),SESSIONS,limit=16)

    def test_wrong_source_and_reinstrumentation_are_refused(self):
        with self.assertRaises(ValueError):builder.build(self.original+'\n')
        with self.assertRaises(ValueError):builder.build(self.proposed)


    def test_actual_frozen_config_and_received_Lua_metadata_use1890_not_model_stack11128(self):
        config=GAME/'tools/quality_capacity_proposal/profile04/Robotron/Scripts/dqn/config.py'
        tree=ast.parse(config.read_text())
        count=next(n.value.value for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(a,ast.Name) and a.id=='WIRE_PARAMS_COUNT' for a in n.targets))
        self.assertEqual(count,1890)
        root=GAME/'logs/managed-learning-20261015/run-26/startup-diagnostic-v3-original01-20261020'
        observed=[]
        for slot in range(4096,4110):
            path=root/f'Lua-{slot}-prefix-readonly.jsonl'
            raw=path.read_bytes()
            rows=[json.loads(line) for line in raw.splitlines()]
            wired=[x for x in rows if x.get('kind')=='frame' and x.get('wire_observed') is True]
            self.assertTrue(wired)
            self.assertTrue(all(x['wire_n']==count and x['payload_bytes']==7597 for x in wired))
            observed.extend(wired)
        self.assertGreater(len(observed),0)
        self.assertEqual(trace.wire_fields(PAYLOAD)['wire_n'],count)
        self.assertEqual(len(PAYLOAD),7597)

    def test_original_parser_refuses_actual_shape_and_new_parser_refuses_stack_shape(self):
        path=HERE/'startup_server_prefix_v1.py'
        spec=importlib.util.spec_from_file_location('_preserved_wrong_wire_observer',path)
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        with self.assertRaisesRegex(ValueError,'fixed v2 wire shape'):old.wire_fields(PAYLOAD)
        wrong=trace.HEADER.pack(11128,0.,0.,0,0,0,0,1,20000,2,1,3)+b'\0'*(11128*4+4)
        with self.assertRaisesRegex(ValueError,'fixed v2 wire shape'):trace.wire_fields(wrong)
        a=private();r,lines=recorder()
        with trace.capture(r,a):
            trace.notify(a,'connect',0,4096);trace.notify(a,'received',0,wrong)
        self.assertGreater(r.faults,0)

    def test_matching_wrong_shape_on_both_sides_cannot_pass_join(self):
        lua,server=self.matched_fixture()
        left=[json.loads(x) for x in lua[4096].splitlines()]
        right=[json.loads(x) for x in server.splitlines()]
        for rows in (left,right):
            for row in rows:
                if row.get('kind')=='frame':
                    row['wire_n']=11128;row['payload_bytes']=trace.HEADER.size+11128*4+4
        with self.assertRaisesRegex(ValueError,'Matched wire shape differs'):
            trace.reconcile({4096:encoded(left)},encoded(right),SESSIONS,limit=16)

    def test_actual1890_payload_reaches_all_five_unchanged_handler_paths_without_fault(self):
        for mode in ('parse','crash','done','inactive','play'):
            with self.subTest(mode=mode):
                before,_,_=handler_run(self.original,mode)
                after,rec,lines=handler_run(self.proposed,mode)
                self.assertEqual(before,after);self.assertEqual(rec.faults,0)
                row=next(json.loads(x) for x in lines if json.loads(x)['kind']=='frame')
                self.assertEqual((row['wire_n'],row['payload_bytes']),(1890,7597))


if __name__=='__main__':
    time.sleep(2)  # Preserve a bracketable original CPU service birth.
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-startup-server-matched-prefix-CPU-contracts-v2',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Exact extracted socket handler/action-packer bodies; synthetic sockets, memory, agent and boundary shims; actual Lua5.4 header/capture execution. No real parser/model/ROM/MAME/banks.',
        production_changed=False,protocol_selected=False,real_ROM_start_proven=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
