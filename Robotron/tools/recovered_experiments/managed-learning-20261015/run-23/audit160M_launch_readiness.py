"""Read-only prospective160M launch readiness; never visits candidate/gate files."""
from pathlib import Path
import ast
import datetime
import hashlib
import json
import os
import subprocess
import sys
import urllib.request

D = Path(__file__).resolve().parent
C = D.parent
G = D.parents[2]
GPU0 = "GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0"
GB300 = "GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1"
LABEL = "sidecar-gpu0-160M-regression-guard-01"
SLOTS = list(range(4096, 4112))
started = datetime.datetime.now(datetime.timezone.utc).isoformat()

def pin(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def process(pid):
    parts = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
    return dict(pid=pid, start_ticks=int(parts[19]), state=parts[0])

def environment(pid):
    return dict(value.decode().split("=", 1) for value in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0") if b"=" in value)

plan_path = D / "quality160M-preparation/quality160M-regression-guard-plan.json"
plan = json.loads(plan_path.read_bytes())
campaign_path = Path(plan["reference"]["campaign"])
campaign_raw = campaign_path.read_bytes()
campaign = json.loads(campaign_raw)
common = campaign["common_runtime"]
metadata_path = Path(plan["reference"]["checkpoint"]["metadata_path"])
metadata_raw = metadata_path.read_bytes()
metadata = json.loads(metadata_raw)
sources = {relative: pin(G / relative) for relative in common["source_hashes"]}
sys.path.insert(0, str(G / "tools"))
from sidecar_boot import load_snapshot
boot = load_snapshot(Path(common["job"]["boot_assets"]))
manifest = json.loads((D / "actor192-all-connected.json").read_bytes())
main_actors = []
for actor in manifest["actors"]:
    try:
        actual = process(actor["pid"])
        same = actual["start_ticks"] == actor["start_ticks"] and actual["state"] not in ("Z", "X")
    except (OSError, ValueError, IndexError):
        same = False
    main_actors.append(dict(pid=actor["pid"], slot=actor["slot"], same_start_ticks=same))
main = process(1436155)
supervisor = process(1438661)
main_environment = environment(1436155)
first_actor_environment = environment(main_actors[0]["pid"])
library = Path(first_actor_environment["LD_PRELOAD"])
library_hash = pin(library)
listeners = []
for table in ("/proc/net/tcp", "/proc/net/tcp6"):
    for line in Path(table).read_text().splitlines()[1:]:
        fields = line.split()
        if int(fields[1].rsplit(":", 1)[1], 16) == 9999 and fields[3] == "0A":
            listeners.append(dict(table=table, line=line))
mames, private_runners, unreadable_mame = [], [], []
for entry in Path("/proc").iterdir():
    if not entry.name.isdecimal():
        continue
    try:
        command = entry.joinpath("cmdline").read_bytes().split(b"\0")
        args = [value.decode(errors="replace") for value in command if value]
    except OSError:
        continue
    if any(Path(value).name == "run_frozen_sidecar.py" for value in args):
        private_runners.append(dict(pid=int(entry.name), argv=args))
    if not args or Path(args[0]).name != "mame" or "robotron" not in args:
        continue
    try:
        values = environment(int(entry.name))
        mames.append(dict(pid=int(entry.name), slot=values.get("ROBOTRON_CLIENT_SLOT"),
            socket_address=values.get("ROBOTRON_SOCKET_ADDRESS"), wait_port=values.get("ROBOTRON_SOCKET_WAIT_PORT")))
    except OSError as error:
        unreadable_mame.append(dict(pid=int(entry.name), error=str(error)))
highslot_mames = [row for row in mames if row["slot"] in set(map(str, SLOTS))]
gpu_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
gpu = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,name,utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
    text=True, capture_output=True, timeout=5)
apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,gpu_uuid,process_name,used_memory", "--format=csv,noheader,nounits"],
    text=True, capture_output=True, timeout=5)
gpu_rows = [[value.strip() for value in line.split(",")] for line in gpu.stdout.splitlines() if line.strip()]
app_rows = [[value.strip() for value in line.split(",")] for line in apps.stdout.splitlines() if line.strip()]
private_gpu_apps = [row for row in app_rows if row[1] == GPU0]
main_gpu_apps = [row for row in app_rows if row[0] == "1436155"]
with urllib.request.urlopen("http://127.0.0.1:8771/api/now", timeout=3) as response:
    api = json.load(response)
health = {key: api[key] for key in ("ts", "client_count", "measurement_active", "training_steps", "optimized_samples", "learner_frame_count", "frame_count")}
job = dict(common["job"], checkpoint=plan["candidate"]["checkpoint"], directory=str(C / LABEL), label=LABEL)
argv = ["env", "-u", "LD_PRELOAD", "-u", "ROBOTRON_SOCKET_WAIT_ACTIVE", "CUDA_VISIBLE_DEVICES=" + GPU0,
    "OMP_NUM_THREADS=2", "MKL_NUM_THREADS=2", "OPENBLAS_NUM_THREADS=2", "TORCHINDUCTOR_COMPILE_THREADS=2",
    str(G.parent / ".venv-gb300/bin/python"), "-Xgil=0", "-B", "-u", str(G / "tools/run_frozen_sidecar.py"),
    "--checkpoint", job["checkpoint"], "--job-dir", job["directory"], "--label", LABEL,
    "--device", "cuda", "--gpu-uuid", GPU0, "--inference-backend", "inductor", "--port", "9999",
    "--cohort-s", "600", "--timeout-s", "1200", "--wait-us", "1000", "--cpu-threads", "2",
    "--mame", job["mame"], "--rompath", job["rompath"], "--boot-assets", job["boot_assets"], "--launch"]
runner_tree = ast.parse((G / "tools/run_frozen_sidecar.py").read_text())
declared = {arg.value for node in ast.walk(runner_tree) if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
    for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
requested = {value for value in argv[argv.index(str(G / "tools/run_frozen_sidecar.py")) + 1:] if value.startswith("--")}
fixed = common["job"]
checks = dict(
    adopted_plan_pin=pin(plan_path) == "dc9a1ed23a24dd3457455ac7fbd3f31c88c3764d47b96ba413a2d0974c90583c",
    protected128_campaign_pin=hashlib.sha256(campaign_raw).hexdigest() == plan["reference"]["campaign_sha256"],
    protected128_metadata_pin=hashlib.sha256(metadata_raw).hexdigest() == plan["reference"]["checkpoint"]["metadata_sha256"],
    protected128_identity_and_saved_clocks=metadata["sha256"] == plan["reference"]["checkpoint"]["sha256"]
        and metadata["saved_checkpoint_metadata"] == plan["reference"]["saved_clocks"],
    source12_exact=len(sources) == 12 and sources == common["source_hashes"],
    boot_identity_and_all3_seed_files_exact=boot["identity"] == common["boot_identity"] and boot["files"] == common["boot_files"],
    existing_native_shim_exact=library_hash == common["socket_wait_sha256"],
    backend_protocol_fixed=fixed["gpu_uuid"] == GPU0 and fixed["port"] == 9999 and fixed["actors"] == 16
        and fixed["actor_slots"] == SLOTS and fixed["cohort_s"] == 600 and fixed["timeout_s"] == 1200
        and fixed["wait_us"] == 1000 and fixed["cpu_threads"] == 2 and fixed["inference_backend"] == "inductor"
        and fixed["epsilon"] == fixed["expert_ratio"] == 0 and fixed["difficulty"] == 5 and fixed["start_level"] == 1
        and fixed["replay_enabled"] is False and fixed["fp16"] is False,
    main192_pinned_identities_intact=len(main_actors) == 192 and all(row["same_start_ticks"] for row in main_actors),
    main_trainer_supervisor_same=main["start_ticks"] == 24126660 and supervisor["start_ticks"] == 24161893
        and main["state"] not in ("Z", "X") and supervisor["state"] not in ("Z", "X"),
    main_API192_and_not_measuring=health["client_count"] == 192 and health["measurement_active"] is False,
    GPU0_compute_idle=apps.returncode == gpu.returncode == 0 and not private_gpu_apps
        and any(row[1] == GPU0 and row[3] == "0" for row in gpu_rows),
    main_context_GB300_only=bool(main_gpu_apps) and all(row[1] == GB300 for row in main_gpu_apps)
        and main_environment.get("CUDA_VISIBLE_DEVICES") == "1",
    port9999_no_listener=not listeners,
    private_highslots_and_runner_free=not highslot_mames and not unreadable_mame and not private_runners,
    only_pinned192_Robotron_MAME_present=len(mames) == 192 and {row["pid"] for row in mames} == {row["pid"] for row in main_actors},
    deferred_cli_flags_known=requested.issubset(declared),
    deferred_label_exact=LABEL == plan["candidate"]["labels"][0],
    prospective_output_directory_unused=not (C / LABEL).exists(),
)
report = dict(schema="robotron-160M-prospective-launch-readiness-independent-v1", started_utc=started,
    finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), PASS=all(checks.values()), checks=checks,
    deferred_argv=argv, prospective_job_metadata=job, frozen_numeric_policy=common["numeric_policy"],
    expected_runtime=common["runtime"], source_hashes=sources, boot_identity=boot["identity"], boot_files=boot["files"],
    boot_manifest_sha256=boot["manifest_sha256"], existing_shim=dict(path=str(library), sha256=library_hash),
    resource_probe=dict(utc=gpu_at, nvidia_gpu_rows=gpu_rows, compute_apps=app_rows, listeners9999=listeners,
        highslot_mames=highslot_mames, private_runners=private_runners, unreadable_mame=unreadable_mame),
    main=main, main_supervisor=supervisor, main192=main_actors, main_health=health,
    protected128_publication_metadata=dict(campaign_sha256=hashlib.sha256(campaign_raw).hexdigest(),
        metadata_sha256=hashlib.sha256(metadata_raw).hexdigest()),
    future_candidate_gate_lineage_or_quality_payload_visited=False, model_payload_hash_or_load=False,
    job_created_or_launched=False, source_or_control_write=False, training_or_actor_process_controls=False, GPU_context_created=False,
    mandatory_before_root_launch=["Actual160M gate and checkpoint captured and independently CPU-verified with adopted root helper; final lineage SHA pinned",
        "Time-local source12/boot/shim/port/private-slots/GPU0-compute-idle/main192 recheck immediately before launch",
        "No global mainfleet restart or guardedsource mutation during private cohort; preserve full admitted game tails and positive owned cleanup"],
    limits=["Readiness is prospective, not launch permission or proof of actual future compile/numeric metadata. The new runner must still prove strict FP32/TF32 Inductor warm1..16 before its16 actors are admitted.",
        "GPU0 display memory is expected; compute-idle means no CUDA compute context and utilization0 at the query instant. Port/highslot availability is similarly time-local.",
        "Existing protected128 campaign/protection metadata were hashed; no old model payload was hashed or loaded. No future checkpoint/gate/lineage/stat or quality journal/receipt was read; Job.validate/main were not called.",
        "Existing shim bytehash was read only; no build, preload or MAME launch occurred. All command arguments are a deferred list only."])
out = D / "quality160M-private-launch-readiness-independent.json"
with out.open("x") as stream:
    json.dump(report, stream, indent=2, allow_nan=False)
    stream.write("\n")
out.chmod(0o444)
print(json.dumps(dict(PASS=report["PASS"], checks=len(checks), failed=[key for key, value in checks.items() if not value],
    path=str(out), sha256=pin(out), probe_utc=gpu_at), indent=2))
