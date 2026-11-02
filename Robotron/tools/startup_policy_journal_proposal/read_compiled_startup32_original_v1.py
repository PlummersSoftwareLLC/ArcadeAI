"""Once-only raw audit of the original compiled32 diagnostic against its scope.

No Torch, old test/reader main, permit issuance, game, promotion or main mutation.
Diagnostic prefix termination is kept separate from whole-game qualification.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
D=R/'compiled32-policy-startup-real-original01-preparation-20261022'
JOB_SHA='d121edc708344900ffb7b4c76bf2214dd56b9fc8bfa315cd366a641d2c9023fb'


def require(value,message):
    if not value:raise ValueError(message)


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def audit_slot(slot,entry,job,result,starts,games,read,pin):
    subject=dict(slot=slot,session=job['sessions'][str(slot)],connection=job['connections'][str(slot)])
    require(entry['actual_exit']==0 and entry['frames']==1200 and entry['handoff']is not None
        and birth(entry['pid'])!=entry['birth'],'Original slot exit/identity differs')
    actor_pin=pin(Path(job['output'])/'actors'/str(slot)/'original-actor.json')
    actor=read(actor_pin)
    require(actor['pid']==entry['pid']and actor['starttime_ticks']==entry['birth']
        and actor['proxy_port']==job['proxy_ports'][str(slot)]and actor['original_job']['sha256']==JOB_SHA
        and all(actor[k]==v for k,v in subject.items()),'Original actor/session/port binding differs')
    rows=[json.loads(line)for line in read(entry['files']['producer.jsonl'],False).splitlines()]
    require([r['event']for r in rows]==list(range(1,len(rows)+1))
        and all(all(type(r[k])is type(v)and r[k]==v for k,v in subject.items())for r in rows),
        'Original full producer event/subject stream differs')
    chunks=[r for r in rows if r['kind']=='raw_ROM_chunk']
    require([r['offset']for r in chunks]==list(range(0,0x19000,128)),'Whole loaded CPU ROM chunks required')
    image=b''.join(bytes.fromhex(r['data_hex'])for r in chunks)
    require(len(image)==102400 and hashlib.sha256(image).hexdigest()==job['loaded_rom_sha256'],'Actual whole CPU ROM differs')
    snapshots={r['sequence']:r for r in rows if r['kind']=='snapshot'}
    apps={r['sequence']:r for r in rows if r['kind']=='input_applied'}
    require(sorted(snapshots)==sorted(apps)==list(range(1,1201))
        and all(a['apply_ok']is a['socket_ok']is True and a['debug_bypass']is False for a in apps.values()),
        'Original1200 successful input/exchange pairs required')
    footer=rows[-1]
    require(footer==entry['footer']and footer['kind']=='footer'and footer['sequence']==1200
        and footer['failed']is False and not any(r['kind']=='fault'for r in rows),'Original complete footer differs')
    wire=[json.loads(line)for line in read(entry['files']['proxy.jsonl'],False).splitlines()]
    exchanges={r['sequence']:r for r in wire if r['kind']=='origin_exchange'}
    responses={r['sequence']:r for r in wire if r['kind']in ('before_authorizing_response','before_wrapped_response')}
    require(sorted(exchanges)==sorted(responses)==list(range(1,1201)),'Original1200 origin/action pairs required')
    for sequence,exchange in exchanges.items():
        payload=bytes.fromhex(exchange['original_payload_hex'])
        require(len(payload)==7597 and struct.unpack_from('>H',payload)[0]==1890 and payload[-4:]==bytes(4),
                'Original full preview-free1890 payload differs')
        before,after=exchange['before'],exchange['after']
        require(after['frames']-before['frames']==int(exchange['accepted'])
            and before['client_slot']==after['client_slot']==slot and after['eval_only']is True,
            'Original accepted ordinal or slot differs')
        response=bytes.fromhex(responses[sequence]['response_hex'])
        require(len(response)==48 and response[:4]==b'RSP1'and int.from_bytes(response[4:8],'big')==sequence
            and response[-6:]==bytes.fromhex(exchange['actual_action_hex'])
            and apps[sequence]['response_hex']==response.hex(),'Original action/application byte preservation differs')
        move,fire,source,advanced,level,difficulty=struct.unpack('>bbBBBB',response[-6:])
        require(-1<=move<=7 and -1<=fire<=7 and source in (0,4)and advanced==0 and level==1
                and difficulty==0x85,'Actual greedy wave1/difficulty5 action context differs')
    authorizations=[r for r in wire if r['kind']=='before_authorizing_response']
    readiness=[r for r in wire if r['kind']=='original_boot_coin_readiness']
    handoffs=[(i,r)for i,r in enumerate(wire)if r['kind']=='actual_policy_journal_handoff']
    require(len(authorizations)==len(readiness)==len(handoffs)==1,'Unique original first-start chain required')
    handoff_index,handoff=handoffs[0];state=entry['handoff'];jid=state['journal_game_id']
    require(jid in starts and jid in games and handoff['result']==state,'Original journal/handoff join differs')
    start=starts[jid];certificate=start['context']['startup_certificate'];identifier=certificate['identifier']
    body={k:v for k,v in certificate.items()if k!='identifier'}
    require(hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==identifier
        and handoff['certificate']==body and identifier==state['certificate_identifier'],
        'Original immutable journal certificate bytes differ')
    require(all(body[k]==v for k,v in subject.items())and body['policy']==result['policy_before']
        and body['admission']==result['_admission']and body['loaded_rom_sha256']==job['loaded_rom_sha256'],
        'Actual policy/window/ROM/subject join differs')
    application,gate,setup,initialized,origin=[body['evidence'][k]for k in
        ('application','gate','setup','initialization','origin_acceptance')]
    for record in (application,gate,setup):require(rows[record['event']-1]==record,'Raw application/gate/setup differs')
    authorize_sequence=authorizations[0]['sequence'];init_sequence=initialized['sequence']
    require(application['sequence']==authorize_sequence and authorize_sequence<=gate['sequence']<authorize_sequence+3
        and gate['sequence']<=setup['sequence']<init_sequence<footer['first_play_sequence']<=1200
        and application['event']<gate['event']<setup['event']<initialized['event']
        and gate['sequence']==footer['gate_sequence']and setup['sequence']==footer['setup_sequence']
        and init_sequence==footer['initialized_sequence']==handoff['sequence'],
        'Actual original first-start phases are unordered or after play')
    require(application['nonce']==body['nonce']and application['start']==1 and application['coin']==0
        and application['held_start_before_response']is False
        and all(a['start']==0 for sequence,a in apps.items()if sequence<authorize_sequence),
        'First authorization did not precede the first physical START')
    require(gate['address']==0x9840 and gate['instruction_pc']==0x2715 and gate['instruction_hex']=='9740'
        and gate['a']==gate['data']==gate['last_start']==1 and setup['address']==0x9859
        and setup['instruction_pc']==0x2751 and setup['instruction_hex']=='9759'and setup['a']==setup['data']==127
        and all(r['nonce']==body['nonce']and r['dp']==0x98 and r['bank_entry']==1 and r['mask']==255
            and r['last_apply_ok']is r['last_socket_ok']is True for r in (gate,setup)),
        'Distinct accepted START gate/setup or actual inputs differ')
    raw_init=snapshots[init_sequence];exchange=exchanges[init_sequence]
    require(raw_init['event']==initialized['event']and raw_init['score_hex']=='00000000'
        and raw_init['wave']==1 and raw_init['reserves']==2 and raw_init['player_count']==raw_init['current_player']==1
        and raw_init['status']&1 and raw_init['first_play_sequence']==-1 and raw_init['nonce']==body['nonce'],
        'Actual one-player initialized snapshot before play differs')
    first=snapshots[footer['first_play_sequence']]
    require(first['status']&1==0 and first['wave']==1 and first['reserves']>0
        and first['player_count']==first['current_player']==1,'Actual first-play snapshot differs')
    require(origin['accepted']is True and origin['client_slot']==slot and origin['frame_sequence']==init_sequence
        and origin['accepted_frames']==exchange['after']['frames']and exchange['accepted']is True
        and origin['game_uid']==exchange['after']['game_uid']and origin['raw_payload_sha256']==
        hashlib.sha256(bytes.fromhex(exchange['original_payload_hex'])).hexdigest(),'Actual origin accepted-frame join differs')
    latch_index=next(i for i,r in enumerate(wire)if r['kind']=='before_wrapped_response'and r['sequence']==init_sequence)
    require(handoff_index<latch_index and bytes.fromhex(responses[init_sequence]['response_hex'])[8]&2,
            'Journal transition did not precede next action')
    ready=readiness[0]['readiness'];raw_ready=snapshots[authorize_sequence]
    require(readiness[0]['sequence']==authorize_sequence and ready['ready_sequence']==authorize_sequence
        and ready['ready_snapshot_event']==raw_ready['event']and ready['game_start_proven']is False
        and raw_ready['status']==243 and raw_ready['credit']>0
        and raw_ready['credit']&15<=9 and raw_ready['credit']>>4<=9
        and ready['clear']['event']<ready['initialized']['event']<ready['coin_applications'][0]['event']
        <ready['accepted_coin_STATUS']['event']<raw_ready['event'],'Original boot/coin readiness differs')
    require(raw_ready['score_hex']=='00000000'and raw_ready['wave']==raw_ready['reserves']==0
        and raw_ready['player_count']==2 and raw_ready['current_player']==0
        and raw_ready['mode']=='gated'and raw_ready['nonce']=='0'*64,'Original raw ready state differs')
    for record in [ready['clear'],ready['initialized'],ready['accepted_coin_STATUS'],*ready['coin_applications']]:
        require(rows[record['event']-1]==record,'Ready evidence does not match original raw prefix')
    require(ready['clear']['instruction_pc']==0xd137 and ready['clear']['instruction_hex']=='6f80'
        and ready['clear']['data']==0 and ready['initialized']['instruction_pc']==0xd184
        and ready['initialized']['instruction_hex']=='0359'and ready['initialized']['data']==255
        and ready['accepted_coin_STATUS']['instruction_pc']==0x79c4
        and ready['accepted_coin_STATUS']['instruction_hex']=='9759'and ready['accepted_coin_STATUS']['credit']==1,
        'Actual ROM boot/first accepted coin1 anchors differ')
    for record in (ready['clear'],ready['initialized'],ready['accepted_coin_STATUS']):
        require(record['address']==0x9859 and record['dp']==0x98 and record['bank_entry']==1
            and record['mask']==255 and record['last_start']==0 and record['nonce']=='0'*64
            and record['last_apply_ok']is record['last_socket_ok']is True,'Original boot/coin write context differs')
    require(ready['accepted_coin_STATUS']['data']==ready['accepted_coin_STATUS']['a']==243,
            'Actual accepted-coin STATUS write differs')
    for coin in ready['coin_applications']:
        response=bytes.fromhex(coin['response_hex'])
        require(coin['start']==0 and coin['coin']==1 and coin['socket_ok']is coin['apply_ok']is True
            and coin['held_start_before_response']is coin['debug_bypass']is False and coin['nonce']=='0'*64
            and len(response)==48 and response[:4]==b'RSP1'and response[8:10]==b'\0\1'
            and response[10:42]==bytes(32),'Actual original physical coin response/application differs')
    admission=body['admission']
    require(admission['open_unix_ns']<=body['lower_before_send_unix_ns']<=body['upper_after_receive_unix_ns']
        <admission['close_unix_ns']and admission['close_unix_ns']-admission['open_unix_ns']==90_000_000_000
        and body['lower_monotonic_ns']<=exchange['after_original_action_monotonic_ns']<=body['upper_monotonic_ns']
        and abs((body['upper_after_receive_unix_ns']-body['lower_before_send_unix_ns'])
        -(body['upper_monotonic_ns']-body['lower_monotonic_ns']))<=50_000_000,'Actual host clock bracket differs')
    old,new=games[state['previous_journal_game_id']],games[jid]
    require(old['known_start']is old['complete']is old['eligible']is False
        and old['excluded_reason']=='startup_attachment'and old['start_reason']=='initial_attachment'
        and old['terminal_confirmation']is None and 'startup_certificate'not in old['start_context']
        and 'startup_certificate'not in old['end_context'],'Original unknown attachment was relabelled')
    require(old['journal_game_id']!=jid and old['game_uid']==new['game_uid']==origin['game_uid']
        and new['known_start']is True and new['start_reason']=='prospective_certified_first_start_v1'
        and new['start_context']['startup_certificate']==certificate and new['first_play_level']==1
        and new['client_slot']==start['client_slot']==slot,'Prospective first-start journal identity differs')
    if not new['complete']:
        require(new['eligible']is False and new['excluded_reason']=='disconnect'
            and new['terminal_confirmation']is None,'Incomplete diagnostic tail became eligible')
    return dict(slot=slot,original_actor=actor_pin,pid=entry['pid'],birth=entry['birth'],actual_exit=0,
        certificate_identifier=identifier,nonce=body['nonce'],client_id=origin['client_id'],game_uid=origin['game_uid'],
        journal_game_id=jid,previous_journal_game_id=old['journal_game_id'],authorizing_sequence=authorize_sequence,
        gate_sequence=gate['sequence'],setup_sequence=setup['sequence'],initialized_sequence=init_sequence,
        first_play_sequence=footer['first_play_sequence'],host_bracket_ms=(body['upper_monotonic_ns']-body['lower_monotonic_ns'])/1e6,
        original_snapshots=1200,original_exchanges=1200,original_applications=1200,
        original_files=entry['files'],complete_game_score_qualified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--observe',action='store_true')
    args=parser.parse_args()
    if not args.observe:print('PLAN_ONLY: no reads, outputs, GPU, game or policy decisions');return 0
    helper=R/'quality32-reference1597-vs-production1741-original01-preparation-20261021/winner-protection-original01-preparation-20261022/readback-original-final-disposition-v1.py'
    require(hashlib.sha256(helper.read_bytes()).hexdigest()=='bae9e9c3e5eb552322285dc2422d5edd95549273aef58125e187f2305085fcdf',
            'Pure original helper definitions changed')
    spec=importlib.util.spec_from_file_location('_all32_raw_helpers',helper)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    output=D/'original-all32-compiled-policy-startup-independent-readback.json'
    require(not output.exists(),'Original raw audit already consumed')
    intent=m.put(D/'original-all32-raw-readback-intent.json',(json.dumps(dict(source=m.pin(__file__),
        job=m.pin(D/'job.json'),original_attempt=1,no_retry=True,unix_s=time.time()),indent=2)+'\n').encode())
    reader=m.load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','_all32_immutable_reader')
    rt=m.load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_all32_native_lifecycle')
    control=m.load(G/'tools/startup_policy_journal_proposal/control_compiled_startup32_v2.py',
        '62aabf37700af5baf65742bf7a55798968d08f0da4dd82afb6c489bd6344e709','_all32_control_defs')
    read=lambda entry,as_json=True:reader.read_pin(entry,as_json=as_json)
    jp=m.pin(D/'job.json');require(jp['sha256']==JOB_SHA,'Actual original compiled32 job differs');job=read(jp)
    require(job['actor_slots']==list(range(4096,4128))
        and job['gpu_uuid']=='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
        and job['loaded_rom_sha256']=='299e70420f317a4a7a1c3d62c0c6ab76f4f4806f1d0cd033901bdd551e1995ee'
        and job['validated_CPU_prefix']['sha256']=='7d0cc6f960626fef0b9c0a6c40f68f9dcb55fa98d351c6b25111792156cdb647'
        and len(set([*job['sessions'].values(),*job['connections'].values()]))==64,
        'Fixed all32 private GPU/ROM/predecessor/identity scope differs')
    acceptance=read(job['acceptance_scope'])
    require(job['acceptance_scope']['sha256']=='692b5c0572d32ffae79b828eb64296c09eaa6b4e59de28ea9316b7f44a59fc77'
        and acceptance['schema']=='robotron-compiled32-startup-prefix-precommitted-acceptance-v1',
        'Original precommitted acceptance scope differs')
    cp=m.pin(D/'controller-original-result.json');controller=read(cp)
    op=m.pin(D/'execution-original01/root-original-identity.json');owner=read(op)
    require(controller['actual_exit']==0 and controller['original_attempt']==1 and controller['no_retry']is True,
            'Original controller actual outcome differs')
    closure=read(controller['closure']);fields=rt.archived_closure(closure,owner,read,exit_zero=True)
    require(rt.duration_seconds(fields['CPUQuotaPerSecUSec'])==12 and fields['MemoryMax']==str(16<<30)
        and fields['MemorySwapMax']=='0'and rt.duration_seconds(fields['RuntimeMaxUSec'])==900
        and fields['TasksMax']=='512'and rt.duration_seconds(fields['TimeoutStopUSec'])==30
        and fields['KillMode']=='mixed'and fields['SendSIGKILL']=='no'and fields['Restart']=='no',
        'Original compiled32 resource scope differs')
    require(birth(owner['pid'])!=owner['starttime_ticks']
        and not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',owner['unit']).exists(),
        'Original native birth or cgroup remains')
    for unit in (owner['unit'],owner['timer']):require(control.show(unit)['LoadState']=='not-found','Original owned unit remains')
    rp=m.pin(Path(job['output'])/'result.json');result=read(rp)
    require(result['complete']is True and result['errors']==[]
        and result['status']=='PASS_ALL32_COMMON_COMPILED_STARTUP_HANDOFF_PREFIX_ONLY'
        and result['original_lease_released']is True and result['immutable_inputs_unchanged']is True,
        'Original runtime did not pass')
    for entry in job['inputs']+[result['acquired_checkpoint']]:require(m.pin(entry['path'])==entry,'Original bound input changed')
    package=read(job['source_package']);require(len(package['files'])==123,'Exact profile06 closure required')
    for relative,sha in package['files'].items():
        require(m.pin(Path(package['root'])/relative)['sha256']==sha,'Original profile source changed')
    policy=result['policy_before'];require(policy==result['policy_after'],'Loaded policy/clocks changed')
    require(policy['checkpoint_sha256']==job['checkpoint']['sha256']=='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
        and policy['training_enabled']is policy['replay_enabled']is False
        and [policy[k]for k in ('learner_frame_count','training_steps','optimized_samples')]==[1741229950,7128160,27621148672],
        'Original strict frozen policy lineage differs')
    numeric=policy['numeric_policy']
    require(numeric['compiled']is True and numeric['backend']=='inductor'and numeric['device']=='cuda:0'
        and numeric['weights']==numeric['inputs']==numeric['support']=='float32'and numeric['autocast']is False
        and numeric['warm_shapes']==list(range(1,17))and numeric['max_batch_size']==16
        and numeric['serving_thread_checked']is True and numeric['graph_breaks']==0,
        'Common actual compiled fp32 backend differs')
    loaded=read(m.pin(Path(job['output'])/'original-loaded-policy.json'))
    stopped=read(m.pin(Path(job['output'])/'before-intentional-prefix-stop.json'))
    require(loaded['gpu_uuid']==job['gpu_uuid']==loaded['CUDA_VISIBLE_DEVICES']
        and loaded['policy']==stopped['policy']==policy and loaded['compile_report']==stopped['compile_report']
        and loaded['compile_report']['all_shapes_verified']==list(range(1,17))
        and loaded['memory_is_none']is loaded['optimizer_is_none']is True and loaded['replay_enabled']is False,
        'Original compiled policy/graph isolation differs')
    result['_admission']=read(m.pin(Path(job['output'])/'original-fixed-admission.json'))
    start_rows=[json.loads(line)for line in read(result['journal']['measurement_starts.jsonl'],False).splitlines()]
    game_rows=[json.loads(line)for line in read(result['journal']['games.jsonl'],False).splitlines()]
    starts={r['journal_game_id']:r for r in start_rows};games={r['journal_game_id']:r for r in game_rows}
    require(len(starts)==len(start_rows)and len(games)==len(game_rows),'Original journal IDs duplicated')
    require(set(result['original_slots'])=={str(s)for s in range(4096,4128)},'Exact all32 original slots required')
    audits=[audit_slot(slot,result['original_slots'][str(slot)],job,result,starts,games,read,m.pin)
            for slot in range(4096,4128)]
    for key in ('pid','certificate_identifier','nonce','client_id','game_uid','journal_game_id'):
        require(len({r[key]for r in audits})==32,'All32 distinct original '+key+' required')
    require({r['journal_game_id']for r in audits}.issubset(starts)
        and len([r for r in start_rows if 'startup_certificate'in r['context']])==32,
        'Exactly32 original prospective first-start certificates required')
    before,after=result['before_intentional_stop'],result['after_intentional_stop']
    require(set(before['started_ids'])==set(after['started_ids'])==set(starts)
        and before['abandoned']==0 and before['count']+before['pending']==before['started']
        and after['pending']==0 and after['count']+after['abandoned']==after['started']
        and before['started_actor_slots']==list(range(4096,4128)),
        'Admitted tails disappeared or were silently filtered')
    require(result['controller_exit']['valid']is False
        and result['controller_exit']['reason']=='controller_exit_before_cohort_complete',
        'Diagnostic incomplete-prefix exit became a quality measurement')
    supervision=m.load(job['main_sources']['supervision']['path'],job['main_sources']['supervision']['sha256'],'_all32_main_census')
    window=m.load(job['main_sources']['window']['path'],job['main_sources']['window']['sha256'],'_all32_main_health')
    main=read(job['main_binding']);main_policy=read(main['supervision_policy']);baseline=read(main['baseline_API'])
    require(len(result['main_samples'])>=3,'Original pre/post main snapshots required')
    health=[]
    for sample in result['main_samples']:
        census=read(sample['snapshot']);api=read(sample['raw_API'])
        state=supervision.validate_snapshot(main_policy,census,api['client_count'])
        require(state['full_capacity']and not state['pending']and not state['completed_episodes'],
                'Original all192 unchanged actor census differs')
        window.healthy(api,baseline,main['experiment'],sample['unix_s'])
        require(api['learner_frame_count']==sample['learner_frames']and api['training_steps']==sample['training_steps'],
                'Original main clocks differ from raw API')
        health.append(dict(learner_frames=sample['learner_frames'],training_steps=sample['training_steps'],
            unix_s=sample['unix_s'],snapshot=sample['snapshot'],raw_API=sample['raw_API']))
    require(all(health[i+1]['learner_frames']>=row['learner_frames']and health[i+1]['training_steps']>=row['training_steps']
        for i,row in enumerate(health[:-1]))and health[-1]['learner_frames']>health[0]['learner_frames'],
        'Main did not continue forward')
    for path,sha in main['held_hashes'].items():require(m.pin(path)['sha256']==sha,'Original main held source changed')
    require(m.pin(job['lease']['path'])==job['lease'],'Permanent coordinator bytes/identity changed')
    import fcntl
    fd=os.open(job['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    require(m.pin(job['lease']['path'])==job['lease'],'Coordinator probe changed original inode')
    for port in [19998,*range(20000,20032)]:
        with socket.socket()as probe:probe.bind(('127.0.0.1',port))
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],
        capture_output=True,text=True,timeout=10)
    require(gpu.returncode==0 and job['gpu_uuid']not in gpu.stdout,'Private GPU0 remains occupied')
    for entry in job['inputs']+[result['acquired_checkpoint']]:require(m.pin(entry['path'])==entry,'Final bound input differs')
    require('torch'not in sys.modules,'Passive raw audit imported Torch')
    report=dict(schema='robotron-original-compiled32-startup-independent-readback-v1',
        status='PASS_ALL32_COMPILED_POLICY_ROM_START_BEFORE_PLAY_PROSPECTIVE_JOURNAL_FULL1200_MAIN192_ALL6_CLEANUP',
        observed_unix_s=time.time(),source=m.pin(__file__),intent=intent,job=jp,acceptance=job['acceptance_scope'],
        original_controller_result=cp,original_owner=op,original_closure=controller['closure'],original_result=rp,
        actual_runtime_exit=0,all32_original_MAME_exits=0,all6_original_descriptors_verified=True,
        actual_descriptor_exits=[r['exit']for r in closure['full_original_archives']],
        exact_original_native_actor_births_cgroup_service_timer_absent=True,private_GPU0_and_ports_idle=True,
        permanent_coordinator_preserved_and_unlocked=True,policy=policy,compile_report=loaded['compile_report'],
        slots=audits,original_snapshots=38400,original_applications=38400,original_exchanges=38400,
        all32_initializations_before_actual_first_play=True,all32_prospective_handoffs_before_next_action=True,
        every_unknown_attachment_preserved=True,all123_private_sources_and196_main_hashes_unchanged=True,
        main_observations=health,before_intentional_stop=before,after_intentional_stop=after,
        all_admitted_games_retained=True,actual_policy_loaded=True,quality_qualified=False,
        full_game_score_verified=False,learning_speed_gain_verified=False,main_runtime_changed=False,
        quality_protocol_changed=False,old_test_or_reader_rerun=False,
        limitations='32 common compiled-GPU1200-frame prefixes. Deliberate termination leaves incomplete games and an invalid whole-cohort controller, as recorded. No paired score/throughput comparison or complete-game promotion. Full tails and a separately precommitted quality protocol still required.')
    proof=m.put(output,(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(dict(readback=proof,status=report['status'],quality_qualified=False)),flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
