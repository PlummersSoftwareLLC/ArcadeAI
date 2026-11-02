"""Default inert. Bind three FRESH actual physical MAIN engineering contexts.

Root must first install/start/verify the preserved continuous main and bind its
ever-bound original192 case and exact inventory. This preparer does not collect
live evidence, launch a process, alter the case, or qualify a scientific study.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = Path(__file__).resolve().parent
MODE_ROOT = HERE.parent
HC = MODE_ROOT/'health-consumer-live-pidfd-current-EVAL-quiescence-original05'
PROFILE = MODE_ROOT/'health-consumer-live-pidfd-current-EVAL-quiescence-original05/prepare_current_eval_quiescence_case_v5.py'
HELPER = ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
HELPER_SHA = '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
FAMILY_SHA = '9e00ed11b9ad56b8a16911eb38c3d48f9edd0a7fa7d0bb670749cc9ed75d0eac'
MAP_SHA = '5d8ce346200f8737aae484b72a15b7f38dd8ea1da8ac463acc1c94531894f8b9'
PROFILE_SHA = 'cce755775dfa8134a446b0d42d3a13bf96bcca23257fc92b8798622bee2a7b2e'
REGISTRY_SHA = '8cc5340708a73ffb97b16be4b96e72b3d5560ee0b371b7ffd8d67c4074cf76b4'
REVIEWER_SHA = '30ea4d2eb6d97b5ccbd04e262f7b4c45e47af268f7644f7893ad88deba47a133'


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(path, digest, name):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Exact source factory changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(case_path, case_sha, output):
    h = load(HELPER, HELPER_SHA, '_static_engineering_metadata_helpers')
    own = h.pin(Path(__file__).resolve())
    require(own['identity']['mode'] == '0o444', 'Frozen explicit preparer required')
    selected = h.pin(case_path.resolve(strict=True))
    require(selected['sha256'] == case_sha and selected['identity']['mode'] == '0o444',
            'Actual immutable NEW Root static case required')
    require(output.is_absolute() and output.parent.resolve(strict=True) == HERE and not output.exists(),
            'One exclusive original context directory required')
    case = json.loads(h.checked(selected).read_bytes())
    require(case['schema'] == 'robotron-original192-live-pidfd-current-eval-quiescence-case-v5'
            and case['source_guard'] == str(HC/'continuous_physical192_health_v5.py'),
            'Old whole-round or unselected source case cannot be adopted')
    r = load(HC/'continuous_physical192_registry_v5.py', REGISTRY_SHA, '_static_engineering_registry')
    r.validate_case(case)  # Pure held metadata/event joins; no census/proc/API.
    profile = load(PROFILE, PROFILE_SHA, '_static_engineering_inventory')
    profile.validate_inventory(case, h)
    family_pin = h.pin(HC/'prepared-live-pidfd-current-EVAL-quiescence-health-and-observer-SOURCE-ONLY-NOT-QUALIFIED-v5.json')
    map_pin = h.pin(HC/'prospective-live-pidfd-current-EVAL-quiescence-eight-role-observer-source-map-v5.json')
    require(family_pin['sha256'] == FAMILY_SHA and map_pin['sha256'] == MAP_SHA,
            'Exact frozen static source family and eight-role map required')
    family = json.loads(h.checked(family_pin).read_bytes())
    declared = json.loads(h.checked(map_pin).read_bytes())
    observers = declared['observer_sources']
    require(set(observers) == {'client','worker','health','health_base','registry','durability','control','interpreter'},
            'Exact static eight-role observer map required')
    for value in observers.values():
        h.checked(value)
    reviewer = h.pin(HC/'review_continuous_physical192_observer_v5.py')
    require(reviewer['sha256'] == REVIEWER_SHA, 'Exact static raw reviewer required')
    paths = [Path(value['path']) for value in observers.values()]
    paths += [Path(value['path']) for value in (family_pin, map_pin, reviewer)]
    paths += [PROFILE, HELPER,
        HC/'independent-live-pidfd-current-EVAL-quiescence-health-six-source-peer-v5.json',
        ROOT/'tools/training_connection_lifecycle_proposal_20261023/finalize_dedicated_main_health_v1.py']
    paths += [HERE/name for name in ('prepare_physical192_engineering_v4.py',
                                    'probe_physical192_engineering_v4.py',
                                    'close_physical192_engineering_v4.py')]
    sources = {str(path): h.pin(path) for path in paths}
    # Basename keys retain the unchanged engineering closer/intents interface.
    require(len({Path(key).name for key in sources}) == len(sources), 'Duplicate held source basename')
    sources = {Path(path).name: value for path, value in sources.items()}
    require(all(value['identity']['mode'] == '0o444'
                for value in sources.values() if Path(value['path']).is_relative_to(MODE_ROOT)),
            'Prospective private sources must be frozen before actual preparation')
    before_inputs = json.loads(json.dumps(case['inputs']))
    output.mkdir(mode=0o700)
    records = []
    for mode in ('warmup', 'long', 'abort'):
        directory = output/(mode+'-original01'); directory.mkdir(mode=0o700)
        unit = 'robotron-original192-current-eval-quiescence-proof2s-%s-engineering-%s-original01-20261029.service' % (mode, case_sha[:16])
        command = ['systemd-run','--user','--unit='+unit,
            '-p','CPUQuota=200%','-p','MemoryMax=4G','-p','MemorySwapMax=0','-p','TasksMax=128',
            '-p','RuntimeMaxSec='+str(1800 if mode=='long' else 780),'-p','RemainAfterExit=yes','-p','Restart=no',
            '-p','TimeoutStopSec=5','-p','SendSIGKILL=no',
            '-p','StandardOutput=append:'+str(directory/'console.txt'),
            '-p','StandardError=append:'+str(directory/'console.txt'),
            '/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3','-I','-B',
            str(HERE/'probe_physical192_engineering_v4.py'),'--execute','--mode',mode,
            '--case',selected['path'],'--case-sha256',selected['sha256'],'--output',str(directory/'runtime')]
        intent = h.put(directory/'original-launch-intent-NOT-EXECUTED.json', dict(
            schema='robotron-original192-immutable-bootstrap-live-pidfd-engineering-intent-v4',
            argv=command,unit=unit,attempt=1,no_retry=True,case=selected,sources=sources,
            engineering_only=True,actual_live_owner=None,actual_original_tool=None,
            source=own,simultaneous192_actors_claimed=False))
        records.append(dict(kind='main-current-once-EVAL-quiescence192',mode=mode,output=str(directory),unit=unit,
            intent=intent,original_live_owner=None,actual_execution=None))
    for value in sources.values():
        h.checked(value)
    require(h.pin(selected['path']) == selected and case['inputs'] == before_inputs,
            'Actual selected case or held input domain changed during preparation')
    return h.put(output/'prepared-three-original-physical192-contexts-NOT-LAUNCHED.json', dict(
        schema='robotron-original192-immutable-bootstrap-live-pidfd-three-engineering-preparation-v4',status='DATA_PREPARED_NOT_LAUNCHED',
        source=own,source_family=family_pin,source_map=map_pin,case=selected,
        input_inventory_authority=case['input_inventory_authority'],actual_held_input_count=len(case['inputs']),
        historical_parent_main_input_count=247,held_case_and_inputs_unchanged=True,
        sources=sources,observer_sources=observers,observer_reviewer=reviewer,
        logical_observer_dependency_count=8,records=records,
        actual_launch_index_schema='robotron-original192-immutable-bootstrap-live-pidfd-three-original-launches-v4',
        after_actual_operator_launch='Root alone replaces None owner/execution fields in a NEW immutable actual index; this preparation never proves a launch.',
        warmup_work_s=0,abort_work_s=5,long_minimum_work_s=600,long_maximum_work_s=1200,
        long_minimum_observed_samples=3000,long_work_contract='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S',worker_initial_samples=100,
        worker_interval_s=.2,worker_maximum_gap_s=2.0,cached_retired_API_TTL_s=.5,
        observer_CPU_cores=2,observer_memory_bytes=4<<30,observer_runtime_s=4260,
        parent_CPU_cores=2,parent_memory_bytes=4<<30,parent_runtime_s_by_mode=dict(warmup=780,long=1800,abort=780),
        accepted_profile='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5',
        admission_basis='EVER_BOUND_ORIGINAL192_NOT_SIMULTANEOUS',simultaneous192_actors_claimed=False,
        actual_original_owners=None,actual_warmup_or_long_or_abort_closures=None,
        actual_static_context_engineering_qualified=False,scientific_launch_qualified=False,
        quality_qualified=False,main_runtime_changed=False,old_invalid_studies_retried=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare', action='store_true'); p.add_argument('--case', type=Path)
    p.add_argument('--case-sha256'); p.add_argument('--output', type=Path)
    args = p.parse_args()
    if not args.prepare:
        print('PLAN_ONLY_NO_READS_OUTPUTS_IMPORTS_PROBES_OR_ACTIONS'); return
    print(json.dumps(prepare(args.case, args.case_sha256, args.output)), flush=True)


if __name__ == '__main__':
    main()
