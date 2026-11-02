from pathlib import Path
import datetime,hashlib,importlib.util,json,os,time
R=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26');P=R/'rejected-gap-healthy-activation-root-preparation-20261018';G=R.parents[2]
controller=R/'postaccepted-newgame-quality-R1-audit-wait-source-preparation-20261017/control_audit.py'
assert hashlib.sha256(controller.read_bytes()).hexdigest()=='db6e9399792aecb3fb3e84e255a2e208f6a2981316f6e76c306cca5af049f986'
spec=importlib.util.spec_from_file_location('_root_actual_activation_once_controller',controller);c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
job=P/'root-actual-activation-job.json';assert hashlib.sha256(job.read_bytes()).hexdigest()=='453d635110b6fc4c29fb59414d33de6961e1f828ac49390911231a8aaa0b9fb0'
source=G/'tools/rejected_gap_healthy_activation_proposal/run_healthy_activation.py';assert hashlib.sha256(source.read_bytes()).hexdigest()=='ef50ee32880ff93a788d33c7a90ccba01f3de33caa015c849712e31ca910f78e'
peer=P/'root-actual-case-independent-review.json';review=json.loads(peer.read_text());assert review['status']=='PASS_ESSENTIAL_SOURCE_AND_CLOSED_CASE' and review['job']['sha256']==c.pin(job)['sha256']
execution=R/'rejected-gap-healthy-activation-original01-root-execution-20261018';payload=R/'rejected-gap-healthy-activation-original01-20261018'
cfg=dict(unit='robotron-rejected-gap-healthy-activation-original01-20261018.service',output=str(execution),argv=['/usr/bin/python3.12','-I','-B',str(source),'--execute','--job',str(job),'--expected-job-sha256',c.pin(job)['sha256'],'--expected-source-sha256',c.pin(source)['sha256']],properties=['CPUQuota=400%','MemoryMax=16G','MemorySwapMax=0','TasksMax=512','RuntimeMaxSec=1800','TimeoutStopSec=300','SendSIGKILL=no'],pins=[c.pin(x) for x in (controller,Path(__file__),source,job,peer,P/'root-actual-case-readonly-validation.json')],observation_s=1860,result_path=str(payload/'result.json'))
cp=P/'root-actual-execution-config.json';c.publish(cp,cfg)
state_path=R.parent/'state.json';state=json.loads(state_path.read_text());goal=state['optimization_goal'];now=datetime.datetime.now(datetime.timezone.utc).isoformat()
state['stage']='run26_confirmed704M_diagnostic_activation_original01_starting';goal['diagnostic_activation_original01']=dict(status='ORIGINAL_ONCE_STARTING',job=c.pin(job),config=c.pin(cp),source=c.pin(source),independent_case=c.pin(peer),runtime_source_application_complete=False,protected_reference='models_dqn/managed-incumbents/freshCE-accepted-newgame-704M-confirmed-20261018.pt',newest_only=True,retain_original_192=True)
goal['next_action']='Observe this same original activation once through newest-stopped CPU, new-owner startup CPU, original192 reconnect and strict60. No duplicate launch or weight rollback. After success measure diagnostic API and prepare fresh E13 quality family.'
state['updated_utc']=now;state['updated_unix_s']=time.time();tmp=state_path.with_name('state.diagnostic-activation-starting.tmp')
data=(json.dumps(state,separators=(',',':'),allow_nan=False)+'\n').encode();assert len(data)<1048576
with tmp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
os.replace(tmp,state_path);fd=os.open(state_path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
c.launch(cp);c.observe(cp)
