-- Optional startmame.sh --level bootstrap. Keep the normal fleet's main.lua
-- and its pinned launch recipe unchanged; override only this client's start.
local requested_level = tonumber(os.getenv("ROBOTRON_START_LEVEL") or "")
assert(requested_level and requested_level == math.floor(requested_level)
    and requested_level >= 1 and requested_level <= 81,
    "ROBOTRON_START_LEVEL must be an integer from 1 to 81")

local script_dir = assert(debug.getinfo(1, "S").source:match("^@(.+[/\\])"),
    "Cannot locate the Robotron Lua script directory")
-- MAME gives autoboot scripts their own environment. Load the normal script
-- into this same environment so its callbacks see the override below.
assert(loadfile(script_dir .. "main.lua", "t", _ENV))()

-- The server refreshes these fields with every action reply. Apply the local
-- choice at the existing new-game patch boundary, after that reply. Explicit
-- level 1 also overrides an advanced-start instruction from the server.
local apply_start_wave = robotron_apply_start_wave_patch
function robotron_apply_start_wave_patch(...)
    START_ADVANCED = requested_level > 1
    START_LEVEL_MIN = requested_level
    return apply_start_wave(...)
end
print(string.format("[START] Client starting level override: %d", requested_level))
