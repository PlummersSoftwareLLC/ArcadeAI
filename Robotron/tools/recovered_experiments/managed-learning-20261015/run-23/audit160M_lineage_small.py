"""Independent small-evidence160M lineage audit; no checkpoint payload read."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import os

D = Path(__file__).resolve().parent
EXPECTED = "85cd646d34162f59b0a04853f87f615815b68c8d6d08f6ec3924661dcf7504b5"
def read(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()
lineage_path = D / "fresh3-160M-checkpoint-lineage.json"
report, report_sha = read(lineage_path)
proposal, proposal_sha = read(D / "quality160M-preparation/proposed-fresh3-160M-checkpoint-lineage.json")
reference, reference_sha = read(D / "fresh3-128M-checkpoint-lineage.json")
plan, plan_sha = read(D / "quality160M-preparation/quality160M-regression-guard-plan.json")
gate, gate_sha = read(report["trigger_gate"]["path"])
small_evidence = []
for record in report["root_verification_evidence"]:
    path = Path(record["path"])
    if path.suffix == ".pt":
        continue
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"], str(path)
    small_evidence.append(record)
candidate = report["candidate"]
metadata = candidate["saved_metadata"]
previous = reference["candidate"]["saved_metadata"]
actual_stat = Path(candidate["path"]).stat()
actual_identity = dict(size=actual_stat.st_size, mtime_ns=actual_stat.st_mtime_ns,
    inode=actual_stat.st_ino, device=actual_stat.st_dev, mode=oct(actual_stat.st_mode & 0o777), nlink=actual_stat.st_nlink)
capture, root = report["capture_execution"], report["root_verification"]
branch = report["branch_provenance"]
exposure = report["actual_recorded_batch_exposure"]["since128M"]
chronology = branch["compiler_and_instrumentation_chronology"]
source = D / "quality160M-preparation/analyze160M_guard.py"
spec = importlib.util.spec_from_file_location("small160_contract", source)
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
contract.lineage_identity(report, Path(candidate["path"]), previous)
process_fields = Path("/proc/1436155/stat").read_text().split(") ", 1)[1].split()
runtime, runtime_sha = read(branch["runtime_metadata_path"])
expected_meta = dict(training_steps=1030948, total_training_steps=1030948, optimized_samples=2775175168,
    learner_frame_count=164632429, frame_count=328688760, measurement_frame_count=7550388, baseline_batch_size=512)
delta = {key: metadata[key] - previous[key] for key in contract.CORE_CLOCKS}
steps = candidate["optimizer"]["step_values"]
checks = dict(
    exact_final_root_lineage_pin=report_sha == "39567648447348732d8b44dcb6f59d8d20ded5f688462ede5afdcea937fa59e5",
    final_root_lineage_readonly=(lineage_path.stat().st_mode & 0o777) == 0o444 and lineage_path.stat().st_nlink == 1,
    root_final_strict_PASS=report["proposal_only"] is False and report["PASS"] is True and bool(report["checks"])
        and all(value is True for value in report["checks"].values()) and root["status"] == "PASS",
    explicit_proposal_pin_and_pending_capture=proposal_sha == root["proposal_sha256"]
        == "645a4fa54dc88c91f30ddd779ca41f0a95edd64d2c17c67bf1cb6e1126f0535d"
        and proposal["proposal_only"] is True and proposal["root_verification"].startswith("PENDING"),
    candidate_SHA_and_stat_attestation_exact=candidate["sha256"] == EXPECTED and candidate["stat"] == actual_identity,
    actual_saved_clocks_exact=all(metadata[key] == value for key, value in expected_meta.items()),
    source_signature_geometry_matches128=reference_sha == "4535f56d71a1fe3c3b6c3f148ae7ab9cc6f9846d6eaa3b420ede0e82bc6eda18"
        and candidate["state_dict_signatures"] == reference["candidate"]["state_dict_signatures"],
    root_CPU_finite443_Adam81_proof=candidate["all_network_optimizer_tensors_finite"] is True
        and candidate["checkpoint_tensor_count"] == root["saved_tensor_count"] == 443
        and candidate["tensor_devices"] == ["cpu"] and candidate["optimizer"]["all_tensors_CPU"] is True
        and candidate["optimizer"]["state_count"] == 81 and candidate["optimizer"]["tensor_count"] == 243
        and steps == root["optimizer_parameter_steps"] == [1030494.0],
    both_actual_CPU_executions_hiddenCUDA_lowthreads=capture["CUDA_VISIBLE_DEVICES"] == root["CUDA_VISIBLE_DEVICES"] == ""
        and capture["CUDA_initialized"] is root["CUDA_initialized"] is False
        and capture["torch_threads"] == root["torch_threads"] == 2,
    chronological_gate_capture_second_independent_verification=(gate["saved_utc"] < capture["started_utc"]
        < capture["finished_utc"] < root["started_utc"] < root["finished_utc"]),
    root_executed_reviewed_helper_and_precommit=root["verifier_sha256"] == "6dea85bb491cd7e0ae4886632fb9f8bc6131c3e45353d3525d5e948e0348bb8b"
        and root["precommit_sha256"] == "a434cc1b816d9c1ab29173ef01e8df6d9228d02f3738445f456f4a16d0013040",
    actual_gate_target_branch_and_saved_identity=gate_sha == report["trigger_gate"]["sha256"]
        and gate == report["trigger_gate"]["record"] and gate["tag"] == "fresh3-160M"
        and gate["target"] == 164629023 and gate["experiment"] == "best10M-fresh3-eps10-cap8-nosmooth"
        and Path(gate["checkpoint"]) == Path(candidate["path"]) and metadata["learner_frame_count"] >= gate["target"],
    saved4096_exposure_exact=exposure == dict(recorded_batch_size=4096, logical_updates_delta=123549,
        optimized_samples_delta=506056704, learner_frames_delta=32000925)
        and delta["optimized_samples"] == 4096 * delta["training_steps"],
    Adam_exposure_separate_exact=steps[0] - reference["candidate"]["optimizer"]["step_values"][0] == 123492
        and chronology[0]["logical_minus_uniform_Adam_delta"] == 57,
    one_current_default_counter_interval_and_prior_B_history_preserved=len(chronology) == 1
        and chronology[0]["compiler"] == "default" and chronology[0]["exposure_counters_enabled"] is True
        and branch["prior128M_history"]["compiler_and_instrumentation_chronology"]
            == reference["branch_provenance"]["compiler_and_instrumentation_chronology"],
    current_main_identity_unchanged=root["main_process_identity"] == dict(pid=1436155, start_ticks=24126660)
        and int(process_fields[19]) == 24126660 and process_fields[0] not in ("Z", "X"),
    explicit_runtime_metadata_pin=runtime_sha == root["runtime_metadata_sha256"] == branch["runtime_metadata_sha256"]
        == "b53b460673caeca96f23654633ed39bb737ebda431fd7384498fbc414996de5d"
        and branch["recorded_runtime_recipe"] == runtime,
    current_adopted160_plan_pin=plan_sha == "dc9a1ed23a24dd3457455ac7fbd3f31c88c3764d47b96ba413a2d0974c90583c",
    no_API_counter_outcomes_inferred=report["counter_exposure_evidence"]["available"] is False,
    all_small_source_proof_evidence_bytepins_current=bool(small_evidence),
    strict_analyzer_lineage_contract_passed=True,
)
result = dict(schema="robotron-160M-final-lineage-independent-small-audit-v1",
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), PASS=all(checks.values()), checks=checks,
    lineage_path=str(lineage_path), lineage_sha256=report_sha, checkpoint_sha256=EXPECTED, candidate_stat=actual_identity,
    saved_metadata=metadata, root_CPU_witness=root, capture_execution=capture, trigger_gate=report["trigger_gate"],
    exposure_since128M=exposure, Adam_steps=steps, Adam_step_delta=123492, logical_minus_Adam_delta=57,
    source_evidence_pins_checked=small_evidence, counter_evidence_available=False,
    scope="Small JSON/source/proof byte pins and actual candidate stat only. No model payload read/hash repeated, Torch import, GPU context, process/control/source mutation or private partial outcomes. Root's two independent actualCPU witnesses establish tensor/Adam facts; this audit checks their pinned chronology/consistency. The57 logical-minus-Adam difference is not assigned to individual AMP events.")
out = D / "quality160M-final-lineage-independent-small-audit.json"
with out.open("x") as stream:
    json.dump(result, stream, indent=2, allow_nan=False)
    stream.write("\n")
out.chmod(0o444)
print(json.dumps(dict(PASS=result["PASS"], checks=len(checks), failed=[key for key,value in checks.items() if not value],
    path=str(out), sha256=hashlib.sha256(out.read_bytes()).hexdigest()), indent=2))
