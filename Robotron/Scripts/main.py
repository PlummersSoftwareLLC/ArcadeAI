#!/usr/bin/env python3
"""Compatibility launcher for Robotron AI v3.

Keeps the long-standing `python3 Scripts/main.py` entrypoint working while the
actual implementation lives in `Scripts/v3`.
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from v3.main import main as v3_main

    v3_main()


if __name__ == "__main__":
    main()
