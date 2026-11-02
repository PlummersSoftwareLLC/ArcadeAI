"""Precommit, prepare and independently close original deadline reviews.

Default invocation is inert. This module never launches a process, retries a
leg, changes the learner, or qualifies complete-game performance.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT/'logs/managed-learning-20261015/run-26'
ORDER = ['R1', 'C1', 'R2', 'C2']
PROPERTIES = ['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0',
              'RuntimeMaxSec=1980', 'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no']
PINS = {
    'helpers': ('tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
                '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'),
    'reader': ('tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
               'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'),
    'archive': ('tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
                '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'),
    'sequence': ('tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py',
                 'b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4'),
    'controller': ('logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/extended-review-resources-original01/control_owned_health_CPU1980_v1.py',
                   'f96b6a954834ed204a4c1207ea336ccc14f5b44242f853c7b61c0a8dad8128ff'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def dependencies():
    for relative, sha in PINS.values():
        require(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == sha,
                'Original independent review dependency changed: '+relative)
    h = load('_deadline_review_prepare_helpers', ROOT/PINS['helpers'][0])
    reader = load('_deadline_review_prepare_reader', ROOT/PINS['reader'][0])
    def read(pin, as_json=True):
        return reader.read_pin(pin, as_json=as_json)
    return h, read


def validate_manifest(prepared, study):
    require(prepared['schema'] == 'robotron-deadline32-four-original-leg-preparation-v1'
            and prepared['ordered_legs'] == [r['leg'] for r in prepared['cases']] == ORDER
            and prepared['engineering_only'] is study['engineering_only'] is False,
            'Exact production four-leg study required')
    require(study['ordered_legs'] == ORDER and study['no_retry'] is True
            and study['horizon_ns'] == 3600_000_000_000
            and study['n_scored_per_leg'] == 32
            and study['full_game_quality_qualified'] is study['improvement_qualified']
            is study['promotion'] is False, 'Original fixed screening conditions required')


def precommit(manifest, guards, output):
    h, read = dependencies()
    mp = h.pin(manifest.resolve()); prepared = read(mp)
    study = read(prepared['study_precommit']); validate_manifest(prepared, study)
    gp = h.pin(guards.resolve()); publication = read(gp)
    require(publication['status'] == 'PASS' and len(publication['guards']) == 4,
            'Actual four-job CPU guard publication required')
    published = [read(pin) for pin in publication['guards']]
    records = []
    for case, guard, guardpin in zip(prepared['cases'], published, publication['guards']):
        root = Path(case['native_job']['path']).parent
        job = read(case['native_job']); configpin = h.pin(root/'controller-config-CPU-QUALIFIED.json')
        config = read(configpin); controller = load('_deadline_precommit_native_control', h.checked(case['native_controller']))
        require(guard['native_job'] == case['native_job'] and guard['status'] == 'PASS'
                and guard['actual_exit'] == 0 and guard['original_attempt'] == 1
                and guard['no_retry'] is True and job['prelaunch_family_guard_closeout'] == guardpin['path'],
                'Exact original native guard binding required')
        require(job['leg'] == case['leg'] and job['study_precommit'] == prepared['study_precommit']
                and job['checkpoint'] == study['policies'][case['role']]['checkpoint']
                and job['attempt'] == 1 and job['no_retry'] is True, 'Original policy/role/job binding differs')
        require(controller.checked_config(configpin['path']) == config, 'Qualified native config differs')
        for pin in config['pins']:
            require(controller.pin(pin['path']) == pin, 'Qualified native input changed')
        family = read(job['source_family_manifest'])
        reviewer = h.pin(HERE/'review_deadline32_rounds_v11.py')
        require(family['reviewer'] == reviewer, 'Exact held independent reviewer required')
        require(not (root/'independent-review-prepared-original01.json').exists()
                and not (root/('root-'+case['leg']+'-independent-qualified.json')).exists(),
                'Original review paths already consumed')
        records.append(dict(leg=case['leg'], role=case['role'], native_job=case['native_job'],
                            native_config=configpin, native_controller=case['native_controller'],
                            guard=guardpin, reviewer=reviewer,
                            review_job_path=str(root/'independent-review-job.json'),
                            review_config_path=str(root/'independent-review-controller-config.json'),
                            execution=str(root/'independent-review-execution-original01'),
                            report=str(root/'independent-deadline-review-original01.json')))
    output = output.resolve()
    require(output.is_relative_to(BASE) and not output.exists() and output.parent.is_dir(),
            'Exclusive review precommit directory required')
    output.mkdir(mode=0o700)
    return h.put(output/'precommitted-four-reviews.json', dict(
        schema='robotron-four-deadline32-independent-review-precommit-v1', native_prepared=mp,
        CPU_guard_publication=gp, cases=records, ordered_legs=ORDER,
        sources={key:h.pin(ROOT/value[0]) for key,value in PINS.items()},
        source=h.pin(Path(__file__).resolve()), properties=PROPERTIES, observation_s=2040,
        created_monotonic_s=time.monotonic(), boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        engineering_only=False, payload_launched=False, full_game_quality_qualified=False, promotion=False))


def selected(precommit_path, leg):
    h, read = dependencies(); pp = h.pin(precommit_path.resolve()); packet = read(pp)
    require(packet['schema'] == 'robotron-four-deadline32-independent-review-precommit-v1'
            and packet['ordered_legs'] == [r['leg'] for r in packet['cases']] == ORDER
            and packet['engineering_only'] is False and packet['properties'] == PROPERTIES
            and packet['observation_s'] == 2040, 'Exact precommitted review domain/resources required')
    require(packet['source'] == h.pin(Path(__file__).resolve()), 'Preparation source changed after precommit')
    for key, value in packet['sources'].items():
        require(value == h.pin(ROOT/PINS[key][0]), 'Review dependency identity changed')
    require(leg in ORDER, 'Unknown original leg')
    return h, read, pp, packet, packet['cases'][ORDER.index(leg)]


def closed_controller(root, prefix, configpin, sourcepin, sources, h, read):
    sequence = load('_deadline_review_original_sequence', h.checked(sources['sequence']))
    control = load('_deadline_review_original_control', h.checked(sourcepin))
    archive = load('_deadline_review_original_archive', h.checked(sources['archive']))
    config = read(configpin)
    require(control.checked_config(configpin['path']) == config, 'Original owned configuration changed')
    closed = sequence.verify_closed_scope(root, prefix, configpin, h, read, archive, control)
    result = read(closed['result']); child = read(h.pin(root/(prefix+'controller-original-child.json')))
    intentpin = h.pin(root/(prefix+'controller-original-launch.json')); intent = read(intentpin)
    require(type(result['actual_exit']) is int and result['actual_exit'] == 0
            and result['live_registration_errors'] == [] and result['intent'] == child['intent'] == intentpin
            and child['observed_live'] is True
            and sequence.birth(child['pid']) != child['starttime_ticks'],
            'Original owned controller terminal observation required')
    require(intent['source'] == sourcepin and intent['config'] == configpin
            and intent['argv'] == ['/usr/bin/python3.12','-I','-B',sourcepin['path'],
                                   '--execute','--config',configpin['path'],'--expected-source-sha256',sourcepin['sha256']],
            'Original owned controller intent/source differs')
    require(closed['identity']['unit'] == config['unit'], 'Original scope configuration differs')
    return closed


def prepare_leg(precommit_path, leg):
    h, read, pp, packet, case = selected(precommit_path, leg)
    root = Path(case['native_job']['path']).parent
    # Reject live or never-launched legs before creating any review artifact.
    closed = closed_controller(root, '', case['native_config'], case['native_controller'], packet['sources'], h, read)
    job = read(case['native_job']); resultpin = h.pin(Path(job['output'])/'result.json'); result = read(resultpin)
    require(result['original_job'] == case['native_job'] and result['complete'] is True
            and result['errors'] == [] and result['status'] == 'ORIGINAL_DEADLINE32_SEALED_AND_CLOSED'
            and result['attempt'] == 1 and result['no_retry'] is True, 'Original native completion required')
    require(all(not Path(case[key]).exists() for key in ('review_job_path','review_config_path','execution','report'))
            and not (root/'independent-review-prepared-original01.json').exists(), 'Original review attempt already consumed')
    review = dict(schema='robotron-deadline32-original-leg-independent-review-job-v1',
                  output=case['report'], native_job=case['native_job'], native_result=resultpin,
                  native_owner=closed['owner'], native_closure=closed['closure'],
                  native_config=case['native_config'], native_controller=case['native_controller'],
                  source_family_guard_closeout=case['guard'],
                  **{k:packet['sources'][k] for k in ('helpers','reader','archive')})
    inputs = [pp, packet['source'], *packet['sources'].values(), *job['inputs'],
              *[v for v in review.values() if isinstance(v,dict)], case['reviewer'], closed['result']]
    review['inputs'] = list({p['path']:p for p in inputs}.values())
    jp = h.put(Path(case['review_job_path']), review)
    control = load('_deadline_prepare_actual_review_control', h.checked(packet['sources']['controller']))
    config = dict(unit='robotron-deadline-review-'+case['native_job']['sha256'][:12]+'-'+leg.lower()+'-original01.service',
                  output=case['execution'], argv=['/usr/bin/python3.12','-I','-B',case['reviewer']['path'],
                  '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',case['reviewer']['sha256']],
                  properties=PROPERTIES, observation_s=2040,
                  pins=[control.pin(p['path']) for p in [jp,*review['inputs']]])
    cp = h.put(Path(case['review_config_path']),config)
    require(control.checked_config(cp['path']) == config, 'Exact review controller ABI differs')
    return h.put(root/'independent-review-prepared-original01.json',dict(precommit=pp, leg=leg,
                 review_job=jp, review_config=cp, controller=packet['sources']['controller'],
                 reviewer=case['reviewer'], no_retry=True, launched=False, full_game_quality_qualified=False))


def qualify(precommit_path, leg):
    h, read, pp, packet, case = selected(precommit_path, leg)
    root = Path(case['native_job']['path']).parent
    prepared = read(h.pin(root/'independent-review-prepared-original01.json'))
    require(prepared['precommit'] == pp and prepared['leg'] == leg
            and prepared['reviewer'] == case['reviewer'] and prepared['controller'] == packet['sources']['controller'],
            'Exact prepared original independent review required')
    cp = prepared['review_config']; cfg = read(cp); jp = prepared['review_job']; review = read(jp)
    require(cp == h.pin(case['review_config_path']) and jp == h.pin(case['review_job_path'])
            and cfg['properties'] == PROPERTIES and cfg['observation_s'] == 2040
            and cfg['output'] == case['execution'] and review['output'] == case['report']
            and review['native_job'] == case['native_job'] and cfg['argv'] == [
                '/usr/bin/python3.12','-I','-B',case['reviewer']['path'],'--execute','--job',jp['path'],
                '--job-sha256',jp['sha256'],'--source-sha256',case['reviewer']['sha256']], 'Actual review job/argv/resources differ')
    closed = closed_controller(root,'independent-review-',cp,packet['sources']['controller'],packet['sources'],h,read)
    fields = closed['fields']; owner = closed['identity']
    expected = dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='33min',
                    TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no',NRestarts='0',ExecMainCode='1',ExecMainStatus='0')
    require(all(fields[k] == v for k,v in expected.items()),'Actual independent CPU resources/exit differ')
    live = read(h.pin(Path(cfg['output'])/'original-first-observed-show-command.json'))
    livefields = dict(line.split('=',1) for line in read(live['stdout'],False).decode().splitlines() if '=' in line)
    require(livefields['MainPID'] == str(owner['pid']) and livefields['InvocationID'] == owner['invocation_id']
            and livefields['ControlGroup'].endswith('/'+owner['unit'])
            and not Path('/sys/fs/cgroup'+livefields['ControlGroup']).exists(), 'Original reviewer cgroup/live identity differs')
    reportpin = h.pin(case['report']); report = read(reportpin); native = read(review['native_result'])
    nativeowner = read(review['native_owner']); job = read(case['native_job'])
    require(report['schema'] == 'robotron-deadline32-original-leg-independent-review-v1'
            and report['status'] == 'PASS' and report['original_job'] == case['native_job'] and report['leg'] == leg
            and report['native_result'] == review['native_result'] and report['source_family'] == job['source_family_manifest']
            and owner['invocation_id'] != nativeowner['invocation_id'] and report['actual_native_exit'] == 0
            and report['deadline_metric_independently_qualified'] is True
            and report['positive_owned_native_observer_children_threads_and_lease_closure'] is True
            and report['complete_game_quality_qualified'] is report['improvement_qualified'] is False
            and len(report['all32_original_prefixes']) == 32, 'Exact independent successful original report required')
    seal = read(native['deadline_score_seal'])
    for key in ('n_scored','n_completed','n_censored','score_sum','mean_score','median_score'):
        require(report['score_cutoff'][key] == seal[key], 'Independent sealed score audit differs')
    for pin in review['inputs']: h.checked(pin)
    return h.put(root/('root-'+leg+'-independent-qualified.json'),dict(
        schema='robotron-root-deadline32-leg-qualification-v1',status='INDEPENDENT_DEADLINE32_QUALIFIED',leg=leg,
        actual_review_tool_terminal_exit=0,all_six_descriptors_resources_argv_birth_units_cgroup_release_verified=True,
        independent_report=reportpin,review_owner=closed['owner'],review_closure=closed['closure'],
        controller_result=closed['result'],qualified_review_config=cp,precommit=pp,source=h.pin(Path(__file__).resolve()),
        score_cutoff=report['score_cutoff'],full_game_quality_qualified=False,improvement_qualified=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action',choices=('precommit','prepare-leg','qualify'))
    parser.add_argument('--manifest',type=Path);parser.add_argument('--guards',type=Path)
    parser.add_argument('--output',type=Path);parser.add_argument('--precommit',type=Path)
    parser.add_argument('--leg',choices=ORDER);args=parser.parse_args()
    if args.action == 'precommit': result=precommit(args.manifest,args.guards,args.output)
    elif args.action == 'prepare-leg': result=prepare_leg(args.precommit,args.leg)
    elif args.action == 'qualify': result=qualify(args.precommit,args.leg)
    else: print('PLAN_ONLY_NO_READS_OR_ACTIONS');return
    print(json.dumps(result),flush=True)


if __name__ == '__main__': main()
