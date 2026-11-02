"""Unselected acquisition evidence component for the future32-slot root auditor.

Retains the established phase-snapshot checks, with the old single window SHA
replaced by a separately authenticated future window and strict prospective
policy. Root campaign ownership, main holds and original cohort audit lifecycle
are separate mandatory checks. No model loading, launches, writes or promotion.
"""
import importlib.util
import time
from pathlib import Path
import math
import re
import shlex
from types import SimpleNamespace

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
VERIFIER = GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'
VERIFIER_SHA256 = '14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'
REFERENCE_SHA = 'c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'
PACKAGE_SHA = '9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
SLOTS = list(range(4096,4128))


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_snapshot(binding, bundle):
    CFG, BUNDLE = binding, bundle
    proof = bundle['phase_cpu_report']
    args = SimpleNamespace(cpu_job_sha256=binding['evidence']['phase_cpu_job']['sha256'],
        candidate_sha256=binding['candidate']['sha256'], candidate_bytes=binding['candidate']['bytes'])
    job=BUNDLE['phase_cpu_job']; candidate=CFG['candidate']
    require(proof == BUNDLE['phase_cpu_report'] and proof['schema'] ==
            'robotron-phase-snapshot-checkpoint-CPU-result-v1' and proof['status'] == 'PASS'
            and proof['root_job'] == job and proof['job_file']['sha256'] == args.cpu_job_sha256
            and proof['script']['sha256'] == VERIFIER_SHA256, 'Exact candidate CPU PASS/job required')
    require(proof['sha256'] == candidate['sha256'] == args.candidate_sha256
            and proof['bytes'] == candidate['bytes'] == args.candidate_bytes
            and job['source'] == BUNDLE['current_original_provenance']['normal_producer']
            and job['phase_snapshot']['purpose'] == 'candidate'
            and job['phase_snapshot']['observed_clients'] == 192, 'Candidate CPU acquisition scope differs')
    for label, entry in [('source_checkpoint',job['source']),
                         ('root_readonly_verification_copy',job['verification_copy'])]:
        observed=proof['bound_files'][label]
        require(all(observed[key] == entry[key] for key in ('path','sha256','bytes'))
                and all(observed[key] == value for key,value in entry['identity'].items()),
                'CPU source/copy binding differs')
    source=proof['source_before']; copied=proof['verification_copy']
    require(candidate == BUNDLE['current_original_provenance']['evaluation_candidate']
            and source['mode'] == '0o664' and source['nlink'] == 1
            and candidate['identity']['mode'] == '0o444' and candidate['identity']['nlink'] == 1
            and len({(entry['identity']['device'],entry['identity']['inode']) for entry in
                (job['source'],job['verification_copy'],candidate)}) == 3,
            'Normal producer, separate CPU copy and evaluation archive identities required')
    require(source == proof['bound_files']['source_checkpoint']
            and copied == proof['bound_files']['root_readonly_verification_copy']
            and source['sha256'] == copied['sha256'] == candidate['sha256']
            and source['bytes'] == copied['bytes'] == candidate['bytes']
            and (source['device'],source['inode']) != (copied['device'],copied['inode'])
            and copied['mode'] == '0o444' and copied['nlink'] == 1, 'Independent readonly CPU copy required')
    require(proof['phase_metadata_verified'] is True
            and proof['actual_restore_or_optimizer_step'] is False
            and proof['actual_quality_qualification'] is False, 'CPU verification scope differs')
    expected=job['phase_snapshot']['expected_phase']; actual=proof['saved_priority_metric_phase']
    for key in ('metric','phase_id','root_precommit_sha256','started_from','valid','last_resume_record_sha256'):
        require(actual[key] == expected[key], 'CPU phase differs: '+key)
    require(actual['phase_record_sha256'] == expected['founder_phase_record_sha256'], 'CPU founder differs')
    floor=job['clock_floor']
    require(set(floor) == {'training_steps','optimized_samples','learner_frame_count','frame_count'}
            and all(type(floor[k]) is int and proof['clocks'][k] >= floor[k] for k in floor),
            'Actual four-clock acquisition floor differs')
    window=BUNDLE['window_job']; result=BUNDLE['window_result']; latch=BUNDLE['window_latch']
    require(result['status'] == 'CAPTURED_FIRST_BOTH_HORIZONS' and result['checkpoint'] == candidate
            and result['tag'] == window['tag'] and result['owner'] == window['owner']
            and result['progress']['both_horizons'] is True
            and result['progress']['learner_frames'] >= 8_000_000
            and result['progress']['learner_accepted'] >= 8_000_000
            and latch['progress'] == result['progress'] and latch['status'] == 'LATCH'
            and job['experiment'] == window['experiment'], 'Original prospective capture differs')


def validate_window_policy(binding, bundle):
    window = bundle['window_job']
    require(binding['reference']['sha256'] == REFERENCE_SHA
            and binding['candidate']['sha256'] != REFERENCE_SHA,
            'Protected1597 reference and a distinct future candidate required')
    expected = binding['expected_window']
    require(set(expected) == {'owner', 'experiment', 'tag'}
            and all(window[key] == value for key, value in expected.items()),
            'Original prospective owner, experiment and capture tag differ')
    require(window['schema'] == 'robotron-derived-current-window-evidence-view-v1'
            and window['authorized'] is True and len(window['actors']) == 192,
            'Authorized original192-actor window required')
    require(window['policy'] == dict(learner_frames=8_000_000, accepted_dqn_epsilon=8_000_000,
        poll_s=1, maximum_observation_gap_s=30, maximum_API_age_s=5,
        no_applied_optimizer_s=60, one_capture_only=True), 'First-both-horizons capture policy differs')
    quality = window['quality_precommit']
    require(quality == dict(reference=binding['reference']['path'], reference_sha256=REFERENCE_SHA,
        order=['reference','candidate','reference','candidate'], same_fixed_admission_s=5400,
        same_whole_cohort_timeout_s=9000, minimum_games=50, all_slots=SLOTS, full_tails=True,
        max_attempts=1, extensions=False, individual_mean_ratio=1.05, individual_median_ratio=1.0,
        reference_pool='Both fresh reference cohorts only', no_historical_rows=True,
        automatic_promotion=False, source_package=binding['evidence']['source_package'],
        completion_policy='confirmed_reset_reserves_v1', mandatory_original_terminal_journal_readback=True)
        and quality['source_package']['sha256'] == PACKAGE_SHA,
        'New fixed reference,32-slot package and independent full-game gates required')
    proof = bundle['phase_cpu_report']
    require(proof['cuda_initialized'] is False and proof['visible_cuda_devices'] == 0
            and proof['finite']['tensors'] == 443 and proof['adam_state_count'] == 81
            and set(proof['models']) == {'online_state_dict','target_state_dict'}
            and all(value['strict_cpu_load'] is True and value['tensor_count'] == 100
                and value['parameter_count'] == 17_837_490 for value in proof['models'].values()),
            'Original strict CPU finite-model/Adam scope differs')
    progress = bundle['window_result']['progress']
    require(all(type(progress[key]) is int and progress[key] >= 0 for key in (
        'learner_frames','learner_accepted','applied_updates','amp_skips','logical_samples'))
        and progress['applied_updates'] > 0, 'Nonnegative classified progress and actual applied updates required')
    latch = bundle['window_latch']
    require(latch['job_experiment'] == expected['experiment']
            and type(latch['observed_monotonic_s']) in (int,float)
            and math.isfinite(latch['observed_monotonic_s'])
            and latch['observed_monotonic_s'] >= window['baseline_monotonic_s'],
            'First durable horizon latch identity or clock differs')


def validate_CPU_authority(binding, bundle, read, archived_closure):
    """Bind the successful original verifier invocation, job, report and completion."""
    evidence = binding['evidence']
    closure = bundle['phase_cpu_closure']
    fields = archived_closure(closure, closure['original'], read, exit_zero=True)
    completion, config = bundle['phase_cpu_completion'], bundle['phase_cpu_config']
    require(completion['status'] == 'PASS' and completion['CPU_report'] == evidence['phase_cpu_report']
            and completion['cpu_job'] == evidence['phase_cpu_job']
            and completion['original_controller_release'] == evidence['phase_cpu_closure']
            and completion['actual_candidate'] == binding['candidate']
            and completion['quality_qualified'] is False and completion['promotion'] is False,
            'Original CPU completion/report/job/owner join differs')
    expected_argv = [str(GAME.parent/'.venv-gb300/bin/python'), '-Xgil=0', '-I', '-B', str(VERIFIER),
        '--execute', '--job', evidence['phase_cpu_job']['path'], '--expected-job-sha256',
        evidence['phase_cpu_job']['sha256'], '--expected-verifier-sha256', VERIFIER_SHA256]
    require(config['unit'] == closure['original']['unit'] and config['argv'] == expected_argv,
            'Exact original phase-verifier command and named service required')
    expected_wrapper = ['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')] + expected_argv
    match = re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',
                         fields['ExecStart'])
    require(match is not None and shlex.split(match[1]) == expected_wrapper,
            'Archived successful service did not execute the bound CPU verifier/job')
    proof = bundle['phase_cpu_report']
    require(proof['job_file']['path'] == evidence['phase_cpu_job']['path']
            and proof['job_file']['sha256'] == evidence['phase_cpu_job']['sha256']
            and proof['script']['path'] == str(VERIFIER)
            and proof['script']['sha256'] == VERIFIER_SHA256,
            'CPU report actual script or job differs')


def review_acquisition(binding, read, archived_closure):
    """Called only after the root binding itself has been authenticated."""
    bundle = load_bundle(binding, read, archived_closure)
    validate_snapshot(binding, bundle)
    validate_window_policy(binding, bundle)
    validate_CPU_authority(binding, bundle, read, archived_closure)
    read(binding['candidate'], False)
    read(bundle['phase_cpu_job']['verification_copy'], False)
    read(binding['reference'], False)
    return dict(status='PASS_ACQUISITION_ONLY', candidate=binding['candidate'],
        reference=binding['reference'], clocks=bundle['phase_cpu_report']['clocks'],
        quality_qualified=False, promotion=False,
        root_campaign_main_holds_and_original_cohort_audit_lifecycle_still_required=True)


CURRENT_ROOT_SHA = 'd726c72316368009f98051a579eefa33efa60120b2c66067740e8d3da3edf0f3'
CURRENT_CPU_JOB_SHA = '4312b90dc93e0ebd3ef54fb3840727e5627bd6ac0503081bc690c89081255a13'
PROVENANCE_SHA = '5be88f4317f9d3a0db383a0c7c83e7f82c1816ec3a8e4172233c6b0a7a3dbc3c'
LINUX_SHA = '3c0a54a589e6790865b1dcecc1a0bf6e1f662b204155c7bf767a1d8b579f7de2'


def load_bundle(binding, read, archived_closure):
    """Authenticate actual originals before making explicitly internal layout views."""
    evidence = binding['evidence']
    require(evidence['current_capture_root']['sha256'] == CURRENT_ROOT_SHA
            and evidence['phase_cpu_job']['sha256'] == CURRENT_CPU_JOB_SHA,
            'Actual current capture preparation and original CPU job required')
    root = read(evidence['current_capture_root'])
    require(root['provenance_source']['sha256'] == PROVENANCE_SHA
            and root['linux_source']['sha256'] == LINUX_SHA,
            'Exact actual tested original-capture provenance sources required')
    def module(entry, name):
        read(entry, False)
        spec = importlib.util.spec_from_file_location(name+str(time.time_ns()), entry['path'])
        result = importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
        read(entry, False)
        return result
    provenance = module(root['provenance_source'], '_acquisition_current_provenance_')
    linux = module(root['linux_source'], '_acquisition_current_linux_')
    reviewed = provenance.review(root, read, linux.full_pin, archived_closure,
                                linux.process_start, linux.show)
    require(reviewed['views_are_original_producer_bytes'] is False
            and reviewed['quality_qualified'] is False
            and binding['candidate'] == reviewed['evaluation_candidate']
            and evidence['window_job'] == root['window_job'] == reviewed['original_window_job']
            and evidence['window_result'] == reviewed['original_window_result']
            and evidence['window_latch'] == reviewed['original_window_latch']
            and evidence['source_package'] == read(root['window_plan'])['source_package'],
            'Evaluation candidate and original window evidence linkage differs')
    required = ('phase_cpu_job','phase_cpu_report','window_job','window_result','window_latch',
                'phase_cpu_closure','phase_cpu_config','source_package')
    bundle = {key: read(evidence[key]) for key in required}
    require(bundle['phase_cpu_job']['source'] == reviewed['normal_producer']
            and bundle['phase_cpu_job']['clock_floor'] == reviewed['clock_floor'],
            'Actual normal CPU source or original trigger clocks differ')
    # These are local layout views; all evidence entries above still point to
    # their actual original bytes. No derived view is saved as an original job.
    bundle.update(window_job=reviewed['window_view'], window_result=reviewed['result_view'],
                  window_latch=reviewed['latch_view'], current_original_provenance=reviewed)
    if 'phase_cpu_completion' in evidence:
        bundle['phase_cpu_completion'] = read(evidence['phase_cpu_completion'])
    return bundle


if __name__ == '__main__':
    print('PLAN_ONLY: unselected acquisition component; no reads, queries, outputs, launches or promotion')
