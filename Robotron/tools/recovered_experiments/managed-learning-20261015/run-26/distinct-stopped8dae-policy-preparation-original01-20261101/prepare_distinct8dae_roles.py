from pathlib import Path
import copy,importlib.util,json,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';R=B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101';O=B/'quality32-protectedb231-vs-stopped77f9-fullgame-original01-20261101/roles-CPU-original02';P=B/'distinct-stopped8dae-policy-preparation-original01-20261101';D=P/'CPU-roles-original01'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_distinct8H',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');assert not P.exists();P.mkdir(mode=0o700);D.mkdir(mode=0o700);(P/'roles-original01').mkdir(mode=0o700)
old=json.loads((O/'job.json').read_text());prep=json.loads((O/'prepared-CPU-roles.json').read_text());ctl=load('_distinct8ctl',h.checked(prep['controller']));candidate=h.pin(R/'checkpoint-acquisition-original01/independent-stopped-verification-copy.pt');assert candidate['sha256']=='8dae5cccd52624755d291a086cc363c7da3995a821cc1bc2c58310ce4bcb9537';assert candidate['sha256']!=old['roles']['candidate']['checkpoint']['sha256']
authority=h.pin(R/'stopped-CPU-original01/runtime/cpu-verification.json');cpu=json.loads(h.checked(authority).read_text());assert cpu['status']=='PASS'and cpu['clocks']['learner_frame_count']==5254630919
clocks={k:cpu['clocks'][k]for k in ['training_steps','learner_frame_count','optimized_samples','frame_count']}
selection=h.put(P/'selected-distinct-candidate.json',dict(schema='robotron-distinct-preserved-policy-selection-v1',observed_unix_s=time.time(),reference=old['roles']['reference']['checkpoint'],candidate=candidate,candidate_saved_clocks=clocks,candidate_authority=authority,
 rationale='Select the final independently verified pre-maintenance checkpoint. It is later and byte-distinct from failed77f9; evaluate it as a new hypothesis. The original77f9 failed R1 remains invalid and is not retried or rescued.',
 next_steps=['Strict CPU online/target/Adam and batches1..16 frozen inference compatibility','Only after live monitor pending coverage, prepare a fresh15minute32game-per-arm exploratory screen','Full games needed for any policy quality decision; fresh R1/C1/R2/C2 with separate C1/C2 gates'],
 previous_scores_reused=False,formal_statistical_confidence_claim=False,Main_policy_modified=False,quality_qualified=False,promotion=False))
j=copy.deepcopy(old);j.update(selected_fullgame_plan=selection,output=str(P/'roles-original01'),report=str(D/'report.json'));j['roles']['candidate']=dict(checkpoint=candidate,expected_clocks=clocks,authority=authority)
for pin in [j['runtime'],j['source_package'],j['roles']['reference']['checkpoint']]:h.checked(pin)
jp=h.put(D/'job.json',j);c=copy.deepcopy(json.loads((O/'controller-config.json').read_text()));c.update(unit='robotron-b231-8dae-CPU-roles-'+jp['sha256'][:12]+'.service',output=str(D/'execution-original01'))
c['argv'][-3:]=[jp['path'],'--job-sha256',jp['sha256']];c['pins']=[ctl.pin(x['path'])for x in [j['runtime'],jp,j['source_package'],selection,authority,*[v['checkpoint']for v in j['roles'].values()]]];cp=h.put(D/'controller-config.json',c);ctl.checked_config(cp['path'])
p=h.put(D/'prepared-CPU-roles.json',dict(status='PREPARED_DISTINCT8DAE_COMPATIBILITY_CHECK_NOT_LAUNCHED',job=jp,controller=prep['controller'],controller_config=cp,selection=selection,original_failed77f9_preserved=True,no_actor_or_GPU_launch=True,quality_qualified=False,promotion=False))
print(json.dumps({k:p[k]for k in ['path','sha256','bytes']}))
