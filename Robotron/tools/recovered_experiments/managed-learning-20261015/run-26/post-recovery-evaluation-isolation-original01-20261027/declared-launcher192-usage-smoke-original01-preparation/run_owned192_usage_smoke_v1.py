"""Default inert. One isolated owned192 gate→unchanged role wrapper→MAME usage cohort."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time
import urllib.request

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=ROOT/'logs/managed-learning-20261015/run-26'
I=RUN/'post-recovery-evaluation-isolation-original01-20261027'
HERE=Path(__file__).resolve().parent
UNIT='robotron-declared-launcher192-usage-smoke-original01-20261029.service'
CASE=RUN/'post-natural-turnover-durable-next-candidate-20261029-original01/fresh-main-case.json'
P=I/'declared-launcher-census-original34-preparation'
PROBE=I/'declared-launcher-rolebranch-one-smoke-original01-20261029/result.json'
HEALTH=P/'round_main_health_launcher_v1.py'
HELPER=P/'launcher_census_v1.py'
GATE=HERE/'gate_original_usage_child_v1.py'
SCHEMA='robotron-owned192-rolebranch-usage-smoke-job-v1'
STATIC=('parent_pid','cgroup','command','environment','affinity','uids','executable')
LIMITS=dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='512',RuntimeMaxUSec='3min',Restart='no',NRestarts='0')


def require(value,why):
    if not value:raise ValueError(why)


def ident(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def pin(path):
    path=Path(path);require(path.is_absolute()and path.resolve(strict=True)==path and not path.is_symlink(),'Canonical source required')
    a=path.stat();require(stat.S_ISREG(a.st_mode)and a.st_size<=8<<20,'Bounded metadata/source required')
    raw=path.read_bytes();require(ident(a)==ident(path.stat()),'Source changed during read')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=ident(a))


def checked(value):
    require(pin(value['path'])==value,'Exact fullpin changed: '+value['path']);return Path(value['path'])


def read(value):
    return json.loads(checked(value).read_bytes())


def put(path,value):
    raw=(json.dumps(value,allow_nan=False,separators=(',',':'))+'\n').encode()
    require(len(raw)<=8<<20,'Bounded8MiB original artifact required before write')
    with Path(path).open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return pin(path)


def load(name,value):
    spec=importlib.util.spec_from_file_location(name,checked(value));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def show(unit):
    raw=subprocess.check_output(['systemctl','--user','show',unit],text=True,timeout=5)
    return dict(x.split('=',1)for x in raw.splitlines()if'='in x)


def api():
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as response:raw=response.read((1<<20)+1)
    require(len(raw)<=1<<20,'Bounded mainAPI required');return json.loads(raw)


def full_environment(pid):
    return dict(item.decode().split('=',1)for item in Path('/proc',str(pid),'environ').read_bytes().split(b'\0')if b'='in item)


def owner(job,health,reader):
    values=show(UNIT);proc=health.process_record(os.getpid(),reader)
    require(values['Id']==UNIT and values['MainPID']==str(os.getpid())and values['ControlGroup']==proc['cgroup']
        and values['InvocationID']==os.environ['INVOCATION_ID']and values['ActiveState']=='active'and values['SubState']=='running'
        and all(values[k]==v for k,v in LIMITS.items())and proc['uids']==[os.getuid()]*4,'Exact owned fixture unit/resources required')
    return dict(pid=os.getpid(),birth=proc['starttime_ticks'],unit=UNIT,invocation_id=values['InvocationID'],cgroup=proc['cgroup'],uid=os.getuid(),process=proc)


def verify_parent(value):
    require(os.getppid()==value['pid']and birth(value['pid'])==value['birth'],'Original fixture parent birth differs')
    root=Path('/proc',str(value['pid']))
    require(root.stat().st_uid==value['uid']==os.getuid()and root.joinpath('cgroup').read_text().strip()=='0::'+value['cgroup'],'Original parent UID/cgroup differs')
    require([x.decode()for x in root.joinpath('cmdline').read_bytes().split(b'\0')if x]==value['process']['command'],'Original fixture parent command changed')
    require(Path('/proc/self/cgroup').read_text().strip()=='0::'+value['cgroup'],'Gate escaped its fixture scope')


def verify_main_owners(case,health,reader):
    observed={key:health.unit_record(case['units'][key],reader)for key in ('trainer','fleet')}
    for key,value in observed.items():
        old=case['owners'][key]
        require(value['unit']==old['unit']and value['invocation']==old['invocation']
            and (value['process']['pid'],value['process']['starttime_ticks'])==(old['process']['pid'],old['process']['starttime_ticks'])
            and all(value['process'][field]==old['process'][field]for field in STATIC),'Original main physical owner changed')
    return observed


def commit_sweep(output,index,started,rows,stages):
    ended=time.monotonic()
    raw=put(output/('capture-%06d.json'%index),dict(started_monotonic_s=started,ended_monotonic_s=ended,stable_stage_counts=stages,records=rows))
    return dict(raw=raw,started_monotonic_s=started,ended_monotonic_s=ended,stable_stage_counts=stages,
        archiving_ended_monotonic_s=time.monotonic(),actual_stable_MAME_slots=[r['slot']for r in rows if r.get('stage')=='mame'],
        within5s_birth_age=sum(r.get('within_original5s_birth_age')is True for r in rows),outside5s_birth_age=sum(r.get('within_original5s_birth_age')is False for r in rows))


def main_API_projection(case,before,after):
    for snapshot in (before,after):
        rows=snapshot['client_rows'];slots=[str(row['client_slot'])for row in rows]
        require(len(slots)==len(set(slots))==snapshot['client_count']and set(slots)<=set(case['slot_eval'])
            and len({row['client_id']for row in rows})==len(rows)and all(type(row['client_slot'])is int and type(row['client_id'])is int and type(row['eval'])is bool and row['eval']==case['slot_eval'][str(row['client_slot'])]for row in rows),'Main API unique slot/CID/role projection differs')
    for key in ('optimizer','replay'):
        require(all(before['host_pipeline']['learning_exposure'][key][field]==after['host_pipeline']['learning_exposure'][key][field]==case['exposure'][key][field]for field in ('process_id','instance_monotonic_ns','epoch','epoch_reason')),'Original main exposure lineage changed')
    return dict(before=[{k:r[k]for k in ('client_slot','client_id','eval')}for r in before['client_rows']],after=[{k:r[k]for k in ('client_slot','client_id','eval')}for r in after['client_rows']])


def prepare(output):
    require(Path(output).parent.resolve(strict=True)==HERE and not Path(output).exists(),'New own preparation directory required')
    proof=read(pin(PROBE));require(proof['status']=='OWNED_ROLE_BRANCH_USAGE_SMOKE_PASS'and proof['actual_exit']==0
        and proof['same_PID_birth_MAME_observed']is True and proof['output_role_verified']is True,'Actual one-role no-game probe prerequisite required')
    sources=dict(runner=pin(Path(__file__).resolve()),gate=pin(GATE),health=pin(HEALTH),launcher=pin(HELPER))
    require(all(v['identity']['mode']=='0o444'for v in sources.values()),'Frozen explicit sources required')
    health=load('_usage_prep_health',sources['health']);case=read(pin(CASE));health.check_inputs(case,full=True)
    require(set(case['slot_eval'])==set(map(str,range(192)))and all(type(v)is bool for v in case['slot_eval'].values()),'Exact192 rolemap required')
    env=dict(case['owners']['fleet']['process']['environment'],MAME_BIN=str(ROOT/'tools/power_recovery/mame_with_roles.sh'))
    require(env['ROBOTRON_EVAL_MODE']=='0','Original INPUT role0 required')
    Path(output).mkdir(mode=0o700)
    job=dict(schema=SCHEMA,attempt=1,no_retry=True,unit=UNIT,sources=sources,case=pin(CASE),one_probe=pin(PROBE),output=str(Path(output)/'execution-original01'),
        slots=list(range(192)),parent_launch_environment=env,resources=LIMITS,gate_ready_s=60,exec_observation_s=30,cleanup_s=20,
        work_s=120,actor_argument_suffix=['-showusage'],scientific_launch_qualified=False,controls_main_actors=False)
    jp=put(Path(output)/'job.json',job)
    argv=['systemd-run','--user','--unit='+UNIT,'-p','CPUQuota=200%','-p','MemoryMax=4G','-p','MemorySwapMax=0','-p','TasksMax=512',
        '-p','RuntimeMaxSec=180','-p','Restart=no','-p','RemainAfterExit=yes','-p','KillMode=control-group','-p','TimeoutStopSec=30','env',
        *[k+'='+v for k,v in sorted(env.items())],'/usr/bin/python3.12','-I','-B',str(Path(__file__).resolve()),'--execute','--job',jp['path'],'--job-sha256',jp['sha256']]
    return put(Path(output)/'prepared-owned192-usage-fixture-NOT-LAUNCHED.json',dict(job=jp,ROOT_only_launch_argv=argv,actual_owner=None,actual_result=None,
        actual_simultaneous192MAME=None,actual500ms_qualification=None,status='METADATA_ONLY_NOT_LAUNCHED'))


def cleanup(children,births):
    actions=[]
    for stage,wait_s in (('terminate',10),('kill',10)):
        for slot,child in children.items():
            if child.poll()is None:
                require(birth(child.pid)==births[slot],'Refusing cleanup of an unowned/reused PID')
                getattr(child,stage)();actions.append(dict(slot=slot,pid=child.pid,birth=births[slot],action=stage))
        end=time.monotonic()+wait_s
        for child in children.values():
            if child.poll()is None:
                try:child.wait(timeout=max(.001,end-time.monotonic()))
                except subprocess.TimeoutExpired:pass
    require(all(c.poll()is not None for c in children.values()),'Original child reap incomplete')
    return actions


def run(job,jp):
    require(job['schema']==SCHEMA and job['attempt']==1 and job['no_retry']is True and job['unit']==UNIT
        and job['slots']==list(range(192))and job['resources']==LIMITS and job['actor_argument_suffix']==['-showusage']
        and (job['gate_ready_s'],job['exec_observation_s'],job['cleanup_s'],job['work_s'])==(60,30,20,120),'Exact single original usage job required')
    require(set(job['sources'])=={'runner','gate','health','launcher'}and job['sources']['runner']==pin(Path(__file__).resolve())and job['sources']['gate']==pin(GATE)
        and job['sources']['health']['path']==str(HEALTH)and job['sources']['health']['sha256']=='44371d76f1be25453050a1a508afb70325a86bcec965fe19fbd47a0ab3bf65ef'
        and job['sources']['launcher']['path']==str(HELPER)and job['sources']['launcher']['sha256']=='9da0759190ee2dc60393e293b707285168f35fe5a99c8707c10a8c0f834be26f'
        and job['case']['path']==str(CASE)and job['one_probe']['path']==str(PROBE),'Actual selected source/case/one-probe differs')
    for value in job['sources'].values():checked(value)
    proof=read(job['one_probe']);require(proof['status']=='OWNED_ROLE_BRANCH_USAGE_SMOKE_PASS'and proof['actual_exit']==0
        and proof['same_PID_birth_MAME_observed']is True and proof['output_role_verified']is True,'One-role usage prerequisite changed')
    health=load('_usage_health',job['sources']['health']);launch=load('_usage_launch',job['sources']['launcher']);reader=health.linux()
    case=read(job['case']);health.check_inputs(case,full=True)
    actual=owner(job,health,reader)
    require(actual['process']['environment']==case['owners']['fleet']['process']['environment'],'Actual fixture INPUT environment must equal declared fleet INPUT')
    main_fleet=case['owners']['fleet']['process'];require(birth(main_fleet['pid'])==main_fleet['starttime_ticks'],'Original main fleet changed')
    env=full_environment(main_fleet['pid']);require(env['MAME_BIN']==str(ROOT/'tools/power_recovery/mame_with_roles.sh'),'Exact unchanged role wrapper required')
    output=Path(job['output']);require(output.parent==Path(jp['path']).parent and not output.exists(),'New exclusive owned output required');output.mkdir(mode=0o700)
    own=put(output/'owner.json',actual);main_before=verify_main_owners(case,health,reader);put(output/'before-main-owners.json',main_before);before=api();put(output/'before-main.raw.json',before)
    fixture=copy.deepcopy(case);fixture['owners']['fleet']=dict(unit=UNIT,invocation=actual['invocation_id'],process=actual['process'])
    fixture['actor_command']=[*case['actor_command'],'-showusage'];fixture['actor_affinity']=actual['process']['affinity'];fixture=launch.prepare_case(fixture)
    put(output/'actual-fixture-case.json',fixture)
    children={};births={};pipes={};gate_commands={};attempts=[];ready={};cleanup_actions=[];error=None;all_gates=None;release_clock=None;start=time.monotonic();deadline=start+job['work_s']
    ready_read,ready_write=os.pipe2(os.O_CLOEXEC);os.set_blocking(ready_read,False)
    signals=[];old_signals={s:signal.signal(s,lambda signum,frame:signals.append(signum))for s in (signal.SIGTERM,signal.SIGINT)}
    try:
        for slot in job['slots']:
            require(not signals and time.monotonic()<min(start+job['gate_ready_s'],deadline),'Original gate creation interrupted/bounded')
            r,w=os.pipe2(os.O_CLOEXEC);child_env=dict(env,ROBOTRON_CLIENT_SLOT=str(slot),ROBOTRON_ACTOR_ROUND=str(before['training_round']['round']),ROBOTRON_RETIRE_AFTER_GAME='1',ROBOTRON_PREVIEW_FPS='30')
            argv=['/usr/bin/python3.12','-I','-B',str(GATE),'--job',jp['path'],'--job-sha256',jp['sha256'],'--owner',own['path'],'--owner-sha256',own['sha256'],'--slot',str(slot),'--read-fd',str(r),'--ready-fd',str(ready_write),'--round',str(before['training_round']['round'])]
            with(output/('slot-%03d.stdout'%slot)).open('xb')as out,(output/('slot-%03d.stderr'%slot)).open('xb')as err:
                child=subprocess.Popen(argv,env=child_env,cwd=output,stdout=out,stderr=err,pass_fds=(r,ready_write))
            os.close(r);gate_commands[str(slot)]=argv;children[str(slot)]=child;pipes[str(slot)]=w;births[str(slot)]=birth(child.pid)
            require(births[str(slot)]is not None,'Original child birth unavailable')
        os.close(ready_write);ready_write=None;buffer=b''
        while len(ready)<192:
            require(not signals and time.monotonic()<min(start+job['gate_ready_s'],deadline)and all(c.poll()is None for c in children.values()),'Original gates failed/expired before ready')
            select.select([ready_read],[],[],.05)
            try:chunk=os.read(ready_read,65536)
            except BlockingIOError:continue
            require(chunk,'Ready pipe closed before all192');buffer+=chunk
            while b'\n'in buffer:
                line,buffer=buffer.split(b'\n',1);row=json.loads(line);slot=str(row['slot'])
                require(set(row)=={'slot','pid','birth','parent_pid'}and type(row['slot'])is int and slot in children and slot not in ready and row['pid']==children[slot].pid and row['birth']==births[slot]and row['parent_pid']==os.getpid(),'Original gate readiness identity differs');ready[slot]=row
        put(output/'all192-gate-ready.json',ready)
        then=time.monotonic();paired={}
        for slot,child in children.items():
            require(time.monotonic()<deadline,'Original paired-gate work deadline reached')
            a=health.process_record(child.pid,reader);b=health.process_record(child.pid,reader)
            require((a['pid'],a['starttime_ticks'])==(child.pid,births[slot])and all(a[k]==b[k]for k in ('pid','starttime_ticks',*STATIC))
                and a['parent_pid']==os.getpid()and a['cgroup']==actual['cgroup']and a['command']==gate_commands[slot],'Original192 gate physical bracket differs');paired[slot]=dict(record=a,confirm_record=b)
        elapsed=time.monotonic()-then
        require(all(c.poll()is None for c in children.values()),'Gate vanished before original192 barrier')
        all_gates=dict(actual192_gate_population=True,paired_capture_s=elapsed,records=paired,scope='192 owned Python gates before release; NOT192MAME or fullTCP/worker500ms qualification')
        put(output/'original192-gate-paired-capture.json',all_gates)
        health.check_inputs(case)
        release_clock=launch.sample_clock();release=time.monotonic()
        for slot,w in list(pipes.items()):os.write(w,b'G');os.close(w);del pipes[slot]
        while any(c.poll()is None for c in children.values()):
            require(not signals and time.monotonic()<min(release+job['exec_observation_s'],deadline),'Original usage exec observation interrupted/expired')
            sweep=time.monotonic();stages={};sweep_rows=[]
            for slot,child in children.items():
                if child.poll()is not None:continue
                entry=dict(slot=slot,pid=child.pid,birth=births[slot])
                try:
                    a=health.process_record(child.pid,reader);entry['record']=a;b=health.process_record(child.pid,reader);entry['confirm_record']=b
                    require((a['pid'],a['starttime_ticks'])==(child.pid,births[slot])and all(a[k]==b[k]for k in ('pid','starttime_ticks',*STATIC)),'Original child exec raced pair')
                    require(a['parent_pid']==os.getpid()and a['cgroup']==actual['cgroup']and a['uids']==[os.getuid()]*4 and a['affinity']==fixture['actor_affinity'],'Fixture child escaped owner/affinity')
                    clock=launch.sample_clock();entry['clock']=clock
                    entry['actual_birth_age_s']=clock['boottime_s']-a['starttime_ticks']/clock['ticks_per_second']
                    entry['within_original5s_birth_age']=0<=entry['actual_birth_age_s']<=5
                    if a['command']==gate_commands[slot]:stage='gate_releasing'
                    else:stage=launch.phase(fixture,a)
                    entry['stage']=stage
                    if stage!='mame':require(a['environment']==launch.expected_input(fixture,slot,before['training_round']['round']),'Actual unchanged launcher INPUT differs')
                    if stage=='mame':
                        expected=dict(case['actor_environment'],ROBOTRON_CLIENT_SLOT=slot,ROBOTRON_ACTOR_ROUND=str(before['training_round']['round']),ROBOTRON_EVAL_MODE='1'if case['slot_eval'][slot]else'2',ROBOTRON_PREVIEW_CLIENT='1'if slot=='0'else'0')
                        require(a['environment']==expected and a['executable']==case['actor_executable'],'Actual MAME forced role/environment differs')
                    stages[stage]=stages.get(stage,0)+1
                except(OSError,KeyError)as failure:entry['unaccepted_capture']=repr(failure)
                except ValueError as failure:
                    if str(failure)=='Original child exec raced pair':entry['unaccepted_capture']=repr(failure)
                    else:
                        entry['invalid_stable_identity']=repr(failure);sweep_rows.append(entry)
                        attempts.append(commit_sweep(output,len(attempts),sweep,sweep_rows,stages));raise
                sweep_rows.append(entry)
            attempts.append(commit_sweep(output,len(attempts),sweep,sweep_rows,stages))
            require(len(attempts)<=256,'Bounded original capture record count exceeded');time.sleep(.0005)
    except BaseException as failure:error=repr(failure)
    finally:
        for w in pipes.values():os.close(w)
        if ready_write is not None:os.close(ready_write)
        os.close(ready_read)
        try:cleanup_actions=cleanup(children,births)
        except BaseException as failure:error=(error+'; 'if error else'')+'cleanup:'+repr(failure)
        for s,handler in old_signals.items():signal.signal(s,handler)
    terminal={slot:dict(pid=c.pid,birth=births.get(slot),actual_Popen_exit=c.poll(),original_birth_absent=birth(c.pid)!=births.get(slot))for slot,c in children.items()}
    put(output/'original-children-terminal-and-reap.json',dict(children=terminal,cleanup_actions=cleanup_actions,signals_received=signals));put(output/'original-process-attempts.json',attempts)
    after=api();put(output/'after-main.raw.json',after);main_after=verify_main_owners(case,health,reader);put(output/'after-main-owners.json',main_after)
    try:
        require(not error and len(children)==192 and all_gates is not None and not cleanup_actions and not signals,'Original cohort failed or required forced cleanup')
        require(all(v['actual_Popen_exit']==0 and v['original_birth_absent']for v in terminal.values()),'Every original usage child must exit0 and be reaped')
        for slot in children:
            path=output/('slot-%03d.stdout'%int(slot));require(path.stat().st_size<=1<<20,'Bounded usage stdout required');text=path.read_text(errors='replace');require(len(text)>1000 and'showusage'in text.lower(),'Every original child must positively emit installed MAME usage')
        require(before['host_pipeline']['learning_exposure']['optimizer']['process_id']==after['host_pipeline']['learning_exposure']['optimizer']['process_id']==case['owners']['trainer']['process']['pid']
            and birth(main_fleet['pid'])==main_fleet['starttime_ticks'],'Actual original training owner changed')
        main_API_projection(case,before,after)
        health.check_inputs(case,full=True)
    except BaseException as failure:error=(error+'; 'if error else'')+repr(failure)
    peaks={stage:max((row['stable_stage_counts'].get(stage,0)for row in attempts),default=0)for stage in ('gate_releasing','env','bash','python','mame')}
    observed={slot for sweep in attempts for slot in sweep['actual_stable_MAME_slots']}
    result=dict(schema='robotron-owned192-rolebranch-usage-smoke-result-v1',status='OWNED192_USAGE_COHORT_CLOSED'if error is None else'ORIGINAL_FIXTURE_FAILED',error=error,
        job=jp,owner=own,original_children=terminal,gate192_paired_capture_s=all_gates['paired_capture_s']if all_gates else None,
        actual_peak_stable_stage_counts=peaks,slots_with_actual_stable_MAME_output_observed=sorted(observed,key=int),all192_MAME_outputs_observed=len(observed)==192,
        actual_all192_MAME_simultaneous=None,sequential_sweep_had192_stable_MAME_records=peaks['mame']==192,actual_full500ms_qualification=False,
        gate_release_clock=release_clock,maximum_gate_birth_age_at_release_s=max((release_clock['boottime_s']-value/release_clock['ticks_per_second']for value in births.values()),default=None)if release_clock else None,
        original5s_birth_age_phase_observations=dict(within=sum(sweep['within5s_birth_age']for sweep in attempts),outside=sum(sweep['outside5s_birth_age']for sweep in attempts)),
        main_before_after_CID_observations=main_API_projection(case,before,after)if error is None else None,
        main_CID_scope='Per-snapshot observations and role projections only; CIDs may rotate and do not identify physical actors.',gate_age_scope='Pipe hold can make real birth ages exceed the unchanged5s main-launcher rule; fixture never resets birth or qualifies that rule by gate count.',scientific_launch_qualified=False,
        timing_scope='Stable per-sweep observations are sequential paired captures, not an atomic simultaneous executable census; gate192 barrier was positively held. Timings exclude serialization/file I/O and fullTCP/worker pipeline.')
    put(output/'result.json',result);return 0 if error is None else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare');p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');a=p.parse_args()
    require(not(a.prepare and a.execute),'Choose one explicit mode')
    if a.prepare:print(json.dumps(prepare(a.prepare)));return
    if not a.execute:print('INERT: no metadata/API/proc/process or control actions');return
    jp=pin(Path(a.job));require(jp['sha256']==a.job_sha256,'Actual selected job SHA differs');raise SystemExit(run(read(jp),jp))


if __name__=='__main__':main()
