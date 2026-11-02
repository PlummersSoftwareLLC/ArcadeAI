"""Small stdlib fixtures; no actual checkpoint or Torch import."""
import copy
import importlib.util
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("lineage128_proposal_test", HERE / "capture128M_lineage_proposal.py")
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


class Capture128ProposalTests(unittest.TestCase):
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

    def test_actual_contract_import_and_help_are_deferred_and_Torch_free(self):
        before=set(sys.modules)
        contract=module.load_contract()
        self.assertEqual(contract.CORE_CLOCKS,("training_steps","optimized_samples","learner_frame_count"))
        self.assertNotIn("torch",set(sys.modules)-before)
        with patch.object(Path,"read_bytes",side_effect=AssertionError("future data read on import")):
            spec=importlib.util.spec_from_file_location("inert128capture",HERE/"capture128M_lineage_proposal.py")
            loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)

    def test_full_fake_checkpoint_proposal_exposure_and_wrong_batch_rejection(self):
        contract=module.load_contract()
        previous=dict(engine_version=28,state_size=11128,single_frame_state_size=2782,frame_stack=4,
            baseline_batch_size=512,training_steps=784690,optimized_samples=1766502400,total_training_steps=784690,
            learner_frame_count=100634474,frame_count=202605628,measurement_frame_count=7550388,
            last_target_update_samples=1766113280,lr_anchor_step=0.0,lr_gear="climb",epsilon=.1,expert_ratio=.1)
        after=dict(previous,training_steps=900000,total_training_steps=900000,learner_frame_count=132629100,
            optimized_samples=1766502400+115310*4096,frame_count=270000000)
        checkpoint=dict(after,online_state_dict={"weight":Tensor(shape=(2,3))},
            target_state_dict={"weight":Tensor(shape=(2,3))},optimizer_state_dict=optimizer())
        for row in checkpoint["optimizer_state_dict"]["state"].values():row["step"]=Tensor(899661.0)
        info,_=module.optimizer_info(optimizer(),Torch)
        info["step_values"]=[784351.0]
        sigs={key:module.signature(checkpoint[key],Torch) for key in ("online_state_dict","target_state_dict")}
        prior=dict(schema="robotron-96M-checkpoint-lineage-v1",proposal_only=False,PASS=True,
            root_verification=dict(status="PASS"),checks=dict(CPU_only=True),candidate=dict(saved_metadata=previous,
            optimizer=info,state_dict_signatures=sigs),actual_recorded_batch_exposure=dict(since64M=[]))
        reference=dict(candidate=dict(prior["candidate"],sha256="a"*64))
        plan=dict(reference=dict(saved_clocks=previous,checkpoint=dict(path="fake64.pt")),
            additional_history=[dict(lineage_path="fake96.json",lineage_sha256="b"*64)])
        class Finite:
            def all(self):return self
            def item(self):return True
        fake=SimpleNamespace(is_tensor=Torch.is_tensor,isfinite=lambda value:Finite(),
            cuda=SimpleNamespace(is_initialized=lambda:False),__version__="fakeCPU",
            get_num_threads=lambda:2,get_num_interop_threads=lambda:1)
        controls=dict(experiment=module.EXPERIMENT,lr_scale=.5,epsilon_ramp=dict(start=.1,end=.1))
        config=dict(batch_size=4096,baseline_batch_size=512,n_step=3,max_samples_per_frame=8.0,c51_target_smoothing=0.0)
        class Evidence:
            def json(self,path):return controls if path.name=="learning_control.json" else dict(config=config)
            def bind_stat(self,*args):pass
            def snapshot(self):return []
        with tempfile.TemporaryDirectory() as directory,patch.object(Tensor,"is_floating_point",lambda value:True,create=True):
            candidate=Path(directory)/"fake128.pt";candidate.write_bytes(b"not a real checkpoint")
            before=contract.file_stat(candidate)
            gate=dict(tag="fresh3-128M",target=module.TARGET,experiment=module.EXPERIMENT,checkpoint=str(candidate))
            args=(fake,checkpoint,candidate,module.sha(candidate),before,gate,Path(directory)/"gate.json","c"*64,
                reference,prior,plan,Evidence(),"fixture",time.monotonic(),contract)
            report=module.proposed_report(*args)
            self.assertTrue(report["proposal_only"])
            self.assertEqual(report["actual_recorded_batch_exposure"]["totals"]["4096"]["logical_updates"],115310)
            with self.assertRaisesRegex(ValueError,"FINAL root-verified"):
                contract.lineage_identity(report,candidate,previous)
            checkpoint["optimized_samples"]+=2048
            with self.assertRaisesRegex(ValueError,"does not match recorded batch"):
                module.proposed_report(*args)
            checkpoint["optimized_samples"]-=2048
            for key in ("engine_version","state_size","single_frame_state_size","frame_stack"):
                original=checkpoint[key];checkpoint[key]+=1
                with self.subTest(header=key),self.assertRaisesRegex(ValueError,"architecture metadata differs"):
                    module.proposed_report(*args)
                checkpoint[key]=original
            checkpoint["frame_count"]=checkpoint["learner_frame_count"]-1
            with self.assertRaisesRegex(ValueError,"fleet clock is below learner"):
                module.proposed_report(*args)

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
