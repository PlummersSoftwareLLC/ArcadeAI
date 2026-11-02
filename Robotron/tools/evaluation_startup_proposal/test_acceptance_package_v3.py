"""Original CPU contracts for passive hooks, actual Lua callbacks and exact126 packages."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE/filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


SCAFFOLD = r'''
local f=fixture()
local faults, lines, markers, opens = {}, {}, {}, {}
local closes, prior_closes, flushes = 0, 0, 0
local env={ROBOTRON_STARTUP_ACCEPTANCE_PATH="/private/session/tap.jsonl",
    ROBOTRON_STARTUP_DIAGNOSTIC_PATH="/private/session/raw.jsonl",
    ROBOTRON_STARTUP_DIAGNOSTIC_SESSION=string.rep("a",32)}
os.getenv=function(key)return env[key]end
print=function(line)markers[#markers+1]=line end
local stream={write=function(self,line)
    if faults.write=="throw" then error("write") end
    if faults.write=="false" then return nil,"write failure" end
    lines[#lines+1]=line;return self
end,flush=function()
    flushes=flushes+1
    if faults.flush=="throw" then error("flush") end
    return faults.flush~="false"
end,close=function()
    closes=closes+1
    if faults.close=="throw" then error("close") end
    if faults.close=="false" then return nil,"close failure" end
    return true
end}
io.open=function(path,mode)
    opens[#opens+1]={path,mode}
    if faults.open==mode then error("open") end
    if mode=="rb" then
        if faults.existing then return {close=function()prior_closes=prior_closes+1;return true end} end
        return nil,"absent"
    end
    assert(mode=="wb")
    if faults.open=="nil" then return nil,"open failure" end
    return stream
end
manager={machine={devices={[":maincpu"]=f.cpu},memory={banks={[":mainbank"]=f.bank},regions={[":maincpu"]=f.region}}}}
mem=f.space;CLIENT_SLOT=4096;frame_counter=0
local _startup_trace={session=string.rep("a",32),attempts=0,closed=false,epoch=1,exchange_ordinal=1}
'''


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tap_fixture = module('_integration_tap_fixture', 'test_startup_acceptance_tap_v1.py')
        cls.raw_fixture = module('_integration_raw_fixture', 'test_startup_lua_v1.py')
        cls.raw = module('_integration_raw_builder', 'prepare_startup_lua_v1.py')
        cls.builder = module('_integration_acceptance_builder', 'prepare_acceptance_lua_v1.py')
        cls.packager = module('_integration_packager', 'prepare_diagnostic_package_v2.py')
        cls.u = cls.packager.utilities()
        cls.lua = cls.raw_fixture.Lua()
        cls.tap_fixture.Tests.setUpClass()
        cls.prelude = cls.tap_fixture.Tests.prelude
        cls.original = cls.raw_fixture.ORIGINAL.read_text()
        cls.raw_source = cls.raw.build(cls.original, HERE/'startup_prefix_v1.lua', cls.raw_fixture.ORIGINAL_SHA)
        cls.combined = cls.builder.build(cls.raw_source, HERE/'startup_acceptance_tap_v1.lua',
                                        hashlib.sha256(cls.raw_source.encode()).hexdigest())
        cls.blocks = re.findall(re.escape(cls.builder.BEGIN)+r'(.*?)'+re.escape(cls.builder.END),
                                cls.combined, flags=re.S)
        if len(cls.blocks) != 4:
            raise ValueError('Four actual inserted blocks required')
        # Source order is declarations/input/close/bootstrap. Select each actual
        # block by its unique content, rather than assuming insertion order.
        cls.blocks = [next(block for block in cls.blocks if block.lstrip().startswith(token))
                      for token in ('local _acceptance_stream,', '_acceptance_bootstrap()\n',
                                    '_acceptance_note(start_cmd,', '_acceptance_close()\n')]

    def run_lua(self, body, before=''):
        return self.lua.run(self.prelude + SCAFFOLD + before + self.blocks[0] + body)

    def rows(self, body, before=''):
        return [json.loads(x) for x in self.run_lua(body, before).splitlines()]

    def test_full_combined_Lua_compiles_and_all_hooks_strip_to_exact_parent(self):
        self.lua.run(self.combined, compile_only=True)
        self.assertEqual(self.builder.stripped(self.combined), self.raw_source)
        self.assertEqual(self.raw.stripped(self.builder.stripped(self.combined)), self.original)

    def test_hook_order_and_lexical_scope_follow_actual_raw_local_and_controls(self):
        self.assertGreater(self.combined.index(self.builder.BEGIN + self.blocks[0] + self.builder.END), self.combined.index('local _startup_trace'))
        self.assertGreater(self.combined.index(self.builder.BEGIN + self.blocks[1] + self.builder.END), self.combined.index('controls = Controls:new(manager)'))
        self.assertLess(self.combined.index(self.builder.BEGIN + self.blocks[1] + self.builder.END), self.combined.index('\nopen_socket()\n'))
        finish=self.combined.index('    _startup_trace:finish(move_cmd, fire_cmd, start_cmd, coin_cmd, socket_ok, ok_apply)')
        self.assertGreater(self.combined.index(self.builder.BEGIN + self.blocks[2] + self.builder.END), finish)
        self.assertLess(self.combined.index(self.builder.BEGIN + self.blocks[2] + self.builder.END), self.combined.index('    if not ok_apply then',finish))

    def test_source_hash_missing_duplicate_hooks_and_unsafe_helper_path_rejected(self):
        for source,path,sha in (
            (self.raw_source,HERE/'startup_acceptance_tap_v1.lua','0'*64),
            (self.combined,HERE/'startup_acceptance_tap_v1.lua',hashlib.sha256(self.combined.encode()).hexdigest()),
            (self.raw_source.replace(self.raw.BEGIN,'',1),HERE/'startup_acceptance_tap_v1.lua',None),
            (self.raw_source,Path('/tmp/a"bad.lua'),None),
            (self.raw_source,Path('relative.lua'),None)):
            with self.assertRaises(ValueError):
                self.builder.build(source,path,sha or hashlib.sha256(source.encode()).hexdigest())

    def test_disabled_hook_has_no_discovery_module_load_or_output(self):
        out=self.run_lua('''_acceptance_bootstrap();_acceptance_note(1,1,true,true);_acceptance_close()
            assert(#opens==0 and #markers==0 and f.reads==0 and f.region_reads==0 and f.installs==0)
            return "OK"''','''env.ROBOTRON_STARTUP_ACCEPTANCE_PATH=nil
            manager=setmetatable({},{__index=function()error("resource discovery forbidden")end})
            loadfile=function()error("module loading forbidden")end
            ''')
        self.assertEqual(out,'OK')

    def test_actual_loaded_helper_records_same_session_input_and_all256_unmodified_writes(self):
        rows=self.rows('''_acceptance_bootstrap();_acceptance_note(1,0,true,true)
            for value=0,255 do f:write(value);assert(f.memory[0x9859]==value) end
            _acceptance_close();_acceptance_close()
            assert(#markers==0 and closes==1 and f.removes==1 and flushes==#lines)
            return table.concat(lines)''')
        self.assertEqual(rows[0]['session'],'a'*32)
        self.assertEqual([r['data'] for r in rows if r['kind']=='status_write'],list(range(256)))
        self.assertEqual(next(r for r in rows if r['kind']=='input')['frame'],0)
        self.assertFalse(rows[-1]['failed'])

    def test_bad_path_slot_session_and_raw_state_rejected_before_open(self):
        changes=['env.ROBOTRON_STARTUP_ACCEPTANCE_PATH="relative"',
                 'env.ROBOTRON_STARTUP_ACCEPTANCE_PATH="/private/../out"',
                 'env.ROBOTRON_STARTUP_ACCEPTANCE_PATH="/private/./out"',
                 'env.ROBOTRON_STARTUP_ACCEPTANCE_PATH=env.ROBOTRON_STARTUP_DIAGNOSTIC_PATH',
                 'CLIENT_SLOT=4095','CLIENT_SLOT=4128','env.ROBOTRON_STARTUP_DIAGNOSTIC_SESSION="bad"',
                 '_startup_trace.session=string.rep("b",32)', '_startup_trace.closed=true',
                 '_startup_trace.failed=true','_startup_trace.attempts=1']
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_close()
                    assert(#opens==0 and #markers==1 and f.installs==0);return "OK"''',change+'\n'),'OK')

    def test_existing_output_never_truncated_and_probe_handle_closed(self):
        self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_close()
            assert(#opens==1 and opens[1][2]=="rb" and prior_closes==1 and closes==0 and #markers==1)
            return "OK"''','faults.existing=true\n'),'OK')

    def test_failed_open_keeps_failure_marker_without_resource_discovery(self):
        for mode in ['rb','wb','nil']:
            self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_close()
                assert(#markers==1 and f.installs==0 and closes==0 and f.region_reads==0);return "OK"''',
                'faults.open='+json.dumps(mode)+'\n'),'OK')

    def test_stream_owned_before_helper_load_failure_and_closed_once(self):
        self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_close();_acceptance_close()
            assert(#opens==2 and closes==1 and #markers==1 and f.installs==0);return "OK"''',
            'loadfile=function()error("missing module")end\n'),'OK')

    def test_absent_MAME_API_preserves_invalid_output_and_closes_stream(self):
        self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_close()
            assert(closes==1 and #markers==1 and f.installs==0);return "OK"''',
            'manager.machine.memory.banks=nil\n'),'OK')

    def test_install_throw_is_invalid_and_stream_cleanup_runs(self):
        self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_close()
            assert(closes==1 and #markers==1 and f.removes==0);return "OK"''',
            'f.space.install_write_tap=function()error("install")end\n'),'OK')

    def test_repeated_and_late_bootstrap_cannot_install_or_open_again(self):
        self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_bootstrap();_acceptance_close()
            assert(#opens==2 and f.installs==1 and f.removes==1 and closes==1 and #markers==1);return "OK"'''),'OK')
        self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_close()
            assert(#opens==0 and f.installs==0 and #markers==1);return "OK"''','frame_counter=1\n'),'OK')
        self.assertEqual(self.run_lua('''_acceptance_close();_acceptance_bootstrap()
            assert(#opens==0 and f.installs==0 and #markers==1);return "OK"'''),'OK')

    def test_writer_and_flush_false_or_throw_never_escape_and_stream_still_closes(self):
        for field in ['write','flush']:
            for value in ['false','throw']:
                self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_note(1,0,true,true)
                    _acceptance_close();assert(#markers==1 and closes==1);return "OK"''',
                    'faults['+json.dumps(field)+']='+json.dumps(value)+'\n'),'OK')

    def test_callback_reader_error_retains_original_write_and_invalid_status(self):
        self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_note(1,0,true,true)
            f.cpu.state=nil;f:write(123);_acceptance_close()
            assert(f.memory[0x9859]==123 and #markers==1 and closes==1 and f.removes==1);return "OK"'''),'OK')

    def test_remove_error_and_stream_close_error_retained_without_retry(self):
        self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_close();_acceptance_close()
            assert(#markers==1 and closes==1 and f.removes==1);return "OK"''',
            '''f.space.install_write_tap=function(self,a,b,name,cb)
                f.installs=f.installs+1;f.callback=cb
                return {remove=function()f.removes=f.removes+1;error("remove")end}
            end
            '''),'OK')
        for kind in ['throw','false']:
            self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_close();_acceptance_close()
                assert(#markers==1 and closes==1 and f.removes==1);return "OK"''',
                'faults.close='+json.dumps(kind)+'\n'),'OK')

    def test_malformed_and_reconnected_context_invalidate_without_throwing(self):
        for change in ['_startup_trace.epoch=2','_startup_trace.exchange_ordinal=-1',
                       'frame_counter=1','_startup_trace.epoch=0']:
            self.assertEqual(self.run_lua('''_acceptance_bootstrap();'''+change+'''
                _acceptance_note(1,0,true,true);_acceptance_close()
                assert(#markers==1 and closes==1 and f.removes==1);return "OK"'''),'OK')

    def test_full4096_prefix_closes_tap_then_later_frames_are_inert(self):
        rows=self.rows('''_acceptance_bootstrap()
            for i=0,4095 do frame_counter=i;_startup_trace.exchange_ordinal=i+1;_acceptance_note(1,0,true,true) end
            frame_counter=4096;_acceptance_note(0,0,true,true)
            local count=#lines;frame_counter=999999;_acceptance_note(0,0,true,true)
            assert(#lines==count and #markers==0 and f.removes==1 and count==4099)
            _acceptance_close();assert(closes==1 and f.removes==1);return table.concat(lines)''')
        self.assertEqual(rows[-1]['reason'],'capacity')
        self.assertEqual(rows[-1]['inputs_observed'],4096)
        self.assertTrue(rows[-1]['capacity_reached'])

    def test_STATUS_cap_failure_retains_passthrough_and_single_console_marker(self):
        self.assertEqual(self.run_lua('''_acceptance_bootstrap();_acceptance_note(1,0,true,true)
            for i=1,600 do f:write(i%256) end
            assert(f.forwarded==600);frame_counter=1;_acceptance_note(0,0,true,true)
            _acceptance_close();assert(#markers==1 and closes==1 and f.removes==1);return "OK"'''),'OK')

    def test_same_frame_flags_and_coin_are_retained_after_original_apply_failure(self):
        rows=self.rows('''_acceptance_bootstrap();_acceptance_note(1,1,false,false);_acceptance_close()
            assert(#markers==0 and closes==1);return table.concat(lines)''')
        row=next(r for r in rows if r['kind']=='input')
        self.assertEqual((row['frame'],row['epoch'],row['exchange'],row['start'],row['coin']), (0,1,1,1,1))
        self.assertIs(row['apply_ok'],False)
        self.assertIs(row['socket_ok'],False)

    def test_actual_original_and_combined_callbacks_keep_actions_counters_and_apply_error_semantics(self):
        def callback(source):
            return source[source.index('function frame_callback()'):source.index('\nfunction on_mame_exit()')]
        setup=r'''
        _startup_trace=r
        memory=f.space;values=f.memory;mem=memory;values[0x9859]=128
        dead_frame_counter=0;last_save_time=os.time();SAVE_INTERVAL_S=300
        LEGACY_CORE_FEATURES=0;ZP1ENM_EMIT_COUNT=0;DEBUG_BYPASS_SOCKET_FOR_FRAMES=0;DEBUG_FORCE_ACTION_FRAMES=0
        current_socket={};trace_log=function()end;robotron_apply_start_wave_patch=function()end
        local applied={}
        controls={apply_action=function(self,move,fire,start,coin)
            applied={move,fire,start,coin}
            if faults.apply then error("original apply error") end
            values[0x9859]=0x7f;return 2
        end}
        read_frame_observation=function()return {player_alive=0,score=0,replay_level=20000,num_lasers=2,
            wave_number=1,player_x16=100,player_y16=100,enemy_state={},obs={lane_summary_features={},
            local_grid_features={},pool_features={},num_humans=0}}end
        compute_frame_rewards=function()return{done=false,subj_reward=0,obj_reward=0}end
        determine_meta_commands=function()return 1,1 end
        capture_preview_payload=function()return{w=0,h=0,fmt=0}end
        rel_pos_x=function()return 0 end;rel_pos_y=function()return 0 end;wire_lives_track=function()return 3 end
        serialize_frame=function()return payload end
        difficulty_apply=function()end;wavecap_check=function()end
        process_frame_via_socket=function()
            _startup_trace:exchange(payload);_startup_trace:response(response);return 4,6,true
        end
        r:connected()
        '''
        for apply_error in [False,True]:
            outcomes=[]
            for source,observer_fault in [(self.original,False),(self.combined,False),(self.combined,True)]:
                script=(self.raw_fixture.PRELUDE+self.prelude+SCAFFOLD+self.blocks[0]+setup+
                        ('faults.apply=true\n' if apply_error else '')+
                        ('faults.write="throw"\n' if observer_fault else '')+
                        '_acceptance_bootstrap()\n'+callback(source)+r'''
                        local ok,result=pcall(frame_callback)
                        _acceptance_close()
                        return table.concat({tostring(ok),tostring(result),frame_counter,tostring(prev_fire_cmd),
                            tostring(prev_move_cmd),applied[1],applied[2],applied[3],applied[4],values[0x9859]},":")
                        ''')
                outcomes.append(self.lua.run(script))
            self.assertEqual(outcomes,[outcomes[0]]*3)
            if not apply_error:
                self.assertEqual(outcomes[0],'true:true:1:2:4:4:6:1:1:127')

    def test_plan_only_packager_does_not_call_prepare_or_discover_runtime(self):
        code=compile((HERE/'prepare_diagnostic_package_v2.py').read_text(),'<plan-only>','exec')
        with mock.patch.object(sys,'argv',['prepare_diagnostic_package_v2.py']), \
                mock.patch.object(Path,'read_bytes',side_effect=AssertionError('source read forbidden')), \
                mock.patch.object(subprocess,'run',side_effect=AssertionError('process forbidden')), \
                mock.patch('builtins.print') as printed:
            exec(code,{'__name__':'__main__','__file__':str(HERE/'prepare_diagnostic_package_v2.py')})
        self.assertIn('PLAN_ONLY',printed.call_args.args[0])

    def test_actual126_package_inventory_fullpins_reversibility_and_parent_immutability(self):
        parent_before={name:self.u.read(self.u.BASE_ROOT/self.u.relative(name))[1]
                       for name in self.u.declared_files(self.u.decode(self.u.read(self.u.BASE_MANIFEST)[0]))}
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'actual126'
            entry=self.packager.prepare(output)
            manifest=self.u.decode(self.u.read(Path(entry['path']))[0])
            self.assertEqual(manifest['source_count'],126)
            self.u.inventory(output/'Robotron',manifest['files'])
            for name,pin in manifest['file_pins'].items():
                self.assertEqual(self.u.read(Path(pin['path']))[1],pin)
                self.assertEqual(pin['sha256'],manifest['files'][name])
            changed={name for name,pin in parent_before.items() if manifest['files'][name]!=pin['sha256']}
            self.assertEqual(changed,self.packager.CHANGED)
            self.assertEqual(set(manifest['files'])-set(parent_before),self.packager.ADDED)
            actual=(output/'Robotron/Scripts/main.lua').read_text()
            relocated=self.raw.build(self.original,output/'Robotron/Scripts/startup_prefix_v1.lua',self.raw_fixture.ORIGINAL_SHA)
            self.assertEqual(self.builder.stripped(actual),relocated)
            self.assertEqual(self.raw.stripped(self.builder.stripped(actual)),self.original)
            server=module('_integration_server_builder','prepare_startup_server_v1.py')
            self.assertEqual(server.stripped_tree((output/'Robotron/Scripts/dqn/socket_server.py').read_text()),
                             ast.dump(ast.parse((self.u.BASE_ROOT/'Scripts/dqn/socket_server.py').read_text()),include_attributes=False))
            old=(HERE/'startup-diagnostic-profile01/Robotron/Scripts/main.lua').read_text()
            normalized=old.replace(str(HERE/'startup-diagnostic-profile01/Robotron/Scripts/startup_prefix_v1.lua'),
                                   str(output/'Robotron/Scripts/startup_prefix_v1.lua'))
            self.assertEqual(normalized,self.builder.stripped(actual))
            self.assertFalse(manifest['installed_binary_ABI_proven'])
            self.assertFalse(manifest['tap_runtime_integration_present'])
            with self.assertRaises(ValueError):
                self.packager.prepare(output)
        for name,pin in parent_before.items():
            self.assertEqual(self.u.read(self.u.BASE_ROOT/self.u.relative(name))[1],pin)

    def test_package_prepublication_transform_failure_leaves_no_destination(self):
        tap=module('_integration_transform_failure','prepare_acceptance_lua_v1.py')
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'failed'
            original_checked=self.u.checked_builder
            def checked(name,path,pin):
                if path.name=='prepare_acceptance_lua_v1.py':
                    tap.build=mock.Mock(side_effect=ValueError('injected transform failure'))
                    return tap
                return original_checked(name,path,pin)
            with mock.patch.object(self.packager,'utilities',return_value=self.u), \
                    mock.patch.object(self.u,'checked_builder',side_effect=checked):
                with self.assertRaisesRegex(ValueError,'injected'):
                    self.packager.prepare(output)
            self.assertFalse(output.exists())

    def test_partial_publication_failure_retains_original_bytes_without_usable_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'partial'
            original_publish=self.u.publish
            retained=[]
            def publish(path,raw):
                if retained:
                    raise OSError('injected publication failure')
                result=original_publish(path,raw)
                retained.append((path,raw,result))
                return result
            with mock.patch.object(self.packager,'utilities',return_value=self.u), \
                    mock.patch.object(self.u,'publish',side_effect=publish):
                with self.assertRaisesRegex(OSError,'injected'):
                    self.packager.prepare(output)
            self.assertTrue(output.exists())
            self.assertFalse((output/'runtime-source-package.json').exists())
            self.assertEqual(len(retained),1)
            path,raw,pin=retained[0]
            self.assertEqual(self.u.read(path),(raw,pin))
            with self.assertRaises(ValueError):
                self.packager.prepare(output)


if __name__ == '__main__':
    time.sleep(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    print(json.dumps(dict(schema='robotron-passive-startup-package-integration-CPU-v3',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Actual Lua54 with MAME-shaped shims, original callback bodies and an actual temporary126-file package; no emulator or device query.',
        production_changed=False,protocol_selected=False,installed_binary_ABI_proven=False,real_ROM_start_proven=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
