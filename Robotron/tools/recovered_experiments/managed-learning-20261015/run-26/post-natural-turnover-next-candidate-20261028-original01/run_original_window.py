"""Enter one new prospective observational window; never restart training."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
OUT=Path(__file__).resolve().parent
SOURCE=ROOT/'tools/power_recovery/watch_replay_progress_candidate.py'
spec=importlib.util.spec_from_file_location('_new_original_window_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
plan=h.pin(OUT/'window-plan.json');data=json.loads(h.checked(plan).read_bytes())
assert not (OUT/'anchor.raw.json').exists()
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==data['source']['sha256']
pid=os.getpid();birth=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
argv=['/usr/bin/python3','-I','-B',str(SOURCE),'--plan',plan['path']]
h.put(OUT/'original-window-wrapper-intent.json',dict(pid=pid,birth=birth,source=h.pin(Path(__file__).resolve()),
    window_source=h.pin(SOURCE),plan=plan,argv_after_exec=argv,created_unix_s=time.time(),no_training_control=True,no_original_retry=True))
os.execv(argv[0],argv)
