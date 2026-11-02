"""Preserve one current normal autosave for forward-handoff preparation.

Inert unless --execute is supplied. No signals, saves, restores, source changes,
or service operations. The resulting CPU job does not authorize a handoff.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
B = G/'tools/startup_policy_journal_proposal'
Q = R/'quality32-protected1741-vs-normal2202-start-certified-original01-preparation-20261022'
OUT = Q/'future-dashboard-JSON-forward-insurance-original02-preparation'


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
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return 0
    h = load('_forward_insurance_helpers', B/'run_full_policy_startup_v3.py')
    require(h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'Helper changed')
    guard_path = R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py'
    require(h.pin(guard_path)['sha256'] == 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3', 'Guard changed')
    guard = h.load('_forward_insurance_guard', guard_path)
    main_pin = h.pin(Q/'01-reference/prospective-main-binding.json')
    require(main_pin['sha256'] == 'c4ff23f9304729656570175a0d9ef34c2798d011067f0cc9f5e22d059ad61ad6', 'Main binding changed')
    main_binding = json.loads(h.checked(main_pin).read_bytes())
    guard.owner_and_files(main_binding)
    require(not OUT.exists(), 'Original acquisition already consumed; preserve its outcome')
    OUT.mkdir(mode=0o700)

    def health(label):
        guard.owner_and_files(main_binding)
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
            raw = response.read()
        # Keep the actual response even if strict decoding or health fails.
        with (OUT/(label+'-API.raw.json')).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        def reject_constant(value):
            raise ValueError('Nonfinite producer JSON: '+value)
        api = json.loads(raw, parse_constant=reject_constant)
        api = api.get('now', api)
        baseline = json.loads(h.checked(main_binding['baseline_API']).read_bytes())
        guard.healthy(api, baseline.get('now', baseline), main_binding['experiment'], time.time())
        for key in ('loss', 'grad_norm', 'epsilon', 'lr'):
            require(type(api[key]) in (int, float) and __import__('math').isfinite(api[key]), 'Nonfinite current diagnostic: '+key)
        return h.put(OUT/(label+'-main192-health.json'), dict(API=api, main_binding=main_pin, observed_unix_s=time.time()))

    before = health('before-copy')
    template_path = R/'next-normal-autosave-candidate-original01-preparation-20261022/candidate-CPU-job.json'
    template_pin = h.pin(template_path)
    require(template_pin['sha256'] == '128c2bff023ac70d3ea9b03daebeb4908e9c207d66fcfc099cb241ecaeb17ced', 'Prior CPU template changed')
    template = json.loads(h.checked(template_pin).read_bytes())
    src = G/'models_dqn/robotron_dqn_latest.pt'
    source = h.pin(src)
    require(0 <= time.time()-source['identity']['mtime_ns']/1e9 <= 360, 'Normal autosave is stale or future')
    dest = OUT/'current-normal-autosave-readonly.pt'
    intent = h.put(OUT/'copy-precommit.json', dict(
        schema='robotron-forward-handoff-normal-insurance-copy-precommit-v1',
        source=source, destination=str(dest), main_binding=main_pin, main_health_before=before,
        source_builder=h.pin(__file__), CPU_template=template_pin, original_attempt=1,
        purpose='Pre-maintenance insurance and finite/phase proof only; not the final stopped resume state or a selected quality cohort.',
        main_runtime_changed=False, manual_save_requested=False, handoff_authorized_by_this_job=False,
        created_unix_s=time.time()))
    sha = hashlib.sha256()
    with src.open('rb') as incoming, dest.open('xb') as outgoing:
        require(h.identity(os.fstat(incoming.fileno())) == source['identity'], 'Source FD changed before copy')
        while block := incoming.read(4*1024*1024):
            sha.update(block)
            outgoing.write(block)
        outgoing.flush()
        os.fchmod(outgoing.fileno(), 0o444)
        os.fsync(outgoing.fileno())
        require(h.identity(os.fstat(incoming.fileno())) == source['identity'], 'Source FD changed during copy')
    require(h.pin(src) == source and sha.hexdigest() == source['sha256'], 'Source replaced or changed through copy; preserve original outcome')
    candidate = h.pin(dest)
    require(candidate['sha256'] == source['sha256'] and candidate['bytes'] == source['bytes']
            and (candidate['identity']['device'], candidate['identity']['inode']) != (source['identity']['device'], source['identity']['inode']), 'Independent byte-identical copy required')
    after = health('after-copy')
    acquisition = h.put(OUT/'copy-result.json', dict(
        schema='robotron-original-normal-autosave-candidate-copy-result-v1',
        precommit=intent, candidate=candidate, source=source,
        source_original_identity_unchanged_through_copy=True, independent_readonly_inode=True,
        main_health_before=before, main_health_after=after, main_owner=main_binding['owner'],
        manual_save_requested=False, main_runtime_changed=False,
        purpose='Forward preparation insurance only; current main continues beyond these saved clocks.',
        original_attempt=1, no_retry=True, created_unix_s=time.time()))
    job = dict(template)
    old_paths = {template[k]['path'] for k in ('candidate', 'acquisition')}
    old_acquisition = json.loads(h.checked(template['acquisition']).read_bytes())
    old_paths.update(old_acquisition[k]['path'] for k in ('main_health_before', 'main_health_after'))
    job.update(output=str(OUT/'CPU-verification-original01'), candidate=candidate, acquisition=acquisition)
    job['inputs'] = [entry for entry in template['inputs'] if entry['path'] not in old_paths]
    job['inputs'] += [candidate, acquisition, before, after, main_pin, template_pin, h.pin(__file__)]
    for entry in job['inputs']:
        h.checked(entry)
    jp = h.put(OUT/'insurance-CPU-job.json', job)
    ctl = h.load('_forward_insurance_controller', G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    require(h.pin(ctl.__file__)['sha256'] == '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', 'Controller changed')
    verifier = h.pin(B/'verify_normal_autosave_candidate_v1.py')
    require(verifier['sha256'] == '72599a4ca5ef314f93cab6a8084334338d9d0ba9f1c67d997392f324db745b21', 'Verifier changed')
    argv = [str(G.parent/'.venv-gb300/bin/python'), '-Xgil=0', '-I', '-B', verifier['path'],
            '--execute', '--job', jp['path'], '--job-sha256', jp['sha256'], '--source-sha256', verifier['sha256']]
    config = dict(unit='robotron-dashboard-json-forward-insurance-CPU-original01-20261022.service',
        output=str(OUT/'CPU-controller-execution-original01'), argv=argv,
        properties=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0', 'RuntimeMaxSec=180',
                    'TasksMax=256', 'TimeoutStopSec=5', 'SendSIGKILL=no'],
        pins=[ctl.pin(entry['path']) for entry in job['inputs']+[jp, verifier]], observation_s=240)
    cp = h.put(OUT/'CPU-controller-config.json', config)
    guard.owner_and_files(main_binding)
    print(json.dumps(dict(status='PREPARED_NO_CPU_LAUNCH_NO_HANDOFF', job=jp, config=cp, insurance=candidate)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
