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
D=Path(outline['actual_CPU_preparation']);window=p.read_pin(outline['window_job']);O=Path(window['output']);N=R/'confirmed-scoring-quality-original01-preparation-20261018/capacity32-confirmed1059-raw-API-v1-preparation-20261019'
source=outline['campaign_preparer']['source'];assert source['sha256']=='59773f4dcb405f4fdd10e194d6e7d1dea5d9cc8fa7992b86c48247b1bcbc3889'
module=p.checked_module('_actual_campaign_metadata_preparation',source)
lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');info=lease.stat()
boot=G/'logs/managed-learning-20261015/sidecar-boot-assets-v1'
job=dict(schema='robotron-quality32-campaign-preparation-job-v1',phase_cpu_job=p.pin(D/'candidate-CPU-job.json'),phase_cpu_report=p.pin(outline['actual_CPU_report_path']),phase_cpu_closure=p.pin(outline['actual_CPU_closure_path']),phase_cpu_config=p.pin(outline['actual_CPU_config_path']),window_job=outline['window_job'],window_result=p.pin(O/'result.json'),window_latch=p.pin(O/'first-durable-both-horizons.json'),source_package=outline['source_package'],reference=outline['reference'],main_binding_template=outline['main_binding_template'],capacity_review=outline['capacity_review'],preceding_originals=[dict(owner=p.pin(N/(name+'-execution/root-original-live-owner.json')),closure=p.pin(N/(name+'-execution/native-terminal-archive/root-original-result-and-owned-release.json'))) for name in ('pilot-root','outer-controller')],output=outline['actual_campaign_preparation'],native_unit=outline['native_unit'],outer_unit=outline['outer_unit'],review_unit=outline['review_unit'],lease_path=str(lease),lease_identity=dict(device=info.st_dev,inode=info.st_ino),binary_inputs=[p.pin(path.resolve(strict=True)) for path in (G.parent/'.venv-gb300/bin/python',Path('/usr/games/mame'),G/'roms/robotron.zip',boot/'manifest.json')],campaign_parameters=dict(directory=outline['actual_campaign_directory'],reference_label=outline['reference_label'],candidate_label=outline['candidate_label'],hypothesis=outline['hypothesis_token'],boot_assets=str(boot)),hypothesis_description=outline['hypothesis_description'])
entry=c.publish(P/'actual-campaign-preparation-root-job.json',job)
report=module.prepare(job,p.pin(entry['path']),p)
print(json.dumps(dict(status=report['status'],native_controller_config=report['native_controller_config'],outer_launch_plan=report['outer_launch_plan'],CPU_completion=report['CPU_completion'])))
