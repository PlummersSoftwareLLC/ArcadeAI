"""Isolated CPU/libLua5.4 contract for exact extracted wavecap blocks.

Only globals and wavecap_check execute, with fake manager/reset/frame state.
Whole scripts are syntax-compiled, never executed. No MAME, target Python module,
actor, service, socket, GPU, model, replay, CONTROL or PUBLIC access occurs.
"""
import argparse
import ctypes
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time

ROOT = Path(__file__).absolute().parent
BASELINE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fleet-wide-multiple-reconnect-overlap-quarantine-original01-20261031/future-Main-RPC-backpressure-source-only-original01/main_rpc_backpressure120_v1.lua')
BASELINE_SHA = 'bc7df0d6ca18da11cd6498867a5b77e3638d8b721094264f056fe6a949d75f76'
BEGIN = 'WAVE_RESET_CAP = 75\n'
END = '\nlocal function poke_difficulty('


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def selected(path, sha):
    before = path.lstat()
    require(path.is_absolute() and path.resolve() == path and stat.S_ISREG(before.st_mode)
            and before.st_uid == 1001 and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) == 0o444 and 0 < before.st_size < 1 << 20,
            'Bounded owned immutable source required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(fd)) == identity(before), 'Source changed on open')
        raw = os.read(fd, before.st_size + 1)
        require(identity(os.fstat(fd)) == identity(before) == identity(path.lstat())
                and len(raw) == before.st_size, 'Source changed while reading')
    finally:
        os.close(fd)
    require(hashlib.sha256(raw).hexdigest() == sha, 'Selected source SHA differs')
    return raw.decode(), dict(path=str(path), sha256=sha, bytes=len(raw), identity=identity(before))


def split(source):
    require(source.count(BEGIN) == 1 and source.count(END) == 1, 'Unique exact wavecap boundaries required')
    start = source.index(BEGIN)
    end = source.index(END, start)
    return source[:start], source[start:end], source[end:]


class Lua:
    def __init__(self):
        self.library = ctypes.util.find_library('lua5.4')
        require(self.library is not None, 'Standalone libLua5.4 required; no skip qualification')
        self.lib = ctypes.CDLL(self.library)
        self.lib.luaL_newstate.restype = ctypes.c_void_p
        self.lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
        self.lib.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.luaL_loadstring.restype = ctypes.c_int
        self.lib.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ssize_t, ctypes.c_void_p]
        self.lib.lua_pcallk.restype = ctypes.c_int
        self.lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        self.lib.lua_tolstring.restype = ctypes.c_char_p
        self.lib.lua_close.argtypes = [ctypes.c_void_p]

    def run(self, source, execute):
        state = self.lib.luaL_newstate()
        require(bool(state), 'Lua state allocation failed')
        try:
            self.lib.luaL_openlibs(state)
            code = self.lib.luaL_loadstring(state, source.encode())
            if code == 0 and execute:
                code = self.lib.lua_pcallk(state, 0, 1, 0, 0, None)
            if code != 0:
                raise AssertionError(self.lib.lua_tolstring(state, -1, None).decode(errors='replace'))
            return self.lib.lua_tolstring(state, -1, None).decode() if execute else None
        finally:
            self.lib.lua_close(state)


PREFIX = r'''
local resets, frame = 0, 0
local messages = {}
local throw_reset = false
EVAL_MODE = 0
SERVER_IS_EVAL = false
print = function(message) messages[#messages + 1] = message end
manager = {machine = {soft_reset = function(self)
    resets = resets + 1
    if throw_reset then error("simulated reset rejection") end
end}}
'''
STEP = r'''
local function step(w, alive, score)
    frame = frame + 1
    wavecap_check(frame, w, alive, score)
end
'''

# Each case runs separately against both exact source blocks in fresh Lua VMs.
# The old miss/delayed-score results0 are expected reproductions, not passes of
# the new contract. The selected candidate must produce1 in those two cases.
CASES = [
    ('healthy_exact_edge_once', 'step(74,1,60000); step(75,1,60000); step(75,1,61000)', 1, 1),
    ('inactive_first_cap_frame_then_alive', 'step(74,1,60000); step(75,0,60000); assert(resets==0); step(75,1,60000); step(75,1,61000)', 0, 1),
    ('stale_initial_cap_and_attract', 'step(75,0,900000); step(75,1,900000); step(0,0,0); step(75,1,900000)', 0, 0),
    ('EVAL_MODE_exempt', 'EVAL_MODE=1; step(74,1,60000); step(75,0,60000); step(75,1,60000)', 0, 0),
    ('SERVER_IS_EVAL_exempt', 'SERVER_IS_EVAL=true; step(74,1,60000); step(75,0,60000); step(75,1,60000)', 0, 0),
    ('cap_disabled_exempt', 'WAVE_RESET_CAP=0; step(74,1,60000); step(75,1,60000)', 0, 0),
    ('score_guard_delays_until_50k', 'step(74,1,49999); step(75,1,49999); assert(resets==0); step(75,1,50000); step(75,1,51000)', 0, 1),
    ('positive_score_to_zero_clears_pending', 'step(74,1,60000); step(75,0,60000); step(75,1,0); step(75,1,60000)', 0, 0),
    ('below_cap_clears_then_new_edge_arms', 'step(74,1,60000); step(75,0,60000); step(73,1,60000); step(75,1,60000); assert(resets==0); step(74,1,60000); step(75,1,60000)', 1, 1),
    ('legacy_deep_no_edge_unchanged', 'step(76,1,900000); step(77,1,910000); step(120,1,950000); step(75,1,960000)', 0, 0),
    ('reset_attempt_once_even_if_pcall_fails', 'throw_reset=true; step(74,1,60000); step(75,1,60000); step(75,1,61000); step(75,1,62000)', 1, 1),
    ('deferred_attempt_consumed_if_pcall_fails', 'throw_reset=true; step(74,1,60000); step(75,0,60000); step(75,1,60000); step(75,1,61000)', 0, 1),
    ('reload_at_stale_cap_does_not_loop', 'step(74,1,60000); step(75,1,60000); assert(resets==1); __RELOAD_BLOCK__; wavecap_check(99,75,1,60000); wavecap_check(100,75,1,61000)', 1, 1),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--source-sha256')
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--candidate-sha256')
    parser.add_argument('--output-directory', type=Path)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: isolated Lua contract only; no inputs or outputs')
        return 0
    require(all((args.source_sha256, args.candidate, args.candidate_sha256, args.output_directory)), 'Exact selected source and fresh output required')
    require(args.candidate.parent == ROOT and args.candidate.suffix == '.lua', 'Exact private candidate source required')
    output = args.output_directory
    require(output.parent == ROOT and output.name.startswith('independent-isolated-wave75-CPU-')
            and not output.exists() and not output.is_symlink(), 'Fresh private report directory required')
    own_source, own_pin = selected(Path(__file__).absolute(), args.source_sha256)
    baseline, baseline_pin = selected(BASELINE, BASELINE_SHA)
    candidate, candidate_pin = selected(args.candidate, args.candidate_sha256)
    old_prefix, old_block, old_suffix = split(baseline)
    new_prefix, new_block, new_suffix = split(candidate)
    require(old_prefix == new_prefix and old_suffix == new_suffix, 'Any non-wavecap source change is forbidden')
    started = time.time()
    lua = Lua()
    rows = []
    for name, source in [('baseline', baseline), ('candidate', candidate)]:
        try:
            lua.run(source, execute=False)
            rows.append(dict(case='whole_script_compile_only', target=name, status='PASS', whole_script_executed=False))
        except Exception as error:
            rows.append(dict(case='whole_script_compile_only', target=name, status='FAIL', error=repr(error)))
    for name, body, old_expected, new_expected in CASES:
        for target, block, expected in [('baseline', old_block, old_expected), ('candidate', new_block, new_expected)]:
            try:
                case_body = body.replace('__RELOAD_BLOCK__', block)
                log_guard = ''
                if target == 'candidate' and name in ('healthy_exact_edge_once', 'inactive_first_cap_frame_then_alive'):
                    fire = 2 if name == 'healthy_exact_edge_once' else 3
                    delay = fire - 2
                    for field in ('armed_frame=2', 'fire_frame=' + str(fire), 'current_wave=75', 'score=60000', 'delay_frames=' + str(delay)):
                        log_guard += 'assert(string.find(messages[1], ' + json.dumps(field) + ', 1, true));\n'
                program = PREFIX + block + STEP + case_body + '\nassert(resets == ' + str(expected) + ')\n' + log_guard
                program += 'return tostring(resets) .. "\\n" .. table.concat(messages, "\\n")'
                actual = lua.run(program, execute=True)
                reset_text, separator, log = actual.partition('\n')
                require(int(reset_text) == expected, 'Observed reset count differs')
                rows.append(dict(case=name, target=target, status='PASS', actual_reset_attempts=int(reset_text),
                                 expected_reset_attempts=expected, simulated_log=log))
            except Exception as error:
                rows.append(dict(case=name, target=target, status='FAIL', expected_reset_attempts=expected, error=repr(error)))
    selected(BASELINE, BASELINE_SHA)
    selected(args.candidate, args.candidate_sha256)
    selected(Path(__file__).absolute(), args.source_sha256)
    require('torch' not in sys.modules, 'Unexpected Torch import')
    failed = [row for row in rows if row['status'] != 'PASS']
    report = dict(schema='robotron-isolated-wave75-latch-Lua-CPU-contract-v1',
        status='PASS_ISOLATED_LUA_CONTRACT' if not failed else 'FAIL_ISOLATED_LUA_CONTRACT',
        actual_exit=1 if failed else 0, started_unix_s=started, ended_unix_s=time.time(),
        fixture=own_pin, baseline=baseline_pin, candidate=candidate_pin, library=lua.library,
        extracted_blocks=dict(baseline=dict(bytes=len(old_block.encode()), sha256=hashlib.sha256(old_block.encode()).hexdigest()),
                              candidate=dict(bytes=len(new_block.encode()), sha256=hashlib.sha256(new_block.encode()).hexdigest())),
        only_wavecap_block_changed=True, whole_script_compile_only_checks=2, behavioral_cases=len(CASES),
        behavioral_VM_checks=2*len(CASES), checks=len(rows), failures=len(failed), skips=0, results=rows,
        scope=dict(exact_extracted_globals_and_function=True, fake_frame_inputs_and_reset_attempt_counter=True,
            actual_MAME_or_soft_reset_effect_qualified=False, game_or_performance_improvement_qualified=False,
            whole_Main_script_executed=False, target_Python_or_Torch_imported=False,
            actors_services_sockets_GPU_models_replay_CONTROL_PUBLIC_or_canonical_sources_accessed=False,
            future_candidate_installed=False))
    raw = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    output.mkdir(mode=0o700)
    fd = os.open(output/'report.json', os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    directory = os.open(output, os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)
    print(json.dumps(dict(status=report['status'], checks=len(rows), failures=len(failed), skips=0,
                         report=str(output/'report.json'), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))))
    return report['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
