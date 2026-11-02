"""Prepare a fresh all64 RCRC confirmation only after an actual passing screen.

Default is inert. Preparation never launches a controller, game, numerical
runtime or GPU task. The four exact-job CPU receipts remain separately required.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import secrets
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'logs/managed-learning-20261015/run-26'
HERE=Path(__file__).resolve().parent
ORDER=('R1','C1','R2','C2')


def require(value,reason):
    if not value:raise ValueError(reason)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def read(pin,h):
    path=h.checked(pin)
    require(path.is_absolute()and path.resolve(strict=True)==path and not path.is_symlink()
            and path.stat().st_uid==os.getuid()and path.stat().st_mode & 0o222==0
            and path.stat().st_nlink==1 and path.stat().st_size<=64<<20,'Canonical sealed bounded owned evidence required')
    return json.loads(path.read_bytes())


def eligible_screen(assessment_pin,epoch_pin,h):
    assessment=read(assessment_pin,h)
    require(assessment['schema']=='robotron-round-screen-study-independent-assessment-v1'
            and assessment['status']=='FOUR_ORIGINAL_SCREENING_LEGS_QUALIFIED'
            and assessment['historical_replay_only']is False and assessment['screening_passed']is True
            and assessment['policy_decision']=='REQUIRE_FRESH_COMPLETE_GAME_CONFIRMATION'
            and assessment['full_game_quality_qualified']is assessment['promotion']is False
            and assessment['source']==h.pin(HERE/'assess_screen_study.py'),
            'An actual independently qualified passing original screen is required')
    producer=load('_fullgame_actual_screen_assessor',h.checked(assessment['source']))
    # Re-run only the read-only assessment of the same closed originals. This
    # cannot replay games or rescue any failed original or failed numeric gate.
    with tempfile.TemporaryDirectory(prefix='robotron-fullgame-screen-recheck-')as directory:
        checked=producer.assess(Path(assessment['prepared_manifest']['path']),assessment['prepared_manifest']['sha256'],
                               Path(directory)/'recomputed-assessment.json')
        actual=read(checked,h)
    stable=lambda value:{key:item for key,item in value.items()if key!='created_unix_s'}
    require(stable(actual)==stable(assessment)and actual['screening_passed']is True,
            'Original scopes/scores/independent gates differ from the claimed passing assessment')
    screen=read(assessment['study_precommit'],h)
    epoch=read(epoch_pin,h)
    state=json.loads((ROOT/'logs/managed-learning-20261015/state.json').read_bytes())
    require(state['optimization_goal']['next_fixed_reference_epoch']==epoch_pin
            and epoch['reference_policy']==screen['policies']['reference']['checkpoint'],
            'Screen does not use the current protected fixed-reference epoch')
    require(screen['ordered_legs']==list(ORDER)and screen['no_retry']is True
            and screen['separate_fullgame_confirmation_required']==dict(candidate_legs=2,minimum_games_each=64,
                all_slots=32,full_tail=True,mean_ratio_min=[105,100],median_preserved=True),
            'Screen must preserve the complete-game confirmation requirements')
    return assessment,screen,epoch


def known_transports(h):
    values=set();pins=[]
    skip={'torch-cache','torchinductor','triton-cache','cuda-cache','__pycache__','.git'}
    for root,dirs,files in os.walk(BASE):
        dirs[:]=[name for name in dirs if name not in skip]
        if 'job.json'not in files:continue
        path=Path(root)/'job.json'
        if path.is_symlink()or path.stat().st_size>2<<20:continue
        value=json.loads(path.read_bytes())
        if not all(isinstance(value.get(key),dict)for key in ('sessions','connections')):continue
        pin=h.pin(path);pins.append(pin)
        for key in ('sessions','connections'):
            values.update(item for item in value[key].values()if isinstance(item,str))
    return values,pins


def nested_pins(value):
    if isinstance(value,dict):
        if set(value)=={'path','sha256','bytes','identity'}:return[value]
        return[pin for item in value.values()for pin in nested_pins(item)]
    if isinstance(value,list):return[pin for item in value for pin in nested_pins(item)]
    return[]


def prepare(assessment_pin,epoch_pin,hot_pin,lease_pin,output):
    h=load('_fullgame_study_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    assessment,screen,epoch=eligible_screen(assessment_pin,epoch_pin,h)
    state=json.loads((ROOT/'logs/managed-learning-20261015/state.json').read_bytes())
    require(not state.get('active_quality_job')and not state['optimization_goal']['scientific_job_running']
            and not state['optimization_goal'].get('performance_job_running'),'Another scientific/performance job is active')
    output=output.resolve()
    require(output.is_relative_to(BASE)and output.parent.is_dir()and not output.exists(),'Exclusive fresh run-26 study output required')
    contract=load('_fullgame_selected_contract',HERE/'fullgame_round_contract_v2.py')
    native=load('_fullgame_selected_native',HERE/'run_fullgame_rounds_v2.py')
    control=load('_fullgame_selected_controller',HERE/'control_fullgame_rounds.py')
    reviewer=load('_fullgame_selected_reviewer',HERE/'review_fullgame_rounds_v2.py')
    derivation=contract.validate_derivation(HERE/'run_fullgame_rounds_v2.py',HERE/'review_fullgame_rounds_v2.py')
    template=read(h.pin(contract.TEMPLATE),h)
    source_study=read(assessment['prepared_manifest'],h)
    previous_job=read(source_study['cases'][0]['native_job'],h)
    case=read(previous_job['main_binding'],h)
    health=load('_fullgame_prepare_live_health',HERE/'round_health_transport_v4.py')
    observer=load('_fullgame_prepare_live_raw',HERE/'fullgame_round_observer.py')
    deadline=time.monotonic()+15
    while True:
        try:
            baseline=observer.collect(health,case);health.validate(case,baseline);health.check_inputs(case,full=True);break
        except(ValueError,OSError):
            require(time.monotonic()<deadline,'No coherent original main domain; no workload launched')
            time.sleep(.02)
    recovery=read(lease_pin,h);restored=recovery['restored_lease'];h.checked(restored)
    policies={}
    for role,key in [('reference','strict_reference_profile'),('candidate','strict_candidate_profile')]:
        selected=screen['policies'][role];adoption_pin=screen[key];adoption=read(adoption_pin,h)
        require(adoption['status']=='PASS'and adoption['original_scope_released']is True,'Actual strict CPU/profile scope closure required')
        proof=read(adoption['profile_proof'],h)
        require(proof['checkpoint']==selected['checkpoint']and proof['package']==template['source_package'],
                'Screened policy is not compatible with the selected fullgame profile')
        policies[role]=dict(policy=selected['checkpoint'],saved_clocks=selected['expected_policy_clocks'],original_CPU_readback=adoption_pin)
    seen,prior=known_transports(h)
    output.mkdir(mode=0o700)
    baseline_pin=h.put(output/'main-baseline.raw.json',baseline);case['baseline_snapshot']=baseline_pin
    binding=h.put(output/'main-binding.json',case)
    for role,selected in policies.items():
        selected['CPU_report']=h.put(output/(role+'-CPU-authority.json'),dict(status='PASS',sha256=selected['policy']['sha256'],
            clocks=selected['saved_clocks'],independent_profile_adoption=selected['original_CPU_readback'],
            scope='Adapter to the existing original independently closed strict CPU/profile evidence; no new numeric or gameplay claim'))
    pair=h.put(output/'pair-precommit.json',dict(schema='robotron-recovered-round-fullgame-pair-v1',created_unix_s=time.time(),
        ordered_legs=list(ORDER),minimum_complete_games_each=64,all32_slots=True,full_tails=True,no_candidate_pooling=True,
        no_scientific_retry=True,each_mean_ratio_min=[105,100],each_median_preserved=True,engineering_only=False,
        screen_assessment=assessment_pin,protected_reference_epoch=epoch_pin,reference_score_pool=None,
        fresh_reference_R1_R2_required=True,previous_candidate_scores_not_reused_as_reference=True,**policies))
    runtime=h.pin(HERE/'run_fullgame_rounds_v2.py');reviewer_pin=h.pin(HERE/'review_fullgame_rounds_v2.py');controller=h.pin(HERE/'control_fullgame_rounds.py')
    observer_sources=dict(client=h.pin(HERE/'fullgame_round_observer_client_v2.py'),worker=h.pin(HERE/'fullgame_round_observer.py'),
        health=h.pin(HERE/'round_health_transport_v4.py'),interpreter=h.pin(Path('/usr/bin/python3').resolve()))
    protocol=h.put(output/'main-health-protocol.json',dict(schema='robotron-native-fullgame-round-main-health-protocol-v1',
        case=binding,raw_API_required=True,close_requires_final_sample=True,hot_max_gap_s=.5,initial_samples=100))
    finalizer=next(pin for pin in previous_job['inputs']if pin['sha256']=='64c4001e3a46dd1f620bfa28b088f500bf8e9d3788a463d324cc408d7a42e6ee')
    family=h.put(output/'source-family.json',dict(schema='robotron-recovered-round-fullgame-family-v1',runtime=runtime,
        leg_reviewer=reviewer_pin,contract=h.pin(HERE/'fullgame_round_contract_v2.py'),main_observer=observer_sources,
        main_observer_reviewer=h.pin(HERE/'review_fullgame_round_observer_v2.py'),main_health_finalizer=finalizer,
        private_parent_job=h.pin(contract.TEMPLATE),current_main_binding=binding,lease_recovery_authority=lease_pin,
        engineering_only=False,native_launch_qualified=True,main_domain_hot_review=hot_pin))
    records=[];fresh=set()
    for leg in ORDER:
        directory=output/leg;directory.mkdir(mode=0o700);role='reference'if leg.startswith('R')else'candidate';selected=policies[role]
        job=copy.deepcopy(template);job.pop('inputs')
        job.update(runtime=runtime,output=str(directory/'native-output-original01'),quality_leg=leg,quality_pair_precommit=pair,
            checkpoint=selected['policy'],expected_policy_clocks=selected['saved_clocks'],minimum_completed_games=50,
            confirmation_min_complete_games=64,engineering_only=False,source_family_manifest=family,main_health_protocol=protocol,
            main_binding=binding,lease=restored,training_experiment=case['experiment'],original_attempt=1,no_retry=True,
            label='fullgame-rounds-'+leg.lower()+'-'+pair['sha256'][:12],
            prelaunch_CPU_closeout=str(directory/'fullgame-CPU-guards-original01/independent-closeout.json'))
        for key in ('sessions','connections'):
            job[key]={}
            for slot in job['actor_slots']:
                token=secrets.token_hex(16)
                while token=='0'*32 or token in seen or token in fresh:token=secrets.token_hex(16)
                fresh.add(token);job[key][str(slot)]=token
        values=[*nested_pins(job),h.pin(Path(__file__).resolve()),h.pin(HERE/'fullgame_round_adaptation_delta_v2.json'),
                h.pin(HERE/'fullgame_round_contract_v2.py'),reviewer_pin,controller,*observer_sources.values(),finalizer,
                h.pin(HERE/'review_fullgame_round_observer_v2.py'),baseline_pin,lease_pin,hot_pin,assessment_pin,epoch_pin,*prior]
        job['inputs']=list({pin['path']:pin for pin in values}.values());jp=h.put(directory/'job.json',job)
        context=native.validate_completed_context(job,h)
        try:contract.validate_launch(job,jp,context,h)
        except FileNotFoundError as error:
            require(error.filename==job['prelaunch_CPU_closeout']and not Path(job['prelaunch_CPU_closeout']).exists(),
                    'Only the prospective exact CPU receipt may be absent')
        else:raise ValueError('Exact-job CPU receipt must remain uncreated at preparation')
        scope=h.put(directory/'acceptance.json',dict(schema='robotron-original-all32-quota64-quality-acceptance-v1',job=jp,
            original_attempt=1,no_retry=True,outer_start_horizon_s=21540,whole_cohort_timeout_s=21600,
            admission_mode=reviewer.COHORT_SELECTION['strategy'],expected_selected_games=64,wall_limit_s=22200,startup_trace_frames=1200,
            minimum_quality_completed_games=50,quality_minimum_games_remains=50,confirmation_min_complete_games=64,quality_qualified=False,promotion=False))
        config=dict(unit='robotron-compiled-full-tail32-integration-rounds-'+pair['sha256'][:12]+'-'+leg.lower()+'-original01.service',
            output=str(directory/'execution-original01'),argv=[str(ROOT.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',runtime['path'],
                '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']],
            properties=reviewer.PROPERTIES,observation_s=22320,pins=[control.pin(pin['path'])for pin in [jp,scope,*job['inputs']]])
        cp=h.put(directory/'controller-config-NOT-QUALIFIED.json',config)
        require(control.checked_config(cp['path'])==config,'Actual fullgame controller interface differs')
        reviewer.validate_scope(job,jp,read(scope,h),config)
        records.append(dict(leg=leg,role=role,native_job=jp,runtime=runtime,controller=controller,unqualified_controller_config=cp,
            acceptance=scope,prospective_CPU_closeout=job['prelaunch_CPU_closeout'],native_launch_ready=False))
    require(len(fresh)==256 and not fresh & seen,'All256 fresh/disjoint transport identities required')
    return h.put(output/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json',dict(schema='robotron-fullgame-rounds-four-job-preparation-v1',
        pair=pair,cases=records,ordered_legs=list(ORDER),screen_assessment=assessment_pin,reference_epoch=epoch_pin,
        source=h.pin(Path(__file__).resolve()),private_predicate_derivation=derivation,all256_transports_fresh_and_disjoint=True,
        engineering_only=False,exact_job_CPU_closed=False,native_launch_ready=False,any_scientific_payload_launched=False,
        full_game_quality_qualified=False,promotion=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--screen-assessment',type=Path)
    p.add_argument('--reference-epoch',type=Path);p.add_argument('--main-domain-proof',type=Path);p.add_argument('--lease-recovery',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.prepare:
        h=load('_fullgame_CLI_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
        print(json.dumps(prepare(h.pin(a.screen_assessment.resolve()),h.pin(a.reference_epoch.resolve()),h.pin(a.main_domain_proof.resolve()),h.pin(a.lease_recovery.resolve()),a.output)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
