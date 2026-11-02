"""Explicit post-backup queue install and fresh held-startup preparation."""
import argparse, hashlib, importlib.util, json, os
from pathlib import Path
import stat, subprocess, sys
from types import SimpleNamespace

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
R=B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101'
OLD=B/'post-engineering-fullstate-preservation-original03-20261101'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def identity(p):
    s=p.lstat();assert stat.S_ISREG(s.st_mode) and not p.is_symlink()
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');a=parser.parse_args()
    if not a.prepare:print('PLAN_ONLY');return
    header=R/'sources/prepare_current_continuous_preservation_header_v3.py'
    assert hashlib.sha256(header.read_bytes()).hexdigest()=='a9c4dd88a6520b43fc57f4afac1e40b5622f43a9394d352927441050536cc2bc'
    h=load('_queue8192RestorationHeader',header);pin=lambda p:h.metadata(p)[0]
    read=lambda p:h.read(pin(p));packet=read(R/'prepared-current-source-family.json')
    backup=read(R/'full-backup-original01/backup-manifest.json')
    assert backup['status']=='COMPLETE_COMPRESSED_DECOMPRESSED_READBACK_HASHED_AND_FSYNCED'
    assert backup['destination_payload_reread_hash_performed'] is True
    b=h.load('backup');archive=b.load(b.ARCHIVE,b.ARCHIVE_SHA,'_queue8192RestorationArchive')
    for stem in ['stopped-CPU-original01','backup-preparation-original02']:
        receipt=read(R/stem/'original-scope-result-and-positive-owned-closeout.json')
        assert receipt['actual_exit']==0 and receipt['original_Popen_reaped'] is True
        assert receipt['all_original_controller_resources_closed'] is True
        owner=h.read(receipt['owner']);close=h.read(receipt['closure'])
        archive.archived_closure(close,owner,b.read_pin,exit_zero=True)
        b.absent(owner['pid'],owner['starttime_ticks'])
        group=Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')/owner['unit']
        assert not group.exists()
    for u in ['robotron-trainer.service','robotron-mame.service']:
        values=dict(x.split('=',1) for x in subprocess.check_output(['systemctl','--user','show',u,'-p','MainPID','-p','ActiveState','-p','ExecMainStatus'],text=True).splitlines())
        assert values==dict(MainPID='0',ExecMainStatus='0',ActiveState='inactive')
    # The bounded backup has independently decompressed and hashed every file.
    # Check its immutable inventory against current sources and destinations.
    entries=backup['files']
    assert len(entries)==73 and sum(e['bytes_copied'] for e in entries)==328827873243
    for e in entries:
        assert e['complete'] is True and e['fsync_completed'] is True
        assert e['destination_payload_reread_hash_performed'] is True
        assert e['independent_decompressed_bytes']==e['bytes_copied']
        assert e['independent_decompressed_sha256']==e['stream_sha256']
        assert e['independent_compressed_bytes']==e['compressed_bytes']
        assert e['independent_compressed_sha256']==e['compressed_sha256']
        assert identity(Path(e['source']))==e['source_identity_before']==e['source_identity_after']
        assert identity(Path(e['destination']))==e['destination_identity']
    output=R/'post-backup-startup-metadata-original01';assert not output.exists();output.mkdir(mode=0o700)
    target=G/'Scripts/dqn/socket_server.py';before=target.read_bytes()
    assert hashlib.sha256(before).hexdigest()=='1692ee2dbfb6f83d0f50234ee1eb30d0cf6bbe45d670a5a9fb52992fd92b56fc'
    staged=Path(packet['staged_socket_server']['path']);after=staged.read_bytes()
    assert hashlib.sha256(after).hexdigest()==packet['prospective_installed_sha'][str(target)]
    assert after==before.replace(b'AsyncReplayBuffer(agent)',b'AsyncReplayBuffer(agent, max_queue_size=8192)',1)
    oldpin=h.put(output/'socket_server.preimage.py',before)
    temp=target.with_name('socket_server.queue8192.tmp')
    with temp.open('xb') as f:
        f.write(after);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
    assert target.read_bytes()==before;os.replace(temp,target)
    fd=os.open(target.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    installed=[pin(Path(p)) for p in packet['prospective_installed_sha']]
    assert {v['path']:v['sha256']for v in installed}==packet['prospective_installed_sha']
    manifest=read(R/'stopped-CPU-original01/runtime/restoration-manifest.json')
    report=pin(R/'stopped-CPU-original01/runtime/cpu-verification.json');manifestpin=pin(R/'stopped-CPU-original01/runtime/restoration-manifest.json')
    assert backup['restoration_manifest']==manifestpin and backup['strict_CPU_report']==report
    phase=manifest['priority_metric_phase'];checkpoint=manifest['checkpoint']
    resume=h.put(output/('resume-'+checkpoint['sha256']+'.json'),dict(schema='robotron-priority-metric-start-v1',
        phase_id=phase['phase_id'],metric='ce',action='resume',previous_metric='ce',
        checkpoint={k:checkpoint[k]for k in ['path','sha256','bytes']},model_dir=str(G/'models_dqn'),
        root_precommit_sha256=phase['root_precommit_sha256']))
    authority=h.put(output/'actual-stopped-state-startup-authority.json',dict(
        schema='robotron-root-closed-stopped-full-state-startup-authority-v1',CPU_report=report,
        restoration_manifest=manifestpin,original_CPU_exit=0,all_original_CPU_resources_closed=True,
        old_trainer_and_population_closed=True,
        original_CPU_closure=pin(R/'stopped-CPU-original01/execution-original01/root-original-result-and-owned-release.json'),
        original_CPU_owner=pin(R/'stopped-CPU-original01/execution-original01/root-original-identity.json'),
        stopped_authority=manifest['stopped_authority'],complete_backup=pin(R/'full-backup-original01/backup-manifest.json'),
        prior_power_recovery_replay_gap_preserved_in_history=True,uninterrupted_RNG_or_MAME_state_claimed=False))
    selection=h.put(output/'startup-selection.json',dict(schema='robotron-root-continuous-startup-hold-selection-v1',
        unit='robotron-trainer.service',expected_startup_cap=8,restoration_manifest=manifestpin,
        stopped_CPU_report=report,stopped_state_authority=authority,checkpoint=checkpoint,resume_record=resume,
        source_pins=installed,output_directory=str(R/'post-backup-startup-held-original01')))
    operator=load('_queue8192RestorationOperator',packet['startup_operator']['path'])
    assert pin(Path(packet['startup_operator']['path']))==packet['startup_operator']
    operator.prepare_job(SimpleNamespace(expected_source_sha256=packet['startup_operator']['sha256'],
        selection=selection['path'],selection_sha256=selection['sha256'],output=str(output/'startup-job.json')))
    job=pin(output/'startup-job.json')
    oldjob=read(OLD/'post-backup-startup-metadata-original01/startup-job.json')
    override=Path('/home/dave/.config/systemd/user/robotron-trainer.service.d/99-post-engineering-preservation.conf').read_bytes()
    text=override.decode().replace(str(OLD),str(R)).replace(oldjob['checkpoint']['sha256'],checkpoint['sha256'])
    text=text.replace(pin(OLD/'post-backup-startup-metadata-original01/startup-job.json')['sha256'],job['sha256'])
    text=text.replace(oldjob['resume_record']['sha256'],resume['sha256'])
    review=h.put(output/'zz-queue8192-preservation.conf.REVIEW-NOT-INSTALLED',text.encode())
    h.put(output/'PREPARED_NOT_LAUNCHED.json',dict(status='QUEUE8192_INSTALLED_FRESH_HELD_STARTUP_PREPARED_NOT_LAUNCHED',
        job=job,override_review=review,old_socket_source_preimage=oldpin,new_installed_server=pin(target),
        exact_full_backup=pin(R/'full-backup-original01/backup-manifest.json'),scientific_job=False,promotion=False))
    print(json.dumps(dict(status='PREPARED_NOT_LAUNCHED',job={k:job[k]for k in ['path','sha256','bytes']},override=review['path'])))

if __name__=='__main__':main()
