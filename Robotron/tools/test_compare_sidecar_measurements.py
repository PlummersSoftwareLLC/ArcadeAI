"""Reject backend drift before using frozen-game scores for policy decisions."""
import copy
import tempfile
from pathlib import Path
import unittest

from .compare_sidecar_measurements import compare_sidecars, sha256, validate_backend
from .test_compare_frozen_measurements import receipt


def sidecar(label):
    data = receipt(label)
    slots = list(range(4096, 4112))
    for index, row in enumerate(data["rows"]):
        row["client_slot"] = slots[index % len(slots)]
    data["boundary"]["actor_slots"] = slots
    data["job"] = dict(device="cuda", gpu_uuid="GPU-private", actors=16,
        actor_slots=slots, port=9999, cohort_s=60, timeout_s=180, wait_us=1000,
        epsilon=0, expert_ratio=0, difficulty=5, start_level=1, replay_enabled=False,
        fp16=False, mame="/test/mame", rompath="/test/roms", cpu_threads=2,
        boot_assets="/test/boot", inference_backend="inductor", inference_max_batch_size=16)
    data.update(inference_backend="inductor", numeric_policy=dict(
        autocast=False, weights="float32", inputs="float32", support="float32",
        compiled=True, backend="inductor", execution="torch.compile",
        suppress_errors=False, error_on_recompile=True,
        serving_thread_checked=True, warm_shapes=list(range(1, 17))),
        compile_report=dict(all_shapes_verified=list(range(1, 17)),
                            graph_state=dict(unique_graphs=2, graph_breaks=0, unimplemented=0)),
        runtime=dict(torch="test", gpu_name="test"), source_hashes=dict(source="test"),
        ended_source_hashes=dict(source="test"), checkpoint_sha256="a"*64,
        actor_timeout_logs={str(slot): 0 for slot in slots},
        actor_cleanup_timeout_logs={str(slot): 1 for slot in slots},
        boot_assets=dict(identity="boot", files={"nvram": {"sha256": "test"}}),
        boot_restores={str(slot): dict(identity="boot", files={"nvram": {"sha256": "test"}})
                       for slot in slots},
        socket_wait=dict(port=9999, wait_us=1000, sha256="wire",
                         actors={str(slot): dict(matching_activation=True) for slot in slots}))
    return data


class SidecarComparisonTests(unittest.TestCase):
    def test_matching_full_cohorts_pass_without_mutating_or_dropping_cleanup_evidence(self):
        base, candidate = sidecar("base"), sidecar("candidate")
        original = copy.deepcopy((base, candidate))
        report = compare_sidecars(base, candidate, iterations=100)
        self.assertTrue(report["backend_validated"])
        self.assertEqual(report["score_ratio"], 1)
        self.assertEqual((base, candidate), original)

    def test_backend_drift_rejected_even_when_game_protocol_matches(self):
        for field, value in (("gpu_uuid", "GPU-other"), ("wait_us", 500),
                             ("cohort_s", 120), ("cpu_threads", 4),
                             ("boot_assets", "/different/boot")):
            with self.subTest(field=field):
                candidate = sidecar("candidate")
                candidate["job"][field] = value
                with self.assertRaises(ValueError):
                    compare_sidecars(sidecar("base"), candidate, iterations=100)
        for field in ("runtime", "numeric_policy", "source_hashes"):
            with self.subTest(field=field):
                candidate = sidecar("candidate")
                candidate[field]["extra"] = True
                if field == "source_hashes":
                    candidate["ended_source_hashes"] = dict(candidate[field])
                with self.assertRaises(ValueError):
                    compare_sidecars(sidecar("base"), candidate, iterations=100)

    def test_partial_cohorts_and_runtime_errors_rejected(self):
        for field, value in (("pending", 1), ("abandoned", 1), ("complete", False),
                             ("server_error", "disconnect"), ("inference_error", "failed"),
                             ("cleanup_errors", ["unowned process remains"]),
                             ("invalidity_reasons", ["source_changed"])):
            with self.subTest(field=field):
                data = sidecar("bad")
                data[field] = value
                with self.assertRaises(ValueError):
                    validate_backend(data)
        data = sidecar("bad")
        data["actor_timeout_logs"]["4096"] = 1
        with self.assertRaisesRegex(ValueError, "runtime timeouts"):
            validate_backend(data)

    def test_source_mutation_and_silent_compile_fallback_rejected(self):
        for field, value in (("compiled", False), ("suppress_errors", True),
                             ("error_on_recompile", False), ("serving_thread_checked", False),
                             ("warm_shapes", [1, 16])):
            with self.subTest(field=field):
                data = sidecar("bad")
                data["numeric_policy"][field] = value
                with self.assertRaises(ValueError):
                    validate_backend(data)
        data = sidecar("bad")
        data["ended_source_hashes"]["source"] = "changed"
        with self.assertRaisesRegex(ValueError, "source changed"):
            validate_backend(data)

    def test_unknown_backend_and_missing_graph_or_boot_evidence_rejected(self):
        for mutation in (
                lambda d: d["job"].update(inference_backend="unknown"),
                lambda d: d["numeric_policy"].update(backend="eager"),
                lambda d: d["numeric_policy"].update(execution="eager"),
                lambda d: d["compile_report"]["graph_state"].pop("unique_graphs"),
                lambda d: d["compile_report"]["graph_state"].update(unique_graphs=0),
                lambda d: d["boot_assets"].update(files=None)):
            data = sidecar("bad")
            mutation(data)
            with self.assertRaises(ValueError):
                validate_backend(data)

    def test_boot_and_wire_evidence_must_cover_every_actor(self):
        for mutation in (
                lambda d: d["boot_restores"].pop("4096"),
                lambda d: d["boot_restores"]["4096"].update(identity="other"),
                lambda d: d["socket_wait"]["actors"]["4096"].update(matching_activation=False),
                lambda d: d["socket_wait"]["actors"].pop("4096")):
            data = sidecar("bad")
            mutation(data)
            with self.assertRaises(ValueError):
                validate_backend(data)

    def test_overlap_is_rejected_as_a_replication(self):
        data = sidecar("same")
        with self.assertRaisesRegex(ValueError, "overlap"):
            compare_sidecars(data, copy.deepcopy(data), iterations=100)

    def test_optional_checkpoint_readback_detects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.pt"
            path.write_bytes(b"fixture")
            data = sidecar("base")
            data.update(checkpoint_path=str(path), checkpoint_sha256=sha256(path))
            validate_backend(data, verify_checkpoint=True)
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checkpoint copy"):
                validate_backend(data, verify_checkpoint=True)


if __name__ == "__main__":
    unittest.main()
