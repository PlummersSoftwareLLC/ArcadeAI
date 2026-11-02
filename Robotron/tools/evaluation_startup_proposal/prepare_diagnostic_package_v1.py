"""Create a new isolated source package only; never launch or import game code."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import time

GAME = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE_MANIFEST = GAME / 'tools/quality_capacity_proposal/profile04/runtime-source-package.json'
BASE_ROOT = BASE_MANIFEST.parent / 'Robotron'
BASE_SHA = '3ee43f9bd95fdda8f02abc048999a84513da71125dfd6b2e6558f45d2de6caf9'
INPUTS = {
    'prepare_startup_lua_v1.py': '2405f837982fd0df43230599409ab04b25655da30c6132d9aa7f1ae1e0dfa3d0',
    'prepare_startup_server_v1.py': 'eb11f4ca578088ab20980eefba5ff40bde47ee283133d3ced6ee5881baefc6ca',
    'startup_prefix_v1.lua': '07fda72281355fd6bd78439533b337c0a8aea66b77b7c53e8085483ce09d3d61',
    'startup_server_prefix_v1.py': '77992b95bac8da672e3b24e1f1cf2d7ea2a65943ee0785597d3c96867c072a37',
}
CHANGED = {'Scripts/main.lua', 'Scripts/dqn/socket_server.py'}
ADDED = {'Scripts/startup_prefix_v1.lua', 'Scripts/startup_server_prefix_v1.py'}


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def read(path, *, expected_sha=None, maximum_bytes=4*1024*1024):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve(strict=True), 'Exact source path required')
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= maximum_bytes
            and stat.S_IMODE(before.st_mode) == 0o444
            and before.st_uid == os.getuid() and before.st_nlink == 1,
            'Expected bounded immutable single-link owned source')
    with path.open('rb') as stream:
        raw = stream.read(maximum_bytes + 1)
    after = path.stat()
    require(len(raw) <= maximum_bytes and identity(before) == identity(after), 'Source changed during read')
    sha = hashlib.sha256(raw).hexdigest()
    require(expected_sha is None or sha == expected_sha, 'Source SHA differs')
    return raw, dict(path=str(path), sha256=sha, bytes=len(raw), identity=identity(after))


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate manifest key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('Nonfinite manifest number: ' + value)
    result = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    require(isinstance(result, dict), 'Manifest must be an object')
    return result


def relative(name):
    require(isinstance(name, str) and name and '\\' not in name and '\x00' not in name,
            'Invalid relative source name')
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name
            and all(part not in ('', '.', '..') for part in path.parts), 'Noncanonical source name')
    require(path.suffix in ('.py', '.lua', '.c', '.h'), 'Unexpected runtime source type')
    return Path(*path.parts)


def declared_files(manifest):
    files = manifest.get('files')
    require(isinstance(files, dict) and type(manifest.get('source_count')) is int
            and manifest['source_count'] == len(files) == 123, 'Exact parent file count required')
    for name, sha in files.items():
        relative(name)
        require(isinstance(sha, str) and len(sha) == 64
                and all(c in '0123456789abcdef' for c in sha), 'Invalid source hash')
    require(CHANGED <= set(files) and not ADDED & set(files), 'Changed/added source scope differs')
    return files


def destination(path):
    path = Path(path)
    require(all(ord(c) < 128 for c in str(path)), 'Package path must support exact Lua string literals')
    require(path.is_absolute() and path == path.resolve(), 'Absolute canonical new package path required')
    require(path.parent.is_dir() and not path.exists(), 'New package directory with existing parent required')
    forbidden = (BASE_ROOT, GAME/'Scripts', GAME/'models_dqn')
    require(path != GAME and not GAME.is_relative_to(path)
            and not any(path.is_relative_to(p) or p.is_relative_to(path) for p in forbidden),
            'Package destination overlaps protected source/model paths')
    return path


def checked_builder(name, path, entry):
    read(path, expected_sha=entry['sha256'])
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(read(path)[1] == entry, 'Builder changed during import')
    return module


def publish(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    retained, entry = read(path)
    require(retained == raw, 'Published source bytes differ')
    return entry


def inventory(root, expected):
    root = Path(root)
    found = set()
    directories = [root]
    for current, subdirs, files in os.walk(root, followlinks=False):
        current = Path(current)
        require(not current.is_symlink(), 'Package directory is a symlink')
        require(len(directories) <= 512 and len(found) <= 256, 'Package tree exceeds inventory bounds')
        for name in subdirs:
            child = current/name
            require(not child.is_symlink(), 'Package directory symlink')
            directories.append(child)
        for name in files:
            child = current/name
            require(child.is_file() and not child.is_symlink(), 'Unexpected package entry')
            found.add(child.relative_to(root).as_posix())
    require(found == set(expected), 'Package inventory differs from exact declared sources')
    return directories


def prepare(output):
    output = destination(output)
    _, packager_pin = read(Path(__file__).resolve())
    raw_manifest, parent_pin = read(BASE_MANIFEST, expected_sha=BASE_SHA, maximum_bytes=512*1024)
    parent = decode(raw_manifest)
    require(parent.get('root') == str(BASE_ROOT), 'Exact frozen parent root required')
    files = declared_files(parent)
    payloads, originals = {}, {}
    for name, sha in sorted(files.items()):
        payloads[name], originals[name] = read(BASE_ROOT/relative(name), expected_sha=sha)
    require(sum(map(len, payloads.values())) == parent.get('byte_count') == 2444084,
            'Parent byte inventory differs')
    inputs = {}
    helper_bytes = {}
    for name, sha in INPUTS.items():
        helper_bytes[name], inputs[name] = read(HERE/name, expected_sha=sha)
    lua = checked_builder('_diagnostic_package_Lua_builder', HERE/'prepare_startup_lua_v1.py',
                          inputs['prepare_startup_lua_v1.py'])
    server = checked_builder('_diagnostic_package_server_builder', HERE/'prepare_startup_server_v1.py',
                             inputs['prepare_startup_server_v1.py'])
    root = output/'Robotron'
    base_lua = payloads['Scripts/main.lua'].decode()
    base_server = payloads['Scripts/dqn/socket_server.py'].decode()
    proposal_lua = lua.build(base_lua, root/'Scripts/startup_prefix_v1.lua', files['Scripts/main.lua'])
    proposal_server = server.build(base_server)
    require(lua.stripped(proposal_lua) == base_lua, 'Lua reversibility differs')
    require(server.stripped_tree(proposal_server) == ast.dump(ast.parse(base_server),include_attributes=False),
            'Server operational AST differs')
    payloads['Scripts/main.lua'] = proposal_lua.encode()
    payloads['Scripts/dqn/socket_server.py'] = proposal_server.encode()
    payloads['Scripts/startup_prefix_v1.lua'] = helper_bytes['startup_prefix_v1.lua']
    payloads['Scripts/startup_server_prefix_v1.py'] = helper_bytes['startup_server_prefix_v1.py']
    changed = {name for name in files if hashlib.sha256(payloads[name]).hexdigest() != files[name]}
    require(changed == CHANGED and len(payloads) == 125, 'Only two changes/two additions are permitted')
    output.mkdir(mode=0o755)
    root.mkdir(mode=0o755)
    copied = {}
    for name, raw in sorted(payloads.items()):
        path = root/relative(name)
        path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
        copied[name] = publish(path,raw)
    directories = inventory(root, copied)
    for name, entry in originals.items():
        require(read(BASE_ROOT/relative(name))[1] == entry, 'Frozen parent source changed')
    for name, entry in inputs.items():
        require(read(HERE/name)[1] == entry, 'Diagnostic input changed')
    require(read(BASE_MANIFEST)[1] == parent_pin, 'Parent manifest changed')
    require(read(Path(__file__).resolve())[1] == packager_pin, 'Package builder changed')
    manifest = dict(schema='robotron-private-startup-diagnostic-package-v1',unix_s=time.time(),
        root=str(root),parent_manifest=parent_pin,builder_source=packager_pin,builder_inputs=inputs,
        source_count=125,byte_count=sum(e['bytes'] for e in copied.values()),
        files={name:e['sha256'] for name,e in copied.items()},file_pins=copied,
        changed_parent_files=sorted(CHANGED),added_files=sorted(ADDED),unchanged_parent_files=121,
        Lua_exact_original_reversible=True,server_entire_operational_AST_preserved=True,
        game_journal_and_measurement_byte_identical=True,production_changed=False,
        current_cohort_altered=False,launch_selected=False,protocol_selected=False,
        real_ROM_start_proven=False,quality_qualified=False,learning_speed_gain_verified=False,
        remaining_required_work=['Private diagnostic runner and bounded launcher with full failure contracts',
            'Original birth/session/source/ROM/output/clock isolation; preserve original prefix bytes',
            'Real ROM validation only after current private study closes',
            'Actual ROM start-acceptance proof and prospective identical-role protocol before any new eligibility rule'])
    entry = publish(output/'runtime-source-package.json',
                    (json.dumps(manifest,indent=2,allow_nan=False)+'\n').encode())
    for directory in [*reversed(directories),output,output.parent]:
        fd = os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    return entry


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY: no source reads, imports, package writes, process discovery or launches')
    else:
        if args.output is None:parser.error('--output required')
        print(json.dumps(dict(package=prepare(args.output),launch_selected=False,protocol_selected=False)))
