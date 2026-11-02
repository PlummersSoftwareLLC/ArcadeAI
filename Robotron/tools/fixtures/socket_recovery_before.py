"""Static pre-fix production excerpts, test fixtures only.
Original socket_server.py SHA256: 799ddabe29d824d64b62ff0301dd1e6187f68037373e1fb988ea162583ec4580
"""

class _InferenceRequest:
    __slots__ = ("state", "epsilon", "locked_fire", "event", "action", "cancelled")

    def __init__(self, state, epsilon: float, locked_fire=None):
        self.state = state
        self.epsilon = float(epsilon)
        self.locked_fire = locked_fire
        self.event = threading.Event()
        self.action = None
        self.cancelled = False


class AsyncInferenceBatcher:
    """Micro-batch inference requests across clients for better throughput."""

    def __init__(self, agent, max_batch_size=32, max_wait_ms=1.0, request_timeout_ms=50.0):
        self.agent = agent
        self.max_batch_size = max(1, int(max_batch_size))
        self.max_wait_s = max(0.0, float(max_wait_ms) / 1000.0)
        self.request_timeout_s = max(0.001, float(request_timeout_ms) / 1000.0)
        self.queue = queue.Queue(maxsize=20000)
        self.running = True
        self._thread = threading.Thread(target=self._consume, daemon=True, name="InferBatchWorker")
        self._thread.start()

    def infer(self, state, epsilon: float, locked_fire=None):
        if not self.running:
            return self.agent.act(state, epsilon, locked_fire=locked_fire)
        req = _InferenceRequest(state, epsilon, locked_fire=locked_fire)
        try:
            self.queue.put(req, timeout=self.request_timeout_s)
        except queue.Full:
            return self.agent.act(state, epsilon, locked_fire=locked_fire)
        if not req.event.wait(timeout=self.request_timeout_s):
            # Cancel BEFORE falling back to a solo act(): an abandoned request
            # left live in the queue still gets batched and inferred — every
            # timed-out frame was costing TWO inferences.  Under load, 32
            # handlers timing out at once turned into 32 solo CUDA calls plus
            # the batcher's ghost work, which kept latency above the timeout
            # forever: a self-sustaining stampede (measured: AvgInf pinned at
            # ~104ms for an entire boot on 2026-07-13).  Cancelling the
            # request breaks the amplification; the longer timeout (config:
            # inference_request_timeout_ms) keeps handlers in the batched
            # path through transient stalls instead of defecting.
            req.cancelled = True
            return self.agent.act(state, epsilon, locked_fire=locked_fire)
        return req.action if req.action is not None else (0, 0, False)

    def _consume(self):
        while self.running or not self.queue.empty():
            try:
                first = self.queue.get(timeout=0.01)
            except queue.Empty:
                continue

            batch = [first]
            deadline = time.perf_counter() + self.max_wait_s
            while len(batch) < self.max_batch_size:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                try:
                    batch.append(self.queue.get(timeout=remaining))
                except queue.Empty:
                    break

            # Drop requests whose handler already gave up and solo-inferred —
            # running them here would be pure duplicate GPU work.
            batch = [r for r in batch if not r.cancelled]
            if not batch:
                continue

            try:
                states = [r.state for r in batch]
                epsilons = [r.epsilon for r in batch]
                locked_fires = [r.locked_fire for r in batch]
                actions = self.agent.act_batch(states, epsilons, locked_fires=locked_fires)
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

    def stop(self):
        self.running = False
        self._thread.join(timeout=5.0)
        while True:
            try:
                req = self.queue.get_nowait()
            except queue.Empty:
                break
            req.action = (0, 0, False)
            req.event.set()


# ── Socket Server ───────────────────────────────────────────────────────────
class SocketServer:
    @staticmethod
    def _recv_exact(sock, n, timeout_s=0.5):
        """Read exactly *n* bytes; return None on timeout, b"" on EOF/socket error."""
        buf = bytearray()
        deadline = time.time() + timeout_s
        while len(buf) < n:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            try:
                r, _, _ = select.select([sock], [], [], min(0.05, remaining))
            except (OSError, ValueError):
                return b""
            if not r:
                continue
            try:
                chunk = sock.recv(n - len(buf))
            except BlockingIOError:
                continue
            except OSError:
                return b""
            if not chunk:
                return b""
            buf += chunk
        return bytes(buf)
