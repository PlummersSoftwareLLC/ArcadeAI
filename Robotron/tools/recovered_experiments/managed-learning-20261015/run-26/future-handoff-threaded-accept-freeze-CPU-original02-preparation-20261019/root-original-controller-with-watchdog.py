import hashlib,importlib.util,json,os,threading,time
from pathlib import Path
P=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-handoff-threaded-accept-freeze-CPU-original02-preparation-20261019')
source=P/'controller-source.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
config=P/'config.json';assert hashlib.sha256(config.read_bytes()).hexdigest()=='5730a75aad8176c080132a60c2ba11ed1e8355c4c7d897d3d6840b85d674b762'
spec=importlib.util.spec_from_file_location('original_CPU_controller',source);c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
unit=json.loads(config.read_bytes())['unit']
root=Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')/unit
stop=threading.Event();errors=[];observed=set();rescues=[]
def start(p):
 raw=p.read_text();return int(raw[raw.rfind(')')+2:].split()[19])
c.publish(P/'work/watchdog-ready.json',dict(pid=os.getpid(),starttime_ticks=start(Path('/proc/self/stat')),unit=unit,scope='Only this private CPU unit child, never the main trainer/fleet'))
def watch():
 try:
  while not stop.wait(.02):
   for path in (P/'work/freeze-attempts').glob('*.json'):
    item=json.loads(path.read_bytes());child=Path(item['child_path']);observed.add(path.name)
    assert path.name in ('1.json','2.json') and child==root/('listener-proof-'+path.stem)
    assert item['root_path']==str(root) and item['original_unit']==unit
    if time.monotonic()<=item['deadline_monotonic_s']:continue
    if not child.exists() or (child/'cgroup.freeze').read_text().strip()!='1':continue
    owner=json.loads((P/'execution/root-original-identity.json').read_bytes())
    assert owner['unit']==unit and owner['pid']==item['pid'] and owner['starttime_ticks']==item['process_starttime_ticks']
    assert start(Path('/proc',str(owner['pid']),'stat'))==owner['starttime_ticks']
    task=Path('/proc',str(owner['pid']),'task',str(item['tid']))
    assert start(task/'stat')==item['thread_starttime_ticks'] and child.stat().st_uid==os.getuid()
    assert (task/'cgroup').read_text().strip()=='0::'+str(child).removeprefix('/sys/fs/cgroup')
    (child/'cgroup.freeze').write_text('0\n')
    rescues.append(dict(attempt=path.name,child=str(child),unix_s=time.time()))
    c.publish(P/'work/watchdog-triggered.json',dict(status='TEST_INVALID_WATCHDOG_THAW_USED',rescue=rescues[-1]))
 except BaseException as error:
  errors.append(repr(error))
thread=threading.Thread(target=watch,daemon=True);thread.start()
try:
 c.launch(config);result=c.observe(config)
finally:
 stop.set();thread.join(2)
 c.publish(P/'root-watchdog-observation.json',dict(windows_observed=sorted(observed),rescues=rescues,errors=errors,watcher_joined=not thread.is_alive(),trainer_changed=False))
assert not errors and not rescues and not thread.is_alive()
assert result['original_exit']==0 and result['lifecycle_complete'] and result['unit_released']
