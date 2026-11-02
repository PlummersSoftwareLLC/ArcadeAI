"""Small stdlib fixtures; no actual checkpoint or Torch import."""
import copy
import importlib.util
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("lineage96_proposal_test", HERE / "capture96M_lineage_proposal.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Device:
    def __init__(self, name="cpu"):
        self.type = name

    def __str__(self):
        return self.type


class Tensor:
    def __init__(self, value=100.0, shape=(), device="cpu"):
        self.value, self.shape = value, shape
        self.device, self.dtype = Device(device), "torch.float32"

    def item(self):
        return self.value

    def numel(self):
        return math.prod(self.shape)


class Torch:
    @staticmethod
    def is_tensor(value):
        return isinstance(value, Tensor)


def optimizer():
    return dict(state={index: dict(step=Tensor(), exp_avg=Tensor(shape=(2, 3)),
        exp_avg_sq=Tensor(shape=(2, 3))) for index in range(81)},
        param_groups=[dict(params=list(range(99)), lr=2.5e-5, betas=(.9, .999), eps=.00015)])


class Capture96ProposalTests(unittest.TestCase):
    def test_exact_batch_exposure_and_wrong_phase_rejection(self):
        before = dict(training_steps=10, optimized_samples=100, learner_frame_count=5)
        after = dict(training_steps=13, optimized_samples=100 + 3 * 4096, learner_frame_count=8)
        result = module.exposure(before, after, 4096, "fixture4096")
        self.assertEqual((result["logical_updates_delta"], result["optimized_samples_delta"]), (3, 12288))
        with self.assertRaises(ValueError):
            module.exposure(before, after, 2048, "wrong record")
        with self.assertRaises(ValueError):
            module.exposure(after, before, 4096, "reset")

    def test_realistic_Adam81_geometry_counts_steps_and_CPU_devices(self):
        data = optimizer()
        result, tensors = module.optimizer_info(data, Torch)
        self.assertEqual(result["state_count"], 81)
        self.assertEqual(result["step_values"], [100.0])
        self.assertEqual(result["groups"][0]["parameter_count"], 99)
        self.assertEqual(len(tensors), 243)
        self.assertTrue(result["all_tensors_CPU"])
        self.assertEqual(result["groups"][0]["betas"], [.9, .999])

    def test_Adam_missing_states_duplicate_ids_bad_moments_steps_and_GPU_fail(self):
        mutations = [lambda value: value["state"].pop(80),
            lambda value: value["param_groups"][0]["params"].__setitem__(98, 0),
            lambda value: value["state"][0].update(exp_avg_sq=Tensor(shape=(4,))),
            lambda value: value["state"][0].update(step=float("nan")),
            lambda value: value["state"][0].update(exp_avg=Tensor(device="cuda"))]
        for index, change in enumerate(mutations):
            data = optimizer()
            change(data)
            with self.subTest(case=index), self.assertRaises(ValueError):
                module.optimizer_info(data, Torch)

    def test_state_signatures_reject_non_tensor_or_non_CPU(self):
        result = module.signature({"weight": Tensor(shape=(2, 3))}, Torch)
        self.assertEqual(result, {"weight": dict(shape=[2, 3], dtype="torch.float32")})
        for data in ({"weight": []}, {"weight": Tensor(device="cuda")}):
            with self.assertRaises(ValueError):
                module.signature(data, Torch)

    def test_LR_schedule_value_is_recorded_without_changing_group_geometry(self):
        a, b = [dict(lr=.1, eps=.00015)], [dict(lr=.05, eps=.00015)]
        self.assertEqual(module.group_geometry(a), module.group_geometry(b))
        self.assertNotEqual(a, b)
        with self.assertRaises(ValueError):
            module.scalar(float("inf"), Torch)

    def test_missing_capture_pair_stops_before_Torch_or_checkpoint_read(self):
        before = set(sys.modules)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, CUDA_VISIBLE_DEVICES=""), \
                patch.object(module, "RUN", Path(directory)), patch.object(module, "GAME", Path(directory)), \
                patch.object(module, "CAMPAIGN", Path(directory)), \
                patch.object(module, "load_contract", side_effect=AssertionError("contract loaded before actual files")), \
                self.assertRaisesRegex(ValueError, "must both exist"):
            module.capture(Path(directory) / "proposed-fixture.json")
        self.assertFalse(any(name == "torch" or name.startswith("torch.") for name in set(sys.modules) - before))


if __name__ == "__main__":
    unittest.main()
