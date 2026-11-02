"""Native subprocess checks for the opt-in TCP select readiness preload.

LD_PRELOAD is supplied only to the isolated C fixture, never this Python test
process, a trainer, or a MAME instance. Every socket test owns a fresh listener.
"""

import concurrent.futures
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import build_socket_wait
except ImportError:
    import build_socket_wait


NATIVE_FIXTURE = r'''
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "fixture check failed line %d: %s (errno=%d)\n", \
        __LINE__, #condition, errno); return 2; } } while (0)

static double clock_seconds(clockid_t clock_id) {
    struct timespec now;
    clock_gettime(clock_id, &now);
    return (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;
}

static int connect_pair(int *receiver, int *sender) {
    int listener = atoi(getenv("ROBOTRON_TEST_LISTEN_FD"));
    struct sockaddr_storage address;
    socklen_t length = sizeof(address);
    CHECK(getsockname(listener, (struct sockaddr *)&address, &length) == 0);
    *receiver = socket(address.ss_family, SOCK_STREAM, 0);
    CHECK(*receiver >= 0);
    CHECK(connect(*receiver, (struct sockaddr *)&address, length) == 0);
    *sender = accept(listener, NULL, NULL);
    CHECK(*sender >= 0);
    close(listener);
    return 0;
}

static int poll_read(int fd, int *present) {
    struct timeval timeout = {0, 0};
    fd_set reads;
    int status;
    FD_ZERO(&reads);
    FD_SET(fd, &reads);
    errno = E2BIG;
    status = select(fd + 1, &reads, NULL, NULL, &timeout);
    *present = FD_ISSET(fd, &reads);
    if (timeout.tv_sec != 0 || timeout.tv_usec != 0) {
        fprintf(stderr, "zero caller timeout was modified\n");
        return -999;
    }
    return status;
}

struct delayed_action { int fd; pthread_t target; int signal; };
static void *delayed_action(void *argument) {
    struct delayed_action *action = argument;
    struct timespec pause = {0, 3000000};
    nanosleep(&pause, NULL);
    if (action->signal)
        pthread_kill(action->target, SIGUSR1);
    else
        (void)write(action->fd, "x", 1);
    return NULL;
}

static void signal_handler(int signal) { (void)signal; }

static void *ready_thread(void *argument) {
    int fd = *(int *)argument;
    for (int i = 0; i < 200; ++i) {
        int present;
        if (poll_read(fd, &present) != 1 || !present || errno != E2BIG)
            return (void *)1;
    }
    return NULL;
}

int main(int argc, char **argv) {
    int receiver = -1, sender = -1, present, status;
    const char *mode = argc > 1 ? argv[1] : "marker";
    double wall_start = clock_seconds(CLOCK_MONOTONIC);
    double cpu_start = clock_seconds(CLOCK_PROCESS_CPUTIME_ID);
    double wall, cpu;
    if (strcmp(mode, "marker") == 0) {
        const char *marker = getenv("ROBOTRON_SOCKET_WAIT_ACTIVE");
        printf("{\"marker\":\"%s\"}\n", marker ? marker : "");
        return 0;
    }
    CHECK(connect_pair(&receiver, &sender) == 0);
    if (!strcmp(mode, "empty") || !strcmp(mode, "wrong_port")
            || !strcmp(mode, "disabled")) {
        for (int i = 0; i < 100; ++i) {
            CHECK(poll_read(receiver, &present) == 0);
            CHECK(!present && errno == E2BIG);
        }
    } else if (!strcmp(mode, "ready")) {
        CHECK(write(sender, "abcd", 4) == 4);
        for (int i = 0; i < 200; ++i) {
            CHECK(poll_read(receiver, &present) == 1);
            CHECK(present && errno == E2BIG);
        }
        char bytes[4];
        CHECK(read(receiver, bytes, sizeof(bytes)) == 4);
        CHECK(memcmp(bytes, "abcd", 4) == 0);
    } else if (!strcmp(mode, "partial")) {
        char bytes[5];
        CHECK(write(sender, "abc", 3) == 3);
        CHECK(poll_read(receiver, &present) == 1 && present);
        CHECK(read(receiver, bytes, 3) == 3);
        CHECK(poll_read(receiver, &present) == 0 && !present);
        CHECK(write(sender, "de", 2) == 2);
        CHECK(poll_read(receiver, &present) == 1 && present);
        CHECK(read(receiver, bytes + 3, 2) == 2);
        CHECK(memcmp(bytes, "abcde", 5) == 0);
    } else if (!strcmp(mode, "threads")) {
        pthread_t threads[4];
        CHECK(write(sender, "x", 1) == 1);
        for (int i = 0; i < 4; ++i)
            CHECK(pthread_create(&threads[i], NULL, ready_thread, &receiver) == 0);
        for (int i = 0; i < 4; ++i) {
            void *result;
            CHECK(pthread_join(threads[i], &result) == 0 && result == NULL);
        }
    } else if (!strcmp(mode, "eintr") || !strcmp(mode, "null_timeout")) {
        pthread_t worker;
        struct delayed_action action = {sender, pthread_self(), !strcmp(mode, "eintr")};
        struct sigaction handler;
        memset(&handler, 0, sizeof(handler));
        handler.sa_handler = signal_handler;
        sigemptyset(&handler.sa_mask);
        CHECK(sigaction(SIGUSR1, &handler, NULL) == 0);
        CHECK(pthread_create(&worker, NULL, delayed_action, &action) == 0);
        if (action.signal) {
            CHECK(poll_read(receiver, &present) == -1);
            CHECK(errno == EINTR);
        } else {
            fd_set reads;
            FD_ZERO(&reads); FD_SET(receiver, &reads);
            CHECK(select(receiver + 1, &reads, NULL, NULL, NULL) == 1);
            CHECK(FD_ISSET(receiver, &reads));
        }
        CHECK(pthread_join(worker, NULL) == 0);
    } else if (!strcmp(mode, "invalid")) {
        CHECK(close(receiver) == 0);
        CHECK(poll_read(receiver, &present) == -1 && errno == EBADF);
        receiver = -1;
    } else if (!strcmp(mode, "negative_nfds")) {
        fd_set reads;
        struct timeval timeout = {0, 0};
        FD_ZERO(&reads); FD_SET(receiver, &reads);
        CHECK(select(-1, &reads, NULL, NULL, &timeout) == -1 && errno == EINVAL);
    } else if (!strcmp(mode, "large_nfds")) {
        /* Linux accepts larger sets; the shim must avoid inspecting past its
         * own FD_SETSIZE boundary. Supply enough backing storage to libc. */
        for (int i = 0; i < 100; ++i) {
            fd_set reads[2];
            struct timeval timeout = {0, 0};
            FD_ZERO(&reads[0]); FD_ZERO(&reads[1]); FD_SET(receiver, &reads[0]);
            errno = E2BIG;
            CHECK(select(FD_SETSIZE + 1, reads, NULL, NULL, &timeout) == 0);
            CHECK(errno == E2BIG && !FD_ISSET(receiver, &reads[0]));
        }
    } else if (!strcmp(mode, "invalid_timeout")) {
        fd_set reads;
        struct timeval timeout = {0, -1};
        FD_ZERO(&reads); FD_SET(receiver, &reads);
        CHECK(select(receiver + 1, &reads, NULL, NULL, &timeout) == -1 && errno == EINVAL);
    } else if (!strcmp(mode, "nonzero")) {
        for (int i = 0; i < 20; ++i) {
            fd_set reads;
            struct timeval timeout = {0, 2000};
            FD_ZERO(&reads); FD_SET(receiver, &reads);
            CHECK(select(receiver + 1, &reads, NULL, NULL, &timeout) == 0);
            CHECK(!FD_ISSET(receiver, &reads));
            CHECK(timeout.tv_sec == 0 && timeout.tv_usec == 0);
        }
    } else if (!strcmp(mode, "pipe") || !strcmp(mode, "multifd")
            || !strcmp(mode, "writefds") || !strcmp(mode, "exceptfds")
            || !strcmp(mode, "empty_set") || !strcmp(mode, "datagram")
            || !strcmp(mode, "unconnected") || !strcmp(mode, "unix_stream")) {
        int pipes[2], extra = -1, unix_pair[2] = {-1, -1};
        CHECK(pipe(pipes) == 0);
        if (!strcmp(mode, "datagram")) {
            struct sockaddr_storage address;
            socklen_t length = sizeof(address);
            CHECK(getpeername(receiver, (struct sockaddr *)&address, &length) == 0);
            extra = socket(address.ss_family, SOCK_DGRAM, 0);
            CHECK(extra >= 0);
            CHECK(connect(extra, (struct sockaddr *)&address, length) == 0);
        } else if (!strcmp(mode, "unconnected")) {
            extra = socket(AF_INET, SOCK_STREAM, 0);
            CHECK(extra >= 0);
        } else if (!strcmp(mode, "unix_stream")) {
            CHECK(socketpair(AF_UNIX, SOCK_STREAM, 0, unix_pair) == 0);
            extra = unix_pair[0];
        }
        for (int i = 0; i < 100; ++i) {
            fd_set reads, writes, excepts;
            fd_set *write_argument = NULL, *except_argument = NULL;
            int max_fd = receiver, test_fd = receiver;
            struct timeval timeout = {0, 0};
            FD_ZERO(&reads); FD_ZERO(&writes); FD_ZERO(&excepts);
            if (!strcmp(mode, "pipe")) test_fd = pipes[0];
            if (extra >= 0) test_fd = extra;
            if (strcmp(mode, "empty_set")) FD_SET(test_fd, &reads);
            if (test_fd > max_fd) max_fd = test_fd;
            if (!strcmp(mode, "multifd")) {
                FD_SET(pipes[0], &reads);
                if (pipes[0] > max_fd) max_fd = pipes[0];
            }
            if (!strcmp(mode, "writefds")) {
                FD_SET(receiver, &writes); write_argument = &writes;
            }
            if (!strcmp(mode, "exceptfds")) except_argument = &excepts;
            errno = E2BIG;
            status = select(max_fd + 1, &reads, write_argument, except_argument, &timeout);
            CHECK(status >= 0 && errno == E2BIG);
            CHECK(timeout.tv_sec == 0 && timeout.tv_usec == 0);
            if (!strcmp(mode, "writefds")) CHECK(status == 1 && FD_ISSET(receiver, &writes));
        }
        close(pipes[0]); close(pipes[1]);
        if (extra >= 0) close(extra);
        if (unix_pair[1] >= 0) close(unix_pair[1]);
    } else {
        fprintf(stderr, "unknown fixture mode %s\n", mode);
        return 2;
    }
    wall = clock_seconds(CLOCK_MONOTONIC) - wall_start;
    cpu = clock_seconds(CLOCK_PROCESS_CPUTIME_ID) - cpu_start;
    if (receiver >= 0) close(receiver);
    close(sender);
    printf("{\"mode\":\"%s\",\"wall\":%.9f,\"cpu\":%.9f}\n", mode, wall, cpu);
    return 0;
}
'''


class SelectWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("gcc") or shutil.which("cc")
        if sys.platform != "linux" or not compiler:
            raise unittest.SkipTest("native select-wait checks require Linux and a C compiler")
        cls.temporary = tempfile.TemporaryDirectory(prefix="robotron-selectwait-test-")
        cls.cache = Path(cls.temporary.name)
        cls.path = build_socket_wait.build(cls.cache)
        source = cls.cache / "fixture.c"
        source.write_text(NATIVE_FIXTURE)
        cls.fixture = cls.cache / "fixture"
        subprocess.run([compiler, "-O2", "-std=c11", "-Wall", "-Wextra", str(source),
                        "-pthread", "-o", str(cls.fixture)],
                       check=True, capture_output=True, text=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_native(self, mode, microseconds="1000", port=None, ipv6=False):
        family = socket.AF_INET6 if ipv6 else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as listener:
            try:
                listener.bind(("::1" if ipv6 else "127.0.0.1", 0))
            except OSError as error:
                if ipv6:
                    self.skipTest(f"IPv6 loopback unavailable: {error}")
                raise
            listener.listen(4)
            actual_port = listener.getsockname()[1]
            environment = os.environ.copy()
            environment.update({
                "LD_PRELOAD": str(self.path),
                "ROBOTRON_SOCKET_WAIT_ACTIVE": "inherited-invalid-marker",
                "ROBOTRON_SOCKET_WAIT_PORT": str(actual_port) if port is None else port,
                "ROBOTRON_TEST_LISTEN_FD": str(listener.fileno()),
            })
            if port is False:
                environment.pop("ROBOTRON_SOCKET_WAIT_PORT", None)
            if microseconds is None:
                environment.pop("ROBOTRON_SOCKET_WAIT_US", None)
            else:
                environment["ROBOTRON_SOCKET_WAIT_US"] = microseconds
            if mode == "wrong_port":
                environment["ROBOTRON_SOCKET_WAIT_PORT"] = str(actual_port % 65535 + 1)
            result = subprocess.run([str(self.fixture), mode], env=environment,
                                    pass_fds=(listener.fileno(),), capture_output=True,
                                    text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout), result.stderr

    def test_strict_environment_validation_and_inherited_marker_clear(self):
        for value in (None, "", "0", "-1", "+100", " 100", "100 ", "10001", "abc",
                      "1.5", "100x", "1e3", "99999999999999999999999999999999"):
            with self.subTest(value=value):
                data, stderr = self.run_native("marker", value)
                self.assertEqual(data["marker"], "")
                self.assertEqual(stderr, "")
        for value in ("1", "100", "1000", "10000", "000100"):
            with self.subTest(value=value):
                data, _ = self.run_native("marker", value)
                self.assertEqual(data["marker"], "select-v1")

    def test_strict_port_validation(self):
        for port in ("", "0", "-1", "+9998", "65536", "9998x", " 9998"):
            with self.subTest(port=port):
                data, _ = self.run_native("marker", port=port)
                self.assertEqual(data["marker"], "")
        for port in ("1", "9998", "65535"):
            with self.subTest(port=port):
                data, _ = self.run_native("marker", port=port)
                self.assertEqual(data["marker"], "select-v1")
        data, _ = self.run_native("marker", port=False)
        self.assertEqual(data["marker"], "select-v1")

    def test_empty_target_waits_without_consuming_a_core_and_logs_once(self):
        data, stderr = self.run_native("empty")
        self.assertGreaterEqual(data["wall"], .095)
        self.assertLess(data["cpu"], data["wall"] * .35, data)
        self.assertEqual(stderr.count("[robotron-socket-wait]"), 1)
        self.assertRegex(stderr, r"pid=\d+ fd=\d+ port=\d+ interval_us=1000")

    def test_already_ready_returns_immediately_without_consuming_payload(self):
        data, stderr = self.run_native("ready", "10000")
        self.assertLess(data["wall"], .15, data)
        self.assertEqual(stderr.count("[robotron-socket-wait]"), 1)

    def test_partial_tcp_payload_is_returned_intact_and_missing_tail_waits(self):
        data, stderr = self.run_native("partial", "10000")
        self.assertGreaterEqual(data["wall"], .009)
        self.assertLess(data["wall"], .2)
        self.assertEqual(stderr.count("[robotron-socket-wait]"), 1)

    def test_ipv6_peer_port_matches(self):
        data, stderr = self.run_native("empty", ipv6=True)
        self.assertGreaterEqual(data["wall"], .095)
        self.assertEqual(stderr.count("[robotron-socket-wait]"), 1)

    def test_non_target_calls_keep_original_behavior(self):
        for mode in ("wrong_port", "pipe", "datagram", "unconnected", "unix_stream", "large_nfds",
                     "multifd", "writefds", "exceptfds", "empty_set"):
            with self.subTest(mode=mode):
                data, stderr = self.run_native(mode, "10000")
                self.assertLess(data["wall"], .2, data)
                self.assertEqual(stderr, "")

    def test_disabled_mode_does_not_wait_or_log(self):
        data, stderr = self.run_native("disabled", "0")
        self.assertLess(data["wall"], .2)
        self.assertEqual(stderr, "")

    def test_nonzero_timeout_keeps_libc_mutation_and_duration(self):
        data, stderr = self.run_native("nonzero", "10000")
        self.assertGreaterEqual(data["wall"], .035)
        self.assertLess(data["wall"], .15)
        self.assertEqual(stderr, "")

    def test_null_timeout_keeps_blocking_until_readable(self):
        data, stderr = self.run_native("null_timeout", "1000")
        self.assertGreaterEqual(data["wall"], .002)
        self.assertEqual(stderr, "")

    def test_interrupted_target_returns_eintr_without_restarting(self):
        data, stderr = self.run_native("eintr", "10000")
        self.assertGreaterEqual(data["wall"], .002)
        self.assertEqual(stderr.count("[robotron-socket-wait]"), 1)

    def test_invalid_fd_and_invalid_arguments_preserve_libc_errors(self):
        for mode in ("invalid", "negative_nfds", "invalid_timeout"):
            with self.subTest(mode=mode):
                _, stderr = self.run_native(mode, "10000")
                self.assertEqual(stderr, "")

    def test_concurrent_polls_log_once_and_keep_fdsets_local(self):
        data, stderr = self.run_native("threads", "10000")
        self.assertLess(data["wall"], .2)
        self.assertEqual(stderr.count("[robotron-socket-wait]"), 1)

    def test_cache_reuses_complete_library_without_compiler(self):
        before = self.path.stat().st_mtime_ns
        with patch.object(build_socket_wait.shutil, "which", return_value=None):
            self.assertEqual(build_socket_wait.build(self.cache), self.path)
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_concurrent_builders_publish_one_complete_library(self):
        cache = self.cache / "concurrent"
        command = [sys.executable, str(Path(build_socket_wait.__file__)),
                   "--cache-dir", str(cache)]
        def run_builder(_):
            return subprocess.run(command, capture_output=True, text=True,
                                  timeout=40, check=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(run_builder, range(4)))
        paths = {result.stdout.strip() for result in results}
        self.assertEqual(len(paths), 1)
        self.assertTrue(all(not result.stderr for result in results))
        self.assertEqual(len(list(cache.glob("*.so"))), 1)
        self.assertFalse(list(cache.glob(".socketwait-*")))
        # Confirm the concurrently published artifact can load in a new child.
        environment = os.environ.copy()
        environment.update(LD_PRELOAD=paths.pop(), ROBOTRON_SOCKET_WAIT_US="0")
        result = subprocess.run([str(self.fixture), "marker"], env=environment,
                                capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout)["marker"], "")

    def test_compile_failure_has_stderr_and_no_path(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(build_socket_wait.shutil, "which", return_value=None), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = build_socket_wait.main(["--cache-dir", str(self.cache / "no-compiler")])
        self.assertEqual(status, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("no C compiler", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
