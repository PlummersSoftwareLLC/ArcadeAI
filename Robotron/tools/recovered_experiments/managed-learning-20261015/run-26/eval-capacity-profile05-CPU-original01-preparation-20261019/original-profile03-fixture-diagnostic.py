import sys,unittest,json,os
from pathlib import Path
sys.path.insert(0,"/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile03")
suite=unittest.defaultTestLoader.loadTestsFromName("Robotron.Scripts.dqn.test_measurement_actor")
r=unittest.TextTestRunner(verbosity=2).run(suite)
assert r.testsRun==7 and len(r.failures)==1 and len(r.errors)==2
assert "test_low_score_carry_tear" in r.failures[0][0].id()
assert all("_rejected_gaps" in text for _,text in r.errors)
p=Path(sys.argv[1])
with p.open('x') as f:
 json.dump(dict(status="REPRODUCED_PREEXISTING_FIXTURE_FAILURES",tests_run=r.testsRun,failures=[dict(test=t.id(),trace=text) for t,text in r.failures],errors=[dict(test=t.id(),trace=text) for t,text in r.errors],production_changed=False),f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
