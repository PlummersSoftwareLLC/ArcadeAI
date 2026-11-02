#!/usr/bin/env python3
"""Root-only metadata assembly; never starts a trainer or runs numerical code."""
import argparse, base64, copy, hashlib, json, os
from pathlib import Path

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=GAME/'logs/managed-learning-20261015/run-26'
D=Path(__file__).resolve().parent
RECOVERY=R/'accepted-newgame-failed-maintenance-forward-recovery-source-preparation-20261017/run_forward_recovery.py'
RECOVERY_SHA='b6d06f94c454cb4106aab0bf6316c62f9b85e134744f176f6389004e976f606e'
PHASE='ce4096_accepted_newgame_forward_recovery_20261017'

def require(value,message):
    if not value: raise RuntimeError(message)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--expected-source-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: assemble fresh immutable seventeen-field recovery job; no reads/actions');return
    require(args.expected_source_sha256==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'Builder source changed')
    require(hashlib.sha256(RECOVERY.read_bytes()).hexdigest()==RECOVERY_SHA,'Recovery source changed')
    import importlib.util, sys
    spec=importlib.util.spec_from_file_location('_root_recovery_job_builder',RECOVERY)
    recovery=importlib.util.module_from_spec(spec);sys.modules[spec.name]=recovery;spec.loader.exec_module(recovery)
    H=recovery.load_helper();adapter=H.load(H.ADAPTER,H.ADAPTER_SHA,'_root_recovery_builder_adapter');base=adapter.load_v4()
    output=R/'accepted-newgame-failed-maintenance-forward-recovery-20261017'
    names=['recovery-intent.json','root-actual-job.json','root-job-assembly-receipt.json']
    require(not output.exists() and all(not (D/name).exists() for name in names),'Recovery output/job must be new')
    def fixed(relative,digest):
        pin=base.fingerprint(R/relative,base.MAX_JSON)
        require(pin['sha256']==digest,'Fixed original metadata changed: '+relative)
        H.immutable(base,pin);return pin
    failure=fixed('accepted-newgame-maintenance-failed-reconnect-root-evidence-20261017/root-failed-maintenance-evidence-manifest.json','c80cb82f332fb680989b5d6fd7f607f180e90bfa2956a3b195a8aa6cf24b7c07')
    failed_job=fixed('accepted-newgame-healthy-CE-maintenance-root-preparation-20261017/root-actual-job.json','a7efb0e1f69580adbfb10989e4986fb83eabbc76b5dff31d045727b2c0d20990')
    failed_result=fixed('accepted-newgame-healthy-CE-maintenance-20261017/result.json','4b69a18fc7b7a2ad83c54142d0c0712092616f1052f1b78ba255cc53177d5207')
    startup=fixed('accepted-newgame-healthy-CE-maintenance-20261017/CE-startup-CPU-readonly.json','0e30cfd830c61af36c7dedd7b0f35b32ebf5da5a8c29d1cdcb730ccc54c0eddd')
    cpu=fixed('accepted-newgame-failed-maintenance-newest-stopped-CPU-root-preparation-20261017/actual-newest-stopped-CPU-job.json','defbf8d1f1160b05766bdf2d5fa99a40c330b6a500a29a3994a74157d06c8eff')
    report=fixed('accepted-newgame-failed-maintenance-newest-stopped-CPU-root-execution-20261017/newest-stopped-CPU-report-readonly.json','bafd03847686875a4870886745baf37c38f295f8b737e8546332e98b889c7faa')
    release=fixed('accepted-newgame-failed-maintenance-newest-stopped-CPU-root-execution-20261017/root-original-newest-stopped-CPU-result-and-owned-release.json','3e90385ae2883edd5a8076b2463b56dadf145f7cced5c51095214ddc290c2b5b')
    original=base.read_json(failed_job);failed=base.read_json(failed_result);numeric_job=base.read_json(cpu)
    require(numeric_job['source']['sha256']=='ce9edbbdd7a3c8520d68e26b5a1e2f994274b826fdbbdc4830909678bb351f30','Wrong actual newest checkpoint')
    settings=copy.deepcopy(original['transition']['settings_lifecycle'])
    settings['initial']=base.fingerprint(GAME/'models_dqn/game_settings.json',base.MAX_JSON)
    require(base.read_json(settings['initial'])==settings['parsed_values'] and settings['policy']=='same_bytes_after_owned_stop_only','Held settings values/policy changed')
    base.SettingsLifecycle(settings,str(GAME/'models_dqn'))
    completed=base.fingerprint(GAME/'models_dqn/managed_save.request.json.completed',base.MAX_JSON)
    require(not (GAME/'models_dqn/managed_save.request.json').exists(),'Unexpected pending model request')
    dropin_path=Path(original['transition']['original_dropin']['path'])
    dropin_pin=base.fingerprint(dropin_path,base.MAX_SOURCE);dropin_bytes=dropin_path.read_bytes();base.pin(dropin_pin,base.MAX_SOURCE)
    require(hashlib.sha256(dropin_bytes).hexdigest()==dropin_pin['sha256'] and b'16bf255adca0edaefd7dc1f447cfd5ca2494fcf013d233a5f354693d32f22e6a' in dropin_bytes,'Current failed-owner91 phase mismatch')
    dropin=dict(path=str(dropin_path),content_base64=base64.b64encode(dropin_bytes).decode(),mode=int(dropin_pin['identity']['mode'],8))
    tag='CE4096-accepted-newgame-forward-recovery-startup-20261017'
    for suffix in ('.pt','.pt.tmp','.pt.bak'):
        require(not (GAME/'models_dqn/managed-checkpoints'/(tag+suffix)).exists(),'Startup checkpoint name already used')
    intent=dict(schema='robotron-accepted-newgame-failed-maintenance-forward-recovery-intent-v1',failed_job=failed_job,failed_result=failed_result,
        failure_evidence=failure,owner=failed['failed_new_CE_retired'],newest_checkpoint=adapter.triple(numeric_job['source']),phase_id=PHASE,
        no_maintenance_retry=True,no_rollback=True,target_batch_size=4096,target_lr_scale=.5,strict_runtime_s=60,ready_s=600,
        historical_binding_seed=dict(failed_job=failed_job,scope='original transition.before is historical only; retired-owner absence is checked by recovery'),
        original_failure_preserved=True,quality_qualification=False)
    intent_pin=base.publish(D/names[0],intent)
    job=dict(schema=recovery.SCHEMA,activation_authorized=True,failure_evidence=failure,failed_result=failed_result,failed_job=failed_job,
        failed_startup_CPU=startup,newest_CPU_job=cpu,newest_CPU_report=report,newest_CPU_release=release,recovery_intent=intent_pin,
        phase_id=PHASE,request_id='accepted_newgame_failed_maintenance_forward_20261017',startup_tag=tag,output_directory=str(output),
        current_completed_request=completed,settings_lifecycle=settings,current_dropin=dropin)
    recovery.validate(job,base,adapter,H)  # Root-only metadata/hash validation; no runtime or numerical invocation.
    base.pin(settings['initial'],base.MAX_JSON);base.pin(completed,base.MAX_JSON);base.pin(dropin_pin,base.MAX_SOURCE)
    job_pin=base.publish(D/names[1],job)
    receipt=base.publish(D/names[2],dict(status='PASS_METADATA_ASSEMBLY_AND_SEALED_VALIDATE',job=job_pin,recovery_intent=intent_pin,
        builder=base.fingerprint(Path(__file__),base.MAX_SOURCE),recovery=base.fingerprint(RECOVERY,base.MAX_SOURCE),
        current_dropin_full_identity=dropin_pin,recovery_executed=False,new_owner=None,quality_qualification=False))
    print(json.dumps(dict(status='PASS',job=job_pin,assembly_receipt=receipt),allow_nan=False))

if __name__=='__main__': main()
