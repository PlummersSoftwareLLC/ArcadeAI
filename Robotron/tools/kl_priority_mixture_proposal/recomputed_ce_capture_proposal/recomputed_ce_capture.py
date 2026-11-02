"""Startup-opt-in input/PRE-state/actual-CE observer; no loss-kernel overlay.

Only enabled startup imports this module. Offline targets/KL are RECOMPUTED;
agreement with actual CE cannot bound an unobserved executed entropy or rank.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import random
import threading
import time

ATTEMPTS = 8
BATCH_ROWS = 4096
STATE_WIDTH = 11128
ATOMS = 51
MAX_RAW_BYTES = 640 * 1024**2
MAX_DISK_BYTES = 6 * 1024**3
MAX_JSON_BYTES = 1024**2
MAX_STATUSES = 128
LOSS_SHA256 = "de9621e3d926a8f49f230f9e271c645a7498d38445622d6ae2761ab2bbd7253a"
INPUT_NAMES = ("states", "actions", "rewards", "next_states", "dones",
               "horizons", "is_expert", "weights")


def error_text(error):
    try:
        return (type(error).__name__ + ": " + str(error))[:500]
    except Exception:
        return type(error).__name__


class ObservedReplayBatch(tuple):
    def __new__(cls, batch, metadata):
        value = super().__new__(cls, batch)
        value.draw_metadata = metadata
        return value


class _BudgetedFile:
    """Torch's streaming serializer may not exceed remaining artifact bytes."""
    def __init__(self, stream, remaining):
        self.stream, self.remaining, self.written = stream, remaining, 0

    def write(self, data):
        if self.written + len(data) > self.remaining:
            raise OSError("Capture6GiB artifact budget exceeded")
        count = self.stream.write(data)
        if count != len(data):
            raise OSError("Short capture artifact write")
        self.written += count
        return count

    def flush(self):
        return self.stream.flush()


class RecomputedCECapture:
    def __init__(self, directory, cfg, *, optimizer_exposure, runtime):
        if int(cfg.batch_size) != BATCH_ROWS or int(cfg.num_atoms) != ATOMS:
            raise ValueError("Capture requires4096 rows/51 atoms")
        if optimizer_exposure is None:
            raise ValueError("Actual optimizer exposure required")
        if not bool(cfg.use_torch_compile) or not bool(getattr(cfg, "compile_full_loss", True)):
            raise ValueError("Capture requires unchanged original compiled4 loss route")
        if not 1 <= int(getattr(cfg, "replay_prefetch_slots", 3)) <= 3:
            raise ValueError("Only existing1..3 producer slots supported")
        if os.getenv("DQN_EXECUTED_CE_TRACE_DIR", "").strip():
            raise ValueError("Old executed-target trace cannot run with recomputed capture")
        if str(getattr(cfg, "per_priority_metric", "ce")) != "ce" or os.getenv("DQN_PER_PRIORITY_METRIC", "ce") != "ce":
            raise ValueError("Unchanged CE recipe required")
        self.directory = Path(directory)
        if not self.directory.is_absolute() or not self.directory.name.startswith("ce-recomputed-capture-"):
            raise ValueError("Explicit absolute NEW ce-recomputed-capture-* directory required")
        self.directory.mkdir()
        self.lock = threading.RLock()
        self.cfg, self.exposure = cfg, optimizer_exposure
        self.capture_id = "recomputed-inputs-" + str(time.monotonic_ns())
        self.rows, self.errors = [], []
        self.current = self.raw = None
        self.consumed = self.disk_bytes = self.status_count = 0
        self.reporting_failed = self.invalid = False
        self.context = dict(schema="robotron-recomputed-ce-capture-v1", capture_id=self.capture_id,
            attempts=ATTEMPTS, runtime=dict(runtime), config=self._config(),
            boundary="first8 consumed eligible train_step attempts, before transfer",
            loss_sha256=LOSS_SHA256, loss_abi=4, optimizer_recipe_change=False,
            offline_target_scope="RECOMPUTED/conditional; not the executed target",
            unknown=dict(checkpoint_identity="external immutable run binding required",
                source_bundle="external reviewed manifest required",
                learning_anchor="not established", actual_executed_target_entropy="unobserved",
                actual_executed_KL_and_rank="unobserved; CE agreement is not a bound"))
        self._json("context.json", self.context)
        self._publish()

    def _config(self):
        return {name: value for name, value in vars(self.cfg).items()
                if value is None or type(value) in (bool, int, float, str)}

    def _fsync_directory(self):
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _json(self, name, value):
        data = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
        if len(data) > MAX_JSON_BYTES or self.disk_bytes + len(data) > MAX_DISK_BYTES:
            raise OSError("Capture JSON/artifact budget exceeded")
        path = self.directory / name
        try:
            with path.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if path.exists():
                self.disk_bytes += path.stat().st_size
        self._fsync_directory()
        path.chmod(0o444)

    def _publish(self):
        if self.status_count >= MAX_STATUSES:
            self.reporting_failed = True
            return
        self.status_count += 1
        self._json("status-%03d.json" % self.status_count,
            dict(schema=self.context["schema"], capture_id=self.capture_id,
                 attempts_consumed=self.consumed,
                 complete=bool(self.consumed == len(self.rows) == ATTEMPTS and not self.invalid
                               and all(row.get("capture_complete") for row in self.rows)),
                 observer_errors=list(self.errors), reporting_failed=self.reporting_failed,
                 rows=[{k: v for k, v in row.items() if k != "draw"} for row in self.rows],
                 cumulative_disk_bytes=self.disk_bytes))

    def invalidate(self, where, error):
        """Observer reporting must never enter the learner error/fallback path."""
        self.invalid = True
        try:
            with self.lock:
                message = str(where)[:80] + ": " + error_text(error)
                if len(self.errors) < 64:
                    self.errors.append(message)
                if self.current is not None and self.current.get("thread_id") == threading.get_ident():
                    if len(self.current["observer_errors"]) < 16:
                        self.current["observer_errors"].append(message)
                try:
                    self._publish()
                except Exception:
                    self.reporting_failed = True
            try:
                print("[RECOMPUTED CE CAPTURE INVALID] " + message, flush=True)
            except Exception:
                pass
        except Exception:
            self.reporting_failed = True

    def want_draw(self):
        try:
            with self.lock:
                return self.consumed < ATTEMPTS
        except Exception as error:
            self.invalidate("draw_enable", error)
            return False

    def sample(self, memory, batch_size, beta, state_out=None):
        if not self.want_draw():
            return memory.sample(batch_size, beta=beta, _state_out=state_out)
        try:
            batch, metadata = memory.sample_with_metadata(batch_size, beta=beta,
                capture_id=self.capture_id, _state_out=state_out)
        except BaseException as error:
            self.invalidate("actual_sampler_exception_before_consumption", error)
            raise
        if batch is None:
            return None
        try:
            if metadata is not None and metadata.get("observer_error"):
                self.invalidate("draw_metadata", RuntimeError(metadata["observer_error"]))
            return ObservedReplayBatch(batch, metadata)
        except Exception as error:
            self.invalidate("attach_metadata", error)
            return batch

    @staticmethod
    def _clocks(agent):
        return dict(training_steps=int(agent.training_steps), optimized_samples=int(agent.optimized_samples),
            last_target_update_samples=int(getattr(agent, "last_target_update_samples", 0)),
            last_inference_sync=int(getattr(agent, "last_inference_sync", 0)),
            learning_rates=[float(group["lr"]) for group in agent.optimizer.param_groups])

    def begin(self, agent, batch, staged, metrics_context=None):
        with self.lock:
            if self.consumed >= ATTEMPTS:
                return
            if self.current is not None or self.raw is not None:
                raise RuntimeError("Prior raw capture was not drained")
            self.consumed += 1
            row = dict(index=self.consumed, status="entered", capture_complete=False,
                observer_errors=[], thread_id=threading.get_ident())
            self.rows.append(row)
            self.current = row
            row.update(before=self._clocks(agent), exposure_before=self.exposure.snapshot(),
                       consumed_monotonic_ns=time.monotonic_ns())
            if metrics_context is not None:
                with metrics_context.lock:
                    row["frame_context"] = {name: int(getattr(metrics_context, name, 0)) for name in
                        ("frame_count", "learner_frame_count", "measurement_frame_count")}
            metadata = getattr(staged, "draw_metadata", None) if staged is not None else getattr(batch, "draw_metadata", None)
            row["draw"] = metadata
            if staged is not None:
                row["prefetch"] = dict(lease_epoch=staged._epoch, owner_epoch_at_consumption=staged._owner._epoch,
                    current=bool(staged.is_current), sample_ms=float(staged.sample_ms), stage_host_ms=float(staged.stage_host_ms))
                if not staged.is_current:
                    raise RuntimeError("Stale consumed lease")
            else:
                row["prefetch"] = None
            self._json("attempt-%02d.entered.json" % row["index"],
                {key: value for key, value in row.items() if key != "draw"})
            if metadata is None or metadata.get("observer_error"):
                raise RuntimeError("Missing/failed draw-time metadata")

    def unsupported_backend(self, reason):
        if self.current is not None:
            raise RuntimeError(reason)

    def _owned_copy(self, torch, tensor):
        needed = tensor.numel() * tensor.element_size()
        if self.raw["tensor_bytes"] + needed > MAX_RAW_BYTES:
            raise MemoryError("One640MiB current raw snapshot budget exceeded before copy")
        copy = tensor.detach().to(device="cpu", copy=True)
        self.raw["tensor_bytes"] += needed
        if not bool(torch.isfinite(copy).all()):
            # Retain the actual bad value before rejecting interpretation.
            self.raw["nonfinite_copies"] += 1
        return copy

    def pre_loss(self, agent, tensors, *, schedule, kernel, diagnostic_due, use_amp):
        with self.lock:
            row = self.current
            if row is None or self.invalid:
                return
            import numpy as np
            import torch
            started = time.monotonic_ns()
            if len(tensors) != 8 or tensors[0].shape != (BATCH_ROWS, STATE_WIDTH) or tensors[3].shape != tensors[0].shape:
                raise ValueError("Exact consumed input geometry unavailable")
            expected = (torch.float32, torch.long, torch.float32, torch.float32,
                        torch.float32, torch.float32, torch.bool, torch.float32)
            if tuple(t.dtype for t in tensors) != expected or any(t.shape != (BATCH_ROWS,) for t in tensors[1:3] + tensors[4:]):
                raise ValueError("Actual staged input dtype/shape differs")
            if agent.device.type == "cuda":
                torch.cuda.synchronize(agent.device)
            module = getattr(kernel, "_orig_mod", kernel)
            path = Path(inspect.getfile(type(module)))
            source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if source_sha != LOSS_SHA256:
                raise ValueError("Actual compiled loss source is not unchanged original")
            constants = {name: getattr(module, name) for name in
                ("num_fire", "num_atoms", "v_min", "v_max", "delta_z", "gamma", "smooth_eps",
                 "branch_aux", "bc_floor", "q_temperature", "q_margin", "diagnostics")}
            if bool(constants["diagnostics"]) != bool(diagnostic_due):
                raise ValueError("Caller-selected compiled diagnostic variant differs")
            self.raw = dict(tensor_bytes=0, nonfinite_copies=0, inputs={}, online={}, target={},
                capture_id=self.capture_id, attempt=row["index"],
                pre_context=dict(clocks=self._clocks(agent), config=self._config(),
                    kernel_constants=constants, loss_source=str(path), loss_sha256=source_sha,
                    use_amp=bool(use_amp), modes=dict(online=agent.online_net.training, target=agent.target_net.training),
                    matmul_precision=torch.get_float32_matmul_precision(),
                    tf32_matmul=bool(torch.backends.cuda.matmul.allow_tf32),
                    tf32_cudnn=bool(torch.backends.cudnn.allow_tf32), cudnn_benchmark=bool(torch.backends.cudnn.benchmark)))
            for name, value in zip(INPUT_NAMES, tensors):
                self.raw["inputs"][name] = self._owned_copy(torch, value)
            for name, net in (("online", agent.online_net), ("target", agent.target_net)):
                for key, value in net.state_dict().items():
                    if value.is_floating_point() and value.dtype != torch.float32:
                        raise ValueError("PRE model state must retain original FP32 dtype")
                    self.raw[name][key] = self._owned_copy(torch, value)
            if tuple(schedule.shape) != (3,) or schedule.dtype != torch.float32:
                raise ValueError("Actual schedule tensor geometry differs")
            self.raw["schedule"] = self._owned_copy(torch, schedule)
            numpy_state = np.random.get_state()
            self.raw["rng"] = dict(python=random.getstate(),
                numpy=(numpy_state[0], self._owned_copy(torch, torch.from_numpy(numpy_state[1].astype(np.int64))), *numpy_state[2:]),
                cpu=self._owned_copy(torch, torch.get_rng_state()), cuda=None)
            if agent.device.type == "cuda":
                self.raw["rng"]["cuda"] = self._owned_copy(torch, torch.cuda.get_rng_state(agent.device))
            row["pre_snapshot_ns"] = time.monotonic_ns() - started
            row["pre_snapshot_tensor_bytes"] = self.raw["tensor_bytes"]
            row["backend"] = "original_compiled4_diagnostics" if diagnostic_due else "original_compiled4"
            if self.raw["nonfinite_copies"]:
                raise ValueError("Nonfinite PRE copies retained; capture invalid")

    def loss(self, agent, ce, *, weighted_loss, bc_loss, diagnostic_values):
        with self.lock:
            if self.current is None or self.raw is None or self.invalid:
                return
            import torch
            if ce.shape != (BATCH_ROWS,) or weighted_loss.shape != () or bc_loss.shape != () or diagnostic_values is None or diagnostic_values.shape != (12,):
                raise ValueError("Original four-output geometry differs")
            self.raw["actual"] = {name: self._owned_copy(torch, value) for name, value in
                (("ce", ce), ("weighted_loss", weighted_loss), ("bc_loss", bc_loss), ("diagnostic_values", diagnostic_values))}
            self.current["at_loss"] = self._clocks(agent)
            if self.raw["nonfinite_copies"]:
                raise ValueError("Nonfinite actual loss copies retained; capture invalid")

    def outcome(self, mode, found_inf, ticket):
        with self.lock:
            if self.current is None:
                return
            self.current["optimizer_observation"] = dict(mode=str(mode),
                found_inf=None if found_inf is None else float(found_inf),
                ticket_epoch=None if ticket is None else ticket.epoch,
                ticket_finished=bool(ticket is not None and ticket.finished),
                ticket_owner_matches=bool(ticket is not None and ticket.owner is self.exposure))
            self.current["exposure_after_outcome"] = self.exposure.snapshot()

    def _tensorize_draw(self, torch, value):
        import numpy as np
        if isinstance(value, np.ndarray):
            return self._owned_copy(torch, torch.from_numpy(value))
        if isinstance(value, dict):
            return {key: self._tensorize_draw(torch, part) for key, part in value.items()}
        if isinstance(value, (tuple, list)):
            return type(value)(self._tensorize_draw(torch, part) for part in value)
        if isinstance(value, np.generic):
            return value.item()
        if value is None or type(value) in (bool, str, int, float):
            return value
        raise TypeError("Unsupported draw observation type")

    def _persist_raw(self, row):
        if self.raw is None:
            return
        import torch
        self.raw["draw"] = self._tensorize_draw(torch, row.get("draw"))
        self.raw["outcome"] = {key: value for key, value in row.items() if key != "draw"}
        path = self.directory / ("attempt-%02d.payload.pt" % row["index"])
        try:
            with path.open("xb") as stream:
                bounded = _BudgetedFile(stream, MAX_DISK_BYTES - self.disk_bytes)
                torch.save(self.raw, bounded)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if path.exists():
                self.disk_bytes += path.stat().st_size
        self._fsync_directory()
        path.chmod(0o444)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(1024**2):
                digest.update(block)
        row["payload"] = dict(path=str(path), sha256=digest.hexdigest(), bytes=path.stat().st_size,
                              tensor_bytes=self.raw["tensor_bytes"])

    def end(self, agent, *, result=None, exception=None):
        with self.lock:
            row = self.current
            if row is None:
                return
            started = time.monotonic_ns()
            try:
                row["after"] = self._clocks(agent)
                row["exposure_at_exit"] = after = self.exposure.snapshot()
                before = row["exposure_before"]
                row["exception"] = None if exception is None else error_text(exception)
                row["result"] = None if result is None else float(result)
                row["status"] = "learner_exception" if exception is not None else "returned_none" if result is None else "returned_loss"
                delta = {key: after["total"][key] - before["total"][key] for key in
                         ("attempts_started", "outcomes_recorded", "applied", "amp_skipped", "unavailable")}
                row["actual_exposure_delta"] = delta
                observed = row.get("optimizer_observation", {})
                row["outcome_available"] = bool(after["available"] and all(before[key] == after[key] for key in
                    ("process_id", "instance_monotonic_ns", "epoch")) and delta["attempts_started"] == delta["outcomes_recorded"] == 1
                    and delta["unavailable"] == 0 and delta["applied"] + delta["amp_skipped"] == 1
                    and observed.get("ticket_finished") and observed.get("ticket_owner_matches"))
                row["optimizer_outcome"] = ("amp_skipped" if delta["amp_skipped"] == 1 else "applied_admission") if row["outcome_available"] else "unavailable"
                if self.raw is not None and self.raw["pre_context"]["config"] != self._config():
                    row["configuration_changed"] = True
                    self.invalidate("configuration", ValueError("Configuration changed during captured attempt"))
                row["evidence_ready_before_drain"] = bool(exception is None and result is not None and not self.invalid
                    and not row["observer_errors"] and row["outcome_available"] and self.raw is not None and "actual" in self.raw)
            except Exception as error:
                row["evidence_ready_before_drain"] = False
                self.invalidate("attempt_exit_observation", error)
            try:
                # Even a control/observation/learner failure retains whatever
                # actual PRE/loss evidence exists; publication cannot replace it.
                self._persist_raw(row)
                row["capture_complete"] = bool(row.get("evidence_ready_before_drain") and not self.invalid)
            except Exception as error:
                row["capture_complete"] = False
                self.invalidate("attempt_drain", error)
            finally:
                # No PreparedBatch/slot/device/view/raw model tensors survive.
                row.pop("draw", None)
                self.raw = None
                self.current = None
            row["drain_ns"] = time.monotonic_ns() - started
            try:
                self._json("attempt-%02d.json" % row["index"], row)
            except Exception as error:
                row["capture_complete"] = False
                self.invalidate("attempt_receipt", error)
            self._publish()
            if self.consumed == ATTEMPTS:
                complete = len(self.rows) == ATTEMPTS and not self.invalid and not self.reporting_failed and all(r.get("capture_complete") for r in self.rows)
                self._json("final.json", dict(status="EIGHT_INPUT_CE_CAPTURES_COMPLETE" if complete else "INCOMPLETE_OR_INVALID",
                    attempts_consumed=self.consumed, complete=complete, offline_target_scope="RECOMPUTED/conditional",
                    actual_target_entropy_or_KL_observed=False, rows=self.rows, observer_errors=self.errors))
