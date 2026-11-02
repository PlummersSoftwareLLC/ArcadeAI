"""Read actual live owners, all declared startup subjects and main health."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

N=Path(__file__).resolve().parent
G=N.parents[3]

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def birth(pid):
    return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])

def snapshot(path):
    for _ in range(3):
        with path.open('rb')as f:
            before=os.fstat(f.fileno());raw=f.read();after=os.fstat(f.fileno())
        identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if identity(before)==identity(after)and len(raw)==after.st_size:return raw,identity(after)
    raise ValueError('Concurrent snapshot changed; observe same original again')

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--label',required=True);a=p.parse_args()
    c=load('_live_close',N/'close_shared64_original04_case_v1.py').CloseOriginal(a.case);h=c.h
    out=Path(c.job['output']);d=c.directory
    if not(out/'status.json').exists():print(json.dumps(dict(startup_pending=True)));return
    raw,identity=snapshot(out/'status.json');status=json.loads(raw)
    assert 0<=time.time()-status['observed_unix_s']<8
    assert status['errors']==[] and status['original_job']==c.record['native_job']
    assert status['active_start']is not None
    assert sorted(map(int,status['slots']))==c.job['actor_slots']
    boundary=status['controller']['boundary']
    assert boundary['ready']is True and boundary['clients']==boundary['acknowledged']==c.count
    assert boundary['actor_slots']==c.job['actor_slots']
    loaded_pin=h.pin(out/'original-loaded-policy.json');loaded=c.read(loaded_pin);policy=loaded['policy']
    assert policy['checkpoint_sha256']==c.job['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
    assert loaded['gpu_uuid']==loaded['CUDA_VISIBLE_DEVICES']==c.job['gpu_uuid']
    assert loaded['memory_is_none']is loaded['optimizer_is_none']is True and loaded['replay_enabled']is False
    assert policy['training_enabled']is policy['replay_enabled']is False
    assert policy['epsilon']==policy['expert_ratio']==0
    assert loaded['compile_report']['all_shapes_verified']==list(range(1,17))
    assert policy['numeric_policy']['compiled']is True and policy['numeric_policy']['weights']=='float32'
    owners=[]
    for label,base,cpu,memory,tasks,stop in [('native',d,12,24<<30,512,30),('observer',out/'main-health-scope',2,4<<30,128,5)]:
        op=h.pin(base/'execution-original01/root-original-identity.json');owner=c.read(op)
        cfgp=h.pin(base/'controller-config.json');cfg=c.read(cfgp);fields=c.control.show(owner['unit'])
        assert birth(owner['pid'])==owner['starttime_ticks']
        actual=Path('/proc',str(owner['pid']),'cmdline').read_bytes().decode().split('\0')[:-1]
        assert actual==cfg['argv'],(label,actual,cfg['argv'])
        assert fields['ActiveState']=='active'and fields['MainPID']==str(owner['pid'])and fields['InvocationID']==owner['invocation_id']
        assert c.arc.duration_seconds(fields['CPUQuotaPerSecUSec'])==cpu and fields['MemoryMax']==str(memory)
        assert fields['MemorySwapMax']=='0'and fields['TasksMax']==str(tasks)and fields['SendSIGKILL']=='no'
        assert c.arc.duration_seconds(fields['RuntimeMaxUSec'])==22260 and c.arc.duration_seconds(fields['TimeoutStopUSec'])==stop
        assert fields['NRestarts']=='0'and fields['Restart']=='no'
        for pin in cfg['pins']:assert c.control.pin(pin['path'])==pin
        owners.append(dict(kind=label,owner=op,config=cfgp,actual_argv=actual,actual_unit_fields=fields))
    starts_raw,starts_identity=snapshot(out/'journal/measurement_starts.jsonl')
    rows=[json.loads(line)for line in starts_raw.splitlines()];first={}
    for row in rows:first.setdefault(row['client_slot'],row)
    assert sorted(first)==c.job['actor_slots']
    actors=[]
    for slot in c.job['actor_slots']:
        live=status['slots'][str(slot)];actor_pin=h.pin(out/'actors'/str(slot)/'original-actor.json');actor=c.read(actor_pin)
        assert actor['pid']==live['pid']and actor['starttime_ticks']==live['birth']==birth(actor['pid'])
        assert Path('/proc',str(actor['pid']),'cmdline').read_bytes().decode().split('\0')[:-1]==actor['argv']
        assert live['prefix_verified']is True and live['error']is live['actual_exit']is None
        assert live['sequence']>=1200 and live['ledger']['rejected']==0 and live['ledger']['accepted']>=1200
        row=first[slot];cert=row['context']['startup_certificate'];body={k:v for k,v in cert.items()if k!='identifier'}
        assert hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==cert['identifier']
        assert cert['slot']==slot and cert['session']==actor['session']==c.job['sessions'][str(slot)]
        assert cert['connection']==actor['connection']==c.job['connections'][str(slot)]
        assert cert['policy']==policy and cert['loaded_rom_sha256']==c.job['loaded_rom_sha256']
        assert live['handoff']['certificate_identifier']==cert['identifier']
        actors.append(dict(slot=slot,original_actor=actor_pin,pid=actor['pid'],birth=actor['starttime_ticks'],
            sequence=live['sequence'],accepted=live['ledger']['accepted'],rejected=0,
            certificate_identifier=cert['identifier'],journal_game_id=row['journal_game_id']))
    main_sample_pin=h.pin(sorted((out/'main-observations/samples').glob('*-original.json'))[-1]);main_sample=c.read(main_sample_pin)
    transport=main_sample['transport'];raw_api=base64.b64decode(transport['raw_API']['base64'],validate=True)
    assert len(raw_api)==transport['raw_API']['bytes']and hashlib.sha256(raw_api).hexdigest()==transport['raw_API']['sha256']
    assert json.loads(raw_api)['client_count']==192 and 0<=time.time()-transport['observed_unix_s']<4
    mon=N.parent/'LR125-after-protected3045-firstSave-original01-preparation-20261025/postcapture-current-main-readonly-monitor-v2.py'
    process=subprocess.run(['/usr/bin/python3.12','-I','-B',str(mon)],capture_output=True,text=True,timeout=30)
    assert process.returncode==0,process.stderr
    main=json.loads(process.stdout);assert main['client_count']==192 and main['held_inputs']==197 and main['autosave_age_s']<=360
    dest=d/a.label;dest.mkdir(mode=0o700)
    copies=[]
    for name,data in [('status-snapshot.json',raw),('measurement-starts-prefix.jsonl',starts_raw)]:
        target=dest/name
        with target.open('xb')as f:f.write(data);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        copies.append(h.pin(target))
    # Recheck actual owners and all actors at the end of this readback.
    for entry in owners:
        owner=c.read(entry['owner']);assert birth(owner['pid'])==owner['starttime_ticks']
    for actor in actors:assert birth(actor['pid'])==actor['birth']
    report=h.put(dest/'live-readback.json',dict(schema='robotron-shared64-original04-live-readback-v1',case=a.case,
        native_job=c.record['native_job'],qualified_launches=c.qualified_pin,original_attempt=1,no_retry=True,
        status_snapshot=copies[0],measurement_starts_prefix=copies[1],live_source_fd_identities=[identity,starts_identity],
        owners=owners,loaded_policy=loaded_pin,initial_main_readiness=h.pin(out/'original-initial-main-readiness.json'),
        all_declared_original_MAME_births_argv_and_certificates_verified=True,actors=actors,declared_actor_count=c.count,
        actual_all_declared_prefixes_ready=True,active_start=status['active_start'],boundary=boundary,
        original_main_sample=main_sample_pin,original_main_sample_index=transport['index'],main=main,
        all_launch_input_pins_unchanged=True,quality_qualified=False,final_raw_ROM_main_runtime_review_pending=True,
        throughput_gain_verified=False,created_unix_s=time.time()))
    print(json.dumps(dict(readback=report,actors=c.count,min_sequence=min(v['sequence']for v in actors),main=main)))

if __name__=='__main__':main()
