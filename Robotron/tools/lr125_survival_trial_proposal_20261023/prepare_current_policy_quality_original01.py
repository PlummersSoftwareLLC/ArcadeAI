"""Bind the saved independent candidate to a fresh four-leg study; no launch."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
B = G / 'tools/startup_policy_journal_proposal'
N = R / 'quality32-protected1741-vs-currentLR125-firstSave-original01-preparation-20261023'
O = R / 'quality32-protected1741-vs-normal2259-after-JSON-original01-preparation-20261022'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    h = load('_current_prep_helpers', B / 'run_full_policy_startup_v3.py')
    assert h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    reader = load('_current_prep_reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    assert h.pin(reader.__file__)['sha256'] == 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
    read = lambda entry, as_json=True: reader.read_pin(entry, as_json=as_json)
    rt = load('_current_prep_archives', G / 'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    ctl = load('_current_prep_CPU', G / 'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    assert h.pin(rt.__file__)['sha256'] == '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'
    assert h.pin(ctl.__file__)['sha256'] == '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
    proofdir = N / 'fresh-study-launch-preparation-original01'
    proofdir.mkdir(mode=0o700)
    guarddir = N / 'quality-source-guards-execution-original01'
    guard_cfg_pin = h.pin(N / 'quality-source-guards-controller-config-original01.json')
    cfg = ctl.checked_config(guard_cfg_pin['path'])
    owner_pin = h.pin(guarddir / 'root-original-identity.json')
    owner = read(owner_pin)
    closure_pin = h.pin(guarddir / 'root-original-result-and-owned-release.json')
    closure = read(closure_pin)
    fields = rt.archived_closure(closure, owner, read, exit_zero=True)
    assert fields['Id'] == cfg['unit'] and fields['NRestarts'] == '0'
    assert ' '.join(cfg['argv']) + ' ; ignore_errors=no ;' in fields['ExecStart']
    assert rt.duration_seconds(fields['CPUQuotaPerSecUSec']) == 2
    assert fields['MemoryMax'] == str(4 << 30) and fields['MemorySwapMax'] == '0'
    assert rt.duration_seconds(fields['RuntimeMaxUSec']) == 180 and fields['TasksMax'] == '128'
    assert rt.duration_seconds(fields['TimeoutStopUSec']) == 5 and fields['SendSIGKILL'] == 'no' and fields['Restart'] == 'no'
    base = load('_current_prep_sequence_helpers', B / 'sequence_quality32_2259_prospective197_v1.py')
    assert base.birth(owner['pid']) != owner['starttime_ticks']
    for unit in (owner['unit'], owner['timer']):
        assert ctl.show(unit)['LoadState'] == 'not-found'
        assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', unit).exists()
    for entry in cfg['pins']:
        assert ctl.pin(entry['path']) == entry
    stderr = (guarddir / 'stderr.txt').read_text()
    assert 'Ran 8 tests' in stderr and stderr.rstrip().endswith('OK')
    guards = h.put(proofdir / 'independent-eight-source-guards-readback.json', dict(
        config=guard_cfg_pin, owner=owner_pin, closure=closure_pin, fields=fields,
        original_stderr=h.pin(guarddir / 'stderr.txt'), all_six_descriptors_verified=True,
        exact_actual_argv_and_resources_verified=True, owned_scope_absent=True,
        tests=8, original_exit=0, scientific_job_retried=False, created_unix_s=time.time()))

    old_binding_pin = h.pin(N / 'postcapture-owned-slot-current-main-registration-original01/current-main-binding.json')
    assert old_binding_pin['sha256'] == 'b500d5dc4eb1a1c727fd671db3758fcbf14cb86fd10b9c99fe8cb9ab427387c8'
    main_binding = read(old_binding_pin)
    old_policy = read(main_binding['supervision_policy'])
    sup = load('_current_prep_sup', G / 'tools/quality_capacity_proposal/supervised_main_fleet_v2.py')
    assert h.pin(sup.__file__)['sha256'] == '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'
    census = sup.collect(old_policy)
    assert set(census['actors']) == sup.SLOTS
    for role in ('trainer', 'fleet'):
        sup.validate_owner(old_policy[role], census['owners'][role])
        assert all(census['owners'][role]['process'][key] == old_policy['baseline_owners'][role]['process'][key] for key in sup.STATIC)
    changes = []
    for slot, current in census['actors'].items():
        previous = old_policy['baseline_actors'][slot]
        sup.validate_actor(slot, current, previous, old_policy['fleet'])
        if sup.birth(current) != sup.birth(previous):
            assert census['previous_birth_probes'][slot] != previous['starttime_ticks']
            assert current['starttime_ticks'] > previous['starttime_ticks']
            changes.append(dict(slot=slot, previous=sup.birth(previous), current=sup.birth(current)))
    main_binding['actors'] = [dict(slot=int(slot), pid=a['pid'], starttime_ticks=a['starttime_ticks'], mask=a['affinity'])
                             for slot, a in sorted(census['actors'].items(), key=lambda item: int(item[0]))]
    window = load('_current_prep_window', G / 'tools/lr125_survival_trial_proposal_20261023/window_observer.py')
    assert h.pin(window.__file__)['sha256'] == 'ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a'
    window.owner_and_files(main_binding)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        raw = response.read(1048577)
    assert len(raw) <= 1048576
    api = json.loads(raw)
    window.healthy(api, read(main_binding['baseline_API']), main_binding['experiment'], time.time())
    age = time.time() - (G / 'models_dqn/robotron_dqn_latest.pt').stat().st_mtime
    assert 0 <= age <= 360
    with (proofdir / 'current-main-API.raw.json').open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    policy_creator = load('_current_prep_policy', G / 'tools/quality_capacity_proposal/supervised_main_fleet197_v1.py')
    assert h.pin(policy_creator.__file__)['sha256'] == '7e386b07b55268a0c13ba2d71b2ece7b8d73f8de7b38aacd17f836d091c37838'
    policy, snapshot = policy_creator.make_policy(main_binding, old_policy['fleet'])
    state = sup.validate_snapshot(policy, snapshot, api['client_count'])
    assert state['full_capacity'] and not state['pending'] and not state['completed_episodes']
    policy_pin = h.put(proofdir / 'current-main-supervision-policy.json', policy)
    main_binding.update(supervision_policy=policy_pin, baseline_API=h.pin(proofdir / 'current-main-API.raw.json'),
                        prior_binding=old_binding_pin, new_leg_binding_only_prior_original_studies_unchanged=True,
                        current_binding_reason='Verified between-study supervisor replacement at slot86; no original study rebound')
    binding_pin = h.put(proofdir / 'current-main-binding.json', main_binding)
    transition = h.put(proofdir / 'current-main-transition-readback.json', dict(
        previous_binding=old_binding_pin, current_binding=binding_pin, original_census=snapshot,
        verified_between_study_transitions=changes, all197_held_hashes_unchanged=True,
        all192_current_actors_verified=True, main_runtime_changed=False,
        original_closed_studies_rebound=False, api=h.pin(proofdir / 'current-main-API.raw.json'),
        autosave_age_s=age, created_unix_s=time.time()))
    monitor_source = (N / 'postcapture-owned-slot-current-main-registration-original01/root-current-main-readonly-monitor.py').read_text()
    tree = ast.parse(monitor_source)
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PINS' for t in node.targets))
    pins = ast.literal_eval(assignment.value); pins['binding'] = binding_pin
    lines = monitor_source.splitlines(keepends=True)
    lines[assignment.lineno-1:assignment.end_lineno] = ['PINS = ' + repr(pins) + '\n']
    monitor_source = ''.join(lines).replace('historical_original_actor_survivors=191,verified_between_study_replacements=1',
                                            'historical_original_actor_survivors=190,verified_between_study_replacements=2')
    monitor_path = proofdir / 'root-current-main-readonly-monitor.py'
    with monitor_path.open('x') as stream:
        stream.write(monitor_source); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())

    pair_pin = h.pin(N / 'campaign-inputs-and-gates-precommit.json')
    assert pair_pin['sha256'] == '47d3da0f048973a9ce85494585cfcddc034afe705aa37143e6e87ad07fbc07cb'
    pair = read(pair_pin)
    family = dict(native_runtime='run_compiled_full_tail32_quality_current_lr125_v1.py',
                  native_controller='control_compiled_full_tail32_quality_current_lr125_v1.py',
                  leg_reviewer='read_compiled_quality32_current_lr125_original_v1.py',
                  leg_preparer='prepare_quality32_current_lr125_leg_v1.py',
                  campaign_assessor='assess_quality32_current_lr125_campaign_v1.py')
    ready = json.loads((O / 'new-original-quality-launch-readiness-prospective197-original01.json').read_bytes())
    old_ready_pin = h.pin(O / 'new-original-quality-launch-readiness-prospective197-original01.json')
    ready.pop('prospective_unexecuted_review_amendment')
    ready['historical_engineering_source_readiness'] = old_ready_pin
    ready['historical_original17_and4_CPU_guards'] = ready.pop('original_17_and_separate4_CPU_guards')
    ready.update({key: h.pin(B / filename) for key, filename in family.items()})
    ready.update(campaign_directory=str(N), quality_pair=pair_pin, created_unix_s=time.time(),
                 actual_current_policy_source_guards=guards, current_main_binding=binding_pin,
                 current_main_transition=transition, independent_selection=h.pin(N / 'independent-current-policy-selection-precommit.json'),
                 numerical_CPU_report=pair['candidate']['CPU_report'],
                 numerical_CPU_readback=h.pin(N / 'candidate-CPU-independent-closed-readback-original01/readback.json'),
                 cap_health_prototype_applied=False,
                 per_leg_main_binding='Fresh current192/197 binding; strict existing runtime health and complete-game gates unchanged')
    template = json.loads((O / 'native-current197-job-template.json').read_bytes())
    template.pop('prospective_independent_review_sources', None)
    template.update(main_binding=binding_pin, runtime=ready['native_runtime'],
                    output=None, label=None, sessions=None, connections=None,
                    created_unix_s=time.time(), admission_s=5400, whole_cohort_timeout_s=9000,
                    quality_pair_precommit=pair_pin, original_attempt=1, no_retry=True)
    template['main_sources']['window'] = h.pin(window.__file__)
    template['main_sources']['supervision'] = h.pin(sup.__file__)
    template['main_sources']['reader'] = h.pin(reader.__file__)
    extras = [*ready.values(), pair['candidate']['policy'], pair['reference']['policy'],
              h.pin(N / 'actual-current-policy-quality-source-bindings-original01.json'),
              h.pin(N / 'independent-current-policy-capture-readback.json'),
              h.pin(B / 'sequence_fresh_quality32_lr125_v1.py'), h.pin(base.__file__), h.pin(h.__file__)]
    extras = [entry for entry in extras if isinstance(entry, dict) and 'path' in entry and 'sha256' in entry]
    def unique(entries):
        result = {}
        for entry in entries:
            h.checked(entry)
            if entry['path'] in result:
                assert result[entry['path']] == entry
            result[entry['path']] = entry
        return list(result.values())
    template['inputs'] = unique(template['inputs'] + extras + list(template['main_sources'].values()))
    template_pin = h.put(N / 'native-current197-job-template.json', template)
    ready['native_job_template'] = template_pin
    ready['inputs'] = unique(ready['inputs'] + extras + [template_pin])
    ready_pin = h.put(N / 'new-original-quality-launch-readiness.json', ready)
    job = dict(schema='robotron-original-certified-quality32-campaign-assessment-job-v1',
               campaign_directory=str(N), output=str(N / 'independent-campaign-assessment-original01'),
               pair=pair_pin, launch_readiness_precommit=ready_pin,
               legs=[dict(role=role, directory=str(N / folder)) for role, folder in zip(base.ORDER, base.FOLDERS)],
               sources={key: ready[key] for key in ('leg_reviewer', 'native_runtime', 'native_controller', 'CPU_controller', 'native_closure')},
               original_attempt=1, no_retry=True)
    job_pin = h.put(N / 'campaign-assessment-job-original01.json', job)
    assessment_cfg = dict(unit='robotron-current-LR125-firstSave-campaign-assessment-original01-20261023.service',
        output=str(N / 'campaign-assessment-execution-original01'),
        argv=['/usr/bin/python3.12', '-I', '-B', ready['campaign_assessor']['path'], '--execute', '--job', job_pin['path'],
              '--job-sha256', job_pin['sha256'], '--source-sha256', ready['campaign_assessor']['sha256']],
        properties=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0', 'RuntimeMaxSec=180',
                    'TasksMax=256', 'TimeoutStopSec=5', 'SendSIGKILL=no'],
        pins=[ctl.pin(entry['path']) for entry in unique(ready['inputs'] + [ready_pin, job_pin])], observation_s=240)
    assessment_cfg_pin = h.put(N / 'campaign-assessment-controller-config-original01.json', assessment_cfg)
    ctl.checked_config(assessment_cfg_pin['path'])
    cpu = read(ready['numerical_CPU_readback'])
    sequence_pin = h.pin(B / 'sequence_fresh_quality32_lr125_v1.py')
    precommit = dict(schema='robotron-fresh-LR125-quality32-sequence-precommit-v1', source=sequence_pin,
        launch_readiness=ready_pin, campaign_assessment_config=assessment_cfg_pin,
        endpoint_CPU_report=cpu['report'], endpoint_CPU_scope=dict(config=cpu['config'], owner=cpu['original_owner'], closure=cpu['closure']),
        all_four_original_legs_fresh=True, original_attempts_per_leg=1, no_retries=True, created_unix_s=time.time())
    precommit_pin = h.put(N / 'original-fresh-sequence-precommit.json', precommit)
    fresh = load('_current_prep_fresh', sequence_pin['path'])
    fresh.sequence_type(base)(precommit_pin, h, reader).validate_endpoint_CPU()
    display_original = B / 'watch_quality32_2259_display_v1.py'
    display_source = display_original.read_text()
    assert display_source.count('2259.6M candidate') == 1
    display_source = display_source.replace('2259.6M candidate', '2561.1M current LR125 candidate')
    display_path = B / 'watch_quality32_current_lr125_display_v1.py'
    with display_path.open('x') as stream:
        stream.write(display_source); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    (N / 'display').mkdir(mode=0o700)
    display = load('_current_prep_display', display_path)
    legs = [display.project(N, i) for i in range(4)]
    display.publish(N / 'status.json', dict(state='prepared', current_leg=None, total_legs=4, legs=legs,
                                          updated_unix_s=time.time(), outcome=None, reason='Fresh sequence prepared; native launch pending'))
    proof = h.put(proofdir / 'readback.json', dict(status='FRESH_FOUR_LEG_READY_NOT_LAUNCHED',
        binding=binding_pin, monitor=h.pin(monitor_path), actor_transition=transition, source_guards=guards,
        launch_readiness=ready_pin, sequence_precommit=precommit_pin, sequence_source=sequence_pin,
        display_source=h.pin(display_path), actual_candidate=pair['candidate']['policy'],
        saved_candidate_clocks=pair['candidate'].get('saved_clocks', pair['candidate'].get('clocks')),
        prior_invalid32M_window_requalified=False, quality_qualified=False, promotion=False,
        main_runtime_changed=False, created_unix_s=time.time()))
    print(json.dumps(dict(prepared=proof, readiness=ready_pin['sha256'], precommit=precommit_pin['sha256'],
                          sequence_sha256=sequence_pin['sha256'], transitions=changes)))


if __name__ == '__main__':
    main()
