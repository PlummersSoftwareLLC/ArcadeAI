"""Read-only active v4/cap-v1 physical/recipe readiness of NEW main binding."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
NEW = HERE / 'postcapture-current-main-reconciliation-original01'


def pin(path):
    path = path.resolve(); assert path.suffix != '.pt'
    raw = path.read_bytes(); s = path.stat()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
        identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                      ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink))


def load(name, value):
    assert pin(Path(value['path'])) == value
    spec = importlib.util.spec_from_file_location(name, value['path'])
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def put(name, value):
    path = NEW / name
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o444); return pin(path)


def main():
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            assert not os.fsdecode(args[0]).endswith('.pt')
        if event == 'import': assert args[0].split('.')[0] not in ('torch', 'numpy', 'dqn')
    sys.addaudithook(audit)
    prepared_pin = pin(NEW / 'postcapture-main-reconciliation-NOT-CANONICALLY-ADOPTED.json')
    assert prepared_pin['sha256'] == 'b3a9c3012e3946da2700539046ff7abd2f925b9972f8b36403db234746ce59ea'
    prepared = json.loads(Path(prepared_pin['path']).read_text())
    binding_pin = prepared['current_binding']; assert pin(Path(binding_pin['path'])) == binding_pin
    main_binding = json.loads(Path(binding_pin['path']).read_text())
    policy = json.loads(Path(prepared['current_supervision_policy']['path']).read_text())
    capture_job = json.loads((HERE / 'job.json').read_text())
    h = load('_active_reconciled_helpers', capture_job['helpers'])
    engine = load('_actual_active_v4_engine', capture_job['engine'])
    assert capture_job['engine']['sha256'] == 'd67e696915762c66f3cb660d40f25ac11f0422e4e83b1d7fe35a8af0b1f9b72d'
    job = json.loads(h.checked(capture_job['health_job']).read_bytes()); job['binding'] = binding_pin
    modules = engine.dependencies(job, h)
    require_sources = modules['health'].verify_sources(
        Path(job['sources']['window']['path']).read_bytes(),
        Path(job['sources']['supervision']['path']).read_bytes(),
        Path(job['sources']['health']['path']).read_bytes())
    snapshot = modules['supervision'].collect(policy)
    physical = modules['health'].physical(modules['supervision'], policy, snapshot)
    modules['collector'].load('_actual_original_window', job['sources']['window']).owner_and_files(main_binding)
    baseline = json.loads(h.checked(main_binding['baseline_API']).read_bytes())
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        raw = response.read(2 << 20)
    api = json.loads(raw)
    modules['health'].healthy(api, baseline, main_binding['experiment'], time.time())
    assert api['client_count'] == 192 and api['host_pipeline']['learning_exposure']['replay']['process_id'] == main_binding['owner']['pid']
    saved = Path('/home/dave/source/repos/ArcadeAI/Robotron/models_dqn/robotron_dqn_latest.pt').stat()
    modules['health'].autosave(dict(mtime_ns=saved.st_mtime_ns, bytes=saved.st_size), time.time())
    census_pin = put('active-v4-cap-v1-actual-readonly-census.json', snapshot)
    report = dict(schema='robotron-reconciled-active-v4-cap-v1-main-readiness-proof-v1', status='PASS',
        observed_unix_s=time.time(), prepared_reconciliation=prepared_pin, current_binding=binding_pin,
        active_engine=capture_job['engine'], active_sources=job['sources'], source_proof=require_sources,
        active_physical=physical, actual_census=census_pin, held197_owner_and_files_checked=True,
        prospective_policy_held_hash_checksum=policy['held_hashes_sha256'],
        current_client_count=192, owner=main_binding['owner'], learner_frame_count=api['learner_frame_count'],
        training_steps=api['training_steps'], optimized_samples=api['optimized_samples'],
        actual_LR=api['lr'], training_enabled=api['training_enabled'], measurement_active=api['measurement_active'],
        normal_autosave_age_s=time.time()-saved.st_mtime, no_model_body_or_Torch_opened=True,
        no_native_health_stream_or_MAME_GPU_control_or_canonical_state_action=True,
        legacy196_observations_join_not_applied=True, quality_qualified=False,
        script=pin(Path(__file__)))
    print(json.dumps(put('active-v4-cap-v1-readiness-PASS.json', report)), flush=True)


if __name__ == '__main__':
    main()
