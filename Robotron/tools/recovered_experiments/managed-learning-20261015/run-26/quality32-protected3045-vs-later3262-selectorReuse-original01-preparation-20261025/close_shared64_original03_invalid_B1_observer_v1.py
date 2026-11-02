"""Preserve failed original03 B1 and verify cleanup; never retry or rescore."""
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
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None

def main():
    c=load('_invalid_B1_c',N/'close_shared64_original03_case_v1.py').CloseOriginal('02-B1-capacity64')
    h=c.h;d=c.directory;out=Path(c.job['output']);rp=h.pin(out/'result.json');r=c.read(rp)
    assert r['errors'][0]=="Original independent mixed full main-health watch: ValueError('Original autonomous observer birth changed')"
    assert r['errors'][1]=="ValueError('Original compiled32 wall bound/interruption')"
    assert "Original dedicated observer did not close validly: ValueError('Bounded original live lock wait exceeded')"in r['errors']
    assert r['complete']is r['quality_qualified']is False
    assert r['active_start']is r['active_end']is r['active_frame_rate']is None
    assert r['all_original_threads_stopped']is r['original_lease_released']is r['immutable_inputs_unchanged']is True
    assert r['original_unsealed_journal_paths']==[] and len(r['original_slots'])==64
    reap=r['original_post_origin_child_reap'];assert reap['all_original_children_reaped']is True and reap['unknown_slots']==[]
    assert reap['exit_statuses_normalized']is False
    native=c.scope(h.pin(d/'execution-original01/root-original-identity.json'),h.pin(d/'execution-original01/root-original-result-and-owned-release.json'),c.record['launch_config'],1,12,24<<30,22260,512,30,True)
    life=c.read(r['main_observer_lifecycle'])
    assert life['actual_controller_exit']==1 and life['original_scope_released']is life['all_owned_worker_and_controller_processes_reaped']is True
    worker=c.scope(life['worker_owner'],life['worker_closure'],life['worker_config'],1,2,4<<30,22260,128,5)
    outcome=c.read(life['worker_outcome']);failure=c.read(r['main_health_failure'])
    assert outcome['success']is False and outcome['error']==failure['error']=="ValueError('Bounded original live lock wait exceeded')"
    assert outcome['all_writer_threads_stopped']is True and outcome['signals_received']==[]
    release=c.read(life['live_control_release'])
    ram=c.read(life['worker_job'])['live_control']['directory'] if 'directory'in c.read(life['worker_job'])['live_control'] else None
    if ram is not None:assert not Path(ram).exists()
    exits={}
    for slot,actor in r['original_slots'].items():
        assert birth(actor['pid'])!=actor['birth']
        assert actor['outputs_sealed_after_original_writer_closure']is True and actor['original_unsealed_output_paths']==[]
        assert actor['actual_exit']==(0 if int(slot)<4128 else -15)
        exits[slot]=actor['actual_exit']
        for pin in actor['files'].values():h.checked(pin)
        h.checked(actor['boot_restore'])
    for pin in r['journal'].values():h.checked(pin)
    for name in ('03-B2-capacity64','04-A2-control'):
        for sub in ('execution-original01','diagnostic-output-original01','original-native-launch-preflight.json'):
            assert not(d.parent/name/sub).exists()
    A1=h.pin(d.parent/'01-A1-control/independent-original-capacity64-case-closeout.json')
    assert A1['sha256']=='dd151b0aa7e7a36fb2376cb4dcd1c72a3b12cafb1daf12631ae53a26e677d57d'
    assert c.read(A1)['status']=='VALID_ORIGINAL_CAPACITY64_ENGINEERING_CASE_NO_QUALITY'
    resources=c.free_resources()
    monitor=N.parent/'LR125-after-protected3045-firstSave-original01-preparation-20261025/postcapture-current-main-readonly-monitor-v2.py'
    p=subprocess.run(['/usr/bin/python3.12','-I','-B',str(monitor)],capture_output=True,text=True,timeout=30);assert p.returncode==0,p.stderr
    dest=d/'invalid-original-B1-observer-independent-closeout-original01';dest.mkdir(mode=0o700);logs=[]
    for label,scope in [('native',native),('observer',worker)]:
        base=Path(scope['closure']['path']).parent
        for name in ('stdout.txt','stderr.txt'):
            source=base/name;pin=h.pin(source);target=dest/(label+'-'+name)
            with target.open('xb')as f:f.write(h.checked(pin).read_bytes());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
            logs.append(dict(original=pin,immutable_copy=h.pin(target),original_mode_preserved=True))
    disposition=h.put(dest/'independent-invalid-original-B1-observer-disposition.json',dict(
        schema='robotron-shared64-original03-B1-observer-failure-independent-disposition-v1',
        status='INVALID_ORIGINAL_B1_OBSERVER_LOCK_WAIT_CLOSED',source=h.pin(__file__),native_result=rp,
        actual_native_tool_session=79757,actual_native_exit=1,actual_observer_exit=1,native_scope=native,observer_scope=worker,
        all6_descriptors_argv_resources_input_pins_and_owner_unit_cgroup_release_verified=True,
        all64_original_MAME_children_reaped=True,actual_MAME_exits=exits,exit0_count=32,SIGTERM_exit_count=32,
        actor_outputs_sealed_and_pins_checked=True,main_observer_outcome=life['worker_outcome'],main_failure=r['main_health_failure'],
        original_RAM_release=life['live_control_release'],RAM_release_report=release,closed_log_copies=logs,resources=resources,
        main=json.loads(p.stdout),A1_valid_descriptive_only=A1,B2_A2_never_launched=True,
        active600_window_never_started=True,private_FPS_available=False,failed_campaign_preserved=True,retry_allowed=False,
        observed_failure='Observer100ms live-control lock wait exceeded; subsequent failed-state publish collided with its preserved temporary file.',
        cause_of_long_lock_hold_unproven=True,private64_startup_success_verified=False,
        quality_qualified=False,throughput_gain_verified=False,main_runtime_changed=False,created_unix_s=time.time()))
    campaign=h.put(d.parent/'original-engineering-campaign-invalid-disposition.json',dict(
        schema='robotron-capacity64-invalid-original-ABBA-disposition-v1',status='INVALID_ORIGINAL_B1_OBSERVER_LOCK_WAIT_CLOSED',
        original_attempt=3,disposition=disposition,valid_A1_descriptive_history_only=A1,
        all_original_scopes_closed=True,B2_A2_never_launched=True,retry_allowed=False,comparison_reference=None,
        comparison_gain_evaluated=False,prior_or_partial_rates_reused=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(disposition=disposition,campaign=campaign)))

if __name__=='__main__':main()
