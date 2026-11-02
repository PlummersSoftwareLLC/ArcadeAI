"""Read back one CLOSED remaining-study03 600s CPU review; default is inert.

Derived from the actual C1 SMALL recipe, not a raw/native review. It accepts
explicit actual artifact hashes, proves true exited/0/success and archived
ownership release, joins the cached PASS report and stats every input pin.
It never launches a process, imports project modules, reads a model/binary or
replays kernel/prefix bodies. Only a NEW exclusive peer receipt may be written.

Pin ABI: top artifacts are canonical owned single-link regular0444 JSON files;
archive stream pins may carry the controller5-key or helper8-key identity.
Every provided identity key is checked. Controller/job inputs are stat-only,
including original historical0664 sources and the attested Python symlink;
full8-key job inputs retain their exact original mode/timestamps. An identity
check does not independently rehash a binary. JSON/source/stream bodies read
here are explicitly bounded. No selected evidence is chmodded or rewritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import time


RUN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
BUILDER = RUN/'deadline-score32-postterminal-review-per-leg600-builder-original01-preparation-20261027'
REVIEWER = RUN/'deadline-score32-postterminal-review-archive-abi-case02-original01-preparation-20261027/review_deadline32_leg_explicit_archive_v2.py'
REVIEWER_SHA = '90e48709bb17fa92cf795ec806e6ea8c4d5eb815c3f7b5d2e6bb5d492a8c5734'
CONTROL = RUN/'deadline-score32-postterminal-review-resource600-case03-original01-preparation-20261027/control_deadline32_review600_v1.py'
CONTROL_SHA = '848f0fb2d3ada56a49b949aacfb7b11496871722b46202aa214be8c2ed4f9124'
PYTHON = '/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python'
REDUCED = {'device', 'inode', 'mode', 'uid', 'nlink'}
FULL = REDUCED | {'bytes', 'mtime_ns', 'ctime_ns'}
MAX_JSON = 16 << 20
MAX_STREAM = 1 << 20
PROPERTIES = ['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0', 'RuntimeMaxSec=600',
              'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no']


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(path):
    s = Path(path).stat()
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def stat_pin(entry):
    require(type(entry) is dict and set(entry) == {'path', 'sha256', 'bytes', 'identity'}, 'Exact pin shape required')
    require(type(entry['path']) is str and Path(entry['path']).is_absolute(), 'Absolute pinned path required')
    require(type(entry['sha256']) is str and len(entry['sha256']) == 64
            and all(c in '0123456789abcdef' for c in entry['sha256']), 'SHA256 attestation required')
    require(type(entry['bytes']) is int and entry['bytes'] >= 0, 'Pinned size required')
    require(type(entry['identity']) is dict and set(entry['identity']) in (REDUCED, FULL), 'Known5/8-key identity ABI required')
    actual = identity(entry['path'])
    require(entry['bytes'] == actual['bytes'] and all(actual[k] == v for k, v in entry['identity'].items()),
            'Attested identity changed: ' + entry['path'])
    if Path(entry['path']).suffix == '.pt':
        require(stat.S_ISREG(Path(entry['path']).lstat().st_mode) and not Path(entry['path']).is_symlink(),
                'Original attested model must remain a regular file')
    return actual


def bounded_pin(path, *, limit, sha=None, json_artifact=False):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'Canonical artifact path required')
    before = identity(path)
    require(stat.S_ISREG(path.lstat().st_mode) and before['uid'] == os.getuid()
            and before['nlink'] == 1 and before['mode'] == '0o444', 'Owned frozen regular artifact required')
    require(before['bytes'] <= limit and (not json_artifact or path.suffix == '.json'), 'Artifact outside SMALL body scope')
    raw = path.read_bytes()
    require(identity(path) == before, 'Artifact changed while reading')
    digest = hashlib.sha256(raw).hexdigest()
    require(sha is None or sha == digest, 'Actual artifact SHA differs')
    pin = dict(path=str(path), sha256=digest, bytes=len(raw), identity=before)
    return pin, raw


def artifact(path, sha=None):
    pin, raw = bounded_pin(path, limit=MAX_JSON, sha=sha, json_artifact=True)
    return pin, json.loads(raw)


def fields(text):
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def collect(*, source_sha256, config_path, config_sha256, closure_path, closure_sha256,
            owner_path, owner_sha256, report_path, report_sha256):
    """Read-only checks; this function never writes, signals or launches."""
    source, _ = bounded_pin(Path(__file__).resolve(), limit=MAX_STREAM, sha=source_sha256)
    control, _ = bounded_pin(CONTROL, limit=MAX_STREAM, sha=CONTROL_SHA)
    reviewer, _ = bounded_pin(REVIEWER, limit=MAX_STREAM, sha=REVIEWER_SHA)
    config_pin, cfg = artifact(config_path, config_sha256)
    closure_pin, closure = artifact(closure_path, closure_sha256)
    owner_pin, owner = artifact(owner_path, owner_sha256)
    report_pin, report = artifact(report_path, report_sha256)
    leg = report['leg']
    require(leg in ('C1', 'R2', 'C2'), 'Only remaining original study03 legs supported')
    directory = BUILDER/(leg + '-review-envelope-original01')
    execution = directory/'execution-original01'
    require(Path(config_path) == directory/'controller-config.json'
            and Path(closure_path) == execution/'root-original-result-and-owned-release.json'
            and Path(owner_path) == execution/'root-original-identity.json'
            and Path(report_path) == directory/'independent-review.json', 'Exact existing per-leg artifact paths required')
    unit = 'robotron-deadline32-score60min-' + leg.lower() + '-original03-postterminal-review-original01-20261027.service'
    require(closure['original'] == owner and owner['unit'] == cfg['unit'] == unit
            and owner['timer'] == unit[:-8] + '.timer' and owner['observed_live'] is True,
            'Exact original observed ownership required')
    require(type(owner['pid']) is type(owner['starttime_ticks']) is int
            and owner['pid'] > 0 and owner['starttime_ticks'] > 0, 'Positive original PID/birth required')
    for key in ('invocation_id', 'timer_invocation_id'):
        require(type(owner[key]) is str and len(owner[key]) == 32
                and all(c in '0123456789abcdef' for c in owner[key]), 'Exact invocation ID required')
    require(type(closure['original_exec_code']) is type(closure['original_exit']) is int
            and closure['original_exec_code'] == 1 and closure['original_exit'] == 0
            and closure['original_result'] == 'success', 'Only true exited/0/success is accepted')
    require(all(closure[k] is True for k in ('all_six_original_archive_commands_succeeded',
            'original_archived_before_release', 'unit_released', 'lifecycle_complete', 'audit_success'))
            and closure['payload_retried'] is False and closure['error'] is None, 'Complete original archive/release required')
    require(cfg['properties'] == PROPERTIES and type(cfg['observation_s']) is int
            and cfg['observation_s'] == 660 and cfg['output'] == str(execution), 'Exact600s resource contract required')
    job_pin, job = artifact(directory/'review-job.json')
    argv = [PYTHON, '-Xgil=0', '-I', '-B', str(REVIEWER), '--execute', '--job', job_pin['path'],
            '--job-sha256', job_pin['sha256'], '--source-sha256', REVIEWER_SHA]
    require(cfg['argv'] == argv and job['output'] == str(directory/'independent-review.json'), 'Exact review argv/output required')
    checked_streams = {}

    def stream(entry):
        actual = stat_pin(entry)
        require(Path(entry['path']).parent == execution and actual['bytes'] <= MAX_STREAM,
                'Only bounded original-scope archive streams may be read')
        pin, raw = bounded_pin(entry['path'], limit=MAX_STREAM, sha=entry['sha256'])
        require(pin['bytes'] == entry['bytes'], 'Archive stream size differs')
        checked_streams[entry['path']] = pin
        return raw.decode()

    def command(row, argv):
        require(row['argv'] == argv and type(row['exit']) is int and row['exit'] == 0
                and row['timed_out'] is False and row['error'] is None, 'Original descriptor outcome differs')
        text = stream(row['stdout'])
        require(stream(row['stderr']) == '', 'Archive command stderr is not empty')
        return text

    expected = []
    for name, invocation in ((owner['unit'], owner['invocation_id']), (owner['timer'], owner['timer_invocation_id'])):
        expected.extend([['systemctl', '--user', 'show', name], ['systemctl', '--user', 'cat', name],
                         ['journalctl', '--user', '--no-pager', '-o', 'short-iso', '_SYSTEMD_INVOCATION_ID=' + invocation]])
    archives = closure['full_original_archives']
    require(len(archives) == 6, 'All six original descriptors required')
    texts = [command(row, args) for row, args in zip(archives, expected)]
    terminal, timer = fields(texts[0]), fields(texts[3])
    wanted = dict(Id=unit, InvocationID=owner['invocation_id'], MainPID='0', ExecMainPID=str(owner['pid']),
        ExecMainCode='1', ExecMainStatus='0', CPUQuotaPerSecUSec='2s', MemoryMax=str(4 << 30),
        MemorySwapMax='0', RuntimeMaxUSec='10min', TasksMax='128', TimeoutStopUSec='5s',
        SendSIGKILL='no', Restart='no', NRestarts='0', Result='success')
    require(all(terminal.get(k) == v for k, v in wanted.items()), 'Actual original terminal/resources differ')
    require(timer['Id'] == owner['timer'] and timer['InvocationID'] == owner['timer_invocation_id']
            and timer['Unit'] == unit and timer['LoadState'] == 'loaded', 'Original timer identity differs')
    lines = [s for s in texts[1].splitlines() if s.startswith('ExecStart=') and s != 'ExecStart=']
    wrapper = ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
               'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR=' + str(execution/'tmp')]
    require(len(lines) == 1 and shlex.split(lines[0].split('=', 1)[1]) == wrapper + argv,
            'Actual service argv/environment differs')
    live_pin, live_command = artifact(execution/'original-first-observed-show-command.json')
    live = fields(command(live_command, expected[0]))
    require(live['Id'] == unit and live['MainPID'] == str(owner['pid'])
            and live['InvocationID'] == owner['invocation_id']
            and all(live.get(k) == v for k, v in wanted.items() if k not in ('MainPID', 'ExecMainCode')),
            'Original live full-show identity/resources differ')
    cgroup = '/user.slice/user-1001.slice/user@1001.service/app.slice/' + unit
    require(live['ControlGroup'] == cgroup, 'Exact original cgroup required')
    proc = Path('/proc', str(owner['pid']), 'stat')
    birth_absent = not proc.exists() or int(proc.read_text().rsplit(')', 1)[1].split()[19]) != owner['starttime_ticks']
    require(birth_absent and not Path('/sys/fs/cgroup' + cgroup).exists(), 'Original process birth/cgroup remains')
    released = closure['owned_release']
    require(len(released) == 2 and {v['unit'] for v in released} == {unit, owner['timer']}, 'Both exact owned releases required')
    final_units = []
    for row in released:
        require(row['confirmed_absent'] is True and row['reset_failed'] is None, 'Unknown original owned release')
        for key in ('before', 'stop', 'after_stop', 'final'):
            require(row[key] is not None, 'Missing actual release descriptor')
            command(row[key], ['systemctl', '--user', 'stop' if key == 'stop' else 'show', row['unit']])
        final = fields(stream(row['final']['stdout']))
        require(final['Id'] == row['unit'] and final['LoadState'] == 'not-found'
                and final.get('MainPID', '0') == '0'
                and not Path('/run/user/1001/systemd/transient', row['unit']).exists(), 'Original unit not positively absent')
        final_units.append(dict(unit=row['unit'], fields={k: final[k] for k in ('Id', 'LoadState', 'ActiveState', 'SubState')}))
    require(len(cfg['pins']) == len({p['path'] for p in cfg['pins']})
            and len(job['inputs']) == len({p['path'] for p in job['inputs']}), 'Duplicate pin paths')
    for entry in cfg['pins']:
        require(set(entry['identity']) == REDUCED, 'Controller requires its reduced identity ABI')
        stat_pin(entry)
    for entry in job['inputs']:
        require(set(entry['identity']) == FULL, 'Original review inputs require full identity ABI')
        stat_pin(entry)
    config_pins = {p['path']: p for p in cfg['pins']}
    for entry in job['inputs']:
        reduced = dict(entry, identity={k: entry['identity'][k] for k in REDUCED})
        require(config_pins.get(entry['path']) == reduced, 'Full/reduced attestation join differs')
    require(config_pins[job_pin['path']]['sha256'] == job_pin['sha256'], 'Executed review job differs')
    require(report['schema'] == 'robotron-deadline32-original-leg-independent-review-v1'
            and report['status'] == 'PASS' and type(report['actual_native_exit']) is int
            and report['actual_native_exit'] == 0 and report['original_job'] == job['native_job']
            and report['native_result'] == job['native_result'], 'Cached PASS report/native join differs')
    require(report['deadline_metric_independently_qualified'] is True
            and report['complete_game_quality_qualified'] is report['improvement_qualified'] is False
            and report['positive_owned_native_observer_children_threads_and_lease_closure'] is True
            and report['actual_actor_exit_statuses_retained'] is True, 'Cached report scope differs')
    stat_pin(job['native_job'])
    native_pin, native = artifact(job['native_job']['path'], job['native_job']['sha256'])
    require(native_pin == job['native_job'] and native['leg'] == leg
            and report['source_family'] == native['source_family_manifest'], 'Original native/source family differs')
    # This is the CLOSED result JSON, not kernel/sample/model bodies. No hash is
    # recomputed: retain its existing full attestation and validate technical joins.
    stat_pin(job['native_result'])
    require(Path(job['native_result']['path']) == Path(native['output'])/'result.json'
            and job['native_result']['bytes'] <= MAX_JSON, 'Original native result metadata scope differs')
    result = json.loads(Path(job['native_result']['path']).read_text())
    stat_pin(job['native_result'])
    require(result['original_job'] == job['native_job'] and result['complete'] is True
            and result['errors'] == [] and result['original_lease_released'] is True, 'Original sealed native result differs')
    seal = result['deadline_score_seal']
    stat_pin(seal)
    require(Path(seal['path']) == Path(native['output'])/'original-deadline-score-seal.json', 'Original score seal path differs')
    require(len(report['all32_original_prefixes']) == 32, 'Cached all32 prefix proof missing')
    cutoff = report['score_cutoff']
    require(cutoff['n_scored'] == 32 and cutoff['n_completed'] + cutoff['n_censored'] == 32
            and all(cutoff[k] is True for k in ('all32_first_start_identities_joined', 'no_postdeadline_score_credit',
                'full_integer_score_carry_joined', 'common_anchor_exposure_retained', 'pending_games_not_discarded')),
            'Cached fixed32 score proof differs')
    replay = report['main_health']['replay']
    require(replay['all197_held_inputs_final_independently_hashed'] is True
            and set(replay['API_count_histogram']) == {'192'}, 'Cached main protection proof differs')
    require(int(live_command['unix_s'] * 1e9) <= report_pin['identity']['mtime_ns'] <= closure_pin['identity']['mtime_ns'],
            'Cached report is outside its original observed review scope')
    return dict(schema='robotron-deadline32-remaining-leg-successful600-review-independent-small-scope-readback-v1',
        status='PASS_SCOPE_AND_CACHED_REPORT_READBACK', leg=leg, actual_exit=0,
        readback_source=source, selected_review_controller=control, selected_reviewer=reviewer,
        actual_controller_config=config_pin, actual_review_job=job_pin, actual_owner=owner_pin,
        actual_closure=closure_pin, actual_live_fullshow=live_pin, actual_PASS_report=report_pin,
        all6_original_descriptors_verified=True, actual_resources=wanted, exact_argv=argv,
        exact_environment_wrapper=wrapper, original_birth_absent=True, original_units_absent=final_units,
        original_ControlGroup=cgroup, original_cgroup_absent=True,
        controller_reduced_pins_checked=len(cfg['pins']), full_input_stat_identities_checked=len(job['inputs']),
        original_native_job=job['native_job'], original_native_result=job['native_result'],
        original_native_owner=job['native_owner'], original_native_closure=job['native_closure'],
        exact_CPU_guard=job['source_family_guard_closeout'], actual_native_score_seal=seal,
        cached_report_summary=dict(prefixes32=32, kernel_epochs=len(report['main_health']['kernel_epochs']),
            deep_samples=replay['deep_samples'], main_only192=True, held_inputs197_finalhashed=True,
            n_scored=cutoff['n_scored'], n_completed=cutoff['n_completed'], n_censored=cutoff['n_censored'],
            mean_score=cutoff['mean_score']), archive_streams_hashed=len(checked_streams),
        input_pin_sweep_stat_only_and_model_binary_bodies_not_read=True,
        selected_bounded_JSON_and_source_bytes_read=True, native_result_JSON_metadata_read=True,
        score_seal_body_read=False, no_raw_kernel_prefix_or_model_body_replay=True,
        no_tests_or_review_reexecution=True, no_controls_or_selected_source_changes=True,
        ROOT_final_qualification_remains_ROOT_owned=True, observed_unix_s=time.time())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--readback', action='store_true')
    p.add_argument('--check-only', action='store_true')
    p.add_argument('--source-sha256')
    for name in ('config', 'closure', 'owner', 'report'):
        p.add_argument('--' + name)
        p.add_argument('--' + name + '-sha256')
    p.add_argument('--output')
    a = p.parse_args()
    if not a.readback:
        print('PLAN_ONLY: no artifact reads, writes, process actions or review execution')
        return 0
    require(a.source_sha256 and all(getattr(a, k) and getattr(a, k + '_sha256') for k in ('config', 'closure', 'owner', 'report')),
            'Explicit actual closed artifacts and hashes required')
    require(a.check_only or a.output, 'Explicit exclusive peer output required')
    value = collect(source_sha256=a.source_sha256,
        **{k + '_path': getattr(a, k) for k in ('config', 'closure', 'owner', 'report')},
        **{k + '_sha256': getattr(a, k + '_sha256') for k in ('config', 'closure', 'owner', 'report')})
    if a.check_only:
        print(json.dumps(dict(status=value['status'], leg=value['leg'], receipt_written=False,
            actual_PASS_report=value['actual_PASS_report'], actual_closure=value['actual_closure'])))
        return 0
    output = Path(a.output)
    require(output.is_absolute() and output.parent.resolve() == output.parent
            and output.parent == Path(a.config).parent and not output.exists()
            and output.name == 'independent-successful600-review-SMALL-scope-readback-v1.json',
            'New exact per-leg exclusive peer output required')
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        require(stream.write(raw) == len(raw), 'Peer receipt short write')
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o444)
    result, _ = bounded_pin(output, limit=MAX_JSON, json_artifact=True)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
