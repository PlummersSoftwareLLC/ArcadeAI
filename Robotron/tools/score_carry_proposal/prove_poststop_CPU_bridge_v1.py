"""Exercise Poststop.cpu with the actual historical1059 candidate acquisition.

No new candidate is acquired. The immutable original request/slot/owner/phase
proof is reused honestly as historical192-client evidence. The selected CPU149
verifier is launched through the new adapter/C218 bridge, without a main stop,
model load into training, replay mutation, source install or quality rerun.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import time
from types import SimpleNamespace


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME/'logs/managed-learning-20261015/run-26'
H = RUN/'future-score-carry-main-handoff-original01-preparation-20261019'


def load(path,name):
    spec = importlib.util.spec_from_file_location(name,path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def execute(output):
    l = load(Path(__file__).parent/'handoff_linux_v1.py','_bridge_linux')
    require = l.require
    require(output.parent == RUN and not output.exists()
            and output.name.startswith('future-handoff-poststop-CPU-bridge-original'), 'One new private bridge output required')
    source_pins = {name:l.full_pin(Path(__file__).parent/name) for name in
                  ('handoff_linux_v1.py','handoff_poststop_v1.py','prove_poststop_CPU_bridge_v1.py')}
    p = l.module(source_pins['handoff_poststop_v1.py'],'_bridge_poststop')
    prepared_pin = l.full_pin(H/'prepared-inputs.json')
    prepared = json.loads(l.checked(prepared_pin))
    main = json.loads(l.checked(prepared['original_main']))
    guard = load(RUN/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
                 '_bridge_original_guard')
    guard.owner_and_files(main)
    config_pin = l.full_pin(H/'poststop-inputs-original04/poststop-inputs.json')
    config = json.loads(l.checked(config_pin))
    original_job_pin = l.full_pin(RUN/'confirmed-scoring-candidate-CPU-original01-preparation-20261018/candidate-CPU-job.json')
    historical = json.loads(l.checked(original_job_pin))
    spec = historical['phase_snapshot']
    acquisition = json.loads(l.checked(spec['acquisition']))
    require(spec['purpose'] == acquisition['purpose'] == 'candidate' and spec['observed_clients'] == 192
            and acquisition['client_count'] == 192 and spec['owner'] == main['owner']
            and historical['source']['sha256'] == '4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e',
            'Exact original historical1059 acquisition required')
    output.mkdir(mode=0o700)
    l.publish(output/'bridge-intent.json',dict(status='HISTORICAL_CANDIDATE_CPU_BRIDGE_ONLY',
        historical_job=original_job_pin,historical_acquisition=spec['acquisition'],poststop_inputs=config_pin,
        source_pins=source_pins,main_stop_selected=False,new_candidate_acquired=False,quality_rerun=False))
    b = SimpleNamespace(job=dict(backend_source=source_pins['handoff_linux_v1.py'],poststop_inputs=config_pin,
        prepared=prepared_pin,case=config['case']),owner=main['owner'],main=main,out=output)
    b.event = lambda name,value:l.publish(output/name,value)
    b.reader = l.module(l.full_pin(GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'),
                        '_bridge_pin_reader')
    adapter = p.prepare(b)
    b.state = lambda: l.publish(output/'bridge-CPU-state.json',adapter.recovery_state())
    require(adapter.expected == spec['expected_phase'],'Current original phase differs from historical candidate phase')
    report,proof,source,closure = adapter.cpu('candidate',historical['source']['path'],spec['owner'],spec['phase_record'],
        spec['boot_checkpoint'],spec['boot_verification'],spec['expected_phase'],acquisition,historical['clock_floor'],
        observed_clients=192)
    require(json.loads((output/'candidate/acquisition.json').read_bytes()) == acquisition,
            'The bridge rewrote historical acquisition values')
    require(report['status'] == 'PASS' and report['phase_metadata_verified'] is True
            and report['clocks']['learner_frame_count'] == 1059300354
            and report['actual_restore_or_optimizer_step'] is False,'Actual strict bridge CPU proof differs')
    guard.owner_and_files(main)
    for pin in source_pins.values():
        l.checked(pin)
    return l.publish(output/'root-independent-readback.json',dict(status='ACTUAL_POSTSTOP_STRICT149_C218_CPU_BRIDGE_PASS',
        observed_unix_s=time.time(),actual_CPU_report=proof,actual_original_CPU_closure=closure,
        historical_source=source,historical_acquisition=spec['acquisition'],historical_acquisition_values_unchanged=True,
        observed_clients_scope=192,source_pins=source_pins,actual_newest_stopped_CPU_run=False,
        actual_zero_client_startup_CPU_run=False,new_candidate_acquired=False,main_original193_holds_preserved=True,
        production_changed=False,quality_qualification=False,learning_speed_gain_verified=False,
        scope='Actual new adapter archive/job/recipe/phase/C218 execution path with the historical1059 snapshot. No current checkpoint acquisition, no live source handoff or model/replay restoration.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, outputs, queries or runtime actions')
        return 0
    if args.output is None:
        raise ValueError('One new explicit private bridge output required')
    print(json.dumps(execute(args.output)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
