local ok,err=pcall(function() assert(loadfile("/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/full-policy-startup-wire-contract-original01-preparation-20261022/full-observation-main.lua"))() end)
if not ok then print("COMPILED32_STARTUP_FATAL "..tostring(err));manager.machine:exit() end
