"""Default inert. Bind NEW actual static MAIN warmup/long/abort DATA only.

The old original600s scope and its failure remain immutable. Root must first install/start/verify the preserved continuous main and bind its
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
MODE_ROOT = HERE.parent.parent
HC = MODE_ROOT/'health-consumer-original01'
PROFILE = MODE_ROOT/'private-static-profile-consumers-original01/static_profile_contract_v2.py'
HELPER = ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
HELPER_SHA = '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
FAMILY_SHA = '72e03ed29d4f446bac8bdf4d7557a85b01536b43eb7a71c174e305521535c1af'
MAP_SHA = '4629c151898362a71c3aa1f011c2088154c1cd69b9abc8959efdad79103c7410'
PROFILE_SHA = '5260662e651c6f26cde42bb04cde913dd51015658d071499b6966e661e6a451b'
REGISTRY_SHA = '2f3eddaf75ee3b9a875d0a621a63eeea7274eae3afa75bcceb309002233316d1'
REVIEWER_SHA = 'f6dcd7b9ae7556bc1e669b3973a6c5797f845d89c23e2d62a4955b55b519590a'


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
    require(case['schema'] == 'robotron-continuous-static192-health-case-v1'
            and case['source_guard'] == str(HC/'continuous_static192_health_v1.py'),
            'Old whole-round or unselected source case cannot be adopted')
    r = load(HC/'continuous_static192_registry_v1.py', REGISTRY_SHA, '_static_engineering_registry')
    r.validate_case(case)  # Pure held metadata/event joins; no census/proc/API.
    profile = load(PROFILE, PROFILE_SHA, '_static_engineering_inventory')
    profile.validate_inventory(case, h)
    family_pin = h.pin(HC/'prepared-continuous-static192-typed-health-and-observer-SOURCE-ONLY-NOT-QUALIFIED-v1.json')
    map_pin = h.pin(HC/'prospective-static192-eight-role-observer-source-map-v1.json')
    require(family_pin['sha256'] == FAMILY_SHA and map_pin['sha256'] == MAP_SHA,
            'Exact frozen static source family and eight-role map required')
    family = json.loads(h.checked(family_pin).read_bytes())
    declared = json.loads(h.checked(map_pin).read_bytes())
    observers = declared['observer_sources']
    require(set(observers) == {'client','worker','health','health_base','registry','durability','control','interpreter'},
            'Exact static eight-role observer map required')
    for value in observers.values():
        h.checked(value)
    reviewer = h.pin(HC/'review_continuous_static192_observer_v1.py')
    require(reviewer['sha256'] == REVIEWER_SHA, 'Exact static raw reviewer required')
    paths = [Path(value['path']) for value in observers.values()]
    paths += [Path(value['path']) for value in (family_pin, map_pin, reviewer)]
    paths += [PROFILE, HELPER,
        HC/'independent-continuous-static192-typed-health-and-observer-source-peer-v1.json',
        ROOT/'tools/training_connection_lifecycle_proposal_20261023/finalize_dedicated_main_health_v1.py']
    paths += [HERE/name for name in ('prepare_static192_countbounded_long_v2.py',
                                    'probe_static192_countbounded_long_v2.py',
                                    'close_static192_countbounded_long_v2.py')]
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
    for mode in ('long',):
        directory = output/(mode+'-original01'); directory.mkdir(mode=0o700)
        unit = 'robotron-static192-proof2s-%s-countbounded-%s-original02-20261029.service' % (mode, case_sha[:16])
        command = ['systemd-run','--user','--unit='+unit,
            '-p','CPUQuota=200%','-p','MemoryMax=4G','-p','MemorySwapMax=0','-p','TasksMax=128',
            '-p','RuntimeMaxSec=1800','-p','RemainAfterExit=yes','-p','Restart=no',
            '-p','TimeoutStopSec=5','-p','SendSIGKILL=no',
            '-p','StandardOutput=append:'+str(directory/'console.txt'),
            '-p','StandardError=append:'+str(directory/'console.txt'),
            '/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3','-I','-B',
            str(HERE/'probe_static192_countbounded_long_v2.py'),'--execute','--mode',mode,
            '--case',selected['path'],'--case-sha256',selected['sha256'],'--output',str(directory/'runtime')]
        intent = h.put(directory/'original-launch-intent-NOT-EXECUTED.json', dict(
            schema='robotron-static192-countbounded-long-original-engineering-intent-v2',
            argv=command,unit=unit,attempt=1,no_retry=True,case=selected,sources=sources,
            engineering_only=True,actual_live_owner=None,actual_original_tool=None,
            source=own,simultaneous192_actors_claimed=False))
        records.append(dict(kind='main-static192',mode=mode,output=str(directory),unit=unit,
            intent=intent,original_live_owner=None,actual_execution=None))
    for value in sources.values():
        h.checked(value)
    require(h.pin(selected['path']) == selected and case['inputs'] == before_inputs,
            'Actual selected case or held input domain changed during preparation')
    return h.put(output/'prepared-countbounded-original-static192-long-NOT-LAUNCHED.json', dict(
        schema='robotron-static192-countbounded-long-engineering-preparation-v2',status='DATA_PREPARED_NOT_LAUNCHED',
        source=own,source_family=family_pin,source_map=map_pin,case=selected,
        input_inventory_authority=case['input_inventory_authority'],actual_held_input_count=len(case['inputs']),
        historical_parent_main_input_count=247,held_case_and_inputs_unchanged=True,
        sources=sources,observer_sources=observers,observer_reviewer=reviewer,
        logical_observer_dependency_count=8,records=records,
        actual_launch_index_schema='robotron-static192-countbounded-long-original-engineering-launches-v2',
        after_actual_operator_launch='Root alone replaces None owner/execution fields in a NEW immutable actual index; this preparation never proves a launch.',
        long_minimum_work_s=600,long_maximum_work_s=1200,long_minimum_observed_samples=3000,
        long_work_contract='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S',worker_initial_samples=100,
        worker_interval_s=.2,worker_maximum_gap_s=2.0,cached_retired_API_TTL_s=.5,
        observer_CPU_cores=2,observer_memory_bytes=4<<30,observer_runtime_s=4260,
        parent_CPU_cores=2,parent_memory_bytes=4<<30,parent_runtime_s=1800,
        accepted_profile='STATIC_ORIGINAL192_NO_FAULT_ADOPTION',
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
