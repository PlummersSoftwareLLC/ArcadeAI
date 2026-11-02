"""One Root-operated same-operation preflight and immutable R1 launch intent.

Default inert. Explicit preparation invokes only the reviewed read-only finalizer,
then emits exact systemd argv. It never registers canonical state or launches.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
I=G/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027'
A=Path(__file__).resolve().parent
# Actual study is selected by the independently qualified manifest.
O=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/postguard-owned-operations-generic-original02')

FINALIZER_SHA='5b0563d2eba82f45b0123e05da6260f4d72199b2132fc1b8787cbdaf58667622'


def require(ok,message):
    if not ok:raise ValueError(message)


def load(name,path,digest):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Selected R1 preparation dependency differs')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m);return m


def read(pin,h):
    require(pin is not None and pin['identity']['mode']=='0o444' and pin['identity']['nlink']==1
        and pin['bytes']<=2<<20,'Filled immutable bounded metadata PIN required')
    return json.loads(h.checked(pin).read_bytes())


def capture_candidate(study,h,sources):
    # Resolve the one actual selection already held by the new study. This is
    # metadata-only delegation to the unchanged selected F7 eligibility code.
    choices=[value for value in study['prospective_capture_evidence']
             if Path(value['path']).name=='Root-physical192-comparison-selection.json']
    require(len(choices)==1,'Exactly one immutable current comparison selection must be held by this study')
    selected_pin=choices[0];selected=read(selected_pin,h)
    require(selected['schema']=='robotron-root-current-eval-quiescence-fresh-comparison-selection-v5'
        and selected['status']=='ACTUAL_POST_MODE_CONTEXT_SELECTED'
        and selected['candidate_selection_mode']=='FRESH_POST_MODE_CAPTURE'
        and selected['source_family']==sources['source_family'] and selected['source_peer']==sources['source_peer'],
        'Exact newly qualified fresh-capture/current-quiescence selection required')
    family=read(sources['source_family'],h)
    require(family['sources']['prepare_round_study_v10.py']==sources['study_preparer'],
        'Exact source-catalogue study preparer required')
    preparer=load('_current_fresh_R1_capture_eligibility',h.checked(sources['study_preparer']),sources['study_preparer']['sha256'])
    case=read(selected['main_case'],h)
    candidate,evidence=preparer.completed_capture(h,selected,case)
    require(candidate==study['policies']['candidate']
        and all(value in study['prospective_capture_evidence']for value in evidence)
        and all(value in study['prospective_capture_evidence']for value in
            (selected_pin,selected['main_case'],case['input_inventory_authority'])),
        'Study candidate and all unchanged fresh-capture eligibility evidence must join this selected context')
    return dict(result=selected['capture_result'],plan=selected['capture_plan'],
        CPU_verification=candidate['immutable_numerical_or_protection_authority'],
        sha256=candidate['checkpoint']['sha256'],comparison_selection=selected_pin)


def unit_absent(unit):
    value=dict(x.split('=',1)for x in subprocess.check_output(
        ['systemctl','--user','show',unit],text=True,timeout=5).splitlines()if'='in x)
    require(value.get('LoadState')=='not-found','Future exact owned wrapper/display unit already exists')


def command(source,unit,selection,selection_sha,kind):
    wrapper=kind=='wrapper'
    props=['Type=exec','RemainAfterExit=yes','Restart=no','WorkingDirectory='+str(G.parent),
        'CPUQuota='+('200%'if wrapper else'20%'),'MemoryMax='+('512M'if wrapper else'128M'),
        'MemorySwapMax=0','RuntimeMaxSec='+('4800'if wrapper else'4860'),
        'TasksMax='+('128'if wrapper else'32'),'TimeoutStopSec=10','SendSIGKILL=no',
        'StandardOutput=append:'+str(A/(kind+'-original01.stdout.log')),
        'StandardError=append:'+str(A/(kind+'-original01.stderr.log'))]
    return ['systemd-run','--user','--unit='+unit]+['--property='+p for p in props]+[
        '/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1','PYTHONUNBUFFERED=1','/usr/bin/python3.12','-I','-B',source['path'],'--run',
        '--launch-selection',selection,'--launch-selection-sha256',selection_sha,
        '--expected-source-sha256',source['sha256']]


def prepare(args):
    h=load('_window03_R1_prepare_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    input_pin=h.pin(args.inputs.resolve());require(input_pin['sha256']==args.inputs_sha256,'Actual Root operation input differs')
    inputs=read(input_pin,h)
    require(set(inputs)=={'schema','source_preparation','base_readiness','review_precommit','review_CPU',
        'output_readiness','output_selection','guard_source_contract'}and inputs['schema']=='robotron-generic-physical-R1-ROOT-operation-inputs-v1',
        'Exact prospective Root operation inputs required')
    require(inputs['source_preparation']['path']==str(A/'prepared-generic-physical-R1-wrapper-SOURCE-ONLY-NOT-LAUNCHED.json'),
        'Exact source-only R1 preparation packet required')
    prepared=read(inputs['source_preparation'],h);sources=prepared['sources']
    require(prepared['schema']=='robotron-generic-physical-owned-R1-source-preparation-v1'
        and prepared['known_candidate_sha256']is None
        and prepared['actual_serialized_manifest']is None and prepared['actual_study_precommit']is None
        and prepared['actual_serialized_R1_native_job']is None and prepared['actual_guard_index']is None
        and sources['generator']==h.pin(Path(__file__).resolve())
        and sources['wrapper']['path']==str(A/'run_owned_physical_R1_v1.py')
        and sources['finalizer']['path']==str(O/'finalize_physical_study_readiness_v2.py')
        and sources['finalizer']['sha256']==FINALIZER_SHA,'Root-selected frozen R1 source contract differs')
    for pin in sources.values():h.checked(pin)
    require(inputs['base_readiness']is not None and inputs['review_precommit']is not None and inputs['review_CPU']is not None
        and inputs['output_readiness']is not None and inputs['output_selection']is not None,
        'Actual guard/review operation inputs remain unfilled')
    base=read(inputs['base_readiness'],h);manifest_pin=base['prepared_manifest'];manifest=read(manifest_pin,h)
    S=Path(manifest_pin['path']).parent
    require(S.is_relative_to(G/'logs/managed-learning-20261015/run-26'),'Actual fresh run26 study required')
    require(inputs['guard_source_contract'] is not None,'Actual new independently reviewed guard source contract required')
    h.checked(inputs['guard_source_contract'])
    require(manifest['source_preparer']==sources['study_preparer'] and manifest_pin['path']==str(S/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json')
        and manifest['engineering_only']is False and [c['leg']for c in manifest['cases']]==['R1','C1','R2','C2'],
        'Exact selected fresh physical four-job manifest required')
    study=read(manifest['study_precommit'],h)
    require(manifest['study_precommit']['path']==str(S/'study-precommit.json') and study['schema']=='robotron-deadline32-fixed-fresh-RCRC-study-v1'
        and study['ordered_legs']==['R1','C1','R2','C2']and study['no_retry']is True
        and study['policies']['reference']['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883',
        'Actual window03 candidate and protected pair required')
    candidate=capture_candidate(study,h,sources)
    require(Path(base['exact_four_guards']['path']).name=='all-four-exact-native-guard-receipts.json'
        and Path(base['exact_four_guards']['path']).is_relative_to(G/'logs/managed-learning-20261015/run-26'),
        'Actual new closed guard publication required')
    guards=read(base['exact_four_guards'],h);closed=read(guards['original_all4_CPU_closeout'],h)
    report=read(closed['actual_CPU_report'],h);authority=read(report['closed_metadata_readiness_authority'],h)
    require(guards['status']=='PASS'and len(guards['guards'])==4 and closed['actual_exit']==0
        and closed['native_guard_receipts_published']is True and closed['tests_run']==10
        and closed['actual_runtime_limit_s']==180
        and closed['all_six_descriptors_resources_argv_birth_units_cgroup_and_release_verified']is True
        and report['readiness_semantics_reused_from_closed_metadata']==report['readiness_raw_full_integrity_passes']==4
        and authority['native_prepared']==manifest_pin
        and authority['source_contract']==inputs['guard_source_contract'],
        'Actual NEW exact four-job guard qualification required')
    for case,pin in zip(manifest['cases'],guards['guards']):
        guard=read(pin,h)
        require(guard['native_job']==case['native_job']and guard['runtime']==case['runtime']
            and guard['original_all4_CPU_closeout']==guards['original_all4_CPU_closeout']
            and guard['actual_exit']==0,'Exact per-job guard receipt differs')
    precommit=read(inputs['review_precommit'],h);cpu=read(inputs['review_CPU'],h)
    require(precommit['native_prepared']==manifest_pin and precommit['engineering_only']is False
        and precommit['source']==sources['review_preparer']
        and cpu['status']=='PASS_ENGINEERING_ONLY'and cpu['actual_exit']==0
        and read(cpu['original_job'],h)['review_precommit']==inputs['review_precommit'],
        'Actual completed review-preparation qualification required')
    namespace='physical-cohort-proof2s-'+manifest['study_precommit']['sha256'][:16]+'-r1'
    wrapper_unit='robotron-'+namespace+'-wrapper-original01-20261029.service'
    unit_absent(wrapper_unit)
    require(not(A/'original-R1-wrapper-intent.json').exists()
        and not(A/'original-R1-wrapper-terminal.json').exists(),'Original wrapper attempt already exists')
    output=Path(inputs['output_selection']);ready_path=Path(inputs['output_readiness'])
    require(output.parent==A and ready_path.parent==A and output.resolve()==output and ready_path.resolve()==ready_path
        and output!=ready_path and not output.exists()and not ready_path.exists(),
        'Separate exclusive canonical A3 readiness/selection outputs required')
    finalizer=load('_window03_R1_actual_finalizer',h.checked(sources['finalizer']),FINALIZER_SHA)
    started_wall=time.time();started_mono=time.monotonic()
    ready_pin=finalizer.finalize(Path(inputs['base_readiness']['path']),Path(inputs['review_precommit']['path']),
        Path(inputs['review_CPU']['path']),ready_path)
    ready=read(ready_pin,h)
    require(ready['status']=='READY'and ready['prepared_manifest']==manifest_pin
        and ready['source']==sources['finalizer']
        and ready['review_precommit']==inputs['review_precommit']and ready['review_preparation_CPU']==inputs['review_CPU']
        and ready['exact_review_precommit_and_source_CPU_binding_verified']is True,
        'Same-operation final preflight did not qualify')
    case=manifest['cases'][0];entry=ready['configurations'][0]
    require(case['leg']==entry['leg']=='R1'and case['role']=='reference' and case['native_job']['path']==str(S/'R1/job.json')
        and case['runtime']==sources['native']and case['native_controller']==entry['controller']==sources['controller'],
        'Actual R1 launch sources differ')
    cfg=read(entry['config'],h);controller=load('_window03_R1_actual_controller',h.checked(sources['controller']),sources['controller']['sha256'])
    require(controller.checked_config(entry['config']['path'])==cfg,'Actual study-derived controller config differs')
    created_wall=time.time();created_mono=time.monotonic()
    require(started_wall<=ready['checked_unix_s']<=created_wall and 0<=created_wall-ready['checked_unix_s']<=30
        and 0<=created_mono-started_mono<=30,'Actual final preflight must complete in one30s operation')
    selection=dict(schema='robotron-generic-physical-original-R1-launch-selection-v1',source=h.pin(Path(__file__).resolve()),
        source_preparation=inputs['source_preparation'],ROOT_operation_inputs=input_pin,sources=sources,
        readiness=ready_pin,prepared_manifest=manifest_pin,study_precommit=manifest['study_precommit'],
        candidate_sha256=candidate['sha256'],candidate_capture=candidate,reference_sha256=study['policies']['reference']['checkpoint']['sha256'],
        R1=dict(native_job=case['native_job'],config=entry['config'],native_unit=cfg['unit']),
        wrapper_unit=wrapper_unit,original_attempt=1,no_retry=True,
        operation_started_unix_s=started_wall,operation_started_monotonic_s=started_mono,
        created_unix_s=created_wall,created_monotonic_s=created_mono,
        actual_wrapper_owner=None,actual_controller_owner=None,actual_native_owner=None,
        canonical_registration_and_launch_by_Root_still_required=True,quality_qualified=False,promotion=False)
    pin=h.put(output,selection)
    return dict(launch_selection=pin,readiness=ready_pin,
        ROOT_must_register_exact_study_directory=str(S),
        actual_wrapper_owner=None,actual_native_owner=None,
        wrapper_argv=command(sources['wrapper'],wrapper_unit,pin['path'],pin['sha256'],'wrapper'),
        freshness_limit_s=30,launch_or_registration_performed=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--inputs',type=Path);p.add_argument('--inputs-sha256');p.add_argument('--source-sha256')
    a=p.parse_args()
    if not a.prepare:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS');return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256,'Actual same-operation intent source differs')
    print(json.dumps(prepare(a)),flush=True)


if __name__=='__main__':main()
