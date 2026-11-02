local ok,err=pcall(function() assert(loadfile("/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/full-tail-wire-v2-contract-original01-preparation-20261022/full-tail-observation-main.lua"))() end)
if not ok then print("DEADLINE32_LUA_FATAL "..tostring(err));manager.machine:exit() end
