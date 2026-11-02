#!/usr/bin/env python3
"""Create an unapplied minimal patch from the currently inspected core files."""

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Production source moved; re-review the proposal anchor")
    return text.replace(old, new, 1)


WORKER_SOURCE = "\n".join((Path(__file__).resolve().parent / "state_fill_workers_candidate.py").read_text().splitlines()[1:]) + "\n\n"


REPLAY_METHODS = '''    def _publish_state_fill_status_locked(self):
        """Publish scalars while the replay owner updates executor state."""
        status = dict(schema="robotron-parallel-state-fill-v1",
                      requested=self._parallel_state_fill_requested,
                      native_available=bool(_native_gather_available),
                      executor_created=self._state_fill_executor is not None,
                      closed=self._state_fill_closed,
                      completed_batches=self._parallel_state_fill_batches)
        with self._state_fill_status_lock:
            self._state_fill_status_cache = status

    def state_fill_status(self):
        """Bounded scalar snapshot; never waits for the replay/model/CUDA lock.

        Only the parent sampling/shutdown owner publishes this cache. The
        independent short-lived status lock cannot retain any ndarray or nest
        a replay lock acquisition, avoiding a monitoring-to-sampling lock cycle.
        """
        with self._state_fill_status_lock:
            return dict(self._state_fill_status_cache)

    def close_state_fill(self):
        """Replay is the single owner; stop prefetch before calling at shutdown.

        An in-flight sampling parent holds this lock until both writers drain.
        Keep the owner reference until shutdown joins every worker. Failed
        startup owners are retained conservatively even after observed exit.
        """
        with self.lock:
            self._state_fill_closed = True
            self._publish_state_fill_status_locked()
            if self._state_fill_executor is not None:
                if self._state_fill_executor.shutdown(wait=True, cancel_futures=False):
                    self._state_fill_executor = None
                self._publish_state_fill_status_locked()

    def _fill_state_pair_locked(self, outputs, indices, banks):
        """Fill validated disjoint outputs; caller retains the replay lock.

        All source/index references remain live until both tickets are safe.
        Workers do not acquire replay/model locks or draw any RNG.
        A failed pair is discarded by the caller, never retried in place.
        """
        jobs = [(output, getattr(self, field), indices,
                 [(getattr(self, f"{prefix}_{field}"), slots)
                  for prefix, _, slots in banks])
                for output, field in zip(outputs, ("states", "next_states"))]
        if not self._parallel_state_fill_requested or not _native_gather_available:
            return tuple(_fill_state_rows(*job) for job in jobs)
        if self._state_fill_closed:
            raise RuntimeError("Replay parallel state fill has been closed")
        try:
            if self._state_fill_executor is None:
                # Assign the owner before starting any OS thread; startup jobs
                # never contain replay arrays or destination references.
                self._state_fill_executor = _StateFillWorkers()
                self._state_fill_executor.start()
            result = self._state_fill_executor.fill_pair(_fill_state_rows, jobs)
        except BaseException:
            self._state_fill_closed = True
            self._publish_state_fill_status_locked()
            raise
        self._parallel_state_fill_batches += 1
        self._publish_state_fill_status_locked()
        return result

'''


def patched_sources(root=ROOT):
    paths = ("Robotron/Scripts/dqn/replay_buffer.py", "Robotron/Scripts/dqn/agent.py")
    originals = {path: (root / path).read_text() for path in paths}
    replay = originals[paths[0]]
    replay = replace_once(replay, "import threading\n", "import threading\nimport queue\n")
    replay = replace_once(replay, "    from .native_sumtree import gather_fp16_rows as _native_gather_fp16_rows\n",
                          "    from .native_sumtree import gather_fp16_rows as _native_gather_fp16_rows\n"
                          "    from .native_sumtree import NATIVE_GATHER_AVAILABLE as _native_gather_available\n")
    replay = replace_once(replay, "        from native_sumtree import gather_fp16_rows as _native_gather_fp16_rows\n",
                          "        from native_sumtree import gather_fp16_rows as _native_gather_fp16_rows\n"
                          "        from native_sumtree import NATIVE_GATHER_AVAILABLE as _native_gather_available\n")
    replay = replace_once(replay, "        _native_gather_fp16_rows = None\n",
                          "        _native_gather_fp16_rows = None\n        _native_gather_available = False\n")
    replay = replace_once(replay, "def _fill_state_rows(out, ring_source, ring_indices, banks):\n",
                          WORKER_SOURCE + "def _fill_state_rows(out, ring_source, ring_indices, banks):\n")
    replay = replace_once(replay, "        self.lock = threading.Lock()\n",
                          "        self.lock = threading.Lock()\n"
                          "        self._parallel_state_fill_requested = os.getenv(\n"
                          "            \"DQN_PARALLEL_STATE_FILL\", \"0\").strip().lower() in (\"1\", \"true\", \"yes\", \"on\")\n"
                          "        self._state_fill_executor = None\n"
                          "        self._state_fill_closed = False\n"
                          "        self._parallel_state_fill_batches = 0\n"
                          "        self._state_fill_status_lock = threading.Lock()\n"
                          "        self._state_fill_status_cache = {}\n"
                          "        self._publish_state_fill_status_locked()\n")
    replay = replace_once(replay, "    def sample_into(self, batch_size, states_out, next_states_out, beta=0.4):\n",
                          REPLAY_METHODS + "    def sample_into(self, batch_size, states_out, next_states_out, beta=0.4):\n")
    replay = replace_once(replay, "        if banks:\n            all_indices = np.concatenate(\n",
                          "        if _state_out is not None:\n"
                          "            self._fill_state_pair_locked(_state_out, indices, banks)\n"
                          "        if banks:\n            all_indices = np.concatenate(\n")
    replay = replace_once(replay, '''                    return _fill_state_rows(
                        output, getattr(self, field), indices,
                        [(getattr(self, f"{prefix}_{field}"), slots) for prefix, _, slots in banks],
                    )''', "                    return output")
    replay = replace_once(replay, "            _gather_states_fp32(self.states, indices, out=_state_out[0] if _state_out is not None else None),\n",
                          "            _state_out[0] if _state_out is not None else _gather_states_fp32(self.states, indices),\n")
    replay = replace_once(replay, "            _gather_states_fp32(self.next_states, indices, out=_state_out[1] if _state_out is not None else None),\n",
                          "            _state_out[1] if _state_out is not None else _gather_states_fp32(self.next_states, indices),\n")
    agent = originals[paths[1]]
    agent = replace_once(agent, "        memory = getattr(self, \"memory\", None)\n        getter = getattr(memory, \"get_learning_exposure_snapshot\", None)\n",
                         "        memory = getattr(self, \"memory\", None)\n"
                         "        fill_getter = getattr(memory, \"state_fill_status\", None)\n"
                         "        snapshot[\"parallel_state_fill\"] = fill_getter() if callable(fill_getter) else None\n"
                         "        getter = getattr(memory, \"get_learning_exposure_snapshot\", None)\n")
    agent = replace_once(agent, "        if self._prefetcher is not None:\n            self._prefetcher.close()\n\n\n# ── Interactive terminal keyboard handler",
                         "        if self._prefetcher is not None:\n            self._prefetcher.close()\n"
                         "        self.memory.close_state_fill()\n\n\n# ── Interactive terminal keyboard handler")
    return originals, dict(zip(paths, (replay, agent)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    originals, candidates = patched_sources()
    patch = "".join("".join(difflib.unified_diff(originals[path].splitlines(keepends=True),
                                               candidate.splitlines(keepends=True),
                                               fromfile="a/" + path, tofile="b/" + path))
                    for path, candidate in candidates.items())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "production.patch").write_text(patch)
    manifest = dict(schema="robotron-parallel-state-fill-unapplied-v1", utc=datetime.now(timezone.utc).isoformat(),
                    proposal_revision=2, worker_model="explicit-two-thread-owner-with-parent-owned-tickets",
                    daemon_for_early_process_exit=True, normal_shutdown="cancel-pending-drain-claimed-join-owned-workers",
                    applied=False, default_enabled=False, env_gate="DQN_PARALLEL_STATE_FILL",
                    files={path: dict(original_sha256=hashlib.sha256(originals[path].encode()).hexdigest(),
                                      proposed_sha256=hashlib.sha256(candidate.encode()).hexdigest())
                           for path, candidate in candidates.items()},
                    patch_sha256=hashlib.sha256(patch.encode()).hexdigest())
    (args.output_dir / "production-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
