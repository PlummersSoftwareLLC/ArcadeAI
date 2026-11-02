"""Default inert. NEW long/abort data only; never launches or controls a process."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = Path(__file__).resolve().parent
COMPONENT = HERE.parent/'capture-bracket-revision02'
ORIGINAL = ROOT/'tools/post_recovery_evaluation'
HELPER = ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
HELPER_SHA = '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
UNIT_BASE = 'robotron-retired-api-deadline-{}-engineering-original01-20261029.service'
SELECTED_COMPONENT_SHA = {'round_observer_client_retired_API_v4.py': '96ec161c65ce42281f16f0534f4886ea08d9cf5e1a70e761eb4271515d289fea', 'round_observer_retired_API_v4.py': '8511b62f6e1dc5484b2a3b0604004875d84417db2e170ed5478efcacc7e0d854', 'round_health_transport_retired_API_v4.py': '46da3997f9a388f93f3473f9fc866df37e175664f73dc7ef024584a70e6f2985', 'round_main_health_retired_API_v4.py': 'bb578e92a7cb796651673ca7e0bbf43027bc5058ee88ed4ae65a973ce7460c3a', 'api_cached_projections_v3.py': 'db5f06e406bf62128ccaa46ce3155c2a90c76c31daad37d8afb2fcbfa8c36f02', 'review_round_observer_retired_API_v4.py': '5b85c725bfacfbdb047e1f7791f350122e1097d8d0c988d29ce76cf433aa78cb'}


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def prepare(case_path,case_sha,output):
    assert hashlib.sha256(HELPER.read_bytes()).hexdigest()==HELPER_SHA
    h=load('_declared_launcher_data_helpers',HELPER)
    own=h.pin(Path(__file__).resolve())
    assert own['identity']['mode']=='0o444'
    original_case=h.pin(case_path.resolve());assert original_case['sha256']==case_sha
    assert not output.exists() and output.parent.resolve(strict=True)==HERE
    source_paths=[COMPONENT/name for name in ('round_main_health_retired_API_v4.py',
        'round_health_transport_retired_API_v4.py','round_observer_retired_API_v4.py',
        'round_observer_client_retired_API_v4.py','review_round_observer_retired_API_v4.py',
        'api_cached_projections_v3.py')]
    source_paths.append(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/launcher_census_v1.py'))
    source_paths += [HERE/name for name in ('probe_retired_API_engineering_v1.py','prepare_retired_API_engineering_v1.py')]
    source_paths.append(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/readonly-mmap-source-validation-original02/close_declared_launcher_engineering_mmap_v2.py'))
    source_paths += [ORIGINAL/name for name in ('round_admission_proof_v2.py',
        'buffered_raw_writer_v2.py','volatile_live_control_v1.py')]
    source_paths.append(Path('/usr/bin/python3').resolve(strict=True))
    sources={path.name:h.pin(path)for path in source_paths}
    observer_sources={role:sources[name]for role,name in dict(
        client='round_observer_client_retired_API_v4.py',worker='round_observer_retired_API_v4.py',
        health='round_health_transport_retired_API_v4.py',health_base='round_main_health_retired_API_v4.py',
        API_projection='api_cached_projections_v3.py',round_admission='round_admission_proof_v2.py',
        launcher_census='launcher_census_v1.py',durability='buffered_raw_writer_v2.py',
        control='volatile_live_control_v1.py',interpreter=Path('/usr/bin/python3').resolve(strict=True).name).items()}
    assert len(observer_sources)==10
    assert all(sources[name]['sha256']==digest for name,digest in SELECTED_COMPONENT_SHA.items())
    assert all(value['identity']['mode']=='0o444' for path,value in sources.items() if Path(value['path']).parent in (COMPONENT,HERE))
    launch=load('_declared_launcher_case_preparation',h.checked(sources['launcher_census_v1.py']))
    case=json.loads(h.checked(original_case).read_bytes())
    assert len(case['inputs'])==247
    launch.verify_contract(case)
    held_before=json.loads(json.dumps(case['inputs']))
    prior_source_guard=case['source_guard']
    case['source_guard']=str(COMPONENT/'round_main_health_retired_API_v4.py')
    assert case['inputs']==held_before and len(case['inputs'])==247
    output.mkdir(mode=0o700)
    binding=h.put(output/'declared-launcher-main-case.json',case)
    records=[]
    for mode in ('long','abort'):
        directory=output/(mode+'-original01');directory.mkdir(mode=0o700)
        unit=UNIT_BASE.format(mode)
        command=['systemd-run','--user','--unit='+unit,'-p','CPUQuota=200%',
            '-p','MemoryMax=4G','-p','MemorySwapMax=0','-p','TasksMax=128',
            '-p','RuntimeMaxSec=780','-p','RemainAfterExit=yes','-p','Restart=no',
            '-p','TimeoutStopSec=5','-p','SendSIGKILL=no',
            '-p','StandardOutput=append:'+str(directory/'console.txt'),
            '-p','StandardError=append:'+str(directory/'console.txt'),
            '/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3','-I','-B',
            str(HERE/'probe_retired_API_engineering_v1.py'),'--execute','--mode',mode,
            '--case',binding['path'],'--case-sha256',binding['sha256'],'--output',str(directory/'runtime')]
        intent=h.put(directory/'original-launch-intent-NOT-EXECUTED.json',dict(
            schema='robotron-declared-launcher-observer-original-engineering-intent-v1',
            argv=command,unit=unit,attempt=1,no_retry=True,case=binding,sources=sources,
            engineering_only=True,actual_live_owner=None,actual_original_tool=None,
            live_main_active_count_not_assumed192=True,source=own))
        records.append(dict(kind='deadline',mode=mode,output=str(directory),unit=unit,intent=intent,
            original_live_owner=None,actual_execution=None))
    for value in sources.values():h.checked(value)
    assert h.pin(original_case['path'])==original_case
    return h.put(output/'prepared-two-original-observer-contexts-NOT-LAUNCHED.json',dict(
        schema='robotron-declared-launcher-two-observer-engineering-preparation-v1',
        status='DATA_PREPARED_NOT_LAUNCHED',source=own,original_case=original_case,case=binding,
        original_held_input_count=247,held_inputs_unchanged=True,
        source_guard_transition=dict(before=prior_source_guard,after=case['source_guard']),
        raw_retired_receipt_journal_and_PID_absence_evidence_reviewer_bound=True,
        sources=sources,observer_sources=observer_sources,logical_observer_dependency_count=10,records=records,
        actual_launch_index_schema='robotron-declared-launcher-two-original-engineering-launches-v1',
        after_actual_operator_launch='Root writes NEW actual index replacing None owner fields with actual immutable original-live-owner pins; this preparation is not a launch index.',
        long_work_s=600,abort_work_s=5,worker_initial_samples=100,worker_maximum_gap_s=.5,
        observer_CPU_cores=2,observer_memory_bytes=4<<30,observer_runtime_s=4260,
        actual192_fixture_qualified=None,actual_long_or_abort_closure=None,
        retired_API_projection_engineering_qualified=False,
        scientific_launch_qualified=False,quality_qualified=False,main_runtime_changed=False,
        old_invalid_study_retried=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--case',type=Path)
    parser.add_argument('--case-sha256');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.prepare:
        print('INERT: no reads, outputs, processes or controls');return
    print(json.dumps(prepare(args.case,args.case_sha256,args.output)),flush=True)


if __name__=='__main__':main()
