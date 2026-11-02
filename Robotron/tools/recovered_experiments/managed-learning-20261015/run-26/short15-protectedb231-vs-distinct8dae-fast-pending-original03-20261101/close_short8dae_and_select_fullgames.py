from pathlib import Path
import fcntl
import importlib.util
import json
import os
import subprocess
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
F = B / 'short15-protectedb231-vs-distinct8dae-fast-pending-original03-20261101'
R = B / 'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101'
D8 = B / 'distinct-stopped8dae-policy-preparation-original01-20261101'
STATE = B.parent / 'state.json'
DELL = G / 'DELL_SETUP.md'
PUBLIC = G / 'html/next-policy-evaluation.json'
spec = importlib.util.spec_from_file_location('_closeScreen8Header', R / 'sources/prepare_current_continuous_preservation_header_v3.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
small = lambda pin: {key: pin[key] for key in ['path', 'sha256', 'bytes']}
result_pin = h.metadata(F / 'completed-original-short15-independent-result-and-owned-closeout.json')[0]
result = json.loads(Path(result_pin['path']).read_text())
assert result['actual_original_tool_exit'] == 0 and result['all_original_resources_closed']
assert result['full_game_quality_qualified'] is False and result['promotion'] is False
old = STATE.read_bytes()
db = DELL.read_bytes()
ub = PUBLIC.read_bytes()
state = json.loads(old)
goal = state['optimization_goal']
prior = state['current_optimization_recovery_index']
assert prior['sha256'] == '89a8c1390103ef9ebc4c3b3a89490b32ce05322502908b0061887217d8caf375'
roles = json.loads((D8 / 'CPU-roles-original01/report.json').read_text())['roles']
selection = h.put(F / 'next-fresh-fullgame-comparison-selection.json', dict(
    schema='robotron-distinct8dae-fresh-fullgame-selection-v1',
    status='SELECTED_NOT_PREPARED_OR_LAUNCHED', observed_unix_s=time.time(),
    completed_short_screen=small(result_pin),
    reference=dict(checkpoint=roles['reference']['checkpoint'], clocks=roles['reference']['clocks'],
                   authority=h.metadata(D8 / 'roles-original01/reference/CPU-policy-readback.json')[0]),
    candidate=dict(checkpoint=roles['candidate']['checkpoint'], clocks=roles['candidate']['clocks'],
                   authority=h.metadata(D8 / 'roles-original01/candidate/CPU-policy-readback.json')[0]),
    rationale='Candidate trails at5/10/15 minutes by13.67/4.18/0.61 percent, and all64 games remained unfinished. This fixed-time screen cannot rank natural full-game survival or final scores. Evaluate the same distinct8dae snapshot with fresh full games rather than infer full-game quality from an inconclusive short endpoint.',
    ordered_legs=['R1', 'C1', 'R2', 'C2'],
    each_leg='64 natural complete games, first two known starts per all32 slots, full tails; minimum50 floor unchanged.',
    fixed_reference_pool='Fresh R1+R2 only, pooled128 fixed before C1/C2 gate assessment; no old or short-screen scores.',
    candidate_gate='C1 and C2 each separately mean>=1.05 fresh fixed reference mean and median>=reference median. No candidate pooling, retry or censored-game rescue.',
    early_rejection='After original R1/C1/R2 independent review, skip C2 only if exact separate C1 gate fails; passing C1 still requires C2.',
    health='Retain original7s cleanupACK/10s overlap and collection/15s observation-gap and all original process/TCP/source/score/owned-scope predicates. Faster pending polling remains source-qualified by CPU contracts with actual per-sample runtime replay; no unobserved live-branch qualification claim.',
    original_failed77f9R1_remains_invalid=True, scientific_fullgame_launch_started=False,
    prior_scores_reused=False, formal99percent_confidence_claim=False, promotion=False))
api = json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5))
fleet = json.loads((R / 'post-backup-fleet-v6-original02/status.json').read_text())
assert api['pipeline_read_error'] == api['bank_persistence_read_error'] == ''
assert api['training_enabled'] is True and fleet['errors'] == []
lease = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
with lease.open('rb') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.flock(stream, fcntl.LOCK_UN)
readback = h.put(F / 'post-original-screen-current-Main-and-private-lease-readback.json', dict(
    observed_unix_s=time.time(), private_lease_free=True,
    Main={key: api[key] for key in ['ts', 'client_count', 'learner_frame_count', 'training_steps',
                                  'optimized_samples', 'fps', 'lr', 'pipeline_read_error', 'bank_persistence_read_error']},
    fleet_counts=fleet['counts'], fleet_errors=fleet['errors'],
    scope='Current cached API, supervisor ledger and private lease readback; original experiment-owned closures are independently verified in final result.',
    promotion=False))
pre = h.put(F / 'canonical-before-completed-screen-index187.exact.json', old)
dp = h.put(F / 'DELL-before-completed-screen-index187.exact.md', db)
up = h.put(F / 'public-before-completed-screen-index187.exact.json', ub)
summary = ('Original short15 tool20313 actual0 complete and all experiment resources closed. '
           'Reference mean1541889.84375/median1558812.5; candidate mean1532470.3125/median1535475, '
           '15min delta-0.6109percent;5min-13.6728percent/10min-4.1830percent. '
           'All64 firstgames censored; shortendpoint valid, fullgame ranking/confidence unqualified, no promotion. '
           'Original Main replay153accepted/0pending each arm. Extra rollup all-normal0 assumption failed and is preserved; '
           'unchanged protocol permits post-seal censored SIGTERM, proven for21 candidate exits with9positive/negative checks; '
           'all original native/review scopes actual0,43MAME0/21post-cutoff-15,all64reaped, no score or original reviewer changed. '
           'Fresh fullgame selectionb231-vs8dae committed: new R1/C1/R2/C2,64natural/all32/2each/fulltails, '
           'separate C1/C2 >=1.05 fixedfresh128reference mean and preserved median; predeclared C1earlyreject onlyafterR1/C1/R2. '
           'Next prepare exact new namespace/pair source family and preflight before one original fullgame launch. '
           'Maintraining healthy; research savedfloor5309060592 still requires rebind from now-closed shortscreen before capture.')
ip = h.put(F / 'completed-short15-fullgame-followup-selected-index-original187.json', dict(
    schema='robotron-current-optimization-recovery-index-v1',
    status='VALID_ORIGINAL_SHORT15_CLOSED_FULLGAME_RANKING_UNRESOLVED_FRESH_FULLTEST_SELECTED',
    observed_unix_s=time.time(), prior_index=prior, state_preimage=pre,
    DELL_preimage=dp, public_preimage=up, completed_short_screen=small(result_pin),
    next_fullgame_selection=small(selection), current_Main_readback=small(readback),
    actual_running_wait=None, main_training_running=True, scientific_job_running=False,
    next_action=summary, promotion=False))
for target in [state, goal]:
    target.update(current_optimization_recovery_index=small(ip), actual_running_wait=None,
                  main_training_running=True, scientific_job_running=False,
                  engineering_job_running=False, active_screen_job=None,
                  last_completed_short_screen=small(result_pin), pending_fullgame_comparison=small(selection))
goal.update(next_action=summary, latest_verified_wait=None,
            next_research_preservation_requires_rebind=True, updated_unix_s=time.time(),
            latest_goal_turn_classification=dict(classification='progress',
                evidence='Observed original tool20313 terminal0; audited separate original reference/candidate reviews and all resource closures, recomputed endpoints, and selected a wholly fresh natural-fullgame comparison.'))
state['updated_unix_s'] = time.time()
raw = (json.dumps(state, separators=(',', ':'), allow_nan=False) + '\n').encode()
assert len(raw) < 1 << 20
public = json.loads(ub)
public.update(state='finished', stage='short_score_screen_complete', current_leg=None,
              observation_unix_s=time.time(), updated_unix_s=time.time(), quality_qualified=False, promotion=False)
public['next_work'].update(
    state='fullgame_comparison_preparation', current_stage='Short screen complete; preparing full-game comparison',
    detail='At15 minutes: reference mean1,541,890; candidate mean1,532,470 (-0.61%). All64 games were unfinished at cutoff. Fresh full games are needed to assess final scores and survival; training continues.',
    waiting_for='Fresh full-game source bindings and preflight',
    next_stage='New reference cohort, then candidate and independent confirmation',
    eta='No launch estimate until preflight; full games end naturally.',
    updated_unix_s=time.time(), observation_unix_s=time.time())

def cas(path, before, after):
    assert path.read_bytes() == before
    temporary = path.with_name(path.name + '.index187.tmp')
    with temporary.open('xb') as stream:
        stream.write(after)
        stream.flush()
        os.fsync(stream.fileno())
    assert path.read_bytes() == before
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)

cas(STATE, old, raw)
cas(DELL, db, f'Robotron recovery index187: {ip["path"]}\n{summary}\n\n'.encode() + db)
cas(PUBLIC, ub, (json.dumps(public, indent=2, allow_nan=False) + '\n').encode())
h.put(F / 'close_short8dae_and_select_fullgames.py', Path('/tmp/close_short8dae_and_select_fullgames.py').read_bytes())
print(json.dumps(dict(index=small(ip), next_fullgame_selection=small(selection), Main_clients=api['client_count'],
                      Main_learner_frames=api['learner_frame_count'], fleet_counts=fleet['counts'], state_bytes=len(raw))))
