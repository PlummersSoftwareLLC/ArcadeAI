"""Small fake-only contracts; no Torch, actual checkpoint, gate or future data."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("root128_verifier_fixture", HERE / "root_verify128M_lineage.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def counters(pending=0):
    identity = dict(enabled=True, process_id=10, instance_monotonic_ns=20, epoch=1)
    total = dict(attempts_started=5+pending, outcomes_recorded=5, applied=4, amp_skipped=1, unavailable=0)
    sources = dict(dqn=7, epsilon=2, expert=1, eval=3, unattributed=0)
    snapshot = dict(ts=1.0, training_steps=100, optimized_samples=409600, learner_frame_count=20,
        host_pipeline=dict(learning_exposure=dict(
            optimizer=dict(identity, schema="robotron-optimizer-exposure-v1", epoch_reason="optimizer_restore_begin",
                supported_torch="2.13.0+cu130", available=pending==0, total=total, since_epoch=dict(total),
                unclassified_started_total=pending, prior_epoch_outcomes_total=0),
            replay=dict(identity, schema="robotron-replay-insert-exposure-v1", epoch_reason="directory_adopt_begin",
                available=True, accepted_total=13, accepted_since_epoch=13,
                accepted_learner_total=9, accepted_learner_since_epoch=9,
                accepted_by_source_total=sources, accepted_by_source_since_epoch=dict(sources)))))
    return snapshot, copy.deepcopy(snapshot["host_pipeline"]["learning_exposure"])


class Root128VerificationTests(unittest.TestCase):
    def test_Adam_moments_bind_to_actual_pinned_parameter_not_only_each_other(self):
        class Tensor:
            def __init__(self, shape=(2,3), dtype="float32"):
                self.shape,self.dtype=shape,dtype
        online=dict(support=Tensor(shape=(51,)), **{f"p{i}":Tensor(shape=(i+1,)) for i in range(99)})
        ids=list(range(99))
        states={i:dict(exp_avg=Tensor(shape=(i+1,)),exp_avg_sq=Tensor(shape=(i+1,))) for i in range(81)}
        module.check_moments(states,ids,online,list(online),lambda v:isinstance(v,Tensor))
        for broken in (dict(exp_avg=Tensor(shape=(4,)),exp_avg_sq=Tensor(shape=(4,))),
                dict(exp_avg=Tensor(shape=(1,),dtype="float16"),exp_avg_sq=Tensor(shape=(1,),dtype="float16"))):
            states[0]=broken
            with self.subTest(broken=broken),self.assertRaisesRegex(ValueError,"online parameter"):
                module.check_moments(states,ids,online,list(online),lambda v:isinstance(v,Tensor))

    def test_import_and_default_help_path_are_inert(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("future data opened")), \
                patch.object(Path, "open", side_effect=AssertionError("file opened")):
            spec = importlib.util.spec_from_file_location("inert_root128", HERE / "root_verify128M_lineage.py")
            loaded = importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded)
            with patch("sys.argv", ["root_verify128M_lineage.py"]), patch("builtins.print"):
                loaded.main()

    def test_missing_actual_SHAs_fail_before_any_evidence_or_Torch_import(self):
        args = SimpleNamespace(proposal_sha256="ROOT_FUTURE_SHA", checkpoint_sha256="ROOT_FUTURE_SHA")
        with patch.dict(module.os.environ, CUDA_VISIBLE_DEVICES=""), \
                patch.object(Path, "open", side_effect=AssertionError("checkpoint/evidence opened")), \
                self.assertRaisesRegex(ValueError, "Explicit actual64-hex"):
            module.verify(args)

    def test_output_whitelist_rejects_state_controls_other_runs_and_overwrite(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "HERE", Path(directory)/"proposal"):
            valid = Path(directory)/"fresh3-128M-checkpoint-lineage.json"
            self.assertEqual(module.output_path(valid), valid)
            for path in (Path(directory)/"state.json", Path(directory)/"learning_control.json",
                    Path(directory).parent/"fresh3-128M-checkpoint-lineage.json"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    module.output_path(path)
            valid.write_bytes(b"retained")
            with self.assertRaises(ValueError):
                module.output_path(valid)
            self.assertEqual(valid.read_bytes(), b"retained")

    def test_saved_logical_and_Adam_deltas_remain_distinct_and_strict(self):
        before = dict(training_steps=10, optimized_samples=1000, learner_frame_count=20)
        after = dict(training_steps=14, optimized_samples=1000+4*4096, learner_frame_count=21)
        result = module.interval(before, after, [8.], [11.], "fake", "default", True)
        self.assertEqual((result["logical_updates_delta"], result["Adam_uniform_step_delta"],
                          result["logical_minus_uniform_Adam_delta"]), (4, 3, 1))
        for broken, steps in ((dict(after, optimized_samples=after["optimized_samples"]+1), [11.]),
                (dict(after, training_steps=True), [11.]), (after, [float("inf")]), (after, [7.])):
            with self.subTest(broken=broken, steps=steps), self.assertRaises(ValueError):
                module.interval(before, broken, [8.], steps, "fake", "default", True)
        exposure = dict(since64M=[dict(recorded_batch_size=4096, logical_updates_delta=4,
            optimized_samples_delta=16384)], totals={"2048":dict(logical_updates=0,optimized_samples=0),
            "4096":dict(logical_updates=4,optimized_samples=16384)})
        module.check_exposures(exposure)
        exposure["totals"]["4096"]["optimized_samples"] += 1
        with self.assertRaisesRegex(ValueError, "totals differ"):
            module.check_exposures(exposure)

    def test_counter_snapshot_excludes_eval_and_accepts_only_one_pending(self):
        metadata = dict(training_steps=99, optimized_samples=405504, learner_frame_count=19)
        for pending in (0, 1):
            snapshot, baseline = counters(pending)
            result = module.counter_evidence(snapshot, baseline, metadata)
            self.assertEqual(result["counters"]["replay"]["accepted_learner_total"], 9)
            self.assertEqual(result["counters"]["replay"]["accepted_by_source_total"]["eval"], 3)
            self.assertIn("Not persisted", result["limitation"])
        changes = [lambda value:value["host_pipeline"]["learning_exposure"]["optimizer"].update(epoch=2),
            lambda value:value["host_pipeline"]["learning_exposure"]["optimizer"]["total"].update(unavailable=1),
            lambda value:value["host_pipeline"]["learning_exposure"]["optimizer"].update(unclassified_started_total=2),
            lambda value:value["host_pipeline"]["learning_exposure"]["replay"].update(accepted_learner_total=12),
            lambda value:value.update(training_steps=98)]
        for change in changes:
            snapshot, baseline = counters()
            change(snapshot)
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.counter_evidence(snapshot, baseline, metadata)

    def test_publication_never_overwrites_and_changed_evidence_cannot_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"new-lineage.json"
            class Evidence:
                def recheck(self):pass
            module.publish(output, {"fixture":True}, Evidence())
            original = output.read_bytes()
            self.assertEqual(json.loads(original), {"fixture":True})
            self.assertEqual(output.stat().st_mode & 0o777, 0o444)
            with self.assertRaises(FileExistsError):
                module.publish(output, {"fixture":False}, Evidence())
            self.assertEqual(output.read_bytes(), original)
            class Changed:
                def recheck(self):raise ValueError("receipt/proposal changed")
            rejected = Path(directory)/"rejected.json"
            with self.assertRaisesRegex(ValueError, "changed"):
                module.publish(rejected, {"fixture":True}, Changed())
            self.assertFalse(rejected.exists())
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_counter_totals_schema_version_and_epoch_reason_cannot_reset_silently(self):
        metadata = dict(training_steps=99, optimized_samples=405504, learner_frame_count=19)
        def reset_optimizer(value):
            opt=value["host_pipeline"]["learning_exposure"]["optimizer"]
            opt.update(available=False, total=dict.fromkeys(opt["total"],0), since_epoch=dict.fromkeys(opt["total"],0))
        def reset_replay(value):
            replay=value["host_pipeline"]["learning_exposure"]["replay"]
            sources=dict(replay["accepted_by_source_total"],dqn=6)
            replay.update(accepted_by_source_total=sources,accepted_by_source_since_epoch=dict(sources),
                accepted_total=12,accepted_since_epoch=12,accepted_learner_total=8,accepted_learner_since_epoch=8)
        changes=[reset_optimizer,reset_replay,
            lambda value:value["host_pipeline"]["learning_exposure"]["optimizer"].update(schema="future"),
            lambda value:value["host_pipeline"]["learning_exposure"]["replay"].update(epoch_reason="unknown_reset"),
            lambda value:value["host_pipeline"]["learning_exposure"]["optimizer"].update(supported_torch="future")]
        for change in changes:
            snapshot,baseline=counters()
            change(snapshot)
            with self.subTest(change=change),self.assertRaises(ValueError):
                module.counter_evidence(snapshot,baseline,metadata)


if __name__ == "__main__":
    unittest.main()
