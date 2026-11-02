import copy, importlib.util, json, os, pathlib, sys, time
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26'
OLD=B/'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'
C=B/'short15-protectedb231-vs-stopped77f9-immutable-review-original02-20261101'
F=B/'quality32-protectedb231-vs-stopped77f9-fullgame-original01-20261101'
P=B/'preserved-live-research-next64M-original03-20261101'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_prepare_next_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
read=lambda p:json.loads(pathlib.Path(p).read_text())
F.mkdir(mode=0o700);(F/'selected-source').mkdir(mode=0o700);rd=F/'roles-CPU-original01';rd.mkdir(mode=0o700)
old=read(OLD/'roles-CPU-original01/job.json');short=read(C/'selection.json')
proposal=read(B/'post-engineering-fullstate-preservation-original03-20261101/next-fresh-frozen-pair-proposal-original01.json')
source=pathlib.Path(old['runtime']['path']);target=F/'selected-source/acquire_confirmation_roles_CPU_v1.py'
with target.open('xb')as f:f.write(source.read_bytes());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
candidate=pathlib.Path(B/'post-engineering-fullstate-preservation-original03-20261101/checkpoint-acquisition-original02/independent-stopped-verification-copy.pt')
candidate_pin=h.pin(candidate);assert candidate_pin['sha256']=='77f9f42fbdd67c0d5081229710140931422292d83ee437cc08de64c188fe7228'
selection=h.put(F/'next-controlled-comparison-selection.json',dict(
 schema='robotron-new-stopped77f9-fullgame-selection-v1',observed_unix_s=time.time(),
 completed_short_screen=h.pin(C/'completed-short15-independent-result-and-positive-current-closeout-original01.json'),
 candidate=candidate_pin,reference=old['roles']['reference']['checkpoint'],
 rationale='The valid 15-minute screen is a near-tie with checkpoint direction reversal and no complete games. Fresh full games are required to assess survival/late-game quality. This is a later, distinct candidate from failed1c, not a retry or rescue of that campaign.',
 candidate_saved_clocks=dict(training_steps=19730796,learner_frame_count=5160938463,optimized_samples=79241545728,frame_count=9885736399),
 reference_scores='Fresh R1/R2 only; no historic or short-screen scores',
 candidate_gates='Independent complete64 C1 and C2, two per all32/full tails. Each mean>=1.05 pooled fresh128 reference mean and median preserved. No candidate pooling/retry/censor rescue.',
 predeclared_early_rejection='After fully reviewed R1/C1/R2, skip C2 only when the exact fixed C1 gate failed. Passing C1 still needs C2.',
 Main_or_protected_policy_changed=False,statistical_confidence_claim=False,promotion=False))
job=copy.deepcopy(old);job.update(runtime=h.pin(target),selected_fullgame_plan=selection,output=str(F/'roles'),report=str(rd/'report.json'))
job['roles']['candidate']=dict(checkpoint=candidate_pin,expected_clocks=read(selection['path'])['candidate_saved_clocks'],authority=h.pin(B/'post-engineering-fullstate-preservation-original03-20261101/stopped-CPU-original01/runtime/cpu-verification.json'))
jp=h.put(rd/'job.json',job)
prev=B/'preserved-live-research-after-next64M-original02-20261101';prepared=read(prev/'prepared-CPU-preservation.json');ctl=load('_prepare_next_ctl',h.checked(prepared['controller']))
cfg=read(OLD/'roles-CPU-original01/controller-config.json');cfg.update(unit='robotron-fullgame-b231-77f9-roles-original01.service',output=str(rd/'execution-original01'))
cfg['argv']=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2',str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',job['runtime']['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256']]
cfg['pins']=[ctl.pin(x['path'])for x in [job['runtime'],jp,job['source_package'],selection,*[v['checkpoint']for v in job['roles'].values()]]]
cp=h.put(rd/'controller-config.json',cfg)
roleprep=h.put(rd/'prepared-CPU-roles.json',dict(job=jp,controller=prepared['controller'],controller_config=cp,selection=selection,promotion=False))
P.mkdir(mode=0o700)
j=read(prev/'job.json');base=read(prev/'report.json');j.update(previous_preservation_report=h.pin(prev/'report.json'),minimum_saved_learner_frames=base['saved_clocks']['learner_frame_count']+64000000,output=str(P/'acquisition-original01'),report=str(P/'report.json'))
pj=h.put(P/'job.json',j);pc=read(prev/'controller-config.json');pc.update(unit='robotron-preserve-next64M-'+pj['sha256'][:12]+'.service',output=str(P/'execution-original01'))
pc['argv'][-3:]=[pj['path'],'--job-sha256',pj['sha256']]
pc['pins']=[ctl.pin(x['path'])for x in [j['runtime'],pj,j['active_fixed_pair'],j['previous_preservation_report']]]
pcp=h.put(P/'controller-config.json',pc)
pp=h.put(P/'prepared-CPU-preservation.json',dict(job=pj,controller=prepared['controller'],controller_config=pcp,minimum_saved_learner_frames=j['minimum_saved_learner_frames'],promotion=False))
print(json.dumps(dict(roles_prepared={k:roleprep[k]for k in ('path','sha256','bytes')},preservation_prepared={k:pp[k]for k in ('path','sha256','bytes')})))
