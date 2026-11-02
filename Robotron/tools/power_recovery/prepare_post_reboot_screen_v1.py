"""Prepare one fresh post-reboot frozen-policy screen; never launch its GPU legs.

Reuse the qualified recorder, liveness policy, ownership and Main-health checks.
Only the controller unit namespace changes. Failed/interrupted studies remain
historical; this candidate is an independent copy of a later saved generation.
"""
import argparse
import ast
import copy
import difflib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
OLD = B / 'post-repair-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
CASE = B / 'post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
REC = B / 'reboot-recovery-20261031-original01'
CPU = B / 'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/state-sources/control_stopped_fullstate600_CPU_v1.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads(Path(path).read_text())


def helpers():
    path = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    return load('_reboot_screen_helpers', path)


def setup(h):
    CASE.mkdir(mode=0o700)
    source = CASE / 'selected-source'
    source.mkdir(mode=0o700)
    previous = read(OLD / 'prepared-matched-fixed-cutoff-two-arm-DATA-NOT-LAUNCHED-v1.json')
    old_controller = h.checked(previous['selected_sources']['controller'])
    before = old_controller.read_text()
    old_namespace = 'robotron-post-repair-LR625-S2-fixedcutoff-score-'
    new_namespace = 'robotron-post-reboot-LR625-S2-fixedcutoff-score-'
    assert before.count(old_namespace) == 1
    after = before.replace(old_namespace, new_namespace)
    assert ast.dump(ast.parse(after.replace(new_namespace, old_namespace))) == ast.dump(ast.parse(before))
    controller = source / 'control_post_reboot_screen_v1.py'
    with controller.open('x') as stream:
        stream.write(after)
        stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    h.put(source / 'controller-namespace-only-proof.json', dict(
        parent=previous['selected_sources']['controller'], selected=h.pin(controller),
        substitutions=1, normalized_AST_equal=True,
        patch=''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True))),
        resource_or_result_or_ownership_logic_changed=False))
    parent_copy = B / 'post-repair-LR625-applied60k-replay20M-learner16M-original01-20261031/future-post-dose-policy-capture-source-only-original01/copy_named_post_repair_LR625_policy_v1.py'
    copier = load('_reboot_published_policy_copy', parent_copy)
    # Use the identical opened-FD/atomic-publisher copy algorithm on latest.
    copier.LATEST = G / 'models_dqn/robotron_dqn_latest.pt'
    sys.argv = [str(parent_copy), '--output', str(CASE / 'policy-copy-original01')]
    copier.main()
    cp = h.pin(CASE / 'policy-copy-original01/frozen-policy.pt')
    assert cp['sha256'] not in ('50025873cc1b95f6148b12b6760c4b0521af68fb9030f3d3157619488da3850d',
                               'f3051225e2abecba844981c2a5280f1c4b15c5bdf9567ca68eb84ed2278117fe')
    h.put(CASE / 'fresh-candidate-copy-selection.json', dict(checkpoint=cp,
        copier=h.pin(parent_copy), selected_source_path=str(copier.LATEST),
        source_path_override_only=True, training_control_changed=False,
        exposure_gap=REC.as_posix(), quality_qualified=False))
    cpu_dir = CASE / 'policy-CPU-original01'
    cpu_dir.mkdir(mode=0o700)
    verifier = parent_copy.with_name('verify_snapshot_raw_Adam_steps_post_repair_LR625_v1.py')
    ctl = load('_reboot_CPU_controller', CPU)
    config = dict(unit='robotron-post-reboot-policy-CPU-original01-20261031.service',
        output=str(cpu_dir / 'execution-original01'), argv=[
            str(G.parent / '.venv-gb300/bin/python'), '-Xgil=0', '-I', '-B', str(verifier),
            '--checkpoint', cp['path'], '--report', str(cpu_dir / 'report.json')],
        properties=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0',
            'RuntimeMaxSec=600', 'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'],
        pins=[ctl.pin(verifier), ctl.pin(cp['path'])], observation_s=660)
    h.put(cpu_dir / 'controller-config.json', config)
    # Record the interruption without inventing an exit or a score result.
    h.put(CASE / 'preboot-interrupted-screen-disposition.json', dict(
        previous_case=str(OLD), previous_owner=read(OLD / 'Root-controller-runtime-original01/owner.json'),
        previous_status=h.pin(OLD / 'R1/runtime-original01/status.json'),
        old_boot_changed=True, current_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        outer_result_present=(OLD / 'Root-controller-runtime-original01/result.json').exists(),
        native_result_present=(OLD / 'R1/runtime-original01/result.json').exists(),
        original_exit=None, classification='INTERRUPTED_BY_REBOOT_NO_FINAL_RECEIPT',
        prior_scores_adopted=False, previous_science_retried=False, promotion=False))


def cpu(h):
    directory = CASE / 'policy-CPU-original01'
    seq = load('_reboot_CPU_sequence', G / 'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py')
    ctl = load('_reboot_CPU_control', CPU)
    cfg = h.pin(directory / 'controller-config.json')
    result = seq.invoke_controller_once(directory, '', h.pin(CPU), cfg, h)
    rt = load('_reboot_CPU_review', G / 'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    reader = load('_reboot_CPU_reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    closed = seq.verify_closed_scope(directory, '', cfg, h,
        lambda pin, as_json=True: reader.read_pin(pin, as_json=as_json), rt, ctl)
    report = read(directory / 'report.json')
    assert report['checkpoint']['sha256'] == read(CASE / 'fresh-candidate-copy-selection.json')['checkpoint']['sha256']
    assert report['clocks']['training_steps'] > 19275850
    assert report['CUDA_initialized'] is False and report['optimizer_lrs'] == [6.25e-6]
    h.put(directory / 'positive-owned-closeout.json', dict(status='PASS', result=result,
        closure=closed['closure'], report=h.pin(directory / 'report.json'),
        all_original_resources_closed=True, promotion=False))


def assemble(h):
    import urllib.request
    old = read(OLD / 'prepared-matched-fixed-cutoff-two-arm-DATA-NOT-LAUNCHED-v1.json')
    selected_old = read(h.checked(old['selection']))
    report = read(CASE / 'policy-CPU-original01/report.json')
    assert read(CASE / 'policy-CPU-original01/positive-owned-closeout.json')['status'] == 'PASS'
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=8) as response:
        api = json.load(response)
    pipe = api['host_pipeline']['learning_exposure']
    authority = h.pin(REC / 'actual-recovered-trainer-startup-authority.json')
    auth = read(authority['path']); owner = auth['trainer']
    main = dict(API='http://127.0.0.1:8771/api/now',
        owner=dict(pid=owner['pid'], starttime_ticks=owner['birth'], unit=owner['unit'],
            invocation_id=owner['invocation_id'], cgroup=owner['cgroup']),
        environment=selected_old['current_main']['environment'],
        exposure={kind:{key:pipe[kind][key] for key in ('process_id','instance_monotonic_ns','epoch','epoch_reason')}
            for kind in ('optimizer','replay')}, startup_authority=authority, startup_held=auth['new_held_report'])
    assert main['owner']['pid'] == 599082
    current_api = h.put(CASE / 'current-Main-API-snapshot.json', api)
    candidate = dict(display_name='Post-reboot LR625',
        checkpoint=h.pin(CASE / 'policy-copy-original01/frozen-policy.pt'),
        authority=h.pin(CASE / 'policy-CPU-original01/report.json'), expected_policy_clocks=report['clocks'])
    # Small, explicit selection; no inherited stale dose/counter or Main claims.
    selected = {key:copy.deepcopy(selected_old[key]) for key in (
        'schema','status','ordered_legs','screen_only','promotion','reference',
        'private_score_stall_timeout_s','private_lua_score_stall_timeout_s','private_protocol_sources')}
    selected.update(candidate=candidate, current_main=main, current_Main_snapshot=current_api,
        selected_unix_s=time.time(), old_scores_or_jobs_reused=False,
        current_recovery_index=h.pin(REC / 'current-recovery-verified-learning-resumed-index-original101.json'),
        interpretation='Fresh frozen-policy exploration after reboot; newer replay lost, older replay restored. No causal LR or recovery improvement claim.')
    selection = h.put(CASE / 'selection.json', selected)
    sources = copy.deepcopy(old['selected_sources'])
    sources['controller'] = h.pin(CASE / 'selected-source/control_post_reboot_screen_v1.py')
    source_map = h.put(CASE / 'selected-source-map.json', sources)
    lease = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
    if not lease.exists():
        fd = os.open(lease, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.fsync(fd); os.close(fd)
    assert lease.stat().st_uid == os.getuid() and lease.stat().st_size == 0
    prepared = dict(ordered_legs=['R1','C1'], selection=selection,
        selected_sources=sources, screen_only=True, promotion=False, jobs={})
    configs = dict(ordered_legs=['R1','C1'], configs={})
    original_tokens = set()
    for leg in ('R1','C1'):
        job = read(OLD / leg / 'job.json')
        original_tokens.update(job['sessions'].values()); original_tokens.update(job['connections'].values())
    new_tokens = set()
    for leg in ('R1','C1'):
        folder = CASE / leg; folder.mkdir(mode=0o700)
        job = read(OLD / leg / 'job.json')
        policy = selected['reference' if leg == 'R1' else 'candidate']
        job.update(checkpoint=policy['checkpoint'], expected_policy_clocks=policy['expected_policy_clocks'],
            policy_authority=policy['authority'], current_main=main, screen_selection=selection,
            output=str(folder / 'runtime-original01'), lease=h.pin(lease),
            label='post-reboot-LR625-vs-S2-'+leg+'-original01-20261031',
            measurement_label='post-reboot-LR625-vs-S2-'+leg+'-original01-20261031',
            sessions={str(slot):uuid.uuid4().hex for slot in job['actor_slots']},
            connections={str(slot):uuid.uuid4().hex for slot in job['actor_slots']})
        new_tokens.update(job['sessions'].values()); new_tokens.update(job['connections'].values())
        pins=[selection, source_map, h.pin(Path(__file__)), authority, auth['new_held_report'],
            current_api, policy['authority'], h.pin(CASE / 'policy-CPU-original01/positive-owned-closeout.json'),
            h.pin(CASE / 'fresh-candidate-copy-selection.json')]
        pins.extend(job[key] for key in ('runtime','lua','completion_codec','screen_support','seed_runtime','source_package'))
        pins.extend(job['components'].values()); pins.extend(job['boot_seed']['inputs'])
        pins.append(job['boot_seed']['module'])
        # Bind the same already-qualified private watchdog source and CPU evidence.
        pins.extend(value for key,value in selected_old.items() if key.startswith('matched_private_liveness_'))
        job['inputs']=list({value['path']:value for value in pins}.values())
        jp=h.put(folder / 'job.json', job)
        cfg=read(OLD / leg / 'Root-original-C218-config.json')
        cfg.update(unit='robotron-post-reboot-LR625-S2-fixedcutoff-score-'+leg.lower()+'-original01-20261031.service',
            output=str(folder / 'controller-execution-original01'))
        cfg['argv'][7]=jp['path']; cfg['argv'][9]=jp['sha256']
        controller=load('_reboot_scientific_controller_'+leg, sources['controller']['path'])
        cfg['pins']=[controller.pin(jp['path']), controller.pin(job['runtime']['path'])]
        config=h.put(folder / 'controller-config.json',cfg)
        configs['configs'][leg]=config
        prepared['jobs'][leg]=dict(job=jp, argv=cfg['argv'])
    assert len(new_tokens)==128 and not new_tokens & original_tokens
    prepared['controller_configs']=h.put(CASE / 'controller-configs.json', configs)
    h.put(CASE / 'prepared.json', prepared)


def preflight(h):
    prepared=read(CASE / 'prepared.json')
    configs=read(h.checked(prepared['controller_configs']))
    sources=prepared['selected_sources']
    native=load('_reboot_native_preflight',h.checked(sources['native']))
    controller=load('_reboot_controller_preflight',h.checked(sources['controller']))
    selected=read(h.checked(prepared['selection']))
    assert selected['candidate']['checkpoint']['sha256'] != selected['reference']['checkpoint']['sha256']
    rows=[]
    for leg in ('R1','C1'):
        job=read(h.checked(prepared['jobs'][leg]['job']))
        for pin in job['inputs']:h.checked(pin)
        h.checked(job['checkpoint'])
        native.validate_job(job);context=native.validate_completed_context(job,h)
        cfg=controller.checked_config(h.checked(configs['configs'][leg]))
        assert not Path(cfg['output']).exists()
        for suffix in ('.service','.timer'):
            assert controller.show(cfg['unit'].removesuffix('.service')+suffix)['LoadState']=='not-found'
        guard=context['support'].CurrentMainHealth(job,CASE / ('preflight-'+leg),h)
        guard.output.parent.mkdir(mode=0o700);guard.start();sample=guard.observe()
        guard.finish(None)
        rows.append(dict(leg=leg,Main=sample,components=len(context['modules']),package_pins=len(context['package_pins'])))
    job=read(prepared['jobs']['R1']['job']['path'])
    sockets=[]
    try:
        for port in [job['origin_port'],*job['proxy_ports'].values()]:
            sock=socket.socket();sockets.append(sock);sock.bind(('127.0.0.1',port))
    finally:
        for sock in sockets:sock.close()
    with open(job['lease']['path'],'r+b') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert h.pin(job['lease']['path'])==job['lease']
        fcntl.flock(stream,fcntl.LOCK_UN)
    gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=15)
    assert gpu.returncode==0 and job['gpu_uuid'] not in gpu.stdout
    h.put(CASE / 'positive-preflight.json',dict(status='PASS',rows=rows,
        all33ports_bindable=True,lease_free=True,gpu_query=gpu.stdout,
        torch_imported='torch' in sys.modules,private_runtime_launched=False,
        observed_unix_s=time.time(),promotion=False))
    assert 'torch' not in sys.modules
    print(json.dumps(dict(preflight='PASS',candidate_sha256=selected['candidate']['checkpoint']['sha256'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--stage',choices=['setup','cpu','assemble','preflight'])
    args=parser.parse_args()
    if args.execute:
        assert args.stage
        globals()[args.stage](helpers())
    else:
        parser.print_help()
