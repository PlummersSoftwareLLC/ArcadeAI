"""Assemble all four fresh fixed-policy jobs and immutable reviewer family.

Does not launch. Compatibility display files project this full-game campaign
for the existing dashboard; they are not scientific evidence or acceptance.
"""
import argparse
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
C=B/'post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
F=B/'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');args=p.parse_args()
    if not args.execute:p.print_help();return 0
    h=load('_assemble_fixed_fullgame_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    native=json.loads((F/'selected-source/native-controller-preparation.json').read_text())
    reviewer=json.loads((F/'selected-source/reviewer-preparation.json').read_text())
    assessor=json.loads((F/'selected-source/assessor-preparation.json').read_text())
    pairpin=h.pin(F/'fixed-pair-precommit.json');pair=json.loads(h.checked(pairpin).read_text())
    P=C/'fullgame-evaluator-live-engineering-original01-20261101'
    ap=json.loads((P/'slot-permit-archival-source-original02/source-preparation.json').read_text())
    rp=json.loads((C/'full-game-retirement-source-only-original01-20261101/native-retirement-source-original01/source-preparation.json').read_text())
    hp=json.loads((C/'fullgame-current-v6-health-engineering-original02/job.json').read_text())
    oldQ=B/'quality32-protected1741-vs-currentLR125-quota64Protocol-firstSave-original01-preparation-20261024'
    old_review=json.loads((oldQ/'01-reference/independent-review-job.json').read_text())
    template=json.loads((oldQ/'native-current197-job-template.json').read_text())
    family=h.put(F/'selected-source-family.json',dict(schema='robotron-current-v6-fullgame-confirmation-source-family-v1',pair=pairpin,
        native=native['native'],native_controller=native['native_controller'],leg_reviewer=reviewer['leg_reviewer'],
        campaign_assessor=assessor['campaign_assessor'],decision_kernel=assessor['original_decision_kernel'],
        wire_auditor=ap['sources']['audit_fullgame_slot_wire_v2.py'],games_auditor=old_review['sources']['games'],
        original_log_reviewer=h.pin(B/'future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-protocol-interface-correction-original01/read_quality32_quota64_selected_original01_v2.py'),
        current_Main_health=hp['health_source'],slot_closeout=ap['sources']['slot_retirement_closeout_v2.py'],
        source_package=pair['source_package'],finite_engineering=h.pin(P/'independent-raw-review-original01/report.json'),
        archival_CPU=h.pin(P/'slot-permit-archival-source-original02/CPU-contracts-original01.json'),
        native_source_proof=h.pin(F/'selected-source/native-controller-preparation.json'),
        reviewer_source_proof=h.pin(F/'selected-source/reviewer-preparation.json'),
        evaluator_log_contract=h.pin(P/'additional-original-evaluator-log-contract.json'),
        roles_CPU=h.pin(F/'roles-CPU-original01/report.json'),roles_CPU_closeout=h.pin(F/'roles-CPU-original01/original-role-CPU-result-and-owned-closeout.json'),
        scientific_scores_collected=False,promotion=False))
    family_data=json.loads(h.checked(family).read_text())
    CPU=B/'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/state-sources/control_stopped_fullstate600_CPU_v1.py'
    ctl=load('_assemble_fixed_fullgame_controller',h.checked(native['native_controller']))
    cpu=load('_assemble_fixed_fullgame_CPU_controller',CPU)
    legs=[];tokens=set()
    for index,role in enumerate(('R1','C1','R2','C2'),1):
        model_role='reference'if role.startswith('R')else'candidate';selected=pair['roles'][model_role]
        name=f'{index:02d}-{model_role}';directory=F/name;directory.mkdir(mode=0o700)
        j=copy.deepcopy(template)
        j.update(schema='robotron-compiled-quota64-quality-original-v1',runtime=native['native'],output=str(directory/'runtime-original01'),
            quality_leg=role,quality_pair_precommit=pairpin,minimum_completed_games=50,expected_policy_clocks=selected['saved_clocks'],
            checkpoint=selected['policy'],label='fixed-b231-vs-1c-'+role+'-original01-20261101',source_package=pair['source_package'],
            current_main=hp['current_main'],current_fleet=hp['current_fleet'],screen_support=hp['screen_support'],
            current_v6_health_source=family_data['current_Main_health'],current_v6_health_qualification=h.pin(C/'fullgame-current-v6-health-engineering-original02/independent-five-physical-samples-and-CPU10-review-original01.json'),
            source_family_manifest=family,lua=rp['lua'],lease=h.pin('/dev/shm/robotron-snapshot-smoke-gpu0.lock'),
            private_client_idle_timeout_s=22200,private_parked_origin_timeout_s=22200,private_lua_score_stall_timeout_s=22200,
            private_score_stall_timeout_s=0,selected_change='Fixed fresh protectedb231/candidate1c roles; current-v6 health, per-slot two-game retirement and full permit archival; all64/full-tail decision gates unchanged.')
        for k in ('main_sources','main_binding','main_health_protocol'):j.pop(k,None)
        j['quota64_source_pins'].update(bridge=rp['components']['full_startup_proxy_slot_retirement_v1.py'],
            slot_retirement=rp['components']['slot_quota_retirement_v1.py'],slot_closeout=family_data['slot_closeout'])
        j['quota64_validation'].update(finite_current_v6_retirement_engineering=family_data['finite_engineering'],full_slot_permit_archival_CPU=family_data['archival_CPU'])
        j['sessions']={str(k):secrets.token_hex(16)for k in range(4096,4128)}
        j['connections']={str(k):secrets.token_hex(16)for k in range(4096,4128)}
        fresh=set(j['sessions'].values())|set(j['connections'].values());assert len(fresh)==64 and not fresh.intersection(tokens);tokens.update(fresh)
        pins=[native['native'],j['checkpoint'],j['source_package'],j['mame'],j['lua'],j['seed_runtime'],j['screen_support'],
            j['current_v6_health_source'],j['current_v6_health_qualification'],family,pairpin,selected['CPU_report'],selected['original_CPU_readback'],
            *j['quota64_source_pins'].values(),*j['quota64_validation'].values(),*j['full_tail_predecessors'].values(),
            j['historical_startup_acceptance_scope'],j['validated_CPU_prefix'],*j['boot_seed']['inputs'],j['boot_seed']['module']]
        pins.extend(family_data[k]for k in ('native_controller','leg_reviewer','campaign_assessor','decision_kernel','wire_auditor','games_auditor','original_log_reviewer'))
        pins.extend(j['current_fleet'][k]for k in ('job','original_membership','rolemap','physical_helper','source_authority'))
        pins.extend([j['current_fleet']['supervisor']['source'],j['current_main']['startup_authority'],j['current_main']['startup_held']])
        j['inputs']=list({pin['path']:pin for pin in pins}.values())
        jp=h.put(directory/'job.json',j)
        config=dict(unit=f'robotron-b231-1c-{role.lower()}-fullgame-original01-20261101.service',output=str(directory/'execution-original01'),
            argv=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',native['native']['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',native['native']['sha256']],
            properties=['CPUQuota=1200%','MemoryMax=24G','MemorySwapMax=0','RuntimeMaxSec=22260','TasksMax=512','TimeoutStopSec=5','SendSIGKILL=no'],
            pins=[ctl.pin(pin['path'])for pin in [jp,*j['inputs']]],observation_s=22320)
        configpin=h.put(directory/'controller-config.json',config)
        legprep=h.put(directory/'prepared-native.json',dict(schema='robotron-fixed-fullgame-native-leg-preparation-v1',role=role,pair=pairpin,
            native=native['native'],job=jp,controller=native['native_controller'],controller_config=configpin,source_family=family,scientific_job_launched=False,promotion=False))
        rd=directory/'independent-review-original01';rd.mkdir(mode=0o700)
        rj=dict(runtime=reviewer['leg_reviewer'],role=role,native_prepared=legprep,
            original_native_closeout_path=str(directory/'positive-original-native-closeout.json'),
            wire_auditor=family_data['wire_auditor'],original_games=family_data['games_auditor'],original_reviewer=family_data['original_log_reviewer'],
            report=str(rd/'report.json'))
        # Final immutable review jobs add the actual original native-closeout
        # pin only after its sole Popen wait and positive scope release.
        review_template=h.put(directory/'review-job-template.json',rj)
        legs.append(dict(index=index,role=role,model_role=model_role,directory=str(directory),native_prepared=legprep,
            native_job=jp,native_controller_config=configpin,review_job_template=review_template,
            native_closeout_path=str(directory/'positive-original-native-closeout.json'),review_closeout_path=str(directory/'positive-original-review-closeout.json'),
            display_live_path=str(directory/'display-live.json'),display_receipt_path=str(directory/'display-reviewed.json')))
    assert len(tokens)==256
    plan=h.put(F/'plan.json',dict(schema='robotron-fixed-fullgame-dashboard-plan-v1',checkpoints={k:v['policy']for k,v in pair['roles'].items()},
        legs=[dict(index=r['index'],role=r['model_role'],job=dict(label='Protected champion'if r['model_role']=='reference'else'Candidate'),
            evaluator_status_path=r['display_live_path'],receipt_path=r['display_receipt_path'])for r in legs]))
    status=dict(state='prepared',current_leg=None,updated_unix_s=time.time(),legs=[dict(index=r['index'],role=r['model_role'],state='pending')for r in legs],
        outcome=None,reason='Final source and job preparation checks; no games started')
    with (F/'status.json').open('x')as f:json.dump(status,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    prepared=h.put(F/'prepared-campaign.json',dict(schema='robotron-fixed-fullgame-four-leg-campaign-preparation-v1',status='ALL_FOUR_JOBS_PREPARED_NOT_QUALIFIED_OR_LAUNCHED',
        campaign_directory=str(F),pair=pairpin,source_family=family,native=native['native'],native_controller=native['native_controller'],
        leg_reviewer=reviewer['leg_reviewer'],campaign_assessor=assessor['campaign_assessor'],original_decision_kernel=assessor['original_decision_kernel'],
        CPU_controller=h.pin(CPU),legs=legs,dashboard_plan=plan,original_attempt=1,no_retry=True,
        all4_native_jobs_before_first_score=True,all256_session_connection_identities_distinct=True,promotion=False))
    print(json.dumps(dict(status='ALL_FOUR_JOBS_PREPARED_NOT_QUALIFIED_OR_LAUNCHED',prepared=prepared)));return 0


if __name__=='__main__':raise SystemExit(main())
