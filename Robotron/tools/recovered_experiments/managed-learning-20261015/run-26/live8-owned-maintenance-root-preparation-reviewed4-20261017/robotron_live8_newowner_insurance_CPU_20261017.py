#!/usr/bin/env python3
"""New current-owner insurance: one CPU verification, original exit retained."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,stat,subprocess
ROOT=Path('/home/dave/source/repos/ArcadeAI');GAME=ROOT/'Robotron';RUN=GAME/'logs/managed-learning-20261015/run-26'
VERIFIER=RUN/'live8-maintenance-checkpoint-CPU-verifier-proposal-20261017/verify_maintenance_checkpoint.py'
VSHA='7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
UNIT='robotron-live8-newowner-insurance-CPU-20261017.service'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pin(p):
    p=Path(p);assert p.is_absolute() and p==p.resolve(strict=True)
    s=p.lstat();assert stat.S_ISREG(s.st_mode)
    identity=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    digest=sha(p);after=p.lstat();assert all(getattr(after,key)==getattr(s,key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_nlink'))
    return dict(path=str(p),sha256=digest,bytes=s.st_size,identity=identity)
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
def call(*argv):return subprocess.run(list(argv),capture_output=True,text=True,timeout=15,check=True)
def prepare_and_launch(i):
    assert sha(VERIFIER)==VSHA;assert i.parent==RUN and i.name.startswith('live8-insurance-')
    receipt=json.loads((i/'saved-insurance-receipt.json').read_text());assert receipt['trainer']['pid']==4098959 and receipt['trainer']['starttime_ticks']==31468656
    trigger=json.loads((i/'main-before.json').read_text());assert trigger['host_pipeline']['learning_exposure']['optimizer']['process_id']==4098959
    assert json.loads((GAME/'models_dqn/managed_save.request.json.completed').read_text())==dict(tag=receipt['tag']);assert not (GAME/'models_dqn/managed_save.request.json').exists()
    props=dict(line.split('=',1) for line in call('systemctl','--user','show',receipt['trainer']['unit']).stdout.splitlines() if '=' in line)
    assert props['MainPID']=='4098959' and props['InvocationID']==receipt['trainer']['invocation_id'] and props['ActiveState']=='active'
    j=i/'CPU-root-preparation';e=i/'CPU-root-execution';j.mkdir();e.mkdir();(e/'private-tmp').mkdir()
    (j/'trainer-unit-show.txt').write_text(call('systemctl','--user','show',receipt['trainer']['unit']).stdout)
    (j/'trainer-unit-cat.txt').write_text(call('systemctl','--user','cat',receipt['trainer']['unit']).stdout)
    (j/'archived-learning-control.json').write_bytes((GAME/'models_dqn/learning_control.json').read_bytes())
    # The unchanged strict recipe is copied from its actual earlier CPU proof;
    # current source/control/unit pins and new acquisition provenance are fresh.
    previous=json.loads((RUN/'live8-insurance-CPU-root-preparation-reviewed1-20261017/root-job.json').read_text())
    context=dict(game_root=str(GAME),model_dir=str(GAME/'models_dqn'),model_package={name:pin(GAME/'Scripts/dqn'/name) for name in ('model.py','config.py','learning_control.py','__init__.py')},
                 archived_control=pin(j/'archived-learning-control.json'),archived_trainer_unit=pin(j/'trainer-unit-cat.txt'),
                 provenance=[pin(p) for p in [i/'precommit.json',i/'saved-insurance-receipt.json',i/'matching-completed-request.json',i/'root-controller-at-request.py',i/'root-controller-at-completion.py',j/'trainer-unit-show.txt',RUN/'live8-maintenance-checkpoint-CPU-verifier-proposal-20261017/preparation-manifest.json',RUN/'live8-recovery-and-next-loop-root-review-20261017/root-continuation-receipt.json']],
                 held_recipe_context=previous['source_control_context']['held_recipe_context'])
    output=i/'insurance-CPU-verification-v4-window-20261017'
    job=dict(schema='robotron-live8-maintenance-checkpoint-CPU-job-v1',mode='insurance',verifier_sha256=VSHA,experiment='best10M-fresh3-eps10-cap8-nosmooth',source=pin(Path(receipt['source']['path'])),verification_copy=pin(Path(receipt['copy']['path'])),
             clock_floor={key:trigger[key] for key in ('training_steps','optimized_samples','learner_frame_count','frame_count')},source_control_context=context,output_directory=str(output),
             insurance=dict(tag=receipt['tag'],trainer=receipt['trainer'],trigger_snapshot=pin(i/'main-before.json'),completed_request=pin(GAME/'models_dqn/managed_save.request.json.completed')))
    assert job['source']['sha256']==job['verification_copy']['sha256']==receipt['source']['sha256'];assert job['source']['bytes']==receipt['source']['bytes']
    save(j/'root-job.json',job)
    argv=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2',str(ROOT/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B','-u',str(VERIFIER),'--execute','--job',str(j/'root-job.json'),'--expected-job-sha256',sha(j/'root-job.json'),'--expected-verifier-sha256',VSHA]
    command=['systemd-run','--user','--unit='+UNIT,'--property=Type=exec','--property=WorkingDirectory='+str(ROOT),'--property=CPUQuota=200%','--property=MemoryMax=3G','--property=MemorySwapMax=0','--property=TasksMax=64','--property=RuntimeMaxSec=120','--property=TimeoutStopSec=5','--property=RemainAfterExit=yes','--property=Restart=no','--property=Environment=TMPDIR='+str(e/'private-tmp'),'--property=StandardOutput=append:'+str(e/'stdout'),'--property=StandardError=append:'+str(e/'stderr'),*argv]
    save(e/'execution-precommit.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),kind='insurance',unit=UNIT,argv=command,root_controller_sha256=sha(__file__),test_methods=0,main_actions=False))
    r=call(*command);save(e/'scheduling-result.json',dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));print(json.dumps(dict(CPU_launched=True,directory=str(i),job_sha256=sha(j/'root-job.json'))))
def complete(i):
    e=i/'CPU-root-execution';show=call('systemctl','--user','show',UNIT).stdout;props=dict(line.split('=',1) for line in show.splitlines() if '=' in line)
    assert props['SubState'] in ('exited','failed') and props['ExecMainCode']=='1'
    (e/'original-terminal-show.txt').write_text(show);(e/'original-terminal-cat.txt').write_text(call('systemctl','--user','cat',UNIT).stdout);(e/'original-invocation-journal.txt').write_text(call('journalctl','--user','_SYSTEMD_INVOCATION_ID='+props['InvocationID'],'--no-pager').stdout)
    save(e/'original-execution-completion.json',dict(original_invocation=props['InvocationID'],original_pid=int(props['ExecMainPID']),original_exec_code=int(props['ExecMainCode']),original_exit=int(props['ExecMainStatus']),result=props['Result'],unit_released=False))
    assert props['ExecMainStatus']=='0' and props['Result']=='success','First CPU verification failed; do not rerun'
    report=i/'insurance-CPU-verification-v4-window-20261017/cpu-verification.json';v=json.loads(report.read_text());receipt=json.loads((i/'saved-insurance-receipt.json').read_text());assert v['status']=='PASS' and v['mode']=='insurance' and not v['actual_restore_or_optimizer_step'];assert v['sha256']==receipt['source']['sha256'] and v['bytes']==receipt['source']['bytes'];assert v['runtime']['CUDA_VISIBLE_DEVICES']==''
    call('systemctl','--user','stop',UNIT)
    save(e/'root-result-review-and-release.json',dict(status='PASS',kind='insurance',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),original_invocation=props['InvocationID'],original_pid=int(props['ExecMainPID']),original_exec_code=1,original_exit=0,original_result='success',original_archived_before_release=True,unit_stop_returncode=0,numeric_report=str(report),numeric_report_sha256=sha(report),clocks=v['clocks'],main_actions=False))
    print(json.dumps(dict(status='PASS',report=str(report),sha256=sha(report),clocks=v['clocks'])))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['launch','complete']);parser.add_argument('--directory',type=Path,required=True);a=parser.parse_args();i=a.directory.resolve(strict=True);(prepare_and_launch if a.action=='launch' else complete)(i)
