"""Preview the reviewed transport fix without changing loaded production files.

This tool only prints a unified diff (empty after the exact reviewed patch).
There is deliberately no apply or live-process mode.
"""
from __future__ import annotations

import difflib
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LUA = Path("Scripts/main.lua")
SERVER = Path("Scripts/dqn/socket_server.py")


def _once(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise ValueError("Source changed: expected exactly one transport patch anchor")
    return source.replace(before, after, 1)


def proposed_lua(source: str) -> str:
    if hashlib.sha256(source.encode()).hexdigest() == "060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf":
        return source
    source = _once(source, '''        trace_log(frame_idx, "socket_read_timeout", "using neutral action")
        return {-1, -1}
''', '''        trace_log(frame_idx, "socket_read_timeout", "closing connection; using neutral action")
        return nil
''')
    return _once(source, '''    local move_dir, fire_dir, source = unpack(read_result)
''', '''    if read_result == nil then
        -- Replies carry no request ID. Reusing this stream after a timeout
        -- could apply a late reply to the next state or lose byte alignment.
        close_socket()
        return -1, -1, false
    end

    local move_dir, fire_dir, source = unpack(read_result)
''')


def proposed_server(source: str) -> str:
    if hashlib.sha256(source.encode()).hexdigest() == "8fe556f7507547a97839072bbcecc98384c2b395c8ae789ac8ee062f55bca721":
        return source
    source = _once(source,
        '"""Read exactly *n* bytes; return None on timeout, b"" on EOF/socket error."""',
        '''"""Read *n* bytes; None means idle with no bytes consumed.

        A partial timeout is a broken frame, so the handler must close the
        connection rather than treating the remaining bytes as a new header.
        EOF/socket errors return b"" as before.
        """''')
    source = _once(source, '''            if remaining <= 0:
                return None
            try:
                r, _, _ = select.select([sock], [], [], min(0.05, remaining))
''', '''            if remaining <= 0:
                if buf:
                    raise ConnectionError(f"Partial read timeout ({len(buf)}/{n} bytes)")
                return None
            try:
                r, _, _ = select.select([sock], [], [], min(0.05, remaining))
''')
    source = _once(source, '''        buf = bytearray()
        deadline = time.time() + timeout_s
        while len(buf) < n:
            remaining = deadline - time.time()
''', '''        buf = bytearray()
        deadline = time.monotonic() + timeout_s
        while len(buf) < n:
            remaining = deadline - time.monotonic()
''')
    source = _once(source,
        '__slots__ = ("state", "epsilon", "locked_fire", "event", "action", "cancelled")',
        '__slots__ = ("state", "epsilon", "locked_fire", "event", "action", "cancelled", "error")')
    source = _once(source, '''        self.action = None
        self.cancelled = False
''', '''        self.action = None
        self.cancelled = False
        self.error = None
''')
    source = _once(source, '''        self.queue = queue.Queue(maxsize=20000)
        self.running = True
''', '''        self.queue = queue.Queue(maxsize=20000)
        self._request_lock = threading.Lock()
        self._pending = set()
        self.running = True
''')
    start = source.index('    def infer(self, state, epsilon: float, locked_fire=None):',
                         source.index('class AsyncInferenceBatcher:'))
    end = source.index('    def _consume(self):', start)
    source = source[:start] + '''    def infer(self, state, epsilon: float, locked_fire=None):
        req = _InferenceRequest(state, epsilon, locked_fire=locked_fire)
        with self._request_lock:
            if not self.running:
                raise RuntimeError("Inference batcher is stopped")
            self._pending.add(req)
        deadline = time.perf_counter() + self.request_timeout_s
        try:
            self.queue.put(req, timeout=max(0.0, deadline - time.perf_counter()))
        except queue.Full as exc:
            with self._request_lock:
                self._pending.discard(req)
                req.cancelled = True
            raise TimeoutError("Inference queue admission timed out") from exc
        if not req.event.wait(timeout=max(0.0, deadline - time.perf_counter())):
            # Cancellation can skip queued work, but cannot undo an in-flight
            # batch. Never launch a second solo inference for the same state.
            with self._request_lock:
                self._pending.discard(req)
                req.cancelled = True
            raise TimeoutError("Batched inference request timed out")
        with self._request_lock:
            error, action = req.error, req.action
        if error is not None:
            raise RuntimeError(error)
        if action is None:
            raise RuntimeError("Inference completed without an action")
        return action

    def _finish(self, batch, actions=None, error=None):
        with self._request_lock:
            for idx, req in enumerate(batch):
                self._pending.discard(req)
                if req.cancelled:
                    continue
                req.error = error
                if error is None:
                    req.action = actions[idx]
                req.event.set()

''' + source[end:]
    source = _once(source, '''            # Drop requests whose handler already gave up and solo-inferred —
            # running them here would be pure duplicate GPU work.
''', '''            # Skip queued requests whose handler already timed out. A request
            # that expires after dispatch may finish once, without solo work.
''')
    source = _once(source, '''            batch = [r for r in batch if not r.cancelled]
''', '''            with self._request_lock:
                batch = [r for r in batch if self.running and not r.cancelled]
''')
    source = _once(source, '''                actions = self.agent.act_batch(states, epsilons, locked_fires=locked_fires)
            except Exception as e:
                print(f"AsyncInferenceBatcher error: {e}")
                actions = []

            for idx, req in enumerate(batch):
                act = actions[idx] if idx < len(actions) else None
                if act is None:
                    try:
                        act = self.agent.act(req.state, req.epsilon, locked_fire=req.locked_fire)
                    except Exception:
                        act = (0, 0, False)
                req.action = act
                req.event.set()
''', '''                actions = self.agent.act_batch(states, epsilons, locked_fires=locked_fires)
                # Model-space move/fire indices are integers 0..8 (8 = idle).
                if (not isinstance(actions, (list, tuple)) or len(actions) != len(batch)
                        or any(not isinstance(a, (list, tuple)) or len(a) != 3
                               or type(a[0]) is not int or not 0 <= a[0] <= 8
                               or type(a[1]) is not int or not 0 <= a[1] <= 8
                               or type(a[2]) is not bool for a in actions)):
                    raise RuntimeError("Inference returned a malformed action batch")
            except Exception as e:
                error = f"Batched inference failed ({type(e).__name__}: {e})"
                print(error)
                self._finish(batch, error=error)
                continue

            self._finish(batch, actions=actions)
''')
    source = _once(source, '''    def stop(self):
        self.running = False
        self._thread.join(timeout=5.0)
        while True:
            try:
                req = self.queue.get_nowait()
''', '''    def stop(self):
        # Publish failure before joining: a blocked GPU dispatch must not
        # delay waiter shutdown or later overwrite a stop with a valid action.
        with self._request_lock:
            self.running = False
            for req in self._pending:
                req.cancelled = True
                req.error = "Inference batcher stopped before completion"
                req.event.set()
            self._pending.clear()
        self._thread.join(timeout=5.0)
        while True:
            try:
                req = self.queue.get_nowait()
''')
    return _once(source, '''            req.action = (0, 0, False)
            req.event.set()


# ── Socket Server''', '''            req.error = "Inference batcher stopped before dispatch"
            req.event.set()


# ── Socket Server''')


def proposed_sources(root: Path = ROOT) -> dict[Path, tuple[str, str]]:
    return {path: (source, transform(source))
            for path, transform in ((LUA, proposed_lua), (SERVER, proposed_server))
            for source in [(root / path).read_text()]}


def main() -> None:
    for path, (before, after) in proposed_sources().items():
        print("".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=f"a/Robotron/{path}", tofile=f"b/Robotron/{path}")), end="")


if __name__ == "__main__":
    main()
