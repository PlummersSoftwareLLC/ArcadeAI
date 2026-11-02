"""Newest-state verification, exact parser install and one forward startup.

Prepared inputs must be independently pinned before LinuxBackend prepares this
adapter. Importing it performs no reads or runtime actions. Recovery preserves
an unverified live handle; it never stops or retries a replacement on expiry.
"""
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shutil
import time
import zipfile


CLOCKS = ('training_steps','optimized_samples','learner_frame_count','frame_count')
VERIFIER_SHA = '14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'
CONTROLLER_SHA = '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'


def require(value,message):
    if not value:
        raise RuntimeError(message)


def load_linux(job):
    entry = job['backend_source']
    path = Path(entry['path'])
    require(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'],
            'Prepared Linux backend changed')
    spec = importlib.util.spec_from_file_location('_poststop_linux_primitives',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.checked(entry)
    return module


def clock_floor(value):
    require(all(type(value.get(k)) is int and value[k] > 0 for k in CLOCKS), 'Four positive clocks required')
    return {k:value[k] for k in CLOCKS}


def startup_delta(value,baseline):
    now,before = clock_floor(value),clock_floor(baseline)
    require(all(now[k] == before[k] for k in ('learner_frame_count','frame_count')),
            'Input frames advanced before actor admission')
    updates = now['training_steps']-before['training_steps']
    require(updates in (0,1) and now['optimized_samples']-before['optimized_samples'] == updates*4096,
            'Startup work exceeds the actual0or1 batch path')
    return dict(startup_update_count=updates,logical_sample_delta=updates*4096,
                learner_frame_delta=0,raw_frame_delta=0)


def expected_phase(boot_report,resume_pin):
    phase = boot_report['saved_priority_metric_phase']
    require(boot_report['status'] == 'PASS' and boot_report['phase_metadata_verified'] is True
            and phase['metric'] == 'ce' and phase['valid'] is True, 'Strict original boot CE phase required')
    return {k:phase[k] for k in ('metric','phase_id','root_precommit_sha256','started_from','valid')} | dict(
        founder_phase_record_sha256=phase['phase_record_sha256'],last_resume_record_sha256=resume_pin['sha256'])


def archive(linux,source,destination):
    before = linux.full_pin(source)
    with Path(source).open('rb') as src, Path(destination).open('xb') as dst:
        shutil.copyfileobj(src,dst,1 << 20)
        dst.flush()
        os.fchmod(dst.fileno(),0o444)
        os.fsync(dst.fileno())
    result = linux.full_pin(destination)
    require(linux.full_pin(source) == before and result['sha256'] == before['sha256']
            and result['bytes'] == before['bytes'], 'Newest checkpoint/archive changed during copy')
    return result


def publish_request_exclusive(linux,staging,request):
    """Canonical save-slot publication must never replace a foreign request."""
    staged = linux.full_pin(staging)
    require(staged['identity']['mode'] == '0o444','Immutable staged request required')
    os.link(staging,request)  # Fails if another request was published meanwhile.
    Path(staging).unlink()
    published = linux.full_pin(request)
    require(published['sha256'] == staged['sha256'] and published['bytes'] == staged['bytes'],
            'Published save request bytes differ')
    return published


def final_save_journal(raw,owner,start,end):
    require(isinstance(raw,bytes) and 0 < len(raw) <= 4 << 20,'Bounded actual final-save journal required')
    messages = []
    for line in raw.splitlines():
        if not line:
            continue
        row = json.loads(line)
        require(row.get('_SYSTEMD_INVOCATION_ID') == owner['invocation_id']
                and row.get('_PID') == str(owner['pid']) and isinstance(row.get('MESSAGE'),str),
                'Final-save journal contains another producer/invocation')
        stamp = int(row['__REALTIME_TIMESTAMP'])/1e6
        require(start <= stamp <= end,'Final-save journal escaped the actual stop window')
        messages.append(row['MESSAGE'])
    require(messages and not any('save failed:' in message or 'restore failed during shutdown' in message
                                for message in messages),'The actual final save logged a failure')
    text = '\n'.join(messages)
    required = ('Flushing mmap replay buffer (6,000,000 transitions)',
                'Replay mmap flushed in ','Final model & settings saved','Shutdown complete')
    positions = [text.find(value) for value in required]
    require(all(value >= 0 for value in positions) and positions == sorted(positions),
            'The original final replay/model/shutdown success sequence is incomplete')
    return dict(original_final_save_messages_verified=True,producer_pid=owner['pid'],
                invocation_id=owner['invocation_id'],journal_messages=len(messages),
                actual_stop_window=[start,end],caught_replay_or_bank_save_failure=False)


def ring_continuity(boot,stopped,exposure,expected_pid):
    require(boot['spec'] == stopped['spec'] and boot['spec']['capacity'] == 6000000,
            'Original boot/stopped replay geometry differs')
    require(exposure['schema'] == 'robotron-replay-insert-exposure-v1' and exposure['enabled'] is True
            and exposure['available'] is True and exposure['process_id'] == expected_pid
            and type(exposure['epoch']) is int and exposure['epoch'] == 1
            and exposure['epoch_reason'] == 'directory_adopt_begin'
            and type(exposure['accepted_total']) is int and exposure['accepted_total'] >= 0,
            'Original no-reload replay insertion provenance differs')
    before,after = boot['ring'],stopped['ring']
    expected = (before['meta']['ptr']+exposure['accepted_total'])%6000000
    require(after['meta']['size'] == 6000000 and after['meta']['ptr'] == expected,
            'Stopped replay metadata does not contain the final insertion position')
    require(set(before['arrays']) == set(after['arrays']) and len(before['arrays']) == 10,
            'Original replay storage set differs')
    for name,left in before['arrays'].items():
        right = after['arrays'][name]
        require(all(left[k] == right[k] for k in ('path','dtype','shape','data_offset','data_bytes','header_sha256'))
                and all(left['identity'][k] == right['identity'][k]
                        for k in ('device','inode','size','uid','nlink')),'Original replay storage was replaced: '+name)
    return dict(original_replay_storage_objects_preserved=True,boot_pointer=before['meta']['ptr'],
        actual_completed_insertions=exposure['accepted_total'],expected_stopped_pointer=expected,
        actual_stopped_pointer=after['meta']['ptr'],source_derived_pointer_consistency=True,
        actual_state_payload_values_read_or_hashed=False)


class Poststop:
    def __init__(self,backend):
        self.b = backend
        self.linux = load_linux(backend.job)
        self.config = json.loads(self.linux.checked(backend.job['poststop_inputs']))
        c = self.config
        require(c['schema'] == 'robotron-score-carry-poststop-inputs-v1'
                and c['case'] == backend.job['case'] and c['original_owner'] == backend.owner,
                'Post-stop inputs belong to another case/owner')
        for entry in c['pins']:
            self.linux.checked(entry)
        require(c['verifier']['sha256'] == VERIFIER_SHA and c['cpu_controller']['sha256'] == CONTROLLER_SHA,
                'Use the original strict149 verifier and C218 lifecycle')
        for name in ('verifier','cpu_controller','cpu_template','boot_CPU_report','original_phase_record',
                     'bank_helper','archive_checker','settings_archive','phase_dropin','boot_replay_snapshot'):
            self.linux.checked(c[name])
        require(c['phase_dropin']['path'] == '/run/user/'+str(os.getuid())+'/systemd/user/'+
                backend.owner['unit']+'.d/91-per-priority-phase.conf','Only the original phase dropin is selected')
        self.template = json.loads(self.linux.checked(c['cpu_template']))
        self.boot_report = json.loads(self.linux.checked(c['boot_CPU_report']))
        self.boot_replay = json.loads(self.linux.checked(c['boot_replay_snapshot']))
        self.expected = expected_phase(self.boot_report,c['original_phase_record'])
        require(c['boot_checkpoint']['sha256'] == self.boot_report['sha256']
                and c['boot_checkpoint']['bytes'] == self.boot_report['bytes'], 'Actual original boot differs')
        phase = json.loads(self.linux.checked(c['original_phase_record']))
        require(phase['checkpoint'] == c['boot_checkpoint'] and phase['action'] == 'resume',
                'Current process startup record differs from actual boot')
        require(self.template['source_control_context']['held_recipe_context']['optimizer_lr'] == 1.25e-5
                and self.template['source_control_context']['held_recipe_context']['max_samples_per_frame'] == 8,
                'The full recipe must remain unchanged')
        for pair in self.template['phase_snapshot']['sources'].values():
            require(self.linux.checked(pair['current']) == self.linux.checked(pair['archive']),
                    'Actual numerical source archive differs')
        self.cpu_controller = self.linux.module(c['cpu_controller'],'_handoff_C218')
        self.banks = self.linux.module(c['bank_helper'],'_handoff_stopped_banks')
        self.archive_checker = self.linux.module(c['archive_checker'],'_handoff_CPU_archive_checker')
        self.saved = self.installed = self.bank_snapshot = self.phase_pin = None
        self.start_requested = False
        self.cpu_purpose = None
        self.cpu_config = None
        self.commands = 0
        self.startup_save_paused_owner = None

    def recovery_state(self):
        return dict(start_requested=self.start_requested,cpu_purpose=self.cpu_purpose,
                    cpu_config=self.cpu_config,saved=self.saved,installed=self.installed,
                    phase_record=self.phase_pin,bank_snapshot=self.bank_snapshot,
                    startup_save_paused_owner=self.startup_save_paused_owner)

    def sealed_bank_semantics(self,banks):
        return bank_metadata_semantics(banks,self.b.bank_reader)

    def command(self,argv,timeout=30):
        import subprocess
        self.commands += 1
        prefix = 'poststop-command-'+str(self.commands)
        result = subprocess.run(argv,capture_output=True,timeout=timeout)
        self.b.event(prefix+'-stdout.txt',result.stdout)
        self.b.event(prefix+'-stderr.txt',result.stderr)
        self.b.event(prefix+'.json',dict(argv=argv,exit=result.returncode,observed_unix_s=time.time()))
        require(result.returncode == 0,'Forward handoff command failed: '+repr(argv))

    def archive_original_terminal(self,retired):
        import subprocess
        b,l = self.b,self.linux
        self.absent_original()
        start = math.floor(retired['stop_requested_unix_s'])-2
        end = math.ceil(time.time())
        commands = [('show',['systemctl','--user','show',b.owner['unit']]),
                    ('cat',['systemctl','--user','cat',b.owner['unit']]),
                    ('journal',['journalctl','--user','--no-pager','-o','json','--since','@'+str(start),
                        '--until','@'+str(end),'_SYSTEMD_INVOCATION_ID='+b.owner['invocation_id']])]
        archives = {}
        for name,argv in commands:
            result = subprocess.run(argv,capture_output=True,timeout=20)
            stdout = b.event('original-terminal-'+name+'-stdout.txt',result.stdout)
            stderr = b.event('original-terminal-'+name+'-stderr.txt',result.stderr)
            archives[name] = b.event('original-terminal-'+name+'.json',dict(argv=argv,exit=result.returncode,
                stdout=stdout,stderr=stderr,owner=b.owner,observed_unix_s=time.time()))
            require(result.returncode == 0,'Actual original terminal descriptor failed: '+name)
            if name == 'journal':
                save = final_save_journal(result.stdout,b.owner,start,end)
        self.absent_original()
        return b.event('actual-original-terminal-archive.json',dict(owner=b.owner,archives=archives,
            final_save=save,journal_scope='Exact original invocation during the final stop/save window',
            original_terminal_before_any_source_change=True))

    def absent_original(self):
        b,l = self.b,self.linux
        value = l.show(b.owner['unit'])
        require(l.process_start(b.owner['pid']) is None and value.get('MainPID') == '0'
                and value.get('InvocationID') == b.owner['invocation_id']
                and value.get('ExecMainPID') == str(b.owner['pid']) and value.get('ExecMainCode') == '1'
                and value.get('ExecMainStatus') == '0' and value.get('NRestarts') == '0'
                and value.get('ActiveState') == 'inactive', 'Actual original exit0/absence required')
        group = Path('/sys/fs/cgroup'+b.owner['cgroup'])
        require(not group.exists() or not any((p/'cgroup.threads').read_text().strip()
                for p in [group,*[v for v in group.rglob('*') if v.is_dir()]]),
                'Old trainer cgroup still contains tasks')
        return value

    def fleet_held(self):
        b,l = self.b,self.linux
        l.live_owner(b.fleet)
        require((b.fleet_root/'cgroup.freeze').read_text().strip() == '1', 'Original fleet escaped its hold')
        for actor in b.fleet['original192_actors']:
            require(l.process_start(actor['pid']) == actor['starttime_ticks']
                    and sorted(os.sched_getaffinity(actor['pid'])) == actor['mask'], 'Original emulator changed')

    def cpu(self,purpose,source,owner,phase,boot,boot_proof,expected,acquisition,floor):
        b,l = self.b,self.linux
        require(self.cpu_purpose != purpose,'No CPU proof retry')
        directory = b.out/purpose
        directory.mkdir()
        source_pin = l.full_pin(source)
        copied = archive(l,source,directory/'model-readonly.pt')
        job = copy.deepcopy(self.template)
        job.update(source=source_pin,verification_copy=copied,clock_floor=clock_floor(floor),
                   experiment=b.main['experiment'],output_directory=str(directory/'cpu-output'))
        acquisition = dict(acquisition,schema='robotron-owned-phase-snapshot-acquisition-v1',purpose=purpose,
            experiment=job['experiment'],model_dir=str(l.MODEL),owner_before=owner,owner_after=owner,
            client_count=0,source_checkpoint={k:source_pin[k] for k in ('path','sha256','bytes')},
            clock_floor=job['clock_floor'],phase_record_sha256=phase['sha256'],boot_checkpoint=boot)
        acq_pin = b.event(purpose+'/acquisition.json',acquisition)
        job['phase_snapshot'].update(purpose=purpose,owner=owner,observed_clients=0,phase_record=phase,
            boot_checkpoint=boot,boot_verification=boot_proof,expected_phase=expected,acquisition=acq_pin)
        # These are the actual source/control/unit contexts of this acquisition.
        job['source_control_context']['archived_control'] = b.event(purpose+'/learning-control.json',l.CONTROL.read_bytes())
        import subprocess
        unit = subprocess.run(['systemctl','--user','cat',owner['unit']],capture_output=True,timeout=15)
        require(unit.returncode == 0,'Actual trainer unit archive unavailable')
        job['source_control_context']['archived_trainer_unit'] = b.event(purpose+'/trainer-unit.txt',unit.stdout)
        job['source_control_context']['provenance'] = [b.job['prepared'],b.job['poststop_inputs'],boot_proof,phase]
        job_pin = b.event(purpose+'/CPU-job.json',job)
        config = dict(unit='robotron-'+b.job['case']+'-'+purpose.replace('_','-')+'-CPU.service',
            output=str(directory/'cpu-execution'),argv=[self.config['python'],'-Xgil=0','-I','-B',
            self.config['verifier']['path'],'--execute','--job',job_pin['path'],'--expected-job-sha256',job_pin['sha256'],
            '--expected-verifier-sha256',VERIFIER_SHA],properties=['CPUQuota=200%','MemoryMax=4G',
            'RuntimeMaxSec=180','MemorySwapMax=0','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
            pins=[self.cpu_controller.pin(v['path']) for v in (self.config['cpu_controller'],self.config['verifier'],job_pin)],
            observation_s=240)
        config_pin = b.event(purpose+'/CPU-controller-config.json',config)
        self.cpu_purpose,self.cpu_config = purpose,config_pin
        b.state()  # Preserve the original CPU unit/config before scheduling it.
        self.cpu_controller.launch(config_pin['path'])
        lifecycle = self.cpu_controller.observe(config_pin['path'])
        closure = l.full_pin(directory/'cpu-execution/root-original-result-and-owned-release.json')
        owner_pin = l.full_pin(directory/'cpu-execution/root-original-identity.json')
        read = lambda v,as_json=True: b.reader.read_pin(v,as_json=as_json)
        self.archive_checker.archived_closure(lifecycle,json.loads(l.checked(owner_pin)),read,exit_zero=True)
        require(lifecycle['lifecycle_complete'] is True and type(lifecycle['original_exit']) is int
                and lifecycle['original_exit'] == 0,'Original CPU verifier did not complete successfully')
        report_pin = archive(l,directory/'cpu-output/cpu-verification.json',directory/'CPU-report-readonly.json')
        report = json.loads(l.checked(report_pin))
        require(report['status'] == 'PASS' and report['phase_metadata_verified'] is True
                and report['sha256'] == source_pin['sha256'],'Actual strict CPU report differs')
        return report,report_pin,source_pin,closure

    def verify_stopped(self,context,retired,banks):
        b,l = self.b,self.linux
        self.absent_original()
        self.fleet_held()
        terminal_archive = self.archive_original_terminal(retired)
        absence = b.event('actual-original-absence.json',dict(schema='robotron-live8-owned-trainer-absence-v1',
            trainer=b.owner,unit_main_pid=0,unit_active_state='inactive',old_process_absent=True,
            owned_cgroup_empty=True,latest_path=str(l.MODEL/'robotron_dqn_latest.pt')))
        report,proof,source,closure = self.cpu('newest_stopped',l.MODEL/'robotron_dqn_latest.pt',b.owner,
            self.config['original_phase_record'],self.config['boot_checkpoint'],self.config['boot_CPU_report'],
            self.expected,dict(tag=None,completed_slot_transition=None,stopped_absence=absence),banks['clock_floor'])
        self.bank_snapshot = self.banks.stopped_state(self.config['bank_spec'])
        ring = ring_continuity(self.boot_replay,self.bank_snapshot,banks['replay_exposure'],b.owner['pid'])
        bank_pin = b.event('actual-stopped-ring-and-banks.json',self.bank_snapshot)
        # Final save may publish another generation. Its bank mutation revision,
        # metadata values, geometry and storage objects must agree with the seal.
        final_banks = {name:b.bank_reader.read_bank_generation(name,l.MODEL/('robotron_dqn_latest_replay_'+name))
                       for name in ('hof','ephof')}
        verify_final_banks(banks['bank_pair']['banks'],final_banks,banks['bank_metadata_semantics'],
                           self.sealed_bank_semantics(final_banks))
        require(clock_floor(report['clocks']) == banks['clock_floor'],
                'Clocks changed after all input handlers finished and the budget was exhausted')
        self.saved = dict(actual_original_CPU_exit=0,strict_phase_verified=True,newest_stopped_source=True,
            replay_bank_consistency_verified=True,checkpoint=source,report=proof,CPU_closure=closure,
            ring_and_banks=bank_pin,ring_continuity=ring,original_terminal_archive=terminal_archive,
            clocks=clock_floor(report['clocks']))
        b.state()
        return self.saved

    def install(self,context,retired,saved):
        b,l = self.b,self.linux
        self.absent_original()
        self.fleet_held()
        l.checked(saved['checkpoint'])
        source = l.GAME/'Scripts/dqn/socket_server.py'
        source_pin = l.full_pin(source)
        require(source_pin['sha256'] == l.OLD_SOCKET_SHA,'Original parser changed before installation')
        changed = {str(source),str(l.CONTROL),str(l.MODEL/'game_settings.json')}
        for path,sha in b.main['held_hashes'].items():
            if path not in changed:
                require(l.full_pin(path)['sha256'] == sha,'An unselected held input changed: '+path)
        installed = l.atomic_owned_replace(source,source_pin,l.checked(b.prepared['proposed_socket']),suffix=b.job['case'])
        require(installed['sha256'] == l.NEW_SOCKET_SHA,'Selected parser bytes were not installed')
        settings = l.MODEL/'game_settings.json'
        l.atomic_owned_replace(settings,l.full_pin(settings),l.checked(self.config['settings_archive']),suffix=b.job['case'])
        b.control_pin = l.atomic_owned_replace(l.CONTROL,b.control_pin,b.control_bytes,suffix=b.job['case'])
        report = json.loads(l.checked(saved['report']))
        phase = report['saved_priority_metric_phase']
        self.phase_pin = b.event('resume-phase-record.json',dict(schema='robotron-priority-metric-start-v1',
            phase_id=phase['phase_id'],metric='ce',action='resume',previous_metric='ce',
            checkpoint={k:saved['checkpoint'][k] for k in ('path','sha256','bytes')},model_dir=str(l.MODEL),
            root_precommit_sha256=phase['root_precommit_sha256']))
        dropin = self.config['phase_dropin']
        old = self.config['original_phase_record']
        content = l.checked(dropin).decode()
        require(content.count(old['path']) == content.count(old['sha256']) == 1,'Original phase binding differs')
        content = content.replace(old['path'],self.phase_pin['path']).replace(old['sha256'],self.phase_pin['sha256'])
        new_dropin = l.atomic_owned_replace(dropin['path'],dropin,content.encode(),suffix=b.job['case'])
        self.command(['systemctl','--user','daemon-reload'])
        l.checked(saved['checkpoint'])
        self.installed = dict(exact_selected_parser=True,only_selected_source_changed=True,
            newest_checkpoint_unchanged=True,parser=installed,phase_record=self.phase_pin,phase_dropin=new_dropin)
        b.state()
        return self.installed

    def start_once(self,context,saved,installed):
        b,l = self.b,self.linux
        self.absent_original()
        self.fleet_held()
        require(not self.start_requested,'One replacement start only')
        l.checked(saved['checkpoint'])
        l.checked(installed['parser'])
        self.start_requested = True
        b.state()
        self.command(['systemctl','--user','start','--no-block',b.owner['unit']])
        def born():
            value = l.show(b.owner['unit'])
            pid = int(value.get('MainPID','0'))
            if not pid:
                return None
            require(value['InvocationID'] != b.owner['invocation_id'] and pid != b.owner['pid'],
                    'The expected new incarnation did not start')
            owner = dict(pid=pid,starttime_ticks=l.process_start(pid),unit=b.owner['unit'],
                         invocation_id=value['InvocationID'],cgroup=value['ControlGroup'])
            l.live_owner(owner)
            b.replacement = owner
            b.state()
            b.event('actual-replacement-birth.json',owner)
            return owner
        return b.wait(born,20,'The single replacement has not exposed its original live identity')

    def verify_startup(self,replacement,saved,installed):
        b,l = self.b,self.linux
        def ready():
            l.live_owner(replacement)
            try:
                api = b.api(observe_startup=True)
            except (OSError,ValueError,KeyError):
                return None
            if api is None:
                return None
            require(api['client_count'] == 0, 'Input arrived before the original frozen fleet was admitted')
            graphs = api['host_pipeline']['inference_graphs']
            if not (api['memory_buffer_size'] == 6000000 and graphs['ready'] is True
                    and graphs['capture_count'] == 128 and graphs['postload_validations'] == 1):
                return None
            return api
        api = b.wait(ready,600,'The same replacement has not exposed its actual dashboard')
        require(api['client_count'] == 0 and api['memory_buffer_size'] == 6000000
                and api['training_enabled'] is True and api['measurement_active'] is False,
                'Zero-client startup/replay state differs')
        graphs = api['host_pipeline']['inference_graphs']
        require(graphs['ready'] is True and graphs['capture_count'] == 128 and graphs['postload_validations'] == 1,
                'Actual exact-graph restoration is not ready')
        delta = startup_delta(api,saved['clocks'])
        self.banks.assert_unchanged(self.bank_snapshot,self.config['bank_spec'])
        maps = b.event('actual-startup-shared-replay-maps.json',self.banks.verify_maps(replacement['pid'],self.bank_snapshot))
        # A current startup snapshot is acquired and CPU-verified by the same
        # supported save slot. No protected or historical model is substituted.
        report,proof = self.startup_snapshot(replacement,saved)
        delta = startup_delta(report['clocks'],saved['clocks'])
        require(clock_floor(b.api()) == clock_floor(report['clocks']), 'Startup clocks moved after strict CPU proof')
        self.banks.assert_unchanged(self.bank_snapshot,self.config['bank_spec'])
        l.checked(installed['parser'])
        return dict(same_original_replacement=True,newest_state_preserved=True,
            replay_storage_and_bank_identity_verified=True,CPU_report=proof,shared_maps=maps,**delta)

    def startup_snapshot(self,owner,saved):
        # Stage immutable request bytes, then capture the actual canonical PIN
        # during one independently recoverable brief pause of this exact owner.
        b,l = self.b,self.linux
        slot = l.MODEL/'managed_save.request.json.completed'
        request = l.MODEL/'managed_save.request.json'
        tag = b.job['case']+'-startup'
        require(len(tag) <= 80 and not request.exists(),'A save request/tag is already owned')
        source = l.MODEL/'managed-checkpoints'/(tag+'.pt')
        require(not source.exists(),'The startup tag was already consumed')
        before_time = time.time()
        before = None if not slot.exists() else dict(actual_pin=l.full_pin(slot),archive=archive(l,slot,b.out/'startup-slot-before.json'))
        staging = request.with_name(request.name+'.'+b.job['case']+'.tmp')
        require(not staging.exists(),'The owned save staging path already exists')
        raw = (json.dumps(dict(tag=tag))+'\n').encode()
        l.publish(staging,raw)
        request_archive = b.event('startup-request-archive.json',raw)
        # Publication changes ctime, so the pre-publication PIN cannot honestly
        # claim the final canonical ctime. Keep the replacement paused only for
        # this local publication; the outer recovery state records its exact
        # owner before SIGSTOP, and an independent rescue resumes it if lost.
        import signal
        l.live_owner(owner)
        self.startup_save_paused_owner = owner
        b.state()
        os.kill(owner['pid'],signal.SIGSTOP)
        try:
            request_pin = publish_request_exclusive(l,staging,request)
            requested_at = time.time()
        finally:
            require(l.process_start(owner['pid']) == owner['starttime_ticks'],'Replacement changed during save request')
            os.kill(owner['pid'],signal.SIGCONT)
            self.startup_save_paused_owner = None
            b.state()
        def completed():
            l.live_owner(owner)
            return slot.exists() and json.loads(slot.read_bytes()) == dict(tag=tag) and not request.exists() and source.exists()
        b.wait(completed,60,'The same replacement startup save request is pending')
        after_time = time.time()
        after = dict(actual_pin=l.full_pin(slot),archive=archive(l,slot,b.out/'startup-slot-after.json'))
        os.chmod(source,0o444)
        expected = expected_phase(json.loads(l.checked(saved['report'])),self.phase_pin)
        transition = dict(before=before,request=dict(actual_pin=request_pin,archive=request_archive),after=after,
            before_unix_s=before_time,request_unix_s=requested_at,after_unix_s=after_time)
        report,proof,_,_ = self.cpu('startup',source,owner,self.phase_pin,
            {k:saved['checkpoint'][k] for k in ('path','sha256','bytes')},saved['report'],expected,
            dict(tag=tag,completed_slot_transition=transition,stopped_absence=None),saved['clocks'])
        return report,proof

    def verify_progress(self,context,replacement,startup):
        b,l = self.b,self.linux
        baseline = b.api()
        def progressing():
            l.live_owner(replacement)
            for actor in b.fleet['original192_actors']:
                require(l.process_start(actor['pid']) == actor['starttime_ticks']
                        and sorted(os.sched_getaffinity(actor['pid'])) == actor['mask'],'Original emulator changed after thaw')
            api = b.api()
            if api['client_count'] != 192:
                return None
            require({row['client_slot'] for row in api['client_rows']} == set(range(192)),'Reconnected slots differ')
            if (api['learner_frame_count'] <= baseline['learner_frame_count']
                    or api['optimized_samples'] <= baseline['optimized_samples']):
                return None
            require(api['training_enabled'] is True and api['measurement_active'] is False
                    and 0 <= time.time()-(l.MODEL/'robotron_dqn_latest.pt').stat().st_mtime <= 360,
                    'Learning/checkpoint health is not restored')
            return dict(original192_identities_preserved=True,training_progress_verified=True,pipeline_errors=0,
                owner=replacement,learner_frame_count=api['learner_frame_count'],optimized_samples=api['optimized_samples'],
                fleet_fps=api['fps'],quality_qualification=False,learning_speed_gain_verified=False)
        return b.wait(progressing,150,'The original192 actors have not reconnected with healthy learning')


def bank_metadata_semantics(banks,reader):
    result = {}
    for name,bank in banks.items():
        raw,pin = reader.small_file(bank['metadata']['path'],1 << 20)
        require(pin == bank['metadata'],'Captured bank metadata changed before semantic read')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            require(len(entries) == len({v.filename for v in entries})
                    and sum(v.file_size for v in entries) <= 1 << 20,'Bounded unique bank metadata required')
            result[name] = {v.filename:hashlib.sha256(archive.read(v.filename)).hexdigest() for v in entries}
    return result


def verify_final_banks(before,after,before_semantics,after_semantics):
    require(set(before) == set(after) == {'hof','ephof'},'Both real replay banks required')
    for name in before:
        # Generation names/file identities may change on the final synchronous
        # save; the sealed RAM revision and all saved metadata must not change.
        require(before[name]['selector']['mutation_generation'] == after[name]['selector']['mutation_generation']
                and all(before[name][k] == after[name][k] for k in
                        ('episodes','transitions','stride','state_size','captured_adds'))
                and before_semantics[name] == after_semantics[name]
                and all(before[name]['arrays'][k]['header'] == after[name]['arrays'][k]['header']
                        and before[name]['arrays'][k]['bytes'] == after[name]['arrays'][k]['bytes']
                        for k in before[name]['arrays']), 'Final save changed a sealed bank: '+name)


def recover_committed(job,state,*,observation_pending):
    l = load_linux(job)
    prepared = json.loads(l.checked(job['prepared']))
    base = json.loads(l.checked(prepared['original_main']))
    require(state['original_owner'] == base['owner'] and state['case'] == job['case']
            and state['original_stop_sent'] is True,'Committed recovery has foreign scope')
    owner = state.get('replacement') or state['original_owner']
    alive = l.process_start(owner['pid']) == owner['starttime_ticks']
    if alive:
        l.live_owner(owner)
        paused = state.get('poststop',{}).get('startup_save_paused_owner')
        if paused is not None:
            require(paused == state.get('replacement'),'Only the captured save-publication owner may be resumed')
            import signal
            os.kill(owner['pid'],signal.SIGCONT)
        return dict(status='SAME_REPLACEMENT_HANDLE_OBSERVATION_PENDING' if state.get('replacement') else
                    'SAME_ORIGINAL_HANDLE_OBSERVATION_PENDING',owner=owner,original_handle_preserved=True,
                    observation_pending=observation_pending,restart_retry=False,replacement_terminated=False,
                    source_rollback=False,protected_policy_loaded=False,replay_cleared=False,errors=[])
    # A controller loss after a committed stop requires a distinct forward
    # continuation bound to the actual newest checkpoint/CPU/source/CPU handle.
    # Preserve these exact inputs; never infer a successful start or retry here.
    return dict(status='COMMITTED_FORWARD_RECOVERY_REQUIRED',original_handle_preserved=False,
                actual_unit=l.show(base['owner']['unit']),poststop=state.get('poststop'),
                restart_retry=False,replacement_terminated=False,source_rollback=False,
                protected_policy_loaded=False,replay_cleared=False,errors=[])


def prepare(backend):
    return Poststop(backend)
