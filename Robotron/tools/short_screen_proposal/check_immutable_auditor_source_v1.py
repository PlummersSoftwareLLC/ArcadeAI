"""Regression for the exact independent reader's immutable source contract.

No game receipts are reviewed, reclassified, or repaired. No GPU/MAME work.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if not a.execute:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    h = load('_immutable_source_regression_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    case = B / 'short15-protectedb231-vs-stopped77f9-original01-20261101'
    prepared = json.loads(h.checked(h.pin(case / 'prepared-with-review.json')).read_bytes())
    original = prepared['horizon_checkpoint_auditor']
    raw = h.checked(original).read_bytes()
    reader = load('_immutable_source_regression_actual_reader', h.checked(prepared['independent_review']['reader']))
    checks = []

    def check(name, value):
        assert value, name
        checks.append(name)

    def rejects(name, entry):
        try:
            reader.read_pin(entry, as_json=False)
        except (ValueError, RuntimeError):
            checks.append(name)
            return
        raise AssertionError('Unsafe source accepted: ' + name)

    check('original shared source remains exactly unchanged', h.pin(original['path']) == original)
    check('exact failed source still mode0664', original['identity']['mode'] == '0o664')
    rejects('actual review reader reproduces original mutable-source rejection', original)
    assert a.output.is_absolute() and not a.output.exists()
    a.output.mkdir(mode=0o700)
    target = a.output / 'audit_horizon_checkpoint_exact_copy.py'
    with target.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    frozen = h.pin(target)
    check('snapshot bytes and SHA exactly equal original', frozen['sha256'] == original['sha256'] and frozen['bytes'] == original['bytes'])
    check('separate owned readonly single-link file', frozen['identity']['mode'] == '0o444'
        and frozen['identity']['uid'] == os.getuid() and frozen['identity']['nlink'] == 1
        and (frozen['identity']['device'], frozen['identity']['inode']) != (original['identity']['device'], original['identity']['inode']))
    check('actual independent reader accepts selected readonly source', reader.read_pin(frozen, as_json=False) == raw)
    check('complete auditor AST unchanged', ast.dump(ast.parse(target.read_text())) == ast.dump(ast.parse(raw)))
    module = load('_immutable_source_regression_frozen_auditor', target)
    check('expected real pure auditor callable', callable(module.audit_checkpoint))
    bad = copy.deepcopy(frozen); bad['sha256'] = '0' * 64
    rejects('reject incorrect frozen source SHA', bad)
    bad = copy.deepcopy(frozen); bad['identity']['nlink'] = 2
    rejects('reject mismatched source link identity', bad)
    link = a.output / 'symlink-source.py'
    link.symlink_to(target)
    bad = copy.deepcopy(frozen); bad['path'] = str(link)
    rejects('reject source symlink', bad)
    other = a.output / 'hardlink-fixture-source.py'
    with other.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    other_pin = h.pin(other)
    os.link(other, a.output / 'hardlink-fixture-alias.py')
    rejects('reject changed actual source hardlink count', other_pin)
    builder_path = G / 'tools/short_screen_proposal/prepare_current_frozen_screen_v2.py'
    builder = builder_path.read_text()
    check('future builder selects private readonly snapshot',
        "checkpoint_auditor=save('horizon_checkpoint_auditor',checkpoint_parent,h.checked(checkpoint_parent).read_text())" in builder
        and 'horizon_checkpoint_auditor=checkpoint_auditor)' in builder
        and "checkpoint_auditor['identity']['mode']=='0o444'" in builder)
    preflight_path = G / 'tools/short_screen_proposal/check_current_screen_preflight_v2.py'
    preflight = preflight_path.read_text()
    check('future preflight uses actual strict reader before native contexts',
        'reader.read_pin(selected_source,as_json=False)' in preflight
        and preflight.index('reader.read_pin(selected_source,as_json=False)') < preflight.index('native.validate_completed_context(job, h)'))
    check('original shared source still untouched after all fixtures', h.pin(original['path']) == original)
    check('no numerical runtime imported', 'torch' not in sys.modules and 'numpy' not in sys.modules)
    report = h.put(a.output / 'report.json', dict(
        status='PASS_IMMUTABLE_AUDITOR_SOURCE_READER_REGRESSION_ONLY', tests_run=len(checks), checks=checks,
        exact_failed_source_pin=original, private_byte_identical_readonly_source=frozen,
        actual_reader=prepared['independent_review']['reader'], future_builder=h.pin(builder_path),
        future_preflight=h.pin(preflight_path), source=h.pin(Path(__file__)),
        failed_scientific_case_reclassified=False, original_game_or_score_receipts_read=False,
        selected_original_review_replaced=False, shared_source_chmod_or_write=False,
        live_future_scientific_case_qualified=False, promotion=False))
    print(json.dumps(dict(status='PASS_IMMUTABLE_AUDITOR_SOURCE_READER_REGRESSION_ONLY', tests_run=len(checks),
        report={k: report[k] for k in ('path', 'sha256', 'bytes')})))


if __name__ == '__main__':
    main()
