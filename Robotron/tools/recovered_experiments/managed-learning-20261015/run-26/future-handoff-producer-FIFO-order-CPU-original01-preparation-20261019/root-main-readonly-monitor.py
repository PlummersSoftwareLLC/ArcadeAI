import hashlib,importlib.util,json,time,urllib.request
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
def load(path,sha,name):
 assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
p=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','reader')
w=load(R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py','f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3','main_guard')
binding=R/'quality32-CE1059-vs-LR25-first8M-original01-preparation-20261019/runtime-bindings/main-binding.json'
assert p.digest(binding)=='e0b20519a813a752d1d2a2ce6a0ecb855628a9680f5c8d9490d12ae5d33307d2'
main=p.read_pin(p.pin(binding));w.owner_and_files(main)
a=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5))
w.healthy(a,p.read_pin(main['baseline_API']),main['experiment'],time.time())
save=G/'models_dqn/robotron_dqn_latest.pt';info=save.stat();age=time.time()-info.st_mtime
assert 0<=age<=360 and info.st_size>200000000
print(json.dumps(dict(unix_s=time.time(),classification='MAIN_LIVE_ORIGINAL192_PRIVATE_QUALITY_CLOSED',original_owner=main['owner'],original_192_actor_identities_and_193_held_inputs_verified=True,main={k:a[k] for k in ['client_count','training_enabled','measurement_active','learner_frame_count','training_steps','optimized_samples','fps']},autosave_age_s=age,autosave_bytes=info.st_size,private_quality_status=a.get('quality_campaign',{}).get('outcome'),production_changed=False),allow_nan=False))
