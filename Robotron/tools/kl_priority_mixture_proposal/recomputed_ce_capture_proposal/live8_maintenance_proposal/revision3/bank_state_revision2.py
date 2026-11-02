"""Bounded stdlib-only stopped replay/bank descriptor and startup mmap proofs.

No imports of NumPy/Torch; no array-body reads except small ring/bank metadata.
stopped_state(spec) -> {schema,spec,ring:{directory,meta,arrays},banks:{hof,ephof}}.
Each bank has counts:{episodes,transitions}, selector, generation, metadata,
arrays and canonical directory identities. assert_unchanged returns a fresh equal
snapshot or raises. verify_maps returns exact-PID/start/maps proof for the NINE
persistent ring storage maps, not temporary priorities/meta or bank RAM equality.
Callers own stopped/live identities, no-writer window and source/config binding.
Revision2: only the nine ring storage fields accept source-declared fallocate
logical padding; selected bank/priorities payload extents remain exact.
"""
import ast
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import zipfile

SCHEMA = 'robotron-live8-stopped-replay-bank-descriptors-v1'
BANK_SCHEMA = 'robotron-bank-generation-v1'
MAX_HEADER = 65536
MAX_METADATA = 4 << 20
MAX_SELECTOR = 16384
MAX_MAPS = 8 << 20
DTYPES = {'<f2': ('e', 2), '<f4': ('f', 4), '<f8': ('d', 8),
          '<i4': ('i', 4), '<i8': ('q', 8), '|u1': ('B', 1)}
BANK_FIELDS = ('states', 'next_states', 'actions', 'rewards', 'dones', 'horizons', 'is_expert', 'actor_kind')
SCALARS = ('stale_age', 'stale_age_normal', 'stride', 'state_size', 'captured_adds', 'mutation_generation')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def file_identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, size=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, nlink=info.st_nlink)


def canonical(value):
    require(isinstance(value, str), 'Explicit string path required')
    path = Path(value)
    require(path.is_absolute() and path == path.resolve(strict=True), 'Path is not canonical/nonsymlink: ' + value)
    return path


def directory_identity(value):
    path = canonical(value)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(), 'Expected owned real directory')
    # Parent directory child activity is not an object replacement. Selected
    # files/selector have their own complete identity/hash and directory inode.
    return dict(path=str(path), device=info.st_dev, inode=info.st_ino,
                mode=stat.S_IMODE(info.st_mode), uid=info.st_uid)


def open_file(value):
    path = canonical(value)
    stream = os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb')
    try:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1,
                'Expected owned regular single-link descriptor')
        before = file_identity(info)
        require(file_identity(path.lstat()) == before, 'Opened path/descriptor differ')
        return path, stream, before
    except BaseException:
        stream.close()
        raise


def finish_file(path, stream, before):
    require(file_identity(os.fstat(stream.fileno())) == before == file_identity(path.lstat()),
            'Descriptor/path changed while inspected: ' + str(path))


def read_small(value, limit):
    path, stream, before = open_file(value)
    with stream:
        require(before['size'] <= limit, 'Metadata exceeds fixed bound')
        raw = stream.read(limit + 1)
        require(len(raw) == before['size'] and len(raw) <= limit, 'Metadata changed/exceeds bound')
        finish_file(path, stream, before)
    return raw, dict(path=str(path), identity=before, sha256=hashlib.sha256(raw).hexdigest())


def read_exact(stream, count):
    value = stream.read(count)
    require(len(value) == count, 'Truncated NPY header/metadata')
    return value


def parse_header(stream):
    magic = read_exact(stream, 8)
    require(magic[:6] == b'\x93NUMPY' and magic[6:] in (b'\x01\x00', b'\x02\x00', b'\x03\x00'), 'Unsupported NPY magic/version')
    width = 2 if magic[6] == 1 else 4
    length_raw = read_exact(stream, width)
    length = int.from_bytes(length_raw, 'little')
    require(0 < length <= MAX_HEADER, 'NPY header exceeds fixed bound')
    encoded = read_exact(stream, length)
    encoding = 'utf8' if magic[6] == 3 else 'latin1'
    header = ast.literal_eval(encoded.decode(encoding))
    require(isinstance(header, dict) and set(header) == {'descr', 'fortran_order', 'shape'}
            and header['fortran_order'] is False and header['descr'] in DTYPES,
            'Unsupported/object/structured/Fortran NPY dtype/header')
    shape = header['shape']
    require(isinstance(shape, tuple) and len(shape) <= 2
            and all(type(n) is int and n >= 0 for n in shape), 'Invalid NPY shape')
    count = math.prod(shape)
    require(count <= (1 << 63) // DTYPES[header['descr']][1], 'NPY extent overflow')
    prefix = magic + length_raw + encoded
    return dict(dtype=header['descr'], shape=list(shape), data_offset=len(prefix),
                data_bytes=count * DTYPES[header['descr']][1], header_sha256=hashlib.sha256(prefix).hexdigest())


def array_header(value, dtype, shape, *, replay_preallocation=False):
    path, stream, before = open_file(value)
    with stream:
        header = parse_header(stream)
        require(header['dtype'] == dtype and header['shape'] == list(shape), 'Array geometry/dtype differs: ' + str(path))
        exact_extent = header['data_offset'] + header['data_bytes']
        # Only replay._storage_specs fields may originate ensure_live_mmap's
        # posix_fallocate(fd, 0, data_bytes+4096), which extends logical length.
        # It never truncates a larger NPY header+body. Bank/priorities stay exact.
        allowed_extents = {exact_extent}
        if replay_preallocation:
            allowed_extents.add(max(exact_extent, header['data_bytes'] + 4096))
        require(before['size'] in allowed_extents, 'Array logical file length differs')
        finish_file(path, stream, before)
    return dict(path=str(path), identity=before, **header)


def small_npy(raw, dtype, shape):
    stream = io.BytesIO(raw)
    header = parse_header(stream)
    require(header['dtype'] == dtype and header['shape'] == list(shape)
            and len(raw) == header['data_offset'] + header['data_bytes'], 'Small metadata NPY geometry differs')
    require(header['data_bytes'] <= MAX_METADATA, 'Small NPY body too large')
    code, width = DTYPES[dtype]
    values = struct.unpack('<' + code * (header['data_bytes'] // width), read_exact(stream, header['data_bytes']))
    return values


def storage_specs(rows, width, *, bank=False):
    shapes = {name: ((rows, width) if name in ('states', 'next_states') else (rows,)) for name in BANK_FIELDS}
    types = dict(states='<f4' if bank else '<f2', next_states='<f4' if bank else '<f2',
                 actions='<i8', rewards='<f4', dones='<f4', horizons='<i4', is_expert='|u1', actor_kind='|u1')
    if not bank:
        shapes['interesting'] = (rows,); types['interesting'] = '<f4'
        shapes['priorities'] = (rows,); types['priorities'] = '<f8'
    return {name: (types[name], shape) for name, shape in shapes.items()}


def bank_metadata(value, stride, state_size, capacity):
    raw, descriptor = read_small(value, MAX_METADATA)
    required = {name + '.npy' for name in ('ep_len', 'ep_score', 'ep_game', 'ep_level', *SCALARS)}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(len(entries) == len(required) and {e.filename for e in entries} == required
                and len({e.filename for e in entries}) == len(entries), 'Bank NPZ metadata members differ')
        require(sum(e.file_size for e in entries) <= MAX_METADATA
                and all(e.file_size <= MAX_METADATA and e.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        and not (e.flag_bits & 1) for e in entries), 'Bank NPZ metadata bounds/compression differ')
        blobs = {}
        for entry in entries:
            with archive.open(entry) as stream:
                blob = stream.read(entry.file_size + 1)
            require(len(blob) == entry.file_size, 'Bank NPZ entry length differs')
            blobs[entry.filename[:-4]] = blob
    first = parse_header(io.BytesIO(blobs['ep_len']))
    require(first['dtype'] == '<i4' and len(first['shape']) == 1, 'Bank episode length geometry differs')
    episodes = first['shape'][0]
    require(0 < episodes <= capacity, 'Bank episodes outside declared capacity')
    lengths = small_npy(blobs['ep_len'], '<i4', (episodes,))
    scores = small_npy(blobs['ep_score'], '<f8', (episodes,))
    games = small_npy(blobs['ep_game'], '<i8', (episodes,))
    levels = small_npy(blobs['ep_level'], '<i4', (episodes,))
    scalars = {name: small_npy(blobs[name], '<i8', ())[0] for name in SCALARS}
    require(all(0 <= length <= stride for length in lengths) and sum(lengths) > 0
            and all(math.isfinite(score) for score in scores), 'Invalid bank length/score metadata')
    require(scalars['stride'] == stride and scalars['state_size'] == state_size
            and all(scalars[name] >= 0 for name in SCALARS), 'Bank stride/state/revision metadata differs')
    return dict(descriptor=descriptor, counts=dict(episodes=episodes, transitions=sum(lengths)),
                ep_len=list(lengths), ep_score=list(scores), ep_game=list(games), ep_level=list(levels), scalars=scalars)


def bank_state(bank, root, stride, state_size, capacity):
    before = directory_identity(str(root))
    selector_raw, selector = read_small(str(root / 'CURRENT.json'), MAX_SELECTOR)
    selected = json.loads(selector_raw)
    require(isinstance(selected, dict) and set(selected) == {'schema', 'bank', 'generation', 'previous', 'mutation_generation'}
            and selected['schema'] == BANK_SCHEMA and selected['bank'] == bank
            and isinstance(selected['generation'], str) and re.fullmatch(r'gen-[0-9a-f]{32}', selected['generation'])
            and (selected['previous'] is None or isinstance(selected['previous'], str)
                 and re.fullmatch(r'gen-[0-9a-f]{32}', selected['previous']))
            and type(selected['mutation_generation']) is int and selected['mutation_generation'] >= 0,
            'Invalid bank CURRENT selector')
    generation = root / 'generations' / selected['generation']
    generation_before = directory_identity(str(generation))
    metadata = bank_metadata(str(generation / (bank + '_meta.npz')), stride, state_size, capacity)
    require(metadata['scalars']['mutation_generation'] == selected['mutation_generation'], 'Selector/metadata revision differs')
    rows = metadata['counts']['episodes'] * stride
    arrays = {name: array_header(str(generation / (bank + '_' + name + '.npy')), dtype, shape)
              for name, (dtype, shape) in storage_specs(rows, state_size, bank=True).items()}
    require(read_small(str(root / 'CURRENT.json'), MAX_SELECTOR)[1] == selector
            and directory_identity(str(generation)) == generation_before
            and directory_identity(str(root)) == before, 'Selected bank changed during inspection')
    return dict(directory=before, selector=dict(descriptor=selector, value=selected),
                generation=generation_before, metadata=metadata, counts=metadata['counts'], arrays=arrays)


def stopped_state(spec):
    """No liveness assertion here: caller must bind root-owned stop/no-writer state."""
    require(isinstance(spec, dict) and set(spec) == {'ring', 'model_dir', 'capacity', 'state_size', 'episode_capacity', 'bank_strides'},
            'Invalid bank/ring spec')
    require(spec['capacity'] == 6000000 and spec['state_size'] == 11128 and spec['episode_capacity'] == 192
            and spec['bank_strides'] == {'hof': 1536, 'ephof': 2048}, 'Spec differs from current held replay geometry')
    ring, model = canonical(spec['ring']), canonical(spec['model_dir'])
    ring_before = directory_identity(str(ring)); model_before = directory_identity(str(model))
    raw, meta = read_small(str(ring / '_meta.npy'), MAX_HEADER + 64)
    ptr, size, maximum = small_npy(raw, '<f8', (3,))
    require(math.isfinite(ptr) and ptr.is_integer() and 0 <= ptr < spec['capacity']
            and math.isfinite(size) and size.is_integer() and size == spec['capacity']
            and math.isfinite(maximum) and maximum > 0, 'Ring ptr/size/max priority invalid')
    arrays = {name: array_header(str(ring / (name + '.npy')), dtype, shape, replay_preallocation=name != 'priorities')
              for name, (dtype, shape) in storage_specs(spec['capacity'], spec['state_size']).items()}
    banks = {name: bank_state(name, model / ('robotron_dqn_latest_replay_' + name),
                             spec['bank_strides'][name], spec['state_size'], spec['episode_capacity'])
             for name in ('hof', 'ephof')}
    require(read_small(str(ring / '_meta.npy'), MAX_HEADER + 64)[1] == meta
            and directory_identity(str(ring)) == ring_before and directory_identity(str(model)) == model_before,
            'Stopped metadata roots changed during inspection')
    return dict(schema=SCHEMA, spec={**spec, 'bank_strides': dict(spec['bank_strides'])}, ring=dict(directory=ring_before,
                meta=dict(descriptor=meta, ptr=int(ptr), size=int(size), max_priority=maximum), arrays=arrays),
                model_directory=model_before, banks=banks)


def assert_unchanged(snapshot, spec):
    fresh = stopped_state(spec)
    require(fresh == snapshot, 'Held replay/bank descriptor/header/metadata identity changed')
    return fresh


def process_start(pid):
    raw = (Path('/proc') / str(pid) / 'stat').read_text()
    require(int(raw.split(' ', 1)[0]) == pid and ')' in raw, 'Invalid exact PID stat')
    rest = raw[raw.rfind(')') + 2:].split()
    require(len(rest) > 19, 'Truncated exact PID stat')
    return int(rest[19])


def verify_maps(pid, snapshot):
    require(type(pid) is int and pid > 0 and snapshot.get('schema') == SCHEMA, 'Exact live PID/snapshot required')
    start = process_start(pid)
    with (Path('/proc') / str(pid) / 'maps').open('rb') as stream:
        raw = stream.read(MAX_MAPS + 1)
    require(len(raw) <= MAX_MAPS, 'Owned process maps exceeds fixed8MiB')
    expected = {value['path']: (name, value) for name, value in snapshot['ring']['arrays'].items() if name != 'priorities'}
    seen = {name: 0 for name, value in expected.values()}
    for line in raw.decode('utf8', errors='strict').splitlines():
        fields = line.split(None, 5)
        if len(fields) != 6:
            continue
        pathname = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), fields[5])
        if pathname.endswith(' (deleted)') and pathname[:-10] in expected:
            raise RuntimeError('Owned ring map is deleted')
        if pathname not in expected:
            continue
        name, descriptor = expected[pathname]
        major, minor = (int(part, 16) for part in fields[3].split(':'))
        current = descriptor['identity']
        require((major, minor, int(fields[4])) == (os.major(current['device']), os.minor(current['device']), current['inode']),
                'Mapped ring dev/inode differs: ' + name)
        if fields[1] == 'rw-s':
            seen[name] += 1
    require(all(count > 0 for count in seen.values()) and len(seen) == 9, 'Not every persistent ring storage field is mapped')
    require(process_start(pid) == start, 'Exact PID changed while reading maps')
    for pathname, (name, descriptor) in expected.items():
        require(file_identity(Path(pathname).lstat()) == descriptor['identity'],
                'Mapped ring file identity changed: ' + name)
    return dict(pid=pid, starttime_ticks=start, maps_sha256=hashlib.sha256(raw).hexdigest(),
                map_count_by_field=seen, scope='Nine writable-shared ring storage path/dev/inode maps; excludes temporary priorities/meta and bank RAM content')
