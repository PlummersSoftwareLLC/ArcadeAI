"""One new exact126 source artifact after original corrected-wire CPU checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import time
p=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/evaluation_startup_proposal/prepare_diagnostic_package_v3.py')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='cbc637cd36637a711edc2a39c2bddfc78e36b96333bd61c29eb869358ad6e91e'
time.sleep(2)
s=importlib.util.spec_from_file_location('_actual_wire1890_package_builder',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
result=m.prepare(Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/evaluation_startup_proposal/startup-diagnostic-profile03'))
print(json.dumps(dict(status='NEW_CORRECTED_WIRE_PACKAGE_BUILT_NOT_EXECUTED',package=result,actual_emulator_launched=False,quality_qualified=False)),flush=True)
