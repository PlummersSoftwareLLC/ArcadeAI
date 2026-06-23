#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN SOCKET BRIDGE SERVER                                                                     ||
# ||  TCP server bridging Lua (MAME) ↔ Python.  Tempest DQN data-path on Robotron's wire protocol.              ||
# ==================================================================================================================
"""Socket server — receives frames from Lua, queries the branching DQN agent,
returns 5-byte ``>bbBBB`` actions (move_dir, fire_dir, source, start_advanced,
start_level_min).

Game-flow contract (Robotron-specific):
  • Inbound framing: 4-byte big-endian length prefix, then the payload.
  • Payload header ``>HddBIBBBIBB`` (n, subj, obj, done, score, player_alive,
    save, start_pressed, replay_level, num_lasers, wave), then n f32 (big-endian).
  • The model consumes the compact slice of the wire (18 core + 8 lanes × 30
    + 4 derived channels); the full wire is only used for the heuristic expert.
  • Episodes terminate on ``frame.done``.  While ``player_alive`` is false (death
    animation / between lives) we send a neutral action and store no transitions.
  • Reward = clip(obj·obj_scale + subj·subj_scale); both terms are shaped Lua-side.
"""

if __name__ == "__main__":
    print("This is not the main application, run 'main.py' instead")
    exit(1)

import os, sys, time, socket, select, struct, threading, traceback, random, queue
import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Optional

try:
    from .config import (RL_CONFIG, SERVER_CONFIG, metrics, LATEST_MODEL_PATH,
                         game_settings, slice_model_state, WIRE_PARAMS_COUNT)
    from .nstep_buffer import NStepReplayBuffer
    from .model import combine_action, split_joint_action, action_index_to_wire_dir
    from .metrics_display import (
        add_episode_to_dqn100k_window,
        add_episode_to_dqn1m_window,
        add_episode_to_dqn5m_window,
        add_episode_to_dqn_perframe_window,
        add_episode_to_total_windows,
        add_episode_to_eplen_window,
    )
except ImportError:
    from config import (RL_CONFIG, SERVER_CONFIG, metrics, LATEST_MODEL_PATH,
                        game_settings, slice_model_state, WIRE_PARAMS_COUNT)
    from nstep_buffer import NStepReplayBuffer
    from model import combine_action, split_joint_action, action_index_to_wire_dir
    from metrics_display import (
        add_episode_to_dqn100k_window,
        add_episode_to_dqn1m_window,
        add_episode_to_dqn5m_window,
        add_episode_to_dqn_perframe_window,
        add_episode_to_total_windows,
        add_episode_to_eplen_window,
    )

# Robotron heuristic expert — reused from the v3 package (game logic, not PPO).
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../Scripts
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
try:
    # Lean DQN-only extractor: identical behavior to v3.expert.get_expert_action
    # but skips the full (128,32) entity-token tensor the DQN model never uses
    # (~7x faster — keeps high expert ratios from stalling the per-client loop).
    from dqn.expert_fast import fast_expert_action as get_expert_action
except Exception as e:                      # pragma: no cover - expert optional
    print(f"[WARN] Robotron expert unavailable ({e}); expert guidance disabled.")
    get_expert_action = None

_MAX_FRAME_PAYLOAD_BYTES = 4 * 1024 * 1024

# Action source codes (low nibble of the source byte)
_SRC_NONE = 0
_SRC_DQN = 1
_SRC_EPSILON = 2
_SRC_EXPERT = 3
_SRC_EVAL = 4

# Live action diagnostics (set DQN_DEBUG_ACTIONS=1 to enable).  Prints a throttled
# line showing the chosen source, live entity counts, and the exact bytes sent.
_DBG_ACTIONS = os.environ.get("DQN_DEBUG_ACTIONS", "") not in ("", "0", "false", "False")
_DBG_EVERY = max(1, int(os.environ.get("DQN_DEBUG_EVERY", "60")))

# Fire-hold cadence: keep each fire direction stable for this many frames so the
# game registers reliable shots.  Applied Python-side (replaces the old Lua hold)
# so the replay buffer stores the *effective* held fire action, not the raw request.
FIRE_HOLD_FRAMES = max(1, int(getattr(RL_CONFIG, "fire_hold_frames", 4)))


def _apply_fire_hold(cs: dict, raw_fire: int) -> int:
    """Fixed-cadence fire hold.  Returns the effective fire direction to send.

    While a hold is active the previously latched direction is kept and the
    counter decremented; once it expires the freshly requested direction is
    accepted and the hold window restarts.  Fire indices are in model space
    (0-7 = direction, 8 = idle)."""
    cs["fire_pending_dir"] = int(raw_fire)
    count = cs.get("fire_hold_count", 0)
    if count > 0:
        cs["fire_hold_count"] = count - 1
        return int(cs.get("fire_hold_dir", raw_fire))
    next_fire = int(cs.get("fire_pending_dir", raw_fire))
    cs["fire_hold_dir"] = next_fire
    cs["fire_hold_count"] = FIRE_HOLD_FRAMES - 1
    return next_fire


# ── Frame data (parsed from wire) ───────────────────────────────────────────
@dataclass
class FrameData:
    state: np.ndarray
    subjreward: float
    objreward: float
    done: bool
    player_alive: bool
    save_signal: bool
    start_pressed: bool
    level_number: int
    game_score: int
    num_lasers: int


_HDR_FMT = ">HddBIBBBIBB"
_HDR_SIZE = struct.calcsize(_HDR_FMT)


def parse_frame_data(data: bytes) -> Optional[FrameData]:
    """Parse the Robotron binary wire protocol from Lua."""
    if not data or len(data) < _HDR_SIZE:
        return None
    try:
        (n, subj, obj, done, score, alive, save,
         start, replay, lasers, wave) = struct.unpack(_HDR_FMT, data[:_HDR_SIZE])
    except struct.error:
        return None
    base_len = _HDR_SIZE + n * 4
    if len(data) < base_len:
        return None
    state = np.frombuffer(data[_HDR_SIZE:base_len], dtype=">f4", count=n).astype(np.float32)
    if state.shape[0] != n:
        return None
    return FrameData(
        state=state, subjreward=float(subj), objreward=float(obj),
        done=bool(done), player_alive=bool(alive), save_signal=bool(save),
        start_pressed=bool(start), level_number=int(wave),
        game_score=int(score), num_lasers=int(lasers),
    )


# ── Async buffer (queues step() calls to avoid blocking the frame loop) ─────
class AsyncReplayBuffer:
    def __init__(self, agent, batch_size=100, max_queue_size=20000):
        self.agent = agent
        self.batch_size = batch_size
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.running = True
        self._lookback = int(getattr(RL_CONFIG, "pre_death_lookback", 120))
        self._client_indices = {}          # client_id -> deque(maxlen=lookback)
        # Drop accounting (queue overflow on non-critical frames only)
        self.dropped_steps = 0
        self._drop_lock = threading.Lock()
        self._last_drop_warn = 0.0
        self._thread = threading.Thread(target=self._consume, daemon=True)
        self._thread.start()

    def _record_drop(self, n=1):
        with self._drop_lock:
            self.dropped_steps += n
            total = self.dropped_steps
            now = time.time()
            warn = (now - self._last_drop_warn) >= 10.0
            if warn:
                self._last_drop_warn = now
        try:
            metrics.note_replay_drop(n)
        except Exception:
            pass
        if warn:
            print(f"[WARN] Replay queue saturated — dropped {total:,} non-terminal "
                  f"transitions so far (consumer can't keep up)")

    def step_async(self, *args, client_id=None, **kwargs):
        is_terminal = bool(args[4]) if len(args) > 4 else False
        item = ("step", client_id, args, kwargs)
        if is_terminal:
            # Terminal transitions carry the episode-end / death signal — never
            # drop them.  Block briefly (backpressure) instead of discarding.
            try:
                self.queue.put(item, timeout=2.0)
            except queue.Full:
                self._record_drop()
            return
        try:
            self.queue.put(item, timeout=0.05)
        except queue.Full:
            self._record_drop()

    def boost_pre_death(self, client_id):
        # Death-priority boost is critical for credit assignment — don't drop.
        try:
            self.queue.put(("boost", client_id, None, None), timeout=2.0)
        except queue.Full:
            pass

    def _consume(self):
        while self.running:
            try:
                item = self.queue.get(timeout=0.01)
            except queue.Empty:
                continue
            batch = [item]
            while len(batch) < self.batch_size:
                try:
                    batch.append(self.queue.get_nowait())
                except queue.Empty:
                    break
            for cmd, cid, a, kw in batch:
                try:
                    if cmd == "step":
                        idx = self.agent.step(*a, **kw)
                        if cid is not None and idx is not None and idx >= 0:
                            if cid not in self._client_indices:
                                self._client_indices[cid] = deque(maxlen=self._lookback)
                            self._client_indices[cid].append(idx)
                    elif cmd == "boost":
                        self._do_boost(cid)
                except Exception as e:
                    print(f"AsyncReplayBuffer error: {e}")

    def _do_boost(self, client_id):
        indices = self._client_indices.get(client_id)
        if not indices:
            return
        boost = float(getattr(RL_CONFIG, "pre_death_priority_boost", 2.0))
        if boost <= 1.0:
            indices.clear()
            return
        try:
            self.agent.memory.boost_priorities(list(indices), boost)
        except Exception as e:
            print(f"  Pre-death boost error: {e}")
        indices.clear()

    def remove_client(self, client_id):
        self._client_indices.pop(client_id, None)

    def stop(self):
        self.running = False
        while True:
            try:
                cmd, cid, a, kw = self.queue.get_nowait()
                if cmd == "step" and a is not None:
                    self.agent.step(*a, **kw)
                elif cmd == "boost":
                    self._do_boost(cid)
            except queue.Empty:
                break
            except Exception:
                pass
        self._thread.join(timeout=5.0)


class _InferenceRequest:
    __slots__ = ("state", "epsilon", "event", "action")

    def __init__(self, state, epsilon: float):
        self.state = state
        self.epsilon = float(epsilon)
        self.event = threading.Event()
        self.action = None


class AsyncInferenceBatcher:
    """Micro-batch inference requests across clients for better throughput."""

    def __init__(self, agent, max_batch_size=32, max_wait_ms=1.0, request_timeout_ms=50.0):
        self.agent = agent
        self.max_batch_size = max(1, int(max_batch_size))
        self.max_wait_s = max(0.0, float(max_wait_ms) / 1000.0)
        self.request_timeout_s = max(0.001, float(request_timeout_ms) / 1000.0)
        self.queue = queue.Queue(maxsize=20000)
        self.running = True
        self._thread = threading.Thread(target=self._consume, daemon=True, name="InferBatchWorker")
        self._thread.start()

    def infer(self, state, epsilon: float):
        if not self.running:
            return self.agent.act(state, epsilon)
        req = _InferenceRequest(state, epsilon)
        try:
            self.queue.put(req, timeout=self.request_timeout_s)
        except queue.Full:
            return self.agent.act(state, epsilon)
        if not req.event.wait(timeout=self.request_timeout_s):
            return self.agent.act(state, epsilon)
        return req.action if req.action is not None else (0, 0, False)

    def _consume(self):
        while self.running or not self.queue.empty():
            try:
                first = self.queue.get(timeout=0.01)
            except queue.Empty:
                continue

            batch = [first]
            deadline = time.perf_counter() + self.max_wait_s
            while len(batch) < self.max_batch_size:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                try:
                    batch.append(self.queue.get(timeout=remaining))
                except queue.Empty:
                    break

            try:
                states = [r.state for r in batch]
                epsilons = [r.epsilon for r in batch]
                actions = self.agent.act_batch(states, epsilons)
            except Exception as e:
                print(f"AsyncInferenceBatcher error: {e}")
                actions = []

            for idx, req in enumerate(batch):
                act = actions[idx] if idx < len(actions) else None
                if act is None:
                    try:
                        act = self.agent.act(req.state, req.epsilon)
                    except Exception:
                        act = (0, 0, False)
                req.action = act
                req.event.set()

    def stop(self):
        self.running = False
        self._thread.join(timeout=5.0)
        while True:
            try:
                req = self.queue.get_nowait()
            except queue.Empty:
                break
            req.action = (0, 0, False)
            req.event.set()


# ── Socket Server ───────────────────────────────────────────────────────────
class SocketServer:
    def __init__(self, host, port, agent, metrics_wrapper=None):
        self.host = host
        self.port = port
        self.agent = agent
        self.async_buffer = AsyncReplayBuffer(agent) if agent else None
        self.inference_batcher = None
        if agent and bool(getattr(RL_CONFIG, "inference_batching_enabled", True)):
            self.inference_batcher = AsyncInferenceBatcher(
                agent,
                max_batch_size=int(getattr(RL_CONFIG, "inference_batch_max_size", 32)),
                max_wait_ms=float(getattr(RL_CONFIG, "inference_batch_wait_ms", 1.0)),
                request_timeout_ms=float(getattr(RL_CONFIG, "inference_request_timeout_ms", 50.0)),
            )
            print(
                "Async inference batching enabled: "
                f"max_batch={self.inference_batcher.max_batch_size}, "
                f"wait_ms={self.inference_batcher.max_wait_s * 1000.0:.2f}"
            )
        self.metrics = metrics_wrapper if metrics_wrapper is not None else metrics

        self.server_socket = None
        self.running = False
        self.shutdown_event = threading.Event()

        self.clients = {}
        self.client_states = {}
        self.client_lock = threading.Lock()

    def _alloc_id(self):
        with self.client_lock:
            cid = 0
            while cid in self.clients:
                cid += 1
            return cid

    @staticmethod
    def _is_eval_client(cid: int) -> bool:
        stride = int(getattr(RL_CONFIG, "eval_client_stride", 0))
        if stride <= 0:
            return False
        offset = int(getattr(RL_CONFIG, "eval_client_offset", stride - 1)) % stride
        return (int(cid) % stride) == offset

    def _init_client(self, cid):
        n = max(1, int(getattr(RL_CONFIG, "n_step", 1)))
        gamma = float(getattr(RL_CONFIG, "gamma", 0.99))
        nstep = NStepReplayBuffer(n_step=n, gamma=gamma) if n > 1 else None
        eval_only = self._is_eval_client(cid)
        with self.client_lock:
            self.client_states[cid] = {
                "frames": 0, "last_time": time.time(), "fps": 0.0,
                "level_number": 0, "game_score": 0, "last_state": None, "last_action": None,
                "prev_action_source": None,
                "total_reward": 0.0, "ep_dqn_reward": 0.0, "ep_expert_reward": 0.0,
                "ep_subj_reward": 0.0, "ep_obj_reward": 0.0, "ep_frames": 0,
                "ep_dqn_frames": 0,
                "eval_only": eval_only,
                "was_done": False, "nstep": nstep,
                "fire_hold_dir": -1, "fire_hold_count": 0, "fire_pending_dir": -1,
            }
            metrics.client_count = len(self.client_states)

    @staticmethod
    def _recv_exact(sock, n, timeout_s=0.5):
        """Read exactly *n* bytes from a non-blocking socket, or None on EOF/timeout."""
        buf = bytearray()
        deadline = time.time() + timeout_s
        while len(buf) < n:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            try:
                r, _, _ = select.select([sock], [], [], min(0.05, remaining))
            except (OSError, ValueError):
                return None
            if not r:
                continue
            try:
                chunk = sock.recv(n - len(buf))
            except BlockingIOError:
                continue
            except OSError:
                return None
            if not chunk:
                return None
            buf += chunk
        return bytes(buf)

    def _pack_action(self, move_cmd, fire_cmd, source_code):
        _gs = game_settings.snapshot()
        start_adv = 1 if _gs["start_advanced"] else 0
        start_level = max(1, min(255, int(_gs["start_level_min"])))
        source_u8 = int(source_code) & 0x0F
        return struct.pack(">bbBBB", int(move_cmd), int(fire_cmd),
                           source_u8, start_adv, start_level)

    def handle_client(self, sock, cid):
        local_accum = 0
        try:
            sock.setblocking(False)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)

            # Handshake — 2-byte value (preview capability / slot; unused here)
            ping = self._recv_exact(sock, 2, timeout_s=5.0)
            if not ping or len(ping) < 2:
                raise ConnectionError("No handshake")

            BATCH = 8

            while self.running and not self.shutdown_event.is_set():
                # Read 4-byte length header
                hdr = self._recv_exact(sock, 4, timeout_s=0.25)
                if hdr is None:
                    # idle timeout — keep the connection alive
                    continue
                if len(hdr) < 4:
                    raise ConnectionError("EOF")
                dlen = struct.unpack(">I", hdr)[0]
                if dlen <= 0 or dlen > _MAX_FRAME_PAYLOAD_BYTES:
                    raise ConnectionError(f"Invalid payload length {dlen}")

                data = self._recv_exact(sock, dlen, timeout_s=0.5)
                if data is None:
                    raise ConnectionError("Broken payload")

                if len(data) >= 2:
                    n = struct.unpack(">H", data[:2])[0]
                    if n != WIRE_PARAMS_COUNT:
                        print(f"Client {cid}: param mismatch {n} != {WIRE_PARAMS_COUNT}")
                        break
                else:
                    break

                frame = parse_frame_data(data)
                if not frame:
                    sock.sendall(self._pack_action(-1, -1, _SRC_NONE))
                    continue

                # Compact model input (18 core + 8 lanes × 30 + 4 derived)
                model_state = slice_model_state(frame.state)

                with self.client_lock:
                    if cid not in self.client_states:
                        break
                    cs = self.client_states[cid]
                    cs["frames"] += 1
                    cs["level_number"] = frame.level_number
                    cs["game_score"] = frame.game_score
                    now = time.time()
                    el = now - cs["last_time"]
                    if el >= 1.0:
                        cs["fps"] = 1.0 / el
                        cs["last_time"] = now

                # Peak game score is shared metrics state — guard with metrics.lock
                # (not client_lock) to stay consistent with dashboard reads.
                metrics.note_game_score(frame.game_score)

                local_accum += 1
                if local_accum >= BATCH:
                    metrics.update_frame_count(delta=local_accum)
                    local_accum = 0
                    metrics.update_epsilon()
                    metrics.update_expert_ratio()
                    self._calc_avg_game_state()

                # ── Process previous step ───────────────────────────────
                if cs.get("last_state") is not None and cs.get("last_action") is not None:
                    mv_i, fr_i = cs["last_action"]
                    subj_r = float(frame.subjreward) * RL_CONFIG.subj_reward_scale
                    obj_r = float(frame.objreward) * RL_CONFIG.obj_reward_scale
                    total_r = obj_r + subj_r
                    clip = RL_CONFIG.death_reward_clip if frame.done else RL_CONFIG.reward_clip
                    total_r = max(-clip, min(clip, total_r))

                    eval_only = bool(cs.get("eval_only", False))
                    if self.agent and not eval_only:
                        tag = cs.get("prev_action_source", "dqn")
                        nstep = cs.get("nstep")
                        if nstep is not None:
                            joint = combine_action(mv_i, fr_i)
                            matured = nstep.add(cs["last_state"], joint, total_r,
                                                model_state, bool(frame.done),
                                                actor=tag, priority_reward=total_r)
                            for s0, a, Rn, pR, sn, dn, h, act in matured:
                                mv_n, fr_n = split_joint_action(a)
                                self.async_buffer.step_async(
                                    s0, (mv_n, fr_n), Rn, sn, bool(dn),
                                    client_id=cid, actor=act, horizon=int(h), priority_reward=pR)
                        else:
                            self.async_buffer.step_async(
                                cs["last_state"], (mv_i, fr_i), total_r,
                                model_state, bool(frame.done), client_id=cid,
                                actor=tag, horizon=1, priority_reward=total_r)

                    cs["total_reward"] += total_r
                    cs["ep_subj_reward"] = cs.get("ep_subj_reward", 0.0) + subj_r
                    cs["ep_obj_reward"] = cs.get("ep_obj_reward", 0.0) + obj_r
                    cs["ep_frames"] = cs.get("ep_frames", 0) + 1
                    src = cs.get("prev_action_source")
                    if eval_only:
                        pass
                    elif src in ("dqn", "epsilon"):
                        cs["ep_dqn_reward"] += total_r
                        cs["ep_dqn_frames"] = cs.get("ep_dqn_frames", 0) + 1
                    elif src == "expert":
                        cs["ep_expert_reward"] += total_r

                # ── Terminal ────────────────────────────────────────────
                if frame.done:
                    eval_only = bool(cs.get("eval_only", False))
                    if self.async_buffer is not None and not eval_only:
                        self.async_buffer.boost_pre_death(cid)
                    if not cs.get("was_done", False):
                        ep_len = cs.get("ep_frames", 0)
                        if eval_only:
                            metrics.add_eval_episode_reward(
                                cs["total_reward"], frame.game_score, frame.level_number, length=ep_len)
                        else:
                            metrics.add_episode_reward(
                                cs["total_reward"], cs["ep_dqn_reward"], cs["ep_expert_reward"],
                                cs.get("ep_subj_reward", 0.0), cs.get("ep_obj_reward", 0.0),
                                length=ep_len)
                            try:
                                ep_dqn = cs["ep_dqn_reward"]
                                add_episode_to_dqn100k_window(ep_dqn, ep_len)
                                add_episode_to_dqn1m_window(ep_dqn, ep_len)
                                add_episode_to_dqn5m_window(ep_dqn, ep_len)
                                add_episode_to_dqn_perframe_window(ep_dqn, cs.get("ep_dqn_frames", 0), ep_len)
                                add_episode_to_total_windows(cs["total_reward"], ep_len)
                                add_episode_to_eplen_window(ep_len)
                            except Exception:
                                pass
                    cs["was_done"] = True
                    try:
                        sock.sendall(self._pack_action(-1, -1, _SRC_NONE))
                    except Exception:
                        break
                    cs["last_state"] = cs["last_action"] = None
                    cs["prev_action_source"] = None
                    cs["total_reward"] = cs["ep_dqn_reward"] = cs["ep_expert_reward"] = 0.0
                    cs["ep_subj_reward"] = cs["ep_obj_reward"] = 0.0
                    cs["ep_frames"] = 0
                    cs["ep_dqn_frames"] = 0
                    cs["fire_hold_dir"] = -1
                    cs["fire_hold_count"] = 0
                    cs["fire_pending_dir"] = -1
                    continue

                if cs.get("was_done"):
                    cs["was_done"] = False
                    cs["total_reward"] = cs["ep_dqn_reward"] = cs["ep_expert_reward"] = 0.0
                    cs["ep_subj_reward"] = cs["ep_obj_reward"] = 0.0
                    cs["ep_frames"] = 0
                    cs["ep_dqn_frames"] = 0

                # ── Not playable (death animation / between lives) ──────
                if not frame.player_alive:
                    cs["last_state"] = cs["last_action"] = None
                    cs["prev_action_source"] = None
                    cs["fire_hold_dir"] = -1
                    cs["fire_hold_count"] = 0
                    cs["fire_pending_dir"] = -1
                    if (cs.get("nstep") is not None):
                        cs["nstep"].reset()
                    try:
                        sock.sendall(self._pack_action(-1, -1, _SRC_NONE))
                    except Exception:
                        break
                    continue

                # ── Choose action ───────────────────────────────────────
                metrics.increment_total_controls()
                mv_idx, fr_idx = 8, 8           # idle defaults
                action_source = "none"

                # Fire-hold: while a hold is active, lock the fire direction so
                # the expert/model don't fight the cadence — keeps move quality
                # and the stored action consistent with what the game does.
                fire_update_open = cs.get("fire_hold_count", 0) <= 0
                locked_fire = None
                if not fire_update_open:
                    held = cs.get("fire_hold_dir", -1)
                    locked_fire = max(0, min(8, held)) if held >= 0 else 8

                if self.agent:
                    eval_only = bool(cs.get("eval_only", False))
                    expert_ratio = 0.0 if eval_only else metrics.get_expert_ratio()
                    use_expert = (random.random() < expert_ratio) and not metrics.override_expert and not eval_only

                    if use_expert and get_expert_action is not None:
                        # Clamp wave to >=1 like v3 — the expert's rescue/tank-wave
                        # logic keys off wave_number and misbehaves at 0.
                        wave = max(1, int(frame.level_number))
                        mv_idx, fr_idx = get_expert_action(frame.state, wave,
                                                           locked_fire=locked_fire)
                        action_source = "expert"
                    else:
                        epsilon = float(getattr(RL_CONFIG, "eval_epsilon", 0.0)) if eval_only else metrics.get_effective_epsilon()
                        t0 = time.perf_counter()
                        if self.inference_batcher is not None:
                            mv_idx, fr_idx, is_eps = self.inference_batcher.infer(model_state, epsilon)
                        else:
                            mv_idx, fr_idx, is_eps = self.agent.act(model_state, epsilon)
                        metrics.add_inference_time(time.perf_counter() - t0)
                        action_source = "eval" if eval_only else ("epsilon" if is_eps else "dqn")
                    if locked_fire is not None:
                        fr_idx = locked_fire

                if action_source in ("dqn", "epsilon"):
                    metrics.update_learner_frame_count()

                # Apply fire hold → the effective fire is what we send AND store.
                effective_fire = _apply_fire_hold(cs, int(fr_idx))

                cs["last_state"] = model_state
                cs["last_action"] = (int(mv_idx), int(effective_fire))
                cs["prev_action_source"] = action_source

                move_cmd = action_index_to_wire_dir(int(mv_idx))
                fire_cmd = action_index_to_wire_dir(int(effective_fire))
                src_code = {"dqn": _SRC_DQN, "epsilon": _SRC_EPSILON,
                            "expert": _SRC_EXPERT, "eval": _SRC_EVAL}.get(action_source, _SRC_NONE)

                if _DBG_ACTIONS:
                    dn = cs.get("dbg_n", 0) + 1
                    cs["dbg_n"] = dn
                    if dn % _DBG_EVERY == 0:
                        try:
                            from v3.state_processor import _collect_entity_slots as _ces
                            slots = _ces(np.asarray(frame.state, dtype=np.float32))
                            nh = sum(1 for s in slots if s["pool"] == "human")
                            nd = sum(1 for s in slots if s["pool"] == "danger")
                        except Exception as _e:
                            slots, nh, nd = [], -1, -1
                        try:
                            mq, fq = self.agent.debug_q_spread(model_state)
                            mspread = max(mq) - min(mq)
                            fspread = max(fq) - min(fq)
                            qinfo = (f"mQ[{min(mq):+.2f},{max(mq):+.2f}]d{mspread:.3f} "
                                     f"fQ[{min(fq):+.2f},{max(fq):+.2f}]d{fspread:.3f}")
                        except Exception:
                            qinfo = "qspread=err"
                        print(
                            f"[DBG] src={action_source:<7} n={len(frame.state)} "
                            f"ents={len(slots)}(H{nh}/D{nd}) wave={int(frame.level_number)} "
                            f"mv={int(mv_idx)}->{move_cmd} fr={int(effective_fire)}->{fire_cmd} "
                            f"xr={metrics.get_expert_ratio():.2f} eps={metrics.get_effective_epsilon():.2f} "
                            f"{qinfo}", flush=True)

                try:
                    sock.sendall(self._pack_action(move_cmd, fire_cmd, src_code))
                except Exception:
                    break

        except Exception as e:
            print(f"Client {cid} error: {e}")
            traceback.print_exc()
        finally:
            # Flush frames accumulated since the last batch so decay schedules
            # (epsilon / expert ratio) don't lag when a client disconnects.
            if local_accum > 0:
                try:
                    metrics.update_frame_count(delta=local_accum)
                except Exception:
                    pass
                local_accum = 0
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
            with self.client_lock:
                self.client_states.pop(cid, None)
                self.clients[cid] = None
                metrics.client_count = sum(1 for v in self.clients.values() if v is not None)
            if self.async_buffer is not None:
                self.async_buffer.remove_client(cid)
            threading.Timer(1.0, self._cleanup).start()

    def _cleanup(self):
        with self.client_lock:
            dead = [k for k, v in self.clients.items() if v is None]
            for k in dead:
                del self.clients[k]
            metrics.client_count = len(self.clients)

    def _calc_avg_game_state(self):
        try:
            with self.client_lock:
                lvls = [s.get("level_number", 0) for s in self.client_states.values() if s.get("level_number", 0) >= 0]
                scores = [s.get("game_score", 0) for s in self.client_states.values()]
                avg_level = sum(lvls) / len(lvls) if lvls else 0.0
                avg_score = sum(scores) / len(scores) if scores else 0.0
                peak_level = max(lvls) if lvls else None
            metrics.note_game_state_averages(avg_level, avg_score, peak_level)
        except Exception:
            pass

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        for i in range(10):
            try:
                if self.shutdown_event.is_set():
                    return
                self.server_socket.bind((self.host, self.port))
                break
            except OSError as e:
                if e.errno in (98, 48):
                    print(f"Port {self.port} busy, retry {i+1}/10")
                    time.sleep(1.0)
                else:
                    raise
        else:
            raise OSError(f"Cannot bind {self.host}:{self.port}")

        self.server_socket.listen(SERVER_CONFIG.max_clients)
        self.server_socket.setblocking(False)
        self.running = True
        print(f"SocketServer listening on {self.host}:{self.port}")

        try:
            while self.running and not self.shutdown_event.is_set():
                try:
                    rd, _, _ = select.select([self.server_socket], [], [], 0.05)
                except (OSError, ValueError):
                    if self.shutdown_event.is_set():
                        break
                    raise
                if not self.server_socket:
                    break
                if self.server_socket in rd:
                    try:
                        cs, addr = self.server_socket.accept()
                    except OSError:
                        continue
                    cid = self._alloc_id()
                    self._init_client(cid)
                    t = threading.Thread(target=self.handle_client, args=(cs, cid), daemon=True)
                    with self.client_lock:
                        self.clients[cid] = t
                    t.start()
        except Exception as e:
            if not self.shutdown_event.is_set():
                print(f"Server error: {e}")
                traceback.print_exc()
        finally:
            self.stop()

    def stop(self):
        if self.shutdown_event.is_set() and not self.running:
            return
        self.running = False
        self.shutdown_event.set()
        if self.inference_batcher:
            print("Stopping async inference batcher...")
            self.inference_batcher.stop()
            self.inference_batcher = None
        if self.async_buffer:
            print("Flushing async replay buffer...")
            self.async_buffer.stop()
            self.async_buffer = None
        try:
            if self.server_socket:
                try:
                    self.server_socket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.server_socket.close()
                self.server_socket = None
        except Exception:
            pass
