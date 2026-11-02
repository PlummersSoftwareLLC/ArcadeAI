"""One independent original min50 quality32 leg review for the fixed1741/2202 pair.

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
SLOTS=tuple(range(4096,4128))
GPU='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
PAIR_SHA='79ae0a32e8d924d36517dbd76e6b97bb34309f695d0b913a28da514b3a269b90'
POLICIES={
    'reference':dict(sha256='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83',
        clocks=dict(learner_frame_count=1741229950,training_steps=7128160,optimized_samples=27621148672,frame_count=3434514217)),
    'candidate':dict(sha256='7dc8b12238ae8969eb5e66d3c6ff9769338496db697f49e826f71dfab1d2a744',
        clocks=dict(learner_frame_count=2202676281,training_steps=8863417,optimized_samples=34728761344,frame_count=4322965788)),
}
ROLES={'R1':'reference','C1':'candidate','R2':'reference','C2':'candidate'}
RUNTIME_SHA='899e6c472175aa96cfae64b03ebe091852e8ca365c67588d56a2199439a5980b'
PROPERTIES=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=9660',
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


def validate_scope(job,job_pin,scope,config):
    require(job.get('quality_leg')in ROLES and job.get('quality_pair_precommit',{}).get('sha256')==PAIR_SHA
        and job.get('minimum_completed_games')==50
        and job.get('expected_policy_clocks')==POLICIES[ROLES[job['quality_leg']]]['clocks']
        and all(type(v)is int for v in job['expected_policy_clocks'].values()),
        'Exact fixed-role pair, saved clocks and minimum50 required')
    require(job['schema']=='robotron-compiled-full-tail32-quality-original-v1'
        and job['runtime']['sha256']==RUNTIME_SHA
        and job['runtime']['path']==str(HERE/'run_compiled_full_tail32_quality_v1.py')
        and job['checkpoint']['sha256']==POLICIES[ROLES[job['quality_leg']]]['sha256'] and job['actor_slots']==list(SLOTS)
        and job['gpu_uuid']==GPU and job['backend']=='inductor'and job['device']=='cuda'
        and job['origin_port']==19998 and job['proxy_ports']=={str(s):20000+s-4096 for s in SLOTS}
        and job['startup_trace_frames']==1200 and job['admission_s']==5400
        and job['whole_cohort_timeout_s']==9000 and job['wall_limit_s']==9600,
        'Exact original full-tail-v2 engineering scope required')
    require('acceptance_scope'not in job and job['historical_startup_acceptance_scope']['sha256']==
        '692b5c0572d32ffae79b828eb64296c09eaa6b4e59de28ea9316b7f44a59fc77',
        'Historical prefix acceptance cannot be this case acceptance')
    require(scope['schema']=='robotron-original-all32-compiled-quality32-acceptance-v1'
        and scope['job']==job_pin and scope['original_attempt']==1 and scope['no_retry']is True
        and scope['fixed_admission_s']==5400 and scope['whole_cohort_timeout_s']==9000
        and scope['wall_limit_s']==9600 and scope['startup_trace_frames']==1200
        and scope['minimum_quality_completed_games']==50 and scope['quality_minimum_games_remains']==50
        and scope['quality_qualified']is scope['promotion']is False,
        'Exact separately precommitted full-tail acceptance required')
    expected=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',
        job['runtime']['path'],'--execute','--job',job_pin['path'],'--job-sha256',job_pin['sha256'],
        '--source-sha256',RUNTIME_SHA]
    require(config['argv']==expected and config['properties']==PROPERTIES
        and config['observation_s']==9720 and re.fullmatch(
            r'robotron-compiled-full-tail32-integration-[a-z0-9_-]+\.service',config['unit']),
        'Exact precommitted controller argv/resources required')


def validate_native_fields(fields,config,owner,duration):
    require(fields['Id']==owner['unit']==config['unit']
        and fields['InvocationID']==owner['invocation_id']and fields['ExecMainPID']==str(owner['pid'])
        and fields['ExecMainCode']=='1'and fields['ExecMainStatus']=='0'and fields['NRestarts']=='0'
        and duration(fields['CPUQuotaPerSecUSec'])==12 and fields['MemoryMax']==str(16<<30)
        and fields['MemorySwapMax']=='0'and duration(fields['RuntimeMaxUSec'])==9660
        and fields['TasksMax']=='512'and duration(fields['TimeoutStopUSec'])==30
        and fields['KillMode']=='mixed'and fields['SendSIGKILL']=='no'and fields['Restart']=='no',
        'Actual original native exit/identity/resources differ')
    command=' '.join(config['argv'])
    require(command+' ; ignore_errors=no ;'in fields['ExecStart'],
            'Actual systemd command differs from the original runtime/job/source pins')
    start=int(fields['ExecMainStartTimestampMonotonic'])/1e6
    end=int(fields['ExecMainExitTimestampMonotonic'])/1e6
    require(0<start<end<=time.monotonic()and end-start<=9660,'Original actual runtime interval differs')
    return start,end


def validate_runtime_result(result,job):
    require(result['quality_leg']==job['quality_leg']and result['quality_pair_precommit']==job['quality_pair_precommit']
        and result['expected_policy_clocks']==job['expected_policy_clocks']
        and type(result['minimum_completed_games'])is int and result['minimum_completed_games']==50,
        'Actual original quality leg/pair/saved clocks/minimum differ')
    require(result['schema']=='robotron-compiled-full-tail32-quality-original-result-v1'
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
    numeric=policy['numeric_policy']
    require(numeric['compiled']is True and numeric['backend']=='inductor'and numeric['device']=='cuda:0'
        and numeric['weights']==numeric['inputs']==numeric['support']=='float32'and numeric['autocast']is False
        and numeric['warm_shapes']==list(range(1,17))and numeric['max_batch_size']==16
        and numeric['serving_thread_checked']is True and numeric['graph_breaks']==0,
        'Common compiled backend/serving-thread context changed')
    cohort=result['before_intentional_stop']
    require(cohort==result['after_intentional_stop']==result['controller_exit']['cohort']
        and cohort['closed']is cohort['complete']is cohort['valid']is True
        and cohort['pending']==cohort['abandoned']==0 and cohort['count']==cohort['started']>=50
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


def audit_evaluator_logs(stdout,stderr,policy,optional_expert_proof_valid):
    allowed=[]
    for stream,text in [('stdout',stdout),('stderr',stderr)]:
        for number,line in enumerate(text.splitlines(),1):
            if not FLAG.search(line):continue
            kind=None
            if stream=='stdout'and line==EXPERT and optional_expert_proof_valid:
                require(policy['epsilon']==policy['expert_ratio']==0 and policy['training_enabled']is False,
                        'Unused optional expert warning occurred under non-greedy controls')
                kind='exact_unused_optional_expert_import_under_frozen_greedy_inference'
            elif stream=='stdout'and re.fullmatch(r'Client \d+ disconnected: (?:EOF|Broken payload)',line):
                kind='owned_origin_stop_after_all_admitted_tails_and_all32_peer_EOF'
            require(kind is not None,'Unclassified original evaluator log diagnostic: '+line)
            allowed.append(dict(stream=stream,line=number,text=line,classification=kind))
    return dict(allowed_diagnostics=allowed,unknown_errors=0)


def review(config_pin,h,reader):
    artifacts=[]
    def read(entry,as_json=True):
        value=reader.read_pin(entry,as_json=as_json);artifacts.append(entry);return value
    config=read(config_pin)
    require(config['schema']=='robotron-original-quality32-independent-leg-review-job-v1',
            'Explicit independent original review job required')
    output=Path(config['output'])
    native_pin=config['native_job'];job=read(native_pin);directory=Path(native_pin['path']).parent
    require(output==directory/'independent-quality-leg-review-original01'and directory.is_relative_to(R)
        and output.is_absolute()and not output.exists(),'Fresh exact original review output required')
    output.mkdir(mode=0o700)
    intent=h.put(output/'original-review-intent.json',dict(source=h.pin(__file__),review_job=config_pin,
        native_job=native_pin,original_attempt=1,no_retry=True,observed_unix_s=time.time()))
    report=dict(schema='robotron-original-quality32-independent-cohort-review-v1',valid=False,
        quality_qualified=False,promotion=False,full_game_score_verified=False,learning_speed_gain_verified=False,
        main_runtime_changed=False,review_job=config_pin,original_intent=intent,artifacts=artifacts)
    try:
        required={'runtime','control','wire','games','native_closure','main_supervision','main_window','terminal_rom'}
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
        health=[];main=read(job['main_binding']);main_policy=read(main['supervision_policy'])
        baseline=read(main['baseline_API']);previous=None
        require(len(main['held_hashes'])==196 and len(result['main_samples'])>=3,'Original main evidence incomplete')
        for sample in result['main_samples']:
            snapshot=read(sample['snapshot']);api=games.decode(read(sample['raw_API'],False))
            current=sup.validate_snapshot(main_policy,snapshot,api['client_count'])
            require(current['full_capacity']and not current['pending']and not current['completed_episodes'],
                    'Main original births or capacity changed during this original')
            window.healthy(api,baseline,main['experiment'],sample['unix_s'])
            require(api['learner_frame_count']==sample['learner_frames']and api['training_steps']==sample['training_steps']
                and started<=snapshot['collection_started_monotonic_s']<=snapshot['monotonic_s']<=ended,
                'Main raw API or actual observation interval differs')
            if previous:
                require(0<snapshot['monotonic_s']-previous['monotonic_s']<=30
                    and api['learner_frame_count']>=previous['learner_frames']
                    and api['training_steps']>=previous['training_steps'],'Main sample gap or clocks regressed')
            record=dict(monotonic_s=snapshot['monotonic_s'],collection_started_monotonic_s=snapshot['collection_started_monotonic_s'],
                learner_frames=sample['learner_frames'],training_steps=sample['training_steps'],
                snapshot=sample['snapshot'],raw_API=sample['raw_API'])
            health.append(record);previous=record
        require(health[0]['collection_started_monotonic_s']-started<=30
            and ended-health[-1]['monotonic_s']<=30
            and health[-1]['learner_frames']>health[0]['learner_frames']
            and health[-1]['training_steps']>health[0]['training_steps'],
            'Main coverage missed initialization/teardown or work did not advance')
        for path,sha in main['held_hashes'].items():require(h.pin(path)['sha256']==sha,'Original held main source changed')
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
        logs=audit_evaluator_logs(evaluator_text['stdout.txt'],evaluator_text['stderr.txt'],policy,True)
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
        report.update(valid=True,status='PASS_ORIGINAL_ALL32_MIN50_QUALITY_COHORT_AND_RUNTIME',
            original_native_job=native_pin,original_acceptance=config['acceptance'],original_controller_result=controller_pin,
            original_owner=owner_pin,original_closure=controller['closure'],actual_runtime_exit=0,actual_controller_exit=0,
            original_result=result_pin,policy=policy,compile_report=loaded['compile_report'],
            original_games=original_games,raw_prefixes=list(prefixes.values()),applied_tail_shutdown=tails,
            quality_leg=job['quality_leg'],quality_pair_precommit=job['quality_pair_precommit'],
            minimum_quality_complete_games=50,fixed_admission_s=5400,
            actor_logs=actor_logs,evaluator_logs=logs,main_observations=health,
            full_game_score_verified=True,all_admitted_games_retained=True,all32_actual_MAME_exits=0,
            all6_original_descriptors_verified=True,actual_descriptor_exits=[r['exit']for r in closure['full_original_archives']],
            exact_owned_births_unit_timer_cgroup_absent=True,private_GPU_ports_and_coordinator_released=True,
            original_outputs_sealed_after_writer_exit=True,postprefix_raw_reconstructable=False,
            qualification_limit='One independently valid min50/all32 complete-game quality leg. A NEW fixed fresh R1+R2 reference and separate C1/C2 mean>=1.05/median-preserving gates are still required before policy qualification. No pooled candidate, retry, promotion, throughput or learning-speed claim.')
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
