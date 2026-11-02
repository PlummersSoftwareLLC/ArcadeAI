-- Host socket wait configuration.  Keep the default and unsupported platforms
-- on the existing busy-poll path.  The native callback never touches Lua state
-- or advances emulation; it only sleeps the host thread after an empty read.
local socket_wait_raw = os.getenv("ROBOTRON_SOCKET_WAIT_US") or "0"
local socket_wait_us = socket_wait_raw:match("^%d+$") and math.tointeger(tonumber(socket_wait_raw)) or 0
socket_wait_us = math.max(0, math.min(10000, socket_wait_us or 0))
local socket_idle_wait = nil
local socket_time_now = os.clock
local socket_wait_description = "busy polling"
if socket_wait_us > 0 then
    local helper_path = os.getenv("ROBOTRON_HOST_WAIT_LIB")
    local clock_ready = type(emu) == "table" and type(emu.osd_ticks) == "function"
        and type(emu.osd_ticks_per_second) == "function"
    local rate_ok, tick_rate = false, nil
    if clock_ready then
        rate_ok, tick_rate = pcall(emu.osd_ticks_per_second)
        clock_ready = rate_ok and type(tick_rate) == "number" and tick_rate > 0
            and tick_rate < math.huge
        if clock_ready then
            local ticks_ok, ticks = pcall(emu.osd_ticks)
            clock_ready = ticks_ok and type(ticks) == "number" and ticks == ticks
                and ticks ~= math.huge and ticks ~= -math.huge
        end
    end
    if os.getenv("ROBOTRON_SOCKET_WAIT_ACTIVE") == "select-v1" then
        -- Only the successfully loaded, opted-in preload shim sets this flag.
        -- Its read blocks in host time, so CPU-time deadlines are unsafe here.
        assert(clock_ready, "Robotron socket readiness wait requires a host wall clock")
        local host_ticks = emu.osd_ticks
        socket_time_now = function() return host_ticks() / tick_rate end
        socket_wait_description = string.format("socket readiness wait %dus, host wall timers", socket_wait_us)
    else
        local load_ok, sleep_fn = false, nil
        if clock_ready and helper_path and helper_path ~= "" and type(package) == "table"
                and type(package.loadlib) == "function" then
            load_ok, sleep_fn = pcall(package.loadlib, helper_path, "robotron_socket_wait")
        end
        if load_ok and type(sleep_fn) == "function" then
            local host_ticks = emu.osd_ticks
            socket_time_now = function() return host_ticks() / tick_rate end
            socket_idle_wait = sleep_fn
            socket_wait_description = string.format("host sleep %dus, host wall timers", socket_wait_us)
        else
            print("Robotron socket host wait unavailable; using busy polling")
        end
    end
end
local function process_frame_via_socket(frame_payload, frame_idx)
    if not current_socket then
        trace_log(frame_idx, "socket_open_needed", "no active socket")
        if not open_socket() then
            trace_log(frame_idx, "socket_open_failed", "open_socket() returned false")
            return -1, -1, false
        end
        trace_log(frame_idx, "socket_open_ok", "socket ready")
    end

    local write_ok, write_err = pcall(function()
        trace_log(frame_idx, "socket_write_begin", "payload_bytes=" .. tostring(#frame_payload))
        local length_header = string.pack(">I4", #frame_payload)
        current_socket:write(length_header .. frame_payload)
    end)

    if not write_ok then
        trace_log(frame_idx, "socket_write_error", tostring(write_err))
        print("Socket write error: " .. tostring(write_err))
        close_socket()
        return -1, -1, false
    end
    trace_log(frame_idx, "socket_write_ok", "payload sent")

    local read_ok, read_result = pcall(function()
        trace_log(frame_idx, "socket_read_begin", "waiting for 3-byte or 5-byte action")
        local started = socket_time_now()
        local legacy_buffer_ready_at = nil

        local v5_buffer_ready_at = nil
        while (socket_time_now() - started) < SOCKET_READ_TIMEOUT_S do
            if #ACTION_RX_BUFFER >= 6 then
                -- v2 action: 5 bytes + GA1 difficulty byte.
                local action_bytes = string.sub(ACTION_RX_BUFFER, 1, 6)
                ACTION_RX_BUFFER = string.sub(ACTION_RX_BUFFER, 7)
                local move_dir, fire_dir, source, start_advanced, start_level_min, difficulty = string.unpack("bbBBBB", action_bytes)
                START_ADVANCED = (start_advanced or 0) ~= 0
                START_LEVEL_MIN = math.max(1, math.min(81, math.floor(start_level_min or 1)))
                -- High bit = server says we're an eval client (wave-cap exempt).
                local diff_raw = math.floor(difficulty or 5)
                SERVER_IS_EVAL = (diff_raw & 0x80) ~= 0
                SERVER_DIFFICULTY = math.max(1, math.min(10, diff_raw & 0x7F))
                trace_log(
                    frame_idx,
                    "socket_read_ok",
                    string.format(
                        "move=%d fire=%d src=%d adv=%d level=%d diff=%d",
                        move_dir, fire_dir, source, start_advanced or 0, START_LEVEL_MIN, SERVER_DIFFICULTY
                    )
                )
                return {move_dir, fire_dir, source}
            end

            if #ACTION_RX_BUFFER == 5 then
                -- 5-byte action (server hasn't seen our v2 header yet, or is
                -- an old server).  Same settle-wait pattern as the 3-byte
                -- legacy case so a split 6-byte packet isn't misparsed.
                if v5_buffer_ready_at == nil then
                    v5_buffer_ready_at = socket_time_now() + 0.003
                elseif socket_time_now() >= v5_buffer_ready_at then
                    -- A host sleep can straddle the settle deadline while the
                    -- sixth byte arrives. Probe once before declaring legacy.
                    local tail = current_socket:read(1)
                    if tail and #tail > 0 then
                        ACTION_RX_BUFFER = ACTION_RX_BUFFER .. tail
                    else
                        local action_bytes = ACTION_RX_BUFFER
                        ACTION_RX_BUFFER = ""
                        local move_dir, fire_dir, source, start_advanced, start_level_min = string.unpack("bbBBB", action_bytes)
                        START_ADVANCED = (start_advanced or 0) ~= 0
                        START_LEVEL_MIN = math.max(1, math.min(81, math.floor(start_level_min or 1)))
                        trace_log(
                            frame_idx,
                            "socket_read_ok",
                            string.format(
                                "move=%d fire=%d src=%d adv=%d level=%d",
                                move_dir, fire_dir, source, start_advanced or 0, START_LEVEL_MIN
                            )
                        )
                        return {move_dir, fire_dir, source}
                    end
                end
            else
                v5_buffer_ready_at = nil
            end

            if #ACTION_RX_BUFFER == 3 then
                if legacy_buffer_ready_at == nil then
                    legacy_buffer_ready_at = socket_time_now() + 0.003
                elseif socket_time_now() >= legacy_buffer_ready_at then
                    local tail = current_socket:read(3)
                    if tail and #tail > 0 then
                        ACTION_RX_BUFFER = ACTION_RX_BUFFER .. tail
                    else
                        local action_bytes = ACTION_RX_BUFFER
                        ACTION_RX_BUFFER = ""
                        local move_dir, fire_dir, source = string.unpack("bbB", action_bytes)
                        trace_log(frame_idx, "socket_read_ok_legacy", string.format("move=%d fire=%d src=%d", move_dir, fire_dir, source))
                        return {move_dir, fire_dir, source}
                    end
                end
            else
                legacy_buffer_ready_at = nil
            end

            if #ACTION_RX_BUFFER < 6 then
                local chunk = current_socket:read(6 - #ACTION_RX_BUFFER)
                if chunk and #chunk > 0 then
                    ACTION_RX_BUFFER = ACTION_RX_BUFFER .. chunk
                elseif socket_idle_wait then
                    socket_idle_wait()
                end
            end
        end

        ACTION_RX_BUFFER = ""
        trace_log(frame_idx, "socket_read_timeout", "using neutral action")
        return {-1, -1}
    end)

    if not read_ok then
        trace_log(frame_idx, "socket_read_error", tostring(read_result))
        print("Socket read error: " .. tostring(read_result))
        close_socket()
        return -1, -1, false
    end

    local move_dir, fire_dir, source = unpack(read_result)
    local source_u8 = (source or 0) & 0xFF
    set_preview_stream_enabled((source_u8 & 0x40) ~= 0)
    -- Source byte bits:
    --   low nibble = action source
    --   0x40 = preview enabled
    --   0x80 = preview HUD overlay enabled
    PREVIEW_HUD_ENABLED = (source_u8 & 0x80) ~= 0
    last_action_source = source_u8 & 0x0F
    return move_dir or -1, fire_dir or -1, true
end

function register_frame_callback(cb)
    if emu.add_machine_frame_notifier then
        return emu.add_machine_frame_notifier(cb)
    end
    if emu.register_frame then
        return emu.register_frame(cb)
    end
    error("No supported frame callback API found (expected emu.add_machine_frame_notifier or emu.register_frame)")
end


unpack = table.unpack
SOCKET_READ_TIMEOUT_S = 0.03
ACTION_RX_BUFFER = ""
trace_log = function() end
set_preview_stream_enabled = function() end
close_socket = function() if current_socket then current_socket:close(); current_socket = nil end end
open_socket = function() error("unexpected test reconnect") end
local tested = false
global_callback_ref = register_frame_callback(function()
    if tested then return end
    tested = true
    local ok, failure = pcall(function()
        local requested = tonumber(os.getenv("ROBOTRON_SOCKET_WAIT_US"))
        if requested > 0 then
            assert(os.getenv("ROBOTRON_SOCKET_WAIT_ACTIVE") == "select-v1", "preload marker missing")
            assert(string.find(socket_wait_description, "readiness wait", 1, true))
        else
            assert(os.getenv("ROBOTRON_SOCKET_WAIT_ACTIVE") == nil, "disabled preload advertised active")
        end
        current_socket = emu.file("rw")
        assert(current_socket:open("socket.127.0.0.1:" .. os.getenv("ROBOTRON_SOCKET_WAIT_PORT")) == nil)
        current_socket:write(string.pack(">H", 0))
        local machine_before = emu.time()
        local tick_rate = emu.osd_ticks_per_second()
        local wall_before, cpu_before = emu.osd_ticks(), os.clock()
        local kinds = {"full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","full","split","split","legacy","legacy","timeout"}
        for index, kind in ipairs(kinds) do
            SERVER_DIFFICULTY = nil
            local move, fire, exchanged = process_frame_via_socket("probe-" .. tostring(index), index)
            assert(exchanged, "exchange failed at " .. tostring(index))
            assert(emu.time() == machine_before, "emulation advanced inside frame callback")
            if kind == "timeout" then
                assert(move == -1 and fire == -1 and #ACTION_RX_BUFFER == 0)
            else
                assert(move == index % 8 and fire == (index + 3) % 8,
                    "action mismatch at " .. tostring(index))
                if kind ~= "legacy" then assert(SERVER_DIFFICULTY == 5, "modern tail lost") end
            end
        end
        local wall, cpu = (emu.osd_ticks() - wall_before) / tick_rate, os.clock() - cpu_before
        local status = "packets_verified"
        local result = string.format('{"status":%q,"backend":"select-v1","lua_version":%q,"wait_us":%d,"tick_rate":%.0f,"calls":%d,"wall_s":%.9f,"process_cpu_s":%.9f,"machine_time_start_s":%.9f,"machine_time_end_s":%.9f,"frame_callback":"register_frame_callback","modern_packets":52,"legacy_packets":2,"partial_timeouts":1}',
            status, _VERSION, tonumber(os.getenv("ROBOTRON_SOCKET_WAIT_US")), emu.osd_ticks_per_second(),
            #kinds, wall, cpu, machine_before, emu.time())
        local f = assert(io.open(os.getenv("ROBOTRON_WAIT_SMOKE_OUTPUT"), "w"))
        f:write(result .. "\n"); f:close(); print("ROBOTRON_SELECT_WAIT_SMOKE " .. result)
    end)
    if not ok then
        local result = string.format('{"status":"FAILED","error":%q}', tostring(failure))
        local f = assert(io.open(os.getenv("ROBOTRON_WAIT_SMOKE_OUTPUT"), "w"))
        f:write(result .. "\n"); f:close(); print("ROBOTRON_SELECT_WAIT_SMOKE " .. result)
    end
    close_socket()
    manager.machine:exit()
end)
