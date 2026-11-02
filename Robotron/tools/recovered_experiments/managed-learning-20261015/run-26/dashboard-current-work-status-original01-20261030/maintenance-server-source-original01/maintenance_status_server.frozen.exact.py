"""Read-only maintenance page; Root owns exclusive port handoff to/from Main."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import os
from pathlib import Path
import signal
import stat
import time
from urllib.parse import urlsplit

LIMIT = 256 * 1024
PAGE = r'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Training maintenance</title>
<style>body{background:#101923;color:#e6eff8;font:17px system-ui;max-width:1000px;margin:32px auto;padding:0 18px}h1{font-size:29px}.note{color:#b3c4d5}.box{border:1px solid #42576a;border-radius:8px;padding:18px;margin:16px 0}dl{display:grid;grid-template-columns:110px 1fr;gap:14px}dt{font-weight:bold}dd{margin:0;white-space:pre-line}table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid #42576a;padding:8px}</style>
<h1>Training maintenance</h1><p class="note">Main training telemetry is unavailable during maintenance. This page shows published work progress, not live training metrics.</p>
<section class="box"><h2 id="stage">Loading current work…</h2><p id="stamp" class="note"></p>
<dl><dt>Why</dt><dd id="why">—</dd><dt>Waiting for</dt><dd id="wait">—</dd><dt>Next</dt><dd id="next">—</dd><dt>When</dt><dd id="when">No completion estimate has been published.</dd></dl></section>
<section class="box"><h2>Historical A1 · cap 8</h2><p class="note">Completed before this maintenance interval; these are not current readings.</p><p id="historic-time" class="note"></p><table><tbody id="historic"></tbody></table></section>
<script>
const historic = __HISTORIC__;
for (const [name, value] of historic.rows) {
  const row=document.createElement('tr'), label=document.createElement('th'), cell=document.createElement('td');
  label.textContent=name; cell.textContent=Number.isFinite(value)?value.toLocaleString(undefined,{maximumFractionDigits:3}):'Unavailable';
  row.append(label,cell); document.getElementById('historic').append(row);
}
document.getElementById('historic-time').textContent=historic.ended_unix_s?'Measurement ended '+new Date(historic.ended_unix_s*1000).toLocaleString():'';
let last=null,busy=false,failed=false;
const text=v=>typeof v==='string'?v.trim():'';
function render() {
  if (!last) { document.getElementById('stage').textContent='Work status unavailable · retrying'; return; }
  const w=last.next_work, now=Date.now()/1000, stamp=Number.isFinite(w.updated_unix_s)?w.updated_unix_s:last.updated_unix_s;
  const valid=Number.isFinite(stamp)&&stamp>0&&stamp<=now, stale=!valid||now-stamp>90;
  document.getElementById('stage').textContent=text(w.current_stage)||text(w.state).replaceAll('_',' ');
  document.getElementById('stamp').textContent=(valid?'Observed '+new Date(stamp*1000).toLocaleString():'Observation time unavailable')+((stale||failed)?' · update delayed; showing the last reported status':'');
  for(const [id,value] of [['why',text(w.detail)||text(last.detail)],['wait',text(w.waiting_for)],['next',text(w.next_stage)],['when',text(w.eta)||'No completion estimate has been published.']]) document.getElementById(id).textContent=value||'Not yet reported';
}
async function poll() {
  if(busy)return; busy=true;
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),4000);
  try {
    const response=await fetch('/api/html/next-policy-evaluation.json?t='+Date.now(),{cache:'no-store',signal:controller.signal});
    if(!response.ok)throw Error('Unavailable'); const p=await response.json(),w=p.next_work;
    if(p.schema!=='robotron-prepared-policy-screening-status-v1'||!w||typeof w!=='object'||Array.isArray(w)||!(text(w.current_stage)||text(w.state)))throw Error('Incomplete work status');
    last=p;failed=false;
  }catch(error){failed=true;}finally{clearTimeout(timer);busy=false;render();}
}
poll();setInterval(poll,5000);
</script></html>'''


def read_json(path, immutable=False):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path or path.is_symlink():
        raise ValueError('Canonical selected metadata required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or before.st_nlink != 1 or not 0 < before.st_size <= LIMIT:
            raise ValueError('Bounded owned regular metadata required')
        if immutable and stat.S_IMODE(before.st_mode) != 0o444:
            raise ValueError('Immutable historical report required')
        raw = stream.read(LIMIT + 1)
        stable = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_nlink)
        if len(raw) != before.st_size or stable(before) != stable(os.fstat(stream.fileno())) or stable(before) != stable(path.stat()):
            raise ValueError('Metadata changed during read')
    return raw, json.loads(raw)


def write_status(path, value):
    temporary = path.with_name('.' + path.name + '.tmp')
    with temporary.open('xb') as stream:
        stream.write((json.dumps(value, allow_nan=False) + '\n').encode())
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0'); parser.add_argument('--port', type=int, default=8771)
    parser.add_argument('--public', required=True, type=Path); parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--runtime', required=True, type=Path); parser.add_argument('--max-seconds', type=int, default=7200)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.max_seconds <= 7200: parser.error('Bounded port/duration required')
    args.public = args.public.absolute(); args.report = args.report.absolute(); args.runtime = args.runtime.absolute()
    if args.runtime.parent.resolve(strict=True) != args.runtime.parent: parser.error('Canonical fresh runtime required')
    raw_report, report = read_json(args.report, immutable=True)
    if not isinstance(report, dict) or report.get('schema') != 'robotron-cold-budget-arm-observation-v1' or report.get('status') != 'PASS_ENGINEERING_OBSERVATION' or report.get('arm') != 'A1' or report.get('cap') != 8:
        raise ValueError('Actual completed historical A1 cap8 PASS report required')
    fields = [('Duration (seconds)', 'seconds'), ('Game frames/sec', 'game_fps'), ('Applied optimizer updates/sec', 'applied_updates_per_s'), ('New replay inserts/sec', 'new_replay_per_s'), ('New learner replay inserts/sec', 'new_learner_replay_per_s'), ('AMP skip fraction', 'amp_skip_fraction')]
    history = dict(rows=[[title, report.get(key)] for title, key in fields], ended_unix_s=report.get('ended_unix_s'))
    if any(type(v) not in (int, float) or not math.isfinite(v) for _, v in history['rows']) or type(history['ended_unix_s']) not in (int, float) or not math.isfinite(history['ended_unix_s']) or history['ended_unix_s'] <= 0: raise ValueError('Finite historical measurements/time required')
    page = PAGE.replace('__HISTORIC__', json.dumps(history, allow_nan=False).replace('<', '\\u003c')).encode()
    args.runtime.mkdir(mode=0o700, exist_ok=False)
    pid = os.getpid(); birth = int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
    owner = dict(pid=pid, birth=birth, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), host=args.host, port=args.port, public=str(args.public), report=str(args.report), report_sha256=hashlib.sha256(raw_report).hexdigest(), started_unix_s=time.time())
    stopped = []; server = None; exit_code = 1; reason = 'failure'
    for number in (signal.SIGINT, signal.SIGTERM): signal.signal(number, lambda signum, frame: stopped.append(signum))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused): pass
        def send(self, status, body, content_type):
            self.send_response(status); self.send_header('Content-Type', content_type); self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            if status == 503: self.send_header('Retry-After', '5')
            self.end_headers()
            try: self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError): pass
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/': return self.send(200, page, 'text/html; charset=utf-8')
            if path == '/api/html/next-policy-evaluation.json':
                try:
                    raw, value = read_json(args.public)
                    if not isinstance(value, dict) or value.get('schema') != 'robotron-prepared-policy-screening-status-v1': raise ValueError('Wrong work schema')
                    return self.send(200, raw, 'application/json')
                except (OSError, ValueError): return self.send(503, b'{"available":false,"reason":"Work status temporarily unavailable"}', 'application/json')
            if path == '/api/now': return self.send(503, b'{"available":false,"reason":"Main telemetry unavailable during maintenance"}', 'application/json')
            return self.send(404, b'Not found', 'text/plain; charset=utf-8')

    class Server(HTTPServer):
        allow_reuse_address = True  # Allows old TIME_WAIT, never concurrent listeners; no SO_REUSEPORT.
        allow_reuse_port = False
        def get_request(self):
            connection, address = super().get_request(); connection.settimeout(2); return connection, address

    try:
        server = Server((args.host, args.port), Handler); server.timeout = 0.25
        write_status(args.runtime / 'owner.json', owner)
        deadline = time.monotonic() + args.max_seconds; heartbeat = 0
        while not stopped and not (args.runtime / 'STOP').exists() and time.monotonic() < deadline:
            server.handle_request()
            if time.monotonic() >= heartbeat:
                write_status(args.runtime / 'heartbeat.json', dict(owner, server_heartbeat_unix_s=time.time(), work_observation_time_rewritten=False))
                heartbeat = time.monotonic() + 2
        reason = 'signal' if stopped else 'STOP' if (args.runtime / 'STOP').exists() else 'duration_limit'
        exit_code = 0
    except BaseException as error:
        write_status(args.runtime / 'failure.json', dict(owner, error=repr(error), ended_unix_s=time.time()))
    finally:
        if server is not None: server.server_close()
        write_status(args.runtime / 'result.json', dict(owner, actual_exit=exit_code, reason=reason, listener_closed=True, ended_unix_s=time.time()))
    return exit_code


if __name__ == '__main__': raise SystemExit(main())
