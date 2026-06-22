#!/usr/bin/env python3
"""Robotron AI v3 — Socket server bridge.

TCP server bridging Lua (MAME) ↔ Python for the v3 PPO architecture.
Preserves the exact binary wire protocol from v2 so the Lua side
is completely unchanged.

Wire protocol:
  Inbound (Lua → Python):
    4-byte big-endian length
    Header: >HddBIBBBIBB (n_params, subj_reward, obj_reward, done,
            score, player_alive, save, start_pressed, replay_level,
            num_lasers, wave_number)
    State: n × float32 big-endian
    Optional: preview data

  Outbound (Python → Lua):
    5 bytes: move_cmd(i8), fire_cmd(i8), source_byte(u8),
             start_advanced(u8), start_level_min(u8)
"""

import os
import sys
import time
import struct
import socket
import select
import threading
import traceback
import random
import numpy as np
import torch
from collections import deque
from typing import Optional
from dataclasses import dataclass

from .config import CONFIG, GAME_SETTINGS, WIRE_PARAMS_COUNT
from .agent import PPOAgent
from .expert import get_expert_action, get_expert_action_from_entities
from .state_processor import extract_entities
from .reward import shape_reward_with_components, move_potential
from .metrics_display import add_episode_to_reward_windows, add_episode_to_eplen_windows
from .rollout_buffer import RolloutBuffer

# ── Constants ───────────────────────────────────────────────────────────────

FIRE_HOLD_FRAMES = 4
_MAX_FRAME_PAYLOAD_BYTES = 4 * 1024 * 1024
_DIAG = 0.70710678
_FIRE_DIR_VECTORS = (
    (0.0, -1.0), (_DIAG, -_DIAG), (1.0, 0.0), (_DIAG, _DIAG),
    (0.0, 1.0), (-_DIAG, _DIAG), (-1.0, 0.0), (-_DIAG, -_DIAG),
)
_START_PULSE_VALID_FRAMES = 240
_GAMEPLAY_RESET_DEAD_FRAMES = 180
_GAMEPLAY_PLAUSIBLE_START_STREAK = 8
_GAMEPLAY_PROGRESS_ALIVE_STREAK = 30
_ACTION_MIX_WINDOW = 50_000


def _env_flag(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return bool(default)
    return raw not in {"0", "false", "off", "no"}


# ── Frame data (parsed from wire) ──────────────────────────────────────────

@dataclass
class FrameData:
    state: np.ndarray
    subjreward: float
    objreward: float
    done: bool
    player_alive: bool
    save_signal: bool
    start_pressed: bool = False
    level_number: int = 0
    game_score: int = 0
    next_replay_level: int = 0
    num_lasers: int = 0
    preview_width: int = 0
    preview_height: int = 0
    preview_format: int = 0
    preview_pixels: Optional[bytes] = None
    preview_encoded_format: int = 0
    preview_encoded_bytes: int = 0
    preview_raw_bytes: int = 0


def parse_frame_data(data: bytes, parse_preview: bool = False) -> Optional[FrameData]:
    """Parse the binary wire protocol from Lua."""
    fmt = ">HddBIBBBIBB"
    hdr_size = struct.calcsize(fmt)
    if not data or len(data) < hdr_size:
        return None

    vals = struct.unpack(fmt, data[:hdr_size])
    n, subj, obj, done, score, alive, save, start, replay, lasers, wave = vals

    base_len = hdr_size + n * 4
    if len(data) < base_len:
        return None

    state = np.frombuffer(data[hdr_size:base_len], dtype=">f4", count=n).astype(np.float32)
    if state.shape[0] != n:
        return None

    preview_width = preview_height = preview_format = 0
    preview_pixels = None
    preview_encoded_format = preview_encoded_bytes = preview_raw_bytes = 0

    if len(data) > base_len:
        if len(data) < (base_len + 4):
            return None
        preview_len = struct.unpack(">I", data[base_len:base_len + 4])[0]
        tail_start = base_len + 4
        tail_end = tail_start + int(preview_len)
        if tail_end != len(data):
            return None
        if (not parse_preview) and preview_len > 0:
            preview_len = 0
        elif preview_len > 0 and preview_len < 5:
            return None
        if preview_len >= 5:
            preview_width, preview_height, preview_format = struct.unpack(
                ">HHB", data[tail_start:tail_start + 5]
            )
            pixels = data[tail_start + 5:tail_end]
            if preview_width <= 0 or preview_height <= 0 or len(pixels) <= 0:
                return None
            expected_px = preview_width * preview_height * 2
            pf = int(preview_format)
            preview_encoded_format = pf
            preview_encoded_bytes = len(pixels)
            preview_raw_bytes = expected_px
            if pf == 1:
                if len(pixels) != expected_px:
                    return None
                preview_pixels = bytes(pixels)
            elif pf == 2:
                # LZSS decompression
                out = bytearray(expected_px)
                oi = si = 0
                plen = len(pixels)
                ok = True
                while oi < expected_px and si < plen:
                    flags = pixels[si]; si += 1
                    for bit in range(8):
                        if oi >= expected_px:
                            break
                        if (flags >> bit) & 1:
                            if (si + 1) >= plen:
                                ok = False; break
                            b1, b2 = pixels[si], pixels[si + 1]; si += 2
                            mlen = ((b1 >> 4) & 0x0F) + 3
                            dist = ((b1 & 0x0F) << 8) | b2
                            if dist <= 0 or dist > oi:
                                ok = False; break
                            src_idx = oi - dist
                            for _ in range(mlen):
                                if oi >= expected_px:
                                    break
                                out[oi] = out[src_idx]; oi += 1; src_idx += 1
                        else:
                            if si >= plen:
                                ok = False; break
                            out[oi] = pixels[si]; oi += 1; si += 1
                    if not ok:
                        break
                if (not ok) or (oi != expected_px):
                    return None
                preview_pixels = bytes(out)
                preview_format = 1
            elif pf == 3:
                # Word-RLE decompression
                out = bytearray(expected_px)
                oi = si = 0
                plen = len(pixels)
                ok = True
                while si < plen and oi < expected_px:
                    ctrl = pixels[si]; si += 1
                    words = (ctrl & 0x7F) + 1
                    if (ctrl & 0x80) != 0:
                        if (si + 1) >= plen:
                            ok = False; break
                        b0, b1 = pixels[si], pixels[si + 1]; si += 2
                        need = words * 2
                        if (oi + need) > expected_px:
                            ok = False; break
                        for _ in range(words):
                            out[oi] = b0; out[oi + 1] = b1; oi += 2
                    else:
                        need = words * 2
                        if (si + need) > plen or (oi + need) > expected_px:
                            ok = False; break
                        out[oi:oi + need] = pixels[si:si + need]
                        oi += need; si += need
                if (not ok) or (oi != expected_px) or (si != plen):
                    return None
                preview_pixels = bytes(out)
                preview_format = 1
            else:
                return None

    return FrameData(
        state=state,
        subjreward=subj,
        objreward=obj,
        done=bool(done),
        player_alive=bool(alive),
        save_signal=bool(save),
        start_pressed=bool(start),
        level_number=int(wave),
        game_score=int(score),
        next_replay_level=int(replay),
        num_lasers=int(lasers),
        preview_width=int(preview_width),
        preview_height=int(preview_height),
        preview_format=int(preview_format),
        preview_pixels=preview_pixels,
        preview_encoded_format=int(preview_encoded_format),
        preview_encoded_bytes=int(preview_encoded_bytes),
        preview_raw_bytes=int(preview_raw_bytes),
    )


def _frame_confirms_gameplay(cs: dict, frame: FrameData) -> bool:
    pulse_confirms_gameplay = (
        cs.get("start_pulse_window", 0) > 0
        and cs.get("alive_streak", 0) >= 15
        and cs.get("plausible_start_streak", 0) >= _GAMEPLAY_PLAUSIBLE_START_STREAK
    )
    progress_confirms_gameplay = (
        frame.player_alive
        and cs.get("alive_streak", 0) >= _GAMEPLAY_PROGRESS_ALIVE_STREAK
        and (frame.game_score > 0 or frame.level_number > 1)
    )
    return bool(pulse_confirms_gameplay or progress_confirms_gameplay)


# ── Action encoding (matching game's joystick directions) ──────────────────

def encode_action_to_game(move_dir: int, fire_dir: int) -> tuple[int, int]:
    """Convert model action indices to game joystick commands.

    move/fire 0-7 map to game directions 0-7.
    move/fire 8 (idle) maps to game -1 (no input).
    """
    move_cmd = int(move_dir) if 0 <= move_dir <= 7 else -1
    fire_cmd = int(fire_dir) if 0 <= fire_dir <= 7 else -1
    return move_cmd, fire_cmd


# ── Fire hold logic ─────────────────────────────────────────────────────────

def _apply_fire_hold(cs: dict, raw_fire: int) -> int:
    """Fixed-cadence fire hold for LSPROC's 3-stable-frame requirement."""
    cs["fire_pending_dir"] = int(raw_fire)
    count = cs.get("fire_hold_count", 0)
    if count > 0:
        cs["fire_hold_count"] = count - 1
        return cs.get("fire_hold_dir", raw_fire)
    next_fire = int(cs.get("fire_pending_dir", raw_fire))
    cs["fire_hold_dir"] = next_fire
    cs["fire_hold_count"] = FIRE_HOLD_FRAMES - 1
    return next_fire


def _stored_action_label(cs: dict, key: str, default: int = 8) -> int:
    """Read a stored action label while preserving valid action 0."""
    return int(cs.get(key, default))


# ── Metrics (lightweight rolling stats) ─────────────────────────────────────

class Metrics:
    """Thread-safe rolling metrics for the v3 system."""

    def __init__(self):
        self.lock = threading.Lock()
        self.total_frames = 0
        self.episode_rewards = deque(maxlen=200)
        self.reward_components = deque(maxlen=200)
        self.episode_lengths = deque(maxlen=200)
        self.fps_window = deque(maxlen=60)
        self._policy_sampled_window = deque()
        self._policy_sampled_count = 0
        # Cumulative count of frames the policy itself drove (excludes expert /
        # epsilon). Drives the guidance schedules when schedule_on_policy_frames.
        self.policy_frames = 0
        self.peak_game_score = 0
        self.avg_game_score = 0.0
        self.total_games_played = 0
        self.episodes_this_run = 0
        self.client_count = 0
        self.web_client_count = 0
        self.avg_level = 0.0
        self.peak_level = 0.0
        self._level_window = deque(maxlen=200)
        self._game_scores = deque(maxlen=200)
        self._last_fps_time = time.time()
        self._fps_frames = 0
        # Preview frame data
        self.preview_capture_enabled = True
        self.hud_enabled = True
        self.game_preview_seq = 0
        self.game_preview_client_id = -1
        self.game_preview_width = 0
        self.game_preview_height = 0
        self.game_preview_format = ""
        self.game_preview_data = b""
        self.game_preview_updated_ts = 0.0
        self.game_preview_source_format = ""
        self.game_preview_encoded_bytes = 0
        self.game_preview_raw_bytes = 0
        self.game_preview_compression_ratio = 1.0
        self.game_preview_fps = 0.0
        self.total_inference_time = 0.0
        self.total_inference_requests = 0
        self.total_expert_time = 0.0
        self.total_expert_requests = 0
        # Reference to the server for client row queries
        self.global_server = None

    def update_frame(self):
        with self.lock:
            self.total_frames += 1
            self._fps_frames += 1
            now = time.time()
            elapsed = now - self._last_fps_time
            if elapsed >= 1.0:
                self.fps_window.append(self._fps_frames / elapsed)
                self._fps_frames = 0
                self._last_fps_time = now

    def add_episode(
        self,
        reward: float,
        length: int,
        level: float = 0.0,
        game_score: int = 0,
        reward_components: dict[str, float] | None = None,
    ):
        with self.lock:
            self.episode_rewards.append(reward)
            self.reward_components.append(dict(reward_components or {}))
            self.episode_lengths.append(length)
            self.episodes_this_run += 1
            if level > 0:
                self._level_window.append(level)
                self.avg_level = sum(self._level_window) / len(self._level_window)
                if level > self.peak_level:
                    self.peak_level = level
            self._game_scores.append(int(game_score))
            self.avg_game_score = sum(self._game_scores) / len(self._game_scores)
            self.total_games_played += 1

    def update_client_count(self, count: int):
        with self.lock:
            self.client_count = count

    def add_inference_time(self, seconds: float):
        with self.lock:
            self.total_inference_time += max(0.0, float(seconds))
            self.total_inference_requests += 1

    def add_expert_time(self, seconds: float):
        with self.lock:
            self.total_expert_time += max(0.0, float(seconds))
            self.total_expert_requests += 1

    def record_policy_sampled(self, policy_sampled: bool):
        with self.lock:
            sampled = bool(policy_sampled)
            if sampled:
                self.policy_frames += 1
            if len(self._policy_sampled_window) >= _ACTION_MIX_WINDOW:
                dropped = self._policy_sampled_window.popleft()
                if dropped:
                    self._policy_sampled_count = max(0, self._policy_sampled_count - 1)
            self._policy_sampled_window.append(sampled)
            if sampled:
                self._policy_sampled_count += 1

    @property
    def avg_reward(self) -> float:
        with self.lock:
            if not self.episode_rewards:
                return 0.0
            return sum(self.episode_rewards) / len(self.episode_rewards)

    def avg_reward_components(self) -> dict[str, float]:
        with self.lock:
            if not self.reward_components:
                return {}
            keys = ("score", "subj", "surv", "prox", "death", "wave", "move", "clip")
            n = len(self.reward_components)
            return {
                key: sum(float(row.get(key, 0.0)) for row in self.reward_components) / n
                for key in keys
            }

    @property
    def avg_ep_len(self) -> float:
        with self.lock:
            if not self.episode_lengths:
                return 0.0
            return sum(self.episode_lengths) / len(self.episode_lengths)

    @property
    def fps(self) -> float:
        with self.lock:
            if not self.fps_window:
                return 0.0
            return sum(self.fps_window) / len(self.fps_window)

    @property
    def policy_sampled_fraction(self) -> float:
        with self.lock:
            total = len(self._policy_sampled_window)
            if total <= 0:
                return 0.0
            return float(self._policy_sampled_count) / float(total)


# ── Batched inference ───────────────────────────────────────────────────────

class _InferenceRequest:
    __slots__ = ("tensors", "need_actions", "result", "event")

    def __init__(self, tensors: dict, need_actions: bool):
        self.tensors = tensors          # dict of (1, ...) tensors on CPU
        self.need_actions = need_actions # True → sample actions; False → value only
        self.result: Optional[dict] = None
        self.event = threading.Event()


class InferenceBatcher:
    """Dedicated GPU inference thread that batches requests from client threads.

    Client threads call submit_action() or submit_value() which block until
    the batch is processed.  The GPU thread collects requests, concatenates
    tensors along dim 0, runs one forward pass for the whole batch, then
    distributes the per-sample results back via threading events.

    GPU isolation strategy:
      - Multi-GPU: inference runs on infer_device with infer_net — completely
        independent of training on train_device.  No lock needed.
      - Single-GPU: inference and training share one nn.Module, so a gpu_lock
        serializes forward/backward/optimizer mutation even when CUDA streams
        exist. Streams do not make module weight updates thread-safe.
      - CPU/MPS: falls back to a simple gpu_lock (same as before).
    """

    def __init__(self, agent, max_batch: int = 64, max_wait_ms: float = 1.5,
                 client_count_fn=None):
        self.agent = agent
        self.net = agent.get_inference_net()
        self.device = agent.infer_device
        self.stream = agent.infer_stream        # may be None (CPU/MPS)
        self._multi_gpu = agent._multi_gpu
        self.max_batch = max_batch
        self.max_wait_s = max_wait_ms / 1000.0
        # Expected number of clients that may submit each cycle. Because every
        # client thread BLOCKS on its own result, in-flight requests can never
        # exceed the connected-client count — so the straggler window is closed
        # the instant that many have arrived instead of waiting for an
        # unreachable max_batch.
        self._client_count_fn = client_count_fn or (lambda: max_batch)
        self._queue: deque[_InferenceRequest] = deque()
        # A single condition variable drives the producer→consumer hand-off.
        # Its internal lock guards _queue; notify() wakes the GPU thread the
        # moment a request is enqueued, so batches coalesce with no
        # fixed-interval polling.
        self._cond = threading.Condition()
        self._stopped = False
        # gpu_lock is needed whenever inference and training share the same
        # network object. Multi-GPU uses a separate frozen inference copy.
        self.gpu_lock = threading.Lock()
        self._use_gpu_lock = not self._multi_gpu
        self._thread = threading.Thread(target=self._run, daemon=True, name="infer-batch")
        self._thread.start()

    def stop(self):
        with self._cond:
            self._stopped = True
            self._cond.notify_all()

    def submit_action(self, tensors: dict) -> dict:
        """Submit tensors for action sampling.  Blocks until result ready.

        Returns dict: move_action, fire_action, log_prob, entropy, value
        """
        req = _InferenceRequest(tensors, need_actions=True)
        with self._cond:
            self._queue.append(req)
            self._cond.notify()
        req.event.wait()
        return req.result

    def submit_value(self, tensors: dict) -> float:
        """Submit tensors for value-only estimation.  Blocks until ready.

        Returns scalar value estimate.
        """
        req = _InferenceRequest(tensors, need_actions=False)
        with self._cond:
            self._queue.append(req)
            self._cond.notify()
        req.event.wait()
        return req.result["value"]

    def _run(self):
        """GPU thread main loop: collect → batch → forward → distribute."""
        fallback = {
            "move_action": 0, "fire_action": 0,
            "move_log_prob": 0.0, "fire_log_prob": 0.0,
            "log_prob": 0.0, "entropy": 0.0, "value": 0.0,
        }
        while not self._stopped:
            batch: list[_InferenceRequest] = []
            with self._cond:
                # Block until the first request lands (or shutdown is signalled).
                while not self._queue and not self._stopped:
                    self._cond.wait(timeout=0.05)
                if self._stopped:
                    break

                # First request is in. Open a short window so the rest of the
                # active clients can join this same GPU launch, but fire the
                # instant every active client has submitted — they each block on
                # their result, so the queue can't grow past the client count.
                target = min(self.max_batch, max(1, int(self._client_count_fn())))
                deadline = time.monotonic() + self.max_wait_s
                while True:
                    while self._queue and len(batch) < self.max_batch:
                        batch.append(self._queue.popleft())
                    if len(batch) >= target:
                        break  # every active client has checked in — go now
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    # Sleep until the next submit notifies us or the window ends;
                    # no fixed-interval polling.
                    self._cond.wait(timeout=remaining)

            if not batch:
                continue

            try:
                self._process_batch(batch)
            except Exception:
                # On error return fallbacks so client threads don't hang
                for req in batch:
                    if req.result is None:
                        req.result = dict(fallback)
                    req.event.set()

        # Shutdown: release any clients still blocked on a result.
        with self._cond:
            pending = list(self._queue)
            self._queue.clear()
        for req in pending:
            if req.result is None:
                req.result = dict(fallback)
            req.event.set()

    @torch.no_grad()
    def _process_batch(self, batch: list[_InferenceRequest]):
        """Cat tensors, single forward pass, split results, signal events."""
        # Concatenate along batch dim
        efs = torch.cat([r.tensors["entity_features"] for r in batch], dim=0).to(self.device, non_blocking=True)
        ems = torch.cat([r.tensors["entity_mask"] for r in batch], dim=0).to(self.device, non_blocking=True)
        gcs = torch.cat([r.tensors["global_context"] for r in batch], dim=0).to(self.device, non_blocking=True)
        mafs = torch.cat([r.tensors["move_action_features"] for r in batch], dim=0).to(self.device, non_blocking=True)
        fafs = torch.cat([r.tensors["fire_action_features"] for r in batch], dim=0).to(self.device, non_blocking=True)

        if self._use_gpu_lock:
            with self.gpu_lock:
                if self.stream is not None:
                    with torch.cuda.stream(self.stream):
                        self.net.eval()
                        out = self.net.forward(efs, ems, gcs, mafs, fafs)
                    self.stream.synchronize()
                else:
                    self.net.eval()
                    out = self.net.forward(efs, ems, gcs, mafs, fafs)
        else:
            if self.stream is not None:
                with torch.cuda.stream(self.stream):
                    self.net.eval()
                    out = self.net.forward(efs, ems, gcs, mafs, fafs)
                self.stream.synchronize()
            else:
                self.net.eval()
                out = self.net.forward(efs, ems, gcs, mafs, fafs)

        # NaN-safe logit clamping
        move_logits = out["move_logits"].clamp(-50.0, 50.0)
        fire_logits = out["fire_logits"].clamp(-50.0, 50.0)
        values = out["value"]
        if torch.isnan(move_logits).any() or torch.isinf(move_logits).any():
            move_logits = torch.zeros_like(move_logits)
        if torch.isnan(fire_logits).any() or torch.isinf(fire_logits).any():
            fire_logits = torch.zeros_like(fire_logits)
        if torch.isnan(values).any():
            values = torch.where(torch.isnan(values), torch.zeros_like(values), values)

        # Sample actions (cheap — kept on GPU for the batch)
        move_dist = torch.distributions.Categorical(logits=move_logits)
        fire_dist = torch.distributions.Categorical(logits=fire_logits)
        move_actions = move_dist.sample()
        fire_actions = fire_dist.sample()
        move_log_probs = move_dist.log_prob(move_actions)
        fire_log_probs = fire_dist.log_prob(fire_actions)
        log_probs = move_log_probs + fire_log_probs
        entropies = move_dist.entropy() + fire_dist.entropy()

        # One GPU→CPU transfer per tensor, then a single C-level .tolist()
        # conversion each. Avoids ~7×B per-element .item() Python round-trips
        # when fanning results back out to 8-16 client threads.
        move_actions_l = move_actions.cpu().tolist()
        fire_actions_l = fire_actions.cpu().tolist()
        move_log_probs_l = move_log_probs.cpu().tolist()
        fire_log_probs_l = fire_log_probs.cpu().tolist()
        log_probs_l = log_probs.cpu().tolist()
        entropies_l = entropies.cpu().tolist()
        values_l = values.cpu().tolist()

        # Distribute results back to client threads
        for i, req in enumerate(batch):
            if req.need_actions:
                req.result = {
                    "move_action": int(move_actions_l[i]),
                    "fire_action": int(fire_actions_l[i]),
                    "move_log_prob": float(move_log_probs_l[i]),
                    "fire_log_prob": float(fire_log_probs_l[i]),
                    "log_prob": float(log_probs_l[i]),
                    "entropy": float(entropies_l[i]),
                    "value": float(values_l[i]),
                }
            else:
                req.result = {"value": float(values_l[i])}
            req.event.set()


# ── Socket Server ───────────────────────────────────────────────────────────

class SocketServer:
    """TCP server bridging MAME/Lua clients to the PPO agent.

    Each MAME instance connects on its own TCP socket. The server
    manages per-client state, frame processing, action selection,
    and rollout collection.
    """

    def __init__(
        self,
        agent: PPOAgent,
        host: str = None,
        port: int = None,
        max_clients: int = None,
    ):
        cfg = CONFIG.server
        self.agent = agent
        self.host = host or cfg.host
        self.port = port or cfg.port
        self.max_clients = max_clients or cfg.max_clients

        self.metrics = Metrics()
        self.metrics.total_frames = max(0, int(getattr(agent, "total_frames", 0) or 0))
        self.metrics.policy_frames = max(0, int(getattr(agent, "policy_frames", 0) or 0))
        self.metrics.global_server = self
        self.running = False
        self.shutdown_event = threading.Event()
        self.client_states: dict[int, dict] = {}
        self.client_lock = threading.Lock()
        self._next_cid = 0
        self.preview_cid: Optional[int] = None

        # ── Training: async transition collection ────────────────────
        # Transitions queued from client threads, drained by training thread.
        self._transition_queue: deque = deque()
        self._transition_lock = threading.Lock()
        self._train_start_lock = threading.Lock()
        self._train_thread: Optional[threading.Thread] = None
        self._training_active = threading.Event()  # set while train_step is running
        self._train_batch_size = CONFIG.train.rollout_length  # collect this many before training

        # ── Batched inference ────────────────────────────────────────
        # Fire each batch as soon as every connected client has submitted
        # rather than waiting out the straggler window for an unreachable
        # max_batch (each client blocks on its result, so in-flight requests
        # are bounded by the connected-client count).
        self.batcher = InferenceBatcher(
            agent=agent,
            max_batch=max(128, self.max_clients + 8),
            max_wait_ms=1.5,
            client_count_fn=lambda: len(self.client_states),
        )

    def start(self):
        """Start the server (blocking)."""
        self.running = True
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.settimeout(1.0)

        server_sock.bind((self.host, self.port))
        server_sock.listen(self.max_clients)
        print(f"v3 Socket server listening on {self.host}:{self.port}")

        try:
            while self.running and not self.shutdown_event.is_set():
                try:
                    sock, addr = server_sock.accept()
                except socket.timeout:
                    continue

                with self.client_lock:
                    cid = self._next_cid
                    self._next_cid += 1
                    self.client_states[cid] = self._new_client_state()

                thread = threading.Thread(
                    target=self._handle_client,
                    args=(sock, cid),
                    daemon=True,
                )
                thread.start()
                self.metrics.update_client_count(len(self.client_states))
        finally:
            self.running = False
            server_sock.close()

    def stop(self):
        """Signal shutdown."""
        self.running = False
        self.shutdown_event.set()
        self.batcher.stop()

    # ── Training coordinator ────────────────────────────────────────────

    def _push_transition(
        self,
        client_id: int,
        entity_features: torch.Tensor,
        entity_mask: torch.Tensor,
        global_context: torch.Tensor,
        move_action_features: torch.Tensor,
        fire_action_features: torch.Tensor,
        move_action: int,
        fire_action: int,
        log_prob: float,
        value: float,
        has_value: bool,
        reward: float,
        done: bool,
        next_value: float,
        frame_seq: int = 0,
        expert_move: int = 8,
        expert_fire: int = 8,
        is_expert: bool = False,
        policy_sampled: bool = False,
        fire_locked: bool = False,
    ):
        """Thread-safe push of one transition. Triggers training when batch is full."""
        txn = (
            int(client_id),
            int(frame_seq),
            entity_features, entity_mask, global_context, move_action_features, fire_action_features,
            move_action, fire_action, log_prob, value, has_value, reward, done, next_value,
            expert_move, expert_fire, is_expert, policy_sampled, fire_locked,
        )
        with self._transition_lock:
            self._transition_queue.append(txn)
            queue_len = len(self._transition_queue)

        if queue_len >= self._train_batch_size and self.agent.training_enabled:
            self._start_training()

    def _start_training(self):
        """Launch training on a background thread if not already running."""
        thread = None
        with self._train_start_lock:
            if self._training_active.is_set():
                return
            if self._train_thread is not None and self._train_thread.is_alive():
                return
            # Mark the slot active before publishing the thread object so
            # concurrent client threads cannot race a second start() call.
            self._training_active.set()
            thread = threading.Thread(target=self._train_worker, daemon=True, name="v3-train")
            self._train_thread = thread
        try:
            thread.start()
        except Exception:
            with self._train_start_lock:
                if self._train_thread is thread:
                    self._train_thread = None
                self._training_active.clear()
            raise

    def _train_worker(self):
        """Drain transition queue into a RolloutBuffer and run PPO update."""
        try:
            with self._transition_lock:
                max_drain = max(
                    self._train_batch_size,
                    int(getattr(CONFIG.train, "max_rollout_drain", self._train_batch_size) or self._train_batch_size),
                )
                batch_size = min(len(self._transition_queue), max_drain)
                if batch_size < 64:
                    return  # not enough data
                batch = [self._transition_queue.popleft() for _ in range(batch_size)]

            # Build a single-actor rollout buffer
            rollout = RolloutBuffer(
                rollout_length=batch_size,
                num_actors=1,
                device=torch.device("cpu"),
            )

            client_ids: list[int] = []
            frame_seqs: list[int] = []
            next_values: list[float] = []
            for t, txn in enumerate(batch):
                (client_id, frame_seq, ef, em, gc, maf, faf, ma, fa, lp, val, has_val, rew, done, next_val,
                 ex_m, ex_f, is_exp, policy_sampled, fire_locked) = txn
                client_ids.append(int(client_id))
                frame_seqs.append(int(frame_seq))
                next_values.append(float(next_val))
                rollout.entity_features[t, 0] = ef
                rollout.entity_masks[t, 0] = em
                rollout.global_contexts[t, 0] = gc
                rollout.move_action_features[t, 0] = maf
                rollout.fire_action_features[t, 0] = faf
                rollout.move_actions[t, 0] = ma
                rollout.fire_actions[t, 0] = fa
                rollout.log_probs[t, 0] = lp
                rollout.values[t, 0] = val
                rollout.has_value[t, 0] = has_val
                rollout.rewards[t, 0] = rew
                rollout.dones[t, 0] = done
                rollout.expert_move[t, 0] = ex_m
                rollout.expert_fire[t, 0] = ex_f
                rollout.is_expert[t, 0] = is_exp
                rollout.policy_sampled[t, 0] = policy_sampled
                rollout.fire_locked[t, 0] = fire_locked

            rollout.step = batch_size
            rollout.ready = True
            self._compute_grouped_advantages(rollout, client_ids, next_values, frame_seqs)

            # Run training on the appropriate device/stream
            if self.batcher._use_gpu_lock:
                with self.batcher.gpu_lock:
                    if self.agent.train_stream is not None:
                        with torch.cuda.stream(self.agent.train_stream):
                            self.agent.train_step(rollout)
                        self.agent.train_stream.synchronize()
                    else:
                        self.agent.train_step(rollout)
            elif self.agent.train_stream is not None:
                with torch.cuda.stream(self.agent.train_stream):
                    self.agent.train_step(rollout)
                self.agent.train_stream.synchronize()
            else:
                self.agent.train_step(rollout)

            # Sync weights to inference network after training update
            self.agent.sync_inference_weights()
            self.agent._weights_updated.clear()

        except Exception as e:
            print(f"[v3] Training error: {e}")
            traceback.print_exc()
        finally:
            with self._train_start_lock:
                self._training_active.clear()
                self._train_thread = None

    @staticmethod
    def _compute_grouped_advantages(
        rollout: RolloutBuffer,
        client_ids: list[int],
        next_values: list[float],
        frame_seqs: Optional[list[int]] = None,
    ) -> None:
        """Compute GAE independently for each client timeline in a drained batch."""
        gamma = float(CONFIG.train.gamma)
        lam = float(CONFIG.train.gae_lambda)
        by_client: dict[int, list[int]] = {}
        for idx, client_id in enumerate(client_ids):
            by_client.setdefault(int(client_id), []).append(idx)

        rollout.advantages.zero_()
        rollout.returns.zero_()
        for indices in by_client.values():
            if frame_seqs is not None:
                indices.sort(key=lambda i: int(frame_seqs[i]))
            last_gae = 0.0
            for idx in reversed(indices):
                has_value = bool(rollout.has_value[idx, 0].item())
                if not has_value:
                    last_gae = 0.0
                    continue
                done = bool(rollout.dones[idx, 0].item())
                non_terminal = 0.0 if done else 1.0
                reward = float(rollout.rewards[idx, 0].item())
                value = float(rollout.values[idx, 0].item())
                bootstrap = 0.0 if done else float(next_values[idx])
                delta = reward + gamma * bootstrap * non_terminal - value
                last_gae = delta + gamma * lam * non_terminal * last_gae
                rollout.advantages[idx, 0] = last_gae
                rollout.returns[idx, 0] = last_gae + value


    def _new_client_state(self) -> dict:
        return {
            "frames": 0,
            "connected_frames": 0,
            "game_frames": 0,
            "player_alive": False,
            "alive_streak": 0,
            "dead_streak": 0,
            "gameplay_seen": False,
            "start_pulse_window": 0,
            "plausible_start_streak": 0,
            "level_number": 0,
            "start_wave": 1,
            "reward_prev_wave": 0,
            "game_score": 0,
            "raw_game_score": 0,
            "num_lasers": 0,
            "raw_num_lasers": 0,
            "raw_level_number": 0,
            "status": "waiting",
            "last_time": time.time(),
            "fps": 0.0,
            "was_done": False,
            "total_reward": 0.0,
            "ep_frames": 0,
            "episode_id": 1,
            "fire_hold_dir": -1,
            "fire_hold_count": 0,
            "fire_pending_dir": -1,
            "last_state": None,
            "last_action": None,
            "last_player_alive": False,
            "prev_action_source": None,
            "last_alive_game_score": 0,
            "preview_capable": False,
            "client_slot": 0,
            # Training state (tensors from act_with_value)
            "last_tensors": None,
            "last_log_prob": 0.0,
            "last_value": 0.0,
            "last_has_value": False,
            "frame_seq": 0,
            "last_frame_seq": 0,
            "last_is_expert": False,
            "last_expert_move": 8,
            "last_expert_fire": 8,
            "last_policy_sampled": False,
            "last_fire_locked": False,
        }

    # ── Preview client selection ────────────────────────────────────────

    @staticmethod
    def _parse_client_handshake(handshake_value: int) -> tuple[bool, int]:
        raw = max(0, int(handshake_value or 0))
        preview_capable = (raw & 0x01) != 0
        client_slot = max(0, raw >> 1)
        return preview_capable, client_slot

    def _pick_default_preview_client_locked(self) -> Optional[int]:
        candidates = []
        for cid, cs in self.client_states.items():
            if not bool(cs.get("preview_capable", False)):
                continue
            slot = int(cs.get("client_slot", cid))
            candidates.append((slot, int(cid)))
        if not candidates:
            return None
        candidates.sort()
        return int(candidates[0][1])

    def _ensure_preview_client_selected_locked(self) -> tuple[Optional[int], bool]:
        selected = self.preview_cid
        if selected is not None:
            cs = self.client_states.get(int(selected))
            if isinstance(cs, dict) and bool(cs.get("preview_capable", False)):
                return int(selected), False
        fallback = self._pick_default_preview_client_locked()
        changed = self.preview_cid != fallback
        self.preview_cid = fallback
        return fallback, changed

    def _is_preview_client(self, cid: int) -> bool:
        changed = False
        with self.client_lock:
            preview_cid, changed = self._ensure_preview_client_selected_locked()
        if changed:
            self._clear_preview_cache()
        return preview_cid is not None and int(cid) == int(preview_cid)

    def _preview_enabled_for_client(self, cid: int) -> bool:
        if not self._is_preview_client(cid):
            return False
        with self.client_lock:
            cs = self.client_states.get(int(cid))
            if not isinstance(cs, dict) or not bool(cs.get("preview_capable", False)):
                return False
        with self.metrics.lock:
            if not self.metrics.preview_capture_enabled:
                return False
            return int(self.metrics.web_client_count or 0) > 0

    def _hud_enabled_for_client(self, cid: int) -> bool:
        if not self._is_preview_client(cid):
            return False
        with self.metrics.lock:
            return bool(self.metrics.hud_enabled)

    def _clear_preview_cache(self):
        with self.metrics.lock:
            self.metrics.game_preview_client_id = -1
            self.metrics.game_preview_seq = 0
            self.metrics.game_preview_width = 0
            self.metrics.game_preview_height = 0
            self.metrics.game_preview_format = ""
            self.metrics.game_preview_data = b""
            self.metrics.game_preview_updated_ts = 0.0
            self.metrics.game_preview_source_format = ""
            self.metrics.game_preview_encoded_bytes = 0
            self.metrics.game_preview_raw_bytes = 0
            self.metrics.game_preview_compression_ratio = 1.0
            self.metrics.game_preview_fps = 0.0

    def _cache_client_preview(self, cid: int, frame: FrameData):
        if not self._is_preview_client(cid):
            return
        pixels = frame.preview_pixels
        width = frame.preview_width
        height = frame.preview_height
        if not pixels or width <= 0 or height <= 0:
            return
        if frame.preview_format != 1:
            return
        expected_len = width * height * 2
        if len(pixels) != expected_len:
            return
        enc_fmt = frame.preview_encoded_format
        enc_bytes = frame.preview_encoded_bytes
        raw_bytes = frame.preview_raw_bytes
        with self.metrics.lock:
            prev_seq = self.metrics.game_preview_seq
            prev_ts = self.metrics.game_preview_updated_ts
            now_ts = time.time()
            next_seq = prev_seq + 1
            if prev_ts > 0.0:
                dt = max(1e-6, now_ts - prev_ts)
                self.metrics.game_preview_fps = 1.0 / dt
            self.metrics.game_preview_client_id = int(cid)
            self.metrics.game_preview_seq = next_seq
            self.metrics.game_preview_width = width
            self.metrics.game_preview_height = height
            self.metrics.game_preview_format = "rgb565be"
            self.metrics.game_preview_data = bytes(pixels)
            self.metrics.game_preview_updated_ts = now_ts
            self.metrics.game_preview_source_format = {1: "raw", 2: "lzss", 3: "rle"}.get(enc_fmt, "unknown")
            self.metrics.game_preview_encoded_bytes = enc_bytes
            self.metrics.game_preview_raw_bytes = raw_bytes if raw_bytes > 0 else expected_len
            if enc_bytes > 0 and raw_bytes > 0:
                self.metrics.game_preview_compression_ratio = float(raw_bytes) / float(enc_bytes)
            else:
                self.metrics.game_preview_compression_ratio = 1.0

    def get_client_rows(self) -> list[dict]:
        changed = False
        with self.client_lock:
            selected, changed = self._ensure_preview_client_selected_locked()
            rows = []
            for cid, cs in self.client_states.items():
                # ZP1LAS is the remaining ship counter after the current ship,
                # so zero is a valid "last life" value, not necessarily idle.
                lives = max(0, int(cs.get("num_lasers", 0) or 0))
                level = max(0, int(cs.get("level_number", 0) or 0))
                score = max(0, int(cs.get("game_score", 0) or 0))
                rows.append({
                    "client_id": int(cid),
                    "client_slot": int(cs.get("client_slot", cid)),
                    "duration_seconds": float(max(0, int(cs.get("game_frames", 0) or 0))) / 60.0,
                    "connected_duration_seconds": float(max(0, int(cs.get("connected_frames", cs.get("frames", 0)) or 0))) / 60.0,
                    "lives": lives,
                    "level": level,
                    "score": score,
                    "status": str(cs.get("status", "unknown")),
                    "player_alive": bool(cs.get("player_alive", False)),
                    "gameplay_seen": bool(cs.get("gameplay_seen", False)),
                    "dead_streak": max(0, int(cs.get("dead_streak", 0) or 0)),
                    "selected_preview": (selected is not None and int(selected) == int(cid)),
                    "preview_capable": bool(cs.get("preview_capable", False)),
                })
        if changed:
            self._clear_preview_cache()
        rows.sort(key=lambda r: (int(r.get("client_slot", r.get("client_id", 0))), int(r.get("client_id", 0))))
        return rows

    def get_selected_preview_client_id(self) -> Optional[int]:
        changed = False
        with self.client_lock:
            selected, changed = self._ensure_preview_client_selected_locked()
        if changed:
            self._clear_preview_cache()
        return None if selected is None else int(selected)

    def get_selected_preview_client_slot(self) -> Optional[int]:
        selected = self.get_selected_preview_client_id()
        if selected is None:
            return None
        with self.client_lock:
            cs = self.client_states.get(int(selected))
            if not isinstance(cs, dict):
                return None
            try:
                return max(0, int(cs.get("client_slot", selected)))
            except Exception:
                return int(selected)

    def set_preview_client(self, cid: Optional[int]) -> tuple[bool, Optional[int]]:
        with self.client_lock:
            if cid is None:
                selected = self._pick_default_preview_client_locked()
            else:
                cs = self.client_states.get(int(cid))
                if not isinstance(cs, dict) or not bool(cs.get("preview_capable", False)):
                    return False, self.preview_cid
                selected = int(cid)
            changed = self.preview_cid != selected
            self.preview_cid = selected
        if changed:
            self._clear_preview_cache()
        return True, selected

    def _recv_exact(self, sock, n: int, timeout_s: float = 0.5) -> Optional[bytes]:
        """Read exactly n bytes from socket."""
        chunks = []
        remaining = n
        deadline = time.time() + timeout_s
        while remaining > 0:
            if time.time() > deadline:
                return None
            ready = select.select([sock], [], [], max(0.001, deadline - time.time()))
            if not ready[0]:
                continue
            chunk = sock.recv(min(remaining, 65536))
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _pack_action(
        self,
        move_cmd: int,
        fire_cmd: int,
        source_code: int,
        preview_enabled: bool = False,
        hud_enabled: bool = False,
        client_slot: int = 0,
    ) -> bytes:
        """Pack 5-byte action response for Lua.

        source byte layout:
          bits 0-3: action source (0=none, 1=policy, 2=epsilon, 3=expert)
          bit 6:    preview enable flag (tells Lua to send preview frame)
          bit 7:    HUD enable flag
        """
        start_adv = 1 if GAME_SETTINGS.start_advanced else 0
        start_level = 1
        if start_adv:
            # Curriculum: spread per-client start waves so some actors train on
            # dense late-game object fields. Lua latches START_LEVEL_MIN per
            # packet, so per-client values take effect without a Lua change.
            spread = max(1, int(CONFIG.train.curriculum_wave_spread))
            if self.agent.is_guidance_rescue_active():
                spread = max(1, min(spread, int(getattr(CONFIG.train, "guidance_rescue_curriculum_wave_spread", spread))))
            start_level = max(1, min(81, int(GAME_SETTINGS.start_level_min) + (int(client_slot) % spread)))
        source_u8 = (int(source_code) & 0x0F)
        if preview_enabled:
            source_u8 |= 0x40
        if hud_enabled:
            source_u8 |= 0x80
        return struct.pack(
            ">bbBBB",
            int(move_cmd),
            int(fire_cmd),
            int(source_u8),
            int(start_adv),
            int(start_level),
        )

    def _handle_client(self, sock: socket.socket, cid: int):
        """Per-client frame loop."""
        try:
            sock.setblocking(False)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            # Handshake — parse preview capability from the 2-byte value
            sock.setblocking(True)
            sock.settimeout(5.0)
            ping = self._recv_exact(sock, 2, timeout_s=5.0)
            if not ping or len(ping) < 2:
                raise ConnectionError("No handshake")
            handshake_val = struct.unpack(">H", ping)[0]
            preview_capable, client_slot = self._parse_client_handshake(handshake_val)
            is_preview_client = False
            with self.client_lock:
                cs = self.client_states.get(cid)
                if isinstance(cs, dict):
                    cs["preview_capable"] = bool(preview_capable)
                    cs["client_slot"] = int(client_slot)
                selected, changed = self._ensure_preview_client_selected_locked()
            if changed:
                self._clear_preview_cache()
            is_preview_client = bool(preview_capable) and selected is not None and int(selected) == int(cid)
            sock.setblocking(False)
            sock.settimeout(None)

            while self.running and not self.shutdown_event.is_set():
                ready = select.select([sock], [], [], 0.002)
                if not ready[0]:
                    continue

                # Read length header
                hdr = self._recv_exact(sock, 4, timeout_s=0.25)
                if hdr is None or len(hdr) < 4:
                    raise ConnectionError("EOF")
                dlen = struct.unpack(">I", hdr)[0]
                if dlen <= 0 or dlen > _MAX_FRAME_PAYLOAD_BYTES:
                    raise ConnectionError(f"Invalid payload: {dlen}")

                data = self._recv_exact(sock, dlen, timeout_s=0.5)
                if data is None:
                    raise ConnectionError("Broken")

                # Validate param count
                if len(data) >= 2:
                    n = struct.unpack(">H", data[:2])[0]
                    if n != WIRE_PARAMS_COUNT:
                        print(f"Client {cid}: param mismatch {n} != {WIRE_PARAMS_COUNT}")
                        break

                preview_enabled = self._preview_enabled_for_client(cid)
                hud_enabled = self._hud_enabled_for_client(cid)
                should_parse_preview = bool(self._is_preview_client(cid) and preview_enabled)
                frame = parse_frame_data(data, parse_preview=should_parse_preview)
                if not frame:
                    sock.sendall(self._pack_action(-1, -1, 0, preview_enabled=preview_enabled, hud_enabled=hud_enabled, client_slot=client_slot))
                    continue

                with self.client_lock:
                    if cid not in self.client_states:
                        break
                    cs = self.client_states[cid]
                    cs["frames"] += 1
                    cs["connected_frames"] = cs.get("connected_frames", 0) + 1
                    cs["last_time"] = time.time()
                    cs["player_alive"] = frame.player_alive
                    cs["num_lasers"] = frame.num_lasers
                    cs["raw_num_lasers"] = frame.num_lasers
                    cs["raw_level_number"] = frame.level_number
                    cs["raw_game_score"] = max(0, frame.game_score)

                    # Track alive/dead streaks
                    if frame.player_alive:
                        cs["alive_streak"] = cs.get("alive_streak", 0) + 1
                        cs["dead_streak"] = 0
                    else:
                        cs["alive_streak"] = 0
                        cs["dead_streak"] = cs.get("dead_streak", 0) + 1

                    if cs["dead_streak"] >= _GAMEPLAY_RESET_DEAD_FRAMES:
                        cs["gameplay_seen"] = False
                        cs["start_pulse_window"] = 0
                        cs["start_wave"] = 1

                    # Detect game start
                    if frame.start_pressed:
                        cs["start_pulse_window"] = _START_PULSE_VALID_FRAMES
                    elif cs.get("start_pulse_window", 0) > 0:
                        cs["start_pulse_window"] -= 1

                    plausible = frame.player_alive and frame.game_score >= 0
                    if cs.get("start_pulse_window", 0) > 0 and plausible:
                        cs["plausible_start_streak"] = cs.get("plausible_start_streak", 0) + 1
                    else:
                        cs["plausible_start_streak"] = 0

                    if _frame_confirms_gameplay(cs, frame):
                        if not cs.get("gameplay_seen"):
                            cs["gameplay_seen"] = True
                            cs["ep_frames"] = 0
                            cs["game_frames"] = 0
                            cs["start_wave"] = max(1, frame.level_number)
                        cs["start_pulse_window"] = 0

                    if frame.player_alive:
                        cs["level_number"] = frame.level_number
                        cs["game_score"] = max(0, frame.game_score)
                        if cs.get("gameplay_seen"):
                            cs["game_frames"] = cs.get("game_frames", 0) + 1
                            cs["status"] = "playing"
                        else:
                            cs["game_frames"] = 0
                            cs["status"] = "starting"
                    else:
                        cs["status"] = "waiting" if cs.get("dead_streak", 0) >= _GAMEPLAY_RESET_DEAD_FRAMES else "dead"

                    if frame.player_alive and cs.get("gameplay_seen") and frame.num_lasers == 0:
                        with self.metrics.lock:
                            if frame.game_score > self.metrics.peak_game_score:
                                self.metrics.peak_game_score = frame.game_score

                    # Track per-game score
                    if frame.player_alive:
                        if frame.game_score < cs.get("last_alive_game_score", 0):
                            cs["ep_frames"] = 0
                            cs["game_frames"] = 0
                            cs["start_wave"] = max(1, frame.level_number)
                        cs["last_alive_game_score"] = frame.game_score

                # Cache preview frame if this is the selected preview client
                if should_parse_preview and frame.preview_pixels:
                    self._cache_client_preview(cid, frame)

                self.metrics.update_frame()
                self.agent.total_frames = self.metrics.total_frames
                self.agent.policy_frames = self.metrics.policy_frames

                pending_reward = None
                pending_reward_components = None
                pending_prev_tensors = None
                pending_prev_action = None
                pending_prev_log_prob = 0.0
                pending_prev_value = 0.0
                pending_prev_has_value = False
                pending_prev_frame_seq = 0
                pending_prev_expert_move = 8
                pending_prev_expert_fire = 8
                pending_prev_is_expert = False
                pending_prev_policy_sampled = False
                pending_prev_fire_locked = False

                # Current-frame movement potential Φ(s) for PBRS. Wire fields:
                # nearest-human distance = state[10], humans-present proxy =
                # state[13] (count/255, so any human -> >0). Computed every frame
                # (even the first, where the reward block below is skipped) so it
                # can be cached as the "prev" potential for the next transition.
                # Forced to 0 on a terminal frame to guarantee Φ(terminal)=0,
                # which keeps the shaping policy-invariant.
                try:
                    cur_nearest_human = float(frame.state[10])
                    cur_num_humans = float(frame.state[13])
                except (IndexError, TypeError, ValueError):
                    cur_nearest_human, cur_num_humans = 1.0, 0.0
                # Nearest-enemy distance is core wire field index 9 (0-1); feeds
                # both the danger-flee term of the movement potential and the
                # proximity penalty below.
                try:
                    cur_nearest_enemy = float(frame.state[9])
                except (IndexError, TypeError, ValueError):
                    cur_nearest_enemy = 1.0
                cur_move_potential = 0.0 if frame.done else move_potential(
                    cur_nearest_human, cur_num_humans, frame.player_alive,
                    cur_nearest_enemy,
                )

                # ── Process previous step reward → prepare transition ──
                if cs.get("last_state") is not None and cs.get("last_action") is not None:
                    # Wave-clear detection: a wave increment while alive means the
                    # previous action finished clearing a wave. Guard against the
                    # initial 0→start_wave jump at episode start.
                    wave_completed = False
                    cur_wave = int(frame.level_number)
                    if frame.player_alive and not frame.done:
                        prev_wave = int(cs.get("reward_prev_wave", 0))
                        if prev_wave > 0 and cur_wave > prev_wave:
                            wave_completed = True
                        cs["reward_prev_wave"] = cur_wave

                    # Score delta (objreward carries the per-frame score change;
                    # ignore it on the terminal frame, where death dominates).
                    score_delta = max(0.0, float(frame.objreward)) if not frame.done else 0.0
                    # Nearest-enemy distance (core wire field index 9) was read
                    # above for the movement potential; reuse it here.
                    nearest_enemy_dist = cur_nearest_enemy

                    pending_reward, pending_reward_components = shape_reward_with_components(
                        frame.objreward,
                        frame.subjreward,
                        frame.done,
                        player_alive=frame.player_alive,
                        score_delta=score_delta,
                        nearest_enemy_dist=nearest_enemy_dist,
                        wave_completed=wave_completed,
                        wave_number=cur_wave,
                        move_potential_prev=float(cs.get("move_potential", 0.0)),
                        move_potential_cur=cur_move_potential,
                    )
                    cs["total_reward"] += pending_reward
                    totals = cs.setdefault("reward_components", {})
                    for key, val in (pending_reward_components or {}).items():
                        totals[key] = float(totals.get(key, 0.0)) + float(val)
                    cs["ep_frames"] = cs.get("ep_frames", 0) + 1

                    pending_prev_tensors = cs.get("last_tensors")
                    pending_prev_action = cs.get("last_action")
                    pending_prev_log_prob = float(cs.get("last_log_prob", 0.0) or 0.0)
                    pending_prev_value = float(cs.get("last_value", 0.0) or 0.0)
                    pending_prev_has_value = bool(cs.get("last_has_value", False))
                    pending_prev_frame_seq = int(cs.get("last_frame_seq", 0) or 0)
                    pending_prev_expert_move = _stored_action_label(cs, "last_expert_move")
                    pending_prev_expert_fire = _stored_action_label(cs, "last_expert_fire")
                    pending_prev_is_expert = bool(cs.get("last_is_expert", False))
                    pending_prev_policy_sampled = bool(cs.get("last_policy_sampled", False))
                    pending_prev_fire_locked = bool(cs.get("last_fire_locked", False))

                # ── Terminal ────────────────────────────────────────────
                if frame.done:
                    if pending_prev_tensors is not None and pending_prev_action is not None and pending_reward is not None:
                        self._push_transition(
                            client_id=cid,
                            entity_features=pending_prev_tensors["entity_features"],
                            entity_mask=pending_prev_tensors["entity_mask"],
                            global_context=pending_prev_tensors["global_context"],
                            move_action_features=pending_prev_tensors["move_action_features"],
                            fire_action_features=pending_prev_tensors["fire_action_features"],
                            move_action=pending_prev_action[0],
                            fire_action=pending_prev_action[1],
                            log_prob=pending_prev_log_prob,
                            value=pending_prev_value,
                            has_value=pending_prev_has_value,
                            reward=pending_reward,
                            done=True,
                            next_value=0.0,
                            frame_seq=pending_prev_frame_seq,
                            expert_move=pending_prev_expert_move,
                            expert_fire=pending_prev_expert_fire,
                            is_expert=pending_prev_is_expert,
                            policy_sampled=pending_prev_policy_sampled,
                            fire_locked=pending_prev_fire_locked,
                        )
                    self.agent._reset_frame_buffer(cid)
                    cs["fire_hold_dir"] = -1
                    cs["fire_hold_count"] = 0
                    cs["fire_pending_dir"] = -1

                    if not cs.get("was_done"):
                        ep_reward = cs["total_reward"]
                        ep_len = cs.get("ep_frames", 0)
                        ep_level = float(cs.get("level_number", 0))
                        ep_score = int(cs.get("game_score", 0))
                        self.metrics.add_episode(
                            ep_reward, ep_len,
                            level=ep_level, game_score=ep_score,
                            reward_components=cs.get("reward_components", {}),
                        )
                        add_episode_to_reward_windows(ep_reward, ep_len)
                        add_episode_to_eplen_windows(ep_len)
                        self.agent.update_guidance_rescue(
                            self.metrics.avg_reward,
                            avg_score=self.metrics.avg_game_score,
                            avg_ep_len=self.metrics.avg_ep_len,
                            bc_fire_loss=self.agent.last_bc_fire_loss,
                            bc_move_loss=self.agent.last_bc_move_loss,
                        )
                    cs["was_done"] = True
                    _pv = self._preview_enabled_for_client(cid)
                    _hd = self._hud_enabled_for_client(cid)
                    sock.sendall(self._pack_action(-1, -1, 0, preview_enabled=_pv, hud_enabled=_hd, client_slot=client_slot))
                    cs["last_state"] = cs["last_action"] = None
                    cs["last_tensors"] = None
                    cs["last_log_prob"] = 0.0
                    cs["last_value"] = 0.0
                    cs["last_has_value"] = False
                    cs["last_is_expert"] = False
                    cs["last_expert_move"] = 8
                    cs["last_expert_fire"] = 8
                    cs["last_policy_sampled"] = False
                    cs["last_fire_locked"] = False
                    cs["last_player_alive"] = False
                    cs["prev_action_source"] = None
                    cs["episode_id"] = cs.get("episode_id", 1) + 1
                    cs["total_reward"] = 0.0
                    cs["reward_components"] = {}
                    cs["ep_frames"] = 0
                    cs["reward_prev_wave"] = 0
                    cs["move_potential"] = 0.0
                    continue

                if cs.get("was_done"):
                    cs["was_done"] = False
                    cs["total_reward"] = 0.0
                    cs["reward_components"] = {}
                    cs["ep_frames"] = 0

                # Skip dead/attract frames
                if not frame.player_alive:
                    if pending_prev_tensors is not None and pending_prev_action is not None and pending_reward is not None:
                        self._push_transition(
                            client_id=cid,
                            entity_features=pending_prev_tensors["entity_features"],
                            entity_mask=pending_prev_tensors["entity_mask"],
                            global_context=pending_prev_tensors["global_context"],
                            move_action_features=pending_prev_tensors["move_action_features"],
                            fire_action_features=pending_prev_tensors["fire_action_features"],
                            move_action=pending_prev_action[0],
                            fire_action=pending_prev_action[1],
                            log_prob=pending_prev_log_prob,
                            value=pending_prev_value,
                            has_value=pending_prev_has_value,
                            reward=pending_reward,
                            done=True,
                            next_value=0.0,
                            frame_seq=pending_prev_frame_seq,
                            expert_move=pending_prev_expert_move,
                            expert_fire=pending_prev_expert_fire,
                            is_expert=pending_prev_is_expert,
                            policy_sampled=pending_prev_policy_sampled,
                            fire_locked=pending_prev_fire_locked,
                        )
                    self.agent._reset_frame_buffer(cid)
                    cs["last_state"] = cs["last_action"] = None
                    cs["last_tensors"] = None
                    cs["last_log_prob"] = 0.0
                    cs["last_value"] = 0.0
                    cs["last_has_value"] = False
                    cs["last_is_expert"] = False
                    cs["last_expert_move"] = 8
                    cs["last_expert_fire"] = 8
                    cs["last_policy_sampled"] = False
                    cs["last_fire_locked"] = False
                    cs["last_player_alive"] = False
                    cs["prev_action_source"] = None
                    cs["fire_hold_dir"] = -1
                    cs["fire_hold_count"] = 0
                    cs["fire_pending_dir"] = -1
                    cs["reward_prev_wave"] = 0
                    cs["move_potential"] = 0.0
                    _pv = self._preview_enabled_for_client(cid)
                    _hd = self._hud_enabled_for_client(cid)
                    sock.sendall(self._pack_action(-1, -1, 0, preview_enabled=_pv, hud_enabled=_hd, client_slot=client_slot))
                    continue

                # ── Choose action ───────────────────────────────────────
                wire_state = frame.state
                epsilon = self.agent.get_epsilon()
                expert_ratio = self.agent.get_expert_ratio()

                fire_update_open = cs.get("fire_hold_count", 0) <= 0
                locked_fire = None
                if not fire_update_open:
                    held = cs.get("fire_hold_dir", -1)
                    locked_fire = max(0, min(8, held)) if held >= 0 else 8

                # Decide: expert vs policy
                use_expert = random.random() < expert_ratio
                action_source = "none"
                is_epsilon = False
                log_prob = 0.0
                value = 0.0
                has_value = False
                tensors_dict = None
                expert_move_out = 8
                expert_fire_out = 8
                policy_sampled = False
                fire_locked_now = locked_fire is not None

                # Process state once — shared by expert + model (eliminates
                # double entity extraction that was the #1 bottleneck).
                tensors = self.agent._process_and_stack(wire_state, cid)

                if use_expert:
                    wave = max(1, cs.get("level_number", 1))
                    t0 = time.perf_counter()
                    # Use pre-extracted entities from the already-processed
                    # frame inside the agent's frame buffer — avoids the old
                    # double-extraction path.
                    buf = self.agent._get_frame_buffer(cid)
                    latest = buf[-1] if buf else None
                    if latest is not None:
                        _px = float(wire_state[5]) if wire_state.size > 6 else 0.5
                        _py = float(wire_state[6]) if wire_state.size > 6 else 0.5
                        move_idx, fire_idx = get_expert_action_from_entities(
                            latest["entity_features"],
                            latest["entity_mask"],
                            latest["num_entities"],
                            wave_number=wave,
                            px=_px,
                            py=_py,
                            locked_fire=locked_fire,
                        )
                    else:
                        move_idx, fire_idx = get_expert_action(wire_state, wave_number=wave, locked_fire=locked_fire)
                    self.metrics.add_expert_time(time.perf_counter() - t0)
                    expert_move_out = move_idx
                    if locked_fire is not None:
                        fire_idx = locked_fire
                    expert_fire_out = fire_idx
                    action_source = "expert"
                    # Always compute the value head for expert frames so they
                    # carry a real critic estimate and keep each client's GAE
                    # timeline continuous (no broken chains during the guided
                    # phase where most frames are expert-driven).
                    t0 = time.perf_counter()
                    value = self.batcher.submit_value(tensors)
                    self.metrics.add_inference_time(time.perf_counter() - t0)
                    has_value = True
                    tensors_dict = self.agent._detach_tensors(tensors)
                else:
                    is_epsilon = random.random() < epsilon
                    if is_epsilon:
                        move_idx = random.randrange(CONFIG.model.num_move_actions)
                        fire_idx = random.randrange(CONFIG.model.num_fire_actions)
                        if locked_fire is not None:
                            fire_idx = locked_fire
                        t0 = time.perf_counter()
                        value = self.batcher.submit_value(tensors)
                        self.metrics.add_inference_time(time.perf_counter() - t0)
                        has_value = True
                        log_prob = 0.0
                    else:
                        t0 = time.perf_counter()
                        res = self.batcher.submit_action(tensors)
                        self.metrics.add_inference_time(time.perf_counter() - t0)
                        move_idx = res["move_action"]
                        fire_idx = res["fire_action"]
                        log_prob = res["move_log_prob"] if locked_fire is not None else res["log_prob"]
                        value = res["value"]
                        has_value = True
                        if locked_fire is not None:
                            fire_idx = locked_fire
                        policy_sampled = True
                    tensors_dict = self.agent._detach_tensors(tensors)
                    action_source = "policy"

                if pending_prev_tensors is not None and pending_prev_action is not None and pending_reward is not None:
                    self._push_transition(
                        client_id=cid,
                        entity_features=pending_prev_tensors["entity_features"],
                        entity_mask=pending_prev_tensors["entity_mask"],
                        global_context=pending_prev_tensors["global_context"],
                        move_action_features=pending_prev_tensors["move_action_features"],
                        fire_action_features=pending_prev_tensors["fire_action_features"],
                        move_action=pending_prev_action[0],
                        fire_action=pending_prev_action[1],
                        log_prob=pending_prev_log_prob,
                        value=pending_prev_value,
                        has_value=pending_prev_has_value,
                        reward=pending_reward,
                        done=False,
                        next_value=value,
                        frame_seq=pending_prev_frame_seq,
                        expert_move=pending_prev_expert_move,
                        expert_fire=pending_prev_expert_fire,
                        is_expert=pending_prev_is_expert,
                        policy_sampled=pending_prev_policy_sampled,
                        fire_locked=pending_prev_fire_locked,
                    )

                # Apply fire hold
                effective_fire = _apply_fire_hold(cs, fire_idx)

                cs["last_state"] = wire_state
                cs["last_action"] = (move_idx, effective_fire)
                cs["last_player_alive"] = frame.player_alive
                cs["prev_action_source"] = action_source
                cs["last_tensors"] = tensors_dict
                cs["last_log_prob"] = log_prob
                cs["last_value"] = value
                cs["last_has_value"] = has_value
                cs["last_frame_seq"] = int(cs.get("frame_seq", 0) or 0)
                cs["frame_seq"] = int(cs.get("last_frame_seq", 0) or 0) + 1
                cs["last_is_expert"] = use_expert
                cs["last_expert_move"] = expert_move_out
                cs["last_expert_fire"] = expert_fire_out
                cs["last_policy_sampled"] = policy_sampled
                cs["last_fire_locked"] = fire_locked_now
                cs["move_potential"] = cur_move_potential
                self.metrics.record_policy_sampled(policy_sampled)

                # Save signal
                if frame.save_signal:
                    self.agent.save()

                # Send action
                move_cmd, fire_cmd = encode_action_to_game(move_idx, effective_fire)
                if action_source == "expert":
                    source_byte = 3
                elif is_epsilon:
                    source_byte = 2
                elif action_source == "policy":
                    source_byte = 1
                else:
                    source_byte = 0

                _pv = self._preview_enabled_for_client(cid)
                _hd = self._hud_enabled_for_client(cid)
                sock.sendall(self._pack_action(move_cmd, fire_cmd, source_byte, preview_enabled=_pv, hud_enabled=_hd, client_slot=client_slot))

        except Exception as e:
            is_expected = isinstance(e, (ConnectionError, BrokenPipeError, ConnectionResetError, TimeoutError))
            if not is_expected:
                print(f"Client {cid} error: {e}")
                traceback.print_exc()
        finally:
            with self.client_lock:
                self.client_states.pop(cid, None)
                self.metrics.update_client_count(len(self.client_states))
            try:
                sock.close()
            except Exception:
                pass
