"""Verify already-supervised slot2 replacement; write only new monitoring inputs."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

N=Path(__file__).resolve().parent
G=N.parents[3]

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
    h=load('_slot2_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    reader=load('_slot2_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    oldbp=h.pin(N.parent/'LR125-after-protected3045-firstSave-original01-preparation-20261025/postcapture-current-main-binding.json')
    assert oldbp['sha256']=='89a0fef31ef8a504f8cb02f4bc2a6fd04e8ab6555bbcae912531d41d835d1aca'
    old=reader.read_pin(oldbp);binding=copy.deepcopy(old);policy=reader.read_pin(old['supervision_policy'])
    before=copy.deepcopy(policy['baseline_actors']['2']);pid=3544516;proc=Path('/proc',str(pid))
    birth=int(proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]);assert birth==113311128
    assert not Path('/proc',str(before['pid'])).exists()
    actor=copy.deepcopy(before);actor.update(pid=pid,starttime_ticks=birth)
    assert int(proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[1])==before['parent_pid']==2258189
    assert proc.joinpath('cgroup').read_text().strip()=='0::'+before['cgroup']
    assert proc.joinpath('cmdline').read_bytes().decode().split('\0')[:-1]==before['command']
    env=dict(v.split('=',1)for v in proc.joinpath('environ').read_bytes().decode().split('\0')if '='in v)
    assert {k:env.get(k)for k in before['environment']}==before['environment']
    assert sorted(os.sched_getaffinity(pid))==before['affinity']
    uids=[int(v)for v in next(line for line in proc.joinpath('status').read_text().splitlines()if line.startswith('Uid:')).split()[1:]]
    assert uids==before['uids']
    exe=proc.joinpath('exe').resolve();assert str(exe)==before['executable']['path'];st=exe.stat()
    meta=dict(device=st.st_dev,inode=st.st_ino,bytes=st.st_size,mtime_ns=st.st_mtime_ns,ctime_ns=st.st_ctime_ns,mode=oct(st.st_mode&511),uid=st.st_uid)
    assert meta==before['executable']['identity']
    for a in old['actors']:
        if a['slot']==2:continue
        q=Path('/proc',str(a['pid']))
        assert int(q.joinpath('stat').read_text().rsplit(')',1)[1].split()[19])==a['starttime_ticks']
        assert sorted(os.sched_getaffinity(a['pid']))==a['mask']
    owners={}
    for kind in ('trainer','fleet'):
        o=policy[kind];p=subprocess.run(['systemctl','--user','show',o['unit']],capture_output=True,text=True,timeout=20)
        assert p.returncode==0
        fields=dict(line.split('=',1)for line in p.stdout.splitlines()if '='in line)
        assert fields['MainPID']==str(o['pid'])and fields['InvocationID']==o['invocation_id']and fields['NRestarts']=='0'and fields['ActiveState']=='active'
        assert int(Path('/proc',str(o['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])==o['starttime_ticks']
        owners[kind]=dict(argv=p.args,exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as response:raw=response.read(2000000)
    api=json.loads(raw)
    assert api['client_count']==192 and sorted(r['client_slot']for r in api['client_rows'])==list(range(192))
    assert api['training_enabled']is True and api['measurement_active']is False
    assert api['host_pipeline']['learning_exposure']['replay']['process_id']==old['owner']['pid']
    log=Path('/proc/2258189/fd/1').resolve();size=log.stat().st_size
    with log.open('rb')as stream:stream.seek(max(0,size-8000));tail=stream.read()
    assert b'respawned client 2 (PID 3544516' in tail
    dest=N/'evaluator-count-active600-counterbalanced-engineering-original04/postfailure-supervised-slot2-main-reconciliation-original01'
    dest.mkdir(mode=0o700);logcopy=dest/'fleet-supervisor-tail-original-bytes.txt'
    with logcopy.open('xb')as stream:stream.write(tail);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    evidence=h.put(dest/'supervised-actor-transition-evidence.json',dict(
        schema='robotron-postfailure-supervised-slot2-transition-v1',source=h.pin(__file__),prior_binding=oldbp,
        previous_actor=before,current_actor=actor,original191_other_actor_births_and_affinities_unchanged=True,
        current_all192_API_slots_verified=True,actual_unit_readbacks=owners,original_fleet_tail=h.pin(logcopy),
        API_observation={k:api[k]for k in ('ts','client_count','frame_count','learner_frame_count','training_steps','optimized_samples')},
        supervisor_automatically_respawned=True,agent_launched_or_restarted_any_process=False,
        trainer_or_fleet_owner_changed=False,prior_original04_remains_invalid=True,created_unix_s=time.time()))
    policy['baseline_actors']['2']=actor
    assert all(v==policy['baseline_actors'][k]for k,v in reader.read_pin(old['supervision_policy'])['baseline_actors'].items()if k!='2')
    policy_pin=h.put(dest/'current-main-supervision-policy.json',policy)
    for a in binding['actors']:
        if a['slot']==2:a.update(pid=pid,starttime_ticks=birth)
    binding.update(prior_binding=oldbp,supervision_policy=policy_pin,verified_between_study_actor_transition=evidence,
        historical_original_actor_survivors=189,verified_between_study_replacement_count=3,
        current_binding_reason='Only supervised slot2 identity reconciled after original04 invalidated; all197 held hashes/main recipe/trainer/fleet and191 other actors unchanged.',
        historical_study_binding_or_receipts_changed=False)
    assert binding['held_hashes']==old['held_hashes']and len(binding['held_hashes'])==197 and binding['owner']==old['owner']
    binding_pin=h.put(dest/'current-main-binding.json',binding)
    oldmon=N.parent/'LR125-after-protected3045-firstSave-original01-preparation-20261025/postcapture-current-main-readonly-monitor-v2.py'
    tree=ast.parse(oldmon.read_text())
    node=next(z for z in tree.body if isinstance(z,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINS'for t in z.targets))
    pins=ast.literal_eval(node.value);pins['binding']=binding_pin;node.value=ast.parse(repr(pins),mode='eval').body
    for z in ast.walk(tree):
        if isinstance(z,ast.keyword)and z.arg in ('historical_original_actor_survivors','verified_between_study_replacements'):
            z.value=ast.Constant(189 if z.arg=='historical_original_actor_survivors' else 3)
    ast.fix_missing_locations(tree);source=ast.unparse(tree)+'\n';mon=dest/'current-main-readonly-monitor.py';compile(source,str(mon),'exec')
    with mon.open('xb')as stream:stream.write(source.encode());stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    p=subprocess.run(['/usr/bin/python3.12','-I','-B',str(mon)],capture_output=True,text=True,timeout=30)
    assert p.returncode==0,p.stderr;current=json.loads(p.stdout)
    receipt=h.put(dest/'independent-current-main-readback.json',dict(transition=evidence,binding=binding_pin,
        supervision_policy=policy_pin,monitor=h.pin(mon),monitor_actual_exit=0,main=current,
        only_slot2_actor_and_readonly_registry_changed=True,all197_held_hashes_and_recipe_unchanged=True,
        no_process_launch_restart_or_main_recipe_mutation=True,created_unix_s=time.time()))
    print(json.dumps(dict(transition=evidence,binding=binding_pin,monitor=h.pin(mon),readback=receipt,main=current)))

if __name__=='__main__':main()
