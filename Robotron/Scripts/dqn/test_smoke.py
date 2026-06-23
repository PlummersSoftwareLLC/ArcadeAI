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
    # A little signal in the lane block.
    w[C.TACTICAL_LANE_OFFSET:C.TACTICAL_LANE_END] = np.random.rand(
        C.TACTICAL_LANE_END - C.TACTICAL_LANE_OFFSET).astype(np.float32) * 0.1
    return w


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
    w = np.arange(C.WIRE_PARAMS_COUNT, dtype=np.float32)
    ms = C.slice_model_state(w)
    lane_end = C.CORE_FEATURES + C.LANE_COUNT * C.LANE_FEATURES
    object_start = lane_end + C.EXTRA_FEATURES
    check("slice length == MODEL_STATE_SIZE", ms.shape[0] == C.MODEL_STATE_SIZE)
    check("core[0] preserved", ms[0] == w[0])
    check("core[17] preserved", ms[17] == w[17])
    check("lane[0] == wire[40]", ms[C.CORE_FEATURES] == w[C.TACTICAL_LANE_OFFSET])
    check("last lane == wire[279]", ms[lane_end - 1] == w[C.TACTICAL_LANE_END - 1])
    check("extra block present", object_start - lane_end == C.EXTRA_FEATURES)
    check("object block present", ms.shape[0] - object_start == C.OBJECT_FEATURES)

    # Derived proximity channels: 1 - nearest_*_dist (from core indices 9, 10).
    enemy_prox = ms[lane_end + 0]
    human_prox = ms[lane_end + 1]
    check("enemy_prox == 1 - core[9]", np.isclose(enemy_prox, 1.0 - w[9]))
    check("human_prox == 1 - core[10]", np.isclose(human_prox, 1.0 - w[10]))

    # Derived global nearest-human direction, reconstructed from the lane whose
    # human sub-block has the smallest distance.  With arange data every lane has
    # a human present, so lane 0 (smallest values) is nearest.
    human_dx = ms[lane_end + 2]
    human_dy = ms[lane_end + 3]
    li = int(np.argmin(
        [w[C.TACTICAL_LANE_OFFSET + i * C.LANE_FEATURES + C._LANE_HUMAN_DIST]
         for i in range(C.LANE_COUNT)]))
    exp_dx = w[C.TACTICAL_LANE_OFFSET + li * C.LANE_FEATURES + C._LANE_HUMAN_DX]
    exp_dy = w[C.TACTICAL_LANE_OFFSET + li * C.LANE_FEATURES + C._LANE_HUMAN_DY]
    check("human_dx from nearest lane", human_dx == exp_dx)
    check("human_dy from nearest lane", human_dy == exp_dy)

    # When no humans are present anywhere, direction collapses to (0, 0).
    w2 = np.arange(C.WIRE_PARAMS_COUNT, dtype=np.float32)
    for i in range(C.LANE_COUNT):
        w2[C.TACTICAL_LANE_OFFSET + i * C.LANE_FEATURES + C._LANE_HUMAN_COUNT] = 0.0
    ms2 = C.slice_model_state(w2)
    check("no-human dir == 0", ms2[lane_end + 2] == 0.0 and ms2[lane_end + 3] == 0.0)

    w3 = np.zeros(C.WIRE_PARAMS_COUNT, dtype=np.float32)
    ms3 = C.slice_model_state(w3)
    check("empty lane enemy dist == far", ms3[C.CORE_FEATURES + C._LANE_ENEMY_DIST] == 1.0)
    check("empty lane human dist == far", ms3[C.CORE_FEATURES + C._LANE_HUMAN_DIST] == 1.0)
    check("empty lane projectile dist == far", ms3[C.CORE_FEATURES + C._LANE_PROJECTILE_DIST] == 1.0)
    check("empty lane enemy ttc == far", ms3[C.CORE_FEATURES + C._LANE_ENEMY_TTC] == 1.0)
    check("empty lane projectile ttc == far", ms3[C.CORE_FEATURES + C._LANE_PROJECTILE_TTC] == 1.0)
    check("empty lane closest pass == far", ms3[C.CORE_FEATURES + C._LANE_PROJECTILE_CLOSEST_PASS] == 1.0)

    w4 = np.zeros(C.WIRE_PARAMS_COUNT, dtype=np.float32)
    add_pool_slot(w4, "human", 0, [1.0, 0.25, -0.25, 0.20, 0.0, 0.0, 0.1])
    add_pool_slot(w4, "projectile", 0, [1.0, -0.1, 0.1, 0.08, 0.0, 0.0, 0.9, 0.2, 0.1, 0.5, 0.0])
    ms4 = C.slice_model_state(w4)
    obj = ms4[C.OBJECT_TOKEN_OFFSET:C.OBJECT_TOKEN_END].reshape(C.OBJECT_TOKEN_COUNT, C.OBJECT_TOKEN_FEATURES)
    check("object token present flag", obj[0, 0] == 1.0)
    check("object token sorted by priority", obj[0, 11] == C._ROLE_NORM["projectile"])


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


def test_act(agent):
    print("\n[agent.act]")
    ms = C.slice_model_state(fake_wire())
    mv, fr, is_eps = agent.act(ms, epsilon=0.0)
    check("greedy move in 0..8", 0 <= mv <= 8)
    check("greedy fire in 0..8", 0 <= fr <= 8)
    mv, fr, is_eps = agent.act(ms, epsilon=1.0)
    check("epsilon flagged", is_eps is True)
    batch = agent.act_batch([ms, ms, ms], [0.0, 1.0, 0.0])
    check("act_batch returns 3", len(batch) == 3)
    check("act_batch tuples valid", all(0 <= a[0] <= 8 and 0 <= a[1] <= 8 for a in batch))
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
            agent.step(s, (mv, fr), r, ns, done, actor=actor, horizon=1, priority_reward=r)
        check("buffer filled", len(agent.memory) >= C.RL_CONFIG.batch_size)
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
