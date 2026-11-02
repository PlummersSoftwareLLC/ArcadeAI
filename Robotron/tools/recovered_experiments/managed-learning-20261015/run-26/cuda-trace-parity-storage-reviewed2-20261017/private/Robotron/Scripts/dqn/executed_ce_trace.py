"""Opt-in eight-consumed-attempt observer; never selects or changes training.

This proposed module is imported only by the startup-enabled agent path.
Observer entry points contain their own failures so they cannot activate the
learner's compile-disable/fallback handler. Genuine learner errors still escape.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time


ATTEMPTS = 8
MAX_ARRAY_BYTES = 64 * 1024**2
MAX_DISK_BYTES = 128 * 1024**2
MAX_JSON_BYTES = 1024**2


class ObservedReplayBatch(tuple):
    """Same ten fields; diagnostic metadata survives synchronous sampling."""
    def __new__(cls, batch, metadata):
        result = super().__new__(cls, batch)
        result.draw_metadata = metadata
        return result


def error_text(error):
    try:
        return (type(error).__name__ + ": " + str(error))[:500]
    except Exception:
        return type(error).__name__


class ExecutedCETrace:
    """Bounded observation of first8 consumed train_step attempts after guards.

    A failed attempt stays in the eight. Missing targets/outcomes/observer I/O
    invalidate acquisition, never cause a replacement ninth numerical success.
    No optimizer admission is inferred from gradients, loss or logical clocks.
    """
    def __init__(self, directory, cfg, *, optimizer_exposure, runtime):
        if int(cfg.batch_size) != 4096 or int(cfg.num_atoms) != 51:
            raise ValueError("This calibration is fixed to actual4096 rows/51 atoms")
        if optimizer_exposure is None:
            raise ValueError("Actual optimizer exposure counters are required")
        if not 1 <= int(getattr(cfg, "replay_prefetch_slots", 3)) <= 3:
            raise ValueError("Trace storage is bounded to the existing1..3 producer slots")
        if str(getattr(cfg, "per_priority_metric", "ce")) != "ce" or os.getenv("DQN_PER_PRIORITY_METRIC", "ce") != "ce":
            raise ValueError("Executed calibration observes the unchanged CE recipe only")
        self.directory = Path(directory)
        if not self.directory.is_absolute() or not self.directory.name.startswith("ce-executed-trace-"):
            raise ValueError("Explicit absolute new ce-executed-trace-* directory required")
        self.directory.mkdir()  # create-only, no existing artifacts are adopted
        self.lock = threading.RLock()
        self.rows, self.errors = [], []
        self.consumed = 0
        self.current = None
        self.observer_reporting_failed = False
        self.array_bytes = self.disk_bytes = 0
        self.exposure = optimizer_exposure
        self.capture_id = "observer-" + str(time.monotonic_ns())
        self.context = dict(schema="robotron-executed-ce-trace-v1", attempts=ATTEMPTS,
            boundary="first8 consumed train_step attempts after eligibility guards",
            runtime=dict(runtime),
            config={name:value for name,value in vars(cfg).items()
                    if value is None or type(value) in (str, int, float, bool)},
            config_non_scalar_omitted=[name for name,value in vars(cfg).items()
                                      if value is not None and type(value) not in (str,int,float,bool)],
            unknown=dict(model_checkpoint_identity="requires external immutable checkpoint/run binding",
                         source_identity="requires external reviewed overlay/base manifest",
                         full_states="not retained; no numerical replay claim",
                         coherent_anchor="not established by a sequential trace",
                         optimizer_parameter_progress="admission counters do not prove parameter/Adam movement"))
        # Startup failure is fatal before producer/learner construction, never
        # a silent hot toggle to an unobserved training mode.
        self._write_json("context.json", self.context)
        self._publish()

    def want_draw(self):
        try:
            with self.lock:
                return self.consumed < ATTEMPTS
        except Exception as error:
            self.invalidate("draw_enable_observation", error)
            return False

    def invalidate(self, where, error):
        """Best-effort reporting cannot change original training control flow."""
        try:
            with self.lock:
                message = str(where)[:80] + ": " + error_text(error)
                if len(self.errors) < 64:
                    self.errors.append(message)
                if (self.current is not None
                        and self.current.get("consumer_thread_id") == threading.get_ident()
                        and len(self.current["observer_errors"]) < 16):
                    self.current["observer_errors"].append(message)
                try:
                    self._publish()
                except Exception:
                    pass
            try:
                print("[CE TRACE INVALID] " + message, flush=True)
            except Exception:
                pass
        except Exception:
            # Last-resort state is allocated at startup; severe process-level
            # failures may prevent durable publication and require log review.
            self.observer_reporting_failed = True

    def sample(self, memory, batch_size, beta, state_out=None):
        """Exactly one real draw; never retry after an observation failure."""
        if not self.want_draw():
            return memory.sample(batch_size, beta=beta, _state_out=state_out)
        # Replay overlay catches ONLY its metadata-copy failures internally.
        # Actual sample/storage errors retain their original propagation.
        try:
            batch, metadata = memory.sample_with_metadata(
                batch_size, beta=beta, capture_id=self.capture_id, _state_out=state_out)
        except BaseException as error:
            self.invalidate("actual_sampler_exception_before_consumption", error)
            raise  # preserve the original sampler/control exception, no retry
        if batch is None:
            return None
        try:
            if metadata is not None and metadata.get("observer_error"):
                self.invalidate("draw_metadata", RuntimeError(metadata["observer_error"]))
            return ObservedReplayBatch(batch, metadata)
        except Exception as error:
            self.invalidate("attach_draw_metadata", error)
            return batch

    def begin(self, agent, batch, staged, metrics_context=None):
        try:
            with self.lock:
                if self.consumed >= ATTEMPTS:
                    return
                # Reserve before clocks, exposure, metadata or I/O can fail.
                # Missing evidence remains a consumed ordinal, never a retry.
                self.consumed += 1
                row = dict(index=self.consumed, status="entered", observer_errors=[], arrays={},
                           consumer_thread_id=threading.get_ident())
                self.rows.append(row)
                self.current = row
                row.update(consumed_monotonic_ns=time.monotonic_ns(),
                    before=self._clocks(agent), exposure_before=self.exposure.snapshot())
                if metrics_context is not None:
                    with metrics_context.lock:
                        row["frame_context"] = {name:int(getattr(metrics_context,name,0)) for name in
                            ("frame_count","learner_frame_count","measurement_frame_count")}
                    row["frame_context_scope"] = "one metrics-lock observation; not a coherent replay/model snapshot"
                else:
                    row["frame_context"] = None
                metadata = (getattr(staged, "draw_metadata", None) if staged is not None
                            else getattr(batch, "draw_metadata", None))
                if metadata is None:
                    raise RuntimeError("Consumed attempt has no draw-time observation")
                row["draw"] = metadata
                if metadata.get("observer_error"):
                    raise RuntimeError("Consumed draw metadata failed: " + metadata["observer_error"])
                if staged is not None:
                    row["prefetch"] = dict(lease_epoch=staged._epoch,
                        owner_epoch_at_consumption=staged._owner._epoch,
                        is_current_at_consumption=bool(staged.is_current),
                        sample_ms=float(staged.sample_ms), stage_host_ms=float(staged.stage_host_ms))
                    if not row["prefetch"]["is_current_at_consumption"]:
                        raise RuntimeError("Consumed lease was already invalidated")
                else:
                    row["prefetch"] = None
                ended = metadata.get("lock_observation_finished_monotonic_ns")
                row["draw_to_consume_ns"] = row["consumed_monotonic_ns"]-ended if ended is not None else None
                self._publish()
        except Exception as error:
            self.invalidate("begin", error)

    def loss(self, agent, ce, payload, *, weighted_loss, bc_loss, schedule, backend):
        try:
            with self.lock:
                row = self.current
                if row is None:
                    return
                row["backend"] = backend
                if len(payload) != 10:
                    raise ValueError("Trace payload ABI must contain exactly10 same-forward tensors/options")
                row["schedule"] = [float(value) for value in schedule]
                row["at_loss"] = self._clocks(agent)
                names = ("projected_target", "taken_action_log_probabilities",
                         "per_row_bc", "per_row_q_policy", "per_row_margin",
                         "target_action_probabilities", "unclipped_target_support",
                         "bc_contribution", "q_policy_contribution", "margin_contribution")
                values = dict(zip(names, payload))
                values.update(ce=ce, weighted_loss=weighted_loss, bc_loss=bc_loss)
                matrix_names = ("projected_target", "taken_action_log_probabilities",
                                "target_action_probabilities", "unclipped_target_support")
                vector_names = ("ce", "per_row_bc", "per_row_q_policy", "per_row_margin")
                for name, value in values.items():
                    if value is None:
                        row.setdefault("unavailable_auxiliary", []).append(name)
                        continue
                    expected = (4096,51) if name in matrix_names else (4096,) if name in vector_names else ()
                    if tuple(value.shape) != expected:
                        raise ValueError("Unexpected same-forward trace shape: " + name)
                    row.setdefault("tensor_dtypes", {})[name] = str(value.dtype)
                    if self.array_bytes + value.numel()*4 > MAX_ARRAY_BYTES:
                        raise MemoryError("Bounded64MiB trace tensor budget exceeded before copy")
                    array = value.detach().float().cpu().numpy().copy()
                    if self.array_bytes + array.nbytes > MAX_ARRAY_BYTES:
                        raise MemoryError("Bounded64MiB trace tensor budget exceeded")
                    self.array_bytes += array.nbytes
                    array.flags.writeable = False
                    row["arrays"][name] = array
                row["status"] = "loss_observed"
        except Exception as error:
            self.invalidate("loss_observation", error)

    def outcome(self, mode, found_inf, ticket):
        try:
            with self.lock:
                if self.current is None:
                    return
                row = self.current
                row["optimizer_observation"] = dict(mode=str(mode),
                    found_inf=None if found_inf is None else float(found_inf),
                    ticket_epoch=None if ticket is None else ticket.epoch,
                    ticket_finished=bool(ticket is not None and ticket.finished),
                    ticket_owner_matches=bool(ticket is not None and ticket.owner is self.exposure))
                row["exposure_after_outcome"] = self.exposure.snapshot()
        except Exception as error:
            self.invalidate("outcome_observation", error)

    def end(self, agent, *, result=None, exception=None):
        try:
            with self.lock:
                row = self.current
                if row is None:
                    return
                row["after"] = self._clocks(agent)
                row["exposure_at_exit"] = self.exposure.snapshot()
                row["exception"] = None if exception is None else error_text(exception)
                row["result"] = None if result is None else float(result)
                row["status"] = "learner_exception" if exception is not None else (
                    "returned_none" if result is None else "returned_loss")
                before, after = row["exposure_before"], row["exposure_at_exit"]
                delta = {key:after["total"][key]-before["total"][key]
                         for key in ("attempts_started", "outcomes_recorded", "applied", "amp_skipped", "unavailable")}
                row["actual_exposure_delta"] = delta
                same = all(before[key] == after[key] for key in
                           ("process_id", "instance_monotonic_ns", "epoch"))
                observed = row.get("optimizer_observation", {})
                row["outcome_available"] = bool(same and after["available"]
                    and delta["attempts_started"] == delta["outcomes_recorded"] == 1
                    and delta["unavailable"] == 0 and delta["applied"]+delta["amp_skipped"] == 1
                    and observed.get("ticket_finished") and observed.get("ticket_owner_matches"))
                row["optimizer_outcome"] = ("amp_skipped" if delta["amp_skipped"] == 1 else
                    "applied_admission") if row["outcome_available"] else "unavailable"
                row["numerical_capture_complete"] = bool(exception is None and result is not None
                    and not row["observer_errors"] and row["outcome_available"]
                    and "ce" in row["arrays"] and "projected_target" in row["arrays"]
                    and "taken_action_log_probabilities" in row["arrays"])
                self._persist_row(row)
                self.current = None
                self._publish()
        except Exception as error:
            if self.current is not None:
                self.current["numerical_capture_complete"] = False
            self.invalidate("attempt_exit", error)
            self.current = None

    @staticmethod
    def _clocks(agent):
        return dict(training_steps=int(agent.training_steps), optimized_samples=int(agent.optimized_samples),
            last_target_update_samples=int(getattr(agent, "last_target_update_samples", 0)),
            last_inference_sync=int(getattr(agent, "last_inference_sync", 0)),
            learning_rates=[float(group["lr"]) for group in agent.optimizer.param_groups])

    def _persist_row(self, row):
        import numpy as np  # only enabled observer, already used by learner
        arrays = dict(row["arrays"])
        draw = row.get("draw", {})
        def extract(value, prefix):
            if isinstance(value, np.ndarray):
                arrays[prefix] = value
                return {"array": prefix, "dtype": str(value.dtype), "shape": list(value.shape)}
            if isinstance(value, dict):
                return {str(key):extract(item, prefix+"__"+str(key)) for key,item in value.items()}
            if isinstance(value, (tuple, list)):
                return [extract(item, prefix+"__"+str(index)) for index,item in enumerate(value)]
            return value
        summary = {key:value for key,value in row.items() if key not in ("arrays", "draw")}
        summary["draw"] = extract(draw, "draw")
        summary["array_finite"] = {name:bool(np.isfinite(array).all()) for name,array in arrays.items()}
        if not all(summary["array_finite"].values()):
            row["numerical_capture_complete"] = summary["numerical_capture_complete"] = False
            summary["nonfinite_observation"] = True
        needed = sum(value.nbytes for value in arrays.values()) + 1024**2
        if self.disk_bytes + needed > MAX_DISK_BYTES:
            raise OSError("Bounded128MiB trace disk budget exceeded")
        path = self.directory / ("attempt-%02d.npz" % row["index"])
        with path.open("xb") as stream:
            np.savez(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        self.disk_bytes += path.stat().st_size
        self._write_json("attempt-%02d.json" % row["index"], summary)

    def _write_json(self, name, data):
        payload = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False)+"\n").encode()
        if len(payload) > MAX_JSON_BYTES or self.disk_bytes+len(payload) > MAX_DISK_BYTES:
            raise OSError("Bounded trace JSON/disk budget exceeded")
        path = self.directory / name
        temporary = path.with_name(path.name+".tmp")
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        self.disk_bytes += len(payload)  # conservative cumulative write accounting

    def _publish(self):
        summaries = [{key:value for key,value in row.items()
                      if key not in ("arrays", "draw")} for row in self.rows]
        complete = (not self.observer_reporting_failed and self.consumed == len(self.rows) == ATTEMPTS
                    and all(row.get("numerical_capture_complete") for row in self.rows))
        self._write_json("status.json", dict(schema=self.context["schema"],
            status="EIGHT_NUMERICAL_CAPTURES_COMPLETE" if complete and not self.errors else "INCOMPLETE_OR_INVALID",
            attempts_consumed=self.consumed, numerical_captures_complete=complete and not self.errors,
            observer_errors=list(self.errors), rows=summaries,
            observer_reporting_failed=self.observer_reporting_failed,
            tensor_bytes_retained=self.array_bytes, cumulative_disk_bytes=self.disk_bytes))
