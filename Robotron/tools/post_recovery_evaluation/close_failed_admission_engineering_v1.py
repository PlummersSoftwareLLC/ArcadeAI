"""Release an original exited engineering parent after a real failed review.

Preserves parent exit1 and worker exit0. This verifies owned cleanup only and
cannot certify failed timing, gameplay, or launch authority.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def birth(pid):
    p=Path('/proc',str(pid),'stat')
    return int(p.read_text().rsplit(')',1)[1].split()[19])if p.exists()else None


def show(unit):
    r=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=10)
    assert r.returncode==0
    return dict(x.split('=',1)for x in r.stdout.splitlines()if'='in x)


def close(index,expected,kind):
    h=load('_failed_admission_close_h',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    ip=h.pin(index.resolve());assert ip['sha256']==expected
    def read(pin):return json.loads(h.checked(pin).read_bytes())
    packet=read(ip);assert packet['schema']=='robotron-reconnect-four-original-engineering-launches-v1'
    rows=[x for x in packet['records']if x['kind']==kind and x['mode']=='long'];assert len(rows)==1
    row=rows[0];out=Path(row['output']);owner=read(row['original_live_owner']);intent=read(row['intent'])
    assert owner['unit']==row['unit']==intent['unit']and intent['attempt']==1 and intent['no_retry']is True
    assert not(out/'independent-failed-review-owned-closeout.json').exists()
    for pin in intent['sources'].values():h.checked(pin)
    props=show(owner['unit']);expected_props=dict(Id=owner['unit'],MainPID='0',ExecMainPID=str(owner['pid']),
        InvocationID=owner['invocation_id'],ExecMainCode='1',ExecMainStatus='1',Result='exit-code',NRestarts='0',Restart='no',
        CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='13min',TasksMax='128',
        TimeoutStopUSec='5s',SendSIGKILL='no')
    assert all(props.get(k)==v for k,v in expected_props.items())and birth(owner['pid'])!=owner['birth']
    argv=intent['argv'];offset=argv.index('/usr/bin/env');assert' '.join(argv[offset:])+' ; ignore_errors=no ;'in props['ExecStart']
    terminal=h.put(out/'original-failed-terminal-properties.json',props)
    life_pin=h.pin(out/'runtime/main-health-scope/native-observer-lifecycle.json');life=read(life_pin)
    job=read(life['worker_job']);outcome=read(life['outcome']);worker=read(outcome['owner']);wt=read(life['terminal_properties'])
    assert job['parent']['pid']==owner['pid']and job['parent']['birth']==owner['birth']and job['parent']['invocation_id']==owner['invocation_id']
    assert wt['MainPID']=='0'and wt['ExecMainStatus']=='0'and wt['ExecMainCode']=='1'
    assert life['success']is life['all_original_processes_reaped']is life['original_scope_released']is life['launcher_birth_absent']is True
    assert birth(worker['pid'])!=worker['birth']and show(worker['unit'])['LoadState']=='not-found'
    assert not Path('/sys/fs/cgroup'+worker['cgroup']).exists()
    assert outcome['success']is outcome['all_writer_threads_stopped']is True and outcome['error']is None
    assert outcome['uncommitted_raw']==[]and outcome['queued_samples']==len(outcome['samples'])and outcome['queued_unaccepted']==len(outcome['unaccepted'])
    seal=read(outcome['durability_seal']);release=read(outcome['control_release'])
    assert seal['sample_count']==len(outcome['samples'])and seal['committed_records']==len(outcome['samples'])+len(outcome['unaccepted'])
    assert seal['all_writer_threads_stopped']is True and release['directory_absent']is True
    assert not Path(release['original']['path']).exists()
    h.checked(outcome['samples'][0]);h.checked(outcome['samples'][-1]);h.checked(outcome['final_live'])
    worker_start=int(wt['ExecMainStartTimestampMonotonic'])/1e6
    gaps=[dict(index=i,gap_s=publication['updated_monotonic_s']-(worker_start if i==0 else outcome['publications'][i-1]['updated_monotonic_s']))
        for i,publication in enumerate(outcome['publications'])
        if publication['updated_monotonic_s']-(worker_start if i==0 else outcome['publications'][i-1]['updated_monotonic_s'])>.5]
    assert len(gaps)==1 and gaps[0]['index']==0 and .5<gaps[0]['gap_s']<1
    console=(out/'console.txt').read_text();assert'ValueError: Running projection gap exceeds500ms'in console
    assert not(out/'runtime/independent-raw-review.json').exists()and not(out/'runtime/result.json').exists()
    commands=[]
    for action in ['stop','reset-failed']:
        if show(owner['unit'])['LoadState']=='not-found':break
        current=show(owner['unit']);assert current['InvocationID']==owner['invocation_id']and current['MainPID']=='0'
        r=subprocess.run(['systemctl','--user',action,owner['unit']],capture_output=True,text=True,timeout=10)
        commands.append(dict(action=action,exit=r.returncode,stdout=r.stdout,stderr=r.stderr));assert r.returncode==0
    after=show(owner['unit']);assert after['LoadState']=='not-found'
    assert not Path('/sys/fs/cgroup'+owner['properties']['ControlGroup']).exists()
    p=out/'console.txt';fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:os.fchmod(fd,0o444);os.fsync(fd)
    finally:os.close(fd)
    return h.put(out/'independent-failed-review-owned-closeout.json',dict(
        schema='robotron-original-admission-engineering-failed-review-owned-closeout-v1',status='FAILED_ORIGINAL_REVIEW_PRESERVED',
        kind=kind,launch_index=ip,original_parent_owner=row['original_live_owner'],parent_terminal=terminal,
        original_parent_actual_exit=1,worker_actual_exit=0,worker_lifecycle=life_pin,
        all_original_parent_worker_launcher_births_units_cgroups_and_tmpfs_released=True,
        queued_samples=len(outcome['samples']),queued_unaccepted=len(outcome['unaccepted']),
        writer_reported_all_raw_durable_and_joined=True,all_raw_independently_replayed_and_qualified=False,
        original_publication_gap_counterexample=gaps,original_error='Running projection gap exceeds500ms',
        console=h.pin(p),owned_release_commands=commands,released_properties=after,source=h.pin(Path(__file__).resolve()),
        actual_parent_resources=dict(CPU_cores=2,memory_bytes=4<<30,runtime_s=780),
        scientific_launch_qualified=False,quality_qualified=False,promotion=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--index',type=Path);p.add_argument('--index-sha256');p.add_argument('--kind',choices=('deadline','fullgame'))
    a=p.parse_args()
    if a.execute:print(json.dumps(close(a.index,a.index_sha256,a.kind)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
