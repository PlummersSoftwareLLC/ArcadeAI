#!/usr/bin/env python3
"""Prepare reporting copies only; no canonical, training, model or state writes."""
from datetime import datetime, timezone
import copy
import difflib
import hashlib
import json
from pathlib import Path
import statistics

REPO=Path(__file__).resolve().parents[4]
GAME=REPO/'Robotron';CAMPAIGN=GAME/'logs/managed-learning-20261015';RUN=CAMPAIGN/'run-20'
OUT=RUN/'guard96-reporting-proposal'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    OUT.mkdir()
    canonical={'render_learning_progress.py':GAME/'tools/render_learning_progress.py','DELL_SETUP.md':GAME/'DELL_SETUP.md','PIPELINE_REPORTING.md':GAME/'tools/PIPELINE_REPORTING.md','learning-and-throughput-progress.json':CAMPAIGN/'learning-and-throughput-progress.json','learning-and-throughput-progress.png':CAMPAIGN/'learning-and-throughput-progress.png'}
    for name,path in canonical.items():
        dest=OUT/'before'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
    proposed=OUT/'proposed';proposed.mkdir()
    text=canonical['render_learning_progress.py'].read_text()
    text=text.replace('*data.get("fixed_transport_learning", [])]:','*data.get("fixed_transport_learning", []), *data.get("observational_guards", [])]:')
    anchor='    batch_trials = validate_batch_aba(data)\n'
    text=text.replace(anchor,'''    for guard in data.get("observational_guards", []):
        if (guard["role"] != "single-cohort-regression-guard" or guard["promoted"] is not False
                or len(guard["source_receipts"]) != 1):
            raise ValueError("Guard must remain a separate unpromoted single cohort")
    event = data.get("bank_output_first_events")
    if event is not None:
        compared = json.loads(Path(event["comparison_source"]).read_bytes())
        if event["comparison"] != compared["comparison"]:
            raise ValueError("Bank event observation differs from its pinned comparison")
    batch_trials = validate_batch_aba(data)
''')
    text=text.replace('                validated_batch_trials=batch_trials,','                validated_batch_trials=batch_trials,\n                observational_guard_count=len(data.get("observational_guards", [])),')
    anchor='\n\ndef validate_batch_aba(data):'
    overlay='''\n\ndef observational_guard_overlay(axis, groups, guards):
    if not guards:
        return axis.get_ylim()[1]
    labels = [group["plot_label"] for group in groups]
    for index, guard in enumerate(guards, start=len(groups)):
        axis.errorbar(index, guard["mean"], yerr=guard["se"], fmt="D", ms=8,
            mfc="white", mec="#bc7a20", mew=1.7, ecolor="#bc7a20", capsize=4, zorder=4)
        axis.text(index, guard["mean"]+guard["se"]+2500, f"{guard['mean']:,.0f}",
            ha="center", va="bottom", fontsize=10, fontweight="bold", color="#9c661b")
        labels.append(guard["plot_label"])
    axis.set_xticks(range(len(labels)), labels)
    axis.set_xlim(-.4, len(labels)-.6)
    upper = math.ceil(max([axis.get_ylim()[1], *[g["mean"]+g["se"]+9000 for g in guards]])/10000)*10000
    axis.set_ylim(0, upper)
    axis.set_yticks(range(0, upper+1, 40000))
    return upper
'''
    assert anchor in text;text=text.replace(anchor,overlay+anchor)
    text=text.replace('"16M reference → 32M → 64M · latest +25.5% vs 32M",','"64M incumbent · hollow diamond: single-cohort 96M guard",')
    anchor='    batch_aba_axis(rate_ax, data["batch_aba_throughput"])\n'
    text=text.replace(anchor,'    fixed_upper = observational_guard_overlay(fixed_ax, data["fixed_transport_learning"], data.get("observational_guards", []))\n\n'+anchor)
    text=text.replace('Robotron · confirmed learning progress and training throughput','Robotron · learning progress and training throughput')
    text=text.replace('Confirmed quality through {stage}; three separate quality series · selected training: batch 4096 / 192 actors','Confirmed through 64M; 96M guard unpromoted · three separate quality series · batch 4096 / 192 actors')
    renderer=proposed/'render_learning_progress.py';renderer.write_text(text)
    data=json.loads(canonical['learning-and-throughput-progress.json'].read_bytes())
    receipt_path=CAMPAIGN/'sidecar-gpu0-96M-regression-guard-01/receipt.json';receipt=json.loads(receipt_path.read_bytes())
    analysis_path=CAMPAIGN/'run-19/quality96M-guard-first-analysis.json';assert digest(analysis_path)=='fd01088bbbc860083ef7f115bdd488aaaff19ec59ab3958163402007edd3f6cd';analysis=json.loads(analysis_path.read_bytes())
    audit_path=RUN/'quality96M-first-final-independent-audit.json';audit=json.loads(audit_path.read_bytes());assert audit['PASS'] is True and receipt['valid'] is True and receipt['complete'] is True and receipt['count']==receipt['started']==81
    management=analysis['management'];assert management['confirmation_still_needed'] is False and management['promotion'] is False and management['reference_rebased'] is False
    rows=receipt['rows'];scores=[row['score'] for row in rows]
    guard=dict(label='96M single-cohort regression guard (unpromoted)',backend_series='gpu0-compiled-fixed-transport-3s',role='single-cohort-regression-guard',promoted=False,count=len(rows),mean=statistics.mean(scores),median=statistics.median(scores),se=statistics.stdev(scores)/len(scores)**.5,constituent_labels=[receipt['label']],constituent_counts=[81],actor_slots=list(range(4096,4112)),source_receipts=[str(receipt_path)],checkpoint_sha256=receipt['checkpoint_sha256'],unit='One separately valid whole-game cohort; regression guard only, not a confirmed or promoted incumbent',plot_label='96M guard\nunpromoted\nn=81',management_analysis=str(analysis_path),management=management)
    assert guard['mean']==receipt['mean'] and guard['median']==receipt['median']
    data['observational_guards']=[guard]
    comparison_path=RUN/'natural-bank-stream-vs-memmap-independent-comparison.json';assert digest(comparison_path)=='b5bfe48ec56fc1bfba4a9c175edd605a6a05194bf14ff8db55bb89148f2e5a97';comparison=json.loads(comparison_path.read_bytes())
    data['bank_output_first_events']=dict(comparison_source=str(comparison_path),comparison=comparison['comparison'],interpretation='Two dated, sequential first natural events only: memmap34 -> stream0 deadline lines. Whole observation brackets32.813 ->33.003s do not show whole-save acceleration. Different live policy, snapshot payload and unknown host work prevent causal or universal reliability claims.',next_event_result_included=False,default_stream_flag=False,current_trial_stream_flag=True)
    data['created_utc']=datetime.now(timezone.utc).isoformat()
    data['scope']='Confirmed quality through64M plus a separate single-cohort96M regression guard; three distinct backend series. Throughput and first natural bank events are descriptive operational evidence.'
    data['caption']='\n'.join(['Quality: complete greedy wave-1 games at difficulty 5; mean ±1 SE, not formal confidence. Separate valid cohorts; recovery changes are not a causal ablation.','A: historical GB300 (*4M/8M select-v1/1000 µs; earlier busy). B: earlier GPU0 transport. C: fixed transport; hollow 96M marker is one unpromoted cohort. Protected 64M and all tails remain.','D: settled 2026-10-16 UTC A–B–A counter samples/s; GPU-only energy. Batch 4096 changes optimizer exposure; sequential policy/replay/RNG drift prevents learning-equivalence claims.','First natural bank events: memmap 34 → stream 0 deadline lines; 32.813 → 33.003s overall brackets. Descriptive observations, not proof of causality or a universal fix.'])
    extra=[receipt_path,analysis_path,audit_path,CAMPAIGN/'run-19/fresh3-96M-checkpoint-lineage.json',RUN/'natural-bank-stream-independent-audit.json',comparison_path,RUN/'natural-bank-stream-published-files-audit.json',CAMPAIGN/'run-19/natural-bank-memmap-independent-audit.json',renderer]
    existing={row['path'] for row in data['sources']}
    for path in extra:
        if str(path) not in existing:data['sources'].append(dict(path=str(path),sha256=digest(path)));existing.add(str(path))
    data['plotting']['proposal_renderer_path']=str(renderer);data['plotting']['proposal_renderer_sha256']=digest(renderer);data['plotting']['fixed_transport_score_axis_maximum']=230000
    data['validation'].update(constituent_cohort_count=20,constituent_game_count=2237,all20_receipts_revalidated=True,all2237_game_ids_disjoint=True,single96_guard_unpromoted=True,protected64M_reference_unchanged=True,first_stream_event_descriptive_only=True)
    output_json=proposed/'learning-and-throughput-progress.json';output_json.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    dell=canonical['DELL_SETUP.md'].read_text();old='Run20 began a separate `DQN_STREAM_BANK_OUTPUT=1` trial. No natural bank result\nfrom that trial is reported here; the flag or a clean startup is not proof of a fix.\n'
    new='''Run20's first natural streaming event on 2026-10-16 published both banks with\nzero write errors, inference deadlines or journal disconnects, preserving all\n192 actor identities. The earlier memmap event retains its 34 deadline errors.\nObserved full capture/write brackets were 32.813 s (memmap) and 33.003 s (stream);\nthis does not show a faster whole save. Live policy, snapshot payload and\nuncontrolled host work differ. This first pair supports continued observation\nof the opt-in trial, not a causal speedup or universal reliability fix. See\n`logs/managed-learning-20261015/run-20/natural-bank-stream-vs-memmap-independent-comparison.json`.\nThe flag remains default OFF; the current trial is ON. The next natural event\nis not included in this result.\n'''
    assert old in dell;dell=dell.replace(old,new)
    dell+='''\nThe prescribed 96M regression guard on 2026-10-16 completed all 81 admitted\ngames, including every late tail: mean 205,422.22, median 169,600 and SE 8,846.83.\nThe same GPU0 compiled FP32/TF32 backend as both 64M legs passed full validation,\nwith zero runtime timeouts and owned cleanup complete. This is one observational\ncohort, not a confirmed or promoted policy. Neither the fixed mean/median alarm\nnor the N<64 rule triggered a confirmation. Protected 64M remains the incumbent\nand reference; the scheduled 128M assessment is unchanged. The result does not\nestablish a causal batch-size effect or formal noninferiority. The progress\nfigure uses an unconnected hollow marker for this guard. Evidence is in\n`logs/managed-learning-20261015/run-19/quality96M-guard-first-analysis.json` and\n`logs/managed-learning-20261015/run-20/quality96M-first-final-independent-audit.json`.\n'''
    (proposed/'DELL_SETUP.md').write_text(dell)
    pipeline=canonical['PIPELINE_REPORTING.md'].read_text();old='''Run20 began a separate streaming-enabled trial. No result from its first natural
bank event is included here; the enabled flag and startup observations do not
establish a reliability fix or causal performance improvement. The trial plan is
`logs/managed-learning-20261015/run-20/natural-bank-observer-plan.json`.
''';new='''Run20's first natural streaming event published both banks without write errors,
main inference deadlines or journal disconnects; all 192 pinned actors survived.
The memmap baseline retains its 34 deadline errors. Overall observed capture/write
brackets were 32.813 s versus 33.003 s, so this is not evidence of a faster whole
save. Policy, snapshot payload and uncontrolled host work changed; no causal
speedup or universal reliability fix is established. The default remains OFF and
the separate trial is ON. See
`logs/managed-learning-20261015/run-20/natural-bank-stream-vs-memmap-independent-comparison.json`.
No subsequent natural-event result is included here.
''';assert old in pipeline;(proposed/'PIPELINE_REPORTING.md').write_text(pipeline.replace(old,new))
    mapping={'render_learning_progress.py':'Robotron/tools/render_learning_progress.py','DELL_SETUP.md':'Robotron/DELL_SETUP.md','PIPELINE_REPORTING.md':'Robotron/tools/PIPELINE_REPORTING.md'}
    patch=''
    for name,relative in mapping.items():
        patch+='diff --git a/'+relative+' b/'+relative+'\n'+''.join(difflib.unified_diff((OUT/'before'/name).read_text().splitlines(keepends=True),(proposed/name).read_text().splitlines(keepends=True),fromfile='a/'+relative,tofile='b/'+relative))
    (OUT/'guard96-reporting.patch').write_text(patch)
    manifest=dict(schema='robotron-guard96-reporting-proposal-v1',proposal_only=True,utc=data['created_utc'],before={name:dict(path=str(path),sha256=digest(path)) for name,path in canonical.items()},proposed={p.name:dict(path=str(p),sha256=digest(p)) for p in proposed.iterdir()},patch_sha256=digest(OUT/'guard96-reporting.patch'),old_quality_arrays_unchanged=all(data[k]==json.loads((OUT/'before/learning-and-throughput-progress.json').read_bytes())[k] for k in ('learning','sidecar_learning','fixed_transport_learning','throughput','efficiency_update','batch_aba_throughput')),canonical_untouched=True)
    assert manifest['old_quality_arrays_unchanged'];(OUT/'prepared.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(proposal=str(OUT),patch_sha256=manifest['patch_sha256']),indent=2))

if __name__=='__main__':main()
