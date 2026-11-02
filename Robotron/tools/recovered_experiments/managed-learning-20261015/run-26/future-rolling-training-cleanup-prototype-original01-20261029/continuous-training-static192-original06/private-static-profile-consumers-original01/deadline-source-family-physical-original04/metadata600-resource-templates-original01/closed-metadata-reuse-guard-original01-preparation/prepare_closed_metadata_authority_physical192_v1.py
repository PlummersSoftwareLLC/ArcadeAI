"""Build NEW exact-job predicate reuse authority only after actual metadata PASS.

Default inert. Explicit preparation reads closed immutable metadata and writes
one exclusive authority. It never replays raw bodies, launches or controls a
process, opens a model, or reuses a failed/old study's semantic authority.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
LOCAL = Path(__file__).resolve().parent
SOURCE_CONTRACT_SHA = '1504401ad9fcffd33f56c2997de7e2b24bb9f014615b027484339aa01631b461'
SHIM_SHA = '7390cea683ae09ffb16ee82c2dcfec7f71bbdc69438dde3a72141cfd65f97a27'
HELPERS_SHA = '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def helpers():
    path = ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest() == HELPERS_SHA, 'Selected helpers differ')
    return load('_physical192_closed_metadata_prepare_helpers', path)


def read(pin, h):
    require(pin['identity']['mode'] == '0o444' and pin['identity']['nlink'] == 1,
            'Immutable single-link metadata PIN required')
    return json.loads(h.checked(pin).read_bytes())


def selection(path, expected_sha, h):
    selected = h.pin(Path(path).resolve())
    require(selected['sha256'] == expected_sha, 'Actual ROOT selection differs')
    value = read(selected, h)
    require(set(value) == {'schema','source_contract','metadata_closeout','authority_output','native_prepared',
                          'actual_guard_packet','actual_guard_closeout','CPU_or_scientific_launch_qualified'}
            and value['schema'] == 'robotron-physical192-new-closed-metadata-reuse-ROOT-selection-v1'
            and value['CPU_or_scientific_launch_qualified'] is False
            and value['actual_guard_packet'] is value['actual_guard_closeout'] is None,
            'Exact prospective ROOT selection required')
    policy_pin = h.pin(LOCAL/'selected-physical192-prospective-source-contract.json')
    require(policy_pin['sha256'] == SOURCE_CONTRACT_SHA and value['source_contract'] == policy_pin,
            'Selected immutable physical source contract differs')
    policy = read(policy_pin, h)
    require(value['metadata_closeout'] is not None and value['native_prepared'] is not None
            and value['authority_output'] is not None, 'Actual new closed metadata facts remain unfilled')
    require(Path(value['metadata_closeout']['path']) ==
            Path(policy['future_metadata_directory'])/'independent-original-CPU-scope-closeout.json',
            'Only the exact NEW metadata closeout is admissible')
    require(Path(value['native_prepared']['path']) ==
            Path(policy['future_study_directory'])/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json',
            'Only the exact NEW four-job manifest is admissible')
    require(Path(value['authority_output']) == LOCAL.parent/'actual-closed-metadata-reuse-authority-original01.json',
            'Exact exclusive future authority path required')
    return selected, value, policy_pin, policy


def prepare(path, expected_sha):
    h = helpers()
    root_selection, selected, policy_pin, policy = selection(path, expected_sha, h)
    close = read(selected['metadata_closeout'], h)
    require(close['source'] == policy['metadata_closer'], 'Selected metadata closer differs')
    a = dict(schema='robotron-physical192-closed-metadata-and-raw-readiness-predicate-reuse-authority-v1',
             purpose='Only certified NEW four-job raw health/slot semantics are reused; every raw FULLSHA/full8 identity is fresh per job.',
             ROOT_selection=root_selection, source_contract=policy_pin,
             metadata_closeout=selected['metadata_closeout'],
             native_prepared=selected['native_prepared'], ordered_legs=['R1','C1','R2','C2'],
             raw_samples=policy['raw_samples'], full_main_input_count=policy['full_main_input_count'], metadata_original_actual_exit=0,
             raw_predicates_and_all192_slot_coverage_already_passed_for_each_exact_job=True,
             proof_kind='Compositional closed execution: exact metadata driver invokes exact physical preparer; all four validate_launch calls precede final manifest/report PASS. No invented per-case reports.',
             source=h.pin(Path(__file__).resolve()), CPU_or_scientific_launch_by_preparer=False)
    for key in ('physical_source_family','core_source_peer','physical_health_source_family','joint_engineering',
                'physical_private_source_peer','shared_profile_helper','metadata_driver','metadata_preparer','metadata_contract','metadata_closer',
                'raw_review','raw_reviewer','lifecycle','worker_job','outcome','reader','archive'):
        a[key] = policy[key]
    for key, field in (('metadata_report','actual_report'),('metadata_job','original_job'),
                       ('metadata_config','original_config'),('metadata_owner','original_owner'),
                       ('metadata_closure','original_closure')):
        a[key] = close[field]
    report = read(a['metadata_report'], h)
    require(report['native_prepared'] == a['native_prepared'], 'Actual metadata validated a different manifest')
    manifest = read(a['native_prepared'], h)
    a['native_jobs'] = [case['native_job'] for case in manifest['cases']]
    shim_pin = h.pin(LOCAL/'closed_metadata_readiness_reuse_physical192_v1.py')
    require(shim_pin['sha256'] == SHIM_SHA, 'Actual prospective reuse shim differs')
    shim = load('_physical192_closed_metadata_prepare_shim', h.checked(shim_pin))
    # The same verifier used by the CPU guard proves the candidate authority
    # BEFORE its exclusive publication. No raw sample bodies are read here.
    shim.ClosedMetadataReadiness(dict(prepared_manifest=a['native_prepared'],
        closed_metadata_readiness_authority=None, closed_metadata_readiness_source_contract=policy_pin),
        h, lambda *args, **kwargs: None, authority=a)
    target = Path(selected['authority_output'])
    require(target.resolve() == target and target.parent.is_dir() and not target.exists(),
            'Authority output must be exclusive and canonical')
    return h.put(target, a)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--selection', type=Path)
    p.add_argument('--selection-sha256')
    p.add_argument('--source-sha256')
    a = p.parse_args()
    if not a.prepare:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == a.source_sha256,
            'Actual authority generator source differs')
    print(json.dumps(prepare(a.selection, a.selection_sha256)), flush=True)


if __name__ == '__main__':
    main()
