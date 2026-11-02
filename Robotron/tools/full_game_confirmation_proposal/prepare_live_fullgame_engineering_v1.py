"""Prepare one finite ENGINEERING_ONLY all64-natural-game evaluator run.

The stationary checkpoint has CPU qualification. One declared slow original
MAME slot exercises early retirement/parking of the other31 without dropping
its selected tails. No learning candidate, promotion rule or Main is changed.
"""
import argparse
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
C=B/'post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
E=C/'fullgame-evaluator-live-engineering-original01-20261101'
CPU= B/'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/state-sources/control_stopped_fullstate600_CPU_v1.py'


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def write(path,data):
    with path.open('xb')as f:f.write(data);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    h=load('_live_fullgame_engineering_prepare_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    D=E/'native-engineering-original01';D.mkdir(mode=0o700)
    cpu_dir=E/'policy-CPU-original03';cpu=json.loads((cpu_dir/'report.json').read_text())
    require(cpu['status']=='PASS_CPU_IDLE_ENGINEERING_ONLY_POLICY'and cpu['joint_action']==80
        and cpu['CUDA_initialized']is False,'CPU verified stationary engineering checkpoint required')
    close=json.loads((cpu_dir/'positive-original-CPU-closeout.json').read_text())
    require(close['status']=='PASS_CPU_IDLE_ENGINEERING_ONLY_POLICY_AND_OWNED_CLOSEOUT','Actual CPU0 and owned closure required')
    checkpoint=cpu['checkpoint'];h.checked(checkpoint)
    selected=h.put(D/'selection.json',dict(schema='robotron-fullgame-evaluator-engineering-only-selection-v1',
        status='ENGINEERING_ONLY_NOT_LAUNCHED',created_unix_s=time.time(),engineering_only=True,
        checkpoint=checkpoint,CPU_report=h.pin(cpu_dir/'report.json'),CPU_closeout=h.pin(cpu_dir/'positive-original-CPU-closeout.json'),
        joint_action=80,wire_controls=[-1,-1],slots=list(range(4096,4128)),selected_complete_games=64,games_per_slot=2,
        slow_original_slot=4127,slow_speed='0.25',wall_limit_s=540,resource_runtime_limit_s=600,
        purpose='Real natural games plus per-slot early STOP/normal0/EOF/park/global64/current-v6 Main and owned-closeout integration.',
        scores_are_not_learning_quality=True,scientific_or_promotion=False))
    parent_dir=C/'fullgame-current-v6-health-engineering-original02/native-current-v6-source-original01'
    pp=json.loads((parent_dir/'source-preparation.json').read_text());parent=h.checked(pp['native']);original=parent.read_text();source=original;edits=[]
    def replace(old,new):
        nonlocal source
        require(source.count(old)==1,'Nonunique engineering integration anchor: '+old[:90])
        source=source.replace(old,new,1);edits.append((old,new))
    left=source.index("PAIR_SHA='");right=source.index('\n',left)
    replace(source[left:right],'PAIR_SHA='+repr(selected['sha256']))
    left=source.index('POLICIES=');right=source.index('\n',left)
    replace(source[left:right],'POLICIES='+repr(dict(engineering=dict(sha256=checkpoint['sha256'],clocks=cpu['clocks']))))
    replace("ROLES={'R1':'reference','C1':'candidate','R2':'reference','C2':'candidate'}","ROLES={'E1':'engineering'}")
    begin=source.index("    require(PAIR_SHA!='0'*64");end=source.index('    expected_validation=dict(',begin)
    replace(source[begin:end],"    require(job.get('engineering_only')is True and job.get('quality_leg')=='E1'\n"
        "        and job.get('stationary_CPU_report',{}).get('sha256')=="+repr(h.pin(cpu_dir/'report.json')['sha256'])+"\n"
        "        and job.get('stationary_CPU_closeout',{}).get('sha256')=="+repr(h.pin(cpu_dir/'positive-original-CPU-closeout.json')['sha256'])+"\n"
        "        and job.get('engineering_slow_slot')==4127 and job.get('engineering_slow_speed')=='0.25',\n"
        "        'Explicit CPU-qualified ENGINEERING_ONLY stationary policy and fixed slow original required')\n")
    begin=source.index('    require(PAIR_SHA not in (');end=source.index("    require(job.get('current_v6_health_source'",begin)
    replace(source[begin:end],'')
    replace("job['schema']=='robotron-compiled-quota64-quality-original-v1'",
        "job['schema']=='robotron-compiled-quota64-ENGINEERING-only-v1'")
    replace("job['wall_limit_s']==22200","job['wall_limit_s']==540")
    replace("type(job.get(k))is int and job[k]==22200","type(job.get(k))is int and job[k]==540")
    replace("CLIENT_IDLE_TIMEOUT_S==22200.0","CLIENT_IDLE_TIMEOUT_S==540.0")
    lua_parent=C/'full-game-retirement-source-only-original01-20261101/native-retirement-source-original01/full-tail-observation-watchdog22200_v1.lua'
    lua=lua_parent.read_text();require(lua.count('STALL_EXIT_SECS = 22200')==1,'Exact prospective Lua watchdog required')
    lua_target=D/'full-tail-observation-engineering-watchdog540_v1.lua';write(lua_target,lua.replace('STALL_EXIT_SECS = 22200','STALL_EXIT_SECS = 540',1).encode());lua_pin=h.pin(lua_target)
    replace("job['lua']['sha256']=='ef598421644706e9d97548489042fcf020f59c66710bc20f36f901e0b3097fca'",
        "job['lua']['sha256']=="+repr(lua_pin['sha256']))
    old="        argv.extend(['-'+option+'_directory',str(private/name)])\n    return argv"
    replace(old,"        argv.extend(['-'+option+'_directory',str(private/name)])\n"
        "    if int(private.name)==job['engineering_slow_slot']:\n"
        "        argv.extend(['-throttle','-speed',job['engineering_slow_speed']])\n"
        "    return argv")
    anchor="        metadata=actor.checkpoint_metadata\n"
    replace(anchor,anchor+"        import numpy as np\n"
        "        loaded_actions=[]\n"
        "        for batch in range(1,17):\n"
        "            actions=actor.act_batch(np.zeros((batch,actor.state_size),dtype=np.float32),[0.0]*batch)\n"
        "            require(actions==[(8,8,False)]*batch,'Actual compiled GPU engineering policy is not stationary')\n"
        "            loaded_actions.append(dict(batch=batch,actions=actions))\n"
        "        h.put(output/'original-compiled-engineering-idle-actions.json',dict(checkpoint=acquisition,checks=loaded_actions,engineering_only=True))\n")
    replace("schema='robotron-original-full-tail32-live-status-v1'","schema='robotron-original-fullgame-ENGINEERING32-live-status-v1'")
    replace("schema='robotron-compiled-quota64-quality-original-result-v1'","schema='robotron-compiled-quota64-ENGINEERING-original-result-v1'")
    replace("status='PASS_ALL32_COMMON_COMPILED_CERTIFIED_QUALITY_COHORT_AND_HOST_DRAIN'if complete else 'ORIGINAL_COMPILED_QUALITY32_INVALID_NO_RETRY'",
        "status='PASS_ENGINEERING_ONLY_ALL64_NATURAL_GAMES_AND_SLOT_RETIREMENT'if complete else 'ORIGINAL_ENGINEERING_INVALID_NO_RETRY'")
    replace('        quality_qualified=False,full_game_score_verified=False,learning_speed_gain_verified=False,',
        '        engineering_only=True,quality_qualified=False,full_game_score_verified=False,learning_speed_gain_verified=False,')
    restored=source
    for old,new in reversed(edits):
        if new:
            require(restored.count(new)==1,'Nonunique engineering reverse edit');restored=restored.replace(new,old,1)
        else:
            # Deleted historical candidate exclusions occur immediately before
            # the untouched current-health binding. Keep the original position.
            marker="    require(job.get('current_v6_health_source'"
            require(restored.count(marker)==1,'Reverse deletion marker differs');restored=restored.replace(marker,old+marker,1)
    require(restored==original,'Undeclared engineering native change')
    compile(source,'<finite-fullgame-ENGINEERING-only>','exec')
    target=D/'run_fullgame_ENGINEERING_only_v1.py';write(target,source.encode());runtime=h.pin(target)
    original_ast=ast.parse(original);new_ast=ast.parse(source);stable=[]
    for item in original_ast.body:
        if isinstance(item,(ast.ClassDef,ast.FunctionDef))and item.name not in('run','validate_job','actor_command'):
            other=next(n for n in new_ast.body if getattr(n,'name',None)==item.name)
            require(ast.dump(item)==ast.dump(other),'Unrelated original kernel changed');stable.append(item.name)
    template=B/'quality32-protected1741-vs-currentLR125-quota64Protocol-firstSave-original01-preparation-20261024/native-current197-job-template.json'
    job=json.loads(template.read_text());latest=json.loads((C/'C1/job.json').read_text());health_job=json.loads((C/'fullgame-current-v6-health-engineering-original02/job.json').read_text())
    retirement=json.loads((C/'full-game-retirement-source-only-original01-20261101/native-retirement-source-original01/source-preparation.json').read_text())
    components=job['quota64_source_pins'];components.update(bridge=retirement['components']['full_startup_proxy_slot_retirement_v1.py'],
        slot_retirement=retirement['components']['slot_quota_retirement_v1.py'],slot_closeout=retirement['components']['slot_retirement_closeout_v1.py'])
    family=h.put(D/'selected-source-family.json',dict(engineering_only=True,native=runtime,parent_native=pp['native'],
        quota64_components=components,current_v6_health_source=pp['current_health_source'],
        current_v6_health_engineering=pp['current_health_engineering_review'],Lua=lua_pin,
        stationary_policy_CPU=h.pin(cpu_dir/'report.json'),stationary_policy_closeout=h.pin(cpu_dir/'positive-original-CPU-closeout.json')))
    job.update(schema='robotron-compiled-quota64-ENGINEERING-only-v1',engineering_only=True,quality_leg='E1',quality_pair_precommit=selected,
        minimum_completed_games=50,expected_policy_clocks=cpu['clocks'],checkpoint=checkpoint,runtime=runtime,
        output=str(D/'runtime-original01'),label='ENGINEERING-IDLE80-quota64-original01-20261101',wall_limit_s=540,
        private_client_idle_timeout_s=540,private_parked_origin_timeout_s=540,private_lua_score_stall_timeout_s=540,
        private_score_stall_timeout_s=0,lua=lua_pin,lease=h.pin('/dev/shm/robotron-snapshot-smoke-gpu0.lock'),
        current_main=latest['current_main'],current_fleet=health_job['current_fleet'],screen_support=latest['screen_support'],
        current_v6_health_source=pp['current_health_source'],current_v6_health_qualification=pp['current_health_engineering_review'],
        source_family_manifest=family,stationary_CPU_report=h.pin(cpu_dir/'report.json'),stationary_CPU_closeout=h.pin(cpu_dir/'positive-original-CPU-closeout.json'),
        engineering_slow_slot=4127,engineering_slow_speed='0.25',sessions={str(k):secrets.token_hex(16)for k in range(4096,4128)},
        connections={str(k):secrets.token_hex(16)for k in range(4096,4128)})
    for key in ('main_sources','main_binding','main_health_protocol'):job.pop(key,None)
    pins=[runtime,checkpoint,job['source_package'],job['mame'],lua_pin,job['seed_runtime'],job['screen_support'],job['current_v6_health_source'],job['current_v6_health_qualification'],family,selected,job['stationary_CPU_report'],job['stationary_CPU_closeout'],*components.values(),*job['quota64_validation'].values(),*job['full_tail_predecessors'].values(),job['historical_startup_acceptance_scope'],job['validated_CPU_prefix'],*job['boot_seed']['inputs'],job['boot_seed']['module']]
    for key in ('job','original_membership','rolemap','physical_helper','source_authority'):pins.append(job['current_fleet'][key])
    pins.extend([job['current_fleet']['supervisor']['source'],job['current_main']['startup_authority'],job['current_main']['startup_held']])
    job['inputs']=list({pin['path']:pin for pin in pins}.values())
    jp=h.put(D/'job.json',job)
    controller=CPU.read_text();before=controller
    for old,new in [("props.get('CPUQuota')=='200%'","props.get('CPUQuota')=='1200%'"),("props.get('MemoryMax')=='4G'","props.get('MemoryMax')=='24G'"),("props.get('TasksMax','128')=='128'","props.get('TasksMax','512')=='512'")]:
        require(controller.count(old)==1,'Controller resource anchor changed');controller=controller.replace(old,new,1)
    ctl_target=D/'control_fullgame_ENGINEERING600_v1.py';write(ctl_target,controller.encode());ctl=load('_live_fullgame_engineering_ctl',ctl_target)
    config=dict(unit='robotron-fullgame-evaluator-engineering-original01-20261101.service',output=str(D/'execution-original01'),
        argv=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',runtime['path'],'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']],
        properties=['CPUQuota=1200%','MemoryMax=24G','MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=512','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[ctl.pin(p['path'])for p in [runtime,jp,*job['inputs']]],observation_s=660)
    cfg=h.put(D/'controller-config.json',config)
    packet=h.put(D/'prepared-ENGINEERING-only.json',dict(status='PREPARED_ENGINEERING_ONLY_NOT_QUALIFIED_OR_LAUNCHED',selection=selected,
        native=runtime,job=jp,controller=h.pin(ctl_target),controller_config=cfg,parent_native=pp['native'],parent_controller=h.pin(CPU),
        exact_native_declared_edits_reverse_to_parent=True,unchanged_AST_kernels=stable,native_declared_edits=len(edits),
        controller_only_three_resource_literals_changed=True,finite_wall_s=540,resource_runtime_s=600,
        stationary_CPU=h.pin(cpu_dir/'report.json'),stationary_CPU_closeout=h.pin(cpu_dir/'positive-original-CPU-closeout.json'),
        actual_native_MAME_or_GPU_launched=False,Main_or_scientific_policies_modified=False,promotion=False))
    print(json.dumps(dict(status='PREPARED_ENGINEERING_ONLY_NOT_QUALIFIED_OR_LAUNCHED',packet=packet)));return 0


if __name__=='__main__':raise SystemExit(main())
