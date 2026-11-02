import ast,copy,importlib.util,json,os,sys,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=Path(__file__).parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
h=load('actual_context_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
native=load('actual_round_native',G/'tools/post_recovery_evaluation/run_deadline32_rounds_v2.py')
contract=native.round_contract()
forbidden=[]
def audit(event,args):
 if event in ('socket.bind','subprocess.Popen','os.system','os.fork','os.posix_spawn'):
  forbidden.append(event);raise AssertionError('Private payload/process action before preflight: '+event)
sys.addaudithook(audit)
prep=json.loads((P/'preparation.json').read_bytes());contexts=[];rejections=[]
def reject(name,callback):
 try:callback()
 except (AssertionError,ValueError,KeyError)as error:rejections.append(dict(name=name,reason=str(error)));return
 raise AssertionError('Required guard accepted counterfactual: '+name)
for item in prep['fixtures']:
 job=json.loads(h.checked(item['job']).read_bytes())
 for pin in job['inputs']:h.checked(pin)
 context=native.validate_completed_context(job,h)
 assert len(context['package_pins'])==123 and len(context['main_binding']['inputs'])==243
 contexts.append(dict(leg=item['leg'],actual_job=item['job'],source_package_files=123,main_inputs=243,components=sorted(context['modules']),private_payload_launched=False))
 reject(item['leg']+' cannot execute engineering family',lambda:contract.validate_launch(job,context,h))
for field,value in [('gpu_uuid','GPU-wrong'),('backend','eager'),('startup_trace_frames',1199),('horizon_ns',3600000000001)]:
 bad=copy.deepcopy(job);bad[field]=value;reject('private '+field,lambda bad=bad:native.validate_completed_context(bad,h))
protocol=context['protocol'];family=context['family']
bad=copy.deepcopy(protocol);bad['hot_max_gap_s']=5;reject('hot bound cannot weaken to5s',lambda:contract.validate_static(job,bad,family,h))
bad_family=copy.deepcopy(family);bad_family['main_observer']['worker']['sha256']='0'*64
bad_job=copy.deepcopy(job);bad_job['observer_sources']=bad_family['main_observer'];reject('actual observer source SHA',lambda:contract.validate_static(bad_job,protocol,bad_family,h))
def read(pin,as_json=True):
 return json.loads(h.checked(pin).read_bytes())if as_json else h.checked(pin).read_bytes()
binding=read(job['main_binding']);bad_binding=copy.deepcopy(binding);bad_binding['inputs'].pop(next(iter(bad_binding['inputs'])))
def wrong_inputs(pin,as_json=True):return bad_binding if pin==job['main_binding']else read(pin,as_json)
reject('full243 source inventory',lambda:contract.validate_binding(job,protocol,family,wrong_inputs,h))
baseline=read(binding['baseline_snapshot']);bad_baseline=copy.deepcopy(baseline);bad_baseline['api']['lr']=6.25e-6
def wrong_recipe(pin,as_json=True):return bad_baseline if pin==binding['baseline_snapshot']else read(pin,as_json)
reject('actual lower-rate baseline',lambda:contract.validate_binding(job,protocol,family,wrong_recipe,h))
np=G/'tools/post_recovery_evaluation/run_deadline32_rounds_v2.py';rp=G/'tools/post_recovery_evaluation/review_deadline32_rounds_v2.py'
for name,before,after in [('private cutoff',"job['horizon_ns']==3_600_000_000_000","job['horizon_ns']==3_600_000_000_001"),('missing new ownership gate','    round_contract().validate_launch(job, context, h)\n','')]:
 text=np.read_text();assert text.count(before)==1;text=text.replace(before,after,1);path=P/('counterfactual-'+name.replace(' ','-')+'-NEVER-EXECUTED.py');path.write_text(text);path.chmod(0o444);reject(name,lambda path=path:contract.validate_derivation(path,rp))
trial=dict(context);trial['family']=copy.deepcopy(context['family']);trial['family']['native_launch_qualified']=True
readiness=contract.validate_launch(job,trial,h)
assert readiness['accepted_samples']==176 and readiness['full_main_input_count']==243
for mutation in ('owner','source_domain','lineage'):
 bad=dict(trial);bad['main_binding']=copy.deepcopy(trial['main_binding'])
 if mutation=='owner':bad['main_binding']['owners']['trainer']['process']['pid']+=1
 elif mutation=='source_domain':bad['main_binding']['inputs'].pop(next(iter(bad['main_binding']['inputs'])))
 else:bad['main_binding']['exposure']['optimizer']['epoch']+=1
 reject('main domain '+mutation,lambda bad=bad:contract.validate_launch(job,bad,h))
assert forbidden==[]
if 'torch'in sys.modules:assert not sys.modules['torch'].cuda.is_initialized()
h.put(P/'CPU-actual-context-guards-result.json',dict(status='PASS_ENGINEERING_CONTEXT_ONLY',contexts=contexts,rejections=rejections,private_predicate_derivation=contract.validate_derivation(np,rp),forbidden_payload_actions=forbidden,actual192_slot_domain_readiness=readiness,full_live192_capacity_not_claimed=True,native_launch_qualified=False,quality_qualified=False))
print(json.dumps(dict(status='PASS_ENGINEERING_CONTEXT_ONLY',contexts=len(contexts),targeted_rejections=len(rejections))),flush=True)
