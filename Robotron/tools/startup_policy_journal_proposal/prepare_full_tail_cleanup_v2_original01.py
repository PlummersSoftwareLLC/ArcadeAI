"""Prepare a distinct immutable full-tail cleanup-v2 case; never launch it here."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'tools/startup_policy_journal_proposal'
R=G/'logs/managed-learning-20261015/run-26'
N1=R/'compiled32-policy-full-tail-real-original01-preparation-20261022'
N2=R/'compiled32-policy-full-tail-cleanup-v2-real-original01-preparation-20261022'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def main():
    h=load('_prepare_tail_helpers',B/'run_full_policy_startup_v3.py')
    assert h.pin(B/'run_full_policy_startup_v3.py')['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    assert not (N2/'job.json').exists() and not (N2/'execution-original01').exists()
    job=json.loads((N1/'job.json').read_text())
    assert h.pin(N1/'job.json')['sha256']=='8089988cb3d98946de3751ed73e8829a7f25b8fbae145bd6ad957faca15fe786'
    main_binding=h.pin(N2/'prospective-main-binding.json')
    assert main_binding['sha256']=='6789a94abfa3baf9036f590f55704f3680bd1a5f3e3bdc91e2b008f3741a185b'
    main=json.loads(h.checked(main_binding).read_text())
    assert main['supervision_policy']['sha256']=='9122be7de6387851dab2ce7f27485f5a7b147a27c74860e51884195059e0bb86'
    policy=json.loads(h.checked(main['supervision_policy']).read_text())
    preflight_pin=h.pin(N2/'main-preflight-original01/original-steady-main192-preflight-result.json')
    preflight=json.loads(h.checked(preflight_pin).read_text())
    assert preflight['status']=='PASS_CURRENT192_STEADY_SOURCE_RECIPE_FINITE_AUTOSAVE_FORWARD_CLOCKS'
    assert preflight['elapsed_s']>=60 and preflight['current_interval_recoveries']==0
    guard=R/'full-tail-final-review-marker-v2-integration-original01-preparation-20261022/original-three-final-review-marker-v2-independent-readback.json'
    guard_pin=h.pin(guard)
    assert guard_pin['sha256']=='5cc093de59b7da9280984c5644c2d5875475abd3f4a6465c5bcb9a91a940fc08'
    proof=json.loads(h.checked(guard_pin).read_text());assert proof['actual_payload_exit']==proof['actual_controller_exit']==0
    for entry in job['inputs']:h.checked(entry)
    h.package_inputs(job['source_package'])
    sup=load('_prepare_current_sup',h.checked(job['main_sources']['supervision']))
    window=load('_prepare_current_window',h.checked(job['main_sources']['window']))
    snapshot=sup.collect(policy)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as response:raw=response.read(1048577)
    assert len(raw)<=1048576
    api=json.loads(raw)
    current=sup.validate_snapshot(policy,snapshot,api['client_count'])
    assert current['full_capacity'] and not current['pending'] and not current['completed_episodes']
    window.owner_and_files(main)
    window.healthy(api,json.loads(h.checked(main['baseline_API']).read_text()),main['experiment'],time.time())
    assert 0<=time.time()-(G/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime<=360
    census=h.put(N2/'immediate-prelaunch-current192-census.json',snapshot)
    with (N2/'immediate-prelaunch-API.raw.json').open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    api_pin=h.pin(N2/'immediate-prelaunch-API.raw.json')
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=10)
    assert gpu.returncode==0 and job['gpu_uuid']not in gpu.stdout
    assert h.pin(job['lease']['path'])==job['lease']
    fd=os.open(job['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    ports=[19998,*range(20000,20032)]
    sockets=[]
    try:
        for port in ports:
            sock=socket.socket();sockets.append(sock);sock.bind(('127.0.0.1',port))
    finally:
        for sock in sockets:sock.close()
    assert h.pin(job['lease']['path'])==job['lease']
    private_preflight=h.put(N2/'original-private-GPU-coordinator-and-ports-preflight.json',dict(
        original_attempt=1,no_retry=True,GPU=gpu.stdout,GPU_exit=gpu.returncode,GPU_stderr=gpu.stderr,
        coordinator=job['lease'],coordinator_unlocked_without_mutation=True,all_private_ports_available=ports,
        main_census=census,main_API=api_pin,main192_healthy=True,main_runtime_changed=False,observed_unix_s=time.time()))
    runtime=h.pin(B/'run_compiled_full_tail32_v2.py')
    assert runtime['sha256']=='673d5cd6f50546f7571cbcccf17764c7a969e92d553e014e7abfed37cf577fbc'
    ctl_source=h.pin(B/'control_compiled_full_tail32_v2.py')
    assert ctl_source['sha256']=='6c82de8169446395c35485596e3d0648be31e0000ef9e940341ece3c36a8a67e'
    reviewer=h.pin(B/'read_compiled_full_tail32_original_v2.py')
    assert reviewer['sha256']=='6fe6bb2e90848c2f43cbe01e0d349055a8943a401bdcf060ee06baf26c39f6a4'
    wire=h.pin(B/'audit_full_tail_wire_v2.py')
    assert wire['sha256']=='cff5b71f6e8f8d5a7a51eeece9618d0ae55f8ec99f127940969cc13488fe9038'
    job.update(schema='robotron-compiled-full-tail32-original-v2',created_unix_s=time.time(),runtime=runtime,
        output=str(N2/'diagnostic-output-original01'),label='compiled-GPU0-all32-certified-full-tail-cleanup-v2-engineering-original01-20261022',
        main_binding=main_binding,sessions={str(s):secrets.token_hex(16)for s in job['actor_slots']},
        connections={str(s):secrets.token_hex(16)for s in job['actor_slots']},
        selected_change='Runtime-v2 preserves failed observations, waits on each original child after origin closure and seals outputs only after actual original writers and threads close. Separate fixed current main binding; failed v1 remains invalid.',
        expected='All32 original prospective starts admitted over the fixed90s and every admitted game completed, original exact policy and journals, actual MAME0/STOP/EOF and writer closure, main192 healthy. Engineering only; no quality qualification or speed gain.')
    job['historical_startup_acceptance_scope']=job.pop('acceptance_scope')
    new_proofs=[guard_pin,preflight_pin,private_preflight,
        h.pin(R/'full-tail-owned-cleanup-v2-contract-original01-preparation-20261022/original-four-owned-cleanup-v2-independent-readback.json'),
        h.pin(R/'full-tail-original-games-audit-contract-original01-preparation-20261022/original-six-full-tail-games-auditor-independent-readback.json'),
        h.pin(R/'full-tail-independent-wire-audit-contract-original01-preparation-20261022/original-four-full-tail-independent-wire-auditor-readback.json'),
        h.pin(R/'full-tail-v2-final-scope-contract-original01-preparation-20261022/original-six-final-scope-log-rule-failure-preserved.json'),
        h.pin(N1/'original-full-tail32-invalid-output-drift-and-postexit-closure-readback-v2.json')]
    job['cleanup_v2_original_evidence']=new_proofs
    job['prior_invalid_full_tail_case']=new_proofs[-1]
    job['prospective_independent_review_sources']=[reviewer,wire,h.pin(B/'audit_full_tail_games_v1.py')]
    extra=[runtime,ctl_source,reviewer,wire,h.pin(B/'audit_full_tail_games_v1.py'),main_binding,
        main['supervision_policy'],main['baseline_API'],census,api_pin,h.pin(__file__),*new_proofs]
    inputs={e['path']:e for e in job['inputs']}
    for entry in extra:
        if entry['path']in inputs:assert inputs[entry['path']]==entry
        inputs[entry['path']]=entry
    job['inputs']=list(inputs.values())
    for entry in job['inputs']:h.checked(entry)
    native=load('_prepare_runtime_v2',runtime['path']);native.validate_job(job)
    jp=h.put(N2/'job.json',job)
    scope=json.loads((N1/'precommitted-acceptance-scope.json').read_text())
    scope.update(schema='robotron-original-all32-compiled-full-tail-engineering-acceptance-v2',job=jp,
        first_actual_full_tail_attempt=False,first_actual_cleanup_v2_attempt=True,preflight=private_preflight,
        prior_invalid_full_tail_case=new_proofs[-1],cleanup_v2_original_evidence=new_proofs,created_unix_s=time.time())
    scope['completion']+=' Runtime-v2 must reap each original child with actual exit0, preserve all failed health observations, and seal each output only after original writer and thread closure; no appended output after final pins.'
    scope_pin=h.put(N2/'precommitted-acceptance-scope.json',scope)
    ctl=load('_prepare_ctl_v2',ctl_source['path'])
    argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',runtime['path'],
        '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']]
    config=dict(unit='robotron-compiled-full-tail32-integration-cleanup-v2-original01-20261022.service',
        output=str(N2/'execution-original01'),argv=argv,
        properties=scope['resources'].copy(),pins=[],observation_s=9720)
    config['properties']=[f'{k}={v}'for k,v in scope['resources'].items()if k!='observation_s']
    config['pins']=[ctl.pin(e['path'])for e in [*job['inputs'],jp,scope_pin]]
    cfg=h.put(N2/'controller-config.json',config);ctl.checked_config(cfg['path'])
    source_paths=dict(runtime=runtime['path'],control=ctl_source['path'],wire=wire['path'],
        games=str(B/'audit_full_tail_games_v1.py'),
        native_closure=str(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'),
        main_supervision=job['main_sources']['supervision']['path'],main_window=job['main_sources']['window']['path'],
        terminal_rom=str(G/'tools/confirmed_game_boundary_proposal/audit_confirmed_completed_leg_reviewed3.py'))
    review_job=dict(schema='robotron-original-full-tail32-independent-review-job-v1',
        output=str(N2/'independent-full-tail-review-original01'),native_job=jp,acceptance=scope_pin,
        controller_config=cfg,sources={key:h.pin(value)for key,value in source_paths.items()})
    review_job_pin=h.put(N2/'independent-review-job.json',review_job)
    review=load('_prepare_review_v2',reviewer['path']);review.validate_scope(job,jp,scope,config)
    commitment=h.put(N2/'original-cleanup-v2-case-precommit.json',dict(
        schema='robotron-original-cleanup-v2-full-tail-case-precommit-v1',native_job=jp,acceptance=scope_pin,
        controller_config=cfg,controller_source=ctl_source,review_job=review_job_pin,reviewer=reviewer,
        original_attempt=1,no_retry=True,prior_invalid_case_preserved=new_proofs[-1],new_original_evidence=new_proofs,
        main_runtime_changed=False,quality_qualified=False,promotion=False,learning_speed_gain_verified=False,
        created_unix_s=time.time()))
    print(json.dumps(dict(status='PREPARED_NOT_LAUNCHED',job=jp,config=cfg,precommit=commitment,
        main_LF=api['learner_frame_count'],main_TS=api['training_steps'],main_fps=api['fps'])))

if __name__=='__main__':main()
