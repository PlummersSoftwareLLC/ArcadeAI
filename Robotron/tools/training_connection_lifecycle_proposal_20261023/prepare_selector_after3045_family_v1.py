"""Prepare a fresh, explicitly non-launchable evaluator source family.

Retains original frozen inference and scientific gates. No runtime is invoked.
Source integration guards and engineering runtime evidence remain mandatory.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
OLD = R / 'quality32-protected1741-vs-currentLR125-quota64Protocol-firstSave-original01-preparation-20261024'
CAP = R / 'LR125-after-protected3045-firstSave-original01-preparation-20261025'
NEW = R / 'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025'
S = NEW / 'isolated-source-family-original01'


def load(path, name, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    h = load(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', '_family_h',
             '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    manifestpin = h.pin(OLD / 'selected-source-family-manifest.json')
    assert manifestpin['sha256'] == '4d195a9ed442e2e33b7b39cb39dabbd83b18af968406dbd530d8754a2bdafb10'
    manifest = json.loads(h.checked(manifestpin).read_bytes())
    ready = json.loads((OLD / 'new-original-quality-launch-readiness.json').read_bytes())
    renderer = load(Path(manifest['renderer']['path']), '_family_renderer', manifest['renderer']['sha256'])
    state = json.loads((G / 'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    reference = state['current_fixed_reference_policy']
    assert reference['sha256'] == 'b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
    h.checked(reference)
    numericpin = h.pin(CAP / 'independent-original-numerical-and-scope-closeout.json')
    assert numericpin['sha256'] == '2c82aed7080eb1e489645b22372c2df2831618e2d07fd6ae96312f6cd0fdb668'
    numeric = json.loads(h.checked(numericpin).read_bytes())
    candidate = numeric['source']
    assert candidate['sha256'] == 'df4314b05aceddeec263e598690fe803e32985497a0e26b38f36162452291bb4'
    h.checked(candidate)
    prior_pair = json.loads(h.checked(manifest['quality_pair']).read_bytes())
    clocks = prior_pair['candidate']['saved_clocks']
    assert all(numeric['saved_clocks'][k] > clocks[k] for k in clocks)
    aliaspin = h.pin(OLD / 'future-selector-serialization-reuse-UNSELECTED-proposal-original01/actual-writer-object-alias-guards-original01-20261025/independent-original-actual-writer-guards-and-scope-closeout.json')
    assert aliaspin['sha256'] == '2276bffabe05190a8fd2cfecbf3cb50976b213017ca386b8b1c5d7cf9a6401cd'
    assert json.loads(h.checked(aliaspin).read_bytes())['all24_actual_writer_methods_passed'] is True
    NEW.mkdir(mode=0o700)
    S.mkdir(mode=0o700)
    (S / 'components').mkdir(mode=0o700)
    (S / 'templates').mkdir(mode=0o700)
    transformations = []

    def source(path, text, original_pin, changes):
        compile(text, str(path), 'exec')
        with path.open('xb') as stream:
            stream.write(text.encode())
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        pin = h.pin(path)
        transformations.append(dict(original=original_pin, prepared=pin, changes=changes))
        return pin

    proposalpin = h.pin(OLD / 'future-selector-serialization-reuse-UNSELECTED-proposal-original01/fixed_slot_cohort_view_serialization_reuse_UNSELECTED_v1.py')
    assert proposalpin['sha256'] == 'd15cd0f342700af8e90c2027f134b42fa45cc070ee3bc57ddbd30ce82926a22e'
    view = source(S / 'components/fixed_slot_cohort_view_v1.py', h.checked(proposalpin).read_text(), proposalpin, [])
    replacements = {manifest['quota64_source_pins']['view']['sha256']: view['sha256']}

    def substitute(text):
        changes = []
        for old, new in replacements.items():
            count = text.count(old)
            if count:
                text = text.replace(old, new)
                changes.append(dict(old=old, new=new, count=count))
        return text, changes

    components = dict(view=view, bridge=manifest['quota64_source_pins']['bridge'])
    for key, oldpin in [('drain', manifest['quota64_source_pins']['drain']),
                         ('games_auditor', ready['games_auditor']), ('wire_auditor', ready['wire_auditor'])]:
        path = S / 'components' / Path(oldpin['path']).name
        text, changes = substitute(h.checked(oldpin).read_text())
        pin = source(path, text, oldpin, changes)
        components[key] = pin
        replacements[oldpin['sha256']] = pin['sha256']
        replacements[oldpin['path']] = pin['path']
    # Exact runtime-path bindings plus its selector module search directory.
    replacements[manifest['runtime']['path']] = str(S / renderer.FILENAMES['runtime'])
    old_component_directory = str(Path(manifest['quota64_source_pins']['view']['path']).parent)
    replacements["Path('" + old_component_directory + "')"] = "Path('" + str(S / 'components') + "')"
    templates = {}
    templatepins = {}
    for key, oldpin in manifest['source_templates'].items():
        text, changes = substitute(h.checked(oldpin).read_text())
        if any(isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NEW_CANDIDATE_CLOCK_FLOOR' for t in node.targets)
               for node in ast.parse(text).body):
            text = renderer.bind(text, 'NEW_CANDIDATE_CLOCK_FLOOR', clocks)
            changes.append(dict(binding='NEW_CANDIDATE_CLOCK_FLOOR', value=clocks))
        templates[key] = text
        templatepins[key] = source(S / 'templates' / Path(oldpin['path']).name, text, oldpin, changes)

    rendertext = h.checked(manifest['renderer']).read_text()
    rendertext = renderer.bind(rendertext, 'REF_SHA', reference['sha256'])
    rendertext = renderer.bind(rendertext, 'REF_CLOCKS', clocks)
    rendertext = rendertext.replace("'Original protected1741 reference required'", "'Protected3045 reference required'")
    old_predicate = "set(clocks) == set(FAILED_CLOCKS) and all(type(clocks[key]) is int and clocks[key] > floor\n            for key, floor in FAILED_CLOCKS.items())"
    new_predicate = "set(clocks) == set(REF_CLOCKS) and all(type(clocks[key]) is int and clocks[key] > floor\n            for key, floor in REF_CLOCKS.items())"
    assert rendertext.count(old_predicate) == 1
    rendertext = rendertext.replace(old_predicate, new_predicate)
    renderpin = source(S / 'render_quota64_selected_family_after3045_v1.py', rendertext,
                       manifest['renderer'], [dict(bindings=['REF_SHA', 'REF_CLOCKS'],
                        candidate_clock_floor='Protected3045 all four saved clocks', scientific_thresholds_unchanged=True)])
    new_renderer = load(Path(renderpin['path']), '_after3045_renderer', renderpin['sha256'])
    pair = copy.deepcopy(prior_pair)
    pair.update(state='FIXED3045_REFERENCE_LATER3262_CANDIDATE_BEFORE_ALL_NEW_GAMES',
        hypothesis='Continued forward training at retained LR125 may improve over protected3045. Same isolated selector implementation for both policies. No causal LR, throughput or learning-speed claim.',
        reference=dict(policy=reference, saved_clocks=clocks, CPU_report=prior_pair['candidate']['CPU_report'],
                       original_CPU_readback=prior_pair['candidate']['original_CPU_readback'], protected_copy_proof=state['protected_winner_readback']),
        candidate=dict(policy=candidate, saved_clocks=numeric['saved_clocks'], CPU_report=numeric['original_report'],
                       original_CPU_readback=numericpin),
        per_policy_saved_LR={role: dict(lr_scale=.125, optimizer_lr=6.25e-6) for role in ('reference', 'candidate')},
        selection_precommit=h.pin(CAP / 'fresh-later-policy-selection-precommit.json'),
        capture_readback=h.pin(CAP / 'independent-original-capture-and-current-main-closeout.json'),
        historical_scientific_contracts=pair.pop('scientific_contracts'),
        historical_protocol_interface_correction=pair.pop('protocol_interface_correction'),
        historical_original_pair=manifest['quality_pair'],
        old_candidate_scores_reused_as_new_reference=False, engineering_and_initializer_validation_outstanding=True,
        created_unix_s=time.time())
    pairpin = h.put(NEW / 'campaign-inputs-and-gates-precommit.json', pair)
    rendered = new_renderer.render(templates, pair, pairpin['sha256'])
    selected = {}
    for key, item in rendered.items():
        assert item['path'] == str(S / renderer.FILENAMES[key])
        selected[key] = source(Path(item['path']), item['source'], templatepins[key], [dict(pure_pair_binding=pairpin)])
        assert selected[key]['sha256'] == item['sha256']
    family = copy.deepcopy(manifest)
    family.update(selected)
    family.update(schema='robotron-isolated-selector-after3045-prepared-source-family-v1',
        quality_pair=pairpin, source_templates=templatepins, renderer=renderpin,
        quota64_source_pins={key: components[key] for key in ('view', 'drain', 'bridge')},
        games_auditor=components['games_auditor'], wire_auditor=components['wire_auditor'],
        original_source_family=manifestpin, actual_writer_alias_guards=aliaspin,
        selected_family_runtime_guards_passed=False, actual_initializer_verified=False,
        engineering_runtime_validation_passed=False, display_projection_fix_verified=False,
        readiness_for_scientific_launch=False, production_changed=False,
        outstanding=['Run actual preparer-to-native initializer guards with current binding, all roles and source dependencies',
                     'Guard bounded final display projection instead of the oversized assessment read',
                     'Precommit and complete controlled engineering emulator-load validation',
                     'Build fresh readiness and original scientific sequence only after prerequisites pass'])
    familypin = h.put(NEW / 'prepared-source-family-manifest.json', family)
    proofpin = h.put(NEW / 'source-derivation-and-incomplete-preparation-record.json',
        dict(schema='robotron-selector-after3045-source-preparation-v1', family=familypin, pair=pairpin,
             exact_source_transformations=transformations, source_changes_only=True,
             original_game_writer_and_measurement_sources_unchanged=True,
             new_sources_syntax_compiled_only=True, guards_and_runtime_still_required=True,
             new_reference_games_collected=False, new_candidate_quality_unmeasured=True,
             old_results_and_policies_untouched=True, no_runtime_or_controller_invoked=True))
    print(json.dumps(dict(family=familypin, preparation=proofpin, pair=pairpin)))


if __name__ == '__main__':
    main()
