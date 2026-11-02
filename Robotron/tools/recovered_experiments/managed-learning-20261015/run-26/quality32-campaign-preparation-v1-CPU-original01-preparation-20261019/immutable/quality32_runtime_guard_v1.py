"""Unselected original R/C/R/C observer, with unchanged main health witnesses.

Used only through the exact original-pilot controller and an authenticated job.
It records prospective bindings and live parent/process identities, retains the
native outcome, then launches one bounded CPU review. It never changes learning,
retries a cohort or audit, publishes a policy, or adopts a historical process.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = GAME/'tools/quality_capacity_proposal'
BASE = GAME/'tools/eval_capacity_proposal/pilot_runtime_guard_raw_API_v1.py'
BASE_SHA = 'd79aef2c295e9642e54bce2fc25a355b63874ed80394732ac6038c1b69e5a063'
REVIEWER = HERE/'review_closed_quality32_v3.py'
REVIEWER_SHA = '9818c4d3e67956db1b726b50142d73d50875445091be60891a577d1ea7d3fea9'
REVIEW_CONTROL_SHA = '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
SLOTS = list(range(4096,4128))
ORDER = ['reference','candidate','reference','candidate']


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def live_process(pid, parent, cgroup, command=None):
    """Bracket real /proc identity, command, uid, parent, cgroup and affinity."""
    require(type(pid) is int and pid > 0, 'Positive original process PID required')
    directory = Path('/proc')/str(pid)
    def stat():
        values = (directory/'stat').read_text().rsplit(')',1)[1].split()
        require(values[0] not in ('Z','X','x'), 'Original process is no longer live')
        return int(values[1]), int(values[19])
    before = stat()
    argv = (directory/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
    argv = [value.decode() for value in argv]
    groups = (directory/'cgroup').read_text().splitlines()
    status = dict(line.split(':',1) for line in (directory/'status').read_text().splitlines() if ':' in line)
    affinity = sorted(os.sched_getaffinity(pid))
    require(before == stat() and before[0] == parent and before[1] > 0
            and groups == ['0::'+cgroup]
            and [int(value) for value in status['Uid'].split()] == [os.getuid()]*4
            and affinity and argv and (command is None or argv == command),
            'Original live process parent, start, cgroup, command or owner differs')
    return dict(pid=pid,parent_pid=parent,starttime_ticks=before[1],cgroup=cgroup,
        observed_live=True,command=argv,affinity=affinity,observed_unix_s=time.time())


def validate_records(status, plan_sha):
    require(status['plan_sha256'] == plan_sha and status['state'] in ('preparing','running','finished'),
            'Original campaign status or plan identity differs')
    records = status['legs']
    require(len(records) <= 4 and [row['index'] for row in records] == list(range(1,len(records)+1)),
            'Only one ordered original record per leg')
    for position, row in enumerate(records):
        require(type(row['index']) is int and row['role'] == ORDER[position]
                and row['state'] in ('running','finished')
                and (row['state'] != 'running' or position == len(records)-1),
                'Original leg order/state differs')
        # A just-published running record may not yet have its child PID.
        if 'pid' in row:
            require(type(row['pid']) is int and row['pid'] > 0, 'Exact evaluator PID required')
        if row['state'] == 'finished':
            require(type(row.get('returncode')) is int and row['returncode'] == 0 and 'pid' in row,
                    'Original evaluator failed; no retry or next cohort authorized')
    return records


def campaign_command(job, template):
    """One explicit native command, including every supported protocol knob."""
    parameters = job['campaign_parameters']
    require(set(parameters) == {'directory','reference_label','candidate_label','hypothesis','boot_assets'},
            'Exact native campaign parameters required')
    directory = Path(parameters['directory'])
    require(directory.is_absolute() and directory.parent == GAME/'logs/managed-learning-20261015'
            and all(isinstance(parameters[key],str) and parameters[key].strip()
                for key in ('reference_label','candidate_label','hypothesis')),
            'Owned future campaign directory and explicit labels/hypothesis required')
    argv = [str(GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',
        str(HERE/'profile03/Robotron/tools/run_quality_campaign.py')]
    for flag, value in (
        ('--reference-checkpoint',template['reference']['path']),
        ('--candidate-checkpoint',template['candidate']['path']),
        ('--output-dir',str(directory)),('--reference-label',parameters['reference_label']),
        ('--candidate-label',parameters['candidate_label']),
        ('--gpu-uuid','GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'),
        ('--boot-assets',parameters['boot_assets']),('--actors','32'),('--port','9999'),
        ('--cohort-s','5400'),('--timeout-s','7200'),('--mame','/usr/games/mame'),
        ('--rompath',str(GAME/'roms')),('--hypothesis',parameters['hypothesis'])):
        argv.extend([flag,str(value)])
    return argv+['--game-boundary-diagnostics','--launch']


def guard_class(base):
    """Reuse, byte-for-byte, raw API preservation and all main192 predicates."""
    class QualityGuard(base.MainGuard):
        def __init__(self, config, inputs):
            super().__init__(config,inputs)
            self.plan = dict(unit=config['unit'],timer=config['unit'].removesuffix('.service')+'.timer')
            self.native_plan = None
            self.binding_entry = None
            self.births = {}
            self.actor_births = {}
            self.review_attempted = False

        def validate_config(self, config):
            require(config == self.config and config['argv'] == campaign_command(self.job,self.template)
                    and config['pins'] == self.job['launch_pins']
                    and type(config['observation_s']) is int and config['observation_s'] == 30000,
                    'Exact original native command, PINs and observation deadline required')
            require(re.fullmatch(r'robotron-[A-Za-z0-9_-]+\.service',config['unit']) is not None,
                    'Exact original native unit required')
            props = dict(value.split('=',1) for value in config['properties'])
            require(len(props) == len(config['properties']) and props == dict(
                CPUQuota='1200%',MemoryMax='12G',MemorySwapMax='0',RuntimeMaxSec='29400',
                TasksMax='512',TimeoutStopSec='120',KillMode='mixed',SendSIGKILL='no'),
                'Whole campaign bounded native resource/cleanup policy differs')

        def prepare_bindings(self):
            self.binding_dir.mkdir(mode=0o700)
            for name in ('main-samples','main-rejections','API-wires','leg-births'):
                (self.binding_dir/name).mkdir(mode=0o700)
            self.main['baseline_API'] = self.save(self.binding_dir/'baseline-API.raw.json',self.baseline_wire)
            self.main_entry = self.save(self.binding_dir/'main-binding.json',self.main)
            self.held_sha = hashlib.sha256(json.dumps(self.main['held_hashes'],sort_keys=True,
                separators=(',',':')).encode()).hexdigest()
            self.sample()

        def record_birth(self, identity):
            forbidden = {self.main['owner']['pid'],*(owner['pid'] for owner in self.main['actors'])}
            require(self.identity is None and identity['unit'] == self.config['unit']
                    and identity['timer'] == self.plan['timer'] and identity['pid'] not in forbidden
                    and identity['observed_live'] is True
                    and identity['cgroup'].endswith('/'+self.config['unit']),
                    'One original private campaign birth required')
            self.identity = copy.deepcopy(identity)
            self.owner_entry = self.save(self.binding_dir/'native-owner.json',identity)

        def capture_plan(self):
            if self.native_plan is not None or self.identity is None:
                return
            directory = Path(self.job['campaign_parameters']['directory'])
            path = directory/'plan.json'
            if not path.exists():
                return
            entry = self.reader.pin(path)
            plan = self.reader.read_pin(entry)
            campaign = dict(output_directory=str(directory),plan_sha256=entry['sha256'],
                native_unit=self.identity['unit'],native_owner_path=self.owner_entry['path'],
                command=self.config['argv'],controller_output=self.config['output'],
                evaluator_source_hashes=plan['evaluator_source_hashes'],
                execution_source_hashes=plan['execution_source_hashes'])
            self.cohorts.validate_plan(plan,dict(campaign,checkpoints=plan['checkpoints']),self.game)
            for role in ('reference','candidate'):
                require(plan['checkpoints'][role] == dict(source=self.template[role]['path'],
                    snapshot=str(directory/'checkpoints'/(role+'.pt')),sha256=self.template[role]['sha256']),
                    'Original native plan substituted a checkpoint')
                specs = [spec for spec in plan['legs'] if spec['role'] == role]
                require(all(spec['job']['label'] == self.job['campaign_parameters'][role+'_label']+f'-{number:02d}'
                            for number,spec in enumerate(specs,1)), 'Original native role label differs')
            # This write must precede admission. The independent reviewer checks
            # its filesystem timestamps against the original first receipt.
            binding = copy.deepcopy(self.template)
            binding['campaign'] = campaign
            self.binding_entry = self.save(self.binding_dir/'campaign-binding.json',binding)
            self.native_plan = plan
            status_path = Path(plan['legs'][0]['evaluator_status_path'])
            if status_path.exists():
                first = json.loads(status_path.read_bytes())
                start = first.get('start_ts',first.get('admission_start_unix_s'))
                require(start is None or start >= max(self.binding_entry['identity']['ctime_ns'],
                    self.binding_entry['identity']['mtime_ns'])/1e9,
                    'Prospective root binding missed first admission; never adopt late evidence')

        def capture_actors(self):
            self.capture_plan()
            if self.native_plan is None:
                return
            directory = Path(self.job['campaign_parameters']['directory'])
            path = directory/'status.json'
            if not path.exists():
                return
            records = validate_records(json.loads(path.read_bytes()),self.binding_entry_value()['campaign']['plan_sha256'])
            for row in records:
                key = str(row['index'])
                spec = self.native_plan['legs'][row['index']-1]
                require(all(row[name] == spec[name] for name in
                    ('receipt_path','console_log','evaluator_status_path')), 'Original leg paths changed')
                if key in self.births:
                    require(row.get('pid') == self.births[key]['pid'], 'Original evaluator PID changed')
                elif row['state'] == 'running' and 'pid' in row:
                    value = live_process(row['pid'],self.identity['pid'],self.identity['cgroup'],spec['command'])
                    self.save(self.binding_dir/'leg-births'/('leg'+key+'-evaluator.json'),value)
                    self.births[key] = value
                elif row['state'] == 'finished':
                    raise ValueError('Original live evaluator birth missed; never adopt completed records')
                if key not in self.births:
                    continue
                actor_status = Path(spec['evaluator_status_path'])
                if actor_status.exists():
                    display = json.loads(actor_status.read_bytes())
                    current = display.get('actor_pids')
                    if current is None and display.get('phase') == 'finished':
                        current = {slot:value['pid'] for slot,value in display.get('socket_wait',{}).get('actors',{}).items()}
                    current = {} if current is None else current
                    require(set(current).issubset(set(map(str,SLOTS))), 'Foreign private actor slot')
                    if key in self.actor_births:
                        require(current == {slot:value['pid'] for slot,value in self.actor_births[key].items()},
                                'Original private actor PIDs changed')
                    elif set(current) == set(map(str,SLOTS)) and row['state'] == 'running':
                        require(len(set(current.values())) == 32 and all(type(pid) is int for pid in current.values()),
                                'Exactly32 distinct original actor PIDs required')
                        values = {slot:live_process(pid,self.births[key]['pid'],self.identity['cgroup'])
                                  for slot,pid in current.items()}
                        self.save(self.binding_dir/'leg-births'/('leg'+key+'-actors.json'),values)
                        self.actor_births[key] = values
                if row['state'] == 'finished':
                    require(key in self.actor_births, 'Original live32 actor births missed; no historical adoption')

        def binding_entry_value(self):
            return self.reader.read_pin(self.binding_entry)

        def _finish(self):
            if self.failed is None and (set(self.births) != {'1','2','3','4'}
                    or set(self.actor_births) != {'1','2','3','4'} or self.binding_entry is None):
                self.failed = 'Missing original prospective binding or live four-leg birth records'
            self.birth_entry = self.save(self.binding_dir/'leg-evaluator-births.json',self.births)
            self.actor_entry = self.save(self.binding_dir/'leg-actor-identities.json',self.actor_births)
            # Base _finish retains all raw/rejected API witnesses and progress
            # policy. Prevent its single-pilot empty actor registry fallback.
            self.actors = self.actor_births
            super()._finish()

        def close_and_review(self, result):
            require(result['lifecycle_complete'] is True and result['unit_released'] is True and self.finished
                    and not self.review_attempted, 'Original native closure and one review attempt required')
            self.review_attempted = True
            out = Path(self.config['output'])
            if self.binding_entry is None:
                self.save(out/'root-controller-result.json',dict(status='NO_PROSPECTIVE_BINDING_REVIEW_NOT_LAUNCHED',
                    original_native_exit=result['original_exit'],valid=False,retry=False,error=self.failed))
                return dict(valid=False,quality_qualified=False)
            directory = Path(self.job['campaign_parameters']['directory'])
            context = dict(schema='robotron-closed-quality32-campaign-context-v1',binding=self.binding_entry,
                native_owner=self.owner_entry,native_closure=self.reader.pin(self.review_job['runtime_paths']['pilot_closure']),
                native_controller_config=self.config_pin,main_binding=self.main_entry,
                main_observations=self.main_manifest,leg_evaluator_births=self.birth_entry,
                leg_actor_identities=self.actor_entry,status_final=self.reader.pin(directory/'status.json'),
                summary_final=self.reader.pin(directory/'summary.json'))
            closed = self.save(self.review_job['closed_context_path'],context)
            review_job = dict(schema='robotron-closed-quality32-root-review-job-v1',binding=self.binding_entry,
                closed_context_path=self.review_job['closed_context_path'],output=self.job['review_output'],
                main_guard_source=self.job['main_guard_source'],lease_path=self.job['lease_path'],
                lease_identity=self.job['lease_identity'])
            review_job_pin = self.save(self.binding_dir/'original-review-job.json',review_job)
            control = self.reader.checked_module('_quality32_CPU_review_'+str(time.time_ns()),self.job['review_controller_source'])
            review_config = dict(unit=self.job['review_unit'],output=self.job['review_execution'],
                argv=['/usr/bin/python3.12','-I','-B',str(REVIEWER),'--execute','--job',review_job_pin['path'],
                    '--job-sha256',review_job_pin['sha256'],'--source-sha256',REVIEWER_SHA],
                properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
                    'TasksMax=256','TimeoutStopSec=5','SendSIGKILL=no'],
                pins=[control.pin(entry['path']) for entry in
                    [review_job_pin,self.binding_entry,closed,self.job['reviewer_source'],
                     self.job['review_controller_source'],self.job['main_guard_source']]],observation_s=240)
            config_path = self.binding_dir/'original-review-controller-config.json'
            review_config_pin = self.save(config_path,review_config)
            self.save(out/'root-original-independent-review-attempt.json',dict(attempt=1,retry=False,
                context=closed,source=self.job['reviewer_source'],job=review_job_pin,config=review_config_pin))
            # Same process owns scheduling and observation. No retry on failure,
            # timeout, invalid review, missing output or incomplete release.
            control.checked_config(config_path)
            control.launch(config_path)
            closure = control.observe(config_path)
            require(closure['lifecycle_complete'] and closure['unit_released'],
                    'Original CPU review observation/release incomplete; leave owned evidence')
            owner_pin = self.reader.pin(Path(review_config['output'])/'root-original-identity.json')
            closure_pin = self.reader.pin(Path(review_config['output'])/'root-original-result-and-owned-release.json')
            report_pin = self.reader.pin(Path(review_job['output'])/'review.json')
            report = self.reader.read_pin(report_pin)
            self.save(out/'root-controller-result.json',dict(status='ORIGINAL_NATIVE_AND_CPU_REVIEW_CLOSED',
                original_native_exit=result['original_exit'],original_review_exit=closure['original_exit'],
                valid=report['valid'],quality_qualified=report['quality_qualified'],review_report=report_pin,
                review_job=review_job_pin,review_owner=owner_pin,review_closure=closure_pin,
                review_controller_config=review_config_pin,main_guard_error=self.failed,
                retry=False,promotion=False,learning_speed_gain_verified=False))
            return report
    return QualityGuard


def prepare(config, config_pin):
    """All closed predecessor and acquisition evidence precedes any output."""
    require(digest(BASE) == BASE_SHA, 'Exact inherited raw main observer changed')
    spec = importlib.util.spec_from_file_location('_quality32_base_'+str(time.time_ns()),BASE)
    base = importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    reader = base.reader_module()
    reader.read_pin(config_pin,as_json=False)
    require(json.loads(Path(config_pin['path']).read_bytes()) == config
            and set(config) == {'unit','output','argv','properties','pins','observation_s','guard_source','pilot_controller_job'}
            and config['guard_source'] == reader.pin(Path(__file__).resolve()),
            'Exact source-bound root configuration required')
    job = reader.read_pin(config['pilot_controller_job'])
    require(job['schema'] == 'robotron-original-quality32-control-job-v1', 'Exact original quality32 control job required')
    require(job['reviewer_source']['path'] == str(REVIEWER) and job['reviewer_source']['sha256'] == REVIEWER_SHA,
            'Exact tested independent quality reviewer required')
    require(job['review_controller_source']['path'] == str(HERE/'control_quality32_review_v1.py')
            and job['review_controller_source']['sha256'] == REVIEW_CONTROL_SHA,
            'Exact original bounded CPU review controller required')
    reader.read_pin(job['review_controller_source'],as_json=False)
    reviewer = reader.checked_module('_quality32_preflight_review_'+str(time.time_ns()),job['reviewer_source'])
    runtime_path = GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
    require(digest(runtime_path) == '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445',
            'Exact runtime/archive validator required')
    runtime = reader.checked_module('_quality32_preflight_runtime_'+str(time.time_ns()),reader.pin(runtime_path))
    def read(entry,as_json=True):
        return reader.read_pin(entry,as_json=as_json)
    capacity = read(job['capacity_review'])
    require(capacity['valid'] is True and capacity['status'] == 'VALID_ONE_ORIGINAL32_ACTOR_RUNTIME_PILOT'
            and capacity['original_native_exit'] == 0 and capacity['private_cleanup_verified'] is True
            and capacity['main192_continuous_holds_verified'] is True,
            'Current original32 runtime must independently pass before future selection')
    for item in job['preceding_originals']:
        owner = read(item['owner']);closure = read(item['closure'])
        runtime.archived_closure(closure,owner,read,exit_zero=True)
        require(base.process_start(owner['pid']) is None and owner.get('cgroup')
                and not Path('/sys/fs/cgroup'+owner['cgroup']).exists(), 'A preceding original owner remains')
        for unit in (owner['unit'],owner['timer']):
            require(base.unit_fields(unit).get('LoadState') == 'not-found', 'A preceding original unit remains')
    require(len(job['preceding_originals']) >= 2, 'Both current original native/outer closures required')
    template = read(job['binding_template'])
    require(set(template) == {'candidate','reference','evidence','expected_window','main_holds'},
            'Only prospective acquisition and main holds belong in the root template')
    require(digest(reviewer.DEPENDENCIES['acquisition'][0]) == reviewer.DEPENDENCIES['acquisition'][1],
            'Exact acquisition component changed')
    acquisition = reader.checked_module('_quality32_preflight_acquisition_'+str(time.time_ns()),
        reader.pin(reviewer.DEPENDENCIES['acquisition'][0]))
    acquisition.review_acquisition(template,read,runtime.archived_closure)
    require(digest(reviewer.DEPENDENCIES['cohorts'][0]) == reviewer.DEPENDENCIES['cohorts'][1],
            'Exact cohort component changed')
    cohorts = reader.checked_module('_quality32_preflight_cohorts_'+str(time.time_ns()),
        reader.pin(reviewer.DEPENDENCIES['cohorts'][0]))
    game,backend,helpers,auditor = cohorts.dependencies()
    main = read(job['main_binding'])
    reviewer.validate_main_binding(main,template)
    require(job['main_guard_source']['sha256'] == 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3',
            'Exact main owner/file/health predicate required')
    window = reader.checked_module('_quality32_main_'+str(time.time_ns()),job['main_guard_source'])
    window.owner_and_files(main)
    baseline_wire = base.read_API_bytes();baseline = base.raw_witness_module().parse_wire(baseline_wire)
    window.healthy(baseline,baseline,main['experiment'],time.time())
    binding_dir = Path(job['binding_directory'])
    require(binding_dir.is_absolute() and binding_dir.resolve() == binding_dir, 'Owned resolved binding directory required')
    future_paths = [binding_dir,Path(config['output']),Path(job['campaign_parameters']['directory']),
                    Path(job['review_output']),Path(job['review_execution'])]
    require(len(set(future_paths)) == len(future_paths) and all(not path.exists() for path in future_paths),
            'Every future output must be distinct and absent; no retrospective adoption')
    for unit in (config['unit'],config['unit'].removesuffix('.service')+'.timer',
                 job['review_unit'],job['review_unit'].removesuffix('.service')+'.timer'):
        require(base.unit_fields(unit).get('LoadState') == 'not-found', 'Future original unit name already exists')
    for entry in job['binary_inputs']:
        require(reader.pin(entry['path']) == entry, 'Selected executable, ROM or boot input changed')
    paths = dict(pilot_closure=str(Path(config['output'])/'native-terminal-archive/root-original-result-and-owned-release.json'),
                 main_observations=str(binding_dir/'main-observations.json'))
    review_job = dict(closed_context_path=str(binding_dir/'closed-context.json'),runtime_paths=paths,
                     lease_path=job['lease_path'],lease_identity=job['lease_identity'])
    idle_plan = dict(job=dict(gpu_uuid='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'))
    base.idle_GPU(review_job,idle_plan)
    inputs = dict(job=job,template=template,review_job=review_job,reader=reader,reviewer=reviewer,
        cohorts=cohorts,game=game,main=copy.deepcopy(main),baseline=baseline,baseline_wire=baseline_wire,
        window=window,config_pin=reader.pin(config_pin['path']))
    result = guard_class(base)(config,inputs)
    result.validate_config(config)
    result.prepare_bindings()
    require('torch' not in sys.modules, 'Original observer imported numerical runtime')
    return result


if __name__ == '__main__':
    print('PLAN_ONLY: unselected original observer; no reads, queries, outputs, launches or publication')
