"""Bind and verify the actual isolated Lua chain; import performs no reads.

Only future jobs may select this correction. No launch, publication or controls.
The caller still owns fresh identities/design/family/controller qualification.
"""
import copy
import hashlib
import json
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
ENTRY_SHA = 'ccdbf67bd7dc8f7b8e7a8f8ab23f6eb73214bd5d21837fe660986ed04c9ac324'
ADAPTER_SHA = '366bb60cb18e2d4961c1c2142e929f5ddd88acd2b55343d4d2523cc4160823b6'
OLD_ENTRY_SHA = 'b6869212245eb88057251d04ba70fa9800587f66b5de33ca534eecca8294f2b0'


def pin(path):
    path = Path(path)
    before = path.lstat()
    assert stat.S_ISREG(before.st_mode) and not path.is_symlink()
    raw = path.read_bytes()
    after = path.stat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_uid', 'st_nlink')
    assert all(getattr(before, key) == getattr(after, key) for key in fields)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                identity=dict(device=after.st_dev, inode=after.st_ino, bytes=after.st_size,
                              mtime_ns=after.st_mtime_ns, ctime_ns=after.st_ctime_ns,
                              mode=oct(stat.S_IMODE(after.st_mode)), uid=after.st_uid, nlink=after.st_nlink))


def chain():
    entry = pin(HERE / 'full-tail-observation-slot64-main.lua')
    adapter = pin(HERE / 'full_startup_wire_slot64_v2.lua')
    guard = pin(__file__)
    assert entry['sha256'] == ENTRY_SHA and adapter['sha256'] == ADAPTER_SHA
    assert all(item['identity']['mode'] == '0o444' and item['identity']['nlink'] == 1
               for item in (entry, adapter, guard))
    text = Path(entry['path']).read_text()
    needle = 'assert(loadfile(' + json.dumps(adapter['path']) + '))().attach('
    assert text.count(needle) == 1
    assert 'startup_policy_journal_proposal/full_startup_wire_v2.lua' not in text
    return dict(schema='robotron-actual-startup-slot64-Lua-chain-v1', minimum_slot=4096,
                maximum_slot=4159, entry=entry, adapter=adapter, guard=guard)


def validate_job(job):
    expected = chain()
    assert job['startup_lua_chain'] == expected and job['lua'] == expected['entry'], 'Actual job Lua chain differs'
    count = job['capacity_shape']['actor_count']
    assert type(count) is int and count in (32, 64)
    assert job['actor_slots'] == list(range(4096, 4096 + count))
    inputs = {item['path']: item for item in job['inputs']}
    for key in ('entry', 'adapter', 'guard'):
        item = expected[key]
        assert inputs.get(item['path']) == item, 'Actual Lua dependency missing from immutable job inputs'
    return expected


def bind_future_job(job):
    """Pure dict binding for a NEW preparer; never rewrite an existing job.

    The fresh original design, source-family manifests, controller/reviewer pins
    and new session IDs must be created/qualified separately by the ROOT caller.
    """
    result = copy.deepcopy(job)
    assert result['lua']['sha256'] == OLD_ENTRY_SHA
    assert not Path(result['output']).exists(), 'An original output already exists; no retry binding'
    assert result['original_attempt'] == 1 and result['no_retry'] is True
    expected = chain()
    result['lua'] = expected['entry']
    result['startup_lua_chain'] = expected
    # Historical dependencies remain retained, and are never normalized away.
    inputs = {item['path']: item for item in result['inputs']}
    for key in ('entry', 'adapter', 'guard'):
        item = expected[key]
        inputs[item['path']] = item
    result['inputs'] = list(inputs.values())
    role = 'A32' if result['capacity_shape']['actor_count'] == 32 else 'B64'
    runtime = pin(HERE / role / 'run_evaluator_count_active600_v2.py')
    result['runtime'] = runtime
    result['inputs'].append(runtime)
    validate_job(result)
    return result
