#!/usr/bin/env python3
"""One root-owned activate_kl or return_ce transition; literal PLAN by default.

SOURCE PREPARATION ONLY. Uses pinned v4 ownership/storage primitives. No trial
watcher, automatic retry, old-state restore, evaluator or promotion runs here.
"""
from __future__ import annotations
import argparse
import base64
import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import traceback

SCHEMA = 'robotron-raw-kl-installed-phase-transition-job-v3'
RESULT_SCHEMA = 'robotron-raw-kl-installed-phase-transition-result-v3'
V4 = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/live8_maintenance_proposal/revision4/run_live8_maintenance.py')
V4_SHA = 'fdf7c8bfb123b494252acf83d724a51acda95bb7f00877eace28b60d0377ed18'
PHASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/phase_snapshot_cpu_verifier_proposal/verify_phase_snapshot.py')
PHASE_SHA = 'b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519'
STRICT_SHA = '9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'
CANDIDATE = {'agent.py':'865a0df717b39951b7f7c516e4a962e3d48cf4d3dc11295ff266e58653e6c74b',
 'training.py':'90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4',
 'loss_kernel.py':'23eb8fc0d8409c9f31ef26ec4596da9c2257e3985abbbfa7d5fbdcb337e21f67',
 'config.py':'19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd',
 'priority_phase.py':'ee3c0d02bc1eab55e92ffd605c3736fe5a0ef905a8a8ee242c687301ea2b7c5b'}
CLOCKS = ('training_steps','optimized_samples','learner_frame_count','frame_count')
FLAGS = ('DQN_RECOMPUTED_CE_CAPTURE_DIR','DQN_EXECUTED_CE_TRACE_DIR')
SOURCE_NAMES = ('__init__.py','model.py','config.py','learning_control.py',*('agent.py','training.py','loss_kernel.py','priority_phase.py'))
MAX_JSON = 2 << 20
ANCESTOR = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/live_transition_adapter_proposal/run_raw_kl_transition.py')
ANCESTOR_SHA = '8a606d4c152e85c867f5517555ce80fb05cc883decad1f84da0784e4d32bdd3c'
HORIZON = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/sequential_trial_precommit_proposal/horizon_observer_proposal/horizon_observer.py')
HORIZON_SHA = '25d70b4a3888dcba83ea9020c333cba32cfbd19c93b6e69037d6299b161fd7ec'


def require(value, message):
    if not value: raise RuntimeError(message)


def selected_environment(before, metric, record):
    require(metric in ('kl','ce'), 'Unknown static metric')
    result = dict(before)
    for flag in FLAGS: result.pop(flag, None)
    result.update(DQN_PER_PRIORITY_METRIC=metric,DQN_PRIORITY_PHASE_RECORD=record['path'],
        DQN_PRIORITY_PHASE_RECORD_SHA256=record['sha256'])
    return result


def four(value):
    result = {key:value[key] for key in CLOCKS}
    require(all(type(x) is int and x > 0 for x in result.values()), 'Invalid four saved clocks')
    return result


def triple(pin):
    return {key:pin[key] for key in ('path','sha256','bytes')}


def start_record(mode, phase_id, core_sha, model_dir, checkpoint, boot_proof):
    require(mode in ('activate_kl','return_ce') and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',phase_id or ''), 'Invalid transition identity')
    require(re.fullmatch(r'[0-9a-f]{64}',core_sha or ''), 'Invalid immutable trial core SHA')
    previous = boot_proof.get('saved_priority_metric_phase')
    if mode == 'activate_kl':
        require(isinstance(previous,dict) and previous.get('metric') == 'ce' and previous.get('valid') is True,
            'Installed-source activation requires newest verified valid CE predecessor')
    if mode == 'return_ce':
        require(isinstance(previous,dict) and previous.get('metric') == 'kl' and previous.get('valid') is True,
            'CE return requires actual newest valid KL phase; no historical rollback')
    require(previous is None or previous.get('phase_id') != phase_id, 'New phase ID required')
    return dict(schema='robotron-priority-metric-start-v1',phase_id=phase_id,
        metric='kl' if mode == 'activate_kl' else 'ce',action='start',
        previous_metric='unknown' if previous is None else previous['metric'],checkpoint=triple(checkpoint),
        model_dir=model_dir,root_precommit_sha256=core_sha)


def expected_start(record, record_pin, boot_proof):
    return dict(metric=record['metric'],phase_id=record['phase_id'],root_precommit_sha256=record['root_precommit_sha256'],
        founder_phase_record_sha256=record_pin['sha256'],last_resume_record_sha256=None,
        started_from=dict(record['checkpoint'],clocks=four(boot_proof['clocks'])),valid=True)


def request_identity(value):
    """Immutable request bytes/inode; link/rename alone may change ctime/nlink."""
    return {key:value[key] for key in ('device','inode','bytes','mtime_ns','mode','uid')}


def publish_request(base, model, archive, tag, register):
    """Seal+archive bytes BEFORE a no-overwrite publication; retain opened inode.

    The consumer may rename request->completed before the publisher is scheduled
    again. The historical request PIN therefore describes the owned opened file
    at publication, with its intended path; it is not a claimed later path stat.
    """
    path=model/'managed_save.request.json'
    require(not path.exists(),'Pending request already exists')
    raw=(json.dumps({'tag':tag},sort_keys=True)+'\n').encode()
    fd,name=tempfile.mkstemp(prefix='.managed-phase-request-',dir=model)
    temporary=Path(name);before=None;pending=None;primary=None
    try:
        pending=dict(tag=tag,pin=None,archive=None,publication=dict(
            identity_scope='Owned FD before no-overwrite publication; path may immediately move to completed',
            temporary_path=str(temporary),created=base.identity(os.fstat(fd)),published=False))
        register(pending)  # Partial preparation is owned evidence too.
        with os.fdopen(fd,'w+b',closefd=False) as stream:
            stream.write(raw);stream.flush();os.fsync(fd);os.fchmod(fd,0o444)
        before=base.identity(os.fstat(fd))
        _,archived=base.exclusive_copy(temporary,archive)
        historical=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)
        pending.update(pin=historical,archive=archived)
        pending['publication']['prepared']=before
        pending['publication']['before_expose_unix_s']=time.time()
        os.link(temporary,path,follow_symlinks=False)
        pending['publication']['published']=True
        pending['publication']['after_expose_unix_s']=time.time()
        linked=base.identity(os.fstat(fd));pending['publication']['after_link']=linked
        require(request_identity(linked)==request_identity(before) and linked['nlink'] in (1,2),'Publication inode changed')
        require(request_identity(base.identity(temporary.lstat()))==request_identity(before),'Owned invisible temp replaced')
        temporary.unlink();base.fsync_directory(model)
        pending['publication']['after_temp_unlink']=base.identity(os.fstat(fd))
        require(pending['publication']['after_temp_unlink']['nlink']==1,'Request publication has an unexpected link')
        return pending
    except BaseException as error:
        primary=error
        raise
    finally:
        # Remove only our still-open, unchanged invisible inode. Never remove a
        # request/completed/failed path, including on an interrupted publication.
        try:
            if temporary.exists() and before is not None:
                if request_identity(base.identity(temporary.lstat()))==request_identity(before):temporary.unlink()
            os.close(fd)
        except BaseException as error:
            if primary is None:raise
            if pending is not None:pending['publication'].setdefault('secondary_cleanup_errors',[]).append(repr(error))


def zero_replay(raw, owner_pid):
    exposure = raw['host_pipeline']['learning_exposure']
    for value in exposure.values(): require(value['process_id'] == owner_pid, 'Exposure belongs to another process')
    replay = exposure['replay']; categories = replay['accepted_by_source_total']
    require(set(categories)=={'dqn','epsilon','expert','eval','unattributed'} and
        all(type(x) is int and x == 0 for x in categories.values()) and
        replay['accepted_total'] == sum(categories.values()) == 0 and
        replay['accepted_learner_total']==categories['dqn']+categories['epsilon']==0 and replay['available'],
        'Fresh before-resume ring exposure must be actual physical zero')
    return copy.deepcopy(exposure)


def clock_max(*values):
    return {key:max(four(value)[key] for value in values) for key in CLOCKS}


def validate_ending(job,base):
    """Read small pinned observations only; never open candidate/model bytes.

    A return floor is an explicit observation bound, not a fabricated insurance
    result. The original owner-bound insurance remains separately unchanged.
    """
    for name,path,sha in (('ancestor_adapter',ANCESTOR,ANCESTOR_SHA),('horizon',HORIZON,HORIZON_SHA)):
        item=job['helper_pins'][name]
        require(item['path']==str(path) and item['sha256']==sha,'Wrong consumed companion source: '+name)
        base.pin(item,base.MAX_SOURCE)
    ending=job['ending_proof']
    if job['mode']=='activate_kl':
        require(ending is None,'Activation cannot invent an ending decision')
        return None
    require(isinstance(ending,dict) and set(ending)=={'observer_job','activation_receipt','decision','candidate'},
        'Return requires actual ending observation bindings')
    horizon=base.load_module(str(HORIZON),'raw_kl_ending_horizon_contract')
    observer=base.read_json(ending['observer_job']);_,baseline=horizon.validate_job(observer)
    activation=base.read_json(ending['activation_receipt']);decision=base.read_json(ending['decision'])
    insurance=base.read_json(job['insurance_verification']);insured=insurance['root_job']['insurance']['trainer']
    start=base.read_json(activation['start_request'])
    before_resume=base.read_json(activation['before_resume_api_PIN'])
    require(ending['activation_receipt']['sha256']==observer['activation_receipt_sha256'] and
        activation['status']=='READY' and activation['manual_recovery_required'] is False and
        activation['qualification_pass'] is False and activation['owner']==observer['owner']==insured and
        activation['trial_core']['sha256']==observer['trial_core_sha256']==job['running_phase']['expected']['root_precommit_sha256'] and
        activation['boot_four_clocks']==observer['boot_four_clocks'] and
        activation['healthy192_monotonic_s']==observer['healthy192_monotonic_s'] and
        before_resume==observer['before_resume_api'] and
        start['boot_id']==observer['start_request']['boot_id'] and
        start['monotonic_s']==observer['start_request']['monotonic_s'],
        'Ending belongs to a different activation/owner/original clock origin')
    require(decision['schema']=='robotron-raw-kl-horizon-observation-v1' and
        decision['state'] in ('LATCH','INCOMPLETE') and decision['qualification_pass'] is False and
        decision['boot_id']==observer['start_request']['boot_id'], 'Only first latched/incomplete ending is supported')
    observed=horizon.number(decision['observed_monotonic_s'],'ending observation')
    require(observed-observer['start_request']['monotonic_s']==decision['elapsed_s'] and
        observed>=observer['healthy192_monotonic_s'], 'Ending time was reanchored')
    latched=decision['state']=='LATCH'
    raw=decision['first_eligible_observation'] if latched else (
        decision.get('terminal_observation') or decision.get('last_valid_observation'))
    clocks=four(insurance['clocks'])
    if raw is not None:
        current=horizon.normalise(raw)
        require(current['optimizer_identity']==baseline['optimizer_identity'] and
            current['replay_identity']==baseline['replay_identity'] and
            all(current['clocks'][key]>=observer['boot_four_clocks'][key] for key in CLOCKS),
            'Ending API owner/epoch/clock lineage changed')
        clocks=four(raw)
    if latched:
        progress=decision['progress']
        require(0<=decision['elapsed_s']<=horizon.POLICY['cutoff_s'] and
            decision['candidate_requests_allowed']==1 and
            progress['learner_frames']==clocks['learner_frame_count']-observer['boot_four_clocks']['learner_frame_count']>=horizon.POLICY['learner_frames'] and
            progress['physical_accepted']==current['accepted']-baseline['accepted']>=horizon.POLICY['physical_adds'] and
            progress['optimizer_total']==current['optimizer'], 'LATCH identity/horizons differ from its actual API')
        candidate=ending['candidate']
        require(isinstance(candidate,dict) and set(candidate)=={'source','verification_copy','acquisition'},
            'First LATCH requires its one frozen candidate')
        source,copied=candidate['source'],candidate['verification_copy']
        for pin in (source,copied):
            require(set(pin)=={'path','sha256','bytes','identity'} and
                re.fullmatch('[0-9a-f]{64}',pin['sha256'] or '') and type(pin['bytes']) is int and pin['bytes']>0,
                'Explicit candidate source/copy PIN required')
            require(set(pin['identity'])=={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'} and
                pin['identity']['bytes']==pin['bytes'],'Complete candidate identity required')
        require(triple(source)['sha256']==copied['sha256'] and source['bytes']==copied['bytes'] and
            source['path']!=copied['path'] and
            (source['identity']['device'],source['identity']['inode'])!=(copied['identity']['device'],copied['identity']['inode']) and
            copied['identity']['mode']=='0o444' and copied['identity']['uid']==os.getuid() and copied['identity']['nlink']==1,
            'Candidate must have an independent owned0444copy')
        acquisition=base.read_json(candidate['acquisition'])
        tag=acquisition['tag'];require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',tag or '') and
            source['path']==str(Path(job['model_dir'])/'managed-checkpoints'/(tag+'.pt')) and
            tag!=insurance['root_job']['insurance']['tag'] and tag!=job['startup_tag'],
            'Candidate tag is not unique/distinct from insurance/startup')
        require(acquisition['schema']=='robotron-owned-phase-snapshot-acquisition-v1' and
            acquisition['purpose']=='candidate' and acquisition['owner_before']==acquisition['owner_after']==insured and
            acquisition['model_dir']==job['model_dir'] and acquisition['experiment']==job['experiment'] and
            acquisition['source_checkpoint']==triple(source) and
            type(acquisition.get('client_count')) is int and acquisition['client_count'] in (0,192) and
            acquisition.get('stopped_absence','missing') is None and
            acquisition['phase_record_sha256']==job['running_phase']['record']['sha256'] and
            acquisition['boot_checkpoint']==job['running_phase']['boot_checkpoint'] and
            acquisition['clock_floor']==clock_max(insurance['clocks'],clocks),
            'Historical candidate acquisition/first-LATCH floor differs')
        transition=acquisition.get('completed_slot_transition')
        require(isinstance(transition,dict) and set(transition)=={
            'before','request','after','before_unix_s','request_unix_s','after_unix_s'},
            'Actual candidate request/completion transition required')
        times=[horizon.number(transition[key],key) for key in ('before_unix_s','request_unix_s','after_unix_s')]
        require(0<times[0]<=times[1]<=times[2],'Candidate request/completion chronology differs')
        def historical(pair,path):
            require(isinstance(pair,dict) and set(pair)=={'actual_pin','archive'},'Historical slot/archive pair required')
            actual,archive=pair['actual_pin'],pair['archive']
            require(set(actual)=={'path','sha256','bytes','identity'} and actual['path']==str(path) and
                re.fullmatch('[0-9a-f]{64}',actual['sha256'] or '') and
                type(actual['bytes']) is int and actual['bytes']>0 and
                set(actual['identity'])=={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'} and
                actual['identity']['bytes']==actual['bytes'] and archive['path']!=actual['path'] and
                archive['sha256']==actual['sha256'] and archive['bytes']==actual['bytes'] and
                archive['identity']['mode']=='0o444' and archive['identity']['uid']==os.getuid() and
                archive['identity']['nlink']==1,
                'Historical candidate slot/archive identity differs')
            return base.read_json(archive)
        slot=Path(job['model_dir'])/'managed_save.request.json.completed'
        if transition['before'] is not None:
            require(historical(transition['before'],slot)!={'tag':tag},'Candidate tag was already completed')
        requested=historical(transition['request'],Path(job['model_dir'])/'managed_save.request.json')
        completed=historical(transition['after'],slot)
        require(requested==completed=={'tag':tag},'Candidate historical request/completed tag differs')
    else:
        require(ending['candidate'] is None and 'candidate_requests_allowed' not in decision,
            'Incomplete ending cannot acquire a replacement candidate')
        require(horizon.POLICY['cutoff_s']<=decision['elapsed_s']<horizon.POLICY['ceiling_s'],
            'Incomplete ending must be at actual cutoff before owner ceiling')
    return dict(state=decision['state'],decision=ending['decision'],observer_job=ending['observer_job'],
        observation_floor=clocks,floor=clock_max(insurance['clocks'],clocks),
        candidate=copy.deepcopy(ending['candidate']),owner=copy.deepcopy(insured))


def load_v4():
    data = V4.read_bytes();require(hashlib.sha256(data).hexdigest() == V4_SHA,'Pinned v4 source changed')
    spec = importlib.util.spec_from_file_location('_raw_kl_transition_v4',V4)
    module = importlib.util.module_from_spec(spec);sys.modules[spec.name] = module
    exec(compile(data,str(V4),'exec'),module.__dict__)
    return module


def read_job(args, base):
    require(args.job and args.expected_job_sha256 and args.expected_controller_sha256,'Explicit actual root job/source hashes required')
    require(base.fingerprint(Path(__file__).resolve(),base.MAX_SOURCE)['sha256'] == args.expected_controller_sha256,'Adapter source differs')
    job_pin = base.fingerprint(args.job,MAX_JSON)
    require(job_pin['sha256'] == args.expected_job_sha256 and job_pin['identity']['mode'] == '0o444' and
        job_pin['identity']['uid']==os.getuid() and job_pin['identity']['nlink']==1,'Root job must be exact owned readonly metadata')
    job = json.loads(Path(args.job).read_text());require(base.fingerprint(args.job,MAX_JSON) == job_pin,'Root job changed')
    require(job['schema'] == SCHEMA and job['mode'] in ('activate_kl','return_ce'),'One transition only')
    output=base.canonical(job['output_directory'],False)
    require(not output.exists() and output.parent.is_dir(),'Output must be NEW')
    game = base.canonical(job['game_root']);require(base.canonical(job['model_dir']) == game/'models_dqn','Held model directory differs')
    require(Path(job['output_directory']).is_relative_to(game/'logs'),'Owned output must be under game logs')
    require(job['timeouts'] == dict(ready_s=600,save_s=60,cpu_s=120),'Precommitted transition deadlines differ')
    require(job['helper_pins']['v4']['path'] == str(V4) and job['helper_pins']['v4']['sha256'] == V4_SHA,'Wrong v4 helper')
    require(job['helper_pins']['controller']['path']==str(Path(__file__).resolve()) and
        job['helper_pins']['controller']['sha256']==args.expected_controller_sha256,'Adapter recurring source pin differs')
    require(job['phase_verifier']['script']['path'] == str(PHASE) and job['phase_verifier']['script']['sha256'] == PHASE_SHA,'Wrong phase verifier')
    for value in job['helper_pins'].values():base.pin(value,base.MAX_SOURCE)
    for value in job['static_pins']:base.pin(value,base.MAX_SOURCE)
    for value in (job['trial_core'],job['phase_verifier']['script'],job['phase_verifier']['strict_base'],job['protected_reference']):base.pin(value)
    require(job['phase_verifier']['strict_base']['sha256'] == STRICT_SHA and
        job['phase_verifier']['strict_base']['path']==str(PHASE.parent/'strict_phase_base.py'),'Wrong strict phase helper')
    require(job['helper_pins']['phase_script']==job['phase_verifier']['script'] and
        job['helper_pins']['phase_strict']==job['phase_verifier']['strict_base'],'Phase source pins must recur in static guards')
    core = base.read_json(job['trial_core']);require(core['phase_id'] == job['phase_id'] and core['mode'] == job['mode'],'Core operation differs')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,100}',job['phase_id'] or '') and
        re.fullmatch(r'[A-Za-z0-9_-]{1,120}',job['request_id'] or '') and
        re.fullmatch(r'[A-Za-z0-9_-]{1,80}',job['startup_tag'] or ''),'Invalid unique phase/request/save names')
    for name,key,schema,lock in (('stage_A','comparison_pass','robotron-raw-kl-stage-a-numeric-validation-v1','bcc1c696ed1ddbd18879e64cee01d55909b99c8401d908f636228d4c83b36551'),
            ('stage_B','readiness_pass','robotron-raw-kl-stage-b-private-v1','8edbe0082cb93939ebc9bfe6be922058f9c821addf72567f57d2c7a83b53b5fc')):
        proof = base.read_json(job['prerequisites'][name])
        require(proof['schema']==schema and proof['source_lock_sha256']==lock and proof['status'] == 'OBSERVATIONS_COMPLETE' and
            proof[key] is True and proof['owned_cleanup_complete'] is True,
            'Actual Stage A/B readiness prerequisite absent')
    release = base.read_json(job['prerequisites']['quality_release'])
    require(release['source_freeze_released'] is True and release['owned_cleanup_complete'] is True,
        'Quality finalization/resource release not established')
    require(len(job['before']['bindings']['actors']) == 192 and
        set(map(int,job['actor_masks'])) == {x['pid'] for x in job['before']['bindings']['actors']} and
        all(x == list(range(72)) for x in job['actor_masks'].values()) and job['worker_mask'] == list(range(72)), 'Original192/masks differ')
    expected_dropin = Path('/run/user')/str(os.getuid())/'systemd/user'/(job['trainer_unit']+'.d')/'91-per-priority-phase.conf'
    require(job['original_dropin']['path'] == str(expected_dropin),'Wrong dedicated override path')
    before = job['before'];env = before['environment'];latest = str(Path(job['model_dir'])/'robotron_dqn_latest.pt')
    require(env.get('DQN_RATCHET') == '0' and env.get('DQN_EXACT_GRAPH_CHECKPOINT') == latest,'Held latest-only exact graph boot differs')
    explicit = (env.get('ROBOTRON_DQN_MODEL_DIR') or '').strip()
    require((explicit or str(game/'models_dqn')) == job['model_dir'],'Held config default/explicit path differs')
    require(set(job['candidate_sources']) == set(CANDIDATE),'Exactly candidate5 required')
    for name,pin in job['candidate_sources'].items():
        base.pin(pin,base.MAX_SOURCE);require(pin['sha256'] == CANDIDATE[name],'Sealed candidate source differs')
    destinations = {str(game/'Scripts/dqn'/name) for name in CANDIDATE}
    require(not any(x['path'] in destinations or x['path'] in (str(Path(job['model_dir'])/'managed_save.request.json.completed'),
        job['settings_lifecycle']['initial']['path'],job['original_dropin']['path']) for x in job['static_pins']),
        'Mutable source/settings/completion/owned override must have explicit lifecycle, not static inode pins')
    validate_installed_phase(job,base,game,env)
    capture = env.get(FLAGS[0])
    require(not env.get(FLAGS[1]),'Unknown old trace session forbidden')
    if capture:
        dormant = base.read_json(job['completed_dormant_capture'])
        require(job['completed_dormant_capture']['path'] == str(Path(capture)/'final.json') and dormant['complete'] is True and
            dormant['status'] == 'EIGHT_INPUT_CE_CAPTURES_COMPLETE' and dormant['attempts_consumed'] == len(dormant['rows']) == 8 and not dormant['observer_errors'],
            'Only exactly completed dormant8 BEFORE session may retain a flag')
    else:require(job['completed_dormant_capture'] is None,'Unneeded capture adoption')
    require(job['current_completed_request']['path']==str(Path(job['model_dir'])/'managed_save.request.json.completed'),
        'Current completion must bind the actual mutable model slot')
    base.pin(job['current_completed_request'],MAX_JSON)
    validate_ending(job,base)
    base.validate_python_binding(job['verifier'],job['insurance_verification'],hash_executable=True)
    return job,job_pin



def archive_metadata(base, value, target):
    """Independent readonly metadata copy; never relax V4 checkpoint copying."""
    source,target=Path(value['path']),Path(target)
    require(source.suffix != '.pt' and target.suffix in ('.json','.txt'), 'Metadata archive cannot copy model bytes')
    require(target.is_absolute() and target==target.resolve(strict=False) and
        target.parent==target.parent.resolve(strict=True), 'Noncanonical metadata archive destination')
    base.pin(value,base.MAX_SOURCE)
    require(0<value['bytes']<=base.MAX_SOURCE and value['identity']['uid']==os.getuid() and
        value['identity']['nlink']==1, 'Metadata archive source size/owner/link differs')
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as src,target.open('xb') as dst:
        require(base.identity(os.fstat(src.fileno()))==value['identity'], 'Metadata open identity changed')
        for chunk in iter(lambda:src.read(1<<20),b''):dst.write(chunk)
        require(base.identity(os.fstat(src.fileno()))==value['identity'], 'Metadata changed while archiving')
        dst.flush();os.fchmod(dst.fileno(),0o444);os.fsync(dst.fileno())
        sealed=base.identity(os.fstat(dst.fileno()))
    base.fsync_directory(target.parent)
    require(base.fingerprint(source,base.MAX_SOURCE)==value, 'Metadata source path changed')
    copied=base.fingerprint(target,base.MAX_SOURCE)
    require(copied['sha256']==value['sha256'] and copied['bytes']==value['bytes'] and
        copied['identity']['mode']=='0o444' and copied['identity']['uid']==os.getuid() and
        copied['identity']['nlink']==1 and copied['identity']==sealed and
        (copied['identity']['device'],copied['identity']['inode'])!=
        (value['identity']['device'],value['identity']['inode']), 'Independent metadata archive differs')
    return copied


def phase_metadata(base, phase, context, directory):
    """Archive every consumed boot report and historical context before CPU launch."""
    directory.mkdir(mode=0o700)
    phase,context=copy.deepcopy(phase),copy.deepcopy(context)
    evidence={}
    def archived(key,value):
        copied=archive_metadata(base,value,directory/(key+'.json'))
        evidence[key]=dict(original=value,archive=copied)
        return copied
    phase['boot_verification']=archived('boot-CPU-proof',phase['boot_verification'])
    for key in ('archived_control','archived_trainer_unit'):
        context[key]=archived(key,context[key])
    context['provenance']=[archived('provenance-%03d'%i,value) for i,value in enumerate(context['provenance'])]
    return phase,context,evidence


def validate_installed_phase(job,base,game,env):
    """Only already-installed candidate5, with the genuine current founder phase."""
    require(job['sources']==[] and job['running_phase'] is not None,
        'Installed-phase transition requires empty source transaction and authentic running phase')
    for name,value in CANDIDATE.items():
        require(job['before']['bindings']['source_hashes'][str(game/'Scripts/dqn'/name)]==value,
            'Installed source is not exact candidate5: '+name)
    metric='ce' if job['mode']=='activate_kl' else 'kl'
    running=job['running_phase'];record=base.read_json(running['record']);boot=base.read_json(running['boot_verification'])
    require(record['metric']==metric and running['expected']==expected_start(record,running['record'],boot) and
        record['action']=='start' and record['checkpoint']==running['boot_checkpoint'] and
        boot['status']=='PASS' and boot.get('phase_metadata_verified') is True and
        boot['sha256']==running['boot_checkpoint']['sha256'] and boot['bytes']==running['boot_checkpoint']['bytes'] and
        env.get('DQN_PER_PRIORITY_METRIC')==metric and env.get('DQN_PRIORITY_PHASE_RECORD')==running['record']['path'] and
        env.get('DQN_PRIORITY_PHASE_RECORD_SHA256')==running['record']['sha256'],
        'Current phase metric/record/founder/boot proof/environment differs')
    require(not any(env.get(flag) for flag in FLAGS) and job['completed_dormant_capture'] is None,
        'Installed-phase transition requires both capture flags absent')


def runtime_class(base):
    fingerprint,read_json,publish = base.fingerprint,base.read_json,base.publish
    class Runtime(base.Runtime):
        def __init__(self,job,output):
            self.job,self.output=copy.deepcopy(job),output
            self.job['readiness_timeout_s']=job['timeouts']['ready_s']
            tools=Path(job['helper_pins']['live_host']['path']).parent
            sys.dont_write_bytecode=True;sys.path.insert(0,str(tools))
            self.primitives=base.load_module(job['helper_pins']['live_host']['path'],'raw_kl_owned_primitives')
            self.metrics=self.primitives.metrics
            for key,module in (('metrics',self.metrics),('identity',self.metrics.identity),('protection',self.primitives.protection)):
                require(str(Path(module.__file__).resolve()) == job['helper_pins'][key]['path'],'Unexpected dependency '+key)
            self.banks=base.load_module(job['helper_pins']['bank_state']['path'],'raw_kl_bank_state')
            outer=self
            class Host(self.primitives.LiveHost):
                def runtime_dropin(self):return Path(job['original_dropin']['path'])
                def no_sidecars(self):super().no_sidecars();outer.exclusive()
            self.host=Host(job['trainer_unit'],job['fleet_unit']);self.phase='before'
            self.lineages={};self.current_checkpoint=None;self.last_retired=None;self.retirement_candidate=None;self.retired_owner=None
            self.cpu_attempts={};self.verification_failed=False;self.lease_fd=None;self.pending=None
            self.current_completed=copy.deepcopy(job['current_completed_request'])
            self.settings=base.SettingsLifecycle(job['settings_lifecycle'],job['model_dir'])
            self.insurance=read_json(job['insurance_verification']);self.insured=self.insurance['root_job']['insurance']['trainer'];self.floor=four(self.insurance['clocks'])
            require(self.insurance['status']=='PASS' and self.insurance['mode']=='insurance' and self.insurance['root_job']['experiment']==job['experiment'] and
                self.insurance['root_job']['source_control_context']['model_dir']==job['model_dir'],'Wrong fresh insurance scope')
            saved=read_json(job['insurance_receipt']);require(saved['tag']==self.insurance['root_job']['insurance']['tag'] and
                saved['source']['sha256']==self.insurance['root_job']['source']['sha256'],'Wrong insurance request')
            self.original_dropin=None if job['original_dropin']['content_base64'] is None else base64.b64decode(job['original_dropin']['content_base64'])
            require(self.host._dropin_bytes()==self.original_dropin,'Owned phase override drift')
            self.host.dropin_expected=self.original_dropin;self.record=None;self.record_pin=None;self.start_request=None
            self.recovery_dropin=None;self.dropin=None
            self.ending=validate_ending(job,base)

        def request_guard(self):
            path=Path(self.job['model_dir'])/'managed_save.request.json'
            slot=Path(str(path)+'.completed')
            if self.pending is None:
                require(not path.exists(),'Unowned pending model request')
                require(fingerprint(slot,MAX_JSON)==self.current_completed,'Current completed slot changed outside owned transition')
                return
            pending=self.pending
            if not pending['publication']['published']:
                require(not path.exists(),'An unknown request appeared during private preparation')
                require(fingerprint(slot,MAX_JSON)==self.current_completed,'Current completed slot changed during invisible preparation')
                return
            def is_owned_completion(observed):
                return (observed['sha256']==pending['pin']['sha256'] and
                    request_identity(observed['identity'])==request_identity(pending['pin']['identity']) and
                    observed['identity']['nlink']==1 and read_json(observed)=={'tag':pending['tag']})
            try:observed=fingerprint(path,MAX_JSON)
            except FileNotFoundError:
                # os.replace(request,completed) is the one source-proven move.
                require(is_owned_completion(fingerprint(slot,MAX_JSON)),
                    'Owned request vanished without the same published inode completing')
            else:
                require(observed['sha256']==pending['pin']['sha256'] and
                    request_identity(observed['identity'])==request_identity(pending['pin']['identity']) and observed['identity']['nlink']==1,
                    'Owned request replaced externally')
                # The consumer may finish between the request and slot reads.
                completed=fingerprint(slot,MAX_JSON)
                require(completed==self.current_completed or is_owned_completion(completed),
                    'Completed slot changed outside this owned publication')

        def exclusive(self):
            # Unclassified /proc churn only; all classified guard failures remain fatal.
            for entry in Path('/proc').iterdir():
                if not entry.name.isdecimal() or int(entry.name)==os.getpid():continue
                try:argv=(entry/'cmdline').read_bytes().split(b'\0')
                except OSError as e:
                    if e.errno in (errno.ENOENT,errno.ESRCH):continue
                    raise
                names=set(base.BLOCKED)|{'run_raw_kl_transition.py','verify_phase_snapshot.py'}
                require(not any(os.path.basename(os.fsdecode(a)) in names for a in argv if a),'Competing owned helper '+entry.name)
            self.request_guard()
            require(not any(x.is_dir() for x in Path('/dev/shm').glob('robotron-snapshot-smoke-*')),'Private diagnostic tmpfs remains')
            app=Path('/sys/fs/cgroup')/self.job['before']['trainer']['ControlGroup'].lstrip('/')
            for group in app.parent.glob('robotron-snapshot-smoke-*'):
                members=list(group.rglob('cgroup.procs'));require(len(members)<=256 and all(not x.read_text().split() for x in members),'Private cgroup remains populated')

        def inspect(self,phase):
            self.static();current=self.host.describe()
            env=self.job['before']['environment'] if phase=='before' else selected_environment(self.job['before']['environment'],self.record['metric'],self.record_pin)
            base.binding_matches(current,self.job['before'],self.expected_sources(phase),env)
            require(current['trainer']['Restart']==('no' if self.host.dropin_expected is not None else self.job['before']['trainer']['Restart']) and
                self.host._dropin_bytes()==self.host.dropin_expected,'Owned Restart=no override drift')
            for actor in current['bindings']['actors']:
                require(sorted(os.sched_getaffinity(actor['pid']))==self.job['actor_masks'][str(actor['pid'])],'Original actor mask drift')
            require(self.host.metric_host.mask(current['bindings']['worker'])==self.job['worker_mask'],'Inference mask drift')
            return current

        def start_phase(self):
            self.static();self.absence();require(fingerprint(self.current_checkpoint['source']['path'])==self.current_checkpoint['source'],'Newest boot bytes changed')
            self.record=start_record(self.job['mode'],self.job['phase_id'],self.job['trial_core']['sha256'],self.job['model_dir'],self.current_checkpoint['source'],read_json(self.current_checkpoint['verification']))
            self.record_pin=publish(self.output/'phase-record.json',self.record)
            env=selected_environment({},self.record['metric'],self.record_pin)
            require(all(not any(c in str(v) for c in ('\n','"','%')) for v in env.values()),'Unsafe static override value')
            lines=['[Service]','Restart=no']+['Environment="'+k+'='+v+'"' for k,v in env.items()]+['UnsetEnvironment='+' '.join(FLAGS)]
            self.dropin=('\n'.join(lines)+'\n').encode();self.host.write_dropin(self.dropin,self.host.dropin_expected)
            request=dict(schema='robotron-live8-owned-trainer-start-request-v1',insured_trainer=self.insured,
                unit=self.job['trainer_unit'],cgroup=self.host.trainer_cgroup,experiment=self.job['experiment'],model_dir=self.job['model_dir'],
                source_phase='after',owned_start_requested=True,request_id=self.job['request_id'],phase_record=self.record_pin,
                trial_core=self.job['trial_core'],boot_id=self.job['boot_id'],monotonic_s=time.monotonic(),unix_s=time.time())
            require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.job['boot_id'],'Boot changed')
            self.start_request=publish(self.output/'owned-start-request.json',request)
            self.phase='after'  # Source transaction and selected startup env are already complete.
            self.host.start();owner=self.trainer_id()
            lineage=publish(self.output/'owned-start-lineage.json',dict(schema='robotron-live8-owned-restart-lineage-v1',insured_trainer=self.insured,
                retired_trainer=owner,authorized_start_adopted=True,unknown_replacement_adopted=False,experiment=self.job['experiment'],
                model_dir=self.job['model_dir'],source_phase='after',request_id=self.job['request_id'],start_request=self.start_request))
            self.lineages[owner['pid']]=lineage
            return owner

        def phase_sources(self,label):
            directory=self.output/(label+'-sources');directory.mkdir(mode=0o700)
            expected=self.expected_sources('after' if self.phase=='after' else 'before');pairs={}
            for name in SOURCE_NAMES:
                path=Path(self.job['game_root'])/'Scripts/dqn'/name
                current,archive=base.exclusive_copy(path,directory/name)
                require(current['sha256']==expected[str(path)],'Unexpected phase source '+name)
                pairs[name]=dict(current=current,archive=archive)
            context=copy.deepcopy(self.job['verifier']['context'])
            context['model_package']={name:pairs[name]['current'] for name in ('model.py','config.py','learning_control.py','__init__.py')}
            return pairs,context

        def cpu_phase(self,label,purpose,owner,source,copied,phase,acquisition,ledger_key):
            require(ledger_key not in self.cpu_attempts,'Phase CPU already attempted; no retry')
            root=self.output/label;root.mkdir(mode=0o700)
            pairs,context=self.phase_sources(label)
            phase,context,archives=phase_metadata(base,phase,context,root/'metadata')
            publish(root/'metadata-archives.json',archives)
            acquisition_pin=publish(root/'acquisition.json',acquisition)
            spec=dict(purpose=purpose,owner=owner,observed_clients=acquisition['client_count'],phase_record=phase['record'],
                boot_checkpoint=phase['boot_checkpoint'],boot_verification=phase['boot_verification'],expected_phase=phase['expected'],
                acquisition=acquisition_pin,sources=pairs)
            job=dict(schema='robotron-phase-snapshot-checkpoint-CPU-job-v1',verifier_sha256=PHASE_SHA,strict_phase_base_sha256=STRICT_SHA,
                original_strict_base_sha256=self.job['verifier']['script']['sha256'],experiment=self.job['experiment'],source=source,
                verification_copy=copied,clock_floor=acquisition['clock_floor'],source_control_context=context,
                output_directory=str(root/'cpu-output'),phase_snapshot=spec)
            jp=publish(root/'cpu-job.json',job);base.validate_python_binding(self.job['verifier'],self.job['insurance_verification'],hash_executable=True)
            env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
            for key in ('LD_PRELOAD','PYTHONPATH'):env.pop(key,None)
            argv=[self.job['verifier']['python'],'-Xgil=0','-I','-B',str(PHASE),'--execute','--job',jp['path'],
                '--expected-job-sha256',jp['sha256'],'--expected-verifier-sha256',PHASE_SHA]
            try:
                with (root/'cpu.stdout').open('xb') as out,(root/'cpu.stderr').open('xb') as err:
                    with self.metrics.block_restore_signals():self.cpu_attempts[ledger_key]='started'
                    completed=subprocess.run(argv,env=env,stdout=out,stderr=err,timeout=120,check=False)
            except BaseException:
                if ledger_key in self.cpu_attempts:self.verification_failed=True
                raise
            publish(root/'cpu-completion.json',dict(argv=argv,exit_code=completed.returncode))
            if completed.returncode!=0:self.verification_failed=True
            require(completed.returncode==0,'First phase CPU verification failed; no retry')
            try:
                pin=fingerprint(root/'cpu-output/cpu-verification.json',MAX_JSON);proof=read_json(pin)
                require(proof['status']=='PASS' and proof['root_job']==job and proof['phase_metadata_verified'] is True and
                    proof['sha256']==source['sha256'],'Phase CPU proof mismatched')
            except BaseException:self.verification_failed=True;raise
            pin=archive_metadata(base,pin,root/'cpu-report-readonly.json')
            self.cpu_attempts[ledger_key]='passed'
            return pin,proof

        def post_stop_ending(self,retired):
            # Every numeric check is AFTER exact known KL retirement. Nothing in
            # this limb can extend the pre-start3600s owner-presence ceiling.
            self.static();self.absence()
            require(self.job['mode']=='return_ce' and retired==self.retired_owner==self.insured==self.ending['owner'],
                'Post-stop candidate belongs to another retired owner')
            self.floor=clock_max(self.floor,self.ending['floor'])
            result=dict(state=self.ending['state'],decision=self.ending['decision'],
                floor_before_candidate=copy.deepcopy(self.floor),candidate_CPU=None,
                scope='Historical observation floor; no pre-stop CPU or exact optimizer-cutoff claim')
            candidate=self.ending['candidate']
            if candidate is not None:
                acquisition=read_json(candidate['acquisition'])
                require(acquisition['clock_floor']==self.floor,'Candidate floor changed after first ending validation')
                pin,proof=self.cpu_phase('ending-candidate-CPU','candidate',retired,
                    candidate['source'],candidate['verification_copy'],self.job['running_phase'],acquisition,
                    'ending-candidate:'+acquisition['tag'])
                saved=four(proof['clocks'])
                require(all(saved[key]>=self.floor[key] for key in CLOCKS),
                    'Candidate CPU clocks predate actual first-LATCH/insurance floor')
                self.floor=clock_max(self.floor,saved)
                result.update(candidate_CPU=pin,candidate_saved_clocks=saved)
            self.absence()
            result['required_newest_stopped_floor']=copy.deepcopy(self.floor)
            # Existing stopped_checkpoint passes this stronger floor to the
            # unchanged strict wrapper BEFORE any CE start is requested.
            return result

        def stopped_checkpoint(self,retired,label):
            self.static();self.absence();key=base.SettingsLifecycle.key(retired)
            require(retired==self.retired_owner and key not in self.cpu_attempts,'Unregistered/repeated stopped CPU')
            root=self.output/(label+'-copy');root.mkdir(mode=0o700)
            source,copied=base.exclusive_copy(Path(self.job['model_dir'])/'robotron_dqn_latest.pt',root/'latest-readonly-copy.pt')
            absence=publish(root/'absence.json',dict(schema='robotron-live8-owned-trainer-absence-v1',trainer=retired,unit_main_pid=0,
                unit_active_state='inactive',old_process_absent=True,owned_cgroup_empty=True,latest_path=source['path']))
            phase=self.job['running_phase']
            acquisition=dict(schema='robotron-owned-phase-snapshot-acquisition-v1',purpose='newest_stopped',experiment=self.job['experiment'],
                model_dir=self.job['model_dir'],owner_before=retired,owner_after=retired,client_count=192,source_checkpoint=triple(source),
                clock_floor=self.floor,phase_record_sha256=phase['record']['sha256'],boot_checkpoint=phase['boot_checkpoint'],
                tag=None,completed_slot_transition=None,stopped_absence=absence)
            pin,proof=self.cpu_phase(label,'newest_stopped',retired,source,copied,phase,acquisition,key)
            self.absence();require(fingerprint(source['path'])==source,'Newest stopped bytes changed')
            self.current_checkpoint=dict(source=source,verification=pin,clocks=proof['clocks']);self.last_retired=retired;self.cpu_attempts[key]='passed'
            return self.current_checkpoint

        def startup_snapshot(self,raw):
            self.static();owner=self.trainer_id();zero_replay(raw,owner['pid'])
            root=self.output/'startup-save';root.mkdir(mode=0o700);model=Path(self.job['model_dir'])
            target=model/'managed-checkpoints'/(self.job['startup_tag']+'.pt')
            require(all(not Path(str(target)+s).exists() for s in ('','.tmp','.bak')) and not (model/'managed_save.request.json').exists(),'Unique startup snapshot already exists')
            transition=dict(before=None,before_unix_s=time.time())
            slot=model/'managed_save.request.json.completed'
            if slot.exists():
                actual,archive=base.exclusive_copy(slot,root/'completed-before.json');transition['before']=dict(actual_pin=actual,archive=archive)
            failed=model/'managed_save.request.json.failed'
            if failed.exists():base.exclusive_copy(failed,root/'failed-before.json')
            with self.metrics.block_restore_signals():
                pending=publish_request(base,model,root/'request.json',self.job['startup_tag'],lambda value:setattr(self,'pending',value))
            transition.update(request=dict(actual_pin=pending['pin'],archive=pending['archive']),
                request_unix_s=pending['publication']['before_expose_unix_s'])
            deadline=time.monotonic()+60
            while True:
                require(time.monotonic()<=deadline,'Unique startup save did not complete; no retry')
                self.static();require(self.trainer_id()==owner,'Startup save owner replaced')
                if slot.exists():
                    observed=fingerprint(slot,MAX_JSON)
                    if read_json(observed)=={'tag':self.job['startup_tag']}:
                        actual,archive=base.exclusive_copy(slot,root/'completed-after.json')
                        require(request_identity(actual['identity'])==request_identity(pending['pin']['identity']) and actual['identity']['nlink']==1,
                            'Completed request is not the published owned inode')
                        pending['publication']['completed_identity']=actual['identity']
                        transition.update(after=dict(actual_pin=actual,archive=archive),after_unix_s=time.time());break
                if failed.exists() and read_json(fingerprint(failed,MAX_JSON))=={'tag':self.job['startup_tag']}:raise RuntimeError('Actual startup save failed; no retry')
                time.sleep(1)
            with self.metrics.block_restore_signals():
                self.current_completed=copy.deepcopy(actual);self.pending=None
            self.static();after=self.trainer_id();require(after==owner,'Snapshot acquisition owner changed')
            source,copied=base.exclusive_copy(target,root/'startup-readonly-copy.pt')
            boot=read_json(self.current_checkpoint['verification'])
            phase=dict(record=self.record_pin,boot_checkpoint=triple(self.current_checkpoint['source']),boot_verification=self.current_checkpoint['verification'],
                expected=expected_start(self.record,self.record_pin,boot))
            acquisition=dict(schema='robotron-owned-phase-snapshot-acquisition-v1',purpose='startup',experiment=self.job['experiment'],
                model_dir=self.job['model_dir'],owner_before=owner,owner_after=after,client_count=0,source_checkpoint=triple(source),
                clock_floor=four(raw),phase_record_sha256=self.record_pin['sha256'],boot_checkpoint=phase['boot_checkpoint'],
                tag=self.job['startup_tag'],completed_slot_transition=transition,stopped_absence=None,
                request_publication=pending['publication'])
            pin,proof=self.cpu_phase('startup-phase-CPU','startup',owner,source,copied,phase,acquisition,'startup:'+self.job['startup_tag'])
            return dict(phase_CPU=pin,phase=phase,snapshot_source=source,snapshot_copy=copied,acquisition=acquisition,
                saved_current_clocks=four(proof['clocks']),saved_boot_clocks=four(boot['clocks']))

        def ready_transport(self, phase, banks, *, actors):
            deadline = time.monotonic() + self.job["readiness_timeout_s"]
            while time.monotonic() < deadline:
                self.static()
                owner = self.trainer_id()  # Never adopt a PID seen only by a polling observer.
                try:
                    raw = self.raw_api()
                except (OSError, json.JSONDecodeError):
                    time.sleep(1); continue
                exposure = raw.get("host_pipeline", {}).get("learning_exposure", {}).get("optimizer", {})
                graphs = raw.get("host_pipeline", {}).get("inference_graphs", {})
                if (exposure.get("process_id") != owner["pid"] or not graphs.get("ready")
                        or exposure.get("total", {}).get("outcomes_recorded", 0) <= 0
                        or actors and raw.get("client_count") != 192):
                    time.sleep(1); continue
                current = self.inspect(phase)
                require(all(raw[key] >= self.current_checkpoint["clocks"][key] for key in CLOCKS), "Loaded clocks regressed behind actual stopped latest")
                require(raw.get("managed_experiment") == self.job["experiment"], "Loaded branch label differs")
                transition_events = []
                if actors:
                    # Arm the runtime reader BEFORE the final transition scan, so
                    # the boundary has overlapping coverage rather than a gap.
                    self.host.metric_host.configure_logs(current["bindings"]["logs"])
                    transition_events = self.fault_scan()
                    row = self.host.capture()
                else:
                    row = self.metrics.compact_api(raw)
                    row.update(csv=self.job["baseline_csv"], observed_unix_s=time.time(), observed_monotonic_s=time.monotonic(), log_errors=[])
                    row["csv_scope"] = "Held pre-stop baseline; actual new CSV is checked after192 reconnect"
                local = dict(batch_size=4096, replay_cap=8, initial_snapshot=dict(csv=self.job["baseline_csv"]),
                    exposure_identity={kind:self.metrics.exposure_key(row["exposure"][kind]) for kind in ("optimizer", "replay")})
                require(all(value["process_id"] == owner["pid"] for value in local["exposure_identity"].values()), "Exposure epoch is not owned by the new trainer")
                issues = self.metrics.api_issues(row, local)
                if not actors:
                    issues = [issue for issue in issues if issue != "client_count"]
                    require(raw["client_count"] == 0, "Paused actors unexpectedly connected before admission")
                require(not issues, "Postload guards: " + repr(issues))
                if not actors:
                    proof = self.host.bank_load_proof(current)
                    stdout = proof["stdout"]
                    with Path(stdout["path"]).open("rb") as stream:
                        info = os.fstat(stream.fileno())
                        require((info.st_dev,info.st_ino) == (stdout["device"],stdout["inode"]), "New stdout inode changed before boot proof")
                        stream.seek(proof["start_byte"])
                        payload = stream.read(proof["end_byte"]-proof["start_byte"])
                    require(hashlib.sha256(payload).hexdigest() == proof["sha256"], "Owned boot log increment changed")
                    proof["model_boot"] = base.boot_log_proof(payload, self.current_checkpoint["source"]["path"])
                    proof["verified_saved_clocks"] = self.current_checkpoint["clocks"]
                    proof["API_loaded_clock_fields"] = {key:raw.get(key) for key in
                        ("loaded_training_steps", "loaded_optimized_samples", "loaded_frame_count", "loaded_learner_frame_count")}
                    require(fingerprint(self.current_checkpoint["source"]["path"]) == self.current_checkpoint["source"], "Boot latest changed from CPU-verified bytes")
                    require(proof["counts"] == {name.upper():value["counts"] for name,value in banks["banks"].items()}, "Loaded bank counts differ from selected stopped generations")
                    self.banks.assert_unchanged(banks, self.job["bank_spec"])
                    maps = self.banks.verify_maps(owner["pid"], banks)
                else:
                    proof, maps = None, None
                return dict(binding=current, api=row, bank_load_proof=proof, mapped_ring=maps, transition_events=transition_events)
            raise RuntimeError("Owned trainer readiness exceeded fixed600s")
    return Runtime


def source_state(sources):
    """Bounded bytes classification only; never put imported source bodies in JSON."""
    result=[]
    for entry in sources.entries:
        data=sources.observed(entry)
        before,after=sources.staged[entry['destination']]
        result.append(dict(destination=entry['destination'],present=data is not None,
            sha256=None if data is None else hashlib.sha256(data).hexdigest(),
            bytes=0 if data is None else len(data),
            matches_before=data==before,matches_after=data==after,
            classification='known' if data in (before,after) else 'unknown'))
    return result


def transition(runtime,sources,base):
    r=runtime
    result=dict(schema=RESULT_SCHEMA,status='RUNNING',mode=r.job['mode'],qualification_pass=False,
        manual_recovery_required=False,events=[],limitations=[
        'Ordinary newest save may omit optimizer/FIFO/bank tails; no coherent anchor.',
        'Phase started_from boot clocks differ from observed postboot clocks; overshoot retained.',
        'Disk/header/maps are not bank RAM byte equality or full-ring numeric verification.',
        'This adapter performs one transition only, never a trial/quality/promotion loop.'])
    def event(name,**value):
        row=dict(phase=name,unix_s=time.time(),**value);result['events'].append(base.publish(r.output/('event-%02d.json'%len(result['events'])),row))
    primary=None
    try:
        before=r.initial();sources.stage();event('initial',owner=r.trainer_id())
        r.host.begin_transition_logs(before['bindings']['logs'],before['trainer_stdout'])
        r.host.pause(dict(initial=r.job['before']))
        retired=r.stop_owned(before);event('stopped',owner=retired)
        if r.job['mode']=='return_ce':
            ending=r.post_stop_ending(retired);event('ending_candidate_CPU_and_floor',proof=ending)
        boot=r.stopped_checkpoint(retired,'newest-stopped');event('newest_CPU',checkpoint=boot)
        banks=r.banks.stopped_state(r.job['bank_spec']);event('stopped_disk_state',banks=banks)
        sources.reconcile('after',r.absence,r.metrics.block_restore_signals)
        owner=r.start_phase();event('new_owner',owner=owner,start_request=r.start_request,phase_record=r.record_pin)
        loaded=r.ready_transport('after',banks,actors=False)
        raw=r.raw_api();require(raw['client_count']==0,'Original fleet admitted before startup proof')
        zero_replay(raw,owner['pid']);startup=r.startup_snapshot(raw)
        before_resume=r.raw_api();require(before_resume['client_count']==0,'Unexpected startup clients')
        zero_replay(before_resume,owner['pid']);before_pin=base.publish(r.output/'API-before-resume.json',before_resume)
        r.inspect('after');r.banks.assert_unchanged(banks,r.job['bank_spec'])
        event('loaded_before_resume',proof=loaded,startup=startup,API=before_pin)
        resumed=base.resume_all(r.host);result['initial_resume']=resumed
        require(not resumed['failures'],'Some original actors could not resume')
        healthy=r.ready_transport('after',banks,actors=True)
        post=r.raw_api();require(post['client_count']==192,'Fresh healthy192 sample absent')
        require(post['host_pipeline']['learning_exposure']['optimizer']['process_id']==owner['pid'],'Healthy API owner changed')
        post_pin=base.publish(r.output/'API-after192.json',post)
        result.update(status='READY',owner=owner,start_request=r.start_request,phase_record=r.record_pin,
            phase_record_spec=r.record,trial_core=r.job['trial_core'],boot_checkpoint=boot,
            boot_four_clocks=four(base.read_json(boot['verification'])['clocks']),startup_phase_proof=startup,
            before_resume_api_PIN=before_pin,after192_api_PIN=post_pin,healthy192_monotonic_s=time.monotonic(),
            transport_readiness=healthy,installed_sources=r.expected_sources('after'),
            restart_policy='no; a new immutable newest-bound record is required before any intended later restart',
            future_watcher='Root verifies/decodes start_request and before_resume_api_PIN into separately pinned observer job; no observer invoked here')
    except BaseException as error:
        primary=error;result.update(status='FAILED',error=repr(error),traceback=traceback.format_exc(),manual_recovery_required=True)
        # End a newly requested treatment only if its exact requested owner was
        # actually adopted. Never stop an unknown replacement or retry a start.
        if r.start_request is not None:
            try:
                unit=r.host.unit(r.job['trainer_unit'])
                if unit['MainPID']!='0':
                    require(r.host.known_trainer is not None,'Unadopted process; manual only')
                    # A fault after some SIGCONT requires a fresh owned pause.
                    # Preserve unresolved suffix records from the earlier undo.
                    for actor in r.job['before']['bindings']['actors']:
                        if actor not in r.host.paused:
                            with r.metrics.block_restore_signals():
                                r.host.paused.append(actor)
                                r.host.signal_actor(actor,signal.SIGSTOP)
                    r.host.wait_paused()
                    result['failed_new_owner_stopped']=r.stop_owned()
                else:r.absence()
            except BaseException as cleanup:result.setdefault('cleanup_errors',[]).append(repr(cleanup))
    finally:
        with r.metrics.block_restore_signals():undo=base.resume_all(r.host)
        result['final_resume']=undo
        if undo['failures']:result['manual_recovery_required']=True
        result['CPU_ledger']=dict(r.cpu_attempts)
        result['owned_request_at_terminal']=r.pending
        if result['status']!='READY':
            try:result['known_source_state']=source_state(sources)
            except BaseException as error:result.setdefault('evidence_errors',[]).append(repr(error))
    return result,primary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch',action='store_true');parser.add_argument('--job',type=Path)
    parser.add_argument('--expected-job-sha256');parser.add_argument('--expected-controller-sha256')
    args=parser.parse_args(argv)
    if not args.launch:
        print('PLAN_ONLY: one root-bound raw-KL/CE transition; no reads/imported helpers/runtime/actions')
        return 0
    runtime=None;output=None
    try:
        require(not any(n=='torch' or n.startswith(('torch.','numpy','dqn')) for n in sys.modules),'Fresh stdlib-only parent required')
        base=load_v4();job,jp=read_job(args,base)
        output=Path(job['output_directory']);output.mkdir(mode=0o700)
        base.publish(output/'root-job.json',job);backups=output/'sources';backups.mkdir(mode=0o700)
        runtime=runtime_class(base)(job,output)
        with runtime.metrics.interrupt_handlers():result,primary=transition(runtime,base.Sources(job['sources'],backups),base)
        result.update(root_job=jp,finished_unix_s=time.time())
        base.publish(output/'result.json',result)
        print(json.dumps(dict(status=result['status'],manual_recovery_required=result['manual_recovery_required'],output=str(output)),indent=2))
        return 0 if result['status']=='READY' and not result['manual_recovery_required'] else 1
    except BaseException as error:
        if output is not None:
            try:base.publish(output/'controller-error.json',dict(error=repr(error),traceback=traceback.format_exc()))
            except BaseException:pass
        try:traceback.print_exc()
        except BaseException:pass
        return 1
    finally:
        if runtime is not None:runtime.close()


if __name__=='__main__':raise SystemExit(main())
