"""Default inert; Root-only read-only owner/API metadata capture, no child scan.

Uses the exact frozen health consumer's stdlib owner record and GET functions.
No signals, service changes, actor launch, model/device/library or quality work.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

BASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-original01/continuous_static192_health_v1.py')
SHA = '6fcff86103d409a3646f523a6adf6a95cc9eabd3b0090826493aaa99a7b9fbcc'


def publish(path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    s = path.stat()
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=dict(
        device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
        mode=oct(s.st_mode&0o777),uid=s.st_uid,nlink=s.st_nlink))


def capture(args):
    own = Path(__file__).resolve()
    assert hashlib.sha256(own.read_bytes()).hexdigest() == args.expected_source_sha256
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == SHA
    root = Path(args.output)
    assert root.is_absolute() and root.resolve(strict=False) == root and not root.exists()
    root.mkdir(mode=0o700)
    spec = importlib.util.spec_from_file_location('_exact_static192_metadata_base',BASE)
    base = importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    began = time.time();reader = base.linux()
    owners = {role:base.unit_record(unit,reader) for role,unit in
              [('trainer','robotron-trainer.service'),('fleet','robotron-mame.service')]}
    api = base.get('/api/now')
    op = publish(root/'actual-owner-records.json',owners)
    raw = publish(root/'actual-baseline-API.raw.json',api['raw_wire'].encode())
    bracket = publish(root/'actual-baseline-API-capture.json',api)
    result = publish(root/'Root-owner-and-API-metadata-capture.json',dict(
        schema='robotron-root-static192-owner-and-API-metadata-capture-v1',owners=op,baseline_API=raw,
        baseline_API_capture=bracket,began_unix_s=began,ended_unix_s=time.time(),
        no_child_census_or_192_runtime_or_engineering_qualification=True,
        no_signals_or_controls_or_model_GPU_or_quality_actions=True))
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',action='store_true');parser.add_argument('--output')
    parser.add_argument('--expected-source-sha256');args=parser.parse_args()
    if args.capture:capture(args)
    else:print('PLAN_ONLY_NO_READS_IMPORTS_OUTPUTS_PROBES_OR_ACTIONS')
