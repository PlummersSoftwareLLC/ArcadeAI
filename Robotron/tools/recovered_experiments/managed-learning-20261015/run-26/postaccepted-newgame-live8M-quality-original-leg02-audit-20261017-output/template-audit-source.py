#!/usr/bin/env python3
"""Prepared, unexecuted original-journal leg audit. --execute requires owner GO.

Default invocation only prints the proposed read-only audit inputs. This tool
never launches, signals, imports a learner, creates a GPU context, publishes a
policy, or decides a four-leg campaign. Its only writes are a NEW audit directory.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys

sys.dont_write_bytecode = True


SLOTS = list(range(4096, 4112))
TEMPLATE_SHA256 = "47debecaf6a851d00b7d8717cdb342a9b551fe197e659a0c04594195412f7044"
RUNBOOK_SHA256 = "ffd99dc1e4b006ea99e359114b45f55774a83f94bc9867414c969466ac10d7e6"
VERIFIER_SHA256 = "ea6ccfcd62e2683641475634ba1647856a988691a6cede3dbeda629dd03ba56b"
BASE_VERIFIER_SHA256 = "7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead"
REFERENCE_SHA256 = "ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963"
TARGET = 452629023
GAME = Path("/home/dave/source/repos/ArcadeAI/Robotron")
CAMPAIGN_ROOT = GAME / "logs/managed-learning-20261015"
CAMPAIGN_PREFIX = "quality-384M-vs-448M-"
CPU_VERIFIER = GAME / "logs/managed-learning-20261015/run-26/managed-candidate-checkpoint-CPU-verifier-proposal-20261017/verify_candidate_checkpoint.py"
PLAN = "PLAN ONLY: no inputs read/imported. Future --execute audits only an explicitly finished/returncode0 leg1..4 of a root-bound quality-384M-vs-448M-* campaign with actual candidate bytes/hash, plan, generic CPU job/proof/source bindings; all4 diagnosticsTRUE,1200/2400,min50/all16/fulltails. No campaign qualification or launch."
EVALUATOR_NAMES = {"tools/run_frozen_sidecar.py", "tools/sidecar_boot.py", "Scripts/main.lua", "Scripts/robotron_socket_wait.c"} | {
    "Scripts/dqn/"+name for name in ("config.py", "model.py", "actor_tags.py", "socket_server.py", "game_journal.py", "managed_measurement.py", "inference_actor.py", "nstep_buffer.py")}
EXECUTION_NAMES = {str(GAME/"tools"/name) for name in ("run_quality_campaign.py", "run_frozen_sidecar.py", "compare_sidecar_measurements.py", "compare_frozen_measurements.py")}
BOUNDARY_SOURCES = {
    "Scripts/dqn/socket_server.py": "d99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214",
    "Scripts/dqn/game_journal.py": "10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0",
    "tools/run_frozen_sidecar.py": "cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90",
    "tools/run_quality_campaign.py": "574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128"}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def lines(raw):
    require(not raw or raw.endswith(b"\n"), "Partial final JSONL record")
    return [decode(row) for row in raw.splitlines()]


def indexed(rows, description):
    result = {}
    for row in rows:
        key = row["journal_game_id"]
        require(isinstance(key, str) and key and key not in result,
                f"Missing/duplicate {description} ID: {key}")
        result[key] = row
    return result


def immutable(path, payload):
    raw = payload if isinstance(payload, bytes) else (
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def validate_future_plan(plan, args, directory):
    require(directory == args.campaign and directory.parent == CAMPAIGN_ROOT
            and directory.name.startswith(CAMPAIGN_PREFIX) and len(directory.name) > len(CAMPAIGN_PREFIX)
            and plan["output_directory"] == str(directory), "Wrong future448 campaign namespace")
    require(set(plan["evaluator_source_hashes"]) == EVALUATOR_NAMES
            and set(plan["execution_source_hashes"]) == EXECUTION_NAMES, "Require all12+4 source bindings")
    for name, expected in BOUNDARY_SOURCES.items():
        group, key = ("execution_source_hashes", str(GAME / name)) if name == "tools/run_quality_campaign.py" else ("evaluator_source_hashes", name)
        require(plan[group][key] == expected, "Reviewed common boundary source differs: " + name)
    require(plan["execution_source_hashes"][str(GAME / "tools/run_frozen_sidecar.py")]
            == BOUNDARY_SOURCES["tools/run_frozen_sidecar.py"], "Execution/evaluator sidecar differs")
    checkpoints = plan["checkpoints"]
    require(checkpoints["reference"]["sha256"] == REFERENCE_SHA256
            and checkpoints["candidate"]["sha256"] == args.candidate_sha256, "Protected/reference or actual future candidate differs")
    for role, source in (("reference", GAME / "models_dqn/managed-incumbents/fresh3-384M-confirmed.pt"),
                         ("candidate", GAME / "models_dqn/managed-checkpoints/fresh3-448M.pt")):
        require(checkpoints[role]["source"] == str(source)
                and checkpoints[role]["snapshot"] == str(directory / "checkpoints" / (role + ".pt")), "Checkpoint path differs")
    require([spec["index"] for spec in plan["legs"]] == [1,2,3,4]
            and [spec["role"] for spec in plan["legs"]] == ["reference","candidate","reference","candidate"], "Four fresh fixed legs required")
    common = None
    for spec in plan["legs"]:
        job = spec["job"]
        require(job["checkpoint"] == checkpoints[spec["role"]]["snapshot"], "Leg job checkpoint differs from planned role snapshot")
        require(job["game_boundary_diagnostics"] is True and "--game-boundary-diagnostics" in spec["command"], "Diagnostics must be explicitlyTRUE all4 legs")
        require(job["cohort_s"] == 1200 and job["actors"] == 16 and job["actor_slots"] == SLOTS
                and job["epsilon"] == job["expert_ratio"] == 0 and job["difficulty"] == 5
                and job["start_level"] == 1 and job["replay_enabled"] is False and job["fp16"] is False,
                "Frozen game/admission policy differs")
        require(job["device"] == "cuda" and job["gpu_uuid"] == "GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0"
                and job["host"] == "127.0.0.1" and job["port"] == 9999 and job["wait_us"] == 1000
                and job["inference_backend"] == "inductor" and job["inference_max_batch_size"] == 16
                and job["cpu_threads"] == 2 and job["timeout_s"] == 2400, "Frozen backend/pacing profile differs")
        signature = {key: value for key, value in job.items() if key not in ("checkpoint", "directory", "label")}
        require(common is None or signature == common, "Planned common runtime/pacing policy differs across legs")
        common = signature
    gate = plan["precommit"]
    require(gate["min_full_games_per_leg"] == 50 and gate["max_attempts_per_leg"] == 1
            and gate["include_every_admitted_game"] is True and gate["include_full_completion_tail"] is True
            and gate["admission_extensions"] is False, "Admission protocol changed")
    require(gate["new_same_length_reference_cohorts"] is True and gate["historical_or_interrupted_receipts_used"] is False
            and gate["all_actor_slots"] == SLOTS, "Fresh reference/slot precommit differs")
    require(gate["candidate_gate"] == dict(each_candidate_individually=True,
        reference="all games pooled from both fresh reference legs",minimum_mean_ratio=1.05,minimum_median_ratio=1.0),
        "Separate candidate qualification gates changed")


def validate_cpu_proof(proof, args):
    require(proof["schema"] == "robotron-managed-candidate-checkpoint-CPU-result-v1"
            and proof["status"] == "PASS" and proof["script"]["sha256"] == VERIFIER_SHA256
            and proof["base_verifier"]["sha256"] == BASE_VERIFIER_SHA256
            and proof["sha256"] == args.candidate_sha256 and proof["bytes"] == args.candidate_bytes,
            "Matching actual448 candidate-wrapper PASS required")
    require(proof["job_file"]["sha256"] == args.cpu_job_sha256,
            "Actual candidate CPU root job differs")
    source, copied = proof["source_before"], proof["verification_copy"]
    require(source["sha256"] == copied["sha256"] == args.candidate_sha256
            and source["bytes"] == copied["bytes"] == args.candidate_bytes
            and source["path"] == str(GAME / "models_dqn/managed-checkpoints/fresh3-448M.pt")
            and (source["device"], source["inode"]) != (copied["device"], copied["inode"])
            and copied["mode"] == "0o444" and copied["nlink"] == 1
            and proof["bound_files"]["source_checkpoint"] == source
            and proof["bound_files"]["root_readonly_verification_copy"] == copied,
            "CPU source/copy identity differs")
    root_job = proof["root_job"]
    candidate = root_job["candidate"]
    require(root_job["schema"] == "robotron-managed-candidate-checkpoint-CPU-job-v1"
            and root_job["verifier_sha256"] == VERIFIER_SHA256
            and root_job["base_verifier_sha256"] == BASE_VERIFIER_SHA256
            and root_job["experiment"] == "best10M-fresh3-eps10-cap8-nosmooth"
            and root_job["source"]["path"] == source["path"]
            and root_job["source"]["sha256"] == args.candidate_sha256
            and root_job["source"]["bytes"] == args.candidate_bytes
            and candidate["tag"] == "fresh3-448M" and candidate["target_learner_frames"] == TARGET,
            "CPU proof describes another candidate/tag/target")
    gate = proof["candidate_gate"]
    floor = proof["clock_floor"]
    require(gate["tag"] == "fresh3-448M" and gate["target"] == TARGET
            and gate["checkpoint"] == source["path"]
            and gate["experiment"] == root_job["experiment"]
            and gate["trigger_snapshot"]["client_count"] == 192
            and set(floor) == {"training_steps", "optimized_samples", "learner_frame_count", "frame_count"}
            and all(type(floor[key]) is int and floor[key] > 0
                    and floor[key] == gate["trigger_snapshot"][key]
                    and proof["clocks"][key] >= floor[key] for key in floor)
            and floor["learner_frame_count"] >= TARGET,
            "Saved candidate predates authentic gate four-clock floor or448 target")
    require(proof["actual_restore_or_optimizer_step"] is False
            and proof["actual_quality_qualification"] is False,
            "CPU structural verification must not claim restore or quality")


def validate_original_context(entry, row):
    # Complete dictionary identity includes every old/new diagnostic primitive;
    # unknown fields are neither stripped nor normalized for comparison.
    require(entry["context"] == row["start_context"], "Admission/start policy or diagnostic context differs")
    context = entry["context"]
    diagnostic = context.get("game_boundary_diagnostics")
    require(isinstance(diagnostic, dict) and diagnostic.get("schema") == "robotron-game-boundary-inputs-v1"
            and diagnostic.get("journal_start_reason") == entry["start_reason"], "Missing bound boundary diagnostics")
    require({"previous_accepted_wire", "current_wire", "classifier_previous", "last_start_frame_before",
             "last_start_frame_after", "recent_start", "classifier_new_game", "classifier_verdict"} <= set(diagnostic),
            "Incomplete actual boundary diagnostic context")


def classify_actor_lines(actor_lines, address, cutoff, before, measured):
    opened = [index + 1 for index, line in enumerate(actor_lines)
              if line == "Socket connection opened to " + address]
    initialized = [index + 1 for index, line in enumerate(actor_lines)
                   if line == "MAME interface initialized."]
    late_timeouts = [dict(line_number=index + 1, unix_s=timestamp)
                     for index, line in enumerate(actor_lines)
                     if "[SOCKET ACTION TIMEOUT]" in line
                     for match in [re.search(r"\bunix_s=(\d+)\b", line)]
                     if match is not None
                     for timestamp in [int(match[1])] if timestamp > int(cutoff)]
    allowed, actor_issues = [], []
    for number, line in enumerate(actor_lines, 1):
        if not re.search(r"Traceback|\b\w*(?:Error|Exception)\b|\bfailed\b|\bunavailable\b|\bunable\b",
                         line, re.I):
            continue
        kind, evidence = None, {}
        if (line == "ALSA lib seq_hw.c:528:(snd_seq_hw_open) open /dev/snd/seq failed: Permission denied"
                and number == 2 and initialized and opened
                and number < min(initialized) < min(opened)):
            kind = "exact_disabled_sound_sequencer_startup_diagnostic"
            evidence = dict(interface_initialized_line=min(initialized),
                            first_successful_connection_line=min(opened),
                            source="run_frozen_sidecar.mame_spec: -sound none; Lua initializes interface before initial open_socket")
        elif line == "Socket open failed: " + address + " (Connection refused)":
            preceding = [event for event in late_timeouts if event["line_number"] < number
                         and opened and min(opened) < event["line_number"]
                         and not any(event["line_number"] < success < number for success in opened)]
            if preceding and before == measured == 0:
                kind = "owned_post_cutoff_timeout_close_then_refused_reconnect"
                evidence = dict(preceding_post_cutoff_timeout=preceding[-1],
                                cutoff_unix_s=cutoff, before_shutdown=before,
                                runtime_timeouts=measured,
                                source="main.lua: timed receive timeout -> close_socket -> one-second retry -> open_socket print")
        if kind is None:
            actor_issues.append(dict(line_number=number, text=line))
        else:
            allowed.append(dict(line_number=number, text=line, kind=kind, evidence=evidence))
    return allowed, actor_issues


def audit(args):
    require(digest(__file__) == args.source_sha256, "Auditor source SHA mismatch")
    require(args.campaign.parent == CAMPAIGN_ROOT and args.campaign.name.startswith(CAMPAIGN_PREFIX)
            and args.game == GAME, "Only the future448 namespace/game is allowed")
    require(args.output.is_absolute(), "Explicit absolute new audit output required")
    directory = args.campaign.resolve(strict=True)
    output = args.output.resolve()
    require(not output.exists() and not output.is_relative_to(directory),
            "Audit output must be new and outside the campaign")
    output.mkdir(mode=0o700)
    artifacts, payloads = {}, {}

    def capture(path, name):
        raw = Path(path).read_bytes()
        immutable(output / name, raw)
        artifacts[str(path)] = {"sha256": hashlib.sha256(raw).hexdigest(), "copy": name}
        payloads[str(path)] = raw
        return raw

    report = dict(schema="robotron-independent-original-journal-leg-v1",
                  audited_utc=datetime.now(timezone.utc).isoformat(),
                  campaign_directory=str(directory), leg=args.leg,
                  campaign_outcome="not_assessed", artifacts=artifacts,
                  scope="Completed-leg validity only; no quality comparison, speed claim, or live mutation.")
    try:
        for path, name in ((Path(__file__).resolve(), "audit-source.py"),
                           (Path(__file__).resolve().with_name("README.txt"), "audit-README.txt")):
            capture(path, name)
        report["audit_provenance"] = dict(
            sources={str(path): artifacts[str(path)] for path in
                     (Path(__file__).resolve(), Path(__file__).resolve().with_name("README.txt"))},
            python_executable=sys.executable, python_version=sys.version,
            dont_write_bytecode=sys.dont_write_bytecode)
        run = Path(__file__).resolve().parent.parent
        for path, expected, name in (
            (Path(__file__).with_name("template-audit-source.py"), TEMPLATE_SHA256, "template-audit-source.py"),
            (run / "future448M-quality-current-source-readiness-independent-20261017/source-readiness-receipt.json", RUNBOOK_SHA256, "future448-source-readiness.json"),
            (CPU_VERIFIER, VERIFIER_SHA256, "candidate-verifier-source.py")):
            require(digest(path) == expected, "Auditor source preparation provenance changed")
            capture(path, name)
        report["audit_provenance"]["source_template"] = dict(
            template_sha256=TEMPLATE_SHA256, runbook_sha256=RUNBOOK_SHA256, verifier_sha256=VERIFIER_SHA256,
            old_cohort_or_failure_data_loaded=False)
        plan_raw = capture(directory / "plan.json", "campaign-plan.json")
        require(hashlib.sha256(plan_raw).hexdigest() == args.plan_sha256,
                "Unexpected campaign plan hash")
        plan = decode(plan_raw)
        validate_future_plan(plan, args, directory)
        state = decode(capture(directory / "status.json", "campaign-status-observed.json"))
        require(plan["output_directory"] == str(directory)
                and state["plan_sha256"] == args.plan_sha256,
                "Campaign path/hash binding differs")
        require([row["index"] for row in plan["legs"]] == [1, 2, 3, 4]
                and [row["role"] for row in plan["legs"]]
                == ["reference", "candidate", "reference", "candidate"], "Invalid planned order")
        gate = plan["precommit"]
        require(gate["min_full_games_per_leg"] == 50 and gate["max_attempts_per_leg"] == 1
                and gate["include_every_admitted_game"] is True
                and gate["include_full_completion_tail"] is True
                and gate["admission_extensions"] is False, "Admission protocol changed")
        spec = plan["legs"][args.leg - 1]
        records = [row for row in state["legs"] if row["index"] == args.leg]
        require(len(records) == 1 and records[0]["role"] == spec["role"]
                and records[0]["state"] == "finished" and records[0]["returncode"] == 0,
                "Wait for the owner's finished evaluator record with returncode0")
        record = records[0]
        proof_raw = capture(args.cpu_proof, "448-cpu-verification.json")
        require(hashlib.sha256(proof_raw).hexdigest() == args.cpu_proof_sha256, "Actual future CPU proof SHA differs")
        proof = decode(proof_raw)
        validate_cpu_proof(proof, args)
        report["future448_binding"] = dict(candidate_sha256=args.candidate_sha256, candidate_bytes=args.candidate_bytes,
            cpu_proof_sha256=args.cpu_proof_sha256, cpu_job_sha256=args.cpu_job_sha256, minimum_learner_frames=TARGET)
        legdir = directory / f"{args.leg:02d}-{spec['role']}"
        require(Path(spec["receipt_path"]) == legdir / "receipt.json"
                and Path(spec["job"]["directory"]) == legdir,
                "Receipt path does not match planned role")

        game = args.game.resolve(strict=True)
        sources = {}
        for group in ("evaluator_source_hashes", "execution_source_hashes"):
            for name, expected in plan[group].items():
                path = Path(name)
                path = path if path.is_absolute() else game / path
                require(digest(path) == expected, f"Frozen source differs: {path}")
                if str(path) not in sources:
                    raw = capture(path, f"bound-source-{len(sources):02d}-{path.name}")
                    require(hashlib.sha256(raw).hexdigest() == expected, "Frozen source copy race")
                sources[str(path)] = expected
        # Only these reviewed stdlib modules are imported, AFTER source hashes
        # match. No evaluator launch/configure_environment/training code runs.
        sys.path.insert(0, str(game / "tools"))
        import run_quality_campaign as campaign
        import sidecar_boot
        campaign.check_precommit(plan)
        require(sidecar_boot.load_snapshot(Path(spec["job"]["boot_assets"]))
                == plan["boot_assets"], "Boot snapshot differs")
        receipt_raw = capture(legdir / "receipt.json", "receipt.json")
        receipt, validated, receipt_sha = campaign.load_leg(spec, plan)
        require(receipt == decode(receipt_raw), "Receipt changed before validation")
        capture(legdir / "plan.json", "leg-plan.json")
        require(decode(payloads[str(legdir / "plan.json")])
                == dict(spec["job"], checkpoint_sha256=receipt["checkpoint_sha256"]),
                "Leg plan/checkpoint identity differs")
        journal = lines(capture(legdir / "journal/games.jsonl", "games.jsonl"))
        starts = lines(capture(legdir / "journal/measurement_starts.jsonl", "measurement_starts.jsonl"))
        capture(legdir / "journal/lives.jsonl", "lives.jsonl")
        all_games, all_starts = indexed(journal, "journal outcome"), indexed(starts, "start registry")
        start, close = receipt["start_ts"], receipt["close_ts"]
        require(math.isclose(close - start, spec["job"]["cohort_s"], abs_tol=1e-6),
                "Fixed admission window differs")
        admitted = {}
        for identifier, row in all_starts.items():
            if row["experiment"] == receipt["label"] and start <= row["start_unix_s"] <= close:
                require(row["known_start"] is True and row["measurement_active"] is True
                        and row["measurement_generation"] == receipt["generation"]
                        and row["client_slot"] in SLOTS, "Invalid admission context")
                admitted[identifier] = row
        original = {key: all_games[key] for key in admitted if key in all_games}
        receipt_rows = indexed(receipt["rows"], "receipt")
        require(len(admitted) >= 50 and set(original) == set(admitted) == set(receipt_rows),
                "An admitted full tail is missing, duplicated, abandoned, or omitted")
        raw_candidates = {row["journal_game_id"] for row in journal
                          if row["known_start"] is True and row["measurement_active"] is True
                          and row["experiment"] == receipt["label"]
                          and start <= row["start_unix_s"] <= close}
        require(raw_candidates == set(admitted), "Original journal/independent admission registry disagree")
        for identifier, entry in admitted.items():
            row = original[identifier]
            require(row == receipt_rows[identifier], "Receipt changed an original full game")
            for key in ("client_id", "client_slot", "game_uid", "start_utc", "start_unix_s",
                        "start_reason", "known_start", "measurement_active",
                        "measurement_generation", "start_frame"):
                require(entry[key] == row[key], f"Admission/outcome identity differs: {identifier}/{key}")
            validate_original_context(entry, row)
        require({row["client_slot"] for row in original.values()} == set(SLOTS),
                "Every private slot must contribute complete games")
        clients = {slot: {row["client_id"] for row in original.values()
                          if row["client_slot"] == slot} for slot in SLOTS}
        require(all(len(values) == 1 for values in clients.values())
                and set.union(*clients.values()) == set(receipt["boundary"]["acknowledged_client_ids"])
                and len(set.union(*clients.values())) == 16,
                "Private actor/client mapping changed within the cohort")
        require(validated["protocol"]["difficulty"] == spec["job"]["difficulty"] == 5,
                "Original game difficulty differs from precommit")
        for key in ("engine_version", "state_size", "single_frame_state_size", "frame_stack",
                    "wire_params_count", "wire_version", "frame_protocol"):
            require(validated["protocol"][key] == receipt[key], "Original wire/frame protocol differs")
        for key in ("training_steps", "optimized_samples", "learner_frame_count"):
            require(receipt["clocks"][key] == receipt["checkpoint_metadata"][key],
                    "Frozen journal clocks differ from checkpoint metadata")
            if spec["role"] == "candidate":
                require(receipt["checkpoint_metadata"][key] == proof["clocks"][key],
                        "Candidate receipt clock differs from actual448 generic CPU proof")
        cohort = receipt["cohort"]
        require(set(cohort["started_ids"]) == set(admitted)
                and len(cohort["started_ids"]) == len(admitted)
                and cohort["started_actor_slots"] == SLOTS, "Cohort registry coverage differs")
        scores = [row["score"] for row in original.values()]
        stats = dict(count=len(scores), started=len(scores), mean=statistics.mean(scores),
                     median=statistics.median(scores), sd=statistics.stdev(scores),
                     se=statistics.stdev(scores) / math.sqrt(len(scores)))
        for source in (receipt, cohort):
            for key, value in stats.items():
                require(math.isclose(source[key], value, rel_tol=1e-12, abs_tol=1e-9),
                        f"Saved {key} differs from all original games")
        require(receipt["runtime"]["cuda_visible_devices"] == spec["job"]["gpu_uuid"],
                "Actual runtime did not bind the planned physical GPU")
        cutoff = receipt["timeout_snapshot_unix_s"]
        require(cutoff >= max(row["end_unix_s"] for row in original.values()),
                "Cleanup cutoff precedes a required full-game completion")
        timeout_diagnostics = {}
        for slot in SLOTS:
            key = str(slot)
            raw = capture(legdir / "actors" / key / "console.log", f"actor-{slot}.log")
            text = raw.decode(errors="replace")
            actor_lines = text.splitlines()
            events = [int(match[1]) if match else None
                      for line in actor_lines if "[SOCKET ACTION TIMEOUT]" in line
                      for match in [re.search(r"\bunix_s=(\d+)\b", line)]]
            before = receipt["actor_timeout_logs_before_shutdown"][key]
            measured = max(before, sum(index < before or ts is None or ts <= int(cutoff)
                                      for index, ts in enumerate(events)))
            require(before <= len(events) and measured == receipt["actor_timeout_logs"][key] == 0,
                    f"Runtime/missing-time timeout for slot{slot}")
            require(len(events) == receipt["actor_timeout_logs_after_shutdown"][key]
                    and len(events) - measured == receipt["actor_cleanup_timeout_logs"][key],
                    "Final actor timeout diagnostics disagree")
            # Classification follows independently reconstructed timeout
            # validity. No generic failed/error/connection suppression.
            allowed, actor_issues = classify_actor_lines(
                actor_lines, f"socket.{spec['job']['host']}:{spec['job']['port']}", cutoff, before, measured)
            require(not actor_issues, f"Unclassified actor{slot} log issues: {actor_issues}")
            backend = receipt["socket_wait"]["actors"][key]
            activations = [dict(zip(("pid", "fd", "port", "interval_us"), map(int, values)))
                           for values in re.findall(r"\[robotron-socket-wait\] pid=(\d+) fd=(\d+) port=(\d+) interval_us=(\d+)", text)]
            require(any(row["pid"] == backend["pid"] and row["port"] == spec["job"]["port"]
                        and row["interval_us"] == spec["job"]["wait_us"] for row in activations),
                    "Missing exact owned actor pacing activation")
            timeout_diagnostics[key] = dict(runtime=measured, cleanup=len(events) - measured,
                                           cutoff_unix_s=cutoff, allowed_actor_lines=allowed,
                                           source_hashes={name: plan["evaluator_source_hashes"][name]
                                                          for name in ("Scripts/main.lua", "tools/run_frozen_sidecar.py")})
            restore = receipt["boot_restores"][key]
            require(restore["manifest_sha256"] == plan["boot_assets"]["manifest_sha256"]
                    and restore["restored_paths"] == {
                        name: str(legdir / "actors" / key / name)
                        for name in plan["boot_assets"]["files"]},
                    "Private actor boot restore paths/manifest differ")
        require(digest(receipt["socket_wait"]["library"]) == receipt["socket_wait"]["sha256"],
                "Private pacing binary differs")
        console = capture(Path(spec["console_log"]), "evaluator-console.log").decode(errors="replace")
        # Potential exception text is never blanket-exempted. A narrow stopped
        # batcher signature may arise ONLY from owned batcher.stop(); the pinned
        # handler latches it unless shutdown_event was already set. Receipt
        # validity plus empty fatal/cleanup fields and cutoff-after-all-tails
        # therefore prove intentional cleanup, not a lost admitted observation.
        flagged, unclassified = [], []
        stopped = r"Inference batcher (?:stopped before (?:completion|dispatch)|is stopped)"
        exact_cleanup = re.compile(r"(?:Client \d+ error: |RuntimeError: )" + stopped + r"$")
        exact_eof = re.compile(r"Client \d+ disconnected: (?:EOF|Broken payload)$")
        console_lines = console.splitlines()
        traceback_lines = set()
        # Only complete, uninterleaved two-frame traces rooted in the exact
        # pinned handle_client -> infer raise path are cleanup diagnostics.
        # Unknown exception types, foreign frames and ambiguous interleaving
        # remain unclassified and require owner/peer review.
        for index, line in enumerate(console_lines):
            if line != "Traceback (most recent call last):":
                continue
            stop = index + 1
            while stop < len(console_lines) and console_lines[stop].startswith((" ", "\t")):
                stop += 1
            frames = [entry for entry in console_lines[index + 1:stop]
                      if entry.lstrip().startswith("File ")]
            expected = str(game / "Scripts/dqn/socket_server.py")
            if (stop < len(console_lines) and exact_cleanup.fullmatch(console_lines[stop])
                    and len(frames) == 2
                    and re.fullmatch(r'  File "' + re.escape(expected) + r'", line \d+, in handle_client', frames[0])
                    and re.fullmatch(r'  File "' + re.escape(expected) + r'", line \d+, in infer', frames[1])):
                traceback_lines.update(range(index + 1, stop + 2))
        for number, line in enumerate(console_lines, 1):
            if re.search(r"Traceback|\b\w*(?:Error|Exception)\b|\bfailed\b|\bfallback\b|\bunavailable\b|\bdisconnected\b|param mismatch|\[INGEST\] dropped implausible", line, re.I):
                kind = "unclassified"
                if exact_cleanup.fullmatch(line) or number in traceback_lines:
                    kind = "owned_post_cutoff_batcher_shutdown"
                elif exact_eof.fullmatch(line):
                    kind = "owned_shutdown_EOF_after_valid_full_tail"
                flagged.append(dict(line_number=number, text=line, classification=kind))
                if kind == "unclassified":
                    unclassified.append(dict(line_number=number, text=line))
        require(not unclassified, f"Unclassified evaluator log issues require review: {unclassified}")
        excluded = [row for row in journal if row["journal_game_id"] not in admitted]
        report.update(result="valid_completed_leg", valid=True, role=spec["role"],
                      label=receipt["label"], plan_sha256=args.plan_sha256,
                      receipt_sha256=receipt_sha, checkpoint_sha256=receipt["checkpoint_sha256"],
                      statistics=dict(stats, score_sum=sum(scores)),
                      original_game_ids=sorted(original), admission_ids=sorted(admitted),
                      actor_slot_counts=dict(sorted(Counter(str(row["client_slot"])
                                                           for row in original.values()).items())),
                      completion_tail=dict(games=sum(row["end_unix_s"] > close for row in original.values()),
                                           maximum_after_close_s=max(0, max(row["end_unix_s"] for row in original.values()) - close)),
                      excluded_records=dict(count=len(excluded),
                                            reasons=dict(Counter(row["excluded_reason"] or "outside_admission_window"
                                                                 for row in excluded))),
                      timeout_diagnostics=timeout_diagnostics, flagged_console_lines=flagged,
                      numeric_policy=receipt["numeric_policy"], runtime=receipt["runtime"],
                      source_hashes=sources, boot_identity=plan["boot_assets"]["identity"],
                      limitations=["Selected-leg validity only; all four fresh complete cohorts are required for a campaign decision.",
                                   "All original outside-window/startup records preserved; no score threshold or equal-count truncation.",
                                   "Full tail retained. No learning-speed, independence, formal-confidence, or promotion claim."])
        # The controller status may advance to leg2 normally. Only the completed
        # leg record must remain exact; immutable plan/leg evidence stay byte exact.
        later = decode((directory / "status.json").read_bytes())
        require([row for row in later["legs"] if row["index"] == args.leg] == [record],
                "Finished evaluator record changed during review")
        for path, entry in artifacts.items():
            if path != str(directory / "status.json"):
                require(digest(path) == entry["sha256"], f"Original evidence changed during audit: {path}")
        require(all(digest(path) == expected for path, expected in sources.items()), "Frozen source changed during review")
    except Exception as error:
        report.update(result="rejected_or_needs_review", valid=False,
                      error=f"{type(error).__name__}: {error}")
    immutable(output / "review-receipt.json", report)
    directory_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    print(json.dumps(dict(result=report["result"], valid=report["valid"],
                         receipt=str(output / "review-receipt.json"),
                         sha256=digest(output / "review-receipt.json"))))
    return 0 if report["valid"] else 2


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--execute" not in argv:
        print(PLAN)
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=GAME)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--candidate-bytes", type=int, required=True)
    parser.add_argument("--cpu-job-sha256", required=True)
    parser.add_argument("--cpu-proof", type=Path, required=True)
    parser.add_argument("--cpu-proof-sha256", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--leg", type=int, choices=(1,2,3,4), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    for value in (args.plan_sha256, args.candidate_sha256, args.cpu_proof_sha256, args.cpu_job_sha256, args.source_sha256):
        require(re.fullmatch(r"[0-9a-f]{64}",value) is not None, "Actual lowercase SHA256 binding required")
    require(type(args.candidate_bytes) is int and 200 << 20 <= args.candidate_bytes <= 400 << 20, "Actual candidate byte bound required")
    require(args.cpu_proof.is_absolute() and args.cpu_proof == args.cpu_proof.resolve(strict=True)
            and args.cpu_proof.is_relative_to(GAME / "logs/managed-learning-20261015/run-26")
            and args.cpu_proof.name == "cpu-verification.json", "Actual canonical generic CPU proof path required")
    return audit(args)


if __name__ == "__main__":
    raise SystemExit(main())
