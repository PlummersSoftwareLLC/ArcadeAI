"""One owned pipe gate; then literal unchanged role wrapper, never a fallback."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('job','job-sha256','owner','owner-sha256','slot','read-fd','ready-fd','round'):p.add_argument('--'+key,required=True)
    a=p.parse_args();job_path=Path(a.job)
    # Only the fixed adjacent runner supplies verification helpers. Validate its
    # exact bytes against the already Root-selected immutable job before import.
    raw=job_path.read_bytes();job=json.loads(raw)
    import hashlib
    assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    source=Path(__file__).resolve().with_name('run_owned192_usage_smoke_v1.py')
    assert str(source)==job['sources']['runner']['path']and hashlib.sha256(source.read_bytes()).hexdigest()==job['sources']['runner']['sha256']
    spec=importlib.util.spec_from_file_location('_owned_usage_gate_helpers',source);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    jp=r.pin(job_path);r.require(jp['sha256']==a.job_sha256 and r.pin(Path(__file__).resolve())==job['sources']['gate'],'Exact gate/job identity differs')
    ownpin=r.pin(Path(a.owner));r.require(ownpin['sha256']==a.owner_sha256,'Original fixture owner receipt differs');owner=r.read(ownpin)
    r.require(job['schema']==r.SCHEMA and job['unit']==r.UNIT and int(a.slot)in job['slots']and str(int(a.slot))==a.slot,'Exact own original slot required')
    r.verify_parent(owner)
    case=r.read(job['case']);env=dict(os.environ)
    r.require(env['ROBOTRON_CLIENT_SLOT']==a.slot and env['ROBOTRON_ACTOR_ROUND']==a.round and env['ROBOTRON_EVAL_MODE']=='0'
        and env['MAME_BIN']==str(r.ROOT/'tools/power_recovery/mame_with_roles.sh'),'Exact unchanged INPUT environment required')
    ready=int(a.ready_fd);gate=int(a.read_fd);os.set_inheritable(ready,False);os.set_inheritable(gate,False)
    os.write(ready,(json.dumps(dict(slot=int(a.slot),pid=os.getpid(),birth=r.birth(os.getpid()),parent_pid=os.getppid()))+'\n').encode());os.close(ready)
    r.require(os.read(gate,1)==b'G','Original gate was not released');os.close(gate)
    r.verify_parent(owner)
    for key in ('runner','gate'):r.checked(job['sources'][key])
    for name,digest in ((r.ROOT/'tools/power_recovery/mame_with_roles.sh','e7c798484c53a76c83a8203e879900dd1920919188fe5d67675d926d6f8283a4'),
                        (r.ROOT/'tools/power_recovery/mame_with_roles.py','531e70d6531fb3ab8506c1d93abd50d4c02b46f15d1abec59e5aab2c196e3d86')):
        r.require(hashlib.sha256(name.read_bytes()).hexdigest()==digest,'Original role branch source changed')
    argv=['/usr/bin/env','bash',str(r.ROOT/'tools/power_recovery/mame_with_roles.sh'),*case['actor_command'][1:],'-showusage']
    os.execve('/usr/bin/env',argv,env)


if __name__=='__main__':main()
