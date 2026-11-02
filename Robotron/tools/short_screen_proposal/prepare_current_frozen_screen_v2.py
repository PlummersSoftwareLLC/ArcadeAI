"""Prepare one fresh 15-minute frozen screen; default inert, never launches.

Keep the CPU-qualified duration/score/retirement implementation. Bind the
protected reference, current frozen candidate and qualified owned Main health.
"""
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
import time
import uuid

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
C = B / 'post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
M = B / 'post-engineering-fullstate-preservation-original03-20261101'
F = B / 'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'
PROFILE = C / 'future-selectable-duration-source-original04'
HEALTH = F / 'future-owned-overlap-observer-reviewer-original02'
REFERENCE = 'b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
CANDIDATE = '77f9f42fbdd67c0d5081229710140931422292d83ee437cc08de64c188fe7228'


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
    helper = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    h = load('_fresh_screen_h', helper)
    read = lambda pin: json.loads(h.checked(pin).read_bytes())
    runtime_pin = h.pin(M / 'actual-restored-current-training-runtime.json')
    runtime = read(runtime_pin)
    proposal_pin = h.pin(M / 'next-fresh-frozen-pair-proposal-original01.json')
    proposal = read(proposal_pin)
    assert proposal['reference']['sha256'] == REFERENCE and proposal['candidate']['sha256'] == CANDIDATE
    profile_pin = h.pin(PROFILE / 'source-only-duration-profile.json')
    profile = read(profile_pin)
    qualification = read(h.pin(PROFILE / 'CPU-qualified-duration-and-checkpoint-audit-packet.json'))
    assert qualification['status'] == 'PASS_PROSPECTIVE_SOURCE_CPU48_AND_INDEPENDENT_CHECKPOINT_AUDIT_ONLY'
    for entry in profile['sources'].values():
        h.checked(entry)
    assert case.is_absolute() and case.parent.resolve(strict=True) == case.parent and not case.exists()
    case.mkdir(mode=0o700)
    source_dir = case / 'selected-source'
    source_dir.mkdir(mode=0o700)
    sources, deltas = {}, []

    def save(role, parent, text):
        ast.parse(text)
        old = h.checked(parent).read_text()
        path = source_dir / (role + '.py')
        with path.open('x') as stream:
            stream.write(text)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        pin = h.pin(path)
        sources[role] = pin
        deltas.append(dict(role=role, parent=parent, selected=pin,
            patch=''.join(difflib.unified_diff(old.splitlines(True), text.splitlines(True)))))
        return pin

    health_pin = h.pin(HEALTH / 'current_v6_owned_overlap_health_v5.py')
    owned_pin = h.pin(HEALTH / 'owned_train_connection_overlap_v2.py')
    assert owned_pin['sha256'] == 'c10b6a2e752b61aa345e648c26ee9bf7b82a711ab73f1351138ee31dcdb2a879'
    parent = profile['sources']['native']
    text = h.checked(parent).read_text()
    text = replace_once(text, "REFERENCE_SHA='06558cbc185b76b2b44229ddfe469d2a92037e70f89de2481e8fb055f2c736ad'",
                        'REFERENCE_SHA=' + repr(REFERENCE))
    text = replace_once(text, "selected['schema']=='robotron-prospective-S2-b231-two-arm-cutoff-screen-v1'",
                        "selected['schema']=='robotron-prospective-frozen-two-arm-deadline-screen-v2'")
    text = replace_once(text, "    h.checked(job['policy_authority']);modules=load_components(job,h)",
        "    require(job['current_fleet']==selected['current_fleet']\n"
        "        and job['current_v6_health_source']==selected['current_v6_health_source']\n"
        "        and job['owned_TRAIN_overlap_source']==selected['owned_TRAIN_overlap_source']\n"
        "        and job['current_v6_health_source']['sha256']==" + repr(health_pin['sha256']) + "\n"
        "        and job['owned_TRAIN_overlap_source']['sha256']==" + repr(owned_pin['sha256']) + ",\n"
        "        'Exact qualified current physical Main observer sources and epoch required')\n"
        "    h.checked(job['current_v6_health_source']);h.checked(job['owned_TRAIN_overlap_source'])\n"
        "    h.checked(job['policy_authority']);modules=load_components(job,h)")
    text = replace_once(text, "        main_guard=context['support'].CurrentMainHealth(job,output,h);main_guard.start()",
        "        main_module=load('_short_screen_actual_owned_Main',h.checked(job['current_v6_health_source']))\n"
        "        main_guard=main_module.CurrentV6MainHealth(job,output,h);main_guard.start()")
    native = save('native', parent, text)

    parent = profile['sources']['controller']
    text = h.checked(parent).read_text()
    namespace = 'robotron-short15-b231-77f9-' + hashlib.sha256(str(case).encode()).hexdigest()[:10] + '-'
    text = replace_once(text, 'robotron-duration-profile-S2-screen-', namespace)
    text = replace_once(text, '-original01-20261031.service', '-original01-20261101.service')
    text = replace_once(text, profile['sources']['native']['path'], native['path'])
    controller = save('controller', parent, text)

    # Reuse the independently exercised same-byte post-writer seal kernel.
    runner_pin = h.pin(G / 'tools/full_game_confirmation_proposal/run_owned_overlap_fullgame_engineering_v3.py')
    runner = load('_short_screen_seal_parent', h.checked(runner_pin))
    seal_source = ast.get_source_segment(Path(runner_pin['path']).read_text(), next(n for n in
        ast.parse(Path(runner_pin['path']).read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'seal_closed_log'))
    parent = profile['sources']['outer']
    text = h.checked(parent).read_text()
    text = replace_once(text, 'import socket\n', 'import socket\nimport stat\n')
    text = replace_once(text, '            seals[leg] = validate_leg(result, job)',
        "            if not (result['original_exit']==0 and result['unit_released'] is True\n"
        "                    and result['lifecycle_complete'] is True):\n"
        "                raise ValueError('Original native scope must close before log sealing')\n"
        "            original_owner=read(Path(config['output'])/'root-original-identity.json')\n"
        "            if live(original_owner['pid'],original_owner['starttime_ticks']):\n"
        "                raise ValueError('Original native writer remains live')\n"
        "            helper=load_screen_helpers()\n"
        "            log_seal={name:seal_closed_log(Path(config['output'])/name,helper,writers_closed=True)\n"
        "                      for name in ('stdout.txt','stderr.txt')}\n"
        "            write(args.output/(leg+'-original-native-log-seal.json'),log_seal,True)\n"
        '            seals[leg] = validate_leg(result, job)')
    insertion = """\n\ndef require(value, message):
    if not value:
        raise ValueError(message)


def load_screen_helpers():
    path=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    if hashlib.sha256(path.read_bytes()).hexdigest()!='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1':
        raise ValueError('Exact immutable-reader helper required')
    spec=importlib.util.spec_from_file_location('_screen_seal_helpers',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
\n\n""" + seal_source + '\n\n'
    text = replace_once(text, '\ndef main():', insertion + '\ndef main():')
    outer = save('outer', parent, text)

    # Extract exactly the already-qualified physical Main replay statements.
    parent = h.pin(HEALTH / 'review_owned_overlap_fullgame_UNBOUND_v1.py')
    raw = h.checked(parent).read_text()
    function = next(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == 'review')
    start = next(i for i, n in enumerate(function.body) if isinstance(n, ast.Assign)
        and any(getattr(t, 'id', '') == 'source' for t in n.targets)
        and "'_eng_review_actual_v6_health'" in ast.get_source_segment(raw, n))
    end = next(i for i, n in enumerate(function.body) if i > start and isinstance(n, ast.For)
        and ast.unparse(n.target) == 'pin' and ast.unparse(n.iter) == 'bindings.values()')
    block = function.body[start:end + 1]
    helper_text = ('"""Exact qualified physical Main replay kernel, no scientific-case acceptance.\n"""\n'
        'import math\nimport importlib.util\nimport sys\n\n'
        'def require(value,message):\n    if not value:raise ValueError(message)\n\n'
        'def load(name,path):\n    spec=importlib.util.spec_from_file_location(name,path)\n'
        '    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)\n'
        '    return module\n\n'
        'def audit_main(job,result,read,h):\n' + ''.join('    ' + line + '\n' for statement in block
            for line in ast.unparse(statement).splitlines()) +
        "    first=result['main_samples'][0]['clocks']\n"
        "    require(all(previous[k]>first[k]for k in first),'All logical Main clocks must advance')\n"
        "    return dict(accepted=accepted,pending=pending,maximum_gap_s=max_gap,unique_bindings=len(bindings),\n"
        "        final_accepted=True,all_logical_clocks_advanced=True,quality_qualified=False)\n")
    audit_pin = save('owned_main_auditor', parent, helper_text)
    actual = next(n for n in ast.parse(helper_text).body if isinstance(n, ast.FunctionDef) and n.name == 'audit_main')
    assert [ast.dump(n) for n in actual.body[:len(block)]] == [ast.dump(n) for n in block]

    base_job = json.loads((C / 'R1/job.json').read_text())
    reference_role = json.loads((F / 'fixed-pair-precommit.json').read_text())['roles']['reference']
    candidate_report = read(proposal['candidate_strict_CPU_report'])
    reference = dict(display_name='Protected champion', checkpoint=proposal['reference'],
        authority=reference_role['CPU_report'], expected_policy_clocks=reference_role['saved_clocks'])
    candidate = dict(display_name='Saved current policy', checkpoint=proposal['candidate'],
        authority=proposal['candidate_strict_CPU_report'],
        expected_policy_clocks={k: candidate_report['saved_scalars'][k] for k in
            ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')})
    owner = runtime['trainer']
    held = read(runtime['held_report'])
    main = dict(API='http://127.0.0.1:8771/api/now', owner={
        'pid': owner['pid'], 'starttime_ticks': owner['birth'], 'unit': owner['unit'],
        'invocation_id': owner['invocation_id'], 'cgroup': owner['cgroup']},
        environment=dict(DQN_BATCH_SIZE='4096', DQN_MAX_SAMPLES_PER_FRAME='8', DQN_N_STEP='3',
            DQN_PER_PRIORITY_METRIC='ce', ROBOTRON_CONTINUOUS_TRAINING_MODE='1',
            ROBOTRON_CONTINUOUS_STARTUP_JOB_SHA256=runtime['startup_job']['sha256']),
        exposure={kind: {k: held['exposure'][kind][k] for k in
            ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')} for kind in ('optimizer', 'replay')},
        startup_authority=runtime['startup_authority'], startup_held=runtime['held_report'])
    f = json.loads(Path(runtime['fleet_status_path']).read_text())
    assert f['trainer'] == runtime['trainer'] and f['supervisor'] == runtime['fleet']
    current_fleet = dict(epoch=f['epoch'], supervisor=runtime['fleet'], trainer=runtime['trainer'],
        source_authority=f['source_authority'], original_membership=f['original_membership'], rolemap=f['rolemap'],
        physical_helper=read(runtime['fleet_job'])['physical_helper'], job=runtime['fleet_job'], status_path=runtime['fleet_status_path'])
    selected = dict(schema='robotron-prospective-frozen-two-arm-deadline-screen-v2', status='ROOT_SELECTED_NOT_LAUNCHED',
        ordered_legs=['R1', 'C1'], screen_only=True, promotion=False, reference=reference, candidate=candidate,
        private_score_stall_timeout_s=0, private_lua_score_stall_timeout_s=4260,
        private_protocol_sources=dict(runtime=native, lua=base_job['lua']),
        current_main=main, current_fleet=current_fleet, current_v6_health_source=health_pin,
        owned_TRAIN_overlap_source=owned_pin, screen_horizon_ns=900_000_000_000,
        checkpoint_offsets_ns=[300_000_000_000, 600_000_000_000], short_screen_is_promotion_evidence=False,
        selected_unix_s=time.time(), proposal=proposal_pin, current_training_runtime=runtime_pin,
        no_historical_scores_reused=True, prior_failed_case_not_retried=True,
        inference_scope='Exploratory score at15-minute wall-time cutoff; no full-game ranking/confidence or promotion claim.')
    selection = h.put(case / 'selection.json', selected)
    checkpoint_parent=h.pin(G/'tools/short_screen_proposal/audit_horizon_checkpoint_v1.py')
    checkpoint_auditor=save('horizon_checkpoint_auditor',checkpoint_parent,h.checked(checkpoint_parent).read_text())
    assert checkpoint_auditor['sha256']==checkpoint_parent['sha256'] and checkpoint_auditor['identity']['mode']=='0o444'
    source_map = dict(profile['sources'], **sources)
    source_map['lua'] = base_job['lua']
    source_map['health'] = health_pin
    source_map['owned_overlap'] = owned_pin
    source_map['post_writer_log_seal_parent'] = runner_pin
    mapping = h.put(case / 'selected-source-map.json', source_map)
    configs = dict(ordered_legs=['R1', 'C1'], configs={})
    prepared = dict(ordered_legs=['R1', 'C1'], selection=selection, selected_sources=source_map,
        screen_only=True, promotion=False, jobs={}, independent_owned_Main_auditor=audit_pin,
        horizon_checkpoint_auditor=checkpoint_auditor)
    tokens = set()
    for leg, policy in [('R1', reference), ('C1', candidate)]:
        folder = case / leg
        folder.mkdir(mode=0o700)
        job = copy.deepcopy(base_job)
        label = case.name + '-' + leg
        job.update(runtime=native, leg=leg, checkpoint=policy['checkpoint'], expected_policy_clocks=policy['expected_policy_clocks'],
            policy_authority=policy['authority'], current_main=main, current_fleet=current_fleet,
            current_v6_health_source=health_pin, owned_TRAIN_overlap_source=owned_pin, screen_selection=selection,
            horizon_ns=900_000_000_000, checkpoint_offsets_ns=selected['checkpoint_offsets_ns'],
            output=str(folder / 'runtime-original01'), label=label, measurement_label=label,
            sessions={str(slot): uuid.uuid4().hex for slot in base_job['actor_slots']},
            connections={str(slot): uuid.uuid4().hex for slot in base_job['actor_slots']},
            components=profile['components'])
        tokens.update(job['sessions'].values()); tokens.update(job['connections'].values())
        inputs = [selection, mapping, runtime_pin, proposal_pin, policy['authority'], runtime['startup_job'],
            runtime['held_report'], runtime['release_consumed'], runtime['startup_authority'], runtime['fleet_job'],
            current_fleet['original_membership'], current_fleet['rolemap'], current_fleet['physical_helper'],
            current_fleet['supervisor']['source'], health_pin, owned_pin, h.pin(Path(__file__)),
            h.pin(G / 'models_dqn/learning_control.json')]
        inputs += [job[k] for k in ('runtime', 'lua', 'completion_codec', 'screen_support', 'seed_runtime', 'source_package')]
        inputs += list(job['components'].values()) + job['boot_seed']['inputs'] + [job['boot_seed']['module']]
        job['inputs'] = list({p['path']: p for p in inputs}.values())
        jp = h.put(folder / 'job.json', job)
        config = json.loads((C / 'R1/controller-config.json').read_text())
        config.update(unit=namespace + leg.lower() + '-original01-20261101.service', output=str(folder / 'controller-execution-original01'))
        config['argv'] = [str(G.parent / '.venv-gb300/bin/python'), '-Xgil=0', '-I', '-B', native['path'],
            '--execute', '--job', jp['path'], '--job-sha256', jp['sha256'], '--source-sha256', native['sha256']]
        ctl = load('_current_short_screen_controller_' + leg, h.checked(controller))
        config['pins'] = [ctl.pin(jp['path']), ctl.pin(native['path'])]
        config_pin = h.put(folder / 'controller-config.json', config)
        ctl.checked_config(config_pin['path'])
        configs['configs'][leg] = config_pin
        prepared['jobs'][leg] = dict(job=jp, argv=config['argv'])
    assert len(tokens) == 128
    prepared['controller_configs'] = h.put(case / 'controller-configs.json', configs)
    prepared['derivations'] = h.put(case / 'exact-parent-derivations.json', dict(
        builder=h.pin(Path(__file__)), parent_duration_profile=profile_pin, changes=deltas,
        owned_Main_audit_AST_block_unchanged=True, original_main_replay_statements=len(block),
        scoring_and_retirement_components_unchanged=True, resource_limits_unchanged=True))
    pp = h.put(case / 'prepared.json', prepared)
    print(json.dumps(dict(status='PREPARED_NOT_PREFLIGHTED_NOT_LAUNCHED', case=str(case),
        prepared={k: pp[k] for k in ('path', 'sha256', 'bytes')}, duration_seconds_per_arm=900)))


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
