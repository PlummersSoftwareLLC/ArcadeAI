"""CPU-only exposure counter contracts; no Torch, model or replay imports.

ReplayInsertExposure's caller reports only successfully completed ring adds.
These tests exercise its accounting/epoch API; replay integration tests verify
the call placement separately. Device-shaped fakes forbid all data access.
"""
from collections import defaultdict
from types import SimpleNamespace
import threading
import unittest

try:
    from . import learning_exposure as exposure
except ImportError:
    import learning_exposure as exposure


class Device:
    def __init__(self, index=0, kind="cuda"):
        self.index, self.type = index, kind

    def __eq__(self, other):
        return isinstance(other, Device) and (self.type, self.index) == (other.type, other.index)

    def __hash__(self):
        return hash((self.type, self.index))


class DeviceScalar:
    ndim = 0
    dtype = "torch.float32"
    requires_grad = False

    def __init__(self, device=None):
        self.device = device or Device()

    def forbidden(self, *args, **kwargs):
        raise AssertionError("Exposure inspection must never access device data")

    __float__ = item = cpu = to = clone = detach = sum = forbidden


class Adam:
    def __init__(self):
        self.param_groups = [{"fused": True}]
        self._step_supports_amp_scaling = True

    def step(self):
        raise AssertionError("Exposure inspection must never call the optimizer")


class Scaler:
    def __init__(self, optimizer, tensor):
        def unexpected_state_creation():
            raise AssertionError("Exposure inspection must not create optimizer state")
        self._enabled = True
        self._per_optimizer_states = defaultdict(unexpected_state_creation)
        self._per_optimizer_states[id(optimizer)] = {
            "stage": SimpleNamespace(name="UNSCALED"),
            "found_inf_per_device": {tensor.device: tensor},
        }


def capture(scaler, optimizer, *, device=None, version=None):
    return exposure.capture_amp_found_inf(
        scaler, optimizer, device or Device(),
        is_tensor=lambda value: isinstance(value, DeviceScalar),
        adam_type=Adam, scaler_type=Scaler,
        torch_version=exposure.SUPPORTED_TORCH if version is None else version,
    )


class LearningExposureTests(unittest.TestCase):
    def test_default_disabled_and_explicit_enable(self):
        for value in (None, "", "0", "false", "garbage"):
            environment = {} if value is None else {"DQN_LEARNING_EXPOSURE_COUNTERS": value}
            self.assertFalse(exposure.exposure_enabled(environment))
        for value in ("1", "true", "YES", " on "):
            self.assertTrue(exposure.exposure_enabled({"DQN_LEARNING_EXPOSURE_COUNTERS": value}))
        snapshot = exposure.disabled_snapshot()
        self.assertFalse(snapshot["enabled"])
        self.assertFalse(snapshot["available"])

    def test_completed_learner_rows_exclude_expert_eval_and_unknown_sources(self):
        counter = exposure.ReplayInsertExposure()
        # Reported completions include overwritten rows, not just resident rows.
        for source, expert, kind in (
            ("dqn", 0, 0), ("epsilon", 0, 1), ("expert", 1, 2),
            ("eval", 0, 0), (None, 0, 0), ("unknown", 0, 0),
            ("dqn", 0, 1), ("epsilon", 0, 0), ("dqn", 1, 0),
            ("dqn", 0, 0),
        ):
            counter.accepted(source, expert, kind)
        snapshot = counter.snapshot()
        self.assertEqual(snapshot["accepted_total"], 10)
        self.assertEqual(snapshot["accepted_learner_total"], 3)
        self.assertEqual(snapshot["accepted_by_source_total"], {
            "dqn": 2, "epsilon": 1, "expert": 2, "eval": 1, "unattributed": 4,
        })
        # Mere observation/import does not report a new completed add.
        self.assertEqual(counter.snapshot()["accepted_total"], 10)
        snapshot["accepted_by_source_total"]["dqn"] = 999
        self.assertEqual(counter.snapshot()["accepted_by_source_total"]["dqn"], 2)

    def test_clear_and_load_epochs_invalidate_burnin_without_erasing_process_totals(self):
        counter = exposure.ReplayInsertExposure()
        counter.accepted("dqn", 0, 0)
        baseline = counter.snapshot()
        for epoch, reason in enumerate(("clear_begin", "directory_adopt_begin", "array_restore_begin", "flush_begin"), 1):
            counter.new_epoch(reason)
            snapshot = counter.snapshot()
            self.assertEqual(snapshot["epoch"], epoch)
            self.assertEqual(snapshot["epoch_reason"], reason)
            self.assertEqual(snapshot["accepted_learner_since_epoch"], 0)
            self.assertEqual(snapshot["accepted_learner_total"], epoch)
            self.assertEqual(snapshot["instance_monotonic_ns"], baseline["instance_monotonic_ns"])
            counter.accepted("epsilon", 0, 1)
            self.assertEqual(counter.snapshot()["accepted_learner_since_epoch"], 1)
        self.assertEqual(counter.snapshot()["accepted_learner_total"], 5)

    def test_capture_retains_existing_scalar_without_mutation_or_device_read(self):
        optimizer, scalar = Adam(), DeviceScalar()
        scaler = Scaler(optimizer, scalar)
        registry = scaler._per_optimizer_states
        state = registry[id(optimizer)]
        found = state["found_inf_per_device"]
        result, mode = capture(scaler, optimizer)
        self.assertIs(result, scalar)
        self.assertEqual(mode, "single_cuda_found_inf")
        self.assertIs(scaler._per_optimizer_states, registry)
        self.assertIs(registry[id(optimizer)], state)
        self.assertIs(state["found_inf_per_device"], found)
        self.assertEqual(list(found), [scalar.device])
        # The existing registry can be replaced by scaler.update; retention
        # must still hold without cloning or inspecting the device scalar.
        scaler._per_optimizer_states = {}
        self.assertIs(result, scalar)

    def test_unsupported_optimizer_scaler_and_version_are_unavailable(self):
        optimizer, scalar = Adam(), DeviceScalar()
        scaler = Scaler(optimizer, scalar)
        self.assertEqual(capture(scaler, optimizer, version="future-version"), (None, "unsupported_torch"))
        optimizer.param_groups[0]["fused"] = False
        self.assertEqual(capture(scaler, optimizer), (None, "unsupported_optimizer"))
        optimizer.param_groups[0]["fused"] = True
        optimizer._step_supports_amp_scaling = False
        self.assertEqual(capture(scaler, optimizer), (None, "unsupported_optimizer"))
        optimizer._step_supports_amp_scaling = True
        optimizer.step = lambda: None
        self.assertEqual(capture(scaler, optimizer), (None, "unsupported_optimizer"))
        optimizer = Adam()
        class OtherScaler(Scaler):
            pass
        self.assertEqual(capture(OtherScaler(optimizer, scalar), optimizer), (None, "unsupported_scaler"))

    def test_missing_multiple_or_wrong_stage_state_has_no_side_effects(self):
        changes = (
            lambda scaler, optimizer: scaler._per_optimizer_states.clear(),
            lambda scaler, optimizer: scaler._per_optimizer_states.update({123: {}}),
            lambda scaler, optimizer: scaler._per_optimizer_states[id(optimizer)].update(stage=SimpleNamespace(name="STEPPED")),
            lambda scaler, optimizer: scaler._per_optimizer_states[id(optimizer)].update(found_inf_per_device={}),
            lambda scaler, optimizer: scaler._per_optimizer_states[id(optimizer)]["found_inf_per_device"].update({Device(1): DeviceScalar(Device(1))}),
        )
        for change in changes:
            optimizer, scalar = Adam(), DeviceScalar()
            scaler = Scaler(optimizer, scalar)
            change(scaler, optimizer)
            registry = scaler._per_optimizer_states
            keys = list(registry)
            with self.subTest(change=change):
                value, mode = capture(scaler, optimizer)
                self.assertIsNone(value)
                self.assertNotEqual(mode, "single_cuda_found_inf")
                self.assertIs(scaler._per_optimizer_states, registry)
                self.assertEqual(list(registry), keys)

    def test_malformed_scalar_metadata_is_unavailable_without_data_access(self):
        changes = (
            lambda scalar: setattr(scalar, "ndim", 1),
            lambda scalar: setattr(scalar, "dtype", "torch.float16"),
            lambda scalar: setattr(scalar, "requires_grad", True),
            lambda scalar: setattr(scalar, "device", Device(0, "cpu")),
            lambda scalar: setattr(scalar, "device", Device(1)),
        )
        for change in changes:
            optimizer, scalar = Adam(), DeviceScalar()
            scaler = Scaler(optimizer, scalar)
            change(scalar)
            with self.subTest(change=change):
                self.assertEqual(capture(scaler, optimizer), (None, "malformed_inf_tensor"))
        optimizer, scalar = Adam(), DeviceScalar()
        scaler = Scaler(optimizer, scalar)
        scaler._enabled = False
        self.assertEqual(capture(scaler, optimizer), (None, "scaler_disabled"))

    def test_finite_overflow_and_direct_outcomes_are_distinct_from_logical_steps(self):
        counter = exposure.OptimizerExposure()
        for value in (0., 1., 0.):
            counter.finish(counter.begin(), "single_cuda_found_inf", value)
        counter.finish(counter.begin(), "unscaled")
        counter.finish(counter.begin(), "scaler_disabled")
        snapshot = counter.snapshot()
        self.assertEqual(snapshot["total"], {
            "attempts_started": 5, "outcomes_recorded": 5,
            "applied": 4, "amp_skipped": 1, "unavailable": 0,
        })
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["unclassified_started_total"], 0)

    def test_invalid_host_values_exceptions_and_missing_metadata_are_explicit(self):
        counter = exposure.OptimizerExposure()
        for value in (float("nan"), float("inf"), -1, 2, None, True, "0", DeviceScalar()):
            counter.finish(counter.begin(), "single_cuda_found_inf", value)
        for mode in ("unsupported_torch", "missing_scaler_state", "optimizer_exception", "readback_exception"):
            counter.finish(counter.begin(), mode)
        snapshot = counter.snapshot()
        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["total"]["unavailable"], 12)
        self.assertEqual(snapshot["total"]["applied"], 0)
        self.assertEqual(snapshot["total"]["amp_skipped"], 0)

    def test_inflight_and_straddled_outcomes_cannot_certify_a_new_epoch(self):
        counter = exposure.OptimizerExposure()
        counter.finish(counter.begin(), "unscaled")
        old = counter.begin()
        self.assertFalse(counter.snapshot()["available"])
        self.assertEqual(counter.snapshot()["unclassified_started_total"], 1)
        counter.new_epoch("optimizer_restore_begin")
        counter.finish(old, "single_cuda_found_inf", 1.)
        snapshot = counter.snapshot()
        self.assertEqual(snapshot["since_epoch"]["outcomes_recorded"], 0)
        self.assertEqual(snapshot["prior_epoch_outcomes_total"], 1)
        self.assertFalse(snapshot["available"])
        counter.finish(counter.begin(), "unscaled")
        snapshot = counter.snapshot()
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["total"]["attempts_started"], 3)
        self.assertEqual(snapshot["since_epoch"]["attempts_started"], 1)
        self.assertEqual(snapshot["since_epoch"]["applied"], 1)

    def test_duplicate_foreign_tickets_and_mutated_snapshots_do_not_change_counts(self):
        counter = exposure.OptimizerExposure()
        ticket = counter.begin()
        other = exposure.OptimizerExposure()
        other.finish(ticket, "unscaled")
        self.assertEqual(other.snapshot()["total"]["outcomes_recorded"], 0)
        counter.finish(ticket, "unscaled")
        counter.finish(ticket, "unscaled")
        snapshot = counter.snapshot()
        self.assertEqual(snapshot["total"]["applied"], 1)
        snapshot["total"]["applied"] = 999
        snapshot["since_epoch"]["applied"] = 999
        self.assertEqual(counter.snapshot()["total"]["applied"], 1)
        self.assertEqual(counter.snapshot()["since_epoch"]["applied"], 1)

    def test_concurrent_readers_and_completions_leave_exact_bounded_totals(self):
        counter = exposure.OptimizerExposure()
        errors = []
        def writer():
            try:
                for value in (0., 1.) * 100:
                    counter.finish(counter.begin(), "single_cuda_found_inf", value)
                    snapshot = counter.snapshot()
                    self.assertLessEqual(snapshot["total"]["outcomes_recorded"], snapshot["total"]["attempts_started"])
            except BaseException as error:
                errors.append(error)
        threads = [threading.Thread(target=writer) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        snapshot = counter.snapshot()
        self.assertEqual(snapshot["total"]["outcomes_recorded"], 400)
        self.assertEqual(snapshot["total"]["applied"], 200)
        self.assertEqual(snapshot["total"]["amp_skipped"], 200)
        self.assertTrue(snapshot["available"])


if __name__ == "__main__":
    unittest.main()
