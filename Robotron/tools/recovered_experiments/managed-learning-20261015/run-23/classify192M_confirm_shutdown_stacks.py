"""Read-only exact-message/source-order classification of retained shutdown stacks."""
import ast
import datetime
import hashlib
import json
import os
import pathlib
import re

D = pathlib.Path(__file__).resolve().parent
R = D.parents[2]
J = D.parent / 'sidecar-gpu0-192M-confirm-01'
receipt_raw = (J / 'receipt.json').read_bytes()
receipt = json.loads(receipt_raw)
assert receipt['complete'] is True
health_path = D / 'quality192M-confirm-scoreblind-health.jsonl'
health_raw = health_path.read_bytes()
assert health_raw.endswith(b'\n')
health = [json.loads(line) for line in health_raw.splitlines()]
completion_raw = (D / 'quality192M-confirm-scoreblind-health-complete.json').read_bytes()
completion = json.loads(completion_raw)
log_path = D / 'sidecar-gpu0-192M-confirm-01.log'
log_raw = log_path.read_bytes()
log = log_raw.decode('utf-8')
digest = lambda raw: hashlib.sha256(raw).hexdigest()
pattern = 'Traceback (most recent call last):'
exact = 'Inference batcher stopped before completion'
terminal_matches = list(re.finditer(r'^RuntimeError: (.*)$', log, re.M))
headers = list(re.finditer(re.escape(pattern), log))
client_matches = list(re.finditer(r'Client (\d+) error: ([^\r\n]*?)(?=Client \d+ error:|\r?\n|$)', log))
exceptions = [{'byte_offset': len(log[:m.start()].encode()),
               'line': log.count('\n', 0, m.start()) + 1,
               'text': m.group(0)} for m in terminal_matches]
log_counts = lambda row: row['runtime_log_pattern_counts'][str(log_path)]
first = next(i for i, row in enumerate(health) if log_counts(row)[pattern])
last_zero, first_alert = health[first - 1], health[first]
alerts = [{'utc': row['utc'], 'ts': row['ts'], 'issues': row['issues'],
           'log_pattern_counts': row['runtime_log_pattern_counts']}
          for row in health if row.get('issues')]

server_path = R / 'Scripts/dqn/socket_server.py'
runner_path = R / 'tools/run_frozen_sidecar.py'
server_raw, runner_raw = server_path.read_bytes(), runner_path.read_bytes()
server, runner = server_raw.decode(), runner_raw.decode()
server_tree, runner_tree = ast.parse(server), ast.parse(runner)
batcher = next(n for n in server_tree.body if isinstance(n, ast.ClassDef) and n.name == 'AsyncInferenceBatcher')
stop = next(n for n in batcher.body if isinstance(n, ast.FunctionDef) and n.name == 'stop')
string_sites = [n for n in ast.walk(server_tree) if isinstance(n, ast.Constant) and n.value == exact]
cleanup = next(n for n in runner_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'cleanup_with_timeout_evidence')
cleanup_text = ast.get_source_segment(runner, cleanup)
server_class = next(n for n in server_tree.body if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
server_stop = next(n for n in server_class.body if isinstance(n, ast.FunctionDef) and n.name == 'stop')
server_stop_text = ast.get_source_segment(server, server_stop)
cutoff = receipt['timeout_snapshot_unix_s']
other_errors = re.findall(r'^(?:[\w.]*Error|[\w.]*Exception):.*$', log, re.M)
checks = {
    'complete_valid_receipt_no_fatal_or_cleanup_error': receipt['valid'] is True and all(not receipt.get(k) for k in ('reason', 'error', 'server_error', 'inference_error', 'cleanup_errors', 'invalidity_reasons')),
    'all10_tracebacks_same10_exact_terminal_errors': len(headers) == len(terminal_matches) == 10 and all(m.group(1) == exact for m in terminal_matches) and len(other_errors) == 10,
    'all10_handle_infer_stack_frames_and_client_errors_match': log.count('line 2356, in handle_client') == log.count('line 995, in infer') == len(client_matches) == 10 and all(m.group(2) == exact for m in client_matches),
    'unique_exact_message_created_only_by_batcher_stop': len(string_sites) == 1 and stop.lineno <= string_sites[0].lineno <= stop.end_lineno and ('req.error = "' + exact + '"') in ast.get_source_segment(server, stop),
    'shutdown_event_then_cutoff_then_cleanup_source_order': cleanup_text.index('server.shutdown_event.set()') < cleanup_text.index('snapshot_unix_s = clock()') < cleanup_text.index('errors = cleanup_job('),
    'server_stop_sets_shutdown_before_batcher_stop': server_stop_text.index('self.shutdown_event.set()') < server_stop_text.index('self.inference_batcher.stop()'),
    'loaded_source_start_end_current_pins_match': all(receipt['source_hashes'][name] == receipt['ended_source_hashes'][name] == digest(raw) for name, raw in [('Scripts/dqn/socket_server.py', server_raw), ('tools/run_frozen_sidecar.py', runner_raw)]),
    'final_log_complete_prefix_bound_by_watcher': len(log_raw) == completion['log_byte_offsets'][str(log_path)],
    'first10_observed_in_single_bracket_straddling_cutoff': log_counts(last_zero)[pattern] == 0 and log_counts(first_alert)[pattern] == 10 and last_zero['ts'] < cutoff < first_alert['ts'],
    'all8_alert_rows_retained_only_exact_private_stack_pattern': len(alerts) == 8 and all(a['ts'] > cutoff and a['issues'] == ['new_main_or_private_runtime_error_log'] and all(v == (10 if p == str(log_path) and name == pattern else 0) for p, counts in a['log_pattern_counts'].items() for name, v in counts.items()) for a in alerts),
    'runtime0_cleanup16_separate_in_final_receipt': sum(receipt['actor_timeout_logs'].values()) == 0 and sum(receipt['actor_cleanup_timeout_logs'].values()) == 16,
}
report = {
    'schema': 'robotron-192M-confirm01-exact-shutdown-stack-classification-v1',
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'pass': all(checks.values()), 'checks': checks,
    'classification': 'Intentional shutdown diagnostics from stopping in-flight inference requests, not pre-shutdown inference/runtime faults.',
    'receipt_sha256': digest(receipt_raw), 'health_prefix_sha256': digest(health_raw),
    'health_prefix_bytes': len(health_raw), 'watcher_completion_sha256': digest(completion_raw),
    'private_log': {'path': str(log_path), 'bytes': len(log_raw), 'sha256': digest(log_raw), 'traceback_headers': len(headers), 'exact_terminal_errors': exceptions, 'client_ids': [int(m.group(1)) for m in client_matches]},
    'first_append_observation_bracket_utc': [last_zero['utc'], first_alert['utc']],
    'shutdown_cutoff_unix_s': cutoff, 'raw_generic_alert_rows_retained': alerts,
    'source_proof': {'server_sha256': digest(server_raw), 'runner_sha256': digest(runner_raw), 'unique_stop_message_assignment_line': string_sites[0].lineno, 'infer_rethrow_line': 995, 'handler_print_exc_line': 2429, 'batcher_stop_line': stop.lineno, 'server_stop_line': server_stop.lineno, 'runner_shutdown_boundary_line': cleanup.lineno,
                     'reasoning': 'The only producer of the exact request error is AsyncInferenceBatcher.stop(). Runner cleanup publishes shutdown_event and then its cutoff before calling cleanup_job; server.stop sets shutdown_event before stopping the batcher. The handler rethrows that request error and prints a traceback even during shutdown, but suppresses the fatal latch after shutdown_event. All ten errors are that exact stop message; final latches are empty and intentional cleanup completes.'},
    'limits': 'Log lines have no individual wall timestamps, threaded stacks interleave, and buffered stdout appears after stderr stacks. The first-append bracket straddles the cutoff, so timestamp order alone cannot classify them. Classification uses the exact exclusive stop message, reviewed source order, final latch state, complete receipt and retained raw prefix. It does not erase alerts or claim all logs have zero errors.',
}
output = D / 'quality192M-confirm01-shutdown-stack-classification.json'
with output.open('x') as file:
    json.dump(report, file, indent=2, allow_nan=False)
    file.write('\n')
    file.flush()
    os.fchmod(file.fileno(), 0o444)
    os.fsync(file.fileno())
print(json.dumps({'pass': report['pass'], 'checks': len(checks), 'failed': [k for k, v in checks.items() if not v], 'sha256': digest(output.read_bytes())}))
