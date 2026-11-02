"""Fresh192 owned-fleet exec adapter. Default CLI is inert.

No old4947/507 INPUT, consumed permit, process control, batch controller or PID
fiction. The exact new named systemd unit supplies the runtime original parent.
Probes are exact read-only startup commands; only verifyroms may have one Bash
command-substitution intermediate. Actual actors MUST be direct MainPID children.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import types

GAME_ROOT = '/home/dave/source/repos/ArcadeAI/Robotron'
MAME_EXECUTABLE = '/usr/games/mame'
LAUNCHER_SHA = '7a20ccb7a2cea90178a557ffa012d6ac1f5ff7a3ea2db47ec71d3de343c4ad99'
COLLECTOR_SHA = '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'
ROLEMAP_SHA = '63b013ad3c7440262317af8d1ab63a9494ab2a4efda5dd2ff0a4abb18424ed0a'
RAW_SHA = 'cbd8109f8d62f65c26c38ea91c73b3285fda0812895ee5e5fbf4e8565afedbd1'
ORIGINAL_WRAPPER_SHA = '26464f5e7bf9137744a9a867c606aebc97c0beffd99331b93777c38fdee1aea8'
UNIT = 'robotron-managed-run-26-continuation-raw4hz-original01-20261027-fleet.service'
FLEET_TAG = 'managed-run-26-continuation-raw4hz-original01-20261027'
SLOTS = {str(i) for i in range(192)}
ENV_KEYS = {'LD_PRELOAD','LUA_PATH','LUA_CPATH','SDL_VIDEODRIVER','SDL_AUDIODRIVER','MAME_BIN'}
PIN_KEYS = {'path','sha256','bytes','identity'}
MANIFEST_KEYS = {'schema','helper','collector','rolemap','launcher','canonical_lua','wait_library',
    'original_wrapper','parent_unit','parent_argv','parent_environment','actor_environment',
    'actor_args','fleet_tag','wrapper_path'}


def require(value,message):
    if not value:raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def read_bytes(pin):
    require(type(pin)is dict and set(pin)==PIN_KEYS,'Exact full small pin required')
    path=Path(pin['path'])
    require(path.is_absolute()and path.resolve(strict=True)==path and '..'not in path.parts,
        'Canonical nonsymlink source path required')
    require(type(pin['bytes'])is int and 0<pin['bytes']<=2_000_000
        and re.fullmatch('[0-9a-f]{64}',pin['sha256']),'Bounded small source SHA required')
    before=path.lstat()
    require(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and identity(before)==pin['identity']
        and before.st_size==pin['bytes'],'Selected source identity differs')
    with path.open('rb')as stream:
        require(identity(os.fstat(stream.fileno()))==identity(before),'Source changed before open')
        raw=stream.read(2_000_001)
        require(identity(os.fstat(stream.fileno()))==identity(before),'Source changed during read')
    require(identity(path.lstat())==identity(before)and len(raw)==pin['bytes']
        and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Selected source bytes differ')
    return raw


def strict_json(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate JSON key');result[key]=value
        return result
    def invalid(_):raise ValueError('Nonfinite JSON forbidden')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=invalid)


def read(pin):
    require(pin['identity']['mode']=='0o444'and pin['identity']['uid']==os.getuid(),
        'Immutable owned JSON required')
    return strict_json(read_bytes(pin))


def controlled(environment):
    return {key:value for key,value in environment.items()if key.startswith('ROBOTRON_')or key in ENV_KEYS}


def parent_argv():
    return ['bash',GAME_ROOT+'/startmame.sh','192','novideo','nonaudio','--supervise','--socket-address','dell:9998']


def actor_argv():
    return ['robotron','-rompath',GAME_ROOT+'/roms','-cheat','-nothrottle','-sound','none',
        '-video','none','-skip_gameinfo','-autoboot_script',GAME_ROOT+'/Scripts/main.lua']


def input_environments(rolemap,read_json=read):
    """Preserved source227 controls; new tag/paths, not reused actor INPUT data."""
    policy=read_json(rolemap['source_policy'])
    parent=controlled(policy['baseline_owners']['fleet']['process']['environment'])
    parent.update(ROBOTRON_FLEET_ID=FLEET_TAG,MAME_BIN=GAME_ROOT+'/tools/mame_with_socket_wait.sh')
    require(parent.get('ROBOTRON_EVAL_MODE')=='0','Parent must retain cached eval0')
    actor=controlled(policy['baseline_actors']['0']['environment'])
    for key in ('LD_PRELOAD','ROBOTRON_SOCKET_WAIT_PORT','ROBOTRON_CLIENT_SLOT'):actor.pop(key,None)
    actor.update(ROBOTRON_FLEET_ID=FLEET_TAG,ROBOTRON_EVAL_MODE='0',
        ROBOTRON_SOCKET_ADDRESS='dell:9998',ROBOTRON_PREVIEW_CLIENT='0',
        MAME_BIN=GAME_ROOT+'/tools/mame_with_socket_wait.sh')
    return parent,actor


def validate_manifest(manifest,read_json=read,read_source=read_bytes):
    require(type(manifest)is dict and set(manifest)==MANIFEST_KEYS
        and manifest['schema']=='robotron-fresh192-owned-role-exec-manifest-v1'
        and all(value is not None for value in manifest.values()),'Fresh actual manifest facts unfilled')
    require(manifest['parent_unit']==UNIT and manifest['fleet_tag']==FLEET_TAG
        and manifest['parent_argv']==parent_argv()and manifest['actor_args']==actor_argv()
        and manifest['wrapper_path']==GAME_ROOT+'/tools/mame_with_socket_wait.sh','Exact fresh scope required')
    require(manifest['launcher']['path']==GAME_ROOT+'/startmame.sh'and manifest['launcher']['sha256']==LAUNCHER_SHA
        and manifest['canonical_lua']['path']==GAME_ROOT+'/Scripts/main.lua'and manifest['canonical_lua']['sha256']==RAW_SHA
        and manifest['collector']['sha256']==COLLECTOR_SHA and manifest['rolemap']['sha256']==ROLEMAP_SHA
        and manifest['original_wrapper']['sha256']==ORIGINAL_WRAPPER_SHA,'Exact fresh source family required')
    for role in ('helper','collector','launcher','canonical_lua','wait_library','original_wrapper'):
        read_source(manifest[role])
    rolemap=read_json(manifest['rolemap'])
    require(rolemap['schema']=='robotron-fresh-continuation-192-preserved-rolemap-v1'
        and rolemap['source_count']==192 and rolemap['source_held_count']==227
        and set(rolemap['slot_eval'])==set(rolemap['forced_output_mode'])==SLOTS
        and all(type(v)is bool for v in rolemap['slot_eval'].values()),'Exact original192 actual roles required')
    binding=read_json(rolemap['source_binding']);policy=read_json(rolemap['source_policy'])
    require(binding['supervision_policy']==rolemap['source_policy']and len(binding['held_hashes'])==227
        and all(binding['preview_actual_roles'][slot]['eval']is rolemap['slot_eval'][slot]for slot in SLOTS)
        and all(rolemap['forced_output_mode'][slot]==('1'if rolemap['slot_eval'][slot]else'2')for slot in SLOTS),
        'Actual227 source binding/roles differ')
    parent,actor=input_environments(rolemap,read_json)
    require(manifest['parent_environment']==parent and manifest['actor_environment']==actor,
        'Fresh preserved control environment differs')
    require(manifest['wait_library']['path']==parent['ROBOTRON_SOCKET_WAIT_LIBRARY']
        ==actor['ROBOTRON_SOCKET_WAIT_LIBRARY']and parent['ROBOTRON_SOCKET_WAIT_US']==actor['ROBOTRON_SOCKET_WAIT_US']=='1000',
        'Exact preserved readiness shim required')
    return rolemap


def render_wrapper(manifest_pin,manifest,read_source=read_bytes):
    original=read_source(manifest['original_wrapper']);marker=b'exec env LD_PRELOAD='
    require(original.count(marker)==1,'Original wait prefix differs')
    args=['env','-u','LD_PRELOAD','/usr/bin/python3.12','-I','-B',manifest['helper']['path'],
        '--execute','--manifest',manifest_pin['path'],'--manifest-sha256',manifest_pin['sha256'],
        '--expected-source-sha256',manifest['helper']['sha256'],'--']
    return original[:original.index(marker)]+('exec '+' '.join(shlex.quote(a)for a in args)+' "$@"\n').encode()


def verify_rendered_wrapper(manifest_pin,manifest,read_source=read_bytes):
    path=Path(manifest['wrapper_path']);before=path.lstat()
    require(path.resolve(strict=True)==path and stat.S_ISREG(before.st_mode)
        and before.st_uid==os.getuid()and before.st_nlink==1
        and stat.S_IMODE(before.st_mode)&0o111 and 0<before.st_size<=8192,
        'Exact canonical owned executable wrapper required')
    with path.open('rb')as stream:
        require(identity(os.fstat(stream.fileno()))==identity(before),'Wrapper changed before open')
        raw=stream.read(8193)
        require(identity(os.fstat(stream.fileno()))==identity(before),'Wrapper changed during read')
    require(identity(path.lstat())==identity(before)
        and raw==render_wrapper(manifest_pin,manifest,read_source),
        'Actual wrapper differs from acyclic manifest/helper derivation')


def prepare_launch(manifest,rolemap,args,environment):
    require(type(args)is list and all(type(v)is str and '\0'not in v for v in args)
        and all(type(k)is str and type(v)is str and '\0'not in k+v and '='not in k for k,v in environment.items()),
        'Literal argv/string environment required')
    probe='showusage'if args==['-showusage']else'verifyroms'if args==['-rompath',GAME_ROOT+'/roms','-verifyroms','robotron']else None
    output=dict(environment)
    if probe is not None:
        require('ROBOTRON_CLIENT_SLOT'not in environment and controlled(environment)==manifest['parent_environment'],
            'Only startup INPUT environment may probe')
    else:
        slot=environment.get('ROBOTRON_CLIENT_SLOT')
        require(type(slot)is str and re.fullmatch('0|[1-9][0-9]{0,2}',slot)and slot in SLOTS
            and args==manifest['actor_args'],'Exact fresh actor slot/args required')
        expected=dict(manifest['actor_environment'],ROBOTRON_CLIENT_SLOT=slot)
        expected['ROBOTRON_PREVIEW_CLIENT']='1'if slot=='0'else'0'
        require(controlled(environment)==expected,'Fresh actor INPUT controls differ')
        output['ROBOTRON_EVAL_MODE']=rolemap['forced_output_mode'][slot]
    output['LD_PRELOAD']=manifest['wait_library']['path'];output['ROBOTRON_SOCKET_WAIT_PORT']='9998'
    return [MAME_EXECUTABLE,*args],output,probe


def unit_show(unit):
    result=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=5)
    require(result.returncode==0 and result.stderr=='','Fresh named-unit query failed')
    fields={}
    for line in result.stdout.splitlines():
        if '='in line:
            key,value=line.split('=',1);require(key not in fields,'Duplicate unit field');fields[key]=value
    return fields


def process_environment(pid):
    values={}
    for pair in Path('/proc',str(pid),'environ').read_bytes().split(b'\0'):
        if b'='in pair:
            key,value=pair.split(b'=',1);values[key.decode()]=value.decode()
    return controlled(values)


def verify_runtime_parent(manifest,probe,collector,query=unit_show,parent_pid=os.getppid,
                          environment_reader=process_environment):
    fields=query(manifest['parent_unit'])
    require(fields.get('Id')==UNIT and fields.get('ActiveState')=='active'and fields.get('SubState')=='running'
        and fields.get('NRestarts')=='0'and re.fullmatch('[0-9a-f]{32}',fields.get('InvocationID','')),
        'Exact un-restarted fresh named fleet required')
    raw_pid=fields.get('MainPID','');require(raw_pid.isdecimal()and int(raw_pid)>0,'Live fresh MainPID required')
    pid=int(raw_pid);main=collector.process_record(pid)
    require(main['command']==manifest['parent_argv']and main['cgroup']==fields['ControlGroup']
        and main['uids']==[os.getuid()]*4 and environment_reader(pid)==manifest['parent_environment'],
        'Fresh parent process/source/input environment differs')
    ppid=parent_pid();intermediate=None
    if ppid!=pid:
        require(probe=='verifyroms','Only exactverifyroms may use one Bash substitution parent')
        intermediate=collector.process_record(ppid)
        require(intermediate['parent_pid']==pid and intermediate['command']==main['command']
            and all(intermediate[key]==main[key]for key in ('cgroup','uids','executable','affinity'))
            and environment_reader(ppid)==manifest['parent_environment'],
            'Verifyroms substitution is not one exact owned Bash child')
    require(collector.process_record(pid)==main and parent_pid()==ppid,'Parent changed during admission')
    if intermediate is not None:
        require(collector.process_record(ppid)==intermediate,'Verifyroms Bash child changed')
    again=query(manifest['parent_unit'])
    require(all(again.get(key)==fields.get(key)for key in
        ('Id','MainPID','InvocationID','ControlGroup','NRestarts','ActiveState','SubState')),
        'Fresh named unit changed before exec')
    return dict(pid=pid,starttime_ticks=main['starttime_ticks'],invocation_id=fields['InvocationID'],
        direct_parent=ppid==pid,probe=probe)


def dispatch(manifest_pin,manifest,args,environment,collector,read_json=read,read_source=read_bytes,
             exec_function=None,parent_check=None):
    require(read_json(manifest_pin)==manifest,'Actual immutable fresh manifest differs')
    rolemap=validate_manifest(manifest,read_json,read_source)
    verify_rendered_wrapper(manifest_pin,manifest,read_source)
    command,output,probe=prepare_launch(manifest,rolemap,args,environment)
    if parent_check is None:verify_runtime_parent(manifest,probe,collector)
    else:parent_check(probe)
    (os.execve if exec_function is None else exec_function)(command[0],command,output)
    raise AssertionError('execve returned without replacing fresh helper')


def main(argv=None):
    argv=sys.argv[1:]if argv is None else argv
    if not argv:print('PLAN_ONLY: fresh source/data/runtime unit unfilled; no exec or actions');return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--manifest',required=True)
    parser.add_argument('--manifest-sha256',required=True);parser.add_argument('--expected-source-sha256',required=True)
    parser.add_argument('mame_args',nargs=argparse.REMAINDER);args=parser.parse_args(argv)
    source=Path(__file__);s=source.lstat()
    own=dict(path=str(source),sha256=args.expected_source_sha256,bytes=s.st_size,identity=identity(s))
    require(stat.S_IMODE(s.st_mode)==0o444,'Frozen fresh helper required');read_bytes(own)
    p=Path(args.manifest);s=p.lstat();manifest_pin=dict(path=str(p),sha256=args.manifest_sha256,bytes=s.st_size,identity=identity(s))
    manifest=read(manifest_pin);require(manifest['helper']==own,'Fresh manifest helper pin differs')
    rolemap=validate_manifest(manifest)
    pin=manifest['collector'];raw=read_bytes(pin);collector=types.ModuleType('_fresh_exact_collector')
    collector.__file__=pin['path'];exec(compile(raw,pin['path'],'exec'),collector.__dict__)
    require(args.mame_args[:1]==['--'],'Explicit literal argv separator required')
    if args.execute:dispatch(manifest_pin,manifest,args.mame_args[1:],dict(os.environ),collector)
    else:prepare_launch(manifest,rolemap,args.mame_args[1:],dict(os.environ));print('CHECK_ONLY_NO_EXEC_NO_ACTION')
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except(ValueError,OSError,KeyError,TypeError,IndexError)as error:
        print('FRESH_ROLE_EXEC_REFUSED: '+type(error).__name__+': '+str(error),file=sys.stderr);raise SystemExit(2)
