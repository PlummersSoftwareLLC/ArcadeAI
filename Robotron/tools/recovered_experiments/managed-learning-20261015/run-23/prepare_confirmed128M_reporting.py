#!/usr/bin/env python3
"""Prepare reviewed copies only after actual root128M promotion; no canonical writes."""
from datetime import datetime,timezone
from pathlib import Path
import copy,difflib,hashlib,json,os,statistics

REPO=Path(__file__).resolve().parents[4]
GAME=REPO/'Robotron';BASE=GAME/'logs/managed-learning-20261015';RUN=BASE/'run-23'
OUT=RUN/'confirmed128M-reporting-proposal'
PINS={
 'sidecar-fresh3-128M-confirmed-campaign.json':'537975693dc67ae99366902908d8311e800e78121ad8d16969af80bdc64e6faf',
 'run-23/quality128M-two-leg-final-analysis.json':'8648f3b2d8a31e231dcade8d1c9856099f83080ecc022dd8f63618a7bf9248d1',
 'run-23/fresh3-128M-checkpoint-lineage.json':'4535f56d71a1fe3c3b6c3f148ae7ab9cc6f9846d6eaa3b420ede0e82bc6eda18',
 'run-23/quality128M-screen01-final-isolation-audit.json':'225815925087325de6ecd7a53925ab9afa8803f1c5efc9b774b38b24306e9a3d',
 'run-23/quality128M-confirm01-final-isolation-audit.json':'58d70b6bb9d9f3a4c3a6a9a6ea127a06fd653442daf7ec5f319eff4cde730a92',
 'run-23/quality128M-analysis-independent-review.json':'554cf8b2f4814ddf5fffbd133784e37343f35816d0b2ac3c41b6901a6e9e71be',
 'run-23/quality128M-two-leg-final-independent-math-audit.json':'dbeb8e981657552f90448aeb83d9ccf2f14be895b9d8f0c33a14c9b0d8e1e03d',
}
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def main():
    started=datetime.now(timezone.utc).isoformat()
    OUT.mkdir();before=OUT/'before';before.mkdir();proposed=OUT/'proposed';proposed.mkdir()
    canonical={'render_learning_progress.py':GAME/'tools/render_learning_progress.py','DELL_SETUP.md':GAME/'DELL_SETUP.md','PIPELINE_REPORTING.md':GAME/'tools/PIPELINE_REPORTING.md','learning-and-throughput-progress.json':BASE/'learning-and-throughput-progress.json','learning-and-throughput-progress.png':BASE/'learning-and-throughput-progress.png'}
    for name,path in canonical.items():(before/name).write_bytes(path.read_bytes())
    assert digest(canonical['render_learning_progress.py'])=='dd7f651b2a962dfb688051edf7b2b88b0a80768a4743e97476378dd1be7635ef'
    assert digest(canonical['DELL_SETUP.md'])=='8ce0186f8514eafe537870f7ae9ff6f412b27770aca25a3e624f99f6d9267991'
    assert digest(canonical['PIPELINE_REPORTING.md'])=='8af0cd81f610cf247b5cceeac1b9578731814d72a75f822fc94f5c14e2e73db5'
    for rel,expected in PINS.items():assert digest(BASE/rel)==expected,(rel,'source changed')
    campaign=json.loads((BASE/'sidecar-fresh3-128M-confirmed-campaign.json').read_bytes())
    analysis=json.loads((RUN/'quality128M-two-leg-final-analysis.json').read_bytes())
    promotion=json.loads((RUN/'quality128M-root-promotion-audit.json').read_bytes())
    lineage=json.loads((RUN/'fresh3-128M-checkpoint-lineage.json').read_bytes())
    assert promotion['PASS'] is True and promotion['state_changed'] is True and promotion['new_incumbent']['combined_n']==148
    assert campaign['stage']=='confirmed' and campaign['validation']['each_receipt_separately_validated'] is True
    assert analysis['management']['promotion_eligible'] is True and all(x['passes_each_criterion'] is True for x in analysis['management']['each_leg'])
    point=copy.deepcopy(campaign['descriptive_pools']['confirmed128M'])
    labels=[x['label'] for x in campaign['sources']];assert labels==['sidecar-gpu0-128M-screen-01','sidecar-gpu0-128M-confirm-01']
    scores=[];counts=[]
    for row in campaign['sources']:
        receipt_path=Path(row['path']);assert digest(receipt_path)==row['sha256']
        receipt=json.loads(receipt_path.read_bytes());assert receipt['valid'] is True and receipt['complete'] is True and receipt['count']==receipt['started'] and receipt['pending']==receipt['abandoned']==0
        scores.extend(x['score'] for x in receipt['rows']);counts.append(receipt['count'])
    assert counts==[68,80] and len(scores)==148 and statistics.mean(scores)==point['mean'] and statistics.median(scores)==point['median']
    assert statistics.stdev(scores)/len(scores)**.5==point['se']
    text=canonical['render_learning_progress.py'].read_text()
    text=text.replace('def quality_series_axis(axis, groups, title, subtitle, baseline_label, baseline_color):','def quality_series_axis(axis, groups, title, subtitle, baseline_label, baseline_color,\n                        *, positions=None, gain_reference_index=0):')
    text=text.replace('    axis.plot(range(len(groups)), means, color="#c2bdc9", lw=1.6)','    positions = list(range(len(groups))) if positions is None else positions\n    axis.plot(positions, means, color="#c2bdc9", lw=1.6)')
    text=text.replace('axis.errorbar(index, mean, yerr=error, fmt="o", ms=8, capsize=4,','axis.errorbar(positions[index], mean, yerr=error, fmt="o", ms=8, capsize=4,')
    text=text.replace('axis.text(index, mean+error+2500, f"{mean:,.0f}",','axis.text(positions[index], mean+error+2500, f"{mean:,.0f}",')
    text=text.replace('axis.set_xticks(range(len(groups)), [g["plot_label"] for g in groups])','axis.set_xticks(positions, [g["plot_label"] for g in groups])')
    text=text.replace('axis.set_xlim(-.4, len(groups)-.6)','axis.set_xlim(min(positions)-.4, max(positions)+.4)')
    text=text.replace('    gain = (means[-1]/means[0]-1)*100\n    axis.text','    gain = (means[-1]/means[gain_reference_index]-1)*100\n    axis.text')
    text=text.replace('def observational_guard_overlay(axis, groups, guards):','def observational_guard_overlay(axis, groups, guards, order=None):')
    text=text.replace('    labels = [group["plot_label"] for group in groups]\n    for index, guard in enumerate(guards, start=len(groups)):','    combined = {group["label"]: group for group in [*groups, *guards]}\n    order = list(combined) if order is None else order\n    if len(order) != len(combined) or set(order) != set(combined):\n        raise ValueError("Quality timeline must contain each confirmed point and guard once")\n    labels = [combined[label]["plot_label"] for label in order]\n    for guard in guards:\n        index = order.index(guard["label"])')
    text=text.replace('        labels.append(guard["plot_label"])\n','')
    old='''    fixed_upper, fixed_gain = quality_series_axis(fixed_ax, data["fixed_transport_learning"],
        "C  GPU0 compiled · fixed transport, 3s", "64M incumbent · hollow diamond: single-cohort 96M guard",
        "own fixed-transport 16M baseline", "#b87536")

    fixed_upper = observational_guard_overlay(fixed_ax, data["fixed_transport_learning"], data.get("observational_guards", []))'''
    new='''    fixed_groups = data["fixed_transport_learning"]
    timeline = data.get("fixed_transport_plot_order")
    positions = None if timeline is None else [timeline.index(group["label"]) for group in fixed_groups]
    fixed_upper, fixed_gain = quality_series_axis(fixed_ax, fixed_groups,
        "C  GPU0 compiled · fixed transport, 3s", "128M incumbent · hollow diamond: single-cohort 96M guard",
        "64M", "#b87536", positions=positions, gain_reference_index=-2)

    fixed_upper = observational_guard_overlay(fixed_ax, fixed_groups,
        data.get("observational_guards", []), order=timeline)'''
    assert old in text;text=text.replace(old,new)
    text=text.replace('Confirmed through 64M; 96M guard unpromoted','Confirmed through 128M; 96M guard unpromoted')
    text=text.replace('fixed_transport_gain_latest_vs_16M_pct=fixed_gain,','fixed_transport_gain_latest_vs_16M_pct=(fixed_groups[-1]["mean"] / fixed_groups[0]["mean"] - 1) * 100,\n                fixed_transport_gain_128M_vs_64M_pct=fixed_gain,')
    text=text.replace('data["fixed_transport_learning"][-1]["mean"] /\n                    data["fixed_transport_learning"][-2]["mean"]','data["fixed_transport_learning"][2]["mean"] /\n                    data["fixed_transport_learning"][1]["mean"]')
    renderer=proposed/'render_learning_progress.py';renderer.write_text(text)
    data=json.loads(canonical['learning-and-throughput-progress.json'].read_bytes());old_data=copy.deepcopy(data)
    newpoint=dict(label='GPU0 fixed-transport 128M confirmed',backend_series='gpu0-compiled-fixed-transport-3s',count=point['count'],mean=point['mean'],median=point['median'],se=point['se'],constituent_labels=labels,constituent_counts=counts,actor_slots=list(range(4096,4112)),source_receipts=[r['path'] for r in campaign['sources']],checkpoint_sha256=promotion['new_incumbent']['sha256'],unit='Descriptive original-row pool of two separately validated same-policy full-tail cohorts; not a merged receipt',plot_label='128M\nconfirmed\nn=148')
    data['fixed_transport_learning'].append(newpoint)
    data['fixed_transport_plot_order']=[x['label'] for x in data['fixed_transport_learning'][:-1]]+[data['observational_guards'][0]['label'],newpoint['label']]
    data['schema']='robotron-learning-throughput-figure-v6';data['created_utc']=datetime.now(timezone.utc).isoformat()
    data['scope']='Confirmed quality through128M, with a separate unpromoted single-cohort96M regression guard; three distinct backend series. Throughput and first natural bank events remain dated descriptive operational evidence.'
    data['caption']='\n'.join([
     'Quality: complete greedy wave-1 games at difficulty 5; mean ±1 SE, not formal confidence. Separate valid cohorts and repeated looks; recovery changes are not a causal ablation.',
     'A: historical GB300 (*4M/8M select-v1/1000 µs; earlier busy). B: earlier GPU0 transport. C: confirmed 128M +35.8% vs 64M; hollow 96M is one unpromoted guard.',
     'D: settled 2026-10-16 UTC A–B–A counter samples/s; GPU-only energy. Batch and compiler trials change learning exposure; sequential trajectories do not establish causal quality effects.',
     'First natural bank events: memmap 34 → stream 0 deadline lines; 32.813 → 33.003s overall brackets. Descriptive observations, not proof of causality or a universal fix.'])
    data['progress'].update(latest_confirmed_stage='128M',current_managed_reference='128M confirmed original148-game pool',previous64M_reference_preserved=True,GPU0_fixed_transport_gain_128M_vs_64M_pct=promotion['new_incumbent']['mean_gain_pct_vs_composite64M'])
    data['fixed_transport_provenance'].update(latest_campaign_report=str(BASE/'sidecar-fresh3-128M-confirmed-campaign.json'),**{'128M_policy_saved_clocks':lineage['candidate']['saved_metadata']})
    data['confirmed128M_selection']=dict(promoted_utc=promotion['utc'],count=148,reference_for_this_comparison='Original protected64M217 rows',current_managed_reference='128M',each_leg=analysis['management']['each_leg'],comparison=analysis['pooled_candidate_vs_composite'],root_promotion_audit=str(RUN/'quality128M-root-promotion-audit.json'),protected_checkpoint=str(GAME/promotion['new_incumbent']['checkpoint']),protected_checkpoint_sha256=promotion['new_incumbent']['sha256'],protected_metadata_sha256=promotion['new_incumbent']['metadata_sha256'],saved_policy_clocks=lineage['candidate']['saved_metadata'],optimizer_exposure=lineage['candidate']['optimizer'],scope='Root actually promoted after both separately valid passing legs; no merged valid receipt, no96M pooling, no causal batch/compiler attribution.')
    data['plotting'].update(confirmed_stage='128M (fixed-transport GPU0)',renderer=str(canonical['render_learning_progress.py']),renderer_sha256=digest(renderer),fixed_transport_score_axis_maximum=230000)
    data['validation'].update(constituent_cohort_count=22,constituent_game_count=2385,all22_receipts_revalidated=True,all2385_game_ids_disjoint=True,pooled_128M_matches_independent_campaign=True,each_128M_leg_passes_original64M_gate=True,current_managed_reference_128M=True,single96_guard_unpromoted=True,previous_fixed_transport_points_unchanged=True,model_payloads_rehashed_for_this_refresh=False,model_payload_scope='Reuse exact root publication/protection and previous source hash attestations; rendering checks small source bytes and model file stats, no model payload rehash or loading. Standard standalone renderer retains its original full payload validation.')
    extra=[BASE/rel for rel in PINS]+[RUN/'quality128M-root-promotion-audit.json',RUN/'confirmed128M-publication-proposal/build_confirmed128M_campaign.py',RUN/'confirmed128M-publication-proposal/prior-byte-pins.json',RUN/'confirmed128M-publication-proposal/independent-review.json',GAME/'models_dqn/managed-incumbents/fresh3-128M-confirmed.pt.json']
    records={r['path']:r for r in data['sources']}
    for path in extra:records[str(path)]=dict(path=str(path),sha256=digest(path))
    protected=GAME/promotion['new_incumbent']['checkpoint'];records[str(protected)]=dict(path=str(protected),sha256=promotion['new_incumbent']['sha256'])
    records[str(canonical['render_learning_progress.py'])]=dict(path=str(canonical['render_learning_progress.py']),sha256=digest(renderer))
    records[str(before/'render_learning_progress.py')]=dict(path=str(before/'render_learning_progress.py'),sha256=digest(before/'render_learning_progress.py'))
    data['sources']=list(records.values())
    dump(proposed/'learning-and-throughput-progress.json',data)
    dell=canonical['DELL_SETUP.md'].read_text()
    old='''Every admitted whole game must finish, all 16 actors must be represented, and
each leg needs at least 50 games. Runtime timeouts invalidate a leg, including'''
    new='''Every admitted whole game must finish and all 16 actors must be represented.
The official full-leg validator's 50-whole-game validity floor remains unchanged.
The 128M plan adds no extra publication count floor: retain the original whole-game
denominator and report low N as a precision caveat. Runtime timeouts invalidate
a leg, including'''
    assert old in dell;dell=dell.replace(old,new).replace('Never promote an undersized or\ninvalid cohort.','Never promote a cohort that fails its precommitted\nvalidity or quality rules.')
    dell=dell.replace('fixed-transport 16M-to-32M-to-64M series separately from','fixed-transport 16M-to-32M-to-64M-to-128M series separately from')
    dell=dell.replace('protected 64M policy and all fixed-backend quality gates remain separate.','quality assessments and their precommitted gates remain separate from this\nthroughput selection.')
    dell=dell.replace('nor the N<64 rule triggered a confirmation. Protected 64M remains the incumbent\nand reference; the scheduled 128M assessment is unchanged. The result does not','nor the N<64 rule triggered a confirmation. At that check, protected 64M remained\nthe incumbent and reference, and the 128M assessment stayed scheduled. The result does not')
    dell+='''
The subsequent 128M assessment on 2026-10-16 passed both prescribed complete
GPU0 compiled FP32/TF32 cohorts on the unchanged fixed-transport/3s backend.
The original legs contained 68 and 80 games: means 224,480.51 and 191,430.31,
medians 206,462.5 and 156,900. Each independently exceeded the precommitted
159,729.4355 mean floor (1.05 times protected 64M's original 217-game mean)
and 146,575 median floor. Every admitted late tail completed, all 16 private
slots were represented, and both legs had zero runtime inference errors.
Each leg retains 16 separately classified intentional post-cutoff cleanup
timeout diagnostics; these are not erased or counted as runtime failures.

The descriptive original-row pool contains 148 games: mean 206,615.54,
median 166,112.5 and SE 6,519.13, a 35.8211% mean gain over the original
64M reference. All 16 pooled actor-slot mean contrasts were positive.
The fixed 10,000-draw game and paired-slot bootstrap ratio sensitivities were
[1.259, 1.464] and [1.285, 1.438]; repeated looks, selection and changing
trajectories prevent interpreting these as formal confirmatory confidence.
The 96M guard remains a separate unpromoted single cohort and enters neither
this 148-game pool nor the 217-game reference.

Root protected and promoted 128M at 12:45:15.271 UTC. It is now the managed
incumbent and reference; the prior 64M policy, metadata, campaign and original
comparison rows remain preserved. The new independent readonly protected copy is
`models_dqn/managed-incumbents/fresh3-128M-confirmed.pt`, SHA256
`70bf8218fa761de97bc89c30981dfd1d779484b459ec6837ed27213735e908f1`.
Its `.pt.json` metadata and
`logs/managed-learning-20261015/sidecar-fresh3-128M-confirmed-campaign.json`
link the final root CPU lineage, both real receipts and both positive final
isolation/cleanup audits. The promotion receipt is
`logs/managed-learning-20261015/run-23/quality128M-root-promotion-audit.json`.

Saved policy clocks were 907,399 logical updates, 2,269,118,464 optimized samples
and 132,631,504 learner frames; the 81 Adam parameter states each recorded
907,002 steps. These clocks and timestamped process-local application counters
remain distinct. The learned trajectory includes the disclosed batch-size and
rejected compiler trials; this quality gain does not isolate their causal effects
or establish learning equivalence. Panel C now connects only confirmed policies
through 128M, placing the unconnected hollow 96M marker chronologically between
64M and 128M. The other quality backends and dated throughput A–B–A data remain
unchanged.
'''
    (proposed/'DELL_SETUP.md').write_text(dell)
    pipeline=canonical['PIPELINE_REPORTING.md'].read_text()
    old='observations do not change the protected 64M reference or scheduled quality gates.'
    new='observations do not themselves select or rebase a quality reference. The separately\nconfirmed 128M promotion and preserved 64M/96M history are documented in\n`../DELL_SETUP.md`; subsequent quality checks must name their fixed reference.'
    assert old in pipeline;(proposed/'PIPELINE_REPORTING.md').write_text(pipeline.replace(old,new))
    mapping={'render_learning_progress.py':'Robotron/tools/render_learning_progress.py','DELL_SETUP.md':'Robotron/DELL_SETUP.md','PIPELINE_REPORTING.md':'Robotron/tools/PIPELINE_REPORTING.md'}
    patch=''
    for name,relative in mapping.items():patch+='diff --git a/'+relative+' b/'+relative+'\n'+''.join(difflib.unified_diff((before/name).read_text().splitlines(keepends=True),(proposed/name).read_text().splitlines(keepends=True),fromfile='a/'+relative,tofile='b/'+relative))
    (OUT/'confirmed128M-reporting.patch').write_text(patch)
    retained_keys=('learning','sidecar_learning','throughput','efficiency_update','batch_aba_throughput','observational_guards','bank_output_first_events')
    retained={k:data[k]==old_data[k] for k in retained_keys};retained['prior_fixed_transport_points']=data['fixed_transport_learning'][:-1]==old_data['fixed_transport_learning'];assert all(retained.values())
    assert data['fixed_transport_provenance']['matching_receipt_fields']==old_data['fixed_transport_provenance']['matching_receipt_fields']
    assert data['fixed_transport_provenance']['job_controls']==old_data['fixed_transport_provenance']['job_controls']
    model_stats={r['path']:dict(sha256_attestation=r['sha256'],stat=dict(size_bytes=Path(r['path']).stat().st_size,mtime_ns=Path(r['path']).stat().st_mtime_ns,inode=Path(r['path']).stat().st_ino,device=Path(r['path']).stat().st_dev,mode=oct(Path(r['path']).stat().st_mode&0o777),nlink=Path(r['path']).stat().st_nlink)) for r in data['sources'] if r['path'].endswith('.pt')}
    manifest=dict(schema='robotron-confirmed128M-reporting-proposal-v1',proposal_only=True,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),before={name:dict(path=str(path),archived=str(before/name),sha256=digest(path)) for name,path in canonical.items()},proposed={p.name:dict(path=str(p),sha256=digest(p)) for p in proposed.iterdir()},patch_sha256=digest(OUT/'confirmed128M-reporting.patch'),retained_arrays=retained,canonical_untouched=all(path.read_bytes()==(before/name).read_bytes() for name,path in canonical.items()),small_evidence_pins=PINS,model_payload_refresh=dict(rehashed=False,scope='Root already verified publication/protection; source SHA attestations retained, stats only during this reporting refresh.',files=model_stats),canonical_provenance='JSON records canonical renderer path and proposed exact SHA; preview uses an explicitly recorded canonical-renderer alias substitution to the proposed file, avoiding stale proposal aliases after application.')
    assert manifest['canonical_untouched'];dump(OUT/'prepared.json',manifest)
    print(json.dumps(dict(directory=str(OUT),patch_sha256=manifest['patch_sha256'],proposed=manifest['proposed']),indent=2))
if __name__=='__main__':main()
