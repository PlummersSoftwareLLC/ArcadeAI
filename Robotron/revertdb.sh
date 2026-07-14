#!/usr/bin/env bash
# revertdb.sh — restore the best-EScr1M checkpoint over the latest model and
# clear the replay buffer, so the next trainer launch resumes from the record
# policy with a fresh buffer (the standard collapse-recovery procedure).
#
# What it does:
#   1. Refuses to run while the trainer is up (a graceful trainer shutdown
#      saves latest.pt + replay on exit and would clobber this restore).
#   2. Backs up the current latest checkpoint to robotron_dqn_latest.pt.pre_revert.
#   3. Copies robotron_dqn_best.pt -> robotron_dqn_latest.pt (atomic rename).
#   4. Deletes the replay buffer directory (poisoned experience re-teaches
#      the collapse; a fresh buffer refills from the restored policy's play).
#
# The best-checkpoint record sidecar (robotron_dqn_best.pt.json) is left
# untouched: the EScr1M record survives reverts by design.
#
# Usage: ./revertdb.sh [-y]     (-y skips the confirmation prompt)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$SCRIPT_DIR/models_dqn"
BEST="$MODEL_DIR/robotron_dqn_best.pt"
BEST_META="$MODEL_DIR/robotron_dqn_best.pt.json"
LATEST="$MODEL_DIR/robotron_dqn_latest.pt"
PRE_REVERT="$MODEL_DIR/robotron_dqn_latest.pt.pre_revert"
REPLAY_DIR="$MODEL_DIR/robotron_dqn_latest_replay"
# The live ring may be in tmpfs (config replay_tmpfs_dir, default /dev/shm);
# wipe that too so a revert actually clears the buffer the trainer will adopt.
TMPFS_RING="${DQN_REPLAY_TMPFS:-/dev/shm}/robotron_dqn_latest_replay"
SERVER_PORT="${DQN_SERVER_PORT:-9998}"

ASSUME_YES=0
[[ "${1:-}" == "-y" ]] && ASSUME_YES=1

# ── 1. Trainer must not be running ──────────────────────────────────────────
trainer_pids="$(pgrep -f 'run_dqn[.]py|dqn[./]main' || true)"
port_open=0
if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":${SERVER_PORT} "; then
    port_open=1
fi
if [[ -n "${trainer_pids//[[:space:]]/}" || "$port_open" -eq 1 ]]; then
    echo "error: the DQN trainer appears to be RUNNING" >&2
    [[ -n "${trainer_pids//[[:space:]]/}" ]] && echo "  trainer PID(s): $(echo "$trainer_pids" | tr '\n' ' ')" >&2
    [[ "$port_open" -eq 1 ]] && echo "  port ${SERVER_PORT} is listening" >&2
    echo "  Stop it first (Ctrl-C, let the shutdown save finish), then re-run." >&2
    echo "  Reverting under a live trainer would be undone by its exit save." >&2
    exit 1
fi

# ── 2. Sanity-check the best checkpoint ─────────────────────────────────────
if [[ ! -f "$BEST" ]]; then
    echo "error: no best checkpoint at $BEST — nothing to revert to" >&2
    exit 1
fi
best_size=$(stat -c %s "$BEST")
if (( best_size < 1000000 )); then
    echo "error: $BEST is suspiciously small (${best_size} bytes) — refusing" >&2
    exit 1
fi

record="(no sidecar)"
if [[ -f "$BEST_META" ]]; then
    record="$(tr -d '{}"' < "$BEST_META" | tr ',' '\n' | sed 's/^ *//' | paste -sd '  ' -)"
fi

echo "Revert plan:"
echo "  best     : $BEST  ($(du -h "$BEST" | cut -f1), $(date -r "$BEST" '+%Y-%m-%d %H:%M'))"
echo "  record   : $record"
echo "  latest   : $LATEST  -> backed up to $(basename "$PRE_REVERT"), then OVERWRITTEN"
if [[ -d "$REPLAY_DIR" ]]; then
    echo "  replay   : $REPLAY_DIR ($(du -sh "$REPLAY_DIR" 2>/dev/null | cut -f1)) -> DELETED"
else
    echo "  replay   : $REPLAY_DIR (not present — nothing to delete)"
fi
if [[ -d "${REPLAY_DIR}_hof" ]]; then
    echo "  hall-of-fame: ${REPLAY_DIR}_hof ($(du -sh "${REPLAY_DIR}_hof" 2>/dev/null | cut -f1)) -> PRESERVED (by design)"
fi

if [[ "$ASSUME_YES" -ne 1 ]]; then
    read -r -p "Proceed? [y/N] " answer
    [[ "${answer,,}" == "y" || "${answer,,}" == "yes" ]] || { echo "Aborted."; exit 1; }
fi

# ── 3. Backup current latest, restore best (atomic) ────────────────────────
if [[ -f "$LATEST" ]]; then
    cp -f "$LATEST" "$PRE_REVERT"
    echo "Backed up current latest -> $(basename "$PRE_REVERT")"
fi
cp -f "$BEST" "$LATEST.tmp"
mv -f "$LATEST.tmp" "$LATEST"
echo "Restored $(basename "$BEST") -> $(basename "$LATEST")"

# ── 4. Clear the replay buffer (on-disk AND tmpfs ring) ─────────────────────
for d in "$REPLAY_DIR" "$TMPFS_RING"; do
    if [[ -d "$d" ]]; then
        rm -rf "$d"
        echo "Deleted replay ring: $d"
    fi
done
# The hall of fame ("${REPLAY_DIR}_hof") is intentionally NOT deleted — it is
# the permanent peak-play anchor and must survive reverts.

echo
echo "Done. Relaunch the trainer to resume from the record policy with a"
echo "fresh buffer (expert floor lands on the config value automatically)."
