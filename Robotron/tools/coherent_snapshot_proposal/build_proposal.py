"""Build an unapplied patch and inspectable copies; production sources are read-only."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Source anchor differs: ' + before[:100])
    return source.replace(before, after, 1)


def prepare():
    source_dir = ROOT / 'Robotron/Scripts/dqn'
    originals = {name:(source_dir / name).read_text() for name in ('main.py', 'socket_server.py', 'metrics_dashboard.py', 'agent.py')}
    proposed = dict(originals)
    text = proposed['socket_server.py']
    text = once(text, '    from .nstep_buffer import NStepReplayBuffer\n',
                '    from .nstep_buffer import NStepReplayBuffer\n    from .coherent_snapshot import SnapshotFrameGate\n')
    text = once(text, '    from nstep_buffer import NStepReplayBuffer\n',
                '    from nstep_buffer import NStepReplayBuffer\n    from coherent_snapshot import SnapshotFrameGate\n')
    text = once(text, '        self.replay_enabled = bool(replay_enabled)\n', '''        self.replay_enabled = bool(replay_enabled)
        # Startup opt-in only. Disabled gates add no lock or model behavior.
        self.snapshot_gate = SnapshotFrameGate(self.replay_enabled and
            os.getenv("DQN_COHERENT_SNAPSHOT", "0").strip().lower() in ("1", "true", "yes", "on"))
''')
    text = once(text, '        self.dropped_steps = 0\n',
                '        self.dropped_steps = 0\n        self.snapshot_command_failures = 0\n')
    text = once(text, '    def barrier_async(self):\n', '    def barrier_async(self, timeout=None):\n')
    text = once(text, '        self._enqueue_preserving(("barrier", None, None, {"event": acknowledged}))\n', '''        item = ("barrier", None, None, {"event": acknowledged})
        if timeout is None:
            self._enqueue_preserving(item)
        else:
            if not self.running or not self._thread.is_alive():
                raise RuntimeError("Replay consumer is not running")
            self.queue.put(item, timeout=max(0.0, float(timeout)))
''')
    text = once(text, '                    print(f"AsyncReplayBuffer error: {e}")\n',
                '                    self.snapshot_command_failures += 1\n                    print(f"AsyncReplayBuffer error: {e}")\n')
    text = once(text, '''    def handle_client(self, sock, cid):
        local_accum = 0
        local_measurement_accum = 0
        try:
''', '''    def handle_client(self, sock, cid):
        snapshot_token = self.snapshot_gate.register("client:" + str(cid))
        local_accum = 0
        local_measurement_accum = 0
        def flush_snapshot_frame_counters():
            nonlocal local_accum, local_measurement_accum
            if local_accum:
                self._account_frame_batch(local_accum, local_measurement_accum)
                local_accum = local_measurement_accum = 0
        try:
''')
    text = once(text, '''            while self.running and not self.shutdown_event.is_set():
                if (not getattr(self, "replay_enabled", True)
''', '''            while self.running and not self.shutdown_event.is_set():
                self.snapshot_gate.checkpoint(snapshot_token, flush_snapshot_frame_counters)
                if (not getattr(self, "replay_enabled", True)
''')
    start = text.index('        finally:\n            # Flush frames accumulated since the last batch', text.index('    def handle_client('))
    end = text.index('\n    def _cleanup(self):', start)
    body = text[start + len('        finally:\n'):end]
    text = text[:start] + '        finally:\n            try:\n' + ''.join(
        '    ' + line if line.strip() else line for line in body.splitlines(keepends=True)) + '''            finally:
                self.snapshot_gate.unregister(snapshot_token)
''' + text[end:]
    anchor = '''        print(f"SocketServer listening on {self.host}:{self.port}")

        try:
            while self.running and not self.shutdown_event.is_set():
'''
    text = once(text, anchor, '''        print(f"SocketServer listening on {self.host}:{self.port}")

        snapshot_accept_token = self.snapshot_gate.register("accept-loop")
        try:
            while self.running and not self.shutdown_event.is_set():
                self.snapshot_gate.checkpoint(snapshot_accept_token)
''')
    text = once(text, '''        finally:
            self.stop()

    def stop(self):
''', '''        finally:
            try:
                self.stop()
            finally:
                self.snapshot_gate.unregister(snapshot_accept_token)

    def stop(self):
''')
    proposed['socket_server.py'] = text
    text = proposed['main.py']
    text = once(text, '    from .managed_driver import ManagedMeasurementDriver, consume_save_request\n',
                '    from .managed_driver import ManagedMeasurementDriver, consume_save_request\n    from .coherent_snapshot import consume_snapshot_request\n')
    text = once(text, '    from managed_driver import ManagedMeasurementDriver, consume_save_request\n',
                '    from managed_driver import ManagedMeasurementDriver, consume_save_request\n    from coherent_snapshot import consume_snapshot_request\n')
    text = once(text, '''    kb = None
    if IS_INTERACTIVE:
''', '''    kb = None
    # Snapshot mode never creates a keyboard mutation thread. A per-key flag
    # check could miss an action already admitted before the snapshot began.
    metrics.coherent_snapshot_keyboard_disabled = _env_enabled("DQN_COHERENT_SNAPSHOT", False)
    if IS_INTERACTIVE and not metrics.coherent_snapshot_keyboard_disabled:
''')
    text = once(text, '''            learning_control.refresh()
            metrics.managed_experiment = learning_control.label
''', '''            if getattr(metrics, "coherent_snapshot_active", False):
                # Failed cleanup is fail-closed until coordinated recovery.
                time.sleep(0.1)
                continue
            learning_control.refresh()
            metrics.managed_experiment = learning_control.label
            consume_snapshot_request(agent, metrics, server, RL_CONFIG, MODEL_DIR, ratchet_on=ratchet_on,
                                     control=learning_control, game_settings=game_settings)
            if getattr(metrics, "coherent_snapshot_active", False):
                continue
''')
    proposed['main.py'] = text
    text = proposed['metrics_dashboard.py']
    text = once(text, '    from .run_telemetry import pipeline_snapshot\n',
                '    from .run_telemetry import pipeline_snapshot\n    from .coherent_snapshot import snapshot_activity, snapshot_dashboard_overlay\n')
    text = once(text, '    from run_telemetry import pipeline_snapshot\n',
                '    from run_telemetry import pipeline_snapshot\n    from coherent_snapshot import snapshot_activity, snapshot_dashboard_overlay\n')
    text = once(text, '            "training_enabled": training_enabled,\n', '''            "training_enabled": training_enabled,
            "coherent_snapshot_active": bool(getattr(self.metrics, "coherent_snapshot_active", False)),
            "coherent_snapshot": snapshot_activity(self.metrics),
''')
    text = once(text, '''    def now_body(self) -> bytes:
        with self.lock:
            return self._cached_now_body
''', '''    def now_body(self) -> bytes:
        # Snapshot progress cannot wait for the background sampler's replay
        # telemetry locks. Preserve the cached metrics' original timestamp.
        with self.lock:
            cached, latest = self._cached_now_body, dict(self.latest)
        overlay = snapshot_dashboard_overlay(self.metrics, latest)
        return json.dumps(overlay).encode("utf-8") if overlay is not None else cached
''')
    text = once(text, '''      const live = age < 5 && now.training_enabled && Number(now.fps) > 0 && Number(now.client_count) > 0;
''', '''      const snapshot = now.coherent_snapshot || {};
      const live = age < 5 && now.training_enabled && Number(now.fps) > 0 && Number(now.client_count) > 0;
''')
    text = once(text, '''      put("mTrainingStatus", age >= 5 ? "Training metrics are stale · reconnecting" :
''', '''      put("mTrainingStatus", snapshot.active ? snapshot.label : age >= 5 ? "Training metrics are stale · reconnecting" :
''')
    text = once(text, '''      put("mActivityUpdated", age < 5 ? "Updated " + new Date(Number(now.ts) * 1000).toLocaleTimeString() : "Last update " + Math.round(age) + " seconds ago");
''', '''      const snapshotProgress = String(snapshot.phase || "saving").replaceAll("_", " ") + " · " +
        Math.round(Number(snapshot.elapsed_s || 0)) + "s" +
        (snapshot.total_bytes ? " · " + (Number(snapshot.copied_bytes || 0) / 1073741824).toFixed(1) +
          "/" + (Number(snapshot.total_bytes) / 1073741824).toFixed(1) + " GiB" : "");
      put("mActivityUpdated", snapshot.active ? snapshotProgress : age < 5 ? "Updated " + new Date(Number(now.ts) * 1000).toLocaleTimeString() : "Last update " + Math.round(age) + " seconds ago");
''')
    start = text.index('                try:\n', text.index('            if path == "/api/game_settings":'))
    end = text.index('                return\n', start)
    body = text[start:end]
    text = text[:start] + '''                snapshot_gate = getattr(getattr(state.metrics, "global_server", None), "snapshot_gate", None)
                snapshot_token = snapshot_gate.register("dashboard-game-settings") if snapshot_gate is not None else None
                try:
''' + ''.join('    ' + line if line.strip() else line for line in body.splitlines(keepends=True)) + '''                finally:
                    if snapshot_gate is not None:
                        snapshot_gate.unregister(snapshot_token)
''' + text[end:]
    proposed['metrics_dashboard.py'] = text
    text = proposed['agent.py']
    text = once(text, '    def _resume_prefetch(self):\n', '''    def synchronize_snapshot_device(self):
        """Explicit owned-device barrier after host learner/prefetch quiescence."""
        with self._training_lock:
            if self.training_enabled or not self._prefetch_paused:
                raise RuntimeError("Pause learner and prefetch before the snapshot device barrier")
            if self.device.type == "cuda":
                torch.cuda.synchronize(self.device)
                return dict(device=str(self.device), mode="owned_cuda_device_synchronized")
            return dict(device=str(self.device), mode="cpu_noop")

    def _resume_prefetch(self):
''')
    proposed['agent.py'] = text
    proposed['coherent_snapshot.py'] = (HERE / 'coherent_snapshot.py').read_text()
    original_hashes = {}
    patch = []
    for name, source in proposed.items():
        compile(source, name, 'exec')
        output = HERE / 'staged/Robotron/Scripts/dqn' / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(source)
        path = 'Robotron/Scripts/dqn/' + name
        old = originals.get(name, '')
        patch.extend(difflib.unified_diff(old.splitlines(keepends=True), source.splitlines(keepends=True),
                                        fromfile='a/' + path if old else '/dev/null', tofile='b/' + path))
        original_hashes[path] = dict(base_sha256=hashlib.sha256(old.encode()).hexdigest() if old else None,
                                      proposed_sha256=hashlib.sha256(source.encode()).hexdigest())
    (HERE / 'coherent-snapshot.patch').write_text(''.join(patch))
    (HERE / 'proposal-manifest.json').write_text(json.dumps(dict(status='UNAPPLIED_REVIEW_ONLY',
        explicit_startup_optin='DQN_COHERENT_SNAPSHOT=1', source_files=original_hashes), indent=2) + '\n')


if __name__ == '__main__':
    prepare()
