"""Qualify four exact serialized fullgame contexts before private ownership."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch


def require(value,reason):
    if not value:raise ValueError(reason)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def execute(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Actual CPU context driver differs')
    raw=args.job.read_bytes();require(hashlib.sha256(raw).hexdigest()==args.job_sha256,'Actual CPU job differs');job=json.loads(raw)
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and 'torch'not in sys.modules,'CPU only required')
    fields=dict(line.split('=',1)for line in subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=5).splitlines()if'='in line)
    expected=dict(MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='3min',NRestarts='0',Restart='no')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual2CPU/4GiB/180s scope differs')
    h=load('_fullgame_CPU_helpers',Path(job['helpers']['path']))
    for pin in job['inputs']:h.checked(pin)
    prepared=json.loads(h.checked(job['prepared']).read_bytes());cases=prepared['cases']
    require(job['schema']=='robotron-fullgame-four-exact-CPU-job-v1'and job['original_attempt']==1 and job['no_retry']is True,'Original exact CPU job required')
    require([case['leg']for case in cases]==['R1','C1','R2','C2'],'Exact four ordered jobs required')
    engineering=prepared['engineering_only']
    require(engineering is job['engineering_only'],'CPU/native engineering domain differs')
    if not engineering:
        producer=load('_fullgame_exact_production_eligibility',Path(__file__).with_name('prepare_fullgame_study.py'))
        producer.eligible_screen(prepared['screen_assessment'],prepared['reference_epoch'],h)
    controller=load('_fullgame_exact_controller',Path(__file__).with_name('control_fullgame_rounds.py'))
    native=load('_fullgame_actual_native',h.checked(cases[0]['runtime']))
    reviewer=load('_fullgame_actual_reviewer',h.checked(job['reviewer']))
    contract=native.round_contract()
    derivation=contract.validate_derivation(cases[0]['runtime']['path'],job['reviewer']['path'])
    proofs=[];negative=[];started=time.monotonic()
    for case in cases:
        subject=json.loads(h.checked(case['native_job']).read_bytes())
        ctx=native.validate_completed_context(subject,h)
        require(ctx['pair']['engineering_only']is engineering and ctx['family']['native_launch_qualified']is (not engineering),'Exact engineering/production domain required')
        scope=json.loads(h.checked(case['acceptance']).read_bytes())
        cfg=json.loads(h.checked(case['unqualified_controller_config']).read_bytes())
        require(controller.checked_config(case['unqualified_controller_config']['path'])==cfg,'Actual controller interface differs')
        reviewer.validate_scope(subject,case['native_job'],scope,cfg)
        try:
            with patch.object(subprocess,'run',side_effect=AssertionError('Private process/GPU controls reached during engineering refusal')):
                native.run(subject,case['native_job'],h)
        except ValueError as error:
            require(engineering and 'Engineering context can never launch'in str(error),'Wrong refusal point')
        except FileNotFoundError as error:
            require(not engineering and error.filename==subject['prelaunch_CPU_closeout']and not Path(error.filename).exists(),'Only absent prospective exact CPU receipt may stop a production prebody')
        else:raise ValueError('Engineering actual native entry allowed a scientific launch')
        require(not Path(subject['output']).exists(),'Engineering entry created private output')
        proofs.append(dict(leg=case['leg'],native_job=case['native_job'],actual_completed_prebody_context=True,
            actual_independent_scope_consumer=True,actual_native_run_refused_before_private_output_lease_GPU_or_Torch=True,
            pair_minimum_complete_games=ctx['pair']['minimum_complete_games_each'],original_transport_floor_retained=subject['minimum_completed_games']))
        for fault in ('pair_floor','job_floor','cohort_timeout','missing_slot','wrong_policy','wrong_ROM','wrong_lease','wrong_runtime','protocol_samples','family_domain','main_owner','main_epoch'):
            trial=copy.deepcopy(subject)
            with tempfile.TemporaryDirectory(prefix='robotron-fullgame-guard-')as temporary:
                directory=Path(temporary)
                if fault=='pair_floor':
                    value=copy.deepcopy(ctx['pair']);value['minimum_complete_games_each']=50;trial['quality_pair_precommit']=h.put(directory/'pair.json',value)
                elif fault=='job_floor':trial['confirmation_min_complete_games']=50
                elif fault=='cohort_timeout':trial['whole_cohort_timeout_s']+=1
                elif fault=='missing_slot':trial['actor_slots']=trial['actor_slots'][:-1]
                elif fault=='wrong_policy':trial['checkpoint']=copy.deepcopy(trial['checkpoint']);trial['checkpoint']['sha256']='f'*64
                elif fault=='wrong_ROM':trial['loaded_rom_sha256']='f'*64
                elif fault=='wrong_lease':trial['lease']=copy.deepcopy(trial['lease']);trial['lease']['identity']['inode']+=1
                elif fault=='wrong_runtime':trial['runtime']=copy.deepcopy(trial['runtime']);trial['runtime']['sha256']='f'*64
                elif fault=='protocol_samples':
                    value=copy.deepcopy(ctx['protocol']);value['initial_samples']=5;trial['main_health_protocol']=h.put(directory/'protocol.json',value)
                elif fault=='family_domain':
                    value=copy.deepcopy(ctx['family']);value['engineering_only']=not engineering;trial['source_family_manifest']=h.put(directory/'family.json',value)
                else:
                    value=copy.deepcopy(ctx['binding'])
                    if fault=='main_owner':value['owners']['trainer']['process']['pid']+=1
                    else:value['exposure']['replay']['epoch']+=1
                    bp=h.put(directory/'binding.json',value);trial['main_binding']=bp
                    protocol=copy.deepcopy(ctx['protocol']);protocol['case']=bp;trial['main_health_protocol']=h.put(directory/'protocol.json',protocol)
                    family=copy.deepcopy(ctx['family']);family['current_main_binding']=bp;trial['source_family_manifest']=h.put(directory/'family.json',family)
                try:native.validate_completed_context(trial,h)
                except (ValueError,AssertionError):negative.append(dict(leg=case['leg'],fault=fault,rejected=True))
                else:raise ValueError('Actual context accepted damaged '+fault)
    require(len(proofs)==4 and len(negative)==48 and 'torch'not in sys.modules,'Missing actual contexts/guards or numerical import')
    for pin in job['inputs']:h.checked(pin)
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=h.put(output/'report.json',dict(schema='robotron-fullgame-four-exact-contexts-CPU-result-v1',status='PASS',original_job=h.pin(args.job),actual_PID=os.getpid(),actual_scope=fields,
        actual_contexts=proofs,actual_rejected_contexts=negative,source_derivation=derivation,elapsed_s=time.monotonic()-started,
        checkpoint_bytes_hashed_for_integrity=True,Torch_imported=False,weights_deserialized=False,GPU_or_MAME_launched=False,
        engineering_only=engineering,all_four_exact_contexts_qualified=True,
        scientific_launch_qualified=False,full_game_quality_qualified=False,promotion=False))
    print(json.dumps(dict(status='PASS',contexts=4,rejections=48,report=report)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path);parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if args.execute:execute(args)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
