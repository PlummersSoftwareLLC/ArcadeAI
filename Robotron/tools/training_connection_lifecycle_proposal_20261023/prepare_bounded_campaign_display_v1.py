"""Prepare a display-only derivative; preserve the other six evaluator sources."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
N = R / 'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025'
S = N / 'isolated-source-family-original01'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    h = load(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', '_displayprep_h')
    assert h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    originalpin = h.pin(N / 'prepared-source-family-manifest.json')
    assert originalpin['sha256'] == 'a0f01eb0798a7b560556314b7ab861bb0a0f27946156a1b54f709dc79130bbe6'
    family = json.loads(h.checked(originalpin).read_bytes())
    renderer = load(h.checked(family['renderer']), '_displayprep_renderer')
    helper = Path(__file__).parent / 'bounded_campaign_display_projection_v1.py'
    helpertext = helper.read_text()
    helper.chmod(0o444)
    chunks = [ast.get_source_segment(helpertext, node) for node in ast.parse(helpertext).body
              if isinstance(node, (ast.Assign, ast.FunctionDef))]
    original = h.checked(family['source_templates']['display_source']).read_text()
    assert original.count('\ndef main():') == 1
    changed = original.replace('\ndef main():', '\n' + '\n\n'.join(chunks) + '\n\ndef main():')
    oldblock = """        assessment=read(root/'independent-campaign-assessment-original01/assessment.json')
        if assessment.get('valid')is False:state='failed';outcome='invalid';reason=assessment.get('error')
        elif assessment.get('valid')is True and terminal_zero(root,'campaign-assessment-controller-original-result.json'):
            state='finished';outcome='qualified'if assessment.get('quality_qualified')else'not_improved'
"""
    newblock = """        projection=project_campaign(root)
        if projection is not None:
            state=projection['state'];outcome=projection['outcome'];reason=projection['reason']
            if state=='finished':current=None
"""
    assert changed.count(oldblock) == 1
    changed = changed.replace(oldblock, newblock)

    def write(path, text):
        compile(text, str(path), 'exec')
        with path.open('xb') as stream:
            stream.write(text.encode()); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        return h.pin(path)

    templatepin = write(S / 'templates/display_quality32_quota64_bounded_UNSELECTED_v3.py', changed)
    rendertext = h.checked(family['renderer']).read_text()
    filenames = dict(renderer.FILENAMES, display_source='display_quality32_quota64_bounded_selected_v3.py')
    rendertext = renderer.bind(rendertext, 'FILENAMES', filenames)
    renderpin = write(S / 'render_quota64_selected_family_after3045_bounded_display_v2.py', rendertext)
    new_renderer = load(h.checked(renderpin), '_bounded_display_renderer')
    templatepins = dict(family['source_templates'], display_source=templatepin)
    templates = {key: h.checked(pin).read_text() for key, pin in templatepins.items()}
    pair = json.loads(h.checked(family['quality_pair']).read_bytes())
    rendered = new_renderer.render(templates, pair, family['quality_pair']['sha256'])
    for key, item in rendered.items():
        if key == 'display_source':
            selectedpin = write(Path(item['path']), item['source'])
            assert selectedpin['sha256'] == item['sha256']
        else:
            assert family[key]['path'] == item['path'] and family[key]['sha256'] == item['sha256']
            assert h.checked(family[key]).read_text() == item['source']
    newfamily = copy.deepcopy(family)
    newfamily.update(display_source=selectedpin, source_templates=templatepins, renderer=renderpin,
        prior_prepared_family=originalpin, bounded_projection_helper_source=h.pin(helper),
        unchanged_six_native_scientific_sources=True,
        actual_initializer_closeout_for_unchanged_native_components=h.pin(N / 'actual-initializer-source-guards-CPU-original01/independent-original-family-guards-and-CPU-closeout.json'),
        display_projection_fix_verified=False, readiness_for_scientific_launch=False,
        outstanding=['Run original bounded display projection guards and independently close their CPU scope',
                     'Precommit and complete controlled engineering emulator-load validation',
                     'Build fresh readiness and original scientific sequence only after prerequisites pass'])
    familypin = h.put(N / 'prepared-source-family-manifest-bounded-display-v2.json', newfamily)
    proofpin = h.put(N / 'bounded-display-source-derivation-original01.json', dict(
        schema='robotron-bounded-display-source-derivation-v1', original_family=originalpin,
        new_family=familypin, original_display=family['display_source'], new_display=selectedpin,
        helper_source=h.pin(helper), embedded_helper_without_import_dependency=True,
        exact_original_main_block=oldblock, exact_new_main_block=newblock,
        other_six_native_scientific_source_pins_identical=True, scientific_pair_unchanged=family['quality_pair'],
        no_original_artifact_modified=True, no_runtime_or_display_launched=True,
        display_guards_still_required=True))
    print(json.dumps(dict(family=familypin, derivation=proofpin, display=selectedpin)))


if __name__ == '__main__':
    main()
