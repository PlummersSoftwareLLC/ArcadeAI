"""Pure source transformation for a separate, passive ROM provenance observer."""
import hashlib
import json
from pathlib import Path
import re

BEGIN = '-- STARTUP_ACCEPTANCE_V1_BEGIN\n'
END = '-- STARTUP_ACCEPTANCE_V1_END\n'
RAW_BEGIN = '-- STARTUP_DIAGNOSTIC_V1_BEGIN\n'
RAW_END = '-- STARTUP_DIAGNOSTIC_V1_END\n'

# Kept in one lexical scope after the raw recorder's local declaration. All
# observer failures stay outside the original action/error/return paths.
DECLARATIONS = r'''local _acceptance_stream, _acceptance_tap
local _acceptance_enabled, _acceptance_attempted, _acceptance_failed = false, false, false
local _acceptance_reported, _acceptance_stopped = false, false
local function _acceptance_report(code)
    _acceptance_failed = true
    if not _acceptance_reported then
        _acceptance_reported = true
        pcall(print, "ROBOTRON_STARTUP_ACCEPTANCE_TAP_FAILURE:" .. code)
    end
end
local function _acceptance_status()
    if not _acceptance_tap then return nil end
    local ok, status = pcall(_acceptance_tap.status, _acceptance_tap)
    if not ok or type(status) ~= "table" then
        _acceptance_report("status_error"); return nil
    end
    if status.failed or status.logging_failed then _acceptance_report("component_failed") end
    return status
end
local function _acceptance_bootstrap()
    local ok = pcall(function()
        local path = os.getenv("ROBOTRON_STARTUP_ACCEPTANCE_PATH")
        if path == nil or path == "" then return end
        _acceptance_enabled = true
        assert(not _acceptance_attempted and not _acceptance_stopped, "repeat or late bootstrap")
        _acceptance_attempted = true
        assert(frame_counter == 0, "installation after owned input")
        assert(math.type(CLIENT_SLOT) == "integer" and CLIENT_SLOT >= 4096 and CLIENT_SLOT <= 4127)
        local session = os.getenv("ROBOTRON_STARTUP_DIAGNOSTIC_SESSION")
        assert(type(session) == "string" and #session == 32 and session:match("^[a-f0-9]+$"))
        assert(_startup_trace and _startup_trace.session == session and not _startup_trace.closed
            and not _startup_trace.failed and _startup_trace.attempts == 0, "raw recorder not bound before input")
        assert(type(path) == "string" and #path <= 1024 and path:sub(1,1) == "/"
            and not path:find("[%z\r\n]") and not path:find("//",1,true)
            and not path:find("/../",1,true) and not path:find("/./",1,true)
            and not path:match("/%.%.?$") and path:sub(-1) ~= "/", "explicit output path required")
        local raw_path = os.getenv("ROBOTRON_STARTUP_DIAGNOSTIC_PATH")
        assert(type(raw_path) == "string" and raw_path ~= "" and raw_path ~= path)
        -- Caller must bind a fresh owned private directory. fopen is not an
        -- atomic exclusive-create primitive, and no such property is claimed.
        local prior = io.open(path, "rb")
        if prior then
            local closed = prior:close()
            assert(closed == true, "prior read handle close failed")
            error("diagnostic output already exists")
        end
        _acceptance_stream = assert(io.open(path, "wb"))
        -- Own the handle before module loading/resource discovery can fail.
        local module = assert(loadfile(HELPER_PATH))()
        local machine = manager.machine
        _acceptance_tap = module.new({slot=CLIENT_SLOT, session=session, space=mem,
            cpu=machine.devices[":maincpu"], bank=machine.memory.banks[":mainbank"],
            region=machine.memory.regions[":maincpu"], write=function(line)
                local written, result = pcall(function()
                    assert(type(line) == "string" and #line <= 2048)
                    assert(_acceptance_stream:write(line))
                    return _acceptance_stream:flush() == true
                end)
                if not written or result ~= true then
                    _acceptance_report("output_error"); return false
                end
                return true
            end})
        assert(_acceptance_tap:install(), "installation failed")
        _acceptance_status()
    end)
    if not ok then _acceptance_report("setup_error") end
end
local function _acceptance_note(start, coin, apply_ok, socket_ok)
    if not _acceptance_enabled or _acceptance_stopped or _acceptance_failed then return end
    local ok = pcall(function()
        local status = _acceptance_status()
        assert(status, "missing observer")
        if status.closed then return end
        assert(_acceptance_tap:input(frame_counter, _startup_trace.epoch or 0,
            _startup_trace.exchange_ordinal or 0, start, coin, apply_ok, socket_ok), "input observation failed")
        _acceptance_status()
    end)
    if not ok then _acceptance_report("input_error") end
end
local function _acceptance_close()
    if _acceptance_stopped then return end
    _acceptance_stopped = true
    if _acceptance_tap then
        local ok, result = pcall(_acceptance_tap.close, _acceptance_tap, "machine_stop")
        if not ok or result ~= true then _acceptance_report("component_close_error") end
        _acceptance_status()
    end
    if _acceptance_stream then
        local stream = _acceptance_stream
        _acceptance_stream = nil
        local ok, result = pcall(function() return stream:close() end)
        if not ok or result ~= true then _acceptance_report("stream_close_error") end
    end
end'''


def stripped(source):
    return re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END), '', source, flags=re.S)


def build(source, helper_path, expected_sha256):
    if hashlib.sha256(source.encode()).hexdigest() != expected_sha256:
        raise ValueError('Raw instrumented Lua SHA differs')
    if BEGIN in source or END in source:
        raise ValueError('Acceptance hooks already present')
    if source.count(RAW_BEGIN) != 11 or source.count(RAW_END) != 11:
        raise ValueError('Exact eleven raw-prefix blocks required')
    path = Path(helper_path)
    if (not path.is_absolute() or path != path.resolve() or
            any(ord(c) >= 128 or c in '\x00\n\r"\\' for c in str(path))):
        raise ValueError('Canonical absolute ASCII helper path required')
    original = source

    def insert(anchor, code, before=False):
        nonlocal source
        if source.count(anchor) != 1:
            raise ValueError('Unique exact hook anchor required: ' + anchor[:60])
        block = BEGIN + code + '\n' + END
        source = source.replace(anchor, block + anchor if before else anchor + block, 1)

    initial = re.findall(r'^local _startup_trace = [^\n]+\n' + re.escape(RAW_END), source, flags=re.M)
    if len(initial) != 1:
        raise ValueError('Raw local recorder initialization scope differs')
    insert(initial[0], DECLARATIONS.replace('HELPER_PATH', json.dumps(str(path))))
    insert('\nopen_socket()\n', '_acceptance_bootstrap()', before=True)
    insert('    _startup_trace:finish(move_cmd, fire_cmd, start_cmd, coin_cmd, socket_ok, ok_apply)\n',
           '    _acceptance_note(start_cmd, coin_cmd, ok_apply, socket_ok)')
    insert('    _startup_trace:close("machine_stop")\n', '    _acceptance_close()')
    if source.count(BEGIN) != 4 or source.count(END) != 4 or stripped(source) != original:
        raise ValueError('Exact hook reversibility differs')
    return source
