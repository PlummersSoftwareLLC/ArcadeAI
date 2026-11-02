"""Pure source binding for the prospective quota64 study; no file or runtime writes."""
import ast
import hashlib
from pathlib import Path
import re

REF_SHA = 'e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
REF_CLOCKS = dict(learner_frame_count=1741229950, training_steps=7128160,
                  optimized_samples=27621148672, frame_count=3434514217)
FAILED_PAIR = '75baa58f45fc053041a90e2e5d5a66505c76137122ef647198e164e01bf5af5d'
FAILED_POLICY = 'b66e751cc32004822272ccb0691f9e524ee94852c8e461299fac57c2985cdfc3'
FAILED_CLOCKS = dict(learner_frame_count=2958813005, training_steps=11674710,
                     optimized_samples=46243817472, frame_count=5762362942)
CAPACITY_PROOF_SHA = '5fa6952ba9379aba48c15314b3b2ded6f8858bcdd19891bfcab4155630022d9a'
ROOT = Path(__file__).resolve().parent
FILENAMES = dict(runtime='run_quality32_quota64_selected_original01_v1.py',
                 native_controller='control_quality32_quota64_selected_v1.py',
                 leg_reviewer='read_quality32_quota64_selected_original01_v1.py',
                 campaign_assessor='assess_quality32_quota64_selected_original01_v1.py',
                 leg_preparer='prepare_quality32_quota64_selected_original01_v1.py',
                 sequence='sequence_quality32_quota64_selected_original01_v1.py',
                 display_source='display_quality32_quota64_selected_v1.py')


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
            and pair_sha not in ('0' * 64, FAILED_PAIR), 'Distinct new pair required')
    reference, candidate = pair['reference'], pair['candidate']
    require(reference['policy']['sha256'] == REF_SHA and reference['saved_clocks'] == REF_CLOCKS,
            'Original protected1741 reference required')
    candidate_sha = candidate['policy']['sha256']
    require(type(candidate_sha) is str and re.fullmatch('[0-9a-f]{64}', candidate_sha)
            and candidate_sha not in ('0' * 64, REF_SHA, FAILED_POLICY), 'Distinct later candidate required')
    clocks = candidate['saved_clocks']
    require(set(clocks) == set(FAILED_CLOCKS) and all(type(clocks[key]) is int and clocks[key] > floor
            for key, floor in FAILED_CLOCKS.items()), 'All four saved clocks must be strictly later')
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
