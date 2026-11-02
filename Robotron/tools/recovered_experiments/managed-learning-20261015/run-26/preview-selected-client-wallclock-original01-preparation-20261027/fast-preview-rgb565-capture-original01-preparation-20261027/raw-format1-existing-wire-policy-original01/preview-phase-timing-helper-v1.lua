-- Selected actor diagnostics only. No file, socket, gameplay or telemetry wire.
local PREVIEW_PROFILE_SLOT = 163
local PREVIEW_PROFILE_WINDOW_S = 5.0
local preview_profile_enabled = CLIENT_SLOT == PREVIEW_PROFILE_SLOT and socket_clock_kind == "host_wall"
local preview_profile_names = {"frame_period", "capture_total", "snapshot_size", "snapshot_pixels", "convert", "serialize", "socket_write", "action_wait"}
local function preview_profile_empty()
    local stats = {}
    for _, name in ipairs(preview_profile_names) do stats[name] = {0, 0, 0, 0, 0} end
    return stats
end
local preview_profile_stats = preview_profile_empty()
local preview_profile_window_wall, preview_profile_window_cpu = nil, nil
local preview_profile_last_frame_wall, preview_profile_last_frame_cpu = nil, nil
local preview_profile_backwards = 0

if CLIENT_SLOT == PREVIEW_PROFILE_SLOT then
    print(string.format("[PREVIEW_PHASE_V1_BEGIN] slot=%d lua_version=%q wall_clock=%s enabled=%s window_target_s=%.1f process_cpu_scope=all_process_threads",
        CLIENT_SLOT, tostring(_VERSION), tostring(socket_clock_kind), tostring(preview_profile_enabled), PREVIEW_PROFILE_WINDOW_S))
end

local function preview_profile_record(name, wall_s, cpu_s)
    local row = preview_profile_stats[name]
    row[1] = row[1] + 1
    row[2] = row[2] + wall_s
    row[3] = row[3] + cpu_s
    row[4] = math.max(row[4], wall_s)
    row[5] = math.max(row[5], cpu_s)
    if wall_s < 0 or cpu_s < 0 then preview_profile_backwards = preview_profile_backwards + 1 end
end

local function preview_profile_mark()
    if preview_profile_enabled then return socket_time_now(), os.clock() end
    return nil, nil
end

local function preview_profile_finish(name, wall_start, cpu_start)
    if not preview_profile_enabled then return end
    local wall_now, cpu_now = socket_time_now(), os.clock()
    preview_profile_record(name, wall_now - wall_start, cpu_now - cpu_start)
end

local function preview_profile_frame_begin()
    if not preview_profile_enabled then return end
    local wall_now, cpu_now = socket_time_now(), os.clock()
    if preview_profile_last_frame_wall ~= nil then
        preview_profile_record("frame_period", wall_now - preview_profile_last_frame_wall, cpu_now - preview_profile_last_frame_cpu)
    end
    preview_profile_last_frame_wall, preview_profile_last_frame_cpu = wall_now, cpu_now
    if preview_profile_window_wall == nil then
        preview_profile_window_wall, preview_profile_window_cpu = wall_now, cpu_now
        return
    end
    if wall_now - preview_profile_window_wall < PREVIEW_PROFILE_WINDOW_S then return end
    local fields = {string.format("[PREVIEW_PHASE_V1] slot=%d window_wall_s=%.6f window_cpu_s=%.6f preview_enabled=%s clock_backwards=%d",
        CLIENT_SLOT, wall_now - preview_profile_window_wall, cpu_now - preview_profile_window_cpu,
        tostring(preview_stream_enabled == true), preview_profile_backwards)}
    for _, name in ipairs(preview_profile_names) do
        local row = preview_profile_stats[name]
        local denominator = math.max(1, row[1])
        fields[#fields + 1] = string.format("%s_n=%d %s_wall_sum_ms=%.6f %s_cpu_sum_ms=%.6f %s_wall_mean_ms=%.6f %s_cpu_mean_ms=%.6f %s_wall_max_ms=%.6f %s_cpu_max_ms=%.6f",
            name, row[1], name, row[2] * 1000, name, row[3] * 1000,
            name, row[2] * 1000 / denominator, name, row[3] * 1000 / denominator,
            name, row[4] * 1000, name, row[5] * 1000)
    end
    print(table.concat(fields, " "))
    preview_profile_stats = preview_profile_empty()
    preview_profile_window_wall, preview_profile_window_cpu = wall_now, cpu_now
    preview_profile_backwards = 0
end

