"""Frozen whole-game comparison controller, separate from policy ratcheting.

The owner calls enter(), tick() until status()['complete'], persists the result,
then exit(). A timeout invalidates the whole leg; pending games never disappear
from its denominator. This module does not import Torch or the live config.
"""

import math
import os
import time


def _continuous_training_mode_enabled():
    raw = os.getenv("ROBOTRON_CONTINUOUS_TRAINING_MODE", "0")
    if raw not in ("0", "1"):
        raise ValueError("Explicit continuous training mode0/1 required")
    return raw == "1"


class ManagedMeasurement:
    def __init__(self, agent, metrics, journal, *, boundary_status, clock=time.time):
        if not callable(boundary_status):
            raise ValueError("A client/replay boundary readiness callback is required")
        if not callable(getattr(journal, "cohort_status", None)):
            raise ValueError("Whole-game journal cohort_status support is required")
        self.agent, self.metrics, self.journal = agent, metrics, journal
        self.boundary_status, self.clock = boundary_status, clock
        self.phase = "idle"
        self._prior = None
        self._owns_mode = False
        self._installed = False
        self._terminal = False
        self._valid = None
        self._reason = None
        self._cohort = {}
        self._boundary = {}
        self._candidate = None
        self._replay_guard = None
        self._clocks = None
        self.label = None
        self.generation = None
        self.start_ts = self.close_ts = None

    def _clock_values(self):
        return {
            "training_steps": int(self.agent.training_steps),
            "optimized_samples": int(self.agent.optimized_samples),
            "total_training_steps": int(getattr(self.metrics, "total_training_steps", 0)),
            "total_optimized_samples": int(getattr(self.metrics, "total_optimized_samples", 0)),
            "learner_frame_count": int(getattr(self.metrics, "learner_frame_count", 0)),
        }

    def _replay_values(self):
        memory = getattr(self.agent, "memory", None)
        if memory is None:
            return {}
        values = {name: int(getattr(memory, name, 0))
                  for name in ("_adds_total", "size", "hof_total", "ephof_total")}
        values["data_ptr"] = int(getattr(getattr(memory, "tree", None), "data_ptr", 0))
        return values

    def enter(self, label, checkpoint_path=None, cohort_s=120, timeout_s=600):
        if (_continuous_training_mode_enabled()
                or bool(getattr(self.metrics, "continuous_training_mode", False))):
            raise RuntimeError("Main managed measurement entry is disabled in continuous training mode")
        if self._prior is not None:
            raise RuntimeError("Exit the active measurement before entering another")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("A unique nonempty measurement label is required")
        if (not math.isfinite(cohort_s) or not math.isfinite(timeout_s)
                or cohort_s <= 0 or timeout_s <= cohort_s):
            raise ValueError("Timeout must exceed the positive cohort start window")
        if bool(getattr(self.metrics, "measurement_active", False)):
            raise RuntimeError("A measurement is already active")
        if bool(getattr(self.metrics, "ratchet_frozen", False)):
            raise RuntimeError("Managed measurement cannot overlap ratchet measurement")
        # Check preserved checkpoint compatibility before changing live flags.
        prepared = self.agent.prepare_inference_checkpoint(checkpoint_path) if checkpoint_path else None
        self.label, self.checkpoint_path = label, str(checkpoint_path) if checkpoint_path else None
        self.cohort_s, self.timeout_s = float(cohort_s), float(timeout_s)
        self._entered_ts = self.clock()
        self._terminal, self._valid, self._reason = False, None, None
        self._cohort, self._boundary = {}, {}
        self.start_ts = self.close_ts = None
        self._clocks, self._replay_guard = None, None
        self._candidate, self._installed = None, False
        self._prior = dict(
            training_enabled=bool(self.agent.training_enabled),
            metrics_training_enabled=bool(self.metrics.training_enabled),
            behavior_locked=bool(self.agent.behavior_locked),
            prefetch_paused=bool(getattr(self.agent, "_prefetch_paused", False)),
            measurement_label=getattr(self.metrics, "measurement_label", ""),
        )
        self.agent.training_enabled = False
        with self.metrics.lock:
            self.metrics.training_enabled = False
        acquired = False
        try:
            # A real lock is the quiescence barrier; counters appearing stable
            # for a few hundred milliseconds do not prove an update is idle.
            acquired = self.agent._training_lock.acquire(timeout=10.0)
            if not acquired:
                raise TimeoutError("Learner did not release its training lock")
            self.agent.behavior_locked = True
            self.agent._pause_prefetch()
            self._candidate = self.agent.capture_inference_policy()
            with self.metrics.lock:
                self.metrics.measurement_generation = int(getattr(self.metrics, "measurement_generation", 0)) + 1
                self.generation = self.metrics.measurement_generation
                self.metrics.measurement_label = label
                self.metrics.measurement_active = True
            self._owns_mode = True
            # A failed device copy can be partial, so rollback must restore the
            # candidate even if install raises before returning.
            self._installed = True
            self.agent.install_inference_policy(prepared if prepared is not None else self._candidate)
            self._clocks = self._clock_values()
            self.phase = "warming"
        except Exception:
            try:
                if not acquired:
                    # No actor/prefetch operation began. Do not block forever
                    # trying to reacquire the lock that just timed out.
                    with self.metrics.lock:
                        self.metrics.training_enabled = self._prior["metrics_training_enabled"]
                    self.agent.training_enabled = self._prior["training_enabled"]
                    self._prior = None
                else:
                    self._restore()
            except Exception as cleanup_error:
                self.phase = "restore_failed"
                raise RuntimeError("Measurement entry failed and safe restoration failed; training remains paused") from cleanup_error
            raise
        finally:
            if acquired:
                self.agent._training_lock.release()
        return self.status()

    def _finish(self, valid, reason=None):
        self._terminal, self._valid, self._reason = True, bool(valid), reason
        self.phase = "complete"

    def tick(self):
        if self._prior is None or self._terminal:
            return self.status()
        current_clocks = self._clock_values()
        checked_names = (set(self._clocks) - {"learner_frame_count"}
                         if self.phase == "warming" else set(self._clocks))
        if any(current_clocks[name] != self._clocks[name] for name in checked_names):
            self._finish(False, "training_or_learner_clock_moved")
            return self.status()
        if self.clock() - self._entered_ts >= self.timeout_s:
            self._finish(False, "whole_cohort_timeout")
            return self.status()
        if self.phase == "warming":
            self._boundary = self.boundary_status(self.generation)
            if not self._boundary.get("ready", False):
                return self.status()
            if int(self._boundary.get("generation", -1)) != self.generation:
                self._finish(False, "boundary_generation_mismatch")
                return self.status()
            # Account for a pre-publication actor request that completed its
            # normal-action bookkeeping while the entry barrier was draining.
            # No counter is reset; from readiness onward this clock is frozen.
            self._clocks["learner_frame_count"] = current_clocks["learner_frame_count"]
            self._replay_guard = self._replay_values()
            self.start_ts = self.clock()
            self.close_ts = self.start_ts + self.cohort_s
            self.phase = "collecting"
        if self._replay_values() != self._replay_guard:
            self._finish(False, "replay_changed_after_boundary")
            return self.status()
        self._cohort = self.journal.cohort_status(self.label, self.start_ts, self.close_ts)
        if self._cohort.get("abandoned", 0):
            self._finish(False, "abandoned_cohort_game")
        elif self._cohort.get("complete", False):
            expected = set(self._boundary.get("actor_slots", []))
            observed = set(self._cohort.get("started_actor_slots", []))
            if expected and not expected.issubset(observed):
                self._finish(False, "insufficient_actor_coverage")
            else:
                self._finish(True)
        elif self.clock() >= self.close_ts:
            self.phase = "draining"
        return self.status()

    def status(self):
        result = dict(
            active=self._owns_mode, phase=self.phase, complete=self._terminal,
            valid=self._valid, reason=self._reason, label=self.label,
            generation=self.generation, start_ts=self.start_ts, close_ts=self.close_ts,
            checkpoint_path=getattr(self, "checkpoint_path", None),
            clocks=self._clocks, boundary=self._boundary, cohort=self._cohort,
        )
        for name in ("started", "pending", "abandoned", "count", "mean", "median", "sd", "se", "rows"):
            if name in self._cohort:
                result[name] = self._cohort[name]
        return result

    def _restore(self):
        if self._prior is None:
            return
        self.agent.training_enabled = False
        with self.metrics.lock:
            self.metrics.training_enabled = False
        with self.agent._training_lock:
            self.agent.behavior_locked = True
            if self._installed:
                # Restore CURRENT online actor values, never an optimizer or
                # training-state snapshot. Clock/reset changes are forbidden.
                current = self.agent.capture_inference_policy()
                self.agent.install_inference_policy(current)
            if not self._prior["prefetch_paused"]:
                self.agent._resume_prefetch()
            else:
                self.agent._prefetch_paused = True
            with self.metrics.lock:
                if self._owns_mode:
                    self.metrics.measurement_active = False
                    self.metrics.measurement_generation += 1
                    self.metrics.measurement_label = self._prior["measurement_label"]
                self.metrics.training_enabled = self._prior["metrics_training_enabled"]
            self.agent.behavior_locked = self._prior["behavior_locked"]
            self.agent.training_enabled = self._prior["training_enabled"]
        self._prior = None
        self._candidate = None
        self._owns_mode = False
        self._installed = False

    def exit(self):
        if self._prior is None:
            return self.status()
        if not self._terminal:
            self._finish(False, "controller_exit_before_cohort_complete")
        try:
            self._restore()
        except Exception:
            self.phase = "restore_failed"
            self._valid = False
            self._reason = "safe_restoration_failed_training_paused"
            raise
        self.phase = "finished"
        return self.status()
