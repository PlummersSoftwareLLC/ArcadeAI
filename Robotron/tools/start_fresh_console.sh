#!/usr/bin/env bash
# Explicit reset: stop workers, delete learned state, then log to the chosen console.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
console="${1:-/dev/tty}"
[[ -w "$console" ]] || { echo "Console is not writable: $console" >&2; exit 1; }
if pgrep -f '[p]ython.*Scripts/run_dqn.py' >/dev/null; then
    echo 'Stop the running trainer before resetting.' >&2
    exit 1
fi
systemctl --user stop robotron-mame robotron-trainer
./startmame.sh -kill
# Include checkpoints, best models, optimizer state, settings, replay and both HOF banks.
rm -rf -- models_dqn /dev/shm/robotron_dqn_latest_replay
mkdir -p models_dqn
export ROBOTRON_DQN_MODEL_DIR="$PWD/models_dqn"
export DQN_RATCHET=0
export ROBOTRON_RUN_DIR="$PWD/logs/run-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$ROBOTRON_RUN_DIR"
# Remain in the foreground of our own PTY; mirror output into the user's SSH console.
./starttrainer.sh 2>&1 | tee "$ROBOTRON_RUN_DIR/console.log" "$console"
