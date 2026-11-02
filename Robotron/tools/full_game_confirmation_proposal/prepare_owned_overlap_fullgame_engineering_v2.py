"""Prepare one new stationary-policy evaluator engineering run, not an A/B retry."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G/'logs/managed-learning-20261015/run-26'
F = B/'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'
E = B/'post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031/fullgame-evaluator-live-engineering-original01-20261101'
O = F/'future-owned-overlap-observer-reviewer-original01'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write(path, data):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.execute:
        parser.print_help()
        return 0
    h = load('_prepare_owned_native_h', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    directory = args.output.resolve()
    directory.mkdir(mode=0o700)
    original = E/'native-engineering-original01'
    old_job = json.loads((original/'job.json').read_text())
    reviewed = O/'independent-CPU33-live20-readonly-review-original01.json'
    proof = json.loads(reviewed.read_text())
    assert proof['status'] == 'PASS_OWNED_OVERLAP_OBSERVER_CPU33_AND_LIVE20_REVIEW_ONLY'
    assert proof['outcome']['accepted'] == 20 and proof['outcome']['pending'] == 0
    health, owned = proof['observer'], proof['owned_helper']
    h.checked(health);h.checked(owned);h.checked(old_job['checkpoint'])
    selection = h.put(directory/'selection.json', dict(
        schema='robotron-owned-overlap-fullgame-ENGINEERING-selection-v1', engineering_only=True,
        created_unix_s=time.time(), checkpoint=old_job['checkpoint'],
        CPU_report=old_job['stationary_CPU_report'], CPU_closeout=old_job['stationary_CPU_closeout'],
        clocks=old_job['expected_policy_clocks'], joint_action=80, selected_games=64,
        slots=list(range(4096,4128)), games_per_slot=2, slow_slot=4127, slow_speed='0.25',
        wall_s=540, resource_s=600, observer=health, owned_overlap=owned,
        archival_closeout=h.pin(E/'slot-permit-archival-source-original02/slot_retirement_closeout_v2.py'),
        purpose='Actual evaluator/observer/full-permit/STOP integration only; no learning-policy result.',
        failed_scientific_campaign_retried=False, promotion=False))
    parent = h.checked(old_job['runtime'])
    assert hashlib.sha256(parent.read_bytes()).hexdigest() == '0b6a77127cac5247145f9bbbc250a8fabd30ab819c3c0ff7bfd05712d4998868'
    native = parent.read_text()
    edits = []

    def change(old, new):
        nonlocal native
        assert native.count(old) == 1, old[:100]
        native = native.replace(old, new, 1)
        edits.append((old,new))

    change("PAIR_SHA='841245ba593260563720e0b016390c8850f8fd0a923297ec619586f0ab51195f'",
           'PAIR_SHA='+repr(selection['sha256']))
    change('5e7efde5b458ab5dd6f7dba684b412d1cf0c998b62ec69b316f0b822c1d24d4a', health['sha256'])
    change('574b0d38bacab5724ad731e381274b6102d85fc6596b942518ac7e1cc65d4de3', h.pin(reviewed)['sha256'])
    change("        and all(type(job.get(k))is dict for k in ('current_main','current_fleet','source_family_manifest')),",
           "        and job.get('owned_TRAIN_overlap_source',{}).get('sha256')=="+repr(owned['sha256'])+
           "\n        and all(type(job.get(k))is dict for k in ('current_main','current_fleet','source_family_manifest')),")
    archival = h.pin(E/'slot-permit-archival-source-original02/slot_retirement_closeout_v2.py')
    change('0b41660911a55522cac315a9451e3b5700ae1d59edd3aaffd3c3fd5faf176f26', archival['sha256'])
    change('        import slot_retirement_closeout_v1 as slot_closeout',
           "        slot_closeout=load('_owned_engineering_full_slot_archival',h.checked(job['quota64_source_pins']['slot_closeout']))")
    change('    server=actor=controller=server_worker=None;policy_before=policy_after=None',
           '    server=actor=controller=server_worker=None;policy_before=policy_after=None;compile_before=None')
    change('        policy_before=policy_before,policy_after=policy_after,acquired_checkpoint=acquisition,',
           '        policy_before=policy_before,policy_after=policy_after,acquired_checkpoint=acquisition,compile_report=compile_before,')
    restored = native
    for old,new in reversed(edits):restored = restored.replace(new,old,1)
    assert restored == parent.read_text()
    compile(native,'<owned-engineering-native>','exec')
    native_path = directory/'run_owned_overlap_fullgame_ENGINEERING_v1.py'
    write(native_path,native.encode());np = h.pin(native_path)
    reviewer_parent = O/'review_owned_overlap_fullgame_UNBOUND_v1.py'
    review = reviewer_parent.read_text()
    tree = ast.parse(review)
    context = next(n for n in tree.body if getattr(n,'name',None)=='validate_bound_context')
    old_context = ast.get_source_segment(review,context)
    new_context = '''def validate_bound_context(config,prepared,job,pair,family,h):
    require(job['engineering_only']is True and job['quality_leg']==config['role']=='E1'
        and pair['engineering_only']is True and job['quality_pair_precommit']['sha256']==PAIR_SHA
        and pair['checkpoint']==job['checkpoint']and pair['clocks']==job['expected_policy_clocks']
        and pair['selected_games']==64 and pair['slots']==list(range(4096,4128))
        and prepared['native']==job['runtime']and prepared['pair']==job['quality_pair_precommit']
        and family['schema']=='robotron-owned-overlap-ENGINEERING-source-family-v1'
        and family['pair']==job['quality_pair_precommit']and family['native']==job['runtime']
        and family['leg_reviewer']==h.pin(__file__)
        and family['current_Main_health']==job['current_v6_health_source']
        and family['current_Main_owned_overlap']==job['owned_TRAIN_overlap_source']
        and family['wire_auditor']==config['wire_auditor']and family['games_auditor']==config['original_games'],
        'Exact engineering policy/native/owned-observer/reviewer family required')
    cpu=json.loads(h.checked(job['stationary_CPU_report']).read_text())
    close=json.loads(h.checked(job['stationary_CPU_closeout']).read_text())
    require(cpu['status']=='PASS_CPU_IDLE_ENGINEERING_ONLY_POLICY'and cpu['joint_action']==80
        and cpu['checkpoint']==job['checkpoint']and cpu['clocks']==job['expected_policy_clocks']
        and close['status']=='PASS_CPU_IDLE_ENGINEERING_ONLY_POLICY_AND_OWNED_CLOSEOUT',
        'Original CPU-verified stationary engineering policy required')
    return pair
'''
    assert review.count(old_context)==1
    review = review.replace(old_context,new_context,1)
    assert "PAIR_SHA='"+'0'*64+"'" in review
    review = review.replace("PAIR_SHA='"+'0'*64+"'",'PAIR_SHA='+repr(selection['sha256']),1)
    assert "and not result.get('engineering_only')" in review
    review = review.replace("and not result.get('engineering_only')","and result.get('engineering_only')is True",1)
    assert review.count("RuntimeMaxUSec='6h 11min'")==1
    review = review.replace("RuntimeMaxUSec='6h 11min'","RuntimeMaxUSec='10min'",1)
    review = review.replace('PASS_SCIENTIFIC_FULLGAME_LEG_RAW64_PREFIX32_PERMIT_STOP32_BOUNDED_MAIN',
                            'PASS_ENGINEERING_RAW64_PREFIX32_FULLPERMIT_STOP32_OWNED_MAIN')
    review = review.replace('FAIL_INDEPENDENT_SCIENTIFIC_FULLGAME_LEG_REVIEW',
                            'FAIL_INDEPENDENT_OWNED_OVERLAP_ENGINEERING_REVIEW')
    review = review.replace("        valid=True,full_game_score_verified=True,role=job['quality_leg'],",
                            "        engineering_only=True,scores_are_not_learning_quality=True,valid=True,full_game_score_verified=True,role=job['quality_leg'],",1)
    compile(review,'<owned-engineering-reviewer>','exec')
    # Check the actual producer/reviewer ABI before launching games. This would
    # have caught the missing compile_report export in the original attempt.
    native_tree=ast.parse(native)
    native_run=next(n for n in native_tree.body if getattr(n,'name',None)=='run')
    result_calls=[n for n in ast.walk(native_run) if isinstance(n,ast.Call)
        and isinstance(n.func,ast.Attribute) and n.func.attr=='put' and len(n.args)>1
        and isinstance(n.args[0],ast.BinOp) and isinstance(n.args[0].right,ast.Constant)
        and n.args[0].right.value=='result.json']
    assert len(result_calls)==1 and isinstance(result_calls[0].args[1],ast.Call)
    producer_fields={k.arg for k in result_calls[0].args[1].keywords}
    review_function=next(n for n in ast.parse(review).body if getattr(n,'name',None)=='review')
    expected_fields={n.slice.value for n in ast.walk(review_function) if isinstance(n,ast.Subscript)
        and isinstance(n.value,ast.Name) and n.value.id=='result'
        and isinstance(n.slice,ast.Constant) and isinstance(n.slice.value,str)}
    assert not expected_fields-producer_fields, expected_fields-producer_fields
    reviewer_path = directory/'review_owned_overlap_fullgame_ENGINEERING_v1.py'
    write(reviewer_path,review.encode());reviewer_pin=h.pin(reviewer_path)
    template = json.loads((F/'01-reference/review-job-template.json').read_text())
    family = h.put(directory/'selected-source-family.json',dict(
        schema='robotron-owned-overlap-ENGINEERING-source-family-v1',engineering_only=True,pair=selection,
        native=np,leg_reviewer=reviewer_pin,current_Main_health=health,current_Main_owned_overlap=owned,
        wire_auditor=template['wire_auditor'],games_auditor=template['original_games'],
        slot_closeout=archival))
    job = copy.deepcopy(old_job)
    job['quota64_source_pins']['slot_closeout']=archival
    job.update(runtime=np,output=str(directory/'runtime-original01'),quality_pair_precommit=selection,
        label='OWNED-OVERLAP-FULLPERMIT-ENGINEERING-'+directory.name,created_unix_s=time.time(),
        current_v6_health_source=health,current_v6_health_qualification=h.pin(reviewed),
        owned_TRAIN_overlap_source=owned,source_family_manifest=family,
        lease=h.pin('/dev/shm/robotron-snapshot-smoke-gpu0.lock'),
        sessions={str(k):secrets.token_hex(16)for k in range(4096,4128)},
        connections={str(k):secrets.token_hex(16)for k in range(4096,4128)},
        selected_change='New stationary engineering case: owned overlap observer+reviewer, full slot permit archivalv2; no scientific retry.')
    replaced={old_job['runtime']['path'],old_job['current_v6_health_source']['path'],
        old_job['current_v6_health_qualification']['path'],old_job['source_family_manifest']['path'],
        old_job['quality_pair_precommit']['path'],old_job['quota64_source_pins']['slot_closeout']['path']}
    pins=[p for p in old_job['inputs']if p['path']not in replaced]
    pins.extend([np,health,owned,h.pin(reviewed),family,selection,archival])
    job['inputs']=list({p['path']:p for p in pins}.values())
    jp=h.put(directory/'job.json',job)
    ctl_path=original/'control_fullgame_ENGINEERING600_v1.py';ctl=load('_owned_engineering_controller',ctl_path)
    config=dict(unit='robotron-owned-overlap-engineering-'+hashlib.sha256(str(directory).encode()).hexdigest()[:12]+'.service',
        output=str(directory/'execution-original01'),
        argv=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',np['path'],'--execute','--job',jp['path'],
              '--job-sha256',jp['sha256'],'--source-sha256',np['sha256']],
        properties=['CPUQuota=1200%','MemoryMax=24G','MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=512','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[ctl.pin(p['path'])for p in [np,jp,*job['inputs']]],observation_s=660)
    cp=h.put(directory/'controller-config.json',config)
    prepared=h.put(directory/'prepared-native.json',dict(native=np,job=jp,controller=h.pin(ctl_path),
        controller_config=cp,pair=selection,engineering_only=True,quality_qualified=False))
    template.update(runtime=reviewer_pin,role='E1',native_prepared=prepared,
        original_native_closeout_path=str(directory/'positive-original-native-closeout.json'),
        report=str(directory/'independent-review-original01/report.json'))
    review_template=h.put(directory/'review-job-template.json',template)
    # CPU prebody validation runs before any GPU load or first game score.
    runtime=load('_owned_engineering_prebody',native_path)
    assert runtime.validate_job(job)==Path(job['output'])
    for entry in job['inputs']:h.checked(entry)
    package_root,package=h.package_inputs(job['source_package'])
    for slot in range(4096,4128):
        argv=runtime.actor_command(job,Path(job['output'])/'actors'/str(slot))
        assert ('-speed'in argv)is(slot==4127)
    assert len(set(list(job['sessions'].values())+list(job['connections'].values())))==64
    preflight=h.put(directory/'CPU-prebody-original01.json',dict(status='PASS_ENGINEERING_CPU_PREFLIGHT_ONLY',
        job=jp,runtime=np,all_input_pins_checked=len(job['inputs']),source_package_files=len(package),
        all32_original_commands_checked=True,unique_fresh_session_connection_ids=64,
        producer_reviewer_static_result_fields_checked=sorted(expected_fields),
        compile_report_export_contract_checked=True,
        native_only_declared_edits_reverse_to_parent=True,actual_GPU_MAME_or_first_score=False))
    packet=h.put(directory/'prepared-ENGINEERING-only.json',dict(status='PREPARED_NEW_OWNED_OVERLAP_ENGINEERING_NOT_LAUNCHED',
        native_prepared=prepared,review_job_template=review_template,preflight=preflight,selection=selection,
        native_parent=old_job['runtime'],reviewer_parent=h.pin(reviewer_parent),stationary_policy=old_job['checkpoint'],
        engineering_only=True,no_learning_quality_claim=True,promotion=False))
    print(json.dumps(dict(packet=packet,native=prepared,review=review_template)))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
