"""Exercise the future assessor with explicitly synthetic in-memory receipts.

The archive adapter is a CPU fixture, not proof of real unit/game closure. No
fixture receipt is written as scientific evidence and no service is started.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
F=G/'logs/managed-learning-20261015/run-26/quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def main():
    h=load('_CPU_early_C1_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    prep_pin=h.pin(F/'future-authenticated-early-C1-original01/source-preparation.json')
    prep=json.loads(h.checked(prep_pin).read_text());module=load('_CPU_actual_early_C1_assessor',h.checked(prep['source']))
    numeric_proof=json.loads(h.checked(prep['numeric_CPU_preparation']).read_text())
    numeric=load('_CPU_actual_early_C1_numeric',h.checked(numeric_proof['source']))
    checks=[]

    def fixture(c1=1050):
        objects={};case=F.parent/'CPU_ONLY_future_early_C1_fixture_NOT_A_CAMPAIGN'
        def put(name,value):
            pin=dict(path=str(case/name),sha256='f'*64)
            objects[pin['path']]=copy.deepcopy(value);return pin
        pair=put('pair.json',dict(roles={role:dict(policy=dict(sha256=sha))for role,sha in [('reference','reference'),('candidate','candidate')]}))
        rule=put('rule.json',dict(schema='robotron-predeclared-fullgame-C1-failure-rule-v1',campaign_directory=str(case),pair=pair,
            required_closed_roles=['R1','C1','R2'],stage='after_R2_review_before_C2_launch',skip_C2_only_if_C1_gate_failed=True,
            promotion_shortcut_allowed=False,assessor=prep['source'],numeric_gate=numeric_proof['source']))
        family=put('family.json',dict(pair=pair,early_C1_assessor=prep['source'],early_C1_rule=rule,
            early_C1_numeric=numeric_proof['source'],decision_kernel=numeric_proof['original_kernel'],leg_reviewer=dict(sha256='reviewer')))
        legs=[]
        for index,role in enumerate(('R1','C1','R2')):
            sha='reference'if role.startswith('R')else'candidate';scores=[1000 if role.startswith('R')else c1]*64
            rows=[dict(journal_game_id=f'{role}:{i}',client_slot=4096+i//2,score=score,
                complete=True,eligible=True,known_start=True,excluded_reason='')for i,score in enumerate(scores)]
            cohort=dict(closed=True,complete=True,valid=True,pending=0,abandoned=0,pending_ids=[],abandoned_ids=[],
                rows=rows,started_ids=[r['journal_game_id']for r in rows],count=64,started=64,closed_by='slot_quota',
                slot_admitted_counts={str(s):2 for s in numeric.SLOTS},started_actor_slots=list(numeric.SLOTS))
            cohort.update({k:v for k,v in numeric.metrics(scores).items()if k in ('mean','median','sd','se')})
            jobpin=put(f'{role}/job.json',dict(quality_leg=role,source_family_manifest=family,checkpoint=dict(sha256=sha),inputs=[rule]))
            prepared=put(f'{role}/prepared.json',dict(job=jobpin,pair=pair))
            result=put(f'{role}/native-result.json',dict(complete=True,errors=[],original_attempt=1,no_retry=True,before_intentional_stop=cohort))
            def owner_and_closure(kind):
                identity=f'{role}-{kind}'
                owner=put(f'{role}/{kind}-owner.json',dict(pid=100000000+2*index+(kind=='review'),starttime_ticks=100,invocation_id=identity))
                closure=put(f'{role}/{kind}-closure.json',dict(CPU_FIXTURE=True,valid=True,owner=owner,original_exit=0))
                return owner,closure
            owner,closure=owner_and_closure('native')
            native=put(f'{role}/native-close.json',dict(status='PASS_ORIGINAL_FULLGAME_LEG_NATIVE_SCOPE_CLOSED',actual_exit=0,
                original_Popen_reaped=True,all_original_controller_resources_closed=True,native_result=result,owner=owner,closure=closure))
            report=put(f'{role}/review-report.json',dict(status='PASS_SCIENTIFIC_FULLGAME_LEG_RAW64_PREFIX32_PERMIT_STOP32_BOUNDED_MAIN',
                valid=True,full_game_score_verified=True,slot_permit_body_hash_replay_performed=True,role=role,pair=pair,
                native_job=jobpin,native_result=result,original_native_closeout=native,review_runtime=dict(sha256='reviewer'),
                numeric_policy=dict(dtype='float32'),compile_report=dict(all_shapes_verified=list(range(1,17))),
                policy_sha256=sha,cohort=cohort,cohort_selection=numeric.COHORT_SELECTION))
            owner,closure=owner_and_closure('review')
            review=put(f'{role}/review-close.json',dict(status='PASS_ORIGINAL_FULLGAME_LEG_REVIEW_SCOPE_CLOSED',actual_exit=0,
                original_Popen_reaped=True,all_original_controller_resources_closed=True,report=report,owner=owner,closure=closure))
            legs.append(dict(role=role,prepared=prepared,native_closeout=native,review_closeout=review))
        job=dict(schema='robotron-predeclared-early-C1-three-leg-assessment-v1',campaign_directory=str(case),pair=pair,source_family=family,
            legs=legs,predeclared_rule=rule,numeric_gate=copy.deepcopy(numeric_proof['source']),numeric_CPU_proof=copy.deepcopy(prep['numeric_CPU_preparation']),
            original_decision_kernel=copy.deepcopy(numeric_proof['original_kernel']))
        def read(pin,as_json=True):
            if pin['path']in objects:return copy.deepcopy(objects[pin['path']])
            require=module.require;require(as_json is True,'Unexpected CPU fixture binary read')
            return json.loads(h.checked(pin).read_text())
        return job,objects,SimpleNamespace(read_pin=read)

    def run(job,objects,reader):
        actual_load=module.load
        def archive_fixture(closure,owner,read,exit_zero=True):
            module.require(closure['CPU_FIXTURE']is True and closure['valid']is True
                and closure['original_exit']==0 and exit_zero is True,'Synthetic archive contract failed')
            module.require(read(closure['owner'])==owner,'Synthetic archive owner mismatch')
            return {}
        def dispatch(name,path):
            if name=='_fixed_fullgame_assessment_archive':return SimpleNamespace(archived_closure=archive_fixture)
            return actual_load(name,path)
        with patch.object(module,'load',side_effect=dispatch):return module.assess(job,h,reader)

    def check(name,value):
        if not value:raise ValueError(name)
        checks.append(name)
    def reject(name,mutate):
        job,objects,reader=fixture();mutate(job,objects)
        try:run(job,objects,reader)
        except (ValueError,KeyError):checks.append(name);return
        raise ValueError('Invalid synthetic evidence accepted: '+name)
    def obj(objects,pin):return objects[pin['path']]
    def native(objects,job,leg=1):return obj(objects,job['legs'][leg]['native_closeout'])
    def review(objects,job,leg=1):return obj(objects,job['legs'][leg]['review_closeout'])
    def report(objects,job,leg=1):return obj(objects,review(objects,job,leg)['report'])
    def native_job(objects,job,leg=1):return obj(objects,obj(objects,job['legs'][leg]['prepared'])['job'])

    for score in (1049,1050,1100):
        job,objects,reader=fixture(score);r=run(job,objects,reader)
        check(f'C1 {score}: actual bound helper determines skip correctly',r['stop_remaining_legs']is(score<1050))
        check(f'C1 {score}: no early promotion or cancellation',r['promotion_eligible']is False and r['cancellation_or_scheduling_performed']is False)
    cases=[
        ('active campaign excluded',lambda j,o:j.update(campaign_directory=str(F))),
        ('active fixed pair excluded',lambda j,o:j['pair'].update(sha256=module.PAIR_SHA)),
        ('C2 cannot join three-leg assessment',lambda j,o:j['legs'].append(dict(j['legs'][1],role='C2'))),
        ('missing R2 rejected',lambda j,o:j['legs'].pop()),
        ('wrong role order rejected',lambda j,o:j['legs'].reverse()),
        ('undeclared stage rejected',lambda j,o:obj(o,j['predeclared_rule']).update(stage='after_C1')),
        ('promotion shortcut refused',lambda j,o:obj(o,j['predeclared_rule']).update(promotion_shortcut_allowed=True)),
        ('different numerical helper refused',lambda j,o:j['numeric_gate'].update(sha256='wrong')),
        ('rule absent from original C1 inputs',lambda j,o:native_job(o,j).update(inputs=[])),
        ('foreign native source family',lambda j,o:native_job(o,j).update(source_family_manifest={})),
        ('wrong native exit',lambda j,o:native(o,j).update(actual_exit=1)),
        ('unreaped native refused',lambda j,o:native(o,j).update(original_Popen_reaped=False)),
        ('native resources still open',lambda j,o:native(o,j).update(all_original_controller_resources_closed=False)),
        ('wrong independent review exit',lambda j,o:review(o,j).update(actual_exit=1)),
        ('independent reviewer still running',lambda j,o:review(o,j).update(original_Popen_reaped=False)),
        ('incomplete raw review refused',lambda j,o:report(o,j).update(valid=False)),
        ('missing full-game verification',lambda j,o:report(o,j).update(full_game_score_verified=False)),
        ('missing slot body replay',lambda j,o:report(o,j).update(slot_permit_body_hash_replay_performed=False)),
        ('foreign review role',lambda j,o:report(o,j).update(role='C2')),
        ('wrong review runtime',lambda j,o:report(o,j).update(review_runtime={})),
        ('mixed numerical policies',lambda j,o:report(o,j).update(numeric_policy={'dtype':'other'})),
        ('unverified compiled shape',lambda j,o:report(o,j)['compile_report'].update(all_shapes_verified=[1])),
        ('wrong frozen policy',lambda j,o:report(o,j).update(policy_sha256='other')),
        ('wrong native closeout linked',lambda j,o:report(o,j).update(original_native_closeout={})),
        ('archive closure failure',lambda j,o:obj(o,native(o,j)['closure']).update(valid=False)),
        ('original scoped process still live',lambda j,o:obj(o,native(o,j)['owner']).update(
            pid=os.getpid(),starttime_ticks=module.birth(os.getpid()))),
        ('reused original native identity',lambda j,o:obj(o,native(o,j)['owner']).update(obj(o,native(o,j,0)['owner']))),
        ('incomplete original result',lambda j,o:obj(o,native(o,j)['native_result']).update(complete=False)),
        ('original scientific errors',lambda j,o:obj(o,native(o,j)['native_result']).update(errors=['fixture error'])),
        ('scientific retry refused',lambda j,o:obj(o,native(o,j)['native_result']).update(original_attempt=2)),
        ('native no-retry flag lost',lambda j,o:obj(o,native(o,j)['native_result']).update(no_retry=False)),
        ('report cohort differs from original',lambda j,o:report(o,j)['cohort']['rows'][0].update(score=999999)),
    ]
    for name,mutate in cases:reject(name,mutate)
    check('no numerical runtime imported','torch'not in sys.modules)
    packet=h.put(F/'future-authenticated-early-C1-original01/CPU-contracts-original01.json',dict(
        status='PASS_PROSPECTIVE_AUTHENTICATED_C1_CPU_FIXTURES_ONLY',source_preparation=prep_pin,source=prep['source'],
        checker=h.pin(__file__),tests_total=len(checks),checks=checks,
        archive_adapter_explicitly_synthetic=True,no_real_native_or_review_receipt_authenticated=True,
        original_archive_call_and_closed_leg_checks_retained_by_source_AST_proof=True,
        source_or_rule_selected_for_active_campaign=False,scheduler_integration_still_required=True,
        no_scientific_services_or_GPU_jobs_started=True,promotion=False))
    print(json.dumps(dict(status='PASS_PROSPECTIVE_AUTHENTICATED_C1_CPU_FIXTURES_ONLY',tests=len(checks),packet=packet)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
