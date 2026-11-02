"""Current-campaign BEFORE parent release resource observation only.
Default PLAN is read-free. Root alone may explicitly execute after source review.
No release, signals, acceptance, promotion, canonical or model-body operations.
"""
import argparse
import errno
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import urllib.request

RUN=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
SCHEMA='robotron-current-first-LATCH-followup-before-parent-release-resources-v1'
FIXED={'baseline': {'bytes': 200174,
              'identity': {'bytes': 200174,
                           'ctime_ns': 1792273729722485903,
                           'device': 2304,
                           'inode': 81160446,
                           'mode': '0o444',
                           'mtime_ns': 1792273729722485903,
                           'nlink': 1,
                           'uid': 1001},
              'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality-root-preparation-20261017/runtime-baseline.json',
              'sha256': '445b8eea9c5a5009564a04d014fb81aca6957ad1381ed29c332c6987a8e22022'},
 'binding': {'bytes': 254898,
             'identity': {'bytes': 254898,
                          'ctime_ns': 1792273808474594536,
                          'device': 2304,
                          'inode': 81160448,
                          'mode': '0o444',
                          'mtime_ns': 1792273808474594536,
                          'nlink': 1,
                          'uid': 1001},
             'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality-root-preparation-20261017/root-quality-binding-job.json',
             'sha256': '25bde9295865770d9a0317ad32a65efa464abb3f71ec3d68f8adc0c8978eeb5b'},
 'helper': {'bytes': 29433,
            'identity': {'bytes': 29433,
                         'ctime_ns': 1792274392315653342,
                         'device': 2304,
                         'inode': 81160570,
                         'mode': '0o444',
                         'mtime_ns': 1792274359969060889,
                         'nlink': 1,
                         'uid': 1001},
            'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-readiness-collector-source-preparation-20261017/collect_readiness.py',
            'sha256': '9a8b4a20f090597f1ffad1a8c959c0cf886e3b119a17343857c7ce1d0f563f9b'},
 'inventory': {'bytes': 342972,
               'identity': {'bytes': 342972,
                            'ctime_ns': 1792279904886809465,
                            'device': 2304,
                            'inode': 81268846,
                            'mode': '0o444',
                            'mtime_ns': 1792279904886809465,
                            'nlink': 1,
                            'uid': 1001},
               'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-original69-identity-inventory-source-preparation-20261017/original69-identities.json',
               'sha256': 'a4ceba658a1ff635122b13c4ec7b18e2f6ee322b5f6b3dd71ce84ea1b8173e63'},
 'original_readiness_case': {'bytes': 3472,
                             'identity': {'bytes': 3472,
                                          'ctime_ns': 1792274607626450848,
                                          'device': 2304,
                                          'inode': 81160581,
                                          'mode': '0o444',
                                          'mtime_ns': 1792274607626450848,
                                          'nlink': 1,
                                          'uid': 1001},
                             'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality-root-preparation-20261017/root-readiness-case.json',
                             'sha256': '9116725fff363331af9ed2c3cd4b741c78650d9a1a82bfc63560fcfd742d0d90'},
 'parent_archive': {'bytes': 405,
                    'identity': {'bytes': 405,
                                 'ctime_ns': 1792280581212276671,
                                 'device': 2304,
                                 'inode': 81167020,
                                 'mode': '0o444',
                                 'mtime_ns': 1792280581212276671,
                                 'nlink': 1,
                                 'uid': 1001},
                    'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality-root-execution-20261017/original-terminal-archive.json',
                    'sha256': 'c4cecd9faafaeecc0aa29a2a0941f623ea2b52c7a87d74b2750a740172c10fa6'},
 'plan': {'bytes': 277387,
          'identity': {'bytes': 277387,
                       'ctime_ns': 1792274718967148757,
                       'device': 2304,
                       'inode': 81163062,
                       'mode': '0o444',
                       'mtime_ns': 1792274718967148757,
                       'nlink': 1,
                       'uid': 1001},
          'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality-actual-launch-root-20261017/actual-native-plan-readonly-copy.json',
          'sha256': 'fdb13f963f7433d8dcd816934fe266f327760a7953d47a1208f752f284d5fe85'}}
RELEASES={'original_audit_leg01': {'bytes': 20694,
                          'identity': {'bytes': 20694,
                                       'ctime_ns': 1792276177156001508,
                                       'device': 2304,
                                       'inode': 81164392,
                                       'mode': '0o444',
                                       'mtime_ns': 1792276177156001508,
                                       'nlink': 1,
                                       'uid': 1001},
                          'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality-original-row-leg01-audit-root-execution-reviewed1-20261017/root-result-review-and-release.json',
                          'sha256': 'eaa1fc2fc4e09b2b4df6e1454511c95510781bedfafedd64088fd577acbb1292'},
 'original_audit_leg02': {'bytes': 20694,
                          'identity': {'bytes': 20694,
                                       'ctime_ns': 1792277599707903747,
                                       'device': 2304,
                                       'inode': 81167006,
                                       'mode': '0o444',
                                       'mtime_ns': 1792277599707903747,
                                       'nlink': 1,
                                       'uid': 1001},
                          'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality-original-row-leg02-audit-root-execution-reviewed1-20261017/root-result-review-and-release.json',
                          'sha256': '4631c5d322ad14ae39ff1903cc682b48d0baa58312eed70738c07ba5a7185619'},
 'original_audit_leg03': {'bytes': 20694,
                          'identity': {'bytes': 20694,
                                       'ctime_ns': 1792279056773974431,
                                       'device': 2304,
                                       'inode': 81267332,
                                       'mode': '0o444',
                                       'mtime_ns': 1792279056773974431,
                                       'nlink': 1,
                                       'uid': 1001},
                          'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality-original-row-leg03-audit-root-execution-reviewed1-20261017/root-result-review-and-release.json',
                          'sha256': '5720dedc73c0bcef0f88b7904747254973269b6a0ecc7ec328333fa44cee9b97'},
 'original_audit_leg04': {'bytes': 20694,
                          'identity': {'bytes': 20694,
                                       'ctime_ns': 1792280527386687597,
                                       'device': 2304,
                                       'inode': 81269103,
                                       'mode': '0o444',
                                       'mtime_ns': 1792280527386687597,
                                       'nlink': 1,
                                       'uid': 1001},
                          'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality-original-row-leg04-audit-root-execution-reviewed1-20261017/root-result-review-and-release.json',
                          'sha256': '9e2b717de5725c0ce20c13453a83638fa2a20e776622771e1a17a21715c017ea'},
 'quality20_guard': {'bytes': 1421,
                     'identity': {'bytes': 1421,
                                  'ctime_ns': 1792273881740138224,
                                  'device': 2304,
                                  'inode': 81160480,
                                  'mode': '0o444',
                                  'mtime_ns': 1792273881740138224,
                                  'nlink': 1,
                                  'uid': 1001},
                     'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality20-guards-root-execution-20261017/root-result-review-and-release.json',
                     'sha256': 'b041a43cde469861cec59348493b378f49d5f9ceafb98514d68c3958b1c4e341'},
 'quality20_guard-reviewed2': {'bytes': 2235,
                               'identity': {'bytes': 2235,
                                            'ctime_ns': 1792274008457418191,
                                            'device': 2304,
                                            'inode': 81160510,
                                            'mode': '0o444',
                                            'mtime_ns': 1792274008457418191,
                                            'nlink': 1,
                                            'uid': 1001},
                               'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality20-guards-root-execution-reviewed2-20261017/root-result-review-and-release.json',
                               'sha256': '946d0604d497ddc96fc66262ea91761d01c957a4bb48ab7477738f05631df7e6'},
 'quality20_guard-reviewed3': {'bytes': 2229,
                               'identity': {'bytes': 2229,
                                            'ctime_ns': 1792274227511171700,
                                            'device': 2304,
                                            'inode': 81160542,
                                            'mode': '0o444',
                                            'mtime_ns': 1792274227511171700,
                                            'nlink': 1,
                                            'uid': 1001},
                               'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-quality20-guards-root-execution-reviewed3-20261017/root-result-review-and-release.json',
                               'sha256': 'a2c2798e528d8af919d61fcff97f40b791416deef8db14b4eff51e627d8cc011'}}


def require(value,message):
    if not value:raise RuntimeError(message)


def fingerprint(path):
    path=Path(path);require(path.is_absolute() and path==path.resolve(strict=True),'Canonical source required')
    def identity(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
        before=os.fstat(f.fileno());require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and
            before.st_nlink==1 and 0<before.st_size<=4<<20,'Owned bounded source required')
        raw=f.read((4<<20)+1);require(len(raw)==before.st_size and
            identity(before)==identity(os.fstat(f.fileno()))==identity(path.lstat()),'Source changed')
    return raw,dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))


def load_helper():
    raw,actual=fingerprint(FIXED['helper']['path']);require(actual==FIXED['helper'],'Pinned readonly9a8 helper differs')
    spec=importlib.util.spec_from_file_location('_current_before_release_9a8',FIXED['helper']['path'])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    require(fingerprint(FIXED['helper']['path'])[0]==raw,'Helper changed while loading')
    return module


def health(obs,cfg,plan,baseline,maintenance,M):
    # Exact9a8 body264..391 follows, with only explicit bindings to its helpers.
    process=M.process;proc_bytes=M.proc_bytes;process_start=M.process_start;cgroup_empty=M.cgroup_empty
    pin_key=M.pin_key;read_file=M.read_file;identity=M.identity
    UID=M.UID;GAME=M.GAME;GPU_UUIDS=M.GPU_UUIDS;BLOCKED=M.BLOCKED
    resources=obs.pinned(baseline['actual_main192_resources']);environment=obs.pinned(baseline['actual_selected_environment'])
    fleet_descriptor=obs.pinned(baseline['actual_fleet_descriptor']);before_API=json.loads(obs.pinned(baseline['actual_API'],raw_only=True))
    require(resources['owner']==baseline['main_owner'] and resources['worker']==baseline['inference_worker']
        and fleet_descriptor['owner']==baseline['fleet_owner'] and fleet_descriptor['process']==resources['fleet'],
        'Saved exact process/worker/fleet witnesses differ')
    owner=baseline['main_owner'];fleet=baseline['fleet_owner'];worker=baseline['inference_worker']
    def unit_owner(o):
        s=obs.show(o['unit']);require(s.get('MainPID')==str(o['pid']) and s.get('InvocationID')==o['invocation_id']
            and s.get('ControlGroup')==o['cgroup'] and s.get('ActiveState')=='active' and s.get('SubState')=='running'
            and s.get('NRestarts')=='0','Current main/fleet unit identity differs')
        return s
    main_show=unit_owner(owner);fleet_show=unit_owner(fleet);require(main_show.get('Restart')=='no','Main Restart differs')
    main=process(obs,owner,owner['cgroup'],resources['main'])
    actual_fleet=process(obs,fleet,fleet['cgroup'],resources['fleet'])
    saved_actors={x['pid']:x for x in resources['actors']};require(len(saved_actors)==192,'Saved actual actor set differs')
    actors=[]
    for actor in baseline['actors']:
        expected=saved_actors[actor['pid']]
        require(all(expected[k]==actor[k] for k in ('pid','starttime_ticks','mask')),'Baseline/process actor identity differs')
        actors.append(process(obs,actor,fleet['cgroup'],expected))
    require(set(saved_actors)=={x['pid'] for x in baseline['actors']} and
        {x['slot'] for x in baseline['actors']}==set(range(192)),'Original192 actor slot/PID set differs')
    thread=Path('/proc',str(owner['pid']),'task',str(worker['tid']))
    raw_thread=dict(stat=proc_bytes(thread/'stat').decode(),status=proc_bytes(thread/'status').decode(),
        cgroup=proc_bytes(thread/'cgroup').decode(),mask=sorted(os.sched_getaffinity(worker['tid'])))
    worker_pin=obs.publish('inference-worker.json',raw_thread)
    thread_status=dict(line.split(':',1) for line in raw_thread['status'].splitlines() if ':' in line)
    require([int(x) for x in thread_status['Uid'].split()]==[UID]*4,'Inference thread UID differs')
    require(thread.exists() and process_start(worker['tid'])==worker['starttime_ticks'] and
        raw_thread['mask']==worker['mask'] and owner['cgroup'] in
        [line.split(':',2)[2] for line in raw_thread['cgroup'].splitlines()],
        'Inference thread identity/mask/cgroup differs')
    selected=dict(os.fsdecode(x).split('=',1) for x in proc_bytes(Path('/proc',str(owner['pid']),'environ'),1<<20).split(b'\0')
        if b'=' in x and os.fsdecode(x).startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_')))
    selected_pin=obs.publish('selected-environment.json',selected)
    phase=maintenance['startup']['phase']
    require(selected==environment and hashlib.sha256(json.dumps(selected,sort_keys=True).encode()).hexdigest()==baseline['environment_sha256']
        and selected.get('DQN_BATCH_SIZE')=='4096' and selected.get('DQN_PER_PRIORITY_METRIC')=='ce'
        and selected.get('DQN_PRIORITY_PHASE_RECORD')==phase['record']['path']
        and selected.get('DQN_PRIORITY_PHASE_RECORD_SHA256')==phase['record']['sha256'],
        'Exact current maintenance CE4096 environment differs')
    obs.pinned(baseline['actual_maintenance'])
    require(pin_key(baseline['actual_maintenance'])==pin_key(cfg['evidence']['maintenance_result']),
        'Baseline genuine maintenance witness differs')
    predecessor=obs.pinned(cfg['predecessor_quality_plan'])
    require(plan['evaluator_source_hashes']==predecessor['evaluator_source_hashes'] and
        plan['execution_source_hashes']==predecessor['execution_source_hashes'],'Unchanged evaluation12+execution4 closure differs')
    hashes={};resolution=[]
    for name in ('source_hashes','control_hashes','unit_files'):
        for path,digest in baseline[name].items():
            require(Path(path).is_absolute() and (path not in hashes or hashes[path]==digest),'Absolute held source mapping differs')
            hashes[path]=digest
    for name,digest in plan['evaluator_source_hashes'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Evaluator key must be GAME relative')
        path=str(GAME/name);require(path not in hashes or hashes[path]==digest,'Evaluator source overlap differs')
        hashes[path]=digest;resolution.append(dict(declared_key=name,resolved_path=path,sha256=digest))
    for path,digest in plan['execution_source_hashes'].items():
        require(Path(path).is_absolute() and (path not in hashes or hashes[path]==digest),'Absolute execution mapping differs')
        hashes[path]=digest
    checked=[]
    for path,digest in hashes.items():
        _,pin=read_file(path);require(pin['sha256']==digest,'Held source/control/unit file changed: '+path);checked.append(pin)
    helper_processes=[];actor_pids=set();private_processes=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal() or int(p.name)==os.getpid():continue
        try:
            argv=[os.fsdecode(x) for x in proc_bytes(p/'cmdline').split(b'\0') if x]
            groups=proc_bytes(p/'cgroup').decode()
        except OSError as e:
            if e.errno in (errno.ENOENT,errno.ESRCH):continue
            raise
        if any(os.path.basename(x) in BLOCKED for x in argv):helper_processes.append(dict(pid=int(p.name),argv=argv))
        if any('/dev/shm/robotron-snapshot-smoke-' in x for x in argv) or 'robotron-snapshot-smoke-' in groups:
            private_processes.append(dict(pid=int(p.name),argv=argv,cgroup=groups))
        if argv and os.path.basename(argv[0])=='mame' and 'robotron' in argv:actor_pids.add(int(p.name))
    scan_pin=obs.publish('global-process-scan.json',dict(competing_helpers=helper_processes,private_processes=private_processes,
        robotron_actor_pids=sorted(actor_pids)))
    require(not helper_processes and not private_processes,'Competing/private helper process remains')
    require(actor_pids==set(saved_actors),'Global Robotron actor set differs from original192')
    private=[str(p) for p in Path('/dev/shm').glob('robotron-snapshot-smoke-*') if p.is_dir()]
    require(not private,'Private snapshot tmpfs directory remains')
    app=(Path('/sys/fs/cgroup')/owner['cgroup'].lstrip('/')).parent
    groups=[cgroup_empty('/'+str(p.relative_to('/sys/fs/cgroup'))) for p in app.glob('robotron-snapshot-smoke-*')]
    listeners=[];tcp_raw={}
    for table in ('tcp','tcp6'):
        raw=proc_bytes(Path('/proc/net',table),1<<20).decode();tcp_raw[table]=raw
        for row in raw.splitlines()[1:]:
            parts=row.split()
            if parts[3]=='0A' and int(parts[1].rsplit(':',1)[1],16)==9999:listeners.append(row)
    tcp_pin=obs.publish('port9999-tables.json',tcp_raw);require(not listeners,'Port9999 listener remains')
    lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');before=lease.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid==UID,'Existing lease file owner/type differs')
    fd=os.open(lease,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        require(identity(before)==identity(os.fstat(fd))==identity(lease.lstat()),'Lease identity raced')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(identity(before)==identity(os.fstat(fd))==identity(lease.lstat()),'Lease changed during readonly probe')
        fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    require(not os.path.lexists(GAME/'models_dqn/managed_save.request.json'),'Managed save request pending')
    gpu=obs.call(['nvidia-smi','--query-gpu=index,uuid','--format=csv,noheader,nounits'])
    apps=obs.call(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'])
    memory=obs.call(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'])
    require(gpu['returncode']==apps['returncode']==memory['returncode']==0,'GPU observation failed')
    mapping={int(a.strip()):b.strip() for a,b in (line.split(',') for line in gpu['stdout'].splitlines() if line.strip())}
    app_rows=[(int(a.strip()),b.strip()) for a,b in (line.split(',') for line in apps['stdout'].splitlines() if line.strip())]
    free={a.strip():int(b.strip())*(1<<20) for a,b in (line.split(',') for line in memory['stdout'].splitlines() if line.strip())}
    require(mapping==GPU_UUIDS and app_rows==[(owner['pid'],GPU_UUIDS[1])] and free[GPU_UUIDS[0]]>=14*(1<<30),
        'GPU0 ownership/free margin or sole main GPU1 owner differs')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as response:raw=response.read((2<<20)+1)
    require(0<len(raw)<=2<<20,'API response exceeds bound');raw_pin=obs.write('raw-main-API.json',raw)
    api=json.loads(raw);pipeline=api['host_pipeline'];graphs=pipeline['inference_graphs'];age=time.time()-float(api['ts'])
    require(math.isfinite(age) and 0<=age<=5 and api['client_count']==192 and api['training_enabled'] is True
        and api['measurement_active'] is False and api['managed_experiment']==cfg['experiment'],'Fresh held API main192 branch differs')
    require(all(pipeline['learning_exposure'][kind]['process_id']==owner['pid'] for kind in ('optimizer','replay')),
        'API process owner differs')
    require(all(type(api[k]) is int and api[k]>=before_API[k] for k in
        ('training_steps','optimized_samples','learner_frame_count','frame_count')),'API four clocks regressed/unavailable')
    require(graphs['ready'] is True and graphs['capture_count']==128 and graphs['validation_replay_count']==640
        and graphs['postload_validations']>=1 and graphs['runtime_capture_count']==graphs['fallback_count']==0
        and graphs['fatal_error'] is None and all(pipeline[k]['errors']==0 for k in
        ('inference','actor_refresh','target_refresh','learner_priority')),'API graphs/four errors differ')
    latest=GAME/'models_dqn/robotron_dqn_latest.pt';latest_stat=latest.lstat();latest_age=time.time()-latest_stat.st_mtime
    require(stat.S_ISREG(latest_stat.st_mode) and latest_stat.st_uid==UID and 0<latest_stat.st_size<=512<<20
        and math.isfinite(latest_age) and 0<=latest_age<=600,'Latest autosave metadata is not fresh')
    unit_owner(owner);unit_owner(fleet)
    require(all(process_start(x['pid'])==x['starttime_ticks'] for x in [owner,fleet,*baseline['actors']]) and
        process_start(worker['tid'])==worker['starttime_ticks'],'Main/fleet/actor/inference incarnation changed at final bracket')
    return dict(main=main,fleet=actual_fleet,actors=actors,inference_worker=worker_pin,
        selected_environment=selected_pin,checked_source_control_unit_pins=checked,
        evaluator_source_declared_and_resolved=resolution,global_process_scan=scan_pin,
        lease_identity=identity(before),private_tmpfs=private,private_cgroups=groups,port9999=tcp_pin,
        raw_API=raw_pin,API_summary=dict(ts=api['ts'],age_s=age,client_count=192,
            training_enabled=True,learner_frame_count=api['learner_frame_count'],four_pipeline_errors=0),
        latest_autosave_metadata=dict(path=str(latest),identity=identity(latest_stat),age_s=latest_age,
            max_age_s=600,body_read_or_hash=False),GPU0_free_bytes=free[GPU_UUIDS[0]],
        GPU0_no_compute_owner=True,GPU1_main_only=True)


def parent_terminal(obs,inventory):
    owner=inventory['original_quality_owner'];timer=inventory['original_timer']
    s=obs.show(owner['unit'])
    require(s.get('LoadState')=='loaded' and s.get('MainPID')=='0' and
        s.get('ExecMainPID')==str(owner['pid']) and s.get('InvocationID')==owner['invocation_id'] and
        s.get('ExecMainCode')=='1' and s.get('ExecMainStatus')=='0' and s.get('Result')=='success' and
        s.get('NRestarts')=='0' and s.get('ActiveState')=='active' and s.get('SubState')=='exited' and
        s.get('ControlGroup') in ('',owner['cgroup']),'Original parent is not same retained terminal0')
    t=obs.show(timer['unit'])
    require(timer['process_identity_not_applicable'] is True and
        (t.get('LoadState')=='not-found' or (t.get('LoadState')=='loaded' and
        t.get('InvocationID')==timer['invocation_id'])),'Original timer invocation changed')
    return dict(service=s,timer=t,timer_process_identity_not_applicable=True)


def absence(obs,inventory,M,name):
    rows=[]
    for item in inventory['identities']:
        current=M.process_start(item['pid'])
        rows.append(dict(kind=item['kind'],leg=item['leg'],slot=item['slot'],pid=item['pid'],
            original_starttime_ticks=item['starttime_ticks'],observed_starttime_ticks=current,
            original_absent=current!=item['starttime_ticks']))
    result=dict(inventory=FIXED['inventory'],observed_unix_s=time.time(),identities=rows,
        all69_absent=all(x['original_absent'] for x in rows),quality_cgroup=M.cgroup_empty(inventory['original_quality_cgroup']))
    proof=obs.publish(name,result);require(result['all69_absent'],'An original quality process remains')
    return proof


def observe(obs,M):
    inventory=obs.pinned(FIXED['inventory']);cfg=obs.pinned(FIXED['binding']);baseline=obs.pinned(FIXED['baseline'])
    plan=obs.pinned(FIXED['plan']);oldcase=obs.pinned(FIXED['original_readiness_case']);archive=obs.pinned(FIXED['parent_archive'])
    require(inventory['schema']=='robotron-original-quality-historical-69-identity-inventory-v1' and
        inventory['actual_plan']==FIXED['plan'] and inventory['actual_plan_sha256']==FIXED['plan']['sha256'] and
        inventory['counts']==dict(distinct_PID_start_pairs=69,distinct_historical_PIDs=69,evaluators=4,private_actors=64,quality_parent=1,total=69),
        'Exact original69/nativeplan inventory differs')
    require(len(inventory['identities'])==69 and len({(x['pid'],x['starttime_ticks']) for x in inventory['identities']})==69 and
        all(type(x['pid']) is int and x['pid']>0 and type(x['starttime_ticks']) is int and x['starttime_ticks']>0
            for x in inventory['identities']),'Original69 PID/start fields differ')
    owner=inventory['original_quality_owner'];require(owner['pid']==1673818 and owner['starttime_ticks']==36563185 and
        owner['invocation_id']=='942c390f35d84884bd41f3d04ac9d7ff' and
        inventory['original_timer']['invocation_id']=='35e04e4c9ec34171bcbc1112eb57f9c6','Current original quality owner/timer differs')
    require(archive['status']=='ORIGINAL_TERMINAL_ARCHIVED_NOT_RELEASED' and archive['service_retained'] is True and
        all(archive['original'][k]==owner[k] for k in ('pid','starttime_ticks','invocation_id','unit')) and
        archive['exec_main_code']==1 and archive['exec_main_status']==0 and archive['result']=='success',
        'Actual original terminal archive differs')
    require(cfg['runtime_baseline']==FIXED['baseline'] and oldcase['binding']==FIXED['binding'] and
        cfg['campaign']['output_directory']==inventory['campaign_directory']==plan['output_directory'] and
        cfg['campaign']['unit']+'.service'==owner['unit'] and len(plan['evaluator_source_hashes'])==12 and
        len(plan['execution_source_hashes'])==4,'Actual binding/baseline/campaign/source closure differs')
    keys=('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')
    require(all(baseline[k]==cfg['runtime_anchor'][k] for k in keys) and len(baseline['source_hashes'])==61 and
        len(baseline['control_hashes'])==2 and len(baseline['unit_files'])==3 and len(baseline['actors'])==192 and
        not {x['pid'] for x in inventory['identities']}.intersection({baseline['main_owner']['pid'],baseline['fleet_owner']['pid'],
            *[x['pid'] for x in baseline['actors']]}),'Current held192 baseline/quality inventory overlap')
    first_parent=parent_terminal(obs,inventory);first_absence=absence(obs,inventory,M,'original69-before.json')
    units,old_owners,maintenance=M.known_units(obs,cfg,oldcase)
    quality_pair={owner['unit'],inventory['original_timer']['unit']};require(quality_pair.issubset(units),'Quality pair missing')
    units=set(units)-quality_pair;extra_absence=[]
    for label,bound in RELEASES.items():
        receipt=obs.pinned(bound)
        require(receipt['original_archived_before_release'] is True and receipt.get('unit_released',True) is True and
            len(receipt['owned_release'])==2,'Actual extra archive/release differs: '+label)
        pid=receipt['original_pid'];started=receipt['original_starttime_ticks']
        require(type(pid) is int and pid>0 and type(started) is int and started>0,'Actual extra owner PID/start missing')
        current=M.process_start(pid)
        extra_absence.append(dict(release=bound,original_pid=pid,original_starttime_ticks=started,
            observed_starttime_ticks=current,original_absent=current!=started))
        require(current!=started,'An original extra audit/guard process remains: '+label)
        names={x['unit'] for x in receipt['owned_release']}
        require(all(x.get('final_load_state')=='not-found' or x.get('already_absent') is True for x in receipt['owned_release']) and
            len(names)==2 and len({x.removesuffix('.service').removesuffix('.timer') for x in names})==1 and
            any(x.endswith('.service') for x in names) and any(x.endswith('.timer') for x in names),
            'Actual exact extra unitpair differs: '+label)
        units.update(names)
    require(not units.intersection(quality_pair|{baseline['main_owner']['unit'],baseline['fleet_owner']['unit']}),'Protected units cannot be absence targets')
    units=sorted(units);first_units=M.absent_units(obs,units)
    old_absence=[]
    for old in old_owners:
        actual=M.process_start(old['pid']);require(actual!=old['starttime_ticks'],'Old helper remains')
        old_absence.append(dict(owner=old,observed_starttime_ticks=actual))
    observations=health(obs,cfg,plan,baseline,maintenance,M)
    last_absence=absence(obs,inventory,M,'original69-after.json');last_parent=parent_terminal(obs,inventory)
    last_units=M.absent_units(obs,units)
    return dict(schema=SCHEMA,status='PASS_BEFORE_PARENT_RELEASE_RESOURCES_ONLY',observed_unix_s=time.time(),
        inventory=FIXED['inventory'],binding=FIXED['binding'],plan=FIXED['plan'],runtime_baseline=FIXED['baseline'],
        original_parent=owner,original_timer=inventory['original_timer'],parent_retained_terminal=True,quality_units_released=False,
        all69_absent=True,non_parent_owned_helpers_absent=True,original_quality_cgroup_empty=True,
        parent_before=first_parent,parent_after=last_parent,all69_before=first_absence,all69_after=last_absence,
        non_parent_units=units,first_unit_absence=first_units,last_unit_absence=last_units,old_process_absence=old_absence,
        extra_original_process_absence=extra_absence,
        current_held_baseline={k:baseline[k] for k in keys},health=observations,
        release_actions=False,quality_acceptance=False,source_freeze_released=False,qualification_pass=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--output',type=Path);parser.add_argument('--expected-source-sha256');args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no reads/imports/queries/locks/outputs; current resources only, no release/acceptance');return 0
    require(args.output and args.expected_source_sha256,'Explicit root source and NEW output required')
    _,source=fingerprint(Path(__file__).resolve());require(source['sha256']==args.expected_source_sha256 and
        source['identity']['mode']=='0o444','Exact readonly source required')
    out=args.output;require(out.is_absolute() and out.parent==RUN and out==out.resolve(strict=False) and not os.path.lexists(out),'NEW direct run26 output required')
    M=load_helper();out.mkdir(mode=0o700)
    fd=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    obs=M.Observation(out);result=dict(schema=SCHEMA,status='FAILED_BEFORE_PARENT_RELEASE_RESOURCE_OBSERVATION',
        started_unix_s=time.time(),release_actions=False,quality_acceptance=False,source_freeze_released=False,qualification_pass=False)
    try:result.update(observe(obs,M))
    except BaseException as error:result['first_error']=dict(type=type(error).__name__,message=str(error))
    result.update(ended_unix_s=time.time(),checker_source=source,raw_command_metadata=obs.commands,saved_input_pins=obs.pins)
    obs.publish('before-parent-release-resources.json',result)
    print(json.dumps(dict(status=result['status'],output=str(out)),allow_nan=False))
    return 0 if result['status']=='PASS_BEFORE_PARENT_RELEASE_RESOURCES_ONLY' else 2


if __name__=='__main__':raise SystemExit(main())
