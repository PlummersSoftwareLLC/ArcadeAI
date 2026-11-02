"""Guard-only reuse of exact predicates from a closed original metadata scope.

No work at import. No model bodies, live API, service actions or source changes.
Each job freshly checks every full raw SHA and identity; only immutable raw
health/slot predicate results already passed by that exact job are reused.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


SOURCE_CONTRACT_SHA = None  # Unselected until actual metadata PASS and final literal binding.


class ClosedMetadataReadiness:
    def __init__(self, cpu_job, h, phase, authority=None):
        self.h, self.phase = h, phase
        self.authority_pin = cpu_job['closed_metadata_readiness_authority']
        a = self.read(self.authority_pin) if authority is None else authority
        require(a['schema'] == 'robotron-physical192-closed-metadata-and-raw-readiness-predicate-reuse-authority-v1', 'Exact reuse authority required')
        self.a = a
        policy_pin = cpu_job['closed_metadata_readiness_source_contract']
        require(policy_pin['sha256'] == SOURCE_CONTRACT_SHA and a['source_contract'] == policy_pin,
                'Exact selected physical source contract required')
        policy = self.read(policy_pin)
        require(policy['schema'] == 'robotron-physical192-prospective-closed-metadata-guard-source-contract-v1'
                and policy['physical_source_family']['sha256'] == 'eb5070a9ea134c5b16e553e024c554a948d70f469d862d93b7867ae9e9d675bd'
                and policy['physical_health_source_family']['sha256'] == '5a901e68e16270f7985f907964d46cc0ceb7b6e17dd1834009a5d616b88fcecd'
                and policy['actual_new_binding_complete'] is True
                and type(policy['raw_samples']) is int and policy['raw_samples'] >= 3000 and policy['proof_gap_contract'] == 'robotron-main-proof-gap-2s-v1' and policy['maximum_gap_s'] == 2.0 and policy['full_main_input_count'] == 348
                and policy['main_health_profile'] == 'PHYSICAL_ORIGINAL192_TRAIN_CURRENT_TCP_EVAL_ORIGINAL_ONCE',
                'physical source selection differs')
        for key in ('physical_source_family', 'core_source_peer', 'physical_health_source_family', 'joint_engineering',
                    'physical_private_source_peer', 'shared_profile_helper', 'metadata_driver', 'metadata_preparer', 'metadata_contract', 'metadata_closer',
                    'raw_review', 'raw_reviewer', 'lifecycle', 'worker_job', 'outcome', 'reader', 'archive',
                    'physical_main_case', 'physical_input_inventory', 'observer_source_map', 'metadata_assembler',
                    'metadata_controller', 'metadata_resource_packet', 'engineering_finalizer', 'engineering_closer'):
            require(a[key] == policy[key], 'Selected new source differs: ' + key)
            h.checked(a[key])
        joint = self.read(a['joint_engineering'])
        require(joint['schema'] == 'robotron-continuous-physical192-joint-engineering-readiness-v1'
                and joint['status'] == 'ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY'
                and joint['source'] == policy['engineering_finalizer']
                and joint['case'] == policy['physical_main_case']
                and joint['input_inventory_authority'] == policy['physical_input_inventory']
                and joint['source_family'] == policy['physical_health_source_family']
                and joint['observer_sources'] == policy['observer_sources']
                and joint['observer_reviewer'] == a['raw_reviewer']
                and joint['lifecycle'] == a['lifecycle']
                and joint['independent_raw_review'] == a['raw_review']
                and joint['engineering']['long']['independent_raw_review'] == a['raw_review']
                and set(joint['engineering']) == {'warmup','long','abort'}
                and joint['all_three_modes_are_fresh_originals_for_this_physical_case'] is True
                and joint['all_original_engineering_scopes_closed_at_recorded_closer'] is True
                and joint['old_static_or_countbounded_failures_reused_or_requalified'] is False
                and joint['admission_basis'] == 'EVER_BOUND_ORIGINAL192_NOT_SIMULTANEOUS'
                and joint['simultaneous192_actors_claimed'] is False
                and joint['proof_gap_contract'] == policy['proof_gap_contract']
                and joint['maximum_gap_s'] == 2.0 and joint['interval_s'] == .2
                and joint['long_work_contract'] == 'MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S',
                'Only the actual NEW prefix-aware three-original engineering joint may bind reuse')
        for mode, row in joint['engineering'].items():
            closed = self.read(row['closeout'])
            require(closed['source'] == policy['engineering_closer']
                    and closed['status'] == 'PASS_ENGINEERING_ONLY' and closed['mode'] == mode
                    and closed['original_parent_actual_exit'] == 0
                    and closed['worker_actual_exit'] == (1 if mode == 'abort' else 0)
                    and closed['actual_parent_CPU_cores'] == 2 and closed['actual_parent_memory_bytes'] == 4 << 30
                    and closed['actual_parent_runtime_s'] == (1800 if mode == 'long' else 780)
                    and closed['all_original_births_units_cgroups_and_tmpfs_control_absent'] is True,
                    'Actual NEW original engineering scope closure differs')
        require(Path(a['metadata_closeout']['path']).parent == Path(policy['future_metadata_directory'])
                and a['metadata_closeout']['sha256'] != '29ad1900ca8afdcc1dcb9cd871a2a45cbcc278825a2e4959ade938e8d4308e5a'
                and a['metadata_report']['sha256'] != 'c12344e4491857584df5d337adaf9c90d9f53ba14d115e55c48f325b01238f60',
                'Only the NEW closed metadata scope may authorize reuse')
        require(a['metadata_job'] == policy['expected_metadata_job']
                and a['metadata_config'] == policy['expected_metadata_config'],
                'Exact newly prepared physical metadata job/config required')
        self.policy = policy
        close = self.read(a['metadata_closeout'])
        require(close['status'] == 'PASS_ENGINEERING_ONLY' and close['actual_exit'] == 0
                and close['actual_CPU_cores'] == 2 and close['actual_memory_bytes'] == 4 << 30
                and close['actual_runtime_limit_s'] == 600
                and close['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified'] is True,
                'Actual closed original metadata scope required')
        for key, original in [('metadata_report', 'actual_report'), ('metadata_job', 'original_job'),
                              ('metadata_config', 'original_config'), ('metadata_owner', 'original_owner'),
                              ('metadata_closure', 'original_closure'), ('metadata_closer', 'source')]:
            require(a[key] == close[original], 'Metadata closure identity differs: ' + key)
            h.checked(a[key])
        immutable = load('_closed_metadata_immutable', h.checked(a['reader']))
        archive = load('_closed_metadata_archive', h.checked(a['archive']))
        def read_archive(pin, as_json=True):
            return immutable.read_pin(pin, as_json=as_json)
        terminal = archive.archived_closure(self.read(a['metadata_closure']), self.read(a['metadata_owner']), read_archive, exit_zero=True)
        require(terminal['ExecMainCode'] == '1' and terminal['ExecMainStatus'] == '0', 'Original metadata terminal exit differs')
        metadata_job, report = self.read(a['metadata_job']), self.read(a['metadata_report'])
        require(report['status'] == 'PASS' and report['original_job'] == a['metadata_job']
                and report['native_prepared'] == a['native_prepared'] == cpu_job['prepared_manifest']
                and report['Torch_imported'] is report['GPU_or_MAME_launched'] is False,
                'Closed metadata must bind these exact four jobs')
        require(metadata_job['schema'] == 'robotron-selected-admission-study-CPU-preparation-v1'
                and metadata_job['original_attempt'] == 1 and metadata_job['no_retry'] is True
                and metadata_job['deadline_readiness'] == a['joint_engineering'], 'Original metadata source inputs differ')
        config = self.read(a['metadata_config'])
        require(config['argv'][3] == a['metadata_driver']['path'] and config['argv'][-1] == a['metadata_driver']['sha256'], 'Original metadata driver argv differs')
        for pin in metadata_job['inputs']:
            h.checked(pin)
        require(all(a[key] in metadata_job['inputs'] for key in ('metadata_preparer', 'metadata_contract', 'shared_profile_helper', 'metadata_assembler', 'metadata_controller')),
                'Actual metadata job did not hold the selected predicate sources')
        prepared = self.read(a['native_prepared'])
        require(prepared['engineering_only'] is False and prepared['source_preparer'] == a['metadata_preparer']
                and [row['leg'] for row in prepared['cases']] == a['ordered_legs'] == ['R1', 'C1', 'R2', 'C2']
                and [row['native_job'] for row in prepared['cases']] == a['native_jobs'] == policy['exact_jobs'], 'Original four-job preparation differs')
        require(Path(a['native_prepared']['path']).parent == Path(policy['future_study_directory'])
                and all(row['runtime'] == policy['native_runtime']
                        and row['native_controller'] == policy['native_controller'] for row in prepared['cases']),
                'Only the selected physical exact four subjects may be reused')
        self.subjects = [(row['leg'], self.read(row['native_job'])) for row in prepared['cases']]
        self.raw = self.read(a['raw_review'])
        require(self.raw['status'] == 'PASS' and self.raw['lifecycle'] == a['lifecycle']
                and self.raw['original_job'] == a['worker_job'] and self.raw['full_main_input_count'] == policy['full_main_input_count']
                and self.raw['accepted_samples'] == a['raw_samples'] == policy['raw_samples']
                and self.raw['raw_API_and_TCP_and_retirement_snapshots_replayed'] is True
                and self.raw['main_health_profile'] == policy['main_health_profile']
                and all(self.raw[key] is True for key in ('source_bound_original192_physical_bootstrap_verified',
                    'TRAIN155_original_physical_and_current_TCP_verified',
                    'EVAL37_original_connection_and_strict_retirement_evidence_verified',
                    'EVAL_closed_slots_have_positive_normal0_reap_and_cleanup_verified',
                    'prior_completed_EVAL_prefix_and_current_suffix_verified'))
                and self.raw['accepted_evidence_and_projection_gaps_verified'] is True and self.raw['proof_gap_contract'] == 'robotron-main-proof-gap-2s-v1' and self.raw['verified_maximum_gap_s'] == 2.0,
                'Actual full raw readiness predicates required')
        life = self.read(a['lifecycle'])
        require(life['worker_job'] == a['worker_job'] and life['outcome'] == a['outcome'], 'Original readiness lifecycle differs')
        outcome = self.read(a['outcome'])
        require(len(outcome['samples']) == a['raw_samples'], 'Original raw corpus count differs')
        self.samples = outcome['samples']
        self.counts = dict(semantics_reused_from_closed_metadata=0, raw_full_integrity_passes=0)
        phase('closed_metadata_authority_validated', samples=len(self.samples))

    def read(self, pin):
        return json.loads(self.h.checked(pin).read_bytes())

    def validate_launch(self, job, context, h):
        require(h is self.h and any(job == subject for _, subject in self.subjects), 'Reuse only exact originally validated job')
        leg = next(leg for leg, subject in self.subjects if job == subject)
        require(all(os.environ.get(key, '0') == '0' for key in
                    ('ROBOTRON_CONTINUOUS_TRAINING_MODE', 'ROBOTRON_ROLLING_TRAINING_CLEANUP',
                     'ROBOTRON_CONTINUOUS_STARTUP_HOLD')),
                'Private frozen sidecar must remain source-mode0 before ownership')
        family = context['family']
        require(family['native_launch_qualified'] is True, 'Engineering family is never scientific launch authority')
        require(family['main_domain_hot_review'] == self.a['joint_engineering'] and family['round_observer_reviewer'] == self.a['raw_reviewer'], 'Original readiness source binding differs')
        proof = self.read(family['main_domain_hot_review'])
        require(proof['lifecycle'] == self.a['lifecycle'], 'Original readiness proof lifecycle differs')
        h.checked(family['round_observer_reviewer'])
        verified = copy.deepcopy(self.raw)
        require(verified['original_sources'] == family['main_observer'] == self.policy['observer_sources'], 'Main-domain proof uses a different observer source')
        lifecycle = self.read(proof['lifecycle'])
        worker = self.read(lifecycle['worker_job'])
        proved = self.read(worker['case'])
        current = context['main_binding']
        shared = load('_prefix_physical_guard_domain_helper', h.checked(self.policy['shared_profile_helper']))
        shared.same_domain(proved, current)
        shared.validate_inventory(current, h)
        require(len(current['inputs']) == self.policy['full_main_input_count'], 'Exact physical input domain count differs')
        require(proved['inputs'] == current['inputs'] and proved['slot_eval'] == current['slot_eval'],
                'Readiness proof belongs to a different complete source/role domain')
        static = ('pid', 'starttime_ticks', 'parent_pid', 'cgroup', 'command', 'environment', 'affinity', 'uids', 'executable')
        for role in ('trainer', 'fleet'):
            old, actual = proved['owners'][role], current['owners'][role]
            require(old['unit'] == actual['unit'] and old['invocation'] == actual['invocation']
                    and all(old['process'][key] == actual['process'][key] for key in static),
                    'Readiness proof belongs to a different original main owner')
        for kind in ('optimizer', 'replay'):
            require(all(proved['exposure'][kind][key] == current['exposure'][kind][key]
                        for key in ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')),
                    'Readiness exposure lineage changed')
        outcome = self.read(lifecycle['outcome'])
        require(lifecycle['outcome'] == self.a['outcome'] and outcome['samples'] == self.samples, 'Exact original raw corpus differs')
        self.phase('raw_full_integrity_begin', leg=leg, samples=len(self.samples))
        for index, value in enumerate(outcome['samples']):
            h.checked(value)  # Fresh full SHA + all full identity fields, for EACH exact job.
            if (index + 1) % 512 == 0:
                self.phase('raw_full_integrity_progress', leg=leg, checked=index + 1)
        h.checked(self.a['outcome'])
        h.checked(self.a['raw_review'])
        self.counts['semantics_reused_from_closed_metadata'] += 1
        self.counts['raw_full_integrity_passes'] += 1
        self.phase('raw_full_integrity_complete', leg=leg, checked=len(self.samples))
        return verified

    def bind(self, contract):
        require(self.h.pin(Path(contract.__file__).resolve()) == self.a['metadata_contract'], 'Exact original contract source required')
        contract.validate_launch = self.validate_launch
        return contract
