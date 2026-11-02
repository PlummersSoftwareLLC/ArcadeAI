"""Run one prepared engineering native and its original independent CPU review."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G/'logs/managed-learning-20261015/run-26'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--sha256')
    args = parser.parse_args()
    if not args.execute:
        parser.print_help()
        return 0
    require(hashlib.sha256(args.prepared.read_bytes()).hexdigest() == args.sha256,
            'Exact prepared engineering packet required')
    h = load('_owned_engineering_runner_h', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    reader = load('_owned_engineering_reader', G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    read = lambda pin, as_json=True: reader.read_pin(pin, as_json=as_json)
    seq = load('_owned_engineering_original_sequence', G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py')
    archive = load('_owned_engineering_archive', G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    packet = read(h.pin(args.prepared))
    prepared = read(packet['native_prepared'])
    directory = Path(args.prepared).parent
    job = read(prepared['job'])
    require(job['engineering_only'] is True and job['quality_leg'] == 'E1'
            and packet['engineering_only'] is True and read(packet['preflight'])['status']=='PASS_ENGINEERING_CPU_PREFLIGHT_ONLY',
            'Only the new preflighted engineering case may run')
    owner = h.put(directory/'original-runner-owner.json', dict(pid=os.getpid(),birth=seq.birth(os.getpid()),
        runtime=h.pin(Path(__file__)),prepared=h.pin(args.prepared),original_attempt=1,no_retry=True,
        started_unix_s=time.time(),scientific_or_promotion=False))
    native_closed = review_closed = None
    error = None
    code = 1

    def invoke(target, config_pin, controller_pin):
        ctl = load('_owned_engineering_controller_'+target.name.replace('-','_'), h.checked(controller_pin))
        seq.invoke_controller_once(target,'',controller_pin,config_pin,h)
        closed = seq.verify_closed_scope(target,'',config_pin,h,read,archive,ctl,exit_zero=False)
        return read(closed['result'])['actual_exit'], closed

    try:
        actual, native_closed = invoke(directory,prepared['controller_config'],prepared['controller'])
        result_pin = h.pin(Path(job['output'])/'result.json')
        result = read(result_pin)
        require(actual == 0 and result['complete'] is True and not result['errors'],
                'Original engineering native failed; no replacement or retry')
        require(len(result['original_slots'])==32 and all(type(row['actual_exit']) is int
            and row['actual_exit']==0 and seq.birth(row['pid'])!=row['birth']
            and row['outputs_sealed_after_original_writer_closure'] is True
            for row in result['original_slots'].values()), 'Original MAME closeout incomplete')
        native_receipt = h.put(directory/'positive-original-native-closeout.json', dict(
            status='PASS_ORIGINAL_FULLGAME_LEG_NATIVE_SCOPE_CLOSED',actual_exit=actual,
            original_job=prepared['job'],original_controller_config=prepared['controller_config'],
            original_result=native_closed['result'],closure=native_closed['closure'],owner=native_closed['owner'],
            native_result=result_pin,original_Popen_reaped=True,all_original_controller_resources_closed=True,
            engineering_only=True,scientific_review_pending=False,independent_engineering_review_pending=True))
        review_directory = directory/'independent-review-original01'
        review_directory.mkdir(mode=0o700)
        config = read(packet['review_job_template'])
        config.pop('original_native_closeout_path')
        config['original_native_closeout'] = native_receipt
        review_job = h.put(review_directory/'job.json',config)
        cpu_path = B/'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/state-sources/control_stopped_fullstate600_CPU_v1.py'
        cpu = load('_owned_engineering_CPU_controller',cpu_path)
        cpu_config = h.put(review_directory/'controller-config.json',dict(
            unit='robotron-owned-overlap-raw-review-'+hashlib.sha256(str(directory).encode()).hexdigest()[:12]+'.service',
            output=str(review_directory/'execution-original01'),
            argv=[str(G.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',config['runtime']['path'],
                  '--execute','--job',review_job['path'],'--job-sha256',review_job['sha256']],
            properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
            pins=[cpu.pin(p['path']) for p in [config['runtime'],review_job]],observation_s=660))
        actual, review_closed = invoke(review_directory,cpu_config,h.pin(cpu_path))
        review = read(h.pin(Path(config['report'])))
        require(actual==0 and review['status']=='PASS_ENGINEERING_RAW64_PREFIX32_FULLPERMIT_STOP32_OWNED_MAIN'
                and review['engineering_only'] is True and review['slot_permit_body_hash_replay_performed'] is True,
                'Original independent engineering raw review failed; preserve without retry')
        code = 0
    except Exception:
        error = traceback.format_exc()
    require('torch' not in sys.modules, 'Original outer runner imported numerical runtime')
    report = h.put(directory/'original-runner-result.json',dict(
        status='PASS_OWNED_OVERLAP_FULLGAME_ENGINEERING_AND_ORIGINAL_RAW_REVIEW' if code==0 else 'FAIL_ORIGINAL_OWNED_OVERLAP_ENGINEERING_NO_RETRY',
        actual_exit=code,owner=owner,original_native_closed=native_closed,original_review_closed=review_closed,
        error=error,completed_unix_s=time.time(),original_attempt=1,no_retry=True,
        engineering_only=True,policy_quality_gain=False,promotion=False))
    print(json.dumps(dict(actual_exit=code,report=report,error=error)),flush=True)
    return code


if __name__=='__main__':
    raise SystemExit(main())
