#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN APPLICATION ENTRY POINT                                                                  ||
# ||  Boots socket server, spawns keyboard/stats threads, coordinates shutdown.                                   ||
# ==================================================================================================================
"""Robotron AI DQN entry point — joint Rainbow-lite engine."""

import os, sys, time, threading, traceback
import json
import shutil
import math
import random
import socket

import numpy as np
import torch

try:
    from .agent import RainbowAgent, KeyboardHandler, print_with_terminal_restore
    from .config import (RL_CONFIG, MODEL_DIR, LATEST_MODEL_PATH, BEST_MODEL_PATH,
                         IS_INTERACTIVE, metrics, SERVER_CONFIG, game_settings)
    from .metrics_display import display_metrics_header, display_metrics_row, clear_screen
    from .socket_server import SocketServer
except ImportError:
    from agent import RainbowAgent, KeyboardHandler, print_with_terminal_restore
    from config import (RL_CONFIG, MODEL_DIR, LATEST_MODEL_PATH, BEST_MODEL_PATH,
                        IS_INTERACTIVE, metrics, SERVER_CONFIG, game_settings)
    from metrics_display import display_metrics_header, display_metrics_row, clear_screen
    from socket_server import SocketServer

# Dashboard is optional — the training loop runs without it.
try:
    from .metrics_dashboard import MetricsDashboard
except Exception:
    try:
        from metrics_dashboard import MetricsDashboard
    except Exception:
        MetricsDashboard = None


def _env_enabled(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "off", "no"}


def _has_desktop_session() -> bool:
    if any(os.getenv(k) for k in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY")):
        return False
    if os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY") or os.getenv("MIR_SOCKET"):
        return True
    if os.getenv("XDG_CURRENT_DESKTOP") or os.getenv("DESKTOP_SESSION"):
        return True
    if (os.getenv("XDG_SESSION_TYPE") or "").strip().lower() in {"x11", "wayland", "mir"}:
        return True
    if os.name == "nt":
        return (os.getenv("SESSIONNAME") or "").strip().lower() != "services"
    if sys.platform == "darwin":
        return True
    return False


def _resolve_dashboard_host() -> str:
    explicit = os.getenv("ROBOTRON_DQN_DASHBOARD_HOST", "").strip()
    if explicit:
        return explicit
    return "127.0.0.1" if _has_desktop_session() else "0.0.0.0"


def _best_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except Exception:
        pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


def _resolve_dashboard_url_host(bind_host: str) -> str:
    explicit = os.getenv("ROBOTRON_DQN_DASHBOARD_PUBLIC_HOST", "").strip()
    if explicit:
        return explicit
    if bind_host in {"0.0.0.0", "::", "[::]"}:
        return _best_lan_ip()
    return bind_host


# ── Buffer stats ────────────────────────────────────────────────────────────
def print_buffer_stats(agent, kb):
    try:
        if not hasattr(agent, "memory") or agent.memory is None:
            print("\nNo replay buffer")
            return
        stats = agent.memory.get_partition_stats()
        print("\n" + "=" * 70)
        print("REPLAY BUFFER STATISTICS".center(70))
        print("=" * 70)
        total = stats.get("total_size", 0)
        cap = stats.get("total_capacity", max(1, total))
        print(f"  Total:   {total:>12,} / {cap:>12,}")
        print(f"  Agent:   {stats.get('dqn', 0):>12,}   ({stats.get('frac_dqn', 0)*100:>5.1f}%)")
        print(f"  Expert:  {stats.get('expert', 0):>12,}   ({stats.get('frac_expert', 0)*100:>5.1f}%)")
        print(f"  DQN src: {stats.get('actor_dqn', 0):>12,}   ({stats.get('frac_actor_dqn', 0)*100:>5.1f}%)")
        print(f"  Eps src: {stats.get('actor_epsilon', 0):>12,}   ({stats.get('frac_actor_epsilon', 0)*100:>5.1f}%)")
        print(f"  Exp src: {stats.get('actor_expert', 0):>12,}   ({stats.get('frac_actor_expert', 0)*100:>5.1f}%)")
        print(f"  Intrst:  {stats.get('interesting', 0):>12,}   ({stats.get('frac_interesting', 0)*100:>5.1f}%)")
        hof = stats.get("hof")
        if hof:
            print("-" * 70)
            print("  HALL OF FAME (permanent, survives wipes/reverts)")
            quota = f"{hof['fraction']*100:.0f}% of batch" if hof["quota_active"] else "inactive (seeding)"
            print(f"  Episodes: {hof['episodes']:>4} / {hof['max_episodes']:<4}  "
                  f"Transitions: {hof['transitions']:>9,}   Quota: {quota}")
            if hof.get("episodes", 0) > 0:
                print(f"  Scores:   best {hof['best']:>9,.0f}   median {hof['median']:>9,.0f}   "
                      f"worst {hof['worst']:>9,.0f}")
            print(f"  Admission bar: {hof['admission_floor']:>9,.0f}  (episodes below this can never enter)")
        print("=" * 70 + "\n")
        if kb and IS_INTERACTIVE:
            kb.set_raw_mode()
    except Exception as e:
        print(f"\nBuffer stats error: {e}")
        if kb and IS_INTERACTIVE:
            kb.set_raw_mode()


# ── Stats reporter thread ──────────────────────────────────────────────────
def stats_reporter(agent, kb):
    print("Starting stats reporter thread...")
    display_metrics_header()
    last = time.time()
    seen = False

    while True:
        try:
            now = time.time()
            if now - last >= 30.0:
                display_metrics_row(agent, kb)
                last = now
            srv = metrics.global_server
            if srv is None:
                time.sleep(0.1)
                continue
            if getattr(srv, "running", False):
                seen = True
            elif seen:
                print("Server stopped, exiting stats reporter")
                break
            time.sleep(0.1)
        except Exception as e:
            print(f"Stats reporter error: {e}")
            traceback.print_exc()
            break


# ── Keyboard handler thread ────────────────────────────────────────────────
def _collapse_signals(agent, best_escr1m: float = 0.0) -> str | None:
    """Return a reason string when a collapse signature is present, else None.

    Signature A (terminal): near-zero TD loss AND expected Q pinned at the
    C51 support ceiling — the silent zero-loss fixed point the 2026-07-12
    week-long run died in.

    Signature B (sag): TD loss below the healthy band while the eval score
    sits far below the recorded best, Q nowhere near the ceiling — the
    gradient-starvation decline that rolled EScr1M 415K→210K (loss 0.004,
    Q upper 10-21).  Gated on a ~full eval window so a refilling window
    after a restart cannot false-fire, and on best_escr1m > 0 so a fresh
    record file disables it rather than comparing against zero.
    """
    try:
        loss = float(getattr(metrics, "last_loss", 0.0))

        # A: terminal fixed point
        if loss < float(getattr(RL_CONFIG, "collapse_loss_threshold", 0.02)):
            _, q_max = agent.get_q_value_range()
            if not math.isnan(q_max) and q_max > float(getattr(RL_CONFIG, "collapse_q_upper_frac", 0.90)) * float(RL_CONFIG.v_max):
                return f"terminal: loss {loss:.4f} with Q pinned at support ceiling"

        # B/B2: score-based signatures need the eval window
        if best_escr1m > 0.0:
            with metrics.lock:
                escr1m = float(metrics.eval_score_1m_average)
                window_full = int(metrics.eval_score_1m_frames) >= int(0.9 * int(metrics.eval_score_1m_window))
            if window_full:
                # B: gradient-starvation sag (low loss corroborates)
                if loss < float(getattr(RL_CONFIG, "collapse_sag_loss_threshold", 0.12)):
                    frac = float(getattr(RL_CONFIG, "collapse_sag_escr1m_frac", 0.75))
                    if escr1m < frac * best_escr1m:
                        return (f"sag: loss {loss:.4f} with EScr1M {escr1m:,.0f} "
                                f"< {frac:.0%} of best {best_escr1m:,.0f}")
                # B2: deep score collapse regardless of loss — the wave-1 run
                # regressed 305K->65K at HEALTHY loss 0.39-0.41, unreachable
                # by B's loss conjunct.  best.pt is the only true external
                # memory of peak play; a sustained sub-50% eval score is
                # actionable no matter what the loss says.
                frac2 = float(getattr(RL_CONFIG, "collapse_score_only_frac", 0.50))
                if frac2 > 0.0 and escr1m < frac2 * best_escr1m:
                    return (f"score-collapse: EScr1M {escr1m:,.0f} < {frac2:.0%} "
                            f"of best {best_escr1m:,.0f} (loss {loss:.4f})")

        return None
    except Exception:
        return None


def _restore_best_checkpoint(agent) -> bool:
    """Pause training, reload the best-EScr1M checkpoint, wipe the replay
    buffer, resume.  The buffer wipe is essential: restoring good weights
    into 10M transitions of degenerate play just re-teaches the collapse.
    After the wipe, train_step()'s min_replay_to_train gate holds training
    until fresh experience (generated by the restored policy) accumulates.
    """
    if not os.path.exists(BEST_MODEL_PATH):
        print("[COLLAPSE WATCHDOG] no best checkpoint on disk — cannot restore")
        return False
    agent.training_enabled = False
    time.sleep(3.0)  # drain any in-flight train step
    ok = False
    try:
        ok = agent.load(BEST_MODEL_PATH, show_status=False)
        if ok:
            agent.memory.clear()
            print("[COLLAPSE WATCHDOG] best checkpoint restored, replay buffer wiped — "
                  "training resumes automatically once the buffer refills")
            # The automated 2026-07-19 intervention: a frontier collapse means
            # climb-gear pressure exceeded the policy's stability envelope —
            # a plain restore re-collapses (~75K steps, observed twice), but
            # restore + downshift climbed 950K -> 1.68M+.  Shift permanently.
            if bool(getattr(RL_CONFIG, "auto_lr_gearbox", False)):
                agent.shift_to_hold_gear(reason="collapse watchdog restore")
        else:
            print("[COLLAPSE WATCHDOG] best checkpoint failed to load — leaving weights as-is")
    except Exception as e:
        print(f"[COLLAPSE WATCHDOG] restore failed: {e}")
        ok = False
    finally:
        agent.training_enabled = True
    return ok


def keyboard_handler(agent, kb):
    print("Starting keyboard handler thread...")
    while True:
        try:
            key = kb.check_key()
            if not key:
                time.sleep(0.1)
                continue

            if key == "q":
                print("Quit requested...")
                try:
                    if metrics.global_server:
                        metrics.global_server.running = False
                        metrics.global_server.stop()
                except Exception:
                    pass
                try:
                    agent.stop()
                except Exception:
                    pass
                break
            elif key == "s":
                print("Saving model...")
                agent.save(LATEST_MODEL_PATH, is_forced_save=True)
            elif key == "o":
                metrics.toggle_override(kb)
                display_metrics_row(agent, kb)
            elif key == "e":
                metrics.toggle_expert_mode(kb)
                display_metrics_row(agent, kb)
            elif key == "P":
                metrics.toggle_epsilon_pulse(kb)
                if metrics.manual_pulse_active:
                    frames = metrics.manual_pulse_frames_remaining
                    print_with_terminal_restore(kb, f"\nManual pulse FIRED — {frames:,} frames at ε={RL_CONFIG.manual_pulse_epsilon}")
                else:
                    print_with_terminal_restore(kb, "\nManual pulse CANCELLED")
                display_metrics_row(agent, kb)
            elif key == "p":
                metrics.toggle_epsilon_override(kb)
                display_metrics_row(agent, kb)
            elif key.lower() == "v":
                metrics.toggle_verbose_mode(kb)
                display_metrics_row(agent, kb)
            elif key.lower() == "t":
                metrics.toggle_training_mode(kb)
                agent.training_enabled = metrics.training_enabled
                display_metrics_row(agent, kb)
            elif key.lower() == "c":
                clear_screen()
                display_metrics_header()
            elif key.lower() == "h":
                display_metrics_header()
            elif key == " ":
                display_metrics_row(agent, kb)
            elif key == "7":
                metrics.decrease_expert_ratio(kb)
                display_metrics_row(agent, kb)
            elif key == "8":
                metrics.restore_natural_expert_ratio(kb)
                display_metrics_row(agent, kb)
            elif key == "9":
                metrics.increase_expert_ratio(kb)
                display_metrics_row(agent, kb)
            elif key == "4":
                metrics.decrease_epsilon(kb)
                display_metrics_row(agent, kb)
            elif key == "5":
                metrics.restore_natural_epsilon(kb)
                display_metrics_row(agent, kb)
            elif key == "6":
                metrics.increase_epsilon(kb)
                display_metrics_row(agent, kb)
            elif key == "a":
                print_with_terminal_restore(kb, "\nAnalyzing attention patterns...")
                report = agent.diagnose_attention()
                print_with_terminal_restore(kb, report)
            elif key == "r":
                print_with_terminal_restore(kb, "\nResetting attention weights (keeping trunk + heads)...")
                agent.reset_attention_weights()
                display_metrics_row(agent, kb)
            elif key == "b":
                print_buffer_stats(agent, kb)
            elif key == "f":
                print_with_terminal_restore(kb, "\nFlushing replay buffer...")
                agent.flush_replay_buffer()
                print_with_terminal_restore(kb, "Replay buffer flushed.")
                display_metrics_row(agent, kb)
            elif key == "L":
                RL_CONFIG.lr = min(1e-2, RL_CONFIG.lr * 2.0)
                print_with_terminal_restore(kb, f"LR increased to {RL_CONFIG.lr:.2e}")
                display_metrics_row(agent, kb)
            elif key == "l":
                RL_CONFIG.lr = max(1e-6, RL_CONFIG.lr / 2.0)
                print_with_terminal_restore(kb, f"LR decreased to {RL_CONFIG.lr:.2e}")
                display_metrics_row(agent, kb)

            time.sleep(0.1)
        except BlockingIOError:
            time.sleep(0.1)
            continue
        except Exception as e:
            try:
                print(f"Keyboard error: {e}")
            except BlockingIOError:
                pass
            break


# ── Network info ────────────────────────────────────────────────────────────
def print_network_info(agent, dashboard_status: str = "disabled"):
    print("\n" + "=" * 90)
    print("ROBOTRON AI — Joint DQN Engine".center(90))
    print("=" * 90)

    net = agent.online_net
    tp = sum(p.numel() for p in net.parameters())
    tr = sum(p.numel() for p in net.parameters() if p.requires_grad)

    print(f"\nArchitecture:")
    single_state = int(getattr(RL_CONFIG, "single_frame_state_size", agent.state_size))
    frame_stack = int(getattr(RL_CONFIG, "frame_stack", 1))
    raw_trunk = int(getattr(agent.online_net, "raw_trunk_state_size", single_state * frame_stack))
    trunk_in = raw_trunk
    if getattr(agent.online_net, "use_attn", False):
        trunk_in += int(getattr(RL_CONFIG, "attn_dim", 0))
    if getattr(agent.online_net, "use_object_attn", False):
        trunk_in += int(getattr(RL_CONFIG, "object_attn_dim", 0))
    print(f"   State size:       {agent.state_size}  ({single_state} x {frame_stack} frames)")
    print(f"   Single frame:     {RL_CONFIG.core_features} core + {RL_CONFIG.elist_features} ELIST + {RL_CONFIG.enemy_token_count} grouped objects x {RL_CONFIG.enemy_token_features}")
    print(f"   Trunk input:      {trunk_in}  ({raw_trunk} raw compact state + additive attention)")
    print(f"   Actions:          {RL_CONFIG.num_move_actions} move x {RL_CONFIG.num_fire_actions} fire (joint 81-action head, idle=8)")
    trunk_layers = tuple(int(v) for v in getattr(RL_CONFIG, "trunk_layer_sizes", ()) if int(v) > 0)
    trunk_txt = " -> ".join(str(v) for v in trunk_layers) if trunk_layers else f"{RL_CONFIG.trunk_layers} x {RL_CONFIG.trunk_hidden}"
    print(f"   Trunk:            {trunk_txt}")
    print(f"   Lane attention:   OFF (removed from learner input)")
    print(f"   Object attention: {'ON' if RL_CONFIG.use_object_attention else 'OFF'} ({RL_CONFIG.object_attn_heads} heads, dim={RL_CONFIG.object_attn_dim})")
    print(f"   Action attention: {'ON' if RL_CONFIG.use_action_context_attention else 'OFF'}")
    print(f"   Distributional:   {'C51 ({} atoms, [{}, {}])'.format(RL_CONFIG.num_atoms, RL_CONFIG.v_min, RL_CONFIG.v_max) if RL_CONFIG.use_distributional else 'OFF'}")
    print(f"   Dueling:          {'ON' if RL_CONFIG.use_dueling else 'OFF'}")
    print(f"   Parameters:       {tp:,} total, {tr:,} trainable")

    print(f"\nTraining:")
    print(f"   LR:               {RL_CONFIG.lr:.2e} -> {RL_CONFIG.lr_min:.2e} (cosine)")
    print(f"   Batch size:       {RL_CONFIG.batch_size}")
    print(f"   gamma = {RL_CONFIG.gamma},  n-step = {RL_CONFIG.n_step}")
    print(f"   PER alpha={RL_CONFIG.priority_alpha}, beta={RL_CONFIG.priority_beta_start}->1.0")
    print(f"   Target update:    every {RL_CONFIG.target_update_period} steps (hard)")
    print(f"   Grad clip:        {RL_CONFIG.grad_clip_norm}")

    print(f"\nExploration:")
    print(f"   eps:    {RL_CONFIG.epsilon_start} -> {RL_CONFIG.epsilon_end} over {RL_CONFIG.epsilon_decay_frames:,} learner-controlled frames")
    _xp_hold = int(RL_CONFIG.expert_ratio_decay_start_step)
    _xp_hold_txt = f" (after {_xp_hold:,} step hold)" if _xp_hold > 0 else ""
    print(f"   Expert: {RL_CONFIG.expert_ratio_start*100:.0f}% -> {RL_CONFIG.expert_ratio_end*100:.0f}% over {RL_CONFIG.expert_ratio_decay_steps:,} train steps{_xp_hold_txt}")
    print(f"   BC weight: {RL_CONFIG.expert_bc_weight} -> {RL_CONFIG.expert_bc_min_weight} over {RL_CONFIG.expert_bc_decay_steps:,} train steps (after {RL_CONFIG.expert_bc_decay_start_step:,} step hold)")
    print(f"   Eval clients: every {RL_CONFIG.eval_client_stride}th client at eps={RL_CONFIG.eval_epsilon:.2f}, no replay writes")

    print(f"\nServices:")
    print(f"   Dashboard:        {dashboard_status}")

    print(f"\nKeys: [q]uit [s]ave [c]lear [h]eader [space]row [o]verride [e]xpert [p]epsilon [t]rain [v]erbose [a]ttention")
    print(f"   [7/8/9] expert-/reset/+   [4/5/6] epsilon-/reset/+   [b] buffer stats   [f] flush buffer")
    print("\n" + "=" * 90 + "\n")


# ── Main ────────────────────────────────────────────────────────────────────
class RatchetController:
    """Monotonic policy improvement via train → freeze → measure → keep-or-rollback.

    Rationale (2026-07-15): on this system, gradient descent reliably makes a
    good policy WORSE — the untouched 415K checkpoint evals at 215-270K, and
    every training configuration tried (including the exact code that produced
    it) drives it to ~39-75K within ~13k steps.  So stop trusting the gradient
    and gate it: the incumbent policy is only ever replaced by a candidate that
    MEASURED better under an identical frozen all-greedy wave-1 protocol.  The
    served policy cannot get worse by construction; destructive training
    becomes a low accept rate instead of a collapse.

    Measurement protocol (all enforced by metrics.ratchet_frozen, a dedicated
    flag no operator surface can touch): gradient quiesced, whole fleet greedy
    (epsilon 0, expert 0), wave-1 starts, replay writes/boosts/HOF admission
    suspended.  The sample is a START-side cohort: every game beginning within
    ratchet_eval_cohort_s of the freeze is in, and the phase waits for ALL of
    them — no completion-time censoring of long (high-scoring) games.

    Acceptance is a difference-of-means test: candidate mean must exceed the
    incumbent mean by the margin plus z combined standard errors
    (sqrt(se_c^2 + se_i^2)) — both measurements are noisy, not just the
    candidate's.  On reject: EXACT rollback (weights/target/optimizer/scaler/
    schedule clocks), RNG reseed, window halves.  On accept: candidate becomes
    incumbent (RAM snapshot + disk), window grows back toward base.

    Suspended while active (the measured incumbent subsumes them): collapse
    watchdog, legacy rolling-window best-save, periodic latest.pt autosave.
    On restart, boot prefers the on-disk incumbent over latest.pt so a crash
    can never resurrect an unvetted candidate.
    """

    INCUMBENT_PATH = os.path.join(MODEL_DIR, "robotron_dqn_ratchet_incumbent.pt")

    def __init__(self, agent):
        self.agent = agent
        # Incumbent-as-behavior: the fleet plays the measured incumbent at all
        # times; candidates exist only inside the online net during training
        # and only ever act during their own frozen measurement.  Kills the
        # replay-data spiral (see agent._sync_inference) and pegs training
        # data quality to the best-known policy.
        agent.behavior_locked = True
        if not getattr(agent, "use_separate_inference", False):
            print("[RATCHET] WARN: no separate inference net — behavior lock "
                  "inactive; candidate play will enter the ring during training")
        cfg = RL_CONFIG
        self.base_window = max(1, int(getattr(cfg, "ratchet_train_steps", 2_000)))
        self.min_window = max(1, int(getattr(cfg, "ratchet_min_train_steps", 250)))
        self.window = self.base_window
        self.eval_episodes = max(5, int(getattr(cfg, "ratchet_eval_episodes", 40)))
        self.cohort_s = max(30.0, float(getattr(cfg, "ratchet_eval_cohort_s", 240.0)))
        self.timeout_s = max(120.0, float(getattr(cfg, "ratchet_eval_timeout_s", 1_200.0)))
        self.max_extends = max(0, int(getattr(cfg, "ratchet_eval_max_extends", 3)))
        self.margin = float(getattr(cfg, "ratchet_accept_margin", 0.01))
        self.accept_z = float(getattr(cfg, "ratchet_accept_z", 1.0))
        self.reseed = bool(getattr(cfg, "ratchet_reseed_on_reject", True))

        self.phase = "boot"          # boot -> eval -> train -> eval -> ...
        self.epoch = 0
        self.incumbent = None        # in-RAM training-state snapshot
        self.incumbent_score = None
        self.incumbent_scores = []   # the incumbent's own measurement sample
        self.accepts = 0
        self.rejects = 0
        self.consecutive_rejects = 0
        self._eval_t0 = 0.0
        self._train_end_step = 0
        self._extends = 0
        # Pipeline + bar hygiene (2026-07-15)
        self.pipeline = bool(getattr(cfg, "ratchet_pipeline", True))
        self.remeasure_after = max(0, int(getattr(cfg, "ratchet_remeasure_after_rejects", 6)))
        self._pending_candidate = None   # snapshot of the candidate under measurement
        self._next_candidate = None      # pre-trained next candidate (pipeline)
        self._pipe_active = False
        self._pipe_end_step = 0
        self._measuring_incumbent = False

    # ── helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _log(msg: str):
        try:
            print(msg)
        except Exception:
            pass                     # non-blocking stdout can raise; never let
                                     # logging corrupt state-machine flow

    def _quiesce(self, max_wait_s: float = 3.0):
        """Wait for the TrainWorker to finish any in-flight step.

        training_enabled is only checked at step START; a step already past
        the check keeps mutating weights/optimizer.  Snapshotting, restoring,
        or force-syncing concurrently would copy torn tensors.  Poll the step
        counter until it is stable, bounded (same 3s precedent as
        _restore_best_checkpoint's drain).
        """
        deadline = time.time() + max_wait_s
        last = int(self.agent.training_steps)
        stable_since = time.time()
        while time.time() < deadline:
            time.sleep(0.1)
            now_steps = int(self.agent.training_steps)
            if now_steps != last:
                last = now_steps
                stable_since = time.time()
            elif time.time() - stable_since >= 0.3:
                return
        self._log("[RATCHET] WARN: trainer did not quiesce within "
                  f"{max_wait_s:.1f}s — proceeding")

    # ── phase transitions ────────────────────────────────────────────────
    def _enter_eval(self):
        self.agent.training_enabled = False
        self._quiesce()
        # The last <sync-interval steps of the window aren't in the infer net
        # yet — push them so the fleet plays exactly the candidate.
        self.agent._sync_inference(force=True)
        now = time.time()
        # Incumbent measurements get a longer start-window: their SE enters
        # every future gate, so extra precision here pays forever.
        _mult = float(getattr(RL_CONFIG, "ratchet_incumbent_cohort_mult", 1.0))             if (self.epoch == 0 or self._measuring_incumbent) else 1.0
        _window_s = self.cohort_s * max(1.0, _mult)
        with metrics.lock:
            metrics.ratchet_eval_scores = []
            metrics.ratchet_eval_epoch = self.epoch
            metrics.ratchet_eval_collect_t0 = now
            metrics.ratchet_eval_cohort_close_ts = now + _window_s
            metrics.ratchet_eval_cohort_started = 0
            # THE protocol switch: greedy epsilon/expert, wave-1 starts,
            # replay/boost/HOF gating — all consulted directly off this flag,
            # no operator state touched (dashboard POSTs cannot contaminate
            # the measurement or persist ratchet state to disk).
            metrics.ratchet_frozen = True
        self._eval_t0 = now
        self._extends = 0
        self.phase = "eval"
        # The accept path must take exactly the weights being MEASURED — the
        # pipeline moves the online net during the measurement, so bank them.
        self._pending_candidate = self.agent.snapshot_training_state()
        # Pipeline: the GPU idles through the ~5-7 min measurement otherwise.
        # Restore the incumbent into the ONLINE net (infer net untouched — it
        # serves the frozen candidate) and train the NEXT candidate now.
        self._pipe_active = False
        if self.pipeline and self.incumbent is not None:
            try:
                self.agent.restore_training_state(self.incumbent, sync_inference=False)
                if bool(getattr(RL_CONFIG, "ratchet_fresh_optimizer", False)):
                    self.agent.ratchet_begin_window(
                        int(getattr(RL_CONFIG, "ratchet_window_warmup_steps", 200)))
                self._pipe_end_step = int(self.agent.training_steps) + self.window
                self.agent.training_enabled = True
                self._pipe_active = True
            except Exception as e:
                self._log(f"[RATCHET] WARN: pipeline setup failed: {e}")
        if self._measuring_incumbent:
            what = "INCUMBENT (bar re-measure)"
        elif self.epoch == 0:
            what = "incumbent (loaded checkpoint)"
        else:
            what = f"candidate (epoch {self.epoch})"
        pipe = " | pipelining next candidate" if self._pipe_active else ""
        self._log(f"[RATCHET] epoch {self.epoch} EVAL: measuring {what} — fleet greedy wave-1, "
                  f"cohort window {self.cohort_s:.0f}s, waiting for all cohort games{pipe}")

    def _exit_eval_to_train(self):
        with metrics.lock:
            metrics.ratchet_frozen = False
            metrics.ratchet_eval_epoch = -1
            metrics.ratchet_eval_collect_t0 = 0.0
            metrics.ratchet_eval_cohort_close_ts = 0.0
        # Data floor: a candidate window must never train against a thin ring
        # (measured: 2M samples vs a 33K-180K ring bulldozed the checkpoint to
        # 70K in one window).  Sit in a fill phase — fleet playing the
        # incumbent, writes flowing — until the floor is met.  The ring only
        # ever grows, so this costs minutes once and is free thereafter.
        floor = int(getattr(RL_CONFIG, "ratchet_min_ring_transitions", 0))
        try:
            ring = len(self.agent.memory)
        except Exception:
            ring = floor            # no real buffer (tests) — skip the gate
        if ring < floor:
            self.agent.training_enabled = False
            self.phase = "fill"
            self._fill_last_log = time.time()
            self._log(f"[RATCHET] epoch {self.epoch} FILL: ring {ring:,}/{floor:,} "
                      f"incumbent transitions before the next window")
            return
        self._enter_train()

    def _enter_train(self):
        self._train_end_step = int(self.agent.training_steps) + self.window
        fresh = bool(getattr(RL_CONFIG, "ratchet_fresh_optimizer", False))
        if fresh:
            # Kill the stale-Adam-moments shock: zero optimizer state and ramp
            # the LR over the first steps of every candidate window.
            try:
                self.agent.ratchet_begin_window(
                    int(getattr(RL_CONFIG, "ratchet_window_warmup_steps", 200)))
            except Exception as e:
                self._log(f"[RATCHET] WARN: fresh-optimizer setup failed: {e}")
        self.agent.training_enabled = True
        self.phase = "train"
        self._log(f"[RATCHET] epoch {self.epoch} TRAIN: {self.window:,} steps "
                  f"(through step {self._train_end_step:,})"
                  + (" — fresh optimizer + warmup" if fresh else ""))

    def _abort_eval(self, reason: str):
        """Eval could not produce a usable sample (dead fleet, wedged clients).
        Fail SAFE: restore the incumbent if one exists, count nothing, move on."""
        self._log(f"[RATCHET] epoch {self.epoch} ABORTED: {reason}")
        if self.incumbent is not None and self.epoch > 0:
            self.agent.restore_training_state(self.incumbent)
        self.epoch += 1
        self._exit_eval_to_train()

    # ── decisions ────────────────────────────────────────────────────────
    def _decide(self, scores):
        # Freeze any in-flight pipeline window (and the keyboard-'t' case)
        # before touching snapshots — no torn tensors.
        self.agent.training_enabled = False
        self._quiesce(max_wait_s=1.5)
        if self._pipe_active:
            # Incomplete window: discard (costs ~seconds of GPU; keeps every
            # measured candidate a full-window candidate).  Put the incumbent
            # back in the online net so no later path trains on top of a
            # half-window (fleet-facing net untouched until transitions).
            self._pipe_active = False
            self._next_candidate = None
            if self.incumbent is not None:
                try:
                    self.agent.restore_training_state(self.incumbent, sync_inference=False)
                except Exception as e:
                    self._log(f"[RATCHET] WARN: pipeline-discard restore failed: {e}")
        mean = float(np.mean(scores))
        med = float(np.median(scores))
        n = len(scores)
        sd = float(np.std(scores, ddof=1)) if n > 1 else 0.0
        se_c = sd / math.sqrt(max(1, n))

        if self.epoch == 0:
            # State first, logging last — a print() exception must never
            # cause a re-decide with doubled side effects.
            self.incumbent = self.agent.snapshot_training_state()
            self.incumbent_score = mean
            self.incumbent_scores = list(scores)
            self.epoch += 1
            self._exit_eval_to_train()
            try:
                self.agent.save(self.INCUMBENT_PATH, is_forced_save=False,
                                show_status=False, save_replay=False)
            except Exception as e:
                self._log(f"[RATCHET] WARN: incumbent save failed: {e}")
            self._log(f"[RATCHET] epoch 0 BASELINE: incumbent = {mean:,.0f} "
                      f"(median {med:,.0f}, ±SE {se_c:,.0f}, n={n}) — the bar every "
                      f"candidate must beat")
            return

        if self._measuring_incumbent:
            # Bar-hygiene pass: the incumbent's WEIGHTS are untouched; only the
            # number candidates must beat is refreshed (kills winner's-curse
            # inflation from a lucky past accept).
            self._measuring_incumbent = False
            old = self.incumbent_score
            self.incumbent_score = mean
            self.incumbent_scores = list(scores)
            self.consecutive_rejects = 0
            self.epoch += 1
            self._advance_after_decision(restore_first=False)
            self._log(f"[RATCHET] incumbent RE-MEASURED: {mean:,.0f} "
                      f"(median {med:,.0f}, n={n}; bar was {old:,.0f}) — bar reset to reality")
            return

        # Difference-of-means gate: BOTH measurements are noisy.  Requiring
        # the candidate to clear the margin by z combined standard errors
        # keeps the ratchet from advancing on sampling luck (winner's curse:
        # bar inflates, weights don't).
        inc_n = max(1, len(self.incumbent_scores))
        inc_sd = float(np.std(self.incumbent_scores, ddof=1)) if inc_n > 1 else 0.0
        se_i = inc_sd / math.sqrt(inc_n)
        need = self.incumbent_score * self.margin + self.accept_z * math.sqrt(se_c ** 2 + se_i ** 2)
        delta = mean - self.incumbent_score

        if delta >= need:
            epoch_done = self.epoch
            prev = self.incumbent_score
            self.accepts += 1
            self.consecutive_rejects = 0
            # The measured weights were banked at eval entry — the online net
            # may hold a half-trained pipelined successor by now.
            self.incumbent = self._pending_candidate or self.agent.snapshot_training_state()
            self.incumbent_score = mean
            self.incumbent_scores = list(scores)
            self.window = min(self.base_window, self.window * 2)
            self._next_candidate = None      # was perturbed from the OLD incumbent
            self.agent.restore_training_state(self.incumbent)
            self.epoch += 1
            self._exit_eval_to_train()
            try:
                self.agent.save(self.INCUMBENT_PATH, is_forced_save=False,
                                show_status=False, save_replay=False)
            except Exception as e:
                self._log(f"[RATCHET] WARN: incumbent save failed: {e}")
            self._log(f"[RATCHET] epoch {epoch_done} ACCEPT ✓ {mean:,.0f} "
                      f"(median {med:,.0f}, n={n}) beats {prev:,.0f} by {delta:,.0f} "
                      f"(needed {need:,.0f}) — incumbent advanced "
                      f"({self.accepts} accepts / {self.rejects} rejects)")
        else:
            epoch_done = self.epoch
            self.rejects += 1
            self.consecutive_rejects += 1
            if self.reseed:
                seed = (int(time.time() * 1000) ^ (self.epoch * 2_654_435_761)) & 0x7FFFFFFF
                random.seed(seed)
                np.random.seed(seed & 0xFFFFFFFF)
                torch.manual_seed(seed)
            self.window = max(self.min_window, self.window // 2)
            self.epoch += 1
            if self.remeasure_after and self.consecutive_rejects >= self.remeasure_after:
                # Wall of rejects: the bar may be a lucky ghost.  Measure the
                # incumbent itself next; weights untouched, bar refreshed.
                self._next_candidate = None
                self._measuring_incumbent = True
                self._advance_after_decision(restore_first=True)
                self._log(f"[RATCHET] epoch {epoch_done} REJECT ✗ {mean:,.0f} "
                          f"(Δ{delta:+,.0f}, needed +{need:,.0f}) — {self.consecutive_rejects} "
                          f"consecutive → RE-MEASURING the incumbent to reset the bar")
            elif self._next_candidate is not None:
                # Pipelined successor goes straight to measurement — no train
                # phase, the epoch collapses to eval wall-time.
                nxt = self._next_candidate
                self._next_candidate = None
                self.agent.restore_training_state(nxt, sync_inference=False)
                self._enter_eval()
                self._log(f"[RATCHET] epoch {epoch_done} REJECT ✗ {mean:,.0f} "
                          f"(median {med:,.0f}, n={n}) vs incumbent {self.incumbent_score:,.0f} "
                          f"(Δ{delta:+,.0f}, needed +{need:,.0f}) — pipelined candidate "
                          f"entering measurement immediately (window {self.window:,}, "
                          f"{self.consecutive_rejects} consecutive)")
            else:
                self.agent.restore_training_state(self.incumbent)
                self._exit_eval_to_train()
                self._log(f"[RATCHET] epoch {epoch_done} REJECT ✗ {mean:,.0f} "
                          f"(median {med:,.0f}, n={n}) vs incumbent {self.incumbent_score:,.0f} "
                          f"(Δ{delta:+,.0f}, needed +{need:,.0f}) — incumbent restored, "
                          f"window→{self.window:,}, reseeded "
                          f"({self.consecutive_rejects} consecutive)")

    def _advance_after_decision(self, restore_first: bool):
        """Route to the next measurement or train phase after a bar re-measure
        trigger or completion.  restore_first puts the incumbent back in the
        online net (and the fleet) before the next eval begins."""
        if restore_first:
            self.agent.restore_training_state(self.incumbent)
        if self._next_candidate is not None and not self._measuring_incumbent:
            nxt = self._next_candidate
            self._next_candidate = None
            self.agent.restore_training_state(nxt, sync_inference=False)
            self._enter_eval()
        elif self._measuring_incumbent:
            self._enter_eval()
        else:
            self._exit_eval_to_train()

    # ── per-second tick from the supervision loop ────────────────────────
    def tick(self):
        if self.phase == "boot":
            # Fresh frames only: frame_count is restored from the checkpoint,
            # so gate on frames played THIS process, plus live clients.
            fresh = int(metrics.frame_count) - int(getattr(metrics, "loaded_frame_count", 0))
            if int(getattr(metrics, "client_count", 0)) > 0 and fresh > 10_000:
                self._enter_eval()
            return

        if self.phase == "fill":
            floor = int(getattr(RL_CONFIG, "ratchet_min_ring_transitions", 0))
            try:
                ring = len(self.agent.memory)
            except Exception:
                ring = floor
            if ring >= floor:
                self._enter_train()
            elif time.time() - getattr(self, "_fill_last_log", 0.0) >= 60.0:
                self._fill_last_log = time.time()
                self._log(f"[RATCHET] FILL: {ring:,}/{floor:,} transitions "
                          f"({100.0*ring/max(1,floor):.0f}%)")
            return

        if self.phase == "train":
            if int(self.agent.training_steps) >= self._train_end_step:
                self._enter_eval()
            return

        if self.phase == "eval":
            if self._pipe_active:
                # The pipelined window trains DURING the measurement; freeze
                # and bank it the moment it completes its step budget.
                if int(self.agent.training_steps) >= self._pipe_end_step:
                    self.agent.training_enabled = False
                    self._quiesce(max_wait_s=1.5)
                    self._next_candidate = self.agent.snapshot_training_state()
                    self._pipe_active = False
                    self._log("[RATCHET] pipeline: next candidate trained and banked")
            elif self.agent.training_enabled:
                # 't'-key guard (only meaningful when no pipeline window runs)
                self.agent.training_enabled = False
                self._log("[RATCHET] NOTE: training re-enabled externally during a "
                          "measurement — frozen again (use 't' outside eval phases)")
            now = time.time()
            with metrics.lock:
                scores = list(metrics.ratchet_eval_scores)
                started = int(metrics.ratchet_eval_cohort_started)
                close_ts = float(metrics.ratchet_eval_cohort_close_ts)
            cohort_closed = now > close_ts

            if cohort_closed and started >= 5 and len(scores) >= started:
                # Whole cohort finished — the unbiased sample.
                self._decide(scores)
                return
            if now - self._eval_t0 > self.timeout_s:
                if len(scores) >= max(5, min(started, self.eval_episodes) // 3):
                    self._log(f"[RATCHET] eval timeout: deciding on {len(scores)}/{started} "
                              f"cohort games (stragglers censored)")
                    self._decide(scores)
                elif self._extends < self.max_extends:
                    self._extends += 1
                    self._eval_t0 = time.time()
                    self._log(f"[RATCHET] eval timeout with {len(scores)}/{started} games — "
                              f"extending ({self._extends}/{self.max_extends}); check the fleet")
                else:
                    self._abort_eval(f"no usable sample after {self.max_extends} extensions "
                                     f"({len(scores)}/{started} games)")


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Ratchet mode must be known BEFORE the agent exists: the freeze has to be
    # in place before any checkpoint loads or the TrainWorker could squeeze
    # gradient steps into the epoch-0 "untouched checkpoint" baseline.
    ratchet_on = bool(getattr(RL_CONFIG, "ratchet_enabled", False)) or \
        os.getenv("DQN_RATCHET", "").strip().lower() in ("1", "true", "yes", "on")

    agent = RainbowAgent(state_size=RL_CONFIG.state_size)
    if ratchet_on:
        agent.training_enabled = False
    dev = getattr(agent.device, "type", "unknown")
    print(f"Device: {dev.upper()}")

    # CPU guard (2026-07-16): launching with the system python instead of the
    # project venv silently yields a CPU-ONLY torch build — inference goes
    # ~6ms -> ~500-850ms, the fleet drops to ~7 fps, both GPUs sit at 0%, and
    # nothing in the dashboard says why.  A 100x slowdown must never be a
    # silent default.  Override with DQN_ALLOW_CPU=1 for genuine CPU runs.
    if dev != "cuda" and not _env_enabled("DQN_ALLOW_CPU", False):
        import torch as _t
        print("=" * 70)
        print("REFUSING TO START ON CPU — this is almost certainly the wrong python.")
        print(f"  torch: {_t.__version__}   cuda available: {_t.cuda.is_available()}")
        print(f"  running: {sys.executable}")
        print("  Expected the project venv, e.g.:")
        print("    /home/dave/source/repos/ai/venv/bin/python3 -Xgil=0 Scripts/run_dqn.py")
        print("  (CPU inference is ~100x slower: ~7 fps vs ~4000, GPUs idle.)")
        print("  Set DQN_ALLOW_CPU=1 if you really mean it.")
        print("=" * 70)
        sys.exit(2)

    dashboard = None
    dashboard_status = "disabled"

    # Boot preference (review fix): latest.pt is autosaved with CANDIDATE
    # weights mid-window; resuming from it would re-baseline the ratchet on an
    # unvetted policy.  The on-disk incumbent is the last MEASURED winner —
    # prefer it whenever the ratchet is active.
    boot_path = LATEST_MODEL_PATH
    if ratchet_on and os.path.exists(RatchetController.INCUMBENT_PATH):
        boot_path = RatchetController.INCUMBENT_PATH
        print(f"RATCHET: booting from measured incumbent ({boot_path})")

    if os.path.exists(boot_path):
        loaded = agent.load(boot_path)
        if loaded:
            print(f"Loaded model from: {boot_path}\n")
        else:
            print("Model load failed/incompatible, starting fresh\n")
            game_settings.reset()
            game_settings.save()
    else:
        print("No model found, starting fresh\n")
        game_settings.reset()
        game_settings.save()

    dashboard_enabled = _env_enabled("ROBOTRON_DQN_DASHBOARD", True) and MetricsDashboard is not None
    dashboard_host = _resolve_dashboard_host()
    desktop_session = _has_desktop_session()
    if os.getenv("ROBOTRON_DQN_DASHBOARD_BROWSER") is None:
        dashboard_open_browser = desktop_session
    else:
        dashboard_open_browser = _env_enabled("ROBOTRON_DQN_DASHBOARD_BROWSER", desktop_session)
    try:
        dashboard_port = int(os.getenv("ROBOTRON_DQN_DASHBOARD_PORT", "8771"))
    except Exception:
        dashboard_port = 8771
    if dashboard_enabled:
        try:
            dashboard = MetricsDashboard(
                metrics_obj=metrics,
                agent_obj=agent,
                host=dashboard_host,
                port=dashboard_port,
                open_browser=dashboard_open_browser,
            )
            dashboard.start()
            dashboard_url_host = _resolve_dashboard_url_host(dashboard.host)
            dashboard_url = f"http://{dashboard_url_host}:{dashboard.port}"
            dashboard_status = dashboard_url
            if dashboard.host != dashboard_url_host:
                dashboard_status = f"{dashboard_url} (bound {dashboard.host}:{dashboard.port})"
        except Exception as e:
            dashboard = None
            dashboard_status = f"unavailable ({e})"

    print_network_info(agent, dashboard_status=dashboard_status)

    server = SocketServer(SERVER_CONFIG.host, SERVER_CONFIG.port, agent, metrics)
    metrics.global_server = server
    metrics.client_count = 0

    srv_thread = threading.Thread(target=server.start, daemon=True)
    srv_thread.start()

    kb = None
    if IS_INTERACTIVE:
        kb = KeyboardHandler()
        kb.setup_terminal()
        threading.Thread(target=keyboard_handler, args=(agent, kb), daemon=True).start()

    threading.Thread(target=stats_reporter, args=(agent, kb), daemon=True).start()

    last_save = time.time()
    # Peak protection: best-ever EScr1M persists across restarts via a sidecar
    # json, so a fresh process can't overwrite robotron_dqn_best.pt with worse
    # weights just because its in-memory best started at zero.  Keyed on the
    # EVAL score deliberately: eval clients play greedy, injection-free games
    # pinned to wave-1 starts, so the series is immune to curriculum/start-
    # level changes — Scr1M re-baselines whenever the training mix changes and
    # would ratchet on scoreboard inflation instead of policy quality.
    best_meta_path = BEST_MODEL_PATH + ".json"
    best_escr1m = 0.0
    try:
        if os.path.exists(best_meta_path):
            with open(best_meta_path) as f:
                # No fallback to the legacy "best_scr1m" field: it is a
                # different (training-mix) series in different effective units.
                best_escr1m = float(json.load(f).get("best_escr1m", 0.0))
            if best_escr1m > 0.0:
                print(f"Best checkpoint on record: EScr1M {best_escr1m:,.0f} ({BEST_MODEL_PATH})")
    except Exception:
        best_escr1m = 0.0
    # ── policy ratchet (DQN_RATCHET=1 or config.ratchet_enabled) ─────────
    # Monotonic-improvement mode: candidate windows are measured against the
    # incumbent and rolled back unless they win.  Subsumes the watchdog and
    # the rolling-window best-save, so both are suspended while it runs.
    ratchet = None
    if ratchet_on:
        ratchet = RatchetController(agent)
        agent.training_enabled = False   # nothing trains until epoch 0 measures the incumbent
        print("=" * 70)
        print("POLICY RATCHET ACTIVE: train → freeze → measure → keep-or-rollback.")
        print(f"  window {ratchet.base_window:,} steps (floor {ratchet.min_window:,}) | "
              f"cohort {ratchet.cohort_s:.0f}s (all cohort games counted) | "
              f"margin {ratchet.margin:+.1%} + {ratchet.accept_z:.1f}·SE(diff)")
        print("  Epoch 0 measures the loaded checkpoint (eval-only protocol) as the incumbent.")
        print("  Behavior policy = INCUMBENT at all times; candidates act only while measured.")
        print(f"  Data floor: no window trains until the ring holds "
              f"{int(getattr(RL_CONFIG, 'ratchet_min_ring_transitions', 0)):,} incumbent transitions.")
        print("  Watchdog, legacy best-save, and latest.pt autosave suspended while active.")
        print("=" * 70)

    # Collapse watchdog state (see _collapse_signals/_restore_best_checkpoint).
    wd_enabled = bool(getattr(RL_CONFIG, "collapse_watchdog_enabled", True)) and not ratchet_on
    wd_interval = max(10.0, float(getattr(RL_CONFIG, "collapse_check_interval_s", 60.0)))
    wd_need = max(1, int(getattr(RL_CONFIG, "collapse_sustain_checks", 10)))
    wd_cooldown = float(getattr(RL_CONFIG, "collapse_cooldown_s", 21_600.0))
    wd_max = max(1, int(getattr(RL_CONFIG, "collapse_max_restores", 2)))
    wd_next_check = time.time() + wd_interval
    wd_hits = 0
    wd_restores = 0
    wd_cooldown_until = 0.0
    wd_last_steps = -1
    ratchet_tick_errors = 0
    try:
        while srv_thread.is_alive() and not server.shutdown_event.is_set():
            if ratchet is not None:
                try:
                    ratchet.tick()
                    ratchet_tick_errors = 0
                except Exception as e:
                    ratchet_tick_errors += 1
                    print(f"[RATCHET] ERROR in tick ({ratchet_tick_errors}): {e}")
                    traceback.print_exc()
                    if ratchet_tick_errors >= 30:
                        print("[RATCHET] HALTED after repeated tick errors — freezing "
                              "training, serving current weights. Investigate.")
                        agent.training_enabled = False
                        with metrics.lock:
                            metrics.ratchet_frozen = False
                            metrics.ratchet_eval_epoch = -1
                        ratchet = None
            if wd_enabled and time.time() >= wd_next_check:
                wd_next_check = time.time() + wd_interval
                steps_now = int(getattr(metrics, "total_training_steps", 0))
                trainer_active = steps_now != wd_last_steps
                wd_last_steps = steps_now
                if time.time() < wd_cooldown_until or not trainer_active:
                    # Cooling down, or trainer idle (e.g. buffer refilling
                    # after a restore) — a stale last_loss must not count.
                    wd_hits = 0
                elif (wd_reason := _collapse_signals(agent, best_escr1m)) is not None:
                    wd_hits += 1
                    print(f"[COLLAPSE WATCHDOG] signature {wd_hits}/{wd_need} — {wd_reason}")
                    if wd_hits >= wd_need:
                        wd_hits = 0
                        wd_restores += 1
                        print("=" * 70)
                        print(f"[COLLAPSE WATCHDOG] value collapse confirmed — restoring best "
                              f"checkpoint (restore {wd_restores}/{wd_max})")
                        print("=" * 70)
                        _restore_best_checkpoint(agent)
                        wd_cooldown_until = time.time() + wd_cooldown
                        if wd_restores >= wd_max:
                            agent.training_enabled = False
                            wd_enabled = False
                            print("[COLLAPSE WATCHDOG] max restores reached — TRAINING HALTED; "
                                  "serving the frozen best policy. Investigate before re-enabling.")
                else:
                    wd_hits = 0
            if time.time() - last_save >= 300:
                if ratchet is None:
                    agent.save(LATEST_MODEL_PATH, show_status=False)
                last_save = time.time()
                # Save best-by-EScr1M separately. Gate on a ~full eval window
                # (eviction keeps eval_score_1m_frames just UNDER the window,
                # so require 90% — a strict >= would never fire) and a 2%
                # improvement (so a slow climb doesn't churn a 54MB save every
                # cycle).  Suspended under the ratchet: it owns "best" (its
                # measured incumbent on disk); this rolling window would mix
                # candidate generations and ratchet on noise.
                try:
                    if ratchet is None:
                        with metrics.lock:
                            escr1m = float(metrics.eval_score_1m_average)
                            window_full = int(metrics.eval_score_1m_frames) >= int(0.9 * int(metrics.eval_score_1m_window))
                        if window_full and escr1m > best_escr1m * 1.02:
                            agent.save(BEST_MODEL_PATH, show_status=False)
                            best_escr1m = escr1m
                            with open(best_meta_path, "w") as f:
                                json.dump({"best_escr1m": best_escr1m,
                                           "frame_count": int(metrics.frame_count),
                                           "training_steps": int(metrics.total_training_steps)}, f)
                            print(f"New peak EScr1M {escr1m:,.0f} — best checkpoint saved")
                            # Permanent, timestamped copy: best.pt is a moving
                            # target (it is overwritten by the next peak), so a
                            # later regression cannot be undone from it.  This
                            # archive is the actual "never lose the best agent"
                            # guarantee — the project's original goal.
                            try:
                                _arch_dir = os.path.normpath(os.path.join(
                                    os.path.dirname(BEST_MODEL_PATH), "..", "incumbent_archive"))
                                os.makedirs(_arch_dir, exist_ok=True)
                                _stamp = time.strftime("%Y%m%d_%H%M%S")
                                _dst = os.path.join(_arch_dir, f"peak_{_stamp}_escr1m{int(escr1m)}.pt")
                                shutil.copy2(BEST_MODEL_PATH, _dst)
                                print(f"  archived -> {_dst}")
                            except Exception as _e:
                                print(f"  [WARN] peak archive failed: {_e}")
                except Exception as e:
                    print(f"  [WARN] Best-checkpoint save failed: {e}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt, shutting down...")
    finally:
        if ratchet is not None:
            # Monotonicity across restarts: the final latest.pt must hold the
            # last MEASURED winner, never a mid-window candidate.
            with metrics.lock:
                metrics.ratchet_frozen = False
                metrics.ratchet_eval_epoch = -1
            agent.training_enabled = False
            if ratchet.incumbent is not None:
                try:
                    ratchet._quiesce()
                    agent.restore_training_state(ratchet.incumbent)
                    print("[RATCHET] shutdown: incumbent restored for final save")
                except Exception as e:
                    print(f"[RATCHET] WARN: incumbent restore on shutdown failed: {e}")
        agent.save(LATEST_MODEL_PATH, save_replay=True)
        game_settings.save()
        print("Final model & settings saved")
        if IS_INTERACTIVE and kb:
            kb.restore_terminal()
        try:
            server.stop()
        except Exception:
            pass
        try:
            agent.stop()
        except Exception:
            pass
        try:
            srv_thread.join(timeout=2.0)
        except Exception:
            pass
        try:
            if dashboard:
                dashboard.stop()
        except Exception:
            pass
        print("Shutdown complete")


if __name__ == "__main__":
    main()
