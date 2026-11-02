import ast
import copy
import importlib.util
import json
import os
import secrets
import sys
import time
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
OLD = B / 'quality32-protectedb231-vs-stopped77f9-restored8192-fullgame-original01-20261101'
SHORT = B / 'short15-protectedb231-vs-distinct8dae-fast-pending-original03-20261101'
D8 = B / 'distinct-stopped8dae-policy-preparation-original01-20261101'
N = B / 'future-fast-pending-physical-watch-source-original01-20261101'
F = B / 'quality32-protectedb231-vs-distinct8dae-fullgame-original01-20261101'
R = B / 'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


h = load('_full8H', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
head = load('_full8Head', R / 'sources/prepare_current_continuous_preservation_header_v3.py')
reader = load('_full8Reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
read = lambda pin, as_json=True: reader.read_pin(pin, as_json=as_json)
assert not F.exists()
F.mkdir(mode=0o700)
(F / 'selected-source').mkdir(mode=0o700)
oldprep = read(h.pin(OLD / 'prepared-campaign.json'))
oldpair = read(h.pin(OLD / 'fixed-pair-precommit.json'))
oldfamily = read(h.pin(OLD / 'selected-source-family.json'))
selection = h.pin(SHORT / 'next-fresh-fullgame-comparison-selection.json')
selected = read(selection)
role_report_pin = h.pin(D8 / 'CPU-roles-original01/report.json')
role_report = read(role_report_pin)
assert role_report['status'] == 'PASS_FRESH_REFERENCE_AND_CANDIDATE_CPU_ACQUISITION'
roleprep = read(h.pin(D8 / 'CPU-roles-original01/prepared-CPU-roles.json'))
seqhelper = load('_full8ScopeSeq', G / 'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py')
archive = load('_full8ScopeArchive', G / 'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
cpuctl = load('_full8ScopeCPU', h.checked(roleprep['controller']))
verified_cpu_scope = seqhelper.verify_closed_scope(
    D8 / 'CPU-roles-original01', '', roleprep['controller_config'],
    h, read, archive, cpuctl, exit_zero=True)
actual_cpu_closeout = h.pin(D8 / 'CPU-roles-original01/original-role-CPU-result-and-owned-closeout.json')
assert read(actual_cpu_closeout)['all_original_resources_closed'] is True
cpu_closeout = h.put(F / 'reverified-original-role-CPU-scope-closure.json', dict(
    status='PASS_ORIGINAL_CPU_ROLE_SCOPE_REVERIFIED_CLOSED', actual_exit=0,
    all_original_CPU_resources_closed=True, all_original_resources_closed=True,
    original_CPU_closeout=actual_cpu_closeout, original_CPU_report=role_report_pin,
    original_scope=verified_cpu_scope, payload_relaunched=False,
    scope='Read-only re-verification of the same original successful CPU role check; adapt the established fullgame closure field from actual original evidence.'))
pair = copy.deepcopy(oldpair)
pair.update(created_unix_s=time.time(), selected_after_cutoff=selection,
            actual_candidate_description='Distinct stopped8dae at saved LFC5254630919; valid short15 mean-0.61percent is inconclusive for natural full-game ranking. Original77f9 R1 failure remains invalid; no prior scores reused.')
for role in ['reference', 'candidate']:
    item = role_report['roles'][role]
    assert item['checkpoint'] == selected[role]['checkpoint']
    pair['roles'][role] = dict(
        policy=item['checkpoint'], source_policy=item['source_checkpoint'], saved_clocks=item['clocks'],
        CPU_report=h.pin(Path(item['checkpoint']['path']).parent / 'CPU-policy-readback.json'),
        original_CPU_readback=cpu_closeout, policy_authority=item['original_policy_authority'])
pairpin = h.put(F / 'fixed-pair-precommit.json', pair)
derivations = []


def assignment(source, name):
    return next(ast.get_source_segment(source, node) for node in ast.parse(source).body
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))


def derive(name, parent, edits):
    original = h.checked(parent).read_text()
    text = original
    for before, after in edits:
        assert text.count(before) == 1, (name, before[:60])
        text = text.replace(before, after, 1)
    restored = text
    for before, after in reversed(edits):
        assert restored.count(after) == 1
        restored = restored.replace(after, before, 1)
    assert restored == original
    ast.parse(text)
    pin = head.put(F / 'selected-source' / name, text.encode())
    derivations.append(dict(parent=parent, selected=pin, exact_reverse_edits=True,
                            edits=[dict(before=before, after=after) for before, after in edits]))
    return pin


native_parent = h.pin(N / 'run_faster_pending_watch_UNBOUND_v1.py')
source = h.checked(native_parent).read_text()
policies = {role: dict(sha256=item['policy']['sha256'], clocks=item['saved_clocks'])
            for role, item in pair['roles'].items()}
native = derive('run_fixed_b231_vs_distinct8dae_fullgame_v1.py', native_parent, [
    (assignment(source, 'PAIR_SHA'), 'PAIR_SHA=' + repr(pairpin['sha256'])),
    (assignment(source, 'POLICIES'), 'POLICIES=' + repr(policies))])
source = h.checked(oldprep['leg_reviewer']).read_text()
reviewer = derive('review_fixed_b231_vs_distinct8dae_fullgame_v1.py', oldprep['leg_reviewer'], [
    (assignment(source, 'PAIR_SHA'), 'PAIR_SHA=' + repr(pairpin['sha256'])),
    (assignment(source, 'CASE'), 'CASE=Path(' + repr(str(F)) + ')')])
source = h.checked(oldprep['campaign_assessor']).read_text()
assessor = derive('assess_fixed_b231_vs_distinct8dae_fullgame_v1.py', oldprep['campaign_assessor'], [
    (assignment(source, 'PAIR_SHA'), 'PAIR_SHA=' + repr(pairpin['sha256'])),
    (assignment(source, 'CASE'), 'CASE=Path(' + repr(str(F)) + ')')])
proof = h.put(F / 'selected-source/exact-source-bindings.json', dict(
    status='EXACT_PAIR_NAMESPACE_BINDINGS_AND_PREVIOUSLY_CPU_QUALIFIED_PENDING_POLL',
    pair=pairpin, derivations=derivations,
    parent_fullgame_native=oldprep['native'], pending_loop_CPU19=h.pin(N / 'CPU-poll-cadence-contracts-original01.json'),
    latest_valid_short_screen=h.pin(SHORT / 'completed-original-short15-independent-result-and-owned-closeout.json'),
    scientific_games_started=False, live_pending_branch_qualification_claimed=False, promotion=False))
sequence = oldprep['sequence_source']
rule = h.put(F / 'predeclared-early-C1-rule.json', dict(
    schema='robotron-predeclared-fullgame-C1-failure-rule-v1', campaign_directory=str(F), pair=pairpin,
    required_closed_roles=['R1', 'C1', 'R2'], stage='after_R2_review_before_C2_launch',
    skip_C2_only_if_C1_gate_failed=True, promotion_shortcut_allowed=False,
    assessor=oldprep['early_C1_assessor'], numeric_gate=oldprep['early_C1_numeric'], scheduler=sequence))
family = copy.deepcopy(oldfamily)
family.update(pair=pairpin, native=native, leg_reviewer=reviewer, campaign_assessor=assessor,
              native_source_proof=proof, reviewer_source_proof=proof, roles_CPU=role_report_pin,
              roles_CPU_closeout=cpu_closeout, early_C1_rule=rule,
              actual_current_runtime=h.pin(R / 'actual-restored-current-training-runtime.json'))
family_pin = h.put(F / 'selected-source-family.json', family)
ctl = load('_full8NativeCtl', h.checked(oldprep['native_controller']))
current = read(h.pin(SHORT / 'R1/job.json'))
legs = []
all_tokens = set()
for previous_leg in oldprep['legs']:
    role = previous_leg['role']
    model_role = previous_leg['model_role']
    directory = F / Path(previous_leg['directory']).name
    directory.mkdir(mode=0o700)
    chosen = pair['roles'][model_role]
    job = read(previous_leg['native_job'])
    job.update(
        runtime=native, output=str(directory / 'runtime-original01'), quality_pair_precommit=pairpin,
        checkpoint=chosen['policy'], expected_policy_clocks=chosen['saved_clocks'],
        label='fixed-b231-vs-distinct8dae-' + role + '-original01-20261101',
        current_main=current['current_main'], current_fleet=current['current_fleet'],
        screen_support=current['screen_support'], current_v6_health_source=family['current_Main_health'],
        owned_TRAIN_overlap_source=family['current_Main_owned_overlap'],
        current_v6_health_qualification=family['full64_owned_Main_engineering'],
        source_family_manifest=family_pin,
        selected_change='New distinct8dae frozen full-game hypothesis; fresh64/two-per-all32/full tails, unchanged strict7sACK/10s overlap+collection/15s gap and all scoring/closure kernels. Only pending observation sleep changes from5s to0.2s; no old score reuse or promotion shortcut.')
    job['quota64_validation']['qualified_full64_owned_Main_engineering'] = family['full64_owned_Main_engineering']
    job['sessions'] = {str(slot): secrets.token_hex(16) for slot in range(4096, 4128)}
    job['connections'] = {str(slot): secrets.token_hex(16) for slot in range(4096, 4128)}
    fresh = set(job['sessions'].values()) | set(job['connections'].values())
    assert len(fresh) == 64 and not fresh.intersection(all_tokens)
    all_tokens.update(fresh)
    pins = [native, job['checkpoint'], job['source_package'], job['mame'], job['lua'], job['seed_runtime'],
            job['screen_support'], job['current_v6_health_source'], job['owned_TRAIN_overlap_source'],
            job['current_v6_health_qualification'], family_pin, pairpin, chosen['CPU_report'],
            chosen['original_CPU_readback'], rule, sequence, proof,
            *job['quota64_source_pins'].values(), *job['quota64_validation'].values(),
            *job['full_tail_predecessors'].values(), job['historical_startup_acceptance_scope'],
            job['validated_CPU_prefix'], *job['boot_seed']['inputs'], job['boot_seed']['module']]
    pins.extend(family[key] for key in ['native_controller', 'leg_reviewer', 'campaign_assessor',
                'decision_kernel', 'wire_auditor', 'games_auditor', 'original_log_reviewer',
                'early_C1_assessor', 'early_C1_numeric'])
    pins.extend(job['current_fleet'][key] for key in ['job', 'original_membership', 'rolemap', 'physical_helper', 'source_authority'])
    pins.extend([job['current_fleet']['supervisor']['source'], job['current_main']['startup_authority'], job['current_main']['startup_held']])
    job['inputs'] = list({pin['path']: pin for pin in pins}.values())
    job_pin = h.put(directory / 'job.json', job)
    config = read(previous_leg['native_controller_config'])
    config.update(unit='robotron-b231-8dae-' + role.lower() + '-fullgame-original01.service',
                  output=str(directory / 'execution-original01'))
    config['argv'] = [str(G.parent / '.venv-gb300/bin/python'), '-Xgil=0', '-I', '-B', native['path'],
                      '--execute', '--job', job_pin['path'], '--job-sha256', job_pin['sha256'],
                      '--source-sha256', native['sha256']]
    config['pins'] = [ctl.pin(pin['path']) for pin in [job_pin, *job['inputs']]]
    config_pin = h.put(directory / 'controller-config.json', config)
    ctl.checked_config(config_pin['path'])
    preparation = h.put(directory / 'prepared-native.json', dict(
        schema='robotron-fixed-fullgame-native-leg-preparation-v1', role=role, pair=pairpin,
        native=native, job=job_pin, controller=oldprep['native_controller'], controller_config=config_pin,
        source_family=family_pin, scientific_job_launched=False, promotion=False))
    review_dir = directory / 'independent-review-original01'
    review_dir.mkdir(mode=0o700)
    review_job = read(previous_leg['review_job_template'])
    review_job.update(runtime=reviewer, native_prepared=preparation,
                      original_native_closeout_path=str(directory / 'positive-original-native-closeout.json'),
                      report=str(review_dir / 'report.json'))
    review_pin = h.put(directory / 'review-job-template.json', review_job)
    legs.append(dict(index=previous_leg['index'], role=role, model_role=model_role, directory=str(directory),
                     native_prepared=preparation, native_job=job_pin, native_controller_config=config_pin,
                     review_job_template=review_pin, native_closeout_path=str(directory / 'positive-original-native-closeout.json'),
                     review_closeout_path=str(directory / 'positive-original-review-closeout.json'),
                     display_live_path=str(directory / 'display-live.json'), display_receipt_path=str(directory / 'display-reviewed.json')))
assert len(all_tokens) == 256
plan = h.put(F / 'plan.json', dict(
    schema='robotron-fixed-fullgame-dashboard-plan-v1', checkpoints={role: item['policy'] for role, item in pair['roles'].items()},
    legs=[dict(index=leg['index'], role=leg['model_role'], job=dict(label='Protected champion' if leg['model_role'] == 'reference' else 'Distinct later candidate'),
               evaluator_status_path=leg['display_live_path'], receipt_path=leg['display_receipt_path']) for leg in legs]))
prepared = copy.deepcopy(oldprep)
prepared.update(campaign_directory=str(F), pair=pairpin, source_family=family_pin, native=native,
                leg_reviewer=reviewer, campaign_assessor=assessor, legs=legs,
                dashboard_plan=plan, sequence_source=sequence, early_C1_rule=rule)
pp = h.put(F / 'prepared-campaign.json', prepared)
with (F / 'status.json').open('x') as stream:
    json.dump(dict(state='prepared', current_leg=None, legs=[dict(index=leg['index'], role=leg['model_role'], state='pending') for leg in legs], outcome=None, updated_unix_s=time.time()), stream)
    stream.flush()
    os.fsync(stream.fileno())
checker_parent = h.pin(G / 'tools/full_game_confirmation_proposal/check_fixed_confirmation_preflight_v1.py')
source = h.checked(checker_parent).read_text()
checker = derive('check_fixed_distinct8dae_preflight_v1.py', checker_parent, [
    (assignment(source, 'F'), 'F=Path(' + repr(str(F)) + ')'),
    ("    sequence_path=Path(__file__).with_name('run_fixed_confirmation_sequence_v1.py')", "    sequence_path=Path(" + repr(sequence['path']) + ")")])
head.put(F / 'prepare_fullgame_distinct8dae.py', Path('/tmp/prepare_fullgame_distinct8dae.py').read_bytes())
print(json.dumps(dict(prepared={key: pp[key] for key in ['path', 'sha256', 'bytes']},
                      preflight_checker={key: checker[key] for key in ['path', 'sha256', 'bytes']},
                      pair_sha=pairpin['sha256'], fresh_transport_identities=len(all_tokens), native_or_MAME_launched=False)))
