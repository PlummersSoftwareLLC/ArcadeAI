"""Prepare three prospective capacity-only jobs; never launch or alter originals.

The original R1 and common scientific study remain immutable. A fresh exact-job
CPU guard, mixed review precommit and owned continuation are still mandatory.
Default invocation performs no actions.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat

FIXED = {'helpers': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original_manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fresh-c0acc-b231-current-quiescence-deadline32-RCRC-original02-20261029/prepared-four-legs-NOT-LAUNCH-QUALIFIED.json', 'sha256': 'c95dc5bfad490f6491a05373540a596da256088facb219d4182f4d424e6e3e71', 'bytes': 110411, 'identity': {'device': 2304, 'inode': 80228979, 'bytes': 110411, 'mtime_ns': 1793316479009460470, 'ctime_ns': 1793316479009460470, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original_review_precommit': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fresh-c0acc-b231-current-quiescence-deadline32-RCRC-original02-20261029/review-precommit-original01/precommitted-four-reviews.json', 'sha256': '4c987cbe459f56e4c650114b3556e088e2d110bce6847f7f7b8fc2e448ed93a8', 'bytes': 22605, 'identity': {'device': 2304, 'inode': 80381177, 'bytes': 22605, 'mtime_ns': 1793317396390180346, 'ctime_ns': 1793317396390180346, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'R1_qualification': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fresh-c0acc-b231-current-quiescence-deadline32-RCRC-original02-20261029/R1/root-R1-independent-qualified.json', 'sha256': 'f65fe0b91c8c88e4ba618a38a11e3e759465dba0026ce6377006672738e60971', 'bytes': 5191, 'identity': {'device': 2304, 'inode': 80229012, 'bytes': 5191, 'mtime_ns': 1793323173670659153, 'ctime_ns': 1793323173670659153, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original_guards': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/actual-closed-metadata-current-profile-guard-original04/all-four-exact-native-guard-receipts.json', 'sha256': '2dac7ff5f8faec532ae27c4652e16b6b07c2496c570b65843990e6617a8b7256', 'bytes': 3409, 'identity': {'device': 2304, 'inode': 85459779, 'bytes': 3409, 'mtime_ns': 1793317299635163166, 'ctime_ns': 1793317299635163166, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capacity_packet': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-main-journal128-capacity-overlay-original07/prepared-main-journal128-capacity-observer-four-source-SOURCE-ONLY-NOT-LAUNCHED-v1.json', 'sha256': '6a4b70904c730146bcfb48c02aeee1e1873cc032fe9c1534fefb14720388cddd', 'bytes': 10977, 'identity': {'device': 2304, 'inode': 87556158, 'bytes': 10977, 'mtime_ns': 1793325874216528806, 'ctime_ns': 1793325874216528806, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capacity_source_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-main-journal128-capacity-overlay-original07/independent-main-journal128-capacity-four-source-and-map-peer-v1.json', 'sha256': 'b401460e47308e31c6a88a07f3164c61d9957f32418e2cc1b4f76b428648df14', 'bytes': 6739, 'identity': {'device': 2304, 'inode': 87556185, 'bytes': 6739, 'mtime_ns': 1793326041302852876, 'ctime_ns': 1793326041302852876, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'contract': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/deadline_round_contract_main_journal128_v1.py', 'sha256': '76c4e83c564f9c3148ae6b3ea006d3f57e42ae345dd4dcd1c66a409218261659', 'bytes': 18182, 'identity': {'device': 2304, 'inode': 85380297, 'bytes': 18182, 'mtime_ns': 1793325989074305409, 'ctime_ns': 1793326231048576150, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'runtime': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/run_deadline32_rounds_main_journal128_v1.py', 'sha256': 'ee607b30c2f908a7965a9668af16c48f9a6643af4f1df435e8613ca49fb0d2e5', 'bytes': 40135, 'identity': {'device': 2304, 'inode': 85380304, 'bytes': 40135, 'mtime_ns': 1793325989080320532, 'ctime_ns': 1793326231049576153, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'reviewer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/review_deadline32_rounds_main_journal128_v1.py', 'sha256': '9621e0cbd90ac0a61fe60ee05409af0b47fe8fd9243913d2ce5a3999c1092d7d', 'bytes': 11961, 'identity': {'device': 2304, 'inode': 85380305, 'bytes': 11961, 'mtime_ns': 1793325989082274011, 'ctime_ns': 1793326231049576153, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'controller': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/control_deadline32_rounds_main_journal128_v1.py', 'sha256': '2c29ef77e6b273e47f552dcbe0b2c5ab411cd52cfa79524c31c9d28ad7af4d04', 'bytes': 20877, 'identity': {'device': 2304, 'inode': 85380306, 'bytes': 20877, 'mtime_ns': 1793325989085958438, 'ctime_ns': 1793326231049576153, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
FUTURE = ('C1','R2','C2')
JOB_NAME = 'job-main-journal128-original01.json'


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,mode=oct(info.st_mode&511),
        uid=info.st_uid,nlink=info.st_nlink)


def held_identity(value):
    path=Path(value['path'])
    require(path.is_absolute() and path.resolve(strict=True)==path and not path.is_symlink()
            and stat.S_ISREG(path.stat().st_mode) and identity(path.stat())==value['identity']
            and value['bytes']==value['identity']['bytes'], 'Original held identity changed: '+str(path))


def prepare(output):
    held_identity(FIXED['helpers'])
    require(hashlib.sha256(Path(FIXED['helpers']['path']).read_bytes()).hexdigest()==FIXED['helpers']['sha256'],
            'Exact ordinary full8 helper required')
    h=load('_journal128_amendment_h',Path(FIXED['helpers']['path']))
    def read(value):return json.loads(h.checked(value).read_bytes())
    for value in FIXED.values():h.checked(value)
    original=read(FIXED['original_manifest']);old_reviews=read(FIXED['original_review_precommit'])
    old_guards=read(FIXED['original_guards']);q=read(FIXED['R1_qualification'])
    capacity=read(FIXED['capacity_packet']);mapping=read(capacity['observer_source_map'])
    require(original['ordered_legs']==[r['leg']for r in original['cases']]==['R1','C1','R2','C2']
            and original['engineering_only'] is False and old_reviews['native_prepared']==FIXED['original_manifest']
            and old_guards['status']=='PASS' and len(old_guards['guards'])==4,
            'Exact original four-job study and closed guards required')
    require(q['schema']=='robotron-root-deadline32-leg-qualification-v1'
            and q['status']=='INDEPENDENT_DEADLINE32_QUALIFIED' and q['leg']=='R1'
            and type(q['actual_review_tool_terminal_exit'])is int and q['actual_review_tool_terminal_exit']==0
            and q['all_six_descriptors_resources_argv_birth_units_cgroup_release_verified'] is True
            and q['precommit']==FIXED['original_review_precommit']
            and q['full_game_quality_qualified'] is q['improvement_qualified'] is False,
            'Keep the exact already qualified R1 under its original precommit')
    study=read(original['study_precommit']);study_root=Path(original['study_precommit']['path']).parent
    require(study['ordered_legs']==['R1','C1','R2','C2'] and study['no_retry'] is True
            and study['horizon_ns']==3_600_000_000_000 and study['n_scored_per_leg']==32,
            'Unchanged original scientific study required')
    runtime=FIXED['runtime'];reviewer=FIXED['reviewer'];control=load('_journal128_native_control',h.checked(FIXED['controller']))
    contract=load('_journal128_capacity_contract',h.checked(FIXED['contract']))
    output=Path(output).absolute()
    require(output==output.resolve() and output.parent.is_dir() and not output.exists()
            and output.parent==Path(__file__).resolve().parent,
            'Exclusive amendment metadata output directly beneath this source directory required')
    planned=[]
    for row,old_review,guardpin in zip(original['cases'][1:],old_reviews['cases'][1:],old_guards['guards'][1:]):
        require(row['leg'] in FUTURE and old_review['leg']==row['leg'],'Original ordered future roles differ')
        parent=Path(row['native_job']['path']).parent;job=read(row['native_job']);old_cfg=read(old_review['native_config']);guard=read(guardpin)
        require(parent==study_root/row['leg'] and job['leg']==row['leg'] and job['study_precommit']==original['study_precommit']
                and row['native_job']==old_review['native_job']==guard['native_job']
                and guard['status']=='PASS' and guard['actual_exit']==0
                and job['checkpoint']==study['policies'][row['role']]['checkpoint']
                and job['attempt']==1 and job['no_retry'] is True,
                'Original future scientific identity or CPU guard differs')
        for value in job['inputs']:held_identity(value)
        branch=parent/'main-journal128-amendment-original01'
        jp=parent/JOB_NAME;cp=parent/'controller-config-main-journal128-NOT-QUALIFIED-original01.json'
        qualified=parent/'controller-config-main-journal128-CPU-QUALIFIED-original01.json'
        require(all(not p.exists()for p in (branch,jp,cp,qualified,Path(job['output']),Path(old_cfg['output']),
                parent/'controller-original-launch.json',parent/'independent-review-prepared-original01.json',
                parent/('root-'+row['leg']+'-independent-qualified.json'))),
                'Original future payload/review attempt or new amendment path is already consumed')
        planned.append((row,old_review,guardpin,job,old_cfg,parent,branch,jp,cp,qualified))
    # All input/path checks precede any output. There are no unit/API/process probes.
    output.mkdir(mode=0o700)
    selection=h.put(output/'selected-original-study-three-leg-capacity-amendment.json',dict(
        schema='robotron-root-original-study-unused-three-leg-capacity-amendment-v1',
        original_manifest=FIXED['original_manifest'],original_review_precommit=FIXED['original_review_precommit'],
        original_R1_qualification=FIXED['R1_qualification'],original_CPU_guards=FIXED['original_guards'],
        study_precommit=original['study_precommit'],future_legs=list(FUTURE),
        capacity_packet=FIXED['capacity_packet'],capacity_source_peer=FIXED['capacity_source_peer'],
        selected_runtime=runtime,selected_private_reviewer=reviewer,selected_contract=FIXED['contract'],
        selected_native_controller=FIXED['controller'],source=h.pin(Path(__file__).resolve()),
        original_main_case_inventory_profiles_and_R1_unchanged=True,scientific_fields_unchanged=True,
        main_or_journal_changed=False,no_scientific_launch=True,no_policy_quality_verdict=True))
    records=[copy.deepcopy(original['cases'][0])];subjects=[]
    for row,old_review,guardpin,parent_job,old_cfg,parent,branch,jp,cp,qualified in planned:
        branch.mkdir(mode=0o700)
        old_family_pin=parent_job['source_family_manifest'];family=copy.deepcopy(read(old_family_pin))
        family.update(runtime=runtime,reviewer=reviewer,main_observer=mapping['observer_sources'],
            round_observer_reviewer=mapping['observer_reviewer'],
            main_domain_readiness_reviewer=capacity['parents']['observer_reviewer'],
            main_journal_capacity_overlay=FIXED['capacity_packet'])
        contract.capacity_overlay(family,h)
        family_pin=h.put(branch/'source-family-main-journal128.json',family)
        job=copy.deepcopy(parent_job)
        job.update(runtime=runtime,output=str(branch/'deadline-output-original01'),
            observer_sources=mapping['observer_sources'],source_family_manifest=family_pin,
            prelaunch_family_guard_closeout=str(branch/'source-family-guards-CPU-original01/independent-deadline32-family-guards-and-CPU-closeout.json'),
            main_journal_capacity_amendment=selection)
        additions=[selection,h.pin(Path(__file__).resolve()),*FIXED.values(),capacity['observer_source_map'],
            capacity['parent_source_map'],capacity['derivation'],*capacity['sources'].values(),*capacity['parents'].values(),
            family_pin,row['native_job'],old_family_pin,old_review['native_config'],guardpin]
        job['inputs']=list({v['path']:v for v in [*parent_job['inputs'],*additions]}.values())
        mutable={'runtime','output','observer_sources','source_family_manifest','prelaunch_family_guard_closeout','inputs','main_journal_capacity_amendment'}
        require({k:v for k,v in job.items()if k not in mutable}=={k:v for k,v in parent_job.items()if k not in mutable},
                'Capacity amendment changed an undeclared original scientific field')
        job_pin=h.put(jp,job)
        cfg=copy.deepcopy(old_cfg)
        cfg['argv']=[*old_cfg['argv'][:4],runtime['path'],'--execute','--job',job_pin['path'],
                     '--job-sha256',job_pin['sha256'],'--source-sha256',runtime['sha256']]
        # Old large/package pins stay exact. Hash only added source/metadata inputs here.
        pins={v['path']:v for v in old_cfg['pins']}
        for value in [job_pin,*additions]:pins[value['path']]=control.pin(value['path'])
        cfg['pins']=list(pins.values())
        config_pin=h.put(cp,cfg)
        require(control.checked_config(config_pin['path'])==cfg,'Exact amended controller filename/argv ABI differs')
        rec=copy.deepcopy(row);rec.update(native_job=job_pin,runtime=runtime,native_controller=FIXED['controller'],
            unqualified_controller_config=config_pin,source_family=family_pin,
            prelaunch_CPU_closeout=job['prelaunch_family_guard_closeout'],native_launch_ready=False,
            prospective_qualified_config_path=str(qualified),original_unlaunched_job=row['native_job'])
        records.append(rec);subjects.append(dict(leg=row['leg'],native_job=job_pin,unqualified_controller_config=config_pin,
            original_native_job=row['native_job'],original_CPU_guard=guardpin,
            future_CPU_guard_path=job['prelaunch_family_guard_closeout'],qualified_config_path=str(qualified)))
    mixed=copy.deepcopy(original)
    mixed.update(cases=records,original_manifest=FIXED['original_manifest'],
        original_R1_review_precommit=FIXED['original_review_precommit'],original_R1_qualification=FIXED['R1_qualification'],
        capacity_amendment=selection,capacity_amendment_source=h.pin(Path(__file__).resolve()),
        exact_job_CPU_closed=False,native_launch_ready=False,any_scientific_payload_launched=True,
        any_capacity_amended_payload_launched=False,
        original_R1_already_qualified=True,
        remaining='Fresh exact-three guards; explicit mixed review/continuation delegates R1 to original precommit; Root readiness then C1/R2/C2 once.')
    require(mixed['cases'][0]==original['cases'][0] and mixed['study_precommit']==original['study_precommit'],
            'Original R1 row/common study must remain byte-semantically unchanged')
    manifest=h.put(output/'prepared-mixed-original-R1-and-three-capacity-legs-NOT-LAUNCH-QUALIFIED.json',mixed)
    return h.put(output/'prepared-three-unused-leg-capacity-amendment-NOT-LAUNCH-QUALIFIED.json',dict(
        schema='robotron-prepared-unused-three-leg-main-journal128-amendment-v1',
        selected_amendment=selection,mixed_manifest=manifest,subjects=subjects,
        original_R1_qualification=FIXED['R1_qualification'],original_R1_review_precommit=FIXED['original_review_precommit'],
        source=h.pin(Path(__file__).resolve()),no_scientific_payload_launched_by_this_preparation=True,
        exact_three_CPU_guards=None,mixed_review_precommit=None,owned_continuation=None,
        full_game_quality_qualified=False,improvement_qualified=False,promotion=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--output',type=Path)
    parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.prepare:
        print('SOURCE_ONLY_INERT_NO_ACTIONS');return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Exact selected metadata source required')
    print(json.dumps(prepare(args.output)),flush=True)


if __name__=='__main__':main()
