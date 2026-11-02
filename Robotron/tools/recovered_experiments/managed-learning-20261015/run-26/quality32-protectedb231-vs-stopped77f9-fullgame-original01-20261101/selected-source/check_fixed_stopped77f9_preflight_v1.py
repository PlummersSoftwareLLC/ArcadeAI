"""Check the four frozen jobs, review context and exact decision boundaries on CPU.

No controller launch, model runtime import or GPU operation occurs.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
F=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-protectedb231-vs-stopped77f9-fullgame-original01-20261101')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def main():
    h=load('_confirmation_preflight_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    prepared_pin=h.pin(F/'prepared-campaign.json');prepared=json.loads(h.checked(prepared_pin).read_text())
    read=lambda pin:json.loads(h.checked(pin).read_text())
    native=load('_confirmation_preflight_native',h.checked(prepared['native']))
    reviewer=load('_confirmation_preflight_reviewer',h.checked(prepared['leg_reviewer']))
    ctl=load('_confirmation_preflight_controller',h.checked(prepared['native_controller']))
    kernel=load('_confirmation_preflight_kernel',h.checked(prepared['original_decision_kernel']))
    sequence_path=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/short15-protectedb231-vs-stopped77f9-original01-20261101/future-fullgame-owned-ABI-logseal-source-original01/run_early_C1_closed_logseal_UNBOUND_v1.py')
    sequence=load('_confirmation_preflight_sequence',sequence_path)
    pair=read(prepared['pair']);family=read(prepared['source_family']);checks=[]

    def check(name,condition):
        if not condition:raise ValueError(name)
        checks.append(name)

    def rejects(name,callback):
        try:callback()
        except (ValueError,KeyError):checks.append(name);return
        raise ValueError('Invalid case accepted: '+name)

    for leg in prepared['legs']:
        job=read(leg['native_job']);pr=read(leg['native_prepared']);config=read(leg['review_job_template'])
        native.validate_job(job);native.validate_selected_family(job,h)
        reviewer.validate_bound_context(config,pr,job,pair,family,h)
        ctl.checked_config(leg['native_controller_config']['path'])
        check(leg['role']+' exact native/controller/reviewer binding',True)
        for key,value in [('checkpoint',pair['roles']['candidate'if leg['model_role']=='reference'else'reference']['policy']),
                          ('engineering_only',True),('actor_slots',job['actor_slots'][:-1])]:
            bad=copy.deepcopy(job);bad[key]=value
            rejects(leg['role']+' rejects changed '+key,
                    lambda bad=bad:reviewer.validate_bound_context(config,pr,bad,pair,family,h))
        display=sequence.project_display(leg,'reviewing',job,None,None)
        check(leg['role']+' pending review cannot claim completion',display['complete']is False and display['valid']is None)
        rejects(leg['role']+' rejects foreign display policy',lambda:sequence.project_display(
            leg,'native_running',job,None,{'policy':{'checkpoint_sha256':'0'*64}}))

    def fixtures(c1=1050,c2=1050):
        legs=[]
        for index,role in enumerate(('R1','C1','R2','C2')):
            scores=([1000]*64 if role.startswith('R')else[c1 if role=='C1'else c2]*64)
            rows=[dict(journal_game_id=role+'-'+str(i),client_slot=4096+i//2,score=score,
                       complete=True,eligible=True,known_start=True,excluded_reason='')for i,score in enumerate(scores)]
            stats=kernel.metrics(scores)
            cohort=dict(closed=True,complete=True,valid=True,pending=0,abandoned=0,pending_ids=[],abandoned_ids=[],
                rows=rows,started_ids=[r['journal_game_id']for r in rows],count=64,started=64,closed_by='slot_quota',
                slot_admitted_counts={str(slot):2 for slot in kernel.SLOTS},started_actor_slots=list(kernel.SLOTS),
                **{k:stats[k]for k in ('mean','median','sd','se')})
            legs.append(dict(role=role,cohort=cohort,cohort_selection=copy.deepcopy(kernel.COHORT_SELECTION),
                policy_sha256='reference'if role.startswith('R')else'candidate',native_identity=(index,1,'native'),
                review_identity=(index,1,'review'),evidence_verified=True,original_attempt=1,no_retry=True))
        return legs

    decide=lambda legs:kernel.assess_validated_cohorts(legs,'reference','candidate')
    check('exact +5 percent boundary passes both separate cohorts',decide(fixtures())['all_candidate_gates_passed'])
    check('below +5 percent boundary fails',not decide(fixtures(c1=1049))['all_candidate_gates_passed'])
    decision=decide(fixtures(c1=1100,c2=1000))
    check('pooled +5 percent cannot rescue C2 failure',not decision['all_candidate_gates_passed']and decision['candidate_pool_used']is False)
    legs=fixtures();rows=legs[1]['cohort']['rows']
    for i,row in enumerate(rows):row['score']=0 if i<33 else 10000
    stats=kernel.metrics([r['score']for r in rows]);legs[1]['cohort'].update({k:stats[k]for k in ('mean','median','sd','se')})
    check('high mean cannot rescue lower median',not decide(legs)['all_candidate_gates_passed'])
    legs=fixtures();legs[1]['cohort']['rows'].pop()
    rejects('63 finished games cannot pass',lambda:decide(legs))
    legs=fixtures();legs[1]['cohort']['rows'][0]['journal_game_id']=legs[0]['cohort']['rows'][0]['journal_game_id']
    rejects('reused game cannot pass',lambda:decide(legs))
    check('preflight imported no Torch', 'torch'not in sys.modules)
    report=h.put(F/'preflight-CPU-original01.json',dict(status='PASS_FIXED_CONFIRMATION_PREFLIGHT',prepared=prepared_pin,
        sequence_source=h.pin(sequence_path),checker_source=h.pin(__file__),observed_unix_s=time.time(),
        checks=checks,checks_total=len(checks),CPU_only=True,scientific_job_launched=False,
        statistical_confidence_qualified=False,promotion=False))
    print(json.dumps(dict(status='PASS_FIXED_CONFIRMATION_PREFLIGHT',checks=len(checks),report=report)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
