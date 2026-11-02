"""New clock-bracket contract: real socket ordering plus independent rejections.

These guards simulate an acknowledgement producer. They cannot establish actual
MAME input application or ROM acceptance, and never run the completed v5 probe.
"""
from pathlib import Path
import importlib.util
import json
import socket
import threading
import time
import unittest

spec = importlib.util.spec_from_file_location("clock_proposal", Path(__file__).with_name("startup_response_clock_v1.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make(clock=None, **changes):
    now = time.monotonic_ns()
    config = dict(session="1" * 32, connection="2" * 32, slot=4096, epoch=1,
                  exchange=1, frame=100, checkpoint_sha256="3" * 64, generation=5,
                  admission_open_ns=now - 1_000_000_000,
                  admission_close_ns=now + 10_000_000_000)
    config.update(changes)
    if clock is not None:
        config["clock"] = clock
    return module.ResponseClock(**config)


def acknowledgement(token, **changes):
    ack = dict(token, schema="robotron-startup-clock-ack-v1", snapshot_frame=101,
               socket_ok=True, apply_ok=True, debug_bypass=False,
               held_start_before_response=False)
    ack.update(changes)
    return (json.dumps(ack) + "\n").encode()


class ClockContract(unittest.TestCase):
    def test_strict_context_and_invalid_clock_never_send(self):
        for changes in [dict(slot=0), dict(slot=4128), dict(epoch=True),
                        dict(frame=-1), dict(generation=0), dict(exchange=0),
                        dict(checkpoint_sha256="bad"), dict(frame=1 << 64),
                        dict(admission_open_ns=20, admission_close_ns=20)]:
            with self.subTest(changes=changes), self.assertRaises(module.Rejected):
                make(**changes)
        sent = []
        gate = make(clock=lambda: True)
        with self.assertRaises(module.Rejected):
            gate.send_response(lambda raw: sent.append(raw))
        self.assertFalse(sent)
        self.assertEqual(gate.state, "rejected")

    def test_real_socket_acceptance_can_precede_send_return(self):
        # The peer acknowledges while the sending callback is still blocked.
        # Thus a timestamp after sendall's wrapper returns is unsound as lower bound.
        host, peer = socket.socketpair()
        host.settimeout(2)
        peer.settimeout(2)
        received = threading.Event()
        release = threading.Event()
        remote_times, failures = [], []

        def remote():
            try:
                with peer.makefile("rb") as stream:
                    token = json.loads(stream.readline(4097))
                remote_times.append(time.monotonic_ns())
                peer.sendall(acknowledgement(token))
                received.set()
                if not release.wait(2):
                    raise AssertionError("sender never released peer")
            except BaseException as error:
                failures.append(error)
                received.set()

        thread = threading.Thread(target=remote)
        thread.start()
        try:
            gate = make()

            def send(raw):
                host.sendall(raw)
                self.assertTrue(received.wait(2))
                self.assertFalse(failures)

            gate.send_response(send)
            with host.makefile("rb") as stream:
                proof = gate.receive_snapshot(lambda: stream.readline(4097), connection="2" * 32)
            self.assertLessEqual(proof["lower_ns"], remote_times[0])
            self.assertLess(remote_times[0], proof["events"][1]["host_ns"])
            self.assertLessEqual(remote_times[0], proof["upper_ns"])
            self.assertFalse(proof["game_start_certified"])
            self.assertFalse(proof["journal_eligibility_changed"])
        finally:
            release.set()
            thread.join(3)
            host.close()
            peer.close()
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures)

    def test_whole_interval_and_exact_cutoff(self):
        for times in [(9, 11, 12), (10, 11, 20), (10, 21, 22), (12, 11, 13)]:
            with self.subTest(times=times):
                values = iter(times)
                gate = make(clock=lambda: next(values), admission_open_ns=10, admission_close_ns=20)
                with self.assertRaises(module.Rejected):
                    token = gate.send_response(lambda raw: None)
                    gate.receive_snapshot(lambda: acknowledgement(token), connection="2" * 32)
                self.assertEqual(gate.state, "rejected")
        values = iter([10, 10, 19])
        gate = make(clock=lambda: next(values), admission_open_ns=10, admission_close_ns=20)
        token = gate.send_response(lambda raw: None)
        self.assertEqual(gate.receive_snapshot(lambda: acknowledgement(token), connection="2" * 32)["upper_ns"], 19)

    def test_send_failure_and_partial_count_cannot_be_retried(self):
        def disconnect(raw):
            raise BrokenPipeError("original transport lost")
        for send in [disconnect, lambda raw: 3]:
            gate = make()
            with self.assertRaises((BrokenPipeError, module.Rejected)):
                gate.send_response(send)
            with self.assertRaises(module.Rejected):
                gate.send_response(lambda raw: None)
            with self.assertRaises(module.Rejected):
                gate.receive_snapshot(lambda: b"{}\n", connection="2" * 32)

    def test_session_policy_generation_frame_and_nonce_binding(self):
        for key, value in dict(session="4" * 32, connection="4" * 32, slot=4097,
                               epoch=2, exchange=2, frame=99, checkpoint_sha256="4" * 64,
                               generation=6, nonce="0" * 64, snapshot_frame=100).items():
            with self.subTest(key=key):
                gate = make()
                token = gate.send_response(lambda raw: None)
                with self.assertRaises(module.Rejected):
                    gate.receive_snapshot(lambda: acknowledgement(token, **{key: value}), connection="2" * 32)

    def test_failed_bypass_and_preexisting_input_are_rejected(self):
        for key, value in dict(socket_ok=False, apply_ok=False, debug_bypass=True,
                               held_start_before_response=True).items():
            with self.subTest(key=key):
                gate = make()
                token = gate.send_response(lambda raw: None)
                with self.assertRaises(module.Rejected):
                    gate.receive_snapshot(lambda: acknowledgement(token, **{key: value}), connection="2" * 32)

    def test_reconnect_and_duplicate_consumption_are_final(self):
        gate = make()
        token = gate.send_response(lambda raw: None)
        with self.assertRaises(module.Rejected):
            gate.receive_snapshot(lambda: acknowledgement(token), connection="9" * 32)
        gate = make()
        token = gate.send_response(lambda raw: None)
        gate.receive_snapshot(lambda: acknowledgement(token), connection="2" * 32)
        with self.assertRaises(module.Rejected):
            gate.receive_snapshot(lambda: acknowledgement(token), connection="2" * 32)
        self.assertEqual(gate.state, "rejected")

    def test_malformed_duplicate_extra_and_boolean_integer(self):
        for change in [lambda raw: raw[:-1], lambda raw: raw + b"{}\n",
                       lambda raw: b'{"schema":1,"schema":2}\n',
                       lambda raw: b'{"x":NaN}\n',
                       lambda raw: acknowledgement(json.loads(raw), unknown=True),
                       lambda raw: acknowledgement(json.loads(raw), generation=True),
                       lambda raw: acknowledgement(json.loads(raw), socket_ok=1)]:
            gate = make()
            token = gate.send_response(lambda raw: None)
            with self.assertRaises(module.Rejected):
                gate.receive_snapshot(lambda: change(acknowledgement(token)), connection="2" * 32)

    def test_receive_failure_keeps_attempt_terminal(self):
        gate = make()
        gate.send_response(lambda raw: None)

        def timeout():
            raise TimeoutError("no joined original snapshot")

        with self.assertRaises(TimeoutError):
            gate.receive_snapshot(timeout, connection="2" * 32)
        with self.assertRaises(module.Rejected):
            gate.receive_snapshot(lambda: b"{}\n", connection="2" * 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
