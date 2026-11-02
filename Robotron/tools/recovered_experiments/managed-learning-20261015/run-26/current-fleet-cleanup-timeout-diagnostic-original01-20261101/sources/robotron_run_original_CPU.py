import importlib.util,json,pathlib,sys
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron')
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_oneCPUh',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
seq=load('_oneCPUseq',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py')
reader=load('_oneCPUreader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
archive=load('_oneCPUarchive',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
p=pathlib.Path(sys.argv[1]);prepared=json.loads(h.checked(h.pin(p)).read_text());directory=p.parent
ctl=load('_oneCPUctl',h.checked(prepared['controller']))
seq.invoke_controller_once(directory,'',prepared['controller'],prepared['controller_config'],h)
closed=seq.verify_closed_scope(directory,'',prepared['controller_config'],h,lambda p,as_json=True:reader.read_pin(p,as_json=as_json),archive,ctl)
report=h.pin(directory/'report.json');r=reader.read_pin(report)
assert r['status'].startswith('PASS_')
result=h.put(directory/sys.argv[2],dict(status='PASS_ORIGINAL_CPU_AND_POSITIVE_OWNED_CLOSEOUT',actual_exit=0,
 all_original_CPU_resources_closed=True,original_Popen_reaped=True,result=closed['result'],owner=closed['owner'],closure=closed['closure'],report=report))
print(json.dumps(dict(status=r['status'],receipt={k:result[k]for k in ('path','sha256','bytes')})),flush=True)
