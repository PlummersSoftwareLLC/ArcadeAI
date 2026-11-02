"""Inert NEW02/D6 metadata600 preparation and owned closeout; never launches.

Actual endpoint/profile completion is mandatory before materializing any job.
The default guard packet produced by the metadata payload is not selected for
launch; a fresh authority from this new metadata closure is separately required.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
I=B/'post-recovery-evaluation-isolation-original01-20261027'
W=B/'post-natural-turnover-durable-next-candidate-20261029-original02'
N=B/'post-natural-turnover-durable-next-candidate-20261029-original02-preparation'
F=I/'declared-launcher-evaluator-adapters-original06-fresh-study-namespaces-preparation/source-family-original02-unit-authority'
R=F/'metadata600-resource-templates-original01'
HERE=Path(__file__).resolve().parent
META=HERE/'actual-metadata-preparation-original01'
STUDY=I/'durable-window02-D6-fixed-RCRC-study-original01'
JOINT=I/'retired-api-row-projection-original01-preparation/engineering-contexts-original01-preparation/actual-current-main-contexts-original01/independent-retired-API-joint-engineering-qualification-original01.json'
FAMILY_SHA='89deb47e7cfa86a432ee46f888fe2ae557d8235b7e5b3870128f200f1493ed3b'
CONSTRUCTION_SHA='f3e835f7217bb82f07930183835c37e7645669e2ac5c67ce3133fc29f5920c0f'
JOINT_SHA='fc8e681804c7dbc72daec7b4d8487f813b048b3b8809b5765943745b163b12ba'
PLAN_SHA='0e12974bac193fc75e7d55b9746564d0e7d6d0ec7db98082b54b90d412f7c170'
DRIVER_SHA='f9f22173a954d70b30ea6443d2d2d579fb0162c474b534bfc74bc1020f17b71b'
CONTROL_SHA='5679d36399de4f0c7cc83edd900728112110115fb9f9d44d20c9a3e3b7753f55'
CLOSER_SHA='ad8c79d8a038667a1ca75cd1fe249a22dff0d34920c86d28ffbe8ec1d83aa84f'


def require(value,message):
    if not value:raise RuntimeError(message)


def module(name,path,digest):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Selected source changed: '+str(path))
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


def helpers():
    return module('_window02_D6_metadata_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')


def metadata(h,path,digest=None):
    require(path.is_absolute()and path.is_file()and not path.is_symlink()and path.suffix!='.pt'
        and path.stat().st_size<=2<<20,'Bounded actual non-model metadata required')
    pin=h.pin(path)
    require(pin['identity']['mode']=='0o444'and pin['identity']['uid']==os.getuid()
        and pin['identity']['nlink']==1,'Owned immutable original metadata required')
    if digest is not None:require(pin['sha256']==digest,'Actual selected metadata changed')
    return json.loads(h.checked(pin).read_bytes()),pin


def selected_sources(h):
    family,fp=metadata(h,F/'prepared-final-D6-retired-API-fresh-study-namespace-family-SOURCE-ONLY.json',FAMILY_SHA)
    construction,cp=metadata(h,F/'source-construction.json',CONSTRUCTION_SHA)
    values=[fp,cp]
    require(len(construction['records'])==32 and family['observer_dependency_count']==10
        and family['historical_main_input_count']==247,'Exact D6 source inventory required')
    for row in construction['records']:
        expected=row['source'];actual=h.pin(Path(expected['path']))
        require(actual==expected and actual['identity']['mode']=='0o444'
            and actual['identity']['uid']==os.getuid()and actual['identity']['nlink']==1
            and not Path(expected['path']).is_symlink(),'Selected immutable source full PIN differs')
        h.checked(expected);values.append(expected)
    require(set(family['deadline_observer_sources'])=={'client','worker','health','health_base','API_projection',
        'round_admission','launcher_census','durability','control','interpreter'},'Exact ten-source observer authority required')
    return family,values


def engineering(h,family):
    joint,jp=metadata(h,JOINT,JOINT_SHA)
    require(joint['schema']=='robotron-retired-API-joint-engineering-readiness-v1'
        and joint['status']=='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY'
        and joint['observer_sources']==family['deadline_observer_sources']
        and joint['source_family']==family['Native_frozen_source_family']
        and joint['historical_main_input_count']==247 and joint['old_failed_R1_requalified']is False
        and joint['quality_qualified']is joint['scientific_launch_qualified']is False,
        'Actual current retired-API engineering authority differs')
    values=[jp,family['Native_frozen_source_family']]
    for name,code in [('long',0),('abort',1)]:
        row=joint['engineering'][name];closed,cp=metadata(h,Path(row['closeout']['path']),row['closeout']['sha256'])
        require(cp==row['closeout']and closed['status']=='PASS_ENGINEERING_ONLY'
            and closed['mode']==name and closed['kind']=='deadline'
            and closed['worker_actual_exit']==code and closed['original_parent_actual_exit']==0
            and closed['all_original_births_units_cgroups_and_tmpfs_control_absent']is True,
            'Actual independent original engineering closure required')
        values.extend([cp,row['independent_small'],row['lifecycle']])
    small,sp=metadata(h,Path(joint['engineering']['long']['independent_small']['path']))
    require(sp==joint['engineering']['long']['independent_small']
        and small['original_full_raw_review_PASS_joined_but_not_rerun_by_peer']is True
        and small['exact_ten_source_map_matches_prepared_and_frozen_family']is True
        and small['all247_historical_main_inputs_unchanged']is True,'Actual new long SMALL/raw join differs')
    raw,rp=metadata(h,Path(small['independent_raw_review']['path']),small['independent_raw_review']['sha256'])
    require(rp==small['independent_raw_review']and raw['status']=='PASS'
        and raw['original_sources']==family['deadline_observer_sources']and raw['full_main_input_count']==247
        and raw['lifecycle']==joint['engineering']['long']['lifecycle']
        and raw['raw_API_and_TCP_and_retirement_snapshots_replayed']is True
        and raw['legacy_500ms_evidence_and_projection_gaps_verified']is True,
        'Actual new raw readiness must bind the selected exact ten-source family')
    values.extend([sp,rp,*family['deadline_observer_sources'].values(),family['deadline_raw_reviewer']])
    return rp,values


def completed_profiles(h):
    plan,pp=metadata(h,W/'window-plan.json',PLAN_SHA)
    result,rp=metadata(h,W/'result.json')
    require(result['state']=='captured_CPU_verified'and result['owner']==plan['owner']
        and result['endpoint']['path']==str(W/'endpoint.pt')
        and result['endpoint']['sha256']not in {'e078b0da4ce4e25146fab7484f8489f590e1086370746cb392afcd7f5f8adef5',
            'a6e17a3c6cd8a9b6cb5479e6c6cbd1a284c1cd880372d0d02441680bc708e502'},
        'Only the actual distinct completed NEW02 endpoint is eligible')
    canonical,cc=metadata(h,W/'canonical-profile-CPU-original01/independent-original-canonical-CPU-closeout.json')
    frozen,fc=metadata(h,W/'frozen-profile-CPU-original01/independent-original-profile-scope-closeout.json')
    require(canonical['status']==frozen['status']=='PASS'and canonical['actual_exit']==frozen['actual_exit']==0
        and canonical['all_six_descriptors_resources_argv_birth_unit_timer_cgroup_and_release_verified']is True
        and frozen['all_six_descriptors_resources_argv_birth_unit_timer_cgroup_and_release_verified']is True,
        'Both actual independent original profile CPU closures required')
    candidate,cp=metadata(h,W/'frozen-profile-CPU-original01/independent-profile-adoption.json')
    proof,pf=metadata(h,Path(candidate['profile_proof']['path']))
    require(candidate['status']=='PASS'and candidate['actual_exit']==0
        and candidate['all_Q_bytes_and_actions_match']is candidate['original_scope_released']is True
        and frozen['profile_adoption']==cp and proof['checkpoint']['sha256']==result['endpoint']['sha256'],
        'Actual NEW02 independentlyclosed frozen adoption required')
    wrapper=module('_window02_actual_endpoint_metadata',N/'prepare_durable_endpoint_profiles_v4.py',
        'a220fdd92f131b9f5709a43ebf12b3a0afc3d89293bda58db32faf8f4831bd48')
    original=wrapper.original_endpoint()
    require(original['result']=={key:rp[key]for key in ('path','sha256','bytes')},'Actual own endpoint selector differs')
    _,reference=metadata(h,I/'reference-frozen-profile-v2-CPU-original01/independent-profile-adoption.json',
        '59f6fd9df2987ff15c4506b9fa306479bf9ddb893a45aeb21f6c434effe75654')
    return result['endpoint']['sha256'],rp,reference,cp,[pp,rp,cc,fc,cp,pf,h.pin(N/'prepare_durable_endpoint_profiles_v4.py')]


def controller_argv(config):
    return ['/usr/bin/python3.12','-I','-B',str(R/'control_metadata600_v1.py'),'--execute','--config',config['path'],
        '--expected-source-sha256',CONTROL_SHA]


def prepare(h):
    family,values=selected_sources(h)  # Expected bytes/full PINs before imports or output creation.
    raw,eng_inputs=engineering(h,family)
    candidate,rp,reference,profile,profile_inputs=completed_profiles(h)
    _,lease=metadata(h,I/'post-outage-permanent-private-coordinator-restoration-original01.json',
        '26ccbdd83b17aabc5daeecb77e40278f68329152e8913fde26bc75073ccfe09d')
    require(not META.exists()and not STUDY.exists(),'Wholly fresh metadata and four-job study directories required')
    control=module('_window02_metadata600_control',R/'control_metadata600_v1.py',CONTROL_SHA)
    driver=h.pin(R/'prepare_selected_metadata600_v1.py');require(driver['sha256']==DRIVER_SHA,'Selected D6 metadata driver differs')
    values.extend([*eng_inputs,*profile_inputs,lease,driver,h.pin(R/'control_metadata600_v1.py'),
        h.pin(R/'close_metadata600_v1.py'),h.pin(Path(__file__).resolve())])
    values=list({value['path']:value for value in values}.values())
    for value in values:h.checked(value)
    META.mkdir(mode=0o700)
    job=dict(schema='robotron-selected-admission-study-CPU-preparation-v1',
        unit='robotron-window02-D6-metadata-CPU-'+candidate[:12]+'-original01-20261029.service',
        output=str(META/'runtime'),study_directory=str(STUDY),candidate_sha256=candidate,inputs=values,
        original_attempt=1,no_retry=True,capture_result=rp,reference_profile=reference,candidate_profile=profile,
        deadline_readiness=raw,lease_recovery=lease)
    jp=h.put(META/'job.json',job)
    cfg=dict(unit=job['unit'],output=str(META/'execution-original01'),
        argv=['/usr/bin/python3','-I','-B',driver['path'],'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=128',
            'TimeoutStopSec=5','SendSIGKILL=no'],observation_s=660,
        pins=[control.pin(value['path'])for value in [jp,*values]])
    cp=h.put(META/'controller-config.json',cfg);require(control.checked_config(cp['path'])==cfg,'Exact metadata600 ABI differs')
    prepared=h.put(META/'prepared-NOT-LAUNCHED.json',dict(source=h.pin(Path(__file__).resolve()),job=jp,config=cp,
        driver=driver,controller=h.pin(R/'control_metadata600_v1.py'),closer=h.pin(R/'close_metadata600_v1.py'),
        actual_D6_family=h.pin(F/'prepared-final-D6-retired-API-fresh-study-namespace-family-SOURCE-ONLY.json'),
        actual_engineering_joint=h.pin(JOINT),scientific_payload_launched=False,
        default_generated_guard_packet_selected_for_launch=False,fresh_closed_metadata_guard_authority_required=True))
    return dict(prepared=prepared,Root_original_controller_argv=controller_argv(cp))


def packet(h):
    value,pin=metadata(h,META/'prepared-NOT-LAUNCHED.json')
    require(value['source']==h.pin(Path(__file__).resolve())and value['driver']['sha256']==DRIVER_SHA
        and value['controller']['sha256']==CONTROL_SHA and value['closer']['sha256']==CLOSER_SHA,
        'Exact new metadata preparation source family required')
    return value,pin


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group()
    for name in ('prepare-metadata','print-controller-command','close-metadata'):g.add_argument('--'+name,action='store_true')
    args=p.parse_args(argv)
    if not any(vars(args).values()):print('PLAN_ONLY: no reads, imports, outputs, CPU, services, models or controls');return
    h=helpers()
    if args.prepare_metadata:out=prepare(h)
    elif args.print_controller_command:
        value,pin=packet(h);out=dict(prepared=pin,Root_original_controller_argv=controller_argv(value['config']))
    else:
        packet(h)
        out=module('_window02_original_metadata600_closer',R/'close_metadata600_v1.py',CLOSER_SHA).close(META)
    print(json.dumps(out),flush=True)


if __name__=='__main__':main()
