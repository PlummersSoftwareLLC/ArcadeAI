-- Diagnostic prefix only. No start classification, memory writes or game admission.
local M = {}
local Recorder = {}
Recorder.__index = Recorder
local SCHEMA = "robotron-lua-startup-prefix-v1"

local function integer(value, low, high)
    assert(math.type(value) == "integer" and value >= low and value <= high, "invalid diagnostic integer")
    return value
end

local function scalar(value)
    if type(value) == "boolean" then return value and "true" or "false" end
    if math.type(value) == "integer" then return tostring(value) end
    assert(type(value) == "string" and value:match("^[%w_:%-%.]*$"), "invalid diagnostic text")
    return '"' .. value .. '"'
end

local function encode(row)
    local keys, parts = {}, {}
    for key in pairs(row) do keys[#keys + 1] = key end
    table.sort(keys)
    for _, key in ipairs(keys) do parts[#parts + 1] = scalar(key) .. ":" .. scalar(row[key]) end
    return "{" .. table.concat(parts, ",") .. "}\n"
end

function Recorder:emit(row)
    if self.closed then return false end
    if self.events >= self.max_events then
        self.faults, self.closed, self.failed = self.faults + 1, true, true
        if self.close_writer then pcall(self.close_writer) end
        return false
    end
    row.schema, row.slot, row.session = SCHEMA, self.slot, self.session
    local ok, result = pcall(function()
        local line = encode(row)
        assert(#line <= 2048, "diagnostic record exceeds bound")
        return self.write(line)
    end)
    if not ok or result ~= true then
        self.faults = self.faults + 1
        self.closed, self.failed = true, true
        if self.close_writer then pcall(self.close_writer) end
        return false
    end
    self.events = self.events + 1
    return true
end

function Recorder:guard(fn, ...)
    if self.closed then return end
    local ok, result = pcall(fn, self, ...)
    if not ok then
        self.faults = self.faults + 1
        self:emit({kind="fault", reason="observer_error", faults=self.faults})
        self.pending = nil
        return
    end
    return result
end

function Recorder:connected()
    return self:guard(function(s)
        s.epoch, s.exchange_ordinal = s.epoch + 1, 0
        s:emit({kind="connection", epoch=s.epoch})
    end)
end

function Recorder:begin(frame, memory)
    return self:guard(function(s)
        if s.attempts >= s.limit then s:close("capacity"); return end
        s.attempts = s.attempts + 1
        integer(frame, 0, 9007199254740991)
        if s.pending or (s.last_frame ~= nil and frame <= s.last_frame) then
            s.faults = s.faults + 1
            s:emit({kind="fault", reason="unfinished_or_repeated_frame", frame=frame})
        end
        s.last_frame = frame
        local raw = {}
        for _, addr in ipairs({0x9859, 0xBDE4, 0xBDE5, 0xBDE6, 0xBDE7, 0xBDEC, 0xBDED}) do
            raw[#raw + 1] = integer(memory:read_u8(addr), 0, 255)
        end
        s.pending = {kind="frame", frame=frame, epoch=s.epoch,
            exchange=0, raw_status=raw[1], raw_score_hex=string.format("%02x%02x%02x%02x", raw[2], raw[3], raw[4], raw[5]),
            raw_reserves=raw[6], raw_wave=raw[7], wire_observed=false, response_observed=false}
    end, frame, memory)
end

function Recorder:exchange(payload)
    return self:guard(function(s)
        assert(s.pending and s.pending.exchange == 0 and s.epoch > 0, "missing frame or connection")
        s.exchange_ordinal = s.exchange_ordinal + 1
        local n, subj, obj, done, score, alive, save, start, replay, reserves, wave, lives =
            string.unpack(">I2ddBI4BBBI4BBB", payload)
        local r = s.pending
        r.exchange, r.epoch = s.exchange_ordinal, s.epoch
        r.wire_observed, r.payload_bytes, r.wire_n = true, #payload, n
        r.wire_done, r.wire_score, r.wire_alive = done, score, alive
        r.wire_start, r.wire_reserves, r.wire_wave, r.wire_lives = start, reserves, wave, lives
    end, payload)
end

function Recorder:response(bytes)
    return self:guard(function(s)
        assert(s.pending and s.pending.exchange > 0 and not s.pending.response_observed, "unexpected response")
        assert(#bytes == 3 or #bytes == 5 or #bytes == 6, "unexpected action length")
        s.pending.response_observed = true
        s.pending.response_hex = (bytes:gsub(".", function(c) return string.format("%02x", string.byte(c)) end))
    end, bytes)
end

function Recorder:finish(move, fire, start, coin, socket_ok, apply_ok)
    return self:guard(function(s)
        assert(s.pending, "missing frame")
        local r = s.pending
        r.move, r.fire = integer(move, -1, 8), integer(fire, -1, 8)
        r.start_input, r.coin_input = integer(start, 0, 1), integer(coin, 0, 1)
        assert(type(socket_ok) == "boolean" and type(apply_ok) == "boolean", "invalid result flags")
        r.socket_ok, r.apply_ok = socket_ok, apply_ok
        s.pending = nil
        if s:emit(r) then s.rows = s.rows + 1 end
        if s.attempts >= s.limit then s:close("capacity") end
    end, move, fire, start, coin, socket_ok, apply_ok)
end

function Recorder:abort(reason)
    return self:guard(function(s)
        assert(reason == "frame_read_error" or reason == "serialize_error", "unexpected abort")
        s.faults = s.faults + 1
        s:emit({kind="fault", reason=reason, frame=s.last_frame or -1})
        s.pending = nil
        if s.attempts >= s.limit then s:close("capacity") end
    end, reason)
end

function Recorder:close(reason)
    if self.closed then return end
    self:guard(function(s)
        assert(reason == "capacity" or reason == "machine_stop" or reason == "test", "invalid close")
        if s.pending then s.faults = s.faults + 1 end
        s:emit({kind="footer", reason=reason, rows=s.rows, attempts=s.attempts, faults=s.faults,
            last_frame=s.last_frame or -1, captured_prefix_only=true,
            capacity_reached=s.attempts >= s.limit, pending_frame=s.pending ~= nil})
        s.pending, s.closed = nil, true
        if s.close_writer then pcall(s.close_writer) end
    end)
end

function M.new(options)
    local slot = integer(options.slot, 0, 8191)
    local limit = integer(options.limit or 4096, 16, 16384)
    assert(type(options.write) == "function", "explicit diagnostic writer required")
    assert(type(options.session) == "string" and options.session:match("^[a-f0-9]+$") and #options.session == 32,
        "explicit session identity required")
    local s = setmetatable({slot=slot, limit=limit, session=options.session,
        write=options.write, close_writer=options.close_writer, rows=0, attempts=0, faults=0,
        events=0, max_events=limit + 32,
        epoch=0, exchange_ordinal=0, closed=false}, Recorder)
    s:emit({kind="header", limit=limit, raw_status_address=0x9859,
        raw_score_address=0xBDE4, raw_reserves_address=0xBDEC, raw_wave_address=0xBDED})
    return s
end

function M.from_environment(slot)
    local path = os.getenv("ROBOTRON_STARTUP_DIAGNOSTIC_PATH")
    if path == nil or path == "" then
        return setmetatable({closed=true}, Recorder)
    end
    -- The future launcher must create and bind a fresh private actor directory.
    -- Lua fopen is not an atomic exclusive-create primitive; no such claim is made.
    local prior = io.open(path, "rb")
    if prior then prior:close(); error("diagnostic destination already exists") end
    local session = os.getenv("ROBOTRON_STARTUP_DIAGNOSTIC_SESSION")
    local limit = tonumber(os.getenv("ROBOTRON_STARTUP_DIAGNOSTIC_LIMIT") or "4096")
    integer(slot, 0, 8191); integer(limit, 16, 16384)
    assert(type(session) == "string" and session:match("^[a-f0-9]+$") and #session == 32,
        "explicit session identity required")
    local stream = assert(io.open(path, "wb"))
    return M.new({slot=slot, limit=limit, session=session,
        write=function(line)
            assert(stream:write(line))
            return stream:flush() == true
        end,
        close_writer=function() stream:close() end})
end

return M
