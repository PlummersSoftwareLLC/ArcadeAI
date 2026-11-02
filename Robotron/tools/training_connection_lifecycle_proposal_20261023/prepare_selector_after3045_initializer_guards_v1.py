"""CPU-only fixture preparation; does not schedule native/review/sequence jobs."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
OLD = R / 'quality32-protected1741-vs-currentLR125-quota64Protocol-firstSave-original01-preparation-20261024'
NEW = R / 'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025'
CAP = R / 'LR125-after-protected3045-firstSave-original01-preparation-20261025'
A = NEW / 'actual-initializer-source-guards-CPU-original01'


def load(path, name, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    h = load(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', '_guardprep_h',
             '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    c = load(G / 'tools/quality_capacity_proposal/control_quality32_review_v1.py', '_guardprep_c',
             '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14')
    familypin = h.pin(NEW / 'prepared-source-family-manifest.json')
    assert familypin['sha256'] == 'a0f01eb0798a7b560556314b7ab861bb0a0f27946156a1b54f709dc79130bbe6'
    family = json.loads(h.checked(familypin).read_bytes())
    assert family['readiness_for_scientific_launch'] is False
    prior_family = json.loads(h.checked(family['original_source_family']).read_bytes())
    oldready = json.loads((OLD / 'new-original-quality-launch-readiness.json').read_bytes())
    oldpre = json.loads((OLD / 'original-fresh-sequence-precommit.json').read_bytes())
    oldjob = json.loads((OLD / 'selected-family-source-guards-CPU-original01/job.json').read_bytes())
    current = json.loads((G / 'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    A.mkdir(mode=0o700)
    case_root = A / 'never-launched-structural-campaign'
    case_root.mkdir(mode=0o700)
    mapping = {prior_family['quality_pair']['path']: family['quality_pair'],
               oldready['source_family_manifest']['path']: familypin,
               oldready['current_main_binding']['path']: current['current_main_binding']}
    for key in ('runtime', 'native_controller', 'leg_reviewer', 'campaign_assessor', 'leg_preparer', 'sequence', 'display_source'):
        mapping[prior_family[key]['path']] = family[key]
    for key in ('view', 'drain', 'bridge'):
        mapping[prior_family['quota64_source_pins'][key]['path']] = family['quota64_source_pins'][key]
    for key in ('games_auditor', 'wire_auditor'):
        mapping[oldready[key]['path']] = family[key]

    def remap(value):
        if isinstance(value, dict):
            if {'path', 'sha256', 'bytes'} <= value.keys() and value['path'] in mapping:
                return copy.deepcopy(mapping[value['path']])
            return {k: remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v) for v in value]
        return value

    template = remap(json.loads(h.checked(oldready['native_job_template']).read_bytes()))
    template.update(main_binding=current['current_main_binding'], runtime=family['runtime'],
        quality_pair_precommit=family['quality_pair'], quota64_source_pins=family['quota64_source_pins'],
        output=str(case_root / 'NEVER_LAUNCH_NATIVE_TEMPLATE'),
        fixture_only_do_not_launch=True)
    templatepin = h.put(A / 'fixture-native-job-template.json', template)
    mapping[oldready['native_job_template']['path']] = templatepin
    ready = remap(oldready)
    ready.update(campaign_directory=str(case_root), native_job_template=templatepin,
        current_main_binding=current['current_main_binding'], source_family_manifest=familypin,
        numerical_CPU_report=current['current_later_candidate_preparation']['numerical_report'],
        numerical_CPU_readback=current['current_later_candidate_preparation']['numerical_closeout'],
        independent_selection=h.pin(CAP / 'fresh-later-policy-selection-precommit.json'),
        current_main_transition=h.pin(CAP / 'independent-original-capture-and-current-main-closeout.json'),
        case_slug='after3045-selector-reuse-fixture-only', case_date='20261025',
        fixture_only_do_not_launch=True, scientific_launch_authorized_by_this_artifact=False)
    additions = [familypin, family['quality_pair'], templatepin, current['current_main_binding'],
                 *[family[k] for k in ('runtime', 'native_controller', 'leg_reviewer', 'campaign_assessor', 'leg_preparer', 'sequence', 'display_source', 'games_auditor', 'wire_auditor')],
                 *family['quota64_source_pins'].values(), *family['source_templates'].values(), family['renderer'],
                 ready['numerical_CPU_report'], ready['numerical_CPU_readback'], ready['independent_selection'],
                 ready['current_main_transition'], family['actual_writer_alias_guards']]
    ready['inputs'] = list({pin['path']: pin for pin in [*ready['inputs'], *additions]}.values())
    for pin in ready['inputs']:
        h.checked(pin)
    readypin = h.put(A / 'fixture-only-source-context.json', ready)
    mapping[oldpre['launch_readiness']['path']] = readypin
    assessment = remap(json.loads((OLD / 'campaign-assessment-job-original01.json').read_bytes()))
    assessment.update(campaign_directory=str(case_root), output=str(case_root / 'NEVER_LAUNCH_ASSESSMENT'),
        legs=[dict(role=role, directory=str(case_root / folder)) for role, folder in
              zip(('R1', 'C1', 'R2', 'C2'), ready['original_directories'])], fixture_only_do_not_launch=True)
    assessmentpin = h.put(A / 'fixture-only-assessment-job.json', assessment)
    cfg = remap(json.loads(h.checked(oldpre['campaign_assessment_config']).read_bytes()))
    cfg['unit'] = 'robotron-quality32-owned-health-after3045-selector-fixture-final-original01-20261025.service'
    cfg['output'] = str(case_root / 'NEVER_LAUNCH_ASSESSMENT_CONTROLLER')
    cfg['argv'][3] = family['campaign_assessor']['path']
    cfg['argv'][cfg['argv'].index('--job') + 1] = assessmentpin['path']
    cfg['argv'][cfg['argv'].index('--job-sha256') + 1] = assessmentpin['sha256']
    cfg['argv'][cfg['argv'].index('--source-sha256') + 1] = family['campaign_assessor']['sha256']
    cfg['pins'] = [c.pin(pin['path']) for pin in [*ready['inputs'], readypin, assessmentpin]]
    cfgpin = h.put(A / 'fixture-only-assessment-controller-config.json', cfg)
    pre = remap(oldpre)
    pre.update(source=family['sequence'], launch_readiness=readypin,
        campaign_assessment_config=cfgpin,
        endpoint_CPU_report=ready['numerical_CPU_report'],
        endpoint_CPU_scope=dict(config=h.pin(CAP / 'candidate-CPU-preparation-original01/candidate-CPU-controller-config.json'),
            owner=h.pin(CAP / 'candidate-CPU-execution-original01/root-original-identity.json'),
            closure=h.pin(CAP / 'candidate-CPU-execution-original01/root-original-result-and-owned-release.json')),
        fixture_only_do_not_launch=True, created_unix_s=time.time())
    prepin = h.put(A / 'fixture-only-sequence-precommit.json', pre)
    original_validator = h.checked(oldjob['runtime']).read_text()
    # Same ten methods and original initializer sentinel. Clock tests now use
    # the newly protected reference floor instead of the older failed policy.
    assert original_validator.count('renderer.FAILED_CLOCKS') == 3
    validator = original_validator.replace('renderer.FAILED_CLOCKS', 'renderer.REF_CLOCKS')
    validator_path = A / 'validate_after3045_selector_family_v1.py'
    compile(validator, str(validator_path), 'exec')
    with validator_path.open('xb') as stream:
        stream.write(validator.encode()); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    validatorpin = h.pin(validator_path)
    job = copy.deepcopy(oldjob)
    job.update(readiness=readypin, sequence_precommit=prepin, runtime=validatorpin,
               output=str(A / 'output-original01'))
    jobpin = h.put(A / 'job.json', job)
    controller = dict(unit='robotron-selector-after3045-initializer-source-guards-original01-20261025.service',
        output=str(A / 'execution-original01'),
        argv=['/usr/bin/python3.12', '-I', '-B', validatorpin['path'], '--execute', '--job', jobpin['path'],
              '--job-sha256', jobpin['sha256'], '--source-sha256', validatorpin['sha256']],
        properties=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0', 'RuntimeMaxSec=180',
                    'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'],
        pins=[c.pin(pin['path']) for pin in [validatorpin, jobpin, readypin, prepin, *ready['inputs']]], observation_s=240)
    configpin = h.put(A / 'controller-config.json', controller)
    h.put(A / 'fixture-derivation-and-original-CPU-precommit.json', dict(
        schema='robotron-after3045-actual-initializer-guard-precommit-v1',
        prior_guard_job=h.pin(OLD / 'selected-family-source-guards-CPU-original01/job.json'),
        prior_guard_source=oldjob['runtime'], new_guard_source=validatorpin,
        exact_source_substitution=dict(old='renderer.FAILED_CLOCKS', new='renderer.REF_CLOCKS', count=3),
        original_ten_test_methods_preserved=True, expected_tests=10, config=configpin, job=jobpin,
        source_family=familypin, no_runtime_worker_policy_Torch_MAME_allowed=True,
        actual_preparer_protocol_required=True, sentinel_before_dedicated_worker_constructor=True,
        fixture_metadata_not_scientific_launch_readiness=True, original_attempt=1, no_retry=True))
    print(json.dumps(dict(config=configpin, job=jobpin, validator=validatorpin)))


if __name__ == '__main__':
    main()
