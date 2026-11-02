"""Assess four independently closed screening legs; never promote or launch."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'logs/managed-learning-20261015/run-26'
NUMERIC = BASE/'deadline-score60min-protocol-original01-preparation-20261026/deadline_score_report_v1.py'
NUMERIC_SHA = 'baf9719187762ce29d5e6ac8046c0b56c9e397a6a112fb58ed836c6e09856d66'
ORDER = ('R1', 'C1', 'R2', 'C2')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(pin, as_json=True):
    path = Path(pin['path'])
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(), 'Canonical evidence required')
    before = path.stat()
    require(before.st_uid == os.getuid() and before.st_mode & 0o222 == 0 and before.st_size <= 64 << 20,
            'Evidence must be sealed, owned and bounded')
    raw = path.read_bytes()
    stable = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_mode, st.st_uid, st.st_nlink)
    require(stable(path.stat()) == stable(before) and len(raw) == pin['bytes']
            and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'Evidence changed')
    return json.loads(raw) if as_json else raw


def decide(gates):
    return dict(screening_passed=gates['both_numeric_gates_passed'],
        policy_decision='REQUIRE_FRESH_COMPLETE_GAME_CONFIRMATION' if gates['both_numeric_gates_passed'] else 'RETAIN_PROTECTED_REFERENCE',
        full_game_quality_qualified=False, improvement_qualified=False, promotion=False,
        causal_learning_speed_gain_established=False, candidate_pool_rescue=False)


def assess(manifest, expected_sha, output, *, historical_replay=False):
    h = load('_screen_assessment_helpers', ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    manifest_pin = h.pin(manifest.resolve())
    require(manifest_pin['sha256'] == expected_sha, 'Exact selected manifest required')
    selected = read(manifest_pin)
    require([case['leg'] for case in selected['cases']] == list(ORDER), 'Exact ordered four-leg study required')
    require(selected['engineering_only'] is historical_replay, 'Engineering replay must never become production authority')
    study_pin = selected['study_precommit']
    study = read(study_pin)
    require(study['policies']['reference']['checkpoint']['sha256'] == 'b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883', 'Protected reference differs')
    require(study['ordered_legs'] == list(ORDER) and study['no_retry'] is True, 'Fixed original study required')
    require(hashlib.sha256(NUMERIC.read_bytes()).hexdigest() == NUMERIC_SHA, 'Original numeric gates changed')
    numeric = load('_unchanged_deadline32_numeric', NUMERIC)
    archive_pin = h.pin(ROOT/'tools/eval_capacity_proposal/review_original_pilot_score_carry_v1.py')
    archive = load('_screen_assessment_archive', Path(archive_pin['path']))
    seals, qualifications, scopes = {}, {}, {}
    seen_jobs = set()
    for case in selected['cases']:
        leg = case['leg']
        jp = case['native_job']
        job = read(jp)
        require(jp['sha256'] not in seen_jobs and job['leg'] == leg and job['study_precommit'] == study_pin
                and job['attempt'] == 1 and job['no_retry'] is True, 'Original job/study identity differs')
        seen_jobs.add(jp['sha256'])
        role = 'reference' if leg.startswith('R') else 'candidate'
        require(job['checkpoint'] == study['policies'][role]['checkpoint'], 'Preselected policy changed')
        parent = Path(jp['path']).parent
        qp = h.pin(parent/('root-'+leg+'-independent-qualified.json'))
        q = read(qp)
        require(q['schema'] == 'robotron-root-deadline32-leg-qualification-v1'
                and q['status'] == 'INDEPENDENT_DEADLINE32_QUALIFIED' and q['leg'] == leg
                and type(q['actual_review_tool_terminal_exit']) is int and q['actual_review_tool_terminal_exit'] == 0
                and q['all_six_descriptors_resources_argv_birth_units_cgroup_release_verified'] is True
                and q['full_game_quality_qualified'] is q['improvement_qualified'] is False,
                'Independent original leg qualification missing or invalid')
        report = read(q['independent_report'])
        require(report['status'] == 'PASS' and report['original_job'] == jp and report['leg'] == leg
                and report['source_family'] == job['source_family_manifest']
                and report['actual_native_exit'] == 0
                and report['deadline_metric_independently_qualified'] is True
                and report['positive_owned_native_observer_children_threads_and_lease_closure'] is True
                and report['complete_game_quality_qualified'] is report['improvement_qualified'] is False
                and len(report['all32_original_prefixes']) == 32, 'Independent report belongs to another or incomplete leg')
        producer = read(report['native_result'])
        require(producer['original_job'] == jp and producer['complete'] is True and producer['errors'] == [],
                'Original native outcome is invalid')
        native_owner_pin = h.pin(parent/'execution-original01/root-original-identity.json')
        native_closure_pin = h.pin(parent/'execution-original01/root-original-result-and-owned-release.json')
        native_owner, native_closure = read(native_owner_pin), read(native_closure_pin)
        review_owner, review_closure = read(q['review_owner']), read(q['review_closure'])
        archive.archived_closure(native_closure, native_owner, read, exit_zero=True)
        archive.archived_closure(review_closure, review_owner, read, exit_zero=True)
        require(native_owner['invocation_id'] != review_owner['invocation_id'], 'Independent review must use another scope')
        seal_pin = producer['deadline_score_seal']
        seal = read(seal_pin)
        require(seal['policy']['policy_sha256'] == job['checkpoint']['sha256'], 'Sealed scores use another policy')
        numeric.validate(seal)
        require(report['score_cutoff'] == q['score_cutoff'], 'Qualified score audit differs from independent report')
        for key in ('n_scored', 'n_completed', 'n_censored', 'score_sum', 'mean_score', 'median_score'):
            require(report['score_cutoff'][key] == seal[key], 'Independent score denominator/summary differs')
        seals[leg] = seal
        qualifications[leg] = qp
        scopes[leg] = dict(native_owner=native_owner_pin, native_closure=native_closure_pin,
                           review_owner=q['review_owner'], review_closure=q['review_closure'],
                           independent_report=q['independent_report'], score_seal=seal_pin)
    gates = numeric.compare_four(seals)
    require(gates['candidate_pool_rescue'] is gates['automatic_promotion'] is gates['full_game_quality_qualified'] is False,
            'Screening scope changed')
    result = dict(schema='robotron-round-screen-study-independent-assessment-v1', created_unix_s=time.time(),
        status='HISTORICAL_REPLAY_ONLY' if historical_replay else 'FOUR_ORIGINAL_SCREENING_LEGS_QUALIFIED',
        prepared_manifest=manifest_pin, study_precommit=study_pin, ordered_legs=list(ORDER),
        qualifications=qualifications, original_closed_scopes=scopes, numerical_gates=gates,
        unchanged_numeric_source=h.pin(NUMERIC), archive_source=archive_pin, source=h.pin(Path(__file__).resolve()),
        historical_replay_only=historical_replay, **decide(gates))
    return h.put(output.resolve(), result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assess', action='store_true')
    parser.add_argument('--historical-replay', action='store_true')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.assess:
        print(json.dumps(assess(args.manifest, args.manifest_sha256, args.output,
                                historical_replay=args.historical_replay)), flush=True)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
