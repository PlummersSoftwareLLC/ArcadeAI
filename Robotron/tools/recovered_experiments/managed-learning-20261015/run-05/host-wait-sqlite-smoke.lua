
local done = false
emu.register_frame_done(function()
    if done then return end
    done = true
    local output = os.getenv("ROBOTRON_HOST_WAIT_SMOKE_OUTPUT")
    local ok, failure = pcall(function()
        local loaded, sqlite = pcall(require, "lsqlite3")
        print("HOSTWAIT_SQLITE", loaded, type(sqlite), loaded and type(sqlite.sleep) or tostring(sqlite))
        if loaded then for name,value in pairs(sqlite) do if type(value)=="function" then print("HOSTWAIT_SQLITE_FN", name) end end end
        assert(loaded and type(sqlite) == "table" and type(sqlite.sleep) == "function", "builtin SQLite sleep unavailable")
        local rate = emu.osd_ticks_per_second()
        local machine_before = emu.time()
        local ticks_before, cpu_before = emu.osd_ticks(), os.clock()
        local calls = 100
        for index = 1, calls do sqlite.sleep(1) end
        local wall, cpu = (emu.osd_ticks()-ticks_before)/rate, os.clock()-cpu_before
        local machine_after = emu.time()
        assert(machine_after == machine_before, "emulated time advanced")
        assert(wall >= 0.095, "host sleep did not wait")
        assert(cpu < wall * 0.35, "host wait consumed excessive CPU")
        local result = string.format('{"status":"verified","backend":"lsqlite3.sleep","lua_version":%q,"emu_type":%q,"tick_rate":%.0f,"sleep_ms":1,"calls":%d,"wall_s":%.9f,"process_cpu_s":%.9f,"machine_time_start_s":%.9f,"machine_time_end_s":%.9f,"frame_callback":"register_frame_done"}', _VERSION,type(emu),rate,calls,wall,cpu,machine_before,machine_after)
        local f=assert(io.open(output,"w"));f:write(result .. "\n");f:close();print("ROBOTRON_HOST_WAIT_SMOKE "..result)
    end)
    if not ok then
        local result=string.format('{"status":"FAILED","error":%q}',tostring(failure))
        local f=assert(io.open(output,"w"));f:write(result .. "\n");f:close();print("ROBOTRON_HOST_WAIT_SMOKE "..result)
    end
    manager.machine:exit()
end)
