"""Audit and preserve the failed original02 import; never launch or retry."""
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

def main():
    c=load('_invalid_import_close',N/'close_shared64_original02_case_v1.py').CloseOriginal('01-A1-control')
    h=c.h;d=c.directory;out=Path(c.job['output'])
    rp=h.pin(out/'result.json');r=c.read(rp)
    assert r['errors']==["ModuleNotFoundError(\"No module named 'fixed_slot_cohort_drain_v1'\")",
        "Original dedicated observer did not close validly: ValueError('Original evidence coverage incomplete')"]
    assert r['complete']is r['quality_qualified']is False
    assert r['original_slots']=={} and r['journal']=={}
    assert r['active_start']is r['active_end']is r['active_frame_rate']is r['policy_before']is None
    assert r['all_original_threads_stopped']is r['original_lease_released']is r['immutable_inputs_unchanged']is True
    assert r['original_unsealed_journal_paths']==[]
    reap=r['original_post_origin_child_reap']
    assert reap['all_original_children_reaped']is True and reap['original_children']=={} and reap['unknown_slots']==[]
    assert reap['signals_sent']is reap['exit_statuses_normalized']is False
    native=c.scope(h.pin(d/'execution-original01/root-original-identity.json'),
        h.pin(d/'execution-original01/root-original-result-and-owned-release.json'),
        c.record['launch_config'],1,12,24<<30,22260,512,30,True)
    life=c.read(r['main_observer_lifecycle'])
    assert life['actual_controller_exit']==1 and life['original_scope_released']is True
    assert life['all_owned_worker_and_controller_processes_reaped']is True
    worker=c.scope(life['worker_owner'],life['worker_closure'],life['worker_config'],1,2,4<<30,22260,128,5)
    c.read(life['worker_outcome']);c.read(r['main_health_failure'])
    for case in ('02-B1-capacity64','03-B2-capacity64','04-A2-control'):
        for name in ('execution-original01','diagnostic-output-original01','original-native-launch-preflight.json'):
            assert not (d.parent/case/name).exists()
    resources=c.free_resources()
    p=subprocess.run(['/usr/bin/python3.12','-I','-B',str(N.parent/'LR125-after-protected3045-firstSave-original01-preparation-20261025/postcapture-current-main-readonly-monitor-v2.py')],capture_output=True,text=True,timeout=30)
    assert p.returncode==0,p.stderr
    dest=d/'invalid-original-A1-import-independent-closeout-original01';dest.mkdir(mode=0o700)
    logs=[]
    for label,scope in [('native',native),('observer',worker)]:
        base=Path(scope['closure']['path']).parent
        for name in ('stdout.txt','stderr.txt'):
            source=base/name;pin=h.pin(source);raw=h.checked(pin).read_bytes();target=dest/(label+'-'+name)
            with target.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
            logs.append(dict(original=pin,immutable_copy=h.pin(target),original_mode_preserved=True))
    report=h.put(dest/'independent-invalid-original-A1-import-disposition.json',dict(
        schema='robotron-capacity64-original-import-failure-independent-closeout-v1',created_unix_s=time.time(),source=h.pin(__file__),
        status='INVALID_ORIGINAL_A1_IMPORT_CLOSED_NO_RETRY',native_result=rp,native_scope=native,observer_scope=worker,
        native_original_tool_handle=67459,original_tool_handle_now_missing=True,
        original_native_archived_exit=1,original_observer_archived_exit=1,original_births_units_cgroups_absent=True,
        all6_descriptors_argv_resources_and_pins_verified_each_scope=True,closed_log_copies=logs,
        MAME_spawn_count=0,active_rate_available=False,private_resources=resources,main=json.loads(p.stdout),
        B1_B2_A2_never_launched=True,failed_campaign_preserved=True,retry_allowed=False,
        cause='Native import still named fixed_slot_cohort_drain_v1 while held source is fixed_slot_cohort_drain_v2',
        required_next_guard='Cold execute actual native import AST in both32/64 families in actual free-threaded runtime before GPU lease',
        quality_qualified=False,throughput_gain_verified=False,main_runtime_changed=False))
    campaign=h.put(d.parent/'original-engineering-campaign-invalid-disposition.json',dict(
        schema='robotron-capacity64-invalid-original-ABBA-disposition-v1',status='INVALID_ORIGINAL_A1_IMPORT_CLOSED',
        original_attempt=2,disposition=report,all_original_scopes_closed=True,B1_B2_A2_never_launched=True,
        retry_allowed=False,comparison_reference=None,comparison_gain_evaluated=False,
        prior_or_partial_rates_reused=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(disposition=report,campaign=campaign)))

if __name__=='__main__':main()
