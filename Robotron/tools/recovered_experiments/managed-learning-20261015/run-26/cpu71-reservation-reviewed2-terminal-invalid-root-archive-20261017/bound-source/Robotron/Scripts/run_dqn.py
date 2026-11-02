#!/usr/bin/env python3
"""Launch script for Robotron AI DQN (branching Rainbow-lite engine).

Run from the Robotron/Scripts directory:
    python3 run_dqn.py
or, with the free-threaded build (recommended for concurrent MAME clients):
    python3 -Xgil=0 run_dqn.py

Models are written to Robotron/models_dqn/ regardless of the working directory.

CPU thread tuning (optional):
    ROBOTRON_CPU_THREADS          intra-op torch threads (default: torch native)
    ROBOTRON_CPU_INTEROP_THREADS  inter-op torch threads (default: torch native)

Unlike the v3 PPO server, DQN inference is centralised in a single batcher
thread, so torch's native multi-threading helps batched training/inference;
override the env vars above only if you need to throttle CPU usage.
"""
import sys
import os

# Ensure the Scripts directory is on the path so 'dqn' (and 'v3', which supplies
# the shared heuristic expert) are importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _configure_cpu_threads():
    intra = (os.getenv("ROBOTRON_CPU_THREADS") or "").strip()
    interop = (os.getenv("ROBOTRON_CPU_INTEROP_THREADS") or "").strip()
    if intra:
        os.environ.setdefault("OMP_NUM_THREADS", intra)
        os.environ.setdefault("MKL_NUM_THREADS", intra)
    try:
        import torch
    except Exception:
        return
    if intra:
        try:
            torch.set_num_threads(max(1, int(intra)))
        except Exception:
            pass
    if interop:
        try:
            torch.set_num_interop_threads(max(1, int(interop)))
        except Exception:
            pass


_configure_cpu_threads()

from dqn.main import main

main()
