"""Independently join four closed fullgame legs to the unchanged quota64 gates.

Default inert. No scientific launch, retry, policy installation, main mutation,
learning-speed claim, throughput claim, or pooling of candidate scores.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation')
LOCAL=Path(__file__).resolve().parent


def pipeline():
    spec=importlib.util.spec_from_file_location('_fullgame_study_assessment_pipeline',LOCAL/'fullgame_review_pipeline_v7.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def assess(precommit,expected_sha,output):
    p=pipeline();h=p.helpers();commit_pin=h.pin(precommit.resolve());p.require(commit_pin['sha256']==expected_sha,'Exact review precommit required')
    commit=p.read(commit_pin)
    p.require(commit['schema']=='robotron-four-fullgame-independent-review-precommit-v1'and commit['engineering_only']is False,
        'Engineering reviews cannot qualify a production fullgame study')
    p.require(commit['ordered_legs']==[case['leg']for case in commit['cases']]==p.ORDER
        and commit['assessor']==h.pin(Path(__file__).resolve())and commit['pipeline']==h.pin(LOCAL/'fullgame_review_pipeline_v7.py')
        and commit['leg_reviewer']==h.pin(LOCAL/'review_fullgame_rounds_v7.py')
        and commit['review_entry']==h.pin(LOCAL/'fullgame_review_entry_v6.py')
        and commit['current_boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'Exact original sources/order/boot precommit required')
    prepared=p.read(commit['native_prepared'])
    p.require(prepared['engineering_only']is False and prepared['ordered_legs']==p.ORDER,'Production native study required')
    producer=p.load('_fullgame_final_eligibility',LOCAL/'prepare_fullgame_study_v6.py')
    producer.eligible_screen(prepared['screen_assessment'],prepared['reference_epoch'],h)
    pair=p.read(prepared['pair'])
    p.require(pair['engineering_only']is False and pair['minimum_complete_games_each']==64
        and pair['screen_assessment']==prepared['screen_assessment']and pair['protected_reference_epoch']==prepared['reference_epoch'],
        'Actual screened fixed-reference fullgame pair required')
    publication=p.read(commit['CPU_guard_publication'])
    p.require(publication['status']=='PASS'and publication['prepared']==commit['native_prepared']
        and [case['leg']for case in publication['cases']]==p.ORDER,'Exact four-job CPU guard publication required')
    reviewer=p.load('_fullgame_final_actual_reviewer',LOCAL/'review_fullgame_rounds_v7.py')
    contract=reviewer.round_contract();legs=[];scope_proofs=[];main_domain=None;previous_end=0;all_transports=set()
    for case,review_case,guard in zip(prepared['cases'],commit['cases'],publication['cases']):
        role=case['leg'];root=Path(case['native_job']['path']).parent
        p.require(review_case['leg']==guard['leg']==role and review_case['native_job']==guard['native_job']==case['native_job'],
            'Original exact job/review/CPU guard leg joins differ')
        subject=p.read(case['native_job']);role_policy=pair['reference'if role.startswith('R')else'candidate']
        p.require(subject['quality_pair_precommit']==prepared['pair']and subject['checkpoint']==role_policy['policy']
            and subject['expected_policy_clocks']==role_policy['saved_clocks']and subject['confirmation_min_complete_games']==64,
            'Original policy/clocks/pair/minimum changed')
        tokens={*subject['sessions'].values(),*subject['connections'].values()}
        p.require(len(tokens)==64 and not tokens & all_transports,'Original transport identity reused between legs');all_transports.update(tokens)
        ctx=contract.context(subject,h)
        # Owner process census fields can advance; compare the precommitted
        # binding pin, which all four exact jobs share, rather than live state.
        if main_domain is None:main_domain=subject['main_binding']
        p.require(subject['main_binding']==main_domain,'Original main domain changed between legs')
        packet=p.read(review_case['review_job']);review_cfg=p.read(review_case['review_config'])
        p.require(packet['controller_config']==guard['qualified_controller_config'],'Reviewer used an unqualified/different native configuration')
        p.validate_packet(case,packet,review_cfg,h)
        for cfg_pin in (packet['controller_config'],review_case['review_config']):
            cfg=p.read(cfg_pin)
            controller=p.cpu_controller(h)if cfg_pin==review_case['review_config']else p.load('_fullgame_final_native_control',LOCAL/'control_fullgame_rounds_v6.py')
            for pin in cfg['pins']:p.require(controller.pin(pin['path'])==pin,'Original scoped launch input changed')
        ns=p.owned_scope(packet['controller_config'],h,native=True);rs=p.owned_scope(review_case['review_config'],h)
        p.require(commit['created_monotonic_s']<=ns['interval'][0]and previous_end<=ns['interval'][0]
            and ns['interval'][1]<=rs['interval'][0],'Original preparation/native/review/RCRC order changed')
        previous_end=rs['interval'][1]
        for name,scope in [('controller-original-result.json',ns),('independent-review-controller-original-result.json',rs)]:
            carrier=p.read(h.pin(root/name))
            p.require(type(carrier['actual_exit'])is int and carrier['actual_exit']==0
                and carrier['original_attempt']==1 and carrier['no_retry']is True and carrier['closure']==scope['closure_pin'],
                'Original controller failed/retried or archived another scope')
        result_pin=h.pin(Path(subject['output'])/'result.json');result=p.read(result_pin)
        policy,cohort=reviewer.validate_runtime_result(result,subject)
        report_pin=h.pin(root/'independent-quality-leg-review-original01/review.json');report=p.read(report_pin)
        p.require(report['schema']=='robotron-original-quota64-independent-cohort-review-v1'
            and report['status']=='PASS_ORIGINAL_QUOTA64_ALL32_FULL_GAMES_AND_RUNTIME'
            and report['valid']is report['full_game_score_verified']is True
            and report['quality_qualified']is report['promotion']is False
            and report['review_job']==review_case['review_job']and report['original_native_job']==case['native_job']
            and report['original_result']==result_pin and report['original_acceptance']==case['acceptance']
            and report['original_owner']==ns['owner_pin']and report['original_closure']==ns['closure_pin']
            and report['original_controller_result']==h.pin(root/'controller-original-result.json')
            and report['policy']==policy and report['quality_leg']==role and report['quality_pair_precommit']==prepared['pair']
            and report['actual_runtime_exit']==report['actual_controller_exit']==0
            and report['expected_selected_games']==64 and report['minimum_quality_complete_games']==50,
            'Actual valid independent original fullgame review missing or points to another cohort')
        for key in ('all_admitted_games_retained','all6_original_descriptors_verified','exact_owned_births_unit_timer_cgroup_absent',
                    'private_GPU_ports_and_coordinator_released','original_outputs_sealed_after_writer_exit'):
            p.require(report[key]is True,'Incomplete independent original evidence: '+key)
        p.require(type(report['all32_actual_MAME_exits'])is int and report['all32_actual_MAME_exits']==0
            and report['actual_descriptor_exits']==[0]*6 and len(report['raw_prefixes'])==len(report['applied_tail_shutdown'])==32,
            'All32 actual startup/tail/MAME and six descriptor exits required')
        for pin in report['artifacts']:
            if set(pin['identity'])=={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}:h.checked(pin)
            else:p.read(pin,False)
        stats=report['original_games']['statistics'];scores=[row['score']for row in cohort['rows']]
        p.require(stats['count']==len(scores)==64 and stats['score_sum']==sum(scores)
            and set(report['original_games']['admitted_ids'])==set(cohort['started_ids']),
            'Independent raw journal denominator/statistics differ')
        for name,pin in result['journal'].items():
            h.checked(pin);p.require(pin['sha256']==report['original_games']['original_payload_sha256'][name],'Original raw game/start/life payload changed')
        health=report['main_observer_independently_verified'];life=p.read(result['main_observer_lifecycle'])
        p.require(health==report['main_health_raw_replay']and health['status']=='PASS'
            and health['lifecycle']==result['main_observer_lifecycle']and health['original_job']==life['worker_job']
            and health['original_sources']==ctx['family']['main_observer']and health['full_main_input_count']==len(ctx['binding']['inputs'])==ctx['inventory']['input_count']
            and report['main_health_engine']==packet['sources']['main_health_engine']
            and report['source_family_manifest']==subject['source_family_manifest']
            and report['main_health_case_roles']==p.ORDER[:len(legs)+1], 'Independent original raw main-health joins differ')
        p.require(health['proof_gap_contract']=='robotron-main-proof-gap-2s-v1'
            and health['verified_maximum_gap_s']==2.0, 'Exact prospective2s fullgame raw proof required')
        for key in ('raw_API_and_TCP_and_retirement_snapshots_replayed','hundred_sample_readiness_verified',
                    'accepted_evidence_and_projection_gaps_verified','fresh_final_sample_verified',
                    'actual_resources_and_exit_and_owned_release_verified'):
            p.require(health[key]is True,'Incomplete independent original health proof: '+key)
        worker=p.read(life['worker_job'])
        p.require(worker['native_job']==case['native_job']and worker['native_runtime']==subject['runtime']
            and worker['case']==subject['main_binding']and worker['parent']['pid']==ns['owner']['pid']
            and worker['parent']['birth']==ns['owner']['starttime_ticks']and worker['parent']['invocation_id']==ns['owner']['invocation_id'],
            'Independent observer belongs to another original native scope')
        legs.append(dict(role=role,policy_sha256=policy['checkpoint_sha256'],cohort=cohort,cohort_selection=report['cohort_selection'],
            evidence_verified=True,original_attempt=1,no_retry=True,
            native_identity=[ns['owner'][key]for key in ('pid','starttime_ticks','invocation_id')],
            review_identity=[rs['owner'][key]for key in ('pid','starttime_ticks','invocation_id')]))
        scope_proofs.append(dict(leg=role,native_owner=ns['owner_pin'],native_closure=ns['closure_pin'],review_owner=rs['owner_pin'],
            review_closure=rs['closure_pin'],independent_review=report_pin,native_result=result_pin))
    decision=p.numerical_decision(legs,pair['reference']['policy']['sha256'],pair['candidate']['policy']['sha256'],h)
    for role in ('reference','candidate'):h.checked(pair[role]['policy'])
    p.require('torch'not in sys.modules,'Independent fullgame assessment imported numerical runtime')
    output=output.resolve();p.require(output.is_relative_to(p.BASE)and not output.exists(),'Fresh original fullgame assessment output required')
    return h.put(output,dict(schema='robotron-recovered-round-fullgame-study-assessment-v1',status='FOUR_ORIGINAL_COMPLETE_GAME_LEGS_QUALIFIED',
        review_precommit=commit_pin,native_prepared=commit['native_prepared'],pair=prepared['pair'],original_scopes=scope_proofs,
        source=h.pin(Path(__file__).resolve()),pipeline=h.pin(LOCAL/'fullgame_review_pipeline_v7.py'),
        unchanged_numeric_source=h.pin(p.NUMERIC),created_unix_s=time.time(),**decision))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--assess',action='store_true');a.add_argument('--precommit',type=Path)
    a.add_argument('--precommit-sha256');a.add_argument('--output',type=Path);args=a.parse_args()
    if args.assess:print(json.dumps(assess(args.precommit,args.precommit_sha256,args.output)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
