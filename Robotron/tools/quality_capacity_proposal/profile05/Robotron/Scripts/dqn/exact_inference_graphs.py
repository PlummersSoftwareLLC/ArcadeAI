"""Opt-in, startup-only exact-size CUDA graphs for joint CPU-return inference.

This module imports no torch and allocates nothing on import. The agent owns the
stream and RLock. Every static-input copy, replay and blocking fresh CPU copy
must finish in that lock, on that stream. CUDA diagnostic callers never receive
these reusable outputs. No padding, shared pools, recapture or eager fallback.
"""
import threading
import time


MAX_BATCH = 128
DEFAULT_BUDGET_BYTES = 10 * (1 << 30)
MIN_FREE_BYTES = 512 * (1 << 20)


class ExactInferenceGraphError(RuntimeError):
    """A requested graph route is unsafe; startup/serving must fail closed."""


def storage_signature(net):
    tensors = [("parameter:" + name, value) for name, value in net.named_parameters()]
    tensors += [("buffer:" + name, value) for name, value in net.named_buffers()]
    return {name: (value.data_ptr(), tuple(value.shape), tuple(value.stride()),
                   str(value.dtype), str(value.device)) for name, value in tensors}


def private_pool_bytes(segments, pools):
    """Actual reserved allocator segments belonging to our distinct pools."""
    pools = {tuple(pool) for pool in pools}
    sizes = {pool: 0 for pool in pools}
    for segment in segments:
        pool = tuple(segment.get("segment_pool_id", ()))
        if pool in sizes:
            sizes[pool] += int(segment["total_size"])
    if pools and not all(sizes.values()):
        raise ExactInferenceGraphError("CUDA graph private-pool accounting is incomplete")
    return sum(sizes.values())


def _compile_state(torch):
    counters = torch._dynamo.utils.counters
    return {key: dict(counters.get(key, {}))
            for key in ("stats", "graph_break", "unimplemented")}


def disabled_snapshot():
    return {"schema": "robotron-exact-inference-graphs-v1", "requested": False,
            "ready": False, "capture_count": 0, "fallback_count": 0}


class ExactInferenceGraphs:
    """One immutable graph per actual size 1..128, on the existing actor stream.

    The budget covers our *actual private-pool reserved segments plus persistent
    static input bytes*. It excludes the pre-existing learner/ordinary cache.
    Graph capture itself can release the ordinary cache; subtracting a warmed
    process reservation would therefore undercount and is deliberately avoided.
    Allocator/process/free-memory readouts occur only during startup capture.
    """

    def __init__(self, torch, net, compiled, *, stream, lock, state_size,
                 budget_bytes=DEFAULT_BUDGET_BYTES, wall_budget_s=300.0):
        self.torch, self.net, self.compiled = torch, net, compiled
        self.stream, self.lock, self.state_size = stream, lock, int(state_size)
        self.slots = {}
        self._stats_lock = threading.Lock()
        self._pending = None
        self._validating = False
        self._signature = storage_signature(net)
        self._started = time.monotonic()
        self._wall_budget_s = float(wall_budget_s)
        self._stats = dict(disabled_snapshot(), requested=True, ready=False,
            max_batch=MAX_BATCH, covered_shapes=[], private_pool_per_shape=True,
            padding=False, runtime_capture_count=0, fallback_count=0,
            replay_count=0, cpu_return_batches=0, cpu_return_rows=0,
            validation_replay_count=0, validation_cpu_returns=0,
            diagnostic_compiled_calls=0, postload_validations=0,
            fatal_error=None, budget_bytes=int(budget_bytes),
            budget_scope="private_pool_reserved_plus_static_inputs",
            private_pool_reserved_bytes=0, static_input_bytes=0,
            graph_owned_reserved_bytes=0, process_reserved_bytes_at_start=0,
            process_reserved_bytes_after_capture=0, process_peak_reserved_bytes=0,
            minimum_global_free_bytes=0, startup_s=0.0, numeric_policy={})
        try:
            if (stream is None or int(state_size) < 1 or budget_bytes <= 0
                    or not callable(compiled)
                    or not hasattr(compiled, "_torchdynamo_orig_callable")):
                raise ExactInferenceGraphError("Exact graphs require the existing compiled CUDA actor/stream")
            parameters = list(net.parameters())
            if not parameters or parameters[0].device.type != "cuda":
                raise ExactInferenceGraphError("Exact graphs require a CUDA actor")
            self.device = parameters[0].device
            if net.training or any(p.is_floating_point() and p.dtype != torch.float32
                                   for p in list(net.parameters()) + list(net.buffers())):
                raise ExactInferenceGraphError("Exact graphs require eval-mode FP32 actor tensors")
            with lock, torch.cuda.device(self.device), torch.no_grad(), torch.autocast("cuda", enabled=False):
                self._stats["numeric_policy"] = self._numeric_policy()
                self._stats["process_reserved_bytes_at_start"] = int(torch.cuda.memory_reserved(self.device))
                free, _ = torch.cuda.mem_get_info(self.device)
                self._stats["minimum_global_free_bytes"] = int(free)
                self.stream.wait_stream(torch.cuda.current_stream(self.device))
                # Deterministic CPU-only construction: no global RNG state is read or changed.
                self._pattern = ((torch.arange(MAX_BATCH * self.state_size, dtype=torch.float32)
                                  .reshape(MAX_BATCH, self.state_size) % 251) / 250).contiguous()
                self._empty = torch.zeros_like(self._pattern)
                before = _compile_state(torch)
                with torch._dynamo.config.patch(suppress_errors=False, error_on_recompile=False):
                    with torch.cuda.stream(stream):
                        for size in range(1, MAX_BATCH + 1):
                            for sample in (self._pattern, self._empty):
                                compiled(sample[:size].to(self.device)).detach().cpu()
                            self._deadline()
                after = _compile_state(torch)
                for key in ("graph_break", "unimplemented"):
                    if after[key] != before[key]:
                        raise ExactInferenceGraphError("Graph warmup contains compiler breaks/unsupported paths")
                self._compile_guard = after
                pools = set()
                with torch._dynamo.config.patch(suppress_errors=False, error_on_recompile=True):
                    for size in range(1, MAX_BATCH + 1):
                        with torch.cuda.stream(stream):
                            inputs = self._pattern[:size].to(self.device).clone()
                            for _ in range(3):
                                compiled(inputs)
                        stream.synchronize()
                        graph = torch.cuda.CUDAGraph()
                        with torch.cuda.graph(graph, stream=stream, capture_error_mode="global"):
                            outputs = compiled(inputs)
                        stream.synchronize()
                        if tuple(outputs.shape) != (size, 81) or outputs.dtype != torch.float32:
                            raise ExactInferenceGraphError("Captured joint Q layout is not FP32 [batch,81]")
                        pool = tuple(graph.pool())
                        if pool in pools:
                            raise ExactInferenceGraphError("Exact graph pools must be independent")
                        pools.add(pool)
                        self.slots[size] = (graph, inputs, outputs)
                        self._stats["static_input_bytes"] += int(inputs.numel() * inputs.element_size())
                        self._capture_memory(pools)
                        self._stats["capture_count"] = len(self.slots)
                        self._deadline()
                if _compile_state(torch) != self._compile_guard:
                    raise ExactInferenceGraphError("Capture changed compilation state after warmup")
                self.check_storage()
                # Constructor validates random-initialized actor; load() repeats this
                # after the actual checkpoint is copied, before any fleet admission.
                self._stats["ready"] = True
                self.validate(postload=False)
                self._stats["covered_shapes"] = list(range(1, MAX_BATCH + 1))
                self._stats["startup_s"] = time.monotonic() - self._started
        except Exception as exc:
            raise self.fail(exc) from exc

    def _numeric_policy(self):
        t = self.torch
        return {"weights_inputs": "float32", "grad_context": "no_grad",
                "autocast": False, "dynamic_compiled": True,
                "compile_internal_cudagraphs": False,
                "matmul_precision": t.get_float32_matmul_precision(),
                "cuda_matmul_allow_tf32": bool(t.backends.cuda.matmul.allow_tf32),
                "cudnn_allow_tf32": bool(t.backends.cudnn.allow_tf32)}

    def _deadline(self):
        if time.monotonic() - self._started > self._wall_budget_s:
            raise ExactInferenceGraphError("Exact graph startup exceeded its wall budget")

    def _capture_memory(self, pools):
        t = self.torch
        reserved = private_pool_bytes(t.cuda.memory_snapshot(), pools)
        owned = reserved + self._stats["static_input_bytes"]
        free, _ = t.cuda.mem_get_info(self.device)
        self._stats.update(private_pool_reserved_bytes=reserved, graph_owned_reserved_bytes=owned,
            process_reserved_bytes_after_capture=int(t.cuda.memory_reserved(self.device)),
            process_peak_reserved_bytes=int(t.cuda.max_memory_reserved(self.device)),
            minimum_global_free_bytes=min(self._stats["minimum_global_free_bytes"], int(free)))
        if owned > self._stats["budget_bytes"] or free < MIN_FREE_BYTES:
            raise ExactInferenceGraphError("Exact graph memory budget/free headroom exceeded")

    def fail(self, exc):
        error = exc if isinstance(exc, ExactInferenceGraphError) else ExactInferenceGraphError(str(exc))
        with self._stats_lock:
            if self._stats["fatal_error"] is None:
                self._stats["fatal_error"] = str(error)
            self._stats["ready"] = False
        return error

    def _check_locked(self):
        # The same lock protects actor refresh and the complete CPU-return call.
        owned = getattr(self.lock, "_is_owned", None)
        if owned is not None and not owned():
            raise self.fail(ExactInferenceGraphError("Actor sync lock is not held"))
        with self._stats_lock:
            ready, error = self._stats["ready"], self._stats["fatal_error"]
        if not ready or error is not None:
            raise ExactInferenceGraphError("Exact graph actor is not ready: " + str(error))

    def check_storage(self):
        if storage_signature(self.net) != self._signature:
            raise self.fail(ExactInferenceGraphError("Captured actor parameter/buffer storage changed"))

    def prepare_input(self, states):
        """Copy directly into the exact slot; caller holds sync lock/stream."""
        try:
            self._check_locked()
            if self.torch.cuda.current_stream(self.device) != self.stream:
                raise ExactInferenceGraphError("Graph input copy is on the wrong CUDA stream")
            shape = tuple(states.shape)
            if (len(shape) != 2 or shape[1] != self.state_size or shape[0] not in self.slots
                    or states.dtype != self.torch.float32 or self._pending is not None
                    or (states.is_cuda and states.device != self.device)):
                raise ExactInferenceGraphError("Unsupported graph input or unfinished CPU return")
            graph, inputs, outputs = self.slots[shape[0]]
            inputs.copy_(states)
            if states.is_cuda:
                states.record_stream(self.stream)
            self._pending = (shape[0], threading.get_ident(), inputs)
            return inputs
        except Exception as exc:
            raise self.fail(exc) from exc

    def replay_prepared(self, inputs):
        try:
            self._check_locked()
            if self.torch.cuda.current_stream(self.device) != self.stream:
                raise ExactInferenceGraphError("Graph replay is on the wrong CUDA stream")
            if (self._pending is None or self._pending[1] != threading.get_ident()
                    or self._pending[2] is not inputs):
                raise ExactInferenceGraphError("Graph replay does not own the prepared input")
            graph, _, outputs = self.slots[self._pending[0]]
            graph.replay()
            with self._stats_lock:
                key = "validation_replay_count" if self._validating else "replay_count"
                self._stats[key] += 1
            return outputs
        except Exception as exc:
            raise self.fail(exc) from exc

    def complete_cpu_return(self):
        self._check_locked()
        if self._pending is None or self._pending[1] != threading.get_ident():
            raise self.fail(ExactInferenceGraphError("Graph CPU return has no owner"))
        rows = self._pending[0]
        self._pending = None
        with self._stats_lock:
            if self._validating:
                self._stats["validation_cpu_returns"] += 1
            else:
                self._stats["cpu_return_batches"] += 1
                self._stats["cpu_return_rows"] += rows

    def note_compiled_diagnostic(self):
        self._check_locked()
        with self._stats_lock:
            self._stats["diagnostic_compiled_calls"] += 1

    def validate(self, *, samples=None, postload=True):
        """Exact byte/policy parity for all actual sizes, under paused load guard.

        samples may be a fixed CPU copy of replay rows; no replay sampling/RNG.
        Validation is startup/load only and intentionally completes CPU copies.
        Runtime periodic refresh only checks tensor storage, without barriers.
        """
        t = self.torch
        try:
            with self.lock, t.cuda.device(self.device), t.no_grad(), t.autocast("cuda", enabled=False):
                self._check_locked()
                self.check_storage()
                if self._pending is not None or self._numeric_policy() != self._stats["numeric_policy"]:
                    raise ExactInferenceGraphError("Graph validation context changed")
                datasets = [self._empty, self._pattern]
                if samples is not None:
                    if (tuple(samples.shape) != (MAX_BATCH, self.state_size)
                            or samples.dtype != t.float32 or samples.is_cuda):
                        raise ExactInferenceGraphError("Fixed validation sample must be CPU FP32 [128,state_size]")
                    datasets.append(samples)
                before = _compile_state(t)
                self._validating = True
                with t._dynamo.config.patch(suppress_errors=False, error_on_recompile=True):
                    with t.cuda.stream(self.stream):
                        for size in range(1, MAX_BATCH + 1):
                            for sample in datasets:
                                inputs = self.prepare_input(sample[:size])
                                expected = self.compiled(inputs).detach().cpu()
                                actual = self.replay_prepared(inputs).detach().cpu()
                                self.complete_cpu_return()
                                if (not bool(t.isfinite(actual).all())
                                        or not t.equal(expected.contiguous().view(t.uint8),
                                                       actual.contiguous().view(t.uint8))):
                                    raise ExactInferenceGraphError(f"Exact graph Q/policy parity failed at size {size}")
                if _compile_state(t) != before:
                    raise ExactInferenceGraphError("Post-capture validation changed compilation state")
                self.check_storage()
                if postload:
                    with self._stats_lock:
                        self._stats["postload_validations"] += 1
                self._validating = False
        except Exception as exc:
            raise self.fail(exc) from exc
        finally:
            self._validating = False

    def snapshot(self):
        """Stored scalars only: reporting never touches CUDA or actor locks."""
        with self._stats_lock:
            return dict(self._stats, covered_shapes=list(self._stats["covered_shapes"]),
                        numeric_policy=dict(self._stats["numeric_policy"]))
