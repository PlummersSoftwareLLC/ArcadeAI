"""UNSELECTED later-policy quality32 reviewer template with complete mixed main-health replay.

No numerical runtime, games, signals, retry, promotion or main mutation. Every
original min50/all32 full tail must pass. A valid leg does not qualify a policy;
NEW fixed R1+R2 and separate C1/C2 confirmation gates remain required.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=G/'tools/startup_policy_journal_proposal'
R=G/'logs/managed-learning-20261015/run-26'
SELECTED_RUNTIME=Path(__file__).with_name('run_fullgame_rounds_v7.py')
NEW_CANDIDATE_CLOCK_FLOOR={'learner_frame_count': 3041579470, 'training_steps': 11979944, 'optimized_samples': 47494055936, 'frame_count': 5918642727}
SLOTS=tuple(range(4096,4128))
GPU='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
PAIR_SHA='0'*64
POLICIES={}
ROLES={'R1':'reference','C1':'candidate','R2':'reference','C2':'candidate'}
RUNTIME_SHA='0'*64
PROPERTIES=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=22260',
    'TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no']


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


COHORT_SELECTION = dict(
    schema='robotron-fixed-slot64-selection-v1',
    strategy='first_two_known_starts_per_declared_slot', actor_slots=list(SLOTS),
    games_per_slot=2, expected_games=64, minimum_complete_games=50,
    outer_start_horizon_s=21540, whole_cohort_timeout_from_enter_s=21600,
    timestamp_close_role='outer_start_horizon',
    selector_source_sha256='494dcdbcb0ae30f95f4724435e6bf61c68bec3aa7fc3705e39636c0ba60ddbd0')


def same_completed_membership(saved,fresh):
    """Permit append-only outside starts after the terminal controller tick.

    Every selected member, result and accounting field must still match.
    Extra starts remain in the original raw journals for independent audit.
    """
    key='retained_outside_cohort_ids'
    if type(saved)is not dict or type(fresh)is not dict:return False
    left,right=saved.get(key),fresh.get(key)
    if type(left)is not list or type(right)is not list:return False
    if right[:len(left)]!=left or len(right)!=len(set(right)):return False
    if set(right)&set(fresh.get('started_ids',[])):return False
    return canonical({k:v for k,v in saved.items()if k!=key})==canonical(
        {k:v for k,v in fresh.items()if k!=key})


def round_contract():
    path=Path(__file__).with_name('fullgame_round_contract_v7.py')
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='62189866a90b7f3f1aa6e56ad517c47625824d68a2a78ff722f9eb8b7d50d0b7','Exact recovered fullgame contract required')
    return load('_recovered_fullgame_round_contract',path)


def validate_scope(job,job_pin,scope,config):
    round_contract().install_pair(job,globals())
    require(PAIR_SHA!='0'*64 and RUNTIME_SHA!='0'*64
        and PAIR_SHA!='3d3169064b25e933218e4d2dce2a3cd62ef5f3f5324354f362a9137671759650'
        and POLICIES['candidate']['sha256']!='697ad174cb7f0c4ffe4221fbfe571f058c679809cce84ccc27ae0966a791d6fc'
        and PAIR_SHA!='75baa58f45fc053041a90e2e5d5a66505c76137122ef647198e164e01bf5af5d'
        and POLICIES['candidate']['sha256']!='b66e751cc32004822272ccb0691f9e524ee94852c8e461299fac57c2985cdfc3'
        and all(type(POLICIES['candidate']['clocks'][key])is int
                and POLICIES['candidate']['clocks'][key]>value for key,value in NEW_CANDIDATE_CLOCK_FLOOR.items()),
        'UNBOUND reviewer requires a distinct fully later candidate/new fixed-reference pair')
    require(PAIR_SHA not in ('7c74a3f8e27b3401404fe5d69bfbabd243f5cd57984b4f8f33087ba05a9a9f51','7862f46a6d42c51ef05fe8be2e97cdf29ad13717412b32451bc94417267bdba6','399f029598471553677c730b97c2ecc174b6fc1c8e295f72e1b319840926890a','24829cde7c4153795a335b9883a57e6c58ef4974879035245c8fbdff7ae16089','a8d442fb60bd5d4859e2c3683f9e91e410c71d33d6b0de3e3b25d87f17d05cb2')
        and all(type(POLICIES['candidate']['clocks'][key])is int and POLICIES['candidate']['clocks'][key]>value for key,value in {'learner_frame_count': 2739279553, 'training_steps': 10864951, 'optimized_samples': 42927044608, 'frame_count': 5347766313}.items()) and POLICIES['candidate']['sha256']!='95726b361f01bceab95bd5deaf6f5534dd1e8d4e7335e38904ae5ca3ee49987d',
        'Unselected reviewer template requires a genuinely later policy/new pair')
    require(job.get('quality_leg')in ROLES and job.get('quality_pair_precommit',{}).get('sha256')==PAIR_SHA
        and job.get('minimum_completed_games')==50
        and job.get('expected_policy_clocks')==POLICIES[ROLES[job['quality_leg']]]['clocks']
        and all(type(v)is int for v in job['expected_policy_clocks'].values()),
        'Exact fixed-role pair, saved clocks and minimum50 required')
    require(job['schema']=='robotron-compiled-quota64-quality-original-v1'
        and job['runtime']['sha256']==RUNTIME_SHA
        and job['runtime']['path']==str(SELECTED_RUNTIME)
        and job['checkpoint']['sha256']==POLICIES[ROLES[job['quality_leg']]]['sha256'] and job['actor_slots']==list(SLOTS)
        and job['gpu_uuid']==GPU and job['backend']=='inductor'and job['device']=='cuda'
        and job['origin_port']==19998 and job['proxy_ports']=={str(s):20000+s-4096 for s in SLOTS}
        and job['startup_trace_frames']==1200 and job['admission_s']==21540
        and job['whole_cohort_timeout_s']==21600 and job['wall_limit_s']==22200,
        'Exact original full-tail-v2 engineering scope required')
    require('acceptance_scope'not in job and job['historical_startup_acceptance_scope']['sha256']==
        '692b5c0572d32ffae79b828eb64296c09eaa6b4e59de28ea9316b7f44a59fc77',
        'Historical prefix acceptance cannot be this case acceptance')
    require(scope['schema']=='robotron-original-all32-quota64-quality-acceptance-v1'
        and scope['job']==job_pin and scope['original_attempt']==1 and scope['no_retry']is True
        and scope['outer_start_horizon_s']==21540 and scope['whole_cohort_timeout_s']==21600
        and scope['admission_mode']==COHORT_SELECTION['strategy'] and scope['expected_selected_games']==64
        and scope['wall_limit_s']==22200 and scope['startup_trace_frames']==1200
        and scope['minimum_quality_completed_games']==50 and scope['quality_minimum_games_remains']==50
        and scope['quality_qualified']is scope['promotion']is False,
        'Exact separately precommitted full-tail acceptance required')
    expected=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',
        job['runtime']['path'],'--execute','--job',job_pin['path'],'--job-sha256',job_pin['sha256'],
        '--source-sha256',RUNTIME_SHA]
    require(config['argv']==expected and config['properties']==PROPERTIES
        and config['observation_s']==22320 and re.fullmatch(
            r'robotron-compiled-full-tail32-integration-[a-z0-9_-]+\.service',config['unit']),
        'Exact precommitted controller argv/resources required')


def validate_native_fields(fields,config,owner,duration):
    require(fields['Id']==owner['unit']==config['unit']
        and fields['InvocationID']==owner['invocation_id']and fields['ExecMainPID']==str(owner['pid'])
        and fields['ExecMainCode']=='1'and fields['ExecMainStatus']=='0'and fields['NRestarts']=='0'
        and duration(fields['CPUQuotaPerSecUSec'])==12 and fields['MemoryMax']==str(16<<30)
        and fields['MemorySwapMax']=='0'and duration(fields['RuntimeMaxUSec'])==22260
        and fields['TasksMax']=='512'and duration(fields['TimeoutStopUSec'])==30
        and fields['KillMode']=='mixed'and fields['SendSIGKILL']=='no'and fields['Restart']=='no',
        'Actual original native exit/identity/resources differ')
    command=' '.join(config['argv'])
    require(command+' ; ignore_errors=no ;'in fields['ExecStart'],
            'Actual systemd command differs from the original runtime/job/source pins')
    start=int(fields['ExecMainStartTimestampMonotonic'])/1e6
    end=int(fields['ExecMainExitTimestampMonotonic'])/1e6
    require(0<start<end<=time.monotonic()and end-start<=22260,'Original actual runtime interval differs')
    return start,end



def validate_initial_readiness(receipt,receipt_pin,job,job_pin,raw,loaded_pin,admission,started,ended):
    """Require raw-recomputed readiness closure before private policy/game setup."""
    ready=raw['transport']['initial_readiness']
    require(receipt['schema']=='robotron-native-initial-main-readiness-v1'
        and receipt['original_job']==job_pin and receipt['runtime']==job['runtime']
        and receipt['main_health_protocol']==job['main_health_protocol']
        and receipt['before_sidecar_Torch_policy_or_MAME']is True,
        'Original readiness receipt source/job/protocol/order differs')
    require(type(ready['first_qualified_baseline_index'])is int
        and type(receipt['first_qualified_baseline_index'])is int
        and type(receipt['unaccepted_initial_samples'])is int
        and type(ready['unaccepted_samples'])is int
        and ready['first_qualified_baseline_index']==ready['unaccepted_samples']
        and 0<=ready['unaccepted_samples']<=10
        and receipt['first_qualified_baseline_index']==ready['first_qualified_baseline_index']
        and receipt['first_qualified_baseline_unix_s']==ready['first_qualified_baseline_unix_s']
        and receipt['unaccepted_initial_samples']==ready['unaccepted_samples'],
        'Original readiness receipt differs from complete unfiltered raw replay')
    first=ready['first_qualified_baseline_unix_s'];observed=receipt['observed_unix_s']
    mono=receipt['observed_monotonic_s'];loaded=loaded_pin['identity']['mtime_ns']/1e9
    require(all(type(value)in (int,float)and math.isfinite(value)for value in (first,observed,mono,loaded))
        and 0<=first-raw['first_observed_unix_s']<=2
        and started<=mono<=ended
        and first<=observed<=loaded<=admission['open_unix_ns']/1e9
        and receipt_pin['identity']['mtime_ns']<=loaded_pin['identity']['mtime_ns'],
        'Initial readiness was not closed within its bound before loaded policy/admission')
    return dict(original_receipt=receipt_pin,first_qualified_baseline_index=ready['first_qualified_baseline_index'],
        first_qualified_baseline_unix_s=first,unaccepted_initial_samples=ready['unaccepted_samples'],
        before_private_policy_and_game_setup_verified=True,quality_qualified=False)


def validate_runtime_result(result,job):
    require(type(result.get('main_observer_lifecycle'))is dict and type(result.get('initial_main_readiness'))is dict and type(result.get('main_health_report'))is dict and result.get('main_health_failure')is None
        and result['main_health_protocol']==job['main_health_protocol']
        and result['source_family_manifest']==job['source_family_manifest'],
        'Original native complete mixed health report/protocol/family required')
    require(result['quality_leg']==job['quality_leg']and result['quality_pair_precommit']==job['quality_pair_precommit']
        and result['expected_policy_clocks']==job['expected_policy_clocks']
        and type(result['minimum_completed_games'])is int and result['minimum_completed_games']==50,
        'Actual original quality leg/pair/saved clocks/minimum differ')
    require(result['schema']=='robotron-compiled-quota64-quality-original-result-v1'
        and result['status']=='PASS_ALL32_COMMON_COMPILED_CERTIFIED_QUALITY_COHORT_AND_HOST_DRAIN'
        and result['complete']is True and result['errors']==[]and result['original_attempt']==1
        and result['no_retry']is True and result['original_lease_released']is True
        and result['immutable_inputs_unchanged']is True and result['all_original_threads_stopped']is True
        and result['main_observation_failures']==[]and result['original_unsealed_journal_paths']==[]
        and result['quality_qualified']is result['full_game_score_verified']is False,
        'Original runtime did not finish validly or retain exact owned closure')
    policy=result['policy_before'];require(policy==result['policy_after'],'Loaded frozen policy changed')
    require(policy['checkpoint_sha256']==job['checkpoint']['sha256']==POLICIES[ROLES[job['quality_leg']]]['sha256']
        and policy['measurement_active']is True and policy['training_enabled']is policy['replay_enabled']is False
        and policy['epsilon']==policy['expert_ratio']==0
        and all(policy[k]==job['expected_policy_clocks'][k]for k in
                ('learner_frame_count','training_steps','optimized_samples')),'Protected actual loaded policy/clocks/isolation differ')
    require(canonical(policy['cohort_selection'])==canonical(result['cohort_selection'])==canonical(COHORT_SELECTION)
        and result['expected_selected_games']==64,'Exact selected per-slot count strategy changed')
    numeric=policy['numeric_policy']
    require(numeric['compiled']is True and numeric['backend']=='inductor'and numeric['device']=='cuda:0'
        and numeric['weights']==numeric['inputs']==numeric['support']=='float32'and numeric['autocast']is False
        and numeric['warm_shapes']==list(range(1,17))and numeric['max_batch_size']==16
        and numeric['serving_thread_checked']is True and numeric['graph_breaks']==0,
        'Common compiled backend/serving-thread context changed')
    cohort=result['before_intentional_stop']
    require(same_completed_membership(result['controller_exit']['cohort'],cohort)
        and same_completed_membership(cohort,result['after_intentional_stop'])
        and cohort['closed']is cohort['complete']is cohort['valid']is True
        and cohort['pending']==cohort['abandoned']==0 and cohort['count']==cohort['started']==64
        and cohort['closed_by']=='slot_quota'
        and cohort['slot_admitted_counts']=={str(slot):2 for slot in SLOTS}
        and len(cohort['rows'])==len(cohort['started_ids'])==len(set(cohort['started_ids']))==cohort['count']
        and cohort['pending_ids']==cohort['abandoned_ids']==[]
        and cohort['started_actor_slots']==list(SLOTS),'Original full cohort changed or lost a tail')
    controller=result['controller_exit']
    require(controller['active']is False and controller['phase']=='finished'
        and controller['complete']is controller['valid']is True and controller['reason']is None,
        'Original measurement did not remain valid through teardown')
    reaped=result['original_post_origin_child_reap']
    require(reaped['all_original_children_reaped']is True and reaped['unknown_slots']==[]
        and reaped['signals_sent']is reaped['exit_statuses_normalized']is False
        and set(reaped['original_children'])==set(result['original_slots'])=={str(s)for s in SLOTS},
        'Original actual child wait is incomplete or normalized')
    for slot,entry in result['original_slots'].items():
        child=reaped['original_children'][slot]
        require(entry['actual_exit']==child['actual_exit']==0
            and entry['pid']==child['pid']and entry['birth']==child['birth']
            and entry['outputs_sealed_after_original_writer_closure']is True
            and entry['original_unsealed_output_paths']==[]and entry['peer_EOF']is True,
            'An original MAME exit/writer closure is missing')
    return policy,cohort


FLAG=re.compile(r'\[SOCKET ACTION TIMEOUT\]|Socket open failed:|Traceback|\b\w*(?:Error|Exception)\b|\bfailed\b|\bunable\b|\bunavailable\b|\bfallback\b|\bdisconnected\b|param mismatch|\[INGEST\] dropped implausible',re.I)
EXPERT="[WARN] Robotron expert unavailable (No module named 'v3'); expert guidance disabled."
ALSA='ALSA lib seq_hw.c:528:(snd_seq_hw_open) open /dev/snd/seq failed: Permission denied'


def audit_actor_logs(stdout,stderr,slot,pid,port):
    text=stdout+'\n'+stderr
    require('[SOCKET ACTION TIMEOUT]'not in text and 'Socket open failed:'not in text
        and 'FULL_STARTUP_ADAPTER_FAILURE'not in text and 'COMPILED32_FULL_TAIL_FATAL'not in text,
        'Original emulator transport/Lua fault or reconnect occurred')
    require(stdout.splitlines().count('MAME interface initialized.')==1
        and stdout.splitlines().count('Socket connection opened to socket.127.0.0.1:'+str(port))==1
        and '[PATCH] RRCHRIS runtime ROM patch disabled.'in stdout
        and '[DIFFICULTY] GA1 poked to 5'in stdout,'Original MAME boot/controls/one connection differ')
    activations=[tuple(map(int,value))for value in re.findall(
        r'\[robotron-socket-wait\] pid=(\d+) fd=(\d+) port=(\d+) interval_us=(\d+)',text)]
    require(any(a[0]==pid and a[2]==port and a[3]==1000 for a in activations),
            'Original owned actor socket-wait activation missing')
    allowed=[]
    for stream,value in [('stdout',stdout),('stderr',stderr)]:
        for index,line in enumerate(value.splitlines(),1):
            if not FLAG.search(line):continue
            require(stream=='stderr'and line==ALSA,'Unclassified original actor log diagnostic: '+line)
            allowed.append(dict(stream=stream,line=index,text=line,classification='exact_disabled_sound_startup'))
    return dict(slot=slot,allowed_diagnostics=allowed,action_timeouts=0,reconnects=0)


def audit_evaluator_logs(stdout,stderr,policy,optional_expert_proof_valid,*,expected_closed_client_ids):
    require(type(expected_closed_client_ids)is set and len(expected_closed_client_ids)==32
        and all(type(cid)is int and cid>=0 for cid in expected_closed_client_ids),
        'All32 independently verified original closed-client identities required')
    require(policy['epsilon']==policy['expert_ratio']==0 and policy['training_enabled']is False,
        'Shutdown log allowances require frozen greedy controls')
    token=re.compile(r'Client ([0-9]+) disconnected: (EOF|Broken payload)')
    allowed=[];closed=set();expert_count=0
    for stream,text in [('stdout',stdout),('stderr',stderr)]:
        for number,line in enumerate(text.splitlines(),1):
            if not FLAG.search(line):continue
            kind=None;line_ids=[]
            if stream=='stdout'and line==EXPERT and optional_expert_proof_valid is True:
                expert_count+=1;require(expert_count==1,'Duplicate optional expert diagnostic')
                kind='exact_unused_optional_expert_import_under_frozen_greedy_inference'
            elif stream=='stdout':
                matches=list(token.finditer(line));cursor=0
                if matches:
                    for match in matches:
                        require(not line[cursor:match.start()].strip(),
                            'Unknown bytes around original shutdown log token: '+line)
                        cid=int(match.group(1))
                        require(cid in expected_closed_client_ids and cid not in closed,
                            'Foreign or duplicate original shutdown client token: '+line)
                        closed.add(cid);line_ids.append(cid);cursor=match.end()
                    require(not line[cursor:].strip(),'Unknown bytes after original shutdown log token: '+line)
                    kind='exact_owned_origin_shutdown_tokens_after_all_admitted_tails_and_all32_peer_EOF'
            require(kind is not None,'Unclassified original evaluator log diagnostic: '+line)
            allowed.append(dict(stream=stream,line=number,text=line,classification=kind,client_ids=line_ids))
    require(closed==expected_closed_client_ids,'Original shutdown log client coverage is incomplete')
    return dict(allowed_diagnostics=allowed,unknown_errors=0,exact_shutdown_tokens=len(closed),
        closed_client_ids=sorted(closed),expected_closed_client_ids=sorted(expected_closed_client_ids))


def review(config_pin,h,reader):
    artifacts=[]
    def read(entry,as_json=True):
        value=reader.read_pin(entry,as_json=as_json);artifacts.append(entry);return value
    config=read(config_pin)
    require(config['schema']=='robotron-original-quota64-independent-leg-review-job-v1',
            'Explicit independent original review job required')
    output=Path(config['output'])
    native_pin=config['native_job'];job=read(native_pin);directory=Path(native_pin['path']).parent
    round_contract().install_pair(job,globals())
    require(output==directory/'independent-quality-leg-review-original01'and directory.is_relative_to(R)
        and output.is_absolute()and not output.exists(),'Fresh exact original review output required')
    output.mkdir(mode=0o700)
    intent=h.put(output/'original-review-intent.json',dict(source=h.pin(__file__),review_job=config_pin,
        native_job=native_pin,original_attempt=1,no_retry=True,observed_unix_s=time.time()))
    report=dict(schema='robotron-original-quota64-independent-cohort-review-v1',valid=False,
        quality_qualified=False,promotion=False,full_game_score_verified=False,learning_speed_gain_verified=False,
        main_runtime_changed=False,review_job=config_pin,original_intent=intent,artifacts=artifacts)
    try:
        required={'runtime','control','wire','games','native_closure','main_supervision','main_window','terminal_rom',
            'main_health_engine','main_prefix_validator','main_observer_reviewer'}
        require(set(config['sources'])==required,'Exact independent review dependency set required')
        modules={}
        for key,entry in config['sources'].items():
            read(entry,False);modules[key]=load('_closed_full_tail_'+key+'_'+str(len(sys.modules)),entry['path'])
        wire,games,runtime,control,rt,sup,window,rom=[modules[k]for k in
            ('wire','games','runtime','control','native_closure','main_supervision','main_window','terminal_rom')]
        require(config['sources']['runtime']==job['runtime']and config['sources']['runtime']['sha256']==RUNTIME_SHA,
                'Original runtime source differs')
        wire.dependencies()
        scope=read(config['acceptance']);controller_config=read(config['controller_config'])
        validate_scope(job,native_pin,scope,controller_config)
        pair=read(job['quality_pair_precommit'])
        selected=pair[ROLES[job['quality_leg']]]
        require(selected['policy']==job['checkpoint']
            and all(selected['saved_clocks'][k]==job['expected_policy_clocks'][k]for k in selected['saved_clocks']),
            'Original immutable pair policy/CPU clocks differ')
        cpu=read(selected['CPU_report']);read(selected['original_CPU_readback'])
        cpu_sha=cpu.get('sha256',cpu.get('candidate',{}).get('sha256'))
        require(cpu['status']=='PASS'and cpu_sha==job['checkpoint']['sha256']
            and all(cpu['clocks'][k]==v for k,v in job['expected_policy_clocks'].items()),
            'Original independently verified selected policy CPU report differs')
        control.checked_config(config['controller_config']['path'])
        for entry in controller_config['pins']:require(control.pin(entry['path'])==entry,'Controller original input changed')
        require(any(entry['path']==config['acceptance']['path']and entry['sha256']==config['acceptance']['sha256']
            for entry in controller_config['pins']),'Actual full-tail scope was not controller-pinned')
        for entry in job['inputs']:h.checked(entry)
        root,package_pins=h.package_inputs(job['source_package'])
        controller_pin=h.pin(directory/'controller-original-result.json');controller=read(controller_pin)
        owner_pin=h.pin(directory/'execution-original01/root-original-identity.json');owner=read(owner_pin)
        require(controller['actual_exit']==0 and controller['original_attempt']==1 and controller['no_retry']is True,
                'Original controller failed; no partial-cohort review or retry')
        closure=read(controller['closure']);fields=rt.archived_closure(closure,owner,read,exit_zero=True)
        started,ended=validate_native_fields(fields,controller_config,owner,rt.duration_seconds)
        require(birth(owner['pid'])!=owner['starttime_ticks'],'Original native birth remains')
        for unit in (owner['unit'],owner['timer']):
            require(control.show(unit)['LoadState']=='not-found','Original owned unit remains')
            require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists(),
                    'Original owned cgroup remains')
        out=Path(job['output']);result_pin=h.pin(out/'result.json');result=read(result_pin)
        policy,cohort=validate_runtime_result(result,job)
        acquired=result['acquired_checkpoint'];read(acquired,False)
        require(acquired['path']==str(out/'checkpoint.pt')and acquired['sha256']==job['checkpoint']['sha256']
            and (acquired['identity']['device'],acquired['identity']['inode'])!=
                (job['checkpoint']['identity']['device'],job['checkpoint']['identity']['inode']),
            'Actual inference acquisition was not an independent protected policy copy')
        loaded=read(h.pin(out/'original-loaded-policy.json'))
        stopped=read(h.pin(out/'before-intentional-full-tail-origin-stop.json'))
        require(loaded['policy']==stopped['policy']==policy
            and loaded['compile_report']==stopped['compile_report']
            and loaded['compile_report']['all_shapes_verified']==list(range(1,17))
            and loaded['gpu_uuid']==loaded['CUDA_VISIBLE_DEVICES']==job['gpu_uuid']==GPU
            and loaded['memory_is_none']is loaded['optimizer_is_none']is True
            and loaded['replay_enabled']is False and stopped['cohort']==cohort
            and stopped['controller']['complete']is stopped['controller']['valid']is stopped['controller']['active']is True,
            'Original loaded serving backend/controller state changed')
        admission=read(h.pin(out/'original-fixed-admission.json'))
        permit=read(h.pin(out/'original-complete-cohort-drain-permit.json'))
        require(permit['identifier']==result['drain_identifier']==stopped['drain_identifier']
            and {k:v for k,v in permit.items()if k!='identifier'}==result['drain_payload']==stopped['drain_payload'],
            'Original complete-cohort permit differs across its original records')
        payloads={name:read(result['journal'][name],False)for name in
                  ('games.jsonl','measurement_starts.jsonl','lives.jsonl')}
        require(all(entry['path']==str(out/'journal'/name)for name,entry in result['journal'].items()),
                'Original journal path escaped the selected runtime')
        starts=games.indexed(games.lines(payloads['measurement_starts.jsonl']),'start')
        game_rows=games.indexed(games.lines(payloads['games.jsonl']),'game')
        internal=dict(result,_admission=admission)
        prefixes={};actor_evidence={};actor_logs=[]
        expected_files={'producer.jsonl','lifecycle.jsonl','proxy.jsonl','actor-stdout.txt','actor-stderr.txt','boot.lua'}
        for slot in SLOTS:
            entry=result['original_slots'][str(slot)];private=out/'actors'/str(slot)
            actor=read(h.pin(private/'original-actor.json'));actor_evidence[slot]=actor
            require(actor['argv']==runtime.actor_command(job,private)and '-seconds_to_run'not in actor['argv']
                and actor['pid']==entry['pid']and actor['starttime_ticks']==entry['birth']
                and actor['original_job']==native_pin and actor['boot_restore']==entry['boot_restore']
                and birth(entry['pid'])!=entry['birth'],'Original actor command/birth/job differs')
            require(set(entry['files'])==expected_files and all(p['path']==str(private/name)
                for name,p in entry['files'].items()),'Original actor output files escaped or are missing')
            require(actor['lifecycle_identity']==entry['lifecycle_identity']
                and actor['trace_identity']==entry['trace_identity'],'Original precreated file identities changed')
            wire.validate_original_file_identity(actor['lifecycle_identity'],entry['files']['lifecycle.jsonl'])
            wire.validate_original_file_identity(actor['trace_identity'],entry['files']['producer.jsonl'])
            prefix=wire.audit_slot_prefix(slot,entry,job,internal,starts,game_rows,read,h.pin,
                                         expected_job_sha256=native_pin['sha256'])
            prefixes[slot]=prefix
            restore=read(entry['boot_restore'])
            require(restore['seed']==job['boot_seed']and restore['identity']==job['boot_seed']['identity']
                and restore['restored_paths']=={name:str(private/name)for name in restore['files']},
                'Original initialized seed restore differs')
            originals={Path(e['path']).relative_to(Path(job['boot_seed']['directory'])).as_posix():e
                       for e in job['boot_seed']['inputs']if Path(e['path']).name!='manifest.json'}
            require(set(restore['files'])==set(originals)and all(
                restore['files'][name]=={key:originals[name][key]for key in ('bytes','sha256')}
                for name in originals),'Original copied boot bytes differ from the initialized seed')
            actor_logs.append(audit_actor_logs(read(entry['files']['actor-stdout.txt'],False).decode(),
                read(entry['files']['actor-stderr.txt'],False).decode(),slot,entry['pid'],job['proxy_ports'][str(slot)]))
        for key in ('pid','nonce','client_id','journal_game_id','certificate_identifier'):
            require(len({entry[key]for entry in prefixes.values()})==32,'Original all32 distinct '+key+' required')
        original_games=games.review(payloads,cohort,policy,admission,prefixes)
        require(permit['cohort_sha256']==original_games['cohort_fingerprint']
            and set(permit['started_ids'])==set(original_games['admitted_ids'])
            and permit['count']==permit['started']==cohort['count']
            and permit['issued_unix_ns']>=max(int(row['end_unix_s']*1e9)for row in cohort['rows']),
            'Host shutdown preceded or changed original full-game completion')
        outside=permit['retained_outside_start_ids']
        require(type(outside)is list and len(outside)==len(set(outside))
            and original_games['retained_outside_start_ids'][:len(outside)]==outside
            and canonical(permit['cohort_selection'])==canonical(COHORT_SELECTION),
            'Original outside-start prefix or permit quota descriptor changed')
        tails=[]
        for slot in SLOTS:
            entry=result['original_slots'][str(slot)];subject={k:prefixes[slot][k]for k in ('slot',)}
            subject.update(session=job['sessions'][str(slot)],connection=job['connections'][str(slot)])
            registration=next(r for r in permit['original_subjects']if r['slot']==slot)
            require(all(registration[k]==prefixes[slot][k]for k in
                ('journal_game_id','certificate_identifier','client_id','nonce')),
                'Host shutdown registration differs from original raw startup')
            lifecycle=games.lines(read(entry['files']['lifecycle.jsonl'],False))
            require(lifecycle==entry['lifecycle'],'Original saved Lua lifecycle differs from its raw bytes')
            tails.append(wire.audit_applied_tail(wire.wire_rows(read(entry['files']['proxy.jsonl'],False)),
                lifecycle,entry,subject,permit,original_games['cohort_fingerprint'],policy,admission))
        checked_health=round_contract().review_health(job,native_pin,result,owner,controller_config,admission,started,ended,read,h)
        report['main_observer_independently_verified']=checked_health['checked']
        report['initial_main_readiness_verified']=checked_health['receipt']
        report.update(main_health_raw_replay=checked_health['checked'],
            main_health_case_roles=list(ROLES)[:list(ROLES).index(job['quality_leg'])+1],
            main_health_engine=config['sources']['main_health_engine'],source_family_manifest=job['source_family_manifest'])
        health=checked_health['health']
        rom.validate_optional_expert_proof()
        # systemd-owned stdout/stderr are normal files; preserve exact terminal
        # bytes in this review without changing their original mode or receipt.
        evaluator_text={}
        for name in ('stdout.txt','stderr.txt'):
            path=directory/'execution-original01'/name;before=h.pin(path);raw=path.read_bytes()
            require(h.pin(path)==before,'Original terminal log changed during capture')
            target=output/('original-native-'+name)
            with target.open('xb')as stream:
                stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
            artifacts.append(h.pin(target))
            evaluator_text[name]=raw.decode(errors='replace')
        logs=audit_evaluator_logs(evaluator_text['stdout.txt'],evaluator_text['stderr.txt'],policy,True,
            expected_closed_client_ids={prefix['client_id']for prefix in prefixes.values()})
        h.checked(result['socket_wait_library'])
        require(h.pin(job['lease']['path'])==job['lease'],'Persistent GPU coordinator changed')
        import fcntl
        fd=os.open(job['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)
        for port in [19998,*range(20000,20032)]:
            with socket.socket()as probe:probe.bind(('127.0.0.1',port))
        gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],
            capture_output=True,text=True,timeout=10)
        require(gpu.returncode==0 and GPU not in gpu.stdout,'Private GPU0 remains occupied')
        for entry in job['inputs']+package_pins+[acquired]:h.checked(entry)
        for entry in config['sources'].values():read(entry,False)
        require('torch'not in sys.modules,'Independent reviewer imported numerical runtime')
        report.update(valid=True,status='PASS_ORIGINAL_QUOTA64_ALL32_FULL_GAMES_AND_RUNTIME',
            original_native_job=native_pin,original_acceptance=config['acceptance'],original_controller_result=controller_pin,
            original_owner=owner_pin,original_closure=controller['closure'],actual_runtime_exit=0,actual_controller_exit=0,
            original_result=result_pin,policy=policy,compile_report=loaded['compile_report'],
            original_games=original_games,raw_prefixes=list(prefixes.values()),applied_tail_shutdown=tails,
            quality_leg=job['quality_leg'],quality_pair_precommit=job['quality_pair_precommit'],
            minimum_quality_complete_games=50,outer_start_horizon_s=21540,expected_selected_games=64,cohort_selection=COHORT_SELECTION,
            actor_logs=actor_logs,evaluator_logs=logs,main_observations=health,
            full_game_score_verified=True,all_admitted_games_retained=True,all32_actual_MAME_exits=0,
            all6_original_descriptors_verified=True,actual_descriptor_exits=[r['exit']for r in closure['full_original_archives']],
            exact_owned_births_unit_timer_cgroup_absent=True,private_GPU_ports_and_coordinator_released=True,
            original_outputs_sealed_after_writer_exit=True,postprefix_raw_reconstructable=False,
            qualification_limit='One independently valid all64 first-two-per-slot/all32 complete-game quality leg with minimum50 floor. A NEW fixed fresh R1+R2 reference and separate C1/C2 mean>=1.05/median-preserving gates are still required before policy qualification. No pooled candidate, retry, promotion, throughput or learning-speed claim.')
    except Exception as error:
        report.update(status='ORIGINAL_QUALITY32_LEG_REVIEW_INVALID_NO_RETRY',error=repr(error))
    report['observed_unix_s']=time.time()
    proof=h.put(output/'review.json',report)
    print(json.dumps(dict(review=proof,valid=report['valid'],quality_qualified=False)),flush=True)
    return 0 if report['valid']else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe',action='store_true');parser.add_argument('--job')
    parser.add_argument('--job-sha256');parser.add_argument('--expected-source-sha256');args=parser.parse_args()
    if not args.observe:print('PLAN_ONLY: no original review, runtime or outputs');return 0
    helper=HERE/'run_full_policy_startup_v3.py'
    require(hashlib.sha256(helper.read_bytes()).hexdigest()==
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1','Review helper source changed')
    h=load('_original_full_tail_final_helpers',helper)
    require(args.job and args.job_sha256 and args.expected_source_sha256
        and h.pin(__file__)['sha256']==args.expected_source_sha256,'Explicit original review/source bindings required')
    reader_path=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    require(hashlib.sha256(reader_path.read_bytes()).hexdigest()==
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','Immutable reader source changed')
    reader=load('_original_full_tail_immutable_reader',reader_path)
    pin=h.pin(args.job);require(pin['sha256']==args.job_sha256,'Original review job changed')
    return review(pin,h,reader)


if __name__=='__main__':sys.exit(main())
