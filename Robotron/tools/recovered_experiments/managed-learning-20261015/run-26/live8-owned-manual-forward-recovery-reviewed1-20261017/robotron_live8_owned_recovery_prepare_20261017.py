#!/usr/bin/env python3
"""Root manual forward recovery preparation; no source/control/trainer writes."""
import importlib.util,json,os,subprocess,sys
from pathlib import Path
REPO=Path('/home/dave/source/repos/ArcadeAI');GAME=REPO/'Robotron';RUN=GAME/'logs/managed-learning-20261015/run-26'
D=RUN/'live8-owned-manual-forward-recovery-reviewed1-20261017'
CONTROLLER=GAME/'tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/live8_maintenance_proposal/revision3/run_live8_maintenance.py'
def main():
    sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('root_manual_forward_recovery',CONTROLLER);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    j=json.loads((RUN/'live8-owned-maintenance-root-preparation-reviewed3-20261017/root-job.json').read_text())
    insurance=m.read_json(j['insurance_verification']);old=insurance['root_job']['insurance']['trainer']
    show=subprocess.run(['systemctl','--user','show',j['trainer_unit'],'-p','MainPID','-p','ActiveState','-p','SubState','-p','Result'],capture_output=True,text=True,check=True,timeout=5).stdout
    assert 'MainPID=0' in show and 'ActiveState=inactive' in show,show
    assert not Path('/proc',str(old['pid'])).exists()
    cgroup=Path('/sys/fs/cgroup')/old['cgroup'].lstrip('/')
    assert not cgroup.exists() or not any(p.read_text().split() for p in cgroup.rglob('cgroup.procs'))
    assert not Path(j['original_dropin']['path']).exists()
    for entry in j['sources']:
        dest=Path(entry['destination'])
        assert (m.fingerprint(dest)['sha256']==entry['before']['sha256']) if entry['before'] else not dest.exists()
    for path,expected in j['before']['bindings']['source_hashes'].items():assert m.fingerprint(path)['sha256']==expected,path
    for path,expected in j['before']['bindings']['control_hashes'].items():assert m.fingerprint(path)['sha256']==expected,path
    python_proof=m.validate_python_binding(j['verifier'],j['insurance_verification'],hash_executable=True)
    D.mkdir(mode=0o700)
    m.publish(D/'root-python-proof.json',python_proof)
    (D/'trainer-inactive-show.txt').write_text(show)
    source,copied=m.exclusive_copy(Path(j['model_dir'])/'robotron_dqn_latest.pt',D/'latest-readonly-copy.pt')
    absent=m.publish(D/'absence.json',dict(schema='robotron-live8-owned-trainer-absence-v1',trainer=old,unit_main_pid=0,unit_active_state='inactive',old_process_absent=True,owned_cgroup_empty=True,latest_path=source['path']))
    job=dict(schema='robotron-live8-maintenance-checkpoint-CPU-job-v1',mode='stopped_latest',verifier_sha256=j['verifier']['script']['sha256'],experiment=j['experiment'],source=source,verification_copy=copied,
             clock_floor={key:insurance['clocks'][key] for key in m.CLOCKS},source_control_context=j['verifier']['context'],output_directory=str(D/'cpu-output'),
             stopped_latest=dict(old_trainer=old,absence_receipt=absent,insurance_verification=j['insurance_verification']))
    record=m.publish(D/'cpu-job.json',job)
    script=j['verifier']['script'];argv=[j['verifier']['python'],'-Xgil=0','-I','-B',script['path'],'--execute','--job',record['path'],'--expected-job-sha256',record['sha256'],'--expected-verifier-sha256',script['sha256']]
    command=['systemd-run','--user','--unit=robotron-live8-owned-recovery-CPU-reviewed1-20261017.service','--property=Type=exec','--property=RemainAfterExit=yes','--property=CPUQuota=200%','--property=MemoryMax=3G',
             '--property=MemorySwapMax=0','--property=TasksMax=64','--property=RuntimeMaxSec=120','--property=TimeoutStopSec=5','--property=WorkingDirectory='+str(REPO),
             '--property=StandardOutput=append:'+str(D/'cpu.stdout'),'--property=StandardError=append:'+str(D/'cpu.stderr'),'/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH',
             'CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2',*argv]
    m.publish(D/'root-CPU-launch-intent.json',dict(argv=command,checkpoint=source,actions='CPU verification only; no trainer start or source writes',ordinary_stop_primary_failure_preserved=True))
    result=subprocess.run(command,capture_output=True,text=True,timeout=15)
    m.publish(D/'root-CPU-launch-return.json',dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr));assert result.returncode==0,result.stderr
    print(json.dumps(dict(CPU_verification_launched=True,checkpoint_sha256=source['sha256'],job_sha256=record['sha256'])))
if __name__=='__main__':main()
