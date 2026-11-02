"""CAS-adopt immutable Robotron progress evidence; preserve exact prior state."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

N=Path(__file__).resolve().parent
G=N.parents[3]

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def exact(path,raw):
    with path.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())

def replace(path,raw,pre):
    assert path.read_bytes()==pre
    tmp=path.with_name(path.name+'.shared64-next')
    with tmp.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
    assert path.read_bytes()==pre;os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def main():
    p=argparse.ArgumentParser();p.add_argument('--record',type=Path,required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
    h=load('_shared64_adopt_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    assert h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    reader=load('_shared64_adopt_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    record_pin=h.pin(a.record.resolve());assert record_pin['sha256']==a.sha256
    record=reader.read_pin(record_pin)
    for pin in record['evidence']:h.checked(pin)
    archive=Path(record['archive']);archive.mkdir(mode=0o700)
    path=G/'logs/managed-learning-20261015/state.json';pre=path.read_bytes();state=json.loads(pre);old=copy.deepcopy(state)
    exact(archive/'canonical-before.exact.json',pre)
    g=state['optimization_goal'];prior=g['current_recovery_index'];recovery=copy.deepcopy(reader.read_pin(prior))
    updates=record['updates'];assert not({'current_recovery_index','current_optimization_recovery_index'}&updates.keys())
    updates.update(status='active',last_updated_unix_s=time.time(),previous_goal_turn_classification=g.get('latest_goal_turn_classification'))
    g.update(updates);recovery.update(updates)
    recovery.update(previous_recovery_index=prior,canonical_preimage=h.pin(archive/'canonical-before.exact.json'),
        created_unix_s=time.time(),progress_record=record_pin,goal_status='active')
    recovery_pin=h.put(Path(record['recovery']),recovery)
    g['current_recovery_index']=g['current_optimization_recovery_index']=recovery_pin
    assert {k:v for k,v in state.items()if k!='optimization_goal'}=={k:v for k,v in old.items()if k!='optimization_goal'}
    raw=(json.dumps(state,separators=(',',':'),allow_nan=False)+'\n').encode();assert len(raw)<1<<20
    replace(path,raw,pre)
    receipt=h.put(archive/'canonical-adoption.json',dict(record=record_pin,previous_exact=h.pin(archive/'canonical-before.exact.json'),
        recovery=recovery_pin,state_after=h.pin(path),only_optimization_goal_changed=True,state_bytes=len(raw),created_unix_s=time.time()))
    doc=G/'DELL_SETUP.md';before=doc.read_bytes();exact(archive/'DELL_SETUP-before.exact.md',before)
    separator=b'Earlier five-minute observation, retained for history:\n';assert before.count(separator)==1
    head=('# Dell GB300 Robotron setup\n\nCurrent optimization recovery: [Current verified progress](logs/managed-learning-20261015/run-26/'+Path(record['recovery']).name+'). Goal active.\n\n'+record['documentation'].rstrip()+'\n\n').encode()
    replace(doc,head+separator+before.split(separator,1)[1],before)
    h.put(archive/'documentation-adoption.json',dict(canonical=receipt,recovery=recovery_pin,
        document_after=h.pin(doc),previous_exact=h.pin(archive/'DELL_SETUP-before.exact.md'),historical_suffix_preserved_verbatim=True))
    print(json.dumps(dict(adoption=receipt,recovery=recovery_pin,state_bytes=len(raw))))

if __name__=='__main__':main()
