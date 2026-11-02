#!/usr/bin/env bash
# Opt-in wrapper: preload the readiness helper into MAME only, including respawns.
set -euo pipefail
: "${ROBOTRON_SOCKET_WAIT_LIBRARY:?Set the absolute library path from build_socket_wait.py}"
: "${ROBOTRON_SOCKET_WAIT_US:?Set a readiness interval between 100 and 10000 microseconds}"
if [[ "$ROBOTRON_SOCKET_WAIT_LIBRARY" != /* || ! -f "$ROBOTRON_SOCKET_WAIT_LIBRARY" || "$ROBOTRON_SOCKET_WAIT_LIBRARY" == *[[:space:]:]* ]]; then
    echo 'Expected an existing absolute library path without whitespace or colons' >&2
    exit 2
fi
if [[ ! "$ROBOTRON_SOCKET_WAIT_US" =~ ^([1-9][0-9]{2,3}|10000)$ ]]; then
    echo 'Readiness interval must be between 100 and 10000 microseconds' >&2
    exit 2
fi
exec env LD_PRELOAD="$ROBOTRON_SOCKET_WAIT_LIBRARY" \
    ROBOTRON_SOCKET_WAIT_PORT=9998 /usr/games/mame "$@"
