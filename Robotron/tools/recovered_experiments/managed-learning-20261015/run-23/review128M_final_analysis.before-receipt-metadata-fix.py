#!/usr/bin/env python3
"""Small completed-report arithmetic/contract review; no model/Torch/controls."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,importlib.util,json,math,os,statistics,sys

BASE=Path(__file__).resolve().parents[1]
RUN=Path(__file__).resolve().parent
started=datetime.now(timezone.utc).isoformat()
evidence=[]
checks={}
def read(path):
    path=Path(path).resolve();raw=path.read_bytes()
    evidence.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    return json.loads(raw)
def check(name,value):
    checks[name]=bool(value)
    if not value:raise ValueError(name)
def stats(rows):
    scores=[r['score'] for r in rows]
    return dict(count=len(scores),mean=statistics.mean(scores),median=statistics.median(scores),
                sd=statistics.stdev(scores),se=statistics.stdev(scores)/math.sqrt(len(scores)))
def same(a,b):return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)
def stat_match(left,right):return all(same(left[k],right[k]) for k in ('count','mean','median','sd','se'))
analysis=read(RUN/'quality128M-two-leg-final-analysis.json')
lineage=read(analysis['lineage']['path'])
check('final_root_lineage_byte_pin',evidence[-1]['sha256']==analysis['lineage']['sha256'])
check('final_root_lineage_PASS',lineage['PASS'] is True and lineage['proposal_only'] is False and lineage['root_verification']['status']=='PASS')
helper=RUN/'confirmed128M-publication-proposal/build_confirmed128M_campaign.py'
helper_raw=helper.read_bytes();helper_sha=hashlib.sha256(helper_raw).hexdigest()
check('frozen_publisher_537de6',helper_sha=='537de6c233c119337d45162eec47659a4e1e67e00cc8bbfa169230e0781c775a')
evidence.append(dict(path=str(helper),sha256=helper_sha,bytes=len(helper_raw)))
spec=importlib.util.spec_from_file_location('frozen128publisher_contract',helper)
publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
publisher.confirmed_gate(analysis,analysis['policy_identity']['candidate']['sha256'],analysis['lineage']['path'],analysis['lineage']['sha256'])
checks['actual_complete_analysis_passes_frozen_publisher_gate']=True
labels=[*publisher.REFERENCE_LABELS,*publisher.LABELS]
by_label={r['label']:r for r in analysis['sources']}
check('all22_source_labels_unique',len(by_label)==len(analysis['sources'])==22)
rows={};receipt_summaries=[];backend=analysis['matched_frozen_backend'];expected_slots=list(range(4096,4112))
for label in labels:
    receipt=read(by_label[label]['path']);identity=evidence[-1]
    check(label+':receipt_byte_pin',identity['sha256']==by_label[label]['sha256'])
    rr=receipt['rows'];rows[label]=rr;st=stats(rr)
    check(label+':full_original_denominator',receipt['complete'] is True and receipt['valid'] is True and receipt['started']==receipt['count']==len(rr) and receipt['pending']==receipt['abandoned']==0 and receipt['cohort']['rows']==rr and set(receipt['cohort']['started_ids'])=={r['journal_game_id'] for r in rr})
    check(label+':receipt_statistics',stat_match(st,receipt))
    check(label+':full_tails_and_all16_slots',sorted({r['client_slot'] for r in rr})==expected_slots and all(r['complete'] is True and r['eligible'] is True and r['known_start'] is True and r['first_play_level']==1 and receipt['start_ts']<=r['start_unix_s']<receipt['close_ts'] and r['end_unix_s']>=r['start_unix_s'] for r in rr))
    check(label+':ready_boundary',receipt['boundary']['ready'] is True and receipt['boundary']['clients']==receipt['boundary']['expected']==receipt['boundary']['acknowledged']==16 and receipt['boundary']['actor_slots']==expected_slots)
    check(label+':common_frozen_backend',receipt['numeric_policy']==backend['numeric_policy'] and receipt['source_hashes']==receipt['ended_source_hashes']==backend['source_hashes'] and all(receipt['runtime'][k]==v for k,v in backend['runtime'].items()) and all(receipt['job'][k]==v for k,v in backend['job'].items()) and receipt['boot_assets']['identity']==backend['boot_identity'] and receipt['boot_assets']['files']==backend['boot_files'] and receipt['socket_wait']['sha256']==backend['socket_wait_sha256'])
    key='candidate' if label in publisher.LABELS else 'reference';policy=analysis['policy_identity'][key]
    check(label+':saved_checkpoint_clocks',receipt['checkpoint_sha256']==policy['sha256'] and all(receipt['checkpoint_metadata'].get(k)==v for k,v in policy['metadata'].items()) and all(r[c][k]==receipt['clocks'][mapped] for r in rr for c in ('start_context','end_context') for k,mapped in [('training_steps','training_steps'),('optimized_samples','optimized_samples'),('learner_frames','learner_frame_count')]))
    check(label+':runtime_clean_fulltail_cleanup_retained',not receipt['server_error'] and not receipt['inference_error'] and not receipt['cleanup_errors'] and not receipt['invalidity_reasons'] and sum(receipt['actor_timeout_logs'].values())==0)
    receipt_summaries.append(dict(label=label,**st,started=receipt['started'],pending=receipt['pending'],abandoned=receipt['abandoned'],completed_tails_after_admission=sum(r['end_unix_s']>receipt['close_ts'] for r in rr),runtime_action_timeouts=sum(receipt['actor_timeout_logs'].values()),deliberate_cleanup_timeout_diagnostics=sum(receipt['actor_cleanup_timeout_logs'].values())))
reference=[r for label in publisher.REFERENCE_LABELS for r in rows[label]]
candidate=[r for label in publisher.LABELS for r in rows[label]]
refstats=stats(reference);candstats=stats(candidate);pool=analysis['pooled_candidate_vs_composite']
check('original217_reference_and148_candidate_weighting',stat_match(refstats,pool['reference']) and stat_match(candstats,pool['candidate']) and candstats['count']==148 and refstats['count']==217)
check('mean_ratio_delta_and_median_math',same(candstats['mean']/refstats['mean'],pool['mean_ratio']) and same(candstats['mean']-refstats['mean'],pool['mean_difference']) and same(candstats['median']-refstats['median'],pool['median_difference']))
for label in publisher.LABELS:
    leg=next(x for x in analysis['management']['each_leg'] if x['label']==label)
    check(label+':individual_original_gate',stat_match(stats(rows[label]),leg) and leg['mean']>=refstats['mean']*1.05 and leg['median']>=refstats['median'] and leg['passes_each_criterion'] is True)
previous=read(BASE/'run-19/quality96M-guard-first-analysis.json')
old_sources={r['label']:(r['path'],r['sha256']) for r in previous['sources']}
check('all20_historical_receipt_pins_preserved',len(old_sources)==20 and all((by_label[k]['path'],by_label[k]['sha256'])==v for k,v in old_sources.items()))
guard=read(by_label[publisher.GUARD_LABEL]['path'])
check('96M_guard_separate_and_byte_pinned',evidence[-1]['sha256']==by_label[publisher.GUARD_LABEL]['sha256'] and analysis['additional_history']==[dict(label=publisher.GUARD_LABEL,count=81,pooled_into_reference=False)] and publisher.GUARD_LABEL not in pool['reference']['source_labels']+pool['candidate']['source_labels'])
allrows=reference+candidate+guard['rows'];ids=[r['journal_game_id'] for r in allrows]
check('four_compared_legs_and_guard_ids_disjoint',len(ids)==len(set(ids)))
check('global_denominator_math',analysis['global_ids']==dict(receipts=22,games=2237+148,overlaps=0))
check('six_official_pair_validation_attestations',len(analysis['official_pair_validation'])==6 and all(x['backend_validated'] is True and x['checkpoint_copies_verified_separately'] is True for x in analysis['official_pair_validation'].values()))
check('fixed_descriptive_bootstrap_provenance',analysis['fixed_bootstrap_iterations']==10000 and pool['game_bootstrap']['iterations']==pool['paired_slot_bootstrap']['iterations']==10000 and pool['game_bootstrap']['seed']==pool['paired_slot_bootstrap']['seed']==20261016)
slotmeans=[]
for slot in expected_slots:
    r=statistics.mean(x['score'] for x in reference if x['client_slot']==slot)
    c=statistics.mean(x['score'] for x in candidate if x['client_slot']==slot)
    claim=pool['actor_contrasts'][str(slot)]
    check('slot%d_contrast_math'%slot,same(claim['reference_mean'],r) and same(claim['candidate_mean'],c) and same(claim['mean_ratio'],c/r) and c>r)
    slotmeans.append(c/r)
check('all16_slot_contrasts_positive',pool['slots_with_positive_mean_contrast']==16)
check('Adam_logical_sample_clocks_separate',analysis['policy_identity']['candidate']['optimizer']==lineage['candidate']['optimizer'] and analysis['policy_identity']['candidate']['metadata']==lineage['candidate']['saved_metadata'] and analysis['optimizer_exposure']['minimum_parameter_step_delta']==907002-606960 and analysis['exposure_deltas']['since64M']==dict(training_steps=907399-607219,optimized_samples=2269118464-1267425280,learner_frame_count=132631504-68634783))
audits=[]
for label,filename in zip(publisher.LABELS,('quality128M-screen01-final-isolation-audit.json','quality128M-confirm01-final-isolation-audit.json')):
    audit=read(RUN/filename)
    publisher.audit_identity(audit,by_label[label],analysis['policy_identity']['candidate']['sha256'])
    audits.append(dict(label=label,path=evidence[-1]['path'],sha256=evidence[-1]['sha256'],checks=len(audit['checks'])))
checks['both_positive_final_audits_compatible_with_frozen_publisher']=True
check('report_is_eligibility_not_promotion',analysis['management']['promotion_eligible'] is True and analysis['management']['promotion'] is False and analysis['management']['reference_rebased'] is False and analysis['promotion'] is False and analysis['protection'] is False and analysis['state_or_control_changes'] is False)
check('no_Torch_import',not any(k=='torch' or k.startswith('torch.') for k in sys.modules))
result=dict(schema='robotron-128M-completed-analysis-independent-review-v1',utc=datetime.now(timezone.utc).isoformat(),started_utc=started,pid=os.getpid(),PASS=all(checks.values()),checks=checks,evidence=evidence,receipts=receipt_summaries,reference64M=refstats,candidate128M=candstats,mean_gain_pct=(candstats['mean']/refstats['mean']-1)*100,median_gain_pct=(candstats['median']/refstats['median']-1)*100,slot_ratio_range=[min(slotmeans),max(slotmeans)],final_isolation_audits=audits,scope=['Small completed receipt/report/lineage JSON and frozen publisher contract only; no actual publisher/strict analyzer/bootstrap executed, no model payload read or hash, no Torch/GPU/control/state/canonical changes.','All four compared receipts plus96M guard byte pins/rows independently checked. Historical20 receipt identity pins compared to the prior96M analysis; their model/payload bytes and global IDs are not revalidated here. The strict final analyzer and future publisher cover all22.','Bootstrap endpoints are inspected as fixed descriptive reported sensitivities, not independently recomputed confidence intervals; repeated looks, actor dependence and changing trajectories remain.','Eligibility is not publication, protection, promotion or rebasing; root owns those decisions.'])
out=RUN/'quality128M-analysis-independent-review.json'
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(dict(PASS=result['PASS'],checks=len(checks),path=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),reference=refstats,candidate=candstats,gain_pct=result['mean_gain_pct'],audits=audits),indent=2))
