-- One isolated, policy-free ROM/input diagnostic. Never admits a game.
local M, Gate = {}, {}
Gate.__index = Gate
local ZERO = string.rep("\0", 32)
local function integer(v, low, high)
    assert(math.type(v) == "integer" and v >= low and v <= high, "integer outside contract")
    return v
end
local function hex(s)
    return (s:gsub(".", function(c) return string.format("%02x", string.byte(c)) end))
end
local function bytes(memory, offset, count)
    local out = {}
    for n=offset,offset+count-1 do out[#out+1]=string.char(integer(memory:read_u8(n),0,255)) end
    return table.concat(out)
end
local function json(row)
    local out, keys = {}, {}
    for k in pairs(row) do keys[#keys+1]=k end
    table.sort(keys)
    for _, k in ipairs(keys) do
        local v = row[k]
        if type(v)=="string" then
            assert(v:match("^[%w_:%-%.]*$"), "unsafe diagnostic string")
            v='"'..v..'"'
        elseif type(v)=="boolean" then v=v and "true" or "false"
        else v=tostring(integer(v,-1,9007199254740991)) end
        out[#out+1]='"'..k..'":'..v
    end
    local line="{"..table.concat(out,",").."}\n"
    assert(#line<=2048,"diagnostic row too large")
    return line
end
function Gate:emit(row)
    assert(not self.closed and self.events<4096,"diagnostic event capacity exceeded")
    self.events=self.events+1
    row.schema,row.slot,row.session,row.connection,row.event="robotron-gated-start-trace-v1",self.slot,self.session,self.connection,self.events
    assert(self.write(json(row))==true,"diagnostic write failed")
end
function Gate:snapshot()
    local m=self.memory
    return {status=integer(m:read_u8(0x9859),0,255),score_hex=hex(bytes(m,0xBDE4,4)),
        reserves=integer(m:read_u8(0xBDEC),0,255),wave=integer(m:read_u8(0xBDED),0,255),
        current_player=integer(m:read_u8(0x983F),0,255),player_count=integer(m:read_u8(0x9840),0,255),
        credit=integer(m:read_u8(0x9851),0,255)}
end
function Gate:observe_write(offset,data,mask)
    self.writes=self.writes+1
    assert(self.writes<=512,"write witness capacity exceeded")
    local state=self.cpu.state
    local curpc=integer(state.CURPC.value,0,65535)
    local instruction=hex(bytes(self.memory,curpc,2))
    local row=self:snapshot()
    row.kind,row.sequence,row.address,row.data,row.mask="ROM_write",self.sequence,offset,data,mask
    row.pc,row.instruction_pc,row.dp,row.a,row.bank_entry=state.PC.value,curpc,state.DP.value,state.A.value,self.bank.entry
    row.instruction_hex,row.last_start,row.last_coin=instruction,self.last_start,self.last_coin
    row.last_apply_ok,row.last_socket_ok,row.nonce=self.last_apply_ok,self.last_socket_ok,hex(self.nonce)
    row.base_page_hex=hex(bytes(self.memory,0x9800,0x61))
    -- This is a distinguished observation, not a certificate: full loaded ROM,
    -- preceding input and initialization still require independent reconciliation.
    if offset==0x9859 and data==0x7f and mask==255 and curpc==0x2751
       and state.DP.value==0x98 and state.A.value==0x7f and instruction=="9759" then
        self.accepted_site_count=self.accepted_site_count+1
        self.accepted_site_sequence=self.sequence
    end
    self:emit(row)
end
function Gate:install()
    assert(not self.installed and not self.closed,"repeat installation")
    assert(self.region.size==0x19000 and self.region.bytewidth==1 and self.region.bitwidth==8,"wrong raw ROM region")
    self.start:set_value(0);self.coin:set_value(0)
    self:emit({kind="header",limit=self.limit,start_sequence=self.start_sequence,start_pulse=3,
        raw_region_size=self.region.size,policy_loaded=false,start_eligibility_changed=false})
    for offset=0,0x18fff,128 do
        self:emit({kind="raw_ROM_chunk",offset=offset,data_hex=hex(bytes(self.region,offset,128))})
    end
    for _,address in ipairs({0x9859,0x9840,0x983F,0xBDEC,0xBDED}) do
        local handle=self.memory:install_write_tap(address,address,"gated_start_"..self.slot.."_"..address,
            function(offset,data,mask)
                if not self.closed and not self.failed then
                    local ok=pcall(self.observe_write,self,offset,data,mask)
                    -- Defer removal/exit to the next frame callback, outside
                    -- the active write tap. Never replace the original write.
                    if not ok then self.failed=true;self.observer_fault=true end
                end
                return nil -- never replace a ROM/RAM write
            end)
        self.handles[#self.handles+1]=assert(handle,"write observer installation failed")
    end
    self.installed=true
end
function Gate:apply_response(raw)
    assert(type(raw)=="string" and #raw==42,"exact42-byte response required")
    local magic,sequence,start,coin,nonce=string.unpack(">c4I4BBc32",raw)
    assert(magic=="RSC1" and sequence==self.sequence,"wrong or stale response")
    integer(start,0,1);integer(coin,0,1)
    local expected_start=(sequence>=self.start_sequence and sequence<self.start_sequence+3) and 1 or 0
    local expected_coin=(sequence>=self.start_sequence-18 and sequence<self.start_sequence-15) and 1 or 0
    assert(start==expected_start and coin==expected_coin,"response differs from fixed input schedule")
    if sequence<self.start_sequence then assert(nonce==ZERO,"premature nonce")
    elseif sequence==self.start_sequence then
        assert(nonce~=ZERO and self.last_start==0 and self.nonce==ZERO,"fresh neutral-to-START authorization required")
        self.nonce=nonce
    else assert(nonce==self.nonce and nonce~=ZERO,"authorization changed or disappeared") end
    -- Failed transport never reaches this function. On a failed setter the
    -- enclosing step releases both controls and exits; no fallback local START.
    self.start:set_value(start);self.coin:set_value(coin)
    self.last_start,self.last_coin,self.last_apply_ok,self.last_socket_ok=start,coin,true,true
    self:emit({kind="input_applied",sequence=sequence,start=start,coin=coin,nonce=hex(nonce),
        response_hex=hex(raw),socket_ok=true,apply_ok=true,debug_bypass=false,held_start_before_response=false})
end
function Gate:step()
    if self.closed then return end
    local ok=pcall(function()
        assert(self.installed and not self.failed and self.sequence<self.limit,"unready or exhausted producer")
        self.sequence=self.sequence+1
        local row=self:snapshot()
        if self.sequence>self.start_sequence and row.wave==1 and row.reserves>0 and row.score_hex=="00000000"
           and self.initialized_sequence<0 then self.initialized_sequence=self.sequence end
        if row.wave==1 and row.reserves>0 and (row.status&1)==0 and self.first_play_sequence<0 then
            self.first_play_sequence=self.sequence
        end
        row.kind,row.sequence="snapshot",self.sequence
        row.nonce,row.accepted_site_count=hex(self.nonce),self.accepted_site_count
        row.accepted_site_sequence,row.initialized_sequence=self.accepted_site_sequence,self.initialized_sequence
        row.first_play_sequence=self.first_play_sequence
        row.last_start,row.last_coin,row.last_apply_ok,row.last_socket_ok=self.last_start,self.last_coin,self.last_apply_ok,self.last_socket_ok
        self:emit(row)
        local request=json(row)
        assert(self.send(string.pack(">I4",#request)..request)==true,"request send failed")
        local response=self.receive(42)
        self:apply_response(response)
        if self.sequence==self.limit then self:close("capacity");self.exit() end
    end)
    if not ok then self:fail("frame_or_transport_failure") end
end
function Gate:close(reason)
    if self.closed then return end
    pcall(function()self.start:set_value(0)end);pcall(function()self.coin:set_value(0)end)
    local remove_failed=false
    for _,handle in ipairs(self.handles) do if not pcall(function()handle:remove()end) then remove_failed=true end end
    self.failed=self.failed or remove_failed
    pcall(self.emit,self,{kind="footer",reason=reason,sequence=self.sequence,failed=self.failed,
        accepted_site_count=self.accepted_site_count,accepted_site_sequence=self.accepted_site_sequence,
        initialized_sequence=self.initialized_sequence,first_play_sequence=self.first_play_sequence,
        real_ROM_start_acceptance_proven=false,start_eligibility_changed=false})
    self.closed=true
end
function Gate:fail(reason)
    if self.closed then return end
    self.failed=true
    pcall(self.emit,self,{kind="fault",reason=reason,sequence=self.sequence})
    self:close(reason);self.exit()
end
function M.new(o)
    integer(o.slot,4096,4127);integer(o.limit,1000,1600);integer(o.start_sequence,700,o.limit-128)
    for _,value in ipairs({o.session,o.connection}) do assert(type(value)=="string" and #value==32 and value:match("^[a-f0-9]+$"),"fixed identity required") end
    return setmetatable({slot=o.slot,session=o.session,connection=o.connection,limit=o.limit,start_sequence=o.start_sequence,
        memory=o.memory,region=o.region,cpu=o.cpu,bank=o.bank,start=o.start,coin=o.coin,
        send=o.send,receive=o.receive,write=o.write,exit=o.exit,handles={},nonce=ZERO,events=0,writes=0,
        sequence=0,last_start=0,last_coin=0,last_apply_ok=false,last_socket_ok=false,
        installed=false,failed=false,closed=false,accepted_site_count=0,accepted_site_sequence=-1,
        initialized_sequence=-1,first_play_sequence=-1},Gate)
end
function M.from_environment()
    local machine=manager.machine
    local function env(k) return assert(os.getenv(k),"missing diagnostic setting "..k) end
    local path=env("ROBOTRON_GATED_TRACE_PATH")
    local file=assert(io.open(path,"a"))
    local sock=emu.file("rw")
    assert(sock:open("socket."..env("ROBOTRON_GATED_TRACE_ADDRESS"))==nil,"isolated socket open failed")
    local ticks,rate=emu.osd_ticks,emu.osd_ticks_per_second()
    assert(type(ticks)=="function" and rate>0,"host timer required")
    local function receive(n)
        local data,started="",ticks()
        while #data<n and (ticks()-started)/rate<3.5 do
            local chunk=sock:read(n-#data)
            if chunk and #chunk>0 then data=data..chunk end
        end
        assert(#data==n,"original response timeout")
        return data
    end
    local function field(names)
        local found=nil
        for _,port in pairs(machine.ioport.ports) do
            for _,name in ipairs(names) do
                local v=port.fields[name]
                if v then assert(found==nil or found==v,"ambiguous input field");found=v end
            end
        end
        return assert(found,"missing required input field")
    end
    local gate=M.new({slot=tonumber(env("ROBOTRON_GATED_TRACE_SLOT")),session=env("ROBOTRON_GATED_TRACE_SESSION"),
        connection=env("ROBOTRON_GATED_TRACE_CONNECTION"),limit=1200,start_sequence=768,
        memory=machine.devices[":maincpu"].spaces["program"],cpu=machine.devices[":maincpu"],
        region=machine.memory.regions[":maincpu"],bank=machine.memory.banks[":mainbank"],
        start=field({"1 Player Start","P1 Start","Start 1"}),coin=field({"Coin 1","P1 Coin","Insert Coin"}),
        write=function(line)local ok=file:write(line);file:flush();return ok~=nil end,
        send=function(data)sock:write(data);return true end,receive=receive,exit=function()machine:exit()end})
    gate:install()
    assert(emu.add_machine_frame_notifier or emu.register_frame,"frame callback unavailable")
    gate.frame_notifier=(emu.add_machine_frame_notifier or emu.register_frame)(function()gate:step()end)
    gate.stop_notifier=(emu.add_machine_stop_notifier or emu.register_stop)(function()
        gate:close("machine_stop");sock:close();file:close()
    end)
    return gate
end
return M
