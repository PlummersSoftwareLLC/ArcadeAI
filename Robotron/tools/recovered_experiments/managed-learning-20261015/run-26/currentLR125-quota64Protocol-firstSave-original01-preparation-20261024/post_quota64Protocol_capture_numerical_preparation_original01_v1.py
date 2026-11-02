import ast,copy,hashlib,importlib.util,json,os,shutil,time,urllib.request
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';B=G/'tools/startup_policy_journal_proposal';P=G/'tools/training_connection_lifecycle_proposal_20261023';D=R/'currentLR125-quota64Protocol-firstSave-original01-preparation-20261024';N=R/'quality32-protected1741-vs-currentLR125-restored192-firstSave-original01-preparation-20261023'
def load(path,name,sha=None):
 raw=Path(path).read_bytes()
 if sha: assert hashlib.sha256(raw).hexdigest()==sha
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_post_h','2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1');reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_post_r','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
arc=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_post_arc','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445');closer=load(P/'independent_component_closeout_v3.py','_post_close')
proof=closer.closeout(D,h,arc,read,0);capture=read(h.pin(D/'output-original01/result.json'));selected=read(capture['selection']);prefix=read(capture['prefix']);job=read(h.pin(D/'job.json'))
engine=load(job['engine']['path'],'_post_engine',job['engine']['sha256'])
# Precommitted before capture: retain the full60s/200ms prefix and every raw record.
assert 280<=len(prefix['samples'])<=301 and prefix['deep_samples']==12
# The original prefix closed before the managed-save slot changed. A later
# replay's final CURRENT-held-input predicate correctly cannot certify its
# historical slot. Preserve that limitation; do not substitute an archive
# for the live path or label this prefix independently replay-qualified.
try:
 engine.replay(prefix['health_job'],prefix['samples'],read(prefix['initial_cursors']),read,h,original_statuses=prefix['actual_status'])
except ValueError as error:
 assert str(error)=='Original197 held inputs changed at independent readback'
 replay=dict(independent_raw_replay_passed=False,actual_readback_error=str(error),reason='Owned completed-slot transition occurred after original prefix closed; no live path or original bytes substituted',scientific_qualification=False)
else:raise AssertionError('Expected historical slot mismatch after the owned capture transition')
for sample in prefix['samples']: h.checked(sample)
assert prefix['writer']['thread_stopped'] and prefix['writer']['all_original_samples_persisted']
assert prefix['guard_ended_monotonic_s']-prefix['guard_started_monotonic_s']>=60
for part in ['before','request','after']:
 t=capture['completed_slot_transition'][part]
 assert read(t['archive'])==({'tag':capture['tag']} if part!='before' else read(t['archive']))
assert read(capture['completed_slot_transition']['before']['archive'])!={'tag':capture['tag']}
assert capture['checkpoint']==h.pin(capture['checkpoint']['path'])
assert capture['completed_slot_transition']['request']['actual_pin']['identity']['inode']==capture['completed_slot_transition']['after']['actual_pin']['identity']['inode']
before=read(job['binding']);binding=copy.deepcopy(before);slot=str(G/'models_dqn/managed_save.request.json.completed');after=capture['completed_slot_transition']['after']['actual_pin'];actual=h.pin(slot)
assert actual==after and before['held_hashes'][slot]==capture['completed_slot_transition']['before']['actual_pin']['sha256']
binding['held_hashes'][slot]=after['sha256'];binding['prior_binding']=job['binding'];binding['owned_managed_save_slot_transition']=capture['completed_slot_transition'];binding['owned_completed_slot_only_source_hold_transition']=True;binding['current_binding_reason']='Exact completed-slot transition from one precommitted owned-health first-save capture; all other held hashes and actor identities unchanged'
assert {k:v for k,v in binding['held_hashes'].items()if k!=slot}=={k:v for k,v in before['held_hashes'].items()if k!=slot}
binding_path=D/'postcapture-current-main-binding.json'
if binding_path.exists():
 assert read(h.pin(binding_path))==binding
 newbinding=h.pin(binding_path)
else:newbinding=h.put(binding_path,binding)
oldmon=(R/'currentLR125-quota64-firstSave-original01-preparation-20261024/postcapture-current-main-readonly-monitor-v2.py').read_text();node=next(x for x in ast.parse(oldmon).body if isinstance(x,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINS'for t in x.targets));pins=ast.literal_eval(node.value);pins['binding']=newbinding;lines=oldmon.splitlines(keepends=True);lines[node.lineno-1:node.end_lineno]=['PINS = '+repr(pins)+'\n'];mon=''.join(lines)
monpath=D/'postcapture-current-main-readonly-monitor-v2.py'
with monpath.open('xb')as f:f.write(mon.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
monpin=h.pin(monpath);exec(compile(mon,monpin['path'],'exec'),{'__name__':'_postcapture_monitor'})
api=read(capture['trigger_API']);clocks={k:api[k]for k in ['training_steps','optimized_samples','learner_frame_count','frame_count']};assert clocks['learner_frame_count']>selected['after_learner_frame_count'];assert all(type(clocks[key])is int and clocks[key]>value for key,value in selected['failed3041_saved_clock_floor'].items())
publication=read(h.pin(D/'output-original01/request-publication.json'));assert publication['brief_exact_owner_pause'] and publication['owner_pause_s']<1
proof.update(schema='robotron-owned-health-firstSave-independent-closeout-v1',capture=h.pin(D/'output-original01/result.json'),prefix_raw_replay=replay,postcapture_binding=newbinding,postcapture_monitor=monpin,actual_publication=publication,learning_recipe_changed=False,old_studies_requalified=False,quality_qualified=False)
proofpin=h.put(D/'independent-original-capture-and-current-main-closeout.json',proof)
prep=D/'candidate-CPU-preparation-original01';prep.mkdir(mode=0o700)
oldjob=json.loads((N/'candidate-CPU-preparation-original01/candidate-CPU-job.json').read_text());num=copy.deepcopy(oldjob);num['source']=capture['checkpoint'];num['clock_floor']=clocks;num['output_directory']=str(D/'candidate-CPU-verification-original01')
acq=dict(schema='robotron-owned-phase-snapshot-acquisition-v1',purpose='candidate',experiment=binding['experiment'],model_dir=str(G/'models_dqn'),owner_before=capture['owner'],owner_after=binding['owner'],client_count=api['client_count'],source_checkpoint={k:capture['checkpoint'][k]for k in ['path','sha256','bytes']},clock_floor=clocks,phase_record_sha256=num['phase_snapshot']['phase_record']['sha256'],boot_checkpoint=num['phase_snapshot']['boot_checkpoint'],tag=capture['tag'],completed_slot_transition=capture['completed_slot_transition'],stopped_absence=None,independent_capture_selection=capture['selection'],actual_original_capture_result=h.pin(D/'output-original01/result.json'),current_main_registration=proofpin,failed32M_window_not_used_as_endpoint_proof=True)
acqpin=h.put(prep/'actual-independent-current-policy-acquisition.json',acq);num['phase_snapshot']['acquisition']=acqpin;num['phase_snapshot']['owner']=binding['owner'];num['phase_snapshot']['observed_clients']=api['client_count']
copyfile=prep/'candidate-independent-readonly.pt'
with open(capture['checkpoint']['path'],'rb')as src,copyfile.open('xb')as dst:
 shutil.copyfileobj(src,dst,8<<20);dst.flush();os.fchmod(dst.fileno(),0o444);os.fsync(dst.fileno())
num['verification_copy']=h.pin(copyfile);assert num['verification_copy']['sha256']==capture['checkpoint']['sha256'] and num['verification_copy']['identity']['inode']!=capture['checkpoint']['identity']['inode']
numjob=h.put(prep/'candidate-CPU-job.json',num)
cpu=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_post_cpu','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14');oldcfg=json.loads((N/'candidate-CPU-preparation-original01/candidate-CPU-controller-config.json').read_text());argv=oldcfg['argv'][:];argv[argv.index('--job')+1]=numjob['path'];argv[argv.index('--expected-job-sha256')+1]=numjob['sha256'];pins=[cpu.pin(p['path'])for p in oldcfg['pins'][:3]]+[cpu.pin(x['path'])for x in [numjob,num['source'],num['verification_copy'],acqpin,proofpin]]
cfg=dict(unit='robotron-quota64Protocol-LR125-firstSave-numerical-CPU-original01-20261024.service',output=str(D/'candidate-CPU-execution-original01'),argv=argv,properties=oldcfg['properties'],pins=pins,observation_s=240)
cfgpin=h.put(prep/'candidate-CPU-controller-config.json',cfg)
print(json.dumps(dict(capture_closeout=proofpin,source=num['source']['sha256'],clock_floor=clocks,numerical_config=cfgpin)))
