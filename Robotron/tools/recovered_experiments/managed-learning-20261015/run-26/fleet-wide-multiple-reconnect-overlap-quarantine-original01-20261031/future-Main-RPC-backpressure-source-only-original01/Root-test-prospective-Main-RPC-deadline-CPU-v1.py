"""Exercise the prospective Lua deadline with the existing standalone CPU VM.

No MAME, sockets, production imports, model bodies, API, or service actions.
Long delays below are simulated host-clock advances, not wall-clock sleeps.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import unittest

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = Path(__file__).resolve().parent
CANDIDATE = HERE / 'main_rpc_backpressure120_v1.lua'
PARENT = ROOT / 'Scripts/main.lua'
HARNESS = ROOT / 'tools/test_socket_wait.py'
CANDIDATE_SHA = 'bc7df0d6ca18da11cd6498867a5b77e3638d8b721094264f056fe6a949d75f76'
PARENT_SHA = '2d478f7f5f8b7d954dcb22367b1367ac82c8d88d66762657df16e4a72b242b83'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    candidate = CANDIDATE.read_bytes()
    parent = PARENT.read_bytes()
    assert hashlib.sha256(candidate).hexdigest() == CANDIDATE_SHA
    assert hashlib.sha256(parent).hexdigest() == PARENT_SHA
    assert candidate.count(b'SOCKET_READ_TIMEOUT_S = 120.0') == 1
    assert candidate.replace(b'SOCKET_READ_TIMEOUT_S = 120.0',
                             b'SOCKET_READ_TIMEOUT_S = 3.5', 1) == parent
    timeout = re.search(rb'^SOCKET_READ_TIMEOUT_S = ([0-9.]+)$',
                        candidate, re.MULTILINE).group(1).decode()
    assert float(timeout) == 120.0
    spec = importlib.util.spec_from_file_location('isolated_socket_wait_cpu_harness', HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SCRIPT = CANDIDATE

    class CandidateDeadlineTests(module.SocketWaitTests):
        def long_exchange(self, body):
            actual_run = self.run_lua

            def run_actual_deadline(text, execute=True):
                assert text.count('SOCKET_READ_TIMEOUT_S = 0.01') == 1
                text = text.replace('SOCKET_READ_TIMEOUT_S = 0.01',
                                    'SOCKET_READ_TIMEOUT_S = ' + timeout, 1)
                # Existing preload-readiness shim model; accelerate only its
                # fake clock so 120 simulated seconds need fewer than1000reads.
                assert text.count('wall + 0.0002') == 2
                text = text.replace('wall + 0.0002', 'wall + 0.25')
                actual_run(text, execute=execute)

            self.run_lua = run_actual_deadline
            try:
                self.exchange_test(body, preload=True)
            finally:
                self.run_lua = actual_run

        def test_candidate_accepts_one_original_response_after_65_host_seconds(self):
            self.long_exchange(r'''
events = {{65, string.pack("bbBBBB", 2, 3, 1, 0, 1, 5)}}
local m,f,ok = process_frame_via_socket("original_state",77)
assert(ok and m==2 and f==3 and wall==65 and cpu==0)
assert(#writes==1 and frames==77 and current_socket~=nil)
assert(string.sub(writes[1],5)=="original_state" and #events==0)
''')

        def test_candidate_keeps_original_partial_reply_until_65_host_seconds(self):
            self.long_exchange(r'''
local packet=string.pack("bbBBBB",4,5,1,0,1,5)
events={{0,string.sub(packet,1,2)},{65,string.sub(packet,3)}}
local m,f,ok=process_frame_via_socket("original_partial_state",77)
assert(ok and m==4 and f==5 and wall==65 and cpu==0)
assert(#writes==1 and frames==77 and #ACTION_RX_BUFFER==0 and #events==0)
''')

        def test_candidate_hard_timeout_closes_empty_original_stream_at_120(self):
            self.long_exchange(r'''
print=function() end
events={}
local m,f,ok=process_frame_via_socket("empty_response",77)
assert(not ok and m==-1 and f==-1 and current_socket==nil)
assert(wall>=120 and wall<=120.25 and cpu==0 and frames==77)
assert(#writes==1 and #ACTION_RX_BUFFER==0)
''')

        def test_candidate_hard_timeout_discards_partial_and_does_not_adopt_late_tail(self):
            self.long_exchange(r'''
print=function() end
local packet=string.pack("bbBBBB",6,7,1,0,1,5)
events={{0,string.sub(packet,1,2)},{121,string.sub(packet,3)}}
local m,f,ok=process_frame_via_socket("late_partial",77)
assert(not ok and m==-1 and f==-1 and current_socket==nil)
assert(wall>=120 and wall<=120.25 and cpu==0 and frames==77)
assert(#writes==1 and #ACTION_RX_BUFFER==0 and #events==1)
assert(events[1][1]==121)
''')

    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(CandidateDeadlineTests))
    report = {
        'schema': 'robotron-Root-prospective-Main-Lua-deadline-CPU-v1',
        'candidate_sha256': CANDIDATE_SHA, 'parent_sha256': PARENT_SHA,
        'harness_path': str(HARNESS),
        'harness_sha256': hashlib.sha256(HARNESS.read_bytes()).hexdigest(),
        'whole_source_one_literal_inverse_exact': True,
        'long_fixture_deadline_from_actual_candidate_seconds': float(timeout),
        'tests_run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped),
        'success': result.wasSuccessful() and not result.skipped,
        'scope': 'Standalone Lua54 CPU VM and fake host clocks; no actual MAME or transport latency qualification',
        'output': stream.getvalue(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=False)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, 'w') as out:
        json.dump(report, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    print(json.dumps({key: report[key] for key in
                      ('tests_run', 'failures', 'errors', 'skipped', 'success', 'scope')}))
    raise SystemExit(0 if report['success'] else 1)


if __name__ == '__main__':
    main()
