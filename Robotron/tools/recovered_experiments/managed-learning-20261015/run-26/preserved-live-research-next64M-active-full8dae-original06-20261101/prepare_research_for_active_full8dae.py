import ast
import copy
import importlib.util
import json
import sys
import time
import urllib.request
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
F = B / 'quality32-protectedb231-vs-distinct8dae-fullgame-original01-20261101'
OLD = B / 'preserved-live-research-next64M-current-short8dae-original05-20261101'
P = B / 'preserved-live-research-next64M-active-full8dae-original06-20261101'
R = B / 'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


h = load('_preserveFull8H', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
head = load('_preserveFull8Head', R / 'sources/prepare_current_continuous_preservation_header_v3.py')
old = json.loads((OLD / 'job.json').read_text())
op = json.loads((OLD / 'prepared-CPU-preservation.json').read_text())
state = json.loads((B.parent / 'state.json').read_text())
assert state['active_quality_job']['directory'] == str(F) and state['scientific_job_running'] is True
owner = json.loads((F / 'original-sequence-owner.json').read_text())
assert int(Path('/proc', str(owner['pid']), 'stat').read_text().rsplit(')', 1)[1].split()[19]) == owner['birth']
pair_pin = h.pin(F / 'fixed-pair-precommit.json')
pair = json.loads(h.checked(pair_pin).read_text())
assert pair['roles']['candidate']['policy']['sha256'] == '8dae5cccd52624755d291a086cc363c7da3995a821cc1bc2c58310ce4bcb9537'
assert not P.exists()
P.mkdir(mode=0o700)
(P / 'sources').mkdir(mode=0o700)
parent = h.pin(G / 'tools/full_game_confirmation_proposal/preserve_live_research_checkpoint_CPU_v2.py')
source = h.checked(parent).read_text()
before = "    assert pair['schema']=='robotron-prospective-frozen-two-arm-deadline-screen-v2'"
after = ("    assert pair['schema']=='robotron-protectedb231-vs-postreboot1c-fullgame-fixed-pair-v1'\n"
         "    assert job['active_fixed_pair']['sha256']==" + repr(pair_pin['sha256']) + "\n"
         "    assert pair['roles']['candidate']['policy']['sha256']=='8dae5cccd52624755d291a086cc363c7da3995a821cc1bc2c58310ce4bcb9537'")
assert source.count(before) == 1
updated = source.replace(before, after)
assert updated.replace(after, before) == source
ast.parse(updated)
runtime = head.put(P / 'sources/preserve_current_full8dae_checkpoint_CPU_v1.py', updated.encode())
job = copy.deepcopy(old)
job.update(runtime=runtime, active_fixed_pair=pair_pin, output=str(P / 'acquisition-original01'), report=str(P / 'report.json'))
assert job['minimum_saved_learner_frames'] == 5309060592
jp = h.put(P / 'job.json', job)
ctl = load('_preserveFull8Ctl', h.checked(op['controller']))
config = copy.deepcopy(json.loads((OLD / 'controller-config.json').read_text()))
config.update(unit='robotron-preserve-next64M-full8dae-' + jp['sha256'][:12] + '.service', output=str(P / 'execution-original01'))
for index, value in enumerate(config['argv']):
    if value == old['runtime']['path']:
        config['argv'][index] = runtime['path']
    if value == str(OLD / 'job.json'):
        config['argv'][index] = jp['path']
    if value == op['job']['sha256']:
        config['argv'][index] = jp['sha256']
config['pins'] = [ctl.pin(pin['path']) for pin in [runtime, jp, pair_pin, job['previous_preservation_report']]]
cp = h.put(P / 'controller-config.json', config)
ctl.checked_config(cp['path'])
api = json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5))
proof = h.put(P / 'sources/exact-parent-context-guard-derivation.json', dict(
    parent=parent, selected=runtime, exact_reverse_single_guard_edit=True,
    changed_scope='Bind actual fullgame schema, exact pair SHA and distinct8dae; every copying/clock/finite/81Adam/scaler/phase/noGPU predicate unchanged.',
    saved_floor=job['minimum_saved_learner_frames'], Main_owner=job['main_owner'], payload_started=False))
prep = h.put(P / 'prepared-CPU-preservation.json', dict(
    status='PREPARED_UNLAUNCHED_REQUIRES_STABLE_SAVED_HEADER_AT_MILESTONE', runtime=runtime,
    source_guard_derivation=proof, controller=op['controller'], controller_config=cp, job=jp,
    active_fullgame_pair=pair_pin, previous_unlaunched_short_context=h.pin(OLD / 'prepared-CPU-preservation.json'),
    minimum_saved_learner_frames=job['minimum_saved_learner_frames'], observed_live_learner_frames=api['learner_frame_count'],
    observed_unix_s=time.time(), live_floor_reached=api['learner_frame_count'] >= job['minimum_saved_learner_frames'],
    launch_only_when='Same Main and still-active original fullgame context; verify stable published saved checkpoint header at or above5309060592 before one CPU2/4G/600s acquisition. Rebind if context changes. Live counters alone do not authorize copying.',
    no_checkpoint_or_replay_copy_started=True, selected_for_a_test=False, quality_qualified=False, promotion=False))
head.put(P / 'prepare_research_for_active_full8dae.py', Path('/tmp/prepare_research_for_active_full8dae.py').read_bytes())
print(json.dumps(dict(prepared={key: prep[key] for key in ['path', 'sha256', 'bytes']},
                      live_learner_frames=api['learner_frame_count'], saved_floor=job['minimum_saved_learner_frames'],
                      live_floor_reached=api['learner_frame_count'] >= job['minimum_saved_learner_frames'], payload_started=False)))
