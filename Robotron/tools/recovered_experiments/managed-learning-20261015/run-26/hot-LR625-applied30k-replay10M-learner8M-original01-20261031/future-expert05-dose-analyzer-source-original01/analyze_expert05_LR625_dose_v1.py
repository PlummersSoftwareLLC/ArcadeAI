"""Pure expert5% at LR625 dose analysis; no observations, control writes or actions."""
from math import isfinite, isclose
OWNER = {'pid': 208501, 'birth': 27823352}
TARGETS = {'applied_updates': 60000, 'replay_additions': 20000000, 'learner_frames': 16000000}
OP = {'attempted': 'attempts_started', 'outcomes': 'outcomes_recorded', 'applied': 'applied', 'skipped': 'amp_skipped', 'unavailable': 'unavailable'}
SRC = ('dqn', 'epsilon', 'expert', 'eval', 'unattributed')
IDS = ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')

class Rejected(ValueError):
  pass

def need(ok, reason):
  if not ok: raise ValueError(reason)

def number(x):
  need(type(x) in (int, float) and isfinite(x), 'Invalid number/time')
  return x

def integer(x):
  need(type(x) is int and x >= 0, 'Invalid nonnegative counter')
  return x

def identity(x):
  v = {k: x[k] for k in IDS}
  for k in IDS[:3]: integer(v[k])
  need(v['instance_monotonic_ns'] > 0 and type(v['epoch_reason']) is str and bool(v['epoch_reason']), 'Invalid identity')
  return v

def sha(x):
  need(type(x) is str and len(x) == 64 and all(c in '0123456789abcdef' for c in x), 'Missing/invalid control SHA')
  return x

def checked(c):
  for k in (*OP, 'replay', 'replay_learner', 'learner_frames', 'training_steps'): integer(c[k])
  need(type(c['source']) is dict and set(c['source']) == set(SRC), 'Replay categories missing')
  for k in SRC: integer(c['source'][k])
  need(c['outcomes'] == c['applied'] + c['skipped'] + c['unavailable'] and c['attempted'] - c['outcomes'] in (0, 1), 'Optimizer accounting invalid')
  need(sum(c['source'].values()) == c['replay'] and c['source']['dqn'] + c['source']['epsilon'] == c['replay_learner'], 'Replay accounting invalid')
  return c

def counters(api):
  e = api['host_pipeline']['learning_exposure']; o, r = e['optimizer'], e['replay']
  return checked(dict(**{k: o['total'][v] for k, v in OP.items()}, replay=r['accepted_total'], replay_learner=r['accepted_learner_total'], source=dict(r['accepted_by_source_total']), learner_frames=api['learner_frame_count'], training_steps=api['training_steps']))

def flat(c):
  return [*(c[k] for k in (*OP, 'replay', 'replay_learner', 'learner_frames', 'training_steps')), *(c['source'][k] for k in SRC)]

def result(status, reason):
  return dict(status=status, reason=reason, all_reached=False, estimated_remaining_s=None, estimated_completion_unix_s=None, mutation_or_quality_authorized=False)

def analyze(anchor, sample):
  """Optional sample.previous={counters,api_ts} uses the prior VALID output."""
  try:
    need(anchor['schema'] == 'robotron-LR625-expert05-dose-anchor-v1' and anchor['main_owner'] == OWNER, 'Wrong anchor/Main')
    need(anchor['targets'] == TARGETS and all(type(v) is int for v in anchor['targets'].values()), 'Wrong targets')
    need(type(anchor['expected_lr']) in (int, float) and anchor['expected_lr'] == 6.25e-6, 'Wrong LR')
    need(type(anchor['expected_expert']) in (int, float) and anchor['expected_expert'] == 0.05, 'Wrong expert ratio')
    need(type(anchor['expected_epsilon']) in (int, float) and anchor['expected_epsilon'] == 0.1, 'Wrong epsilon')
    control = sha(anchor['control_sha256']); start = number(anchor['observed_unix_s']); base_ts = number(anchor['api_ts'])
    need(0 < base_ts <= start, 'Invalid anchor time')
    ids = {k: identity(anchor[k + '_identity']) for k in ('optimizer', 'replay')}
    need(all(v['process_id'] == OWNER['pid'] for v in ids.values()), 'Wrong counter owner')
    base = checked(anchor['base']); need(base['attempted'] == base['outcomes'], 'Anchor must be settled')
  except (KeyError, TypeError, ValueError) as e:
    return result('REJECTED', 'Invalid anchor: ' + str(e))
  try:
    owner = sample['observed_main_owner']
    need(type(owner) is dict and all(type(owner[k]) is int for k in ('pid', 'birth')), 'Owner observation missing')
    if owner != OWNER or sha(sample['observed_control_sha256']) != control: raise Rejected('Main owner/control SHA changed')
    api, policy = sample['api_now'], sample['continuous_policy']
    if policy['consumer_error'] is not None: raise Rejected('Replay consumer error')
    if {k: policy['server_stamp'][k] for k in OWNER} != OWNER: raise Rejected('Policy owner changed')
    e = api['host_pipeline']['learning_exposure']; o, r = e['optimizer'], e['replay']
    for k in ids:
      if identity(e[k]) != ids[k]: raise Rejected(k + ' process/epoch changed')
    if integer(o['total']['unavailable']) > base['unavailable']: raise Rejected('New unavailable outcome')
    now = number(sample['observed_unix_s']); ts = number(api['ts']); previous = sample.get('previous')
    if previous is not None: base_ts = max(base_ts, number(previous['api_ts']))
    need(ts > base_ts and now > start and 0 <= now - ts <= 10 and 0 <= now - number(policy['observed_unix_s']) <= 10, 'Cached/stale observation')
    c = counters(api)
    if any(a < b for a, b in zip(flat(c), flat(base))): raise Rejected('Counter decreased from anchor')
    if previous is not None and any(a < b for a, b in zip(flat(c), flat(checked(previous['counters'])))): raise Rejected('Counter decreased from previous')
    need(api['pipeline_read_error'] == api['bank_persistence_read_error'] == '' and api['host_pipeline']['available'] is True and 0 <= number(api['pipeline_snapshot_age_s']) <= 10, 'Pipeline stale/error')
    need(o['schema'] == 'robotron-optimizer-exposure-v1' and r['schema'] == 'robotron-replay-insert-exposure-v1' and o['enabled'] is r['enabled'] is r['available'] is True, 'Exposure unavailable')
    pending = c['attempted'] - c['outcomes']
    need(integer(o['unclassified_started_total']) == pending and integer(o['prior_epoch_outcomes_total']) == 0, 'Pending accounting invalid')
    if pending == 1:
      need(o['available'] is False, 'Pending availability invalid')
      return result('PENDING', 'One supported in-flight optimizer outcome; resample')
    need(o['available'] is True, 'Optimizer not settled')
    need(api['training_enabled'] is policy['training_enabled'] is policy['replay_admission_open'] is True and api['measurement_active'] is policy['measurement_active'] is False and policy['continuous_training_mode'] is policy['main_measurement_entry_disabled'] is True, 'Main not learning')
    need(isclose(number(api['lr']), anchor['expected_lr'], rel_tol=1e-9, abs_tol=0), 'Selected LR not observed')
    expert_pct = api['game_settings']['expert_pct']
    need(type(expert_pct) is int, 'Expert override observation unavailable')
    if expert_pct != 5 or not isclose(number(api['expert_ratio']), anchor['expected_expert'], rel_tol=1e-9, abs_tol=1e-12):
      raise Rejected('Selected manual expert5% setting changed')
    if not isclose(number(api['epsilon']), anchor['expected_epsilon'], rel_tol=1e-9, abs_tol=1e-12):
      raise Rejected('Selected epsilon changed')
    if policy.get('ratchet_frozen') is not False: raise Rejected('Main ratchet state changed')
    elapsed = now - start
    d = dict(applied_updates=c['applied'] - base['applied'], replay_additions=c['replay'] - base['replay'], learner_frames=c['learner_frames'] - base['learner_frames'])
    remaining = {k: max(0, TARGETS[k] - d[k]) for k in TARGETS}; rates = {k: d[k] / elapsed for k in TARGETS}
    eta = max(remaining[k] / rates[k] for k in TARGETS) if elapsed >= 120 and all(v > 0 for v in rates.values()) else None
    if eta is not None and not isfinite(now + eta): eta = None
    out = result('VALID', 'Dose arithmetic only')
    out.update(deltas=d, remaining=remaining, all_reached=not any(remaining.values()), elapsed_s=elapsed, rates_per_s=rates, estimated_remaining_s=eta, estimated_completion_unix_s=None if eta is None else now + eta, counters=c, api_ts=ts)
    return out
  except Rejected as e:
    return result('REJECTED', str(e))
  except (KeyError, TypeError, ValueError, OverflowError) as e:
    return result('PENDING', str(e))
