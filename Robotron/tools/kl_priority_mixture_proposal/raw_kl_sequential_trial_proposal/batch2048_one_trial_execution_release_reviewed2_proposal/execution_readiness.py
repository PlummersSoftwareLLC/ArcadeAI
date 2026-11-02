"""One explicit CE2048 execution prerequisite; metadata only, no lifecycle actions.

This module has no import-time reads. Its caller authenticates its source before
loading it. Default entrypoints retain literal PLAN without importing this file.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

SCHEMA = 'robotron-ce2048-actual-execution-prerequisites-v1'
NUMERIC_SCHEMA = 'robotron-ce-batch2048-stage-b-private-v1'
MAX_METADATA = 4 << 20
FIXED = {'numeric_manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/phaseB_readiness_proposal/batch2048_CE_private_validation_proposal/preparation-manifest.json', 'sha256': '9a1b0189a6dc5ae552bd16404d745227202a9da24c9dfd7e4654725fce8914c7', 'bytes': 4186}, 'numeric_lock': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/phaseB_readiness_proposal/batch2048_CE_private_validation_proposal/source-lock.json', 'sha256': 'd7b2365efafc637bb094895b92fccd0e7d10a5af7564535cb006006b73079639', 'bytes': 14754}, 'observed_numeric_owner': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-private-readiness-GPU-root-execution-reviewed1-20261017/root-original-parent-identity.json', 'sha256': 'fa2fd91789efec4cad2a506ec2a420e1c562229e31ca2721c9de8ce80584297f', 'bytes': 1550}, 'profile': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_profile_horizon_proposal/profile.json', 'sha256': 'e755e22ade5cb56537b08f41f412e856da09435d88e4e71e09b22aba521eac50', 'bytes': 764}, 'original_terminal_archive': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-private-readiness-owned-cleanup-root-reviewed1-20261017/original-terminal-archive.json', 'sha256': 'e24340c9801b155e5b4eddf894cb02be2a6ae6eb4964a63141482a04320d13fd', 'bytes': 27587}, 'owned_cleanup': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-private-readiness-owned-cleanup-root-reviewed1-20261017/root-owned-cleanup-and-release.json', 'sha256': 'a1772a143ad361dc30a6767dbe802105a77327724a1637ac4eb8cfceb266b95e', 'bytes': 16478}}
GUARDS = {'early': {'manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_early_phase_insurance_proposal/preparation-manifest.json', 'sha256': '58df4a4a395cd84445718a9030577dace400ed600912f2f81fc20f387fcbd22d', 'bytes': 6751}, 'script': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_early_phase_insurance_proposal/test_early_phase_insurance.py', 'sha256': '484af4bd6093063fbf3820a335e159bd56c1174f41aa37fdf420d73e9dcffd45', 'bytes': 22676}, 'future_argv': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_early_phase_insurance_proposal/future-argv.json', 'sha256': '4767a5fe2154f0ea23d59b70414c49f7f37e1ead10749fa4feca7608921b7b2a', 'bytes': 1158}, 'class_name': 'EarlyPhaseContracts', 'methods': 14, 'original_execution': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/batch2048-early-phase-insurance14-guards-root-20261017/original-guard-inline-execution.json', 'sha256': '8ab73e38b57db5e764cbfde885822d0fde5a6ca599b39e97d40898fa38f7dcfa', 'bytes': 2403}}, 'transition': {'manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_phase_lifecycle_integration_reviewed3_proposal/preparation-manifest.json', 'sha256': '1c56e97be10e9570e233c2436330d762910cb0ea4dba58d50e4b6a70d16ada16', 'bytes': 7589}, 'script': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_phase_lifecycle_integration_reviewed3_proposal/test_phase_insurance_transport.py', 'sha256': 'b2de53e582e4893cc0c23f135caa7be5899728ff64f32a0598927d4f8e500bd5', 'bytes': 11147}, 'future_argv': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_phase_lifecycle_integration_reviewed3_proposal/future-argv.json', 'sha256': '07d309dd5213a8031e22145ae720894e1eaad33cb1242e5d89938e8338d33b5e', 'bytes': 1092}, 'class_name': 'PhaseInsuranceTransportContracts', 'methods': 7, 'original_execution': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/batch2048-reviewed3-phase-transport7-guards-root-20261017/original-guard-inline-execution.json', 'sha256': '7566c3ea2182f7f920f15cb6d704b89489f212cf52834caede30684d0f05e643', 'bytes': 2461}}, 'controller': {'manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_one_trial_controller_proposal/preparation-manifest.json', 'sha256': '4328cd863d5d5c5dd99a81b8afd0691732be025a6ced3db31269699d943e134d', 'bytes': 9465}, 'script': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_one_trial_controller_proposal/test_controller_boundary.py', 'sha256': 'a6ea6399a9c01b346ea9d592a2d4221509d3e7c14d939ee37c9cfa3a54c1b8e0', 'bytes': 12530}, 'future_argv': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_one_trial_controller_proposal/future-argv.json', 'sha256': 'b3ef1f11f4cb82b4d8895fba0e0a7ffdf9d523623f2e1c4487cd2fb2f906a265', 'bytes': 1211}, 'class_name': 'ControllerBoundaryContracts', 'methods': 8, 'original_execution': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/batch2048-one-trial-controller8-guards-root-20261017/original-guard-inline-execution.json', 'sha256': '386dda2c87acb3bc9c69a5a8f4dc82b38989ff514e1d5f3b0085283615c53767', 'bytes': 2388}}}
ROLES = ('ce18', 'resume', 'restart_ce')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def triple(value):
    return {key: value[key] for key in ('path', 'sha256', 'bytes')}


def identity(value):
    return dict(device=value.st_dev,inode=value.st_ino,bytes=value.st_size,
        mtime_ns=value.st_mtime_ns,ctime_ns=value.st_ctime_ns,
        mode=oct(stat.S_IMODE(value.st_mode)),uid=value.st_uid,nlink=value.st_nlink)


def read_bytes(value, *, allow_empty=False):
    """Read one exact immutable metadata PIN; never decode or open tensor files."""
    require(set(value) in ({'path','sha256','bytes'}, {'path','sha256','bytes','identity'}),'Expected immutable metadata descriptor')
    path=Path(value['path'])
    require(path.is_absolute() and path==path.resolve(strict=True) and not path.is_symlink()
        and path.suffix not in ('.pt','.pth','.npy','.npz'), 'Noncanonical or nonmetadata proof path')
    before=path.lstat(); expected_identity=value.get('identity',identity(before))
    require(stat.S_ISREG(before.st_mode) and identity(before)==expected_identity
        and before.st_uid==os.getuid() and before.st_nlink==1
        and stat.S_IMODE(before.st_mode)==0o444
        and (0 if allow_empty else 1)<=before.st_size<=MAX_METADATA,
        'Proof is not bounded owned readonly metadata')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        require(identity(os.fstat(stream.fileno()))==expected_identity,'Proof open identity changed')
        data=stream.read(MAX_METADATA+1)
        require(identity(os.fstat(stream.fileno()))==expected_identity,'Proof changed during read')
    require(identity(path.lstat())==expected_identity and len(data)==value['bytes']
        and hashlib.sha256(data).hexdigest()==value['sha256'],'Proof bytes/identity changed')
    return data


def read_json(value):
    def invalid(token):
        raise RuntimeError('Nonfinite token in strict prerequisite metadata: '+token)
    return json.loads(read_bytes(value),parse_constant=invalid)


def bytes_match(actual, expected):
    return all(actual[key]==expected[key] for key in ('sha256','bytes'))


def validate_guard(role, proof_pin, *, read=read_json, data=read_bytes):
    fixed=GUARDS[role]
    require(triple(proof_pin)==fixed['original_execution'],'Wrong original inline execution receipt: '+role)
    proof=read(proof_pin)
    require(proof['status']=='PASS' and type(proof['exit_code']) is int and proof['exit_code']==0
        and type(proof['guard_count']) is int and proof['guard_count']==fixed['methods'],
        'Actual inline stdlib guard did not finish0: '+role)
    require(triple(proof['source_manifest'])==fixed['manifest'],'Guard source family differs: '+role)
    manifest=read(proof['source_manifest'])
    require(any(triple(item)==fixed['script'] for item in
        (manifest['files'].values() if isinstance(manifest['files'],dict) else manifest['files'])),
        'Guard script not in exact sealed source manifest')
    allowed=read(fixed['future_argv']);sealed=allowed.get('guard_argv',allowed.get('argv'))
    sealed_py312=['/usr/bin/python3.12']+sealed[1:]
    direct=['/usr/bin/python3.12','-I','-B',fixed['script']['path'],fixed['class_name'],'-v']
    require(proof['argv'] in (sealed,sealed_py312,direct),'Actual guard command selection differs: '+role)
    require(proof['finished_unix_s']>=proof['started_unix_s'] and
        proof['limits']['CUDA_VISIBLE_DEVICES']=='','Guard chronology/CUDA scope differs')
    stderr=data(proof['original_stderr']).decode('utf-8')
    data(proof['original_stdout'],allow_empty=True)
    summaries=re.findall(r'^Ran ([0-9]+) tests? in [0-9.]+s$',stderr,re.MULTILINE)
    require(summaries==[str(fixed['methods'])] and stderr.rstrip().endswith('OK'),
        'Actual unittest count/OK differs: '+role)
    return proof


def validate(value, *, read=read_json, data=read_bytes):
    """Require the complete original CE2048 probe plus source-bound inline guards.

    Actual result/launch copies may have independent readonly archive paths; their
    hashes/bytes must join the original terminal archive's exact output paths.
    """
    require(set(value)=={'schema','profile','numeric','guards'},'Unexpected actual execution prerequisite shape')
    require(value['schema']==SCHEMA and triple(value['profile'])==FIXED['profile'],
        'Exact CE2048 prerequisite/profile required')
    read(value['profile'])
    numeric=value['numeric']
    require(set(numeric)=={'preparation_manifest','source_lock','observed_owner','launch_manifest',
        'result','original_terminal_archive','owned_cleanup'},'Whole original numerical proof required')
    for name,expected in [('preparation_manifest',FIXED['numeric_manifest']),('source_lock',FIXED['numeric_lock']),
        ('observed_owner',FIXED['observed_numeric_owner']),('original_terminal_archive',FIXED['original_terminal_archive']),
        ('owned_cleanup',FIXED['owned_cleanup'])]:
        require(triple(numeric[name])==expected,'Wrong actual CE2048 source/owner proof: '+name)
        read(numeric[name])
    owner=read(numeric['observed_owner']);lock=read(numeric['source_lock'])
    require(lock['schema']==NUMERIC_SCHEMA and lock['batch_rows']==2048
        and lock['stage_b']['priority_metric']=='ce' and lock['stage_b']['samples_per_attempt']==2048
        and lock['stage_b']['attempts']==18 and lock['stage_b']['roles']==list(ROLES),
        'Old4096/KL proof cannot establish CE2048 readiness')
    launch=read(numeric['launch_manifest']);result=read(numeric['result'])
    terminal=read(numeric['original_terminal_archive']);cleanup=read(numeric['owned_cleanup'])
    require(launch['schema']==result['schema']==NUMERIC_SCHEMA
        and launch['source_lock_sha256']==result['source_lock_sha256']==FIXED['numeric_lock']['sha256']
        and launch['output']==owner['output_directory'] and launch['parent']['pid']==owner['pid']
        and str(launch['parent']['start_ticks'])==str(owner['starttime_ticks'])
        and launch['parent_sha256']=='1327fb04709e211faaf5b26587ba7c83389b8f0542105abf18d042d33c877eb4'
        and launch['worker_sha256']=='d83aa9b778925d13520c762cfe5807b0af177183aa0950a4c07b7e4ea2878b8f',
        'Actual launch/source/result provenance differs')
    require(result['status']=='OBSERVATIONS_COMPLETE' and result['readiness_pass'] is True
        and result['qualification_pass'] is False and result['owned_cleanup_complete'] is True
        and result['actual_attempts']==18 and result['batch_rows']==2048 and result['priority_metric']=='ce',
        'Complete private CE2048 readiness missing')
    variants=result['variants']
    require([item['variant'] for item in variants]==list(ROLES),'All three original roles required')
    for role,item in zip(ROLES,variants):
        require(item['status']=='OBSERVATIONS_COMPLETE' and item['readiness_pass'] is True
            and item['constructor_verified'] is True and item['phase_load_verified'] is True
            and item['qualification_pass'] is False and item['actual_attempts']==(18 if role=='ce18' else 0),
            'Original constructor/phase/update proof missing: '+role)
    require(type(result['applied_outcomes']) is int and 1<=result['applied_outcomes']<=18
        and variants[0]['applied_outcomes']==result['applied_outcomes'], 'No genuine applied CE2048 outcome')
    require(terminal['original_owner']==owner and terminal['ExecMainStatus']==0
        and terminal['ExecMainCode']==1 and terminal['Result']=='success' and terminal['NRestarts']==0
        and terminal['unit_not_released_yet'] is True,'Original numerical terminal0/archive-before-release missing')
    require([x['variant'] for x in terminal['children']]==list(ROLES)
        and all(x['actual_returncode']==0 and x['token_released'] is True for x in terminal['children']),
        'Original child terminal failure')
    for name,key in [('result','result.json'),('launch_manifest','launch-manifest.json')]:
        path=str(Path(owner['output_directory'])/key);original=terminal['pins'][path]
        require(original['path']==path and bytes_match(original,numeric[name]),
            'Readonly copy does not join archived original '+key)
    require(bytes_match(terminal['whole_result'],numeric['result']) and bytes_match(cleanup['whole_result'],numeric['result']),
        'Whole original result/copy differs')
    releases=cleanup['owned_release']
    require(cleanup['status']=='PASS_ORIGINAL_CE2048_PRIVATE_READINESS_ARCHIVED_OWNED_CLEANUP_COMPLETE'
        and triple(cleanup['original_terminal_archive'])==triple(numeric['original_terminal_archive'])
        and cleanup['original_owner']==owner and cleanup['original_parent_exit']==0
        and cleanup['original_three_child_exits']==[0,0,0]
        and cleanup['source_lock_sha256']==FIXED['numeric_lock']['sha256']
        and all(cleanup[k] is True for k in ('original_terminal_archived_before_release','owned_cleanup_complete',
            'readiness_pass','main192_and_resources_healthy'))
        and cleanup['qualification_pass'] is False and cleanup['live_batch2048_activated'] is False
        and [item['unit'] for item in releases]==[owner['unit'].replace('.service','.timer'),owner['unit']]
        and all(item['actual_stop_returncode']==0 and item['final_load_state']=='not-found' for item in releases),
        'Original numerical owned cleanup/release missing')
    require(set(value['guards'])==set(GUARDS),'Exact14/7/8 source-bound guard set required')
    for role,pin in value['guards'].items():validate_guard(role,pin,read=read,data=data)
    return dict(readiness_pass=True,qualification_pass=False,source_lock_sha256=FIXED['numeric_lock']['sha256'])


def validate_job(job, *, read=read_json, data=read_bytes):
    """Validate actual prerequisites and original final core without a hash cycle."""
    helper=job['helper_pins']['execution_readiness']
    require(Path(helper['path'])==Path(__file__).resolve(),'Actual prerequisite helper PIN path differs')
    data(helper)  # Exact immutable source bytes, authenticated before its import by each entrypoint.
    expected=job['execution_prerequisites'];value=read(expected)
    validate(value,read=read,data=data)
    core=read(job['trial_core'])
    if job.get('mode')=='return_batch4096':
        require(core['mode']=='return_batch4096' and core['phase_early_insurance_result']==job['phase_early_insurance_result']
            and core['execution_prerequisites']==expected,
            'Typed return intent differs')
        core=read(core['trial_core'])
    require(core['status']=='FINAL_PRECOMMITTED_ROOT_AUTHORIZED' and core['activation_authorized'] is True
        and core['mode']=='activate_batch2048' and core['batch_profile']==job['batch_profile']
        and core['execution_prerequisites']==expected,'Original final root core/prerequisite binding differs')
    return expected


def bound(path, expected_sha):
    path=Path(path)
    before=path.lstat()
    require(stat.S_ISREG(before.st_mode) and 0<before.st_size<=MAX_METADATA,
        'Explicit source/job is not bounded metadata')
    value=dict(path=str(path),sha256=expected_sha,bytes=before.st_size,identity=identity(before))
    read_bytes(value)
    return value


def preflight_transition(path, expected_sha, source, source_sha):
    bound(source,source_sha)
    job=read_json(bound(path,expected_sha))
    validate_job(job)
    return job


def preflight_trial(path, expected_sha, source, source_sha):
    bound(source,source_sha)
    job=read_json(bound(path,expected_sha))
    activation=read_json(job['activation_job'])
    require(job['sources']['execution_readiness']==activation['helper_pins']['execution_readiness']
        and job['trial_core']==activation['trial_core']
        and job['profile']==activation['batch_profile']
        and job['execution_prerequisites']==activation['execution_prerequisites'],
        'Actual trial/activation/core/prerequisite pins differ')
    validate_job(activation)
    return job
