#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN SMOKE TEST                                                                               ||
# ||  End-to-end validation: action coding, slicing, wire round-trip, model shapes, train_step, socket loop.     ||
# ==================================================================================================================
"""Standalone smoke test for the Robotron joint DQN.

Run from Robotron/Scripts:
    python3 -m dqn.test_smoke
or:
    python3 dqn/test_smoke.py
"""

import os
import sys
import socket
import struct
import threading
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from dqn import config as C
from dqn import model as M
from dqn.agent import RainbowAgent
from dqn.nstep_buffer import NStepReplayBuffer
from dqn import socket_server as SS


_PASS = 0
_FAIL = 0


def check(name, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {name}")
    else:
        _FAIL += 1
        print(f"  FAIL  {name}   {detail}")


# ── Wire helpers (mirror the Lua client) ────────────────────────────────────
def make_payload(state: np.ndarray, *, subj=0.0, obj=0.0, done=0, score=0,
                 alive=1, save=0, start=0, replay=0, lasers=0, wave=1) -> bytes:
    n = int(state.shape[0])
    hdr = struct.pack(SS._HDR_FMT, n, float(subj), float(obj), int(done),
                      int(score), int(alive), int(save), int(start),
                      int(replay), int(lasers), int(wave))
    body = state.astype(">f4").tobytes()
    return hdr + body


def framed(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload


def fake_wire(wave=1) -> np.ndarray:
    w = np.zeros(C.WIRE_PARAMS_COUNT, dtype=np.float32)
    # Plausible core fields so the expert doesn't choke.
    w[5] = 0.5      # player x
    w[6] = 0.5      # player y
    w[9] = 0.8      # nearest enemy dist
    w[10] = 0.7     # nearest human dist
    w[13] = 0.1     # humans-present proxy
    # A little signal in the legacy lane block. The current DQN slice ignores
    # it, but the expert/debug paths still consume the full wire.
    w[C.TACTICAL_LANE_OFFSET:C.TACTICAL_LANE_END] = np.random.rand(
        C.TACTICAL_LANE_END - C.TACTICAL_LANE_OFFSET).astype(np.float32) * 0.1
    return w


def stack_state(single_state: np.ndarray, depth: int | None = None) -> np.ndarray:
    depth = C.RL_CONFIG.frame_stack if depth is None else int(depth)
    return np.concatenate([np.asarray(single_state, dtype=np.float32)] * max(1, depth)).astype(np.float32)


def add_pool_slot(w: np.ndarray, pool_name: str, slot_idx: int, values: list[float]) -> None:
    off = C.TACTICAL_POOL_OFFSET
    for name, max_slots, feat_per_slot in C.TACTICAL_POOL_DEFS:
        if name == pool_name:
            base = off + 1 + int(slot_idx) * feat_per_slot
            w[off] = max(w[off], 1.0 / max(1, max_slots))
            vals = list(values[:feat_per_slot])
            vals += [0.0] * (feat_per_slot - len(vals))
            w[base:base + feat_per_slot] = np.asarray(vals, dtype=np.float32)
            return
        off += 1 + max_slots * feat_per_slot
    raise ValueError(pool_name)


# ── Unit tests ──────────────────────────────────────────────────────────────
def test_action_coding():
    print("\n[action coding]")
    ok = True
    for mv in range(M.NUM_MOVE):
        for fr in range(M.NUM_FIRE):
            j = M.combine_action(mv, fr)
            m2, f2 = M.split_joint_action(j)
            if (m2, f2) != (mv, fr) or not (0 <= j < M.NUM_JOINT):
                ok = False
    check("combine/split round-trip (all 81)", ok)
    check("idle index maps 8 -> -1", M.action_index_to_wire_dir(8) == -1)
    check("dir 0..7 passthrough", all(M.action_index_to_wire_dir(d) == d for d in range(8)))
    check("wire_dir -1 -> 8", M.wire_dir_to_action_index(-1) == 8)


def test_slice():
    print("\n[state slice]")
    w = np.zeros(C.WIRE_PARAMS_COUNT, dtype=np.float32)
    w[:C.GLOBAL_FEATURES] = np.arange(C.GLOBAL_FEATURES, dtype=np.float32)
    add_pool_slot(w, "destructible", 3, [1.0, 0.25, -0.50, 0.20, 0.05, -0.10, 0.80, 0.40, 0.30, 0.25])
    add_pool_slot(w, "destructible", 0, [1.0, -0.10, 0.10, 0.08, 0.0, 0.0, 0.90, 0.50, 0.20, 0.75])
    add_pool_slot(w, "hulk", 0, [1.0, 0.50, 0.0, 0.12, 0.0, 0.0, 0.7, 0.0, 1.0, 0.125])
    add_pool_slot(w, "obstacle", 0, [1.0, -0.75, -0.75, 0.10, 0.0, 0.0, 0.6, 0.0, 1.0, 1.0])
    add_pool_slot(w, "human", 0, [1.0, 0.75, 0.75, 0.10, 0.0, 0.0, 0.0, 0.0, 1.0, 0.875])
    ms = C.slice_model_state(w)
    check("slice length == SINGLE_FRAME_STATE_SIZE", ms.shape[0] == C.SINGLE_FRAME_STATE_SIZE)
    check("MODEL_STATE_SIZE includes frame stack",
          C.MODEL_STATE_SIZE == C.SINGLE_FRAME_STATE_SIZE * C.RL_CONFIG.frame_stack)
    cs = {}
    s1 = np.ones(C.SINGLE_FRAME_STATE_SIZE, dtype=np.float32)
    s2 = np.full(C.SINGLE_FRAME_STATE_SIZE, 2.0, dtype=np.float32)
    stk1 = SS.SocketServer._stack_model_state(cs, s1)
    stk2 = SS.SocketServer._stack_model_state(cs, s2)
    check("frame stack width", stk2.shape[0] == C.MODEL_STATE_SIZE)
    check("frame stack first frame fills history",
          np.allclose(stk1[:C.SINGLE_FRAME_STATE_SIZE], s1))
    check("frame stack current first", np.allclose(stk2[:C.SINGLE_FRAME_STATE_SIZE], s2))
    if C.RL_CONFIG.frame_stack >= 2:
        start = C.SINGLE_FRAME_STATE_SIZE
        end = start + C.SINGLE_FRAME_STATE_SIZE
        check("frame stack previous second", np.allclose(stk2[start:end], s1))
    check("core[0] preserved", ms[0] == w[0])
    check("core[17] preserved", ms[17] == w[17])
    check("elist[18] preserved", ms[18] == w[18])
    check("elist[39] preserved", ms[39] == w[39])
    check("enemy block starts after globals", C.ENEMY_TOKEN_OFFSET == C.GLOBAL_FEATURES)
    check("enemy block size", ms.shape[0] - C.ENEMY_TOKEN_OFFSET == C.ENEMY_FEATURES)
    enemies = ms[C.ENEMY_TOKEN_OFFSET:C.ENEMY_TOKEN_END].reshape(C.ENEMY_TOKEN_COUNT, C.ENEMY_TOKEN_FEATURES)
    near = np.asarray([1.0, -0.10, 0.10, 0.08, 0.0, 0.0, 0.90, 0.50, 0.20, 0.75], dtype=np.float32)
    far = np.asarray([1.0, 0.25, -0.50, 0.20, 0.05, -0.10, 0.80, 0.40, 0.30, 0.25], dtype=np.float32)
    check("destructible rows distance-sort nearest first", np.allclose(enemies[0], near), f"row0={enemies[0]}")
    check("destructible group keeps farther row second", np.allclose(enemies[1], far), f"row1={enemies[1]}")
    hulk_start = C.TOKEN_GROUP_RANGES["hulk"][0]
    obstacle_start = C.TOKEN_GROUP_RANGES["obstacle"][0]
    human_start = C.TOKEN_GROUP_RANGES["human"][0]
    check("hulk group starts after destructibles", enemies[hulk_start, 9] == 0.125, f"row={enemies[hulk_start]}")
    check("obstacle group included in model state", enemies[obstacle_start, 9] == 1.0, f"row={enemies[obstacle_start]}")
    check("human group included in model state", enemies[human_start, 9] == 0.875, f"row={enemies[human_start]}")
    check("all four groups contribute active rows",
          int(np.count_nonzero(enemies[:, 0] > 0.5)) == 5)


def test_nstep_actor_boundaries():
    print("\n[n-step actor boundaries]")
    nbuf = NStepReplayBuffer(n_step=12, gamma=0.5)
    s0 = np.array([0], dtype=np.float32)
    s1 = np.array([1], dtype=np.float32)
    s2 = np.array([2], dtype=np.float32)
    s3 = np.array([3], dtype=np.float32)
    out = []
    out += nbuf.add(s0, 0, 1.0, s1, False, actor="dqn")
    out += nbuf.add(s1, 1, 2.0, s2, False, actor="epsilon")
    out += nbuf.add(s2, 2, 4.0, s3, False, actor="expert")
    check("actor switch flushes learner prefix", len(out) == 2, f"len={len(out)}")
    if len(out) >= 2:
        check("dqn+epsilon grouped as learner", out[0][2] == 2.0 and out[0][6] == 2,
              f"R={out[0][2]} h={out[0][6]}")
        check("boundary does not include expert reward", out[1][2] == 2.0 and out[1][6] == 1,
              f"R={out[1][2]} h={out[1][6]}")

        nbuf2 = NStepReplayBuffer(n_step=3, gamma=0.5)
        out2 = []
        out2 += nbuf2.add(s0, 0, 1.0, s1, False, actor="dqn", interest=0.2)
        out2 += nbuf2.add(s1, 1, 1.0, s2, False, actor="dqn", interest=0.8)
        out2 += nbuf2.add(s2, 2, 1.0, s3, False, actor="dqn", interest=0.4)
        check("n-step carries max interest", len(out2) == 1 and np.isclose(out2[0][8], 0.8),
            f"out={out2}")


def test_parse_roundtrip():
    print("\n[wire parse round-trip]")
    w = fake_wire(wave=7)
    payload = make_payload(w, subj=1.5, obj=-3.0, done=0, score=4242, alive=1, wave=7)
    frame = SS.parse_frame_data(payload)
    check("parse returns a frame", frame is not None)
    if frame is not None:
        check("state length preserved", frame.state.shape[0] == C.WIRE_PARAMS_COUNT)
        check("subjreward parsed", abs(frame.subjreward - 1.5) < 1e-5)
        check("objreward parsed", abs(frame.objreward - (-3.0)) < 1e-5)
        check("score parsed", frame.game_score == 4242)
        check("wave parsed", frame.level_number == 7)
        check("alive parsed", frame.player_alive is True)
        check("state[5] preserved", abs(float(frame.state[5]) - 0.5) < 1e-4)
    bad = SS.parse_frame_data(b"\x00\x01")
    check("short payload -> None", bad is None)


def test_fire_hold():
    print("\n[fire hold]")
    n = SS.FIRE_HOLD_FRAMES
    check("hold frames >= 1", n >= 1)

    # First request latches immediately, then is held for n frames.
    cs = {}
    requests = [2] + [5] * n
    effective = [SS._apply_fire_hold(cs, r) for r in requests]
    check("first frame fires requested dir", effective[0] == 2)
    check(f"direction held for {n} frames", effective[:n] == [2] * n,
          f"got {effective[:n]}")
    check("new direction accepted after hold expires", effective[n] == 5)

    # Idle (8) is held just like any other direction.
    cs2 = {}
    eff_idle = [SS._apply_fire_hold(cs2, 8) for _ in range(n)]
    check("idle held cleanly", all(e == 8 for e in eff_idle))

    # The locked-fire read used by the socket loop mirrors the held direction
    # while the hold window is still open.
    cs3 = {}
    SS._apply_fire_hold(cs3, 3)
    fire_update_open = cs3.get("fire_hold_count", 0) <= 0
    held = cs3.get("fire_hold_dir", -1)
    locked = max(0, min(8, held)) if held >= 0 else 8
    check("hold window open flag correct", (n == 1) == fire_update_open)
    check("locked fire mirrors held dir", locked == 3)


def test_reward_and_hard_starts():
    print("\n[reward + hard starts]")
    frame = SS.FrameData(
        state=fake_wire(), subjreward=100.0, objreward=-5000.0,
        done=False, player_alive=True, save_signal=False, start_pressed=False,
        level_number=1, game_score=5000, num_lasers=0)
    total, score_r, subj_r, death_r, score_delta = SS._shape_transition_reward(frame, last_game_score=0)
    check("5000 score delta maps to reward 5.0", np.isclose(score_r, 5.0), f"score_r={score_r}")
    check("subjective shaping is ignored", np.isclose(subj_r, 0.0), f"subj_r={subj_r}")
    check("5000 score delta is not clipped", np.isclose(total, 5.0), f"total={total}")
    frame2 = SS.FrameData(
        state=fake_wire(), subjreward=0.0, objreward=0.0,
        done=False, player_alive=True, save_signal=False, start_pressed=False,
        level_number=1, game_score=1000, num_lasers=0)
    _, score_r2, _, _, _ = SS._shape_transition_reward(frame2, last_game_score=0)
    check("1000 score delta maps to reward 1.0", np.isclose(score_r2, 1.0), f"score_r={score_r2}")
    dead_frame = SS.FrameData(
        state=fake_wire(), subjreward=-100.0, objreward=-5000.0,
        done=True, player_alive=False, save_signal=False, start_pressed=False,
        level_number=1, game_score=0, num_lasers=0)
    dead_total, _, dead_subj, dead_r, _ = SS._shape_transition_reward(dead_frame, last_game_score=0)
    check("negative subjective shaping is ignored", np.isclose(dead_subj, 0.0), f"subj_r={dead_subj}")
    check("death penalty is -5000 points", np.isclose(dead_r, -5.0), f"death_r={dead_r}")
    check("terminal no-score reward is death only", np.isclose(dead_total, -5.0), f"total={dead_total}")

    old_start_adv = C.game_settings.start_advanced
    old_auto = C.game_settings.auto_curriculum
    old_level = C.game_settings.start_level_min
    try:
        C.game_settings.start_advanced = False
        C.game_settings.auto_curriculum = True
        C.game_settings.start_level_min = 1
        server = SS.SocketServer("127.0.0.1", 19997, None, C.metrics)
        _, _, _, sadv, slvl = struct.unpack(">bbBBB", server._pack_action(-1, -1, 0, cid=3))
        check("auto curriculum enables advanced starts", sadv == 1, f"sadv={sadv}")
        expected = C.RL_CONFIG.hard_start_min_level + (3 % C.RL_CONFIG.hard_start_wave_spread)
        check("hard starts spread by client id", slvl == expected, f"slvl={slvl} expected={expected}")
        C.game_settings.start_advanced = True
        C.game_settings.auto_curriculum = False
        C.game_settings.start_level_min = 3
        _, _, _, sadv, slvl = struct.unpack(">bbBBB", server._pack_action(-1, -1, 0, cid=7))
        check("manual advanced start uses selected level exactly", sadv == 1 and slvl == 3,
              f"sadv={sadv} slvl={slvl}")
    finally:
        C.game_settings.start_advanced = old_start_adv
        C.game_settings.auto_curriculum = old_auto
        C.game_settings.start_level_min = old_level


def test_score_level_1m_metrics():
    print("\n[score/level 1M metrics]")
    m = C.MetricsData()
    m.score_1m_window = 3
    m.level_1m_window = 3

    m.note_game_score(10, 1)
    m.note_game_score(20, 2)
    m.note_game_score(30, 3)
    check("Scr1M averages initial window", np.isclose(m.score_1m_average, 20.0),
          f"avg={m.score_1m_average}")
    check("Lvl1M averages initial window", np.isclose(m.level_1m_average, 2.0),
          f"avg={m.level_1m_average}")

    m.note_game_score(40, 4)
    check("Scr1M evicts oldest sample", np.isclose(m.score_1m_average, 30.0),
          f"avg={m.score_1m_average}")
    check("Lvl1M evicts oldest sample", np.isclose(m.level_1m_average, 3.0),
          f"avg={m.level_1m_average}")

    m.note_game_state_averages(99.0, 888.0)
    check("live average score remains separate", np.isclose(m.average_game_score, 888.0),
          f"live={m.average_game_score}")
    check("live average level remains separate", np.isclose(m.average_level, 99.0),
          f"live={m.average_level}")
    check("live averages do not overwrite Scr1M", np.isclose(m.score_1m_average, 30.0),
          f"avg={m.score_1m_average}")
    check("live averages do not overwrite Lvl1M", np.isclose(m.level_1m_average, 3.0),
          f"avg={m.level_1m_average}")

    m.note_game_score(50)
    check("score-only update leaves Lvl1M unchanged", np.isclose(m.level_1m_average, 3.0),
          f"avg={m.level_1m_average}")
    check("score-only update still updates Scr1M", np.isclose(m.score_1m_average, 40.0),
          f"avg={m.score_1m_average}")


def test_transition_interest_policy():
    print("\n[transition interest]")

    def model_state(wave: int, enemy_row: list[float] | None = None):
        s = np.zeros(C.MODEL_STATE_SIZE, dtype=np.float32)
        s[4] = max(0, min(40, int(wave))) / 40.0
        if enemy_row is not None:
            vals = list(enemy_row[:C.ENEMY_TOKEN_FEATURES])
            vals += [0.0] * (C.ENEMY_TOKEN_FEATURES - len(vals))
            start = C.ENEMY_TOKEN_OFFSET
            s[start:start + C.ENEMY_TOKEN_FEATURES] = np.asarray(vals, dtype=np.float32)
        return s

    def frame(wave: int, done=False):
        return SS.FrameData(
            state=fake_wire(wave=wave), subjreward=0.0, objreward=0.0,
            done=bool(done), player_alive=True, save_signal=False,
            start_pressed=False, level_number=int(wave), game_score=0,
            num_lasers=0)

    threshold = C.RL_CONFIG.interesting_replay_min_score
    quiet = SS._transition_interest_score(model_state(10), model_state(10), frame(10), 0.0, 0.0)
    check("quiet deep wave is not interesting", quiet < threshold, f"score={quiet:.3f}")
    distant = SS._transition_interest_score(
        model_state(10), model_state(10, [1.0, 0.9, 0.0, 0.95, 0.0, 0.0, 0.2, 0.0, 1.0, 0.0]),
        frame(10), 0.0, 0.0)
    check("distant enemy is not interesting", distant < threshold, f"score={distant:.3f}")
    target = SS._transition_interest_score(
        model_state(10), model_state(10, [1.0, 0.02, 0.0, 0.02, 0.0, 0.0, 1.0, 0.7, 0.0, 0.0]),
        frame(10), 0.0, 0.0)
    check("near threatening enemy is interesting", target >= threshold, f"score={target:.3f}")
    scored = SS._transition_interest_score(model_state(4), model_state(4), frame(4), 5.0, 5.0)
    check("rescue-sized score burst is interesting", scored >= threshold, f"score={scored:.3f}")
    terminal = SS._transition_interest_score(model_state(4), model_state(4), frame(4, done=True), 0.0, -1.0)
    check("terminal transition is interesting", terminal >= threshold, f"score={terminal:.3f}")
    advanced = SS._transition_interest_score(model_state(5), model_state(6), frame(6), 0.0, 0.0)
    check("wave advance is interesting", advanced >= threshold, f"score={advanced:.3f}")


def test_legacy_interest_sanitizer():
    print("\n[legacy interest sanitizer]")
    from dqn.replay_buffer import PrioritizedReplayBuffer

    saved_frac = C.RL_CONFIG.max_interesting_replay_fraction
    saved_over_cap = C.RL_CONFIG.interesting_replay_over_cap_min_score
    C.RL_CONFIG.max_interesting_replay_fraction = 0.20
    C.RL_CONFIG.interesting_replay_over_cap_min_score = 0.95
    try:
        capped = PrioritizedReplayBuffer(capacity=100, state_size=C.MODEL_STATE_SIZE)
        s = np.zeros(C.MODEL_STATE_SIZE, dtype=np.float32)
        for _ in range(100):
            capped.add(s, 0, 0.0, s, False, interest=0.6)
        capped_stats = capped.get_partition_stats()
        check("interest admission is capped", capped_stats.get("interesting", 0) <= 20,
              f"stats={capped_stats}")

        buf = PrioritizedReplayBuffer(capacity=100, state_size=C.MODEL_STATE_SIZE)
        for i in range(100):
            buf.add(s, 0, 0.01, s, False, interest=0.0)
        buf.interesting[:100] = 0.9
        buf._n_interesting = 100
        buf.dones[5] = 1.0
        buf.rewards[6] = 5.0
        buf._sanitize_interesting_after_load_locked(100, verbose=False)
        kept = int(np.count_nonzero(buf.interesting[:100] > 0.0))
        check("legacy broad interest is capped", kept <= 20, f"kept={kept}")
        check("terminal flag survives sanitizer", buf.interesting[5] > 0.0)
        check("score burst survives sanitizer", buf.interesting[6] > 0.0)
    finally:
        C.RL_CONFIG.max_interesting_replay_fraction = saved_frac
        C.RL_CONFIG.interesting_replay_over_cap_min_score = saved_over_cap


def test_pre_death_reward_penalty():
    print("\n[pre-death reward penalty]")
    from dqn.replay_buffer import PrioritizedReplayBuffer

    cfg = C.RL_CONFIG
    saved = (
        cfg.pre_death_reward_lookback,
        cfg.pre_death_base_penalty,
        cfg.pre_death_danger_penalty,
        cfg.pre_death_max_penalty,
        cfg.pre_death_min_danger,
        cfg.pre_death_penalize_expert,
    )
    try:
        default_buf = PrioritizedReplayBuffer(capacity=4, state_size=C.MODEL_STATE_SIZE)
        s0 = np.zeros(C.MODEL_STATE_SIZE, dtype=np.float32)
        default_buf.add(s0, 0, 0.0, s0, False, expert=0)
        default_changed = default_buf.apply_pre_death_penalty([0])
        check("pre-death reward penalty disabled by default",
              default_changed == 0 and np.isclose(default_buf.rewards[0], 0.0),
              f"changed={default_changed} reward={default_buf.rewards[0]}")

        cfg.pre_death_reward_lookback = 4
        cfg.pre_death_base_penalty = 0.10
        cfg.pre_death_danger_penalty = 0.40
        cfg.pre_death_max_penalty = 0.50
        cfg.pre_death_min_danger = 0.0
        cfg.pre_death_penalize_expert = False

        buf = PrioritizedReplayBuffer(capacity=8, state_size=C.MODEL_STATE_SIZE)
        idxs = []
        for i, danger in enumerate([0.0, 0.0, 0.25, 0.75, 1.0]):
            s = np.zeros(C.MODEL_STATE_SIZE, dtype=np.float32)
            start = C.ENEMY_TOKEN_OFFSET
            s[start:start + C.ENEMY_TOKEN_FEATURES] = np.asarray([
                1.0, 0.0, 0.0, 0.20, 0.0, 0.0, float(danger), 0.0, 1.00, 0.0
            ], dtype=np.float32)
            buf.add(s, 0, 0.0, s, False, expert=0)
            idxs.append(i)
        changed = buf.apply_pre_death_penalty(idxs)
        check("pre-death penalty applies to lookback window", changed == 4, f"changed={changed}")
        check("oldest outside lookback is unchanged", np.isclose(buf.rewards[0], 0.0),
              f"r0={buf.rewards[0]}")
        check("dangerous recent frame gets stronger penalty", buf.rewards[4] < buf.rewards[1],
              f"r1={buf.rewards[1]} r4={buf.rewards[4]}")

        expert_buf = PrioritizedReplayBuffer(capacity=4, state_size=C.MODEL_STATE_SIZE)
        s = np.zeros(C.MODEL_STATE_SIZE, dtype=np.float32)
        start = C.ENEMY_TOKEN_OFFSET
        s[start:start + C.ENEMY_TOKEN_FEATURES] = np.asarray([
            1.0, 0.0, 0.0, 0.20, 0.0, 0.0, 1.0, 0.0, 1.00, 0.0
        ], dtype=np.float32)
        expert_buf.add(s, 0, 0.0, s, False, expert=1)
        skipped = expert_buf.apply_pre_death_penalty([0])
        check("pre-death penalty skips expert by default", skipped == 0 and np.isclose(expert_buf.rewards[0], 0.0),
              f"skipped={skipped} reward={expert_buf.rewards[0]}")
    finally:
        (
            cfg.pre_death_reward_lookback,
            cfg.pre_death_base_penalty,
            cfg.pre_death_danger_penalty,
            cfg.pre_death_max_penalty,
            cfg.pre_death_min_danger,
            cfg.pre_death_penalize_expert,
        ) = saved


def test_expert_anchor_decay():
    print("\n[expert anchor decay]")
    from dqn.training import _bc_weight_schedule, _margin_weight_schedule, _q_policy_weight_schedule
    cfg = C.RL_CONFIG

    # BC weight decays from start to its floor over the configured step window.
    bc_start = _bc_weight_schedule(0)
    bc_end = _bc_weight_schedule(cfg.expert_bc_decay_start_step + cfg.expert_bc_decay_steps + 10_000)
    check("bc weight starts at configured weight", np.isclose(bc_start, cfg.expert_bc_weight),
          f"bc_start={bc_start}")
    check("bc weight decays to floor", np.isclose(bc_end, cfg.expert_bc_min_weight),
          f"bc_end={bc_end}")

    # Direct Q-policy imitation trains the acting head, then decays to 0.
    q_start = _q_policy_weight_schedule(0)
    q_mid = _q_policy_weight_schedule(cfg.expert_q_policy_decay_start_step + cfg.expert_q_policy_decay_steps // 2)
    q_end = _q_policy_weight_schedule(cfg.expert_q_policy_decay_start_step + cfg.expert_q_policy_decay_steps + 10_000)
    check("q-policy weight starts at configured weight", np.isclose(q_start, cfg.expert_q_policy_weight),
          f"q_start={q_start}")
    check("q-policy weight monotonically decreasing", q_start >= q_mid >= q_end,
          f"start={q_start} mid={q_mid} end={q_end}")
    check("q-policy weight decays to zero floor", np.isclose(q_end, cfg.expert_q_policy_min_weight),
          f"q_end={q_end}")

    # Margin weight also imitates into the acting head and decays to 0.
    m_start = _margin_weight_schedule(0)
    m_mid = _margin_weight_schedule(cfg.expert_q_margin_decay_start_step + cfg.expert_q_margin_decay_steps // 2)
    m_end = _margin_weight_schedule(cfg.expert_q_margin_decay_start_step + cfg.expert_q_margin_decay_steps + 10_000)
    check("margin weight starts at configured weight", np.isclose(m_start, cfg.expert_q_margin_weight),
          f"m_start={m_start}")
    check("margin weight monotonically decreasing", m_start >= m_mid >= m_end,
          f"start={m_start} mid={m_mid} end={m_end}")
    check("margin weight decays to zero floor", np.isclose(m_end, cfg.expert_q_margin_min_weight),
          f"m_end={m_end}")


def test_subjective_reward_disabled():
    print("\n[subjective reward disabled]")
    cfg = C.RL_CONFIG
    m = C.metrics
    with m.lock:
        saved_steps = m.total_training_steps
        saved_last = m.last_subj_positive_weight
    try:
        with m.lock:
            m.total_training_steps = 60

        def reward_for(raw_subj):
            frame = SS.FrameData(
                state=np.zeros(C.WIRE_PARAMS_COUNT, dtype=np.float32),
                subjreward=float(raw_subj),
                objreward=0.0,
                done=False,
                player_alive=True,
                save_signal=False,
                start_pressed=False,
                level_number=1,
                game_score=0,
                num_lasers=0,
            )
            return SS._shape_transition_reward(frame, 0)[2]

        pos = reward_for(100.0)
        neg = reward_for(-100.0)
        subj_w = SS._subj_positive_weight_schedule(0)
        check("SubjW disabled by config", np.isclose(subj_w, 0.0), f"subj_w={subj_w}")
        check("positive subjective reward ignored", np.isclose(pos, 0.0), f"pos={pos}")
        check("negative subjective reward ignored", np.isclose(neg, 0.0), f"neg={neg}")
    finally:
        with m.lock:
            m.total_training_steps = saved_steps
            m.last_subj_positive_weight = saved_last


def test_epsilon_expert_floor():
    print("\n[epsilon expert floor]")
    cfg = C.RL_CONFIG
    m = C.metrics
    with m.lock:
        saved_eps = m.epsilon
        saved_xr = m.expert_ratio
        saved_lfc = m.learner_frame_count
        saved_override = m.manual_epsilon_override
        saved_pulse = m.manual_pulse_active
    try:
        with m.lock:
            m.manual_epsilon_override = False
            m.manual_pulse_active = False
            # Far past decay so natural epsilon sits at its end value.
            m.learner_frame_count = cfg.epsilon_decay_frames * 4
            m.expert_ratio = cfg.epsilon_expert_floor_until_ratio + 0.2
        eps_active = m.update_epsilon()
        check("epsilon held at floor while expert active",
              eps_active >= cfg.epsilon_expert_floor - 1e-9,
              f"eps={eps_active} floor={cfg.epsilon_expert_floor}")
        with m.lock:
            m.expert_ratio = 0.0
        eps_done = m.update_epsilon()
        check("epsilon floor releases after handoff",
              eps_done <= cfg.epsilon_expert_floor + 1e-9, f"eps={eps_done}")
    finally:
        with m.lock:
            m.epsilon = saved_eps
            m.expert_ratio = saved_xr
            m.learner_frame_count = saved_lfc
            m.manual_epsilon_override = saved_override
            m.manual_pulse_active = saved_pulse


def test_dqn_window_math():
    print("\n[DQN window math]")
    from dqn import metrics_display as MD

    saved = (
        MD._dqn100k.copy(), MD._dqn100k_dqn_frames, MD._dqn100k_total_frames,
        MD._dqn1m.copy(), MD._dqn1m_dqn_frames, MD._dqn1m_total_frames,
        MD._dqn5m.copy(), MD._dqn5m_dqn_frames, MD._dqn5m_total_frames,
    )
    try:
        MD._dqn100k.clear(); MD._dqn100k_dqn_frames = 0; MD._dqn100k_total_frames = 0
        MD._dqn1m.clear(); MD._dqn1m_dqn_frames = 0; MD._dqn1m_total_frames = 0
        MD._dqn5m.clear(); MD._dqn5m_dqn_frames = 0; MD._dqn5m_total_frames = 0

        MD.add_episode_to_dqn100k_window(10.0, ep_len=100, dqn_frames=10)
        dqn100k, _, _ = MD.get_dqn_window_averages()
        check("DQN100K/F normalizes by DQN frames", np.isclose(dqn100k, 1.0), f"got {dqn100k}")

        MD.add_episode_to_dqn100k_window(100.0, ep_len=1000, dqn_frames=100)
        dqn100k, _, _ = MD.get_dqn_window_averages()
        check("longer same-quality episode does not inflate DQN100K/F", np.isclose(dqn100k, 1.0), f"got {dqn100k}")

        MD.add_episode_to_dqn1m_window(5.0, ep_len=50, dqn_frames=5)
        MD.add_episode_to_dqn5m_window(12.0, ep_len=120, dqn_frames=6)
        _, dqn1m, dqn5m = MD.get_dqn_window_averages()
        check("DQN1M/F normalized", np.isclose(dqn1m, 1.0), f"got {dqn1m}")
        check("DQN5M/F normalized", np.isclose(dqn5m, 2.0), f"got {dqn5m}")
    finally:
        (
            d100, d100f, d100tf,
            d1m, d1mf, d1mtf,
            d5m, d5mf, d5mtf,
        ) = saved
        MD._dqn100k.clear(); MD._dqn100k.extend(d100)
        MD._dqn100k_dqn_frames = d100f; MD._dqn100k_total_frames = d100tf
        MD._dqn1m.clear(); MD._dqn1m.extend(d1m)
        MD._dqn1m_dqn_frames = d1mf; MD._dqn1m_total_frames = d1mtf
        MD._dqn5m.clear(); MD._dqn5m.extend(d5m)
        MD._dqn5m_dqn_frames = d5mf; MD._dqn5m_total_frames = d5mtf


def test_dashboard_gpu_parser():
    print("\n[dashboard GPU parser]")
    from dqn.metrics_dashboard import _DashboardState, _parse_nvidia_smi_gpu_csv
    sample = (
        "0, NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition, 71, 44, 4570, 97887, 81, 271.15, 300.00, 2175, 52\n"
        "1, NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition, 9, 0, 891, 97887, 57, 84.91, 300.00, 2317, 30\n"
    )
    rows = _parse_nvidia_smi_gpu_csv(sample)
    check("GPU parser returns two devices", len(rows) == 2, f"rows={rows}")
    check("GPU parser keeps device index", rows and rows[0]["index"] == 0 and rows[1]["index"] == 1, f"rows={rows}")
    check("GPU parser reads utilization", rows and rows[0]["gpu_util_pct"] == 71.0 and rows[1]["gpu_util_pct"] == 9.0, f"rows={rows}")
    flat = _DashboardState._flatten_gpus(rows)
    check("GPU flatten exposes gpu0 util", flat.get("gpu0_util") == 71.0, f"flat={flat}")
    check("GPU flatten exposes gpu1 memory", flat.get("gpu1_mem_used_mib") == 891.0, f"flat={flat}")


def test_dashboard_system_parser():
    print("\n[dashboard system parser]")
    from dqn.metrics_dashboard import _cpu_util_from_times, _parse_proc_meminfo, _parse_proc_stat_cpu_times
    stat0 = "cpu  100 0 50 850 0 0 0 0 0 0\n"
    stat1 = "cpu  150 0 70 880 0 0 0 0 0 0\n"
    t0 = _parse_proc_stat_cpu_times(stat0)
    t1 = _parse_proc_stat_cpu_times(stat1)
    check("CPU parser reads idle/total", t0 == (850.0, 1000.0) and t1 == (880.0, 1100.0), f"t0={t0} t1={t1}")
    util = _cpu_util_from_times(t0, t1)
    check("CPU delta utilization", np.isclose(util, 70.0), f"util={util}")
    mem = _parse_proc_meminfo(
        "MemTotal:       1048576 kB\n"
        "MemFree:         131072 kB\n"
        "MemAvailable:    786432 kB\n"
        "Buffers:          32768 kB\n"
        "Cached:           65536 kB\n"
    )
    check("meminfo available MiB", np.isclose(mem.get("ram_available_mib"), 768.0), f"mem={mem}")
    check("meminfo free percent", np.isclose(mem.get("ram_free_pct"), 75.0), f"mem={mem}")


def test_model_shapes(agent):
    print("\n[model shapes]")
    import torch
    dev = next(agent.online_net.parameters()).device
    st = torch.zeros(4, C.MODEL_STATE_SIZE, device=dev)
    move_dist, fire_dist = agent.online_net(st, log=False)
    joint_dist = agent.online_net.joint_dist(st, log=False)
    check("move_dist shape (4,9,51)", tuple(move_dist.shape) == (4, M.NUM_MOVE, C.RL_CONFIG.num_atoms))
    check("fire_dist shape (4,9,51)", tuple(fire_dist.shape) == (4, M.NUM_FIRE, C.RL_CONFIG.num_atoms))
    check("joint_dist shape (4,81,51)", tuple(joint_dist.shape) == (4, M.NUM_JOINT, C.RL_CONFIG.num_atoms))
    check("move_dist sums to 1", torch.allclose(move_dist.sum(-1), torch.ones(4, M.NUM_MOVE, device=dev), atol=1e-4))
    check("joint_dist sums to 1", torch.allclose(joint_dist.sum(-1), torch.ones(4, M.NUM_JOINT, device=dev), atol=1e-4))
    mq, fq = agent.online_net.q_values_branched(st)
    jq = agent.online_net.q_values_joint(st)
    check("move_q shape (4,9)", tuple(mq.shape) == (4, M.NUM_MOVE))
    check("fire_q shape (4,9)", tuple(fq.shape) == (4, M.NUM_FIRE))
    check("joint_q shape (4,81)", tuple(jq.shape) == (4, M.NUM_JOINT))
    bc_joint, bc_move, bc_fire = agent.online_net.bc_logits(st)
    check("bc_joint logits shape (4,81)", tuple(bc_joint.shape) == (4, M.NUM_JOINT))
    check("bc_move logits shape (4,9)", tuple(bc_move.shape) == (4, M.NUM_MOVE))
    check("bc_fire logits shape (4,9)", tuple(bc_fire.shape) == (4, M.NUM_FIRE))
    raw = agent.online_net._raw_trunk_state(st)
    enemies = agent.online_net._object_tokens(st)
    expected_raw = C.RL_CONFIG.global_features * C.RL_CONFIG.frame_stack
    check("raw trunk keeps stacked globals only", tuple(raw.shape) == (4, expected_raw),
          f"shape={tuple(raw.shape)} expected={(4, expected_raw)}")
    check("enemy tokens shape (4,112,10)",
          tuple(enemies.shape) == (4, C.ENEMY_TOKEN_COUNT, C.ENEMY_TOKEN_FEATURES),
          f"shape={tuple(enemies.shape)}")
    expected_trunk_in = expected_raw + (C.RL_CONFIG.object_attn_dim if C.RL_CONFIG.use_object_attention else 0)
    first_linear = next(m for m in agent.online_net.trunk if isinstance(m, torch.nn.Linear))
    check("trunk input excludes flattened enemy block", first_linear.in_features == expected_trunk_in,
          f"in={first_linear.in_features} expected={expected_trunk_in}")


def test_act(agent):
    print("\n[agent.act]")
    ms = stack_state(C.slice_model_state(fake_wire()))
    mv, fr, is_eps = agent.act(ms, epsilon=0.0)
    check("greedy move in 0..8", 0 <= mv <= 8)
    check("greedy fire in 0..8", 0 <= fr <= 8)
    mv, fr, is_eps = agent.act(ms, epsilon=0.0, locked_fire=3)
    check("locked-fire greedy respects fire lock", fr == 3 and 0 <= mv <= 8, f"mv={mv} fr={fr}")
    mv, fr, is_eps = agent.act(ms, epsilon=1.0)
    check("epsilon flagged", is_eps is True)
    mv, fr, is_eps = agent.act(ms, epsilon=1.0, locked_fire=4)
    check("locked-fire epsilon respects fire lock", fr == 4 and is_eps is True, f"mv={mv} fr={fr}")
    batch = agent.act_batch([ms, ms, ms], [0.0, 1.0, 0.0], locked_fires=[None, 5, 6])
    check("act_batch returns 3", len(batch) == 3)
    check("act_batch tuples valid", all(0 <= a[0] <= 8 and 0 <= a[1] <= 8 for a in batch))
    check("act_batch respects fire locks", batch[1][1] == 5 and batch[2][1] == 6, f"batch={batch}")
    check("safe epsilon returns valid", all(0 <= agent.act(ms, epsilon=1.0)[i] <= 8 for i in (0, 1)))


def test_train_step(agent):
    print("\n[train_step]")
    # Quiesce the background TrainWorker so it doesn't race our direct call.
    # (In production only that single thread ever calls train_step; the socket
    #  path only calls agent.step, so concurrent training never happens.)
    agent.running = False
    try:
        agent._train_queue.put_nowait(None)
    except Exception:
        pass
    try:
        agent._train_thread.join(timeout=5.0)
    except Exception:
        pass

    check("replay state dtype is float32", agent.memory.states.dtype == np.float32,
          f"dtype={agent.memory.states.dtype}")

    # Temporarily lower the warmup gate so a real update runs on a small buffer.
    _saved_min = C.RL_CONFIG.min_replay_to_train
    C.RL_CONFIG.min_replay_to_train = C.RL_CONFIG.batch_size
    try:
        # Inject enough transitions to train a batch.
        rng = np.random.default_rng(0)
        n = max(C.RL_CONFIG.batch_size * 2, 1600)
        for i in range(n):
            s = rng.random(C.MODEL_STATE_SIZE).astype(np.float32)
            ns = rng.random(C.MODEL_STATE_SIZE).astype(np.float32)
            mv = int(rng.integers(0, 9))
            fr = int(rng.integers(0, 9))
            r = float(rng.normal(0, 1))
            done = bool(i % 50 == 0)
            actor = "expert" if (i % 4 == 0) else "dqn"
            interest = 0.9 if (i % 13 == 0) else 0.0
            agent.step(s, (mv, fr), r, ns, done, actor=actor, horizon=1, priority_reward=r, interest=interest)
        check("buffer filled", len(agent.memory) >= C.RL_CONFIG.batch_size)
        stats = agent.memory.get_partition_stats()
        check("interesting transitions tracked", stats.get("interesting", 0) > 0,
              f"stats={stats}")
        from dqn.training import train_step
        loss = train_step(agent)
        check("train_step returns finite loss", loss is not None and np.isfinite(loss), f"loss={loss}")
        loss2 = train_step(agent)
        check("second train_step ok", loss2 is not None and np.isfinite(loss2), f"loss={loss2}")
        # q-value range should be finite after a couple of updates
        lo, hi = agent.get_q_value_range()
        check("q-range finite", np.isfinite(lo) and np.isfinite(hi), f"({lo},{hi})")
    finally:
        C.RL_CONFIG.min_replay_to_train = _saved_min


def test_expert():
    print("\n[expert integration]")
    if SS.get_expert_action is None:
        check("expert available", False, "v3.expert import failed")
        return
    w = fake_wire(wave=3)
    mv, fr = SS.get_expert_action(w, 3)
    check("expert move in 0..8", 0 <= int(mv) <= 8, f"mv={mv}")
    check("expert fire in 0..8", 0 <= int(fr) <= 8, f"fr={fr}")

    # Parity: the lean DQN extractor must match the shared v3 expert exactly.
    try:
        from v3.expert import get_expert_action as _shared_expert
        from dqn.expert_fast import fast_expert_action as _fast_expert
        from v3.state_processor import _POOLS_START, ENTITY_POOL_DEFS
        rng = np.random.default_rng(7)
        n_wire = C.WIRE_PARAMS_COUNT
        mism = 0
        for _ in range(500):
            wire = np.zeros(n_wire, dtype=np.float32)
            wire[5] = rng.random()
            wire[6] = rng.random()
            off = _POOLS_START
            for _pool, ms, fps in ENTITY_POOL_DEFS:
                base = off + 1
                for s in range(ms):
                    if rng.random() < 0.4:
                        ss = base + s * fps
                        wire[ss] = 1.0
                        for k in range(1, fps):
                            wire[ss + k] = rng.random() * 2 - 1
                off += 1 + ms * fps
            wave = int(rng.integers(1, 12))
            lf = None if rng.random() < 0.7 else int(rng.integers(0, 9))
            if _shared_expert(wire, wave_number=wave, locked_fire=lf) != \
               _fast_expert(wire, wave_number=wave, locked_fire=lf):
                mism += 1
        check("fast expert matches shared expert (500 states)", mism == 0,
              f"{mism} mismatches")
    except Exception as e:
        check("fast expert parity", False, f"error: {e}")


# ── Socket integration ──────────────────────────────────────────────────────
def test_socket_integration(agent):
    print("\n[socket integration]")
    host, port = "127.0.0.1", 19998
    server = SS.SocketServer(host, port, agent, C.metrics)
    C.metrics.global_server = server
    t = threading.Thread(target=server.start, daemon=True)
    t.start()

    # Wait for the listener to come up.
    deadline = time.time() + 5.0
    sock = None
    while time.time() < deadline:
        try:
            sock = socket.create_connection((host, port), timeout=1.0)
            break
        except OSError:
            time.sleep(0.05)
    check("server accepts connection", sock is not None)
    if sock is None:
        server.stop()
        return

    try:
        sock.sendall(struct.pack(">H", 0))      # handshake

        def recv_action():
            buf = b""
            sock.settimeout(2.0)
            while len(buf) < 5:
                chunk = sock.recv(5 - len(buf))
                if not chunk:
                    return None
                buf += chunk
            return struct.unpack(">bbBBB", buf)

        valid = True
        start_before = len(agent.memory)
        N = 60
        for i in range(N):
            done = 1 if i == N - 1 else 0
            obj = -25000.0 if done else 5.0
            w = fake_wire(wave=1 + (i // 20))
            sock.sendall(framed(make_payload(
                w, subj=0.3, obj=obj, done=done, score=100 * i, alive=1, wave=1 + (i // 20))))
            act = recv_action()
            if act is None:
                valid = False
                break
            mv, fr, src, sadv, slvl = act
            if not (-1 <= mv <= 7 and -1 <= fr <= 7 and 0 <= src <= 3 and slvl >= 1):
                valid = False
                break
            if done:
                check("terminal -> neutral action", mv == -1 and fr == -1 and src == 0,
                      f"got {act}")
        check("all actions well-formed", valid)

        # Give the async replay buffer a moment to drain its queue.
        time.sleep(0.5)
        grew = len(agent.memory) > start_before
        check("transitions stored in replay buffer", grew,
              f"before={start_before} after={len(agent.memory)}")
    finally:
        try:
            sock.close()
        except Exception:
            pass
        server.stop()
        time.sleep(0.2)


def main():
    print("=" * 70)
    print("ROBOTRON DQN SMOKE TEST".center(70))
    print("=" * 70)

    test_action_coding()
    test_slice()
    test_nstep_actor_boundaries()
    test_parse_roundtrip()
    test_fire_hold()
    test_reward_and_hard_starts()
    test_score_level_1m_metrics()
    test_transition_interest_policy()
    test_legacy_interest_sanitizer()
    test_pre_death_reward_penalty()
    test_expert_anchor_decay()
    test_subjective_reward_disabled()
    test_epsilon_expert_floor()
    test_dqn_window_math()
    test_dashboard_gpu_parser()
    test_dashboard_system_parser()
    test_expert()

    print("\n[building agent]")
    agent = RainbowAgent(state_size=C.RL_CONFIG.state_size)
    check("agent built", agent is not None)
    print(f"  device = {agent.device}")

    test_model_shapes(agent)
    test_act(agent)
    test_train_step(agent)
    test_socket_integration(agent)

    try:
        agent.stop()
    except Exception:
        pass

    print("\n" + "=" * 70)
    print(f"RESULT: {_PASS} passed, {_FAIL} failed".center(70))
    print("=" * 70)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
