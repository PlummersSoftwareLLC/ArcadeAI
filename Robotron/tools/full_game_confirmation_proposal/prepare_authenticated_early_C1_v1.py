"""Prepare a future receipt-authenticated C1 failure assessor, without launch.

The active campaign is explicitly excluded. Every original closed-leg check is
inherited from its frozen four-leg assessor. Future native jobs must include
the same immutable early-stop rule before their first score.
"""
import argparse
import ast
import importlib.util
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
    h=load('_prepare_authenticated_C1_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    prepared=json.loads((F/'prepared-campaign.json').read_text());parent=h.checked(prepared['campaign_assessor'])
    numeric_packet=h.pin(F/'future-early-C1-rejection-original01/CPU-source-preparation.json')
    numeric=json.loads(h.checked(numeric_packet).read_text());assert numeric['tests_total']==39
    source=parent.read_text();original=source;edits=[]

    def replace(before,after):
        nonlocal source
        assert source.count(before)==1,before
        source=source.replace(before,after,1);edits.append((before,after))

    end=source.index('"""',3)+3
    replace(source[:end],'"""Authenticate a future predeclared three-leg C1 failure decision.\n\nNever schedules, cancels or promotes. Current active campaign is excluded.\n"""')
    replace("ORDER=('R1','C1','R2','C2')","ORDER=('R1','C1','R2')\nNUMERIC_GATE_SHA="+repr(numeric['source']['sha256']))
    marker='def assess(job,h,reader):\n'
    validation='''def validate_future_precommit(job,h,read):
    case=Path(job['campaign_directory'])
    require(job['schema']=='robotron-predeclared-early-C1-three-leg-assessment-v1'
        and case.is_absolute() and case.resolve()==case and case.is_relative_to(G/'logs/managed-learning-20261015/run-26')
        and case!=CASE and job['pair']['sha256']!=PAIR_SHA
        and [r['role']for r in job['legs']]==list(ORDER),
        'Fresh future case and exact original first-three roles required; active campaign excluded')
    rule=read(job['predeclared_rule'])
    require(rule['schema']=='robotron-predeclared-fullgame-C1-failure-rule-v1'
        and rule['campaign_directory']==str(case) and rule['pair']==job['pair']
        and rule['required_closed_roles']==list(ORDER)
        and rule['stage']=='after_R2_review_before_C2_launch'
        and rule['skip_C2_only_if_C1_gate_failed']is True
        and rule['promotion_shortcut_allowed']is False
        and rule['assessor']==h.pin(__file__) and rule['numeric_gate']==job['numeric_gate']
        and job['numeric_gate']['sha256']==NUMERIC_GATE_SHA,
        'Exact future predeclared rule/numerical helper/source required')
    proof=read(job['numeric_CPU_proof'])
    require(proof['status']=='PASS_PROSPECTIVE_EXACT_C1_REJECTION_CPU_ONLY'
        and proof['tests_total']==39 and proof['source']==job['numeric_gate']
        and proof['original_kernel']==job['original_decision_kernel']
        and proof['exact_reverse_edit_proof']is True,
        'Qualified original numeric source derivation required')
    return case,rule


'''
    replace(marker,validation+marker)
    old="""    require(job['schema']=='robotron-fixed-b231-1c-four-leg-assessment-v1'and job['pair']['sha256']==PAIR_SHA
        and Path(job['campaign_directory'])==CASE and [r['role']for r in job['legs']]==list(ORDER),
        'Exact original four-role campaign required')
"""
    replace(old,'    case,rule=validate_future_precommit(job,h,read)\n')
    replace("family['campaign_assessor']==h.pin(__file__)","family['early_C1_assessor']==h.pin(__file__)\n        and family['early_C1_rule']==job['predeclared_rule']\n        and family['early_C1_numeric']==job['numeric_gate']")
    replace("h.checked(job['original_decision_kernel'])","h.checked(job['numeric_gate'])")
    replace("role=item['role'];prepared=read(item['prepared']);native_job=read(prepared['job'])",
        "role=item['role'];prepared=read(item['prepared']);native_job=read(prepared['job'])\n"
        "        require(job['predeclared_rule']in native_job['inputs'],\n"
        "            'This same immutable early-stop rule must have been a checked input of every original leg')")
    replace(".parent.is_relative_to(CASE)",".parent.is_relative_to(case)")
    replace('decision=kernel.assess_validated_cohorts(', 'decision=kernel.assess_first_candidate(')
    replace("status='PASS_ORIGINAL_FIXED_FOUR_LEG_ASSESSMENT'","status='PASS_AUTHENTICATED_PREDECLARED_C1_FAILURE_ASSESSMENT'")
    replace("decision=decision,all_candidate_gates_passed=decision['all_candidate_gates_passed'],\n        promotion_eligible=decision['all_candidate_gates_passed'],promotion_performed=False,",
        "decision=decision,stop_remaining_legs=decision['stop_remaining_legs'],C2_required=decision['C2_required'],\n"
        "        predeclared_rule=job['predeclared_rule'],promotion_eligible=False,promotion_performed=False,\n"
        "        cancellation_or_scheduling_performed=False,C2_execution_status_not_assessed=True,")
    replace("'Observed fixed-protocol full-game confirmation. No causal learning-rate/throughput or independently calibrated population-confidence claim.'",
        "'Exact impossibility of promotion if fully reviewed C1 fails; passing C1 still requires C2. No population inferiority, confidence or throughput claim.'")
    replace("status='FAIL_ORIGINAL_FIXED_FOUR_LEG_ASSESSMENT'","status='FAIL_AUTHENTICATED_PREDECLARED_C1_ASSESSMENT'")
    back=source
    for before,after in reversed(edits):assert back.count(after)==1;back=back.replace(after,before,1)
    assert back==original
    # Apart from the fresh-case domain and an ADDITIONAL precommit input
    # requirement, the entire original closed-leg authentication loop remains.
    old_tree=ast.parse(original);new_tree=ast.parse(source)
    old_fn=next(n for n in old_tree.body if isinstance(n,ast.FunctionDef)and n.name=='assess')
    new_fn=next(n for n in new_tree.body if isinstance(n,ast.FunctionDef)and n.name=='assess')
    old_loop=next(n for n in old_fn.body if isinstance(n,ast.For))
    new_loop=next(n for n in new_fn.body if isinstance(n,ast.For))
    normalized=ast.unparse(new_loop).replace('.parent.is_relative_to(case)','.parent.is_relative_to(CASE)')
    normalized_tree=ast.parse(normalized).body[0]
    # The added require is the fourth statement after role/prepared/job reads.
    assert isinstance(normalized_tree.body[3],ast.Expr)
    assert 'immutable early-stop rule' in ast.unparse(normalized_tree.body[3])
    normalized_tree.body.pop(3)
    assert ast.dump(normalized_tree,include_attributes=False)==ast.dump(old_loop,include_attributes=False)
    compile(source,'<future-authenticated-C1-assessor>','exec');args.output.mkdir(mode=0o700)
    target=args.output/'assess_authenticated_early_C1_v1.py'
    with target.open('x')as out:out.write(source);out.flush();os.fsync(out.fileno());os.fchmod(out.fileno(),0o444)
    proof=h.put(args.output/'source-preparation.json',dict(status='FUTURE_AUTHENTICATED_C1_SOURCE_NOT_CPU_TESTED_OR_SELECTED',
        source=h.pin(target),parent=prepared['campaign_assessor'],generator=h.pin(__file__),numeric_CPU_preparation=numeric_packet,
        exact_reverse_edit_proof=True,all_original_closed_leg_authentication_AST_retained=True,
        additional_rule_must_be_in_all3_original_native_inputs=True,active_case_and_pair_explicitly_excluded=True,
        edits=[dict(before=a,after=b)for a,b in edits],future_scheduler_precommit_required=True,
        no_cancellation_or_scheduling_or_promotion=True,selected_or_deployed=False))
    print(json.dumps(dict(status='FUTURE_AUTHENTICATED_C1_SOURCE_NOT_CPU_TESTED_OR_SELECTED',proof=proof)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
