"""Default inert. Root-only new entry/case preparation; never resume old counts.

No mode launches the durable observer. --verify-entry explicitly invokes the
already selected original CPU lifecycle once; Root must authorize that action.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import stat
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G/'logs/managed-learning-20261015/run-26'
OLD = B/'post-natural-turnover-durable-next-candidate-20261029-original01'
OUT = B/'post-natural-turnover-durable-next-candidate-20261029-original02'
WATCH = G/'tools/power_recovery/watch_replay_progress_candidate.py'
WATCH_SHA = '303a6cd4096b42477df60c4631aa76d3df234a1ccb88cc7a69d5a6ab0e88f962'
LIB = G/'tools/power_recovery/watch_learning_window_v2.py'
LIB_SHA = 'f7398454d3985b05d653b54a4dd7b13299a50866d8e5dbbd98100e786c9ce186'
OLD_PLAN_SHA = '97206a8e82ff4f43f8d74b8ab564c682ef2504d2f3ec13195154f52888baee6a'
LOSS = B/'post-recovery-evaluation-isolation-original01-20261027/durable-e078b0da-launcher-mmap-study-original01/R1/read-only-startup-observation-original01/independent-original-R1-anchor-then-failure-small-observation.json'
LOSS_SHA = '59fb3487cf82e1121c85f28c4ca6dbaa394b44e861b2ea6581561906b73d41bf'
FAMILY = B/'post-recovery-evaluation-isolation-original01-20261027/distincta6e17a3c-single-journal-family11-study-original01/R1/source-family.json'
FAMILY_SHA = 'dca06ef8a24d99839a396ce478780520c9338c4e1f6d6c8c57606cbb9bc33df4'
ENTRY_UNIT = 'robotron-durable-entry-CPU-original02-20261029.service'
ENDPOINT_UNIT = 'robotron-durable-endpoint-CPU-original02-20261029.service'
OBSERVER_UNIT = 'robotron-durable-candidate-window-original02-20261029.service'
THRESHOLDS = dict(applied_updates=5000,replay_inserts=1000000,elapsed_s=3600)
CANONICAL_SOURCE_MODES = {WATCH:0o664, LIB:0o664,
    G/'tools/post_recovery_evaluation/round_observer_v10.py':0o664,
    G/'tools/post_recovery_evaluation/round_health_transport_v7.py':0o664}


def require(value, message):
    if not value: raise RuntimeError(message)


def checked(path, digest):
    require(path.is_file() and not path.is_symlink(), 'Regular source required: '+str(path))
    before=path.stat()
    require(before.st_uid==os.getuid() and stat.S_IMODE(before.st_mode)==CANONICAL_SOURCE_MODES.get(path,0o444) and before.st_nlink==1,
            'Selected source/authority must retain its exact owned mode and independent link')
    raw=path.read_bytes(); after=path.stat()
    stable=lambda value:(value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns,value.st_mode,value.st_uid,value.st_nlink)
    require(stable(before)==stable(after) and hashlib.sha256(raw).hexdigest()==digest,
            'Pinned source changed: '+str(path)); return raw


def load(name, path, digest):
    raw=checked(path,digest); module=__import__('types').ModuleType(name); module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__); return module


def dependencies():
    watch=load('_durable_original_watch',WATCH,WATCH_SHA)
    observer=load('_durable_original_observer',LIB,LIB_SHA)
    plan=json.loads(checked(OLD/'window-plan.json',OLD_PLAN_SHA))
    loss=json.loads(checked(LOSS,LOSS_SHA))
    require(loss['schema']=='robotron-readonly-original-R1-anchor-then-failure-small-observation-v1'
            and loss['status']=='ORIGINAL_ANCHORED_THEN_FAILED_NO_QUALITY'
            and loss['scientific_quality_or_improvement_qualified'] is False
            and loss['private_scores_or_quality_comparisons_read'] is False,
            'Original E078 evaluation failure must remain invalid without a quality claim')
    require(plan['thresholds']==THRESHOLDS and plan['maximum_wait_s']==14400, 'Original selection rules differ')
    require(observer.owner()==plan['owner'], 'Original live trainer incarnation changed')
    for value in plan['inputs']: observer.check_pin(value)
    return watch,observer,plan


def prepare_entry(watch,observer,plan):
    require(not OUT.exists(), 'New independent case only; never adopt partial output')
    OUT.mkdir(mode=0o700); entry=OUT/'entry-CPU-original01'; entry.mkdir(mode=0o700)
    endpoint=observer.copy_snapshot(Path(plan['checkpoint']),entry/'entry.pt')
    observer.publish(OUT/'entry-snapshot-prepared-NOT-CPU-VERIFIED.json',dict(
        schema='robotron-independent-durable-window-entry-preparation-v1',endpoint=endpoint,
        owner=plan['owner'],source=observer.pin(Path(__file__)),prior_plan=observer.pin(OLD/'window-plan.json'),
        CPU_unit=ENTRY_UNIT,own_window_not_started=True,prior_partial_counts_reused=False),exclusive=True)
    print(json.dumps(dict(status='ENTRY_COPIED_NOT_CPU_VERIFIED',entry=endpoint,next_mode='--verify-entry')))


def verify_entry(watch,observer,plan):
    entry=OUT/'entry-CPU-original01'; prepared=observer.read(OUT/'entry-snapshot-prepared-NOT-CPU-VERIFIED.json')
    require(prepared['owner']==plan['owner'] and not (OUT/'entry-CPU-authority.json').exists(), 'Original entry CPU only')
    endpoint=prepared['endpoint']; observer.check_pin(endpoint)
    verification=watch.verify_CPU(dict(plan,CPU_unit=ENTRY_UNIT),entry,endpoint,observer)
    observer.publish(OUT/'entry-CPU-authority.json',dict(endpoint=endpoint,
        actual_CPU_verification=observer.pin(entry/'endpoint-CPU.json'),
        original_CPU_owner=observer.pin(entry/'CPU-original-owner.json'),
        original_CPU_terminal=observer.pin(entry/'CPU-original-terminal.json'),
        original_CPU_release=observer.pin(entry/'CPU-owned-release.json'),
        new_entry_Adam_step=verification['Adam_step_min'],own_window_not_started=True),exclusive=True)
    print(json.dumps(dict(status='OWN_ENTRY_CPU_VERIFIED_AND_RELEASED',next_mode='--prepare-window')))


def prepare_window(watch,observer,plan):
    require(not (OUT/'window-plan.json').exists() and not (OUT/'anchor.raw.json').exists(), 'Wholly new window only')
    authority=observer.read(OUT/'entry-CPU-authority.json'); verification=observer.read(authority['actual_CPU_verification']['path'])
    for key in ('actual_CPU_verification','original_CPU_owner','original_CPU_terminal','original_CPU_release'):
        observer.check_pin(authority[key])
    require(verification['checkpoint']==authority['endpoint'] and verification['CUDA_initialized'] is False, 'Own entry CPU differs')
    family=json.loads(checked(FAMILY,FAMILY_SHA)); components=family['main_observer']
    worker=load('_durable_entry_worker',Path(components['worker']['path']),components['worker']['sha256'])
    health=load('_durable_entry_health',Path(components['health']['path']),components['health']['sha256'])
    case=observer.read(Path(plan['clean_roster_case']['path']))
    case['initial_round']=observer.read(Path(case['round_root'])/'status.json')['round']; case.pop('baseline_snapshot',None)
    deadline=time.monotonic()+30
    while True:
        try:
            sample=worker.collect(health,case);health.validate(case,sample);health.check_inputs(case,full=True);break
        except (ValueError,OSError):
            require(time.monotonic()<deadline, 'No valid original current roster within30s');time.sleep(.02)
    observer.publish(OUT/'fresh-main-entry.raw.json',sample,exclusive=True)
    case['baseline_snapshot']=observer.pin(OUT/'fresh-main-entry.raw.json')
    observer.publish(OUT/'fresh-main-case.json',case,exclusive=True)
    fresh=observer.observe(plan['owner'],OUT,plan['expected_exposure_lineage']);observer.validate(fresh,plan['owner'])
    require(all(fresh[k]>=verification['clocks'][k] for k in observer.CLOCKS), 'Entry proof is newer than prelaunch API')
    observer.publish(OUT/'prelaunch-API-NOT-WINDOW-ANCHOR.json',fresh,exclusive=True)
    new=copy.deepcopy(plan)
    for key in ('interrupted_observer_case','interrupted_observer_exit_known','interrupted_observer_disposition'):
        new.pop(key,None)
    new.update(purpose='New independent durable original02 exposure window after invalid E078 screening; no old elapsed time, progress counts, reference games or scores reused.',
        entry_Adam_step=verification['Adam_step_min'],entry_verification=authority['actual_CPU_verification'],
        CPU_unit=ENDPOINT_UNIT,clean_roster_case=observer.pin(OUT/'fresh-main-case.json'),
        clean_roster_snapshot=observer.pin(OUT/'fresh-main-entry.raw.json'),
        original_partial_counts_reused=False,original_failed_case_restarted=False,
        prior_completed_candidate_case=str(OLD),prior_completed_candidate_policy_sha256='e078b0da4ce4e25146fab7484f8489f590e1086370746cb392afcd7f5f8adef5',
        prior_candidate_screening_failed_without_quality=True,prior_scientific_case_retried=False,
        prior_failed_screening_disposition=observer.pin(LOSS),
        clean_roster_entry_scope='Entry sanity for this exposure-only window; no500ms scientific observer qualification or evaluator source-family selection is conferred.',
        observer_process_lifetime='Root-launched durable systemd service, Restart=no, RemainAfterExit=yes; original terminal must be archived.',
        entry_snapshot_authority_is_historical_same_process=False)
    # Drop historical entry/case inputs, then retain exact source/config guards.
    # Historical cases remain preserved on disk; none supplies this window's data.
    new['inputs']=[value for value in plan['inputs'] if '/run-26/post-' not in value['path']]
    new['inputs'] += [observer.pin(OUT/'fresh-main-case.json'),observer.pin(OUT/'fresh-main-entry.raw.json'),
        *[authority[key] for key in ('actual_CPU_verification','original_CPU_owner','original_CPU_terminal','original_CPU_release')],
        observer.pin(LOSS),
        observer.pin(Path(__file__))]
    new['inputs']=list({value['path']:value for value in new['inputs']}.values())
    for value in new['inputs']: observer.check_pin(value)
    observer.publish(OUT/'window-plan.json',new,exclusive=True)
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',plan=observer.pin(OUT/'window-plan.json'),command=observer_command())))


def observer_command():
    return ['systemd-run','--user','--unit='+OBSERVER_UNIT,
        '-p','Type=exec','-p','Restart=no','-p','RemainAfterExit=yes',
        '-p','CPUQuota=100%','-p','MemoryMax=256M','-p','MemorySwapMax=0','-p','TasksMax=32',
        '-p','RuntimeMaxSec=14820','-p','TimeoutStopSec=10','-p','SendSIGKILL=no',
        '-p','StandardOutput=append:'+str(OUT/'observer.stdout.log'),
        '-p','StandardError=append:'+str(OUT/'observer.stderr.log'),
        '/usr/bin/python3.12','-I','-B',str(WATCH),'--plan',str(OUT/'window-plan.json')]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare-entry',action='store_true')
    modes.add_argument('--verify-entry',action='store_true')
    modes.add_argument('--prepare-window',action='store_true')
    modes.add_argument('--print-observer-command',action='store_true')
    args=parser.parse_args(argv)
    if args.print_observer_command:print(json.dumps(dict(argv=observer_command(),launch_performed=False)));return
    if not any((args.prepare_entry,args.verify_entry,args.prepare_window)):
        print('PLAN_ONLY: no reads, copies, queries, outputs, CPU or observer launch');return
    watch,observer,plan=dependencies()
    if args.prepare_entry:prepare_entry(watch,observer,plan)
    elif args.verify_entry:verify_entry(watch,observer,plan)
    else:prepare_window(watch,observer,plan)


if __name__=='__main__':main()
