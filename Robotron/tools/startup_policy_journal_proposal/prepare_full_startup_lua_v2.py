"""Source-bound transformation of a new isolated Lua copy, never production."""
import hashlib
import json
from pathlib import Path
import re

SOURCE_SHA='060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf'
BEGIN='-- FULL_POLICY_STARTUP_V2_BEGIN\n'
END='-- FULL_POLICY_STARTUP_V2_END\n'

READ=r'''    local read_ok, read_result = pcall(function()
        local started = socket_time_now()
        while (socket_time_now() - started) < SOCKET_READ_TIMEOUT_S do
            if #ACTION_RX_BUFFER >= 48 then
                local extended = string.sub(ACTION_RX_BUFFER, 1, 48)
                ACTION_RX_BUFFER = string.sub(ACTION_RX_BUFFER, 49)
                local action_bytes = _startup:protect("decode_response", extended, frame_idx + 1)
                local move_dir, fire_dir, source, start_advanced, start_level_min, difficulty = string.unpack("bbBBBB", action_bytes)
                START_ADVANCED = (start_advanced or 0) ~= 0
                START_LEVEL_MIN = math.max(1, math.min(81, math.floor(start_level_min or 1)))
                local diff_raw = math.floor(difficulty or 5)
                SERVER_IS_EVAL = (diff_raw & 0x80) ~= 0
                SERVER_DIFFICULTY = math.max(1, math.min(10, diff_raw & 0x7F))
                trace_log(frame_idx, "socket_read_ok_startup_envelope", "original_v2_action_preserved")
                return {move_dir, fire_dir, source}
            end
            local chunk = current_socket:read(48 - #ACTION_RX_BUFFER)
            if chunk and #chunk > 0 then
                ACTION_RX_BUFFER = ACTION_RX_BUFFER .. chunk
            elseif socket_idle_wait then
                socket_idle_wait()
            end
        end
        log_socket_receive_timeout(#ACTION_RX_BUFFER, math.max(0, socket_time_now() - started))
        ACTION_RX_BUFFER = ""
        trace_log(frame_idx, "socket_read_timeout", "closing connection; startup authorization rejected")
        return nil
    end)

'''


def build(source,helper_path):
    if hashlib.sha256(source.encode()).hexdigest()!=SOURCE_SHA or BEGIN in source or END in source:
        raise ValueError('Exact unmodified source copy required')
    helper=Path(helper_path)
    if not helper.is_absolute() or any(c in str(helper)for c in ['\n','\r','"','\\']):
        raise ValueError('Explicit absolute helper path required')
    original=source
    start=source.index('    local read_ok, read_result = pcall(function()\n')
    end=source.index('    if not read_ok then\n',start)
    prior_read=source[start:end]
    if prior_read.count('return {move_dir, fire_dir, source}')!=3:
        raise ValueError('Original six/five/three-byte reader differs')
    source=source[:start]+READ+source[end:]
    def insert(anchor,code,*,before=False):
        nonlocal source
        if source.splitlines(keepends=True).count(anchor)!=1:
            raise ValueError('Exact startup integration anchor differs: '+anchor[:70])
        block=BEGIN+code+'\n'+END
        source=re.sub('^'+re.escape(anchor),lambda _:block+anchor if before else anchor+block,
                      source,flags=re.M)
    insert('CLIENT_SLOT = math.max(0, math.floor(tonumber(os.getenv("ROBOTRON_CLIENT_SLOT") or "0") or 0))\n',
           'local _startup = nil')
    insert('local function close_socket()\n',
           '    if _startup and _startup.connected_once and not _startup.closed then _startup:fail("original_socket_closed") end')
    insert('            current_socket = sock\n','            _startup:protect("connected", sock)')
    insert('open_socket()\n',
           ' _startup = assert(loadfile('+json.dumps(str(helper))+'))().attach(controls, {eval_mode=EVAL_MODE, '
           'debug_bypass_frames=DEBUG_BYPASS_SOCKET_FOR_FRAMES, force_action_frames=DEBUG_FORCE_ACTION_FRAMES})',before=True)
    insert('    trace_log(frame_counter, "frame_begin", "callback entered")\n',
           '    _startup:protect("begin", frame_counter + 1)')
    insert('    local start_cmd, coin_cmd = determine_meta_commands(dead_frame_counter, player_alive)\n',
           '    start_cmd, coin_cmd = _startup:protect("plan", frame_counter + 1, start_cmd, coin_cmd)')
    insert('        local length_header = string.pack(">I4", #frame_payload)\n',
           '        frame_payload = _startup:protect("envelope", frame_payload, frame_idx + 1)',before=True)
    insert('    local effective_fire = fire_cmd  -- fallback if pcall fails\n',
           '    start_cmd, coin_cmd = _startup:protect("inputs", socket_ok, '
           'DEBUG_BYPASS_SOCKET_FOR_FRAMES > 0 and frame_counter < DEBUG_BYPASS_SOCKET_FOR_FRAMES, '
           'DEBUG_FORCE_ACTION_FRAMES > 0 and frame_counter < DEBUG_FORCE_ACTION_FRAMES)',before=True)
    insert('    local ok_apply, apply_result = pcall(controls.apply_action, controls, move_cmd, fire_cmd, start_cmd, coin_cmd)\n',
           '    _startup:protect("applied", start_cmd, coin_cmd, socket_ok, ok_apply)')
    insert('    frame_counter = frame_counter + 1\n','    _startup:protect("finish", frame_counter)')
    insert('        trace_log(frame_counter, err_phase or "frame_read_error", tostring(err_detail), true)\n',
           '        _startup:fail("frame_observation_failed")',before=True)
    insert('        trace_log(frame_counter, "serialize_frame_error", tostring(payload_or_err), true)\n',
           '        _startup:fail("frame_serialization_failed")',before=True)
    insert('    trace_log(frame_counter, "session_stop", "machine stop notifier", true)\n',
           '    if _startup then _startup:close("machine_stop") end',before=True)
    reverse=source.replace(READ,prior_read)
    reverse=re.sub(re.escape(BEGIN)+r'.*?'+re.escape(END),'',reverse,flags=re.S)
    if reverse!=original:
        raise ValueError('Reversing explicit reader replacement and hook blocks changed original bytes')
    return source,dict(original_sha256=SOURCE_SHA,proposed_sha256=hashlib.sha256(source.encode()).hexdigest(),
        helper_path=str(helper),original_response_reader=prior_read,new_response_reader=READ,
        reverse_restores_original_bytes=True,
        scope='Full original observation/reward/control calculation retained; explicit version2 envelope and one-use startup input gate, bounded trace continuation and drained-shutdown control supplied by the selected helper.')
