"""Explicit restart-only priority phase; no replay migration or leaf-age claim.

Imported only for an explicit phase or a checkpoint carrying phase metadata.
The root's immutable startup record and checkpoint retain observational lineage;
they do not make an ordinary restart a coherent replay/learning anchor.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re

SCHEMA = "robotron-priority-metric-phase-v1"
START_SCHEMA = "robotron-priority-metric-start-v1"
CLOCKS = ("training_steps", "optimized_samples", "learner_frame_count", "frame_count")
DIAGNOSTICS = ("signed_min", "signed_max", "negative_rows", "near_zero_rows",
               "target_min", "target_mass_error_max", "target_mass_error_mean")


def require(value, message):
    if not value:
        raise RuntimeError("Priority phase: " + message)


def file_pin(path):
    path = Path(path)
    before = path.stat()
    require(path.is_file() and not path.is_symlink(), "regular checkpoint required")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    require(all(getattr(before, key) == getattr(after, key) for key in keys), "checkpoint moved")
    return {"path": str(path), "sha256": digest, "bytes": after.st_size}


class PriorityPhase:
    def __init__(self, metric, checkpoint, model_dir):
        require(metric in ("ce", "kl"), "unknown metric")
        require(checkpoint is not None, "held resume-only graph profile required")
        for name in ("DQN_RECOMPUTED_CE_CAPTURE_DIR", "DQN_EXECUTED_CE_TRACE_DIR"):
            require(not os.getenv(name, "").strip(), "capture flags must be absent for this trial")
        path = Path(os.environ.get("DQN_PRIORITY_PHASE_RECORD", ""))
        expected = os.environ.get("DQN_PRIORITY_PHASE_RECORD_SHA256", "")
        require(path.is_absolute() and re.fullmatch(r"[0-9a-f]{64}", expected), "explicit phase record/hash required")
        require(path == path.resolve(strict=True) and not path.is_symlink(), "canonical phase record required")
        info = path.stat()
        require(info.st_uid == os.getuid() and info.st_nlink == 1
                and info.st_mode & 0o777 == 0o444 and 0 < info.st_size <= 65536, "owned immutable small phase record required")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "phase record changed")
        spec = json.loads(raw)
        fields = {"schema", "phase_id", "metric", "action", "previous_metric", "checkpoint",
                  "model_dir", "root_precommit_sha256"}
        require(isinstance(spec, dict) and set(spec) == fields and spec["schema"] == START_SCHEMA, "startup schema")
        require(re.fullmatch(r"[A-Za-z0-9_-]{1,100}", spec["phase_id"] or "")
                and spec["metric"] == metric and spec["action"] in ("start", "resume")
                and spec["previous_metric"] in ("ce", "kl", "unknown")
                and re.fullmatch(r"[0-9a-f]{64}", spec["root_precommit_sha256"] or ""), "startup identity/metric")
        source = spec["checkpoint"]
        require(set(source) == {"path", "sha256", "bytes"}
                and source["path"] == os.path.realpath(checkpoint)
                and spec["model_dir"] == os.path.realpath(model_dir)
                and re.fullmatch(r"[0-9a-f]{64}", source["sha256"] or "")
                and type(source["bytes"]) is int and source["bytes"] > 0, "startup checkpoint/branch")
        self.spec, self.record_sha256 = spec, expected
        self.loaded, self.state = False, None

    def before_load(self, path, checkpoint):
        require(os.path.realpath(path) == self.spec["checkpoint"]["path"]
                and file_pin(path) == self.spec["checkpoint"], "wrong actual newest startup bytes")
        previous = checkpoint.get("priority_metric_phase")
        if previous is not None:
            require(isinstance(previous, dict) and previous.get("schema") == SCHEMA
                    and previous.get("metric") in ("ce", "kl"), "unknown saved phase metadata")
        previous_metric = previous["metric"] if previous is not None else "unknown"
        require(self.spec["previous_metric"] == previous_metric, "predecessor metric differs; untagged tree is unknown")
        if self.spec["action"] == "resume":
            require(previous is not None and previous.get("phase_id") == self.spec["phase_id"]
                    and previous["metric"] == self.spec["metric"] and previous.get("valid") is True
                    and previous.get("root_precommit_sha256") == self.spec["root_precommit_sha256"],
                    "resume must match a valid persisted phase")
            require(all(type(previous.get(key)) is int and previous[key] >= 0
                        for key in ("priority_update_calls", "ring_rows_submitted")), "saved phase counters")
            self.state = dict(previous)
            self.state["last_resume_record_sha256"] = self.record_sha256
        else:
            require(previous is None or previous.get("phase_id") != self.spec["phase_id"], "new phase ID required")
            clocks = {key: checkpoint[key] for key in CLOCKS}
            require(all(type(value) is int and value > 0 for value in clocks.values()), "positive saved clocks required")
            self.state = dict(schema=SCHEMA, phase_id=self.spec["phase_id"], metric=self.spec["metric"],
                root_precommit_sha256=self.spec["root_precommit_sha256"], phase_record_sha256=self.record_sha256,
                last_resume_record_sha256=None,
                started_from=dict(self.spec["checkpoint"], clocks=clocks),
                predecessor=None if previous is None else {key: previous.get(key) for key in ("phase_id", "metric", "valid")},
                initial_tree="mixed/unknown historical leaves, insertion hints and boosts; no per-leaf metric or generation tag",
                priority_update_calls=0, ring_rows_submitted=0, last_diagnostics=None,
                last_rejected_diagnostics=None, valid=True, invalid_reason=None)

    def finish_load(self, path):
        require(file_pin(path) == self.spec["checkpoint"], "startup checkpoint changed during restore")
        self.loaded = True

    def require_ready(self, metric):
        require(self.loaded and self.state is not None and self.state.get("valid") is True
                and metric == self.spec["metric"], "restart/rebuild/load agreement required")

    def note_update(self, metric, ring_rows, diagnostics):
        self.require_ready(metric)
        require(type(ring_rows) is int and ring_rows >= 0, "invalid submitted ring-row count")
        if metric == "kl":
            require(len(diagnostics) == len(DIAGNOSTICS)
                    and all(math.isfinite(float(value)) for value in diagnostics), "invalid signed/mass diagnostics")
            self.state["last_diagnostics"] = dict(zip(DIAGNOSTICS, map(float, diagnostics)))
        self.state["priority_update_calls"] += 1
        self.state["ring_rows_submitted"] += ring_rows

    def invalidate(self, error):
        if self.state is not None:
            self.state["valid"] = False
            self.state["invalid_reason"] = str(error)[:1024]

    def reject_diagnostics(self, values):
        # Failure-only CPU readback, never fabricate finite values for NaN/Inf.
        if self.state is not None:
            self.state["last_rejected_diagnostics"] = {
                key: float(value) if math.isfinite(float(value)) else str(float(value))
                for key, value in zip(DIAGNOSTICS, values)}

    def snapshot(self):
        require(self.loaded and self.state is not None, "cannot save an un-restored phase")
        return dict(self.state)


def require_checkpoint_phase(checkpoint, metric, phase):
    if phase is None:
        require(metric == "ce" and checkpoint.get("priority_metric_phase") is None,
                "saved tagged phase requires an explicit restart record, including return-to-CE")
