"""Build a separate diagnostic Lua copy; no production writes or runtime imports."""
import hashlib
import json
from pathlib import Path
import re

BEGIN = '-- STARTUP_DIAGNOSTIC_V1_BEGIN\n'
END = '-- STARTUP_DIAGNOSTIC_V1_END\n'


def stripped(source):
    return re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END), '', source, flags=re.S)


def build(source, helper_path, expected_sha256):
    if hashlib.sha256(source.encode()).hexdigest() != expected_sha256:
        raise ValueError('Original frozen Lua source SHA differs')
    if BEGIN in source or END in source:
        raise ValueError('Diagnostic source was already prepared')
    helper_path = Path(helper_path)
    if not helper_path.is_absolute() or any(x in str(helper_path) for x in ('\n', '\r', '"', '\\')):
        raise ValueError('Explicit absolute diagnostic helper path required')
    original = source

    def insert(anchor, code, *, before=False, count=1):
        nonlocal source
        if source.splitlines(keepends=True).count(anchor) != count:
            raise ValueError('Exact Lua anchor count differs: ' + anchor[:60])
        block = BEGIN + code + '\n' + END
        source = re.sub('^' + re.escape(anchor),
                        lambda _: block + anchor if before else anchor + block,
                        source, flags=re.M)

    insert('CLIENT_SLOT = math.max(0, math.floor(tonumber(os.getenv("ROBOTRON_CLIENT_SLOT") or "0") or 0))\n',
           'local _startup_trace = assert(loadfile(' + json.dumps(str(helper_path)) + '))().from_environment(CLIENT_SLOT)')
    insert('            current_socket = sock\n', '            _startup_trace:connected()')
    insert('    trace_log(frame_counter, "frame_begin", "callback entered")\n',
           '    _startup_trace:begin(frame_counter, mem)')
    insert('        trace_log(frame_counter, err_phase or "frame_read_error", tostring(err_detail), true)\n',
           '        _startup_trace:abort("frame_read_error")', before=True)
    insert('        trace_log(frame_counter, "serialize_frame_error", tostring(payload_or_err), true)\n',
           '        _startup_trace:abort("serialize_error")', before=True)
    insert('        current_socket:write(length_header .. frame_payload)\n',
           '        _startup_trace:exchange(frame_payload)', before=True)
    insert('                return {move_dir, fire_dir, source}\n',
           '                _startup_trace:response(action_bytes)', before=True)
    insert('                        return {move_dir, fire_dir, source}\n',
           '                        _startup_trace:response(action_bytes)', before=True, count=2)
    insert('    local ok_apply, apply_result = pcall(controls.apply_action, controls, move_cmd, fire_cmd, start_cmd, coin_cmd)\n',
           '    _startup_trace:finish(move_cmd, fire_cmd, start_cmd, coin_cmd, socket_ok, ok_apply)')
    insert('    trace_log(frame_counter, "session_stop", "machine stop notifier", true)\n',
           '    _startup_trace:close("machine_stop")')
    if stripped(source) != original:
        raise ValueError('Removing diagnostic blocks did not restore exact original Lua bytes')
    return source
