#!/usr/bin/env python3
"""Prospective root-only224M/256M CPU lineage proof. Import/default/help are inert.

Only explicit --verify reads a future gate/checkpoint. One bounded byte snapshot
supplies both SHA and CPU load. No model, source, state or control writes exist.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
CAMPAIGN = RUN.parent
GAME = CAMPAIGN.parents[1]
REPO = GAME.parent
PRECOMMIT_SHA = '0264714f16d86a5fa6be5554f0c524ae3ede4e645a3ba8a17403a2064a66b186'
EXPERIMENT = 'best10M-fresh3-eps10-cap8-nosmooth'
ROLES = {'224M': 228629023, '256M': 260629023}
META_KEYS = ('engine_version', 'state_size', 'single_frame_state_size', 'frame_stack',
    'baseline_batch_size', 'training_steps', 'total_training_steps', 'optimized_samples',
    'learner_frame_count', 'frame_count', 'measurement_frame_count', 'last_target_update_samples',
    'lr_anchor_step', 'lr_gear', 'epsilon', 'expert_ratio')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def file_stat(path):
    path = Path(path)
    require(not path.is_symlink(), 'Symlink file refused')
    s = path.stat()
    require(stat.S_ISREG(s.st_mode), 'Regular file required')
    return dict(size=s.st_size, mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                inode=s.st_ino, device=s.st_dev, mode=oct(stat.S_IMODE(s.st_mode)), nlink=s.st_nlink)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_pinned(record, retained):
    path = Path(record['path'])
    before = file_stat(path)
    require(0 < before['size'] < 3_000_000 and valid_sha(record['sha256']), 'Bad bounded evidence pin')
    raw = path.read_bytes()
    require(digest(raw) == record['sha256'] and file_stat(path) == before, 'Changed pinned evidence: ' + str(path))
    retained[str(path)] = (record['sha256'], before)
    return raw


def recheck(retained):
    for path, (sha, before) in retained.items():
        require(file_stat(path) == before and digest(Path(path).read_bytes()) == sha,
                'Evidence changed before publication: ' + path)


def process_identity(pid):
    require(type(pid) is int and pid > 0, 'Invalid PID')
    parts = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()
    require(parts[0] != 'Z', 'Owned process is zombie')
    return dict(pid=pid, start_ticks=int(parts[19]))


def process_environment(pid):
    raw = Path('/proc', str(pid), 'environ').read_bytes()
    return dict(row.decode().split('=', 1) for row in raw.split(b'\0') if b'=' in row)


def require_integer(value, name):
    require(type(value) is int and value >= 0, 'Invalid saved integer: ' + name)


def exposure(before, after, adam_before, adam_after):
    keys = {'logical_updates_delta': 'training_steps', 'optimized_samples_delta': 'optimized_samples',
            'learner_frames_delta': 'learner_frame_count', 'fleet_frames_delta': 'frame_count'}
    for meta in (before, after):
        for field in keys.values():
            require_integer(meta[field], field)
    result = {name: after[field] - before[field] for name, field in keys.items()}
    require(result['logical_updates_delta'] > 0 and all(v >= 0 for v in result.values())
        and result['optimized_samples_delta'] == 4096 * result['logical_updates_delta'], 'Saved4096 exposure/chronology differs')
    for values in (adam_before, adam_after):
        require(isinstance(values, list) and len(values) == 1 and type(values[0]) in (int, float)
            and math.isfinite(values[0]) and float(values[0]).is_integer() and values[0] >= 0, 'Uniform integral Adam clocks required')
    adam_delta = adam_after[0] - adam_before[0]
    require(0 <= adam_delta <= result['logical_updates_delta'], 'Adam clocks regressed or exceed logical attempts')
    return dict(recorded_batch_size=4096, **result, Adam_parameter_steps_before=adam_before,
        Adam_parameter_steps_after=adam_after, Adam_uniform_step_delta=adam_delta,
        logical_minus_uniform_Adam_delta=result['logical_updates_delta'] - adam_delta,
        interpretation='Actual saved clocks, not reconciled process AMP counts or fresh replay admissions.')


def validate_gate(gate, role, path, metadata=None):
    require(role in ROLES and gate['tag'] == 'fresh3-' + role and type(gate['target']) is int
        and gate['target'] == ROLES[role] and gate['experiment'] == EXPERIMENT
        and Path(gate['checkpoint']).absolute() == Path(path).absolute(), 'Gate role/target/branch/checkpoint differs')
    trigger = gate['trigger_snapshot']
    for key in ('learner_frame_count', 'frame_count', 'training_steps', 'optimized_samples', 'client_count'):
        require_integer(trigger[key], 'trigger ' + key)
    require(trigger['learner_frame_count'] >= ROLES[role] and trigger['client_count'] == 192, 'Gate boundary differs')
    if metadata is not None:
        require(all(metadata[k] >= trigger[k] for k in ('learner_frame_count', 'frame_count', 'training_steps', 'optimized_samples')),
                'Actual saved clock precedes trigger; trigger is not the saved clock')


def validate_saved(saved, reference, latest_anchor, role, gate, cpu, torch):
    require(isinstance(saved, dict), 'Checkpoint must be a dictionary')
    metadata = {key: cpu.scalar(saved[key], torch) for key in META_KEYS}
    for key in META_KEYS[:12]:
        require_integer(metadata[key], key)
    previous = reference['saved_metadata']
    require(all(metadata[k] == previous[k] for k in ('engine_version', 'state_size', 'single_frame_state_size',
        'frame_stack', 'baseline_batch_size')), 'Saved architecture metadata changed')
    require(metadata['training_steps'] == metadata['total_training_steps']
        and metadata['frame_count'] >= metadata['learner_frame_count'] >= ROLES[role]
        and metadata['measurement_frame_count'] == previous['measurement_frame_count'] == 7550388
        and latest_anchor['last_target_update_samples'] <= metadata['last_target_update_samples'] <= metadata['optimized_samples']
        and metadata['optimized_samples'] - metadata['last_target_update_samples'] < 1000 * 512,
        'Saved clocks/target phase differ')
    require(type(metadata['epsilon']) in (int, float) and metadata['epsilon'] == .1
        and type(metadata['expert_ratio']) in (int, float) and math.isfinite(metadata['expert_ratio'])
        and abs(metadata['expert_ratio'] - .1) < 1e-12
        and metadata['lr_gear'] == previous['lr_gear'] == 'climb'
        and type(metadata['lr_anchor_step']) in (int, float) and math.isfinite(metadata['lr_anchor_step'])
        and metadata['lr_anchor_step'] == previous['lr_anchor_step'] == 0, 'Saved behavior/LR controls differ')
    opt = saved['optimizer_state_dict']
    require(isinstance(opt, dict) and isinstance(opt.get('state'), dict)
        and len(opt['state']) == 81 and all(type(owner) is int for owner in opt['state'])
        and all(isinstance(row, dict) and set(row) == {'step', 'exp_avg', 'exp_avg_sq'} for row in opt['state'].values()),
        'Malformed Adam81 ownership/state')
    steps = sorted({float(cpu.scalar(row['step'], torch)) for row in opt['state'].values()})
    # Reuse the reviewed inventory, ordered99 moment-owner, groups/LR, scaler and
    # finite443 CPU validator. The manifest below is NOT independent clock proof;
    # actual clock acceptance is supplied by reference/anchors/gate/exposure here.
    facts = cpu.validate_checkpoint(saved, dict(saved_metadata=metadata, optimizer_state_count=81,
        optimizer_parameter_steps=steps), reference, torch)
    require(len(steps) == 1, 'Adam state steps must be uniform')
    validate_gate(gate, role, gate['checkpoint'], metadata)
    return metadata, facts


def publish(path, report, before_publish):
    raw = (json.dumps(report, indent=2, allow_nan=False) + '\n').encode()
    fd, temporary = tempfile.mkstemp(prefix='.future-cpu-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        before_publish()
        os.link(temporary, path)  # exclusive final publication; no replacement
        os.unlink(temporary)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return digest(raw)


def execute(args):
    require(args.role in ROLES and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'Explicit role and hidden CUDA required')
    require(all(valid_sha(v) for v in (args.gate_sha256, args.precommit_sha256))
        and args.precommit_sha256 == PRECOMMIT_SHA
        and (args.checkpoint_sha256 is None or valid_sha(args.checkpoint_sha256)),
        'Explicit gate/precommit pins required; optional expected candidate SHA must be valid')
    output = Path(args.output)
    require(not output.is_symlink() and output.absolute().parent == RUN
        and output.name == 'fresh3-' + args.role + '-checkpoint-lineage.json' and not output.exists(), 'New fixed lineage output required')
    require((args.role == '224M' and args.prior_224_lineage is None and args.prior_224_lineage_sha256 is None)
        or (args.role == '256M' and args.prior_224_lineage is not None and valid_sha(args.prior_224_lineage_sha256)),
        '256M requires explicit final224M lineage pin;224M cannot consume one')
    start, tick = datetime.now(timezone.utc).isoformat(), time.monotonic()
    retained = {}
    contract = json.loads(read_pinned(dict(path=str(HERE/'future-cpu-precommit.json'), sha256=PRECOMMIT_SHA), retained))
    verifier_sha = digest(Path(__file__).read_bytes())
    read_pinned(dict(path=str(Path(__file__).resolve()), sha256=verifier_sha), retained)
    documents = {}
    for name, record in contract['evidence'].items():
        raw = read_pinned(record, retained)
        if Path(record['path']).suffix == '.json':
            documents[name] = json.loads(raw)
    # All completed chronology and current source/control evidence is bound
    # before any future gate/model read or Torch import.
    common = load_module('future_cpu_common', contract['evidence']['common']['path'])
    sys.modules['startup_common'] = common
    cpu = load_module('future_cpu_checks', contract['evidence']['cpu_checks']['path'])
    reference_report = documents['reference192M']; reference = reference_report['candidate']
    require(reference_report['PASS'] is True and reference_report['proposal_only'] is False
        and reference_report['root_verification']['status'] == 'PASS'
        and reference_report['root_verification']['CUDA_initialized'] is False, 'Final192M CPU proof required')
    require(documents['protected192_metadata']['sha256'] == reference['sha256']
        and documents['protected192_metadata']['saved_checkpoint_metadata'] == reference['saved_metadata']
        and documents['promotion192']['root_promoted'] is True
        and documents['promotion192']['new_incumbent']['sha256'] == reference['sha256'], 'Protected192 provenance differs')
    anchors = [documents['run24_anchor'], documents['run25_anchor']]
    for anchor in anchors:
        require(anchor['cpu_only'] is True and anchor['cuda_initialized'] is False
            and anchor['optimizer_tensors_finite_CPU'] is True and anchor['optimizer_state_count'] == 81
            and anchor['architecture_unchanged'] is True, 'Completed resume CPU proof differs')
    chronology, completed_exposure = contract['collector_resume_chronology'], []
    before_meta, before_steps = reference['saved_metadata'], reference['optimizer']['step_values']
    for key, anchor, recorded in zip(('run24_anchor', 'run25_anchor'), anchors, chronology, strict=True):
        require(recorded['path'] == contract['evidence'][key]['path'] and recorded['sha256'] == contract['evidence'][key]['sha256']
            and recorded['saved_metadata'] == anchor['saved_metadata'], 'Anchor chronology pin differs')
        completed_exposure.append(exposure(before_meta, anchor['saved_metadata'], before_steps, anchor['optimizer_parameter_steps']))
        before_meta, before_steps = anchor['saved_metadata'], anchor['optimizer_parameter_steps']
    runtime, environment, observation = documents['runtime'], documents['environment'], documents['run25_observation']
    require(runtime['environment'] == environment == observation['environment']
        and observation['PASS'] is True and documents['controls'] == contract['controls'], 'Runtime/control provenance differs')
    require(documents['controls']['experiment'] == EXPERIMENT and documents['controls']['lr_scale'] == .5
        and documents['controls']['epsilon_ramp']['start'] == documents['controls']['epsilon_ramp']['end'] == .1,
        'Held branch control differs')
    wanted = dict(DQN_BATCH_SIZE='4096', DQN_COMPILE_MODE='default', DQN_LEARNING_EXPOSURE_COUNTERS='1',
        DQN_N_STEP='3', DQN_MAX_SAMPLES_PER_FRAME='8', DQN_C51_TARGET_SMOOTHING='0',
        DQN_STREAM_BANK_OUTPUT='1', DQN_EXACT_INFERENCE_GRAPHS='1', DQN_NATIVE_BATCH_UPDATE='1',
        DQN_INFERENCE_BATCH_WAIT_MS='1', DQN_REPLAY_PREFETCH='1', DQN_DIRECT_REPLAY_FILL='1')
    require(all(environment.get(k) == v for k,v in wanted.items()), 'Held environment recipe differs')
    for key, recorded in zip(('run23_observation', 'run24_observation', 'run25_observation'), contract['completed_process_chronology'], strict=True):
        old = documents[key]
        require(old['PASS'] is True and old['pid'] == recorded['pid'] and old['start_ticks'] == recorded['start_ticks']
            and old['environment']['DQN_INFERENCE_BATCH_WAIT_MS'] == recorded['collector_wait_ms']
            and old['source_hashes'] == observation['source_hashes'] and old['private12_hashes'] == observation['private12_hashes'],
            'Recorded process/source chronology differs')
        normalized = dict(old['environment'], ROBOTRON_RUN_DIR=environment['ROBOTRON_RUN_DIR'], DQN_INFERENCE_BATCH_WAIT_MS='1')
        require(normalized == environment, 'Recorded chronology changes more than runpath/collector')
    require(len(observation['source_hashes']) == 20 and len(observation['private12_hashes']) == 12, 'Source inventory differs')
    for base, mapping in ((REPO, observation['source_hashes']), (GAME, observation['private12_hashes'])):
        for name, sha in mapping.items():
            require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe source path')
            read_pinned(dict(path=str(base/name), sha256=sha), retained)
    current = contract['expected_main']
    require(observation['pid'] == current['pid'] and observation['start_ticks'] == current['start_ticks'], 'Current main baseline differs')
    def check_main():
        require(process_identity(current['pid']) == current, 'Main restarted; reviewed chronology amendment required')
        actual = process_environment(current['pid'])
        require(common.selected_environment(actual) == environment and actual.get('LD_PRELOAD') is None, 'Main actual environment differs')
        require(b'-Xgil=0' in Path('/proc', str(current['pid']), 'cmdline').read_bytes(), 'Main free-threaded command differs')
        pin = documents['actors']
        require(pin['trainer_pid'] == current['pid'] and pin['trainer_start_ticks'] == current['start_ticks']
            and len(pin['actors']) == 192 and len({r['pid'] for r in pin['actors']}) == 192
            and all(type(r['slot']) is int for r in pin['actors']) and {r['slot'] for r in pin['actors']} == set(range(192)), 'Main actor pin differs')
        for row in pin['actors'] + pin['supervisor_identities']:
            require(type(row['start_ticks']) is int and process_identity(row['pid']) == {k: row[k] for k in ('pid', 'start_ticks')},
                    'Owned main identity changed')
    check_main()
    role = contract['roles'][args.role]
    path = Path(role['checkpoint'])
    require(role['target'] == ROLES[args.role], 'Prepared role target differs')
    gate_record = dict(path=role['gate'], sha256=args.gate_sha256)
    gate = json.loads(read_pinned(gate_record, retained))
    validate_gate(gate, args.role, path)
    prior224 = None
    if args.role == '256M':
        require(Path(args.prior_224_lineage).absolute() == RUN/'fresh3-224M-checkpoint-lineage.json', 'Wrong final224M lineage path')
        prior224 = json.loads(read_pinned(dict(path=str(args.prior_224_lineage), sha256=args.prior_224_lineage_sha256), retained))
        require(prior224['schema'] == 'robotron-224M-checkpoint-lineage-v1' and prior224['PASS'] is True
            and prior224['proposal_only'] is False and prior224['root_verification']['status'] == 'PASS'
            and prior224['root_verification']['CUDA_initialized'] is False
            and prior224['checks'] and all(v is True for v in prior224['checks'].values()), 'Final224M lineage required')
        proof = prior224['root_verification']
        require(proof['precommit_sha256'] == PRECOMMIT_SHA and proof['verifier_sha256'] == verifier_sha
            and proof['model_body_reads'] == proof['model_CPU_loads'] == 1
            and Path(prior224['candidate']['path']) == Path(contract['roles']['224M']['checkpoint']), '224M CPU proof/identity differs')
        validate_gate(prior224['trigger_gate']['record'], '224M', prior224['candidate']['path'], prior224['candidate']['saved_metadata'])
    before = file_stat(path)
    require(0 < before['size'] <= 512*1024*1024 and before['nlink'] == 1, 'Bounded independent candidate required')
    payload = path.read_bytes()  # the ONLY candidate body read/hash/load input
    actual_sha = digest(payload)
    require((args.checkpoint_sha256 is None or actual_sha == args.checkpoint_sha256)
        and file_stat(path) == before, 'Actual candidate expected SHA/stat differs')
    import torch
    torch.set_num_threads(2); torch.set_num_interop_threads(1)
    require(not torch.cuda.is_initialized(), 'CUDA unexpectedly initialized')
    saved = torch.load(io.BytesIO(payload), map_location='cpu', weights_only=True)
    metadata, facts = validate_saved(saved, reference, anchors[-1]['saved_metadata'], args.role, gate, cpu, torch)
    steps = facts['optimizer_parameter_steps']
    since192 = exposure(reference['saved_metadata'], metadata, reference['optimizer']['step_values'], steps)
    since_run25 = exposure(anchors[-1]['saved_metadata'], metadata, anchors[-1]['optimizer_parameter_steps'], steps)
    since224 = exposure(prior224['candidate']['saved_metadata'], metadata, prior224['candidate']['optimizer']['step_values'], steps) if prior224 else None
    candidate = dict(path=str(path), sha256=actual_sha, stat=before, saved_metadata=metadata,
        state_dict_signatures=facts['geometry'], tensor_devices=['cpu'], checkpoint_tensor_count=443,
        all_network_optimizer_tensors_finite=True, grad_scaler_state_dict=facts['grad_scaler_state_dict'],
        optimizer=dict(state_count=81, step_values=steps, minimum_parameter_step=steps[0], maximum_parameter_step=steps[0],
            groups=facts['optimizer_groups'], all_tensors_CPU=True, tensor_count=243))
    report = dict(schema='robotron-' + args.role + '-checkpoint-lineage-v1', PASS=True, proposal_only=False,
        utc=datetime.now(timezone.utc).isoformat(), candidate=candidate, protected192M=contract['evidence']['reference192M'],
        trigger_gate=dict(**gate_record, record=gate), checks=dict(same_byte_SHA_and_single_CPU_load=True,
            finite443_ordered99_Adam81_scaler=True, source20_private12_current_owned_main=True,
            saved4096_chronology_and_target_phase=True, completed_history_bound_before_future_bytes=True),
        branch_provenance=dict(experiment=EXPERIMENT, compile_mode='default', exposure_counters_enabled=True,
            held_recipe=dict(batch_size=4096, n_step=3, max_samples_per_frame=8., lr_scale=.5, epsilon=.1, expert_ratio=.1),
            collector_resume_chronology=chronology, completed_collector_exposure=completed_exposure, run25_candidate_exposure=since_run25,
            runtime_metadata_path=contract['evidence']['runtime']['path'], runtime_metadata_sha256=contract['evidence']['runtime']['sha256'],
            recorded_runtime_recipe=runtime, control_path=contract['evidence']['controls']['path'], control_snapshot=documents['controls'],
            prior192M_history=reference_report['branch_provenance'], current_main_identity=current),
        actual_recorded_batch_exposure=dict(since192M=since192, since224M=since224),
        counter_exposure_evidence=dict(available=False, reason='No API counter reconciliation. Each process/load epoch is separate; imported6M ring/banks are not new admissions.'),
        root_verification=dict(status='PASS', started_utc=start, finished_utc=datetime.now(timezone.utc).isoformat(),
            elapsed_s=time.monotonic()-tick, method='One root CPU payload proof; independent source/metadata peer review is separate, not a second model load.',
            CUDA_VISIBLE_DEVICES='', CUDA_initialized=False, torch_threads=torch.get_num_threads(), torch_version=str(torch.__version__),
            model_body_reads=1, model_CPU_loads=1, precommit_sha256=PRECOMMIT_SHA,
            verifier_sha256=verifier_sha, main_process_identity=current,
            source20_hashes=observation['source_hashes'], private12_hashes=observation['private12_hashes']),
        evidence=[dict(path=p, sha256=v[0]) for p,v in retained.items()],
        limitations=['Saved logical attempts/sample clocks and per-parameter Adam clocks are distinct; their gap is not certified AMP-skip count.',
            'Run23 collector1 -> run24 collector0.5 -> run25 collector1 includes learning exposure; rejected performance trial is retained.',
            'Static source/current environment and process continuity do not prove every historical scalar read or reproduce RNG/actor trajectories.',
            'Concurrent private GPU0 evaluation is permitted; this helper does not inspect scores/private GPU state or change any process.',
            'The new1200s reference must be separately finalized; original600s192M scores are not a rebased reference.'])
    def final_check():
        recheck(retained); check_main()
        require(file_stat(path) == before and not torch.cuda.is_initialized(), 'Candidate changed/CUDA initialized before publication')
    result = publish(output.absolute(), report, final_check)
    return dict(PASS=True, path=str(output.absolute()), sha256=result, checkpoint_sha256=actual_sha,
                saved_metadata=metadata, optimizer_parameter_steps=steps)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--role', choices=tuple(ROLES))
    parser.add_argument('--checkpoint-sha256', help='Optional producer-attested expected SHA; do not preread the candidate to fill this')
    for flag in ('gate-sha256', 'precommit-sha256', 'output', 'prior-224-lineage', 'prior-224-lineage-sha256'):
        parser.add_argument('--' + flag)
    args = parser.parse_args()
    if not args.verify:
        parser.print_help(); return
    if args.role is None or args.output is None:
        parser.error('--verify needs explicit --role, --output and actual SHA pins')
    try:
        print(json.dumps(execute(args), allow_nan=False))
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, 'Future CPU lineage verification rejected: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
