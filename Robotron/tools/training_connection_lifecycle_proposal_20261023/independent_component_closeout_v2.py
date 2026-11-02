"""Read actual original CPU archive descriptors/resources, argv and owned release."""
import json
from pathlib import Path
import subprocess


def closeout(directory,h,archive,read,expected_exit):
    directory=Path(directory);config=json.loads(h.checked(h.pin(directory/'controller-config.json')).read_bytes())
    output=directory/'execution-original01'
    cp=h.pin(output/'root-original-result-and-owned-release.json');closure=read(cp)
    op=h.pin(output/'root-original-identity.json');owner=read(op)
    fields=archive.archived_closure(closure,owner,read,exit_zero=expected_exit==0)
    assert closure['original_exit']==expected_exit
    for key,value in dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',
        TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no').items():assert fields[key]==value,(key,fields[key])
    expected='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(output/'tmp')+' '+' '.join(config['argv'])
    assert expected+' ; ignore_errors=no ;'in fields['ExecStart']
    for pin in config['pins']:
        actual=h.pin(pin['path']);assert all(actual[k]==pin[k]for k in ['path','sha256','bytes'])
        assert all(actual['identity'][k]==v for k,v in pin['identity'].items())
    live=[]
    for unit in (owner['unit'],owner['timer']):
        process=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=5)
        assert process.returncode==0
        current=dict(line.split('=',1)for line in process.stdout.splitlines()if '='in line)
        assert current['Id']==unit and current['LoadState']=='not-found'
        if unit==owner['unit']:assert current['MainPID']=='0'
        live.append(dict(argv=process.args,exit=process.returncode,stdout=process.stdout,stderr=process.stderr))
    proc=Path('/proc',str(owner['pid']),'stat')
    assert not proc.exists()or int(proc.read_text().rsplit(')',1)[1].split()[19])!=owner['starttime_ticks']
    cg=fields.get('ControlGroup','')
    if cg:assert not(Path('/sys/fs/cgroup'+cg)/'cgroup.procs').exists()or not(Path('/sys/fs/cgroup'+cg)/'cgroup.procs').read_text().strip()
    result=dict(owner=op,closure=cp,actual_exit=expected_exit,
        actual6_original_descriptors_argv_resources_pins_release_and_birth_absence_verified=True,
        post_release_original_units=live,actual_stdout=h.pin(output/'stdout.txt'),actual_stderr=h.pin(output/'stderr.txt'),
        original_log_modes_preserved=True)
    return result
