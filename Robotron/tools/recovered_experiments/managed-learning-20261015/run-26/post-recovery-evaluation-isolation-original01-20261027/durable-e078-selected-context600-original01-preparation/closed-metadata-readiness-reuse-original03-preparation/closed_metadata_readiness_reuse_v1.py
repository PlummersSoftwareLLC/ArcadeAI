"""Guard-only reuse of exact predicates from a closed original metadata scope.

No work at import. No model bodies, live API, service actions or source changes.
Each job freshly checks every full raw SHA and identity; only immutable raw
health/slot predicate results already passed by that exact job are reused.
"""
import copy
import importlib.util
import json
from pathlib import Path


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class ClosedMetadataReadiness:
    def __init__(self, cpu_job, h, phase):
        self.h, self.phase = h, phase
        self.authority_pin = cpu_job['closed_metadata_readiness_authority']
        a = self.read(self.authority_pin)
        require(a['schema'] == 'robotron-closed-metadata-and-raw-readiness-predicate-reuse-authority-v1', 'Exact reuse authority required')
        self.a = a
        for key, sha in {
            'metadata_closeout': '29ad1900ca8afdcc1dcb9cd871a2a45cbcc278825a2e4959ade938e8d4308e5a',
            'metadata_report': 'c12344e4491857584df5d337adaf9c90d9f53ba14d115e55c48f325b01238f60',
            'metadata_driver': '6d0539c4f0fe385e5347db7826a98ed4d380abdf91c4de326baabba14d9d4a3c',
            'metadata_preparer': '0596b784624feb7dd0c2406aae0d83227bf894feaaa58212a049bc974abc95e7',
            'metadata_contract': 'cdafb1a0c417a697e1232ca7be7d21bd0652dbf7cfc949cbd8bb12c913f079c3',
            'raw_review': '5808521bcf78a52a25d1abc271120bad12d9bdf4f13f2ccd6da27bed29e5f6fa',
            'raw_reviewer': 'b583bae60bc09b56666851b80851a582a4e14b4508d0221cf43769045c1b49f2',
        }.items():
            require(a[key]['sha256'] == sha, 'Selected original reuse source differs: ' + key)
            h.checked(a[key])
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
                and metadata_job['deadline_readiness'] == a['raw_review'], 'Original metadata source inputs differ')
        config = self.read(a['metadata_config'])
        require(config['argv'][3] == a['metadata_driver']['path'] and config['argv'][-1] == a['metadata_driver']['sha256'], 'Original metadata driver argv differs')
        for pin in metadata_job['inputs']:
            h.checked(pin)
        require(all(a[key] in metadata_job['inputs'] for key in ('metadata_preparer', 'metadata_contract')),
                'Actual metadata job did not hold the selected predicate sources')
        prepared = self.read(a['native_prepared'])
        require(prepared['engineering_only'] is False and prepared['source_preparer'] == a['metadata_preparer']
                and [row['leg'] for row in prepared['cases']] == a['ordered_legs'] == ['R1', 'C1', 'R2', 'C2']
                and [row['native_job'] for row in prepared['cases']] == a['native_jobs'], 'Original four-job preparation differs')
        self.subjects = [(row['leg'], self.read(row['native_job'])) for row in prepared['cases']]
        self.raw = self.read(a['raw_review'])
        require(self.raw['status'] == 'PASS' and self.raw['lifecycle'] == a['lifecycle']
                and self.raw['original_job'] == a['worker_job'] and self.raw['full_main_input_count'] == 247
                and self.raw['accepted_samples'] == a['raw_samples'] == 3101
                and self.raw['raw_API_and_TCP_and_retirement_snapshots_replayed'] is True
                and self.raw['legacy_500ms_evidence_and_projection_gaps_verified'] is True,
                'Actual full raw readiness predicates required')
        life = self.read(a['lifecycle'])
        require(life['worker_job'] == a['worker_job'] and life['outcome'] == a['outcome'], 'Original readiness lifecycle differs')
        outcome = self.read(a['outcome'])
        require(len(outcome['samples']) == 3101, 'Original raw corpus count differs')
        self.samples = outcome['samples']
        self.counts = dict(semantics_reused_from_closed_metadata=0, raw_full_integrity_passes=0)
        phase('closed_metadata_authority_validated', samples=len(self.samples))

    def read(self, pin):
        return json.loads(self.h.checked(pin).read_bytes())

    def validate_launch(self, job, context, h):
        require(h is self.h and any(job == subject for _, subject in self.subjects), 'Reuse only exact originally validated job')
        leg = next(leg for leg, subject in self.subjects if job == subject)
        family = context['family']
        require(family['native_launch_qualified'] is True, 'Engineering family is never scientific launch authority')
        require(family['main_domain_hot_review'] == self.a['raw_review'] and family['round_observer_reviewer'] == self.a['raw_reviewer'], 'Original readiness source binding differs')
        proof = self.read(family['main_domain_hot_review'])
        require(proof['lifecycle'] == self.a['lifecycle'], 'Original readiness proof lifecycle differs')
        h.checked(family['round_observer_reviewer'])
        verified = copy.deepcopy(self.raw)
        require(verified['original_sources'] == family['main_observer'], 'Main-domain proof uses a different observer source')
        lifecycle = self.read(proof['lifecycle'])
        worker = self.read(lifecycle['worker_job'])
        proved = self.read(worker['case'])
        current = context['main_binding']
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
