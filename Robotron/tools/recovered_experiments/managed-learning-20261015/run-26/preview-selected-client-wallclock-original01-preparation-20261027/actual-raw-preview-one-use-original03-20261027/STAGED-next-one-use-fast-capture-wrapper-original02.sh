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
exec env -u LD_PRELOAD /usr/bin/python3.12 -I -B /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/raw-preview-parameterized-one-use-helper-original01/exec_next_once_raw_preview_v2.py --execute --base-helper /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/role-bound-wrapper-trial-original01/exec_role_bound_mame_v1.py --fuse-helper /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/role-bound-wrapper-trial-original02-single-use/exec_role_bound_mame_once_v2.py --collector-source /home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/supervised_main_fleet_v2.py --accepted-guards /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/posttrial-slot163-authorities-and-readonly-reconciliation-original02-guard-corrections/posttrial_slot163_output_authority_v2.py --authority /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/actual-raw-preview-one-use-original03-20261027/actual-next-one-use-capture-authority-original02.json --authority-sha256 bbc2db0ea483242d5a0153c1278560cbe21d833e8007e6471634a1e76d8850d1 --expected-source-sha256 ecdb78d2843e240ba75286c6647be7b9acdf4a232dce45e6af5b1266318641c6 -- "$@"
