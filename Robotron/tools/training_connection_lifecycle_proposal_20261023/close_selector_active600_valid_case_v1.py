"""Independently close the actual original CPU review; never evaluate B gates early."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
E = R / 'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025/selector-active600-counterbalanced-engineering-original01'


def load(path, name, sha=None):
    if sha is not None:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--case', choices=['02-B1-proposal', '03-B2-proposal', '04-A2-baseline'])
    parser.add_argument('--observed-review-session', type=int)
    parser.add_argument('--observed-review-exit', type=int)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY'); return 0
    assert args.observed_review_session > 0 and args.observed_review_exit == 0
    h = load(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', '_case_h',
             '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader = load(G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py', '_case_reader',
                  'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    arc = load(G / 'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py', '_case_arc',
               '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
    closer = load(G / 'tools/training_connection_lifecycle_proposal_20261023/independent_component_closeout_v3.py', '_case_closer')
    def read(pin, as_json=True):
        return reader.read_pin(pin, as_json=as_json)
    directory = E / args.case
    cpu = directory / 'independent-original-active600-CPU-original01'
    closure = closer.closeout(cpu, h, arc, read, 0)
    reportpin = h.pin(cpu / 'output-original01/report.json'); report = read(reportpin)
    result = read(report['native_result']); job = read(report['native_job'])
    assert job['engineering_case'] == args.case
    measurements = report['timing_analysis']
    assert report['native_expected_exit1_verified'] is report['all_native_archives_resources_commands_pins_release_verified'] is report['private_resources_free'] is True
    assert report['native600_load_requirement_achieved'] is report['all_original_fixed_query_kernel_epochs_and_raw_headers_independently_replayed'] is True
    assert len(report['all32_original_startup_prefixes']) == 32
    assert all(row['all1200_original_pairs_and_loaded_ROM_verified'] is True for row in report['all32_original_startup_prefixes'])
    assert measurements['active_duration_ns'] >= 600000000000 and measurements['fixed_stratum']['count'] >= 100
    assert measurements['exact_rates_and_stratum_recomputed_without_runtime_measurement_helper'] is True
    assert report['raw_replay']['samples'] == len(report['kernel_epochs'])
    assert report['raw_replay']['deep_samples'] >= 100 and report['raw_replay']['maximum_observation_gap_s'] <= .5
    assert report['quality_qualified'] is report['scientific_case'] is False
    terminalpin = h.pin(directory / 'independent-original-native-and-observer-owned-terminal-closeout.json')
    terminal = read(terminalpin)
    assert terminal['native_job'] == report['native_job'] and terminal['native_result'] == report['native_result']
    assert terminal['all6_native_descriptors_argv_resources_pins_owner_absence_and_unit_release_verified'] is True
    ordered = ['01-A1-baseline', '02-B1-proposal', '03-B2-proposal', '04-A2-baseline']
    index = ordered.index(args.case)
    prior = []
    for name in ordered[:index]:
        pin = h.pin(E / name / 'independent-original-active600-all-scopes-raw-and-measurement-closeout.json')
        value = read(pin)
        assert value['case'] == name and value['private_resources_free'] is True
        assert value['all_three_original_scope_descriptors_resources_argv_pins_birth_absence_and_release_verified'] is True
        prior.append(pin)
    role = args.case.split('-')[1]
    proof = dict(schema='robotron-selector-active600-original-case-independent-closeout-v1',
        status='VALID_ORIGINAL_' + role + '_ACTIVE600_ENGINEERING_CASE_NO_QUALITY',
        case=args.case, implementation=job['engineering_implementation'], created_unix_s=time.time(),
        native_job=report['native_job'], native_result=report['native_result'],
        actual_native_original_tool_session_id=terminal['actual_original_tool_session_id'],
        actual_native_exit=1, actual_observer_exit=0,
        actual_reviewer_original_tool_session_id=args.observed_review_session, actual_reviewer_exit=0,
        native_and_observer_terminal_closeout=terminalpin, independent_report=reportpin,
        independent_reviewer_scope=closure,
        all_three_original_scope_descriptors_resources_argv_pins_birth_absence_and_release_verified=True,
        all32_original_MAME_reaped_exit0=True, all32_original_ROM_and1200_prefix_pairs_verified=True,
        raw_samples=report['raw_replay']['samples'], deep_samples=report['raw_replay']['deep_samples'],
        maximum_observation_gap_s=report['raw_replay']['maximum_observation_gap_s'],
        active_duration_ns=measurements['active_duration_ns'], active_accepted_frames=measurements['accepted_frames'],
        active_aggregate_accepted_frame_FPS=measurements['aggregate_accepted_frame_FPS'],
        fixed_stratum_call_count=measurements['fixed_stratum']['count'],
        fixed_stratum_median_CPU_ns_twice=measurements['fixed_stratum']['median_thread_CPU_ns_twice'],
        raw_selector_calls=measurements['original_call_count'],
        all_active_statuses_advance_every_slot=measurements['all_active_statuses_advance_every_slot'],
        private_resources_free=True, completed_valid_original_count=index + 1,
        prior_original_valid_closeouts=prior, A_reference_pool_not_fixed_until_A2=True,
        B_gates_not_evaluated=True, engineering_only=True, scientific_case=False,
        quality_qualified=False, full_game_score_verified=False, learning_speed_gain_verified=False,
        useful_training_throughput_gain_verified=False,
        next_action='Continue fixed original order after fresh preflight; after all4 valid, fix A1+A2 reference and separately assess B1/B2 with the precommitted integer gates.')
    pin = h.put(directory / 'independent-original-active600-all-scopes-raw-and-measurement-closeout.json', proof)
    print(json.dumps(dict(closeout=pin, completed_valid_originals=index + 1, raw_samples=proof['raw_samples'],
                          active_s=measurements['active_duration_s'], fixed_stratum_calls=proof['fixed_stratum_call_count'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
