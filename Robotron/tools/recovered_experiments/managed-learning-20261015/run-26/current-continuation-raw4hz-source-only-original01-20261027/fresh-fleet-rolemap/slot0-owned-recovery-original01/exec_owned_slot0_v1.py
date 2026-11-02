"""Inert unless explicitly executed in the one named, ROOT-admitted slot0 unit."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import sys
import types

UNIT = 'robotron-managed-run-26-continuation-raw4hz-original01-20261027-slot0-owned-recovery-original01.service'
BASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027')
HELPER = BASE / 'fresh-fleet-rolemap/slot0-preview-flag-correction-original02/exec_fresh_fleet_roles_v2.py'
HELPER_SHA = 'd922ecfac60acaafa7e1624007a7bb1b8bb9e267277a7629d14e27098b47a94d'


def require(value, message):
    if not value: raise ValueError(message)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print('PLAN_ONLY: exact owned slot0 service only; no actions'); return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', required=True)
    parser.add_argument('--job-sha256', required=True)
    parser.add_argument('--expected-source-sha256', required=True)
    args = parser.parse_args(argv)
    require(args.execute, 'Only explicit ROOT-owned execution is supported')
    require(not HELPER.is_symlink() and HELPER.stat().st_mode & 0o777 == 0o444,
            'Frozen V2 helper required')
    raw = HELPER.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == HELPER_SHA, 'Exact corrected V2 helper required')
    h = types.ModuleType('_slot0_frozen_roles'); h.__file__ = str(HELPER)
    exec(compile(raw, str(HELPER), 'exec'), h.__dict__)
    def pin(path, sha):
        path = Path(path); s = path.lstat()
        return dict(path=str(path), sha256=sha, bytes=s.st_size, identity=h.identity(s))
    source = Path(__file__).resolve(strict=True)
    own = pin(source, args.expected_source_sha256)
    require(own['identity']['mode'] == '0o444', 'Frozen slot0 bootstrap required')
    h.read_bytes(own)
    job = h.read(pin(args.job, args.job_sha256))
    require(set(job) == {'schema','unit','source','manifest','quarantine_admission'}
            and job['schema'] == 'robotron-owned-slot0-only-exec-job-v1'
            and job['unit'] == UNIT and job['source'] == own, 'Exact slot0 job required')
    admission = h.read(job['quarantine_admission'])
    require(admission['schema'] == 'robotron-root-owned-slot0-only-quarantine-admission-v1'
            and admission['manifest'] == job['manifest'] and type(admission['slot']) is int and admission['slot'] == 0
            and all(admission[k] is True for k in ('slot0_absent','supervisor_slot0_quarantined',
                'other191_unchanged','trainer_unchanged','one_owned_slot0_start_only')),
            'ROOT positive slot0 quarantine and original191 admission required')
    manifest = h.read(job['manifest']); rolemap = h.validate_manifest(manifest)
    require(manifest['helper']['path'] == str(HELPER)
            and manifest['helper']['sha256'] == HELPER_SHA
            and rolemap['slot_eval']['0'] is False and rolemap['forced_output_mode']['0'] == '2',
            'Corrected manifest and original training role required')
    h.verify_rendered_wrapper(job['manifest'], manifest)
    environment = dict(os.environ)
    command, output, probe = h.prepare_launch(manifest, rolemap, manifest['actor_args'], environment)
    require(environment.get('ROBOTRON_CLIENT_SLOT') == '0' and probe is None
            and command == [h.MAME_EXECUTABLE, *h.actor_argv()]
            and output['ROBOTRON_EVAL_MODE'] == '2'
            and output['ROBOTRON_PREVIEW_CLIENT'] == '1', 'Only literal training slot0 may exec')
    collector = types.ModuleType('_slot0_source_collector'); collector.__file__ = manifest['collector']['path']
    exec(compile(h.read_bytes(manifest['collector']), collector.__file__, 'exec'), collector.__dict__)
    def owner():
        fields = h.unit_show(UNIT); current = collector.process_record(os.getpid())
        require(fields.get('Id') == UNIT and fields.get('MainPID') == str(os.getpid())
                and fields.get('ActiveState') == 'active' and fields.get('SubState') == 'running'
                and fields.get('Type') == 'simple' and fields.get('Restart') == 'no'
                and fields.get('NRestarts') == '0'
                and re.fullmatch('[0-9a-f]{32}', fields.get('InvocationID',''))
                and os.environ.get('INVOCATION_ID') == fields['InvocationID']
                and current['cgroup'] == fields.get('ControlGroup')
                == '/user.slice/user-'+str(os.getuid())+'.slice/user@'+str(os.getuid())+'.service/app.slice/'+UNIT
                and current['uids'] == [os.getuid()]*4
                and current['command'] == ['/usr/bin/python3.12','-I','-B',str(source),*argv],
                'Exact un-restarted owned slot0 MainPID/birth/UID/invocation/cgroup/argv required')
        return {key:fields[key] for key in ('Id','MainPID','ActiveState','SubState',
                'Type','Restart','NRestarts','InvocationID','ControlGroup')}, current
    before = owner()
    require(h.read(job['manifest']) == manifest, 'Manifest changed before exec')
    h.validate_manifest(manifest); h.verify_rendered_wrapper(job['manifest'], manifest)
    require(owner() == before, 'Owned slot0 process birth or unit changed before exec')
    os.execve(command[0], command, output)
    raise AssertionError('execve returned')


if __name__ == '__main__':
    main()
