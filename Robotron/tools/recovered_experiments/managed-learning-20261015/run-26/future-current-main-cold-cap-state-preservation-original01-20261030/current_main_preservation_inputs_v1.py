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
    helper=Path(__file__).with_name('continuous_budget_bank_intent_v1.py');intent=load(helper,selection['budget_intent_source']['sha256'],'_current_continuous_budget_intent')
    require(pin(helper)==selection['budget_intent_source'],'Exact budget seam source required')
    def api():
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as response:return json.load(response)
    before=api();banks={k:reader.read_bank_generation(k,ROOT/'models_dqn'/('robotron_dqn_latest_replay_'+k))for k in('hof','ephof')}
    time.sleep(1.1);after=api();pair=intent.validate(before,after,banks,expected_pid=owner['pid'],now=time.time(),
        expected_cap=selection['expected_current_cap'],loaded_baseline=anchor['loaded_baseline'])
    verify_input_closure(selection)
    root=Path(output);root.mkdir(mode=0o700)
    bp=publish(root/'before-zero-input-budget.json',before);ap=publish(root/'after-zero-input-budget.json',after)
    boot=publish(root/'actual-restored-boot-descriptor.json',anchor)
    value=dict(schema='robotron-continuous-input-closed-budget-bank-seal-v1',original_selection=selection_pin,
        owner=owner,fleet=selection['fleet'],source=pin(Path(__file__).resolve()),budget_intent_source=selection['budget_intent_source'],
        input_closure=selection['input_closure'],before_API=bp,final_API=ap,boot_state_descriptor=boot,
        bank_pair=pair,bank_metadata_semantics=semantics.bank_metadata_semantics(banks,reader),
        replay_exposure=after['host_pipeline']['learning_exposure']['replay'],clock_floor={k:after[k]for k in('training_steps','optimized_samples','learner_frame_count','frame_count')},
        input_sources_sealed=True,all_handlers_finished=True,budget_exhausted=True,sealed_unix_s=time.time(),
        prefetch_paused_claimed=False,prefetch_read_only_staging_may_remain=True,saved_payload_integrity_qualified=False)
    return publish(root/'bank-seal.json',value)


if __name__=='__main__':
    print('SOURCE_ONLY_INERT_USE_SELECTED_STOP_PRODUCER')
