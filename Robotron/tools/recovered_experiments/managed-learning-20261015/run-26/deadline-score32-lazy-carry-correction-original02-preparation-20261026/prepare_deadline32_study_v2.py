"""Prepare four fresh fixed deadline32 envelopes; inert by default/import.

No launches, model bodies, GPU, MAME, unit controls, main/source/state changes.
Final actual jobs remain unqualified until their exact bounded CPU closeout.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time
Q=Path(__file__).resolve().parent
OLD=Q.parent/'deadline-score60min-protocol-original01-preparation-20261026'
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
N=R/'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025'
P=N/'evaluator-count-active600-counterbalanced-engineering-original06/future-startup-slot64-chain-correction-original01'
CAP=R/'deadline-score32-later-policy-firstSave-original01-preparation-20261026'
SLOTS=tuple(range(4096,4128))
LEGS=('R1','C1','R2','C2')

def require(ok,message):
    if not ok:raise ValueError(message)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

def prepare():
    h=load('_deadline_study_immutable_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    def read(pin):return json.loads(h.checked(pin).read_bytes())
    def put(path,value):return h.put(path,value)
    def frozen(path):
        p=Path(path);require(stat.S_IMODE(p.stat().st_mode)==0o444,'New selected source is not frozen: '+str(p));return h.pin(p)
    state=json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    require(not state['scientific_job_running'] and not state['performance_job_running'],'No other original study may be active')
    binding=state['current_main_binding'];monitor=state['current_main_monitor'];supervision=state['current_main_supervision_policy']
    require(binding['sha256']=='07b2e23220d9d4d5950a6a6259f268bcc71102f4b228f694cc0f3cbe1505f468'
        and monitor['sha256']=='a16e51a71a066a06dcaa02657024fcd52c0ccc8f3f23ef6c970e4051f538b224'
        and supervision['sha256']=='affdf3172e30a35979e3e3fa3b7136175e5caad2fe9d92ba30a1e15f695aafce',
        'Exact ROOT-adopted postcapture main context required')
    require(read(binding)['supervision_policy']==supervision,'Current main supervision binding differs')
    for entry in (binding,monitor,supervision):h.checked(entry)
    template=read(h.pin(N/'01-reference/job.json'))
    oldcold=read(h.pin(P/'cold-prefix-preparation05-original01/job.json'))
    originalfamily=read(oldcold['source_family_manifest']);originalprotocol=read(oldcold['main_health_protocol'])
    runtime=frozen(OLD/'run_deadline32_leg_v1.py');reviewer=frozen(OLD/'review_deadline32_leg_v1.py')
    controller=frozen(Q/'control_deadline32_leg_v2.py')
    components={key:frozen(path)for key,path in dict(
        recorder=OLD/'deadline_score_recorder_v3.py',hooks=Q/'deadline_proxy_hooks_v2.py',
        report=OLD/'deadline_score_report_v1.py',lifecycle=OLD/'deadline_measurement_lifecycle_v1.py',
        clock_proxy=OLD/'private-startup-clock32-original01/full_startup_proxy_deadline32_v1.py',
        clock_authority=OLD/'private-startup-clock32-original01/startup_handoff_deadline32_v1.py',
        clock_codec=OLD/'private-startup-clock32-original01/wire_codec_deadline32_v1.py',
        clock_readiness=OLD/'private-startup-clock32-original01/boot_readiness_deadline32_v1.py',
        clock_ledger=OLD/'private-startup-clock32-original01/tail_ledger_deadline32_v1.py',
        clock_sampler=G/'tools/startup_clock_cosampling_proposal_20261026/clock_cosampling_v1.py',
        prefix_auditor=OLD/'private-startup-clock32-original01/audit_startup_deadline32_clock_v2.py',
        score_auditor=OLD/'audit_deadline32_score_v1.py').items()}
    derivation=frozen(OLD/'observer-bound4260-family-original01/source-derivation-direct-historical-v2.json')
    observer=read(derivation)['selected_sources']
    for entry in observer.values():h.checked(entry)
    design=frozen(OLD/'deadline-score32-design-precommit.json')
    invalid_predecessor=frozen(OLD/'root-original-study-startup-failure-disposition.json')
    candidate_adoption=h.pin(CAP/'root-candidate-numerical-adoption.json');candidate=read(candidate_adoption)
    require(candidate['root_accepts_numerical_verification']is True and candidate['source']['sha256']=='78cd9bf9392ee759dc42dea31f764058c24f272fd695594368317244527b1409',
        'Exact ROOT-selected later3630 candidate required')
    selection=h.pin(CAP/'fresh-later-policy-selection-precommit.json');selected=read(selection)
    epoch=selected['reference_epoch'];reference=read(epoch)
    require(reference['reference_policy']==template['checkpoint'] and template['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883',
        'Protected3045 fixed reference differs')
    numerical=read(candidate['report']);training_experiment=numerical['root_job']['experiment']
    require(training_experiment=='CE4096-LR125-survival32M-original01-20261023','Actual saved recipe context differs')
    def model_stat(entry):
        p=Path(entry['path']);s=p.lstat();i=entry['identity']
        require(stat.S_ISREG(s.st_mode) and not p.is_symlink() and s.st_size==entry['bytes']
            and all(i[k]==v for k,v in dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink).items()),
            'Previously attested model identity changed; do not reuse its digest')
    for entry in (reference['reference_policy'],candidate['source']):model_stat(entry)
    policies=dict(reference=dict(checkpoint=reference['reference_policy'],expected_policy_clocks=reference['saved_clocks'],
        training_experiment=training_experiment,immutable_numerical_or_protection_authority=epoch),
        candidate=dict(checkpoint=candidate['source'],expected_policy_clocks=candidate['saved_clocks'],
        training_experiment=training_experiment,immutable_numerical_or_protection_authority=candidate_adoption))
    directory=Q/'fixed-RCRC-deadline32-study-original02'
    require(not directory.exists(),'Exclusive original preparation directory already exists; never overwrite')
    directory.mkdir(mode=0o700)
    study=put(directory/'study-precommit.json',dict(schema='robotron-deadline32-fixed-fresh-RCRC-study-v1',created_unix_s=time.time(),
        design_precommit=design,invalid_predecessor=invalid_predecessor,new_lazy_carry_hook=components['hooks'],ordered_legs=list(LEGS),horizon_ns=3_600_000_000_000,actor_slots=list(SLOTS),
        policies=policies,n_scored_per_leg=32,n_reference_pooled=64,first_games_per_slot=1,
        resource_bounds=dict(native_work_s=4200,startup_s=300,cleanup_s=60,native_watchdog_s=4260,
            observer_watchdog_s=4260,outer_observation_s=4320,request_budget_ns=3_000_000_000,inflight_drain_bound_ns=3_500_000_000),
        each_candidate_mean_ratio_min=[105,100],each_candidate_median_preserved=True,
        zero_reference_score_sum_relative_gain='undefined; no numerical qualification; leg itself remains valid',
        no_outcome_selection=True,no_retry=True,original_attempt_per_leg=1,completed_game_floor=None,
        historical_fullgame_scores_reused=False,scientific_improvement_qualified=False,
        main_binding=binding,current_main_monitor=monitor,current_main_supervision_policy=supervision))
    prior_paths=set(N.glob('*/job.json'))
    for sub in N.glob('*engineering-original*'):prior_paths.update(sub.glob('*/job.json'))
    prior_paths.update(P.glob('*/job.json'))
    prior_paths.update((OLD/'fixed-RCRC-deadline32-study-original01').glob('*/job.json'))
    prior_paths.update((OLD/'guard-path-correction-original01').glob('*/job.json'))
    prior_ids=set();prior_jobs=[]
    for path in sorted(prior_paths):
        item=json.loads(path.read_bytes())
        if 'sessions'not in item:continue
        prior_jobs.append(h.pin(path))
        for key in ('sessions','connections'):prior_ids.update(item[key].values())
    fresh=set();records=[]
    native=load('_deadline_actual_prepared_native',Path(runtime['path']))
    actualreview=load('_deadline_actual_prepared_reviewer',Path(reviewer['path']))
    immutable=load('_deadline_actual_prepared_reader',Path(template['main_sources']['reader']['path']))
    read_actual=lambda pin,as_json=True:immutable.read_pin(pin,as_json=as_json)
    controller_pin_cache={}
    def controller_pin(entry):
        p=Path(entry['path']);s=p.stat();i=entry['identity']
        values=dict(device=s.st_dev,inode=s.st_ino,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
        require(stat.S_ISREG(s.st_mode)and s.st_size==entry['bytes']and all(values[k]==i[k]for k in values),'Controller pin stat differs')
        for key,value in (('mtime_ns',s.st_mtime_ns),('ctime_ns',s.st_ctime_ns)):
            if key in i:require(i[key]==value,'Controller pin timestamps changed')
        if p.suffix=='.pt':model_stat(entry)
        elif str(p)not in controller_pin_cache:
            require(hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],'Controller input digest differs')
        result=dict(path=entry['path'],sha256=entry['sha256'],bytes=entry['bytes'],identity=values)
        if str(p)in controller_pin_cache:require(controller_pin_cache[str(p)]==result,'Cached input pin changed')
        controller_pin_cache[str(p)]=result
        return result
    for leg in LEGS:
        private=directory/leg;private.mkdir(mode=0o700);role='reference'if leg.startswith('R')else'candidate'
        chosen=policies[role];label='deadline32-score60min-'+leg.lower()+'-original02-20261026'
        job={key:copy.deepcopy(template[key])for key in ('source_package','actor_source_sha256','loaded_rom_sha256','prior_ROM_identity_proof',
            'lua','mame','rompath','boot_seed','seed_runtime','lease','main_sources')}
        job.update(schema='robotron-deadline32-one-original-leg-v1',created_unix_s=time.time(),leg=leg,attempt=1,no_retry=True,
            runtime=runtime,output=str(private/'deadline-output-original01'),actor_slots=list(SLOTS),origin_port=19998,
            proxy_ports={str(s):20000+s-4096 for s in SLOTS},device='cuda',backend='inductor',cpu_threads=2,
            inference_max_batch_size=16,gpu_uuid='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0',
            horizon_ns=3_600_000_000_000,startup_limit_s=300,wall_limit_s=4200,cleanup_limit_s=60,
            inflight_drain_bound_ns=3_500_000_000,startup_trace_frames=1200,startup_admission_duration_ns=300_000_000_000,
            resources=dict(cpu_cores=12,memory_bytes=24<<30,tasks_max=512,runtime_max_s=4260),
            observer_resources=dict(cpu_cores=2,memory_bytes=4<<30,tasks_max=128,runtime_max_s=4260),controller_observation_s=4320,
            label=label,measurement_label=label,training_experiment=training_experiment,
            checkpoint=chosen['checkpoint'],expected_policy_clocks=chosen['expected_policy_clocks'],study_precommit=study,
            policy_authority=chosen['immutable_numerical_or_protection_authority'],
            components=components,observer_sources=observer,main_binding=binding,current_main_monitor=monitor,
            current_main_supervision_policy=supervision,
            prelaunch_family_guard_closeout=str(private/'source-family-guards-CPU-original01/independent-deadline32-family-guards-and-CPU-closeout.json'),
            deadline_metric_independently_qualified=False,improvement_qualified=False,main_runtime_changed=False)
        for key in ('sessions','connections'):
            job[key]={}
            for slot in SLOTS:
                token=secrets.token_hex(16)
                while token in fresh or token in prior_ids or token=='0'*32:token=secrets.token_hex(16)
                fresh.add(token);job[key][str(slot)]=token
        family=copy.deepcopy(originalfamily)
        family.update(schema='robotron-deadline32-one-original-leg-source-family-v1',runtime=runtime,deadline_components=components,
            main_observer=observer,native_closure=controller,reviewer=reviewer,observer_bound4260_derivation=derivation,
            experiment_precommit=study,diagnostic_precommit=design,source_preparation_only=True,native_launch_selected=False,
            cold_prefix_only=False,deadline32_only=True,current_main_binding=binding,
            legacy_32slot_component_proofs_only=True,full_new_reviewer_native_raw_pass=False)
        family.pop('observer_bound420_derivation',None)
        context=actualreview.validate_protocol_provenance(family,read_actual)
        context_pin=put(private/'completed-source-provenance-context-preflight.json',dict(passed=True,context=context,
            source_scope='Full actual completed historical codec/observer derivations and selected4260 whole-source bridge. No model/native outcomes/GPU/MAME.'))
        family_pin=put(private/'source-family.json',family)
        protocol=copy.deepcopy(originalprotocol)
        protocol['health_job'].update(duration_s=4200,driver=runtime,binding=binding,output=str(Path(job['output'])/'main-observations'),selection=study)
        protocol_pin=put(private/'main-health-protocol.json',protocol)
        job.update(source_family_manifest=family_pin,main_health_protocol=protocol_pin)
        inputs=[runtime,reviewer,controller,design,invalid_predecessor,study,derivation,context_pin,family_pin,protocol_pin,binding,monitor,supervision,
            candidate_adoption,candidate['report'],h.pin(CAP/'independent-original02-numerical-SMALL-review.json'),selection,epoch,*components.values(),*observer.values(),*job['main_sources'].values(),
            job['source_package'],job['checkpoint'],job['policy_authority'],job['lua'],job['mame'],job['seed_runtime'],job['boot_seed']['module'],
            *job['boot_seed']['inputs'],h.pin(G/'tools/startup_policy_journal_proposal/full_startup_wire_v2.lua'),
            h.pin(__file__),h.pin(P/'run_cold_slot64_prefix_v1.py'),
            h.pin(G/'tools/startup_policy_journal_proposal/audit_quality32_games_v1.py'),
            h.pin(G/'tools/startup_policy_journal_proposal/wire_codec_v2.py'),
            family['main_health_finalizer'],family['main_prefix_validator'],family['main_live_control'],family['main_observer_interpreter'],*prior_jobs,*protocol['health_job']['sources'].values()]
        job['inputs']=list({p['path']:p for p in inputs}.values())
        require(native.validate_job(job)==Path(job['output']),'Actual native job validation differs')
        actual_context=native.validate_completed_context(job,h)
        prebody=put(private/'actual-native-prebody-completed-context.json',dict(
            schema='robotron-deadline32-prepared-native-prebody-context-v1',passed=True,
            runtime=runtime,components=components,main_binding=binding,held_main_inputs=len(actual_context['main_binding']['held_hashes']),
            main_actor_count=len(actual_context['main_binding']['actors']),
            actual_main_health_contract_checked=True,protocol_provenance=actual_context['protocol_provenance'],
            actual_package_source_inputs=len(actual_context['package_pins']),
            scope='Actual selected native.validate_completed_context on final in-memory metadata before serialization. Exact serializedjobSHA qualification remains for separate bounded original CPU scope.',
            model_Torch_GPU_MAME_or_native_actions=False))
        job['inputs'].append(prebody)
        jp=put(private/'job.json',job)
        config=dict(unit='robotron-deadline32-score60min-'+leg.lower()+'-original02-20261026.service',
            output=str(private/'execution-original01'),argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',runtime['path'],
                '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']],
            properties=['CPUQuota=1200%','MemoryMax=24G','MemorySwapMax=0','RuntimeMaxSec=4260','TasksMax=512',
                'TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],observation_s=4320,
            pins=[controller_pin(p)for p in {p['path']:p for p in [jp,*job['inputs']]}.values()])
        cp=put(private/'controller-config-NOT-QUALIFIED.json',config)
        control=load('_deadline_actual_prepared_controller_'+leg,Path(controller['path']))
        require(control.checked_config(cp['path'])==config,'Actual native controller config interface differs')
        records.append(dict(leg=leg,role=role,native_job=jp,runtime=runtime,native_controller=controller,
            unqualified_controller_config=cp,source_family=family_pin,main_health_protocol=protocol_pin,
            completed_source_provenance_context=context_pin,actual_native_prebody_context=prebody,prelaunch_CPU_closeout=job['prelaunch_family_guard_closeout'],
            no_retry=True,native_launch_ready=False,all_output_and_execution_paths_absent=not Path(job['output']).exists()and not Path(config['output']).exists()))
    require(len(fresh)==256 and not(fresh&prior_ids),'All four256 fresh transport identities must be disjoint')
    packet=put(directory/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json',dict(schema='robotron-deadline32-four-original-leg-preparation-v1',
        study_precommit=study,ordered_legs=list(LEGS),cases=records,source_preparer=h.pin(__file__),reviewer=reviewer,invalid_predecessor=invalid_predecessor,
        native_runtime_and_metric_unchanged=True,new_hook_missing_zero_semantics_only=True,
        actual_new_native_component_provenance_and_controller_interfaces_checked=True,
        all256_transport_IDs_fresh_and_disjoint=True,prior_jobs=prior_jobs,protected_model_body_read=False,
        exact_job_CPU_closed=False,native_launch_ready=False,any_scientific_payload_launched=False,
        remaining='Separate exact bounded180s CPU job-family guards/closure, source peer+ROOT adoption, fresh main192/197/GPU0/ports/lease/unit readiness, ROOT-only firstR1 launch.'))
    print(json.dumps(packet),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true')
    if parser.parse_args().prepare:prepare()
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
