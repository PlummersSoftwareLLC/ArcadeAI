"""Raw evidence integrity and unchanged real health checks; no live process actions."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

import raw_api_witness_v1 as wire

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME / 'logs/managed-learning-20261015/run-26'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class RawAPIWitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        path = RUN / ('confirmed-scoring-quality-original01-preparation-20261018/'
            'capacity32-confirmed1059-score-carry-v1-preparation-20261019/'
            'nonfinite-snapshot-terminal-readback-20261019/current-main-API.json')
        self.base = json.loads(path.read_bytes())
        self.health = module('_raw_test_actual_health', RUN /
            'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')
        self.review = module('_raw_test_actual_optimizer', GAME /
            'tools/eval_capacity_proposal/review_original_pilot_score_carry_v1.py')
        self.counter = 0

    def archive(self, raw):
        path = self.root / f'{self.counter:03d}.raw'
        self.counter += 1
        path.write_bytes(raw)
        path.chmod(0o444)
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))

    def read(self, pin):
        raw = Path(pin['path']).read_bytes()
        if len(raw) != pin['bytes'] or hashlib.sha256(raw).hexdigest() != pin['sha256']:
            raise ValueError('Original wire bytes changed')
        return raw

    def healthy(self, api):
        self.health.healthy(api, self.base, self.base['managed_experiment'], self.base['ts'])
        self.review.inspect_optimizer_observation(api['host_pipeline']['learning_exposure']['optimizer'])

    def accept(self, api):
        raw = json.dumps(api).encode()
        pin = self.archive(raw)  # Must precede parsing, health and metadata encoding.
        parsed = wire.parse_wire(raw)
        self.healthy(parsed)
        sample = wire.witness_fields(parsed, pin)
        wire.canonical(sample)
        return raw, sample, wire.rejoin_witness(sample, self.read)

    def test_finite_full_response_and_projection_rejoin_without_changes(self):
        raw, sample, api = self.accept(self.base)
        self.assertEqual(api, self.base)
        self.assertEqual(self.read(sample['API_wire']), raw)

    def test_nonfinite_diagnostic_floats_preserve_raw_bytes_and_actual_health(self):
        for value in (float('inf'), float('-inf'), float('nan')):
            with self.subTest(value=repr(value)):
                api = copy.deepcopy(self.base)
                api['grad_norm'] = value
                raw, sample, decoded = self.accept(api)
                self.assertEqual(self.read(sample['API_wire']), raw)
                self.assertTrue(any(x['path'] == ['grad_norm'] for x in sample['API_nonfinite_paths']))
                self.assertFalse(math.isfinite(decoded['grad_norm']))
                self.assertNotIn('grad_norm', sample['API'])

    def test_nested_noncritical_diagnostics_are_not_silently_discarded(self):
        api = copy.deepcopy(self.base)
        api['diagnostic'] = {'value': [float('inf'), float('nan')]}
        _, sample, decoded = self.accept(api)
        self.assertEqual(len([x for x in sample['API_nonfinite_paths'] if x['path'][0]=='diagnostic']), 2)
        self.assertTrue(math.isnan(decoded['diagnostic']['value'][1]))

    def test_nonfinite_critical_fields_still_fail_actual_health_after_raw_archive(self):
        for field, value in (('lr', float('inf')), ('ts', float('nan')),
                             ('pipeline_snapshot_age_s', float('inf'))):
            with self.subTest(field=field):
                api = copy.deepcopy(self.base)
                api[field] = value
                pin = self.archive(json.dumps(api).encode())
                with self.assertRaises(ValueError):
                    self.healthy(wire.parse_wire(self.read(pin)))
                self.assertTrue(Path(pin['path']).exists())

    def test_runtime_errors_and_optimizer_outcomes_still_fail(self):
        for change in ('pipeline', 'bank', 'unavailable', 'two_pending'):
            api = copy.deepcopy(self.base)
            api['grad_norm'] = float('inf')
            if change == 'pipeline': api['host_pipeline']['inference']['errors'] = 1
            elif change == 'bank': api['bank_persistence']['write_failures'] = 1
            elif change == 'unavailable':
                api['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable'] += 1
            else:
                api['host_pipeline']['learning_exposure']['optimizer']['total']['attempts_started'] += 2
            pin = self.archive(json.dumps(api).encode())
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.healthy(wire.parse_wire(self.read(pin)))

    def test_inflight_optimizer_semantics_remain_independent_of_storage(self):
        api = copy.deepcopy(self.base)
        optimizer = api['host_pipeline']['learning_exposure']['optimizer']
        for name in ('total', 'since_epoch'):
            optimizer[name]['attempts_started'] = optimizer[name]['outcomes_recorded'] + 1
        optimizer['available'] = False
        optimizer['unclassified_started_total'] = 1
        self.accept(api)

    def test_each_critical_projection_field_is_bound_to_original_bytes(self):
        _, sample, _ = self.accept(self.base)
        for field in wire.TOP_FIELDS:
            value = copy.deepcopy(sample)
            value['API'][field] = 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError):
                wire.rejoin_witness(value, self.read)

    def test_projection_type_substitution_is_rejected(self):
        _, sample, _ = self.accept(self.base)
        sample['API']['client_count'] = float(sample['API']['client_count'])
        with self.assertRaises(ValueError):
            wire.rejoin_witness(sample, self.read)

    def test_full_pipeline_exposure_and_bank_projection_are_bound(self):
        for field in ('host_pipeline', 'bank_persistence'):
            _, sample, _ = self.accept(self.base)
            sample['API'][field] = {}
            with self.subTest(field=field), self.assertRaises(ValueError):
                wire.rejoin_witness(sample, self.read)

    def test_wrong_raw_hash_or_missing_payload_rejects(self):
        _, sample, _ = self.accept(self.base)
        original = copy.deepcopy(sample)
        sample['API_wire']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            wire.rejoin_witness(sample, self.read)
        Path(original['API_wire']['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            wire.rejoin_witness(original, self.read)

    def test_hidden_or_changed_nonfinite_diagnostic_declarations_reject(self):
        api = copy.deepcopy(self.base)
        api['grad_norm'] = float('inf')
        _, sample, _ = self.accept(api)
        for value in ([], [dict(path=['grad_norm'], kind='nan')]):
            altered = copy.deepcopy(sample)
            altered['API_nonfinite_paths'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                wire.rejoin_witness(altered, self.read)

    def test_missing_format_and_wire_binding_reject(self):
        _, sample, _ = self.accept(self.base)
        for field in ('API_witness_format', 'API_wire'):
            altered = copy.deepcopy(sample)
            del altered[field]
            with self.subTest(field=field), self.assertRaises((KeyError, ValueError)):
                wire.rejoin_witness(altered, self.read)

    def test_invalid_json_duplicate_keys_and_nonobject_remain_archived(self):
        for raw in (b'{bad', b'{"x":1,"x":2}', b'[]', b'null', b''):
            pin = self.archive(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                wire.parse_wire(self.read(pin))
            self.assertEqual(self.read(pin), raw)

    def test_oversized_response_and_deep_diagnostics_reject(self):
        with self.assertRaises(ValueError):
            wire.parse_wire(b' ' * (wire.MAX_WIRE_BYTES + 1))
        value = float('inf')
        for _ in range(65): value = [value]
        with self.assertRaises(ValueError):
            wire.nonfinite_paths(value)


if __name__ == '__main__':
    unittest.main(verbosity=2)
