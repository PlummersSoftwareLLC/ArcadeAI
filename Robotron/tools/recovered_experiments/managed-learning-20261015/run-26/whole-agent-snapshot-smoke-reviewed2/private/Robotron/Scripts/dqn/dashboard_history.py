"""Compact chart history without retaining full live dashboard snapshots."""

from bisect import bisect_left
from collections.abc import Iterable, Mapping
import math
from typing import Any


DEFAULT_HISTORY_RESPONSE_LIMIT = 2400


def compact_history_row(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Keep scalar chart fields; live client rows and diagnostics stay in /api/now.

    Returning a new dictionary also prevents history from retaining references to
    mutable nested objects that producers replace on every sample.
    """
    return {
        key: value for key, value in snapshot.items()
        if value is None or isinstance(value, (str, int, float, bool))
    }


def bounded_history(
    history: Iterable[Mapping[str, Any]],
    limit: int = DEFAULT_HISTORY_RESPONSE_LIMIT,
) -> list[dict[str, Any]]:
    """Return compact points across the entire retained time horizon.

    Sample nearest to evenly spaced timestamps when timestamps are valid and
    ordered. Missing or reset clocks fall back to evenly spaced row indices.
    Both endpoints survive for limits of at least two. A one-point response is
    the most recent point. Duplicate selections are omitted, so the result is
    always bounded even when samples cluster around large gaps.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("history limit must be a positive integer")
    rows = list(history)
    if len(rows) <= limit:
        return [compact_history_row(row) for row in rows]
    if limit == 1:
        return [compact_history_row(rows[-1])]

    timestamps = [row.get("ts") for row in rows]
    valid_times = all(
        isinstance(ts, (int, float)) and not isinstance(ts, bool)
        and math.isfinite(ts)
        for ts in timestamps
    )
    valid_times = valid_times and all(
        earlier <= later for earlier, later in zip(timestamps, timestamps[1:])
    ) and timestamps[-1] > timestamps[0]

    if valid_times:
        start, end = timestamps[0], timestamps[-1]
        selected = {0, len(rows) - 1}
        for slot in range(1, limit - 1):
            target = start + (end - start) * slot / (limit - 1)
            right = bisect_left(timestamps, target)
            left = max(0, right - 1)
            # bisect_left stays within bounds for interior finite targets.
            nearest = left if target - timestamps[left] <= timestamps[right] - target else right
            selected.add(nearest)
        indices = sorted(selected)
    else:
        indices = [slot * (len(rows) - 1) // (limit - 1) for slot in range(limit)]
    return [compact_history_row(rows[index]) for index in indices]
