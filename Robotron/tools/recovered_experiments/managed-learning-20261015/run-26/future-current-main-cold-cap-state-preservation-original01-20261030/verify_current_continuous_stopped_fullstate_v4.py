"""Strict stopped .0625 CE checkpoint/ring/bank preservation; default inert.

Root alone creates the actual job after owned stop. This verifier never starts,
stops, signals, installs, saves a model, changes controls or admits actors. The
retained strict numerical body checks all model/Adam/scaler values; this wrapper
binds the current source/owner/phase and emits exact startup comparison data.
Ring state payloads are header/stat-only, never falsely described as hashed.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import resource
import stat
import subprocess
import sys
import time
import traceback
import types

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE=ROOT/'logs/managed-learning-20261015/run-26'
SCHEMA='robotron-stopped-full-training-state-CPU-job-v1'
MANIFEST_SCHEMA='robotron-stopped-full-training-state-restoration-manifest-v1'
CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count')
OWNER = None  # Bound only by exact selected actual startup/stop metadata.
PHASE_ANCHOR_SHA = None  # Bound only by exact selected actual startup/stop metadata.
BOOT_SHA = None  # Bound only by exact selected actual startup/stop metadata.
RECORD_SHA = None  # Bound only by exact selected actual startup/stop metadata.
MANIFEST_TOOLS_SHA='3ab7c6a018afce917bd1199ec9d09b5d3041936d638cdf17f91514006685faf7'
DEPENDENCIES={
    'recipe_verifier':(BASE/'post-preview-LR0625-hot-verifier-original01-preparation-20261027/verify_recipe_phase_snapshot_lr0625_v1.py',
        'b1a18582bd7d6e0e2db3bd91ce6a9e9dc469bd386a047f9c6bf171a8f1fcc260'),
    'bank_descriptors':(ROOT/'tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/live8_maintenance_proposal/revision4/bank_state_revision2.py',
        'e0c69fb38f5fec86e117edf42b4ff1ce2ff44b82b979c5240116121a7a1ce54f'),
    'bank_witness':(ROOT/'tools/score_carry_proposal/bank_generation_witness.py',
        'dcbebda66feac28a312819a83c8915a8f6cb812ace78b10f2368c7ab4ab4804e'),
    'poststop_semantics':(BASE/'current-continuation-raw4hz-source-only-original01-20261027/preview-flags-preserveRAM-trainer-restart-original01/stop-sources/current192_poststop_only_v1.py',
        '7c8e995d67bfbd826e87d327a5dc4dfa796bb12e4c368a3eafd37e23c8466278'),
}


def require(value,message):
    if not value:raise RuntimeError(message)


def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,mtime_ns=info.st_mtime_ns,
        ctime_ns=info.st_ctime_ns,mode=oct(stat.S_IMODE(info.st_mode)),uid=info.st_uid,nlink=info.st_nlink)


def pin(path):
    path=Path(path)
    require(path.is_absolute()and path.resolve(strict=True)==path and not path.is_symlink(),'Canonical physical file required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb')as stream:
        before=identity(os.fstat(stream.fileno()))
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode)and before['uid']==os.getuid()
            and before['nlink']==1,'Owned regular single-link file required')
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
        require(identity(os.fstat(stream.fileno()))==before==identity(path.stat()),'File changed during full hash')
    return dict(path=str(path),sha256=digest,bytes=before['bytes'],identity=before)


def checked(value,*,immutable=False,limit=None,allow_empty=False):
    require(type(value)is dict and set(value)=={'path','sha256','bytes','identity'},'Full8 source/evidence pin required')
    if limit is not None:require(type(value['bytes'])is int and (0<=value['bytes'] if allow_empty else 0<value['bytes']) and value['bytes']<=limit,'Bounded metadata required')
    if immutable:require(value['identity']['mode']=='0o444','Immutable owned metadata required')
    require(pin(value['path'])==value,'Selected full pin changed: '+value['path'])
    return Path(value['path'])


def read(value):
    path=checked(value,immutable=True,limit=4<<20);raw=path.read_bytes()
    require(pin(path)==value,'Immutable JSON changed during decode')
    return json.loads(raw)


def put(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return pin(path)


def load(name,value,*,immutable=True):
    path=checked(value,immutable=immutable,limit=4<<20)
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module



def select_context(job):
    """Bind one actual cold incarnation; no old owner/boot/phase is relabelled."""
    global OWNER, FLEET, PHASE_ANCHOR_SHA, BOOT_SHA, RECORD_SHA
    entry=job['current_inputs_source']
    require(entry['path']==str(Path(__file__).with_name('current_main_preservation_inputs_v1.py')),
            'Exact selected current preservation metadata source required')
    helper=load('_current_continuous_preservation_inputs',entry)
    selection=helper.read(job['current_selection'])
    expected=helper.startup_anchor(selection)
    require(job['owner']==selection['owner'] and job['fleet']==selection['fleet']
            and job['expected_current_cap']==selection['expected_current_cap']
            and job['phase_anchor']==job['boot_CPU_report']
            and read(job['phase_anchor'])==expected,
            'Actual restored boot descriptor/owner/cap differs')
    require(job['phase_record']==expected['phase_record'], 'Actual current resume record required')
    OWNER,FLEET=selection['owner'],selection['fleet']
    PHASE_ANCHOR_SHA,BOOT_SHA,RECORD_SHA=(job[k]['sha256'] for k in ('phase_anchor','boot_CPU_report','phase_record'))
    return helper,selection,expected


def select_current_recipe(job,recipe):
    """Same strict tensor/numerical body, exact selected .0625 cap8/12 literals."""
    context=job['source_control_context']['held_recipe_context'];cap=job['expected_current_cap']
    expected=dict(recipe.HISTORICAL_HELD_CONTEXT,learning_control_lr_scale=.0625,
                  optimizer_lr=3.125e-6,max_samples_per_frame=cap)
    require(type(cap)is int and cap in(8,12) and context==expected
            and set(context)==set(expected)and all(type(context[k])is type(v)for k,v in expected.items()),
            'All held recipe fields must match; only selected cold cap8/12 is variable')
    data=recipe.STRICT_PATH.read_bytes()
    require(hashlib.sha256(data).hexdigest()==recipe.STRICT_SHA256,'Original strict body changed')
    replacements=list(recipe.RECIPE_REPLACEMENTS)
    if cap==12:replacements.extend([(b'max_samples_per_frame=8,',b'max_samples_per_frame=12,'),
        (b"DQN_MAX_SAMPLES_PER_FRAME='8',",b"DQN_MAX_SAMPLES_PER_FRAME='12',")])
    effective=data
    for old,new in replacements:
        require(effective.count(old)==1 and effective.count(new)==0,'Exact recipe literal boundary differs')
        effective=effective.replace(old,new)
    inverse=effective
    for old,new in reversed(replacements):inverse=inverse.replace(new,old)
    require(inverse==data,'Unrelated strict source mutation refused')
    selected=types.ModuleType('_current_continuous_selected_strict_body');selected.__file__=str(recipe.STRICT_PATH)
    exec(compile(effective,str(recipe.STRICT_PATH)+'::current-cold-cap-'+str(cap),'exec'),selected.__dict__)
    require(selected.HELD_RECIPE_CONTEXT==context,'Effective strict context differs')
    return selected,dict(schema='robotron-phase-CPU-recipe-source-specialization-v1',
        selected_recipe=dict(priority_metric='ce',batch_size=4096,learning_control_lr_scale=.0625,
            scheduled_lr=3.125e-6,max_samples_per_frame=cap),
        full_held_recipe_context=copy.deepcopy(context),raw_strict_source_sha256=recipe.STRICT_SHA256,
        effective_source_sha256=hashlib.sha256(effective).hexdigest(),
        literal_replacements=[dict(original=a.decode(),effective=b.decode())for a,b in replacements],
        reverse_exact_raw_source=True,tensor_Adam_scaler_finite_and_shape_predicates_unchanged=True,
        declared_recipe_and_isolated_setup_env_literals_only=True,saved_metadata_normalized=False)

def old_owner_absent(owner):
    require(owner==OWNER or owner==FLEET,'Only the explicitly selected trainer/fleet is accepted')
    path=Path('/proc',str(owner['pid']),'stat')
    try:
        raw=path.read_text();parts=raw[raw.rfind(')')+2:].split()
        require(int(parts[19])!=owner['starttime_ticks'],'Original trainer birth remains live')
        result='PID_REUSED_OTHER_BIRTH'
    except (FileNotFoundError,ProcessLookupError):result='ABSENT'
    group=Path('/sys/fs/cgroup'+owner['cgroup'])
    if group.exists():
        for current in (group,*[p for p in group.rglob('*')if p.is_dir()]):
            require(not(current/'cgroup.threads').read_text().split(),'Original trainer cgroup still has tasks')
    return dict(owner=owner,old_birth=result,original_cgroup_absent_or_all_threads_empty=True)


def current_phase(checkpoint,evidence,anchor,record,boot,floor,api,tools,torch):
    """Retain full actual phase; only its two mutable learning counters may grow."""
    phase=checkpoint.get('priority_metric_phase');previous=anchor['priority_phase']
    require(anchor['priority_phase_valid']is True and anchor['CUDA_initialized']is False,
        'Retained actual W03 numerical lineage witness required')
    require(type(phase)is dict and set(phase)==set(previous),'Full current phase fields differ')
    moving={'priority_update_calls','ring_rows_submitted'}
    require(all(phase[k]==previous[k]for k in set(previous)-moving),'Saved phase lineage/validity changed')
    require(phase['metric']=='ce'and phase['valid']is True and phase['invalid_reason']is None
        and phase['last_resume_record_sha256']==RECORD_SHA,'Actual CE founder/resume phase required')
    require(all(type(phase[k])is int and phase[k]>=previous[k]for k in moving),'Phase counters regressed')
    require(record['schema']=='robotron-priority-metric-start-v1'and record['action']=='resume'
        and record['metric']==record['previous_metric']=='ce'
        and record['checkpoint']==boot['checkpoint']and record['root_precommit_sha256']==phase['root_precommit_sha256']
        and record['phase_id']==phase['phase_id'],'Actual boot/resume source lineage differs')
    for key in CLOCKS:
        require(type(checkpoint[key])is int and checkpoint[key]==floor[key]==api[key]
            and checkpoint[key]>=max(anchor['clocks'][key],boot['saved_clocks'][key]),
            'Saved exact final clock/retained floor differs: '+key)
    require(checkpoint['total_training_steps']==api['training_steps']
        and checkpoint['measurement_frame_count']==api['measurement_frames'],
        'Metrics/measurement clocks differ from final source-owned pause')
    payload_keys=('online_state_dict','target_state_dict','optimizer_state_dict','grad_scaler_state_dict')
    require(set(checkpoint)==set(payload_keys)|set(evidence['clocks'])|{'priority_metric_phase'},
        'Unexpected or omitted saved checkpoint payload fields')
    evidence['restoration_payload']={key:tools.typed_tree(checkpoint[key],torch)for key in payload_keys}
    evidence['saved_scalars']={key:copy.deepcopy(value)for key,value in checkpoint.items()if key not in payload_keys and key!='priority_metric_phase'}
    evidence['saved_priority_metric_phase']=copy.deepcopy(phase)
    evidence['phase_metadata_verified']=True


def verify_terminal_archive(value,poststop):
    archived=read(value)
    require(archived['owner']==OWNER and set(archived['archives'])=={'show','cat','journal'},
        'Exact original terminal archive domain required')
    commands={name:read(entry)for name,entry in archived['archives'].items()}
    for name,command in commands.items():
        require(type(command['exit'])is int and command['exit']==0 and command['owner']==OWNER,
            'Original terminal command did not complete: '+name)
        checked(command['stdout'],immutable=True,limit=4<<20,allow_empty=True)
        checked(command['stderr'],immutable=True,limit=4<<20,allow_empty=True)
    show=commands['show']
    require(show['argv']==['systemctl','--user','show',OWNER['unit']],
        'Actual original terminal show command differs')
    raw=Path(show['stdout']['path']).read_text()
    fields=dict(line.split('=',1)for line in raw.splitlines()if'='in line)
    expected=dict(Id=OWNER['unit'],InvocationID=OWNER['invocation_id'],MainPID='0',
        ExecMainPID=str(OWNER['pid']),ExecMainCode='1',ExecMainStatus='0',NRestarts='0',ActiveState='inactive')
    require(all(fields.get(k)==v for k,v in expected.items()),'Archived original normal0/unit/invocation differs')
    tail=checked(archived['console_tail'],immutable=True,limit=4<<20).read_bytes()
    require(poststop.final_save_console(tail)==archived['final_save'],
        'Actual final replay/model/shutdown return sequence differs')
    return dict(original_terminal_archives_verified=True,original_normal_exit0=True,
        final_console_return_sequence_verified=True,bank_persistence_not_inferred_from_return=True)


def verify_api_and_authority(job,poststop):
    authority=read(job['stopped_authority']);api=read(authority['final_API']);seal=read(authority['bank_seal'])
    require(authority['schema']=='robotron-continuous-budget-stopped-preservation-authority-v1'
        and authority['owner']==job['owner']==OWNER and type(authority['actual_exit'])is int and authority['actual_exit']==0
        and authority['original_scope_released']is True,'Actual original0 and positively released stop required')
    terminal=verify_terminal_archive(authority['terminal_archive'],poststop)
    helper,selection,anchor=select_context(job)
    require(authority['original_selection']==job['current_selection']
            and seal['original_selection']==job['current_selection'] and seal['owner']==OWNER and seal['fleet']==FLEET
            and authority['fleet_terminal_archive']==selection['fleet_terminal_archive'],
            'Exact current continuous input/stop authority required')
    helper.verify_input_closure(selection)
    intent=load('_current_continuous_budget_intent',seal['budget_intent_source'])
    require(seal['bank_pair']==intent.validate(read(seal['before_API']),api,seal['bank_pair']['banks'],
            expected_pid=OWNER['pid'],now=seal['sealed_unix_s'],expected_cap=job['expected_current_cap'],
            loaded_baseline=anchor['loaded_baseline']), 'Actual sealed budget/bank intent must replay exactly')
    old_owner_absent(FLEET)

    require(type(authority['stopped_unix_s'])in(int,float)and math.isfinite(authority['stopped_unix_s'])
        and 0<api['ts']<=authority['stopped_unix_s'],'Actual stopped chronology differs')
    require(api['client_count']==0 and api['client_rows']==[] and api['training_enabled']is True
        and api['measurement_active']is False and api['memory_buffer_size']==6000000
        and api['lr']==3.125e-6 and api['managed_experiment']==job['experiment']
        and api['pipeline_read_error']==api['bank_persistence_read_error']=='','Final zero-client supported pause/recipe required')
    require(seal['input_sources_sealed']is seal['all_handlers_finished']is seal['budget_exhausted']is True
        and seal['prefetch_paused_claimed']is False,
        'Original handler/FIFO/prefetch/budget and bank seal required')
    require(seal['clock_floor']==job['clock_floor']and all(api[k]==job['clock_floor'][k]for k in CLOCKS),
        'Root final paused clocks differ')
    require(seal['bank_pair']['status']=='CONTINUOUS_BUDGET_EXHAUSTED_RAM_BANK_INTENT_AND_PRIOR_DISK_GEOMETRY_VERIFIED'
        and seal['bank_pair']['expected_pid']==OWNER['pid']and seal['bank_pair']['final_synchronous_save_required']is True,
        'Actual current RAM revision intent required')
    for kind,reason in (('optimizer','optimizer_restore_begin'),('replay','directory_adopt_begin')):
        value=api['host_pipeline']['learning_exposure'][kind]
        require(value['process_id']==OWNER['pid']and value['epoch']==1 and value['epoch_reason']==reason
            and value['enabled']is value['available']is True,'Current original exposure owner/epoch differs')
    opt=api['host_pipeline']['learning_exposure']['optimizer'];tot=opt['total']
    require(tot['attempts_started']==tot['outcomes_recorded']==tot['applied']+tot['amp_skipped']
        and tot['unavailable']==opt['unclassified_started_total']==0,'Optimizer/prefetch work remains unclassified')
    require(seal['replay_exposure']==api['host_pipeline']['learning_exposure']['replay'],
        'Final ring insert provenance differs from sealed API')
    return authority,api,seal,terminal


def scan_array(path,descriptor,np,*,positive=False):
    """Full finite scalar priority scan; states/next_states are never passed here."""
    value=np.load(path,allow_pickle=False,mmap_mode='r')
    require(value.dtype.str==descriptor['dtype']and list(value.shape)==descriptor['shape'],'Array payload geometry differs')
    low=math.inf;high=-math.inf;count=0
    for start in range(0,value.size,1<<20):
        part=value.reshape(-1)[start:start+(1<<20)]
        require(bool(np.isfinite(part).all())and(not positive or bool((part>0).all())),'Nonfinite/nonpositive stored priorities')
        if part.size:low=min(low,float(part.min()));high=max(high,float(part.max()));count+=int(part.size)
    del value
    return dict(elements=count,minimum=low,maximum=high,finite=True,strictly_positive=positive)


def bank_payloads(snapshot,np,tools):
    result={}
    for name,bank in snapshot['banks'].items():
        lengths=bank['metadata']['ep_len'];games=bank['metadata']['ep_game'];levels=bank['metadata']['ep_level']
        require(len(lengths)==len(games)==len(levels)==bank['counts']['episodes']
            and 0<bank['counts']['episodes']<=snapshot['spec']['episode_capacity'],
            'Exact sealed episode count/capacity/UID metadata required')
        # Source permits legacy -1 UID sentinels. Preserve every actual value;
        # do not invent a positive UID or reject a supported historical bank.
        require(all(type(v)is int for v in games),'Invalid persisted bank episode UID type')
        fields={}
        for field,row in bank['arrays'].items():
            full=pin(row['path'])
            require(full['identity']['bytes']==row['identity']['size'],'Bank payload extent changed')
            value=np.load(row['path'],allow_pickle=False,mmap_mode='r')
            valid=tools.bank_valid_prefix_payload(value,lengths,bank['metadata']['scalars']['stride'],np)
            if value.dtype.kind=='f':
                for episode,length in enumerate(lengths):
                    for start in range(0,length,256):
                        part=value[episode*bank['metadata']['scalars']['stride']+start:
                            episode*bank['metadata']['scalars']['stride']+min(length,start+256)]
                        require(bool(np.isfinite(part).all()),'Nonfinite valid bank field: '+name+'/'+field)
            del value
            require(identity(Path(row['path']).stat())==full['identity'],
                'Bank file changed during valid-prefix value capture')
            fields[field]=dict(file=full,valid_prefix=valid)
        result[name]=dict(fields=fields,episode_metadata=copy.deepcopy(bank['metadata']),
            selector=copy.deepcopy(bank['selector']),all_eight_complete_files_hashed=True,
            valid_prefix_float_values_finite=True,padding_not_interpreted_as_training_rows=True)
    return result


def ring_scalar_payloads(snapshot,np,tools):
    result={}
    fields=set(snapshot['ring']['arrays'])-{'states','next_states'}
    require(fields=={'actions','rewards','dones','horizons','is_expert','actor_kind','interesting','priorities'},
        'Exact eight ring scalar arrays required')
    for name in sorted(fields):
        row=snapshot['ring']['arrays'][name];source=pin(row['path'])
        value=np.load(row['path'],allow_pickle=False,mmap_mode='r')
        require(value.dtype.str==row['dtype']and list(value.shape)==row['shape'],'Ring scalar geometry differs')
        payload=tools.ndarray_payload(value,np)
        if value.dtype.kind=='f':
            for start in range(0,value.size,1<<20):
                require(bool(np.isfinite(value[start:start+(1<<20)]).all()),'Nonfinite ring scalar field: '+name)
        del value
        require(identity(Path(row['path']).stat())==source['identity'],'Ring scalar changed during exact capture')
        result[name]=dict(file=source,payload=payload)
    return result


def fulfill_bank_intent(intent,final_banks,old_semantics,new_semantics,stop_time,*,episode_capacity):
    """7c8 predicate body with exact actual count bounded by declared capacity.

    Prior maintenance knew both banks were full192. Here neither a bank shrink
    nor a padded fake192 is accepted: actual sealed count must remain identical.
    """
    require(set(final_banks)==set(intent['target_revisions'])=={'hof','ephof'},'Both final bank generations required')
    for name,target in intent['target_revisions'].items():
        bank=final_banks[name];prior=intent['banks'][name]
        require(bank['selector']['mutation_generation']==target
            and bank['pointer']['mtime_ns']>=int(stop_time*1e9)
            and bank['episodes']==prior['episodes']and 0<bank['episodes']<=episode_capacity
            and bank['stride']==prior['stride']and bank['state_size']==prior['state_size']==11128
            and bank['captured_adds']>=prior['captured_adds'],
            'Final synchronous bank save did not fulfill its sealed RAM revision/geometry: '+name)
        if not intent['dirty_at_seal'][name]:
            left,right=old_semantics[name],new_semantics[name]
            moving={'captured_adds.npy','stale_age.npy','stale_age_normal.npy'}
            require(set(left)==set(right)and all(left[key]==right[key]for key in set(left)-moving)
                and bank['transitions']==prior['transitions']
                and all(json.dumps(prior['arrays'][key]['header'],sort_keys=True,allow_nan=False)==json.dumps(bank['arrays'][key]['header'],sort_keys=True,allow_nan=False)
                    and prior['arrays'][key]['bytes']==bank['arrays'][key]['bytes']for key in prior['arrays']),
                'Unchanged clean bank episode metadata/geometry moved: '+name)
    return dict(final_synchronous_bank_generations_verified=True,target_revisions=intent['target_revisions'],
        dirty_at_seal=intent['dirty_at_seal'],all_target_revisions_now_persisted=True,
        actual_state_payload_values_read_or_hashed=False)


def ring_continuity(snapshot,job,seal):
    """Require Root's source-qualified pointer anchor, never assume accepted0."""
    selected=read(job['ring_storage_before']);anchor=read(job['ring_insert_anchor'])
    require(selected['spec']==snapshot['spec'],'Original ring geometry changed')
    for name,left in selected['ring']['arrays'].items():
        right=snapshot['ring']['arrays'][name]
        require(all(left[k]==right[k]for k in('path','dtype','shape','data_offset','data_bytes','header_sha256'))
            and all(left['identity'][k]==right['identity'][k]for k in('device','inode','size','uid','nlink')),
            'Original replay storage replaced: '+name)
    exposure=seal['replay_exposure']
    require(anchor['schema']=='robotron-source-bound-replay-pointer-insertion-anchor-v1'
        and anchor['owner']==OWNER and anchor['process_id']==exposure['process_id']
        and anchor['instance_monotonic_ns']==exposure['instance_monotonic_ns']
        and anchor['epoch']==exposure['epoch']==1 and anchor['epoch_reason']==exposure['epoch_reason']
        and type(anchor['ptr'])is int and 0<=anchor['ptr']<6000000
        and type(anchor['accepted_total'])is int and 0<=anchor['accepted_total']<=exposure['accepted_total'],
        'Actual same-producer pointer/insertion anchor required')
    checked(anchor['source_evidence'],immutable=True,limit=4<<20)
    expected=(anchor['ptr']+exposure['accepted_total']-anchor['accepted_total'])%6000000
    require(snapshot['ring']['meta']['ptr']==expected and snapshot['ring']['meta']['size']==6000000,
        'Final ring ptr/size does not fulfill original insertion position')
    return dict(source_anchor=job['ring_insert_anchor'],expected_pointer=expected,
        actual_completed_insertions_since_anchor=exposure['accepted_total']-anchor['accepted_total'],
        all_original_ten_storage_objects_and_headers_preserved=True,ring_state_payloads_hashed=False)


def execute(args):
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and 'LD_PRELOAD'not in os.environ and 'PYTHONPATH'not in os.environ,
        'Fresh CPU-hidden isolated process required')
    require(not any(n=='torch'or n.startswith('torch.')or n=='numpy'or n.startswith('dqn')for n in sys.modules),
        'Fresh stdlib-only process required')
    self_pin=pin(Path(__file__).resolve());require(self_pin['sha256']==args.source_sha256,'Exact selected verifier source required')
    job_pin=pin(Path(args.job).resolve());require(job_pin['sha256']==args.job_sha256,'Exact original stopped CPU job required')
    job=read(job_pin)
    require(job['schema']==SCHEMA and job['source']==self_pin and job['original_attempt']==1 and job['no_retry']is True,
        'Exact original stopped CPU job required')
    require(job['unit']=='robotron-current-continuous-header-stopped600-'+job['current_selection']['sha256'][:16]+'.service',
        'Unique original stopped-state CPU unit required')
    raw=subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=10)
    fields=dict(line.split('=',1)for line in raw.splitlines()if'='in line)
    expected=dict(Id=job['unit'],MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],
        CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',
        RuntimeMaxUSec='10min',Restart='no',NRestarts='0')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual original600s/2CPU/4GiB scope differs')
    select_context(job)
    require(job['owner']==OWNER and set(job['clock_floor'])==set(CLOCKS)
        and all(type(v)is int and v>0 for v in job['clock_floor'].values()),'Exact owner/final four clocks required')
    deps={}
    for name,(path,digest)in DEPENDENCIES.items():
        value=job['dependencies'][name]
        require(value['path']==str(path)and value['sha256']==digest,'Selected strict source differs: '+name)
        # Only the exact installed bank witness is a normal0664 source. It is
        # bound by full8/path/SHA; canonical production sources are never chmod'd.
        deps[name]=load('_stopped_fullstate_'+name,value,immutable=name!='bank_witness')
    tools_pin=job['dependencies']['manifest_tools']
    require(tools_pin['path']=='/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/state-sources/restoration_manifest_tools_v1.py'
        and tools_pin['sha256']==MANIFEST_TOOLS_SHA,'Exact shared typed-tree contract required')
    tools=load('_stopped_fullstate_manifest_tools',tools_pin)
    for value in job['inputs']:checked(value,immutable=value['identity']['mode']=='0o444')
    authority,api,seal,terminal=verify_api_and_authority(job,deps['poststop_semantics'])
    absence_before=old_owner_absent(job['owner'])
    require(job['boot_CPU_report']['sha256']==BOOT_SHA and job['phase_record']['sha256']==RECORD_SHA
        and job['phase_anchor']['sha256']==PHASE_ANCHOR_SHA,'Actual current boot/phase anchors required')
    boot,record,anchor=(read(job[k])for k in('boot_CPU_report','phase_record','phase_anchor'))
    require(boot['schema']=='robotron-actual-continuous-boot-state-descriptor-v1'
        and boot['owner']==OWNER and boot['CUDA_initialized']is False
        and boot['fresh_CPU_test_or_new_runtime_qualification_claimed']is False,
        'Actual restored startup descriptor required; no new CPU report is fabricated')
    recipe=deps['recipe_verifier']
    base,specialization=select_current_recipe(job,recipe)
    require(specialization['selected_recipe']['learning_control_lr_scale']==.0625
        and specialization['selected_recipe']['max_samples_per_frame']==job['expected_current_cap'],
        'Exact .0625 selected current-cap recipe required')
    output=Path(job['output_directory'])
    require(output.is_absolute()and output.resolve(strict=False)==output and not output.exists()
        and output.parent.is_dir(),'Exclusive new Root output required')
    output.mkdir(mode=0o700);base.DIRECTORY=output
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_FSIZE,(32<<20,32<<20))
    evidence=dict(schema='robotron-stopped-full-training-state-CPU-result-v1',status='RUNNING',bound_files={},
        original_job=job_pin,source=self_pin,recipe_specialization=specialization,absence_before=absence_before,
        actual_scope=fields)
    started=time.monotonic()
    try:
        model_dir=base.check_context(job,evidence)
        require(model_dir==ROOT/'models_dqn'and job['source_checkpoint']['path']==str(model_dir/'robotron_dqn_latest.pt'),
            'Actual final latest source required')
        checkpoint_job=dict(job,source=job['source_checkpoint'])
        copied=base.check_root_copy(checkpoint_job,evidence)
        snapshot=deps['bank_descriptors'].stopped_state(job['bank_spec'])
        ring_proof=ring_continuity(snapshot,job,seal)
        print(json.dumps(dict(phase='STRICT_CHECKPOINT_ALL_MODEL_ADAM_SCALER')),flush=True)
        def metadata(checkpoint,ev):
            torch=sys.modules['torch']
            current_phase(checkpoint,ev,anchor,record,boot,job['clock_floor'],api,tools,torch)
        base.validate_checkpoint(copied,job['clock_floor'],evidence,metadata_callback=metadata)
        import numpy as np
        priority=snapshot['ring']['arrays']['priorities']
        priorities_pin=pin(priority['path']);priority_values=scan_array(priority['path'],priority,np,positive=True)
        require(snapshot['ring']['meta']['max_priority']>=priority_values['maximum'],
            'Persisted max-priority hint is below an actual stored priority')
        final_banks={name:deps['bank_witness'].read_bank_generation(name,model_dir/('robotron_dqn_latest_replay_'+name))for name in('hof','ephof')}
        semantics=deps['poststop_semantics'].bank_metadata_semantics(final_banks,deps['bank_witness'])
        fulfillment=fulfill_bank_intent(seal['bank_pair'],final_banks,
            seal['bank_metadata_semantics'],semantics,api['ts'],episode_capacity=job['bank_spec']['episode_capacity'])
        print(json.dumps(dict(phase='COMPLETE_SELECTED_BANK_FILES_AND_VALID_ROWS')),flush=True)
        banks=bank_payloads(snapshot,np,tools)
        ring_scalars=ring_scalar_payloads(snapshot,np,tools)
        require(deps['bank_descriptors'].stopped_state(job['bank_spec'])==snapshot,'Ring/bank descriptors changed during stopped verification')
        require(pin(priority['path'])==priorities_pin,'Ring priorities changed during stopped verification')
        priorities=np.load(priority['path'],allow_pickle=False,mmap_mode='r')
        priority_payload=tools.ndarray_payload(priorities,np);del priorities
        absence_after=old_owner_absent(job['owner'])
        for name,before in evidence['bound_files'].items():require(base.fingerprint(before['path'])==before,'Strict bound file changed: '+name)
        for value in job['inputs']:checked(value,immutable=value['identity']['mode']=='0o444')
        require(pin(Path(args.job).resolve())==job_pin and pin(Path(__file__).resolve())==self_pin,'Original job/verifier changed')
        manifest=dict(schema=MANIFEST_SCHEMA,status='VERIFIED_STOPPED_STATE',original_job=job_pin,
            source=self_pin,manifest_tools=tools_pin,checkpoint=job['source_checkpoint'],verification_copy=job['verification_copy'],
            owner=job['owner'],stopped_authority=job['stopped_authority'],boot_CPU_report=job['boot_CPU_report'],
            original_terminal_verification=terminal,
            phase_record=job['phase_record'],phase_anchor=job['phase_anchor'],recipe=copy.deepcopy(evidence['held_recipe_context']),
            checkpoint_payload=evidence.pop('restoration_payload'),saved_scalars=evidence['saved_scalars'],
            priority_metric_phase=evidence['saved_priority_metric_phase'],ring_and_banks=snapshot,
            ring_continuity=ring_proof,ring_priorities=dict(file=priorities_pin,payload=priority_payload,scan=priority_values),
            ring_scalar_payload=ring_scalars,
            bank_payload=banks,bank_intent_fulfillment=fulfillment,absence_before=absence_before,absence_after=absence_after,
            ring_states_and_next_states_full_payload_hashed=False,all_bank_fields_full_files_hashed=True,
            RNG_state_saved=False,per_client_or_MAME_RAM_restored=False,
            startup_restore_verified=False,execution_or_actor_admission_authorized=False,quality_qualified=False,promotion=False)
        mp=put(output/'restoration-manifest.json',manifest)
        evidence.update(status='PASS',restoration_manifest=mp,checkpoint=job['source_checkpoint'],
            phase_metadata_verified=True,all_81_Adam_states_and_moments_verified=True,
            GradScaler_full_state_verified=True,all_saved_scalar_clocks_captured=True,
            full_bank_field_files_and_valid_prefixes_verified=True,ring_storage_headers_and_priority_values_verified=True,
            ring_state_payloads_read_or_hashed=False,elapsed_s=time.monotonic()-started,
            CUDA_initialized=False,any_training_or_control_action=False,quality_qualified=False,promotion=False)
        report=put(output/'cpu-verification.json',evidence)
        print(json.dumps(dict(status='PASS',report=report,restoration_manifest=mp)),flush=True)
        return 0
    except BaseException as error:
        evidence.update(status='FAIL',error=repr(error),traceback=traceback.format_exc(),elapsed_s=time.monotonic()-started)
        try:put(output/'verification-error.json',evidence)
        except BaseException as secondary:print('Error evidence publication failed: '+repr(secondary),file=sys.stderr)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if args.execute:raise SystemExit(execute(args))
    print('PLAN_ONLY_NO_READS_IMPORTS_OUTPUTS_OR_ACTIONS')
