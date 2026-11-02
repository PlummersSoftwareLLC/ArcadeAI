import unittest

from .check_frozen_profile_cpu_v2 import canonical


class ProfileMetadataTests(unittest.TestCase):
    def test_JSON_tuple_roundtrip_keeps_same_metadata(self):
        self.assertEqual(canonical(dict(clock=123, defaulted=())),
                         canonical(dict(clock=123, defaulted=[])))

    def test_real_clock_policy_and_type_changes_are_rejected(self):
        baseline = canonical(dict(clock=123, defaulted=[], autocast=False))
        for value in [dict(clock=124,defaulted=[],autocast=False),
                      dict(clock=123,defaulted=[],autocast=True),
                      dict(clock=True,defaulted=[],autocast=False),
                      dict(clock=123,defaulted=['state_size'],autocast=False)]:
            self.assertNotEqual(baseline,canonical(value))

    def test_nonfinite_values_cannot_be_normalized(self):
        with self.assertRaises(ValueError):
            canonical(dict(clock=float('nan')))


if __name__ == '__main__':
    unittest.main()
