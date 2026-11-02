"""Prepare only: sampled host priority timing, no live source mutation."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import textwrap


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
DESTINATION = RUN / "priority-host-timing-proposal"
NAMES = ("Scripts/dqn/agent.py", "Scripts/dqn/replay_buffer.py",
         "Scripts/dqn/training.py", "Scripts/dqn/pipeline_telemetry.py")


def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("Expected anchor once: " + old[:70])
    return text.replace(old, new, 1)


def main():
    original = {name: (ROOT / name).read_text() for name in NAMES}
    expected = {"Scripts/dqn/agent.py": "5109e6b48fc86b7996ff808ccda02d14d2142dcc3f07b30363216152ab602ede",
                "Scripts/dqn/replay_buffer.py": "b64c1b8bab1527dbd89e5b7594b2d2306e4aab227d2472f5f11156e15c2920ac"}
    for name, digest in expected.items():
        if hashlib.sha256(original[name].encode()).hexdigest() != digest:
            raise RuntimeError("Expected reviewed current source: " + name)
    proposed = dict(original)
    replay_name = "Scripts/dqn/replay_buffer.py"
    replay = proposed[replay_name]
    start = replay.index("    def update_priorities(self, indices, td_errors):")
    end = replay.index("\n    def boost_priorities", start)
    old_method = replay[start:end]
    body = old_method.split("        with self.lock:\n", 1)[1].rstrip()
    measured = '''    def update_priorities(self, indices, td_errors, timing_out=None):
        """Update priorities; optional host timings are published after unlock.

        The normal two-argument call performs no extra clock reads. Timed
        calls preserve the same replay lock and operation order, including
        early returns/errors; timing_out is a caller-owned dictionary.
        """
        measuring = timing_out is not None
        started = time.perf_counter() if measuring else 0.0
        acquired = finished = None
        try:
            with self.lock:
                if measuring:
                    acquired = time.perf_counter()
                try:
''' + textwrap.indent(body, "        ") + '''
                finally:
                    if measuring:
                        finished = time.perf_counter()
        finally:
            if measuring and acquired is not None:
                timing_out.update(
                    replay_lock_wait_ms=(acquired - started) * 1000.0,
                    locked_priority_ms=(finished - acquired) * 1000.0,
                    replay_update_host_ms=(time.perf_counter() - started) * 1000.0,
                )
'''
    proposed[replay_name] = replay[:start] + measured + replay[end:]
    training_name = "Scripts/dqn/training.py"
    training = proposed[training_name]
    training = once(training, "    priority_t0 = time.perf_counter()\n    host = packed.cpu().numpy()\n",
                    "    priority_telemetry = getattr(agent, \"_pipeline_telemetry\", None) if diagnostic_due else None\n"
                    "    priority_timings = {} if priority_telemetry is not None else None\n"
                    "    priority_t0 = time.perf_counter()\n"
                    "    host = packed.cpu().numpy()\n"
                    "    if priority_timings is not None:\n"
                    "        priority_readback_done = time.perf_counter()\n")
    training = once(training, "    agent.memory.update_priorities(indices, td_errors)\n"
                    "    priority_ms = (time.perf_counter() - priority_t0) * 1000.0\n",
                    "    if priority_timings is None:\n"
                    "        agent.memory.update_priorities(indices, td_errors)\n"
                    "    else:\n"
                    "        priority_update_started = time.perf_counter()\n"
                    "        agent.memory.update_priorities(indices, td_errors, timing_out=priority_timings)\n"
                    "    priority_ms = (time.perf_counter() - priority_t0) * 1000.0\n"
                    "    if priority_timings is not None:\n"
                    "        priority_timings.update(\n"
                    "            readback_host_ms=(priority_readback_done - priority_t0) * 1000.0,\n"
                    "            cpu_bookkeeping_ms=(priority_update_started - priority_readback_done) * 1000.0,\n"
                    "            total_host_ms=priority_ms,\n"
                    "        )\n"
                    "        priority_telemetry.record_learner_priority(priority_timings)\n")
    proposed[training_name] = training
    helper_name = "Scripts/dqn/pipeline_telemetry.py"
    helper = proposed[helper_name]
    helper = once(helper, '    "target_refresh": ("host_ms",),\n',
                  '    "target_refresh": ("host_ms",),\n'
                  '    "learner_priority": (\n'
                  '        "readback_host_ms", "cpu_bookkeeping_ms", "replay_lock_wait_ms",\n'
                  '        "locked_priority_ms", "replay_update_host_ms", "total_host_ms",\n'
                  '    ),\n')
    helper = once(helper, "    def snapshot(self, reset=False):\n",
                  "    def record_learner_priority(self, measurements):\n"
                  "        \"\"\"Existing diagnostic cadence, successful completed phases only.\n\n"
                  "        Caller has released replay lock; all values are host elapsed ms.\n"
                  "        CPU readback may wait for previously enqueued CUDA work.\n"
                  "        \"\"\"\n"
                  "        self._record(\"learner_priority\", measurements)\n\n"
                  "    def snapshot(self, reset=False):\n")
    proposed[helper_name] = helper
    manifest = {"state": "PREPARED ONLY; no production source edits", "sources": {},
                "guarded_source_sha256": json.loads((RUN / "fresh3-64M-sidecar-screen-readiness.json").read_text())["sources"]}
    patch = []
    for name in NAMES:
        ast.parse(proposed[name])
        for category, contents in (("before", original[name]), ("proposed", proposed[name])):
            path = DESTINATION / category / Path(name).name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        manifest["sources"][name] = {"before_sha256": hashlib.sha256(original[name].encode()).hexdigest(),
                                      "proposed_sha256": hashlib.sha256(proposed[name].encode()).hexdigest(),
                                      "changed": original[name] != proposed[name]}
        patch.extend(difflib.unified_diff(original[name].splitlines(True), proposed[name].splitlines(True),
                                            fromfile="a/Robotron/" + name, tofile="b/Robotron/" + name))
    target = DESTINATION / "priority-host-timing.patch"
    target.write_text("".join(patch))
    manifest["patch_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    (DESTINATION / "prepared.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
