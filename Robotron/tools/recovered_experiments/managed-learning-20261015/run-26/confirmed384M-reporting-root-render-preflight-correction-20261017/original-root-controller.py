from pathlib import Path
import ast, datetime, hashlib, json, os, subprocess

ROOT = Path('/home/dave/source/repos/ArcadeAI')
BASE = ROOT/'Robotron/logs/managed-learning-20261015/run-26'
P = BASE/'confirmed384M-reporting-proposal-20261017'
OUT = BASE/'confirmed384M-reporting-private-render-reviewed1-20261017'
UNIT = 'robotron-reporting384-private-render-reviewed1-20261017.service'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())

assert not OUT.exists()
inputs = ['render_learning_progress.py', 'learning-and-throughput-progress.json', 'private-render-argv.json',
          'compare_sidecar_measurements.py', 'compare_frozen_measurements.py']
pins = {name:sha(P/name) for name in inputs}
assert pins['render_learning_progress.py'] == '3074bdef730dfdaff58884eb5360d7984563c1e063ea5a5e70a53acda09bdb4c'
assert pins['compare_sidecar_measurements.py'] == '879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746'
assert pins['compare_frozen_measurements.py'] == '53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0'
argv = json.loads((P/'private-render-argv.json').read_text())
ast.parse(argv[-1])
assert str(OUT/'learning-and-throughput-progress.png') in argv[-1]
state = json.loads((BASE.parent/'state.json').read_text())
assert state['incumbent']['sha256'] == 'ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963'
assert state['optimization_goal']['status'] == 'active'
old = json.loads((BASE.parent/'learning-and-throughput-progress.json').read_text())
new = json.loads((P/'learning-and-throughput-progress.json').read_text())
groups = ['learning','sidecar_learning','fixed_transport_learning','observational_guards','unplotted_guard_history']
assert all(new.get(k) == old.get(k) for k in groups)
assert sum(len(old.get(k, [])) for k in groups) == 13
for unit in (UNIT, UNIT.replace('.service','.timer')):
    obs = subprocess.run(['systemctl','--user','show',unit,'-p','LoadState','--value'],capture_output=True,text=True)
    assert obs.stdout.strip() == 'not-found', (unit,obs.stdout,obs.stderr)
OUT.mkdir(mode=0o700)
(OUT/'bound-inputs').mkdir()
for name in inputs:
    (OUT/'bound-inputs'/name).write_bytes((P/name).read_bytes())
    assert sha(OUT/'bound-inputs'/name) == pins[name]
launch = ['systemd-run','--user','--unit='+UNIT,
    '--property=WorkingDirectory='+str(ROOT),'--property=CPUQuota=200%',
    '--property=MemoryMax=3G','--property=MemorySwapMax=0','--property=TasksMax=128',
    '--property=RuntimeMaxSec=90s','--property=TimeoutStopSec=5s','--property=Restart=no',
    '--property=RemainAfterExit=yes','--property=CollectMode=inactive',
    '--property=StandardOutput=append:'+str(OUT/'stdout'),
    '--property=StandardError=append:'+str(OUT/'stderr'),*argv]
save(OUT/'execution-precommit.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
     unit=UNIT,argv=launch,input_pins=pins,root_controller_sha256=sha(__file__),
     old13_quality_objects_unchanged=True,actual_render_result=None,live_adoption=False))
result = subprocess.run(launch, capture_output=True, text=True)
save(OUT/'scheduling-result.json',dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
assert result.returncode == 0
print(json.dumps(dict(unit=UNIT,output=str(OUT),scheduled=True)))
