-- Static pre-fix production excerpts; never loaded by the application.
-- Original main.lua SHA256: 6128b00a0e578c2d1a99076bf58b06bebbf5a17ef0dd356633816608f01153ba
local function close_socket()
    if current_socket then
        current_socket:close()
        current_socket = nil
    end
    ACTION_RX_BUFFER = ""
    set_preview_stream_enabled(false)
    PREVIEW_HUD_ENABLED = false
end

local function open_socket() end

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

        log_socket_receive_timeout(#ACTION_RX_BUFFER, math.max(0, socket_time_now() - started))
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

local function determine_meta_commands() end
