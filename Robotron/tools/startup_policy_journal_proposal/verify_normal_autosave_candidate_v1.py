"""One strict CPU check of a preserved normal-autosave candidate; inert by default.

Reuse unchanged finite/model/Adam/scaler and saved-phase validators. Acquisition
is a completed normal autosave, not a managed save, restore or coherent anchor.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'tools/startup_policy_journal_proposal'
CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count')

def require(value,message):
    if not value:raise ValueError(message)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job')
    parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    h=load('_normal_candidate_helpers',B/'run_full_policy_startup_v3.py')
    require(h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1','Helper changed')
    require(h.pin(__file__)['sha256']==args.source_sha256,'Verifier source changed')
    jp=h.pin(args.job);require(jp['sha256']==args.job_sha256,'Job changed')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and not os.environ.get('LD_PRELOAD')
        and not os.environ.get('PYTHONPATH'),'CPU isolation required')
    job=json.loads(h.checked(jp).read_text())
    require(job['schema']=='robotron-preserved-normal-autosave-candidate-CPU-job-v1','Exact candidate CPU job required')
    output=Path(job['output']);require(not output.exists()and output.parent==Path(jp['path']).parent,'Fresh exact output required')
    output.mkdir(mode=0o700)
    report=dict(schema='robotron-preserved-normal-autosave-candidate-CPU-result-v1',status='RUNNING',
        job=jp,source=h.pin(__file__),candidate=job['candidate'],original_attempt=1,no_retry=True,
        quality_qualified=False,promotion=False,main_runtime_changed=False,
        actual_restore_or_optimizer_step=False,learning_speed_gain_verified=False,
        acquisition_scope='Preserved completed normal autosave; source path is historical after its ordinary replacement. No managed save or coherent replay/optimizer anchor claim.')
    try:
        for entry in job['inputs']:h.checked(entry)
        acquisition=json.loads(h.checked(job['acquisition']).read_text())
        require(acquisition['candidate']==job['candidate']and acquisition['source']['sha256']==job['candidate']['sha256']
            and acquisition['source']['bytes']==job['candidate']['bytes']
            and acquisition['source_original_identity_unchanged_through_copy']is True
            and acquisition['independent_readonly_inode']is True
            and acquisition['manual_save_requested']is acquisition['main_runtime_changed']is False,
            'Original normal-autosave copy differs')
        require(job['candidate']['identity']['mode']=='0o444'and job['candidate']['identity']['nlink']==1,
            'Readonly independent candidate required')
        prior_job=json.loads(h.checked(job['prior_verified_CPU_job']).read_text())
        prior=json.loads(h.checked(job['prior_verified_CPU_report']).read_text())
        require(prior['status']=='PASS'and prior['sha256']==job['protected_policy']['sha256']
            and prior_job['source_control_context']==job['source_control_context'],
            'Actual prior protected-policy verification/context differs')
        phase=load('_normal_candidate_phase_helpers',h.checked(job['phase_verifier']))
        require(job['phase_verifier']['sha256']=='14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5',
            'Unchanged saved-phase verifier required')
        historical=phase.load_base()
        base,specialization=phase.select_recipe_base(dict(source_control_context=job['source_control_context'],
            phase_snapshot=prior_job['phase_snapshot']),historical)
        report.update(bound_files={},recipe_specialization=specialization)
        base.DIRECTORY=output
        base.check_context(dict(source_control_context=job['source_control_context'],experiment=prior_job['experiment']),report)
        floor={k:prior['clocks'][k]for k in CLOCKS}
        after=json.loads(h.checked(acquisition['main_health_after']).read_text())['API']
        def saved_phase(checkpoint,evidence):
            phase.verify_phase(checkpoint,evidence,prior_job['phase_snapshot']['expected_phase'],floor,floor,
                'resume',prior['saved_priority_metric_phase'])
            require(checkpoint['learner_frame_count']-floor['learner_frame_count']>=8_000_000
                and checkpoint['optimized_samples']-floor['optimized_samples']>=64_000_000,
                'Next candidate needs additional learner and optimized exposure')
            require(all(checkpoint[k]<=after[k]for k in CLOCKS),'Saved clocks exceed the actual postcopy live main')
        base.validate_checkpoint(h.checked(job['candidate']),floor,report,metadata_callback=saved_phase)
        require(report['cuda_initialized']is False and report['visible_cuda_devices']==0,'Numerical CPU scope escaped')
        report['additional_saved_work_from_protected']={k:report['clocks'][k]-floor[k]for k in CLOCKS}
        report['Adam_logical_step_difference_from_protected']=report['logical_training_steps_minus_adam_step']-prior['logical_training_steps_minus_adam_step']
        for entry in job['inputs']:h.checked(entry)
        require(h.pin(args.job)==jp and h.pin(__file__)==report['source'],'Original job/source changed')
        report.update(status='PASS',CPU_verified=True,phase_metadata_verified=True,
            scope='Strict finite tensors/scalars; exact online/target geometry and support; saved Adam slots, LR/recipe, scaler, four clocks and unchanged phase lineage. No policy quality, speed, optimizer restoration or main mutation claim.')
    except Exception as error:
        report.update(status='FAIL',CPU_verified=False,error=repr(error),traceback=traceback.format_exc())
    report['ended_unix_s']=time.time()
    receipt=h.put(output/'cpu-verification.json',report)
    print(json.dumps(dict(status=report['status'],report=receipt,clocks=report.get('clocks'),error=report.get('error'))),flush=True)
    return 0 if report['status']=='PASS'else 1

if __name__=='__main__':sys.exit(main())
