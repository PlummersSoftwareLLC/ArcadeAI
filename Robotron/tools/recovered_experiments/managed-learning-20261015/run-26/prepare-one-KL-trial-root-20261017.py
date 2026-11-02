"""Prepare concrete immutable trial jobs after root CPU guards and source review.

Read-only runtime inspection and log-file creation only. Does not arm or execute.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time

REPO = Path('/home/dave/source/repos/ArcadeAI')
GAME = REPO / 'Robotron'
RUN = GAME / 'logs/managed-learning-20261015/run-26'
DRAFT = RUN / 'preKL-live-activation-job-root-preparation-20261017'
SRC = GAME / 'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/live_one_trial_controller_proposal'
OUT = RUN / 'rawKL-trial01-final-root-preparation-20261017'
ADAPTER_SHA = '7d0aa20b5ef4fc1d6c889718ee688387cd684cf702cced503714435132b949d6'

def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)

def pin(path):
    path = Path(path)
    with path.open('rb') as stream:
        before = identity(os.fstat(stream.fileno()))
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        assert before == identity(os.fstat(stream.fileno())) == identity(path.lstat()), path
    return dict(path=str(path), sha256=digest, bytes=before['bytes'], identity=before)

def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
        stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return pin(path)

def load(path, digest, name):
    assert pin(path)['sha256'] == digest
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--source-review', type=Path, required=True)
    parser.add_argument('--source-review-sha256', required=True)
    parser.add_argument('--cross-review', type=Path, required=True)
    parser.add_argument('--cross-review-sha256', required=True)
    args = parser.parse_args()
    manifest = pin(SRC / 'preparation-manifest.json')
    assert manifest['sha256'] == args.manifest_sha256
    for path in SRC.iterdir():
        if path.is_file(): assert not path.stat().st_mode & 0o222
    reviews = []
    for path, digest in [(args.source_review,args.source_review_sha256),(args.cross_review,args.cross_review_sha256)]:
        actual = pin(path); assert actual['sha256'] == digest
        reviews.append(actual)
    guard = RUN / 'optional-rawKL-one-trial-controller-guards-root-execution-reviewed2-20261017/root-result-review-and-release.json'
    guarded = json.loads(guard.read_text()); assert guarded['status'] == 'PASS' and guarded['source_pins_held'] is True
    activation = json.loads((DRAFT / 'activation-job-DRAFT.json').read_text())
    core = json.loads((DRAFT / 'trial-core-DRAFT.json').read_text())
    adapter = load(Path(activation['helper_pins']['controller']['path']), ADAPTER_SHA, '_root_final_KL_adapter')
    base = adapter.load_v4()
    for value in activation['helper_pins'].values(): base.pin(value, base.MAX_SOURCE)
    sys.path.insert(0, str(GAME / 'tools')); sys.dont_write_bytecode = True
    primitives = base.load_module(activation['helper_pins']['live_host']['path'], '_root_final_KL_primitives')
    class Host(primitives.LiveHost):
        def runtime_dropin(self): return Path(activation['original_dropin']['path'])
    host = Host(activation['trainer_unit'], activation['fleet_unit'])
    before = host.describe()
    assert before == activation['before'], 'Runtime identity/source/control changed since draft'
    host.adopt_initial(before)
    host.metric_host.configure_logs(before['bindings']['logs'])
    row = host.capture()
    plan = dict(batch_size=4096,replay_cap=8,initial_snapshot=dict(csv=row['csv']),
        exposure_identity={name:primitives.metrics.exposure_key(row['exposure'][name]) for name in ('optimizer','replay')})
    assert not primitives.metrics.api_issues(row, plan)
    assert row['client_count'] == 192
    assert all(sorted(os.sched_getaffinity(actor['pid'])) == activation['actor_masks'][str(actor['pid'])] for actor in before['bindings']['actors'])
    assert host.metric_host.mask(before['bindings']['worker']) == activation['worker_mask']
    assert host._dropin_bytes() is None
    assert base.fingerprint(Path(activation['current_completed_request']['path']),base.MAX_JSON) == activation['current_completed_request']
    banks = base.load_module(activation['helper_pins']['bank_state']['path'], '_root_final_KL_banks')
    spec = activation['bank_spec']
    live_storage = dict(scope='Live as-of immutable selected bank descriptors and ring directory only; no stopped/memory-equality claim',
        ring_directory=banks.directory_identity(spec['ring']),
        banks={name:banks.bank_state(name,Path(spec['model_dir'])/('robotron_dqn_latest_replay_'+name),spec['bank_strides'][name],spec['state_size'],spec['episode_capacity']) for name in ('hof','ephof')},
        stopped_no_writer_descriptors=None, actual_startup_mmaps=None,
        derived_before_new_KL_start='Root-owned stop, then stopped_state; startup verifies same selected banks and persistent maps')
    OUT.mkdir(mode=0o700)
    # Raw supported API NaN is retained in its own file, outside strict jobs/core.
    with (OUT/'fresh-raw-health.json').open('x') as stream:
        json.dump(dict(before=before,API=row),stream,indent=2,allow_nan=True);stream.write('\n')
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    live_pin = save(OUT/'live-storage-asof-descriptors.json',live_storage)
    prepared = dict(manifest=manifest,source_reviews=reviews,actual_CPU_guards=pin(guard),fresh_health=pin(OUT/'fresh-raw-health.json'),
        prepared_monotonic_s=time.monotonic(),scope='Read-only preparation; no source installation/signals/stop/start/arming')
    preparation_pin = save(OUT/'root-preparation-prerequisites.json',prepared)
    state = json.loads((RUN.parent/'state.json').read_text())
    proposal = state['optimization_goal']['future_kl_priority_calibration']['optional_sequential_KL_source']
    core.update(status='FINAL_PRECOMMITTED_ROOT_AUTHORIZED',activation_authorized=True,
        preparation=preparation_pin,
        execution_envelope=dict(controller_runtime_s=7200,deadline_runtime_s=6000,
            scope='Outer runtime includes old CE stop/CPU then fixed KL3600 ceiling and post-absence candidate/latestCPU/CE startup; never extends KL owner ceiling'),
        authorization_scope='One sequential policy-search trial with fixed horizons and deadlines; no automatic trial retry or relaxed confirmation')
    known = core['future_immutable_core_bindings']
    known.update(candidate5_sources=activation['candidate_sources'],
        control_and_unit_overrides=dict(control_hashes=before['bindings']['control_hashes'],unit_files=before['unit_files'],environment=before['environment'],dedicated_phase_override=activation['original_dropin']),
        fresh_before_trainer_and_all192_actor_identities=before,
        production_helpers_and_evaluation_profile=dict(helpers=activation['helper_pins'],confirmation=core['future_confirmation'],source_manifest=manifest),
        protected_checkpoint_and_metadata=dict(checkpoint=activation['protected_reference'],metadata=pin(Path(activation['protected_reference']['path']+'.json'))),
        ring_current_and_both_bank_start_proof=dict(asof=live_pin,bank_spec=spec,actual_stopped_and_startup_proofs='Derived by pinned transition before/after actual KL start'))
    core['prerequisites'].update(phase_snapshot_CPU_wrapper_source_and_guards=proposal['phase_snapshot_CPU_source'],
        protected_best_after448=activation['protected_reference'],
        quality448_original_controller_exit=pin(Path(state['active_quality_job']['original_terminal_archive']['path'])))
    # Actual newest stopped checkpoint, new owner, clocks and candidate proofs
    # remain unknown until execution. Their honest null fields stay in the core.
    core_pin = save(OUT/'trial-core-FINAL.json',core)
    activation.update(trial_core=core_pin,before=before,baseline_csv=row['csv'])
    activation['static_pins'].extend([manifest,*reviews,pin(guard),preparation_pin])
    activation_pin = save(OUT/'activation-job-FINAL.json',activation)
    read_args=argparse.Namespace(job=Path(activation_pin['path']),expected_job_sha256=activation_pin['sha256'],expected_controller_sha256=ADAPTER_SHA)
    verified, verified_pin=adapter.read_job(read_args,base)
    assert verified==activation and verified_pin==activation_pin
    insurance=base.read_json(activation['insurance_verification'])
    trial=dict(schema='robotron-one-raw-kl-trial-job-v1',
        boot_id=activation['boot_id'],trial_core=core_pin,activation_job=activation_pin,
        output_directory=str(RUN/'rawKL-trial01-controller-20261017'),
        sources=dict(controller=pin(SRC/'run_one_trial.py'),deadline=pin(SRC/'deadline_guard.py'),early_insurance=pin(SRC/'early_insurance.py'),
            adapter=activation['helper_pins']['controller'],horizon=activation['helper_pins']['horizon']),
        old_owner=insurance['root_job']['insurance']['trainer'],
        deadlines=dict(latch_s=3240,stop_intent_s=3310,owner_ceiling_s=3600),observation_budget_bytes=32<<20,
        early_insurance=dict(tag='rawkl-early-insurance-20261017-trial01',cpu_unit='robotron-rawkl-early-insurance-trial01-20261017.service',save_timeout_s=60,cpu_timeout_s=120),
        candidate_tag='rawkl-first-8M-20261017-trial01',
        return_intent=dict(phase_id='ce_after_rawkl_20261017_trial01',request_id='rawkl_trial01_return_ce_20261017',startup_tag='rawkl-ce-startup-20261017-trial01',output_directory=str(RUN/'rawKL-trial01-return-CE-20261017')))
    assert all(not Path(path).exists() for path in [trial['output_directory'],activation['output_directory'],trial['return_intent']['output_directory']])
    trial_pin=save(OUT/'one-trial-job-FINAL.json',trial)
    save(OUT/'root-FINAL-readonly-validation.json',dict(status='PASS',preparation=preparation_pin,core=core_pin,activation=activation_pin,trial=trial_pin,armed=False,executed=False))
    print(json.dumps(dict(status='FINAL_PREPARED_NOT_ARMED',trial=trial_pin,core=core_pin,activation=activation_pin)))

if __name__=='__main__': main()
