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
from dqn.agent import (
    RainbowAgent,
    _close_cardinal_target_dir_from_state,
    _prefer_cardinal_fire_for_close_target,
)
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
    w[:C.CORE_ELIST_FEATURES] = np.arange(C.CORE_ELIST_FEATURES, dtype=np.float32)
    expected_lane = []
    for action_idx, wire_lane_idx in enumerate(C.ACTION_LANE_WIRE_INDICES):
        enemy_density = 0.10 + 0.01 * action_idx
        human_density = 0.20 + 0.01 * action_idx
        base = C.TACTICAL_LANE_OFFSET + wire_lane_idx * C.LANE_FEATURES
        w[base + 7] = enemy_density
        w[base + 11] = human_density
        expected_lane.extend([enemy_density, human_density])
    add_pool_slot(w, "danger", 3, [1.0, 0.25, -0.50, 0.20, 0.05, -0.10, 0.80, 0.40, 0.30, 0.50])
    add_pool_slot(w, "projectile", 0, [1.0, -0.1, 0.1, 0.08, 0.0, 0.0, 0.9, 0.2, 0.1, 0.5, 0.0])
    add_pool_slot(w, "human", 0, [1.0, 0.75, 0.75, 0.10, 0.0, 0.0, 0.0])
    add_pool_slot(w, "electrode", 0, [1.0, -0.75, -0.75, 0.10, 0.6])
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
    lane_summary = ms[C.LANE_SUMMARY_OFFSET:C.LANE_SUMMARY_END]
    check("lane density summary is action-ordered",
          np.allclose(lane_summary, np.asarray(expected_lane, dtype=np.float32), atol=1e-6),
          f"lane_summary={lane_summary}")
    target_summary = ms[C.TARGET_SUMMARY_OFFSET:C.TARGET_SUMMARY_END]
    check("nearest destructible target summary",
          np.allclose(target_summary, np.asarray([-0.1, 0.1, 0.08], dtype=np.float32), atol=1e-6),
          f"target_summary={target_summary}")
    empty_ms = C.slice_model_state(np.zeros(C.WIRE_PARAMS_COUNT, dtype=np.float32))
    check("empty nearest target defaults absent",
          np.allclose(empty_ms[C.TARGET_SUMMARY_OFFSET:C.TARGET_SUMMARY_END],
                      np.asarray([0.0, 0.0, 1.0], dtype=np.float32)),
          f"target_summary={empty_ms[C.TARGET_SUMMARY_OFFSET:C.TARGET_SUMMARY_END]}")
    check("object block starts after globals", C.OBJECT_TOKEN_OFFSET == C.GLOBAL_FEATURES)
    check("object block follows target summary", C.OBJECT_TOKEN_OFFSET == C.TARGET_SUMMARY_END)
    check("object block size", ms.shape[0] - C.OBJECT_TOKEN_OFFSET == C.OBJECT_FEATURES)
    objects = ms[C.OBJECT_TOKEN_OFFSET:C.OBJECT_TOKEN_END].reshape(C.OBJECT_TOKEN_COUNT, C.OBJECT_TOKEN_FEATURES)
    active = objects[objects[:, 0] > 0.5]
    check("all tactical pools become object rows", active.shape[0] == 4, f"active={active.shape[0]}")
    roles = set(np.round(active[:, 11], 2).tolist())
    check("projectile/danger/human/electrode roles present",
          {0.25, 0.50, 0.75, 1.00}.issubset(roles), f"roles={roles}")
    check("highest-priority projectile sorts first",
          np.isclose(objects[0, 15], 1.0) and np.isclose(objects[0, 12], 1.0),
          f"row0={objects[0]}")
    check("danger row keeps motion/threat fields",
          np.any(np.all(np.isclose(active[:, 1:10],
                                   np.asarray([0.25, -0.50, 0.20, 0.05, -0.10, 0.80, 0.40, 0.30, 0.20],
                                              dtype=np.float32), atol=1e-5), axis=1)),
          f"active={active}")
    check("electrode blocker flag present", np.any((active[:, 11] > 0.95) & (active[:, 13] > 0.5)))
    check("human rescue flag present", np.any((active[:, 11] > 0.70) & (active[:, 11] < 0.80) & (active[:, 14] > 0.5)))


def test_nstep_actor_boundaries():
    print("\n[n-step actor boundaries]")
    nbuf = NStepReplayBuffer(n_step=12, gamma=0.5)
    s0 = np.array([0], dtype=np.float32)
    s1 = np.array([1], dtype=np.float32)
    s2 = np.array([2], dtype=np.float32)
    s3 = np.array([3], dtype=np.float32)
    out = []
    out += nbuf.add(s0, 0, 1.0, s1, False, actor="dqn", advisor_action=7)
    out += nbuf.add(s1, 1, 2.0, s2, False, actor="epsilon")
    out += nbuf.add(s2, 2, 4.0, s3, False, actor="expert")
    check("actor switch flushes learner prefix", len(out) == 2, f"len={len(out)}")
    if len(out) >= 2:
        check("dqn+epsilon grouped as learner", out[0][2] == 2.0 and out[0][6] == 2,
              f"R={out[0][2]} h={out[0][6]}")
        check("n-step preserves first advisor action", out[0][9] == 7, f"advisor={out[0][9]}")
        check("boundary does not include expert reward", out[1][2] == 2.0 and out[1][6] == 1,
              f"R={out[1][2]} h={out[1][6]}")

        nbuf2 = NStepReplayBuffer(n_step=3, gamma=0.5)
        out2 = []
        out2 += nbuf2.add(s0, 0, 1.0, s1, False, actor="dqn", interest=0.2)
        out2 += nbuf2.add(s1, 1, 1.0, s2, False, actor="dqn", interest=0.8)
        out2 += nbuf2.add(s2, 2, 1.0, s3, False, actor="dqn", interest=0.4)
        check("n-step carries max interest", len(out2) == 1 and np.isclose(out2[0][8], 0.8),
            f"out={out2}")


def test_episode_level_expert_guidance():
    print("\n[episode-level expert guidance]")
    server = SS.SocketServer("127.0.0.1", 0, None)
    saved_mode = getattr(C.RL_CONFIG, "expert_guidance_mode", "episode")
    saved_expert = SS.get_expert_action
    saved_game_expert_pct = C.game_settings.expert_pct
    with C.metrics.lock:
        saved_ratio = C.metrics.expert_ratio
        saved_override = C.metrics.override_expert
        saved_expert_mode = C.metrics.expert_mode
    try:
        C.RL_CONFIG.expert_guidance_mode = "episode"
        C.game_settings.expert_pct = -1
        SS.get_expert_action = lambda *args, **kwargs: (8, 8)
        with C.metrics.lock:
            C.metrics.expert_ratio = 1.0
            C.metrics.override_expert = False
            C.metrics.expert_mode = False
        cs = {"episode_control_initialized": False, "episode_use_expert": False}
        check("episode ratio 100 enables expert episode",
              server._episode_expert_enabled(cs, eval_only=False) is True)
        check("episode gate initializes once", cs["episode_control_initialized"] is True)

        with C.metrics.lock:
            C.metrics.expert_ratio = 0.0
        check("episode ratio 0 disables current expert episode",
              server._episode_expert_enabled(cs, eval_only=False) is False)
        check("frame mode remains configurable",
              setattr(C.RL_CONFIG, "expert_guidance_mode", "frame") is None
              and server._expert_guidance_mode() == "frame")
    finally:
        C.RL_CONFIG.expert_guidance_mode = saved_mode
        C.game_settings.expert_pct = saved_game_expert_pct
        SS.get_expert_action = saved_expert
        with C.metrics.lock:
            C.metrics.expert_ratio = saved_ratio
            C.metrics.override_expert = saved_override
            C.metrics.expert_mode = saved_expert_mode


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
        state=fake_wire(), subjreward=0.0, objreward=-25000.0,
        done=False, player_alive=True, save_signal=False, start_pressed=False,
        level_number=1, game_score=5000, num_lasers=0)
    total, score_r, subj_r, death_r, score_delta = SS._shape_transition_reward(frame, last_game_score=0)
    check("5000 score delta maps to reward 5.0", np.isclose(score_r, 5.0), f"score_r={score_r}")
    check("5000 score delta is not clipped", np.isclose(total, 5.0), f"total={total}")
    frame2 = SS.FrameData(
        state=fake_wire(), subjreward=0.0, objreward=0.0,
        done=False, player_alive=True, save_signal=False, start_pressed=False,
        level_number=1, game_score=1000, num_lasers=0)
    _, score_r2, _, _, _ = SS._shape_transition_reward(frame2, last_game_score=0)
    check("1000 score delta maps to reward 1.0", np.isclose(score_r2, 1.0), f"score_r={score_r2}")

    no_human_state = fake_wire()
    no_human_state[13] = 0.0
    no_human_state[9] = 0.4
    frame_delay = SS.FrameData(
        state=no_human_state, subjreward=0.0, objreward=0.0,
        done=False, player_alive=True, save_signal=False, start_pressed=False,
        level_number=1, game_score=0, num_lasers=0)
    total_delay, _, subj_delay, _, _ = SS._shape_transition_reward(frame_delay, last_game_score=0)
    expected_delay = -float(C.RL_CONFIG.no_human_delay_penalty)
    check("no-human delay penalty applies",
          np.isclose(subj_delay, expected_delay) and np.isclose(total_delay, expected_delay),
          f"subj={subj_delay} total={total_delay} expected={expected_delay}")

    crowded_model_state = np.zeros(C.MODEL_STATE_SIZE, dtype=np.float32)
    obj_start = int(C.RL_CONFIG.global_features)
    obj_feats = int(C.RL_CONFIG.object_token_features)
    for i in range(int(C.RL_CONFIG.no_human_delay_max_targets) + 1):
        off = obj_start + i * obj_feats
        crowded_model_state[off + 0] = 1.0  # present
        crowded_model_state[off + 3] = 0.4  # dist
        crowded_model_state[off + 12] = 1.0 # destructible
    crowded_total, _, crowded_subj, _, _ = SS._shape_transition_reward(
        frame_delay, last_game_score=0, model_state=crowded_model_state)
    check("no-human delay penalty skips crowded combat",
          np.isclose(crowded_subj, 0.0) and np.isclose(crowded_total, 0.0),
          f"subj={crowded_subj} total={crowded_total}")

    cleanup_model_state = np.zeros(C.MODEL_STATE_SIZE, dtype=np.float32)
    for i in range(int(C.RL_CONFIG.no_human_delay_max_targets)):
        off = obj_start + i * obj_feats
        cleanup_model_state[off + 0] = 1.0
        cleanup_model_state[off + 3] = 0.4
        cleanup_model_state[off + 12] = 1.0
    cleanup_total, _, cleanup_subj, _, _ = SS._shape_transition_reward(
        frame_delay, last_game_score=0, model_state=cleanup_model_state)
    check("no-human delay penalty applies in cleanup",
          np.isclose(cleanup_subj, expected_delay) and np.isclose(cleanup_total, expected_delay),
          f"subj={cleanup_subj} total={cleanup_total} expected={expected_delay}")

    human_state = fake_wire()
    human_state[13] = 1.0 / 255.0
    human_state[9] = 0.4
    frame_humans = SS.FrameData(
        state=human_state, subjreward=0.0, objreward=0.0,
        done=False, player_alive=True, save_signal=False, start_pressed=False,
        level_number=1, game_score=0, num_lasers=0)
    total_humans, _, subj_humans, _, _ = SS._shape_transition_reward(frame_humans, last_game_score=0)
    check("no-human delay penalty skips live-human states",
          np.isclose(subj_humans, 0.0) and np.isclose(total_humans, 0.0),
          f"subj={subj_humans} total={total_humans}")

    frame_score_no_humans = SS.FrameData(
        state=no_human_state, subjreward=0.0, objreward=0.0,
        done=False, player_alive=True, save_signal=False, start_pressed=False,
        level_number=1, game_score=1000, num_lasers=0)
    total_score_no_humans, score_no_humans, subj_score_no_humans, _, _ = SS._shape_transition_reward(
        frame_score_no_humans, last_game_score=0)
    check("no-human delay penalty skips scoring frames",
          np.isclose(score_no_humans, 1.0)
          and np.isclose(subj_score_no_humans, 0.0)
          and np.isclose(total_score_no_humans, 1.0),
          f"score={score_no_humans} subj={subj_score_no_humans} total={total_score_no_humans}")

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


def test_transition_interest_policy():
    print("\n[transition interest]")

    def model_state(wave: int, object_row: list[float] | None = None):
        s = np.zeros(C.MODEL_STATE_SIZE, dtype=np.float32)
        s[4] = max(0, min(40, int(wave))) / 40.0
        if object_row is not None:
            vals = list(object_row[:C.OBJECT_TOKEN_FEATURES])
            vals += [0.0] * (C.OBJECT_TOKEN_FEATURES - len(vals))
            start = C.OBJECT_TOKEN_OFFSET
            s[start:start + C.OBJECT_TOKEN_FEATURES] = np.asarray(vals, dtype=np.float32)
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
    check("distant object is not interesting", distant < threshold, f"score={distant:.3f}")
    target = SS._transition_interest_score(
        model_state(10), model_state(10, [1.0, 0.02, 0.0, 0.02, 0.0, 0.0, 1.0, 0.7, 0.0, 0.0]),
        frame(10), 0.0, 0.0)
    check("near threatening object is interesting", target >= threshold, f"score={target:.3f}")
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
            start = C.OBJECT_TOKEN_OFFSET
            row = [
                1.0, 0.0, 0.0, 0.20, 0.0, 0.0, float(danger), 0.0,
                1.00, 0.0, 0.0, 0.50, 1.0, 0.0, 0.0, 0.0,
            ]
            s[start:start + C.OBJECT_TOKEN_FEATURES] = np.asarray(row, dtype=np.float32)
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
        start = C.OBJECT_TOKEN_OFFSET
        row = [
            1.0, 0.0, 0.0, 0.20, 0.0, 0.0, 1.0, 0.0,
            1.00, 0.0, 0.0, 0.50, 1.0, 0.0, 0.0, 0.0,
        ]
        s[start:start + C.OBJECT_TOKEN_FEATURES] = np.asarray(row, dtype=np.float32)
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


def test_expert_replay_quota():
    print("\n[expert replay quota]")
    from dqn.replay_buffer import PrioritizedReplayBuffer

    cfg = C.RL_CONFIG
    saved = (
        cfg.expert_replay_fraction,
        cfg.interesting_replay_fraction,
        cfg.recent_replay_fraction,
    )
    try:
        cfg.expert_replay_fraction = 0.25
        cfg.interesting_replay_fraction = 0.0
        cfg.recent_replay_fraction = 0.0
        buf = PrioritizedReplayBuffer(capacity=64, state_size=C.MODEL_STATE_SIZE)
        s = np.zeros(C.MODEL_STATE_SIZE, dtype=np.float32)
        for i in range(48):
            buf.add(s, i % M.NUM_JOINT, 0.0, s, False, expert=0, advisor_action=(i + 1) % M.NUM_JOINT)
        for i in range(16):
            buf.add(s, i % M.NUM_JOINT, 0.0, s, False, expert=1)
        batch = buf.sample(32, beta=0.4)
        expert_count = int(batch[6].sum()) if batch is not None else 0
        origins = getattr(buf, "last_sample_origin_counts", {})
        advisor_actions = batch[9] if batch is not None and len(batch) >= 10 else np.asarray([], dtype=np.int64)
        check("expert replay quota samples demonstrations",
              batch is not None and expert_count >= 8,
              f"expert_count={expert_count}")
        check("expert replay quota origin tracked",
              int(origins.get("expert", 0)) >= 8,
              f"origins={origins}")
        check("advisor actions sampled",
              batch is not None and advisor_actions.shape[0] == 32,
              f"advisor_shape={advisor_actions.shape}")
    finally:
        (
            cfg.expert_replay_fraction,
            cfg.interesting_replay_fraction,
            cfg.recent_replay_fraction,
        ) = saved


def test_expert_anchor_decay():
    print("\n[expert anchor decay]")
    from dqn.training import (
        _advisor_margin_weight_schedule,
        _advisor_q_policy_weight_schedule,
        _bc_weight_schedule,
        _margin_weight_schedule,
        _q_policy_weight_schedule,
    )
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
    check("q-policy weight decays to configured floor", np.isclose(q_end, cfg.expert_q_policy_min_weight),
          f"q_end={q_end}")

    # Margin weight also imitates into the acting head and decays to 0.
    m_start = _margin_weight_schedule(0)
    m_mid = _margin_weight_schedule(cfg.expert_q_margin_decay_start_step + cfg.expert_q_margin_decay_steps // 2)
    m_end = _margin_weight_schedule(cfg.expert_q_margin_decay_start_step + cfg.expert_q_margin_decay_steps + 10_000)
    check("margin weight starts at configured weight", np.isclose(m_start, cfg.expert_q_margin_weight),
          f"m_start={m_start}")
    check("margin weight monotonically decreasing", m_start >= m_mid >= m_end,
          f"start={m_start} mid={m_mid} end={m_end}")
    check("margin weight decays to configured floor", np.isclose(m_end, cfg.expert_q_margin_min_weight),
          f"m_end={m_end}")

    # Advisor imitation should bridge the handoff but not become a permanent
    # ceiling on the acting Q-policy.
    aq_start = _advisor_q_policy_weight_schedule(0)
    aq_handoff = _advisor_q_policy_weight_schedule(cfg.expert_ratio_decay_steps)
    aq_end = _advisor_q_policy_weight_schedule(cfg.advisor_q_policy_decay_start_step + cfg.advisor_q_policy_decay_steps + 10_000)
    check("advisor q-policy starts at configured weight", np.isclose(aq_start, cfg.advisor_q_policy_weight),
          f"aq_start={aq_start}")
    check("advisor q-policy remains active at handoff",
          aq_handoff > cfg.advisor_q_policy_min_weight,
          f"handoff={aq_handoff} floor={cfg.advisor_q_policy_min_weight}")
    check("advisor q-policy releases to floor", np.isclose(aq_end, cfg.advisor_q_policy_min_weight),
          f"aq_end={aq_end}")

    am_start = _advisor_margin_weight_schedule(0)
    am_handoff = _advisor_margin_weight_schedule(cfg.expert_ratio_decay_steps)
    am_end = _advisor_margin_weight_schedule(cfg.advisor_q_margin_decay_start_step + cfg.advisor_q_margin_decay_steps + 10_000)
    check("advisor margin starts at configured weight", np.isclose(am_start, cfg.advisor_q_margin_weight),
          f"am_start={am_start}")
    check("advisor margin remains active at handoff",
          am_handoff > cfg.advisor_q_margin_min_weight,
          f"handoff={am_handoff} floor={cfg.advisor_q_margin_min_weight}")
    check("advisor margin releases to floor", np.isclose(am_end, cfg.advisor_q_margin_min_weight),
          f"am_end={am_end}")


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
    objects = agent.online_net._object_tokens(st)
    expected_raw = C.RL_CONFIG.global_features * C.RL_CONFIG.frame_stack
    check("raw trunk keeps stacked globals/lane/target summary only", tuple(raw.shape) == (4, expected_raw),
          f"shape={tuple(raw.shape)} expected={(4, expected_raw)}")
    check("object tokens shape (4,96,16)",
          tuple(objects.shape) == (4, C.OBJECT_TOKEN_COUNT, C.OBJECT_TOKEN_FEATURES),
          f"shape={tuple(objects.shape)}")
    expected_trunk_in = expected_raw + (C.RL_CONFIG.object_attn_dim if C.RL_CONFIG.use_object_attention else 0)
    first_linear = next(m for m in agent.online_net.trunk if isinstance(m, torch.nn.Linear))
    check("trunk input excludes flattened object block", first_linear.in_features == expected_trunk_in,
          f"in={first_linear.in_features} expected={expected_trunk_in}")


def test_dashboard_model_summary(agent):
    print("\n[dashboard model summary]")
    from dqn.metrics_dashboard import _DashboardState
    desc = _DashboardState(C.metrics, agent)._get_model_desc()
    expected_state = f"state {C.RL_CONFIG.state_size}"
    expected_trunk = f"trunk {expected_trunk_in(agent)}"
    expected_objects = f"object-attn {C.RL_CONFIG.object_token_count}x{C.RL_CONFIG.object_token_features}"
    check("summary includes full state size", expected_state in desc, desc)
    check("summary includes lane density size", f"{C.RL_CONFIG.lane_summary_features}lane" in desc, desc)
    check("summary includes nearest-target size", f"{C.RL_CONFIG.target_summary_features}target" in desc, desc)
    check("summary includes post-attention trunk shape", expected_trunk in desc, desc)
    check("summary includes object-token shape", expected_objects in desc, desc)
    check("summary marks geometry bias", "geom" in desc, desc)
    check("summary includes parameter count", "params" in desc and "1.2M" in desc, desc)


def expected_trunk_in(agent) -> str:
    import torch
    first_linear = next(m for m in agent.online_net.trunk if isinstance(m, torch.nn.Linear))
    layers = [str(first_linear.in_features)]
    layers += [str(C.RL_CONFIG.trunk_hidden)] * int(C.RL_CONFIG.trunk_layers)
    return " \u00bb ".join(layers)


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

    snap_single = np.zeros(C.SINGLE_FRAME_STATE_SIZE, dtype=np.float32)
    snap_single[C.TARGET_SUMMARY_OFFSET:C.TARGET_SUMMARY_OFFSET + 3] = (-0.12, 0.02, 0.13)
    q = np.zeros((M.NUM_MOVE, M.NUM_FIRE), dtype=np.float32)
    q[0, 5] = 10.0
    q[1, 6] = 9.2
    snap_state = stack_state(snap_single)
    check("close near-axis target resolves to W", _close_cardinal_target_dir_from_state(snap_state) == 6)
    check("close diagonal fire snaps to W", _prefer_cardinal_fire_for_close_target(snap_state, q, 0, 5) == (1, 6))

    snap_single[C.TARGET_SUMMARY_OFFSET:C.TARGET_SUMMARY_OFFSET + 3] = (-0.12, 0.12, 0.18)
    diag_state = stack_state(snap_single)
    check("true diagonal target does not cardinal-snap",
          _prefer_cardinal_fire_for_close_target(diag_state, q, 0, 5) == (0, 5))


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
            advisor = ((mv + 1) % 9, fr) if actor != "expert" else (mv, fr)
            agent.step(s, (mv, fr), r, ns, done, actor=actor, horizon=1,
                       priority_reward=r, interest=interest, advisor_action=advisor)
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
        diag_vals = [
            C.metrics.last_current_q_action_mean,
            C.metrics.last_bellman_loss,
            C.metrics.last_imitation_loss,
            C.metrics.last_bc_loss_contrib,
            C.metrics.last_expert_q_policy_weight,
            C.metrics.last_expert_q_policy_loss_contrib,
            C.metrics.last_expert_q_margin_weight,
            C.metrics.last_expert_q_margin_loss_contrib,
            C.metrics.last_advisor_q_policy_weight,
            C.metrics.last_advisor_q_policy_loss_contrib,
            C.metrics.last_advisor_q_margin_weight,
            C.metrics.last_advisor_q_margin_loss_contrib,
            C.metrics.last_target_q_mean,
            C.metrics.last_unclamped_target_q_mean,
            C.metrics.last_next_q_max_mean,
            C.metrics.last_target_next_q_mean,
            C.metrics.last_double_q_gap_mean,
            C.metrics.last_td_q_mean,
            C.metrics.last_td_q_abs_mean,
            C.metrics.last_q_gap_mean,
            C.metrics.last_target_clip_low_frac,
            C.metrics.last_target_clip_high_frac,
            C.metrics.last_target_low_atom_mass,
            C.metrics.last_target_high_atom_mass,
            C.metrics.last_target_mass_error_mean,
            C.metrics.last_policy_idle_move_frac,
            C.metrics.last_policy_idle_fire_frac,
            C.metrics.last_policy_noop_frac,
            C.metrics.last_policy_top_action_frac,
            C.metrics.last_policy_action_entropy,
            C.metrics.last_sample_idle_move_frac,
            C.metrics.last_sample_idle_fire_frac,
            C.metrics.last_sample_noop_frac,
            C.metrics.last_sample_top_action_frac,
            C.metrics.last_sample_action_entropy,
            C.metrics.last_sample_reward_mean,
            C.metrics.last_sample_reward_abs_mean,
            C.metrics.last_sample_advisor_frac,
            C.metrics.last_advisor_joint_agreement,
            C.metrics.last_advisor_q_rank_mean,
            C.metrics.last_advisor_q_margin_mean,
        ]
        check("Bellman diagnostics finite",
              all(np.isfinite(float(v)) for v in diag_vals),
              f"diag={diag_vals}")
        origin_sum = (
            C.metrics.last_sample_per_frac
            + C.metrics.last_sample_expert_quota_frac
            + C.metrics.last_sample_interesting_frac
            + C.metrics.last_sample_recent_frac
        )
        check("sample origin fractions sum to one",
              abs(origin_sum - 1.0) < 1e-6,
              f"origin_sum={origin_sum}")
        check("expert rank diagnostic populated",
              C.metrics.last_expert_q_rank_mean >= 1.0,
              f"rank={C.metrics.last_expert_q_rank_mean}")
        check("advisor diagnostic populated",
              C.metrics.last_sample_advisor_frac > 0.0 and C.metrics.last_advisor_q_rank_mean >= 1.0,
              f"frac={C.metrics.last_sample_advisor_frac} rank={C.metrics.last_advisor_q_rank_mean}")
        check("projected target distribution preserves mass",
              C.metrics.last_target_mass_error_mean < 1e-4,
              f"mass_error={C.metrics.last_target_mass_error_mean}")
        check("action entropy diagnostics bounded",
              0.0 <= C.metrics.last_policy_action_entropy <= 1.0
              and 0.0 <= C.metrics.last_sample_action_entropy <= 1.0,
              f"policy={C.metrics.last_policy_action_entropy} sample={C.metrics.last_sample_action_entropy}")
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
    test_episode_level_expert_guidance()
    test_parse_roundtrip()
    test_fire_hold()
    test_reward_and_hard_starts()
    test_transition_interest_policy()
    test_legacy_interest_sanitizer()
    test_pre_death_reward_penalty()
    test_expert_replay_quota()
    test_expert_anchor_decay()
    test_epsilon_expert_floor()
    test_dqn_window_math()
    test_expert()

    print("\n[building agent]")
    agent = RainbowAgent(state_size=C.RL_CONFIG.state_size)
    check("agent built", agent is not None)
    print(f"  device = {agent.device}")

    test_model_shapes(agent)
    test_dashboard_model_summary(agent)
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
