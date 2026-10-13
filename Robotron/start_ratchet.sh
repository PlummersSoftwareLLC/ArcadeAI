#!/bin/bash
# Stage and launch a policy-ratchet run from the 415K checkpoint.
#
#   ./start_ratchet.sh          stage only (prints the launch command)
#   ./start_ratchet.sh --run    stage + launch in this terminal (keyboard live)
#
# What it does: stops any running trainer, restores the archived 415K
# checkpoint to latest/best, removes the phantom-best sidecar, wipes the
# replay ring + HOF (candidate-policy data must not leak across experiments),
# resets game settings to wave-1 natural, then launches with DQN_RATCHET=1.
set -euo pipefail
cd "$(dirname "$0")"

ARCH=checkpoint_archive/robotron_dqn_mature_f401M_s2541775_415k.pt
[[ -f "$ARCH" ]] || { echo "ABORT: archive missing: $ARCH"; exit 1; }

pid=$(pgrep -f 'run_dqn[.]py' | head -1 || true)
if [[ -n "$pid" ]]; then
  echo "stopping trainer $pid ..."
  kill -INT "$pid" 2>/dev/null || true
  for i in $(seq 1 45); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  kill -0 "$pid" 2>/dev/null && { kill -TERM "$pid"; sleep 5; }
fi
pgrep -f 'run_dqn[.]py' >/dev/null && { echo "ABORT: trainer still running"; exit 1; }

cp -f "$ARCH" models_dqn/robotron_dqn_latest.pt
cp -f "$ARCH" models_dqn/robotron_dqn_best.pt
rm -f models_dqn/robotron_dqn_best.pt.json \
      models_dqn/robotron_dqn_latest.pt.bak models_dqn/robotron_dqn_best.pt.bak
# The incumbent is a CLIMBED artifact (hours of gated compute) — never delete
# it silently.  Archive it and require --fresh to discard.
if [ -f models_dqn/robotron_dqn_ratchet_incumbent.pt ]; then
  ts=$(date +%Y%m%d_%H%M%S)
  mkdir -p incumbent_archive
  cp -f models_dqn/robotron_dqn_ratchet_incumbent.pt "incumbent_archive/incumbent_$ts.pt"
  echo "archived existing incumbent -> incumbent_archive/incumbent_$ts.pt"
  if [ "${1:-}" = "--fresh" ] || [ "${2:-}" = "--fresh" ]; then
    rm -f models_dqn/robotron_dqn_ratchet_incumbent.pt
    echo "--fresh: incumbent discarded, restarting from the archive checkpoint"
  else
    echo "NOTE: incumbent KEPT — boot will resume from it, not the archive."
    echo "      pass --fresh to start over from the 415K checkpoint."
  fi
fi
rm -rf models_dqn/robotron_dqn_latest_replay models_dqn/robotron_dqn_latest_replay.tmp \
       models_dqn/robotron_dqn_latest_replay_hof /dev/shm/robotron_dqn_latest_replay
cat > models_dqn/game_settings.json <<'JSON'
{"start_advanced": false, "start_level_min": 1, "epsilon_pct": -1, "expert_pct": -1, "auto_curriculum": false}
JSON

md5a=$(md5sum "$ARCH" | cut -c1-12)
md5l=$(md5sum models_dqn/robotron_dqn_latest.pt | cut -c1-12)
echo "staged: latest/best = 415K archive ($md5a == $md5l), ring+HOF wiped, settings reset"
echo
if [[ "${1:-}" == "--run" ]]; then
  exec env DQN_RATCHET=1 python3 -Xgil=0 Scripts/run_dqn.py
else
  echo "launch with:"
  echo "  cd $(pwd) && DQN_RATCHET=1 python3 -Xgil=0 Scripts/run_dqn.py"
fi
