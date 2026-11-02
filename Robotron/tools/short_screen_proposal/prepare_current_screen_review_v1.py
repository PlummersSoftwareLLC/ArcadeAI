"""Freeze independent per-arm reviews before any new short-screen scores."""
import argparse
import ast
import copy
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pprint
import sys

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


def execute(case):
    h = load('_current_review_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    read = lambda entry: json.loads(h.checked(entry).read_bytes())
    base_pin = h.pin(case / 'prepared.json')
    prepared = read(base_pin)
    for role in ('R1', 'C1'):
        job = read(prepared['jobs'][role]['job'])
        assert not Path(job['output']).exists()
    assert not (case / 'original-sequence-launch-intent.json').exists()
    source = case / 'review-source'
    source.mkdir(mode=0o700)
    derivations = []

    def save(name, parent, text):
        ast.parse(text)
        path = source / name
        with path.open('x') as stream:
            stream.write(text); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        entry = h.pin(path)
        derivations.append(dict(parent=parent, selected=entry, patch=''.join(difflib.unified_diff(
            h.checked(parent).read_text().splitlines(True), text.splitlines(True)))))
        return entry

    job = read(prepared['jobs']['R1']['job'])
    parent = h.pin(G / 'tools/power_recovery/review_closed_post_reboot_screen_leg_v1.py')
    text = h.checked(parent).read_text()
    text = replace_once(text, "C=G/'logs/managed-learning-20261015/run-26/post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'",
                        'C=Path(' + repr(str(case)) + ')')
    text = replace_once(text, "prepared_pin=h.pin(C/'prepared.json')", "prepared_pin=h.pin(C/'prepared-with-review.json')")
    text = replace_once(text, 'fa61b63cc2f8b9c12e5298507d66c42ec8d64129bd1d66732ba355dc725d495d',
                        prepared['selection']['sha256'])
    text = replace_once(text, '947f82b448abd66cf2118ae31c5ac980a8e61d174e9f201be2c4200b0bf19e33',
                        job['components']['score_auditor']['sha256'])
    function = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == 'audit_main')
    old = ast.get_source_segment(text, function)
    new = ('OWNED_MAIN_AUDITOR=' + pprint.pformat(prepared['independent_owned_Main_auditor']) + '\n\n'
        'def audit_main(job,result,read,h):\n'
        "    auditor=load('_current_selected_owned_Main_auditor',Path(OWNED_MAIN_AUDITOR['path']),OWNED_MAIN_AUDITOR['sha256'])\n"
        '    h.checked(OWNED_MAIN_AUDITOR)\n'
        '    return auditor.audit_main(job,result,read,h)')
    text = replace_once(text, old, new)
    text = replace_once(text, 'main=audit_main(job,result,read,support)', 'main=audit_main(job,result,read,h)')
    before = "    for pin in job['inputs']:h.checked(pin)"
    extra = """    require(result['compile_report']['all_shapes_verified']==list(range(1,17))
        and result['policy_before']['numeric_policy']['compiled'] is True,'Actual common compiled inference required')
    checkpoint_pin=prepared['horizon_checkpoint_auditor'];read(checkpoint_pin,False)
    checkpoints=load('_current_selected_checkpoint_auditor',Path(checkpoint_pin['path']),checkpoint_pin['sha256'])
    require(set(result['predeclared_horizon_checkpoints'])=={str(v)for v in job['checkpoint_offsets_ns']},
        'All predeclared intermediate horizons required')
    checkpoint_reviews={key:checkpoints.audit_checkpoint(job,read(pin),seal,score,prefixes,result,games,modules['score_auditor'])
        for key,pin in result['predeclared_horizon_checkpoints'].items()}
"""
    text = replace_once(text, before, extra + before)
    text = replace_once(text, 'prefixes=prefixes,score=score,main=main,',
                        'prefixes=prefixes,score=score,main=main,intermediate_checkpoint_reviews=checkpoint_reviews,')
    reviewer = save('review_current_short_screen_leg_v1.py', parent, text)
    cpu_path = B / 'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/state-sources/control_stopped_fullstate600_CPU_v1.py'
    cpu_pin = h.pin(cpu_path)
    cpu = load('_current_screen_review_CPU_control', h.checked(cpu_pin))
    review_protocol = dict(source=reviewer, CPU_controller=cpu_pin,
        sequence=h.pin(G / 'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py'),
        reader=h.pin(G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'),
        archive=h.pin(G / 'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'), configs={}, reports={})
    for leg in ('R1', 'C1'):
        directory = case / (leg + '-independent-review-original01')
        directory.mkdir(mode=0o700)
        report = directory / 'report.json'
        config = dict(unit='robotron-short15-review-' + hashlib.sha256(str(case).encode()).hexdigest()[:10] + '-' + leg.lower() + '.service',
            output=str(directory / 'execution-original01'),
            argv=['/usr/bin/python3', '-I', '-B', reviewer['path'], '--execute', '--leg', leg,
                '--source-sha256', reviewer['sha256'], '--output', str(report)],
            properties=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0', 'RuntimeMaxSec=600',
                'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'],
            observation_s=660, pins=[cpu.pin(reviewer['path']), cpu.pin(prepared['selection']['path']),
                cpu.pin(prepared['jobs'][leg]['job']['path'])])
        cp = h.put(directory / 'controller-config.json', config)
        cpu.checked_config(cp['path'])
        review_protocol['configs'][leg] = cp
        review_protocol['reports'][leg] = str(report)
    prepared['independent_review'] = review_protocol
    parent = prepared['selected_sources']['outer']
    text = h.checked(parent).read_text()
    text = replace_once(text, 'import stat\n', 'import stat\nimport sys\n')
    text = replace_once(text, "            seals[leg] = validate_leg(result, job)",
        "            seals[leg] = validate_leg(result, job)\n"
        "            independent=review_original_arm(prepared,leg)\n"
        "            write(args.output/(leg+'-independent-review-closed.json'),independent,True)")
    review_function = '''
def review_original_arm(prepared,leg):
    helper=load_screen_helpers();protocol=prepared['independent_review']
    def load(name,entry):
        path=helper.checked(entry);spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        return module
    seq=load('_current_arm_original_CPU_sequence',protocol['sequence'])
    reader=load('_current_arm_original_reader',protocol['reader'])
    archive=load('_current_arm_original_archives',protocol['archive'])
    cpu=load('_current_arm_original_CPU_controller',protocol['CPU_controller'])
    config_pin=protocol['configs'][leg];config=json.loads(helper.checked(config_pin).read_bytes())
    directory=Path(config['output']).parent
    seq.invoke_controller_once(directory,'',protocol['CPU_controller'],config_pin,helper)
    read=lambda pin,as_json=True:reader.read_pin(pin,as_json=as_json)
    closed=seq.verify_closed_scope(directory,'',config_pin,helper,read,archive,cpu,exit_zero=False)
    require(read(closed['result'])['actual_exit']==0,'Original independent review process failed; no retry')
    report_pin=helper.pin(protocol['reports'][leg]);report=read(report_pin)
    require(report['status']=='PASS_ORIGINAL_SELECTED_PREFIX_SCORE_AND_BOUNDED_MAIN_REPLAY',
        'Original independent score/prefix/owned-Main review failed; next arm must remain unstarted')
    return dict(original_report=report_pin,original_closed_scope=closed,no_retry=True,promotion=False)

'''
    text = replace_once(text, '\ndef main():', '\n' + review_function + '\ndef main():')
    outer = save('outer_with_original_independent_reviews_v1.py', parent, text)
    prepared['selected_sources'] = dict(prepared['selected_sources'], outer=outer, independent_leg_review=reviewer)
    prepared['unextended_parent_preparation'] = base_pin
    prepared['review_derivations'] = h.put(case / 'independent-review-and-outer-derivations.json', dict(
        builder=h.pin(Path(__file__)), sources=derivations, all_before_first_scores=True,
        actual_model_or_GPU_or_MAME_launched=False, prior_case_or_results_modified=False))
    pp = h.put(case / 'prepared-with-review.json', prepared)
    parent = h.pin(G / 'tools/power_recovery/launch_post_reboot_screen_v1.py')
    text = h.checked(parent).read_text()
    text = replace_once(text, "CASE=G/'logs/managed-learning-20261015/run-26/post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'",
                        'CASE=Path(' + repr(str(case)) + ')')
    text = replace_once(text, "prepared=h.pin(CASE/'prepared.json')", "prepared=h.pin(CASE/'prepared-with-review.json')")
    launcher = save('launch_fresh_original_screen_v1.py', parent, text)
    packet = h.put(case / 'prepared-with-independent-review-NOT-LAUNCHED.json', dict(
        status='PREPARED_FRESH_SHORT15_WITH_PRECOMMITTED_INDEPENDENT_PER_ARM_REVIEW_NOT_LAUNCHED',
        prepared=pp, launcher=launcher, independent_review_protocol=review_protocol,
        preflight_required_before_launch=True, promotion=False))
    print(json.dumps(dict(packet={k: packet[k] for k in ('path', 'sha256', 'bytes')},
                          launcher={k: launcher[k] for k in ('path', 'sha256', 'bytes')})))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--case', type=Path)
    a = p.parse_args()
    if a.execute:
        assert a.case
        execute(a.case)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
