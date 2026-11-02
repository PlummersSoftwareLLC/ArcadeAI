"""Pure source binding for the prospective quota64 study; no file or runtime writes."""
import ast
import hashlib
from pathlib import Path
import re

REF_SHA='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
REF_CLOCKS={'learner_frame_count': 3045860554, 'training_steps': 11995683, 'optimized_samples': 47558522880, 'frame_count': 5926701223}
FAILED_PAIR='3d3169064b25e933218e4d2dce2a3cd62ef5f3f5324354f362a9137671759650'
FAILED_POLICY='697ad174cb7f0c4ffe4221fbfe571f058c679809cce84ccc27ae0966a791d6fc'
FAILED_CLOCKS={'learner_frame_count': 3041579470, 'training_steps': 11979944, 'optimized_samples': 47494055936, 'frame_count': 5918642727}
CAPACITY_PROOF_SHA = '5fa6952ba9379aba48c15314b3b2ded6f8858bcdd19891bfcab4155630022d9a'
ROOT = Path(__file__).resolve().parent
FILENAMES={'runtime': 'run_quality32_quota64_selected_original01_v2.py', 'native_controller': 'control_quality32_quota64_selected_v2.py', 'leg_reviewer': 'read_quality32_quota64_selected_original01_v2.py', 'campaign_assessor': 'assess_quality32_quota64_selected_original01_v2.py', 'leg_preparer': 'prepare_quality32_quota64_selected_labels_v3.py', 'sequence': 'sequence_quality32_quota64_selected_original01_v2.py', 'display_source': 'display_quality32_quota64_bounded_selected_v3.py'}


def require(value, message):
    if not value: raise ValueError(message)


def bind(source, name, value):
    nodes = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
             and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
             and node.targets[0].id == name]
    require(len(nodes) == 1, 'Exactly one binding required: ' + name)
    node = nodes[0]; lines = source.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = [name + '=' + repr(value) + '\n']
    return ''.join(lines)


def render(templates, pair, pair_sha):
    require(set(templates) == set(FILENAMES), 'Exact seven source templates required')
    require(type(pair_sha) is str and re.fullmatch('[0-9a-f]{64}', pair_sha)
            and pair_sha not in ('0' * 64, FAILED_PAIR, '75baa58f45fc053041a90e2e5d5a66505c76137122ef647198e164e01bf5af5d'), 'Distinct new pair required')
    reference, candidate = pair['reference'], pair['candidate']
    require(reference['policy']['sha256'] == REF_SHA and reference['saved_clocks'] == REF_CLOCKS,
            'Protected3045 reference required')
    candidate_sha = candidate['policy']['sha256']
    require(type(candidate_sha) is str and re.fullmatch('[0-9a-f]{64}', candidate_sha)
            and candidate_sha not in ('0' * 64, REF_SHA, FAILED_POLICY, 'b66e751cc32004822272ccb0691f9e524ee94852c8e461299fac57c2985cdfc3'), 'Distinct later candidate required')
    clocks = candidate['saved_clocks']
    require(set(clocks) == set(REF_CLOCKS) and all(type(clocks[key]) is int and clocks[key] > floor
            for key, floor in REF_CLOCKS.items()), 'All four saved clocks must be strictly later')
    require(pair['expected_selected_games'] == 64 and pair['games_per_slot'] == 2
            and pair['minimum_complete_games_per_leg'] == 50
            and pair['whole_cohort_timeout_from_enter_s'] == 21600
            and pair['outer_start_horizon_s'] == 21540
            and pair['fixed_order'] == ['R1', 'C1', 'R2', 'C2']
            and pair['candidate_pooling_for_qualification'] is False
            and pair['promotion_requires_both_independent_candidate_gates'] is True
            and pair['candidate_gates'] == {role: dict(minimum_mean_ratio=1.05, minimum_median_ratio=1.0)
                                           for role in ('C1', 'C2')}, 'Unchanged fixed scientific gates required')
    policies = {role: dict(sha256=pair[role]['policy']['sha256'], clocks=pair[role]['saved_clocks'])
                for role in ('reference', 'candidate')}
    result = {}
    for key in FILENAMES:
        source = templates[key]
        if key in ('runtime', 'leg_reviewer', 'campaign_assessor', 'leg_preparer', 'sequence'):
            source = bind(source, 'PAIR_SHA', pair_sha)
        if key in ('runtime', 'leg_reviewer'): source = bind(source, 'POLICIES', policies)
        if key == 'runtime': source = bind(source, 'CAPACITY_PROOF_SHA', CAPACITY_PROOF_SHA)
        if key == 'leg_reviewer': source = bind(source, 'RUNTIME_SHA', result['runtime']['sha256'])
        ast.parse(source)
        result[key] = dict(path=str(ROOT / FILENAMES[key]), source=source,
                           sha256=hashlib.sha256(source.encode()).hexdigest())
    return result
