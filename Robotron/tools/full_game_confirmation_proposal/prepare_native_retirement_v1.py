"""Prepare an UNBOUND full-game native with per-slot retirement integration.

Original quota64, full-tail, Lua STOP and owned cleanup kernels remain. The old
pair is deliberately unbound, so this source cannot launch a scientific job.
Current-v6 Main health, new policy selection/prebody, an actual engineering
integration and independent raw review remain necessary before future binding.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
P=B/'future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-protocol-interface-correction-original01/run_quality32_quota64_selected_original01_v2.py'
PARENT_SHA='9ecf99ba66b76b8bd31de06e894124e495d3fedba86ba5a1c36db628ccb95f83'
LUA=B/'full-tail-wire-v2-contract-original01-preparation-20261022/full-tail-observation-main.lua'
LUA_SHA='b6869212245eb88057251d04ba70fa9800587f66b5de33ca534eecca8294f2b0'
TOOLS=Path(__file__).parent


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,raw):
    with path.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)


def prepare(directory,proxy_directory,h):
    require(directory.is_absolute()and not directory.exists(),'Fresh absolute preparation directory required')
    require(sha(P)==PARENT_SHA and sha(LUA)==LUA_SHA,'Original full-game source changed')
    proxy_preparation=json.loads((proxy_directory/'source-preparation.json').read_text())
    proxy_source=h.checked(proxy_preparation['source'])
    proxy_tests=json.loads((proxy_directory/'CPU-contracts-original01.json').read_text())
    require(proxy_tests['status']=='PASS'and proxy_tests['tests_run']==7,'Original parked-proxy CPU contracts required')
    require(sha(proxy_source)==proxy_tests['source']['sha256'],'Tested parked proxy differs')
    authority=TOOLS/'slot_quota_retirement_v1.py';closeout=TOOLS/'slot_retirement_closeout_v1.py'
    require(sha(authority)=='78c1ed55490690d2fb18268fe2d8616251031a4692c1a8fb08a5cb22f54820e6',
        'Exact tested slot authority required')
    directory.mkdir(mode=0o700)
    copies={}
    for source in [proxy_source,authority,closeout]:
        target=directory/source.name;write(target,source.read_bytes());copies[source.name]=h.pin(target)
    lua_text=LUA.read_text();require(lua_text.count('STALL_EXIT_SECS = 180')==1,'Original Lua score watchdog anchor differs')
    lua_target=directory/'full-tail-observation-watchdog22200_v1.lua'
    write(lua_target,lua_text.replace('STALL_EXIT_SECS = 180','STALL_EXIT_SECS = 22200',1).encode())
    lua_pin=h.pin(lua_target)
    source=P.read_text();edits=[]
    def replace(old,new):
        nonlocal source
        require(source.count(old)==1,'Nonunique native integration anchor: '+old[:100])
        source=source.replace(old,new,1);edits.append((old,new))
    replace("PAIR_SHA='63000cf3441f085e8b297d9c589f19e7147c7213a07288e644c420089e497dc3'",
        "PAIR_SHA='"+'0'*64+"'  # UNBOUND: fresh current-Main health/policy/engineering selection required")
    old_bridge="BRIDGE_COMPONENTS=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/native-source-family-original01')"
    replace(old_bridge,'BRIDGE_COMPONENTS=Path('+repr(str(directory))+')')
    replace("bridge='af47c3dac80cc3888023e5ce8fb62b4b0934fab1df7576719adad4ef373832ca')",
        'bridge='+repr(copies[proxy_source.name]['sha256'])+',\n'
        '        slot_retirement='+repr(copies[authority.name]['sha256'])+',\n'
        '        slot_closeout='+repr(copies[closeout.name]['sha256'])+')')
    anchor="    require('acceptance_scope'not in job\n"
    replace(anchor,"    require(all(type(job.get(k))is int and job[k]==22200 for k in\n"
        "        ('private_client_idle_timeout_s','private_parked_origin_timeout_s','private_lua_score_stall_timeout_s'))\n"
        "        and type(job.get('private_score_stall_timeout_s'))is int and job['private_score_stall_timeout_s']==0\n"
        "        and job['lua']['sha256']=="+repr(lua_pin['sha256'])+",'Exact matched full-game parked/idle/score-only watchdog policy required')\n"+anchor)
    replace('    drain=None;drain_lock=threading.Lock();drain_payload=None;drain_identifier=None',
        '    drain=None;drain_lock=threading.Lock();drain_payload=None;drain_identifier=None;retirement_partition=None')
    replace("        sys.path.insert(0,str(root/'Scripts'));sys.path.insert(0,str(HERE))",
        "        os.environ['DQN_CLIENT_IDLE_TIMEOUT_S']=str(job['private_client_idle_timeout_s'])\n"
        "        sys.path.insert(0,str(root/'Scripts'));sys.path.insert(0,str(HERE))")
    replace('        from dqn.socket_server import SocketServer,parse_frame_data',
        '        from dqn.socket_server import SocketServer,parse_frame_data,CLIENT_IDLE_TIMEOUT_S\n'
        "        require(CLIENT_IDLE_TIMEOUT_S==22200.0,'Actual private full-game idle lifetime differs')\n"
        "        config.RL_CONFIG.client_stall_timeout_s=job['private_score_stall_timeout_s']\n"
        "        require(config.RL_CONFIG.client_stall_timeout_s==0,'Private score-only watchdog remains enabled')")
    replace('        import full_startup_proxy_quota64_v1 as bridge',
        '        import full_startup_proxy_slot_retirement_v1 as bridge\n'
        '        import slot_quota_retirement_v1 as slot_retirement\n'
        '        import slot_retirement_closeout_v1 as slot_closeout')
    replace('                    drain=CohortDrain(server.game_journal,controller,subjects=subjects,\n'
        '                        policy_reader=policy_reader,admission_reader=admission)',
        '                    drain=slot_retirement.SlotQuotaRetirement(CohortDrain(\n'
        '                        server.game_journal,controller,subjects=subjects,\n'
        '                        policy_reader=policy_reader,admission_reader=admission))')
    replace('                drain_reader=drain_reader)',
        "                drain_reader=lambda slot=slot:None if drain_reader()is None else drain_reader().for_slot(slot),\n"
        "                parked_origin_timeout_s=job['private_parked_origin_timeout_s'])")
    replace("        certified={row['proxy'].handoff['journal_game_id']for row in actors.values()}",
        "        certified={row['proxy'].handoff['journal_game_id']for row in actors.values()}\n"
        '        retirement_partition=slot_closeout.validate(drain,before_stop,actors,\n'
        '            drain_payload=drain_payload,drain_identifier=drain_identifier)')
    replace("            and drain.permit.used_slots==set(SLOTS),'All32 first certificates and every admitted completed game required')",
        "            and retirement_partition['complete']is True,'All32 first certificates and every admitted completed game required')")
    replace('        drain_identifier=drain_identifier,drain_payload=drain_payload,\n        journal=journal,',
        '        drain_identifier=drain_identifier,drain_payload=drain_payload,\n'
        '        slot_retirement_closeout=retirement_partition,\n'
        "        private_parked_origin_timeout_s=job['private_parked_origin_timeout_s'],\n"
        "        private_client_idle_timeout_s=job['private_client_idle_timeout_s'],\n"
        "        private_score_stall_timeout_s=job['private_score_stall_timeout_s'],\n"
        "        private_lua_score_stall_timeout_s=job['private_lua_score_stall_timeout_s'],\n"
        '        journal=journal,')
    restored=source
    for old,new in reversed(edits):
        require(restored.count(new)==1,'Nonunique reverse native integration anchor')
        restored=restored.replace(new,old,1)
    require(restored==P.read_text(),'Undeclared native change')
    compile(source,'<future-unbound-slot-retirement-native>','exec')
    original_ast=ast.parse(P.read_text());future_ast=ast.parse(source)
    stable=['actor_environment','actor_command','PrivateLease','process_birth','await_original_actor_exits',
        'finalize_actor_outputs','persist_main_observation','validate_lifecycle','validate_main_health_contract']
    for name in stable:
        left=next(n for n in original_ast.body if getattr(n,'name',None)==name)
        right=next(n for n in future_ast.body if getattr(n,'name',None)==name)
        require(ast.dump(left)==ast.dump(right),'Original ownership/Lua/health kernel changed: '+name)
    target=directory/'run_quality32_slot_retirement_UNBOUND_v1.py';write(target,source.encode())
    report=dict(status='UNBOUND_NATIVE_SOURCE_ONLY_NOT_LAUNCHABLE',parent=h.pin(P),native=h.pin(target),
        generator=h.pin(Path(__file__)),components=copies,lua=lua_pin,original_lua=h.pin(LUA),
        exact_reverse_edit_equals_original=True,unchanged_AST_kernels=stable,declared_edit_count=len(edits),
        original_global64_guard_retained=True,per_slot_two_complete_games_and_32_STOPs_separately_required=True,
        original_global_STOP_consumption_history_never_fabricated=True,
        active_transport_timeout_s=5,post_STOP_peer_EOF_timeout_s=30,
        matched_parked_origin_and_private_idle_and_Lua_watchdog_s=22200,private_score_only_server_watchdog_s=0,
        old_pair_deliberately_unbound=True,old_Main_health_contract_deliberately_not_requalified=True,
        remaining_before_launch=['Fresh current-v6 Main health binding and qualified observer/source family.',
            'Fresh exact policy/CPU/pair/source/resource prebody and namespace/controller bindings.',
            'Independent review of32 retirement receipts plus unchanged all64 completion; finite real-MAME engineering integration after original50607 closes.',
            'Separate fresh R1/R2 versus C1/C2 complete-game promotion gates, no cutoff substitution or scientific retries.'],
        actual_GPU_MAME_native_body_or_scientific_job_launched=False,live_controls_changed=False,promotion=False)
    pin=h.put(directory/'source-preparation.json',report);print(json.dumps(dict(status=report['status'],report=pin)))
    return pin


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--directory',type=Path);parser.add_argument('--proxy-directory',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    require(args.directory is not None and args.proxy_directory is not None,'Fresh directory and tested proxy directory required')
    h=load('_native_slot_retirement_prepare_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    prepare(args.directory,args.proxy_directory,h);return 0


if __name__=='__main__':raise SystemExit(main())
