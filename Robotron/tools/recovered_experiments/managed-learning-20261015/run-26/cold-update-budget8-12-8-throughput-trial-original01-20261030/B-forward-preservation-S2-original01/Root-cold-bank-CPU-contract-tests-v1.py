import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import time
import zipfile

R = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = R/'logs/managed-learning-20261015/run-26/future-current-main-cold-cap-state-preservation-original01-20261030'
H = Path(__file__).resolve().parent
D = H/'Root-bank-counter-lineage-diagnostic-original01'
S = H/'Root-cold-bank-draft-metadata-smoke-original01'
O = H/'Root-final-cold-bank-CPU-contract-tests-original01'
O.mkdir(exist_ok=False)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def read(path):
    return json.loads(path.read_text())

rows = []
helper = load(N/'current_main_preservation_inputs_cold_bank_v2.py', 'root_final_origin')
validator = load(N/'continuous_budget_bank_intent_cold_bank_v2.py', 'root_final_intent')
selection = read(H/'actual-DATA-preparation-original01/stop-DATA/runtime/actual-current-stop-selection.json')
banks = read(D/'current-bank-metadata-and-header-descriptors.json')
before = read(D/'current-API-before.json')
after = read(D/'current-API-after.json')
origin = helper.cold_bank_origin(selection, banks)
kwargs = dict(expected_pid=167514, now=after['ts'], expected_cap=12,
              loaded_baseline=dict(frame_count=8917176727, measurement_frame_count=7679621, optimized_samples=71471781888))
intent = validator.validate(before, after, banks, origin=origin, **kwargs)
rows.append(dict(case='exact-inherited-origin-and-stable-API-accepted', status='PASS'))
old_validator = load(N/'continuous_budget_bank_intent_v1.py', 'root_old_intent')
try:
    old_validator.validate(before, after, banks, **kwargs)
except ValueError as exc:
    assert 'prior disk selector disagree' in str(exc)
    rows.append(dict(case='original-counter-namespace-refusal-reproduced', status='PASS'))
else:
    raise AssertionError('Original namespace refusal not reproduced')

def reject(label, operation):
    try:
        operation()
    except ValueError:
        rows.append(dict(case=label, status='PASS'))
    else:
        raise AssertionError('Failed to reject '+label)

def change_origin_bank(field, value):
    changed = copy.deepcopy(banks)
    changed['hof']['selector'][field] = value
    helper.cold_bank_origin(selection, changed)

reject('changed-inherited-selector-generation', lambda: change_origin_bank('generation', 'gen-'+'a'*32))
reject('changed-inherited-revision', lambda: change_origin_bank('mutation_generation', 14))
changed = copy.deepcopy(banks)
changed['hof']['arrays']['states']['header']['shape'][0] -= 1
reject('changed-inherited-array-header', lambda: helper.cold_bank_origin(selection, changed))
changed = copy.deepcopy(banks)
changed['ephof']['metadata']['sha256'] = '0'*64
reject('changed-inherited-NPZ-hash', lambda: helper.cold_bank_origin(selection, changed))
changed = copy.deepcopy(selection)
changed['owner']['pid'] += 1
reject('wrong-current-owner', lambda: helper.cold_bank_origin(changed, banks))

mutations = [
 ('bank-writer-active', lambda d: d['bank_persistence'].update(writer_active=True)),
 ('intervening-bank-write', lambda d: d['bank_persistence'].update(writes=1)),
 ('intervening-bank-capture', lambda d: d['bank_persistence'].update(capture_attempts=1)),
 ('incorrect-local-saved-revision', lambda d: d['bank_persistence']['saved_revision'].update(hof=2)),
 ('incorrect-dirty-flag', lambda d: d['bank_persistence']['dirty'].update(ephof=False)),
 ('unknown-optimizer-outcome', lambda d: d['host_pipeline']['learning_exposure']['optimizer']['total'].update(unavailable=1)),
 ('changed-replay-epoch', lambda d: d['host_pipeline']['learning_exposure']['replay'].update(epoch=2)),
 ('remaining-client', lambda d: d.update(client_count=1)),
 ('moving-optimized-clock', lambda d: d.update(optimized_samples=d['optimized_samples']+4096)),
]
for label, mutate in mutations:
    changed = copy.deepcopy(after)
    mutate(changed)
    reject(label, lambda changed=changed: validator.validate(before, changed, banks, origin=origin, **kwargs))

vpath = N/'verify_current_continuous_stopped_fullstate_cold_bank_v5.py'
tree = ast.parse(vpath.read_bytes())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ('require', 'fulfill_bank_intent')]
namespace = dict(json=json)
exec(compile(ast.Module(body=functions, type_ignores=[]), str(vpath), 'exec'), namespace)
fulfill = namespace['fulfill_bank_intent']
old_semantics = {}
member_raw = {}
for bank, descriptor in banks.items():
    raw = Path(descriptor['metadata']['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == descriptor['metadata']['sha256']
    with zipfile.ZipFile(Path(descriptor['metadata']['path'])) as archive:
        member_raw[bank] = {name: archive.read(name) for name in archive.namelist()}
    old_semantics[bank] = {name: hashlib.sha256(raw).hexdigest() for name, raw in member_raw[bank].items()}
new_semantics = copy.deepcopy(old_semantics)
final_banks = copy.deepcopy(banks)
scalars = copy.deepcopy(origin['scalars'])
local_adds = intent['process_adds_at_seal']
for bank, target in intent['target_revisions'].items():
    final_banks[bank]['selector'].update(previous=banks[bank]['selector']['generation'], generation='gen-'+('a' if bank=='hof' else 'b')*32, mutation_generation=target)
    final_banks[bank]['pointer']['mtime_ns'] = 2_000_000_000
    final_banks[bank]['captured_adds'] = local_adds
    scalars[bank].update(mutation_generation=target, captured_adds=local_adds)
    if not intent['dirty_at_seal'][bank]:
        scalars[bank]['stale_age'] += local_adds
        scalars[bank]['stale_age_normal'] += local_adds
    else:
        scalars[bank].update(stale_age=100, stale_age_normal=100)
    for key in ('mutation_generation', 'captured_adds', 'stale_age', 'stale_age_normal'):
        member = key+'.npy'
        changed_raw = member_raw[bank][member][:-8] + struct.pack('<q', scalars[bank][key])
        new_semantics[bank][member] = hashlib.sha256(changed_raw).hexdigest()

def verify(final=final_banks, semantic=new_semantics, scalar=scalars):
    return fulfill(intent, final, old_semantics, semantic, 1.0, episode_capacity=192, final_scalars=scalar)
verify()
rows.append(dict(case='clean-and-dirty-local-final-generations-accepted', status='PASS'))
for label, bank, key, value in [
 ('old-generation-retained', 'hof', 'generation', banks['hof']['selector']['generation']),
 ('wrong-previous-generation', 'hof', 'previous', 'gen-'+'c'*32),
 ('wrong-final-local-revision', 'ephof', 'mutation_generation', 8),
]:
    changed = copy.deepcopy(final_banks)
    changed[bank]['selector'][key] = value
    reject(label, lambda changed=changed: verify(final=changed))
for label, bank, key, value in [
 ('foreign-captured-add-count', 'hof', 'captured_adds', 11732734),
 ('wrong-final-NPZ-revision', 'hof', 'mutation_generation', 13),
 ('wrong-clean-relative-age', 'hof', 'stale_age', scalars['hof']['stale_age']+1),
 ('negative-dirty-age', 'ephof', 'stale_age', -1),
 ('unreachable-dirty-age', 'ephof', 'stale_age', local_adds+1),
]:
    changed = copy.deepcopy(scalars)
    changed[bank][key] = value
    reject(label, lambda changed=changed: verify(scalar=changed))
changed = copy.deepcopy(new_semantics)
changed['hof']['ep_score.npy'] = '0'*64
reject('clean-episode-score-payload-hash-change', lambda: verify(semantic=changed))
changed = copy.deepcopy(final_banks)
changed['hof']['arrays']['states']['header']['shape'][0] -= 1
reject('clean-state-header-dimension-change', lambda: verify(final=changed))
changed = copy.deepcopy(final_banks)
changed['hof']['arrays']['states']['bytes'] -= 2
reject('clean-state-byte-extent-change', lambda: verify(final=changed))
changed = copy.deepcopy(final_banks)
changed['hof']['episodes'] -= 1
reject('episode-count-loss', lambda: verify(final=changed))
changed = copy.deepcopy(final_banks)
changed['hof']['pointer']['mtime_ns'] = 0
reject('pre-stop-pointer-timestamp', lambda: verify(final=changed))

report = dict(schema='robotron-root-cold-bank-lineage-CPU-contract-check-v1', status='PASS', cases=rows,
              tested_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [N/'current_main_preservation_inputs_cold_bank_v2.py', N/'continuous_budget_bank_intent_cold_bank_v2.py', vpath]},
              synthetic_final_save_metadata_not_runtime_qualification=True, actual_CPU_execution=True,
              live_runtime_control_or_model_or_array_body_mutation=False, checked_unix_s=time.time())
with (O/'report.json').open('x') as stream:
    json.dump(report, stream, allow_nan=False, indent=2)
    stream.write('\n')
    stream.flush()
    os.fchmod(stream.fileno(), 0o444)
    os.fsync(stream.fileno())
print(json.dumps(dict(status='PASS', cases=len(rows), report=str(O/'report.json'))))
