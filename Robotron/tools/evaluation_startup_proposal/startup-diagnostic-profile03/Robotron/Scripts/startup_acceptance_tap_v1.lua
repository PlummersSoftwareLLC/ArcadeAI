-- Isolated raw provenance component. No memory/register/input writes or admission.
local M = {}
local Tap = {}
Tap.__index = Tap
local LIMIT, WRITES, MAX_EVENTS = 4096, 512, 4620

local function integer(value, low, high)
    assert(math.type(value) == "integer" and value >= low and value <= high, "diagnostic integer out of bounds")
    return value
end

local function scalar(value)
    if type(value) == "boolean" then return value and "true" or "false" end
    if math.type(value) == "integer" then return tostring(value) end
    assert(type(value) == "string" and value:match("^[%w_:%-%.]*$"), "unsafe diagnostic text")
    return '"' .. value .. '"'
end

local function encode(row)
    local keys, parts = {}, {}
    for key in pairs(row) do keys[#keys + 1] = key end
    table.sort(keys)
    for _, key in ipairs(keys) do parts[#parts + 1] = scalar(key) .. ":" .. scalar(row[key]) end
    local line = "{" .. table.concat(parts, ",") .. "}\n"
    assert(#line <= 2048, "diagnostic record exceeds bound")
    return line
end

local function hex_read(object, start, length)
    assert(length <= 245, "bounded byte witness required")
    local bytes = {}
    for addr = start, start + length - 1 do
        bytes[#bytes + 1] = string.format("%02x", integer(object:read_u8(addr), 0, 255))
    end
    return table.concat(bytes)
end

function Tap:emit(row)
    if self.closed or self.logging_failed then return false end
    if self.events >= MAX_EVENTS then
        self.failed, self.logging_failed, self.active = true, true, false
        self.faults = self.faults + 1
        return false
    end
    self.events = self.events + 1
    row.schema, row.slot, row.session, row.sequence = "robotron-ROM-start-tap-v1", self.slot, self.session, self.events
    local ok, result = pcall(function() return self.write(encode(row)) end)
    if not ok or result ~= true then
        self.failed, self.logging_failed, self.active = true, true, false
        self.faults = self.faults + 1
        return false
    end
    return true
end

function Tap:fail(reason)
    if not self.failed then
        self.failed, self.active = true, false
        self.faults = self.faults + 1
        self:emit({kind="fault", reason=reason, faults=self.faults})
    end
end

function Tap:state()
    local s = self.cpu.state
    return integer(s.PC.value, 0, 65535), integer(s.CURPC.value, 0, 65535),
        integer(s.DP.value, 0, 255), integer(s.A.value, 0, 255), integer(self.bank.entry, 0, 1)
end

function Tap:record_write(offset, data, mask)
    assert(offset == 0x9859 and integer(mask, 0, 255) == 255, "unexpected write tap access")
    integer(data, 0, 255)
    self.writes = self.writes + 1
    assert(self.writes <= WRITES, "STATUS write capacity exceeded")
    local pc, curpc, dp, a, bank = self:state()
    local last = self.last_input
    local row = {kind="status_write", write_ordinal=self.writes, address=offset, data=data, mask=mask,
        previous_status=integer(self.space:read_u8(0x9859), 0, 255), pc=pc, instruction_pc=curpc, dp=dp, a=a,
        bank_entry=bank, instruction_hex=hex_read(self.space, curpc, 2),
        last_input_frame=last.frame, epoch=last.epoch, exchange=last.exchange,
        last_start=last.start, last_coin=last.coin, last_apply_ok=last.apply_ok, last_socket_ok=last.socket_ok,
        inputs_observed=self.inputs, score_hex=hex_read(self.space, 0xBDE4, 4),
        raw_reserves=integer(self.space:read_u8(0xBDEC), 0, 255), raw_wave=integer(self.space:read_u8(0xBDED), 0, 255),
        credit=integer(self.space:read_u8(0x9851), 0, 255), current_player=integer(self.space:read_u8(0x983F), 0, 255),
        player_count=integer(self.space:read_u8(0x9840), 0, 255)}
    assert(self:emit(row), "STATUS witness output failed")
end

function Tap:install()
    if self.disabled then return false end
    if self.install_attempted then self:fail("repeat_install"); return false end
    self.install_attempted = true
    local ok = pcall(function()
        assert(not self.closed and not self.failed and self.inputs == 0, "tap must precede owned input")
        assert(self.cpu.tag == ":maincpu" and self.bank.tag == ":mainbank", "exact CPU and bank required")
        assert(self.space.data_width == 8 and self.space.shift == 0 and self.space.address_mask == 65535,
            "byte-addressed 6809 program space required")
        assert(self.region.tag == ":maincpu" and self.region.size == 0x19000
            and self.region.bytewidth == 1 and self.region.bitwidth == 8, "exact raw ROM region required")
        local code = hex_read(self.region, 0x126C0, 245)
        local vector = hex_read(self.region, 0xD000, 3)
        local init = hex_read(self.region, 0xD106, 15)
        assert(vector == "7ed106" and init == "1aff10cebf7086981f8b8601b7c900", "ROM initialization bytes differ")
        assert(hex_read(self.region, 0x126CC, 3) == "7e26fc"
            and hex_read(self.region, 0x126FC, 25) == "8601108ec3b30d592af3f6cc05c40fc10926029751915122e4",
            "ROM first-start gate bytes differ")
        local pc, curpc, dp, a, bank = self:state()
        assert(self:emit({kind="header", input_limit=LIMIT, write_limit=WRITES, status_address=0x9859,
            cpu_tag=self.cpu.tag, bank_tag=self.bank.tag, region_tag=self.region.tag, region_size=self.region.size,
            region_bytewidth=1, region_bitwidth=8, span_region_offset=0x126C0, span_bytes=245, ROM_span_hex=code,
            OS_vector_hex=vector, initialization_hex=init, initial_pc=pc, initial_instruction_pc=curpc,
            initial_dp=dp, initial_a=a, initial_bank_entry=bank, inputs_observed=0,
            raw_provenance_only=true, full_ROM_image_verified=false, start_eligibility_changed=false}),
            "header publication failed")
        -- No callback return value escapes. Even a failed observer supplies nil
        -- to MAME's optional-data replacement API, preserving the original byte.
        self.callback = function(offset, data, mask)
            if self.active and not self.closed and not self.failed then
                local observed = pcall(self.record_write, self, offset, data, mask)
                if not observed then self:fail("write_observer_error") end
            end
            return nil
        end
        self.handle = assert(self.space:install_write_tap(0x9859, 0x9859,
            "robotron_start_provenance_" .. self.slot .. "_" .. self.session, self.callback))
        self.active = true
        assert(self:emit({kind="installed", inputs_observed=0, frame=-1, raw_provenance_only=true}), "install record failed")
    end)
    if not ok then self:fail("installation_error") end
    return ok and not self.failed
end

function Tap:input(frame, epoch, exchange, start, coin, apply_ok, socket_ok)
    if self.disabled then return true end
    if self.closed or self.failed then return false end
    if self.inputs >= LIMIT then return self:close("capacity") end
    local ok = pcall(function()
        assert(self.active and self.install_attempted, "input before tap installation")
        integer(frame, 0, LIMIT - 1); integer(epoch, 0, 1); integer(exchange, 0, LIMIT)
        integer(start, 0, 1); integer(coin, 0, 1)
        assert(type(apply_ok) == "boolean" and type(socket_ok) == "boolean", "explicit original input result required")
        assert(frame == self.inputs and epoch >= self.last_input.epoch
            and exchange >= self.last_input.exchange and (epoch ~= 0 or exchange == 0), "input context regressed")
        self.inputs = self.inputs + 1
        self.last_input = {frame=frame, epoch=epoch, exchange=exchange, start=start, coin=coin,
            apply_ok=apply_ok, socket_ok=socket_ok}
        assert(self:emit({kind="input", frame=frame, epoch=epoch, exchange=exchange, start=start, coin=coin,
            apply_ok=apply_ok, socket_ok=socket_ok, inputs_observed=self.inputs}), "input record failed")
    end)
    if not ok then self:fail("input_context_error") end
    return ok and not self.failed
end

function Tap:close(reason)
    if self.disabled then return true end
    if self.closed then return not self.failed end
    if reason ~= "capacity" and reason ~= "machine_stop" and reason ~= "test" then self:fail("close_reason_error") end
    self.active = false
    if self.handle and not self.remove_attempted then
        self.remove_attempted = true
        local ok = pcall(function() self.handle:remove() end)
        if not ok then self:fail("tap_remove_error") end
    end
    self:emit({kind="footer", reason=reason, inputs_observed=self.inputs, writes_observed=self.writes,
        faults=self.faults, failed=self.failed, logging_failed=self.logging_failed,
        last_input_frame=self.last_input.frame, capacity_reached=self.inputs == LIMIT,
        raw_provenance_only=true, real_ROM_start_acceptance_proven=false, start_eligibility_changed=false})
    self.closed = true
    return not self.failed
end

function Tap:status()
    return {enabled=not self.disabled, active=self.active, closed=self.closed, failed=self.failed,
        logging_failed=self.logging_failed, faults=self.faults, inputs=self.inputs, writes=self.writes,
        events=self.events, remove_attempted=self.remove_attempted or false}
end

function M.new(options)
    integer(options.slot, 4096, 4127)
    assert(type(options.session) == "string" and #options.session == 32
        and options.session:match("^[a-f0-9]+$"), "bound private session required")
    assert(type(options.write) == "function", "explicit bounded writer required")
    return setmetatable({slot=options.slot, session=options.session, write=options.write,
        cpu=options.cpu, space=options.space, bank=options.bank, region=options.region,
        active=false, closed=false, failed=false, logging_failed=false, events=0, faults=0, inputs=0, writes=0,
        last_input={frame=-1, epoch=0, exchange=0, start=0, coin=0, apply_ok=false, socket_ok=false}}, Tap)
end

function M.disabled()
    return setmetatable({disabled=true, active=false, closed=true, failed=false, logging_failed=false,
        faults=0, inputs=0, writes=0, events=0}, Tap)
end

return M
