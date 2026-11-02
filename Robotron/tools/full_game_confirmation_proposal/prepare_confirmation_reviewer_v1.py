"""Derive the fixed scientific reviewer from the successful raw engineering review.

Original ROM/START, all64 natural-terminal/life/quota, actual STOP/Lua/ledger
and current-v6 physical/API kernels stay. Scientific context and archived full
slot bodies are mandatory; immutable repeated binding events are cached then
individually rehashed at close for bounded six-hour review capacity.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
C=B/'post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
F=B/'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'

CONTEXT="""def validate_bound_context(config,prepared,job,pair,family,h):
    role=job['quality_leg']
    require(role in ('R1','C1','R2','C2')and config['role']==role
        and job['quality_pair_precommit']['sha256']==PAIR_SHA
        and pair['schema']=='robotron-protectedb231-vs-postreboot1c-fullgame-fixed-pair-v1'
        and pair['ordered_legs']==['R1','C1','R2','C2']
        and not job.get('engineering_only')and job['actor_slots']==list(range(4096,4128)),
        'Exact fixed scientific pair/role/all32 scope required')
    selected=pair['roles']['reference'if role.startswith('R')else'candidate']
    require(job['checkpoint']==selected['policy']and job['expected_policy_clocks']==selected['saved_clocks']
        and prepared['native']==job['runtime']and prepared['pair']==job['quality_pair_precommit']
        and family['schema']=='robotron-current-v6-fullgame-confirmation-source-family-v1'
        and family['pair']==job['quality_pair_precommit']and family['native']==job['runtime']
        and family['leg_reviewer']==h.pin(__file__)
        and family['wire_auditor']==config['wire_auditor']and family['games_auditor']==config['original_games']
        and family['current_Main_health']==job['current_v6_health_source']
        and family['slot_closeout']==job['quota64_source_pins']['slot_closeout'],
        'Original policy/CPU clocks/native/reviewer/wire/health family changed')
    cpu=json.loads(h.checked(selected['CPU_report']).read_text())
    close=json.loads(h.checked(selected['original_CPU_readback']).read_text())
    require(cpu['status']=='PASS_FRESH_CPU_ROLE_POLICY_AND_INFERENCE'
        and cpu['checkpoint']==job['checkpoint']and cpu['clocks']==job['expected_policy_clocks']
        and cpu['CPU_only']is True and cpu['CUDA_initialized']is False
        and close['actual_exit']==0 and close['all_original_CPU_resources_closed']is True,
        'Fresh original CPU role verification and positive owned closure required')
    require(Path(prepared['job']['path']).parent.is_relative_to(CASE)
        and Path(config['report']).parent==Path(prepared['job']['path']).parent/'independent-review-original01',
        'Fresh fixed-case review namespace required')
    return selected


"""


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    p=G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py';sp=importlib.util.spec_from_file_location('_confirmation_reviewer_prepare_h',p);h=importlib.util.module_from_spec(sp);sys.modules[sp.name]=h;sp.loader.exec_module(h)
    parent_job=json.loads((C/'fullgame-evaluator-live-engineering-original01-20261101/independent-raw-review-original01/job.json').read_text())
    parent=h.checked(parent_job['runtime']);original=parent.read_text();source=original;edits=[]
    pair=h.pin(F/'fixed-pair-precommit.json')
    def replace(old,new):
        nonlocal source
        assert source.count(old)==1;source=source.replace(old,new,1);edits.append((old,new))
    gline="G=Path('/home/dave/source/repos/ArcadeAI/Robotron')\n"
    replace(gline,gline+'PAIR_SHA='+repr(pair['sha256'])+'\nCASE=Path('+repr(str(F))+')\n')
    replace('def review(config,h,reader):\n',CONTEXT+'def review(config,h,reader):\n')
    start=source.index("    terminal=read(config['original_terminal'])");end=source.index("    archive=load(",start)
    replacement="""    pair=read(job['quality_pair_precommit']);family=read(job['source_family_manifest'])
    selected=validate_bound_context(config,prepared,job,pair,family,h)
    terminal=read(config['original_native_closeout'])
    require(terminal['status']=='PASS_ORIGINAL_FULLGAME_LEG_NATIVE_SCOPE_CLOSED'
        and terminal['actual_exit']==0 and terminal['original_job']==jp
        and terminal['original_Popen_reaped']is True and terminal['all_original_controller_resources_closed']is True
        and result['complete']is True and result['errors']==[]and not result.get('engineering_only')
        and result['original_attempt']==1 and result['no_retry']is True
        and result['original_job']==jp and result['all_original_threads_stopped']is result['original_lease_released']is True,
        'Original scientific scope did not close normally')
"""
    replace(source[start:end],replacement)
    replace("    fields=archive.archived_closure(close,owner,read,exit_zero=True)\n",
        "    fields=archive.archived_closure(close,owner,read,exit_zero=True)\n"
        "    controller_config=read(prepared['controller_config'])\n"
        "    require(' '.join(controller_config['argv'])+' ; ignore_errors=no ;'in fields['ExecStart']\n"
        "        and terminal['original_controller_config']==prepared['controller_config'],\n"
        "        'Actual original command differs from the fixed native/job/source pins')\n")
    replace("RuntimeMaxUSec='10min'","RuntimeMaxUSec='6h 11min'")
    replace("    wire_preparation=read(config['wire_preparation']);wire_pin=wire_preparation['source']",
        "    wire_pin=config['wire_auditor'];read(wire_pin,False)")
    replace("    tails=[];receipts=[]\n","    tails=[];receipts=[]\n    archived_permits={r['slot']:r['full_slot_permit']for r in result['slot_retirement_closeout']['slots']}\n    require(set(archived_permits)==set(range(4096,4128)),'All32 actual archived permit bodies required')\n")
    replace('policy,window,selected_rows=selected))',
        "policy,window,selected_rows=selected,slot_permit_record=archived_permits[slot]))")
    replace('    accepted=0;pending=0;previous=None;previous_begin=None;max_gap=0;bindings={};pending_begin=None',
        '    accepted=0;pending=0;previous=None;previous_begin=None;max_gap=0;bindings={};binding_cache={};pending_begin=None')
    replace("            require(read(pin)==event,'Actual captured binding differs from immutable event')",
        "            cached=binding_cache.get(pin['path'])\n"
        "            if cached is None:\n"
        "                value=read(pin);binding_cache[pin['path']]=(pin,value)\n"
        "            else:\n"
        "                require(cached[0]==pin,'An immutable binding path changed identity')\n"
        "                value=cached[1]\n"
        "            require(value==event,'Actual captured binding differs from immutable event')")
    start=source.index("    idle=read(h.pin(out/'original-compiled-engineering-idle-actions.json'))")
    end=source.index("    for pin in job['inputs']:",start)
    replace(source[start:end],"    require(result['compile_report']['all_shapes_verified']==list(range(1,17))\n"
        "        and policy['numeric_policy']['compiled']is True,'Actual common float32 compiled backend not ready')\n")
    anchor="    for pin in job['inputs']:h.checked(pin)\n"
    replace(anchor,"    loaded=read(h.pin(out/'original-loaded-policy.json'))\n"
        "    unused_expert_proof=bool(policy['epsilon']==policy['expert_ratio']==0\n"
        "        and policy['training_enabled']is False and loaded['replay_enabled']is False\n"
        "        and loaded['memory_is_none']is loaded['optimizer_is_none']is True)\n"
        "    require(unused_expert_proof,'Frozen greedy no-replay/no-optimizer allowance not proven')\n"
        "    evaluator_logs=original_reviewer.audit_evaluator_logs(\n"
        "        read(h.pin(root/'execution-original01/stdout.txt'),False).decode(),\n"
        "        read(h.pin(root/'execution-original01/stderr.txt'),False).decode(),policy,unused_expert_proof,\n"
        "        expected_closed_client_ids={p['client_id']for p in prefixes.values()})\n"+anchor)
    replace("status='PASS_ENGINEERING_RAW64_PREFIX32_SLOT_STOP32_BOUNDED_MAIN_WITH_PERMIT_BODY_GAP'",
        "status='PASS_SCIENTIFIC_FULLGAME_LEG_RAW64_PREFIX32_PERMIT_STOP32_BOUNDED_MAIN'")
    replace("original_terminal=config['original_terminal']","original_native_closeout=config['original_native_closeout']")
    replace('        source01_full_slot_permit_bodies_not_archived=True,slot_permit_body_hash_replay_performed=False,',
        '        valid=True,full_game_score_verified=True,role=job[\'quality_leg\'],pair=job[\'quality_pair_precommit\'],\n'
        '        policy_sha256=job[\'checkpoint\'][\'sha256\'],cohort=cohort,cohort_selection=policy[\'cohort_selection\'],\n'
        '        numeric_policy=policy[\'numeric_policy\'],compile_report=result[\'compile_report\'],\n'
        '        original_native_owner=owner,slot_permit_body_hash_replay_performed=True,')
    replace("        required_before_scientific_source_selection='Persist full per-slot permit bodies with exact source proof and CPU contracts; do not synthesize missing bodies for this original engineering run.',\n",'')
    replace('current_scientific_source_family_qualified=False','candidate_promotion_qualified=False')
    replace('        actor_logs=actor_logs,early_slot_retirements_before_global_completion=len(early),',
        '        actor_logs=actor_logs,evaluator_logs=evaluator_logs,early_slot_retirements_before_global_completion=len(early),')
    replace("status='FAIL_INDEPENDENT_ENGINEERING_RAW_REVIEW'","status='FAIL_INDEPENDENT_SCIENTIFIC_FULLGAME_LEG_REVIEW'")
    reverted=source
    # The one deleted engineering-only note belongs just before raw-tail scope.
    for old,new in reversed(edits):
        if new:assert reverted.count(new)==1;reverted=reverted.replace(new,old,1)
        else:
            marker='        raw_postprefix_frames_reconstructed=False,'
            assert reverted.count(marker)==1;reverted=reverted.replace(marker,old+marker,1)
    assert reverted==original
    compile(source,'<fixed-scientific-fullgame-review>','exec')
    target=F/'selected-source/review_fixed_fullgame_leg_v1.py'
    with target.open('x')as f:f.write(source);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
    packet=h.put(F/'selected-source/reviewer-preparation.json',dict(status='FIXED_SCIENTIFIC_REVIEWER_SOURCE_BOUND_NOT_JOB_QUALIFIED',
        pair=pair,parent_successful_engineering_reviewer=parent_job['runtime'],leg_reviewer=h.pin(target),generator=h.pin(Path(__file__)),
        exact_declared_edits_revert_to_parent=True,declared_edits=len(edits),
        original_raw_ROM_START_clock_input_all64_terminal_ROM_life_quota_and_STOP_Lua_ledger_kernels_retained=True,
        all32_actual_full_slot_permit_bodies_required_and_hashed=True,
        immutable_binding_cache_requires_exact_pin_and_end_rehash=True,scientific_job_launched=False,promotion=False))
    print(json.dumps(dict(status='FIXED_SCIENTIFIC_REVIEWER_SOURCE_BOUND_NOT_JOB_QUALIFIED',packet=packet)));return 0


if __name__=='__main__':raise SystemExit(main())
