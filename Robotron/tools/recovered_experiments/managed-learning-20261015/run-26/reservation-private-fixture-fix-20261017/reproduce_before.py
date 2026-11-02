"""Stdlib/mock-only reproduction with returned failure context preserved."""
import json
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, '/home/dave/source/repos/ArcadeAI')
from Robotron.tools.inference_cpu_reservation_proposal import test_cpu_reservation_trial as tests

original = tests.trial.run_trial


def observed(*args, **kwargs):
    result = original(*args, **kwargs)
    print(json.dumps(dict(state=result.get('state'), error=result.get('error'),
                          traceback=result.get('traceback'),
                          restoration=result.get('restoration'),
                          status_publication_error=result.get('status_publication_error'))), flush=True)
    return result


names = [
    'test_full_fresh_trial_durably_precommits_all_originals_before_writes',
    'test_final_status_failure_cannot_leave_qualified_decision',
]
suite = unittest.TestSuite(tests.ReservationSafetyTests(name) for name in names)
with patch.object(tests.trial, 'run_trial', side_effect=observed):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
