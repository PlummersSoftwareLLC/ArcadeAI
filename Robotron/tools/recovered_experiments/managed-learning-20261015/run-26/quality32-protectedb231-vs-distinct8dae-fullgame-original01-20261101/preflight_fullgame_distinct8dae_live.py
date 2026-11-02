import ast
import copy
import fcntl
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
F = B / 'quality32-protectedb231-vs-distinct8dae-fullgame-original01-20261101'
OLD = B / 'quality32-protectedb231-vs-stopped77f9-restored8192-fullgame-original01-20261101'
SHORT = B / 'short15-protectedb231-vs-distinct8dae-fast-pending-original03-20261101'
BASE_SHORT = B / 'short15-protectedb231-vs-stopped77f9-immutable-review-original02-20261101'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


h = load('_full8LiveH', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
reader = load('_full8LiveReader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
read = lambda pin, as_json=True: reader.read_pin(pin, as_json=as_json)
prepared_pin = h.pin(F / 'prepared-campaign.json')
p = read(prepared_pin)
old = read(h.pin(OLD / 'prepared-campaign.json'))
family = read(p['source_family'])
sequence = load('_full8LiveSequence', h.checked(p['sequence_source']))
checks = []


def check(name, value):
    if not value:
        raise ValueError(name)
    checks.append(name)


def restore_globals(tree, previous_tree, names):
    previous = {node.targets[0].id: node for node in previous_tree.body
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
    for index, node in enumerate(tree.body):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            tree.body[index] = copy.deepcopy(previous[node.targets[0].id])


check('Exact original full sequence and predeclared four-leg/C1 rule', sequence.validate_future_prepared(dict(runtime=p['sequence_source']), p, h) == F)
for key in ['native', 'native_controller', 'leg_reviewer', 'campaign_assessor', 'decision_kernel',
            'wire_auditor', 'games_auditor', 'original_log_reviewer', 'current_Main_health',
            'current_Main_owned_overlap', 'slot_closeout', 'source_package', 'early_C1_assessor',
            'early_C1_numeric', 'sequence_source']:
    read(family[key], False)
    check('Immutable selected source ' + key, True)
old_tree = ast.parse(h.checked(old['native']).read_text())
new_tree = ast.parse(h.checked(p['native']).read_text())
restore_globals(new_tree, old_tree, ['PAIR_SHA', 'POLICIES'])
watch = next(node for node in ast.walk(new_tree) if isinstance(node, ast.FunctionDef) and node.name == 'watch_main')
loop = next(node for node in watch.body if isinstance(node, ast.While))
check('Only pending wait0.2s versus stable5s in native', ast.unparse(loop.test) == 'not health_stop.wait(0.2 if main_guard.pending_since is not None else 5)')
loop.test = ast.parse('not health_stop.wait(5)', mode='eval').body
check('Whole native AST otherwise unchanged from previous fullgame source', ast.dump(new_tree, include_attributes=False) == ast.dump(old_tree, include_attributes=False))
for key in ['leg_reviewer', 'campaign_assessor']:
    old_tree = ast.parse(h.checked(old[key]).read_text())
    new_tree = ast.parse(h.checked(p[key]).read_text())
    restore_globals(new_tree, old_tree, ['PAIR_SHA', 'CASE'])
    check('Whole ' + key + ' AST unchanged except pair/namespace', ast.dump(new_tree, include_attributes=False) == ast.dump(old_tree, include_attributes=False))
check('Controller and sequencing code unchanged', p['native_controller'] == old['native_controller'] and p['sequence_source'] == old['sequence_source'])
previous_tokens = set()
for case in [OLD, B / 'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101']:
    previous = read(h.pin(case / 'prepared-campaign.json'))
    for leg in previous['legs']:
        job = read(leg['native_job'])
        previous_tokens.update(job['sessions'].values())
        previous_tokens.update(job['connections'].values())
for case in [SHORT, BASE_SHORT]:
    for role in ['R1', 'C1']:
        job = read(h.pin(case / role / 'job.json'))
        previous_tokens.update(job['sessions'].values())
        previous_tokens.update(job['connections'].values())
tokens = set()
for leg in p['legs']:
    job = read(leg['native_job'])
    tokens.update(job['sessions'].values())
    tokens.update(job['connections'].values())
    check(leg['role'] + ' fresh unused output', not Path(job['output']).exists())
    check(leg['role'] + ' predeclared rule bound before first score', p['early_C1_rule'] in job['inputs'])
check('All256 transport identities distinct and absent from prior actual campaigns/screens', len(tokens) == 256 and not tokens.intersection(previous_tokens))
base_short = read(h.pin(BASE_SHORT / 'prepared-with-review.json'))
auditor = load('_full8LiveMainAuditor', h.checked(base_short['independent_owned_Main_auditor']))
observations = []
for leg in p['legs'][:2]:
    job = read(leg['native_job'])
    output = F / ('preflight-owned-Main-' + leg['role'] + '-original01')
    output.mkdir(mode=0o700)
    health = load('_full8LiveHealth' + leg['role'], h.checked(job['current_v6_health_source']))
    guard = health.CurrentV6MainHealth(job, output, h)
    guard.start()
    for index in range(4):
        if index:
            time.sleep(.2 if guard.pending_since is not None else 5.1)
        guard.observe()
    report = guard.finish(None)
    result = dict(main_samples=guard.samples, main_health_report=report, main_observer_lifecycle=guard.lifecycle)
    replay = auditor.audit_main(job, result, read, h)
    check(leg['role'] + ' original physical Main and cleanup replay passed', replay['accepted'] >= 2 and replay['all_logical_clocks_advanced'] and replay['final_accepted'])
    observations.append(dict(role=leg['role'], main_report=report, independent_audit=replay))
job = read(p['legs'][0]['native_job'])
short_prepared = read(h.pin(SHORT / 'prepared-with-review.json'))
ports_helper = load('_full8LivePorts', h.checked(short_prepared['selected_sources']['outer']))
ports = ports_helper.wait_for_job_ports(job)
check('All33 private ports simultaneously bindable with no traffic', ports['status'] == 'PORTS_FREE_BEFORE_LAUNCH' and ports['probe_sockets_released'])
with Path(job['lease']['path']).open('r+b') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    check('Same permanent GPU0 lease free', h.pin(job['lease']['path']) == job['lease'])
    fcntl.flock(stream, fcntl.LOCK_UN)
gpu = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory', '--format=csv,noheader'], capture_output=True, text=True, timeout=10)
check('Evaluation GPU0 has no compute process', gpu.returncode == 0 and job['gpu_uuid'] not in gpu.stdout)
check('No numerical runtime imported', 'torch' not in sys.modules and 'numpy' not in sys.modules)
result = h.put(F / 'preflight-physical-source-ABI-original01.json', dict(
    status='PASS_FRESH_FULLGAME_PHYSICAL_SOURCE_ABI_PREFLIGHT', observed_unix_s=time.time(),
    prepared=prepared_pin, checks=checks, checks_total=len(checks), Main=observations,
    selected_sequence=p['sequence_source'], selected_early_rule=p['early_C1_rule'],
    ports=ports, GPU_query=dict(exit=gpu.returncode, stdout=gpu.stdout, stderr=gpu.stderr),
    scientific_games_launched=False, confidence_qualified=False, promotion=False))
print(json.dumps(dict(status='PASS_FRESH_FULLGAME_PHYSICAL_SOURCE_ABI_PREFLIGHT', checks=len(checks),
                      report={key: result[key] for key in ['path', 'sha256', 'bytes']})), flush=True)
