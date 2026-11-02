"""Prepare and test a prospective exact C1-failure decision; no live changes.

After three independently reviewed full cohorts, C1's failure already makes
promotion impossible. A future precommitted scheduler may skip C2 in that case.
This cannot accept a winner early or infer population confidence. The active
four-leg campaign remains unchanged and this source does not schedule work.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
F=G/'logs/managed-learning-20261015/run-26/quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--output',type=Path);args=p.parse_args()
    if not args.execute:p.print_help();return 0
    h=load('_early_C1_prepare_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    prepared=json.loads((F/'prepared-campaign.json').read_text());pin=prepared['original_decision_kernel']
    kernel=load('_early_C1_original_kernel',h.checked(pin))
    original=inspect.getsource(kernel.assess_validated_cohorts);text=original;edits=[]

    def replace(before,after):
        nonlocal text
        assert text.count(before)==1,before
        text=text.replace(before,after,1);edits.append((before,after))

    replace('def assess_validated_cohorts(', 'def assess_first_candidate(')
    replace('Exactly original R1/C1/R2/C2 order required','Exactly reviewed original R1/C1/R2 order required')
    replace("for role in ('C1','C2'):","for role in ('C1',):")
    start=text.index('    return dict(fixed_fresh_reference=reference,')
    old_return=text[start:]
    replace(old_return,"""    c1=candidates['C1']
    return dict(status='C1_GATE_FAILED_C2_MAY_BE_SKIPPED'if not c1['passed']else'C1_PASSED_C2_REQUIRED',
        fixed_fresh_reference=reference,reference_roles=['R1','R2'],candidate_C1=c1,
        stop_remaining_legs=not c1['passed'],C2_required=c1['passed'],
        promotion_eligible=False,population_confidence_qualified=False,
        reference_pool_size=128,candidate_C1_size=64,candidate_pool_used=False,
        decision_scope='Exact precommitted promotion gate only; no claim of population inferiority.',
        scheduling_or_cancellation_performed=False)
""")
    back=text
    for before,after in reversed(edits):assert back.count(after)==1;back=back.replace(after,before,1)
    assert back==original
    # All per-cohort validity/coverage/statistics checks and numerical gates
    # retain their original source. Only the role domain, C1 loop and result
    # projection differ; ORDER is explicitly bound to the first three roles.
    header='''"""Prospective exact C1 failure certificate. Never a promotion decision.

Caller must independently verify all three original full-game receipts using
its precommitted raw reviewers before setting evidence_verified. This module
does not authenticate runtime receipts, start/stop games, or replace a selected
campaign. A future scheduler must precommit this rule before its first score.
"""
import hashlib
import importlib.util
from pathlib import Path
import sys
'''
    header+=f"ORIGINAL_KERNEL_PATH={pin['path']!r}\nORIGINAL_KERNEL_SHA256={pin['sha256']!r}\n"
    header+='''path=Path(ORIGINAL_KERNEL_PATH)
if hashlib.sha256(path.read_bytes()).hexdigest()!=ORIGINAL_KERNEL_SHA256:
    raise ValueError('Original numerical kernel changed')
spec=importlib.util.spec_from_file_location('_early_C1_exact_original_kernel',path)
original=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original;spec.loader.exec_module(original)
ORDER=('R1','C1','R2')
ROLES=original.ROLES
SLOTS=original.SLOTS
COHORT_SELECTION=original.COHORT_SELECTION
require=original.require
metrics=original.metrics
json=original.json
math=original.math

'''
    source=header+text
    compile(source,'<prospective-early-C1>','exec');args.output.mkdir(mode=0o700)
    target=args.output/'assess_early_C1_rejection_v1.py'
    with target.open('x')as out:out.write(source);out.flush();os.fsync(out.fileno());os.fchmod(out.fileno(),0o444)
    future=load('_early_C1_actual_generated_source',target);checks=[]

    def fixtures(c1=1050,c2=1050):
        result=[]
        for i,role in enumerate(('R1','C1','R2','C2')):
            scores=[1000]*64 if role.startswith('R')else[c1 if role=='C1'else c2]*64
            rows=[dict(journal_game_id=f'{role}:{j}',client_slot=4096+j//2,score=score,
                complete=True,eligible=True,known_start=True,excluded_reason='')for j,score in enumerate(scores)]
            cohort=dict(closed=True,complete=True,valid=True,pending=0,abandoned=0,pending_ids=[],abandoned_ids=[],
                count=64,started=64,rows=rows,started_ids=[r['journal_game_id']for r in rows],closed_by='slot_quota',
                slot_admitted_counts={str(s):2 for s in kernel.SLOTS},started_actor_slots=list(kernel.SLOTS))
            cohort.update({k:v for k,v in kernel.metrics(scores).items()if k in ('mean','median','sd','se')})
            result.append(dict(role=role,cohort=cohort,cohort_selection=copy.deepcopy(kernel.COHORT_SELECTION),
                policy_sha256='reference'if role.startswith('R')else'candidate',native_identity=(i,1,'native'),
                review_identity=(i,1,'review'),evidence_verified=True,original_attempt=1,no_retry=True))
        return result

    def assess(legs):return future.assess_first_candidate(legs[:3],'reference','candidate')
    def check(name,value):
        if not value:raise ValueError(name)
        checks.append(name)
    def rejects(name,legs):
        try:assess(legs)
        except (ValueError,KeyError):checks.append(name);return
        raise ValueError('Invalid evidence accepted: '+name)

    # Differential checks exercise the original fourth cohort, including an
    # arbitrarily strong C2, without ever supplying a synthetic real receipt.
    for score in (0,999,1000,1049,1050,1051,1100,10**18):
        legs=fixtures(c1=score,c2=10**18);decision=assess(legs)
        full=kernel.assess_validated_cohorts(legs,'reference','candidate')
        check(f'C1 {score}: exact original decision agrees',decision['candidate_C1']==full['independent_candidates']['C1'])
        check(f'C1 {score}: later C2 cannot rescue C1 failure',not decision['stop_remaining_legs']or not full['all_candidate_gates_passed'])
        check(f'C1 {score}: early promotion impossible',decision['promotion_eligible']is False)
    legs=fixtures();rows=legs[1]['cohort']['rows']
    for i,row in enumerate(rows):row['score']=0 if i<33 else 10000
    legs[1]['cohort'].update({k:v for k,v in kernel.metrics([r['score']for r in rows]).items()if k in ('mean','median','sd','se')})
    check('higher mean cannot rescue lower C1 median',assess(legs)['stop_remaining_legs'])
    for name,mutate in [
        ('incomplete tail',lambda l:l[1]['cohort'].update(complete=False)),
        ('63 rows',lambda l:l[1]['cohort']['rows'].pop()),
        ('pending game',lambda l:l[1]['cohort'].update(pending=1)),
        ('wrong reference policy',lambda l:l[0].update(policy_sha256='candidate')),
        ('unverified raw evidence',lambda l:l[1].update(evidence_verified=False)),
        ('scientific retry',lambda l:l[1].update(original_attempt=2)),
        ('wrong slot count',lambda l:l[1]['cohort']['slot_admitted_counts'].update({'4096':1})),
        ('wrong saved mean',lambda l:l[1]['cohort'].update(mean=999999)),
        ('foreign selection',lambda l:l[1]['cohort_selection'].update(games_per_slot=1)),
        ('duplicate native owner',lambda l:l[1].update(native_identity=l[0]['native_identity'])),
        ('duplicate game',lambda l:l[1]['cohort']['rows'][0].update(journal_game_id=l[0]['cohort']['rows'][0]['journal_game_id'])),
        ('boolean score',lambda l:l[1]['cohort']['rows'][0].update(score=True)),
    ]:
        legs=fixtures();mutate(legs);rejects(name,legs)
    legs=fixtures();legs[0],legs[1]=legs[1],legs[0];rejects('wrong three-leg order',legs)
    check('no Torch imported','torch'not in sys.modules)
    packet=h.put(args.output/'CPU-source-preparation.json',dict(status='PASS_PROSPECTIVE_EXACT_C1_REJECTION_CPU_ONLY',
        original_kernel=pin,source=h.pin(target),generator=h.pin(__file__),exact_reverse_edit_proof=True,
        declared_edits=[dict(before=a,after=b)for a,b in edits],tests_total=len(checks),tests=checks,
        caller_must_authenticate_all3_original_closed_full_game_reviews=True,
        future_scheduler_precommit_and_integration_required=True,selected_or_deployed=False,
        active_original_sequence_changed=False,scientific_job_launched=False,promotion=False))
    print(json.dumps(dict(status='PASS_PROSPECTIVE_EXACT_C1_REJECTION_CPU_ONLY',tests=len(checks),packet=packet)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
