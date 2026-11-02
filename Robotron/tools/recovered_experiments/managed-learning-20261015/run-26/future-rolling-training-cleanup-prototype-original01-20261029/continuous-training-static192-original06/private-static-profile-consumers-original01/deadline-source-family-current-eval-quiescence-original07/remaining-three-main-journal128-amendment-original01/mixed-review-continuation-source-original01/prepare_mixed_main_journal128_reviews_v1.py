"""Precommit, prepare and independently close original deadline reviews.

Default invocation is inert. This module never launches a process, retries a
leg, changes the learner, or qualifies complete-game performance.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation')
LOCAL = Path(__file__).resolve().parent
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


CAPACITY_SOURCE_PACKET = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/remaining-three-main-journal128-amendment-original01/prepared-remaining-three-main-journal128-private-ports-and-metadata-producer-SOURCE-ONLY-v2.json', 'sha256': 'b3d0f32f01d910a731eca5d8801102adf3c6ea4bad2821c6477e73dc5381d8b0', 'bytes': 24993, 'identity': {'device': 2304, 'inode': 87556244, 'bytes': 24993, 'mtime_ns': 1793327519004069612, 'ctime_ns': 1793327519004069612, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
ORIGINAL_PREPARER = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/prepare_deadline_independent_review_v4.py', 'sha256': 'd0955c345dd46d08d261cf6c20c8dff87e1335c4977d55d75a8ed895fac99be0', 'bytes': 17179, 'identity': {'device': 2304, 'inode': 85357787, 'bytes': 17179, 'mtime_ns': 1793311807198943930, 'ctime_ns': 1793311807226163363, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
ORIGINAL_SEQUENCE = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/postguard-owned-operations-original01/sequence_physical_deadline_study_v3.py', 'sha256': 'd821a0121ad4b2cdec82877299d5666aecee56b42aa11c5ce70c738096cc80f9', 'bytes': 21820, 'identity': {'device': 2304, 'inode': 85459256, 'bytes': 21820, 'mtime_ns': 1793314910867886909, 'ctime_ns': 1793314910868296958, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
ORIGINAL_R1_PRECOMMIT = {'bytes': 22605, 'identity': {'bytes': 22605, 'ctime_ns': 1793317396390180346, 'device': 2304, 'inode': 80381177, 'mode': '0o444', 'mtime_ns': 1793317396390180346, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fresh-c0acc-b231-current-quiescence-deadline32-RCRC-original02-20261029/review-precommit-original01/precommitted-four-reviews.json', 'sha256': '4c987cbe459f56e4c650114b3556e088e2d110bce6847f7f7b8fc2e448ed93a8'}
ORIGINAL_R1_QUALIFICATION = {'bytes': 5191, 'identity': {'bytes': 5191, 'ctime_ns': 1793323173670659153, 'device': 2304, 'inode': 80229012, 'mode': '0o444', 'mtime_ns': 1793323173670659153, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fresh-c0acc-b231-current-quiescence-deadline32-RCRC-original02-20261029/R1/root-R1-independent-qualified.json', 'sha256': 'f65fe0b91c8c88e4ba618a38a11e3e759465dba0026ce6377006672738e60971'}
FUTURE = ['C1','R2','C2']

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


def metadata_input_classification(values, h):
    """Preserve full8 holds; don't repeatedly hash opaque bodies in outer checks.

    Original R1 qualification replay is unchanged and may itself hash its own
    previously held checkpoints. No blanket body-free claim is made here.
    """
    catalogue = json.loads(h.checked(CAPACITY_SOURCE_PACKET).read_bytes())
    producer = load('_mixed_metadata_exact_identity', h.checked(catalogue['producer']))
    witness = json.loads(h.checked(catalogue['fixed_input_pins']['interpreter_symlink_binding']).read_bytes())
    metadata = []; opaque = []
    for value in values:
        path = Path(value['path'])
        if path.suffix == '.pt' or str(path) in ('/usr/games/mame','/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python'):
            producer.held_identity(value,witness)
            opaque.append(value)
        else:
            h.checked(value); metadata.append(value)
    return dict(schema='robotron-mixed-review-outer-metadata-full8-classification-v1',
        metadata_inputs=metadata,stat_only_inputs=opaque,all_full8_input_holds_preserved=True,
        original_R1_qualification_replay_full_hash_checks_unchanged=True)


def original_R1_verification():
    """Replay the ORIGINAL sealed qualification through original d821/d095 only."""
    h, read = dependencies()
    require(read(ORIGINAL_R1_PRECOMMIT)['source'] == ORIGINAL_PREPARER,
            'Original R1 preparation source differs')
    old = load('_mixed_review_original_R1_sequence', h.checked(ORIGINAL_SEQUENCE))
    return old.verify_existing_R1(Path(ORIGINAL_R1_PRECOMMIT['path']), ORIGINAL_R1_QUALIFICATION)


def validate_mixed_identity(wrapper, prepared, original, old_review, selected_amendment):
    require(wrapper['schema'] == 'robotron-prepared-unused-three-leg-main-journal128-amendment-v1'
            and wrapper['original_R1_review_precommit'] == ORIGINAL_R1_PRECOMMIT
            and wrapper['original_R1_qualification'] == ORIGINAL_R1_QUALIFICATION,
            'Explicit original R1/amended-future study selection required')
    require(prepared['original_R1_review_precommit'] == ORIGINAL_R1_PRECOMMIT
            and prepared['original_R1_qualification'] == ORIGINAL_R1_QUALIFICATION
            and prepared['cases'][0] == original['cases'][0]
            and prepared['cases'][0]['native_job'] == old_review['cases'][0]['native_job']
            and prepared['study_precommit'] == original['study_precommit']
            and prepared['capacity_amendment'] == wrapper['selected_amendment'],
            'Original R1 row and common study must remain exact')
    require(selected_amendment['original_review_precommit'] == ORIGINAL_R1_PRECOMMIT
            and selected_amendment['original_R1_qualification'] == ORIGINAL_R1_QUALIFICATION
            and selected_amendment['future_legs'] == FUTURE
            and selected_amendment['original_main_case_inventory_profiles_and_R1_unchanged'] is True
            and selected_amendment['scientific_fields_unchanged'] is True
            and selected_amendment['main_or_journal_changed'] is False,
            'Only unused future source capacity may change')
    require([row['leg'] for row in wrapper['subjects']] == FUTURE,
            'Exactly the three unused future subjects required')



def validate_three_publication(publication):
    require(publication['schema'] == 'robotron-three-capacity-exact-native-guard-publication-v1'
            and publication['status'] == 'PASS' and publication['ordered_legs'] == FUTURE
            and len(publication['guards']) == 3 and publication['old_exact_job_receipts_reused'] is False,
            'Fresh exact-three capacity guard publication required')


def precommit(manifest, guards, output):
    h, read = dependencies()
    ap = h.pin(manifest.resolve()); wrapper = read(ap)
    catalogue = read(CAPACITY_SOURCE_PACKET); h.checked(CAPACITY_SOURCE_PACKET)
    require(wrapper['source'] == catalogue['producer'], 'Selected capacity metadata producer differs')
    mp = wrapper['mixed_manifest']; prepared = read(mp)
    old_review = read(ORIGINAL_R1_PRECOMMIT)
    original = read(prepared['original_manifest']); study = read(prepared['study_precommit'])
    validate_manifest(prepared, study)
    amendment = read(wrapper['selected_amendment'])
    validate_mixed_identity(wrapper, prepared, original, old_review, amendment)
    require(amendment['source'] == catalogue['producer'] and prepared['original_manifest'] == catalogue['fixed_input_pins']['original_manifest'],
            'Capacity amendment ancestry differs')
    require(original_R1_verification() == ORIGINAL_R1_QUALIFICATION, 'Original R1 replay differs')
    gp = h.pin(guards.resolve()); publication = read(gp)
    validate_three_publication(publication)
    require(publication['prepared_capacity_amendment'] == ap, 'Guard publication belongs to another capacity preparation')
    h.checked(publication['original_three_CPU_closeout'])
    records = [copy.deepcopy(old_review['cases'][0])]
    for case, subject, guardpin in zip(prepared['cases'][1:], wrapper['subjects'], publication['guards']):
        guard = read(guardpin); root = Path(case['native_job']['path']).parent
        job = read(case['native_job']); configpin = h.pin(Path(case['prospective_qualified_config_path']))
        require(subject['leg'] == case['leg'] and subject['native_job'] == case['native_job']
                and subject['qualified_config_path'] == configpin['path'], 'Selected amended subject/config differs')
        config = read(configpin); controller = load('_mixed_precommit_native_control', h.checked(case['native_controller']))
        require(guard['schema'] == 'robotron-deadline32-original-prelaunch-family-guard-v1'
                and guard['native_job'] == case['native_job'] and guard['runtime'] == job['runtime']
                and guard['status'] == 'PASS' and guard['actual_exit'] == 0 and guard['original_attempt'] == 1
                and guard['no_retry'] is True and guard['original_three_CPU_closeout'] == publication['original_three_CPU_closeout']
                and job['prelaunch_family_guard_closeout'] == guardpin['path'],
                'Exact new native-job guard/three-scope closure required')
        require(job['leg'] == case['leg'] and job['study_precommit'] == prepared['study_precommit']
                and job['checkpoint'] == study['policies'][case['role']]['checkpoint']
                and job['attempt'] == 1 and job['no_retry'] is True
                and job['main_journal_capacity_amendment'] == wrapper['selected_amendment'],
                'Original policy/role/job identity differs')
        require(controller.checked_config(configpin['path']) == config, 'Qualified new native config differs')
        require(config['argv'][4:] == [job['runtime']['path'],'--execute','--job',case['native_job']['path'],
                '--job-sha256',case['native_job']['sha256'],'--source-sha256',job['runtime']['sha256']],
                'Qualified config invokes another native job or runtime')
        require(controller.pin(case['native_job']['path']) in config['pins']
                and controller.pin(guardpin['path']) in config['pins'], 'Qualified config lacks exact new job/guard pins')
        held = {value['path']:value for value in job['inputs']}
        for value in config['pins']:
            path = Path(value['path'])
            if path.suffix == '.pt' or str(path) in ('/usr/games/mame','/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python'):
                full = held[value['path']]; metadata_input_classification([full],h)
                expected = dict(path=full['path'],sha256=full['sha256'],bytes=full['bytes'],
                    identity={key:full['identity'][key]for key in ('device','inode','mode','uid','nlink')})
                require(value == expected, 'Qualified opaque input lost its exact declared full8/SHA')
            else:
                require(controller.pin(value['path']) == value, 'Qualified native input changed')
        family = read(job['source_family_manifest']); reviewer = family['reviewer']
        require(reviewer == catalogue['private_sources']['reviewer']
                and job['runtime'] == catalogue['private_sources']['runtime']
                and case['native_controller'] == catalogue['private_sources']['controller'],
                'Explicit selected capacity reviewer/runtime/controller required')
        h.checked(reviewer)
        require(not (root/'independent-review-prepared-original01.json').exists()
                and not (root/('root-'+case['leg']+'-independent-qualified.json')).exists(),
                'Original future review paths already consumed')
        records.append(dict(leg=case['leg'], role=case['role'], native_job=case['native_job'],
            native_config=configpin, native_controller=case['native_controller'], guard=guardpin, reviewer=reviewer,
            review_job_path=str(root/'independent-review-job.json'),review_config_path=str(root/'independent-review-controller-config.json'),
            execution=str(root/'independent-review-execution-original01'),report=str(root/'independent-deadline-review-original01.json')))
    output = output.resolve()
    require(output.is_relative_to(BASE) and not output.exists() and output.parent.is_dir(),
            'Exclusive mixed review precommit directory required')
    output.mkdir(mode=0o700)
    return h.put(output/'precommitted-four-reviews.json',dict(
        schema='robotron-four-deadline32-independent-review-precommit-v1',native_prepared=mp,CPU_guard_publication=gp,
        cases=records,ordered_legs=ORDER,sources={key:h.pin(ROOT/value[0]) for key,value in PINS.items()},
        source=h.pin(Path(__file__).resolve()),properties=PROPERTIES,observation_s=2040,
        retained_R1=dict(precommit=ORIGINAL_R1_PRECOMMIT,qualification=ORIGINAL_R1_QUALIFICATION,
            preparer=ORIGINAL_PREPARER,sequence=ORIGINAL_SEQUENCE),capacity_preparation=ap,
        capacity_source_packet=CAPACITY_SOURCE_PACKET,capacity_amendment=wrapper['selected_amendment'],
        created_monotonic_s=time.monotonic(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        engineering_only=False,original_R1_already_qualified=True,future_capacity_payload_launched=False,
        payload_launched_by_this_preparation=False,full_game_quality_qualified=False,promotion=False))


def selected(precommit_path, leg):
    h, read = dependencies(); pp = h.pin(precommit_path.resolve()); packet = read(pp)
    require(packet['schema'] == 'robotron-four-deadline32-independent-review-precommit-v1'
            and packet['ordered_legs'] == [r['leg'] for r in packet['cases']] == ORDER
            and packet['engineering_only'] is False and packet['properties'] == PROPERTIES
            and packet['observation_s'] == 2040, 'Exact precommitted review domain/resources required')
    require(packet['source'] == h.pin(Path(__file__).resolve()), 'Preparation source changed after precommit')
    for key, value in packet['sources'].items():
        require(value == h.pin(ROOT/PINS[key][0]), 'Review dependency identity changed')
    require(packet['retained_R1'] == dict(precommit=ORIGINAL_R1_PRECOMMIT,qualification=ORIGINAL_R1_QUALIFICATION,
            preparer=ORIGINAL_PREPARER,sequence=ORIGINAL_SEQUENCE), 'Original R1 delegation changed')
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
    require(leg in FUTURE, 'R1 review is already sealed; only future legs may be prepared')
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
    require(leg in FUTURE, 'R1 qualification must be replayed read-only through its original source')
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
