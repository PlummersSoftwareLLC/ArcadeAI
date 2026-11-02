import argparse,hashlib,importlib.util,json
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--source-sha256');args=parser.parse_args()
if not args.execute:print('PLAN_ONLY: no reads, outputs, copies or launches');raise SystemExit(0)
assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
P=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-1059-reference-next8M-window-original01-preparation-20261019');G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26'
def load(path,sha,name):
 assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
p=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','reader')
c=load(G/'tools/eval_capacity_proposal/control_original_pilot.py','db1119b3ea7db7e9878b7ebd89f06a3b1c126bde46a5398617a3739917a2d9b9','publisher')
outline=p.read_pin(p.pin(P/'tested-CPU-and-campaign-preparation-handoff.json'));old=p.read_pin(outline['original_handoff'])
closure=p.pin(outline['window_closure_path']);closed=p.read_pin(closure);assert closed['original_exit']==0 and closed['lifecycle_complete'] and closed['unit_released']
source=outline['candidate_CPU_preparer']['source'];assert source['sha256']=='52a41adfaed55d296cb6212ceff8213c9daefea503665cb313db60b8486d60e9'
module=p.checked_module('_actual_CPU_metadata_preparation',source)
job=dict(schema='robotron-quality32-original-candidate-CPU-preparation-v1',window_job=outline['window_job'],window_source=p.read_pin(p.pin(P/'root-selection.json'))['source'],window_owner=outline['window_original_owner'],window_closure=closure,CPU_template=old['CPU_job_template'],CPU_controller=p.pin(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'),destination=outline['actual_CPU_preparation'],CPU_unit=outline['actual_CPU_unit'])
entry=c.publish(P/'actual-candidate-CPU-preparation-root-job.json',job)
report=module.prepare(job,p.pin(entry['path']),p)
print(json.dumps(dict(status=report['status'],CPU_job=report['CPU_job'],CPU_controller_config=report['CPU_controller_config'],CPU_verified=False)))
