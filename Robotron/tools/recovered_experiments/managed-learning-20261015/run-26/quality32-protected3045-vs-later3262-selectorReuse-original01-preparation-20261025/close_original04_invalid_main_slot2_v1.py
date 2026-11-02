"""Audit failed original04 A1; preserve the main slot2 transition and all results."""
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

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None

def main():
    c=load('_invalid04_c',N/'close_shared64_original04_case_v1.py').CloseOriginal('01-A1-control')
    h=c.h;d=c.directory;out=Path(c.job['output']);rp=h.pin(out/'result.json');r=c.read(rp)
    error="ValueError('Only full192 or single duplicate193 is covered; no191/other-count exception')"
    assert r['errors'][0]=="Original independent mixed full main-health watch: ValueError('Original observer is not running successfully')"
    assert 'Original dedicated observer did not close validly: '+error in r['errors']
    assert r['complete']is r['quality_qualified']is False and r['active_frame_rate']is r['active_end']is None
    assert r['active_start']is not None and r['all_original_threads_stopped']is r['original_lease_released']is r['immutable_inputs_unchanged']is True
    assert r['original_unsealed_journal_paths']==[] and len(r['original_slots'])==32
    native=c.scope(h.pin(d/'execution-original01/root-original-identity.json'),
        h.pin(d/'execution-original01/root-original-result-and-owned-release.json'),c.record['launch_config'],1,12,24<<30,22260,512,30,True)
    life=c.read(r['main_observer_lifecycle']);outcome=c.read(life['worker_outcome'])
    worker=c.scope(life['worker_owner'],life['worker_closure'],life['worker_config'],1,2,4<<30,22260,128,5)
    assert outcome['success']is False and outcome['error']==error and outcome['all_writer_threads_stopped']is True
    assert outcome['signals_received']==[] and outcome['observed_samples']==1387
    assert outcome['running_projection_publication_stats']==dict(attempts=1386,published=1386,coalesced_busy_reader=0,errors=0)
    assert life['original_scope_released']is life['all_owned_worker_and_controller_processes_reaped']is True
    reap=r['original_post_origin_child_reap'];assert reap['all_original_children_reaped']is True and reap['unknown_slots']==[]
    assert reap['signals_sent']is reap['exit_statuses_normalized']is False
    for actor in r['original_slots'].values():
        assert actor['actual_exit']==0 and birth(actor['pid'])!=actor['birth']
        assert actor['outputs_sealed_after_original_writer_closure']is True and actor['original_unsealed_output_paths']==[]
        for pin in actor['files'].values():h.checked(pin)
    for pin in r['journal'].values():h.checked(pin)
    release=c.read(life['live_control_release']);assert release['original_root_absent']is release['original_members_absent']is True
    intent=c.read(release['intent']);assert intent['all_original_bytes_durably_archived']is True
    for entry in intent['files']:
        assert h.pin(h.checked(entry['archived']))['sha256']==entry['original']['sha256']
    failure=c.read(r['main_health_failure'])
    samples=sorted((out/'main-observations/samples').glob('*-original.json'));assert len(samples)==1387
    lastpin=h.pin(samples[-1]);last=c.read(lastpin);transport=last['transport']
    raw=base64.b64decode(transport['raw_API']['base64'],validate=True)
    assert len(raw)==transport['raw_API']['bytes']and hashlib.sha256(raw).hexdigest()==transport['raw_API']['sha256']
    api=json.loads(raw);assert api['client_count']==191
    assert sorted(v['client_slot']for v in api['client_rows'])==[s for s in range(192)if s!=2]
    for name in ('02-B1-capacity64','03-B2-capacity64','04-A2-control'):
        for sub in ('execution-original01','diagnostic-output-original01','original-native-launch-preflight.json'):
            assert not(d.parent/name/sub).exists()
    resources=c.free_resources()
    reconciled=d.parent/'postfailure-supervised-slot2-main-reconciliation-original01'
    new_binding=h.pin(reconciled/'current-main-binding.json');monitor=h.pin(reconciled/'current-main-readonly-monitor.py')
    p=subprocess.run(['/usr/bin/python3.12','-I','-B',str(h.checked(monitor))],capture_output=True,text=True,timeout=30)
    assert p.returncode==0,p.stderr;current=json.loads(p.stdout)
    assert current['client_count']==192 and current['held_inputs']==197 and current['bound192_actor_identities_and_affinities_verified']is True
    dest=d/'invalid-original-A1-main-slot2-independent-closeout-original01';dest.mkdir(mode=0o700);logs=[]
    for label,scope in [('native',native),('observer',worker)]:
        for name in ('stdout.txt','stderr.txt'):
            source=Path(scope['closure']['path']).parent/name;target=dest/(label+'-'+name)
            with target.open('xb')as stream:stream.write(h.checked(h.pin(source)).read_bytes());stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
            logs.append(dict(original=h.pin(source),immutable_copy=h.pin(target),original_mode_preserved=True))
    disposition=h.put(dest/'independent-invalid-original-A1-main-slot2-disposition.json',dict(
        schema='robotron-original04-main-slot2-failure-independent-closeout-v1',status='INVALID_ORIGINAL_A1_MAIN191_SLOT2_TRANSITION_CLOSED',source=h.pin(__file__),
        native_result=rp,actual_original_tool_session=38946,actual_native_exit=1,actual_observer_exit=1,
        native_scope=native,observer_scope=worker,all6_descriptors_resources_argv_pins_birth_units_cgroups_release_verified=True,
        all32_original_MAME_exit0_and_reaped_and_outputs_sealed_verified=True,
        original_main_failure=r['main_health_failure'],original_observer_outcome=life['worker_outcome'],
        original_last_raw_main_sample=lastpin,last_raw_API_checksum_and191_count_and_only_slot2_missing_verified=True,
        original_raw_sample_count=1387,running_projection_publication_stats=outcome['running_projection_publication_stats'],
        observer_publication_failure=False,original_RAM_release=life['live_control_release'],closed_logs=logs,resources=resources,
        B1_B2_A2_never_launched=True,active600_window_not_completed=True,qualified_control_FPS_available=False,
        new_supervised_slot2_transition=h.pin(reconciled/'supervised-actor-transition-evidence.json'),
        new_main_binding=new_binding,new_main_monitor=monitor,new_main=current,
        all197_held_hashes_trainer_recipe_and191_other_actor_identities_unchanged=True,
        historical_original04_binding_or_result_rewritten=False,failed_original_preserved=True,retry_allowed=False,
        quality_qualified=False,throughput_gain_verified=False,created_unix_s=time.time()))
    campaign=h.put(d.parent/'original-engineering-campaign-invalid-disposition.json',dict(
        schema='robotron-capacity64-invalid-original-ABBA-disposition-v1',status='INVALID_ORIGINAL_A1_MAIN191_SLOT2_TRANSITION_CLOSED',
        original_attempt=4,disposition=disposition,all_original_scopes_closed=True,B1_B2_A2_never_launched=True,
        retry_allowed=False,comparison_reference=None,comparison_gain_evaluated=False,prior_or_partial_rates_reused=False,
        quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(disposition=disposition,campaign=campaign,new_main=current)))

if __name__=='__main__':main()
