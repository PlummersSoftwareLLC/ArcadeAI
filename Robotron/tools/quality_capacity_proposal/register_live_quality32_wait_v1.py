"""Register one fresh verified live original monitor report in canonical metadata.

Default is inert. This never starts/stops a service, alters a scientific input,
qualifies a result, captures a model or changes a protected policy. Reusable with
fresh, distinct registered root-monitor reports; each prior state is retained.
"""
import argparse,copy,hashlib,json,os,re,stat,subprocess,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';STATE=R.parent/'state.json'


def require(v,message):
    if not v:raise ValueError(message)


def pin(path):
    path=Path(path)
    def identity(s):return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    before=identity(path.stat());raw=path.read_bytes();require(identity(path.stat())==before,'File changed during read')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)


def read(entry):
    observed=pin(entry['path']);require(observed==entry and observed['identity']['mode']=='0o444' and observed['identity']['uid']==os.getuid() and observed['identity']['nlink']==1,'Full immutable artifact identity differs')
    return json.loads(Path(entry['path']).read_bytes())


def encode(value):return(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()


def archive(path,raw):
    with path.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
    return pin(path)


def live(owner):
    path=Path('/proc',str(owner['pid']),'stat');first=path.read_text().rsplit(')',1)[1].split();require(first[0]not in ('Z','X','x') and int(first[19])==owner['starttime_ticks'],'Original process birth changed')
    result=subprocess.run(['systemctl','--user','show',owner['unit']],capture_output=True,text=True,timeout=10);require(result.returncode==0,'Original unit observation failed')
    fields=dict(line.split('=',1)for line in result.stdout.splitlines()if '='in line)
    expected=dict(Id=owner['unit'],MainPID=str(owner['pid']),InvocationID=owner['invocation_id'],NRestarts='0',ActiveState='active',SubState='running',ControlGroup=owner['cgroup'])
    require(all(fields.get(k)==v for k,v in expected.items()),'Original controller owner/unit/invocation changed')
    last=path.read_text().rsplit(')',1)[1].split();require(last[0]not in ('Z','X','x') and int(last[19])==owner['starttime_ticks'],'Original controller changed during observation')


def register(report_path,expected_sha):
    raw=STATE.read_bytes();state=json.loads(raw);goal=state['optimization_goal'];job=state['active_quality_job'];Q=Path(job['preparation']);report_path=Path(report_path)
    require(report_path.is_absolute() and report_path.resolve()==report_path and report_path.parent==Q/'root-live-monitor' and re.fullmatch(r'\d+-report\.json',report_path.name),'Actual registered original monitor report path required')
    report_pin=pin(report_path);require(report_pin['sha256']==expected_sha,'Exact original report SHA required');report=read(report_pin)
    require(report['classification']=='LIVE_SUPERVISED_QUALITY32_PREFIX_VERIFIED' and 0<=time.time()-report['unix_s']<=30 and report['campaign_state']=='running','Fresh live original quality report required')
    require(report['main']['client_count']==192 and report['quality_qualified'] is False and report['scientific_approval_inferred'] is False and report['main_or_private_runtime_changed'] is False,'Live monitor scope differs')
    owners=report['original_owners'];require(len(owners)==2 and all(x['live']for x in owners),'Both original controllers must be live')
    expected_owners=[read(job[k])for k in ['original_native_owner','original_outer_owner']]
    require([x['original']for x in owners]==expected_owners,'Report substituted an original controller')
    for owner in expected_owners:live(owner)
    index=report['current_leg'];labels={1:'R1',2:'C1',3:'R2',4:'C2'};require(type(index)is int and index in labels,'Original four-leg index required')
    current=next((x for x in report['legs']if x['index']==index),None);require(current is not None and current['role']==('reference'if index in (1,3)else 'candidate'),'Current original leg role differs')
    protected=copy.deepcopy({k:state[k]for k in ['incumbent','incumbent_history','last_closed_quality_job','fixed','next_checkpoint','state_history_archives']});reference=copy.deepcopy(goal['current_fixed_reference_policy']);main_binding=copy.deepcopy(goal['current_main_binding']);command=copy.deepcopy(goal['current_main_monitor_command'])
    backup=archive(Q/('state-before-registered-wait-'+report_path.stem+'.raw.json'),raw)
    leg=labels[index];phase=current.get('phase')or'starting';safe_phase=phase if re.fullmatch(r'[a-z_]+',phase)else'observing'
    for active in [state['active_quality_job'],goal['active_quality_job']]:active.update(current_leg=index,phase=leg+'_'+safe_phase)
    goal.update(current_campaign_leg=index,current_leg=index,current_campaign_phase=leg+'_'+safe_phase,current_phase='profile06_reference1597_vs_production1741_original_'+leg.lower()+'_'+safe_phase)
    state['stage']='PROFILE06_REFERENCE1597_VS_PRODUCTION1741_ORIGINAL_'+leg+'_'+safe_phase.upper();goal['stage']=state['stage']
    goal['previous_goal_turn_classification']=goal.get('latest_goal_turn_classification');goal['latest_goal_turn_classification']='verified wait'
    goal['last_verified_wait']=dict(observed_unix_s=report['unix_s'],same_originals_live=True,receipt=report_pin,main_clients=192,current_leg=index,verified_current_private_births=current.get('verified_actor_births'),previous_state_backup=backup)
    goal['actual_running_wait'].update(kind='same_original_quality32_'+leg+'_live_and_main192_training',observed_unix_s=report['unix_s'],confirmed_live_now=True,monitor_observation=report_pin,live_main_learner_frames=report['main']['learner_frame_count'],current_leg=index,current_cohort_snapshot=current.get('counts'))
    if index==1:goal['actual_running_wait']['current_R1_snapshot']=current.get('counts')
    goal['last_updated_unix_s']=time.time();state['updated_unix_s']=goal['last_updated_unix_s']
    require(protected=={k:state[k]for k in protected} and reference==goal['current_fixed_reference_policy'] and main_binding==goal['current_main_binding'] and command==goal['current_main_monitor_command'],'Protected policy/current scientific bindings changed')
    data=encode(state);require(len(data)<1<<20 and STATE.read_bytes()==raw,'Canonical state limit or compare-and-swap failed')
    tmp=STATE.with_name('.state-register-live-'+report_path.stem+'.tmp')
    with tmp.open('xb')as f:f.write(data);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o664)
    os.replace(tmp,STATE);fd=os.open(STATE.parent,os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    print(json.dumps(dict(classification='verified wait',current_leg=leg,current_phase=phase,counts=current.get('counts'),main=report['main'],original_monitor_report=report_pin,prior_state_backup=backup,state_bytes=len(data),scientific_runtime_changed=False)))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--register',action='store_true');parser.add_argument('--report',type=Path);parser.add_argument('--report-sha256');args=parser.parse_args()
    if not args.register:print('PLAN_ONLY: no reads, observations, writes or runtime changes');return
    require(args.report and args.report_sha256,'Fresh bound original monitor report required');register(args.report,args.report_sha256)
if __name__=='__main__':main()
