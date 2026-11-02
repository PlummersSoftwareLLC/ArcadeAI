local ok,err=pcall(function() assert(loadfile("/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_clock_proposal/gated_start_trace_v2.lua"))().from_environment() end)
if not ok then print("GATED_START_DIAGNOSTIC_FATAL "..tostring(err));manager.machine:exit() end
