"""Bounded read-only wait on the already captured original window identity."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
P=Path(__file__).resolve().parent
owner=json.loads((P/'execution/root-original-live-owner.json').read_bytes())
assert owner['pid']==1458186 and owner['starttime_ticks']==59776225
assert owner['invocation_id']=='9a7e5eba07574d57af712a5fe3836ad9'
script=P/'run-original-window.py'
assert hashlib.sha256(script.read_bytes()).hexdigest()=='0c568c358cf1cd442d3951bbbb7709d675da4f91bfa089980b1b8f14e4996a1f'
output=P/('root-original-wait-'+str(time.time_ns()));output.mkdir(mode=0o700)
def publish(path,raw):
    with path.open('xb') as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def value(path,v):publish(path,(json.dumps(v,indent=2,allow_nan=False)+'\n').encode())
print(json.dumps(dict(status='WAITING_ON_SAME_ORIGINAL_WINDOW',output=str(output),owner=owner)),flush=True)
start=time.monotonic();deadline=owner['starttime_ticks']/os.sysconf('SC_CLK_TCK')+5700
records=[];terminal=None;error=None
try:
    while time.monotonic()<deadline:
        index=len(records);before=time.monotonic()
        # The source-bound observer owns archive/release if the original exits.
        # Do not interrupt its bounded archive commands with a shorter wrapper timeout.
        result=subprocess.run(['/usr/bin/python3.12','-I','-B',str(script),'--observe'],capture_output=True)
        end=time.monotonic();stem=f'{index:05d}'
        publish(output/(stem+'-stdout.bin'),result.stdout);publish(output/(stem+'-stderr.bin'),result.stderr)
        record=dict(index=index,start_monotonic_s=before,end_monotonic_s=end,exit=result.returncode,
                    stdout=str(output/(stem+'-stdout.bin')),stderr=str(output/(stem+'-stderr.bin')))
        value(output/(stem+'-observation.json'),record);records.append(record)
        assert result.returncode==0,'Original observer refused; preserve and inspect, never restart'
        observed=json.loads(result.stdout);assert observed['owner']==owner
        if observed['classification']=='ORIGINAL_WINDOW_TERMINAL_CLOSED':
            terminal=observed
            print(json.dumps(dict(status='ORIGINAL_WINDOW_TERMINAL_CLOSED',original_exit=observed['original_exit'],
                result_status=(observed.get('original_result') or {}).get('status'),output=str(output))),flush=True)
            break
        assert observed['classification']=='ORIGINAL_WINDOW_LIVE'
        progress=observed.get('window_status') or {}
        print(json.dumps(dict(status='VERIFIED_SAME_ORIGINAL_LIVE',sample=index,
            elapsed_s=progress.get('elapsed_s'),learner_frames=progress.get('learner_frames'),
            learner_accepted=progress.get('learner_accepted'),both_horizons=progress.get('both_horizons'),
            applied_updates=progress.get('applied_updates'),amp_skips=progress.get('amp_skips'),
            main_clients=observed['main']['client_count'],main_fleet_fps=observed['main']['fleet_fps'],
            autosave_age_s=observed['main']['autosave_age_s'],sample_path=record['stdout'])),flush=True)
        time.sleep(min(30,max(0,deadline-time.monotonic())))
    else:error='Observation deadline only; no original terminal outcome inferred and no restart'
except BaseException as exc:
    error=repr(exc);raise
finally:
    value(output/'wait-result.json',dict(schema='robotron-root-same-original-window-bounded-wait-v1',
        owner=owner,start_monotonic_s=start,end_monotonic_s=time.monotonic(),samples=records,
        original_terminal=terminal,error=error,original_restarted=False,
        scientific_review_rerun=False,quality_qualified=False,learning_speed_gain_verified=False))
