"""Final read-only rollup after original tool20313 actually returns0."""
import argparse
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
F = B / 'short15-protectedb231-vs-distinct8dae-fast-pending-original03-20261101'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--finalize', action='store_true')
    parser.add_argument('--actual-tool-session', type=int)
    parser.add_argument('--actual-tool-exit', type=int)
    args = parser.parse_args()
    if not args.finalize:
        print('PLAN_ONLY: no input reads or result writes')
        return 0
    assert args.actual_tool_session == 20313 and args.actual_tool_exit == 0
    h = load('_finalShort8H', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    reader = load('_finalShort8Reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    def read(pin, as_json=True):
        return reader.read_pin(pin, as_json=as_json)
    prepared_pin = h.pin(F / 'prepared-with-review.json')
    prepared = read(prepared_pin)
    seq = load('_finalShort8Seq', h.checked(prepared['independent_review']['sequence']))
    archive = load('_finalShort8Archive', h.checked(prepared['independent_review']['archive']))
    native_controller = load('_finalShort8NativeCtl', h.checked(prepared['selected_sources']['controller']))
    cpu_controller = load('_finalShort8CpuCtl', h.checked(prepared['independent_review']['CPU_controller']))
    exit_pin = h.pin(F / 'original-sequence-actual-exit.json')
    outer_exit = read(exit_pin)
    assert outer_exit['actual_exit'] == 0 and outer_exit['original_Popen_reaped'] is True
    assert outer_exit['original_attempt'] == 1 and outer_exit['no_retry'] is True
    assert seq.birth(outer_exit['original_pid']) != outer_exit['original_birth']
    outer_result_pin = h.pin(F / 'Root-controller-runtime-original01/result.json')
    outer_result = read(outer_result_pin)
    assert outer_result['actual_exit'] == 0 and outer_result['error'] is None
    assert outer_result['legs'] == ['R1', 'C1'] and outer_result['reporter_thread_closed'] is True
    assert outer_result['native_or_original_controller_retried'] is False
    arms = {}
    for leg in ['R1', 'C1']:
        report_pin = h.pin(F / (leg + '-independent-review-original01') / 'report.json')
        report = read(report_pin)
        assert report['status'] == 'PASS_ORIGINAL_SELECTED_PREFIX_SCORE_AND_BOUNDED_MAIN_REPLAY'
        assert report['prepared'] == prepared_pin and report['original_actual_exit'] == 0
        job_pin = prepared['jobs'][leg]['job']
        job = read(job_pin)
        native = read(report['original_native_result'])
        assert native['original_job'] == job_pin and native['complete'] is True and native['errors'] == []
        assert native['status'] == 'ORIGINAL_DEADLINE32_SEALED_AND_CLOSED'
        assert all(native[key] is True for key in ['all_original_threads_stopped', 'original_lease_released', 'immutable_inputs_unchanged'])
        owner_pin = h.pin(F / leg / 'controller-execution-original01/root-original-identity.json')
        owner = read(owner_pin)
        closure = read(report['original_archived_closure'])
        fields = archive.archived_closure(closure, owner, read, exit_zero=True)
        assert fields['ExecMainStatus'] == '0'
        assert seq.birth(owner['pid']) != owner['starttime_ticks']
        for unit in [owner['unit'], owner['timer']]:
            assert native_controller.show(unit)['LoadState'] == 'not-found'
            assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', unit).exists()
        review_scope = seq.verify_closed_scope(
            F / (leg + '-independent-review-original01'), '',
            prepared['independent_review']['configs'][leg], h, read,
            archive, cpu_controller, exit_zero=True)
        reap = native['original_post_origin_child_reap']
        assert reap['all_original_children_reaped'] is True
        assert reap['signals_sent'] is False and reap['exit_statuses_normalized'] is False
        assert len(reap['original_children']) == 32 and reap['unknown_slots'] == []
        for child in reap['original_children'].values():
            assert child['actual_exit'] == 0
            assert seq.birth(child['pid']) != child['birth']
        seal = read(report['score_seal'])
        assert seal['n_scored'] == len(seal['rows']) == 32
        assert seal['n_completed'] + seal['n_censored'] == 32
        assert seal['horizon_ns'] == 900_000_000_000 and seal['fixed_denominator_valid'] is True
        scores = [row['score_at_deadline'] for row in seal['rows']]
        assert all(type(score) is int and score >= 0 for score in scores)
        assert sum(scores) == seal['score_sum'] == report['score']['score_sum']
        assert sum(scores) / 32 == seal['mean_score'] == report['score']['mean_score']
        assert statistics.median(scores) == seal['median_score'] == report['score']['median_score']
        main_replay = report['main']
        assert main_replay['all_original_strict_predicates_retained'] is True
        assert main_replay['actual_pending_cadence_audited'] is True
        assert main_replay['pending'] == len(main_replay['actual_pending_next_observation_gaps'])
        assert main_replay['live_pending_coverage'] is bool(main_replay['pending'])
        assert native['compile_report']['all_shapes_verified'] == list(range(1, 17))
        assert native['policy_before'] == native['policy_after']
        assert native['policy_before']['checkpoint_sha256'] == job['checkpoint']['sha256']
        for pin in job['inputs']:
            h.checked(pin)
        arms[leg] = dict(
            independent_review=report_pin,
            native_result=report['original_native_result'],
            score_seal=report['score_seal'],
            score=report['score'],
            Main_replay=main_replay,
            intermediate=report['intermediate_checkpoint_reviews'],
            native_original_owner=owner_pin,
            original_native_closure=report['original_archived_closure'],
            review_scope=review_scope,
            all32_original_children_normal0_and_births_absent=True,
            accepted_frames=seal['accepted_frame_exposure'])
    comparisons = []
    for minutes, horizon in [(5, 300_000_000_000), (10, 600_000_000_000), (15, 900_000_000_000)]:
        def score(leg):
            if minutes == 15:
                return arms[leg]['score']['mean_score']
            return arms[leg]['intermediate'][str(horizon)]['mean_score']
        reference, candidate = score('R1'), score('C1')
        comparisons.append(dict(minutes=minutes, reference_mean=reference, candidate_mean=candidate,
                                candidate_change_fraction=candidate / reference - 1))
    output = F / 'completed-original-short15-independent-result-and-owned-closeout.json'
    pin = h.put(output, dict(
        schema='robotron-original-fixed15min-screen-final-rollup-v1',
        status='VALID_ORIGINAL_SHORT15_SCORE_SCREEN_NO_FULLGAME_RANKING',
        observed_unix_s=time.time(), actual_original_tool_session=20313,
        actual_original_tool_exit=0, original_sequence_exit=exit_pin,
        original_outer_result=outer_result_pin, prepared=prepared_pin,
        arms=arms, comparisons=comparisons,
        candidate_accepted_frame_change_fraction=arms['C1']['accepted_frames'] / arms['R1']['accepted_frames'] - 1,
        all_original_resources_closed=True,
        any_actual_pending_branch_live_coverage=any(a['Main_replay']['live_pending_coverage'] for a in arms.values()),
        qualification_scope='32 first games per arm at a fixed900s wall-time cutoff; score witnesses and original resource closures independently validated. Full-game ranking is unqualified. The5/10-minute checkpoints reuse the same games and are descriptive only. Serial shared-host exposure can confound wall-time scores; no posthoc frame normalization chooses a winner.',
        formal_statistical_confidence_qualified=False,
        full_game_quality_qualified=False,
        scientific_run_retried_or_rescued=False,
        promotion=False))
    print(json.dumps(dict(result={key: pin[key] for key in ['path', 'sha256', 'bytes']}, comparisons=comparisons)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
