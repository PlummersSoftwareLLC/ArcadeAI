"""Root-only DATA construction; never imports evaluator/Torch or launches a process."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat


def require(ok,message):
    if not ok:raise ValueError(message)


def pin(path):
    p=Path(path);s=p.lstat()
    require(p.is_absolute()and p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_uid==os.getuid()and s.st_nlink==1
        and 0<s.st_size<=1<<20,'Bounded owned canonical metadata/source required')
    raw=p.read_bytes();after=p.stat();require(all(getattr(s,k)==getattr(after,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_nlink')),'Metadata changed while pinning')
    return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=dict(device=s.st_dev,inode=s.st_ino,
        bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink))


def read(value):
    require(pin(value['path'])==value and value['identity']['mode']=='0o444','Exact immutable metadata/source pin required')
    return json.loads(Path(value['path']).read_bytes())


def put(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return pin(path)


def prepare(args):
    own=pin(Path(__file__).resolve());require(own['sha256']==args.source_sha256 and own['identity']['mode']=='0o444','Exact selected frozen DATA source required')
    selected_pin=pin(args.selection);require(selected_pin['sha256']==args.selection_sha256,'Selected screen SHA differs')
    selected=read(selected_pin);sources_pin=pin(args.sources)
    require(sources_pin['sha256']==args.sources_sha256,'Exact frozen source table required');sources=read(sources_pin)
    require(selected['schema']=='robotron-prospective-S2-b231-two-arm-cutoff-screen-v1'
        and selected['status']=='ROOT_SELECTED_NOT_LAUNCHED'and selected['ordered_legs']==['R1','C1']
        and selected['screen_only']is True and selected['promotion']is False,'New explicit prospective screen selection required')
    require(read(selected['A2_observation_report'])['status']=='PASS_ENGINEERING_OBSERVATION','A2 measurement must finish before this quality screen')
    copy_record=read(selected['S2_copy_descriptor']);authority=read(selected['candidate']['authority'])
    manifest=read(authority['restoration_manifest']);cpu=read(authority['CPU_report'])
    require(copy_record['all_original_writers_stopped_before_copy']is True
        and selected['candidate']['checkpoint']==copy_record['verification_copy']
        and copy_record['stopped_authority']==authority['actual_stopped_authority']
        and copy_record['source_checkpoint']['sha256']==manifest['checkpoint']['sha256']==selected['candidate']['checkpoint']['sha256']
        and authority['original_CPU_exit']==authority['backup_original_exit']==0
        and authority['all_original_CPU_resources_closed']is authority['all_original_backup_resources_closed']is True
        and cpu['status']=='PASS'and cpu['restoration_manifest']==authority['restoration_manifest']
        and all(selected['candidate']['expected_policy_clocks'][k]==manifest['saved_scalars'][k]for k in selected['candidate']['expected_policy_clocks']),
        'Exact stopped S2 independent checkpoint copy and actual CPU/backup evidence required')
    base=read(sources['base_job']);require(base['checkpoint']==selected['reference']['checkpoint']
        and base['expected_policy_clocks']==selected['reference']['expected_policy_clocks']
        and selected['reference']['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
        and selected['candidate']['checkpoint']['sha256']!=selected['reference']['checkpoint']['sha256'],
        'Protected b231 reference and distinct fixed S2 candidate required')
    read(selected['reference']['authority']);main=selected['current_main'];startup=read(main['startup_authority']);held=read(main['startup_held']);trainer=startup['trainer']
    require(startup['all_model_optimizer_replay_banks_clocks_preserved']is True
        and main['owner']==dict(pid=trainer['pid'],starttime_ticks=trainer['birth'],invocation_id=trainer['invocation_id'],cgroup=trainer['cgroup'],unit=trainer['unit'])
        and held['owner']['pid']==trainer['pid']and held['owner']['birth']==trainer['birth']and held['owner']['invocation_id']==trainer['invocation_id']
        and held['restoration_manifest']==authority['restoration_manifest']
        and all(main['exposure'][kind]=={k:held['exposure'][kind][k]for k in('process_id','instance_monotonic_ns','epoch','epoch_reason')}for kind in('optimizer','replay')),
        'Exact current A2 restored owner/held exposure lineage required')
    for entry in sources['selected'].values():
        require(pin(entry['path'])==entry and entry['identity']['mode']=='0o444','Frozen screen source changed')
    output=Path(args.output);require(output.is_absolute()and output.resolve()==output and not output.exists()
        and output.parent.is_dir(),'Fresh DATA output required');output.mkdir(mode=0o700)
    fields={'actor_slots','actor_source_sha256','backend','boot_seed','cleanup_limit_s','controller_observation_s','cpu_threads',
        'device','gpu_uuid','horizon_ns','inference_max_batch_size','inflight_drain_bound_ns','lease','loaded_rom_sha256',
        'lua','mame','observer_resources','origin_port','proxy_ports','resources','rompath','seed_runtime','source_package',
        'startup_admission_duration_ns','startup_limit_s','startup_trace_frames','training_experiment','wall_limit_s'}
    jobs={};global_tokens=set()
    for leg,role in(('R1','reference'),('C1','candidate')):
        root=output/leg;root.mkdir(mode=0o700);job={k:copy.deepcopy(base[k])for k in fields};policy=selected[role]
        components=copy.deepcopy(base['components'])
        for key in('clock_proxy','recorder'):components[key]=sources['selected'][key]
        sessions={str(slot):secrets.token_hex(16)for slot in job['actor_slots']}
        connections={str(slot):secrets.token_hex(16)for slot in job['actor_slots']}
        tokens=set(sessions.values())|set(connections.values());require(len(tokens)==64 and not tokens&global_tokens,'New unique original transport identities required');global_tokens|=tokens
        job.update(schema='robotron-deadline32-one-original-leg-v1',attempt=1,no_retry=True,leg=leg,
            output=str(root/'runtime-original01'),runtime=sources['selected']['runtime'],components=components,
            checkpoint=policy['checkpoint'],expected_policy_clocks=policy['expected_policy_clocks'],policy_authority=policy['authority'],
            sessions=sessions,connections=connections,label='S2-b231-screen-'+leg,measurement_label='S2-b231-screen-'+leg,
            private_client_idle_timeout_s=4260,completion_codec=sources['selected']['completion_codec'],screen_only=True,screen_selection=selected_pin,screen_support=sources['selected']['support'],current_main=selected['current_main'])
        holds=[own,sources_pin,selected_pin,policy['checkpoint'],policy['authority'],selected['S2_copy_descriptor'],
            selected['A2_observation_report'],job['runtime'],job['screen_support'],job['completion_codec'],job['source_package'],job['seed_runtime'],job['lua'],
            job['boot_seed']['module'],*job['boot_seed']['inputs'],*components.values(),selected['current_main']['startup_authority'],selected['current_main']['startup_held']]
        job['inputs']=list({v['path']:v for v in holds}.values());jp=put(root/'job.json',job)
        jobs[leg]=dict(job=jp,argv=[selected['private_python'],'-Xgil=0','-I','-B',job['runtime']['path'],'--execute',
            '--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',job['runtime']['sha256']])
    return put(output/'prepared-two-arm-screen-DATA-NOT-LAUNCHED.json',dict(schema='robotron-S2-two-arm-screen-DATA-v1',
        selection=selected_pin,sources=sources_pin,ordered_legs=['R1','C1'],jobs=jobs,screen_only=True,promotion=False,
        launch_performed=False,C1_requires_actual_R1_exit0_and_32_valid_scores_and_all_owned_writers_closed=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--selection',type=Path)
    p.add_argument('--selection-sha256');p.add_argument('--sources',type=Path);p.add_argument('--sources-sha256');p.add_argument('--output',type=Path);p.add_argument('--source-sha256');a=p.parse_args()
    if not a.prepare:print('PLAN_ONLY: no input reads, outputs, model, GPU, API or process actions')
    else:print(json.dumps(prepare(a),indent=2))
