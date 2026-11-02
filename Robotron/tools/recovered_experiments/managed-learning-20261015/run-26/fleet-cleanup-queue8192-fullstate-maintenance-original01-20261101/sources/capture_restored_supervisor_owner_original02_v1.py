"""Default-inert independent service/proc identity capture for a restored fleet."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time


def service(unit):
    fields = ('Id', 'MainPID', 'InvocationID', 'ControlGroup', 'ActiveState',
              'SubState', 'Type', 'Restart', 'NRestarts')
    args = ['systemctl', '--user', 'show', unit]
    for name in fields:
        args.extend(['-p', name])
    return dict(line.split('=', 1) for line in
                subprocess.check_output(args, text=True).splitlines())


def process(pid):
    proc = Path('/proc', str(pid))
    birth = int((proc / 'stat').read_text().rsplit(')', 1)[1].split()[19])
    command = (proc / 'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
    env = dict(record.split(b'=', 1) for record in
               (proc / 'environ').read_bytes().split(b'\0') if b'=' in record)
    return dict(birth=birth, command=[os.fsdecode(arg) for arg in command],
                cgroup=(proc / 'cgroup').read_text().splitlines(),
                uid=proc.stat().st_uid,
                invocation_id=env.get(b'INVOCATION_ID', b'').decode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--header', type=Path)
    parser.add_argument('--header-sha256')
    a = parser.parse_args()
    if not a.execute:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    import hashlib
    assert hashlib.sha256(a.header.read_bytes()).hexdigest() == a.header_sha256
    spec = importlib.util.spec_from_file_location('_actualFleetOwnerHeader', a.header)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    root = a.header.parent.parent
    directory = root / 'actual-restored-Main-fleet-preparation-original02'
    job_pin = h.metadata(directory / 'fresh-continuous-supervisor-v6-job.json')[0]
    job = h.read(job_pin)
    source = next(v for v in job['inputs'] if v['sha256'] ==
                  '986777d1be4a474bab21f968a1a30bbf79b58623682bad75c23417d140e85a6a')
    assert h.metadata(source['path'])[0] == source
    unit = 'robotron-mame.service'
    before = service(unit)
    assert all(before[k] == v for k, v in dict(Id=unit, ActiveState='active',
               SubState='running', Type='exec', Restart='no', NRestarts='0').items())
    pid = int(before['MainPID'])
    assert pid > 1 and pid != 1360667
    actual = process(pid)
    assert actual['uid'] == os.getuid() == 1001
    assert actual['invocation_id'] == before['InvocationID']
    assert actual['cgroup'] == ['0::' + before['ControlGroup']]
    assert actual['command'] == ['/usr/bin/python3.12', '-I', '-B', source['path'],
        '--execute', '--config', job_pin['path'], '--config-sha256', job_pin['sha256'],
        '--source-sha256', source['sha256']]
    trainer = service('robotron-trainer.service')
    owner = job['trainer']
    assert trainer['MainPID'] == str(owner['pid'])
    assert trainer['InvocationID'] == owner['invocation_id']
    assert trainer['ControlGroup'] == owner['cgroup']
    assert trainer['ActiveState'] == 'active' and trainer['SubState'] == 'running'
    assert process(owner['pid'])['birth'] == owner['birth']
    expected = dict(pid=pid, birth=actual['birth'], unit=unit,
                    invocation_id=before['InvocationID'], cgroup=before['ControlGroup'],
                    source=source)
    assert service(unit) == before and process(pid) == actual
    owner_pin = h.put(directory / 'actual-new-fleet-supervisor-owner.json', expected)
    evidence = h.put(directory / 'independent-supervisor-owner-capture.json', dict(
        status='ACTUAL_NEW_SUPERVISOR_OBSERVED_FROM_SERVICE_AND_PROC',
        observed_unix_s=time.time(), job=job_pin, expected_owner=owner_pin,
        service_fields=before, actual_process=actual, actual_Main_service=trainer,
        fleet_status_not_used_for_identity_selection=True,
        no_process_or_service_action=True, quality_qualified=False, promotion=False))
    print(json.dumps(dict(owner={k: owner_pin[k] for k in ('path', 'sha256', 'bytes')},
                          evidence={k: evidence[k] for k in ('path', 'sha256', 'bytes')})))


if __name__ == '__main__':
    main()
