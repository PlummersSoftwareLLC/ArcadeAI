"""Pure RAM ownership/release contracts and unchanged codec guards on tmpfs."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import unittest


def load(pin, name):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--execute', action='store_true')
    p.add_argument('--job')
    p.add_argument('--job-sha256')
    p.add_argument('--source-sha256')
    args = p.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw = Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job = json.loads(raw)
    assert job['schema'] == 'robotron-RAM-live-control-contract-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    h = load(job['helpers'], '_RAM_contract_h')
    reader = load(job['reader'], '_RAM_contract_reader')
    helper = load(job['RAM_helper'], '_RAM_contract_helper')
    protocol = load(job['codec'], '_RAM_contract_codec')
    for pin in job['inputs']:
        h.checked(pin)
    def read(pin, as_json=True):
        return reader.read_pin(pin, as_json=as_json)
    output = Path(job['output'])
    output.mkdir(mode=0o700)
    fields = dict(line.split('=', 1) for line in subprocess.check_output(
        ['systemctl', '--user', 'show', job['unit']], text=True, timeout=5).splitlines() if '=' in line)
    assert fields['MainPID'] == str(os.getpid()) and fields['InvocationID'] == os.environ['INVOCATION_ID']
    parent = dict(pid=os.getpid(), birth=helper.process_birth(os.getpid()), uid=os.geteuid(),
        unit=job['unit'], invocation_id=fields['InvocationID'], cgroup=fields['ControlGroup'])
    jp = h.pin(args.job)
    negative = []
    bindings = []
    releases = []

    def make():
        nonce = secrets.token_hex(16)
        binding = helper.create(nonce, parent, jp, 'robotron-RAM-synthetic-' + nonce + '.service', h)
        bindings.append(binding)
        return binding

    def reject(name, function):
        try:
            function()
        except (ValueError, OSError, KeyError, TypeError) as error:
            negative.append(dict(case=name, error=repr(error)))
        else:
            raise AssertionError('Unsafe RAM contract accepted: ' + name)

    def fixture_release(binding, label):
        # These scope descriptors are explicit PURE fixtures, never systemd evidence.
        folder = output / label
        folder.mkdir(mode=0o700)
        unit = binding['observer_unit']
        owner = dict(pid=2147483647, starttime_ticks=1, unit=unit,
                     timer=unit.removesuffix('.service') + '.timer')
        op = h.put(folder / 'synthetic-owner.json', owner)
        cp = h.put(folder / 'synthetic-closure.json', dict(original=owner, lifecycle_complete=True,
            unit_released=True, original_archived_before_release=True,
            owned_release=[dict(unit=owner[k], confirmed_absent=True) for k in ('unit', 'timer')]))
        wj = h.put(folder / 'synthetic-worker-job.json', dict(nonce=binding['nonce'], parent=parent,
            native_job=jp, observer_unit=unit, live_control=binding, live_control_helper=job['RAM_helper']))
        archive = folder / 'archive'
        return archive, wj, op, cp

    # Run every original protocol predicate against real tmpfs files.
    binding = make()
    node, = [n for n in ast.walk(ast.parse(h.checked(job['original_contract_source']).read_text()))
             if isinstance(n, ast.ClassDef) and n.name == 'Contracts']
    original_negative = []
    namespace = dict(protocol=protocol, root=Path(binding['root']), negative=original_negative,
        copy=copy, unittest=unittest, tempfile=tempfile, Path=Path, os=os)
    exec(compile(ast.Module(body=[node], type_ignores=[]), job['original_contract_source']['path'], 'exec'), namespace)
    tests = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(namespace['Contracts']))
    assert tests.wasSuccessful() and tests.testsRun == 3 and len(original_negative) == 38
    releases.append(helper.release_unstarted(binding, parent, jp, output / 'original-codec-RAM-release', h))

    binding = make()
    helper.validate(binding, binding['nonce'], parent, jp, h)
    mutations = [
        ('schema', lambda x: x.update(schema='wrong')),
        ('extra_key', lambda x: x.update(extra=True)),
        ('missing_key', lambda x: x.pop('nonce')),
        ('nonce', lambda x: x.update(nonce='f'*32)),
        ('parent', lambda x: x['parent'].update(birth=x['parent']['birth']+1)),
        ('native_job', lambda x: x.update(native_job={})),
        ('root_escape', lambda x: x.update(root='/dev/shm')),
        ('live_escape', lambda x: x.update(live_path='/tmp/live.json')),
        ('lock_escape', lambda x: x.update(lock_path='/tmp/live.json.lock')),
        ('helper_source', lambda x: x['helper'].update(sha256='0'*64)),
        ('inode', lambda x: x['root_identity'].update(inode=0)),
        ('inode_boolean', lambda x: x['root_identity'].update(inode=True)),
        ('device', lambda x: x['root_identity'].update(device=-1)),
        ('root_UID', lambda x: x['root_identity'].update(uid=os.geteuid()+1)),
        ('root_mode', lambda x: x['root_identity'].update(mode='0o755')),
        ('root_links', lambda x: x['root_identity'].update(nlink=3)),
        ('mount', lambda x: x['mount'].update(stdout='ext4\n')),
        ('mount_exit', lambda x: x['mount'].update(exit=1)),
        ('mount_argv', lambda x: x['mount'].update(argv=[])),
        ('unit', lambda x: x.update(observer_unit='../foreign')),
        ('clock_boolean', lambda x: x.update(created_monotonic_s=True)),
        ('clock_nan', lambda x: x.update(created_monotonic_s=float('nan'))),
        ('clock_future', lambda x: x.update(created_monotonic_s=time.monotonic()+100)),
    ]
    for name, mutate in mutations:
        changed = copy.deepcopy(binding)
        mutate(changed)
        reject(name, lambda value=changed: helper.validate(value, binding['nonce'], parent, jp, h))
    reject('existing_nonce_not_adopted', lambda: helper.create(binding['nonce'], parent, jp, binding['observer_unit'], h))
    root = Path(binding['root'])
    root.chmod(0o755)
    reject('actual_root_mode', lambda: helper.check_live(binding))
    root.chmod(0o700)
    held = root.with_name(root.name + '-held-fixture')
    root.rename(held)
    root.mkdir(mode=0o700)
    reject('actual_replaced_inode', lambda: helper.check_live(binding))
    root.rmdir()
    root.symlink_to(held)
    reject('actual_root_symlink', lambda: helper.check_live(binding))
    root.unlink()
    held.rename(root)
    releases.append(helper.release_unstarted(binding, parent, jp, output / 'binding-contract-release', h))

    for temporary in (False, True):
        binding = make()
        root = Path(binding['root'])
        protocol.publish_live(root / 'live.json', dict(sequence=1, explicit_synthetic_fixture=True))
        if temporary:
            path = root / 'live.json.2147483647.tmp'
            path.write_bytes(b'{')
            path.chmod(0o664)
        archive, wj, op, cp = fixture_release(binding, 'archive-' + str(temporary))
        release = helper.archive_and_release(binding, archive, h, worker_job=wj, owner=op, closure=cp)
        checked = helper.verify_release(binding, release, archive, wj, op, cp, read, h)
        assert checked['archived_members'] == (3 if temporary else 2)
        releases.append(release)
        value = read(release)
        changed = dict(value, original_root_absent=False)
        def changed_read(pin, as_json=True):
            return changed if pin == release and as_json else read(pin, as_json)
        reject('false_release:' + str(temporary), lambda: helper.verify_release(binding, release, archive, wj, op, cp, changed_read, h))

    binding = make()
    root = Path(binding['root'])
    protocol.publish_live(root / 'live.json', dict(explicit_synthetic_fixture=True))
    unknown = root / 'unknown-preserve-me'
    unknown.write_bytes(b'original fixture bytes')
    original = h.pin(unknown)
    archive, wj, op, cp = fixture_release(binding, 'unknown-file')
    reject('unknown_member_preserved', lambda: helper.archive_and_release(binding, archive, h, worker_job=wj, owner=op, closure=cp))
    assert h.pin(unknown) == original and not archive.exists()
    unknown.unlink()
    releases.append(helper.archive_and_release(binding, archive, h, worker_job=wj, owner=op, closure=cp))

    binding = make()
    root = Path(binding['root'])
    target = output / 'symlink-target-untouched'
    target.write_bytes(b'untouched original target')
    target_pin = h.pin(target)
    link = root / 'live.json'
    link.symlink_to(target)
    archive, wj, op, cp = fixture_release(binding, 'symlink-member')
    reject('symlink_member_preserved', lambda: helper.archive_and_release(binding, archive, h, worker_job=wj, owner=op, closure=cp))
    assert link.is_symlink() and h.pin(target) == target_pin and not archive.exists()
    link.unlink()
    releases.append(helper.release_unstarted(binding, parent, jp, output / 'symlink-empty-release', h))
    assert all(not Path(b['root']).exists() and not Path(b['root']).is_symlink() for b in bindings)
    provenance = read(job['provenance'])
    for record in provenance['source_changes']:
        source = h.checked(record['prospective']).read_text()
        for before, after in reversed(record['changes']):
            assert source.count(after) == 1
            source = source.replace(after, before)
        assert source == h.checked(record['original']).read_text()
    report = h.put(output / 'report.json', dict(schema='robotron-RAM-live-control-contract-report-v1',
        original_codec_contract_tests=3, original_codec_negative_guards=original_negative,
        RAM_negative_guards=negative, exact_original_source_reversals_verified=True,
        bindings=bindings, release_receipts=releases, all_owned_RAM_fixture_roots_absent=True,
        synthetic_scope_descriptors_are_not_actual_worker_evidence=True,
        actual_RAM_worker_component_still_required=True, production_changed=False,
        scientific_case=False, quality_qualified=False))
    print(json.dumps(dict(report=report, original_guards=38, RAM_guards=len(negative))), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
