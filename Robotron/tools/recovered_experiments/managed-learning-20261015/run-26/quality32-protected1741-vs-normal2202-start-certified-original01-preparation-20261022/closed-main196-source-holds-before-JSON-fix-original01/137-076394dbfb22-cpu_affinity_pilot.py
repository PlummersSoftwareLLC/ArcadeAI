#!/usr/bin/env python3
"""Reversible, explicit CPU-affinity pilot for this repository's Robotron fleet.

Default/status performs no writes and changes no affinity:
  python Robotron/tools/cpu_affinity_pilot.py --trainer-pid 406146 --sample-seconds 2
  python Robotron/tools/cpu_affinity_pilot.py apply --trainer-pid 406146 \
      --snapshot Robotron/logs/cpu-affinity-original.json
  python Robotron/tools/cpu_affinity_pilot.py restore \
      --snapshot Robotron/logs/cpu-affinity-original.json

Apply requires all requested slots (32 by default), reserves CPUs 0-7 for the OS,
assigns slot S to CPU 8+S, and assigns every trainer thread CPUs 56-71. No other
processes, including compiler subprocesses or the MAME supervisor, are changed.
Slots come from ROBOTRON_CLIENT_SLOT, exported by startmame.sh.

Original masks and process/thread start times are durably saved before changes.
Restore skips exited/replaced processes, preserves original per-thread masks,
and gives new threads in the SAME verified process its original leader mask.
Linux has per-thread affinity, not a process-default mask; that leader mask is
the documented fallback. Newly spawned processes are outside this snapshot.
Use one pilot at a time. A restarted actor loses its pilot affinity.

Identity checks immediately precede every affinity syscall. Linux accepts a
numeric TID rather than a pidfd here, so thread exit/reuse between verification
and the syscall remains a small unavoidable kernel-API race. Disappearing tasks
are skipped; a changed process start time is never intentionally targeted.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time
import sys


ROBOTRON = Path(__file__).resolve().parents[1]
SCHEMA = "robotron-cpu-affinity-pilot-v1"
TRAINER_CPUS = set(range(56, 72))


def stat_fields(text):
    """Parse /proc stat even when the comm field contains spaces or parentheses."""
    tail = text[text.rfind(")")+2:].split()
    return dict(starttime_ticks=int(tail[19]), cpu_ticks=int(tail[11])+int(tail[12]),
                processor=int(tail[36]))


def status_fields(path):
    return dict(line.split(":", 1) for line in path.read_text().splitlines() if ":" in line)


def resolve_argument(value, cwd):
    path = Path(value)
    return (path if path.is_absolute() else cwd/path).resolve()


def identify_process(pid, kind):
    """Require current UID and exact executable/project command, never a substring."""
    directory = Path("/proc")/str(pid)
    before = stat_fields((directory/"stat").read_text())["starttime_ticks"]
    status = status_fields(directory/"status")
    uid = [int(value) for value in status["Uid"].split()]
    if uid != [os.getuid()]*4:
        raise ValueError(f"PID {pid} is not owned exclusively by the current UID")
    args = [value.decode(errors="surrogateescape") for value in
            (directory/"cmdline").read_bytes().split(b"\0") if value]
    cwd, exe = (directory/"cwd").resolve(), (directory/"exe").resolve()
    if cwd != ROBOTRON or not args or resolve_argument(args[0], cwd) != exe:
        raise ValueError(f"PID {pid} executable/cwd does not match this Robotron project")
    slot = None
    if kind == "trainer":
        python = (ROBOTRON.parent/".venv-gb300/bin/python").resolve()
        if (exe != python or len(args) != 3 or args[1] != "-Xgil=0"
                or resolve_argument(args[2], cwd) != ROBOTRON/"Scripts/run_dqn.py"):
            raise ValueError(f"PID {pid} is not the exact Robotron trainer command")
    elif kind == "mame":
        if exe != Path("/usr/games/mame").resolve() or len(args) < 2 or args[1] != "robotron":
            raise ValueError(f"PID {pid} is not the expected Robotron MAME executable")
        for flag, expected in (("-autoboot_script", ROBOTRON/"Scripts/main.lua"),
                               ("-rompath", ROBOTRON/"roms")):
            if args.count(flag) != 1 or args.index(flag)+1 >= len(args):
                raise ValueError(f"PID {pid} lacks its exact project {flag}")
            value = args[args.index(flag)+1]
            if flag == "-rompath":
                value = value.split(";", 1)[0]
            if resolve_argument(value, cwd) != expected:
                raise ValueError(f"PID {pid} uses another project's {flag}")
        # Read environment only after confirming this exact project's MAME.
        values = [item.split(b"=", 1)[1] for item in (directory/"environ").read_bytes().split(b"\0")
                  if item.startswith(b"ROBOTRON_CLIENT_SLOT=")]
        if len(values) != 1 or not values[0].isdigit():
            raise ValueError(f"PID {pid} has no unambiguous launcher client slot")
        slot = int(values[0])
    else:
        raise ValueError("Unsupported process kind")
    after = stat_fields((directory/"stat").read_text())["starttime_ticks"]
    if before != after:
        raise ProcessLookupError(f"PID {pid} changed during identity verification")
    return dict(pid=int(pid), starttime_ticks=before, uid=uid, cmdline=args,
                cwd=str(cwd), exe=str(exe), client_slot=slot)


def thread_ids(pid):
    return sorted(int(path.name) for path in (Path("/proc")/str(pid)/"task").iterdir())


def read_thread(pid, tid):
    directory = Path("/proc")/str(pid)/"task"/str(tid)
    before = stat_fields((directory/"stat").read_text())
    if int(status_fields(directory/"status")["Tgid"]) != pid:
        raise ProcessLookupError("Thread belongs to another process")
    migrations = None
    try:
        for line in (directory/"sched").read_text().splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() in ("se.nr_migrations", "nr_migrations"):
                migrations = int(value.strip())
    except (OSError, ValueError):
        pass
    after = stat_fields((directory/"stat").read_text())
    if before["starttime_ticks"] != after["starttime_ticks"]:
        raise ProcessLookupError("Thread changed during inspection")
    return dict(tid=tid, **after, migrations=migrations)


def verify_process(record):
    actual = identify_process(record["identity"]["pid"], record["kind"])
    if actual != record["identity"]:
        raise ProcessLookupError(f"PID {actual['pid']} no longer has its saved identity")
    return actual


def capture_process(pid, kind):
    identity = identify_process(pid, kind)
    record = dict(kind=kind, identity=identity)
    for _ in range(8):
        verify_process(record)
        before = thread_ids(pid)
        threads = []
        try:
            for tid in before:
                info = read_thread(pid, tid)
                mask = sorted(os.sched_getaffinity(tid))
                if read_thread(pid, tid)["starttime_ticks"] != info["starttime_ticks"]:
                    raise ProcessLookupError("Thread changed during affinity capture")
                threads.append(dict(tid=tid, starttime_ticks=info["starttime_ticks"], original_affinity=mask))
        except (FileNotFoundError, ProcessLookupError):
            continue
        if before == thread_ids(pid):
            verify_process(record)
            leader = next((thread for thread in threads if thread["tid"] == pid), None)
            if leader is None:
                raise ValueError(f"PID {pid} has no live leader for the restore default")
            record.update(threads=threads, default_original_affinity=leader["original_affinity"],
                          target_affinity=sorted(TRAINER_CPUS if kind == "trainer" else
                                                 {8+identity["client_slot"]}))
            return record
    raise RuntimeError(f"PID {pid} thread set did not stabilize; no changes made")


def boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def make_plan(trainer_pid, actors=32):
    processes = [capture_process(trainer_pid, "trainer")]
    for path in sorted(Path("/proc").iterdir(), key=lambda item: int(item.name) if item.name.isdigit() else -1):
        if not path.name.isdigit():
            continue
        try:
            args = (path/"cmdline").read_bytes().split(b"\0")
            if len(args) < 2 or args[1] != b"robotron":
                continue
            processes.append(capture_process(int(path.name), "mame"))
        except (OSError, ValueError):
            continue
    processes[1:] = sorted(processes[1:], key=lambda record: record["identity"]["client_slot"])
    slots = [record["identity"]["client_slot"] for record in processes[1:]]
    problems = []
    if sorted(slots) != list(range(actors)):
        problems.append(f"Expected exactly slots 0-{actors-1}; observed {slots}")
    online = set(range(os.cpu_count() or 0))
    if online != set(range(72)):
        problems.append("This pilot requires the specified 72-CPU host (0-71)")
    for record in processes:
        mask = set(record["target_affinity"])
        if not mask or not mask.issubset(online):
            problems.append(f"PID {record['identity']['pid']} target CPUs are unavailable")
    return dict(schema=SCHEMA, created_utc=datetime.now(timezone.utc).isoformat(),
                robotron_dir=str(ROBOTRON), uid=os.getuid(), boot_id=boot_id(),
                trainer_pid=trainer_pid, actor_count=actors, reserved_os_cpus=list(range(8)),
                state="prepared", ready=not problems, problems=problems, processes=processes)


def atomic_json(path, value, *, exclusive=False):
    """Publish a complete fsynced file; initial snapshots cannot overwrite a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name+".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def set_verified_affinity(record, info, mask):
    verify_process(record)
    current = read_thread(record["identity"]["pid"], info["tid"])
    if current["starttime_ticks"] != info["starttime_ticks"]:
        raise ProcessLookupError("Thread identity changed before affinity syscall")
    os.sched_setaffinity(info["tid"], set(mask))


def restore_process(record):
    """Restore every current task, checking original thread identity before reuse."""
    pid = record["identity"]["pid"]
    try:
        verify_process(record)
    except (OSError, ValueError) as exc:
        return dict(pid=pid, skipped=str(exc), changed_threads=0)
    originals = {thread["tid"]: thread for thread in record["threads"]}
    changed, new, skipped = set(), set(), []
    for _ in range(8):
        verify_process(record)
        before = thread_ids(pid)
        complete = True
        for tid in before:
            try:
                info = read_thread(pid, tid)
                original = originals.get(tid)
                known = original and original["starttime_ticks"] == info["starttime_ticks"]
                mask = original["original_affinity"] if known else record["default_original_affinity"]
                if not known:
                    new.add(tid)
                if set(os.sched_getaffinity(tid)) != set(mask):
                    set_verified_affinity(record, info, mask)
                    changed.add(tid)
                    if set(os.sched_getaffinity(tid)) != set(mask):
                        raise RuntimeError(f"PID {pid} TID {tid} restore mask did not match")
            except (FileNotFoundError, ProcessLookupError) as exc:
                skipped.append(dict(tid=tid, reason=str(exc)))
                complete = False
        if complete and before == thread_ids(pid):
            return dict(pid=pid, changed_threads=len(changed), new_threads_using_leader_default=sorted(new),
                        skipped_threads=skipped)
    raise RuntimeError(f"PID {pid} threads did not stabilize during restore")


def validate_snapshot(snapshot):
    if (snapshot.get("schema") != SCHEMA or snapshot.get("robotron_dir") != str(ROBOTRON)
            or snapshot.get("uid") != os.getuid() or snapshot.get("boot_id") != boot_id()):
        raise ValueError("Snapshot belongs to another schema/project/user/boot")
    if not snapshot.get("processes"):
        raise ValueError("Snapshot has no processes")
    for record in snapshot["processes"]:
        if record["kind"] not in ("trainer", "mame"):
            raise ValueError("Snapshot has an unsupported process kind")
        for mask in [record["default_original_affinity"]]+[thread["original_affinity"] for thread in record["threads"]]:
            if not mask or any(type(cpu) is not int or not 0 <= cpu < 72 for cpu in mask):
                raise ValueError("Snapshot has an invalid original affinity")


def restore_snapshot(snapshot, path):
    validate_snapshot(snapshot)
    results, errors = [], []
    for record in snapshot["processes"]:
        try:
            results.append(restore_process(record))
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(dict(pid=record["identity"]["pid"], error=str(exc)))
    snapshot.update(state="restore_failed" if errors else "restored", restore_results=results,
                    restore_errors=errors, restored_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(path, snapshot)
    if errors:
        raise RuntimeError(f"Restore incomplete; inspect {path}")
    return snapshot


def apply_plan(plan, path):
    if not plan["ready"]:
        raise ValueError("Pilot is not ready: "+"; ".join(plan["problems"]))
    # Refresh all masks immediately before the durable snapshot. Status/runtime
    # sampling may have taken place earlier, and tasks can be created meanwhile.
    for record in plan["processes"]:
        verify_process(record)
    for _ in range(8):
        refreshed = [capture_process(record["identity"]["pid"], record["kind"])
                     for record in plan["processes"]]
        if any(current["identity"] != original["identity"]
               for current, original in zip(refreshed, plan["processes"])):
            raise ProcessLookupError("A process changed while refreshing the snapshot; no changes made")
        if all(thread_ids(record["identity"]["pid"]) == [thread["tid"] for thread in record["threads"]]
               for record in refreshed):
            plan["processes"] = refreshed
            break
    else:
        raise RuntimeError("Fleet thread sets did not stabilize before snapshot; no changes made")
    atomic_json(path, plan, exclusive=True)
    try:
        for record in plan["processes"]:
            pid, mask = record["identity"]["pid"], set(record["target_affinity"])
            for _ in range(8):
                verify_process(record)
                before = thread_ids(pid)
                for tid in before:
                    try:
                        set_verified_affinity(record, read_thread(pid, tid), mask)
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                if before == thread_ids(pid) and all(os.sched_getaffinity(tid) == mask for tid in before):
                    break
            else:
                raise RuntimeError(f"PID {pid} did not stabilize at its requested affinity")
        plan.update(state="applied", applied_utc=datetime.now(timezone.utc).isoformat())
        atomic_json(path, plan)
        return plan
    except BaseException:
        # Durable original masks exist even if rollback fails or the tool dies.
        restore_snapshot(plan, path)
        raise


def runtime_sample(processes, seconds):
    def capture():
        result = {}
        for record in processes:
            try:
                verify_process(record)
                pid = record["identity"]["pid"]
                for tid in thread_ids(pid):
                    try:
                        info = read_thread(pid, tid)
                        result[(pid, tid, info["starttime_ticks"])] = info
                    except (FileNotFoundError, ProcessLookupError):
                        pass
            except (OSError, ValueError):
                pass
        return result
    before = capture(); started = time.monotonic()
    time.sleep(seconds)
    after = capture(); elapsed = time.monotonic()-started
    ticks = os.sysconf("SC_CLK_TCK")
    summaries = []
    for record in processes:
        pid = record["identity"]["pid"]
        keys = [key for key in before.keys() & after.keys() if key[0] == pid]
        migrations = [after[key]["migrations"]-before[key]["migrations"] for key in keys
                      if before[key]["migrations"] is not None and after[key]["migrations"] is not None]
        summaries.append(dict(pid=pid, cpu_percent=sum(after[key]["cpu_ticks"]-before[key]["cpu_ticks"]
            for key in keys)/ticks/elapsed*100, migrations=sum(migrations) if migrations else None,
            matched_threads=len(keys), new_threads=sum(key[0] == pid and key not in before for key in after),
            lost_threads=sum(key[0] == pid and key not in after for key in before)))
    return dict(elapsed_s=elapsed, clock_ticks_per_second=ticks, processes=summaries)


def cpus_text(cpus):
    values = sorted(set(cpus)); groups = []
    for cpu in values:
        if groups and cpu == groups[-1][-1]+1:
            groups[-1].append(cpu)
        else:
            groups.append([cpu])
    return ",".join(str(group[0]) if len(group) == 1 else f"{group[0]}-{group[-1]}" for group in groups)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", nargs="?", default="status", choices=("status", "apply", "restore"))
    parser.add_argument("--trainer-pid", type=int, default=406146)
    parser.add_argument("--actors", type=int, choices=(16, 32), default=32)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--sample-seconds", type=float, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not 0 <= args.sample_seconds <= 30:
            raise ValueError("CPU sample duration must be between 0 and 30 seconds")
        if args.action == "restore":
            if args.snapshot is None:
                raise ValueError("restore requires --snapshot")
            result = restore_snapshot(json.loads(args.snapshot.read_text()), args.snapshot)
        else:
            result = make_plan(args.trainer_pid, args.actors)
            if args.sample_seconds:
                result["runtime_sample"] = runtime_sample(result["processes"], args.sample_seconds)
            if args.action == "apply":
                if args.snapshot is None:
                    raise ValueError("apply requires a new --snapshot path")
                result = apply_plan(result, args.snapshot)
        if args.json:
            print(json.dumps(result, indent=2, allow_nan=False))
        else:
            print(f"{args.action}: {result['state']} | trainer {result['trainer_pid']} | "
                  f"actors {len(result['processes'])-1}/{result['actor_count']}")
            for record in result["processes"]:
                identity = record["identity"]
                label = "trainer" if record["kind"] == "trainer" else f"MAME slot {identity['client_slot']}"
                originals = sorted({cpus_text(thread["original_affinity"]) for thread in record["threads"]})
                print(f"  {label}: PID {identity['pid']}, {len(record['threads'])} threads, "
                      f"original {';'.join(originals)} -> pilot {cpus_text(record['target_affinity'])}")
            for problem in result.get("problems", []):
                print(f"  Not ready: {problem}")
            for sample in result.get("runtime_sample", {}).get("processes", []):
                print(f"  CPU PID {sample['pid']}: {sample['cpu_percent']:.1f}%, "
                      f"migrations {sample['migrations']}, matched threads {sample['matched_threads']}")
            if args.snapshot:
                print(f"  Snapshot: {args.snapshot}")
            if args.action == "restore":
                for item in result.get("restore_results", []):
                    print(f"  Restore PID {item['pid']}: {item}")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f"Affinity pilot rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
