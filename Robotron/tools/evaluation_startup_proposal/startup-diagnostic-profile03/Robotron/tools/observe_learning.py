#!/usr/bin/env python3
"""Persist low-rate experiment observations while training continues."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.request

root=Path(__file__).resolve().parents[1]/'logs'/'managed-learning-20261015'
while True:
    try:
        with urllib.request.urlopen('http://localhost:8771/api/now',timeout=10) as response:
            value=json.load(response)
        value['observed_utc']=datetime.now(timezone.utc).isoformat()
        with (root/'observations.jsonl').open('a') as stream:
            stream.write(json.dumps(value)+'\n')
        (root/'latest.json').write_text(json.dumps(value,indent=2))
    except Exception as exc:
        with (root/'observer-errors.log').open('a') as stream:
            stream.write(f'{datetime.now(timezone.utc).isoformat()} {exc}\n')
    time.sleep(30)
