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
exec env -u LD_PRELOAD /usr/bin/python3.12 -I -B /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/role-bound-wrapper-trial-original01/exec_role_bound_mame_v1.py --execute --manifest /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/role-bound-wrapper-trial-original01/prospective-slot163-manifest.json --manifest-sha256 68b63331a54dbe27902ba10e736c70f02ec9c1c9c7e8cfa21082550b889c4eaf --expected-source-sha256 bfff44be287802cc226470050594bf4231051db4f35f087ddaca2bb3be69becc -- "$@"
