"""Explicit Root-only release of the two successfully completed original services."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
A = Path(__file__).resolve().parent
S = A.parent / 'durable-window03-D7-fixed-RCRC-study-original01'
H = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
C = G / 'tools/quality_capacity_proposal/control_quality32_review_v1.py'

def load(name, path, digest):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None

def close():
    h = load('_root_close_h', H, '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    ctl = load('_root_close_c', C, '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14')
    launch_path = A / 'ROOT-original-launch-command-results-original01.json'
    launch_pin = h.pin(launch_path)
    assert launch_pin['sha256'] == '794a8d61260c0d2a3546cdec30b987eb8fdc6f1982be2ef0bc8b67620d71c3bf'
    launch = json.loads(h.checked(launch_pin).read_bytes())
    terminal_pin = h.pin(A / 'original-R1-wrapper-terminal.json')
    terminal = json.loads(h.checked(terminal_pin).read_bytes())
    assert terminal['status'] == 'NATIVE_CLOSED_REVIEW_PENDING'
    assert terminal['actual_controller_exit'] == 0 and terminal['live_registration_errors'] == []
    closed = json.loads((S / 'R1/controller-original-result.json').read_bytes())
    assert closed['actual_exit'] == 0
    native = json.loads((S / 'R1/deadline-output-original01/result.json').read_bytes())
    assert native['status'] == 'ORIGINAL_DEADLINE32_SEALED_AND_CLOSED'
    assert native['complete'] is True and native['errors'] == []
    owners = [('wrapper', launch['wrapper_original_owner'], 426482, 14461446),
              ('display', launch['passive_display_original_owner'], 426485, 14461448)]
    # Validate BOTH original terminal owners before archiving or releasing either.
    for kind, owner, pid, ticks in owners:
        assert owner['pid'] == pid and owner['starttime_ticks'] == ticks
        assert birth(pid) is None, (kind, 'original PID not absent')
        values = ctl.show(owner['unit'])
        ctl.original_terminal(values, owner)
        assert values['ExecMainStatus'] == '0' and values['Result'] == 'success'
        assert owner['properties']['ControlGroup'].startswith('/user.slice/')
        assert values.get('ControlGroup') in (None, '', owner['properties']['ControlGroup'])
    out = A / 'ROOT-completed-R1-wrapper-display-closeout-original01'
    out.mkdir()
    records = []
    for kind, owner, pid, ticks in owners:
        directory = out / kind
        directory.mkdir()
        archives = [ctl.command(directory, 'original-service-show', ['systemctl','--user','show',owner['unit']]),
                    ctl.command(directory, 'original-service-cat', ['systemctl','--user','cat',owner['unit']]),
                    ctl.command(directory, 'original-service-journal', ['journalctl','--user','--no-pager','-o','short-iso',
                                 '_SYSTEMD_INVOCATION_ID='+owner['invocation_id']])]
        assert all(item['exit'] == 0 and not item['timed_out'] for item in archives)
        values = ctl.fields(archives[0])
        ctl.original_terminal(values, owner)
        assert values['ExecMainStatus'] == '0' and values['Result'] == 'success'
        release = ctl.release_original(directory, 'service', owner, {}, {})
        assert release['confirmed_absent'] and ctl.show(owner['unit'])['LoadState'] == 'not-found'
        cgroup = Path('/sys/fs/cgroup') / owner['properties']['ControlGroup'].lstrip('/')
        assert birth(pid) is None and not cgroup.exists()
        logs = []
        for stream in ('stdout','stderr'):
            path = A / (('wrapper' if kind == 'wrapper' else 'projector')+'-original01.'+stream+'.log')
            if path.exists():
                os.chmod(path, 0o444)
                logs.append(h.pin(path))
        records.append(dict(kind=kind, original=owner, actual_original_exit=0,
                            archives=archives, owned_release=release, original_cgroup=str(cgroup),
                            original_birth_and_cgroup_absent=True, sealed_logs=logs))
    result = h.put(out / 'ROOT-original-successful-R1-wrapper-display-owned-release.json', dict(
        schema='robotron-root-original-successful-R1-wrapper-display-owned-release-v1',
        created_unix_s=time.time(), actual_launch_receipt=launch_pin, original_wrapper_terminal=terminal_pin,
        records=records, all_six_archives_successful=True, both_original_exits_zero=True,
        both_original_units_births_and_cgroups_absent=True,
        scientific_payload_retried=False, independent_review_or_quality_qualification_performed=False,
        canonical_state_written=False))
    print(json.dumps(result), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--close', action='store_true')
    args = parser.parse_args()
    if args.close:
        close()
    else:
        print('SOURCE_ONLY: no reads, queries, archives or release actions')
