"""Test future scheduler flow using removed /tmp fixtures and no real children.

Only the controller boundary is mocked. The actual prepared Sequence.run,
early-decision validation and final publisher execute. No synthetic original
receipt survives outside the explicitly labelled CPU fixture directories.
"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
F=G/'logs/managed-learning-20261015/run-26/quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def main():
    h=load('_future_sequence_CPU_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    pp=h.pin(F/'future-early-C1-sequence-original01/source-preparation.json');proof=json.loads(h.checked(pp).read_text())
    m=load('_actual_future_sequence_CPU',h.checked(proof['source']))
    auth=json.loads(h.checked(proof['authenticated_assessor_preparation']).read_text())
    np=json.loads(h.checked(auth['numeric_CPU39']).read_text())
    checks=[]

    def check(name,value):
        if not value:raise ValueError(name)
        checks.append(name)

    old_ast=ast.parse(h.checked(proof['parent']).read_text());new_ast=ast.parse(h.checked(proof['source']).read_text())
    old_class=next(n for n in old_ast.body if isinstance(n,ast.ClassDef)and n.name=='Sequence')
    new_class=next(n for n in new_ast.body if isinstance(n,ast.ClassDef)and n.name=='Sequence')
    for name in ('invoke','CPU_config','reporter','publish','read','update'):
        a=next(n for n in old_class.body if getattr(n,'name',None)==name)
        b=next(n for n in new_class.body if getattr(n,'name',None)==name)
        check(name+' retains original AST',ast.dump(a)==ast.dump(b))

    def fixture(root):
        game=root/'Robotron';case=game/'logs/managed-learning-20261015/run-26/CPU_ONLY_fixture_NOT_SCIENTIFIC'
        case.mkdir(parents=True);(game/'html').mkdir()
        pair=h.put(case/'pair.json',dict(CPU_FIXTURE=True))
        rule=h.put(case/'rule.json',dict(schema='robotron-predeclared-fullgame-C1-failure-rule-v1',campaign_directory=str(case),pair=pair,
            required_closed_roles=['R1','C1','R2'],stage='after_R2_review_before_C2_launch',skip_C2_only_if_C1_gate_failed=True,
            promotion_shortcut_allowed=False,assessor=auth['source'],numeric_gate=np['source'],scheduler=proof['source']))
        family=h.put(case/'family.json',dict(sequence_source=proof['source'],pair=pair,early_C1_assessor=auth['source'],
            early_C1_numeric=np['source'],early_C1_rule=rule))
        reviewer=h.put(case/'reviewer-CPU-FIXTURE.json',dict(CPU_FIXTURE=True))
        assessor=h.put(case/'four-leg-assessor-CPU-FIXTURE.json',dict(CPU_FIXTURE=True))
        controller=h.put(case/'controller-CPU-FIXTURE.json',dict(CPU_FIXTURE=True));legs=[]
        for index,role in enumerate(('R1','C1','R2','C2'),1):
            d=case/role;d.mkdir();rd=d/'independent-review-original01';rd.mkdir()
            native=h.put(d/'job.json',dict(CPU_FIXTURE=True,quality_leg=role,source_family_manifest=family,quality_pair_precommit=pair,
                inputs=[rule],output=str(d/'runtime-original01'),checkpoint=dict(sha256='fixture-policy')))
            prepared=h.put(d/'prepared.json',dict(CPU_FIXTURE=True,job=native))
            cfg=h.put(d/'native-config.json',dict(CPU_FIXTURE=True,job=native))
            review=h.put(d/'review-template.json',dict(CPU_FIXTURE=True,runtime=reviewer,role=role,
                original_native_closeout_path=str(d/'native-close.json'),report=str(rd/'report.json')))
            legs.append(dict(index=index,role=role,model_role='reference'if role.startswith('R')else'candidate',directory=str(d),
                native_job=native,native_prepared=prepared,native_controller_config=cfg,review_job_template=review,
                native_closeout_path=str(d/'native-close.json'),review_closeout_path=str(d/'review-close.json'),
                display_live_path=str(d/'display-live.json'),display_receipt_path=str(d/'display-receipt.json')))
        prepared=dict(campaign_directory=str(case),pair=pair,source_family=family,sequence_source=proof['source'],
            early_C1_rule=rule,early_C1_assessor=auth['source'],early_C1_numeric=np['source'],early_C1_numeric_CPU_proof=auth['numeric_CPU39'],
            native_controller=controller,CPU_controller=controller,leg_reviewer=reviewer,campaign_assessor=assessor,
            original_decision_kernel=np['original_kernel'],legs=legs)
        job=dict(CPU_FIXTURE=True,runtime=proof['source']);jobpin=h.put(case/'sequence-job.json',job);job['job_path']=jobpin['path']
        return game,case,job,prepared

    fixture_roots=[]
    for scenario in ('C1_fail','C1_pass','early_CPU_nonzero','foreign_early_report'):
        with tempfile.TemporaryDirectory(prefix='robotron-early-C1-CPU-',dir='/tmp')as td:
            fixture_roots.append(td);game,case,job,prepared=fixture(Path(td))
            with patch.object(m,'G',game),patch.object(m,'CASE',case):
                check(scenario+' valid fresh precommit accepted',m.validate_future_prepared(job,prepared,h)==case)
                seq=m.Sequence.__new__(m.Sequence);seq.job=job;seq.h=h;seq.prepared=prepared
                seq.lock=threading.Lock();seq.publish_lock=threading.Lock();seq.stop=threading.Event();seq.worker=None
                seq.state=dict(stage='prepared',current=None,finished={},terminal=False,error=None,assessment=None)
                seq.results=[];seq.display_errors=[];seq.native_controller=seq.cpu_controller=None
                seq.read=lambda pin,as_json=True:json.loads(h.checked(pin).read_text())
                events=[];seq.publish=lambda:None
                def config(directory,unit,runtime,jp):
                    return h.put(directory/'controller-config.json',dict(CPU_FIXTURE=True,runtime=runtime,job=jp))
                seq.CPU_config=config
                def invoke(directory,cfgpin,controller_pin,controller):
                    cfg=seq.read(cfgpin);payload=seq.read(cfg['job']);closed={}
                    for name in ('result','closure','owner'):closed[name]=h.put(directory/('CPU-FIXTURE-'+name+'.json'),dict(CPU_FIXTURE=True))
                    if payload.get('quality_leg'):
                        role=payload['quality_leg'];events.append('native:'+role);out=Path(payload['output']);out.mkdir()
                        result=dict(complete=True,errors=[],all_original_threads_stopped=True,original_lease_released=True,
                            original_slots={str(i):dict(actual_exit=0,pid=100000000+i,birth=1,outputs_sealed_after_original_writer_closure=True)for i in range(32)})
                        h.put(out/'result.json',result)
                    elif payload.get('schema')=='robotron-predeclared-early-C1-three-leg-assessment-v1':
                        events.append('early-assessment')
                        if scenario=='early_CPU_nonzero':return None,closed,1
                        failed=scenario=='C1_fail'
                        report=dict(status='PASS_AUTHENTICATED_PREDECLARED_C1_FAILURE_ASSESSMENT',valid=True,original_job=cfg['job'],runtime=payload['runtime'],
                            pair=payload['pair'],source_family=payload['source_family'],predeclared_rule=payload['predeclared_rule'],
                            stop_remaining_legs=failed,C2_required=not failed,promotion_eligible=False,cancellation_or_scheduling_performed=False)
                        if scenario=='foreign_early_report':report['pair']={}
                        h.put(payload['report'],report)
                    elif payload.get('schema')=='robotron-fixed-b231-1c-four-leg-assessment-v1':
                        events.append('four-leg-assessment');h.put(payload['report'],dict(valid=True,all_candidate_gates_passed=True))
                    else:
                        events.append('review:'+payload['role']);h.put(payload['report'],dict(valid=True,full_game_score_verified=True,
                            cohort=dict(count=64,started=64,pending=0,mean=1000,median=1000,se=0)))
                    return None,closed,0
                seq.invoke=invoke
                actual=seq.run()
                natives=[e for e in events if e.startswith('native:')];reviews=[e for e in events if e.startswith('review:')]
                if scenario=='C1_pass':
                    check('C1 pass requires original C2 launch',natives==['native:R1','native:C1','native:R2','native:C2'])
                    check('C1 pass reviews all4 cohorts',len(reviews)==4)
                    check('C1 pass performs unchanged four-leg assessment',events[-1]=='four-leg-assessment'and actual==0)
                else:
                    check(scenario+' never launches C2',natives==['native:R1','native:C1','native:R2'])
                    check(scenario+' only first3 reviews',len(reviews)==3)
                    check(scenario+' no fabricated fourth assessment','four-leg-assessment'not in events)
                    check(scenario+' exit semantics',actual==(0 if scenario=='C1_fail'else 1))
                check(scenario+' early assessment occurs after R2 review',events.index('early-assessment')>events.index('review:R2'))
                check(scenario+' reporter stops',not seq.worker.is_alive())
                result=seq.read(h.pin(case/'original-sequence-result.json'))
                check(scenario+' no promotion performed',result['promotion_performed']is False)
                if scenario=='C1_fail':
                    seq.publish_locked();status=json.loads((case/'status.json').read_text());skip=json.loads((case/'C2/display-live.json').read_text())
                    check('C1 failure ends valid non-improved campaign',status['state']=='finished'and status['outcome']=='not_improved_C1')
                    check('skipped C2 is not marked finished',status['legs'][3]['state']=='skipped')
                    check('skipped C2 has no completion/validity/score credit',skip['complete']is False and skip['valid']is None and skip['cohort']=={})
                    check('skipped C2 runtime directory absent',not(case/'C2/runtime-original01').exists())

    # Prelaunch refusal contracts use fresh immutable pin fixtures each time.
    for damage in ('active_case','active_pair','rule_missing','dirty_output','consumed_launch','wrong_scheduler','wrong_assessor'):
        with tempfile.TemporaryDirectory(prefix='robotron-early-C1-guard-',dir='/tmp')as td:
            fixture_roots.append(td);game,case,job,prepared=fixture(Path(td))
            if damage=='active_case':prepared['campaign_directory']=str(m.ACTIVE_CASE)
            elif damage=='active_pair':prepared['pair']['sha256']='9ea5d482628964107a0543665239c5147599e543c0e3ecd0d51b759e8c7e6b62'
            elif damage=='dirty_output':(case/'R1/runtime-original01').mkdir()
            elif damage=='consumed_launch':(case/'R1/controller-original-launch.json').write_text('{}')
            elif damage=='wrong_scheduler':job['runtime']={}
            elif damage=='wrong_assessor':prepared['early_C1_assessor']={}
            elif damage=='rule_missing':
                leg=prepared['legs'][1];native=json.loads(h.checked(leg['native_job']).read_text());native['inputs']=[]
                leg['native_job']=h.put(case/'C1/bad-inputs-job.json',native)
            with patch.object(m,'G',game),patch.object(m,'CASE',case):
                try:m.validate_future_prepared(job,prepared,h)
                except (ValueError,KeyError):checks.append('prelaunch rejects '+damage)
                else:raise ValueError('Bad future precommit accepted: '+damage)
    check('all synthetic receipt directories removed',all(not Path(p).exists()for p in fixture_roots))
    check('no Torch imported','torch'not in sys.modules)
    packet=h.put(F/'future-early-C1-sequence-original01/CPU-flow-contracts-original01.json',dict(
        status='PASS_FUTURE_EARLY_C1_SCHEDULER_CPU_FIXTURES_ONLY',source_preparation=pp,source=proof['source'],checker=h.pin(__file__),
        tests_total=len(checks),checks=checks,controller_boundary_explicitly_mocked=True,
        actual_Sequence_run_early_validation_and_final_publisher_executed=True,all_synthetic_receipt_directories_removed=True,
        real_native_or_review_or_archive_or_GPU_jobs_executed=False,active_sources_or_PUBLIC_or_units_changed=False,
        fresh_future_case_sourcefamily_precommit_and_preflight_still_required=True,promotion=False))
    print(json.dumps(dict(status='PASS_FUTURE_EARLY_C1_SCHEDULER_CPU_FIXTURES_ONLY',tests=len(checks),packet=packet)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
