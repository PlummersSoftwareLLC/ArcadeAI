"""UNEXECUTED source preparation. Run only after root releases quality freeze.

The future suite imports real copied replay/config/native modules and NumPy,
uses synthetic width8 storage and4096 draws, and never constructs an agent.
"""
import contextlib
import copy
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

try:
    from . import sampler_fixture as fixture
except ImportError:
    import sampler_fixture as fixture


class SamplerFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = None
        provided = os.environ.get("KL_SAMPLER_FIXTURE_OUTPUT")
        if provided:
            cls.work = Path(provided) / "private"
            cls.work.mkdir()
        else:
            cls.temporary = tempfile.TemporaryDirectory(prefix="robotron-kl-sampler-fixture-")
            cls.work = Path(cls.temporary.name)
        cls.base, cls.candidate = fixture.load_private_sources(cls.work)
        cls.np = sys.modules["numpy"]

    @classmethod
    def tearDownClass(cls):
        if cls.temporary is not None:
            cls.temporary.cleanup()

    def pair(self, scenario="default"):
        return (fixture.make_buffer(self.base, scenario),
                fixture.make_buffer(self.candidate, scenario))

    def assert_rng_equal(self, left, right):
        self.assertEqual(left[0], right[0])
        self.np.testing.assert_array_equal(left[1], right[1])
        self.assertEqual(left[2:], right[2:])

    def assert_batch_bytes_equal(self, left, right):
        self.assertEqual(len(left), 10)
        self.assertEqual(len(right), 10)
        for a, b in zip(left, right):
            self.assertEqual(a.dtype, b.dtype)
            self.assertEqual(a.shape, b.shape)
            self.assertEqual(a.tobytes(), b.tobytes())

    def draw_pair(self, scenario="default", *, traced=False, direct=False, beta=1.):
        left, right = self.pair(scenario)
        seed = fixture.SEED
        self.np.random.seed(seed)
        expected = left.sample(fixture.BATCH, beta=beta)
        expected_rng = self.np.random.get_state()
        self.np.random.seed(seed)
        if direct:
            outs = tuple(self.np.empty((fixture.BATCH, fixture.STATE_WIDTH), dtype=self.np.float32)
                         for _ in range(2))
        else:
            outs = None
        if traced:
            actual, metadata = right.sample_with_metadata(
                fixture.BATCH, beta=beta, capture_id="synthetic-" + scenario, _state_out=outs)
        else:
            metadata = None
            actual = right.sample_into(fixture.BATCH, *outs, beta=beta) if direct else right.sample(fixture.BATCH, beta=beta)
        actual_rng = self.np.random.get_state()
        self.assert_batch_bytes_equal(expected, actual)
        self.assert_rng_equal(expected_rng, actual_rng)
        return right, actual, metadata

    def test_default_off_exact_bytes_and_rng_for_all_scenarios(self):
        for scenario in ("default", "bank_shortfall", "interesting_shortfall", "stale_banks", "duplicates"):
            for beta in (.4, 1.):
                with self.subTest(scenario=scenario, beta=beta):
                    buffer, _, metadata = self.draw_pair(scenario, beta=beta)
                    self.assertIsNone(metadata)
                    self.assertFalse(any(name.startswith("_draw_trace") for name in vars(buffer)))

    def test_default_off_direct_fill_exact_bytes_and_rng(self):
        self.draw_pair(direct=True)

    def test_on_exact_bytes_rng_and_nominal_actual_4096_origins(self):
        _, batch, m = self.draw_pair(traced=True)
        counts = {name: stop-start for name, start, stop in m["origin_boundaries"]}
        self.assertEqual(counts, dict(per=901, interesting=737, recent=1434, hof=410, ephof=614))
        self.np.testing.assert_array_equal(m["indices"], batch[8])
        self.np.testing.assert_array_equal(m["supplied_weights_float32"], batch[9])
        fixture.OBSERVATIONS.append(dict(scenario="default", counts=counts, beta=m["beta"],
            per_weight_mean_float64=float(m["supplied_weights_float64"][:901].mean()),
            expected_unknowns=sorted(m["unknown"])))

    def test_actual_bank_and_interesting_shortfalls_reassign_to_ring_per(self):
        for scenario, expected in (
                ("bank_shortfall", dict(per=1925, interesting=737, recent=1434, hof=0, ephof=0)),
                ("interesting_shortfall", dict(per=1638, interesting=0, recent=1434, hof=410, ephof=614))):
            with self.subTest(scenario=scenario):
                _, _, m = self.draw_pair(scenario, traced=True)
                counts = {name: stop-start for name, start, stop in m["origin_boundaries"]}
                self.assertEqual(counts, expected)
                fixture.OBSERVATIONS.append(dict(scenario=scenario, counts=counts))

    def test_actual_bank_staleness_changes_quota_at_same_4096_size(self):
        _, batch, m = self.draw_pair("stale_banks", traced=True)
        counts = {name: stop-start for name, start, stop in m["origin_boundaries"]}
        self.assertEqual(counts, dict(per=1669, interesting=737, recent=1434, hof=102, ephof=154))
        self.assertEqual(len(batch[8]), 4096)
        self.assertEqual(m["banks"]["hof"]["quota_scale"], .25)
        self.assertEqual(m["banks"]["ephof"]["quota_scale"], .25)
        fixture.OBSERVATIONS.append(dict(scenario="stale_banks", counts=counts))

    def test_selected_leaf_float64_normalizer_and_bank_recoupling_reconstruct_emitted(self):
        for scenario in ("default", "bank_shortfall", "interesting_shortfall", "stale_banks"):
            with self.subTest(scenario=scenario):
                _, batch, m = self.draw_pair(scenario, traced=True, beta=.73)
                raw = (m["size"] * (self.np.maximum(m["per_raw_leaves"], 1e-10) / m["tree_total"])) ** (-m["beta"])
                self.np.testing.assert_array_equal(raw, m["per_raw_weights_float64"])
                per = raw / max(1e-12, float(raw.max()))
                expected = self.np.ones(4096, dtype=self.np.float64)
                expected[:len(per)] = per
                for name, start, stop in m["origin_boundaries"]:
                    if name in ("hof", "ephof"):
                        expected[start:stop] = per.mean()
                self.np.testing.assert_array_equal(expected, m["supplied_weights_float64"])
                self.np.testing.assert_array_equal(expected.astype(self.np.float32), batch[9])
                self.assertEqual(m["selected_per_min_clamped_leaf"], float(m["per_clamped_leaves"].min()))

    def test_duplicate_indices_do_not_erase_origin_boundaries_or_ordered_sample_rows(self):
        _, batch, m = self.draw_pair("duplicates", traced=True)
        boundaries = {name:(start, stop) for name,start,stop in m["origin_boundaries"]}
        for name in ("per", "interesting", "recent"):
            start, stop = boundaries[name]
            self.np.testing.assert_array_equal(batch[8][start:stop], self.np.full(stop-start, 136))
        self.assertLess(len(self.np.unique(batch[8])), len(batch[8]))
        self.assertEqual([name for name,_,_ in m["origin_boundaries"]],
                         ["per", "interesting", "recent", "hof", "ephof"])
        fixture.OBSERVATIONS.append(dict(scenario="duplicates",
            unique_indices=int(self.np.unique(batch[8]).size), ordered_rows=len(batch[8])))

    def test_metadata_is_detached_across_tree_ring_bank_writes_and_later_draw(self):
        buffer, _, m = self.draw_pair(traced=True)
        before = copy.deepcopy(m)
        buffer.tree.tree *= 2
        buffer.actions[:] = 80
        buffer.rewards[:] = 7
        buffer.hof_states[:] = 19
        buffer.hof_actions[:] = 1
        buffer._bank_revision["hof"] += 1
        buffer._bank_load_epoch["hof"] += 1
        buffer.sample_with_metadata(4096, capture_id="later")
        for name in ("indices", "ring_selected_raw_leaves", "per_raw_leaves",
                     "per_clamped_leaves", "per_raw_weights_float64",
                     "supplied_weights_float64", "supplied_weights_float32"):
            self.np.testing.assert_array_equal(m[name], before[name])
            self.assertFalse(m[name].flags.writeable)
        for name in m["small_batch_fields"]:
            self.np.testing.assert_array_equal(m["small_batch_fields"][name], before["small_batch_fields"][name])
            self.assertFalse(m["small_batch_fields"][name].flags.writeable)
        self.assertEqual(m["banks"]["hof"]["revision"], before["banks"]["hof"]["revision"])
        self.assertEqual(m["banks"]["hof"]["load_epoch"], before["banks"]["hof"]["load_epoch"])
        self.np.testing.assert_array_equal(m["banks"]["hof"]["selected_slots"], before["banks"]["hof"]["selected_slots"])

    def test_direct_state_reuse_does_not_alias_retained_small_metadata(self):
        buffer, batch, m = self.draw_pair(traced=True, direct=True)
        outs = (batch[0], batch[3])
        saved = m["small_batch_fields"]["actions"].copy()
        buffer.actions[:] = 80
        buffer.hof_actions[:] = buffer.ephof_actions[:] = 80
        buffer.sample_with_metadata(4096, capture_id="reuse-direct-slot", _state_out=outs)
        self.np.testing.assert_array_equal(m["small_batch_fields"]["actions"], saved)
        self.assertIn("full_states", m["unknown"])

    def test_empty_warmup_draw_and_invalid_capture_do_not_invent_ticket(self):
        buffer = fixture.make_buffer(self.candidate)
        buffer.size = 0
        rng = self.np.random.get_state()
        self.assertEqual(buffer.sample_with_metadata(4096, capture_id="empty"), (None, None))
        for size, identity in ((4097, "oversize"), (4096, ""), (True, "bool")):
            with self.assertRaises(ValueError):
                buffer.sample_with_metadata(size, capture_id=identity)
        self.assert_rng_equal(rng, self.np.random.get_state())

    def test_default_cli_never_reads_sources_imports_packages_or_creates_output(self):
        with mock.patch.object(fixture, "checked_source", side_effect=AssertionError("source read")), \
             mock.patch.object(fixture, "load_private_sources", side_effect=AssertionError("package import")), \
             mock.patch.object(Path, "mkdir", side_effect=AssertionError("output mutation")), \
             contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(fixture.main([]), 0)
        self.assertIn("PLAN_ONLY_UNEXECUTED", stream.getvalue())

    def test_no_torch_and_every_imported_package_source_stays_private(self):
        self.assertNotIn("torch", sys.modules)
        self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"], "")
        for name, module in list(sys.modules.items()):
            if name.startswith(("kl_fixture_base", "kl_fixture_candidate")):
                self.assertTrue(Path(module.__file__).resolve().is_relative_to(self.work.resolve()))


if __name__ == "__main__":
    unittest.main()
