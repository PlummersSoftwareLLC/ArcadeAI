"""Run private journal tests plus unchanged legacy test bodies; no runtime action."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    directory=Path(__file__).resolve().parent
    root=directory.parents[1]
    original_tests=root/'Scripts/dqn/test_game_journal.py'
    before=original_tests.read_bytes()
    old=b'from .game_journal import GameJournal'
    new=b'from game_journal_candidate import GameJournal'
    if before.count(old)!=1 or new in before:raise ValueError('Original legacy import boundary differs')
    effective=before.replace(old,new)
    if effective.replace(new,old)!=before:raise ValueError('Legacy test bodies changed')
    sys.path.insert(0,str(directory))
    legacy=types.ModuleType('_private_confirmed_legacy_tests')
    legacy.__file__=str(original_tests)
    exec(compile(effective,str(original_tests),'exec'),legacy.__dict__)
    import test_confirmed_boundaries as confirmed
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(legacy),
        unittest.defaultTestLoader.loadTestsFromModule(confirmed)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if any(n=='torch' or n.startswith('torch.') or n=='numpy' or n.startswith('dqn') for n in sys.modules):
        raise ValueError('Private stdlib journal tests unexpectedly imported numerical/training modules')
    evidence=json.loads(confirmed.EVIDENCE.read_text())
    report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),legacy_bodies_byte_identical=True,
        original_legacy_test_sha256=hashlib.sha256(before).hexdigest(),legacy_import_only_specialization=True,
        observed_terminal_prefix_cases=len(evidence['links']),
        case_scope='142 observed terminal-score/later-baseline pairs with a minimal synthetic lifecycle; not full original wire replay or actual emulator validation.',
        candidate_source_sha256=hashlib.sha256((directory/'game_journal_candidate.py').read_bytes()).hexdigest(),
        numerical_modules_imported=False,installed_source_changed=False,actual_MAME_or_GPU=False,
        qualification=False,promotion=False)
    with args.output.open('x') as stream:
        json.dump(report,stream,indent=2);stream.write('\n');stream.flush()
        os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(report,indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
