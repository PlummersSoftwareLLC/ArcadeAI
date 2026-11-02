"""Unselected typed-recipe CE4096 first durable8+8 frozen-policy bindings.

Source/saved metadata only until an explicit future root call. No import-time I/O.
No causal learning-speed inference, old failed-operation repair alias or retry.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import shlex
GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
Q=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
SCHEMA='robotron-live-ce-lr-continuation-quality-bindings-v1'
PHASE=GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'
PHASE_SHA='14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'
STRICT_SHA='9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'
BASE_SHA='7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
SELECTOR=GAME/'tools/live_lr_recipe_continuation_proposal/capture_candidate.py'
SELECTOR_SHA='96f7035b30e827c1d16cedb9073a6c89d7ccee6dea1e95b9b1433d34529dfbae'
OBSERVER=GAME/'tools/live_lr_recipe_continuation_proposal/observer.py'
OBSERVER_SHA='11380275b544eb7196d33d92b1fbe28a1ae057404120419a2cfa447410c7e430'
ACTIVATION_RESULT=RUN/'rejected-gap-healthy-activation-original01-20261018/result.json'
ACTIVATION_SHA='f47b861115c62a87097f6eef0750f9c07db8a6876d59c87ab0a5ff0801a19621'
ACTIVATION_ADOPTION=RUN/'rejected-gap-healthy-activation-root-preparation-20261018/root-actual-activation-canonical-adoption.json'
ADOPTION_SHA='490c7cb2de233ded3a9cd6c06d7c3c1d0006c3b714a526a584fe085e13a3ed0b'
QUALITY_RELEASE_SHA='567c32a2d89efca4b0dbd972eea0425880d5005ddd0cdf863952367fc24c0e9a'
PREDECESSOR_PLAN_SHA='4093225c8fdec659880cc06a5c54549139708909f7a011696ac03f298d3338e8'
INVALID49_RELEASE_SHA='a7d7f523674d8135535779da782eb4ab3aa342b012695960f1ccef03b0fd6e7f'
REFERENCE=GAME/'models_dqn/managed-incumbents/freshCE-accepted-newgame-704M-confirmed-20261018.pt'
REFERENCE_SHA='eba19578c91b2380859754b99b9a8510efaed11f3ec2f672e89c5988e50ad74c'
REFERENCE_META_SHA='34190c0dcbfe2383bcf0c5dec31adb318ca02822c8c0d8d2289607447e075eae'
CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count')
OWNER_KEYS={'pid','starttime_ticks','unit','invocation_id','cgroup'}
LIMIT=4<<20
EVIDENCE_KEYS={'capture_case','capture_result','capture_release','window_job','window_result','decision','durability',
    'trigger_API','phase_cpu_job','phase_cpu_report','phase_cpu_completion','CPU_execution',\
    'historical_invalid49_release','historical_invalid49_plan','control_transition','barrier'}

EVALUATOR = {'tools/run_frozen_sidecar.py': 'db1fd0eac2c68b73425c77767ef0f842374291c855338f6b2ac05ee6b79dc04f', 'tools/sidecar_boot.py': 'f06492e6d96cd472d9f0073b4c643e820bcacb6a96c5f542a59d6b6874e62362', 'Scripts/main.lua': '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf', 'Scripts/robotron_socket_wait.c': 'fc9ed2719839f72e36346d0886e5b32116a167d49414b506dc8b5f4252464cfc', 'Scripts/dqn/config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'Scripts/dqn/model.py': 'bcd174f05610c6f773ca8c53f9155206eba4f7b6a11383516ddd71f3b513eeb4', 'Scripts/dqn/actor_tags.py': 'fc5b868a7fb68d4ab7ba65ba872ea0e845759af6143edfe648239d57cb7f1591', 'Scripts/dqn/socket_server.py': 'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed', 'Scripts/dqn/game_journal.py': '10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0', 'Scripts/dqn/managed_measurement.py': '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6', 'Scripts/dqn/inference_actor.py': '7cc812adeab8dc7cb989f9024592767928afa786966b85f3488023fb8d6b34ce', 'Scripts/dqn/nstep_buffer.py': 'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1', 'Scripts/dqn/rejected_gap_telemetry.py': 'd58610a139644b79f39504e48e1bc43bda9837cc51d743bec623103918c50cbd'}
EXECUTION = {'/home/dave/source/repos/ArcadeAI/Robotron/tools/run_quality_campaign.py': '574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128', '/home/dave/source/repos/ArcadeAI/Robotron/tools/run_frozen_sidecar.py': 'db1fd0eac2c68b73425c77767ef0f842374291c855338f6b2ac05ee6b79dc04f', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_sidecar_measurements.py': '879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_frozen_measurements.py': '53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0'}
CANDIDATE_SOURCES = {'agent.py': '865a0df717b39951b7f7c516e4a962e3d48cf4d3dc11295ff266e58653e6c74b', 'training.py': '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4', 'loss_kernel.py': '23eb8fc0d8409c9f31ef26ec4596da9c2257e3985abbbfa7d5fbdcb337e21f67', 'config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'priority_phase.py': 'ee3c0d02bc1eab55e92ffd605c3736fe5a0ef905a8a8ee242c687301ea2b7c5b'}


# Frozen historical maps are independent literals, never derived from current E13.
PRE_DIAGNOSTIC_EVALUATOR = {'tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', 'tools/sidecar_boot.py': 'f06492e6d96cd472d9f0073b4c643e820bcacb6a96c5f542a59d6b6874e62362', 'Scripts/main.lua': '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf', 'Scripts/robotron_socket_wait.c': 'fc9ed2719839f72e36346d0886e5b32116a167d49414b506dc8b5f4252464cfc', 'Scripts/dqn/config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'Scripts/dqn/model.py': 'bcd174f05610c6f773ca8c53f9155206eba4f7b6a11383516ddd71f3b513eeb4', 'Scripts/dqn/actor_tags.py': 'fc5b868a7fb68d4ab7ba65ba872ea0e845759af6143edfe648239d57cb7f1591', 'Scripts/dqn/socket_server.py': '4a1f6a3cc7c82d8c85e1af93ceac0ca7457663d5f5ba7c7d893e3c2b3003e26c', 'Scripts/dqn/game_journal.py': '10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0', 'Scripts/dqn/managed_measurement.py': '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6', 'Scripts/dqn/inference_actor.py': '7cc812adeab8dc7cb989f9024592767928afa786966b85f3488023fb8d6b34ce', 'Scripts/dqn/nstep_buffer.py': 'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'}
PRE_DIAGNOSTIC_EXECUTION = {'/home/dave/source/repos/ArcadeAI/Robotron/tools/run_quality_campaign.py': '574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128', '/home/dave/source/repos/ArcadeAI/Robotron/tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_sidecar_measurements.py': '879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_frozen_measurements.py': '53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0'}
INVALID49_EVALUATOR = {'tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', 'tools/sidecar_boot.py': 'f06492e6d96cd472d9f0073b4c643e820bcacb6a96c5f542a59d6b6874e62362', 'Scripts/main.lua': '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf', 'Scripts/robotron_socket_wait.c': 'fc9ed2719839f72e36346d0886e5b32116a167d49414b506dc8b5f4252464cfc', 'Scripts/dqn/config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'Scripts/dqn/model.py': 'bcd174f05610c6f773ca8c53f9155206eba4f7b6a11383516ddd71f3b513eeb4', 'Scripts/dqn/actor_tags.py': 'fc5b868a7fb68d4ab7ba65ba872ea0e845759af6143edfe648239d57cb7f1591', 'Scripts/dqn/socket_server.py': 'd99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214', 'Scripts/dqn/game_journal.py': '10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0', 'Scripts/dqn/managed_measurement.py': '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6', 'Scripts/dqn/inference_actor.py': '7cc812adeab8dc7cb989f9024592767928afa786966b85f3488023fb8d6b34ce', 'Scripts/dqn/nstep_buffer.py': 'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'}
INVALID49_EXECUTION = {'/home/dave/source/repos/ArcadeAI/Robotron/tools/run_quality_campaign.py': '574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128', '/home/dave/source/repos/ArcadeAI/Robotron/tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_sidecar_measurements.py': '879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_frozen_measurements.py': '53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0'}

def require(value, message):
    if not value:
        raise ValueError(message)

def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)

def read_bytes(pin, *, allow_empty=False):
    require(set(pin) == {'path', 'sha256', 'bytes', 'identity'}, 'Full metadata PIN required')
    path = Path(pin['path'])
    require(path.is_absolute() and path == path.resolve(strict=True) and
        path.suffix not in ('.pt','.pth','.npy','.npz'), 'Canonical metadata path required; no tensor bodies')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and (0 if allow_empty else 1) <= before.st_size <= LIMIT
            and before.st_uid == os.getuid() and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) == 0o444, 'Owned readonly bounded metadata required')
        data = stream.read(LIMIT + 1)
        require(identity(os.fstat(stream.fileno())) == identity(before) == identity(path.lstat())
            == pin['identity'], 'Metadata changed during read')
    require(len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256'], 'Metadata PIN differs')
    return data

def four(value):
    result = {key: value[key] for key in CLOCKS}
    require(all(type(v) is int and v > 0 for v in result.values()), 'Four positive actual clocks required')
    return result

def flat(pin):
    return dict(path=pin['path'], sha256=pin['sha256'], **pin['identity'])

def triple(value):
    return {key:value[key] for key in ('path','sha256','bytes')}

def owner(value):
    require(set(value)==OWNER_KEYS and type(value['pid']) is int and value['pid']>0 and
        type(value['starttime_ticks']) is int and value['starttime_ticks']>0 and
        re.fullmatch('[0-9a-f]{32}',value['invocation_id'] or '') and
        value['cgroup'].endswith('/'+value['unit']), 'Exact actual five-key owner required')
    return value

def check_reference(reference,reader):
    require(set(reference)=={'path','sha256','bytes','metadata'} and reference['path']==str(REFERENCE) and
        reference['sha256']==REFERENCE_SHA and reference['bytes']==275202741 and
        reference['metadata']['path']==str(REFERENCE)+'.json' and reference['metadata']['sha256']==REFERENCE_META_SHA,
        'Actual protected704 reference/metadata required')
    meta=reader(reference['metadata'])
    require(meta['schema']=='robotron-protected-quality-winner-v1' and meta['protected_checkpoint']==str(REFERENCE) and
        meta['checkpoint_sha256']==REFERENCE_SHA and meta['assessment']['qualified_improvement'] is True,
        'Protected704 publication metadata differs')

def terminal(execution, read_text, read_journal, *, exit_status=0, result="success"):
    owner = execution['owner']; require(set(owner) == OWNER_KEYS, 'Exact original controller/deadline identity required')
    fields = dict(line.split('=', 1) for line in read_text(execution['show']).splitlines() if '=' in line)
    require(fields['LoadState'] == 'loaded' and fields['MainPID'] == '0'
        and fields['ExecMainPID'] == str(owner['pid']) and fields['InvocationID'] == owner['invocation_id']
        and fields['NRestarts'] == '0' and fields['ExecMainCode'] == '1'
        and fields['ExecMainStatus'] == str(exit_status) and fields['Result'] == result,
        'Exact original retained execution exit/result required; failures cannot be relabelled')
    require(read_text(execution['cat']) and execution['archived_before_release'] is True and execution['released'] is True,
        'Original unit/cat/invocation archived before actual release required')
    read_journal(execution['journal'])

def read(pin):
    return json.loads(read_bytes(pin),parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))

def read_raw(pin):
    # Only explicitly named raw API/event/outcome witnesses use this reader.
    return json.loads(read_bytes(pin))

def same_raw(left,right):
    return json.dumps(left,sort_keys=True,allow_nan=True)==json.dumps(right,sort_keys=True,allow_nan=True)

def finite(value):
    require(type(value) in (int,float) and math.isfinite(value),'Finite numeric evidence required')
    return value

def load_observer():
    require(hashlib.sha256(OBSERVER.read_bytes()).hexdigest()==OBSERVER_SHA,'Selected pure observer source differs')
    spec=importlib.util.spec_from_file_location('_quality_postfix_live8M_pure_observer',OBSERVER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.configure_recipe(load_selector().load('recipe'))
    return module

def load_selector():
    require(hashlib.sha256(SELECTOR.read_bytes()).hexdigest()==SELECTOR_SHA,'Selected typed activation capture source differs')
    spec=importlib.util.spec_from_file_location('_quality_postdiagnostic_capture',SELECTOR)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def check_historical_sources(predecessor,invalid49,old_plan,old_plan_pin):
    require(predecessor['evaluator_source_hashes']==PRE_DIAGNOSTIC_EVALUATOR and
        predecessor['execution_source_hashes']==PRE_DIAGNOSTIC_EXECUTION,
        'Immediate409322 E12/X4 history must remain literal and independent of current E13')
    require(invalid49['source_freeze_released'] is True and invalid49['owned_cleanup_complete'] is True and
        invalid49['native_outcome']=='invalid' and invalid49['completed_legs']==[1,2] and
        invalid49['R2_C2_not_run'] is True and invalid49['C1_count']==49 and invalid49['minimum_count']==50 and
        invalid49['quality_acceptance'] is False and invalid49['all_four_completed'] is False and
        triple(old_plan_pin)==triple(invalid49['native_plan']) and
        all(old_plan_pin['identity'][k]==v for k,v in invalid49['native_plan']['identity'].items()) and
        old_plan['evaluator_source_hashes']==INVALID49_EVALUATOR and
        old_plan['execution_source_hashes']==INVALID49_EXECUTION,
        'Historical invalid49 stays invalid under its own literal E12/X4 maps')

def check_diagnostic_sources(sources,environment):
    expected={'socket_server.py':'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed',
        'rejected_gap_telemetry.py':'d58610a139644b79f39504e48e1bc43bda9837cc51d743bec623103918c50cbd',
        'metrics_dashboard.py':'3d1aa1950e6b1c5224ace3aecb9c837e433e5c36941b89465b414749f903da27',
        'experiment_status.py':'aa1d018902be0875ff237e9cb3fa1bb29f066f4480123cf783a99091551d722c'}
    require(len(sources)==62 and all(sources.get(str(GAME/'Scripts/dqn'/name))==sha for name,sha in expected.items()) and
        environment.get('ROBOTRON_REJECTED_GAP_TELEMETRY')=='1','Exact diagnostic62 sources and enabled flag required')

def check_CPU_command(execution,completion,text_reader):
    cat=text_reader(execution['cat']);show=text_reader(execution['show'])
    commands=[shlex.split(line.split('=',1)[1]) for line in cat.splitlines()
        if line.startswith('ExecStart=') and line.split('=',1)[1].strip()]
    require(len(commands)==1,'One actual archived ExecStart required')
    argv=commands[0];command=completion['argv']
    require(argv[-len(command):]==command and argv[:5]==['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH'],
        'Archived retained CPU ExecStart is not the original exact numerical command')
    assignments=argv[5:-len(command)]
    require(all('=' in x for x in assignments),'Exact explicit numerical environment assignments required')
    environment=dict(x.split('=',1) for x in assignments)
    require(len(environment)==len(assignments) and set(environment)=={'CUDA_VISIBLE_DEVICES','PYTHONDONTWRITEBYTECODE',
        'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','TMPDIR'} and
        environment['CUDA_VISIBLE_DEVICES']=='' and environment['PYTHONDONTWRITEBYTECODE']=='1' and
        all(environment[k]=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')) and
        Path(environment['TMPDIR']).is_absolute(),'Actual CPU CUDAhidden/unset preload+pythonpath/thread context differs')
    field=next((line.split('=',1)[1] for line in show.splitlines() if line.startswith('ExecStart=')),None)
    match=re.search(r'argv\[\]=(.*?) ; ignore_errors=',field or '')
    require(match is not None and shlex.split(match.group(1))==argv,
        'Original full show and unit cat ExecStart differ')

def candidate_descriptor(value):
    require(set(value) == {'tag','path','sha256','bytes'}
        and re.fullmatch('[A-Za-z0-9_-]{1,100}', value['tag'] or '')
        and value['path'] == str(GAME/'models_dqn/managed-checkpoints'/(value['tag']+'.pt'))
        and re.fullmatch('[0-9a-f]{64}', value['sha256'] or '')
        and type(value['bytes']) is int and 0 < value['bytes'] <= 512 << 20,
        'Actual unique live-CE candidate tag/hash/dynamic bytes required')

def check_cpu(job, proof, completion, candidate):
    selected=load_selector().load('recipe').from_held(job['source_control_context']['held_recipe_context'])
    candidate_descriptor(candidate)
    require(job['schema'] == 'robotron-phase-snapshot-checkpoint-CPU-job-v1'
        and job['verifier_sha256'] == PHASE_SHA and job['strict_phase_base_sha256'] == STRICT_SHA
        and job['original_strict_base_sha256'] == BASE_SHA, 'Actual candidate phase CPU job required')
    spec = job['phase_snapshot']
    require(spec['purpose'] == 'candidate' and spec['observed_clients'] == 192
        and spec['expected_phase']['metric'] == 'ce' and spec['expected_phase']['valid'] is True,
        'Only genuine live192 CE candidate phase CPU accepted')
    owner(spec['owner'])
    source, copied = job['source'], job['verification_copy']
    require(source['path'] == candidate['path']
        and candidate['sha256'] == source['sha256'] == copied['sha256']
        and candidate['bytes'] == source['bytes'] == copied['bytes'], 'Candidate source/hash/bytes differ')
    require(source['path'] != copied['path']
        and (source['identity']['device'], source['identity']['inode']) !=
            (copied['identity']['device'], copied['identity']['inode'])
        and all(p['identity']['bytes'] == candidate['bytes'] and p['identity']['mode'] == '0o444'
            and p['identity']['nlink'] == 1 and p['identity']['uid'] == os.getuid() for p in (source, copied)),
        'Independent readonly candidate copy required')
    require(proof['schema'] == 'robotron-phase-snapshot-checkpoint-CPU-result-v1'
        and proof['status'] == 'PASS' and proof['phase_metadata_verified'] is True
        and proof['script']['sha256'] == PHASE_SHA and proof['strict_phase_base']['sha256'] == STRICT_SHA
        and proof['original_strict_base']['sha256'] == BASE_SHA and proof['root_job'] == job
        and proof['sha256'] == candidate['sha256'] and proof['bytes'] == candidate['bytes']
        and proof['path'] == copied['path'] and proof['source_before'] == flat(source)
        and proof['verification_copy'] == flat(copied)
        and proof['actual_restore_or_optimizer_step'] is False and proof['actual_quality_qualification'] is False,
        'Matching strict phase CPU result required')
    argv = completion['argv']
    require(set(completion) == {'argv','exit_code'} and completion['exit_code'] == 0
        and isinstance(argv,list) and len(argv) == 12 and Path(argv[0]).is_absolute(),
        'Genuine numerical command and original exit0 required; no fabricated CPU owner')
    require(argv == [argv[0],'-Xgil=0','-I','-B',str(PHASE),'--execute','--job',proof['job_file']['path'],
        '--expected-job-sha256',proof['job_file']['sha256'],'--expected-verifier-sha256',PHASE_SHA],
        'Phase CPU argv flags/order/job/source differ')
    require(all(four(proof['clocks'])[k] >= four(job['clock_floor'])[k] for k in CLOCKS), 'Candidate predates capture floor')
    saved = proof['saved_priority_metric_phase']; expected = spec['expected_phase']
    require(saved['metric'] == 'ce' and saved['valid'] is True
        and all(saved[k] == expected[k] for k in ('phase_id','root_precommit_sha256','started_from'))
        and saved['phase_record_sha256'] == expected['founder_phase_record_sha256']
        and saved['last_resume_record_sha256'] == expected['last_resume_record_sha256'], 'Saved CE founder/resume differs')
    require(proof['held_recipe_context']==job['source_control_context']['held_recipe_context'] and
        proof['held_recipe_context']['batch_size']==4096 and proof['held_recipe_context']['learning_control_lr_scale']==selected['learning_control_lr_scale'] and
        proof['held_recipe_context']['optimizer_lr']==proof['adam_group']['lr']==selected['scheduled_lr'] and
        proof['cuda_initialized'] is False and proof['visible_cuda_devices']==0 and proof['finite']['tensors']==443 and
        proof['adam_state_count']==81 and proof['adam_group_count']==1 and len(proof['adam_steps'])==81 and
        finite(proof['adam_step_min'])==finite(proof['adam_step_max'])>0 and proof['grad_scaler']['scale']>0 and
        set(proof['models'])=={'online_state_dict','target_state_dict'} and
        all(x['strict_cpu_load'] is True for x in proof['models'].values()),'Actual selected recipe/4096 finite81Adam/scaler CPU evidence differs')



    specialization=proof['recipe_specialization']
    require(specialization['selected_recipe']==selected and
        specialization['full_held_recipe_context']==job['source_control_context']['held_recipe_context'] and
        specialization['raw_strict_source_sha256']==STRICT_SHA and
        specialization['common_recipe_source']['sha256']=='f11e4c8d6725c04c4495b416318713f675ba9305ffe6f7c4009a3bff9b860d0e' and
        specialization['replacement_count']==(3 if selected['learning_control_lr_scale']==.25 else 0) and
        specialization['effective_source_sha256']==('5612ad9c5730030f818232146fc5073000b89ae8e93577fab8bd18a03d16c8e8' if selected['learning_control_lr_scale']==.25 else STRICT_SHA) and
        specialization['reverse_exact_raw_source'] is True and specialization['numeric_function_bodies_changed'] is False and
        specialization['saved_metadata_normalized'] is False,'Actual limited recipe-source specialization required')


def archived_bytes(pin,allow_empty=False):
    # Root control stream PINs genuinely use minimal identities; JSON remains FULLPIN-only.
    path=Path(pin['path']);require(path.is_absolute() and path==path.resolve(strict=True),'Canonical archived text required')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        before=os.fstat(stream.fileno());actual=identity(before)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1 and
            stat.S_IMODE(before.st_mode)==0o444 and (0 if allow_empty else 1)<=before.st_size<=LIMIT,
            'Owned readonly bounded archived bytes required')
        raw=stream.read(LIMIT+1)
        require(identity(os.fstat(stream.fileno()))==actual==identity(path.lstat()) and
            all(actual[k]==v for k,v in pin['identity'].items()) and len(raw)==pin['bytes'] and
            hashlib.sha256(raw).hexdigest()==pin['sha256'],'Archived declared bytes/identity changed')
    return raw


def archive_text(pin):return archived_bytes(pin).decode('utf-8','surrogateescape')


def check_root_capture(released,result_pin,case_pin,case,text_reader):
    payload_matches = 'payload_result' not in released
    if not payload_matches:
        payload = released['payload_result']
        expected_payload = {k: result_pin[k] for k in ('path', 'sha256', 'bytes')}
        expected_payload['identity'] = {k: result_pin['identity'][k]
            for k in ('device', 'inode', 'mode', 'uid', 'nlink')}
        payload_matches = (type(payload) is dict and payload == expected_payload
            and all(type(payload[k]) is type(expected_payload[k]) for k in expected_payload)
            and all(type(payload['identity'][k]) is type(expected_payload['identity'][k])
                    for k in expected_payload['identity'])
            and Path(payload['path']).is_absolute())
    if released['schema']=='robotron-root-audit-original-result-and-GC-aware-owned-release-v1':
        require(released['status']=='ORIGINAL_AUDIT_EXIT0_ARCHIVED_AND_RELEASED' and
            type(released['original_exec_code']) is int and released['original_exec_code']==1 and
            type(released['original_exit']) is int and released['original_exit']==0 and released['original_result']=='success' and
            released['lifecycle_complete'] is True and released['all_six_original_archive_commands_succeeded'] is True and
            released['error'] is None and released['payload_retried'] is False and released['audit_success'] is True and
            released['unit_released'] is True and released['original_archived_before_release'] is True and
            payload_matches and result_pin['path']==str(Path(case['output_directory'])/'result.json'),
            'Only complete genuine GC-aware capture0 with all six successful archives is eligible')
    else:
        require(released['schema']=='robotron-root-retained-original-result-and-release-v1' and
            released['original_exec_code']==1 and released['original_exit']==0 and released['original_result']=='success' and
            released['original_archived_before_release'] is True and released['unit_released'] is True and
            payload_matches and result_pin['path']==str(Path(case['output_directory'])/'result.json'),'Original successful capture/archive/release required')
    original=released['original'];unit=original['unit'];timer=original['timer'];a=released['full_original_archives']
    commands=[['systemctl','--user','show',unit],['systemctl','--user','cat',unit],
        ['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+original['invocation_id']],
        ['systemctl','--user','show',timer],['systemctl','--user','cat',timer],
        ['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+original['timer_invocation_id']]]
    require(original['observed_live'] is True and timer==unit.removesuffix('.service')+'.timer' and
        len(a)==6 and all(x['argv']==cmd and x['exit']==0 for x,cmd in zip(a,commands)),
        'Actual six original service/timer archives required')
    fields=dict(line.split('=',1) for line in text_reader(a[0]['stdout']).splitlines() if '=' in line)
    require(fields['ExecMainPID']==str(original['pid']) and fields['InvocationID']==original['invocation_id'] and
        fields['MainPID']=='0' and fields['NRestarts']=='0' and fields['ExecMainCode']=='1' and fields['ExecMainStatus']=='0' and
        fields['Result']=='success','Original retained capture identity/exit differs')
    cat=text_reader(a[1]['stdout']);commands=[shlex.split(x.split('=',1)[1]) for x in cat.splitlines() if x.startswith('ExecStart=') and x.split('=',1)[1].strip()]
    require(len(commands)==1 and str(SELECTOR) in commands[0],'Original capture must invoke exact selected source')
    tail=commands[0][commands[0].index(str(SELECTOR))+1:]
    require(tail.count('--execute')==1,'One explicit original capture execute required')
    tail=[x for x in tail if x!='--execute'];require(len(tail)==8,'Exact source/case/output flag set required')
    flags=dict(zip(tail[::2],tail[1::2]));require(flags=={'--case':case_pin['path'],'--expected-case-sha256':case_pin['sha256'],
        '--output':case['output_directory'],'--expected-source-sha256':SELECTOR_SHA},'Original capture source/case/output differs')
    release=released['owned_release'];require(len(release)==2 and [x['unit'] for x in release]==[timer,unit] and
        max(x['unix_s'] for x in a)<=release[0]['stop']['unix_s']<=release[1]['stop']['unix_s'],'Exact archive-before timer-first release required')
    for x in release:
        require(x['stop']['argv']==['systemctl','--user','stop',x['unit']] and x['stop']['exit']==0 and
            x['final']['argv']==['systemctl','--user','show',x['unit']] and x['final']['exit']==0 and
            dict(line.split('=',1) for line in text_reader(x['final']['stdout']).splitlines() if '=' in line)['LoadState']=='not-found',
            'Exact owned capture pair not-found proof differs')


def check_window(case,result,window,outcome,B,event,receipt,observer):
    observer.validate_job(window,B)
    require(window['policy']==case['window']['policy'] and window['experiment']==result['_experiment'] and
        window['owner']==result['owner'] and window['current_phase']==result['current_phase'] and
        window['proofs']==dict(root_precommit=result['root_case'],activation_result=case['activation']['result'],
            activation_adoption=case['activation']['adoption'],control=result['control_after'],control_transition=result['control_transition'],barrier=result['barrier']),
        'Original root precommit/activation/control/B origin differs')
    require(outcome['status']=='LATCH_DURABLE' and outcome['candidate_requests_allowed']==1 and outcome['qualification_pass'] is False and
        same_raw(outcome['observation'],event) and event['schema']==observer.OBSERVATION_SCHEMA and event['state']=='LATCH' and
        event['candidate_requests_allowed']==0 and event['qualification_pass'] is False,'Only original timely durable first-LATCH grants one request')
    pair=outcome['durability'];require(pair['completion']==receipt and same_raw(observer.durable_result(event,pair,window),outcome),
        'Actual paired original event file+dir fsync cutoff evidence differs')
    start=window['baseline']['observed_clock'];elapsed=finite(event['observed_monotonic_s'])-start['monotonic_s']
    require(event['boot_id']==start['boot_id'] and event['elapsed_s']==elapsed and 0<=elapsed<=window['policy']['cutoff_s'],
        'Original first-LATCH actual origin/cutoff differs')
    base=observer.normalise(B);current=observer.normalise(event['first_eligible_observation']);p=event['progress']
    require(current['optimizer_identity']==base['optimizer_identity'] and current['replay_identity']==base['replay_identity'] and
        all(current[g][k]>=base[g][k] for g in ('clocks','optimizer','optimizer_since_epoch','categories') for k in base[g]) and
        current['optimizer']['unavailable']==base['optimizer']['unavailable']==0,'Same-B identity/epoch/counters differ')
    api=event['first_eligible_observation'];require(api['client_count']==192 and api['training_enabled'] is True and
        api['measurement_active'] is False and api['managed_experiment']==result['_experiment'] and finite(api['lr'])==window['recipe']['scheduled_lr'],
        'Original LATCH must be actual selected live192 recipe')
    delta={k:current['optimizer'][k]-base['optimizer'][k] for k in observer.COUNTERS}
    expected=dict(learner_frames=current['clocks']['learner_frame_count']-base['clocks']['learner_frame_count'],
        fleet_frames=current['clocks']['frame_count']-base['clocks']['frame_count'],physical_accepted=current['accepted']-base['accepted'],
        learner_accepted=current['learner_accepted']-base['learner_accepted'],physical_by_source={k:current['categories'][k]-base['categories'][k] for k in observer.CATEGORIES},
        logical_steps=current['clocks']['training_steps']-base['clocks']['training_steps'],logical_samples=current['clocks']['optimized_samples']-base['clocks']['optimized_samples'],
        optimizer_total=current['optimizer'],optimizer_delta_from_B=delta,optimizer_pending=current['unclassified'],
        AMP_classified_denominator=delta['applied']+delta['amp_skipped'],admitted_samples_from_B=delta['applied']*4096,
        admitted_samples_process_total=current['optimizer']['applied']*4096)
    require(all(p[k]==v for k,v in expected.items()) and p['learner_frames']>=8000000 and p['learner_accepted']>=8000000,
        'NEW original8M learner AND8M DQN+epsilon accepted required; physicalall5 cannot substitute')
    denominator=expected['AMP_classified_denominator'];require(p['AMP_skip_fraction']==(None if denominator==0 else delta['amp_skipped']/denominator),
        'Original same-B AMP denominator differs')
    return base,current


def verified_known_CPU_metadata_review(execution,job_pin,report_pin,completion_pin,completion,reader):
    if 'metadata_review' not in execution:return False
    path=Path(__file__).with_name('cpu_metadata_review.py').resolve(strict=True);info=path.lstat()
    expected='755b2818db1c3a7dbfb33d005b17afb3791e5080ad23198ac422cc3e0360bb34'
    helper_pin=dict(path=str(path),sha256=expected,bytes=info.st_size,identity=identity(info))
    raw=archived_bytes(helper_pin)
    spec=importlib.util.spec_from_file_location('_exact_known_original_CPU_metadata_review',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    require(archived_bytes(helper_pin)==raw,'Exact known-review helper changed during load')
    return module.verify_known_review(execution,job_pin,report_pin,completion_pin,completion,reader,check_cpu,archived_bytes,helper_pin)


def check_CPU_release(execution,job_pin,report_pin,completion_pin,completion,reader,text_reader,journal_reader):
    terminal(execution,text_reader,journal_reader);check_CPU_command(execution,completion,text_reader)
    release=reader(execution['release_receipt']);archive=reader(release['original_terminal_archive']);cpu_owner=execution['owner']
    original=release['original'];groups=archive['full_original_archives']
    require(archive['original']==original and original['observed_live'] is True and
        (original['pid'],original['starttime_ticks'],original['invocation_id'],original['unit'])==
        (cpu_owner['pid'],cpu_owner['starttime_ticks'],cpu_owner['invocation_id'],cpu_owner['unit']) and
        original['timer']==execution['timer']==cpu_owner['unit'].removesuffix('.service')+'.timer' and
        set(groups)=={'service_show','service_cat','service_journal','timer_show','timer_cat','timer_journal'},
        'Actual original CPU identity and ALL SIX service/timer archive groups required')
    expected={}
    for kind,unit,invocation in (('service',original['unit'],original['invocation_id']),
                                ('timer',original['timer'],original['timer_invocation_id'])):
        expected[kind+'_show']=['systemctl','--user','show',unit,'--all']
        expected[kind+'_cat']=['systemctl','--user','cat',unit]
        expected[kind+'_journal']=['journalctl','--user','_SYSTEMD_INVOCATION_ID='+invocation,'--no-pager','-o','short-iso-precise']
    ended=[]
    for name,argv in expected.items():
        group=groups[name];command=reader(group['command'])
        require(command['argv']==argv and command['returncode']==0 and
            command['stdout'].encode('utf-8','surrogateescape')==journal_reader(group['stdout']) and
            command['stderr'].encode('utf-8','surrogateescape')==journal_reader(group['stderr']) and
            finite(command['started_unix_s'])<=finite(command['ended_unix_s']),
            'Original CPU six-group command/stream provenance differs: '+name)
        ended.append(command['ended_unix_s'])
    timer_show=dict(line.split('=',1) for line in text_reader(groups['timer_show']['stdout']).splitlines() if '=' in line)
    require(timer_show['LoadState']=='loaded' and timer_show['InvocationID']==original['timer_invocation_id'] and
        timer_show['Unit']==cpu_owner['unit'],'Original CPU timer incarnation/owned service differs')
    stops=[reader(item['stop']) for item in release['owned_release']]
    require(len(stops)==2 and all(command['argv']==['systemctl','--user','stop',item['unit']] and command['returncode']==0
        for command,item in zip(stops,release['owned_release'])) and
        max(ended)<=stops[0]['started_unix_s']<=stops[0]['ended_unix_s']<=stops[1]['started_unix_s'],
        'All six original CPU archives must complete BEFORE exact timer-first release')
    require((release['status']=='PASS' or verified_known_CPU_metadata_review(execution,job_pin,report_pin,completion_pin,completion,reader)) and release['original_exec_code']==1 and release['original_exit']==0 and
        release['original_result']=='success' and release['original_archived_before_release'] is True and release['unit_released'] is True and
        release['CPU_report']==report_pin and release['cpu_job']==job_pin and
        (release['original_pid'],release['original_starttime_ticks'],release['original_invocation'])==
        (cpu_owner['pid'],cpu_owner['starttime_ticks'],cpu_owner['invocation_id']) and
        archive['full_original_archives']['service_show']['stdout']==execution['show'] and
        archive['full_original_archives']['service_cat']['stdout']==execution['cat'] and
        archive['full_original_archives']['service_journal']['stdout']==execution['journal'] and
        [x['unit'] for x in release['owned_release']]==[execution['timer'],cpu_owner['unit']] and
        all(x['stop_returncode']==0 and x['final_load_state']=='not-found' for x in release['owned_release']) and
        execution['job']==job_pin and execution['report']==report_pin and execution['completion']==completion_pin and
        execution['command']==completion['argv'],'Genuine original retained CPU0/archive-before exact timer-first release required')


def check_transition(case,result,job,window,change,barrier,reader):
    recipes=load_selector().load('recipe');selected=recipes.check_recipe(case['recipe'])
    spec=job['phase_snapshot'];phase=result['current_phase']
    require(recipes.from_held(job['source_control_context']['held_recipe_context'])==selected,
        'Endpoint numerical context must match selected window/capture recipe')
    require(result['control_transition']==window['proofs']['control_transition'] and result['barrier']==window['proofs']['barrier'] and
        result['control_after']==window['proofs']['control'] and barrier['completed_clock']==window['post_control_barrier_clock'],
        'Original transition/barrier/control proof tuple required')
    original=reader(result['original_control_archive']);control=reader(job['source_control_context']['archived_control'])
    recipes.check_control(original,control,job['experiment'],selected)
    
    require(result['original_control_archive']['sha256']==case['control_before']['sha256'] and
        change['before']==case['control_before'] and change['archive']==result['control_after'] and
        change['after']['path']==case['control_before']['path'] and
        change['after']['sha256']==result['control_after']['sha256']==job['source_control_context']['archived_control']['sha256'] and
        change['after']['bytes']==result['control_after']['bytes']==job['source_control_context']['archived_control']['bytes'] and
        change['completed_clock']['boot_id']==barrier['completed_clock']['boot_id'] and
        change['completed_clock']['monotonic_s']<=barrier['completed_clock']['monotonic_s'],
        'Exact owned recipe transaction/archive and post-refresh barrier required')
    barrier_acquisition=reader(barrier['frozen']['acquisition'])
    require(barrier_acquisition['tag']==case['tags']['barrier'] and
        barrier_acquisition['owner_before']==barrier_acquisition['owner_after']==spec['owner'] and
        barrier_acquisition['phase_record_sha256']==phase['record']['sha256'] and
        barrier_acquisition['completed_slot_transition']['before']['actual_pin']==case['completed_slot'] and
        barrier_acquisition['completed_slot_transition']['after']['actual_pin']==barrier['completed_slot'] and
        len(barrier['request_publications'])==1 and
        barrier['request_publications'][0]['tag']==case['tags']['barrier'] and
        barrier['request_publications'][0]['pin']==barrier_acquisition['completed_slot_transition']['request']['actual_pin'],
        'Exactly one declared barrier precedes the one endpoint request')
    return control


def validate(binding,*,reader=read,raw_reader=read_raw,text_reader=archive_text,
             journal_reader=lambda p:archived_bytes(p,allow_empty=True),observer=None):
    require(set(binding)=={'schema','activation_authorized','experiment','candidate','reference','evidence','current_ce_phase',
        'runtime_baseline','runtime_anchor','predecessor_quality_plan','campaign','recipe'} and binding['schema']==SCHEMA and
        binding['activation_authorized'] is True,'Explicit prospective quality binding required')
    recipes=load_selector().load('recipe');selected=recipes.check_recipe(binding['recipe'])
    check_reference(binding['reference'],reader);e=binding['evidence'];require(set(e)==EVIDENCE_KEYS,'Exact original capture/window/CPU evidence required')
    raw_keys={'window_result','decision','trigger_API'}
    v={k:(raw_reader(pin) if k in raw_keys else reader(pin)) for k,pin in e.items()}
    case,result=v['capture_case'],v['capture_result'];job,proof,completion=v['phase_cpu_job'],v['phase_cpu_report'],v['phase_cpu_completion']
    require(case['schema']=='robotron-live-ce-lr-continuation-case-v1' and case['capture_authorized'] is True and
        result['schema']=='robotron-live-ce-lr-continuation-result-v1' and result['status']=='CAPTURED_PENDING_ROOT_CPU' and
        result['root_case']==result['root_precommit']==e['capture_case'] and result['CPU_executed'] is False and
        result['qualification_pass'] is False and result['model_only'] is True and result['replay_RNG_actor_anchor'] is False and
        result['control_changed'] is True and result['hold_recipe_through_quality'] is True and result['restored_control'] is False and result['owner_actions'] is False and
        result['cpu_job']==e['phase_cpu_job'] and result['window_job']==e['window_job'] and result['window_result']==e['window_result'] and
        result['trigger_API']==e['trigger_API'],'Successful original typed capture/window tuple required')
    check_root_capture(v['capture_release'],e['capture_result'],e['capture_case'],case,text_reader)
    require(case['recipe']==result['recipe']==binding['recipe'],'One typed endpoint recipe required')
    context=load_selector().activation_context(case,None)
    activated=context['activation'];phase=binding['current_ce_phase'];spec=job['phase_snapshot']
    require(phase==activated['startup']['phase']==result['current_phase'] and
        activated['owner']==result['owner']==spec['owner'] and
        phase==dict(record=spec['phase_record'],boot_checkpoint=spec['boot_checkpoint'],
            boot_verification=spec['boot_verification'],expected=spec['expected_phase']),
        'Same genuine diagnostic activation owner/phase required for candidate proof')
    historical=context['historical_report'];ready_clock=context['ready_clock']
    window,outcome,event,receipt=v['window_job'],v['window_result'],v['decision'],v['durability'];obs=observer or load_observer()
    require(window['post_control_barrier_clock']==v['barrier']['completed_clock'] and window['recipe']==selected and result['barrier']==e['barrier'] and result['control_transition']==e['control_transition'] and window['baseline']['api']['path']==str(Path(case['output_directory'])/'B-API.raw.json') and
        outcome['durability']['event']==e['decision'] and outcome['durability']['durability']==e['durability'],'Original READY/B/decision/durability path tuple differs')
    B=raw_reader(window['baseline']['api']);base,current=check_window(case,dict(result,_experiment=binding['experiment']),window,outcome,B,event,receipt,obs)
    root=Path(case['output_directory']);sequence=event['sequence']
    require(type(sequence) is int and sequence>=0 and e['decision']['path']==str(root/'observations'/('observation-%04d.json'%sequence)) and
        e['durability']['path']==str(root/'observations'/('durability-%04d.json'%sequence)) and
        e['trigger_API']['path']==str(root/'endpoint/trigger-API.json') and e['trigger_API'] in job['source_control_context']['provenance'],
        'Source-generated original event/trigger paths differ')
    check_cpu(job,proof,completion,binding['candidate'])
    require(triple(proof['job_file'])==triple(e['phase_cpu_job']) and result['cpu_argv']==completion['argv'] and
        result['source']==job['source'] and result['verification_copy']==job['verification_copy'] and result['acquisition']==spec['acquisition'] and
        binding['candidate']['tag']==case['tags']['endpoint'] and job['experiment']==binding['experiment'],
        'Only predeclared first frozen managed endpoint may be evaluated')
    acquisition=reader(spec['acquisition']);trigger=v['trigger_API'];floor=four(trigger)
    require(floor==four(job['clock_floor'])==four(acquisition['clock_floor']) and
        all(floor[k]>=max(four(historical['clocks'])[k],base['clocks'][k],current['clocks'][k]) for k in CLOCKS) and
        acquisition['purpose']=='candidate' and acquisition['client_count']==192 and acquisition['tag']==case['tags']['endpoint'] and
        acquisition['owner_before']==acquisition['owner_after']==spec['owner'] and acquisition['stopped_absence'] is None and
        acquisition['source_checkpoint']==triple(job['source']) and acquisition['phase_record_sha256']==phase['record']['sha256'] and
        acquisition['boot_checkpoint']==phase['boot_checkpoint'],'Exact fresh trigger4 at/after startup/B/firstLATCH acquisition required')
    require(trigger['client_count']==192 and trigger['training_enabled'] is True and trigger['measurement_active'] is False and
        trigger['managed_experiment']==binding['experiment'] and finite(trigger['lr'])==selected['scheduled_lr'],'Original fresh192 recipe trigger required')
    captured=reader(result['capture_completion']);transition=acquisition['completed_slot_transition']
    publications=captured['request_publications']
    require(len(publications)==1 and publications[0]['tag']==case['tags']['endpoint'] and publications[0]['pin']==transition['request']['actual_pin'] and
        publications[0]['archive']==transition['request']['archive'] and publications[0]['publication']['published'] is True and
        publications[0]['publication']['completed_identity']==transition['after']['actual_pin']['identity'] and
        transition['before']['actual_pin']==v['barrier']['completed_slot'],'Exactly one original managed publication from precommitted completed slot required')
    require(captured['status']=='COMPLETE' and captured['tag']==case['tags']['endpoint'] and captured['owner_before']==captured['owner_after']==spec['owner'] and
        captured['transition']==transition and transition['request_unix_s']<=transition['after_unix_s'] and
        transition['request']['actual_pin']['identity']['inode']==transition['after']['actual_pin']['identity']['inode'] and
        transition['request']['actual_pin']['sha256']==transition['after']['actual_pin']['sha256'],
        'Genuine matched same-inode original capture request/completion required')
    check_CPU_release(v['CPU_execution'],e['phase_cpu_job'],e['phase_cpu_report'],e['phase_cpu_completion'],completion,reader,text_reader,journal_reader)
    check_transition(case,result,job,window,v['control_transition'],v['barrier'],reader)
    baseline=reader(binding['runtime_baseline']);anchor=binding['runtime_anchor'];api=raw_reader(baseline['actual_API'])
    require(baseline['status']=='PASS' and baseline['main_owner']==anchor['main_owner']==spec['owner'] and
        all(baseline[k]==anchor[k] for k in ('fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')) and
        len(anchor['actors'])==len({a['pid'] for a in anchor['actors']})==192 and len(anchor['source_hashes'])==62 and
        len(anchor['control_hashes'])==2 and len(anchor['unit_files'])==3 and baseline['actual_activation']==case['activation']['result'] and
        baseline['source_hashes']==activated['healthy192']['binding']['bindings']['source_hashes'] and
        {a['pid'] for a in anchor['actors']}=={a['pid'] for a in activated['healthy192']['binding']['bindings']['actors']},
        'Fresh same-owner diagnostic CE4096 source/192 baseline required')
    check_diagnostic_sources(anchor['source_hashes'],reader(baseline['actual_selected_environment']))
    for name,digest in CANDIDATE_SOURCES.items():require(anchor['source_hashes'][str(GAME/'Scripts/dqn'/name)]==digest,'Candidate5 science source changed')
    require(anchor['source_hashes'][str(GAME/'Scripts/dqn/socket_server.py')]==EVALUATOR['Scripts/dqn/socket_server.py'] and
        anchor['control_hashes'][str(GAME/'models_dqn/learning_control.json')]==result['control_after']['sha256'] and
        api['client_count']==192 and api['training_enabled'] is True and api['measurement_active'] is False and
        api['managed_experiment']==binding['experiment'] and finite(api['lr'])==selected['scheduled_lr'] and
        all(four(api)[k]>=four(proof['clocks'])[k] for k in CLOCKS) and
        baseline['actual_API']['identity']['mtime_ns']>=e['phase_cpu_report']['identity']['mtime_ns'],
        'Fresh postCPU recipe/192/current socket/control baseline required')
    exposure=obs.normalise(api);require(exposure['optimizer_identity']==base['optimizer_identity'] and exposure['replay_identity']==base['replay_identity'],
        'Same owner original optimizer/replay epochs required')
    require(case['source_freeze_release']['sha256']==QUALITY_RELEASE_SHA and
        binding['predecessor_quality_plan']['sha256']==PREDECESSOR_PLAN_SHA and
        e['historical_invalid49_release']['sha256']==INVALID49_RELEASE_SHA,
        'Exact confirmed704 release/immediate409322 and historical invalid49 pointers required')
    predecessor=reader(binding['predecessor_quality_plan'])
    check_historical_sources(predecessor,v['historical_invalid49_release'],v['historical_invalid49_plan'],
        e['historical_invalid49_plan'])
    campaign=binding['campaign']
    for key in ('output_directory','preview_directory','execution_directory'):
        path=Path(campaign[key]);require(path.is_absolute() and path==path.resolve(strict=False) and path.is_relative_to(GAME/'logs/managed-learning-20261015'),'Canonical fresh quality directory required')
    require(len({campaign[k] for k in ('output_directory','preview_directory','execution_directory')})==3 and
        re.fullmatch('robotron-quality-[A-Za-z0-9_-]+',campaign['unit']) and campaign['reference_label']!=campaign['candidate_label'] and campaign['hypothesis'].strip(),
        'Fresh unique prospective2400/3600 RCRC campaign binding required')
    return dict(cpu_job=job,proof=proof,completion=completion,capture=result,current_ce_phase=phase,window=window,baseline=baseline,predecessor=predecessor,activation=activated,activation_pins=case['activation'])
