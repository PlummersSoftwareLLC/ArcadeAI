"""Prepare/close exact original CPU facts/profile scopes without model adoption.

Uses the unchanged benchmark, profile producer and independent profile adopter.
Original six-descriptor CPU archives are checked before preserving any facts.
Default invocation is inert. No service launch or learner-state mutation here.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def helpers():
    return load('_original_profile_scope_helpers', ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')


def read(pin, h):
    path = h.checked(pin)
    h.require(pin['identity']['mode'] == '0o444', 'Sealed original metadata required')
    return json.loads(path.read_bytes())


def prepare(capture_result, output, *, canonical_closeout=None):
    h = helpers()
    result_pin = h.pin(capture_result.resolve())
    result = read(result_pin,h)
    h.require(result['state'] == 'captured_CPU_verified' and result['promotion'] is False
              and result['added']['applied_updates'] >= 5000 and result['added']['replay_inserts'] >= 1_000_000
              and result['added']['elapsed_s'] >= 3600, 'Actual completed independent capture required')
    checkpoint = h.pin(result['endpoint']['path'])
    h.require(checkpoint['sha256'] == result['endpoint']['sha256']
              and checkpoint['identity']['mode'] == '0o444'
              and checkpoint['sha256'] != '444a14287789b26e3d84564cf4a9e49518d82d91d6a3ed82ca09526ef89c8523',
              'Exact distinct immutable new candidate required')
    directory = output.resolve()
    directory.mkdir(mode=0o700)
    benchmark = h.pin(ROOT/'tools/benchmark_sidecar_inference.py')
    h.require(benchmark['sha256'] == '39d90c6dc70d69a4fef4c7244868819ddd06f7cc4283998d821632cf0ce2bde5',
              'Actual unchanged inference benchmark required')
    mode = 'canonical' if canonical_closeout is None else 'frozen'
    job = dict(checkpoint=checkpoint, benchmark=benchmark, output=str(directory/'runtime'))
    if mode == 'canonical':
        argv = [benchmark['path'],'--cpu-facts','--checkpoint',checkpoint['path'],'--directory',job['output']]
        inputs = [checkpoint,benchmark,result_pin]
    else:
        authority = h.pin(canonical_closeout.resolve())
        closed = read(authority,h)
        h.require(closed['schema'] == 'robotron-original-canonical-CPU-profile-closeout-v1'
                  and closed['checkpoint'] == checkpoint and closed['actual_exit'] == 0,
                  'Actual closed original canonical facts required')
        old = ROOT/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/selected-candidate-frozen-profile-v2-CPU-original01/job.json'
        recipe = json.loads(old.read_bytes())
        job.update(driver=h.pin(HERE/'check_frozen_profile_cpu_v2.py'), package=recipe['package'],
                   canonical_CPU_facts=closed['immutable_facts'])
        for pin in job.values():
            if isinstance(pin,dict) and 'sha256' in pin:
                h.checked(pin)
        inputs = [*list(pin for pin in job.values() if isinstance(pin,dict)),result_pin,authority]
    jp = h.put(directory/'job.json',job)
    if mode == 'frozen':
        argv = [job['driver']['path'],'--job',jp['path'],'--job-sha256',jp['sha256']]
    control_path = ROOT/'tools/quality_capacity_proposal/control_quality32_review_v1.py'
    control = load('_profile_scope_actual_controller',control_path)
    config = dict(unit='robotron-new-candidate-'+mode+'-CPU-'+checkpoint['sha256'][:12]+'-original01.service',
        output=str(directory/'execution-original01'), argv=[str(ROOT.parent/'.venv-gb300/bin/python'),
            '-Xgil=0','-I','-B',*argv],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
                    'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=240, pins=[control.pin(pin['path']) for pin in [jp,*inputs]])
    cp = h.put(directory/'controller-config.json',config)
    h.require(control.checked_config(cp['path']) == config,'Actual CPU controller ABI differs')
    return h.put(directory/'prepared-NOT-LAUNCHED.json',dict(mode=mode,job=jp,config=cp,
        capture_result=result_pin,source=h.pin(Path(__file__).resolve()),controller=h.pin(control_path),
        quality_qualified=False,promotion=False))


def close(directory):
    h = helpers()
    directory = directory.resolve()
    packet = read(h.pin(directory/'prepared-NOT-LAUNCHED.json'),h)
    h.checked(packet['source'])
    job = read(packet['job'],h)
    config = read(packet['config'],h)
    control = load('_profile_scope_closed_controller',h.checked(packet['controller']))
    h.require(control.checked_config(packet['config']['path']) == config,'Exact original config differs')
    for pin in config['pins']:
        h.require(control.pin(pin['path']) == pin,'Original launch input changed')
    immutable = load('_profile_scope_immutable',ROOT/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    archive = load('_profile_scope_original_archives',ROOT/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    root = Path(config['output'])
    owner_pin = h.pin(root/'root-original-identity.json')
    closure_pin = h.pin(root/'root-original-result-and-owned-release.json')
    owner, closure = read(owner_pin,h), read(closure_pin,h)
    terminal = archive.archived_closure(closure,owner,immutable.read_pin,exit_zero=True)
    expected = dict(Id=config['unit'],ExecMainPID=str(owner['pid']),InvocationID=owner['invocation_id'],
        MainPID='0',ExecMainCode='1',ExecMainStatus='0',NRestarts='0',Restart='no',CPUQuotaPerSecUSec='2s',
        MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='3min',SendSIGKILL='no')
    h.require(all(terminal[key] == value for key,value in expected.items()),'Actual original CPU scope/exit/resources differ')
    h.require(all(arg in terminal['ExecStart'] for arg in config['argv'])
              and 'CUDA_VISIBLE_DEVICES=' in terminal['ExecStart'],'Actual isolated CPU command differs')
    first = read(h.pin(root/'original-first-observed-show-command.json'),h)
    live = dict(line.split('=',1) for line in immutable.read_pin(first['stdout'],as_json=False).decode().splitlines() if '=' in line)
    h.require(live['MainPID'] == str(owner['pid']) and live['InvocationID'] == owner['invocation_id']
              and not Path('/sys/fs/cgroup'+live['ControlGroup']).exists(), 'Original live owner/cgroup closure differs')
    path = Path('/proc',str(owner['pid']),'stat')
    h.require(not path.exists() or int(path.read_text().rsplit(')',1)[1].split()[19]) != owner['starttime_ticks'],
              'Original CPU birth remains')
    h.require(all(control.show(unit)['LoadState'] == 'not-found' for unit in (owner['unit'],owner['timer'])),
              'Original unit/timer remains')
    raw_path = Path(job['output'])/'result.json'
    original = h.pin(raw_path)
    raw = raw_path.read_bytes()
    h.require(h.pin(raw_path) == original and len(raw) < 1<<20,'Original closed CPU facts changed or exceed bound')
    facts = json.loads(raw)
    h.require(facts['checkpoint_sha256'] == job['checkpoint']['sha256']
              and facts['cuda_initialized'] is False and facts['inference_error'] is None,
              'Actual CPU inference facts differ')
    if packet['mode'] == 'frozen':
        h.put(directory/'actual-original-terminal-properties.json',terminal)
        adopter = load('_unchanged_profile_original_adopter',HERE/'adopt_profile_scope_v2.py')
        adopted = adopter.adopt(directory,owner['unit'],owner['pid'],owner['invocation_id'],
                                directory/'actual-original-terminal-properties.json')
        return h.put(directory/'independent-original-profile-scope-closeout.json',dict(
            schema='robotron-original-frozen-profile-CPU-scope-closeout-v1',status='PASS',
            actual_exit=0,owner=owner_pin,closure=closure_pin,profile_adoption=adopted,
            all_six_descriptors_resources_argv_birth_unit_timer_cgroup_and_release_verified=True,
            quality_qualified=False,promotion=False))
    exact = directory/'canonical-CPU-facts.exact.json'
    with exact.open('xb') as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return h.put(directory/'independent-original-canonical-CPU-closeout.json',dict(
        schema='robotron-original-canonical-CPU-profile-closeout-v1',status='PASS',checkpoint=job['checkpoint'],
        original_job=packet['job'],immutable_facts=h.pin(exact),actual_exit=0,owner=owner_pin,closure=closure_pin,
        all_six_descriptors_resources_argv_birth_unit_timer_cgroup_and_release_verified=True,
        source=h.pin(Path(__file__).resolve()),quality_qualified=False,promotion=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',action='store_true');p.add_argument('--close',action='store_true')
    p.add_argument('--capture-result',type=Path);p.add_argument('--directory',type=Path)
    p.add_argument('--canonical-closeout',type=Path)
    args = p.parse_args()
    if args.prepare:
        print(json.dumps(prepare(args.capture_result,args.directory,canonical_closeout=args.canonical_closeout)),flush=True)
    elif args.close:
        print(json.dumps(close(args.directory)),flush=True)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
