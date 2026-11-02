"""Complete only the stability checks after the original unused-expert warning.

The original auditor and evaluator are never invoked. The original exit2 and
valid=False remain unchanged. This writes one new supplemental review only.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import statistics
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
PREP = ROOT/'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018'
SUPPLEMENT = PREP/'R1-optional-expert-warning-supplemental-review-original01-20261019'
CAMPAIGN = ROOT/'logs/managed-learning-20261015/quality-CE845M-vs-confirmed-scoring-LR25-next8M-trial01-20261018'
WARNING = "[WARN] Robotron expert unavailable (No module named 'v3'); expert guidance disabled."
AUDITOR_SHA = 'a405fe2e7c4462a8ddac884d40b89f45d3d9ba47136286e497e85770593d35c0'
SOCKET_SHA = '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408'
WIRE_SHA = 'e204e717bd889f998d36f20d92b09513033bde550e3f958fdc9e7ae1032fe8aa'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def run():
    audit_dir = PREP/'audit-bindings/leg01-audit'
    original = read(audit_dir/'review-receipt.json')
    control = read(PREP/'audit-bindings/leg01-controller/root-original-result-and-owned-release.json')
    require(control['original_exit'] == 2 and control['unit_released']
            and control['lifecycle_complete'], 'Original failed audit must remain archived/released')
    expected_error = ('ValueError: Unclassified evaluator log issues require review: '
                      + repr([dict(line_number=2, text=WARNING)]))
    require(original['valid'] is False and original['result'] == 'rejected_or_needs_review'
            and original['error'] == expected_error, 'Only the exact original warning is in scope')
    auditor = ROOT/'tools/confirmed_game_boundary_proposal/audit_confirmed_completed_leg_reviewed2.py'
    require(digest(auditor) == AUDITOR_SHA, 'Original auditor source changed')
    # Its fixed source reaches this unique exception only after all original
    # terminal/ROM/admission/clock/runtime/actor-log predicates. The remaining
    # post-console predicates are evidence/source and finished-record stability.
    source = auditor.read_text()
    require(source.count('require(not unclassified, f"Unclassified evaluator log issues require review: {unclassified}")') == 1,
            'Original control-flow checkpoint changed')
    intent = read(SUPPLEMENT/'review-intent.json')
    require(intent['C1_completed_count_at_intent'] == 0, 'Record the pre-outcome review intent')
    require(read(SUPPLEMENT/'C1-status-at-supplemental-review-intent.json')['count'] == 0,
            'Captured candidate intent status differs')
    wire_dir = SUPPLEMENT/'actual-wire-differential-CPU-original01'
    wire = read(wire_dir/'work/result.json')
    wire_control = read(wire_dir/'execution/root-original-result-and-owned-release.json')
    wire_source = ROOT/'tools/confirmed_game_boundary_proposal/optional_expert_warning_proposal/prove_unused_expert_on_actual_wire.py'
    require(digest(wire_source) == WIRE_SHA and wire_control['original_exit'] == 0
            and wire_control['unit_released'] and wire_control['lifecycle_complete']
            and wire['status'] == 'PASS' and wire['child_exit'] == 0, 'Actual handler differential failed')
    require(len(wire['cases']) == 6 and all(case['expert_calls'] == 0 for case in wire['cases']),
            'All six missing/present-trap cases must show zero expert calls')
    require({(case['case'], case['expert_condition']) for case in wire['cases']} ==
            {(case, condition) for case in ('truncated_nonzero','zero_real_restart','zero_no_restart')
             for condition in ('missing','present_trap')}, 'Differential cases incomplete')
    require(wire['manifest']['package_hashes']['socket_server.py'] == SOCKET_SHA,
            'Actual handler differential used another source')
    state = read(CAMPAIGN/'status.json')
    captured_state = read(audit_dir/'campaign-status-observed.json')
    record = next(row for row in captured_state['legs'] if row['index'] == 1)
    require(record['state'] == 'finished' and record['returncode'] == 0
            and [row for row in state['legs'] if row['index'] == 1] == [record],
            'Original finished evaluator record changed')
    stable = []
    for path, entry in original['artifacts'].items():
        require(digest(audit_dir/entry['copy']) == entry['sha256'], 'Original captured audit bytes changed')
        if Path(path) != CAMPAIGN/'status.json':
            require(digest(path) == entry['sha256'], 'Original completed-leg evidence changed: '+path)
        stable.append(dict(path=path, copy=entry['copy'], sha256=entry['sha256']))
    plan = read(CAMPAIGN/'plan.json')
    game = Path(plan['legs'][0]['command'][4]).parents[1]
    for group in ('evaluator_source_hashes', 'execution_source_hashes'):
        for name, expected in plan[group].items():
            path = Path(name) if Path(name).is_absolute() else game/name
            require(digest(path) == expected, 'Frozen source changed after original audit')
    socket = game/'Scripts/dqn/socket_server.py'
    require(digest(socket) == SOCKET_SHA, 'Frozen socket source differs')
    tree = ast.parse(socket.read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'get_expert_action']
    require(len(calls) == 1, 'Unexpected extra expert-action caller')
    guarded = [node for node in ast.walk(tree) if isinstance(node, ast.If)
               and ast.unparse(node.test) == 'use_expert and get_expert_action is not None']
    require(len(guarded) == 1 and calls[0] in list(ast.walk(guarded[0])), 'Expert call guard changed')
    assignment = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'use_expert' for target in node.targets)]
    require(len(assignment) == 1 and ast.unparse(assignment[0].value) ==
            'random.random() < expert_ratio and (not metrics.override_expert) and (not eval_only)',
            'Frozen expert-selection predicate changed')
    receipt = read(CAMPAIGN/'01-reference/receipt.json')
    rows = receipt['rows']
    require(receipt['valid'] is True and receipt['count'] == receipt['started'] == len(rows) == 202
            and receipt['pending'] == receipt['abandoned'] == 0, 'Original complete cohort differs')
    require(all(row['eval_only'] is True and row['measurement_active'] is True
                and all(row[context]['expert_ratio'] == row[context]['epsilon'] == 0
                        for context in ('start_context','end_context')) for row in rows),
            'Warning allowance only applies to actual frozen greedy evaluation')
    require(receipt['job']['expert_ratio'] == receipt['job']['epsilon'] == 0
            and receipt['job']['actors'] == 16, 'Original frozen profile changed')
    ids = {row['journal_game_id'] for row in rows}
    for name in ('original_terminal_readback','rom_game_over_evidence'):
        proof = original[name]
        require(proof['status'] == 'PASS' and proof['verified_games'] == len(proof['links']) == 202
                and {row['journal_game_id'] for row in proof['links']} == ids,
                'Original successful prefix proof must cover all202 games')
    console = (audit_dir/'evaluator-console.log').read_text().splitlines()
    require(console[1] == WARNING and console.count(WARNING) == 1, 'Exact startup warning differs')
    scores = [row['score'] for row in rows]
    stats = dict(count=202, score_sum=sum(scores), mean=statistics.mean(scores), median=statistics.median(scores))
    require(stats['mean'] == receipt['mean'] and stats['median'] == receipt['median'], 'Original arithmetic changed')
    report = dict(schema='robotron-original-audit-optional-warning-supplement-v1',
        status='ORIGINAL_NEEDS_REVIEW_RESOLVED_EXACT_UNUSED_EXPERT_WARNING',
        observed_unix_s=time.time(), leg=1, role='reference', plan_sha256=state['plan_sha256'],
        original_audit_valid=False, original_audit_exit=2, original_evaluator_exit=0,
        supplemental_valid_completed_leg=True, classified_warning=dict(line_number=2,text=WARNING,
            reason='Frozen greedy controls exclude the only expert action branch; actual handler differential passed.'),
        original_auditor_source_sha256=AUDITOR_SHA, original_failed_review_sha256=digest(audit_dir/'review-receipt.json'),
        pre_outcome_review_intent_sha256=digest(SUPPLEMENT/'review-intent.json'),
        actual_handler_proof_sha256=digest(wire_dir/'work/result.json'),
        actual_handler_original_closure_sha256=digest(wire_dir/'execution/root-original-result-and-owned-release.json'),
        preserved_original_artifacts=stable, original_finished_record=record, statistics=stats,
        original_game_ids=sorted(ids), original_terminal_readback=original['original_terminal_readback'],
        rom_game_over_evidence=original['rom_game_over_evidence'],
        cohort_rerun=False, original_auditor_rerun=False, original_receipts_changed=False,
        scientific_gates_changed=False, quality_qualified=False, promotion=False,
        scope='Supplement only for exact unused optional warning and remaining post-console stability checks. '
              'Original audit failure remains. All four original fresh cohorts and remaining independent reviews are still required.')
    output = SUPPLEMENT/'supplemental-review-output'
    output.mkdir(mode=0o700)
    with (output/'review.json').open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush()
        os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'],count=202,quality_qualified=False,promotion=False)))
    return 0


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if args.execute:
        raise SystemExit(run())
    print('PLAN_ONLY: no reads, launches or writes')
