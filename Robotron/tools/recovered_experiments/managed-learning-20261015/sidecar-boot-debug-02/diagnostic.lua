dofile("/home/dave/source/repos/ArcadeAI/Robotron/Scripts/main.lua")

local diagnostic_frame = 0
local diagnostic_screen = manager.machine.screens[":screen"]
diagnostic_snapshot_ref = register_frame_done_callback(function()
    diagnostic_frame = diagnostic_frame + 1
    if diagnostic_frame == 120 or diagnostic_frame == 600 or diagnostic_frame == 1800 then
        local filename = "/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/sidecar-boot-debug-02/screen-" .. diagnostic_frame .. ".png"
        local ok, result = pcall(function() return diagnostic_screen:snapshot(filename) end)
        print("[BOOT DIAGNOSTIC SNAPSHOT] " .. filename .. " ok=" .. tostring(ok) .. " result=" .. tostring(result))
    end
end)
