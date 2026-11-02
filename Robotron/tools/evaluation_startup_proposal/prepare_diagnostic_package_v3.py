"""Build a new 126-file passive-tap package; no emulator or numerical imports."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
UTIL_PATH = HERE/'prepare_diagnostic_package_v1.py'
UTIL_SHA = '0856ed1a51b741a0cdb013e1af575362fcbd3d0a0e4289e2959b74077cd65098'
INPUTS = {
    'prepare_startup_lua_v1.py': '2405f837982fd0df43230599409ab04b25655da30c6132d9aa7f1ae1e0dfa3d0',
    'prepare_startup_server_v2.py': '55ad2f41dd9dccbb58708c1317b9aebcd614c33d9eb5560cd686bfae4b2c7f14',
    'startup_prefix_v1.lua': '07fda72281355fd6bd78439533b337c0a8aea66b77b7c53e8085483ce09d3d61',
    'startup_server_prefix_v2.py': '0d2a612b6cfa1726e7f0c9f163d0484a8ce3c29cc3ee8e06323c798032f7c7ba',
}
CHANGED = {'Scripts/main.lua', 'Scripts/dqn/socket_server.py'}
ADDED = {'Scripts/startup_prefix_v1.lua', 'Scripts/startup_server_prefix_v2.py',
         'Scripts/startup_acceptance_tap_v1.lua'}


def utilities():
    before = UTIL_PATH.stat()
    raw = UTIL_PATH.read_bytes()
    if (hashlib.sha256(raw).hexdigest() != UTIL_SHA or before != UTIL_PATH.stat()
            or before.st_mode & 0o777 != 0o444 or before.st_uid != os.getuid()
            or before.st_nlink != 1 or UTIL_PATH != UTIL_PATH.resolve(strict=True)):
        raise ValueError('Immutable utility source differs')
    spec = importlib.util.spec_from_file_location('_passive_package_immutable_utilities', UTIL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if UTIL_PATH.stat() != before:
        raise ValueError('Utility changed during import')
    module.read(UTIL_PATH, expected_sha=UTIL_SHA)
    return module


def prepare(output):
    u = utilities()
    output = u.destination(output)
    _, self_pin = u.read(Path(__file__).resolve())
    _, utility_pin = u.read(UTIL_PATH, expected_sha=UTIL_SHA)
    raw_parent, parent_pin = u.read(u.BASE_MANIFEST, expected_sha=u.BASE_SHA, maximum_bytes=512*1024)
    parent = u.decode(raw_parent)
    u.require(parent.get('root') == str(u.BASE_ROOT), 'Exact frozen parent root required')
    files = u.declared_files(parent)
    payloads, originals = {}, {}
    for name, sha in sorted(files.items()):
        payloads[name], originals[name] = u.read(u.BASE_ROOT/u.relative(name), expected_sha=sha)
    u.require(sum(map(len, payloads.values())) == parent.get('byte_count') == 2444084,
              'Frozen byte inventory differs')
    inputs, helpers = {}, {}
    for name, sha in INPUTS.items():
        helpers[name], inputs[name] = u.read(HERE/name, expected_sha=sha)
    # These new inputs have full immutable identities in the published manifest;
    # a caller's prospective CPU/job pins must bind them before prepare is called.
    for name in ('prepare_acceptance_lua_v1.py', 'startup_acceptance_tap_v1.lua'):
        helpers[name], inputs[name] = u.read(HERE/name)
    lua = u.checked_builder('_passive_package_raw_lua', HERE/'prepare_startup_lua_v1.py',
                            inputs['prepare_startup_lua_v1.py'])
    server = u.checked_builder('_passive_package_raw_server', HERE/'prepare_startup_server_v2.py',
                               inputs['prepare_startup_server_v2.py'])
    tap = u.checked_builder('_passive_package_tap_lua', HERE/'prepare_acceptance_lua_v1.py',
                            inputs['prepare_acceptance_lua_v1.py'])
    root = output/'Robotron'
    base_lua = payloads['Scripts/main.lua'].decode()
    base_server = payloads['Scripts/dqn/socket_server.py'].decode()
    raw_lua = lua.build(base_lua, root/'Scripts/startup_prefix_v1.lua', files['Scripts/main.lua'])
    combined = tap.build(raw_lua, root/'Scripts/startup_acceptance_tap_v1.lua',
                         hashlib.sha256(raw_lua.encode()).hexdigest())
    proposed_server = server.build(base_server)
    u.require(tap.stripped(combined) == raw_lua and lua.stripped(tap.stripped(combined)) == base_lua,
              'Nested Lua reversibility differs')
    u.require(server.stripped_tree(proposed_server) == ast.dump(ast.parse(base_server), include_attributes=False),
              'Entire server operational AST differs')
    payloads['Scripts/main.lua'] = combined.encode()
    payloads['Scripts/dqn/socket_server.py'] = proposed_server.encode()
    for name in ADDED:
        payloads[name] = helpers[Path(name).name]
    changed = {name for name in files if hashlib.sha256(payloads[name]).hexdigest() != files[name]}
    u.require(changed == CHANGED and len(payloads) == 126, 'Only two changes/three additions permitted')
    output.mkdir(mode=0o755)
    root.mkdir(mode=0o755)
    copied = {}
    for name, raw in sorted(payloads.items()):
        path = root/u.relative(name)
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        copied[name] = u.publish(path, raw)
    directories = u.inventory(root, copied)
    for name, entry in originals.items():
        u.require(u.read(u.BASE_ROOT/u.relative(name))[1] == entry, 'Frozen parent changed')
    for name, entry in inputs.items():
        u.require(u.read(HERE/name)[1] == entry, 'Proposal input changed')
    u.require(u.read(u.BASE_MANIFEST)[1] == parent_pin and u.read(UTIL_PATH)[1] == utility_pin
              and u.read(Path(__file__).resolve())[1] == self_pin, 'Builder or parent manifest changed')
    manifest = dict(schema='robotron-private-startup-diagnostic-package-v2', unix_s=time.time(),
        root=str(root), parent_manifest=parent_pin, builder_source=self_pin,
        utility_source=utility_pin, builder_inputs=inputs, source_count=126,
        byte_count=sum(e['bytes'] for e in copied.values()),
        files={name:e['sha256'] for name,e in copied.items()}, file_pins=copied,
        changed_parent_files=sorted(CHANGED), added_files=sorted(ADDED), unchanged_parent_files=121,
        Lua_exact_raw_prefix_reversible=True, Lua_exact_original_reversible=True,
        server_entire_operational_AST_preserved=True, game_journal_and_measurement_byte_identical=True,
        tap_package_integration_present=True, tap_runtime_integration_present=False,
        production_changed=False, current_cohort_altered=False, launch_selected=False,
        protocol_selected=False, installed_binary_ABI_proven=False, real_ROM_start_proven=False,
        quality_qualified=False, learning_speed_gain_verified=False,
        remaining_required_work=['New runtime/launcher source versions bound to this exact126 manifest',
            'Collect and independently join raw Lua/server/tap evidence, including every invalid/partial prefix',
            'Real MAME ABI and loaded-byte proof after original current study/review closes and winner protection',
            'First-start certification and a prospective identical-role quality protocol before any eligibility change'])
    result = u.publish(output/'runtime-source-package.json',
                       (json.dumps(manifest, indent=2, allow_nan=False)+'\n').encode())
    for directory in [*reversed(directories), output, output.parent]:
        fd = os.open(directory, os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY: no source reads, imports, package writes, process discovery or launches')
    else:
        if args.output is None:
            parser.error('--output required')
        print(json.dumps(dict(package=prepare(args.output), launch_selected=False, protocol_selected=False)))
