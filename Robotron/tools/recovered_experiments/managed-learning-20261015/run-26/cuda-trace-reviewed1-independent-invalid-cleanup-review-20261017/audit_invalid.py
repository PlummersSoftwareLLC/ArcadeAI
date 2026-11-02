"""One-shot stdlib metadata/source/runtime audit, no tensor/framework loads."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

ROOT = Path('/home/dave/source/repos/ArcadeAI')
RUN = ROOT / 'Robotron/logs/managed-learning-20261015/run-26'
TRIAL = RUN / 'cuda-trace-parity-reviewed1-20261017'
LAUNCH = RUN / 'cuda-trace-parity-root-launch-reviewed1-20261017'
OUT = Path(__file__).resolve().parent
checks, archived = [], []


def require(value, name):
    checks.append(dict(check=name, passed=bool(value)))
    if not value:
        raise RuntimeError(name)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(name, raw):
    target = OUT / name
    with target.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    target.chmod(0o444)
    return dict(path=str(target.relative_to(ROOT)), sha256=sha(raw), bytes=len(raw))


def archive(path, name):
    raw = path.read_bytes()
    require(len(raw) <= 2*1024*1024, 'bounded_archive:' + str(path))
    record = write(name, raw)
    record['original'] = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    archived.append(record)
    return raw


def command(argv, name):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    record = dict(argv=argv, actual_exit=result.returncode, stdout=result.stdout, stderr=result.stderr)
    write(name, (json.dumps(record, indent=2)+'\n').encode())
    return record


def identity(pid):
    try:
        raw = Path('/proc/%d/stat' % pid).read_text()
    except FileNotFoundError:
        return None
    tail = raw[raw.rfind(')')+2:].split()
    return dict(pid=pid, start_ticks=tail[19], ppid=int(tail[1]), pgid=int(tail[2]),
                affinity=sorted(os.sched_getaffinity(pid)))


manifest = json.loads(archive(TRIAL/'launch-manifest.json', 'original-launch-manifest.json'))
failure = json.loads(archive(TRIAL/'failure.json', 'original-failure.json'))
child = json.loads(archive(TRIAL/'base/child-exit.json', 'original-base-child-exit.json'))
archive(TRIAL/'ownership.json', 'original-ownership.json')
precommit = json.loads(archive(LAUNCH/'execution-precommit.json', 'original-execution-precommit.json'))
console = archive(LAUNCH/'console.log', 'original-parent-console.log').decode()
archive(LAUNCH/'launch-result.json', 'original-launch-result.json')
archive(LAUNCH/'scheduling-carrier-before-trigger-proof.json', 'original-carrier-proof.json')
archive(TRIAL/'base/runtime.json', 'original-base-runtime.json')
archive(TRIAL/'base/worker.log', 'original-base-worker.log')
inputs = json.loads(archive(TRIAL/'inputs/inputs.json', 'original-inputs.json'))
require(failure == dict(status='VALIDATION_ERROR', error="FileNotFoundError(2, 'No such file or directory')"), 'actual_validation_error')
require(child['variant']=='base' and child['pid']==3448771 and child['owned_identity']['start_ticks']=='29729525'
        and child['actual_returncode']==-15 and child['token_released'] is True, 'exact_reaped_owned_base_worker')
require(26 < child['elapsed_s'] < 27, 'saved_base_elapsed26seconds')
require(manifest['parent']['pid']==3448753 and manifest['parent']['start_ticks']=='29729431'
        and manifest['worker_sha256']==precommit['source_pins']['cuda_trace_worker.py']
        and manifest['parent_sha256']==precommit['source_pins']['cuda_trace_parent.py'], 'original_launch_source_and_owner_binding')
require('base.byte_count(layout.output)' in console and 'value = path.lstat()' in console
        and '/base/cache/triton/' in console and 'tmp.pid_3448973_' in console
        and 'FileNotFoundError: [Errno 2]' in console, 'failure_localized_to_owned_active_cache_lstat')
for name, record in manifest['sources'].items():
    raw = archive(TRIAL/'private/Robotron/Scripts/dqn'/name, 'private-source-'+name)
    require(sha(raw)==record['sha256'], 'all16_actual_private_source_hashes:'+name)
    require(sha(Path(record['source']).read_bytes())==record['sha256'], 'all16_original_bound_source_hashes:'+name)
for key, record in manifest['numerical_protocol']['immutable_helpers'].items():
    raw = archive(Path(record['source']), 'pinned-helper-'+key+'.py')
    require(sha(raw)==record['sha256'], 'immutable_helper_hash:'+key)
source_lock = Path('Robotron/tools/kl_priority_mixture_proposal/cuda_trace_validation_proposal/source-lock.json')
raw = archive(ROOT/source_lock, 'original-numerical-source-lock.json')
require(sha(raw)==manifest['source_lock_sha256'], 'numerical_protocol_lock_unchanged')
triton = ROOT/'.venv-gb300/lib/python3.14t/site-packages/triton/runtime/cache.py'
archive(triton, 'installed-triton-cache.py')
phase_listing = {}
for phase in ('base','off','on'):
    folder = TRIAL/phase
    files = sorted(path.name for path in folder.iterdir() if path.is_file())
    phase_listing[phase] = files
    require(not any(path.name.startswith(('attempt-','reference-','warmup-')) for path in folder.iterdir()), 'no_saved_attempt_or_warmup_receipt:'+phase)
    require(not (folder/'phase-result.json').exists(), 'no_phase_completion:'+phase)
    if phase != 'base':
        require('worker.log' not in files and 'child-exit.json' not in files and 'runtime.json' not in files,
                'off_on_not_started:'+phase)
require(not (TRIAL/'result.json').exists() and not (TRIAL/'cleanup-failure.json').exists(), 'no_aggregate_success_or_cleanup_failure')
input_stats = {}
for name, record in inputs['files'].items():
    path = TRIAL/'inputs'/name
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_size==record['bytes'], 'input_saved_size_only:'+name)
    input_stats[name] = dict(bytes=info.st_size, mode=stat.S_IMODE(info.st_mode), recorded_sha256=record['sha256'],
                             independent_binary_hash_or_tensor_verification=False)
owned = {str(pid):identity(pid) for pid in (3448753,3448771,3448704,3448973)}
require(all(value is None for value in owned.values()), 'original_parent_worker_carrier_and_named_compiler_pids_absent')
main = identity(3032848)
require(main is not None and main['start_ticks']=='28609635' and main['affinity']==list(range(72)), 'same_main_identity_and_original72mask')
paths = {key:dict(path=manifest[key], exists=Path(manifest[key]).exists(), symlink=Path(manifest[key]).is_symlink())
         for key in ('tmpfs','cgroup')}
require(all(not value['exists'] and not value['symlink'] for value in paths.values()), 'owned_cgroup_and_tmpfs_removed')
lease_path = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
descriptor = os.open(lease_path, os.O_RDONLY | os.O_NOFOLLOW)
try:
    info = os.fstat(descriptor)
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid(), 'existing_owned_regular_lease_file')
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    lease = dict(path=str(lease_path), exclusive_nonblocking_probe_succeeded=True, opened_read_only=True,
                 file_created_or_contents_written=False)
    fcntl.flock(descriptor, fcntl.LOCK_UN)
finally:
    os.close(descriptor)
gpu = command(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,process_name,used_memory','--format=csv,noheader,nounits'], 'independent-gpu-compute-query.json')
require(gpu['actual_exit']==0, 'nvidia_smi_readonly_query_completed')
apps = [line for line in gpu['stdout'].splitlines() if line.strip()]
require(len(apps)==1 and apps[0].split(',')[0].strip()=='3032848'
        and manifest['forbidden_gpu_uuid'] in apps[0] and manifest['gpu_uuid'] not in gpu['stdout'], 'main_only_compute_gpu0_released')
unit = command(['systemctl','--user','show','robotron-snapshot-smoke-ce-trace-reviewed1-20261017.service',
    '-p','ActiveState','-p','SubState','-p','MainPID','-p','InvocationID','-p','ExecMainCode','-p','ExecMainStatus',
    '-p','Result','-p','ExecMainStartTimestamp','-p','ExecMainExitTimestamp','-p','CPUUsageNSec','-p','MemoryPeak'], 'independent-unit-current-query.json')
initial_observed = 'MainPID=0\nResult=exit-code\nExecMainStartTimestamp=Fri 2026-10-16 22:04:49 CDT\nExecMainExitTimestamp=Fri 2026-10-16 22:05:16 CDT\nExecMainCode=1\nExecMainStatus=1\nControlGroup=\nMemoryPeak=4508942336\nCPUUsageNSec=32820391000\nId=robotron-snapshot-smoke-ce-trace-reviewed1-20261017.service\nActiveState=failed\nSubState=failed\nInvocationID=24f8354b89a245f6a0528b66533c3fbc\n'
write('independent-original-unit-first-tool-observation.txt', initial_observed.encode())
result = dict(schema='robotron-cuda-reviewed1-independent-invalid-cleanup-audit-v1', status='PASS_SCOPED_INVALID_RUN_AND_CLEANUP',
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), checks=checks,
    original_service=dict(invocation='24f8354b89a245f6a0528b66533c3fbc', actual_independent_initial_terminal_observation=True,
        initial_observation_provenance='Unmodified transcription of first read-only tool result while original invocation still existed; current requery retained separately',
        exec_main_code=1, exec_main_status=1, active_state='failed', memory_peak_bytes=4508942336, cpu_usage_ns=32820391000),
    saved_base_child=child, diagnosis=dict(parent_cache_lstat_failure=True,
        exact_tmp_rename_syscall_not_traced=True, installed_triton_put_atomic_publish_source_preserved=True,
        completed_warmup_receipts=0, executed_training_attempt_receipts=0, off_on_started=False,
        scientific_parity_or_training_conclusion=False, retry_or_rescue_performed_by_auditor=False),
    phase_artifact_listing=phase_listing, owned_processes=owned, main=main, owned_paths=paths, lease=lease,
    input_metadata_only=input_stats, archived=archived,
    limits=['No tensor/batch/model contents loaded or validated; saved input digests reported, not independently rehashed.',
            'No assertion that an in-flight compile/partial warmup never executed; only no completed warmup or train-step receipt exists and source ordering puts attempts after warmup proof.',
            'Compute-app listing does not inspect ordinary display graphics allocations.',
            'Only exact recorded main identity/mask verified; no independent192actor/API/source-boundary audit claimed.',
            'No production mutation, framework import, CUDA context, broad signal or numerical retry.'])
record = write('review-receipt.json', (json.dumps(result,indent=2,allow_nan=False)+'\n').encode())
directory = os.open(OUT, os.O_RDONLY | os.O_DIRECTORY)
try: os.fsync(directory)
finally: os.close(directory)
print(json.dumps(dict(status=result['status'], checks=len(checks), receipt=record),indent=2))
