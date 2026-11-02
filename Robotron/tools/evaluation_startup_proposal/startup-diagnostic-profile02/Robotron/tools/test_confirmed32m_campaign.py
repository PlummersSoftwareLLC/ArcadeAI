"""CPU preparation tests; no real campaign build, pending receipt or protection."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "logs/managed-learning-20261015/run-08/build_confirmed32M_campaign.py"
spec = importlib.util.spec_from_file_location("prepared_confirmed32m_campaign", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def rows(label, score, count=64):
    return [dict(score=score, client_slot=module.SLOTS[i % 16], duration_s=1,
                 playable_frames=100, journal_game_id=f"{label}:{i}") for i in range(count)]


class Confirmed32MPreparationTests(unittest.TestCase):
    def test_each_leg_gate_cannot_be_rescued_by_strong_pooled_mean(self):
        weak, strong = rows("weak", 104), rows("strong", 500)
        self.assertGreater(module.summarize_rows(weak+strong, ["weak", "strong"])["mean"], 105)
        with self.assertRaisesRegex(ValueError, "gain gate rejected"):
            module.gain_gate(rows("ref", 100), dict(weak=weak, strong=strong))

    def test_high_mean_with_lower_median_is_rejected_and_exact_boundary_passes(self):
        bad = rows("bad", 99)
        bad[-1]["score"] = 10000
        with self.assertRaisesRegex(ValueError, "median_at_least_reference.*false"):
            module.gain_gate(rows("ref", 100), dict(bad=bad, good=rows("good", 110)))
        result = module.gain_gate(rows("ref", 100), dict(first=rows("a", 105), confirm=rows("b", 110)))
        self.assertTrue(result["passed"])
        with self.assertRaises(ValueError):
            module.gain_gate(rows("ref", 100), dict(first=rows("a", 110)))

    def test_pools_weight_rows_and_are_not_synthetic_valid_receipts(self):
        reference, first, second = rows("ref", 100), rows("a", 120), rows("b", 140, 128)
        original = copy.deepcopy((reference, first, second))
        with patch.object(module, "validate_receipt", side_effect=AssertionError("No pooled receipt")), \
             patch.object(module, "compare_sidecars", side_effect=AssertionError("No pooled receipt")):
            result = module.compare_rows(reference, first+second, ["ref"], ["a", "b"], iterations=100)
        self.assertEqual(result["candidate"]["count"], 192)
        self.assertAlmostEqual(result["candidate"]["mean"], 400/3)
        self.assertEqual(result["candidate"]["median"], 140)
        self.assertAlmostEqual(result["mean_ratio"], 4/3)
        self.assertEqual(result["slots_with_positive_mean_contrast"], 16)
        self.assertEqual(result["paired_slot_bootstrap"]["method"], "paired actor-slot clusters")
        for value in result["paired_slot_bootstrap"]["mean_ratio_ci"]:
            self.assertAlmostEqual(value, 4/3)
        self.assertNotIn("valid", result)
        self.assertNotIn("complete", result)
        self.assertEqual((reference, first, second), original)

    def test_global_overlap_including_historical_games_rejects(self):
        self.assertEqual(set(module.verify_disjoint(dict(a={"a"}, b={"b"})).values()), {0})
        with self.assertRaisesRegex(ValueError, "overlap.*historical"):
            module.verify_disjoint(dict(candidate={"shared"}, historical={"shared"}))

    def test_new_publication_is_independent_readonly_and_idempotent_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory)/"source.pt", Path(directory)/"protected.pt"
            source.write_bytes(b"isolated synthetic checkpoint")
            metadata = dict(utc="first", sha256=module.digest(source), marker=["all real receipts required by caller"])
            before = source.stat(), source.read_bytes()
            first = module.protect_checkpoint(source, destination, metadata)
            self.assertNotEqual(source.stat().st_ino, destination.stat().st_ino)
            self.assertEqual(destination.stat().st_nlink, 1)
            self.assertFalse(destination.stat().st_mode & 0o222)
            meta_path = destination.with_suffix(".pt.json")
            self.assertFalse(meta_path.stat().st_mode & 0o222)
            saved_bytes = meta_path.read_bytes()
            second = module.protect_checkpoint(source, destination, dict(metadata, utc="later"))
            self.assertEqual(first, second)
            self.assertEqual(meta_path.read_bytes(), saved_bytes)
            self.assertEqual(source.read_bytes(), before[1])
            self.assertEqual(source.stat().st_mode, before[0].st_mode)
            with self.assertRaisesRegex(ValueError, "metadata differs"):
                module.protect_checkpoint(source, destination, dict(metadata, marker=["changed"]))
            self.assertEqual(meta_path.read_bytes(), saved_bytes)

    def test_mismatch_partial_pair_and_symlink_fail_without_replacing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory)/"source.pt", Path(directory)/"protected.pt"
            source.write_bytes(b"fixture")
            with self.assertRaisesRegex(ValueError, "Identity changed"):
                module.protect_checkpoint(source, destination, dict(sha256="0"*64))
            self.assertFalse(destination.exists())
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["source.pt"])
            destination.write_bytes(b"previous evidence")
            with self.assertRaisesRegex(ValueError, "Partial existing"):
                module.protect_checkpoint(source, destination, dict(sha256=module.digest(source)))
            self.assertEqual(destination.read_bytes(), b"previous evidence")
            alias = Path(directory)/"alias.pt"
            alias.symlink_to(source)
            with self.assertRaisesRegex(ValueError, "Identity changed"):
                module.verify_hash(alias, module.digest(source))

    def test_atomic_publish_refuses_existing_file_and_cleans_temporaries(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/"published.json"
            target.write_bytes(b"immutable evidence")
            with self.assertRaises(FileExistsError):
                module.publish_json(target, dict(new="wrong"))
            self.assertEqual(target.read_bytes(), b"immutable evidence")
            self.assertEqual(list(Path(directory).iterdir()), [target])
            target.unlink()
            with self.assertRaisesRegex(OSError, "injected"):
                module.publish_file(target, lambda stream: (_ for _ in ()).throw(OSError("injected")))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_source_mutation_during_copy_cannot_publish_protected_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory)/"source.pt", Path(directory)/"protected.pt"
            source.write_bytes(b"original bytes")
            metadata = dict(sha256=module.digest(source))
            original_publish = module.publish_file
            def mutate_before_copy(path, writer, **kwargs):
                def changed_writer(stream):
                    source.write_bytes(b"changed source")
                    return writer(stream)
                return original_publish(path, changed_writer, **kwargs)
            with patch.object(module, "publish_file", side_effect=mutate_before_copy), \
                 patch.object(module, "publish_json", side_effect=AssertionError("No metadata publication")):
                with self.assertRaisesRegex(ValueError, "Copied checkpoint identity differs"):
                    module.protect_checkpoint(source, destination, metadata)
            self.assertFalse(destination.exists())
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["source.pt"])

    def test_cli_import_and_help_do_not_invoke_campaign_or_protect(self):
        with patch.object(module, "build_campaign", side_effect=AssertionError("Pending builder must not execute")), \
             patch.object(module, "protect_checkpoint", side_effect=AssertionError("No live protection")):
            with self.assertRaises(SystemExit) as caught:
                module.main(["--help"])
            self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
