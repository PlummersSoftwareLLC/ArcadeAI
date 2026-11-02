"""Strict inference actor for an isolated frozen-policy evaluator.

This module never constructs RainbowAgent, replay, an optimizer, or a learner.
The canonical checkpoint policy stays on CPU for restoration; only one
RainbowNet serves actions. CPU and CUDA inference use float32, without autocast.
CUDA TF32 settings match the production model module. Eager versus compiled
kernels and different GPU architectures still require a new common-backend
baseline and candidate comparison.
"""

from collections.abc import Mapping
import copy
import hashlib
import math
import os
from pathlib import Path
import threading
import time

import numpy as np
import torch

try:
    from .config import RL_CONFIG
    from .model import RainbowNet, NUM_MOVE, NUM_FIRE, NUM_JOINT
except ImportError:
    from config import RL_CONFIG
    from model import RainbowNet, NUM_MOVE, NUM_FIRE, NUM_JOINT


ENGINE_VERSION = 28
_CLOCK_FIELDS = ("training_steps", "optimized_samples", "learner_frame_count", "frame_count")
_OPTIONAL_CLOCK_FIELDS = ("total_training_steps", "total_optimized_samples", "last_target_update_samples")


def _file_identity(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


class InferenceActor:
    """Serve immutable-checkpoint greedy actions and temporary measurement swaps.

    ``capture_inference_policy`` always returns the original selected policy,
    matching the online-policy restoration contract of ManagedMeasurement.
    Temporary installs never change checkpoint identity, counters, or that copy.
    Invalid inference requests and runtime failures latch ``inference_error``;
    callers must abort the entire evaluation instead of accepting neutral-action
    fallbacks from a transport batching layer.
    """

    def __init__(self, checkpoint_path, device="cpu", *, inference_dtype=torch.float32,
                 inference_backend="eager"):
        if inference_dtype not in (torch.float32, "float32", "fp32"):
            raise ValueError("InferenceActor requires the production float32 inference policy")
        self.inference_device = torch.device(device)
        if self.inference_device.type not in ("cpu", "cuda"):
            raise ValueError("InferenceActor supports CPU or CUDA only")
        if inference_backend not in ("eager", "inductor"):
            raise ValueError("Inference backend must be eager or inductor")
        if inference_backend == "inductor" and self.inference_device.type != "cuda":
            raise ValueError("The opt-in inductor sidecar backend requires CUDA")
        self.inference_backend = inference_backend
        self.device = self.inference_device
        self.inference_dtype = torch.float32
        self.state_size = int(RL_CONFIG.state_size)
        self._training_lock = threading.RLock()
        self._sync_lock = threading.RLock()
        self.behavior_locked = False
        self._prefetch_paused = False
        self._inference_error = None
        self._closed = False
        self.memory = None
        self.optimizer = None
        self.use_separate_inference = True
        self.compiled_infer_q_joint = None
        self._compile_guard = None
        self._compile_report = None

        # Construct and validate on CPU before allocating any requested GPU.
        self.infer_net = RainbowNet(self.state_size).cpu().float().eval()
        self.infer_net.requires_grad_(False)
        expected = self.infer_net.state_dict()
        self._schema = {name: (value.shape, value.dtype) for name, value in expected.items()}
        self._support = expected.get("support")
        if self._support is not None:
            self._support = self._support.detach().clone().cpu()
        state, metadata, sha256, path = self._read_checkpoint(checkpoint_path)
        self._checkpoint_metadata = metadata
        self._checkpoint_sha256 = sha256
        self._checkpoint_path = path
        self._original_policy = {name: value.detach().clone().cpu() for name, value in state.items()}
        self.infer_net.load_state_dict(state, strict=True)
        del state
        if self.inference_device.type == "cuda":
            # These are already enabled by production model.py on CUDA. Set
            # them explicitly in this isolated process and record the policy.
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            torch.backends.cudnn.benchmark = True
            torch.set_float32_matmul_precision("high")
        self.infer_net.to(device=self.inference_device, dtype=self.inference_dtype)
        self.infer_net.eval()
        self._numeric_policy = dict(
            execution="eager", backend="eager", weights="float32", inputs="float32", support="float32",
            autocast=False, compiled=False, device=str(self.inference_device),
            float32_matmul_precision=torch.get_float32_matmul_precision(),
            cuda_matmul_allow_tf32=bool(torch.backends.cuda.matmul.allow_tf32),
            cudnn_allow_tf32=bool(torch.backends.cudnn.allow_tf32),
            cudnn_benchmark=bool(torch.backends.cudnn.benchmark),
            caveat="GPU architecture and eager/compiled kernel differences require a common-backend baseline.",
        )
        if inference_backend == "inductor":
            self._prepare_compiled_inference()

    @property
    def checkpoint_path(self):
        return self._checkpoint_path

    @property
    def checkpoint_sha256(self):
        return self._checkpoint_sha256

    @property
    def checkpoint_metadata(self):
        return dict(self._checkpoint_metadata)

    @property
    def numeric_policy(self):
        return copy.deepcopy(self._numeric_policy)

    @property
    def compile_report(self):
        return copy.deepcopy(self._compile_report)

    @property
    def inference_error(self):
        return self._inference_error

    @property
    def training_enabled(self):
        return False

    @training_enabled.setter
    def training_enabled(self, value):
        if value:
            raise RuntimeError("InferenceActor cannot enable training")

    @property
    def training_steps(self):
        return self._checkpoint_metadata["training_steps"]

    @property
    def optimized_samples(self):
        return self._checkpoint_metadata["optimized_samples"]

    @property
    def learner_frame_count(self):
        return self._checkpoint_metadata["learner_frame_count"]

    @property
    def frame_count(self):
        return self._checkpoint_metadata["frame_count"]

    def _validate_policy(self, state):
        if not isinstance(state, Mapping) or set(state) != set(self._schema):
            raise ValueError("Inference checkpoint actor keys differ from the exact model schema")
        for name, value in state.items():
            shape, dtype = self._schema[name]
            if not isinstance(value, torch.Tensor) or value.shape != shape or value.dtype != dtype:
                raise ValueError(f"Inference checkpoint tensor shape or dtype differs: {name}")
            if value.layout != torch.strided:
                raise ValueError(f"Inference checkpoint tensor layout differs: {name}")
            if value.is_floating_point() and not bool(torch.isfinite(value).all()):
                raise ValueError(f"Inference checkpoint tensor is non-finite: {name}")
        if self._support is not None and not torch.equal(state["support"].detach().cpu(), self._support):
            raise ValueError("Inference checkpoint C51 support differs")

    def _read_checkpoint(self, filepath):
        path = Path(filepath).expanduser().resolve(strict=True)
        sha256 = hashlib.sha256()
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                sha256.update(chunk)
            stream.seek(0)
            checkpoint = torch.load(stream, map_location="cpu", weights_only=True)
            after = os.fstat(stream.fileno())
        if _file_identity(before) != _file_identity(after) or _file_identity(after) != _file_identity(path.stat()):
            raise ValueError("Inference checkpoint changed while reading")
        if not isinstance(checkpoint, dict):
            raise ValueError("Inference checkpoint must be a dictionary")
        expected = dict(engine_version=ENGINE_VERSION, state_size=self.state_size,
                        single_frame_state_size=int(RL_CONFIG.single_frame_state_size),
                        frame_stack=int(RL_CONFIG.frame_stack))
        for name, value in expected.items():
            actual = checkpoint.get(name)
            if isinstance(actual, bool) or not isinstance(actual, int) or actual != value:
                raise ValueError(f"Inference checkpoint metadata differs: {name}")
        for name in _CLOCK_FIELDS:
            value = checkpoint.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"Inference checkpoint needs a nonnegative integer clock: {name}")
        for name in _OPTIONAL_CLOCK_FIELDS:
            if name in checkpoint:
                value = checkpoint[name]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f"Inference checkpoint optional clock is invalid: {name}")
        state = checkpoint.get("online_state_dict")
        self._validate_policy(state)
        metadata_names = (*expected, *_CLOCK_FIELDS, *_OPTIONAL_CLOCK_FIELDS, "measurement_frame_count")
        metadata = {name: checkpoint[name] for name in metadata_names if name in checkpoint}
        measurement_frames = checkpoint.get("measurement_frame_count", 0)
        if isinstance(measurement_frames, bool) or not isinstance(measurement_frames, int) or measurement_frames < 0:
            raise ValueError("Inference checkpoint measurement frame clock is invalid")
        metadata["measurement_frame_count"] = measurement_frames
        metadata["defaulted_metadata_fields"] = (() if "measurement_frame_count" in checkpoint
                                                 else ("measurement_frame_count",))
        return state, metadata, sha256.hexdigest(), str(path)

    def capture_inference_policy(self):
        with self._training_lock:
            return {name: value.clone() for name, value in self._original_policy.items()}

    def prepare_inference_checkpoint(self, filepath):
        state, _, sha256, path = self._read_checkpoint(filepath)
        if path == self._checkpoint_path and sha256 != self._checkpoint_sha256:
            raise ValueError("The selected inference checkpoint identity changed")
        return state

    def install_inference_policy(self, state):
        with self._training_lock, self._sync_lock:
            if self.training_enabled or not self.behavior_locked:
                raise RuntimeError("Lock behavior and pause training before installing a measurement policy")
            self._validate_policy(state)
            try:
                if self.inference_device.type == "cuda":
                    torch.cuda.synchronize(self.inference_device)
                self.infer_net.load_state_dict(state, strict=True)
                self.infer_net.eval()
                if self.inference_device.type == "cuda":
                    torch.cuda.synchronize(self.inference_device)
            except Exception as error:
                self._latch(error)
                raise

    def _pause_prefetch(self):
        self._prefetch_paused = True

    def _resume_prefetch(self):
        self._prefetch_paused = False

    def _latch(self, error):
        if self._inference_error is None:
            self._inference_error = f"{type(error).__name__}: {error}"

    def _check_ready(self):
        if self._closed:
            raise RuntimeError("InferenceActor is closed")
        if self._inference_error is not None:
            raise RuntimeError(f"InferenceActor has a latched fatal error: {self._inference_error}")

    @staticmethod
    def _compiled_graph_state():
        from torch._dynamo.utils import counters
        return dict(unique_graphs=int(counters.get("stats", {}).get("unique_graphs", 0)),
                    graph_breaks=sum(counters.get("graph_break", {}).values()),
                    unimplemented=sum(counters.get("unimplemented", {}).values()))

    def _verify_compile_guard(self):
        if self._compile_guard is None:
            return
        import torch._dynamo as dynamo
        if dynamo.config.suppress_errors or not dynamo.config.error_on_recompile:
            raise RuntimeError("Strict compiled inference settings changed")
        if self._compiled_graph_state() != self._compile_guard:
            raise RuntimeError("Compiled inference graph/retrace/fallback counters changed after warmup")

    def _prepare_compiled_inference(self):
        """Compile and warm serially before any socket or actor can be created.

        Serving rejects a recompile or fallback after readiness. Warmup uses
        the exact inference context, all supported batch sizes and a separate
        serving thread; model/module/tensor storage is never replaced.
        """
        import torch._dynamo as dynamo
        started = time.monotonic()
        dynamo.config.suppress_errors = False
        dynamo.config.error_on_recompile = False
        for name, value in (("recompile_limit", 64), ("cache_size_limit", 64),
                            ("accumulated_recompile_limit", 1024), ("accumulated_cache_size_limit", 1024)):
            if hasattr(dynamo.config, name):
                setattr(dynamo.config, name, value)
        options = {"triton.cudagraphs": False}
        self.compiled_infer_q_joint = torch.compile(
            self.infer_net.q_values_joint, backend="inductor", dynamic=True, options=options)
        populated = np.random.default_rng(20261016).random((16, self.state_size), dtype=np.float32)
        variants = (np.zeros_like(populated), populated)
        primary = (1, 2, 4, 8, 16)
        for size in (*primary, *(size for size in range(1, 17) if size not in primary)):
            for states in variants:
                self.act_batch(states[:size], [0.0]*size)
        guard = self._compiled_graph_state()
        if not guard["unique_graphs"] or guard["graph_breaks"] or guard["unimplemented"]:
            raise RuntimeError(f"Compiled inference did not produce complete supported graphs: {guard}")
        self._compile_guard = guard
        dynamo.config.error_on_recompile = True
        failures = []

        def serving_probe():
            try:
                for size in range(1, 17):
                    for states in variants:
                        self.act_batch(states[:size], [0.0]*size,
                                       [None if i % 2 == 0 else i % NUM_FIRE for i in range(size)])
            except BaseException as error:
                failures.append(error)

        worker = threading.Thread(target=serving_probe, name="CompileServingProbe", daemon=True)
        worker.start()
        worker.join(timeout=60.0)
        if worker.is_alive():
            error = TimeoutError("Compiled inference serving-thread warmup exceeded60s")
            self._latch(error)
            raise error
        if failures:
            raise RuntimeError("Compiled inference serving-thread warmup failed") from failures[0]
        self._verify_compile_guard()
        self._numeric_policy.update(
            execution="torch.compile", compiled=True, backend="inductor", dynamic=True,
            compile_options=options, cudagraphs=False, suppress_errors=False,
            error_on_recompile=True, graph_breaks=0, max_batch_size=16,
            warm_shapes=list(range(1, 17)), warm_context="torch.inference_mode/autocast_disabled",
            serving_thread_checked=True,
        )
        self._compile_report = dict(warm_s=time.monotonic()-started, graph_state=dict(guard),
                                    primary_warm_shapes=list(primary), all_shapes_verified=list(range(1, 17)))

    def _infer_q_joint(self, states_t, return_cpu=False):
        with self._sync_lock:
            self._check_ready()
            try:
                if states_t.ndim != 2 or states_t.shape[1] != self.state_size:
                    raise ValueError("Inference input must have shape (batch, state_size)")
                if self.compiled_infer_q_joint is not None and not 1 <= states_t.shape[0] <= 16:
                    raise ValueError("Compiled sidecar inference only supports prewarmed batches1..16")
                if not bool(torch.isfinite(states_t).all()):
                    raise ValueError("Inference input contains non-finite values")
                self.infer_net.eval()
                self._verify_compile_guard()
                with torch.inference_mode(), torch.autocast(self.inference_device.type, enabled=False):
                    inputs = states_t.to(device=self.inference_device, dtype=self.inference_dtype)
                    fn = self.compiled_infer_q_joint or self.infer_net.q_values_joint
                    output = fn(inputs)
                    self._verify_compile_guard()
                    if output.shape != (states_t.shape[0], NUM_JOINT) or not bool(torch.isfinite(output).all()):
                        raise ValueError("Inference Q output has invalid shape or non-finite values")
                    if return_cpu:
                        return output.detach().cpu()
                    # A returned GPU tensor must finish before the lock permits
                    # an in-place policy install on another inference thread.
                    if self.inference_device.type == "cuda":
                        torch.cuda.synchronize(self.inference_device)
                    return output
            except Exception as error:
                self._latch(error)
                raise

    def act(self, state, epsilon=0.0, locked_fire=None):
        return self.act_batch([state], [epsilon], [locked_fire])[0]

    def act_batch(self, states, epsilons, locked_fires=None):
        with self._sync_lock:
            self._check_ready()
            try:
                if len(states) != len(epsilons):
                    raise ValueError("Inference states and epsilons must be aligned")
                if any(not math.isfinite(float(value)) or float(value) != 0 for value in epsilons):
                    raise ValueError("InferenceActor serves greedy epsilon=0 actions only")
                if len(states) == 0:
                    return []
                locks = [None] * len(states) if locked_fires is None else list(locked_fires)
                locks += [None] * max(0, len(states) - len(locks))
                batch = np.asarray(states, dtype=np.float32)
                if batch.shape != (len(states), self.state_size):
                    raise ValueError("Inference states have invalid shape")
                q = self._infer_q_joint(torch.from_numpy(batch), return_cpu=True)
                values = q.numpy().reshape(len(states), NUM_MOVE, NUM_FIRE)
                best = values.reshape(len(states), NUM_JOINT).argmax(axis=1)
                actions = []
                for row, joint in enumerate(best):
                    if locks[row] is not None:
                        fire = max(0, min(NUM_FIRE - 1, int(locks[row])))
                        move = int(values[row, :, fire].argmax())
                    else:
                        move, fire = int(joint) // NUM_FIRE, int(joint) % NUM_FIRE
                    actions.append((move, fire, False))
                return actions
            except Exception as error:
                self._latch(error)
                raise

    def debug_q_spread(self, state):
        tensor = torch.from_numpy(np.asarray(state, dtype=np.float32)).unsqueeze(0)
        q = self._infer_q_joint(tensor, return_cpu=True).view(1, NUM_MOVE, NUM_FIRE)
        return q.max(dim=2).values[0].tolist(), q.max(dim=1).values[0].tolist()

    def close(self):
        with self._sync_lock:
            self._closed = True

    @staticmethod
    def _forbidden(*args, **kwargs):
        raise RuntimeError("InferenceActor forbids training, replay, checkpoint mutation, and saving")

    step = train_step = train = save = load = update_target = _forbidden
    start_training_thread = snapshot_training_state = restore_training_state = _forbidden
    add_replay = save_replay = load_replay = clear_replay = _forbidden
