"""One stdlib child tests the unchanged reviewed cgroup owner in a new unit."""
import hashlib,importlib.util,json,os,subprocess,sys,time,traceback
from pathlib import Path

OUT=Path(__file__).resolve().parent
MODULE=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/coherent_snapshot_proposal/whole_agent_smoke.py')
EXPECTED='dbdb86f37e7158876262949eaf37c0c6d8954bd136f6c5187bcc6c3fe04f37bf'
NONCE='resource-probe-20261016T225828Z'
TOKEN='release-owned-stdlib-child-20261016T225828Z'

def save(name,value):
    with (OUT/name).open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())

def proc(pid):
    p=Path('/proc')/str(pid);parts=(p/'stat').read_text().rsplit(') ',1)[1].split()
    return dict(pid=pid,start_ticks=parts[19],ppid=int(parts[1]),pgid=int(parts[2]),cgroup=(p/'cgroup').read_text().strip())

def resources(path):
    return {name:(path/name).read_text().strip() for name in ('memory.max','memory.swap.max','memory.oom.group','memory.current','pids.max','pids.current','cpu.max','cgroup.procs','cgroup.events','cgroup.controllers','cgroup.subtree_control')}

CHILD="""import json,os,sys,select
from pathlib import Path
if not select.select([sys.stdin],[],[],15)[0]:raise SystemExit(7)
if sys.stdin.readline().strip()!=sys.argv[1]:raise SystemExit(8)
pid=os.getpid();p=Path('/proc')/str(pid);parts=(p/'stat').read_text().rsplit(') ',1)[1].split()
print(json.dumps(dict(pid=pid,start_ticks=parts[19],cgroup=(p/'cgroup').read_text().strip(),numerical_modules=[n for n in sys.modules if n.split('.')[0] in ('torch','numpy','dqn')])) ,flush=True)
"""

group=child=child_identity=module=None
result=dict(status='failed',parent=proc(os.getpid()),errors=[],cleanup={})
try:
    actual=hashlib.sha256(MODULE.read_bytes()).hexdigest()
    if actual!=EXPECTED:raise RuntimeError('Reviewed cgroup source changed before import')
    spec=importlib.util.spec_from_file_location('reviewed_snapshot_smoke_resource_probe',MODULE)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    parent=module.cgroup_parent()
    result.update(module_sha256=actual,delegated_parent=str(parent),outer_before=resources(parent),supervisor_cgroup=result['parent']['cgroup'])
    group=module.OwnedCgroup(parent,NONCE)
    command=[sys.executable,'-I','-B','-c',CHILD,TOKEN]
    child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    child_identity=proc(child.pid)
    group.attach(child.pid)
    attached=proc(child.pid)
    relative='/'+str(group.path.relative_to('/sys/fs/cgroup'))
    if attached['start_ticks']!=child_identity['start_ticks'] or attached['cgroup']!='0::'+relative:raise RuntimeError('Child attachment identity/cgroup mismatch')
    if group.path.parent!=parent or group.path.name=='snapshot-supervisor':raise RuntimeError('Child group is not the owned supervisor sibling')
    if group.members()!=[child.pid]:raise RuntimeError('Unexpected child group members')
    inner=resources(group.path);outer=resources(parent)
    expected_inner={'memory.max':str(module.BOUNDS['memory_bytes']),'memory.swap.max':'0','memory.oom.group':'1','pids.max':str(module.BOUNDS['tasks']),'cpu.max':'200000 100000'}
    if any(inner[k]!=v for k,v in expected_inner.items()):raise RuntimeError('Reviewed inner controller settings mismatch')
    quota,period=map(int,outer['cpu.max'].split())
    if int(outer['memory.max'])>256*1024*1024 or outer['memory.swap.max']!='0' or int(outer['pids.max'])>32 or quota>period:raise RuntimeError('Outer resource bounds mismatch')
    result.update(child_command=command,child_before_attach=child_identity,child_after_attach=attached,owned_group=str(group.path),owned_group_directory_identity=group.identity,inner=inner,outer_after_attach=outer,
        effective_caps=dict(memory_bytes=min(int(inner['memory.max']),int(outer['memory.max'])),swap_bytes=0,pids=min(int(inner['pids.max']),int(outer['pids.max'])),cpu_cores=min(2,quota/period)))
    save('attached.json',result)
    deadline=time.monotonic()+10
    while not (OUT/'release.flag').exists():
        if time.monotonic()>=deadline:raise TimeoutError('Outer property inspection did not release probe')
        time.sleep(.02)
    output,errors=child.communicate((TOKEN+'\n').encode(),timeout=5)
    if child.returncode:raise RuntimeError('Owned stdlib child failed: '+errors.decode(errors='replace'))
    receipt=json.loads(output)
    if receipt['pid']!=child.pid or receipt['start_ticks']!=child_identity['start_ticks'] or receipt['cgroup']!=attached['cgroup'] or receipt['numerical_modules']:raise RuntimeError('Child post-token receipt mismatch')
    result.update(status='passed',child_receipt=receipt,child_returncode=child.returncode)
except BaseException as error:
    result['errors'].append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
finally:
    try:
        if child is not None and child.poll() is None:
            if child.stdin is not None and not child.stdin.closed:child.stdin.close()
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                if proc(child.pid)['start_ticks']!=child_identity['start_ticks']:raise RuntimeError('Refusing cleanup signal to reused child')
                child.terminate();child.wait(timeout=3)
        if group is not None:
            result['cleanup']['remaining_members']=group.members()
            group.close();result['cleanup']['owned_group_removed']=not group.path.exists()
    except BaseException as error:
        result['status']='failed';result['errors'].append(dict(cleanup_type=type(error).__name__,message=str(error)))
    result['numerical_modules']=[name for name in sys.modules if name.split('.')[0] in ('numpy','torch','dqn')]
    if result['numerical_modules']:result['status']='failed'
    result['module_hash_unchanged']=hashlib.sha256(MODULE.read_bytes()).hexdigest()==EXPECTED
    save('result.json',result)
sys.exit(0 if result['status']=='passed' else 1)
