"""One prospective SAME-.25 CE4096 continuation: label-only, barrier, first durable8+8 endpoint.

Default PLAN reads nothing. Reuses sealed concrete health/Snapshot/CPU-job code.
No trainer stop, CPU launch, evaluation, restoration or qualification action.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import traceback

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
Q=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
SCHEMA='robotron-live-ce-lr-continuation-case-v1'
RESULT_SCHEMA='robotron-live-ce-lr-continuation-result-v1'
FIXED_SOCKET='f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed'
ACTIVATION_RESULT=RUN/'rejected-gap-healthy-activation-original01-20261018/result.json'
ACTIVATION_SHA='f47b861115c62a87097f6eef0750f9c07db8a6876d59c87ab0a5ff0801a19621'
ACTIVATION_ADOPTION=RUN/'rejected-gap-healthy-activation-root-preparation-20261018/root-actual-activation-canonical-adoption.json'
ADOPTION_SHA='490c7cb2de233ded3a9cd6c06d7c3c1d0006c3b714a526a584fe085e13a3ed0b'
QUALITY_RELEASE_SHA='46f10a5e95dee9bc324f6e4496720f055d5248495946635b6c5eb450d9d8a145'
FOUNDER='75ec8703405edfb250100006cab8ff44a364cbc84e33583697a985306fd21f10'
ACTUAL_OWNER={'pid':2863379,'starttime_ticks':39797375,'unit':'robotron-managed-run-26-d3b365c9-trainer.service',
    'invocation_id':'5a8bfc5e10674a8e9169978804378393',
    'cgroup':'/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-managed-run-26-d3b365c9-trainer.service'}

DEPS={
 'entry':(Q/'lr25_prechange_entry_capture_proposal/capture_entry.py','f9eb356ee7d43d549a0e7ffe504afc20c4a717c39890ac4a79d414b9b8bc8003'),
 'driver':(Q/'lr25_hot_window_driver_reviewed2_proposal/run_hot_window.py','35c774c87827252ec623211110f887e98da6da728cb67b2cfa039f894f5a33b5'),
 'ops':(RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py','d525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'),
 'capture':(Q/'recovered_live_ce_candidate_capture_proposal/capture_live_CE_candidate.py','7be0eaf012e208299548f131fd42651239740692d58b8a6d997a6eee6733e46c'),
 'snapshot':(Q/'live_one_trial_installed_ce_revision2_proposal/early_insurance.py','0112da455fd0c3c7b711cda2ff59f8575a637f2544ec37f9ad68ad2698b0dab4'),
 'phase':(GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py','14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'),
 'recipe':(Path(__file__).with_name('recipe.py'),'9bc9a24f5f36c5dbe4f6385c1f47a5698bcda0bd6178f7546b263ee136aa1c3a'),
 'observer':(GAME/'tools/live_lr_recipe_continuation_proposal/observer.py','11380275b544eb7196d33d92b1fbe28a1ae057404120419a2cfa447410c7e430'),
}
CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count')

def require(value,message):
    if not value:raise RuntimeError(message)

def fingerprint(path,limit=4<<20):
    path=Path(path);require(path.is_absolute() and path==path.resolve(strict=True),'Canonical input required')
    def ident(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        before=os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1 and
            0<before.st_size<=limit,'Owned bounded input required')
        raw=stream.read(limit+1)
        require(len(raw)==before.st_size and ident(before)==ident(os.fstat(stream.fileno()))==ident(path.lstat()),'Input changed')
    return raw,dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=ident(before))

def pinned(pin,raw_only=False):
    raw,actual=fingerprint(pin['path']);require(actual==pin and actual['identity']['mode']=='0o444','Exact readonly metadata required')
    return raw if raw_only else json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite metadata: '+x)))

def load(name):
    path,sha=DEPS[name];require(isinstance(sha,str) and len(sha)==64,'Unsealed source dependency: '+name)
    raw,pin=fingerprint(path);require(pin['sha256']==sha and pin['identity']['mode']=='0o444','Dependency changed: '+name)
    spec=importlib.util.spec_from_file_location('_prechange_entry_'+name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    require(fingerprint(path)[0]==raw,'Dependency changed during load')
    return module

def text(pin):
    # Root control's raw stream PINs intentionally contain a subset identity.
    raw,actual=fingerprint(pin['path'])
    require(all(actual[k]==pin[k] for k in ('path','sha256','bytes')) and
        actual['identity']['mode']=='0o444' and all(actual['identity'][k]==v for k,v in pin['identity'].items()),
        'Exact readonly archived raw bytes/declared identity required')
    return raw.decode('utf-8','surrogateescape')


def properties(raw):
    return dict(line.split('=',1) for line in raw.splitlines() if '=' in line)


def activation_context(case,files):
    require(set(case['activation'])=={'result','adoption'},'Exact typed activation result/adoption PINs required')
    result_pin=case['activation']['result'];adoption_pin=case['activation']['adoption']
    require(result_pin['path']==str(ACTIVATION_RESULT) and result_pin['sha256']==ACTIVATION_SHA and
        adoption_pin['path']==str(ACTIVATION_ADOPTION) and adoption_pin['sha256']==ADOPTION_SHA,
        'Only the genuine closed diagnostic activation is current owner authority')
    rec=pinned(result_pin);adoption=pinned(adoption_pin)
    require(rec['schema']=='robotron-rejected-gap-healthy-activation-result-v1' and
        rec['status']=='READY_HEALTHY_DIAGNOSTIC_ACTIVATION' and rec['maintenance_only'] is True and
        rec['source_application_attempts']==rec['owned_start_attempts']==1 and rec['manual_recovery_required'] is False and
        rec['qualification_pass'] is False and rec['owned_request_at_terminal'] is None and
        rec['final_resume']['all_matching_actors_resumed'] is True and not rec['final_resume']['failures'] and
        rec['owner']==ACTUAL_OWNER and rec['startup']['phase']['record']['sha256']==FOUNDER,
        'Genuine completed diagnostic activation/current owner and phase required')
    require(adoption['schema']=='robotron-root-healthy-diagnostic-activation-adoption-v1' and
        adoption['status']=='PASS_RUNTIME_ACTIVATION_AND_OWNED_RELEASE' and adoption['original_result']==result_pin and
        adoption['owner']==rec['owner'] and adoption['phase']==rec['startup']['phase'] and
        adoption['source_count']==62 and adoption['source_files_applied']==4 and adoption['source_application_attempts']==1 and
        adoption['owned_start_attempts']==1 and adoption['original192_retained'] is True and
        adoption['newest_and_startup_cpu_pass'] is True and adoption['protected704_reference_unchanged'] is True and
        adoption['qualification_pass'] is False,'Actual diagnostic adoption does not match the original activation')
    release=pinned(adoption['original_closure'])
    require(release['schema']=='robotron-root-retained-original-result-and-release-v1' and
        release['original_exec_code']==1 and release['original_exit']==0 and release['original_result']=='success' and
        release['original_archived_before_release'] is True and release['unit_released'] is True,
        'Original activation0 must be archived and released before candidate collection')
    original=release['original'];require(original['observed_live'] is True and type(original['pid']) is int and
        original['pid']>0 and type(original['starttime_ticks']) is int and original['starttime_ticks']>0 and
        original['timer']==original['unit'].removesuffix('.service')+'.timer','Actual original service/timer identity required')
    commands=[['systemctl','--user','show',original['unit']],['systemctl','--user','cat',original['unit']],
        ['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+original['invocation_id']],
        ['systemctl','--user','show',original['timer']],['systemctl','--user','cat',original['timer']],
        ['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+original['timer_invocation_id']]]
    archives=release['full_original_archives']
    require(len(archives)==6 and all(a['argv']==cmd and a['exit']==0 for a,cmd in zip(archives,commands)),
        'Exact six original service/timer archives required')
    show=properties(text(archives[0]['stdout']));timer=properties(text(archives[3]['stdout']))
    require(show['InvocationID']==original['invocation_id'] and show['ExecMainPID']==str(original['pid']) and
        show['MainPID']=='0' and show['NRestarts']=='0' and show['ExecMainCode']=='1' and
        show['ExecMainStatus']=='0' and show['Result']=='success' and
        timer['InvocationID']==original['timer_invocation_id'],'Archived original terminal identity differs')
    released=release['owned_release']
    require(len(released)==2 and [x['unit'] for x in released]==[original['timer'],original['unit']],
        'Exact timer-first owned release required')
    for item in released:
        require(item['stop']['argv']==['systemctl','--user','stop',item['unit']] and item['stop']['exit']==0 and
            item['final']['argv']==['systemctl','--user','show',item['unit']] and item['final']['exit']==0 and
            properties(text(item['final']['stdout']))['LoadState']=='not-found','Owned release not-found proof differs')
    require(max(a['unix_s'] for a in archives)<=released[0]['stop']['unix_s']<=released[1]['stop']['unix_s'],
        'Original archives must precede timer-first release')
    phase=rec['startup']['phase'];record=pinned(phase['record']);boot=pinned(phase['boot_verification'])
    historical=pinned(rec['startup']['phase_CPU_readonly_archive']);start=pinned(rec['start_request'])
    expected=phase['expected'];owner=rec['owner'];job=pinned(rec['root_job'])
    require(job['quality_release']['sha256']==QUALITY_RELEASE_SHA,
        'Activation historical successful46f authority must remain unchanged')
    historical_quality_release=pinned(job['quality_release'])
    quality_release=historical_quality_release
    require(quality_release['source_freeze_released'] is True and quality_release['both_independent_candidate_gates_pass'] is True and
        quality_release['C1_original_failed_audit_preserved'] is True and quality_release['quality_retry_or_extension'] is False,
        'Authentic confirmed704 closure/release required')
    require(record['metric']=='ce' and record['previous_metric']=='ce' and record['action']=='start' and
        record['phase_id']==expected['phase_id'] and record['root_precommit_sha256']==expected['root_precommit_sha256'] and
        record['checkpoint']==phase['boot_checkpoint'] and expected['metric']=='ce' and expected['valid'] is True and
        expected['founder_phase_record_sha256']==phase['record']['sha256'] and expected['last_resume_record_sha256'] is None and
        boot['status']=='PASS' and boot['sha256']==phase['boot_checkpoint']['sha256'] and
        boot['bytes']==phase['boot_checkpoint']['bytes'],'Truthful dynamic CE phase/boot joins differ')
    require(historical['status']=='PASS' and historical['phase_metadata_verified'] is True and
        historical['script']['sha256']=='b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519' and
        historical['strict_phase_base']['sha256']=='9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8' and
        historical['root_job']['phase_snapshot']['purpose']=='startup' and
        historical['root_job']['phase_snapshot']['observed_clients']==0 and
        historical['root_job']['phase_snapshot']['owner']==owner and
        historical['root_job']['phase_snapshot']['expected_phase']==expected and
        historical['saved_priority_metric_phase']['phase_record_sha256']==phase['record']['sha256'] and
        historical['saved_priority_metric_phase']['phase_id']==expected['phase_id'] and
        historical['saved_priority_metric_phase']['metric']=='ce' and historical['saved_priority_metric_phase']['valid'] is True,
        'Startup0 CPU is only a genuine historical floor for this current CE owner')
    require(historical['held_recipe_context']==historical['root_job']['source_control_context']['held_recipe_context'] and
        historical['held_recipe_context']['batch_size']==4096 and historical['held_recipe_context']['learning_control_lr_scale']==.5 and
        historical['held_recipe_context']['optimizer_lr']==2.5e-5,'Genuine held4096/.5 CPU context required')
    strict=pinned(rec['reconnect']['strict_runtime'])
    require(strict['end_monotonic_s']-strict['start_monotonic_s']>=60 and
        strict['end_monotonic_s']<=strict['original_deadline_monotonic_s'] and
        start['phase_record']==phase['record'] and start['unit']==owner['unit'] and start['cgroup']==owner['cgroup'] and
        rec['healthy192']['api']['client_count']==192 and not rec['healthy192']['api']['log_errors'],
        'Completed strict60/current192 activation evidence required')
    require(case['source_freeze_release']==load('recipe').RELEASE_PIN,
        'Only actual confirmed845 adoption/freeze release is continuation authority')
    quality_release=pinned(case['source_freeze_release'])
    load('recipe').check_release(quality_release,owner)
    ready_clock=dict(boot_id=start['boot_id'],monotonic_s=rec['healthy192']['api']['observed_monotonic_s'],
        wall_s=rec['healthy192']['api']['observed_unix_s'])
    return dict(activation=rec,adoption=adoption,closure=release,quality_release=quality_release,phase=phase,owner=owner,historical_report=historical,
        historical_floor={k:historical['clocks'][k] for k in CLOCKS},startup_tag=job['transition']['startup_tag'],ready_clock=ready_clock)


def validate(case,output,modules,files):
    require(set(case)=={'schema','capture_authorized','activation','source_freeze_release','runtime_baseline','readiness',
        'control_before','completed_slot','experiment','recipe','tags','window','output_directory','cpu_python'} and
        case['schema']==SCHEMA and case['capture_authorized'] is True,'Explicit exact prospective root case required')
    require(output==Path(case['output_directory']) and output.is_absolute() and output==output.resolve(strict=False) and
        output.parent==RUN and not output.exists(),'Fresh direct run26 output required')
    require(type(case['cpu_python']) is str and Path(case['cpu_python']).is_absolute(),'Root-verified CPU Python required')
    recipes=modules['recipe'];chosen=recipes.check_recipe(case['recipe'])
    require(chosen==recipes.for_scale(.25), 'Only the prospective same-.25 recipe is admitted')
    require(set(case['tags'])=={'barrier','endpoint'} and len(set(case['tags'].values()))==2 and
        all(type(t) is str and 0<len(t)<=80 and all(c.isascii() and (c.isalnum() or c in '_-') for c in t)
            for t in case['tags'].values()),'Two unique precommitted tags required')
    context=activation_context(case,files);baseline=pinned(case['runtime_baseline']);ready=pinned(case['readiness'])
    release=context['quality_release']
    recipes.check_release(release,context['owner'],baseline['actors'])
    require(release['source_freeze_released'] is True and release['both_independent_candidate_gates_pass'] is True,
        'Root must bind genuine completed quality freeze release')
    env=pinned(baseline['actual_selected_environment']);resources=pinned(baseline['actual_main192_resources'])
    entry_exposure=modules['observer'].normalise(json.loads(pinned(baseline['actual_API'],raw_only=True)))
    require(all({k:entry_exposure[name+'_identity'][k] for k in ('process_id','instance_monotonic_ns','epoch')}
        ==release['main_exposure_identities'][name] for name in ('optimizer','replay')),
        'Fresh baseline must retain released optimizer/replay identities')
    require(baseline['main_owner']==context['owner'] and
        baseline['actual_activation']==case['activation']['result'] and len(baseline['source_hashes'])==62 and
        len(baseline['control_hashes'])==2 and len(baseline['unit_files'])==3 and len(baseline['actors'])==192 and
        baseline['source_hashes'][str(GAME/'Scripts/dqn/socket_server.py')]==FIXED_SOCKET and
        env['DQN_BATCH_SIZE']=='4096' and env['DQN_PER_PRIORITY_METRIC']=='ce' and
        env['DQN_MAX_SAMPLES_PER_FRAME']=='8' and env['ROBOTRON_REJECTED_GAP_TELEMETRY']=='1' and env['DQN_PRIORITY_PHASE_RECORD_SHA256']==context['phase']['record']['sha256'] and
        env['DQN_PRIORITY_PHASE_RECORD']==context['phase']['record']['path'],'Fresh corrected current CE4096/192 maps required')
    control_path=GAME/'models_dqn/learning_control.json'
    require(case['control_before']['path']==str(control_path) and
        (env.get('ROBOTRON_DQN_CONTROL_PATH') or str(control_path))==str(control_path) and
        ((env.get('ROBOTRON_DQN_MODEL_DIR') or '').strip() or str(GAME/'models_dqn'))==str(GAME/'models_dqn'),
        'Actual held default model/control paths required')
    raw_control,control_pin=fingerprint(control_path)
    require(control_pin==case['control_before'] and baseline['control_hashes'][str(control_path)]==control_pin['sha256'],
        'Unchanged actual .25 control required')
    control=json.loads(raw_control,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite control: '+x)))
    require(type(control['lr_scale']) is float and control['lr_scale']==.25 and control.get('measurement') is None and
        control['epsilon_ramp']['start']==control['epsilon_ramp']['end']==.1 and
        type(control['experiment']) is str,
        'Fresh unchanged .25 before-control required')
    for tag in case['tags'].values():
        require(tag!=context['startup_tag'] and all(not Path(str(GAME/'models_dqn/managed-checkpoints'/(tag+'.pt'))+suffix).exists()
            for suffix in ('','.tmp','.bak')),'Prospective tags must be new')
    target=dict(control,experiment=case['experiment'],lr_scale=chosen['learning_control_lr_scale'])
    recipes.check_control(control,target,case['experiment'],chosen)
    by_pid={a['pid']:a for a in baseline['actors']};owner=context['owner']
    binding=context['activation']['healthy192']['binding'];native=binding['bindings']
    known_actors={a['pid']:a for a in native['actors']}
    require(baseline['source_hashes']==native['source_hashes'] and
        set(baseline['control_hashes'])==set(native['control_hashes']) and
        all(sha==native['control_hashes'][path] for path,sha in baseline['control_hashes'].items() if path!=str(control_path)) and
        baseline['unit_files']=={p:sha for values in binding['unit_files'].values() for p,sha in values.items()} and
        env==binding['environment'] and baseline['inference_worker']['tid']==native['worker']['thread']['tid'] and
        baseline['inference_worker']['starttime_ticks']==native['worker']['thread']['starttime_ticks'] and
        baseline['fleet_owner']['pid']==int(binding['fleet']['MainPID']) and
        baseline['fleet_owner']['starttime_ticks']==binding['supervisor_start_ticks'] and
        baseline['fleet_owner']['cgroup']==binding['fleet']['ControlGroup'] and set(by_pid)==set(known_actors) and
        all(a['starttime_ticks']==known_actors[pid]['starttime_ticks'] and a['slot']==known_actors[pid]['client_slot']
            for pid,a in by_pid.items()),'Fresh baseline must retain actual READY source/fleet/worker/original192 identities')
    require(resources['owner']==owner and all(resources['main'][k]==owner[k] for k in ('pid','starttime_ticks','cgroup')) and
        all(resources['fleet'][k]==baseline['fleet_owner'][k] for k in ('pid','starttime_ticks','cgroup')) and
        resources['worker']==baseline['inference_worker'] and len(resources['actors'])==192 and len(by_pid)==192 and
        {a['slot'] for a in baseline['actors']}==set(range(192)) and {a['pid'] for a in resources['actors']}==set(by_pid) and
        all(all(a[k]==by_pid[a['pid']][k] for k in ('pid','starttime_ticks','mask')) for a in resources['actors']),
        'Pinned current main/fleet/worker/192 resource descriptors differ')
    last_release=context['closure']['owned_release'][-1]['final']['unix_s']
    require(ready['status']=='PASS' and 0<=time.time()-ready['observed_unix_s']<=180 and
        ready['observed_unix_s']>=max(last_release,recipes.release_wall_s(release)) and all(ready[k]==baseline[k] for k in
        ('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')) and
        ready['resources']['GPU0_free_bytes']>=14*(1<<30) and all(ready['resources'][k] is True for k in
        ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free','no_competing_helpers',
         'no_private_cgroup_tmpfs_processes','no_pending_save','owned_units_released')),'Fresh post-activation exclusive readiness required')
    observer=modules['observer'];window=case['window']
    require(set(window)=={'policy','preparation_timeout_s'} and set(window['policy'])==set(observer.POLICY)|{'cutoff_s'} and
        all(type(window['policy'][k]) is type(v) and window['policy'][k]==v for k,v in observer.POLICY.items()) and
        type(window['policy']['cutoff_s']) in (int,float) and math.isfinite(window['policy']['cutoff_s']) and window['policy']['cutoff_s']==3600 and
        type(window['preparation_timeout_s']) in (int,float) and math.isfinite(window['preparation_timeout_s']) and
        0<window['preparation_timeout_s']<=180,'New exact8M+8M policy and bounded B preparation required')
    modules['entry'].slot_guard(case,files)
    context.update(baseline=baseline,env=env,resources=resources,control=control,raw_control=raw_control,recipe=chosen)
    return context



class Continuation:
    """No owner lifecycle. Finite original transaction methods are reused unchanged."""
    def __init__(self,case,case_pin,output,modules,files,context,health):
        self.job,self.job_pin,self.out,self.modules,self.files,self.context,self.health=case,case_pin,output,modules,files,context,health
        self.ops=modules['ops'];self.hashes=health.hashes
        self.expected_completed=copy.deepcopy(case['completed_slot']);self.control_pin=copy.deepcopy(case['control_before'])
        self.owner=context['owner'];self.phase=context['phase'];self.pending=None
    def publish(self,name,value):return self.ops.publish(self.out/name,value)
    def slot_guard(self):return self.modules['driver'].Driver.slot_guard(self)
    def replace_control(self,raw,name):return self.modules['driver'].Driver.replace_control(self,raw,name)
    def save_once(self,stage,floor):
        recipe=self.context['recipe'];raw,api=self.health.check_health(self.job['experiment'],recipe['scheduled_lr'])
        self.slot_guard();require(all(self.modules['capture'].four(api)[k]>=floor[k] for k in CLOCKS),'Save API regressed floor')
        floor=self.modules['capture'].four(api)
        capture=self.modules['capture'];runtime=capture.CaptureRuntime(self.ops,self.files,
            dict(model_dir=str(GAME/'models_dqn'),experiment=self.job['experiment'],tag=self.job['tags'][stage],
                 startup_tag=self.context['startup_tag']),self.owner,self.hashes)
        require(runtime.current_completed==self.expected_completed,'New stage cannot adopt another completion')
        adapter=type('SnapshotPrimitives',(),{name:staticmethod(getattr(capture,name)) for name in
            ('four','triple','request_identity','publish_request')})
        snapshot=self.modules['snapshot'].Snapshot(adapter,self.files,runtime,
            dict(tag=self.job['tags'][stage],save_timeout_s=60),self.out/stage)
        self.pending=snapshot;self.files.raw_api=raw;self.files.api=api;snapshot.start(api,floor)
        while snapshot.state=='PENDING':
            time.sleep(.2);self.health.check_health(self.job['experiment'],recipe['scheduled_lr']);snapshot.tick()
        require(snapshot.state=='COMPLETE','First '+stage+' snapshot failed: '+str(snapshot.error))
        frozen=snapshot.freeze(purpose='candidate',phase=self.phase)
        runtime.request_guard();require(runtime.current_completed==snapshot.completed,'Stage completion lost')
        self.expected_completed=copy.deepcopy(snapshot.completed);self.pending=None
        return snapshot,runtime,frozen,floor


def build_CPU_job(case,case_pin,context,frozen,floor,snapshot,before_pin,after_pin,files,ops,phase,output):
    entry=load('entry');directory=output/'metadata';directory.mkdir(mode=0o700);pairs={}
    for name in entry.SOURCE_NAMES:
        current,archive=files.exclusive_copy(GAME/'Scripts/dqn'/name,directory/name)
        pairs[name]=dict(current=current,archive=archive)
    _,control=files.exclusive_copy(case['control_before']['path'],directory/'learning_control.json')
    unit=ops.command(['systemctl','--user','cat',context['owner']['unit']]);require(unit['returncode']==0,'Actual trainer unit cat failed')
    unit_pin=ops.write_bytes(directory/'trainer-unit.txt',unit['stdout'].encode('utf-8','surrogateescape'))
    held=load('recipe').held_context(case['recipe'],context['historical_report']['root_job']['source_control_context']['held_recipe_context'])
    current_phase=context['phase']
    job=dict(schema=phase.SCHEMA,verifier_sha256=DEPS['phase'][1],strict_phase_base_sha256=phase.STRICT_SHA256,
        original_strict_base_sha256=phase.ORIGINAL_SHA256,experiment=case['experiment'],
        source=frozen['source'],verification_copy=frozen['verification_copy'],clock_floor=floor,
        source_control_context=dict(game_root=str(GAME),model_dir=str(GAME/'models_dqn'),
            model_package={name:pairs[name]['current'] for name in entry.MODEL_NAMES},archived_control=control,
            archived_trainer_unit=unit_pin,held_recipe_context=held,
            provenance=[case_pin,case['source_freeze_release'],case['runtime_baseline'],case['readiness'],before_pin,after_pin,snapshot.raw_pin,context['control_transition'],context['barrier']]),
        output_directory=str(output/'candidate-CPU-output'),phase_snapshot=dict(purpose='candidate',owner=context['owner'],observed_clients=192,
            phase_record=current_phase['record'],boot_checkpoint=current_phase['boot_checkpoint'],boot_verification=current_phase['boot_verification'],
            expected_phase=current_phase['expected'],acquisition=frozen['acquisition'],sources=pairs))
    base=phase.load_base();base,unused_recipe_provenance=phase.select_recipe_base(job,base)
    evidence=dict(bound_files={});model=base.check_context(job,evidence);phase.check_acquisition(job,base,evidence,model)
    return job


def run(case,case_pin,output,modules):
    entry,driver,ops,capture,observer,phase=(modules[k] for k in ('entry','driver','ops','capture','observer','phase'))
    observer.configure_recipe(modules['recipe']);files=capture.Files(ops);context=validate(case,output,modules,files)
    health=entry.EntryHealth(driver,ops,files,observer,context['baseline'],context['owner'],context['env'],context['resources'],context['historical_floor'])
    raw,api=health.check_health(context['control']['experiment'],1.25e-5);entry.slot_guard(case,files)
    output.mkdir(mode=0o700);files.fsync_directory(output.parent)
    runner=Continuation(case,case_pin,output,modules,files,context,health)
    result=dict(schema=RESULT_SCHEMA,status='STARTING',root_case=case_pin,root_precommit=case_pin,CPU_executed=False,
        qualification_pass=False,model_only=True,replay_RNG_actor_anchor=False,control_changed=False,owner_actions=False,
        recipe=copy.deepcopy(case['recipe']),hold_recipe_through_quality=True,restored_control=False)
    try:
        original=ops.write_bytes(output/'control-before-readonly.json',context['raw_control']);result['original_control_archive']=original
        fresh_before=capture.four(api)
        new=modules['recipe'].check_control(context['control'],dict(context['control'],experiment=case['experiment'],
            lr_scale=case['recipe']['learning_control_lr_scale']),case['experiment'],case['recipe'])
        result.update(control_changed=None,control_transaction_attempted=True)
        after_archive=runner.replace_control((json.dumps(new,indent=2,allow_nan=False)+'\n').encode(),'control-target')
        result.update(control_changed=True,control_after=after_archive,
            control_transition=files.fingerprint(output/'control-target-receipt.json',4<<20))
        deadline=time.monotonic()+case['window']['preparation_timeout_s'];lr=case['recipe']['scheduled_lr']
        while True:
            raw,api=health.check_health(None,None)
            if api['managed_experiment']==case['experiment'] and api['lr']==lr:break
            require(time.monotonic()<deadline,'First target LR refresh timed out');time.sleep(.2)
        barrier,barrier_runtime,barrier_frozen,unused_floor=runner.save_once('barrier',fresh_before)
        barrier_clock=driver.clock();barrier_pin=ops.publish(output/'barrier.json',dict(frozen=barrier_frozen,completed_clock=barrier_clock,completed_slot=copy.deepcopy(runner.expected_completed),request_publications=barrier_runtime.publications))
        result['barrier']=barrier_pin;context.update(control_transition=result['control_transition'],barrier=barrier_pin)
        while True:
            raw,api=health.check_health(case['experiment'],lr);runner.slot_guard();now=driver.clock();normal=observer.normalise(api)
            require(time.monotonic()<=deadline,'B preparation exceeded precommitted budget')
            if normal['unclassified']==0 and normal['optimizer']['applied']>0 and normal['learner_accepted']>0 and normal['accepted']>0 and api['ts']-api['pipeline_snapshot_age_s']>=barrier_clock['wall_s']:break
            time.sleep(1)
        B=ops.write_bytes(output/'B-API.raw.json',raw)
        window=dict(schema=observer.SCHEMA,experiment=case['experiment'],owner=context['owner'],recipe=copy.deepcopy(case['recipe']),
            current_phase=context['phase'],proofs=dict(root_precommit=case_pin,activation_result=case['activation']['result'],
            activation_adoption=case['activation']['adoption'],control=after_archive,control_transition=result['control_transition'],barrier=barrier_pin),
            post_control_barrier_clock=barrier_clock,baseline=dict(api=B,observed_clock=now),policy=copy.deepcopy(case['window']['policy']))
        observer.validate_job(window,api);window_pin=ops.publish(output/'window-job.json',window)
        result['window_job']=window_pin
        before=ops.publish(output/'before-window-health.json',dict(owner=context['owner'],client_count=192,clocks=capture.four(api),
            observed_clock=now,historical_floor=context['historical_floor'],window_job=window_pin))
        journal=observer.ReceiptJournal(publish=lambda path,value:ops.write_bytes(path,observer.encoded(value)),get_clock=driver.clock,root=output/'observations',job=window)
        (output/'observations').mkdir(mode=0o700);files.fsync_directory(output)
        def evidence():
            runner.slot_guard();barrier_runtime.request_guard()
            return dict(ok=True,unchanged_control_sha256=runner.control_pin['sha256'],current_phase_record_sha256=context['phase']['record']['sha256'])
        outcome=observer.poll(window,baseline_api=api,get_api=lambda:health.check_health(case['experiment'],lr)[1],
            get_owner=barrier_runtime.trainer_id,get_evidence=evidence,get_clock=driver.clock,sleep=time.sleep,emit=journal.emit)
        result['window_result']=ops.write_bytes(output/'window-result.json',observer.encoded(outcome))
        require(outcome['status']=='LATCH_DURABLE' and outcome['candidate_requests_allowed']==1,'Original window grants no candidate: '+outcome['status'])
        eligible=outcome['observation']['first_eligible_observation'];floor={k:max(context['historical_floor'][k],normal['clocks'][k],eligible[k]) for k in CLOCKS}
        snapshot,runtime,frozen,floor=runner.save_once('endpoint',floor)
        after_raw,after_api=health.check_health(case['experiment'],lr)
        require(all(capture.four(after_api)[k]>=floor[k] for k in CLOCKS),'Postcapture API regressed endpoint floor')
        ops.write_bytes(output/'after-capture-API.raw.json',after_raw)
        after=ops.publish(output/'after-capture-health.json',dict(owner=context['owner'],client_count=192,clocks=capture.four(after_api),observed_clock=driver.clock()))
        job=build_CPU_job(case,case_pin,context,frozen,floor,snapshot,before,after,files,ops,phase,output)
        runner.slot_guard();runtime.request_guard();health.check_health(case['experiment'],lr)
        job_pin=ops.publish(output/'candidate-CPU-job.json',job)
        completion=ops.publish(output/'capture-completion.json',dict(status='COMPLETE',tag=case['tags']['endpoint'],owner_before=snapshot.owner,
            owner_after=snapshot.owner_after,transition=snapshot.transition,request_publications=runtime.publications))
        result.update(status='CAPTURED_PENDING_ROOT_CPU',owner=context['owner'],current_phase=context['phase'],source=frozen['source'],
            verification_copy=frozen['verification_copy'],acquisition=frozen['acquisition'],trigger_API=snapshot.raw_pin,capture_completion=completion,
            cpu_job=job_pin,candidate_clocks=None,cpu_report=None,cpu_completion=None,
            cpu_argv=[case['cpu_python'],'-Xgil=0','-I','-B',str(DEPS['phase'][0]),'--execute','--job',job_pin['path'],
                '--expected-job-sha256',job_pin['sha256'],'--expected-verifier-sha256',DEPS['phase'][1]])
    except BaseException as error:
        result.update(status='FAILED',error=repr(error),traceback=traceback.format_exc(),manual_control_review=result.get('control_transaction_attempted',False),
            snapshot=None if runner.pending is None else runner.pending.result(),window_emission_failure=None if 'journal' not in locals() else journal.failure,
            no_retry=True,automatic_restoration=False)
    ops.publish(output/'result.json',result);return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--preflight-only',action='store_true')
    parser.add_argument('--case',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--expected-case-sha256');parser.add_argument('--expected-source-sha256');args=parser.parse_args(argv)
    require(not(args.execute and args.preflight_only),'Choose preflight-only OR execute')
    if not(args.execute or args.preflight_only):
        print('PLAN_ONLY_UNSELECTED: no reads/imports/control/window/requests/CPU/actions');return 0
    require(all((args.case,args.output,args.expected_case_sha256,args.expected_source_sha256)),'Explicit pinned case/source/new output required')
    _,source=fingerprint(Path(__file__).resolve());require(source['sha256']==args.expected_source_sha256 and source['identity']['mode']=='0o444','Exact sealed source required')
    raw,case_pin=fingerprint(args.case);require(case_pin['sha256']==args.expected_case_sha256 and case_pin['identity']['mode']=='0o444','Exact readonly case required')
    case=json.loads(raw);modules={key:load(key) for key in DEPS}
    if args.preflight_only:
        modules['observer'].configure_recipe(modules['recipe'])
        files=modules['capture'].Files(modules['ops']);context=validate(case,args.output,modules,files)
        health=modules['entry'].EntryHealth(modules['driver'],modules['ops'],files,modules['observer'],
            context['baseline'],context['owner'],context['env'],context['resources'],context['historical_floor'])
        _,api=health.check_health(context['control']['experiment'],1.25e-5);modules['entry'].slot_guard(case,files)
        print(json.dumps(dict(status='PREFLIGHT_ONLY_PASS_NO_ACTIONS',root_case=case_pin,owner=context['owner'],
            recipe=context['recipe'],current_phase=context['phase'],fresh_clocks=modules['capture'].four(api),
            control_changed=False,request_started=False,CPU_executed=False,output_created=False),allow_nan=False))
        return 0
    return 0 if run(case,case_pin,args.output,modules)['status']=='CAPTURED_PENDING_ROOT_CPU' else 1


if __name__=='__main__':sys.exit(main())
