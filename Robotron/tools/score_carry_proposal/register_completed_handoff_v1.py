"""Register an actually verified handoff and publish its read-only monitor.

Never starts/stops a service, changes controls, modifies a model or promotes a
policy. Requires actual successful controller/rescue closures and live192.
"""
import argparse
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


def execute(directory):
    l = load(directory/'sources/handoff_linux_v1.py','_register_linux')
    l.require(directory.parent == RUN and directory.name.startswith('future-score-carry-live-controller-original'),
              'One selected actual handoff preparation required')
    plan_pin = l.full_pin(directory/'plan.json')
    plan = json.loads(l.checked(plan_pin))
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
        reviewer.archived_closure(closure,closure['original'],read,exit_zero=True)
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
    changes = {str(GAME/'Scripts/dqn/socket_server.py'),str(GAME/'models_dqn/managed_save.request.json.completed')}
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
        actual_parser=l.NEW_SOCKET_SHA,protected_policy_changed=False,new_quality_qualification=False,
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
