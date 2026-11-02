"""Source inserted into the unapplied replay proposal; not a live import."""

import queue
import threading


class _StateFillTicket:
    """Parent-owned before publication; claim/cancel serialize destination use."""

    def __init__(self, function, job):
        self._lock = threading.Lock()
        self.done = threading.Event()
        self._phase = "pending"
        self._function, self._job = function, job
        self.result, self.error = None, None

    def run(self):
        with self._lock:
            if self._phase != "pending":
                return
            self._phase = "running"
            function, job = self._function, self._job
        try:
            self.result = function(*job)
        except BaseException as error:
            self.error = error
        finally:
            with self._lock:
                self._function = self._job = None
                self._phase = "done"
                self.done.set()

    def cancel_if_pending(self):
        with self._lock:
            if self._phase == "pending":
                self._function = self._job = None
                self._phase = "cancelled"
                self.done.set()


class _StateFillWorkers:
    """Two explicit owned threads; no output work is published during startup.

    A queue publication can fail after insertion. Parent tickets exist before
    insertion, so retirement cancels unclaimed tickets and waits for claimed
    writers independently of whether publication returned successfully.
    """

    def __init__(self):
        self._queue = queue.SimpleQueue()
        self._stop = threading.Event()
        self._max_workers = 2
        self._started = False
        self._startup_failed = False
        # Register every Thread object before calling any Thread.start().
        self._threads = tuple(threading.Thread(target=self._work,
                              name=f"robotron-state-fill_{index}", daemon=False)
                              for index in range(2))

    def start(self):
        try:
            for thread in self._threads:
                thread.start()
            self._started = True
        except BaseException:
            self._startup_failed = True
            self.shutdown()
            raise

    def _work(self):
        while not self._stop.is_set():
            try:
                ticket = self._queue.get(timeout=.05)
            except queue.Empty:
                continue
            ticket.run()

    def _publish(self, ticket):
        self._queue.put(ticket)

    @staticmethod
    def _wait_ticket(ticket):
        ticket.done.wait()

    def _cancel_and_drain(self, tickets):
        for ticket in tickets:
            ticket.cancel_if_pending()
        # A handled interruption of Event.wait cannot release a running writer.
        # Keep its first interruption for propagation after every ticket is safe.
        interrupted = None
        for ticket in tickets:
            while not ticket.done.is_set():
                try:
                    self._wait_ticket(ticket)
                except BaseException as error:
                    if interrupted is None:
                        interrupted = error
        return interrupted

    def fill_pair(self, function, jobs):
        if not self._started or self._stop.is_set():
            raise RuntimeError("Replay state-fill workers are unavailable")
        tickets = tuple(_StateFillTicket(function, job) for job in jobs)
        if len(tickets) != 2:
            raise ValueError("Exactly two replay state fields are required")
        try:
            for ticket in tickets:
                self._publish(ticket)
            for ticket in tickets:
                self._wait_ticket(ticket)
            for ticket in tickets:
                if ticket.error is not None:
                    raise ticket.error
            return tuple(ticket.result for ticket in tickets)
        except BaseException:
            # This also covers an unreturned publication that enqueued work.
            # Cancel under the same ticket lock that claims each destination.
            self._cancel_and_drain(tickets)
            self.shutdown()
            raise

    def shutdown(self, wait=True, cancel_futures=False):
        if not wait:
            raise ValueError("Replay state-fill shutdown must join owned workers")
        self._stop.set()
        interrupted = None
        for thread in self._threads:
            # A failed startup retains the entire owner in replay. A thread
            # interrupted before its ident becomes visible can still start
            # later, see the stop event, and exit without any output-bearing job.
            if thread.ident is None:
                continue
            while thread.is_alive():
                try:
                    thread.join()
                except BaseException as error:
                    if interrupted is None:
                        interrupted = error
        if interrupted is not None:
            raise interrupted
        # Failed-start Thread objects are retained conservatively for inspection
        # and subsequent shutdown attempts, even when all observed threads exited.
        return not self._startup_failed
