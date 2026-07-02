#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN METRICS DISPLAY                                                                          ||
# ||  Periodic header + row output for training telemetry (ported from Tempest).                                  ||
# ==================================================================================================================
"""Console metrics display and rolling reward/episode-length windows."""

if __name__ == "__main__":
    print("This is not the main application, run 'main.py' instead")
    exit(1)

import sys, time, math, threading
import numpy as np
from collections import deque

try:
    from .config import metrics, IS_INTERACTIVE, RL_CONFIG, game_settings
except ImportError:
    from config import metrics, IS_INTERACTIVE, RL_CONFIG, game_settings

row_counter = 0

# Rolling DQN reward-per-DQN-frame windows. Eviction is keyed by total episode
# frames so the windows advance at a stable wall-clock cadence even when the
# expert ratio changes, but the value is normalized by DQN-controlled frames so
# it does not rise just because episodes get longer or the policy gets more
# control time.
DQN100K_FRAMES = 100_000
_dqn100k = deque()
_dqn100k_dqn_frames = 0
_dqn100k_total_frames = 0

DQN1M_FRAMES = 1_000_000
_dqn1m = deque()
_dqn1m_dqn_frames = 0
_dqn1m_total_frames = 0

DQN5M_FRAMES = 5_000_000
_dqn5m = deque()
_dqn5m_dqn_frames = 0
_dqn5m_total_frames = 0

# Longer rolling DQN-reward-per-DQN-frame window. Like DQN100K/F, DQN1M/F, and
# DQN5M/F, this is frame-weighted: total DQN reward divided by total
# DQN-controlled frames. It isolates per-frame policy quality and is invariant
# to the expert ratio — the clean "is the DQN itself getting better?" signal.
#
# IMPORTANT: the window must evict on *total* frames (ep_len), NOT on DQN frames.
# DQN-controlled frames are only ~(1 - expert_ratio) of play (≈1% early on), so a
# window sized in DQN frames would take ~hours to fill and would behave as a
# cumulative lifetime average that decays as ~1/N regardless of actual learning.
# Keying eviction on total frames makes it a genuine rolling window (~3.8 min at
# 10M frames) that tracks recent per-frame quality, comparable to DQN5M's cadence.
DQN_PERFRAME_FRAMES = 10_000_000   # total-frame span of the rolling window
_dqn_pf = deque()            # (dqn_reward_sum, dqn_frames, ep_len) per episode
_dqn_pf_frames = 0           # accumulated DQN-controlled frames (denominator)
_dqn_pf_total_frames = 0     # accumulated total frames (eviction budget)

_dqn_windows_lock = threading.Lock()

# Rolling TOTAL reward windows (all episodes, not just DQN)
_total100k = deque()
_total100k_frames = 0
_total1m = deque()
_total1m_frames = 0
_total5m = deque()
_total5m_frames = 0

# Rolling episode-length windows
EPLEN100K_FRAMES = 100_000
_eplen100k = deque()
_eplen100k_frames = 0

_eplen1m = deque()
_eplen1m_frames = 0


def _add_episode_to_dqn_window(win, reward: float, dqn_frames: int, ep_len: int, limit: int, frame_refs: tuple[str, str]):
    dqn_frames = int(dqn_frames)
    ep_len = int(ep_len)
    if dqn_frames <= 0 or ep_len <= 0:
        return
    with _dqn_windows_lock:
        dqn_ref, total_ref = frame_refs
        win.append((float(reward), dqn_frames, ep_len))
        globals()[dqn_ref] += dqn_frames
        globals()[total_ref] += ep_len
        while win and globals()[total_ref] > limit:
            _, old_dqn_frames, old_ep_len = win.popleft()
            globals()[dqn_ref] -= old_dqn_frames
            globals()[total_ref] -= old_ep_len


def add_episode_to_dqn100k_window(dqn_reward: float, ep_len: int, dqn_frames: int | None = None):
    frames = ep_len if dqn_frames is None else dqn_frames
    _add_episode_to_dqn_window(
        _dqn100k, dqn_reward, frames, ep_len, DQN100K_FRAMES,
        ("_dqn100k_dqn_frames", "_dqn100k_total_frames"),
    )


def add_episode_to_dqn25k_window(dqn_reward: float, ep_len: int):
    # Backward-compat alias for older callers.
    add_episode_to_dqn100k_window(dqn_reward, ep_len)


def add_episode_to_dqn1k_window(dqn_reward: float, ep_len: int):
    # Backward-compat alias for very old callers.
    add_episode_to_dqn100k_window(dqn_reward, ep_len)


def add_episode_to_dqn1m_window(dqn_reward: float, ep_len: int, dqn_frames: int | None = None):
    frames = ep_len if dqn_frames is None else dqn_frames
    _add_episode_to_dqn_window(
        _dqn1m, dqn_reward, frames, ep_len, DQN1M_FRAMES,
        ("_dqn1m_dqn_frames", "_dqn1m_total_frames"),
    )


def add_episode_to_dqn5m_window(dqn_reward: float, ep_len: int, dqn_frames: int | None = None):
    frames = ep_len if dqn_frames is None else dqn_frames
    _add_episode_to_dqn_window(
        _dqn5m, dqn_reward, frames, ep_len, DQN5M_FRAMES,
        ("_dqn5m_dqn_frames", "_dqn5m_total_frames"),
    )


def _avg_window(win):
    if not win:
        return 0.0
    return sum(r for r, _ in win) / len(win)


def _dqn_frame_average(win, dqn_frames: int) -> float:
    if not win or dqn_frames <= 0:
        return 0.0
    return sum(r for r, _, _ in win) / max(1, dqn_frames)


def get_dqn_window_averages() -> tuple[float, float, float]:
    with _dqn_windows_lock:
        return (
            _dqn_frame_average(_dqn100k, _dqn100k_dqn_frames),
            _dqn_frame_average(_dqn1m, _dqn1m_dqn_frames),
            _dqn_frame_average(_dqn5m, _dqn5m_dqn_frames),
        )


def add_episode_to_dqn_perframe_window(dqn_reward: float, dqn_frames: int, ep_len: int = 0):
    """Record one episode's DQN reward sum, DQN-controlled frame count, and total
    episode length.  Eviction is budgeted by *total* frames so the window rolls
    at a fixed wall-clock cadence regardless of the expert ratio."""
    global _dqn_pf_frames, _dqn_pf_total_frames
    if dqn_frames <= 0:
        return
    ep_len = int(ep_len) if ep_len and ep_len > 0 else int(dqn_frames)
    with _dqn_windows_lock:
        _dqn_pf.append((float(dqn_reward), int(dqn_frames), ep_len))
        _dqn_pf_frames += int(dqn_frames)
        _dqn_pf_total_frames += ep_len
        while _dqn_pf and _dqn_pf_total_frames > DQN_PERFRAME_FRAMES:
            _, fr, el = _dqn_pf.popleft()
            _dqn_pf_frames -= fr
            _dqn_pf_total_frames -= el


def get_dqn_perframe_average() -> float:
    """Frame-weighted DQN reward per DQN-controlled frame (expert-independent)."""
    with _dqn_windows_lock:
        if not _dqn_pf or _dqn_pf_frames <= 0:
            return 0.0
        total_r = sum(r for r, _, _ in _dqn_pf)
        return total_r / max(1, _dqn_pf_frames)



def add_episode_to_total_windows(total_reward: float, ep_len: int):
    """Add an episode's total reward to all total-reward rolling windows."""
    global _total100k_frames, _total1m_frames, _total5m_frames
    if ep_len <= 0:
        return
    r = float(total_reward)
    l = int(ep_len)
    with _dqn_windows_lock:
        for buf, frames_ref, limit in (
            (_total100k, "_total100k_frames", DQN100K_FRAMES),
            (_total1m, "_total1m_frames", DQN1M_FRAMES),
            (_total5m, "_total5m_frames", DQN5M_FRAMES),
        ):
            buf.append((r, l))
            cur = globals()[frames_ref] + l
            while buf and cur > limit:
                _, ol = buf.popleft()
                cur -= ol
            globals()[frames_ref] = cur


def get_total_window_averages() -> tuple[float, float, float]:
    with _dqn_windows_lock:
        return _avg_window(_total100k), _avg_window(_total1m), _avg_window(_total5m)


def add_episode_to_eplen_window(ep_len: int):
    """Add an episode's length to the 100K and 1M-frame rolling windows."""
    global _eplen100k_frames, _eplen1m_frames
    if ep_len <= 0:
        return
    l = int(ep_len)
    with _dqn_windows_lock:
        _eplen100k.append((float(l), l))
        _eplen100k_frames += l
        while _eplen100k and _eplen100k_frames > EPLEN100K_FRAMES:
            _, ol = _eplen100k.popleft()
            _eplen100k_frames -= ol

        _eplen1m.append((float(l), l))
        _eplen1m_frames += l
        while _eplen1m and _eplen1m_frames > DQN1M_FRAMES:
            _, ol = _eplen1m.popleft()
            _eplen1m_frames -= ol


def get_eplen_100k_average() -> float:
    with _dqn_windows_lock:
        return _avg_window(_eplen100k) if _eplen100k else 0.0


def get_eplen_1m_average() -> float:
    with _dqn_windows_lock:
        return _avg_window(_eplen1m) if _eplen1m else 0.0


def clear_screen():
    if IS_INTERACTIVE:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def _print_line(msg, is_header=False):
    global row_counter
    if is_header:
        print(msg)
        print("-" * len(msg))
        row_counter = 0
    else:
        print(msg)
        row_counter += 1
    sys.stdout.flush()


def display_metrics_header():
    global row_counter
    row_counter = 0
    hdr = (
        f"{'Frame':>11} {'Steps':>10} {'FPS':>7} {'Epsi':>7} {'Xprt':>7} "
        f"{'Scr1M':>9} {'Lvl1M':>6} "
        f"{'Rwrd':>9} {'Score':>9} {'Shape':>9} {'Death':>9} {'DQN100K/F':>9} {'DQN1M/F':>9} {'DQN5M/F':>9} {'DQN10M/F':>9} "
        f"{'EvalR':>8} {'EScr1M':>8} {'EvalLvl':>7} "
        f"{'Loss':>10} {'AgrM%':>6} {'AgrF%':>6} "
        f"{'EpLen':>8} {'BCLoss':>8} {'BCW':>6} {'SubjW':>6} {'DqnB%':>6} {'EpsB%':>6} {'ExpB%':>6} {'Sync':>5} "
        f"{'Clnt':>4} {'Web':>4} "
        f"{'AvgInf':>7} {'Steps/s':>8} {'Rpl/F':>7} {'GrNorm':>8} {'Q-Range':>14} {'Mem':>10} {'LR':>9} {'Drop':>7} {'Tms S/X/C/P':>17}"
    )
    _print_line(hdr, is_header=True)
    try:
        now = time.time()
        with metrics.lock:
            if metrics.last_fps_time <= 0:
                metrics.last_fps_time = now
    except Exception:
        pass


def display_metrics_row(agent, kb_handler):
    global row_counter
    if row_counter > 0 and row_counter % 30 == 0:
        display_metrics_header()

    # ── Interval averages ───────────────────────────────────────────────
    mean_reward = 0.0
    mean_subj = 0.0
    mean_obj = 0.0
    mean_death = 0.0
    with metrics.lock:
        if metrics.reward_count_interval > 0:
            mean_reward = metrics.reward_sum_interval / max(1, metrics.reward_count_interval)
        if metrics.reward_count_interval_subj > 0:
            mean_subj = metrics.reward_sum_interval_subj / max(1, metrics.reward_count_interval_subj)
        if metrics.reward_count_interval_obj > 0:
            mean_obj = metrics.reward_sum_interval_obj / max(1, metrics.reward_count_interval_obj)
        if metrics.reward_count_interval_death > 0:
            mean_death = metrics.reward_sum_interval_death / max(1, metrics.reward_count_interval_death)
        # Reset
        metrics.reward_sum_interval = metrics.reward_count_interval = 0
        metrics.reward_sum_interval_dqn = metrics.reward_count_interval_dqn = 0
        metrics.reward_sum_interval_subj = metrics.reward_count_interval_subj = 0
        metrics.reward_sum_interval_obj = metrics.reward_count_interval_obj = 0
        metrics.reward_sum_interval_death = metrics.reward_count_interval_death = 0
        if metrics.eval_count_interval > 0:
            eval_reward = metrics.eval_reward_sum_interval / max(1, metrics.eval_count_interval)
            eval_level = metrics.eval_level_sum_interval / max(1, metrics.eval_count_interval)
        else:
            eval_reward = metrics.eval_average_reward
            eval_level = metrics.eval_average_level
        if getattr(metrics, "eval_score_1m_count", 0) > 0:
            eval_score = metrics.eval_score_1m_average
        else:
            eval_score = metrics.eval_average_score
        metrics.eval_reward_sum_interval = 0.0
        metrics.eval_score_sum_interval = 0.0
        metrics.eval_level_sum_interval = 0.0
        metrics.eval_length_sum_interval = 0.0
        metrics.eval_count_interval = 0

    # Fallback to deque
    if mean_reward == 0.0:
        try:
            n = min(len(metrics.episode_rewards), len(metrics.dqn_rewards), 20)
            if n > 0:
                mean_reward = sum(list(metrics.episode_rewards)[-n:]) / n
        except Exception:
            pass

    # ── Loss / agreement / steps/s ──────────────────────────────────────
    loss_avg = 0.0
    agree_move_avg = 0.0
    agree_fire_avg = 0.0
    steps_per_sec = 0.0
    avg_inf_ms = 0.0
    with metrics.lock:
        if metrics.total_inference_requests > 0:
            avg_inf_ms = (metrics.total_inference_time / metrics.total_inference_requests) * 1000
        metrics.total_inference_time = 0.0
        metrics.total_inference_requests = 0

        if metrics.loss_count_interval > 0:
            loss_avg = metrics.loss_sum_interval / max(1, metrics.loss_count_interval)
        if metrics.agree_count_interval > 0:
            agree_move_avg = metrics.agree_move_sum_interval / max(1, metrics.agree_count_interval)
            agree_fire_avg = metrics.agree_fire_sum_interval / max(1, metrics.agree_count_interval)
        metrics.loss_sum_interval = metrics.loss_count_interval = 0
        metrics.agree_sum_interval = metrics.agree_count_interval = 0
        metrics.agree_move_sum_interval = metrics.agree_fire_sum_interval = 0.0

        now = time.time()
        last_t = getattr(metrics, "_last_row_time", 0.0)
        steps_int = metrics.training_steps_interval
        elapsed = now - last_t if last_t > 0 else 1.0
        steps_per_sec = steps_int / max(0.001, elapsed)
        metrics.training_steps_interval = 0
        metrics.frames_count_interval = 0
        metrics._last_row_time = now

    # ── Episode length ──────────────────────────────────────────────────
    avg_ep_len = 0.0
    with metrics.lock:
        if metrics.episode_length_count_interval > 0:
            avg_ep_len = metrics.episode_length_sum_interval / max(1, metrics.episode_length_count_interval)
        metrics.episode_length_sum_interval = 0
        metrics.episode_length_count_interval = 0

    # ── Rolling score / wave ────────────────────────────────────────────
    display_level = metrics.level_1m_average + 1.0
    average_game_score = metrics.score_1m_average

    # ── DQN windows ─────────────────────────────────────────────────────
    dqn100k, dqn1m, dqn5m = get_dqn_window_averages()
    dqn_pf = get_dqn_perframe_average()

    # ── Q range ─────────────────────────────────────────────────────────
    q_range = "N/A"
    if agent:
        try:
            mn, mx = agent.get_q_value_range()
            if not (np.isnan(mn) or np.isnan(mx)):
                q_range = f"[{mn:.1f},{mx:.1f}]"
        except Exception:
            q_range = "err"

    mem_k = metrics.memory_buffer_size // 1000

    # ── Current LR ──────────────────────────────────────────────────────
    lr_str = ""
    if agent and hasattr(agent, "get_lr"):
        try:
            cur_lr = agent.get_lr()
            lr_str = f"{cur_lr:.1e}"
        except Exception:
            lr_str = "?"

    # ── Reward display — scale up by point_reward_scale for readability ──
    _prs = float(RL_CONFIG.point_reward_scale)

    def _fr(v, w=9):
        try:
            return f"{float(v):.1f}".rjust(w)
        except Exception:
            return "0.0".rjust(w)

    def _frp(v, w=8):
        # Per-frame reward is small; keep 3 decimals while below 1 so progress
        # is visible, otherwise fall back to 1 decimal for compactness.
        try:
            fv = float(v)
            return (f"{fv:.3f}" if abs(fv) < 1.0 else f"{fv:.1f}").rjust(w)
        except Exception:
            return "0.000".rjust(w)

    eps_val = metrics.get_effective_epsilon()*100
    xprt_val = metrics.get_expert_ratio()*100
    eps_mark = "*" if game_settings.epsilon_pct >= 0 else ""
    xprt_mark = "*" if game_settings.expert_pct >= 0 else ""
    eps_pct = f"{eps_val:.0f}%{eps_mark}".rjust(7)
    xprt_pct = f"{xprt_val:.0f}%{xprt_mark}".rjust(7)
    subj_w = float(getattr(metrics, "last_subj_positive_weight", 1.0))
    replay_ratio = (steps_per_sec * float(RL_CONFIG.batch_size)) / max(1e-6, float(metrics.fps))
    train_ms = (
        f"{metrics.last_train_sample_ms:.0f}/"
        f"{metrics.last_train_transfer_ms:.0f}/"
        f"{metrics.last_train_compute_ms:.0f}/"
        f"{metrics.last_train_priority_ms:.0f}"
    )

    row = (
        f"{metrics.frame_count:>11,} {metrics.total_training_steps:>10,} {metrics.fps:>7.1f} {eps_pct} {xprt_pct} "
        f"{average_game_score:>9,.0f} {display_level:>6.1f} "
        f"{_fr(mean_reward*_prs)} {_fr(mean_obj*_prs)} {_fr(mean_subj*_prs)} {_fr(mean_death*_prs)} {_fr(dqn100k*_prs)} "
        f"{_fr(dqn1m*_prs)} {_fr(dqn5m*_prs)} {_frp(dqn_pf*_prs, 9)} "
        f"{_fr(eval_reward*_prs, 8)} {eval_score:>8,.0f} {eval_level:>7.1f} "
        f"{loss_avg:>10.6f} {agree_move_avg*100:>5.1f}% {agree_fire_avg*100:>5.1f}% "
        f"{avg_ep_len:>8.1f} {metrics.last_bc_loss:>8.4f} {metrics.last_bc_weight:>6.3f} {subj_w:>6.3f} "
        f"{metrics.last_sample_dqn_frac*100:>5.1f}% {metrics.last_sample_epsilon_frac*100:>5.1f}% {metrics.last_sample_expert_frac*100:>5.1f}% {metrics.last_inference_sync_age:>5} "
        f"{metrics.client_count:>4} {metrics.web_client_count:>4} "
        f"{avg_inf_ms:>7.2f} {steps_per_sec:>8.1f} "
        f"{replay_ratio:>7.2f} {metrics.last_grad_norm:>8.3f} {q_range:>14} {mem_k:>8}k {lr_str:>9} {metrics.replay_dropped_steps:>7,} {train_ms:>17}"
    )
    _print_line(row)
