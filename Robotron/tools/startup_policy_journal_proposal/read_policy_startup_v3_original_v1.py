"""Once-only independent raw reconciliation of the closed CPU/eager v3 case.

This reads immutable artifacts. It never imports Torch, creates a permit,
executes a game/reviewer/old guard, mutates a journal or promotes a policy.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
D=R/'accumulated-credit-full-policy-CPU-real-original01-preparation-20261022'
JOB_SHA='5add2a8701fdc0dc370886ce648ad9d18c35e9975942b2764584147bc60ca611'


def require(value,message):
    if not value:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe',action='store_true');args=parser.parse_args()
    if not args.observe:print('PLAN_ONLY: no reads, outputs or execution');return 0
    helper=R/'quality32-reference1597-vs-production1741-original01-preparation-20261021/winner-protection-original01-preparation-20261022/readback-original-final-disposition-v1.py'
    require(hashlib.sha256(helper.read_bytes()).hexdigest()=='bae9e9c3e5eb552322285dc2422d5edd95549273aef58125e187f2305085fcdf','Pinned pure helper differs')
    spec=importlib.util.spec_from_file_location('_v3_readback_helpers',helper)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    output=D/'original-policy-loaded1200-prospective-handoff-independent-readback.json'
    require(not output.exists(),'Original readback already consumed')
    intent=m.put(D/'original-raw-readback-intent.json',(json.dumps(dict(source=m.pin(__file__),
        job=m.pin(D/'job.json'),original_attempt=1,no_retry=True,unix_s=time.time()),indent=2)+'\n').encode())
    reader=m.load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','_v3_immutable_reader')
    rt=m.load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_v3_runtime_defs')
    control=m.load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py',
        '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_v3_control_defs')
    read=lambda entry,as_json=True:reader.read_pin(entry,as_json=as_json)
    jp=m.pin(D/'job.json');require(jp['sha256']==JOB_SHA,'Original v3 job differs');job=read(jp)
    cp=m.pin(D/'controller-original-result.json');controller=read(cp)
    op=m.pin(D/'execution-original01/root-original-identity.json');owner=read(op)
    closure=read(controller['closure'])
    require(controller['actual_exit']==0 and controller['original_attempt']==1
            and controller['no_retry']is True,'Original controller actual outcome differs')
    fields=rt.archived_closure(closure,owner,read,exit_zero=True)
    require(rt.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
        and fields['MemorySwapMax']=='0'and rt.duration_seconds(fields['RuntimeMaxUSec'])==180
        and fields['TasksMax']=='256'and rt.duration_seconds(fields['TimeoutStopUSec'])==5
        and fields['SendSIGKILL']=='no'and fields['Restart']=='no','Original resource scope differs')
    require(not Path('/proc',str(owner['pid'])).exists()
        and not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',owner['unit']).exists(),
        'Original runtime birth/cgroup remains')
    for unit in (owner['unit'],owner['timer']):require(control.show(unit)['LoadState']=='not-found','Owned unit remains')
    rp=m.pin(Path(job['output'])/'result.json');result=read(rp)
    require(result['complete']is True and result['status']=='PASS_ACTUAL_POLICY_STARTUP_HANDOFF_PREFIX_ONLY'
        and result['errors']==[]and result['original_MAME_exit']==0 and result['original_frames']==1200
        and result['immutable_inputs_unchanged']is True,'Actual diagnostic did not pass')
    require(not Path('/proc',str(result['original_MAME_pid'])).exists(),'Original MAME remains')
    for port in (19997,19998):
        with socket.socket()as probe:probe.bind(('127.0.0.1',port))
    for entry in job['inputs']+[result['acquired_checkpoint']]:require(m.pin(entry['path'])==entry,'Held input differs')
    package=read(job['source_package']);require(len(package['files'])==123,'Complete profile06 required')
    for relative,sha in package['files'].items():
        require(m.pin(Path(package['root'])/relative)['sha256']==sha,'Original profile source changed')
    rows=[json.loads(line)for line in read(result['files']['producer.jsonl'],False).splitlines()]
    require([r['event']for r in rows]==list(range(1,len(rows)+1)),'Original raw event sequence differs')
    subject={k:job[k]for k in ('session','connection')};subject['slot']=4096
    require(all(all(type(r[k])is type(v)and r[k]==v for k,v in subject.items())for r in rows),'Original raw subject differs')
    chunks=[r for r in rows if r['kind']=='raw_ROM_chunk']
    require([r['offset']for r in chunks]==list(range(0,0x19000,128)),'Whole CPU ROM chunks differ')
    image=b''.join(bytes.fromhex(r['data_hex'])for r in chunks)
    require(len(image)==102400 and hashlib.sha256(image).hexdigest()==job['loaded_rom_sha256'],
            'Whole actual loaded CPU ROM differs')
    prior_rom=read(job['prior_ROM_identity_proof'])
    require(prior_rom['full_loaded_CPU_ROM_region_sha256']==job['loaded_rom_sha256'],'Original all12-chip ROM binding differs')
    snapshots={r['sequence']:r for r in rows if r['kind']=='snapshot'}
    apps={r['sequence']:r for r in rows if r['kind']=='input_applied'}
    require(sorted(snapshots)==sorted(apps)==list(range(1,1201)),'Full1200 snapshot/application pairs required')
    require(all(r['socket_ok']is r['apply_ok']is True and r['debug_bypass']is False for r in apps.values()),
            'Original transport/application failed')
    footer=rows[-1]
    require(footer['kind']=='footer'and footer['sequence']==1200 and footer['failed']is False
        and not any(r['kind']=='fault'for r in rows),'Full original MAME footer differs')
    wire=[json.loads(line)for line in read(result['files']['proxy.jsonl'],False).splitlines()]
    exchanges={r['sequence']:r for r in wire if r['kind']=='origin_exchange'}
    responses={r['sequence']:r for r in wire if r['kind']in ('before_authorizing_response','before_wrapped_response')}
    require(sorted(exchanges)==sorted(responses)==list(range(1,1201)),'Full original exchange/response pairs required')
    for sequence,exchange in exchanges.items():
        payload=bytes.fromhex(exchange['original_payload_hex'])
        require(len(payload)==7597 and struct.unpack_from('>H',payload)[0]==1890
                and payload[-4:]==bytes(4),'Original full preview-free observation differs')
        before,after=exchange['before'],exchange['after']
        require(after['frames']-before['frames']==int(exchange['accepted']),'Original acceptance ordinal differs')
        response=bytes.fromhex(responses[sequence]['response_hex'])
        require(len(response)==48 and response[:4]==b'RSP1'and int.from_bytes(response[4:8],'big')==sequence
                and response[-6:]==bytes.fromhex(exchange['actual_action_hex'])
                and apps[sequence]['response_hex']==response.hex(),'Original action/application bytes differ')
        move,fire,source,advanced,level,difficulty=struct.unpack('>bbBBBB',response[-6:])
        require(-1<=move<=7 and -1<=fire<=7 and source in (0,4)
            and advanced==0 and level==1 and difficulty==0x85,'Actual greedy eval action context differs')
    authorizations=[r for r in wire if r['kind']=='before_authorizing_response']
    handoffs=[(i,r)for i,r in enumerate(wire)if r['kind']=='actual_policy_journal_handoff']
    readiness=[r for r in wire if r['kind']=='original_boot_coin_readiness']
    require(len(authorizations)==len(handoffs)==len(readiness)==1,'Unique original startup chain required')
    starts=[json.loads(line)for line in read(result['files']['journal/measurement_starts.jsonl'],False).splitlines()]
    games=[json.loads(line)for line in read(result['files']['journal/games.jsonl'],False).splitlines()]
    require(len(starts)==1 and len(games)==2,'Exact excluded attachment and distinct pending game required')
    start=starts[0];certificate=start['context']['startup_certificate']
    identifier=certificate['identifier'];body={k:v for k,v in certificate.items()if k!='identifier'}
    require(hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==identifier,
            'Original certificate digest differs')
    handoff_index,handoff=handoffs[0]
    require(handoff['certificate']==body and handoff['result']==result['actual_handoff']
            and identifier==result['actual_handoff']['certificate_identifier'],'Journal/certificate join differs')
    evidence=body['evidence'];application,gate,setup,initialized,origin=[evidence[k]for k in
        ('application','gate','setup','initialization','origin_acceptance')]
    for record in (application,gate,setup):require(rows[record['event']-1]==record,'Raw application/gate/setup differs from certificate')
    require(application['sequence']==authorizations[0]['sequence']==787
        and gate['sequence']==footer['gate_sequence']==788
        and setup['sequence']==footer['setup_sequence']==789
        and initialized['sequence']==footer['initialized_sequence']==handoff['sequence']==796
        and footer['first_play_sequence']==878,'Original accepted startup phases differ')
    require(gate['instruction_pc']==0x2715 and gate['instruction_hex']=='9740'and gate['address']==0x9840
        and gate['a']==gate['data']==gate['last_start']==1 and setup['instruction_pc']==0x2751
        and setup['instruction_hex']=='9759'and setup['address']==0x9859 and setup['a']==setup['data']==127,
        'Distinct accepted START gate/setup differs')
    require(application['event']<gate['event']<setup['event']<initialized['event']
        and all(r['nonce']==body['nonce']for r in (application,gate,setup,initialized)),
        'Raw nonce/order join differs')
    raw_init=snapshots[796]
    require(raw_init['event']==initialized['event']and raw_init['score_hex']=='00000000'
        and raw_init['wave']==1 and raw_init['reserves']==2 and raw_init['player_count']==raw_init['current_player']==1
        and raw_init['status']&1 and raw_init['first_play_sequence']==-1,'Actual before-play initialization differs')
    require(origin['accepted']is True and origin['frame_sequence']==796 and origin['accepted_frames']==796
        and exchanges[796]['accepted']is True and origin['game_uid']==exchanges[796]['after']['game_uid']
        and origin['raw_payload_sha256']==hashlib.sha256(bytes.fromhex(exchanges[796]['original_payload_hex'])).hexdigest(),
        'Original origin acceptance/payload differs')
    latch_index=next(i for i,r in enumerate(wire)if r['kind']=='before_wrapped_response'and r['sequence']==796)
    require(handoff_index<latch_index and bytes.fromhex(responses[796]['response_hex'])[8]&2,
            'Prospective journal transaction did not precede next action')
    policy=result['policy_before']
    require(policy==result['policy_after']==body['policy']and policy['checkpoint_sha256']==job['checkpoint']['sha256']
        =='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
        and policy['training_enabled']is policy['replay_enabled']is False
        and policy['numeric_policy']['device']=='cpu'and policy['numeric_policy']['compiled']is False,
        'Actual loaded frozen policy changed')
    require(policy['learner_frame_count']==1741229950 and policy['training_steps']==7128160
        and policy['optimized_samples']==27621148672,'Frozen policy clocks differ')
    admission=read(m.pin(Path(job['output'])/'original-fixed-admission.json'))
    require(admission==body['admission']and admission['open_unix_ns']<=body['lower_before_send_unix_ns']
        <=body['upper_after_receive_unix_ns']<admission['close_unix_ns']
        and admission['close_unix_ns']-admission['open_unix_ns']==90_000_000_000,
        'Actual host-clock bracket escapes fixed admission')
    require(body['lower_monotonic_ns']<=exchanges[796]['after_original_action_monotonic_ns']
        <=body['upper_monotonic_ns']and abs((body['upper_after_receive_unix_ns']-body['lower_before_send_unix_ns'])
        -(body['upper_monotonic_ns']-body['lower_monotonic_ns']))<=50_000_000,'Original host clocks disagree')
    old,new=games
    require(old['known_start']is old['complete']is old['eligible']is False
        and old['start_reason']=='initial_attachment'and old['excluded_reason']=='startup_attachment'
        and old['terminal_confirmation']is None and 'startup_certificate'not in old['start_context']
        and 'startup_certificate'not in old['end_context'],'Unknown attachment was relabelled')
    require(old['journal_game_id']!=new['journal_game_id']==start['journal_game_id']
        and old['game_uid']==new['game_uid']==origin['game_uid']and new['known_start']is True
        and new['start_reason']=='prospective_certified_first_start_v1'
        and new['start_context']['startup_certificate']==certificate and new['first_play_level']==1,
        'Distinct prospective start or unchanged ingest UID differs')
    require(new['complete']is new['eligible']is False and new['excluded_reason']=='disconnect'
        and new['terminal_confirmation']is None,'Intentional prefix end became a full game')
    before,after=result['before_intentional_stop'],result['after_intentional_stop']
    require([before[k]for k in ('started','count','pending','abandoned')]==[1,0,1,0]
        and [after[k]for k in ('started','count','pending','abandoned')]==[1,0,0,1]
        and result['controller_exit']['valid']is False
        and result['controller_exit']['reason']=='controller_exit_before_cohort_complete',
        'Diagnostic-only incomplete tail accounting differs')
    for entry in job['inputs']+[result['acquired_checkpoint']]:require(m.pin(entry['path'])==entry,'Final input changed')
    require('torch'not in sys.modules,'Passive readback imported Torch')
    report=dict(schema='robotron-policy-startup-v3-original-raw-independent-readback-v1',
        status='PASS_ACTUAL_PROTECTED_POLICY_ROM_START_BEFORE_PLAY_PROSPECTIVE_JOURNAL_FULL1200_ALL6_CLEANUP',
        observed_unix_s=time.time(),source=m.pin(__file__),intent=intent,job=jp,
        original_controller_result=cp,original_owner=op,original_closure=controller['closure'],
        actual_runtime_exit=0,actual_MAME_exit=0,all6_original_descriptors_verified=True,
        actual_descriptor_exits=[r['exit']for r in closure['full_original_archives']],
        exact_original_service_timer_actor_births_and_cgroup_absent=True,private_ports_idle=True,
        original_result=rp,raw_files=result['files'],policy=policy,host_clock_certificate=certificate,
        host_clock_bracket_ms=(body['upper_monotonic_ns']-body['lower_monotonic_ns'])/1e6,
        first_authorization_sequence=787,accepted_START_gate_sequence=788,later_setup_sequence=789,
        accepted_initialization_sequence=796,first_play_sequence=878,
        original_snapshots=1200,original_applications=1200,original_exchanges=1200,
        loaded_full_CPU_ROM_bytes=102400,loaded_full_CPU_ROM_sha256=job['loaded_rom_sha256'],
        actual_policy_loaded=True,actual_prospective_journal_handoff=True,
        unknown_attachment_preserved_excluded=True,distinct_journal_id_same_ingest_UID=True,
        handoff_before_next_action=True,before_intentional_stop=before,after_intentional_stop=after,
        all123_profile_sources_and_original_inputs_unchanged=True,
        full_game_score_verified=False,quality_qualified=False,quality_protocol_changed=False,
        learning_speed_gain_verified=False,main_runtime_changed=False,old_reader_or_guard_rerun=False,
        limitations='One original CPU/eager actor and1200 frames. The pending game was deliberately disconnected and is incomplete/ineligible. Common compiled GPU/all32-slot/full-tail validation and a separately precommitted quality protocol remain required.')
    proof=m.put(output,(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(dict(readback=proof,status=report['status'],quality_qualified=False)),flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
