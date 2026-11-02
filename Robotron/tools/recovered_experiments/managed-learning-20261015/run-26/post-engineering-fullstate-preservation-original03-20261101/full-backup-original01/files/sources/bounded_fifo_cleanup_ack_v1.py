"""Prospective ACK wait only; never enqueues, signals, clears, or publishes.

The original FIFO Event must actually be set by its sole consumer. The normal
wait remains five seconds. Grace shares ONE seven-second ACK deadline, measured
after enqueue; it is not seven extra seconds. An already published cleanup
error is outside this helper and remains immutable.
"""
import math
import time


INITIAL_ACK_WAIT_S = 5.0
TOTAL_ACK_WAIT_S = 7.0


def wait_for_fifo_reset_ack(ack, *, clock=None):
    """Return timing evidence only after ACK, or raise without changing state.

    ``clock`` is an optional monotonic clock for deterministic CPU contracts.
    The production caller supplies the Event returned by remove_client().
    Scheduling can overrun a timeout; a late return past the total deadline is
    rejected even when the Event is then set.
    """
    clock = time.monotonic if clock is None else clock
    started = clock()
    if type(started) not in (int, float) or not math.isfinite(started):
        raise ValueError("Finite monotonic ACK start required")
    deadline = started + TOTAL_ACK_WAIT_S
    if not math.isfinite(deadline):
        raise ValueError("Finite monotonic ACK deadline required")
    initial_returned_ack = ack.wait(timeout=INITIAL_ACK_WAIT_S)
    initial_ack_is_set = ack.is_set()
    observed = clock()
    if (type(observed) not in (int, float) or not math.isfinite(observed)
            or observed < started):
        raise ValueError("ACK monotonic clock moved backwards or became invalid")
    if observed > deadline:
        raise TimeoutError("FIFO replay cleanup ACK deadline exceeded "
                           f"(total=7.000s, elapsed={observed-started:.6f}s)")
    if initial_ack_is_set:
        return dict(acknowledged=True, grace_used=not bool(initial_returned_ack),
                    elapsed_s=observed-started, total_limit_s=TOTAL_ACK_WAIT_S)
    remaining = deadline - observed
    if remaining > 0.0:
        ack.wait(timeout=remaining)
    final_ack_is_set = ack.is_set()
    finished = clock()
    if (type(finished) not in (int, float) or not math.isfinite(finished)
            or finished < observed):
        raise ValueError("ACK monotonic clock moved backwards or became invalid")
    if finished <= deadline and final_ack_is_set:
        return dict(acknowledged=True, grace_used=True,
                    elapsed_s=finished-started, total_limit_s=TOTAL_ACK_WAIT_S)
    raise TimeoutError("FIFO replay cleanup ACK deadline exceeded "
                       f"(total=7.000s, elapsed={finished-started:.6f}s)")
