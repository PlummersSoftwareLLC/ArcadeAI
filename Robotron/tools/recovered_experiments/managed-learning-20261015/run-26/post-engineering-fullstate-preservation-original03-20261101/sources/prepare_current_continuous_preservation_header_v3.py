"""Root metadata-only assembly of current continuous stop/strict600 jobs.

Default inert. Owner/closure captures are supplied by Root. No live probe,
model/array body read, save, source install or service action occurs here.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import time

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE=ROOT/'logs/managed-learning-20261015/run-26'
HERE=Path(__file__).resolve().parent
PARENT=BASE/'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01'
SOURCES={'CPU_controller': {'bytes': 17267,
                    'identity': {'bytes': 17267,
                                 'ctime_ns': 1793274951895866951,
                                 'device': 2304,
                                 'inode': 85225677,
                                 'mode': '0o444',
                                 'mtime_ns': 1793274951895866951,
                                 'nlink': 1,
                                 'uid': 1001},
                    'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/state-sources/control_stopped_fullstate600_CPU_v1.py',
                    'sha256': '19338ee6d5ae925f5dadd390a4d3f98f23217b9faeb5ffc2bd25b8631d6d1dd7'},
 'backup': {'bytes': 22393,
            'identity': {'bytes': 22393,
                         'ctime_ns': 1793533292368005071,
                         'device': 2304,
                         'inode': 85479126,
                         'mode': '0o444',
                         'mtime_ns': 1793533292368005071,
                         'nlink': 1,
                         'uid': 1001},
            'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-engineering-fullstate-preservation-original03-20261101/sources/copy_verified_current_continuous_state_v6.py',
            'sha256': 'a38d9dff1dd8f2b6e07198b1e685b00c55148bde785783a7c14d9ff750df2bcc'},
 'backup_controller': {'bytes': 17269,
                       'identity': {'bytes': 17269,
                                    'ctime_ns': 1793276698175882231,
                                    'device': 2304,
                                    'inode': 85225863,
                                    'mode': '0o444',
                                    'mtime_ns': 1793276698175882231,
                                    'nlink': 1,
                                    'uid': 1001},
                       'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/backup-sources/control_stopped_training_backup3600_v1.py',
                       'sha256': '7e59804f7b3eb86ad5f0fca0b62f9f940bbca429b837588f926f53d2c27068e6'},
 'backup_template': {'bytes': 1273,
                     'identity': {'bytes': 1273,
                                  'ctime_ns': 1793278182335692807,
                                  'device': 2304,
                                  'inode': 85226048,
                                  'mode': '0o444',
                                  'mtime_ns': 1793278182335692807,
                                  'nlink': 1,
                                  'uid': 1001},
                     'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/backup-sources/Root-stopped-backup-v4-job-template-UNFILLED-NOT-LAUNCHABLE.json',
                     'sha256': 'dbf8f2d48bbb00856a1df3fad8f7c492e1e526f3495561d692c4bc05517b905c'},
 'bank_reader': {'bytes': 13050,
                 'identity': {'bytes': 13050,
                              'ctime_ns': 1792431306252706502,
                              'device': 2304,
                              'inode': 81930385,
                              'mode': '0o664',
                              'mtime_ns': 1792431306252706502,
                              'nlink': 1,
                              'uid': 1001},
                 'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/score_carry_proposal/bank_generation_witness.py',
                 'sha256': 'dcbebda66feac28a312819a83c8915a8f6cb812ace78b10f2368c7ab4ab4804e'},
 'budget_intent': {'bytes': 6200,
                   'identity': {'bytes': 6200,
                                'ctime_ns': 1793533292355937027,
                                'device': 2304,
                                'inode': 85479124,
                                'mode': '0o444',
                                'mtime_ns': 1793533292355937027,
                                'nlink': 1,
                                'uid': 1001},
                   'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-engineering-fullstate-preservation-original03-20261101/sources/continuous_budget_bank_intent_v1.py',
                   'sha256': '2095dbc7dfe7ea96e4be231fe65bc0f6a2bdd481820ac67d605f231f679e18d7'},
 'cleanup_book': {'bytes': 11929,
                  'identity': {'bytes': 11929,
                               'ctime_ns': 1793280905175032219,
                               'device': 2304,
                               'inode': 79724997,
                               'mode': '0o664',
                               'mtime_ns': 1793280905166436803,
                               'nlink': 1,
                               'uid': 1001},
                  'path': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/connection_cleanup_receipts.py',
                  'sha256': 'f27e38411238fcf62256e6b317836b757d31d5e0ac962ec8523dd380236d80ee'},
 'game_journal': {'bytes': 21517,
                  'identity': {'bytes': 21517,
                               'ctime_ns': 1793280905225032357,
                               'device': 2304,
                               'inode': 79725793,
                               'mode': '0o664',
                               'mtime_ns': 1793280905215145578,
                               'nlink': 1,
                               'uid': 1001},
                  'path': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/game_journal.py',
                  'sha256': '6aa78cb40434793853d17a1032cc6454ac86b0168828848d9d390336ba8678f0'},
 'inputs': {'bytes': 12952,
            'identity': {'bytes': 12952,
                         'ctime_ns': 1793533292334623062,
                         'device': 2304,
                         'inode': 85479121,
                         'mode': '0o444',
                         'mtime_ns': 1793533292334623062,
                         'nlink': 1,
                         'uid': 1001},
            'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-engineering-fullstate-preservation-original03-20261101/sources/current_main_preservation_inputs_v1.py',
            'sha256': 'a73137cc18cf2c5a1511bdd754e6126f55f0ecf3677c4a6bddd7152db4555f13'},
 'linux': {'bytes': 61466,
           'identity': {'bytes': 61466,
                        'ctime_ns': 1793087972119852954,
                        'device': 2304,
                        'inode': 84698492,
                        'mode': '0o444',
                        'mtime_ns': 1793087832575076042,
                        'nlink': 1,
                        'uid': 1001},
           'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027/preview-flags-preserveRAM-trainer-restart-original01/stop-sources/current192_linux_stop_v1.py',
           'sha256': '3268d0bf2e18d3a7aa9c09addd331b1e42353be45c666203f0818caf294d7437'},
 'semantics': {'bytes': 38995,
               'identity': {'bytes': 38995,
                            'ctime_ns': 1793087991148673998,
                            'device': 2304,
                            'inode': 84698536,
                            'mode': '0o444',
                            'mtime_ns': 1793087618540584727,
                            'nlink': 1,
                            'uid': 1001},
               'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027/preview-flags-preserveRAM-trainer-restart-original01/stop-sources/current192_poststop_only_v1.py',
               'sha256': '7c8e995d67bfbd826e87d327a5dc4dfa796bb12e4c368a3eafd37e23c8466278'},
 'stop': {'bytes': 21677,
          'identity': {'bytes': 21677,
                       'ctime_ns': 1793533292353123449,
                       'device': 2304,
                       'inode': 85479123,
                       'mode': '0o444',
                       'mtime_ns': 1793533292353123449,
                       'nlink': 1,
                       'uid': 1001},
          'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-engineering-fullstate-preservation-original03-20261101/sources/stop_current_continuous_main_fifo_frontier_v2.py',
          'sha256': 'a200c44f5bef77653c01b0416670c7dfc454f44007896a3df55046a685806635'},
 'stop_controller': {'bytes': 17267,
                     'identity': {'bytes': 17267,
                                  'ctime_ns': 1793276061836343604,
                                  'device': 2304,
                                  'inode': 85225403,
                                  'mode': '0o444',
                                  'mtime_ns': 1793276061836343604,
                                  'nlink': 1,
                                  'uid': 1001},
                     'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/stop-sources/control_owned_current_stop900_v1.py',
                     'sha256': '3016bffdec578cacbb354e5d8d453b05e84d42ed8a42e0a3874d91f439c063e8'},
 'stop_kernel': {'bytes': 33465,
                 'identity': {'bytes': 33465,
                              'ctime_ns': 1793533292345414557,
                              'device': 2304,
                              'inode': 85479122,
                              'mode': '0o444',
                              'mtime_ns': 1793533292345414557,
                              'nlink': 1,
                              'uid': 1001},
                 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-engineering-fullstate-preservation-original03-20261101/sources/stop_owned_current_round_training_v3.py',
                 'sha256': '32fb1bdb6a5242229e7f7991c045117edfe1a4ece9b0451962f9702d48284416'},
 'strict_template': {'bytes': 7625,
                     'identity': {'bytes': 7625,
                                  'ctime_ns': 1793278182327324654,
                                  'device': 2304,
                                  'inode': 85226044,
                                  'mode': '0o444',
                                  'mtime_ns': 1793278182327324654,
                                  'nlink': 1,
                                  'uid': 1001},
                     'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/state-sources/Root-stopped-fullstate-v2-job-template-UNFILLED-NOT-LAUNCHABLE.json',
                     'sha256': '57a2a416867beb75623442461b48746a299083ee58e7a1c1b4e2bb21c02c2ca9'},
 'verifier': {'bytes': 35189,
              'identity': {'bytes': 35189,
                           'ctime_ns': 1793533292362123481,
                           'device': 2304,
                           'inode': 85479125,
                           'mode': '0o444',
                           'mtime_ns': 1793533292362123481,
                           'nlink': 1,
                           'uid': 1001},
              'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-engineering-fullstate-preservation-original03-20261101/sources/verify_current_continuous_stopped_fullstate_v4.py',
              'sha256': '790687d7801dc36e1f414bb83dcea62dde8eccadfca41238b00575f627ae1f4d'}}
HELD=dict(batch_size=4096,baseline_batch_size=512,epsilon=.1,expert_ratio=.1,n_step=3,
    max_samples_per_frame=8,c51_target_smoothing=0,learning_control_lr_scale=.125,
    lr_gear='climb',lr_anchor_step=0.,optimizer_lr=6.25e-6,optimizer_eps=1.5e-4,
    fused=True,gamma=.995,num_atoms=51,v_min=-10.,v_max=50.)


def require(value,reason):
    if not value:raise ValueError(reason)


def metadata(path):
    p=Path(path);s=p.lstat();require(p.is_absolute()and p.resolve(strict=True)==p and not p.is_symlink()
        and stat.S_ISREG(s.st_mode)and s.st_uid==os.getuid()and s.st_nlink==1 and 0<s.st_size<=4<<20,'Bounded canonical metadata/source required')
    raw=p.read_bytes();i=lambda v:dict(device=v.st_dev,inode=v.st_ino,bytes=v.st_size,mtime_ns=v.st_mtime_ns,ctime_ns=v.st_ctime_ns,mode=oct(stat.S_IMODE(v.st_mode)),uid=v.st_uid,nlink=v.st_nlink)
    require(i(s)==i(p.stat()),'Metadata/source changed');return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=i(s)),raw


def read(value):
    actual,raw=metadata(value['path']);require(actual==value and value['identity']['mode']=='0o444','Exact sealed full8 metadata required');return json.loads(raw)


def put(path,value):
    raw=value if isinstance(value,bytes)else(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return metadata(path)[0]


def load(role):
    value=SOURCES[role];require(metadata(value['path'])[0]==value,'Selected constructor source changed')
    spec=importlib.util.spec_from_file_location('_current_preservation_'+role,value['path']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def prepare_stop(selection,sha,observation,observed_sha,output):
    own,_=metadata(Path(__file__).resolve());sp,raw=metadata(selection);op,observed=metadata(observation)
    require(sp['sha256']==sha and op['sha256']==observed_sha,'Exact Root selection/observation required')
    selected=json.loads(raw);actual=json.loads(observed);helper=load('inputs')
    anchor=helper.startup_anchor(selected)
    require(selected['input_closure_producer']==SOURCES['stop']
        and selected['zero_frame_FIFO_probe']==dict(authorized=True,client_slot=1,eval_only=True,
            application_frames_to_send=0,scientific_or_natural_game_claimed=False),
        'Explicit selected FIFO-frontier source and zero-frame slot1 authority required')
    require(actual['schema']=='robotron-Root-current-continuous-preservation-observation-v1'
        and actual['trainer']==selected['owner']and actual['fleet']==selected['fleet']
        and 0<=time.time()-actual['observed_unix_s']<=60,'Fresh original owner observation required')
    sourcepins=actual['current_source_pins'];byname={Path(v['path']).name:v for v in sourcepins}
    require(all(byname[k]['sha256']==v for k,v in helper.CURRENT_SHAS.items()),'Current writer/budget source family differs')
    for v in sourcepins:require(metadata(v['path'])[0]==v,'Current selected source changed')
    persistent=actual['persistent_native']
    require(len(persistent)==5 and len({v['comm']for v in persistent.values()})==5
        and {v['comm']for v in persistent.values()}=={'Thread-1 (serve','Thread-2 (_samp','Thread-3 (_cons','Thread-4 (start','Thread-5 (stats'},
        'Five source-bound current persistent native tasks required')
    out=Path(output).absolute();require(out.resolve()==out and out.parent.is_dir()and not out.exists(),'Fresh metadata directory required');out.mkdir(mode=0o700)
    population=put(out/'original-current-population.json',dict(trainer=selected['owner'],fleet=selected['fleet'],actors=actual['actors']))
    control,control_raw=metadata(ROOT/'models_dqn/learning_control.json');require(control==actual['base_control'],'Selected actual control changed')
    require(json.loads(control_raw)['lr_scale']==.125 and json.loads(control_raw).get('measurement')is None,'Exact ordinary continuous recipe required')
    job=dict(schema='robotron-owned-current-round-stop-job-v1',operation_mode='CONTINUOUS_INPUT_CLOSED_BUDGET_EXHAUSTED',
        authorized=True,original_attempt=1,no_retry=True,case='continuous-stop-'+sp['sha256'][:16],source=SOURCES['stop'],
        trainer=selected['owner'],fleet=selected['fleet'],current_selection=sp,current_inputs_source=SOURCES['inputs'],
        expected_current_cap=selected['expected_current_cap'],output=str(out/'runtime'),base_control=control,
        zero_frame_FIFO_probe=selected['zero_frame_FIFO_probe'],
        FIFO_frontier_sources={name:SOURCES[role]for name,role in
            [('connection_cleanup_receipts.py','cleanup_book'),('game_journal.py','game_journal')]},
        experiment=json.loads(control_raw)['experiment'],persistent_native=persistent,
        exposure_instances={k:anchor['exposure_at_load'][k]['instance_monotonic_ns']for k in('optimizer','replay')},
        original_population=population,current_source_pins=sourcepins,historical_cleanup_receipts=actual['historical_cleanup_receipts'],
        console=actual['console'],actor_command=actual['actor_command'],mame_executable=actual['mame_executable'],
        dependencies=dict(linux_utilities=SOURCES['linux'],bank_reader=SOURCES['bank_reader'],bank_intent=SOURCES['budget_intent'],bank_semantics=SOURCES['semantics']),
        inputs=[own,sp,op,population,control,*sourcepins,*SOURCES.values(),selected['startup_job'],selected['startup_held'],selected['startup_release_consumed'],*actual['historical_cleanup_receipts']])
    jp=put(out/'job.json',job);ctl=load('stop_controller')
    cfg=dict(unit='robotron-current-continuous-stop900-'+sp['sha256'][:16]+'.service',output=str(out/'execution-original01'),
        argv=['/usr/bin/python3','-I','-B',SOURCES['stop']['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',SOURCES['stop']['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=900','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=960,pins=[ctl.pin(v['path'])for v in[jp,*job['inputs']]])
    cp=put(out/'controller-config.json',cfg);ctl.checked_config(cp['path'])
    return put(out/'prepared-current-continuous-stop-NOT-LAUNCHED.json',dict(job=jp,config=cp,
        Root_controller_argv=['/usr/bin/python3.12','-I','-B',SOURCES['stop_controller']['path'],'--execute','--config',cp['path'],'--expected-source-sha256',SOURCES['stop_controller']['sha256']],
        actual_stop_or_model_CPU_or_backup=False))


def prepare_cpu(selection,sha,authority,authority_sha,acquisition,acq_sha,output):
    own,_=metadata(Path(__file__).resolve());sp,raw=metadata(selection);require(sp['sha256']==sha,'Exact completed current stop context required');selected=json.loads(raw)
    helper=load('inputs');anchor=helper.startup_anchor(selected)
    ap,raw=metadata(authority);require(ap['sha256']==authority_sha,'Exact actual stopped authority required');a=json.loads(raw)
    require(a['schema']=='robotron-continuous-budget-stopped-preservation-authority-v1'and a['original_selection']==sp
        and a['owner']==selected['owner']and a['actual_exit']==0 and a['original_scope_released']is True,'Only actual same-current normal0 stop required')
    seal=read(a['bank_seal']);api=read(a['final_API']);boot=read(seal['boot_state_descriptor']);require(boot==anchor,'Same actual restored boot descriptor required')
    cp,raw=metadata(acquisition);require(cp['sha256']==acq_sha,'Exact actual independent checkpoint-copy acquisition required');acq=json.loads(raw)
    require(acq['schema']=='robotron-root-stopped-checkpoint-and-independent-copy-v1'and acq['stopped_authority']==ap,'Actual independent copy belongs to another stop')
    source,copied=acq['source_checkpoint'],acq['verification_copy']
    for v in(source,copied):
        path=Path(v['path']);s=path.stat();require(path.resolve()==path and not path.is_symlink()
            and s.st_size==v['bytes']and s.st_ino==v['identity']['inode']and s.st_dev==v['identity']['device'], 'Actual checkpoint/copy stat differs')
    require(source['path']==str(ROOT/'models_dqn/robotron_dqn_latest.pt')and source['sha256']==copied['sha256']
        and(source['identity']['device'],source['identity']['inode'])!=(copied['identity']['device'],copied['identity']['inode'])
        and copied['identity']['mode']=='0o444','Same independent readonly latest copy required')
    out=Path(output).absolute();require(out.resolve()==out and out.parent.is_dir()and not out.exists(),'Fresh strict CPU preparation required');out.mkdir(mode=0o700)
    old=read(SOURCES['strict_template'])
    anchor_replay=anchor['exposure_at_load']['replay'];ring_anchor=put(out/'actual-current-ring-adoption-anchor.json',dict(schema='robotron-source-bound-replay-pointer-insertion-anchor-v1',
        owner=selected['owner'],process_id=selected['owner']['pid'],instance_monotonic_ns=anchor_replay['instance_monotonic_ns'],
        epoch=anchor_replay['epoch'],epoch_reason=anchor_replay['epoch_reason'],ptr=anchor['ring_at_load']['ptr'],accepted_total=anchor_replay['accepted_total'],source_evidence=selected['startup_held']))
    control,control_raw=metadata(ROOT/'models_dqn/learning_control.json');archived_control=put(out/'actual-final-learning-control.json',control_raw)
    byname={Path(v['path']).name:v for v in read(selected['input_closure'])['source_pins']}
    package={k:byname[k]for k in('model.py','config.py','learning_control.py','__init__.py')}
    for v in package.values():require(metadata(v['path'])[0]==v,'Selected model source changed')
    terminal=read(a['terminal_archive']);cat=read(terminal['archives']['cat']);require(cat['exit']==0,'Original unit CAT0 required')
    recipe=dict(HELD,max_samples_per_frame=selected['expected_current_cap'])
    old.update(schema='robotron-stopped-full-training-state-CPU-job-v1',source=SOURCES['verifier'],
        unit='robotron-current-continuous-header-stopped600-'+sp['sha256'][:16]+'.service',owner=selected['owner'],fleet=selected['fleet'],
        current_selection=sp,current_inputs_source=SOURCES['inputs'],expected_current_cap=selected['expected_current_cap'],
        experiment=api['managed_experiment'],clock_floor=seal['clock_floor'],source_checkpoint=source,verification_copy=copied,
        stopped_authority=ap,boot_CPU_report=seal['boot_state_descriptor'],phase_anchor=seal['boot_state_descriptor'],phase_record=anchor['phase_record'],
        ring_insert_anchor=ring_anchor,ring_storage_before=selected['ring_storage_before'],output_directory=str(out/'runtime'),
        phase_snapshot=dict(expected_phase=dict(metric='ce')),
        source_control_context=dict(game_root=str(ROOT),model_dir=str(ROOT/'models_dqn'),model_package=package,
            archived_control=archived_control,archived_trainer_unit=cat['stdout'],
            provenance=[sp,ap,a['bank_seal'],selected['startup_job'],selected['startup_held'],selected['startup_release_consumed']],held_recipe_context=recipe))
    old['inputs']=[own,SOURCES['strict_template'],sp,ap,cp,a['bank_seal'],a['final_API'],seal['before_API'],selected['input_closure'],a['terminal_archive'],
        a['fleet_terminal_archive'],terminal['archives']['cat'],cat['stdout'],archived_control,ring_anchor,selected['ring_storage_before'],
        seal['boot_state_descriptor'],anchor['phase_record'],*package.values(),*old['dependencies'].values(),*SOURCES.values()]
    jp=put(out/'job.json',old);ctl=load('CPU_controller');cfg=dict(unit=old['unit'],output=str(out/'execution-original01'),
        argv=[str(ROOT.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',SOURCES['verifier']['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',SOURCES['verifier']['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=660,pins=[ctl.pin(v['path'])for v in[jp,*old['inputs']]])
    conf=put(out/'controller-config.json',cfg);ctl.checked_config(conf['path'])
    return put(out/'prepared-current-continuous-stopped600-NOT-LAUNCHED.json',dict(job=jp,config=conf,
        Root_controller_argv=['/usr/bin/python3.12','-I','-B',SOURCES['CPU_controller']['path'],'--execute','--config',conf['path'],'--expected-source-sha256',SOURCES['CPU_controller']['sha256']],
        CPU_or_startup_or_backup_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group();m.add_argument('--prepare-stop',action='store_true');m.add_argument('--prepare-cpu',action='store_true')
    p.add_argument('--selection',type=Path);p.add_argument('--selection-sha256');p.add_argument('--observation',type=Path);p.add_argument('--observation-sha256')
    p.add_argument('--stopped-authority',type=Path);p.add_argument('--stopped-authority-sha256');p.add_argument('--checkpoint-acquisition',type=Path);p.add_argument('--checkpoint-acquisition-sha256')
    p.add_argument('--output',type=Path);p.add_argument('--source-sha256');a=p.parse_args()
    if a.prepare_stop or a.prepare_cpu:
        require(metadata(Path(__file__).resolve())[0]['sha256']==a.source_sha256,'Exact immutable preparer source required')
        if a.prepare_stop:result=prepare_stop(a.selection,a.selection_sha256,a.observation,a.observation_sha256,a.output)
        else:result=prepare_cpu(a.selection,a.selection_sha256,a.stopped_authority,a.stopped_authority_sha256,a.checkpoint_acquisition,a.checkpoint_acquisition_sha256,a.output)
        print(json.dumps(result),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
