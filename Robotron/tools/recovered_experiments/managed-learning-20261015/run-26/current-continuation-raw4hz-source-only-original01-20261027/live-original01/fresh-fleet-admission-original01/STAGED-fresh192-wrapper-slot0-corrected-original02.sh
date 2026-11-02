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
exec env -u LD_PRELOAD /usr/bin/python3.12 -I -B /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027/fresh-fleet-rolemap/slot0-preview-flag-correction-original02/exec_fresh_fleet_roles_v2.py --execute --manifest /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027/live-original01/fresh-fleet-admission-original01/actual-fresh192-manifest-slot0-corrected-original02.json --manifest-sha256 7a714971ae04c2406068a3f9bf27438374440b17a90fb8644c5ccda4afd949b0 --expected-source-sha256 d922ecfac60acaafa7e1624007a7bb1b8bb9e267277a7629d14e27098b47a94d -- "$@"
