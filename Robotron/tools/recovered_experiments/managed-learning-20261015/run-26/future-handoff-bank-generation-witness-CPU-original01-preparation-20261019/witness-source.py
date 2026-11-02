"""Read-only bank-generation checks for an independently quiesced trainer.

Checks metadata and array headers, never reads or hashes the large bank state
payloads. A result proves neither all data values nor input-source quiescence.
The caller must separately enforce the verified maintenance protocol.
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


FIELDS = dict(states='<f4', next_states='<f4', actions='<i8', rewards='<f4',
              dones='<f4', horizons='<i4', is_expert='|u1', actor_kind='|u1')
META_FIELDS = {'ep_score', 'ep_len', 'ep_game', 'ep_level', 'stale_age',
               'stale_age_normal', 'stride', 'state_size', 'captured_adds', 'mutation_generation'}


def require(value, message):
    if not value:
        raise ValueError(message)


def integer(value):
    return type(value) is int and value >= 0


def identity(value):
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
                uid=value.st_uid, nlink=value.st_nlink)


def open_regular(path):
    path = Path(path)
    require(path.resolve(strict=True) == path, 'Symlink/path alias is forbidden')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    value = os.fstat(fd)
    try:
        require(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid()
                and value.st_nlink == 1, 'Bank input is not an owned single-link regular file')
    except BaseException:
        os.close(fd)
        raise
    return os.fdopen(fd, 'rb'), identity(value)


def small_file(path, maximum):
    stream, before = open_regular(path)
    with stream:
        require(before['bytes'] <= maximum, 'Bank metadata exceeds the bounded read size')
        data = stream.read(maximum+1)
        require(len(data) == before['bytes'] and identity(os.fstat(stream.fileno())) == before,
                'Bank metadata changed during read')
    require(identity(Path(path).stat()) == before, 'Bank metadata path changed')
    return data, dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), **before)


def strict_json(data):
    def pairs(values):
        require(len(values) == len({k for k, _ in values}), 'Duplicate bank selector key')
        return dict(values)
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda value: require(False, 'Nonfinite selector constant'))


def npy_header(stream):
    require(stream.read(6) == b'\x93NUMPY', 'Invalid NPY magic')
    version = stream.read(2)
    require(version in (b'\x01\x00', b'\x02\x00', b'\x03\x00'), 'Unsupported NPY header version')
    width = 2 if version == b'\x01\x00' else 4
    length_raw = stream.read(width)
    require(len(length_raw) == width, 'Truncated NPY header length')
    length = int.from_bytes(length_raw, 'little')
    require(0 < length <= 65536, 'NPY header exceeds its bound')
    raw = stream.read(length)
    require(len(raw) == length, 'Truncated NPY header')
    expression = ast.parse(raw.decode('utf-8' if version == b'\x03\x00' else 'latin1').strip(), mode='eval')
    require(isinstance(expression.body, ast.Dict), 'NPY header is not a dictionary')
    value = ast.literal_eval(expression)
    require(len(expression.body.keys) == len(value) and set(value) == {'descr', 'fortran_order', 'shape'},
            'NPY header keys are duplicate or unexpected')
    require(value['fortran_order'] is False and isinstance(value['shape'], tuple)
            and all(integer(n) for n in value['shape']), 'Unsupported NPY shape/order')
    require(value['descr'] in ('<f4', '<f8', '<i4', '<i8', '|u1'), 'Unsupported/object NPY dtype')
    offset = 8 + width + length
    count = math.prod(value['shape'])
    require(count <= (1 << 48), 'NPY element count exceeds its bound')
    return value, offset, count * int(value['descr'][-1])


def meta_array(data):
    stream = io.BytesIO(data)
    header, offset, payload = npy_header(stream)
    require(offset+payload == len(data), 'Metadata NPY byte size differs')
    code = {'<f4': 'f', '<f8': 'd', '<i4': 'i', '<i8': 'q', '|u1': 'B'}[header['descr']]
    values = [v[0] for v in struct.iter_unpack('<'+code, data[offset:])]
    return header, values


def read_bank_generation(bank, directory, *, state_size=11128):
    require(bank in ('hof', 'ephof') and integer(state_size) and state_size > 0, 'Bank scope differs')
    directory = Path(directory)
    require(directory.resolve(strict=True) == directory and directory.is_dir(), 'Bank directory alias')
    pointer = directory/'CURRENT.json'
    raw, pointer_pin = small_file(pointer, 4096)
    selected = strict_json(raw)
    require(isinstance(selected, dict) and set(selected) ==
            {'schema', 'bank', 'generation', 'previous', 'mutation_generation'}, 'Bank selector schema differs')
    generation = selected['generation']
    require(selected['schema'] == 'robotron-bank-generation-v1' and selected['bank'] == bank
            and type(generation) is str and re.fullmatch(r'gen-[0-9a-f]{32}', generation)
            and integer(selected['mutation_generation']), 'Invalid bank generation selector')
    previous = selected['previous']
    require(previous is None or (type(previous) is str and re.fullmatch(r'gen-[0-9a-f]{32}', previous)),
            'Invalid previous generation')
    chosen = directory/'generations'/generation
    require(chosen.resolve(strict=True) == chosen and chosen.is_dir(), 'Selected generation alias or missing')
    metadata_raw, metadata_pin = small_file(chosen/(bank+'_meta.npz'), 1 << 20)
    with zipfile.ZipFile(io.BytesIO(metadata_raw)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and set(names) == {n+'.npy' for n in META_FIELDS},
                'Bank metadata members differ')
        require(all(v.file_size <= 128 << 10 for v in archive.infolist())
                and sum(v.file_size for v in archive.infolist()) <= 1 << 20,
                'Uncompressed bank metadata exceeds its bound')
        metadata = {n: meta_array(archive.read(n+'.npy')) for n in META_FIELDS}
    def scalar(name):
        header, values = metadata[name]
        require(header['shape'] == () and header['descr'] == '<i8' and len(values) == 1,
                'Bank scalar metadata differs')
        return values[0]
    count = len(metadata['ep_len'][1])
    stride = scalar('stride')
    require(0 < count <= 16384 and 0 < stride <= (1 << 20) and scalar('state_size') == state_size,
            'Bank episode geometry differs')
    require(scalar('mutation_generation') == selected['mutation_generation'],
            'Selector and metadata revisions differ')
    require(scalar('captured_adds') >= 0, 'Captured replay-add clock is invalid')
    for field, dtype in [('ep_score','<f8'), ('ep_len','<i4'), ('ep_game','<i8'), ('ep_level','<i4')]:
        header, values = metadata[field]
        require(header['shape'] == (count,) and header['descr'] == dtype, 'Bank episode metadata shape/dtype differs')
    lengths = metadata['ep_len'][1]
    require(all(0 <= n <= stride for n in lengths) and all(math.isfinite(v) for v in metadata['ep_score'][1]),
            'Invalid episode lengths or scores')
    arrays = {}
    for field, dtype in FIELDS.items():
        path = chosen/(bank+'_'+field+'.npy')
        stream, before = open_regular(path)
        with stream:
            header, offset, payload = npy_header(stream)
            expected = (count*stride, state_size) if field in ('states', 'next_states') else (count*stride,)
            require(header['shape'] == expected and header['descr'] == dtype
                    and before['bytes'] == offset+payload, 'Bank array geometry/dtype/file size differs: '+field)
            require(identity(os.fstat(stream.fileno())) == before, 'Bank array changed during header read')
        require(identity(path.stat()) == before, 'Bank array path changed during header read')
        arrays[field] = dict(path=str(path), header=header, **before)
    ended_raw, ended_pin = small_file(pointer, 4096)
    require(ended_raw == raw and ended_pin == pointer_pin, 'CURRENT changed during bank capture')
    return dict(bank=bank, selector=selected, pointer=pointer_pin, metadata=metadata_pin,
                episodes=count, transitions=sum(lengths), stride=stride, state_size=state_size,
                captured_adds=scalar('captured_adds'), arrays=arrays,
                state_payload_read_or_hashed=False)


def validate_paused_bank_pair(before, after, banks, *, expected_pid, now):
    """Validate two paused API views around disk reads; caller seals inputs."""
    require(set(banks) == {'hof', 'ephof'} and type(expected_pid) is int and expected_pid > 0,
            'Both original bank/owner scopes are required')
    for api in (before, after):
        require(type(api.get('ts')) in (int, float) and math.isfinite(api['ts'])
                and 0 <= now-api['ts'] <= 5, 'Stale, future or nonfinite API')
        age = api.get('pipeline_snapshot_age_s')
        require(type(age) in (int, float) and math.isfinite(age) and 0 <= age <= 5
                and api.get('pipeline_read_error') == api.get('bank_persistence_read_error') == '',
                'Stale or failed pipeline/bank snapshot')
        managed = api['managed_measurement']
        require(api['training_enabled'] is False and api['measurement_active'] is True
                and managed['active'] is True and managed['phase'] in ('warming', 'collecting', 'draining')
                and type(managed['generation']) is int and managed['generation'] > 0,
                'Supported measurement pause is not active')
        pipe = api['host_pipeline']
        optimizer = pipe['learning_exposure']['optimizer']
        replay = pipe['learning_exposure']['replay']
        require(pipe['available'] is True and optimizer['enabled'] is True and replay['enabled'] is True
                and optimizer['process_id'] == replay['process_id'] == expected_pid,
                'Original pipeline/exposure owner differs')
        total = optimizer['total']
        require(all(integer(total.get(k)) for k in ('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable'))
                and total['attempts_started'] == total['outcomes_recorded'] == total['applied']+total['amp_skipped']
                and total['unavailable'] == 0 and optimizer['unclassified_started_total'] == 0
                and optimizer['available'] is True, 'Unfinished/unclassified optimizer work remains')
        bank = api['bank_persistence']
        require(bank['writer_active'] is False and type(bank['write_failures']) is int
                and bank['write_failures'] == 0 and bank['last_error'] is None
                and bank['output']['active'] is None,
                'Bank writer is active or failed')
        for name in banks:
            require(integer(bank['revision'][name]) and integer(bank['saved_revision'][name])
                    and bank['dirty'][name] is False
                    and bank['revision'][name] == bank['saved_revision'][name] ==
                        banks[name]['selector']['mutation_generation'], 'RAM/disk bank revision not sealed: '+name)
    require(before['ts'] <= after['ts'], 'API time regressed')
    require(before['managed_measurement']['generation'] == after['managed_measurement']['generation']
            and before['managed_measurement']['label'] == after['managed_measurement']['label'],
            'Measurement generation/label changed')
    for name in ('frame_count','learner_frame_count','measurement_frames','training_steps','optimized_samples'):
        require(before[name] == after[name] and integer(before[name]), 'Paused clock moved: '+name)
    for name in ('generation',):
        require(before['host_pipeline'][name] == after['host_pipeline'][name], 'Pipeline generation changed')
    elapsed = [api['host_pipeline']['elapsed_s'] for api in (before, after)]
    require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in elapsed)
            and elapsed[1] > elapsed[0], 'Two views reused one cached pipeline/bank sample')
    for name in ('optimizer', 'replay'):
        left = before['host_pipeline']['learning_exposure'][name]
        right = after['host_pipeline']['learning_exposure'][name]
        require(type(left['epoch']) is int and left['epoch'] > 0 and left['epoch'] == right['epoch'],
                'Exposure restore/load epoch changed')
        keys = ('total',) if name == 'optimizer' else ('accepted_total', 'accepted_learner_total', 'accepted_by_source_total')
        require(all(left[k] == right[k] for k in keys), 'Paused '+name+' counters moved')
    return dict(status='PAUSED_BANK_REVISION_AND_GEOMETRY_PAIR_VERIFIED',
                expected_pid=expected_pid, banks=banks, independent_sealed_input_witness_required=True,
                actual_state_payload_values_verified=False, production_handoff_ready=False)
