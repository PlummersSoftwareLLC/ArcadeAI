"""Concrete installed-CE trial02 preparation; no arming or runtime mutation."""
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time

REPO=Path('/home/dave/source/repos/ArcadeAI'); GAME=REPO/'Robotron'
RUN=GAME/'logs/managed-learning-20261015/run-26'
SRC=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/live_one_trial_installed_ce_revision2_proposal'
ACQ=RUN/'preKL-insurance-20261017T124608Z-root-acquisition'
OUT=RUN/'rawKL-trial02-final-root-preparation-20261017'
MANIFEST='f6350a192c3e87b0d2c45bc395bccd9a428b3420d824c7d2d419924b3184709c'
ADAPTER='fd4e9d7b9b562c2bd6c663b9651d02b4167a3f552fcacb71cb8571440f3e9bf5'

def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
def pin(path):
    path=Path(path)
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        before=identity(os.fstat(stream.fileno())); digest=hashlib.file_digest(stream,'sha256').hexdigest()
        assert before==identity(os.fstat(stream.fileno()))==identity(path.lstat()),path
    return dict(path=str(path),sha256=digest,bytes=before['bytes'],identity=before)
def save(name,value,raw=False):
    path=OUT/name
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=raw);stream.write('\n');stream.flush()
        os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(OUT,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return pin(path)
def load(path,digest,name):
    assert pin(path)['sha256']==digest
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-review',type=Path,required=True);parser.add_argument('--source-review-sha256',required=True)
    parser.add_argument('--cross-review',type=Path,required=True);parser.add_argument('--cross-review-sha256',required=True)
    args=parser.parse_args()
    manifest=pin(SRC/'preparation-manifest.json');assert manifest['sha256']==MANIFEST
    selected=json.loads((SRC/'preparation-manifest.json').read_text())
    for name,expected in selected['files'].items():
        actual=pin(SRC/name);assert actual['sha256']==expected['sha256'] and actual['bytes']==expected['bytes'] and actual['identity']['mode']=='0o444'
    reviews=[]
    for path,digest in [(args.source_review,args.source_review_sha256),(args.cross_review,args.cross_review_sha256)]:
        value=pin(path);assert value['sha256']==digest and value['identity']['mode']=='0o444';reviews.append(value)
    guards=RUN/'optional-rawKL-installed-CE57-guards-root-execution-reviewed1-20261017/root-result-review-and-release.json'
    result=json.loads(guards.read_text());assert result['status']=='PASS' and result['test_methods']==57 and result['source_pins_held']
    a=json.loads((RUN/'rawKL-trial01-activation-20261017/root-job.json').read_text())
    core=json.loads((RUN/'rawKL-trial01-final-root-preparation-20261017/trial-core-FINAL.json').read_text())
    adapter=load(SRC/'run_raw_kl_transition.py',ADAPTER,'_root_trial02_adapter');base=adapter.load_v4()
    for key in ['v4','live_host','metrics','identity','protection','bank_state','phase_script','phase_strict','ancestor_adapter','horizon']:
        base.pin(a['helper_pins'][key],base.MAX_SOURCE)
    sys.path.insert(0,str(GAME/'tools'));sys.dont_write_bytecode=True
    primitives=base.load_module(a['helper_pins']['live_host']['path'],'_root_trial02_primitives')
    class Host(primitives.LiveHost):
        def runtime_dropin(self):return Path(a['original_dropin']['path'])
    host=Host(a['trainer_unit'],a['fleet_unit']);before=host.describe()
    prior=json.loads((RUN/'rawKL-trial01-forward-CE-repair-root-terminal-and-health-20261017/fresh-owned-main-and-all192-health.json').read_text())
    assert before==prior['binding'],'Current CE ownership/source/control changed since completed recovery'
    assert before['trainer']['MainPID']=='511524'
    host.adopt_initial(before);host.metric_host.configure_logs(before['bindings']['logs']);row=host.capture()
    plan=dict(batch_size=4096,replay_cap=8,initial_snapshot=dict(csv=a['baseline_csv']),
        exposure_identity={name:primitives.metrics.exposure_key(row['exposure'][name]) for name in ('optimizer','replay')})
    assert not primitives.metrics.api_issues(row,plan)
    assert all(sorted(os.sched_getaffinity(actor['pid']))==a['actor_masks'][str(actor['pid'])] for actor in before['bindings']['actors'])
    assert host.metric_host.mask(before['bindings']['worker'])==a['worker_mask']
    current_dropin=host._dropin_bytes();assert current_dropin is not None
    verifier=json.loads((ACQ/'CPU-root-preparation/verified-python-binding-and-context.json').read_text())
    insurance=pin(ACQ/'CPU-root-preparation/insurance-CPU-readonly-report.json')
    proof=base.read_json(insurance);assert proof['root_job']['insurance']['trainer']['pid']==511524
    assert proof['status']=='PASS' and proof['mode']=='insurance'
    base.validate_python_binding(verifier,insurance,hash_executable=True)
    repair_result=json.loads((RUN/'rawKL-trial01-forward-CE-repair-20261017/result.json').read_text())
    assert repair_result['status']=='READY_CE_FORWARD_REPAIR' and not repair_result['manual_recovery_required']
    running=repair_result['startup']['phase'];assert running['expected']['metric']=='ce'
    source_hashes=before['bindings']['source_hashes']
    assert all(source_hashes[str(GAME/'Scripts/dqn'/name)]==value for name,value in adapter.CANDIDATE.items())
    banks=base.load_module(a['helper_pins']['bank_state']['path'],'_root_trial02_banks');spec=a['bank_spec']
    live=dict(scope='Live as-of selected immutable bank descriptors and ring directory; not a stopped/memory equality proof',
        ring_directory=banks.directory_identity(spec['ring']),
        banks={name:banks.bank_state(name,Path(spec['model_dir'])/('robotron_dqn_latest_replay_'+name),spec['bank_strides'][name],spec['state_size'],spec['episode_capacity']) for name in ('hof','ephof')},
        actual_stopped_descriptors=None,actual_startup_maps=None)
    OUT.mkdir(mode=0o700)
    health=save('fresh-current-CE-owner192-health.json',dict(binding=before,API=row),raw=True)
    storage=save('live-storage-asof-descriptors.json',live)
    source_peer=pin(RUN/'preKL-current511524-insurance-independent-saved-review-20261017/review-receipt.json')
    prerequisites=save('root-preparation-prerequisites.json',dict(manifest=manifest,source_reviews=reviews,
        actual57_guards=pin(guards),current_owner_insurance=insurance,current_owner_insurance_saved_review=source_peer,
        current_owner_python_binding=pin(ACQ/'CPU-root-preparation/actual-v4-python-binding-readonly-PASS.json'),
        fresh_health=health,storage_asof=storage,previous_trial01_failed=pin(RUN/'rawKL-trial01-controller-20261017/result.json'),
        completed_CE_repair=pin(RUN/'rawKL-trial01-forward-CE-repair-independent-saved-result-review-20261017/review-receipt.json'),
        prepared_monotonic_s=time.monotonic(),scope='Read-only preparation and owned log publication; no arming, actors, trainer or source mutation'))
    a.update(schema=adapter.SCHEMA,mode='activate_kl',before=before,sources=[],
        baseline_csv=row['csv'],output_directory=str(RUN/'rawKL-trial02-activation-20261017'),
        phase_id='kl_raw_priority_8M_20261017_trial02',request_id='rawkl_trial02_activate_20261017',startup_tag='rawkl-startup-20261017-trial02',
        completed_dormant_capture=None,running_phase=running,ending_proof=None,verifier=verifier,
        insurance_verification=insurance,insurance_receipt=pin(ACQ/'saved-insurance-receipt.json'),
        current_completed_request=pin(GAME/'models_dqn/managed_save.request.json.completed'),
        original_dropin=dict(path=a['original_dropin']['path'],content_base64=base64.b64encode(current_dropin).decode(),mode=0o644))
    assert json.loads(Path(a['current_completed_request']['path']).read_text())==dict(tag='preKL-insurance-20261017T124608Z')
    a['settings_lifecycle']['initial']=pin(GAME/'models_dqn/game_settings.json')
    a['helper_pins']['controller']=pin(SRC/'run_raw_kl_transition.py')
    a['static_pins'].extend([manifest,*reviews,pin(guards),prerequisites,source_peer])
    core.update(mode='activate_kl',phase_id=a['phase_id'],trial_id='raw_kl_sequential_8M_20261017_trial02',
        status='FINAL_PRECOMMITTED_ROOT_AUTHORIZED',activation_authorized=True,preparation=prerequisites,
        previous_trial01=dict(status='FAILED_INVALID',result=pin(RUN/'rawKL-trial01-controller-20261017/result.json'),
            no_candidate=True,not_retried_or_relabelled=True,one_KL_startup_update_preserved_in_forward_CE_state=True),
        installed_source_transition=dict(sources=[],running_CE_phase=running,current_CE_owner=proof['root_job']['insurance']['trainer']),
        execution_envelope=dict(controller_runtime_s=7200,deadline_runtime_s=6000,scope='Includes fixed KL3600 ceiling and post-absence verification/CE return; no KL extension'))
    core['future_immutable_core_bindings'].update(candidate5_sources=a['candidate_sources'],
        control_and_unit_overrides=dict(control_hashes=before['bindings']['control_hashes'],unit_files=before['unit_files'],environment=before['environment'],dedicated_phase_override=a['original_dropin']),
        fresh_before_trainer_and_all192_actor_identities=before,
        insurance_source_copy_CPU=dict(source=proof['root_job']['source'],copy=proof['root_job']['verification_copy'],CPU=insurance),
        planned_owned_start_request_id=a['request_id'],
        planned_phase_id_and_unique_save_tags=dict(phase_id=a['phase_id'],startup=a['startup_tag'],early_insurance='rawkl-early-insurance-20261017-trial02',candidate='rawkl-first-8M-20261017-trial02',CE_startup='rawkl-ce-startup-20261017-trial02'),
        production_helpers_and_evaluation_profile=dict(helpers=a['helper_pins'],confirmation=core['future_confirmation'],manifest=manifest),
        protected_checkpoint_and_metadata=dict(checkpoint=a['protected_reference'],metadata=pin(a['protected_reference']['path']+'.json')),
        ring_current_and_both_bank_start_proof=dict(asof=storage,bank_spec=spec,actual_stopped_and_startup_proofs='Derived by the exact owned transition before/after new KL start'),trial_id=core['trial_id'])
    core['prerequisites']['fresh_current_owner_insurance_CPU']=insurance
    cp=save('trial-core-FINAL.json',core);a['trial_core']=cp
    ap=save('activation-job-FINAL.json',a)
    checked,checked_pin=adapter.read_job(argparse.Namespace(job=Path(ap['path']),expected_job_sha256=ap['sha256'],expected_controller_sha256=ADAPTER),base)
    assert checked==a and checked_pin==ap
    trial=dict(schema='robotron-one-raw-kl-trial-job-v1',sources=dict(controller=pin(SRC/'run_one_trial.py'),deadline=pin(SRC/'deadline_guard.py'),early_insurance=pin(SRC/'early_insurance.py'),adapter=a['helper_pins']['controller'],horizon=a['helper_pins']['horizon']),
        activation_job=ap,trial_core=cp,old_owner=proof['root_job']['insurance']['trainer'],boot_id=a['boot_id'],
        output_directory=str(RUN/'rawKL-trial02-controller-20261017'),deadlines=dict(latch_s=3240,stop_intent_s=3310,owner_ceiling_s=3600),observation_budget_bytes=32<<20,
        early_insurance=dict(tag='rawkl-early-insurance-20261017-trial02',cpu_unit='robotron-rawkl-early-insurance-trial02-20261017.service',save_timeout_s=60,cpu_timeout_s=120),
        candidate_tag='rawkl-first-8M-20261017-trial02',return_intent=dict(phase_id='ce_after_rawkl_20261017_trial02',request_id='rawkl_trial02_return_ce_20261017',startup_tag='rawkl-ce-startup-20261017-trial02',output_directory=str(RUN/'rawKL-trial02-return-CE-20261017')))
    assert all(not Path(value).exists() for value in [trial['output_directory'],a['output_directory'],trial['return_intent']['output_directory']])
    tp=save('one-trial-job-FINAL.json',trial)
    receipt=save('root-FINAL-readonly-validation.json',dict(status='PASS',core=cp,activation=ap,trial=tp,preparation=prerequisites,armed=False,executed=False))
    print(json.dumps(dict(status='FINAL_PREPARED_NOT_ARMED',receipt=receipt,trial=tp,core=cp,activation=ap)))

if __name__=='__main__':main()
