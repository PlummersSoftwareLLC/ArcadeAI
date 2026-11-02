"""Prepare a pinned source-only patch; never writes a canonical source file."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
GAME = HERE.parents[3]
BASE_REPLAY = "1fe8eff5dd90a991ae4e226c478b2df12aa2704440b4202aef55f303515231db"
BASE_PRIORITY = "fa866eaaba56883a9df28046238ec0c235248dbf43837496caf40560c0aa69b6"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError("Source anchor is absent or ambiguous: " + before[:60])
    return text.replace(before, after)


def exclusive(path, content):
    with path.open("xb") as output:
        output.write(content)


def main():
    replay = GAME / "Scripts/dqn/replay_buffer.py"
    priority = GAME / "Scripts/dqn/pipeline_telemetry.py"
    original = replay.read_bytes()
    priority_bytes = priority.read_bytes()
    if sha(original) != BASE_REPLAY or sha(priority_bytes) != BASE_PRIORITY:
        raise ValueError("Pinned replay/priority telemetry base differs; refuse preparation")
    before = HERE / "before"
    before.mkdir()
    exclusive(before / replay.name, original)
    exclusive(before / priority.name, priority_bytes)
    text = original.decode()
    text = once(text, "class SumTree:\n", "try:\n"
        "    from .bank_output import (BankOutputTelemetry, stream_output_enabled,\n"
        "                              write_bank_array)\n"
        "except ImportError:\n"
        "    from bank_output import (BankOutputTelemetry, stream_output_enabled,\n"
        "                             write_bank_array)\n\n\nclass SumTree:\n")
    text = once(text,
        "            last_write_duration_s=0.0, last_error=None)\n",
        "            last_write_duration_s=0.0, last_error=None)\n"
        "        # Only field-file output changes when explicitly requested.\n"
        "        # Capture/publication/revision/epoch/flush semantics stay unchanged.\n"
        "        self._bank_stream_output = stream_output_enabled()\n"
        "        self._bank_output_telemetry = BankOutputTelemetry(self._bank_stream_output)\n")
    text = once(text,
        "                               for bank in (\"hof\", \"ephof\")}\n        return result\n",
        "                               for bank in (\"hof\", \"ephof\")}\n"
        "        # No writer/replay/model lock is held while reading phase scalars.\n"
        "        output = getattr(self, \"_bank_output_telemetry\", None)\n"
        "        result[\"output\"] = output.snapshot() if output is not None else dict(available=False)\n"
        "        return result\n")
    block = '''                output = np.lib.format.open_memmap(path, mode="w+", dtype=source.dtype,
                    shape=(snapshot["count"]*snapshot["stride"], *source.shape[1:]))
                try:
                    cursor = 0
                    for episode, length in enumerate(lengths):
                        length = int(length)
                        begin = episode*snapshot["stride"]
                        output[begin:begin+length] = source[cursor:cursor+length]
                        cursor += length
                    output.flush()
                finally:
                    output._mmap.close()
                with open(path, "rb") as stream:
                    os.fsync(stream.fileno())
'''
    text = once(text, block, '''                write_bank_array(path, source, count=snapshot["count"],
                    stride=snapshot["stride"], lengths=lengths,
                    stream_output=self._bank_stream_output,
                    telemetry=self._bank_output_telemetry, bank=bank, field=field)
''')
    proposed = HERE / "proposed/replay_buffer.py"
    exclusive(proposed, text.encode())
    additions = HERE / "proposed/bank_output.py"
    helper_bytes = additions.read_bytes()
    patch = "".join(difflib.unified_diff(original.decode().splitlines(True),
        text.splitlines(True), fromfile="a/Robotron/Scripts/dqn/replay_buffer.py",
        tofile="b/Robotron/Scripts/dqn/replay_buffer.py"))
    patch += "".join(difflib.unified_diff([], helper_bytes.decode().splitlines(True),
        fromfile="/dev/null", tofile="b/Robotron/Scripts/dqn/bank_output.py"))
    patch_path = HERE / "sparse-bank-output.patch"
    exclusive(patch_path, patch.encode())
    if replay.read_bytes() != original or priority.read_bytes() != priority_bytes:
        raise ValueError("Canonical source changed during preparation")
    data = dict(schema="robotron-sparse-bank-output-prepared-v1",
        utc=datetime.now(timezone.utc).isoformat(), proposal_only=True,
        default_off_env="DQN_STREAM_BANK_OUTPUT", base_replay_sha256=BASE_REPLAY,
        priority_telemetry_sha256=BASE_PRIORITY, priority_telemetry_changed=False,
        proposed_replay_sha256=sha(text.encode()), proposed_helper_sha256=sha(helper_bytes),
        patch_sha256=sha(patch.encode()), production_sources_changed=False,
        tests_not_yet_run=True,
        reporting="Existing bank_persistence raw/API/CSV JSON gains output; no new columns",
        protocol_sources_changed=False, GPU_context=False, process_controls=False)
    exclusive(HERE / "prepared.json", (json.dumps(data, indent=2) + "\n").encode())
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
