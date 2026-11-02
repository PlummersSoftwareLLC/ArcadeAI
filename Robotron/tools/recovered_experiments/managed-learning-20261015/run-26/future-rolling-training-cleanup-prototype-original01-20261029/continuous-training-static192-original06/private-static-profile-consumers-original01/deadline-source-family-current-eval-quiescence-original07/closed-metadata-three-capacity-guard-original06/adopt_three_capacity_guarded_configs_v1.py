"""Publish exact qualified config metadata after one closed three-job CPU PASS.

No native/science launch, process/unit controls, Main or journal mutation.
Only declared unused config paths and one fresh adoption directory are written.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

LOCAL=Path(__file__).resolve().parent
HELPER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
DRIVER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/closed-metadata-three-capacity-guard-original05/qualify_three_capacity_jobs_cpu_v1.py', 'sha256': '22600f1824636431398f0c267058ce0ef7a78061e482383628876e1af299c444', 'bytes': 18145, 'identity': {'device': 2304, 'inode': 87556193, 'bytes': 18145, 'mtime_ns': 1793326648755143307, 'ctime_ns': 1793326941092955607, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
CLOSER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/closed-metadata-three-capacity-guard-original05/close_three_capacity_jobs_cpu_v1.py', 'sha256': '80378747b290e932153c60ed3bd82a7cb80be10aacd3061afc664a7ffd30b5aa', 'bytes': 10745, 'identity': {'device': 2304, 'inode': 87556194, 'bytes': 10745, 'mtime_ns': 1793326796187237560, 'ctime_ns': 1793326941094955613, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PRODUCER={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/remaining-three-main-journal128-amendment-original01/prepare_remaining_three_main_journal128_amendment_v2.py', 'sha256': '037c79e120a2ff891e1fb961f583e01ffe5213a5d0fedcae94fd574f0f65616e', 'bytes': 21205, 'identity': {'device': 2304, 'inode': 87556239, 'bytes': 21205, 'mtime_ns': 1793327288211443439, 'ctime_ns': 1793327518997144555, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
SHIM={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/closed-metadata-three-capacity-guard-original06/closed_metadata_three_capacity_readiness_v2.py', 'sha256': '9a0a6255031018f7b7153d28f0c4a042fa1f7d2f023ea4e9d8f7fabbfbb1bcc2', 'bytes': 14560, 'identity': {'device': 2304, 'inode': 87556250, 'bytes': 14560, 'mtime_ns': 1793327888008299734, 'ctime_ns': 1793328158032951956, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}


def require(value,reason):
    if not value:raise ValueError(reason)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def adopt(amendment_path,amendment_sha256,guards_path,guards_sha256,output):
    require(hashlib.sha256(Path(HELPER['path']).read_bytes()).hexdigest()==HELPER['sha256'],
            'Exact ordinary immutable helper source required')
    h=load('_three_guard_config_adoption_helpers',Path(HELPER['path']));h.checked(HELPER)
    def read(value):return json.loads(h.checked(value).read_bytes())
    def selected(path,digest):
        value=h.pin(Path(path).resolve());require(value['sha256']==digest,'Exact selected metadata SHA required');return value
    ap=selected(amendment_path,amendment_sha256);gp=selected(guards_path,guards_sha256)
    prepared=read(ap);publication=read(gp)
    require(prepared['schema']=='robotron-prepared-unused-three-leg-main-journal128-amendment-v1'
            and prepared['source']==PRODUCER
            and publication['schema']=='robotron-three-capacity-exact-native-guard-publication-v1'
            and publication['status']=='PASS'and publication['ordered_legs']==['C1','R2','C2']
            and publication['old_exact_job_receipts_reused']is False
            and publication['prepared_capacity_amendment']==ap and len(publication['guards'])==3,
            'Only exact new three-job positive guard publication may adopt configs')
    index_pin=publication['original_three_CPU_closeout'];index=read(index_pin)
    require(index['schema']=='robotron-three-capacity-one-original-CPU-independent-closeout-v1'
            and index['status']=='PASS'and index['source']==CLOSER
            and index['actual_exit']==0 and index['actual_CPU_cores']==2
            and index['actual_memory_bytes']==4<<30 and index['actual_runtime_limit_s']==180
            and index['tests_run']==10 and index['new_native_chain_tests']==4
            and index['all_six_descriptors_resources_argv_birth_units_cgroup_and_release_verified']is True
            and index['native_guard_receipts_published']is True,
            'Independent original exact2CPU4G180 PASS and owned closure required')
    job=read(index['actual_CPU_job']);report=read(index['actual_CPU_report'])
    require(SHIM is not None and job['source']==DRIVER and job['readiness_reuse_shim']==SHIM
            and job['amendment_producer']==PRODUCER and job['prepared_amendment']==ap
            and job['prepared_manifest']==prepared['mixed_manifest']
            and report['schema']=='robotron-deadline32-three-capacity-jobs-CPU-guard-result-v1'
            and report['passed']is True and report['errors']==report['failures']==[]
            and report['tests_run']==10 and report['readiness_semantics_reused_from_closed_metadata']==3
            and report['readiness_raw_full_integrity_passes']==3
            and report['original_CPU_job']==index['actual_CPU_job']
            and report['prepared_capacity_amendment']==ap
            and report['old_exact_job_receipts_reused']is False,
            'Actual selected new guard job/report/source binding differs')
    packet=read(h.pin(Path(index['actual_CPU_job']['path']).parent/'prepared-three-CPU-NOT-LAUNCHED.json'))
    require(packet['CPU_job']==index['actual_CPU_job']and packet['driver']==DRIVER
            and packet['prepared_capacity_amendment']==ap,'Exact actual CPU preparation required')
    archive=load('_three_config_adoption_archive',h.checked(packet['archive']))
    immutable=load('_three_config_adoption_immutable',h.checked(packet['reader']))
    terminal=archive.archived_closure(read(index['actual_CPU_closure']),read(index['actual_CPU_owner']),
        lambda value,as_json=True:immutable.read_pin(value,as_json=as_json),exit_zero=True)
    require(terminal['ExecMainCode']=='1'and terminal['ExecMainStatus']=='0',
            'Positive original CPU terminal/reap/archive/release must precede config publication')
    mixed=read(prepared['mixed_manifest']);selection=read(prepared['selected_amendment'])
    control=load('_three_config_adoption_native_controller',h.checked(selection['selected_native_controller']))
    require([r['leg']for r in prepared['subjects']]==[r['leg']for r in mixed['cases'][1:]]==['C1','R2','C2'],
            'Exactly the three original unused future legs required')
    output=Path(output).absolute()
    require(output==output.resolve()and output.parent==LOCAL and not output.exists(),
            'One fresh direct-child adoption directory required')
    planned=[]
    for record,row,guard_pin in zip(prepared['subjects'],mixed['cases'][1:],publication['guards']):
        native=read(row['native_job']);guard=read(guard_pin)
        path=Path(record['qualified_config_path']);parent=Path(row['native_job']['path']).parent
        require(row['leg']==record['leg']and row['native_job']==record['native_job']
                and guard['schema']=='robotron-deadline32-original-prelaunch-family-guard-v1'
                and guard['status']=='PASS'and guard['native_job']==row['native_job']
                and guard['runtime']==row['runtime']and guard['actual_exit']==0
                and guard['actual_CPU_cores']==2 and guard['actual_memory_bytes']==4<<30
                and guard['actual_runtime_limit_s']==180 and guard['original_three_CPU_closeout']==index_pin
                and guard_pin['path']==record['future_CPU_guard_path']==native['prelaunch_family_guard_closeout']
                and row['prospective_qualified_config_path']==str(path)
                and path==parent/'controller-config-main-journal128-CPU-QUALIFIED-original01.json'
                and not path.exists()and not Path(native['output']).exists(),
                'Fresh exact-job positive guard and declared unused qualified config required')
        cfg=read(row['unqualified_controller_config'])
        require(not Path(cfg['output']).exists()and control.checked_config(row['unqualified_controller_config']['path'])==cfg,
                'Original native controller execution must remain unused')
        updated=copy.deepcopy(cfg);pins={v['path']:v for v in cfg['pins']}
        require(guard_pin['path']not in pins,'Unqualified config already consumed the new exact guard')
        pins[guard_pin['path']]=control.pin(guard_pin['path']);updated['pins']=list(pins.values())
        planned.append((row,guard_pin,path,updated))
    # Exclusive directory is the one-shot marker; a partial publication is kept.
    output.mkdir(mode=0o700)
    configs=[]
    for row,guard_pin,path,cfg in planned:
        value=h.put(path,cfg)
        require(control.checked_config(value['path'])==cfg,'Published exact qualified controller config differs')
        configs.append(dict(leg=row['leg'],native_job=row['native_job'],guard=guard_pin,
            unqualified_controller_config=row['unqualified_controller_config'],qualified_config=value))
    return h.put(output/'qualified-three-config-adoption.json',dict(
        schema='robotron-three-capacity-guarded-controller-config-adoption-v1',
        status='PASS_QUALIFIED_CONTROLLER_CONFIG_METADATA_PUBLISHED',source=h.pin(Path(__file__).resolve()),
        prepared_capacity_amendment=ap,guard_publication=gp,original_three_CPU_closeout=index_pin,
        ordered_legs=['C1','R2','C2'],qualified_configs=configs,
        original_R1_qualification=prepared['original_R1_qualification'],
        original_R1_review_precommit=prepared['original_R1_review_precommit'],
        actual_CPU_report=index['actual_CPU_report'],actual_CPU_closure=index['actual_CPU_closure'],
        old_exact_job_receipts_reused=False,no_scientific_payload_launched=True,
        fresh_Main_GPU_port_lease_readiness_proved=False,quality_or_improvement_qualified=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adopt',action='store_true')
    p.add_argument('--amendment',type=Path);p.add_argument('--amendment-sha256')
    p.add_argument('--guards',type=Path);p.add_argument('--guards-sha256');p.add_argument('--output',type=Path)
    p.add_argument('--source-sha256');args=p.parse_args()
    if not args.adopt:print('SOURCE_ONLY_INERT_NO_ACTIONS');return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Exact selected adopter required')
    print(json.dumps(adopt(args.amendment,args.amendment_sha256,args.guards,args.guards_sha256,args.output)),flush=True)


if __name__=='__main__':main()
