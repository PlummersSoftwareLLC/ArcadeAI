"""Prepare each remaining leg’s repaired600s review after its true native exit0.

Default/import is inert. Preparation reads metadata and source, never a model
body, Torch, GPU, MAME, scores before cutoff, unit controls or production state.
Future result/owner/closure hashes are computed only from their actual closed
files. This helper cannot launch a review or native leg.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
Q=R/'deadline-score60min-protocol-original01-preparation-20261026'
Y=R/'deadline-score32-fixed-fleet-admission-original03-preparation-20261026'
QUALIFIED=Y/'qualified-native-envelopes-after-CPU-original01/qualified-four-native-envelopes.json'
QUALIFIED_SHA='4ea6d7d830b7d0c7fc77c2ec16365004e6c0897f6442bea9f6ff9e47a0e2867d'
REVIEWER=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score32-postterminal-review-archive-abi-case02-original01-preparation-20261027/review_deadline32_leg_explicit_archive_v2.py')
REVIEWER_SHA='90e48709bb17fa92cf795ec806e6ea8c4d5eb815c3f7b5d2e6bb5d492a8c5734'
HELPERS=G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
HELPERS_SHA='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
READER=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
ARCHIVE=G/'tools/eval_capacity_proposal/review_original_pilot_score_carry_v1.py'
ARCHIVE_SHA='8efdb031e52b63e9679b5c1225787019ff86be1d99bf401535d8df53d22d1d9d'
CONTROL=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score32-postterminal-review-resource600-case03-original01-preparation-20261027/control_deadline32_review600_v1.py')
CONTROL_SHA='848f0fb2d3ada56a49b949aacfb7b11496871722b46202aa214be8c2ed4f9124'
INITIAL=G/'tools/startup_policy_journal_proposal/read_compiled_quality32_owned_health_template_v5.py'
INITIAL_SHA='c735569717651c1031d9ee84dd108e663b5db268bdafcf2158cc30c8cea228e3'
PYTHON=Path('/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python')
OBSERVER_ADAPTER=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score32-postterminal-review-archive-abi-case02-original01-preparation-20261027/observer_archive_dependency_adapter_v1.py')
OBSERVER_ADAPTER_SHA='5d39afce2801393abcb71735762beb9a1351df2b8a19200f8305e8c79bad05ca'
OBSERVER_DERIVATION=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score32-postterminal-review-archive-abi-case02-original01-preparation-20261027/observer-archive-dependency-derivation-v1.json')
OBSERVER_DERIVATION_SHA='812c234f2669ec674cf767a416393725a1b6b6a00f29aa53a3f5f0900c568977'


def require(ok,message):
    if not ok:raise ValueError(message)


def metadata_pin(path):
    path=Path(path)
    require(path.suffix in ('.json','.py','.txt','.lua'),'Metadata/source files only')
    before=path.stat();raw=path.read_bytes();after=path.stat()
    def identity(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    require(identity(before)==identity(after),'Metadata changed during preparation')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(after))


def source_pin(path,sha=None):
    p=metadata_pin(path)
    require(p['identity']['mode']=='0o444' and (sha is None or p['sha256']==sha),'Selected frozen source differs')
    return p


def load(name,pin):
    require(metadata_pin(pin['path'])==pin,'Actual source pin differs')
    spec=importlib.util.spec_from_file_location(name,pin['path']);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


def controller_pin_from_attestation(entry):
    """Retain the existing controller ABI without hashing a model/binary body."""
    path=Path(entry['path']);s=path.stat()
    actual=dict(device=s.st_dev,inode=s.st_ino,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    require(s.st_size==entry['bytes'] and all(actual[k]==entry['identity'][k]for k in actual),
            'Previously attested input identity changed')
    for key,value in (('mtime_ns',s.st_mtime_ns),('ctime_ns',s.st_ctime_ns)):
        if key in entry['identity']:require(entry['identity'][key]==value,'Previously attested input timestamp changed')
    if path.suffix in ('.json','.py','.txt','.lua'):
        require(metadata_pin(path)['sha256']==entry['sha256'],'Metadata/source digest changed')
    elif path.suffix=='.pt':
        require(stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink(),'Original model must remain the regular attested file')
    return dict(path=entry['path'],sha256=entry['sha256'],bytes=entry['bytes'],identity=actual)


def prepare(leg,output_directory,source_sha256):
    require(leg in ('C1','R2','C2'),'One remaining selected fixed study03 leg required; R1 is already reviewed')
    require('torch'not in sys.modules,'Metadata preparation must use a fresh process without Torch')
    preparation_source=source_pin(Path(__file__).resolve(),source_sha256)
    sources=dict(helpers=source_pin(HELPERS,HELPERS_SHA),reader=source_pin(READER,READER_SHA),
        archive=source_pin(ARCHIVE,ARCHIVE_SHA),controller=source_pin(CONTROL,CONTROL_SHA),
        reviewer=source_pin(REVIEWER,REVIEWER_SHA),initial_helpers=source_pin(INITIAL,INITIAL_SHA),
        observer_archive_adapter=source_pin(OBSERVER_ADAPTER,OBSERVER_ADAPTER_SHA),
        observer_archive_derivation=source_pin(OBSERVER_DERIVATION,OBSERVER_DERIVATION_SHA))
    h=load('_deadline_postterminal_helpers',sources['helpers'])
    immutable=load('_deadline_postterminal_reader',sources['reader'])
    def read(pin,as_json=True):return immutable.read_pin(pin,as_json=as_json)
    qualified_pin=source_pin(QUALIFIED,QUALIFIED_SHA);qualified=read(qualified_pin)
    case=next(c for c in qualified['cases']if c['leg']==leg)
    job=read(case['native_job']);cfg=read(case['native_launch_config']);family=read(job['source_family_manifest'])
    require(job['leg']==leg and job['runtime']['sha256']=='85b2efdd43c8c1c7a0f48610908bec1ded2b936d066080328b6862fc394ae556'
            and family['reviewer']['sha256']=='f2b311fd6d375e6b1e35c571b91cfb8c209881855834941d5b0292b51a9bbf5e',
            'Selected native job/original family reviewer parent differs')
    # The actual native family remains immutable. Select the explicit archive
    # adapter for this CPU review without changing any native/scientific rule.
    repaired=load('_deadline_postterminal_repaired_reviewer',sources['reviewer'])
    bridge_review=dict(observer_archive_adapter=sources['observer_archive_adapter'],
        observer_archive_derivation=sources['observer_archive_derivation'],archive=sources['archive'],
        native_controller=case['native_controller'])
    archive_derivation_check=repaired.validate_observer_archive_derivation(bridge_review,family,read)
    # These are exact caller-selected original paths, not guessed future pins.
    # An active or failed original cannot produce a review envelope here.
    native_root=Path(cfg['output'])
    closure_pin=metadata_pin(native_root/'root-original-result-and-owned-release.json');closure=read(closure_pin)
    owner_pin=metadata_pin(native_root/'root-original-identity.json');owner=read(owner_pin)
    require(closure['original_exit']==0 and owner['unit']==cfg['unit'],'True original native exit0 required before preparation')
    archive=load('_deadline_postterminal_archive',sources['archive'])
    fields=archive.archived_closure(closure,owner,read,exit_zero=True)
    require(fields['CPUQuotaPerSecUSec']=='12s' and fields['MemoryMax']==str(24<<30)
            and fields['RuntimeMaxUSec']=='1h 11min' and fields['TasksMax']=='512','Actual original native resource scope differs')
    proc=Path('/proc',str(owner['pid']),'stat')
    require(not proc.exists()or int(proc.read_text().rsplit(')',1)[1].split()[19])!=owner['starttime_ticks'],
            'Original native process remains live')
    result_pin=metadata_pin(Path(job['output'])/'result.json');result=read(result_pin)
    require(result['original_job']==case['native_job'] and result['complete'] is True and result['errors']==[]
            and result['deadline_score_seal'] is not None and result['original_lease_released'] is True,
            'Actual complete, sealed and owned-closed original result required')
    guard_pin=case['exact_job_CPU_guard'];guard=read(guard_pin)
    require(guard['native_job']==case['native_job'] and guard['runtime']==case['runtime'] and guard['actual_exit']==0,
            'Actual original CPU guard/job binding differs')
    initial=load('_deadline_postterminal_initial_helpers',sources['initial_helpers'])
    require(callable(initial.validate_initial_readiness),'Original initial-readiness function missing')
    control=load('_deadline_postterminal_review_controller',sources['controller'])
    require('torch'not in sys.modules,'Shared review helper imported Torch')
    directory=Path(output_directory)
    require(directory.is_absolute() and directory.resolve()==directory and not directory.exists() and directory.parent.is_dir(),
            'Fresh exact isolated review-envelope directory required')
    review_output=directory/'independent-review.json'
    inputs=[*job['inputs'],*sources.values(),preparation_source,qualified_pin,case['native_job'],case['native_launch_config'],
        case['native_controller'],owner_pin,closure_pin,result_pin,guard_pin,job['source_family_manifest'],
        job['main_health_protocol'],job['study_precommit']]
    unique={}
    for entry in inputs:
        key=entry['path']
        require(key not in unique or unique[key]==entry,'Conflicting original source/input pin')
        unique[key]=entry
    inputs=list(unique.values())
    # Validate every current input before the first output mutation. Large
    # models, MAME and interpreter retain their original attested digests/stat.
    pins=[controller_pin_from_attestation(p)for p in inputs]
    directory.mkdir(mode=0o700)
    review=dict(schema='robotron-deadline32-original-leg-independent-review-job-v1',output=str(review_output),
        native_job=case['native_job'],native_result=result_pin,native_owner=owner_pin,native_closure=closure_pin,
        native_config=case['native_launch_config'],native_controller=case['native_controller'],
        source_family_guard_closeout=guard_pin,helpers=sources['helpers'],reader=sources['reader'],
        archive=sources['archive'],initial_helpers=sources['initial_helpers'],inputs=inputs,
        observer_archive_adapter=sources['observer_archive_adapter'],
        observer_archive_derivation=sources['observer_archive_derivation'])
    review_pin=h.put(directory/'review-job.json',review)
    argv=[str(PYTHON),'-Xgil=0','-I','-B',str(REVIEWER),'--execute','--job',review_pin['path'],
        '--job-sha256',review_pin['sha256'],'--source-sha256',REVIEWER_SHA]
    python_pin=next(p for p in cfg['pins']if p['path']==str(PYTHON))
    pins.extend((controller_pin_from_attestation(review_pin),controller_pin_from_attestation(python_pin)))
    cpins={p['path']:p for p in pins}
    config=dict(unit='robotron-deadline32-score60min-'+leg.lower()+'-original03-postterminal-review-original01-20261027.service',
        output=str(directory/'execution-original01'),argv=argv,properties=['CPUQuota=200%','MemoryMax=4G',
            'MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=660,pins=list(cpins.values()))
    config_pin=h.put(directory/'controller-config.json',config)
    require(control.checked_config(config_pin['path'])==config,'Actual bounded review config differs')
    prepared=h.put(directory/'prepared-postterminal-review-NOT-LAUNCHED.json',dict(
        schema='robotron-deadline32-postterminal-review-preparation-v1',leg=leg,qualified_native_envelopes=qualified_pin,
        preparation_source=preparation_source,explicit_archive_dependency_derivation=archive_derivation_check,
        review_resources=dict(cpu_cores=2,memory_bytes=4<<30,runtime_s=600,tasks_max=128,observation_s=660),
        repaired_reviewer_selected_directly_without_bad_f2b_execution=True,
        native_job=case['native_job'],actual_native_result=result_pin,actual_native_owner=owner_pin,
        actual_native_closure=closure_pin,exact_CPU_guard=guard_pin,reviewer=sources['reviewer'],
        review_job=review_pin,review_controller=sources['controller'],review_controller_config=config_pin,
        future_result_hashes_guessed=False,model_or_binary_bodies_read=False,Torch_imported=False,
        source_or_main_changed=False,unit_or_process_actions=False,review_launched=False,
        deadline_metric_qualified=False,improvement_qualified=False,ROOT_review_and_launch_required=True))
    return prepared


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--leg',choices=('C1','R2','C2'));parser.add_argument('--output-directory')
    parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.prepare:print('PLAN_ONLY: no reads, outputs, model or runtime actions');return 0
    require(args.leg and args.output_directory and args.source_sha256,'Explicit original leg, source SHA and fresh output directory required')
    print(json.dumps(prepare(args.leg,args.output_directory,args.source_sha256)),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
