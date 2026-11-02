#!/usr/bin/env python3
"""Audit one completed leg of the isolated confirmed-terminal campaign.

Default invocation only prints the proposed read-only audit inputs. This tool
never launches, signals, imports a learner, creates a GPU context, publishes a
policy, or decides a four-leg campaign. Its only writes are a NEW audit directory.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys

sys.dont_write_bytecode = True


SLOTS = list(range(4096, 4112))
VERIFIER_SHA256 = "14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5"
GAME = Path("/home/dave/source/repos/ArcadeAI/Robotron")
EVAL_GAME = GAME/'tools/confirmed_game_boundary_proposal/quality_integration_reviewed4/Robotron'
CAMPAIGN_ROOT = GAME / "logs/managed-learning-20261015"
CPU_VERIFIER = GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'
CFG = BUNDLE = BINDING_PIN = None
PLAN = "PLAN_ONLY: no reads/imports; fresh isolated R/C/R/C,5400/7200,min50,all16,confirmed-terminals; no launches or promotion"


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
    require(directory == args.campaign == Path(CFG['campaign']['output_directory'])
            and directory.parent == CAMPAIGN_ROOT and plan['output_directory'] == str(directory),
            'Wrong exact prospective campaign')
    require(args.plan_sha256 == CFG['campaign']['plan_sha256'], 'Exact original native plan required')
    require(plan['evaluator_source_hashes'] == CFG['campaign']['evaluator_source_hashes']
            and plan['execution_source_hashes'] == CFG['campaign']['execution_source_hashes'],
            'Exact canonical source bindings required')
    require(plan['evaluator_source_hashes']['Scripts/dqn/socket_server.py'] ==
            '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408',
            'Production continuity correction required')
    require(plan['evaluator_source_hashes']['Scripts/dqn/game_journal.py'] ==
            '3b8dc9ecf592cdb868443e9c1b21cde3ef398ac0a79a2d00c1c70a811bdeb90e'
            and plan['evaluator_source_hashes']['tools/confirmed_terminal_evidence.py'] ==
            '2416a19e63d9bcea7521795c139bbde269dc229124a1d34c5fc2a6a4d4aa6502',
            'Confirmed-reset scorer and mandatory original-byte readback required')
    require('effective_implementation' not in plan, 'Native isolated package plan required')
    for role in ('reference', 'candidate'):
        require(plan['checkpoints'][role] == dict(source=CFG[role]['path'],
            snapshot=str(directory/'checkpoints'/(role+'.pt')), sha256=CFG[role]['sha256']),
            'Exact protected reference/first-window candidate required')
    require(CFG['reference']['sha256'] ==
            'fda8dcdf80a794b2715843dc892890296363c7586c60bae435a0925e32997ecd',
            'Protected845M reference differs')
    require([spec['index'] for spec in plan['legs']] == [1,2,3,4]
            and [spec['role'] for spec in plan['legs']] == ['reference','candidate','reference','candidate'],
            'Four fresh fixed legs required')
    common = None
    for spec in plan['legs']:
        job = spec['job']
        require(spec['command'][:5] == [str(GAME.parent/'.venv-gb300/bin/python'),
                '-Xgil=0','-B','-u',str(EVAL_GAME/'tools/run_frozen_sidecar.py')],
                'Exact private evaluator command prefix required')
        require(job['checkpoint'] == plan['checkpoints'][spec['role']]['snapshot'], 'Role checkpoint differs')
        require(job.get('completion_policy') == 'confirmed_reset_reserves_v1',
                'Explicit confirmed-terminal completion policy required')
        require(job['game_boundary_diagnostics'] is True and '--game-boundary-diagnostics' in spec['command'],
                'Diagnostics required on all four legs')
        require(job['cohort_s'] == 5400 and job['timeout_s'] == 7200 and job['actors'] == 16
                and job['actor_slots'] == SLOTS and job['epsilon'] == job['expert_ratio'] == 0
                and job['difficulty'] == 5 and job['start_level'] == 1 and job['replay_enabled'] is False
                and job['fp16'] is False, 'Frozen full-game admission policy differs')
        require(job['device'] == 'cuda' and job['gpu_uuid'] == 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
                and job['host'] == '127.0.0.1' and job['port'] == 9999 and job['wait_us'] == 1000
                and job['inference_backend'] == 'inductor' and job['inference_max_batch_size'] == 16
                and job['cpu_threads'] == 2, 'Frozen backend/pacing policy differs')
        signature = {key:value for key,value in job.items() if key not in ('checkpoint','directory','label')}
        require(common is None or signature == common, 'Common policy differs across legs'); common = signature
    gate=plan['precommit']
    require(gate == dict(order=['reference','candidate','reference','candidate'],
        new_same_length_reference_cohorts=True, historical_or_interrupted_receipts_used=False,
        min_full_games_per_leg=50, all_actor_slots=SLOTS, include_every_admitted_game=True,
        include_full_completion_tail=True, max_attempts_per_leg=1, admission_extensions=False,
        automatic_promotion=False, automatic_rollback=False, learning_changes=False,
        candidate_gate=dict(each_candidate_individually=True,
            reference='all games pooled from both fresh reference legs', minimum_mean_ratio=1.05,
            minimum_median_ratio=1.0)), 'Fresh independent gates differ')


def validate_cpu_proof(proof, args):
    job=BUNDLE['phase_cpu_job']; candidate=CFG['candidate']
    require(proof == BUNDLE['phase_cpu_report'] and proof['schema'] ==
            'robotron-phase-snapshot-checkpoint-CPU-result-v1' and proof['status'] == 'PASS'
            and proof['root_job'] == job and proof['job_file']['sha256'] == args.cpu_job_sha256
            and proof['script']['sha256'] == VERIFIER_SHA256, 'Exact candidate CPU PASS/job required')
    require(proof['sha256'] == candidate['sha256'] == args.candidate_sha256
            and proof['bytes'] == candidate['bytes'] == args.candidate_bytes
            and job['source'] == candidate and job['phase_snapshot']['purpose'] == 'candidate'
            and job['phase_snapshot']['observed_clients'] == 192, 'Candidate CPU acquisition scope differs')
    for label, entry in [('source_checkpoint',job['source']),
                         ('root_readonly_verification_copy',job['verification_copy'])]:
        observed=proof['bound_files'][label]
        require(all(observed[key] == entry[key] for key in ('path','sha256','bytes'))
                and all(observed[key] == value for key,value in entry['identity'].items()),
                'CPU source/copy binding differs')
    source=proof['source_before']; copied=proof['verification_copy']
    require(source == proof['bound_files']['source_checkpoint']
            and copied == proof['bound_files']['root_readonly_verification_copy']
            and source['sha256'] == copied['sha256'] == candidate['sha256']
            and source['bytes'] == copied['bytes'] == candidate['bytes']
            and (source['device'],source['inode']) != (copied['device'],copied['inode'])
            and copied['mode'] == '0o444' and copied['nlink'] == 1, 'Independent readonly CPU copy required')
    require(proof['phase_metadata_verified'] is True
            and proof['actual_restore_or_optimizer_step'] is False
            and proof['actual_quality_qualification'] is False, 'CPU verification scope differs')
    expected=job['phase_snapshot']['expected_phase']; actual=proof['saved_priority_metric_phase']
    for key in ('metric','phase_id','root_precommit_sha256','started_from','valid','last_resume_record_sha256'):
        require(actual[key] == expected[key], 'CPU phase differs: '+key)
    require(actual['phase_record_sha256'] == expected['founder_phase_record_sha256'], 'CPU founder differs')
    floor=job['clock_floor']
    require(set(floor) == {'training_steps','optimized_samples','learner_frame_count','frame_count'}
            and all(type(floor[k]) is int and proof['clocks'][k] >= floor[k] for k in floor),
            'Actual four-clock acquisition floor differs')
    window=BUNDLE['window_job']; result=BUNDLE['window_result']; latch=BUNDLE['window_latch']
    require(CFG['evidence']['window_job']['sha256'] ==
            'cd6a47e2112dffbe68a6ec7da2224337b8b2543702e54b75f4f9982745a68942',
            'Original prospective window job required')
    require(result['status'] == 'CAPTURED_FIRST_BOTH_HORIZONS' and result['checkpoint'] == candidate
            and result['tag'] == window['tag'] and result['owner'] == window['owner']
            and result['progress']['both_horizons'] is True
            and result['progress']['learner_frames'] >= 8_000_000
            and result['progress']['learner_accepted'] >= 8_000_000
            and latch['progress'] == result['progress'] and latch['status'] == 'LATCH'
            and job['experiment'] == window['experiment'], 'Original prospective capture differs')


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
    require(args.campaign == Path(CFG["campaign"]["output_directory"]) and args.campaign.parent == CAMPAIGN_ROOT
            and args.game == EVAL_GAME, "Only the exact bound campaign/private game is allowed")
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

    report = dict(schema="robotron-confirmed-original-terminal-leg-v1",
                  audited_utc=datetime.now(timezone.utc).isoformat(),
                  campaign_directory=str(directory), leg=args.leg,
                  campaign_outcome="not_assessed", artifacts=artifacts,
                  scope="Completed-leg validity only; no quality comparison, speed claim, or live mutation.")
    try:
        for path, name in ((Path(__file__).resolve(), "audit-source.py"),):
            capture(path, name)
        report['audit_provenance'] = dict(source_sha256=args.source_sha256,
            python_executable=sys.executable, python_version=sys.version,
            dont_write_bytecode=sys.dont_write_bytecode,
            root_binding=capture(BINDING_PIN['path'], 'root-quality-binding.json').decode(),
            original_row_and_log_predicates_preserved=True,
            mandatory_original_terminal_readback=True)
        for name, entry in CFG['evidence'].items():
            require(digest(entry['path']) == entry['sha256'], 'Bound evidence changed before capture')
            capture(entry['path'], 'bound-'+name+'.json')
        require(digest(CPU_VERIFIER) == VERIFIER_SHA256, 'CPU verifier source changed')
        capture(CPU_VERIFIER, 'phase-verifier-source.py')
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
        proof_raw = capture(args.cpu_proof, "candidate-phase-cpu-verification.json")
        require(hashlib.sha256(proof_raw).hexdigest() == args.cpu_proof_sha256, "Actual future CPU proof SHA differs")
        proof = decode(proof_raw)
        validate_cpu_proof(proof, args)
        report['confirmed_scoring_binding'] = dict(candidate=CFG['candidate'],
            reference=CFG['reference'], evidence=CFG['evidence'], root_binding_job=BINDING_PIN)
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
        campaign_path=game/'tools/run_quality_campaign.py'
        require(digest(campaign_path)==CFG['campaign']['execution_source_hashes'][str(campaign_path)],'Selected companion campaign differs')
        module_spec=importlib.util.spec_from_file_location('_audited_continuous_guard_campaign',campaign_path)
        campaign=importlib.util.module_from_spec(module_spec);sys.modules[module_spec.name]=campaign
        module_spec.loader.exec_module(campaign)
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
                "Canonical leg plan/checkpoint identity differs")
        journal = lines(capture(legdir / "journal/games.jsonl", "games.jsonl"))
        starts = lines(capture(legdir / "journal/measurement_starts.jsonl", "measurement_starts.jsonl"))
        capture(legdir / "journal/lives.jsonl", "lives.jsonl")
        import confirmed_terminal_evidence as terminals
        original_terminal_links = terminals.verify_original_journal_bytes(receipt, {
            'games.jsonl': payloads[str(legdir/'journal/games.jsonl')],
            'measurement_starts.jsonl': payloads[str(legdir/'journal/measurement_starts.jsonl')]})
        report['original_terminal_readback'] = dict(status='PASS',
            verified_games=len(original_terminal_links), links=original_terminal_links,
            journal_sha256=receipt['terminal_journal_sha256'])
        all_games, all_starts = indexed(journal, "journal outcome"), indexed(starts, "start registry")
        rom_links=[validate_rom_terminal(row,receipt['terminal_successors'][row['journal_game_id']])
                   for row in receipt['rows']]
        report['rom_game_over_evidence']=dict(status='PASS',verified_games=len(rom_links),links=rom_links)

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
                        "Candidate receipt clock differs from actual first-candidate phase CPU proof")
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


def read_pin(entry):
    path=Path(entry['path']); info=path.lstat()
    identity=dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,mode=oct(info.st_mode&0o777),
        uid=info.st_uid,nlink=info.st_nlink)
    require(path.is_absolute() and path == path.resolve(strict=True)
            and info.st_size == entry['bytes'] and identity == entry['identity']
            and identity['mode'] == '0o444' and identity['uid'] == os.getuid() and identity['nlink'] == 1,
            'Exact owned immutable binding required')
    raw=path.read_bytes(); require(hashlib.sha256(raw).hexdigest() == entry['sha256'], 'Binding SHA differs')
    return decode(raw)




def validate_rom_terminal(row, successor):
    """Independent ROM game-over evidence, in addition to classifier/reset proof."""
    confirmation=row.get('terminal_confirmation',{})
    diagnostic=confirmation.get('ingest_boundary_inputs')
    if diagnostic is None:
        diagnostic=successor.get('context',{}).get('game_boundary_diagnostics')
    require(isinstance(diagnostic,dict), 'Missing original accepted terminal primitives')
    previous=diagnostic.get('previous_accepted_wire',{})
    current=diagnostic.get('current_wire',{})
    require(type(confirmation.get('previous_raw_reserves')) is int
            and confirmation['previous_raw_reserves']==0,
            'Final accepted reset lacks exhausted ROM reserve counter')
    require(previous.get('player_alive') is False or current.get('player_alive') is False,
            'Final accepted reset lacks an observed inactive player')
    require(diagnostic.get('recent_start') is True,
            'Final accepted reset lacks a recent observed restart pulse')
    return dict(journal_game_id=row['journal_game_id'],score=row['score'],
        previous_raw_reserves=0,inactive_player_observed=True,recent_restart_observed=True)


def validate_selected_package_and_validations():
    package=BUNDLE['source_package']
    require(package['schema']=='robotron-private-corrected-quality-package-v1'
            and package['root']==str(EVAL_GAME) and package['source_count']==122
            and len(package['files'])==122 and package['installed_source_changed'] is False,
            'Exact isolated evaluation package required')
    for relative,expected in package['files'].items():
        path=EVAL_GAME/relative
        require(path.resolve(strict=True).is_relative_to(EVAL_GAME)
                and digest(path)==expected, 'Selected private source changed')
    for label in ('validation_reference','validation_integrated'):
        value=BUNDLE[label]
        require(value['status']=='PASS' and value['error'] is None
                and value['cleanup_errors']==[] and value['source_unchanged'] is True
                and value['owned_actors_absent'] is True
                and value['quality_qualification'] is False and value['promotion'] is False,
                'Actual real-MAME terminal validation failed or changed scope')
        require(set(value['progress']['completed_slot_counts'])=={str(x) for x in SLOTS}
                and len(value['socket_wait_backend'])==16
                and all(x['matching_activation'] is True for x in value['socket_wait_backend'].values())
                and set(value['timeout_evidence']['actor_timeout_logs'])=={str(x) for x in SLOTS}
                and all(x==0 for x in value['timeout_evidence']['actor_timeout_logs'].values()),
                'Real-MAME validation lost actor/backend/timeout coverage')
        for key in ('main_before','main_after'):
            require(value[key]['pid']==BUNDLE['window_job']['owner']['pid']
                    and value[key]['clients']==192 and value[key]['errors']==0,
                    'Actual main owner changed across terminal validation')
    reference=BUNDLE['validation_reference']; integrated=BUNDLE['validation_integrated']
    require(reference['kind']=='reference' and reference['progress']['completed']>=16
            and reference['progress']['retained_full_scores'], 'Protected greedy full-score retention missing')
    require(integrated['kind']=='no-fire-up' and integrated['progress']['zero_completed']>=2
            and len(integrated['progress']['zero_slots'])>=2
            and integrated['original_terminal_readback']['status']=='PASS'
            and integrated['original_terminal_readback']['verified_games']>=integrated['progress']['completed'],
            'Actual integrated zero-score/original-byte validation missing')
    window=BUNDLE['window_job']
    require(window['tag']=='confirmed_scoring_LR25_next8M_01_20261018'
            and window['quality_precommit']['same_fixed_admission_s']==5400
            and window['quality_precommit']['same_whole_cohort_timeout_s']==7200
            and window['quality_precommit']['completion_policy']=='confirmed_reset_reserves_v1'
            and window['quality_precommit']['mandatory_original_terminal_journal_readback'] is True,
            'Fresh selected window/profile required')


def configure(args):
    global CFG,BUNDLE,BINDING_PIN
    path=args.binding_job.resolve(strict=True); info=path.lstat()
    BINDING_PIN=dict(path=str(path),sha256=args.binding_job_sha256,bytes=info.st_size,
        identity=dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
            mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,mode=oct(info.st_mode&0o777),
            uid=info.st_uid,nlink=info.st_nlink))
    CFG=read_pin(BINDING_PIN)
    require(set(CFG) == {'schema','campaign','candidate','reference','evidence'}
            and CFG['schema'] == 'robotron-confirmed-scoring-original-leg-binding-v1', 'Binding schema differs')
    require(set(CFG['evidence']) == {'phase_cpu_job','phase_cpu_report','window_job','window_result','window_latch',
        'source_package','validation_reference','validation_integrated'},
            'Actual CPU and original-window evidence required')
    BUNDLE={name:read_pin(entry) for name,entry in CFG['evidence'].items()}
    validate_selected_package_and_validations()
    args.candidate_sha256=CFG['candidate']['sha256']; args.candidate_bytes=CFG['candidate']['bytes']
    args.cpu_job_sha256=CFG['evidence']['phase_cpu_job']['sha256']
    args.cpu_proof=Path(CFG['evidence']['phase_cpu_report']['path'])
    args.cpu_proof_sha256=CFG['evidence']['phase_cpu_report']['sha256']
    require(args.campaign == Path(CFG['campaign']['output_directory']), 'Wrong concrete campaign binding')
    validate_cpu_proof(BUNDLE['phase_cpu_report'],args)


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if '--execute' not in argv:
        print(PLAN);return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game',type=Path,default=EVAL_GAME);parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--plan-sha256',required=True);parser.add_argument('--source-sha256',required=True)
    parser.add_argument('--binding-job',type=Path,required=True);parser.add_argument('--binding-job-sha256',required=True)
    parser.add_argument('--leg',type=int,choices=(1,2,3,4),required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args(argv)
    for value in (args.plan_sha256,args.source_sha256,args.binding_job_sha256):
        require(re.fullmatch(r'[0-9a-f]{64}',value) is not None,'Actual lowercase SHA binding required')
    require(digest(__file__)==args.source_sha256,'Auditor source SHA differs')
    configure(args)
    return audit(args)

if __name__ == "__main__":
    raise SystemExit(main())
