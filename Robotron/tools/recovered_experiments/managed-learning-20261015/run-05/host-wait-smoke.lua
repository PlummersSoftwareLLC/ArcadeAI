
print("HOSTWAIT_DIAG", _VERSION, type(emu), type(emu.osd_ticks), type(emu.osd_ticks_per_second), type(package.loadlib))
print("HOSTWAIT_RATE", pcall(emu.osd_ticks_per_second))
print("HOSTWAIT_TICKS", pcall(emu.osd_ticks))
print("HOSTWAIT_LOAD", pcall(package.loadlib, os.getenv("ROBOTRON_HOST_WAIT_LIB"), "robotron_socket_wait"))
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
    local load_ok, sleep_fn = false, nil
    if clock_ready and helper_path and helper_path ~= "" and type(package) == "table"
            and type(package.loadlib) == "function" then
        load_ok, sleep_fn = pcall(package.loadlib, helper_path, "robotron_socket_wait")
    end
    if load_ok and type(sleep_fn) == "function" then
        local host_ticks = emu.osd_ticks
        socket_time_now = function() return host_ticks() / tick_rate end
        socket_idle_wait = sleep_fn
        socket_wait_description = string.format("host sleep %dus, monotonic wall timers", socket_wait_us)
    else
        print("Robotron socket host wait unavailable; using busy polling")
    end
end

local done = false
local function smoke_once()
    if done then return end
    done = true
    local output = assert(os.getenv("ROBOTRON_HOST_WAIT_SMOKE_OUTPUT"))
    local ok, failure = pcall(function()
        assert(type(emu) == "table" and type(package.loadlib) == "function")
        assert(type(socket_idle_wait) == "function", "native helper did not load")
        local count = 200
        local duration_us = tonumber(os.getenv("ROBOTRON_SOCKET_WAIT_US"))
        if duration_us == 100 then count = 1000 end
        assert(select("#", socket_idle_wait()) == 0, "C helper returned Lua values")
        local machine_before = emu.time()
        local host_before, cpu_before = socket_time_now(), os.clock()
        for index = 1, count do socket_idle_wait() end
        local wall, cpu = socket_time_now() - host_before, os.clock() - cpu_before
        local machine_after = emu.time()
        assert(machine_after == machine_before, "emulated time advanced while sleeping")
        assert(wall >= count * duration_us / 1000000 * 0.95, "native sleep did not wait")
        assert(cpu < wall * 0.35, "sleep consumed excessive process CPU")
        local result = string.format(
            '{"status":"verified","lua_version":%q,"emu_type":%q,"tick_rate":%.0f,"package_loadlib":"function","native_callback":"function","duration_us":%d,"calls":%d,"wall_s":%.9f,"process_cpu_s":%.9f,"machine_time_start_s":%.9f,"machine_time_end_s":%.9f,"frame_callback":"register_frame_done","description":%q}',
            _VERSION, type(emu), emu.osd_ticks_per_second(), duration_us, count,
            wall, cpu, machine_before, machine_after, socket_wait_description)
        local stream = assert(io.open(output, "w")); stream:write(result .. "\n"); stream:close()
        print("ROBOTRON_HOST_WAIT_SMOKE " .. result)
    end)
    if not ok then
        local result = string.format('{"status":"FAILED","error":%q}', tostring(failure))
        local stream = assert(io.open(output, "w")); stream:write(result .. "\n"); stream:close()
        print("ROBOTRON_HOST_WAIT_SMOKE " .. result)
    end
    manager.machine:exit()
end
emu.register_frame_done(smoke_once)
