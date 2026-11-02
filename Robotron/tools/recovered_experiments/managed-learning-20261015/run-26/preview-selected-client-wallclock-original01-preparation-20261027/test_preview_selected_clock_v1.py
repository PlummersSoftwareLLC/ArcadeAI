"""CPU-only source checks. No MAME, sockets, Torch, controls, or live capture."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import threading
import types
import typing
import unittest


ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = Path(__file__).resolve().parent
OBSERVED = {}
SOURCES = {
    'original': (ROOT / 'Scripts/main.lua', '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf'),
    'wall': (HERE / 'main-lua-wallclock-only-candidate.lua', 'e347f412747733df57b20fd5f0ac04cd08bf929e37852f4cb20c175771c53f63'),
    'phase': (HERE / 'main-lua-selected-preview30-candidate.lua', '507f3f5a799d49791d2c6cbca3f4600167a166c4a410723d4d29225d18b6e0ab'),
}


def checked(path, sha):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == sha
    return raw.decode()


def actual_server_methods():
    source = checked(ROOT / 'Scripts/dqn/socket_server.py',
                     'b552b2e83a9cc10cf7e4125cef22f571abe9189bd2ad3e63c6f48aa7df0e4516')
    tree = ast.parse(source)
    selected = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
    names = {'_pick_default_preview_client_locked', '_ensure_preview_client_selected_locked',
             '_is_preview_client', '_preview_enabled_for_client', '_clear_preview_cache',
             'set_preview_client', 'get_selected_preview_client_id'}
    selected.body = [n for n in selected.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in selected.body} == names
    selected.bases = []
    module = ast.fix_missing_locations(ast.Module(body=[selected], type_ignores=[]))
    scope = {'Optional': typing.Optional}
    exec(compile(module, str(ROOT / 'Scripts/dqn/socket_server.py'), 'exec'), scope)
    cls = scope['SocketServer']
    server = cls.__new__(cls)
    server.client_lock = threading.Lock()
    server.client_states = {i: {'preview_capable': True, 'client_slot': i} for i in range(192)}
    server.preview_cid = 0
    server.preview_disabled = False
    server.metrics = types.SimpleNamespace(lock=threading.Lock(), preview_capture_enabled=True,
                                           web_client_count=1)
    return server


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {name: checked(*entry) for name, entry in SOURCES.items()}
        hp = ROOT / 'tools/preview_wall_clock_proposal_20261021/validate_preview_clock_v1.py'
        checked(hp, '02634d807c7e2a45ca309b25f2a335b0ad7e4b33d8ffda2c459ea17828a43163')
        spec = importlib.util.spec_from_file_location('_preview_prior_lua_harness', hp)
        cls.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helper)
        library = Path('/usr/lib/aarch64-linux-gnu/liblua5.4.so.0.0.0')
        assert hashlib.sha256(library.read_bytes()).hexdigest() == '1efa98f498f9867b603cba7a8e8ad1d3b44a4070774043848cb8fda216d482d6'
        cls.lua = cls.helper.Lua(library)

    def test_exact_source_deltas_and_compile(self):
        original, wall, phase = [self.sources[x] for x in ('original', 'wall', 'phase')]
        self.assertEqual(wall, original.replace('    local now_s = os.clock()\n',
                                                '    local now_s = socket_time_now()\n', 1))
        self.assertEqual(phase, wall.replace('    last_preview_capture_time_s = now_s\n',
                         '    last_preview_capture_time_s = now_s - ((now_s - last_preview_capture_time_s) % PREVIEW_MIN_INTERVAL_S)\n', 1))
        for source in self.sources.values():
            self.lua.run(source, compile_only=True)

    def test_one_selected_of192_and_switch(self):
        server = actual_server_methods()
        self.assertEqual([i for i in range(192) if server._preview_enabled_for_client(i)], [0])
        self.assertEqual(server.set_preview_client(163), (True, 163))
        self.assertEqual([i for i in range(192) if server._preview_enabled_for_client(i)], [163])
        self.assertEqual(server.metrics.game_preview_client_id, -1)
        self.assertEqual(server.metrics.game_preview_seq, 0)
        self.assertEqual(server.metrics.game_preview_data, b'')

    def test_no_viewer_capture_disabled_and_stop(self):
        server = actual_server_methods()
        for attribute, value in [('web_client_count', 0), ('preview_capture_enabled', False)]:
            setattr(server.metrics, attribute, value)
            self.assertFalse(any(server._preview_enabled_for_client(i) for i in range(192)))
            server.metrics.web_client_count = 1
            server.metrics.preview_capture_enabled = True
        self.assertEqual(server.set_preview_client(None), (True, None))
        self.assertFalse(any(server._preview_enabled_for_client(i) for i in range(192)))
        self.assertFalse(server.set_preview_client(999)[0])

    def test_selected_disconnect_fallback_is_single_capable_member(self):
        server = actual_server_methods()
        server.set_preview_client(163)
        del server.client_states[163]
        server.client_states[0]['preview_capable'] = False
        self.assertEqual(server.get_selected_preview_client_id(), 1)
        self.assertEqual([i for i in range(192) if server._preview_enabled_for_client(i)], [1])

    def test_actual_lua_disabled_capture_and_cpu_wait_negative(self):
        body = '''
        for i=0,2000 do fake_wall=i/1000;capture_game_preview() end
        assert(captures==0 and pending_preview_blob==nil)
        set_preview_stream_enabled(true)
        for i=0,2000 do fake_wall=i/1000;capture_game_preview() end
        local enabled_count=captures
        set_preview_stream_enabled(false)
        fake_wall=10;capture_game_preview()
        assert(captures==enabled_count and pending_preview_blob==nil)
        return tostring(enabled_count)
        '''
        counts = {name: int(self.lua.run(self.helper.fixture(source) + body))
                  for name, source in self.sources.items()}
        OBSERVED['stationary_CPU_2s_capture_counts'] = counts
        self.assertEqual(counts['original'], 1)
        self.assertTrue(58 <= counts['wall'] <= 61)
        self.assertTrue(59 <= counts['phase'] <= 61)

    def test_target_phase_cadence_25_40_50_60_hz(self):
        rows = []
        for frequency in (25, 40, 50, 60):
            body = ('set_preview_stream_enabled(true)\n'
                    f'for i=0,{frequency * 10} do fake_wall=i/{frequency};capture_game_preview() end\n'
                    'return tostring(captures)')
            wall, phase = [int(self.lua.run(self.helper.fixture(self.sources[name]) + body))
                           for name in ('wall', 'phase')]
            target = min(frequency, 30) * 10
            self.assertTrue(target - 1 <= phase <= target + 1, (frequency, wall, phase))
            if frequency in (40, 50):
                self.assertLess(wall, phase - 20)
            rows.append(dict(callback_hz=frequency, simulated_wall_s=10,
                             baseline_wall_captures=wall, target_phase_captures=phase))
        OBSERVED['cadence'] = rows

    def test_legacy_clock_one_line_fallback_schedule_unchanged(self):
        body = '''
        assert(socket_clock_kind=="process_cpu")
        set_preview_stream_enabled(true)
        local counts={}
        for i=0,200 do fake_wall=i;fake_cpu=i/100;capture_game_preview();counts[#counts+1]=captures end
        return table.concat(counts,",")
        '''
        for mode in ('legacy', 'unsupported'):
            before, after = [self.lua.run(self.helper.fixture(self.sources[name], mode) + body)
                             for name in ('original', 'wall')]
            self.assertEqual(before, after)

    def test_target_long_stall_discards_backlog_without_burst(self):
        body = '''
        set_preview_stream_enabled(true)
        capture_game_preview()
        assert(captures==1)
        fake_wall=1000
        capture_game_preview()
        assert(captures==2)
        for i=1,100 do capture_game_preview() end
        assert(captures==2)
        set_preview_stream_enabled(false)
        fake_wall=1001;capture_game_preview()
        assert(captures==2 and pending_preview_blob==nil)
        set_preview_stream_enabled(true)
        fake_wall=1002;capture_game_preview()
        assert(captures==3)
        return "one_capture_no_backlog_burst"
        '''
        self.assertEqual(self.lua.run(self.helper.fixture(self.sources['phase']) + body),
                         'one_capture_no_backlog_burst')


if __name__ == '__main__':
    unittest.main()
