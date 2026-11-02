"""Correct an UNLAUNCHED controller PIN shape; preserve original artifacts."""
import hashlib
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
PREP = HERE / 'candidate-CPU-preparation-original01'
IDENTITY_KEYS = ('device', 'inode', 'mode', 'uid', 'nlink')


def pin(path):
    path = path.resolve(); raw = path.read_bytes(); s = path.stat()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
        identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                      ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink))


def put(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o444)
    return pin(path)


def main():
    original_pin = pin(PREP / 'prepared-candidate-CPU-NOT-LAUNCHED.json')
    assert original_pin['sha256'] == '3b6d50de8c8448b9758a624bbbbca5e0be2c8acde71dc0f24bcd5fd0f0eb98cd'
    manifest = json.loads(Path(original_pin['path']).read_text())
    config_pin = pin(Path(manifest['controller_config']['path']))
    assert config_pin == manifest['controller_config']
    config = json.loads(Path(config_pin['path']).read_text())
    assert not Path(config['output']).exists()
    job = json.loads(Path(manifest['job']['path']).read_text())
    assert not Path(job['output_directory']).exists()
    for value in config['pins']:
        s = Path(value['path']).stat()
        observed = dict(device=s.st_dev, inode=s.st_ino, mode=oct(stat.S_IMODE(s.st_mode)),
                        uid=s.st_uid, nlink=s.st_nlink)
        assert observed == {key: value['identity'][key] for key in IDENTITY_KEYS}
        # Lifecycle controller pin() intentionally omits times and duplicate size.
        value['identity'] = observed
    revised = put(PREP / 'candidate-CPU-controller-config-revision02-UNLAUNCHED.json', config)
    manifest['controller_config'] = revised
    manifest['unlaunched_revision01_preserved'] = original_pin
    manifest['revision02_pin_shape_only_source_job_and_model_unchanged'] = True
    manifest['pin_shape_correction_source'] = pin(Path(__file__))
    print(json.dumps(put(PREP / 'prepared-candidate-CPU-revision02-NOT-LAUNCHED.json', manifest)), flush=True)


if __name__ == '__main__':
    main()
