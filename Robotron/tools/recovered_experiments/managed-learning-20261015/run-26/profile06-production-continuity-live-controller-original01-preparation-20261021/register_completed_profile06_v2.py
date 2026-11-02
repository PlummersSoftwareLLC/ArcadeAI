"""Register an actually verified handoff and publish its read-only monitor.

Never starts/stops a service, changes controls, modifies a model or promotes a
policy. Requires actual successful controller/rescue closures and live192.
"""
import argparse
import re
import shlex
import importlib.util
import json
from pathlib import Path
import time
import urllib.request


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME/'logs/managed-learning-20261015/run-26'


def load(path,name):
    spec = importlib.util.spec_from_file_location(name,path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value



def check_resources(l,reviewer,fields,runtime,memory,tasks):
    l.require(reviewer.duration_seconds(fields['CPUQuotaPerSecUSec']) == 2
        and fields['MemoryMax'] == str(memory) and fields['MemorySwapMax'] == '0'
        and reviewer.duration_seconds(fields['RuntimeMaxUSec']) == runtime
        and fields['TasksMax'] == str(tasks)
        and reviewer.duration_seconds(fields['TimeoutStopUSec']) == 5
        and fields['SendSIGKILL'] == fields['Restart'] == 'no','Original resource descriptor differs')


def check_original_audits(l,reviewer,reader,live,plan,stopped,startup,installed):
    read = lambda entry,as_json=True:reader.read_pin(entry,as_json=as_json)
    kernel_pin = l.full_pin(live.parent/'current-cgroup-save-recovery-kernel-original01/root-kernel-and-all24-lifecycles-independent-readback-v2.json')
    l.require(kernel_pin['sha256'] == 'c619978ca38973aec58994e54aaff06ff7fb9461dfa83fe948dab1390bfdee32','Original kernel readback changed')
    kernel = read(kernel_pin)
    l.require(kernel['all24_original_descriptors_and_owned_releases_verified'] is True,'Original kernel lifecycles incomplete')
    reports = {}; CPU_closures = {}; copies = {}
    for purpose in ('newest_stopped','startup'):
        directory = live/purpose
        config_pin = l.full_pin(directory/'CPU-controller-config.json'); config = read(config_pin)
        closure_pin = l.full_pin(directory/'cpu-execution/root-original-result-and-owned-release.json'); closure = read(closure_pin)
        owner_pin = l.full_pin(directory/'cpu-execution/root-original-identity.json'); owner = read(owner_pin)
        fields = reviewer.archived_closure(closure,owner,read,exit_zero=True)
        check_resources(l,reviewer,fields,180,4<<30,128)
        expected = ['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+config['argv']
        match = re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart'])
        l.require(match is not None and shlex.split(match[1]) == expected,'Original CPU command differs')
        l.require(l.show(owner['unit'])['LoadState'] == l.show(owner['timer'])['LoadState'] == 'not-found','Original CPU owned release incomplete')
        rp = l.full_pin(directory/'CPU-report-readonly.json'); report = read(rp)
        l.require(report['status'] == 'PASS' and report['phase_metadata_verified'] is True
            and report['adam_state_count'] == 81 and report['adam_group_count'] == 1
            and report['cuda_initialized'] is False and report['visible_cuda_devices'] == 0
            and report['actual_restore_or_optimizer_step'] is False,'Original strict CPU result differs')
        archived = report['verification_copy']; actual_copy = l.full_pin(archived['path'])
        l.require(actual_copy['identity']['mode'] == '0o444'
            and all(actual_copy[key] == archived[key] for key in ('path','sha256','bytes'))
            and all(actual_copy['identity'][key] == archived[key] for key in ('device','inode','mtime_ns','ctime_ns','mode','uid','nlink')),
            'Original independent CPU copy changed')
        l.require(actual_copy['sha256'] == report['sha256'],'Original CPU report and bytes disagree')
        producer = report['source_before']
        # The actual producer was observed in normal mode. Its mutable latest
        # pathname may legitimately have autosaved since the stopped snapshot.
        l.require(producer['mode'] == '0o664','Normal producer mode changed during acquisition')
        reports[purpose] = report
        copies[purpose] = actual_copy
        CPU_closures[purpose] = dict(report=rp,closure=closure_pin,owner=owner_pin,config=config_pin,
            descriptor_exits=[a['exit'] for a in closure['full_original_archives']])
    stopped_report = reports['newest_stopped']; started_report = reports['startup']
    l.require(stopped['report'] == CPU_closures['newest_stopped']['report']
        and startup['CPU_report'] == CPU_closures['startup']['report'],'Actual stage/CPU report chain differs')
    delta = startup['startup_update_count']
    l.require(type(delta) is int and delta in (0,1),'Unexpected startup update count')
    for name,increment in [('training_steps',delta),('total_training_steps',delta),
        ('optimized_samples',delta*4096),('learner_frame_count',0),('frame_count',0),('measurement_frame_count',0)]:
        l.require(started_report['clocks'][name]-stopped_report['clocks'][name] == increment,'Actual startup clock differs: '+name)
    l.require(started_report['adam_step_min']-stopped_report['adam_step_min'] == delta
        and started_report['adam_step_max']-stopped_report['adam_step_max'] == delta
        and started_report['logical_training_steps_minus_adam_step'] == stopped_report['logical_training_steps_minus_adam_step'],
        'Actual startup Adam clocks differ')
    stopped_pin = l.full_pin(live/'original_main_graceful_stop.json'); retired = read(stopped_pin)
    terminal_pin = l.full_pin(live/'actual-original-terminal-archive.json'); terminal = read(terminal_pin)
    l.require(retired['actual_exit'] == 0 and retired['original_absent'] is True
        and terminal['owner'] == plan['prior_original_owner']
        and terminal['original_terminal_before_any_source_change'] is True,'Original trainer terminal proof differs')
    fields = retired['original_terminal']; prior = plan['prior_original_owner']
    l.require(fields['InvocationID'] == prior['invocation_id'] and fields['ExecMainPID'] == str(prior['pid'])
        and fields['MainPID'] == '0' and fields['ExecMainCode'] == '1' and fields['ExecMainStatus'] == '0'
        and fields['NRestarts'] == '0' and fields['Result'] == 'success','Original trainer exit was not normal zero')
    for name,entry in terminal['archives'].items():
        l.require(entry['exit'] == 0 and entry['timed_out'] is False,'Original trainer archive command failed: '+name)
        read(entry['stdout'],False);read(entry['stderr'],False)
    read(terminal['console_tail'],False)
    l.require(terminal['final_save']['actual_original_stdout_tail_verified'] is True
        and terminal['final_save']['actual_replay_flush_success_logged'] is True
        and terminal['final_save']['caught_replay_or_bank_save_failure'] is False,'Original graceful save failed')
    l.require(stopped['ring_continuity']['original_replay_storage_objects_preserved'] is True
        and stopped['ring_continuity']['source_derived_pointer_consistency'] is True
        and stopped['bank_intent_fulfillment']['all_target_revisions_now_persisted'] is True
        and startup['replay_storage_and_bank_identity_verified'] is True,'Original replay/bank continuity missing')
    l.require(stopped_report['sha256'] == stopped['checkpoint']['sha256']
        and stopped_report['clocks']['learner_frame_count'] == 1719906551
        and stopped_report['clocks']['optimized_samples'] == 27292198912,'Actual newest stopped state differs')
    return dict(original_kernel=kernel_pin,original_CPU_closures=CPU_closures,
        original_stopped_trainer=stopped_pin,original_terminal_archive=terminal_pin,
        original_verification_copies=copies,all24_handoff_and_CPU_descriptors_verified=True,
        normal_producer_modes_preserved=True,actual_startup_update_count=delta,
        actual_stopped_clocks=stopped_report['clocks'],actual_startup_clocks=started_report['clocks'],
        actual_Adam_clocks_preserved=True,original_tests_retried=False)


def execute(directory):
    l = load(directory/'sources/handoff_linux_v1.py','_register_linux')
    l.require(directory.parent == RUN and directory.name == 'profile06-production-continuity-live-controller-original01-preparation-20261021',
              'One selected actual handoff preparation required')
    plan_pin = l.full_pin(directory/'plan.json')
    plan = json.loads(l.checked(plan_pin))
    l.require(plan_pin['sha256'] == 'ebaaf494d421532cfdc2ae94ae4fb5d99bef29bd529b642d18e6b29d8f4a4122','Original selected plan differs')
    live = Path(plan['live_output'])
    result_pin = l.full_pin(live/'result.json')
    result = json.loads(l.checked(result_pin))
    l.require(result['status'] == 'SCORE_CARRY_HANDOFF_VERIFIED_ORIGINAL192_LEARNING'
              and result['original_stop_attempts'] == result['replacement_start_attempts'] == 1,
              'Actual successful original controller result required')
    reader = l.module(plan['base_live_job']['dependencies']['reader'],'_register_reader')
    reviewer = l.module(plan['archive_checker'],'_register_archive_reviewer')
    guard = l.module(plan['base_live_job']['dependencies']['main_guard'],'_register_main_guard')
    raw = l.module(plan['base_live_job']['dependencies']['raw_API'],'_register_raw_API')
    read = lambda entry,as_json=True:reader.read_pin(entry,as_json=as_json)
    closures = {}
    for role in ('controller','rescue'):
        pin = l.full_pin(directory/(role+'-unit/root-original-result-and-owned-release.json'))
        closure = json.loads(l.checked(pin))
        fields = reviewer.archived_closure(closure,closure['original'],read,exit_zero=True)
        check_resources(l,reviewer,fields,2300 if role == 'rescue' else 1800,1<<30 if role == 'rescue' else 4<<30,256)
        l.require(l.show(closure['original']['unit'])['LoadState'] ==
                  l.show(closure['original']['timer'])['LoadState'] == 'not-found','Original owned cleanup incomplete')
        closures[role] = pin
    owner = result['live']['owner']
    l.live_owner(owner)
    prepared = json.loads(l.checked(plan['prepared']))
    binding = json.loads(l.checked(prepared['original_main']))
    installed = json.loads((live/'exact_parser_and_resume_record_installed.json').read_bytes())
    startup = json.loads((live/'same_replacement_startup_verified.json').read_bytes())
    stopped = json.loads((live/'newest_stopped_checkpoint_CPU_verified.json').read_bytes())
    l.require(installed['parser']['sha256'] == l.NEW_SOCKET_SHA and startup['CPU_report']
              and stopped['actual_original_CPU_exit'] == 0,'Actual newest-state/startup verification chain missing')
    audits = check_original_audits(l,reviewer,reader,live,plan,stopped,startup,installed)
    for key in ('phase_record','phase_dropin'):
        l.checked(installed[key])
    slot = GAME/'models_dqn/managed_save.request.json.completed'
    l.require(slot.read_bytes() == (live/'startup-slot-after.json').read_bytes()
              and json.loads(slot.read_bytes()) == dict(tag=plan['case']+'-startup'),'Original completed startup slot differs')
    changes = {str(GAME/'Scripts/dqn/socket_server.py'),str(slot),installed['phase_dropin']['path']}
    observed_changes = {}
    for path,sha in binding['held_hashes'].items():
        now = l.full_pin(path)
        if now['sha256'] != sha:
            l.require(path in changes,'An unselected original held input changed: '+path)
            observed_changes[path] = dict(before=sha,after=now['sha256'])
        binding['held_hashes'][path] = now['sha256']
    l.require(l.full_pin(GAME/'Scripts/dqn/socket_server.py')['sha256'] == l.NEW_SOCKET_SHA,'Actual deployed parser differs')
    for key in ('phase_record','phase_dropin'):
        entry = installed[key]
        l.checked(entry)
        binding['held_hashes'][entry['path']] = entry['sha256']
    output = directory/'completed-registration'
    output.mkdir(mode=0o700)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:
        wire = response.read(raw.MAX_WIRE_BYTES+1)
    api = raw.parse_wire(wire)
    l.require(api['host_pipeline']['learning_exposure']['replay']['process_id'] == owner['pid'],
              'Current API does not belong to the actual replacement')
    baseline = l.publish(output/'baseline-API.raw.json',wire)
    witness = l.publish(output/'baseline-API-witness.json',raw.witness_fields(api,baseline))
    binding.update(owner=owner,baseline_API=baseline)
    guard.owner_and_files(binding)
    guard.healthy(api,api,binding['experiment'],time.time())
    latest = GAME/'models_dqn/robotron_dqn_latest.pt'
    l.require(0 <= time.time()-latest.stat().st_mtime <= 360 and latest.stat().st_size > 200 << 20,
              'Latest checkpoint is not current')
    binding_pin = l.publish(output/'current-main-binding.json',binding)
    monitor = '''import importlib.util,json,time,urllib.request
from pathlib import Path
def load(entry,name):
 import hashlib
 assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256']
 s=importlib.util.spec_from_file_location(name,entry['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
PINS = __PINS__
l=load(PINS['linux'],'_current_linux');reader=load(PINS['reader'],'_current_reader');guard=load(PINS['guard'],'_current_guard');raw=load(PINS['raw'],'_current_raw')
b=reader.read_pin(PINS['binding']);l.live_owner(b['owner']);guard.owner_and_files(b)
with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:wire=response.read(raw.MAX_WIRE_BYTES+1)
a=raw.parse_wire(wire);guard.healthy(a,reader.read_pin(b['baseline_API']),b['experiment'],time.time())
assert a['host_pipeline']['learning_exposure']['replay']['process_id']==b['owner']['pid']
latest=l.MODEL/'robotron_dqn_latest.pt';age=time.time()-latest.stat().st_mtime;assert 0<=age<=360 and latest.stat().st_size>200<<20
print(json.dumps(dict(classification='NEWEST_STATE_SCORE_CARRY_MAIN_LIVE_ORIGINAL192',owner=b['owner'],held_inputs=len(b['held_hashes']),original192_actor_identities_and_affinities_verified=True,client_count=a['client_count'],training_enabled=a['training_enabled'],measurement_active=a['measurement_active'],learner_frame_count=a['learner_frame_count'],training_steps=a['training_steps'],optimized_samples=a['optimized_samples'],fleet_fps=a['fps'],autosave_age_s=age,production_changed_by_this_monitor=False,quality_qualification=False,learning_speed_gain_verified=False)))
'''
    pins = dict(linux=plan['sources']['handoff_linux_v1.py'],reader=plan['base_live_job']['dependencies']['reader'],
        guard=plan['base_live_job']['dependencies']['main_guard'],raw=plan['base_live_job']['dependencies']['raw_API'],
        binding=binding_pin)
    monitor = monitor.replace('__PINS__',repr(pins))
    compile(monitor,'root-current-main-readonly-monitor.py','exec')
    monitor_pin = l.publish(output/'root-current-main-readonly-monitor.py',monitor.encode())
    l.live_owner(owner)
    guard.owner_and_files(binding)
    return l.publish(output/'root-independent-registration.json',dict(status='DEPLOYED_SCORE_CARRY_NEWEST_STATE_ORIGINAL192_REGISTERED',
        original_plan=plan_pin,original_controller_result=result_pin,original_closures=closures,
        newest_stopped_CPU=stopped['report'],startup_CPU=startup['CPU_report'],startup_update_count=startup['startup_update_count'],
        current_main_binding=binding_pin,current_main_monitor=monitor_pin,current_API_witness=witness,
        original_held_changes=observed_changes,newest_state_preserved=True,original192_PIDs_and_affinities_preserved=True,
        actual_parser=l.NEW_SOCKET_SHA,original_extended_audits=audits,protected_policy_changed=False,new_quality_qualification=False,
        learning_speed_gain_verified=False,goal_complete=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--handoff-preparation',type=Path)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, outputs or runtime actions')
        return 0
    if args.handoff_preparation is None:
        raise ValueError('Actual selected handoff preparation required')
    print(json.dumps(execute(args.handoff_preparation)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
