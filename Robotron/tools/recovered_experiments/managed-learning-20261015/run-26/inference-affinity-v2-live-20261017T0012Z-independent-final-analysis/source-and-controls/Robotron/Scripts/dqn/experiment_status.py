"""Bounded, read-only campaign summaries for the training dashboard.

This reader reports evaluator receipts; it never launches experiments, selects a
policy, or touches learner state. Only compact, explicitly selected fields leave
this module. In particular receipts' per-game rows and process details stay local.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import threading
import time


_STATUS_LIMIT = 1024 * 1024
# Real plans include a boot-asset inventory (~270 KiB), even with just four legs.
_PLAN_LIMIT = 512 * 1024
_RECEIPT_LIMIT = 8 * 1024 * 1024
_MAX_LEGS = 4


def _number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return value if math.isfinite(value) else None
        except OverflowError:
            return None
    return None


def _text(value, limit=160):
    if not isinstance(value, str):
        return None
    # Labels and terminal reasons are useful, but host paths are not UI data.
    value = re.sub(r"(?<!\w)/(?:[^\s,;]+)", "[path]", value)
    return " ".join(value.split())[:limit]


def _mapping(value):
    return value if isinstance(value, dict) else {}


class ExperimentStatusReader:
    """Read at most four declared evaluator files, no directory scans or writes."""

    def __init__(self, game_root=None, state_path=None, *, cache_seconds=2.0,
                 clock=time.time, monotonic=time.monotonic):
        self.game_root = Path(game_root or Path(__file__).resolve().parents[2]).resolve()
        self.logs_root = (self.game_root / "logs").resolve()
        self.state_path = self._under(
            state_path or self.logs_root / "managed-learning-20261015/state.json",
            self.logs_root, self.game_root)
        self.cache_seconds = max(2.0, float(cache_seconds))
        self._clock = clock
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._cached = None
        self._last_good = None
        self._read_at = float("-inf")

    def _under(self, value, boundary, relative_to):
        if not isinstance(value, (str, Path)) or not str(value):
            raise ValueError("Missing experiment path")
        path = Path(value)
        if ".." in path.parts:
            raise ValueError("Experiment path traversal")
        if not path.is_absolute():
            # Managed state historically records repository-relative Robotron/logs.
            base = (self.game_root.parent if path.parts[0] == self.game_root.name
                    else relative_to)
            path = base / path
        path = path.resolve()
        if not path.is_relative_to(boundary) or path == boundary:
            raise ValueError("Experiment path outside allowed directory")
        return path

    @staticmethod
    def _read(path, limit):
        # Bounded read, including protection against growth between stat and read.
        if path.stat().st_size > limit:
            raise ValueError("Experiment document exceeds size limit")
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("Experiment document exceeds size limit")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Experiment document is not an object")
        return result

    def snapshot(self):
        with self._lock:
            now = self._monotonic()
            if self._cached is None or now - self._read_at >= self.cache_seconds:
                try:
                    result = self._load()
                    self._last_good = deepcopy(result)
                except (OSError, ValueError, TypeError, RecursionError):
                    result = deepcopy(self._last_good) if self._last_good else {
                        "available": False, "state": "unavailable", "legs": [],
                        "current_leg": None, "total_legs": 0,
                        "updated_unix_s": None, "comparison": None,
                        "outcome": None, "reason": None,
                    }
                    result["read_error"] = "Experiment status could not be read safely"
                self._cached = result
                self._read_at = now
            result = deepcopy(self._cached)
        updated = result.get("updated_unix_s")
        result["age_s"] = max(0.0, self._clock() - updated) if updated else None
        result["stale"] = bool(result.get("read_error") or (
            result.get("state") == "running" and
            (result["age_s"] is None or result["age_s"] > 30)))
        return result

    def _load(self):
        state = self._read(self.state_path, _STATUS_LIMIT)
        active = _mapping(state.get("active_quality_job"))
        if not active:
            return {"available": False, "state": "unavailable", "legs": [],
                    "current_leg": None, "total_legs": 0, "updated_unix_s": None,
                    "comparison": None, "outcome": None, "reason": None}
        campaign = self._under(active.get("directory"), self.logs_root, self.game_root)
        status_path = self._under(campaign / "status.json", campaign, campaign)
        status = self._read(status_path, _STATUS_LIMIT)
        plan_path = self._under(campaign / "plan.json", campaign, campaign)
        try:
            plan = self._read(plan_path, _PLAN_LIMIT)
        except FileNotFoundError:
            plan = {}
        declared = plan.get("legs", [])
        live = status.get("legs", [])
        if not isinstance(declared, list) or not isinstance(live, list):
            raise ValueError("Malformed experiment legs")
        # Ignore any extra entries rather than walking an unbounded input list.
        specs = {entry.get("index"): entry for entry in declared[:_MAX_LEGS]
                 if isinstance(entry, dict)}
        live_specs = {entry.get("index"): entry for entry in live[:_MAX_LEGS]
                      if isinstance(entry, dict)}
        indices = list(dict.fromkeys([*specs, *live_specs]))[:_MAX_LEGS]
        updated = _number(status.get("updated_unix_s")) or status_path.stat().st_mtime
        legs = []
        for index in indices:
            spec = specs.get(index, {})
            progress = live_specs.get(index, {})
            job = _mapping(spec.get("job"))
            leg_state = _text(progress.get("state")) or "pending"
            data = {}
            path_value = None
            if leg_state == "finished":
                path_value = progress.get("receipt_path") or spec.get("receipt_path")
                limit = _RECEIPT_LIMIT
            elif leg_state != "pending":
                path_value = (progress.get("evaluator_status_path") or
                              spec.get("evaluator_status_path"))
                limit = _STATUS_LIMIT
            if path_value:
                path = self._under(path_value, campaign, campaign)
                try:
                    data = self._read(path, limit)
                    if index == status.get("current_leg") and leg_state == "running":
                        updated = min(updated, path.stat().st_mtime)
                except FileNotFoundError:
                    # The runner publishes its PID before the evaluator is ready.
                    previous = next((leg for leg in (self._last_good or {}).get("legs", [])
                                     if leg["index"] == index), {})
                    started = _number(progress.get("started_unix_s"))
                    if (leg_state == "finished" or previous.get("count") is not None or
                            (started is not None and self._clock() - started > 30)):
                        raise
            cohort = _mapping(data.get("cohort"))
            leg = {"index": _number(index),
                   "role": _text(progress.get("role") or spec.get("role")),
                   "label": _text(data.get("label") or job.get("label")),
                   "state": leg_state, "phase": _text(data.get("phase")) or leg_state}
            for key in ("count", "started", "pending", "mean", "median", "se"):
                leg[key] = _number(data.get(key, cohort.get(key)))
            for key in ("valid", "complete"):
                value = data.get(key)
                leg[key] = value if isinstance(value, bool) else None
            leg["admission_start_unix_s"] = _number(data.get("start_ts", cohort.get("start_ts")))
            leg["admission_close_unix_s"] = _number(data.get("close_ts", cohort.get("close_ts")))
            leg["reason"] = _text(data.get("reason"))
            legs.append(leg)
        return {"available": True, "state": _text(status.get("state")) or "unknown",
                "current_leg": _number(status.get("current_leg")),
                "total_legs": len(indices), "updated_unix_s": updated,
                "comparison": self._comparison(plan, active, legs), "legs": legs,
                "outcome": _text(status.get("outcome")),
                "reason": _text(status.get("reason"))}

    @staticmethod
    def _comparison(plan, active, legs):
        checkpoints = _mapping(plan.get("checkpoints"))
        labels = []
        for role in ("reference", "candidate"):
            checkpoint = _mapping(checkpoints.get(role))
            source = checkpoint.get("source") or active.get(role + "_checkpoint")
            label = next((leg.get("label") for leg in legs if leg["role"] == role), None)
            raw = str(source or label or role)
            milestone = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)M\b", raw, re.IGNORECASE)
            labels.append(milestone.group(1) + "M" if milestone else
                          _text(label or Path(raw).stem))
        return " vs ".join(labels)
