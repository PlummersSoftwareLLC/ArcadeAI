"""CPU Lua production-component traces and strict independent content-join contracts."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name,HERE/filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def rows(raw):
    return [json.loads(line) for line in raw.splitlines()]


def encoded(values):
    return ''.join(json.dumps(row,separators=(',',':'))+'\n' for row in values).encode()


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker=module('_tap_join_contract_checker','reconcile_acceptance_tap_v1.py')
        cls.trace=module('_tap_join_server_fixture','startup_server_prefix_v1.py')
        cls.fixture=module('_tap_join_actual_Lua_fixture','test_startup_acceptance_tap_v1.py')
        cls.fixture.Tests.setUpClass()
        cls.lua=cls.fixture.Tests.lua
        cls.rom3=cls.fixture.ROM3.read_bytes()
        cls.rom10=cls.fixture.ROM10.read_bytes()
        cls.session={4096:'a'*32}
        cls.baseline=cls.make_fixture(cls.session,4,16)

    @classmethod
    def make_fixture(cls,sessions,n,limit):
        lua_prefixes,taps={},{}
        payload=cls.trace.HEADER.pack(11128,0.,0.,0,0,0,0,1,20000,2,1,3)+b'\0'*(11128*4+4)
        action=struct.pack('bbBBBB',4,6,4,0,1,0x85)
        neutral=struct.pack('bbBBBB',-1,-1,0,0,1,0x85)
        for slot,session in sessions.items():
            script=cls.fixture.Tests.prelude+'''
            local Raw=assert(loadfile('''+json.dumps(str(HERE/'startup_prefix_v1.lua'))+'''))()
            local f=fixture('''+str(slot)+','+json.dumps(session)+''')
            local rawlines={}
            local r=Raw.new({slot='''+str(slot)+',session='+json.dumps(session)+',limit='+str(limit)+''',
                write=function(line)rawlines[#rawlines+1]=line;return true end})
            assert(f.r:install())
            -- Unknown input is explicitly retained before the first applied pulse.
            f:write(129);r:connected()
            local payload=string.pack(">I2ddBI4BBBI4BBB",11128,0.0,0.0,0,0,0,0,1,20000,2,1,3)
                ..string.rep("\\0",11128*4)..string.pack(">I4",0)
            for i=0,'''+str(n-1)+''' do
                local action=i==0 and string.pack("bbBBBB",-1,-1,0,0,1,0x85)
                    or string.pack("bbBBBB",4,6,4,0,1,0x85)
                r:begin(i,f.space);r:exchange(payload);r:response(action)
                r:finish(i==0 and -1 or 4,i==0 and -1 or 6,1,1,true,true)
                assert(f.r:input(i,1,i+1,1,1,true,true))
                if i==0 then f:write(127) end
                if i==1 then f.cpu.state.PC.value=0x27a7;f.cpu.state.CURPC.value=0x27a5;f:write(127) end
            end
            r:close("test");assert(f.r:close("machine_stop"))
            return table.concat(rawlines).."<SPLIT>"..output(f)
            '''
            left,right=cls.lua.run(script).split('<SPLIT>')
            lua_prefixes[slot]=left.encode();taps[slot]=right.encode()
        lines=[]
        capture=cls.trace.Recorder(sessions,lambda line:lines.append(line) is None,limit=limit)
        server=types.SimpleNamespace(replay_enabled=False,async_buffer=None,
                                     agent=types.SimpleNamespace(training_enabled=False))
        sock=types.SimpleNamespace(sendall=lambda value:None)
        with cls.trace.capture(capture,server):
            for cid,(slot,session) in enumerate(sessions.items()):
                cls.trace.notify(server,'connect',cid,slot)
                for i in range(n):
                    cls.trace.notify(server,'received',cid,payload)
                    if i:
                        cls.trace.notify(server,'accepted',cid,i)
                    cls.trace.send(server,sock,cid,neutral if i==0 else action)
                cls.trace.notify(server,'disconnect',cid)
        return dict(lua_prefixes=lua_prefixes,server_prefix=''.join(lines).encode(),tap_prefixes=taps,
            actor_consoles={slot:b'original actor CPU fixture console\n' for slot in sessions},
            sessions=dict(sessions),rom3=cls.rom3,rom10=cls.rom10,limit=limit)

    def altered(self,change):
        data=copy.deepcopy(self.baseline)
        values=rows(data['tap_prefixes'][4096]);change(values)
        data['tap_prefixes'][4096]=encoded(values)
        return data

    def join(self,data=None):
        return self.checker.reconcile(**(self.baseline if data is None else data))

    def reject(self,data):
        with self.assertRaises(ValueError):
            self.join(data)

    def test_actual_Lua_components_join_START1_and_common_restart_separately_without_certification(self):
        result=self.join();slot=result['slots']['4096']
        self.assertEqual(result['matched_inputs'],4)
        self.assertEqual(slot['status_writes'],3)
        self.assertEqual(slot['writes_before_first_input'],1)
        self.assertEqual(slot['common_restart_write_observations'],1)
        self.assertEqual(len(slot['START1_write_observations']),1)
        event=slot['START1_write_observations'][0]
        self.assertEqual((event['applied_input_frame'],event['exchange']),(0,1))
        self.assertEqual(event['following_raw_frame']['frame'],1)
        self.assertFalse(event['real_ROM_start_acceptance_proven'])
        self.assertFalse(slot['first_start_certified'])

    def test_received_and_accepted_ordinals_remain_distinct(self):
        result=self.join()['raw_prefix_reconciliation']
        self.assertEqual((result['matched_frames'],result['accepted_frames'],result['rejected_frames']),(4,3,1))
        data=copy.deepcopy(self.baseline);values=rows(data['server_prefix'])
        values[3]['accepted_ordinal']=values[3]['exchange']
        data['server_prefix']=encoded(values);self.reject(data)

    def test_missing_or_extra_slot_in_any_inventory_rejected(self):
        for name in ['lua_prefixes','tap_prefixes','actor_consoles']:
            for extra in [False,True]:
                data=copy.deepcopy(self.baseline)
                if extra:data[name][4097]=next(iter(data[name].values()))
                else:data[name].pop(4096)
                self.reject(data)

    def test_distinct_bound_private_sessions_and_slot_types_required(self):
        for sessions in [{4095:'a'*32},{4096:'bad'},{4096:'a'*32,4097:'a'*32},{True:'a'*32}]:
            data=copy.deepcopy(self.baseline);data['sessions']=sessions;self.reject(data)

    def test_console_close_failure_marker_cannot_be_overruled_by_valid_footer(self):
        data=copy.deepcopy(self.baseline)
        data['actor_consoles'][4096]+=b'ROBOTRON_STARTUP_ACCEPTANCE_TAP_FAILURE:stream_close_error\n'
        self.reject(data)
        data['actor_consoles'][4096]=None;self.reject(data)

    def test_console_bound_and_incomplete_binary_capture_rejected(self):
        data=copy.deepcopy(self.baseline);data['actor_consoles'][4096]=b'x'*(16*1024*1024+1);self.reject(data)
        for raw in [b'',self.baseline['tap_prefixes'][4096][:-1],b'\xff\n']:
            data=copy.deepcopy(self.baseline);data['tap_prefixes'][4096]=raw;self.reject(data)

    def test_duplicate_JSON_keys_nonfinite_unknown_fields_and_event_types_rejected(self):
        raw=self.baseline['tap_prefixes'][4096]
        for replacement in [b'{"kind":"header",',b'{"sequence":NaN,',b'{"sequence":Infinity,']:
            data=copy.deepcopy(self.baseline);data['tap_prefixes'][4096]=raw.replace(b'{',replacement,1);self.reject(data)
        for change in [lambda x:x[0].update(extra=1),lambda x:x[0].update(kind='unknown'),
                       lambda x:x[0].update(kind=[]),lambda x:x[0].pop('cpu_tag')]:
            self.reject(self.altered(change))

    def test_line_and_total_event_caps_rejected_before_semantic_join(self):
        for raw in [b'{' + b' '*2048+b'}\n',b'{}\n'*4621]:
            data=copy.deepcopy(self.baseline);data['tap_prefixes'][4096]=raw;self.reject(data)

    def test_sequence_slot_session_schema_and_integer_bool_substitutions_rejected(self):
        for change in [lambda x:x[0].update(sequence=True),lambda x:x[2].update(sequence=1),
                       lambda x:x[1].update(slot=4097),lambda x:x[1].update(session='b'*32),
                       lambda x:x[1].update(schema='different'),lambda x:x[-1].update(failed=0),
                       lambda x:x[0].update(initial_pc=1.0)]:
            self.reject(self.altered(change))

    def test_missing_repeated_or_late_installation_and_footer_rejected(self):
        for change in [lambda x:x.pop(1),lambda x:x.insert(2,dict(x[1])),lambda x:x.pop(),
                       lambda x:x.reverse()]:
            self.reject(self.altered(change))

    def test_declared_CPU_bank_region_size_and_span_metadata_rejected_if_wrong(self):
        for key,value in [('cpu_tag',':other'),('bank_tag',':wrong'),('region_tag',':wrong'),
                          ('region_size',0x18000),('region_bytewidth',2),('region_bitwidth',16),
                          ('span_region_offset',0x26c0),('span_bytes',244),('status_address',0x9858),
                          ('input_limit',4095),('write_limit',513)]:
            self.reject(self.altered(lambda x,k=key,v=value:x[0].update({k:v})))

    def test_entire_loaded245_span_checked_including_bytes_outside_critical_signatures(self):
        def change(values):
            data=bytearray.fromhex(values[0]['ROM_span_hex']);data[150]^=1
            values[0]['ROM_span_hex']=data.hex()
        self.reject(self.altered(change))

    def test_loaded_initialization_vector_and_ROM_chip_identity_checked(self):
        for key,value in [('OS_vector_hex','00d106'),('initialization_hex','00'*15)]:
            self.reject(self.altered(lambda x,k=key,v=value:x[0].update({k:v})))
        for name in ['rom3','rom10']:
            data=copy.deepcopy(self.baseline);raw=bytearray(data[name]);raw[-1]^=1;data[name]=bytes(raw);self.reject(data)

    def test_mapped_instruction_bytes_checked_against_immutable_ROM(self):
        self.reject(self.altered(lambda x:x[4].update(instruction_hex='0000')))

    def test_every_input_frame_epoch_exchange_start_coin_and_apply_flags_join_raw(self):
        for key,value in [('frame',1),('epoch',0),('exchange',2),('start',0),('coin',0),
                          ('apply_ok',False),('socket_ok',False),('inputs_observed',2)]:
            self.reject(self.altered(lambda x,k=key,v=value:x[3].update({k:v})))

    def test_write_context_cannot_borrow_another_input_or_skip_unknown_initial_context(self):
        for index,key,value in [(2,'last_input_frame',0),(2,'last_start',1),(2,'epoch',1),
                                (4,'last_input_frame',1),(4,'exchange',2),(4,'last_apply_ok',False),
                                (4,'last_socket_ok',False),(4,'inputs_observed',2),(4,'last_coin',0)]:
            self.reject(self.altered(lambda x,i=index,k=key,v=value:x[i].update({k:v})))

    def test_reordered_events_with_renumbered_sequences_still_fail_context_join(self):
        def change(values):
            values[4],values[5]=values[5],values[4]
            for n,row in enumerate(values,1):row['sequence']=n
        self.reject(self.altered(change))

    def test_write_address_mask_ordinal_and_byte_ranges_strict(self):
        for key,value in [('address',0x9858),('mask',0),('write_ordinal',8),('data',256),
                          ('previous_status',-1),('pc',65536),('bank_entry',2),('score_hex','xyz')]:
            self.reject(self.altered(lambda x,k=key,v=value:x[4].update({k:v})))

    def test_fault_or_failed_footer_and_count_cap_mismatch_rejected(self):
        for key,value in [('faults',1),('failed',True),('logging_failed',True),('inputs_observed',3),
                          ('writes_observed',2),('last_input_frame',2),('capacity_reached',True),('reason','capacity'),
                          ('reason','test')]:
            self.reject(self.altered(lambda x,k=key,v=value:x[-1].update({k:v})))
        self.reject(self.altered(lambda x:x[4].update(kind='fault')))

    def test_header_and_footer_cannot_claim_acceptance_or_full_ROM_certification(self):
        for index,key in [(0,'full_ROM_image_verified'),(0,'start_eligibility_changed'),
                          (-1,'real_ROM_start_acceptance_proven'),(-1,'start_eligibility_changed')]:
            self.reject(self.altered(lambda x,i=index,k=key:x[i].update({k:True})))

    def test_bank_DP_PC_A_old_STATUS_and_site_conditions_do_not_certify_other_writes(self):
        for key,value in [('bank_entry',0),('dp',0),('pc',0x2754),('a',0),('previous_status',127)]:
            data=self.altered(lambda x,k=key,v=value:x[4].update({k:v}))
            result=self.join(data)
            self.assertEqual(result['slots']['4096']['START1_write_observations'],[])
            self.assertFalse(result['raw_ROM_start_acceptance_proven'])

    def test_partial_prefix_can_match_content_without_full_capture_or_runtime_approval(self):
        result=self.join();self.assertEqual(result['matched_inputs'],4)
        for key in ['original_runtime_outcome_verified','raw_ROM_start_acceptance_proven',
                    'start_eligibility_changed','protocol_selected','quality_qualified','learning_speed_gain_verified']:
            self.assertIs(result[key],False)
        self.assertFalse(result['slots']['4096']['full_loaded_ROM_image_verified'])
        self.assertEqual(result['input_sha256']['tap']['4096'],hashlib.sha256(self.baseline['tap_prefixes'][4096]).hexdigest())

    def test_modified_raw_Lua_server_response_or_accepted_stamp_cannot_use_tap_to_rescue(self):
        for name in ['lua_prefixes','server_prefix']:
            data=copy.deepcopy(self.baseline)
            raw=data[name][4096] if name=='lua_prefixes' else data[name]
            values=rows(raw);target=next(x for x in values if x.get('kind')=='frame')
            if name=='lua_prefixes':target['response_hex']='000000'
            else:target['send_ok']=False
            if name=='lua_prefixes':data[name][4096]=encoded(values)
            else:data[name]=encoded(values)
            self.reject(data)

    def test_exact512_write_bound_matches_but513th_is_invalid(self):
        def many(total):
            data=copy.deepcopy(self.baseline);values=rows(data['tap_prefixes'][4096])
            footer=values.pop();template=dict(values[6])
            for ordinal in range(4,total+1):
                row=dict(template,write_ordinal=ordinal,inputs_observed=4,last_input_frame=3,exchange=4,
                         sequence=len(values)+1)
                values.append(row)
            footer.update(sequence=len(values)+1,writes_observed=total)
            values.append(footer);data['tap_prefixes'][4096]=encoded(values)
            return data
        self.assertEqual(self.join(many(512))['slots']['4096']['status_writes'],512)
        with self.assertRaisesRegex(ValueError,'capacity'):
            self.join(many(513))

    def test_full16_slots4096_inputs_join_actual_Lua_outputs_without_claiming_real_runtime(self):
        sessions={slot:format(slot,'032x') for slot in range(4096,4112)}
        data=self.make_fixture(sessions,4096,4096)
        result=self.join(data)
        self.assertEqual((result['actor_slots'],result['matched_inputs']),(16,65536))
        self.assertEqual(result['raw_prefix_reconciliation']['accepted_frames'],16*4095)
        self.assertTrue(all(s['inputs']==4096 and len(s['START1_write_observations'])==1 for s in result['slots'].values()))
        self.assertFalse(result['original_runtime_outcome_verified'])

    def test_raw_matcher_dependency_is_the_pinned_source_and_not_a_callers_claim(self):
        path=HERE/'startup_server_prefix_v1.py'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),self.checker.RAW_MATCHER_SHA)
        with mock.patch.object(self.checker.Path,'read_bytes',return_value=b'forged matcher'):
            with self.assertRaisesRegex(ValueError,'source differs'):
                self.join()

    def test_library_entry_does_not_read_inputs_or_discover_runtime(self):
        source=(HERE/'reconcile_acceptance_tap_v1.py').read_text()
        with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('read forbidden')), \
                mock.patch('builtins.print') as output:
            exec(compile(source,'<library-entry>','exec'),{'__name__':'__main__','__file__':str(HERE/'reconcile_acceptance_tap_v1.py')})
        self.assertIn('LIBRARY_ONLY',output.call_args.args[0])


if __name__ == '__main__':
    time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-passive-tap-strict-join-CPU-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Actual CPU Lua54 component traces, including16x4096 inputs and strict byte/session/context joins; no MAME, GPU, service or socket operations inside tests.',
        production_changed=False,protocol_selected=False,real_ROM_start_proven=False,learning_speed_gain_verified=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
