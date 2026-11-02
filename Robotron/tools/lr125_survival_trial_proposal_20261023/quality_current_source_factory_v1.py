"""Render a separate LR125 quality family after its actual endpoint is known.

Definitions only: this module never writes files, imports an evaluator, creates
jobs or launches anything. Rendering is not CPU verification or launch readiness.
The caller must independently prove the actual endpoint and its numerical CPU
receipt before publishing sources bound to that policy.
"""
import ast
import hashlib
from pathlib import Path
import re

G = Path(__file__).resolve().parents[2]
B = G / 'tools/startup_policy_journal_proposal'
OLD_PAIR = 'ad0ff9558602611227651bdf472ca4d2685d7038711c934dbe123142f6639d6e'
OLD_WINDOW = 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3'
NEW_WINDOW = 'ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a'
REFERENCE = dict(sha256='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83',
    clocks=dict(learner_frame_count=1741229950, training_steps=7128160,
                optimized_samples=27621148672, frame_count=3434514217))
BASELINE = {'training_steps': 10205908, 'optimized_samples': 40227608576, 'learner_frame_count': 2561071773, 'frame_count': 5010336626}
OLD = {
    'runtime': ('run_compiled_full_tail32_quality2259_v1.py',
                'c105c5adb795f5c76650828fccfe9715e278aee528f770b4a56284218b055b4d'),
    'controller': ('control_compiled_full_tail32_quality2259_v1.py',
                   '4542fc0c346d03f68a61a6c55cc7f08e5f1830b2b53aead24f73718a989ff871'),
    'reviewer': ('read_compiled_quality32_2259_original_v2.py',
                 'b48a9b08617c93459f67057378041565fefa00cd1e01e5fd391727613c024821'),
    'preparer': ('prepare_quality32_2259_leg_v2.py',
                 '5c8cc35fdb5655cb4a8d8764854b088e246a4c683b8f88dd1be4d4f1327f5f4f'),
    'assessor': ('assess_quality32_2259_campaign_v2.py',
                 '223080f96874dad0972ec595214ad4988c169ceb061ced2143c3c2cf349de463'),
}
NEW = {'runtime': 'run_compiled_full_tail32_quality_current_lr125_v1.py', 'controller': 'control_compiled_full_tail32_quality_current_lr125_v1.py', 'reviewer': 'read_compiled_quality32_current_lr125_original_v1.py', 'preparer': 'prepare_quality32_current_lr125_leg_v1.py', 'assessor': 'assess_quality32_current_lr125_campaign_v1.py'}


FIXED_BINDING = {'pair_sha256': '47d3da0f048973a9ce85494585cfcddc034afe705aa37143e6e87ad07fbc07cb', 'selection_sha256': 'd819d5aa4548e6d4e21263b24b9481edb4251608c55108c72cabc3f2cdb6909f', 'reference': {'sha256': 'e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83', 'clocks': {'learner_frame_count': 1741229950, 'training_steps': 7128160, 'optimized_samples': 27621148672, 'frame_count': 3434514217}}, 'candidate': {'sha256': 'c7016b2501b5688e6f39c5ac2191b0f5bf2b61c02cee4197f7fadc191d2d1c9b', 'clocks': {'learner_frame_count': 2561076926, 'training_steps': 10205928, 'optimized_samples': 40227686400, 'frame_count': 5010346466}}, 'main_window_sha256': 'ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a'}

def require(value, message):
    if not value:
        raise ValueError(message)


def checked_binding(binding):
    require(type(binding) is dict and set(binding) == {'pair_sha256', 'reference', 'candidate', 'main_window_sha256', 'selection_sha256'},
            'Exact separate LR125 quality binding required')
    require(type(binding['reference']) is dict and type(binding['candidate']) is dict
        and type(binding['reference'].get('clocks')) is dict
        and all(type(v) is int for v in binding['reference']['clocks'].values()),
        'Typed reference and candidate policy descriptors required')
    require(binding == FIXED_BINDING and all(type(v) is int for v in binding['candidate']['clocks'].values()),
            'Exact independent current-policy selection, pair, policy and four clocks required')
    require(binding['reference'] == REFERENCE and binding['main_window_sha256'] == NEW_WINDOW,
            'Protected1741 reference and reviewed current LR125 health source required')
    for label, sha in [('pair', binding['pair_sha256']), ('candidate', binding['candidate'].get('sha256'))]:
        require(type(sha) is str and re.fullmatch('[0-9a-f]{64}', sha) is not None and sha != '0' * 64,
                'Invalid SHA: ' + label)
    require(binding['pair_sha256'] != OLD_PAIR, 'Closed2259 pair cannot be reused')
    candidate = binding['candidate']
    require(set(candidate) == {'sha256', 'clocks'} and candidate['sha256'] not in
        (REFERENCE['sha256'], 'c97f7d82118c6d743d3ce9649a709ef49f93946e349f55c5e9ab47339a27af9b'),
        'New distinct endpoint policy required')
    require(type(candidate['clocks']) is dict and set(candidate['clocks']) == set(BASELINE)
        and all(type(v) is int and v >= BASELINE[k] for k, v in candidate['clocks'].items())
        and candidate['clocks']['learner_frame_count'] >= BASELINE['learner_frame_count'],
        'Actual saved clocks must reach the new independent snapshot selection floor')
    return dict(reference=REFERENCE, candidate=candidate)


def render(binding):
    """Return source bytes and reversible provenance, without publication."""
    policies = checked_binding(binding)
    files, records = {}, {}
    for role in ('runtime', 'controller', 'reviewer', 'preparer', 'assessor'):
        name, expected_sha = OLD[role]
        original = (B / name).read_bytes()
        require(hashlib.sha256(original).hexdigest() == expected_sha, 'Source container changed: ' + role)
        effective = original
        replacements = []

        def replace(old, new):
            nonlocal effective
            old, new = old.encode(), new.encode()
            require(old != new and effective.count(old) == 1 and effective.count(new) == 0,
                    'Unique binding boundary changed: ' + role + ': ' + old.decode())
            effective = effective.replace(old, new)
            replacements.append(dict(original=old.decode(), effective=new.decode()))

        if role != 'controller':
            replace(OLD_PAIR, binding['pair_sha256'])
        if role in ('runtime', 'reviewer'):
            tree = ast.parse(original)
            node = next(n for n in tree.body if isinstance(n, ast.Assign) and
                        any(isinstance(t, ast.Name) and t.id == 'POLICIES' for t in n.targets))
            replace(ast.get_source_segment(original.decode(), node), 'POLICIES=' + repr(policies))
        if role == 'runtime':
            replace(OLD_WINDOW, NEW_WINDOW)
            replace('precommitted1741/2259 pair', 'precommitted1741/LR125 endpoint pair')
        if role in ('controller', 'reviewer'):
            replace(OLD['runtime'][0], NEW['runtime'])
        if role == 'reviewer':
            replace(OLD['runtime'][1], hashlib.sha256(files['runtime']).hexdigest())
            replace('fixed1741/2259 pair', 'fixed1741/LR125 endpoint pair')
        if role == 'preparer':
            replace('quality1741-vs-normal2259-after-JSON-', 'quality1741-vs-currentLR125-firstSave-')
            replace('robotron-compiled-full-tail32-integration-quality1741-2259-json-',
                    'robotron-compiled-full-tail32-integration-quality1741-currentlr125-firstsave-')
            replace('robotron-quality32-2259json-', 'robotron-quality32-currentlr125-firstsave-')
            # The label and two service unit names have different suffixes.
            lines = [line for line in effective.decode().splitlines() if 'original01-20261022' in line]
            require(len(lines) == 3 and effective.count(b'original01-20261022') == 3,
                    'Exactly three dated label/unit boundaries required')
            for line in lines:
                replace(line, line.replace('original01-20261022', 'original01-20261023'))
        if role == 'assessor':
            replace("cpucfg_name=('independent-review-controller-config-prospective197-original01.json' if role=='R1' else 'independent-review-controller-config.json')",
                    "cpucfg_name='independent-review-controller-config.json'")
        reversed_bytes = effective
        for item in reversed(replacements):
            old, new = item['original'].encode(), item['effective'].encode()
            require(reversed_bytes.count(new) == 1, 'Ambiguous reverse binding: ' + role)
            reversed_bytes = reversed_bytes.replace(new, old)
        require(reversed_bytes == original, 'Unrelated source change: ' + role)
        files[role] = effective
        records[role] = dict(source_container_path=str(B / name), source_container_sha256=expected_sha,
            future_path=str(B / NEW[role]), effective_sha256=hashlib.sha256(effective).hexdigest(),
            effective_bytes=len(effective), literal_replacements=replacements, reverse_exact=True)
    return files, dict(schema='robotron-LR125-five-source-quality-binding-v1', binding=binding,
        entries=records, publication_performed=False, actual_endpoint_CPU_verified_by_renderer=False,
        no_scoring_gate_startup_tail_or_runtime_limit_change=True)


if __name__ == '__main__':
    print('PLAN_ONLY: pure renderer; no publication, job, evaluator, control or runtime actions')
