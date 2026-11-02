"""Prospective exact C1 failure certificate. Never a promotion decision.

Caller must independently verify all three original full-game receipts using
its precommitted raw reviewers before setting evidence_verified. This module
does not authenticate runtime receipts, start/stop games, or replace a selected
campaign. A future scheduler must precommit this rule before its first score.
"""
import hashlib
import importlib.util
from pathlib import Path
import sys
ORIGINAL_KERNEL_PATH='/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-protocol-interface-correction-original01/assess_quality32_quota64_selected_original01_v2.py'
ORIGINAL_KERNEL_SHA256='6b6bdc1230c50db5b143c7f86f5e150b08f0e25dfb75a4615ab8d460b5623bf2'
path=Path(ORIGINAL_KERNEL_PATH)
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

def assess_first_candidate(legs,reference_sha,candidate_sha):
    """Numerical decision only; the executable separately proves all receipts."""
    require(type(legs)is list and [leg['role']for leg in legs]==list(ORDER),'Exactly reviewed original R1/C1/R2 order required')
    require(reference_sha!=candidate_sha,'Distinct fixed reference and candidate policies required')
    ids=set();native_ids=set();review_ids=set();summaries={};scores={}
    for leg in legs:
        role=leg['role'];cohort=leg['cohort']
        require(leg['evidence_verified']is True and leg['original_attempt']==1 and leg['no_retry']is True,
            'Each original leg must have independent actual runtime/review evidence')
        require(leg['policy_sha256']==(reference_sha if ROLES[role]=='reference'else candidate_sha),
            'Original leg policy role changed')
        for value,seen in [(tuple(leg['native_identity']),native_ids),(tuple(leg['review_identity']),review_ids)]:
            require(value not in seen,'Original leg native/review identity reused');seen.add(value)
        require(cohort['closed']is cohort['complete']is cohort['valid']is True
            and cohort['pending']==cohort['abandoned']==0
            and cohort['pending_ids']==cohort['abandoned_ids']==[],'Each original full tail must finish validly')
        rows=cohort['rows'];started=cohort['started_ids'];row_ids=[row['journal_game_id']for row in rows]
        require(type(cohort['count'])is int and cohort['count']==cohort['started']==len(rows)==len(started)==64
            and cohort['closed_by']=='slot_quota'
            and cohort['slot_admitted_counts']=={str(slot):2 for slot in SLOTS}
            and len(set(started))==len(started)and set(started)==set(row_ids)and len(set(row_ids))==len(rows),
            'Original admitted denominator lost a game or duplicated evidence')
        require(not ids.intersection(started),'A game was reused across independent cohorts');ids.update(started)
        require(cohort['started_actor_slots']==list(range(4096,4128))
            and {row['client_slot']for row in rows}==set(range(4096,4128)),
            'Every original quality leg requires all32 slots')
        require(all(row['complete']is row['eligible']is row['known_start']is True
            and row['excluded_reason']==''for row in rows),'An original quality game is incomplete/excluded')
        require(all(sum(row['client_slot']==slot for row in rows)==2 for slot in SLOTS),
            'Every original slot must contribute exactly its two selected full games')
        require(json.dumps(leg['cohort_selection'],sort_keys=True,separators=(',',':'),allow_nan=False)
            ==json.dumps(COHORT_SELECTION,sort_keys=True,separators=(',',':'),allow_nan=False),
            'Original leg count selection strategy/bounds changed')
        scores[role]=[row['score']for row in rows];summary=metrics(scores[role])
        for key in ('count','mean','median','sd','se'):
            require(type(cohort[key])in (int,float)and math.isfinite(cohort[key])
                and math.isclose(cohort[key],summary[key],rel_tol=1e-12,abs_tol=1e-9),
                'Saved cohort statistics differ from all original games')
        summaries[role]=summary
    reference=metrics(scores['R1']+scores['R2'])
    require(reference['score_sum']>0,'A positive fixed reference is required for a percentage improvement')
    candidates={}
    for role in ('C1',):
        candidate=summaries[role]
        # Exact integer comparison avoids floating-point boundary changes.
        mean_pass=candidate['score_sum']*reference['count']*20>=reference['score_sum']*candidate['count']*21
        median_pass=candidate['median_twice']>=reference['median_twice']
        candidates[role]=dict(**candidate,mean_ratio=candidate['mean']/reference['mean'],
            median_ratio=(candidate['median']/reference['median']if reference['median']else None),
            mean_at_least_105_percent=mean_pass,median_preserved=median_pass,passed=mean_pass and median_pass)
    c1=candidates['C1']
    return dict(status='C1_GATE_FAILED_C2_MAY_BE_SKIPPED'if not c1['passed']else'C1_PASSED_C2_REQUIRED',
        fixed_fresh_reference=reference,reference_roles=['R1','R2'],candidate_C1=c1,
        stop_remaining_legs=not c1['passed'],C2_required=c1['passed'],
        promotion_eligible=False,population_confidence_qualified=False,
        reference_pool_size=128,candidate_C1_size=64,candidate_pool_used=False,
        decision_scope='Exact precommitted promotion gate only; no claim of population inferiority.',
        scheduling_or_cancellation_performed=False)
