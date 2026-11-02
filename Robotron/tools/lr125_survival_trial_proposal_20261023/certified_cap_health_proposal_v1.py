"""Prospective pure main-health classifier; not selected or integrated.

Only source-certified cap75 resets of unchanged original training processes may
explain a single connection dip. Callers must authenticate modules, source/control
holds, raw API, census and log bytes. This module performs no I/O and qualifies no
game, policy or learning window. Existing invalid attempts remain invalid.
"""
import ast
import copy
import hashlib
import math
import re

WINDOW_SHA = 'ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a'
LUA_SHA = '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf'
LIMITS = dict(max_episodes=4, max_episode_s=45, max_total_s=120, max_sample_gap_s=30,
              max_certificate_age_s=10, max_census_age_s=5)
CAP = '[WAVECAP] wave advance 74 -> 75 - soft reset (training-data rebalance)'
SLOTS = {str(i) for i in range(192)}


def require(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def api_guard(source):
    """Retain the original guard body; raw191 needs the separate certificate."""
    require(type(source) is bytes and hashlib.sha256(source).hexdigest() == WINDOW_SHA,
            'Exact reviewed LR125 API guard source required')
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'healthy')
    original = ast.get_source_segment(source.decode(), node)
    old = "api['client_count']==192 and"
    new = "type(api['client_count']) is int and api['client_count'] in (191,192) and"
    require(original.count(old) == 1, 'Original connection predicate boundary changed')
    effective = original.replace(old, new).replace('def healthy(', 'def _api_health(', 1)
    require(effective.replace(new, old).replace('def _api_health(', 'def healthy(', 1) == original,
            'Only connection-predicate/name specialization permitted')
    namespace = dict(require=require, math=math)
    exec(compile(effective, '<source-bound-API-predicates>', 'exec'), namespace)
    return namespace['_api_health']


class CapHealth:
    def __init__(self, supervision, policy, baseline_api, window_source, log_origins):
        require(set(log_origins) == SLOTS and all(set(v) == {'inode', 'offset'} and
            type(v['inode']) is int and v['inode'] > 0 and type(v['offset']) is int and v['offset'] >= 0
            for v in log_origins.values()), 'Exact initial192 log inode/cursors required')
        supervision.validate_policy(policy)
        self.sup = supervision
        self.policy = copy.deepcopy(policy)
        self.baseline = copy.deepcopy(baseline_api)
        self.experiment = baseline_api['managed_experiment']
        self.origins = copy.deepcopy(log_origins)
        self.guard = api_guard(window_source)

    def census(self, snapshot, api_count, clock):
        require(snapshot['schema'] == 'robotron-main-supervision-snapshot-v1'
            and type(api_count) is int and api_count in (191, 192), 'Unknown census or client count')
        for key, started, now in [('monotonic_s', 'collection_started_monotonic_s', clock['monotonic_s']),
                                  ('unix_s', 'collection_started_unix_s', clock['unix_s'])]:
            require(all(finite(v) and v > 0 for v in (snapshot[key], snapshot[started], now))
                and 0 <= snapshot[key] - snapshot[started] <= 5
                and 0 <= now - snapshot[key] <= 5, 'Slow, stale or invalid physical census')
        require(set(snapshot['owners']) == {'trainer', 'fleet'}, 'Both original owners required')
        for role in ('trainer', 'fleet'):
            self.sup.validate_owner(self.policy[role], snapshot['owners'][role])
            require(all(snapshot['owners'][role]['process'][key] ==
                self.policy['baseline_owners'][role]['process'][key] for key in self.sup.STATIC),
                'Original main owner configuration changed')
        actors, probes = snapshot['actors'], snapshot['previous_birth_probes']
        require(set(actors) == set(probes) == SLOTS
            and len({a['pid'] for a in actors.values()}) == 192, 'All192 original processes required')
        for slot, actor in actors.items():
            original = self.policy['baseline_actors'][slot]
            self.sup.validate_actor(slot, actor, original, self.policy['fleet'])
            require(self.sup.birth(actor) == self.sup.birth(original)
                and probes[slot] == original['starttime_ticks'], 'Actor replacement or missing original birth')

    def client_epochs(self, api):
        rows = api['client_rows']
        require(type(rows) is list and len(rows) == api['client_count'], 'Client count and row coverage differ')
        epochs, ids = {}, set()
        for row in rows:
            slot = row['client_slot']
            require(type(slot) is int and str(slot) in SLOTS and str(slot) not in epochs
                and type(row['client_id']) is int and row['client_id'] >= 0 and row['client_id'] not in ids
                and finite(row['connected_seconds']) and row['connected_seconds'] >= 0,
                'Unknown, duplicate or malformed client row')
            epochs[str(slot)] = api['ts'] - row['connected_seconds']
            ids.add(row['client_id'])
        return epochs

    def log_chunks(self, state, chunks, clock):
        for chunk in chunks:
            slot = chunk['slot']
            require(slot in SLOTS and type(chunk['raw']) is str, 'Original actor log chunk required')
            cursor = state['cursors'][slot]
            raw = chunk['raw'].encode()
            require(chunk['lua_sha256'] == LUA_SHA and chunk['inode'] == cursor['inode']
                and type(chunk['offset_start']) is int and chunk['offset_start'] == cursor['offset']
                and type(chunk['offset_end']) is int and chunk['offset_end'] == chunk['offset_start'] + len(raw)
                and 0 < len(raw) <= 256 << 10, 'Log inode/source/byte range changed or skipped')
            require(finite(chunk['monotonic_s']) and finite(chunk['unix_s'])
                and state['last_monotonic_s'] <= chunk['monotonic_s'] <= clock['monotonic_s']
                and state['last_unix_s'] <= chunk['unix_s'] <= clock['unix_s'], 'Log evidence clock outside observation')
            cursor['offset'] = chunk['offset_end']
            if CAP not in chunk['raw']:
                continue
            require(chunk['raw'].count(CAP) == 1, 'Ambiguous multiple cap events')
            tail = chunk['raw'].split(CAP, 1)[1]
            pid = self.policy['baseline_actors'][slot]['pid']
            markers = re.findall(r'\[robotron-socket-wait\] pid=(\d+) fd=\d+ port=9998 interval_us=1000', tail)
            require('MAME interface initialized.' in tail
                and 'Socket connection opened to socket.dell:9998' in tail
                and markers == [str(pid)], 'Cap must reinitialize/reconnect the same actual process')
            state['recent_caps'][slot] = dict(slot=slot, actor_pid=pid,
                actor_birth=self.policy['baseline_actors'][slot]['starttime_ticks'],
                monotonic_s=chunk['monotonic_s'], unix_s=chunk['unix_s'],
                raw_sha256=hashlib.sha256(raw).hexdigest(), inode=chunk['inode'],
                offset_start=chunk['offset_start'], offset_end=chunk['offset_end'])

    def observe(self, snapshot, api, clock, chunks=(), state=None):
        require(set(clock) == {'monotonic_s', 'unix_s'}
            and all(finite(v) and v > 0 for v in clock.values()), 'Exact positive observation clock required')
        self.census(snapshot, api['client_count'], clock)
        self.guard(api, self.baseline, self.experiment, clock['unix_s'])
        epochs = self.client_epochs(api)
        if state is None:
            require(api['client_count'] == 192 and set(epochs) == SLOTS and not chunks,
                    'Initial full capacity required; no cap exception at entry')
            return dict(schema='robotron-prospective-certified-cap-health-state-v1',
                last_monotonic_s=clock['monotonic_s'], last_unix_s=clock['unix_s'],
                cursors=copy.deepcopy(self.origins), recent_caps={}, used_slots=[], episodes=[],
                pending=None, total_charged_s=0., total_charged_wall_s=0., last_client_count=192,
                last_healthy_epochs=epochs, full_capacity=True)
        require(state['schema'] == 'robotron-prospective-certified-cap-health-state-v1'
            and 0 < clock['monotonic_s'] - state['last_monotonic_s'] <= LIMITS['max_sample_gap_s']
            and 0 < clock['unix_s'] - state['last_unix_s'] <= LIMITS['max_sample_gap_s'],
            'Observation gap or clock regression')
        updated = copy.deepcopy(state)
        self.log_chunks(updated, chunks, clock)
        pending = updated['pending']
        if api['client_count'] == 191:
            missing = SLOTS - set(epochs)
            require(len(missing) == 1, 'Exactly one identified missing connection required')
            slot = next(iter(missing))
            if pending is None:
                certificate = updated['recent_caps'].get(slot)
                require(certificate is not None and slot not in updated['used_slots']
                    and len(updated['used_slots']) < LIMITS['max_episodes']
                    and 0 <= clock['monotonic_s'] - certificate['monotonic_s'] <= LIMITS['max_certificate_age_s']
                    and 0 <= clock['unix_s'] - certificate['unix_s'] <= LIMITS['max_certificate_age_s'],
                    'Uncertified, expired, repeated-slot or over-budget connection gap')
                pending = dict(slot=slot, certificate=copy.deepcopy(certificate),
                    started_monotonic_s=state['last_monotonic_s'], started_unix_s=state['last_unix_s'],
                    first_bad_API_ts=api['ts'], previous_connection_epoch=state['last_healthy_epochs'][slot])
                updated['used_slots'].append(slot)
            require(slot == pending['slot'], 'Another missing slot during cap reconnect')
        if pending is not None:
            duration = clock['monotonic_s'] - pending['started_monotonic_s']
            wall = clock['unix_s'] - pending['started_unix_s']
            require(0 < duration <= LIMITS['max_episode_s'] and 0 < wall <= LIMITS['max_episode_s']
                and updated['total_charged_s'] + duration <= LIMITS['max_total_s']
                and updated['total_charged_wall_s'] + wall <= LIMITS['max_total_s'],
                'Cap reconnect duration or whole-study capacity budget exceeded')
            if api['client_count'] == 192:
                epoch = epochs[pending['slot']]
                require(epoch >= pending['first_bad_API_ts'] - 5
                    and epoch - pending['previous_connection_epoch'] >= 1,
                    'Full capacity returned without a fresh matching connection')
                updated['episodes'].append(dict(pending, ended_monotonic_s=clock['monotonic_s'],
                    ended_unix_s=clock['unix_s'], charged_s=duration, charged_wall_s=wall,
                    restored_connection_epoch=epoch))
                updated['total_charged_s'] += duration
                updated['total_charged_wall_s'] += wall
                pending = None
        if api['client_count'] == 192:
            require(set(epochs) == SLOTS, 'Full192 coverage required')
            updated['last_healthy_epochs'] = epochs
        updated.update(pending=pending, last_monotonic_s=clock['monotonic_s'],
            last_unix_s=clock['unix_s'], last_client_count=api['client_count'],
            full_capacity=pending is None and api['client_count'] == 192)
        return updated


def closed_summary(state):
    require(state['pending'] is None and state['full_capacity'] is True
        and state['last_client_count'] == 192, 'A case must finish with all192 connections')
    return dict(episodes=copy.deepcopy(state['episodes']), total_charged_s=state['total_charged_s'],
                total_charged_wall_s=state['total_charged_wall_s'], used_slots=list(state['used_slots']))


def combine_closed_legs(summaries):
    """Case-wide budget is cumulative; preparing another leg cannot reset it."""
    episodes = [e for summary in summaries for e in summary['episodes']]
    slots = [e['slot'] for e in episodes]
    mono = sum(e['charged_s'] for e in episodes)
    wall = sum(e['charged_wall_s'] for e in episodes)
    require(len(episodes) <= LIMITS['max_episodes'] and len(set(slots)) == len(slots)
        and all(finite(e['charged_s']) and finite(e['charged_wall_s'])
            and 0 < e['charged_s'] <= LIMITS['max_episode_s']
            and 0 < e['charged_wall_s'] <= LIMITS['max_episode_s'] for e in episodes)
        and mono <= LIMITS['max_total_s'] and wall <= LIMITS['max_total_s'],
        'Combined case cap-reset count, slot reuse or capacity duration exceeds fixed budget')
    return dict(episodes=copy.deepcopy(episodes), total_charged_s=mono, total_charged_wall_s=wall,
                used_slots=slots, full_capacity_at_all_leg_ends=True)
