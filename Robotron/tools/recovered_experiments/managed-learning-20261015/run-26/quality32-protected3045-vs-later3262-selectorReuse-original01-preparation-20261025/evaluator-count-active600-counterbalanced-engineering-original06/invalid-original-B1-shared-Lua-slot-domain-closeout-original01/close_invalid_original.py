"""Record the failed original06 B1 and closed ABBA study; no process actions.

Requires the separately root-adopted terminal recovery already complete. Reuses
the original scope/resource verifier, but never its successful600s case path.
"""
import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
E=HERE.parent
N=E.parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
    original=load('_close_original06_B1',N/'close_shared64_original06_case_v1.py')
    c=original.CloseOriginal('02-B1-capacity64')
    h=c.h;out=Path(c.job['output'])
    result_pin=h.pin(out/'result.json')
    assert result_pin['sha256']=='9e3c9d2c8e234aaada94226aeeb0a377c056dc45a38edb9deeddebc182d69e53'
    r=c.read(result_pin)
    assert r['complete'] is r['quality_qualified'] is False
    assert r['active_start'] is r['active_end'] is r['active_frame_rate'] is None
    assert r['errors'][0]=="ValueError('Original actor exited nonzero or before host-authorized drain')"
    assert r['all_original_threads_stopped'] is r['original_lease_released'] is r['immutable_inputs_unchanged'] is True
    assert r['original_unsealed_journal_paths']==[] and len(r['original_slots'])==64
    native=c.scope(h.pin(c.directory/'execution-original01/root-original-identity.json'),
        h.pin(HERE/'root-original-result-and-owned-release.json'),c.record['launch_config'],1,12,24<<30,22260,512,30,True)
    life=c.read(r['main_observer_lifecycle'])
    observer=c.scope(life['worker_owner'],life['worker_closure'],life['worker_config'],0,2,4<<30,22260,128,5)
    assert life['original_scope_released'] is life['all_owned_worker_and_controller_processes_reaped'] is True
    worker_outcome=c.read(life['worker_outcome'])
    assert worker_outcome['success'] is True and worker_outcome['all_writer_threads_stopped'] is True
    assert r['main_health_failure'] is None
    rows=[]
    for slot in range(4096,4160):
        row=r['original_slots'][str(slot)];files=row['files']
        assert c.control.pin(files['actor-stdout.txt']['path'])['sha256']==files['actor-stdout.txt']['sha256']
        assert row['outputs_sealed_after_original_writer_closure'] is True and row['original_unsealed_output_paths']==[]
        assert c.control.pin(files['actor-stderr.txt']['path'])['sha256']==files['actor-stderr.txt']['sha256']
        assert original.birth(row['pid'])!=row['birth']
        # Verify all original actor outputs, preserving true exit codes.
        for pin in files.values():h.checked(pin)
        stdout=Path(files['actor-stdout.txt']['path']).read_bytes()
        stderr=Path(files['actor-stderr.txt']['path']).read_bytes()
        lifetime=[json.loads(line) for line in c.read(files['lifecycle.jsonl'],False).splitlines()]
        item=dict(slot=slot,pid=row['pid'],birth=row['birth'],actual_exit=row['actual_exit'],
            stdout=files['actor-stdout.txt'],stderr=files['actor-stderr.txt'],producer=files['producer.jsonl'],lifecycle=files['lifecycle.jsonl'],
            integer_contract_failure=b'startup integer outside contract' in stdout,
            prefix_finish_failure=b'FULL_STARTUP_ADAPTER_FAILURE:finish' in stderr,
            lifecycle_faults=[v for v in lifetime if v['kind']=='fault'],
            closed=[v for v in lifetime if v['kind'] in ('closed','prefix_closed')])
        if slot>=4128:
            assert item['integer_contract_failure'] and files['producer.jsonl']['bytes']==files['lifecycle.jsonl']['bytes']==0
        rows.append(item)
    reap=r['original_post_origin_child_reap']
    assert reap['all_original_children_reaped'] is True and reap['unknown_slots']==[]
    assert reap['signals_sent'] is reap['exit_statuses_normalized'] is False
    for pin in r['journal'].values():h.checked(pin)
    lua=h.pin(G/'tools/startup_policy_journal_proposal/full_startup_wire_v2.lua')
    text=h.checked(lua).read_text()
    assert text.count('integer(a.slot,4096,4127)')==1
    actor_lua=c.job['lua'];actual=h.checked(actor_lua).read_text()
    assert str(G/'tools/startup_policy_journal_proposal/full_startup_wire_v2.lua') in actual
    assert 'self.initialized_sequence>0' in text and 'self.first_play_sequence>self.initialized_sequence' in text
    for name in ('03-B2-capacity64','04-A2-control'):
        for sub in ('execution-original01','diagnostic-output-original01','original-native-launch-preflight.json'):
            assert not(E/name/sub).exists()
    resources=c.free_resources()
    monitor=N/'evaluator-count-active600-counterbalanced-engineering-original04/postfailure-supervised-slot2-main-reconciliation-original01/current-main-readonly-monitor.py'
    p=subprocess.run(['/usr/bin/python3.12','-I','-B',str(monitor)],capture_output=True,text=True,timeout=30)
    assert p.returncode==0,p.stderr
    current=json.loads(p.stdout)
    assert current['client_count']==192 and current['held_inputs']==197
    assert current['bound192_actor_identities_and_affinities_verified'] is True
    proof=dict(schema='robotron-original06-B1-shared-Lua32-domain-invalid-closeout-v1',
        status='INVALID_ORIGINAL_B1_SHARED_LUA_SLOT_DOMAIN_CLOSED',created_unix_s=time.time(),source=h.pin(__file__),
        native_result=result_pin,native_scope=native,observer_scope=observer,
        original_observer_outcome=life['worker_outcome'],original_main_report=r['main_health_report'],
        all_native_and_observer_six_descriptors_resources_argv_invocations_and_release_verified=True,
        all64_actor_outputs_SHA_and_sealing_and_exact_PID_birth_absence_verified=True,
        actual_MAME_exits=dict(collections.Counter(str(v['actual_exit']) for v in rows)),actor_details=rows,
        original_post_origin_reap=reap,resources=resources,
        loaded_lua=actor_lua,actual_adapter=lua,all32_highslots_rejected_before_first_frame=True,
        failure_mechanism='Actual boot Lua loads unchanged adapter with slot4096..4127 bound. All32 highslots4128..4159 report startup integer outside contract with empty producer/lifecycle. The64 job never achieved its all64 startup or active600 anchor. Low-slot finish_failed at prefix1200 and later origin EOF/inference errors are retained; no quality or capacity outcome can be inferred.',
        causal_limits='Direct source and all32 original high-slot logs establish adapter-domain rejection. Historical cgroup memory.events are unavailable after cgroup removal; no zero-OOM claim. Root native actual terminal is exit-code1, not an OOM-kill result. No individual later error timing is claimed as the first wall-clock event.',
        new_main=current,current_monitor=h.pin(monitor),all197_current_held_inputs_and_main192_unchanged=True,
        B2_A2_never_launched=True,valid_A1_preserved=h.pin(E/'01-A1-control/independent-original-capacity64-case-closeout.json'),
        reference_rate_reused=False,comparison_gain_evaluated=False,quality_qualified=False,
        failed_original_preserved=True,retry_allowed=False,main_recipe_changed=False)
    disposition=h.put(HERE/'independent-invalid-original-B1-and-study-closeout.json',proof)
    campaign=h.put(HERE/'original06-ABBA-invalid-disposition.json',dict(
        schema='robotron-capacity64-invalid-original-ABBA-disposition-v1',status=proof['status'],
        original_attempt=6,disposition=disposition,all_original_scopes_closed=True,B2_A2_never_launched=True,
        retry_allowed=False,valid_originals=1,comparison_gain_evaluated=False,prior_or_partial_rates_reused=False,
        quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(disposition=disposition,campaign=campaign,new_main=current)))

if __name__=='__main__':main()
