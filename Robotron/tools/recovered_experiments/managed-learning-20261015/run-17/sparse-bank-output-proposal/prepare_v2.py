"""Append a durable actual-import repository test, preserving reviewed v1 bytes."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
GAME = HERE.parents[3]
PINS = {
    "sparse-bank-output.patch": "160c8933dcace1ff732e97a84bc140b4bfaf4af9e538bf30f570780815744c19",
    "proposed/replay_buffer.py": "4c123933177a8d256af950842fada76521532bfaf08c3d2806ad351cef234751",
    "proposed/bank_output.py": "85a161a445dc44e8bb0ef225a5630b485ff0c4d4874f9d04367544ab744caa9d",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    for name, expected in PINS.items():
        if digest(HERE / name) != expected:
            raise ValueError("Reviewed v1 source changed: " + name)
    if digest(GAME / "Scripts/dqn/replay_buffer.py") != "1fe8eff5dd90a991ae4e226c478b2df12aa2704440b4202aef55f303515231db":
        raise ValueError("Canonical replay source changed")
    if digest(GAME / "Scripts/dqn/pipeline_telemetry.py") != "fa866eaaba56883a9df28046238ec0c235248dbf43837496caf40560c0aa69b6":
        raise ValueError("Canonical priority telemetry changed")
    test = HERE / "proposed/test_bank_output.py"
    text = test.read_text()
    patch = (HERE / "sparse-bank-output.patch").read_text()
    patch += "".join(difflib.unified_diff([], text.splitlines(True), fromfile="/dev/null",
                       tofile="b/Robotron/Scripts/dqn/test_bank_output.py"))
    with (HERE / "sparse-bank-output-v2.patch").open("x") as stream:
        stream.write(patch)
    value = dict(schema="robotron-sparse-bank-output-v2-prepared-v1",
        utc=datetime.now(timezone.utc).isoformat(), proposal_only=True,
        unchanged_v1_pins=PINS, durable_test_sha256=digest(test),
        v2_patch_sha256=digest(HERE / "sparse-bank-output-v2.patch"),
        test_scope="Actual relative .bank_output import; no artifact path/hash/proposed-source dependencies",
        tests_not_yet_run=True, canonical_sources_changed=False,
        production_applied=False, process_controls=False, GPU_context=False)
    with (HERE / "prepared-v2.json").open("x") as stream:
        json.dump(value, stream, indent=2); stream.write("\n")
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
