"""Verify the latest model/optimizer with restored durable replay, on CPU.

The older replay backup is explicitly recorded; no pre-outage trajectory or
uninterrupted experience collection is claimed. Produces an exact before-update
manifest for the existing startup hold, without changing canonical sources.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def require(value, message):
    if not value:raise ValueError(message)


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def configure_recipe(recipe):
    require(recipe == dict(batch_size=4096, n_step=3, max_samples_per_frame=8),
            'Exact selected4096/n3/cap8 recipe required')
    os.environ.update(DQN_BATCH_SIZE=str(recipe['batch_size']), DQN_N_STEP=str(recipe['n_step']),
                      DQN_MAX_SAMPLES_PER_FRAME=str(recipe['max_samples_per_frame']))


def execute(args):
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and 'torch' not in sys.modules,
            'Fresh CPU-only verifier required')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,
            'Original verifier source changed')
    raw=args.job.read_bytes();require(hashlib.sha256(raw).hexdigest()==args.job_sha256,'Original CPU job changed')
    job=json.loads(raw);G=Path(job['game_root'])
    h=load('_reboot_verify_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    def read(pin):return json.loads(h.checked(pin).read_bytes())
    require(job['schema']=='robotron-reboot-exact-restoration-CPU-job-v1'
            and job['original_attempt']==1 and job['no_retry'] is True,'One original recovery verification required')
    for pin in job['inputs']:h.checked(pin)
    offline=load('_reboot_verify_offline',h.checked(job['restore_source']))
    offline.offline_units()
    restored=read(job['restore_report']);require(restored['status']=='DURABLE_RING_RESTORED_AND_REREAD_VERIFIED'
        and restored['all_data_verified_before_meta_commit'] is True
        and len(restored['restored_files'])==10,'Actual completed checksum restoration required')
    for row in restored['restored_files']:
        require(offline.regular(row['target'])==row['destination'] and row['full_destination_reread_verified'] is True,
                'Restored ring changed after its complete checksum verification')
    require(offline.regular(restored['committed_meta']['path'])==restored['committed_meta']['identity'],
            'Restored ring metadata changed')
    directory=Path(job['output']);directory.mkdir(mode=0o700);started=time.monotonic()
    fields=dict(line.split('=',1)for line in subprocess.check_output(
        ['systemctl','--user','show',job['unit']],text=True,timeout=10).splitlines()if '='in line)
    expected=dict(Id=job['unit'],MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],
        CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),RuntimeMaxUSec='10min',Restart='no',NRestarts='0')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual bounded CPU scope differs')
    report=dict(schema='robotron-stopped-full-training-state-CPU-result-v1',status='RUNNING',
        original_job=h.pin(args.job),actual_scope=fields,source=h.pin(Path(__file__).resolve()),
        prior_boot_interrupted=True,continuous_replay_since_checkpoint_claimed=False,
        quality_qualified=False,promotion=False)
    try:
        launcher=load('_reboot_actual_checkpoint_CPU',h.checked(job['launcher']))
        configure_recipe(job['recipe'])
        launcher.prepare(Path(job['checkpoint']['path']),directory/'resume-records',directory/'checkpoint-CPU.json',8)
        checkpoint_CPU=json.loads((directory/'checkpoint-CPU.json').read_bytes())
        require(checkpoint_CPU['checkpoint']=={k:job['checkpoint'][k]for k in ('path','sha256','bytes')},
                'Actual CPU checkpoint differs from preserved latest state')
        import torch
        import numpy as np
        torch.set_num_threads(2)
        saved=torch.load(job['checkpoint']['path'],map_location='cpu',weights_only=False,mmap=True)
        tools=load('_reboot_exact_manifest_tools',h.checked(job['manifest_tools']))
        strict=load('_reboot_existing_payload_predicates',h.checked(job['strict_payload_source']))
        descriptors=load('_reboot_existing_ring_bank_descriptors',h.checked(job['bank_descriptors']))
        snapshot=descriptors.stopped_state(job['bank_spec'])
        require(snapshot['ring']['meta']['size']==6000000,'Full restored ring required')
        payload_keys=('online_state_dict','target_state_dict','optimizer_state_dict','grad_scaler_state_dict')
        scalars={key:copy.deepcopy(value)for key,value in saved.items()
                 if key not in payload_keys and key!='priority_metric_phase'}
        require(set(scalars)==set(job['saved_scalar_keys']),'Complete exact saved scalar payload required')
        phase=copy.deepcopy(saved['priority_metric_phase'])
        require(phase['metric']=='ce'and phase['valid']is True and phase['invalid_reason'] is None,
                'Valid saved CE priority phase required')
        require(all(value==6.25e-6 for value in checkpoint_CPU['saved_optimizer_lrs']),
                'Preserve actual saved optimizer learning rate')
        print(json.dumps(dict(phase='VERIFYING_COMPLETE_CURRENT_BANKS_AND_RING_SCALARS')),flush=True)
        banks=strict.bank_payloads(snapshot,np,tools)
        ring_scalars=strict.ring_scalar_payloads(snapshot,np,tools)
        priority=snapshot['ring']['arrays']['priorities']
        scan=strict.scan_array(priority['path'],priority,np,positive=True)
        require(snapshot['ring']['meta']['max_priority']>=scan['maximum'],'Stored maximum priority is inconsistent')
        require(descriptors.stopped_state(job['bank_spec'])==snapshot,'Ring or banks changed during CPU verification')
        for row in restored['restored_files']:
            require(offline.regular(row['target'])==row['destination'],'Restored ring changed during CPU verification')
        for pin in job['inputs']:h.checked(pin)
        offline.offline_units();require(not torch.cuda.is_initialized(),'CPU verification initialized CUDA')
        manifest=dict(schema='robotron-stopped-full-training-state-restoration-manifest-v1',status='VERIFIED_STOPPED_STATE',
            original_job=h.pin(args.job),source=h.pin(Path(__file__).resolve()),manifest_tools=job['manifest_tools'],
            checkpoint=job['checkpoint'],verification_copy=job['preserved_checkpoint'],owner=job['prior_main_owner'],
            stopped_authority=job['reboot_observation'],
            original_terminal_verification=dict(prior_boot_interrupted=True,original_normal_exit0=False,
                current_trainer_and_fleet_offline=True,not_a_scientific_retry=True),
            checkpoint_payload={key:tools.typed_tree(saved[key],torch)for key in payload_keys},saved_scalars=scalars,
            priority_metric_phase=phase,ring_and_banks=snapshot,
            ring_continuity=dict(recovered_from_durable_backup=True,continuous_with_latest_checkpoint=False,
                backup_checkpoint_sha256=restored['restored_replay_belongs_to_checkpoint_sha256'],
                actual_ring_restore=job['restore_report'],new_exposure_epoch_required=True),
            ring_scalar_payload=ring_scalars,
            ring_priorities=dict(file=ring_scalars['priorities']['file'],payload=ring_scalars['priorities']['payload'],scan=scan),
            bank_payload=banks,ring_states_and_next_states_full_payload_hashed=True,
            full_ring_checksum_authority=job['restore_report'],all_bank_fields_full_files_hashed=True,
            RNG_state_saved=False,per_client_or_MAME_RAM_restored=False,startup_restore_verified=False,
            execution_or_actor_admission_authorized=False,quality_qualified=False,promotion=False)
        mp=h.put(directory/'restoration-manifest.json',manifest)
        report.update(status='PASS',restoration_manifest=mp,checkpoint=job['checkpoint'],
            full_latest_model_optimizer_scaler_and_scalars_verified=True,exact_ring_and_bank_descriptors_verified=True,
            actual_checkpoint_CPU=h.pin(directory/'checkpoint-CPU.json'),CUDA_initialized=False,
            all_training_units_remained_offline=True,elapsed_s=time.monotonic()-started)
        result=h.put(directory/'cpu-verification.json',report)
        print(json.dumps(dict(status='PASS',report=result,restoration_manifest=mp)),flush=True);return 0
    except BaseException as error:
        report.update(status='FAIL',error=repr(error),elapsed_s=time.monotonic()-started)
        h.put(directory/'verification-error.json',report);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--job',type=Path);p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if a.execute:raise SystemExit(execute(a))
    print('PLAN_ONLY_NO_READS_OR_ACTIONS')
