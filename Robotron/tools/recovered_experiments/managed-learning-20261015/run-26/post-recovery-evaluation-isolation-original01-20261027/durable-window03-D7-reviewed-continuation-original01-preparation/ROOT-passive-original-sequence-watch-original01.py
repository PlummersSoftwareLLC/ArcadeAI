"""Read-only watch of original continuation handles and already-public metadata."""
import json
from pathlib import Path
import time
import urllib.request

O = Path(__file__).resolve().parent
G = O.parents[3]
# Resolve the known Robotron root independently of log-directory depth.
G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
S = O.parent / 'durable-window03-D7-fixed-RCRC-study-original01'
Q = O / 'continuation-sequence-original01'
original = json.loads((O / 'ROOT-original-C1-R2-C2-sequence-launch-command.json').read_bytes())['owner']
assert (original['pid'], original['starttime_ticks']) == (509396, 14926259)

def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None

def read(path):
    if not path.exists():
        return None
    assert path.is_file() and path.suffix != '.pt' and path.stat().st_size < 4 << 20
    return json.loads(path.read_bytes())

def same(owner):
    return bool(owner and birth(owner['pid']) == owner['starttime_ticks'])

with (O / 'ROOT-passive-original-sequence-watch-original01.jsonl').open('x') as out:
    for index in range(650):
        outcome = read(Q / 'sequence-original-outcome.json')
        state = read(G / 'logs/managed-learning-20261015/state.json')
        active = state.get('active_quality_job') or {}
        leg = active.get('current_leg')
        if isinstance(leg, int):
            leg = ['R1','C1','R2','C2'][leg-1]
        public = read(G / 'html/next-policy-evaluation.json') or {}
        timing = public.get('deadline_timing') or {}
        row = dict(index=index, unix_s=time.time(), utc=time.strftime('%H:%M:%S',time.gmtime()),
                   original_sequence_live=same(original), leg=leg, stage=active.get('stage'),
                   original_scope_live=same(active.get('actual_original_scope')),
                   original_controller_live=same(active.get('actual_original_controller')),
                   sequence_terminal=outcome.get('status') if outcome else None,
                   public_state=public.get('state'), public_phase=public.get('stage'),
                   public_age_s=time.time()-public.get('updated_unix_s',time.time()),
                   remaining_s=timing.get('remaining_s'))
        if leg in ('R1','C1','R2','C2'):
            folder = S / leg
            # Native result bodies can exceed12MiB. Never open them in this watch.
            row['native_result_exists'] = (folder/'deadline-output-original01/result.json').exists()
            row['qualification_exists'] = (folder/('root-'+leg+'-independent-qualified.json')).exists()
            for label,prefix in [('native',''),('review','independent-review-')]:
                closed = read(folder/(prefix+'controller-original-result.json'))
                row[label+'_controller_exit'] = closed.get('actual_exit') if closed else None
        try:
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as response:
                api = json.load(response)
            tr = api.get('training_round') or {}
            clients = api.get('client_rows') or []
            row['main'] = dict(fps=api.get('fps'), round=tr.get('round'), active=tr.get('active'),
                completed=tr.get('completed'), train=sum(r.get('eval') is False for r in clients),
                eval=sum(r.get('eval') is True for r in clients), GB300_util=api.get('gpu1_util'))
        except Exception as error:
            row['main_read_error'] = repr(error)
        line=json.dumps(row,separators=(',',':'));out.write(line+'\n');out.flush();print(line,flush=True)
        if outcome is not None or not row['original_sequence_live']:
            break
        time.sleep(40)
