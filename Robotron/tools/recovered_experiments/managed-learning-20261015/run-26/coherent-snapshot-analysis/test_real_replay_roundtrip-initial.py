"""Tiny real replay/checkpoint roundtrip, entirely on CPU in temporary directories.

Uses the production replay saver/loader and AST-extracted agent save/load methods,
with small Linear models and actual Adam/CPU GradScaler. It does not construct
a trainer, Rainbow network, game client, CUDA context, or live replay mapping.
"""
import ast
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import traceback
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = ""
for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np
import torch

from Robotron.Scripts.dqn import replay_buffer as replay
from .coherent_snapshot import SnapshotFrameGate, capture_snapshot, process_identity
from .test_coherent_snapshot import FakeConsumer


def agent_methods(metrics, cfg):
    """Run the actual checkpoint code without importing its CUDA-heavy module."""
    source = Path(__file__).resolve().parents[2] / "Scripts/dqn/agent.py"
    tree = ast.parse(source.read_text())
    names = {"save", "load", "_load_compatible", "_load_optimizer_state_dict",
             "_legacy_target_update_samples"}
    decorators = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name in ("_with_training_lock", "_with_training_paused")]
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "RainbowAgent")
    methods = [node for node in original.body if isinstance(node, ast.FunctionDef) and node.name in names]
    candidate = ast.ClassDef(name="CheckpointMethods", bases=[], keywords=[], body=methods, decorator_list=[])
    namespace = dict(os=os, shutil=shutil, torch=torch, traceback=traceback,
                     metrics=metrics, RL_CONFIG=cfg, ENGINE_VERSION=28, RESET_METRICS=False)
    exec(compile(ast.fix_missing_locations(ast.Module(body=decorators + [candidate], type_ignores=[])),
                 str(source), "exec"), namespace)
    return namespace["CheckpointMethods"]


class RealRoundtripTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="robotron-real-snapshot-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in dict(hof_enabled=True, ephof_enabled=True, hof_max_episodes=2,
                ephof_max_episodes=2, hof_episode_stride=64, ephof_episode_stride=64,
                hof_min_game_score=0, ephof_min_episode_score=0, hof_min_transitions=1,
                ephof_min_transitions=1, interesting_replay_bank_size=64,
                replay_live_mmap=True, replay_flush_msync=True).items():
            self.stack.enter_context(patch.object(replay.RL_CONFIG, name, value))
        rng = np.random.get_state()
        self.addCleanup(np.random.set_state, rng)
        torch_rng = torch.get_rng_state()
        self.addCleanup(torch.set_rng_state, torch_rng)
        torch.manual_seed(713711)
        self.cfg = SimpleNamespace(batch_size=3, single_frame_state_size=7, frame_stack=1,
            target_update_period=100, expert_ratio_start=.1, epsilon_start=.1)
        self.metrics = SimpleNamespace(lock=threading.Lock(), training_enabled=True,
            frame_count=1234, learner_frame_count=987, measurement_frame_count=0,
            total_training_steps=2, total_optimized_samples=6, expert_ratio=.1, epsilon=.1,
            coherent_snapshot_keyboard_disabled=True)
        self.methods = agent_methods(self.metrics, self.cfg)
        self.memory = self.new_memory(self.directory / "live")
        with redirect_stdout(io.StringIO()):
            self.assertTrue(self.memory.ensure_live_mmap(str(self.directory / "live/ring"), verbose=False))
        for index in range(45):
            self.add_row(index)
        slots = np.arange(32, dtype=np.int64)
        self.assertTrue(self.memory.hof_admit(slots, 100000, game_uid=7, level=3))
        self.assertTrue(self.memory.ephof_admit(np.roll(slots, 8), 50000, game_uid=8, level=2))
        for index in range(45, 48):
            self.add_row(index)
        self.memory.update_priorities(np.arange(32, dtype=np.int64), np.linspace(.1, 3., 32))
        self.assertEqual(self.memory.tree.data_ptr, 16)
        self.agent = self.new_agent(self.memory)
        self.step(self.agent)
        self.step(self.agent)
        self.server = SimpleNamespace(snapshot_gate=SnapshotFrameGate(True), async_buffer=FakeConsumer(),
                                      running=True, shutdown_event=threading.Event())

    def new_memory(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        memory = replay.PrioritizedReplayBuffer(32, 7)
        memory._hof_dir = str(directory / "banks/hof")
        memory._ephof_dir = str(directory / "banks/ephof")
        self.addCleanup(memory._wait_bank_writer)
        return memory

    def add_row(self, index):
        state = (np.arange(7, dtype=np.float32) + index) / 100
        self.memory.add(state, index % 81, index / 1000, -state, index % 9 == 0,
                        horizon=1 + index % 3, expert=int(index % 5 == 0), actor_kind=index % 3)

    def new_agent(self, memory):
        owner = self.methods()
        owner.memory, owner._ring_dir = memory, memory._mmap_dir
        owner._training_lock = threading.RLock()
        owner.training_enabled, owner._prefetch_paused = True, False
        owner.online_net = torch.nn.Linear(7, 5)
        owner.target_net = torch.nn.Linear(7, 5)
        owner.optimizer = torch.optim.Adam(owner.online_net.parameters(), lr=2.5e-5, foreach=False)
        owner.grad_scaler = torch.amp.GradScaler("cpu", init_scale=128., growth_interval=1)
        owner.device, owner.state_size = torch.device("cpu"), 7
        owner.training_steps, owner.optimized_samples, owner.baseline_batch_size = 0, 0, 512
        owner.last_target_update_samples, owner.lr_manual_scale = 1, .5
        owner.lr_gear, owner.lr_anchor_step = "climb", 0.
        owner._pause_prefetch = lambda: setattr(owner, "_prefetch_paused", True)
        owner._resume_prefetch = lambda: setattr(owner, "_prefetch_paused", False)
        owner._sync_inference = lambda **_: None
        owner.synchronize_snapshot_device = lambda: dict(device="cpu", mode="cpu_noop")
        return owner

    def step(self, owner):
        x = torch.arange(21, dtype=torch.float32).reshape(3, 7) / 100
        owner.optimizer.zero_grad(set_to_none=True)
        owner.grad_scaler.scale(owner.online_net(x).square().mean()).backward()
        owner.grad_scaler.step(owner.optimizer)
        owner.grad_scaler.update()
        owner.training_steps += 1
        owner.optimized_samples += len(x)

    def capture(self):
        ring = Path(self.agent._ring_dir)
        info = ring.stat()
        request = dict(tag="real-cpu", request_id=uuid.uuid4().hex, expected_pid=os.getpid(),
            expected_start_ticks=process_identity()["start_ticks"], expected_ring_dir=str(ring),
            expected_ring_device=info.st_dev, expected_ring_inode=info.st_ino, timeout_s=30)
        with redirect_stdout(io.StringIO()):
            result = capture_snapshot(self.agent, self.metrics, self.server, self.cfg, self.directory, request)
        self.assertTrue(result["valid"])
        return Path(result["directory"]), result["manifest"]

    def assert_nested_equal(self, left, right):
        if isinstance(left, torch.Tensor):
            self.assertTrue(torch.equal(left, right))
        elif isinstance(left, dict):
            self.assertEqual(left.keys(), right.keys())
            for key in left:
                self.assert_nested_equal(left[key], right[key])
        elif isinstance(left, (tuple, list)):
            self.assertEqual(len(left), len(right))
            for a, b in zip(left, right):
                self.assert_nested_equal(a, b)
        else:
            self.assertEqual(left, right)

    def restore_branch(self, archive, name):
        branch = self.directory / name
        shutil.copytree(archive, branch)
        memory = self.new_memory(branch)
        owner = self.new_agent(memory)
        owner._ring_dir = str(branch / "ring")
        with redirect_stdout(io.StringIO()):
            self.assertTrue(owner.load(str(branch / "model.pt"), show_status=False))
        self.assertEqual(len(memory), 32)
        return owner

    def test_real_wrapped_replay_banks_adam_scaler_and_two_fresh_starts_match(self):
        archive, manifest = self.capture()
        self.assertEqual(manifest["before"], manifest["after"])
        self.assertEqual(manifest["before"]["replay_pointer"], 16)
        self.assertEqual(manifest["before"]["replay_adds"], 48)
        checkpoint = torch.load(archive / "model.pt", map_location="cpu", weights_only=True)
        self.assert_nested_equal(checkpoint["optimizer_state_dict"], self.agent.optimizer.state_dict())
        self.assert_nested_equal(checkpoint["grad_scaler_state_dict"], self.agent.grad_scaler.state_dict())
        a, b = (self.restore_branch(archive, name) for name in ("branch-a", "branch-b"))
        for owner in (a, b):
            self.assertEqual((owner.training_steps, owner.optimized_samples), (2, 6))
            self.assertEqual(owner.memory.tree.data_ptr, 16)
            for attribute, _, _ in owner.memory._storage_specs().values():
                np.testing.assert_array_equal(getattr(owner.memory, attribute), getattr(self.memory, attribute))
            np.testing.assert_array_equal(owner.memory.tree.tree[32:], self.memory.tree.tree[32:])
            for bank in ("hof", "ephof"):
                self.assertEqual(getattr(owner.memory, bank + "_total"), getattr(self.memory, bank + "_total"))
                rows = getattr(self.memory, "_" + bank + "_flat")
                for field in self.memory._BANK_FIELDS:
                    np.testing.assert_array_equal(getattr(owner.memory, bank + "_" + field)[rows],
                                                  getattr(self.memory, bank + "_" + field)[rows])
                for field in ("ep_score", "ep_len", "ep_game", "ep_level"):
                    np.testing.assert_array_equal(getattr(owner.memory, bank + "_" + field),
                                                  getattr(self.memory, bank + "_" + field))
                self.assertEqual(owner.memory._adds_total - getattr(owner.memory, "_" + bank + "_last_admit_add"),
                                 self.memory._adds_total - getattr(self.memory, "_" + bank + "_last_admit_add"))
            self.assert_nested_equal(owner.online_net.state_dict(), self.agent.online_net.state_dict())
            self.assert_nested_equal(owner.target_net.state_dict(), self.agent.target_net.state_dict())
            self.assert_nested_equal(owner.optimizer.state_dict(), self.agent.optimizer.state_dict())
            self.assert_nested_equal(owner.grad_scaler.state_dict(), self.agent.grad_scaler.state_dict())
        np.random.seed(713711)
        rng = np.random.get_state()
        sample_a = a.memory.sample(24, beta=.7)
        np.random.set_state(rng)
        sample_b = b.memory.sample(24, beta=.7)
        for x, y in zip(sample_a, sample_b):
            np.testing.assert_array_equal(x, y)
        self.step(a)
        self.step(b)
        self.assert_nested_equal(a.online_net.state_dict(), b.online_net.state_dict())
        self.assert_nested_equal(a.optimizer.state_dict(), b.optimizer.state_dict())
        self.assert_nested_equal(a.grad_scaler.state_dict(), b.grad_scaler.state_dict())
        self.assertFalse(torch.cuda.is_initialized())

    def test_archive_is_independent_of_later_ring_writes_and_bank_generation_gc(self):
        archive, manifest = self.capture()
        before = {name:hashlib.sha256((archive / name).read_bytes()).hexdigest()
                  for name in manifest["files"]}
        for index in range(48, 80):
            self.add_row(index)
        for iteration in range(3):
            self.assertTrue(self.memory.hof_admit(np.arange(32), 200000 + iteration, game_uid=20+iteration))
            self.memory.save(self.memory._mmap_dir, verbose=False)
        for name, sha in before.items():
            self.assertEqual(hashlib.sha256((archive / name).read_bytes()).hexdigest(), sha)
        owner = self.restore_branch(archive, "after-live-mutation")
        np.testing.assert_array_equal(owner.memory.states, np.load(archive / "ring/states.npy"))
        self.assertEqual(owner.memory.tree.data_ptr, 16)
        self.assertTrue((archive / "COMPLETE.json").is_file())
        self.assertFalse(torch.cuda.is_initialized())


if __name__ == "__main__":
    unittest.main()
