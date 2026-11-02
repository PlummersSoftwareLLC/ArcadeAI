"""Root-only exact five-file source installation AFTER qualified full backup.

Default inert. Root supplies immutable complete-backup and positively closed
original-backup proofs. No model/replay/control writes, services, signals, GPU or
API calls. Four exact preimages and any partial installation are retained.
"""
import argparse,ast,hashlib,json,os,re,stat,time
from pathlib import Path
ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
OPERATOR={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-A2-RPC-ACK-telemetry-fullstate-maintenance-original01-20261031/future-post-backup-held-startup-source-original01/prepare_and_release_repaired_current_fullstate_startup_v5.py', 'sha256': '11f7e4f1d1d8b11b373d4922c704ab072a57fc85f976d919c41995821df95d1a', 'bytes': 17169, 'identity': {'device': 2304, 'inode': 82734107, 'bytes': 17169, 'mtime_ns': 1793478910663965778, 'ctime_ns': 1793478910663965778, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
INSTALL=[{'source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fleet-wide-multiple-reconnect-overlap-quarantine-original01-20261031/future-Main-RPC-and-FIFO-ACK-composed-source-only-original02/socket_server.py', 'sha256': '1692ee2dbfb6f83d0f50234ee1eb30d0cf6bbe45d670a5a9fb52992fd92b56fc', 'bytes': 164721, 'identity': {'device': 2304, 'inode': 82727544, 'bytes': 164721, 'mtime_ns': 1793470544630465316, 'ctime_ns': 1793470544630589636, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'destination': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/socket_server.py', 'expected_preimage_sha256': 'a076501b0601a637b91269a41572be60496754ad1da4b04385d77c51b9f34423', 'new_destination_must_be_proven_absent_before_install': False, 'actual_preimage': None, 'actual_installed_pin': None}, {'source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fleet-wide-multiple-reconnect-overlap-quarantine-original01-20261031/future-Main-RPC-and-FIFO-ACK-composed-source-only-original02/bounded_fifo_cleanup_ack_v1.py', 'sha256': 'aab678c023598c90aa0374473eab7da8db9e71818a5d668aee2c222730d92fd8', 'bytes': 2577, 'identity': {'device': 2304, 'inode': 82727545, 'bytes': 2577, 'mtime_ns': 1793470544631795785, 'ctime_ns': 1793470544631795785, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'destination': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/bounded_fifo_cleanup_ack_v1.py', 'expected_preimage_sha256': None, 'new_destination_must_be_proven_absent_before_install': True, 'actual_preimage': None, 'actual_installed_pin': None}, {'source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fleet-wide-multiple-reconnect-overlap-quarantine-original01-20261031/future-Main-RPC-backpressure-source-only-original01/main_rpc_backpressure120_v1.lua', 'sha256': 'bc7df0d6ca18da11cd6498867a5b77e3638d8b721094264f056fe6a949d75f76', 'bytes': 174496, 'identity': {'device': 2304, 'inode': 82724466, 'bytes': 174496, 'mtime_ns': 1793469559512328719, 'ctime_ns': 1793469559513140274, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'destination': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/main.lua', 'expected_preimage_sha256': '2d478f7f5f8b7d954dcb22367b1367ac82c8d88d66762657df16e4a72b242b83', 'new_destination_must_be_proven_absent_before_install': False, 'actual_preimage': None, 'actual_installed_pin': None}, {'source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-learner-CUDA-diagnostic-timing-API-source-only-original01-20261031/selected-source/training.py', 'sha256': '8cd1e1399c8313c4b9b0465142a72273ffcbb0e1a9053c4c3c9590493f110fe0', 'bytes': 35521, 'identity': {'device': 2304, 'inode': 82728916, 'bytes': 35521, 'mtime_ns': 1793473337287700540, 'ctime_ns': 1793473337287700540, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'destination': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/training.py', 'expected_preimage_sha256': '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4', 'new_destination_must_be_proven_absent_before_install': False, 'actual_preimage': None, 'actual_installed_pin': None}, {'source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-learner-CUDA-diagnostic-timing-API-source-only-original01-20261031/composed-dashboard-cache-source-only-original01/metrics_dashboard.py', 'sha256': '9b133ae93eb199ab6b9dc834d7e3879c4f4de2d42dcf07eda1e51b88a8ba2403', 'bytes': 250973, 'identity': {'device': 2304, 'inode': 82732028, 'bytes': 250973, 'mtime_ns': 1793473934483712298, 'ctime_ns': 1793473934484225643, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'destination': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/metrics_dashboard.py', 'expected_preimage_sha256': 'b36ad5ceb8c0cb389e942018233c8a6ddbd0723b7cfb63d7958f5e97ee6f0b38', 'new_destination_must_be_proven_absent_before_install': False, 'actual_preimage': None, 'actual_installed_pin': None}]
CPU_SHA='c608a2ce35263a07b064111a34606ed3c6d9a54f35334f1fa80620a766a2f21d'
STATE_SHA='06083be0404682c192d4feb61259827485a9b5c4ffd5a05a611dd08bf3878a5b'
BACKUP_SOURCE_SHA='80e743771abf28ba839e6ee5d9bf8079fa13bf3ab29a0897bb2501c757a4bb8f'

def require(value,message):
    if not value:raise ValueError(message)

def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)

def read(path,*,expected=None,immutable=False,limit=8<<20):
    path=Path(path);before=path.lstat()
    require(path.is_absolute()and path.resolve()==path and stat.S_ISREG(before.st_mode)and before.st_uid==1001 and before.st_nlink==1 and 0<before.st_size<=limit,'Canonical owned bounded source/metadata required')
    if immutable:require(stat.S_IMODE(before.st_mode)==0o444,'Immutable selected source/metadata required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(fd))==identity(before),'Read identity changed on open')
        with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(limit+1)
        require(identity(os.fstat(fd))==identity(before),'Read identity changed')
    finally:os.close(fd)
    require(identity(path.lstat())==identity(before)and len(raw)==before.st_size,'Read path/size changed')
    pin=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))
    if expected is not None:require(pin==expected,'Selected source/metadata full8 differs')
    return pin,raw

def directory_sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def save(path,value,mode=0o444):
    raw=value if type(value)is bytes else(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False)as stream:stream.write(raw);stream.flush();os.fchmod(fd,mode);os.fsync(fd)
    finally:os.close(fd)
    directory_sync(path.parent)
    return read(path)[0]

def absent(pid,born):
    require(type(pid)is int and type(born)is int and pid>1 and born>0,'Typed original PID/birth required')
    try:current=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:current=None
    require(current!=born,'Original Main/fleet/backup process still present')
    return dict(pid=pid,expected_birth=born,observed_birth=current,original_birth_absent=True)

def no_helper(path):
    require(path.parent.resolve()==path.parent,'Canonical source parent required')
    try:path.lstat()
    except FileNotFoundError:return
    raise ValueError('New ACK helper target unexpectedly exists; never overwrite/adopt it')

def install(args):
    require(os.getuid()==1001,'Exact source owner required')
    own,_=read(Path(__file__).resolve(),immutable=True);require(own['sha256']==args.expected_source_sha256,'Exact frozen installer required')
    manifest_pin,raw=read(args.backup_manifest,immutable=True);require(manifest_pin['sha256']==args.backup_manifest_sha256,'Exact actual full-backup manifest SHA required');manifest=json.loads(raw)
    closed_pin,raw=read(args.Root_closed_backup,immutable=True);require(closed_pin['sha256']==args.Root_closed_backup_sha256,'Exact Root closed-backup proof SHA required');closed=json.loads(raw)
    require(manifest['schema']=='robotron-verified-stopped-full-training-backup-v1'and manifest['status']=='COMPLETE_STREAM_HASHED_AND_FSYNCED'and manifest['source']['sha256']==BACKUP_SOURCE_SHA and manifest['strict_CPU_report']['sha256']==CPU_SHA and manifest['restoration_manifest']['sha256']==STATE_SHA,'Only actual qualified current-A2 complete full backup required')
    for key in('full_ring_states_and_next_states_streamed_and_hashed','all_selected_bank_generation_fields_copied','all_files_independent_single_link_readonly','no_sources_written_or_chmodded'):require(manifest[key]is True,'Incomplete full-state backup coverage')
    files=manifest['files'];require(type(files)is list and files and len({v['relative']for v in files})==len(files),'Unique complete backup file inventory required')
    require(sum(v['bytes_copied']for v in files)==manifest['total_bytes']and len([v for v in files if v['relative'].startswith('ring/')and v['relative']!='ring/_meta.npy'])==10,'Complete ring/byte accounting required')
    for name in('hof','ephof'):
        rows=[v for v in files if v['relative'].startswith('banks/'+name+'/')];require(len(rows)==10 and any(v['relative']=='banks/'+name+'/CURRENT.json'for v in rows),'Complete selected bank inventory required')
        for field in('states','next_states','actions','rewards','dones','horizons','is_expert','actor_kind'):require(sum(v['relative'].endswith('/'+name+'_'+field+'.npy')for v in rows)==1,'All eight full bank fields required')
    for value in files:
        require(value['complete']is value['fsync_completed']is True and type(value['bytes_copied'])is int and value['bytes_copied']>=0 and value['bytes_copied']==value['source_identity_before']['bytes']==value['destination_identity']['bytes']and value['source_identity_before']==value['source_identity_after']and value['destination_identity']['mode']=='0o444'and value['destination_identity']['nlink']==1 and(value['source_identity_before']['device'],value['source_identity_before']['inode'])!=(value['destination_identity']['device'],value['destination_identity']['inode'])and re.fullmatch('[0-9a-f]{64}',value['stream_sha256']),'Incomplete/unfsynced/nonindependent backup entry')
        if value['expected_source_sha256']is not None:require(value['stream_sha256']==value['expected_source_sha256'],'Backup expected source SHA mismatch')
    require(closed['schema']=='robotron-Root-original-fullstate-backup-positive-closeout-v1'and closed['backup_manifest']==manifest_pin and type(closed['actual_exit'])is int and closed['actual_exit']==0,'Exact actual original-backup normal0 closure required')
    for key in('original_tool_terminal0_confirmed','all_original_backup_processes_absent','all_original_backup_units_released','all_original_backup_cgroups_empty'):require(closed[key]is True,'Root original-backup positive closure acknowledgement required')
    owner=closed['original_owner'];scope=manifest['actual_scope'];require(scope['Id']==owner['unit']and scope['MainPID']==str(owner['pid'])and scope['InvocationID']==owner['invocation_id'],'Original backup owner/manifest scope differs')
    originals=[(208501,27823352),(965562,30270092),(owner['pid'],owner['starttime_ticks'])];absence_before=[absent(*v)for v in originals]
    operator_pin,raw=read(OPERATOR['path'],expected=OPERATOR,immutable=True);tree=ast.parse(raw)
    catalogues=[ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='INSTALLED_SHA'for t in n.targets)];require(len(catalogues)==1 and len(catalogues[0])==14,'Exact fourteen-entry held-startup catalogue required');catalogue=catalogues[0]
    staged=[];oldpins={};expected_targets={v['destination']for v in INSTALL};unchanged={}
    require(len(INSTALL)==len(expected_targets)==5,'Exact five source targets required')
    for item in INSTALL:
        source_pin,data=read(item['source']['path'],expected=item['source'],immutable=True);target=Path(item['destination']);require(catalogue[str(target)]==source_pin['sha256'],'Private source/catalogue differs')
        if item['new_destination_must_be_proven_absent_before_install']:no_helper(target);prior=None;preimage=None
        else:
            prior,preimage=read(target);require(prior['sha256']==item['expected_preimage_sha256'],'Exact unchanged canonical preimage required');oldpins[str(target)]=prior
        staged.append((target,data,source_pin,prior,preimage))
    for path,sha in catalogue.items():
        if path not in expected_targets:
            selected,_=read(path);require(selected['sha256']==sha,'Unchanged catalogue source differs');unchanged[path]=selected
    output=args.output.absolute();require(output.parent==HERE and output.resolve()==output and not output.exists(),'Fresh direct-child installation evidence directory required')
    output.mkdir(mode=0o700);preimages={};installed=[];attempted=[]
    try:
        for target,data,source_pin,prior,preimage in staged:
            if prior is not None:preimages[str(target)]=dict(original=prior,preserved=save(output/(target.name+'.before.exact'),preimage))
        save(output/'preflight-and-preimages.json',dict(source=own,backup_manifest=manifest_pin,Root_closed_backup=closed_pin,original_absence=absence_before,preimages=preimages,new_helper_proven_absent=True,private_sources=[v[2]for v in staged],unchanged_catalogue=unchanged))
        for target,data,source_pin,prior,preimage in staged:
            read(source_pin['path'],expected=source_pin,immutable=True)
            if prior is None:no_helper(target)
            else:read(target,expected=prior)
        for value in unchanged.values():read(value['path'],expected=value)
        for target,data,source_pin,prior,preimage in staged:
            attempted.append(str(target))
            absence=[absent(*v)for v in originals];temporary=target.with_name('.'+target.name+'.Root-A2-source-repair-'+str(os.getpid())+'.tmp')
            if prior is None:no_helper(target)
            else:read(target,expected=prior)
            mode=int(prior['identity']['mode'],8)if prior is not None else 0o664;save(temporary,data,mode)
            if prior is None:os.link(temporary,target,follow_symlinks=False);os.unlink(temporary)  # Exclusive new name; never overwrite an unexpected helper.
            else:os.replace(temporary,target)
            directory_sync(target.parent);fresh,_=read(target);require(fresh['sha256']==source_pin['sha256'],'Installed source hash differs');installed.append(fresh);save(output/('%02d-installed.json'%len(installed)),dict(target=fresh,private_source=source_pin,absence_before_replace=absence))
        fresh_catalogue=[]
        for path,sha in catalogue.items():
            value,_=read(path);require(value['sha256']==sha,'Final installed catalogue SHA differs');fresh_catalogue.append(value)
        for pin in(manifest_pin,closed_pin,operator_pin,own):read(pin['path'],expected=pin,immutable=True)
        for path,pin in unchanged.items():read(path,expected=pin)
        return save(output/'installation-receipt.json',dict(schema='robotron-Root-exact-five-repair-source-installation-v1',status='EXACT_FIVE_SOURCES_INSTALLED_AND_FSYNCED',source=own,backup_manifest=manifest_pin,Root_closed_backup=closed_pin,operator=operator_pin,preimages=preimages,installed=installed,source_pins=fresh_catalogue,original_absence_after=[absent(*v)for v in originals],observed_unix_s=time.time(),model_replay_control_or_service_actions=False,runtime_or_held_restore_qualified=False))
    except BaseException as error:
        save(output/'installation-failure-preserved.json',dict(status='FAILED_PARTIAL_INSTALLATION_RETAINED',error=repr(error),attempted_targets=attempted,verified_installed=installed,preimages=preimages,automatic_rollback_or_cleanup=False));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--install',action='store_true');parser.add_argument('--expected-source-sha256')
    parser.add_argument('--backup-manifest',type=Path);parser.add_argument('--backup-manifest-sha256');parser.add_argument('--Root-closed-backup',type=Path);parser.add_argument('--Root-closed-backup-sha256');parser.add_argument('--output',type=Path,default=HERE/'actual-five-source-install-original01');args=parser.parse_args()
    if args.install:print(json.dumps(install(args)),flush=True)
    else:print('PLAN_ONLY_NO_READS_WRITES_OR_ACTIONS')
