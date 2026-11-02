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
S=I/'durable-window02-D6-fixed-RCRC-study-original01'
L=I/'durable-window02-D6-selected-metadata600-original01-preparation'
F=I/'declared-launcher-evaluator-adapters-original06-fresh-study-namespaces-preparation/source-family-original02-unit-authority'
CANDIDATE='862fb4cde4ecb146b5b23a83b77ccbf1675a980bc310f6c2a6a8806d87b7c81e'
FINALIZER_SHA='45336cba9197102357ae1639b50f0155011dbb0e7b608c2709ecbb9f029091ad'


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
    h=load('_window02_R1_prepare_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    input_pin=h.pin(args.inputs.resolve());require(input_pin['sha256']==args.inputs_sha256,'Actual Root operation input differs')
    inputs=read(input_pin,h)
    require(set(inputs)=={'schema','source_preparation','base_readiness','review_precommit','review_CPU',
        'output_readiness','output_selection'}and inputs['schema']=='robotron-window02-D6-R1-ROOT-operation-inputs-v1',
        'Exact prospective Root operation inputs required')
    require(inputs['source_preparation']['path']==str(A/'prepared-window02-D6-R1-wrapper-display-SOURCE-ONLY-NOT-LAUNCHED.json'),
        'Exact source-only R1 preparation packet required')
    prepared=read(inputs['source_preparation'],h);sources=prepared['sources']
    require(prepared['schema']=='robotron-window02-D6-owned-R1-source-preparation-v1'
        and prepared['known_candidate_sha256']==CANDIDATE
        and sources['generator']==h.pin(Path(__file__).resolve())
        and sources['wrapper']['path']==str(A/'run_owned_R1_window02_v1.py')
        and sources['projector']['path']==str(A/'project_owned_R1_window02_v1.py')
        and sources['finalizer']['path']==str(L/'finalize_window02_D6_readiness_v1.py')
        and sources['finalizer']['sha256']==FINALIZER_SHA,'Root-selected frozen R1 source contract differs')
    for pin in sources.values():h.checked(pin)
    require(inputs['base_readiness']is not None and inputs['review_precommit']is not None and inputs['review_CPU']is not None
        and inputs['output_readiness']is not None and inputs['output_selection']is not None,
        'Actual guard/review operation inputs remain unfilled')
    base=read(inputs['base_readiness'],h);manifest_pin=base['prepared_manifest'];manifest=read(manifest_pin,h)
    require(manifest_pin==prepared['actual_serialized_manifest'] and manifest_pin['path']==str(S/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json')
        and manifest['engineering_only']is False and [c['leg']for c in manifest['cases']]==['R1','C1','R2','C2'],
        'Exact fresh D6 four-job manifest required')
    study=read(manifest['study_precommit'],h)
    require(manifest['study_precommit']==prepared['actual_study_precommit'] and study['schema']=='robotron-deadline32-fixed-fresh-RCRC-study-v1'
        and study['ordered_legs']==['R1','C1','R2','C2']and study['no_retry']is True
        and study['policies']['candidate']['checkpoint']['sha256']==CANDIDATE
        and study['policies']['reference']['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883',
        'Actual window02 candidate and protected pair required')
    require(base['exact_four_guards']==prepared['actual_guard_index'], 'Actual NEW qualified guard index differs')
    guards=read(base['exact_four_guards'],h);closed=read(guards['original_all4_CPU_closeout'],h)
    report=read(closed['actual_CPU_report'],h);authority=read(report['closed_metadata_readiness_authority'],h)
    require(guards['status']=='PASS'and len(guards['guards'])==4 and closed['actual_exit']==0
        and closed['native_guard_receipts_published']is True and closed['tests_run']==10
        and closed['actual_runtime_limit_s']==180
        and closed['all_six_descriptors_resources_argv_birth_units_cgroup_and_release_verified']is True
        and report['readiness_semantics_reused_from_closed_metadata']==report['readiness_raw_full_integrity_passes']==4
        and authority['native_prepared']==manifest_pin
        and authority['source_contract']['sha256']=='51dba1d3150db4af359b57dec6c5d29e23d3b2ae4a360dfde5a7ee16d5dc0ecc',
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
    namespace='window02-retired-api-'+manifest['study_precommit']['sha256'][:16]+'-r1'
    wrapper_unit='robotron-'+namespace+'-wrapper-original01-20261029.service'
    projector_unit='robotron-'+namespace+'-passive-display-original01-20261029.service'
    for unit in (wrapper_unit,projector_unit):unit_absent(unit)
    require(not(A/'original-R1-wrapper-intent.json').exists()
        and not(A/'original-R1-wrapper-terminal.json').exists(),'Original wrapper attempt already exists')
    output=Path(inputs['output_selection']);ready_path=Path(inputs['output_readiness'])
    require(output.parent==A and ready_path.parent==A and output.resolve()==output and ready_path.resolve()==ready_path
        and output!=ready_path and not output.exists()and not ready_path.exists(),
        'Separate exclusive canonical A2 readiness/selection outputs required')
    finalizer=load('_window02_R1_actual_finalizer',h.checked(sources['finalizer']),FINALIZER_SHA)
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
    require(case['leg']==entry['leg']=='R1'and case['role']=='reference' and case['native_job']==prepared['actual_serialized_R1_native_job']
        and case['runtime']==sources['native']and case['native_controller']==entry['controller']==sources['controller'],
        'Actual R1 launch sources differ')
    cfg=read(entry['config'],h);controller=load('_window02_R1_actual_controller',h.checked(sources['controller']),sources['controller']['sha256'])
    require(controller.checked_config(entry['config']['path'])==cfg,'Actual study-derived controller config differs')
    created_wall=time.time();created_mono=time.monotonic()
    require(started_wall<=ready['checked_unix_s']<=created_wall and 0<=created_wall-ready['checked_unix_s']<=30
        and 0<=created_mono-started_mono<=30,'Actual final preflight must complete in one30s operation')
    selection=dict(schema='robotron-window02-D6-original-R1-launch-selection-v1',source=h.pin(Path(__file__).resolve()),
        source_preparation=inputs['source_preparation'],ROOT_operation_inputs=input_pin,sources=sources,
        readiness=ready_pin,prepared_manifest=manifest_pin,study_precommit=manifest['study_precommit'],
        candidate_sha256=CANDIDATE,reference_sha256=study['policies']['reference']['checkpoint']['sha256'],
        R1=dict(native_job=case['native_job'],config=entry['config'],native_unit=cfg['unit']),
        wrapper_unit=wrapper_unit,projector_unit=projector_unit,original_attempt=1,no_retry=True,
        operation_started_unix_s=started_wall,operation_started_monotonic_s=started_mono,
        created_unix_s=created_wall,created_monotonic_s=created_mono,
        actual_wrapper_owner=None,actual_controller_owner=None,actual_native_owner=None,
        canonical_registration_and_launch_by_Root_still_required=True,quality_qualified=False,promotion=False)
    pin=h.put(output,selection)
    return dict(launch_selection=pin,readiness=ready_pin,
        ROOT_must_register_exact_study_directory=str(S),
        actual_wrapper_owner=None,actual_native_owner=None,
        wrapper_argv=command(sources['wrapper'],wrapper_unit,pin['path'],pin['sha256'],'wrapper'),
        passive_display_argv=command(sources['projector'],projector_unit,pin['path'],pin['sha256'],'projector'),
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
