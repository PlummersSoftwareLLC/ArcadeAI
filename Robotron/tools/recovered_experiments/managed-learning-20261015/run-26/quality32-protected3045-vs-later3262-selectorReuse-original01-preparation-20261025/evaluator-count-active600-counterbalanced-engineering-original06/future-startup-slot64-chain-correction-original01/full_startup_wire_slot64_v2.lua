-- Isolated full-observation startup adapter. Not loaded by the running fleet.
local M, Adapter = {}, {}
Adapter.__index = Adapter
local ZERO=string.rep("\0",32)
local function integer(v,lo,hi)
    assert(math.type(v)=="integer" and v>=lo and v<=hi,"startup integer outside contract")
    return v
end
local function hex(raw)
    return (raw:gsub(".",function(c)return string.format("%02x",string.byte(c))end))
end
local function unhex(value)
    assert(type(value)=="string" and #value%2==0 and value:match("^[a-f0-9]+$"),"bad hex")
    return (value:gsub("..",function(pair)return string.char(tonumber(pair,16))end))
end
local function read_hex(memory,offset,count)
    local out={}
    for address=offset,offset+count-1 do out[#out+1]=string.format("%02x",integer(memory:read_u8(address),0,255))end
    return table.concat(out)
end
local function json(row)
    local keys,out={},{}
    for key in pairs(row)do keys[#keys+1]=key end
    table.sort(keys)
    for _,key in ipairs(keys)do
        local value=row[key]
        if type(value)=="string"then
            assert(value:match("^[%w_:%-%.]*$"),"unsafe trace text");value='"'..value..'"'
        elseif type(value)=="boolean"then value=value and "true"or"false"
        else value=tostring(integer(value,-1,9007199254740991))end
        out[#out+1]='"'..key..'":'..value
    end
    local result="{"..table.concat(out,",").."}\n"
    assert(#result<=2048,"trace row exceeds bound")
    return result
end
function Adapter:emit(row)
    assert(not self.closed and not self.trace_closed and self.events<4096,"trace capacity exceeded")
    self.events=self.events+1
    row.schema,row.slot,row.session,row.connection,row.event=
        "robotron-full-policy-startup-trace-v2",self.slot,self.session,self.connection,self.events
    assert(self.writer(json(row))==true,"startup trace write failed")
end
function Adapter:lifecycle(kind,values)
    assert(not self.lifecycle_closed and self.lifecycle_events<16,"lifecycle capacity exceeded")
    self.lifecycle_events=self.lifecycle_events+1
    local row=values or{}
    row.schema,row.kind,row.slot,row.session,row.connection,row.event,row.sequence=
        "robotron-full-tail-lifecycle-v2",kind,self.slot,self.session,self.connection,
        self.lifecycle_events,self.sequence
    assert(self.lifecycle_writer(json(row))==true,"lifecycle write failed")
end
function Adapter:neutral()
    pcall(function()self.start:set_value(0)end)
    pcall(function()self.coin:set_value(0)end)
end
function Adapter:close_trace(reason)
    if self.trace_closed then return end
    for _,handle in ipairs(self.handles)do
        assert(pcall(function()handle:remove()end),"trace tap removal failed")
    end
    self.handles={}
    self:emit({kind="footer",reason=reason,sequence=self.sequence,
        failed=self.failed,frame_limit=self.limit,gate_sequence=self.gate_sequence,
        setup_sequence=self.setup_sequence,initialized_sequence=self.initialized_sequence,
        first_play_sequence=self.first_play_sequence,latched_sequence=self.latched_sequence,
        machine_exit_requested=self.stop_received})
    assert(self.stream:close(),"startup trace close failed")
    self.trace_closed=true
    self:lifecycle("prefix_closed",{trace_events=self.events,first_play_sequence=self.first_play_sequence,
        initialized_sequence=self.initialized_sequence,latched_sequence=self.latched_sequence,
        failed=self.failed,machine_exit_requested=self.stop_received})
end
function Adapter:close(reason)
    if self.closed then return end
    self:neutral()
    self:close_trace(reason)
    self:lifecycle("closed",{reason=reason,failed=self.failed,stop_received=self.stop_received})
    assert(self.lifecycle_stream:close(),"lifecycle close failed")
    self.lifecycle_closed=true
    self.closed=true
end
function Adapter:fail(reason)
    if self.closed then return end
    self.failed=true
    if not self.trace_closed then pcall(self.emit,self,{kind="fault",reason=reason,sequence=self.sequence})end
    pcall(self.lifecycle,self,"fault",{reason=reason})
    pcall(self.close,self,reason)
    self.closed=true;self:neutral();self.exit()
end
function Adapter:snapshot()
    return {status=self.memory:read_u8(0x9859),score_hex=read_hex(self.memory,0xBDE4,4),
        wave=self.memory:read_u8(0xBDED),reserves=self.memory:read_u8(0xBDEC),
        player_count=self.memory:read_u8(0x9840),current_player=self.memory:read_u8(0x983F),
        credit=self.memory:read_u8(0x9851)}
end
function Adapter:observe_write(address,data,mask)
    self.writes=self.writes+1;assert(self.writes<=512,"write witness capacity exceeded")
    local state=self.cpu.state
    local pc=integer(state.CURPC.value,0,65535)
    local row=self:snapshot()
    row.kind,row.sequence,row.address,row.data,row.mask="ROM_write",self.sequence,address,data,mask
    row.pc,row.instruction_pc,row.dp,row.a,row.bank_entry=state.PC.value,pc,state.DP.value,state.A.value,self.bank.entry
    row.instruction_hex=read_hex(self.memory,pc,2)
    row.last_start,row.last_coin,row.last_apply_ok,row.last_socket_ok=self.last_start,self.last_coin,self.last_apply_ok,self.last_socket_ok
    row.nonce=hex(self.nonce)
    row.base_page_hex=read_hex(self.memory,0x9800,0x61)
    if self.bank.entry==1 and state.DP.value==0x98 and mask==255 then
        if address==0x9840 and data==1 and pc==0x2715 and state.A.value==1 and row.instruction_hex=="9740"then
            assert(self.nonce~=ZERO and self.gate_sequence==-1,"earlier or duplicate accepted START")
            self.gate_sequence=self.sequence
        end
        if address==0x9859 and data==127 and pc==0x2751 and state.A.value==127 and row.instruction_hex=="9759"then
            assert(self.gate_sequence>=0 and self.setup_sequence==-1,"setup without unique accepted START")
            self.setup_sequence=self.sequence
        end
    end
    self:emit(row)
end
function Adapter:install()
    assert(not self.installed and self.region.size==0x19000 and self.region.bytewidth==1
        and self.region.bitwidth==8,"fresh exact CPU ROM region required")
    self:neutral()
    self:emit({kind="header",frame_limit=self.limit,raw_region_size=self.region.size,
        authorization="fixed_server_admission",full_observation_envelope=true,continues_after_prefix=true})
    for offset=0,0x18fff,128 do
        self:emit({kind="raw_ROM_chunk",offset=offset,data_hex=read_hex(self.region,offset,128)})
    end
    for _,address in ipairs({0x9859,0x9840,0x983F,0xBDEC,0xBDED})do
        self.handles[#self.handles+1]=assert(self.memory:install_write_tap(address,address,
            "full_startup_"..self.slot.."_"..address,function(offset,data,mask)
                if not self.closed and not self.trace_closed and not self.failed then
                    if not pcall(self.observe_write,self,offset,data,mask)then self.failed=true end
                end
                return nil -- preserve the CPU's original write
            end))
    end
    self.installed=true
end
function Adapter:connected(sock)
    assert(self.installed and not self.connected_once and not self.failed,"startup reconnect forbidden")
    self.connected_once=true
    sock:write(string.pack(">c4c16c16I2","RSG2",unhex(self.session),unhex(self.connection),self.slot))
end
function Adapter:begin(sequence)
    assert(not self.failed and not self.closed and self.installed and sequence==self.sequence+1
        and sequence<=0xffffffff,"invalid original frame sequence")
    self.sequence=sequence;self.request_sent=false;self.response_ready=false;self.input_recorded=false
    local row=self:snapshot()
    if self.setup_sequence>=0 and row.wave==1 and row.reserves==2 and row.score_hex=="00000000"
        and row.player_count==1 and row.current_player==1 and self.initialized_sequence==-1 then
        self.initialized_sequence=sequence
    end
    if row.wave==1 and row.reserves>0 and (row.status&1)==0 and self.first_play_sequence==-1 then
        self.first_play_sequence=sequence
        if self.mode=="latched"then self.mode="legacy"end
    end
    row.kind,row.sequence="snapshot",sequence
    row.nonce,row.first_play_sequence=hex(self.nonce),self.first_play_sequence
    row.last_start,row.last_coin,row.last_apply_ok,row.last_socket_ok=self.last_start,self.last_coin,self.last_apply_ok,self.last_socket_ok
    row.gate_sequence,row.setup_sequence,row.initialized_sequence=self.gate_sequence,self.setup_sequence,self.initialized_sequence
    row.mode=self.mode
    if self.trace_closed then
        assert(sequence>self.limit and self.mode=="legacy" and self.first_play_sequence>0,
            "continuation without certified first play")
        row.event=0
    else self:emit(row)end
    self.pending=row
end
function Adapter:plan(sequence,start,coin)
    assert(sequence==self.sequence and self.pending,"plan without snapshot")
    self.planned_start,self.planned_coin=integer(start,0,1),integer(coin,0,1)
    if self.mode=="legacy"then return start,coin end
    return 0,0 -- actual first START/coin await an original matching response
end
function Adapter:envelope(payload,sequence)
    assert(sequence==self.sequence and not self.request_sent and self.pending,"duplicate request")
    assert(type(payload)=="string" and #payload==7597 and string.unpack(">I2",payload)==1890
        and string.unpack(">I4",payload,#payload-3)==0,"exact preview-free original v2 payload required")
    local p=self.pending
    local metadata={schema="robotron-full-startup-envelope-v2",slot=self.slot,session=self.session,
        connection=self.connection,sequence=sequence,event=p.event,status=p.status,score_hex=p.score_hex,
        wave=p.wave,reserves=p.reserves,current_player=p.current_player,player_count=p.player_count,credit=p.credit,
        planned_start=self.planned_start,planned_coin=self.planned_coin,mode=self.mode,
        last_start=self.last_start,last_coin=self.last_coin,last_apply_ok=self.last_apply_ok,
        last_socket_ok=self.last_socket_ok,nonce=hex(self.nonce),first_play_sequence=self.first_play_sequence}
    local raw=json(metadata)
    self.request_sent=true
    return string.pack(">c4I4I4I4","RSG2",sequence,#payload,#raw)..payload..raw
end
function Adapter:decode_response(raw,sequence)
    assert(sequence==self.sequence and self.request_sent and not self.response_ready,"unexpected response")
    assert(type(raw)=="string" and #raw==48,"exact48-byte response required")
    local magic,seq,flags,coin,nonce,action=string.unpack(">c4I4BBc32c6",raw)
    assert(magic=="RSP2" and seq==sequence and flags<=7 and coin<=1,"foreign or stale response")
    local move,fire,source,advanced,level,difficulty=string.unpack(">bbBBBB",action)
    assert(move>=-1 and move<=7 and fire>=-1 and fire<=7 and (source==0 or source==4)
        and advanced==0 and level==1 and difficulty==0x85,"actual forced-eval action context differs")
    local start,latch=flags&1,(flags&2)~=0
    local stop=(flags&4)~=0
    assert(not stop or(self.trace_closed and sequence>self.limit and self.mode=="legacy" and latch),
        "shutdown before certified continuation")
    assert(start==0 or self.planned_start==1,"unsolicited START")
    assert(coin==0 or self.planned_coin==1,"unsolicited coin")
    if self.nonce==ZERO then
        if start==1 then
            assert(nonce~=ZERO and not latch and self.last_start==0,"fresh first authorization required")
            self.nonce,self.mode,self.authorized_sequence=nonce,"authorized",sequence
        else assert(nonce==ZERO and not latch,"premature or foreign nonce")end
    else
        assert(nonce==self.nonce,"startup nonce changed")
        if self.mode=="authorized" and start==1 then
            assert(sequence<self.authorized_sequence+3,"startup pulse extended")
        end
        if latch and self.mode=="authorized"then
            local row=self.pending
            assert(self.initialized_sequence>0 and self.initialized_sequence<=sequence
                and self.first_play_sequence==-1 and row.wave==1 and row.reserves==2
                and row.score_hex=="00000000" and row.player_count==1 and row.current_player==1
                and (row.status&1)~=0 and start==0,"latch outside accepted before-play initialization")
            self.latched_sequence=sequence
            self.mode="latched"
        end
        if self.mode=="latched"or self.mode=="legacy"then assert(latch,"startup latch disappeared")end
        if self.mode=="latched"then assert(start==0 and coin==0,"input during initialized countdown")end
    end
    self.allowed_start,self.allowed_coin,self.response_hex=start,coin,hex(raw)
    self.stop_received=stop
    if stop then self:lifecycle("stop_response",{response_hex=self.response_hex,nonce=hex(self.nonce)})end
    self.response_ready=true
    return action
end
function Adapter:inputs(socket_ok,debug_bypass,forced_action)
    assert(socket_ok==true and debug_bypass==false and forced_action==false and self.response_ready
        and not self.failed,"failed or bypassed startup response")
    if self.mode=="legacy"then
        assert(self.allowed_start==self.planned_start and self.allowed_coin==self.planned_coin,
            "ordinary post-start inputs changed")
    end
    return self.allowed_start,self.allowed_coin
end
function Adapter:applied(start,coin,socket_ok,apply_ok)
    assert(self.response_ready and not self.input_recorded,"unexpected input application")
    assert(socket_ok==true and apply_ok==true and start==self.allowed_start and coin==self.allowed_coin,
        "actual input application failed")
    self.last_start,self.last_coin,self.last_apply_ok,self.last_socket_ok=start,coin,true,true
    local row={kind="input_applied",sequence=self.sequence,start=start,coin=coin,
        nonce=hex(self.nonce),response_hex=self.response_hex,socket_ok=true,apply_ok=true,
        debug_bypass=false,held_start_before_response=false}
    if not self.trace_closed then self:emit(row)
    elseif self.stop_received then
        row.kind=nil;row.sequence=nil
        self:lifecycle("stop_applied",row)
    end
    self.input_recorded=true
end
function Adapter:finish(sequence)
    assert(sequence==self.sequence and self.input_recorded,"unfinished original frame")
    if sequence==self.limit then
        assert(self.mode=="legacy" and self.nonce~=ZERO and self.initialized_sequence>0
            and self.first_play_sequence>self.initialized_sequence,"no certified play within prefix bound")
        self:close_trace("prefix_complete") -- close only provenance, never the game
    end
    if self.stop_received then
        assert(self.trace_closed and sequence>self.limit and not self.failed,"invalid controlled shutdown")
        self:lifecycle("exit_requested",{response_hex=self.response_hex,apply_ok=self.last_apply_ok})
        self:close("drained_shutdown");self.exit()
    end
end
function Adapter:protect(method,...)
    local values={pcall(self[method],self,...)}
    if not values[1]then self:fail(method.."_failed");error("FULL_STARTUP_ADAPTER_FAILURE:"..method)end
    return table.unpack(values,2)
end
function M.attach(controls,options)
    assert(options.eval_mode==1 and options.debug_bypass_frames==0 and options.force_action_frames==0,
        "explicit evaluation without debug overrides required")
    local function env(key)local value=os.getenv(key);assert(value,"missing "..key);return value end
    local machine=manager.machine
    local stream=assert(io.open(env("ROBOTRON_FULL_STARTUP_TRACE"),"a"))
    local lifecycle_stream=assert(io.open(env("ROBOTRON_FULL_TAIL_LIFECYCLE"),"a"))
    local a=setmetatable({slot=tonumber(env("ROBOTRON_FULL_STARTUP_SLOT")),
        session=env("ROBOTRON_FULL_STARTUP_SESSION"),connection=env("ROBOTRON_FULL_STARTUP_CONNECTION"),
        cpu=machine.devices[":maincpu"],memory=machine.devices[":maincpu"].spaces["program"],
        bank=machine.memory.banks[":mainbank"],region=machine.memory.regions[":maincpu"],
        start=assert(controls.p1_start),coin=assert(controls.coin_1),
        writer=function(line)local ok=stream:write(line);stream:flush();return ok~=nil end,
        lifecycle_writer=function(line)local ok=lifecycle_stream:write(line);lifecycle_stream:flush();return ok~=nil end,
        lifecycle_stream=lifecycle_stream,lifecycle_events=0,lifecycle_closed=false,
        exit=function()machine:exit()end,stream=stream,limit=1200,sequence=0,events=0,writes=0,
        handles={},nonce=ZERO,mode="gated",last_start=0,last_coin=0,last_apply_ok=false,last_socket_ok=false,
        gate_sequence=-1,setup_sequence=-1,initialized_sequence=-1,latched_sequence=-1,first_play_sequence=-1,
        installed=false,failed=false,closed=false,trace_closed=false,stop_received=false,connected_once=false},Adapter)
    integer(a.slot,4096,4159)
    for _,v in ipairs({a.session,a.connection})do
        assert(#v==32 and v:match("^[a-f0-9]+$")and v~=string.rep("0",32),"fresh bound identity required")
    end
    a:protect("install")
    a:lifecycle("header",{trace_frame_limit=1200,continuation_enabled=true})
    return a
end
return M
