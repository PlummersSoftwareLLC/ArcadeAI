"""Explicit prefleet proc/source/API audit for collector trial; default/import inert."""
import datetime
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request

import startup_common as common

def validate_prefleet(api, saved, cpu, pid, contract):
    """Pure finite-schema health checks; does not read the runtime."""
    graphs = api['host_pipeline']['inference_graphs']
    native = api['host_pipeline']['native_batch_update']
    bank = api['bank_persistence']
    numeric = graphs['numeric_policy']
    common.outcome_checks(api['host_pipeline']['learning_exposure'], pid)
    return {
        'prefleet_clients0_training_enabled_not_measurement': api['client_count'] == 0 and api['training_enabled'] is True and api['measurement_active'] is False,
        'prefleet_saved_fleet_learner_measurement_clocks_exact': api['frame_count'] == saved['frame_count'] and api['learner_frame_count'] == saved['learner_frame_count'] and api['measurement_frames'] == saved['measurement_frame_count'],
        'exactly_one4096_postload_logical_attempt': api['training_steps'] == saved['training_steps'] + 1 and api['optimized_samples'] == saved['optimized_samples'] + 4096,
        'ring6M_and_both_CPU_bank_generation_counts_exact': api['memory_buffer_size'] == 6000000 and set(cpu['banks']) == {'hof', 'ephof'} and all(row['match'] for row in cpu['banks'].values()),
        'bank_restore_clean_revisions1_without_new_write': bank['capture_attempts'] == bank['writes'] == bank['write_failures'] == 0 and bank['last_error'] is None and bank['writer_active'] is False and bank['revision'] == bank['saved_revision'] == {'hof': 1, 'ephof': 1} and not any(bank['dirty'].values()),
        'stream_bank_output_preserved_no_phase_error': bank['output']['available'] and bank['output']['stream_output_enabled'] and bank['output']['backend'] == 'stream' and bank['output']['active'] is None and all(row['errors'] == 0 for row in bank['output']['totals'].values()),
        'exact128_shapes_640_validation_returns_postload1': graphs['requested'] and graphs['ready'] and graphs['capture_count'] == 128 and graphs['validation_replay_count'] == graphs['validation_cpu_returns'] == 640 and graphs['postload_validations'] == 1 and graphs['covered_shapes'] == list(range(1,129)),
        'graph_private_pools_no_padding_or_runtime_capture_fallback_fatal': graphs['private_pool_per_shape'] and not graphs['padding'] and graphs['runtime_capture_count'] == graphs['fallback_count'] == 0 and graphs['fatal_error'] is None,
        'graph_owned_memory_within_unchanged16GiB_budget': 0 < graphs['graph_owned_reserved_bytes'] <= graphs['budget_bytes'] == int(contract['environment']['DQN_EXACT_GRAPH_BUDGET_BYTES']),
        'actor_graph_FP32_TF32_no_autocast_dynamic_no_internal_graphs': numeric['weights_inputs'] == 'float32' and numeric['grad_context'] == 'no_grad' and numeric['autocast'] is False and numeric['dynamic_compiled'] is True and numeric['compile_internal_cudagraphs'] is False and numeric['matmul_precision'] == 'high' and numeric['cuda_matmul_allow_tf32'] and numeric['cudnn_allow_tf32'],
        'native_available_one_success_no_error_or_fallback': native['enabled'] and native['available'] and native['completed_count'] == native['success_count'] == 1 and native['fallback_count'] == native['error_count'] == 0,
        'known_first_optimizer_outcome_imported_replay_excluded_new_epoch': True,
        'API_read_errors0': not api['pipeline_read_error'] and not api['bank_persistence_read_error'],
        'finite_objective_loss_no_gradient_assumption': type(api['loss']) in (int, float) and math.isfinite(api['loss']),
        'computed_LR_epsilon_expert_preserved': api['lr'] == 2.5e-5 and api['epsilon'] == .1 and abs(api['expert_ratio'] - .1) < 1e-12,
    }

def tee_observation(run):
    found = []
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal():
            continue
        try:
            cmd = path.joinpath('cmdline').read_bytes().replace(b'\0', b' ').decode()
            if cmd.startswith('tee ') and str(run / 'console.log') in cmd:
                fds = {fd.name: os.readlink(fd) for fd in path.joinpath('fd').iterdir()}
                found.append(dict(pid=int(path.name), cmdline=cmd, fds=fds))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    common.require(len(found) == 1 and str(run / 'console.log') in found[0]['fds'].values()
                   and '/dev/pts/2' in found[0]['fds'].values(), 'Actual console tee route differs')
    return found

def owns_API(pid):
    sockets = set()
    for fd in Path('/proc', str(pid), 'fd').iterdir():
        try:
            value = os.readlink(fd)
            if value.startswith('socket:['):
                sockets.add(value[8:-1])
        except FileNotFoundError:
            pass
    for table in ('tcp', 'tcp6'):
        for line in Path('/proc/net', table).read_text().splitlines()[1:]:
            fields = line.split()
            if fields[1].split(':')[-1] == f'{8771:04X}' and fields[3] == '0A' and fields[9] in sockets:
                return True
    return False

def execute(args):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat(); tick = time.monotonic()
    contract = common.baseline()
    run, prior, game, _ = common.run_paths(args, contract)
    result_path = run / 'startup-readonly-independent-audit.json'
    common.require(not result_path.exists(), 'Existing prefleet audit; refuse overwrite/retry')
    root = common.doc(run / 'startup-root-record.json')
    common.require(root['pid'] == args.trainer_pid, 'Root trainer identity differs')
    proc_before = common.process(args.trainer_pid)
    p = Path('/proc', str(args.trainer_pid))
    env = dict(item.split('=', 1) for item in p.joinpath('environ').read_bytes().decode().split('\0') if '=' in item)
    prior_observation = common.doc(prior / 'startup-independent-process-source-observation.json')
    selected, changes = common.check_environment(env, common.doc(run / 'resume-environment.json'),
        prior_observation['environment'], contract, run, args.expected_wait)
    common.require(prior_observation['PASS'] and prior_observation['source_hashes'] == contract['source20']
                   and prior_observation['private12_hashes'] == contract['private12'], 'Prior source identity differs')
    source, private = common.check_sources(contract)
    cmdline = p.joinpath('cmdline').read_bytes().replace(b'\0', b' ').decode()
    common.require('-Xgil=0' in cmdline, 'Free-threaded trainer command differs')
    tee = tee_observation(run)
    manifest = common.doc(run / 'final-resume-checkpoint.json', args.resume_manifest_sha256)
    common.require(not Path('/proc', str(manifest['stopped_trainer_pid'])).exists(), 'Previous trainer still exists')
    cpu_path = run / 'startup-independent-checkpoint-cpu.json'
    cpu = common.doc(cpu_path, args.cpu_report_sha256)
    common.require(cpu['PASS'] and cpu['trainer'] == proc_before and cpu['resume_manifest_sha256'] == args.resume_manifest_sha256
                   and cpu['anchor_sha256'] == manifest['sha256'] and cpu['metadata'] == manifest['saved_metadata']
                   and cpu['expected_wait_ms'] == args.expected_wait and cpu['run_dir'] == str(run) and cpu['prior_run'] == str(prior)
                   and cpu['source_hashes'] == source and cpu['private12_hashes'] == private
                   and cpu['CUDA_initialized'] is False and cpu['all_saved_tensors_finite_CPU'], 'CPU audit identity differs')
    metadata, previous_metadata = common.doc(run / 'metadata.json'), common.doc(prior / 'metadata.json')
    config_changes = common.check_config(metadata['config'], previous_metadata['config'], contract, args.expected_wait)
    common.require(metadata['config']['compile_full_loss'] and metadata['config']['use_torch_compile'], 'Training compile disabled')
    log = (run / 'console.log').read_bytes(); end = log.rfind(b'\n') + 1; prefix = log[:end]
    text = prefix.decode(errors='replace')
    patterns = ['torch.compile unavailable','disabling torch.compile','falling back to eager','Traceback',
                'Training error:','ExactInferenceGraphError','Batched inference request timed out',
                'Batched inference failed','Non-finite loss','Optimizer state skipped:',
                'GradScaler state skipped:', 'starting fresh', 'cold optimizer']
    errors = {word: text.count(word) for word in patterns}
    training = re.search(r'torch\.compile: training graphs warm \((\d+)s\)', text)
    allwarm = re.search(r'torch\.compile: all graphs warm in (\d+)s', text)
    bank_log_checks = {bank: re.search(r'\b' + bank.upper() + r' loaded: ' + str(row['episodes'])
        + r' episodes / ' + re.escape(f"{row['transitions']:,}") + r' transitions', text) is not None
        for bank, row in cpu['banks'].items()}
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=3) as response:
        api_raw = response.read()
    api = json.loads(api_raw)
    capture = datetime.datetime.now(datetime.timezone.utc).isoformat()
    gpu = subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],
                         capture_output=True, text=True, timeout=5)
    app_rows = [line.strip().split(',') for line in gpu.stdout.splitlines() if line.strip()]
    trainer_gpu = [row[1].strip() for row in app_rows if row[0].strip() == str(args.trainer_pid)]
    checks = validate_prefleet(api, manifest['saved_metadata'], cpu, args.trainer_pid, contract)
    checks.update(actual_CPU_anchor_metadata_Adam81_scaler_exact=cpu['optimizer_state_count'] == 81 and bool(cpu['grad_scaler_state_dict']),
                  source20_and_private12_exact_pinned_run23=source == contract['source20'] and private == contract['private12'],
                  actual_environment_only_runpath_and_collector=set(changes) <= {'ROBOTRON_RUN_DIR','DQN_INFERENCE_BATCH_WAIT_MS'},
                  metadata_config_only_collector=set(config_changes) <= {'inference_batch_wait_ms'},
                  warm_training_default_and_allgraphs_complete=bool(training and allwarm),
                  zero_logged_compile_training_transport_reset_errors=all(count == 0 for count in errors.values()),
                  exact6M_mmap_and_bank_count_load_messages='Replay buffer mmap mapped: 6,000,000 transitions' in text and all(bank_log_checks.values()),
                  API_owned_by_expected_trainer=owns_API(args.trainer_pid),
                  trainer_physical_GB300_only=gpu.returncode == 0 and trainer_gpu == [contract['expected_gpu_uuid']],
                  actual_tee_log_and_pts2_visible=True,
                  trainer_identity_stable=common.process(args.trainer_pid) == proc_before)
    observation = dict(schema='robotron-collector4096-independent-process-source-v1', PASS=all(checks.values()),
                       utc=capture, pid=args.trainer_pid, start_ticks=proc_before['start_ticks'], cmdline=cmdline,
                       environment=selected, environment_delta_vs_prior=changes, source_hashes=source,
                       private12_hashes=private, tee=tee, prior_run=str(prior), expected_wait_ms=args.expected_wait,
                       scope='Actual exec environment/proc/small sources and readonly NVML; no CUDA context or heap injection.')
    process_sha = common.publish(run / 'startup-independent-process-source-observation.json', observation)
    # Preserve the exact API bytes, with the same exclusive readonly publication contract.
    api_sha = common.publish_raw(run / 'startup-api-independent-before-fleet.json', api_raw)
    report = dict(schema='robotron-collector4096-prefleet-independent-audit-v1', PASS=all(checks.values()),
                  checks=checks, trainer_pid=args.trainer_pid, trainer_start_ticks=proc_before['start_ticks'],
                  run_dir=str(run), prior_run=str(prior), expected_wait_ms=args.expected_wait,
                  prefleet_capture_utc=capture, prefleet_API_ts=api['ts'], config_delta_vs_prior=config_changes,
                  environment_delta_vs_prior=changes, baseline_contract_sha256=common.BASELINE_SHA,
                  clock_evidence=dict(saved=manifest['saved_metadata'], prefleet={key:api[key] for key in
                    ['frame_count','learner_frame_count','measurement_frames','training_steps','optimized_samples']},
                    saved_clock_delta_vs_prior_resume_anchor=cpu['saved_clock_delta_vs_prior_resume_anchor']),
                  learning_exposure=api['host_pipeline']['learning_exposure'], graphs=api['host_pipeline']['inference_graphs'],
                  native=api['host_pipeline']['native_batch_update'], bank_output_backend=api['bank_persistence']['output']['backend'],
                  console_error_counts=errors, bank_load_message_checks=bank_log_checks,
                  compile_warm_log=dict(training_s=int(training[1]) if training else None, all_s=int(allwarm[1]) if allwarm else None,
                    console_complete_prefix_bytes=end, console_complete_prefix_sha256=common.digest(prefix),
                    policy='Pinned source/environment default selects max_autotune=False and training triton.cudagraphs=False; exact actor graph FP32/TF32 route unchanged.'),
                  NVML=dict(returncode=gpu.returncode, compute_apps=gpu.stdout),
                  evidence_sha256={'final-resume-checkpoint.json':args.resume_manifest_sha256,
                    'startup-independent-checkpoint-cpu.json':args.cpu_report_sha256,
                    'startup-independent-process-source-observation.json':process_sha,
                    'startup-api-independent-before-fleet.json':api_sha,
                    'startup-root-record.json':common.digest(common.small_raw(run/'startup-root-record.json')),
                    'resume-environment.json':common.digest(common.small_raw(run/'resume-environment.json'))},
                  audit_execution=dict(started_utc=started, finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                       elapsed_s=time.monotonic()-tick, pid=os.getpid()),
                  limits=['API LR is computed schedule telemetry, not inspection of the live optimizer. Actual saved optimizer LR/moments/scaler/target clocks are validated by the pinned CPU audit and unchanged source load contract; live heap values are not read.',
                          'One new postload attempt can be known applied or AMP-skipped; imported replay/banks are not new learner admissions. No subtraction across process/epoch counters or per-row AMP cause claims.',
                          'Prefleet only;192 actual actor/startticks/slots/current-PID log prefixes/shim/health plus prospective settled throughput require the separate observer.',
                          'Exact saved clocks and source contracts preserve resume lineage, not identical data/kernel/RNG/actor trajectories or bitwise learning equivalence.'])
    result_sha = common.publish(result_path, report)
    print(json.dumps(dict(PASS=report['PASS'], checks=len(checks), failed=[key for key,value in checks.items() if not value],
                          path=str(result_path), sha256=result_sha, cpu_sha256=args.cpu_report_sha256)))
    common.require(report['PASS'], 'Prefleet guard failed; preserve evidence and do not admit fleet')

def main():
    args = common.arguments(__doc__, observe=True)
    if args is not None:
        execute(args)

if __name__ == '__main__':
    main()
