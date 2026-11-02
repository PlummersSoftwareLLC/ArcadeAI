#!/usr/bin/env python3
"""Explicit actual-source override for unchanged historical exposure fixtures.

Default: print the plan only. --run verifies the reviewed actual source pins,
then runs all 13 original fixtures with the installed helper. An explicit flag
also adds the proposed durable helper tests. No Torch/model/replay import; replay/agent integration
fixtures execute bounded selected methods extracted from actual source.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest


HERE = Path(__file__).resolve().parent
EXPECTED = {
    "agent.py": "28977d6b925a4606a61b76438595f45ae054fc81aaaad989ab93e00d98a05668",
    "replay_buffer.py": "28556797d15e0acf9387030b87f9ccce0b18e1e3cfa629b63c2d7239a4206238",
    "training.py": "194081120faae4228b0af0d6127c1e12c6d6180acdfe7d7a6a8c7cbcf24b963f",
    "learning_exposure.py": "30d9191e9fc845d80e52a7a891244fcf0c7041cf60529f6559b15e6d47ac5c7f",
}
FIXTURE_SHA = "223aae3e160ba254adf6b0326e9770d30f45c1afe22174a8838026e0459d1e12"
DURABLE_SHA = "1bfbb9b2bf1f1ea2692a91db294c303a7b723b0ccd936fa6c1b2dbe8c4d4b784"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ActualSourceOverride:
    """Map only fixture 'proposed/' references to an explicit actual tree."""
    def __init__(self, actual):
        self.actual = actual

    def __truediv__(self, value):
        parts = Path(value).parts
        if parts and parts[0] == "proposed":
            return self.actual.joinpath(*parts[1:])
        return HERE / value


def run(actual, output, include_durable=False):
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("Set CUDA_VISIBLE_DEVICES='' before CPU fixture execution")
    if output.exists():
        raise FileExistsError(output)
    if sha(HERE / "test_exposure_proposal.py") != FIXTURE_SHA:
        raise RuntimeError("Original fixture bytes changed")
    if sha(HERE / "proposed/test_learning_exposure.py") != DURABLE_SHA:
        raise RuntimeError("Durable test bytes changed")
    actual_hashes = {name: sha(actual / name) for name in EXPECTED}
    if actual_hashes != EXPECTED:
        raise RuntimeError("Actual production source does not equal the reviewed proposal pins")
    protected = [HERE / "test_exposure_proposal.py", *sorted((HERE / "before").glob("*.py")),
                 HERE / "preparation-validation.json", HERE / "preparation-validation-v2.json",
                 HERE / "independent-cpu-fixtures.json", HERE / "gpu0-parity-01/result.json"]
    before = {str(path.relative_to(HERE)): sha(path) for path in protected}
    started = datetime.now(timezone.utc).isoformat()
    monotonic = time.monotonic()
    # The original fixture file is imported unchanged. Its source-root and
    # helper globals are then explicitly redirected for this new invocation.
    original = load("original_exposure_fixture_actual_override", HERE / "test_exposure_proposal.py")
    helper = load("learning_exposure", actual / "learning_exposure.py")
    original.ex = helper
    original.HERE = ActualSourceOverride(actual)
    original.GAME = actual.parent.parent
    suite = unittest.defaultTestLoader.loadTestsFromModule(original)
    if include_durable:
        durable = load("durable_exposure_fixture_actual_override", HERE / "proposed/test_learning_exposure.py")
        assert durable.exposure is helper
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(durable))
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    ended = datetime.now(timezone.utc).isoformat()
    after = {str(path.relative_to(HERE)): sha(path) for path in protected}
    torch_imported = any(name == "torch" or name.startswith("torch.") for name in sys.modules)
    assert before == after, "Historical fixtures/oracles/receipts changed"
    assert actual_hashes == {name: sha(actual / name) for name in EXPECTED}, "Actual sources changed during tests"
    assert not torch_imported, "CPU scalar fixtures unexpectedly imported Torch"
    report = dict(
        schema="robotron-exposure-actual-source-fixtures-v1",
        status="PASS" if result.wasSuccessful() else "FAIL",
        utc_start=started, utc_end=ended, elapsed_s=time.monotonic() - monotonic,
        pid=os.getpid(), tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        actual_dqn_dir=str(actual), actual_source_hashes=actual_hashes,
        fixture_sha256=FIXTURE_SHA, durable_test_sha256=DURABLE_SHA,
        include_durable=include_durable,
        historical_bytes=before, historical_bytes_unchanged=True,
        override="proposed/ maps to explicit actual tree; original before/ oracle retained",
        actual_helper_path=helper.__file__, Torch_imported=torch_imported,
        CUDA_VISIBLE_DEVICES=os.environ.get("CUDA_VISIBLE_DEVICES"), output=log.getvalue(),
        scope="Fresh CPU invocation only; no old receipts overwritten, no production/model/process/control edits.",
    )
    with output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(log.getvalue())
    print(json.dumps({key: value for key, value in report.items() if key != "output"}, indent=2))
    if not result.wasSuccessful():
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--actual-dqn-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-durable", action="store_true")
    args = parser.parse_args()
    if not args.run:
        print(json.dumps(dict(mode="plan_only", actual_dqn_dir=str(args.actual_dqn_dir.resolve()),
                              required_source_hashes=EXPECTED, original_fixtures=13,
                              durable_fixtures=12 if args.include_durable else 0), indent=2))
        return
    if args.output is None:
        parser.error("--run requires a fresh --output path")
    run(args.actual_dqn_dir.resolve(), args.output.resolve(), args.include_durable)


if __name__ == "__main__":
    main()
