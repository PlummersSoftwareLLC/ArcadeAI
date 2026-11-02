"""Prepare observability v2 copies/patch only; preserve v1 and live sources."""
import difflib
import hashlib
import json
from pathlib import Path


RUN = Path(__file__).resolve().parent
BASE = RUN.parents[3]
V1 = RUN / "native-batch-prototype"
DESTINATION = RUN / "native-batch-observed-v2"


def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("Expected anchor once: " + old[:80])
    return text.replace(old, new, 1)


def main():
    v1_manifest = json.loads((V1 / "integration-prepared.json").read_text())
    originals, proposed = {}, {}
    for name, record in v1_manifest["sources"].items():
        original = (BASE / name).read_text()
        if hashlib.sha256(original.encode()).hexdigest() != record["before_sha256"]:
            raise RuntimeError("Live source differs from pinned v1 original: " + name)
        originals[name] = original
        proposed[name] = (V1 / "proposed" / Path(name).name).read_text()
    native_name = "Robotron/Scripts/dqn/native_sumtree.py"
    native = proposed[native_name]
    native = once(native, "import tempfile\n", "import tempfile\nimport threading\n")
    native = once(native, "NATIVE_BATCH_AVAILABLE = False\n",
                  "NATIVE_BATCH_AVAILABLE = False\n_BATCH_STATS_LOCK = threading.Lock()\n"
                  "_BATCH_COUNTS = {\"success\": 0, \"fallback\": 0, \"error\": 0}\n")
    start = native.index("def batch_update(tree, capacity, indices, priorities):")
    end = native.index("\n\n_load_native()", start)
    previous_helper = native[start:end]
    validation = previous_helper[previous_helper.index("    if (not isinstance(tree, np.ndarray)"):]
    replacement = '''def _batch_update_enabled(tree, capacity, indices, priorities):
    if _BATCH_FUNCTION is None:
        return False
''' + validation + '''


def batch_update(tree, capacity, indices, priorities):
    """Default-off exact path; count completed enabled calls, never CUDA work.

    The existing replay lock owns validation and the GIL-released C call.
    Unsupported/unavailable inputs return False for the original NumPy path.
    Unexpected exceptions are counted and re-raised, never silently retried.
    """
    if not NATIVE_BATCH_ENABLED:
        return False
    try:
        used = _batch_update_enabled(tree, capacity, indices, priorities)
    except Exception:
        with _BATCH_STATS_LOCK:
            _BATCH_COUNTS["error"] += 1
        raise
    with _BATCH_STATS_LOCK:
        _BATCH_COUNTS["success" if used else "fallback"] += 1
    return used


def batch_update_status():
    """Cumulative process-local scalars only; no reset, replay or CUDA lock.

    Each enabled completed call contributes once to success/fallback/error.
    Disabled calls do no counting. Snapshot never holds another owner lock.
    """
    with _BATCH_STATS_LOCK:
        return {"schema": "robotron-native-batch-update-v1",
                "enabled": bool(NATIVE_BATCH_ENABLED),
                "available": bool(NATIVE_BATCH_AVAILABLE and _BATCH_FUNCTION is not None),
                "completed_count": sum(_BATCH_COUNTS.values()),
                "success_count": _BATCH_COUNTS["success"],
                "fallback_count": _BATCH_COUNTS["fallback"],
                "error_count": _BATCH_COUNTS["error"]}
'''
    proposed[native_name] = native[:start] + replacement + native[end:]
    agent_name = "Robotron/Scripts/dqn/agent.py"
    agent = (BASE / agent_name).read_text()
    originals[agent_name] = agent
    agent = once(agent, "    from .replay_buffer import PrioritizedReplayBuffer\n",
                 "    from .replay_buffer import PrioritizedReplayBuffer\n    from .native_sumtree import batch_update_status\n")
    agent = once(agent, "    from replay_buffer import PrioritizedReplayBuffer\n",
                 "    from replay_buffer import PrioritizedReplayBuffer\n    from native_sumtree import batch_update_status\n")
    agent = once(agent, '        snapshot["inference_graphs"] = graphs.snapshot() if graphs is not None else disabled_snapshot()\n',
                 '        snapshot["inference_graphs"] = graphs.snapshot() if graphs is not None else disabled_snapshot()\n'
                 '        snapshot["native_batch_update"] = batch_update_status()\n')
    proposed[agent_name] = agent
    manifest = {"state": "PREPARED V2 ONLY; no live changes", "env": "DQN_NATIVE_BATCH_UPDATE=1",
                "default": "off", "prior_patch_sha256": v1_manifest["patch_sha256"], "sources": {}}
    patch = []
    for name in originals:
        for category, contents in (("before", originals[name]), ("proposed", proposed[name])):
            path = DESTINATION / category / Path(name).name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        manifest["sources"][name] = {"before_sha256": hashlib.sha256(originals[name].encode()).hexdigest(),
                                      "proposed_sha256": hashlib.sha256(proposed[name].encode()).hexdigest()}
        patch.extend(difflib.unified_diff(originals[name].splitlines(True), proposed[name].splitlines(True),
                                            fromfile="a/" + name, tofile="b/" + name))
    target = DESTINATION / "native-batch-observed-v2.patch"
    target.write_text("".join(patch))
    manifest["patch_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    (DESTINATION / "integration-prepared.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
