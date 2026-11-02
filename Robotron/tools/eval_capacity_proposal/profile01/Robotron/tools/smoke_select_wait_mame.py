#!/usr/bin/env python3
"""Explicit isolated MAME integration check for the optional socket wait shim.

Uses a private loopback listener, one test emulator, temporary configuration
directories and the production Lua exchange function. Never connects to 9998.
Run only after coordinating with any live experiment owner.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import time

try:
    from .build_socket_wait import build
except ImportError:
    from build_socket_wait import build


GAME = Path(__file__).resolve().parents[1]
LIBC = ctypes.CDLL(None, use_errno=True)


class Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


LIBC.clock_getcpuclockid.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
LIBC.clock_getcpuclockid.restype = ctypes.c_int
LIBC.clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(Timespec)]
LIBC.clock_gettime.restype = ctypes.c_int


def process_snapshot(pid):
    """Read Linux accounting plus the child's POSIX process CPU clock."""
    root = Path("/proc", str(pid))
    try:
        threads = []
        for task in (root / "task").iterdir():
            raw = (task / "stat").read_text()
            fields = raw[raw.rfind(")") + 2:].split()
            threads.append(dict(tid=int(task.name), user_ticks=int(fields[11]),
                                system_ticks=int(fields[12]),
                                scheduled_runtime_ns=int((task / "schedstat").read_text().split()[0]),
                                children=(task / "children").read_text().split()))
        clock_id, timestamp = ctypes.c_int(), Timespec()
        clock_error = LIBC.clock_getcpuclockid(pid, ctypes.byref(clock_id))
        cpu_ns = None
        if not clock_error and LIBC.clock_gettime(clock_id.value, ctypes.byref(timestamp)) == 0:
            cpu_ns = timestamp.tv_sec * 1000000000 + timestamp.tv_nsec
        raw = (root / "stat").read_text()
        fields = raw[raw.rfind(")") + 2:].split()
        return dict(pid=pid, exe=os.readlink(root / "exe"), parent_pid=int(fields[1]),
                    wall_s=time.perf_counter(), clock_process_cpu_ns=cpu_ns,
                    clock_getcpuclockid_error=clock_error, threads=threads)
    except (OSError, ValueError, ProcessLookupError):
        return None


def fleet_pids():
    result = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            args = [value.decode() for value in (process / "cmdline").read_bytes().split(b"\0") if value]
        except (OSError, UnicodeDecodeError):
            continue
        if args and Path(args[0]).name == "mame" and len(args) > 1 and args[1] == "robotron":
            result.append(int(process.name))
    return sorted(result)


def receive_exact(connection, length):
    chunks = bytearray()
    while len(chunks) < length:
        part = connection.recv(length - len(chunks))
        if not part:
            raise RuntimeError("test emulator disconnected before completing its request")
        chunks.extend(part)
    return bytes(chunks)


def run(output_dir: Path, *, wait_us=1000, mame="/usr/games/mame", rompath=None, delay_ms=2):
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    library = build()
    source = (GAME / "Scripts/main.lua").read_text()
    configuration = source[source.index("-- Host socket wait configuration."):
                           source.index("-- End host socket wait configuration.")]
    exchange = source[source.index("local function process_frame_via_socket("):
                      source.index("local function determine_meta_commands(")]
    registration = source[source.index("function register_frame_callback(cb)"):
                          source.index("function register_frame_done_callback(cb)")]
    cases = ([{"kind": "full", "delay_s": delay_ms / 1000}] * 50
             + [{"kind": "split", "prefix": 3, "delay_s": .002},
                {"kind": "split", "prefix": 5, "delay_s": .002},
                {"kind": "legacy", "prefix": 3}, {"kind": "legacy", "prefix": 5},
                {"kind": "timeout", "prefix": 2}])
    lua_cases = "{" + ",".join('"' + row["kind"] + '"' for row in cases) + "}"
    fixture = r'''
unpack = table.unpack
SOCKET_READ_TIMEOUT_S = 0.03
ACTION_RX_BUFFER = ""
trace_log = function() end
set_preview_stream_enabled = function() end
close_socket = function() if current_socket then current_socket:close(); current_socket = nil end end
open_socket = function() error("unexpected test reconnect") end
local tested = false
global_callback_ref = register_frame_callback(function()
    if tested then return end
    tested = true
    local ok, failure = pcall(function()
        local requested = tonumber(os.getenv("ROBOTRON_SOCKET_WAIT_US"))
        if requested > 0 then
            assert(os.getenv("ROBOTRON_SOCKET_WAIT_ACTIVE") == "select-v1", "preload marker missing")
            assert(string.find(socket_wait_description, "readiness wait", 1, true))
        else
            assert(os.getenv("ROBOTRON_SOCKET_WAIT_ACTIVE") == nil, "disabled preload advertised active")
        end
        current_socket = emu.file("rw")
        assert(current_socket:open("socket.127.0.0.1:" .. os.getenv("ROBOTRON_SOCKET_WAIT_PORT")) == nil)
        current_socket:write(string.pack(">H", 0))
        local machine_before = emu.time()
        local tick_rate = emu.osd_ticks_per_second()
        local wall_before, cpu_before = emu.osd_ticks(), os.clock()
        local kinds = CASES
        for index, kind in ipairs(kinds) do
            SERVER_DIFFICULTY = nil
            local move, fire, exchanged = process_frame_via_socket("probe-" .. tostring(index), index)
            assert(exchanged, "exchange failed at " .. tostring(index))
            assert(emu.time() == machine_before, "emulation advanced inside frame callback")
            if kind == "timeout" then
                assert(move == -1 and fire == -1 and #ACTION_RX_BUFFER == 0)
            else
                assert(move == index % 8 and fire == (index + 3) % 8,
                    "action mismatch at " .. tostring(index))
                if kind ~= "legacy" then assert(SERVER_DIFFICULTY == 5, "modern tail lost") end
            end
        end
        local wall, cpu = (emu.osd_ticks() - wall_before) / tick_rate, os.clock() - cpu_before
        local status = "packets_verified"
        local result = string.format('{"status":%q,"backend":"select-v1","lua_version":%q,"wait_us":%d,"tick_rate":%.0f,"calls":%d,"wall_s":%.9f,"process_cpu_s":%.9f,"machine_time_start_s":%.9f,"machine_time_end_s":%.9f,"frame_callback":"register_frame_callback","modern_packets":52,"legacy_packets":2,"partial_timeouts":1}',
            status, _VERSION, tonumber(os.getenv("ROBOTRON_SOCKET_WAIT_US")), emu.osd_ticks_per_second(),
            #kinds, wall, cpu, machine_before, emu.time())
        local f = assert(io.open(os.getenv("ROBOTRON_WAIT_SMOKE_OUTPUT"), "w"))
        f:write(result .. "\n"); f:close(); print("ROBOTRON_SELECT_WAIT_SMOKE " .. result)
    end)
    if not ok then
        local result = string.format('{"status":"FAILED","error":%q}', tostring(failure))
        local f = assert(io.open(os.getenv("ROBOTRON_WAIT_SMOKE_OUTPUT"), "w"))
        f:write(result .. "\n"); f:close(); print("ROBOTRON_SELECT_WAIT_SMOKE " .. result)
    end
    close_socket()
    manager.machine:exit()
end)
'''.replace("CASES", lua_cases)
    script = output_dir / f"select-wait-{wait_us}us-smoke.lua"
    script.write_text(configuration + exchange + registration + fixture)
    result_path = output_dir / f"select-wait-{wait_us}us-result.json"
    result_path.unlink(missing_ok=True)
    log_path = output_dir / f"select-wait-{wait_us}us-mame.log"
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    assert port != 9998
    listener.listen(1)
    listener.settimeout(20)
    server_results, server_errors, cpu_samples, continuous_samples = [], [], [], []
    process = None

    def sample_cpu():
        if process is None:
            return
        snapshot = process_snapshot(process.pid)
        if snapshot:
            cpu_samples.append(snapshot)

    def peer():
        try:
            with listener:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(5)
                    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    assert receive_exact(connection, 2) == b"\0\0"
                    for index, row in enumerate(cases, 1):
                        length = struct.unpack(">I", receive_exact(connection, 4))[0]
                        payload = receive_exact(connection, length)
                        assert payload == f"probe-{index}".encode()
                        if index == 1:
                            sample_cpu()
                        packet = struct.pack("bbBBBB", index % 8, (index + 3) % 8, 1, 0, 1, 5)
                        started = time.perf_counter()
                        if row["kind"] == "full":
                            time.sleep(row["delay_s"])
                            connection.sendall(packet)
                        elif row["kind"] == "split":
                            connection.sendall(packet[:row["prefix"]])
                            time.sleep(row["delay_s"])
                            connection.sendall(packet[row["prefix"]:])
                        else:
                            connection.sendall(packet[:row["prefix"]])
                        server_results.append(dict(index=index, **row,
                                                   actual_send_gap_s=time.perf_counter() - started))
                        if index == len(cases):
                            sample_cpu()
                    # Keep the final partial packet pending until the client's
                    # host-wall timeout completes; EOF would change that case.
                    connection.recv(1)
        except BaseException as error:
            server_errors.append(repr(error))

    before = fleet_pids()
    started = datetime.now(timezone.utc).isoformat()
    thread = threading.Thread(target=peer, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory(prefix="robotron-select-wait-smoke-") as temporary:
        isolated = Path(temporary)
        command = [mame, "robotron", "-rompath", str(rompath or GAME / "roms"),
                   "-nothrottle", "-sound", "none", "-video", "none", "-skip_gameinfo",
                   "-autoboot_delay", "0", "-autoboot_script", str(script), "-seconds_to_run", "2",
                   "-cfg_directory", str(isolated / "cfg"), "-nvram_directory", str(isolated / "nvram"),
                   "-inipath", str(isolated / "ini")]
        # This environment belongs solely to our one emulator subprocess.
        environment = dict(os.environ, LD_PRELOAD=str(library),
                           ROBOTRON_SOCKET_WAIT_US=str(wait_us), ROBOTRON_SOCKET_WAIT_PORT=str(port),
                           ROBOTRON_WAIT_SMOKE_OUTPUT=str(result_path))
        environment.pop("ROBOTRON_SOCKET_WAIT_ACTIVE", None)
        with log_path.open("w") as stream:
            process = subprocess.Popen(command, cwd=isolated, env=environment,
                                       stdout=stream, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 25
                while process.poll() is None:
                    snapshot = process_snapshot(process.pid)
                    if snapshot:
                        continuous_samples.append(snapshot)
                    if time.monotonic() > deadline:
                        raise TimeoutError("isolated MAME smoke timed out")
                    time.sleep(.005)
                code = process.wait()
            except TimeoutError:
                process.kill()
                process.wait()
                raise
    thread.join(timeout=6)
    after = fleet_pids()
    result = json.loads(result_path.read_text()) if result_path.exists() else None
    accounting = None
    if len(cpu_samples) == 2 and all(row["clock_process_cpu_ns"] is not None for row in cpu_samples):
        cpu_start, cpu_end = cpu_samples
        duration = cpu_end["wall_s"] - cpu_start["wall_s"]
        used = (cpu_end["clock_process_cpu_ns"] - cpu_start["clock_process_cpu_ns"]) / 1000000000
        main_start = next(row for row in cpu_start["threads"] if row["tid"] == process.pid)
        main_end = next(row for row in cpu_end["threads"] if row["tid"] == process.pid)
        main_used = (main_end["scheduled_runtime_ns"] - main_start["scheduled_runtime_ns"]) / 1000000000
        accounting = dict(window_wall_s=duration, posix_process_cpu_s=used,
                          cpu_fraction=used / duration,
                          main_thread_cpu_s=main_used, main_thread_cpu_fraction=main_used / duration,
                          other_and_retired_threads_cpu_s=max(0, used - main_used),
                          main_exe=cpu_start["exe"], pid=process.pid)
    # A short-lived MAME startup worker can consume CPU and disappear during
    # this callback. Its time stays in the process clock, so qualify the
    # socket-serving main thread and retain process/retired-thread evidence.
    cpu_valid = bool(accounting and (wait_us == 0 or accounting["main_thread_cpu_fraction"] < .35))
    verified = (code == 0 and result and result["status"] == "packets_verified" and not server_errors
                and len(server_results) == len(cases) and not thread.is_alive() and before == after
                and not Path("/proc", str(process.pid)).exists() and cpu_valid)
    receipt = dict(status="verified" if verified else "FAILED", started_utc=started,
                   completed_utc=datetime.now(timezone.utc).isoformat(), test_pid=process.pid,
                   test_exit_code=code, test_pid_gone=not Path("/proc", str(process.pid)).exists(),
                   port=port, command=command, initial_fleet_pids=before, final_fleet_pids=after,
                   unchanged_fleet=before == after, helper_path=str(library),
                   helper_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                   lua_source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                   script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
                   server_errors=server_errors, server_cases=server_results,
                   process_cpu_tick_rate=os.sysconf("SC_CLK_TCK"), cpu_samples=cpu_samples,
                   continuous_cpu_samples=continuous_samples, posix_cpu_accounting=accounting,
                   log=log_path.name, result=result)
    receipt_path = output_dir / f"select-wait-{wait_us}us-embedded-mame.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": str(receipt_path), "status": receipt["status"], "result": result,
                      "test_pid": process.pid, "test_pid_gone": receipt["test_pid_gone"],
                      "unchanged_fleet": receipt["unchanged_fleet"],
                      "posix_cpu_accounting": accounting}, indent=2))
    return 0 if verified else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--wait-us", type=int, choices=(0, 100, 1000), default=1000)
    parser.add_argument("--mame", default="/usr/games/mame")
    parser.add_argument("--rompath", type=Path)
    parser.add_argument("--delay-ms", type=float, default=2)
    args = parser.parse_args(argv)
    return run(args.output_dir, wait_us=args.wait_us, mame=args.mame, rompath=args.rompath,
               delay_ms=args.delay_ms)


if __name__ == "__main__":
    raise SystemExit(main())
