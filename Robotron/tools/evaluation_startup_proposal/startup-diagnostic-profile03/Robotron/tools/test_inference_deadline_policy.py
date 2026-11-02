"""CPU-only integration checks for the configured serving deadline."""
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = ""

from Robotron.Scripts.dqn import socket_server


class InferenceDeadlinePolicyTests(unittest.TestCase):
    def test_actual_socket_server_passes_three_second_config_to_real_batcher(self):
        class Actor:
            @property
            def memory(self):
                raise AssertionError("The test must not inspect replay")

            def act_batch(self, states, epsilons, locked_fires=None):
                threading.Event().wait(.3)  # a healthy dispatch beyond the old 250ms limit
                return [(2, 3, False)]

            def act(self, *args, **kwargs):
                raise AssertionError("Solo fallback is forbidden")

        self.assertEqual(socket_server.RL_CONFIG.inference_request_timeout_ms, 3000.0)
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"ROBOTRON_RUN_DIR": directory}), \
                patch.object(socket_server, "AsyncReplayBuffer",
                             side_effect=AssertionError("No replay consumer")):
            server = socket_server.SocketServer("127.0.0.1", 9999, Actor(), replay_enabled=False)
            try:
                self.assertIsInstance(server.inference_batcher, socket_server.AsyncInferenceBatcher)
                self.assertEqual(server.inference_batcher.request_timeout_s, 3.0)
                lua = (Path(__file__).resolve().parents[1]/"Scripts/main.lua").read_text()
                lua_timeout = float(re.search(r"^SOCKET_READ_TIMEOUT_S\s*=\s*([0-9.]+)",
                                             lua, flags=re.MULTILINE).group(1))
                self.assertEqual(lua_timeout-server.inference_batcher.request_timeout_s, .5)
                self.assertIsNone(server.async_buffer)
                self.assertIsNone(server.server_socket)  # no listener was opened
                started = time.monotonic()
                self.assertEqual(server.inference_batcher.infer("state", 0), (2, 3, False))
                self.assertGreaterEqual(time.monotonic()-started, .25)
            finally:
                server.inference_batcher.stop()

    def test_explicit_short_deadline_still_expires_without_duplicate_solo_work(self):
        entered, release = threading.Event(), threading.Event()
        calls, results = [], []

        class Actor:
            def act_batch(self, states, epsilons, locked_fires=None):
                calls.append("batch"); entered.set()
                if not release.wait(1):
                    raise RuntimeError("Test failed to release blocked inference")
                return [(2, 3, False)]

            def act(self, *args, **kwargs):
                calls.append("solo")
                raise AssertionError("Solo fallback is forbidden")

        batcher = socket_server.AsyncInferenceBatcher(
            Actor(), max_wait_ms=0, request_timeout_ms=20)

        def infer():
            try:
                results.append(batcher.infer("state", 0))
            except Exception as error:
                results.append(error)

        handler = threading.Thread(target=infer)
        handler.start()
        try:
            self.assertEqual(batcher.request_timeout_s, .02)
            self.assertTrue(entered.wait(1))
            handler.join(.5)
            self.assertFalse(handler.is_alive())
            self.assertIsInstance(results[0], TimeoutError)
            self.assertEqual(calls, ["batch"])
        finally:
            release.set(); handler.join(1); batcher.stop()
        self.assertEqual(calls, ["batch"])


if __name__ == "__main__":
    unittest.main()
