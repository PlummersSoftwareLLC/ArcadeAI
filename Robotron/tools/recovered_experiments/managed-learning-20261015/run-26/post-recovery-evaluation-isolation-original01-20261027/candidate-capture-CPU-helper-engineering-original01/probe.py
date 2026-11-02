import importlib.util,json
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
P=Path(__file__).parent
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
plan=json.loads((B/'post-recovery-learning-20261027-original03/window-plan.json').read_bytes())
observer=load('CPU_probe_observer',G/'tools/power_recovery/watch_learning_window_v2.py')
runner=load('CPU_probe_candidate',G/'tools/power_recovery/watch_replay_progress_candidate.py')
plan['CPU_unit']='robotron-replay-progress-helper-CPU-original01.service'
endpoint=observer.pin(B/'post-recovery-learning-20261027-original01/entry-snapshot.pt')
report=runner.verify_CPU(plan,P,endpoint,observer)
observer.publish(P/'result.json',dict(status='PASS_ENGINEERING_CPU_LIFECYCLE_ONLY',verification=report,existing_entry_policy_only=True,quality_qualified=False),exclusive=True)
print('PASS_ENGINEERING_CPU_LIFECYCLE_ONLY',flush=True)
