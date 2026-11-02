"""Low-cost original-R1 status watch. Reads no individual or aggregate scores."""
import json
import os
from pathlib import Path
import time
import urllib.request

A = Path(__file__).resolve().parent
S = A.parent / 'durable-window03-D7-fixed-RCRC-study-original01'
R = S / 'R1'
receipt = json.loads((A / 'ROOT-original-launch-command-results-original01.json').read_bytes())
callback = json.loads((A / 'actual-original-R1-live-owner.json').read_bytes())
owners = dict(wrapper=receipt['wrapper_original_owner'],
              native=callback['owner'], controller=callback['controller'],
              display=receipt['passive_display_original_owner'])

def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None

def read(path):
    return json.loads(path.read_bytes()) if path.exists() else None

terminal_paths = dict(wrapper=A / 'original-R1-wrapper-terminal.json',
                      controller=R / 'controller-original-result.json',
                      native=R / 'deadline-output-original01/result.json')
anchor = read(R / 'deadline-output-original01/original-deadline-anchor.json')['anchor']
fd = os.open(A / 'ROOT-passive-R1-watch-original01.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as log:
    for index in range(115):
        terminals = {key: read(path) for key, path in terminal_paths.items()}
        status = read(R / 'deadline-output-original01/status.json') or {}
        actual = {key: birth(owner['pid']) == owner['starttime_ticks'] for key, owner in owners.items()}
        row = dict(index=index, unix_s=time.time(), utc=time.strftime('%H:%M:%S', time.gmtime()),
                   phase=status.get('phase'), status_age_s=time.time()-status.get('observed_unix_s', time.time()),
                   errors=status.get('errors'), n_selected=status.get('n_selected_first_games'),
                   n_completed=status.get('n_completed'), n_censored=status.get('n_censored'),
                   deadline_scores_sealed=status.get('deadline_scores_sealed'),
                   remaining_s=(anchor['deadline_monotonic_ns']-time.monotonic_ns())/1e9,
                   original_births_live=actual,
                   terminal={key: {k:value.get(k) for k in ('status', 'actual_exit', 'actual_controller_exit', 'complete')}
                             if value is not None else None for key,value in terminals.items()})
        try:
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=3) as response:
                api = json.load(response)
            tr = api.get('training_round', {})
            row['main'] = dict(fps=api.get('fps'), round=tr.get('round'), active=tr.get('active'),
                               completed=tr.get('completed'), api_age_s=time.time()-api['ts'])
        except Exception as error:
            row['main_read_error'] = repr(error)
        line = json.dumps(row, separators=(',', ':'))
        log.write(line+'\n')
        log.flush()
        print(line, flush=True)
        if terminals['wrapper'] is not None:
            break
        if not actual['wrapper'] or not actual['native'] or not actual['controller']:
            # A terminal file may be in flight; Root resolves the original outcome.
            break
        time.sleep(40)
