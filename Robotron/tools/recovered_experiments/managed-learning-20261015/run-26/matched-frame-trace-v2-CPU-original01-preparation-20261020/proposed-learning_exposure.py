"""Default-off bounded exposure telemetry; imports no NumPy/Torch/device code.

ReplayInsertExposure has NO lock: replay owns its existing lock for every method.
OptimizerExposure owns only its scalar lock, never a model/replay/device lock.
Counters are process-local, never checkpoint-restored or used by schedules.
"""
import matched_frame_trace_v2 as _request_trace
from collections.abc import Mapping
from dataclasses import dataclass
import math
from numbers import Real
import os
import threading
import time

SUPPORTED_TORCH = "2.13.0+cu130"


def exposure_enabled(environ=None):
    return (os.environ if environ is None else environ).get(
        "DQN_LEARNING_EXPOSURE_COUNTERS", "0").strip().lower() in ("1", "true", "yes", "on")


def disabled_snapshot():
    return dict(schema="robotron-learning-exposure-v1", enabled=False, available=False,
                reason="DQN_LEARNING_EXPOSURE_COUNTERS disabled")


class ReplayInsertExposure:
    """Count only normally completed ring adds; the caller holds replay.lock."""
    categories = ("dqn", "epsilon", "expert", "eval", "unattributed")

    def __init__(self):
        self.process_id = os.getpid()
        self.instance_monotonic_ns = time.monotonic_ns()
        self.epoch = 0
        self.epoch_reason = "created_empty"
        self.counts = dict.fromkeys(self.categories, 0)
        self.base = dict(self.counts)

    def new_epoch(self, reason):
        # Invalidate the previous ring lineage BEFORE destructive mutation.
        # A failed partial load therefore cannot preserve a stale burn-in proof.
        self.epoch += 1
        self.epoch_reason = str(reason)[:80]
        self.base = dict(self.counts)

    def accepted(self, source_actor, expert, actor_kind):
        if expert:
            category = "expert"
        elif source_actor == "eval":
            category = "eval"
        elif source_actor == "dqn" and actor_kind == 0:
            category = "dqn"
        elif source_actor == "epsilon" and actor_kind == 1:
            category = "epsilon"
        else:
            category = "unattributed"
        self.counts[category] += 1
        _request_trace.insert_accepted(self, category)

    def snapshot(self):
        total = dict(self.counts)
        epoch = {key: total[key] - self.base[key] for key in self.categories}
        return dict(schema="robotron-replay-insert-exposure-v1", enabled=True,
            available=True, process_id=self.process_id, instance_monotonic_ns=self.instance_monotonic_ns,
            epoch=self.epoch, epoch_reason=self.epoch_reason,
            accepted_total=sum(total.values()), accepted_learner_total=total["dqn"] + total["epsilon"],
            accepted_by_source_total=total,
            accepted_since_epoch=sum(epoch.values()), accepted_learner_since_epoch=epoch["dqn"] + epoch["epsilon"],
            accepted_by_source_since_epoch=epoch,
            scope="New normally completed ring.add calls only; imported rows/banks/wire frames excluded. Process-local, not persisted.")


def capture_amp_found_inf(scaler, optimizer, device, *, is_tensor, adam_type, scaler_type, torch_version):
    """Retain ONE existing scalar tensor by identity after unscale, before step.

    Read metadata only. No item/cpu/to/clone/detach/reduction/synchronization.
    Unsupported/private-state drift yields an unavailable outcome, not a fallback
    optimizer implementation. The optimizer/scaler themselves remain untouched.
    """
    try:
        if torch_version != SUPPORTED_TORCH:
            return None, "unsupported_torch"
        if type(optimizer) is not adam_type or getattr(optimizer.step, "__func__", None) is not adam_type.step:
            return None, "unsupported_optimizer"
        if getattr(optimizer, "_step_supports_amp_scaling", None) is not True:
            return None, "unsupported_optimizer"
        groups = optimizer.param_groups
        if not groups or not all(group.get("fused") is True for group in groups):
            return None, "unsupported_optimizer"
        if type(scaler) is not scaler_type:
            return None, "unsupported_scaler"
        if scaler._enabled is False:
            return None, "scaler_disabled"
        if scaler._enabled is not True:
            return None, "missing_scaler_state"
        states = scaler._per_optimizer_states
        # update() adds later device states in-place into the first tensor.
        # Prohibit that case instead of creating a reduction/copy ourselves.
        if not isinstance(states, Mapping) or len(states) != 1 or id(optimizer) not in states:
            return None, "nonunique_optimizer_state"
        state = states.get(id(optimizer))
        if not isinstance(state, Mapping) or getattr(state.get("stage"), "name", None) != "UNSCALED":
            return None, "bad_scaler_stage"
        found = state.get("found_inf_per_device")
        if not isinstance(found, Mapping) or len(found) != 1:
            return None, "nonunique_inf_device"
        owner, tensor = next(iter(found.items()))
        if (not is_tensor(tensor) or tensor.ndim != 0 or str(tensor.dtype) != "torch.float32"
                or tensor.requires_grad or tensor.device.type != "cuda"
                or tensor.device != device or owner != tensor.device):
            return None, "malformed_inf_tensor"
        return tensor, "single_cuda_found_inf"
    except Exception:
        return None, "missing_scaler_state"


@dataclass(slots=True)
class _Ticket:
    owner: object
    epoch: int
    finished: bool = False


class OptimizerExposure:
    """Completed call outcomes after the REQUIRED packed readback, plus starts.

    All APIs are scalar-only. A ticket makes exceptional/straddled outcomes
    explicit without retaining an unbounded per-step registry.
    """
    fields = ("attempts_started", "outcomes_recorded", "applied", "amp_skipped", "unavailable")

    def __init__(self):
        self.lock = threading.Lock()
        self.process_id = os.getpid()
        self.instance_monotonic_ns = time.monotonic_ns()
        self.epoch, self.epoch_reason = 0, "optimizer_created"
        self.total = dict.fromkeys(self.fields, 0)
        self.current = dict(self.total)
        self.straddled_outcomes = 0
        self.last_reason = None

    def new_epoch(self, reason):
        with self.lock:
            self.epoch += 1
            self.epoch_reason = str(reason)[:80]
            self.current = dict.fromkeys(self.fields, 0)

    def begin(self):
        with self.lock:
            self.total["attempts_started"] += 1
            self.current["attempts_started"] += 1
            return _Ticket(self, self.epoch)

    def finish(self, ticket, mode, found_inf=None):
        if mode in ("unscaled", "scaler_disabled"):
            outcome, reason = "applied", mode
        elif mode == "single_cuda_found_inf":
            # This is an already-read HOST scalar, not a Tensor.item call.
            try:
                if not isinstance(found_inf, Real) or isinstance(found_inf, bool):
                    raise TypeError("outcome must already be a real HOST scalar")
                value = float(found_inf)
                if not math.isfinite(value) or value not in (0.0, 1.0):
                    raise ValueError("not binary found_inf")
                outcome, reason = ("amp_skipped" if value == 1.0 else "applied"), mode
            except (TypeError, ValueError, OverflowError):
                outcome, reason = "unavailable", "invalid_found_inf_readback"
        else:
            outcome, reason = "unavailable", str(mode)[:80]
        with self.lock:
            if not isinstance(ticket, _Ticket) or ticket.owner is not self or ticket.finished:
                # Telemetry misuse cannot advance optimizer or double count.
                self.last_reason = "invalid_or_duplicate_ticket"
                return
            ticket.finished = True
            self.total["outcomes_recorded"] += 1
            self.total[outcome] += 1
            if ticket.epoch == self.epoch:
                self.current["outcomes_recorded"] += 1
                self.current[outcome] += 1
            else:
                self.straddled_outcomes += 1
            self.last_reason = reason

    def snapshot(self):
        with self.lock:
            return dict(schema="robotron-optimizer-exposure-v1", enabled=True,
                available=(self.current["unavailable"] == 0 and self.current["outcomes_recorded"] > 0
                    and self.total["attempts_started"] == self.total["outcomes_recorded"]),
                process_id=self.process_id, instance_monotonic_ns=self.instance_monotonic_ns,
                epoch=self.epoch, epoch_reason=self.epoch_reason,
                total=dict(self.total), since_epoch=dict(self.current),
                unclassified_started_total=self.total["attempts_started"]-self.total["outcomes_recorded"],
                prior_epoch_outcomes_total=self.straddled_outcomes, last_reason=self.last_reason,
                supported_torch=SUPPORTED_TORCH,
                scope="Applied=optimizer call admitted, not proof every parameter moved/Adam step advanced. Step/scaler attempts; exceptions/missing state unavailable. Process-local, not a schedule/checkpoint counter.")
