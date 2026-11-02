import argparse,json,os,time,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--capture',type=int,choices=range(4));a=p.parse_args()
if a.capture is None:print('PLAN_ONLY');raise SystemExit(0)
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';Q=Path(__file__).resolve().parent;F=B/'quality32-protectedb231-vs-stopped77f9-restored8192-fullgame-original01-20261101';R=B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101'
job=json.loads((F/'01-reference/job.json').read_text());expected=job['current_main'];owner=expected['owner'];proc=Path('/proc',str(owner['pid']));assert int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])==owner['starttime_ticks']
start=time.monotonic()
with urllib.request.urlopen(expected['API'],timeout=5)as response:raw=response.read((1<<20)+1)
assert len(raw)<=1<<20;now=json.loads(raw);assert time.monotonic()-start<=10 and 0<=time.time()-now['ts']<=10
assert now['pipeline_read_error']==now['bank_persistence_read_error']=='' and now['host_pipeline']['available']is True
for kind in ['optimizer','replay']:
 actual=now['host_pipeline']['learning_exposure'][kind];assert {k:actual[k]for k in ['process_id','instance_monotonic_ns','epoch','epoch_reason']}==expected['exposure'][kind]
heartbeat=json.loads((F/'sequence-heartbeat.json').read_text());assert heartbeat['current_leg']=='R1' and heartbeat['terminal']is False
fleet=json.loads((R/'post-backup-fleet-v6-original02/status.json').read_text());assert fleet['error_summary']['occurrences']==0
rolecounts={role:sum(v['state']==role for v in fleet['slots'].values())for role in ['active_train','active_eval','closed_eval','reconnecting_train']}
record=dict(observed_unix_s=time.time(),API=now,original_Main_owner=owner,role_counts=rolecounts,heartbeat=heartbeat,API_read_elapsed_s=time.monotonic()-start,scientific_quality_claimed=False,training_control_changed=False)
path=Q/f'sample-{a.capture:02d}.json'
with path.open('x')as stream:stream.write(json.dumps(record,indent=2,allow_nan=False)+'\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
fd=os.open(Q,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps(dict(sample=a.capture,Main_ts=now['ts'],frames=now['frame_count'],learner_frames=now['learner_frame_count'],steps=now['training_steps'],samples=now['optimized_samples'],roles=rolecounts)))
