import argparse,importlib.util,json,pathlib,sys,time
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26/fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
a=argparse.ArgumentParser();a.add_argument('--stage',choices=['stop','CPU','backup'],required=True);a.add_argument('--prepared',type=pathlib.Path,required=True);args=a.parse_args()
h=load('_maintScopeH',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');seq=load('_maintScopeSeq',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py');reader=load('_maintScopeReader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py');archive=load('_maintScopeArchive',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
read=lambda pin,as_json=True:reader.read_pin(pin,as_json=as_json)
state=json.loads((G/'logs/managed-learning-20261015/state.json').read_text());assert state['active_maintenance_job']['directory']==str(R)
packet=read(h.pin(R/'prepared-current-source-family.json'));role={'stop':'stop_controller','CPU':'CPU_controller','backup':'backup_controller'}[args.stage];controller=packet['source_catalogue'][role]
assert args.prepared.resolve()==args.prepared and args.prepared.is_relative_to(R)
prepared=read(h.pin(args.prepared));config_pin=prepared.get('config',prepared.get('controller_config'));assert config_pin
config=read(config_pin);assert pathlib.Path(config['output']).is_relative_to(R)
ctl=load('_maintScopeCtl',h.checked(controller));directory=args.prepared.parent
def on_live(owner,child):
 h.put(directory/'actual-original-live-owner-for-root.json',dict(stage=args.stage,owner=owner,controller_child=child,observed_unix_s=time.time()))
seq.invoke_controller_once(directory,'',controller,config_pin,h,on_live=on_live)
closed=seq.verify_closed_scope(directory,'',config_pin,h,read,archive,ctl,exit_zero=False);code=read(closed['result'])['actual_exit']
receipt=h.put(directory/'original-scope-result-and-positive-owned-closeout.json',dict(stage=args.stage,actual_exit=code,original_Popen_reaped=True,all_original_controller_resources_closed=True,original_result=closed['result'],owner=closed['owner'],closure=closed['closure'],original_attempt=1,no_retry=True))
print(json.dumps(dict(actual_exit=code,receipt={k:receipt[k]for k in ['path','sha256','bytes']})),flush=True);sys.exit(code)
