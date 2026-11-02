"""Prepare a fresh first-save job only after actual positive native600 closure.

Preparation writes private files only; the later source-bound controller owns
one managed save after its unchanged60s main-health prefix.
"""
import copy,importlib.util,json,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023';B=G/'tools/startup_policy_journal_proposal'
D=R/'currentLR125-RAMKernel-firstSave-original01-preparation-20261024'
OLD=R/'currentLR125-dedicatedObserver-firstSave-original01-preparation-20261024'
NATIVE=R/'native32-RAM-live-filtered-free314-load600-original01-preparation-20261024'
T=R/'RAM-live-kernel-quality-template-contracts-CPU-original01-preparation-20261024'
FLOOR=dict(learner_frame_count=2739279553,training_steps=10864951,optimized_samples=42927044608,frame_count=5347766313)
def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
h=load(B/'run_full_policy_startup_v3.py','_capture_prepare_h');cpu=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_capture_prepare_cpu')
def read(pin):return json.loads(h.checked(pin).read_bytes())
goal=json.loads((R.parent/'state.json').read_bytes())['optimization_goal']
assert goal['actual_running_wait']is None and goal['all_current_original_handles_terminal']and not goal['full_source_freeze']
closedpin=h.pin(NATIVE/'independent-original-positive600-RAM-control-all-scopes-closeout.json');closed=read(closedpin)
assert closed['schema']=='robotron-RAM-live-filtered-reference600-all-scopes-independent-closeout-v1'
assert closed['native600_requirement_achieved']and closed['actual_native_exit']==1 and closed['actual_worker_exit']==0 and not closed['quality_qualified']
review=read(closed['independent_report']);assert review['native600_load_requirement_achieved']and review['private_resources_free']
assert review['raw_replay']['samples']>=2800 and review['raw_replay']['deep_samples']>=100 and len(review['all32_original_startup_prefixes'])==32
nativejob=read(h.pin(NATIVE/'job.json'));family=read(nativejob['source_family_manifest']);health=read(nativejob['main_health_protocol'])['health_job']
assert family['main_observer']['protocol']['sha256']=='f59df995a625ed534af1c2cb54a15c885a8e431ab84e3829e6a8b2c6ceb7bf10'
assert family['main_live_control']['sha256']=='52372d96fdbfbd2955c260ef864d456e034c8cfe015aa776b4391b5b2e679f8c'and review['RAM_control_independent_review']['original_root_absent']is True
monitor=h.pin(OLD/'postcapture-current-main-readonly-monitor-v2.py');main=json.loads(subprocess.check_output(['/usr/bin/python3.12','-I','-B',monitor['path']],text=True,timeout=25))
assert main['client_count']==192 and main['held_inputs']==197 and main['training_enabled']and 0<=main['autosave_age_s']<=360
assert all(main[key]>FLOOR[key]for key in ['learner_frame_count','training_steps','optimized_samples'])
assert health['binding']==goal['current_main_binding'];tag='currentLR125_RAMKernel_firstSave_original01_20261024'
assert not (G/'models_dqn/managed-checkpoints'/(tag+'.pt')).exists()
D.mkdir(mode=0o700);selected=h.put(D/'selected-prefix-health-inputs.json',health)
selection=h.put(D/'fresh-later-policy-selection-precommit.json',dict(schema='robotron-RAM-kernel-first-save-selection-v1',tag=tag,after_learner_frame_count=main['learner_frame_count'],failed2739_saved_clock_floor=FLOOR,
 current_main_monitor=monitor,current_main=main,required_prefix_s=60,diagnostic_closed=closedpin,
 source_template_contracts=h.pin(T/'independent-original12-tests84-rejections-and-RAM-template-scope-closeout.json'),
 hypothesis='A genuinely later retainedLR125 frozen policy may beat protected1741 in full-game quality; no causal LR, observer, throughput or learning-speed gain is assumed.',
 prior_failed_candidate_retried=False,prior_diagnostic_rerun=False,original_attempt=1,no_retry=True,learning_settings_changed=False,quality_qualified=False,created_unix_s=time.time()))
j=read(h.pin(OLD/'job.json'));j.update(output=str(D/'output-original01'),tag=tag,after_learner_frame_count=main['learner_frame_count'],health_job=selected,binding=health['binding'],selection=selection)
jp=h.put(D/'job.json',j);driver=j['driver'];cfg=read(h.pin(OLD/'controller-config.json'))
pins=[jp,selection,selected,j['helpers'],j['engine'],j['binding'],driver,closedpin,closed['independent_report'],*health['sources'].values()]
cfg.update(unit='robotron-currentLR125-transientKernel-firstSave-original01-20261024.service',output=str(D/'execution-original01'),argv=['/usr/bin/python3.12','-I','-B',driver['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],pins=[cpu.pin(p['path'])for p in {p['path']:p for p in pins}.values()])
cp=h.put(D/'controller-config.json',cfg);cpu.checked_config(cp['path']);print(json.dumps(dict(config=cp,job=jp,selection=selection)))
