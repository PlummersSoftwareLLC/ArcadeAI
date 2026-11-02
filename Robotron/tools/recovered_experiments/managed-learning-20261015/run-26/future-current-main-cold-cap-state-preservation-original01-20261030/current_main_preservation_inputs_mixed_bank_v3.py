"""Root-only current continuous stop metadata; no work at import.

The seal proves input closure plus an exhausted existing budget. It never
claims managed-measurement/prefetch pause or successful saved payloads.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import stat
import subprocess
import time
import urllib.request

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
FIRST_OWNER=dict(pid=654315,starttime_ticks=16564768,unit='robotron-trainer.service',
    invocation_id='c9a7ad073c8043af8b9499acb4ae4372',
    cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-trainer.service')
FIRST_FLEET=dict(pid=909646,starttime_ticks=17859362,unit='robotron-mame.service',
    invocation_id='5648e44c5c0d415ebfc7d109256f4676',
    cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-mame.service')
CURRENT_SHAS={'agent.py':'d2a95ff0828df2a00ac86049965b6df304d26b50263b76d027d27a586ff77152',
 'main.py':'78178c39b281c0baf52222387f06db2d899c1bf2adfbe8c9fe2fd22729ff59c5',
 'replay_buffer.py':'34b05e3c4403bc2dca53222222416db2afb733c480ee6238a0cc4e723885d0e8',
 'socket_server.py':'a076501b0601a637b91269a41572be60496754ad1da4b04385d77c51b9f34423',
 'training.py':'90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4'}
COLD_ORIGIN={'job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-cold-cap12-original01/startup-metadata/startup-job.json', 'sha256': '0f370c2d47047a9aac6676495e140eb1654a12c630a7a4d02d9add92e7dc9b27', 'bytes': 9799, 'identity': {'device': 2304, 'inode': 81429522, 'bytes': 9799, 'mtime_ns': 1793389338247855650, 'ctime_ns': 1793389338247855650, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'held': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-cold-cap12-original01/startup-held/verified-held-before-first-update.json', 'sha256': '47f15ce7778d053561f3160b5b81298fb26a6a115a692ea4838bc8cef79fe652', 'bytes': 6700, 'identity': {'device': 2304, 'inode': 81429521, 'bytes': 6700, 'mtime_ns': 1793389409373076495, 'ctime_ns': 1793389409373076495, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'consumed': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/B-cold-cap12-original01/startup-held/release-consumed.json', 'sha256': '3e2938eeb6b0879d462d1ac7512a35ba405158d97a9c91adb1750b28fe1ade01', 'bytes': 2763, 'identity': {'device': 2304, 'inode': 81429535, 'bytes': 2763, 'mtime_ns': 1793389571829037404, 'ctime_ns': 1793389571829037404, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'manifest': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/A1-forward-preservation-S1-original01/actual-stopped600-S1-preparation-original01/runtime/restoration-manifest.json', 'sha256': 'ab3a23495a31adfd57c33dfbf6c066b0de08b1fd0a28ba970125971c01550c66', 'bytes': 422227, 'identity': {'device': 2304, 'inode': 81429272, 'bytes': 422227, 'mtime_ns': 1793388404615755357, 'ctime_ns': 1793388404615755357, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'backup': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/cold-update-budget8-12-8-throughput-trial-original01-20261030/full-stopped-backup-S1-original01/backup-manifest.json', 'sha256': '73e620edd8e43e7c3a830914fec864f12ce8c603ba45fa3088a3a50973c4d29b', 'bytes': 134121, 'identity': {'device': 2304, 'inode': 81429470, 'bytes': 134121, 'mtime_ns': 1793388989664017579, 'ctime_ns': 1793388989664017579, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
BANK_READER=ROOT/'tools/score_carry_proposal/bank_generation_witness.py'
BANK_READER_SHA='dcbebda66feac28a312819a83c8915a8f6cb812ace78b10f2368c7ab4ab4804e'
SEMANTICS=ROOT/'logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027/preview-flags-preserveRAM-trainer-restart-original01/stop-sources/current192_poststop_only_v1.py'
SEMANTICS_SHA='7c8e995d67bfbd826e87d327a5dc4dfa796bb12e4c368a3eafd37e23c8466278'


def require(value,reason):
    if not value:raise ValueError(reason)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def pin(path):
    p=Path(path);s=p.lstat()
    require(p.is_absolute()and p.resolve(strict=True)==p and not p.is_symlink()
        and stat.S_ISREG(s.st_mode)and s.st_uid==os.getuid()and s.st_nlink==1
        and 0<s.st_size<=4<<20,'Bounded canonical owner metadata/source required')
    raw=p.read_bytes();require(identity(s)==identity(p.stat()),'Metadata changed')
    return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(s))


def read(value):
    require(pin(value['path'])==value and value['identity']['mode']=='0o444','Exact immutable full8 metadata required')
    return json.loads(Path(value['path']).read_bytes())


def publish(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();p=Path(path)
    require(p.parent.is_dir()and p.resolve(strict=False)==p and not p.exists(),'Exclusive physical metadata output required')
    with p.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return pin(p)


def load(path,sha,name):
    value=pin(path);require(value['sha256']==sha,'Selected helper source differs')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def startup_anchor(selection):
    require(selection['schema']=='robotron-root-current-continuous-preservation-selection-v1','Exact Root current/cold selection schema required')
    owner,fleet=selection['owner'],selection['fleet']
    require(type(selection['expected_current_cap'])is int and selection['expected_current_cap']in(8,12),'Exact current cap8/12 required')
    require(set(owner)==set(FIRST_OWNER)and set(fleet)==set(FIRST_FLEET)
        and owner['unit']=='robotron-trainer.service'and fleet['unit']=='robotron-mame.service', 'Exact owner roles required')
    for value,original in((owner,FIRST_OWNER),(fleet,FIRST_FLEET)):
        require(type(value['pid'])is int and value['pid']>1 and type(value['starttime_ticks'])is int
            and value['starttime_ticks']>0 and value['cgroup']==original['cgroup']
            and re.fullmatch('[0-9a-f]{32}',value['invocation_id'])is not None,'Typed permanent-unit incarnation required')
    if selection['first_current_main_stop']is True:
        require(owner==FIRST_OWNER and fleet==FIRST_FLEET and selection['expected_current_cap']==8,'Exact first current Main/fleet/cap8 required')
    else:
        require(selection['first_current_main_stop']is False and owner!=FIRST_OWNER,'Explicit fresh cold incarnation required')
    job=read(selection['startup_job']);held=read(selection['startup_held']);consumed=read(selection['startup_release_consumed'])
    expected={**owner,'birth':owner['starttime_ticks'],'uid':os.getuid()};del expected['starttime_ticks']
    require(job['schema']=='robotron-continuous-main-before-update-startup-hold-job-v1'
        and held['schema']=='robotron-continuous-main-held-exact-restoration-report-v1'
        and held['status']=='VERIFIED_HELD_BEFORE_FIRST_UPDATE'and held['owner']==expected
        and held['original_job']==selection['startup_job']and held['checkpoint']==job['checkpoint']
        and held['restoration_manifest']==job['restoration_manifest']
        and held['all_online_target_Adam_scaler_payloads_equal']is True
        and held['optimizer_attempts_before_release']==held['new_replay_inserts_before_release']==0,
        'Actual same-owner exact held restoration required')
    require(consumed['schema']=='robotron-continuous-startup-release-consumed-v1'
        and consumed['owner']==expected and consumed['original_job']==selection['startup_job']
        and consumed['held_report']==selection['startup_held']and consumed['no_optimizer_or_replay_work_before_release']is True,
        'Actual original one-use release consumption required')
    if not selection['first_current_main_stop']:
        require(held['startup_budget']['expected_startup_cap']==selection['expected_current_cap']
            and held['startup_budget']['runtime_cap']==selection['expected_current_cap'],'Actual future cap witness required')
    manifest=read(job['restoration_manifest']);record=read(job['resume_record'])
    cpu=read(job['stopped_CPU_report']);closed=read(job['stopped_state_authority']);release=read(consumed['Root_release'])
    require(cpu['status']=='PASS'and cpu['restoration_manifest']==job['restoration_manifest']
        and closed['original_CPU_exit']==0 and closed['all_original_CPU_resources_closed']is True
        and closed['restoration_manifest']==job['restoration_manifest']
        and release['original_job']==selection['startup_job']and release['held_report']==selection['startup_held']
        and release['owner']==expected and release['allow_training']is True, 'Actual closed restore/release provenance required')
    require(manifest['status']=='VERIFIED_STOPPED_STATE'and manifest['checkpoint']==job['checkpoint']
        and held['saved_scalars']==manifest['saved_scalars']and record['checkpoint']=={k:job['checkpoint'][k]for k in('path','sha256','bytes')},
        'Exact restored boot manifest/resume record required')
    phase=copy.deepcopy(manifest['priority_metric_phase']);phase['last_resume_record_sha256']=job['resume_record']['sha256']
    return dict(schema='robotron-actual-continuous-boot-state-descriptor-v1',owner=owner,fleet=fleet,
        startup_job=selection['startup_job'],startup_held=selection['startup_held'],startup_release_consumed=selection['startup_release_consumed'],
        original_stopped_CPU_report=job['stopped_CPU_report'],original_restoration_manifest=job['restoration_manifest'],
        checkpoint=record['checkpoint'],saved_clocks={k:manifest['saved_scalars'][k]for k in('training_steps','optimized_samples','learner_frame_count','frame_count')},
        clocks={k:manifest['saved_scalars'][k]for k in('training_steps','optimized_samples','learner_frame_count','frame_count')},
        priority_phase=phase,priority_phase_valid=True,CUDA_initialized=False,phase_record=job['resume_record'],
        loaded_baseline={k:manifest['saved_scalars'][k]for k in('frame_count','measurement_frame_count','optimized_samples')},
        exposure_at_load=held['exposure'],
        ring_at_load=manifest['ring_and_banks']['ring']['meta'],
        fresh_CPU_test_or_new_runtime_qualification_claimed=False)




def cold_bank_origin(selection,banks):
    """Replay the exact B boot ancestry against already captured disk metadata.

    No old CURRENT pointer is reopened after final save; read_bank_generation
    authenticates those live objects at sealing, then this pure projection is
    replayed against the immutable S1 manifest after stop.
    """
    require(selection['startup_job']==COLD_ORIGIN['job']and selection['startup_held']==COLD_ORIGIN['held']
        and selection['startup_release_consumed']==COLD_ORIGIN['consumed'],'Exact selected B restoration required')
    job,held,consumed,manifest,backup=(read(COLD_ORIGIN[k])for k in('job','held','consumed','manifest','backup'))
    require(job['restoration_manifest']==COLD_ORIGIN['manifest']and held['restoration_manifest']==COLD_ORIGIN['manifest']
        and held['original_job']==COLD_ORIGIN['job']and consumed['held_report']==COLD_ORIGIN['held']
        and consumed['original_job']==COLD_ORIGIN['job']and consumed['owner']==held['owner']
        and held['owner']['pid']==selection['owner']['pid']==167514
        and held['owner']['birth']==selection['owner']['starttime_ticks']==27299341
        and held['owner']['invocation_id']==selection['owner']['invocation_id']=='99edc3b8c8d24bb2a7570ef18b0e7bdc'
        and job['expected_startup_cap']==selection['expected_current_cap']==12,'Same B owner/cap/manifest required')
    closed=read(job['stopped_state_authority'])
    require(closed['full_independent_backup']==COLD_ORIGIN['backup']and closed['backup_original_exit']==0
        and closed['all_original_backup_resources_closed']is True and closed['restoration_manifest']==COLD_ORIGIN['manifest']
        and backup['status']=='COMPLETE_STREAM_HASHED_AND_FSYNCED'and backup['restoration_manifest']==COLD_ORIGIN['manifest']
        and backup['strict_CPU_report']==job['stopped_CPU_report'],'Exact closed independent S1 backup required')
    require(held['all_online_target_Adam_scaler_payloads_equal']is True
        and held['new_replay_inserts_before_release']==held['optimizer_attempts_before_release']==0
        and held['exposure']['replay']['accepted_total']==0
        and consumed['no_optimizer_or_replay_work_before_release']is True,'Exact zero-work held bank origin required')
    def flat(entry):
        i=entry['identity'];return dict(path=entry['path'],**{k:i[k]for k in('device','inode','mtime_ns','ctime_ns','uid','nlink')},bytes=i['size'])
    expected={};scalars={}
    for name,value in manifest['ring_and_banks']['banks'].items():
        require(held['replay']['banks'][name]['all_valid_field_payloads_and_episode_metadata_equal']is True,'Held bank payload equality required')
        meta=value['metadata'];scalars[name]=meta['scalars']
        pointer=flat(value['selector']['descriptor']);pointer['sha256']=value['selector']['descriptor']['sha256']
        metadata=flat(meta['descriptor']);metadata['sha256']=meta['descriptor']['sha256']
        arrays={k:dict(flat(row),header=dict(descr=row['dtype'],fortran_order=False,shape=row['shape']))for k,row in value['arrays'].items()}
        expected[name]=dict(bank=name,selector=value['selector']['value'],pointer=pointer,metadata=metadata,
            episodes=value['counts']['episodes'],transitions=value['counts']['transitions'],stride=meta['scalars']['stride'],
            state_size=meta['scalars']['state_size'],captured_adds=meta['scalars']['captured_adds'],arrays=arrays,state_payload_read_or_hashed=False)
    require(set(banks)==set(expected)=={'hof','ephof'},'Both per-bank boot/current origins required')
    loaded_scalars=copy.deepcopy(scalars);origins={}
    reader=None
    for name,bank in banks.items():
        prior=expected[name]
        if json.dumps(bank,sort_keys=True,allow_nan=False)==json.dumps(prior,sort_keys=True,allow_nan=False):
            origins[name]=dict(kind='INHERITED_BOOT_DISK',saved_local_revision=1,age_base_adds=0)
            continue
        require(bank['bank']==name and bank['selector']['previous']==prior['selector']['generation']
            and bank['selector']['generation']!=prior['selector']['generation']
            and type(bank['selector']['mutation_generation'])is int and bank['selector']['mutation_generation']>1
            and bank['pointer']['mtime_ns']>=COLD_ORIGIN['consumed']['identity']['mtime_ns']
            and bank['metadata']['mtime_ns']>=COLD_ORIGIN['consumed']['identity']['mtime_ns']
            and bank['pointer']['mtime_ns']>=bank['metadata']['mtime_ns']
            and bank['episodes']==prior['episodes']and bank['stride']==prior['stride']
            and bank['state_size']==prior['state_size']and set(bank['arrays'])==set(prior['arrays'])
            and all(json.dumps(bank['arrays'][key]['header'],sort_keys=True,allow_nan=False)==json.dumps(prior['arrays'][key]['header'],sort_keys=True,allow_nan=False)
                and bank['arrays'][key]['bytes']==prior['arrays'][key]['bytes']for key in prior['arrays']),
            'Current local bank must be a single source-geometry successor of the exact loaded disk generation')
        if reader is None:reader=load(BANK_READER,BANK_READER_SHA,'_current_mixed_bank_metadata_reader')
        raw,descriptor=reader.small_file(bank['metadata']['path'],1<<20)
        require(descriptor==bank['metadata'],'Exact selected local metadata NPZ changed')
        with reader.zipfile.ZipFile(reader.io.BytesIO(raw))as archive:
            require(len(archive.namelist())==len(set(archive.namelist()))
                and set(archive.namelist())=={key+'.npy'for key in reader.META_FIELDS}
                and all(v.file_size<=128<<10 for v in archive.infolist())
                and sum(v.file_size for v in archive.infolist())<=1<<20,'Exact bounded unique local bank metadata required')
            current={}
            for key in('stale_age','stale_age_normal','stride','state_size','captured_adds','mutation_generation'):
                header,values=reader.meta_array(archive.read(key+'.npy'))
                require(header==dict(descr='<i8',fortran_order=False,shape=())and len(values)==1
                    and type(values[0])is int and values[0]>=0,'Typed source-local bank scalar required')
                current[key]=values[0]
        require(current['mutation_generation']==bank['selector']['mutation_generation']
            and current['captured_adds']==bank['captured_adds']and current['stride']==bank['stride']
            and current['state_size']==bank['state_size']and current['stale_age']<=current['captured_adds']
            and current['stale_age_normal']>=current['stale_age']
            and(current['stale_age_normal']<=current['captured_adds']or current['stale_age_normal']==loaded_scalars[name]['stale_age_normal']+current['captured_adds']),
            'Published local bank scalar/age lineage is not source-reachable')
        scalars[name]=current
        origins[name]=dict(kind='CURRENT_BOOT_PERSISTED_SUCCESSOR',saved_local_revision=current['mutation_generation'],age_base_adds=current['captured_adds'])
    return dict(schema='robotron-source-bound-mixed-bank-counter-origin-v2',evidence=COLD_ORIGIN,
        owner=selection['owner'],banks=copy.deepcopy(banks),scalars=scalars,bank_origins=origins,
        loaded_banks=expected,loaded_scalars=loaded_scalars,held_replay=held['exposure']['replay'],
        held_optimizer=held['exposure']['optimizer'],loaded_local_revision=1,loaded_adds_total=0,
        loaded_bank_payload_and_episode_metadata_equal=True,counter_values_normalized_or_reset=False)



def verify_input_closure(selection):
    value=read(selection['input_closure'])
    require(value['schema']=='robotron-Root-continuous-input-closure-v1'and value['owner']==selection['owner']
        and value['fleet']==selection['fleet']and value['all_original_population_births_absent']is True
        and value['all_GAME_handlers_and_FIFO_work_finished']is True
        and value['no_deferred_callbacks_or_Timer_threads']is True
        and value['GAME_listener_sealed_until_original_trainer_exit']is True
        and type(value['source_pins'])is list and value['source_pins'], 'Actual Root-owned input/FIFO seal required')
    require(value['source']==selection['input_closure_producer']and pin(value['source']['path'])==value['source'],
        'Exact actual closure producer source required')
    for evidence in value['evidence']:read(evidence)
    observed={Path(v['path']).name:v['sha256']for v in value['source_pins']}
    require(all(observed.get(k)==v for k,v in CURRENT_SHAS.items()),'Exact current writer/budget source family required')
    for v in value['source_pins']:
        require(pin(v['path'])==v,'Current selected source changed')
    return value


def seal(selection_pin,output):
    selection=read(selection_pin);anchor=startup_anchor(selection);closure=verify_input_closure(selection)
    owner=selection['owner'];props=dict(x.split('=',1)for x in subprocess.check_output(['systemctl','--user','show',owner['unit']],text=True,timeout=10).splitlines()if'='in x)
    require(props.get('MainPID')==str(owner['pid'])and props.get('InvocationID')==owner['invocation_id']
        and props.get('ControlGroup')==owner['cgroup']and props.get('ActiveState')=='active','Same original current trainer required')
    proc=Path('/proc',str(owner['pid']))
    require(int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])==owner['starttime_ticks']
        and proc.stat().st_uid==os.getuid(),'Same actual trainer birth/UID required')
    entries=[x.split('=',1)for x in(proc/'environ').read_bytes().decode().split('\0')if'='in x]
    require([v for k,v in entries if k=='DQN_MAX_SAMPLES_PER_FRAME']==[str(selection['expected_current_cap'])]
        and dict(entries).get('ROBOTRON_CONTINUOUS_TRAINING_MODE')=='1','Actual current continuous startup cap required')
    reader=load(BANK_READER,BANK_READER_SHA,'_current_stop_bank_reader');semantics=load(SEMANTICS,SEMANTICS_SHA,'_current_stop_bank_semantics')
    helper=Path(__file__).with_name('continuous_budget_bank_intent_mixed_bank_v3.py');intent=load(helper,selection['budget_intent_source']['sha256'],'_current_continuous_budget_intent')
    require(pin(helper)==selection['budget_intent_source'],'Exact budget seam source required')
    def api():
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as response:return json.load(response)
    before=api();banks={k:reader.read_bank_generation(k,ROOT/'models_dqn'/('robotron_dqn_latest_replay_'+k))for k in('hof','ephof')}
    origin=cold_bank_origin(selection,banks)
    time.sleep(1.1);after=api();pair=intent.validate(before,after,banks,expected_pid=owner['pid'],now=time.time(),
        expected_cap=selection['expected_current_cap'],loaded_baseline=anchor['loaded_baseline'],origin=origin)
    verify_input_closure(selection)
    root=Path(output);root.mkdir(mode=0o700)
    bp=publish(root/'before-zero-input-budget.json',before);ap=publish(root/'after-zero-input-budget.json',after)
    boot=publish(root/'actual-restored-boot-descriptor.json',anchor)
    value=dict(schema='robotron-continuous-input-closed-budget-bank-seal-v1',original_selection=selection_pin,
        owner=owner,fleet=selection['fleet'],source=pin(Path(__file__).resolve()),budget_intent_source=selection['budget_intent_source'],
        input_closure=selection['input_closure'],before_API=bp,final_API=ap,boot_state_descriptor=boot,
        bank_pair=pair,cold_bank_origin=origin,bank_metadata_semantics=semantics.bank_metadata_semantics(banks,reader),
        replay_exposure=after['host_pipeline']['learning_exposure']['replay'],clock_floor={k:after[k]for k in('training_steps','optimized_samples','learner_frame_count','frame_count')},
        input_sources_sealed=True,all_handlers_finished=True,budget_exhausted=True,sealed_unix_s=time.time(),
        prefetch_paused_claimed=False,prefetch_read_only_staging_may_remain=True,saved_payload_integrity_qualified=False)
    return publish(root/'bank-seal.json',value)


if __name__=='__main__':
    print('SOURCE_ONLY_INERT_USE_SELECTED_STOP_PRODUCER')
