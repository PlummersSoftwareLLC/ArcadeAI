"""Write proposed source copies/patch only; never mutate production files."""
import difflib
import hashlib
import json
from pathlib import Path


DIRECTORY = Path(__file__).resolve().parent
BASE = DIRECTORY.parents[4]
FILES = ("Robotron/Scripts/dqn/native_sumtree.py", "Robotron/Scripts/dqn/replay_buffer.py",
         "Robotron/Scripts/dqn/sumtree.c")


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError("Expected source anchor exactly once: " + before[:80])
    return text.replace(before, after, 1)


def main():
    original = {name: (BASE / name).read_text() for name in FILES}
    proposed = dict(original)
    native = proposed[FILES[0]]
    native = replace_once(native, "_GATHER_FUNCTION = None\nNATIVE_AVAILABLE = False",
                          "_GATHER_FUNCTION = None\n_BATCH_FUNCTION = None\n"
                          "NATIVE_BATCH_ENABLED = os.getenv(\"DQN_NATIVE_BATCH_UPDATE\", \"0\").strip().lower() in (\"1\", \"true\", \"yes\", \"on\")\n"
                          "NATIVE_BATCH_AVAILABLE = False\nNATIVE_AVAILABLE = False")
    native = replace_once(native, "global _LIBRARY, _FUNCTION, _GATHER_FUNCTION\n",
                          "global _LIBRARY, _FUNCTION, _GATHER_FUNCTION, _BATCH_FUNCTION\n    global NATIVE_BATCH_AVAILABLE\n")
    native = replace_once(native, "        NATIVE_STATUS = \"exact float64 native propagation\"\n",
                          "        NATIVE_STATUS = \"exact float64 native propagation\"\n"
                          "        batch = getattr(library, \"robotron_sumtree_batch_update\", None)\n"
                          "        if batch is not None:\n"
                          "            batch.argtypes = (ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64,\n"
                          "                              ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64)\n"
                          "            batch.restype = ctypes.c_int\n"
                          "            _BATCH_FUNCTION = batch\n"
                          "            NATIVE_BATCH_AVAILABLE = True\n")
    prototype = (DIRECTORY / "native_batch_update.py").read_text()
    start = prototype.index("    if (not isinstance(tree, np.ndarray)")
    end = prototype.index("\n\n\ndef batch_update(owner", start)
    validation = prototype[start:end].replace("return bool(load()(", "return bool(_BATCH_FUNCTION(")
    helper = '''\n\ndef batch_update(tree, capacity, indices, priorities):
    """Default-off exact batched propagation; False leaves the old path intact.

    Enable before process startup with DQN_NATIVE_BATCH_UPDATE=1. The caller
    owns the replay lock, including this GIL-released C call. Unsupported ABI,
    aliases, non-finite priorities and empty input retain NumPy semantics.
    """
    if not NATIVE_BATCH_ENABLED or _BATCH_FUNCTION is None:
        return False
'''
    native = replace_once(native, "\n\n_load_native()\n", helper + validation + "\n\n\n_load_native()\n")
    proposed[FILES[0]] = native
    replay = proposed[FILES[1]]
    replay = replace_once(replay, "\ntry:\n    from .config import RL_CONFIG", '''
try:
    from .native_sumtree import batch_update as _native_batch_update
except ImportError:
    try:
        from native_sumtree import batch_update as _native_batch_update
    except ImportError:
        _native_batch_update = None

try:
    from .config import RL_CONFIG''')
    replay = replace_once(replay, "        tree_idx = data_indices.astype(np.int64) + self.capacity\n",
                          "        if (_native_batch_update is not None\n"
                          "                and _native_batch_update(self.tree, self.capacity, data_indices, priorities)):\n"
                          "            mx = float(priorities.max())\n"
                          "            if mx > self.max_priority:\n"
                          "                self.max_priority = mx\n"
                          "            return\n"
                          "        tree_idx = data_indices.astype(np.int64) + self.capacity\n")
    proposed[FILES[1]] = replay
    c = replace_once(proposed[FILES[2]], "#include <stdint.h>\n",
                     "#include <stdint.h>\n#include <stddef.h>\n#include <stdlib.h>\n")
    extra = (DIRECTORY / "batch_update.c").read_text()
    extra = extra[extra.index("static int compare_index"):]
    proposed[FILES[2]] = c.rstrip() + "\n\n/* Optional exact batch path; existing scalar/gather functions above are unchanged. */\n" + extra
    patches = []
    manifest = {"state": "PREPARED ONLY; no production edits", "env": "DQN_NATIVE_BATCH_UPDATE=1",
                "default": "disabled; unchanged NumPy path", "sources": {}}
    for name in FILES:
        for category, contents in (("before", original[name]), ("proposed", proposed[name])):
            path = DIRECTORY / category / Path(name).name
            path.parent.mkdir(exist_ok=True)
            path.write_text(contents)
        manifest["sources"][name] = {"before_sha256": hashlib.sha256(original[name].encode()).hexdigest(),
                                      "proposed_sha256": hashlib.sha256(proposed[name].encode()).hexdigest()}
        patches.extend(difflib.unified_diff(original[name].splitlines(True), proposed[name].splitlines(True),
                                            fromfile="a/" + name, tofile="b/" + name))
    patch = DIRECTORY / "native-batch-default-off.patch"
    patch.write_text("".join(patches))
    manifest["patch_sha256"] = hashlib.sha256(patch.read_bytes()).hexdigest()
    (DIRECTORY / "integration-prepared.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
