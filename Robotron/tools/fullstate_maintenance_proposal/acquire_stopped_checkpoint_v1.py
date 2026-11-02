"""Copy the actual stopped checkpoint independently; no restore or startup."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--header', type=Path)
    p.add_argument('--header-sha256')
    p.add_argument('--stop-outcome', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if not a.execute:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    assert hashlib.sha256(a.header.read_bytes()).hexdigest() == a.header_sha256
    spec = importlib.util.spec_from_file_location('_stopped_checkpoint_header', a.header)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    outcome_pin = h.metadata(a.stop_outcome)[0]
    outcome = h.read(outcome_pin)
    assert outcome['status'] == 'ORIGINAL_CONTINUOUS_OWNER_STOPPED_STRICT_CPU_AND_BACKUP_REQUIRED'
    assert outcome['owned_hold_release_errors'] == []
    authority_pin = outcome['actual_stopped_authority']
    authority = h.read(authority_pin)
    assert authority['actual_exit'] == 0 and authority['original_scope_released'] is True
    selection = h.read(outcome['actual_current_selection'])
    verifier = h.load('verifier')
    for owner in (selection['owner'], selection['fleet']):
        verifier.old_owner_absent(owner)
        assert subprocess.check_output(['systemctl', '--user', 'show', owner['unit'], '-p', 'MainPID', '--value'], text=True).strip() == '0'
    assert a.output.is_absolute() and not a.output.exists()
    a.output.mkdir(mode=0o700)
    source = verifier.pin(h.ROOT / 'models_dqn/robotron_dqn_latest.pt')
    target = a.output / 'independent-stopped-verification-copy.pt'
    digest = hashlib.sha256()
    with os.fdopen(os.open(source['path'], os.O_RDONLY | os.O_NOFOLLOW), 'rb') as src:
        assert verifier.identity(os.fstat(src.fileno())) == source['identity']
        with target.open('xb') as dst:
            for chunk in iter(lambda: src.read(8 << 20), b''):
                dst.write(chunk)
                digest.update(chunk)
            dst.flush()
            os.fchmod(dst.fileno(), 0o444)
            os.fsync(dst.fileno())
        assert verifier.identity(os.fstat(src.fileno())) == source['identity']
    fd = os.open(a.output, os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)
    copied = verifier.pin(target)
    assert source['sha256'] == digest.hexdigest() == copied['sha256']
    assert source['bytes'] == copied['bytes']
    assert (source['identity']['device'], source['identity']['inode']) != (copied['identity']['device'], copied['identity']['inode'])
    assert verifier.pin(source['path']) == source
    result = h.put(a.output / 'acquisition.json', dict(
        schema='robotron-root-stopped-checkpoint-and-independent-copy-v1', stopped_authority=authority_pin,
        source_checkpoint=source, verification_copy=copied, original_stop_outcome=outcome_pin,
        stream_hash_and_independent_readback_equal=True, source=h.metadata(Path(__file__).resolve())[0],
        restore_or_service_action_performed=False))
    print(json.dumps({k: result[k] for k in ('path', 'sha256', 'bytes')}))


if __name__ == '__main__':
    main()
